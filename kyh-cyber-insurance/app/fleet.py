"""Link to the KYH live-monitoring collector (Part 2).

The collector receives signed reports from the agents on every insured machine and
rolls them up into one result per control for the whole company. It sends that
roll-up here, signed. This module:

  1. authenticates the collector (HMAC over the exact body, increasing sequence number,
     timestamp within 5 minutes, company must be linked to that collector);
  2. stores the roll-up unchanged (append-only);
  3. records each control result as an AGENT_FLEET observation with
     TECHNICALLY_OBSERVED strength (Engine A), skipping exact repeats;
  4. lets the existing coverage engine evaluate warranties.

It never prices. Before bind the observations feed the next quote like any other
evidence; after bind they reach only the warranty state machine.
"""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from . import audit, coverage, observations
from .database import new_id, now_iso

SCHEMA_ID = "kyh-fleet-rollup/1"
MAX_SKEW = timedelta(minutes=5)
REFRESH_HOURS = 6          # re-record an unchanged result at most this often
MAX_CONTROLS, MAX_HOSTS = 64, 5000
VALID = {("PASS", "true"), ("PASS", "partial"), ("FAIL", "false")}


class FleetError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _parse(ts):
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ administration
def register_collector(conn, name, dashboard_url, actor):
    cid = new_id("COL")
    secret = secrets.token_hex(32)
    conn.execute("INSERT INTO collectors (collector_id,name,secret,dashboard_url,created_at) "
                 "VALUES (?,?,?,?,?)", (cid, name, secret, dashboard_url, now_iso()))
    audit.log(conn, actor, "COLLECTOR_REGISTERED", "COLLECTOR", cid,
              new_value=dict(name=name, dashboard_url=dashboard_url))
    return dict(collector_id=cid, secret=secret,
                note="Store the secret in the collector (kyh_collector link-platform). It is shown once.")


def link_company(conn, collector_id, company_id, collector_company_id, actor):
    if not conn.execute("SELECT 1 FROM collectors WHERE collector_id=?", (collector_id,)).fetchone():
        raise FleetError("UNKNOWN_COLLECTOR", "No such collector", 404)
    if not conn.execute("SELECT 1 FROM companies WHERE company_id=?", (company_id,)).fetchone():
        raise FleetError("UNKNOWN_COMPANY", "No such company", 404)
    conn.execute("INSERT OR REPLACE INTO collector_links VALUES (?,?,?,?)",
                 (collector_id, company_id, str(collector_company_id)[:80], now_iso()))
    audit.log(conn, actor, "COLLECTOR_LINKED", "COMPANY", company_id,
              new_value=dict(collector_id=collector_id, collector_company_id=collector_company_id))
    return dict(ok=True)


def list_collectors(conn):
    out = []
    for c in conn.execute("SELECT collector_id,name,dashboard_url,last_seq,last_seen,created_at "
                          "FROM collectors ORDER BY created_at").fetchall():
        d = dict(c)
        d["links"] = [dict(r) for r in conn.execute(
            "SELECT l.company_id, l.collector_company_id, co.name FROM collector_links l "
            "JOIN companies co ON co.company_id=l.company_id WHERE l.collector_id=?",
            (c["collector_id"],)).fetchall()]
        out.append(d)
    return out


