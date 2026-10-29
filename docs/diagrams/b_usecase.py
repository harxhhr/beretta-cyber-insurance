"""Behavioural UML: use case diagrams."""
from svg import D, INK, MUTED, GROUND, WHITE, DATA


def _boundary(d, x, y, w, h, name):
    d.rect(x, y, w, h, fill=GROUND, stroke=INK, rx=6)
    d.text(x + w / 2, y + 22, name, size=13.5, weight="700")


def _assoc(d, a, b):
    d.line([a, b], sw=1.1)


def _dep(d, a, b, label):
    d.line([a, b], end="open", dash="6 4", label=label, lsize=10, ldy=-4)


def usecase_insured():
    d = D(1400, 860, "Use cases: insured", "Use case diagram")
    d.text(20, 32, "Use cases for the insured company: the customer user and its IT administrator", size=17,
           weight="700", anchor="start")
    _boundary(d, 260, 60, 560, 740, "Beretta platform  (role CUSTOMER: read only, own company)")
    _boundary(d, 900, 60, 360, 740, "Endpoint agent  (on each machine)")
    d.actor(120, 300, "Insured user", "CUSTOMER role token")
    d.actor(1340, 260, "IT administrator", "admin rights on\nthe endpoint")
    d.actor(1340, 640, "Agent service", "timer, «system»", top=True)

    cx = 540
    uc = [("Send proposal form\nand documents (offline)", 120), ("View own profile\nand classification", 195),
          ("View questionnaire\nanswers and evidence", 270), ("View documents and\nclaims on record", 345),
          ("View evidence posture\nper control", 420), ("View premium, eligibility\nand savings", 495),
          ("View policy and\nwarranty states", 570), ("View Monitoring tab\n(fleet roll-up, SIMULATED label)", 645),
          ("Ask the underwriter\nto change data (offline)", 720)]
    pos = {}
    for label, y in uc:
        rx = d.usecase(cx, y, label, ry=28)
        pos[label.split("\n")[0]] = (cx, y, rx)
    for k, (x, y, rx) in pos.items():
        _assoc(d, (150, 340), (x - rx, y))
    # include / extend

    ax = 1080
    uca = [("Install and enrol agent\n(token + ca.pem)", 140), ("Pin collector CA", 225),
           ("Run checks locally,\nsend nothing  (once --no-send)", 320),
           ("See what is checked\nand never collected", 405), ("Request a scan now\nafter a fix", 490),
           ("Read transparency log\n(sent.jsonl)", 575), ("Send signed reports\nfull / delta / heartbeat", 680)]
    apos = {}
    for label, y in uca:
        rx = d.usecase(ax, y, label, ry=28, rx=150)
        apos[label.split("\n")[0]] = (ax, y, rx)
    for k in ["Install and enrol agent", "Run checks locally,", "See what is checked", "Request a scan now",
              "Read transparency log"]:
        x, y, rx = apos[k]
        _assoc(d, (1325, 320), (x + rx, y))
    x, y, rx = apos["Send signed reports"]
    _assoc(d, (1325, 660), (x + rx, y))
    _dep(d, (ax, 168), (ax, 197), "")
    d.text(ax + 8, 186, "«include»", size=10, anchor="start", color=MUTED)
    d.line([(ax - 150, 680), (840, 680), (840, 645), (cx + 230, 645)], end="open", dash="6 4", color=DATA,
           label="feeds (via collector)", lseg=0, lsize=10, lcolor=DATA)
    d.caption("B1", "Use case diagram for the insured. The customer role is read-only and sees only its own "
                    "company; the underwriter enters intake. The agent is read-only.")
    return d


def usecase_insurer():
    d = D(1400, 900, "Use cases: insurer", "Use case diagram")
    d.text(20, 32, "Use cases for the insurer: underwriter, administrator and collector operator", size=17,
           weight="700", anchor="start")
    _boundary(d, 220, 60, 640, 800, "Beretta platform")
    _boundary(d, 940, 60, 330, 800, "Collector")
    d.actor(100, 230, "Underwriter", "quote, bind, assess")
    d.actor(100, 620, "Admin", "+ admin")
    d.line([(100, 600), (100, 330)], end="tri")
    d.actor(1340, 420, "Collector operator", "admin token", top=True)

    cx = 420
    uw = [("Assess document field\n(locator required)", 110), ("Enter intake: profile, answers,\ndocuments, claims, signals", 180),
          ("Set policy structure\n(limit, retention, covers)", 250), ("Calculate quote\n(Engine B, model V2)", 330),
          ("Bind policy at a\nstored calculation", 430), ("Review warranty states\nand transition events", 520),
          ("Review audit log", 590)]
    p = {}
    for label, y in uw:
        rx = d.usecase(cx, y, label, ry=27)
        p[label.split("\n")[0]] = (cx, y, rx)
        _assoc(d, (130, 270), (cx - rx, y))
    sub = [("Resolve evidence\nposture (Engine A)", 330), ("Approve referral or\noverride gate", 430),
           ("Initialise warranties\n(all MET, then evaluate)", 500)]
    q = {}
    for label, y in sub:
        rx = d.usecase(720, y, label, ry=27, rx=118)
        q[label.split("\n")[0]] = (720, y, rx)
    _dep(d, (cx + p["Calculate quote"][2], 330), (720 - 118, 330), "«include»")
    d.line([(720 - 118, 430), (cx + p["Bind policy at a"][2], 430)], end="open", dash="6 4", label="«extend»",
           lsize=10, ldy=-4)
    _dep(d, (cx + p["Bind policy at a"][2] - 10, 440), (720 - 118, 497), "«include»")
    adm = [("Edit loadings and\ngate mode (BLOCK / WARN)", 680), ("Edit control weights\nand grace days", 750),
           ("Register collector,\nlink company", 820)]
    for label, y in adm:
        rx = d.usecase(cx, y, label, ry=27)
        _assoc(d, (130, 660), (cx - rx, y))
    d.note(600, 610, 240, 58, ["Admin inherits every underwriter", "use case. Every change is audited."])

    ox = 1105
    op = [("Initialise collector,\nissue admin token", 120), ("Add company\n(declared endpoints)", 200),
          ("Issue enrolment token\n(max uses, expiry)", 280), ("Approve build hash\nand policy hash", 360),
          ("Link to platform,\nlink company", 440), ("Watch fleet dashboard\n(hosts, liveness, controls)", 530),
          ("Retire an agent", 610), ("Push roll-up now", 680), ("Bind (standalone only)", 760)]
    for label, y in op:
        rx = d.usecase(ox, y, label, ry=27, rx=140)
        _assoc(d, (1325, 440), (ox + rx, y))
    d.line([(ox - 140, 440), (860, 440), (860, 820), (cx + 120, 820)], dash="6 4", end="open", color=DATA,
           label="needs", lseg=0, lpos=0.5, lsize=10, lcolor=DATA)
    d.caption("B2", "Use case diagram for the insurer. Hollow triangle: Admin is a specialised Underwriter.")
    return d


FIGURES = [
    ("B1", "usecase_insured", "Use case diagram: insured", usecase_insured),
    ("B2", "usecase_insurer", "Use case diagram: insurer", usecase_insurer),
]
