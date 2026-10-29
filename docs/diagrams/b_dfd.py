"""Data flow diagrams (Gane–Sarson notation): context (level 0) and level 1."""
from svg import D, INK, MUTED, WHITE, RAISED, GROUND, DATA, DATA_SOFT, PRIMARY


def entity(d, x, y, w, h, name, sub=None):
    d.rect(x + 5, y + 5, w, h, fill="#c9cfd8", stroke="none")
    d.rect(x, y, w, h, fill=WHITE, stroke=INK, sw=1.4)
    d.text(x + w / 2, y + h / 2 + (-2 if sub else 5), name, size=12.5, weight="700")
    if sub:
        d.text(x + w / 2, y + h / 2 + 15, sub, size=10.5, color=MUTED)


def process(d, x, y, w, h, num, name, sub=None):
    d.rect(x, y, w, h, fill=DATA_SOFT, stroke=DATA, rx=12, sw=1.5)
    d.line([(x, y + 24), (x + w, y + 24)], color=DATA, sw=1)
    d.text(x + w / 2, y + 17, num, size=11, weight="700", color=DATA)
    rows = name.split("\n")
    for i, r in enumerate(rows):
        d.text(x + w / 2, y + 46 + i * 16, r, size=12, weight="600")
    if sub:
        d.text(x + w / 2, y + 46 + len(rows) * 16 + 2, sub, size=10, color=MUTED, mono=True)


def store(d, x, y, w, sid, name):
    h = 34
    d.rect(x, y, w, h, fill=WHITE, stroke="none")
    d.line([(x + w, y), (x, y), (x, y + h), (x + w, y + h)], sw=1.3)
    d.line([(x + 46, y), (x + 46, y + h)], sw=1.1)
    d.text(x + 23, y + 22, sid, size=11.5, weight="700")
    d.text(x + 56, y + 22, name, size=11.5, anchor="start")


def flow(d, pts, label=None, **kw):
    d.line(pts, end="arrow", label=label, lsize=10.5, **kw)


# ================================================================================================ B15
def dfd_context():
    d = D(1400, 820, "DFD level 0: context", "Data flow diagram")
    d.text(20, 32, "Data flow diagram, level 0 (context): Beretta and the people and machines around it", size=17,
           weight="700", anchor="start")
    process(d, 540, 300, 320, 170, "0", "Beretta cyber-insurance\nsystem", "agent · collector · platform")
    entity(d, 60, 110, 220, 70, "Insured SME", "CUSTOMER role")
    entity(d, 60, 590, 220, 70, "Underwriter", "UNDERWRITER role")
    entity(d, 590, 80, 220, 70, "Insured endpoints", "Windows · Linux · macOS")
    entity(d, 1120, 110, 220, 70, "Collector operator", "insurer IT")
    entity(d, 1120, 590, 220, 70, "Administrator", "ADMIN role")
    flow(d, [(280, 135), (560, 135), (560, 300)], "proposal form, documents, claims\n(entered by the underwriter)",
         lseg=0, ldy=-22)
    flow(d, [(600, 300), (600, 165), (280, 165)], "own company only: premium, evidence,\nwarranty states, monitoring view", lseg=1,
         ldy=20)
    flow(d, [(660, 150), (660, 300)], "read-only check results\n(signed reports)", ldx=-8, lanchor="end",
         lpos=0.45, ldy=0)
    flow(d, [(740, 300), (740, 150)], "enrolment credentials\n(agent_id, secret)", ldx=8, lanchor="start",
         lpos=0.45, ldy=0)
    flow(d, [(280, 615), (580, 615), (580, 470)], "intake entry, document assessments,\nsignals, quote and bind "
                                                  "decisions, referral approval", lseg=0, ldy=-22)
    flow(d, [(620, 470), (620, 640), (280, 640)], "premium breakdown, gate, referral\nreasons, warranty events, "
                                                  "audit", lseg=1, ldy=20)
    flow(d, [(1120, 135), (840, 135), (840, 300)], "companies, enrolment tokens,\napproved build and policy "
                                                   "hashes", lseg=0, ldy=-22)
    flow(d, [(800, 300), (800, 165), (1120, 165)], "fleet dashboard: hosts,\nliveness, controls", lseg=1, ldy=20)
    flow(d, [(1120, 615), (820, 615), (820, 470)], "loadings, gate mode, control weights,\nsector frequencies, "
                                                   "collectors", lseg=0, ldy=-22)
    flow(d, [(780, 470), (780, 640), (1120, 640)], "audit log", lseg=1, ldy=16)
    d.note(60, 700, 1280, 52, ["What never crosses the boundary from an endpoint: file contents, browsing, "
                               "keystrokes, e-mail, passwords, clear-text user names.",
                               "Simulated endpoints in the demo are labelled SIMULATED in every view."], size=11)
    d.caption("B15", "Context DFD. Squares: external entities; rounded box: the system as one process.")
    return d


