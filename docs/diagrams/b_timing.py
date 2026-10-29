"""Behavioural UML: timing diagram of the whole life of a policy."""
from svg import D, INK, MUTED, WHITE, RAISED, DATA, DATA_SOFT, STATE_COLOURS, MET, MET_BG, BREACH, BREACH_BG, \
    GRACE, GRACE_BG, UNKNOWN, UNKNOWN_BG, REMED, REMED_BG

NONE = ("#9aa4b5", "#f7f8fa")
PASS = (MET, MET_BG)
FAIL = (BREACH, BREACH_BG)
WAIT = (GRACE, GRACE_BG)
INFO = (DATA, DATA_SOFT)


def timing():
    d = D(1500, 900, "Timing diagram: from enrolment to breach and repair", "Timing diagram")
    d.text(20, 32, "Timing: agent roll-out, quote, bind, then a breach and its repair (one control: EDR)", size=17,
           weight="700", anchor="start")
    x0, x1, days = 300, 1470, 21
    px = (x1 - x0) / days

    def X(t):
        return x0 + t * px

    rows = [
        ("Host KAL-PLANT-WS03", "agent liveness",
         [(0, 1, "not installed", NONE), (1, 21, "ONLINE  (reports every tick; heartbeat keeps it ≤ 6 h)", PASS)]),
        ("Host WS03: EDR check", "edr.running_healthy",
         [(0, 1, "—", NONE), (1, 10, "PASS", PASS), (10, 19, "FAIL  (Defender stopped)", FAIL), (19, 21, "PASS", PASS)]),
        ("Collector: fleet EDR", "4 hosts, 95 % rule",
         [(0, 1, "NOT_OBSERVABLE", NONE), (1, 10, "PASS  4/4", PASS), (10, 19, "FAIL  3/4 = 75 %", FAIL),
          (19, 21, "PASS 4/4", PASS)]),
        ("Platform: CTRL-EDR evidence", "resolved posture",
         [(0, 1, "STATED", WAIT), (1, 10, "VERIFIED  (AGENT_FLEET)", PASS), (10, 19, "NOT_WORKING", FAIL),
          (19, 21, "VERIFIED", PASS)]),
        ("Policy", "policies.status",
         [(0, 2, "DRAFT", NONE), (2, 3, "QUOTED", INFO), (3, 21, "BOUND", PASS)]),
        ("Warranty CTRL-EDR", "coverage state machine",
         [(0, 3, "—", NONE), (3, 10, "MET", STATE_COLOURS["MET"]), (10, 17, "IN_GRACE", STATE_COLOURS["IN_GRACE"]),
          (17, 19, "BREACHED", STATE_COLOURS["BREACHED"]), (19, 21, "MET", STATE_COLOURS["MET"])]),
        ("Premium", "₹, from the stored calculation",
         [(0, 2, "none", NONE), (2, 3, "quoted", INFO), (3, 21, "bound premium, fixed: unchanged through the breach",
                                                         INFO)]),
    ]
    top, rh = 150, 76
    # axis + day grid
    for t in range(days + 1):
        x = X(t)
        d.line([(x, top - 10), (x, top + rh * len(rows))], color="#edf0f4", sw=1)
        d.text(x, top + rh * len(rows) + 18, f"d{t}", size=10.5, color=MUTED)
    d.text(x0 + (x1 - x0) / 2, top + rh * len(rows) + 40, "time (days since onboarding; the demo compresses this "
                                                          "with fast-forward)", size=11, color=MUTED)
    # events
    events = [(0, "onboarding,\nquestionnaire (EDR: yes)"), (1, "agents\nenrolled"), (2, "quote"), (3, "bind"),
              (10, "EDR stops\non WS03"), (17, "grace\nexpires"), (19, "EDR\nrestored")]
    for t, lab in events:
        x = X(t)
        d.line([(x, top - 18), (x, top + rh * len(rows))], color=DATA, sw=1, dash="4 3")
        rows_ = lab.split("\n")
        for i, r in enumerate(rows_):
            d.text(x - (6 if t == 0 else 0), top - 52 + i * 14 + (2 - len(rows_)) * 14, r, size=10.5, color=DATA,
                   weight="600", anchor="end" if t == 0 else "middle")
    # rows
    for i, (name, sub, segs) in enumerate(rows):
        y = top + i * rh
        d.line([(20, y + rh), (x1, y + rh)], color="#c9cfd8", sw=1)
        d.text(24, y + 34, name, size=12.5, weight="700", anchor="start")
        d.text(24, y + 52, sub, size=10.5, anchor="start", color=MUTED)
        for (a, b, lab, (stroke, fill)) in segs:
            xa, xb, yc, hh = X(a), X(b), y + rh / 2, 30
            k = 6 if b - a > 0.3 else 2
            pts = f"{xa},{yc} {xa + k},{yc - hh / 2} {xb - k},{yc - hh / 2} {xb},{yc} {xb - k},{yc + hh / 2} " \
                  f"{xa + k},{yc + hh / 2}"
            d.raw(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')
            if (xb - xa) > len(lab) * 6.2 + 8:
                d.text((xa + xb) / 2, yc + 4, lab, size=10.5, weight="600", color=stroke)
            elif (xb - xa) > 30:
                d.text((xa + xb) / 2, yc + 4, lab[:max(1, int((xb - xa) / 7))], size=10, weight="600", color=stroke)
    d.line([(20, top), (x1, top)], color="#c9cfd8", sw=1)
    # duration constraint on the warranty row
    wy = top + 5 * rh + 8
    d.line([(X(10), wy), (X(17), wy)], start="open", end="open", color=GRACE, sw=1.2)
    d.text((X(10) + X(17)) / 2, wy - 4, "{7 days grace}", size=10.5, color=GRACE, weight="600", halo=True)
    d.line([(X(1), top + 2 * rh + 10), (X(1), top + 2 * rh + 10)])
    yb = top + rh * len(rows) + 60
    d.note(20, yb, 1450, 104, [
        "• A fleet result reaches the platform within one link-worker pass (≤ 30 s) of the report that changed it, "
        "or on the 15-minute heartbeat.",
        "• d10: one failing host out of four puts the fleet below 95 %, so CTRL-EDR is NOT_WORKING and the warranty "
        "starts its 7-day grace.",
        "• d17: still failing, so BREACHED: the configured coverage consequence applies (incident-response deductible "
        "doubled).",
        "• d19: the next passing roll-up moves BREACHED → REMEDIATED → MET at once. The premium line never moves "
        "after bind."], size=11)
    d.h = yb + 104 + 40
    d.caption("B17", "Timing diagram (value-lifeline form). Each row is one lifeline; a change of band is a state "
                     "change at that time.")
    return d


FIGURES = [("B17", "timing", "Timing diagram: roll-out, bind, breach and repair", timing)]
