"""Behavioural UML: sequence diagrams."""
from svg import D, INK, MUTED, WHITE, DATA, GROUND


class Seq:
    """Running-y helper: lifelines by key, messages placed top to bottom."""

    def __init__(self, d, lines, top=60, bottom=None):
        self.d, self.x, self.y, self.top, self.spec = d, {}, top + 110, top, lines
        self.at = len(d.out)
        for key, x, name, kind in lines:
            self.x[key] = x

    def finish(self, caption_num, caption):
        """Draw the lifelines under everything else and size the canvas to the content."""
        d, bottom = self.d, self.y + 10
        body, d.out = d.out, []
        for key, x, name, kind in self.spec:
            d.lifeline(x, self.top, bottom, name, kind="actor" if kind == "actor" else "box",
                       stereo=None if kind in ("actor", None) else kind)
        d.out = body[:self.at] + d.out + body[self.at:]
        d.h = bottom + 50
        d.caption(caption_num, caption)

    def gap(self, h=12):
        self.y += h

    def msg(self, a, b, label, kind="sync", step=34):
        rows = label.count("\n")
        self.y += rows * 14
        self.d.msg(self.x[a], self.x[b], self.y, label, kind=kind, size=11)
        self.y += step

    def self_(self, a, label, step=40):
        self.d.msg(self.x[a], self.x[a], self.y - 8, label, kind="self", size=11)
        self.y += step

    def frag(self, tag, guard, x1, x2):
        """Open a combined fragment; returns a handle for else()/close()."""
        f = {"tag": tag, "x1": x1, "x2": x2, "y": self.y - 14, "elses": [], "guard": guard}
        self.y += 26
        return f

    def else_(self, f, guard):
        f["elses"].append((self.y - 14, guard))
        self.y += 18

    def close(self, f):
        y2 = self.y - 6
        d = self.d
        d.frame(f["x1"], f["y"], f["x2"] - f["x1"], y2 - f["y"], f["tag"], dash=None, sw=1)
        d.text(f["x1"] + len(f["tag"]) * 5.75 + 30, f["y"] + 16, f["guard"], size=10.5, anchor="start",
               weight="600", color=DATA)
        for ey, g in f["elses"]:
            d.line([(f["x1"], ey), (f["x2"], ey)], dash="6 4", sw=1)
            d.text(f["x1"] + 10, ey + 14, g, size=10.5, anchor="start", weight="600", color=DATA)
        self.y += 12


# ================================================================================================ B8
def seq_enrol_report():
    d = D(1460, 1160, "Sequence: enrolment and reporting", "Sequence diagram")
    d.text(20, 32, "Sequence: agent enrolment, then signed reports to the collector", size=17, weight="700",
           anchor="start")
    s = Seq(d, [("adm", 70, "IT admin", "actor"), ("cli", 250, "installer / CLI", None),
                ("ag", 470, "Agent service", None), ("h", 720, "Collector Handler", None),
                ("core", 930, "core", "module"), ("db", 1120, "collector.db", None),
                ("lw", 1320, "LinkWorker", None)])
    s.msg("adm", "cli", "install.ps1 -Server URL -Token kyh_enr_… -CaFile ca.pem")
    s.msg("cli", "h", "POST /api/v1/enroll\n{enrollment_token, hostname, platform, os, build_hash, policy_hash}")
    s.msg("h", "core", "enroll(conn, now, body)")
    s.msg("core", "db", "find token by sha-256 hash")
    f = s.frag("alt", "[token unknown, expired or used up]", 225, 1180)
    s.msg("core", "cli", "401 BAD_TOKEN | TOKEN_EXPIRED | TOKEN_EXHAUSTED", kind="reply")
    s.else_(f, "[valid]")
    s.msg("core", "db", "INSERT agent (new secret, build_trusted, policy_trusted)")
    s.msg("core", "db", "uses + 1; audit AGENT_ENROLLED")
    s.msg("core", "cli", "200 {agent_id, agent_secret, company_id}", kind="reply")
    s.close(f)
    s.self_("cli", "save agent.json")
    s.msg("cli", "ag", "start service (Windows service / systemd / launchd)", kind="async")
    s.gap(6)
    lp = s.frag("loop", "[every 30 s tick]", 410, 1400)
    s.self_("ag", "scan(): run due checks; full every snapshot period, else delta")
    s.self_("ag", "enqueue(): spool.put(seq, signed body); line in sent.jsonl")
    s.msg("ag", "h", "POST /api/v1/report\nX-KYH-Agent-Id, X-KYH-Signature: v1=HMAC-SHA256(secret, body)")
    s.msg("h", "core", "ingest(conn, now, agent_id, signature, raw)")
    s.self_("core", "size, enrolled, HMAC, schema, seq > last_seq, clock")
    s.self_("core", "strength = SIMULATED | UNTRUSTED_BUILD | UNTRUSTED_POLICY")
    d.text(s.x["core"] + 46, s.y - 30, "| TECHNICALLY_OBSERVED", size=11, anchor="start", halo=True)
    s.msg("core", "db", "INSERT report, observations; upsert results_current")
    s.msg("h", "lw", "wake() (linked companies re-evaluated)", kind="async")
    a = s.frag("alt", "[202 accepted, or 409 REPLAY]", 425, 1385)
    s.msg("h", "ag", "202 {accepted, report_id, evidence_strength}", kind="reply")
    s.self_("ag", "spool.ack(seq)")
    s.else_(a, "[429, 5xx or network error]")
    s.self_("ag", "backoff = min(max(2 × backoff, 30 s), 900 s); retry later")
    s.else_(a, "[other 4xx]")
    s.self_("ag", "spool.dead_letter(seq): never retried")
    s.close(a)
    s.close(lp)
    s.finish("B8", "Sequence diagram of enrolment and reporting. Solid head: call; open head: asynchronous; "
                    "dashed: reply.")
    return d


