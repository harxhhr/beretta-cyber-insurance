"""Default configuration that drives the platform.

Everything in this module is written into SQLite on first run and is
editable afterwards through the Admin API.  Nothing here is hard-coded
into engine logic: the engines read the database, not this file.

ALL NUMERIC ASSUMPTIONS BELOW ARE DEMONSTRATION ASSUMPTIONS —
NOT PRODUCTION ACTUARIAL RATES.
"""

MODEL_VERSION = "UNDERWRITING_MODEL_V1"      # frozen: kept so stored V1 quotes reproduce
MODEL_VERSION_V2 = "UNDERWRITING_MODEL_V2"   # active model (app/pricing_v2.py, app/pricing_v2_params.json)

# ---------------------------------------------------------------------------
# Sector base annual incident frequencies (illustrative prototype assumptions)
# ---------------------------------------------------------------------------
SECTORS = {
    "Financial Services": 0.20,
    "Healthcare": 0.18,
    "Technology": 0.16,
    "Retail": 0.13,
    "Professional Services": 0.12,
    "Manufacturing": 0.10,
    "Other": 0.08,
}

# ---------------------------------------------------------------------------
# Evidence strength.  Credits for a PASSED control are scaled by these
# multipliers so a declared answer never counts like technical evidence.
# Failure loads always count in full (a failure is a failure).
# ---------------------------------------------------------------------------
EVIDENCE_STRENGTHS = ["DECLARED", "DOCUMENTED", "TESTED", "TECHNICALLY_OBSERVED"]
EVIDENCE_CREDIT_MULTIPLIER = {
    "DECLARED": 0.60,
    "DOCUMENTED": 0.80,
    "TESTED": 0.90,
    "TECHNICALLY_OBSERVED": 1.00,
}

SOURCE_TYPES = ["QUESTIONNAIRE", "DOCUMENT", "AGENT", "AGENT_FLEET", "OUTSIDE_IN_SCAN", "UNDERWRITER"]
# Default evidence strength implied by each source type when not stated.
SOURCE_DEFAULT_EVIDENCE = {
    "QUESTIONNAIRE": "DECLARED",
    "DOCUMENT": "DOCUMENTED",
    "AGENT": "TECHNICALLY_OBSERVED",
    # Fleet roll-up from the KYH live-monitoring collector (Part 2): one result per control
    # for the whole company, computed from signed per-host agent reports.
    "AGENT_FLEET": "TECHNICALLY_OBSERVED",
    "OUTSIDE_IN_SCAN": "TECHNICALLY_OBSERVED",
    "UNDERWRITER": "DOCUMENTED",
}

