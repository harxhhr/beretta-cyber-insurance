# Beretta premium model V2 (UNDERWRITING_MODEL_V2)

This document specifies Engine B as implemented in `kyh-cyber-insurance/app/pricing_v2.py`. Every number
lives in `kyh-cyber-insurance/app/pricing_v2_params.json` with its value, unit, source, locator and tag.

Tags:
- **[L]** taken from a published source.
- **[D]** derived from [L] values by a script in `kyh-cyber-insurance/scripts/`.
- **[A]** an assumption. Every [A] carries a sensitivity range, and every quote lists the [A] values it used.

Sources and locators follow the V2 specification; they were not re-checked against the reports themselves.

## 1. What the model does

V2 replaces V1's additive posture score with a frequency–severity model built from published claims data.
It splits each risk into five perils, prices how often each happens and how much each costs, applies the
policy's retention and limits, and divides the expected loss by a target loss ratio.

```
For each peril p in {RANSOMWARE, BEC, FTF, MISC_FIRST_PARTY, THIRD_PARTY}:
  λ_p = λ_p,global × R_turnover_freq(R) × R_sector_freq(sector) × F_india,p × M_controls_freq,p × M_claims
  X_p ~ Lognormal(mean = m_p × R_turnover_sev(R) × R_sector_sev(sector) × S_india, σ)
  payout_p = E[ min( Σ_h s_p,h · M_sev,p,h · (X_p − d)+ , L_total ) ]          (no per-cover sub-limits)

Expected loss      EL = Σ_p λ_p × payout_p
Technical premium     = EL × (1 + trend) / TLR          trend = 0, TLR = 0.50
Payable               = Technical premium × 1.18          GST 18%, shown as its own line
```

There is one premium per policy; the peril split is shown in the breakdown. Model inputs from the source
data are in USD and converted at `usd_inr` (88.0 [A], TODO-SOURCE: the current RBI reference rate).
Turnover is entered in INR; all outputs are in INR. The India factors `F_india` and `S_india` are kept as
parameters but set to 1, so no India adjustment is applied yet.

**The central rule is unchanged: monitoring never re-prices a bound policy.** After bind, agent and
fleet data move warranty states only. The engine refuses to price a bound policy, and the tests check
this.

## 2. Inputs

| Input | Where it comes from |
|---|---|
| NIC 2008 code (2-digit division) | Intake screen; questionnaire addendum R1 |
| Annual turnover (INR) | Intake screen; proposal form B1.1, addendum R2 |
| Years in operation | Intake screen; proposal form A3, addendum R3 |
| RBI/SEBI-regulated flag | Intake screen; addendum R4 |
| Material incidents in the last 3 years | Claims history; addendum R5 |
| Overall limit and retention per claim | Policy structure |
| Evidence status of each priced control | Engine A's resolved evidence (§5.2) |

Employees, endpoint counts, IT dependence and record counts are not used for pricing. Data type, DPDP
exposure and cross-border data are deferred.

## 3. Classification

### 3.1 Turnover

| Band (USD) | Frequency | Average loss | Tag |
|---|---|---|---|
| < 10M | 1.07% | $79,000 | Frequency: Coalition's <$25M rate applied to <$10M firms [A]. Severity [L] |
| 10M – 25M | 1.19% | $79,000 | Frequency [D] = 1.07% ÷ 0.90, the 0.90 from IRIS 2025 Fig 7 and App. A2. Severity [L] |
| 25M – 100M | 3.99% | $139,000 | [L] Coalition 2025 Figs 3.1–3.6 |
| ≥ 100M | 5.97% | $228,000 | [L] |

**Transition zones.** There are no cliffs between bands. Within ×/÷ 1.25 of each boundary b, the value
moves log-linearly from the lower band's value to the upper band's:

```
f(R) = f_lo × (f_hi / f_lo) ^ ( ln(R / (b/1.25)) / ln(1.25²) )
```

The zone factor 1.25 is [A] (tested at 1.10 and 1.50). The relativities are
`R_turnover_freq = f(R) / 1.48%` and `R_turnover_sev = sev(R) / $115,000`, Coalition's 2024 global
frequency and average loss [L].