# ================================================================================================ B9
def seq_rollup():
    d = D(1460, 1200, "Sequence: fleet roll-up to the platform", "Sequence diagram")
    d.text(20, 32, "Sequence: collector pushes a signed fleet roll-up; the platform updates warranties only",
           size=17, weight="700", anchor="start")
    s = Seq(d, [("lw", 80, "LinkWorker", None), ("ev", 250, "evaluate", "module"),
                ("pl", 440, "platform_link", "module"), ("api", 650, "Platform API", None),
                ("fl", 830, "fleet", "module"), ("ob", 1010, "observations", "module"),
                ("cv", 1180, "coverage", "module"), ("db", 1360, "kyh.db", None)])
    lp = s.frag("loop", "[every 30 s, or when a report arrives; each linked company]", 30, 1420)
    s.msg("lw", "pl", "sync_company(app, company_id, link)")
    s.msg("pl", "ev", "evaluate_company(conn, id, now, s)")
    s.self_("ev", "liveness per host (ONLINE / UNVERIFIED / SILENT)")
    s.self_("ev", "host_control(): silence rule per control")
    s.self_("ev", "company_control(): PASS if ≥ 95 % of observed hosts pass")
    s.self_("ev", "coverage(): reporting ÷ declared ≥ 90 %")
    s.msg("ev", "pl", "snapshot", kind="reply")
    s.self_("pl", "build_controls(): map to CTRL-*; any failing source fails;")
    d.text(s.x["pl"] + 46, s.y - 30, "BACKUP pass sent as partial; MFA not sent", size=11, anchor="start", halo=True)
    s.gap(4)
    o = s.frag("opt", "[change_hash same and last push < 15 min ago]", 200, 620)
    s.msg("pl", "lw", "no push", kind="reply")
    s.close(o)
    s.self_("pl", "seq = next_seq(); signature = HMAC-SHA256(secret, body)")
    s.msg("pl", "api", "POST /api/collector/rollup\n{schema, collector_id, seq, sent_at, company, controls[], fleet}")
    s.msg("api", "fl", "authenticate(conn, collector_id, signature, raw)")
    s.msg("api", "fl", "ingest_rollup(conn, collector, raw)")
    s.self_("fl", "schema, collector, seq > last_seq, |now − sent_at| ≤ 5 min, link")
    s.msg("fl", "db", "INSERT collector_rollups (immutable); last_seq = seq")
    each = s.frag("loop", "[each control, if changed or > 6 h since the last record]", 790, 1405)
    s.msg("fl", "ob", "record_observation(AGENT_FLEET, TECHNICALLY_OBSERVED, locator)")
    s.msg("ob", "db", "INSERT observation")
    s.close(each)
    s.msg("fl", "db", "upsert fleet_snapshots; audit COLLECTOR_ROLLUP_RECEIVED")
    b = s.frag("opt", "[policy is BOUND]", 790, 1405)
    s.msg("fl", "cv", "evaluate_policy(conn, policy_id, company_id)")
    s.msg("cv", "ob", "resolve_posture(conn, company_id)")
    s.msg("ob", "cv", "best evidence per control", kind="reply")
    s.self_("cv", "state transitions (B3)")
    s.msg("cv", "db", "UPDATE warranties; INSERT warranty_events; audit")
    s.close(b)
    s.msg("fl", "api", "result", kind="reply")
    s.msg("api", "pl", "200 {observations_recorded, warranties[], repricing_performed: false}", kind="reply")
    s.self_("pl", "store platform_state (dashboard shows these states)")
    d.note(1010, s.y - 120, 400, 50, ["Pre-bind, the observations wait for the next quote.",
                               "Post-bind, only the warranty machine runs."], size=10.5)
    s.close(lp)
    s.finish("B9", "Sequence diagram of the Part 2 → Part 1 link. pricing_v2 is never called on this path.")
    return d


