// Builds docs/Beretta_Demo_Presenter_Guide.docx  (node build_demo_guide.js; PDF via Word, see build_all_windows.py)
// The presenter's guide: setup, the demonstration step by step, and what every screen element means.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, AlignmentType, HeadingLevel,
  WidthType, ShadingType, BorderStyle, Footer, PageNumber, PageBreak, TableOfContents, LevelFormat,
} = require("docx");

const FIG = path.join(__dirname, "figures");
const FONT = "Times New Roman";
const MONO = "Courier New";
const W = 9026;
const LINE = { style: BorderStyle.SINGLE, size: 4, color: "9AA4B5" };
const borders = { top: LINE, bottom: LINE, left: LINE, right: LINE };

// inline markup: **bold**, `code`, _italic_
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, size: 24, ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, size: 24, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: MONO, size: 20 }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, font: FONT, size: 24, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size: 24, ...base }));
  return out;
}
const body = [];
const P = (t, o = {}) => body.push(new Paragraph({ alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { after: 120, line: 360 }, children: runs(t, o.run || {}) }));
const H1 = t => body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true,
  spacing: { before: 240, after: 200 }, children: [new TextRun({ text: t, font: FONT, size: 32, bold: true })] }));
const H2 = t => body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 },
  keepNext: true, children: [new TextRun({ text: t, font: FONT, size: 26, bold: true })] }));
const H3 = t => body.push(new Paragraph({ spacing: { before: 200, after: 80 }, keepNext: true,
  children: [new TextRun({ text: t, font: FONT, size: 24, bold: true, italics: true })] }));
let listN = 0;   // each numbered list restarts at 1
const B = (items, ref = "bullets", instance = 0) => items.forEach(t => body.push(new Paragraph({
  numbering: { reference: ref, level: 0, instance },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 360 }, children: runs(t) })));
const N = items => B(items, "numbers", ++listN);
const CODE = lines => lines.forEach((l, i) => body.push(new Paragraph({ spacing: { after: i === lines.length - 1 ? 160 : 0 },
  shading: { type: ShadingType.CLEAR, color: "auto", fill: "EEF0F3" }, indent: { left: 240 },
  children: [new TextRun({ text: l, font: MONO, size: 20 })] })));

function cell(text, width, header) {
  return new TableCell({ width: { size: width, type: WidthType.DXA }, borders,
    shading: header ? { type: ShadingType.CLEAR, color: "auto", fill: "EAEDF1" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ spacing: { after: 0, line: 276 }, children: runs(text, { size: 21, bold: header || undefined }) })] });
}
function table(head, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const w = widths.map(x => Math.round(x * W / total));
  body.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: w,
    rows: [new TableRow({ tableHeader: true, children: head.map((h, i) => cell(h, w[i], true)) }),
           ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, w[i])) }))] }));
  body.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
}
function pngSize(f) {
  const b = fs.readFileSync(f);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
let figN = 0;
function figure(file, caption, widthPx = 600) {
  const f = path.join(FIG, file);
  const { w, h } = pngSize(f);
  let wp = widthPx, hp = Math.round(widthPx * h / w);
  if (hp > 760) { hp = 760; wp = Math.round(760 * w / h); }
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
    children: [new ImageRun({ type: "png", data: fs.readFileSync(f), transformation: { width: wp, height: hp },
      altText: { title: caption, description: caption, name: file } })] }));
  figN += 1;
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: `Fig. ${figN}. `, bold: true, font: FONT, size: 20 }), ...runs(caption, { size: 20 })] }));
}
// one demo step: what to do, what to show, what to say
function step(n, title, doIt, show, say) {
  H2(`Step ${n}. ${title}`);
  H3("Do");
  N(doIt);
  H3("Show");
  B(show);
  H3("Say");
  P(`_“${say}”_`);
}

// ============================================================ title page
const tp = (t, size, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 160 },
  children: [new TextRun({ text: t, font: FONT, size, bold: o.bold, italics: o.italics })] });
