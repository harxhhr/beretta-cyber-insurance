"""Charts for the capstone report (Chapter 4). Standard library only; PNG through headless Edge.

    py docs/report/make_report_charts.py

Control multipliers are computed from kyh-cyber-insurance/app/pricing_v2_params.json. The worked-example and
sensitivity values are the outputs of scripts/worked_example_v2.py and scripts/sensitivity_v2.py, copied here
so the charts can be redrawn without running the engine.
"""
import json
import os
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "docs", "diagrams"))
import build  # noqa: E402  (to_png, browser)
from svg import INK, MUTED, BORDER, DATA, MET, FONT  # noqa: E402

BREACH, GRACE, SOFT = "#a3261b", "#8a5a00", "#9aa4b5"
OUT_SVG, OUT_PNG = os.path.join(HERE, "svg"), os.path.join(HERE, "png")


class Chart:
    def __init__(self, w, h, title):
        self.w, self.h, self.title, self.parts = w, h, title, []

    def text(self, x, y, s, size=13, anchor="middle", color=INK, weight="400", italic=False):
        st = ' font-style="italic"' if italic else ""
        self.parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" '
                          f'font-weight="{weight}"{st}>{escape(str(s))}</text>')

    def rect(self, x, y, w, h, fill, stroke="none"):
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" '
                          f'fill="{fill}" stroke="{stroke}"/>')

    def line(self, x1, y1, x2, y2, color=BORDER, sw=1, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
                          f'stroke-width="{sw}"{da}/>')

    def poly(self, pts, color, sw=2.2):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.parts.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}"/>')

    def dot(self, x, y, color, r=5):
        self.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>')

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" font-family="{FONT}">\n<title>{escape(self.title)}</title>\n'
                f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>\n' + "\n".join(self.parts) + "\n</svg>\n")


def inr(v):
    """Indian digit grouping: 1,17,876."""
    s = str(int(round(v)))
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])


def hbars(name, title, rows, unit_fmt, color=DATA, w=1100, left=330, note=None):
    """Horizontal bar chart. rows: [(label, value)]."""
    bh, gap, top = 34, 14, 70
    h = top + len(rows) * (bh + gap) + (70 if note else 40)
    c = Chart(w, h, title)
    c.text(20, 34, title, size=18, anchor="start", weight="700")
    vmax = max(v for _, v in rows)
    span = w - left - 150
    for i, (lab, v) in enumerate(rows):
        y = top + i * (bh + gap)
        c.text(left - 14, y + bh / 2 + 5, lab, size=14, anchor="end")
        c.rect(left, y, span * v / vmax, bh, color)
        c.text(left + span * v / vmax + 10, y + bh / 2 + 5, unit_fmt(v), size=14, anchor="start", weight="700")
    c.line(left, top - 6, left, top + len(rows) * (bh + gap) - gap + 6, INK, 1.2)
    if note:
        c.text(20, h - 22, note, size=12.5, anchor="start", color=MUTED, italic=True)
    return name, c


def peril_el():
    rows = [("Ransomware", 20823), ("Funds transfer fraud", 20287), ("Business email compromise", 5379),
            ("Other first-party", 3277), ("Third-party liability", 181)]
    return hbars("C1_expected_loss_by_peril", "Expected loss by peril, worked example (total ₹49,947)", rows, inr,
                 note="IT services firm, NIC 62, turnover ₹150 crore, limit ₹5 crore, retention ₹5 lakh. "
                      "Output of scripts/worked_example_v2.py.")


def whatif():
    rows = [("Privileged access management", 32421), ("EDR", 20877), ("Vulnerability management", 12739),
            ("Tested backups", 5333), ("Email security", 4901), ("MFA", 3787), ("Security awareness", 1850),
            ("Incident response plan", 614)]
    return hbars("C3_whatif_savings", "Premium saving if each control were verified (base ₹99,895)", rows, inr,
                 color=MET, note="Each bar re-prices the worked example with only that control set to VERIFIED.")


