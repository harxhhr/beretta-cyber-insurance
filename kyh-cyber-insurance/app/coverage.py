"""Coverage engine — post-bind warranty monitoring.

State machine per (bound policy, warranty control):

    MET --control fails--> IN_GRACE --grace expires--> BREACHED
      ^                       |
      +---- REMEDIATED <------+  (control passes again during grace or breach)

Post-bind observations NEVER re-price the policy; they only drive this
state machine and its configured coverage consequences.

Prototype coverage-condition evaluation; final claim determination remains
subject to policy wording and authorized claims handling.
"""
from datetime import datetime, timedelta, timezone

from . import audit, observations
from .database import new_id, now_iso

STATES = ["MET", "IN_GRACE", "BREACHED", "REMEDIATED", "BREACH_CONFIRMED"]
COVERAGE_EVAL_LABEL = ("Prototype coverage-condition evaluation; final claim determination "
                       "remains subject to policy wording and authorized claims handling.")


def _parse(ts):
    return datetime.fromisoformat(ts)


def initialize_warranties(conn, policy_id, actor="system"):
    ts = now_iso()
    for ctrl in conn.execute("SELECT * FROM controls WHERE is_warranty=1").fetchall():
        wid = new_id("WTY")
        conn.execute("""INSERT OR IGNORE INTO warranties
            (warranty_id,policy_id,control_id,state,last_observed_at,grace_period_days,
             coverage_effect,updated_at) VALUES (?,?,?,?,?,?,?,?)""",
            (wid, policy_id, ctrl["control_id"], "MET", None,
             ctrl["grace_period_days"], ctrl["coverage_effect"], ts))
        _event(conn, wid, policy_id, ctrl["control_id"], None, "MET", ts,
               note="Warranty initialized at bind")
    # Evaluate immediately against current posture so a control that is already
    # failing at bind is tracked from day one.
    pol = conn.execute("SELECT company_id FROM policies WHERE policy_id=?",
                       (policy_id,)).fetchone()
    evaluate_policy(conn, policy_id, pol["company_id"], actor=actor)


def _event(conn, warranty_id, policy_id, control_id, frm, to, at, obs_id=None, note=None):
    conn.execute("INSERT INTO warranty_events VALUES (?,?,?,?,?,?,?,?,?)",
                 (new_id("WEV"), warranty_id, policy_id, control_id, frm, to, at,
                  obs_id, note))


def _transition(conn, w, to_state, actor, obs_id=None, note=None, extra_sql=None,
                extra_args=()):
    frm = w["state"]
    if frm == to_state:
        return False
    at = now_iso()
    sql = "UPDATE warranties SET state=?, updated_at=?" + (", " + extra_sql if extra_sql else "")
    conn.execute(sql + " WHERE warranty_id=?", (to_state, at, *extra_args, w["warranty_id"]))
    _event(conn, w["warranty_id"], w["policy_id"], w["control_id"], frm, to_state, at,
           obs_id, note)
    ev = {"IN_GRACE": "WARRANTY_BREACH_DETECTED", "BREACHED": "WARRANTY_BREACH_CONFIRMED",
          "REMEDIATED": "WARRANTY_REMEDIATED", "MET": "WARRANTY_MET"}.get(to_state,
                                                                          "WARRANTY_STATE_CHANGED")
    audit.log(conn, actor=actor, event_type=ev, entity_type="WARRANTY",
              entity_id=w["warranty_id"],
              old_value={"state": frm}, new_value={"state": to_state, "note": note,
                                                   "control_id": w["control_id"],
                                                   "policy_id": w["policy_id"]})
    return True


