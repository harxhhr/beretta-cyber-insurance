"""Pricing V2 (UNDERWRITING_MODEL_V2): the model's own maths, the ten test groups of the V2 specification.

Run:  python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance
"""
import json
import math
import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
_tmp = tempfile.mkdtemp(prefix="kyh-v2-test-")
os.environ.setdefault("KYH_DB", os.path.join(_tmp, "test.db"))
os.environ.setdefault("KYH_SECRETS", os.path.join(_tmp, "secrets.json"))

from app import coverage, database, observations, pricing_v2 as e, underwriting  # noqa: E402

PRM = e.load_params()
CONTROLS = e.priced_controls(PRM)


def inputs(**kw):
    base = dict(nic_code="62", turnover_inr=150e7, years_in_operation=10, regulated_rbi_sebi=False,
                material_incidents_3y=0, limit_total_inr=5e7, retention_inr=5e5,
                statuses={c: "STATED" for c in CONTROLS})
    base.update(kw)
    return base


def premium(**kw):
    return e.price(inputs(**kw), PRM, with_what_if=False)["technical_premium"]


class Centring(unittest.TestCase):
    """1. p x m_has + (1 - p) x m_lacks = 1 for every control (uncapped)."""
    def test_every_control_is_centred(self):
        for table in ("frequency", "severity"):
            for cid, c in PRM["controls"][table].items():
                has, lacks = e.m_has_lacks(c["S"], c["p"])
                self.assertAlmostEqual(c["p"] * has + (1 - c["p"]) * lacks, 1.0, places=12, msg=cid)
                self.assertLess(has, 1.0)
                self.assertGreater(lacks, 1.0)


class Monotonicity(unittest.TestCase):
    """2. Better evidence never raises the premium; turnover, retention and limit move it the right way."""
    def test_upgrading_any_control_never_raises_the_premium(self):
        order = ["UNKNOWN", "STATED", "VERIFIED"]
        for cid in CONTROLS:
            prices = []
            for s in order:
                st = {c: "STATED" for c in CONTROLS}
                st[cid] = s
                prices.append(premium(statuses=st))
            self.assertGreaterEqual(prices[0], prices[1], cid)
            self.assertGreaterEqual(prices[1], prices[2], cid)

    def test_not_working_priced_like_unknown(self):
        a = {c: "STATED" for c in CONTROLS}
        b = dict(a)
        a["CTRL-EDR"], b["CTRL-EDR"] = "NOT_WORKING", "UNKNOWN"
        self.assertEqual(premium(statuses=a), premium(statuses=b))

    def test_higher_turnover_never_lowers_frequency(self):
        last = 0.0
        for r_usd in [x * 1e5 for x in range(5, 40000, 37)]:
            cls = e.classify(dict(turnover_inr=r_usd * e.v(PRM["currency"]["usd_inr"]), nic_code="62"), PRM)
            self.assertGreaterEqual(cls["turnover_frequency"] + 1e-15, last)
            last = cls["turnover_frequency"]

    def test_higher_retention_never_raises_the_premium(self):
        prices = [premium(retention_inr=d) for d in (0, 1e5, 5e5, 2e6, 1e7)]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_higher_limit_never_lowers_the_premium(self):
        prices = [premium(limit_total_inr=L) for L in (1e6, 1e7, 5e7, 2e8, 1e9)]
        self.assertEqual(prices, sorted(prices))


class TransitionZones(unittest.TestCase):
    """3. Continuous at every zone edge and boundary; band interiors return exact band values."""
    def freq(self, r_usd):
        return e.banded(r_usd, PRM["turnover"]["freq_bands"], e.v(PRM["turnover"]["zone_factor"]))[0]

    def test_continuous_at_edges_and_boundaries(self):
        z = e.v(PRM["turnover"]["zone_factor"])
        for b in (10e6, 25e6, 100e6):
            for x in (b / z, b, b * z):
                self.assertAlmostEqual(self.freq(x * (1 - 1e-9)), self.freq(x * (1 + 1e-9)), places=8)

    def test_band_interiors_exact(self):
        expected = [(5e6, 0.0107), (17e6, 0.0119), (50e6, 0.0399), (500e6, 0.0597)]
        for r, f in expected:
            self.assertEqual(self.freq(r), f)
        self.assertAlmostEqual(self.freq(10e6 * 1.25), 0.0119, places=12)   # zone ends on the upper band value
        self.assertAlmostEqual(self.freq(10e6 / 1.25), 0.0107, places=12)


