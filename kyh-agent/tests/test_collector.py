"""Collector: enrollment, ingestion security, fleet roll-up, silence rule, warranty lifecycle, no repricing."""
import hashlib
import hmac
import inspect
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import _paths  # noqa: F401
from kyh_collector import core, evaluate as ev, settings as settings_mod
from kyh_collector import db as dbm

T0 = datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)
BUILD, POLICY = "b" * 64, "p" * 64
S = settings_mod.load("/nonexistent")
S["coverage_onboarding_days"] = 0  # most tests exercise coverage immediately; onboarding tested separately
WARRANTY_CHECKS = {"PATCH": "patch.security_updates", "EDR": "edr.running_healthy",
                   "BACKUP": "backup.recent_success", "MFA": "mfa.identity_provider"}


class Base(unittest.TestCase):
    declared = 4
    demo = False

    def setUp(self):
        self.d = tempfile.mkdtemp()
        path = os.path.join(self.d, "c.db")
        dbm.init(path)
        self.conn = dbm.connect(path)
        self.now = T0
        self.cid = core.add_company(self.conn, T0, "Kalinga Components", self.declared, demo=self.demo)
        self.token = core.issue_enrollment_token(self.conn, T0, self.cid, max_uses=100, days=7)
        core.approve(self.conn, T0, "approved_builds", BUILD, "release")
        core.approve(self.conn, T0, "approved_policies", POLICY, "baseline")
        core.bind_policy(self.conn, T0, self.cid, 245000, S)
        self.agents = {}
        self.seq = {}

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.d)

    def enroll(self, host, build=BUILD):
        out = core.enroll(self.conn, self.now, {"enrollment_token": self.token, "hostname": host,
                                                "platform": "windows", "build_hash": build, "policy_hash": POLICY})
        self.agents[host] = out
        self.seq[host] = 0
        return out

    def body(self, host, results, kind="full", seq=None, created=None, build=BUILD, simulated=False, **extra):
        if seq is None:
            self.seq[host] += 1
            seq = self.seq[host]
        env = {"schema_version": 2, "kind": kind, "agent_id": self.agents[host]["agent_id"], "seq": seq,
               "created_at": core.iso(created or self.now), "simulated": simulated,
               "agent": {"build_hash": build, "hostname": host, "version": "2.0.0"},
               "policy": {"hash": POLICY}, "results": results}
        env.update(extra)
        return json.dumps(env, sort_keys=True).encode()

    def sig(self, host, raw):
        return "v1=" + hmac.new(bytes.fromhex(self.agents[host]["agent_secret"]), raw, hashlib.sha256).hexdigest()

    def send(self, host, statuses: dict, **kw):
        """statuses: {control: status or (status, assurance)}"""
        results = []
        for control, st in statuses.items():
            st, assurance = st if isinstance(st, tuple) else (st, None)
            results.append({"check_id": WARRANTY_CHECKS.get(control, control.lower() + ".check"), "control": control,
                            "tier": "warranty" if control in WARRANTY_CHECKS else "important", "status": st,
                            "assurance": assurance, "summary": f"{control} {st}", "evidence": {},
                            "observed_at": core.iso(kw.get("created") or self.now)})
        raw = self.body(host, results, **kw)
        return core.ingest(self.conn, self.now, self.agents[host]["agent_id"], self.sig(host, raw), raw, S)

    def healthy(self, host, **kw):
        return self.send(host, {"PATCH": "PASS", "EDR": ("PASS", "OPERATING"), "BACKUP": "PASS",
                                "MFA": "NOT_SUPPORTED"}, **kw)

    def evaluate(self):
        return ev.evaluate_company(self.conn, self.cid, self.now, S)

    def warranty(self, snap, control):
        return next(w for w in snap["warranties"] if w["control"] == control)

    def advance(self, **kw):
        self.now += timedelta(**kw)


