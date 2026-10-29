"""Generate the document figures (300 dpi PNG, Beretta house style: navy / maroon / ledger grey)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

NAVY, MAROON, LEDGER, INK, GREY = "#12161d", "#1d5fbf", "#f2f4f7", "#0b0e14", "#5b6270"
BAD = "#9b1c22"  # breach red: bad news only
OK, WARN, INFO = "#145c33", "#8a4b06", "#1a4f8f"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10})


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def chip(ax, x, y, w, h, title, sub=None, edge=NAVY, fill=LEDGER, tcolor=NAVY, bold=True, fs=10, subfs=8.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                linewidth=1.4, edgecolor=edge, facecolor=fill))
    if sub:
        ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", color=tcolor, fontsize=fs,
                fontweight="bold" if bold else "normal")
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", color=INK, fontsize=subfs, linespacing=1.25)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", color=tcolor, fontsize=fs,
                fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, color=NAVY, label=None, lx=0, ly=0, style="-|>", ls="-", fs=8.2, rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=13, color=color,
                                 linewidth=1.4, linestyle=ls, connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, ha="center", va="center", fontsize=fs, color=color,
                bbox=dict(facecolor="white", edgecolor="none", pad=1.2))


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- 1. system overview
def fig_overview():
    fig, ax = canvas(11, 5.6)
    ax.text(0.2, 5.35, "Insured company's network", color=GREY, fontsize=9, fontweight="bold")
    ax.add_patch(FancyBboxPatch((0.1, 0.5), 3.4, 4.7, boxstyle="round,pad=0.02,rounding_size=0.15",
                                linewidth=1, edgecolor=GREY, facecolor="white", linestyle="--"))
    for i, (n, s) in enumerate([("Laptop", "Beretta agent"), ("Desktop", "Beretta agent"), ("Server", "Beretta agent")]):
        chip(ax, 0.45, 3.75 - i * 1.3, 2.7, 0.95, n, s + "  (read-only)")
    ax.text(4.0, 5.35, "Insurer (Beretta platform)", color=GREY, fontsize=9, fontweight="bold")
    ax.add_patch(FancyBboxPatch((3.9, 0.5), 7.0, 4.7, boxstyle="round,pad=0.02,rounding_size=0.15",
                                linewidth=1, edgecolor=GREY, facecolor="white", linestyle="--"))
    chip(ax, 4.9, 2.55, 2.4, 1.3, "Collector", "verify signature\nstore report\nroll up fleet")
    chip(ax, 8.1, 3.6, 2.5, 1.05, "Warranty state machine", "MET / IN_GRACE /\nBREACHED / REMEDIATED",
         edge=MAROON, tcolor=MAROON)
    chip(ax, 8.1, 2.1, 2.5, 1.0, "Monitoring dashboard", "browser, admin token")
    chip(ax, 8.1, 0.75, 2.5, 1.0, "Engine B: pricing", "premium fixed at bind", edge=GREY, tcolor=GREY)
    for i in range(3):
        arrow(ax, 3.15, 4.22 - i * 1.3, 4.9, 3.2)
    ax.text(4.35, 4.55, "signed reports\n(HTTPS, pinned CA)", ha="center", fontsize=8.2, color=NAVY)
    arrow(ax, 7.3, 3.45, 8.1, 4.1)
    arrow(ax, 7.3, 3.0, 8.1, 2.6)
    arrow(ax, 7.3, 2.75, 8.1, 1.25, color=BAD, style="-", ls=(0, (3, 3)))
    ax.text(7.95, 1.62, "no path", color=BAD, fontsize=8.5, fontweight="bold", ha="right")
    ax.plot([7.62, 7.82], [1.78, 2.02], color=BAD, lw=2)
    ax.plot([7.62, 7.82], [2.02, 1.78], color=BAD, lw=2)
    save(fig, "fig1_overview.png")


# ---------------------------------------------------------------- 2. agent layers (bottom to top)
def fig_layers():
    layers = [
        ("Operating system", "files, /proc, registry, PowerShell Get-* cmdlets, OS tools"),
        ("Collectors  (linux.py / windows.py / macos.py)", "read-only; list arguments, no shell, timeout on every call"),
        ("Parsers  (parsers.py)", "raw text/JSON  ->  plain facts; no OS access, fully unit-tested"),
        ("Verdicts  (verdicts.py)", "facts + thresholds  ->  PASS / FAIL + assurance level"),
        ("Policy  (policy.json)", "which checks run, how often, thresholds; data only, hashed"),
        ("Runner  (runner.py)", "one thread per check; crash / timeout / no-admin become explicit statuses"),
        ("Scheduler  (agent.py)", "intervals + jitter; full snapshot daily, deltas on change, heartbeat 15 min"),
        ("Envelope + signature  (security.py)", "canonical JSON, sequence number, HMAC-SHA256, build + policy hash"),
        ("Outbox  (spool.py)", "SQLite queue; survives reboots and network loss; replays in order"),
        ("Transport  (transport.py)", "HTTPS, TLS 1.2+, trusts only the collector's private CA"),
    ]
    h, gap = 0.62, 0.14
    fig, ax = canvas(10, len(layers) * (h + gap) + 0.6)
    for i, (t, s) in enumerate(layers):
        y = 0.3 + i * (h + gap)
        edge = MAROON if i in (0, 9) else NAVY
        ax.add_patch(FancyBboxPatch((0.3, y), 9.4, h, boxstyle="round,pad=0.01,rounding_size=0.1",
                                    linewidth=1.3, edgecolor=edge, facecolor=LEDGER if i not in (0, 9) else "white"))
        ax.text(0.45, y + h / 2, f"{i + 1}", color="white", fontsize=9, fontweight="bold", ha="center", va="center",
                bbox=dict(boxstyle="circle,pad=0.25", facecolor=edge, edgecolor="none"))
        ax.text(0.8, y + h * 0.66, t, color=edge, fontsize=10, fontweight="bold", va="center")
        ax.text(0.8, y + h * 0.28, s, color=INK, fontsize=8.6, va="center")
        if i < len(layers) - 1:
            arrow(ax, 9.3, y + h, 9.3, y + h + gap, style="-|>")
    save(fig, "fig2_agent_layers.png")


# ---------------------------------------------------------------- 3. ingestion gate
def fig_ingest():
    steps = [("Size", "at most\n1 MB", "413"), ("Agent known", "enrolled,\nnot retired", "401"),
             ("Signature", "HMAC over\nexact bytes", "401"), ("Schema", "version 2,\nids match", "400"),
             ("Sequence", "higher than\nlast seen", "409"), ("Timestamp", "not future,\n< 30 days old", "400"),
             ("Results", "statuses and\nids valid", "400")]
    fig, ax = canvas(13.9, 3.5)
    w, g = 1.45, 0.25
    for i, (t, s, code) in enumerate(steps):
        x = 0.2 + i * (w + g)
        chip(ax, x, 1.6, w, 1.2, t, s, subfs=8)
        ax.text(x + w / 2, 1.2, f"reject {code}", ha="center", color=BAD, fontsize=8.5)
        arrow(ax, x + w / 2, 1.58, x + w / 2, 1.33, color=BAD)
        arrow(ax, x + w, 2.2, x + w + g, 2.2)
    x = 0.2 + len(steps) * (w + g)
    chip(ax, x, 1.5, 1.4, 1.4, "Store", "report +\nobservations\n(append-only)", edge=OK, tcolor=OK, subfs=8)
    ax.text(0.2, 0.6, "Checks run in this order. Authentication comes before the body is parsed, so an attacker "
                      "cannot reach the JSON parser without the agent's secret.", fontsize=9, color=INK)
    ax.text(0.2, 0.22, "Unapproved build or policy hash: stored, but tagged UNTRUSTED and never counted toward "
                       "a warranty.", fontsize=9, color=INK)
    save(fig, "fig3_ingest.png")


# ---------------------------------------------------------------- 4. roll-up funnel
def fig_rollup():
    fig, ax = canvas(11, 3.3)
    boxes = [("Check result", "one check on one host\nPASS / FAIL / N/A / ...", 0.2),
             ("Host control", "any FAIL -> FAIL\nsilent: last FAIL -> FAIL;\nlast PASS -> left out 14 d", 2.95),
             ("Fleet control", ">= 95% of observed\nhosts must PASS", 5.7),
             ("Warranty", "state machine\nwith grace period", 8.45)]
    for t, s, x in boxes:
        chip(ax, x, 1.4, 2.35, 1.3, t, s, edge=MAROON if t == "Warranty" else NAVY,
             tcolor=MAROON if t == "Warranty" else NAVY)
    for x in (2.55, 5.3, 8.05):
        arrow(ax, x, 2.05, x + 0.4, 2.05)
    ax.text(0.2, 0.85, "Only TECHNICALLY_OBSERVED results count (SIMULATED too, for demo companies).", fontsize=8.6)
    ax.text(0.2, 0.5, "NOT_SUPPORTED / NOT_APPLICABLE / ERROR / SILENT_PASS hosts are left out of the ratio. If no host can observe a "
                      "control, it is NOT_OBSERVABLE", fontsize=8.6)
    ax.text(0.2, 0.2, "and the warranty does not move: missing evidence is not treated as a breach.", fontsize=8.6)
    save(fig, "fig4_rollup.png")


# ---------------------------------------------------------------- 5. state machine
def fig_states():
    fig, ax = canvas(10.5, 4.6)
    pos = {"MET": (0.4, 2.9), "IN_GRACE": (3.9, 2.9), "BREACHED": (7.4, 2.9), "REMEDIATED": (3.9, 0.5)}
    col = {"MET": OK, "IN_GRACE": WARN, "BREACHED": BAD, "REMEDIATED": INFO}
    for k, (x, y) in pos.items():
        chip(ax, x, y, 2.6, 0.95, k, edge=col[k], tcolor=col[k], fs=11)
    arrow(ax, 3.0, 3.55, 3.9, 3.55, color=INK)
    ax.text(3.45, 4.1, "control fails", ha="center", fontsize=8.2, color=INK)
    arrow(ax, 6.5, 3.55, 7.4, 3.55, color=INK)
    ax.text(6.95, 4.12, "grace expires,\nstill failing", ha="center", fontsize=8.2, color=INK)
    arrow(ax, 5.0, 2.9, 4.8, 1.45, label="fixed", lx=-0.35, color=INK)
    arrow(ax, 8.4, 2.9, 6.5, 1.2, label="fixed", lx=0.45, ly=0.15, color=INK)
    arrow(ax, 3.9, 1.0, 1.7, 2.9, label="fix held 24 h", lx=-0.55, ly=-0.05, color=INK)
    arrow(ax, 5.6, 1.45, 5.8, 2.9, label="fails again\n(new grace)", lx=0.72, color=INK)
    ax.text(0.4, 0.15, "Grace: PATCH 14 d, EDR / BACKUP / MFA 7 d,\nMONITORING_COVERAGE 14 d  [C-asm]",
            fontsize=8.4, color=INK)
    ax.text(7.2, 0.95, "NOT_OBSERVABLE: no transition", fontsize=8.6, color=GREY)
    ax.text(7.2, 0.6, "Premium: never touched", fontsize=8.6, color=MAROON, fontweight="bold")
    save(fig, "fig5_states.png")


# ---------------------------------------------------------------- 6. liveness timeline
def fig_liveness():
    fig, ax = canvas(10, 2.55)
    segs = [(0, 1.6, "ONLINE", OK, "results trusted"), (1.6, 5.4, "UNVERIFIED", WARN,
                                                         "last results kept, flagged, no warranty change"),
            (5.4, 9.6, "SILENT", BAD, "last result FAIL: still counts as FAIL\n"
                                         "last result PASS: left out of the roll-up\nfor up to 14 days, then counts as FAIL")]
    for a, b, t, c, s in segs:
        ax.add_patch(FancyBboxPatch((0.2 + a, 1.35), b - a - 0.05, 0.55, boxstyle="round,pad=0.01,rounding_size=0.08",
                                    facecolor=c, edgecolor="none"))
        ax.text(0.2 + (a + b) / 2, 1.625, t, color="white", fontweight="bold", ha="center", va="center")
        ax.text(0.2 + (a + b) / 2, 0.85, s, ha="center", va="top", fontsize=8.4, linespacing=1.35)
    for x, lab in ((0.2, "last report"), (1.8, "6 h"), (5.6, "72 h")):
        ax.plot([x, x], [1.3, 2.0], color=INK, lw=1)
        ax.text(x, 2.15, lab, ha="center", fontsize=8.6)
    ax.text(0.2, 0.02, "Any message resets the clock, including a 15-minute heartbeat with no results in it. "
                       "Silent hosts never count as reporting for coverage. Thresholds [C-asm].", fontsize=8.0, color=GREY)
    save(fig, "fig6_liveness.png")


# ---------------------------------------------------------------- 7. deployment
def fig_deploy():
    fig, ax = canvas(11, 4.4)
    chip(ax, 0.3, 2.9, 3.0, 1.15, "1. Insurer sets up collector", "init, gen-cert, add-company,\nbind, approve build")
    chip(ax, 4.0, 2.9, 3.0, 1.15, "2. Insurer sends to insured", "ca.pem + enrollment token\n+ agent package")
    chip(ax, 7.7, 2.9, 3.0, 1.15, "3. Insured IT installs", "install.ps1 / install.sh\n(admin rights)")
    chip(ax, 7.7, 0.9, 3.0, 1.15, "4. Agent enrolls", "gets its own id + secret;\nstarts as a service")
    chip(ax, 4.0, 0.9, 3.0, 1.15, "5. Reports flow", "full daily, deltas,\nheartbeat every 15 min")
    chip(ax, 0.3, 0.9, 3.0, 1.15, "6. Insurer watches", "dashboard: fleet,\nwarranties, events", edge=MAROON,
         tcolor=MAROON)
    arrow(ax, 3.3, 3.47, 4.0, 3.47)
    arrow(ax, 7.0, 3.47, 7.7, 3.47)
    arrow(ax, 9.2, 2.9, 9.2, 2.05)
    arrow(ax, 7.7, 1.47, 7.0, 1.47)
    arrow(ax, 4.0, 1.47, 3.3, 1.47)
    save(fig, "fig7_deploy.png")


if __name__ == "__main__":
    for f in (fig_overview, fig_layers, fig_ingest, fig_rollup, fig_states, fig_liveness, fig_deploy):
        f()
    print("figures written to", OUT)
