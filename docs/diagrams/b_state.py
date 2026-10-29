"""Behavioural UML: state machine diagrams."""
from svg import (D, INK, MUTED, WHITE, RAISED, GROUND, DATA, DATA_SOFT, STATE_COLOURS, EV, MET, BREACH, GRACE,
                 UNKNOWN, UNKNOWN_BG, REMED, MET_BG, BREACH_BG, GRACE_BG, REMED_BG)


def _table(d, x, y, widths, rows, size=11, head=True):
    """Simple ruled table; rows[0] is the header when head=True."""
    rh = size * 1.9
    w = sum(widths)
    d.rect(x, y, w, rh * len(rows), fill=WHITE, stroke=INK, sw=1)
    if head:
        d.rect(x, y, w, rh, fill=RAISED, stroke=INK, sw=1)
    for i, row in enumerate(rows):
        cx = x
        for j, cell in enumerate(row):
            d.text(cx + 8, y + rh * i + rh * 0.66, cell, size=size, anchor="start",
                   weight="600" if head and i == 0 else "normal", mono=(j == 0 and not (head and i == 0)))
            cx += widths[j]
        if i:
            d.line([(x, y + rh * i), (x + w, y + rh * i)], color="#c9cfd8", sw=0.8)


# ================================================================================================ B3
def sm_warranty_platform():
    d = D(1400, 800, "Warranty state machine (platform)", "State machine diagram")
    d.text(20, 32, "Warranty state machine on the platform: one per bound policy × warranty control", size=17,
           weight="700", anchor="start")
    d.frame(20, 50, 1360, 470, "stm  Warranty  (coverage.evaluate_policy)")
    d.initial(90, 205)
    d.state(170, 160, 230, 90, "MET", ["no coverage consequence"], STATE_COLOURS["MET"])
    d.state(590, 160, 240, 90, "IN_GRACE", ["grace period running", "(7 or 14 days)"], STATE_COLOURS["IN_GRACE"])
    d.state(1060, 160, 260, 90, "BREACHED", ["configured coverage", "consequence applies"], STATE_COLOURS["BREACHED"])
    d.state(590, 400, 240, 90, "REMEDIATED", ["transient: restored to MET", "in the same evaluation"],
            STATE_COLOURS["REMEDIATED"])
    d.line([(98, 205), (170, 205)], end="arrow", label="bind /\ninitialize_warranties()", ldy=24, ldx=-6, lsize=10.5)
    d.line([(400, 190), (590, 190)], end="arrow", label="control FAIL /\nbreach_detected_at = now,\n"
                                                         "grace_expires_at = now + grace", ldy=-40, lsize=10.5)
    d.line([(830, 190), (1060, 190)], end="arrow", label="[now ≥ grace_expires_at]\nstill FAIL", ldy=-22,
           lsize=10.5)
    d.line([(710, 250), (710, 400)], end="arrow", label="PASS or PARTIAL /\nclear grace dates", ldx=8,
           lanchor="start", ldy=-10, lsize=10.5)
    d.line([(1190, 250), (1190, 445), (830, 445)], end="arrow", label="PASS or PARTIAL /\nclear grace dates",
           lseg=1, ldy=-22, lsize=10.5)
    d.line([(590, 445), (285, 445), (285, 250)], end="arrow", label="[immediately] /\n\"Warranty restored\"",
           lseg=0, ldy=-22, lsize=10.5)
    d.note(60, 300, 190, 92, ["Evidence UNKNOWN: no", "change. Absence of a report", "is not a breach.",
                              "Every transition writes a", "warranty_event and audit row."], size=10)
    d.note(880, 290, 220, 84, ["Expiry is also checked", "lazily on every read of the", "warranties, and by the demo's",
                               "fast-forward (DEMO_TIME_TRAVEL)."], size=10)
    d.text(30, 552, "Warranty controls and their configured consequences (catalogue.py, illustrative wording)",
           size=13, weight="700", anchor="start")
    _table(d, 30, 566, [210, 90, 1040], [
        ["Control", "Grace", "Coverage consequence while BREACHED"],
        ["CTRL-MFA", "7 days", "Ransomware and cyber-extortion coverage head suspended"],
        ["CTRL-BACKUP-TESTED", "7 days", "Data-restoration claims subject to 50 % co-insurance"],
        ["CTRL-EDR", "7 days", "Incident-response deductible doubled"],
        ["CTRL-PATCH-CRIT", "14 days", "Claims arising from unpatched critical CVEs subject to co-insurance"],
        ["CTRL-AGENT-COVERAGE", "14 days", "Unmonitored endpoints treated as non-compliant with every warranty"],
    ])
    d.text(30, 742, "What triggers an evaluation: any new observation for the company (questionnaire, document, "
                    "fleet roll-up), bind itself, and the expiry check. The premium never changes.", size=11.5,
           anchor="start", color=MUTED)
    d.caption("B3", "State machine of a platform warranty. Guards in [ ], effects after /.")
    return d


