// Builds docs/Beretta_VM_Setup_and_Demo_Guide.docx  (node build_vm_guide.js)
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
let firstH1 = true;   // only the first section starts a new page; the rest flow
const H1 = (t) => { toc.push([1, t]); body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t })],
  pageBreakBefore: firstH1, keepNext: true, spacing: { before: firstH1 ? 120 : 480, after: 240 } })); firstH1 = false; };
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

const NC = (items) => B(items, "numbers-" + numCount);   // continue the previous numbered list
// ================================================================= TITLE PAGE
const tp = (t, size, o = {}) => body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
  children: [new TextRun({ text: t, font: FONT, size, ...o })] }));
body.push(new Paragraph({ spacing: { before: 1800 }, children: [] }));
tp("Beretta", 28, { bold: true });
tp("Live Monitoring on a Windows VM", 40, { bold: true });
tp("using Oracle VirtualBox", 30, { bold: true });
tp("Step-by-step setup and demonstration guide", 26, { italics: true });
body.push(new Paragraph({ spacing: { before: 900 }, children: [] }));
tp("Final-year capstone project, B.Tech / MBA Tech", 24);
tp("Mukesh Patel School of Technology Management & Engineering, NMIMS Mumbai", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Harsh (K080)  ·  Yugandhara Raj Goud (K023)  ·  Krish Mundhra (K041)", 24);
tp("Supervisor: Prof. Rohit Suryawanshi", 24);
body.push(new Paragraph({ spacing: { before: 400 }, children: [] }));
tp("Agent 2.0.0  ·  Collector 2.0.0 (linked mode)  ·  27 October 2026", 22);
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Contents", bold: true, font: FONT, size: 28 })] }));
const tocIndex = body.length;

// ================================================================= 1
H1("1. What you will build");
P("The linked demo so far runs four simulated endpoints on one laptop. This guide adds a fifth endpoint that is real: a Windows 11 virtual machine running the Beretta agent as a SYSTEM scheduled task. The agent reads the VM's actual security settings and sends signed reports over HTTPS to the collector on your laptop. The collector rolls them up with the four simulated hosts and pushes the result to the Beretta platform.");
P("In the viva you change a real setting in the VM, such as switching off Defender's real-time protection. Within about a minute the platform moves the EDR warranty to IN_GRACE, and the premium stays the same. Switch it back on and the warranty returns to MET.");
figure("vm_fig1_setup.png", "The laptop runs the platform, the collector and four simulated agents. The VM runs the real agent and reaches the collector over VirtualBox's host-only network. A shared folder carries the agent and scripts into the VM.");
table("What runs where", ["Where", "What", "Address"], [
  ["Laptop", "Beretta platform (Part 1): pricing, binding, the warranty state machine", "`http://127.0.0.1:8000`"],
  ["Laptop", "Collector (Part 2) and its dashboard", "`https://192.168.56.1:8443`"],
  ["Laptop", "Four simulated agents (always labelled SIMULATED)", "inside `run_linked_demo.py`"],
  ["VM", "Beretta agent, 12 read-only checks, scheduled task as SYSTEM", "`C:\\Program Files\\KYH\\Agent`"],
  ["VM", "`kyh-vm-demo.ps1`: changes one real setting, then asks for a re-check", "shared folder `vm-kit`"],
], [1300, 4800, 2926]);
P("**Time needed.** The first setup takes two to three hours, most of it Windows installing and updating. After that, getting ready for a demonstration takes about ten minutes.");
P("**Why a VM and not the laptop itself.** The demonstration switches off antivirus and the firewall, and the agent installs with administrator rights. In a VM you take a snapshot first and roll back in seconds, and your own machine stays protected.");

// ================================================================= 2
H1("2. What you need");
table("Checklist", ["Item", "Why", "Where"], [
  ["Oracle VirtualBox 7.1 or later (written against 7.2)", "Version 7 added the virtual TPM 2.0 and Secure Boot that Windows 11 requires; the Extension Pack is not needed.", "virtualbox.org (already installed)"],
  ["Windows 11 Enterprise evaluation ISO (version 26H2, x64)", "Free for 90 days, no product key, includes BitLocker. Its lifecycle date (9 Oct 2029) passes the OS support check. A Pro 24H2 image would fail it: support ended on 13 Oct 2026.", "Microsoft Evaluation Center [1]; registration form first"],
  ["Python 3.13, Windows installer (64-bit)", "The agent and both servers are standard-library Python. Needed on the laptop and in the VM.", "python.org/downloads/windows. The `Python-3.11.15` folder in Downloads is source code, not an installer."],
  ["The updated suite zip", "Contains the VM mode, the kit scripts and the `scan-now` command added for this guide.", "`kyh-cyber-insurance-linked.zip` sent with this guide"],
  ["Git for Windows, or the `cryptography` package", "Used once on the laptop to create the private certificate authority.", "git-scm.com, or `py -m pip install cryptography`"],
  ["About 16 GB RAM and 70 GB free disk", "The VM gets 4 GB RAM and a 64 GB disk (it uses about 25 GB).", ""],
], [2500, 3900, 2626]);
P("The evaluation page lists version 26H2, build 26300 [1]. Microsoft's release table gives Enterprise 26H2 updates until 9 October 2029 [2]. The agent's lifecycle table was updated with that build for this guide.");

// ================================================================= 3
H1("3. Part A: build the VM in Oracle VirtualBox");
P("This part was written against Oracle VirtualBox 7.2 on a Windows 11 laptop [5]. Version 7.1 looks almost the same; if a menu name differs slightly in your version, look for the same word in the nearby menus. Two VirtualBox terms are used throughout: the **host** is your laptop, and the **guest** is the Windows VM. The **Host key** is the right Ctrl key: press it once to release the mouse and keyboard from the VM window.");

H2("3.1 Check the laptop first");
N([
  "**Virtualization is on.** Open Task Manager → Performance → CPU and check that **Virtualization: Enabled** is shown. If it says Disabled, turn on Intel VT-x or AMD-V (sometimes called SVM) in the laptop's BIOS/UEFI settings.",
  "**VirtualBox is up to date.** Open VirtualBox → **Help → Check for Updates**, or install the latest 7.x from virtualbox.org. The Extension Pack is not needed for this guide.",
  "**Disk space.** About 70 GB free on the drive that holds the VMs (by default `C:\\Users\\<you>\\VirtualBox VMs`). Snapshots take extra space.",
]);
P("**The green turtle.** On Windows 11 hosts, VirtualBox sometimes has to run on top of Windows' own hypervisor (Hyper-V), because Windows features such as Memory Integrity, WSL2, Docker Desktop or Windows Sandbox use it. VirtualBox still works, but much more slowly, and shows a small green turtle icon in the VM window's status bar [6]. If you see it and Windows installation or updates crawl, fix it before going further (Section 3.8).");

H2("3.2 Create the VM");
P("Download the Windows 11 Enterprise evaluation ISO (x64) from [1] first. Then in VirtualBox click **New**. The wizard has three pages (in **Expert** mode they are all on one page; either works).");
P("**Page 1: Name and operating system**", { keepNext: true });
B([
  "**Name:** `Beretta-Win11`.",
  "**Folder:** leave the default unless that drive is short of space.",
  "**ISO Image:** choose the Windows 11 Enterprise evaluation ISO. VirtualBox reads it and fills in **Type: Microsoft Windows** and **Version: Windows 11 (64-bit)** by itself. If the ISO holds several editions, pick **Windows 11 Enterprise Evaluation**.",
  "Leave unattended installation **on** (the box called **Skip Unattended Installation** stays unticked, or **Install OS Using Unattended Installation** stays ticked, depending on the version).",
]);
P("**Page 2: Unattended guest OS install**", { keepNext: true });
B([
  "**User Name:** `kyhadmin`, and a **Password** you will remember. This becomes the Windows administrator account.",
  "**Product Key:** leave empty; the evaluation does not need one.",
  "**Host Name:** `KAL-ACCT-VM01`. This is the name that appears on both dashboards next to the simulated `KAL-` hosts.",
  "**Domain Name:** leave the default.",
  "**Install Guest Additions:** ticked. Guest Additions are VirtualBox's drivers for the guest; shared folders, the shared clipboard, window resizing and time sync need them.",
  "**Install in Background:** unticked, so you can watch.",
]);
P("**Page 3: Virtual hardware**", { keepNext: true });
B([
  "**Base Memory:** 4096 MB (4 GB). More is fine if the laptop has 16 GB or more; stay in the green part of the slider.",
  "**Processors:** 2 (never more than half the laptop's threads).",
  "**Use EFI / Enable EFI:** ticked. Windows 11 needs it.",
  "**Disk Size:** 64 GB, left as dynamically allocated (it grows as needed, to about 25 GB for this VM). Leave **Pre-allocate Full Size** unticked.",
]);
P("Check the summary and click **Finish**. VirtualBox creates the VM and starts installing Windows on its own. It takes 20 to 40 minutes with several restarts. Do not click inside the window while it runs.");

H2("3.3 Check the VM's settings");
P("When installation has finished, shut Windows down (Start → Power → Shut down), select `Beretta-Win11` in VirtualBox and open **Settings**. Check these values; the wizard normally sets them already for Windows 11 [3]:");
table("VM settings to check", ["Settings page", "Setting", "Value"], [
  ["System → Motherboard", "Enable EFI (special OSes only)", "ticked"],
  ["System → Motherboard", "Enable Secure Boot", "ticked"],
  ["System → Motherboard", "TPM", "v2.0"],
  ["System → Processor", "Processors", "2"],
  ["Display → Screen", "Graphics Controller / Video Memory", "VBoxSVGA, 128 MB"],
  ["General → Advanced", "Shared Clipboard / Drag'n'Drop", "Bidirectional (copy and paste between laptop and VM)"],
], [2600, 3300, 3126]);
P("TPM 2.0 matters twice: Windows 11 requires it to install, and BitLocker in the VM uses it if you choose to turn encryption on (Section 6).");

H2("3.4 Network: two adapters");
P("The VM needs two network cards: one for the internet and one private link to the laptop. Still in **Settings → Network**:");
B([
  "**Adapter 1:** Enable Network Adapter ticked, **Attached to: NAT**. This is the default. It gives the VM internet for Windows Update, Defender signatures and the time servers.",
  "**Adapter 2:** tick **Enable Network Adapter**, set **Attached to: Host-only Adapter**, and **Name: VirtualBox Host-Only Ethernet Adapter**. This is the private network between the VM and the laptop.",
]);
P("Click **OK**. Then check the host-only network itself: in the main VirtualBox window open **File → Tools → Network Manager** (in some versions, the **Tools** entry above the machine list, then **Network**), tab **Host-only Networks**. You should see **VirtualBox Host-Only Ethernet Adapter** with IPv4 address `192.168.56.1` and mask `255.255.255.0`, and on its DHCP tab **Enable Server** ticked (the VM then gets an address such as `192.168.56.101` automatically). If the list is empty, click **Create**; VirtualBox makes one with these defaults.");

H2("3.5 Guest Additions");
P("The unattended install normally installs Guest Additions. To check, start the VM and look in the Windows notification area for the VirtualBox icon, or in Settings → Apps for **Oracle VirtualBox Guest Additions**. If they are missing: in the VM window choose **Devices → Insert Guest Additions CD image**, open File Explorer → the CD drive (usually `D:`), run **VBoxWindowsAdditions.exe**, accept the defaults and the driver prompts, and restart the VM.");
P("Useful in the VM window: **View → Auto-resize Guest Display** makes Windows fit the window; **Input → Keyboard → Insert Ctrl-Alt-Del** (or Host+Del) sends Ctrl+Alt+Del to the VM instead of the laptop.");

H2("3.6 Prepare Windows");
N([
  "Start the VM. If the hostname was not set during install, open PowerShell as administrator and run `Rename-Computer -NewName KAL-ACCT-VM01 -Restart`.",
  "Check the network: in PowerShell, `ipconfig` should show two Ethernet adapters, one with a `10.0.2.x` address (NAT) and one with `192.168.56.x` (host-only).",
  "**Settings → Windows Update**: install everything, restart, and repeat until it says you are up to date. The PATCH check fails while security updates are pending.",
  "**Windows Security → Virus & threat protection → Protection updates → Check for updates.** The EDR check needs signatures less than three days old.",
  "**Windows Security → Virus & threat protection → Manage settings → Tamper Protection: Off.** Leave Real-time protection **on**. Tamper Protection would otherwise stop the demo script from switching real-time protection off. Turn it back on after the viva.",
  "Install Python 3.13 in the VM: run the installer, tick **Add python.exe to PATH**, choose **Customize installation → Next**, tick **Install Python 3.13 for all users**, then **Install**. The agent runs as SYSTEM, and an all-users install in `C:\\Program Files\\Python313` is the cleanest location for it. (To get the installer into the VM, download it inside the VM, or drag it from the laptop once drag-and-drop is on.)",
]);

H2("3.7 Snapshots");
P("A snapshot saves the VM's whole state so you can return to it in seconds. Take one now, with the VM shut down:");
N([
  "In VirtualBox, select `Beretta-Win11`, click the small menu button next to its name (three lines) and choose **Snapshots**.",
  "Click **Take**, name it `base-updated`, and click **OK**.",
]);
P("To go back later: shut the VM down, open the same **Snapshots** list, select the snapshot and click **Restore**. When asked whether to save the current state first, choose **No** unless you want to keep it. The same can be done from a command prompt on the laptop:");
code([
  "\"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe\" snapshot Beretta-Win11 take demo-ready",
  "\"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe\" snapshot Beretta-Win11 restore demo-ready",
]);
P("**Giving the VM to a teammate.** **File → Export Appliance** saves the VM as one `.ova` file; **File → Import Appliance** on the other laptop recreates it. The 90-day evaluation clock keeps running inside the copy.");

H2("3.8 If VirtualBox is slow (the green turtle)");
P("If the green turtle appears, Windows' hypervisor is running underneath VirtualBox. The simplest fix on most laptops [6]:");
N([
  "Make sure you have the laptop's BitLocker recovery key (Microsoft account → Devices → BitLocker keys). Changing hypervisor settings can make Windows ask for it at the next start.",
  "**Windows Security → Device security → Core isolation → Memory integrity: Off**, and restart.",
  "If the turtle is still there, open **Turn Windows features on or off** and untick **Hyper-V**, **Virtual Machine Platform**, **Windows Hypervisor Platform** and **Windows Sandbox**, then restart.",
  "Check in PowerShell: `Get-CimInstance Win32_ComputerSystem | Select-Object HypervisorPresent` should now say `False`.",
]);
P("This turns off WSL2 and Docker Desktop on the laptop until you turn the features back on. If you need those, you can leave things as they are: VirtualBox still runs, only more slowly, which mainly matters during the long Windows Update step.");

// ================================================================= 4
H1("4. Part B: prepare the laptop");
N([
  "Install Python 3.13 on the laptop if `py --version` does not already print 3.9 or newer.",
  "Unzip the suite to a plain folder such as `C:\\Beretta\\suite`. Avoid OneDrive or Desktop folders that sync: the demo writes SQLite databases, and sync tools lock them.",
  "Find the host-only address. Run `ipconfig` and look for **Ethernet adapter VirtualBox Host-Only Network**. The IPv4 address is usually `192.168.56.1`. If yours differs, use it everywhere this guide says `192.168.56.1`.",
  "Allow the VM to reach the collector. Open PowerShell **as administrator** on the laptop and run the command below once. It only opens port 8443 to the host-only network, not to Wi-Fi.",
]);
code([
  'New-NetFirewallRule -DisplayName "Beretta demo collector (VM)" -Direction Inbound -Action Allow `',
  '  -Protocol TCP -LocalPort 8443 -RemoteAddress 192.168.56.0/24',
]);
P("If your host-only address is different, change the last part of the rule to match: for a laptop address of `192.168.129.1`, use `-RemoteAddress 192.168.129.0/24`.");
NC([
  "Certificate tool: if `git --version` works, nothing to do (Git for Windows includes openssl). Otherwise run `py -m pip install cryptography`.",
  "Start the demo in VM mode, in a normal (not administrator) PowerShell:",
]);
code([
  "cd C:\\Beretta\\suite",
  "py run_linked_demo.py --vm-ip 192.168.56.1",
]);
P("The first run creates a private certificate authority in `demo-tls\\` and prints something like this:");
code([
  "Created a private CA and certificate for 192.168.56.1 in C:\\Beretta\\suite\\demo-tls",
  "==============================================================================",
  "Beretta platform (Part 1): http://127.0.0.1:8000/#/companies/CO-.../monitoring",
  "Collector    (Part 2): https://192.168.56.1:8443   admin token: kyh_admin_...",
  "Kalinga Components is linked on both sides; 4 simulated endpoints are reporting.",
  "==============================================================================",
  "Declared endpoints: 5 (4 simulated + 1 real VM)",
  "VM kit: C:\\Beretta\\suite\\vm-kit   (also zipped: C:\\Beretta\\suite\\vm-kit.zip)",
  "  Collector for the VM: https://192.168.56.1:8443    enrollment token: kyh_enr_...",
  "  In the VM (elevated PowerShell, inside the shared vm-kit folder):",
  "    powershell -ExecutionPolicy Bypass -File .\\connect-vm.ps1",
  "  Bind only after the VM shows up here (type: hosts), or coverage starts below 90%.",
  "kyh>",
]);
NC([
  "Leave this window open. The `kyh>` prompt is where you type `hosts`, `bind`, `status` and `fast-forward` later.",
  "Open the platform link in a browser. Open `https://192.168.56.1:8443` for the collector. The browser warns about the certificate because it does not know your private CA: choose **Advanced → Continue**. The agent is not affected, since it trusts only that CA (`ca.pem`). Paste the admin token printed above.",
  "If Windows shows a firewall prompt for Python, **Allow** on private networks is enough. The rule from step 4 already covers the VM.",
]);

// ================================================================= 5
H1("5. Part C: connect the VM");
N([
  "In the running VM window choose **Devices → Shared Folders → Shared Folders Settings**, then click the **+** (Add Share) button. **Folder Path:** `C:\\Beretta\\suite\\vm-kit`. **Folder Name:** `vm-kit`. **Mount Point:** `Z:`. Tick **Auto-mount** and **Make Permanent**; leave **Read-only** unticked. Click **OK** twice. (With the VM shut down, the same is under **Settings → Shared Folders**.) Shared folders need Guest Additions (Section 3.5).",
  "In the VM, File Explorer → This PC now shows **vm-kit (\\\\VBOXSVR) (Z:)**. If it does not, restart the VM once. Still nothing? Drag `vm-kit.zip` from the laptop into the VM window (drag-and-drop must be Bidirectional, Section 3.3) and unzip it to `C:\\vm-kit`, then use that folder instead of `Z:\\` below.",
  "Open PowerShell **as administrator** in the VM and run:",
]);
code([
  "Set-Location Z:\\",
  "powershell -ExecutionPolicy Bypass -File .\\connect-vm.ps1",
]);
P("The script finds Python, checks it can reach the collector, installs the agent into `C:\\Program Files\\KYH\\Agent`, enrolls it with the one-time token, registers the scheduled task and waits for the first full report. That report includes a Windows Update search and can take a few minutes. You should see:");
code([
  "Python:    C:\\Program Files\\Python313\\python.exe",
  "Collector: https://192.168.56.1:8443",
  "Enrolled as ag_7d1c... for Kalinga Components Ltd. Config written to C:\\ProgramData\\KYH\\Agent\\config.json",
  "Installed. Useful commands (elevated PowerShell): ...",
  "Waiting for the first full report. The Windows Update search inside the PATCH check can take a few minutes...",
  "Scan requested (all checks). The running agent picks it up within its tick (about 30 s).",
  "",
  "  TIER       CONTROL           STATUS          ASSURANCE  SUMMARY",
  "  warranty   PATCH             PASS            OPERATING  No security updates pending",
  "  warranty   EDR               PASS            OPERATING  Microsoft Defender active, real-time protection on, ...",
  "  ...",
]);
P("On the laptop, type `hosts` at the `kyh>` prompt. The VM appears as a real host:");
code([
  "kyh> hosts",
  "  KAL-FIN-LT01       simulated  ONLINE      last seen 2026-10-27T09:12:40  all OK",
  "  ...",
  "  KAL-ACCT-VM01      REAL       ONLINE      last seen 2026-10-27T09:15:02  FAIL: DISK_ENCRYPTION, LOG_RETENTION, TIME_SYNC",
  "  reporting 5 of 5 declared endpoints",
]);
P("In the collector dashboard the VM's host page shows its real Windows version, ~not simulated~, with results marked TECHNICALLY_OBSERVED.");

// ================================================================= 6
H1("6. Part D: make the VM pass before you bind");
P("The company now has five endpoints, and a control passes for the company only when at least 95% of observed hosts pass it. With five hosts, one failing host gives 80%, so ~one~ failing VM fails the whole company. That is what makes the demonstration work, and it is also why the VM must be clean before you bind. Otherwise a warranty starts in IN_GRACE from the first minute.");
table("What a fresh VM reports, and what to do", ["Control", "Fresh VM", "What to do", "Affects"], [
  ["PATCH", "PASS once updated", "Windows Update until up to date", "Warranty"],
  ["EDR", "PASS", "Keep real-time protection on, signatures current", "Warranty"],
  ["BACKUP", "NOT_SUPPORTED (no backup software)", "`make-green` writes the backup marker (see below)", "Warranty"],
  ["MFA", "NOT_SUPPORTED, always", "Nothing: MFA is enforced by the identity provider, not visible from an endpoint", "Warranty (needs IdP evidence)"],
  ["DISK_ENCRYPTION", "FAIL (BitLocker off)", "Optional: turn on BitLocker (below)", "Quote only"],
  ["FIREWALL", "PASS", "Nothing", "Quote only"],
  ["EXPOSED_SERVICES", "PASS, with SMB (445) listed for review", "Nothing", "Quote only"],
  ["REMOTE_ACCESS", "NOT_APPLICABLE (RDP off)", "Nothing", "Quote only"],
  ["ADMIN_ACCOUNTS", "PASS (2 admins, Guest off)", "Nothing", "Quote only"],
  ["OS_SUPPORT", "PASS (26H2 Enterprise, to 2029-10-09)", "Nothing", "Quote only"],
  ["LOG_RETENTION", "FAIL (only days of logs)", "Leave it and explain it (below)", "Quote only"],
  ["TIME_SYNC", "FAIL (syncs to time.windows.com)", "`make-green` switches to NPL/NIC servers", "Quote only"],
], [2150, 2350, 3026, 1500]);
P("\"Warranty\" means the platform's four endpoint warranties (PATCH, EDR, BACKUP, MFA). \"Quote only\" controls feed the price before bind and show on the dashboards, but they never change a warranty after bind.");
P("Run this in the VM (administrator PowerShell, in the `vm-kit` folder):");
code(["powershell -ExecutionPolicy Bypass -File .\\kyh-vm-demo.ps1 make-green"]);
P("It does four things and then runs a full re-check:");
B([
  "**Writes the backup marker** `C:\\ProgramData\\KYH\\Agent\\backup-last-success` with the current time. In a real company the backup job writes this file after each successful run; the agent reads its age. The VM has no backup software, so the marker stands in for one. Say so if asked.",
  "**Points Windows Time at NPL and NIC** (`time.nplindia.org`, `samay1.nic.in`), as the CERT-In directions ask, and forces a sync.",
  "**Turns the firewall and real-time protection on** and updates Defender signatures.",
  "**Asks the agent for a full scan** and prints the table.",
]);
P("**LOG_RETENTION will still fail.** CERT-In asks for 180 days of logs; a VM installed this week has a few days. Real companies meet this by forwarding logs to a central store (Wazuh, Winlogbeat, Splunk and others are recognised). It is a useful example of an honest FAIL that the agent cannot fix by itself, and it does not touch any warranty.");
P("**Optional: BitLocker.** Take a snapshot first, then in an administrator PowerShell run the command below. Wait until `Get-BitLockerVolume C:` shows FullyEncrypted, then run `kyh-vm-demo.ps1 scan`.");
code(["Enable-BitLocker -MountPoint C: -EncryptionMethod XtsAes128 -UsedSpaceOnly -TpmProtector -SkipHardwareTest"]);
P("**Check before you bind.** On the laptop, `hosts` must show no FAIL for PATCH, EDR or BACKUP on the VM. The `bind` command checks this for you and refuses with the reason if the VM is not ready (`bind --force` overrides it). Then shut the VM down and take a snapshot named `demo-ready` (Section 3.7).");

// ================================================================= 7
H1("7. Part E: the demonstration");
H2("7.1 Thirty minutes before");
N([
  "Start the VM (restore `demo-ready` if anything was changed since).",
  "Laptop: `py run_linked_demo.py --vm-ip 192.168.56.1`.",
  "VM: `connect-vm.ps1`, then `kyh-vm-demo.ps1 make-green`. Every start of the demo begins with empty demo data, so the VM must connect again each time. The shared folder already holds the new token.",
  "Laptop: `hosts` shows 5 of 5 reporting and the VM passes PATCH, EDR and BACKUP.",
  "Open both dashboards and log in. Keep the VM's PowerShell window visible next to the browser.",
]);
H2("7.2 The run (about ten minutes)");
figure("vm_fig2_flow.png", "The main sequence of the demonstration. Agent re-check takes up to 30 s, the collector pushes within 5 s; refresh the platform page.");
table("Demonstration steps", ["#", "You do", "The panel sees", "Point to make"], [
  ["1", "Collector dashboard → Kalinga Components → the VM's host page", "Five endpoints: four labelled SIMULATED, one REAL Windows 11 with its own build number", "Twelve read-only checks run as SYSTEM on a real machine; every report is signed and numbered"],
  ["2", "VM: `kyh-vm-demo.ps1 policy`", "What is collected and what is never collected", "No files, browsing, keystrokes or user names; a local copy of every report stays on the machine (`sent.jsonl`)"],
  ["3", "Platform → company → Monitoring tab", "Fleet evidence recorded as AGENT_FLEET, TECHNICALLY_OBSERVED", "Before bind, monitoring is evidence for the quote like any document"],
  ["4", "Laptop `kyh>`: `bind` (it checks the VM first; the UI Bind button does not)", "Policy BOUND, premium fixed, warranties MET", "Pricing happens once, here"],
  ["5", "VM: `kyh-vm-demo.ps1 defender-off`", "VM prints EDR FAIL. Collector: EDR 4/5 hosts. Platform (refresh): EDR IN_GRACE, 7-day grace, \"incident-response deductible doubled\"", "A real change on a real machine reaches the insurer in about a minute. The premium does not move."],
  ["6", "VM: `kyh-vm-demo.ps1 defender-on`", "EDR PASS; platform REMEDIATED then MET; event history kept", "Fixing it restores cover; nothing is re-priced"],
  ["7 (opt.)", "`defender-off`, then `kyh>` `fast-forward`, refresh, then `defender-on`", "BREACHED, then REMEDIATED and MET", "`fast-forward` is demo-only and written to the audit log as DEMO_TIME_TRAVEL"],
  ["8 (opt.)", "`backup-stale`, then `backup-ok`", "BACKUP warranty IN_GRACE, then MET", "A second warranty, driven by a different check"],
  ["9 (opt.)", "`firewall-off`, then `firewall-on`", "Secure configuration fails in the fleet table; no warranty changes", "Only warranty controls carry consequences after bind"],
], [700, 2400, 3000, 2926]);
P("**Silence.** If asked what happens when someone uninstalls the agent: the host turns UNVERIFIED after 6 hours and SILENT after 72. A silent host whose last result failed keeps counting as failing, so removing the agent hides nothing. One whose last result passed (a laptop switched off for leave) is left out of the roll-up for up to 14 days, then counts as failing. Silent hosts never count towards coverage. That cannot be shown live in a viva; the collector tests cover it, including 10 of 100 machines on leave for 10 days.");
P("**If a change seems slow.** The agent picks up the re-check request at its next tick (up to 30 seconds) and the collector pushes within 5 seconds. The platform page does not refresh itself, so refresh it.");

// ================================================================= 8
H1("8. Next time, and cleaning up");
B([
  "**Every start of the demo wipes the demo data** (`run_linked_demo.py`), so run `connect-vm.ps1` in the VM again each time. The kit in the shared folder is rewritten with the new token; `README.txt` in it shows when.",
  "**The certificate is kept** in `demo-tls\\` and made again only if you pass a different `--vm-ip`. The browser warning therefore appears once per browser.",
  "**Snapshots.** If the VM gets into a strange state, shut it down and restore `demo-ready` (Section 3.7), then run `connect-vm.ps1` and `make-green` again (this also fixes the clock after a restore). Guest Additions normally correct the clock on their own within a minute.",
  "**Pausing between sessions.** Closing the VM window with **Save the machine state** resumes it exactly where it was, which is quicker than a full start. The agent will have been quiet in the meantime, so run `kyh-vm-demo.ps1 scan` after resuming.",
  "**The evaluation licence lasts 90 days.** Installed on 27 October 2026, it runs out around 25 January 2027, after which Windows restarts itself every hour. If the viva is later, install closer to the date.",
  "**Backing up the VM.** **File → Export Appliance** produces one `.ova` file you can copy to a teammate's laptop as a spare for the viva.",
  "**After the viva:** remove the agent with `agent\\install\\windows\\uninstall.ps1`, turn Tamper Protection back on, and on the laptop run `Remove-NetFirewallRule -DisplayName \"Beretta demo collector (VM)\"`.",
]);

// ================================================================= 9
H1("9. Troubleshooting");
table("Problems and fixes", ["Symptom", "Likely cause", "Fix"], [
  ["CERTIFICATE_VERIFY_FAILED: Missing Authority Key Identifier", "Certificate made by an older kit; Python 3.13 and newer check certificates strictly", "Use the latest suite zip; the demo then replaces the old `demo-tls` folder by itself. Re-run `connect-vm.ps1` in the VM"],
  ["VirtualBox: \"VT-x is not available\" (VERR_VMX_NO_VMX) or \"AMD-V is disabled\"", "Virtualization is off in the laptop BIOS, or another hypervisor holds it", "Turn on VT-x / AMD-V in the BIOS; see Section 3.8"],
  ["Green turtle in the status bar; the VM is very slow", "Windows' Hyper-V is running under VirtualBox", "Section 3.8"],
  ["Windows setup: \"This PC can't run Windows 11\"", "EFI, Secure Boot or TPM 2.0 missing in the VM", "Settings → System → Motherboard: EFI and Secure Boot ticked, TPM v2.0 (Section 3.3)"],
  ["No `192.168.56.x` address in the VM", "Adapter 2 not attached, or the host-only network has no DHCP server", "Settings → Network → Adapter 2 = Host-only Adapter; File → Tools → Network Manager → DHCP Server enabled (Section 3.4)"],
  ["`192.168.56.1` missing on the laptop (`ipconfig`)", "The host-only network was deleted or not created", "File → Tools → Network Manager → Create; restart the laptop if Windows does not show it at once"],
  ["No `vm-kit` drive in the VM", "Guest Additions missing, or the share was added without Auto-mount", "Install Guest Additions (Section 3.5); edit the share and tick Auto-mount and Make Permanent; restart the VM"],
  ["Mouse or keyboard stuck inside the VM", "The VM has captured input", "Press the right Ctrl key (the Host key) once"],
  ["`connect-vm.ps1`: Cannot reach 192.168.56.1:8443", "Demo not running; adapter 2 not host-only; firewall rule missing; or an old Block rule for Python", "In the VM: `Test-NetConnection 192.168.56.1 -Port 8443`. On the laptop, remove Block rules: `Get-NetFirewallRule -DisplayName python* | Where-Object Action -eq Block | Remove-NetFirewallRule`"],
  ["\"running scripts is disabled on this system\"", "PowerShell execution policy", "Use the `powershell -ExecutionPolicy Bypass -File ...` form shown in this guide"],
  ["Enrollment refused (401 or 403)", "Token from an earlier demo run", "Use the current `connect-vm.ps1` from the shared folder (check the time in `README.txt`)"],
  ["CERTIFICATE_VERIFY_FAILED", "Demo started with a different `--vm-ip` than the VM uses", "Start the demo with the host-only IP and re-run `connect-vm.ps1`"],
  ["Demo fails creating the certificate", "No openssl and no `cryptography`", "Install Git for Windows, or `py -m pip install cryptography`"],
  ["Python not found", "Python not installed in the VM", "Install Python 3.13 for all users (Section 3.6)"],
  ["`scan-now` says \"No scan seen yet\"", "The scheduled task is not running", "`Start-ScheduledTask \"KYH Live Monitoring Agent\"`; read `C:\\ProgramData\\KYH\\Agent\\agent-errors.log`"],
  ["A check shows ERROR", "First run of that Windows check on this build", "Send the output of `kyh-vm-demo.ps1 status` and `agent-errors.log`"],
  ["PATCH FAIL: updates pending", "Windows Update not finished", "Install, restart, `kyh-vm-demo.ps1 scan`"],
  ["EDR FAIL: signatures old", "Defender not updated", "`Update-MpSignature`, then `kyh-vm-demo.ps1 scan`"],
  ["`defender-off` warns about Tamper Protection", "Tamper Protection is on", "Turn it off (Section 3.6, step 5) and run again"],
  ["TIME_SYNC: not synchronised", "The network blocks NTP (UDP 123), common on campus", "Try another network, or explain it: it is a quote-only control"],
  ["VM shows UNVERIFIED or SILENT", "VM was off or asleep", "`kyh-vm-demo.ps1 scan`"],
  ["Platform still shows the old state", "Page not refreshed", "Refresh; type `status` at `kyh>` to see the platform's view"],
  ["`bind` refuses", "VM fails PATCH, EDR or BACKUP, or is not reporting", "Fix what it lists (`make-green`), or `bind --force`"],
], [2800, 2450, 3776]);

// ================================================================= 10
H1("10. What was added for this guide");
table("Code changes", ["Where", "Change"], [
  ["Agent", "`kyh_agent scan-now [--control X] [--wait N]`: asks the running service to re-check now. The service stays the only process that scans and sends, so sequence numbers stay in order."],
  ["Agent policy", "Windows 11 26H2 (build 26300) lifecycle dates: Pro 2028-10-10, Enterprise 2029-10-09 [2]."],
  ["Agent and collector", "Requests to localhost and private addresses skip any system proxy. Found while testing: with a proxy configured, Python sent the VM's reports to the proxy."],
  ["Collector", "`gen-cert` finds the openssl that ships with Git for Windows and falls back to the `cryptography` package."],
  ["Windows installer", "The Python path in the scheduled task is quoted (`C:\\Program Files` contains a space)."],
  ["`run_linked_demo.py`", "`--vm-ip`: HTTPS on the host-only address only, a fifth declared endpoint, the `vm-kit` folder, and the `hosts`, `vm` and checked `bind` commands."],
  ["`vm-kit`", "`connect-vm.ps1` (install and enroll) and `kyh-vm-demo.ps1` (15 actions: `status`, `policy`, `scan`, `make-green`, and eleven that each change one real setting and re-check it)."],
], [2200, 6826]);
P("Tests: Part 1 32, Part 2 155, integration 1, all passing. The VM path was also tested end to end in the build environment with a real (Linux) agent run from the generated kit. It enrolled with the kit's CA and was accepted as a trusted build. A stale backup moved the platform's BACKUP warranty to IN_GRACE within ten seconds, and a fresh one brought it back to MET.");
P("**One limit to keep in mind.** The Windows checks are unit-tested against recorded Windows output, but this VM is the first time they run on a real Windows machine. If any check shows ERROR, that is a bug to fix, not a setup mistake.");

body.push(new Paragraph({ children: [new PageBreak()] }));
H1("References");
[
  "[1] Microsoft, \"Windows 11 Enterprise evaluation,\" Microsoft Evaluation Center. [Online]. Available: https://www.microsoft.com/en-in/evalcenter/evaluate-windows-11-enterprise. [Accessed: 27-Oct-2026].",
  "[2] Microsoft, \"Windows 11 release information,\" Microsoft Learn. [Online]. Available: https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information. [Accessed: 27-Oct-2026].",
  "[3] Pureinfotech, \"VirtualBox 7 brings TPM and Secure Boot support for Windows 11,\" Pureinfotech. [Online]. Available: https://pureinfotech.com/virtualbox-7-tpm-secure-boot-windows-11/. [Accessed: 27-Oct-2026].",
  "[4] Indian Computer Emergency Response Team, \"Directions under sub-section (6) of section 70B of the Information Technology Act, 2000,\" No. 20(3)/2022-CERT-In, 28 Apr. 2022.",
  "[5] Oracle, \"Creating a New Virtual Machine,\" Oracle VirtualBox 7.2 User Guide. [Online]. Available: https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/create-vm.html. [Accessed: 27-Oct-2026].",
  "[6] Kicksecure, \"VirtualBox: Green Turtle Issue.\" [Online]. Available: https://www.kicksecure.com/wiki/VirtualBox/Green_Turtle_Issue. [Accessed: 27-Oct-2026].",
].forEach((r) => body.push(new Paragraph({ children: runs(r), spacing: { after: 120, line: 300 }, indent: { left: 540, hanging: 540 } })));

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
  title: "Beretta: Live Monitoring on a Windows VM",
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
  const out = path.join(__dirname, "Beretta_VM_Setup_and_Demo_Guide.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, `(${figN} figures, ${tabN} tables)`);
});
