"""Windows collectors. PowerShell snippets are read-only (Get-* cmdlets and COM searches only);
registry reads use the standard-library winreg module so no process is spawned."""

from __future__ import annotations

import json

from . import parsers as P
from . import verdicts as V
from .base import (ERROR, NOT_SUPPORTED, NeedsPrivilege, Outcome, looks_like_access_denied,
                   read_text, run_cmd, run_powershell)

PS_PROCESSES = "@(Get-Process | Select-Object -ExpandProperty ProcessName)"


def _reg(hive_path: str, name: str):
    import winreg  # Windows-only stdlib module
    root, _, sub = hive_path.partition("\\")
    hive = {"HKLM": winreg.HKEY_LOCAL_MACHINE}[root]
    try:
        with winreg.OpenKey(hive, sub) as k:
            return winreg.QueryValueEx(k, name)[0]
    except FileNotFoundError:
        return None


def _ps_json(script: str, timeout: float = 60):
    rc, out, err = run_powershell(script, timeout=timeout)
    if rc != 0 or not out.strip():
        if looks_like_access_denied(err):
            raise NeedsPrivilege(err.strip()[:200])
        raise RuntimeError(err.strip()[:300] or f"PowerShell exited {rc}")
    return json.loads(out)


# ----------------------------------------------------------------------------- PATCH
PS_PATCH = r"""
$ErrorActionPreference='Stop'
$s=New-Object -ComObject Microsoft.Update.Session
$r=$s.CreateUpdateSearcher().Search("IsInstalled=0 and IsHidden=0 and Type='Software'")
$u=@(foreach($x in $r.Updates){[pscustomobject]@{Title=$x.Title;Severity=$x.MsrcSeverity;Categories=@(foreach($c in $x.Categories){$c.Name})}})
$h=Get-HotFix | Where-Object {$_.InstalledOn} | Sort-Object InstalledOn -Descending | Select-Object -First 1
[pscustomobject]@{Pending=$u;LastHotfix=$(if($h){$h.InstalledOn.ToString('o')}else{$null})} | ConvertTo-Json -Depth 4 -Compress
"""
PS_LAST_HOTFIX = r"""
$h=Get-HotFix | Where-Object {$_.InstalledOn} | Sort-Object InstalledOn -Descending | Select-Object -First 1
[pscustomobject]@{Pending=$null;LastHotfix=$(if($h){$h.InstalledOn.ToString('o')}else{$null})} | ConvertTo-Json -Compress
"""


def patch(p, ctx) -> Outcome:
    method = "Windows Update Agent search + Get-HotFix"
    rc, out, err = run_powershell(PS_PATCH, timeout=p.get("timeout", 300))
    if rc != 0 or not out.strip():  # offline / WSUS unreachable: fall back to last-install age only
        rc, out, err = run_powershell(PS_LAST_HOTFIX, timeout=60)
        method = "Get-HotFix (update search unavailable)"
        if rc != 0:
            return Outcome(ERROR, f"Could not query updates: {err.strip()[:200]}", method=method)
        facts = P.parse_windows_updates(out)
        facts["pending_security"] = None
    else:
        facts = P.parse_windows_updates(out)
    facts["index_age_days"] = None
    return V.patching(facts, p, ctx.now, method)


# ----------------------------------------------------------------------------- EDR
PS_EDR = r"""
$ErrorActionPreference='SilentlyContinue'
$d=Get-MpComputerStatus | Select-Object AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureAge,AMRunningMode
[pscustomobject]@{Processes=%s;Defender=$d} | ConvertTo-Json -Depth 3 -Compress
""" % PS_PROCESSES


def edr(p, ctx) -> Outcome:
    data = _ps_json(PS_EDR)
    found = P.match_known_processes(data.get("Processes") or [], p["known_processes"])
    defender = P.parse_defender_status(json.dumps(data["Defender"])) if data.get("Defender") else None
    return V.edr(found, defender, p, "Get-Process + Get-MpComputerStatus")


