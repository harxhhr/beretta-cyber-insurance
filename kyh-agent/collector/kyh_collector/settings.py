"""Collector settings. Every threshold here is an assumed demonstration value [C-asm]
unless stated otherwise; an administrator can override them in data/settings.json."""

from __future__ import annotations

import copy
import json
import os

LABEL = ("Prototype coverage-condition evaluation; final claim determination remains subject to policy "
         "wording and authorized claims handling.")

DEFAULTS = {
    # Liveness: how long a host may stay quiet before we stop trusting its last results.
    "unverified_after_hours": 6,        # [C-asm] shown as UNVERIFIED, no warranty change
    "silent_after_hours": 72,           # [C-asm] after this a host is SILENT (see silent_pass_exclusion_days)
    # A SILENT host whose last trusted result for a control was FAIL keeps counting as FAIL (silence can't hide a
    # failure). If its last result was PASS it is left out of the roll-up for up to this many days (leave, holidays),
    # then counts as FAIL. Coverage still counts silent hosts as not reporting.
    "silent_pass_exclusion_days": 14,   # [C-asm]
    # Fleet roll-up
    "warranty_pass_ratio": 0.95,        # [C-asm] share of observed hosts that must pass
    "coverage_min_ratio": 0.90,         # [C-asm] reporting hosts / declared endpoints
    "coverage_onboarding_days": 14,     # [C-asm] time after bind to roll the agent out before coverage is enforced
    "warranty_controls": ["PATCH", "EDR", "BACKUP", "MFA", "MONITORING_COVERAGE"],
    "grace_days": {"PATCH": 14, "EDR": 7, "BACKUP": 7, "MFA": 7, "MONITORING_COVERAGE": 14},  # [C-asm]
    "remediation_confirm_hours": 24,    # [C-asm] a fix must hold this long before REMEDIATED -> MET
    "coverage_effects": {               # [C-asm] illustrative consequences, not policy wording
        "PATCH": "Ransomware & cyber-extortion claims subject to 50% co-insurance while breached",
        "EDR": "Ransomware & cyber-extortion claims subject to a 2x deductible while breached",
        "BACKUP": "Business-interruption and data-restoration cover subject to 25% co-insurance while breached",
        "MFA": "Social-engineering / funds-transfer-fraud cover suspended while breached",
        "MONITORING_COVERAGE": "Unmonitored endpoints treated as non-compliant for all warranties",
    },
    # Linked mode (collector feeds the KYH platform, which owns warranties)
    "platform_control_map": {           # collector control -> KYH platform control
        "PATCH": "CTRL-PATCH-CRIT", "EDR": "CTRL-EDR", "BACKUP": "CTRL-BACKUP-TESTED", "MFA": "CTRL-MFA",
        "DISK_ENCRYPTION": "CTRL-ENCRYPTION",
        "FIREWALL": "CTRL-SECCONFIG", "REMOTE_ACCESS": "CTRL-SECCONFIG", "EXPOSED_SERVICES": "CTRL-SECCONFIG",
        "OS_SUPPORT": "CTRL-SECCONFIG",
        # Pricing V2 prices endpoint privilege management (Marsh 2023) as CTRL-PAM; local admins are its endpoint view.
        "ADMIN_ACCOUNTS": "CTRL-PAM",
        "LOG_RETENTION": "CTRL-LOGGING", "TIME_SYNC": "CTRL-LOGGING",
        "MONITORING_COVERAGE": "CTRL-AGENT-COVERAGE",
    },
    # A PASS here is sent as "partial": a recent backup is observable, a restore test is not.
    "platform_partial_on_pass": ["BACKUP"],
    "push_interval_seconds": 30,        # how often the link worker re-evaluates linked companies
    "push_heartbeat_minutes": 15,       # push even without changes this often
    # Ingestion security
    "max_clock_skew_minutes": 5,
    "max_report_age_days": 30,
    "max_body_bytes": 1_000_000,
    "rate_limit_per_minute": 30,
    "supported_schema_versions": [2],
}


def load(data_dir: str) -> dict:
    s = copy.deepcopy(DEFAULTS)
    path = os.path.join(data_dir, "settings.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            override = json.load(fh)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(s.get(k), dict):
                s[k].update(v)
            else:
                s[k] = v
    return s
