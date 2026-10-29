"""Figures for the complete agent guide (Beretta house style)."""
from make_link_figures import BAD, GREY, INK, LEDGER, MAROON, NAVY, OK, arrow, canvas, chip, save  # noqa: F401
from matplotlib.patches import FancyBboxPatch

AMBER = "#8a4b06"


def band(ax, x, y, w, h, label):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", linewidth=1,
                                edgecolor=GREY, facecolor="white", linestyle="--"))
    ax.text(x + 0.12, y + h - 0.28, label, color=GREY, fontsize=9.2, fontweight="bold")


def fig_one_check():
    """The full path of one check, from a Windows setting to a platform warranty."""
    rows = [
        ("VM / laptop", [("Windows setting", "Defender real-time\nprotection switched off"),
                         ("Collector function", "Get-MpComputerStatus\n(read-only PowerShell)"),
                         ("Parser", "JSON -> facts:\nrealtime_enabled = false"),
                         ("Verdict", "FAIL, assurance PRESENT\n\"real-time protection off\"")]),
        ("Agent", [("Runner", "guarded thread,\ntime budget, CheckResult"),
                   ("Scheduler", "fingerprint changed\n-> delta report"),
                   ("Envelope", "seq 42, build + policy hash,\nHMAC-SHA256 signature"),
                   ("Outbox -> HTTPS", "SQLite queue, then TLS 1.2+\nto the pinned CA only")]),
        ("Collector", [("Ingest gate", "size, agent, signature,\nschema, seq, time, results"),
                       ("Stored", "report + observation;\nTECHNICALLY_OBSERVED"),
                       ("Host control", "this host: EDR FAIL"),
                       ("Fleet roll-up", "4/5 hosts pass = 80%\n< 95% -> EDR FAIL")]),
        ("Platform", [("Signed roll-up", "CTRL-EDR = false,\nseq + 1, HMAC"),
                      ("Engine A", "AGENT_FLEET observation,\nstrongest evidence wins"),
                      ("Warranty", "CTRL-EDR: MET -> IN_GRACE\n7-day grace"),
                      ("Premium", "unchanged;\nrepricing_performed: false")]),
    ]
    fig, ax = canvas(11.9, 8.4)
    w, h, gap = 2.55, 1.15, 0.33
    for r, (lane, items) in enumerate(rows):
        y0 = 8.4 - (r + 1) * 2.05
        band(ax, 0.05, y0 - 0.05, 11.8, 1.95, lane)
        for i, (t, sub) in enumerate(items):
            x = 0.45 + i * (w + gap)
            last = r == 3 and i == 3
            col = MAROON if (r == 3 and i == 2) else (OK if last else NAVY)
            chip(ax, x, y0 + 0.25, w, h, t, sub, edge=col, tcolor=col, fs=9.3, subfs=7.6)
            if i < 3:
                arrow(ax, x + w, y0 + 0.25 + h / 2, x + w + gap, y0 + 0.25 + h / 2, color=GREY)
        if r < 3:   # the last chip of each row hands over to the first chip of the next row
            ax.text(0.45 + 3 * (w + gap) + w, y0 + 0.02, "continues in the next row  ", fontsize=7.6,
                    color=GREY, ha="right", va="bottom", style="italic")
    save(fig, "guide_fig_one_check.png")


def fig_two_jobs():
    fig, ax = canvas(12, 4.6)
    band(ax, 0.05, 2.45, 11.9, 2.0, "Before bind: monitoring is evidence for the quote")
    band(ax, 0.05, 0.15, 11.9, 2.0, "After bind: monitoring drives warranties only")
    chip(ax, 0.4, 2.7, 2.4, 1.2, "Fleet roll-up", "AGENT_FLEET,\nTECHNICALLY_OBSERVED")
    chip(ax, 3.4, 2.7, 2.6, 1.2, "Engine A", "best evidence per control\n(beats questionnaire)")
    chip(ax, 6.6, 2.7, 2.4, 1.2, "Engine B", "VERIFIED status:\nfull control effect")
    chip(ax, 9.5, 2.7, 2.2, 1.2, "Quote", "premium fixed\nat bind", edge=OK, tcolor=OK)
    for x1, x2 in ((2.8, 3.4), (6.0, 6.6), (9.0, 9.5)):
        arrow(ax, x1, 3.3, x2, 3.3)
    chip(ax, 0.4, 0.4, 2.4, 1.2, "Fleet roll-up", "same signed\nroll-up")
    chip(ax, 3.4, 0.4, 2.6, 1.2, "Engine A", "observation recorded\n(history kept)")
    chip(ax, 6.6, 0.4, 2.4, 1.2, "Warranty machine", "MET / IN_GRACE /\nBREACHED / REMEDIATED",
         edge=MAROON, tcolor=MAROON, fs=9.4)
    chip(ax, 9.5, 0.4, 2.2, 1.2, "Premium", "never re-priced", edge=GREY, tcolor=GREY)
    for x1, x2 in ((2.8, 3.4), (6.0, 6.6)):
        arrow(ax, x1, 1.0, x2, 1.0)
    ax.plot([9.05, 9.45], [0.75, 1.25], color=BAD, lw=2)
    ax.plot([9.05, 9.45], [1.25, 0.75], color=BAD, lw=2)
    ax.text(9.25, 1.72, "no path", fontsize=8, color=BAD, ha="center")
    save(fig, "guide_fig_two_jobs.png")


def fig_platform_states():
    fig, ax = canvas(12, 4.4)
    chip(ax, 0.3, 2.4, 2.2, 1.1, "MET", edge=OK, tcolor=OK, fs=12)
    chip(ax, 4.2, 2.4, 2.4, 1.1, "IN_GRACE", edge=AMBER, tcolor=AMBER, fs=12)
    chip(ax, 8.4, 2.4, 2.4, 1.1, "BREACHED", edge=BAD, tcolor=BAD, fs=12)
    chip(ax, 4.2, 0.3, 2.4, 1.1, "REMEDIATED", edge=NAVY, tcolor=NAVY, fs=12)
    arrow(ax, 2.5, 3.1, 4.2, 3.1)
    ax.text(3.35, 3.3, "roll-up: FAIL", fontsize=8.6, ha="center", color=INK)
    arrow(ax, 6.6, 3.1, 8.4, 3.1)
    ax.text(7.5, 3.3, "grace expired,\nstill FAIL", fontsize=8.6, ha="center", color=INK)
    arrow(ax, 5.2, 2.4, 5.2, 1.4)
    ax.text(4.6, 1.85, "PASS", fontsize=8.6, ha="center", color=INK)
    arrow(ax, 8.9, 2.4, 6.6, 1.0)
    ax.text(8.25, 1.55, "PASS", fontsize=8.6, ha="center", color=INK)
    arrow(ax, 4.2, 0.85, 1.4, 2.4)
    ax.text(2.1, 1.35, "immediately\n(same evaluation)", fontsize=8.6, ha="center", color=INK)
    ax.text(0.3, 4.05, "Grace: PATCH 14 d · EDR 7 d · BACKUP 7 d · MFA 7 d · Monitoring coverage 14 d",
            fontsize=9, color=INK)
    ax.text(7.2, 0.75, "UNKNOWN (no evidence): no change\nPARTIAL counts as PASS\nPremium: never touched",
            fontsize=8.8, color=GREY)
    save(fig, "guide_fig_platform_states.png")


if __name__ == "__main__":
    fig_one_check()
    fig_two_jobs()
    fig_platform_states()
    print("ok")
