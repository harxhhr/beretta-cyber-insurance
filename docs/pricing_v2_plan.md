# Engine B V2 (UNDERWRITING_MODEL_V2): implementation plan

Plan for `KYH_Engine_B_V2_master_prompt.md`. Nothing has been changed yet.

## What the code has today

- **Engine B V1** is `kyh-cyber-insurance/app/underwriting.py`: sector base frequency × posture modifier
  (additive control weights) × claims modifier × exposure modifier, then per-head
  `severity_fraction × limit`, then a 1.40 additive loading. Defaults live in `app/catalogue.py` and
  are copied into SQLite.
- **Engine A** (`app/observations.py`) resolves one best observation per control: status
  PASS / PARTIAL / FAIL / UNKNOWN, evidence strength, source type, and `source_id` (the document id for
  document evidence, so the document type is reachable).
- **Stored data:** companies have `sector` (seven V1 sectors), revenue, employees and geography. There is
  no NIC code, years in operation or RBI/SEBI flag. Claims have no "material" flag. Policies have
  per-head limit and deductible rows for seven heads, with no FTF head and no overall limit or retention.
- **Calculations** already store `model_version`, `input_snapshot` and `result_json`, so V1 quotes can
  be reproduced from their snapshot.
- **Questionnaire:** CYBERUW-IQ-1.0 exists only as finished PDFs; there is no source to regenerate them.
  - Already present: A3 year established, B1 revenue, G3 sandboxing, M4 call-back verification, N4
    training.
  - Missing: NIC 2008 code, an explicit RBI/SEBI flag, a count of material incidents with the
    definition, a misrepresentation declaration, and a "don't know" answer option.
- **Repository:** this folder is not a git repository.
- **Tests that read V1 output:** the `TestPremiumEngine` tests call `underwriting` directly. These also
  read V1-only fields:
  - `test_full_demonstration_scenario` (V1 keys from `/api/quote`)
  - two fleet-link tests (`posture_modifier.contributions`)
  - the integration test (`posture_modifier` from `/api/quote`)

## Conflict with CLAUDE.md

CLAUDE.md rule 2 says "never change the pricing logic". This task replaces Engine B, so I will:
- leave V1 frozen, with its code and parameters untouched, so stored V1 quotes reproduce exactly;
- put all V2 logic in new files;
- reword rule 2 at the end to say V1 is frozen and V2 parameters change only through the parameter file.

## Files

**New**

| File | What it holds |
|---|---|
| `kyh-cyber-insurance/app/pricing_v2_params.json` | Every V2 parameter as `{value, unit, source, locator, tag, sensitivity}`, the NIC→sector table, and notes on supporting (unpriced) evidence |
| `kyh-cyber-insurance/app/pricing_v2.py` | The V2 engine: classification, peril frequency, lognormal payout (quantile grid plus closed-form LEV), evidence status, control combining, claims credibility, TLR/GST, gating, referral, breakdown, what-if savings |
| `kyh-cyber-insurance/app/pricing.py` | One entry point: `quote(conn, policy_id)` runs the active model (V2). `reproduce(calculation_id)` re-runs a stored quote with the model it was made with |
| `kyh-cyber-insurance/scripts/derive_sigma.py`, `derive_credit_x.py`, `derive_alpha.py` | Reproduce every `[D]` value and print the sensitivity variants the spec asks for |
| `kyh-cyber-insurance/scripts/sensitivity_v2.py`, `worked_example_v2.py` | The sensitivity table and the NIC 62 worked example |
| `kyh-cyber-insurance/tests/test_pricing_v2.py` | The ten V2 test groups in §11 |
| `docs/premium_model_v2.md` | Specification, formulas, parameter table, assumptions, limitations, V1 → V2 comparison |
| `docs/pricing_v2_report.md` | Final report: every TODO-SOURCE item and every deviation |

**Changed**

