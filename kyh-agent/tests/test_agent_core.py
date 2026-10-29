"""Agent internals: policy safety, runner failure handling, signing, integrity, outbox, scheduling."""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import _paths  # noqa: F401
from kyh_agent import config as config_mod
from kyh_agent import policy as policy_mod
from kyh_agent.agent import Agent, fingerprint
from kyh_agent.checks import base
from kyh_agent.checks.base import NeedsPrivilege, Outcome, ToolMissing
from kyh_agent.runner import Context, Runner
from kyh_agent.security import build_hash, sign, verify
from kyh_agent.spool import Spool
from kyh_agent.transport import Transport, TransportError

POL = policy_mod.load()


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def const_registry(outcomes: dict):
    """Registry whose checks return fixed outcomes (mutable dict so tests can change them)."""
    return {cid: {"linux": (lambda p, ctx, _c=cid: outcomes.get(_c, Outcome("PASS", "ok")))} for cid in POL.by_id}


class PolicySafety(unittest.TestCase):
    def test_shipped_policy_valid_and_hash_stable(self):
        self.assertEqual(policy_mod.load().hash, POL.hash)
        self.assertEqual(len(POL.checks), 12)

    def test_policy_cannot_add_new_checks(self):
        doc = copy.deepcopy(POL.doc)
        doc["checks"].append({"id": "custom.run_this", "control": "X", "tier": "important"})
        with self.assertRaisesRegex(policy_mod.PolicyError, "cannot introduce new checks"):
            policy_mod.validate(doc)

    def test_bad_tier_and_interval_rejected(self):
        doc = copy.deepcopy(POL.doc)
        doc["checks"][0]["tier"] = "vip"
        self.assertRaises(policy_mod.PolicyError, policy_mod.validate, doc)
        doc = copy.deepcopy(POL.doc)
        doc["checks"][0]["interval_minutes"] = 1
        self.assertRaises(policy_mod.PolicyError, policy_mod.validate, doc)

    def test_params_must_be_plain_data(self):
        doc = copy.deepcopy(POL.doc)
        doc["checks"][0]["params"]["x"] = object()
        self.assertRaises(policy_mod.PolicyError, policy_mod.validate, doc)

    def test_every_check_has_all_three_platforms(self):
        from kyh_agent.checks import REGISTRY
        for cid, impls in REGISTRY.items():
            self.assertEqual(set(impls), {"linux", "windows", "darwin"}, cid)


class RunnerFailureModes(unittest.TestCase):
    def _run(self, fn):
        reg = {cid: {"linux": fn} for cid in POL.by_id}
        return Runner(POL, platform="linux", registry=reg).run_one("edr.running_healthy")

    def test_privilege_error_is_not_supported(self):
        def f(p, c):
            raise NeedsPrivilege("need root")
        r = self._run(f)
        self.assertEqual(r.status, "NOT_SUPPORTED")
        self.assertTrue(r.evidence["requires_admin"])

    def test_missing_tool(self):
        def f(p, c):
            raise ToolMissing("lsblk")
        self.assertEqual(self._run(f).status, "NOT_SUPPORTED")

    def test_command_timeout_is_error(self):
        def f(p, c):
            raise subprocess.TimeoutExpired(["apt-get"], 5)
        self.assertEqual(self._run(f).status, "ERROR")

    def test_crash_is_error_not_exception(self):
        def f(p, c):
            return 1 / 0
        r = self._run(f)
        self.assertEqual(r.status, "ERROR")
        self.assertIn("ZeroDivisionError", r.summary)

    def test_hung_check_is_abandoned(self):
        with mock.patch.object(Runner, "SLACK_SECONDS", 0):
            out = Runner._guarded(lambda p, c: time.sleep(3), {}, None, 0.2)
        self.assertEqual(out.status, "ERROR")

    def test_result_shape(self):
        r = self._run(lambda p, c: Outcome("PASS", "fine", "OPERATING", {"a": 1}, "m"))
        d = r.to_dict()
        for k in ("check_id", "control", "tier", "status", "assurance", "evidence", "observed_at", "platform"):
            self.assertIn(k, d)
        self.assertEqual((d["control"], d["tier"]), ("EDR", "warranty"))