const title = [
  new Paragraph({ spacing: { before: 2400 }, children: [] }),
  tp("Beretta", 40, { bold: true }),
  tp("Explainable Cyber Insurance for Indian SMEs", 28),
  tp("Presenter's Guide for the Faculty Demonstration", 28, { bold: true, after: 600 }),
  tp("Setup, the demonstration step by step, and what every screen means", 24, { italics: true, after: 1200 }),
  tp("Final-year capstone project", 24),
  tp("Mukesh Patel School of Technology Management & Engineering, NMIMS Mumbai", 24),
  tp("Harsh Rathod (K080) · Yugandhara Raj Goud (K023) · Krish Mundhra (K041)", 24),
  tp("Supervisor: Prof. Rohit Suryawanshi", 24, { after: 600 }),
  tp("Pricing model UNDERWRITING_MODEL_V2 · Agent policy 2.1.0 · October 2026", 22),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Contents", font: FONT, size: 32, bold: true })] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
];

// ============================================================ 1. What you are showing
H1("1. What you are showing");
P("Beretta prices cyber insurance for Indian SMEs and keeps checking the insured's security after the policy is bound. It has two parts that talk to each other:");
B(["**Part 1, the Beretta platform** (http://127.0.0.1:8000). It collects evidence about the company, prices the policy with an explainable model, binds it, and runs the warranty state machine after bind.",
   "**Part 2, live monitoring** (http://127.0.0.1:8443). A read-only agent on each of the company's computers checks twelve security settings and sends signed reports to a collector. The collector rolls the machines up into one result per control and sends that to the platform."]);
P("The one rule to repeat during the demonstration: **monitoring never re-prices a bound policy.** After bind, what the agents see can only change the state of a warranty (Met, In grace, Breached, Remediated). The premium stays as it was bound.");
P("The demonstration follows one company, **Kalinga Components Ltd**, a manufacturer (NIC 28) with four endpoints. All four endpoints are **SIMULATED** and every screen says so. The story takes about fifteen minutes:");
N(["what the applicant fills in;", "the company's evidence, including live monitoring;", "the premium, and why it is that number;",
   "binding the policy;", "a security control failing after bind;", "the grace period running out;", "the fix;", "proof that the premium never changed."]);

// ============================================================ 2. Before
H1("2. Before the presentation");
H2("2.1 The day before");
N(["Turn off the broken Windows Python alias so that `python` works: **Settings → Apps → Advanced app settings → App execution aliases**, switch off **python.exe** and **python3.exe**. Otherwise type `py` wherever this guide says `python`.",
   "Run the three test suites once from `C:\\Suite\\kyh-cyber-insurance-linked`. All must pass (62+ / 158 / 1 tests):"]);
CODE(["python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance",
      "python kyh-agent/run_tests.py",
      "python integration/test_linked_system.py"]);
H2("2.2 Ten minutes before");
N(["Close any terminal that is still running an old demo. Two copies cannot run at once: the second cannot reset the demo data while the first holds it.",
   "Open PowerShell in `C:\\Suite\\kyh-cyber-insurance-linked` and start the demo. It recreates all demo data on every start, so you always begin clean:"]);
CODE(["python run_linked_demo.py"]);
N(["Leave this terminal open. It prints the platform and collector addresses and the **collector admin token**, then waits at a `kyh>` prompt. You type demo commands there later.",
   "Open two browser tabs: **http://127.0.0.1:8000** (platform) and **http://127.0.0.1:8443** (collector). On the collector, paste the admin token from the terminal and choose **Open dashboard**.",
   "If either tab was open from an earlier run, press **F5** once. An old tab keeps the previous run's login and shows “Unknown token”.",
   "Set the browser zoom so the page fits the projector (100% at 1366×768 or 1920×1080)."]);
