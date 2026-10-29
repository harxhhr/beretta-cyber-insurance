"""Collector link (Part 2 -> Part 1): authentication, evidence recording, warranty-only effect.

Run:  python -m unittest discover tests -v
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
_tmp = tempfile.mkdtemp(prefix="kyh-fleet-test-")
os.environ.setdefault("KYH_DB", os.path.join(_tmp, "test.db"))
os.environ.setdefault("KYH_SECRETS", os.path.join(_tmp, "secrets.json"))

from app import coverage, database, fleet, observations, pricing_v2, underwriting  # noqa: E402


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


class FleetLinkBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = database.init_db(seed=False)

    def setUp(self):
        c = self.conn
        self.cid = database.new_id("CO")
        c.execute("INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,geography,"
                  "created_at,nic_code,years_in_operation) VALUES (?,?,?,?,?,?,?,?,?)",
                  (self.cid, "Kalinga Components", "Industrials", 6e8, 420, "India", database.now_iso(), "28", 18))
        self.pid = database.new_id("POL")
        c.execute("INSERT INTO policies (policy_id,company_id,status,period_start,period_end,created_at,"
                  "limit_total_inr,retention_inr) VALUES (?,?, 'DRAFT','2026-09-01','2027-08-31',?,?,?)",
                  (self.pid, self.cid, database.now_iso(), 20_000_000, 100_000))
        for h in c.execute("SELECT * FROM coverage_head_defaults").fetchall():
            c.execute("INSERT INTO policy_coverages (policy_id,coverage_id,name,limit_inr,sublimit_inr,"
                      "deductible_inr,severity_fraction,enabled) VALUES (?,?,?,?,?,?,?,1)",
                      (self.pid, h["coverage_id"], h["name"], 1_000_000, None, 0, h["severity_fraction"]))
        for ctrl in c.execute("SELECT control_id FROM controls WHERE monitoring_only=0").fetchall():
            observations.record_observation(c, self.cid, ctrl["control_id"], "true",
                                            source_type="QUESTIONNAIRE", actor="t")
        reg = fleet.register_collector(c, "KYH collector", "https://collector.test:8443", "admin")
        self.col_id, self.secret = reg["collector_id"], reg["secret"]
        fleet.link_company(c, self.col_id, self.cid, "co_kalinga", "admin")
        self.seq = 0

    def payload(self, controls, seq=None, sent=None, company=None, **extra):
        if seq is None:
            self.seq += 1
            seq = self.seq
        now = sent or datetime.now(timezone.utc)
        body = {"schema": fleet.SCHEMA_ID, "collector_id": self.col_id, "seq": seq, "sent_at": iso(now),
                "evaluated_at": iso(now),
                "company": {"collector_company_id": "co_kalinga", "platform_company_id": company or self.cid,
                            "declared_endpoints": 4},
                "coverage": {"status": "PASS", "declared": 4, "reporting": 4},
                "controls": [{"platform_control_id": k, "status": "FAIL" if v == "false" else "PASS", "value": v,
                              "reason": f"{k} test", "passing": 4 if v != "false" else 3, "observed": 4,
                              "failing_hosts": [{"host": "KAL-PLANT-WS03"}] if v == "false" else [],
                              "sources": [{"control": "EDR", "status": "PASS"}]} for k, v in controls.items()],
                "fleet": {"declared": 4, "reporting": 4, "liveness_counts": {"ONLINE": 4}, "hosts": []}}
        body.update(extra)
        return json.dumps(body).encode()

    def sig(self, raw, secret=None):
        return "v1=" + hmac.new(bytes.fromhex(secret or self.secret), raw, hashlib.sha256).hexdigest()

    def send(self, controls, **kw):
        raw = self.payload(controls, **kw)
        col = fleet.authenticate(self.conn, self.col_id, self.sig(raw), raw)
        return fleet.ingest_rollup(self.conn, col, raw)

    def quote_and_bind(self):
        r = pricing_v2.calculate_premium(self.conn, self.pid)
        underwriting.bind_policy(self.conn, self.pid, r["calculation_id"])
        return r


class Authentication(FleetLinkBase):
    def test_bad_signature(self):
        raw = self.payload({"CTRL-EDR": "true"})
        with self.assertRaises(fleet.FleetError) as e:
            fleet.authenticate(self.conn, self.col_id, self.sig(raw, "00" * 32), raw)
        self.assertEqual((e.exception.code, e.exception.status), ("BAD_SIGNATURE", 401))

    def test_unknown_collector(self):
        with self.assertRaises(fleet.FleetError) as e:
            fleet.authenticate(self.conn, "COL-nope", "v1=x", b"{}")
        self.assertEqual(e.exception.code, "UNKNOWN_COLLECTOR")

    def test_replay_rejected(self):
        raw = self.payload({"CTRL-EDR": "true"}, seq=7)
        col = fleet.authenticate(self.conn, self.col_id, self.sig(raw), raw)
        fleet.ingest_rollup(self.conn, col, raw)
        col = fleet.authenticate(self.conn, self.col_id, self.sig(raw), raw)
        with self.assertRaises(fleet.FleetError) as e:
            fleet.ingest_rollup(self.conn, col, raw)
        self.assertEqual((e.exception.code, e.exception.status), ("REPLAY", 409))

    def test_stale_timestamp(self):
        with self.assertRaises(fleet.FleetError) as e:
            self.send({"CTRL-EDR": "true"}, sent=datetime.now(timezone.utc) - timedelta(minutes=10))
        self.assertEqual(e.exception.code, "STALE_OR_FUTURE")

    def test_company_must_be_linked_to_this_collector(self):
        other = database.new_id("CO")
        self.conn.execute("INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,"
                          "geography,created_at) VALUES (?,?,?,?,?,?,?)",
                          (other, "Other", "Retail", 1, 1, "India", database.now_iso()))
        with self.assertRaises(fleet.FleetError) as e:
            self.send({"CTRL-EDR": "true"}, company=other)
        self.assertEqual((e.exception.code, e.exception.status), ("NOT_LINKED", 403))

    def test_invalid_values_and_controls(self):
        with self.assertRaises(fleet.FleetError):
            self.send({"CTRL-EDR": "maybe"})
        with self.assertRaises(fleet.FleetError):
            self.send({"CTRL-DOES-NOT-EXIST": "true"})


class EvidenceAndPricing(FleetLinkBase):
    def test_rollup_recorded_as_technically_observed_fleet_evidence(self):
        out = self.send({"CTRL-EDR": "true", "CTRL-BACKUP-TESTED": "partial"})
        self.assertEqual(sorted(out["observations_recorded"]), ["CTRL-BACKUP-TESTED", "CTRL-EDR"])
        self.assertIs(out["repricing_performed"], False)
        p = observations.resolve_posture(self.conn, self.cid)
        self.assertEqual((p["CTRL-EDR"]["source_type"], p["CTRL-EDR"]["evidence_strength"]),
                         ("AGENT_FLEET", "TECHNICALLY_OBSERVED"))
        self.assertEqual(p["CTRL-BACKUP-TESTED"]["status"], "PARTIAL")
        self.assertIn("roll-up", p["CTRL-EDR"]["source_locator"])

    def test_unchanged_result_not_recorded_twice(self):
        self.send({"CTRL-EDR": "true"})
        out = self.send({"CTRL-EDR": "true"})
        self.assertEqual(out["unchanged"], ["CTRL-EDR"])
        n = self.conn.execute("SELECT COUNT(*) FROM observations WHERE company_id=? AND source_type='AGENT_FLEET'",
                              (self.cid,)).fetchone()[0]
        self.assertEqual(n, 1)

    def test_prebind_fleet_evidence_feeds_the_quote(self):
        before = pricing_v2.calculate_premium(self.conn, self.pid, persist=False)
        self.assertEqual(before["statuses"]["CTRL-EDR"], "STATED")          # questionnaire only
        self.send({"CTRL-EDR": "true", "CTRL-PATCH-CRIT": "true"})
        r = pricing_v2.calculate_premium(self.conn, self.pid, persist=False)
        self.assertEqual(r["evidence"]["CTRL-EDR"]["source_type"], "AGENT_FLEET")
        self.assertEqual(r["statuses"]["CTRL-EDR"], "VERIFIED")             # fleet evidence verifies
        self.assertLess(r["technical_premium"], before["technical_premium"])

    def test_fleet_backup_pass_is_sent_as_partial_and_priced_as_stated(self):
        self.send({"CTRL-BACKUP-TESTED": "partial"})
        r = pricing_v2.calculate_premium(self.conn, self.pid, persist=False)
        self.assertEqual(r["statuses"]["CTRL-BACKUP-TESTED"], "STATED")
        self.assertEqual(r["eligibility"]["status"], "CONDITIONALLY_ELIGIBLE")

    def test_monitoring_only_control_never_priced_or_gating(self):
        base = pricing_v2.calculate_premium(self.conn, self.pid, persist=False)
        self.send({"CTRL-AGENT-COVERAGE": "false"})
        r = pricing_v2.calculate_premium(self.conn, self.pid, persist=False)
        self.assertEqual(r["technical_premium"], base["technical_premium"])
        self.assertNotIn("CTRL-AGENT-COVERAGE", r["statuses"])
        self.assertNotIn("CTRL-AGENT-COVERAGE", r["eligibility"]["reason"])


class WarrantiesOnly(FleetLinkBase):
    def test_post_bind_fleet_failure_moves_warranty_never_premium(self):
        self.send({"CTRL-EDR": "true"})
        self.quote_and_bind()
        premium = self.conn.execute("SELECT bound_premium FROM policies WHERE policy_id=?", (self.pid,)).fetchone()[0]
        out = self.send({"CTRL-EDR": "false"})
        states = {w["control_id"]: w["state"] for w in out["warranties"]}
        self.assertEqual(states["CTRL-EDR"], "IN_GRACE")
        self.assertEqual(out["policy"]["status"], "BOUND")
        after = self.conn.execute("SELECT bound_premium FROM policies WHERE policy_id=?", (self.pid,)).fetchone()[0]
        self.assertEqual(premium, after)
        n = self.conn.execute("SELECT COUNT(*) FROM calculations WHERE policy_id=?", (self.pid,)).fetchone()[0]
        self.assertEqual(n, 1)
        out = self.send({"CTRL-EDR": "true"})
        self.assertEqual({w["control_id"]: w["state"] for w in out["warranties"]}["CTRL-EDR"], "MET")

    def test_coverage_warranty_created_at_bind_and_enforced(self):
        self.quote_and_bind()
        out = self.send({"CTRL-AGENT-COVERAGE": "false"})
        w = {x["control_id"]: x for x in out["warranties"]}["CTRL-AGENT-COVERAGE"]
        self.assertEqual((w["state"], w["grace_period_days"]), ("IN_GRACE", 14))

    def test_unlinked_policies_keep_coverage_warranty_met(self):
        self.quote_and_bind()
        ws = {w["control_id"]: w["state"] for w in coverage.policy_warranties(self.conn, self.pid)}
        self.assertEqual(ws["CTRL-AGENT-COVERAGE"], "MET")   # no evidence is not a breach

    def test_snapshot_stored_for_the_dashboard(self):
        self.send({"CTRL-EDR": "true"})
        snap = fleet.latest_snapshot(self.conn, self.cid)
        self.assertEqual(snap["collector_company_id"], "co_kalinga")
        self.assertEqual(snap["dashboard_url"], "https://collector.test:8443")


class HttpRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.api import make_server
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        with open(database.SECRETS_PATH) as fh:
            cls.tokens = json.load(fh)["role_tokens"]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def call(self, method, path, body=None, headers=None, raw=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                     data=raw if raw is not None else (json.dumps(body).encode() if body else None),
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_admin_register_link_and_signed_rollup(self):
        admin = {"X-Auth-Token": self.tokens["admin"]}
        st, _ = self.call("POST", "/api/admin/collectors", {"name": "x"}, {"X-Auth-Token": self.tokens["customer"]})
        self.assertEqual(st, 403)
        st, reg = self.call("POST", "/api/admin/collectors", {"name": "KYH collector",
                                                              "dashboard_url": "https://c:8443"}, admin)
        self.assertEqual(st, 200)
        st, co = self.call("POST", "/api/companies", {"name": "HTTP Co", "nic_code": "28",
                                                      "annual_revenue_inr": 1e8, "employee_count": 50},
                           {"X-Auth-Token": self.tokens["underwriter"]})
        st, _ = self.call("POST", f"/api/admin/collectors/{reg['collector_id']}/links",
                          {"company_id": co["company_id"], "collector_company_id": "co_http"}, admin)
        self.assertEqual(st, 200)
        now = iso(datetime.now(timezone.utc))
        body = json.dumps({"schema": fleet.SCHEMA_ID, "collector_id": reg["collector_id"], "seq": 1, "sent_at": now,
                           "evaluated_at": now, "company": {"platform_company_id": co["company_id"]},
                           "controls": [{"platform_control_id": "CTRL-EDR", "status": "PASS", "value": "true",
                                         "passing": 2, "observed": 2, "sources": [{"control": "EDR"}]}],
                           "fleet": {"hosts": []}}).encode()
        sig = "v1=" + hmac.new(bytes.fromhex(reg["secret"]), body, hashlib.sha256).hexdigest()
        st, out = self.call("POST", "/api/collector/rollup", raw=body,
                            headers={"X-KYH-Collector-Id": reg["collector_id"], "X-KYH-Signature": sig})
        self.assertEqual(st, 200, out)
        self.assertIs(out["repricing_performed"], False)
        st, out = self.call("POST", "/api/collector/rollup", raw=body,
                            headers={"X-KYH-Collector-Id": reg["collector_id"], "X-KYH-Signature": "v1=bad"})
        self.assertEqual(st, 401)
        st, f = self.call("GET", f"/api/companies/{co['company_id']}/fleet", headers=admin)
        self.assertEqual(f["fleet"]["collector_company_id"], "co_http")


if __name__ == "__main__":
    unittest.main()