def tornado():
    base = 99895
    rows = [("σ (severity shape)", 1.97, 116213, 2.19, 100108), ("β (within-stage damping)", 0.0, 108065, 1.0, 84408),
            ("x (credit for STATED)", 0.4, 113039, 0.8, 87308), ("TLR", 0.48, 104057, 0.57, 87627),
            ("Trend", "−10%", 89905, "+10%", 109884), ("α (claims credibility)", 3.45, 104003, 6.94, 92649),
            ("Turnover zone factor", 1.10, 99895, 1.50, 104433), ("USD/INR", 83, 95798, 92, 103097),
            ("MFA adoption p", 0.5, 96817, 0.9, 101342), ("Control caps", "[0.5, 2.0]", 99895, "[0.4, 2.5]", 98347),
            ("Head-share placeholders", "×0.75", 99999, "×1.25", 99790)]
    rows.sort(key=lambda r: -max(abs(r[2] - base), abs(r[4] - base)))
    w, left, top, bh, gap = 1200, 300, 92, 30, 12
    h = top + len(rows) * (bh + gap) + 80
    c = Chart(w, h, "Sensitivity of the worked-example premium")
    c.text(20, 34, "Sensitivity of the worked-example premium to each assumption (base ₹99,895)", size=18,
           anchor="start", weight="700")
    lim = 0.20
    cx, half = left + (w - left - 60) / 2, (w - left - 60) / 2
    for k in (-0.2, -0.1, 0, 0.1, 0.2):
        x = cx + half * k / lim
        c.line(x, top - 14, x, top + len(rows) * (bh + gap), INK if k == 0 else BORDER, 1.2 if k == 0 else 1,
               None if k == 0 else "4 4")
        c.text(x, top - 20, f"{k * 100:+.0f}%" if k else "0", size=12, color=MUTED)
    for i, (lab, lo, plo, hi, phi) in enumerate(rows):
        y = top + i * (bh + gap)
        c.text(left - 14, y + bh / 2 + 5, lab, size=14, anchor="end")
        for val, prem, col in ((lo, plo, SOFT), (hi, phi, DATA)):
            d = (prem - base) / base
            x0, x1 = sorted((cx, cx + half * d / lim))
            c.rect(x0, y, x1 - x0, bh, col)
            if abs(d) > 0.0005:
                tx = x1 + 6 if d > 0 else x0 - 6
                c.text(tx, y + bh / 2 + 5, f"{val}: {d * 100:+.1f}%", size=12, anchor="start" if d > 0 else "end")
    c.rect(left, h - 46, 16, 16, SOFT)
    c.text(left + 24, h - 33, "low value of the assumption", size=12.5, anchor="start", color=MUTED)
    c.rect(left + 260, h - 46, 16, 16, DATA)
    c.text(left + 284, h - 33, "high value", size=12.5, anchor="start", color=MUTED)
    return "C2_sensitivity_tornado", c


def control_multipliers():
    prm = json.load(open(os.path.join(ROOT, "kyh-cyber-insurance", "app", "pricing_v2_params.json"), encoding="utf-8"))
    ctl = prm["controls"]
    x = ctl["credit_x"]["value"]
    lo, hi = ctl["multiplier_cap"]["value"]
    names = {"CTRL-SECCONFIG": "Secure configuration", "CTRL-PAM": "Privileged access mgmt", "CTRL-EDR": "EDR",
             "CTRL-LOGGING": "Logging & monitoring", "CTRL-VULNMGMT": "Vulnerability mgmt",
             "CTRL-PATCH-CRIT": "Critical patching", "CTRL-AWARENESS": "Security awareness",
             "CTRL-EMAILSEC": "Email security", "CTRL-MFA": "MFA"}
    rows = []
    for cid, v in ctl["frequency"].items():
        S, p = v["S"], v["p"]
        den = p + (1 - p) * S
        has, lacks = min(max(1 / den, lo), hi), min(max(S / den, lo), hi)
        rows.append((names.get(cid, cid), has, 1 - x * (1 - has), lacks))
    rows.sort(key=lambda r: r[3] / r[1], reverse=True)
    w, left, top, bh = 1200, 280, 96, 40
    h = top + len(rows) * bh + 90
    c = Chart(w, h, "Frequency multiplier by evidence status")
    c.text(20, 34, "Frequency multiplier of each priced control by evidence status (log scale)", size=18,
           anchor="start", weight="700")
    import math
    a, b = math.log(0.45), math.log(2.1)
    X = lambda m: left + (w - left - 60) * (math.log(m) - a) / (b - a)
    for t in (0.5, 0.75, 1.0, 1.5, 2.0):
        c.line(X(t), top - 16, X(t), top + len(rows) * bh, INK if t == 1 else BORDER, 1.2 if t == 1 else 1,
               None if t == 1 else "4 4")
        c.text(X(t), top - 22, f"×{t:g}", size=12, color=MUTED)
    for i, (lab, has, stated, lacks) in enumerate(rows):
        y = top + i * bh + bh / 2
        c.text(left - 14, y + 5, lab, size=14, anchor="end")
        c.line(X(has), y, X(lacks), y, BORDER, 3)
        c.dot(X(has), y, MET, 7)
        c.dot(X(stated), y, GRACE, 6)
        c.dot(X(lacks), y, BREACH, 7)
    ly = h - 40
    for k, (col, lab) in enumerate(((MET, "VERIFIED (m_has)"), (GRACE, f"STATED (credit x = {x})"),
                                    (BREACH, "NOT_WORKING / UNKNOWN (m_lacks)"))):
        c.dot(left + 10 + k * 280, ly, col, 7)
        c.text(left + 24 + k * 280, ly + 5, lab, size=12.5, anchor="start", color=MUTED)
    return "C4_control_multipliers", c