# ----------------------------------------------------------------------------- BACKUP
PS_BACKUP = r"""
$ErrorActionPreference='SilentlyContinue'
$wb=$null
if(Get-Command Get-WBSummary){ $s=Get-WBSummary; if($s -and $s.LastSuccessfulBackupTime -gt [datetime]'2000-01-01'){ $wb=$s.LastSuccessfulBackupTime.ToUniversalTime().ToString('o') } }
[pscustomobject]@{WB=$wb;Processes=%s} | ConvertTo-Json -Compress
""" % PS_PROCESSES


def backup(p, ctx) -> Outcome:
    for path in p["marker_paths"].get("windows", []):
        txt = read_text(path)
        if txt:
            ts = P.parse_iso(txt.strip().splitlines()[0])
            if ts:
                return V.backup(ts, f"marker {path}", [], p, ctx.now, "KYH backup marker file")
    data = _ps_json(PS_BACKUP)
    if data.get("WB"):
        return V.backup(P.parse_iso(data["WB"]), "Windows Server Backup", [], p, ctx.now, "Get-WBSummary")
    agents = P.match_process_keywords(data.get("Processes") or [], p["process_keywords"])
    return V.backup(None, None, agents, p, ctx.now, "marker file + Get-WBSummary + process table")


# ----------------------------------------------------------------------------- DISK
PS_BITLOCKER = r"""
$v=Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
[pscustomobject]@{MountPoint=$v.MountPoint;VolumeStatus=$v.VolumeStatus.ToString();ProtectionStatus=$v.ProtectionStatus.ToString();EncryptionPercentage=$v.EncryptionPercentage} | ConvertTo-Json -Compress
"""


def disk_encryption(p, ctx) -> Outcome:
    rc, out, err = run_powershell(PS_BITLOCKER, timeout=60)
    if rc == 0 and out.strip():
        info, method = P.parse_bitlocker(out), "Get-BitLockerVolume"
    else:
        if looks_like_access_denied(err):
            raise NeedsPrivilege("BitLocker status requires administrator rights")
        rc, out, err = run_cmd(["manage-bde", "-status", "C:"], timeout=60)
        if rc != 0:
            if looks_like_access_denied(out + err):
                raise NeedsPrivilege("manage-bde requires administrator rights")
            return Outcome(NOT_SUPPORTED, "BitLocker is not available on this edition", method="manage-bde")
        info, method = P.parse_manage_bde(out), "manage-bde -status"
    return V.disk_encryption(info["fully_encrypted"] or info["protection_on"], info, method,
                             suspended=info["fully_encrypted"] and not info["protection_on"])


# ----------------------------------------------------------------------------- FIREWALL
def firewall(p, ctx) -> Outcome:
    rc, out, err = run_powershell(
        "Get-NetFirewallProfile | Select-Object Name,@{n='Enabled';e={[string]$_.Enabled}} | ConvertTo-Json -Compress")
    if rc != 0:
        return Outcome(ERROR, f"Get-NetFirewallProfile failed: {err.strip()[:200]}", method="Get-NetFirewallProfile")
    info = P.parse_windows_firewall(out)
    return V.firewall(info["all_enabled"], info, "Get-NetFirewallProfile (Domain/Private/Public)")


# ----------------------------------------------------------------------------- LISTENERS
def exposed_services(p, ctx) -> Outcome:
    rc, out, err = run_powershell(
        "Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort | ConvertTo-Json -Compress")
    if rc != 0:
        return Outcome(ERROR, f"Get-NetTCPConnection failed: {err.strip()[:200]}", method="Get-NetTCPConnection")
    return V.exposed_services(P.parse_windows_listeners(out), p, "Get-NetTCPConnection -State Listen")


# ----------------------------------------------------------------------------- REMOTE ACCESS
def remote_access(p, ctx) -> Outcome:
    base = r"HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server"
    deny = _reg(base, "fDenyTSConnections")
    nla = _reg(base + r"\WinStations\RDP-Tcp", "UserAuthentication")
    return V.rdp_hardening(rdp_enabled=(deny == 0), nla=(nla == 1), method="registry: Terminal Server settings")


# ----------------------------------------------------------------------------- ADMINS
PS_ADMINS = r"""
$ErrorActionPreference='Stop'
$a=@(Get-LocalGroupMember -SID 'S-1-5-32-544' | ForEach-Object { $_.Name })
$g=Get-LocalUser | Where-Object { $_.SID.Value -like '*-501' } | Select-Object -First 1
[pscustomobject]@{Admins=$a;GuestEnabled=[bool]($g -and $g.Enabled)} | ConvertTo-Json -Compress
"""


