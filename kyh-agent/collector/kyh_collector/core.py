"""Enrollment, report ingestion and admin operations (transport-independent, so tests call them directly)."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from . import db as dbm

STRENGTH_OBSERVED = "TECHNICALLY_OBSERVED"
STRENGTH_SIMULATED = "SIMULATED"
STRENGTH_UNTRUSTED_BUILD = "UNTRUSTED_BUILD"
STRENGTH_UNTRUSTED_POLICY = "UNTRUSTED_POLICY"
STATUSES = {"PASS", "FAIL", "NOT_APPLICABLE", "NOT_SUPPORTED", "ERROR"}
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def sha(s) -> str:
    return hashlib.sha256(s if isinstance(s, bytes) else s.encode()).hexdigest()


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# ============================================================ admin operations
def create_admin_token(conn, now) -> str:
    token = "kyh_admin_" + secrets.token_urlsafe(24)
    conn.execute("INSERT INTO admin_tokens VALUES (?,?)", (sha(token), iso(now)))
    dbm.audit(conn, iso(now), "cli", "ADMIN_TOKEN_CREATED")
    return token  # shown once; only its hash is stored


def check_admin(conn, token: str | None) -> bool:
    if not token:
        return False
    h = sha(token)
    for row in conn.execute("SELECT token_hash FROM admin_tokens"):
        if hmac.compare_digest(row["token_hash"], h):
            return True
    return False


def add_company(conn, now, name: str, declared_endpoints: int, sector: str = "", demo: bool = False,
                company_id: str | None = None) -> str:
    cid = company_id or "co_" + uuid.uuid4().hex[:10]
    conn.execute("INSERT INTO companies (id, name, sector, declared_endpoints, demo_mode, created_at) "
                 "VALUES (?,?,?,?,?,?)",
                 (cid, name, sector, int(declared_endpoints), int(demo), iso(now)))
    conn.execute("INSERT INTO policies (company_id, status) VALUES (?, 'QUOTED')", (cid,))
    dbm.audit(conn, iso(now), "admin", "COMPANY_CREATED", cid, f"{name}; declared={declared_endpoints}; demo={demo}")
    return cid


def issue_enrollment_token(conn, now, company_id: str, max_uses: int = 50, days: int = 7) -> str:
    if not conn.execute("SELECT 1 FROM companies WHERE id=?", (company_id,)).fetchone():
        raise ApiError(404, "NO_COMPANY", "unknown company")
    token = "kyh_enr_" + secrets.token_urlsafe(18)
    conn.execute("INSERT INTO enrollment_tokens VALUES (?,?,?,?,?,0)",
                 (sha(token), company_id, iso(now), iso(now + timedelta(days=days)), int(max_uses)))
    dbm.audit(conn, iso(now), "admin", "ENROLLMENT_TOKEN_ISSUED", company_id, f"max_uses={max_uses}; days={days}")
    return token


def bind_policy(conn, now, company_id: str, premium_inr: int, settings: dict,
                model_id: str = "UNDERWRITING_MODEL_V1") -> None:
    """Records the premium that Engine B calculated at inception. Nothing in the collector ever changes it."""
    row = conn.execute("SELECT status FROM policies WHERE company_id=?", (company_id,)).fetchone()
    if row is None:
        raise ApiError(404, "NO_COMPANY", "unknown company")
    linked = conn.execute("SELECT platform_company_id FROM companies WHERE id=?", (company_id,)).fetchone()
    if linked and linked["platform_company_id"]:
        raise ApiError(409, "LINKED_TO_PLATFORM", "this company is linked to the Beretta platform, which binds "
                                                  "the policy and owns its warranties")
    if row["status"] == "BOUND":
        raise ApiError(409, "POLICY_ALREADY_BOUND", "policy already bound; the premium is fixed")
    conn.execute("UPDATE policies SET status='BOUND', model_id=?, bound_premium_inr=?, bound_at=? WHERE company_id=?",
                 (model_id, int(premium_inr), iso(now), company_id))
    for control in settings["warranty_controls"]:
        conn.execute("INSERT OR REPLACE INTO warranties (company_id, control, state, since) VALUES (?,?,'MET',?)",
                     (company_id, control, iso(now)))
        conn.execute("INSERT INTO warranty_events (company_id, control, from_state, to_state, at, reason) "
                     "VALUES (?,?,NULL,'MET',?,'Policy bound')", (company_id, control, iso(now)))
    dbm.audit(conn, iso(now), "admin", "POLICY_BOUND", company_id, f"premium_inr={premium_inr}; model={model_id}")


def approve(conn, now, table: str, h: str, label: str) -> None:
    assert table in ("approved_builds", "approved_policies")
    conn.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?,?)", (h, label, iso(now)))
    conn.execute(f"UPDATE agents SET {'build_trusted' if table == 'approved_builds' else 'policy_trusted'}=1 "
                 f"WHERE {'build_hash' if table == 'approved_builds' else 'policy_hash'}=?", (h,))
    dbm.audit(conn, iso(now), "admin", table.upper().rstrip("S") + "_ADDED", h, label)


def retire_agent(conn, now, agent_id: str, reason: str) -> None:
    row = conn.execute("SELECT company_id FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    if row is None:
        raise ApiError(404, "UNKNOWN_AGENT", "unknown agent")
    conn.execute("UPDATE agents SET retired=1 WHERE agent_id=?", (agent_id,))
    dbm.audit(conn, iso(now), "admin", "AGENT_RETIRED", agent_id, reason)


def _approved(conn, table: str, h: str) -> bool:
    return bool(h) and conn.execute(f"SELECT 1 FROM {table} WHERE hash=?", (h,)).fetchone() is not None


# ============================================================ enrollment
def enroll(conn, now, body: dict) -> dict:
    token = body.get("enrollment_token") or ""
    row = conn.execute("SELECT * FROM enrollment_tokens WHERE token_hash=?", (sha(token),)).fetchone()
    if row is None:
        dbm.audit(conn, iso(now), "anonymous", "ENROLL_REJECTED", "", "unknown token")
        raise ApiError(401, "BAD_TOKEN", "enrollment token not recognised")
    if now > parse(row["expires_at"]):
        raise ApiError(401, "TOKEN_EXPIRED", "enrollment token expired")
    if row["uses"] >= row["max_uses"]:
        raise ApiError(401, "TOKEN_EXHAUSTED", "enrollment token has no uses left")
    company = conn.execute("SELECT * FROM companies WHERE id=?", (row["company_id"],)).fetchone()
    agent_id = "ag_" + uuid.uuid4().hex[:16]
    secret = secrets.token_hex(32)
    build, pol = str(body.get("build_hash", ""))[:64], str(body.get("policy_hash", ""))[:64]
    conn.execute(
        "INSERT INTO agents (agent_id, company_id, hostname, platform, os, secret, enrolled_at, agent_version, "
        "build_hash, build_trusted, policy_hash, policy_trusted) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (agent_id, company["id"], str(body.get("hostname", ""))[:128], str(body.get("platform", ""))[:16],
         str(body.get("os", ""))[:128], secret, iso(now), str(body.get("agent_version", ""))[:32],
         build, int(_approved(conn, "approved_builds", build)), pol, int(_approved(conn, "approved_policies", pol))))
    conn.execute("UPDATE enrollment_tokens SET uses=uses+1 WHERE token_hash=?", (row["token_hash"],))
    dbm.audit(conn, iso(now), agent_id, "AGENT_ENROLLED", company["id"], f"host={body.get('hostname')}")
    return {"agent_id": agent_id, "agent_secret": secret, "company_id": company["id"],
            "company_name": company["name"], "server_time": iso(now)}


# ============================================================ ingestion
def ingest(conn, now, agent_id: str, signature: str, raw: bytes, settings: dict) -> dict:
    """Validate and store one signed report. Order of checks matters: authenticate before parsing."""
    if len(raw) > settings["max_body_bytes"]:
        raise ApiError(413, "TOO_LARGE", "report exceeds size limit")
    agent = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id or "",)).fetchone()
    if agent is None or agent["retired"]:
        raise ApiError(401, "UNKNOWN_AGENT", "agent not enrolled")
    expected = "v1=" + hmac.new(bytes.fromhex(agent["secret"]), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        dbm.audit(conn, iso(now), agent_id, "REPORT_REJECTED", agent["company_id"], "bad signature")
        raise ApiError(401, "BAD_SIGNATURE", "signature does not match report body")
    try:
        env = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "BAD_JSON", "body is not valid JSON")
    if env.get("schema_version") not in settings["supported_schema_versions"]:
        raise ApiError(400, "SCHEMA_VERSION", f"unsupported schema_version {env.get('schema_version')}")
    if env.get("agent_id") != agent_id:
        raise ApiError(400, "AGENT_MISMATCH", "envelope agent_id differs from header")
    seq = env.get("seq")
    if not isinstance(seq, int) or seq < 1:
        raise ApiError(400, "BAD_SEQ", "seq must be a positive integer")
    if seq <= agent["last_seq"]:
        dbm.audit(conn, iso(now), agent_id, "REPORT_REJECTED", agent["company_id"],
                  f"replay/out-of-order seq {seq} <= {agent['last_seq']}")
        raise ApiError(409, "REPLAY", f"sequence {seq} already received")
    try:
        created = parse(env["created_at"])
    except (KeyError, ValueError, AttributeError):
        raise ApiError(400, "BAD_TIMESTAMP", "created_at missing or invalid")
    if created > now + timedelta(minutes=settings["max_clock_skew_minutes"]):
        raise ApiError(400, "FUTURE_TIMESTAMP", "created_at is in the future beyond allowed clock skew")
    if created < now - timedelta(days=settings["max_report_age_days"]):
        raise ApiError(400, "TOO_OLD", "report older than the accepted replay window")
    kind = env.get("kind")
    if kind not in ("full", "delta", "heartbeat"):
        raise ApiError(400, "BAD_KIND", "kind must be full, delta or heartbeat")
    results = env.get("results") or []
    for r in results:
        if not isinstance(r, dict) or r.get("status") not in STATUSES or not _ID.match(str(r.get("check_id", ""))) \
                or not _ID.match(str(r.get("control", ""))):
            raise ApiError(400, "BAD_RESULT", "result entry failed validation")

    ag = env.get("agent") or {}
    build = str(ag.get("build_hash", ""))[:64]
    pol = str((env.get("policy") or {}).get("hash", ""))[:64]
    build_ok, pol_ok = _approved(conn, "approved_builds", build), _approved(conn, "approved_policies", pol)
    simulated = bool(env.get("simulated"))
    strength = (STRENGTH_SIMULATED if simulated else STRENGTH_UNTRUSTED_BUILD if not build_ok
                else STRENGTH_UNTRUSTED_POLICY if not pol_ok else STRENGTH_OBSERVED)

    cur = conn.execute(
        "INSERT INTO reports (agent_id, seq, kind, created_at, received_at, body_sha256, body, simulated, "
        "evidence_strength) VALUES (?,?,?,?,?,?,?,?,?)",
        (agent_id, seq, kind, iso(created), iso(now), sha(raw), raw, int(simulated), strength))
    report_id = cur.lastrowid
    conn.execute(
        "UPDATE agents SET last_seq=?, last_seen=?, build_hash=?, build_trusted=?, policy_hash=?, policy_trusted=?, "
        "last_simulated=?, queue_depth=?, hostname=COALESCE(?, hostname), os=COALESCE(?, os), "
        "agent_version=COALESCE(?, agent_version) WHERE agent_id=?",
        (seq, iso(now), build, int(build_ok), pol, int(pol_ok), int(simulated), env.get("queue_depth"),
         ag.get("hostname"), ag.get("os"), ag.get("version"), agent_id))
    if kind == "full":
        conn.execute("UPDATE agents SET last_full_at=? WHERE agent_id=?", (iso(now), agent_id))
    for r in results:
        observed = str(r.get("observed_at") or iso(created))
        vals = (agent_id, r["check_id"], r["control"], str(r.get("tier", "")), r["status"], r.get("assurance"),
                str(r.get("summary", ""))[:500], json.dumps(r.get("evidence", {}))[:20000],
                str(r.get("method", ""))[:200], observed, strength)
        conn.execute("INSERT INTO observations (report_id, agent_id, company_id, check_id, control, tier, status, "
                     "assurance, summary, evidence, method, observed_at, evidence_strength) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (report_id, vals[0], agent["company_id"]) + vals[1:])
        prev = conn.execute("SELECT observed_at FROM results_current WHERE agent_id=? AND check_id=?",
                            (agent_id, r["check_id"])).fetchone()
        if prev is None or parse(observed) >= parse(prev["observed_at"]):  # late-arriving old reports don't win
            conn.execute("INSERT OR REPLACE INTO results_current VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         vals + (report_id,))
    return {"accepted": True, "report_id": report_id, "seq": seq, "evidence_strength": strength,
            "company_id": agent["company_id"], "results": len(results)}