# ================================================================================================ B16
def dfd_level1():
    d = D(1620, 980, "DFD level 1", "Data flow diagram")
    d.text(20, 32, "Data flow diagram, level 1: how evidence flows from an endpoint to a warranty state", size=17,
           weight="700", anchor="start")
    d.rect(20, 52, 1580, 330, fill=GROUND, stroke="#c9cfd8", rx=8, dash="5 3")
    d.text(32, 72, "Part 2: live monitoring (kyh-agent)", size=12, weight="700", anchor="start", color=MUTED)
    d.rect(20, 400, 1580, 470, fill=GROUND, stroke="#c9cfd8", rx=8, dash="5 3")
    d.text(32, 420, "Part 1: Beretta platform (kyh-cyber-insurance)", size=12, weight="700", anchor="start",
           color=MUTED)
    W = 230
    entity(d, 40, 120, 170, 70, "Endpoint OS", "read-only queries")
    process(d, 290, 100, W, 110, "1.0", "Run endpoint\nchecks", "Runner, 12 checks")
    store(d, 290, 290, W, "D1", "Outbox (outbox.db)")
    process(d, 620, 100, W, 110, "2.0", "Validate and\nstore reports", "core.ingest")
    store(d, 620, 290, W, "D2", "Reports, results_current")
    process(d, 950, 100, W, 110, "3.0", "Evaluate fleet", "liveness, 95 % rule")
    process(d, 1280, 100, W, 110, "4.0", "Push roll-up", "platform_link")
    flow(d, [(210, 155), (290, 155)], "output", ldy=-6)
    flow(d, [(405, 210), (405, 290)], "signed report", ldx=8, lanchor="start", ldy=4)
    flow(d, [(520, 307), (560, 307), (560, 170), (620, 170)], "HTTPS POST", lseg=1, ldx=-6, lanchor="end",
         lpos=0.3, ldy=0)
    flow(d, [(735, 210), (735, 290)], "report, observations", ldx=8, lanchor="start", ldy=4)
    flow(d, [(850, 307), (1065, 307), (1065, 210)], "current results, last_seen", lseg=0, ldy=-6)
    flow(d, [(1180, 155), (1280, 155)], "snapshot", ldy=-6)
    process(d, 1280, 470, W, 110, "5.0", "Record evidence", "Engine A")
    store(d, 1280, 650, W, "D3", "Observations")
    process(d, 860, 470, W, 110, "6.0", "Price the risk", "Engine B, model V2")
    store(d, 860, 650, W, "D4", "Calculations")
    store(d, 860, 720, W, "D5", "pricing_v2_params")
    process(d, 440, 470, W, 110, "7.0", "Bind and run\nwarranties", "underwriting, coverage")
    store(d, 440, 650, W, "D6", "Policies, warranties")
    entity(d, 1420, 290, 160, 64, "Proposal form", "entered by underwriter")
    entity(d, 60, 495, 170, 64, "Underwriter")
    flow(d, [(1395, 210), (1395, 470)], "signed roll-up\n(AGENT_FLEET)", ldx=8, lanchor="start", lpos=0.62,
         ldy=0)
    flow(d, [(1500, 354), (1500, 470)], "answers,\ndocuments,\nclaims", ldx=8, lanchor="start", lpos=0.45, ldy=0)
    flow(d, [(1395, 580), (1395, 650)], "observation + strength + locator", ldx=8, lanchor="start", ldy=4)
    flow(d, [(1280, 667), (1180, 667), (1180, 525), (1090, 525)], "best evidence\nper control", lseg=1, ldx=8,
         lanchor="start", lpos=0.5, ldy=0)
    flow(d, [(975, 580), (975, 650)], "calculation + snapshot", ldx=8, lanchor="start", ldy=4)
    flow(d, [(1090, 737), (1120, 737), (1120, 560), (1090, 560)], "parameters", lseg=1, ldx=6, lanchor="start",
         lpos=0.5, ldy=0)
    flow(d, [(860, 680), (760, 680), (760, 525), (670, 525)], "bound\ncalculation", lseg=1, ldx=-6, lanchor="end",
         lpos=0.5, ldy=0)
    flow(d, [(555, 580), (555, 650)], "BOUND, warranty states", ldx=8, lanchor="start", ldy=4)
    flow(d, [(1300, 470), (1300, 440), (600, 440), (600, 470)], "evaluate warranties (bound policy only)",
         lseg=1, lpos=0.6, ldy=-6)
    flow(d, [(230, 527), (440, 527)], "bind, referral approval", ldy=-6)
    flow(d, [(900, 470), (900, 456), (190, 456), (190, 495)], "quote, breakdown, gate", lseg=1, lpos=0.25, ldy=-5)
    flow(d, [(145, 559), (145, 860), (1440, 860), (1440, 580)], "document assessments, outside-in signals",
         lseg=1, lpos=0.5, ldy=-6)
    store(d, 440, 760, 300, "D7", "Audit log (every process writes)")
    d.caption("B16", "Level-1 DFD. Rounded boxes: processes; open boxes: data stores; shadowed squares: entities.")
    return d


FIGURES = [
    ("B15", "dfd_context", "DFD level 0: context", dfd_context),
    ("B16", "dfd_level1", "DFD level 1: evidence to warranty", dfd_level1),
]
