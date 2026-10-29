"""Verdicts: turn observed facts + policy thresholds into a PASS/FAIL outcome.

Each function is pure (facts, params, now) -> Outcome, so the decision rules can
be read, tested and cited independently of how the facts were collected.
"""

from __future__ import annotations

from datetime import date, datetime

from .base import (ABSENT, FAIL, NOT_APPLICABLE, NOT_SUPPORTED, OPERATING, PASS, PRESENT,
                   RUNNING, Outcome, iso)
from .parsers import host_matches, is_loopback


def _days(now: datetime, then: datetime | None):
    return None if then is None else round((now - then).total_seconds() / 86400, 1)


# ------------------------------------------------------------------ PATCH (warranty)
def patching(facts: dict, p: dict, now: datetime, method: str) -> Outcome:
    pending = facts.get("pending_security")
    last = facts.get("last_update")
    index_age = facts.get("index_age_days")
    since = _days(now, last)
    ev = {"pending_security": pending, "pending_total": facts.get("pending_total"),
          "days_since_last_update": since, "package_index_age_days": index_age,
          "security_packages": facts.get("security_packages", []),
          "max_patch_age_days": p["max_patch_age_days"]}
    if index_age is not None and index_age > p["max_index_age_days"]:
        return Outcome(FAIL, f"Package index is {index_age} days old; the pending-update count cannot be trusted",
                       PRESENT, ev, method)
    if pending == 0:
        return Outcome(PASS, "No security updates pending", OPERATING, ev, method)
    what = "Pending updates could not be listed" if pending is None else f"{pending} security update(s) pending"
    if since is not None and since <= p["max_patch_age_days"]:
        return Outcome(PASS, f"{what}, but the machine was patched {since} days ago "
                             f"(within the {p['max_patch_age_days']}-day cycle)",
                       OPERATING if pending is not None else RUNNING, ev, method)
    age = "never observed" if since is None else f"{since} days ago"
    return Outcome(FAIL, f"{what}; last patching {age} (limit {p['max_patch_age_days']} days)", PRESENT, ev, method)


# ------------------------------------------------------------------ EDR (warranty)
def edr(found: dict, defender: dict | None, p: dict, method: str, health: dict | None = None) -> Outcome:
    """found = {process: product} of known EDR/AV processes; defender = parsed Get-MpComputerStatus."""
    ev = {"edr_processes": found, "defender": defender, "health": health,
          "max_signature_age_days": p["max_signature_age_days"]}
    third_party = {k: v for k, v in found.items() if not v.startswith("Microsoft Defender")}
    if health is not None and health.get("healthy") is False:
        return Outcome(FAIL, f"{health.get('product')} reports itself unhealthy", PRESENT, ev, method)
    if health is not None and health.get("healthy") is True:
        return Outcome(PASS, f"{health.get('product')} running and reports healthy", OPERATING, ev, method)
    if third_party:
        names = ", ".join(sorted(set(third_party.values())))
        return Outcome(PASS, f"EDR running: {names} (process observed; product health not queryable locally)",
                       RUNNING, ev, method)
    if defender is not None:
        age = defender.get("signature_age_days")
        mode = (defender.get("running_mode") or "Normal").lower()
        active = defender["service_enabled"] and defender["antivirus_enabled"] and "passive" not in mode
        if active and defender["realtime_enabled"] and age is not None and age <= p["max_signature_age_days"]:
            return Outcome(PASS, f"Microsoft Defender active, real-time protection on, signatures {age} day(s) old",
                           OPERATING, ev, method)
        problems = []
        if not active:
            problems.append(f"not the active engine (mode: {defender.get('running_mode')})")
        if not defender["realtime_enabled"]:
            problems.append("real-time protection off")
        if age is None or age > p["max_signature_age_days"]:
            problems.append(f"signatures {age} days old (limit {p['max_signature_age_days']})")
        return Outcome(FAIL, "Microsoft Defender present but " + "; ".join(problems), PRESENT, ev, method)
    if found:  # Defender for Endpoint on Linux/macOS, no health query available
        names = ", ".join(sorted(set(found.values())))
        return Outcome(PASS, f"EDR running: {names} (process observed)", RUNNING, ev, method)
    return Outcome(FAIL, "No known EDR/anti-malware process is running", ABSENT, ev, method)


