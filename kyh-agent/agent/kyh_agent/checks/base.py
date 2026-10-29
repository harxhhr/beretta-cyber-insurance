"""Shared building blocks for checks: result type, status vocabulary, safe command runner."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

# ---- Result status: did the control hold on this machine? --------------------------
PASS = "PASS"                        # control observed and meets the policy threshold
FAIL = "FAIL"                        # control observed and does not meet the threshold
NOT_APPLICABLE = "NOT_APPLICABLE"    # control does not apply here (e.g. no SSH server installed)
NOT_SUPPORTED = "NOT_SUPPORTED"      # cannot be observed from this endpoint (e.g. MFA, or needs admin)
ERROR = "ERROR"                      # the check itself failed (timeout, crash, unparseable output)
STATUSES = (PASS, FAIL, NOT_APPLICABLE, NOT_SUPPORTED, ERROR)

# ---- Assurance: how strongly was the control seen to be working? -------------------
OPERATING = "OPERATING"  # running and a health signal confirmed it is effective
RUNNING = "RUNNING"      # running/configured, but effectiveness is not verifiable locally
PRESENT = "PRESENT"      # installed, but not effective (stopped, stale, suspended)
ABSENT = "ABSENT"        # not found at all
ASSURANCE_LEVELS = (OPERATING, RUNNING, PRESENT, ABSENT, None)

IS_WINDOWS = sys.platform.startswith("win")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Outcome:
    """What a check function returns. The runner wraps it into a CheckResult."""
    status: str
    summary: str
    assurance: str | None = None
    evidence: dict = field(default_factory=dict)
    method: str = ""


@dataclass
class CheckResult:
    check_id: str
    control: str
    tier: str
    status: str
    summary: str
    assurance: str | None = None
    evidence: dict = field(default_factory=dict)
    method: str = ""
    platform: str = ""
    observed_at: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class ToolMissing(Exception):
    """The OS tool a check needs is not installed on this machine."""


class NeedsPrivilege(Exception):
    """The check needs administrator/root rights the agent does not have."""


def run_cmd(args, timeout: float = 30, input_text: str | None = None):
    """Run an OS command safely and return (returncode, stdout, stderr).

    Safety rules enforced here, in one place:
      * args must be a list — never a shell string, never shell=True
      * every call has a timeout (subprocess.TimeoutExpired propagates to the runner)
      * locale forced to C so output parses the same on every machine
      * no console window flashes on Windows
    """
    if not isinstance(args, (list, tuple)) or not args:
        raise ValueError("run_cmd requires a non-empty argument list")
    env = dict(os.environ)
    env.update({"LC_ALL": "C", "LANG": "C"})
    kwargs = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            [str(a) for a in args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            shell=False,
            env=env,
            stdin=subprocess.DEVNULL if input_text is None else None,
            input=input_text,
            **kwargs,
        )
    except FileNotFoundError as exc:
        raise ToolMissing(str(args[0])) from exc
    return proc.returncode, proc.stdout, proc.stderr


def run_powershell(script: str, timeout: float = 60):
    """Run a read-only PowerShell snippet (Windows only)."""
    return run_cmd(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=timeout,
    )


def looks_like_access_denied(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ("access is denied", "access denied", "permission denied",
                                "requires elevation", "administrator", "operation not permitted",
                                "must be run as root", "you need to be root"))


def read_text(path: str, limit: int = 2_000_000) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except PermissionError as exc:
        raise NeedsPrivilege(f"cannot read {path}") from exc
