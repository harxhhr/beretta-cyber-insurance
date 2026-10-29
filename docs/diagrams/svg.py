"""A small SVG drawing kit for the Beretta UML figures. Standard library only.

Every figure is a `D` (diagram) with absolute coordinates in pixels. Colours follow the platform's
house style (see kyh-cyber-insurance/frontend/styles.css): ink lines on white, colour only on states.
"""
import os
from xml.sax.saxutils import escape

# ---- house-style tokens (mirrors styles.css) -----------------------------------------------------
INK, MUTED, BORDER, RULE, RAISED = "#0b0e14", "#555d6b", "#c9cfd8", "#edf0f4", "#f7f8fa"
GROUND, WHITE, PRIMARY = "#f2f4f7", "#ffffff", "#12161d"
DATA, DATA_SOFT = "#1d5fbf", "#e8effa"
MET, MET_BG = "#145c33", "#e2f4e8"
GRACE, GRACE_BG = "#8a4b06", "#fff2d6"
BREACH, BREACH_BG = "#9b1c22", "#ffe8e6"
UNKNOWN, UNKNOWN_BG = "#434956", "#eaedf1"
REMED, REMED_BG = "#1a4f8f", "#e3edf9"
EV = {"DECLARED": "#9aa4b5", "DOCUMENTED": "#6b8fcf", "TESTED": "#3a6fc4", "TECHNICALLY_OBSERVED": "#1d4f9e"}
STATE_COLOURS = {"MET": (MET, MET_BG), "IN_GRACE": (GRACE, GRACE_BG), "BREACHED": (BREACH, BREACH_BG),
                 "REMEDIATED": (REMED, REMED_BG), "UNKNOWN": (UNKNOWN, UNKNOWN_BG)}

FONT = "Segoe UI, Helvetica, Arial, sans-serif"
MONO = "Consolas, Menlo, monospace"
CHAR = 0.56  # average glyph width / font size, used to size boxes


def tw(s, size=12):
    """Estimated text width in px."""
    return len(s) * size * CHAR