# ================================================================================================ B4
def sm_warranty_collector():
    d = D(1400, 640, "Warranty state machine (collector, standalone)", "State machine diagram")
    d.text(20, 32, "Warranty state machine in the collector (standalone companies only)", size=17, weight="700",
           anchor="start")
    d.frame(20, 50, 1360, 470, "stm  Warranty  (evaluate.step, pure function)")
    d.initial(90, 205)
    d.state(170, 160, 230, 90, "MET", ["fleet control passes"], STATE_COLOURS["MET"])
    d.state(590, 160, 240, 90, "IN_GRACE", ["grace: PATCH 14 d, EDR 7 d,", "BACKUP 7 d, coverage 14 d"],
            STATE_COLOURS["IN_GRACE"])
    d.state(1060, 160, 260, 90, "BREACHED", ["coverage effect applies"], STATE_COLOURS["BREACHED"])
    d.state(590, 380, 240, 90, "REMEDIATED", ["fix must hold 24 h"], STATE_COLOURS["REMEDIATED"])
    d.line([(98, 205), (170, 205)], end="arrow", label="bind", ldy=-8, lsize=10.5)
    d.line([(400, 190), (590, 190)], end="arrow", label="FAIL /\nstart grace", ldy=-22, lsize=10.5)
    d.line([(830, 190), (1060, 190)], end="arrow", label="[grace expired]\nstill FAIL", ldy=-22, lsize=10.5)
    d.line([(680, 250), (680, 380)], end="arrow", label="PASS", ldx=-8, lanchor="end", lsize=10.5)
    d.line([(760, 380), (760, 250)], end="arrow", label="FAIL (regression) /\nnew grace period", ldx=8,
           lanchor="start", lsize=10.5, ldy=-8)
    d.line([(1190, 250), (1190, 425), (830, 425)], end="arrow", label="PASS", lseg=1, ldy=-8, lsize=10.5)
    d.line([(590, 425), (285, 425), (285, 250)], end="arrow", label="[PASS held ≥ 24 h]", lseg=0, ldy=-8,
           lsize=10.5)
    d.note(60, 300, 200, 78, ["NOT_OBSERVABLE never", "moves a warranty: absence", "of evidence is not evidence",
                              "of breach."], size=10)
    d.note(30, 540, 1340, 56, ["For a company linked to the platform this machine is not used: the collector "
                               "displays the platform's states (B3), and the platform's REMEDIATED → MET is "
                               "immediate.",
                               "The fleet control fed in is PASS only when ≥ 95 % of observed hosts pass."], size=11)
    d.caption("B4", "State machine of a collector warranty. Differs from B3 in the 24 h hold and the regression "
                    "transition.")
    return d