# ---------------------------------------------------------------------------
# The 15-parameter control catalogue.
#   pricing_weight  : frequency credit when the control is MET (subtracted)
#   failure_effect  : frequency load  when the control is FAILED (added)
#   unknown_effect  : frequency load  when no observation exists
#   tier 1 = warranty, 2 = important, 3 = hygiene
# ---------------------------------------------------------------------------
CONTROLS = [
    # ---- Tier 1: WARRANTIES -------------------------------------------------
    dict(control_id="CTRL-MFA", name="Multi-factor authentication",
         description="MFA enforced for remote access, email and privileged accounts.",
         tier=1, is_warranty=1, pricing_weight=0.08, failure_effect=0.18,
         unknown_effect=0.10, grace_period_days=7,
         coverage_effect="Ransomware & cyber-extortion coverage head suspended while breached (illustrative).",
         evidence_requirements="IdP configuration export, agent observation, or CAIQ IAM section."),
    dict(control_id="CTRL-BACKUP-TESTED", name="Tested backups",
         description="Backups exist, are current, and restoration has been tested.",
         tier=1, is_warranty=1, pricing_weight=0.07, failure_effect=0.15,
         unknown_effect=0.09, grace_period_days=7,
         coverage_effect="Data-restoration claims subject to 50% co-insurance while breached (illustrative).",
         evidence_requirements="Backup restore test report dated within 12 months."),
    dict(control_id="CTRL-EDR", name="Endpoint detection & response",
         description="EDR deployed, enabled and reporting on managed endpoints.",
         tier=1, is_warranty=1, pricing_weight=0.06, failure_effect=0.14,
         unknown_effect=0.08, grace_period_days=7,
         coverage_effect="Incident-response deductible doubled while breached (illustrative).",
         evidence_requirements="EDR console export or agent observation of running sensor."),
    dict(control_id="CTRL-PATCH-CRIT", name="Critical patching process",
         description="Critical vulnerabilities patched within a defined SLA.",
         tier=1, is_warranty=1, pricing_weight=0.05, failure_effect=0.12,
         unknown_effect=0.07, grace_period_days=14,
         coverage_effect="Claims arising from unpatched critical CVEs subject to coinsurance (illustrative).",
         evidence_requirements="Patch-management report or agent patch-level observation."),
    # ---- Tier 2: IMPORTANT CONTROLS ----------------------------------------
    dict(control_id="CTRL-PAM", name="Privileged access management",
         description="Privileged accounts vaulted, rotated and monitored.",
         tier=2, is_warranty=0, pricing_weight=0.04, failure_effect=0.08,
         unknown_effect=0.04, grace_period_days=0, coverage_effect="",
         evidence_requirements="PAM tool report or documented process."),
    dict(control_id="CTRL-SEGMENTATION", name="Network segmentation",
         description="Production, corporate and OT networks segmented.",
         tier=2, is_warranty=0, pricing_weight=0.04, failure_effect=0.07,
         unknown_effect=0.04, grace_period_days=0, coverage_effect="",
         evidence_requirements="Network architecture document or VAPT confirmation."),
    dict(control_id="CTRL-EMAILSEC", name="Email security",
         description="Anti-phishing gateway plus SPF/DKIM/DMARC enforcement.",
         tier=2, is_warranty=0, pricing_weight=0.04, failure_effect=0.08,
         unknown_effect=0.04, grace_period_days=0, coverage_effect="",
         evidence_requirements="DNS records (outside-in) or gateway configuration."),
    dict(control_id="CTRL-VULNMGMT", name="Vulnerability management",
         description="Recurring authenticated scanning with tracked remediation.",
         tier=2, is_warranty=0, pricing_weight=0.03, failure_effect=0.06,
         unknown_effect=0.03, grace_period_days=0, coverage_effect="",
         evidence_requirements="Scanner export or VAPT report."),
    dict(control_id="CTRL-IRPLAN", name="Incident response plan",
         description="IR plan exists, is current, and has been exercised.",
         tier=2, is_warranty=0, pricing_weight=0.03, failure_effect=0.06,
         unknown_effect=0.03, grace_period_days=0, coverage_effect="",
         evidence_requirements="IR plan + tabletop exercise evidence (existence/currency/tested tracked separately)."),
    # ---- Tier 3: HYGIENE CONTROLS -------------------------------------------
    dict(control_id="CTRL-AWARENESS", name="Security awareness training",
         description="All-staff annual training plus phishing simulations.",
         tier=3, is_warranty=0, pricing_weight=0.02, failure_effect=0.03,
         unknown_effect=0.015, grace_period_days=0, coverage_effect="",
         evidence_requirements="Training completion report."),
    dict(control_id="CTRL-ASSETINV", name="Asset inventory",
         description="Maintained inventory of hardware, software and data assets.",
         tier=3, is_warranty=0, pricing_weight=0.02, failure_effect=0.03,
         unknown_effect=0.015, grace_period_days=0, coverage_effect="",
         evidence_requirements="Inventory export or CMDB screenshot."),
    dict(control_id="CTRL-PASSPOLICY", name="Password policy",
         description="Enforced password length/quality and lockout policy.",
         tier=3, is_warranty=0, pricing_weight=0.015, failure_effect=0.03,
         unknown_effect=0.015, grace_period_days=0, coverage_effect="",
         evidence_requirements="Policy document or agent observation of local policy."),
    dict(control_id="CTRL-LOGGING", name="Logging & monitoring",
         description="Central log collection with retention and alerting.",
         tier=3, is_warranty=0, pricing_weight=0.02, failure_effect=0.03,
         unknown_effect=0.015, grace_period_days=0, coverage_effect="",
         evidence_requirements="SIEM report or agent observation of log services."),
    dict(control_id="CTRL-SECCONFIG", name="Secure configuration practices",
         description="Hardening baselines applied (CIS or equivalent).",
         tier=3, is_warranty=0, pricing_weight=0.015, failure_effect=0.03,
         unknown_effect=0.015, grace_period_days=0, coverage_effect="",
         evidence_requirements="Configuration report or agent checks."),
    dict(control_id="CTRL-ENCRYPTION", name="Disk & data encryption",
         description="Full-disk encryption on endpoints; encryption at rest for data stores.",
         tier=3, is_warranty=0, pricing_weight=0.02, failure_effect=0.04,
         unknown_effect=0.02, grace_period_days=0, coverage_effect="",
         evidence_requirements="Agent disk-encryption observation or MDM report."),
]
# ---- Monitoring-only warranty (added with the Part 2 collector link) --------
# Not part of the 15 priced controls: monitoring_only controls are skipped by the
# posture modifier and by pre-bind eligibility, so premiums are unchanged. It exists
# only so the post-bind state machine can enforce "the agent must keep reporting".
MONITORING_CONTROLS = [
    dict(control_id="CTRL-AGENT-COVERAGE", name="Live monitoring coverage",
         description="The KYH monitoring agent reports from at least 90% of the endpoints declared "
                     "on the proposal form (silent hosts count as not reporting).",
         tier=1, is_warranty=1, monitoring_only=1, pricing_weight=0.0, failure_effect=0.0,
         unknown_effect=0.0, grace_period_days=14,
         coverage_effect="Unmonitored endpoints treated as non-compliant with every warranty while breached (illustrative).",
         evidence_requirements="Fleet roll-up from the KYH collector."),
]
for _c in CONTROLS:
    _c.setdefault("monitoring_only", 0)