class D:
    def __init__(self, w, h, title, kind):
        self.w, self.h, self.title, self.kind = w, h, title, kind
        self.out = []

    # ---------------------------------------------------------------- primitives
    def raw(self, s):
        self.out.append(s)

    def rect(self, x, y, w, h, fill=WHITE, stroke=INK, sw=1.2, rx=0, dash=None, opacity=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' fill-opacity="{opacity}"' if opacity is not None else ""
        self.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{o} '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=12, weight="normal", anchor="middle", color=INK, italic=False, mono=False,
             halo=False):
        st = ' font-style="italic"' if italic else ""
        h = f' stroke="{WHITE}" stroke-width="4" paint-order="stroke" stroke-linejoin="round"' if halo else ""
        self.raw(f'<text x="{x}" y="{y}" font-family="{MONO if mono else FONT}" font-size="{size}" '
                 f'font-weight="{weight}" text-anchor="{anchor}" fill="{color}"{st}{h}>{escape(s)}</text>')

    def lines(self, x, y, rows, size=12, gap=None, **kw):
        gap = gap or size * 1.35
        for i, r in enumerate(rows):
            self.text(x, y + i * gap, r, size=size, **kw)

    def line(self, pts, end=None, start=None, dash=None, color=INK, sw=1.2, label=None, lpos=0.5, lseg=None,
             ldx=0, ldy=-6, lsize=11, lcolor=None, lanchor="middle", lweight="normal"):
        """Polyline through pts. end/start: 'arrow' (filled), 'open' (V), 'tri' (hollow triangle),
        'diamond' (filled), 'odiamond' (hollow), 'crow' / 'one' / 'zero-many' (ER), None."""
        p = " ".join(f"{a},{b}" for a, b in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        me = f' marker-end="url(#m-{end})"' if end else ""
        ms = f' marker-start="url(#m-{start})"' if start else ""
        self.raw(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}"{d}{me}{ms} '
                 f'stroke-linejoin="round"/>')
        if label:
            i = lseg if lseg is not None else (len(pts) - 2) // 2
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            lx, ly = x1 + (x2 - x1) * lpos + ldx, y1 + (y2 - y1) * lpos + ldy
            for k, row in enumerate(label.split("\n")):
                self.text(lx, ly + k * (lsize + 3), row, size=lsize, color=lcolor or color, anchor=lanchor,
                          halo=True, weight=lweight)

    def arrow(self, x1, y1, x2, y2, **kw):
        kw.setdefault("end", "arrow")
        self.line([(x1, y1), (x2, y2)], **kw)

    # ---------------------------------------------------------------- UML shapes
    def box(self, x, y, w, h, title, rows=(), stereo=None, fill=WHITE, stroke=INK, rx=6, tsize=13, rsize=11,
            tcolor=INK, rcolor=MUTED, dash=None, sw=1.2, align="middle"):
        self.rect(x, y, w, h, fill=fill, stroke=stroke, rx=rx, dash=dash, sw=sw)
        n = (1 if stereo else 0) + 1 + len(rows)
        block = (tsize * 1.3) + (rsize * 1.35 * len(rows)) + (rsize * 1.3 if stereo else 0)
        cy = y + (h - block) / 2 + tsize * 0.95
        cx = x + w / 2 if align == "middle" else x + 10
        if stereo:
            self.text(cx, cy - 2, f"«{stereo}»", size=rsize, color=MUTED, anchor=align)
            cy += rsize * 1.3
        self.text(cx, cy, title, size=tsize, weight="600", color=tcolor, anchor=align)
        for i, r in enumerate(rows):
            self.text(cx, cy + rsize * 1.45 * (i + 1), r, size=rsize, color=rcolor, anchor=align)
        return n

    def component(self, x, y, w, h, title, rows=(), stereo="component", fill=WHITE, stroke=INK):
        self.box(x, y, w, h, title, rows, stereo=stereo, fill=fill, stroke=stroke, rx=4)
        # component icon, top right
        ix, iy = x + w - 24, y + 8
        self.rect(ix, iy, 14, 18, fill=WHITE, stroke=stroke, sw=1)
        self.rect(ix - 4, iy + 3, 8, 4, fill=WHITE, stroke=stroke, sw=1)
        self.rect(ix - 4, iy + 11, 8, 4, fill=WHITE, stroke=stroke, sw=1)

    def classbox(self, x, y, w, name, attrs=(), ops=(), stereo=None, fill=WHITE, stroke=INK, hfill=RAISED,
                 size=11):
        """UML class with three compartments. Returns the box height."""
        rh = size * 1.45
        head = 26 + (14 if stereo else 0)
        ha = (len(attrs) * rh + 10) if attrs else 8
        ho = (len(ops) * rh + 10) if ops else 8
        h = head + ha + ho
        self.rect(x, y, w, h, fill=fill, stroke=stroke)
        self.rect(x, y, w, head, fill=hfill, stroke=stroke)
        ty = y + 18
        if stereo:
            self.text(x + w / 2, ty - 2, f"«{stereo}»", size=size - 1, color=MUTED)
            ty += 14
        self.text(x + w / 2, ty, name, size=13, weight="600")
        self.line([(x, y + head + ha), (x + w, y + head + ha)], color=stroke, sw=1)
        for i, a in enumerate(attrs):
            self.text(x + 8, y + head + 4 + rh * (i + 0.8), a, size=size, anchor="start", mono=True)
        for i, o in enumerate(ops):
            self.text(x + 8, y + head + ha + 4 + rh * (i + 0.8), o, size=size, anchor="start", mono=True)
        return h

    def entity(self, x, y, w, name, cols, fill=WHITE, hfill=PRIMARY, size=11):
        """ER entity: dark header, one row per column. cols: (name, type, key) with key 'PK','FK','PK FK' or ''."""
        rh = size * 1.6
        h = 26 + len(cols) * rh + 6
        self.rect(x, y, w, h, fill=fill, stroke=INK, rx=4)
        self.rect(x, y, w, 26, fill=hfill, stroke=INK, rx=4)
        self.rect(x + 0.6, y + 18, w - 1.2, 8, fill=hfill, stroke="none")
        self.text(x + w / 2, y + 17.5, name, size=12.5, weight="600", color=WHITE)
        for i, (c, t, k) in enumerate(cols):
            cy = y + 26 + rh * (i + 0.8)
            if k:
                self.text(x + 8, cy, k, size=9.5, anchor="start", color=DATA if "PK" in k else MUTED, weight="700")
            self.text(x + 40, cy, c, size=size, anchor="start", mono=True,
                      weight="700" if "PK" in k else "normal")
            self.text(x + w - 8, cy, t, size=size - 1, anchor="end", color=MUTED, mono=True)
        return h

    def actor(self, x, y, name, sub=None, color=INK, top=False):
        """Stick figure; (x, y) is the head centre. top=True puts the name above the head."""
        self.raw(f'<circle cx="{x}" cy="{y}" r="9" fill="{WHITE}" stroke="{color}" stroke-width="1.4"/>')
        self.line([(x, y + 9), (x, y + 34)], color=color, sw=1.4)
        self.line([(x - 15, y + 18), (x + 15, y + 18)], color=color, sw=1.4)
        self.line([(x - 13, y + 52), (x, y + 34), (x + 13, y + 52)], color=color, sw=1.4)
        self.text(x, y + 70, name, size=12, weight="600")
        if sub:
            for i, r in enumerate(sub.split("\n")):
                self.text(x, y + 85 + i * 14, r, size=10.5, color=MUTED)

    def usecase(self, cx, cy, label, rx=None, ry=22, fill=WHITE, stroke=INK, size=11.5):
        rows = label.split("\n")
        rx = rx or max(tw(r, size) for r in rows) / 2 + 22
        self.raw(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="1.2"/>')
        top = cy - (len(rows) - 1) * size * 0.65 + size * 0.36
        for i, r in enumerate(rows):
            self.text(cx, top + i * size * 1.3, r, size=size)
        return rx

    def state(self, x, y, w, h, name, rows=(), colours=None, rx=14, tsize=13, rsize=10.5):
        stroke, fill = colours or (INK, WHITE)
        self.rect(x, y, w, h, fill=fill, stroke=stroke, rx=rx, sw=1.5)
        if rows:
            self.text(x + w / 2, y + 20, name, size=tsize, weight="700", color=stroke)
            self.line([(x, y + 29), (x + w, y + 29)], color=stroke, sw=0.8)
            for i, r in enumerate(rows):
                self.text(x + w / 2, y + 45 + i * rsize * 1.4, r, size=rsize, color=INK)
        else:
            self.text(x + w / 2, y + h / 2 + tsize * 0.36, name, size=tsize, weight="700", color=stroke)

    def initial(self, x, y, r=8):
        self.raw(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{INK}"/>')

    def final(self, x, y, r=10):
        self.raw(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{WHITE}" stroke="{INK}" stroke-width="1.4"/>')
        self.raw(f'<circle cx="{x}" cy="{y}" r="{r - 4}" fill="{INK}"/>')

    def decision(self, cx, cy, w, h, label="", size=11, fill=WHITE, stroke=INK):
        pts = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
        self.raw(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        rows = label.split("\n") if label else []
        top = cy - (len(rows) - 1) * size * 0.65 + size * 0.36
        for i, r in enumerate(rows):
            self.text(cx, top + i * size * 1.3, r, size=size)

    def action(self, x, y, w, h, label, size=11.5, fill=WHITE, stroke=INK, weight="normal", sub=None):
        """Activity action (rounded rectangle). label may contain \\n."""
        self.rect(x, y, w, h, fill=fill, stroke=stroke, rx=12)
        rows = label.split("\n")
        extra = sub.split("\n") if sub else []
        n = len(rows) + len(extra)
        top = y + h / 2 - (n - 1) * size * 0.68 + size * 0.36
        for i, r in enumerate(rows):
            self.text(x + w / 2, top + i * size * 1.36, r, size=size, weight=weight)
        for j, r in enumerate(extra):
            self.text(x + w / 2, top + (len(rows) + j) * size * 1.36, r, size=size - 1.5, color=MUTED, mono=True)

    def bar(self, x, y, w, h=6, vertical=False):
        """Fork / join bar."""
        if vertical:
            self.rect(x, y, h, w, fill=INK, stroke=INK)
        else:
            self.rect(x, y, w, h, fill=INK, stroke=INK)

    def note(self, x, y, w, h, rows, size=10.5, fill="#fffdf5", stroke="#b9a978", color=INK):
        f = 12
        pts = f"{x},{y} {x + w - f},{y} {x + w},{y + f} {x + w},{y + h} {x},{y + h}"
        self.raw(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
        self.raw(f'<polyline points="{x + w - f},{y} {x + w - f},{y + f} {x + w},{y + f}" fill="none" '
                 f'stroke="{stroke}" stroke-width="1"/>')
        for i, r in enumerate(rows):
            self.text(x + 8, y + 16 + i * size * 1.4, r, size=size, anchor="start", color=color)

    def frame(self, x, y, w, h, tag, stroke=INK, fill="none", dash=None, size=11.5, sw=1.2):
        """UML frame with a pentagon name tag (sd, stm, act, alt, loop ...)."""
        self.rect(x, y, w, h, fill=fill, stroke=stroke, dash=dash, sw=sw)
        t = len(tag) * size * 0.5 + 18
        pts = f"{x},{y} {x + t},{y} {x + t},{y + 14} {x + t - 8},{y + 22} {x},{y + 22}"
        self.raw(f'<polygon points="{pts}" fill="{WHITE}" stroke="{stroke}" stroke-width="{sw}"/>')
        self.text(x + 7, y + 15.5, tag, size=size, anchor="start", weight="600")

    def node(self, x, y, w, h, title, stereo="device", d=12, fill=WHITE):
        """Deployment node (3-D box)."""
        self.raw(f'<polygon points="{x},{y + d} {x + d},{y} {x + w + d},{y} {x + w + d},{y + h - d} {x + w},{y + h} '
                 f'{x + w},{y + d}" fill="{RULE}" stroke="{INK}" stroke-width="1.2"/>')
        self.raw(f'<line x1="{x + w}" y1="{y + d}" x2="{x + w + d}" y2="{y}" stroke="{INK}" stroke-width="1.2"/>')
        self.rect(x, y + d, w, h - d, fill=fill, stroke=INK)
        self.text(x + 10, y + d + 17, f"«{stereo}»", size=10.5, anchor="start", color=MUTED)
        self.text(x + 10, y + d + 33, title, size=13, anchor="start", weight="700")

    def artifact(self, x, y, w, h, title, sub=None, fill=WHITE):
        self.rect(x, y, w, h, fill=fill, stroke=INK)
        fx, fy = x + w - 16, y + 6
        self.raw(f'<polygon points="{fx},{fy} {fx + 7},{fy} {fx + 10},{fy + 3} {fx + 10},{fy + 13} {fx},{fy + 13}" '
                 f'fill="{WHITE}" stroke="{INK}" stroke-width="0.9"/>')
        self.text(x + 8, y + 16, "«artifact»", size=9.5, anchor="start", color=MUTED)
        self.text(x + 8, y + 31, title, size=11.5, anchor="start", weight="600", mono=True)
        if sub:
            for i, r in enumerate(sub.split("\n")):
                self.text(x + 8, y + 45 + i * 13, r, size=10, anchor="start", color=MUTED)

    def cylinder(self, x, y, w, h, title, sub=None, fill=WHITE):
        e = 8
        self.raw(f'<path d="M{x},{y + e} A{w / 2},{e} 0 0 0 {x + w},{y + e} L{x + w},{y + h - e} '
                 f'A{w / 2},{e} 0 0 1 {x},{y + h - e} Z" fill="{fill}" stroke="{INK}" stroke-width="1.2"/>')
        self.raw(f'<ellipse cx="{x + w / 2}" cy="{y + e}" rx="{w / 2}" ry="{e}" fill="{fill}" stroke="{INK}" '
                 f'stroke-width="1.2"/>')
        self.text(x + w / 2, y + h / 2 + 6, title, size=11.5, weight="600")
        if sub:
            self.text(x + w / 2, y + h / 2 + 20, sub, size=10, color=MUTED)

    def lollipop(self, x, y, label, side="right", size=10.5):
        """Provided interface (ball) with a short stem from (x, y)."""
        dx = 22 if side == "right" else -22 if side == "left" else 0
        dy = 22 if side == "down" else -22 if side == "up" else 0
        self.line([(x, y), (x + dx, y + dy)], sw=1.2)
        self.raw(f'<circle cx="{x + dx * 1.3}" cy="{y + dy * 1.3}" r="7" fill="{WHITE}" stroke="{INK}" '
                 f'stroke-width="1.3"/>')
        lx = x + dx * 1.3 + (12 if side == "right" else -12 if side == "left" else 0)
        ly = y + dy * 1.3 + (20 if side == "down" else -12 if side == "up" else 4)
        anchor = "start" if side == "right" else "end" if side == "left" else "middle"
        self.text(lx, ly, label, size=size, anchor=anchor, mono=True)

    def badge(self, x, y, n, colour=DATA):
        """Numbered circle used to key connectors to a legend."""
        self.raw(f'<circle cx="{x}" cy="{y}" r="9" fill="{colour}" stroke="{WHITE}" stroke-width="1.5"/>')
        self.text(x, y + 4, str(n), size=11, weight="700", color=WHITE)

    def pill(self, x, y, label, colours, size=10.5, mono=False):
        stroke, fill = colours
        w = tw(label, size) + 16
        self.rect(x, y - size - 3, w, size + 9, fill=fill, stroke=stroke, rx=(size + 9) / 2, sw=1)
        self.text(x + w / 2, y + 1, label, size=size, color=stroke, weight="600", mono=mono)
        return w

    def ladder(self, x, y, level, scale=1.0):
        """The Beretta evidence ladder: four ascending bars, `level` (0-4) filled."""
        cols = list(EV.values())
        for i in range(4):
            bh = (6 + i * 4) * scale
            bx = x + i * 6 * scale
            fill = cols[i] if i < level else WHITE
            self.rect(bx, y - bh, 4 * scale, bh, fill=fill, stroke=cols[i] if i < level else BORDER, sw=0.8)

    # ---------------------------------------------------------------- sequence helpers
    def lifeline(self, x, top, bottom, name, stereo=None, w=None, kind="box"):
        w = w or max(tw(name, 12.5) + 24, 96)
        if kind == "actor":
            self.actor(x, top + 10, name)
            y0 = top + 92
        else:
            h = 44 if stereo else 34
            self.rect(x - w / 2, top, w, h, fill=RAISED, stroke=INK, rx=3)
            if stereo:
                self.text(x, top + 15, f"«{stereo}»", size=10, color=MUTED)
                self.text(x, top + 33, name, size=12.5, weight="600")
            else:
                self.text(x, top + 22, name, size=12.5, weight="600")
            y0 = top + h
        self.line([(x, y0), (x, bottom)], dash="5 4", color=MUTED, sw=1)
        return y0

    def activation(self, x, y1, y2, fill=WHITE):
        self.rect(x - 5, y1, 10, y2 - y1, fill=fill, stroke=INK, sw=1)

    def msg(self, x1, x2, y, label, kind="sync", size=11, ldy=-6, mono=False):
        """sync: filled head; async: open head; reply: dashed open head; self: loop."""
        if kind == "self":
            self.line([(x1 + 5, y), (x1 + 40, y), (x1 + 40, y + 18), (x1 + 6, y + 18)], end="arrow")
            self.text(x1 + 46, y + 4, label, size=size, anchor="start", halo=True, mono=mono)
            return
        end = "arrow" if kind == "sync" else "open"
        dash = "6 4" if kind == "reply" else None
        sx = x1 + (5 if x2 > x1 else -5)
        ex = x2 - (5 if x2 > x1 else -5)
        self.line([(sx, y), (ex, y)], end=end, dash=dash)
        rows = label.split("\n")
        for i, r in enumerate(rows):
            self.text((x1 + x2) / 2, y + ldy - (len(rows) - 1 - i) * (size + 3), r, size=size, halo=True,
                      mono=mono, color=MUTED if kind == "reply" else INK)

    # ---------------------------------------------------------------- output
    def caption(self, num, text):
        if os.environ.get("BERETTA_NO_CAPTION"):
            self.h -= 26
            return
        self.text(16, self.h - 14, f"Figure {num}. {text}", size=12, anchor="start", color=MUTED, italic=True)

    def svg(self):
        defs = f"""<defs>
<marker id="m-arrow" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" markerHeight="11" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,1 L11,6 L0,11 z" fill="{INK}"/></marker>
<marker id="m-open" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,1 L11,6 L0,11" fill="none" stroke="{INK}" stroke-width="1.3"/></marker>
<marker id="m-tri" viewBox="0 0 16 16" refX="15" refY="8" markerWidth="16" markerHeight="16" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1,1 L15,8 L1,15 z" fill="{WHITE}" stroke="{INK}" stroke-width="1.2"/></marker>
<marker id="m-diamond" viewBox="0 0 20 12" refX="19" refY="6" markerWidth="20" markerHeight="12" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1,6 L10,1 L19,6 L10,11 z" fill="{INK}" stroke="{INK}"/></marker>
<marker id="m-odiamond" viewBox="0 0 20 12" refX="19" refY="6" markerWidth="20" markerHeight="12" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1,6 L10,1 L19,6 L10,11 z" fill="{WHITE}" stroke="{INK}"/></marker>
<marker id="m-many" viewBox="0 0 20 20" refX="19" refY="10" markerWidth="20" markerHeight="20" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M19,2 L5,10 L19,18 M5,2 L5,18" fill="none" stroke="{INK}" stroke-width="1.2"/></marker>
<marker id="m-one" viewBox="0 0 20 20" refX="19" refY="10" markerWidth="20" markerHeight="20" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M9,3 L9,17 M14,3 L14,17" fill="none" stroke="{INK}" stroke-width="1.2"/></marker>
<marker id="m-zmany" viewBox="0 0 26 20" refX="25" refY="10" markerWidth="26" markerHeight="20" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M25,2 L13,10 L25,18" fill="none" stroke="{INK}" stroke-width="1.2"/><circle cx="7" cy="10" r="4" fill="{WHITE}" stroke="{INK}" stroke-width="1.2"/></marker>
</defs>"""
        body = "\n".join(self.out)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" font-family="{FONT}">\n<title>{escape(self.title)}</title>\n'
                f'{defs}\n<rect width="{self.w}" height="{self.h}" fill="{WHITE}"/>\n{body}\n</svg>\n')
