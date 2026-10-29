"""From host results to company warranty states.

  host result  ->  host control status  ->  company control status  ->  warranty state machine

This module decides coverage conditions only. It has no access to, and no code path
into, premium calculation: the bound premium is read here for display and never written.
"""

from __future__ import annotations

import json
import math
from datetime import timedelta

from .core import STRENGTH_OBSERVED, STRENGTH_SIMULATED, iso, parse
from .settings import LABEL

ONLINE, UNVERIFIED, SILENT = "ONLINE", "UNVERIFIED", "SILENT"
NOT_OBSERVABLE = "NOT_OBSERVABLE"
SILENT_PASS = "SILENT_PASS"   # silent host whose last result passed: left out of the roll-up for a while
MET, IN_GRACE, BREACHED, REMEDIATED = "MET", "IN_GRACE", "BREACHED", "REMEDIATED"
TIER_ORDER = {"warranty": 0, "regulatory": 1, "important": 2}


# ------------------------------------------------------------------ 1. host liveness
def liveness(agent, now, s) -> dict:
    ref = agent["last_seen"] or agent["enrolled_at"]
    hours = (now - parse(ref)).total_seconds() / 3600
    state = ONLINE if hours <= s["unverified_after_hours"] else UNVERIFIED if hours <= s["silent_after_hours"] \
        else SILENT
    return {"state": state, "hours_quiet": round(hours, 1), "never_reported": agent["last_seen"] is None}


# ------------------------------------------------------------------ 2. host -> control
def usable(row, demo: bool) -> bool:
    return row["evidence_strength"] == STRENGTH_OBSERVED or (demo and row["evidence_strength"] == STRENGTH_SIMULATED)


def host_control(rows, live: dict, demo: bool, s: dict | None = None) -> tuple:
    """rows = this host's current results for one control. Returns (status, reason).

    Silence rule, judged on the host's last known result for this control:
      * last result FAIL (or no trusted result at all): FAIL. Going quiet can never hide a failure.
      * last result PASS, quiet for up to silent_pass_exclusion_days: SILENT_PASS, left out of the
        fleet ratio (staff on leave, office closed for a holiday).
      * last result PASS, quiet for longer: FAIL.
    Controls the host could never observe (e.g. MFA) are left alone.
    """
    rows = [r for r in rows if usable(r, demo)]
    statuses = {r["status"] for r in rows}
    observable = bool(statuses & {"PASS", "FAIL"})
    if live["state"] == SILENT and (observable or not rows):
        hours = live["hours_quiet"]
        if not rows:
            return "FAIL", f"host silent for {hours} h with no trusted result"
        if "FAIL" in statuses:
            return "FAIL", f"host silent for {hours} h; last result was FAIL"
        cap_days = (s or {}).get("silent_pass_exclusion_days", 0)
        if hours <= cap_days * 24:
            return SILENT_PASS, (f"host silent for {hours} h; last result was PASS, so it is left out of the "
                                 f"roll-up until it has been quiet for {cap_days} days")
        return "FAIL", f"host silent for {hours} h, more than {cap_days} days; last result was PASS"
    if not rows:
        return "NO_DATA", "no trusted result"
    statuses = [r["status"] for r in rows]
    for st in ("FAIL", "PASS", "ERROR", "NOT_SUPPORTED", "NOT_APPLICABLE"):
        if st in statuses:
            return st, next(r["summary"] for r in rows if r["status"] == st)
    return statuses[0], rows[0]["summary"]


