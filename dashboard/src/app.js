(function () {
  "use strict";

  // ── load embedded data ──────────────────────────────────────────────────────
  var D = JSON.parse(document.getElementById("asteria-data").textContent);
  var meta       = D.meta       || {};
  var summary    = D.summary    || [];
  var series     = (D.series    || {}).rows || [];
  var seriesCols = (D.series    || {}).columns || [];
  var extMeta    = D.external_meta || [];
  var assoc      = D.association   || [];
  var quality    = D.quality       || [];
  var sources    = D.sources       || [];
  var methodology= D.methodology  || {};
  var objectives = D.objectives    || [];
  var countries  = D.countries     || [];
  var busUnits   = D.business_units || [];
  var notices    = D.notices       || [];

  // ── helpers ─────────────────────────────────────────────────────────────────
  function fmt(v, digits) {
    if (v === null || v === undefined) return "N/A";
    return (parseFloat(v) * 100).toFixed(digits !== undefined ? digits : 1) + "%";
  }
  function fmtRaw(v, digits) {
    if (v === null || v === undefined) return "N/A";
    return parseFloat(v).toFixed(digits !== undefined ? digits : 3);
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;");
  }
  function el(id) { return document.getElementById(id); }

  // ── topbar meta ──────────────────────────────────────────────────────────────
  el("run-meta").textContent = "As-of: " + (meta.as_of || "") + " · Source: " + (meta.source_mode || "") + " · Run: " + (meta.run_timestamp || "").slice(0,16).replace("T"," ") + " UTC";
  el("footer-asof").textContent = meta.as_of || "";

  // ── notices ──────────────────────────────────────────────────────────────────
  var noticeContainer = el("notices");
  notices.forEach(function (n) {
    var div = document.createElement("div");
    div.className = "notice-bar" + (n.level === "warning" ? "" : " info");
    div.setAttribute("role","alert");
    div.innerHTML = "<span aria-hidden='true'>" + (n.level === "warning" ? "⚠" : "ℹ") + "</span> " + esc(n.message);
    noticeContainer.appendChild(div);
  });

  // ── objective config lookup ───────────────────────────────────────────────────
  var objMap = {};
  objectives.forEach(function (o) { objMap[o.objective_id] = o; });

  function meetsTarget(value, obj) {
    if (value === null || value === undefined || !obj) return null;
    return obj.direction === "at_least" ? value >= obj.target_value : value <= obj.target_value;
  }

  // ── 01 stat cards ────────────────────────────────────────────────────────────
  var allRows = summary.filter(function (r) { return r.country_code === "ALL" && r.business_unit === "ALL"; });

  allRows.forEach(function (row) {
    var obj  = objMap[row.objective_id];
    var hit  = meetsTarget(row.value, obj);
    var card = document.createElement("div");
    card.className = "stat-card" + (hit === false ? " miss" : "");
    card.setAttribute("role","region");
    card.setAttribute("aria-label", esc(obj ? obj.name : row.objective_id));

    var pct   = row.value !== null ? (row.value * 100).toFixed(1) + "%" : "N/A";
    var tgt   = obj ? (obj.direction === "at_least" ? "≥ " : "≤ ") + (obj.target_value * 100).toFixed(0) + "%" : "";
    var cls   = hit === true ? "hit" : hit === false ? "miss" : "";
    var badge = hit === true ? "✅ On target" : hit === false ? "❌ Off target" : "";
    var n     = row.denominator !== null && row.denominator !== undefined ? "n = " + Math.round(row.denominator) : "";

    card.innerHTML =
      "<span class='stat-badge " + cls + "'>" + badge + "</span>" +
      "<div class='stat-label'>" + esc(obj ? obj.name : row.objective_id) + "</div>" +
      "<div class='stat-value " + cls + "'>" + pct + "</div>" +
      "<div class='stat-sub'>Target " + tgt + " &nbsp;·&nbsp; " + n + "</div>";
    el("stat-cards").appendChild(card);
  });

  // ── 01 filters ───────────────────────────────────────────────────────────────
  var selObj     = el("sel-objective");
  var selCountry = el("sel-country");
  var selBU      = el("sel-bu");

  function addOption(sel, val, label) {
    var o = document.createElement("option");
    o.value = val; o.textContent = label;
    sel.appendChild(o);
  }

  addOption(selObj, "ALL", "All objectives");
  objectives.forEach(function (o) { addOption(selObj, o.objective_id, o.name || o.objective_id); });

  addOption(selCountry, "ALL", "All countries");
  countries.forEach(function (c) { addOption(selCountry, c.iso2, c.name + " (" + c.iso2 + ")"); });

  addOption(selBU, "ALL", "All business units");
  busUnits.forEach(function (u) { addOption(selBU, u, u); });

  // ── 01 breakdown table builder ────────────────────────────────────────────────
  function buildBreakdown() {
    var objId    = selObj.value;
    var country  = selCountry.value;
    var bu       = selBU.value;

    // Filter summary rows for the country tab: country-level, BU="ALL"
    var countryRows = summary.filter(function (r) {
      var matchObj  = objId === "ALL" || r.objective_id === objId;
      var matchBU   = bu === "ALL" || r.business_unit === bu;
      var isCountry = r.country_code !== "ALL" && r.business_unit === "ALL";
      var matchC    = country === "ALL" || r.country_code === country;
      return matchObj && matchBU && isCountry && matchC;
    });

    // Filter summary rows for the BU tab: bu-level, country="ALL"
    var buRows = summary.filter(function (r) {
      var matchObj  = objId === "ALL" || r.objective_id === objId;
      var matchC    = country === "ALL" || r.country_code === country;
      var isBU      = r.business_unit !== "ALL" && r.country_code === "ALL";
      var matchBU   = bu === "ALL" || r.business_unit === bu;
      return matchObj && matchC && isBU && matchBU;
    });

    renderBreakdownRows(el("tbody-country"), countryRows, "country_code");
    renderBreakdownRows(el("tbody-bu"),      buRows,      "business_unit");
  }

  function renderBreakdownRows(tbody, rows, groupKey) {
    tbody.innerHTML = "";
    if (!rows.length) {
      tbody.innerHTML = "<tr><td colspan='6' class='empty'>No data for this selection.</td></tr>";
      return;
    }
    rows.forEach(function (row) {
      var obj = objMap[row.objective_id];
      var hit = meetsTarget(row.value, obj);
      var cls = hit === true ? "hit" : hit === false ? "miss" : "";
      var pct = row.value !== null ? (row.value * 100).toFixed(1) + "%" : "N/A";
      var tgt = obj ? obj.target_value * 100 : null;
      var n   = row.denominator !== null ? Math.round(row.denominator) : "—";

      // simple progress bar: value vs target (capped at 100%)
      var barPct = 0;
      if (row.value !== null && tgt !== null) barPct = Math.min(100, (row.value * 100));
      var barMiss = hit === false ? " miss" : "";

      var badge = hit === true ? "<span class='badge badge-hit'>✅ On target</span>"
                : hit === false ? "<span class='badge badge-miss'>❌ Off target</span>"
                : "<span class='badge badge-muted'>—</span>";

      var tr = document.createElement("tr");
      tr.className = cls;
      tr.innerHTML =
        "<td><strong>" + esc(row[groupKey] || "—") + "</strong>" +
              (groupKey === "country_code" ? "" : "") + "</td>" +
        "<td>" + pct + "</td>" +
        "<td>" + (tgt !== null ? (obj.direction === "at_least" ? "≥ " : "≤ ") + tgt.toFixed(0) + "%" : "—") + "</td>" +
        "<td>" + n + "</td>" +
        "<td style='min-width:80px'><div class='progress-wrap'>" +
          "<div class='progress-bar" + barMiss + "' style='width:" + barPct + "%' role='progressbar' aria-valuenow='" + barPct + "' aria-valuemin='0' aria-valuemax='100'></div>" +
        "</div></td>" +
        "<td>" + badge + "</td>";
      tbody.appendChild(tr);
    });
  }

  [selObj, selCountry, selBU].forEach(function (sel) {
    sel.addEventListener("change", buildBreakdown);
  });
  buildBreakdown();

  // ── 01 tabs: country / BU ─────────────────────────────────────────────────────
  setupTabs([el("tab-country"), el("tab-bu")], [el("pane-country"), el("pane-bu")]);

  // ── 02 external signals ──────────────────────────────────────────────────────
  var tbodyExt = el("tbody-ext");
  extMeta.forEach(function (m) {
    var isSynth = m.data_origin === "fixture_synthetic";
    var tr = document.createElement("tr");
    if (isSynth) tr.style.color = "#f5c848";
    var originBadge = isSynth
      ? "<span class='badge badge-warn'>Synthetic</span>"
      : "<span class='badge badge-info'>Live</span>";
    tr.innerHTML =
      "<td>" + esc(m.label) + "</td>" +
      "<td>" + esc(m.lens)  + "</td>" +
      "<td class='mono'>" + esc(m.frequency) + "</td>" +
      "<td class='mono'>" + esc(m.latest_period || "—") + "</td>" +
      "<td>" + (m.n_observations || 0) + "</td>" +
      "<td>" + originBadge + "</td>";
    tbodyExt.appendChild(tr);
  });
  if (!extMeta.length) {
    tbodyExt.innerHTML = "<tr><td colspan='6' class='empty'>No external indicators loaded.</td></tr>";
  }

  // ── 03 association ───────────────────────────────────────────────────────────
  var tbodyAssoc = el("tbody-assoc");

  // Group: non-finding rows first, then by objective + indicator
  var nfRows     = assoc.filter(function (r) { return r.n === 0 || r.n === null; });
  var assocRows  = assoc.filter(function (r) { return r.n > 0; });

  nfRows.forEach(function (r) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + esc(r.objective_id) + "</td>" +
      "<td colspan='7' class='text-muted'><em>" + esc(r.note || "Skipped — see note") + "</em></td>" +
      "<td></td>";
    tbodyAssoc.appendChild(tr);
  });

  assocRows.forEach(function (r) {
    var rVal = r.r !== null && r.r !== undefined ? parseFloat(r.r) : null;
    var pVal = r.p_bonferroni !== null ? parseFloat(r.p_bonferroni) : null;
    var rCls = rVal === null ? "corr-neu" : Math.abs(rVal) < 0.1 ? "corr-neu" : rVal > 0 ? "corr-pos" : "corr-neg";
    var pCls = pVal !== null && pVal < 0.05 ? " sig" : "";
    var ci   = (r.ci_lower !== null && r.ci_lower !== undefined)
               ? "[" + fmtRaw(r.ci_lower) + ", " + fmtRaw(r.ci_upper) + "]"
               : "N/A";
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + esc(r.objective_id) + "</td>" +
      "<td>" + esc(r.indicator_id) + "</td>" +
      "<td class='mono small'>" + esc(r.method) + "</td>" +
      "<td>" + (r.n !== null ? r.n : "—") + "</td>" +
      "<td class='" + rCls + "'>" + (rVal !== null ? fmtRaw(rVal, 3) : "N/A") + "</td>" +
      "<td class='mono small text-muted'>" + ci + "</td>" +
      "<td class='mono" + pCls + "'>" + (r.p_value !== null ? fmtRaw(r.p_value, 4) : "N/A") + "</td>" +
      "<td class='mono" + pCls + "'>" + (pVal !== null ? fmtRaw(pVal, 4) : "N/A") + "</td>" +
      "<td class='small text-muted'>" + esc(r.note || "") + "</td>";
    tbodyAssoc.appendChild(tr);
  });

  if (!assoc.length) {
    tbodyAssoc.innerHTML = "<tr><td colspan='9' class='empty'>No association results.</td></tr>";
  }

  // ── 04 quality ───────────────────────────────────────────────────────────────
  var tbodyQual = el("tbody-quality");
  quality.forEach(function (q) {
    var isBlock = q.severity === "excluded_from_analysis";
    var sevBadge = isBlock
      ? "<span class='badge badge-miss'>Excluded</span>"
      : "<span class='badge badge-info'>Info</span>";
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td class='mono small'>" + esc(q.quality_flag) + "</td>" +
      "<td>" + sevBadge + "</td>" +
      "<td>" + (q.row_count || 0) + "</td>" +
      "<td>" + (q.pct_of_rows !== null ? parseFloat(q.pct_of_rows).toFixed(2) + "%" : "—") + "</td>" +
      "<td class='small text-muted'>" + esc(q.treatment) + "</td>";
    tbodyQual.appendChild(tr);
  });
  if (!quality.length) {
    tbodyQual.innerHTML = "<tr><td colspan='5' class='empty'>No quality data.</td></tr>";
  }

  // ── 04 sources ───────────────────────────────────────────────────────────────
  var srcList = el("sources-list");
  sources.forEach(function (s) {
    var div = document.createElement("div");
    div.className = "source-card";
    var indHtml = (s.indicators || []).map(function (i) {
      return "<li class='small text-muted'><strong>" + esc(i.label) + "</strong> — " +
        esc(i.lens) + " · " + esc(i.frequency) + " · lag " + i.publication_lag_days + "d" +
        (i.docs_url ? " · <a href='" + esc(i.docs_url) + "' rel='noopener' target='_blank'>docs ↗</a>" : "") +
        "</li>";
    }).join("");
    div.innerHTML =
      "<h3>" + esc(s.name) + "</h3>" +
      "<a href='" + esc(s.url) + "' rel='noopener' target='_blank'>" + esc(s.url) + "</a>" +
      "<p>" + esc(s.licence) + "</p>" +
      (indHtml ? "<ul style='margin-top:.6rem;padding-left:1.1rem;list-style:disc'>" + indHtml + "</ul>" : "");
    srcList.appendChild(div);
  });

  // ── 04 methodology ───────────────────────────────────────────────────────────
  var methodList = el("method-list");
  (methodology.decisions || []).forEach(function (d) {
    var dt = document.createElement("dt");
    var dd = document.createElement("dd");
    dt.textContent = d.topic;
    dd.textContent = d.decision;
    methodList.appendChild(dt);
    methodList.appendChild(dd);
  });
  if (methodology.publication_lag_note) {
    el("pub-lag-note").innerHTML = "<strong>Publication lags:</strong> " + esc(methodology.publication_lag_note);
  }
  if (methodology.frequency_integrity) {
    el("freq-note").innerHTML = "<strong>Frequency integrity:</strong> " + esc(methodology.frequency_integrity);
  }

  // ── 04 trust tabs ────────────────────────────────────────────────────────────
  setupTabs(
    [el("tab-quality"), el("tab-sources"), el("tab-method")],
    [el("pane-quality"), el("pane-sources"), el("pane-method")]
  );

  // ── sticky nav highlighting ──────────────────────────────────────────────────
  var sections = ["explore","understand","challenge","trust"];
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        sections.forEach(function (id) {
          var a = el("nav-" + id);
          if (a) a.classList.toggle("active", id === entry.target.id);
        });
      }
    });
  }, { rootMargin: "-30% 0px -60% 0px" });
  sections.forEach(function (id) {
    var sec = el(id);
    if (sec) observer.observe(sec);
  });

  // ── generic tab helper ───────────────────────────────────────────────────────
  function setupTabs(tabs, panes) {
    tabs.forEach(function (btn, i) {
      btn.addEventListener("click", function () {
        tabs.forEach(function (b, j) {
          b.classList.toggle("active", j === i);
          b.setAttribute("aria-selected", j === i ? "true" : "false");
          if (panes[j]) panes[j].hidden = j !== i;
        });
      });
    });
  }
}());
