/* Beretta frontend — vanilla JS. All pricing logic lives on the server;
   this file only renders what the engines return. */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const state = { tokens: null, role: "UNDERWRITER", meta: null, company: null, tab: "intake", lastCalc: {} };

const fmtINR = n => n == null ? "—" : "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const fmtPct = n => (n >= 0 ? "+" : "") + (100 * n).toFixed(1) + "%";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dt = s => s ? String(s).replace("T", " ").replace(/\.\d+/, "").replace(/(\+.*|Z)$/, "") + " UTC" : "—";

/* Display labels. API and database values stay exactly as named; only what is shown is friendlier.
   SIMULATED is never relabelled. */
const LABELS = {
  MET: "Met", IN_GRACE: "In grace", BREACHED: "Breached", REMEDIATED: "Remediated",
  PASS: "Pass", FAIL: "Fail", PARTIAL: "Partial", UNKNOWN: "Unknown",
  DRAFT: "Draft", QUOTED: "Quoted", BOUND: "Bound",
  ELIGIBLE: "Eligible", CONDITIONALLY_ELIGIBLE: "Conditionally eligible", INELIGIBLE: "Ineligible",
  ONLINE: "Online", UNVERIFIED: "Unverified", SILENT: "Silent", SILENT_PASS: "Silent pass",
  NOT_OBSERVABLE: "Not observable", NOT_SUPPORTED: "Not supported", NOT_APPLICABLE: "Not applicable",
  NO_DATA: "No data", ASSESSED: "Assessed", LINKED: "Linked", ERROR: "Error", SIMULATED: "SIMULATED",
  VERIFIED: "Verified", STATED: "Stated", NOT_WORKING: "Not working",
  CREDENTIAL: "Credential", WEAKNESS: "Weakness", EXECUTION: "Execution",
};
const label = s => LABELS[s] || String(s ?? "—").replace(/_/g, " ").toLowerCase().replace(/^./, c => c.toUpperCase());
const pill = (s, text) => `<span class="pill ${esc(s)}">${esc(text ?? label(s))}</span>`;

/* What each warranty state means for the insured, in plain words. */
const STATE_MEANING = {
  MET: "The control is in place. Cover applies as written.",
  IN_GRACE: "The control has lapsed. The insured has until the grace period ends to fix it.",
  BREACHED: "The grace period ended without a fix. The coverage consequence below now applies.",
  REMEDIATED: "The control was restored after a breach. Normal cover is back.",
};

const EV_LABEL = { DECLARED: "Declared", DOCUMENTED: "Documented", TESTED: "Tested", TECHNICALLY_OBSERVED: "Technically observed" };
const ladder = `<span class="ladder" aria-hidden="true"><i></i><i></i><i></i><i></i></span>`;
const evTag = (strength, extra = "") =>
  `<span class="ev static ${esc(strength)}" title="${esc(strength)}">${ladder}${esc(EV_LABEL[strength] || strength)}${extra}</span>`;

function toast(msg, isError = false) {
  const t = document.createElement("div");
  t.className = "toast" + (isError ? " error" : "");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), isError ? 6000 : 3500);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.tokens) headers["X-Auth-Token"] = state.tokens[state.role];
  const resp = await fetch(path, { ...opts, headers });
  let data = {};
  try { data = await resp.json(); } catch (_) { /* empty body */ }
  if (!resp.ok) {
    const msg = data.message ? `${data.error}: ${data.message}` : `HTTP ${resp.status}`;
    throw Object.assign(new Error(msg), { code: data.error, payload: data });
  }
  return data;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });
const put = (path, body) => api(path, { method: "PUT", body: JSON.stringify(body) });

/* ------------------------------------------------ provenance popover */
function showPopover(html) {
  const backdrop = document.createElement("div");
  backdrop.className = "popover-backdrop";
  backdrop.innerHTML = `<div class="popover" role="dialog" aria-modal="true">${html}
    <div class="btnrow"><button class="btn secondary" data-close>Close</button></div></div>`;
  const close = () => { backdrop.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = e => { if (e.key === "Escape") close(); };
  backdrop.addEventListener("click", e => {
    if (e.target === backdrop || e.target.hasAttribute("data-close")) close();
  });
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);
  backdrop.querySelector("[data-close]").focus();
}

function provenanceHTML(ctrl) {
  const src = (ctrl.sources || []).map(s => `
    <div class="srcline">
      <div class="head"><span><b>${esc(s.source_type)}</b> · value <b>${esc(s.value)}</b></span>${evTag(s.evidence_strength)}</div>
      <span class="mono">Locator: ${esc(s.source_locator || "—")} · Observed ${esc(dt(s.observed_at))} · ${esc(s.observation_id)}</span>
      ${s.notes ? `<br><span class="note">${esc(s.notes)}</span>` : ""}
    </div>`).join("") || `<p class="empty">No observations yet, so this control is priced as unknown.</p>`;
  return `<h4>${esc(ctrl.name)}</h4>
    <p class="note" style="margin:0 0 14px">Where this value came from. The strongest evidence wins; between equal strengths, the most recent observation wins.</p>
    <p style="margin:0 0 12px">Resolved status ${pill(ctrl.status)}
       ${ctrl.conflict ? '<span class="conflict">Sources disagree</span>' : ""}</p>
    ${src}`;
}

function evChip(ctrl) {
  if (!ctrl.evidence_strength) return `<button type="button" class="ev none" data-prov>${ladder}No evidence</button>`;
  return `<button type="button" class="ev ${esc(ctrl.evidence_strength)}" data-prov title="${esc(ctrl.evidence_strength)}: open the source trail">${ladder}${esc(EV_LABEL[ctrl.evidence_strength] || ctrl.evidence_strength)}<span class="src">${esc(ctrl.source_type)}</span></button>`;
}

/* ------------------------------------------------ bootstrap + router */
async function boot() {
  state.tokens = await api("/api/demo/tokens");
  state.meta = await api("/api/meta");
  $("#roleSelect").value = state.role;
  await loadMe();
  $("#roleSelect").addEventListener("change", async e => { state.role = e.target.value; await loadMe(); route(); });
  const side = $("#side"), toggle = $("#navToggle");
  const setNav = open => { side.classList.toggle("open", open); toggle.setAttribute("aria-expanded", String(open)); toggle.textContent = open ? "Close" : "Menu"; };
  toggle.addEventListener("click", () => setNav(!side.classList.contains("open")));
  window.addEventListener("hashchange", () => { setNav(false); route(); });
  route();
}

function setActiveNav(view) {
  document.querySelectorAll("#nav a").forEach(a =>
    a.classList.toggle("active", a.dataset.view === view));
}

/* Who is viewing. An insured customer is read-only and sees only their own company. */
async function loadMe() {
  state.me = await api("/api/me");
  document.body.classList.toggle("customer", !!state.me.read_only);
}
const isCustomer = () => !!(state.me && state.me.read_only);

/* For a customer: drop everything staff-only from the rendered view and make every field read-only. */
function applyReadOnly(el) {
  if (!isCustomer()) return;
  el.querySelectorAll(".staff-only").forEach(x => x.remove());
  el.querySelectorAll("input, select, textarea").forEach(x => { x.disabled = true; });
}

async function route() {
  let hash = location.hash || "#/forms";
  const main = $("#main");
  main.innerHTML = `<p class="sub loading">Loading…</p>`;
  try {
    if (isCustomer()) {
      // staff screens are not available to a customer: send them to their own policy
      if (/^#\/(dashboard|audit|admin|companies\/?$)/.test(hash) || hash === "#/" || hash.startsWith("#/mine")) {
        const tab = hash.startsWith("#/mine/") ? hash.split("/")[2] : "";
        hash = `#/companies/${state.me.company_id}${tab ? "/" + tab : ""}`;
        if (!state.me.company_id) {
          main.innerHTML = `<h1>My policy</h1><p class="empty">No company is linked to this account yet.</p>`;
          return;
        }
      }
    }
    if (hash.startsWith("#/companies/")) {
      const [, , id, tab] = hash.split("/");
      state.tab = tab || "intake";
      setActiveNav(isCustomer() ? "mine" : "companies");
      await renderCompany(main, id);
    } else if (hash.startsWith("#/companies")) { setActiveNav("companies"); await renderCompanies(main); }
    else if (hash.startsWith("#/forms")) { setActiveNav("forms"); await renderForms(main); }
    else if (hash.startsWith("#/audit")) { setActiveNav("audit"); await renderAudit(main); }
    else if (hash.startsWith("#/admin")) { setActiveNav("admin"); await renderAdmin(main); }
    else if (hash.startsWith("#/regulatory")) { setActiveNav("regulatory"); await renderRegulatory(main); }
    else { setActiveNav("dashboard"); await renderDashboard(main); }
  } catch (e) {
    main.innerHTML = `<h1>Could not load this view</h1><div class="card"><p style="margin:0">${esc(e.message)}</p>
      <div class="btnrow"><button class="btn secondary" id="retry">Try again</button></div></div>`;
    $("#retry").addEventListener("click", route);
  }
}

/* ------------------------------------------------ dashboard */
async function renderDashboard(main) {
  const d = await api("/api/dashboard");
  const bad = d.warranties_breached || 0, grace = d.warranties_in_grace || 0;
  const finding = bad || grace
    ? `${bad} warrant${bad === 1 ? "y" : "ies"} breached and ${grace} in grace across ${d.active_policies} bound polic${d.active_policies === 1 ? "y" : "ies"}. Premiums stay as bound; open the company's Monitoring tab to see what lapsed.`
    : d.active_policies
      ? `No warranty is in grace or breached on the ${d.active_policies} bound polic${d.active_policies === 1 ? "y" : "ies"}.`
      : "No policy is bound yet. Work a company through intake and quote to bind the first one.";
  const totalBound = d.policies.reduce((s, p) => s + (Number(p.bound_premium) || 0), 0);
  const anyBound = d.policies.some(p => p.bound_premium != null);
  main.innerHTML = `
    <h1>Portfolio</h1>
    <p class="sub">${esc(finding)}</p>
    <div class="kpirow">
      <div class="kpis" aria-label="Book">
        ${kpi("Companies", d.companies)}
        ${kpi("Bound policies", d.active_policies)}
        ${kpi("Pending underwriting", d.pending_underwriting)}
        ${kpi("Premium calculations", d.quotes_issued)}
      </div>
      <div class="kpis" aria-label="Warranties">
        ${kpi("Warranties breached", bad, bad ? "bad" : "zero")}
        ${kpi("Warranties in grace", grace, grace ? "warn" : "zero")}
        ${kpi("Average posture", d.avg_posture_score == null ? "—" : d.avg_posture_score + "%", "", "Share of controls met")}
      </div>
    </div>
    <h2>Policies</h2>
    <div class="card"><div class="tablewrap"><table><thead><tr>
      <th>Company</th><th>Sector</th><th>Policy</th><th>Status</th><th class="num">Bound premium</th></tr></thead>
      <tbody>${d.policies.map(p => `
        <tr class="clickable" data-go="#/companies/${esc(p.company_id)}" tabindex="0">
          <td><b>${esc(p.name)}</b></td><td>${esc(p.sector)}</td>
          <td class="mono">${esc(p.policy_id)}</td>
          <td>${pill(p.status)}</td>
          <td class="num">${p.bound_premium == null ? '<span class="note">—</span>' : `<b>${fmtINR(p.bound_premium)}</b>`}</td></tr>`).join("")}
        ${anyBound ? `<tr><td colspan="4" class="note">Total bound premium</td><td class="num"><b>${fmtINR(totalBound)}</b></td></tr>` : ""}
      </tbody></table></div></div>
    <h2>Recent audit events</h2>
    <div class="card"><div class="tablewrap">${auditTable(d.recent_audit)}</div></div>
    <p class="note" style="margin-top:16px">${esc(state.meta.assumptions_note)}</p>`;
  bindRows(main);
}
const kpi = (k, v, cls = "", s = "") =>
  `<div class="kpi"><div class="k">${esc(k)}</div><div class="v ${cls}">${esc(v ?? "—")}</div>${s ? `<div class="s">${esc(s)}</div>` : ""}</div>`;
