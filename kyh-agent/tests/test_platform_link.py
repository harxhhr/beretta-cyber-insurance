"""Linked mode: the collector feeds the KYH platform (Part 1), which owns warranties."""
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import _paths  # noqa: F401
from kyh_collector import core, platform_link as pl
from kyh_collector.server import App

T0 = datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)
BUILD, POLICY = "b" * 64, "p" * 64
LINK = {"url": "http://platform.test", "collector_id": "COL-test", "secret": "ab" * 32,
        "dashboard_url": "https://collector.test:8443"}


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


class FakePlatform:
    """Records what it receives and answers like the KYH platform."""

    def __init__(self):
        self.received, self.fail_next, self.state = [], False, {"CTRL-EDR": "MET"}

    def __call__(self, link, body):
        if self.fail_next:
            self.fail_next = False
            return None, {"error": "UNREACHABLE", "message": "connection refused"}
        sig = "v1=" + hmac.new(bytes.fromhex(link["secret"]), body, hashlib.sha256).hexdigest()
        p = json.loads(body)
        self.received.append((p, sig))
        for c in p["controls"]:
            if c["platform_control_id"] == "CTRL-EDR":
                self.state["CTRL-EDR"] = "IN_GRACE" if c["status"] == "FAIL" else "MET"
        return 200, {"repricing_performed": False,
                     "policy": {"status": "BOUND", "bound_at": "2026-10-20T00:00:00+00:00", "bound_premium": 245000},
                     "warranties": [{"control_id": k, "control_name": "Endpoint detection & response", "state": v,
                                     "grace_expires_at": None, "consequence": "deductible doubled"}
                                    for k, v in self.state.items()]}


class LinkedBase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.clock = Clock()
        self.app = App(self.d, clock=self.clock)
        self.app.settings["coverage_onboarding_days"] = 0
        conn = self.app.conn()
        self.cid = core.add_company(conn, T0, "Kalinga Components", 2, company_id="co_kalinga")
        core.approve(conn, T0, "approved_builds", BUILD, "r")
        core.approve(conn, T0, "approved_policies", POLICY, "p")
        self.token = core.issue_enrollment_token(conn, T0, self.cid, 10)
        pl.link_company(conn, T0, self.cid, "CO-platform1")
        self.agents, self.seq = {}, {}
        for h in ("KAL-LT01", "KAL-LT02"):
            self.agents[h] = core.enroll(conn, T0, {"enrollment_token": self.token, "hostname": h,
                                                    "build_hash": BUILD, "policy_hash": POLICY})
            self.seq[h] = 0
        conn.close()
        self.platform = FakePlatform()

    def tearDown(self):
        shutil.rmtree(self.d)

    def report(self, host, statuses):
        self.seq[host] += 1
        results = [{"check_id": c.lower() + ".x", "control": c, "tier": "warranty", "status": st,
                    "summary": f"{c} {st}", "evidence": {}, "observed_at": core.iso(self.clock())}
                   for c, st in statuses.items()]
        raw = json.dumps({"schema_version": 2, "kind": "full", "agent_id": self.agents[host]["agent_id"],
                          "seq": self.seq[host], "created_at": core.iso(self.clock()),
                          "agent": {"build_hash": BUILD, "hostname": host}, "policy": {"hash": POLICY},
                          "results": results}).encode()
        sig = "v1=" + hmac.new(bytes.fromhex(self.agents[host]["agent_secret"]), raw, hashlib.sha256).hexdigest()
        conn = self.app.conn()
        core.ingest(conn, self.clock(), self.agents[host]["agent_id"], sig, raw, self.app.settings)
        conn.close()

    def healthy(self, host):
        self.report(host, {"PATCH": "PASS", "EDR": "PASS", "BACKUP": "PASS", "MFA": "NOT_SUPPORTED",
                           "FIREWALL": "PASS", "TIME_SYNC": "FAIL"})

    def sync(self, force=False):
        return pl.sync_company(self.app, self.cid, LINK, force=force, sender=self.platform)


class Mapping(LinkedBase):
    def test_controls_mapped_grouped_and_honest(self):
        self.healthy("KAL-LT01")
        self.healthy("KAL-LT02")
        out = self.sync()
        sent = {c["platform_control_id"]: c for c in out["controls"]}
        self.assertEqual(sent["CTRL-EDR"]["value"], "true")
        self.assertEqual(sent["CTRL-BACKUP-TESTED"]["value"], "partial")          # restore test not observable
        self.assertIn("restore testing", sent["CTRL-BACKUP-TESTED"]["reason"])
        self.assertEqual(sent["CTRL-SECCONFIG"]["status"], "PASS")                # FIREWALL only
        self.assertEqual(sent["CTRL-LOGGING"]["status"], "FAIL")                  # TIME_SYNC failed
        self.assertEqual(sent["CTRL-AGENT-COVERAGE"]["status"], "PASS")           # 2 of 2 reporting
        self.assertNotIn("CTRL-MFA", sent)                                         # never observable -> not sent
        payload, _ = self.platform.received[-1]
        self.assertIn("MFA", [u["control"] for u in payload["unmapped"]])
        self.assertEqual(payload["company"]["platform_company_id"], "CO-platform1")

    def test_any_failing_source_fails_the_platform_control(self):
        self.report("KAL-LT01", {"FIREWALL": "PASS", "REMOTE_ACCESS": "FAIL"})
        self.report("KAL-LT02", {"FIREWALL": "PASS", "REMOTE_ACCESS": "FAIL"})
        sent = {c["platform_control_id"]: c for c in self.sync()["controls"]}
        self.assertEqual(sent["CTRL-SECCONFIG"]["status"], "FAIL")
        self.assertEqual({s["control"] for s in sent["CTRL-SECCONFIG"]["sources"]}, {"FIREWALL", "REMOTE_ACCESS"})


