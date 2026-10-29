// Builds docs/report/Beretta_Capstone_Final_Report.docx in the MPSTME capstone report format
// (Guidelines, Capstone Project, B.Tech / MBA Tech, Annexure A.8).
//   node docs/report/build_report.js     then   powershell -File docs/report/finish_with_word.ps1
// Page layout from A.8: Times New Roman; 1.5 line spacing; left margin 1.5", other margins 1"; header left =
// project title, header right = academic year; footer right = page number; chapter titles 18 bold, section
// titles 14 bold, subsection titles 12 bold; figure names below figures and table names above tables, 10 pt;
// body 12 pt; front-matter lists numbered in Roman, chapters from 1 in decimal.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, AlignmentType, HeadingLevel,
  WidthType, ShadingType, BorderStyle, Header, Footer, PageNumber, LevelFormat, PageBreak, NumberFormat,
  TabStopType, Tab, Bookmark, PageReference, VerticalAlign, HighlightColor, UnderlineType, TableLayoutType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const OUT = path.join(__dirname, "Beretta_Capstone_Final_Report.docx");
const FONT = "Times New Roman";
const MONO = "Consolas";
const PAGE_W = 11906, PAGE_H = 16838;                  // A4, as in the guideline document
const M_LEFT = 2160, M_OTHER = 1440;                  // 1.5" and 1"
const TEXT_W = PAGE_W - M_LEFT - M_OTHER;             // 8306 twips = 5.77"
const MAX_IMG_W = 545, MAX_IMG_H = 760;               // pixels at 96 dpi inside the text area

const META = {
  title: "Beretta: An Explainable Cyber-Insurance Underwriting and Continuous Warranty Monitoring Platform for Indian SMEs",
  short: "Beretta: Explainable Cyber Insurance for Indian SMEs",
  year: "2026-27",
  program: "B.Tech. + MBA (Tech.) Integrated Programme",
  stream: "[Name of the stream]",
  students: [["Harsh Rathod", "K080", "[SAP ID]"], ["Yugandhara Raj Goud", "K023", "[SAP ID]"],
             ["Krish Mundhra", "K041", "[SAP ID]"]],
  mentor: "Prof. Rohit Suryawanshi",
  mentorRole: "Designation, Name of the department",
};

// ---------------------------------------------------------------- inline markup
// **bold**  ~italic~  `code`  [[placeholder]] (yellow, to be filled in by the team)
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|~[^~]+~|\[\[[^\]]+\]\])/g;
  let last = 0, m;
  const push = (t, o) => out.push(new TextRun({ text: t, font: FONT, ...base, ...o }));
  while ((m = re.exec(text))) {
    if (m.index > last) push(text.slice(last, m.index), {});
    const t = m[0];
    if (t.startsWith("**")) push(t.slice(2, -2), { bold: true });
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: MONO, size: (base.size || 24) - 3 }));
    else if (t.startsWith("[[")) push(t.slice(2, -2), { highlight: HighlightColor.YELLOW });
    else push(t.slice(1, -1), { italics: true });
    last = m.index + t.length;
  }
  if (last < text.length) push(text.slice(last), {});
  return out;
}

// ---------------------------------------------------------------- references (IEEE, numbered by first citation)
const REFS = require("./references.js");
const refOrder = [];
function cite(...keys) {
  const nums = keys.map((k) => {
    if (!REFS[k]) throw new Error("unknown reference " + k);
    if (!refOrder.includes(k)) refOrder.push(k);
    return refOrder.indexOf(k) + 1;
  });
  return nums.map((n) => `[${n}]`).join(", ");
}

// ---------------------------------------------------------------- document model
let body = [];                       // the current section's children
const sections = {};
const toc = [];                      // [level, label, text, bookmark]
const figs = [], tabs = [];          // [number, caption, bookmark]
let chap = "0", figN = 0, tabN = 0, bm = 0, listInst = 0;
const nextBm = (p) => `${p}${++bm}`;

