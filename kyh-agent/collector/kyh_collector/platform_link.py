"""Linked mode: feed the Beretta platform (Part 1) with fleet roll-ups.

The collector keeps everything that is about endpoints: signed agent reports, replay
protection, the silence rule and the 95% fleet roll-up. The platform keeps everything
that is about the policy: pricing, and the one warranty state machine.

For each linked company the link worker periodically:
  1. evaluates the company (same code as the dashboard);
  2. maps collector controls onto platform controls (several can feed one);
  3. sends one signed roll-up if anything meaningful changed, or as a heartbeat;
  4. stores the platform's answer (policy status, warranty states) for display.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import ssl
import threading
import urllib.error
import urllib.request

from . import evaluate as ev
from .core import ApiError, iso, parse

SCHEMA_ID = "kyh-fleet-rollup/1"
LINK_FILE = "platform_link.json"


# ------------------------------------------------------------------ configuration
def load_link(data_dir: str) -> dict | None:
    path = os.path.join(data_dir, LINK_FILE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_link(data_dir: str, url: str, collector_id: str, secret: str, ca_file: str | None = None,
              dashboard_url: str | None = None, name: str = "Beretta collector") -> str:
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, LINK_FILE)
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"url": url.rstrip("/"), "collector_id": collector_id, "secret": secret, "ca_file": ca_file,
                   "dashboard_url": dashboard_url, "name": name}, fh, indent=2)
    os.replace(path + ".tmp", path)
    return path


def link_company(conn, now, company_id: str, platform_company_id: str) -> None:
    if not conn.execute("SELECT 1 FROM companies WHERE id=?", (company_id,)).fetchone():
        raise ApiError(404, "NO_COMPANY", "unknown company")
    conn.execute("UPDATE companies SET platform_company_id=?, platform_linked_at=? WHERE id=?",
                 (platform_company_id, iso(now), company_id))
    conn.execute("INSERT INTO audit_log (at, actor, action, entity, detail) VALUES (?,?,?,?,?)",
                 (iso(now), "admin", "PLATFORM_LINKED", company_id, f"platform_company_id={platform_company_id}"))


# ------------------------------------------------------------------ mapping
def build_controls(snapshot: dict, s: dict) -> tuple[list, list]:
    """Group collector controls by platform control.

    FAIL if any source control fails; PASS if at least one passes and none fails;
    nothing is sent when every source is NOT_OBSERVABLE (absence of evidence is not sent
    as evidence). Returns (controls_to_send, unmapped_or_unobservable).
    """
    cmap, partial = s["platform_control_map"], set(s["platform_partial_on_pass"])
    rows = list(snapshot["controls"]) + [dict(snapshot["coverage"], tier="warranty",
                                              passing=snapshot["coverage"].get("reporting"),
                                              observed=snapshot["coverage"].get("declared"),
                                              failing_hosts=[])]
    groups, skipped = {}, []
    for r in rows:
        target = cmap.get(r["control"])
        if not target:
            skipped.append({"control": r["control"], "why": "no platform mapping"})
            continue
        if r["status"] not in ("PASS", "FAIL"):
            skipped.append({"control": r["control"], "why": r["status"], "platform_control_id": target,
                            "reason": r.get("reason", "")})
            continue
        groups.setdefault(target, []).append(r)
    # A source no host could observe is listed under the control it would have fed, if that control was sent.
    not_observed = {}
    for u in [u for u in skipped if u.get("platform_control_id") in groups]:
        not_observed.setdefault(u["platform_control_id"], []).append(u["control"])
    skipped = [u for u in skipped if u.get("platform_control_id") not in groups]
    out = []
    for target, srcs in sorted(groups.items()):
        failing = [r for r in srcs if r["status"] == "FAIL"]
        status = "FAIL" if failing else "PASS"
        value = "false" if failing else ("partial" if any(r["control"] in partial for r in srcs) else "true")
        def why(r):
            hosts = "; ".join(f"{h['host']}: {h['reason']}" for h in (r.get("failing_hosts") or [])[:5])
            return f"{r['control']}: {r['reason']}" + (f" (failing: {hosts})" if hosts else "")
        reason = "; ".join(why(r) for r in (failing or srcs))
        if value == "partial":
            reason += " (sent as partial: restore testing is not observable from endpoints)"
        hosts = []
        for r in failing:
            hosts += r.get("failing_hosts") or []
        out.append({"platform_control_id": target, "status": status, "value": value, "reason": reason[:600],
                    "observed": min(r["observed"] or 0 for r in srcs), "passing": min(r["passing"] or 0 for r in srcs),
                    "failing_hosts": hosts[:50],
                    "sources": [{"control": r["control"], "status": r["status"], "passing": r["passing"],
                                 "observed": r["observed"]} for r in srcs],
                    "not_observed": not_observed.get(target, [])})
    return out, skipped


def fleet_view(snapshot: dict) -> dict:
    return {"declared": snapshot["coverage"].get("declared"), "enrolled": snapshot["coverage"].get("enrolled"),
            "reporting": snapshot["coverage"].get("reporting"), "liveness_counts": snapshot["liveness_counts"],
            "collector_controls": [{k: c[k] for k in ("control", "tier", "status", "passing", "observed", "reason")}
                                   for c in snapshot["controls"]],
            "hosts": [{"agent_id": h["agent_id"], "host": h["hostname"], "os": h["os"],
                       "liveness": h["liveness"]["state"], "last_seen": h["last_seen"],
                       "simulated": h["simulated"], "build_trusted": h["build_trusted"],
                       "controls": {c: v["status"] for c, v in h["controls"].items()}}
                      for h in snapshot["hosts"]]}


def change_hash(controls: list, fleet: dict, coverage: dict) -> str:
    key = {"c": [(c["platform_control_id"], c["value"]) for c in controls],
           "cov": coverage.get("status"),
           "h": sorted((h["agent_id"], h["liveness"], tuple(sorted(h["controls"].items()))) for h in fleet["hosts"])}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def next_seq(conn) -> int:
    row = conn.execute("SELECT v FROM platform_meta WHERE k='seq'").fetchone()
    seq = (int(row["v"]) if row else 0) + 1
    conn.execute("INSERT OR REPLACE INTO platform_meta (k, v) VALUES ('seq', ?)", (str(seq),))
    return seq


# ------------------------------------------------------------------ transport
def sign(secret_hex: str, body: bytes) -> str:
    return "v1=" + hmac.new(bytes.fromhex(secret_hex), body, hashlib.sha256).hexdigest()


def _open(req, timeout, ctx):
    """Go direct (no system proxy) to localhost and private addresses, where a proxy cannot reach."""
    import ipaddress
    host = urllib.request.urlparse(req.full_url).hostname or ""
    try:
        direct = host == "localhost" or ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
    except ValueError:
        direct = False
    if direct:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                           urllib.request.HTTPSHandler(context=ctx)).open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def http_send(link: dict, body: bytes, timeout: float = 15):
    req = urllib.request.Request(link["url"] + "/api/collector/rollup", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-KYH-Collector-Id", link["collector_id"])
    req.add_header("X-KYH-Signature", sign(link["secret"], body))
    ctx = None
    if link["url"].startswith("https"):
        ctx = ssl.create_default_context(cafile=link.get("ca_file")) if link.get("ca_file") \
            else ssl.create_default_context()
    try:
        with _open(req, timeout, ctx) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except ValueError:
            return exc.code, {}
    except (urllib.error.URLError, OSError) as exc:
        return None, {"error": "UNREACHABLE", "message": str(getattr(exc, "reason", exc))}


# ------------------------------------------------------------------ one sync step
def sync_company(app, company_id: str, link: dict, force: bool = False, sender=http_send) -> dict:
    """Evaluate, decide, push, store. The HTTP call happens outside the database lock."""
    s, now = app.settings, app.clock()
    with app.lock:
        conn = app.conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            snap = ev.evaluate_company(conn, company_id, now, s)
            if not snap or not snap.get("linked"):
                conn.execute("ROLLBACK")
                return {"pushed": False, "why": "not linked"}
            controls, skipped = build_controls(snap, s)
            fleet = fleet_view(snap)
            h = change_hash(controls, fleet, snap["coverage"])
            ps = conn.execute("SELECT * FROM platform_state WHERE company_id=?", (company_id,)).fetchone()
            due = force or ps is None or not ps["last_ok"] or ps["last_hash"] != h or not ps["last_push_at"] or \
                (now - parse(ps["last_push_at"])).total_seconds() >= 60 * s["push_heartbeat_minutes"]
            if not due:
                conn.execute("ROLLBACK")
                return {"pushed": False, "why": "no change"}
            seq = next_seq(conn)
            conn.execute("COMMIT")
        finally:
            conn.close()

    company = snap["company"]
    payload = {"schema": SCHEMA_ID, "collector_id": link["collector_id"], "seq": seq, "sent_at": iso(app.clock()),
               "evaluated_at": snap["evaluated_at"],
               "collector_dashboard_url": link.get("dashboard_url"),
               "company": {"collector_company_id": company["id"], "platform_company_id": company["platform_company_id"],
                           "name": company["name"], "declared_endpoints": company["declared_endpoints"]},
               "coverage": snap["coverage"], "controls": controls, "unmapped": skipped, "fleet": fleet}
    body = json.dumps(payload, sort_keys=True, default=str).encode()
    status, resp = sender(link, body)
    ok = status == 200

    with app.lock:
        conn = app.conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            prev = conn.execute("SELECT response_json FROM platform_state WHERE company_id=?", (company_id,)).fetchone()
            conn.execute(
                "INSERT INTO platform_state (company_id, last_attempt_at, last_push_at, last_ok, last_http, last_error, "
                "last_hash, last_seq, sent_json, response_json) VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(company_id) DO UPDATE SET last_attempt_at=excluded.last_attempt_at, "
                "last_push_at=COALESCE(excluded.last_push_at, platform_state.last_push_at), last_ok=excluded.last_ok, "
                "last_http=excluded.last_http, last_error=excluded.last_error, "
                "last_hash=COALESCE(excluded.last_hash, platform_state.last_hash), last_seq=excluded.last_seq, "
                "sent_json=excluded.sent_json, "
                "response_json=COALESCE(excluded.response_json, platform_state.response_json)",
                (company_id, iso(now), iso(now) if ok else None, int(ok), status,
                 None if ok else f"{resp.get('error', 'HTTP ' + str(status))}: {resp.get('message', '')}"[:300],
                 h if ok else None, seq, json.dumps({"controls": controls, "unmapped": skipped}),
                 json.dumps(resp) if ok else (prev["response_json"] if prev else None)))
            conn.execute("COMMIT")
        finally:
            conn.close()
    return {"pushed": True, "ok": ok, "status": status, "seq": seq, "response": resp, "controls": controls}


# ------------------------------------------------------------------ background worker
class LinkWorker(threading.Thread):
    """Re-evaluates linked companies every push_interval_seconds, or right away when a report arrives.
    Periodic evaluation is also what turns a quiet host into SILENT without any new report."""

    def __init__(self, app, link: dict):
        super().__init__(daemon=True, name="kyh-platform-link")
        self.app, self.link = app, link
        self.wake = threading.Event()
        self.stopped = threading.Event()
        self.last = {}

    def run(self):
        while not self.stopped.is_set():
            self.wake.wait(self.app.settings["push_interval_seconds"])
            self.wake.clear()
            try:
                conn = self.app.conn()
                ids = [r["id"] for r in conn.execute("SELECT id FROM companies WHERE platform_company_id IS NOT NULL")]
                conn.close()
                for cid in ids:
                    self.last[cid] = sync_company(self.app, cid, self.link)
            except Exception as exc:  # noqa: BLE001 - the link must never take the collector down
                self.last["_error"] = repr(exc)

    def stop(self):
        self.stopped.set()
        self.wake.set()
