"""SQLite persistence layer. Standard library only. All queries parameterized."""
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from . import catalogue

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _env(name, legacy, default):
    # Prefer the KYH_ variable; fall back to the legacy CYBERUW_ name.
    return os.environ.get(name) or os.environ.get(legacy) or default


DB_PATH = _env("KYH_DB", "CYBERUW_DB", os.path.join(DATA_DIR, "kyh.db"))
SECRETS_PATH = _env("KYH_SECRETS", "CYBERUW_SECRETS", os.path.join(DATA_DIR, "secrets.json"))

_local = threading.local()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def connect():
    """One connection per thread; WAL for the multi-threaded HTTP server."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL, company_id TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY, name TEXT NOT NULL, sector TEXT NOT NULL,
    annual_revenue_inr REAL, employee_count INTEGER, geography TEXT,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS controls (
    control_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
    tier INTEGER NOT NULL, is_warranty INTEGER NOT NULL,
    pricing_weight REAL NOT NULL, failure_effect REAL NOT NULL,
    unknown_effect REAL NOT NULL, expected_value TEXT NOT NULL DEFAULT 'true',
    grace_period_days INTEGER NOT NULL DEFAULT 0, coverage_effect TEXT,
    evidence_requirements TEXT, monitoring_only INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS sectors (
    sector TEXT PRIMARY KEY, base_frequency REAL NOT NULL);

CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS coverage_head_defaults (
    coverage_id TEXT PRIMARY KEY, name TEXT NOT NULL, severity_fraction REAL NOT NULL);

CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id),
    status TEXT NOT NULL DEFAULT 'DRAFT',          -- DRAFT | QUOTED | BOUND
    period_start TEXT, period_end TEXT,
    bound_at TEXT, bound_calculation_id TEXT, bound_premium REAL,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS policy_coverages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id TEXT NOT NULL REFERENCES policies(policy_id),
    coverage_id TEXT NOT NULL, name TEXT NOT NULL,
    limit_inr REAL NOT NULL, sublimit_inr REAL, deductible_inr REAL DEFAULT 0,
    severity_fraction REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE(policy_id, coverage_id));

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    control_id TEXT NOT NULL REFERENCES controls(control_id),
    value TEXT NOT NULL,                            -- 'true' | 'false' | 'partial'
    dims TEXT,                                      -- JSON {exists, current, tested}
    source_type TEXT NOT NULL, source_id TEXT,
    observed_at TEXT NOT NULL, received_at TEXT NOT NULL,
    source_locator TEXT, evidence_strength TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL DEFAULT 'ACTIVE', notes TEXT);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    document_type TEXT NOT NULL, category TEXT NOT NULL,
    filename TEXT NOT NULL, uploaded_at TEXT NOT NULL,
    assessment_status TEXT NOT NULL DEFAULT 'PENDING',
    default_evidence_strength TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    incident_date TEXT NOT NULL, incident_type TEXT NOT NULL,
    loss_amount_inr REAL, status TEXT NOT NULL, remediation TEXT,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS outside_in_signals (
    signal_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    signal_type TEXT NOT NULL, detail TEXT, severity TEXT NOT NULL DEFAULT 'ADVERSE',
    related_control_id TEXT, observed_at TEXT NOT NULL, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    token TEXT UNIQUE NOT NULL, hostname TEXT, last_seen TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS agent_reports (
    report_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    company_id TEXT NOT NULL, received_at TEXT NOT NULL,
    raw_json TEXT NOT NULL);                       -- immutable

CREATE TABLE IF NOT EXISTS calculations (
    calculation_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL, policy_id TEXT NOT NULL,
    calculated_at TEXT NOT NULL, model_version TEXT NOT NULL,
    input_snapshot TEXT NOT NULL, result_json TEXT NOT NULL,
    technical_premium REAL NOT NULL, eligibility TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS warranties (
    warranty_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES policies(policy_id),
    control_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'MET',
    last_observed_at TEXT, breach_detected_at TEXT, grace_expires_at TEXT,
    grace_period_days INTEGER NOT NULL, coverage_effect TEXT,
    updated_at TEXT NOT NULL, UNIQUE(policy_id, control_id));

CREATE TABLE IF NOT EXISTS warranty_events (
    event_id TEXT PRIMARY KEY, warranty_id TEXT NOT NULL,
    policy_id TEXT NOT NULL, control_id TEXT NOT NULL,
    from_state TEXT, to_state TEXT NOT NULL, at TEXT NOT NULL,
    trigger_observation_id TEXT, note TEXT);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, actor TEXT NOT NULL,
    event_type TEXT NOT NULL, entity_type TEXT, entity_id TEXT,
    old_value TEXT, new_value TEXT, metadata TEXT);
-- Link to the KYH live-monitoring collector (Part 2). The collector sends one signed
-- fleet roll-up per company; this platform stays the only warranty authority.
CREATE TABLE IF NOT EXISTS collectors (
    collector_id TEXT PRIMARY KEY, name TEXT NOT NULL, secret TEXT NOT NULL,
    dashboard_url TEXT, last_seq INTEGER NOT NULL DEFAULT 0, last_seen TEXT,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS collector_links (
    collector_id TEXT NOT NULL REFERENCES collectors(collector_id),
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    collector_company_id TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY (collector_id, company_id));

CREATE TABLE IF NOT EXISTS collector_rollups (
    rollup_id TEXT PRIMARY KEY, collector_id TEXT NOT NULL, company_id TEXT NOT NULL,
    seq INTEGER NOT NULL, received_at TEXT NOT NULL, raw_json TEXT NOT NULL);  -- immutable

CREATE TABLE IF NOT EXISTS fleet_snapshots (
    company_id TEXT PRIMARY KEY, collector_id TEXT NOT NULL, rollup_id TEXT NOT NULL,
    received_at TEXT NOT NULL, snapshot_json TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS ix_obs_company ON observations(company_id, control_id);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_events(timestamp);
"""