def evaluate_policy(conn, policy_id, company_id, actor="system"):
    """Re-evaluate every warranty against current resolved posture, and expire
    grace periods. Deterministic given the observation set and the clock."""
    posture = observations.resolve_posture(conn, company_id)
    now = datetime.now(timezone.utc)
    results = []
    for w in conn.execute("SELECT * FROM warranties WHERE policy_id=?", (policy_id,)).fetchall():
        p = posture.get(w["control_id"], {})
        status = p.get("status")
        obs_id = p.get("observation_id")
        observed_at = p.get("observed_at")
        if observed_at:
            conn.execute("UPDATE warranties SET last_observed_at=? WHERE warranty_id=?",
                         (observed_at, w["warranty_id"]))
        if status == "FAIL":
            if w["state"] in ("MET", "REMEDIATED"):
                grace_days = w["grace_period_days"]
                detected = now.isoformat(timespec="microseconds")
                expires = (now + timedelta(days=grace_days)).isoformat(timespec="microseconds")
                _transition(conn, w, "IN_GRACE", actor, obs_id,
                            note=f"Failing observation; grace period {grace_days} days",
                            extra_sql="breach_detected_at=?, grace_expires_at=?",
                            extra_args=(detected, expires))
            elif w["state"] == "IN_GRACE" and w["grace_expires_at"] \
                    and now >= _parse(w["grace_expires_at"]):
                _transition(conn, w, "BREACHED", actor, obs_id,
                            note="Grace period expired while control still failing")
        elif status in ("PASS", "PARTIAL"):
            if w["state"] in ("IN_GRACE", "BREACHED"):
                _transition(conn, w, "REMEDIATED", actor, obs_id,
                            note="Passing observation received",
                            extra_sql="breach_detected_at=NULL, grace_expires_at=NULL",
                            extra_args=())
                w2 = conn.execute("SELECT * FROM warranties WHERE warranty_id=?",
                                  (w["warranty_id"],)).fetchone()
                _transition(conn, w2, "MET", actor, obs_id, note="Warranty restored")
        # UNKNOWN: no change — absence of a report is not a breach in this prototype.
        results.append(warranty_view(conn, w["warranty_id"]))
    return results


def expire_grace_periods(conn, actor="scheduler"):
    """Lazy expiry pass (also callable on a schedule)."""
    now = datetime.now(timezone.utc)
    for w in conn.execute("SELECT * FROM warranties WHERE state='IN_GRACE'").fetchall():
        if w["grace_expires_at"] and now >= _parse(w["grace_expires_at"]):
            _transition(conn, w, "BREACHED", actor, note="Grace period expired")


def warranty_view(conn, warranty_id):
    w = conn.execute("SELECT w.*, c.name AS control_name FROM warranties w "
                     "JOIN controls c ON c.control_id=w.control_id "
                     "WHERE w.warranty_id=?", (warranty_id,)).fetchone()
    d = dict(w)
    d["coverage_consequence"] = coverage_consequence(d)
    return d


def coverage_consequence(w):
    """Illustrative policy-condition evaluation for the current state."""
    if w["state"] == "MET" or w["state"] == "REMEDIATED":
        return dict(applies=False, text="None — warranty met.", label=COVERAGE_EVAL_LABEL)
    if w["state"] == "IN_GRACE":
        return dict(applies=False,
                    text=(f"Warranty breached on {w['breach_detected_at']}. Grace period "
                          f"expires on {w['grace_expires_at']}. If the warranty remains "
                          f"breached when a covered incident occurs after grace expiry, the "
                          f"configured coverage consequence may apply: "
                          f"{w['coverage_effect'] or 'per policy wording'}."),
                    label=COVERAGE_EVAL_LABEL)
    return dict(applies=True,
                text=(f"Warranty breach confirmed. Configured coverage consequence: "
                      f"{w['coverage_effect'] or 'per policy wording'}."),
                label=COVERAGE_EVAL_LABEL)


def policy_warranties(conn, policy_id):
    expire_grace_periods(conn)
    rows = conn.execute("SELECT warranty_id FROM warranties WHERE policy_id=?",
                        (policy_id,)).fetchall()
    return [warranty_view(conn, r["warranty_id"]) for r in rows]


def policy_warranty_events(conn, policy_id, limit=200):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM warranty_events WHERE policy_id=? ORDER BY at DESC LIMIT ?",
        (policy_id, min(int(limit), 1000))).fetchall()]