# ================================================================================================ B10
def seq_quote_bind():
    d = D(1460, 1060, "Sequence: quote and bind", "Sequence diagram")
    d.text(20, 32, "Sequence: an underwriter prices the risk (Engine B) and binds the policy", size=17,
           weight="700", anchor="start")
    s = Seq(d, [("uw", 70, "Underwriter", "actor"), ("ui", 220, "Web UI", None), ("api", 390, "api.Handler", None),
                ("pr", 580, "pricing_v2", "module"), ("ob", 770, "observations", "module"),
                ("un", 960, "underwriting", "module"), ("cv", 1140, "coverage", "module"),
                ("db", 1330, "kyh.db", None)])
    s.msg("uw", "ui", "Calculate quote")
    s.msg("ui", "api", "POST /api/quote {policy_id}\nX-Auth-Token")
    s.self_("api", "_user(conn, 'quote'): role UNDERWRITER or ADMIN")
    s.msg("api", "pr", "calculate_premium(conn, policy_id)")
    a = s.frag("alt", "[policy BOUND]", 360, 1390)
    s.msg("pr", "api", "409 POLICY_ALREADY_BOUND (monitoring never re-prices)", kind="reply")
    s.else_(a, "[not bound]")
    s.msg("pr", "ob", "resolve_posture(conn, company_id)")
    s.msg("ob", "pr", "best evidence per control, with provenance", kind="reply")
    s.self_("pr", "evidence_status → classify → control_effects → claims")
    s.self_("pr", "per peril: λ_p and expected payout; EL; ÷ TLR; × 1.18 GST")
    s.self_("pr", "gate(), refer(), what_if() savings")
    s.msg("pr", "db", "INSERT calculations (input snapshot + parameters); DRAFT → QUOTED; audit")
    s.msg("pr", "api", "result (premium, breakdown, gate, referral)", kind="reply")
    s.close(a)
    s.msg("api", "ui", "200 quote", kind="reply")
    s.msg("ui", "uw", "premium breakdown, gate, referral reasons, savings", kind="reply")
    s.gap(6)
    s.msg("uw", "ui", "Bind (tick referral approval if asked)")
    s.msg("ui", "api", "POST /api/policies/bind\n{policy_id, calculation_id, referral_approved}")
    s.msg("api", "un", "bind_policy(conn, policy_id, calculation_id, referral_approved)")
    b = s.frag("alt", "[already bound | unknown calculation | INELIGIBLE under BLOCK | referral not approved]",
               360, 1390)
    s.msg("un", "api", "409 POLICY_ALREADY_BOUND | UNKNOWN_CALCULATION | INELIGIBLE | REFERRAL_REQUIRED",
          kind="reply")
    s.else_(b, "[else]")
    s.msg("un", "db", "UPDATE policies: BOUND, bound_at, bound_calculation_id, bound_premium")
    s.msg("un", "cv", "initialize_warranties(conn, policy_id)")
    s.msg("cv", "db", "INSERT warranties (MET) and events")
    s.msg("cv", "ob", "evaluate_policy → resolve_posture")
    s.msg("cv", "db", "a control already failing → IN_GRACE")
    s.msg("un", "db", "audit POLICY_BOUND")
    s.msg("un", "api", "{status BOUND, bound_premium}", kind="reply")
    s.close(b)
    s.msg("api", "ui", "200 bound", kind="reply")
    s.finish("B10", "Sequence diagram of quote and bind. The bound premium is the stored calculation's premium; "
                     "nothing re-prices it.")
    return d


FIGURES = [
    ("B8", "seq_enrol_report", "Sequence: agent enrolment and reporting", seq_enrol_report),
    ("B9", "seq_rollup", "Sequence: fleet roll-up and warranty evaluation", seq_rollup),
    ("B10", "seq_quote_bind", "Sequence: quote and bind", seq_quote_bind),
]
