// Builds docs/Beretta_Part1_Part2_Link.docx  (node build_link_doc.js)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, AlignmentType, HeadingLevel,
  WidthType, ShadingType, BorderStyle, Footer, PageNumber, LevelFormat, PageBreak, TableOfContents,
} = require("docx");

const FIG = path.join(__dirname, "figures");
const FONT = "Times New Roman";
const MONO = "Courier New";
const W = 9026; // A4 text width in DXA with 1" margins

// ---------------------------------------------------------------- inline markup: **bold**, `code`, _italic_
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|~[^~]+~)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: MONO, size: (base.size || 24) - 3 }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, font: FONT, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out;
}

const body = [];
let figN = 0, tabN = 0;
const P = (t, o = {}) => body.push(new Paragraph({ children: runs(t), alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 120, line: 360 }, ...o }));
const toc = [];
const H1 = (t) => { toc.push([1, t]); body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t })],
  pageBreakBefore: true })); };
const H2 = (t) => { toc.push([2, t]); body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t })] })); };
const H3 = (t) => body.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: t })] }));
const B = (items, ref = "bullets") => items.forEach((t) => body.push(new Paragraph({ numbering: { reference: ref, level: 0 },
  children: runs(t), alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 320 } })));
const N = (items) => B(items, "numbers-" + (++numCount));
let numCount = 0;

function code(lines) {
  lines.forEach((l, i) => body.push(new Paragraph({
    children: [new TextRun({ text: l === "" ? " " : l, font: MONO, size: 15 })],
    shading: { type: ShadingType.CLEAR, color: "auto", fill: "F1F2F5" },
    spacing: { before: i === 0 ? 80 : 0, after: i === lines.length - 1 ? 160 : 0, line: 240 },
    keepNext: i < lines.length - 1, keepLines: true,
    indent: { left: 144, right: 144 },
  })));
}

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

function figure(file, caption, widthPx = 600) {
  const f = path.join(FIG, file);
  const { w, h } = pngSize(f);
  let wp = widthPx, hp = Math.round(widthPx * h / w);
  if (hp > 820) { hp = 820; wp = Math.round(820 * w / h); }
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
    children: [new ImageRun({ type: "png", data: fs.readFileSync(f), transformation: { width: wp, height: hp },
      altText: { title: caption, description: caption, name: file } })] }));
  figN += 1;
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: `Fig. ${figN}. `, bold: true, font: FONT, size: 20 }), ...runs(caption, { size: 20 })] }));
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "9AA1AD" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(caption, headers, rows, widths) {
  tabN += 1;
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160, after: 80 }, keepNext: true,
    children: [new TextRun({ text: `Table ${tabN}. `, bold: true, font: FONT, size: 20 }), ...runs(caption, { size: 20 })] }));
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, i, head) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: "E4E7EC" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: String(t).split("\n").map((line) => new Paragraph({ spacing: { after: 0, line: 252 },
      children: runs(line, { size: 19, bold: head || undefined }) })),
  });
  body.push(new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, i, false)) }))],
  }));
  body.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
}

// ================================================================= TITLE PAGE
const tp = (t, size, o = {}) => body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
  children: [new TextRun({ text: t, font: FONT, size, ...o })] }));