function bindRows(el) {
  el.querySelectorAll("[data-go]").forEach(r => {
    r.addEventListener("click", () => location.hash = r.dataset.go);
    r.addEventListener("keydown", e => { if (e.key === "Enter") location.hash = r.dataset.go; });
  });
}

/* ------------------------------------------------ companies list + create */
async function renderCompanies(main) {
  const d = await api("/api/companies");
  main.innerHTML = `
    <h1>Companies</h1>
    <p class="sub">${d.companies.length} compan${d.companies.length === 1 ? "y" : "ies"} on the book. Each one moves through intake, quote, bind and monitoring.</p>
    <div class="grid split">
      <div class="card"><table><thead><tr><th>Company</th><th>Sector</th><th>Policy status</th></tr></thead>
      <tbody>${d.companies.map(c => `
        <tr class="clickable" data-go="#/companies/${esc(c.company_id)}" tabindex="0">
          <td><b>${esc(c.name)}</b></td><td>${esc(c.sector)}</td>
          <td>${pill(c.policy_status)}</td></tr>`).join("") || `<tr><td colspan="3"><p class="empty">No companies yet. Onboard the first one on the right.</p></td></tr>`}
      </tbody></table></div>
      <div class="card">
        <h3>Onboard a company</h3>
        <label class="f" for="ncName">Name</label><input id="ncName" maxlength="120">
        <label class="f" for="ncNic">NIC 2008 code</label>
        <input id="ncNic" inputmode="numeric" maxlength="5" placeholder="62" aria-describedby="ncNicHelp">
        <p class="note" id="ncNicHelp" style="margin-top:6px">The first two digits (the division) set the rating sector. <span id="ncNicSector"></span></p>
        <div class="grid cols-2" style="column-gap:12px;row-gap:0">
          <div><label class="f" for="ncRev">Annual turnover (₹)</label><input id="ncRev" type="number" min="0" value="500000000"></div>
          <div><label class="f" for="ncYears">Years in operation</label><input id="ncYears" type="number" min="0" value="10"></div>
          <div><label class="f" for="ncLimit">Overall limit (₹)</label><input id="ncLimit" type="number" min="1" value="20000000"></div>
          <div><label class="f" for="ncRet">Retention per claim (₹)</label><input id="ncRet" type="number" min="0" value="100000"></div>
        </div>
        <label class="f checkline"><input type="checkbox" id="ncReg"> Regulated by RBI or SEBI</label>
        <div class="grid cols-2" style="column-gap:12px;row-gap:0">
          <div><label class="f" for="ncEmp">Employees</label><input id="ncEmp" type="number" min="0" value="200"></div>
          <div><label class="f" for="ncGeo">Geography</label><input id="ncGeo" value="India"></div>
        </div>
        <p class="note" style="margin-top:6px">Employees are kept for the record; V2 does not price them.</p>
        <div class="btnrow"><button class="btn" id="ncCreate">Create company</button></div>
      </div>
    </div>`;
  bindRows(main);
  $("#ncNic").addEventListener("input", e => { $("#ncNicSector").textContent = nicSector(e.target.value); });
  $("#ncCreate").addEventListener("click", async () => {
    try {
      const r = await post("/api/companies", {
        name: $("#ncName").value, nic_code: $("#ncNic").value,
        annual_revenue_inr: $("#ncRev").value, years_in_operation: $("#ncYears").value,
        regulated_rbi_sebi: $("#ncReg").checked, limit_total_inr: $("#ncLimit").value,
        retention_inr: $("#ncRet").value, employee_count: $("#ncEmp").value,
        geography: $("#ncGeo").value });
      toast("Company created. Agent token issued — shown in the Intake tab.");
      location.hash = `#/companies/${r.company_id}`;
    } catch (e) { toast(e.message, true); }
  });
}

/* NIC 2008 division -> pricing V2 rating sector (the table lives in pricing_v2_params.json). */
function nicSector(code) {
  const div = parseInt(String(code || "").slice(0, 2), 10);
  if (!div && div !== 0) return "";
  const hit = (state.meta.v2.nic_sectors || []).find(([lo, hi]) => div >= lo && div <= hi);
  return hit ? `Division ${String(div).padStart(2, "0")} rates as ${hit[2]}.` : "Not mapped: priced at the global-average sector.";
}

/* ------------------------------------------------ company workspace */
async function renderCompany(main, id) {
  const [detail, postureResp] = await Promise.all([
    api(`/api/companies/${id}`), api(`/api/posture/${id}`)]);
  state.company = detail;
  const co = detail.company, pol = detail.policy;
  const posture = postureResp.posture;
  const bound = pol.status === "BOUND";
  const tabs = isCustomer()
    ? [["intake", "Your details"], ["quote", "Your premium"], ["monitoring", "Cover and monitoring"]]
    : [["intake", "Intake"], ["quote", "Quote and calculation"], ["monitoring", "Monitoring after bind"]];
  main.innerHTML = `
    ${isCustomer()
      ? `<p class="readonly-note"><b>View only.</b> This is what your insurer holds for ${esc(co.name)}. To change anything, contact your underwriter.</p>`
      : `<p class="note" style="margin:0 0 8px"><a href="#/companies">Companies</a> / ${esc(co.name)}</p>`}
    <div class="titlerow">
      <div>
        <h1>${esc(co.name)} ${pill(pol.status)}</h1>
        <p class="facts">
          <span>${co.nic_code ? `NIC ${esc(co.nic_code)} · ${esc(co.sector)}` : esc(co.sector)}</span>
          <span>${fmtINR(co.annual_revenue_inr)} turnover</span>
          ${co.years_in_operation != null ? `<span>${esc(co.years_in_operation)} years in operation</span>` : ""}
          ${co.regulated_rbi_sebi ? "<span>RBI/SEBI-regulated</span>" : ""}<span>${esc(co.geography)}</span></p>
      </div>
      ${bound ? `<div class="kpis" style="min-width:240px"><div class="kpi"><div class="k">Bound premium</div>
        <div class="v money">${fmtINR(pol.bound_premium)}</div><div class="s">Fixed at inception</div></div></div>` : ""}
    </div>
    <div class="tabs" role="tablist">${tabs.map(([k, l]) =>
      `<button role="tab" aria-selected="${state.tab === k}" data-tab="${k}" class="${state.tab === k ? "active" : ""}">${l}</button>`).join("")}</div>
    <div id="tabBody"></div>`;
  main.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => {
    location.hash = `#/companies/${id}/${b.dataset.tab}`;
  }));
  const body = $("#tabBody");
  if (state.tab === "quote") await renderQuoteTab(body, detail, posture);
  else if (state.tab === "monitoring") await renderMonitoringTab(body, detail);
  else renderIntakeTab(body, detail, posture);
  applyReadOnly(main);
}