### 3.2 Sector

The NIC 2008 division maps to a rating sector through the table in the parameter file, a GICS-style
judgement mapping [A]. For example, NIC 62 → Information Technology, 86 → Healthcare, 47 → Consumer
Discretionary, 28 → Industrials. A missing or unmapped code is priced at the global average
(relativity 1.0).

- **Frequency relativity** = sector frequency ÷ 1.48%, from Coalition 2025 Fig 2.1 [L]. Education (1.60),
  Professional Services (1.50) and Public Sector (1.34) come from IRIS 2025 App. A1, used directly as
  relativities (treating the median sector as the average is [A]).
- **Severity relativity** = sector average loss ÷ $115,000, from Coalition 2025 Fig 2.2 [L]. Energy uses
  the report's historical $108,000 rather than the volatile 2024 figure. The three gap sectors come from
  NetDiligence 2025 Table 5 SME costs ÷ $264K [D].
- The same relativity applies to every peril [A]; there is no published peril × sector table.

## 4. Perils

| Peril | λ_global | Mean loss m_p | Source |
|---|---|---|---|
| Ransomware | 0.31% | $292,000 | Coalition 2025 Figs 6.1, 6.2 [L] |
| Business email compromise | 0.44% | $35,000 | Figs 4.1, 4.2 [L] |
| Funds transfer fraud | 0.44% | $185,000 (before clawbacks) | Figs 5.1, 5.2 [L] |
| Other first-party | 0.17% | $49,000 | Figs 7.1, 7.2 [L] |
| Third-party liability | 0.02% | $23,000 | Figs 8.1, 8.2 [L] |

The five perils sum to 1.38%. Adding "other" claims (6.2% of 1.48% ≈ 0.09%) gives 1.47%, against Coalition's
1.48% (tested).

**Severity shape.** Each peril's loss is lognormal with a shared σ = 2.193 [D]. `scripts/derive_sigma.py`
solves mean = e^(μ+σ²/2) = $264K and P(X > $1M) = 395 / 8,936 (NetDiligence 2025 SMEs). The equation has
two roots:
- σ = 2.193 predicts P(X > $500K) = 8.26% against the observed 8.24%, so it is kept.
- σ = 1.214 predicts 12.86%, so it is rejected.

IRIS 2025 (firms < $100M, median $357K, p95 $9.1M) gives σ ≈ 1.97, used as the low sensitivity. Per firm and
peril, mean_p = m_p × R_turnover_sev × R_sector_sev × S_india, and μ_p = ln(mean_p) − σ²/2.

## 5. Coverage heads and payout

The heads are Incident Response / Forensics, Business Interruption, Data Restoration, Legal & Regulatory,
Third-Party Liability, Cyber Extortion / Ransomware, Notification, and a new head, **Funds Transfer Fraud /
Social Engineering**, because FTF losses fall under no existing head.

Each peril's loss splits across heads in fixed shares s_p,h (each row sums to 1):

| Peril | IR | BI | DR | Legal | TPL | Extortion | Notification | FTF |
|---|---|---|---|---|---|---|---|---|
| Ransomware | 0.20 [D] | 0.35 [D] | 0.06 [D] | 0.08 | 0.02 | 0.25 | 0.04 | 0 |
| BEC | 0.40 | 0 | 0 | 0.25 | 0.05 | 0 | 0.30 | 0 |
| FTF | 0.05 | 0 | 0 | 0.05 | 0 | 0 | 0 | 0.90 |
| Other first-party | 0.25 | 0.40 | 0.25 | 0.10 | 0 | 0 | 0 | 0 |
| Third-party | 0 | 0 | 0 | 0.30 | 0.70 | 0 | 0 | 0 |

The ransomware BI, restoration and forensics shares are [D] from Coalition 2025 p.17. All other shares are
placeholders [A], TODO-SOURCE: NetDiligence 2025 crisis-services tables 10 and 14.