H2("2.3 The commands you will type at the kyh> prompt");
table(["Command", "What it does", "When"], [
  ["`break KAL-PLANT-WS03 edr_down`", "That one simulated machine starts reporting that its anti-malware/EDR is not running.", "Step 6"],
  ["`fast-forward`", "Ends every running grace period now (a demonstration shortcut; it is recorded in the audit log as DEMO_TIME_TRAVEL).", "Step 7"],
  ["`fix KAL-PLANT-WS03`", "The machine reports healthy again.", "Step 8"],
  ["`status`", "Prints the warranty states in the terminal.", "Any time"],
  ["`hosts`", "Lists the endpoints with their liveness and failing checks.", "Any time"],
  ["`bind`", "Quotes and binds from the terminal (same as the button). Use the button in the demo instead.", "Backup only"],
  ["`quit`", "Stops the demo.", "The end"],
], [3, 6, 1.4]);

// ============================================================ 3. Demonstration
H1("3. The demonstration, step by step");
P("Each step says what to do, what to point at, and one or two sentences to say. The figures show what the screen should look like.");

step(1, "What the applicant fills in", [
  "On the platform tab, choose **Questionnaires** in the sidebar."],
  ["The full proposal form (CYBERUW-IQ-1.0) and the new **Rating Addendum** (CYBERUW-IQ-1.1). The addendum asks the NIC 2008 code, RBI/SEBI regulation, material incidents, a yes / no / don't know for each priced control, payment verification and the misrepresentation declaration.",
   "**How evidence changes the price**: the four evidence strengths. A “yes” in a questionnaire is _stated_ and earns 60% of a control's effect; evidence from the agent, a test or an independent report is _verified_ and earns all of it."],
  "Before a quote, the applicant fills in the proposal form. The price depends on how strong the evidence is: saying you have MFA is worth less than proving it.");
figure("guide_01_questionnaires.png", "Questionnaires: the proposal form, the V2 rating addendum and the evidence key.");

step(2, "The portfolio", ["Choose **Portfolio**."],
  ["The line under the title: nothing is bound yet.", "The two strips of figures: the book (companies, bound policies, pending, calculations) and the warranties (breached, in grace, average posture).", "Three companies, all Draft."],
  "This is the underwriter's view of the book. We will take Kalinga Components from draft to a bound policy.");
figure("guide_02_portfolio.png", "Portfolio: the book, the warranties and every policy.");

step(3, "The company and its evidence", ["Choose **Companies → Kalinga Components Ltd**. You land on the **Intake** tab."],
  ["**Classification**: NIC 28 rates as Industrials; turnover ₹60 crore; 18 years in operation. This is all the model rates the company on; employees are kept but not priced.",
   "**Endpoint monitoring**: Linked via the Beretta collector, 4 of 4 endpoints reporting. Fleet results enter as _Technically observed_ evidence, the strongest kind.",
   "**Policy structure** (scroll): an overall limit of ₹2 crore and a ₹1 lakh retention. There are no per-cover sub-limits: each claim pays its loss above the retention, across all covers including the new Funds Transfer Fraud cover, up to the overall limit.",
   "**Security questionnaire**: each control shows its resolved value and an evidence chip whose bars show its strength. Click a chip to show the source trail."],
  "Every value here has a source. Where several sources disagree, the strongest evidence wins, and you can always see where a value came from.");
figure("guide_03_intake_top.png", "Intake: classification and endpoint monitoring.");
figure("guide_04_policy_structure.png", "Policy structure: the overall limit and the retention per claim.");
figure("guide_05_questionnaire.png", "Security questionnaire: each control with its resolved value and evidence strength.");

step(4, "Live monitoring feeds the evidence", ["Switch to the collector tab and open **Kalinga Components Ltd**."],
  ["The four endpoints, each labelled **SIMULATED**, all online.", "**Link to the Beretta platform**: the last push and what was sent for each platform control.", "The note that warranty states are held by the Beretta platform: the collector only displays them."],
  "The agent is read-only. It checks settings such as patching, anti-malware and backups, signs its reports, and the collector sends one signed roll-up per company to the platform.");