class Enrollment(Base):
    def test_enroll_returns_identity_and_secret(self):
        out = self.enroll("KAL-LT01")
        self.assertTrue(out["agent_id"].startswith("ag_"))
        self.assertEqual(len(out["agent_secret"]), 64)
        self.assertEqual(out["company_id"], self.cid)

    def test_bad_expired_exhausted_tokens(self):
        with self.assertRaises(core.ApiError) as e:
            core.enroll(self.conn, self.now, {"enrollment_token": "kyh_enr_wrong"})
        self.assertEqual(e.exception.code, "BAD_TOKEN")
        with self.assertRaises(core.ApiError) as e:
            core.enroll(self.conn, self.now + timedelta(days=8), {"enrollment_token": self.token})
        self.assertEqual(e.exception.code, "TOKEN_EXPIRED")
        one = core.issue_enrollment_token(self.conn, T0, self.cid, max_uses=1)
        core.enroll(self.conn, self.now, {"enrollment_token": one})
        with self.assertRaises(core.ApiError) as e:
            core.enroll(self.conn, self.now, {"enrollment_token": one})
        self.assertEqual(e.exception.code, "TOKEN_EXHAUSTED")

    def test_tokens_are_stored_hashed(self):
        rows = self.conn.execute("SELECT token_hash FROM enrollment_tokens").fetchall()
        self.assertNotIn(self.token, [r[0] for r in rows])


class IngestionSecurity(Base):
    def setUp(self):
        super().setUp()
        self.enroll("KAL-LT01")
        self.aid = self.agents["KAL-LT01"]["agent_id"]

    def ingest(self, raw, sig=None, agent_id=None):
        return core.ingest(self.conn, self.now, agent_id or self.aid, sig or self.sig("KAL-LT01", raw), raw, S)

    def assertRejected(self, code, raw, **kw):
        with self.assertRaises(core.ApiError) as e:
            self.ingest(raw, **kw)
        self.assertEqual(e.exception.code, code)
        return e.exception

    def test_valid_report_is_technically_observed(self):
        out = self.healthy("KAL-LT01")
        self.assertEqual(out["evidence_strength"], "TECHNICALLY_OBSERVED")

    def test_bad_signature_rejected_and_audited(self):
        raw = self.body("KAL-LT01", [])
        e = self.assertRejected("BAD_SIGNATURE", raw, sig="v1=" + "0" * 64)
        self.assertEqual(e.status, 401)
        self.assertTrue(self.conn.execute("SELECT 1 FROM audit_log WHERE action='REPORT_REJECTED'").fetchone())

    def test_body_modified_after_signing_rejected(self):
        raw = self.body("KAL-LT01", [])
        sig = self.sig("KAL-LT01", raw)
        self.assertRejected("BAD_SIGNATURE", raw.replace(b'"full"', b'"delta"'), sig=sig)

    def test_replay_and_out_of_order_rejected(self):
        raw = self.body("KAL-LT01", [], seq=5)
        self.ingest(raw)
        self.assertEqual(self.assertRejected("REPLAY", raw).status, 409)
        self.assertRejected("REPLAY", self.body("KAL-LT01", [], seq=4))

    def test_future_and_ancient_timestamps(self):
        self.assertRejected("FUTURE_TIMESTAMP", self.body("KAL-LT01", [], created=self.now + timedelta(minutes=10)))
        self.assertRejected("TOO_OLD", self.body("KAL-LT01", [], created=self.now - timedelta(days=31)))

    def test_offline_queue_within_window_accepted(self):
        out = self.ingest(self.body("KAL-LT01", [], created=self.now - timedelta(days=3)))
        self.assertTrue(out["accepted"])

    def test_unknown_agent_oversize_schema_mismatch(self):
        raw = self.body("KAL-LT01", [])
        self.assertRejected("UNKNOWN_AGENT", raw, agent_id="ag_nobody")
        self.assertRejected("TOO_LARGE", b"x" * (S["max_body_bytes"] + 1))
        self.assertRejected("SCHEMA_VERSION", self.body("KAL-LT01", [], schema_version=1))
        self.assertRejected("AGENT_MISMATCH", self.body("KAL-LT01", [], agent_id="ag_other"))

    def test_result_validation(self):
        bad = [{"check_id": "edr.x", "control": "EDR", "status": "TOTALLY_FINE"}]
        self.assertRejected("BAD_RESULT", self.body("KAL-LT01", bad))
        bad = [{"check_id": "<script>", "control": "EDR", "status": "PASS"}]
        self.assertRejected("BAD_RESULT", self.body("KAL-LT01", bad))

    def test_reports_are_stored_verbatim(self):
        raw = self.body("KAL-LT01", [])
        self.ingest(raw)
        row = self.conn.execute("SELECT body, body_sha256 FROM reports").fetchone()
        self.assertEqual(row["body"], raw)
        self.assertEqual(row["body_sha256"], hashlib.sha256(raw).hexdigest())

    def test_late_old_report_does_not_overwrite_newer_result(self):
        self.send("KAL-LT01", {"EDR": "FAIL"})
        self.send("KAL-LT01", {"EDR": "PASS"}, created=self.now - timedelta(hours=5))
        row = self.conn.execute("SELECT status FROM results_current WHERE control='EDR'").fetchone()
        self.assertEqual(row["status"], "FAIL")

    def test_host_detail_never_exposes_secret(self):
        self.healthy("KAL-LT01")
        detail = ev.host_detail(self.conn, self.aid)
        self.assertNotIn("secret", detail["agent"])
        self.assertNotIn(self.agents["KAL-LT01"]["agent_secret"], json.dumps(detail, default=str))


