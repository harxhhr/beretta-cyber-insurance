"""Load and validate the check policy (a data file, never code)."""

from __future__ import annotations

import hashlib
import json
import os

from .checks import REGISTRY

DEFAULT_POLICY = os.path.join(os.path.dirname(__file__), "policy.json")
TIERS = ("warranty", "important", "regulatory")
_SIMPLE = (str, int, float, bool, type(None))


class PolicyError(ValueError):
    pass


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _only_data(value, where):
    """Params may only contain plain data (no code, no callables)."""
    if isinstance(value, _SIMPLE):
        return
    if isinstance(value, list):
        for v in value:
            _only_data(v, where)
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise PolicyError(f"{where}: non-string key")
            _only_data(v, where)
        return
    raise PolicyError(f"{where}: unsupported value type {type(value).__name__}")


class Policy:
    def __init__(self, doc: dict):
        self.doc = doc
        self.meta = doc["policy"]
        self.defaults = doc.get("defaults", {})
        self.checks = doc["checks"]
        self.by_id = {c["id"]: c for c in self.checks}
        self.hash = hashlib.sha256(canonical_json(doc)).hexdigest()

    @property
    def id(self):
        return self.meta["id"]

    @property
    def version(self):
        return self.meta["version"]

    def interval_seconds(self, check_id: str) -> int:
        return int(self.by_id[check_id].get("interval_minutes", 1440)) * 60

    def timeout(self, check_id: str) -> float:
        return float(self.by_id[check_id].get("timeout_seconds", self.defaults.get("timeout_seconds", 60)))


def validate(doc: dict) -> Policy:
    for key in ("policy", "checks"):
        if key not in doc:
            raise PolicyError(f"missing top-level key '{key}'")
    for key in ("id", "version"):
        if key not in doc["policy"]:
            raise PolicyError(f"policy.{key} missing")
    seen = set()
    for c in doc["checks"]:
        cid = c.get("id")
        if cid not in REGISTRY:
            raise PolicyError(f"unknown check id '{cid}': policies cannot introduce new checks")
        if cid in seen:
            raise PolicyError(f"duplicate check id '{cid}'")
        seen.add(cid)
        if c.get("tier") not in TIERS:
            raise PolicyError(f"{cid}: tier must be one of {TIERS}")
        if not c.get("control"):
            raise PolicyError(f"{cid}: control missing")
        iv = c.get("interval_minutes", 1440)
        if not isinstance(iv, int) or iv < 5:
            raise PolicyError(f"{cid}: interval_minutes must be an integer >= 5")
        _only_data(c.get("params", {}), cid)
    return Policy(doc)


def load(path: str | None = None) -> Policy:
    path = path or DEFAULT_POLICY
    with open(path, "r", encoding="utf-8") as fh:
        return validate(json.load(fh))
