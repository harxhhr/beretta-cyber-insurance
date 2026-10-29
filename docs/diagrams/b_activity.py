"""Behavioural UML: activity diagrams and flowcharts."""
from svg import D, INK, MUTED, WHITE, RAISED, GROUND, DATA, DATA_SOFT, MET, MET_BG, BREACH, BREACH_BG, GRACE_BG, \
    GRACE, UNKNOWN, UNKNOWN_BG


def flow_final(d, x, y, r=9):
    d.raw(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{WHITE}" stroke="{INK}" stroke-width="1.3"/>')
    k = r * 0.7
    d.line([(x - k, y - k), (x + k, y + k)], sw=1.3)
    d.line([(x - k, y + k), (x + k, y - k)], sw=1.3)


def panel(d, x, y, w, title, rows, size=11):
    h = 30 + len(rows) * size * 1.5 + 8
    d.rect(x, y, w, h, fill=RAISED, stroke="#c9cfd8", rx=6)
    d.text(x + 12, y + 20, title, size=12, weight="700", anchor="start")
    for i, r in enumerate(rows):
        d.text(x + 12, y + 40 + i * size * 1.5, r, size=size, anchor="start", mono=r.startswith(" "))
    return h


# ================================================================================================ B11
def act_ingest():
    d = D(1420, 920, "Activity: collector report ingestion", "Activity diagram")
    d.text(20, 32, "Activity: how the collector checks one report before it can count", size=17, weight="700",
           anchor="start")
    d.frame(14, 46, 1392, 830, "act  core.ingest()  (authenticate before parsing)")
    cx = 380
    d.initial(cx, 76)
    d.action(cx - 150, 96, 300, 40, "Receive POST /api/v1/report")
    d.arrow(cx, 84, cx, 96)
    checks = [("body ≤ 1 MB?", "413 TOO_LARGE"), ("agent enrolled\nand not retired?", "401 UNKNOWN_AGENT"),
              ("HMAC-SHA256 signature\nmatches the body?", "401 BAD_SIGNATURE · audit REPORT_REJECTED"),
              ("valid JSON, schema v2,\nsame agent_id?", "400 BAD_JSON · SCHEMA_VERSION · AGENT_MISMATCH"),
              ("seq > agent.last_seq?", "409 REPLAY · audit (agent acks: it was delivered)"),
              ("created_at within\n30 days … now + 5 min?", "400 TOO_OLD · FUTURE_TIMESTAMP"),
              ("kind full / delta / heartbeat,\nevery result valid?", "400 BAD_KIND · BAD_RESULT")]
    y = 136
    for i, (q, err) in enumerate(checks):
        dy = y + 24 + i * 86
        d.arrow(cx, dy - 24 if i == 0 else dy - 26, cx, dy)
        d.decision(cx, dy + 30, 230, 60, q, size=10.5)
        d.line([(cx + 115, dy + 30), (560, dy + 30)], end="arrow", label="[no]", lpos=0.4, ldy=-6, lsize=10.5)
        d.action(560, dy + 10, 270, 40, err, size=10.5, fill=BREACH_BG, stroke=BREACH)
        flow_final(d, 856, dy + 30)
        d.line([(830, dy + 30), (847, dy + 30)], end="arrow")
        if i < len(checks) - 1:
            d.text(cx + 8, dy + 74, "[yes]", size=10.5, anchor="start")
    last = y + 24 + 6 * 86 + 60
    d.text(cx + 8, last + 16, "[yes]", size=10.5, anchor="start")
    d.line([(cx, last), (cx, last + 30), (876, last + 30), (876, 110), (1040, 110), (1040, 130)], end="arrow")

    # evidence strength column
    sx = 1040
    q2 = [("simulated flag set?", "SIMULATED", "counts only for a demo company", (GRACE, GRACE_BG), "[yes]"),
          ("build hash approved?", "UNTRUSTED_BUILD", "never counts", (BREACH, BREACH_BG), "[no]"),
          ("policy hash approved?", "UNTRUSTED_POLICY", "never counts", (BREACH, BREACH_BG), "[no]")]
    for i, (q, name, sub, col, guard) in enumerate(q2):
        cy = 160 + i * 100
        d.decision(sx, cy, 210, 56, q, size=10.5)
        d.line([(sx + 105, cy), (1170, cy)], end="arrow", label=guard, lpos=0.45, ldy=-6, lsize=10.5)
        d.action(1170, cy - 24, 200, 48, name, sub=sub, size=11, fill=col[1], stroke=col[0], weight="600")
        d.line([(1370, cy), (1390, cy), (1390, 520), (1060, 520)], end="arrow")
        d.arrow(sx, cy + 28, sx, cy + 72)
        d.text(sx + 8, cy + 48, "[no]" if i == 0 else "[yes]", size=10.5, anchor="start")
    d.action(sx - 110, 432, 220, 46, "TECHNICALLY_OBSERVED", sub="results count", fill=MET_BG, stroke=MET,
             weight="600")
    d.arrow(sx, 478, sx, 500)
    d.decision(sx, 520, 40, 40)
    steps = ["Store report (immutable) and its\nobservations; update last_seq, last_seen",
             "Upsert results_current, only where\nobserved_at is newer than the stored one",
             "Return 202 {accepted, report_id,\nevidence_strength}",
             "Wake the link worker\n(linked companies are re-evaluated)"]
    for i, t in enumerate(steps):
        y0 = 566 + i * 72
        d.arrow(sx, 540 if i == 0 else y0 - 22, sx, y0)
        d.action(sx - 150, y0, 300, 50, t, size=11)
    d.arrow(sx, 566 + 3 * 72 + 50, sx, 566 + 3 * 72 + 72)
    d.final(sx, 566 + 3 * 72 + 82)
    d.text(14, 898, "Late-arriving old reports are stored but never overwrite a newer current result.", size=11.5,
           anchor="start", color=MUTED)
    d.h = 950
    d.caption("B11", "Activity diagram of report ingestion. ⊗ ends a rejected report: nothing is stored.")
    return d


# ================================================================================================ B12
def act_pricing():
    d = D(1420, 1330, "Flowchart: pricing model V2", "Activity diagram")
    d.text(20, 32, "Flowchart: how Engine B (UNDERWRITING_MODEL_V2) prices a quote", size=17, weight="700",
           anchor="start")
    cx, w = 400, 420
    x0 = cx - w / 2
    d.initial(cx, 66)
    d.action(x0, 86, w, 54, "Collect inputs", sub="NIC code, turnover, years, RBI/SEBI flag,\nclaims, limit, retention")
    d.arrow(cx, 74, cx, 86)
    d.arrow(cx, 140, cx, 162)
    d.decision(cx, 192, 180, 58, "policy BOUND?")
    d.line([(cx + 90, 192), (720, 192)], end="arrow", label="[yes]", lpos=0.3, ldy=-6)
    d.action(720, 170, 300, 44, "Refuse: POLICY_ALREADY_BOUND", sub="monitoring never re-prices", size=11,
             fill=BREACH_BG, stroke=BREACH)
    flow_final(d, 1046, 192)
    d.line([(1020, 192), (1037, 192)], end="arrow")
    d.text(cx + 8, 238, "[no]", size=10.5, anchor="start")
    seq = [("Classify the firm", "sector from NIC 2008 (unmapped → 1.0);\nturnover band, ×/÷ 1.25 transition zones"),
           ("Read evidence status per control", "VERIFIED · STATED · NOT_WORKING · UNKNOWN")]
    y = 252
    for t, sub in seq:
        d.arrow(cx, y - 30 if y == 252 else y - 22, cx, y)
        d.action(x0, y, w, 58, t, sub=sub)
        y += 80
    # expansion region over perils
    d.arrow(cx, y - 22, cx, y + 6)
    d.rect(x0 - 30, y + 6, w + 60, 290, fill=GROUND, stroke=INK, dash="6 4", rx=10)
    d.text(x0 - 20, y + 26, "«parallel»  for each peril: RANSOMWARE, BEC, FTF, MISC_FIRST_PARTY, THIRD_PARTY",
           size=10.5, anchor="start", color=MUTED)
    per = [("Frequency λ_p", "λ_global × R_turnover × R_sector × F_india\n× M_controls,p × M_claims"),
           ("Severity X_p ~ Lognormal", "mean m_p × R_turnover_sev × R_sector_sev × S_india\nσ = 2.193"),
           ("Expected payout", "E[ min( Σ_h s_p,h · M_sev,p,h · (X_p − d)+ , L_total ) ]\n24,000-point quantile grid")]
    yy = y + 40
    for i, (t, sub) in enumerate(per):
        if i:
            d.arrow(cx, yy - 22, cx, yy)
        d.action(x0, yy, w, 64, t, sub=sub)
        yy += 86
    y = y + 296
    rest = [("Expected loss  EL = Σ_p λ_p × payout_p", None),
            ("Technical premium = EL × (1 + trend) ÷ TLR", "trend = 0, TLR = 0.50"),
            ("Payable = technical × 1.18", "GST 18 %, shown as its own line"),
            ("Gate the warranties", "MFA, backups, EDR, patching → ELIGIBLE /\nCONDITIONALLY_ELIGIBLE / INELIGIBLE"),
            ("Referral check", "reasons shown; bind needs approval"),
            ("What-if savings", "re-price with each control VERIFIED,\nlargest saving first"),
            ("Persist calculation", "input snapshot + full parameter file;\nDRAFT → QUOTED; audit POLICY_QUOTED")]
    for t, sub in rest:
        d.arrow(cx, y, cx, y + 22)
        h = 40 if not sub else 44 + sub.count("\n") * 14
        d.action(x0, y + 22, w, h, t, sub=sub)
        y += 22 + h
    d.arrow(cx, y, cx, y + 22)
    d.final(cx, y + 32)

    # detail panels
    px, pw = 780, 610
    h1 = panel(d, px, 262, pw, "Control multiplier (Marsh 2023: relative risk S, adoption p)",
               ["VERIFIED      m_has   = 1 / (p + (1 − p) S)", "STATED        1 − 0.6 × (1 − m_has)",
                "NOT_WORKING   m_lacks = S / (p + (1 − p) S)", "UNKNOWN       m_lacks",
                "each multiplier capped to [0.5, 2.0]; the average firm sits at 1.0"])
    d.line([(px, 340), (x0 + w, 360)], dash="4 4", color=MUTED)
    h2 = panel(d, px, 262 + h1 + 14, pw, "Combining controls into M_controls,p",
               ["stages: credential, weakness, execution", "within a stage, largest |ln m| first:",
                "   ln M_stage = Σ_k β^k · ln m_k,   β = 0.5", "across stages: multiply",
                "clamp the result to [0.27, 3.0]"])
    d.line([(px, 262 + h1 + 50), (x0 + w, 480)], dash="4 4", color=MUTED)
    h3 = panel(d, px, 262 + h1 + h2 + 28, pw, "Claims history M_claims (same for every peril, no cap)",
               ["   M_claims = (α + N) ÷ (α + λ_firm × T),   α = 4.22",
                "N = material incidents in 3 years; T = min(3, years in operation)"])
    d.line([(px, 262 + h1 + h2 + 60), (x0 + w, 500)], dash="4 4", color=MUTED)
    panel(d, px, 930, pw, "Gate and referral rules (gating never changes the price)",
          ["warranty VERIFIED → passes (MFA also passes when STATED)", "any warranty STATED → CONDITIONALLY_ELIGIBLE",
           "NOT_WORKING or UNKNOWN → INELIGIBLE under BLOCK (WARN: override)",
           "refer if turnover > USD 2B, a multiplier at 3.0, ≥ 2 incidents, RBI/SEBI"])
    d.line([(px, 960), (x0 + w, 980)], dash="4 4", color=MUTED)
    d.note(px, 1110, pw, 64, ["Every number above lives in app/pricing_v2_params.json with its source and tag",
                              "[L] published · [D] derived by a script · [A] assumption with a sensitivity range.",
                              "pricing_v2.reproduce(snapshot) gives the same premium later."], size=10.5)
    d.h = y + 80
    d.caption("B12", "Flowchart of the V2 premium. Worked example (docs/premium_model_v2.md §11): EL ₹49,947, "
                     "technical ₹99,895, payable ₹1,17,876.")
    return d


# ================================================================================================ B13
def act_agent_loop():
    d = D(1000, 1380, "Activity: agent service loop", "Activity diagram")
    d.text(20, 32, "Activity: one tick of the agent service (Agent.tick)", size=17, weight="700", anchor="start")
    L, C, R, w = 180, 480, 790, 260

    def act(x, y, t, h=42, sub=None, **kw):
        d.action(x - w / 2, y, w, h, t, sub=sub, size=11, **kw)

    d.initial(C, 66)
    act(C, 86, "Service starts", sub="load agent.json and policy.json")
    d.arrow(C, 74, C, 86)
    d.arrow(C, 128, C, 158)
    d.decision(C, 175, 36, 34)
    d.arrow(C, 192, C, 210)
    act(C, 210, "take_scan_request()", sub="scan-now.json in the state dir")
    d.arrow(C, 252, C, 270)
    d.decision(C, 300, 200, 60, "scan-now request?")
    for x, t, g in [(L, "scan()  due checks", "[no file]"), (C, "scan(listed checks)", "[controls listed]"),
                    (R, "scan(force_full=True)", "[empty request]")]:
        if x == C:
            d.arrow(C, 330, C, 360)
            d.text(C + 8, 348, g, size=10.5, anchor="start")
        else:
            sx = C - 100 if x < C else C + 100
            d.line([(sx, 300), (x, 300), (x, 360)], end="arrow", label=g, lseg=0, ldy=-6, lsize=10.5)
        act(x, 360, t)
        d.line([(x, 402), (x, 425), (C + (-18 if x < C else 18 if x > C else 0), 425)] if x != C else
               [(C, 402), (C, 408)], end="arrow")
    d.decision(C, 425, 36, 34)
    d.arrow(C, 442, C, 466)
    d.decision(C, 498, 230, 64, "full snapshot due?\n(or forced)")
    d.line([(C + 115, 498), (R, 498), (R, 540)], end="arrow", label="[yes]", lseg=0, ldy=-6, lsize=10.5)
    act(R, 540, "Run all 12 checks", sub="enqueue('full', results)", h=50)
    d.arrow(C, 530, C, 552)
    d.text(C + 8, 546, "[no]", size=10.5, anchor="start")
    act(C, 552, "Run checks whose interval is due")
    d.arrow(C, 594, C, 614)
    d.decision(C, 644, 230, 60, "any fingerprint\nchanged?")
    d.arrow(C, 674, C, 700)
    d.text(C + 8, 692, "[yes]", size=10.5, anchor="start")
    act(C, 700, "enqueue('delta', changed)")
    d.line([(C - 115, 644), (L, 644), (L, 780), (C - 18, 780)], end="arrow", label="[no]", lseg=0, ldy=-6,
           lsize=10.5)
    d.arrow(C, 742, C, 763)
    d.line([(R, 590), (R, 780), (C + 18, 780)], end="arrow")
    d.decision(C, 780, 36, 34)
    d.arrow(C, 797, C, 822)
    d.decision(C, 852, 200, 60, "heartbeat due?")
    d.line([(C + 100, 852), (R, 852), (R, 880)], end="arrow", label="[yes]", lseg=0, ldy=-6, lsize=10.5)
    act(R, 880, "enqueue('heartbeat', [])")
    d.line([(R, 922), (R, 950), (C + 18, 950)], end="arrow")
    d.arrow(C, 882, C, 933)
    d.text(C + 8, 905, "[no]", size=10.5, anchor="start")
    d.decision(C, 950, 36, 34)
    d.arrow(C, 967, C, 990)
    act(C, 990, "flush(): POST each pending report", sub="X-KYH-Signature = v1=HMAC-SHA256", h=50)
    d.arrow(C, 1040, C, 1060)
    d.decision(C, 1090, 200, 60, "collector reply?")
    outs = [(L, "spool.ack(seq)", "[200, 202, 409 REPLAY]", (MET, MET_BG)),
            (C, "spool.dead_letter(seq)", "[other 4xx]", (BREACH, BREACH_BG)),
            (R, "backoff = min(max(2b, 30), 900)\nstop this flush", "[429, 5xx, network]", (GRACE, GRACE_BG))]
    for x, t, g, col in outs:
        if x == C:
            d.arrow(C, 1120, C, 1150)
            d.text(C + 8, 1140, g, size=10.5, anchor="start")
        else:
            sx = C - 100 if x < C else C + 100
            d.line([(sx, 1090), (x, 1090), (x, 1150)], end="arrow", label=g, lseg=0, ldy=-6, lsize=10.5)
        d.action(x - w / 2, 1150, w, 46, t, size=11, fill=col[1], stroke=col[0])
        if x != C:
            d.line([(x, 1196), (x, 1220), (C + (-18 if x < C else 18), 1220)], end="arrow")
    d.arrow(C, 1196, C, 1203)
    d.decision(C, 1220, 36, 34)
    d.arrow(C, 1237, C, 1258)
    act(C, 1258, "sleep(max(30 s, backoff))")
    d.line([(C, 1300), (C, 1320), (34, 1320), (34, 175), (C - 18, 175)], end="arrow", label="next tick", lseg=1,
           lpos=0.5, ldx=-2, ldy=0, lanchor="middle", lsize=10.5)
    d.note(640, 210, 330, 64, ["Any exception is written to agent-errors.log;", "the loop survives it. Only this "
                               "service scans", "and sends: the outbox and seq stay consistent."], size=10.5)
    d.caption("B13", "Activity diagram of the agent loop. Small diamonds merge flows.")
    return d


# ================================================================================================ B14
def act_end_to_end():
    lanes = [("Insured", 210), ("Underwriter / Admin", 250), ("Collector operator", 220),
             ("Insured IT + agent", 220), ("Collector", 230), ("Platform", 250)]
    W = sum(w for _, w in lanes) + 40
    d = D(int(W), 1260, "Activity: end-to-end onboarding to a monitored policy", "Activity diagram")
    d.text(20, 32, "Activity with swimlanes: from onboarding to an active, monitored policy", size=17, weight="700",
           anchor="start")
    x, xs = 20, {}
    for name, w in lanes:
        d.rect(x, 50, w, 1160, fill=WHITE if len(xs) % 2 else GROUND, stroke=INK, sw=1)
        d.rect(x, 50, w, 34, fill=RAISED, stroke=INK, sw=1)
        d.text(x + w / 2, 72, name, size=12.5, weight="700")
        xs[name] = (x + w / 2, w)
        x += w

    def a(lane, y, t, h=48, **kw):
        cx, w = xs[lane]
        d.action(cx - (w - 24) / 2, y, w - 24, h, t, size=10.5, **kw)
        return cx

    def go(p1, p2, **kw):
        d.line([p1, p2] if p1[0] == p2[0] or p1[1] == p2[1] else [p1, (p1[0], (p1[1] + p2[1]) / 2),
                                                                   (p2[0], (p1[1] + p2[1]) / 2), p2],
               end="arrow", **kw)

    I, U, O, T, C, P = (xs[n][0] for n, _ in lanes)
    d.initial(I, 98)
    a("Insured", 120, "Onboard company\n(profile, NIC, turnover)")
    go((I, 106), (I, 120))
    a("Platform", 120, "Create company,\nDRAFT policy")
    go((I + 93, 144), (P - 113, 144))
    a("Insured", 196, "Answer questionnaire;\nregister documents, claims")
    go((I, 168), (I, 196))
    a("Platform", 196, "Record DECLARED /\nDOCUMENTED observations")
    go((I + 93, 220), (P - 113, 220))
    a("Underwriter / Admin", 272, "Assess documents;\nregister collector, link company")
    go((P, 244), (U, 272), label="", lsize=10)
    a("Collector operator", 348, "add-company, link-company,\napprove build + policy hash")
    go((U, 320), (O, 348))
    a("Collector operator", 424, "issue-token\n(max uses, expiry)")
    go((O, 396), (O, 424))
    a("Insured IT + agent", 500, "Install agent on each\nendpoint with token + CA")
    go((O, 472), (T, 500), label="token, ca.pem", lsize=10, lseg=1, ldy=-5)
    a("Collector", 500, "Enrol: agent_id +\nsecret; audit")
    go((T + 98, 524), (C - 103, 524))
    a("Insured IT + agent", 576, "Run 12 read-only checks;\nsend signed reports")
    go((T, 548), (T, 576))
    a("Collector", 576, "Verify, store; liveness;\n95 % fleet roll-up")
    go((T + 98, 600), (C - 103, 600))
    a("Platform", 652, "Record AGENT_FLEET evidence\n(TECHNICALLY_OBSERVED)")
    go((C, 624), (P, 652), label="signed roll-up", lsize=10, lseg=1, ldy=-5)
    a("Underwriter / Admin", 728, "Calculate quote (Engine B)")
    go((P, 700), (U, 728))
    d.decision(U, 830, 210, 64, "gate ELIGIBLE and\nreferral cleared?", size=10.5)
    go((U, 776), (U, 798))
    d.line([(U - 105, 830), (xs["Underwriter / Admin"][0] - 118, 830), (xs["Underwriter / Admin"][0] - 118, 750)],
           color=INK)
    d.line([(U - 118, 750), (U - 112, 750)], end="arrow")
    d.text(U - 112, 812, "[no]", size=10.5, anchor="start")
    a("Insured", 900, "Fix the gap; evidence\nimproves (STATED → VERIFIED)", fill=GRACE_BG, stroke=GRACE)
    d.line([(U - 60, 852), (I, 870), (I, 900)], end="arrow", dash="6 4", label="savings shown", lsize=10, lseg=0)
    d.line([(I - 93, 924), (32, 924), (32, 220), (I - 93, 220)], dash="6 4", end="arrow", label="re-answer, add evidence", lseg=1, lpos=0.5, ldx=8, ldy=0, lanchor="start", lsize=10)
    a("Underwriter / Admin", 900, "Bind at the stored\ncalculation")
    go((U, 862), (U, 900))
    d.text(U + 8, 888, "[yes]", size=10.5, anchor="start")
    a("Platform", 976, "BOUND: premium fixed;\nwarranties initialised (MET)", fill=MET_BG, stroke=MET)
    go((U, 948), (P, 976))
    a("Collector", 1052, "Keep evaluating fleet;\npush on change / 15 min")
    a("Platform", 1128, "Warranty machine only:\nMET ↔ IN_GRACE → BREACHED", fill=DATA_SOFT, stroke=DATA)
    go((C, 1100), (P, 1128), label="roll-ups", lsize=10, lseg=1, ldy=-5)
    d.line([(P, 1024), (P, 1040), (C + 40, 1040), (C + 40, 1052)], end="arrow", dash="6 4")
    d.final(P + 100, 1196)
    d.line([(P, 1176), (P, 1196), (P + 90, 1196)], end="arrow")
    d.h = 1240
    d.caption("B14", "Swimlane activity diagram of the whole process. The premium is set once, at bind.")
    return d


FIGURES = [
    ("B11", "act_ingest", "Activity: collector report ingestion", act_ingest),
    ("B12", "act_pricing", "Flowchart: pricing model V2", act_pricing),
    ("B13", "act_agent_loop", "Activity: agent service loop", act_agent_loop),
    ("B14", "act_end_to_end", "Activity (swimlanes): onboarding to a monitored policy", act_end_to_end),
]