class PushBehaviour(LinkedBase):
    def test_signed_sequenced_and_only_on_change(self):
        self.healthy("KAL-LT01")
        self.healthy("KAL-LT02")
        first = self.sync()
        self.assertTrue(first["ok"])
        payload, sig = self.platform.received[0]
        self.assertTrue(sig.startswith("v1=") and payload["schema"] == pl.SCHEMA_ID)
        self.assertFalse(self.sync()["pushed"])                    # nothing changed
        self.report("KAL-LT02", {"EDR": "FAIL"})
        second = self.sync()
        self.assertTrue(second["pushed"])
        self.assertEqual(second["seq"], first["seq"] + 1)
        edr = next(c for c in second["controls"] if c["platform_control_id"] == "CTRL-EDR")
        self.assertEqual((edr["status"], edr["failing_hosts"][0]["host"]), ("FAIL", "KAL-LT02"))

    def test_heartbeat_push_without_changes(self):
        self.healthy("KAL-LT01")
        self.sync()
        self.clock.t += timedelta(minutes=16)
        self.healthy("KAL-LT01")
        self.assertTrue(self.sync()["pushed"])

    def test_failed_push_is_retried(self):
        self.healthy("KAL-LT01")
        self.platform.fail_next = True
        out = self.sync()
        self.assertFalse(out["ok"])
        conn = self.app.conn()
        st = conn.execute("SELECT * FROM platform_state WHERE company_id=?", (self.cid,)).fetchone()
        self.assertEqual(st["last_ok"], 0)
        self.assertIn("UNREACHABLE", st["last_error"])
        conn.close()
        self.assertTrue(self.sync()["ok"])                         # retried on the next cycle

    def test_silent_host_pushed_as_failure_without_any_new_report(self):
        self.healthy("KAL-LT01")
        self.report("KAL-LT02", {"EDR": "FAIL"})                  # LT02 is failing EDR ...
        self.sync()
        self.clock.t += timedelta(hours=73)
        self.healthy("KAL-LT01")                                   # ... and then goes quiet
        sent = {c["platform_control_id"]: c for c in self.sync()["controls"]}
        self.assertEqual(sent["CTRL-EDR"]["status"], "FAIL")
        self.assertIn("last result was FAIL", sent["CTRL-EDR"]["reason"])
        self.assertEqual(sent["CTRL-AGENT-COVERAGE"]["status"], "FAIL")

    def test_silent_host_that_was_passing_is_left_out_then_fails(self):
        self.healthy("KAL-LT01")
        self.healthy("KAL-LT02")
        self.sync()
        self.clock.t += timedelta(hours=73)
        self.healthy("KAL-LT01")                                   # LT02 quiet, last result PASS
        sent = {c["platform_control_id"]: c for c in self.sync()["controls"]}
        self.assertEqual((sent["CTRL-EDR"]["status"], sent["CTRL-EDR"]["observed"]), ("PASS", 1))
        self.assertEqual(sent["CTRL-AGENT-COVERAGE"]["status"], "FAIL")   # coverage still counts it
        self.clock.t += timedelta(days=12)
        self.healthy("KAL-LT01")
        sent = {c["platform_control_id"]: c for c in self.sync()["controls"]}
        self.assertEqual(sent["CTRL-EDR"]["status"], "FAIL")


class PlatformIsTheAuthority(LinkedBase):
    def test_collector_shows_platform_states_and_runs_no_state_machine(self):
        self.healthy("KAL-LT01")
        self.report("KAL-LT02", {"EDR": "FAIL"})
        self.sync()
        from kyh_collector import evaluate as ev
        conn = self.app.conn()
        snap = ev.evaluate_company(conn, self.cid, self.clock(), self.app.settings)
        self.assertTrue(snap["linked"])
        self.assertEqual([(w["platform_control_id"], w["state"]) for w in snap["warranties"]],
                         [("CTRL-EDR", "IN_GRACE")])
        self.assertTrue(snap["warranties"][0]["from_platform"])
        self.assertEqual(snap["policy"]["bound_premium_inr"], 245000)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM warranties").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM warranty_events").fetchone()[0], 0)
        conn.close()

    def test_binding_on_the_collector_is_refused(self):
        conn = self.app.conn()
        with self.assertRaises(core.ApiError) as e:
            core.bind_policy(conn, T0, self.cid, 1, self.app.settings)
        self.assertEqual(e.exception.code, "LINKED_TO_PLATFORM")
        conn.close()

    def test_link_file_is_private(self):
        path = pl.save_link(self.d, **{k: LINK[k] for k in ("url", "collector_id", "secret")})
        if os.name != "nt":  # Windows has no POSIX mode bits; os.stat reports 0o666 whatever the ACL is
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(pl.load_link(self.d)["collector_id"], "COL-test")


if __name__ == "__main__":
    unittest.main()