body.push(new Paragraph({ spacing: { before: 1800 }, children: [] }));
tp("Beretta", 28, { bold: true });
tp("Linking Part 1 and Part 2", 40, { bold: true });
tp("How the live-monitoring collector feeds the underwriting platform, and what changed in each", 26, { italics: true });
body.push(new Paragraph({ spacing: { before: 900 }, children: [] }));
tp("Final-year capstone project, B.Tech / MBA Tech", 24);
tp("Mukesh Patel School of Technology Management & Engineering, NMIMS Mumbai", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Harsh (K080)  ·  Yugandhara Raj Goud (K023)  ·  Krish Mundhra (K041)", 24);
tp("Supervisor: Prof. Rohit Suryawanshi", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Beretta platform UNDERWRITING_MODEL_V1  ·  Collector 2.0.0 (linked mode)  ·  26 October 2026", 22);
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Contents", bold: true, font: FONT, size: 28 })] }));
const tocIndex = body.length;

// ================================================================= 1
H1("1. What changed");
P("Part 1, the Beretta platform, prices a policy once at inception and then runs the warranty state machine. Part 2 is the live-monitoring agent and its collector. Before this change, each had its own warranty state machine. With both running, the same company could show its EDR warranty as MET on one dashboard and IN_GRACE on the other.");
P("The two are now linked so that each part does one job. The **collector** owns everything about endpoints: the agent's identity, signed reports, replay protection, the silence rule and the fleet roll-up. The **platform** owns everything about the policy: evidence resolution, pricing, binding, and the only warranty state machine. The collector sends the platform one signed result per control for each company, and the platform treats it as evidence like any other.");
table("Before and after", ["", "Before", "After"], [
  ["Warranty state machines", "Two (platform and collector)", "One (platform)"],
  ["How endpoint data reaches the platform", "Old single-host agent, one bearer token per company", "Collector fleet roll-up, HMAC-signed, numbered, linked per company"],
  ["Evidence label in the platform", "AGENT", "AGENT_FLEET, TECHNICALLY_OBSERVED"],
  ["Effect before bind", "Agent results fed the quote", "Fleet results feed the quote"],
  ["Effect after bind", "Warranties only", "Warranties only (unchanged rule)"],
  ["Agent kept reporting?", "Not enforced", "New monitoring-only warranty: at least 90% of declared endpoints reporting"],
  ["Premiums", "Fixed at bind", "Fixed at bind; the 15 priced controls and every formula are unchanged"],
], [2600, 3000, 3426]);
P("The pricing logic of Part 1 was not changed. Three tests check this (Section 8).");

// ================================================================= 2
H1("2. How the parts fit together");
figure("link_fig1_architecture.png", "Agents report to the collector. The collector sends a signed roll-up to the platform, which records it as evidence and runs the only warranty state machine. Warranty states are read back for display.");
table("Who owns what", ["Collector (Part 2)", "Beretta platform (Part 1)"], [
  ["Agent enrollment and per-host secrets", "Companies, policies, questionnaires, documents, claims"],
  ["Signature, sequence and timestamp checks on every agent report", "Evidence resolution (Engine A): strongest evidence wins"],
  ["Per-host results and their raw evidence", "Pricing (Engine B), once, at inception"],
  ["Liveness: ONLINE, UNVERIFIED after 6 h, SILENT after 72 h", "Binding"],
  ["Fleet roll-up: at least 95% of observed hosts must pass", "The warranty state machine and coverage consequences"],
  ["Monitoring coverage: hosts reporting vs declared", "Audit trail of every decision"],
], [4513, 4513]);
P("Both dashboards link to each other. On the platform, the Monitoring tab of a linked company shows the fleet, and each host name opens the collector's page for that host. On the collector, a banner names the platform as the warranty authority and links to the company's Monitoring tab.");

// ================================================================= 3
H1("3. One roll-up, from start to finish");
figure("link_fig2_sequence.png", "What happens when EDR stops on one of four machines after bind.");
N([
  "The agent on KAL-PLANT-WS03 sends a signed report: EDR is FAIL.",
  "The collector checks the report exactly as before (size, identity, signature, schema, sequence, timestamp) and stores it.",
  "Because the company is linked, the collector wakes its **link worker**. The worker also runs on its own every 30 seconds, which is how a machine that stops reporting turns SILENT without any new report.",
  "The worker evaluates the fleet: 3 of 4 hosts pass EDR, below the 95% threshold, so EDR is FAIL for the company.",
  "It maps EDR to the platform control CTRL-EDR, builds the payload, increases the sequence number and signs the exact bytes with HMAC-SHA256.",
  "It sends the payload to `POST /api/collector/rollup`. The HTTP call is made outside the collector's database lock, so a slow platform never blocks incoming agent reports.",
  "The platform verifies it (Section 5), records CTRL-EDR = false as an AGENT_FLEET observation, and calls its existing `coverage.evaluate_policy`.",
  "It answers with the policy status, every warranty state and `repricing_performed: false`.",
  "The collector stores the answer and shows those states. It never computes warranty states itself for a linked company.",
]);
P("A roll-up is sent when something meaningful changes (a control result, a host's liveness, or a host's result for any check) and otherwise as a heartbeat every 15 minutes. If the platform cannot be reached, the error is shown on the collector's link panel and the next cycle tries again with a fresh roll-up and a new sequence number. Old roll-ups are never replayed.");
P("A shortened roll-up:");
code([
  "{ \"schema\": \"kyh-fleet-rollup/1\", \"collector_id\": \"COL-80dfce4927\", \"seq\": 6,",
  "  \"sent_at\": \"2026-10-26T13:22:28Z\", \"evaluated_at\": \"2026-10-26T13:22:28Z\",",
  "  \"company\": { \"collector_company_id\": \"co_kalinga\", \"platform_company_id\": \"CO-7bc45931f9\" },",
  "  \"controls\": [",
  "    { \"platform_control_id\": \"CTRL-EDR\", \"status\": \"FAIL\", \"value\": \"false\",",
  "      \"passing\": 3, \"observed\": 4, \"failing_hosts\": [{ \"host\": \"KAL-PLANT-WS03\", ... }],",
  "      \"sources\": [{ \"control\": \"EDR\", \"status\": \"FAIL\" }] },",
  "    { \"platform_control_id\": \"CTRL-BACKUP-TESTED\", \"status\": \"PASS\", \"value\": \"partial\", ... } ],",
  "  \"unmapped\": [{ \"control\": \"MFA\", \"why\": \"NOT_OBSERVABLE\" }],",
  "  \"coverage\": { \"status\": \"PASS\", \"declared\": 4, \"reporting\": 4 },",
  "  \"fleet\": { \"hosts\": [ ... per-host liveness and results for the dashboard ... ] } }",
]);

// ================================================================= 4
H1("4. Mapping collector controls to platform controls");
P("The collector checks twelve things on each machine; the platform has fifteen priced controls. The mapping lives in one setting, `platform_control_map`, so it can be read and changed in one place.");
table("The mapping", ["Collector control", "Platform control", "Note"], [
  ["PATCH", "CTRL-PATCH-CRIT (warranty)", ""],
  ["EDR", "CTRL-EDR (warranty)", ""],
  ["BACKUP", "CTRL-BACKUP-TESTED (warranty)", "A pass is sent as **partial**"],
  ["MFA", "CTRL-MFA (warranty)", "Never sent: not observable from endpoints"],
  ["DISK_ENCRYPTION", "CTRL-ENCRYPTION", ""],
  ["FIREWALL, REMOTE_ACCESS, EXPOSED_SERVICES, ADMIN_ACCOUNTS, OS_SUPPORT", "CTRL-SECCONFIG", "Hardening baseline"],
  ["LOG_RETENTION, TIME_SYNC", "CTRL-LOGGING", "The two CERT-In checks"],
  ["MONITORING_COVERAGE", "CTRL-AGENT-COVERAGE (new, monitoring only)", "Section 6"],
], [3300, 3000, 2726]);
P("Four rules decide what is sent:");
B([
  "**Several sources, one control.** When more than one collector control feeds a platform control, the platform control fails if any source fails. It passes only if at least one source passed and none failed.",
  "**Nothing observed, nothing sent.** If no machine could observe a control (every host said NOT_SUPPORTED or NOT_APPLICABLE), nothing is sent for it. The platform keeps resolving that control from its questionnaire and document evidence, so an unobservable control is never turned into a fake PASS or FAIL. MFA is always in this position.",
  "**Backups are sent as partial.** The agent can see that a backup ran recently. It cannot see whether a restore was ever tested, and the platform control is called Tested backups. Sending \"partial\" is the honest answer: before bind it earns half the credit, and the quote marks the warranty as unverified. After bind, partial counts as passing, so a recent backup keeps the warranty MET.",
  "**Silence counts.** A host silent for more than 72 hours whose last result failed keeps failing; one whose last result passed is left out of the roll-up for up to 14 days, then fails (rule revised on 27 Oct 2026). Controls it could never observe are left alone.",
]);
P("The platform and the collector dashboards both show this mapping for the latest roll-up: which collector controls built each platform control, the hosts passing, and the reason (Fig. 6 and Fig. 8).");

// ================================================================= 5
H1("5. What the platform does with a roll-up");
H2("5.1 Checks before anything is stored");
table("Roll-up checks, in order", ["Check", "Rejected with"], [
  ["Collector registered", "401 UNKNOWN_COLLECTOR"],
  ["HMAC-SHA256 over the exact body matches the collector's secret", "401 BAD_SIGNATURE (audited)"],
  ["Schema is kyh-fleet-rollup/1 and the collector id matches the header", "400 / 403"],
  ["Sequence number higher than the last one accepted", "409 REPLAY (audited)"],
  ["sent_at within 5 minutes of platform time", "400 STALE_OR_FUTURE"],
  ["The company is linked to this collector", "403 NOT_LINKED"],
  ["Every control exists; status PASS/FAIL with value true, partial or false", "400"],
], [6000, 3026]);
P("An administrator registers a collector on the platform's Model configuration page. The platform creates a random 256-bit secret and shows it once, with the exact command to paste on the collector. The administrator then links a platform company to the collector's company id (Fig. 3). A collector can only send roll-ups for companies it is linked to.");
figure("p1_admin.png", "Platform, Model configuration: registering a collector and linking a company to it.", 560);
H2("5.2 Recording the evidence");
P("Each control result becomes an observation with source type **AGENT_FLEET** and evidence strength **TECHNICALLY_OBSERVED**, the top of the evidence ladder. The source locator names the roll-up, the collector controls behind it and the host count, for example \"Beretta collector roll-up #6 · EDR · 3/4 hosts pass\". The note lists the failing hosts. The raw roll-up is stored unchanged.");
P("To keep the observation history readable, a result is not recorded again if the value and host count are the same as the last AGENT_FLEET observation for that control and that observation is less than six hours old. Every roll-up still updates the fleet snapshot used by the dashboard.");
H2("5.3 Before bind: evidence for the quote");
P("Fleet results enter Engine A like any other evidence. Engine A picks the strongest evidence for each control, so a TECHNICALLY_OBSERVED fleet result outranks a DECLARED questionnaire answer. In the demo, the Kalinga Components questionnaire said secure configuration was not in place; the fleet shows all four machines passing, so the control is priced as met with the full observed credit. Engine B itself is untouched.");
figure("p1_quote_posture.png", "The platform's quote for Kalinga Components. Controls the fleet could observe show the full evidence ladder, Technically observed, from source AGENT_FLEET, with the roll-up and host count; the rest still come from the questionnaire.", 600);
H2("5.4 After bind: warranties only");
P("After bind, the platform passes the roll-up to its existing coverage engine and nothing else. In the demo, stopping EDR on one machine moved the EDR warranty to IN_GRACE within a few seconds. The bound premium of ₹1,28,977 did not change at any point.");
figure("p1_ingrace_cards.png", "Platform Monitoring tab after EDR stopped on KAL-PLANT-WS03. Only the EDR warranty moved.", 600);
figure("p1_prebind_fleet_crop.png", "The new Endpoints section of the Monitoring tab: fleet tiles, what the fleet sent, which collector controls built each result, and why.", 600);
figure("p1_timeline.png", "The platform's warranty timeline for the demo: MET, IN_GRACE, BREACHED (after the demo's fast-forward), REMEDIATED, MET.", 600);

// ================================================================= 6
H1("6. The monitoring-coverage warranty");
P("Part 2 added a warranty that the agent must keep reporting, because otherwise the easiest way to hide a failing machine is to uninstall the agent from it. The platform now has the same warranty as a sixteenth control, **CTRL-AGENT-COVERAGE** (Live monitoring coverage): at least 90% of the endpoints declared on the proposal form must be reporting, with a 14-day grace period.");
P("It is marked **monitoring only**, and that flag keeps it out of everything to do with price:");
B([
  "the posture modifier skips it, so the 15 priced controls and every premium are exactly as before;",
  "pre-bind eligibility skips it, so it never makes a quote conditional;",
  "the questionnaire does not ask about it;",
  "the dashboard's average posture score ignores it.",
]);
P("It is created at bind with the other warranties. For a company with no collector linked it never receives evidence, so it stays MET: missing evidence is not a breach, which is the platform's existing rule. The collector does not send it during the first 14 days after bind, so the insured's IT team has time to install the agent everywhere.");

// ================================================================= 7
H1("7. The collector in linked mode");
P("For a linked company the collector stops running its own warranty state machine. Its warranty cards show the states the platform returned after the last push, labelled as held by the Beretta platform. Binding the company on the collector is refused with LINKED_TO_PLATFORM. The warranty event list points to the platform's timeline. Companies that are not linked keep the stand-alone behaviour from the Part 2 document.");
figure("p2_link_panel.png", "Collector dashboard, linked company: the platform's warranty states and the link panel showing the last push and the mapping.", 600);
P("One difference is worth knowing for the viva. In the collector's own state machine a fix had to hold for 24 hours before REMEDIATED became MET. The platform's rule, which now applies, moves REMEDIATED to MET immediately. The platform's logic was kept as it was; adding a confirmation period there is a one-line change if wanted.");

// ================================================================= 8
H1("8. Code changes and tests");
table("Files changed", ["Project", "File", "Change"], [
  ["Part 1", "app/fleet.py (new)", "Register and link collectors, verify roll-ups, record AGENT_FLEET evidence, run warranties"],
  ["Part 1", "app/api.py", "Routes: /api/collector/rollup, /api/companies/{id}/fleet, admin collector endpoints"],
  ["Part 1", "app/catalogue.py", "AGENT_FLEET source type; CTRL-AGENT-COVERAGE as monitoring only"],
  ["Part 1", "app/database.py", "Four tables (collectors, links, roll-ups, fleet snapshots); monitoring_only column with a migration for existing databases"],
  ["Part 1", "app/underwriting.py, app/observations.py", "Skip monitoring-only controls in the posture modifier and eligibility"],
  ["Part 1", "frontend/app.js, styles.css", "Endpoints section on the Monitoring tab, intake card, Monitoring collectors admin section"],
  ["Part 2", "collector/kyh_collector/platform_link.py (new)", "Mapping, change detection, signing, push, background worker"],
  ["Part 2", "evaluate.py, core.py, server.py, db.py, settings.py", "Linked mode: no own warranties, platform state shown, bind refused, worker started"],
  ["Part 2", "__main__.py, static/app.js", "link-platform, link-company, push-now; link panel on the dashboard"],
  ["Both", "integration/, run_linked_demo.py", "End-to-end test across both systems; the presentation demo"],
], [1100, 3300, 4626]);
table("Tests", ["Suite", "Tests", "What the new ones prove"], [
  ["Part 1 (kyh-cyber-insurance)", "32 (17 original, unchanged, all passing + 15 new)", "Bad signature, unknown collector, replay, stale time, unlinked company, invalid values; AGENT_FLEET recorded at TECHNICALLY_OBSERVED; repeats skipped; fleet evidence lowers the quote; the monitoring-only control is never priced and never gates a quote; after bind a fleet failure moves the warranty and the premium and calculation count stay the same; coverage warranty enforced; HTTP admin and roll-up routes"],
  ["Part 2 (kyh-agent)", "144 (135 original + 9 new)", "Mapping and grouping rules, backup sent as partial, MFA never sent; signed, numbered, sent only on change; heartbeat; failed push retried; a silent host reaches the platform as a failure without any new report; collector runs no state machine for a linked company and refuses to bind it"],
  ["Integration", "1", "Both servers running: four agents report, the platform receives the fleet, the quote uses it, bind, EDR stops on one machine, the platform warranty goes IN_GRACE, the collector shows IN_GRACE, the fix brings it back to MET, and the premium never changes"],
], [2200, 1900, 4926]);

// ================================================================= 9
H1("9. Running it");
H2("9.1 The presentation demo");
code([
  "python run_linked_demo.py",
  "  Beretta platform: http://127.0.0.1:8000   (Kalinga Components -> Monitoring tab)",
  "  Collector:    http://127.0.0.1:8443   (paste the admin token it prints)",
  "",
  "kyh> bind                              # or click Calculate premium, then Bind, on the platform",
  "kyh> break KAL-PLANT-WS03 edr_down     # EDR warranty -> IN_GRACE within ~5 s",
  "kyh> fast-forward                      # DEMO ONLY: end the grace period -> BREACHED",
  "kyh> fix KAL-PLANT-WS03                # REMEDIATED -> MET",
]);
P("A suggested order for the panel: show the fleet on the platform before bind and point at the AGENT_FLEET evidence in the quote; bind; break EDR on one machine and show the warranty move while the premium stays the same; open the collector from the host link to show the evidence behind it; fix it. `fast-forward` writes a DEMO_TIME_TRAVEL entry to the audit log, so it is never hidden.");
H2("9.2 A real deployment");
N([
  "On the platform, as Administrator: Model configuration → Monitoring collectors → Register collector. Copy the command it shows; the secret is shown once.",
  "On the collector server: run that `link-platform` command, then `link-company --company co_xxxx --platform-company CO-xxxx` for each insured, then restart `serve`. The link worker starts automatically.",
  "On the platform: link the same company to the collector (Link a company to a collector).",
  "Install agents on the insured's machines as described in the Part 2 document. The first roll-up arrives within 30 seconds of the first report.",
  "Use HTTPS between the collector and the platform (`link-platform --url https://... --ca-file`).",
]);

// ================================================================= 10
H1("10. Limits and next steps");
B([
  "**The old single-host agent endpoint is still open** (`/api/agent/report`, one bearer token per company). It was kept so the Part 1 tests and demo still work. Once the collector is in use, it should be switched off, because it accepts unsigned reports.",
  "**Shared secrets.** Both the agent-to-collector and collector-to-platform links use HMAC, so each receiver holds a copy of the sender's secret. Public-key signatures would avoid that; Python's standard library has no Ed25519.",
  "**One collector per company.** A company can be linked to more than one collector, but their roll-ups would compete. One collector per insured is the intended set-up.",
  "**Grace periods are whole days on the platform.** That is why the demo uses `fast-forward` instead of short grace periods.",
  "**The platform's wider interface was not redesigned in this step.** Only the Monitoring tab, the intake card and the admin section changed. The broader interface changes are the next piece of work.",
]);

// ================================================================= static contents (page numbers from pages.json)
let pages = {};
try { pages = JSON.parse(fs.readFileSync(path.join(__dirname, "pages.json"), "utf8")); } catch (e) { /* first pass */ }
fs.writeFileSync(path.join(__dirname, "headings.json"), JSON.stringify(toc));
const tocParas = toc.map(([lvl, t]) => new Paragraph({
  spacing: { after: lvl === 1 ? 60 : 20, before: lvl === 1 ? 100 : 0, line: 276 },
  indent: { left: lvl === 1 ? 0 : 400 },
  tabStops: [{ type: "right", position: W, leader: "dot" }],
  children: [new TextRun({ text: t, font: FONT, size: lvl === 1 ? 23 : 21, bold: lvl === 1 }),
    new TextRun({ text: "\t" + (pages[t] || ""), font: FONT, size: lvl === 1 ? 23 : 21, bold: lvl === 1 })],
}));
body.splice(tocIndex, 0, ...tocParas);

// ================================================================= DOCUMENT
const numbering = { config: [
  { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ...Array.from({ length: 20 }, (_, i) => ({ reference: "numbers-" + (i + 1), levels: [{ level: 0,
    format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] })),
] };

const doc = new Document({
  creator: "Beretta capstone team",
  title: "Beretta: Linking Part 1 and Part 2",
  styles: {
    default: { document: { run: { font: FONT, size: 24, color: "000000" } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: "000000" }, paragraph: { spacing: { before: 120, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: "000000" }, paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, italics: true, font: FONT }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering,
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })] })] }) },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(__dirname, "Beretta_Part1_Part2_Link.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, `(${figN} figures, ${tabN} tables)`);
});