**Policy structure.** The overall limit L_total and the retention d per claim are the only inputs. There are
**no per-cover sub-limits**: every cover pays its share of the loss above the retention, and the overall
limit is the only cap. (The specification had placeholder sub-limits as shares of L_total; they were
removed by decision, see the report.) The heads are still used to split each loss, so the severity controls
act on the covers they affect, and to show where the expected payout goes.

**Payout.** The expected payout is integrated over the lognormal on a quantile grid: 20,000 mid-point
quantiles below the 99th percentile and 4,000 more above it. The closed-form limited expected value

```
LEV(u) = e^(μ+σ²/2) · Φ((ln u − μ − σ²)/σ) + u · (1 − Φ((ln u − μ)/σ))
```

checks it. For one head with share 1 and overall limit L, the grid matches LEV(d + L) − LEV(d) to about
1 in 10⁷; the test requires 0.1%. A full quote, including every what-if, takes about 0.15 s.

## 6. Controls

### 6.1 Multipliers from claims data

For a control with relative risk S (incident rate without it ÷ with it) and adoption p:

```
m_has = 1 / (p + (1−p)·S)      m_lacks = S / (p + (1−p)·S)      so  p·m_has + (1−p)·m_lacks = 1
```

The average firm sits at 1.0 (tested for every control). Each multiplier is capped to [0.5, 2.0] [A],
tested at [0.4, 2.5].

**Frequency controls.** S and p are from Marsh McLennan, *Using data to prioritize cybersecurity
investments* (2023), Figure 1 [L].

| Control | S | p | Perils | Stage |
|---|---|---|---|---|
| Secure configuration | 5.58 | 0.96 | Ransomware, other first-party | Weakness |
| Privileged access management | 2.92 | 0.35 | Ransomware, other first-party | Execution |
| EDR | 2.23 | 0.82 | Ransomware, other first-party | Execution |
| Logging & monitoring (SOC/SIEM) | 2.19 | 0.88 | Ransomware, other first-party | Execution |
| Vulnerability management (high CVEs ≤ 7 days) | 2.19 | 0.24 | Ransomware, other first-party | Weakness |
| Critical patching (critical CVEs ≤ 7 days) | 1.57 | 0.53 | Ransomware, other first-party | Weakness |
| Awareness (phishing simulation ≥ yearly) | 1.76 | 0.89 | Ransomware, BEC, FTF | Credential |
| Email security (attachment sandboxing) | 1.56 | 0.75 | Ransomware, BEC, FTF | Credential |
| MFA | 1.4 | 0.70 [A] TODO-SOURCE | Ransomware, BEC, FTF | Credential |

**Severity controls**, converted to S and priced with the same formula:

| Control | S | p | Applies to | Source |
|---|---|---|---|---|
| Tested backups | 8.0 | 0.43 | Ransomware → BI, DR, Extortion; other first-party → BI, DR | Sophos 2024, compromised backups [L] |
| Incident response plan | 1.055 | 0.5 [A] | All perils and heads | IBM Cost of a Data Breach 2023 |
| Awareness (severity part) | 1.055 | 0.5 [A] | All perils and heads | IBM 2023 |
| Encryption | 1.101 | 0.5 [A] | Other first-party, third-party → Notification, Legal, TPL | IBM 2019 (outdated, TODO-SOURCE) |

Several controls are not priced because no centred effect has been published: segmentation, asset
inventory, password policy, live monitoring coverage (a warranty only) and payment verification (asked in
addendum R7). They still drive warranties, monitoring and underwriting judgement. Logging's severity
effect is not priced.

Outside-in findings are evidence for these controls, not a separate modifier. Exposed RDP or SMB, weak TLS
and end-of-life software mean secure configuration is not working. A missing DMARC record means email
security is not working; a DMARC record present verifies it.

### 6.2 Evidence status

Engine A resolves the best evidence for each control. V2 reads it as one of four statuses:

| Status | When | Multiplier |
|---|---|---|
| VERIFIED | Agent, fleet or outside-in PASS (technically observed); tested evidence (restore test, tabletop, pentest); an independent document (SOC 2 Type II, ISO 27001 SoA, VAPT, scanner export, configuration or endpoint report) | m_has |
| STATED | Questionnaire "yes"; a self-assessment (CAIQ, SIG Lite) or self-authored policy; a partial result, for example the fleet's "backups recent, restore not tested" | 1 − x·(1 − m_has), x = 0.6 |
| NOT_WORKING | Agent, fleet or scan FAIL; questionnaire "no" | m_lacks |
| UNKNOWN | No evidence ("don't know") | m_lacks |

**Credit x = 0.6 [D].** Marsh measured S on declared controls. If a share f of declarations are hollow,
`1/S_true = (1/S − f)/(1 − f)`, and a declaration is worth `(1 − m_has(S)) / (1 − m_has(S_true))` of the
true credit. Averaged over the Marsh controls (`scripts/derive_credit_x.py`), x is 0.81 / 0.62 / 0.43 for
f = 0.1 / 0.2 / 0.3. The base f = 0.20 is [A].

### 6.3 Combining controls

Controls that defend the same attack stage overlap, so their effects are damped:
- **Within a stage**, multipliers are sorted by |ln m|, largest first, and combined as
  `ln M_stage = Σ_k β^k · ln m_k` with β = 0.5 [A] (tested at 0 and 1). The stages are credential,
  weakness and execution.
- **Across stages**, the stage results multiply.
- **Severity controls** on one peril × head form one group with the same rule.

Every combined multiplier is clamped to [0.27, 3.0] [L]:
- **Floor:** Coalition policyholders have 73% fewer claims than the industry.
- **Ceiling:** end-of-life software is associated with about 3× claims.

## 7. Claims history

```
M_claims = (α + N) / (α + λ_firm × T)
```

It applies equally to every peril's frequency, after controls, with no cap.
- **N** is the number of material incidents in the last 3 years. Material means a loss above the
  retention, a DPDP or CERT-In notification, or a ransom decision. A claim's explicit flag wins;
  otherwise it is inferred from the loss and the incident type.
- **T** = min(3, years in operation).
- **λ_firm** is Σ λ_p after classification and controls.
- **α = 4.22** [D], as the V2 specification gives. At λT = 0.03 this gives N = 0 → 0.99, N = 1 → 1.23,
  N = 2 → 1.46 (tested).

`scripts/derive_alpha.py` reproduces the specification's derivation:
1. A negative-binomial fit to IRIS 2022 Fig 4 (P(0) = 87.1%, P(1) = 11.3%) gives α_total = 1.09.
2. Control heterogeneity is measured on ransomware frequency with β = 0.5, giving 1 + CV² = 1.45 (spec: 1.46).
   Sector heterogeneity over the 13 published sector relativities gives 1.078 (spec: 1.06).
3. `1 + 1/α_resid = (1 + 1/α_total) / ((1 + CV²_controls)(1 + CV²_sector))` gives α ≈ 4.5
   (3.5 / 8.6 for β = 0 / 1; spec: 3.5 / 4.2 / 6.9).

The small differences come from the sector list; the parameter file uses the spec's 4.22. For reference,
the script also prints α measured on the all-peril firm frequency (≈ 1.6).

## 8. Loadings and tax

- **Technical premium** = EL × (1 + trend) / TLR.
- **TLR** = 0.50 [L], between Fitch's 9-year US standalone average (48%) and NAIC 2026's 2025 primary
  standalone figure (57%).
- **Split:** the breakdown shows 50% expected loss, 30% expenses (the IRDAI 2023 cap, commission included)
  and 20% for profit, risk margin, reinsurance and accumulation. V1's separate 1.40 loading is gone.
- **Trend** = 0 [A], tested at ±10%.
- **GST** at 18% is added on top as its own line. The bound premium is the technical premium.

## 9. Eligibility and referral

**Warranties** (gate): MFA, tested backups, EDR, critical patching.
- A warranty passes when VERIFIED. MFA also passes when STATED: the platform cannot verify MFA, and the
  addendum carries a misrepresentation declaration.
