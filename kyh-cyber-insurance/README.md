# Beretta — Explainable Cyber Insurance Underwriting & Continuous Warranty Monitoring

A working prototype of an **open, inspectable, explainable, and auditable** cyber-insurance
underwriting pipeline: evidence → control assessment → pricing at inception → policy
binding → continuous post-bind warranty monitoring.

Built with **Python standard library only** (zero third-party dependencies), SQLite, and a
vanilla HTML/CSS/JS dashboard — deliberately, so every calculation and decision can be
read, audited, and reproduced.

---

## Quick start

```bash
python server.py
# open http://127.0.0.1:8000
```

That's it. On first run the server creates `data/kyh.db`, seeds three demonstration
companies, and writes role tokens to `data/secrets.json` (kept outside source code; the
tokens are also printed at startup). The dashboard's role switcher (Underwriter / Insured
customer / Administrator) uses these tokens.

Run the tests:

```bash
python -m unittest discover tests -v
```

Run the scripted demonstration scenario (server must be running):

```bash
python scripts/run_demo.py
```

Run the endpoint agent (agent tokens for the seeded companies are in
`data/demo_profiles.json`):

```bash
# genuine read-only OS checks on this machine:
KYH_AGENT_TOKEN=<token> python agent/agent.py --once
# print the JSON report without sending:
python agent/agent.py --print
# periodic reporting:
KYH_AGENT_TOKEN=<token> python agent/agent.py --interval 300
# labelled SIMULATED demo profile (for demonstrations):
KYH_AGENT_TOKEN=<token> python agent/agent.py --simulate mfa_down --once
```

---

## The two engines

```
ENGINE A — INFORMATION GATHERING              ENGINE B — RISK & PREMIUM
┌────────────────────────────────┐            ┌─────────────────────────────────┐
│ Questionnaire   (DECLARED)     │            │ λ_sector  (configurable)        │
│ Documents       (DOCUMENTED/   │            │   × posture_modifier            │
│                  TESTED)       │  resolve   │   × claims_modifier             │
│ Endpoint agent  (TECHNICALLY_  │──────────▶ │   × exposure_modifier           │
│                  OBSERVED)     │  posture   │ = λ_adjusted                    │
│ Outside-in scan (TECHNICALLY_  │            │ pure = λ_adj × Σ(sev_h×limit_h) │
│                  OBSERVED)     │            │ technical = pure × (1+loadings) │
│ Underwriter     (DOCUMENTED)   │            │ + eligibility gating            │
│ Claims history / Firmographics │            │ + persisted snapshot + version  │
└────────────────────────────────┘            └─────────────────────────────────┘
```

**Pre-bind (INCEPTION):** everything above feeds the quoted technical premium.

**Post-bind:** agent observations feed **warranty evaluation only**:

```
MET ──control fails──▶ IN_GRACE ──grace expires──▶ BREACHED
 ▲                        │
 └──── REMEDIATED ◀───────┘   (passing observation during grace/breach)
```

Post-bind observations **never** re-price the policy. The engine returns a structured
`POLICY_ALREADY_BOUND` error if a re-quote is attempted, and the automated test suite
enforces this as a mandatory acceptance test.

---

## Repository layout

```
server.py            entry point (python server.py)
app/
  catalogue.py       15-control catalogue, sectors, coverage heads, defaults, MODEL_VERSION
  database.py        SQLite schema, connections, seed data (3 demo companies)
  observations.py    Engine A: observation recording + best-evidence resolution
  underwriting.py    Engine B: posture/claims/exposure modifiers, pure premium, loadings,
                     eligibility, bind — with persisted snapshots
  coverage.py        warranty state machine, grace periods, coverage consequences
  audit.py           append-only audit trail
  security.py        tokens, role authorization, rate limiting, input validation
  api.py             JSON routes + static frontend serving (http.server)
agent/
  agent.py           endpoint agent runner (config, token, periodic reporting, logging)
  checks.py          genuine read-only OS checks; NOT_SUPPORTED when unobservable
frontend/            vanilla HTML/CSS/JS dashboard (no pricing logic in the browser)
tests/               unittest suite incl. HTTP end-to-end demonstration scenario
scripts/run_demo.py  scripted Stage 1–7 demonstration
data/                created at runtime: kyh.db, secrets.json, demo_profiles.json
docs/                premium model, API, database schema notes
```

