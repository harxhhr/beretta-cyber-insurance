// Beretta Live Monitoring dashboard. Vanilla JS, no build step.
// Every value that came from an agent (hostnames, summaries, evidence) is escaped before
// it touches the DOM: agents are outside the insurer's trust boundary.
(function () {
  "use strict";
  var TOKEN_KEY = "kyh_admin_token";
  var view = document.getElementById("view");
  var timer = null;

  // Display labels only; API values are unchanged. SIMULATED is never relabelled.
  var LABELS = {
    MET: "Met", IN_GRACE: "In grace", BREACHED: "Breached", REMEDIATED: "Remediated",
    PASS: "Pass", FAIL: "Fail", PARTIAL: "Partial", UNKNOWN: "Unknown", BOUND: "Bound",
    ONLINE: "Online", UNVERIFIED: "Unverified", SILENT: "Silent", SILENT_PASS: "Silent pass",
    NOT_OBSERVABLE: "Not observable", NOT_SUPPORTED: "Not supported", NOT_APPLICABLE: "Not applicable",
    NO_DATA: "No data", OPERATING: "Operating", PRESENT: "Present", ABSENT: "Absent", ERROR: "Error"
  };
  var MATRIX = { PASS: "Pass", FAIL: "Fail", PARTIAL: "Partial", NO_DATA: "—", NOT_OBSERVABLE: "N/obs",
                 NOT_SUPPORTED: "N/sup", NOT_APPLICABLE: "N/a", UNKNOWN: "?" };
  var MEANING = {
    MET: "The control is in place. Cover applies as written.",
    IN_GRACE: "The control has lapsed. The insured has until the grace period ends to fix it.",
    BREACHED: "The grace period ended without a fix. The coverage consequence applies.",
    REMEDIATED: "The control was restored after a breach. Normal cover is back."
  };

  function esc(v) {
    return String(v === null || v === undefined ? "" : v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function label(s) {
    if (s === null || s === undefined) return "-";
    return LABELS[s] || String(s).replace(/_/g, " ").toLowerCase().replace(/^./, function (c) { return c.toUpperCase(); });
  }
  function chip(s, extra) { return '<span class="chip ' + esc(String(s).replace(/[^A-Z_]/g, "")) + '">' + esc(extra || label(s)) + "</span>"; }
  function inr(n) { return n === null || n === undefined ? "-" : "₹" + Number(n).toLocaleString("en-IN"); }
  function when(ts) { if (!ts) return "-"; var d = new Date(ts); return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }); }
  function ago(ts) {
    if (!ts) return "never";
    var m = Math.round((Date.now() - new Date(ts).getTime()) / 60000);
    if (m < 1) return "just now"; if (m < 60) return m + " min ago";
    var h = Math.round(m / 60); if (h < 48) return h + " h ago"; return Math.round(h / 24) + " days ago";
  }
  function token() { try { return sessionStorage.getItem(TOKEN_KEY); } catch (e) { return window.__kyhToken || null; } }
  function setToken(t) { try { sessionStorage.setItem(TOKEN_KEY, t); } catch (e) { window.__kyhToken = t; } }
  function clearToken() { try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) { window.__kyhToken = null; } }

  function api(path) {
    return fetch(path, { headers: { Authorization: "Bearer " + token() } }).then(function (r) {
      if (r.status === 401) { clearToken(); showLogin("That token was rejected. Check it and try again."); throw new Error("unauthorized"); }
      return r.json();
    });
  }

  function showLogin(msg) {
    document.getElementById("login").classList.remove("hidden");
    document.getElementById("logout").classList.add("hidden");
    document.getElementById("login-error").textContent = msg || "";
    document.getElementById("updated").textContent = "";
    view.innerHTML = "";
    document.getElementById("token").focus();
  }

  document.getElementById("login-form").addEventListener("submit", function (e) {
    e.preventDefault();
    setToken(document.getElementById("token").value.trim());
    document.getElementById("login").classList.add("hidden");
    route();
  });
  document.getElementById("logout").addEventListener("click", function () { clearToken(); showLogin(); });

  // ------------------------------------------------------------------ overview
  function renderOverview(data) {
    var breached = 0, grace = 0;
    data.companies.forEach(function (c) {
      c.warranties.forEach(function (w) { if (w.state === "BREACHED") breached++; if (w.state === "IN_GRACE") grace++; });
    });
    var n = data.companies.length, cos = n + (n === 1 ? " company" : " companies");
    var html = "<h1>Insured companies</h1><p class=\"sub\">" +
      (breached || grace ? esc(breached + " breached and " + grace + " in grace across " + cos + ". ")
                         : esc("No warranty is in grace or breached across " + cos + ". ")) +
      "Warranty states are re-evaluated on every agent report and every page load.</p><div class=\"cards\">";
    data.companies.forEach(function (c) {
      var cov = c.coverage || {};
      var pct = cov.ratio === null || cov.ratio === undefined ? 0 : Math.min(100, Math.round(cov.ratio * 100));
      html += '<div class="card co" tabindex="0" role="link" data-id="' + esc(c.company.id) + '">' +
        '<div class="head"><h4>' + esc(c.company.name) + "</h4>" + chip(c.policy.status) + "</div>" +
        '<div class="chips">' + (c.company.demo_mode ? chip("SIM", "SIMULATED") : "") + (c.linked ? chip("RUNNING", "Linked to Beretta platform") : "") + "</div>" +
        (c.policy.bound_premium_inr === null || c.policy.bound_premium_inr === undefined
          ? '<p class="muted">Not bound yet: no premium and no warranties.</p>'
          : '<div class="money">' + esc(inr(c.policy.bound_premium_inr)) + '</div><p class="muted">Bound premium</p>') +
        "<p>" + esc(cov.reporting) + " of " + esc(cov.declared) + ' endpoints reporting</p><div class="bar' + (cov.status === "FAIL" ? " low" : "") + '"><span data-w="' + pct + '"></span></div>' +
        '<div class="chips">' + c.warranties.map(function (w) { return chip(w.state, w.control.replace(/_/g, " ") + ": " + label(w.state)); }).join("") + "</div></div>";
    });
    if (!data.companies.length) html += '<p class="muted">No companies yet.</p>';
    view.innerHTML = html + "</div>";
    Array.prototype.forEach.call(view.querySelectorAll(".co"), function (el) {
      var go = function () { location.hash = "#/company/" + el.getAttribute("data-id"); };
      el.addEventListener("click", go);
      el.addEventListener("keydown", function (e) { if (e.key === "Enter") go(); });
    });
    document.getElementById("foot").textContent = "";
    widths();
  }

  // ------------------------------------------------------------------ company
  function renderCompany(d) {
    var cov = d.coverage, lc = d.liveness_counts, pol = d.policy || {};
    var pct = cov.ratio === null ? 0 : Math.min(100, Math.round(cov.ratio * 100));
    var plat = d.linked ? d.platform : null;
    var platUrl = plat && plat.url ? plat.url + "/#/companies/" + encodeURIComponent(plat.platform_company_id) + "/monitoring" : null;
    var html = '<p class="crumb"><a href="#/">All companies</a> / ' + esc(d.company.name) + "</p>" +
      "<h1>" + esc(d.company.name) + " " + chip(pol.status) + "</h1>" +
      '<p class="sub">' + esc(cov.reporting) + " of " + esc(cov.declared) + " declared endpoints reporting. " +
      (pol.bound_at ? "Bound " + esc(when(pol.bound_at)) + "." : "Not bound yet.") + "</p>";

    var hasPremium = pol.bound_premium_inr !== null && pol.bound_premium_inr !== undefined;
    html += '<div class="lead"><div class="panel premium"><div class="k">Bound premium</div>' +
      (hasPremium ? '<div class="v">' + esc(inr(pol.bound_premium_inr)) + "</div>" : '<div class="v none">Not bound yet</div>') +
      '<div class="muted">' + esc(pol.model_id || "-") + "</div></div>" +
      '<div class="panel note"><b>' + esc(d.premium_note) + "</b>" +
      (plat ? '<span class="muted">Warranty authority: the Beretta platform (company <span class="mono">' + esc(plat.platform_company_id) + "</span>)." +
        (platUrl ? ' <a href="' + esc(platUrl) + '" target="_blank" rel="noopener">Open it in the Beretta platform</a>' : "") + "</span>"
            : '<span class="muted">Status: ' + esc(label(pol.status)) + "</span>") + "</div></div>";

    html += '<div class="tiles">' +
      tile("Declared endpoints", cov.declared) + tile("Enrolled agents", cov.enrolled) +
      '<div class="tile"><div class="k">Reporting</div><div class="v">' + esc(cov.reporting) + '</div><div class="bar' + (cov.status === "FAIL" ? " low" : "") + '"><span data-w="' + pct + '"></span></div></div>' +
      tile("Online", lc.ONLINE) + tile("Unverified", lc.UNVERIFIED, lc.UNVERIFIED ? "warn" : "") + tile("Silent", lc.SILENT, lc.SILENT ? "bad" : "") + "</div>";

    html += "<h2>Warranties" + (plat ? ' <span class="muted">held by the Beretta platform, read back after each push</span>' : "") + '</h2><div class="cards">';
    d.warranties.forEach(function (w) {
      html += '<div class="card ' + esc(w.state) + '"><div class="head"><h4>' + esc(w.control.replace(/_/g, " ")) + "</h4>" + chip(w.state) + "</div>" +
        "<p>" + esc(MEANING[w.state] || "") + "</p>" +
        (w.since ? '<p class="muted">Since ' + esc(when(w.since)) + "</p>" : "") +
        (w.grace_expires_at && w.state === "IN_GRACE" ? "<p><b>Grace ends " + esc(when(w.grace_expires_at)) + "</b></p>" : "") +
        (w.last_reason ? '<p class="muted">' + esc(w.last_reason) + "</p>" : "") +
        (w.consequence ? '<p class="consequence">' + esc(w.consequence) + "</p>" : "") + "</div>";
    });
    if (!d.warranties.length) html += '<p class="muted">The policy is not bound yet, so no warranties are being enforced.' + (plat ? " Fleet results still go to the platform as evidence for the next quote." : "") + "</p>";
    html += "</div>";
    if (plat) html += renderLink(plat);

    html += '<h2>Controls across the fleet</h2><div class="panel"><div class="scroll"><table><tr><th>Tier</th><th>Control</th><th>Status</th><th class="num">Hosts passing</th><th>Why</th></tr>';
    d.controls.forEach(function (c) {
      html += "<tr><td>" + esc(c.tier) + "</td><td>" + esc(c.control.replace(/_/g, " ")) + "</td><td>" + chip(c.status) + '</td><td class="num">' +
        (c.observed ? esc(c.passing + " / " + c.observed) : '<span class="muted">-</span>') + "</td><td>" + esc(c.reason) +
        (c.failing_hosts.length ? '<br><span class="muted">Failing: ' + esc(c.failing_hosts.map(function (f) { return f.host; }).join(", ")) + "</span>" : "") + "</td></tr>";
    });
    html += "</table></div></div>";

    var controls = d.controls.map(function (c) { return c.control; });
    html += '<h2>Endpoints <span class="muted">' + esc(d.hosts.length) + '</span></h2><div class="panel"><div class="scroll"><table class="matrix"><tr><th>Host</th><th>Liveness</th><th>Last seen</th>' +
      controls.map(function (c) { return '<th class="c">' + esc(c.replace(/_/g, " ")) + "</th>"; }).join("") + "</tr>";
    d.hosts.forEach(function (h) {
      var flags = (h.simulated ? " " + chip("SIM", "SIMULATED") : "") + (!h.build_trusted ? " " + chip("FAIL", "Untrusted build") : "");
      html += '<tr><td><a href="#/host/' + esc(h.agent_id) + '"><b>' + esc(h.hostname || h.agent_id) + "</b></a>" + flags +
        '<br><span class="muted">' + esc(h.os || h.platform) + "</span></td><td>" + chip(h.liveness.state) + '</td><td class="when">' + esc(ago(h.last_seen)) + "</td>" +
        controls.map(function (c) { var x = h.controls[c] || { status: "NO_DATA", reason: "" }; return '<td class="c" title="' + esc(x.reason) + '">' + chip(x.status, MATRIX[x.status] || label(x.status)) + "</td>"; }).join("") + "</tr>";
    });
    if (!d.hosts.length) html += '<tr><td colspan="' + (3 + controls.length) + '" class="muted">No agents enrolled yet.</td></tr>';
    html += "</table></div></div>";

    html += "<h2>Warranty events</h2>";
    if (plat) html += '<div class="panel"><p>Warranty changes for this company are recorded by the Beretta platform, which owns its warranties.' +
      (platUrl ? ' <a href="' + esc(platUrl) + '" target="_blank" rel="noopener">Open the timeline there</a>.' : "") + "</p></div>";
    else {
      html += '<div class="panel"><div class="scroll"><table><tr><th>When</th><th>Control</th><th>Change</th><th>Reason</th></tr>';
      (d.events || []).forEach(function (e) {
        html += '<tr><td class="when">' + esc(when(e.at)) + "</td><td>" + esc(e.control.replace(/_/g, " ")) + '</td><td class="when">' + (e.from_state ? chip(e.from_state) + " &rarr; " : "") + chip(e.to_state) +
          "</td><td>" + esc(e.reason) + (e.consequence ? '<br><span class="error">' + esc(e.consequence) + "</span>" : "") + "</td></tr>";
      });
      if (!(d.events || []).length) html += '<tr><td colspan="4" class="muted">No warranty changes yet.</td></tr>';
      html += "</table></div></div>";
    }
    html += '<h2>Audit trail</h2><div class="panel"><div class="scroll"><table><tr><th>When</th><th>Actor</th><th>Action</th><th>Detail</th></tr>';
    (d.audit || []).forEach(function (a) {
      html += '<tr><td class="when">' + esc(when(a.at)) + "</td><td>" + esc(a.actor) + "</td><td>" + esc(a.action) + "</td><td>" + esc(a.detail) + "</td></tr>";
    });
    if (!(d.audit || []).length) html += '<tr><td colspan="4" class="muted">No audit entries.</td></tr>';
    html += "</table></div></div>";
    view.innerHTML = html;
    document.getElementById("foot").textContent = d.label;
    widths();
  }

  function renderLink(p) {
    var st = p.state || {};
    var html = '<h2>Link to the Beretta platform</h2><div class="panel"><p>' +
      (st.last_attempt_at ? (st.last_ok ? chip("PASS", "Last push OK") : chip("FAIL", "Last push failed")) + ' push <span class="mono">#' + esc(st.last_seq) + "</span> &middot; " + esc(ago(st.last_attempt_at)) +
        (st.last_error ? ' &middot; <span class="error">' + esc(st.last_error) + "</span>" : "") : chip("NO_DATA", "Not pushed yet")) +
      '</p><p class="muted">Several collector controls can feed one platform control, and it fails if any of them fails. Controls that no host can observe are not sent, so the platform keeps its own evidence for them.</p>' +
      '<div class="scroll"><table><tr><th>Platform control</th><th>Sent</th><th>From collector controls</th><th class="num">Hosts passing</th><th>Why</th></tr>';
    (p.mapping || []).forEach(function (m) {
      html += "<tr><td><code>" + esc(m.platform_control_id) + "</code></td><td>" + chip(m.status, label(m.status) + " (" + m.value + ")") + "</td><td>" +
        m.sources.map(function (x) { return chip(x.status, x.control + ": " + label(x.status)); }).join(" ") +
        (m.not_observed || []).map(function (x) { return " " + chip("NO_DATA", x + ": n/a"); }).join("") + '</td><td class="num">' + esc(m.passing + " / " + m.observed) + "</td><td>" + esc(m.reason) + "</td></tr>";
    });
    (p.unmapped || []).forEach(function (u) {
      html += "<tr><td><code>" + esc(u.platform_control_id || "-") + "</code></td><td>" + chip("NOT_OBSERVABLE", "Not sent") + "</td><td>" + chip("NO_DATA", u.control) + '</td><td class="num"><span class="muted">-</span></td><td class="muted">' + esc(u.reason || u.why) + "</td></tr>";
    });
    return html + "</table></div></div>";
  }

  function tile(k, v, cls) {
    var empty = v === undefined || v === null;
    return '<div class="tile"><div class="k">' + esc(k) + '</div><div class="v ' + (cls || (!v ? "zero" : "")) + '">' + esc(empty ? "-" : v) + "</div></div>";
  }

  // ------------------------------------------------------------------ host
  function renderHost(d) {
    var a = d.agent;
    var html = '<p class="crumb"><a href="#/">All companies</a> / <a href="#/company/' + esc(a.company_id) + '">Company</a> / ' + esc(a.hostname) + "</p>";
    html += "<h1>" + esc(a.hostname) + "</h1><p class=\"sub\">" + esc(a.os) + " &middot; agent " + esc(a.agent_version) + ' &middot; <span class="mono">' + esc(a.agent_id) + "</span></p>";
    html += '<div class="tiles"><div class="tile"><div class="k">Last seen</div><div class="v">' + esc(ago(a.last_seen)) + "</div></div>" +
      '<div class="tile"><div class="k">Last full snapshot</div><div class="v">' + esc(ago(a.last_full_at)) + "</div></div>" +
      tile("Reports waiting in outbox", a.queue_depth, a.queue_depth ? "warn" : "") +
      '<div class="tile"><div class="k">Build and policy</div><p>' + (a.build_trusted ? chip("PASS", "Build approved") : chip("FAIL", "Build not approved")) + " " +
      (a.policy_trusted ? chip("PASS", "Policy approved") : chip("FAIL", "Policy not approved")) +
      '</p><span class="mono">' + esc((a.build_hash || "").slice(0, 16)) + "</span></div></div>";
    html += '<h2>Latest result per check</h2><div class="panel"><div class="scroll"><table><tr><th>Tier</th><th>Control</th><th>Status</th><th>Assurance</th><th>Summary and evidence</th><th>Observed</th></tr>';
    d.results.forEach(function (r) {
      html += "<tr><td>" + esc(r.tier) + "</td><td>" + esc(r.control.replace(/_/g, " ")) + "</td><td>" + chip(r.status) + "</td><td>" + (r.assurance ? chip(r.assurance) : '<span class="muted">-</span>') +
        "</td><td>" + esc(r.summary) + "<details><summary>Evidence (" + esc(r.evidence_strength) + ", " + esc(r.method) + ")</summary><pre>" +
        esc(JSON.stringify(r.evidence, null, 2)) + '</pre></details></td><td class="when">' + esc(when(r.observed_at)) + "</td></tr>";
    });
    html += '</table></div></div><h2>Recent reports <span class="muted">immutable once received</span></h2><div class="panel"><div class="scroll"><table><tr><th class="num">Seq</th><th>Kind</th><th>Created on host</th><th>Received</th><th>Strength</th><th>SHA-256</th></tr>';
    d.reports.forEach(function (r) {
      html += '<tr><td class="num">' + esc(r.seq) + "</td><td>" + esc(r.kind) + '</td><td class="when">' + esc(when(r.created_at)) + '</td><td class="when">' + esc(when(r.received_at)) + "</td><td>" +
        esc(r.evidence_strength) + "</td><td><code>" + esc(r.body_sha256.slice(0, 16)) + "</code></td></tr>";
    });
    view.innerHTML = html + "</table></div></div>";
  }

  function widths() {
    Array.prototype.forEach.call(view.querySelectorAll("[data-w]"), function (el) { el.style.width = el.getAttribute("data-w") + "%"; });
  }

  // ------------------------------------------------------------------ router
  function route() {
    if (!token()) { showLogin(); return; }
    document.getElementById("logout").classList.remove("hidden");
    var h = location.hash.replace(/^#\/?/, "").split("/");
    var p;
    if (h[0] === "company" && h[1]) p = api("/api/v1/companies/" + encodeURIComponent(h[1])).then(renderCompany);
    else if (h[0] === "host" && h[1]) p = api("/api/v1/agents/" + encodeURIComponent(h[1])).then(renderHost);
    else p = api("/api/v1/overview").then(renderOverview);
    p.then(function () { document.getElementById("updated").textContent = "Updated " + new Date().toLocaleTimeString("en-IN"); })
     .catch(function () {});
    clearTimeout(timer);
    timer = setTimeout(function () { if (!document.querySelector("details[open]")) route(); else timer = setTimeout(route, 15000); }, 15000);
  }
  window.addEventListener("hashchange", route);
  route();
})();