# ================================================================================================ B5
def sm_evidence():
    d = D(1400, 860, "Control evidence state machine", "State machine diagram")
    d.text(20, 32, "Evidence status of one control: how new observations change what pricing sees", size=17,
           weight="700", anchor="start")
    d.frame(20, 50, 930, 640, "stm  Control evidence status  (resolve_posture → evidence_status)")
    st = {"UNKNOWN": (UNKNOWN, UNKNOWN_BG), "STATED": (GRACE, GRACE_BG), "VERIFIED": (MET, MET_BG),
          "NOT_WORKING": (BREACH, BREACH_BG)}
    d.initial(80, 150)
    d.state(130, 110, 220, 80, "UNKNOWN", ["no evidence  →  m_lacks"], st["UNKNOWN"])
    d.state(620, 110, 260, 80, "STATED", ["declared or partial", "→ 1 − 0.6 (1 − m_has)"], st["STATED"])
    d.state(130, 480, 220, 80, "NOT_WORKING", ["observed failing  →  m_lacks"], st["NOT_WORKING"])
    d.state(620, 480, 260, 80, "VERIFIED", ["observed, tested or", "independent  →  m_has"], st["VERIFIED"])
    d.line([(88, 150), (130, 150)], end="arrow")
    d.line([(350, 140), (620, 140)], end="arrow", label="questionnaire yes · self-assessment\n"
                                                         "· own policy doc · partial result", ldy=-22, lsize=10.5)
    d.line([(240, 190), (240, 480)], end="arrow", label="questionnaire no ·\nagent / fleet /\nscan FAIL", ldx=-8,
           lanchor="end", lsize=10.5)
    d.line([(350, 180), (620, 500)], end="arrow", label="TECHNICALLY_OBSERVED PASS ·\nTESTED · SOC 2 / ISO / VAPT",
           lpos=0.3, ldx=-12, lanchor="end", lsize=10.5)
    d.line([(800, 190), (800, 480)], end="arrow", label="stronger PASS\n[strength ≥ best]", ldx=8, lanchor="start",
           lsize=10.5)
    d.line([(700, 480), (700, 190)], end="arrow", label="PARTIAL\n[strength ≥ best]\ne.g. fleet BACKUP", ldx=-8,
           lanchor="end", lsize=10.5)
    d.line([(620, 535), (350, 535)], end="arrow", label="FAIL [strength ≥ best]", ldy=-8, lsize=10.5)
    d.line([(350, 555), (620, 555)], end="arrow", label="PASS [strength ≥ best], e.g. fix seen by agent",
           ldy=20, lsize=10.5)
    d.line([(620, 175), (330, 480)], end="arrow", label="FAIL [strength ≥ best]", lpos=0.62, ldx=-10,
           lanchor="end", lsize=10.5)
    d.note(40, 610, 880, 62, ["Resolution rule: among a control's ACTIVE observations, the highest evidence strength "
                              "wins; a tie goes to the most recent.",
                              "So a later questionnaire \"yes\" (DECLARED) cannot hide an agent FAIL "
                              "(TECHNICALLY_OBSERVED). Before bind the status prices the",
                              "risk at the next quote; after bind it only drives warranties (B3)."], size=10.5)
    # evidence ladder
    d.text(990, 70, "Evidence strength (lowest to highest)", size=13, weight="700", anchor="start")
    rows = [("DECLARED", "questionnaire answer", 1), ("DOCUMENTED", "document assessed, with locator", 2),
            ("TESTED", "restore test, tabletop, pentest", 3),
            ("TECHNICALLY_OBSERVED", "agent, fleet or outside-in scan", 4)]
    for i, (name, sub, lvl) in enumerate(rows):
        y = 110 + i * 62
        d.rect(990, y, 380, 52, fill=WHITE, stroke="#c9cfd8", rx=6)
        d.ladder(1006, y + 38, lvl, scale=1.1)
        d.text(1046, y + 22, name, size=12, weight="700", anchor="start", color=list(EV.values())[i], mono=True)
        d.text(1046, y + 40, sub, size=10.5, anchor="start", color=MUTED)
    d.text(990, 380, "Multipliers (Marsh 2023: relative risk S, adoption p)", size=13, weight="700", anchor="start")
    _table(d, 990, 394, [150, 230], [["Status", "Multiplier"], ["VERIFIED", "m_has = 1 / (p + (1−p) S)"],
                                     ["STATED", "1 − x (1 − m_has), x = 0.6"],
                                     ["NOT_WORKING", "m_lacks = S / (p + (1−p) S)"], ["UNKNOWN", "m_lacks"]],
           size=11)
    d.note(990, 520, 380, 92, ["Gate: a warranty passes only when VERIFIED;", "MFA also passes when STATED (it cannot",
                               "be observed). STATED → conditionally eligible;", "NOT_WORKING or UNKNOWN → ineligible",
                               "under BLOCK."], size=10.5)
    d.text(20, 730, "Examples", size=13, weight="700", anchor="start")
    d.lines(20, 752, ["• Questionnaire says EDR yes → STATED. The fleet roll-up then reports EDR PASS on ≥ 95 % "
                      "of hosts → VERIFIED.",
                      "• One host's EDR stops and the fleet drops below 95 % → NOT_WORKING. A later questionnaire "
                      "\"yes\" changes nothing.",
                      "• Backups: the fleet can see a recent backup but not a restore test, so a pass arrives as "
                      "PARTIAL → STATED."], size=11.5, anchor="start")
    d.caption("B5", "State machine of a control's evidence status. Every transition is a new observation that "
                    "becomes the best one.")
    return d