figure("guide_06_collector_prebind.png", "Collector, before bind: the company, its endpoints and the link to the platform.");

step(5, "The premium", [
  "Back on the platform tab, open the **Quote and calculation** tab and choose **Calculate premium**.",
  "Scroll down slowly, section by section."],
  ["**Premium**: about ₹94,135 technical premium; with 18% GST, ₹1,11,079 payable. **Conditionally eligible**: backups are recent but no restore test is evidenced. **No referral**.",
   "**Classification**: turnover USD 6.8M and how turnover and sector scale frequency and severity.",
   "**Perils**: five rows. For each, frequency × expected payout = expected loss; the total is ₹47,067.",
   "**Controls and evidence**: EDR, patching, PAM, secure configuration and logging are Verified by the agent; email security is Not working because an outside-in scan found no DMARC record.",
   "**What verification would save**: the saving for verifying each control.",
   "**Claims history**: one material incident gives ×1.23.",
   "**From expected loss to premium**: the 50 / 30 / 20 split, then GST.",
   "Open **assumptions used in this quote** to show that every assumption is listed with its range."],
  "Every rupee is explained: which perils it comes from, which controls raised or lowered it and on what evidence, and what the company could do to pay less.");
figure("guide_07_quote_top.png", "The premium, eligibility and referral, with the one-paragraph explanation.");
figure("guide_08_classification_perils.png", "Classification and the five perils: frequency × expected payout = expected loss.");
figure("guide_09_controls.png", "Controls and evidence: status, best evidence and effect of each priced control.");
figure("guide_10_whatif_claims.png", "What verification would save, and the claims-history multiplier.");
figure("guide_11_premium_build.png", "From expected loss to premium: target loss ratio, expense and margin split, GST.");

step(6, "Bind, then a control fails", [
  "On the quote, choose **Bind policy at ₹94,135**. The page opens the **Monitoring after bind** tab: five warranties, all Met.",
  "In the terminal, type `break KAL-PLANT-WS03 edr_down`.",
  "Wait about 10 seconds and refresh the Monitoring tab (F5)."],
  ["EDR is now **In grace**, with the date the grace ends and what happens if it is not fixed.",
   "The premium figure: unchanged, “Fixed at inception”.",
   "**Endpoints** (scroll): EDR 3 of 4 hosts passing, and KAL-PLANT-WS03 failing in the host matrix.",
   "On the collector tab: the same In grace state, read back from the platform, and the host page explaining the failure."],
  "One machine stopped its anti-malware. The platform did not re-price the policy; it moved the EDR warranty into a grace period. The insured now has seven days to fix it.");
figure("guide_13_monitoring_grace.png", "Monitoring after bind: EDR in grace, the premium unchanged.");
figure("guide_14_fleet.png", "Endpoints: what the fleet sent, and the host matrix showing the failing machine.");
figure("guide_16_collector_company.png", "Collector: the platform's warranty states, read back after each push.");
figure("guide_17_collector_host.png", "Collector host page: every check, its evidence and the signed report history.");

step(7, "The grace period runs out", ["Type `fast-forward` in the terminal, then refresh the Monitoring tab."],
  ["EDR is now **Breached**, and its coverage consequence applies.", "The premium is still unchanged."],
  "Grace periods are whole days, so for the demonstration we end them early. This is recorded in the audit log. A breach changes what a claim may pay; it does not change what the policy costs.");
figure("guide_18_breached.png", "After fast-forward: EDR breached.");

step(8, "The fix", ["Type `fix KAL-PLANT-WS03`, wait about 10 seconds and refresh."],
  ["EDR goes **Remediated**, then **Met**.", "**Warranty timeline**: Met → In grace → Breached → Remediated → Met, each with its time and the observation that caused it."],
  "Once the machine reports healthy again, the warranty is restored. The whole history is kept.");