const LINE = 360;                    // 1.5 lines
const P = (t, o = {}) => body.push(new Paragraph({ children: runs(t), alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 120, line: LINE }, ...o }));
const PC = (t, o = {}) => body.push(new Paragraph({ children: runs(t), alignment: AlignmentType.CENTER,
  spacing: { after: 120, line: LINE }, ...o }));
function B(items, ref = "bul") {
  listInst += 1;
  const inst = listInst;
  for (const t of items) body.push(new Paragraph({ children: runs(t), alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: ref, level: 0, instance: inst }, spacing: { after: 60, line: LINE } }));
  body.push(new Paragraph({ spacing: { after: 60 }, children: [] }));
}
const N = (items) => B(items, "num");
function EQ(t, label) {   // a displayed equation, centred, with its number on the right
  body.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 60, after: 120, line: LINE },
    tabStops: [{ type: TabStopType.CENTER, position: Math.round(TEXT_W / 2) }, { type: TabStopType.RIGHT, position: TEXT_W }],
    children: [new TextRun({ children: [new Tab()] }), ...runs(t, { italics: false }),
      ...(label ? [new TextRun({ children: [new Tab(), `(${label})`], font: FONT })] : [])] }));
}
function CODE(lines) {
  const border = { style: BorderStyle.SINGLE, size: 4, color: "B8BEC8" };
  body.push(new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: [TEXT_W],
    rows: [new TableRow({ children: [new TableCell({
      borders: { top: border, bottom: border, left: border, right: border },
      shading: { type: ShadingType.CLEAR, color: "auto", fill: "F4F5F7" },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: lines.map((l) => new Paragraph({ spacing: { after: 0, line: 240 },
        children: [new TextRun({ text: l || " ", font: MONO, size: 17 })] })) })] })] }));
  body.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
}

// headings: chapter = "Chapter n" + title, 18 bold, centred, new page
function CH(num, title) {
  chap = String(num); figN = 0; tabN = 0;
  const id = nextBm("ch");
  toc.push([1, `Chapter ${num}`, title, id]);
  body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 360, line: LINE },
    children: [new Bookmark({ id, children: [new TextRun({ text: `Chapter ${num}` })] }),
      new TextRun({ text: title, break: 1 })] }));
}
function UNNUMBERED(title, level = 1, label = "") {   // References, appendices
  const id = nextBm("un");
  toc.push([level, label, title, id]);
  body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 360, line: LINE },
    children: [new Bookmark({ id, children: [new TextRun({ text: label ? `${label}: ${title}` : title })] })] }));
}
function H2(num, title) {
  const id = nextBm("s");
  toc.push([2, num, title, id]);
  body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true,
    children: [new Bookmark({ id, children: [new TextRun({ text: `${num} ${title}` })] })] }));
}
function H3(num, title) {
  const id = nextBm("ss");
  toc.push([3, num, title, id]);
  body.push(new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true,
    children: [new Bookmark({ id, children: [new TextRun({ text: `${num} ${title}` })] })] }));
}

