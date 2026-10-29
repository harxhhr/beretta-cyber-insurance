"""Engine B — Risk & Premium Calculation.

Deterministic and fully explainable. No hidden adjustments: every rupee of
the technical premium can be traced back through the persisted calculation
record and its input snapshot.

    lambda_adjusted = lambda_sector x posture_mod x claims_mod x exposure_mod
    pure_premium    = lambda_adjusted x sum(severity_fraction_h x limit_h)
    technical       = pure_premium x (1 + expenses + profit + risk_margin + reinsurance)
"""
import json
from datetime import datetime, timezone

from . import audit, catalogue, observations
from .database import get_config, new_id, now_iso

ROUND = 2


class EngineError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def _cfg(conn):
    keys = ["loading_expenses", "loading_profit", "loading_risk_margin",
            "loading_reinsurance", "posture_modifier_floor", "posture_modifier_cap",
            "claims_load_per_incident", "claims_lookback_years", "claims_modifier_cap",
            "exposure_load_per_signal", "exposure_modifier_cap", "warranty_gate_mode"]
    return {k: get_config(conn, k) for k in keys}


def posture_modifier(conn, posture, cfg):
    """Transparent modifier from the 15 controls.
    PASS   -> -pricing_weight x evidence multiplier x confidence
    PARTIAL-> half of the pass credit
    FAIL   -> +failure_effect (failures count in full)
    UNKNOWN-> +unknown_effect (absence of evidence is priced, labelled as such)
    """
    contributions = []
    total = 0.0
    for ctrl in conn.execute("SELECT * FROM controls WHERE monitoring_only=0 "
                             "ORDER BY tier, control_id").fetchall():
        p = posture[ctrl["control_id"]]
        if p["status"] == "PASS":
            mult = catalogue.EVIDENCE_CREDIT_MULTIPLIER[p["evidence_strength"]]
            delta = -ctrl["pricing_weight"] * mult * (p.get("confidence") or 1.0)
            reason = f"met ({p['evidence_strength'].lower()} evidence)"
        elif p["status"] == "PARTIAL":
            mult = catalogue.EVIDENCE_CREDIT_MULTIPLIER[p["evidence_strength"]]
            delta = -0.5 * ctrl["pricing_weight"] * mult
            reason = "partially met"
        elif p["status"] == "FAIL":
            delta = ctrl["failure_effect"]
            reason = "not met"
        else:  # UNKNOWN
            delta = ctrl["unknown_effect"]
            reason = "no observation — priced as unknown"
        total += delta
        contributions.append(dict(
            control_id=ctrl["control_id"], name=ctrl["name"], tier=ctrl["tier"],
            is_warranty=bool(ctrl["is_warranty"]), status=p["status"],
            evidence_strength=p["evidence_strength"], source_type=p["source_type"],
            source_locator=p["source_locator"], observation_id=p["observation_id"],
            delta=round(delta, 4), delta_pct=f"{delta:+.1%}", reason=reason,
            conflict=p["conflict"]))
    raw = 1.0 + total
    floor, cap = cfg["posture_modifier_floor"], cfg["posture_modifier_cap"]
    clamped = min(max(raw, floor), cap)
    return dict(raw=round(raw, 4), value=round(clamped, 4), floor=floor, cap=cap,
                clamped=clamped != round(raw, 4), contributions=contributions)


def claims_modifier(conn, company_id, cfg):
    cutoff_year = datetime.now(timezone.utc).year - int(cfg["claims_lookback_years"])
    claims = [dict(r) for r in conn.execute(
        "SELECT * FROM claims WHERE company_id=? ORDER BY incident_date DESC",
        (company_id,)).fetchall()]
    in_window = [c for c in claims if int(str(c["incident_date"])[:4]) >= cutoff_year]
    raw = 1.0 + cfg["claims_load_per_incident"] * len(in_window)
    value = min(raw, cfg["claims_modifier_cap"])
    return dict(value=round(value, 4), incidents_in_window=len(in_window),
                lookback_years=cfg["claims_lookback_years"],
                load_per_incident=cfg["claims_load_per_incident"], claims=in_window)


def exposure_modifier(conn, company_id, cfg):
    signals = [dict(r) for r in conn.execute(
        "SELECT * FROM outside_in_signals WHERE company_id=? AND severity='ADVERSE'",
        (company_id,)).fetchall()]
    raw = 1.0 + cfg["exposure_load_per_signal"] * len(signals)
    value = min(raw, cfg["exposure_modifier_cap"])
    return dict(value=round(value, 4), adverse_signals=len(signals),
                load_per_signal=cfg["exposure_load_per_signal"], signals=signals)