| File | Change |
|---|---|
| `app/database.py` | Additive migrations only (ADD COLUMN if missing): `companies.nic_code`, `years_in_operation`, `regulated_rbi_sebi`; `claims.material`; `policies.limit_total_inr`, `retention_inr`. Add the FTF / Social Engineering head. Config `active_model_version = UNDERWRITING_MODEL_V2`. Give the three demo companies NIC codes |
| `app/underwriting.py` | V1 math untouched. Add a pure `reproduce_v1(snapshot)` for the "V1 quotes still reproduce" test. `bind_policy` stays shared; it reads the stored calculation, so it works for both models |
| `app/api.py` | Company create/update take the new fields. `/api/quote` goes through `pricing.quote`. Outside-in signals linked to a control become OUTSIDE_IN_SCAN observations (V2 has no exposure modifier). Admin shows the V2 parameters read-only with their tags |
| `app/catalogue.py` | Add `MODEL_VERSION_V2` and the FTF head. The 15 controls, weights and V1 constants stay as they are |
| Frontend (`index.html`, `app.js`, `styles.css`) | Intake: NIC code, years in operation, RBI/SEBI flag, material incidents. Policy structure: overall limit and retention, with sub-limits shown as % of the limit. Quote page: V2 breakdown (classification, per-peril table, controls with evidence status, claims, EL → TLR split → technical → GST → total, gating, referral, `[A]` list) and what-if savings. V1 calculations keep their current view |
| Questionnaire | A new addendum, "CYBERUW-IQ-1.1 Addendum" (DOCX + PDF), with the missing fields. The existing PDFs stay unchanged because they can't be regenerated without their source |
| `CLAUDE.md` | Rule 2 reworded as above; test counts updated |

Part 2 (agent and collector) is not touched. The fleet already sends BACKUP as `partial`, which V2
reads as STATED, as the spec intends.

## How Engine A's result maps to V2 evidence status

| Engine A result | V2 status |
|---|---|
| PASS, TECHNICALLY_OBSERVED (agent, fleet, outside-in) | VERIFIED |
| PASS, TESTED (restore test, tabletop, pentest) | VERIFIED |
| PASS, DOCUMENTED from SOC2 Type II, ISO 27001 SoA, VAPT, scanner export, config or endpoint report | VERIFIED |
| PASS, DOCUMENTED from CAIQ, SIG Lite or an underwriter note | STATED |
| PASS, DECLARED (questionnaire "yes", narrative policy) | STATED |
| PARTIAL (for example fleet backup recent but restore untested) | STATED |
| FAIL (agent or scan FAIL, or questionnaire "no") | NOT_WORKING |
| No observation ("don't know") | UNKNOWN |

## Migration

- **Existing calculations:** never rewritten. V1 bound policies stay bound at their V1 premium.
- **New quotes:** all use V2.
- **Companies without a NIC code:** priced at the global-average sector (relativity 1.0), with a
  breakdown note asking for the code.
- **Retention:** defaults to the largest existing per-head deductible. The overall limit defaults to
  the largest existing per-head limit; both are editable.

## Points I'll handle as follows unless you say otherwise

1. **Values and sources:** I use the numbers and locators exactly as the spec gives them. I can't open
   the source reports here, so the final report will say that sources and locators were taken from the
   spec and not checked against the reports themselves.
2. **Derived values:** the scripts compute them. If a script lands slightly off the spec's figure (for
   example α ≈ 4.2), I use the script's output and record the difference as a deviation.
3. **Payout grid:** 20,000 mid-point quantiles plus a finer upper tail, as specified. A quote with
   what-if savings recomputes about 12 premiums. If that takes longer than about 2 s, I'll cache
   per-peril payouts rather than shrink the grid, and report the timing.
4. **Gate mode:** BLOCK becomes the default. In the demo, Kalinga's backups are STATED, so it becomes
   CONDITIONALLY_ELIGIBLE and can still be bound. MFA STATED passes.

## Stages

These follow the spec, with one commit and all three test suites after each stage:
(1) parameters and derivation scripts → (2) engine core → (3) controls and evidence → (4) claims,
TLR, GST → (5) gating and referral → (6) breakdown, what-if, API and UI → (7) questionnaire fields
and addendum → (8) tests → (9) worked example, sensitivity analysis, documentation and final report.
