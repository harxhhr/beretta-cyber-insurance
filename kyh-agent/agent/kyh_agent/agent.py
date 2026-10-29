"""The agent loop: schedule checks, detect changes, build signed envelopes, queue, send."""

from __future__ import annotations

import hashlib
import json
import os
import platform as _platform
import random
import socket
import time
from datetime import datetime, timedelta

from . import SCHEMA_VERSION, __version__
from . import config as config_mod
from .checks.base import iso, utcnow
from .policy import canonical_json
from .runner import Runner, current_platform
from .security import build_hash, sign
from .spool import Spool
from .transport import Transport, TransportError

MAX_BODY = 900_000  # stay under the collector's 1 MB cap


def fingerprint(result: dict) -> str:
    """What counts as a 'change'. Timestamps and durations are excluded on purpose."""
    key = f"{result['status']}|{result.get('assurance')}|{result['summary']}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def os_label() -> str:
    try:
        if current_platform() == "linux":
            with open("/etc/os-release", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        return f"{_platform.system()} {_platform.release()} ({_platform.version()[:40]})"
    except OSError:
        return _platform.platform()


SCAN_REQUEST = "scan-now.json"


def request_scan(state_dir: str, controls=None) -> str:
    """Ask the running agent service to scan now (all checks, or only the named controls)."""
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, SCAN_REQUEST)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"controls": [c.upper() for c in (controls or [])], "requested_at": iso(utcnow())}, fh)
    os.replace(tmp, path)
    return path


class Agent:
    def __init__(self, cfg, policy, state_dir: str, transport=None, clock=utcnow, registry=None,
                 simulate: str | None = None, platform: str | None = None, sleep=time.sleep, rng=None):
        self.cfg = cfg
        self.policy = policy
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.clock = clock
        self.sleep = sleep
        self.rng = rng or random.Random()
        self.simulate = simulate
        self.platform = platform or current_platform()
        if simulate:
            from .simulate import registry_for
            registry = registry_for(simulate, self.platform)
        self.runner = Runner(policy, platform=self.platform, registry=registry, clock=clock,
                             salt=cfg.get("agent_id", "unenrolled"))
        self.spool = Spool(os.path.join(state_dir, "outbox.db"))
        self.transport = transport
        if self.transport is None and cfg.get("server_url"):
            self.transport = Transport(cfg["server_url"], cfg.get("ca_file"),
                                       allow_insecure_http=bool(cfg.get("allow_insecure_http")))
        self.build = build_hash()
        self.hostname = cfg.get("hostname_override") or socket.gethostname()
        self.state_path = os.path.join(state_dir, "state.json")
        self.state = self._load_state()
        self.backoff = 0
        self.started = time.monotonic()

    def close(self) -> None:
        """Release the outbox database (Windows will not delete a state dir with it open)."""
        self.spool.close()

    # ------------------------------------------------------------------ state
    def _load_state(self) -> dict:
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {"next_due": {}, "fingerprints": {}, "next_full": None, "next_heartbeat": None,
                    "last_results": {}, "last_scan_at": None}

    def _save_state(self) -> None:
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh, indent=1, sort_keys=True)
        os.replace(tmp, self.state_path)

    def _jitter(self, seconds: float) -> float:
        j = float(self.policy.defaults.get("jitter_fraction", 0.1))
        return seconds * (1 + self.rng.uniform(-j, j))

    # ------------------------------------------------------------------ envelope
    def envelope(self, kind: str, results: list, seq: int) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": kind,                                  # full | delta | heartbeat
            "agent_id": self.cfg.get("agent_id"),
            "seq": seq,
            "created_at": iso(self.clock()),
            "agent": {"version": __version__, "build_hash": self.build, "platform": self.platform,
                      "hostname": self.hostname, "os": self.cfg.get("os_override") or os_label()},
            "policy": {"id": self.policy.id, "version": self.policy.version, "hash": self.policy.hash},
            "simulated": bool(self.simulate),
            "queue_depth": self.spool.depth(),
            "results": results,
        }

    def enqueue(self, kind: str, results: list) -> int:
        seq = self.spool.next_seq()
        env = self.envelope(kind, results, seq)
        body = canonical_json(env)
        if len(body) > MAX_BODY:  # trim evidence rather than lose the verdicts
            for r in env["results"]:
                r["evidence"] = {"truncated": True}
            body = canonical_json(env)
        self.spool.put(seq, kind, env["created_at"], body)
        self._transparency(env)
        return seq

    def _transparency(self, env: dict) -> None:
        """Local, human-readable record of everything the agent sends (visible to the insured's staff)."""
        line = {"seq": env["seq"], "kind": env["kind"], "created_at": env["created_at"],
                "results": {r["check_id"]: r["status"] for r in env["results"]}}
        path = os.path.join(self.state_dir, "sent.jsonl")
        if os.path.exists(path) and os.path.getsize(path) > 5_000_000:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")

    # ------------------------------------------------------------------ sending
    def flush(self) -> dict:
        stats = {"sent": 0, "rejected": 0, "remaining": 0, "error": None}
        if not self.transport or not self.cfg.enrolled:
            stats["remaining"] = self.spool.depth()
            stats["error"] = "not enrolled"
            return stats
        for seq, kind, created_at, body in self.spool.pending(limit=200):
            headers = {"X-KYH-Agent-Id": self.cfg["agent_id"],
                       "X-KYH-Signature": sign(self.cfg["agent_secret"], body)}
            try:
                status, resp = self.transport.post("/api/v1/report", body, headers)
            except TransportError as exc:
                stats["error"] = str(exc)
                self.backoff = min(max(self.backoff * 2, 30), 900)
                break
            if status in (200, 202) or (status == 409 and resp.get("code") == "REPLAY"):
                self.spool.ack(seq)       # 409 REPLAY = the collector already has it (lost ACK)
                stats["sent"] += 1
                self.backoff = 0
            elif status in (429,) or status >= 500:
                stats["error"] = f"collector busy ({status})"
                self.backoff = min(max(self.backoff * 2, 30), 900)
                break
            else:                          # 4xx: this report will never be accepted; park it
                self.spool.dead_letter(seq, status, json.dumps(resp)[:500])
                stats["rejected"] += 1
        stats["remaining"] = self.spool.depth()
        return stats

    # ------------------------------------------------------------------ scanning
    def scan(self, check_ids=None, force_full: bool = False) -> dict:
        now = self.clock()
        due_full = force_full or self.state.get("next_full") is None or \
            now >= datetime.fromisoformat(self.state["next_full"].replace("Z", "+00:00"))
        if due_full:
            check_ids = [c["id"] for c in self.policy.checks]
        elif check_ids is None:
            check_ids = [cid for cid in self.policy.by_id if self._is_due(cid, now)]
        if not check_ids:
            return {"kind": None, "ran": 0, "sent": 0}
        results = [r.to_dict() for r in self.runner.run(check_ids)]
        changed = [r for r in results if self.state["fingerprints"].get(r["check_id"]) != fingerprint(r)]
        for r in results:
            self.state["fingerprints"][r["check_id"]] = fingerprint(r)
            self.state["last_results"][r["check_id"]] = r
            nxt = now + timedelta(seconds=self._jitter(self.policy.interval_seconds(r["check_id"])))
            self.state["next_due"][r["check_id"]] = iso(nxt)
        self.state["last_scan_at"] = iso(now)
        kind = None
        if due_full:
            kind = "full"
            self.state["next_full"] = iso(now + timedelta(seconds=self._jitter(self.cfg.full_snapshot_seconds())))
            self.enqueue("full", results)
        elif changed:
            kind = "delta"
            self.enqueue("delta", changed)
        self._save_state()
        return {"kind": kind, "ran": len(results), "sent": len(results) if kind == "full" else len(changed)}

    def _is_due(self, check_id: str, now: datetime) -> bool:
        nd = self.state["next_due"].get(check_id)
        return nd is None or now >= datetime.fromisoformat(nd.replace("Z", "+00:00"))

    def heartbeat_if_due(self) -> bool:
        now = self.clock()
        nh = self.state.get("next_heartbeat")
        if nh and now < datetime.fromisoformat(nh.replace("Z", "+00:00")):
            return False
        self.enqueue("heartbeat", [])
        self.state["next_heartbeat"] = iso(now + timedelta(seconds=self.cfg.heartbeat_seconds()))
        self._save_state()
        return True

    def take_scan_request(self):
        """Return the check ids asked for by `kyh-agent scan-now` ([] = everything), or None if no request.

        The request is a small file in the state directory, so the one running service stays the only
        process that scans and sends; nothing else touches the outbox or the sequence numbers."""
        path = os.path.join(self.state_dir, SCAN_REQUEST)
        try:
            with open(path, encoding="utf-8") as fh:
                req = json.load(fh)
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            req = {}
        try:
            os.remove(path)
        except OSError:
            pass
        wanted = {str(x).upper() for x in (req.get("controls") or [])} | {str(x) for x in (req.get("checks") or [])}
        return [c["id"] for c in self.policy.checks if c["control"].upper() in wanted or c["id"] in wanted]

    def tick(self) -> dict:
        """One iteration of the service loop."""
        req = self.take_scan_request()
        if req is None:
            out = self.scan()
        elif req:
            out = self.scan(check_ids=req)
        else:
            out = self.scan(force_full=True)
        self.heartbeat_if_due()
        out["flush"] = self.flush()
        return out

    def run_forever(self, tick_seconds: int = 30, stop=None) -> None:
        while not (stop and stop()):
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - the service must survive any single failure
                with open(os.path.join(self.state_dir, "agent-errors.log"), "a", encoding="utf-8") as fh:
                    fh.write(f"{iso(self.clock())} {type(exc).__name__}: {exc}\n")
            self.sleep(max(tick_seconds, self.backoff))


