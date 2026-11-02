"""Build deliverables/Group19_Capstone_exe_summary.docx (then run to_pdf.ps1 for the PDF).

    py docs/submission/build_exec_summary.py
    powershell -ExecutionPolicy Bypass -File docs/submission/to_pdf.ps1 deliverables/Group19_Capstone_exe_summary.docx

Needs python-docx (documentation tooling only; the system itself stays standard-library only).
Format: Times New Roman 12, 1.5 line spacing, justified, page numbers centred.
"""
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "deliverables", "Group19_Capstone_exe_summary.docx")
MAROON = RGBColor(0x8B, 0x1A, 0x2B)
FONT = "Times New Roman"


def set_font(run, size=None, bold=None, color=None, italic=None):
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def shade(cell, hex_fill):
    tc = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc.append(shd)


def page_number(paragraph):
    run = paragraph.add_run()
    set_font(run, 11)
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._element.append(el)


class Doc:
    def __init__(self):
        self.d = Document()
        sec = self.d.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.top_margin = sec.bottom_margin = Cm(2.2)
        sec.left_margin = sec.right_margin = Cm(2.54)
        normal = self.d.styles["Normal"]
        normal.font.name = FONT
        normal.font.size = Pt(12)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        pf = normal.paragraph_format
        pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.space_after = Pt(6)
        foot = sec.footer.paragraphs[0]
        foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        page_number(foot)

    def center(self, text, size, bold=False, after=4, color=None):
        p = self.d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        p.paragraph_format.space_after = Pt(after)
        set_font(p.add_run(text), size, bold, color)

    def heading(self, text):
        p = self.d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        set_font(p.add_run(text), 14, True, MAROON)

    def para(self, text, lead=None):
        p = self.d.add_paragraph()
        if lead:
            set_font(p.add_run(lead + " "), bold=True)
        set_font(p.add_run(text))
        return p

    def bullets(self, items):
        for lead, text in items:
            p = self.d.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            set_font(p.add_run(lead + " "), bold=True)
            set_font(p.add_run(text))

    def table(self, rows, widths):
        t = self.d.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                cell = t.cell(i, j)
                cell.width = widths[j]
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                p.paragraph_format.space_after = Pt(2)
                if i == 0:
                    shade(cell, "8B1A2B")
                    set_font(p.add_run(value), 11, True, RGBColor(0xFF, 0xFF, 0xFF))
                else:
                    if j == 0:
                        shade(cell, "EEEFF0")
                    set_font(p.add_run(value), 11, j == 0)
        return t