class Payout(unittest.TestCase):
    """4. Numerical integration matches the closed-form LEV within 0.1% (one head, share 1, overall limit L)."""
    def test_matches_lev(self):
        sigma = e.v(PRM["severity_shape"]["sigma"])
        for mean, d, L in ((2e6, 5e5, 5e7), (2e7, 1e5, 2e7), (5e5, 0, 1e6), (3e6, 2e6, 1e9)):
            mu = math.log(mean) - sigma * sigma / 2
            num, _ = e.expected_payout(mu, sigma, d, {"H": 1.0}, L, PRM)
            closed = e.lev(d + L, mu, sigma) - e.lev(d, mu, sigma)
            self.assertLess(abs(num - closed) / closed, 0.001, (mean, d, L))

    def test_aggregate_limit_caps_the_payout(self):
        r = e.price(inputs(limit_total_inr=1e6), PRM, with_what_if=False)
        for p in r["perils"]:
            self.assertLessEqual(p["payout"], 1e6 + 1e-6)

    def test_no_per_cover_sub_limits(self):
        """Removed by decision: every cover pays its share above the retention, capped only by the overall limit."""
        self.assertNotIn("sublimit_pct", PRM["heads"])
        sigma = e.v(PRM["severity_shape"]["sigma"])
        mu, d, L = math.log(2e7) - sigma * sigma / 2, 1e5, 5e7
        one, _ = e.expected_payout(mu, sigma, d, {"A": 1.0}, L, PRM)
        split, per_head = e.expected_payout(mu, sigma, d, {"A": 0.5, "B": 0.5}, L, PRM)
        self.assertAlmostEqual(one, split, delta=one * 1e-9)        # splitting the loss across covers changes nothing
        self.assertAlmostEqual(per_head["A"], per_head["B"], delta=one * 1e-9)


class Reconciliation(unittest.TestCase):
    """5. The five peril frequencies sum to 1.38%; with 'other' claims they reach ~1.47% against 1.48%."""
    def test_peril_frequencies(self):
        total = sum(e.v(PRM["perils"][p]["frequency"]) for p in e.PERILS)
        self.assertAlmostEqual(total, 0.0138, places=6)
        other = e.v(PRM["global"]["other_claims_share"]) * e.v(PRM["global"]["claims_frequency"])
        self.assertAlmostEqual(total + other, 0.0147, delta=0.0002)


class ClaimsHistory(unittest.TestCase):
    """6. M_claims at lambda x T = 0.03: N = 0 -> 0.99, 1 -> 1.23, 2 -> 1.46 (alpha = 4.22, as the V2 spec gives)."""
    def test_values(self):
        a = e.v(PRM["claims"]["alpha"])
        self.assertEqual(a, 4.22)
        for n, want in ((0, 0.99), (1, 1.23), (2, 1.46)):
            self.assertAlmostEqual((a + n) / (a + 0.03), want, places=2)

    def test_engine_applies_it(self):
        r0 = e.price(inputs(material_incidents_3y=0), PRM, with_what_if=False)
        r1 = e.price(inputs(material_incidents_3y=1), PRM, with_what_if=False)
        lam_t = r0["claims"]["lambda_firm"] * r0["claims"]["years_used"]
        a = e.v(PRM["claims"]["alpha"])
        self.assertAlmostEqual(r1["claims"]["multiplier"], (a + 1) / (a + lam_t), places=12)
        self.assertGreater(r1["technical_premium"], r0["technical_premium"])

    def test_young_firm_uses_its_own_years(self):
        r = e.price(inputs(years_in_operation=1), PRM, with_what_if=False)
        self.assertEqual(r["claims"]["years_used"], 1)


