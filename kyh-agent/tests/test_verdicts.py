"""Verdicts: the decision rules that turn facts + thresholds into PASS/FAIL."""
import unittest
from datetime import datetime, timedelta, timezone

import _paths  # noqa: F401
from kyh_agent import policy as policy_mod
from kyh_agent.checks import verdicts as V

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
POL = policy_mod.load()


def params(check_id):
    return POL.by_id[check_id]["params"]


class Patching(unittest.TestCase):
    p = params("patch.security_updates")

    def test_nothing_pending_passes(self):
        self.assertEqual(V.patching({"pending_security": 0}, self.p, NOW, "t").status, "PASS")

    def test_pending_but_inside_cycle_passes(self):
        o = V.patching({"pending_security": 3, "last_update": NOW - timedelta(days=5)}, self.p, NOW, "t")
        self.assertEqual(o.status, "PASS")

    def test_window_is_seven_days_as_priced(self):
        # Pricing V2 prices CTRL-PATCH-CRIT on "critical CVEs patched within 7 days" (Marsh 2023).
        self.assertEqual(self.p["max_patch_age_days"], 7)
        o = V.patching({"pending_security": 3, "last_update": NOW - timedelta(days=10)}, self.p, NOW, "t")
        self.assertEqual(o.status, "FAIL")

    def test_pending_and_overdue_fails(self):
        o = V.patching({"pending_security": 3, "last_update": NOW - timedelta(days=45)}, self.p, NOW, "t")
        self.assertEqual((o.status, o.assurance), ("FAIL", "PRESENT"))
        self.assertIn("45.0 days ago", o.summary)

    def test_stale_package_index_is_not_trusted(self):
        o = V.patching({"pending_security": 0, "index_age_days": 40}, self.p, NOW, "t")
        self.assertEqual(o.status, "FAIL")

    def test_unknown_pending_and_overdue_fails(self):
        o = V.patching({"pending_security": None, "last_update": NOW - timedelta(days=50)}, self.p, NOW, "t")
        self.assertEqual(o.status, "FAIL")
        self.assertIn("could not be listed", o.summary)


class Edr(unittest.TestCase):
    p = params("edr.running_healthy")
    fresh = {"service_enabled": True, "antivirus_enabled": True, "realtime_enabled": True,
             "signature_age_days": 1, "running_mode": "Normal"}

    def test_defender_healthy_is_operating(self):
        o = V.edr({"msmpeng": "Microsoft Defender Antivirus"}, self.fresh, self.p, "t")
        self.assertEqual((o.status, o.assurance), ("PASS", "OPERATING"))

    def test_stale_signatures_are_PRESENT_not_OPERATING(self):
        o = V.edr({"msmpeng": "Microsoft Defender Antivirus"}, dict(self.fresh, signature_age_days=9), self.p, "t")
        self.assertEqual((o.status, o.assurance), ("FAIL", "PRESENT"))

    def test_realtime_off_fails(self):
        self.assertEqual(V.edr({}, dict(self.fresh, realtime_enabled=False), self.p, "t").status, "FAIL")

    def test_passive_defender_without_third_party_fails(self):
        self.assertEqual(V.edr({}, dict(self.fresh, running_mode="Passive Mode"), self.p, "t").status, "FAIL")

    def test_third_party_edr_process_is_RUNNING(self):
        o = V.edr({"csfalconservice": "CrowdStrike Falcon"}, dict(self.fresh, running_mode="Passive Mode"), self.p, "t")
        self.assertEqual((o.status, o.assurance), ("PASS", "RUNNING"))

    def test_nothing_running_is_absent(self):
        self.assertEqual(V.edr({}, None, self.p, "t").assurance, "ABSENT")

    def test_vendor_health_unhealthy_overrides_process(self):
        o = V.edr({"wdavdaemon": "MDE"}, None, self.p, "t", health={"product": "MDE", "healthy": False})
        self.assertEqual((o.status, o.assurance), ("FAIL", "PRESENT"))


class Backup(unittest.TestCase):
    p = params("backup.recent_success")

    def test_recent(self):
        o = V.backup(NOW - timedelta(days=2), "marker", [], self.p, NOW, "t")
        self.assertEqual(o.status, "PASS")
        self.assertFalse(o.evidence["restore_test_verified"])

    def test_old(self):
        self.assertEqual(V.backup(NOW - timedelta(days=12), "marker", [], self.p, NOW, "t").status, "FAIL")

    def test_software_without_timestamp_is_not_supported(self):
        o = V.backup(None, None, ["veeam.endpoint.service"], self.p, NOW, "t")
        self.assertEqual((o.status, o.assurance), ("NOT_SUPPORTED", "PRESENT"))

    def test_no_evidence_is_not_a_fail(self):
        self.assertEqual(V.backup(None, None, [], self.p, NOW, "t").status, "NOT_SUPPORTED")