def eligibility(posture, gate_mode):
    """Warranty gating before bind."""
    failed, unknown = [], []
    for p in posture.values():
        if not p["is_warranty"] or p.get("monitoring_only"):
            continue  # monitoring-only warranties are enforced after bind, never gate a quote
        if p["status"] == "FAIL":
            failed.append(p["name"])
        elif p["status"] in ("UNKNOWN", "PARTIAL"):
            unknown.append(p["name"])
    if failed:
        status = "INELIGIBLE" if gate_mode == "BLOCK" else "CONDITIONALLY_ELIGIBLE"
        reason = ("Warranty control(s) not met: " + ", ".join(failed) +
                  (". Binding blocked by configuration." if gate_mode == "BLOCK"
                   else ". Remediation or underwriter override required before bind."))
    elif unknown:
        status, reason = "CONDITIONALLY_ELIGIBLE", ("Warranty control(s) unverified: "
                                                    + ", ".join(unknown))
    else:
        status, reason = "ELIGIBLE", "All warranty controls met."
    return dict(status=status, reason=reason, failed_warranties=failed,
                unverified_warranties=unknown)


def calculate_premium(conn, policy_id, actor="underwriter", persist=True):
    pol = conn.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
    if not pol:
        raise EngineError("UNKNOWN_POLICY", f"No policy {policy_id}")
    if pol["status"] == "BOUND":
        # Hard architectural rule: bound policies are never re-priced.
        raise EngineError("POLICY_ALREADY_BOUND",
                          "This policy is bound. Post-bind observations evaluate "
                          "warranties; they do not re-price the policy.")
    company = conn.execute("SELECT * FROM companies WHERE company_id=?",
                           (pol["company_id"],)).fetchone()
    sector_row = conn.execute("SELECT base_frequency FROM sectors WHERE sector=?",
                              (company["sector"],)).fetchone()
    if not sector_row:
        raise EngineError("UNKNOWN_SECTOR", f"No base frequency for {company['sector']}")
    cfg = _cfg(conn)

    posture = observations.resolve_posture(conn, company["company_id"])
    pm = posture_modifier(conn, posture, cfg)
    cm = claims_modifier(conn, company["company_id"], cfg)
    em = exposure_modifier(conn, company["company_id"], cfg)

    base = sector_row["base_frequency"]
    adjusted = round(base * pm["value"] * cm["value"] * em["value"], 6)

    covs = [dict(r) for r in conn.execute(
        "SELECT * FROM policy_coverages WHERE policy_id=? AND enabled=1", (policy_id,)).fetchall()]
    if not covs:
        raise EngineError("NO_COVERAGES", "Policy has no enabled coverage heads")
    coverage_contributions = []
    expected_loss_per_incident = 0.0
    for c in covs:
        per_incident = c["severity_fraction"] * c["limit_inr"]
        expected_annual = adjusted * per_incident
        expected_loss_per_incident += per_incident
        coverage_contributions.append(dict(
            coverage_id=c["coverage_id"], name=c["name"], limit_inr=c["limit_inr"],
            sublimit_inr=c["sublimit_inr"], deductible_inr=c["deductible_inr"],
            severity_fraction=c["severity_fraction"],
            expected_loss_per_incident=round(per_incident, ROUND),
            expected_annual_loss=round(expected_annual, ROUND)))
    pure = round(adjusted * expected_loss_per_incident, ROUND)

    loadings = dict(expenses=cfg["loading_expenses"], profit=cfg["loading_profit"],
                    risk_margin=cfg["loading_risk_margin"],
                    reinsurance=cfg["loading_reinsurance"])
    loading_total = sum(loadings.values())
    technical = round(pure * (1 + loading_total), ROUND)

    elig = eligibility(posture, cfg["warranty_gate_mode"])
    posture_pct = pm["value"] - 1.0
    combined_pct = (pm["value"] * cm["value"] * em["value"]) - 1.0
    explanation = (
        f"The technical premium is ₹{technical:,.2f} because the expected annual incident "
        f"frequency for a {company['sector']} risk is {base:.2f}, and the security posture, "
        f"claims history and outside-in exposure together "
        f"{'reduced' if combined_pct < 0 else 'increased'} that frequency by "
        f"{abs(combined_pct):.1%} to {adjusted:.4f}. The configured coverage structure "
        f"produces an expected loss of ₹{expected_loss_per_incident:,.0f} per incident, "
        f"giving a pure premium of ₹{pure:,.2f}, loaded by {loading_total:.0%} for "
        f"expenses, profit, risk margin and reinsurance. Security posture alone "
        f"{'reduced' if posture_pct < 0 else 'increased'} expected frequency by "
        f"{abs(posture_pct):.1%}.")

    result = dict(
        model_version=catalogue.MODEL_VERSION,
        company=dict(company_id=company["company_id"], name=company["name"],
                     sector=company["sector"],
                     annual_revenue_inr=company["annual_revenue_inr"],
                     employee_count=company["employee_count"],
                     geography=company["geography"]),
        sector_frequency=base,
        posture_modifier=pm, claims_modifier=cm, exposure_modifier=em,
        adjusted_frequency=adjusted,
        coverage_contributions=coverage_contributions,
        expected_loss_per_incident=round(expected_loss_per_incident, ROUND),
        pure_premium=pure, loadings=loadings, loading_total=round(loading_total, 4),
        technical_premium=technical, eligibility=elig, explanation=explanation,
        assumptions_note="Demonstration assumptions — not production actuarial rates.")

    calc_id = new_id("CALC")
    result["calculation_id"] = calc_id
    result["calculated_at"] = now_iso()
    if persist:
        snapshot = dict(posture=posture, claims=cm["claims"], signals=em["signals"],
                        coverages=covs, config=cfg,
                        firmographics=result["company"])
        conn.execute("INSERT INTO calculations VALUES (?,?,?,?,?,?,?,?,?)",
                     (calc_id, company["company_id"], policy_id, result["calculated_at"],
                      catalogue.MODEL_VERSION, json.dumps(snapshot), json.dumps(result),
                      technical, elig["status"]))
        conn.execute("UPDATE policies SET status='QUOTED' WHERE policy_id=? AND status='DRAFT'",
                     (policy_id,))
        audit.log(conn, actor=actor, event_type="PREMIUM_CALCULATED",
                  entity_type="CALCULATION", entity_id=calc_id,
                  new_value=dict(policy_id=policy_id, technical_premium=technical,
                                 adjusted_frequency=adjusted,
                                 eligibility=elig["status"],
                                 model_version=catalogue.MODEL_VERSION))
        audit.log(conn, actor=actor, event_type="POLICY_QUOTED", entity_type="POLICY",
                  entity_id=policy_id, new_value=dict(calculation_id=calc_id,
                                                      technical_premium=technical))
    return result


