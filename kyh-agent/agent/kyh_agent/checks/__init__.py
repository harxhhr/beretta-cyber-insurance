"""Check registry.

The registry is the complete, fixed list of things the agent knows how to observe.
The policy file can choose which of these run and set their thresholds, but it can
never add new code: a check id that is not in REGISTRY is rejected at load time.
This is the "no remote code execution" guarantee.
"""

from __future__ import annotations

from . import linux, macos, verdicts, windows

LINUX, WINDOWS, DARWIN = "linux", "windows", "darwin"


def _mfa(p, ctx):
    return verdicts.mfa()


REGISTRY = {
    "patch.security_updates": {LINUX: linux.patch, WINDOWS: windows.patch, DARWIN: macos.patch},
    "edr.running_healthy": {LINUX: linux.edr, WINDOWS: windows.edr, DARWIN: macos.edr},
    "backup.recent_success": {LINUX: linux.backup, WINDOWS: windows.backup, DARWIN: macos.backup},
    "mfa.identity_provider": {LINUX: _mfa, WINDOWS: _mfa, DARWIN: _mfa},
    "disk.encryption": {LINUX: linux.disk_encryption, WINDOWS: windows.disk_encryption, DARWIN: macos.disk_encryption},
    "firewall.enabled": {LINUX: linux.firewall, WINDOWS: windows.firewall, DARWIN: macos.firewall},
    "network.exposed_services": {LINUX: linux.exposed_services, WINDOWS: windows.exposed_services,
                                 DARWIN: macos.exposed_services},
    "remote.access_hardening": {LINUX: linux.remote_access, WINDOWS: windows.remote_access,
                                DARWIN: macos.remote_access},
    "accounts.local_admins": {LINUX: linux.admin_accounts, WINDOWS: windows.admin_accounts,
                              DARWIN: macos.admin_accounts},
    "os.vendor_support": {LINUX: linux.os_support, WINDOWS: windows.os_support, DARWIN: macos.os_support},
    "logging.retention": {LINUX: linux.log_retention, WINDOWS: windows.log_retention, DARWIN: macos.log_retention},
    "time.sync_source": {LINUX: linux.time_sync, WINDOWS: windows.time_sync, DARWIN: macos.time_sync},
}