class EvidenceTrust(Base):
    def test_unapproved_build_is_stored_but_not_counted(self):
        self.enroll("KAL-LT01", build="e" * 64)
        out = self.send("KAL-LT01", {"EDR": "FAIL"}, build="e" * 64)
        self.assertEqual(out["evidence_strength"], "UNTRUSTED_BUILD")
        snap = self.evaluate()
        self.assertEqual(self.warranty(snap, "EDR")["state"], "MET")
        self.assertFalse(snap["hosts"][0]["build_trusted"])

    def test_simulated_reports_ignored_outside_demo_mode(self):
        self.enroll("KAL-LT01")
        self.send("KAL-LT01", {"EDR": "FAIL"}, simulated=True)
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "MET")


class DemoMode(Base):
    demo = True

    def test_simulated_reports_count_in_demo_mode(self):
        self.enroll("KAL-LT01")
        self.send("KAL-LT01", {"EDR": "FAIL"}, simulated=True)
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "IN_GRACE")


class FleetRollup(Base):
    declared = 20

    def test_95_percent_threshold(self):
        for i in range(20):
            self.enroll(f"H{i:02d}")
            self.healthy(f"H{i:02d}")
        self.send("H00", {"EDR": "FAIL"})
        c = next(x for x in self.evaluate()["controls"] if x["control"] == "EDR")
        self.assertEqual((c["status"], c["passing"], c["observed"]), ("PASS", 19, 20))
        self.send("H01", {"EDR": "FAIL"})
        c = next(x for x in self.evaluate()["controls"] if x["control"] == "EDR")
        self.assertEqual(c["status"], "FAIL")
        self.assertEqual({f["host"] for f in c["failing_hosts"]}, {"H00", "H01"})

    def test_pure_rollup_function(self):
        hosts = [("a", "PASS", ""), ("b", "NOT_SUPPORTED", ""), ("c", "ERROR", "")]
        self.assertEqual(ev.company_control("EDR", hosts, S)["status"], "PASS")   # only 'a' was observable
        self.assertEqual(ev.company_control("MFA", [("a", "NOT_SUPPORTED", "")], S)["status"], "NOT_OBSERVABLE")


