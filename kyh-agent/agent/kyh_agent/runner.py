"""Runs checks safely: one platform function per check, a hard timeout, and every
failure mode mapped to an explicit status instead of a crash."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from .checks import DARWIN, LINUX, REGISTRY, WINDOWS
from .checks.base import (ERROR, NOT_SUPPORTED, CheckResult, NeedsPrivilege, Outcome, ToolMissing,
                          iso, utcnow)


def current_platform() -> str:
    if sys.platform.startswith("win"):
        return WINDOWS
    if sys.platform == "darwin":
        return DARWIN
    return LINUX


@dataclass
class Context:
    now: datetime
    salt: str = "unenrolled"

    def hash_id(self, name: str) -> str:
        """Salted hash so account names never leave the machine and cannot be linked across insureds."""
        return hashlib.sha256(f"{self.salt}:{name}".encode()).hexdigest()[:12]


class Runner:
    SLACK_SECONDS = 5  # extra time on top of a check's budget before it is abandoned

    def __init__(self, policy, platform: str | None = None, registry: dict | None = None,
                 clock=utcnow, salt: str = "unenrolled"):
        self.policy = policy
        self.platform = platform or current_platform()
        self.registry = registry or REGISTRY
        self.clock = clock
        self.salt = salt

    def run_one(self, check_id: str) -> CheckResult:
        spec = self.policy.by_id[check_id]
        params = spec.get("params", {})
        fn = self.registry.get(check_id, {}).get(self.platform)
        started = time.monotonic()
        ctx = Context(now=self.clock(), salt=self.salt)
        if fn is None:
            outcome = Outcome(NOT_SUPPORTED, f"No implementation for {self.platform}", method="n/a")
        else:
            outcome = self._guarded(fn, params, ctx, self.policy.timeout(check_id))
        return CheckResult(
            check_id=check_id, control=spec["control"], tier=spec["tier"],
            status=outcome.status, summary=outcome.summary, assurance=outcome.assurance,
            evidence=outcome.evidence, method=outcome.method, platform=self.platform,
            observed_at=iso(ctx.now), duration_ms=int((time.monotonic() - started) * 1000),
        )

    def run(self, check_ids=None) -> list:
        ids = list(check_ids) if check_ids is not None else [c["id"] for c in self.policy.checks]
        return [self.run_one(cid) for cid in ids]

    @classmethod
    def _guarded(cls, fn, params, ctx, timeout) -> Outcome:
        box = {}

        def target():
            try:
                box["out"] = fn(params, ctx)
            except NeedsPrivilege as exc:
                box["out"] = Outcome(NOT_SUPPORTED, f"Requires administrator/root rights ({exc})",
                                     evidence={"requires_admin": True}, method="privilege check")
            except ToolMissing as exc:
                box["out"] = Outcome(NOT_SUPPORTED, f"Required OS tool not installed: {exc}", method="tool lookup")
            except subprocess.TimeoutExpired as exc:
                box["out"] = Outcome(ERROR, f"OS command timed out: {' '.join(map(str, exc.cmd))[:120]}",
                                     method="timeout")
            except Exception as exc:  # noqa: BLE001 - a broken check must never kill the agent
                box["out"] = Outcome(ERROR, f"Check crashed: {type(exc).__name__}: {str(exc)[:200]}",
                                     method="exception")

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout + cls.SLACK_SECONDS)
        if t.is_alive():
            return Outcome(ERROR, f"Check exceeded its {int(timeout)}s time budget", method="timeout")
        out = box.get("out")
        if not isinstance(out, Outcome):
            return Outcome(ERROR, "Check returned no result", method="exception")
        return out
