module.exports = ({ P, B, N, EQ, CH, H2, H3, FIG, TAB, cite, peekFig, peekTab }) => {
  // ================================================================ CHAPTER 4
  CH(4, "Results and Analysis");
  P("This chapter evaluates the system. Section 4.1 gives the test results and how they trace to the requirements. Section 4.2 checks the pricing model against its sources. Section 4.3 works through a full quote, and Section 4.4 measures how much the premium depends on each assumption. Section 4.5 reports the linked demonstration, Section 4.6 the role-separation checks, and Section 4.7 compares V2 with V1 and with current practice. Verification and validation followed IEEE Std 1012-2016 " + cite("ieee1012") + ": every requirement has at least one automated test, and the tests were run after every change. Test design followed the concepts of ISO/IEC/IEEE 29119-1:2022 " + cite("ieee29119") + ": unit tests for each module, property tests for the model (for example, that upgrading a control never raises the premium), and end-to-end tests that run the real servers.");

  H2("4.1", "Test results");
  P("All three test suites pass (" + peekTab() + ", " + peekFig() + "). Part 2's suite starts real HTTPS servers with a private certificate authority; on Windows it needs `openssl` on the path, otherwise six of its tests are skipped rather than failed.");
  TAB("Automated test suites", ["Suite", "Command", "Tests", "Result"], [
    ["Part 1: platform and pricing", "python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance", "65", "OK"],
    ["Part 2: agent and collector", "python kyh-agent/run_tests.py", "158", "OK"],
    ["Integration: both systems", "python integration/test_linked_system.py", "1", "OK"],
    ["**Total**", "", "**224**", "**All pass**"],
  ], [2400, 4200, 800, 900], { size: 18, align: ["l", "l", "r", "c"] });
  FIG("docs/report/png/C8_test_counts.png", "Automated tests per suite");
  TAB("What the tests cover", ["File", "Tests", "Covers"], [
    ["test_pricing_v2.py", "28", "Every control centred; upgrading a control never raises the premium; NOT_WORKING priced like UNKNOWN; turnover, retention and limit monotonic; continuity at band edges; payout matches LEV; aggregate limit caps the payout; no sub-limits; peril frequencies; α values and use; gating and referral; snapshot reproduces; savings real and sorted; every parameter tagged and sourced"],
    ["test_platform.py", "21", "Evidence strength scales credit; documents verify, self-assessments state; best evidence wins; existence, currency and testing; outside-in signals as evidence; quote, bind and snapshot; V1 quotes still reproduce; **no re-pricing after bind**; full warranty state machine; grace days; audit events; HTTP end-to-end; roles; customer read-only and scoped; malformed input"],
    ["test_platform_fleet_link.py", "16", "Bad signature, unknown collector, replay, stale time, unlinked company, invalid values; fleet evidence recorded at TECHNICALLY_OBSERVED; repeats skipped; fleet evidence feeds the quote; backup pass priced as STATED; monitoring-only control never priced; post-bind failure moves the warranty, never the premium"],
    ["kyh-agent: test_parsers.py", "36", "Parsing of recorded Windows, Linux and macOS output, including PowerShell single-object JSON, BitLocker codes, sshd Include files and IPv6 in /proc/net/tcp6"],
    ["kyh-agent: test_verdicts.py", "30", "Every decision rule: patch age, EDR health and signature age, backup age, exposed services, time sources and the rest"],
    ["kyh-agent: test_agent_core.py", "37", "Policy validation and hashing, runner failure handling, scheduler deltas and heartbeats, signing, outbox ordering and limits, transport answers"],
    ["kyh-agent: test_collector.py", "38", "Enrolment, the ingestion gate, replay and signature rejection, build and policy approval, liveness and the silence rule, the 95% roll-up, the warranty state machine, the API"],
    ["kyh-agent: test_platform_link.py", "10", "Mapping and grouping, backup sent as partial, MFA never sent, signed and numbered roll-ups sent only on change, heartbeat, retry, silent host reaches the platform as a failure, no state machine for linked companies"],
    ["kyh-agent: test_end_to_end.py", "7", "Real HTTPS collector and agents: enrol, report, tamper, replay, offline outbox"],
    ["integration/test_linked_system.py", "1", "Both servers: four agents report, the quote uses the fleet, bind, EDR stops on one machine, the platform warranty goes IN_GRACE and the collector shows it, the fix returns it to MET, the premium never changes"],
  ], [2500, 700, 5100], { size: 17 });
  P("The requirements were traced to tests as recommended by ISO/IEC/IEEE 29148 " + cite("ieee29148") + " (" + peekTab() + ").");
  TAB("Requirement traceability", ["Requirement", "Verified by"], [
    ["R1. Every input carries a source, locator and evidence strength; the strongest evidence wins", "test_best_evidence_wins_resolution, test_evidence_strength_scales_credit"],
    ["R2. Every pricing parameter has a value, unit, source, locator and tag; every assumption a sensitivity range", "test_every_parameter_has_a_tag_and_source_and_every_assumption_a_sensitivity"],
    ["R3. The average firm pays the base rate for every control", "test_every_control_is_centred"],
    ["R4. Better evidence never raises the premium", "test_upgrading_any_control_never_raises_the_premium"],
    ["R5. The payout integration is accurate", "test_matches_lev, test_aggregate_limit_caps_the_payout"],
    ["R6. The same inputs always give the same premium, now and later", "test_deterministic, test_v2_snapshot_reproduces, test_v1_quotes_still_reproduce"],
    ["R7. A bound policy is never re-priced", "test_MANDATORY_post_bind_no_reprice, test_post_bind_failure_moves_warranty_not_premium, integration test"],
    ["R8. Agent reports cannot be forged or replayed", "test_end_to_end (tamper, replay), collector ingestion tests"],
    ["R9. Roll-ups to the platform cannot be forged, replayed or sent for unlinked companies", "test_bad_signature, test_replay_rejected, test_company_must_be_linked_to_this_collector"],
    ["R10. The insured customer is read-only and sees only its own company", "test_customer_is_read_only_and_sees_only_their_company"],
  ], [4600, 3700], { size: 18 });

  H2("4.2", "Checks of the pricing model against its sources");
  P("**Severity shape.** The lognormal shape was fitted to two facts from NetDiligence 2025: the SME mean claim ($264K) and the share of claims above $1M (395 of 8,936, or 4.42%) " + cite("netdiligence2025") + ". Two values of σ satisfy both. The third published point, the share above $500K (8.24%), separates them (" + peekFig() + "): σ = 2.193 predicts 8.26% and σ = 1.214 predicts 12.86%. The model uses 2.193. IRIS 2025's median and 95th percentile for firms under $100M give σ ≈ 1.97, which is used as the low value in the sensitivity analysis.");
  FIG("docs/report/png/C7_sigma_fit.png", "Check on the lognormal shape against the share of SME claims above $500K");
  P("**Frequency.** The five peril frequencies add to 1.38%; with Coalition's 6.2% \"other\" claims the total is 1.47%, against the published 1.48%. The 10–25M turnover band (1.19%) is reproduced by `derive_sigma.py` from 1.07% ÷ 0.90.");
  P("**Payout integration.** For a single head with share 1, the 24,000-point quantile grid matches the closed-form LEV(d + L) − LEV(d) of Equation 3.4 to about one part in 10⁷; the test requires agreement within 0.1%.");
  P("**Centring and monotonicity.** For every priced control, p·m_has + (1 − p)·m_lacks = 1 within rounding, so the average firm pays the base rate. Upgrading any control from UNKNOWN to STATED to VERIFIED never raises the premium, a higher retention never raises it, and a higher limit or turnover never lowers it. " + peekFig() + " shows each control's multiplier by evidence status. The spread between verified and failing is widest for secure configuration, EDR and logging, which have high adoption: lacking a control that 96% of firms have is a strong signal. Privileged access management and vulnerability management have low adoption, so verifying them gives the largest reduction.");
  FIG("docs/report/png/C4_control_multipliers.png", "Frequency multiplier of each priced control by evidence status");
  P("**Claims credibility.** " + peekFig() + " shows the claims multiplier for zero to four incidents at λT = 0.03 for the base α and the ends of its sensitivity range. One material incident raises the premium by about 23%, two by about 46%. A larger α gives the firm's own history less weight.");
  FIG("docs/report/png/C5_claims_credibility.png", "Claims-history multiplier against the number of material incidents");
  P("**Derived values.** `derive_credit_x.py` gives x = 0.62 at f = 0.2 (the file uses 0.6). `derive_alpha.py` reproduces α ≈ 4.5 by the specification's method; the specification's value of 4.22 is used. The script also shows that measuring heterogeneity on the all-peril frequency instead of ransomware would give α ≈ 1.6 (Section 5.2).");

  H2("4.3", "Worked example");
  P("`scripts/worked_example_v2.py` prices an IT services firm (" + peekTab() + "). Its evidence is mixed on purpose: four controls verified, EDR failing, PAM unknown and the rest only stated.");
  TAB("Worked example: inputs", ["Input", "Value"], [
    ["Sector", "NIC 62 → Information Technology"],
    ["Turnover", "₹150 crore (USD 17.05M at ₹88/USD), 10–25M band"],
    ["Years in operation; material incidents", "10; 1"],
    ["Policy", "Overall limit ₹5 crore; retention ₹5 lakh per claim"],
    ["VERIFIED", "Critical patching, secure configuration, logging, encryption"],
    ["NOT_WORKING / UNKNOWN", "EDR / privileged access management"],
    ["STATED", "MFA, email security, awareness, vulnerability management, tested backups, IR plan"],
  ], [3000, 5300]);
  TAB("Worked example: results", ["Step", "Result"], [
    ["Classification", "Turnover ×0.804 (frequency), ×0.687 (severity); sector ×0.919, ×1.141"],
    ["Controls, ransomware", "Weakness ×0.609, execution ×2.013 (EDR failing, PAM unknown), credential ×0.885 → ×1.085"],
    ["Claims history", "(4.22 + 1) / (4.22 + 0.00993 × 3) = ×1.228"],
    ["Expected loss", "₹49,947 (ransomware ₹20,823; FTF ₹20,287; BEC ₹5,379; other first-party ₹3,277; third-party ₹181)"],
    ["Premium", "Technical ₹99,895; GST ₹17,981; payable ₹1,17,876"],
    ["Gate", "INELIGIBLE: EDR not working (gate mode BLOCK)"],
    ["Largest savings", "Verify PAM ₹32,421; fix and verify EDR ₹20,877; verify vulnerability management ₹12,739"],
  ], [2300, 6000]);
  P("Ransomware and funds transfer fraud carry 82% of the expected loss (" + peekFig() + "). Funds transfer fraud is large because its mean loss ($185K) is high and its frequency (0.44%) is the joint highest. The premium is built from the expected loss as in " + peekFig(2) + ", and " + peekFig(3) + " lists what verifying each control would save. The firm cannot be bound until EDR is fixed, because EDR is a warranty and it is failing; the premium is still computed so the firm can see the price it would pay.");
  FIG("docs/report/png/C1_expected_loss_by_peril.png", "Expected loss by peril, worked example");
  FIG("docs/report/png/C6_premium_build.png", "From expected loss to payable premium, worked example");
  FIG("docs/report/png/C3_whatif_savings.png", "Premium saving if each control were verified, worked example");
  P("A full quote including the eight what-if re-pricings took 0.18 s on the development laptop, so the what-if list can be computed on every quote.");

  H2("4.4", "Sensitivity analysis");
  P("Every assumption [A] in the parameter file has a low and a high value. `scripts/sensitivity_v2.py` moves each in turn for the worked-example firm (" + peekTab() + ", " + peekFig() + ").");
  TAB("Sensitivity of the worked-example premium (base ₹99,895)", ["Assumption", "Low", "Change", "High", "Change"], [
    ["σ (severity shape)", "1.97", "+16.3%", "2.19", "+0.2%"],
    ["β (within-stage damping)", "0", "+8.2%", "1", "−15.5%"],
    ["x (credit for STATED)", "0.4", "+13.2%", "0.8", "−12.6%"],
    ["TLR", "0.48", "+4.2%", "0.57", "−12.3%"],
    ["Trend", "−10%", "−10.0%", "+10%", "+10.0%"],
    ["α (claims credibility)", "3.45", "+4.1%", "6.94", "−7.3%"],
    ["Turnover zone factor", "1.10", "0.0%", "1.50", "+4.5%"],
    ["USD/INR", "83", "−4.1%", "92", "+3.2%"],
    ["MFA adoption p", "0.5", "−3.1%", "0.9", "+1.4%"],
    ["Control caps", "[0.5, 2.0]", "base", "[0.4, 2.5]", "−1.5%"],
    ["Head-share placeholders", "×0.75", "+0.1%", "×1.25", "−0.1%"],
  ], [3000, 1300, 1300, 1300, 1400], { align: ["l", "c", "r", "c", "r"] });
  FIG("docs/report/png/C2_sensitivity_tornado.png", "Sensitivity of the worked-example premium to each assumption");
  P("Four observations follow.");
  B([
    "No single assumption moves the premium by more than about 16%, so the model's output is driven mainly by its published inputs.",
    "A lower σ raises the premium. With the mean held fixed, a thinner tail puts less of the loss above the ₹5 crore limit and more in the band the policy pays.",
    "The credit for a stated control (x) and the damping within a stage (β) matter most among the controls assumptions. Both are reasons to collect verified evidence: the more controls are verified, the less these assumptions matter.",
    "Without sub-limits, the head-share placeholders barely matter (±0.1%); they only decide which covers the severity controls act on.",
  ]);

  H2("4.5", "Linked demonstration");
  P("`run_linked_demo.py` starts the platform, the collector and four simulated endpoints for Kalinga Components (NIC 28, Industrials, ₹60 crore turnover, 18 years, one material incident, limit ₹2 crore, retention ₹1 lakh). Every simulated result is labelled SIMULATED. The demonstration was run end to end for this report, and " + peekTab() + " lists what happened at each step.");
  TAB("Demonstration run", ["Step", "Action", "Observed result"], [
    ["1", "Agents report; collector sends roll-up #1", "Platform records AGENT_FLEET evidence; 4 of 4 endpoints reporting; secure configuration, PAM, EDR, patching, logging and encryption VERIFIED"],
    ["2", "Underwriter calculates the premium", "₹94,135 technical, ₹1,11,079 payable; CONDITIONALLY_ELIGIBLE (tested backups only stated, because restore testing cannot be observed)"],
    ["3", "Underwriter binds", "Policy BOUND at ₹94,135; warranties created, all MET"],
    ["4", "`break KAL-PLANT-WS03 edr_down`", "3 of 4 hosts pass EDR (75% < 95%); CTRL-EDR warranty MET → IN_GRACE within seconds; premium ₹94,135"],
    ["5", "`fast-forward` (audited DEMO_TIME_TRAVEL)", "EDR warranty IN_GRACE → BREACHED; coverage consequence shown; premium ₹94,135"],
    ["6", "`fix KAL-PLANT-WS03`", "EDR warranty BREACHED → REMEDIATED → MET; premium ₹94,135"],
    ["7", "Re-price the bound policy (as in the integration and platform tests)", "Refused: 409 POLICY_ALREADY_BOUND"],
  ], [600, 2700, 5000], { size: 18 });
  P("The premium did not change at any step after bind, and every roll-up answer from the platform carried `repricing_performed: false`. " + peekFig() + " to " + peekFig(5) + " are screens from this run, and " + peekFig(6) + " is the timing diagram of a warranty moving through its states.");
  FIG("docs/figures/guide_06_collector_prebind.png", "Collector before bind: four simulated endpoints reporting for Kalinga Components");
  FIG("docs/figures/guide_10_whatif_claims.png", "Quote for Kalinga Components: what verification would save, and claims history");
  FIG("docs/figures/guide_13_monitoring_grace.png", "Platform Monitoring tab after EDR stopped on one machine: only the EDR warranty moved", 545, 700);
  FIG("docs/figures/guide_18_breached.png", "After the demonstration's fast-forward: the EDR warranty is breached; the premium is unchanged", 545, 640);
  FIG("docs/figures/guide_19_timeline.png", "Warranty timeline: MET, IN_GRACE, BREACHED, REMEDIATED, MET");
  FIG("docs/diagrams/report/png/B17_timing.png", "UML timing diagram of the EDR warranty during the demonstration");
  P("The fleet section of the Monitoring tab (" + peekFig() + ") shows each host's liveness and results, what the fleet sent for each control, which collector controls built it, and why.");
  FIG("docs/figures/guide_14_fleet.png", "Monitoring tab: endpoints, what the fleet sent, and why", 545, 740);

  H2("4.6", "Role separation");
  P("The insured-customer role was checked against a running server with the customer's token (" + peekTab() + "). Every write was refused, every read of another company returned \"not found\", and the customer's quote contained only the price, the eligibility, the evidence per control and the savings. The underwriter's working (perils, loadings, referral details and input snapshot) is not sent to the customer at all.");
  TAB("Customer-role checks", ["Request as the insured customer", "Result"], [
    ["GET /api/me", "200: read-only, own company"],
    ["GET /api/companies", "Only its own company"],
    ["GET another company, or its policy", "404 NOT_FOUND"],
    ["GET dashboard, audit log, model configuration", "403"],
    ["POST claims, questionnaires, documents, outside-in signals", "403"],
    ["PUT company profile or policy structure; POST quote or bind", "403"],
    ["GET its own quote", "200, with premium, GST, eligibility, statuses, evidence, savings and policy structure only"],
  ], [4800, 3500], { size: 19 });

  H2("4.7", "Comparison with the earlier model and with practice");
  P(peekTab() + " compares V2 with V1. V1 remains in the code, frozen, and its stored quotes still reproduce exactly.");
  TAB("Model V1 and model V2", ["", "V1", "V2"], [
    ["Structure", "One frequency × Σ(severity fraction × limit)", "Five perils, each frequency × lognormal payout"],
    ["Base frequency", "Seven illustrative sectors (8–20%)", "Coalition 2025 sector and turnover data (about 1–6%)"],
    ["Controls", "Additive weights, clamped to [0.6, 1.6]", "Multiplicative, centred, damped within a stage, bounded [0.27, 3.0]"],
    ["Evidence", "Credit scaled 0.6 / 0.8 / 0.9 / 1.0 by strength", "VERIFIED / STATED (x = 0.6) / NOT_WORKING / UNKNOWN"],
    ["Severity", "Fraction of each head's limit", "Lognormal (σ 2.193) through the retention and the overall limit"],
    ["Claims", "+10% per incident, cap 1.5", "Credibility (α + N) / (α + λT)"],
    ["Outside-in", "Separate exposure modifier", "Evidence for the control it concerns"],
    ["Loading", "× 1.40 additive", "÷ TLR 0.50 with a 50/30/20 split; GST 18% on top"],
    ["Gating", "WARN by default", "BLOCK by default; MFA may be stated; referral needs approval"],
    ["Sources", "Illustrative", "Every value tagged [L], [D] or [A] with its source"],
  ], [1700, 3100, 3500], { size: 18 });
  P("Against the practice described by Romanosky et al. " + cite("romanosky2019") + ", where the price is a revenue-based rate with a few modifiers, V2 prices each peril from published claims data, distinguishes verified from stated controls, and shows the applicant the effect of each one. Against the proposal forms studied by Woods et al. " + cite("woods2017a") + ", Beretta asks about fifteen controls, records how each answer was verified, and checks the warranty controls after bind.");

  H2("4.8", "Summary");
  P("All 224 tests pass. The model reproduces its published inputs, its payout integration matches the closed form, and no assumption moves the worked-example premium by more than about 16%. In the linked demonstration, an EDR failure on one machine moved one warranty through all its states while the bound premium stayed fixed, and the customer role was confirmed read-only.");

  // ================================================================ CHAPTER 5
  CH(5, "Advantages, Limitations and Applications");
  P("This chapter sets out what the system does well, where it falls short, and where it could be used.");
  H2("5.1", "Advantages");
  B([
    "**Every number is traceable.** Each pricing value has a source, a locator and a tag in one file; the quote lists the assumptions it used, and a test fails if any parameter lacks a source.",
    "**The price is explained to the insured.** The customer sees the premium, what is needed before cover, the evidence held for each control and how much verifying each one would save.",
    "**Evidence strength matters.** A declared control earns 60% of a verified control's credit, and a failing one is priced as absent, so there is a reason to provide evidence and no reward for an unchecked \"yes\".",
    "**Monitoring is fair to the insured.** The premium is fixed at bind. Monitoring can only move warranty states, with a grace period before any breach, and every state change is logged.",
    "**Reports cannot easily be faked.** Signed reports, sequence numbers, build hashes and the silence rule cover forgery, replay, modified agents and uninstalled agents.",
    "**Privacy by design.** The agent is read-only and never collects file contents, browsing, keystrokes, e-mail, passwords or clear-text user names.",
    "**Reproducible.** The same inputs always give the same premium, and stored snapshots reproduce old quotes under both V1 and V2.",
    "**No dependencies.** The standard-library-only design makes the system easy to inspect, run and audit.",
  ]);
  H2("5.2", "Limitations");
  B([
    "**US data without an India adjustment.** The frequencies and severities come from US-weighted claims studies. The India factors are set to 1 and the USD/INR rate is a placeholder.",
    "**Shared effects.** Turnover and sector relativities are assumed equal across perils, and one σ is used for all perils.",
    "**Mixed sources.** Base frequencies come from Coalition's book and control adoption from Marsh's clients; if Marsh's clients are better controlled, the average firm may be under-priced.",
    "**Placeholders.** The coverage-head shares, the adoption of the IR plan, awareness and encryption, and MFA adoption are assumptions.",
    "**No sub-limits.** Each cover can pay up to the overall limit. Real policy wordings usually sub-limit some covers, such as funds transfer fraud, which would lower the premium.",
    "**α depends on its basis.** Measuring heterogeneity on ransomware frequency gives 4.22; measuring it on the all-peril frequency gives about 1.6. A real book's experience should settle it.",
    "**Accumulation** (one event hitting many insureds) is not modelled separately; it sits inside the 20% margin.",
    "**Windows checks not yet run on real hardware.** They are tested on recorded output; the first run on the Windows virtual machine is their real test.",
    "**Prototype security.** Static role tokens; a demonstration endpoint (`/api/demo/tokens`) that gives the dashboard's role switcher every role's token and must be removed before any real use, since it would let a customer act as an underwriter; shared HMAC secrets rather than public-key signatures; and a legacy single-host agent endpoint that accepts unsigned reports and must be disabled.",
    "**MFA cannot be observed** from endpoints; it needs an identity-provider export or connector.",
    "**Grace periods are whole days**, so the demonstration uses an audited fast-forward.",
  ]);
  H2("5.3", "Applications");
  B([
    "**Insurers and managing general agents in India** can use the design as a reference for evidence-graded SME cyber underwriting with post-bind warranty monitoring.",
    "**Brokers** can show a client the premium effect of each control before approaching insurers.",
    "**SMEs** can use the insured view to plan security spending against premium savings.",
    "**Regulators and auditors** can inspect a complete, reproducible pricing method with every assumption labelled.",
    "**Teaching and research** in actuarial science, security economics and secure systems design, where every part can be read and changed.",
    "**Compliance monitoring.** The agent's CERT-In checks (log retention and time synchronisation) are useful on their own for Indian organisations.",
  ]);
  H2("5.4", "Summary");
  P("Beretta's main strengths are traceability, explanation and a clean separation between monitoring and price. Its main limitation is that its loss data is from the US and several shares and adoptions are still assumptions, each labelled and tested for sensitivity.");

  // ================================================================ CHAPTER 6
  CH(6, "Conclusion and Future Scope");
  H2("6.1", "Conclusion");
  P("This project built Beretta, an explainable cyber-insurance underwriting platform for Indian SMEs linked to a read-only endpoint-monitoring system, and showed that the whole chain from evidence to pricing, binding and post-bind warranty monitoring can be built openly, with every number traceable.");
  P("Engine A records every piece of evidence with its source and strength, and resolves each control to its strongest evidence. Engine B prices five perils from published claims data with a lognormal severity fitted to SME claims, multiplicative control effects centred on the average firm, a 60% credit for stated controls derived from an assumed hollow-declaration rate, and a credibility factor for claims history. The model reproduces its published inputs, its numerical payout matches the closed form, and no single assumption moves the worked-example premium by more than about 16%. Every quote shows the applicant why the premium is what it is and how much verifying each control would save.");
  P("The agent and collector supply signed, tamper-evident endpoint evidence from Windows, Linux and macOS. Before bind this evidence lowers the price of a well-run firm; after bind it moves warranty states only. In the demonstration an EDR failure on one of four machines moved the EDR warranty through IN_GRACE, BREACHED and back to MET while the bound premium stayed at ₹94,135. The system passes 224 automated tests, including one that runs both systems end to end.");
  P("The project's conclusion is that the gap identified in Chapter 2 can be closed: cyber insurance can be priced from published data with the strength of the evidence taken into account, explained to the insured, and monitored after bind without re-pricing the policy.");
  H2("6.2", "Future scope");
  B([
    "**Indian claims data.** Calibrate the India factors F_india and S_india, the head shares and the adoptions from Indian claims, and replace the placeholder exchange rate with the RBI reference rate.",
    "**Identity-provider connectors** for Microsoft Entra ID and Google Workspace, so MFA can be verified rather than stated.",
    "**Sub-limits and policy wording.** Add per-cover sub-limits from a real wording, which would make the coverage consequences of a breached warranty enforceable terms rather than illustrations.",
    "**Accumulation modelling** for events that hit many insureds at once, such as a widely used software vulnerability.",
    "**Public-key signatures** (for example Ed25519) between agent, collector and platform, so no receiver holds the sender's secret, and retirement of the legacy single-host endpoint.",
    "**Real deployment.** Run the agent on a pilot fleet, starting with the Windows virtual machine, and measure false positives and the agent's load.",
    "**Experience checking.** Compare the model's expected losses with an insurer's actual claims to test σ, α and the control effects, in particular the choice between α = 4.22 and α ≈ 1.6.",
    "**Document extraction.** Read assessed fields from SOC 2, ISO 27001 and VAPT reports automatically, keeping the locator for each value.",
  ]);
};