/* ---------------- intake tab */
function renderIntakeTab(body, detail, posture) {
  const co = detail.company, pol = detail.policy;
  const bound = pol.status === "BOUND";
  const controls = state.meta.controls.filter(c => !c.monitoring_only);
  const priced = new Set([...Object.keys(state.meta.v2.frequency_controls), ...Object.keys(state.meta.v2.severity_controls)]);
  body.innerHTML = `
    <div class="stage inception"><b>Inception: gathering information</b>
      <span>Everything below feeds one risk dataset. Each value shows how strong its evidence is; select it to see the source trail.</span></div>
    <div class="grid cols-2">
      <div class="card">
        <h3>Classification <span class="note">what V2 rates on</span></h3>
        <div class="grid cols-2" style="column-gap:12px;row-gap:0">
          <div><label class="f" for="pfNic" style="margin-top:0">NIC 2008 code</label>
            <input id="pfNic" value="${esc(co.nic_code || "")}" inputmode="numeric" maxlength="5" ${bound ? "disabled" : ""}></div>
          <div><label class="f" for="pfRev" style="margin-top:0">Annual turnover (₹)</label>
            <input id="pfRev" type="number" min="0" value="${esc(co.annual_revenue_inr ?? "")}" ${bound ? "disabled" : ""}></div>
          <div><label class="f" for="pfYears">Years in operation</label>
            <input id="pfYears" type="number" min="0" value="${esc(co.years_in_operation ?? "")}" ${bound ? "disabled" : ""}></div>
          <div><label class="f checkline" style="margin-top:38px"><input type="checkbox" id="pfReg" ${co.regulated_rbi_sebi ? "checked" : ""} ${bound ? "disabled" : ""}> RBI- or SEBI-regulated</label></div>
        </div>
        <p class="note" id="pfNicSector">${esc(nicSector(co.nic_code)) || "No NIC code yet: the quote uses the global-average sector."}</p>
        ${bound ? '<p class="note">Locked: the policy is bound.</p>' : '<div class="btnrow staff-only"><button class="btn secondary" id="saveProfile">Save classification</button></div>'}
        <p class="note">Employees (${esc(co.employee_count)}) and geography (${esc(co.geography)}) are kept for the record but not priced.</p>
      </div>
      <div class="card">
        <h3>Endpoint monitoring</h3>
        ${detail.fleet ? `<table class="kv">
          <tr><td>Live monitoring</td><td>${pill("LINKED")} <span class="note">via ${esc(detail.fleet.collector_name)}</span></td></tr>
          <tr><td>Endpoints reporting</td><td>${esc(detail.fleet.fleet.reporting)} of ${esc(detail.fleet.fleet.declared)} declared</td></tr>
          <tr><td>Latest fleet roll-up</td><td><span class="mono">#${esc(detail.fleet.seq)}</span> · ${esc(dt(detail.fleet.received_at))}</td></tr>
        </table>
        <p class="note">Fleet results enter the risk dataset as ${evTag("TECHNICALLY_OBSERVED", '<span class="src">AGENT_FLEET</span>')} evidence. <a href="#/companies/${esc(co.company_id)}/monitoring">See the endpoints</a></p>
        <h3 style="margin-top:20px" class="staff-only">Legacy single-host agent</h3>` : ""}
        <table class="kv staff-only">
          <tr><td>Status</td><td>${detail.agent.connected ? pill("met", "Connected") : pill("unknown", "Never reported")}</td></tr>
          <tr><td>Endpoints</td><td>${detail.agent.endpoint_count}</td></tr>
          <tr><td>Last seen</td><td>${esc(dt(detail.agent.agents[0] && detail.agent.agents[0].last_seen))}</td></tr>
          <tr><td>Latest report</td><td class="mono">${detail.agent.latest_report ? esc(detail.agent.latest_report.report_id) + " · " + esc(dt(detail.agent.latest_report.received_at)) : "—"}</td></tr>
        </table>
        <p class="note staff-only">Deploy <span class="mono">agent/agent.py</span> with the company's agent token (see <span class="mono">data/demo_profiles.json</span> for seeded companies). Reports are immutable once received.</p>
      </div>
    </div>

    <h2>Policy structure ${bound ? '<span class="note">Locked: the policy is bound</span>' : ""}</h2>
    <div class="card">
      <div class="grid cols-2" style="column-gap:12px;row-gap:0;max-width:560px">
        <div><label class="f" for="polLimit" style="margin-top:0">Overall limit (₹)</label>
          <input id="polLimit" type="number" min="1" value="${esc(pol.limit_total_inr ?? "")}" ${bound ? "disabled" : ""}></div>
        <div><label class="f" for="polRet" style="margin-top:0">Retention per claim (₹)</label>
          <input id="polRet" type="number" min="0" value="${esc(pol.retention_inr ?? "")}" ${bound ? "disabled" : ""}></div>
      </div>
      ${bound ? "" : `<div class="btnrow staff-only"><button class="btn secondary" id="saveCov">Save policy structure</button></div>`}
      <p class="note">Each claim pays its loss above the retention, across all covers (${Object.values(state.meta.v2.heads || {}).map(esc).join(", ")}), up to the overall limit. Policy period ${esc(pol.period_start)} to ${esc(pol.period_end)}.</p>
    </div>

    <h2>Security questionnaire <span class="note">${controls.length} controls</span></h2>
    <div class="card"><div class="tablewrap">
      <table><thead><tr><th>Control</th><th>Tier</th><th>Resolved value</th><th>Evidence</th><th class="staff-only">Customer answer</th><th class="staff-only">Notes</th></tr></thead>
      <tbody>${controls.map(c => {
        const p = posture[c.control_id];
        return `<tr>
          <td>${esc(c.name)}${c.is_warranty ? ' <span class="pill tag">Warranty</span>' : ""}${priced.has(c.control_id) ? "" : ' <span class="pill tag">Not priced</span>'}</td>
          <td>${c.tier}</td>
          <td>${pill(p.status)}${p.conflict ? ' <span class="conflict">Sources disagree</span>' : ""}</td>
          <td data-ctrl="${esc(c.control_id)}">${evChip(p)}</td>
          <td class="staff-only"><select aria-label="Answer for ${esc(c.name)}" data-q="${esc(c.control_id)}" style="min-width:130px">
            <option value="">No change / don't know</option><option value="true">Yes</option>
            <option value="false">No</option><option value="partial">Partially</option></select>
            ${["CTRL-IRPLAN", "CTRL-BACKUP-TESTED"].includes(c.control_id) ? `
            <div class="note" style="margin-top:6px;display:flex;gap:10px;flex-wrap:wrap">
              <label><input type="checkbox" data-dim="${esc(c.control_id)}" data-d="exists" checked> exists</label>
              <label><input type="checkbox" data-dim="${esc(c.control_id)}" data-d="current" checked> current</label>
              <label><input type="checkbox" data-dim="${esc(c.control_id)}" data-d="tested"> tested</label>
            </div>` : ""}</td>
          <td class="staff-only"><input aria-label="Notes for ${esc(c.name)}" data-qn="${esc(c.control_id)}" maxlength="200" placeholder="Optional" style="min-width:140px"></td>
        </tr>`; }).join("")}
      </tbody></table></div>
      <div class="btnrow staff-only"><button class="btn" id="submitQ">Submit questionnaire answers</button>
        <span class="note">Answers enter as ${evTag("DECLARED")} evidence, the weakest strength. They never count the same as technical evidence.</span></div>
    </div>

    <div class="grid cols-2">
      <div class="card">
        <h3>Documents and evidence</h3>
        ${detail.documents.length ? `<div class="tablewrap"><table><thead><tr><th>Document</th><th>Category</th><th>Status</th><th>Default evidence</th></tr></thead>
          <tbody>${detail.documents.map(d => `<tr><td>${esc(d.filename)}<br><span class="mono">${esc(d.document_id)}</span></td>
            <td>${esc(d.category)}</td><td>${pill(d.assessment_status === "ASSESSED" ? "met" : "unknown", label(d.assessment_status))}</td>
            <td>${evTag(d.default_evidence_strength)}</td></tr>`).join("")}</tbody></table></div>`
        : `<p class="empty">No documents registered yet.</p>`}
        <div class="staff-only">
        <label class="f" for="docName">Register a document</label>
        <input id="docName" placeholder="backup-restore-test-2026.pdf" maxlength="120">
        <p class="note" style="margin-top:6px">Metadata only. Uploaded files are never opened or run.</p>
        <label class="f" for="docType">Document type</label>
        <select id="docType">${state.meta.document_types.map(t => `<option>${esc(t)}</option>`).join("")}</select>
        <div class="btnrow"><button class="btn secondary" id="regDoc">Register document</button></div>
        <h3 style="margin-top:28px">Assess a field from a document</h3>
        <label class="f" for="asDoc">Document</label>
        <select id="asDoc">${detail.documents.map(d => `<option value="${esc(d.document_id)}">${esc(d.filename)}</option>`).join("")}</select>
        <label class="f" for="asCtrl">Control</label>
        <select id="asCtrl">${controls.map(c => `<option value="${esc(c.control_id)}">${esc(c.name)}</option>`).join("")}</select>
        <label class="f" for="asVal">Value</label>
        <select id="asVal"><option value="true">Met</option><option value="false">Not met</option><option value="partial">Partial</option></select>
        <label class="f" for="asLoc">Where in the document</label>
        <input id="asLoc" maxlength="120" placeholder="Question IAM-04, or Page 14 §5.2" aria-describedby="asLocHelp">
        <p class="note" id="asLocHelp" style="margin-top:6px">Required. The locator is shown in the source trail.</p>
        <div class="btnrow"><button class="btn secondary" id="assessBtn">Record assessed value</button></div>
        </div>
      </div>
      <div class="stack">
        <div class="card">
          <h3>Claims history</h3>
          ${detail.claims.length ? `<table><thead><tr><th>Date</th><th>Type</th><th class="num">Loss</th><th>Material</th></tr></thead>
            <tbody>${detail.claims.map(c => `<tr><td>${esc(c.incident_date)}</td><td>${esc(c.incident_type)}<br><span class="note">${esc(label(c.status))}${c.remediation ? " · " + esc(c.remediation) : ""}</span></td>
              <td class="num">${fmtINR(c.loss_amount_inr)}</td>
              <td>${c.material == null ? '<span class="note">Inferred</span>' : (c.material ? "Yes" : "No")}</td></tr>`).join("")}</tbody></table>`
          : `<p class="empty">No prior incidents recorded.</p>`}
          <p class="note">Only <b>material</b> incidents in the last 3 years count: a loss above the retention, a DPDP or CERT-In notification, or a ransom decision. If not marked, it is inferred from the loss and the type.</p>
          <div class="staff-only">
          <div class="grid cols-2" style="column-gap:12px;row-gap:0">
            <div><label class="f" for="clDate">Incident date</label><input id="clDate" type="date"></div>
            <div><label class="f" for="clType">Type</label><input id="clType" maxlength="120" placeholder="Ransomware"></div>
            <div><label class="f" for="clLoss">Loss amount (₹)</label><input id="clLoss" type="number" min="0"></div>
            <div><label class="f" for="clStatus">Status</label><select id="clStatus"><option value="CLOSED">Closed</option><option value="OPEN">Open</option></select></div>
          </div>
          <label class="f" for="clMaterial">Material incident?</label>
          <select id="clMaterial"><option value="">Infer from loss and type</option><option value="true">Yes</option><option value="false">No</option></select>
          <div class="btnrow"><button class="btn secondary" id="addClaim">Record incident</button></div>
          </div>
        </div>
        <div class="card">
          <h3>Outside-in scan signals</h3>
          <p class="note" style="margin:-6px 0 12px">Imported from an external scan; Beretta does not scan anyone. A finding is evidence for the control it concerns, for example exposed RDP means secure configuration is not working.</p>
          ${detail.signals.length ? `<table><thead><tr><th>Signal</th><th>Evidence for</th><th>Detail</th></tr></thead>
            <tbody>${detail.signals.map(s => `<tr><td class="mono">${esc(s.signal_type)}</td>
              <td>${s.related_control_id ? `<span class="mono">${esc(s.related_control_id)}</span> ${pill(s.severity === "POSITIVE" ? "PASS" : "FAIL")}` : '<span class="note">—</span>'}</td>
              <td>${esc(s.detail || "")}</td></tr>`).join("")}</tbody></table>`
          : `<p class="empty">No signals recorded.</p>`}
          <div class="staff-only">
          <label class="f" for="sigType">Signal type</label><input id="sigType" maxlength="60" placeholder="EXPOSED_RDP">
          <label class="f" for="sigDetail">Detail</label><input id="sigDetail" maxlength="200">
          <div class="btnrow"><button class="btn secondary" id="addSig">Record signal</button></div>
          </div>
        </div>
      </div>
    </div>`;

  body.querySelectorAll("[data-ctrl]").forEach(td => {
    td.addEventListener("click", e => {
      if (e.target.closest("[data-prov]")) showPopover(provenanceHTML(posture[td.dataset.ctrl]));
    });
  });

  const cid = detail.company.company_id;
  if ($("#saveCov")) $("#saveCov").addEventListener("click", async () => {
    try { await put(`/api/policies/${detail.policy.policy_id}/coverages`, {
        limit_total_inr: $("#polLimit").value, retention_inr: $("#polRet").value });
      toast("Policy structure saved."); route(); } catch (e) { toast(e.message, true); }
  });
  if ($("#pfNic")) $("#pfNic").addEventListener("input", e => { $("#pfNicSector").textContent = nicSector(e.target.value); });
  if ($("#saveProfile")) $("#saveProfile").addEventListener("click", async () => {
    try { await put(`/api/companies/${cid}`, { nic_code: $("#pfNic").value, annual_revenue_inr: $("#pfRev").value,
        years_in_operation: $("#pfYears").value, regulated_rbi_sebi: $("#pfReg").checked });
      toast("Classification saved."); route(); } catch (e) { toast(e.message, true); }
  });
  $("#submitQ").addEventListener("click", async () => {
    const answers = [];
    body.querySelectorAll("[data-q]").forEach(sel => {
      if (!sel.value) return;
      const ctrl = sel.dataset.q;
      const a = { control_id: ctrl, value: sel.value,
                  notes: (body.querySelector(`[data-qn="${ctrl}"]`) || {}).value || null };
      const dims = {};
      body.querySelectorAll(`[data-dim="${ctrl}"]`).forEach(cb => dims[cb.dataset.d] = cb.checked);
      if (Object.keys(dims).length) a.dims = dims;
      answers.push(a);
    });
    if (!answers.length) return toast("Choose an answer for at least one control.", true);
    try { const r = await post("/api/questionnaires", { company_id: cid, answers });
      toast(`Recorded ${r.recorded} questionnaire observations.`); route(); }
    catch (e) { toast(e.message, true); }
  });
  $("#regDoc").addEventListener("click", async () => {
    try { await post("/api/documents", { company_id: cid, document_type: $("#docType").value, filename: $("#docName").value });
      toast("Document registered."); route(); } catch (e) { toast(e.message, true); }
  });
  if ($("#assessBtn")) $("#assessBtn").addEventListener("click", async () => {
    try { await post(`/api/documents/${$("#asDoc").value}/assess`,
        { control_id: $("#asCtrl").value, value: $("#asVal").value, source_locator: $("#asLoc").value });
      toast("Assessed value recorded with its locator."); route(); } catch (e) { toast(e.message, true); }
  });
  $("#addClaim").addEventListener("click", async () => {
    try { await post("/api/claims", { company_id: cid, incident_date: $("#clDate").value,
        incident_type: $("#clType").value, loss_amount_inr: $("#clLoss").value || null,
        status: $("#clStatus").value, material: $("#clMaterial").value || null }); toast("Incident recorded."); route(); }
    catch (e) { toast(e.message, true); }
  });
  $("#addSig").addEventListener("click", async () => {
    try { await post("/api/outside-in", { company_id: cid, signal_type: $("#sigType").value,
        detail: $("#sigDetail").value }); toast("Signal recorded."); route(); }
    catch (e) { toast(e.message, true); }
  });
}

