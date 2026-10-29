// Builds docs/Beretta_Live_Monitoring_Agent.docx  (node build_doc.js)
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
tp("Part 2: Live Monitoring Agent", 40, { bold: true });
tp("How the agent and collector work, from the bottom up, and how to deploy them", 26, { italics: true });
body.push(new Paragraph({ spacing: { before: 900 }, children: [] }));
tp("Final-year capstone project, B.Tech / MBA Tech", 24);
tp("Mukesh Patel School of Technology Management & Engineering, NMIMS Mumbai", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Harsh (K080)  ·  Yugandhara Raj Goud (K023)  ·  Krish Mundhra (K041)", 24);
tp("Supervisor: Prof. Rohit Suryawanshi", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Agent and collector version 2.0.0  ·  Policy kyh-endpoint-baseline 2.0.0  ·  30 September 2026", 22);
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Contents", bold: true, font: FONT, size: 28 })] }));
const tocIndex = body.length;

// ================================================================= 1
H1("1. What the agent is");
P("The agent is the second part of Beretta. Part 1 prices a policy at inception. Part 2 answers a different question once the policy is bound: are the security controls the company promised still in place today?");
P("It has two pieces. The **agent** is a small Python program installed on each of the insured company's laptops, desktops and servers. It reads settings and status from the operating system, never changes anything, and sends a signed report. The **collector** is a server run by the insurer. It checks every report, combines the results for the whole company, and moves each coverage warranty through the states MET, IN_GRACE, BREACHED and REMEDIATED.");
P("One rule from Part 1 carries over unchanged: **monitoring never re-prices the policy.** The premium is fixed at bind by Engine B. Agent data can only change warranty states, and a warranty state changes what a claim pays under the policy wording, not what the policy costs. The collector has no code path that writes to the premium, and three tests check this (Section 7).");

H2("1.1 Does it have a visual interface?");
P("Yes, but not on the insured machine. There are three ways to see what the agent is doing:");
B([
  "**On the endpoint: no window.** The agent runs as a background service (a Windows scheduled task running as SYSTEM, a systemd service on Linux, a launchd daemon on macOS). An employee has nothing to click or close. This is deliberate: an agent with a tray icon can be quit by the person whose machine is being checked, and a GUI adds code that runs with high privileges.",
  "**On the endpoint: a terminal status command.** An administrator can run `python -m kyh_agent status` or `once --no-send` to print a colour-coded table of the latest results (example below). `show-policy` prints exactly what is checked and what is never collected.",
  "**At the insurer: a web dashboard.** The collector serves a dashboard in the browser, protected by an admin token. It shows the bound premium, fleet tiles, warranty cards with grace deadlines, a host-by-control matrix, per-host evidence and the event and audit history (Section 4.6, Figs. 7 and 8).",
]);
P("Real output from `once --no-send` on the Ubuntu 24.04 build machine used for this project (no EDR, no disk encryption, no NTP configured, so several checks fail as they should):");
code([
  "TIER       CONTROL           STATUS          ASSURANCE  SUMMARY",
  "---------------------------------------------------------------------------------------------",
  "warranty   PATCH             FAIL            PRESENT    Package index is 144.7 days old; ...",
  "warranty   EDR               FAIL            ABSENT     No known EDR/anti-malware process ...",
  "warranty   BACKUP            NOT_SUPPORTED   ABSENT     No local backup evidence found. ...",
  "warranty   MFA               NOT_SUPPORTED   -          MFA is enforced by the identity ...",
  "important  DISK_ENCRYPTION   FAIL            ABSENT     System drive is not encrypted",
  "important  EXPOSED_SERVICES  PASS            -          No high-risk services listening ...",
  "important  REMOTE_ACCESS     NOT_APPLICABLE  -          No SSH server installed",
  "important  OS_SUPPORT        PASS            -          Ubuntu 24.04.4 LTS supported until ...",
  "regulatory TIME_SYNC         FAIL            ABSENT     No NTP source configured",
]);

H2("1.2 What was built");
table("Deliverables in the repository", ["Component", "Location", "What it contains"], [
  ["Agent", "agent/kyh_agent/", "12 checks for Windows, Linux and macOS; policy file; runner; scheduler; signing; offline outbox; HTTPS client; command line"],
  ["Collector", "collector/kyh_collector/", "Enrollment, signed-report ingestion, fleet roll-up, warranty state machine, REST API, admin command line"],
  ["Dashboard", "collector/kyh_collector/static/", "Single-page web interface, vanilla HTML/CSS/JS, served by the collector"],
  ["Installers", "agent/install/", "install and uninstall scripts for Windows (PowerShell), Linux (systemd) and macOS (launchd)"],
  ["Tests", "tests/", "135 tests: parsers, decision rules, agent internals, collector logic, HTTPS end-to-end"],
  ["Demo", "scripts/run_demo.py", "Collector plus four simulated endpoints for a live presentation, with a 3-minute grace mode"],
], [1700, 2600, 4726]);
P("Everything uses the Python 3.9+ standard library only, matching the zero-dependency rule of Part 1. The code is about 4,000 lines, plus about 1,350 lines of tests.");

// ================================================================= 2
H1("2. The big picture");
figure("fig1_overview.png", "System overview. Agents report to the collector; the collector feeds the warranty state machine and the dashboard. There is no path from monitoring to pricing.");
P("A single report goes through these steps:");
N([
  "**Enroll (once).** The insured's IT team installs the agent with a one-time enrollment token from the insurer. The agent swaps the token for its own identity and a 256-bit secret.",
  "**Check.** On a schedule, the agent runs its read-only checks and turns each into PASS, FAIL or one of three \"could not tell\" statuses.",
  "**Report.** Results go into a signed JSON envelope with a sequence number. The envelope is written to a local queue first, then sent over HTTPS.",
  "**Verify.** The collector checks size, identity, signature, schema, sequence and timestamp before storing anything (Fig. 3).",
  "**Roll up.** Host results become one status per control for the whole company: at least 95% of observed hosts must pass.",
  "**Warranty.** For a bound policy, each warranty control moves through the state machine. Failing starts a grace period; failing past the deadline is a breach.",
  "**Show.** The dashboard displays the result, with the fixed premium at the top.",
]);

// ================================================================= 3
H1("3. The agent, from the bottom up");
P("The agent is built in ten layers. Each layer only talks to the ones next to it, which is what makes the lower layers testable without a real Windows machine and the upper layers testable without a network.");
figure("fig2_agent_layers.png", "Agent layers, from the operating system (1) up to the network (10).", 560);

H2("3.1 Layer 1: what is read on each operating system");
P("The policy groups checks into three tiers. **Warranty** checks feed the coverage warranties. **Regulatory** checks cover two CERT-In 2022 obligations that apply to every Indian entity in scope [2]. **Important** checks are hygiene: they are shown on the dashboard and stored as evidence but do not drive a warranty in this version.");
table("The twelve checks and where each one reads from", ["Control (tier)", "Windows", "Linux", "macOS"], [
  ["PATCH (warranty)", "Windows Update Agent COM search + Get-HotFix", "apt-get -s upgrade, dpkg.log; or dnf updateinfo --security", "softwareupdate -l"],
  ["EDR (warranty)", "Get-Process + Get-MpComputerStatus (Defender mode, real-time, signature age)", "/proc process table; mdatp health if present", "ps process table"],
  ["BACKUP (warranty)", "agent marker file; Get-WBSummary; backup software processes", "agent marker file; backup processes", "marker file; tmutil latestbackup"],
  ["MFA (warranty)", "not observable: always NOT_SUPPORTED", "same", "same"],
  ["DISK_ENCRYPTION", "Get-BitLockerVolume; manage-bde fallback", "lsblk: dm-crypt layer under /", "fdesetup status"],
  ["FIREWALL", "Get-NetFirewallProfile (all three profiles)", "ufw, firewalld, nftables, iptables", "socketfilterfw"],
  ["EXPOSED_SERVICES", "Get-NetTCPConnection -State Listen", "/proc/net/tcp and tcp6", "netstat -anv"],
  ["REMOTE_ACCESS", "registry: RDP enabled, NLA required", "sshd -T, or sshd_config with Include files", "sshd_config if SSH is listening"],
  ["ADMIN_ACCOUNTS", "Administrators group (SID S-1-5-32-544), Guest (RID 501)", "/etc/group sudo/wheel/admin, extra UID 0", "dscl admin group"],
  ["OS_SUPPORT", "registry build number vs lifecycle table", "/etc/os-release vs lifecycle table", "macOS major version"],
  ["LOG_RETENTION (regulatory)", "oldest Security/System event; log forwarder process", "oldest /var/log file or journal entry; forwarder or rsyslog forwarding", "forwarder process only"],
  ["TIME_SYNC (regulatory)", "w32tm /query /status + W32Time registry", "timedatectl, chronyc, chrony/timesyncd/ntp config", "systemsetup"],
], [1900, 2500, 2500, 2126]);
P("MFA is listed even though no endpoint can observe it. MFA is enforced by the identity provider (Microsoft Entra ID, Google Workspace), not by a laptop. Reporting NOT_SUPPORTED with guidance on what document to upload is more honest than guessing, and it keeps the report complete.");

H2("3.2 Layer 2: collectors");
P("A collector is the only code that touches the operating system. Every OS command goes through one function, `run_cmd`, which enforces four rules in one place:");
B([
  "Commands are passed as a list of arguments. A shell string is refused, and `shell=True` is never used, so no check can be turned into command injection.",
  "Every call has a timeout. A hung command becomes an ERROR result instead of a stuck agent.",
  "The locale is forced to `C`, so output parses the same on an English or Hindi Windows install.",
  "On Windows no console window flashes on the user's screen.",
]);
P("Where Python can read something directly, no process is started at all: the Linux process list and listening sockets come from `/proc`, and Windows registry values come from the standard `winreg` module. The commands that are run are read-only by construction: PowerShell `Get-*` cmdlets, `apt-get -s` (simulate), `dnf --cacheonly`.");

H2("3.3 Layer 3: parsers");
P("Parsers turn raw text or JSON into plain facts and never touch the OS. That is why they can be tested on a Linux build machine with output captured from Windows and macOS. Some cases the parsers handle:");
B([
  "PowerShell's `ConvertTo-Json` turns a one-element list into a single object; the Windows Update and firewall parsers accept both.",
  "BitLocker status can come back as a word (\"On\") or a number (1) depending on the PowerShell version.",
  "OpenSSH uses the **first** value it sees for a setting. On Ubuntu cloud images, `/etc/ssh/sshd_config.d/50-cloud-init.conf` is included at the top and often sets `PasswordAuthentication yes`, which silently overrides a `no` further down the main file. The parser expands Include files in place and applies first-value-wins, so it reports what sshd actually does.",
  "IPv6 addresses in `/proc/net/tcp6` are stored as four little-endian 32-bit words.",
]);

H2("3.4 Layer 4: verdicts");
P("A verdict takes facts plus the policy thresholds and returns a status, an assurance level, a one-line summary and the evidence behind it. Separating the rule from the data collection means each rule can be read, cited and tested on its own.");
table("Result status", ["Status", "Meaning"], [
  ["PASS", "Control observed and meets the threshold"],
  ["FAIL", "Control observed and does not meet the threshold"],
  ["NOT_APPLICABLE", "Control does not apply here, e.g. no SSH server installed"],
  ["NOT_SUPPORTED", "Cannot be observed from this machine, e.g. MFA, or the check needs admin rights"],
  ["ERROR", "The check itself failed: timeout, crash or unreadable output"],
], [2200, 6826]);
table("Assurance level: how strongly the control was seen working", ["Level", "Meaning", "Example"], [
  ["OPERATING", "Running, and a health signal confirms it works", "Defender active, real-time on, signatures 1 day old"],
  ["RUNNING", "Running or configured; effectiveness not checkable locally", "CrowdStrike process seen; logs forwarded to Wazuh"],
  ["PRESENT", "Installed but not effective", "Defender with 9-day-old signatures; BitLocker suspended"],
  ["ABSENT", "Not found", "No anti-malware process at all"],
], [1700, 3900, 3426]);
P("The assurance level is how the agent follows the Part 1 rule that tool presence is not a working control. A stale Defender is FAIL with assurance PRESENT, not a PASS. Some of the rules, in plain words:");
B([
  "**Patching.** PASS if no security updates are pending, or if some are pending but the machine was patched within the last 30 days (a normal monthly cycle). FAIL if the package index is more than 14 days old, because then \"0 pending\" means nothing.",
  "**EDR.** PASS/OPERATING for Defender only if it is the active engine, real-time protection is on and signatures are at most 3 days old. A known third-party EDR process is PASS/RUNNING, since its health cannot be queried without the vendor's tools.",
  "**Backup.** PASS if the last success is within 7 days. Backup software with no readable timestamp is NOT_SUPPORTED, not FAIL, because backups often run centrally. Restore testing is always marked as not verified.",
  "**Exposed services.** Telnet, FTP, VNC, Redis, Elasticsearch, Memcached and MongoDB listening on a network interface is a FAIL. RDP, SMB, SSH and database ports pass with a \"review\" note, because the agent cannot tell whether they are reachable from the internet; that needs an outside-in scan.",
  "**Time sync.** PASS only when synchronised to `samay1.nic.in`, `samay2.nic.in` or `time.nplindia.org`, the NIC and NPL servers named for the CERT-In Directions. A domain-joined Windows PC syncing from its domain controller passes with RUNNING, and the note asks the insured to confirm the domain controller syncs to NIC/NPL.",
]);

H2("3.5 Layer 5: the policy file");
P("`policy.json` decides which checks run, how often, and every threshold. It is data, not code. The list of things the agent can check is fixed in the program (the check registry), and the policy can only choose from that list and set numbers. A policy that names an unknown check is rejected when it loads. This means nobody, including the insurer, can push new code to an insured machine through the policy.");
P("The policy is hashed (SHA-256 of its canonical JSON), and the hash goes into every report. The collector only trusts results produced under a policy hash it has approved. Every threshold that is an assumption rather than a sourced value is tagged `C-asm`, following the provenance discipline of Part 1.");
table("Main thresholds and their provenance", ["Setting", "Value", "Provenance"], [
  ["Patch cycle / package index age", "30 days / 14 days", "C-asm"],
  ["EDR signature age", "3 days", "C-asm"],
  ["Backup age", "7 days", "C-asm"],
  ["Local administrators", "at most 3", "C-asm"],
  ["Log retention", "180 days", "CERT-In Directions, 28 Apr 2022 [2]"],
  ["Approved time sources", "samay1/samay2.nic.in, time.nplindia.org", "CERT-In Directions and FAQ [2]"],
  ["OS end-of-support dates", "table per OS and build", "Vendor lifecycle pages as of 30 Sep 2026 [11], [12]; re-verify before submission"],
], [3200, 2800, 3026]);

H2("3.6 Layer 6: the runner");
P("The runner calls the right platform function for each check and wraps it so that nothing a check does can stop the agent:");
table("How the runner handles failures", ["What happens in a check", "Result"], [
  ["Needs admin rights it does not have", "NOT_SUPPORTED, evidence notes requires_admin"],
  ["Required OS tool not installed", "NOT_SUPPORTED"],
  ["OS command times out", "ERROR"],
  ["Python exception (bug, unexpected output)", "ERROR with the exception type"],
  ["Check hangs past its time budget", "ERROR; the check is abandoned and the agent moves on"],
], [4500, 4526]);

H2("3.7 Layer 7: the scheduler");
P("The scheduler runs each check on its own interval and sends three kinds of report:");
B([
  "**Full snapshot** once a day (and on start-up): every check result.",
  "**Delta** whenever a result changes. Only the changed results are sent. \"Changed\" means a different status, assurance or summary; timestamps do not count.",
  "**Heartbeat** every 15 minutes, with no results. It tells the collector the machine is alive, which matters for the silence rule in Section 4.3.",
]);
table("Check intervals", ["Checks", "Interval"], [
  ["EDR", "every 60 minutes"],
  ["PATCH, BACKUP", "every 4 hours (the Windows Update search is slow)"],
  ["All others", "every 24 hours"],
], [4500, 4526]);
P("Each interval gets ±10% random jitter, so a company's 500 laptops do not all report in the same second after a power cut.");

H2("3.8 Layer 8: the envelope and its signature");
P("Every report is a JSON envelope. A shortened example:");
code([
  "{ \"schema_version\": 2, \"kind\": \"delta\", \"agent_id\": \"ag_53b33de7def34672\", \"seq\": 41,",
  "  \"created_at\": \"2026-09-30T11:41:54Z\",",
  "  \"agent\":  { \"version\": \"2.0.0\", \"build_hash\": \"4c68...3448\", \"platform\": \"windows\",",
  "              \"hostname\": \"KAL-FIN-LT01\", \"os\": \"Windows 11 Pro 24H2\" },",
  "  \"policy\": { \"id\": \"kyh-endpoint-baseline\", \"version\": \"2.0.0\", \"hash\": \"31f4...19e1\" },",
  "  \"simulated\": false, \"queue_depth\": 0,",
  "  \"results\": [ { \"check_id\": \"edr.running_healthy\", \"control\": \"EDR\", \"tier\": \"warranty\",",
  "                 \"status\": \"FAIL\", \"assurance\": \"PRESENT\",",
  "                 \"summary\": \"Microsoft Defender present but signatures 9 days old (limit 3)\",",
  "                 \"evidence\": { ... }, \"method\": \"Get-Process + Get-MpComputerStatus\",",
  "                 \"observed_at\": \"2026-09-30T11:41:50Z\" } ] }",
]);
P("The agent serialises the envelope in a fixed way (sorted keys, no spaces) and computes an HMAC-SHA256 over the exact bytes using its secret. The result travels in the `X-KYH-Signature` header. If one byte of the report changes on the way, the collector's recomputed signature will not match. The **sequence number** only goes up and survives restarts; the collector refuses any number it has already seen, which stops an old \"all PASS\" report from being replayed.");
P("The **build hash** is a SHA-256 over every file of the agent's code and its policy. A modified agent, for example one edited to always return PASS, produces a different build hash, and its reports are stored but not trusted (Section 4.2).");

H2("3.9 Layer 9: the outbox");
P("Every report is written to a small SQLite database on the machine before it is sent. If the laptop is offline, on a train or behind a captive portal, reports wait in order with their original timestamps and are replayed when the connection returns. The collector accepts reports up to 30 days old. The outbox is capped at 10,000 reports; when full, it drops old heartbeats first, then old deltas, and keeps full snapshots longest.");
table("How the agent reacts to each collector answer", ["Answer", "Agent action"], [
  ["202 Accepted", "Remove from outbox"],
  ["409 REPLAY", "Remove: the collector already has it (the first answer was lost)"],
  ["Other 4xx (bad signature, bad schema)", "Move to a dead-letter table so it cannot block the queue"],
  ["429 or 5xx, or no connection", "Keep it, back off (30 s doubling up to 15 min), retry"],
], [3800, 5226]);

H2("3.10 Layer 10: transport");
P("Reports go over HTTPS with TLS 1.2 or newer. The agent is given the collector's own certificate authority file (`ca.pem`) at install, and it trusts **only** that CA. A network device doing TLS interception, or a fake collector with a certificate from a public CA, is refused. Plain HTTP is allowed only to `localhost`, for development.");

H2("3.11 Commands on the machine, and transparency");
table("Agent command line", ["Command", "Purpose"], [
  ["enroll --server --token --ca-file", "One-time registration with the collector"],
  ["run", "Service mode; this is what the service manager starts"],
  ["once [--no-send] [--json]", "Run every check now and print the table (or the full JSON)"],
  ["status", "Last results and how many reports are waiting to be sent"],
  ["show-policy", "What is checked, how often, and what is never collected"],
  ["build-info", "Version, build hash and policy hash, for the insurer to approve"],
], [3500, 5526]);
P("The agent also writes `sent.jsonl` on the machine: one line per report sent, with the status of every check. The insured's staff can see exactly what left their machine.");

H2("3.12 Simulation mode");
P("A live presentation cannot switch off Defender on a laptop in front of an examiner. `--simulate <profile>` replaces the real checks with scripted results (`healthy`, `edr_down`, `edr_stale`, `patch_overdue`, `backup_stale`, `mixed`). Every simulated result starts with \"[SIMULATED]\", carries `simulated: true` in its evidence, and the whole envelope is flagged. The collector ignores simulated reports unless the company was created in demo mode.");

// ================================================================= 4
H1("4. The collector");
H2("4.1 Enrollment");
P("The insurer creates an enrollment token for a company with a limit on uses and an expiry date (for example, 45 uses over 14 days for a 40-machine fleet). Only a hash of the token is stored. When an agent enrolls, the collector checks the token, creates an agent ID and a random 256-bit secret, and returns both over TLS. The agent stores the secret in a file only the system account can read. The collector also returns its clock time, and the agent warns if the two differ by more than 5 minutes, since timestamps are evidence.");

H2("4.2 Checking a report");
figure("fig3_ingest.png", "The ingestion gate. Each check must pass before the next runs; the report is stored only at the end.");
P("Signature failures and replayed sequence numbers are written to the audit log as security events. Once a report passes, it is stored exactly as received, together with its SHA-256, and never edited. A correction is simply a newer report. Each result is labelled with an evidence strength:");
table("Evidence strength of a stored result", ["Label", "When", "Counts toward warranties?"], [
  ["TECHNICALLY_OBSERVED", "Approved build and approved policy", "Yes"],
  ["SIMULATED", "Envelope flagged simulated", "Only for demo-mode companies"],
  ["UNTRUSTED_BUILD", "Build hash not on the approved list", "No"],
  ["UNTRUSTED_POLICY", "Policy hash not on the approved list", "No"],
], [2600, 3900, 2526]);
P("TECHNICALLY_OBSERVED is the top step of the Part 1 evidence ladder (credit 1.00). Before bind, these observations can feed Engine A as evidence; after bind, they reach only the warranty state machine.");

H2("4.3 From one host to a warranty");
figure("fig4_rollup.png", "Roll-up from a single check result to a company warranty.");
P("**Liveness.** Each host is ONLINE, UNVERIFIED or SILENT depending on how long it has been quiet (Fig. 5). This is the answer to the most obvious way to cheat: uninstall the agent from a machine that is failing. If silence were ignored, the failing machine would vanish and the warranty would look healthier. Under this rule, a machine quiet for more than 72 hours counts as a FAIL for every control it was able to observe. Controls it could never observe, such as MFA, are left alone.");
figure("fig6_liveness.png", "The silence rule.");
P("**Host control.** If any check for a control on a host fails, the host fails that control. **Fleet control.** Only hosts that could observe the control count. The control passes for the company if at least 95% of them pass. If no host can observe it, the status is NOT_OBSERVABLE, and the warranty does not move: missing evidence is not treated as a breach. MFA is always in this position until an identity-provider connector exists.");

H2("4.4 The monitoring-coverage warranty");
P("A company could also enroll only its five best machines. To close that gap, the collector adds a fifth warranty, MONITORING_COVERAGE: the number of hosts reporting must be at least 90% of the endpoint count the company declared on its proposal form. It is not enforced for the first 14 days after bind, so IT has time to roll the agent out.");

H2("4.5 The warranty state machine");
figure("fig5_states.png", "Warranty states and transitions.");
P("The rules are the same as in Part 1, with one addition: a fix must hold for 24 hours before REMEDIATED returns to MET, so a warranty cannot flap between states every hour. Grace expiry is checked whenever the company is evaluated, which happens on every report and every dashboard load, so no scheduler is needed. Every transition is written to the warranty event log with its reason.");
table("Illustrative coverage consequences while BREACHED [C-asm]", ["Warranty", "Grace", "Consequence (illustrative, not policy wording)"], [
  ["PATCH", "14 days", "Ransomware & cyber-extortion claims subject to 50% co-insurance"],
  ["EDR", "7 days", "Ransomware & cyber-extortion claims subject to a 2x deductible"],
  ["BACKUP", "7 days", "Business-interruption and data-restoration cover subject to 25% co-insurance"],
  ["MFA", "7 days", "Social-engineering / funds-transfer-fraud cover suspended"],
  ["MONITORING_COVERAGE", "14 days", "Unmonitored endpoints treated as non-compliant for all warranties"],
], [2300, 1100, 5626]);
P("Every consequence shown by the system carries the label used in Part 1: ~Prototype coverage-condition evaluation; final claim determination remains subject to policy wording and authorized claims handling.~");

H2("4.6 The dashboard");
P("The dashboard is a single page served by the collector. After sign-in with the admin token it shows a list of insured companies, then, for each company:");
B([
  "a banner with the bound premium and the statement that monitoring never re-prices;",
  "tiles for declared endpoints, enrolled agents, hosts reporting, and hosts online, unverified or silent;",
  "one card per warranty with its state, the grace deadline, the reason and the consequence;",
  "a table of every control across the fleet with the failing hosts named;",
  "a host-by-control matrix; each host links to a page with every check result, its assurance level, the raw evidence and the list of stored reports with their hashes;",
  "the warranty event log and the audit trail.",
]);
P("It refreshes every 15 seconds. Hostnames, summaries and evidence come from agents, which sit outside the insurer's trust boundary, so every value is HTML-escaped before display and the page is served with a strict Content-Security-Policy.");
figure("dash_company_top.png", "Dashboard, company view, from the live demo (simulated endpoints, 3-minute grace periods). EDR has passed its grace deadline and is BREACHED; PATCH is in grace; BACKUP failed, was fixed and is back to MET. The premium has not changed.", 600);
figure("dash_host.png", "Dashboard, host view: every check with its assurance level, the evidence behind it, and the immutable report history.", 560);

H2("4.7 API");
table("Collector HTTP API", ["Method and path", "Who calls it", "Purpose"], [
  ["POST /api/v1/enroll", "Agent", "Exchange an enrollment token for identity and secret"],
  ["POST /api/v1/report", "Agent", "Submit a signed report; the answer includes repricing_performed: false"],
  ["GET /api/v1/overview", "Dashboard (admin token)", "All companies with coverage and warranty states"],
  ["GET /api/v1/companies/{id}", "Dashboard (admin token)", "Full company view, events and audit"],
  ["GET /api/v1/agents/{id}", "Dashboard (admin token)", "Host detail; the signing secret is never returned"],
  ["GET /healthz", "Monitoring", "Liveness of the collector itself"],
], [2900, 2300, 3826]);

// ================================================================= 5
H1("5. Security design");
P("The main threat here is unusual. In most security software the attacker is an outsider. In insurance monitoring the party with a reason to fake a PASS is the insured, who controls the machine the agent runs on. Mott et al. describe how insurers moved from questionnaires to making controls a condition of cover during the ransomware years [6]; that move only works if the evidence is hard to fake.");
table("Threats and defences", ["Threat", "Defence", "What remains"], [
  ["Report edited in transit", "TLS with a pinned private CA; HMAC over exact bytes", "None found in testing"],
  ["Old \"all PASS\" report replayed", "Strictly increasing sequence number; 30-day window", "None found in testing"],
  ["Agent uninstalled or blocked on a failing machine", "Heartbeats; silence over 72 h counts as FAIL; coverage warranty", "72-hour window [C-asm]"],
  ["Agent code edited to always pass", "Build hash checked against approved releases", "A local admin who also forges the build hash can still lie (see below)"],
  ["Policy edited to lower thresholds", "Policy hash checked against approved policies", "Same as above"],
  ["Insurer pushes code to the insured", "No command channel; policy is data; unknown checks rejected", "None"],
  ["Stolen enrollment token", "Hashed at rest, limited uses, expiry; every enrollment audited", "Rogue hosts could enroll within the limits"],
  ["Malicious values in reports (XSS)", "Server-side validation of ids and statuses; escaping in the dashboard; CSP", "None found in testing"],
  ["Flooding the collector", "1 MB body cap; per-agent and per-IP rate limits", "No protection against a large distributed flood"],
  ["Collector database leak", "Tokens stored as hashes; secret never returned by the API", "Agent secrets are stored in clear (needed for HMAC)"],
], [2400, 3700, 2926]);
P("The honest limit: an administrator on the insured machine who is determined to lie can read the agent's secret and send well-formed false reports. Software alone cannot stop this. The fix is hardware-backed attestation, in which a TPM chip signs measurements of what code is running, as done by the open-source Keylime project [9]. It is listed as future work in Section 10, in the same way Part 1 flags the flat reinsurance loading instead of hiding it.");
P("On the endpoint, the Linux service runs as root because some checks need it (firewall rules, `sshd -T`, the full process list), but systemd makes the whole filesystem read-only for it except its own state folder, and caps it at 5% CPU and 150 MB of memory.");

// ================================================================= 6
H1("6. Privacy");
P("The agent runs on machines that employees use, so the Digital Personal Data Protection Act 2023 applies to what it sends [3]. The design collects configuration state and nothing about people.");
table("What the agent collects", ["Collected", "Never collected"], [
  ["Control states, OS version, hostname, counts, configuration values, installed security software names", "File contents, document names, browsing history, keystrokes, screenshots, e-mail, passwords"],
  ["Administrator account names as salted hashes (salted with the agent ID, so they cannot be matched across companies)", "Usernames in clear text"],
], [4513, 4513]);
P("Every report sent is logged on the machine in `sent.jsonl`, and `show-policy` prints the collected and never-collected lists. A server-side retention period for raw reports is not implemented yet and is listed in Section 10.");

// ================================================================= 7
H1("7. Testing");
P("All 135 tests pass with `python run_tests.py` in about 4 seconds on Python 3.11.");
table("Test suite", ["File", "Tests", "What it proves"], [
  ["test_parsers.py", "36", "Every parser against output captured from Windows, Ubuntu, Debian, RHEL and macOS, including the PowerShell single-object and sshd drop-in cases"],
  ["test_verdicts.py", "28", "Every decision rule, including: stale EDR signatures give FAIL/PRESENT, not OPERATING; MFA is never claimed; Windows 11 24H2 warns 13 days before end of support"],
  ["test_agent_core.py", "33", "Policy cannot add checks; runner turns crash, timeout, missing tool and missing admin into statuses; no shell; signing and tamper detection; build hash changes when code changes; outbox order and cap; scheduling, deltas, jitter, heartbeats; offline replay; simulation labelling; config file permissions"],
  ["test_collector.py", "33", "Enrollment tokens; every ingestion rejection; untrusted builds and simulated reports not counted; 95% roll-up; full lifecycle MET > IN_GRACE > BREACHED > REMEDIATED > MET; regression gets a fresh grace; silence rule; coverage warranty and onboarding window; retirement; no repricing"],
  ["test_end_to_end.py", "5", "Real HTTPS with a generated private CA: two agents enroll and report, warranty state changes; replayed and forged reports rejected; an agent pinned to another CA refuses to connect; dashboard needs the admin token; path traversal is refused"],
], [2000, 800, 6226]);
P("The mandatory acceptance test from Part 1 is kept in three forms. The first drives a company into BREACHED and checks that the policy row, including the premium, is byte-for-byte the same as at bind. The second checks that binding twice is refused. The third reads the source of the ingestion and evaluation functions and fails if any of them contains an SQL statement that writes to the policies table.");
P("**Limit of the test suite.** The Windows and macOS collectors were tested through their parsers with captured output. They have not yet been run end to end on a real Windows or Mac machine in this environment. Section 8.7 lists the checks to run on a Windows laptop before the demo.");

// ================================================================= 8
H1("8. Deployment");
figure("fig7_deploy.png", "Deployment sequence.");
H2("8.1 What you need");
B([
  "**Collector server:** any machine with Python 3.9+ and the `openssl` tool (for the certificates). The insurer runs it. Port 8443 must be reachable from the insured's network.",
  "**Each endpoint:** Python 3.9+ installed for all users, and administrator rights for the install. Windows 10/11 and Server 2016+, Ubuntu/Debian/RHEL-family Linux, macOS 14+.",
  "From the insurer to the insured: the agent folder, `ca.pem` and an enrollment token.",
]);
H2("8.2 Set up the collector");
code([
  "export PYTHONPATH=collector:agent        # Windows: set PYTHONPATH=collector;agent",
  "alias kc='python -m kyh_collector --data /srv/kyh'",
  "",
  "kc init                  # prints the admin token ONCE; keep it in a password manager",
  "kc gen-cert --host collector.example.in",
  "                         # tls/ca.pem goes to agents; keep tls/ca.key offline",
  "kc add-company --name \"Kalinga Components\" --declared-endpoints 40   # prints co_xxxx",
  "kc bind --company co_xxxx --premium 245000",
  "python -m kyh_agent build-info          # prints build_hash and policy_hash",
  "kc approve-build  --hash <build_hash>  --label 2.0.0",
  "kc approve-policy --hash <policy_hash> --label baseline-2.0.0",
  "kc issue-token --company co_xxxx --max-uses 45 --days 14",
  "kc serve --host 0.0.0.0 --port 8443 \\",
  "   --tls-cert /srv/kyh/tls/server.pem --tls-key /srv/kyh/tls/server.key",
]);
P("The premium passed to `bind` is the figure Engine B calculated at inception; the collector only records it. Thresholds can be changed by creating `/srv/kyh/settings.json` with the keys to override (for example `{\"grace_days\": {\"EDR\": 10}}`).");
H2("8.3 Install on Windows");
code([
  "# Elevated PowerShell, in the agent folder",
  ".\\install\\windows\\install.ps1 -Server https://collector.example.in:8443 `",
  "    -Token kyh_enr_XXXX -CaFile .\\ca.pem",
]);
P("The script copies the agent to `C:\\Program Files\\KYH\\Agent`, creates `C:\\ProgramData\\KYH\\Agent` readable only by SYSTEM and Administrators, enrolls, and registers a scheduled task named \"KYH Live Monitoring Agent\" that runs as SYSTEM at start-up and restarts every minute if it stops. A scheduled task is used instead of a Windows service because a native service needs `pywin32` or a wrapper, and the agent has no third-party dependencies.");
H2("8.4 Install on Linux");
code([
  "sudo ./install/linux/install.sh --server https://collector.example.in:8443 \\",
  "     --token kyh_enr_XXXX --ca-file ca.pem",
  "systemctl status kyh-agent          # should be active (running)",
  "journalctl -u kyh-agent -f",
]);
P("Code goes to `/opt/kyh-agent`, configuration (including the secret, mode 600) to `/etc/kyh-agent`, and state to `/var/lib/kyh-agent`.");
H2("8.5 Install on macOS");
code(["sudo ./install/macos/install.sh --server https://collector.example.in:8443 \\",
  "     --token kyh_enr_XXXX --ca-file ca.pem",
  "sudo launchctl print system/com.kyh.agent"]);
H2("8.6 Check that it works");
N([
  "On the endpoint, run `status`: it should show a recent scan and 0 reports waiting.",
  "On the dashboard, the host should appear as ONLINE within a minute, with a green BUILD APPROVED badge. A red UNTRUSTED BUILD badge means `approve-build` was not run for this release.",
  "Open the host page and read the evidence for any FAIL. A NOT_SUPPORTED that mentions admin rights means the agent is not running as SYSTEM/root.",
]);
H2("8.7 Before the demo: checks on a real Windows laptop");
B([
  "Run `python -m kyh_agent once --no-send` from an elevated prompt and confirm each of the 12 checks gives a sensible result, not ERROR.",
  "Turn Defender real-time protection off for a minute and re-run: EDR should go to FAIL/PRESENT.",
  "Turn the Windows Firewall off for the Public profile: FIREWALL should FAIL and name the profile.",
]);
H2("8.8 Running the system over time");
table("Routine operations", ["Task", "How"], [
  ["New agent release", "Run build-info on the new release and approve-build on the collector before rolling it out; hosts on the old build stay trusted until you remove it"],
  ["Machine decommissioned", "kyh_collector retire --agent ag_xxx (audited); otherwise it goes SILENT and counts as failing"],
  ["More machines to enroll", "issue-token again; tokens expire and have a use limit"],
  ["Back up the collector", "Copy the data folder (collector.db holds reports, evidence and events)"],
  ["Remove the agent", "install/*/uninstall script, after retiring the host"],
], [2800, 6226]);
H2("8.9 Presentation demo");
code(["python scripts/run_demo.py --fast",
  "kyh-demo> break KAL-PLANT-WS03 edr_down   # EDR goes IN_GRACE, then BREACHED ~3 min later",
  "kyh-demo> fix KAL-PLANT-WS03              # REMEDIATED, then MET ~2 min later",
  "kyh-demo> break KAL-FIN-LT01 mixed        # PATCH in grace + CERT-In TIME_SYNC failure"]);
P("`--fast` shortens the grace periods to about three minutes so the whole lifecycle fits in a presentation. The premium on the banner does not change at any point, which is the point to make to the panel.");

// ================================================================= 9
H1("9. Connecting to the Part 1 platform");
P("The agent and collector were built as a separate package so they could be tested on their own. They follow the Part 1 data model (evidence strengths, warranty states, grace periods, consequence labels, audit log), and they are not yet wired into the Part 1 server. The merge path:");
N([
  "**Before bind:** each company-level control from the collector becomes a TECHNICALLY_OBSERVED observation in Engine A, with the collector report hash as its locator. Engine B then prices as it does today.",
  "**After bind:** the Part 1 agent-report handler is replaced by the collector's ingestion, and the Part 1 `coverage.py` warranties read the collector's company-level status. MONITORING_COVERAGE is added to the warranty list.",
  "**Control names:** PATCH, EDR, BACKUP and MFA map to the four Tier-1 controls of the 15-control catalogue. The hygiene and CERT-In checks map to the Tier-2 and Tier-3 controls where they exist and become new catalogue entries where they do not.",
]);

// ================================================================= 10
H1("10. Limitations and next steps");
B([
  "**Local administrators can forge reports.** Needs TPM-based attestation (for example Keylime [9]) to fix; out of scope for a prototype.",
  "**HMAC means the collector holds every agent's secret.** Moving to per-agent Ed25519 signatures would let the collector verify without being able to sign. Python's standard library has no Ed25519, so this would break the zero-dependency rule.",
  "**MFA is not observed.** Needs an identity-provider connector (Entra ID conditional access, Google Workspace 2-Step Verification enforcement).",
  "**Exploited-vulnerability matching** against the CISA KEV catalogue [10] was left out of this phase. Matching installed software versions to CVEs is error-prone; a first version would cover only browsers, VPN clients and remote-access tools.",
  "**Windows packaging.** A signed installer and a real Windows service (for example PyInstaller plus sc.exe) would remove the need for Python on each machine.",
  "**Time-sync traceability.** A server that is traceable to NIC/NPL but not named in the list currently fails; the insured has to document it.",
  "**Configured vs selected NTP source.** With chrony, a NIC server listed in the configuration counts even if chrony currently prefers another source.",
  "**Thresholds and lifecycle dates** are demonstration values or dated vendor data and need review before any real use.",
  "**No retention limit** is enforced yet for raw reports on the collector.",
]);

// ================================================================= REFERENCES
H1("References");
[
  "[1] K. Dempsey et al., \"Information Security Continuous Monitoring (ISCM) for Federal Information Systems and Organizations,\" NIST Special Publication 800-137, Sep. 2011. doi: 10.6028/NIST.SP.800-137.",
  "[2] Indian Computer Emergency Response Team (CERT-In), \"Directions under sub-section (6) of section 70B of the Information Technology Act, 2000,\" No. 20(3)/2022-CERT-In, 28 Apr. 2022, and FAQs, 18 May 2022.",
  "[3] Government of India, The Digital Personal Data Protection Act, 2023 (No. 22 of 2023).",
  "[4] Center for Internet Security, \"CIS Critical Security Controls, Version 8,\" 2021.",
  "[5] D. Woods, I. Agrafiotis, J. R. C. Nurse, and S. Creese, \"Mapping the coverage of security controls in cyber insurance proposal forms,\" Journal of Internet Services and Applications, vol. 8, no. 8, 2017. doi: 10.1186/s13174-017-0059-y.",
  "[6] G. Mott, S. Turner, J. R. C. Nurse, J. MacColl, J. Sullivan, A. Cartwright, and E. Cartwright, \"Between a rock and a hard(ening) place: Cyber insurance in the ransomware era,\" Computers & Security, vol. 128, 103162, 2023. doi: 10.1016/j.cose.2023.103162.",
  "[7] Wazuh Inc., \"Security Configuration Assessment,\" Wazuh documentation. [Online]. Available: https://documentation.wazuh.com/current/user-manual/capabilities/sec-config-assessment/index.html",
  "[8] osquery project, \"osquery: SQL powered operating system instrumentation.\" [Online]. Available: https://osquery.io/",
  "[9] Keylime project (CNCF), \"Keylime: bootstrap and maintain trust on the edge, cloud and IoT.\" [Online]. Available: https://keylime.dev/",
  "[10] Cybersecurity and Infrastructure Security Agency, \"Known Exploited Vulnerabilities Catalog.\" [Online]. Available: https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
  "[11] Microsoft, \"Microsoft Lifecycle Policy.\" [Online]. Available: https://learn.microsoft.com/en-us/lifecycle/",
  "[12] Canonical, \"Ubuntu release cycle.\" [Online]. Available: https://ubuntu.com/about/release-cycle",
].forEach((r) => body.push(new Paragraph({ children: runs(r), spacing: { after: 100, line: 300 },
  indent: { left: 560, hanging: 560 } })));
P("NIST SP 800-137 [1] frames the agent as continuous monitoring of control effectiveness. Woods et al. [5] show that proposal forms rely on self-assessment, which is the motivation for technically observed evidence. Wazuh SCA [7] and osquery [8] are prior art for policy-driven configuration checks and change-only reporting; the agent does not use them, to keep zero dependencies.", { spacing: { before: 200, line: 360 } });

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
  title: "Beretta: Live Monitoring Agent",
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
  const out = path.join(__dirname, "Beretta_Live_Monitoring_Agent.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, `(${figN} figures, ${tabN} tables)`);
});
