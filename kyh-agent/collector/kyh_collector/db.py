"""SQLite storage. Reports and observations are append-only: corrections arrive as new rows."""

from __future__ import annotations

import sqlite3

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, sector TEXT, declared_endpoints INTEGER NOT NULL DEFAULT 0,
    demo_mode INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enrollment_tokens (
    token_hash TEXT PRIMARY KEY, company_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    max_uses INTEGER NOT NULL, uses INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, hostname TEXT, platform TEXT, os TEXT,
    secret TEXT NOT NULL, enrolled_at TEXT NOT NULL, last_seq INTEGER NOT NULL DEFAULT 0, last_seen TEXT,
    last_full_at TEXT, agent_version TEXT, build_hash TEXT, build_trusted INTEGER NOT NULL DEFAULT 0,
    policy_hash TEXT, policy_trusted INTEGER NOT NULL DEFAULT 0, last_simulated INTEGER NOT NULL DEFAULT 0,
    queue_depth INTEGER, retired INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY, agent_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL,
    created_at TEXT NOT NULL, received_at TEXT NOT NULL, body_sha256 TEXT NOT NULL, body BLOB NOT NULL,
    simulated INTEGER NOT NULL, evidence_strength TEXT NOT NULL, UNIQUE(agent_id, seq));
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY, report_id INTEGER NOT NULL, agent_id TEXT NOT NULL, company_id TEXT NOT NULL,
    check_id TEXT NOT NULL, control TEXT NOT NULL, tier TEXT NOT NULL, status TEXT NOT NULL, assurance TEXT,
    summary TEXT, evidence TEXT, method TEXT, observed_at TEXT NOT NULL, evidence_strength TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS results_current (
    agent_id TEXT NOT NULL, check_id TEXT NOT NULL, control TEXT NOT NULL, tier TEXT NOT NULL,
    status TEXT NOT NULL, assurance TEXT, summary TEXT, evidence TEXT, method TEXT, observed_at TEXT NOT NULL,
    evidence_strength TEXT NOT NULL, report_id INTEGER NOT NULL, PRIMARY KEY (agent_id, check_id));
CREATE TABLE IF NOT EXISTS policies (
    company_id TEXT PRIMARY KEY, status TEXT NOT NULL, model_id TEXT, bound_premium_inr INTEGER,
    bound_at TEXT);
CREATE TABLE IF NOT EXISTS warranties (
    company_id TEXT NOT NULL, control TEXT NOT NULL, state TEXT NOT NULL, since TEXT NOT NULL,
    breach_detected_at TEXT, grace_expires_at TEXT, remediated_at TEXT, last_observed TEXT, last_reason TEXT,
    PRIMARY KEY (company_id, control));
CREATE TABLE IF NOT EXISTS warranty_events (
    id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, control TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
    at TEXT NOT NULL, reason TEXT, consequence TEXT);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, entity TEXT,
    detail TEXT);
CREATE TABLE IF NOT EXISTS approved_builds (hash TEXT PRIMARY KEY, label TEXT, added_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approved_policies (hash TEXT PRIMARY KEY, label TEXT, added_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_tokens (token_hash TEXT PRIMARY KEY, created_at TEXT NOT NULL);
-- Linked mode: the KYH platform (Part 1) owns warranties; we push fleet roll-ups to it.
CREATE TABLE IF NOT EXISTS platform_state (
    company_id TEXT PRIMARY KEY, last_attempt_at TEXT, last_push_at TEXT, last_ok INTEGER,
    last_http INTEGER, last_error TEXT, last_hash TEXT, last_seq INTEGER, sent_json TEXT,
    response_json TEXT);
CREATE TABLE IF NOT EXISTS platform_meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_obs_agent ON observations(agent_id, check_id);
CREATE INDEX IF NOT EXISTS ix_events_company ON warranty_events(company_id, at);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(path: str) -> None:
    conn = connect(path)
    conn.executescript(SCHEMA)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(companies)").fetchall()}
    if "platform_company_id" not in cols:  # databases created before linked mode
        conn.execute("ALTER TABLE companies ADD COLUMN platform_company_id TEXT")
        conn.execute("ALTER TABLE companies ADD COLUMN platform_linked_at TEXT")
    conn.close()


def audit(conn, at: str, actor: str, action: str, entity: str = "", detail: str = "") -> None:
    conn.execute("INSERT INTO audit_log (at, actor, action, entity, detail) VALUES (?,?,?,?,?)",
                 (at, actor, action, entity, detail[:2000]))
