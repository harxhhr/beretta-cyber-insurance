module.exports = ({ P, B, CODE, FIG, TAB, SRC, H2, UNNUMBERED, chapterLetter }) => {
  // ---------------------------------------------------------------- A
  UNNUMBERED("Soft Code Flowcharts", 1, "Appendix A");
  chapterLetter("A");
  P("This appendix gives the flowcharts (UML activity diagrams) of the main procedures that are not already shown in Chapter 3. The flowchart of a V2 quote is Fig. 3.10.");
  FIG("docs/diagrams/report/png/B11_act_ingest.png", "Flowchart: the collector's ingestion of an agent report", 545, 740);
  FIG("docs/diagrams/report/png/B13_act_agent_loop.png", "Flowchart: the agent's scheduling and reporting loop", 545, 740);
  FIG("docs/diagrams/report/png/B14_act_end_to_end.png", "Flowchart: end to end, from intake to a breached warranty", 545, 740);
  P("The warranty evaluation that runs on every roll-up is:");
  CODE([
    "Algorithm A.1  evaluate_policy(policy, now)",
    "  if policy.status != BOUND: return",
    "  for each warranty w of the policy:",
    "      e <- resolve_posture(company, w.control)           # strongest, most recent evidence",
    "      if e is None: continue                             # missing evidence is never a breach",
    "      ok <- e.value in {true, partial}",
    "      if w.state == MET and not ok:          move w to IN_GRACE, grace_until <- now + grace_days(w)",
    "      elif w.state == IN_GRACE and ok:       move w to REMEDIATED, then MET",
    "      elif w.state == IN_GRACE and now > grace_until:  move w to BREACHED (consequence applies)",
    "      elif w.state == BREACHED and ok:       move w to REMEDIATED, then MET",
    "      write every move to warranty_events and audit_events",
    "  return states, repricing_performed = false",
  ]);
  P("The collector's fleet roll-up for one control is:");
  CODE([
    "Algorithm A.2  fleet_status(company, control, now)",
    "  observed <- []",
    "  for each host h of the company:",
    "      if now - h.last_seen > 72 h and h ever reported control: observed.append(FAIL)   # silence rule",
    "      elif h has a result r for control and r.status in {PASS, FAIL}: observed.append(r.status)",
    "  if observed is empty: return NOT_OBSERVABLE           # nothing is sent to the platform",
    "  share <- count(PASS in observed) / len(observed)",
    "  return PASS if share >= 0.95 else FAIL",
  ]);

  // ---------------------------------------------------------------- B
  UNNUMBERED("Data Sheets", 1, "Appendix B");
  chapterLetter("B");
  P("The full parameter file is `kyh-cyber-insurance/app/pricing_v2_params.json`; every entry has a value, unit, source, locator and tag. The tables below are extracts. Tags: [L] taken from a published source, [D] derived by a script, [A] an assumption with a sensitivity range.");
  TAB("Global values", ["Parameter", "Value", "Tag", "Source"], [
    ["Global claim frequency", "1.48% per policy-year", "L", "Coalition 2025, 2024 global frequency"],
    ["Global average loss", "$115,000", "L", "Coalition 2025, 2024 global average"],
    ["Other claims share", "6.2%", "L", "Coalition 2025 (reconciliation only)"],
    ["Severity shape σ", "2.193", "D", "NetDiligence 2025 SMEs; scripts/derive_sigma.py"],
    ["Credit for STATED x", "0.6", "D", "scripts/derive_credit_x.py, f = 0.2 [A]"],
    ["Within-stage damping β", "0.5", "A", "Judgement; tested 0 and 1"],
    ["Per-control cap", "[0.5, 2.0]", "A", "Judgement; tested [0.4, 2.5]"],
    ["Combined bounds", "[0.27, 3.0]", "L", "Coalition 2025"],
    ["Claims credibility α", "4.22", "D", "IRIS 2022; scripts/derive_alpha.py"],
    ["Target loss ratio", "0.50", "L", "Fitch 2024 (48%); NAIC 2026 (57%)"],
    ["Expense share", "30%", "L", "IRDAI 2023 expenses regulations"],
    ["Trend", "0", "A", "Tested ±10%"],
    ["GST", "18%", "L", "GST on general insurance premium"],
    ["USD/INR", "88.0", "A", "Placeholder; tested 83 and 92"],
    ["India factors F_india, S_india", "1.0", "A", "Switched off: no India claims data yet"],
  ], [2400, 1600, 600, 3700], { size: 18 });
  TAB("Sector frequencies and average losses (Coalition 2025 unless noted)", ["Sector", "Frequency", "Frequency relativity", "Average loss (USD)", "Severity relativity"], [
    ["Consumer Discretionary", "1.33%", "0.899", "118,493", "1.030"],
    ["Consumer Staples", "2.60%", "1.757", "123,718", "1.076"],
    ["Energy", "1.35%", "0.912", "108,000", "0.939"],
    ["Financial Services", "1.47%", "0.993", "95,066", "0.827"],
    ["Healthcare", "1.38%", "0.932", "144,662", "1.258"],
    ["Industrials", "1.64%", "1.108", "104,741", "0.911"],
    ["Information Technology", "1.36%", "0.919", "131,183", "1.141"],
    ["Materials", "2.20%", "1.486", "99,030", "0.861"],
    ["Nonprofit", "1.34%", "0.905", "73,498", "0.639"],
    ["Real Estate", "1.02%", "0.689", "179,237", "1.559"],
    ["Education (IRIS / NetDiligence)", "—", "1.60", "—", "0.65"],
    ["Professional Services (IRIS / NetDiligence)", "—", "1.50", "—", "1.03"],
    ["Public Sector (IRIS / NetDiligence)", "—", "1.34", "—", "0.68"],
  ], [2900, 1200, 1500, 1500, 1200], { size: 18, align: ["l", "r", "r", "r", "r"] });
  TAB("Loss split by coverage head (shares of each peril's loss)", ["Peril", "IR", "BI", "DR", "Legal", "TPL", "Extortion", "Notify", "FTF"], [
    ["Ransomware", "0.20", "0.35", "0.06", "0.08", "0.02", "0.25", "0.04", "0"],
    ["BEC", "0.40", "0", "0", "0.25", "0.05", "0", "0.30", "0"],
    ["FTF", "0.05", "0", "0", "0.05", "0", "0", "0", "0.90"],
    ["Other first-party", "0.25", "0.40", "0.25", "0.10", "0", "0", "0", "0"],
    ["Third-party", "0", "0", "0", "0.30", "0.70", "0", "0", "0"],
  ], [1900, 700, 700, 700, 800, 700, 1000, 800, 700], { size: 18, align: ["l", "c", "c", "c", "c", "c", "c", "c", "c"] });
  P("The ransomware IR, BI and DR shares are derived from Coalition 2025; the other shares are placeholders [A].");
  TAB("Agent policy thresholds (policy kyh-endpoint-baseline 2.1.0)", ["Setting", "Value", "Provenance"], [
    ["Patch age", "7 days", "Matches Marsh 2023 \"critical CVEs patched within 7 days\""],
    ["Package index age", "14 days", "Assumption"],
    ["EDR signature age", "3 days", "Assumption"],
    ["Backup age", "7 days", "Assumption"],
    ["Local administrators", "At most 3", "Assumption"],
    ["Log retention", "180 days", "CERT-In Directions, 28 April 2022"],
    ["Approved time sources", "samay1.nic.in, samay2.nic.in, time.nplindia.org", "CERT-In Directions"],
    ["Liveness", "UNVERIFIED after 6 h, SILENT after 72 h", "Assumption"],
    ["Fleet pass threshold", "95% of observing hosts", "Assumption"],
    ["Monitoring coverage", "90% of declared endpoints, 14 days after bind", "Assumption"],
  ], [2400, 2900, 3000], { size: 18 });
  TAB("Platform API routes", ["Method and path", "Permission"], [
    ["GET /api/meta, /api/regulatory, /api/forms", "none (public reference data)"],
    ["GET /api/me", "any signed-in role"],
    ["GET /api/dashboard, /api/audit", "staff"],
    ["GET /api/companies (customer: own company only)", "read"],
    ["POST /api/companies; PUT /api/companies/{id}", "intake"],
    ["GET /api/companies/{id}, /fleet; /api/posture/{id}; /api/questionnaires/{id}; /api/documents/{id}; /api/claims/{id}; /api/outside-in/{id}; /api/agent/status/{id}", "read (customer: own company only)"],
    ["POST /api/questionnaires, /api/documents, /api/claims, /api/outside-in", "intake"],
    ["POST /api/documents/{id}/assess", "assess"],
    ["POST /api/quote; GET /api/quote/{id} (customer: trimmed view)", "quote / read"],
    ["POST /api/policies/bind", "bind"],
    ["GET /api/policies/{id}, /warranties, /warranty-events (customer: own policy only)", "read"],
    ["PUT /api/policies/{id}/coverages", "quote"],
    ["GET/PUT /api/admin/config, /api/admin/controls/{id}, /api/admin/sectors; GET /api/admin/pricing-params; /api/admin/collectors", "admin"],
    ["POST /api/collector/rollup", "collector HMAC signature"],
    ["POST /api/agent/report", "legacy agent bearer token (to be disabled)"],
    ["GET /api/demo/tokens", "demonstration only (to be removed)"],
  ], [5800, 2500], { size: 17 });

  // ---------------------------------------------------------------- C
  UNNUMBERED("List of Components", 1, "Appendix C");
  chapterLetter("C");
  P("Beretta has no hardware components beyond ordinary computers (Section 3.2). Its software components are listed below.");
  TAB("Platform (Part 1) modules", ["Module", "Lines", "Purpose"], [
    ["app/api.py", "819", "HTTP routes, permission checks, customer scoping, static files"],
    ["app/pricing_v2.py", "546", "Engine B, model V2: classification, perils, payout, controls, claims, premium, gate, referral, what-if, reproduce"],
    ["app/database.py", "369", "SQLite schema, migrations, seed companies"],
    ["app/underwriting.py", "276", "V1 model (frozen), binding, referral approval"],
    ["app/catalogue.py", "216", "Controls, sectors, coverage heads, default configuration"],
    ["app/observations.py", "199", "Engine A: observations, best-evidence resolution, documents, signals"],
    ["app/fleet.py", "193", "Collector registration and links, roll-up verification, AGENT_FLEET evidence"],
    ["app/coverage.py", "160", "Warranty state machine and coverage consequences"],
    ["app/security.py", "89", "Tokens, role permissions, rate limiting, input validation"],
    ["app/audit.py", "41", "Append-only audit log"],
    ["app/pricing_v2_params.json", "—", "Every V2 parameter with value, unit, source, locator and tag"],
    ["frontend/ (index.html, app.js, styles.css)", "1,654", "Platform dashboard"],
    ["scripts/ (derive_sigma, derive_credit_x, derive_alpha, worked_example_v2, sensitivity_v2, run_demo)", "468", "Model derivations, worked example and sensitivity"],
  ], [3300, 700, 4300], { size: 18, align: ["l", "r", "l"] });
  TAB("Monitoring (Part 2) components", ["Component", "Purpose"], [
    ["agent/kyh_agent/checks/ (windows.py, linux.py, macos.py, parsers.py, verdicts.py)", "Twelve read-only checks per OS, parsers and decision rules"],
    ["agent/kyh_agent/ (runner, policy, security, spool, transport, simulate, config)", "Guarded runner, policy file, signing, outbox, HTTPS client, labelled simulation"],
    ["agent/kyh_agent/policy.json", "Which checks run, how often, and every threshold"],
    ["agent/install/", "Installers for Windows, Linux and macOS"],
    ["collector/kyh_collector/ (server, core, evaluate, db, settings)", "Enrolment, ingestion gate, roll-up, liveness, stand-alone warranties, API"],
    ["collector/kyh_collector/platform_link.py", "Mapping to platform controls, change detection, signing and pushing roll-ups"],
    ["collector/kyh_collector/static/", "Collector dashboard under a strict Content-Security-Policy"],
    ["run_linked_demo.py; integration/test_linked_system.py", "Linked demonstration; end-to-end test of both systems"],
    ["docs/diagrams/, docs/report/make_report_charts.py", "Standard-library generators for every UML diagram and chart in this report"],
  ], [4300, 4000], { size: 18 });

  // ---------------------------------------------------------------- D
  UNNUMBERED("List of Paper Presented and Published", 1, "Appendix D");
  chapterLetter("D");
  P("[[To be completed by the team: list any paper presented or published from this project (authors, title, conference or journal, date), or state that none has been published at the time of submission.]]");

  // ---------------------------------------------------------------- E
  UNNUMBERED("Source Code", 1, "Appendix E");
  chapterLetter("E");
  P("This appendix lists the source code of the parts that carry the project's contributions: on the platform, Engine A (evidence), Engine B (the V2 pricing model), the warranty state machine, the verification of signed fleet roll-ups and the role permissions; on the endpoint agent, the reporting loop, report signing, the decision rules and the Windows checks; and on the collector, the ingestion gate, the fleet roll-up with the silence rule, and the signed link to the platform. Each file is printed in full, exactly as it is in the project folder. The other files (the HTTP routes, the two dashboards, the database schemas, the Linux and macOS checks, the installers, the command-line tools, the model scripts, the demonstration and the tests) are listed in Appendix C and are in the project repository. Lines longer than the page continue on the next line with an indent.");
  const groups = [
    ["E.1", "Platform (Part 1)", [
      ["kyh-cyber-insurance/app/observations.py", "Engine A: observations, evidence strength and best-evidence resolution (Section 3.3.3)."],
      ["kyh-cyber-insurance/app/pricing_v2.py", "Engine B, model V2: classification, perils, lognormal payout, controls, claims credibility, premium, gate, referral, what-if and reproduction (Section 3.3.4)."],
      ["kyh-cyber-insurance/app/coverage.py", "The warranty state machine and coverage consequences (Section 3.3.6)."],
      ["kyh-cyber-insurance/app/fleet.py", "Verification of signed collector roll-ups and AGENT_FLEET evidence (Section 3.3.9)."],
      ["kyh-cyber-insurance/app/security.py", "Role permissions, token checks, rate limiting and input validation (Section 3.3.10)."],
    ]],
    ["E.2", "Endpoint agent (Part 2)", [
      ["kyh-agent/agent/kyh_agent/agent.py", "The agent loop: schedules checks, detects changes, builds signed envelopes, queues and sends them (Section 3.3.7)."],
      ["kyh-agent/agent/kyh_agent/security.py", "HMAC-SHA256 report signing, canonical JSON and the build hash."],
      ["kyh-agent/agent/kyh_agent/checks/verdicts.py", "Decision rules: the status and assurance level of each check."],
      ["kyh-agent/agent/kyh_agent/checks/windows.py", "The Windows checks (read-only PowerShell and registry queries)."],
    ]],
    ["E.3", "Collector (Part 2)", [
      ["kyh-agent/collector/kyh_collector/core.py", "Enrolment and the ingestion gate for signed reports (Section 3.3.8)."],
      ["kyh-agent/collector/kyh_collector/evaluate.py", "Liveness, the silence rule, the 95% fleet roll-up and stand-alone warranties."],
      ["kyh-agent/collector/kyh_collector/platform_link.py", "Mapping to platform controls and the signed roll-ups sent to the platform."],
    ]],
  ];
  for (const [num, title, files] of groups) {
    H2(num, title);
    for (const [f, purpose] of files) SRC(f, purpose);
  }
};
