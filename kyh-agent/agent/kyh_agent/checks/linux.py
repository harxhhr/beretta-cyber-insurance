"""Linux collectors: gather raw facts from the OS (read-only) and hand them to verdicts."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from datetime import datetime, timezone

from . import parsers as P
from . import verdicts as V
from .base import (ERROR, NOT_APPLICABLE, NOT_SUPPORTED, NeedsPrivilege, Outcome, ToolMissing,
                   looks_like_access_denied, read_text, run_cmd)

IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def _mtime(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except OSError:
        return None


def list_processes() -> list:
    """Process names from /proc without spawning anything: comm + basename(argv[0])."""
    names = []
    for pid_dir in glob.glob("/proc/[0-9]*"):
        try:
            with open(pid_dir + "/comm", "r", errors="replace") as fh:
                names.append(fh.read().strip())
            with open(pid_dir + "/cmdline", "rb") as fh:
                argv0 = fh.read().split(b"\0", 1)[0].decode(errors="replace")
            if argv0:
                names.append(os.path.basename(argv0.split()[0]))
        except OSError:
            continue
    return names


# ----------------------------------------------------------------------------- PATCH
def patch(p, ctx) -> Outcome:
    if shutil.which("apt-get"):
        rc, out, err = run_cmd(["apt-get", "-s", "-o", "Debug::NoLocking=1", "upgrade"], timeout=p.get("timeout", 120))
        if rc != 0:
            return Outcome(ERROR, f"apt-get simulation failed: {err.strip()[:200]}", method="apt-get -s upgrade")
        facts = P.parse_apt_simulate(out)
        stamp = _mtime("/var/lib/apt/periodic/update-success-stamp")
        lists = [m for m in (_mtime(f) for f in glob.glob("/var/lib/apt/lists/*Release")) if m]
        newest_index = max([x for x in [stamp] + lists if x], default=None)
        facts["index_age_days"] = None if newest_index is None else round(
            (ctx.now - newest_index).total_seconds() / 86400, 1)
        logs = "".join(read_text(f) or "" for f in ("/var/log/dpkg.log.1", "/var/log/dpkg.log"))
        facts["last_update"] = P.parse_last_package_change(logs)
        return V.patching(facts, p, ctx.now, "apt-get -s upgrade + /var/log/dpkg.log")
    if shutil.which("dnf"):
        rc, out, err = run_cmd(["dnf", "-q", "--cacheonly", "updateinfo", "list", "--security"],
                               timeout=p.get("timeout", 120))
        if rc != 0:
            return Outcome(ERROR, f"dnf updateinfo failed: {err.strip()[:200]}", method="dnf updateinfo")
        facts = P.parse_dnf_security(out)
        facts["last_update"] = P.parse_last_package_change(read_text("/var/log/dnf.rpm.log") or "")
        facts["index_age_days"] = None
        return V.patching(facts, p, ctx.now, "dnf updateinfo list --security + /var/log/dnf.rpm.log")
    return Outcome(NOT_SUPPORTED, "No supported package manager (apt or dnf) found", method="package manager")


# ----------------------------------------------------------------------------- EDR
def edr(p, ctx) -> Outcome:
    found = P.match_known_processes(list_processes(), p["known_processes"])
    health = None
    if "wdavdaemon" in found and shutil.which("mdatp"):
        try:
            rc, out, _ = run_cmd(["mdatp", "health", "--field", "healthy"], timeout=20)
            if rc == 0 and out.strip() in ("true", "false"):
                health = {"product": "Microsoft Defender for Endpoint", "healthy": out.strip() == "true"}
        except (ToolMissing, subprocess.TimeoutExpired):
            pass
    return V.edr(found, None, p, "/proc process table" + (" + mdatp health" if health else ""), health)


# ----------------------------------------------------------------------------- BACKUP
def backup(p, ctx) -> Outcome:
    for path in p["marker_paths"].get("linux", []):
        txt = read_text(path)
        if txt:
            ts = P.parse_iso(txt.strip().splitlines()[0])
            if ts:
                return V.backup(ts, f"marker {path}", [], p, ctx.now, "KYH backup marker file")
    agents = P.match_process_keywords(list_processes(), p["process_keywords"])
    return V.backup(None, None, agents, p, ctx.now, "marker file + process table")


# ----------------------------------------------------------------------------- DISK
def disk_encryption(p, ctx) -> Outcome:
    try:
        rc, out, err = run_cmd(["lsblk", "-J", "-o", "NAME,TYPE,MOUNTPOINTS"], timeout=20)
        if rc != 0:  # older util-linux has MOUNTPOINT only
            rc, out, err = run_cmd(["lsblk", "-J", "-o", "NAME,TYPE,MOUNTPOINT"], timeout=20)
    except ToolMissing:
        return Outcome(NOT_SUPPORTED, "lsblk not available", method="lsblk")
    if rc != 0:
        return Outcome(ERROR, f"lsblk failed: {err.strip()[:200]}", method="lsblk")
    info = P.lsblk_root_is_encrypted(out)
    if not info["root_found"]:
        return Outcome(NOT_SUPPORTED, "Root filesystem is not on a local block device (container, network or "
                                      "unusual layout)", evidence=info, method="lsblk")
    return V.disk_encryption(info["encrypted"], info, "lsblk (dm-crypt/LUKS in root device chain)")


# ----------------------------------------------------------------------------- FIREWALL
def firewall(p, ctx) -> Outcome:
    tried = []
    if shutil.which("ufw"):
        rc, out, err = run_cmd(["ufw", "status"], timeout=20)
        if rc == 0 and P.parse_ufw_status(out) is not None:
            active = P.parse_ufw_status(out)
            if active:
                return V.firewall(True, {"tool": "ufw", "status": "active"}, "ufw status")
            tried.append("ufw inactive")
        elif looks_like_access_denied(err + out):
            tried.append("ufw needs root")
    if shutil.which("firewall-cmd"):
        rc, out, _ = run_cmd(["firewall-cmd", "--state"], timeout=20)
        if out.strip() == "running":
            return V.firewall(True, {"tool": "firewalld", "state": "running"}, "firewall-cmd --state")
        tried.append("firewalld not running")
    if shutil.which("nft"):
        rc, out, err = run_cmd(["nft", "list", "ruleset"], timeout=20)
        if rc == 0:
            info = P.parse_nft_ruleset(out)
            if info["protective"]:
                return V.firewall(True, {"tool": "nftables", **info}, "nft list ruleset")
            tried.append(f"nftables: {info['input_chains']} input chain(s), none filtering")
        elif looks_like_access_denied(err):
            tried.append("nft needs root")
    if shutil.which("iptables"):
        rc, out, err = run_cmd(["iptables", "-S", "INPUT"], timeout=20)
        if rc == 0:
            info = P.parse_iptables_s(out)
            if info["protective"]:
                return V.firewall(True, {"tool": "iptables", **info}, "iptables -S INPUT")
            tried.append("iptables: INPUT accepts all")
        elif looks_like_access_denied(err):
            tried.append("iptables needs root")
    if tried and all("needs root" in t for t in tried):
        raise NeedsPrivilege("firewall state needs root: " + "; ".join(tried))
    return V.firewall(False, {"checked": tried or ["no firewall tool found"]}, "ufw/firewalld/nft/iptables")


# ----------------------------------------------------------------------------- LISTENERS
def exposed_services(p, ctx) -> Outcome:
    listeners = P.parse_proc_net_tcp(read_text("/proc/net/tcp") or "", ipv6=False)
    listeners += P.parse_proc_net_tcp(read_text("/proc/net/tcp6") or "", ipv6=True)
    return V.exposed_services(listeners, p, "/proc/net/tcp{,6}")


# ----------------------------------------------------------------------------- REMOTE ACCESS
def _expand_sshd(path, seen=None):
    seen = seen if seen is not None else set()
    if path in seen:
        return []
    seen.add(path)
    text = read_text(path)
    if text is None:
        return []
    out = []
    # Include directives are processed in place: expand them before the lines that follow.
    target = []
    for line in text.splitlines():
        if line.strip().lower().startswith("include"):
            out.append((path, "\n".join(target)))
            target = []
            for pat in P.sshd_includes(line):
                pat = pat if os.path.isabs(pat) else os.path.join("/etc/ssh", pat)
                for inc in sorted(glob.glob(pat)):
                    out.extend(_expand_sshd(inc, seen))
            continue
        target.append(line)
    out.append((path, "\n".join(target)))
    return out


def remote_access(p, ctx) -> Outcome:
    sshd = shutil.which("sshd") or ("/usr/sbin/sshd" if os.path.exists("/usr/sbin/sshd") else None)
    if not sshd:
        return Outcome(NOT_APPLICABLE, "No SSH server installed", method="which sshd")
    if IS_ROOT:
        rc, out, _ = run_cmd([sshd, "-T"], timeout=20)
        if rc == 0 and out.strip():
            return V.ssh_hardening(P.parse_sshd_effective(out), p, "sshd -T (effective config)")
    cfg = P.parse_sshd_config(_expand_sshd("/etc/ssh/sshd_config"))
    return V.ssh_hardening(cfg, p, "/etc/ssh/sshd_config (+Include files)")


# ----------------------------------------------------------------------------- ADMINS
def admin_accounts(p, ctx) -> Outcome:
    info = P.parse_admin_members(read_text("/etc/group") or "", read_text("/etc/passwd") or "", p["admin_groups"])
    hashed = [ctx.hash_id(a) for a in info["admins"]]
    return V.admin_accounts(len(info["admins"]), hashed, len(info["extra_uid0"]), False, p,
                            "/etc/group + /etc/passwd")


# ----------------------------------------------------------------------------- OS SUPPORT
def os_support(p, ctx) -> Outcome:
    rel = P.parse_os_release(read_text("/etc/os-release") or "")
    distro, ver = rel.get("ID", "linux").lower(), rel.get("VERSION_ID", "")
    label = rel.get("PRETTY_NAME") or f"{distro} {ver}"
    table = p["eol"]["linux"]
    key = f"{distro}:{ver}"
    if key not in table:
        key = f"{distro}:{ver.split('.')[0]}"  # RHEL-family majors, e.g. rocky:9
    if key not in table:
        return V.os_support(label, None, p, ctx.now, "/etc/os-release", known=False)
    return V.os_support(label, table[key], p, ctx.now, "/etc/os-release")


# ----------------------------------------------------------------------------- LOGGING
def _first_journal_entry():
    if not shutil.which("journalctl"):
        return None
    try:
        proc = subprocess.Popen(["journalctl", "-o", "short-iso", "-q", "--no-pager"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, env={"LC_ALL": "C", "PATH": os.environ.get("PATH", "")})
        line = proc.stdout.readline()
        proc.kill()
        proc.wait(timeout=5)
        return P.parse_journal_first_line(line)
    except OSError:
        return None


def log_retention(p, ctx) -> Outcome:
    procs = list_processes()
    syslog = P.match_known_processes(procs, {"rsyslogd": "rsyslog", "syslog-ng": "syslog-ng",
                                             "systemd-journald": "journald"})
    active = bool(syslog) or os.path.exists("/run/systemd/journal/socket")
    fwd = P.match_known_processes(procs, p["forwarder_processes"])
    forwarder = ", ".join(sorted(set(fwd.values()))) or None
    if not forwarder:
        conf = "".join(read_text(f) or "" for f in ["/etc/rsyslog.conf"] + sorted(glob.glob("/etc/rsyslog.d/*.conf")))
        if P.rsyslog_forwards(conf):
            forwarder = "rsyslog remote forwarding"
    oldest = []
    for pat in ("/var/log/syslog*", "/var/log/messages*", "/var/log/auth.log*", "/var/log/secure*"):
        oldest += [m for m in (_mtime(f) for f in glob.glob(pat)) if m]
    j = _first_journal_entry()
    if j:
        oldest.append(j)
    retained = round((ctx.now - min(oldest)).total_seconds() / 86400, 1) if oldest else None
    return V.log_retention(active, forwarder, retained, p,
                           "process table + rsyslog config + oldest /var/log file / first journal entry")


# ----------------------------------------------------------------------------- TIME SYNC
def time_sync(p, ctx) -> Outcome:
    synced, sources, method = None, [], []
    if shutil.which("timedatectl"):
        try:
            rc, out, _ = run_cmd(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], timeout=10)
            if rc == 0 and out.strip() in ("yes", "no"):
                synced = out.strip() == "yes"
                method.append("timedatectl")
            rc, out, _ = run_cmd(["timedatectl", "show-timesync", "-p", "ServerName", "--value"], timeout=10)
            if rc == 0 and out.strip():
                sources.append(out.strip().lower())
        except ToolMissing:
            pass
    if shutil.which("chronyc"):
        try:
            rc, out, _ = run_cmd(["chronyc", "-n", "sources"], timeout=10)
            if rc == 0:
                s = P.parse_chronyc_sources(out)
                if s["selected"]:
                    sources.append(s["selected"])
                method.append("chronyc sources")
        except ToolMissing:
            pass
    for f in ["/etc/chrony/chrony.conf", "/etc/chrony.conf"] + sorted(glob.glob("/etc/chrony/sources.d/*.sources")):
        sources += P.parse_chrony_conf(read_text(f) or "")
    ts = "".join(read_text(f) or "" for f in ["/etc/systemd/timesyncd.conf"] +
                 sorted(glob.glob("/etc/systemd/timesyncd.conf.d/*.conf")))
    sources += P.parse_timesyncd_conf(ts)
    sources += P.parse_chrony_conf(read_text("/etc/ntp.conf") or "")
    sources = list(dict.fromkeys(sources))  # de-duplicate, keep order
    return V.time_sync(synced, sources, p, " + ".join(method + ["NTP config files"]))