- Any other warranty STATED → CONDITIONALLY_ELIGIBLE. Evidence is expected before bind; an underwriter may
  still bind.
- Any warranty NOT_WORKING or UNKNOWN → INELIGIBLE under gate mode BLOCK (the default). Under WARN it is
  conditionally eligible with an underwriter override.
- Gating never changes the price. A failed warranty is priced once, at m_lacks.

**Referral.** The price is computed, but binding needs the underwriter to tick an approval. The reasons are
shown. Triggers:
- turnover above USD 2B;
- any peril's control multiplier at the 3.0 ceiling;
- two or more material incidents;
- an RBI- or SEBI-regulated entity.

The post-bind warranty state machine and grace periods are unchanged.

## 10. Explainability

Every quote stores and returns:
- the classification and turnover zones;
- per peril: base frequency, turnover and sector relativities, each control's multiplier with its
  evidence status and source, the per-stage results, the claims multiplier, the final frequency, the mean
  loss and the payout per head;
- EL, the TLR split, the technical premium, GST and the payable amount;
- the gating result and referral reasons;
- the list of [A] parameters used.

**What-if savings** re-price the quote with one control at a time set to VERIFIED and list the saving,
largest first. The snapshot stores the inputs and the full parameter file, so `pricing_v2.reproduce(snapshot)`
gives the same premium later, whatever has changed since.

## 11. Worked example

`python kyh-cyber-insurance/scripts/worked_example_v2.py` prices an IT services firm with these inputs:
- **Firm:** NIC 62, turnover ₹150 crore (USD 17.05M), 10 years in operation, 1 material incident.
- **Policy:** limit ₹5 crore, retention ₹5 lakh.
- **Evidence:** patching, secure configuration, logging and encryption verified; EDR not working; PAM
  unknown; the rest stated.

| Step | Result |
|---|---|
| Classification | Information Technology; turnover ×0.804 (frequency), ×0.687 (severity); sector ×0.919, ×1.141 |
| Controls (ransomware) | weakness ×0.609, execution ×2.013 (EDR not working, PAM unknown), credential ×0.885 → ×1.085 |
| Claims | (4.22 + 1) / (4.22 + 0.0099 × 3) = ×1.228 |
| Expected loss | ₹49,947 (ransomware ₹20,823, FTF ₹20,287, BEC ₹5,379, other first-party ₹3,277, third-party ₹181) |
| Premium | technical ₹99,895; GST ₹17,981; payable ₹1,17,876 |
| Gate | INELIGIBLE: EDR not working (BLOCK) |
| Largest savings | verify PAM ₹32,421; fix and verify EDR ₹20,877; verify vulnerability management ₹12,739 |

## 12. Sensitivity

`python kyh-cyber-insurance/scripts/sensitivity_v2.py` moves each assumption to its low and high value for
the worked-example firm (base ₹99,895):

| Assumption | Low | Change | High | Change |
|---|---|---|---|---|
| β | 0 | +8.2% | 1 | −15.5% |
| x | 0.4 | +13.2% | 0.8 | −12.6% |
| Control caps | [0.5, 2.0] | base | [0.4, 2.5] | −1.5% |
| Zone factor | 1.10 | 0.0% | 1.50 | +4.5% |
| TLR | 0.48 | +4.2% | 0.57 | −12.3% |
| σ | 1.97 | +16.3% | 2.19 | +0.2% |
| Trend | −10% | −10.0% | +10% | +10.0% |
| α | 3.45 | +4.1% | 6.94 | −7.3% |
| MFA adoption | 0.5 | −3.1% | 0.9 | +1.4% |
| Head-share placeholders | ×0.75 | +0.1% | ×1.25 | −0.1% |
| USD/INR | 83 | −4.1% | 92 | +3.2% |

A lower σ raises the premium: with the mean held fixed, less of the loss sits in the far tail, beyond the
limit, and more sits in the band the policy pays. Without sub-limits the head shares barely matter: they
only decide which covers the severity controls (backups, IR plan, awareness, encryption) act on.

## 13. Limitations

