# Pricing V2: final report

The V2 engine (UNDERWRITING_MODEL_V2) is live in the platform and every new quote uses it. This report
lists what still needs a real source, what differs from `KYH_Engine_B_V2_master_prompt.md`, and why.

## Test results

| Suite | Result |
|---|---|
| Part 1: `python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance` | 61 tests OK (35 platform and fleet-link, moved to V2; 26 new V2 tests) |
| Part 2: `python kyh-agent/run_tests.py` | 158 tests OK (one test added for the 7-day patch window) |
| Integration: `python integration/test_linked_system.py` | 1 test OK |

The V2 suite (`tests/test_pricing_v2.py`) covers all ten groups in the specification:
1. centring;
2. monotonicity in evidence, turnover, retention and limit;
3. transition-zone continuity and exact band interiors;
4. payout against the closed-form LEV;
5. peril reconciliation;
6. the claims values at λT = 0.03 (0.99 / 1.23 / 1.46, as the spec gives);
7. gating;
8. referral, including binding blocked without approval;
9. no re-pricing after bind;
10. V1 and V2 reproduction.

It also checks the what-if savings and that every parameter carries its provenance.

## TODO-SOURCE items

| Parameter | Placeholder | Needed |
|---|---|---|
| `currency.usd_inr` | 88.0 [A] | Current RBI reference rate |
| Head shares, all rows except ransomware IR / BI / restoration | Spec placeholders [A] | NetDiligence 2025 crisis-services tables 10 and 14 |
| MFA adoption `p` | 0.70 [A] | A published adoption rate (Marsh gives none) |
| IR-plan severity adoption `p` | 0.5 [A] | A published adoption rate |
| Awareness severity adoption `p` | 0.5 [A] | A published adoption rate |
| Encryption severity effect | IBM 2019, S = 1.101 [A] | A newer figure; adoption 0.5 is also a placeholder |
| Sources and locators in general | As given in the spec | A check of each figure against the reports; not done here |

## Deviations from the specification