# ------------------------------------------------------------------ 3. fleet roll-up
def company_control(control: str, host_statuses: list, s) -> dict:
    """host_statuses = [(hostname, status, reason)]. Only PASS/FAIL hosts are 'observed'."""
    observed = [h for h in host_statuses if h[1] in ("PASS", "FAIL")]
    passing = [h for h in observed if h[1] == "PASS"]
    failing = [{"host": h[0], "reason": h[2]} for h in observed if h[1] == "FAIL"]
    quiet = sum(1 for h in host_statuses if h[1] == SILENT_PASS)
    note = f"; {quiet} silent host(s) whose last result passed left out" if quiet else ""
    if not observed:
        other = sorted({h[1] for h in host_statuses}) or ["NO_DATA"]
        return {"control": control, "status": NOT_OBSERVABLE, "observed": 0, "passing": 0, "ratio": None,
                "failing_hosts": [], "silent_excluded": quiet,
                "reason": f"No host could observe this control ({', '.join(other)})"}
    ratio = len(passing) / len(observed)
    status = "PASS" if ratio >= s["warranty_pass_ratio"] else "FAIL"
    return {"control": control, "status": status, "observed": len(observed), "passing": len(passing),
            "ratio": round(ratio, 4), "failing_hosts": failing, "silent_excluded": quiet,
            "reason": f"{len(passing)}/{len(observed)} observed hosts pass ({ratio:.0%}; "
                      f"threshold {s['warranty_pass_ratio']:.0%}){note}"}


def coverage(company, lives: list, s, onboarding_until=None, now=None) -> dict:
    declared = company["declared_endpoints"]
    reporting = sum(1 for lv in lives if lv["state"] != SILENT and not lv["never_reported"])
    if onboarding_until is not None and now is not None and now < onboarding_until:
        return {"control": "MONITORING_COVERAGE", "status": NOT_OBSERVABLE, "declared": declared,
                "enrolled": len(lives), "reporting": reporting,
                "ratio": round(reporting / declared, 4) if declared else None,
                "reason": f"Agent roll-out window until {iso(onboarding_until)}; {reporting} of {declared} "
                          f"declared endpoints reporting so far"}
    if not declared:
        return {"control": "MONITORING_COVERAGE", "status": NOT_OBSERVABLE, "declared": 0, "enrolled": len(lives),
                "reporting": reporting, "ratio": None, "reason": "No declared endpoint count on the proposal"}
    ratio = reporting / declared
    need = math.ceil(declared * s["coverage_min_ratio"])
    return {"control": "MONITORING_COVERAGE", "status": "PASS" if ratio >= s["coverage_min_ratio"] else "FAIL",
            "declared": declared, "enrolled": len(lives), "reporting": reporting, "ratio": round(ratio, 4),
            "reason": f"{reporting} of {declared} declared endpoints reporting ({ratio:.0%}; need {need}, "
                      f"i.e. {s['coverage_min_ratio']:.0%})"}


# ------------------------------------------------------------------ 4. warranty state machine
def step(w: dict, observed: str, reason: str, now, s) -> tuple:
    """Return (new_state_dict, event or None). Pure: no database access.

    MET --fail--> IN_GRACE --grace expires--> BREACHED
    IN_GRACE/BREACHED --pass--> REMEDIATED --pass held N h--> MET
    REMEDIATED --fail--> IN_GRACE (new grace period)
    NOT_OBSERVABLE never moves a warranty: absence of evidence is not evidence of breach.
    """
    control, state = w["control"], w["state"]
    new = dict(w, last_observed=observed, last_reason=reason)
    grace = timedelta(days=s["grace_days"].get(control, 7))
    effect = s["coverage_effects"].get(control, "")
    failing = observed == "FAIL"
    to, why, consequence = None, reason, None

    if observed == NOT_OBSERVABLE:
        pass
    elif state == MET and failing:
        to = IN_GRACE
        new.update(breach_detected_at=iso(now), grace_expires_at=iso(now + grace), remediated_at=None)
        consequence = f"If not fixed by {iso(now + grace)}: {effect}"
    elif state == IN_GRACE and not failing:
        to = REMEDIATED
        new.update(remediated_at=iso(now))
    elif state == IN_GRACE and now >= parse(w["grace_expires_at"]):
        to, consequence = BREACHED, effect
        why = f"Grace period expired at {w['grace_expires_at']}; still failing: {reason}"
    elif state == BREACHED and not failing:
        to = REMEDIATED
        new.update(remediated_at=iso(now))
    elif state == REMEDIATED and failing:
        to = IN_GRACE
        new.update(breach_detected_at=iso(now), grace_expires_at=iso(now + grace), remediated_at=None)
        consequence = f"Regression. If not fixed by {iso(now + grace)}: {effect}"
    elif state == REMEDIATED and now - parse(w["remediated_at"]) >= timedelta(hours=s["remediation_confirm_hours"]):
        to = MET
        why = f"Fix held for {s['remediation_confirm_hours']} h"
        new.update(breach_detected_at=None, grace_expires_at=None)

    if to is None:
        return new, None
    new.update(state=to, since=iso(now))
    return new, {"control": control, "from_state": state, "to_state": to, "at": iso(now), "reason": why,
                 "consequence": consequence}


