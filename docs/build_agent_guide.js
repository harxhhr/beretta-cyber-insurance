// Builds docs/Beretta_Agent_Complete_Guide.docx  (node build_agent_guide.js)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, AlignmentType, HeadingLevel,
  WidthType, ShadingType, BorderStyle, Footer, PageNumber, LevelFormat, PageBreak, TableOfContents,
} = require("docx");

const FIG = path.join(__dirname, "figures");
const FIG2 = path.join(__dirname, "..", "kyh-agent", "docs", "figures");
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
const NC = (items) => B(items, "numbers-" + numCount);
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
  const f = fs.existsSync(path.join(FIG, file)) ? path.join(FIG, file) : path.join(FIG2, file);
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
body.push(new Paragraph({ spacing: { before: 1500 }, children: [] }));
tp("Beretta", 28, { bold: true });
tp("The Live Monitoring Agent", 40, { bold: true });
tp("A complete technical guide, from the operating system to the warranty", 26, { italics: true });
tp("How it works, how it is set up, and how to answer questions about it", 24, { italics: true });
body.push(new Paragraph({ spacing: { before: 800 }, children: [] }));
tp("Final-year capstone project, B.Tech / MBA Tech", 24);
tp("Mukesh Patel School of Technology Management & Engineering, NMIMS Mumbai", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Harsh (K080)  ·  Yugandhara Raj Goud (K023)  ·  Krish Mundhra (K041)", 24);
tp("Supervisor: Prof. Rohit Suryawanshi", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Agent 2.0.0  ·  Collector 2.0.0 (linked mode)  ·  Beretta platform UNDERWRITING_MODEL_V1  ·  27 October 2026", 22);
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Contents", bold: true, font: FONT, size: 28 })] }));
const tocIndex = body.length;

// ================================================================= 1
H1("1. How to use this guide");
P("This guide explains the second part of Beretta, the live monitoring agent, and everything it connects to. It starts at the bottom, with the exact setting the agent reads on a Windows, Linux or Mac machine, and works up through the agent's layers, the collector that receives its reports, and the Beretta platform that holds the policy. It then covers set-up, the full workflow of a policy, the security and privacy design, the tests, the design decisions, and the limits.");
P("It replaces the earlier \"Live Monitoring Agent\" document, which was written before the agent was linked to the platform. Everything here was checked against the code as it stands now (agent and collector 2.0.0, linked mode, with the VM support added on 27 October 2026).");
B([
  "**For a quick overview**, read Section 3 and look at Fig. 2 (the path of one check).",
  "**For the viva**, read Section 3, then Section 14 (design decisions and why) and Section 16 (questions and answers). The numbers worth remembering are in Table 3.",
  "**For set-up**, Section 8 gives the commands; the separate VM guide has every click.",
]);
P("Words in capitals such as PASS, IN_GRACE or TECHNICALLY_OBSERVED are exact values used in the code and the database. Thresholds marked [C-asm] are assumed demonstration values, not actuarially derived numbers, following the provenance rule used in Part 1. The glossary is in Section 17.");

// ================================================================= 2
H1("2. The problem and the one rule");
H2("2.1 Why an insurer wants live monitoring");
P("A cyber insurer prices a policy from what it knows about the company's security. In practice most of that comes from a proposal form the company fills in about itself. Woods et al. studied these forms and found they rely on self-assessment [5]. During the ransomware years insurers responded by making some controls a condition of cover: multi-factor authentication, endpoint protection, backups and patching became warranties, and a claim could be reduced if they were missing when an incident happened [6].");
P("A warranty only works if someone can tell whether it is being kept. A form signed on the first day says nothing about month seven. NIST calls the alternative information security continuous monitoring: maintaining ongoing awareness of whether controls are in place and working [1]. That is the job of the agent. It runs on every laptop, desktop and server of the insured company, reads the actual state of the security controls, and reports it in a form the insurer can trust.");
H2("2.2 The rule both parts keep");
P("**Monitoring never re-prices a bound policy.** The premium is calculated once, at inception, by Engine B in the Beretta platform, and it is fixed when the policy is bound. After that, monitoring data can only change the state of a warranty. A warranty state changes what a claim may pay under the policy wording; it does not change what the policy costs.");
P("There are three reasons for the rule. A premium that moves every hour is not a price the insured can budget for or the insurer can file. Re-pricing on a single bad day would punish a company for being monitored, which discourages monitoring. And keeping the two apart makes the system easier to audit: every rupee of the premium traces back to one calculation record, and every warranty change traces back to one observation. The code enforces the rule: no part of the collector or the link writes to a premium, the platform's response to every roll-up carries `repricing_performed: false`, and tests check that a premium stays byte-for-byte the same while warranties move (Sections 12 and 13).");
H2("2.3 What a warranty means here");
P("A warranty is a control the insured promises to keep in place while the policy runs. Beretta has five, all evaluated by the platform after bind:");
table("The five warranties", ["Platform control", "Fed by agent check", "Grace", "Consequence if breached (illustrative)"], [
  ["CTRL-PATCH-CRIT  Critical patching", "PATCH", "14 days", "Claims arising from unpatched critical CVEs subject to co-insurance"],
  ["CTRL-EDR  Endpoint detection & response", "EDR", "7 days", "Incident-response deductible doubled"],
  ["CTRL-BACKUP-TESTED  Tested backups", "BACKUP (sent as partial)", "7 days", "Data-restoration sub-limit reduced by 50%"],
  ["CTRL-MFA  Multi-factor authentication", "none (not observable from an endpoint)", "7 days", "Ransomware & cyber-extortion cover suspended"],
  ["CTRL-AGENT-COVERAGE  Live monitoring coverage", "MONITORING_COVERAGE", "14 days", "Unmonitored endpoints treated as non-compliant with every warranty"],
], [2900, 2200, 900, 3026]);
P("Every consequence shown by the system carries the label ~Prototype coverage-condition evaluation; final claim determination remains subject to policy wording and authorized claims handling.~ The consequences show how a warranty breach could matter; they are not policy wording.");

// ================================================================= 3
H1("3. The whole system at a glance");
figure("link_fig1_architecture.png", "The three parts. Agents report to the collector; the collector sends one signed roll-up per company to the Beretta platform, which records it as evidence and runs the only warranty state machine. Warranty states are read back for display.");
P("There are three programs, each with one job:");
B([
  "**The agent** runs on each insured machine. It reads security settings, never changes them, and sends signed reports. It has no window; it runs as a background service.",
  "**The collector** is run by the insurer. It checks every report, keeps each machine's latest results, decides whether a machine has gone quiet, and combines the machines into one result per control for the whole company. It has its own web dashboard.",
  "**The Beretta platform** (Part 1) holds the company, the quote, the policy and the warranties. It treats the collector's roll-up as the strongest kind of evidence. Before bind that evidence feeds the quote; after bind it drives the warranties only.",
]);
table("Who owns what", ["Agent (each machine)", "Collector (insurer)", "Beretta platform (insurer)"], [
  ["Reading 12 controls from the OS", "Agent identities and secrets", "Companies, quotes, policies"],
  ["Deciding PASS / FAIL per check", "Checking every report (signature, sequence, time)", "Evidence resolution (Engine A)"],
  ["Scheduling, change detection, heartbeats", "Storing reports unchanged", "Pricing at inception (Engine B)"],
  ["Signing and queueing reports", "Liveness: ONLINE, UNVERIFIED, SILENT", "Binding"],
  ["Sending over pinned HTTPS", "Fleet roll-up (95% rule), coverage (90% rule)", "The warranty state machine"],
  ["Keeping a local copy of what it sent", "Pushing a signed roll-up to the platform", "Audit trail of every decision"],
], [3000, 3013, 3013]);
figure("guide_fig_one_check.png", "The path of one check, used as the running example in this guide: Defender's real-time protection is switched off on one of five machines, and the platform's EDR warranty moves to IN_GRACE. Each row is one part of the system; each box is a section of this guide.");
P("Table 3 collects the numbers that come up most often. Each is explained where it is used.");
table("Numbers worth remembering", ["What", "Value", "Where it is set"], [
  ["Checks per machine", "12 (4 warranty, 6 important, 2 regulatory)", "agent `policy.json`"],
  ["Result statuses / assurance levels", "5 / 4", "agent `checks/base.py`"],
  ["Check intervals", "EDR 60 min; PATCH and BACKUP 4 h; others 24 h; ±10% jitter", "`policy.json`"],
  ["Full snapshot / heartbeat / service tick", "every 24 h / every 15 min / every 30 s", "agent config and loop"],
  ["Report size limit", "1 MB at the collector (agent trims evidence above 900 kB)", "collector settings"],
  ["Clock skew / oldest report accepted", "5 minutes into the future / 30 days old", "collector settings"],
  ["Rate limit", "30 requests per minute per agent (enrollment: per IP address)", "collector settings"],
  ["Outbox size", "10,000 reports; heartbeats dropped first", "agent `spool.py`"],
  ["Liveness", "ONLINE up to 6 h quiet, UNVERIFIED up to 72 h, then SILENT", "collector settings [C-asm]"],
  ["Silent machines", "last result FAIL: counts as FAIL; last result PASS: left out of the roll-up for up to 14 days, then FAIL", "collector settings [C-asm]"],
  ["Fleet pass rule", "at least 95% of observing hosts pass", "collector settings [C-asm]"],
  ["Coverage rule", "at least 90% of declared endpoints reporting; 14-day roll-out window", "collector settings [C-asm]"],
  ["Link to platform", "re-evaluated every 30 s or on each report; pushed on change or every 15 min", "collector settings"],
  ["Platform roll-up checks", "sent_at within 5 min; sequence must increase", "platform `fleet.py`"],
  ["Grace periods", "PATCH 14 d, EDR 7 d, BACKUP 7 d, MFA 7 d, coverage 14 d", "platform catalogue [C-asm]"],
  ["Tests", "Part 2: 155; Part 1: 32; integration: 1", "Section 12"],
], [2900, 3900, 2226]);

// ================================================================= 4
H1("4. The agent, from the bottom up");
P("The agent is about 2,500 lines of standard-library Python in ten layers (Fig. 3). Each layer talks only to the layers next to it. That is what lets the lower layers be tested without a real Windows machine and the upper layers without a network.");
figure("fig2_agent_layers.png", "Agent layers, from the operating system (1) up to the network (10).", 560);

H2("4.1 Layer 1: what is read on each operating system");
P("The policy groups the twelve checks into three tiers. **Warranty** checks feed the platform's warranties. **Important** checks are security hygiene: they feed the quote and the dashboards, but no warranty. **Regulatory** checks cover two CERT-In obligations of April 2022 that apply to Indian entities in scope: keep logs for 180 days, and synchronise clocks to the national time servers [2].");
table("Where each check reads from", ["Control (tier)", "Windows", "Linux", "macOS"], [
  ["PATCH (warranty)", "Windows Update Agent COM search for missing software updates; Get-HotFix for the last install", "`apt-get -s upgrade` and dpkg.log; or `dnf --cacheonly updateinfo --security`", "`softwareupdate -l`"],
  ["EDR (warranty)", "process list + Get-MpComputerStatus (engine mode, real-time, signature age)", "/proc process list; `mdatp health` if present", "`ps` process list"],
  ["BACKUP (warranty)", "agent marker file; Get-WBSummary; backup software processes", "marker file; backup processes", "marker file; `tmutil latestbackup`"],
  ["MFA (warranty)", "not observable: always NOT_SUPPORTED", "same", "same"],
  ["DISK_ENCRYPTION", "Get-BitLockerVolume on the system drive; `manage-bde` fallback", "`lsblk`: a dm-crypt layer under /", "`fdesetup status`"],
  ["FIREWALL", "Get-NetFirewallProfile: all three profiles", "ufw, firewalld, nftables, iptables", "Application Firewall"],
  ["EXPOSED_SERVICES", "Get-NetTCPConnection -State Listen", "/proc/net/tcp and tcp6", "`netstat -anv`"],
  ["REMOTE_ACCESS", "registry: RDP enabled, NLA required", "`sshd -T`, or sshd_config with Include files", "sshd_config, if SSH is listening"],
  ["ADMIN_ACCOUNTS", "Administrators group (SID S-1-5-32-544), Guest (RID 501)", "sudo/wheel/admin groups, extra UID 0 accounts", "`dscl` admin group"],
  ["OS_SUPPORT", "registry build number against a lifecycle table", "/etc/os-release against a lifecycle table", "macOS major version"],
  ["LOG_RETENTION (regulatory)", "oldest Security (or System) event; log forwarder process", "oldest /var/log file or journal entry; forwarder or rsyslog forwarding", "forwarder process only"],
  ["TIME_SYNC (regulatory)", "`w32tm /query /status` + W32Time registry", "timedatectl, chronyc, chrony/timesyncd/ntp config", "`systemsetup`"],
], [2300, 2500, 2350, 1876]);
P("Windows and Linux are the primary platforms; macOS is best effort. MFA is in the list even though no endpoint can see it, because MFA is enforced by the identity provider (Microsoft Entra ID, Google Workspace), not by a laptop. Reporting NOT_SUPPORTED with guidance on what to upload is more honest than guessing.");
H3("The decision rule for each check");
P("Table 5 gives the exact rule each check applies. These rules live in `verdicts.py`, one small function per check, separate from the code that collects the facts.");
table("Pass and fail rules", ["Check", "PASS when", "FAIL when", "Other outcomes"], [
  ["PATCH", "no security updates pending; or some pending but last patch within 30 days", "updates pending and last patch older than 30 days or never seen; or Linux package index older than 14 days", "ERROR if the update tool fails"],
  ["EDR", "Defender is the active engine, real-time on, signatures at most 3 days old (OPERATING); or a known third-party EDR process runs (RUNNING)", "Defender present but passive, real-time off or signatures stale (PRESENT); no known product at all (ABSENT)", "Product self-reports unhealthy (mdatp) is FAIL"],
  ["BACKUP", "last successful backup within 7 days", "last success older than 7 days", "NOT_SUPPORTED if no timestamp is readable (backups may run centrally)"],
  ["MFA", "never", "never", "always NOT_SUPPORTED"],
  ["DISK_ENCRYPTION", "system drive encrypted, protection on", "not encrypted; or encrypted with protection suspended", "NOT_SUPPORTED if BitLocker is not available or root is not on a local disk"],
  ["FIREWALL", "Windows: Domain, Private and Public profiles all on; Linux: ufw active, firewalld running, or an input chain that drops", "any Windows profile off; Linux input accepts everything", "NOT_SUPPORTED if the state needs root"],
  ["EXPOSED_SERVICES", "no critical port listening on a network interface (review ports noted)", "FTP, Telnet, VNC, Redis, Elasticsearch, Memcached or MongoDB listening", "loopback-only listeners are ignored"],
  ["REMOTE_ACCESS", "RDP with Network Level Authentication; SSH with keys only and no root password login", "RDP without NLA; SSH allowing passwords, root login or empty passwords", "NOT_APPLICABLE if RDP/SSH is off"],
  ["ADMIN_ACCOUNTS", "at most 3 local administrators, Guest off, no extra UID 0", "more than 3 admins, Guest enabled, or extra UID 0 accounts", "names leave the machine only as salted hashes"],
  ["OS_SUPPORT", "vendor support continues (warning within 90 days)", "end of support has passed", "NOT_SUPPORTED if the build is not in the table"],
  ["LOG_RETENTION", "logs forwarded off-host (RUNNING); or local logs cover 180 days (OPERATING)", "logging off; or under 180 days and no forwarder", "macOS: NOT_SUPPORTED without a forwarder"],
  ["TIME_SYNC", "synchronised to samay1.nic.in, samay2.nic.in or time.nplindia.org; or following a Windows domain", "not synchronised; no source; or another source", ""],
], [2000, 2750, 2750, 1526]);
P("Three rules need a word of explanation. **Patching** allows pending updates within a normal monthly cycle, because a machine is never at zero pending for long; the 14-day index rule stops a Linux machine that never refreshes its package list from reporting \"0 pending\" forever. **Exposed services** cannot tell whether a port is reachable from the internet, only that it listens on a network interface, so RDP, SMB, SSH and database ports pass with a \"review\" note and only clear-text or usually-unauthenticated services fail. **Time sync** accepts a Windows machine that follows its domain controller, with a note asking the insured to confirm the domain controller syncs to NIC or NPL.");

H2("4.2 Layer 2: collector functions");
P("Each OS has its own file (`windows.py`, `linux.py`, `macos.py`) with one function per check. These functions are the only code that touches the operating system. Every OS command goes through one helper, `run_cmd`, which enforces four rules in one place:");
B([
  "**No shell.** Commands are lists of arguments; a string is refused and `shell=True` is never used. No input from anywhere can turn into command injection.",
  "**A timeout on every call.** A hung command becomes an ERROR result, not a stuck agent.",
  "**The C locale.** `LC_ALL=C` makes output parse the same on any language setting.",
  "**No console window.** On Windows, `CREATE_NO_WINDOW` stops a black window flashing on the user's screen.",
]);
P("Where Python can read a value directly, no process is started at all: Linux processes and listening sockets come from `/proc`, and Windows registry values (RDP settings, OS build, time service) come from the standard `winreg` module. The commands that do run are read-only by construction: PowerShell `Get-*` cmdlets, `apt-get -s` (simulate only), `dnf --cacheonly`. Two exceptions turn into statuses rather than errors: a missing tool raises `ToolMissing`, and a permission problem raises `NeedsPrivilege`. Both become NOT_SUPPORTED in Layer 6.");

H2("4.3 Layer 3: parsers");
P("Parsers turn raw command output into plain facts, and never touch the OS. That is why they can be tested on a Linux build machine using output captured from Windows and macOS (36 tests). Some cases they handle:");
B([
  "PowerShell's `ConvertTo-Json` turns a one-item list into a single object. The Windows Update, firewall and listener parsers accept both shapes.",
  "BitLocker status comes back as a word (\"On\") or a number (1) depending on the PowerShell version.",
  "Windows timestamps can have seven decimal places, which Python rejects; the parser trims them.",
  "OpenSSH uses the **first** value it sees for a setting. On Ubuntu cloud images an included file near the top often sets `PasswordAuthentication yes`, silently overriding a `no` further down. The parser expands Include files in place and applies first-value-wins, so it reports what sshd actually does.",
  "IPv6 addresses in `/proc/net/tcp6` are stored as four little-endian 32-bit words.",
]);

H2("4.4 Layer 4: verdicts");
P("A verdict function takes the facts and the policy's thresholds and returns four things: a status, an assurance level, a one-line summary, and the evidence behind it. Keeping the rule apart from the data collection means each rule can be read, cited and tested on its own (29 tests).");
table("Result status: did the control hold on this machine?", ["Status", "Meaning", "Example"], [
  ["PASS", "observed, and meets the threshold", "Defender active, signatures 1 day old"],
  ["FAIL", "observed, and does not meet the threshold", "Firewall Public profile off"],
  ["NOT_APPLICABLE", "the control does not apply here", "no SSH server installed"],
  ["NOT_SUPPORTED", "cannot be observed from this machine", "MFA; BitLocker without admin rights"],
  ["ERROR", "the check itself failed", "timeout, crash, unreadable output"],
], [2100, 3600, 3326]);
table("Assurance level: how strongly was the control seen working?", ["Level", "Meaning", "Example"], [
  ["OPERATING", "running, and a health signal confirms it works", "Defender active, real-time on, current signatures"],
  ["RUNNING", "running or configured; effectiveness not checkable locally", "CrowdStrike process seen; logs forwarded to Wazuh"],
  ["PRESENT", "installed but not effective", "Defender with 9-day-old signatures; BitLocker suspended"],
  ["ABSENT", "not found", "no anti-malware process at all"],
], [1700, 3700, 3626]);
P("Assurance is how the agent follows a Part 1 rule: the presence of a tool is not a working control. A Defender with stale signatures is FAIL with assurance PRESENT, never a PASS.");

H2("4.5 Layer 5: the policy file");
P("`policy.json` decides which checks run, how often, and with what thresholds. It is data, not code. The list of things the agent knows how to check is fixed in the program (the check registry in `checks/__init__.py`); the policy can only choose from that list and set numbers. When the policy loads it is validated:");
B([
  "every check id must exist in the registry: **a policy cannot introduce a new check**;",
  "no duplicate ids; the tier must be warranty, important or regulatory; a control name is required;",
  "intervals must be whole minutes, at least 5;",
  "parameters may only contain plain data (text, numbers, true/false, lists, objects).",
]);
P("This is the agent's guarantee against remote code execution: nobody, including the insurer, can make an insured machine run new code by changing the policy. The policy is hashed (SHA-256 of its canonical JSON) and the hash goes into every report, so the collector can tell exactly which rules produced each result. Every threshold that is an assumption carries a provenance tag.");
table("Thresholds and where they come from", ["Setting", "Value", "Provenance"], [
  ["Patch cycle / package index age", "30 days / 14 days", "C-asm"],
  ["EDR signature age", "3 days", "C-asm"],
  ["Backup age", "7 days", "C-asm"],
  ["Local administrators", "at most 3", "C-asm"],
  ["Log retention", "180 days", "CERT-In Directions, 28 Apr 2022 [2]"],
  ["Approved time sources", "samay1/samay2.nic.in, time.nplindia.org", "CERT-In Directions [2]"],
  ["OS end-of-support dates", "per OS and build, incl. Windows 11 26H2 (build 26300)", "vendor lifecycle pages [10], [11]; table dated 27 Oct 2026"],
], [3000, 3300, 2726]);

H2("4.6 Layer 6: the runner");
P("The runner picks the right function for the platform and runs each check in its own thread with a time budget (60 seconds by default, 300 for PATCH, plus 5 seconds of slack). Nothing a check does can stop the agent:");
table("How the runner turns problems into statuses", ["What happens", "Result"], [
  ["The check needs admin rights it does not have", "NOT_SUPPORTED, evidence marks requires_admin"],
  ["A required OS tool is not installed", "NOT_SUPPORTED"],
  ["An OS command times out", "ERROR"],
  ["Python exception (bug or unexpected output)", "ERROR, with the exception type"],
  ["The check runs past its budget", "ERROR; the thread is abandoned and the agent moves on"],
  ["No implementation for this OS", "NOT_SUPPORTED"],
], [4600, 4426]);
P("The runner also supplies a salt (the agent's own id) used to hash account names: `SHA-256(agent_id:name)`, first 12 hex characters. Administrator names therefore never leave the machine, and the same name on two companies' machines gives different hashes.");

H2("4.7 Layer 7: the scheduler");
P("The service loop wakes every 30 seconds (one ~tick~). On each tick it runs whatever checks are due, decides what to send, and tries to send it. There are three kinds of report:");
B([
  "**Full snapshot**: every check result. Sent at the first run and then once every 24 hours.",
  "**Delta**: only the results that changed since the last time that check ran. \"Changed\" means a different status, assurance or summary (a fingerprint of the three); timestamps and run times do not count, so an unchanged machine sends nothing.",
  "**Heartbeat**: no results at all, every 15 minutes. It proves the machine is alive, which matters for the silence rule (Section 5.5).",
]);
table("Check intervals", ["Checks", "Interval", "Why"], [
  ["EDR", "60 minutes", "the warranty most likely to change and the cheapest to read"],
  ["PATCH, BACKUP", "4 hours", "the Windows Update search is slow; backups run daily"],
  ["All others", "24 hours", "configuration settings rarely change"],
], [2400, 1800, 4826]);
P("Each interval gets ±10% random jitter, so 500 laptops do not all report in the same second after a power cut. **On-demand re-check:** `kyh_agent scan-now [--control EDR]` leaves a small request file in the agent's state folder. The running service picks it up at its next tick, re-checks only the named controls (or everything), and sends the result at once. The service stays the only process that scans and sends, so the sequence numbers stay in order. This is what the demonstration uses to show a change within a minute instead of waiting for the next interval.");

H2("4.8 Layer 8: the envelope and its signature");
P("Every report is a JSON envelope. A shortened example from the running example (Fig. 2):");
code([
  "{ \"schema_version\": 2, \"kind\": \"delta\", \"agent_id\": \"ag_7d1c09a2e4b6f318\", \"seq\": 42,",
  "  \"created_at\": \"2026-10-27T09:41:54Z\",",
  "  \"agent\":  { \"version\": \"2.0.0\", \"build_hash\": \"4c68...3448\", \"platform\": \"windows\",",
  "              \"hostname\": \"KAL-ACCT-VM01\", \"os\": \"Windows (10.0.26300)\" },",
  "  \"policy\": { \"id\": \"kyh-endpoint-baseline\", \"version\": \"2.0.0\", \"hash\": \"31f4...19e1\" },",
  "  \"simulated\": false, \"queue_depth\": 0,",
  "  \"results\": [ { \"check_id\": \"edr.running_healthy\", \"control\": \"EDR\", \"tier\": \"warranty\",",
  "      \"status\": \"FAIL\", \"assurance\": \"PRESENT\",",
  "      \"summary\": \"Microsoft Defender present but real-time protection off\",",
  "      \"evidence\": { \"defender\": { ... }, \"max_signature_age_days\": 3 },",
  "      \"method\": \"Get-Process + Get-MpComputerStatus\", \"observed_at\": \"2026-10-27T09:41:50Z\",",
  "      \"platform\": \"windows\", \"duration_ms\": 1840 } ] }",
]);
P("The `os` field is only a label from Python's platform module (older Python versions call Windows 11 \"Windows 10\"). The OS_SUPPORT check reads the real edition and build from the registry. The envelope is written in one fixed form (sorted keys, no spaces) and signed:");
B([
  "**Signature.** HMAC-SHA256 over the exact bytes, using the agent's 256-bit secret, sent in the header `X-KYH-Signature: v1=<hex>`. If one byte changes on the way, the collector's recomputed signature will not match.",
  "**Sequence number.** It only goes up, and it is stored in the outbox database so it survives restarts and reinstalls of the service. The collector refuses any number it has already seen, which stops an old \"all PASS\" report from being sent again (a replay).",
  "**Build hash.** SHA-256 over every `.py` file of the agent and its policy, in sorted order, with Windows line endings normalised. An edited agent, for example one changed to always return PASS, has a different build hash, and the collector stores its reports but does not trust them.",
  "**Policy hash.** As above, for the rules in force.",
  "**Simulated flag.** True only in simulation mode (Section 4.14).",
]);
P("If an envelope would be larger than 900 kB, the evidence fields are replaced by `{\"truncated\": true}` so the verdicts still get through under the collector's 1 MB limit.");

H2("4.9 Layer 9: the outbox");
P("Every report is written to a small SQLite database on the machine (`outbox.db`) before it is sent. If the laptop is offline, on a train or behind a hotel login page, reports wait in order with their original timestamps and sequence numbers, and are replayed when the connection returns. The collector accepts reports up to 30 days old. Up to 200 waiting reports are sent per tick. The outbox holds at most 10,000 reports; when it is full, the oldest heartbeats go first, then the oldest deltas, and full snapshots are kept longest.");
table("How the agent reacts to each answer", ["Collector answer", "Agent action"], [
  ["202 Accepted", "remove from the outbox"],
  ["409 REPLAY", "remove: the collector already has it (the first answer was lost)"],
  ["any other 4xx (bad signature, bad schema, unknown agent)", "move to a dead-letter table so it cannot block the queue"],
  ["429 or 5xx, or no connection", "keep it; back off 30 s, doubling up to 15 minutes; retry"],
], [3900, 5126]);

H2("4.10 Layer 10: transport");
P("Reports go over HTTPS with TLS 1.2 or newer. At install the agent is given the collector's own certificate authority file, `ca.pem`, and it trusts **only** that authority. A fake collector with a certificate from a public authority, or a network device that intercepts TLS, is refused. Plain HTTP is allowed only to localhost, for development. Requests to localhost or private addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x) skip any system proxy, because a proxy cannot reach them; this was found while testing the VM set-up, where Python would otherwise have sent the VM's reports to the proxy.");

H2("4.11 Enrollment, from the agent's side");
P("A new machine has no identity. The installer runs `kyh_agent enroll` with the collector's address, the CA file and a one-time **enrollment token** from the insurer. The agent sends the token with its hostname, OS, version, build hash and policy hash. The collector answers with an **agent id** (`ag_` plus 16 hex characters) and a random 256-bit **secret**, and its own clock time. The agent writes these to `config.json`, created with owner-only permissions (on Windows the folder is limited to SYSTEM and Administrators). If the two clocks differ by more than 5 minutes the agent prints a warning, because timestamps are evidence and the collector rejects reports from more than 5 minutes in the future.");

H2("4.12 Running as a service");
table("How the agent runs on each OS", ["", "Windows", "Linux", "macOS"], [
  ["Runs as", "scheduled task \"KYH Live Monitoring Agent\", as SYSTEM, at start-up, restarts every minute if stopped", "systemd service `kyh-agent`, restart after 30 s", "launchd daemon `com.kyh.agent`"],
  ["Code", "C:\\Program Files\\KYH\\Agent", "/opt/kyh-agent", "/Library/KYH/Agent"],
  ["Config and state", "C:\\ProgramData\\KYH\\Agent (SYSTEM and Administrators only)", "/etc/kyh-agent (0700), /var/lib/kyh-agent", "/Library/Application Support/KYH/Agent (0700)"],
  ["Installer", "install.ps1 (elevated)", "install.sh (root)", "install.sh (root)"],
], [1500, 2700, 2600, 2226]);
P("**Why a scheduled task and not a Windows service:** a native service needs `pywin32` or a wrapper program, and the agent has no third-party dependencies. A packaged service is listed as future work. **Why root on Linux:** some checks need it (firewall rules, `sshd -T`, the full process list). The systemd unit limits the damage: the whole filesystem is read-only to the agent except its own state folder, home folders are read-only, it cannot gain new privileges, and it is capped at 5% CPU and 150 MB of memory with idle I/O priority.");
table("Files the agent keeps", ["File", "Contents"], [
  ["config.json", "server address, CA path, agent id and secret (owner-only)"],
  ["state.json", "last results, next due time per check, fingerprints, next full snapshot and heartbeat"],
  ["outbox.db", "the outbox, the dead-letter table and the sequence counter"],
  ["sent.jsonl", "one line per report sent, with the status of every check: what left the machine"],
  ["agent-errors.log", "any error that reached the service loop"],
  ["backup-last-success", "optional marker a backup job writes after each successful run"],
  ["ca.pem", "the collector's certificate authority (Windows and Linux installs)"],
], [2600, 6426]);

H2("4.13 The command line");
table("Agent commands (python -m kyh_agent ...)", ["Command", "What it does"], [
  ["enroll --server --token --ca-file [--hostname]", "one-time registration with the collector"],
  ["run", "service mode; what the service manager starts"],
  ["once [--no-send] [--json]", "run every check now and print the table (or the full envelope)"],
  ["scan-now [--control X] [--wait N]", "ask the running service to re-check now; with --wait, print the new results"],
  ["status", "last results and how many reports are waiting"],
  ["show-policy", "what is checked, how often, and what is never collected"],
  ["build-info", "version, build hash and policy hash, for the insurer to approve"],
], [3600, 5426]);
P("This answers the question \"does the agent have a visual interface?\": not on the insured machine. There is no window or tray icon, deliberately: an icon can be closed by the person whose machine is being checked, and a GUI is extra code running with high privileges. Administrators use the commands above. The insurer sees the collector's web dashboard and the platform's Monitoring tab.");

H2("4.14 Simulation mode");
P("`--simulate <profile>` replaces the real checks with scripted results so a presentation can show a failure without breaking a real machine. Profiles: `healthy`, `edr_down`, `edr_stale`, `patch_overdue`, `backup_stale`, `mixed`. Simulation is always labelled: every summary starts with \"[SIMULATED]\", every result's evidence has `simulated: true`, and the envelope is flagged. The collector counts simulated results only for companies created in demo mode; for any other company they are stored and ignored. The linked demo uses four simulated machines and, optionally, one real Windows VM.");
// ================================================================= 5
H1("5. The collector");
P("The collector is a standard-library Python web server (about 1,700 lines with its dashboard) run by the insurer. It does five things: enrolls agents, checks and stores reports, works out each machine's state, rolls machines up into one result per control for the company, and, in linked mode, pushes that result to the Beretta platform.");
H2("5.1 What it stores");
table("Collector database (SQLite, collector.db)", ["Table", "Holds"], [
  ["companies", "insured companies, declared endpoint count from the proposal, demo flag, link to the platform company"],
  ["enrollment_tokens", "SHA-256 of each token, company, expiry, uses allowed and used"],
  ["agents", "one row per machine: id, secret, hostname, OS, last sequence number, last seen, build and policy hash and whether each is approved, retired flag"],
  ["reports", "every accepted report exactly as received, its SHA-256, kind, evidence strength; never edited"],
  ["observations", "one row per check result in every report (append-only history)"],
  ["results_current", "the latest result per machine and check (what the roll-up reads)"],
  ["approved_builds / approved_policies", "agent build hashes and policy hashes the insurer trusts"],
  ["admin_tokens", "SHA-256 of dashboard admin tokens"],
  ["audit_log", "enrollments, rejected reports, approvals, retirements, links"],
  ["policies, warranties, warranty_events", "the stand-alone state machine (Section 5.9); not used for linked companies"],
  ["platform_state, platform_meta", "linked mode: last push, its sequence number, what was sent and what the platform answered"],
], [3000, 6026]);
P("Reports and observations are append-only. A correction is simply a newer report. A late-arriving old report (from an outbox replay) is stored in the history but never overwrites a newer current result.");

H2("5.2 Enrollment");
P("The insurer creates an enrollment token for a company with a limit on uses and an expiry (`issue-token --max-uses 45 --days 14` for a 40-machine fleet, for example). The token looks like `kyh_enr_...`; only its SHA-256 is stored. When an agent presents it, the collector checks it exists, has not expired and has uses left; then it creates the agent id and a random 256-bit secret (`secrets.token_hex(32)`), records whether the agent's build and policy hashes are approved, counts one use, writes an audit row, and answers 201 with the id, secret, company and its clock time. Enrollment is rate-limited per IP address (30 a minute), and a wrong token is audited.");

H2("5.3 The ingest gate");
P("Every report goes through a fixed sequence of checks before anything is stored (Fig. 4). The order matters: the signature is checked before the body is parsed, so a sender without the agent's secret cannot even reach the JSON parser.");
figure("fig3_ingest.png", "The ingest gate. Each check must pass before the next runs; the report is stored only at the end.");
table("Ingest checks in order, and the answer when one fails", ["#", "Check", "Rejected with"], [
  ["0", "Rate limit: at most 30 reports a minute from this agent", "429 RATE_LIMIT"],
  ["1", "Body at most 1 MB", "413 TOO_LARGE"],
  ["2", "Agent id known and not retired", "401 UNKNOWN_AGENT"],
  ["3", "HMAC-SHA256 signature matches the exact body (constant-time compare)", "401 BAD_SIGNATURE, audited"],
  ["4", "Valid JSON; schema_version 2; agent id inside equals the header", "400 BAD_JSON / SCHEMA_VERSION / AGENT_MISMATCH"],
  ["5", "Sequence number is a positive integer and higher than the last one stored", "400 BAD_SEQ; 409 REPLAY, audited"],
  ["6", "created_at valid, not more than 5 minutes in the future, not older than 30 days", "400 BAD_TIMESTAMP / FUTURE_TIMESTAMP / TOO_OLD"],
  ["7", "kind is full, delta or heartbeat; each result has a known status and safe ids", "400 BAD_KIND / BAD_RESULT"],
  ["-", "Accepted: stored, evaluated", "202, with repricing_performed: false"],
], [500, 5800, 2726]);
P("Ingestion runs under a lock, one report at a time, so two reports cannot race past the sequence check. Rejections for a bad signature or a replay are committed to the audit log even though the report itself is refused.");

H2("5.4 How much a result is trusted");
P("Each accepted report is labelled with an evidence strength, and only some labels count:");
table("Evidence strength of a stored report", ["Label", "When", "Counts?"], [
  ["TECHNICALLY_OBSERVED", "approved build hash and approved policy hash", "yes"],
  ["SIMULATED", "the envelope says simulated", "only for demo-mode companies"],
  ["UNTRUSTED_BUILD", "build hash not on the approved list", "no (stored, shown, ignored)"],
  ["UNTRUSTED_POLICY", "policy hash not on the approved list", "no (stored, shown, ignored)"],
], [2700, 4000, 2326]);
P("TECHNICALLY_OBSERVED is the top step of the Part 1 evidence ladder: declared 0.60, documented 0.80, tested 0.90, technically observed 1.00. When the insurer approves a new release (`approve-build`), the collector marks every agent already on that hash as trusted.");

H2("5.5 Liveness: the silence rule");
figure("fig6_liveness.png", "The silence rule.");
P("Each machine is ONLINE, UNVERIFIED or SILENT according to how long it has been quiet since its last message (any message counts, including a heartbeat). Up to 6 hours it is ONLINE. Up to 72 hours it is UNVERIFIED: its last results are kept and flagged, and nothing changes. After 72 hours it is SILENT, and what that means depends on the **last result it sent** for each control:");
B([
  "**Last result FAIL:** the machine keeps counting as failing that control. Going quiet can never hide a failure.",
  "**Last result PASS:** the machine is left out of the roll-up for that control (status SILENT_PASS) for up to **14 days** of silence, then counts as failing.",
  "**No trusted result at all:** counts as failing.",
  "**Controls it could never observe**, such as MFA, are left alone.",
]);
P("The rule has two jobs. It closes the most obvious way to cheat: take a failing machine off the network or uninstall the agent. Its last result was FAIL, so it stays FAIL. And it does not punish ordinary absence. If 10 of a company's 100 laptops are switched off for 10 days of leave, they were passing when they went quiet, so they are left out; the other 90 decide the result (90 of 90 pass), and no warranty moves. An earlier version counted every silent machine as failing, which would have put that company in grace on day 3 of every holiday.");
P("Two limits stop the exclusion being abused. After 14 days of silence a machine counts as failing even if it was passing [C-asm]. And silent machines never count as reporting for the coverage rule (Section 5.8), so a company cannot take more than 10% of its declared machines quiet at once without the coverage warranty failing. One gap remains, and it should be stated if asked: a machine that was passing, was cut off from the network, and then had a control switched off while disconnected is left out rather than failed until it reconnects (its queued reports then arrive) or reaches 14 days. In linked mode the link worker re-evaluates every 30 seconds, so these changes happen on time even if no other machine reports.");

H2("5.6 From check results to a machine's control status");
P("One control can have more than one check behind it on a machine. The collector picks one status per machine and control, using only results it trusts:");
N([
  "If the machine is SILENT and it could observe the control: FAIL if its last result was FAIL or it has no trusted result; SILENT_PASS (left out of the roll-up) if its last result was PASS and it has been quiet for at most 14 days; FAIL after that.",
  "If there is no trusted result, the status is NO_DATA.",
  "Otherwise the first of these that appears wins: FAIL, PASS, ERROR, NOT_SUPPORTED, NOT_APPLICABLE. One failing check fails the control on that machine.",
]);

H2("5.7 The fleet roll-up");
figure("fig4_rollup.png", "From one check result to a company result.");
P("For each control, only machines whose status is PASS or FAIL count as ~observing~ it; SILENT_PASS machines are left out and named in the reason. The control passes for the company if **at least 95% of observing machines pass**. With 40 machines, two may fail and the company still passes; with five machines, one failing machine gives 80% and the company fails. If no machine can observe a control, its status is NOT_OBSERVABLE: missing evidence is reported as missing, not as a failure, and no warranty moves on it. MFA is always in that position.");
P("Why 95% and not 100%: in a fleet of hundreds there is nearly always one machine mid-update or just back from leave. A 100% rule would keep warranties in grace permanently, and a warranty that is always failing stops meaning anything. The value is an assumption [C-asm] that an underwriter would set per account.");

H2("5.8 Monitoring coverage");
P("A company could also enroll only its five best machines. The coverage rule closes that gap: the number of machines **reporting** (enrolled, has reported at least once, not SILENT) must be at least 90% of the endpoint count the company declared on its proposal. For 40 declared machines that means 36. For the first 14 days after bind the rule is not enforced (status NOT_OBSERVABLE), so the company's IT team has time to roll the agent out. Coverage becomes the platform warranty CTRL-AGENT-COVERAGE.");

H2("5.9 The stand-alone warranty state machine");
P("The collector has its own warranty state machine for companies that are **not** linked to a platform (for example when Part 2 is shown on its own). For linked companies it is switched off completely, and the platform's states are shown instead (Section 6.8). It is included here because the code exists and a panel may ask.");
figure("fig5_states.png", "The collector's stand-alone state machine. A fix must hold for 24 hours before REMEDIATED returns to MET.");
P("It differs from the platform's machine in one way: after a fix the warranty waits in REMEDIATED for 24 hours before returning to MET, so a control that flaps every hour cannot keep resetting its grace period. A failure during those 24 hours is a regression and starts a fresh grace period. Grace expiry is checked every time the company is evaluated (on each report and each dashboard load), so no separate scheduler is needed.");

H2("5.10 The dashboard and API");
figure("p2_linked_top.png", "The collector dashboard for a linked company. The premium and warranty states are read back from the Beretta platform; the collector does not run its own state machine for this company.", 600);
P("The dashboard is a single page (vanilla HTML, CSS and JavaScript) served by the collector. After sign-in with the admin token it lists the insured companies; for each company it shows the bound premium, tiles for declared, enrolled, reporting, online, unverified and silent machines, one card per warranty, a table of every control across the fleet with the failing machines named, a machine-by-control matrix, and the event and audit history. Each machine links to a page with every check result, its assurance level, the raw evidence and the list of stored reports with their SHA-256 hashes.");
figure("dash_host.png", "The host page: every check with its assurance level and evidence, and the stored reports.", 520);
P("Hostnames, summaries and evidence come from agents, which are outside the insurer's control, so every value is escaped before display. Pages are served with a Content-Security-Policy that allows only the collector's own scripts and styles and forbids framing, plus `nosniff` and `no-store` headers. The admin token is kept in the browser's session storage only. The page refreshes every 15 seconds (paused while a detail panel is open).");
table("Collector HTTP API", ["Method and path", "Caller", "Purpose"], [
  ["POST /api/v1/enroll", "agent", "exchange a token for an identity and secret"],
  ["POST /api/v1/report", "agent", "submit a signed report"],
  ["GET /api/v1/overview", "dashboard (admin token)", "all companies with coverage and warranty states"],
  ["GET /api/v1/companies/{id}", "dashboard (admin token)", "full company view, events, audit, link status"],
  ["GET /api/v1/agents/{id}", "dashboard (admin token)", "machine detail; the signing secret is never returned"],
  ["GET /healthz", "monitoring", "is the collector itself up"],
], [3100, 2300, 3626]);
table("Collector admin commands (python -m kyh_collector --data DIR ...)", ["Command", "Purpose"], [
  ["init", "create the database; print an admin token once"],
  ["gen-cert --host NAME_OR_IP", "create the private CA and server certificate (openssl, or the cryptography package)"],
  ["add-company --name --declared-endpoints [--demo]", "register an insured company"],
  ["issue-token --company --max-uses --days", "create an enrollment token"],
  ["approve-build / approve-policy --hash", "trust an agent release or policy"],
  ["serve --host --port --tls-cert --tls-key", "run the API and dashboard"],
  ["list", "companies, machines and states in the terminal"],
  ["retire --agent", "take a decommissioned machine out of the fleet (audited)"],
  ["bind --company --premium", "stand-alone mode only: record the premium from Engine B"],
  ["link-platform / link-company / push-now", "linked mode: connect to the platform, map a company, push now"],
], [4300, 4726]);

// ================================================================= 6
H1("6. The link to the Beretta platform");
H2("6.1 Why the platform owns the warranties");
P("Before the two parts were linked, each had its own warranty state machine. With both running, the same company could show EDR as MET on one dashboard and IN_GRACE on the other. The link (called Option B during design) gives each part one job: the collector owns everything about machines, and the platform owns everything about the policy, including the only warranty state machine. The collector sends the platform a signed result per control for each company, and the platform treats it as evidence like any other source.");
H2("6.2 Connecting the two");
N([
  "On the platform's Admin page, register the collector. The platform creates a collector id (`COL-...`) and a 256-bit secret, shown once.",
  "On the collector, run `link-platform --url ... --collector-id ... --secret ...`. This writes `platform_link.json` with owner-only permissions.",
  "On the platform, link the platform company to the collector's company id. On the collector, run `link-company --company co_x --platform-company CO-y`. The collector will now refuse its own `bind` for that company.",
]);
H2("6.3 When the collector pushes");
P("A background thread, the link worker, wakes every 30 seconds, or at once when a report arrives for a linked company. For each linked company it evaluates the fleet, maps the controls (Section 6.4) and computes a hash of what matters: each platform control's value, the coverage status, and each machine's liveness and control statuses. It sends a roll-up when that hash changed, when the last push failed, or when 15 minutes have passed (a heartbeat to the platform). The HTTP call is made outside the database lock so a slow platform cannot hold up agent reports. The platform's answer, including its warranty states, is stored and shown on the collector dashboard.");
H2("6.4 Mapping collector controls to platform controls");
table("Control mapping", ["Collector control(s)", "Platform control"], [
  ["PATCH", "CTRL-PATCH-CRIT (warranty)"],
  ["EDR", "CTRL-EDR (warranty)"],
  ["BACKUP", "CTRL-BACKUP-TESTED (warranty); a PASS is sent as \"partial\""],
  ["MFA", "CTRL-MFA (warranty); never sent, because no machine can observe it"],
  ["DISK_ENCRYPTION", "CTRL-ENCRYPTION"],
  ["FIREWALL, REMOTE_ACCESS, EXPOSED_SERVICES, ADMIN_ACCOUNTS, OS_SUPPORT", "CTRL-SECCONFIG (secure configuration)"],
  ["LOG_RETENTION, TIME_SYNC", "CTRL-LOGGING"],
  ["MONITORING_COVERAGE", "CTRL-AGENT-COVERAGE (monitoring-only warranty)"],
], [5200, 3826]);
B([
  "**Several sources, one control:** if any source fails, the platform control fails; it passes only if at least one source passes and none fails. The failing machines and their reasons are put in the reason text.",
  "**Not observable is not sent:** a source no machine could observe is listed under `not_observed` for that control; a platform control with no observable source is not sent at all. Absence of evidence is never sent as evidence.",
  "**Backup is partial:** the agent can see that a backup ran recently, but not that a restore was tested, and the platform control is \"tested backups\". Sending it as partial gives half the pricing credit before bind and still counts as passing for the warranty.",
]);
H2("6.5 The roll-up message");
code([
  "POST /api/collector/rollup",
  "X-KYH-Collector-Id: COL-b6d39e00e8",
  "X-KYH-Signature: v1=<HMAC-SHA256 of the body>",
  "",
  "{ \"schema\": \"kyh-fleet-rollup/1\", \"collector_id\": \"COL-b6d39e00e8\", \"seq\": 7,",
  "  \"sent_at\": \"2026-10-27T09:42:01Z\", \"evaluated_at\": \"2026-10-27T09:42:01Z\",",
  "  \"company\": { \"collector_company_id\": \"co_kalinga\",",
  "               \"platform_company_id\": \"CO-8367c87375\",",
  "               \"name\": \"Kalinga Components Ltd\", \"declared_endpoints\": 5 },",
  "  \"coverage\": { \"status\": \"PASS\", \"reporting\": 5, \"declared\": 5, ... },",
  "  \"controls\": [",
  "    { \"platform_control_id\": \"CTRL-EDR\", \"status\": \"FAIL\", \"value\": \"false\",",
  "      \"passing\": 4, \"observed\": 5,",
  "      \"reason\": \"EDR: 4/5 observed hosts pass (80%; threshold 95%) ...\",",
  "      \"failing_hosts\": [ { \"host\": \"KAL-ACCT-VM01\",",
  "                         \"reason\": \"... real-time protection off\" } ],",
  "      \"sources\": [ ... ], \"not_observed\": [] }, ... ],",
  "  \"unmapped\": [ ... ],",
  "  \"fleet\": { \"hosts\": [ ... each machine's liveness and statuses ... ] } }",
]);
H2("6.6 What the platform checks");
table("Platform roll-up checks in order", ["Check", "Rejected with"], [
  ["Collector id is registered", "401 UNKNOWN_COLLECTOR"],
  ["HMAC signature over the exact body", "401 BAD_SIGNATURE, audited"],
  ["Valid JSON; schema kyh-fleet-rollup/1; collector id in the body equals the header", "400 / 403 COLLECTOR_MISMATCH"],
  ["Sequence number higher than the last one from this collector", "409 REPLAY, audited"],
  ["sent_at within 5 minutes of the platform's clock", "400 STALE_OR_FUTURE"],
  ["The company is linked to this collector", "403 NOT_LINKED"],
  ["At most 64 controls and 5,000 machines; each control known, status PASS/FAIL, value true/partial/false", "400"],
], [5800, 3226]);
P("A roll-up that passes is stored unchanged (append-only), and a snapshot is kept for the Monitoring tab. Then each control becomes an **observation** in Engine A, with source type AGENT_FLEET and strength TECHNICALLY_OBSERVED, and a locator such as \"Beretta collector roll-up #7 · EDR · 4/5 hosts pass\". A result identical to the last one (same value, same host counts) within 6 hours is not recorded again, so the observation history stays readable. If the policy is bound, the platform then evaluates its warranties and answers with their states and `repricing_performed: false`.");
H2("6.7 Before bind and after bind");
figure("guide_fig_two_jobs.png", "The same roll-up does two different jobs, depending on whether the policy is bound.");
P("**Engine A** keeps every observation for a control and picks the best one: highest evidence strength first, newest second. A fleet result (technically observed, 1.00) therefore outranks the company's questionnaire answer (declared, 0.60) for the same control, and the platform flags the conflict when they disagree.");
P("**Before bind**, Engine B prices from that posture. Each passing control lowers the expected incident frequency by its pricing weight times the evidence multiplier; a partial pass gives half; a failing control adds its failure load in full; a control with no evidence adds an \"unknown\" load. The result is clamped between 0.60 and 1.60 and multiplied into the sector frequency, then into the severity of each coverage head, then the loadings are added. So a fleet that passes EDR earns the full EDR credit, where a questionnaire \"yes\" earns 60% of it. A failing warranty control before bind makes the quote conditionally eligible: remediation or an underwriter override is needed.");
P("**After bind**, the same observations only reach the warranty state machine. The premium was fixed at bind and no code path changes it.");
P("**The monitoring-only control.** CTRL-AGENT-COVERAGE was added to the platform with the link. It is a warranty after bind, but it is marked monitoring-only: it is skipped by the posture modifier, by pre-bind eligibility, by the questionnaire and by the dashboard's average posture. The 15 priced controls and every premium are exactly as before the link.");
H2("6.8 The platform's warranty state machine");
figure("guide_fig_platform_states.png", "The platform's warranty state machine, the only one used for linked companies.");
P("At bind the platform creates one warranty per warranty control, each at MET, and evaluates them straight away, so a control already failing at bind is tracked from day one. After that it re-evaluates on every roll-up (and checks for expired grace periods whenever warranties are read):");
B([
  "**MET or REMEDIATED, and the control fails:** IN_GRACE. The breach time and the grace deadline are recorded.",
  "**IN_GRACE, still failing, deadline passed:** BREACHED. The configured consequence now applies.",
  "**IN_GRACE or BREACHED, and the control passes (or is partial):** REMEDIATED, then MET in the same evaluation.",
  "**No evidence (UNKNOWN):** no change. Absence of a report is not a breach; silence is handled earlier, by the collector, which decides how each silent machine counts (Section 5.5).",
]);
table("The two state machines compared", ["", "Collector (stand-alone)", "Platform (linked; used in the demo)"], [
  ["Used for", "companies not linked to a platform", "every linked company"],
  ["REMEDIATED to MET", "after the fix holds 24 hours", "immediately"],
  ["Grace periods", "collector settings", "platform control catalogue"],
  ["Consequences", "collector settings (illustrative)", "platform catalogue (illustrative)"],
  ["Premium", "never touched", "never touched"],
], [1900, 3300, 3826]);
P("Every transition is stored as a warranty event and an audit entry, so the full history of a warranty (for example MET, IN_GRACE, REMEDIATED, MET) can be shown to an auditor or a claims handler.");
figure("p1_ingrace_cards.png", "The platform's warranty cards after Defender was switched off on one machine: EDR is IN_GRACE with its deadline and consequence; the others are MET.", 560);
figure("link_fig2_sequence.png", "One failure, message by message, from the agent to the platform and back.");

// ================================================================= 7
H1("7. The complete workflow: the life of a policy");
P("This is the whole system from a company's first contact to a claim, in order.");
N([
  "**Proposal.** Kalinga Components applies for cover. It fills in the questionnaire (DECLARED evidence) and declares 40 endpoints. It may upload documents (DOCUMENTED or TESTED evidence).",
  "**Collector set-up (insurer).** The insurer adds the company to the collector with 40 declared endpoints, links it to the platform company, approves the current agent build and policy hashes, and issues an enrollment token (for example 45 uses, 14 days).",
  "**Roll-out (insured's IT).** The IT team receives the agent folder, `ca.pem` and the token, and runs the installer on each machine with admin rights. Each agent enrolls, gets its own id and secret, starts as a service and sends a full snapshot.",
  "**Reporting.** From then on each machine sends deltas when something changes, a heartbeat every 15 minutes and a full snapshot every 24 hours. The collector checks each report, updates the machine's current results, and the link worker pushes the company roll-up to the platform when it changes.",
  "**Quote.** The underwriter requests a quote. Engine A now has fleet evidence for most controls, which outranks the questionnaire. Engine B prices from it. Failing warranty controls make the quote conditionally eligible until fixed.",
  "**Bind.** The policy is bound. The premium is fixed. Five warranties start at MET and are evaluated straight away. The 14-day coverage roll-out window starts.",
  "**Ordinary days.** Most days nothing changes and almost nothing is sent: heartbeats and the daily snapshot.",
  "**Something breaks.** Someone switches off Defender's real-time protection on one machine. Within the EDR interval (60 minutes, or at once with `scan-now`) that machine reports EDR FAIL. If that takes the company below 95%, the roll-up says CTRL-EDR false, and the platform moves the EDR warranty to IN_GRACE with a 7-day deadline. Both dashboards show it. The premium does not change.",
  "**Fix.** IT turns protection back on. The next report is PASS, the company is back above 95%, and the warranty goes REMEDIATED then MET. The history keeps all four events.",
  "**Not fixed.** If the 7 days pass with EDR still failing, the warranty is BREACHED and its consequence applies (in this prototype: incident-response deductible doubled) until it is fixed.",
  "**Agent removed, or staff on leave.** If someone uninstalls the agent from a failing machine, it goes UNVERIFIED after 6 hours and SILENT after 72, and keeps counting as failing because its last result was FAIL. Laptops switched off for a holiday were passing when they went quiet, so they are left out of the roll-up for up to 14 days and no warranty moves. If more than 10% of declared machines go quiet at once, the coverage warranty fails.",
  "**Claim.** If an incident happens, the warranty event history shows the state of each warranty at any moment, and every observation traces back to a signed report. Final claim decisions remain with the policy wording and authorised claims handling.",
  "**Renewal.** A renewal would be priced from the year's evidence, which is the next point where monitoring can influence price. Renewal itself is not built in the prototype.",
]);
H2("7.1 How fast a change reaches the platform");
table("Time from a real change to the platform", ["Step", "Normal operation", "In the demo"], [
  ["Agent notices the change", "at the check's next interval (EDR 60 min, PATCH/BACKUP 4 h, others 24 h)", "`scan-now`: next tick, up to 30 s"],
  ["Agent sends", "same tick", "same tick"],
  ["Collector accepts and evaluates", "under a second", "under a second"],
  ["Link worker pushes", "at once (woken by the report)", "at once"],
  ["Platform updates the warranty", "on receipt", "on receipt; refresh the page"],
], [3000, 3700, 2326]);

// ================================================================= 8
H1("8. Setting it up");
H2("8.1 One laptop (simulated machines)");
code([
  "python run_linked_demo.py",
  "#  platform  http://127.0.0.1:8000     collector  http://127.0.0.1:8443 (admin token printed)",
  "kyh> bind                              # quote and bind Kalinga Components",
  "kyh> break KAL-PLANT-WS03 edr_down     # EDR goes IN_GRACE on both dashboards",
  "kyh> fast-forward                      # demo only: end grace periods now (audited)",
  "kyh> fix KAL-PLANT-WS03                # REMEDIATED, then MET",
  "kyh> status | hosts | quit",
]);
P("This starts the platform and the collector in one process, registers and links them, and creates four simulated machines that report every 30 seconds. Nothing touches the laptop's own settings. `fast-forward` exists because grace periods on the platform are whole days; it writes a DEMO_TIME_TRAVEL entry to the audit log so the shortcut is never hidden.");
H2("8.2 Laptop plus a real Windows VM");
figure("vm_fig1_setup.png", "The VM set-up used for the demonstration.");
P("`python run_linked_demo.py --vm-ip 192.168.56.1` adds a fifth, real machine. The collector then listens only on the laptop's VirtualBox host-only address, over HTTPS with a private certificate authority kept in `demo-tls/`; the company declares five endpoints; and a `vm-kit` folder is written for the VM, containing the agent, `ca.pem`, `connect-vm.ps1` (install and enroll) and `kyh-vm-demo.ps1` (actions that change one real setting and ask for a re-check). The `bind` command first checks that the VM passes PATCH, EDR and BACKUP. Every step, including building the VM, is in the separate guide ~Beretta VM Setup and Demo Guide~.");
H2("8.3 A real deployment");
P("In a real deployment the collector runs on an insurer server and the platform on another, with HTTPS between them. The order of work:");
code([
  "# insurer: collector server",
  "python -m kyh_collector --data /srv/kyh init                       # admin token, shown once",
  "python -m kyh_collector --data /srv/kyh gen-cert --host collector.insurer.in",
  "python -m kyh_collector --data /srv/kyh add-company --name \"Kalinga Components\" --declared-endpoints 40",
  "python -m kyh_agent build-info                                     # prints build_hash and policy_hash",
  "python -m kyh_collector --data /srv/kyh approve-build  --hash <build_hash>  --label 2.0.0",
  "python -m kyh_collector --data /srv/kyh approve-policy --hash <policy_hash> --label baseline-2.0.0",
  "python -m kyh_collector --data /srv/kyh link-platform --url https://kyh.insurer.in --collector-id COL-.. --secret ..",
  "python -m kyh_collector --data /srv/kyh link-company --company co_x --platform-company CO-y",
  "python -m kyh_collector --data /srv/kyh issue-token --company co_x --max-uses 45 --days 14",
  "python -m kyh_collector --data /srv/kyh serve --host 0.0.0.0 --port 8443 \\",
  "    --tls-cert /srv/kyh/tls/server.pem --tls-key /srv/kyh/tls/server.key",
  "",
  "# insured: each Windows machine, elevated PowerShell, in the agent folder",
  ".\\install\\windows\\install.ps1 -Server https://collector.insurer.in:8443 -Token kyh_enr_.. -CaFile .\\ca.pem",
  "# each Linux machine",
  "sudo ./install/linux/install.sh --server https://collector.insurer.in:8443 --token kyh_enr_.. --ca-file ca.pem",
]);
P("`ca.key`, the private key of the certificate authority, stays offline with the insurer. Collector thresholds can be changed per installation by placing a `settings.json` in the data folder with only the keys to override.");
table("Routine operations", ["Task", "How"], [
  ["New agent release", "run build-info on it and approve-build before rolling it out; machines on the old build stay trusted until that hash is removed"],
  ["Machine decommissioned", "retire --agent ag_x (audited); otherwise it goes SILENT and, after 14 days, counts as failing"],
  ["More machines to enroll", "issue a new token; tokens expire and have a use limit"],
  ["Check a machine", "on it: status, or scan-now --wait 120; on the dashboard: its host page"],
  ["Back up the collector", "copy the data folder (collector.db and platform_link.json)"],
  ["Remove the agent", "retire it first, then run the uninstall script"],
], [2700, 6326]);

// ================================================================= 9
H1("9. The demonstration in the viva");
figure("vm_fig2_flow.png", "The main sequence of the demonstration.");
N([
  "Collector dashboard: five machines, four labelled SIMULATED and one REAL Windows 11 VM. Open the VM's host page: twelve real results, each with its evidence and assurance.",
  "In the VM: `kyh-vm-demo.ps1 policy` shows what is collected and what never is.",
  "Platform, Monitoring tab: fleet evidence recorded as AGENT_FLEET, TECHNICALLY_OBSERVED. Bind at the `kyh>` prompt (it checks the VM is ready first).",
  "In the VM: `kyh-vm-demo.ps1 defender-off`. The VM prints EDR FAIL; the collector shows EDR 4/5; the platform shows EDR IN_GRACE with a 7-day deadline and its consequence. The premium is unchanged.",
  "In the VM: `kyh-vm-demo.ps1 defender-on`. EDR passes; the warranty goes REMEDIATED and MET; the event history keeps every step.",
  "Optional: `fast-forward` to show BREACHED; `backup-stale`/`backup-ok` for a second warranty; `firewall-off`/`firewall-on` to show that a non-warranty control fails in the fleet table without moving any warranty.",
]);
P("The points to make: a real change on a real machine reaches the insurer in about a minute; every step is signed, numbered and stored; and the premium never moves.");

// ================================================================= 10
H1("10. Security design");
P("The main threat is unusual. In most security software the attacker is an outsider. In insurance monitoring, the party with a reason to fake a PASS is the insured, who controls the machine the agent runs on. Moving from questionnaires to monitored warranties only helps if the evidence is hard to fake [6].");
table("Threats and defences", ["Threat", "Defence", "What remains"], [
  ["Report changed in transit", "TLS 1.2+ to a pinned private CA; HMAC over the exact bytes", "none found in testing"],
  ["Old \"all PASS\" report sent again", "sequence number must increase; reports over 30 days old refused", "none found in testing"],
  ["Forged report from another machine", "per-agent 256-bit secret; signature checked before parsing", "needs the secret (see the honest limit)"],
  ["Agent removed or blocked on a failing machine", "heartbeats; a silent machine whose last result failed keeps failing; coverage warranty", "a passing machine cut off and then changed is left out for up to 14 days [C-asm]"],
  ["Agent code edited to always pass", "build hash checked against approved releases", "an admin who also fakes the build hash (see below)"],
  ["Policy edited to lower thresholds", "policy hash checked against approved policies", "same as above"],
  ["Insurer pushes code to insured machines", "no command channel; the policy is data; unknown checks rejected", "none"],
  ["Stolen enrollment token", "hashed at rest; limited uses; expiry; every enrollment audited", "rogue machines could enroll within the limits"],
  ["Fake collector or TLS interception", "the agent trusts only the collector's own CA", "theft of ca.key (kept offline)"],
  ["Malicious values in reports (XSS)", "ids and statuses validated; values escaped in the dashboard; CSP", "none found in testing"],
  ["Flooding", "1 MB body cap; 30 requests a minute per agent and per IP for enrollment", "no defence against a large distributed flood"],
  ["Forged roll-up to the platform", "collector secret, HMAC, sequence, 5-minute window, company must be linked", "the collector's secret, if stolen"],
  ["Collector database leak", "tokens stored as hashes; secrets never returned by the API", "agent secrets are stored in clear (HMAC needs them)"],
  ["Simulated data passed off as real", "envelope flag; label on every result; ignored outside demo companies", "none"],
], [2500, 3800, 2726]);
H2("10.1 The honest limit");
P("An administrator on the insured machine who is determined to lie can read the agent's secret and send well-formed false reports. Software running on a machine cannot fully protect itself from the machine's own administrator. The known fix is hardware-backed attestation, in which the TPM chip signs measurements of the code that is running, as the open-source Keylime project does [9]. This is listed as future work rather than hidden, in the same way Part 1 flags its assumed loadings. Against everything short of that (casual tampering, uninstalling, editing the code, replaying old reports, network interception) the design holds, and every attempt that is detected is written to the audit log.");
H2("10.2 Why these choices");
B([
  "**HMAC rather than public-key signatures:** Python's standard library has HMAC but no Ed25519, and the project has no third-party dependencies. The cost is that the collector holds every agent's secret.",
  "**A private CA rather than a public certificate:** pinning to the insurer's own CA means a certificate bought for any other domain, or a corporate TLS-inspection box, cannot impersonate the collector.",
  "**A sequence number rather than a nonce:** it needs no extra round trip, survives offline periods (reports queue in order), and makes replays and gaps visible.",
]);

// ================================================================= 11
H1("11. Privacy");
P("The agent runs on machines that employees use, so the Digital Personal Data Protection Act 2023 applies to what it sends [3]. The design collects configuration state and nothing about people.");
table("What the agent collects", ["Collected", "Never collected"], [
  ["control states, OS version, hostname, counts, configuration values, names of installed security software", "file contents, document names, browsing history, keystrokes, screenshots, e-mail, passwords"],
  ["administrator account names as salted hashes (salted with the agent id, so they cannot be matched across companies)", "user names in clear text, personal data of employees"],
], [4513, 4513]);
P("Every report sent is logged on the machine in `sent.jsonl`, so the company's own staff can see exactly what left each machine, and `show-policy` prints the collected and never-collected lists. A retention period for raw reports on the collector is not yet enforced and is listed under limitations.");

// ================================================================= 12
H1("12. Testing");
P("All tests run with the standard library's unittest in a few seconds.");
table("Test suites", ["Suite", "Tests", "What it proves"], [
  ["Part 2: test_parsers", "36", "every parser against output captured from Windows, Ubuntu, Debian, RHEL and macOS, including the PowerShell single-object and sshd Include cases"],
  ["Part 2: test_verdicts", "29", "every decision rule; stale signatures are FAIL/PRESENT, never OPERATING; MFA never claimed; Windows 11 26H2 supported on both tables"],
  ["Part 2: test_agent_core", "37", "policy cannot add checks; crash, timeout, missing tool and missing admin become statuses; no shell; signing and tamper detection; build hash; outbox order and cap; scheduling, deltas, jitter, heartbeats; scan-now; offline replay; simulation labels; file permissions; proxy bypass"],
  ["Part 2: test_collector", "38", "silence judged on the last result, including 10 of 100 machines on leave for 10 days with no warranty change; enrollment tokens; every ingest rejection; untrusted builds and simulated reports not counted; 95% roll-up; full stand-alone lifecycle; silence rule; coverage and roll-out window; retirement; no re-pricing"],
  ["Part 2: test_end_to_end", "5", "real HTTPS with a generated CA: agents enroll and report, warranties change; replayed and forged reports refused; an agent pinned to another CA refuses to connect; dashboard needs the admin token"],
  ["Part 2: test_platform_link", "10", "mapping and FAIL dominance; signed, numbered pushes only on change, plus heartbeat pushes; failed pushes retried; a silent failing machine pushed as a failure with no new report, and a silent passing one left out then failed after 14 days; platform states shown; collector bind refused for linked companies; link file private"],
  ["Part 1: test_platform", "17", "the original underwriting tests, unchanged and passing"],
  ["Part 1: test_platform_fleet_link", "15", "bad signature, unknown collector, replay, stale time, unlinked company, invalid values; AGENT_FLEET evidence and de-duplication; fleet evidence feeds the quote before bind; after bind a failure moves the warranty and never the premium; coverage warranty; monitoring-only control never priced or gating"],
  ["integration", "1", "both systems started for real over HTTP: four machines report, quote uses AGENT_FLEET, bind, EDR down gives IN_GRACE on both, fix gives MET, premium unchanged, event path MET, IN_GRACE, REMEDIATED, MET"],
], [2800, 800, 5426]);
P("The rule that monitoring never re-prices is tested in several ways: a company is driven into BREACHED and its policy row, including the premium, is checked to be identical to the moment of bind; binding twice is refused; and the ingestion and evaluation code is checked for any statement that writes to the policies table.");
P("Beyond the unit tests, the VM path was tested end to end with a real (Linux) agent run from the generated kit: it enrolled with the kit's CA, was trusted as an approved build, and a stale backup marker moved the platform's BACKUP warranty to IN_GRACE within about ten seconds and back to MET when fixed. **Limit:** the Windows and macOS checks are tested through their parsers with captured output; the Windows VM run is the first time they run on a real Windows machine.");

// ================================================================= 13
H1("13. The rule \"monitoring never re-prices\", in the code");
P("Because this rule is the centre of the design, here is exactly where it is held:");
B([
  "The collector's evaluation module reads the bound premium for display and has no statement that writes it. Its `bind` command refuses a second bind and refuses any bind for a linked company.",
  "The platform's roll-up handler writes observations and, if the policy is bound, calls only the warranty evaluation. Its answer always includes `repricing_performed: false`.",
  "Engine B runs only when a quote is requested; binding stores that quote's premium, and binding again is refused (POLICY_ALREADY_BOUND).",
  "The monitoring-only control is excluded from every pricing function, so adding it did not change any premium (checked by the Part 1 tests).",
]);

// ================================================================= 14
H1("14. Design decisions and why");
table("Decisions a panel may ask about", ["Decision", "Alternative considered", "Why this way"], [
  ["Python standard library only", "osquery, Wazuh agent, third-party packages", "matches Part 1's zero-dependency rule; every line can be read and audited; nothing to licence or patch [7], [8]"],
  ["Read-only checks, no remediation", "agent fixes problems itself", "an insurer must not change the insured's systems; read-only is also safer to install"],
  ["Policy is data; checks are fixed in code", "downloadable check scripts", "removes any remote-code-execution path from insurer to insured"],
  ["Push from agents to collector", "collector polls machines", "laptops sit behind NAT and firewalls; outbound HTTPS works everywhere"],
  ["Deltas plus heartbeat plus daily snapshot", "send everything every time", "little traffic on normal days, but silence is still detected and state is re-synced daily"],
  ["Local outbox with sequence numbers", "send and forget", "nothing is lost offline; replays and gaps are visible"],
  ["PASS/FAIL plus assurance level", "PASS/FAIL only", "a tool being installed is not the same as working; PRESENT vs OPERATING shows the difference"],
  ["NOT_SUPPORTED instead of guessing", "infer MFA or backup state", "honest evidence; the platform asks for the right document instead"],
  ["95% fleet rule", "100%, or average score", "realistic for large fleets; one machine mid-update should not breach a warranty"],
  ["Silence judged on the last result", "count every silent machine as failing; or ignore silent machines", "silence can never hide a failure, but staff on leave do not breach warranties; the 14-day cap and the coverage rule limit abuse"],
  ["Coverage warranty (90% of declared)", "trust the enrolled count", "stops a company enrolling only its best machines"],
  ["Collector separate from the platform", "agent reports straight to the platform", "machine-level concerns (secrets, replay, silence) stay out of the policy system; one collector can serve many companies"],
  ["Platform owns the only warranty machine", "two machines kept in sync", "two sources of truth gave conflicting states"],
  ["Backup sent as partial", "send PASS", "a recent backup is observable; a tested restore is not"],
  ["Scheduled task on Windows", "Windows service", "a service needs pywin32 or a wrapper; packaging is future work"],
  ["HMAC signatures", "Ed25519", "not in the standard library; see Section 10.2"],
], [2600, 2500, 3926]);

// ================================================================= 15
H1("15. Limitations and next steps");
B([
  "**A determined local administrator can forge reports.** Needs TPM-based attestation (for example Keylime [9]).",
  "**The collector holds every agent's secret** because of HMAC. Per-agent public-key signatures would fix this, at the cost of a dependency.",
  "**MFA is not observed.** Needs a connector to the identity provider (Entra ID conditional access, Google Workspace 2-Step Verification).",
  "**A passing machine that goes quiet is left out for up to 14 days.** If it was cut off from the network and then had a control switched off, that change is only seen when it reconnects or reaches 14 days. The coverage rule limits how many machines can be in that state.",
  "**Restore testing is not observed**, which is why backup is sent as partial. A dated restore-test report uploaded to the platform covers it.",
  "**Thresholds and lifecycle dates** are demonstration values or dated vendor data, to be reviewed before real use.",
  "**Windows packaging.** A signed installer and a real Windows service would remove the need for Python on each machine.",
  "**Exploited-vulnerability matching** against the CISA KEV catalogue [13] is not done; PATCH counts pending updates rather than specific known-exploited CVEs.",
  "**Time-sync traceability.** A server traceable to NIC/NPL but not named in the list fails until the insured documents it.",
  "**The old single-machine agent endpoint in Part 1** (`/api/agent/report`, bearer token) is still open for the original tests; it should be switched off before real use because it accepts unsigned reports.",
  "**No retention limit** is enforced yet for raw reports on the collector.",
  "**Grace periods are whole days on the platform**, which is why the demo uses an audited fast-forward.",
]);

// ================================================================= 16
H1("16. Questions you may be asked");
P("Short answers, each pointing to the section with the detail.");
const QA = (q, a) => {
  body.push(new Paragraph({ keepNext: true, spacing: { before: 160, after: 40, line: 300 }, children: runs("**Q. " + q + "**") }));
  body.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 100, line: 340 }, children: runs(a) }));
};
H2("16.1 The idea");
QA("What problem does the agent solve?", "A warranty is a promise to keep a control in place for the whole policy year, but the insurer only sees a form signed on day one. The agent observes the controls continuously on every machine, so the insurer knows whether each warranty is still being kept (2.1).");
QA("Does monitoring change the premium?", "No. The premium is fixed at bind by Engine B. After bind, monitoring only moves warranty states. The platform's answer to every roll-up carries `repricing_performed: false`, and tests check the premium stays identical while warranties move. Monitoring affects price only before bind and at renewal (2.2, 13).");
QA("Then what does a breach actually do?", "It applies a configured coverage consequence to future claims, such as a doubled incident-response deductible for EDR, after a grace period. In the prototype these are illustrative and labelled as such (2.3).");
QA("Why not just use the questionnaire?", "Self-assessment is the weakest evidence: the platform credits a declared answer at 0.60 and a technically observed one at 1.00. Research on proposal forms shows they rely on self-assessment [5] (2.1, 6.7).");
H2("16.2 The agent");
QA("What exactly does the agent check?", "Twelve controls: patching, EDR, backup and MFA (warranty); disk encryption, firewall, exposed services, remote access, admin accounts and OS support (important); log retention and time sync (CERT-In). Table 4 lists the source on each OS and Table 5 the pass/fail rule (4.1).");
QA("How does it know Defender is working, not just installed?", "It reads Get-MpComputerStatus: Defender must be the active engine (not passive), real-time protection must be on, and signatures must be at most 3 days old. Installed but failing any of these is FAIL with assurance PRESENT (4.1, 4.4).");
QA("Why is MFA always NOT_SUPPORTED?", "MFA is enforced by the identity provider, not by a laptop. Reporting NOT_SUPPORTED with guidance is more honest than guessing; MFA evidence comes from an identity-provider export uploaded to the platform (4.1).");
QA("Can the agent change anything on the machine?", "No. Every command is read-only (Get-* cmdlets, apt-get -s, registry reads), there is no shell, and there is no command channel from the insurer (4.2, 4.5).");
QA("Can the insurer push new checks or code to the agent?", "No. The checks are fixed in the program; the policy file can only choose among them and set numbers, and a policy naming an unknown check is rejected at load (4.5).");
QA("What happens if a check crashes or hangs?", "It becomes an ERROR result with the reason; a hung check is abandoned after its time budget. The agent itself never stops (4.6).");
QA("How often does it report, and how much traffic is that?", "A full snapshot daily, a delta only when a result changes, a heartbeat every 15 minutes. On a normal day that is 96 tiny heartbeats and one snapshot per machine (4.7).");
QA("What if the laptop is offline for a week?", "Reports wait in the local outbox in order and are sent when it reconnects; the collector accepts them up to 30 days old. Meanwhile the machine shows UNVERIFIED, then SILENT after 72 hours (4.9, 5.5).");
QA("Does it slow the machine down?", "Most checks run once a day, EDR hourly, PATCH and BACKUP every 4 hours. On Linux the service is capped at 5% CPU and 150 MB and runs at idle I/O priority (4.7, 4.12).");
QA("Does it have a user interface?", "Not on the insured machine, on purpose: there is nothing for an employee to close. Administrators use the command line (status, scan-now, show-policy). The insurer uses the collector dashboard and the platform's Monitoring tab (4.13, 5.10).");
QA("Why does it need admin or root rights?", "Some facts are only readable with them: BitLocker status, firewall rules, sshd's effective configuration, the full process list. On Linux the service is sandboxed so it can only write to its own state folder (4.12).");
H2("16.3 Trust and security");
QA("How do you know a report really came from that machine?", "Each machine has its own 256-bit secret from enrollment, and every report carries an HMAC-SHA256 of its exact bytes. The collector recomputes it before reading the report (4.8, 5.3).");
QA("What stops someone replaying an old all-PASS report?", "Every report has a sequence number that only goes up; the collector refuses any number it has already seen, with 409 REPLAY, and audits it (4.8, 5.3).");
QA("What if someone edits the agent to always say PASS?", "Its build hash changes. The collector stores its reports but labels them UNTRUSTED_BUILD and does not count them (4.8, 5.4).");
QA("What if they just uninstall the agent?", "Heartbeats stop. After 72 hours the machine is SILENT. If its last result was failing, it keeps counting as failing, so removing the agent hides nothing. If it was passing, it is left out for up to 14 days and then counts as failing. Silent machines never count as reporting, so the coverage warranty catches mass removal (5.5, 5.8).");
QA("If 10 of 100 employees go on leave for 10 days, does the company fail?", "No. Their laptops were passing when they went quiet, so after 72 hours they are left out of the roll-up instead of counted as failing: 90 of 90 pass. Coverage is 90 of 100 reporting, exactly the 90% needed. An 11th person on leave would fail coverage but not EDR. After 14 days quiet, the laptops would count as failing (5.5).");
QA("Can a local administrator fake everything?", "Yes, with enough effort: they can read the secret and send well-formed false reports. Software alone cannot stop that; TPM-based attestation can. It is listed as a limitation (10.1).");
QA("Why a private CA?", "The agent trusts only the collector's own CA, so a fake server with a certificate from a public CA, or a TLS-inspection device, is refused (4.10, 10.2).");
QA("Why HMAC and not digital signatures?", "HMAC is in Python's standard library and public-key signatures such as Ed25519 are not. The trade-off is that the collector holds each agent's secret (10.2).");
QA("Is employee data collected?", "No. Configuration state only; admin names leave as salted hashes; nothing about files, browsing or keystrokes. Every report sent is logged on the machine (11).");
H2("16.4 The collector and the roll-up");
QA("Why 95% and not 100%?", "In a large fleet there is almost always one machine mid-update or switched off. A 100% rule would keep warranties in grace permanently. The figure is an assumption an underwriter would tune (5.7).");
QA("With five machines, one failure fails the company. Is that fair?", "It is how the 95% rule works at small sizes, and it is what the demo uses. For a small company an underwriter could set a lower ratio per account in the collector settings (5.7).");
QA("What if a control cannot be seen on any machine?", "It is NOT_OBSERVABLE and no warranty moves. Absence of evidence is not treated as a breach (5.7, 6.4).");
QA("What stops a company enrolling only its best machines?", "The coverage warranty: reporting machines must be at least 90% of the endpoints declared on the proposal, after a 14-day roll-out window (5.8).");
QA("Why is there a separate collector at all?", "Machine-level work (secrets, replay checks, silence, per-host evidence) is a different job from policy work. Keeping it separate keeps the platform simple and lets one collector serve many companies (6.1, 14).");
H2("16.5 The platform link");
QA("How does the platform trust the collector?", "Same pattern as agent to collector: a registered collector id and secret, an HMAC over each roll-up, a rising sequence number, a 5-minute time window, and the company must be linked to that collector (6.6).");
QA("How does fleet data affect the quote?", "Each control becomes an AGENT_FLEET observation at TECHNICALLY_OBSERVED strength. Engine A picks it over weaker evidence, and Engine B gives a passing control its full credit (1.00) instead of the 0.60 a declared answer gets (6.7).");
QA("Why did the two state machines differ, and which one is used?", "The collector's stand-alone machine waits 24 hours before REMEDIATED returns to MET; the platform's returns at once. For linked companies, which includes the demo, only the platform's is used (5.9, 6.8).");
QA("What is CTRL-AGENT-COVERAGE?", "A warranty that the agent keeps reporting from at least 90% of declared machines. It is monitoring-only: never priced, never in the questionnaire, so adding it changed no premium (6.7).");
QA("Why is backup sent as partial?", "The platform control is tested backups. The agent can see that a backup ran recently but not that a restore was tested (6.4).");
H2("16.6 Set-up and the demo");
QA("How is it installed on a company's machines?", "The insurer sends the agent folder, ca.pem and an enrollment token. IT runs install.ps1 (Windows, elevated) or install.sh (Linux/macOS, root) on each machine. Each agent enrolls itself and starts as a service (4.11, 4.12, 8.3).");
QA("Is the demo data real?", "Four machines are simulated and labelled SIMULATED everywhere; the fifth is a real Windows VM with real checks. Simulated results are only accepted for companies created in demo mode (4.14, 8.2).");
QA("Why use fast-forward?", "Grace periods are whole days. fast-forward ends running grace periods now so BREACHED can be shown, and it is written to the audit log as DEMO_TIME_TRAVEL (8.1).");
QA("Why a VM rather than the laptop itself?", "The demo switches off antivirus and the firewall and installs with admin rights. In a VM that is safe and can be rolled back with a snapshot (8.2).");
QA("How fast does a change reach the platform?", "Normally within the check's interval (EDR within 60 minutes). With scan-now, within about 30 seconds; after that the collector and platform react in under a second (7.1).");
H2("16.7 Limits");
QA("What would you do next?", "TPM attestation, an identity-provider connector for MFA, a packaged Windows service, KEV-based vulnerability matching, public-key signatures, and switching off the old Part 1 agent endpoint (15).");
QA("Which numbers are assumptions?", "Every threshold tagged [C-asm]: 30-day patch cycle, 3-day signatures, 7-day backups, 3 admins, 95% fleet, 90% coverage, 6/72-hour liveness, grace periods and consequences. The 180-day log retention and NIC/NPL time sources come from CERT-In (4.5, Table 3).");