def admin_accounts(p, ctx) -> Outcome:
    info = P.parse_windows_admins(json.dumps(_ps_json(PS_ADMINS)))
    hashed = [ctx.hash_id(a) for a in info["admins"]]
    return V.admin_accounts(len(info["admins"]), hashed, 0, info["guest_enabled"], p,
                            "Get-LocalGroupMember S-1-5-32-544 + Get-LocalUser (RID 501)")


# ----------------------------------------------------------------------------- OS SUPPORT
def os_support(p, ctx) -> Outcome:
    cv = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    build = str(_reg(cv, "CurrentBuild") or "")
    display = _reg(cv, "DisplayVersion") or _reg(cv, "ReleaseId") or ""
    kind = (_reg(cv, "InstallationType") or "Client").lower()
    edition = (_reg(cv, "EditionID") or "").lower()
    tables = p["eol"]["windows"]
    if "server" in kind:
        table, label = tables["server"], f"Windows Server (build {build})"
    else:
        name = "Windows 11" if build.isdigit() and int(build) >= 22000 else "Windows 10"
        label = f"{name} {display} (build {build})"
        table = tables["client_enterprise"] if ("enterprise" in edition or "education" in edition) else tables["client"]
    if build not in table:
        return V.os_support(label, None, p, ctx.now, "registry: CurrentVersion", known=False)
    return V.os_support(label, table[build], p, ctx.now, "registry: CurrentVersion")


# ----------------------------------------------------------------------------- LOGGING
PS_LOGS = r"""
$ErrorActionPreference='SilentlyContinue'
$log='Security'; $e=Get-WinEvent -LogName Security -MaxEvents 1 -Oldest
if(-not $e){ $log='System'; $e=Get-WinEvent -LogName System -MaxEvents 1 -Oldest }
$l=Get-WinEvent -ListLog $log
[pscustomobject]@{Log=$log;Oldest=$(if($e){$e.TimeCreated.ToUniversalTime().ToString('o')}else{$null});Enabled=[bool]$l.IsEnabled;MaxSizeBytes=$l.MaximumSizeInBytes;Processes=%s} | ConvertTo-Json -Compress
""" % PS_PROCESSES


def log_retention(p, ctx) -> Outcome:
    data = _ps_json(PS_LOGS, timeout=90)
    fwd = P.match_known_processes(data.get("Processes") or [], p["forwarder_processes"])
    oldest = P.parse_iso(data.get("Oldest")) if data.get("Oldest") else None
    retained = round((ctx.now - oldest).total_seconds() / 86400, 1) if oldest else None
    out = V.log_retention(bool(data.get("Enabled")), ", ".join(sorted(set(fwd.values()))) or None, retained, p,
                          f"Get-WinEvent ({data.get('Log')} log, oldest record) + process table")
    out.evidence["log_name"] = data.get("Log")
    out.evidence["max_size_bytes"] = data.get("MaxSizeBytes")
    return out


# ----------------------------------------------------------------------------- TIME SYNC
def time_sync(p, ctx) -> Outcome:
    params = r"HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters"
    ttype = (_reg(params, "Type") or "").upper()
    configured = [s.split(",")[0].lower() for s in (_reg(params, "NtpServer") or "").split() if s]
    synced, sources = None, []
    try:
        rc, out, _ = run_cmd(["w32tm", "/query", "/status"], timeout=20)
        if rc == 0:
            st = P.parse_w32tm_status(out)
            synced = st["synchronized"]
            if st["source"]:
                sources.append(st["source"])
    except Exception:  # noqa: BLE001 - w32tm missing or service stopped; registry still tells us the config
        pass
    hierarchy = ttype in ("NT5DS", "ALLSYNC") and not any(P.host_matches(s, p["approved_sources"]) for s in sources)
    sources = list(dict.fromkeys(sources + configured))
    return V.time_sync(synced, sources, p, "w32tm /query /status + registry W32Time", hierarchy=hierarchy)