/* ---------------- quote tab */
async function renderQuoteTab(body, detail, posture) {
  const pol = detail.policy;
  const bound = pol.status === "BOUND";
  body.innerHTML = `
    <div class="stage inception"><b>Inception pricing</b>
      <span>${isCustomer() ? "Your premium is set once, when the policy is bound. Monitoring afterwards never changes it."
        : "The engine is deterministic: the same inputs always give the same premium."}</span></div>
    ${bound ? `<div class="callout"><b>This policy is bound, so it is never re-priced.</b> The engine refuses to recalculate it. Warranty status after bind is on the Monitoring tab. The bound calculation below can still be reproduced from its snapshot.</div>`
      : `<div class="btnrow staff-only" style="margin-top:0"><button class="btn" id="calcBtn">Calculate premium</button>
          <span class="note">${esc(state.meta.assumptions_note)}</span></div>`}
    <h2>Calculation history</h2>
    <div class="card"><div class="tablewrap">
      ${detail.calculations.length ? `<table><thead><tr><th>Calculation</th><th>When</th><th>Model</th><th>Eligibility</th><th class="num">Technical premium</th><th></th></tr></thead>
      <tbody>${detail.calculations.map(c => `<tr>
        <td><span class="mono">${esc(c.calculation_id)}</span>${pol.bound_calculation_id === c.calculation_id ? " " + pill("BOUND") : ""}</td>
        <td>${esc(dt(c.calculated_at))}</td><td class="mono">${esc(c.model_version)}</td>
        <td>${pill(c.eligibility)}</td>
        <td class="num"><b>${fmtINR(c.technical_premium)}</b></td>
        <td class="num"><button class="btn secondary small" data-view-calc="${esc(c.calculation_id)}">View</button></td></tr>`).join("")}
      </tbody></table>` : `<p class="empty">${isCustomer() ? "Your underwriter has not quoted this policy yet." : "No calculations yet. Calculate a premium to see the full working."}</p>`}
    </div></div>
    <div id="calcView"></div>`;

  if ($("#calcBtn")) $("#calcBtn").addEventListener("click", async () => {
    try {
      const r = await post("/api/quote", { policy_id: pol.policy_id });
      toast("Premium calculated and persisted with input snapshot.");
      renderCalculation($("#calcView"), r, detail, posture, true);
      detail.calculations.unshift({ calculation_id: r.calculation_id, calculated_at: r.calculated_at,
        technical_premium: r.technical_premium, eligibility: r.eligibility.status, model_version: r.model_version });
    } catch (e) { toast(e.message, true); }
  });
  body.querySelectorAll("[data-view-calc]").forEach(b => b.addEventListener("click", async () => {
    const r = await api(`/api/quote/${b.dataset.viewCalc}`);
    renderCalculation($("#calcView"), r, detail, posture, !bound && b.dataset.viewCalc === detail.calculations[0].calculation_id);
    $("#calcView").scrollIntoView({ behavior: "smooth" });
  }));
  if (detail.calculations.length) {
    const r = await api(`/api/quote/${detail.calculations[0].calculation_id}`);
    renderCalculation($("#calcView"), r, detail, posture,
      !bound && true);
  }
}

function renderCalculation(el, r, detail, livePosture, canBind) {
  if (r.customer_view) return renderCalculationCustomer(el, r);
  if (r.model_version === "UNDERWRITING_MODEL_V2") return renderCalculationV2(el, r, detail, canBind);
  return renderCalculationV1(el, r, detail, livePosture, canBind);
}

/* The insured's view of a quote: the price, what stands between them and cover, and what would lower it.
   The server sends only these fields to a customer (api._customer_quote). */
function renderCalculationCustomer(el, r) {
  const elig = r.eligibility || {}, ev = r.evidence || {}, st = r.statuses || {};
  const ids = Object.keys(st).sort((a, b) => ctrlName(a).localeCompare(ctrlName(b)));
  const saves = (r.what_if || []).filter(w => w.saving_inr > 0);
  const eligText = { ELIGIBLE: "You can be offered cover at this premium.",
    CONDITIONALLY_ELIGIBLE: "Cover can be offered, on the condition below.",
    INELIGIBLE: "Cover cannot be offered yet. The reason is below; your underwriter will tell you what to provide." }[elig.status]
    || "Your underwriter is reviewing this quote.";
  el.innerHTML = `
    <h2 style="margin-top:36px">Quote <span class="mono">${esc(r.calculation_id)}</span> <span class="note">${esc(dt(r.calculated_at))}</span></h2>
    <div class="grid cols-2 stretch">
      <div class="card"><h3>Your premium</h3>
        <div class="kpi" style="padding:0"><div class="k">Premium before tax</div>
          <div class="v money lead" style="font-size:30px">${fmtINR(r.technical_premium)}</div>
          ${r.total_premium ? `<div class="s">+ GST ${Math.round(r.gst_rate * 100)}% ${fmtINR(r.gst)} = <b>${fmtINR(r.total_premium)}</b> payable</div>` : ""}</div></div>
      <div class="card"><h3>Can you be covered?</h3>
        <p style="margin:0 0 8px">${pill(elig.status)}</p>
        <p class="note" style="margin:0">${esc(eligText)}</p>
        ${elig.status !== "ELIGIBLE" && elig.reason ? `<p class="note">${esc(elig.reason.replace(/CTRL-[A-Z-]+/g, id => ctrlName(id)))}</p>` : ""}</div>
    </div>
    <div class="callout">Your premium reflects your sector, your turnover, your claims history and how strongly each security control is evidenced.${saves.length ? " Showing that the controls below work would lower it." : ""}</div>
    ${r.policy_structure ? `<p class="note">Retention per claim ${fmtINR(r.policy_structure.retention_inr)} · overall limit ${fmtINR(r.policy_structure.limit_total_inr)}${r.classification && r.classification.sector ? " · sector " + esc(r.classification.sector) : ""}${r.claims && r.claims.incidents != null ? " · material incidents in the last 3 years: " + esc(r.claims.incidents) : ""}.</p>` : ""}

    ${saves.length ? `<h2>How you could lower it</h2>
    <div class="card"><table class="whatif"><thead><tr><th>Show this control works</th><th>Now</th><th class="num">Premium after</th><th class="num">Saving</th></tr></thead>
      <tbody>${saves.map(w => `<tr><td>${esc(ctrlName(w.control_id))}</td><td>${pill(w.current_status)}</td>
        <td class="num">${fmtINR(w.premium_if_verified)}</td><td class="num"><b style="color:var(--met)">${fmtINR(w.saving_inr)}</b></td></tr>`).join("")}</tbody></table>
      <p class="note">A control counts as verified when the monitoring agent observes it, or an independent report or test confirms it. Your answer alone counts for less.</p></div>` : ""}

    ${ids.length ? `<h2>Your security controls</h2>
    <div class="card"><div class="tablewrap"><table>
      <thead><tr><th>Control</th><th>How we see it</th><th>Best evidence we hold</th></tr></thead>
      <tbody>${ids.map(id => { const e = ev[id] || {};
        return `<tr><td>${esc(ctrlName(id))}${(state.meta.v2.warranties || []).includes(id) ? ' <span class="pill tag">Warranty</span>' : ""}</td>
          <td>${pill(st[id])}</td>
          <td>${e.evidence_strength ? evTag(e.evidence_strength) : '<span class="note">None</span>'}</td></tr>`; }).join("")}
      </tbody></table></div>
      <p class="note">A warranty is a control you must keep in place while the policy runs. Monitoring checks it; it never changes your premium.</p></div>` : ""}`;
}

const PERIL_LABEL = { RANSOMWARE: "Ransomware", BEC: "Business email compromise", FTF: "Funds transfer fraud",
  MISC_FIRST_PARTY: "Other first-party", THIRD_PARTY: "Third-party liability" };
const ctrlName = id => (state.meta.controls.find(c => c.control_id === id) || {}).name || id;
const fmtX = n => n == null ? "—" : "×" + Number(n).toFixed(3);
const fmtFreq = n => (100 * n).toFixed(3) + "%";

