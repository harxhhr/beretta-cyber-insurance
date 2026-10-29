"""Engine B, UNDERWRITING_MODEL_V2: a frequency-severity premium model calibrated to published claims data.

    For each peril p:
      lambda_p = lambda_p,global x R_turnover_freq x R_sector_freq x F_india,p x M_controls_freq,p x M_claims
      X_p      ~ Lognormal(mean = m_p x R_turnover_sev x R_sector_sev x S_india, sigma)
      payout_p = E[ min( sum_h s_p,h x M_sev,p,h x (X_p - d)+ , L_total ) ]      (no per-cover sub-limits)
    EL        = sum_p lambda_p x payout_p
    Technical = EL x (1 + trend) / TLR
    Customer  = Technical x (1 + GST)

`price(inputs, params)` is a pure function: the same inputs and parameters always give the same result,
and the result carries every intermediate value. `calculate_premium(conn, policy_id)` collects the inputs
from the database, prices them, and stores the inputs and the parameters as the snapshot, so any V2 quote
can be reproduced later with `price(snapshot["inputs"], snapshot["params"])`.

Every number comes from pricing_v2_params.json, where each one carries its source, locator and tag.
"""
import copy
import json
import math
import os
from datetime import datetime, timezone
from functools import lru_cache
from statistics import NormalDist

from . import audit, observations
from .database import get_config, new_id, now_iso

MODEL_VERSION = "UNDERWRITING_MODEL_V2"
PERILS = ["RANSOMWARE", "BEC", "FTF", "MISC_FIRST_PARTY", "THIRD_PARTY"]
STAGES = ["CREDENTIAL", "WEAKNESS", "EXECUTION"]
STATUSES = ["VERIFIED", "STATED", "NOT_WORKING", "UNKNOWN"]
PARAMS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pricing_v2_params.json")
ROUND = 2