assert len(CONTROLS) == 15  # the priced catalogue is unchanged
ALL_CONTROLS = CONTROLS + MONITORING_CONTROLS

# ---------------------------------------------------------------------------
# Coverage heads with default severity fractions (illustrative).
# severity_fraction = expected share of the head's limit consumed per incident.
# ---------------------------------------------------------------------------
COVERAGE_HEADS = [
    dict(coverage_id="COV-IR",     name="Incident Response / Forensics", severity_fraction=0.20),
    dict(coverage_id="COV-BI",     name="Business Interruption",         severity_fraction=0.15),
    dict(coverage_id="COV-DR",     name="Data Restoration",              severity_fraction=0.12),
    dict(coverage_id="COV-LEGAL",  name="Legal & Regulatory",            severity_fraction=0.10),
    dict(coverage_id="COV-TPL",    name="Third-Party Liability",         severity_fraction=0.08),
    dict(coverage_id="COV-EXT",    name="Cyber Extortion / Ransomware",  severity_fraction=0.18),
    dict(coverage_id="COV-NOTIFY", name="Notification Costs",            severity_fraction=0.06),
    # Added with pricing V2 (FTF losses are not covered by any other head). severity_fraction 0 keeps V1 unchanged.
    dict(coverage_id="COV-FTF",    name="Funds Transfer Fraud / Social Engineering", severity_fraction=0.0),
]

# ---------------------------------------------------------------------------
# Loadings and engine bounds (all editable in Admin).
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "loading_expenses": 0.15,
    "loading_profit": 0.10,
    "loading_risk_margin": 0.10,
    "loading_reinsurance": 0.05,
    "posture_modifier_floor": 0.60,
    "posture_modifier_cap": 1.60,
    # Claims history: frequency load per prior incident in the lookback window
    "claims_load_per_incident": 0.10,
    "claims_lookback_years": 3,
    "claims_modifier_cap": 1.50,
    # Outside-in: frequency load per adverse signal
    "exposure_load_per_signal": 0.03,
    "exposure_modifier_cap": 1.30,
    # Warranty gating before bind: BLOCK | WARN (pricing V2 default: BLOCK)
    "warranty_gate_mode": "BLOCK",
    "rate_limit_per_minute": 240,
}

REGULATORY_CONTEXT = [
    dict(key="DPDP", name="Digital Personal Data Protection Act, 2023",
         note="Personal data breach obligations and penalties shape Legal & Regulatory and Notification exposure."),
    dict(key="CERT-IN", name="CERT-In Directions, 2022",
         note="6-hour incident reporting and 180-day log retention affect Logging & Monitoring expectations."),
    dict(key="RBI", name="RBI cyber security framework (banks/NBFCs)",
         note="Applies where the insured is RBI-regulated; informs warranty expectations for financial-services risks."),
    dict(key="SEBI", name="SEBI CSCRF (market intermediaries)",
         note="Applies to SEBI-regulated entities; informs control expectations for capital-market risks."),
    dict(key="IRDAI", name="IRDAI (Information and Cyber Security) Guidelines",
         note="Governs insurers' own security and product conduct; relevant to any production deployment."),
]

DISCLAIMER = ("This prototype is an educational/research underwriting architecture and is not "
              "legal, actuarial, regulatory, or insurance advice. Production deployment would "
              "require validation against applicable Indian law, regulatory requirements, policy "
              "wording, actuarial standards, and insurer governance.")