/* Pricing V2: frequency x severity per peril, controls with evidence status, claims credibility, TLR, GST. */
function renderCalculationV2(el, r, detail, canBind) {
  const c = r.classification, el2 = r.loadings, refer = r.referral, elig = r.eligibility;
  const bindable = canBind && elig.status !== "INELIGIBLE";
  // every priced control once, with its frequency and severity multipliers
  const ctl = {};
  for (const p of r.perils) for (const x of p.control_detail.controls)
    ctl[x.control_id] = Object.assign(ctl[x.control_id] || { perils: [] }, { status: x.status, freq: x.multiplier, stage: x.stage, source: x.source, tag: x.tag }),
    ctl[x.control_id].perils.push(PERIL_LABEL[p.peril]);
  for (const k of Object.keys(r.severity_controls || {})) for (const x of r.severity_controls[k].controls)
    ctl[x.control_id] = Object.assign(ctl[x.control_id] || { perils: [] }, { status: x.status, sev: x.multiplier });
  const ev = r.evidence || {};
  const rows = Object.entries(ctl).sort((a, b) => Math.abs(Math.log(b[1].freq || b[1].sev || 1)) - Math.abs(Math.log(a[1].freq || a[1].sev || 1)));
  const maxSplit = el2.split_inr.expected_loss + el2.split_inr.expenses + el2.split_inr.profit_risk_reinsurance;
  const seg = (v, cls, lbl) => `<div class="seg ${cls}" style="flex:${Math.max(v, 0.0001)}" title="${esc(lbl)}"></div>`;

  el.innerHTML = `
    <div class="titlerow" style="margin-top:36px;align-items:center">
      <h2 style="margin:0">Calculation <span class="mono">${esc(r.calculation_id)}</span> <span class="note">model ${esc(r.model_version)}</span></h2>
    </div>
    <div class="grid cols-3 stretch" style="margin-top:12px">
      <div class="card"><h3>Premium</h3>
        <div class="kpi" style="padding:0"><div class="k">Technical premium</div>
          <div class="v money lead" style="font-size:30px">${fmtINR(r.technical_premium)}</div>
          <div class="s">+ GST ${Math.round(r.gst_rate * 100)}% ${fmtINR(r.gst)} = <b>${fmtINR(r.total_premium)}</b> payable</div></div>
        ${bindable ? `${refer.required ? `<label class="f checkline"><input type="checkbox" id="refOk"> I approve this referral as underwriter</label>` : ""}
          <div class="btnrow"><button class="btn" id="bindBtn">Bind policy at ${fmtINR(r.technical_premium)}</button></div>` : ""}
        ${canBind && elig.status === "INELIGIBLE" ? `<p class="note">Binding is blocked: a warranty is not met or not evidenced.</p>` : ""}</div>
      <div class="card"><h3>Eligibility</h3>
        <p style="margin:0 0 8px">${pill(elig.status)}</p>
        <p class="note" style="margin:0">${esc(elig.reason.replace(/CTRL-[A-Z-]+/g, id => ctrlName(id)))}</p>
        <p class="note">${esc(elig.note)} Gate mode ${esc(label(elig.gate_mode))}.</p></div>
      <div class="card"><h3>Referral</h3>
        ${refer.required ? `<p style="margin:0 0 8px">${pill("grace", "Referred")}</p>
          <ul class="reasons">${refer.reasons.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
          <p class="note">The price stands; binding needs an underwriter's approval.</p>`
          : `<p style="margin:0 0 8px">${pill("met", "No referral")}</p><p class="note" style="margin:0">None of the referral triggers applies.</p>`}</div>
    </div>
    <div class="callout">${esc(r.explanation)}</div>

    <h2>Classification</h2>
    <div class="card"><div class="freqchain">
      <div class="step"><b>${esc(c.sector)}</b><span>${c.nic_matched ? `NIC ${esc(c.nic_code)}` : "NIC missing: global average"}</span></div>
      <div class="step"><b>USD ${(c.turnover_usd / 1e6).toFixed(1)}M</b><span>${fmtINR(c.turnover_inr)} at ₹${c.usd_inr}/USD</span></div>
      <div class="step"><b>${fmtX(c.turnover_freq_relativity)}</b><span>Turnover, frequency${c.frequency_zone ? " (transition zone)" : ""}</span></div>
      <div class="step"><b>${fmtX(c.turnover_sev_relativity)}</b><span>Turnover, severity${c.severity_zone ? " (transition zone)" : ""}</span></div>
      <div class="step"><b>${fmtX(c.sector_freq_relativity)}</b><span>Sector, frequency</span></div>
      <div class="step"><b>${fmtX(c.sector_sev_relativity)}</b><span>Sector, severity</span></div>
    </div></div>

    <h2>Perils <span class="note">frequency × expected payout = expected loss</span></h2>
    <div class="card"><div class="tablewrap"><table>
      <thead><tr><th>Peril</th><th class="num">Base frequency</th><th class="num">Turnover</th><th class="num">Sector</th>
        <th class="num">Controls</th><th class="num">Claims</th><th class="num">Frequency</th><th class="num">Mean loss</th>
        <th class="num">Expected payout</th><th class="num">Expected loss</th></tr></thead>
      <tbody>${r.perils.map(p => `<tr>
        <td>${esc(PERIL_LABEL[p.peril] || p.peril)}${p.control_detail.hit_ceiling ? ' <span class="pill breach">At ceiling</span>' : ""}</td>
        <td class="num">${fmtFreq(p.base_frequency)}</td><td class="num">${fmtX(p.turnover_relativity)}</td>
        <td class="num">${fmtX(p.sector_relativity)}</td>
        <td class="num" style="color:${p.control_multiplier < 1 ? "var(--met)" : p.control_multiplier > 1 ? "var(--breach)" : "inherit"}">${fmtX(p.control_multiplier)}</td>
        <td class="num">${fmtX(p.claims_multiplier)}</td><td class="num"><b>${fmtFreq(p.frequency)}</b></td>
        <td class="num">${fmtINR(p.severity_mean_inr)}</td><td class="num">${fmtINR(p.payout)}</td>
        <td class="num"><b>${fmtINR(p.expected_loss)}</b></td></tr>`).join("")}
        <tr><td><b>Total</b></td><td colspan="8"></td><td class="num"><b>${fmtINR(r.expected_loss)}</b></td></tr>
      </tbody></table></div>
      <p class="note">Losses are lognormal (σ ${r.perils[0].sigma}). Expected payout applies the ${fmtINR(r.policy_structure.retention_inr)} retention and the ${fmtINR(r.policy_structure.limit_total_inr)} overall limit.</p></div>

    <h2>Controls and evidence <span class="note">largest effect first</span></h2>
    <div class="card"><div class="tablewrap"><table>
      <thead><tr><th>Control</th><th>Evidence status</th><th>Best evidence</th><th>Stage</th><th class="num">Frequency ×</th><th class="num">Severity ×</th><th>Perils</th></tr></thead>
      <tbody>${rows.map(([id, x]) => {
        const e = ev[id] || {};
        return `<tr><td>${esc(ctrlName(id))}${(state.meta.v2.warranties || []).includes(id) ? ' <span class="pill tag">Warranty</span>' : ""}</td>
          <td>${pill(x.status)}</td>
          <td>${e.evidence_strength ? evTag(e.evidence_strength, `<span class="src">${esc(e.source_type)}</span>`) : '<span class="note">None</span>'}</td>
          <td>${esc(label(x.stage || "—"))}</td>
          <td class="num">${x.freq == null ? "—" : fmtX(x.freq)}</td>
          <td class="num">${x.sev == null ? "—" : fmtX(x.sev)}</td>
          <td class="note">${esc([...new Set(x.perils)].join(", ") || "Severity only")}</td></tr>`; }).join("")}
      </tbody></table></div>
      <p class="note">Verified evidence earns the control's full effect, stated evidence ${Math.round(state.meta.v2.credit_x * 100)}% of it; not working and unknown are priced as lacking the control. Controls in one attack stage overlap, so each extra one counts for half the one before.</p></div>

    ${(r.what_if || []).length ? `<h2>What verification would save</h2>
    <div class="card"><table class="whatif"><thead><tr><th>Verify</th><th>Now</th><th class="num">Premium if verified</th><th class="num">Saving</th></tr></thead>
      <tbody>${r.what_if.filter(w => w.saving_inr > 0).map(w => `<tr><td>${esc(ctrlName(w.control_id))}</td><td>${pill(w.current_status)}</td>
        <td class="num">${fmtINR(w.premium_if_verified)}</td><td class="num"><b style="color:var(--met)">${fmtINR(w.saving_inr)}</b></td></tr>`).join("")}</tbody></table>
      <p class="note">Each line re-prices this quote with only that control verified (for example by the monitoring agent or an independent report).</p></div>` : ""}

    <h2>Claims history</h2>
    <div class="card"><div class="freqchain">
      <div class="step"><b>${r.claims.incidents}</b><span>Material incidents, last 3 years</span></div>
      <div class="step"><b>${r.claims.years_used}</b><span>Years used</span></div>
      <div class="step"><b>${fmtFreq(r.claims.lambda_firm)}</b><span>Expected incidents a year, before history</span></div>
      <div class="op">→</div>
      <div class="step result"><b>${fmtX(r.claims.multiplier)}</b><span>(α + N) / (α + λT), α = ${r.claims.alpha}</span></div>
    </div></div>

    <h2>From expected loss to premium</h2>
    <div class="card">
      <div class="splitbar" aria-hidden="true">${seg(el2.split_inr.expected_loss, "el", "Expected loss")}${seg(el2.split_inr.expenses, "ex", "Expenses")}${seg(el2.split_inr.profit_risk_reinsurance, "mg", "Margin")}</div>
      <table class="kv" style="margin-top:12px">
        <tr><td>Expected loss${el2.trend ? ` × (1 + trend ${el2.trend})` : ""}</td><td class="num">${fmtINR(el2.split_inr.expected_loss)} <span class="note">${Math.round(el2.tlr * 100)}%</span></td></tr>
        <tr><td>Expenses, commission included (IRDAI cap)</td><td class="num">${fmtINR(el2.split_inr.expenses)} <span class="note">${Math.round(el2.expense_ratio * 100)}%</span></td></tr>
        <tr><td>Profit, risk margin, reinsurance and accumulation</td><td class="num">${fmtINR(el2.split_inr.profit_risk_reinsurance)} <span class="note">${Math.round(el2.margin_ratio * 100)}%</span></td></tr>
        <tr><td><b>Technical premium</b> = expected loss ÷ ${el2.tlr}</td><td class="num"><b>${fmtINR(r.technical_premium)}</b></td></tr>
        <tr><td>GST ${Math.round(r.gst_rate * 100)}%</td><td class="num">${fmtINR(r.gst)}</td></tr>
        <tr><td><b>Payable</b></td><td class="num"><b>${fmtINR(r.total_premium)}</b></td></tr>
      </table></div>

    <details class="assumptions"><summary>${r.assumptions.length} assumptions used in this quote</summary>
      <table><thead><tr><th>Parameter</th><th>Value</th><th>Sensitivity</th><th>Note</th></tr></thead>
      <tbody>${r.assumptions.map(a => `<tr><td class="mono">${esc(a.parameter)}</td><td class="mono">${esc(JSON.stringify(a.value)).slice(0, 80)}</td>
        <td class="mono">${esc(JSON.stringify(a.sensitivity ?? "—"))}</td><td class="note">${esc(a.locator || "")}</td></tr>`).join("")}</tbody></table>
    </details>
    <p class="note">${esc(r.assumptions_note)} The inputs and every parameter are saved with this quote, so it can be reproduced exactly.</p>`;

  if ($("#bindBtn")) $("#bindBtn").addEventListener("click", async () => {
    try {
      await post("/api/policies/bind", { policy_id: detail.policy.policy_id, calculation_id: r.calculation_id,
        referral_approved: !!($("#refOk") && $("#refOk").checked) });
      toast("Policy bound. The calculation snapshot is fixed and warranty monitoring has started.");
      location.hash = `#/companies/${detail.company.company_id}/monitoring`;
    } catch (e) { toast(e.message, true); }
  });
}