## Database schema (relationships)

`companies 1—1 policies 1—* policy_coverages`; `companies 1—* observations *—1 controls`;
`companies 1—* documents/claims/outside_in_signals/agents`; `agents 1—* agent_reports`
(immutable raw JSON); `policies 1—* calculations` (each with `input_snapshot` +
`model_version`); `policies 1—* warranties 1—* warranty_events`; everything writes
`audit_events`. All queries are parameterized. See `docs/DATABASE.md`.

## Premium model (worked example — engine output, not hand-typed)

For seeded Company B (Manufacturing, base frequency 0.10, demonstration assumption):

```
posture_modifier   0.9940   (15 control contributions, each itemized with evidence)
claims_modifier    1.1000   (1 incident in 3-year lookback × 10% load)
exposure_modifier  1.0300   (1 adverse outside-in signal × 3% load)
adjusted freq      0.10 × 0.9940 × 1.10 × 1.03 = 0.1126
pure premium       0.1126 × Σ(severity_fraction × limit)      = ₹1,30,076
technical premium  pure × (1 + 0.15 + 0.10 + 0.10 + 0.05)     = ₹1,82,107
```

Key modelling choices, all visible in the calculation view:
- **Evidence strength scales credits**: a PASS earns its full configured credit only when
  TECHNICALLY_OBSERVED (agent); DECLARED questionnaire answers earn 60% of it. Failures
  count in full. Questionnaire answers are therefore never treated as equivalent to
  technical evidence.
- **Unknown is priced**: a control with no observation adds a labelled "unknown" load.
- **Existence ≠ currency ≠ tested**: observations carry `{exists, current, tested}` dims;
  an artefact with `tested=false` cannot carry TESTED strength, and `current=false`
  downgrades the value to PARTIAL.
- **Best evidence wins**: per control, the highest-strength, most recent observation is
  the resolved value; disagreeing sources are flagged as conflicts, and the full source
  trail is one click away (source type, locator, timestamps, notes).
- **Snapshots + versioning**: every calculation persists its full input snapshot under
  `UNDERWRITING_MODEL_V1`; changing assumptions later never rewrites historical quotes.

## Warranty lifecycle (worked example)

Company B binds at ₹1,71,847 (engine output from the demo run). The agent later reports
`CTRL-MFA = FAIL`:

```
MFA warranty: MET → IN_GRACE   (breach detected 2026-08-18, grace 7 days,
                                expires 2026-08-25)
Coverage consequence shown:    "If the warranty remains breached when a covered
                                incident occurs after grace expiry, the configured
                                consequence may apply: ransomware coverage head
                                suspended (illustrative)."
Premium:                       ₹1,71,847 — UNCHANGED
Re-quote attempt:              HTTP 409 POLICY_ALREADY_BOUND
```

Every transition is timestamped in `warranty_events` and mirrored to the audit log.
The coverage evaluation is labelled: *"Prototype coverage-condition evaluation; final
claim determination remains subject to policy wording and authorized claims handling."*

## Endpoint agent

Read-only, defensive, platform-aware checks: pending security updates and
unattended-upgrades (apt), EDR/telemetry process presence, disk encryption (dm-crypt /
FileVault / BitLocker status where readable), host firewall, logging daemon, local
password policy, SSH root-login hardening. MFA and backup restore testing are **not**
locally observable, so the agent honestly reports NOT_SUPPORTED with guidance on what
evidence to provide instead — it never fabricates results, and mere tool presence is
reported as PRESENT-level evidence, not as a working control. `--simulate` profiles exist
for demonstrations and label every observation SIMULATED. Reports are immutable once
received; corrections are new observations.

## Live monitoring link (Part 2 collector)

The single-host agent above is kept for backward compatibility. Fleet monitoring now comes
from the Beretta live-monitoring collector (`../kyh-agent`). The collector checks signed reports
from every insured machine, applies the silence rule and the 95% fleet roll-up, and sends
**one signed roll-up per company** to `POST /api/collector/rollup`. This platform stays the
only warranty authority:

- each result is recorded as an `AGENT_FLEET` observation at TECHNICALLY_OBSERVED strength
  (exact repeats within 6 hours are skipped);