# ------------------------------------------------------------------ BACKUP (warranty)
def backup(last_success: datetime | None, source: str | None, agents: list, p: dict, now: datetime,
           method: str) -> Outcome:
    age = _days(now, last_success)
    ev = {"last_success": iso(last_success), "age_days": age, "source": source, "backup_software": agents,
          "max_backup_age_days": p["max_backup_age_days"], "restore_test_verified": False}
    note = " Restore testing cannot be verified from the endpoint; supply a dated restore-test record."
    if last_success is not None:
        if age <= p["max_backup_age_days"]:
            return Outcome(PASS, f"Last successful backup {age} days ago ({source}).{note}", OPERATING, ev, method)
        return Outcome(FAIL, f"Last successful backup {age} days ago (limit {p['max_backup_age_days']}) ({source})",
                       PRESENT, ev, method)
    if agents:
        return Outcome(NOT_SUPPORTED, f"Backup software detected ({', '.join(agents)}) but its last-success time is "
                                      f"not readable locally. Provide the backup job report, or configure the "
                                      f"job to write the KYH backup marker.", PRESENT, ev, method)
    return Outcome(NOT_SUPPORTED, "No local backup evidence found. Backups may run centrally; provide the backup "
                                  "job report as documentary evidence.", ABSENT, ev, method)


# ------------------------------------------------------------------ MFA (warranty)
def mfa(method: str = "not observable from an endpoint") -> Outcome:
    return Outcome(NOT_SUPPORTED, "MFA is enforced by the identity provider, not the endpoint. Evidence must come "
                                  "from an IdP export or connector (e.g. Entra ID / Google Workspace sign-in policy).",
                   None, {"guidance": "Upload the IdP conditional-access / 2-step verification policy export."}, method)


# ------------------------------------------------------------------ disk encryption
def disk_encryption(encrypted: bool, detail: dict, method: str, suspended: bool = False) -> Outcome:
    if encrypted and not suspended:
        return Outcome(PASS, "System drive is encrypted", OPERATING, detail, method)
    if encrypted and suspended:
        return Outcome(FAIL, "System drive is encrypted but protection is suspended", PRESENT, detail, method)
    return Outcome(FAIL, "System drive is not encrypted", ABSENT, detail, method)


# ------------------------------------------------------------------ firewall
def firewall(enabled: bool, detail: dict, method: str) -> Outcome:
    if enabled:
        return Outcome(PASS, "Host firewall is enabled", OPERATING, detail, method)
    return Outcome(FAIL, "Host firewall is disabled or has no filtering rules", ABSENT, detail, method)


# ------------------------------------------------------------------ exposed services
def exposed_services(listeners: list, p: dict, method: str) -> Outcome:
    critical = {int(k): v for k, v in p["critical_ports"].items()}
    review = {int(k): v for k, v in p["review_ports"].items()}
    allow = set(int(x) for x in p.get("allow_ports", []))
    exposed = sorted({port for ip, port in listeners if not is_loopback(ip)})
    crit = [{"port": x, "service": critical[x]} for x in exposed if x in critical and x not in allow]
    rev = [{"port": x, "service": review[x]} for x in exposed if x in review and x not in allow]
    ev = {"listening_ports_non_loopback": exposed, "critical": crit, "review": rev,
          "note": "Local view only. Whether a port is reachable from the internet needs an outside-in scan."}
    if crit:
        names = ", ".join(f"{c['service']} ({c['port']})" for c in crit)
        return Outcome(FAIL, f"High-risk service listening on a network interface: {names}", None, ev, method)
    if rev:
        names = ", ".join(f"{c['service']} ({c['port']})" for c in rev)
        return Outcome(PASS, f"No high-risk listeners. Review: {names}", None, ev, method)
    return Outcome(PASS, "No high-risk services listening on network interfaces", None, ev, method)


# ------------------------------------------------------------------ remote access
def ssh_hardening(cfg: dict, p: dict, method: str) -> Outcome:
    root = cfg.get("permitrootlogin", "prohibit-password")   # OpenSSH >= 7.0 default
    pw = cfg.get("passwordauthentication", "yes")             # OpenSSH default
    empty = cfg.get("permitemptypasswords", "no")
    ev = {"permitrootlogin": root, "passwordauthentication": pw, "permitemptypasswords": empty}
    problems = []
    if root == "yes":
        problems.append("root can log in with a password (PermitRootLogin yes)")
    if empty == "yes":
        problems.append("empty passwords allowed")
    if pw == "yes" and p.get("require_key_auth", True):
        problems.append("password authentication enabled (keys required by policy)")
    if problems:
        return Outcome(FAIL, "SSH server: " + "; ".join(problems), None, ev, method)
    return Outcome(PASS, "SSH server hardened (no root password login, key-based auth)", None, ev, method)


def rdp_hardening(rdp_enabled: bool, nla: bool, method: str) -> Outcome:
    ev = {"rdp_enabled": rdp_enabled, "nla_required": nla}
    if not rdp_enabled:
        return Outcome(NOT_APPLICABLE, "Remote Desktop is disabled", None, ev, method)
    if nla:
        return Outcome(PASS, "Remote Desktop enabled with Network Level Authentication", None, ev, method)
    return Outcome(FAIL, "Remote Desktop enabled WITHOUT Network Level Authentication", None, ev, method)