function renderCalculationV1(el, r, detail, livePosture, canBind) {
  const pm = r.posture_modifier, cm = r.claims_modifier, em = r.exposure_modifier;
  const snapshotPosture = (r.input_snapshot && r.input_snapshot.posture) || livePosture;
  const maxAmt = r.technical_premium;
  const bar = (v, cls = "") => `<div class="bar ${cls}" style="width:${Math.max(2, 100 * v / maxAmt)}%"></div>`;
  const loadRows = Object.entries(r.loadings).map(([k, v]) => {
    const amt = r.pure_premium * v;
    return `<div class="row"><div class="lbl">+ ${esc(k.replace("_", " "))} (${(v * 100).toFixed(0)}%)</div>${bar(amt, "load")}<div class="amt">${fmtINR(amt)}</div></div>`;
  }).join("");
  const bindable = canBind && r.eligibility.status !== "INELIGIBLE";

  el.innerHTML = `
    <div class="titlerow" style="margin-top:36px;align-items:center">
      <h2 style="margin:0">Calculation <span class="mono">${esc(r.calculation_id)}</span> <span class="note">model ${esc(r.model_version)}</span></h2>
    </div>
    <div class="grid cols-3 stretch" style="margin-top:12px">
      <div class="card"><h3>Technical premium</h3>
        <div class="kpi" style="padding:0"><div class="v money lead" style="font-size:30px">${fmtINR(r.technical_premium)}</div>
        <div class="s">${esc(r.company.sector)} · ${fmtINR(r.company.annual_revenue_inr)} revenue · ${esc(r.company.employee_count)} employees</div></div>
        ${bindable ? `<div class="btnrow"><button class="btn" id="bindBtn">Bind policy at ${fmtINR(r.technical_premium)}</button></div>` : ""}
        ${canBind && r.eligibility.status === "INELIGIBLE" ? `<p class="note">Binding is blocked: the risk is ineligible under the current warranty gating.</p>` : ""}</div>
      <div class="card"><h3>Eligibility</h3>
        <p style="margin:0 0 8px">${pill(r.eligibility.status)}</p>
        <p class="note" style="margin:0">${esc(r.eligibility.reason)}</p></div>
      <div class="card"><h3>Why this premium</h3>
        <p class="note" style="margin:0;color:var(--text)">${esc(r.explanation)}</p></div>
    </div>

    <h2>Frequency chain</h2>
    <div class="card"><div class="freqchain">
      <div class="step"><b>${r.sector_frequency.toFixed(2)}</b><span>Sector base frequency</span></div>
      <div class="op">×</div>
      <div class="step"><b>${pm.value.toFixed(4)}</b><span>Posture modifier${pm.clamped ? " (clamped)" : ""}</span></div>
      <div class="op">×</div>
      <div class="step"><b>${cm.value.toFixed(4)}</b><span>Claims: ${cm.incidents_in_window} incident(s) in ${cm.lookback_years} y</span></div>
      <div class="op">×</div>
      <div class="step"><b>${em.value.toFixed(4)}</b><span>Exposure: ${em.adverse_signals} adverse signal(s)</span></div>
      <div class="op">=</div>
      <div class="step result"><b>${r.adjusted_frequency.toFixed(4)}</b><span>Adjusted frequency</span></div>
    </div></div>

    <h2>Security posture <span class="note">every control, its evidence and its effect on frequency</span></h2>
    <div class="card"><div class="tablewrap"><table><thead><tr><th>Control</th><th>Status</th><th>Evidence</th><th class="num">Frequency effect</th><th>Why</th></tr></thead>
      <tbody>${pm.contributions.map(c => `
        <tr><td>${esc(c.name)}${c.is_warranty ? ' <span class="pill tag">Warranty</span>' : ""}</td>
        <td>${pill(c.status)}${c.conflict ? ' <span class="conflict">Sources disagree</span>' : ""}</td>
        <td data-provctrl="${esc(c.control_id)}">${evChip(c)}</td>
        <td class="num" style="color:${c.delta < 0 ? "var(--met)" : c.delta > 0 ? "var(--breach)" : "var(--muted)"}">${esc(c.delta_pct)}</td>
        <td class="note">${esc(c.reason)}${c.source_locator ? ` · <span class="mono">${esc(c.source_locator)}</span>` : ""}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="note">Posture modifier = 1 ${pm.raw - 1 >= 0 ? "+" : "−"} ${Math.abs(pm.raw - 1).toFixed(4)} = ${pm.raw.toFixed(4)}${pm.clamped ? `, clamped to [${pm.floor}, ${pm.cap}] → ${pm.value.toFixed(4)}` : ""}. Credits are scaled by evidence strength; failures count in full.</p></div>

    <h2>Expected losses by coverage head</h2>
    <div class="card"><div class="tablewrap"><table><thead><tr><th>Coverage head</th><th class="num">Limit</th><th class="num">Severity fraction</th>
      <th class="num">Expected loss per incident</th><th class="num">Annual (× ${r.adjusted_frequency.toFixed(4)})</th></tr></thead>
      <tbody>${r.coverage_contributions.map(c => `<tr><td>${esc(c.name)}</td>
        <td class="num">${fmtINR(c.limit_inr)}</td><td class="num">${c.severity_fraction}</td>
        <td class="num">${fmtINR(c.expected_loss_per_incident)}</td>
        <td class="num">${fmtINR(c.expected_annual_loss)}</td></tr>`).join("")}
      <tr><td><b>Total</b></td><td></td><td></td><td class="num"><b>${fmtINR(r.expected_loss_per_incident)}</b></td>
        <td class="num"><b>${fmtINR(r.pure_premium)}</b></td></tr></tbody></table></div></div>

    <h2>Premium waterfall</h2>
    <div class="card waterfall">
      <div class="row"><div class="lbl">Pure premium (expected annual loss)</div>${bar(r.pure_premium)}<div class="amt">${fmtINR(r.pure_premium)}</div></div>
      ${loadRows}
      <div class="row total"><div class="lbl">Technical premium (× ${(1 + r.loading_total).toFixed(2)})</div>${bar(r.technical_premium, "total")}<div class="amt">${fmtINR(r.technical_premium)}</div></div>
    </div>
    <p class="note">${esc(r.assumptions_note)} The input snapshot is saved, so this quote can be reproduced even if the company's data changes later.</p>`;

  el.querySelectorAll("[data-provctrl]").forEach(td => td.addEventListener("click", e => {
    if (e.target.closest("[data-prov]")) {
      const p = snapshotPosture[td.dataset.provctrl];
      if (p) showPopover(provenanceHTML(p));
    }
  }));
  if ($("#bindBtn")) $("#bindBtn").addEventListener("click", async () => {
    try {
      await post("/api/policies/bind", { policy_id: detail.policy.policy_id, calculation_id: r.calculation_id });
      toast("Policy bound. Calculation snapshot fixed; warranty monitoring started.");
      location.hash = `#/companies/${detail.company.company_id}/monitoring`;
    } catch (e) { toast(e.message, true); }
  });
}

/* ---------------- monitoring tab */
async function renderMonitoringTab(body, detail) {
  const pol = detail.policy;
  if (pol.status !== "BOUND") {
    body.innerHTML = `<div class="stage postbind"><b>Warranty monitoring after bind</b>
        <span>Monitoring starts when the policy is bound. Until then, agent data is evidence for the next quote.</span></div>
      <p class="empty">This policy is not bound yet, so no warranties are being enforced.</p>
      ${fleetSection(detail, [])}`;
    return;
  }
  const [w, ev] = await Promise.all([
    api(`/api/policies/${pol.policy_id}/warranties`),
    api(`/api/policies/${pol.policy_id}/warranty-events`)]);
  const count = s => w.warranties.filter(x => x.state === s).length;
  body.innerHTML = `
    <div class="stage postbind"><b>Warranty monitoring after bind</b>
      <span>Policy period ${esc(pol.period_start)} to ${esc(pol.period_end)}.</span></div>
    <div class="kpis" style="margin-bottom:16px">
      ${kpi("Warranties met", count("MET") + count("REMEDIATED"), "", `of ${w.warranties.length}`)}
      ${kpi("In grace", count("IN_GRACE"), count("IN_GRACE") ? "warn" : "zero")}
      ${kpi("Breached", count("BREACHED"), count("BREACHED") ? "bad" : "zero")}
      ${kpi("Premium", fmtINR(pol.bound_premium), "money", "Fixed at inception")}
    </div>
    <div class="callout strong"><b>Security changes after bind move warranty states and their coverage consequences. They never re-price the bound policy.</b></div>
    <div class="grid cols-2">
      ${w.warranties.map(x => `
        <div class="card wcard ${esc(x.state)}">
          <div class="whead"><h3>${esc(x.control_name)}</h3>${pill(x.state)}</div>
          <p class="meaning">${esc(STATE_MEANING[x.state] || "")}</p>
          <dl>
            <dt>Last observed</dt><dd>${esc(dt(x.last_observed_at))}</dd>
            <dt>Grace period</dt><dd>${x.grace_period_days} days</dd>
            ${x.breach_detected_at ? `<dt>Lapse detected</dt><dd>${esc(dt(x.breach_detected_at))}</dd>` : ""}
            ${x.grace_expires_at ? `<dt>Grace ends</dt><dd><b>${esc(dt(x.grace_expires_at))}</b></dd>` : ""}
            <dt>If breached</dt><dd>${esc(x.coverage_consequence.text)}</dd>
          </dl>
          <p class="note">${esc(x.coverage_consequence.label)}</p>
        </div>`).join("")}
    </div>
    ${fleetSection(detail, w.warranties)}
    <h2>Warranty timeline</h2>
    <div class="card"><div class="tablewrap">${ev.events.length ? `<table><thead><tr><th>When</th><th>Warranty</th><th>Change</th><th>Note</th></tr></thead>
      <tbody>${ev.events.map(e => `<tr><td style="white-space:nowrap">${esc(dt(e.at))}</td><td class="mono">${esc(e.control_id)}</td>
        <td style="white-space:nowrap">${e.from_state ? pill(e.from_state) + " → " : '<span class="note">Start</span> → '}${pill(e.to_state)}</td>
        <td class="note">${esc(e.note || "")}${e.trigger_observation_id ? ` · <span class="mono">${esc(e.trigger_observation_id)}</span>` : ""}</td></tr>`).join("")}
      </tbody></table>` : `<p class="empty">No state changes yet.</p>`}</div></div>`;
}

