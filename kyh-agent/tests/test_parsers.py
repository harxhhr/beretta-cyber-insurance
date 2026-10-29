"""Parsers: raw OS output captured from real machines -> facts."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

import _paths  # noqa: F401
from kyh_agent.checks import parsers as P
from kyh_agent.checks.linux import _expand_sshd

APT = """NOTE: This is only a simulation!
Reading package lists...
Inst libssl3 [3.0.2-0ubuntu1.10] (3.0.2-0ubuntu1.12 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])
Inst openssl [3.0.2-0ubuntu1.10] (3.0.2-0ubuntu1.12 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])
Inst vim-common [2:8.2.3995-1ubuntu2.15] (2:8.2.3995-1ubuntu2.16 Ubuntu:22.04/jammy-updates [all])
Inst openssh-server [1:9.2p1-2] (1:9.2p1-2+deb12u3 Debian-Security:12/stable-security [amd64])
Conf libssl3 (3.0.2-0ubuntu1.12 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])
"""

DPKG = """2026-08-01 10:00:00 startup archives unpack
2026-08-01 10:00:01 upgrade libc6:amd64 2.35-0ubuntu3.7 2.35-0ubuntu3.8
2026-09-10 09:30:00 install htop:amd64 <none> 3.0.5-7build2
2026-09-10 09:30:01 status installed htop:amd64 3.0.5-7build2
"""

WU = {"Pending": [
    {"Title": "2026-09 Cumulative Update for Windows 11 Version 24H2 (KB5065426)", "Severity": "Critical",
     "Categories": ["Security Updates", "Windows 11"]},
    {"Title": "Microsoft Defender Antivirus antimalware platform update", "Severity": None,
     "Categories": ["Definition Updates"]}],
    "LastHotfix": "2026-08-14T00:00:00.0000000+05:30"}

LSBLK_LUKS = {"blockdevices": [{"name": "nvme0n1", "type": "disk", "mountpoints": [None], "children": [
    {"name": "nvme0n1p1", "type": "part", "mountpoints": ["/boot/efi"]},
    {"name": "nvme0n1p3", "type": "part", "mountpoints": [None], "children": [
        {"name": "dm_crypt-0", "type": "crypt", "mountpoints": [None], "children": [
            {"name": "ubuntu--vg-root", "type": "lvm", "mountpoints": ["/"]}]}]}]}]}
LSBLK_PLAIN_OLD = {"blockdevices": [{"name": "sda", "type": "disk", "mountpoint": None, "children": [
    {"name": "sda1", "type": "part", "mountpoint": "/"}]}]}

PROC_TCP = """  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0100007F:0CEA 00000000:0000 0A 00000000:00000000 00:00000000 00000000   114        0 20813 1
   1: 00000000:0017 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 21000 1
   2: 0100007F:1F90 0100007F:D2F0 01 00000000:00000000 00:00000000 00000000     0        0 21001 1
"""
PROC_TCP6 = """  sl  local_address                         remote_address                        st
   0: 00000000000000000000000001000000:0016 00000000000000000000000000000000:0000 0A 0
   1: 00000000000000000000000000000000:0050 00000000000000000000000000000000:0000 0A 0