- **US data without India adjustment.** The frequencies and severities come from US-weighted claims books.
  The India factors are set to 1, and the INR rate is a placeholder.
- **Turnover and sector effects** are assumed equal across perils.
- **One σ** is shared by all perils.
- **Mixed sources.** Base frequencies come from Coalition's book, while control adoption comes from
  Marsh's clients. If Marsh's clients are better controlled than Coalition's, the average firm may be
  underpriced.
- **Accumulation** (one event hitting many insureds) is not modelled separately; it sits inside the 20%
  margin.
- **Placeholders:** the head shares, the IR-plan, awareness and encryption adoption, and MFA adoption.
- **No sub-limits.** Each cover can pay up to the overall limit; a real policy wording would usually
  sub-limit some covers (for example funds transfer fraud), which would lower the premium.
- **α's derivation** depends on which frequency the heterogeneity is measured on (§7): the specification's
  ransomware basis gives 4.22, the all-peril basis about 1.6. A real book's loss experience should check it.
- **Untested on Windows:** the agent's Windows checks have not yet run on a real Windows machine.

## 14. V1 → V2

| | V1 | V2 |
|---|---|---|
| Structure | One frequency × Σ (severity fraction × limit) | Five perils, each frequency × lognormal payout |
| Base frequency | Seven illustrative sectors (8–20%) | Coalition 2025 sector and turnover data (about 1–6%) |
| Controls | Additive weights, clamped to [0.6, 1.6] | Multiplicative, centred on the average firm, damped within a stage, bounded [0.27, 3.0] |
| Evidence | Credit scaled 0.6 / 0.8 / 0.9 / 1.0 by strength | VERIFIED / STATED (x = 0.6) / NOT_WORKING / UNKNOWN |
| Severity | Fraction of each head's limit | Lognormal (σ 2.193) through the retention and the overall limit |
| Claims | +10% per incident, cap 1.5 | Credibility (α + N) / (α + λT) |
| Outside-in | Separate exposure modifier | Evidence for the control it concerns |
| Loading | × 1.40 additive | ÷ TLR 0.50, with a 50/30/20 split shown; GST 18% on top |
| Gating | WARN by default | BLOCK by default; MFA may be stated; referral needs approval |
| Explainability | Per-control deltas | Full breakdown, what-if savings, [A] list |

V1's code and parameters are kept, so stored V1 quotes reproduce exactly (`underwriting.reproduce_v1`,
tested). All new quotes use V2.

## 15. Agent changes made for V2

| Change | Why |
|---|---|
| The patch check now passes only if the machine was patched within **7 days** (was 30). Agent policy 2.1.0. | V2 prices critical patching on Marsh's "critical CVEs patched within 7 days". |
| The collector maps the local-administrators check to **CTRL-PAM** (was secure configuration). | V2 prices endpoint privilege management as its own control, with a large effect (S = 2.92). |

The other mappings already matched V2: EDR, backups sent as partial (so they read as STATED), encryption,
logging, and end-of-life OS → secure configuration.

## References

[1] Coalition, *2025 Cyber Claims Report*, 2025.
[2] NetDiligence, *Cyber Claims Study 2025*, 2025.
[3] Cyentia Institute, *Information Risk Insights Study (IRIS) 2025*, 2025; and *IRIS 2022*, 2022.
[4] Marsh McLennan, *Using data to prioritize cybersecurity investments*, 2023.
[5] Sophos, *The Impact of Compromised Backups on Ransomware Outcomes*, 2024.
[6] Sophos, *Active Adversary Report 2025*, 2025.
[7] IBM Security, *Cost of a Data Breach Report*, 2023 and 2019.
[8] L. Meyer et al., "How effective is multifactor authentication at deterring cyberattacks?", Microsoft, 2023.
[9] NAIC, *Report on the Cybersecurity Insurance Market*, 2026.
[10] Fitch Ratings, via *Insurance Journal*, May 2024.
[11] IRDAI, *(Expenses of Management of Insurers transacting General or Health Insurance Business)
Regulations*, 2023.
