"""Pure parsers: raw OS output in, plain Python facts out.

Nothing in this module touches the operating system, which is what makes every
parser unit-testable with fixture text captured from real machines.
"""

from __future__ import annotations

import fnmatch
import json
import re
import socket
import struct
from datetime import datetime, timezone

# ============================================================== patching

def parse_apt_simulate(text: str) -> dict:
    """Parse `apt-get -s upgrade` output. Lines look like:
    Inst libssl3 [3.0.2-0ubuntu1.10] (3.0.2-0ubuntu1.12 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])
    """
    total, security = 0, []
    for line in (text or "").splitlines():
        if not line.startswith("Inst "):
            continue
        total += 1
        if "-security" in line or "Debian-Security" in line:
            security.append(line.split()[1])
    return {"pending_total": total, "pending_security": len(security), "security_packages": security[:25]}


def parse_dnf_security(text: str) -> dict:
    """Parse `dnf -q updateinfo list --security` output: `RHSA-2024:1234 Important/Sec. openssl-3.0.7...`"""
    pkgs = set()
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 3 and ("/Sec" in parts[1] or parts[0].upper().startswith(("RHSA", "ALSA", "RLSA", "FEDORA", "ELSA"))):
            pkgs.add(parts[2])
    return {"pending_security": len(pkgs), "security_packages": sorted(pkgs)[:25]}


_DPKG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (upgrade|install) ")
_RPM_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\S*\s+\S+\s+(Upgrade|Upgraded|Installed|Install):")


def parse_last_package_change(text: str) -> datetime | None:
    """Most recent install/upgrade time from dpkg.log or dnf.rpm.log text (local time assumed UTC)."""
    last = None
    for line in (text or "").splitlines():
        m = _DPKG_TS.match(line)
        if m:
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        else:
            m = _RPM_TS.match(line)
            if not m:
                continue
            ts = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
        ts = ts.replace(tzinfo=timezone.utc)
        if last is None or ts > last:
            last = ts
    return last


def parse_windows_updates(text: str) -> dict:
    """Parse the JSON produced by the Windows Update Agent search snippet in windows.py."""
    data = json.loads(text or "{}")
    pending = data.get("Pending") or []
    if isinstance(pending, dict):  # PowerShell unwraps single-element arrays
        pending = [pending]
    security = []
    for u in pending:
        sev = (u.get("Severity") or "").lower()
        cats = u.get("Categories") or []
        if isinstance(cats, str):
            cats = [cats]
        cats_l = [c.lower() for c in cats]
        if sev in ("critical", "important") or "security updates" in cats_l or "critical updates" in cats_l:
            security.append(u.get("Title", "?"))
    last = data.get("LastHotfix")
    return {
        "pending_total": len(pending),
        "pending_security": len(security),
        "security_packages": security[:25],
        "last_update": parse_iso(last) if last else None,
    }


def parse_softwareupdate_list(text: str) -> dict:
    """Parse macOS `softwareupdate -l`."""
    labels = re.findall(r"^\s*\* Label:\s*(.+)$", text or "", re.M)
    return {"pending_total": len(labels), "pending_security": len(labels), "security_packages": labels[:25]}


# ============================================================== processes