MIGRATIONS = [
    # (table, column, declaration). Additive only; old rows keep working.
    ("controls", "monitoring_only", "INTEGER NOT NULL DEFAULT 0"),      # collector link
    ("companies", "nic_code", "TEXT"),                                   # pricing V2 classification
    ("companies", "years_in_operation", "REAL"),
    ("companies", "regulated_rbi_sebi", "INTEGER NOT NULL DEFAULT 0"),
    ("claims", "material", "INTEGER"),                                   # NULL = infer from loss / type
    ("policies", "limit_total_inr", "REAL"),                             # V2 policy structure
    ("policies", "retention_inr", "REAL"),
]


def _migrate(conn):
    """Bring older databases up to date (idempotent)."""
    for table, col, decl in MIGRATIONS:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def init_db(seed=True):
    conn = connect()
    conn.executescript(SCHEMA)
    _migrate(conn)
    _seed_reference(conn)
    _ensure_secrets(conn)
    if seed and conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"] == 0:
        _seed_demo(conn)
    conn.commit()
    return conn


def _seed_reference(conn):
    for c in catalogue.ALL_CONTROLS:
        conn.execute("""INSERT OR IGNORE INTO controls
            (control_id,name,description,tier,is_warranty,pricing_weight,failure_effect,
             unknown_effect,grace_period_days,coverage_effect,evidence_requirements,
             monitoring_only)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (c["control_id"], c["name"], c["description"], c["tier"], c["is_warranty"],
             c["pricing_weight"], c["failure_effect"], c["unknown_effect"],
             c["grace_period_days"], c["coverage_effect"], c["evidence_requirements"],
             c["monitoring_only"]))
    for s, f in catalogue.SECTORS.items():
        conn.execute("INSERT OR IGNORE INTO sectors VALUES (?,?)", (s, f))
    for k, v in catalogue.DEFAULT_CONFIG.items():
        conn.execute("INSERT OR IGNORE INTO config VALUES (?,?)", (k, json.dumps(v)))
    for h in catalogue.COVERAGE_HEADS:
        conn.execute("INSERT OR IGNORE INTO coverage_head_defaults VALUES (?,?,?)",
                     (h["coverage_id"], h["name"], h["severity_fraction"]))


def _ensure_secrets(conn):
    """Role tokens live in data/secrets.json, outside source code."""
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] > 0:
        return
    tokens = {}
    for role in ("underwriter", "admin", "customer"):
        tok = secrets.token_urlsafe(24)
        tokens[role] = tok
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
                     (new_id("USR"), f"Demo {role}", role.upper(), tok, None, now_iso()))
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    with open(SECRETS_PATH, "w") as fh:
        json.dump({"role_tokens": tokens}, fh, indent=2)
    try:
        os.chmod(SECRETS_PATH, 0o600)
    except OSError:
        pass


def get_config(conn, key):
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def set_config(conn, key, value):
    conn.execute("INSERT INTO config VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (key, json.dumps(value)))


# ---------------------------------------------------------------------------
# Demonstration data — three companies with different risk profiles.
# Observations here are engine INPUTS; every premium is produced by the engine.
# ---------------------------------------------------------------------------
def _seed_demo(conn):
    from . import observations as obs_mod, audit  # local import to avoid cycles
    ts = now_iso()

    def add_company(name, sector, rev, emp, nic, years, limit_total, retention):
        cid = new_id("CO")
        conn.execute("""INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,
                        geography,created_at,nic_code,years_in_operation,regulated_rbi_sebi)
                        VALUES (?,?,?,?,?,?,?,?,?,0)""", (cid, name, sector, rev, emp, "India", ts, nic, years))
        pid = new_id("POL")
        conn.execute("""INSERT INTO policies (policy_id,company_id,status,period_start,period_end,created_at,
                        limit_total_inr,retention_inr) VALUES (?,?,?,?,?,?,?,?)""",
                     (pid, cid, "DRAFT", "2026-09-01", "2027-08-31", ts, limit_total, retention))
        for h in catalogue.COVERAGE_HEADS:
            limit = {"COV-IR": 1_000_000, "COV-BI": 1_500_000, "COV-DR": 1_000_000,
                     "COV-LEGAL": 1_000_000, "COV-TPL": 1_500_000, "COV-EXT": 2_000_000,
                     "COV-NOTIFY": 500_000, "COV-FTF": 500_000}[h["coverage_id"]]
            conn.execute("""INSERT INTO policy_coverages
                (policy_id,coverage_id,name,limit_inr,sublimit_inr,deductible_inr,severity_fraction,enabled)
                VALUES (?,?,?,?,?,?,?,1)""",
                (pid, h["coverage_id"], h["name"], limit, None, 50_000, h["severity_fraction"]))
        tok = secrets.token_urlsafe(24)
        aid = new_id("AGT")
        conn.execute("INSERT INTO agents VALUES (?,?,?,?,?,?)", (aid, cid, tok, None, None, ts))
        return cid, pid, aid, tok

    def q_obs(cid, ctrl, value, dims=None, note=None):
        obs_mod.record_observation(conn, company_id=cid, control_id=ctrl, value=value,
                                   source_type="QUESTIONNAIRE", source_id="seed-questionnaire",
                                   source_locator=f"Question {ctrl}", dims=dims, notes=note,
                                   actor="seed")

    profiles = {}
    # Company A — strong
    # NIC 2008: 86 human health, 28 machinery and equipment, 47 retail trade; the sector shown is the
    # V2 rating sector those divisions map to.
    a, ap, aa, at = add_company("Meridian Diagnostics Pvt Ltd", "Healthcare", 1_000_000_000, 850,
                                "86", 12, 50_000_000, 200_000)
    for ctrl in [c["control_id"] for c in catalogue.CONTROLS]:
        q_obs(a, ctrl, "true")
    q_obs(a, "CTRL-BACKUP-TESTED", "true", dims={"exists": True, "current": True, "tested": True})
    q_obs(a, "CTRL-IRPLAN", "true", dims={"exists": True, "current": True, "tested": True})
    # Document-backed evidence for key controls
    doc = new_id("DOC")
    conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)",
                 (doc, a, "SOC2_TYPE2", "AUDIT_ARTIFACT", "meridian-soc2-typeII.pdf", ts, "ASSESSED", "DOCUMENTED"))
    for ctrl, loc in [("CTRL-MFA", "Section CC6.1, p.34"), ("CTRL-EDR", "Section CC7.1, p.41"),
                      ("CTRL-LOGGING", "Section CC7.2, p.43")]:
        obs_mod.record_observation(conn, company_id=a, control_id=ctrl, value="true",
                                   source_type="DOCUMENT", source_id=doc, source_locator=loc,
                                   evidence_strength="DOCUMENTED", actor="seed")
    profiles["A"] = dict(company_id=a, policy_id=ap, agent_id=aa, agent_token=at)

    # Company B — mixed (backups exist but untested; weak hygiene)
    b, bp, ba, bt = add_company("Kalinga Components Ltd", "Industrials", 600_000_000, 420,
                                "28", 18, 20_000_000, 100_000)
    good = ["CTRL-MFA", "CTRL-EDR", "CTRL-PAM", "CTRL-EMAILSEC", "CTRL-VULNMGMT"]
    weak = ["CTRL-AWARENESS", "CTRL-ASSETINV", "CTRL-SECCONFIG"]
    for ctrl in good:
        q_obs(b, ctrl, "true")
    for ctrl in weak:
        q_obs(b, ctrl, "false")
    q_obs(b, "CTRL-PATCH-CRIT", "true", note="Monthly cycle; SLA informal")
    q_obs(b, "CTRL-BACKUP-TESTED", "false",
          dims={"exists": True, "current": True, "tested": False},
          note="Backups run nightly; no restore test on record")
    q_obs(b, "CTRL-IRPLAN", "true", dims={"exists": True, "current": False, "tested": False})
    q_obs(b, "CTRL-PASSPOLICY", "true")
    q_obs(b, "CTRL-LOGGING", "true")
    q_obs(b, "CTRL-SEGMENTATION", "true")
    q_obs(b, "CTRL-ENCRYPTION", "true")
    conn.execute("""INSERT INTO claims (claim_id,company_id,incident_date,incident_type,loss_amount_inr,
                    status,remediation,created_at,material) VALUES (?,?,?,?,?,?,?,?,1)""",
                 (new_id("CLM"), b, "2024-11-12", "Business email compromise",
                  1_200_000, "CLOSED", "Mail rules removed; MFA rolled out to finance", ts))
    obs_mod.record_signal(conn, b, "DMARC_MISSING", "No DMARC record on kalinga.example", "CTRL-EMAILSEC",
                          actor="seed")
    profiles["B"] = dict(company_id=b, policy_id=bp, agent_id=ba, agent_token=bt)
    # The demo "Insured customer" account belongs to Kalinga: it sees only this company, read-only.
    conn.execute("UPDATE users SET company_id=?, name='Kalinga Components (insured)' "
                 "WHERE role='CUSTOMER' AND company_id IS NULL", (b,))

    # Company C — weak
    c, cp, ca, ct = add_company("Sundar Retail Ventures", "Consumer Discretionary", 250_000_000, 130,
                                "47", 6, 10_000_000, 50_000)
    for ctrl in ["CTRL-MFA", "CTRL-EDR", "CTRL-BACKUP-TESTED", "CTRL-PATCH-CRIT",
                 "CTRL-PAM", "CTRL-VULNMGMT", "CTRL-AWARENESS", "CTRL-LOGGING",
                 "CTRL-SECCONFIG", "CTRL-ENCRYPTION"]:
        q_obs(c, ctrl, "false")
    q_obs(c, "CTRL-PASSPOLICY", "true")
    q_obs(c, "CTRL-ASSETINV", "false")
    obs_mod.record_signal(conn, c, "EXPOSED_RDP", "RDP 3389 open to internet on 2 hosts", None, actor="seed")
    obs_mod.record_signal(conn, c, "TLS_WEAK", "TLS 1.0 accepted on storefront", "CTRL-SECCONFIG", actor="seed")
    profiles["C"] = dict(company_id=c, policy_id=cp, agent_id=ca, agent_token=ct)

    audit.log(conn, actor="seed", event_type="DEMO_DATA_SEEDED", entity_type="SYSTEM",
              entity_id="seed", metadata=profiles)
    out_dir = os.path.dirname(DB_PATH)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "demo_profiles.json"), "w") as fh:
        json.dump(profiles, fh, indent=2)