// ================================================================= 17
H1("17. Glossary");
table("Terms", ["Term", "Meaning"], [
  ["Agent", "the program on each insured machine that reads and reports controls"],
  ["Collector", "the insurer's server that receives agent reports and rolls them up"],
  ["Beretta platform", "Part 1: evidence, pricing, binding and the warranty state machine"],
  ["Engine A / Engine B", "the platform's evidence resolution / its premium calculation"],
  ["Control", "a security measure, such as EDR or disk encryption"],
  ["Warranty", "a control the insured must keep in place while the policy runs"],
  ["Bind", "the moment the policy is issued and the premium is fixed"],
  ["Grace period", "time allowed to fix a failing warranty before it is BREACHED"],
  ["Evidence strength", "how much a result is trusted: DECLARED, DOCUMENTED, TESTED, TECHNICALLY_OBSERVED"],
  ["Assurance", "how strongly a control was seen working: OPERATING, RUNNING, PRESENT, ABSENT"],
  ["Full / delta / heartbeat", "report with every result / only changed results / no results, proof of life"],
  ["Envelope", "the signed JSON report the agent sends"],
  ["HMAC-SHA256", "a keyed hash proving the sender knows the secret and the body was not changed [12]"],
  ["Sequence number", "a counter in every report that must always increase; stops replays"],
  ["Build hash / policy hash", "SHA-256 fingerprints of the agent's code / its rules"],
  ["Outbox", "the agent's local queue of reports waiting to be sent"],
  ["Liveness", "ONLINE, UNVERIFIED or SILENT, from how long a machine has been quiet"],
  ["Roll-up", "one result per control for the whole company"],
  ["NOT_OBSERVABLE", "no machine could observe the control; no warranty moves"],
  ["AGENT_FLEET", "the platform source type for collector roll-ups"],
  ["Monitoring-only control", "CTRL-AGENT-COVERAGE: a warranty that is never priced"],
  ["Private CA / pinning", "the insurer's own certificate authority; the agent trusts only it"],
  ["[C-asm]", "an assumed demonstration value, not actuarially derived"],
  ["CERT-In", "Indian Computer Emergency Response Team; its 2022 Directions require 180-day logs and NIC/NPL time"],
  ["DPDP Act", "Digital Personal Data Protection Act, 2023"],
], [2800, 6226]);