def normalise_process_name(name: str) -> str:
    name = (name or "").strip().replace("\\", "/").split("/")[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def match_known_processes(process_names, known: dict) -> dict:
    """Return {process_name: product} for running processes found in the `known` table."""
    running = {normalise_process_name(p) for p in process_names if p}
    table = {normalise_process_name(k): v for k, v in known.items()}
    return {p: table[p] for p in sorted(running) if p in table}


def match_process_keywords(process_names, keywords) -> list:
    running = {normalise_process_name(p) for p in process_names if p}
    return sorted({p for p in running for k in keywords if k.lower() in p})


def parse_defender_status(text: str) -> dict | None:
    """Parse `Get-MpComputerStatus | ConvertTo-Json` (selected fields)."""
    if not (text or "").strip():
        return None
    d = json.loads(text)
    return {
        "service_enabled": bool(d.get("AMServiceEnabled")),
        "antivirus_enabled": bool(d.get("AntivirusEnabled")),
        "realtime_enabled": bool(d.get("RealTimeProtectionEnabled")),
        "signature_age_days": d.get("AntivirusSignatureAge"),
        "running_mode": d.get("AMRunningMode") or "Normal",
    }


# ============================================================== disk encryption

def lsblk_root_is_encrypted(text: str) -> dict:
    """Walk `lsblk -J -o NAME,TYPE,MOUNTPOINT(S)` and report whether '/' sits on a dm-crypt layer."""
    data = json.loads(text or "{}")

    def mounts(node):
        mps = node.get("mountpoints")
        if mps is None:
            mps = [node.get("mountpoint")]
        return [m for m in mps if m]

    def walk(node, path):
        path = path + [node]
        if "/" in mounts(node):
            return path
        for child in node.get("children") or []:
            found = walk(child, path)
            if found:
                return found
        return None

    for dev in data.get("blockdevices") or []:
        path = walk(dev, [])
        if path:
            chain = [f"{n.get('name')}({n.get('type')})" for n in path]
            return {"root_found": True, "encrypted": any(n.get("type") == "crypt" for n in path), "chain": chain}
    return {"root_found": False, "encrypted": False, "chain": []}


def parse_bitlocker(text: str) -> dict | None:
    if not (text or "").strip():
        return None
    d = json.loads(text)
    if isinstance(d, list):
        d = d[0] if d else {}
    prot = str(d.get("ProtectionStatus", "")).strip()
    vol = str(d.get("VolumeStatus", "")).strip()
    return {
        "mount_point": d.get("MountPoint"),
        "protection_on": prot in ("On", "1"),
        "volume_status": vol,
        "fully_encrypted": vol in ("FullyEncrypted", "1"),
        "encryption_percentage": d.get("EncryptionPercentage"),
    }


def parse_manage_bde(text: str) -> dict:
    """`manage-bde -status C:` fallback (e.g. Windows Home device encryption)."""
    t = text or ""
    prot = re.search(r"Protection Status:\s*(.+)", t)
    conv = re.search(r"Conversion Status:\s*(.+)", t)
    prot_s = prot.group(1).strip() if prot else ""
    conv_s = conv.group(1).strip() if conv else ""
    return {"protection_on": "Protection On" in prot_s, "volume_status": conv_s,
            "fully_encrypted": "Fully Encrypted" in conv_s, "mount_point": None, "encryption_percentage": None}


def parse_fdesetup(text: str) -> dict:
    t = (text or "").strip()
    return {"filevault_on": "FileVault is On" in t, "in_progress": "in progress" in t.lower(), "raw": t[:200]}


# ============================================================== firewall

def parse_ufw_status(text: str) -> bool | None:
    m = re.search(r"^Status:\s*(\w+)", text or "", re.M)
    return None if not m else m.group(1).lower() == "active"


def parse_nft_ruleset(text: str) -> dict:
    """An nftables ruleset protects input if some input-hook chain drops by policy or has drop/reject rules."""
    chains, protective = 0, False
    current_is_input = False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("chain "):
            current_is_input = False
        if "hook input" in line:
            chains += 1
            current_is_input = True
            if re.search(r"policy\s+drop", line):
                protective = True
        elif current_is_input and re.search(r"\b(drop|reject)\b", line):
            protective = True
    return {"input_chains": chains, "protective": protective}


def parse_iptables_s(text: str) -> dict:
    policy_drop = bool(re.search(r"^-P INPUT (DROP|REJECT)", text or "", re.M))
    rules = len(re.findall(r"^-A INPUT .*-j (DROP|REJECT)", text or "", re.M))
    return {"policy_drop": policy_drop, "drop_rules": rules, "protective": policy_drop or rules > 0}


def parse_windows_firewall(text: str) -> dict:
    d = json.loads(text or "[]")
    if isinstance(d, dict):
        d = [d]
    profiles = {p.get("Name"): str(p.get("Enabled")).lower() in ("true", "1") for p in d}
    return {"profiles": profiles, "all_enabled": bool(profiles) and all(profiles.values()),
            "disabled": sorted(k for k, v in profiles.items() if not v)}


def parse_socketfilterfw(text: str) -> bool | None:
    m = re.search(r"State = (\d)", text or "")
    if m:
        return m.group(1) in ("1", "2")
    t = (text or "").lower()
    if "enabled" in t:
        return True
    if "disabled" in t:
        return False
    return None


# ============================================================== listening sockets

def _hex_to_ipv4(h: str) -> str:
    return socket.inet_ntop(socket.AF_INET, struct.pack("<I", int(h, 16)))


def _hex_to_ipv6(h: str) -> str:
    words = [struct.pack("<I", int(h[i:i + 8], 16)) for i in range(0, 32, 8)]
    return socket.inet_ntop(socket.AF_INET6, b"".join(words))


def parse_proc_net_tcp(text: str, ipv6: bool = False) -> list:
    """Parse /proc/net/tcp or /proc/net/tcp6; return [(ip, port)] for sockets in LISTEN (0A)."""
    out = []
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4 or parts[3] != "0A":
            continue
        ip_hex, port_hex = parts[1].split(":")
        ip = _hex_to_ipv6(ip_hex) if ipv6 else _hex_to_ipv4(ip_hex)
        out.append((ip, int(port_hex, 16)))
    return out


def parse_windows_listeners(text: str) -> list:
    d = json.loads(text or "[]")
    if isinstance(d, dict):
        d = [d]
    return [(str(x.get("LocalAddress")), int(x.get("LocalPort"))) for x in d if x.get("LocalPort") is not None]


def parse_netstat_listen(text: str) -> list:
    """macOS `netstat -anv -p tcp`: local address column like `*.22`, `127.0.0.1.631`, `::1.631`."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0].startswith("tcp") and "LISTEN" in parts:
            local = parts[3]
            if "." not in local:
                continue
            host, port = local.rsplit(".", 1)
            if port.isdigit():
                out.append(("0.0.0.0" if host == "*" else host, int(port)))
    return out


def is_loopback(ip: str) -> bool:
    ip = (ip or "").strip("[]")
    return ip.startswith("127.") or ip in ("::1", "localhost") or ip.startswith("::ffff:127.")


# ============================================================== SSH / RDP

def parse_sshd_effective(text: str) -> dict:
    """Parse `sshd -T` output (lower-case `key value` lines)."""
    out = {}
    for line in (text or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            out.setdefault(parts[0].lower(), parts[1].strip().lower())
    return out


def parse_sshd_config(files: list) -> dict:
    """Resolve sshd_config semantics from [(path, text)] already expanded in Include order.

    sshd uses the FIRST value it sees for each keyword; Match blocks apply only to
    matching connections, so they are ignored for the global view.
    """
    out = {}
    for _path, text in files:
        in_match = False
        for raw in (text or "").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.replace("=", " ", 1).split(None, 1)
            key = parts[0].lower()
            if key == "match":
                in_match = True
                continue
            if in_match or key == "include" or len(parts) < 2:
                continue
            out.setdefault(key, parts[1].strip().lower())
    return out


def sshd_includes(text: str) -> list:
    pats = []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.lower().startswith("include"):
            pats.extend(line.split()[1:])
    return pats


# ============================================================== accounts

def parse_admin_members(group_text: str, passwd_text: str, admin_groups) -> dict:
    admins = set()
    for line in (group_text or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 4 and parts[0] in admin_groups:
            admins.update(m for m in parts[3].split(",") if m)
    uid0 = []
    for line in (passwd_text or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[2] == "0":
            uid0.append(parts[0])
    extra_uid0 = [u for u in uid0 if u != "root"]
    admins.update(extra_uid0)
    admins.discard("root")
    return {"admins": sorted(admins), "extra_uid0": extra_uid0}


def parse_dscl_group(text: str) -> list:
    m = re.search(r"GroupMembership:\s*(.*)", text or "")
    return [u for u in (m.group(1).split() if m else []) if u != "root"]


def parse_windows_admins(text: str) -> dict:
    d = json.loads(text or "{}")
    admins = d.get("Admins") or []
    if isinstance(admins, str):
        admins = [admins]
    return {"admins": admins, "guest_enabled": bool(d.get("GuestEnabled"))}


# ============================================================== OS lifecycle

def parse_os_release(text: str) -> dict:
    out = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


# ============================================================== logging

def rsyslog_forwards(text: str) -> bool:
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if re.search(r"(^|\s)@@?[\w\[\]\.:-]+", line) or "omfwd" in line or "omrelp" in line:
            return True
    return False


def parse_wevtutil_first_date(text: str) -> datetime | None:
    m = re.search(r"Date:\s*(\S+)", text or "")
    return parse_iso(m.group(1)) if m else None


def parse_journal_first_line(line: str) -> datetime | None:
    """First line of `journalctl -o short-iso`: `2026-06-01T10:00:00+0530 host unit[1]: msg`."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-]\d{2}:?\d{2}|Z)?", (line or "").strip())
    if not m:
        return None
    return parse_iso(m.group(1) + (m.group(2) or "Z"))