class Hygiene(unittest.TestCase):
    def test_mfa_is_never_claimed(self):
        self.assertEqual(V.mfa().status, "NOT_SUPPORTED")

    def test_exposed_telnet_fails_rdp_is_review(self):
        p = params("network.exposed_services")
        self.assertEqual(V.exposed_services([("0.0.0.0", 23)], p, "t").status, "FAIL")
        o = V.exposed_services([("0.0.0.0", 3389), ("127.0.0.1", 6379)], p, "t")
        self.assertEqual(o.status, "PASS")
        self.assertEqual([r["port"] for r in o.evidence["review"]], [3389])

    def test_allow_list(self):
        p = dict(params("network.exposed_services"), allow_ports=[23])
        self.assertEqual(V.exposed_services([("0.0.0.0", 23)], p, "t").status, "PASS")

    def test_ssh(self):
        p = params("remote.access_hardening")
        self.assertEqual(V.ssh_hardening({"permitrootlogin": "yes", "passwordauthentication": "no"}, p, "t").status,
                         "FAIL")
        self.assertEqual(V.ssh_hardening({"permitrootlogin": "no", "passwordauthentication": "no"}, p, "t").status,
                         "PASS")

    def test_rdp(self):
        self.assertEqual(V.rdp_hardening(False, False, "t").status, "NOT_APPLICABLE")
        self.assertEqual(V.rdp_hardening(True, False, "t").status, "FAIL")
        self.assertEqual(V.rdp_hardening(True, True, "t").status, "PASS")

    def test_admins(self):
        p = params("accounts.local_admins")
        self.assertEqual(V.admin_accounts(5, [], 0, False, p, "t").status, "FAIL")
        self.assertEqual(V.admin_accounts(1, [], 0, True, p, "t").status, "FAIL")
        self.assertEqual(V.admin_accounts(2, ["a1b2"], 0, False, p, "t").status, "PASS")

    def test_disk(self):
        self.assertEqual(V.disk_encryption(True, {}, "t", suspended=True).status, "FAIL")


class OsSupport(unittest.TestCase):
    p = params("os.vendor_support")

    def test_ubuntu_2004_is_past_eol(self):
        self.assertEqual(V.os_support("Ubuntu 20.04", self.p["eol"]["linux"]["ubuntu:20.04"], self.p, NOW, "t").status,
                         "FAIL")

    def test_windows_11_24h2_close_to_eol_warns_but_passes(self):
        o = V.os_support("Windows 11 24H2", self.p["eol"]["windows"]["client"]["26100"], self.p, NOW, "t")
        self.assertEqual(o.status, "PASS")
        self.assertIn("support ends", o.summary)
        self.assertEqual(o.evidence["days_to_end_of_support"], 13)

    def test_windows_11_26h2_supported_on_both_tables(self):
        w = self.p["eol"]["windows"]
        self.assertEqual((w["client"]["26300"], w["client_enterprise"]["26300"]), ("2028-10-10", "2029-10-09"))
        self.assertEqual(V.os_support("Windows 11 26H2", w["client_enterprise"]["26300"], self.p, NOW, "t").status,
                         "PASS")

    def test_unknown_os(self):
        self.assertEqual(V.os_support("Plan9", None, self.p, NOW, "t", known=False).status, "NOT_SUPPORTED")


class CertIn(unittest.TestCase):
    def test_log_retention(self):
        p = params("logging.retention")
        self.assertEqual(V.log_retention(True, "Wazuh", None, p, "t").assurance, "RUNNING")
        self.assertEqual(V.log_retention(True, None, 200, p, "t").status, "PASS")
        self.assertEqual(V.log_retention(True, None, 30, p, "t").status, "FAIL")
        self.assertEqual(V.log_retention(False, "Wazuh", 400, p, "t").status, "FAIL")

    def test_time_sync(self):
        p = params("time.sync_source")
        self.assertEqual(V.time_sync(True, ["samay1.nic.in"], p, "t").status, "PASS")
        self.assertEqual(V.time_sync(True, ["time.windows.com"], p, "t").status, "FAIL")
        self.assertEqual(V.time_sync(False, ["samay1.nic.in"], p, "t").status, "FAIL")
        self.assertEqual(V.time_sync(True, ["time.windows.com"], dict(p, require_nic_npl_source=False), "t").status,
                         "PASS")
        self.assertEqual(V.time_sync(True, ["dc01.corp"], p, "t", hierarchy=True).assurance, "RUNNING")


if __name__ == "__main__":
    unittest.main()
