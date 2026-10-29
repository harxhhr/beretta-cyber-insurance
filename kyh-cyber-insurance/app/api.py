"""HTTP layer: JSON APIs + static frontend. Standard library http.server only."""
import json
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import audit, catalogue, coverage, fleet, observations, pricing_v2, security, underwriting
from .database import (BASE_DIR, connect, get_config, init_db, new_id, now_iso,
                       set_config)

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
MAX_BODY = 1_000_000  # 1 MB request cap

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8", ".json": "application/json",
        ".svg": "image/svg+xml", ".png": "image/png", ".pdf": "application/pdf",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


class ApiError(Exception):
    def __init__(self, code, message, status=400, field=None):
        super().__init__(message)
        self.code, self.message, self.status, self.field = code, message, status, field


def err_from(e):
    if isinstance(e, ApiError):
        return e
    if isinstance(e, security.AuthError):
        return ApiError(e.code, e.message, e.status)
    if isinstance(e, observations.ValidationError):
        return ApiError(e.code, e.message, 400, e.field)
    if isinstance(e, fleet.FleetError):
        return ApiError(e.code, e.message, e.status)
    if isinstance(e, (underwriting.EngineError, pricing_v2.EngineError)):
        status = 409 if e.code == "POLICY_ALREADY_BOUND" else 400
        return ApiError(e.code, e.message, status)
    if isinstance(e, ValueError):
        return ApiError("VALIDATION_ERROR", str(e), 400)
    return ApiError("INTERNAL_ERROR", "An internal error occurred.", 500)


