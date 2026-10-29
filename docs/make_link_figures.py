"""Figures for the Part 1 + Part 2 link document (Beretta house style)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

NAVY, MAROON, LEDGER, INK, GREY, OK = "#12161d", "#1d5fbf", "#f2f4f7", "#0b0e14", "#5b6270", "#145c33"
BAD = "#9b1c22"  # breach red: bad news only
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10})


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def chip(ax, x, y, w, h, title, sub=None, edge=NAVY, tcolor=NAVY, fill=LEDGER, fs=10, subfs=8.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", linewidth=1.4,
                                edgecolor=edge, facecolor=fill))
    if sub:
        ax.text(x + w / 2, y + h * 0.7, title, ha="center", va="center", color=tcolor, fontsize=fs, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.32, sub, ha="center", va="center", color=INK, fontsize=subfs, linespacing=1.3)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", color=tcolor, fontsize=fs, fontweight="bold")


def arrow(ax, x1, y1, x2, y2, color=NAVY, ls="-", style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=13, color=color,
                                 linewidth=1.4, linestyle=ls))


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_architecture():
    fig, ax = canvas(12, 5.6)
    for x, w, label in ((0.1, 2.6, "Insured company"), (3.1, 3.6, "Part 2: Beretta collector"),
                        (7.1, 4.8, "Part 1: Beretta platform")):
        ax.add_patch(FancyBboxPatch((x, 0.35), w, 4.75, boxstyle="round,pad=0.02,rounding_size=0.15",
                                    linewidth=1, edgecolor=GREY, facecolor="white", linestyle="--"))
        ax.text(x + 0.1, 5.25, label, color=GREY, fontsize=9.5, fontweight="bold")
    for i, h in enumerate(("Laptop", "Desktop", "Server")):
        chip(ax, 0.35, 3.75 - i * 1.25, 2.1, 0.9, h, "Beretta agent (read-only)")
    chip(ax, 3.35, 3.3, 3.1, 1.45, "Ingest + roll-up", "signed reports, replay check,\nsilence rule, 95% per control")
    chip(ax, 3.35, 1.45, 3.1, 1.3, "Link worker", "map controls, sign, push\non change or every 15 min")
    chip(ax, 3.35, 0.55, 3.1, 0.7, "Endpoint dashboard", fs=9)
    chip(ax, 7.35, 3.45, 2.1, 1.3, "Engine A", "AGENT_FLEET evidence\nTECHNICALLY_OBSERVED")
    chip(ax, 9.65, 3.45, 2.0, 1.3, "Engine B", "uses it before bind;\nprices once", edge=GREY, tcolor=GREY)
    chip(ax, 7.35, 1.45, 4.3, 1.4, "Warranty state machine (only one)", "MET / IN_GRACE / BREACHED / REMEDIATED\n"
                                                                     "incl. Live monitoring coverage", edge=MAROON,
         tcolor=MAROON)
    chip(ax, 7.35, 0.55, 4.3, 0.7, "Platform dashboard (Monitoring tab)", fs=9)
    for i in range(3):
        arrow(ax, 2.45, 4.2 - i * 1.25, 3.35, 4.0)
    arrow(ax, 4.9, 3.3, 4.9, 2.75)
    arrow(ax, 6.45, 2.1, 7.35, 3.75)
    ax.text(6.55, 3.25, "signed roll-up", fontsize=8.2, color=NAVY, rotation=60)
    arrow(ax, 8.4, 3.45, 8.4, 2.85)
    ax.text(8.5, 3.08, "after bind", fontsize=8, color=MAROON)
    arrow(ax, 9.45, 4.1, 9.65, 4.1)
    arrow(ax, 7.35, 1.75, 6.45, 1.75, color=MAROON, ls=(0, (3, 2)))
    ax.text(6.9, 1.25, "warranty states\nread back", fontsize=7.8, color=MAROON, ha="center")
    save(fig, "link_fig1_architecture.png")


def fig_sequence():
    lanes = [("Agent", 0.9), ("Collector", 3.6), ("Link worker", 6.3), ("Beretta platform", 9.4)]
    steps = [
        (0, 1, "1. signed report (EDR: FAIL on WS03)"),
        (1, 1, "2. checks: signature, sequence, time; stores it"),
        (1, 2, "3. wake the worker"),
        (2, 2, "4. evaluate fleet: EDR 3/4 hosts pass, below 95%"),
        (2, 2, "5. map EDR -> CTRL-EDR = FAIL; sign; seq + 1"),
        (2, 3, "6. POST /api/collector/rollup"),
        (3, 3, "7. verify; AGENT_FLEET observation; evaluate warranties"),
        (3, 2, "8. reply: EDR warranty IN_GRACE, repricing_performed: false"),
        (2, 1, "9. store the reply; dashboards show IN_GRACE"),
    ]
    h = 0.62 * len(steps) + 1.4
    fig, ax = canvas(11.6, h)
    for name, x in lanes:
        chip(ax, x - 0.85, h - 0.75, 1.7, 0.55, name, fs=9.5)
        ax.plot([x, x], [0.2, h - 0.75], color=GREY, lw=1, ls=(0, (3, 3)))
    y = h - 1.25
    for a, b, text in steps:
        xa, xb = lanes[a][1], lanes[b][1]
        if a == b:
            ax.add_patch(FancyBboxPatch((xa - 0.07, y - 0.12), 0.14, 0.24, boxstyle="round,pad=0.01",
                                        facecolor=NAVY, edgecolor=NAVY))
            ax.text(xa + 0.2, y, text, fontsize=8.4, va="center", color=INK)
        else:
            color = MAROON if b < a else NAVY
            arrow(ax, xa, y, xb, y, color=color)
            ax.text((xa + xb) / 2, y + 0.16, text, fontsize=8.4, ha="center", color=color)
        y -= 0.62
    save(fig, "link_fig2_sequence.png")


# The screenshots (p1_*, p2_*) are captured already cropped to their page section, so nothing is cropped here.

if __name__ == "__main__":
    fig_architecture()
    fig_sequence()
    print("ok")
