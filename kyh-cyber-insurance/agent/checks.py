"""Genuine, defensive, read-only OS checks for the endpoint agent.

Rules honoured here:
- No offensive capability; read-only inspection only.
- If a control cannot be safely/reliably observed on this platform, the check
  returns NOT_SUPPORTED — results are never fabricated.
- Software merely being installed is reported as PRESENT-level evidence, not
  as proof the control works; the evidence text states exactly what was seen.
"""
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(cmd, timeout=10):
    """Run a fixed, read-only command (list form only — no shell)."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.returncode, (out.stdout or "") + (out.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def _result(control_id, check_name, status, value=None, evidence="", level=""):
    return dict(control_id=control_id, check_name=check_name, status=status,
                value=value, evidence=evidence.strip()[:400],
                observability=level, timestamp=_now())


IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


def check_mfa():
    # MFA is an identity-provider setting; it is not reliably observable from a
    # single endpoint on any platform. Honest answer: NOT_SUPPORTED.
    return _result("CTRL-MFA", "mfa_local_observability", "NOT_SUPPORTED",
                   evidence="MFA enforcement lives in the identity provider and cannot "
                            "be verified from this endpoint. Provide IdP evidence instead.")


def check_firewall():
    if IS_LINUX:
        if shutil.which("ufw"):
            rc, out = _run(["ufw", "status"])
            if rc == 0 and "Status:" in out:
                active = "Status: active" in out
                return _result("CTRL-SECCONFIG", "host_firewall", "PASS" if active else "FAIL",
                               active, f"ufw reports: {out.splitlines()[0]}",
                               "ENABLED" if active else "PRESENT")
        if os.path.exists("/proc/sys/net/ipv4"):
            rc, out = _run(["iptables", "-S"])
            if rc == 0:
                rules = [l for l in out.splitlines() if l and not l.startswith("-P")]
                has_rules = len(rules) > 0
                return _result("CTRL-SECCONFIG", "host_firewall",
                               "PASS" if has_rules else "WARN", has_rules,
                               f"iptables readable; {len(rules)} non-default rules.",
                               "CONFIGURED" if has_rules else "PRESENT")
    if IS_WINDOWS:
        rc, out = _run(["netsh", "advfirewall", "show", "allprofiles", "state"])
        if rc == 0:
            on = out.count("ON") >= 1 and "OFF" not in out
            return _result("CTRL-SECCONFIG", "host_firewall", "PASS" if on else "FAIL",
                           on, out[:200], "ENABLED" if on else "PRESENT")
    return _result("CTRL-SECCONFIG", "host_firewall", "NOT_SUPPORTED",
                   evidence="No readable firewall interface on this platform/permissions.")


def check_disk_encryption():
    if IS_LINUX:
        try:
            with open("/proc/mounts") as fh:
                mounts = fh.read()
        except OSError:
            return _result("CTRL-ENCRYPTION", "disk_encryption", "NOT_SUPPORTED",
                           evidence="/proc/mounts unreadable.")
        crypt = "/dev/mapper" in mounts and ("crypt" in mounts or
                                             os.path.isdir("/dev/mapper"))
        rc, out = _run(["lsblk", "-o", "NAME,TYPE"])
        if rc == 0:
            has_crypt = "crypt" in out
            return _result("CTRL-ENCRYPTION", "disk_encryption",
                           "PASS" if has_crypt else "FAIL", has_crypt,
                           "lsblk shows a dm-crypt volume." if has_crypt
                           else "No dm-crypt volume visible in lsblk.",
                           "OBSERVED_WORKING" if has_crypt else "")
        return _result("CTRL-ENCRYPTION", "disk_encryption", "NOT_SUPPORTED",
                       evidence="lsblk unavailable; encryption state not observable.")
    if IS_MAC:
        rc, out = _run(["fdesetup", "status"])
        if rc == 0:
            on = "On" in out
            return _result("CTRL-ENCRYPTION", "disk_encryption", "PASS" if on else "FAIL",
                           on, out.strip(), "ENABLED" if on else "")
    if IS_WINDOWS:
        rc, out = _run(["manage-bde", "-status"])
        if rc == 0:
            on = "Percentage Encrypted: 100" in out or "Fully Encrypted" in out
            return _result("CTRL-ENCRYPTION", "disk_encryption", "PASS" if on else "FAIL",
                           on, "BitLocker status read.", "ENABLED" if on else "")
    return _result("CTRL-ENCRYPTION", "disk_encryption", "NOT_SUPPORTED",
                   evidence="Encryption status not observable on this platform/permissions.")


def check_patch_level():
    if IS_LINUX and shutil.which("apt"):
        rc, out = _run(["apt", "list", "--upgradable"], timeout=30)
        if rc == 0:
            pending = max(0, len([l for l in out.splitlines() if "/" in l]) - 0)
            # security updates specifically
            sec = len([l for l in out.splitlines() if "-security" in l])
            status = "PASS" if sec == 0 else ("WARN" if sec <= 5 else "FAIL")
            return _result("CTRL-PATCH-CRIT", "pending_security_updates", status,
                           sec == 0, f"{sec} pending security updates "
                                     f"({pending} total upgradable).",
                           "OBSERVED_WORKING")
    if IS_WINDOWS:
        return _result("CTRL-PATCH-CRIT", "pending_security_updates", "NOT_SUPPORTED",
                       evidence="Windows Update query requires COM/PowerShell module not "
                                "guaranteed present; not fabricating a result.")
    return _result("CTRL-PATCH-CRIT", "pending_security_updates", "NOT_SUPPORTED",
                   evidence="No supported package manager found.")


EDR_MARKERS = ["falcon-sensor", "wazuh-agent", "osqueryd", "cbagentd", "SentinelAgent",
               "mfetpd", "xagt", "elastic-agent", "velociraptor", "CrowdStrike",
               "cortex-xdr"]


def check_edr():
    procs = ""
    if IS_LINUX or IS_MAC:
        rc, procs = _run(["ps", "-axo", "comm"])
    elif IS_WINDOWS:
        rc, procs = _run(["tasklist"])
    else:
        rc = None
    if rc != 0:
        return _result("CTRL-EDR", "edr_process", "NOT_SUPPORTED",
                       evidence="Process list not readable.")
    found = [m for m in EDR_MARKERS if m.lower() in procs.lower()]
    if found:
        return _result("CTRL-EDR", "edr_process", "PASS", True,
                       f"EDR/telemetry agent process running: {', '.join(found)}. "
                       f"Running process observed; policy enforcement not verified.",
                       "OBSERVED_WORKING")
    return _result("CTRL-EDR", "edr_process", "FAIL", False,
                   "No known EDR/telemetry agent process observed on this endpoint.")


def check_logging():
    if IS_LINUX:
        rc, out = _run(["ps", "-axo", "comm"])
        if rc == 0:
            svc = [s for s in ("rsyslogd", "systemd-journal", "syslog-ng", "fluent")
                   if s in out]
            if svc:
                return _result("CTRL-LOGGING", "log_service", "PASS", True,
                               f"Logging service running: {', '.join(svc)}. Local only — "
                               f"central collection not verified.", "ENABLED")
            return _result("CTRL-LOGGING", "log_service", "FAIL", False,
                           "No logging daemon observed.")
    return _result("CTRL-LOGGING", "log_service", "NOT_SUPPORTED",
                   evidence="Logging service not observable on this platform.")


def check_password_policy():
    if IS_LINUX and os.path.exists("/etc/login.defs"):
        try:
            with open("/etc/login.defs") as fh:
                text = fh.read()
        except OSError:
            return _result("CTRL-PASSPOLICY", "local_password_policy", "NOT_SUPPORTED",
                           evidence="/etc/login.defs unreadable.")
        max_days = None
        for line in text.splitlines():
            if line.strip().startswith("PASS_MAX_DAYS"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    max_days = int(parts[1])
        pwquality = os.path.exists("/etc/security/pwquality.conf")
        ok = pwquality or (max_days is not None and max_days <= 365)
        return _result("CTRL-PASSPOLICY", "local_password_policy",
                       "PASS" if ok else "WARN", ok,
                       f"PASS_MAX_DAYS={max_days}; pwquality "
                       f"{'present' if pwquality else 'absent'}. Local policy only.",
                       "CONFIGURED" if ok else "PRESENT")
    return _result("CTRL-PASSPOLICY", "local_password_policy", "NOT_SUPPORTED",
                   evidence="Local password policy not observable here.")


def check_auto_updates():
    if IS_LINUX:
        path = "/etc/apt/apt.conf.d/20auto-upgrades"
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    text = fh.read()
                on = 'Unattended-Upgrade "1"' in text
                return _result("CTRL-PATCH-CRIT", "unattended_upgrades",
                               "PASS" if on else "WARN", on,
                               "unattended-upgrades " + ("enabled" if on else "installed "
                               "but not enabled"), "ENABLED" if on else "PRESENT")
            except OSError:
                pass
        return _result("CTRL-PATCH-CRIT", "unattended_upgrades", "WARN", False,
                       "No unattended-upgrades configuration found.")
    return _result("CTRL-PATCH-CRIT", "unattended_upgrades", "NOT_SUPPORTED",
                   evidence="Automatic updates not observable on this platform.")


BACKUP_MARKERS = ["restic", "borg", "duplicity", "veeamagent", "rclone"]


def check_backups():
    found = [m for m in BACKUP_MARKERS if shutil.which(m)]
    if found:
        return _result("CTRL-BACKUP-TESTED", "backup_tooling", "WARN", "partial",
                       f"Backup tooling installed: {', '.join(found)}. Tool presence only — "
                       f"neither recent runs nor restore tests are observable from here.",
                       "PRESENT")
    return _result("CTRL-BACKUP-TESTED", "backup_tooling", "NOT_SUPPORTED",
                   evidence="No backup tooling observable; backup/restore status cannot be "
                            "verified from this endpoint. Provide a restore-test report.")


def check_ssh_hardening():
    cfg = "/etc/ssh/sshd_config"
    if IS_LINUX and os.path.exists(cfg):
        try:
            with open(cfg) as fh:
                text = fh.read()
        except OSError:
            return _result("CTRL-SECCONFIG", "ssh_root_login", "NOT_SUPPORTED",
                           evidence="sshd_config unreadable.")
        lines = [l.strip() for l in text.splitlines()
                 if l.strip().lower().startswith("permitrootlogin")]
        val = lines[-1].split()[-1].lower() if lines else "default"
        ok = val in ("no", "prohibit-password", "default")
        return _result("CTRL-SECCONFIG", "ssh_root_login", "PASS" if ok else "FAIL", ok,
                       f"PermitRootLogin = {val}.", "CONFIGURED")
    return _result("CTRL-SECCONFIG", "ssh_root_login", "NOT_SUPPORTED",
                   evidence="No sshd configuration on this endpoint.")


ALL_CHECKS = [check_mfa, check_edr, check_backups, check_patch_level, check_auto_updates,
              check_firewall, check_disk_encryption, check_logging,
              check_password_policy, check_ssh_hardening]


def run_all():
    results = []
    for fn in ALL_CHECKS:
        try:
            results.append(fn())
        except Exception as e:  # a broken check must not fabricate a result
            results.append(_result("CTRL-SECCONFIG", fn.__name__, "NOT_SUPPORTED",
                                   evidence=f"Check errored safely: {e.__class__.__name__}"))
    return results


# ---------------------------------------------------------------------------
# Simulation profiles for demonstrations. Reports produced from these are
# explicitly labelled SIMULATED in every evidence string.
# ---------------------------------------------------------------------------
SIM_PROFILES = {
    "good":  {"CTRL-MFA": "PASS", "CTRL-EDR": "PASS", "CTRL-BACKUP-TESTED": "PASS",
              "CTRL-PATCH-CRIT": "PASS", "CTRL-ENCRYPTION": "PASS",
              "CTRL-LOGGING": "PASS", "CTRL-SECCONFIG": "PASS",
              "CTRL-PASSPOLICY": "PASS"},
    "mixed": {"CTRL-MFA": "PASS", "CTRL-EDR": "PASS", "CTRL-BACKUP-TESTED": "FAIL",
              "CTRL-PATCH-CRIT": "WARN", "CTRL-ENCRYPTION": "PASS",
              "CTRL-LOGGING": "PASS", "CTRL-SECCONFIG": "WARN",
              "CTRL-PASSPOLICY": "PASS"},
    "weak":  {"CTRL-MFA": "FAIL", "CTRL-EDR": "FAIL", "CTRL-BACKUP-TESTED": "FAIL",
              "CTRL-PATCH-CRIT": "FAIL", "CTRL-ENCRYPTION": "FAIL",
              "CTRL-LOGGING": "FAIL", "CTRL-SECCONFIG": "FAIL",
              "CTRL-PASSPOLICY": "PASS"},
    "mfa_down": {"CTRL-MFA": "FAIL"},
    "mfa_up":   {"CTRL-MFA": "PASS"},
}


def run_simulated(profile):
    mapping = SIM_PROFILES[profile]
    return [_result(ctrl, f"simulated_{ctrl.lower()}", status,
                    status == "PASS",
                    f"SIMULATED demonstration observation (profile '{profile}').")
            for ctrl, status in mapping.items()]