# ---------------------------------------------------------------------- enrollment
def enroll(cfg, server_url: str, token: str, ca_file: str | None, policy, allow_insecure_http=False,
           transport=None, hostname: str | None = None) -> dict:
    t = transport or Transport(server_url, ca_file, allow_insecure_http=allow_insecure_http)
    if hostname:
        cfg["hostname_override"] = hostname
    body = json.dumps({"enrollment_token": token, "hostname": hostname or socket.gethostname(),
                       "platform": current_platform(), "os": os_label(), "agent_version": __version__,
                       "build_hash": build_hash(), "policy_id": policy.id, "policy_hash": policy.hash}).encode()
    status, resp = t.post("/api/v1/enroll", body)
    if status != 201:
        raise RuntimeError(f"Enrollment refused ({status}): {resp.get('error', resp)}")
    cfg.update({"server_url": server_url, "ca_file": ca_file, "agent_id": resp["agent_id"],
                "agent_secret": resp["agent_secret"], "company_id": resp["company_id"],
                "company_name": resp.get("company_name"), "enrolled_at": iso(utcnow()),
                "allow_insecure_http": bool(allow_insecure_http)})
    config_mod.save(cfg)
    skew = None
    if resp.get("server_time"):
        server_now = datetime.fromisoformat(resp["server_time"].replace("Z", "+00:00"))
        skew = round(abs((utcnow() - server_now).total_seconds()), 1)
    return {"agent_id": resp["agent_id"], "company": resp.get("company_name"), "clock_skew_seconds": skew}
