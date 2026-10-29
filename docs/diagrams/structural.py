"""Structural UML figures: component, deployment, class and ER diagrams."""
from svg import (D, INK, MUTED, RAISED, RULE, DATA, DATA_SOFT, MET, MET_BG, BREACH, WHITE, GROUND)


# ================================================================================================ S1
def component_system():
    d = D(1560, 850, "Beretta system: component diagram", "Component diagram")
    d.text(20, 32, "Beretta: component view of the three subsystems and how they connect", size=17, weight="700",
           anchor="start")

    # ---- Part 2a: endpoint agent
    d.frame(20, 50, 440, 700, "subsystem  Endpoint agent  (kyh-agent/agent)", fill=GROUND)
    d.component(40, 100, 230, 64, "CLI", ["once · status · show-policy", "scan-now · build-info"])
    d.component(40, 194, 230, 64, "Service loop", ["Agent.tick(), every 30 s", "full / delta / heartbeat"])
    d.component(40, 288, 230, 64, "Check runner", ["Runner + REGISTRY", "12 checks × 3 OS"])
    d.component(40, 382, 230, 64, "Outbox", ["Spool (SQLite)", "seq, ack, dead-letter"])
    d.component(40, 476, 230, 64, "Transport", ["HTTPS, pinned ca.pem", "HMAC-SHA256 signature"])
    d.box(290, 194, 150, 64, "Baseline policy", ["policy.json", "sha-256 policy hash"], stereo="artifact", rx=2)
    d.box(290, 288, 150, 64, "Host OS", ["read-only commands,", "files, PowerShell"], stereo="external", rx=2,
          dash="5 3")
    d.box(290, 382, 150, 64, "Transparency log", ["sent.jsonl", "readable by staff"], stereo="artifact", rx=2)
    d.arrow(155, 164, 155, 194, dash="6 4", end="open", label="scan-now request file", ldx=6, lanchor="start",
            ldy=4)
    d.arrow(155, 258, 155, 288, dash="6 4", end="open")
    d.arrow(155, 352, 155, 382, dash="6 4", end="open", label="enqueue report", ldx=6, lanchor="start", ldy=4)
    d.arrow(155, 446, 155, 476, dash="6 4", end="open", label="flush pending", ldx=6, lanchor="start", ldy=4)
    d.arrow(270, 226, 290, 226, dash="6 4", end="open")
    d.arrow(270, 320, 290, 320, dash="6 4", end="open")
    d.arrow(270, 414, 290, 414, dash="6 4", end="open")
    d.note(40, 580, 400, 92, ["Read-only by design. Never collects file contents,",
                              "browsing, keystrokes, e-mail, passwords or clear-text",
                              "user names. Runs as a Windows service, systemd unit",
                              "or launchd daemon. Python standard library only."])

    # ---- Part 2b: collector
    d.frame(500, 50, 460, 700, "subsystem  Collector  (kyh-agent/collector)", fill=GROUND)
    d.component(540, 100, 360, 64, "Ingest", ["core.enroll() · core.ingest()",
                                              "token, HMAC, replay, clock-skew checks"])
    d.component(540, 194, 360, 80, "Evaluation", ["evaluate.evaluate_company()",
                                                  "liveness → host control → fleet roll-up",
                                                  "95 % hosts pass · 90 % coverage"])
    d.component(540, 304, 360, 64, "Warranty state machine", ["evaluate.step()",
                                                              "standalone companies only"])
    d.component(540, 398, 360, 64, "Platform link", ["LinkWorker · sync_company()",
                                                     "signed roll-up on change, 15 min heartbeat"])
    d.component(540, 492, 360, 64, "Dashboard", ["static/index.html, app.js",
                                                 "admin token, strict CSP"])
    d.cylinder(620, 592, 200, 66, "collector.db", "SQLite, WAL")
    d.arrow(720, 164, 720, 194, dash="6 4", end="open", label="results_current", ldx=6, lanchor="start", ldy=4)
    d.arrow(720, 274, 720, 304, dash="6 4", end="open")
    d.line([(900, 234), (935, 234), (935, 430), (900, 430)], end="open", dash="6 4", label="snapshot",
           lseg=1, lpos=0.82, ldx=-4, ldy=0, lanchor="end")
    d.line([(540, 524), (522, 524), (522, 234), (540, 234)], end="open", dash="6 4")
    d.arrow(720, 556, 720, 592, dash="6 4", end="open")
    d.note(540, 676, 400, 60, ["Linked company: no state machine of its own;",
                               "shows the platform's warranty states."])

    # ---- Part 1: platform
    d.frame(1000, 50, 540, 700, "subsystem  Beretta platform  (kyh-cyber-insurance)", fill=GROUND)
    d.component(1020, 100, 235, 64, "Web UI", ["frontend/index.html", "app.js, styles.css"])
    d.component(1020, 194, 235, 64, "HTTP API", ["api.Handler", "role tokens, 1 MB cap"])
    d.component(1020, 300, 235, 70, "Fleet link", ["fleet.ingest_rollup()", "HMAC, seq, ±5 min, mapping"])
    d.component(1020, 470, 235, 64, "Audit", ["audit.log()", "append-only trail"])
    d.component(1285, 100, 235, 64, "Engine B: pricing V2", ["pricing_v2.price()", "perils × lognormal"])
    d.component(1285, 194, 235, 64, "Underwriting", ["bind_policy(), gate()", "refer()"])
    d.component(1285, 300, 235, 70, "Coverage engine", ["coverage.evaluate_policy()",
                                                        "the warranty state machine"])
    d.component(1285, 400, 235, 64, "Engine A: evidence", ["observations.resolve_posture()",
                                                           "best evidence per control"])
    d.cylinder(1200, 600, 180, 66, "kyh.db", "SQLite, WAL")
    d.arrow(1137, 164, 1137, 194, label="fetch /api/*", ldx=6, lanchor="start", ldy=4, dash="6 4", end="open")
    d.line([(1255, 212), (1270, 212), (1270, 132), (1285, 132)], dash="6 4", end="open")
    d.arrow(1255, 236, 1285, 236, dash="6 4", end="open")
    d.arrow(1255, 335, 1285, 335, dash="6 4", end="open")
    d.arrow(1402, 258, 1402, 300, dash="6 4", end="open", label="initialise warranties", ldx=6, lanchor="start",
            ldy=4)
    d.arrow(1402, 370, 1402, 400, dash="6 4", end="open")
    d.line([(1520, 132), (1532, 132), (1532, 432), (1520, 432)], dash="6 4", end="open")
    d.line([(1137, 370), (1137, 440), (1285, 440)], dash="6 4", end="open", label="record AGENT_FLEET",
           lseg=1, ldy=-5)
    d.line([(1402, 464), (1402, 633), (1380, 633)], dash="6 4", end="open")
    d.line([(1137, 534), (1137, 633), (1200, 633)], dash="6 4", end="open")
    d.note(1020, 686, 500, 50, ["The only warranty authority. Monitoring never re-prices a bound",
                                "policy: repricing_performed is always false."])

    # ---- cross-subsystem connectors (keyed to the legend)
    d.line([(270, 508), (480, 508), (480, 132), (540, 132)], end="arrow", sw=1.6, color=DATA)
    d.line([(900, 446), (980, 446), (980, 318), (1020, 318)], end="arrow", sw=1.6, color=DATA)
    d.line([(1020, 356), (990, 356), (990, 520), (900, 520)], end="open", dash="6 4", color=DATA, sw=1.4)
    d.badge(480, 300, 1)
    d.badge(980, 380, 2)
    d.badge(990, 470, 3)
    legend = [(1, "HTTPS POST /api/v1/enroll and /api/v1/report: TLS with a pinned CA, body signed HMAC-SHA256"),
              (2, "POST /api/collector/rollup: one signed, sequenced fleet roll-up per linked company"),
              (3, "200 response: the platform's warranty states, repricing_performed = false")]
    for i, (n, t) in enumerate(legend):
        d.badge(30 + (i % 2) * 760, 772 + (i // 2) * 24, n)
        d.text(46 + (i % 2) * 760, 776 + (i // 2) * 24, t, size=11.5, anchor="start")
    d.caption("S1", "Component diagram. Solid blue: network calls between subsystems; dashed: dependencies "
                    "inside a subsystem.")
    return d


# ================================================================================================ S2
def deployment():
    d = D(1420, 800, "Beretta: deployment diagram", "Deployment diagram")
    d.text(20, 32, "Deployment: where each part runs and how the nodes talk", size=17, weight="700", anchor="start")

    # insured endpoint
    d.node(20, 60, 400, 500, "Insured endpoint  × N", stereo="device")
    d.text(30, 125, "Windows 10/11 or Server · Linux · macOS", size=11, anchor="start", color=MUTED)
    d.rect(40, 140, 360, 400, fill=RAISED, stroke=INK)
    d.text(52, 160, "«execution environment»", size=10.5, anchor="start", color=MUTED)
    d.text(52, 176, "Python 3.9+ service (KYH Agent)", size=12.5, anchor="start", weight="600")
    d.text(52, 192, "Windows service · systemd unit · launchd daemon", size=10.5, anchor="start", color=MUTED)
    d.artifact(60, 210, 320, 54, "kyh_agent/", "the agent package; build hash checked by collector")
    d.artifact(60, 274, 320, 54, "policy.json", "baseline: 12 checks, intervals, thresholds")
    d.artifact(60, 338, 320, 54, "agent.json", "agent_id, agent_secret (after enrolment)")
    d.artifact(60, 402, 320, 54, "outbox.db · state.json", "spooled signed reports, fingerprints")
    d.artifact(60, 466, 320, 54, "ca.pem · sent.jsonl", "pinned collector CA; local copy of what is sent")

    # collector server
    d.node(520, 60, 400, 500, "Insurer monitoring server", stereo="device")
    d.text(530, 125, "listens on :8443", size=11, anchor="start", color=MUTED)
    d.rect(540, 140, 360, 400, fill=RAISED, stroke=INK)
    d.text(552, 160, "«execution environment»", size=10.5, anchor="start", color=MUTED)
    d.text(552, 176, "Python 3.9+  python -m kyh_collector serve", size=12.5, anchor="start", weight="600")
    d.artifact(560, 210, 320, 54, "kyh_collector/", "HTTP server, evaluation, link worker")
    d.artifact(560, 274, 320, 54, "collector.db", "SQLite: agents, reports, results")
    d.artifact(560, 338, 320, 54, "tls/server.pem · server.key", "made by gen-cert; ca.pem goes to endpoints")
    d.artifact(560, 402, 320, 54, "platform_link.json", "platform URL, collector_id, shared secret")
    d.artifact(560, 466, 320, 54, "static/", "dashboard: index.html, app.js, style.css")

    # platform server
    d.node(1010, 60, 390, 500, "Beretta platform server", stereo="device")
    d.text(1020, 125, "listens on :8000", size=11, anchor="start", color=MUTED)
    d.rect(1030, 140, 350, 400, fill=RAISED, stroke=INK)
    d.text(1042, 160, "«execution environment»", size=10.5, anchor="start", color=MUTED)
    d.text(1042, 176, "Python 3.9+  server.py", size=12.5, anchor="start", weight="600")
    d.artifact(1050, 210, 310, 54, "app/", "api, engines A and B, coverage, fleet")
    d.artifact(1050, 274, 310, 54, "kyh.db", "SQLite: policies, observations, warranties")
    d.artifact(1050, 338, 310, 54, "pricing_v2_params.json", "every V2 number with source and tag")
    d.artifact(1050, 402, 310, 54, "secrets.json", "role tokens (never committed)")
    d.artifact(1050, 466, 310, 54, "frontend/", "index.html, app.js, styles.css")

    # browsers
    d.node(520, 620, 400, 100, "Operator browser", stereo="device")
    d.text(530, 700, "collector dashboard, admin token", size=11, anchor="start", color=MUTED)
    d.node(1010, 620, 390, 100, "User browser", stereo="device")
    d.text(1020, 700, "insured, underwriter or admin role", size=11, anchor="start", color=MUTED)

    # communication paths
    d.line([(420, 300), (520, 300)], sw=1.6, color=DATA)
    d.lines(476, 266, ["«HTTPS»", "pinned CA"], size=10, color=DATA)
    d.lines(476, 318, ["HMAC-SHA256", "seq, clock"], size=10, color=DATA)
    d.line([(920, 300), (1010, 300)], sw=1.6, color=DATA)
    d.lines(971, 266, ["«HTTP(S)»", "roll-up"], size=10, color=DATA)
    d.lines(971, 318, ["HMAC-SHA256", "seq, ±5 min"], size=10, color=DATA)
    d.line([(720, 560), (720, 620)], sw=1.4)
    d.text(728, 595, "«HTTPS» :8443", size=10.5, anchor="start")
    d.line([(1205, 560), (1205, 620)], sw=1.4)
    d.text(1213, 595, "«HTTP» :8000, X-Auth-Token", size=10.5, anchor="start")
    d.note(20, 600, 440, 96, ["Demo set-up (run_linked_demo.py): all three nodes on one",
                               "laptop at 127.0.0.1, with four SIMULATED endpoints.",
                               "With --vm-ip, a real Windows VM on a host-only network",
                               "(192.168.56.x) runs the agent and reports to the",
                               "laptop's collector over HTTPS."])
    d.caption("S2", "Deployment diagram. Multiplicity × N: one agent per insured machine.")
    return d


# ================================================================================================ S3
def class_agent():
    d = D(1500, 960, "Endpoint agent: class diagram", "Class diagram")
    d.text(20, 32, "Endpoint agent (kyh_agent): class diagram", size=17, weight="700", anchor="start")
    h_agent = d.classbox(520, 60, 400, "Agent",
                         ["- cfg : Config", "- policy : Policy", "- runner : Runner", "- spool : Spool",
                          "- transport : Transport", "- state : dict  (fingerprints, next_due)",
                          "- backoff : int  (30 s … 900 s)"],
                         ["+ tick() : dict", "+ scan(check_ids, force_full) : dict", "+ heartbeat_if_due() : bool",
                          "+ flush() : dict", "+ enqueue(kind, results) : int",
                          "+ envelope(kind, results, seq) : dict", "+ take_scan_request() : list",
                          "+ run_forever(tick_seconds)"])
    d.classbox(60, 70, 300, "Config", ["dict subclass, agent.json", "+ agent_id, agent_secret", "+ server_url"],
               ["+ enrolled : bool", "+ heartbeat_seconds() : int", "+ full_snapshot_seconds() : int",
                "+ load(path) / save(cfg)"])
    d.classbox(60, 330, 300, "Policy", ["+ id, version : str", "+ hash : str  (sha-256)", "+ checks : list",
                                        "+ by_id : dict"],
               ["+ interval_seconds(check_id) : int", "+ timeout(check_id) : float", "+ validate(doc) : Policy"])
    d.classbox(1080, 70, 360, "Spool", ["- path : str  (outbox.db)", "- max_rows : int = 10000"],
               ["+ next_seq() : int", "+ put(seq, kind, created_at, body)", "+ pending(limit) : list",
                "+ ack(seq)", "+ dead_letter(seq, http_status, reason)", "+ depth() : int"])
    d.classbox(1080, 330, 360, "Transport", ["- server_url : str", "- ca_file : str  (pinned CA)"],
               ["+ post(path, body, headers) : (int, dict)"])
    h_run = d.classbox(520, 520, 400, "Runner", ["- policy : Policy", "- platform : linux | windows | darwin",
                                         "- registry : dict"],
               ["+ run(check_ids) : list[CheckResult]", "+ run_one(check_id) : CheckResult",
                "- _guarded(fn, params, ctx, timeout) : Outcome"])
    d.classbox(60, 600, 300, "Context", ["privacy helper passed to checks"], ["+ hash_id(name) : str"])
    h_cr = d.classbox(1080, 500, 360, "CheckResult", ["+ check_id, control, tier : str", "+ status : Status",
                                               "+ assurance : Assurance", "+ evidence : dict", "+ method : str",
                                               "+ observed_at : str", "+ duration_ms : int"],
               ["+ to_dict() : dict"], stereo="dataclass")
    d.classbox(1080, 740, 360, "Outcome", ["+ status, summary, method", "+ assurance, evidence"],
               stereo="dataclass")
    d.classbox(520, 740, 400, "REGISTRY", ["patch · edr · backup · mfa · disk · firewall",
                                           "exposed_services · remote_access · local_admins",
                                           "os_support · log_retention · time_sync"],
               ["check(params, ctx) : Outcome  per OS"], stereo="module checks")
    d.classbox(60, 760, 140, "Status", ["PASS", "FAIL", "NOT_APPLICABLE", "NOT_SUPPORTED", "ERROR"],
               stereo="enumeration", size=10)
    d.classbox(220, 760, 140, "Assurance", ["OPERATING", "RUNNING", "PRESENT", "ABSENT"],
               stereo="enumeration", size=10)

    # relationships
    bot = 60 + h_agent
    d.line([(520, 130), (360, 130)], end="open", label="reads", ldy=-6)
    d.line([(520, 380), (360, 380)], end="open", label="1  policy", ldy=-6)
    d.line([(920, 130), (1080, 130)], start="diamond", label="1  outbox", ldy=-6)
    d.line([(920, 380), (1080, 380)], end="open", label="0..1", ldy=-6)
    d.line([(720, bot), (720, 520)], start="diamond", label="1", ldx=10, lanchor="start", ldy=4)
    d.line([(560, 520), (560, 470), (360, 470), (360, 470)], end="open", label="uses thresholds", lseg=1,
           ldy=-6)
    d.line([(920, 560), (1080, 560)], dash="6 4", end="open", label="«create»", ldy=-6)
    d.line([(720, 520 + h_run), (720, 740)], end="open", label="looks up", ldx=10, lanchor="start", ldy=4)
    d.line([(920, 790), (1080, 790)], dash="6 4", end="open", label="returns", ldy=-6)
    d.line([(520, 640), (360, 640)], dash="6 4", end="open", label="«create»", ldy=-6)
    d.line([(1260, 500 + h_cr), (1260, 740)], dash="6 4", end="open", label="wraps", ldx=8, lanchor="start", ldy=4)
    d.note(60, 230, 300, 72, ["MFA is listed but always NOT_SUPPORTED:", "it cannot be observed from an",
                              "endpoint. Honest reporting, not a FAIL."])
    d.caption("S3", "Class diagram of the agent package. Filled diamond: composition; dashed arrow: dependency.")
    return d


# ================================================================================================ S4
def class_collector():
    d = D(1500, 860, "Collector: class diagram", "Class diagram")
    d.text(20, 32, "Collector (kyh_collector): classes and modules", size=17, weight="700", anchor="start")
    hH = d.classbox(40, 70, 360, "Handler", ["BaseHTTPRequestHandler"],
               ["+ do_POST()  /api/v1/enroll, /api/v1/report", "+ do_GET()  overview, companies/{id},",
                "                agents/{id}, static files", "- _admin(conn) : bool"])
    d.classbox(560, 70, 360, "App", ["+ data_dir : str", "+ settings : dict", "+ lock : threading.Lock",
                                     "+ link : dict | None", "+ clock : () → datetime"],
               ["+ conn() : Connection", "+ rate_limited(key) : bool", "+ start_link_worker()"])
    hL = d.classbox(1080, 70, 380, "LinkWorker", ["threading.Thread", "- interval : push_interval_seconds"],
               ["+ run()  evaluate + push every 30 s", "+ stop()"])
    hC = d.classbox(40, 330, 380, "core", ["STRENGTH_OBSERVED, _SIMULATED,", "_UNTRUSTED_BUILD, _UNTRUSTED_POLICY"],
               ["+ enroll(conn, now, body) : dict", "+ ingest(conn, now, agent_id, sig, raw, s)",
                "+ add_company(…) · issue_enrollment_token(…)", "+ bind_policy(…) · approve(…)",
                "+ retire_agent(…) · check_admin(…)"], stereo="module")
    hE = d.classbox(560, 330, 380, "evaluate", ["ONLINE · UNVERIFIED · SILENT", "SILENT_PASS · NOT_OBSERVABLE"],
               ["+ liveness(agent, now, s) : dict", "+ host_control(rows, live, demo, s)",
                "+ company_control(control, hosts, s)", "+ coverage(company, lives, s, …)",
                "+ step(w, observed, reason, now, s)", "+ evaluate_company(conn, id, now, s)",
                "+ host_detail(conn, agent_id)"], stereo="module")
    hP = d.classbox(1080, 330, 380, "platform_link", ["SCHEMA_ID = kyh-fleet-rollup/1"],
               ["+ link_company(conn, now, id, platform_id)", "+ build_controls(snapshot, s)",
                "+ change_hash(controls, fleet, coverage)", "+ sign(secret_hex, body) : str",
                "+ sync_company(app, id, link, force)"], stereo="module")
    d.classbox(40, 640, 380, "ApiError", ["+ status : int", "+ code : str", "+ message : str"],
               stereo="exception")
    d.classbox(560, 640, 380, "settings", ["DEFAULTS: 6 h / 72 h liveness,", "95 % pass, 90 % coverage,",
                                           "grace days, platform_control_map"],
               ["+ load(data_dir) : dict"], stereo="module")
    d.classbox(1080, 640, 380, "db", ["SCHEMA: 15 tables"],
               ["+ connect(path) : Connection", "+ audit(conn, at, actor, action, …)"], stereo="module")
    # relations
    d.line([(400, 130), (560, 130)], end="open", label="server.app", ldy=-6)
    d.line([(920, 130), (1080, 130)], start="diamond", label="0..1", ldy=-6)
    d.line([(220, 70 + hH), (220, 330)], dash="6 4", end="open", label="«use»", ldx=8, lanchor="start", ldy=4)
    d.line([(330, 70 + hH), (330, 270), (660, 270), (660, 330)], dash="6 4", end="open", label="«use»", lseg=1)
    d.line([(1270, 70 + hL), (1270, 330)], dash="6 4", end="open", label="«use»", ldx=8, lanchor="start", ldy=4)
    d.line([(1080, 420), (940, 420)], dash="6 4", end="open", label="evaluate_company", ldy=-6)
    d.line([(160, 330 + hC), (160, 640)], dash="6 4", end="open", label="«raise»", ldx=8, lanchor="start", ldy=4)
    d.line([(660, 330 + hE), (660, 640)], dash="6 4", end="open", label="reads s", ldx=8, lanchor="start", ldy=4)
    d.line([(1370, 330 + hP), (1370, 640)], dash="6 4", end="open", label="«use»", ldx=8, lanchor="start", ldy=4)
    d.line([(330, 330 + hC), (330, 600), (1200, 600), (1200, 640)], dash="6 4", end="open",
           label="every module writes the audit log through db.audit()", lseg=1, lpos=0.72)
    d.caption("S4", "Class diagram of the collector. «module» boxes are Python modules of functions; the only "
                    "classes are Handler, App, LinkWorker and ApiError.")
    return d


# ================================================================================================ S5
def class_platform():
    d = D(1500, 940, "Platform: module and class diagram", "Class diagram")
    d.text(20, 32, "Beretta platform (kyh-cyber-insurance/app): modules and their dependencies", size=17,
           weight="700", anchor="start")
    hA = d.classbox(560, 60, 380, "api.Handler", ["BaseHTTPRequestHandler", "ROUTES: 40 method/path pairs"],
               ["+ _route(method, path)", "+ _user(conn, perm) : user", "+ h_quote · h_bind · h_collector_rollup",
                "+ h_questionnaire_submit · h_posture …"])
    d.classbox(40, 60, 360, "security", ["ROLE_PERMS: CUSTOMER read (own company);", "UNDERWRITER + staff, intake, quote,",
                                         "bind, assess; ADMIN + admin"],
               ["+ authenticate(conn, token) : user", "+ require(user, perm)"], stereo="module")
    hF = d.classbox(1100, 60, 360, "fleet", ["SCHEMA_ID = kyh-fleet-rollup/1", "MAX_SKEW = 5 min · REFRESH_HOURS = 6"],
               ["+ register_collector(…) · link_company(…)", "+ authenticate(conn, id, signature, raw)",
                "+ ingest_rollup(conn, collector, raw)", "+ latest_snapshot(conn, company_id)"],
               stereo="module")
    hO = d.classbox(40, 330, 380, "observations  (Engine A)", ["EVIDENCE_STRENGTHS ranked:",
                                                          "DECLARED < DOCUMENTED < TESTED", "< TECHNICALLY_OBSERVED"],
               ["+ record_observation(conn, company, control, …)", "+ resolve_posture(conn, company_id)",
                "+ record_signal(…) · register_document(…)", "+ assess_document_field(…)"], stereo="module")
    hP = d.classbox(560, 330, 380, "pricing_v2  (Engine B)", ["UNDERWRITING_MODEL_V2",
                                                         "PERILS: RANSOMWARE, BEC, FTF, ...", ],
               ["+ classify(inputs, prm)", "+ evidence_status(entry, docs, prm)", "+ control_effects(statuses, prm)",
                "+ expected_payout(mu, sigma, d, f, L, prm)", "+ price(inputs, prm) · what_if(…)",
                "+ gate(statuses, mode, prm) · refer(…)", "+ calculate_premium(conn, policy_id)",
                "+ reproduce(snapshot)"], stereo="module")
    hC = d.classbox(1100, 330, 360, "coverage", ["STATES: MET, IN_GRACE,", "BREACHED, REMEDIATED"],
               ["+ initialize_warranties(conn, policy_id)", "+ evaluate_policy(conn, policy, company)",
                "+ expire_grace_periods(conn)", "+ coverage_consequence(w)"], stereo="module")
    d.classbox(1100, 660, 360, "underwriting", ["V1 model, frozen so stored quotes", "reproduce"],
               ["+ bind_policy(conn, policy, calc, referral_ok)", "+ calculate_premium(…)  V1 only",
                "+ reproduce_v1(snapshot, result)"], stereo="module")
    d.box(560, 680, 380, 64, "pricing_v2_params.json", ["value · unit · source · locator · tag [L] [D] [A]"],
          stereo="artifact", rx=2)
    d.classbox(40, 660, 380, "catalogue", ["CONTROLS: 15 priced + CTRL-AGENT-COVERAGE", "SOURCE_TYPES",
                                           "EVIDENCE_STRENGTHS"], stereo="module")
    d.classbox(560, 790, 180, "audit", [], ["+ log(conn, actor, …)"], stereo="module")
    d.classbox(760, 790, 180, "database", [], ["+ connect() · init()", "+ new_id() · now_iso()"], stereo="module")
    # relations
    aB, fB, oB, pB, cB = 60 + hA, 60 + hF, 330 + hO, 330 + hP, 330 + hC
    d.line([(560, 110), (400, 110)], dash="6 4", end="open", label="«use»", ldy=-6)
    d.line([(940, 110), (1100, 110)], dash="6 4", end="open", label="rollup", ldy=-6)
    d.line([(600, aB), (600, 275), (230, 275), (230, 330)], dash="6 4", end="open",
           label="posture, questionnaire", lseg=1)
    d.line([(750, aB), (750, 330)], dash="6 4", end="open", label="quote", ldx=8, lanchor="start", ldy=4, lpos=0.3)
    d.line([(900, aB), (900, 285), (1070, 285), (1070, 710), (1100, 710)], dash="6 4", end="open",
           label="bind", lseg=2, lpos=0.95, ldx=-6, lanchor="end")
    d.line([(1130, fB), (1130, 305), (400, 305), (400, 330)], dash="6 4", end="open",
           label="record_observation", lseg=1, lpos=0.4, ldy=14)
    d.line([(1280, fB), (1280, 330)], dash="6 4", end="open", label="evaluate_policy", ldx=8, lanchor="start",
           ldy=4)
    d.line([(560, 420), (420, 420)], dash="6 4", end="open", label="resolve", ldy=-6)
    d.line([(1150, cB), (1150, 630), (370, 630), (370, oB)], dash="6 4", end="open", label="resolve_posture",
           lseg=1, lpos=0.5)
    d.line([(1280, 660), (1280, cB)], dash="6 4", end="open", label="initialize_warranties", ldx=8,
           lanchor="start", ldy=4)
    d.line([(750, pB), (750, 680)], dash="6 4", end="open", label="load_params", ldx=8, lanchor="start", ldy=-14)
    d.line([(230, oB), (230, 660)], dash="6 4", end="open", label="reads controls", ldx=8, lanchor="start",
           ldy=4, lpos=0.3)
    d.note(40, 800, 380, 64, ["Monitoring never re-prices: fleet calls", "coverage only, never pricing_v2.",
                                "Every module logs through audit."])
    d.caption("S5", "Module diagram of the platform. Every number used by Engine B comes from the parameter file.")
    return d


# ================================================================================================ S6
def er_platform():
    d = D(1720, 1110, "Platform database: ER diagram", "ER diagram")
    d.text(20, 32, "Platform database (kyh.db): entities and relationships", size=17, weight="700", anchor="start")

    def ent(key, x, y, cols, w=250):
        d.entity(x, y, w, key, cols)

    ent("users", 20, 60, [("user_id", "TEXT", "PK"), ("name", "TEXT", ""), ("role", "TEXT", ""),
                          ("token", "TEXT", ""), ("company_id", "TEXT", "FK")])
    ent("documents", 20, 220, [("document_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"),
                               ("document_type", "TEXT", ""), ("category", "TEXT", ""),
                               ("assessment_status", "TEXT", ""), ("default_strength", "TEXT", "")])
    ent("claims", 20, 400, [("claim_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"), ("incident_date", "TEXT", ""),
                            ("incident_type", "TEXT", ""), ("loss_amount_inr", "REAL", ""),
                            ("material", "INT", "")])
    ent("outside_in_signals", 20, 580, [("signal_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"),
                                        ("signal_type", "TEXT", ""), ("severity", "TEXT", ""),
                                        ("related_control_id", "TEXT", "FK")])
    ent("audit_events", 20, 780, [("event_id", "TEXT", "PK"), ("timestamp", "TEXT", ""), ("actor", "TEXT", ""),
                                  ("event_type", "TEXT", ""), ("entity_type", "TEXT", ""),
                                  ("entity_id", "TEXT", ""), ("old_value", "JSON", ""), ("new_value", "JSON", "")])
    ent("companies", 330, 330, [("company_id", "TEXT", "PK"), ("name", "TEXT", ""), ("sector", "TEXT", ""),
                                ("nic_code", "TEXT", ""), ("annual_revenue_inr", "REAL", ""),
                                ("employee_count", "INT", ""), ("years_in_operation", "REAL", ""),
                                ("regulated_rbi_sebi", "INT", "")])
    ent("agents", 330, 600, [("agent_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"), ("token", "TEXT", ""),
                             ("hostname", "TEXT", ""), ("last_seen", "TEXT", "")])
    ent("agent_reports", 330, 790, [("report_id", "TEXT", "PK"), ("agent_id", "TEXT", "FK"),
                                    ("received_at", "TEXT", ""), ("raw_json", "TEXT", "")])
    ent("observations", 640, 60, [("observation_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"),
                                  ("control_id", "TEXT", "FK"), ("value", "true|false|partial", ""),
                                  ("dims", "JSON", ""), ("source_type", "TEXT", ""), ("source_id", "TEXT", ""),
                                  ("evidence_strength", "TEXT", ""), ("observed_at", "TEXT", ""),
                                  ("source_locator", "TEXT", ""), ("status", "TEXT", "")])
    ent("policies", 640, 380, [("policy_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"),
                               ("status", "DRAFT|QUOTED|BOUND", ""), ("bound_at", "TEXT", ""),
                               ("bound_calculation_id", "TEXT", "FK"), ("bound_premium", "REAL", ""),
                               ("limit_total_inr", "REAL", ""), ("retention_inr", "REAL", "")])
    ent("calculations", 640, 640, [("calculation_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"),
                                   ("policy_id", "TEXT", "FK"), ("model_version", "TEXT", ""),
                                   ("input_snapshot", "JSON", ""), ("result_json", "JSON", ""),
                                   ("technical_premium", "REAL", ""), ("eligibility", "TEXT", "")])
    ent("policy_coverages", 640, 880, [("id", "INT", "PK"), ("policy_id", "TEXT", "FK"), ("coverage_id", "TEXT", ""),
                                       ("limit_inr", "REAL", ""), ("deductible_inr", "REAL", ""),
                                       ("severity_fraction", "REAL", ""), ("enabled", "INT", "")])
    ent("controls", 950, 60, [("control_id", "TEXT", "PK"), ("name", "TEXT", ""), ("tier", "INT", ""),
                              ("is_warranty", "INT", ""), ("monitoring_only", "INT", ""),
                              ("grace_period_days", "INT", ""), ("coverage_effect", "TEXT", "")])
    ent("warranties", 950, 380, [("warranty_id", "TEXT", "PK"), ("policy_id", "TEXT", "FK"),
                                 ("control_id", "TEXT", "FK"), ("state", "MET|IN_GRACE|…", ""),
                                 ("breach_detected_at", "TEXT", ""), ("grace_expires_at", "TEXT", ""),
                                 ("grace_period_days", "INT", "")])
    ent("warranty_events", 950, 640, [("event_id", "TEXT", "PK"), ("warranty_id", "TEXT", "FK"),
                                      ("from_state", "TEXT", ""), ("to_state", "TEXT", ""), ("at", "TEXT", ""),
                                      ("trigger_observation_id", "TEXT", "FK")])
    ent("collectors", 1260, 60, [("collector_id", "TEXT", "PK"), ("name", "TEXT", ""), ("secret", "TEXT", ""),
                                 ("dashboard_url", "TEXT", ""), ("last_seq", "INT", ""), ("last_seen", "TEXT", "")])
    ent("collector_links", 1260, 260, [("collector_id", "TEXT", "PK FK"), ("company_id", "TEXT", "PK FK"),
                                       ("collector_company_id", "TEXT", "")])
    ent("collector_rollups", 1260, 420, [("rollup_id", "TEXT", "PK"), ("collector_id", "TEXT", "FK"),
                                         ("company_id", "TEXT", "FK"), ("seq", "INT", ""),
                                         ("raw_json", "TEXT", "")])
    ent("fleet_snapshots", 1260, 620, [("company_id", "TEXT", "PK FK"), ("collector_id", "TEXT", "FK"),
                                       ("rollup_id", "TEXT", "FK"), ("snapshot_json", "JSON", "")])
    # reference tables, unlinked
    d.frame(1560, 60, 140, 300, "reference", fill="none", dash="5 3")
    for i, (n1, n2, c) in enumerate([("sectors", "", "sector PK"), ("config", "", "key PK"),
                                     ("coverage_head", "_defaults", "coverage_id PK")]):
        d.rect(1576, 100 + i * 80, 108, 56, fill=WHITE, stroke=INK, rx=4)
        d.text(1630, 120 + i * 80, n1, size=11, weight="600")
        if n2:
            d.text(1630, 133 + i * 80, n2, size=11, weight="600")
        d.text(1630, 148 + i * 80, c, size=9.5, color=MUTED, mono=True)

    def rel(pts, start="one", end="many", **kw):
        d.line(pts, start=start, end=end, lsize=10, **kw)

    # companies → left column
    rel([(330, 345), (310, 345), (310, 120), (270, 120)])
    rel([(330, 365), (295, 365), (295, 290), (270, 290)])
    rel([(330, 460), (270, 460)])
    rel([(330, 490), (300, 490), (300, 640), (270, 640)])
    # companies → agents → reports ; companies → observations, policies
    rel([(455, 503), (455, 600)])
    rel([(455, 720), (455, 790)])
    rel([(455, 330), (455, 180), (640, 180)])
    rel([(580, 430), (640, 430)])
    # companies → collector side, along the corridor between rows
    rel([(580, 345), (1235, 345), (1235, 300), (1260, 300)], label="company_id", lseg=0, lpos=0.62)
    rel([(580, 362), (1222, 362), (1222, 660), (1260, 660)], end="one")
    # observations ↔ controls ; controls → warranties
    rel([(950, 110), (890, 110)])
    rel([(1075, 215), (1075, 380)])
    # policies → warranties, calculations, coverages
    rel([(890, 430), (950, 430)])
    rel([(700, 553), (700, 640)], label="policy_id", ldx=6, lanchor="start", ldy=4)
    d.line([(800, 553), (800, 640)], end="one", dash="6 4", label="bound_calculation_id", ldx=6, lanchor="start",
           ldy=4, lsize=10)
    rel([(640, 520), (615, 520), (615, 950), (640, 950)])
    # warranties → events ; observations → events (trigger, optional)
    rel([(1075, 535), (1075, 640)])
    d.line([(890, 250), (920, 250), (920, 760), (950, 760)], start="one", end="zmany", dash="6 4",
           label="trigger", lseg=1, lpos=0.62, ldy=0, lsize=10)
    # collectors
    rel([(1385, 198), (1385, 260)])
    rel([(1510, 130), (1530, 130), (1530, 480), (1510, 480)])
    d.line([(1385, 540), (1385, 620)], start="one", end="one", label="latest rollup_id", ldx=8, lanchor="start",
           ldy=4, lsize=10)
    d.note(1260, 790, 440, 102, ["Append-only: observations, agent_reports, collector_rollups,",
                                 "warranty_events and audit_events are never updated;",
                                 "a correction is a new row.",
                                 "Not drawn, to keep the figure readable:",
                                 "calculations.company_id, collector_rollups.company_id → companies;",
                                 "outside_in_signals.related_control_id → controls (0..1)."])
    d.caption("S6", "ER diagram of the platform database (crow's foot). Bars: exactly one; crow's foot: many; "
                    "dashed: optional (0..1).")
    return d


# ================================================================================================ S7
def er_collector():
    d = D(1500, 900, "Collector database: ER diagram", "ER diagram")
    d.text(20, 32, "Collector database (collector.db): entities and relationships", size=17, weight="700",
           anchor="start")
    E = {}

    def ent(key, x, y, cols, w=260):
        h = d.entity(x, y, w, key, cols)
        E[key] = (x, y, w, h)
        return h

    ent("enrollment_tokens", 20, 60, [("token_hash", "TEXT", "PK"), ("company_id", "TEXT", "FK"),
                                      ("expires_at", "TEXT", ""), ("max_uses", "INT", ""), ("uses", "INT", "")])
    ent("companies", 20, 300, [("id", "TEXT", "PK"), ("name", "TEXT", ""), ("sector", "TEXT", ""),
                               ("declared_endpoints", "INT", ""), ("demo_mode", "INT", "")])
    ent("policies", 20, 520, [("company_id", "TEXT", "PK FK"), ("status", "TEXT", ""), ("model_id", "TEXT", ""),
                              ("bound_premium_inr", "INT", ""), ("bound_at", "TEXT", "")])
    ent("platform_state", 20, 700, [("company_id", "TEXT", "PK FK"), ("last_push_at", "TEXT", ""),
                                    ("last_ok", "INT", ""), ("last_hash", "TEXT", ""), ("last_seq", "INT", ""),
                                    ("response_json", "JSON", "")])
    ent("agents", 380, 60, [("agent_id", "TEXT", "PK"), ("company_id", "TEXT", "FK"), ("hostname", "TEXT", ""),
                            ("platform", "TEXT", ""), ("secret", "TEXT", ""), ("last_seq", "INT", ""),
                            ("last_seen", "TEXT", ""), ("build_hash", "TEXT", ""), ("build_trusted", "INT", ""),
                            ("policy_hash", "TEXT", ""), ("policy_trusted", "INT", ""), ("retired", "INT", "")])
    ent("warranties", 380, 520, [("company_id", "TEXT", "PK FK"), ("control", "TEXT", "PK"),
                                 ("state", "MET|IN_GRACE|…", ""), ("since", "TEXT", ""),
                                 ("grace_expires_at", "TEXT", ""), ("remediated_at", "TEXT", "")])
    ent("warranty_events", 380, 720, [("id", "INT", "PK"), ("company_id", "TEXT", "FK"), ("control", "TEXT", ""),
                                      ("from_state", "TEXT", ""), ("to_state", "TEXT", ""), ("reason", "TEXT", "")])
    ent("reports", 740, 60, [("id", "INT", "PK"), ("agent_id", "TEXT", "FK"), ("seq", "INT", ""),
                             ("kind", "full|delta|heartbeat", ""), ("body_sha256", "TEXT", ""),
                             ("simulated", "INT", ""), ("evidence_strength", "TEXT", "")])
    ent("observations", 740, 300, [("id", "INT", "PK"), ("report_id", "INT", "FK"), ("agent_id", "TEXT", "FK"),
                                   ("company_id", "TEXT", "FK"), ("check_id", "TEXT", ""), ("control", "TEXT", ""),
                                   ("status", "TEXT", ""), ("assurance", "TEXT", ""),
                                   ("evidence_strength", "TEXT", ""), ("observed_at", "TEXT", "")])
    ent("results_current", 740, 590, [("agent_id", "TEXT", "PK FK"), ("check_id", "TEXT", "PK"),
                                      ("control", "TEXT", ""), ("status", "TEXT", ""), ("observed_at", "TEXT", ""),
                                      ("report_id", "INT", "FK")])
    ent("approved_builds", 1100, 60, [("hash", "TEXT", "PK"), ("label", "TEXT", ""), ("added_at", "TEXT", "")])
    ent("approved_policies", 1100, 200, [("hash", "TEXT", "PK"), ("label", "TEXT", ""), ("added_at", "TEXT", "")])
    ent("admin_tokens", 1100, 340, [("token_hash", "TEXT", "PK"), ("created_at", "TEXT", "")])
    ent("audit_log", 1100, 450, [("id", "INT", "PK"), ("at", "TEXT", ""), ("actor", "TEXT", ""),
                                 ("action", "TEXT", ""), ("entity", "TEXT", ""), ("detail", "TEXT", "")])
    ent("platform_meta", 1100, 640, [("k", "TEXT", "PK"), ("v", "TEXT", "")])

    def rel(pts, start="one", end="many", **kw):
        d.line(pts, start=start, end=end, lsize=10, **kw)

    rel([(150, 300), (150, 60 + 120)])  # companies → tokens (draw upward: start at companies)
    rel([(280, 330), (330, 330), (330, 100), (380, 100)])                       # agents
    rel([(150, 300 + 120), (150, 520)], end="one")                              # policies 1:0..1
    d.line([(150, 520 + 120), (150, 640)], color=WHITE)
    rel([(280, 400), (310, 400), (310, 740), (280, 740)], end="one")            # platform_state
    rel([(280, 370), (350, 370), (350, 560), (380, 560)])                      # warranties
    rel([(510, 520 + 136), (510, 720)], label="company_id", ldx=8, lanchor="start", ldy=4)  # events (logical)
    rel([(640, 100), (740, 100)])                                               # reports
    rel([(870, 60 + 148), (870, 300)])                                          # observations by report
    rel([(640, 140), (700, 140), (700, 330), (740, 330)])                       # observations by agent
    rel([(640, 180), (680, 180), (680, 630), (740, 630)])                       # results_current
    rel([(1000, 120), (1020, 120), (1020, 680), (1000, 680)], label="report_id", lseg=1, ldx=6, lanchor="start")
    d.line([(1100, 90), (1060, 90), (1060, 40), (600, 40), (600, 60)], dash="6 4", label="build_hash (logical)",
           lseg=1, lsize=10, lpos=0.4)
    d.line([(1100, 230), (1050, 230), (1050, 262), (640, 262)], dash="6 4",
           label="policy_hash (logical)", lseg=2, lsize=10, lpos=0.3)
    d.note(1100, 740, 380, 106, ["evidence_strength on each report decides if its",
                                 "results count: TECHNICALLY_OBSERVED counts;",
                                 "SIMULATED counts only for a demo company;",
                                 "UNTRUSTED_BUILD and UNTRUSTED_POLICY never count.",
                                 "Warranties here are used only for standalone companies."])
    d.caption("S7", "ER diagram of the collector database. Dashed: hash matched against the approval tables, "
                    "not a foreign key.")
    return d


FIGURES = [
    ("S1", "component_system", "Component diagram: the whole system", component_system),
    ("S2", "deployment", "Deployment diagram", deployment),
    ("S3", "class_agent", "Class diagram: endpoint agent", class_agent),
    ("S4", "class_collector", "Class diagram: collector", class_collector),
    ("S5", "class_platform", "Module diagram: platform", class_platform),
    ("S6", "er_platform", "ER diagram: platform database", er_platform),
    ("S7", "er_collector", "ER diagram: collector database", er_collector),
]
