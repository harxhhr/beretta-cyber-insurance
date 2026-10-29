module.exports = ({ P, B, N, EQ, CODE, CH, H2, H3, FIG, TAB, cite, peekFig, peekTab }) => {
  CH(3, "Methodology and Implementation");
  P("This chapter describes how Beretta was designed and built. Section 3.1 gives the block diagram of the whole system. Section 3.2 describes the hardware it runs on. Section 3.3 describes the software of both parts, with the UML diagrams, the pricing model and the main algorithms. Section 3.4 shows the working system. The design descriptions follow the viewpoints of IEEE Std 1016-2009 (context, composition, logical, information, interaction and state dynamics) " + cite("ieee1016") + ", the requirements were written in the form recommended by ISO/IEC/IEEE 29148:2018 " + cite("ieee29148") + ", and all diagrams use UML 2.5.1 notation " + cite("uml25") + ".");
  P("The work followed an iterative method. Part 1 was built first with an illustrative additive pricing model (V1), the endpoint agent and collector were built next as Part 2, the two were then linked, and finally the pricing engine was replaced with the published-data model V2. V1 is kept, frozen, so that quotes made under it can still be reproduced.");

  // ---------------------------------------------------------------- 3.1
  H2("3.1", "Block diagram");
  P(peekFig() + " is the block diagram. The insured company's machines run the read-only agent. The agents report to the collector (Part 2), which checks each report, works out a result per control for the whole company and sends one signed roll-up to the platform (Part 1). In the platform, Engine A records the roll-up as evidence; before bind Engine B uses that evidence to price the policy, and after bind only the warranty state machine reads it. The collector reads the warranty states back for display.");
  FIG("docs/figures/link_fig1_architecture.png", "Block diagram of Beretta: insured endpoints, the collector (Part 2) and the platform (Part 1)");
  P(peekFig() + " shows the same system as UML components with their interfaces, and " + peekFig(2) + " shows it as a context data-flow diagram: the people and machines outside the system and the data each exchanges with it. " + peekFig(3) + " breaks the system into its level-1 processes and data stores.");
  FIG("docs/diagrams/report/png/S1_component_system.png", "UML component diagram of the whole system");
  FIG("docs/diagrams/report/png/B15_dfd_context.png", "Context data-flow diagram (level 0)");
  FIG("docs/diagrams/report/png/B16_dfd_level1.png", "Level-1 data-flow diagram: processes and data stores");

  // ---------------------------------------------------------------- 3.2
  H2("3.2", "Hardware description");
  P("Beretta needs no special hardware. The platform and the collector are ordinary Python programs that run on any computer with Python 3.9 or later, and the agent runs on the insured company's existing laptops, desktops and servers. " + peekTab() + " lists the machines used to build and demonstrate the system.");
  TAB("Hardware and software used for development and demonstration", ["Item", "Specification", "Role"], [
    ["Development laptop", "Intel Core Ultra 9 285H, 16 cores; 32 GB RAM; Windows 11 Home (build 26200)", "Runs the platform (port 8000), the collector (port 8443), four simulated endpoints, the tests and the document tools"],
    ["Windows virtual machine", "Oracle VirtualBox 7.2; Windows 11 Enterprise evaluation (26H2, x64); 4 GB RAM, 64 GB disk; virtual TPM 2.0 and Secure Boot", "A real endpoint running the agent as a SYSTEM scheduled task, reached over the host-only network 192.168.56.0/24"],
    ["Ubuntu 24.04 build machine", "Linux, Python 3", "Real run of the Linux checks during agent development"],
    ["Python", "3.14.5 on Windows (any 3.9+ works)", "The only runtime for every part"],
    ["Web browser", "Microsoft Edge 156 (any current browser)", "The two dashboards; headless Edge also renders the figures"],
    ["Node.js", "24.16 with the ~docx~ package", "Builds the Word documents only; not part of the system"],
  ], [1700, 3300, 3300]);
  P("The deployment is shown in " + peekFig() + ". In production the platform would run at the insurer, the collector on a server the insurer controls, and the agents on the insured's machines, with HTTPS between each. The agent reaches only the collector, using a certificate authority file pinned at install. " + peekFig(2) + " shows the demonstration set-up with the virtual machine.");
  FIG("docs/diagrams/report/png/S2_deployment.png", "UML deployment diagram");
  FIG("docs/figures/vm_fig1_setup.png", "Demonstration set-up: the laptop runs both systems and the simulated endpoints; the Windows VM runs the real agent");
  P("The agent's footprint is small. It is a set of Python files and a policy file, it runs each check on its own interval (EDR hourly, patching and backup every four hours, the rest daily), and a report is a few kilobytes of JSON. Reports wait in a local SQLite outbox when the machine is offline.");

  // ---------------------------------------------------------------- 3.3
  H2("3.3", "Software description, flowcharts and algorithms");
  H3("3.3.1", "Design constraints and technology");
  P("Four constraints shaped the software, and each is checked by the tests or the code review rules of the project:");
  B([
    "**Standard library only.** Every part uses only the Python standard library, and the dashboards are plain HTML, CSS and JavaScript with no frameworks or external resources. Anyone can read and run the whole system without installing packages, and there are no third-party dependencies to audit.",
    "**One place for every number.** Every V2 pricing value lives in `app/pricing_v2_params.json` with its value, unit, source, locator and tag. Code never contains a pricing constant.",
    "**Monitoring never re-prices.** After bind, monitoring data reaches only the warranty state machine. The pricing engine refuses to price a bound policy, and the platform's answer to every roll-up carries `repricing_performed: false`.",
    "**Simulated data is always labelled.** Every simulated endpoint result starts with \"[SIMULATED]\" and every view shows the label.",
  ]);
  TAB("Software components and technology", ["Component", "Technology", "Main modules"], [
    ["Platform server and API", "Python `http.server`, JSON over HTTP " + cite("rfc8259"), "`api.py` (40 routes), `security.py`, `audit.py`"],
    ["Engine A (evidence)", "Python, SQLite", "`observations.py`, `catalogue.py`"],
    ["Engine B (pricing V2)", "Python `math`, `statistics.NormalDist`", "`pricing_v2.py`, `pricing_v2_params.json`"],
    ["Binding and warranties", "Python, SQLite", "`underwriting.py`, `coverage.py`, `fleet.py`"],
    ["Platform dashboard", "HTML, CSS, JavaScript", "`frontend/index.html`, `app.js`, `styles.css`"],
    ["Endpoint agent", "Python; PowerShell, `/proc`, `winreg`, OS tools (read-only)", "`checks/` (Windows, Linux, macOS), `runner.py`, `security.py`, `spool.py`, `transport.py`"],
    ["Collector", "Python `http.server` over TLS, SQLite", "`server.py`, `core.py`, `evaluate.py`, `platform_link.py`"],
    ["Collector dashboard", "HTML, CSS, JavaScript under a strict Content-Security-Policy", "`static/index.html`, `app.js`, `style.css`"],
  ], [2000, 3000, 3300]);

  H3("3.3.2", "Structure and data model of the platform");
  P("The platform is organised as modules with one job each. " + peekFig() + " shows the classes and modules and how they call each other, and " + peekFig(2) + " the database. A company has one policy; a policy has its coverages, its calculations (each with the full input snapshot and the model version) and its warranties, and each warranty has a history of state changes. Every observation of a control belongs to a company and records its source, locator, evidence strength and time. Every decision is written to the audit table.");
  FIG("docs/diagrams/report/png/S5_class_platform.png", "UML class diagram of the platform (Part 1)");
  FIG("docs/diagrams/report/png/S6_er_platform.png", "Entity–relationship diagram of the platform database");

  H3("3.3.3", "Engine A: evidence and the evidence ladder");
  P("Engine A turns everything known about a company into one resolved value per control. Each input is stored as an **observation** with the control, the value (true, partial or false), the source type, a source locator (for example \"Question IAM-04\" or \"Page 14 §5.2\"), the evidence strength and the time. " + peekTab() + " gives the sources and their default strengths.");
  TAB("Evidence sources and their strength", ["Source", "Default strength", "Example"], [
    ["Questionnaire answer", "DECLARED", "\"Yes, MFA is enforced for e-mail\""],
    ["Self-assessment or self-authored policy", "DOCUMENTED", "CAIQ, SIG Lite, internal IR policy"],
    ["Independent document", "DOCUMENTED", "SOC 2 Type II, ISO 27001 statement of applicability, VAPT report, scanner export, IdP MFA export"],
    ["Test evidence", "TESTED", "Backup restore test, tabletop exercise, penetration test"],
    ["Outside-in scan signal", "TECHNICALLY_OBSERVED", "Exposed RDP; DMARC record present"],
    ["Endpoint agent / fleet roll-up", "TECHNICALLY_OBSERVED", "EDR running with current signatures on 4 of 4 hosts"],
  ], [2600, 2000, 3700]);
  P("For each control the **strongest, most recent** observation wins. If sources disagree (for example a questionnaire says secure configuration is not in place but the fleet shows every host passing), the stronger evidence wins and the control is flagged so the underwriter can see the conflict. The full source trail of every control is one click away in the interface. Observations are never edited: a correction is a new observation. For the incident-response plan and backups, the questionnaire also asks whether the artefact exists, is current and has been tested, because a backup that exists but has never been restored is not the same as a tested backup.");
  P("Model V2 reads the resolved evidence as one of four **statuses** (" + peekTab() + "). This mapping is the link between Engine A and Engine B. " + peekFig() + " shows it as a state machine.");
  TAB("Evidence status used by the pricing model", ["Status", "When", "Pricing effect"], [
    ["VERIFIED", "Agent, fleet or outside-in PASS; tested evidence; an independent document", "Full effect of the control (m_has)"],
    ["STATED", "Questionnaire \"yes\"; a self-assessment or self-authored policy; a partial result such as \"backups recent, restore not tested\"", "60% of the verified credit"],
    ["NOT_WORKING", "Agent, fleet or scan FAIL; questionnaire \"no\"", "Priced as lacking the control (m_lacks)"],
    ["UNKNOWN", "No evidence, or \"don't know\"", "Priced as lacking the control (m_lacks)"],
  ], [1700, 4300, 2300]);
  FIG("docs/diagrams/report/png/B5_sm_evidence.png", "State diagram of a control's evidence status");

  H3("3.3.4", "Engine B: the pricing model V2");
  P("Engine B prices a policy once, at inception. Model V2 replaces V1's additive posture score with a frequency–severity model built from published claims data. It splits the risk into five perils, prices how often each happens and how much each costs, applies the policy's retention and overall limit, and divides the expected loss by a target loss ratio. " + peekFig() + " is the flowchart of a quote.");
  FIG("docs/diagrams/report/png/B12_act_pricing.png", "Flowchart of a V2 quote (UML activity diagram)", 545, 700);
  P("**Inputs.** The model rates on the NIC 2008 code (two-digit division) " + cite("nic2008") + ", annual turnover in rupees, years in operation, whether the firm is RBI- or SEBI-regulated, the number of material incidents in the last three years, the overall limit and retention, and the evidence status of each priced control. Employees, endpoint counts and record counts are kept for the record but not priced. Source data is in US dollars and is converted at a placeholder rate of ₹88 per dollar.");
  P("**Frequency.** For each peril p the annual frequency is");
  EQ("λₚ = λₚ,global × R_turnover,freq × R_sector,freq × F_india,p × M_controls,p × M_claims", "3.1");
  P("where λₚ,global is Coalition's 2025 frequency for the peril " + cite("coalition2025") + " (" + peekTab() + "), the two relativities come from the firm's turnover band and sector, F_india is kept as a parameter but set to 1 because no Indian claims data is used yet, and the last two factors are the control and claims multipliers described below.");
  TAB("Perils, base frequencies and mean losses (Coalition 2025)", ["Peril", "λ global", "Mean loss m_p", "Source locator"], [
    ["Ransomware", "0.31%", "$292,000", "Figs 6.1, 6.2"],
    ["Business email compromise (BEC)", "0.44%", "$35,000", "Figs 4.1, 4.2"],
    ["Funds transfer fraud (FTF)", "0.44%", "$185,000 (before clawbacks)", "Figs 5.1, 5.2"],
    ["Other first-party", "0.17%", "$49,000", "Figs 7.1, 7.2"],
    ["Third-party liability", "0.02%", "$23,000", "Figs 8.1, 8.2"],
  ], [3000, 1300, 2400, 1600], { align: ["l", "r", "r", "l"] });
  P("The five perils sum to 1.38%; adding the 6.2% of claims Coalition files as \"other\" gives 1.47%, against its published all-claims frequency of 1.48%. The turnover bands and their values are in " + peekTab() + ". To avoid a cliff at each band boundary b, within a factor of 1.25 either side the value moves log-linearly from the lower band's value to the upper one's:");
  EQ("f(R) = f_lo × (f_hi / f_lo) ^ [ ln(R / (b / 1.25)) / ln(1.25²) ]", "3.2");
  TAB("Turnover bands", ["Band (USD)", "Frequency", "Average loss", "Tag"], [
    ["< 10M", "1.07%", "$79,000", "[A] frequency: Coalition's < $25M rate applied to < $10M; [L] severity"],
    ["10M – 25M", "1.19%", "$79,000", "[D] 1.07% ÷ 0.90, the 0.90 from IRIS 2025 " + cite("iris2025")],
    ["25M – 100M", "3.99%", "$139,000", "[L] Coalition 2025 Figs 3.1–3.6"],
    ["≥ 100M", "5.97%", "$228,000", "[L]"],
  ], [1600, 1300, 1500, 3900], { align: ["l", "r", "r", "l"] });
  P("The relativities are the band value divided by Coalition's global frequency (1.48%) and average loss ($115,000). The NIC division maps to a rating sector (for example NIC 62 → Information Technology, 86 → Healthcare, 28 → Industrials) whose frequency and severity relativities come from Coalition's sector figures; three sectors missing there come from IRIS 2025 and NetDiligence 2025 " + cite("netdiligence2025") + ". A missing or unmapped NIC code is priced at the global average.");
  P("**Severity and payout.** Each peril's loss X is lognormal with mean mₚ × R_turnover,sev × R_sector,sev and a shared shape σ = 2.193. The shape was fitted to NetDiligence's 2025 SME claims: mean $264,000 and 395 of 8,936 claims above $1M. These two conditions have two solutions; σ = 2.193 also predicts the observed share above $500K (8.26% against 8.24%), while σ = 1.214 predicts 12.86%, so the first is kept (Section 4.2). Each loss is split across coverage heads h in fixed shares s_p,h, and the policy pays the loss above the retention d up to the overall limit L:");
  EQ("payoutₚ = E[ min( Σₕ sₚ,ₕ · M_sev,p,h · (Xₚ − d)⁺ , L ) ]", "3.3");
  P("There are no per-cover sub-limits: every cover pays its share above the retention and the overall limit is the only cap. The head shares still matter, because the severity controls (tested backups, incident response plan, training, encryption) act on the heads they affect. The expectation is integrated numerically over 24,000 quantiles of the lognormal (20,000 below the 99th percentile and 4,000 above) and checked against the closed-form limited expected value");
  EQ("LEV(u) = e^(μ+σ²/2) · Φ((ln u − μ − σ²)/σ) + u · (1 − Φ((ln u − μ)/σ))", "3.4");
  P("For one head with share 1, the grid matches LEV(d + L) − LEV(d) to about one part in 10⁷.");
  P("**Controls.** For a control with relative risk S (claim rate without it divided by the rate with it) and adoption p, the multipliers for having and lacking it are");
  EQ("m_has = 1 / (p + (1 − p)·S)        m_lacks = S / (p + (1 − p)·S)", "3.5");
  P("so that p·m_has + (1 − p)·m_lacks = 1: a firm with the average mix of controls pays the base rate. Each multiplier is capped to [0.5, 2.0]. S and p for the frequency controls are from Marsh McLennan's 2023 study " + cite("marsh2023") + " (" + peekTab() + "); MFA's adoption is an assumption. The severity controls are tested backups (S = 8.0, from Sophos " + cite("sophos2024") + "), the incident-response plan and training (S = 1.055 each, from IBM 2023 " + cite("ibm2023") + ") and encryption (S = 1.101, from IBM 2019 " + cite("ibm2019") + ").");
  TAB("Frequency controls (Marsh McLennan 2023)", ["Control", "S", "p", "Perils", "Attack stage"], [
    ["Secure configuration", "5.58", "0.96", "Ransomware, other first-party", "Weakness"],
    ["Privileged access management", "2.92", "0.35", "Ransomware, other first-party", "Execution"],
    ["EDR", "2.23", "0.82", "Ransomware, other first-party", "Execution"],
    ["Logging & monitoring", "2.19", "0.88", "Ransomware, other first-party", "Execution"],
    ["Vulnerability management (high CVEs ≤ 7 days)", "2.19", "0.24", "Ransomware, other first-party", "Weakness"],
    ["Critical patching (critical CVEs ≤ 7 days)", "1.57", "0.53", "Ransomware, other first-party", "Weakness"],
    ["Security awareness (phishing simulation)", "1.76", "0.89", "Ransomware, BEC, FTF", "Credential"],
    ["Email security (attachment sandboxing)", "1.56", "0.75", "Ransomware, BEC, FTF", "Credential"],
    ["MFA", "1.40", "0.70 [A]", "Ransomware, BEC, FTF", "Credential"],
  ], [3100, 700, 900, 2300, 1300], { align: ["l", "r", "r", "l", "l"] });
  P("A VERIFIED control gets m_has, NOT_WORKING and UNKNOWN get m_lacks, and a STATED control gets part of the verified credit:");
  EQ("m_stated = 1 − x · (1 − m_has),   x = 0.6", "3.6");
  P("The credit x is derived, not chosen. Marsh measured S on declared controls. If a share f of declarations are hollow, the true relative risk satisfies 1/S_true = (1/S − f)/(1 − f), and a declaration is worth (1 − m_has(S)) / (1 − m_has(S_true)) of the true credit. Averaged over the Marsh controls this gives x = 0.81, 0.62 and 0.43 for f = 0.1, 0.2 and 0.3; the model uses f = 0.2 [A].");
  P("Controls that defend the same attack stage overlap, so their effects are damped. Within a stage the multipliers are sorted by |ln m|, largest first, and combined as");
  EQ("ln M_stage = Σₖ βᵏ · ln mₖ,   β = 0.5", "3.7");
  P("The stage results then multiply, and the combined multiplier for a peril is clamped to [0.27, 3.0]: the floor is Coalition's finding that its policyholders have 73% fewer claims than the industry, the ceiling its finding that end-of-life software is associated with about three times as many claims " + cite("coalition2025") + ".");
  P("**Claims history.** Material incidents in the last three years (a loss above the retention, a DPDP or CERT-In notification, or a ransom decision) enter through a credibility multiplier applied to every peril:");
  EQ("M_claims = (α + N) / (α + λ_firm · T),   α = 4.22", "3.8");
  P("where N is the number of material incidents, T = min(3, years in operation) and λ_firm is the firm's total frequency after classification and controls. This is the Poisson–gamma credibility form " + cite("buhlmann1967") + ". The value α = 4.22 comes from a negative-binomial fit to IRIS 2022 incident counts (P(0) = 87.1%, P(1) = 11.3%, α_total = 1.09), with the heterogeneity explained by controls and sector removed " + cite("iris2022") + ". At λT = 0.03 it gives multipliers of 0.99, 1.23 and 1.46 for zero, one and two incidents.");
  P("**Premium.** The expected loss is EL = Σₚ λₚ × payoutₚ, and");
  EQ("Technical premium = EL × (1 + trend) / TLR,   trend = 0,   TLR = 0.50", "3.9");
  P("The target loss ratio of 0.50 lies between Fitch's nine-year average for US standalone cyber (48%) " + cite("fitch2024") + " and NAIC's latest figure (57%) " + cite("naic2026") + ". The breakdown shows it as 50% expected loss, 30% expenses (the IRDAI 2023 expense cap, commission included " + cite("irdai2023") + ") and 20% for profit, risk margin, reinsurance and accumulation. GST at 18% is added as its own line; the bound premium is the technical premium.");
  P("**Gating and referral.** MFA, tested backups, EDR and critical patching are warranties. A warranty passes when VERIFIED (MFA also when STATED, because the platform cannot verify MFA and the questionnaire addendum carries a misrepresentation declaration). A warranty that is only STATED makes the quote CONDITIONALLY_ELIGIBLE; one that is NOT_WORKING or UNKNOWN makes it INELIGIBLE under the default gate mode BLOCK. Gating never changes the price. A quote is referred, so binding needs an underwriter's approval, when turnover exceeds USD 2 billion, a peril's control multiplier is at the 3.0 ceiling, the firm has two or more material incidents, or it is RBI- or SEBI-regulated.");
  P("**Explainability and reproducibility.** Every quote stores and returns the classification, the per-peril chain, every control's multiplier with its status and source, the payout per head, the loadings, the gate and referral reasons, the list of assumptions used, and a what-if list that re-prices the quote with each control in turn set to VERIFIED. The snapshot stores the inputs and the whole parameter file, so `pricing_v2.reproduce(snapshot)` gives the same premium later, whatever has changed since. Python floats are IEEE 754 binary64 " + cite("ieee754") + " and the calculation has no random element, so the same inputs always give the same premium. The algorithm is:");
  CODE([
    "Algorithm 3.1  calculate_premium(policy)",
    "  if policy.status == BOUND: raise POLICY_ALREADY_BOUND        # monitoring never re-prices",
    "  prm    <- load pricing_v2_params.json",
    "  firm   <- classify(NIC code, turnover, years, regulated)     # sector, bands, transition zones",
    "  status <- {c: evidence_status(resolve_posture(c)) for each priced control c}",
    "  for each peril p in {RANSOMWARE, BEC, FTF, MISC_FIRST_PARTY, THIRD_PARTY}:",
    "      M_ctl[p] <- clamp( prod over stages ( exp( sum_k beta^k * ln m_k ) ), 0.27, 3.0 )",
    "      lam[p]   <- lam_global[p] * R_turn_f * R_sec_f * F_india[p] * M_ctl[p]",
    "  M_claims <- (alpha + N) / (alpha + sum(lam) * min(3, years))",
    "  for each peril p:",
    "      lam[p]   <- lam[p] * M_claims",
    "      mu       <- ln(m[p] * R_turn_s * R_sec_s * S_india) - sigma^2 / 2",
    "      pay[p]   <- E[ min( sum_h s[p,h] * M_sev[p,h] * max(X - d, 0), L ) ],  X ~ LN(mu, sigma)",
    "  EL <- sum_p lam[p] * pay[p];   technical <- EL * (1 + trend) / TLR;   gst <- 0.18 * technical",
    "  gate <- warranties(status);   referral <- triggers(firm, M_ctl, N, regulated)",
    "  what_if <- for each control not VERIFIED: re-price with it VERIFIED, record the saving",
    "  store calculation with input snapshot, parameter file and model version; audit POLICY_QUOTED",
  ]);

  H3("3.3.5", "Eligibility, binding and the policy life cycle");
  P("A policy moves through the states shown in " + peekFig() + ": DRAFT, QUOTED after a calculation, and BOUND when an underwriter binds it at a stored calculation. Binding refuses a policy that is already bound or a calculation that does not belong to the policy, refuses an INELIGIBLE quote under gate mode BLOCK, and refuses a referred quote unless the underwriter has approved the referral. At bind the warranties are created, all MET, and evaluated once against the current evidence. " + peekFig(2) + " shows the sequence of a quote and a bind across the modules.");
  FIG("docs/diagrams/report/png/B7_sm_policy.png", "State diagram of a policy");
  FIG("docs/diagrams/report/png/B10_seq_quote_bind.png", "Sequence diagram: quote and bind");

  H3("3.3.6", "The warranty state machine");
  P("After bind, each warranty control is in one of four states (" + peekFig() + "). A failing result moves a MET warranty to IN_GRACE and starts its grace period (14 days for patching, 7 for EDR, backups and MFA, 14 for monitoring coverage). If the control is still failing when the grace period ends, the warranty is BREACHED, and the configured coverage consequence applies to claims from then on (for example, data-restoration claims subject to 50% co-insurance while the backup warranty is breached; these consequences are illustrative, not policy wording). A passing result moves an IN_GRACE or BREACHED warranty to REMEDIATED and then to MET. Missing evidence is never a breach. Every transition is written to the warranty event log and the audit log. Grace periods are whole days, so the demonstration uses a `fast-forward` command, which is itself audited as DEMO_TIME_TRAVEL.");
  FIG("docs/figures/guide_fig_platform_states.png", "Warranty states on the platform and the grace period of each warranty");
  FIG("docs/diagrams/report/png/B3_sm_warranty_platform.png", "UML state machine of a platform warranty");

  H3("3.3.7", "Part 2: the endpoint agent");
  P("The agent is a small Python program installed on each of the insured's machines. It reads settings and status from the operating system, never changes anything, and sends a signed report. It has no window on the endpoint; it runs as a Windows scheduled task as SYSTEM, a systemd service on Linux or a launchd daemon on macOS. An administrator can run `once --no-send` to see the results locally, and `show-policy` to see exactly what is checked and what is never collected. The agent is built in ten layers (" + peekFig() + "); each layer talks only to its neighbours, which is why the checks can be tested on recorded output without a real Windows machine.");
  FIG("kyh-agent/docs/figures/fig2_agent_layers.png", "Agent layers, from the operating system (1) to the network (10)", 480);
  P("**Checks.** The policy groups twelve checks into three tiers (" + peekTab() + "). Warranty checks feed the coverage warranties; the two regulatory checks cover the CERT-In obligations on log retention and time synchronisation " + cite("certin2022") + "; the rest are hygiene checks stored as evidence.");
  TAB("The twelve agent checks", ["Control (tier)", "Windows", "Linux", "macOS"], [
    ["PATCH (warranty)", "Windows Update Agent search, Get-HotFix", "apt-get -s upgrade, dpkg.log; dnf updateinfo", "softwareupdate -l"],
    ["EDR (warranty)", "Get-Process, Get-MpComputerStatus", "/proc process table; mdatp health", "ps process table"],
    ["BACKUP (warranty)", "agent marker; Get-WBSummary; backup processes", "agent marker; backup processes", "marker; tmutil latestbackup"],
    ["MFA (warranty)", "not observable: NOT_SUPPORTED", "same", "same"],
    ["DISK_ENCRYPTION", "Get-BitLockerVolume; manage-bde", "lsblk: dm-crypt under /", "fdesetup status"],
    ["FIREWALL", "Get-NetFirewallProfile", "ufw, firewalld, nftables, iptables", "socketfilterfw"],
    ["EXPOSED_SERVICES", "Get-NetTCPConnection -State Listen", "/proc/net/tcp, tcp6", "netstat -anv"],
    ["REMOTE_ACCESS", "registry: RDP, NLA", "sshd -T or sshd_config with Includes", "sshd_config"],
    ["ADMIN_ACCOUNTS", "Administrators group, Guest account", "sudo/wheel/admin groups, extra UID 0", "dscl admin group"],
    ["OS_SUPPORT", "build number vs lifecycle table", "/etc/os-release vs lifecycle table", "major version"],
    ["LOG_RETENTION (regulatory)", "oldest Security/System event; forwarder", "oldest log or journal entry; forwarder", "forwarder process"],
    ["TIME_SYNC (regulatory)", "w32tm /query /status", "timedatectl, chronyc, timesyncd", "systemsetup"],
  ], [2000, 2300, 2300, 1700], { size: 18 });
  P("Every OS command goes through one function that takes an argument list (never a shell string), applies a timeout, forces the C locale and hides the console window. Each verdict returns a status (PASS, FAIL, NOT_APPLICABLE, NOT_SUPPORTED or ERROR) and an assurance level (OPERATING, RUNNING, PRESENT or ABSENT), so a Defender installation with nine-day-old signatures is a FAIL with assurance PRESENT, not a PASS. For V2, the patch check passes only if the machine was patched within seven days, matching Marsh's \"critical CVEs patched within 7 days\". MFA is reported as NOT_SUPPORTED because it is enforced by the identity provider, not the laptop.");
  P("**Reports and their protection.** A report is a JSON envelope with a kind (full snapshot daily, delta on any change, heartbeat every 15 minutes), the agent's identity, a sequence number, the build hash and policy hash, and the results. The agent serialises it with sorted keys and computes HMAC-SHA256 " + cite("rfc2104", "fips180") + " over the exact bytes with its 256-bit secret. The sequence number only increases, so an old \"all PASS\" report cannot be replayed. The build hash is a SHA-256 over the agent's code and policy, so an agent edited to always pass is detected. Reports are written to an outbox before sending and sent over TLS 1.2 or later to a collector whose CA is pinned " + cite("rfc8446") + ". " + peekFig() + " shows the classes of the agent and " + peekFig(2) + " the enrolment and reporting sequence. " + peekFig(3) + " traces one check from a Windows setting to the platform.");
  FIG("docs/diagrams/report/png/S3_class_agent.png", "UML class diagram of the agent");
  FIG("docs/diagrams/report/png/B8_seq_enrol_report.png", "Sequence diagram: agent enrolment and a signed report");
  FIG("docs/figures/guide_fig_one_check.png", "One check from the Windows setting to the platform warranty");

  H3("3.3.8", "Part 2: the collector");
  P("The collector is the insurer-side server for the agents. An overview is in " + peekFig() + ". It enrols agents with limited-use tokens, checks every report, stores accepted reports unchanged with their SHA-256, and rolls the results up per company.");
  FIG("kyh-agent/docs/figures/fig1_overview.png", "Collector overview: agents, ingestion, roll-up, warranties and the dashboard");
  P("**Ingestion.** A report is checked in a fixed order before anything is stored (" + peekFig() + "): size, known agent, signature, schema, sequence, timestamp and result format. Signature failures and replays are written to the audit log as security events. Each stored result is labelled TECHNICALLY_OBSERVED only if the build hash and policy hash are on the approved list; otherwise it is stored as UNTRUSTED_BUILD or UNTRUSTED_POLICY and ignored. Simulated reports are accepted only for companies created in demo mode.");
  FIG("kyh-agent/docs/figures/fig3_ingest.png", "The ingestion gate: each check must pass before the next runs", 480);
  P("**Roll-up and the silence rule.** Each host is ONLINE, UNVERIFIED after six hours without a report, or SILENT after 72 hours (" + peekFig() + "). A silent host counts as a FAIL for every control it used to report, which defeats the simplest way to hide a failing machine: uninstalling the agent. A host fails a control if any of its checks for that control fails. For the company, only hosts that could observe the control count, and the control passes if at least 95% of them pass (" + peekFig(2) + "). If no host can observe a control, as for MFA, its status is NOT_OBSERVABLE and nothing is sent for it.");
  FIG("kyh-agent/docs/figures/fig6_liveness.png", "The silence rule", 480);
  FIG("kyh-agent/docs/figures/fig4_rollup.png", "Roll-up from a check result to a company control", 480);
  FIG("docs/diagrams/report/png/B6_sm_liveness.png", "UML state machine of host liveness");
  P("A company could enrol only its best machines, so the collector adds a monitoring-coverage warranty: at least 90% of the endpoints declared on the proposal form must be reporting, with 14 days after bind to roll the agent out. For companies that are not linked to the platform, the collector runs its own warranty state machine (" + peekFig() + ", " + peekFig(2) + "), in which a fix must hold for 24 hours before REMEDIATED returns to MET. For linked companies it runs none and shows the platform's states. The collector's classes and database are in " + peekFig(3) + " and " + peekFig(4) + ".");
  FIG("kyh-agent/docs/figures/fig5_states.png", "Collector warranty states (stand-alone mode)", 480);
  FIG("docs/diagrams/report/png/B4_sm_warranty_collector.png", "UML state machine of a collector warranty (stand-alone mode)");
  FIG("docs/diagrams/report/png/S4_class_collector.png", "UML class diagram of the collector");
  FIG("docs/diagrams/report/png/S7_er_collector.png", "Entity–relationship diagram of the collector database");

  H3("3.3.9", "Linking Part 2 to Part 1");
  P("The link gives each part one job. The collector owns everything about endpoints; the platform owns everything about the policy and runs the only warranty state machine for linked companies. The collector maps its twelve controls to the platform's controls (" + peekTab() + ") and sends one signed roll-up per company when a result changes and as a heartbeat every 15 minutes.");
  TAB("Mapping of collector controls to platform controls", ["Collector control", "Platform control", "Rule"], [
    ["PATCH", "CTRL-PATCH-CRIT (warranty)", ""],
    ["EDR", "CTRL-EDR (warranty)", ""],
    ["BACKUP", "CTRL-BACKUP-TESTED (warranty)", "A pass is sent as ~partial~: restore testing is not observable, so it reads as STATED"],
    ["MFA", "CTRL-MFA (warranty)", "Never sent: not observable from endpoints"],
    ["DISK_ENCRYPTION", "CTRL-ENCRYPTION", ""],
    ["FIREWALL, REMOTE_ACCESS, EXPOSED_SERVICES, OS_SUPPORT", "CTRL-SECCONFIG", "Fails if any source fails"],
    ["ADMIN_ACCOUNTS", "CTRL-PAM", "Changed for V2, which prices PAM separately"],
    ["LOG_RETENTION, TIME_SYNC", "CTRL-LOGGING", "The two CERT-In checks"],
    ["MONITORING_COVERAGE", "CTRL-AGENT-COVERAGE (monitoring only)", "Never priced, never gates a quote"],
  ], [3000, 2700, 2600], { size: 18 });
  P("The platform checks each roll-up before storing it: the collector must be registered, the HMAC-SHA256 over the body must match its secret, the sequence number must be higher than the last one accepted, the timestamp must be within five minutes, and the company must be linked to that collector. Each result becomes an AGENT_FLEET observation at TECHNICALLY_OBSERVED strength. Before bind it feeds the next quote like any other evidence; after bind it reaches only the warranty state machine. " + peekFig() + " shows the two jobs, and " + peekFig(2) + " and " + peekFig(3) + " the sequence of one roll-up.");
  FIG("docs/report/png/C9_monitoring_two_jobs.png", "What monitoring does before and after bind");
  FIG("docs/figures/link_fig2_sequence.png", "What happens when EDR stops on one of four machines after bind");
  FIG("docs/diagrams/report/png/B9_seq_rollup.png", "UML sequence diagram of the Part 2 → Part 1 roll-up");

  H3("3.3.10", "Roles and access control");
  P("The platform has three roles (" + peekTab() + "). Role separation is enforced on the server: every route checks the caller's permission, and for the insured customer every read is limited to its own company, so asking for another company's records returns \"not found\". The interface follows the same rules, but hiding a button is never the only protection.");
  TAB("Roles and permissions", ["Role", "Permissions", "Can do"], [
    ["Insured customer", "read (own company only)", "See its profile, classification, evidence per control, documents and claims on record, premium, eligibility and what would lower the premium, policy and warranty states, and the Monitoring tab. Cannot edit anything, see other companies, the portfolio, the audit log or the model configuration."],
    ["Underwriter", "read, staff, intake, quote, bind, assess", "Enter intake, record claims, documents and signals, assess documents, price, approve referrals and bind, review warranties and the audit log"],
    ["Administrator", "all of the above + admin", "Edit model configuration and gate mode, register collectors and link companies"],
  ], [1700, 2300, 4300]);
  P(peekFig() + " and " + peekFig(2) + " are the use-case diagrams for the insured and the insurer.");
  FIG("docs/diagrams/report/png/B1_usecase_insured.png", "Use-case diagram for the insured company");
  FIG("docs/diagrams/report/png/B2_usecase_insurer.png", "Use-case diagram for the insurer");

  H3("3.3.11", "Security and privacy design");
  P(peekTab() + " lists the main threats to the system and how each is handled.");
  TAB("Threats and countermeasures", ["Threat", "Countermeasure"], [
    ["Forged or altered agent report", "HMAC-SHA256 over the exact bytes with a per-agent 256-bit secret; rejected and audited on mismatch"],
    ["Replay of an old passing report", "Monotonic sequence number per agent, kept across restarts; timestamp window"],
    ["Modified agent that always passes", "Build hash of code and policy; results from an unapproved build are not trusted"],
    ["Uninstalling the agent from a failing machine", "Silence rule: a host silent for 72 hours fails every control it used to report; monitoring-coverage warranty"],
    ["Fake collector or TLS interception", "Agent trusts only the collector's pinned CA; TLS 1.2 or later"],
    ["Forged roll-up to the platform", "HMAC-SHA256 with the collector's secret, sequence check, five-minute window, company must be linked"],
    ["Pushing code to endpoints through the policy", "The policy file can only choose from checks compiled into the agent and set thresholds"],
    ["Command injection in checks", "Commands passed as argument lists, never shell strings; read-only commands only"],
    ["Customer editing its own data or seeing others'", "Server-side permissions; customer reads scoped to its company; all writes need staff permissions"],
    ["SQL injection, oversized requests, abuse", "Parameterised SQL throughout; 1 MB body cap; per-token rate limit; input validation with structured errors"],
    ["Script injection in the collector dashboard", "Strict Content-Security-Policy: no inline scripts or styles, no external resources"],
  ], [3200, 5100], { size: 18 });
  P("For privacy, the agent never collects file contents, browsing history, keystrokes, e-mail, passwords or clear-text user names, and it writes a local log of every report it sends so the insured's staff can see exactly what left the machine. Uploaded documents are stored as metadata with assessed fields and locators; their contents are never opened or run.");

  H3("3.3.12", "User interface");
  P("Both dashboards share one visual style: ink on a blue-grey ground, white cards, colour only on states and on the main figure of a screen, and the evidence ladder (four ascending bars) on every evidence chip to show its strength. Labels are in plain language and say what a state means and what happens next. " + peekFig() + " to " + peekFig(8) + " show the platform as the underwriter sees it, and " + peekFig(9) + " and " + peekFig(10) + " as the insured customer sees it.");
  FIG("docs/figures/guide_02_portfolio.png", "Platform: portfolio dashboard (underwriter)");
  FIG("docs/figures/guide_03_intake_top.png", "Platform: company intake, with classification and endpoint monitoring");
  FIG("docs/figures/guide_05_questionnaire.png", "Platform: security questionnaire with resolved value and evidence per control", 545, 640);
  FIG("docs/figures/guide_07_quote_top.png", "Platform: quote summary with premium, eligibility and referral");
  FIG("docs/figures/guide_08_classification_perils.png", "Platform: classification and the per-peril frequency and payout");
  FIG("docs/figures/guide_09_controls.png", "Platform: controls and evidence, largest effect first", 545, 700);
  FIG("docs/figures/guide_11_premium_build.png", "Platform: from expected loss to premium");
  FIG("docs/figures/guide_12_admin.png", "Platform: model configuration (administrator), priced controls with their sources", 545, 700);
  FIG("docs/figures/guide_20_customer_details.png", "Platform as the insured customer: read-only view of its own company");
  FIG("docs/figures/guide_21_customer_premium.png", "Platform as the insured customer: premium, eligibility, savings and evidence per control", 545, 720);

  // ---------------------------------------------------------------- 3.4
  H2("3.4", "Implementation");
  P("The system was implemented and run as described above. " + peekTab() + " gives the size of each part. The tests are described in Chapter 4.");
  TAB("Size of the implementation (lines, including comments)", ["Part", "Folder", "Lines"], [
    ["Platform application", "kyh-cyber-insurance/app", "2,908"],
    ["Platform dashboard", "kyh-cyber-insurance/frontend", "1,654"],
    ["Model derivation and example scripts", "kyh-cyber-insurance/scripts", "468"],
    ["Platform tests", "kyh-cyber-insurance/tests", "1,053"],
    ["Endpoint agent", "kyh-agent/agent", "2,642"],
    ["Collector and its dashboard", "kyh-agent/collector", "1,904"],
    ["Agent and collector tests", "kyh-agent/tests", "1,716"],
    ["Integration test", "integration", "178"],
    ["UML figure generator", "docs/diagrams", "2,212"],
  ], [3200, 3600, 1500], { align: ["l", "l", "r"] });
  P("Installers are provided for Windows (PowerShell, scheduled task as SYSTEM), Linux (systemd) and macOS (launchd). " + peekFig() + " shows a production deployment, and " + peekFig(2) + " the steps of the demonstration with the Windows virtual machine. The collector's own dashboard is shown in " + peekFig(3) + " to " + peekFig(5) + ".");
  FIG("kyh-agent/docs/figures/fig7_deploy.png", "Deployment of the agent and collector", 500);
  FIG("docs/figures/vm_fig2_flow.png", "Demonstration flow with the Windows virtual machine");
  FIG("docs/figures/guide_15_collector_overview.png", "Collector: overview of companies and hosts");
  FIG("docs/figures/guide_16_collector_company.png", "Collector: one company, with the platform's warranty states and the link panel");
  FIG("docs/figures/guide_17_collector_host.png", "Collector: one host, with the evidence behind each check");

  H2("3.5", "Summary");
  P("Beretta is built from two standard-library Python systems. The platform grades evidence, prices with a published-data frequency–severity model whose every factor is shown, binds, and runs the only warranty state machine; the agent and collector supply signed, read-only endpoint evidence that drives warranties after bind and never the premium. The next chapter tests whether it works and whether the model matches its sources.");
};