# ------------------------------------------------------------------ authentication
def authenticate(conn, collector_id, signature, raw):
    row = conn.execute("SELECT * FROM collectors WHERE collector_id=?", (collector_id or "",)).fetchone()
    if row is None:
        raise FleetError("UNKNOWN_COLLECTOR", "Collector not registered", 401)
    expected = "v1=" + hmac.new(bytes.fromhex(row["secret"]), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        audit.log(conn, f"collector:{collector_id}", "COLLECTOR_ROLLUP_REJECTED", "COLLECTOR",
                  collector_id, new_value={"reason": "bad signature"})
        raise FleetError("BAD_SIGNATURE", "Signature does not match body", 401)
    return dict(row)


# ------------------------------------------------------------------ ingestion
def ingest_rollup(conn, collector, raw, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise FleetError("INVALID_JSON", "Body must be JSON")
    if not isinstance(body, dict) or body.get("schema") != SCHEMA_ID:
        raise FleetError("SCHEMA", f"schema must be {SCHEMA_ID}")
    if body.get("collector_id") != collector["collector_id"]:
        raise FleetError("COLLECTOR_MISMATCH", "collector_id in body differs from header", 403)
    seq = body.get("seq")
    if not isinstance(seq, int) or seq <= collector["last_seq"]:
        audit.log(conn, f"collector:{collector['collector_id']}", "COLLECTOR_ROLLUP_REJECTED",
                  "COLLECTOR", collector["collector_id"],
                  new_value={"reason": f"replayed sequence {seq} <= {collector['last_seq']}"})
        raise FleetError("REPLAY", f"Sequence {seq} already received", 409)
    try:
        sent = _parse(body["sent_at"])
        evaluated = _parse(body.get("evaluated_at") or body["sent_at"])
    except (KeyError, ValueError):
        raise FleetError("BAD_TIMESTAMP", "sent_at missing or invalid")
    if abs(now - sent) > MAX_SKEW:
        raise FleetError("STALE_OR_FUTURE", "sent_at is more than 5 minutes from platform time")

    company_id = (body.get("company") or {}).get("platform_company_id")
    link = conn.execute("SELECT * FROM collector_links WHERE collector_id=? AND company_id=?",
                        (collector["collector_id"], company_id)).fetchone()
    if link is None:
        raise FleetError("NOT_LINKED", "This collector is not linked to that company", 403)

    controls = body.get("controls") or []
    hosts = (body.get("fleet") or {}).get("hosts") or []
    if not isinstance(controls, list) or len(controls) > MAX_CONTROLS or len(hosts) > MAX_HOSTS:
        raise FleetError("TOO_MANY_ITEMS", "controls/hosts list too long")
    for c in controls:
        if not isinstance(c, dict) or (c.get("status"), c.get("value")) not in VALID:
            raise FleetError("INVALID_CONTROL_VALUE", "each control needs status PASS/FAIL and value true/partial/false")
        if not conn.execute("SELECT 1 FROM controls WHERE control_id=?", (c.get("platform_control_id"),)).fetchone():
            raise FleetError("UNKNOWN_CONTROL", f"Unknown control {c.get('platform_control_id')}")

    rollup_id = new_id("ROL")
    conn.execute("INSERT INTO collector_rollups VALUES (?,?,?,?,?,?)",
                 (rollup_id, collector["collector_id"], company_id, seq, now_iso(), raw.decode("utf-8")))
    conn.execute("UPDATE collectors SET last_seq=?, last_seen=? WHERE collector_id=?",
                 (seq, now_iso(), collector["collector_id"]))

    recorded, unchanged = [], []
    for c in controls:
        ctrl = c["platform_control_id"]
        counts = f"{c.get('passing', '?')}/{c.get('observed', '?')} hosts pass"
        prev = conn.execute("""SELECT value, observed_at, source_locator FROM observations
                               WHERE company_id=? AND control_id=? AND source_type='AGENT_FLEET'
                               ORDER BY observed_at DESC, rowid DESC LIMIT 1""", (company_id, ctrl)).fetchone()
        if prev and prev["value"] == c["value"] and (prev["source_locator"] or "").endswith(counts) and \
                evaluated - _parse(prev["observed_at"]) < timedelta(hours=REFRESH_HOURS):
            unchanged.append(ctrl)
            continue
        failing = ", ".join(h.get("host", "?") for h in (c.get("failing_hosts") or [])[:10])
        sources = ", ".join(s.get("control", "?") for s in c.get("sources") or [])
        observations.record_observation(
            conn, company_id=company_id, control_id=ctrl, value=c["value"], source_type="AGENT_FLEET",
            source_id=rollup_id,
            source_locator=f"{collector['name']} roll-up #{seq} · {sources} · {counts}",
            evidence_strength="TECHNICALLY_OBSERVED", observed_at=evaluated.isoformat(timespec="microseconds"),
            notes=(str(c.get("reason", ""))[:300] + (f" Failing: {failing}" if failing else "")),
            actor=f"collector:{collector['collector_id']}")
        recorded.append(ctrl)

    snapshot = dict(collector_id=collector["collector_id"], collector_name=collector["name"],
                    dashboard_url=collector["dashboard_url"], seq=seq, rollup_id=rollup_id,
                    evaluated_at=body.get("evaluated_at"), received_at=now_iso(),
                    collector_company_id=link["collector_company_id"],
                    company=body.get("company"), fleet=body.get("fleet") or {},
                    controls=controls, coverage=body.get("coverage"),
                    unmapped=body.get("unmapped") or [])
    conn.execute("INSERT OR REPLACE INTO fleet_snapshots VALUES (?,?,?,?,?)",
                 (company_id, collector["collector_id"], rollup_id, now_iso(), json.dumps(snapshot)))
    audit.log(conn, f"collector:{collector['collector_id']}", "COLLECTOR_ROLLUP_RECEIVED",
              "COMPANY", company_id, new_value=dict(rollup_id=rollup_id, seq=seq, recorded=recorded,
                                                    unchanged=unchanged))

    # Post-bind: warranty evaluation ONLY. Pre-bind: observations wait for the next quote.
    pol = conn.execute("SELECT * FROM policies WHERE company_id=?", (company_id,)).fetchone()
    warranties = []
    if pol and pol["status"] == "BOUND":
        warranties = coverage.evaluate_policy(conn, pol["policy_id"], company_id,
                                              actor=f"collector:{collector['collector_id']}")
    return dict(rollup_id=rollup_id, seq=seq, observations_recorded=recorded, unchanged=unchanged,
                repricing_performed=False,
                policy=dict(policy_id=pol["policy_id"], status=pol["status"], bound_at=pol["bound_at"],
                            bound_premium=pol["bound_premium"]) if pol else None,
                warranties=[{k: w[k] for k in ("control_id", "control_name", "state", "breach_detected_at",
                                                "grace_expires_at", "grace_period_days")}
                            | {"consequence": w["coverage_consequence"]["text"]} for w in warranties])


def latest_snapshot(conn, company_id):
    row = conn.execute("SELECT * FROM fleet_snapshots WHERE company_id=?", (company_id,)).fetchone()
    return json.loads(row["snapshot_json"]) if row else None
