"""Both systems running for real: agents -> collector -> KYH platform.

    python integration/test_linked_system.py

Checks the whole chain over HTTP: fleet evidence reaches the platform before bind and
feeds the quote; after bind, an endpoint failure moves the platform's warranty and the
premium stays exactly the same; the collector shows the platform's warranty state.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="kyh-linked-")
os.environ["KYH_DB"] = os.path.join(TMP, "platform", "kyh.db")
os.environ["KYH_SECRETS"] = os.path.join(TMP, "platform", "secrets.json")
sys.path[:0] = [os.path.join(ROOT, "kyh-cyber-insurance"), os.path.join(ROOT, "kyh-agent", "agent"),
                os.path.join(ROOT, "kyh-agent", "collector")]

from app.api import make_server as make_platform  # noqa: E402
from kyh_agent import config as agent_config  # noqa: E402
from kyh_agent import policy as agent_policy  # noqa: E402
from kyh_agent.agent import Agent, enroll  # noqa: E402
from kyh_agent.security import build_hash  # noqa: E402
from kyh_agent.simulate import registry_for  # noqa: E402
from kyh_collector import core, platform_link  # noqa: E402
from kyh_collector.server import make_server as make_collector  # noqa: E402


def http(method, url, body=None, headers=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def wait_for(fn, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.25)
    raise AssertionError("condition not reached in time")


class LinkedSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # ---- Part 1: KYH platform (seeds 3 demo companies; B = Kalinga Components)
        cls.platform = make_platform("127.0.0.1", 0)
        threading.Thread(target=cls.platform.serve_forever, daemon=True).start()
        cls.purl = f"http://127.0.0.1:{cls.platform.server_address[1]}"
        with open(os.environ["KYH_SECRETS"]) as fh:
            tok = json.load(fh)["role_tokens"]
        cls.admin, cls.uw = {"X-Auth-Token": tok["admin"]}, {"X-Auth-Token": tok["underwriter"]}
        with open(os.path.join(TMP, "platform", "demo_profiles.json")) as fh:
            cls.b = json.load(fh)["B"]

        # ---- register the collector on the platform and link company B
        st, reg = http("POST", cls.purl + "/api/admin/collectors", {"name": "KYH collector"}, cls.admin)
        assert st == 200, reg
        st, _ = http("POST", f"{cls.purl}/api/admin/collectors/{reg['collector_id']}/links",
                     {"company_id": cls.b["company_id"], "collector_company_id": "co_kalinga"}, cls.admin)
        assert st == 200

        # ---- Part 2: collector, linked
        cdata = os.path.join(TMP, "collector")
        os.makedirs(cdata)
        with open(os.path.join(cdata, "settings.json"), "w") as fh:
            json.dump({"push_interval_seconds": 1, "coverage_onboarding_days": 0}, fh)
        platform_link.save_link(cdata, cls.purl, reg["collector_id"], reg["secret"], dashboard_url="http://collector")
        cls.collector = make_collector(cdata, "127.0.0.1", 0)
        threading.Thread(target=cls.collector.serve_forever, daemon=True).start()
        cls.curl = f"http://127.0.0.1:{cls.collector.server_address[1]}"
        app = cls.collector.app
        conn = app.conn()
        now = app.clock()
        cls.cadmin = {"Authorization": "Bearer " + core.create_admin_token(conn, now)}
        core.add_company(conn, now, "Kalinga Components Ltd", 4, "Manufacturing", True, "co_kalinga")
        enr = core.issue_enrollment_token(conn, now, "co_kalinga", 10)
        core.approve(conn, now, "approved_builds", build_hash(), "test")
        core.approve(conn, now, "approved_policies", agent_policy.load().hash, "test")
        platform_link.link_company(conn, now, "co_kalinga", cls.b["company_id"])
        conn.close()

        # ---- four simulated endpoints
        cls.agents = {}
        pol = agent_policy.load()
        for h in ("KAL-FIN-LT01", "KAL-HR-LT02", "KAL-PLANT-WS03", "KAL-SRV-ERP01"):
            state = os.path.join(TMP, "agents", h)
            cfg = agent_config.load(os.path.join(state, "config.json"))
            enroll(cfg, cls.curl, enr, None, pol, hostname=h)
            ag = Agent(cfg, pol, state, simulate="healthy", platform="windows")
            ag.scan(force_full=True)
            ag.flush()
            cls.agents[h] = ag

    @classmethod
    def tearDownClass(cls):
        cls.collector.app.worker.stop()
        cls.collector.shutdown()
        cls.platform.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)

    def set_profile(self, host, profile):
        ag = self.agents[host]
        ag.simulate = profile
        ag.runner.registry = registry_for(profile, ag.platform)
        ag.scan(force_full=True)
        self.assertEqual(ag.flush()["error"], None)

    def warranty(self, control):
        st, w = http("GET", f"{self.purl}/api/policies/{self.b['policy_id']}/warranties", headers=self.uw)
        return {x["control_id"]: x["state"] for x in w["warranties"]}.get(control)

    def test_full_chain(self):
        # 1. fleet evidence arrives at the platform before bind
        def fleet_ready():
            f = http("GET", f"{self.purl}/api/companies/{self.b['company_id']}/fleet", headers=self.uw)[1]["fleet"]
            return f if f and f["fleet"]["reporting"] == 4 else None
        fleet = wait_for(fleet_ready)
        self.assertEqual(fleet["fleet"]["reporting"], 4)
        sent = {c["platform_control_id"]: c["value"] for c in fleet["controls"]}
        self.assertEqual((sent["CTRL-EDR"], sent["CTRL-BACKUP-TESTED"]), ("true", "partial"))
        self.assertNotIn("CTRL-MFA", sent)

        # 2. the quote uses it as TECHNICALLY_OBSERVED fleet evidence; then bind
        st, q = http("POST", self.purl + "/api/quote", {"policy_id": self.b["policy_id"]}, self.uw)
        self.assertEqual(st, 200, q)
        self.assertEqual(q["model_version"], "UNDERWRITING_MODEL_V2")
        edr = q["evidence"]["CTRL-EDR"]
        self.assertEqual((edr["source_type"], edr["evidence_strength"]), ("AGENT_FLEET", "TECHNICALLY_OBSERVED"))
        self.assertEqual(q["statuses"]["CTRL-EDR"], "VERIFIED")            # fleet evidence verifies EDR
        self.assertEqual(q["statuses"]["CTRL-BACKUP-TESTED"], "STATED")    # recent backup, restore untested
        st, bound = http("POST", self.purl + "/api/policies/bind",
                         {"policy_id": self.b["policy_id"], "calculation_id": q["calculation_id"]}, self.uw)
        self.assertEqual(st, 200, bound)
        premium = bound["bound_premium"]
        self.assertEqual(self.warranty("CTRL-EDR"), "MET")

        # 3. EDR stops on one machine -> platform warranty IN_GRACE, premium unchanged
        self.set_profile("KAL-PLANT-WS03", "edr_down")
        wait_for(lambda: self.warranty("CTRL-EDR") == "IN_GRACE")
        st, pol = http("GET", f"{self.purl}/api/policies/{self.b['policy_id']}", headers=self.uw)
        self.assertEqual(pol["policy"]["bound_premium"], premium)

        # 4. the collector dashboard shows the platform's state, not its own
        def collector_view():
            st, snap = http("GET", self.curl + "/api/v1/companies/co_kalinga", headers=self.cadmin)
            ws = {w["platform_control_id"]: w["state"] for w in snap["warranties"]}
            return snap if ws.get("CTRL-EDR") == "IN_GRACE" else None
        snap = wait_for(collector_view)
        self.assertTrue(snap["linked"])
        self.assertEqual(snap["policy"]["bound_premium_inr"], premium)

        # 5. fixed -> REMEDIATED -> MET on the platform (its own rules)
        self.set_profile("KAL-PLANT-WS03", "healthy")
        wait_for(lambda: self.warranty("CTRL-EDR") == "MET")
        st, ev = http("GET", f"{self.purl}/api/policies/{self.b['policy_id']}/warranty-events", headers=self.uw)
        path = [e["to_state"] for e in sorted(ev["events"], key=lambda e: e["at"]) if e["control_id"] == "CTRL-EDR"]
        self.assertEqual(path, ["MET", "IN_GRACE", "REMEDIATED", "MET"])
        st, pol = http("GET", f"{self.purl}/api/policies/{self.b['policy_id']}", headers=self.uw)
        self.assertEqual(pol["policy"]["bound_premium"], premium)


if __name__ == "__main__":
    unittest.main(verbosity=2)
