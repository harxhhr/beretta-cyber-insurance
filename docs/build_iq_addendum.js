// Builds kyh-cyber-insurance/frontend/forms/CyberUW-IQ-1.1-Addendum.docx  (node build_iq_addendum.js)
// The pricing V2 addendum to the CYBERUW-IQ-1.0 proposal form: the fields V2 rates on that the 1.0 form
// does not ask. Existing questions are cross-referenced, not repeated.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, ShadingType,
  BorderStyle, Footer, PageNumber, HeadingLevel,
} = require("docx");

const FONT = "Times New Roman";
const W = 9026; // A4 text width in DXA with 1" margins
const LINE = { style: BorderStyle.SINGLE, size: 4, color: "9AA4B5" };
const borders = { top: LINE, bottom: LINE, left: LINE, right: LINE };

const t = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || 22, bold: o.bold, italics: o.italics });
const P = (text, o = {}) => new Paragraph({ spacing: { after: o.after ?? 120, line: 300 }, alignment: o.align,
  children: Array.isArray(text) ? text : [t(text, o)] });
const H = text => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 },
  children: [new TextRun({ text, font: FONT, size: 24, bold: true })] });

function cell(children, width, shade) {
  return new TableCell({ width: { size: width, type: WidthType.DXA }, borders,
    shading: shade ? { type: ShadingType.CLEAR, color: "auto", fill: shade } : undefined,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: (Array.isArray(children) ? children : [children]).map(c => typeof c === "string" ? P(c, { after: 0 }) : c) });
}

function form(rows, widths = [900, 5126, 3000]) {
  const head = new TableRow({ tableHeader: true, children: ["Ref", "Question", "Response"].map((h, i) =>
    cell(P([t(h, { bold: true })], { after: 0 }), widths[i], "EAEDF1")) });
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths,
    rows: [head, ...rows.map(([ref, q, resp]) => new TableRow({ children: [
      cell(P([t(ref, { bold: true })], { after: 0 }), widths[0]), cell(q, widths[1]), cell(resp || "", widths[2])] }))] });
}

const box = "☐";
const yn = `${box} Yes   ${box} No`;
const ynd = `${box} Yes   ${box} No   ${box} Don't know`;

const controls = [
  ["R6.1", "Multi-factor authentication enforced for remote access, email and privileged accounts (F)"],
  ["R6.2", "Endpoint detection and response running on managed endpoints (H)"],
  ["R6.3", "Backups that have been restore-tested in the last 12 months (J)"],
  ["R6.4", "Critical vulnerabilities patched within 7 days (I)"],
  ["R6.5", "High-severity vulnerabilities patched within 7 days (I)"],
  ["R6.6", "Endpoint privilege management: local administrator rights removed or controlled (F)"],
  ["R6.7", "Hardening baselines (CIS or equivalent) applied; no internet-exposed RDP/SMB (E)"],
  ["R6.8", "Central logging with alerting reviewed by a SOC or SIEM (H)"],
  ["R6.9", "Phishing simulation for all staff at least once a year (N)"],
  ["R6.10", "Email attachment sandboxing, with SPF, DKIM and DMARC enforced (G)"],
  ["R6.11", "A written incident response plan, exercised in the last 12 months (N)"],
  ["R6.12", "Full-disk encryption on endpoints and encryption at rest for data stores (C)"],
];

const children = [
  P([t("Beretta · CyberUW", { bold: true, size: 20 })], { after: 0 }),
  P([t("Cyber Insurance Proposal Form: Rating Addendum", { bold: true, size: 32 })], { after: 60 }),
  P([t("CYBERUW-IQ-1.1 Addendum · attach to CYBERUW-IQ-1.0 · pricing model UNDERWRITING_MODEL_V2", { size: 20 })], { after: 200 }),
  P("Complete this addendum with the full proposal form. It asks the facts the premium model rates on that the 1.0 form does not ask directly. Where a question already exists in the 1.0 form, it is referenced, not repeated. Answer \"Don't know\" rather than guess: an unknown control is priced the same as a missing one, but a wrong answer can void cover (R8)."),

  H("Section R1–R4 · Classification"),
  form([
    ["R1", [P("NIC 2008 code of the main business activity (at least the 2-digit division; 4 or 5 digits if known).", { after: 40 }),
      P([t("The division sets the rating sector, for example 62 computer programming, 86 human health, 47 retail trade.", { italics: true, size: 20 })], { after: 0 })], ""],
    ["R2", "Annual turnover for the last full financial year, in ₹ (see also B1.1).", "₹"],
    ["R3", "Years in operation (see also A3, year established).", ""],
    ["R4", [P("Is the company regulated by the Reserve Bank of India or the Securities and Exchange Board of India?", { after: 40 }),
      P([t("If yes, name the regulator and the registration or licence number.", { italics: true, size: 20 })], { after: 0 })], yn],
  ]),

  H("Section R5 · Material incidents"),
  P([t("A material incident", { bold: true }), t(" is any cyber incident in the last 3 years that caused a financial loss above the retention applied for in Section P, or required a notification under the DPDP Act 2023 or to CERT-In, or involved a decision on whether to pay a ransom.")]),
  form([
    ["R5.1", "Number of material incidents in the last 3 years.", ""],
    ["R5.2", "For each one: date, type, loss in ₹, and whether it was notified (also describe in Section O).", ""],
  ]),

  H("Section R6 · Priced security controls"),
  P("These are the controls the premium depends on. The letter in brackets is the 1.0 section with the detailed questions. A control evidenced by the monitoring agent or an independent report (SOC 2 Type II, ISO 27001 SoA, VAPT, scanner export, restore-test report) earns its full credit; a \"Yes\" without evidence earns part of it."),
  form(controls.map(([ref, q]) => [ref, q, ynd])),

  H("Section R7 · Payment verification (not priced)"),
  form([
    ["R7", [P("Are payment-instruction changes and new payees verified by a call-back to a known number, or by dual approval, before any funds are sent? (see also M4)", { after: 40 }),
      P([t("Recorded for underwriting and claims; no published effect size exists yet, so it does not change the premium.", { italics: true, size: 20 })], { after: 0 })], ynd],
  ]),

  H("Section R8 · Declaration"),
  P("I declare that the answers in this addendum and in the proposal form are true and complete to the best of my knowledge, and that I have not withheld any material fact. I understand that a false statement, or the non-disclosure of a material fact, may void cover from inception, including cover for any claim arising from the matter misstated. I will tell the insurer promptly if any answer changes before the policy is bound."),
  P(" "),
  form([
    ["", "Name and designation of the authorised signatory", ""],
    ["", "Signature", ""],
    ["", "Date and place", ""],
  ], [900, 4126, 4000]),
];

const doc = new Document({
  creator: "Beretta capstone team", title: "CYBERUW-IQ-1.1 Rating Addendum",
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: "CYBERUW-IQ-1.1 Addendum · Page ", font: FONT, size: 18 }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 })] })] }) },
    children,
  }],
});

const out = path.join(__dirname, "..", "kyh-cyber-insurance", "frontend", "forms", "CyberUW-IQ-1.1-Addendum.docx");
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(out, buf); console.log("wrote", out); });