// ---------------------------------------------------------------- figures and tables
function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.toString("ascii", 1, 4) === "PNG") return [b.readUInt32BE(16), b.readUInt32BE(20)];
  let i = 2;                                              // JPEG: find the SOF marker
  while (i < b.length) {
    const marker = b[i + 1], len = b.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc3) return [b.readUInt16BE(i + 7), b.readUInt16BE(i + 5)];
    i += 2 + len;
  }
  throw new Error("no size for " + file);
}
function imageRun(file, maxW = MAX_IMG_W, maxH = MAX_IMG_H) {
  const [w, h] = pngSize(file);
  const s = Math.min(maxW / w, maxH / h);
  return new ImageRun({ type: file.endsWith(".jpg") ? "jpg" : "png", data: fs.readFileSync(file),
    transformation: { width: Math.round(w * s), height: Math.round(h * s) },
    altText: { title: path.basename(file), description: path.basename(file), name: path.basename(file) } });
}
function FIG(rel, caption, maxW = MAX_IMG_W, maxH = MAX_IMG_H) {
  const file = path.join(ROOT, rel);
  if (!fs.existsSync(file)) throw new Error("missing figure " + rel);
  figN += 1;
  const num = `${chap}.${figN}`, id = nextBm("f");
  figs.push([num, caption, id]);
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
    children: [imageRun(file, maxW, maxH)] }));
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240, line: 276 },
    children: [new Bookmark({ id, children: [new TextRun({ text: `Fig. ${num} `, bold: true, font: FONT, size: 20 })] }),
      ...runs(caption, { size: 20 })] }));
  return `Fig. ${num}`;
}
const peekFig = (k = 1) => `Fig. ${chap}.${figN + k}`;
const peekTab = (k = 1) => `Table ${chap}.${tabN + k}`;
const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
const cellBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
function TAB(caption, headers, rows, widths, o = {}) {
  tabN += 1;
  const num = `${chap}.${tabN}`, id = nextBm("t");
  tabs.push([num, caption, id]);
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 80 },
    children: [new Bookmark({ id, children: [new TextRun({ text: `Table ${num} `, bold: true, font: FONT, size: 20 })] }),
      ...runs(caption, { size: 20 })] }));
  const total = widths.reduce((a, b) => a + b, 0);
  const scale = TEXT_W / total;
  const ws = widths.map((w) => Math.round(w * scale));
  const sz = o.size || 20;
  const cell = (t, i, head) => new TableCell({
    borders: cellBorders, width: { size: ws[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: "E7E9ED" } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: String(t).split("\n").map((line) => new Paragraph({ spacing: { after: 0, line: 252 },
      alignment: o.align && o.align[i] === "r" ? AlignmentType.RIGHT : (o.align && o.align[i] === "c" ? AlignmentType.CENTER : AlignmentType.LEFT),
      children: runs(line, { size: sz, bold: head || undefined }) })),
  });
  body.push(new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: ws, layout: TableLayoutType.FIXED,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, i, false)) }))] }));
  body.push(new Paragraph({ spacing: { after: 160 }, children: [] }));
  return `Table ${num}`;
}

// A full source file for Appendix E: a bold heading with the path, size and purpose, then every line in
// 7 pt Consolas, single spaced. Long lines wrap with a hanging indent so the continuation is visible.
let srcLines = 0, srcFiles = 0;
function SRC(rel, purpose) {
  const file = path.join(ROOT, rel);
  const text = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n").replace(/\t/g, "    ").replace(/\n+$/, "");
  const lines = text.split("\n");
  srcLines += lines.length; srcFiles += 1;
  body.push(new Paragraph({ keepNext: true, spacing: { before: 240, after: 60, line: 276 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "808080", space: 2 } },
    children: [new TextRun({ text: rel, font: MONO, size: 19, bold: true }),
      new TextRun({ text: `   ${lines.length} lines`, font: FONT, size: 19 })] }));
  if (purpose) body.push(new Paragraph({ keepNext: true, spacing: { after: 80, line: 260 },
    children: runs(purpose, { size: 19, italics: true }) }));
  for (const l of lines) body.push(new Paragraph({ style: "SourceCode", children: [new TextRun({ text: l || " " })] }));
}

const h = { P, PC, B, N, EQ, CODE, CH, H2, H3, FIG, TAB, SRC, cite, peekFig, peekTab, UNNUMBERED,
  newSection: (name) => { body = []; sections[name] = body; }, chapterLetter: (c) => { chap = c; figN = 0; tabN = 0; } };

// ---------------------------------------------------------------- the chapters (written first, so numbering is known)
h.newSection("main");
require("./ch1_ch2.js")(h);
require("./ch3.js")(h);
require("./ch4_ch6.js")(h);

// references
UNNUMBERED("References");
refOrder.forEach((k, i) => body.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 100, line: 300 },
  indent: { left: 640, hanging: 640 }, tabStops: [{ type: TabStopType.LEFT, position: 640 }],
  children: [new TextRun({ text: `[${i + 1}]`, font: FONT, size: 22 }), new TextRun({ children: [new Tab()], font: FONT }),
    ...runs(REFS[k], { size: 22 })] })));