"""

W32TM_OK = """Leap Indicator: 0(no warning)
Stratum: 4 (secondary reference - syncd by (S)NTP)
Last Successful Sync Time: 30-09-2026 10:12:44
Source: time.windows.com,0x9
Poll Interval: 10 (1024s)
"""
W32TM_BAD = "Leap Indicator: 3(not synchronized)\nStratum: 0 (unspecified)\nSource: Local CMOS Clock\n"

CHRONYC = """MS Name/IP address         Stratum Poll Reach LastRx Last sample
===============================================================================
^* 164.100.192.10                2   6   377    35   -210us[ -305us] +/-   12ms
^- 185.125.190.56                2   6   377    34  +1482us[+1482us] +/-   48ms
"""


class PatchParsers(unittest.TestCase):
    def test_apt_counts_only_security_pockets(self):
        f = P.parse_apt_simulate(APT)
        self.assertEqual(f["pending_total"], 4)
        self.assertEqual(f["pending_security"], 3)  # jammy-security x2 + Debian-Security x1
        self.assertIn("openssh-server", f["security_packages"])

    def test_dpkg_last_change(self):
        self.assertEqual(P.parse_last_package_change(DPKG), datetime(2026, 9, 10, 9, 30, tzinfo=timezone.utc))

    def test_dnf_security(self):
        out = "RHSA-2026:1234 Important/Sec. openssl-1:3.0.7-25.el9_3.x86_64\n" \
              "RHSA-2026:1234 Important/Sec. openssl-libs-1:3.0.7-25.el9_3.x86_64\n"
        self.assertEqual(P.parse_dnf_security(out)["pending_security"], 2)

    def test_windows_update_json(self):
        f = P.parse_windows_updates(json.dumps(WU))
        self.assertEqual((f["pending_total"], f["pending_security"]), (2, 1))
        self.assertEqual(f["last_update"], datetime(2026, 8, 13, 18, 30, tzinfo=timezone.utc))

    def test_windows_update_single_object_unwrapped_by_powershell(self):
        f = P.parse_windows_updates(json.dumps({"Pending": {"Title": "x", "Severity": "Important",
                                                            "Categories": "Security Updates"}, "LastHotfix": None}))
        self.assertEqual(f["pending_security"], 1)

    def test_softwareupdate(self):
        out = "Software Update found the following new or updated software:\n* Label: macOS Sonoma 14.7.1-23H222\n" \
              "\tTitle: macOS Sonoma 14.7.1, Version: 14.7.1, Recommended: YES, Action: restart,\n"
        self.assertEqual(P.parse_softwareupdate_list(out)["pending_total"], 1)


class ProcessAndDefender(unittest.TestCase):
    def test_process_matching_is_case_and_exe_insensitive(self):
        found = P.match_known_processes(["MsMpEng.exe", "C:\\Program Files\\CrowdStrike\\CSFalconService.exe",
                                         "explorer"], {"MsMpEng": "Defender", "CSFalconService": "Falcon"})
        self.assertEqual(found, {"csfalconservice": "Falcon", "msmpeng": "Defender"})

    def test_keywords(self):
        self.assertEqual(P.match_process_keywords(["Veeam.EndPoint.Service", "bash"], ["veeam"]),
                         ["veeam.endpoint.service"])

    def test_defender_json(self):
        d = P.parse_defender_status(json.dumps({"AMServiceEnabled": True, "AntivirusEnabled": True,
                                                "RealTimeProtectionEnabled": False, "AntivirusSignatureAge": 9,
                                                "AMRunningMode": "Normal"}))
        self.assertFalse(d["realtime_enabled"])
        self.assertEqual(d["signature_age_days"], 9)


class DiskAndFirewall(unittest.TestCase):
    def test_luks_root_detected(self):
        info = P.lsblk_root_is_encrypted(json.dumps(LSBLK_LUKS))
        self.assertTrue(info["root_found"] and info["encrypted"])
        self.assertIn("dm_crypt-0(crypt)", info["chain"])

    def test_plain_root_old_lsblk_format(self):
        info = P.lsblk_root_is_encrypted(json.dumps(LSBLK_PLAIN_OLD))
        self.assertTrue(info["root_found"])
        self.assertFalse(info["encrypted"])

    def test_no_root_device_in_container(self):
        self.assertFalse(P.lsblk_root_is_encrypted('{"blockdevices": []}')["root_found"])

    def test_bitlocker_strings_and_numbers(self):
        self.assertTrue(P.parse_bitlocker('{"ProtectionStatus":"On","VolumeStatus":"FullyEncrypted"}')["protection_on"])
        b = P.parse_bitlocker('[{"ProtectionStatus":0,"VolumeStatus":1}]')
        self.assertTrue(b["fully_encrypted"])
        self.assertFalse(b["protection_on"])

    def test_manage_bde(self):
        out = "Volume C: [OS]\n    Conversion Status:    Fully Encrypted\n    Protection Status:    Protection On\n"
        m = P.parse_manage_bde(out)
        self.assertTrue(m["fully_encrypted"] and m["protection_on"])

    def test_fdesetup(self):
        self.assertTrue(P.parse_fdesetup("FileVault is On.")["filevault_on"])
        self.assertFalse(P.parse_fdesetup("FileVault is Off.")["filevault_on"])

    def test_ufw(self):
        self.assertTrue(P.parse_ufw_status("Status: active\n\nTo Action From"))
        self.assertFalse(P.parse_ufw_status("Status: inactive"))

    def test_nft(self):
        rules = "table inet filter {\n chain input {\n  type filter hook input priority filter; policy drop;\n }\n}"
        self.assertTrue(P.parse_nft_ruleset(rules)["protective"])
        accept = "table inet filter {\n chain input {\n  type filter hook input priority 0; policy accept;\n }\n}"
        self.assertFalse(P.parse_nft_ruleset(accept)["protective"])

    def test_iptables(self):
        self.assertTrue(P.parse_iptables_s("-P INPUT DROP\n-A INPUT -i lo -j ACCEPT\n")["protective"])
        self.assertFalse(P.parse_iptables_s("-P INPUT ACCEPT\n")["protective"])

    def test_windows_firewall_profiles(self):
        out = json.dumps([{"Name": "Domain", "Enabled": "True"}, {"Name": "Private", "Enabled": "True"},
                          {"Name": "Public", "Enabled": "False"}])
        info = P.parse_windows_firewall(out)
        self.assertFalse(info["all_enabled"])
        self.assertEqual(info["disabled"], ["Public"])

    def test_socketfilterfw(self):
        self.assertTrue(P.parse_socketfilterfw("Firewall is enabled. (State = 1)"))
        self.assertFalse(P.parse_socketfilterfw("Firewall is disabled. (State = 0)"))


class Sockets(unittest.TestCase):
    def test_proc_net_tcp_ipv4(self):
        self.assertEqual(P.parse_proc_net_tcp(PROC_TCP), [("127.0.0.1", 3306), ("0.0.0.0", 23)])

    def test_proc_net_tcp_ipv6(self):
        self.assertEqual(P.parse_proc_net_tcp(PROC_TCP6, ipv6=True), [("::1", 22), ("::", 80)])

    def test_netstat_macos(self):
        out = "tcp4       0      0  *.22                   *.*                    LISTEN      131072 131072\n" \
              "tcp4       0      0  127.0.0.1.631          *.*                    LISTEN      131072 131072\n"
        self.assertEqual(P.parse_netstat_listen(out), [("0.0.0.0", 22), ("127.0.0.1", 631)])

    def test_loopback(self):
        self.assertTrue(P.is_loopback("127.0.0.53") and P.is_loopback("::1") and P.is_loopback("::ffff:127.0.0.1"))
        self.assertFalse(P.is_loopback("0.0.0.0") or P.is_loopback("::"))


class Ssh(unittest.TestCase):
    def test_first_value_wins_and_match_blocks_ignored(self):
        cfg = P.parse_sshd_config([("/etc/ssh/sshd_config", "PermitRootLogin no\nPasswordAuthentication no\n"
                                    "Match User backup\n    PasswordAuthentication yes\n")])
        self.assertEqual(cfg["passwordauthentication"], "no")

    def test_dropin_before_main_file_wins(self):
        cfg = P.parse_sshd_config([("50-cloud-init.conf", "PasswordAuthentication yes"),
                                   ("sshd_config", "PasswordAuthentication no")])
        self.assertEqual(cfg["passwordauthentication"], "yes")

    def test_include_expanded_in_place(self):
        with tempfile.TemporaryDirectory() as d:
            inc = os.path.join(d, "conf.d")
            os.mkdir(inc)
            with open(os.path.join(inc, "10-x.conf"), "w") as fh:
                fh.write("PasswordAuthentication yes\n")
            main = os.path.join(d, "sshd_config")
            with open(main, "w") as fh:
                fh.write(f"Include {inc}/*.conf\nPasswordAuthentication no\nPermitRootLogin no\n")
            cfg = P.parse_sshd_config(_expand_sshd(main))
        self.assertEqual(cfg["passwordauthentication"], "yes")
        self.assertEqual(cfg["permitrootlogin"], "no")

    def test_sshd_T(self):
        self.assertEqual(P.parse_sshd_effective("permitrootlogin without-password\nport 22\n")["permitrootlogin"],
                         "without-password")


class AccountsLoggingTime(unittest.TestCase):
    def test_admins_and_hidden_uid0(self):
        info = P.parse_admin_members("sudo:x:27:alice,bob\nwheel:x:10:\nadm:x:4:syslog,alice\n",
                                     "root:x:0:0:root:/root:/bin/bash\ntoor:x:0:0::/:/bin/sh\n"
                                     "alice:x:1000:1000::/home/alice:/bin/bash\n", ["sudo", "wheel", "admin"])
        self.assertEqual(info["admins"], ["alice", "bob", "toor"])
        self.assertEqual(info["extra_uid0"], ["toor"])

    def test_dscl(self):
        self.assertEqual(P.parse_dscl_group("GroupMembership: root alice bob"), ["alice", "bob"])

    def test_rsyslog_forwarding(self):
        self.assertTrue(P.rsyslog_forwards("*.* @@siem.example.in:514\n"))
        self.assertTrue(P.rsyslog_forwards('action(type="omfwd" target="10.0.0.5" port="514" protocol="tcp")'))
        self.assertFalse(P.rsyslog_forwards("# *.* @@siem.example.in:514\n*.* /var/log/syslog\n"))

    def test_journal_and_wevtutil_dates(self):
        self.assertEqual(P.parse_journal_first_line("2026-04-01T10:00:00+0530 host kernel: Linux"),
                         datetime(2026, 4, 1, 4, 30, tzinfo=timezone.utc))
        self.assertEqual(P.parse_wevtutil_first_date("Event[0]:\n  Date: 2026-03-01T00:00:00.0000000Z\n"),
                         datetime(2026, 3, 1, tzinfo=timezone.utc))

    def test_w32tm(self):
        self.assertEqual(P.parse_w32tm_status(W32TM_OK), {"source": "time.windows.com", "synchronized": True})
        self.assertFalse(P.parse_w32tm_status(W32TM_BAD)["synchronized"])

    def test_chrony(self):
        self.assertEqual(P.parse_chronyc_sources(CHRONYC)["selected"], "164.100.192.10")
        self.assertEqual(P.parse_chrony_conf("server samay1.nic.in iburst\npool 2.ubuntu.pool.ntp.org iburst\n"
                                             "# server x\n"), ["samay1.nic.in", "2.ubuntu.pool.ntp.org"])

    def test_timesyncd_fallback_only_when_no_primary(self):
        self.assertEqual(P.parse_timesyncd_conf("[Time]\nNTP=samay1.nic.in\nFallbackNTP=ntp.ubuntu.com\n"),
                         ["samay1.nic.in"])
        self.assertEqual(P.parse_timesyncd_conf("[Time]\nFallbackNTP=ntp.ubuntu.com\n"), ["ntp.ubuntu.com"])

    def test_iso_variants(self):
        self.assertEqual(P.parse_iso("/Date(1788220800000)/"), datetime(2026, 9, 1, tzinfo=timezone.utc))
        self.assertIsNotNone(P.parse_iso("2026-08-14T00:00:00.1234567+05:30"))
        self.assertIsNone(P.parse_iso("not a date"))


if __name__ == "__main__":
    unittest.main()