def reproduce_v1(snapshot, result):
    """Re-run V1's arithmetic for a stored V1 calculation, from its snapshot (coverages, config, claims,
    signals) and the per-control contributions recorded in its result. Used to show that stored V1 quotes
    still reproduce now that V2 is the active model. Returns the technical premium."""
    cfg = snapshot["config"]
    total = sum(c["delta"] for c in result["posture_modifier"]["contributions"])
    pm = round(min(max(1.0 + total, cfg["posture_modifier_floor"]), cfg["posture_modifier_cap"]), 4)
    cm = round(min(1.0 + cfg["claims_load_per_incident"] * len(snapshot["claims"]), cfg["claims_modifier_cap"]), 4)
    em = round(min(1.0 + cfg["exposure_load_per_signal"] * len(snapshot["signals"]), cfg["exposure_modifier_cap"]), 4)
    adjusted = round(result["sector_frequency"] * pm * cm * em, 6)
    per_incident = sum(c["severity_fraction"] * c["limit_inr"] for c in snapshot["coverages"])
    pure = round(adjusted * per_incident, ROUND)
    loading = sum(cfg[k] for k in ("loading_expenses", "loading_profit", "loading_risk_margin",
                                   "loading_reinsurance"))
    return round(pure * (1 + loading), ROUND)


def bind_policy(conn, policy_id, calculation_id, actor="underwriter", referral_approved=False):
    pol = conn.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
    if not pol:
        raise EngineError("UNKNOWN_POLICY", f"No policy {policy_id}")
    if pol["status"] == "BOUND":
        raise EngineError("POLICY_ALREADY_BOUND", "Policy is already bound.")
    calc = conn.execute("SELECT * FROM calculations WHERE calculation_id=? AND policy_id=?",
                        (calculation_id, policy_id)).fetchone()
    if not calc:
        raise EngineError("UNKNOWN_CALCULATION",
                          "Bind requires a persisted calculation for this policy.")
    gate = get_config(conn, "warranty_gate_mode")
    if gate == "BLOCK" and calc["eligibility"] == "INELIGIBLE":
        raise EngineError("INELIGIBLE", "Warranty gating blocks binding this risk.")
    referral = (json.loads(calc["result_json"]).get("referral") or {})
    if referral.get("required") and not referral_approved:
        raise EngineError("REFERRAL_REQUIRED", "This quote is referred: " + " ".join(referral["reasons"]) +
                          " An underwriter must approve the referral to bind.")
    ts = now_iso()
    conn.execute("""UPDATE policies SET status='BOUND', bound_at=?,
                    bound_calculation_id=?, bound_premium=? WHERE policy_id=?""",
                 (ts, calculation_id, calc["technical_premium"], policy_id))
    # Create warranty records from the catalogue for post-bind monitoring.
    from . import coverage  # local import to avoid cycle
    coverage.initialize_warranties(conn, policy_id, actor=actor)
    audit.log(conn, actor=actor, event_type="POLICY_BOUND", entity_type="POLICY",
              entity_id=policy_id,
              new_value=dict(bound_premium=calc["technical_premium"], model_version=calc["model_version"],
                             calculation_id=calculation_id, bound_at=ts,
                             referral_approved=bool(referral.get("required") and referral_approved)))
    return dict(policy_id=policy_id, status="BOUND", bound_at=ts,
                bound_premium=calc["technical_premium"],
                bound_calculation_id=calculation_id)