class Handler(BaseHTTPRequestHandler):
    server_version = "KYH/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ util
    def log_message(self, fmt, *args):  # quieter default logging
        print(f"[{now_iso()}] {self.address_string()} {fmt % args}")

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ApiError("PAYLOAD_TOO_LARGE", "Request body too large", 413)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise ApiError("INVALID_JSON", "Request body must be valid JSON")
        if not isinstance(data, dict):
            raise ApiError("INVALID_JSON", "Request body must be a JSON object")
        return data

    def _raw_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ApiError("PAYLOAD_TOO_LARGE", "Request body too large", 413)
        return self.rfile.read(length) if length else b""

    def _user(self, conn, perm="read"):
        user = security.authenticate_user(conn, self.headers.get("X-Auth-Token"))
        security.require(user, perm)
        return user

    # -- customer scoping: an insured customer only ever sees their own company ----------------
    @staticmethod
    def _is_customer(user):
        return user["role"] == "CUSTOMER"

    def _own(self, user, company_id):
        """Staff see every company. A customer sees only the company on their account; anything else is
        reported as not found, so other companies' ids are not even confirmed to exist."""
        if self._is_customer(user) and (not user.get("company_id") or company_id != user["company_id"]):
            raise ApiError("NOT_FOUND", "No such record", 404)

    def _reader(self, conn, company_id):
        user = self._user(conn)
        self._own(user, company_id)
        return user

    def _policy_reader(self, conn, policy_id):
        row = conn.execute("SELECT company_id FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
        user = self._user(conn)
        self._own(user, row["company_id"] if row else None)
        return user

    # Parts of a quote an insured customer sees: the premium, what is needed before cover, which controls
    # count and what verifying them would save. The underwriting workings (per-peril maths, expense and
    # margin split, assumptions, referral) stay with the insurer.
    CUSTOMER_QUOTE_KEYS = ("model_version", "calculation_id", "calculated_at", "technical_premium", "gst",
                           "gst_rate", "total_premium", "eligibility", "statuses", "evidence", "what_if",
                           "policy_structure")

    def _customer_quote(self, r):
        out = {k: r[k] for k in self.CUSTOMER_QUOTE_KEYS if k in r}
        cls = r.get("classification") or {}
        out["classification"] = dict(sector=cls.get("sector"), nic_code=cls.get("nic_code"))
        out["claims"] = dict(incidents=(r.get("claims") or {}).get("incidents"))
        if "total_premium" not in r:    # a V1 quote
            out["total_premium"] = None
        elig = out.get("eligibility") or {}
        out["eligibility"] = dict(status=elig.get("status"), reason=elig.get("reason"))
        out["explanation"] = (
            f"Your premium is ₹{r['technical_premium']:,.0f}"
            + (f" (₹{r['total_premium']:,.0f} with GST)" if r.get("total_premium") else "")
            + ". It reflects your sector, your turnover, your claims history and how strongly each security "
              "control is evidenced. Verifying the controls listed below would lower it.")
        out["customer_view"] = True
        return out

    def _agent(self, conn):
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
        return security.authenticate_agent(conn, token)

    # ------------------------------------------------------------- dispatch
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def _dispatch(self, method):
        conn = connect()
        path = self.path.split("?")[0]
        query = {}
        if "?" in self.path:
            for pair in self.path.split("?", 1)[1].split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    query[k] = v
        try:
            if not path.startswith("/api/"):
                if method == "GET":
                    return self._static(path)
                raise ApiError("NOT_FOUND", "Unknown path", 404)
            handler = self._route(method, path)
            if handler is None:
                raise ApiError("NOT_FOUND", f"No route {method} {path}", 404)
            fn, params = handler
            result = fn(conn, params, query)
            conn.commit()
            self._send_json(result)
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001 — single boundary, structured errors
            conn.rollback()
            ae = err_from(e)
            if ae.code == "INTERNAL_ERROR":
                traceback.print_exc()
            payload = {"error": ae.code, "message": ae.message}
            if ae.field:
                payload["field"] = ae.field
            self._send_json(payload, ae.status)

    ROUTES = [
        ("GET",  r"^/api/meta$", "h_meta"),
        ("GET",  r"^/api/demo/tokens$", "h_demo_tokens"),
        ("GET",  r"^/api/me$", "h_me"),
        ("GET",  r"^/api/dashboard$", "h_dashboard"),
        ("GET",  r"^/api/companies$", "h_companies_list"),
        ("POST", r"^/api/companies$", "h_companies_create"),
        ("GET",  r"^/api/companies/(?P<id>[\w-]+)$", "h_company_detail"),
        ("PUT",  r"^/api/companies/(?P<id>[\w-]+)$", "h_company_update"),
        ("GET",  r"^/api/companies/(?P<id>[\w-]+)/fleet$", "h_company_fleet"),
        ("POST", r"^/api/collector/rollup$", "h_collector_rollup"),
        ("GET",  r"^/api/admin/collectors$", "h_collectors_list"),
        ("POST", r"^/api/admin/collectors$", "h_collectors_create"),
        ("POST", r"^/api/admin/collectors/(?P<id>[\w-]+)/links$", "h_collector_link"),
        ("GET",  r"^/api/posture/(?P<id>[\w-]+)$", "h_posture"),
        ("POST", r"^/api/questionnaires$", "h_questionnaire_submit"),
        ("GET",  r"^/api/questionnaires/(?P<id>[\w-]+)$", "h_questionnaire_get"),
        ("POST", r"^/api/documents$", "h_document_register"),
        ("POST", r"^/api/documents/(?P<id>[\w-]+)/assess$", "h_document_assess"),
        ("GET",  r"^/api/documents/(?P<id>[\w-]+)$", "h_documents_get"),
        ("POST", r"^/api/claims$", "h_claims_create"),
        ("GET",  r"^/api/claims/(?P<id>[\w-]+)$", "h_claims_get"),
        ("POST", r"^/api/outside-in$", "h_signal_create"),
        ("GET",  r"^/api/outside-in/(?P<id>[\w-]+)$", "h_signals_get"),
        ("POST", r"^/api/agent/report$", "h_agent_report"),
        ("GET",  r"^/api/agent/status/(?P<id>[\w-]+)$", "h_agent_status"),
        ("POST", r"^/api/quote$", "h_quote"),
        ("GET",  r"^/api/quote/(?P<id>[\w-]+)$", "h_quote_get"),
        ("POST", r"^/api/policies/bind$", "h_bind"),
        ("GET",  r"^/api/policies/(?P<id>[\w-]+)$", "h_policy_get"),
        ("PUT",  r"^/api/policies/(?P<id>[\w-]+)/coverages$", "h_policy_coverages"),
        ("GET",  r"^/api/policies/(?P<id>[\w-]+)/warranties$", "h_warranties"),
        ("GET",  r"^/api/policies/(?P<id>[\w-]+)/warranty-events$", "h_warranty_events"),
        ("GET",  r"^/api/audit$", "h_audit"),
        ("GET",  r"^/api/regulatory$", "h_regulatory"),
        ("GET",  r"^/api/forms$", "h_forms"),
        ("GET",  r"^/api/admin/config$", "h_config_get"),
        ("GET",  r"^/api/admin/pricing-params$", "h_pricing_params"),
        ("PUT",  r"^/api/admin/config$", "h_config_put"),
        ("PUT",  r"^/api/admin/controls/(?P<id>[\w-]+)$", "h_control_put"),
        ("PUT",  r"^/api/admin/sectors$", "h_sectors_put"),
    ]

    def _route(self, method, path):
        for m, pattern, name in self.ROUTES:
            if m != method:
                continue
            match = re.match(pattern, path)
            if match:
                return getattr(self, name), match.groupdict()
        return None

    # -------------------------------------------------------------- static
    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.realpath(os.path.join(FRONTEND_DIR, rel))
        if not full.startswith(os.path.realpath(FRONTEND_DIR)) or not os.path.isfile(full):
            raise ApiError("NOT_FOUND", "Not found", 404)
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(os.path.splitext(full)[1],
                                                  "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ handlers
    def h_meta(self, conn, p, q):
        controls = [dict(r) for r in conn.execute(
            "SELECT * FROM controls ORDER BY tier, control_id").fetchall()]
        sectors = {r["sector"]: r["base_frequency"] for r in
                   conn.execute("SELECT * FROM sectors").fetchall()}
        prm = pricing_v2.load_params()
        v2 = dict(model_version=pricing_v2.MODEL_VERSION,
                  nic_sectors=prm["sector"]["nic_map"]["ranges"],
                  perils=pricing_v2.PERILS, heads=prm["heads"]["names"], head_order=prm["heads"]["order"],
                  frequency_controls={k: dict(S=c["S"], p=c["p"], stage=c["stage"], perils=c["perils"],
                                              source=c["source"], tag=c["tag"])
                                      for k, c in prm["controls"]["frequency"].items()},
                  severity_controls={k: dict(S=c["S"], p=c["p"], targets=c["targets"], source=c["source"],
                                             tag=c["tag"]) for k, c in prm["controls"]["severity"].items()},
                  unpriced=prm["controls"]["unpriced"]["items"],
                  warranties=prm["gating"]["warranties"],
                  credit_x=pricing_v2.v(prm["controls"]["credit_x"]),
                  tlr=pricing_v2.v(prm["loadings"]["tlr"]), gst=pricing_v2.v(prm["loadings"]["gst"]),
                  usd_inr=pricing_v2.v(prm["currency"]["usd_inr"]))
        return dict(model_version=pricing_v2.MODEL_VERSION, controls=controls,
                    sectors=sectors, v2=v2,
                    evidence_strengths=catalogue.EVIDENCE_STRENGTHS,
                    source_types=catalogue.SOURCE_TYPES,
                    document_types=sorted(observations.DOCUMENT_CATEGORIES),
                    disclaimer=catalogue.DISCLAIMER,
                    assumptions_note="Calibrated to published claims data (mostly US) with stated assumptions — "
                                     "not a filed rate.")

    def h_demo_tokens(self, conn, p, q):
        # PROTOTYPE CONVENIENCE ONLY (documented in README/limitations):
        # exposes demo role tokens so the local dashboard can switch roles.
        # Must be removed for any non-local deployment.
        rows = conn.execute("SELECT role, token FROM users").fetchall()
        return {r["role"]: r["token"] for r in rows}

    def h_me(self, conn, p, q):
        """Who is viewing: role, and for an insured customer the one company on their account."""
        user = self._user(conn)
        co = conn.execute("SELECT name FROM companies WHERE company_id=?", (user["company_id"],)).fetchone()             if user.get("company_id") else None
        return dict(role=user["role"], name=user["name"], company_id=user.get("company_id"),
                    company_name=co["name"] if co else None,
                    read_only=self._is_customer(user))

    def h_dashboard(self, conn, p, q):
        self._user(conn, "staff")
        coverage.expire_grace_periods(conn)
        stats = {}
        stats["companies"] = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
        stats["active_policies"] = conn.execute(
            "SELECT COUNT(*) c FROM policies WHERE status='BOUND'").fetchone()["c"]
        stats["pending_underwriting"] = conn.execute(
            "SELECT COUNT(*) c FROM policies WHERE status IN ('DRAFT','QUOTED')").fetchone()["c"]
        stats["quotes_issued"] = conn.execute(
            "SELECT COUNT(*) c FROM calculations").fetchone()["c"]
        stats["warranties_breached"] = conn.execute(
            "SELECT COUNT(*) c FROM warranties WHERE state='BREACHED'").fetchone()["c"]
        stats["warranties_in_grace"] = conn.execute(
            "SELECT COUNT(*) c FROM warranties WHERE state='IN_GRACE'").fetchone()["c"]
        # Average posture score = share of PASS across resolved controls
        scores = []
        for c in conn.execute("SELECT company_id FROM companies").fetchall():
            posture = observations.resolve_posture(conn, c["company_id"])
            known = [v for v in posture.values()
                     if v["status"] != "UNKNOWN" and not v["monitoring_only"]]
            if known:
                scores.append(sum(1 for v in known if v["status"] == "PASS") / len(known))
        stats["avg_posture_score"] = round(100 * sum(scores) / len(scores)) if scores else None
        stats["recent_audit"] = audit.query(conn, limit=12)
        rows = conn.execute("""SELECT p.policy_id, p.status, p.bound_premium, p.company_id,
                                      c.name, c.sector FROM policies p
                               JOIN companies c ON c.company_id=p.company_id""").fetchall()
        stats["policies"] = [dict(r) for r in rows]
        return stats

    # -- companies ---------------------------------------------------------
    def h_companies_list(self, conn, p, q):
        user = self._user(conn)
        sql = """SELECT co.*, po.policy_id, po.status AS policy_status, po.bound_premium
                 FROM companies co LEFT JOIN policies po ON po.company_id=co.company_id"""
        if self._is_customer(user):
            rows = conn.execute(sql + " WHERE co.company_id=?", (user.get("company_id"),)).fetchall()
        else:
            rows = conn.execute(sql + " ORDER BY co.name").fetchall()
        return {"companies": [dict(r) for r in rows]}

    def h_companies_create(self, conn, p, q):
        user = self._user(conn, "intake")
        b = self._body()
        name = security.clean_str(b.get("name"), "name")
        prof = self._profile_fields(b, required=True)
        prm = pricing_v2.load_params()
        sector, _ = pricing_v2.nic_to_sector(prof["nic_code"], prm)   # stored for display; V2 prices from the NIC code
        emp = int(security.clean_number(b.get("employee_count"), "employee_count", 0, required=False) or 0)
        geo = security.clean_str(b.get("geography"), "geography", required=False) or "India"
        limit_total = security.clean_number(b.get("limit_total_inr", 10_000_000), "limit_total_inr", 1)
        retention = security.clean_number(b.get("retention_inr", 100_000), "retention_inr", 0)
        cid, pid = new_id("CO"), new_id("POL")
        conn.execute("""INSERT INTO companies (company_id,name,sector,annual_revenue_inr,employee_count,geography,
                        created_at,nic_code,years_in_operation,regulated_rbi_sebi) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     (cid, name, sector, prof["annual_revenue_inr"], emp, geo, now_iso(), prof["nic_code"],
                      prof["years_in_operation"], prof["regulated_rbi_sebi"]))
        conn.execute("""INSERT INTO policies (policy_id,company_id,status,period_start,
                        period_end,created_at,limit_total_inr,retention_inr) VALUES (?,?, 'DRAFT', ?,?,?,?,?)""",
                     (pid, cid, b.get("period_start") or "2026-09-01",
                      b.get("period_end") or "2027-08-31", now_iso(), limit_total, retention))
        defaults = conn.execute("SELECT * FROM coverage_head_defaults").fetchall()
        for h in defaults:
            conn.execute("""INSERT INTO policy_coverages
                (policy_id,coverage_id,name,limit_inr,sublimit_inr,deductible_inr,
                 severity_fraction,enabled) VALUES (?,?,?,?,?,?,?,1)""",
                (pid, h["coverage_id"], h["name"], 1_000_000, None, 50_000,
                 h["severity_fraction"]))
        import secrets as pysecrets
        atok = pysecrets.token_urlsafe(24)
        aid = new_id("AGT")
        conn.execute("INSERT INTO agents VALUES (?,?,?,?,?,?)",
                     (aid, cid, atok, None, None, now_iso()))
        audit.log(conn, user["name"], "COMPANY_CREATED", "COMPANY", cid,
                  new_value=dict(name=name, sector=sector, **prof))
        return dict(company_id=cid, policy_id=pid, agent_id=aid, agent_token=atok)

    @staticmethod
    def _profile_fields(b, required=False):
        """Pricing V2 classification inputs: NIC 2008 code, turnover, years in operation, RBI/SEBI flag."""
        out = {}
        if required or "nic_code" in b:
            nic = security.clean_str(b.get("nic_code"), "nic_code", 5)
            if not re.fullmatch(r"\d{2}(\d{1,3})?", nic):
                raise ApiError("INVALID_NIC_CODE", "NIC 2008 code must be digits; the first two are the division",
                               field="nic_code")
            out["nic_code"] = nic[:2]
        if required or "annual_revenue_inr" in b:
            out["annual_revenue_inr"] = security.clean_number(b.get("annual_revenue_inr"), "annual_revenue_inr", 0)
        if required or "years_in_operation" in b:
            out["years_in_operation"] = security.clean_number(b.get("years_in_operation"), "years_in_operation",
                                                              0, 500, required=False)
        if required or "regulated_rbi_sebi" in b:
            out["regulated_rbi_sebi"] = 1 if b.get("regulated_rbi_sebi") in (True, 1, "1", "true", "yes") else 0
        return out

    def h_company_update(self, conn, p, q):
        user = self._user(conn, "intake")
        co = conn.execute("SELECT * FROM companies WHERE company_id=?", (p["id"],)).fetchone()
        if not co:
            raise ApiError("UNKNOWN_COMPANY", "No such company", 404)
        pol = conn.execute("SELECT * FROM policies WHERE company_id=?", (p["id"],)).fetchone()
        if pol and pol["status"] == "BOUND":
            raise ApiError("POLICY_ALREADY_BOUND", "The policy is bound; its rating inputs are fixed.", 409)
        b = self._body()
        prof = self._profile_fields(b)
        if not prof:
            raise ApiError("NO_FIELDS", "Nothing to update")
        if "nic_code" in prof:
            prof["sector"] = pricing_v2.nic_to_sector(prof["nic_code"], pricing_v2.load_params())[0]
        sets = ", ".join(f"{k}=?" for k in prof)
        conn.execute(f"UPDATE companies SET {sets} WHERE company_id=?", (*prof.values(), p["id"]))
        audit.log(conn, user["name"], "COMPANY_PROFILE_UPDATED", "COMPANY", p["id"],
                  old_value={k: co[k] for k in prof}, new_value=prof)
        return dict(ok=True)

    def h_company_detail(self, conn, p, q):
        self._reader(conn, p["id"])
        co = conn.execute("SELECT * FROM companies WHERE company_id=?", (p["id"],)).fetchone()
        if not co:
            raise ApiError("UNKNOWN_COMPANY", "No such company", 404)
        pol = conn.execute("SELECT * FROM policies WHERE company_id=?", (p["id"],)).fetchone()
        covs = [dict(r) for r in conn.execute(
            "SELECT * FROM policy_coverages WHERE policy_id=?", (pol["policy_id"],)).fetchall()]
        docs = [dict(r) for r in conn.execute(
            "SELECT * FROM documents WHERE company_id=? ORDER BY uploaded_at DESC",
            (p["id"],)).fetchall()]
        claims = [dict(r) for r in conn.execute(
            "SELECT * FROM claims WHERE company_id=? ORDER BY incident_date DESC",
            (p["id"],)).fetchall()]
        signals = [dict(r) for r in conn.execute(
            "SELECT * FROM outside_in_signals WHERE company_id=?", (p["id"],)).fetchall()]
        calcs = [dict(calculation_id=r["calculation_id"], calculated_at=r["calculated_at"],
                      technical_premium=r["technical_premium"], eligibility=r["eligibility"],
                      model_version=r["model_version"])
                 for r in conn.execute(
                     "SELECT * FROM calculations WHERE company_id=? ORDER BY calculated_at DESC",
                     (p["id"],)).fetchall()]
        return dict(company=dict(co), policy=dict(pol), coverages=covs, documents=docs,
                    claims=claims, signals=signals, calculations=calcs,
                    agent=self.h_agent_status(conn, {"id": p["id"]}, {}, _checked=True),
                    fleet=fleet.latest_snapshot(conn, p["id"]))

    def h_posture(self, conn, p, q):
        self._reader(conn, p["id"])
        return dict(company_id=p["id"],
                    posture=observations.resolve_posture(conn, p["id"]))

    # -- intake ------------------------------------------------------------
    def h_questionnaire_submit(self, conn, p, q):
        user = self._user(conn, "intake")
        b = self._body()
        cid = security.clean_str(b.get("company_id"), "company_id")
        answers = b.get("answers")
        if not isinstance(answers, list) or not answers:
            raise ApiError("INVALID_ANSWERS", "answers must be a non-empty list", field="answers")
        ids = []
        for a in answers:
            ids.append(observations.record_observation(
                conn, company_id=cid, control_id=a.get("control_id"),
                value=a.get("value"), source_type="QUESTIONNAIRE",
                source_id="web-questionnaire",
                source_locator=f"Question {a.get('control_id')}",
                dims=a.get("dims"), notes=a.get("notes"), actor=user["name"]))
        audit.log(conn, user["name"], "QUESTIONNAIRE_UPDATED", "COMPANY", cid,
                  metadata=dict(observations=len(ids)))
        self._maybe_evaluate_warranties(conn, cid)
        return dict(recorded=len(ids), observation_ids=ids)

    def h_questionnaire_get(self, conn, p, q):
        self._reader(conn, p["id"])
        rows = conn.execute("""SELECT * FROM observations WHERE company_id=? AND
                               source_type='QUESTIONNAIRE' ORDER BY observed_at DESC""",
                            (p["id"],)).fetchall()
        return {"observations": [dict(r) for r in rows]}

    def h_document_register(self, conn, p, q):
        user = self._user(conn, "intake")
        b = self._body()
        did = observations.register_document(
            conn, security.clean_str(b.get("company_id"), "company_id"),
            security.clean_str(b.get("document_type"), "document_type"),
            security.clean_str(b.get("filename"), "filename"), actor=user["name"])
        return dict(document_id=did)

    def h_document_assess(self, conn, p, q):
        user = self._user(conn, "assess")
        b = self._body()
        oid = observations.assess_document_field(
            conn, p["id"], security.clean_str(b.get("control_id"), "control_id"),
            b.get("value"), security.clean_str(b.get("source_locator"), "source_locator"),
            dims=b.get("dims"), evidence_strength=b.get("evidence_strength"),
            actor=user["name"])
        doc = conn.execute("SELECT company_id FROM documents WHERE document_id=?",
                           (p["id"],)).fetchone()
        self._maybe_evaluate_warranties(conn, doc["company_id"])
        return dict(observation_id=oid)

    def h_documents_get(self, conn, p, q):
        self._reader(conn, p["id"])
        rows = conn.execute("SELECT * FROM documents WHERE company_id=?", (p["id"],)).fetchall()
        return {"documents": [dict(r) for r in rows]}

    def h_claims_create(self, conn, p, q):
        user = self._user(conn, "intake")
        b = self._body()
        cid = security.clean_str(b.get("company_id"), "company_id")
        claim_id = new_id("CLM")
        material = b.get("material")
        material = None if material in (None, "") else (1 if material in (True, 1, "1", "true", "yes") else 0)
        conn.execute("""INSERT INTO claims (claim_id,company_id,incident_date,incident_type,loss_amount_inr,
                        status,remediation,created_at,material) VALUES (?,?,?,?,?,?,?,?,?)""",
                     (claim_id, cid,
                      security.clean_str(b.get("incident_date"), "incident_date", 20),
                      security.clean_str(b.get("incident_type"), "incident_type"),
                      security.clean_number(b.get("loss_amount_inr"), "loss_amount_inr", 0,
                                            required=False),
                      security.clean_str(b.get("status"), "status", 40),
                      security.clean_str(b.get("remediation"), "remediation", 500,
                                         required=False),
                      now_iso(), material))
        audit.log(conn, user["name"], "CLAIM_RECORDED", "CLAIM", claim_id,
                  new_value=dict(company_id=cid, incident_type=b.get("incident_type")))
        return dict(claim_id=claim_id)

    def h_claims_get(self, conn, p, q):
        self._reader(conn, p["id"])
        return {"claims": [dict(r) for r in conn.execute(
            "SELECT * FROM claims WHERE company_id=? ORDER BY incident_date DESC",
            (p["id"],)).fetchall()]}

    def h_signal_create(self, conn, p, q):
        user = self._user(conn, "intake")
        b = self._body()
        cid = security.clean_str(b.get("company_id"), "company_id")
        related = b.get("related_control_id") or None
        if related and not conn.execute("SELECT 1 FROM controls WHERE control_id=?", (related,)).fetchone():
            raise ApiError("UNKNOWN_CONTROL", f"Unknown control {related}", field="related_control_id")
        sid, oid = observations.record_signal(
            conn, cid, security.clean_str(b.get("signal_type"), "signal_type", 60),
            security.clean_str(b.get("detail"), "detail", 300, required=False), related, actor=user["name"])
        self._maybe_evaluate_warranties(conn, cid)
        return dict(signal_id=sid, observation_id=oid)

    def h_signals_get(self, conn, p, q):
        self._reader(conn, p["id"])
        return {"signals": [dict(r) for r in conn.execute(
            "SELECT * FROM outside_in_signals WHERE company_id=?", (p["id"],)).fetchall()]}

    # -- agent ---------------------------------------------------------------
    AGENT_STATUS_MAP = {"PASS": "true", "FAIL": "false", "WARN": "partial",
                        "PARTIAL": "partial"}

    def h_agent_report(self, conn, p, q):
        agent = self._agent(conn)
        b = self._body()
        checks = b.get("checks")
        if not isinstance(checks, list):
            raise ApiError("INVALID_REPORT", "Report must contain a 'checks' list",
                           field="checks")
        if b.get("agent_id") and b["agent_id"] != agent["agent_id"]:
            raise ApiError("AGENT_MISMATCH", "agent_id does not match the token", 403)
        report_id = new_id("RPT")
        conn.execute("INSERT INTO agent_reports VALUES (?,?,?,?,?)",
                     (report_id, agent["agent_id"], agent["company_id"], now_iso(),
                      json.dumps(b)))  # immutable raw report
        conn.execute("UPDATE agents SET last_seen=?, hostname=? WHERE agent_id=?",
                     (now_iso(), str(b.get("hostname", ""))[:120], agent["agent_id"]))
        recorded, skipped = 0, []
        for ch in checks:
            status = str(ch.get("status", "")).upper()
            if status == "NOT_SUPPORTED":
                skipped.append(ch.get("control_id"))
                continue
            value = self.AGENT_STATUS_MAP.get(status)
            if value is None:
                raise ApiError("INVALID_CONTROL_VALUE",
                               f"Unknown check status '{ch.get('status')}'",
                               field=str(ch.get("control_id")))
            observations.record_observation(
                conn, company_id=agent["company_id"], control_id=ch.get("control_id"),
                value=value, source_type="AGENT", source_id=report_id,
                source_locator=f"{b.get('hostname','endpoint')} / {ch.get('check_name', ch.get('control_id'))}",
                evidence_strength="TECHNICALLY_OBSERVED",
                confidence=float(ch.get("confidence", 1.0)),
                observed_at=ch.get("timestamp"), notes=ch.get("evidence"),
                actor=f"agent:{agent['agent_id']}")
            recorded += 1
        audit.log(conn, f"agent:{agent['agent_id']}", "AGENT_REPORT_RECEIVED",
                  "AGENT_REPORT", report_id,
                  new_value=dict(company_id=agent["company_id"], checks=len(checks),
                                 recorded=recorded, not_supported=skipped))
        # Post-bind: warranty evaluation ONLY. Never premium recalculation.
        warranty_result = self._maybe_evaluate_warranties(conn, agent["company_id"])
        return dict(report_id=report_id, observations_recorded=recorded,
                    not_supported=skipped, warranty_evaluation=warranty_result,
                    repricing_performed=False)

    def _maybe_evaluate_warranties(self, conn, company_id):
        pol = conn.execute("SELECT * FROM policies WHERE company_id=? AND status='BOUND'",
                           (company_id,)).fetchone()
        if not pol:
            return None
        results = coverage.evaluate_policy(conn, pol["policy_id"], company_id)
        return dict(policy_id=pol["policy_id"],
                    warranties=[dict(control_id=w["control_id"], state=w["state"])
                                for w in results])

    def h_agent_status(self, conn, p, q, _checked=False):
        if not _checked:
            self._reader(conn, p["id"])
        agents = conn.execute("SELECT agent_id, hostname, last_seen, created_at "
                              "FROM agents WHERE company_id=?", (p["id"],)).fetchall()
        reports = conn.execute("""SELECT report_id, received_at FROM agent_reports
                                  WHERE company_id=? ORDER BY received_at DESC LIMIT 1""",
                               (p["id"],)).fetchone()
        return dict(agents=[dict(a) for a in agents],
                    connected=any(a["last_seen"] for a in agents),
                    endpoint_count=len(agents),
                    latest_report=dict(reports) if reports else None)

    # -- live-monitoring collector (Part 2) -----------------------------------
    def h_collector_rollup(self, conn, p, q):
        raw = self._raw_body()
        collector = fleet.authenticate(conn, self.headers.get("X-KYH-Collector-Id"),
                                       self.headers.get("X-KYH-Signature"), raw)
        security.rate_limit(conn, "collector:" + collector["collector_id"])
        return fleet.ingest_rollup(conn, collector, raw)

    def h_company_fleet(self, conn, p, q):
        self._reader(conn, p["id"])
        return {"fleet": fleet.latest_snapshot(conn, p["id"])}

    def h_collectors_list(self, conn, p, q):
        self._user(conn, "admin")
        return {"collectors": fleet.list_collectors(conn)}

    def h_collectors_create(self, conn, p, q):
        user = self._user(conn, "admin")
        b = self._body()
        return fleet.register_collector(
            conn, security.clean_str(b.get("name"), "name", 80),
            security.clean_str(b.get("dashboard_url"), "dashboard_url", 200, required=False),
            actor=user["name"])

    def h_collector_link(self, conn, p, q):
        user = self._user(conn, "admin")
        b = self._body()
        return fleet.link_company(conn, p["id"], security.clean_str(b.get("company_id"), "company_id"),
                                  security.clean_str(b.get("collector_company_id"), "collector_company_id", 80),
                                  actor=user["name"])

    # -- quote / bind -------------------------------------------------------
    def h_quote(self, conn, p, q):
        user = self._user(conn, "quote")
        b = self._body()
        pid = security.clean_str(b.get("policy_id"), "policy_id")
        return pricing_v2.calculate_premium(conn, pid, actor=user["name"])

    def h_quote_get(self, conn, p, q):
        user = self._user(conn)
        row = conn.execute("SELECT * FROM calculations WHERE calculation_id=?",
                           (p["id"],)).fetchone()
        if not row:
            raise ApiError("UNKNOWN_CALCULATION", "No such calculation", 404)
        self._own(user, row["company_id"])
        result = json.loads(row["result_json"])
        if self._is_customer(user):
            return self._customer_quote(result)
        result["input_snapshot"] = json.loads(row["input_snapshot"])
        return result

    def h_bind(self, conn, p, q):
        user = self._user(conn, "bind")
        b = self._body()
        return underwriting.bind_policy(
            conn, security.clean_str(b.get("policy_id"), "policy_id"),
            security.clean_str(b.get("calculation_id"), "calculation_id"),
            actor=user["name"], referral_approved=b.get("referral_approved") is True)

    def h_policy_get(self, conn, p, q):
        self._policy_reader(conn, p["id"])
        pol = conn.execute("SELECT * FROM policies WHERE policy_id=?", (p["id"],)).fetchone()
        if not pol:
            raise ApiError("UNKNOWN_POLICY", "No such policy", 404)
        covs = [dict(r) for r in conn.execute(
            "SELECT * FROM policy_coverages WHERE policy_id=?", (p["id"],)).fetchall()]
        return dict(policy=dict(pol), coverages=covs)

    def h_policy_coverages(self, conn, p, q):
        user = self._user(conn, "quote")
        pol = conn.execute("SELECT * FROM policies WHERE policy_id=?", (p["id"],)).fetchone()
        if not pol:
            raise ApiError("UNKNOWN_POLICY", "No such policy", 404)
        if pol["status"] == "BOUND":
            raise ApiError("POLICY_ALREADY_BOUND",
                           "Coverage structure of a bound policy cannot be edited.", 409)
        b = self._body()
        for k in ("limit_total_inr", "retention_inr"):
            if k in b:
                conn.execute(f"UPDATE policies SET {k}=? WHERE policy_id=?",
                             (security.clean_number(b[k], k, 1 if k == "limit_total_inr" else 0), p["id"]))
        for c in b.get("coverages", []):
            conn.execute("""UPDATE policy_coverages SET limit_inr=?, sublimit_inr=?,
                            deductible_inr=?, enabled=? WHERE policy_id=? AND coverage_id=?""",
                         (security.clean_number(c.get("limit_inr"), "limit_inr", 0),
                          security.clean_number(c.get("sublimit_inr"), "sublimit_inr", 0,
                                                required=False),
                          security.clean_number(c.get("deductible_inr"), "deductible_inr", 0,
                                                required=False) or 0,
                          1 if c.get("enabled", True) else 0, p["id"], c.get("coverage_id")))
        audit.log(conn, user["name"], "POLICY_STRUCTURE_UPDATED", "POLICY", p["id"],
                  new_value=b)
        return dict(ok=True)

    def h_warranties(self, conn, p, q):
        self._policy_reader(conn, p["id"])
        return dict(warranties=coverage.policy_warranties(conn, p["id"]),
                    note="Post-bind security changes affect warranty status and configured "
                         "coverage consequences. They do not automatically re-price the "
                         "bound policy.")

    def h_warranty_events(self, conn, p, q):
        self._policy_reader(conn, p["id"])
        return {"events": coverage.policy_warranty_events(conn, p["id"],
                                                          q.get("limit", 200))}

    # -- audit / admin -------------------------------------------------------
    def h_audit(self, conn, p, q):
        self._user(conn, "staff")
        return {"events": audit.query(conn, event_type=q.get("event_type"),
                                      entity_id=q.get("entity_id"),
                                      actor=q.get("actor"),
                                      limit=q.get("limit", 200))}

    def h_regulatory(self, conn, p, q):
        return dict(context=catalogue.REGULATORY_CONTEXT, disclaimer=catalogue.DISCLAIMER)

    def h_forms(self, conn, p, q):
        # Catalogue of downloadable questionnaire / proposal-form PDFs.
        catalogue_path = os.path.join(FRONTEND_DIR, "forms", "forms_catalogue.json")
        try:
            with open(catalogue_path) as fh:
                forms = json.load(fh)
        except (OSError, json.JSONDecodeError):
            forms = []
        # Only advertise files that actually exist on disk.
        for f in forms:
            f["available"] = os.path.isfile(os.path.join(FRONTEND_DIR, "forms", f["file"]))
        return dict(forms=forms, disclaimer=catalogue.DISCLAIMER,
                    model_version=pricing_v2.MODEL_VERSION)

    def h_config_get(self, conn, p, q):
        self._user(conn, "admin")
        rows = conn.execute("SELECT * FROM config").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def h_pricing_params(self, conn, p, q):
        """The V2 parameter file, read-only. Changes go through the file so every value keeps its provenance."""
        self._user(conn, "admin")
        return dict(path="kyh-cyber-insurance/app/pricing_v2_params.json", params=pricing_v2.load_params())

    def h_config_put(self, conn, p, q):
        user = self._user(conn, "admin")
        b = self._body()
        for k, v in b.items():
            if get_config(conn, k) is None:
                raise ApiError("UNKNOWN_CONFIG_KEY", f"Unknown config key {k}", field=k)
            old = get_config(conn, k)
            if k == "warranty_gate_mode":
                if v not in ("WARN", "BLOCK"):
                    raise ApiError("INVALID_CONFIG", "warranty_gate_mode must be WARN or BLOCK",
                                   field=k)
            else:
                v = security.clean_number(v, k, 0)
            set_config(conn, k, v)
            audit.log(conn, user["name"], "MODEL_CONFIGURATION_CHANGED", "CONFIG", k,
                      old_value=old, new_value=v)
        return dict(ok=True,
                    note="Model assumptions changed. Historical calculations retain their "
                         "own snapshots and model version and are unaffected.")

    def h_control_put(self, conn, p, q):
        user = self._user(conn, "admin")
        b = self._body()
        old = conn.execute("SELECT * FROM controls WHERE control_id=?", (p["id"],)).fetchone()
        if not old:
            raise ApiError("UNKNOWN_CONTROL", "No such control", 404)
        fields = {}
        for f in ("pricing_weight", "failure_effect", "unknown_effect"):
            if f in b:
                fields[f] = security.clean_number(b[f], f, 0, 1)
        if "grace_period_days" in b:
            fields["grace_period_days"] = int(security.clean_number(
                b["grace_period_days"], "grace_period_days", 0, 365))
        if "coverage_effect" in b:
            fields["coverage_effect"] = security.clean_str(b["coverage_effect"],
                                                           "coverage_effect", 300,
                                                           required=False) or ""
        if not fields:
            raise ApiError("NO_FIELDS", "Nothing to update")
        sets = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE controls SET {sets} WHERE control_id=?",
                     (*fields.values(), p["id"]))
        audit.log(conn, user["name"], "MODEL_CONFIGURATION_CHANGED", "CONTROL", p["id"],
                  old_value={k: old[k] for k in fields}, new_value=fields)
        return dict(ok=True)

    def h_sectors_put(self, conn, p, q):
        user = self._user(conn, "admin")
        b = self._body()
        for sector, freq in b.items():
            old = conn.execute("SELECT base_frequency FROM sectors WHERE sector=?",
                               (sector,)).fetchone()
            if not old:
                raise ApiError("UNKNOWN_SECTOR", f"Unknown sector {sector}", field=sector)
            conn.execute("UPDATE sectors SET base_frequency=? WHERE sector=?",
                         (security.clean_number(freq, sector, 0, 1), sector))
            audit.log(conn, user["name"], "MODEL_CONFIGURATION_CHANGED", "SECTOR", sector,
                      old_value=old["base_frequency"], new_value=freq)
        return dict(ok=True)


def make_server(host="127.0.0.1", port=8000):
    init_db()
    return ThreadingHTTPServer((host, port), Handler)