class Gating(unittest.TestCase):
    """7. MFA STATED passes; EDR STATED -> conditional; EDR UNKNOWN -> ineligible under BLOCK. Gating never prices."""
    def warranties(self, **st):
        base = {c: "VERIFIED" for c in CONTROLS}
        base.update(st)
        return base

    def test_mfa_stated_passes(self):
        self.assertEqual(e.gate(self.warranties(**{"CTRL-MFA": "STATED"}), "BLOCK", PRM)["status"], "ELIGIBLE")

    def test_edr_stated_is_conditional(self):
        self.assertEqual(e.gate(self.warranties(**{"CTRL-EDR": "STATED"}), "BLOCK", PRM)["status"],
                         "CONDITIONALLY_ELIGIBLE")

    def test_edr_unknown_is_ineligible_under_block_and_conditional_under_warn(self):
        st = self.warranties(**{"CTRL-EDR": "UNKNOWN"})
        self.assertEqual(e.gate(st, "BLOCK", PRM)["status"], "INELIGIBLE")
        self.assertEqual(e.gate(st, "WARN", PRM)["status"], "CONDITIONALLY_ELIGIBLE")

    def test_gate_mode_never_changes_the_price(self):
        st = self.warranties(**{"CTRL-EDR": "UNKNOWN"})
        a = e.price(inputs(statuses=st, gate_mode="BLOCK"), PRM, with_what_if=False)
        b = e.price(inputs(statuses=st, gate_mode="WARN"), PRM, with_what_if=False)
        self.assertEqual(a["technical_premium"], b["technical_premium"])


class Referral(unittest.TestCase):
    """8. Turnover > USD 2B, a frequency multiplier at the 3.0 ceiling, N >= 2, RBI/SEBI-regulated."""
    def reasons(self, **kw):
        return e.price(inputs(**kw), PRM, with_what_if=False)["referral"]

    def test_clean_risk_not_referred(self):
        self.assertFalse(self.reasons()["required"])

    def test_triggers(self):
        usd_inr = e.v(PRM["currency"]["usd_inr"])
        self.assertTrue(self.reasons(turnover_inr=2.1e9 * usd_inr)["required"])
        self.assertTrue(self.reasons(material_incidents_3y=2)["required"])
        self.assertTrue(self.reasons(regulated_rbi_sebi=True)["required"])
        worst = self.reasons(statuses={c: "NOT_WORKING" for c in CONTROLS})
        self.assertTrue(any("3.0 ceiling" in r for r in worst["reasons"]))

    def test_missing_nic_uses_global_average_without_referral(self):
        r = e.price(inputs(nic_code=None), PRM, with_what_if=False)
        self.assertEqual(r["classification"]["sector"], "Global average")
        self.assertEqual((r["classification"]["sector_freq_relativity"], r["classification"]["sector_sev_relativity"]),
                         (1.0, 1.0))
        self.assertFalse(r["referral"]["required"])

    def test_referral_blocks_bind_without_approval(self):
        conn = database.init_db(seed=False)
        cid, pid = database.new_id("CO"), database.new_id("POL")
        conn.execute("""INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,geography,
                        created_at,nic_code,years_in_operation,regulated_rbi_sebi) VALUES (?,?,?,?,?,?,?,?,?,1)""",
                     (cid, "Regulated NBFC", "Financial Services", 5e8, 50, "India", database.now_iso(), "64", 8))
        conn.execute("""INSERT INTO policies (policy_id,company_id,status,period_start,period_end,created_at,
                        limit_total_inr,retention_inr) VALUES (?,?, 'DRAFT','2026-09-01','2027-08-31',?,?,?)""",
                     (pid, cid, database.now_iso(), 1e7, 1e5))
        for c in conn.execute("SELECT control_id FROM controls").fetchall():
            observations.record_observation(conn, cid, c["control_id"], "true", source_type="AGENT", actor="t")
        r = e.calculate_premium(conn, pid)
        self.assertTrue(r["referral"]["required"])
        with self.assertRaises(underwriting.EngineError) as cm:
            underwriting.bind_policy(conn, pid, r["calculation_id"])
        self.assertEqual(cm.exception.code, "REFERRAL_REQUIRED")
        underwriting.bind_policy(conn, pid, r["calculation_id"], referral_approved=True)