figure("guide_19_timeline.png", "Warranty timeline: the full path of the EDR warranty.");

step(9, "Proof that monitoring never re-priced the policy", ["Open the **Quote and calculation** tab again."],
  ["The **Calculate premium** button is gone, and the bound calculation is marked Bound. The engine refuses to price a bound policy (error POLICY_ALREADY_BOUND).", "Optionally open **Audit log**: every observation, calculation, bind and warranty change is recorded."],
  "This is the central rule of the design: monitoring changes warranty states, never the premium.");

step(10, "If they ask how the model works", ["Switch **Acting as** (bottom of the sidebar) to **Administrator** and open **Model configuration**."],
  ["**Priced controls**: each control's relative risk S, adoption p, and its multiplier when verified, stated or lacking, with the source.", "**All V2 parameters with provenance**: every number, its source and its tag ([L] published, [D] derived, [A] assumption)."],
  "Every number in the model has a published source or is marked as an assumption with a range. The full specification is in docs/premium_model_v2.md.");
figure("guide_12_admin.png", "Model configuration: the priced controls and their multipliers.");
P("To finish, type `quit` in the terminal.");

// ============================================================ 4. What every screen means
H1("4. What every screen means");
H2("4.1 Everywhere on the platform");
table(["Element", "Meaning"], [
  ["Sidebar", "Questionnaires, Portfolio and Companies are the underwriting work; Audit log and Regulatory context are records; Model configuration is settings."],
  ["Acting as", "The role the screens act as: Underwriter (prices and binds), Insured customer (read-only), Administrator (model configuration). Some screens and buttons depend on it."],
  ["Status pills", "Small coloured labels. Green means good (Met, Pass, Verified, Bound); amber means watch (In grace, Partial, Conditionally eligible); red means bad (Breached, Fail, Not working, Ineligible); blue means Stated or Remediated; grey means unknown or no data."],
  ["Evidence chip", "A small box with four bars. The number of filled bars is the evidence strength: 1 Declared, 2 Documented, 3 Tested, 4 Technically observed. Next to it is where the evidence came from (QUESTIONNAIRE, DOCUMENT, AGENT_FLEET, OUTSIDE_IN_SCAN …). Click it for the source trail."],
  ["SIMULATED", "Data from a simulated endpoint. It is always shown and never hidden."],
], [2, 7]);

H2("4.2 Questionnaires");
table(["Element", "Meaning"], [
  ["Proposal form (Full)", "CYBERUW-IQ-1.0, the 19-page pre-application questionnaire, sections A to Q."],
  ["Rating Addendum", "CYBERUW-IQ-1.1, the three-page addendum with the facts pricing V2 rates on that the 1.0 form does not ask."],
  ["Short form and supplements", "A shorter screening form and stand-alone security-controls and India-regulatory sections."],
  ["How evidence changes the price", "Declared (a questionnaire yes) is priced as stated, 60% of the control's effect. Documented is verified if the report is independent (SOC 2 Type II, ISO 27001 SoA, VAPT, scanner export, identity-provider MFA export), otherwise stated. Tested and Technically observed are verified, the full effect."],
], [2.2, 7]);

H2("4.3 Portfolio");
table(["Element", "Meaning"], [
  ["Line under the title", "The one thing to know: how many warranties are breached or in grace across the bound policies."],
  ["Companies / Bound policies / Pending underwriting / Premium calculations", "How many companies are on the book, how many policies are bound, how many are draft or quoted, and how many premium calculations have been made."],
  ["Warranties breached / in grace", "Across all bound policies. Red or amber when not zero."],
  ["Average posture", "The share of controls whose resolved value is Pass, averaged across companies. It is an overview figure; it is not used in pricing."],
  ["Policies table", "Each policy with its status and bound premium; the total bound premium at the bottom. Click a row to open the company."],
  ["Recent audit events", "The latest recorded actions (observations, calculations, binds, warranty changes)."],
], [2.6, 7]);

