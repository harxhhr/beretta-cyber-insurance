"""End to end over real HTTPS: collector in a thread, agent with a pinned private CA."""
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import _paths  # noqa: F401
from kyh_agent import config as config_mod
from kyh_agent import policy as policy_mod
from kyh_agent.agent import Agent, enroll
from kyh_agent.security import build_hash
from kyh_agent.transport import Transport, TransportError
from kyh_collector import core
from kyh_collector.__main__ import gen_cert
from kyh_collector.server import make_server

HAVE_OPENSSL = shutil.which("openssl") is not None


@unittest.skipUnless(HAVE_OPENSSL, "openssl tool needed to mint test certificates")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.tls = gen_cert(os.path.join(cls.d, "tls"), ["localhost", "127.0.0.1"])
        cls.httpd = make_server(os.path.join(cls.d, "data"), "127.0.0.1", 0, cls.tls["cert"], cls.tls["key"])
        cls.url = f"https://localhost:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        app = cls.httpd.app
        conn = app.conn()
        now = app.clock()
        cls.admin = core.create_admin_token(conn, now)
        cls.cid = core.add_company(conn, now, "Kalinga Components", 2, demo=True)
        cls.enr = core.issue_enrollment_token(conn, now, cls.cid)
        core.approve(conn, now, "approved_builds", build_hash(), "test build")
        core.approve(conn, now, "approved_policies", policy_mod.load().hash, "baseline")
        core.bind_policy(conn, now, cls.cid, 245000, app.settings)
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.d)

    def new_agent(self, name, simulate):
        state = os.path.join(self.d, name)
        cfg = config_mod.load(os.path.join(state, "config.json"))
        pol = policy_mod.load()
        enroll(cfg, self.url, self.enr, self.tls["ca"], pol, hostname=name)
        agent = Agent(cfg, pol, state, simulate=simulate)
        self.addCleanup(agent.close)
        return agent

    def get(self, path, token=None):
        req = urllib.request.Request(self.url + path)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        ctx = Transport(self.url, self.tls["ca"]).ctx
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def test_1_full_flow_over_tls(self):
        a = self.new_agent("KAL-LT01", "healthy")
        b = self.new_agent("KAL-LT02", "edr_down")
        for agent in (a, b):
            agent.scan(force_full=True)
            agent.heartbeat_if_due()
            stats = agent.flush()
            self.assertEqual((stats["sent"], stats["remaining"], stats["error"]), (2, 0, None))
        status, body, _ = self.get(f"/api/v1/companies/{self.cid}", self.admin)
        snap = json.loads(body)
        self.assertEqual(status, 200)
        states = {w["control"]: w["state"] for w in snap["warranties"]}
        self.assertEqual(states["EDR"], "IN_GRACE")
        self.assertEqual(states["PATCH"], "MET")
        self.assertEqual(states["MONITORING_COVERAGE"], "MET")
        self.assertEqual(snap["policy"]["bound_premium_inr"], 245000)

    def test_2_report_response_says_no_repricing(self):
        a = self.new_agent("KAL-LT03", "healthy")
        a.scan(force_full=True)
        body = a.spool.pending()[0][3]
        from kyh_agent.security import sign
        t = Transport(self.url, self.tls["ca"])
        status, resp = t.post("/api/v1/report", body, {"X-KYH-Agent-Id": a.cfg["agent_id"],
                                                        "X-KYH-Signature": sign(a.cfg["agent_secret"], body)})
        self.assertEqual(status, 202)
        self.assertIs(resp["repricing_performed"], False)
        status, resp = t.post("/api/v1/report", body, {"X-KYH-Agent-Id": a.cfg["agent_id"],
                                                        "X-KYH-Signature": sign(a.cfg["agent_secret"], body)})
        self.assertEqual((status, resp["code"]), (409, "REPLAY"))
        status, resp = t.post("/api/v1/report", body.replace(b"PASS", b"FAIL", 1),
                              {"X-KYH-Agent-Id": a.cfg["agent_id"], "X-KYH-Signature": sign("00" * 32, body)})
        self.assertEqual((status, resp["code"]), (401, "BAD_SIGNATURE"))

    def test_3_agent_refuses_a_collector_it_does_not_trust(self):
        other = gen_cert(os.path.join(self.d, "other-ca"), ["localhost"])
        t = Transport(self.url, other["ca"])  # pinned to a different CA -> must not connect
        with self.assertRaises(TransportError):
            t.post("/api/v1/report", b"{}")

    def test_4_dashboard_requires_admin_token(self):
        status, body, headers = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Beretta Live Monitoring", body)
        self.assertIn("default-src 'self'", headers.get("Content-Security-Policy", ""))
        self.assertEqual(self.get("/api/v1/overview")[0], 401)
        self.assertEqual(self.get("/api/v1/overview", "kyh_admin_wrong")[0], 401)
        status, body, _ = self.get("/api/v1/overview", self.admin)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["companies"][0]["company"]["name"], "Kalinga Components")

    def test_5_path_traversal_not_served(self):
        self.assertEqual(self.get("/static/../server.py")[0], 404)
        self.assertEqual(self.get("/../../etc/passwd")[0], 404)


if __name__ == "__main__":
    unittest.main()


class CertificatesPassStrictVerification(unittest.TestCase):
    """Python 3.13+ turns on VERIFY_X509_STRICT by default. Both certificate generators must pass it,
    on any Python version, or agents on a new Python refuse the collector (found on Python 3.14)."""

    def _handshake(self, paths):
        import socket
        import ssl
        sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        sctx.load_cert_chain(paths["cert"], paths["key"])
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)

        def serve():
            conn, _ = srv.accept()
            try:
                sctx.wrap_socket(conn, server_side=True).close()
            except (ssl.SSLError, OSError):
                pass
        threading.Thread(target=serve, daemon=True).start()
        cctx = ssl.create_default_context(cafile=paths["ca"])
        cctx.verify_flags |= ssl.VERIFY_X509_STRICT
        try:
            with cctx.wrap_socket(socket.create_connection(srv.getsockname()), server_hostname="192.168.56.1"):
                pass
        finally:
            srv.close()

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_openssl_certificates(self):
        from kyh_collector.__main__ import _gen_cert_openssl, find_openssl
        try:
            find_openssl()
        except FileNotFoundError:
            self.skipTest("openssl not installed")
        self._handshake(_gen_cert_openssl(os.path.join(self.d, "o"), ["192.168.56.1", "127.0.0.1"]))

    def test_cryptography_certificates(self):
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")
        from kyh_collector.__main__ import _gen_cert_python
        os.makedirs(os.path.join(self.d, "c"))
        paths = {k: os.path.join(self.d, "c", v) for k, v in
                 {"ca_key": "ca.key", "ca": "ca.pem", "key": "server.key", "cert": "server.pem"}.items()}
        _gen_cert_python(paths, ["192.168.56.1", "127.0.0.1"], 825)
        self._handshake(paths)