const unused = Object.keys(REFS).filter((k) => !refOrder.includes(k));
if (unused.length) throw new Error("references never cited: " + unused.join(", "));
require("./appendices.js")(h);

// ---------------------------------------------------------------- front matter
const blank = (n = 1) => [...Array(n)].map(() => new Paragraph({ children: [] }));
const C = (text, size, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 120, line: o.line ?? 300 },
  children: [new TextRun({ text, font: FONT, size, bold: o.bold, color: o.color, italics: o.italics,
    underline: o.underline ? { type: UnderlineType.SINGLE } : undefined,
    highlight: o.highlight ? HighlightColor.YELLOW : undefined })] });
// The university logo is not in the repository; put nmims_logo.jpg next to this file to include it.
const LOGO = path.join(__dirname, "nmims_logo.jpg");
if (!fs.existsSync(LOGO)) console.warn("nmims_logo.jpg not found: building without the logo");
const logo = (wpx) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120 },
  children: fs.existsSync(LOGO) ? [imageRun(LOGO, wpx, wpx)] : [] });
const BLUE = "2F5496";

const title = [
  ...blank(1),
  C(META.title, 36, { bold: true, after: 360, line: 360 }),
  C("Project Report submitted in the partial fulfilment", 26, { after: 60 }),
  C("of", 26, { after: 60 }),
  C(META.program, 26, { color: BLUE, after: 60 }),
  C("In", 26, { color: BLUE, after: 60 }),
  C(META.stream, 26, { color: BLUE, highlight: true, after: 240 }),
  C("by", 22, { after: 120 }),
  ...META.students.map(([n, r]) => C(`${n} (${r})`, 26, { bold: true, after: 40 })),
  C("", 22, { after: 120 }),
  C("Under the supervision of", 22, { after: 60 }),
  C(META.mentor, 24, { underline: true, after: 40 }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 },
    children: [new TextRun({ text: "(", font: FONT, size: 22 }), ...runs("[[" + META.mentorRole + "]], MPSTME", { size: 22 }),
      new TextRun({ text: ")", font: FONT, size: 22 })] }),
  C("SVKM's NMIMS University", 34, { bold: true, after: 40 }),
  C("(Deemed-to-be University)", 20, { after: 120 }),
  logo(140),
  C("MUKESH PATEL SCHOOL OF TECHNOLOGY", 30, { bold: true, after: 20 }),
  C("MANAGEMENT & ENGINEERING (MPSTME)", 30, { bold: true, after: 20 }),
  C("Vile Parle (W), Mumbai-56", 26, { after: 120 }),
  C(META.year, 26, { after: 0 }),
  new Paragraph({ children: [new PageBreak()] }),
];

const names = META.students.map(([n, r]) => `${n} (${r})`);
const certificate = [
  logo(140),
  C("CERTIFICATE", 34, { bold: true, underline: true, after: 480 }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 240, line: LINE },
    children: runs(`This is to certify that the project entitled "${META.title}" has been done by ${names[0]}, ` +
      `${names[1]} and ${names[2]} under my guidance and supervision and has been submitted in partial fulfilment of ` +
      `the degree of ${META.program} in [[${META.stream.replace(/[[\]]/g, "")}]] of MPSTME, SVKM's NMIMS ` +
      `(Deemed-to-be University), Mumbai, India.`) }),
  ...blank(3),
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }], spacing: { after: 0 },
    children: [new TextRun({ text: "_______________________", font: FONT }), new TextRun({ children: [new Tab(), "_______________________"], font: FONT })] }),
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }], spacing: { after: 0 },
    children: [new TextRun({ text: `Project mentor: ${META.mentor}`, font: FONT }), new TextRun({ children: [new Tab(), "Examiner (name and signature)"], font: FONT })] }),
  new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: "(Internal Guide)", font: FONT })] }),
  new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: "Date:", font: FONT })] }),
  ...blank(3),
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }], spacing: { after: 0 },
    children: [new TextRun({ text: "Place: Mumbai", font: FONT }), new TextRun({ children: [new Tab(), "_______________________"], font: FONT })] }),
  new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 0 },
    children: [new TextRun({ text: "(HoD) (name and signature)", font: FONT })] }),
  new Paragraph({ children: [new PageBreak()] }),
];