H2("4.4 Company: Intake tab");
table(["Element", "Meaning"], [
  ["Classification", "NIC 2008 code (its first two digits set the rating sector), annual turnover, years in operation and the RBI/SEBI flag: the inputs the model rates on. Locked once the policy is bound."],
  ["Endpoint monitoring", "Whether a live-monitoring collector is linked, how many declared endpoints report, and the latest fleet roll-up. The legacy single-host agent is the older Part 1 agent and is not used in the demo."],
  ["Policy structure", "The overall limit (the most the policy pays for one claim) and the retention per claim (the part the insured pays first). There are no per-cover sub-limits."],
  ["Security questionnaire", "Every control: its tier, the resolved value (best evidence wins), the evidence chip, and a box to record the customer's answer (yes, no, partially, or no change / don't know). “Not priced” marks controls kept for warranties and underwriting only."],
  ["Documents and evidence", "Register a document by type, then record what it shows for a control with a locator (page or question). Independent documents verify a control; self-assessments state it."],
  ["Claims history", "Past incidents. Only material incidents in the last 3 years count: a loss above the retention, a DPDP or CERT-In notification, or a ransom decision."],
  ["Outside-in scan signals", "Findings from an external scan (imported, not scanned by Beretta). Each one is evidence for a control, for example exposed RDP means secure configuration is not working."],
], [2.2, 7]);

H2("4.5 Company: Quote and calculation tab");
table(["Element", "Meaning"], [
  ["Technical premium", "Expected loss ÷ the 50% target loss ratio. This is the premium that is bound."],
  ["GST / payable", "18% GST on top; payable is what the customer pays."],
  ["Eligibility", "Eligible: every warranty (MFA, tested backups, EDR, critical patching) is verified (MFA may be stated). Conditionally eligible: a warranty is only stated; evidence is expected before bind. Ineligible: a warranty is not working or unknown and the gate mode is Block, so binding is blocked. Gating never changes the price."],
  ["Referral", "The price stands, but an underwriter must tick an approval to bind. Triggers: turnover above USD 2B, a control multiplier at the 3.0 ceiling, two or more material incidents, or an RBI/SEBI-regulated entity."],
  ["Explanation", "The quote in one paragraph."],
  ["Classification strip", "The rating sector, turnover in USD at the configured rate, and the four relativities: turnover and sector, each for frequency and severity (×1.000 is average)."],
  ["Perils table", "Base frequency (the global rate for that peril) × turnover × sector × controls × claims = frequency per year. Mean loss is the average loss size; expected payout is what the policy would pay per incident after the retention and limits; expected loss = frequency × expected payout. At ceiling means the controls multiplier hit 3.0."],
  ["Controls and evidence", "Each priced control: its evidence status (Verified, Stated, Not working, Unknown), its best evidence, the attack stage it defends (credential, weakness, execution), and its frequency and severity multipliers (below ×1 lowers the premium)."],
  ["What verification would save", "The premium if that one control were verified, and the saving. Sorted largest first."],
  ["Claims history", "Material incidents N, years used T, expected incidents a year before history, and the multiplier (α + N) / (α + λT) with α = 4.22."],
  ["From expected loss to premium", "The bar and table split the technical premium into 50% expected loss, 30% expenses (the IRDAI cap, commission included) and 20% profit, risk margin, reinsurance and accumulation; then GST."],
  ["Assumptions", "Every [A] parameter the quote used, with its value and sensitivity range."],
  ["Calculation history", "Every past calculation with its model version (V1 quotes from before V2 still open in their own view)."],
], [2.2, 7]);