class SafeCommands(unittest.TestCase):
    def test_string_commands_refused(self):
        with self.assertRaises(ValueError):
            base.run_cmd("rm -rf /")

    def test_never_uses_shell(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            base.run_cmd(["echo", "hi"], timeout=3)
        kwargs = run.call_args.kwargs
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 3)
        self.assertEqual(kwargs["env"]["LC_ALL"], "C")

    def test_missing_binary_maps_to_toolmissing(self):
        with self.assertRaises(ToolMissing):
            base.run_cmd(["definitely-not-a-real-binary-kyh"])


class SigningAndIntegrity(unittest.TestCase):
    secret = "ab" * 32

    def test_roundtrip_and_tamper(self):
        body = b'{"seq":1}'
        sig = sign(self.secret, body)
        self.assertTrue(verify(self.secret, body, sig))
        self.assertFalse(verify(self.secret, b'{"seq":2}', sig))
        self.assertFalse(verify("cd" * 32, body, sig))
        self.assertFalse(verify(self.secret, body, sig[3:]))

    def test_build_hash_detects_modification(self):
        pkg = os.path.dirname(os.path.abspath(policy_mod.__file__))
        with tempfile.TemporaryDirectory() as d:
            copy_dir = os.path.join(d, "kyh_agent")
            shutil.copytree(pkg, copy_dir, ignore=shutil.ignore_patterns("__pycache__"))
            self.assertEqual(build_hash(copy_dir), build_hash(pkg))
            with open(os.path.join(copy_dir, "checks", "verdicts.py"), "a") as fh:
                fh.write("\n# always PASS\n")
            self.assertNotEqual(build_hash(copy_dir), build_hash(pkg))

    def test_build_hash_ignores_line_endings(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for folder, data in ((a, b"a = 1\nb = 2\n"), (b, b"a = 1\r\nb = 2\r\n")):
                with open(os.path.join(folder, "x.py"), "wb") as fh:
                    fh.write(data)
            self.assertEqual(build_hash(a), build_hash(b))

    def test_account_names_are_salted_hashes(self):
        a, b = Context(datetime.now(timezone.utc), "agent1"), Context(datetime.now(timezone.utc), "agent2")
        self.assertEqual(a.hash_id("alice"), a.hash_id("alice"))
        self.assertNotEqual(a.hash_id("alice"), b.hash_id("alice"))
        self.assertNotIn("alice", a.hash_id("alice"))


class Outbox(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)  # cleanups run last-in first-out, so this runs after the closes
        self.path = os.path.join(self.d, "outbox.db")

    def spool(self, **kw):
        s = Spool(self.path, **kw)
        self.addCleanup(s.close)  # Windows cannot delete an open database file
        return s

    def test_sequence_survives_restart(self):
        s = Spool(self.path)
        self.assertEqual([s.next_seq(), s.next_seq()], [1, 2])
        s.close()
        self.assertEqual(self.spool().next_seq(), 3)

    def test_fifo_ack_and_dead_letter(self):
        s = self.spool()
        for i in (1, 2, 3):
            s.put(i, "delta", "t", b"x")
        self.assertEqual([r[0] for r in s.pending()], [1, 2, 3])
        s.ack(1)
        s.dead_letter(2, 400, "bad")
        self.assertEqual([r[0] for r in s.pending()], [3])
        self.assertEqual(s.db.execute("SELECT COUNT(*) FROM dead_letter").fetchone()[0], 1)

    def test_cap_drops_heartbeats_before_snapshots(self):
        s = self.spool(max_rows=3)
        s.put(1, "full", "t", b"x")
        s.put(2, "heartbeat", "t", b"x")
        s.put(3, "delta", "t", b"x")
        s.put(4, "heartbeat", "t", b"x")
        kinds = [r[1] for r in s.pending()]
        self.assertEqual(kinds.count("full"), 1)
        self.assertEqual(len(kinds), 3)
        self.assertEqual([r[0] for r in s.pending()], [1, 3, 4])


class FakeTransport:
    def __init__(self, responses=None):
        self.sent = []
        self.responses = responses or []

    def post(self, path, body, headers=None):
        self.sent.append((path, json.loads(body), headers))
        if self.responses:
            r = self.responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        return 202, {"accepted": True}


class Scheduling(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)  # runs after each agent's close() (cleanups are LIFO)
        self.cfg = config_mod.Config(agent_id="ag_test", agent_secret="ab" * 32, server_url="http://localhost")
        self.clock = Clock(datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc))
        self.outcomes = {}
        self.tx = FakeTransport()

    def agent(self, **kw):
        a = Agent(self.cfg, POL, self.d, transport=self.tx, clock=self.clock, platform="linux",
                  registry=const_registry(self.outcomes), **kw)
        self.addCleanup(a.close)
        return a

    def test_first_scan_is_full_then_only_changes_are_sent(self):
        a = self.agent()
        self.assertEqual(a.scan()["kind"], "full")
        self.assertIsNone(a.scan()["kind"])                    # nothing due yet
        self.clock.advance(minutes=70)                          # EDR interval is 60 min (+/-10% jitter)
        self.assertIsNone(a.scan()["kind"])                    # EDR re-ran but unchanged -> nothing sent
        self.outcomes["edr.running_healthy"] = Outcome("FAIL", "No EDR", "ABSENT")
        self.clock.advance(minutes=70)
        out = a.scan()
        self.assertEqual((out["kind"], out["sent"]), ("delta", 1))
        a.flush()
        last = self.tx.sent[-1][1]
        self.assertEqual(last["kind"], "delta")
        self.assertEqual([r["check_id"] for r in last["results"]], ["edr.running_healthy"])

    def test_scan_now_runs_only_the_named_control_at_once(self):
        from kyh_agent.agent import SCAN_REQUEST, request_scan
        a = self.agent()
        a.tick()                                                # first full report
        self.outcomes["firewall.enabled"] = Outcome("FAIL", "Host firewall is disabled", "ABSENT")
        self.assertIsNone(a.tick()["kind"])                    # firewall runs daily: change not seen yet
        request_scan(self.d, ["firewall"])
        out = a.tick()
        self.assertEqual((out["kind"], out["ran"], out["sent"]), ("delta", 1, 1))
        self.assertFalse(os.path.exists(os.path.join(self.d, SCAN_REQUEST)))   # request consumed once
        self.assertEqual(self.tx.sent[-1][1]["results"][0]["status"], "FAIL")
        self.assertIsNone(a.tick()["kind"])

    def test_scan_now_without_controls_sends_full_snapshot(self):
        from kyh_agent.agent import request_scan
        a = self.agent()
        a.tick()
        request_scan(self.d)
        out = a.tick()
        self.assertEqual((out["kind"], out["ran"]), ("full", 12))

    def test_scan_now_cli_rejects_unknown_control(self):
        from kyh_agent.__main__ import main
        with mock.patch("sys.stderr"):
            self.assertEqual(main(["--state-dir", self.d, "--config", os.path.join(self.d, "c.json"),
                                   "scan-now", "--control", "TELEPATHY"]), 1)
        with mock.patch("sys.stdout"):
            self.assertEqual(main(["--state-dir", self.d, "--config", os.path.join(self.d, "c.json"),
                                   "scan-now", "--control", "edr"]), 0)
        with open(os.path.join(self.d, "scan-now.json")) as fh:
            self.assertEqual(json.load(fh)["controls"], ["EDR"])

    def test_full_snapshot_repeats_daily(self):
        a = self.agent()
        a.scan()
        self.clock.advance(hours=27)
        self.assertEqual(a.scan()["kind"], "full")

    def test_jitter_within_ten_percent(self):
        a = self.agent()
        a.scan()
        nd = datetime.fromisoformat(a.state["next_due"]["edr.running_healthy"].replace("Z", "+00:00"))
        minutes = (nd - self.clock()).total_seconds() / 60
        self.assertTrue(54 <= minutes <= 66, minutes)

    def test_heartbeat_interval(self):
        a = self.agent()
        self.assertTrue(a.heartbeat_if_due())
        self.assertFalse(a.heartbeat_if_due())
        self.clock.advance(minutes=16)
        self.assertTrue(a.heartbeat_if_due())

    def test_signed_envelope_contents(self):
        a = self.agent()
        a.scan()
        a.flush()
        path, env, headers = self.tx.sent[0]
        self.assertEqual(path, "/api/v1/report")
        self.assertEqual(headers["X-KYH-Agent-Id"], "ag_test")
        self.assertTrue(headers["X-KYH-Signature"].startswith("v1="))
        self.assertEqual(env["schema_version"], 2)
        self.assertEqual(env["policy"]["hash"], POL.hash)
        self.assertEqual(env["agent"]["build_hash"], build_hash())
        self.assertFalse(env["simulated"])

    def test_offline_then_replay_in_order(self):
        self.tx.responses = [TransportError("connection refused")]
        a = self.agent()
        a.scan()
        a.heartbeat_if_due()
        stats = a.flush()
        self.assertEqual((stats["sent"], stats["remaining"]), (0, 2))
        self.assertGreaterEqual(a.backoff, 30)
        stats = a.flush()
        self.assertEqual((stats["sent"], stats["remaining"]), (2, 0))
        self.assertEqual([s[1]["seq"] for s in self.tx.sent[1:]], [1, 2])

    def test_rejections(self):
        self.tx.responses = [(409, {"code": "REPLAY"}), (401, {"code": "BAD_SIGNATURE"})]
        a = self.agent()
        a.scan()
        a.heartbeat_if_due()
        stats = a.flush()
        self.assertEqual((stats["sent"], stats["rejected"], stats["remaining"]), (1, 1, 0))

    def test_simulation_is_always_labelled(self):
        a = Agent(self.cfg, POL, self.d, transport=self.tx, clock=self.clock, platform="linux", simulate="edr_down")
        self.addCleanup(a.close)
        a.scan()
        a.flush()
        env = self.tx.sent[0][1]
        self.assertTrue(env["simulated"])
        edr = next(r for r in env["results"] if r["check_id"] == "edr.running_healthy")
        self.assertEqual(edr["status"], "FAIL")
        self.assertTrue(all(r["evidence"]["simulated"] and r["summary"].startswith("[SIMULATED]")
                            for r in env["results"]))

    def test_transparency_log_written(self):
        a = self.agent()
        a.scan()
        with open(os.path.join(self.d, "sent.jsonl")) as fh:
            line = json.loads(fh.readline())
        self.assertEqual(line["kind"], "full")
        self.assertEqual(len(line["results"]), 12)

    def test_fingerprint_ignores_timestamps(self):
        r = {"status": "PASS", "assurance": None, "summary": "x", "observed_at": "a"}
        self.assertEqual(fingerprint(r), fingerprint(dict(r, observed_at="b", duration_ms=9)))

    def test_config_file_is_private(self):
        cfg = config_mod.Config(agent_secret="s")
        cfg.path = os.path.join(self.d, "cfg", "config.json")
        config_mod.save(cfg)
        self.assertTrue(os.path.isfile(cfg.path))
        if os.name != "nt":  # Windows has no POSIX mode bits; os.stat reports 0o666 whatever the ACL is
            self.assertEqual(os.stat(cfg.path).st_mode & 0o777, 0o600)


class TransportPolicy(unittest.TestCase):
    def test_private_addresses_bypass_system_proxy(self):
        from kyh_agent.transport import direct_route
        for h in ("localhost", "127.0.0.1", "192.168.56.1", "10.0.2.2", "172.16.4.9", "::1"):
            self.assertTrue(direct_route(h), h)
        for h in ("collector.kyh.in", "8.8.8.8"):
            self.assertFalse(direct_route(h), h)

    def test_plain_http_only_to_localhost(self):
        Transport("http://127.0.0.1:8443")
        with self.assertRaises(ValueError):
            Transport("http://collector.example.in")
        Transport("http://collector.example.in", allow_insecure_http=True)


if __name__ == "__main__":
    unittest.main()
