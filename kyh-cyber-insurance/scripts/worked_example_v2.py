"""Worked example for pricing V2: an IT services firm, priced step by step.

    python scripts/worked_example_v2.py

NIC 62 (computer programming and consultancy), turnover ₹150 crore, overall limit ₹5 crore, retention
₹5 lakh, 10 years in operation, 1 material incident in the last 3 years. Mixed evidence: patching,
secure configuration, logging and encryption verified by the agent; EDR not working (agent FAIL);
privileged access management unknown; everything else stated in the questionnaire.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import pricing_v2 as e  # noqa: E402

prm = e.load_params()
statuses = {c: "STATED" for c in e.priced_controls(prm)}
statuses.update({"CTRL-PATCH-CRIT": "VERIFIED", "CTRL-SECCONFIG": "VERIFIED", "CTRL-LOGGING": "VERIFIED",
                 "CTRL-ENCRYPTION": "VERIFIED", "CTRL-EDR": "NOT_WORKING", "CTRL-PAM": "UNKNOWN"})
INPUTS = dict(nic_code="62", turnover_inr=150e7, years_in_operation=10, regulated_rbi_sebi=False,
              material_incidents_3y=1, limit_total_inr=5e7, retention_inr=5e5, statuses=statuses, gate_mode="BLOCK")


def inr(x):
    return f"₹{x:,.0f}"


def main():
    r = e.price(INPUTS, prm)
    c = r["classification"]
    print("=" * 96)
    print("PRICING V2 WORKED EXAMPLE: IT services, NIC 62, turnover ₹150 crore")
    print("=" * 96)
    print(f"\n1. Classification")
    print(f"   NIC {c['nic_code']} -> {c['sector']}; turnover {inr(c['turnover_inr'])} / {c['usd_inr']} = USD {c['turnover_usd'] / 1e6:.2f}M"
          f"{'' if not (c['frequency_zone'] or c['severity_zone']) else ' (transition zone)'}")
    print(f"   turnover frequency {c['turnover_frequency']:.4%} / 1.48% = x{c['turnover_freq_relativity']:.4f}")
    print(f"   turnover severity  USD {c['turnover_severity_usd']:,.0f} / 115,000 = x{c['turnover_sev_relativity']:.4f}")
    print(f"   sector relativity  frequency x{c['sector_freq_relativity']:.4f}, severity x{c['sector_sev_relativity']:.4f}")

    print(f"\n2. Controls and evidence status")
    for cid in e.priced_controls(prm):
        print(f"   {cid:<20} {statuses[cid]}")

    print(f"\n3. Frequency per peril (before claims history)")
    for p in r["perils"]:
        stages = ", ".join(f"{s.lower()} x{m:.3f}" for s, m in p["control_detail"]["per_stage"].items())
        print(f"   {p['peril']:<17} {p['base_frequency']:.3%} x {p['turnover_relativity']:.4f} x {p['sector_relativity']:.4f}"
              f" x controls {p['control_multiplier']:.4f} [{stages}] = {p['frequency_before_claims']:.5%}")
    cl = r["claims"]
    print(f"\n4. Claims history: lambda_firm = {cl['lambda_firm']:.5%}, T = {cl['years_used']}, N = {cl['incidents']}, "
          f"alpha = {cl['alpha']} -> M = ({cl['alpha']} + {cl['incidents']}) / ({cl['alpha']} + {cl['lambda_firm']:.5f} x "
          f"{cl['years_used']}) = x{cl['multiplier']:.4f}")

    print(f"\n5. Severity and payout per peril (lognormal, sigma {r['perils'][0]['sigma']}; retention "
          f"{inr(r['policy_structure']['retention_inr'])}; overall limit {inr(r['policy_structure']['limit_total_inr'])})")
    for p in r["perils"]:
        heads = ", ".join(f"{h[4:]} {inr(v)}" for h, v in p["payout_per_head"].items() if v > 0)
        print(f"   {p['peril']:<17} lambda {p['frequency']:.5%} | mean loss {inr(p['severity_mean_inr'])} | "
              f"payout {inr(p['payout'])} | EL {inr(p['expected_loss'])}")
        print(f"   {'':<17} by head: {heads}")

    ld = r["loadings"]
    print(f"\n6. Premium")
    print(f"   expected loss                       {inr(r['expected_loss']):>12}")
    print(f"   / target loss ratio {ld['tlr']}            -> technical premium {inr(r['technical_premium'])}")
    print(f"     of which expected loss {ld['tlr']:.0%} {inr(ld['split_inr']['expected_loss'])}, expenses "
          f"{ld['expense_ratio']:.0%} {inr(ld['split_inr']['expenses'])}, margin {ld['margin_ratio']:.0%} "
          f"{inr(ld['split_inr']['profit_risk_reinsurance'])}")
    print(f"   GST {r['gst_rate']:.0%}                             {inr(r['gst']):>12}")
    print(f"   payable                             {inr(r['total_premium']):>12}")

    print(f"\n7. Eligibility: {r['eligibility']['status']} ({r['eligibility']['reason']})")
    print(f"   Referral: {'; '.join(r['referral']['reasons']) or 'none'}")
    print(f"\n8. What verification would save")
    for w in r["what_if"]:
        if w["saving_inr"] > 0:
            print(f"   verify {w['control_id']:<20} (now {w['current_status']:<11}) -> {inr(w['premium_if_verified'])}, "
                  f"save {inr(w['saving_inr'])}")
    print(f"\n9. {len(r['assumptions'])} [A] parameters used; see docs/premium_model_v2.md")
    return r


if __name__ == "__main__":
    main()
