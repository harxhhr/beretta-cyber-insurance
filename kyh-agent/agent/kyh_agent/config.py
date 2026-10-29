"""Agent configuration and on-disk locations."""

from __future__ import annotations

import json
import os
import sys

if sys.platform.startswith("win"):
    DEFAULT_DIR = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "KYH", "Agent")
    DEFAULT_CONFIG = os.path.join(DEFAULT_DIR, "config.json")
    DEFAULT_STATE = DEFAULT_DIR
elif sys.platform == "darwin":
    DEFAULT_DIR = "/Library/Application Support/KYH/Agent"
    DEFAULT_CONFIG = os.path.join(DEFAULT_DIR, "config.json")
    DEFAULT_STATE = DEFAULT_DIR
else:
    DEFAULT_CONFIG = "/etc/kyh-agent/config.json"
    DEFAULT_STATE = "/var/lib/kyh-agent"


class Config(dict):
    """Keys: server_url, ca_file, agent_id, agent_secret, company_id, company_name, enrolled_at,
    heartbeat_minutes, full_snapshot_hours, allow_insecure_http."""

    path: str = DEFAULT_CONFIG

    @property
    def enrolled(self) -> bool:
        return bool(self.get("agent_id") and self.get("agent_secret"))

    def heartbeat_seconds(self) -> int:
        return int(self.get("heartbeat_minutes", 15)) * 60

    def full_snapshot_seconds(self) -> int:
        return int(self.get("full_snapshot_hours", 24)) * 3600


def load(path: str | None = None) -> Config:
    path = path or DEFAULT_CONFIG
    cfg = Config()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    cfg.path = path
    return cfg


def save(cfg: Config) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(cfg.path)), exist_ok=True)
    tmp = cfg.path + ".tmp"
    # Create with owner-only permissions: the file holds the agent's signing secret.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(dict(cfg), fh, indent=2, sort_keys=True)
    os.replace(tmp, cfg.path)
    if hasattr(os, "chmod") and not sys.platform.startswith("win"):
        os.chmod(cfg.path, 0o600)
