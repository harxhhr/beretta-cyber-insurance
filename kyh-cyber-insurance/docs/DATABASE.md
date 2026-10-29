# Database schema

SQLite, WAL mode, foreign keys on, all queries parameterized. Created by
`app/database.py` on first run.

## Reference / configuration (drives the engines)
- **controls** — the 15-parameter catalogue: `control_id, name, description, tier,
  is_warranty, pricing_weight (credit when met), failure_effect (load when failed),
  unknown_effect (load when unobserved), expected_value, grace_period_days,
  coverage_effect, evidence_requirements`.
- **sectors** — `sector, base_frequency` (demonstration assumptions).
- **coverage_head_defaults** — default severity fractions per coverage head.
- **config** — loadings, modifier floor/cap, claims/exposure loads, warranty gate mode,
  rate limit. JSON-encoded values; all editable via the Admin API and audited.

## Entities
- **companies** — firmographics (sector, revenue, employees, geography).
- **users** — role tokens (UNDERWRITER / CUSTOMER / ADMIN); tokens live in
  `data/secrets.json`, outside source code.
- **policies** — 1 per company in the prototype; `status DRAFT→QUOTED→BOUND`,
  `bound_at, bound_calculation_id, bound_premium` fixed at bind.
- **policy_coverages** — per-policy coverage heads: limit, sublimit, deductible,
  severity_fraction, enabled. Locked once bound.

## Risk dataset (Engine A)
- **observations** — the normalized common representation for every source:
  `observation_id, company_id, control_id, value(true/false/partial),
  dims{exists,current,tested}, source_type, source_id, observed_at, received_at,
  source_locator, evidence_strength, confidence, status, notes`. Append-only;
  corrections are new rows.
- **documents** — metadata + assessment status + default evidence strength per
  document type category. Assessed fields become observations with mandatory locators.
- **claims** — prior incidents (date, type, loss, status, remediation).
- **outside_in_signals** — imported adverse signals, optionally linked to a control.
- **agents / agent_reports** — per-company agent tokens; raw reports stored immutably.

## Engine outputs & monitoring
- **calculations** — persisted premium calculations: full `result_json`,
  `input_snapshot` (resolved posture incl. provenance, claims, signals, coverages,
  config, firmographics) and `model_version`, so historical quotes stay reproducible.
- **warranties** — one row per (bound policy × warranty control): state, breach and
  grace timestamps, configured grace days and coverage effect.
- **warranty_events** — every timestamped state transition with its trigger observation.
- **audit_events** — append-only trail: timestamp, actor, event_type, entity, old/new
  values, metadata.
