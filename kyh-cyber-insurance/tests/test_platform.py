"""Automated tests — Python standard library unittest only.

Run:  python -m unittest discover tests -v
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# Isolated database per test run, created BEFORE importing app modules.
_tmp = tempfile.mkdtemp(prefix="kyh-test-")
os.environ["KYH_DB"] = os.path.join(_tmp, "test.db")
os.environ["KYH_SECRETS"] = os.path.join(_tmp, "secrets.json")

from app import coverage, database, observations, pricing_v2, underwriting  # noqa: E402
from app.database import get_config, set_config                  # noqa: E402


def fresh_company(conn, name="TestCo", sector="Healthcare", nic="86"):
    cid = database.new_id("CO")
    conn.execute("""INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,geography,
                    created_at,nic_code,years_in_operation) VALUES (?,?,?,?,?,?,?,?,?)""",
                 (cid, name, sector, 1_000_000_000, 500, "India", database.now_iso(), nic, 10))
    pid = database.new_id("POL")
    conn.execute("""INSERT INTO policies (policy_id,company_id,status,period_start,
                    period_end,created_at,limit_total_inr,retention_inr)
                    VALUES (?,?, 'DRAFT','2026-09-01','2027-08-31',?,?,?)""",
                 (pid, cid, database.now_iso(), 50_000_000, 200_000))
    for h in conn.execute("SELECT * FROM coverage_head_defaults").fetchall():
        conn.execute("""INSERT INTO policy_coverages
            (policy_id,coverage_id,name,limit_inr,sublimit_inr,deductible_inr,
             severity_fraction,enabled) VALUES (?,?,?,?,?,?,?,1)""",
            (pid, h["coverage_id"], h["name"], 1_000_000, None, 0,
             h["severity_fraction"]))
    return cid, pid


def all_pass(conn, cid, source="QUESTIONNAIRE", strength=None):
    for c in conn.execute("SELECT control_id FROM controls").fetchall():
        observations.record_observation(conn, cid, c["control_id"], "true",
                                        source_type=source,
                                        evidence_strength=strength, actor="test")


class TestPremiumEngine(unittest.TestCase):
    """Engine B (V2) over Engine A's resolved evidence. The model's own maths is in test_pricing_v2.py."""
    @classmethod
    def setUpClass(cls):
        cls.conn = database.init_db(seed=False)

    def quote(self, pid):
        return pricing_v2.calculate_premium(self.conn, pid, persist=False)

    def test_v2_is_the_active_model_and_breakdown_adds_up(self):
        cid, pid = fresh_company(self.conn)
        all_pass(self.conn, cid, source="AGENT")  # TECHNICALLY_OBSERVED
        r = self.quote(pid)
        self.assertEqual(r["model_version"], "UNDERWRITING_MODEL_V2")
        self.assertEqual(r["classification"]["sector"], "Healthcare")   # NIC 86
        el = sum(p["frequency"] * p["payout"] for p in r["perils"])
        self.assertAlmostEqual(r["expected_loss"], round(el, 2), places=2)
        self.assertAlmostEqual(r["technical_premium"], r["expected_loss"] / 0.50, delta=0.02)
        self.assertAlmostEqual(r["total_premium"], r["technical_premium"] * 1.18, delta=0.02)

    def test_deterministic(self):
        cid, pid = fresh_company(self.conn)
        all_pass(self.conn, cid)
        self.assertEqual(self.quote(pid)["technical_premium"], self.quote(pid)["technical_premium"])

    def test_strong_controls_reduce_and_weak_increase(self):
        strong_c, strong_p = fresh_company(self.conn, "Strong")
        weak_c, weak_p = fresh_company(self.conn, "Weak")
        all_pass(self.conn, strong_c, source="AGENT")
        for c in self.conn.execute("SELECT control_id FROM controls").fetchall():
            observations.record_observation(self.conn, weak_c, c["control_id"], "false",
                                            source_type="AGENT", actor="test")
        rs, rw = self.quote(strong_p), self.quote(weak_p)
        for p in rs["perils"]:
            self.assertLessEqual(p["control_multiplier"], 1.0)
        for p in rw["perils"]:
            self.assertGreaterEqual(p["control_multiplier"], 1.0)
        self.assertLess(rs["technical_premium"], rw["technical_premium"])

    def test_evidence_strength_scales_credit(self):
        declared_c, declared_p = fresh_company(self.conn, "Declared")
        observed_c, observed_p = fresh_company(self.conn, "Observed")
        all_pass(self.conn, declared_c, source="QUESTIONNAIRE")   # DECLARED -> STATED
        all_pass(self.conn, observed_c, source="AGENT")           # TECHNICALLY_OBSERVED -> VERIFIED
        rd, ro = self.quote(declared_p), self.quote(observed_p)
        self.assertTrue(all(s == "STATED" for s in rd["statuses"].values()))
        self.assertTrue(all(s == "VERIFIED" for s in ro["statuses"].values()))
        self.assertLess(ro["technical_premium"], rd["technical_premium"])

    def test_independent_documents_verify_and_self_assessments_state(self):
        c1, p1 = fresh_company(self.conn, "SOC2")
        c2, p2 = fresh_company(self.conn, "CAIQ")
        for cid, dtype in ((c1, "SOC2_TYPE2"), (c2, "CAIQ")):
            did = observations.register_document(self.conn, cid, dtype, "evidence.pdf", "t")
            observations.assess_document_field(self.conn, did, "CTRL-EDR", "true", "p.12", actor="t")
        self.assertEqual(self.quote(p1)["statuses"]["CTRL-EDR"], "VERIFIED")
        self.assertEqual(self.quote(p2)["statuses"]["CTRL-EDR"], "STATED")

    def test_idp_mfa_export_verifies_mfa(self):
        cid, pid = fresh_company(self.conn, "IdP")
        observations.record_observation(self.conn, cid, "CTRL-MFA", "true", source_type="QUESTIONNAIRE", actor="t")
        self.assertEqual(self.quote(pid)["statuses"]["CTRL-MFA"], "STATED")
        did = observations.register_document(self.conn, cid, "IDP_MFA_EXPORT", "entra-mfa-policy.csv", "t")
        observations.assess_document_field(self.conn, did, "CTRL-MFA", "true", "Conditional access policy MFA-All",
                                           actor="t")
        self.assertEqual(self.quote(pid)["statuses"]["CTRL-MFA"], "VERIFIED")

    def test_best_evidence_wins_resolution(self):
        cid, pid = fresh_company(self.conn, "Resolve")
        observations.record_observation(self.conn, cid, "CTRL-MFA", "true",
                                        source_type="QUESTIONNAIRE", actor="t")
        observations.record_observation(self.conn, cid, "CTRL-MFA", "false",
                                        source_type="AGENT", actor="t")
        posture = observations.resolve_posture(self.conn, cid)
        p = posture["CTRL-MFA"]
        self.assertEqual(p["status"], "FAIL")  # technical observation outranks declared
        self.assertEqual(p["evidence_strength"], "TECHNICALLY_OBSERVED")
        self.assertTrue(p["conflict"])
        self.assertEqual(self.quote(pid)["statuses"]["CTRL-MFA"], "NOT_WORKING")

    def test_existence_currency_tested_dims(self):
        cid, pid = fresh_company(self.conn, "Dims")
        # Claimed TESTED strength but dims say tested=false -> downgraded to DOCUMENTED
        oid = observations.record_observation(
            self.conn, cid, "CTRL-IRPLAN", "true", source_type="DOCUMENT",
            evidence_strength="TESTED",
            dims={"exists": True, "current": True, "tested": False}, actor="t")
        row = self.conn.execute("SELECT * FROM observations WHERE observation_id=?",
                                (oid,)).fetchone()
        self.assertEqual(row["evidence_strength"], "DOCUMENTED")
        # current=false downgrades value to partial
        oid2 = observations.record_observation(
            self.conn, cid, "CTRL-BACKUP-TESTED", "true", source_type="DOCUMENT",
            dims={"exists": True, "current": False, "tested": False}, actor="t")
        row2 = self.conn.execute("SELECT * FROM observations WHERE observation_id=?",
                                 (oid2,)).fetchone()
        self.assertEqual(row2["value"], "partial")

    def test_warranty_gating_eligibility(self):
        cid, pid = fresh_company(self.conn, "Gate")
        all_pass(self.conn, cid, source="AGENT")
        observations.record_observation(self.conn, cid, "CTRL-EDR", "false",
                                        source_type="AGENT", actor="t")
        set_config(self.conn, "warranty_gate_mode", "WARN")
        self.assertEqual(self.quote(pid)["eligibility"]["status"], "CONDITIONALLY_ELIGIBLE")
        set_config(self.conn, "warranty_gate_mode", "BLOCK")
        r2 = self.quote(pid)
        self.assertEqual(r2["eligibility"]["status"], "INELIGIBLE")
        self.assertIn("CTRL-EDR", r2["eligibility"]["reason"])

    def test_outside_in_signal_is_evidence_not_a_modifier(self):
        cid, pid = fresh_company(self.conn, "Signals")
        all_pass(self.conn, cid)
        before = self.quote(pid)
        observations.record_signal(self.conn, cid, "EXPOSED_RDP", "3389 open", actor="t")
        after = self.quote(pid)
        self.assertEqual(after["statuses"]["CTRL-SECCONFIG"], "NOT_WORKING")
        self.assertGreater(after["technical_premium"], before["technical_premium"])

    def test_invalid_value_rejected(self):
        cid, pid = fresh_company(self.conn, "Bad")
        with self.assertRaises(observations.ValidationError) as cm:
            observations.record_observation(self.conn, cid, "CTRL-MFA", "banana",
                                            source_type="AGENT", actor="t")
        self.assertEqual(cm.exception.code, "INVALID_CONTROL_VALUE")


class TestPolicyLifecycleAndWarranties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = database.init_db(seed=False)

    def _quote_and_bind(self, name="Life"):
        cid, pid = fresh_company(self.conn, name)
        all_pass(self.conn, cid, source="AGENT")
        r = pricing_v2.calculate_premium(self.conn, pid)  # persisted, V2
        underwriting.bind_policy(self.conn, pid, r["calculation_id"])
        return cid, pid, r

    def test_quote_bind_and_snapshot_reproducibility(self):
        cid, pid, r = self._quote_and_bind("Snap")
        pol = self.conn.execute("SELECT * FROM policies WHERE policy_id=?", (pid,)).fetchone()
        self.assertEqual(pol["status"], "BOUND")
        self.assertEqual(pol["bound_premium"], r["technical_premium"])
        # Change company data afterwards; historical calc must be unchanged.
        self.conn.execute("UPDATE companies SET nic_code='64' WHERE company_id=?", (cid,))
        row = self.conn.execute("SELECT * FROM calculations WHERE calculation_id=?",
                                (r["calculation_id"],)).fetchone()
        stored = json.loads(row["result_json"])
        self.assertEqual(stored["technical_premium"], r["technical_premium"])
        snap = json.loads(row["input_snapshot"])
        self.assertEqual(snap["inputs"]["nic_code"], "86")
        # the snapshot alone reproduces the quote, whatever changed in the database since
        self.assertEqual(pricing_v2.reproduce(snap)["technical_premium"], r["technical_premium"])

    def test_v1_quotes_still_reproduce(self):
        """V1 is frozen: a quote made with V1 reproduces from its stored snapshot and result."""
        cid, pid = fresh_company(self.conn, "V1 era")
        all_pass(self.conn, cid, source="AGENT")
        r = underwriting.calculate_premium(self.conn, pid)   # the frozen V1 engine
        row = self.conn.execute("SELECT * FROM calculations WHERE calculation_id=?",
                                (r["calculation_id"],)).fetchone()
        self.assertEqual(row["model_version"], "UNDERWRITING_MODEL_V1")
        self.assertEqual(underwriting.reproduce_v1(json.loads(row["input_snapshot"]),
                                                   json.loads(row["result_json"])), row["technical_premium"])

    def test_MANDATORY_post_bind_no_reprice(self):
        """Agent observation changes -> warranty state changes -> premium does NOT change."""
        cid, pid, r = self._quote_and_bind("NoReprice")
        premium_before = self.conn.execute(
            "SELECT bound_premium FROM policies WHERE policy_id=?", (pid,)).fetchone()[0]
        # Post-bind failing observation (MFA down)
        observations.record_observation(self.conn, cid, "CTRL-MFA", "false",
                                        source_type="AGENT", actor="agent:test")
        coverage.evaluate_policy(self.conn, pid, cid)
        w = self.conn.execute("SELECT * FROM warranties WHERE policy_id=? AND control_id='CTRL-MFA'",
                              (pid,)).fetchone()
        self.assertEqual(w["state"], "IN_GRACE")           # warranty state changed
        self.assertIsNotNone(w["grace_expires_at"])
        premium_after = self.conn.execute(
            "SELECT bound_premium FROM policies WHERE policy_id=?", (pid,)).fetchone()[0]
        self.assertEqual(premium_before, premium_after)     # premium did NOT change
        # And the engine actively refuses to re-price a bound policy.
        with self.assertRaises(pricing_v2.EngineError) as cm:
            pricing_v2.calculate_premium(self.conn, pid)
        self.assertEqual(cm.exception.code, "POLICY_ALREADY_BOUND")
        # No new calculation rows were created for this policy after bind.
        n = self.conn.execute("SELECT COUNT(*) c FROM calculations WHERE policy_id=?",
                              (pid,)).fetchone()["c"]
        self.assertEqual(n, 1)

    def test_warranty_full_state_machine(self):
        cid, pid, _ = self._quote_and_bind("States")
        # fail -> IN_GRACE
        observations.record_observation(self.conn, cid, "CTRL-EDR", "false",
                                        source_type="AGENT", actor="t")
        coverage.evaluate_policy(self.conn, pid, cid)
        w = self.conn.execute("SELECT * FROM warranties WHERE policy_id=? AND control_id='CTRL-EDR'",
                              (pid,)).fetchone()
        self.assertEqual(w["state"], "IN_GRACE")
        # remediate -> MET (via REMEDIATED)
        observations.record_observation(self.conn, cid, "CTRL-EDR", "true",
                                        source_type="AGENT", actor="t")
        coverage.evaluate_policy(self.conn, pid, cid)
        w = self.conn.execute("SELECT state FROM warranties WHERE policy_id=? AND control_id='CTRL-EDR'",
                              (pid,)).fetchone()
        self.assertEqual(w["state"], "MET")
        states = [e["to_state"] for e in self.conn.execute(
            "SELECT * FROM warranty_events WHERE policy_id=? AND control_id='CTRL-EDR' ORDER BY at",
            (pid,)).fetchall()]
        self.assertIn("REMEDIATED", states)
        # fail again, then force grace expiry -> BREACHED, consequence applies
        observations.record_observation(self.conn, cid, "CTRL-EDR", "false",
                                        source_type="AGENT", actor="t")
        coverage.evaluate_policy(self.conn, pid, cid)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        self.conn.execute("UPDATE warranties SET grace_expires_at=? WHERE policy_id=? AND control_id='CTRL-EDR'",
                          (past, pid))
        coverage.expire_grace_periods(self.conn)
        wv = [x for x in coverage.policy_warranties(self.conn, pid)
              if x["control_id"] == "CTRL-EDR"][0]
        self.assertEqual(wv["state"], "BREACHED")
        self.assertTrue(wv["coverage_consequence"]["applies"])
        self.assertIn("policy wording", wv["coverage_consequence"]["label"])

    def test_grace_period_uses_catalogue_days(self):
        cid, pid, _ = self._quote_and_bind("Grace")
        observations.record_observation(self.conn, cid, "CTRL-PATCH-CRIT", "false",
                                        source_type="AGENT", actor="t")
        coverage.evaluate_policy(self.conn, pid, cid)
        w = self.conn.execute(
            "SELECT * FROM warranties WHERE policy_id=? AND control_id='CTRL-PATCH-CRIT'",
            (pid,)).fetchone()
        delta = (datetime.fromisoformat(w["grace_expires_at"]) -
                 datetime.fromisoformat(w["breach_detected_at"]))
        self.assertEqual(delta.days, 14)  # configured for patching warranty

    def test_audit_events_recorded(self):
        cid, pid, r = self._quote_and_bind("Audit")
        observations.record_observation(self.conn, cid, "CTRL-MFA", "false",
                                        source_type="AGENT", actor="t")
        coverage.evaluate_policy(self.conn, pid, cid)
        types = {row["event_type"] for row in self.conn.execute(
            "SELECT DISTINCT event_type FROM audit_events").fetchall()}
        for expected in ("CONTROL_OBSERVATION_CREATED", "PREMIUM_CALCULATED",
                         "POLICY_QUOTED", "POLICY_BOUND", "WARRANTY_BREACH_DETECTED"):
            self.assertIn(expected, types)


class TestHTTPEndToEnd(unittest.TestCase):
    """Full demonstration scenario over real HTTP (spec §32 / §39)."""

    @classmethod
    def setUpClass(cls):
        from app.api import make_server
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        with open(os.environ["KYH_SECRETS"]) as fh:
            cls.tokens = json.load(fh)["role_tokens"]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def call(self, method, path, body=None, token=None, agent_token=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Auth-Token"] = token
        if agent_token:
            headers["Authorization"] = f"Bearer {agent_token}"
        req = urllib.request.Request(url, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body else None)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_full_demonstration_scenario(self):
        uw = self.tokens["underwriter"]
        # Create company (Company B analogue: mixed security)
        st, co = self.call("POST", "/api/companies", token=uw, body=dict(
            name="Demo Mixed Co", nic_code="28", years_in_operation=15,
            annual_revenue_inr=600_000_000, employee_count=400, geography="India",
            limit_total_inr=20_000_000, retention_inr=100_000))
        self.assertEqual(st, 200)
        cid, pid, agent_token = co["company_id"], co["policy_id"], co["agent_token"]

        # Stage 1 — questionnaire
        answers = [dict(control_id=c, value=v) for c, v in [
            ("CTRL-MFA", "true"), ("CTRL-EDR", "true"), ("CTRL-BACKUP-TESTED", "false"),
            ("CTRL-PATCH-CRIT", "true"), ("CTRL-PAM", "true"), ("CTRL-SEGMENTATION", "true"),
            ("CTRL-EMAILSEC", "true"), ("CTRL-VULNMGMT", "true"), ("CTRL-IRPLAN", "true"),
            ("CTRL-AWARENESS", "false"), ("CTRL-ASSETINV", "false"),
            ("CTRL-PASSPOLICY", "true"), ("CTRL-LOGGING", "true"),
            ("CTRL-SECCONFIG", "false"), ("CTRL-ENCRYPTION", "true")]]
        st, _ = self.call("POST", "/api/questionnaires", token=uw,
                          body=dict(company_id=cid, answers=answers))
        self.assertEqual(st, 200)

        # Stage 2 — agent reports MFA PASS, EDR PASS, backups recent but restore untested
        report = dict(hostname="ep-01", platform="Linux", checks=[
            dict(control_id="CTRL-MFA", status="PASS", evidence="sim"),
            dict(control_id="CTRL-EDR", status="PASS", evidence="sim"),
            dict(control_id="CTRL-BACKUP-TESTED", status="WARN", evidence="sim: restore untested"),
            dict(control_id="CTRL-ENCRYPTION", status="NOT_SUPPORTED", evidence="n/a")])
        st, rr = self.call("POST", "/api/agent/report", agent_token=agent_token, body=report)
        self.assertEqual(st, 200)
        self.assertEqual(rr["observations_recorded"], 3)
        self.assertIn("CTRL-ENCRYPTION", rr["not_supported"])
        self.assertFalse(rr["repricing_performed"])

        # Stage 3 — premium calculation with full breakdown
        st, quote = self.call("POST", "/api/quote", token=uw, body=dict(policy_id=pid))
        self.assertEqual(st, 200)
        for key in ("classification", "perils", "claims", "expected_loss", "loadings",
                    "technical_premium", "gst", "total_premium", "eligibility", "referral",
                    "what_if", "assumptions", "calculation_id"):
            self.assertIn(key, quote)
        self.assertEqual(quote["model_version"], "UNDERWRITING_MODEL_V2")
        self.assertEqual(quote["statuses"]["CTRL-EDR"], "VERIFIED")
        self.assertEqual(quote["statuses"]["CTRL-BACKUP-TESTED"], "STATED")
        self.assertEqual(quote["eligibility"]["status"], "CONDITIONALLY_ELIGIBLE")
        premium = quote["technical_premium"]

        # Stage 4 — bind
        st, bound = self.call("POST", "/api/policies/bind", token=uw,
                              body=dict(policy_id=pid, calculation_id=quote["calculation_id"]))
        self.assertEqual(st, 200)
        self.assertEqual(bound["bound_premium"], premium)

        # Stage 5 — later, agent reports MFA FAIL
        st, rr2 = self.call("POST", "/api/agent/report", agent_token=agent_token,
                            body=dict(hostname="ep-01", platform="Linux", checks=[
                                dict(control_id="CTRL-MFA", status="FAIL",
                                     evidence="sim: MFA disabled")]))
        self.assertEqual(st, 200)
        self.assertFalse(rr2["repricing_performed"])
        self.assertIsNotNone(rr2["warranty_evaluation"])

        # Stage 6 — warranty breach visible with grace + consequence
        st, w = self.call("GET", f"/api/policies/{pid}/warranties", token=uw)
        mfa = [x for x in w["warranties"] if x["control_id"] == "CTRL-MFA"][0]
        self.assertEqual(mfa["state"], "IN_GRACE")
        self.assertIsNotNone(mfa["grace_expires_at"])
        self.assertIn("Grace period expires", mfa["coverage_consequence"]["text"])
        self.assertIn("do not automatically re-price", w["note"])

        # Stage 7 — premium UNCHANGED, and re-quote refused
        st, polv = self.call("GET", f"/api/policies/{pid}", token=uw)
        self.assertEqual(polv["policy"]["bound_premium"], premium)
        st, refuse = self.call("POST", "/api/quote", token=uw, body=dict(policy_id=pid))
        self.assertEqual(st, 409)
        self.assertEqual(refuse["error"], "POLICY_ALREADY_BOUND")

        # Everything audited
        st, log = self.call("GET", "/api/audit?limit=400", token=uw)
        types = {e["event_type"] for e in log["events"]}
        for expected in ("QUESTIONNAIRE_UPDATED", "AGENT_REPORT_RECEIVED",
                         "PREMIUM_CALCULATED", "POLICY_BOUND",
                         "WARRANTY_BREACH_DETECTED"):
            self.assertIn(expected, types)

    def test_auth_and_role_separation(self):
        st, e = self.call("GET", "/api/dashboard")
        self.assertEqual(st, 401)
        cust = self.tokens["customer"]
        st, e = self.call("POST", "/api/quote", token=cust, body=dict(policy_id="x"))
        self.assertEqual(st, 403)  # customers cannot price
        st, e = self.call("PUT", "/api/admin/config", token=self.tokens["underwriter"],
                          body={"loading_profit": 0.1})
        self.assertEqual(st, 403)  # underwriters cannot change model config

    def test_customer_is_read_only_and_sees_only_their_company(self):
        uw, cust = self.tokens["underwriter"], self.tokens["customer"]
        st, me = self.call("GET", "/api/me", token=cust)
        self.assertEqual(st, 200)
        self.assertTrue(me["read_only"])
        own = me["company_id"]
        self.assertTrue(own)
        st, companies = self.call("GET", "/api/companies", token=cust)
        self.assertEqual({c["company_id"] for c in companies["companies"]}, {own})
        st, all_cos = self.call("GET", "/api/companies", token=uw)
        other = next(c["company_id"] for c in all_cos["companies"] if c["company_id"] != own)
        self.assertEqual(self.call("GET", f"/api/companies/{other}", token=cust)[0], 404)
        st, detail = self.call("GET", f"/api/companies/{own}", token=cust)
        self.assertEqual(st, 200)
        pid = detail["policy"]["policy_id"]
        for path in ("/api/dashboard", "/api/audit", "/api/admin/pricing-params"):
            self.assertEqual(self.call("GET", path, token=cust)[0], 403, path)
        writes = [("POST", "/api/claims", dict(company_id=own, incident_date="2025-01-01",
                                                incident_type="Ransomware", loss_amount_inr=1)),
                  ("POST", "/api/questionnaires", dict(company_id=own, answers=[])),
                  ("POST", "/api/documents", dict(company_id=own, document_type="OTHER", filename="x.pdf")),
                  ("POST", "/api/outside-in", dict(company_id=own, signal_type="EXPOSED_RDP")),
                  ("PUT", f"/api/companies/{own}", dict(nic_code="86")),
                  ("PUT", f"/api/policies/{pid}/coverages", dict(retention_inr=1)),
                  ("POST", "/api/policies/bind", dict(policy_id=pid, calculation_id="x"))]
        for method, path, body in writes:
            self.assertEqual(self.call(method, path, token=cust, body=body)[0], 403, path)
        # the customer's quote carries the price and what would lower it, not the working
        st, q = self.call("POST", "/api/quote", token=uw, body=dict(policy_id=pid))
        self.assertEqual(st, 200)
        st, cq = self.call("GET", f"/api/quote/{q['calculation_id']}", token=cust)
        self.assertEqual(st, 200)
        self.assertTrue(cq["customer_view"])
        self.assertEqual(cq["technical_premium"], q["technical_premium"])
        for hidden in ("perils", "loadings", "referral", "input_snapshot", "expected_loss"):
            self.assertNotIn(hidden, cq)

    def test_malformed_input_structured_error(self):
        uw = self.tokens["underwriter"]
        st, e = self.call("POST", "/api/companies", token=uw,
                          body=dict(name="X", nic_code="not-a-code",
                                    annual_revenue_inr="abc", employee_count=1))
        self.assertEqual(st, 400)
        self.assertIn("error", e)
        self.assertIn("message", e)


if __name__ == "__main__":
    unittest.main(verbosity=2)