# ============================================================== time sync

def parse_chrony_conf(text: str) -> list:
    out = []
    for raw in (text or "").splitlines():
        parts = raw.split("#", 1)[0].split()
        if len(parts) >= 2 and parts[0] in ("server", "pool", "peer"):
            out.append(parts[1].lower())
    return out


def parse_chronyc_sources(text: str) -> dict:
    """`chronyc -n sources`: the selected source line starts with `^*`."""
    selected, all_src = None, []
    for line in (text or "").splitlines():
        m = re.match(r"^\^([*+\-?x~])\s+(\S+)", line)
        if m:
            all_src.append(m.group(2).lower())
            if m.group(1) == "*":
                selected = m.group(2).lower()
    return {"selected": selected, "sources": all_src}


def parse_timesyncd_conf(text: str) -> list:
    """systemd-timesyncd uses NTP= servers; FallbackNTP= only when no NTP= is set."""
    primary, fallback = [], []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("NTP="):
            primary.extend(s.lower() for s in line.split("=", 1)[1].split())
        elif line.startswith("FallbackNTP="):
            fallback.extend(s.lower() for s in line.split("=", 1)[1].split())
    return primary or fallback


def parse_w32tm_status(text: str) -> dict:
    src = re.search(r"^Source:\s*(.+)$", text or "", re.M)
    leap = re.search(r"^Leap Indicator:\s*(\d)", text or "", re.M)
    source = src.group(1).strip() if src else None
    source_host = source.split(",")[0].strip().lower() if source else None
    unsynced = (leap and leap.group(1) == "3") or (source_host or "").startswith(("local cmos", "free-running"))
    return {"source": source_host, "synchronized": None if source is None else not unsynced}


def host_matches(host: str, approved) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == a or fnmatch.fnmatch(host, a) for a in (x.lower() for x in approved))


# ============================================================== utilities

def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    v = str(value).strip()
    m = re.match(r"^/Date\((\d+)", v)  # PowerShell 5 JSON dates
    if m:
        return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc)
    v = v.replace("Z", "+00:00")
    v = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", v)
    v = re.sub(r"\.(\d{6})\d+", r".\1", v)  # Windows 7-digit fractions
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