# ================================================================================================ B6
def sm_liveness():
    d = D(1400, 760, "Host liveness state machine", "State machine diagram")
    d.text(20, 32, "Machine liveness: how long a host may stay quiet before its results stop counting", size=17,
           weight="700", anchor="start")
    d.frame(20, 50, 1360, 400, "stm  Host liveness  (evaluate.liveness, judged on every evaluation)")
    d.initial(70, 200)
    d.state(120, 150, 220, 100, "ENROLLED", ["agent_id + secret issued", "clock starts at enrolled_at"],
            (INK, WHITE))
    d.state(460, 150, 220, 100, "ONLINE", ["quiet ≤ 6 h", "results count"], STATE_COLOURS["MET"])
    d.state(800, 150, 220, 100, "UNVERIFIED", ["6 h < quiet ≤ 72 h", "shown, no warranty change"],
            STATE_COLOURS["IN_GRACE"])
    d.state(1140, 150, 220, 100, "SILENT", ["quiet > 72 h", "silence rule applies"], STATE_COLOURS["BREACHED"])
    d.line([(78, 200), (120, 200)], end="arrow")
    d.line([(340, 200), (460, 200)], end="arrow", label="first accepted\nreport", ldy=-22, lsize=10.5)
    d.line([(680, 185), (800, 185)], end="arrow", label="[quiet > 6 h]", ldy=-8, lsize=10.5)
    d.line([(1020, 185), (1140, 185)], end="arrow", label="[quiet > 72 h]", ldy=-8, lsize=10.5)
    d.line([(800, 225), (680, 225)], end="arrow", label="report accepted", ldy=20, lsize=10.5)
    d.line([(1250, 250), (1250, 310), (570, 310), (570, 250)], end="arrow", label="report accepted (any kind,"
                                                                               " heartbeat too)", lseg=1, ldy=-6,
           lsize=10.5)
    d.line([(230, 250), (230, 360), (1290, 360), (1290, 250)], end="arrow", dash="6 4",
           label="[never reported, 72 h after enrolment]", lseg=1, ldy=-6, lsize=10.5)
    d.line([(1360, 200), (1372, 200)], color=WHITE)
    d.final(1350, 420)
    d.line([(1320, 250), (1340, 410)], end="arrow", label="retire", ldx=10, lanchor="start", lsize=10.5)

    d.frame(20, 470, 1360, 230, "stm  Silence rule for one control on a SILENT host  (evaluate.host_control)")
    d.initial(70, 590)
    d.decision(200, 590, 170, 70, "last trusted\nresult?")
    d.line([(78, 590), (115, 590)], end="arrow")
    d.state(420, 510, 260, 64, "FAIL", ["counts as failing in the roll-up"], STATE_COLOURS["BREACHED"])
    d.state(420, 610, 260, 64, "SILENT_PASS", ["left out of the fleet ratio"], STATE_COLOURS["UNKNOWN"])
    d.state(860, 610, 260, 64, "FAIL", ["counts as failing"], STATE_COLOURS["BREACHED"])
    d.line([(200, 555), (200, 542), (420, 542)], end="arrow", label="[FAIL, or no trusted result]", lseg=1,
           ldy=-6, lsize=10.5)
    d.line([(285, 590), (300, 590), (300, 642), (420, 642)], end="arrow", label="[PASS]", lseg=2, ldy=-6,
           lsize=10.5)
    d.line([(680, 642), (860, 642)], end="arrow", label="[quiet > 14 days]", ldy=-6, lsize=10.5)
    d.note(1150, 500, 220, 180, ["Going quiet can never hide", "a failure. A host whose last", "result passed is "
                                 "excused for", "14 days (leave, holidays),", "then counts as FAIL.",
                                 "Coverage still counts every", "SILENT host as not", "reporting."], size=10.5)
    d.text(20, 726, "Thresholds from collector settings ([C-asm] demonstration values): unverified_after_hours 6, "
                    "silent_after_hours 72, silent_pass_exclusion_days 14.", size=11.5, anchor="start", color=MUTED)
    d.caption("B6", "State machines for host liveness (top) and the per-control silence rule (bottom).")
    return d