def main():
    doc = Doc()
    d = doc.d

    logos = d.add_paragraph()
    logos.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logos.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    logos.paragraph_format.space_after = Pt(6)
    logos.add_run().add_picture(os.path.join(ROOT, "docs", "report", "nmims_logo.jpg"), height=Cm(1.7))
    logos.add_run("            ")
    logos.add_run().add_picture(os.path.join(HERE, "beretta_logo.png"), height=Cm(1.2))

    doc.center("Executive Summary  |  Capstone Project, Group 19", 12, True, 2, MAROON)
    doc.center("An Explainable Automated Cyber-Insurance Underwriting and Continuous Monitoring Platform", 15, True, 4)
    doc.center("Krish Mundhra (K041)  |  Harsh Rathod (K080)  |  Yugandhara Goud (K023)", 11)
    doc.center("Faculty Mentor: Prof. Rohit Suryawanshi  |  B.Tech CSE (Cybersecurity), MPSTME, "
               "SVKM’s NMIMS, Mumbai  |  2026-27", 11, after=8)

    doc.heading("1. Introduction and problem statement")
    doc.para("Cyber insurance lets a company pass part of the cost of an incident to an insurer. Indian small and "
             "medium enterprises (SMEs) face the same ransomware, email-compromise and payment-fraud attacks as large "
             "firms, yet few of them carry cover, while the CERT-In Directions (six-hour incident reporting) and the "
             "DPDP Act (penalties of up to ₹250 crore) have raised the cost of an incident. The way cyber "
             "insurance is sold has not kept pace:")
    doc.bullets([
        ("Priced with traditional thinking.", "Loss history is short and heavy-tailed, and premiums rest mainly on "
         "revenue and industry."),
        ("The premium is a black box.", "The insured sees one number and cannot tell which answer raised it or what "
         "would lower it."),
        ("One questionnaire, once a year.", "The policy rests on a form the company completes itself, and nobody "
         "revisits it until renewal."),
        ("Controls are never verified.", "A self-declared “yes” is priced the same as a test result."),
        ("A static view of a dynamic landscape.", "Nothing is checked after the policy is bound, so a gap surfaces "
         "only at claim time."),
    ])
    doc.para("To design and build an explainable cyber-insurance underwriting system for Indian SMEs that grades the "
             "evidence behind each security control, prices a policy from published claims data with every factor "
             "traceable and explained, monitors the insured’s endpoints after bind with a read-only agent whose "
             "reports cannot be forged or replayed, and lets monitoring change warranty states only, never the "
             "bound premium.", lead="Problem statement:")

    doc.heading("2. Methodology")
    doc.para("Beretta is built as two engines that share one record of evidence.")
    doc.para("Every input is stored as an observation with a source, a locator and one of four evidence strengths: "
             "DECLARED, DOCUMENTED, TESTED and TECHNICALLY_OBSERVED. For each of 15 controls the strongest, most "
             "recent evidence wins. A read-only endpoint agent runs 12 checks and sends reports signed with "
             "HMAC-SHA256 and numbered against replay, and a build hash exposes modified agents. The collector rolls "
             "the results up per company (a control passes if at least 95% of the hosts able to observe it pass, and "
             "a silent host counts as a failure) and sends one signed roll-up to the platform.", lead="Risk engine.")
    doc.para("A frequency–severity model prices five perils separately: ransomware, email compromise, funds "
             "transfer fraud, other first-party loss and third-party liability. Frequencies come from Coalition’s "
             "2025 claims data, each loss is lognormal with a shape (σ = 2.193) fitted to NetDiligence SME "
             "claims, and the payout is integrated through the retention and the limit. Control effects come from "
             "Marsh McLennan (2023), and a stated control earns 60% of a verified control’s credit. Claims "
             "history enters through a credibility factor (α = 4.22). The technical premium is the expected "
             "loss divided by a 0.50 target loss ratio, with 18% GST added. Every parameter sits in one file with "
             "its source and a tag: published, derived or assumed.", lead="Pricing engine.")
    doc.para("Monitoring results reach a bound policy only through a warranty state machine (MET, IN_GRACE, "
             "BREACHED, REMEDIATED) with a 7- or 14-day grace period. The engine refuses to price a bound policy.",
             lead="Warranties after bind.")
    doc.para("The system uses the Python standard library and plain HTML, CSS and JavaScript, with dashboards for "
             "the underwriter, administrator and insured, and a fleet dashboard for the collector. It was validated "
             "by 224 automated tests and a live demonstration with four SIMULATED endpoints and a Windows virtual "
             "machine.", lead="Build and test.")

    doc.heading("3. Key findings and results")
    doc.table([
        ("Area", "Result"),
        ("Testing", "All 224 automated tests pass: 65 for the platform and pricing model, 158 for the agent and "
         "collector, and 1 end-to-end test across both systems."),
        ("Evidence changes the price", "For a reference firm the technical premium is ₹2,48,235 with no "
         "evidence, ₹55,342 with every control stated and ₹46,487 with every control verified."),
        ("Worked example", "IT services firm, ₹150 crore turnover, ₹5 crore limit: expected loss "
         "₹49,947, technical premium ₹99,895, payable ₹1,17,876. Verifying privileged access "
         "management alone would save ₹32,421."),
        ("Model checks", "The five peril frequencies add to 1.38% (1.47% with other claims) against the published "
         "1.48%. No single assumption moves the premium by more than about 16%."),
        ("Linked demonstration", "Stopping EDR on one of four machines moved the EDR warranty to IN_GRACE within "
         "seconds, then to BREACHED, and back to MET after the fix. The bound premium stayed at ₹94,135 "
         "throughout, and a re-price was refused."),
    ], [Cm(4.2), Cm(11.7)])
    p = doc.para("The main limitation is that the loss data is US-weighted: the India adjustment factors stay at 1 "
                 "until Indian claims data is published, and several shares and adoption rates are labelled "
                 "assumptions with a sensitivity range.")
    p.paragraph_format.space_before = Pt(8)

    doc.heading("4. Project value and impact")
    doc.bullets([
        ("For SMEs:", "a premium they can understand, with the saving from each control shown, so security spending "
         "can be planned against cost."),
        ("For insurers and MGAs:", "a reference design for evidence-graded underwriting with post-bind warranty "
         "monitoring, which reduces reliance on unverified answers."),
        ("For brokers, regulators and auditors:", "a complete, reproducible pricing method in which every assumption "
         "is labelled and every quote can be reproduced from its snapshot."),
        ("Privacy and fairness:", "the agent is read-only and collects no personal content, and monitoring never "
         "re-prices the policy; it acts through warranties with a grace period."),
    ])
    doc.para("The opportunity is large. India has 8.84 crore enterprises on the Udyam portals, published estimates "
             "put cyber-insurance take-up among Indian companies under 5%, and the Indian market is forecast to grow "
             "about 18.4% a year against 14.2% worldwide (MarketsandMarkets). The next steps are calibration to "
             "Indian claims, identity-provider connectors to verify MFA, policy limits and payouts on the dashboard, "
             "and a pilot on real company fleets.")

    d.core_properties.title = "Group 19 Capstone Executive Summary"
    d.core_properties.author = "Krish Mundhra, Harsh Rathod, Yugandhara Goud"
    d.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