H2("4.6 Company: Monitoring after bind tab");
table(["Element", "Meaning"], [
  ["Figures strip", "How many warranties are met, in grace and breached, and the premium fixed at inception."],
  ["Black banner", "The central rule: security changes after bind move warranty states and their consequences, never the premium."],
  ["Warranty cards", "For each warranty: its state and what it means, when it was last observed, the grace period, when a lapse was detected and when grace ends, and what happens if it is breached (an illustrative coverage consequence)."],
  ["Endpoints", "From which collector and roll-up the data came. The figures: endpoints declared, reporting, online, unverified (quiet 6 to 72 hours) and silent (quiet over 72 hours)."],
  ["What the fleet sent", "For each platform control: the fleet's result, the collector checks it was built from, how many hosts pass, the warranty state, and why. “Not sent” means no host could observe it, so the platform keeps its own evidence."],
  ["Hosts matrix", "Every endpoint (each SIMULATED in the demo), its liveness and last-seen time, and each check's result. N/sup means not supported on that platform; N/a means not applicable."],
  ["Warranty timeline", "Every state change with its time, the note, and the observation that caused it."],
], [2.2, 7]);

H2("4.7 The collector (Part 2)");
table(["Element", "Meaning"], [
  ["Insured companies", "One card per company: policy status, SIMULATED and Linked labels, bound premium, endpoints reporting and the warranty chips."],
  ["Company page: premium panel", "The bound premium and the rule that monitoring never re-prices; for a linked company, the Beretta platform is the warranty authority."],
  ["Figures", "Declared endpoints, enrolled agents, reporting, online, unverified, silent."],
  ["Warranties", "For a linked company, the platform's warranty states read back after each push; the collector does not run its own state machine for it."],
  ["Link to the Beretta platform", "The last push (OK or failed), and what was sent for each platform control, built from which collector checks."],
  ["Controls across the fleet", "Each collector check (backup, EDR, MFA, patch, log retention …) with the share of hosts passing; it fails when fewer than 95% pass."],
  ["Endpoints", "The host matrix; click a host for its page."],
  ["Host page", "Last seen, last full snapshot, reports waiting, whether its build and policy are approved, the latest result per check with its evidence (expand Evidence), and the signed report history with each report's SHA-256."],
], [2.2, 7]);

H2("4.8 Model configuration, Audit log, Regulatory context");
table(["Element", "Meaning"], [
  ["Gate mode", "Block (default): a failed or unknown warranty makes the risk ineligible. Warn: conditionally eligible with an underwriter override."],
  ["Warranty grace periods", "How many days the insured has to fix a lapsed warranty before it is breached."],
  ["Priced controls", "Relative risk S (how much more often firms without the control have incidents), adoption p, and the multipliers when verified, stated or lacking, centred so the average firm is ×1."],
  ["All V2 parameters", "Every number in the model with its unit, tag and source. Read-only: values change only in the parameter file, so their provenance is kept."],
  ["Audit log", "Every recorded action; filter by event type, entity or actor."],
  ["Regulatory context", "The Indian rules the design follows: DPDP Act 2023, CERT-In Directions 2022, RBI and SEBI cyber frameworks, IRDAI guidelines."],
], [2.2, 7]);

// ============================================================ 5. Glossary
H1("5. Glossary of states and labels");
H2("5.1 Evidence");
table(["Label", "Meaning"], [
  ["Declared", "The company says so (questionnaire, self-written policy). One bar."],
  ["Documented", "A document backs it up. Two bars."],
  ["Tested", "A test shows it works (restore test, tabletop, pentest). Three bars."],
  ["Technically observed", "The agent, the fleet or an outside-in scan saw it. Four bars."],
  ["Verified", "Pricing status: full effect of the control (technically observed, tested, or an independent document)."],
  ["Stated", "Pricing status: 60% of the effect (declared, a self-assessment, or a partial result such as backups recent but restore untested)."],
  ["Not working", "Pricing status: evidence says the control fails (agent or scan FAIL, or a questionnaire no). Priced as lacking."],
  ["Unknown", "Pricing status: no evidence (don't know). Priced as lacking."],
], [2, 7]);
H2("5.2 Warranties, eligibility, endpoints");
table(["Label", "Meaning"], [
  ["Met", "The control is in place; cover applies as written."],
  ["In grace", "The control has lapsed; the insured has until the grace period ends to fix it."],
  ["Breached", "The grace period ended without a fix; the coverage consequence applies."],
  ["Remediated", "The control was restored after a lapse; the warranty returns to Met."],
  ["Eligible / Conditionally eligible / Ineligible", "Whether the risk can be bound (see 4.5)."],
  ["Draft / Quoted / Bound", "Policy status: no quote yet / at least one quote / bound."],
  ["Online / Unverified / Silent", "An endpoint reported recently / has been quiet 6 to 72 hours / has been quiet more than 72 hours."],
  ["Pass / Fail / Partial", "A check or control result. Partial: the control is there but not fully evidenced."],
  ["Not observable / Not supported / Not applicable / No data", "The check cannot be measured on that host, or does not apply, or nothing was reported."],
], [2.4, 7]);

