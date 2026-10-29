"""macOS collectors (best-effort tier: Windows and Linux are the primary platforms)."""

from __future__ import annotations

import platform
import re

from . import parsers as P
from . import verdicts as V
from .base import ERROR, FAIL, NOT_APPLICABLE, NOT_SUPPORTED, Outcome, NeedsPrivilege, read_text, run_cmd
from .linux import _expand_sshd


def _processes():
    rc, out, _ = run_cmd(["ps", "-axo", "comm="], timeout=20)
    return out.splitlines() if rc == 0 else []


def patch(p, ctx) -> Outcome:
    rc, out, err = run_cmd(["softwareupdate", "-l"], timeout=p.get("timeout", 240))
    if rc != 0:
        return Outcome(ERROR, f"softwareupdate failed: {(err or out).strip()[:200]}", method="softwareupdate -l")
    facts = P.parse_softwareupdate_list(out + err)
    facts.update({"last_update": None, "index_age_days": None})
    return V.patching(facts, p, ctx.now, "softwareupdate -l")


def edr(p, ctx) -> Outcome:
    return V.edr(P.match_known_processes(_processes(), p["known_processes"]), None, p, "ps process table")


def backup(p, ctx) -> Outcome:
    for path in p["marker_paths"].get("darwin", []):
        txt = read_text(path)
        if txt and P.parse_iso(txt.strip().splitlines()[0]):
            return V.backup(P.parse_iso(txt.strip().splitlines()[0]), f"marker {path}", [], p, ctx.now, "marker file")
    rc, out, _ = run_cmd(["tmutil", "latestbackup"], timeout=30)
    m = re.search(r"(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})(\d{2})", out or "")
    if rc == 0 and m:
        ts = P.parse_iso(f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4)}")
        return V.backup(ts, "Time Machine", [], p, ctx.now, "tmutil latestbackup")
    agents = P.match_process_keywords(_processes(), p["process_keywords"])
    return V.backup(None, None, agents, p, ctx.now, "marker + tmutil + process table")


def disk_encryption(p, ctx) -> Outcome:
    rc, out, _ = run_cmd(["fdesetup", "status"], timeout=20)
    info = P.parse_fdesetup(out)
    return V.disk_encryption(info["filevault_on"], info, "fdesetup status")


def firewall(p, ctx) -> Outcome:
    rc, out, _ = run_cmd(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"], timeout=20)
    state = P.parse_socketfilterfw(out)
    if state is None:
        return Outcome(ERROR, "Could not read Application Firewall state", method="socketfilterfw")
    return V.firewall(state, {"tool": "Application Firewall", "raw": out.strip()[:200]}, "socketfilterfw")


def _listeners():
    rc, out, _ = run_cmd(["netstat", "-anv", "-p", "tcp"], timeout=30)
    return P.parse_netstat_listen(out)


def exposed_services(p, ctx) -> Outcome:
    return V.exposed_services(_listeners(), p, "netstat -anv -p tcp")


def remote_access(p, ctx) -> Outcome:
    if not any(port == 22 and not P.is_loopback(ip) for ip, port in _listeners()):
        return Outcome(NOT_APPLICABLE, "Remote Login (SSH) is off", method="netstat")
    return V.ssh_hardening(P.parse_sshd_config(_expand_sshd("/etc/ssh/sshd_config")), p, "/etc/ssh/sshd_config")


def admin_accounts(p, ctx) -> Outcome:
    rc, out, _ = run_cmd(["dscl", ".", "-read", "/Groups/admin", "GroupMembership"], timeout=20)
    admins = P.parse_dscl_group(out)
    return V.admin_accounts(len(admins), [ctx.hash_id(a) for a in admins], 0, False, p, "dscl admin group")


def os_support(p, ctx) -> Outcome:
    ver = platform.mac_ver()[0] or "0"
    major = int(ver.split(".")[0])
    label = f"macOS {ver}"
    minimum = p["eol"]["darwin_min_major"]
    if major < minimum:
        return Outcome(FAIL, f"{label} is older than the oldest macOS still receiving security updates "
                               f"(policy minimum {minimum})", None, {"os": label, "min_major": minimum}, "sw_vers")
    return V.os_support(label, None, p, ctx.now, "platform.mac_ver")


def log_retention(p, ctx) -> Outcome:
    fwd = P.match_known_processes(_processes(), p["forwarder_processes"])
    if fwd:
        return V.log_retention(True, ", ".join(sorted(set(fwd.values()))), None, p, "process table")
    return Outcome(NOT_SUPPORTED, "Unified-log retention is not measurable locally on macOS; forward logs to a "
                                  "central store to evidence 180-day retention", None, {}, "process table")


def time_sync(p, ctx) -> Outcome:
    sources, synced = [], None
    rc, out, err = run_cmd(["systemsetup", "-getnetworktimeserver"], timeout=20)
    m = re.search(r"Network Time Server:\s*(\S+)", out or "")
    if m:
        sources.append(m.group(1).lower())
    rc2, out2, _ = run_cmd(["systemsetup", "-getusingnetworktime"], timeout=20)
    if "Network Time:" in (out2 or ""):
        synced = "On" in out2
    sources += P.parse_chrony_conf(read_text("/etc/ntp.conf") or "")
    if not sources and synced is None:
        raise NeedsPrivilege("systemsetup requires administrator rights")
    return V.time_sync(synced, list(dict.fromkeys(sources)), p, "systemsetup + /etc/ntp.conf")