class WarrantyLifecycle(Base):
    declared = 1

    def setUp(self):
        super().setUp()
        self.enroll("KAL-LT01")
        self.healthy("KAL-LT01")

    def test_full_cycle_met_grace_breached_remediated_met(self):
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "MET")
        out = self.send("KAL-LT01", {"EDR": ("FAIL", "ABSENT")})
        w = self.warranty(self.evaluate(), "EDR")
        self.assertEqual(w["state"], "IN_GRACE")
        self.assertEqual(w["grace_expires_at"], core.iso(self.now + timedelta(days=7)))
        self.assertEqual(out["results"], 1)

        self.advance(days=6, hours=23)
        self.send("KAL-LT01", {"EDR": "FAIL"})
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "IN_GRACE")

        self.advance(hours=2)  # grace expired; lazy evaluation on read is enough, no new report needed
        w = self.warranty(self.evaluate(), "EDR")
        self.assertEqual(w["state"], "BREACHED")
        self.assertIn("2x deductible", w["consequence"])

        self.send("KAL-LT01", {"EDR": "PASS"})
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "REMEDIATED")
        self.advance(hours=23)
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "REMEDIATED")
        self.advance(hours=2)
        self.send("KAL-LT01", {"EDR": "PASS"})
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "MET")

        path = [(r["from_state"], r["to_state"]) for r in self.conn.execute(
            "SELECT * FROM warranty_events WHERE control='EDR' ORDER BY id")]
        self.assertEqual(path, [(None, "MET"), ("MET", "IN_GRACE"), ("IN_GRACE", "BREACHED"),
                                ("BREACHED", "REMEDIATED"), ("REMEDIATED", "MET")])

    def test_fix_within_grace_and_regression(self):
        self.send("KAL-LT01", {"PATCH": "FAIL"})
        self.evaluate()
        self.advance(days=2)
        self.send("KAL-LT01", {"PATCH": "PASS"})
        self.assertEqual(self.warranty(self.evaluate(), "PATCH")["state"], "REMEDIATED")
        self.advance(hours=1)
        self.send("KAL-LT01", {"PATCH": "FAIL"})
        w = self.warranty(self.evaluate(), "PATCH")
        self.assertEqual(w["state"], "IN_GRACE")
        self.assertEqual(w["grace_expires_at"], core.iso(self.now + timedelta(days=14)))  # fresh grace period

    def test_stale_edr_present_counts_as_failing(self):
        self.send("KAL-LT01", {"EDR": ("FAIL", "PRESENT")})
        self.assertEqual(self.warranty(self.evaluate(), "EDR")["state"], "IN_GRACE")

    def test_mfa_not_observable_never_moves(self):
        for _ in range(3):
            self.advance(days=10)
            self.healthy("KAL-LT01")
            w = self.warranty(self.evaluate(), "MFA")
            self.assertEqual(w["state"], "MET")
            self.assertEqual(w["last_observed"], "NOT_OBSERVABLE")

    def test_pure_step_function(self):
        w = {"control": "EDR", "state": "MET"}
        new, event = ev.step(w, "FAIL", "down", T0, S)
        self.assertEqual((new["state"], event["to_state"]), ("IN_GRACE", "IN_GRACE"))
        same, none = ev.step(new, "NOT_OBSERVABLE", "", T0 + timedelta(days=30), S)
        self.assertIsNone(none)
        self.assertEqual(same["state"], "IN_GRACE")