/* ---------------- live fleet from the Beretta collector (Part 2) */
function fleetSection(detail, warranties) {
  const f = detail.fleet;
  const bound = detail.policy.status === "BOUND";
  if (!f) return `<div class="fleethead"><h2>Endpoints</h2></div>
    <p class="empty" style="margin-top:12px">No live-monitoring collector is linked to this company yet. An administrator registers one under
      <a href="#/admin">Model configuration</a>, then links this company to it.</p>`;
  const names = Object.fromEntries(state.meta.controls.map(c => [c.control_id, c.name]));
  const wstate = Object.fromEntries((warranties || []).map(x => [x.control_id, x.state]));
  const fl = f.fleet || {}, lc = fl.liveness_counts || {};
  const cov = f.coverage || {};
  const pct = cov.ratio == null ? 0 : Math.min(100, Math.round(cov.ratio * 100));
  const collectorLink = f.dashboard_url && !isCustomer() ? `${f.dashboard_url.replace(/\/$/, "")}/#/company/${encodeURIComponent(f.collector_company_id)}` : null;
  const hostLink = h => f.dashboard_url && !isCustomer() ? `${f.dashboard_url.replace(/\/$/, "")}/#/host/${encodeURIComponent(h.agent_id)}` : null;
  const cols = (fl.collector_controls || []).map(c => c.control);
  const tile = (v, label, extra = "") => `<div class="kpi"><div class="k">${esc(label)}</div><div class="v ${v ? "" : "zero"}">${esc(v ?? "—")}</div>${extra}</div>`;
  const wpill = id => wstate[id] ? pill(wstate[id]) : "";
  const matrixLabel = s => ({ PASS: "Pass", FAIL: "Fail", PARTIAL: "Partial", NO_DATA: "—", NOT_OBSERVABLE: "N/obs", NOT_SUPPORTED: "N/sup", NOT_APPLICABLE: "N/a", UNKNOWN: "?" }[s] || label(s));
  return `
    <div class="fleethead"><h2>Endpoints</h2>
      <span class="note">From <b>${esc(f.collector_name)}</b> · roll-up <span class="mono">#${esc(f.seq)}</span> · evaluated ${esc(dt(f.evaluated_at))}
      ${collectorLink ? ` · <a href="${esc(collectorLink)}" target="_blank" rel="noopener">Open the collector</a>` : ""}</span></div>
    <p class="note" style="margin:6px 0 0">${bound
      ? "The collector rolls signed per-host reports up to one result per control. Those results reach <b>only</b> the warranties above. The premium does not change."
      : "Before bind, these fleet results are evidence for the next quote at the top strength, technically observed. After bind they only drive warranties."}</p>
    <div class="kpis fleet-tiles">
      ${tile(fl.declared, "Endpoints declared")}
      ${tile(fl.reporting, "Reporting", `<div class="meter ${cov.status === "FAIL" ? "low" : ""}"><span style="width:${pct}%"></span></div>`)}
      ${tile(lc.ONLINE, "Online")}
      ${tile(lc.UNVERIFIED, "Unverified", `<div class="s">Quiet 6 to 72 h</div>`)}
      ${tile(lc.SILENT, "Silent", `<div class="s">Quiet over 72 h</div>`)}
    </div>
    <div class="card"><h3>What the fleet sent to Beretta</h3>
      <div class="tablewrap"><table><thead><tr><th>Platform control</th><th>Fleet result</th><th>Built from</th><th class="num">Hosts passing</th>${bound ? "<th>Warranty</th>" : ""}<th>Why</th></tr></thead>
      <tbody>${(f.controls || []).map(c => `<tr>
        <td>${esc(names[c.platform_control_id] || c.platform_control_id)}<br><span class="mono">${esc(c.platform_control_id)}</span></td>
        <td>${pill(c.value === "partial" ? "PARTIAL" : c.status)}</td>
        <td><div class="srcchips">${(c.sources || []).map(x => pill(x.status, x.control)).join("")}${(c.not_observed || []).map(x => `<span class="pill NO_DATA" title="No host could observe this">${esc(x)} · n/a</span>`).join("")}</div></td>
        <td class="num">${esc(c.passing)} / ${esc(c.observed)}</td>
        ${bound ? `<td>${wpill(c.platform_control_id) || `<span class="note">Not a warranty</span>`}</td>` : ""}
        <td class="note">${esc(c.reason)}</td></tr>`).join("")}
      ${(f.unmapped || []).map(u => `<tr><td>${esc(names[u.platform_control_id] || u.platform_control_id || "—")}<br><span class="mono">${esc(u.platform_control_id || "")}</span></td>
        <td>${pill("NOT_OBSERVABLE", "Not sent")}</td><td><div class="srcchips">${pill("NO_DATA", u.control)}</div></td>
        <td class="num"><span class="note">—</span></td>${bound ? `<td>${wpill(u.platform_control_id)}</td>` : ""}
        <td class="note">${esc(u.reason || u.why)}. Nothing is sent, so Beretta keeps using its questionnaire and document evidence.</td></tr>`).join("")}
      </tbody></table></div></div>
    <div class="card" style="margin-top:16px"><h3>Hosts <span class="note">${(fl.hosts || []).length}</span></h3>
      <div class="tablewrap"><table class="matrix"><thead><tr><th>Host</th><th>Liveness</th><th>Last seen</th>
        ${cols.map(c => `<th class="c">${esc(c.replace(/_/g, " "))}</th>`).join("")}</tr></thead>
      <tbody>${(fl.hosts || []).map(h => `<tr>
        <td style="white-space:nowrap">${hostLink(h) ? `<a href="${esc(hostLink(h))}" target="_blank" rel="noopener"><b>${esc(h.host)}</b></a>` : `<b>${esc(h.host)}</b>`}
          ${h.simulated ? " " + pill("SIMULATED") : ""}${h.build_trusted ? "" : " " + pill("FAIL", "Untrusted build")}
          <br><span class="note">${esc(h.os || "")}</span></td>
        <td>${pill(h.liveness)}</td>
        <td style="white-space:nowrap">${esc(dt(h.last_seen))}</td>
        ${cols.map(c => { const s = (h.controls || {})[c] || "NO_DATA"; return `<td class="c"><span class="pill ${esc(s)}" title="${esc(s)}">${esc(matrixLabel(s))}</span></td>`; }).join("")}
      </tr>`).join("")}</tbody></table></div>
      <p class="note">Host names open the collector, which keeps each check's evidence and the signed report history.</p>
    </div>`;
}

/* ------------------------------------------------ audit */
async function renderAudit(main) {
  const load = async (filters = {}) => {
    const qs = new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v)));
    const d = await api("/api/audit?" + qs.toString());
    $("#auditBody").innerHTML = auditTable(d.events);
  };
  main.innerHTML = `
    <h1>Audit log</h1>
    <p class="sub">Every calculation, bind, configuration change and warranty transition leaves a record that cannot be edited.</p>
    <div class="card"><div class="grid cols-3" style="row-gap:0">
      <div><label class="f" for="fType" style="margin-top:0">Event type</label><input id="fType" placeholder="PREMIUM_CALCULATED"></div>
      <div><label class="f" for="fEntity" style="margin-top:0">Entity id</label><input id="fEntity" placeholder="POL-…"></div>
      <div><label class="f" for="fActor" style="margin-top:0">Actor</label><input id="fActor" placeholder="agent:AGT-…"></div>
    </div><div class="btnrow"><button class="btn secondary" id="fGo">Apply filters</button></div></div>
    <div class="card tablewrap" id="auditBody" style="margin-top:16px"></div>`;
  $("#fGo").addEventListener("click", () => load({ event_type: $("#fType").value, entity_id: $("#fEntity").value, actor: $("#fActor").value }));
  await load();
}

function auditTable(events) {
  if (!events.length) return `<p class="empty">No events match.</p>`;
  return `<table><thead><tr><th>When</th><th>Actor</th><th>Event</th><th>Entity</th><th>Detail</th></tr></thead>
    <tbody>${events.map(e => `<tr>
      <td style="white-space:nowrap">${esc(dt(e.timestamp))}</td><td>${esc(e.actor)}</td>
      <td class="mono">${esc(e.event_type)}</td>
      <td class="mono">${esc(e.entity_type || "")} ${esc(e.entity_id || "")}</td>
      <td class="note">${esc(JSON.stringify(e.new_value ?? e.metadata ?? "")).slice(0, 160)}</td></tr>`).join("")}
    </tbody></table>`;
}