- before bind it feeds the next quote like any other evidence; after bind it reaches only
  `coverage.evaluate_policy` and never the premium;
- the roll-up must carry a valid HMAC signature, a sequence number higher than the last one,
  a timestamp within 5 minutes, and a company linked to that collector;
- a monitoring-only warranty, `CTRL-AGENT-COVERAGE` (at least 90% of declared endpoints
  reporting, 14-day grace), is excluded from the posture modifier and from pre-bind
  eligibility, so the 15 priced controls and every premium are unchanged.

Set-up: Administrator role → Model configuration → Monitoring collectors → register a
collector (the secret is shown once) and link a company. The Monitoring tab of a linked
company shows the live fleet. See `../run_linked_demo.py` for both systems running together.

## Security measures in the prototype

Bearer-token agent auth and role tokens (constant-time comparison), role-based
authorization (customer cannot price or bind; only admin edits the model), parameterized
SQL throughout, JSON schema/field validation with structured errors, 1 MB body cap,
per-token rate limiting, path-traversal-safe static serving, safe filename handling,
secrets generated at runtime into `data/secrets.json` (never in source), no execution of
uploaded content (documents are metadata + assessed fields only), and a full audit trail.

## Demonstration walkthrough (UI)

1. **Dashboard** — portfolio stats, policies, recent audit events.
2. **Companies → Kalinga Components (Company B) → Intake** — five input buckets, each
   field showing its source; click any evidence chip for the full provenance trail.
3. **Quote & calculation** — press *Calculate premium*: frequency chain, per-control
   contributions with evidence and locators, coverage expected losses, premium waterfall,
   plain-language explanation, eligibility banner. Bind.
4. **Monitoring (post-bind)** — run
   `python agent/agent.py --simulate mfa_down --once` with Company B's token, refresh:
   the MFA warranty card moves to IN_GRACE with its grace expiry and configured coverage
   consequence, while the premium stays fixed. Run `--simulate mfa_up` to watch
   REMEDIATED → MET.
5. **Audit log** — filter by event type, entity, or actor.
6. **Model configuration** (Administrator role) — edit loadings, sector frequencies,
   control weights, grace periods, and warranty gate mode (WARN/BLOCK); every change is
   audited and never affects historical calculations.

## Research positioning

Continuous-monitoring-linked cyber insurance **already exists commercially** (e.g.
Coalition and At-Bay internationally; Mitigata in India). This prototype does not claim
that concept as an invention. Two claims are kept deliberately separate:

- **Market motivation:** India has an underserved cyber-insurance opportunity.
- **Research/technical gap:** an *open and inspectable* pipeline demonstrating the
  complete flow from evidence → control assessment → pricing → binding → continuous
  warranty monitoring, with every number traceable — valuable for research and education.

## Assumptions and limitations

- **All rates are demonstration assumptions — not production actuarial rates.** Sector
  frequencies, control weights, severity fractions, and loadings are illustrative and
  clearly labelled as such throughout the UI and API.
- Authentication is simplified (static role tokens; `/api/demo/tokens` exposes them so
  the local dashboard can switch roles). This endpoint and scheme must be removed for
  any non-local deployment; role separation itself is real and enforced server-side.
- Document handling stores metadata and manually assessed fields with mandatory source
  locators; it does not parse file contents. The observation model (value + locator +
  evidence strength) is the integration point for a future extraction model.
- Outside-in signals are imported/simulated; no external scanning is performed.
- The coverage engine gives an illustrative policy-condition evaluation, not claims
  decisions.
- Single-node SQLite prototype: no TLS, clustering, backups, or key management.
  Production would additionally need actuarial validation, filed policy wordings,
  hardened identity/agent PKI, and insurer governance.

## Regulatory context

The platform surfaces the Indian regulatory environment it is designed around — the
Digital Personal Data Protection Act 2023, CERT-In Directions 2022, and RBI / SEBI /
IRDAI frameworks — as context fields only.

> This prototype is an educational/research underwriting architecture and is not legal,
> actuarial, regulatory, or insurance advice. Production deployment would require
> validation against applicable Indian law, regulatory requirements, policy wording,
> actuarial standards, and insurer governance.