// ============================================================ 6. Questions
H1("6. Likely questions");
table(["Question", "Short answer"], [
  ["Where do the numbers come from?", "Published claims data: Coalition 2025 for frequencies and severities, Marsh McLennan 2023 for control effects, Sophos and IBM for severity effects, NetDiligence and IRIS for the loss shape. Every value is tagged in the parameter file; assumptions carry a range."],
  ["Is this priced for India?", "Not yet. The data is mostly from the US; India adjustment factors exist in the model but are set to 1 until Indian claims data is available. This is listed as a limitation."],
  ["Why does verified evidence cost less than a questionnaire yes?", "Some declared controls are not really working. Assuming 20% of declarations are hollow, a declaration is worth about 60% of a verified control."],
  ["Why didn't the premium change when EDR failed?", "By design. The premium is fixed at bind; monitoring only changes warranty states, which affect what a claim may pay. Re-pricing mid-term would punish the insured for being monitored."],
  ["What does the agent collect?", "Only security settings (patch age, anti-malware state, backup age, firewall, encryption …). It is read-only and never collects files, browsing, keystrokes, e-mail, passwords or clear-text user names."],
  ["How do you stop fake reports?", "Each report is signed with the agent's secret, carries a sequence number that cannot repeat, and comes from an approved build and policy. The collector's roll-up to the platform is signed too."],
  ["Is the data real?", "The four endpoints are simulated and labelled SIMULATED everywhere. A real Windows VM can be added (see the VM setup guide)."],
  ["What is not modelled?", "Accumulation (one event hitting many insureds), peril-specific sector effects, and several placeholder shares and adoption rates, all listed in docs/premium_model_v2.md."],
], [3, 6]);

// ============================================================ 7. Troubleshooting
H1("7. If something goes wrong");
table(["What you see", "What to do"], [
  ["“Could not load this view” or “Unknown token”", "Press F5. The tab is from an earlier run."],
  ["`python` fails with “cannot be accessed by the system”", "Use `py` instead, or turn off the Python app execution aliases (section 2.1)."],
  ["The demo will not start (address in use, or “file already exists”)", "Another demo is still running. Close its terminal, then start again."],
  ["Nothing changes after a break or fix", "Wait 10 to 15 seconds, then refresh. The agents report every few seconds."],
  ["The collector asks for a token", "Paste the admin token printed in the terminal."],
  ["You want to start over", "Type `quit` and run `python run_linked_demo.py` again. All demo data is recreated."],
], [3.2, 6]);

// ============================================================ document
const doc = new Document({
  creator: "Beretta capstone team", title: "Beretta: Presenter's Guide for the Faculty Demonstration",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 32, bold: true }, paragraph: { spacing: { before: 240, after: 200 } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true }, paragraph: { spacing: { before: 280, after: 120 } } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })] })] }) },
    children: [...title, ...body],
  }],
});
const out = path.join(__dirname, "Beretta_Demo_Presenter_Guide.docx");
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(out, buf); console.log("wrote", out, "figures:", figN); });