# ------------------------------------------------------------------ orchestration
def evaluate_company(conn, company_id: str, now, s, persist: bool = True) -> dict:
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    if company is None:
        return {}
    demo = bool(company["demo_mode"])
    policy = conn.execute("SELECT * FROM policies WHERE company_id=?", (company_id,)).fetchone()
    agents = conn.execute("SELECT * FROM agents WHERE company_id=? AND retired=0 ORDER BY hostname",
                          (company_id,)).fetchall()
    rows = conn.execute("SELECT rc.* FROM results_current rc JOIN agents a ON a.agent_id=rc.agent_id "
                        "WHERE a.company_id=? AND a.retired=0", (company_id,)).fetchall()
    by_agent = {}
    for r in rows:
        by_agent.setdefault(r["agent_id"], []).append(r)
    controls = {}  # control -> tier
    for r in rows:
        controls.setdefault(r["control"], r["tier"])
    for c in s["warranty_controls"]:
        if c != "MONITORING_COVERAGE":
            controls.setdefault(c, "warranty")

    hosts, lives = [], []
    per_control = {c: [] for c in controls}
    for a in agents:
        lv = liveness(a, now, s)
        lives.append(lv)
        mine = by_agent.get(a["agent_id"], [])
        cells = {}
        for c in controls:
            st, why = host_control([r for r in mine if r["control"] == c], lv, demo, s)
            cells[c] = {"status": st, "reason": why}
            per_control[c].append((a["hostname"] or a["agent_id"], st, why))
        hosts.append({"agent_id": a["agent_id"], "hostname": a["hostname"], "platform": a["platform"],
                      "os": a["os"], "last_seen": a["last_seen"], "liveness": lv, "controls": cells,
                      "build_trusted": bool(a["build_trusted"]), "policy_trusted": bool(a["policy_trusted"]),
                      "simulated": bool(a["last_simulated"]), "agent_version": a["agent_version"],
                      "queue_depth": a["queue_depth"]})

    rollup = [dict(company_control(c, per_control[c], s), tier=controls[c]) for c in controls]
    rollup.sort(key=lambda x: (TIER_ORDER.get(x["tier"], 9), x["control"]))

    linked = bool(company["platform_company_id"]) if "platform_company_id" in company.keys() else False
    platform = None
    if linked:
        # Linked mode: the Beretta platform is the only warranty authority. We read back
        # what it last told us and never run our own state machine for this company.
        ps = conn.execute("SELECT * FROM platform_state WHERE company_id=?", (company_id,)).fetchone()
        resp = json.loads(ps["response_json"]) if ps and ps["response_json"] else {}
        platform = {"platform_company_id": company["platform_company_id"], "state": dict(ps) if ps else None,
                    "policy": resp.get("policy"), "warranties": resp.get("warranties") or []}
        bound_at = (resp.get("policy") or {}).get("bound_at")
        start = bound_at or company["platform_linked_at"]
        onboarding_until = parse(start) + timedelta(days=s.get("coverage_onboarding_days", 0)) if start else None
    else:
        onboarding_until = None
        if policy and policy["bound_at"]:
            onboarding_until = parse(policy["bound_at"]) + timedelta(days=s.get("coverage_onboarding_days", 0))
    cov = coverage(company, lives, s, onboarding_until, now)
    observed = {x["control"]: (x["status"], x["reason"]) for x in rollup}
    observed["MONITORING_COVERAGE"] = (cov["status"], cov["reason"])

    warranties, changes = [], []
    if linked:
        for w in platform["warranties"]:
            warranties.append({"control": w.get("control_name") or w["control_id"],
                               "platform_control_id": w["control_id"], "state": w["state"],
                               "since": None, "grace_expires_at": w.get("grace_expires_at"),
                               "last_reason": "State held by the Beretta platform",
                               "consequence": w.get("consequence") if w["state"] in (IN_GRACE, BREACHED) else None,
                               "from_platform": True})
    elif policy and policy["status"] == "BOUND":
        for w in conn.execute("SELECT * FROM warranties WHERE company_id=? ORDER BY control", (company_id,)):
            st, why = observed.get(w["control"], (NOT_OBSERVABLE, "no evidence"))
            new, event = step(dict(w), st, why, now, s)
            if persist:
                conn.execute("UPDATE warranties SET state=?, since=?, breach_detected_at=?, grace_expires_at=?, "
                             "remediated_at=?, last_observed=?, last_reason=? WHERE company_id=? AND control=?",
                             (new["state"], new["since"], new.get("breach_detected_at"), new.get("grace_expires_at"),
                              new.get("remediated_at"), new["last_observed"], new["last_reason"], company_id,
                              w["control"]))
                if event:
                    conn.execute("INSERT INTO warranty_events (company_id, control, from_state, to_state, at, "
                                 "reason, consequence) VALUES (?,?,?,?,?,?,?)",
                                 (company_id, event["control"], event["from_state"], event["to_state"], event["at"],
                                  event["reason"], event["consequence"]))
            if event:
                changes.append(event)
            active = new["state"] in (IN_GRACE, BREACHED)
            new["consequence"] = (s["coverage_effects"].get(w["control"]) if new["state"] == BREACHED else
                                  f"Applies if still failing at {new.get('grace_expires_at')}: "
                                  f"{s['coverage_effects'].get(w['control'])}" if active else None)
            warranties.append(new)

    live_counts = {k: sum(1 for lv in lives if lv["state"] == k) for k in (ONLINE, UNVERIFIED, SILENT)}
    if linked:
        pp = platform["policy"] or {}
        policy_view = {"status": pp.get("status", "UNKNOWN"), "bound_premium_inr": pp.get("bound_premium"),
                       "bound_at": pp.get("bound_at"), "model_id": "Beretta platform (Part 1)"}
    else:
        policy_view = dict(policy) if policy else None
    return {
        "company": dict(company),
        "linked": linked,
        "platform": platform,
        "policy": policy_view,
        "premium_note": "Premium fixed at bind. Monitoring changes warranty state only; it never re-prices.",
        "coverage": cov,
        "liveness_counts": live_counts,
        "controls": rollup,
        "warranties": warranties,
        "warranty_changes": changes,
        "hosts": hosts,
        "label": LABEL,
        "evaluated_at": iso(now),
    }


def host_detail(conn, agent_id: str) -> dict | None:
    a = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    if a is None:
        return None
    res = conn.execute("SELECT * FROM results_current WHERE agent_id=? ORDER BY tier, control", (agent_id,))
    reports = conn.execute("SELECT seq, kind, created_at, received_at, evidence_strength, body_sha256 FROM reports "
                           "WHERE agent_id=? ORDER BY seq DESC LIMIT 25", (agent_id,))
    agent = {k: a[k] for k in a.keys() if k != "secret"}  # never expose the signing secret
    results = []
    for r in res:
        d = dict(r)
        d["evidence"] = json.loads(d["evidence"] or "{}")
        results.append(d)
    results.sort(key=lambda x: (TIER_ORDER.get(x["tier"], 9), x["control"]))
    return {"agent": agent, "results": results, "reports": [dict(x) for x in reports]}