// ================================================================= APPENDIX
H1("Appendix A. Where everything is in the code");
table("Agent (kyh-agent/agent/kyh_agent)", ["File", "Lines", "Role"], [
  ["checks/base.py", "133", "statuses, assurance levels, result types, run_cmd"],
  ["checks/windows.py, linux.py, macos.py", "230 / 287 / 112", "Layer 2: one function per check per OS"],
  ["checks/parsers.py", "471", "Layer 3: raw output to facts"],
  ["checks/verdicts.py", "239", "Layer 4: facts and thresholds to an outcome"],
  ["checks/__init__.py", "36", "the fixed check registry"],
  ["policy.json, policy.py", "-, 94", "Layer 5: the rules and their validation and hash"],
  ["runner.py", "96", "Layer 6: guarded execution, salted hashes"],
  ["agent.py", "282", "Layers 7 to 9: scheduling, envelopes, outbox use, sending, enrollment, scan-now"],
  ["security.py", "43", "signing and build hash"],
  ["spool.py", "82", "the outbox database and sequence counter"],
  ["transport.py", "77", "Layer 10: HTTPS with pinning, proxy bypass"],
  ["config.py, simulate.py, __main__.py", "58 / 48 / 186", "config file, demo profiles, command line"],
  ["install/windows, linux, macos", "", "installers, service definitions, uninstallers"],
], [3600, 1500, 3926]);
table("Collector (kyh-agent/collector/kyh_collector) and platform link", ["File", "Lines", "Role"], [
  ["core.py", "230", "admin operations, enrollment, the ingest gate"],
  ["evaluate.py", "270", "liveness, host status, roll-up, coverage, stand-alone state machine"],
  ["platform_link.py", "268", "mapping, roll-up message, signing, link worker"],
  ["server.py", "221", "HTTP API, dashboard, rate limits, security headers"],
  ["db.py, settings.py, __main__.py", "79 / 64 / 291", "schema, thresholds, admin commands"],
  ["static/", "301", "dashboard (HTML, CSS, JavaScript)"],
  ["Part 1: app/fleet.py", "193", "platform side of the link: authenticate, check, record, evaluate"],
  ["Part 1: app/observations.py, underwriting.py, coverage.py", "165 / 254 / 160", "Engine A, Engine B, platform warranty machine"],
], [3600, 1500, 3926]);

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
  "[10] Microsoft, \"Windows 11 release information,\" Microsoft Learn. [Online]. Available: https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information. [Accessed: 27-Oct-2026].",
  "[11] Canonical, \"Ubuntu release cycle.\" [Online]. Available: https://ubuntu.com/about/release-cycle",
  "[12] H. Krawczyk, M. Bellare, and R. Canetti, \"HMAC: Keyed-Hashing for Message Authentication,\" RFC 2104, Feb. 1997.",
  "[13] Cybersecurity and Infrastructure Security Agency, \"Known Exploited Vulnerabilities Catalog.\" [Online]. Available: https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
].forEach((r) => body.push(new Paragraph({ children: runs(r), spacing: { after: 100, line: 300 },
  indent: { left: 560, hanging: 560 } })));

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
  ...Array.from({ length: 60 }, (_, i) => ({ reference: "numbers-" + (i + 1), levels: [{ level: 0,
    format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] })),
] };

const doc = new Document({
  creator: "Beretta capstone team",
  title: "Beretta Live Monitoring Agent: Complete Technical Guide",
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
  const out = path.join(__dirname, "Beretta_Agent_Complete_Guide.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, `(${figN} figures, ${tabN} tables)`);
});
