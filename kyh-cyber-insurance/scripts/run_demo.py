#!/usr/bin/env python3
"""Run the complete demonstration scenario (spec §32) against a running server.

Usage:  python server.py            # terminal 1
        python scripts/run_demo.py  # terminal 2

Walks Company B (mixed security) through:
  1. questionnaire  2. agent report (MFA PASS, EDR PASS, Backups FAIL)
  3. premium calculation  4. bind  5. agent reports MFA FAIL
  6. warranty breach with grace period  7. verify premium UNCHANGED
"""
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.environ.get("KYH_SERVER", "http://127.0.0.1:8000")


def call(method, path, body=None, token=None, agent_token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Auth-Token"] = token
    if agent_token:
        headers["Authorization"] = f"Bearer {agent_token}"
    req = urllib.request.Request(SERVER + path, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    with open(os.path.join(BASE, "data", "secrets.json")) as fh:
        uw = json.load(fh)["role_tokens"]["underwriter"]
    with open(os.path.join(BASE, "data", "demo_profiles.json")) as fh:
        b = json.load(fh)["B"]
    cid, pid, agent_token = b["company_id"], b["policy_id"], b["agent_token"]
    print(f"Company B: {cid}  policy: {pid}\n")

    st, pol = call("GET", f"/api/policies/{pid}", token=uw)
    if pol["policy"]["status"] == "BOUND":
        print("Policy already bound from a previous demo run. Delete data/kyh.db "
              "and restart the server to replay the scenario from scratch.")
        sys.exit(0)

    print("STAGE 1 — questionnaire was completed at seed time (DECLARED evidence).")

    print("STAGE 2 — agent connects and reports MFA=PASS, EDR=PASS, Backups=FAIL")
    st, r = call("POST", "/api/agent/report", agent_token=agent_token, body=dict(
        agent_id=b["agent_id"], hostname="kalinga-ep-01", platform="Linux",
        simulated_profile="mixed",
        checks=[dict(control_id="CTRL-MFA", status="PASS",
                     evidence="SIMULATED demo observation"),
                dict(control_id="CTRL-EDR", status="PASS",
                     evidence="SIMULATED demo observation"),
                dict(control_id="CTRL-BACKUP-TESTED", status="FAIL",
                     evidence="SIMULATED demo observation: no restore test evidence")]))
    print(f"   -> {st}: {r['observations_recorded']} observations recorded; "
          f"repricing_performed={r['repricing_performed']}\n")

    print("STAGE 3 — premium calculation")
    st, q = call("POST", "/api/quote", token=uw, body=dict(policy_id=pid))
    pm = q["posture_modifier"]
    print(f"   Base frequency        {q['sector_frequency']}")
    print(f"   Posture modifier      {pm['value']}")
    print(f"   Claims modifier       {q['claims_modifier']['value']}")
    print(f"   Exposure modifier     {q['exposure_modifier']['value']}")
    print(f"   Adjusted frequency    {q['adjusted_frequency']}")
    print(f"   Pure premium          Rs {q['pure_premium']:,.2f}")
    print(f"   Loadings              {q['loading_total']:.0%}")
    print(f"   TECHNICAL PREMIUM     Rs {q['technical_premium']:,.2f}")
    print(f"   Eligibility           {q['eligibility']['status']} — {q['eligibility']['reason']}")
    print(f"   Calculation id        {q['calculation_id']}  ({q['model_version']})\n")

    print("STAGE 4 — bind policy (snapshot persisted)")
    st, bound = call("POST", "/api/policies/bind", token=uw,
                     body=dict(policy_id=pid, calculation_id=q["calculation_id"]))
    print(f"   -> {st}: bound at Rs {bound['bound_premium']:,.2f}\n")

    print("STAGE 5 — later, the agent reports MFA=FAIL")
    st, r2 = call("POST", "/api/agent/report", agent_token=agent_token, body=dict(
        agent_id=b["agent_id"], hostname="kalinga-ep-01", platform="Linux",
        checks=[dict(control_id="CTRL-MFA", status="FAIL",
                     evidence="SIMULATED demo observation: MFA disabled on VPN gateway")]))
    print(f"   -> {st}: repricing_performed={r2['repricing_performed']}; "
          f"warranty evaluation ran: {json.dumps(r2['warranty_evaluation']['warranties'])}\n")

    print("STAGE 6 — warranty status")
    st, w = call("GET", f"/api/policies/{pid}/warranties", token=uw)
    for x in w["warranties"]:
        line = f"   {x['control_name']:<32} {x['state']:<10} grace {x['grace_period_days']}d"
        if x["grace_expires_at"]:
            line += f"  expires {x['grace_expires_at'][:19]}"
        print(line)
    mfa = [x for x in w["warranties"] if x["control_id"] == "CTRL-MFA"][0]
    print(f"   Coverage consequence (MFA): {mfa['coverage_consequence']['text']}\n")

    print("STAGE 7 — verify premium is UNCHANGED and re-pricing is refused")
    st, pol = call("GET", f"/api/policies/{pid}", token=uw)
    same = pol["policy"]["bound_premium"] == bound["bound_premium"]
    print(f"   Bound premium now: Rs {pol['policy']['bound_premium']:,.2f}  "
          f"(unchanged: {same})")
    st, refuse = call("POST", "/api/quote", token=uw, body=dict(policy_id=pid))
    print(f"   Re-quote attempt -> HTTP {st}: {refuse.get('error')}: {refuse.get('message')}")
    assert same and st == 409, "ACCEPTANCE TEST FAILED"
    print("\nACCEPTANCE TEST PASSED: warranty state changed, premium did not.")


if __name__ == "__main__":
    main()