class NoRepriceAfterBind(unittest.TestCase):
    """9. V2 version of the acceptance test: monitoring after bind moves warranties, never the premium."""
    def test_post_bind_failure_moves_warranty_not_premium(self):
        conn = database.init_db(seed=False)
        cid, pid = database.new_id("CO"), database.new_id("POL")
        conn.execute("""INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,geography,
                        created_at,nic_code,years_in_operation) VALUES (?,?,?,?,?,?,?,?,?)""",
                     (cid, "Bound Co", "Healthcare", 1e9, 500, "India", database.now_iso(), "86", 10))
        conn.execute("""INSERT INTO policies (policy_id,company_id,status,period_start,period_end,created_at,
                        limit_total_inr,retention_inr) VALUES (?,?, 'DRAFT','2026-09-01','2027-08-31',?,?,?)""",
                     (pid, cid, database.now_iso(), 5e7, 2e5))
        for c in conn.execute("SELECT control_id FROM controls").fetchall():
            observations.record_observation(conn, cid, c["control_id"], "true", source_type="AGENT", actor="t")
        r = e.calculate_premium(conn, pid)
        underwriting.bind_policy(conn, pid, r["calculation_id"])
        before = conn.execute("SELECT bound_premium FROM policies WHERE policy_id=?", (pid,)).fetchone()[0]
        self.assertEqual(before, r["technical_premium"])
        observations.record_observation(conn, cid, "CTRL-EDR", "false", source_type="AGENT_FLEET", actor="t")
        coverage.evaluate_policy(conn, pid, cid)
        w = conn.execute("SELECT state FROM warranties WHERE policy_id=? AND control_id='CTRL-EDR'",
                         (pid,)).fetchone()
        self.assertEqual(w["state"], "IN_GRACE")
        after = conn.execute("SELECT bound_premium FROM policies WHERE policy_id=?", (pid,)).fetchone()[0]
        self.assertEqual(before, after)
        with self.assertRaises(e.EngineError) as cm:
            e.calculate_premium(conn, pid)
        self.assertEqual(cm.exception.code, "POLICY_ALREADY_BOUND")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM calculations WHERE policy_id=?", (pid,)).fetchone()[0], 1)


class Reproduction(unittest.TestCase):
    """10. Stored quotes reproduce: V2 from its snapshot, V1 from its snapshot and result."""
    def test_v2_snapshot_reproduces(self):
        conn = database.init_db(seed=False)
        cid, pid = database.new_id("CO"), database.new_id("POL")
        conn.execute("""INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,geography,
                        created_at,nic_code,years_in_operation) VALUES (?,?,?,?,?,?,?,?,?)""",
                     (cid, "Repro Co", "IT", 3e9, 300, "India", database.now_iso(), "62", 7))
        conn.execute("""INSERT INTO policies (policy_id,company_id,status,period_start,period_end,created_at,
                        limit_total_inr,retention_inr) VALUES (?,?, 'DRAFT','2026-09-01','2027-08-31',?,?,?)""",
                     (pid, cid, database.now_iso(), 5e7, 5e5))
        observations.record_observation(conn, cid, "CTRL-EDR", "true", source_type="AGENT", actor="t")
        r = e.calculate_premium(conn, pid)
        snap = json.loads(conn.execute("SELECT input_snapshot FROM calculations WHERE calculation_id=?",
                                       (r["calculation_id"],)).fetchone()[0])
        self.assertEqual(snap["params"]["model_version"], "UNDERWRITING_MODEL_V2")
        self.assertEqual(e.reproduce(snap)["technical_premium"], r["technical_premium"])


class WhatIf(unittest.TestCase):
    def test_savings_are_real_and_sorted(self):
        st = {c: "STATED" for c in CONTROLS}
        st["CTRL-EDR"], st["CTRL-PAM"] = "NOT_WORKING", "UNKNOWN"
        r = e.price(inputs(statuses=st), PRM)
        savings = [w["saving_inr"] for w in r["what_if"]]
        self.assertEqual(savings, sorted(savings, reverse=True))
        for w in r["what_if"]:
            self.assertGreaterEqual(w["saving_inr"], 0)
            st2 = dict(st, **{w["control_id"]: "VERIFIED"})
            self.assertEqual(premium(statuses=st2), w["premium_if_verified"])
        self.assertNotIn("VERIFIED", {w["current_status"] for w in r["what_if"]})


class Provenance(unittest.TestCase):
    def test_every_parameter_has_a_tag_and_source_and_every_assumption_a_sensitivity(self):
        def walk(node, path):
            if isinstance(node, dict):
                if "tag" in node and ("value" in node or "S" in node):
                    self.assertIn(node["tag"], {"L", "D", "A"}, path)
                    self.assertTrue(node.get("source"), path)
                    self.assertTrue(node.get("locator"), path)
                    if node["tag"] == "A" and "value" in node:
                        self.assertIn("sensitivity", node, path)
                for k, sub in node.items():
                    walk(sub, f"{path}.{k}")
            elif isinstance(node, list):
                for i, sub in enumerate(node):
                    walk(sub, f"{path}[{i}]")
        walk(PRM, "params")

    def test_breakdown_lists_assumptions(self):
        r = e.price(inputs(), PRM, with_what_if=False)
        names = {a["parameter"] for a in r["assumptions"]}
        self.assertIn("controls.beta", names)
        self.assertIn("currency.usd_inr", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