/* ------------------------------------------------ admin */
async function renderAdmin(main) {
  let cfg;
  try { cfg = await api("/api/admin/config"); }
  catch (e) {
    main.innerHTML = `<h1>Model configuration</h1>
      <p class="sub">Only an administrator can see and change the model's assumptions.</p>
      <div class="card"><p style="margin:0">Switch <b>Acting as</b> to Administrator in the sidebar to open this screen.</p>
      <p class="note">${esc(e.message)}</p></div>`;
    return;
  }
  const pp = await api("/api/admin/pricing-params");
  const v2 = state.meta.v2;
  const cap = ([lo, hi], x) => Math.min(Math.max(x, lo), hi);
  const capRange = pp.params.controls.multiplier_cap.value;
  const has = c => cap(capRange, 1 / (c.p + (1 - c.p) * c.S)), lacks = c => cap(capRange, c.S / (c.p + (1 - c.p) * c.S));
  const flat = [];
  (function walk(node, path) {
    if (node && typeof node === "object" && !Array.isArray(node)) {
      if ("tag" in node && ("value" in node || "S" in node)) {
        flat.push({ path, value: "value" in node ? node.value : { S: node.S, p: node.p }, unit: node.unit || "",
                    tag: node.tag, source: node.source || "", locator: node.locator || "" });
        return;
      }
      for (const [k, sub] of Object.entries(node)) if (!k.startsWith("_")) walk(sub, path ? `${path}.${k}` : k);
    }
  })(pp.params, "");
  const warrantyCtrls = state.meta.controls.filter(c => c.is_warranty);
  main.innerHTML = `
    <h1>Model configuration</h1>
    <p class="sub">Model <span class="mono">${esc(state.meta.model_version)}</span>. Every V2 value lives in <span class="mono">${esc(pp.path)}</span> with its source, locator and tag, so it is shown here read-only: change it in the file. Past quotes keep their own copy of the parameters and are never rewritten.</p>
    <div class="grid cols-2">
      <div class="card"><h3>Gating</h3>
        <label class="f" for="cfg_gate" style="margin-top:0">Warranty gate mode</label>
        <select id="cfg_gate" data-cfg="warranty_gate_mode" aria-describedby="gateHelp"><option value="BLOCK" ${cfg.warranty_gate_mode === "BLOCK" ? "selected" : ""}>Block: a failed or unknown warranty makes the risk ineligible</option><option value="WARN" ${cfg.warranty_gate_mode === "WARN" ? "selected" : ""}>Warn: conditionally eligible, underwriter override</option></select>
        <p class="note" id="gateHelp" style="margin-top:6px">Warranties: ${v2.warranties.map(w => esc(ctrlName(w))).join(", ")}. MFA passes when stated. Gating never changes the price.</p>
        <div class="btnrow"><button class="btn" id="saveCfg">Save gate mode</button></div>
      </div>
      <div class="card"><h3>Warranty grace periods <span class="note">used after bind</span></h3>
        <div class="grid cols-2" style="column-gap:12px;row-gap:0">
        ${warrantyCtrls.map(c => `<div><label class="f" for="gd_${esc(c.control_id)}">${esc(c.name)}</label><input id="gd_${esc(c.control_id)}" data-ctrlw="${esc(c.control_id)}" data-f="grace_period_days" type="number" step="1" min="0" value="${c.grace_period_days}"></div>`).join("")}
        </div>
        <div class="btnrow"><button class="btn secondary" id="saveCtrls">Save grace periods</button></div>
      </div>
    </div>

    <h2>Priced controls <span class="note">multipliers centred on the average firm</span></h2>
    <div class="card"><div class="tablewrap"><table><thead><tr><th>Control</th><th class="num">Relative risk S</th><th class="num">Adoption p</th>
      <th class="num">Verified ×</th><th class="num">Stated ×</th><th class="num">Lacking ×</th><th>Applies to</th><th>Source</th></tr></thead>
      <tbody>${[...Object.entries(v2.frequency_controls).map(([id, c]) => [id, c, "freq"]), ...Object.entries(v2.severity_controls).map(([id, c]) => [id, c, "sev"])].map(([id, c, kind]) => {
        const h = has(c), stated = 1 - v2.credit_x * (1 - h);
        return `<tr><td>${esc(ctrlName(id))}</td><td class="num">${c.S}</td><td class="num">${c.p}</td>
          <td class="num">${h.toFixed(3)}</td><td class="num">${stated.toFixed(3)}</td><td class="num">${lacks(c).toFixed(3)}</td>
          <td class="note">${kind === "freq" ? `Frequency, ${esc(label(c.stage))} stage: ${c.perils.map(p => esc(PERIL_LABEL[p])).join(", ")}`
            : `Severity: ${c.targets === "ALL" ? "all perils and heads" : Object.entries(c.targets).map(([p, hs]) => `${esc(PERIL_LABEL[p])} (${hs.length} heads)`).join(", ")}`}</td>
          <td class="note">${esc(c.source)} <span class="pill tag">${esc(c.tag)}</span></td></tr>`; }).join("")}</tbody></table></div>
      <p class="note">Not priced (kept as warranties, monitoring or questionnaire items): ${v2.unpriced.map(esc).join(", ")}.</p></div>

    <details class="assumptions"><summary>All ${flat.length} V2 parameters with provenance</summary>
      <table><thead><tr><th>Parameter</th><th>Value</th><th>Unit</th><th>Tag</th><th>Source and locator</th></tr></thead>
      <tbody>${flat.map(f => `<tr><td class="mono">${esc(f.path)}</td><td class="mono">${esc(JSON.stringify(f.value)).slice(0, 90)}</td>
        <td class="note">${esc(f.unit)}</td><td><span class="pill tag">${esc(f.tag)}</span></td>
        <td class="note">${esc(f.source)}${f.locator ? " · " + esc(f.locator) : ""}</td></tr>`).join("")}</tbody></table>
    </details>
    <h2>Monitoring collectors <span class="note">live endpoint monitoring, Part 2</span></h2>
    <div class="grid cols-2">
      <div class="card"><h3>Registered collectors</h3><div id="colList" class="tablewrap"><p class="note loading">Loading…</p></div></div>
      <div class="card"><h3>Register a collector</h3>
        <label class="f" for="colName">Name</label><input id="colName" value="Beretta collector" maxlength="80">
        <label class="f" for="colUrl">Collector dashboard URL</label><input id="colUrl" placeholder="https://collector.example.in:8443" maxlength="200" aria-describedby="colUrlHelp">
        <p class="note" id="colUrlHelp" style="margin-top:6px">Used for links from this platform back to the collector.</p>
        <div class="btnrow"><button class="btn secondary" id="colCreate">Register collector</button></div>
        <div id="colSecret"></div>
        <h3 style="margin-top:28px">Link a company to a collector</h3>
        <label class="f" for="lnkCol">Collector</label><select id="lnkCol"></select>
        <label class="f" for="lnkCo">Company on Beretta</label><select id="lnkCo"></select>
        <label class="f" for="lnkColCo">Company id on the collector</label><input id="lnkColCo" maxlength="80" placeholder="co_kalinga">
        <div class="btnrow"><button class="btn secondary" id="lnkBtn">Link company</button></div>
      </div>
    </div>`;
  const loadCollectors = async () => {
    const [cl, cos] = await Promise.all([api("/api/admin/collectors"), api("/api/companies")]);
    $("#colList").innerHTML = cl.collectors.length ? `<table><thead><tr><th>Collector</th><th>Last roll-up</th><th>Linked companies</th></tr></thead><tbody>
      ${cl.collectors.map(c => `<tr><td>${esc(c.name)}<br><span class="mono">${esc(c.collector_id)}</span></td>
        <td>${c.last_seen ? '<span class="mono">#' + esc(c.last_seq) + "</span> · " + esc(dt(c.last_seen)) : '<span class="note">Never</span>'}</td>
        <td>${c.links.map(l => `${esc(l.name)} <span class="mono">↔ ${esc(l.collector_company_id)}</span>`).join("<br>") || "—"}</td></tr>`).join("")}
      </tbody></table>` : `<p class="empty">No collectors registered.</p>`;
    $("#lnkCol").innerHTML = cl.collectors.map(c => `<option value="${esc(c.collector_id)}">${esc(c.name)} (${esc(c.collector_id)})</option>`).join("");
    $("#lnkCo").innerHTML = cos.companies.map(c => `<option value="${esc(c.company_id)}">${esc(c.name)}</option>`).join("");
  };
  await loadCollectors();
  $("#colCreate").addEventListener("click", async () => {
    try {
      const r = await post("/api/admin/collectors", { name: $("#colName").value, dashboard_url: $("#colUrl").value || null });
      $("#colSecret").innerHTML = `<p class="note" style="margin-top:16px">Run this on the collector. The secret is shown <b>once</b>.</p>
        <div class="secretbox">python -m kyh_collector --data DATA link-platform --url ${esc(location.origin)} --collector-id ${esc(r.collector_id)} --secret ${esc(r.secret)}</div>`;
      toast("Collector registered and audited."); await loadCollectors();
    } catch (e) { toast(e.message, true); }
  });
  $("#lnkBtn").addEventListener("click", async () => {
    try {
      await post(`/api/admin/collectors/${$("#lnkCol").value}/links`, { company_id: $("#lnkCo").value, collector_company_id: $("#lnkColCo").value });
      toast("Company linked. Fleet roll-ups for it are now accepted."); await loadCollectors();
    } catch (e) { toast(e.message, true); }
  });
  $("#saveCfg").addEventListener("click", async () => {
    try { await put("/api/admin/config", { warranty_gate_mode: $("#cfg_gate").value }); toast("Gate mode saved and audited."); }
    catch (e) { toast(e.message, true); }
  });
  $("#saveCtrls").addEventListener("click", async () => {
    const per = {};
    main.querySelectorAll("[data-ctrlw]").forEach(i => {
      (per[i.dataset.ctrlw] = per[i.dataset.ctrlw] || {})[i.dataset.f] = Number(i.value);
    });
    try {
      for (const [id, fields] of Object.entries(per)) await put(`/api/admin/controls/${id}`, fields);
      toast("Grace periods saved and audited."); state.meta = await api("/api/meta");
    } catch (e) { toast(e.message, true); }
  });
}

/* ------------------------------------------------ regulatory */
async function renderRegulatory(main) {
  const d = await api("/api/regulatory");
  main.innerHTML = `
    <h1>Regulatory context</h1>
    <p class="sub">The Indian cyber-risk rules this prototype is designed around. Listing them here does not make the prototype compliant with any of them.</p>
    <div class="grid cols-2 stretch reglist">${d.context.map(c => `
      <div class="card"><div class="key">${esc(c.key)}</div><h3>${esc(c.name)}</h3><p class="note" style="margin:0">${esc(c.note)}</p></div>`).join("")}
    </div>
    <div class="banner" style="margin-top:16px">${esc(d.disclaimer)}</div>`;
}

/* ------------------------------------------------ questionnaires / forms */
async function renderForms(main) {
  const d = await api("/api/forms");
  const forms = d.forms || [];
  const primary = forms.find(f => f.primary);
  const rest = forms.filter(f => !f.primary);

  const href = f => "/forms/" + encodeURIComponent(f.file);
  const meta = f => [f.pages ? f.pages + " pages" : null, "PDF", f.code].filter(Boolean).join(" · ");
  const actions = (f, primaryBtn) => f.available
    ? `<a class="btn ${primaryBtn ? "" : "secondary small"}" href="${href(f)}" download>Download${primaryBtn ? " PDF" : ""}</a>
       <a class="btn secondary ${primaryBtn ? "" : "small"}" href="${href(f)}" target="_blank" rel="noopener">Preview</a>`
    : `<button class="btn secondary ${primaryBtn ? "" : "small"}" disabled title="The file was not found on the server">Unavailable</button>`;

  const x = Math.round((state.meta.v2.credit_x || 0) * 100);
  const strengths = [
    ["DECLARED", `The applicant says so in a questionnaire. Priced as stated: ${x}% of the control's effect.`],
    ["DOCUMENTED", "A report backs the answer up. An independent one (SOC 2 Type II, ISO 27001 SoA, VAPT, scanner export) verifies it; a self-assessment counts as stated."],
    ["TESTED", "A test result shows the control works, such as a restore test or a tabletop. Verified: the full effect."],
    ["TECHNICALLY_OBSERVED", "The monitoring agent or an outside-in scan saw it working. Verified: the full effect."],
  ];

  main.innerHTML = `
    <h1>Questionnaires</h1>
    <p class="sub">An applicant completes one of these before a quote is produced, then returns it to their broker or underwriter. The answers feed an explainable premium. Attaching evidence earns a better rating for the same security posture.</p>

    ${primary ? `<div class="card featured">
      <div>
        <h3>${esc(primary.title)}</h3>
        <p class="meta">For ${esc(primary.audience)} · ${esc(meta(primary))}</p>
        <p style="max-width:72ch">${esc(primary.desc)}</p>
      </div>
      <div class="btnrow">${actions(primary, true)}</div>
    </div>` : ""}

    <h2>Short form and supplementary questionnaires</h2>
    <div class="card"><div class="tablewrap"><table class="formlist">
      <thead><tr><th>Questionnaire</th><th>For</th><th class="num">Pages</th><th></th></tr></thead>
      <tbody>${rest.map(f => `<tr>
        <td><b>${esc(f.title)}</b><span>${esc(f.desc)}</span></td>
        <td>${esc(f.audience)}${f.code ? `<br><span class="mono">${esc(f.code)}</span>` : ""}</td>
        <td class="num">${f.pages ? esc(f.pages) : '<span class="note">—</span>'}</td>
        <td class="actions">${actions(f, false)}</td></tr>`).join("") || `<tr><td colspan="4"><p class="empty">No supplementary forms on this server.</p></td></tr>`}
      </tbody></table></div></div>

    <h2>How evidence changes the price</h2>
    <div class="card">
      <div class="ladderkey">${strengths.map(([s, text]) => `<div>${evTag(s)}<p>${esc(text)}</p></div>`).join("")}</div>
      <p class="note" style="margin-top:16px">A control that is not working, or that nobody has evidenced, is priced as missing. The quote page lists what verifying each control would save.</p>
    </div>

    <p class="onward"><a href="#/companies">Onboard a company</a><a href="#/dashboard">Open the portfolio</a><a href="#/regulatory">Read the regulatory context</a></p>

    <div class="banner" style="margin-top:24px">${esc(d.disclaimer || "")}</div>
    <p class="note">Form set aligned to underwriting model <span class="mono">${esc(d.model_version || "")}</span>. For comparison, real Indian carrier proposal forms include HDFC ERGO, SBI General and Bajaj Allianz cyber proposal forms.</p>`;
}

boot().catch(e => { $("#main").innerHTML = `<div class="card"><p>Failed to start: ${esc(e.message)}</p></div>`; });