| # | What | Why |
|---|---|---|
| 1 | **None for α: it is the spec's 4.22.** Noted for the record: the spec's derivation measures control heterogeneity on ransomware frequency alone (1 + CV² = 1.45). On the all-peril firm frequency, which M_claims multiplies, it would be 1.10 and α ≈ 1.6. | You chose to keep the spec's value. `scripts/derive_alpha.py` reproduces the spec's basis and prints the all-peril figure for reference only. |
| 2 | The sector term of the α derivation uses the 13 published sector relativities (1 + CV² = 1.078), not IRIS's full App. A1 (spec: 1.06). | Only these 13 are in the spec; the full appendix isn't available here. The ransomware-basis α comes out at 3.5 / 4.5 / 8.6 for β = 0 / 0.5 / 1, against the spec's 3.5 / 4.2 / 6.9. |
| 3 | Control heterogeneity is computed by exact enumeration of all 2⁹ control patterns instead of a 200,000-firm Monte Carlo. | Same quantity, without sampling error. |
| 4 | No git branch and no commit per stage. | You chose not to use git or backups. The folder is still not a git repository. |
| 5 | Existing tests were rewritten to assert V2 fields where they read V1 output. The Engine A, warranty, fleet and HTTP scenarios keep their intent. | You asked for the premium model to be replaced from scratch. V1 is still covered by a reproduction test. |
| 6 | Part 2 changed: the patch check window is now 7 days (agent policy 2.1.0), and local administrator accounts now map to CTRL-PAM instead of CTRL-SECCONFIG. | You asked for the agent to be changed to match V2. Both changes make the agent measure what V2 prices. |
| 7 | CONDITIONALLY_ELIGIBLE quotes can still be bound by an underwriter. Referred quotes need an explicit approval tick (`referral_approved`) to bind. | The spec says evidence is "needed before bind" but also keeps gating price-neutral. Blocking conditional risks outright would stop the linked demo, where backups can only ever be STATED. |
| 8 | *(removed)* A missing or unmapped NIC code is no longer a referral trigger; it is priced at the global-average sector, as the spec says. | Your decision: V2 follows the spec. |
| 9 | When years in operation is missing, T = 3 is used. | The spec defines T = min(3, years) but not the missing case. |
| 10 | A claim's material flag is optional. If it isn't set, a claim is material when the loss exceeds the retention or the type mentions ransom. | Old claims have no flag; the addendum and intake screen now ask for it. |
| 11 | "Don't know" means no observation (UNKNOWN). Questionnaire "no" means NOT_WORKING. Both are priced at m_lacks, as the spec requires. | Engine A has no explicit "don't know" value. |
| 12 | Outside-in signals map to controls through a fixed table: EXPOSED_RDP, EXPOSED_SMB, TLS_WEAK and EOL_SOFTWARE → SECCONFIG fail; UNPATCHED_CRITICAL_CVE → PATCH-CRIT fail; DMARC_MISSING → EMAILSEC fail; DMARC_PRESENT → EMAILSEC pass. | The spec gives two examples; the rest are judgement. A signal's explicit related control overrides the table. |
| 13 | The bound premium is the technical premium; GST is shown separately. | GST is a tax, not premium. |
| 14 | The per-head payout display shares the aggregate cap pro rata across heads. | The spec defines only the total. The total is exact either way. |
| 15 | Head-share sensitivity: ransomware's measured shares are fixed and its placeholder shares scaled ±25% and renormalised. Rows with no measured share have their largest share scaled ±25%, then renormalised. | Scaling every share in a row by the same factor and renormalising changes nothing. |
| 16 | V1's editable parameters (loadings, sector frequencies, control weights) were removed from the admin screen. V2 parameters are shown read-only with provenance; gate mode and warranty grace days stay editable. | V2 values must keep their source and tag, so they change in the parameter file. |
| 17 | The default gate mode is now BLOCK. On the platform alone, the seeded Kalinga Components is INELIGIBLE, because its questionnaire says backups are untested. In the linked demo the fleet makes them STATED and it can be bound. | The spec sets BLOCK as the default. |
| 18 | Policies created before V2 have no FTF head row; the engine includes the FTF head for them anyway. | FTF losses would otherwise be unpriced on older policies. |
| 19 | **Per-cover sub-limits removed** (your decision). The spec's placeholder sub-limits (IR 100%, BI 50%, DR 50%, Legal 50%, TPL 100%, Extortion 50%, Notification 50%, FTF 25% of the overall limit) are gone from the model, the parameter file and the policy-structure screen, along with the per-cover "Covered" switches. Each claim now pays its loss above the retention across all covers, up to the overall limit: `payout = E[min(Σ_h s_h·M_sev,h·(X − d)+, L_total)]`. | They were assumptions with no source. The overall limit and the retention stay as inputs. Effect on the worked example: ₹86,871 → ₹99,895, all from funds transfer fraud (its 25% sub-limit was the only binding one). |

## Files

**New**
- `kyh-cyber-insurance/app/pricing_v2.py`, `app/pricing_v2_params.json`
- `kyh-cyber-insurance/scripts/`: `derive_sigma.py`, `derive_credit_x.py`, `derive_alpha.py`,
  `worked_example_v2.py`, `sensitivity_v2.py`
- `kyh-cyber-insurance/tests/test_pricing_v2.py`
- `docs/premium_model_v2.md`, this report, `docs/pricing_v2_plan.md`
- The questionnaire addendum: `docs/build_iq_addendum.js` and
  `kyh-cyber-insurance/frontend/forms/CyberUW-IQ-1.1-Addendum.docx` / `.pdf`

**Changed**
- Part 1: `app/api.py`, `app/database.py` (additive migrations), `app/observations.py`
  (`record_signal`), `app/underwriting.py` (`reproduce_v1`, referral check at bind), `app/catalogue.py`
  (FTF head, model constant, gate default)
- Frontend: `frontend/app.js` and `styles.css` (intake fields, policy structure, V2 quote page, admin
  parameter view, evidence key), `frontend/forms/forms_catalogue.json`
- Tests: the existing tests moved to V2
- Part 2: `kyh-agent/agent/kyh_agent/policy.json`, `kyh-agent/collector/kyh_collector/settings.py`,
  `kyh-agent/tests/test_verdicts.py`, plus the approval labels in `kyh_collector/__main__.py` and
  `run_linked_demo.py`
- `CLAUDE.md`