# ================================================================================================ B7
def sm_policy():
    d = D(1400, 660, "Policy lifecycle state machine", "State machine diagram")
    d.text(20, 32, "Policy lifecycle: from intake to a bound, monitored policy", size=17, weight="700",
           anchor="start")
    d.frame(20, 50, 1360, 520, "stm  Policy  (policies.status)")
    d.initial(70, 200)
    d.state(120, 150, 220, 100, "DRAFT", ["created at onboarding", "evidence being gathered"], (INK, WHITE))
    d.state(500, 150, 240, 100, "QUOTED", ["≥ 1 stored calculation", "price, gate, referral"], (DATA, DATA_SOFT))
    d.rect(960, 100, 400, 330, fill=WHITE, stroke=MET, rx=14, sw=1.5)
    d.text(1160, 124, "BOUND", size=14, weight="700", color=MET)
    d.line([(960, 136), (1360, 136)], color=MET, sw=0.8)
    d.lines(980, 160, ["bound_premium and calculation fixed",
                       "coverages locked; quote refused (409)",
                       "do / one warranty machine per",
                       "      warranty control (B3)"], size=11, anchor="start")
    for i, (n, c) in enumerate([("MET", "MET"), ("IN_GRACE", "IN_GRACE"), ("BREACHED", "BREACHED")]):
        d.state(985 + i * 125, 250, 115, 44, n, colours=STATE_COLOURS[c], tsize=11.5, rx=10)
    d.text(1160, 330, "monitoring changes these states only;", size=11, color=MUTED)
    d.text(1160, 346, "repricing_performed is always false", size=11, color=MUTED)
    d.text(30, 136, "created by POST /api/companies", size=10.5, anchor="start")
    d.line([(78, 200), (120, 200)], end="arrow")
    d.line([(340, 200), (500, 200)], end="arrow", label="calculate_premium()\n[persist] / POLICY_QUOTED", ldy=-22,
           lsize=10.5)
    d.line([(560, 150), (560, 110), (680, 110), (680, 150)], end="arrow", label="re-quote / new calculation", lseg=1,
           ldy=-6, lsize=10.5)
    d.decision(850, 200, 60, 60)
    d.line([(740, 200), (820, 200)], end="arrow", label="bind_policy()", ldy=-8, lsize=10.5)
    d.line([(880, 200), (960, 200)], end="arrow", label="[gate ok and\nreferral cleared]", ldy=-22, lsize=10.5)
    d.line([(850, 230), (850, 330), (620, 330), (620, 250)], end="arrow",
           label="[INELIGIBLE under BLOCK] / 409 INELIGIBLE\n"
                 "[referral not approved] / REFERRAL_REQUIRED", lseg=1, ldy=22, lsize=10.5)
    d.note(980, 470, 380, 80, ["Effect of bind: status BOUND, bound_at,", "bound_calculation_id, bound_premium;",
                               "initialize_warranties() then evaluate at once,", "so a control already failing starts "
                               "IN_GRACE."], size=10.5)
    d.note(60, 400, 520, 150, ["Referral reasons (pricing V2):", "• turnover above USD 2B",
                               "• a peril's control multiplier at the 3.0 ceiling", "• two or more material incidents "
                               "in 3 years", "• an RBI- or SEBI-regulated entity",
                               "Gate: warranties MFA, backups, EDR, patching must be", "VERIFIED (MFA may be STATED)."],
           size=10.5)
    d.text(30, 602, "There is no final state in the prototype: policy expiry and renewal are not modelled.",
           size=11.5, anchor="start", color=MUTED)
    d.caption("B7", "State machine of a policy. The diamond is a choice point evaluated by bind_policy().")
    return d


FIGURES = [
    ("B3", "sm_warranty_platform", "State machine: warranty (platform)", sm_warranty_platform),
    ("B4", "sm_warranty_collector", "State machine: warranty (collector, standalone)", sm_warranty_collector),
    ("B5", "sm_evidence", "State machine: control evidence status", sm_evidence),
    ("B6", "sm_liveness", "State machine: host liveness and silence rule", sm_liveness),
    ("B7", "sm_policy", "State machine: policy lifecycle", sm_policy),
]
