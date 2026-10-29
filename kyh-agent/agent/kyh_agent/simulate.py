"""Demonstration profiles. Simulated results are ALWAYS labelled (evidence.simulated=true and
envelope.simulated=true); the collector ignores them unless the company is in demo mode."""

from __future__ import annotations

from .checks.base import (ABSENT, FAIL, NOT_APPLICABLE, NOT_SUPPORTED, OPERATING, PASS, PRESENT,
                          RUNNING, Outcome)

HEALTHY = {
    "patch.security_updates": (PASS, OPERATING, "No security updates pending"),
    "edr.running_healthy": (PASS, OPERATING, "Microsoft Defender active, signatures 0 day(s) old"),
    "backup.recent_success": (PASS, OPERATING, "Last successful backup 0.4 days ago"),
    "mfa.identity_provider": (NOT_SUPPORTED, None, "MFA is enforced by the identity provider, not the endpoint"),
    "disk.encryption": (PASS, OPERATING, "System drive is encrypted"),
    "firewall.enabled": (PASS, OPERATING, "Host firewall is enabled"),
    "network.exposed_services": (PASS, None, "No high-risk services listening on network interfaces"),
    "remote.access_hardening": (NOT_APPLICABLE, None, "Remote Desktop is disabled"),
    "accounts.local_admins": (PASS, None, "2 local administrator(s); no guest or hidden root accounts"),
    "os.vendor_support": (PASS, None, "Windows 11 24H2 supported"),
    "logging.retention": (PASS, RUNNING, "Logs forwarded off-host by Wazuh"),
    "time.sync_source": (PASS, OPERATING, "Clock synchronised to approved source samay1.nic.in"),
}

PROFILES = {
    "healthy": {},
    "edr_down": {"edr.running_healthy": (FAIL, ABSENT, "No known EDR/anti-malware process is running")},
    "edr_stale": {"edr.running_healthy": (FAIL, PRESENT, "Microsoft Defender present but signatures 9 days old "
                                                         "(limit 3)")},
    "patch_overdue": {"patch.security_updates": (FAIL, PRESENT, "7 security update(s) pending; last patching "
                                                                "52 days ago (limit 30 days)")},
    "backup_stale": {"backup.recent_success": (FAIL, PRESENT, "Last successful backup 12 days ago (limit 7)")},
    "mixed": {"patch.security_updates": (FAIL, PRESENT, "3 security update(s) pending; last patching 41 days ago"),
              "time.sync_source": (FAIL, PRESENT, "Clock synchronised to time.windows.com, not a NIC/NPL server")},
}


def outcome_for(profile: str, check_id: str) -> Outcome:
    if profile not in PROFILES:
        raise ValueError(f"unknown simulate profile '{profile}'. Choose from: {', '.join(PROFILES)}")
    status, assurance, summary = PROFILES[profile].get(check_id, HEALTHY.get(check_id, (PASS, None, "ok")))
    return Outcome(status, "[SIMULATED] " + summary, assurance, {"simulated": True, "profile": profile},
                   "simulation profile")


def registry_for(profile: str, platform: str) -> dict:
    """A drop-in replacement for the real registry that returns scripted outcomes."""
    outcome_for(profile, "x")  # validate name early
    return {cid: {platform: (lambda p, ctx, _cid=cid: outcome_for(profile, _cid))} for cid in HEALTHY}