class SilenceRule(Base):
    declared = 1

    def setUp(self):
        super().setUp()
        self.enroll("KAL-LT01")
        self.healthy("KAL-LT01")
        self.evaluate()

    def test_quiet_6_to_72h_is_unverified_without_state_change(self):
        self.advance(hours=10)
        snap = self.evaluate()
        self.assertEqual(snap["hosts"][0]["liveness"]["state"], "UNVERIFIED")
        self.assertTrue(all(w["state"] == "MET" for w in snap["warranties"]))

    def test_silent_host_that_was_passing_is_left_out_for_14_days(self):
        self.advance(hours=73)
        snap = self.evaluate()
        host = snap["hosts"][0]
        self.assertEqual(host["liveness"]["state"], "SILENT")
        self.assertEqual(host["controls"]["EDR"]["status"], "SILENT_PASS")
        for control in ("PATCH", "EDR", "BACKUP"):   # nothing left to observe: no warranty moves
            self.assertEqual(self.warranty(snap, control)["state"], "MET", control)
        self.assertEqual(self.warranty(snap, "MONITORING_COVERAGE")["state"], "IN_GRACE")  # still not reporting
        self.assertEqual(self.warranty(snap, "MFA")["state"], "MET")

    def test_silent_host_that_was_passing_fails_after_14_days(self):
        self.advance(days=14, hours=1)
        snap = self.evaluate()
        for control in ("PATCH", "EDR", "BACKUP"):
            self.assertEqual(self.warranty(snap, control)["state"], "IN_GRACE", control)
        self.assertIn("more than 14 days", snap["hosts"][0]["controls"]["EDR"]["reason"])
        self.assertEqual(self.warranty(snap, "MFA")["state"], "MET")  # never observable, so silence can't fail it

    def test_going_silent_never_hides_a_failure(self):
        self.send("KAL-LT01", {"PATCH": "PASS", "EDR": ("FAIL", "ABSENT"), "BACKUP": "PASS"})
        self.evaluate()
        self.advance(hours=73)
        snap = self.evaluate()
        cell = snap["hosts"][0]["controls"]["EDR"]
        self.assertEqual(cell["status"], "FAIL")
        self.assertIn("last result was FAIL", cell["reason"])
        self.assertEqual(self.warranty(snap, "EDR")["state"], "IN_GRACE")
        self.assertEqual(snap["hosts"][0]["controls"]["PATCH"]["status"], "SILENT_PASS")

    def test_heartbeat_keeps_host_alive(self):
        self.advance(hours=70)
        raw = self.body("KAL-LT01", [], kind="heartbeat")
        core.ingest(self.conn, self.now, self.agents["KAL-LT01"]["agent_id"], self.sig("KAL-LT01", raw), raw, S)
        self.advance(hours=5)
        self.assertEqual(self.evaluate()["hosts"][0]["liveness"]["state"], "ONLINE")


class StaffOnLeave(Base):
    """100 declared machines; 10 laptops are switched off for 10 days while staff are on leave."""
    declared = 100

    def setUp(self):
        super().setUp()
        self.hosts = [f"KAL-{i:03d}" for i in range(100)]
        for h in self.hosts:
            self.enroll(h)
            self.healthy(h)
        self.evaluate()

    def _day(self, n):
        self.advance(days=1)
        for h in self.hosts[10:]:          # the 90 in the office keep reporting
            self.send(h, {}, kind="heartbeat")
        return self.evaluate()

    def test_ten_days_of_leave_moves_no_warranty(self):
        for n in range(1, 11):
            snap = self._day(n)
            for control in ("PATCH", "EDR", "BACKUP", "MONITORING_COVERAGE"):
                self.assertEqual(self.warranty(snap, control)["state"], "MET", f"day {n} {control}")
        edr = next(c for c in snap["controls"] if c["control"] == "EDR")
        self.assertEqual((edr["observed"], edr["passing"], edr["silent_excluded"]), (90, 90, 10))
        self.assertIn("10 silent host(s)", edr["reason"])
        self.assertEqual(snap["coverage"]["reporting"], 90)   # exactly 90%: coverage still passes

    def test_after_14_days_quiet_they_count_as_failing(self):
        for n in range(1, 16):
            snap = self._day(n)
        self.assertEqual(self.warranty(snap, "EDR")["state"], "IN_GRACE")

    def test_eleven_on_leave_breaks_coverage_not_edr(self):
        quiet = self.hosts[:11]
        for _ in range(4):
            self.advance(days=1)
            for h in self.hosts[11:]:
                self.send(h, {}, kind="heartbeat")
        snap = self.evaluate()
        self.assertEqual(self.warranty(snap, "EDR")["state"], "MET")
        self.assertEqual(self.warranty(snap, "MONITORING_COVERAGE")["state"], "IN_GRACE")
        self.assertEqual(len(quiet), 11)