# ------------------------------------------------------------------ admin accounts
def admin_accounts(count: int, hashed: list, extra_uid0: int, guest_enabled: bool, p: dict, method: str) -> Outcome:
    ev = {"admin_count": count, "admin_ids_hashed": hashed, "extra_uid0_accounts": extra_uid0,
          "guest_enabled": guest_enabled, "max_local_admins": p["max_local_admins"],
          "privacy": "Account names are salted-hashed on the endpoint; only counts leave the machine in clear."}
    problems = []
    if extra_uid0:
        problems.append(f"{extra_uid0} extra account(s) with UID 0")
    if guest_enabled:
        problems.append("Guest account enabled")
    if count > p["max_local_admins"]:
        problems.append(f"{count} local administrators (limit {p['max_local_admins']})")
    if problems:
        return Outcome(FAIL, "; ".join(problems), None, ev, method)
    return Outcome(PASS, f"{count} local administrator(s); no guest or hidden root accounts", None, ev, method)


# ------------------------------------------------------------------ OS support
def os_support(label: str, eol: str | None, p: dict, now: datetime, method: str, known: bool = True) -> Outcome:
    ev = {"os": label, "end_of_support": eol, "table_as_of": p.get("as_of"),
          "note": "Lifecycle dates are policy data; verify against vendor lifecycle pages."}
    if not known:
        return Outcome(NOT_SUPPORTED, f"No lifecycle data for {label}; add it to the policy table", None, ev, method)
    if eol is None:
        return Outcome(PASS, f"{label} is supported", None, ev, method)
    days_left = (date.fromisoformat(eol) - now.date()).days
    ev["days_to_end_of_support"] = days_left
    if days_left < 0:
        return Outcome(FAIL, f"{label} reached end of vendor support on {eol}", None, ev, method)
    if days_left <= p.get("warn_days", 90):
        return Outcome(PASS, f"{label} supported, but support ends on {eol} ({days_left} days)", None, ev, method)
    return Outcome(PASS, f"{label} supported until {eol}", None, ev, method)


# ------------------------------------------------------------------ logging (CERT-In)
def log_retention(active: bool, forwarder: str | None, retained_days: float | None, p: dict, method: str) -> Outcome:
    need = p["required_retention_days"]
    ev = {"logging_active": active, "forwarder": forwarder, "local_retained_days": retained_days,
          "required_retention_days": need,
          "basis": "CERT-In Directions (28 Apr 2022): enable ICT logs and keep them 180 days within India"}
    if not active:
        return Outcome(FAIL, "System event logging is not active", ABSENT, ev, method)
    if forwarder:
        return Outcome(PASS, f"Logs forwarded off-host by {forwarder}; the {need}-day retention must be shown "
                             f"at the central log store", RUNNING, ev, method)
    if retained_days is not None and retained_days >= need:
        return Outcome(PASS, f"Local logs cover {retained_days} days (>= {need})", OPERATING, ev, method)
    have = "unknown" if retained_days is None else f"{retained_days} days"
    return Outcome(FAIL, f"Local logs cover {have} (< {need}) and no log forwarder was detected", PRESENT, ev, method)


# ------------------------------------------------------------------ time sync (CERT-In)
def time_sync(synchronized: bool | None, sources: list, p: dict, method: str, hierarchy: bool = False) -> Outcome:
    approved = p["approved_sources"]
    ok = [s for s in sources if host_matches(s, approved)]
    ev = {"synchronized": synchronized, "sources": sources, "approved_sources": approved,
          "domain_hierarchy": hierarchy,
          "basis": "CERT-In Directions (28 Apr 2022): sync ICT clocks to NIC/NPL NTP or sources traceable to them"}
    if synchronized is False:
        return Outcome(FAIL, "System clock is not synchronised to any time source", ABSENT, ev, method)
    if hierarchy:
        return Outcome(PASS, "Clock follows the Windows domain hierarchy; confirm the domain's PDC emulator syncs "
                             "to NIC/NPL", RUNNING, ev, method)
    if ok:
        level = OPERATING if synchronized else RUNNING
        return Outcome(PASS, f"Clock synchronised to approved source {ok[0]}", level, ev, method)
    if not sources:
        return Outcome(FAIL, "No NTP source configured", ABSENT, ev, method)
    if p.get("require_nic_npl_source", True):
        return Outcome(FAIL, f"Clock synchronised to {', '.join(sources[:3])}, not a NIC/NPL server. Switch to "
                             f"samay1.nic.in / time.nplindia.org or document traceability.", PRESENT, ev, method)
    return Outcome(PASS, f"Clock synchronised to {', '.join(sources[:3])}", RUNNING, ev, method)