class EngineError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def load_params():
    with open(PARAMS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def v(entry):
    """The value of a parameter entry (entries are {value, unit, source, locator, tag})."""
    return entry["value"] if isinstance(entry, dict) and "value" in entry else entry


# ================================================================ classification
def nic_to_sector(nic_code, prm):
    """NIC 2008 division (2 digits) -> rating sector. Unknown or missing -> global average."""
    try:
        div = int(str(nic_code).strip()[:2])
    except (TypeError, ValueError):
        return prm["sector"]["default_sector"], False
    for lo, hi, sector in prm["sector"]["nic_map"]["ranges"]:
        if lo <= div <= hi:
            return sector, True
    return prm["sector"]["default_sector"], False


def banded(r_usd, bands, zone):
    """Band value at turnover r_usd, with log-linear transition zones [b/zone, b*zone] at every boundary b.
    Returns (value, zone_boundary or None)."""
    values = [v(b) for b in bands]
    bounds = [b["upper_usd"] for b in bands[:-1]]
    for i, b in enumerate(bounds):
        lo_edge, hi_edge = b / zone, b * zone
        if lo_edge <= r_usd <= hi_edge:
            f_lo, f_hi = values[i], values[i + 1]
            t = math.log(r_usd / lo_edge) / math.log(zone * zone)
            return f_lo * (f_hi / f_lo) ** t, b
    for i, b in enumerate(bounds):
        if r_usd < b:
            return values[i], None
    return values[-1], None


def classify(inputs, prm):
    usd_inr = v(prm["currency"]["usd_inr"])
    r_usd = float(inputs["turnover_inr"]) / usd_inr
    zone = v(prm["turnover"]["zone_factor"])
    f_turn, f_zone = banded(r_usd, prm["turnover"]["freq_bands"], zone)
    s_turn, s_zone = banded(r_usd, prm["turnover"]["sev_bands"], zone)
    g_freq, g_sev = v(prm["global"]["claims_frequency"]), v(prm["global"]["average_loss_usd"])
    sector, matched = nic_to_sector(inputs.get("nic_code"), prm)
    sp = prm["sector"]
    if sector in sp["frequency"]:
        sec_f = v(sp["frequency"][sector]) / g_freq
    elif sector in sp["frequency_relativity_direct"]:
        sec_f = v(sp["frequency_relativity_direct"][sector])
    else:
        sec_f = 1.0
    if sector in sp["severity_usd"]:
        sec_s = v(sp["severity_usd"][sector]) / g_sev
    elif sector in sp["severity_relativity_direct"]:
        sec_s = v(sp["severity_relativity_direct"][sector])
    else:
        sec_s = 1.0
    return dict(nic_code=inputs.get("nic_code"), nic_matched=matched, sector=sector,
                turnover_inr=float(inputs["turnover_inr"]), turnover_usd=r_usd, usd_inr=usd_inr,
                turnover_frequency=f_turn, turnover_freq_relativity=f_turn / g_freq,
                turnover_severity_usd=s_turn, turnover_sev_relativity=s_turn / g_sev,
                frequency_zone=f_zone, severity_zone=s_zone,
                sector_freq_relativity=sec_f, sector_sev_relativity=sec_s)


# ================================================================ controls
def m_has_lacks(S, p):
    """Centred multipliers for a control with relative risk S and adoption p:
    p x m_has + (1 - p) x m_lacks = 1."""
    denom = p + (1 - p) * S
    return 1.0 / denom, S / denom


def control_multiplier(S, p, status, prm):
    lo, hi = v(prm["controls"]["multiplier_cap"])
    has, lacks = m_has_lacks(S, p)
    has, lacks = min(max(has, lo), hi), min(max(lacks, lo), hi)
    if status == "VERIFIED":
        return has
    if status == "STATED":
        return 1 - v(prm["controls"]["credit_x"]) * (1 - has)
    return lacks  # NOT_WORKING or UNKNOWN


def combine(mults, beta):
    """Overlapping controls: sort by |ln m| descending, ln M = sum_k beta^k ln m_k."""
    logs = sorted((math.log(m) for m in mults), key=abs, reverse=True)
    return math.exp(sum((beta ** k) * lm for k, lm in enumerate(logs)))


def evidence_status(entry, document_types, prm):
    """Map Engine A's resolved control (status + evidence strength + source) to a V2 evidence status."""
    if entry is None or entry.get("status") in (None, "UNKNOWN"):
        return "UNKNOWN"
    st = entry["status"]
    if st == "FAIL":
        return "NOT_WORKING"
    if st == "PARTIAL":
        return "STATED"
    strength = entry.get("evidence_strength")
    if strength in ("TECHNICALLY_OBSERVED", "TESTED"):
        return "VERIFIED"
    if strength == "DOCUMENTED":
        doc_type = document_types.get(entry.get("source_id") or "")
        if doc_type in v(prm["controls"]["verified_document_types"]):
            return "VERIFIED"
        return "STATED"
    return "STATED"  # DECLARED


def control_effects(statuses, prm, overrides=None):
    """Combined frequency multiplier per peril and severity multiplier per peril x head, with every
    individual control multiplier for the breakdown."""
    st = dict(statuses)
    st.update(overrides or {})
    cp = prm["controls"]
    beta = v(cp["beta"])
    floor, ceil = v(cp["combined_bounds"])
    heads = prm["heads"]["order"]
    freq, freq_detail = {}, {}
    for peril in PERILS:
        stages, detail = {}, []
        for cid, c in cp["frequency"].items():
            if peril not in c["perils"]:
                continue
            m = control_multiplier(c["S"], c["p"], st.get(cid, "UNKNOWN"), prm)
            stages.setdefault(c["stage"], []).append(m)
            detail.append(dict(control_id=cid, stage=c["stage"], status=st.get(cid, "UNKNOWN"),
                               multiplier=m, source=c["source"], tag=c["tag"]))
        per_stage = {s: combine(ms, beta) for s, ms in stages.items()}
        raw = math.prod(per_stage.values()) if per_stage else 1.0
        clamped = min(max(raw, floor), ceil)
        freq[peril] = clamped
        freq_detail[peril] = dict(controls=detail, per_stage=per_stage, raw=raw, value=clamped,
                                  hit_ceiling=raw >= ceil, hit_floor=raw <= floor)
    sev, sev_detail = {}, {}
    for peril in PERILS:
        for h in heads:
            ms, detail = [], []
            for cid, c in cp["severity"].items():
                t = c["targets"]
                if t != "ALL" and h not in t.get(peril, []):
                    continue
                m = control_multiplier(c["S"], c["p"], st.get(cid, "UNKNOWN"), prm)
                ms.append(m)
                detail.append(dict(control_id=cid, status=st.get(cid, "UNKNOWN"), multiplier=m))
            raw = combine(ms, beta) if ms else 1.0
            sev[(peril, h)] = min(max(raw, floor), ceil)
            sev_detail[f"{peril}|{h}"] = dict(controls=detail, value=sev[(peril, h)])
    return freq, freq_detail, sev, sev_detail


# ================================================================ severity and payout
@lru_cache(maxsize=8)
def _z_grid(n_main, n_tail):
    """Standard-normal quantiles on a mid-point grid: n_main cells over [0, 0.99), n_tail over [0.99, 1).
    Returns (z values, probability weights)."""
    nd = NormalDist()
    zs, ws = [], []
    w = 0.99 / n_main
    zs += [nd.inv_cdf((i + 0.5) * w) for i in range(n_main)]
    ws += [w] * n_main
    w2 = 0.01 / n_tail
    zs += [nd.inv_cdf(0.99 + (i + 0.5) * w2) for i in range(n_tail)]
    ws += [w2] * n_tail
    return tuple(zs), tuple(ws)


def lev(u, mu, sigma):
    """Closed-form limited expected value E[min(X, u)] of a lognormal."""
    if u <= 0:
        return 0.0
    nd = NormalDist()
    lu = math.log(u)
    return (math.exp(mu + sigma * sigma / 2) * nd.cdf((lu - mu - sigma * sigma) / sigma)
            + u * (1 - nd.cdf((lu - mu) / sigma)))


def expected_payout(mu, sigma, retention, factors, limit_total, prm):
    """E[ min( sum_h f_h x (X - d)+, L_total ) ] by integration over the lognormal on a quantile grid.
    factors are per head (f_h = s_p,h x M_sev,p,h). There are no per-cover sub-limits: the overall limit
    is the only cap. Returns (total, per-head expected payouts)."""
    zs, ws = _z_grid(int(v(prm["severity_shape"]["quantile_points"])),
                     int(v(prm["severity_shape"]["tail_points"])))
    heads = [(h, f) for h, f in factors.items() if f > 0]
    total, per_head = 0.0, {h: 0.0 for h, _ in heads}
    for z, w in zip(zs, ws):
        x = math.exp(mu + sigma * z) - retention
        if x <= 0:
            continue
        paid = [(h, f * x) for h, f in heads]
        s = sum(p for _, p in paid)
        scale = 1.0 if s <= limit_total else limit_total / s
        total += w * min(s, limit_total)
        for h, p in paid:
            per_head[h] += w * p * scale   # the aggregate cap is shared pro rata across heads
    return total, per_head


# ================================================================ the model
def price(inputs, prm, overrides=None, with_what_if=True):
    """Price one policy. inputs: nic_code, turnover_inr, years_in_operation, regulated_rbi_sebi,
    material_incidents_3y, limit_total_inr, retention_inr, statuses {control_id: VERIFIED|STATED|...},
    evidence (optional, for display). overrides: statuses to replace
    (used by what-if). Returns the full breakdown."""
    statuses = dict(inputs["statuses"])
    statuses.update(overrides or {})
    cls = classify(inputs, prm)
    sigma = v(prm["severity_shape"]["sigma"])
    f_india = v(prm["india"]["F_india"])
    s_india = v(prm["india"]["S_india"])
    usd_inr = cls["usd_inr"]
    L_total = float(inputs["limit_total_inr"])
    d = float(inputs["retention_inr"])
    heads = prm["heads"]["order"]

    freq_m, freq_detail, sev_m, sev_detail = control_effects(statuses, prm)

    # frequency before claims history
    peril_rows = {}
    for p in PERILS:
        base = v(prm["perils"][p]["frequency"])
        lam = (base * cls["turnover_freq_relativity"] * cls["sector_freq_relativity"]
               * f_india[p] * freq_m[p])
        peril_rows[p] = dict(peril=p, base_frequency=base, turnover_relativity=cls["turnover_freq_relativity"],
                             sector_relativity=cls["sector_freq_relativity"], india_factor=f_india[p],
                             control_multiplier=freq_m[p], control_detail=freq_detail[p],
                             frequency_before_claims=lam)
    lam_firm = sum(r["frequency_before_claims"] for r in peril_rows.values())

    # claims history (credibility)
    alpha = v(prm["claims"]["alpha"])
    lookback = v(prm["claims"]["lookback_years"])
    years = inputs.get("years_in_operation")
    T = min(lookback, float(years)) if years not in (None, "") else float(lookback)
    N = int(inputs.get("material_incidents_3y") or 0)
    M_claims = (alpha + N) / (alpha + lam_firm * T)

    el = 0.0
    for p, row in peril_rows.items():
        lam = row["frequency_before_claims"] * M_claims
        mean_usd = (v(prm["perils"][p]["mean_loss_usd"]) * cls["turnover_sev_relativity"]
                    * cls["sector_sev_relativity"] * s_india)
        mean_inr = mean_usd * usd_inr
        mu = math.log(mean_inr) - sigma * sigma / 2
        shares = v(prm["heads"]["shares"][p])
        factors = {h: shares[h] * sev_m[(p, h)] for h in heads}
        payout, per_head = _cached_payout(mu, sigma, d, tuple(sorted(factors.items())), L_total, prm)
        row.update(claims_multiplier=M_claims, frequency=lam, severity_mean_inr=mean_inr,
                   severity_mean_usd=mean_usd, mu=mu, sigma=sigma,
                   severity_multipliers={h: sev_m[(p, h)] for h in heads if shares[h] > 0},
                   payout=payout, payout_per_head=per_head, expected_loss=lam * payout)
        el += lam * payout

    trend = v(prm["loadings"]["trend"])
    tlr = v(prm["loadings"]["tlr"])
    expense = v(prm["loadings"]["expense_ratio"])
    gst_rate = v(prm["loadings"]["gst"])
    technical = round(el * (1 + trend) / tlr, ROUND)
    gst = round(technical * gst_rate, ROUND)
    total = round(technical + gst, ROUND)

    gating = gate(statuses, inputs.get("gate_mode", "BLOCK"), prm)
    referral = refer(cls, freq_detail, N, inputs, prm)

    result = dict(
        model_version=MODEL_VERSION,
        classification=cls,
        policy_structure=dict(limit_total_inr=L_total, retention_inr=d),
        statuses=statuses,
        perils=[peril_rows[p] for p in PERILS],
        severity_controls=sev_detail,
        claims=dict(alpha=alpha, incidents=N, years_used=T, lambda_firm=lam_firm, multiplier=M_claims),
        expected_loss=round(el, ROUND),
        loadings=dict(trend=trend, tlr=tlr, expense_ratio=expense, margin_ratio=round(1 - tlr - expense, 4),
                      split_inr=dict(expected_loss=round(el * (1 + trend), ROUND),
                                     expenses=round(technical * expense, ROUND),
                                     profit_risk_reinsurance=round(technical * (1 - tlr - expense), ROUND))),
        technical_premium=technical, gst_rate=gst_rate, gst=gst, total_premium=total,
        eligibility=gating, referral=referral,
        assumptions=assumptions_used(prm))
    if with_what_if:
        result["what_if"] = what_if(dict(inputs, statuses=statuses), prm, statuses, technical)
    return result


_payout_cache = {}


def _cached_payout(mu, sigma, d, factors, L_total, prm):
    """Payouts depend only on severity inputs, so what-if runs that change only frequency controls reuse them."""
    key = (round(mu, 12), sigma, d, factors, L_total,
           v(prm["severity_shape"]["quantile_points"]), v(prm["severity_shape"]["tail_points"]))
    if key not in _payout_cache:
        if len(_payout_cache) > 2000:
            _payout_cache.clear()
        _payout_cache[key] = expected_payout(mu, sigma, d, dict(factors), L_total, prm)
    return _payout_cache[key]


def priced_controls(prm):
    return sorted(set(prm["controls"]["frequency"]) | set(prm["controls"]["severity"]))


def what_if(inputs, prm, statuses, technical):
    """For each priced control not already VERIFIED: the premium with that control VERIFIED, and the saving."""
    out = []
    for cid in priced_controls(prm):
        if statuses.get(cid) == "VERIFIED":
            continue
        r = price(inputs, prm, overrides={cid: "VERIFIED"}, with_what_if=False)
        out.append(dict(control_id=cid, current_status=statuses.get(cid, "UNKNOWN"),
                        premium_if_verified=r["technical_premium"],
                        saving_inr=round(technical - r["technical_premium"], ROUND)))
    out.sort(key=lambda x: x["saving_inr"], reverse=True)
    return out


# ================================================================ gating and referral
def gate(statuses, gate_mode, prm):
    g = prm["gating"]
    stated, failing = [], []
    for cid in g["warranties"]:
        s = statuses.get(cid, "UNKNOWN")
        if s == "VERIFIED" or (s == "STATED" and cid in g["stated_passes"]):
            continue
        (stated if s == "STATED" else failing).append(cid)
    if failing:
        status = "INELIGIBLE" if gate_mode == "BLOCK" else "CONDITIONALLY_ELIGIBLE"
        reason = ("Warranty not met or not evidenced: " + ", ".join(failing) +
                  (". Binding is blocked." if gate_mode == "BLOCK"
                   else ". Needs remediation or an underwriter override before bind."))
    elif stated:
        status = "CONDITIONALLY_ELIGIBLE"
        reason = "Warranty stated but not verified: " + ", ".join(stated) + ". Evidence is needed before bind."
    else:
        status, reason = "ELIGIBLE", "Every warranty is verified (MFA may be stated)."
    return dict(status=status, reason=reason, failing_warranties=failing, stated_warranties=stated,
                gate_mode=gate_mode, note="Gating never changes the price.")


def refer(cls, freq_detail, N, inputs, prm):
    r = prm["referral"]
    reasons = []
    if cls["turnover_usd"] > v(r["turnover_usd_max"]):
        reasons.append(f"Turnover above USD {v(r['turnover_usd_max']) / 1e9:.0f}B.")
    hit = [p for p, dct in freq_detail.items() if dct["hit_ceiling"]]
    if hit:
        reasons.append("Control multiplier at the 3.0 ceiling for: " + ", ".join(hit) + ".")
    if N >= v(r["incidents_min"]):
        reasons.append(f"{N} material incidents in the last 3 years.")
    if inputs.get("regulated_rbi_sebi"):
        reasons.append("RBI- or SEBI-regulated entity.")
    return dict(required=bool(reasons), reasons=reasons)


def assumptions_used(prm):
    """Every [A] parameter in the file, with its sensitivity range."""
    out = []

    def walk(node, path):
        if isinstance(node, dict):
            if node.get("tag") == "A" or node.get("p_tag") == "A":
                out.append(dict(parameter=path, value=node.get("value", {k: node.get(k) for k in ("S", "p") if k in node}),
                                locator=node.get("locator"), sensitivity=node.get("sensitivity")))
            for k, sub in node.items():
                if isinstance(sub, (dict, list)) and k not in ("value",):
                    walk(sub, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, sub in enumerate(node):
                if isinstance(sub, dict):
                    walk(sub, f"{path}[{i}]")
    walk(prm, "")
    return out


# ================================================================ database layer
def collect_inputs(conn, policy_id):
    pol = conn.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
    if not pol:
        raise EngineError("UNKNOWN_POLICY", f"No policy {policy_id}")
    co = conn.execute("SELECT * FROM companies WHERE company_id=?", (pol["company_id"],)).fetchone()
    prm = load_params()
    posture = observations.resolve_posture(conn, co["company_id"])
    src_ids = {}
    for r in conn.execute("SELECT observation_id, source_id FROM observations WHERE company_id=?",
                          (co["company_id"],)).fetchall():
        src_ids[r["observation_id"]] = r["source_id"]
    doc_types = {r["document_id"]: r["document_type"] for r in conn.execute(
        "SELECT document_id, document_type FROM documents WHERE company_id=?", (co["company_id"],)).fetchall()}
    statuses, evidence = {}, {}
    for cid in priced_controls(prm) + list(prm["gating"]["warranties"]):
        e = posture.get(cid)
        if e is not None:
            e = dict(e, source_id=src_ids.get(e.get("observation_id")))
        statuses[cid] = evidence_status(e, doc_types, prm)
        evidence[cid] = dict(name=(e or {}).get("name", cid), resolved_status=(e or {}).get("status"),
                             evidence_strength=(e or {}).get("evidence_strength"),
                             source_type=(e or {}).get("source_type"),
                             source_locator=(e or {}).get("source_locator"),
                             observation_id=(e or {}).get("observation_id"),
                             v2_status=statuses[cid])
    covs = conn.execute("SELECT * FROM policy_coverages WHERE policy_id=?", (policy_id,)).fetchall()
    limit_total = pol["limit_total_inr"] or max([c["limit_inr"] for c in covs] or [0])
    retention = pol["retention_inr"] if pol["retention_inr"] is not None else \
        max([c["deductible_inr"] or 0 for c in covs] or [0])
    years = co["years_in_operation"]
    n_material = material_incidents(conn, co["company_id"], retention)
    return pol, co, prm, posture, dict(
        nic_code=co["nic_code"], turnover_inr=co["annual_revenue_inr"] or 0,
        years_in_operation=years, regulated_rbi_sebi=bool(co["regulated_rbi_sebi"]),
        material_incidents_3y=n_material, limit_total_inr=limit_total, retention_inr=retention,
        statuses=statuses, evidence=evidence,
        gate_mode=get_config(conn, "warranty_gate_mode") or "BLOCK")


def material_incidents(conn, company_id, retention):
    """Material incidents in the last 3 years: a loss above the retention, a DPDP/CERT-In notification,
    or a ransom decision. An explicit `material` flag on the claim wins; otherwise it is inferred."""
    cutoff = datetime.now(timezone.utc).year - 3
    n = 0
    for c in conn.execute("SELECT * FROM claims WHERE company_id=?", (company_id,)).fetchall():
        try:
            if int(str(c["incident_date"])[:4]) < cutoff:
                continue
        except ValueError:
            continue
        flag = c["material"] if "material" in c.keys() else None
        if flag is not None:
            n += int(bool(flag))
        elif (c["loss_amount_inr"] or 0) > retention or "ransom" in (c["incident_type"] or "").lower():
            n += 1
    return n


def calculate_premium(conn, policy_id, actor="underwriter", persist=True):
    pol, co, prm, posture, inputs = collect_inputs(conn, policy_id)
    if pol["status"] == "BOUND":
        raise EngineError("POLICY_ALREADY_BOUND",
                          "This policy is bound. Post-bind observations evaluate warranties; "
                          "they do not re-price the policy.")
    if not inputs["limit_total_inr"]:
        raise EngineError("NO_LIMIT", "Set an overall limit for the policy before quoting.")
    r = price(inputs, prm)
    r["company"] = dict(company_id=co["company_id"], name=co["name"], nic_code=co["nic_code"],
                        annual_revenue_inr=co["annual_revenue_inr"], years_in_operation=co["years_in_operation"],
                        regulated_rbi_sebi=bool(co["regulated_rbi_sebi"]), geography=co["geography"])
    r["evidence"] = inputs["evidence"]
    r["explanation"] = explain(r)
    r["assumptions_note"] = ("Calibrated to published claims data (mostly US); several parameters are "
                             "assumptions, listed in this quote. Not a filed rate.")
    calc_id = new_id("CALC")
    r["calculation_id"], r["calculated_at"] = calc_id, now_iso()
    if persist:
        snapshot = dict(inputs=inputs, params=prm, posture=posture)
        conn.execute("INSERT INTO calculations VALUES (?,?,?,?,?,?,?,?,?)",
                     (calc_id, co["company_id"], policy_id, r["calculated_at"], MODEL_VERSION,
                      json.dumps(snapshot), json.dumps(r), r["technical_premium"], r["eligibility"]["status"]))
        conn.execute("UPDATE policies SET status='QUOTED' WHERE policy_id=? AND status='DRAFT'", (policy_id,))
        audit.log(conn, actor=actor, event_type="PREMIUM_CALCULATED", entity_type="CALCULATION",
                  entity_id=calc_id, new_value=dict(policy_id=policy_id, technical_premium=r["technical_premium"],
                                                    total_premium=r["total_premium"],
                                                    eligibility=r["eligibility"]["status"],
                                                    referral=r["referral"]["required"], model_version=MODEL_VERSION))
        audit.log(conn, actor=actor, event_type="POLICY_QUOTED", entity_type="POLICY", entity_id=policy_id,
                  new_value=dict(calculation_id=calc_id, technical_premium=r["technical_premium"]))
    return r


def reproduce(snapshot):
    """Re-run a stored V2 quote from its snapshot (inputs + parameters as they were)."""
    return price(snapshot["inputs"], snapshot["params"])


PERIL_NAMES = {"RANSOMWARE": "ransomware", "BEC": "business email compromise", "FTF": "funds transfer fraud",
               "MISC_FIRST_PARTY": "other first-party incidents", "THIRD_PARTY": "third-party liability"}


def explain(r):
    c = r["classification"]
    top = sorted(r["perils"], key=lambda p: p["expected_loss"], reverse=True)[0]
    zone = " (inside a turnover transition zone)" if c["frequency_zone"] or c["severity_zone"] else ""
    return (f"Classified as {c['sector']} with turnover USD {c['turnover_usd'] / 1e6:,.1f}M{zone}. "
            f"Expected annual loss is ₹{r['expected_loss']:,.0f}, mostly from {PERIL_NAMES[top['peril']]} "
            f"(₹{top['expected_loss']:,.0f}). Dividing by the 50% target loss ratio gives a technical premium of "
            f"₹{r['technical_premium']:,.0f}; with 18% GST the customer pays ₹{r['total_premium']:,.0f}.")


def with_params(prm, path, value):
    """Copy of the parameters with one value replaced (for sensitivity analysis). path like 'controls.beta'."""
    out = copy.deepcopy(prm)
    node = out
    keys = path.split(".")
    for k in keys[:-1]:
        node = node[k]
    if isinstance(node[keys[-1]], dict) and "value" in node[keys[-1]]:
        node[keys[-1]]["value"] = value
    else:
        node[keys[-1]] = value
    return out