class CoverageWarranty(Base):
    declared = 10

    def test_coverage_below_90_percent_enters_grace(self):
        for i in range(8):
            self.enroll(f"H{i}")
            self.healthy(f"H{i}")
        snap = self.evaluate()
        self.assertEqual(snap["coverage"]["reporting"], 8)
        self.assertEqual(self.warranty(snap, "MONITORING_COVERAGE")["state"], "IN_GRACE")
        self.enroll("H8")
        self.healthy("H8")
        self.assertEqual(self.warranty(self.evaluate(), "MONITORING_COVERAGE")["state"], "REMEDIATED")


class Retirement(Base):
    declared = 1

    def test_retired_host_leaves_fleet_and_cannot_report(self):
        self.enroll("OLD")
        self.healthy("OLD")
        core.retire_agent(self.conn, self.now, self.agents["OLD"]["agent_id"], "decommissioned")
        self.assertEqual(self.evaluate()["hosts"], [])
        with self.assertRaises(core.ApiError) as e:
            self.healthy("OLD")
        self.assertEqual(e.exception.code, "UNKNOWN_AGENT")
        self.assertTrue(self.conn.execute("SELECT 1 FROM audit_log WHERE action='AGENT_RETIRED'").fetchone())


class CoverageOnboarding(Base):
    declared = 10

    def test_coverage_not_enforced_during_rollout_window(self):
        s = dict(S, coverage_onboarding_days=14)
        self.enroll("H0")
        self.healthy("H0")
        snap = ev.evaluate_company(self.conn, self.cid, self.now, s)
        self.assertEqual(snap["coverage"]["status"], "NOT_OBSERVABLE")
        self.assertEqual(self.warranty(snap, "MONITORING_COVERAGE")["state"], "MET")
        self.advance(days=15)
        self.healthy("H0")
        snap = ev.evaluate_company(self.conn, self.cid, self.now, s)
        self.assertEqual(self.warranty(snap, "MONITORING_COVERAGE")["state"], "IN_GRACE")


class NoRepricing(Base):
    """Mandatory acceptance test carried over from the platform: monitoring changes warranty state, never price."""
    declared = 2

    def test_premium_never_changes_whatever_monitoring_sees(self):
        before = dict(self.conn.execute("SELECT * FROM policies WHERE company_id=?", (self.cid,)).fetchone())
        for h in ("A", "B"):
            self.enroll(h)
            self.healthy(h)
        for step_ in range(5):
            self.send("A", {"EDR": "FAIL", "PATCH": "FAIL", "BACKUP": "FAIL"})
            self.advance(days=9)
            self.evaluate()
        self.advance(days=5)
        snap = self.evaluate()
        self.assertTrue(any(w["state"] == "BREACHED" for w in snap["warranties"]))
        after = dict(self.conn.execute("SELECT * FROM policies WHERE company_id=?", (self.cid,)).fetchone())
        self.assertEqual(before, after)
        self.assertEqual(after["bound_premium_inr"], 245000)

    def test_rebind_refused(self):
        with self.assertRaises(core.ApiError) as e:
            core.bind_policy(self.conn, self.now, self.cid, 1, S)
        self.assertEqual(e.exception.code, "POLICY_ALREADY_BOUND")

    def test_no_code_path_from_monitoring_to_policies_table(self):
        for fn in (core.ingest, ev.evaluate_company, ev.step):
            src = inspect.getsource(fn)
            self.assertNotRegex(src, r"(?i)(update|insert\s+into|delete\s+from)\s+policies")


if __name__ == "__main__":
    unittest.main()