def credibility():
    w, h, left, top, right, bottom = 1000, 560, 90, 70, 40, 90
    c = Chart(w, h, "Claims credibility multiplier")
    c.text(20, 34, "Claims-history multiplier M = (α + N) / (α + λT), λT = 0.03", size=18, anchor="start",
           weight="700")
    pw, ph = w - left - right, h - top - bottom
    X = lambda n: left + pw * n / 4
    Y = lambda m: top + ph * (1 - (m - 0.8) / (2.2 - 0.8))
    for m in (0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2):
        c.line(left, Y(m), left + pw, Y(m), BORDER, 1, None if m == 1.0 else "4 4")
        c.text(left - 10, Y(m) + 4, f"×{m:.1f}", size=12, anchor="end", color=MUTED)
    for n in range(5):
        c.text(X(n), top + ph + 24, str(n), size=13, color=MUTED)
    c.text(left + pw / 2, h - 30, "N, material incidents in the last 3 years", size=13, color=MUTED)
    for alpha, col, lab in ((3.45, SOFT, "α = 3.45 (low)"), (4.22, DATA, "α = 4.22 (used)"),
                            (6.94, GRACE, "α = 6.94 (high)")):
        pts = [(X(n), Y((alpha + n) / (alpha + 0.03))) for n in range(5)]
        c.poly(pts, col, 3 if alpha == 4.22 else 2)
        for x_, y_ in pts:
            c.dot(x_, y_, col, 4.5)
        c.text(pts[-1][0] - 6, pts[-1][1] - 10, lab, size=12.5, anchor="end", color=col, weight="700")
    return "C5_claims_credibility", c


def premium_build():
    parts = [("Expected loss", 49947, DATA), ("Expenses 30%", 29968, SOFT), ("Profit, risk, reinsurance 20%", 19979,
             "#5b6474"), ("GST 18%", 17981, GRACE)]
    w, h, left, top = 1100, 300, 40, 90
    c = Chart(w, h, "From expected loss to payable premium")
    c.text(20, 34, "From expected loss to payable premium, worked example", size=18, anchor="start", weight="700")
    total = sum(v for _, v, _ in parts)
    span, x = w - 2 * left, left
    for lab, v, col in parts:
        bw = span * v / total
        c.rect(x, top, bw, 60, col)
        c.text(x + bw / 2, top + 36, inr(v), size=14, color="#ffffff", weight="700")
        c.text(x + bw / 2, top + 88, lab, size=13)
        x += bw
    tech = left + span * 99895 / total
    c.line(tech, top - 14, tech, top + 74, INK, 2)
    c.text(tech, top - 20, "technical premium ₹99,895 (EL ÷ TLR 0.50)", size=12.5, anchor="end")
    c.text(w - left, top - 20, "payable ₹1,17,876", size=12.5, anchor="end", weight="700")
    c.text(20, h - 24, "The bound premium is the technical premium; GST is shown on its own line.", size=12.5,
           anchor="start", color=MUTED, italic=True)
    return "C6_premium_build", c


def sigma_fit():
    rows = [("Observed (NetDiligence 2025 SMEs)", 8.24, INK), ("σ = 2.193 (kept)", 8.26, MET),
            ("σ = 1.214 (rejected)", 12.86, BREACH)]
    w, left, top, bh, gap = 1000, 330, 70, 38, 16
    h = top + 3 * (bh + gap) + 60
    c = Chart(w, h, "Severity shape check")
    c.text(20, 34, "Check on the lognormal shape: share of SME claims above $500K", size=18, anchor="start",
           weight="700")
    span = w - left - 120
    for i, (lab, v, col) in enumerate(rows):
        y = top + i * (bh + gap)
        c.text(left - 14, y + bh / 2 + 5, lab, size=14, anchor="end")
        c.rect(left, y, span * v / 14, bh, col)
        c.text(left + span * v / 14 + 10, y + bh / 2 + 5, f"{v:.2f}%", size=14, anchor="start", weight="700")
    c.text(20, h - 22, "Both roots match the mean ($264K) and P(X > $1M) = 395/8,936; only σ = 2.193 also "
                       "matches the $500K point.", size=12.5, anchor="start", color=MUTED, italic=True)
    return "C7_sigma_fit", c