const frontHead = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 },
  children: [new TextRun({ text: t, bold: true, font: FONT, size: 32 })] });
const just = (t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 160, line: LINE }, children: runs(t) });
const FM = require("./front_matter.js");
function plainTable(headers, rows, widths, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0), ws = widths.map((w) => Math.round(w * TEXT_W / total));
  const cell = (t, i, head) => new TableCell({ borders: cellBorders, width: { size: ws[i], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: "E7E9ED" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ alignment: (o.align || [])[i] === "c" ? AlignmentType.CENTER : AlignmentType.LEFT,
      spacing: { after: 0, line: 276 }, children: Array.isArray(t) ? t : runs(String(t), { size: 22, bold: head || undefined }) })] });
  return new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: ws, layout: TableLayoutType.FIXED,
    rows: [new TableRow({ tableHeader: true, children: headers.map((x, i) => cell(x, i, true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((x, i) => cell(x, i, false)) }))] });
}
const pref = (id) => [new TextRun({ children: [new PageReference(id)], font: FONT, size: 22 })];

const acknowledgement = [
  frontHead("ACKNOWLEDGEMENT"),
  ...FM.acknowledgement.map(just),
  ...blank(1),
  plainTable(["Student Name", "Roll No.", "SAP ID"], META.students.map(([n, r, s]) => [n, r, runs(`[[${s.replace(/[[\]]/g, "")}]]`, { size: 22 })]),
    [4200, 1800, 2300], { align: ["l", "c", "c"] }),
];

const abstract = [frontHead("ABSTRACT"), ...FM.abstract.map(just),
  new Paragraph({ spacing: { before: 200, line: LINE }, alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text: "Keywords: ", bold: true, font: FONT }), ...runs(FM.keywords)] }),
  new Paragraph({ children: [new PageBreak()] })];

// Table of contents, laid out as in A.8 ("Topics | Page")
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const nb = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };
const frontIds = { lof: "fm_lof", lot: "fm_lot", abb: "fm_abb" };
const tocRows = [
  [0, "List of Figures", frontIds.lof], [0, "List of Tables", frontIds.lot], [0, "Abbreviations", frontIds.abb],
  ...toc.map(([lvl, label, text, id]) => [lvl, lvl === 1 ? (label ? `${label}  ${text}` : text) : `${label}  ${text}`, id]),
];
const tocTable = new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: [TEXT_W - 1100, 1100],
  layout: TableLayoutType.FIXED,
  rows: [new TableRow({ children: ["Topics", "Page"].map((t, i) => new TableCell({ borders: nb,
    width: { size: i ? 1100 : TEXT_W - 1100, type: WidthType.DXA },
    children: [new Paragraph({ alignment: i ? AlignmentType.RIGHT : AlignmentType.LEFT, spacing: { after: 120 },
      children: [new TextRun({ text: t, bold: true, font: FONT, size: 24 })] })] })) }),
  ...tocRows.map(([lvl, text, id]) => new TableRow({ cantSplit: true, children: [
    new TableCell({ borders: nb, width: { size: TEXT_W - 1100, type: WidthType.DXA },
      children: [new Paragraph({ indent: { left: lvl === 2 ? 480 : lvl === 3 ? 1000 : 0 }, spacing: { before: lvl === 1 ? 100 : 0, after: 30, line: 276 },
        children: [new TextRun({ text, font: FONT, size: lvl >= 2 ? (lvl === 3 ? 21 : 22) : 24, bold: lvl < 2 })] })] }),
    new TableCell({ borders: nb, width: { size: 1100, type: WidthType.DXA },
      children: [new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: lvl === 1 ? 100 : 0, after: 30, line: 276 },
        children: [new TextRun({ children: [new PageReference(id)], font: FONT, size: lvl >= 2 ? (lvl === 3 ? 21 : 22) : 24, bold: lvl < 2 })] })] }),
  ] })),
] });
const contents = [frontHead("Table of Contents"), tocTable];

const listHead = (t, id) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 },
  children: [new Bookmark({ id, children: [new TextRun({ text: t, bold: true, font: FONT, size: 32 })] })] });
const lists = [
  listHead("List of Figures", frontIds.lof),
  plainTable(["Fig No", "Name of the figure", "Page No"], figs.map(([n, c, id]) => [n, c.replace(/\*\*|`|~/g, ""), pref(id)]),
    [1000, 6300, 1000], { align: ["c", "l", "c"] }),
  new Paragraph({ children: [new PageBreak()] }),
  listHead("List of Tables", frontIds.lot),
  plainTable(["Table No", "Name of the Table", "Page No"], tabs.map(([n, c, id]) => [n, c.replace(/\*\*|`|~/g, ""), pref(id)]),
    [1100, 6200, 1000], { align: ["c", "l", "c"] }),
  new Paragraph({ children: [new PageBreak()] }),
  listHead("Abbreviations", frontIds.abb),
  plainTable(["Sr. No.", "Abbreviation", "Full form"], FM.abbreviations.map(([a, f], i) => [String(i + 1), a, f]),
    [900, 2100, 5300], { align: ["c", "l", "l"] }),
];

// ---------------------------------------------------------------- page furniture
const headerPara = () => new Header({ children: [new Paragraph({
  tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }],
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "808080", space: 4 } },
  children: [new TextRun({ text: META.short, font: FONT, size: 20 }),
    new TextRun({ children: [new Tab(), `Academic Year ${META.year}`], font: FONT, size: 20 })] })] });
const footerPara = () => new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
  children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 22 })] })] });
const emptyHF = { headers: { default: new Header({ children: [new Paragraph({ children: [] })] }) },
  footers: { default: new Footer({ children: [new Paragraph({ children: [] })] }) } };
const page = (pageNumbers) => ({ page: { size: { width: PAGE_W, height: PAGE_H },
  margin: { top: M_OTHER, bottom: M_OTHER, left: M_LEFT, right: M_OTHER, header: 708, footer: 708 },
  ...(pageNumbers ? { pageNumbers } : {}) } });

const doc = new Document({
  creator: "Harsh Rathod, Yugandhara Raj Goud, Krish Mundhra",
  title: META.title,
  description: "Capstone project final report, MPSTME, SVKM's NMIMS",
  styles: {
    default: { document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { line: LINE } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 36, bold: true, color: "000000" },
        paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 0, after: 360 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "000000" },
        paragraph: { spacing: { before: 300, after: 140, line: LINE }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: "000000" },
        paragraph: { spacing: { before: 220, after: 100, line: LINE }, outlineLevel: 2 } },
      { id: "SourceCode", name: "Source Code", basedOn: "Normal", quickFormat: true,
        run: { font: MONO, size: 14 },
        paragraph: { spacing: { before: 0, after: 0, line: 200, lineRule: "exact" }, indent: { left: 360, hanging: 360 } } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [
    { properties: { ...page() }, ...emptyHF, children: [...title, ...certificate, ...acknowledgement] },
    { properties: { ...page() }, headers: { default: headerPara() }, footers: { default: new Footer({ children: [new Paragraph({ children: [] })] }) },
      children: [...abstract, ...contents] },
    { properties: { ...page({ start: 1, formatType: NumberFormat.LOWER_ROMAN }) }, headers: { default: headerPara() },
      footers: { default: footerPara() }, children: lists },
    { properties: { ...page({ start: 1, formatType: NumberFormat.DECIMAL }) }, headers: { default: headerPara() },
      footers: { default: footerPara() }, children: sections.main },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`wrote ${OUT}: ${figs.length} figures, ${tabs.length} tables, ${refOrder.length} references, ` +
    `${srcFiles} source files (${srcLines} lines)`);
});