def tests():
    rows = [("Part 2: agent and collector", 158), ("Part 1: platform and pricing", 65), ("Integration: both systems", 1)]
    return hbars("C8_test_counts", "Automated tests, all passing", rows, lambda v: f"{v} tests", w=1000, left=300,
                 note="python -m unittest; kyh-agent/run_tests.py; integration/test_linked_system.py")


def two_jobs():
    """Monitoring before and after bind (replaces docs/figures/guide_fig_two_jobs.png, which had V1 wording)."""
    w, h = 1400, 560
    c = Chart(w, h, "What monitoring does before and after bind")
    bw, bh, gap, x0 = 280, 110, 40, 60

    def box(x, y, head, sub, col=INK, fill="#f2f4f7"):
        c.parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="12" fill="{fill}" stroke="{col}" '
                       f'stroke-width="2.4"/>')
        c.text(x + bw / 2, y + 40, head, size=19, weight="700", color=col)
        for k, line in enumerate(sub.split("\n")):
            c.text(x + bw / 2, y + 70 + k * 22, line, size=14.5)

    def arrow(x1, y, x2):
        c.line(x1, y, x2 - 10, y, INK, 2.4)
        c.parts.append(f'<path d="M{x2 - 12},{y - 7} L{x2},{y} L{x2 - 12},{y + 7} z" fill="{INK}"/>')

    for band, (y, label) in enumerate(((30, "Before bind: monitoring is evidence for the quote"),
                                       (300, "After bind: monitoring drives warranties only"))):
        c.parts.append(f'<rect x="20" y="{y}" width="{w - 40}" height="230" rx="14" fill="none" stroke="{MUTED}" '
                       f'stroke-dasharray="8 6" stroke-width="1.6"/>')
        c.text(40, y + 32, label, size=17, anchor="start", weight="700", color=MUTED)
    rows = [[("Fleet roll-up", "AGENT_FLEET,\nTECHNICALLY_OBSERVED", INK), ("Engine A", "best evidence per control\n(beats questionnaire)", INK),
             ("Engine B", "VERIFIED status:\nfull control effect", INK), ("Quote", "premium fixed\nat bind", MET)],
            [("Fleet roll-up", "same signed\nroll-up", INK), ("Engine A", "observation recorded\n(history kept)", INK),
             ("Warranty machine", "MET / IN_GRACE /\nBREACHED / REMEDIATED", DATA), ("Premium", "never re-priced", MUTED)]]
    for r, y in ((0, 80), (1, 350)):
        for i, (head, sub, col) in enumerate(rows[r]):
            x = x0 + i * (bw + gap + 10)
            box(x, y, head, sub, col)
            if i < 3:
                nx = x0 + (i + 1) * (bw + gap + 10)
                if r == 1 and i == 2:
                    m = (x + bw + nx) / 2
                    c.line(x + bw + 6, y + 30, nx - 6, y + bh - 30, BREACH, 4)
                    c.line(x + bw + 6, y + bh - 30, nx - 6, y + 30, BREACH, 4)
                    c.text(m, y - 10, "no path", size=14, color=BREACH)
                else:
                    arrow(x + bw + 4, y + bh / 2, nx - 4)
    return "C9_monitoring_two_jobs", c


def main():
    os.makedirs(OUT_SVG, exist_ok=True)
    os.makedirs(OUT_PNG, exist_ok=True)
    exe = build.browser()
    build.PNG_DIR = OUT_PNG
    for fn in (peril_el, tornado, whatif, control_multipliers, credibility, premium_build, sigma_fit, tests, two_jobs):
        name, c = fn()
        path = os.path.join(OUT_SVG, name + ".svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(c.svg())
        if exe:
            build.to_png(exe, path, os.path.join(OUT_PNG, name + ".png"), c.w, c.h)
        print(name)
    frame = os.path.join(OUT_PNG, "_frame.html")
    if os.path.exists(frame):
        os.remove(frame)


if __name__ == "__main__":
    main()
