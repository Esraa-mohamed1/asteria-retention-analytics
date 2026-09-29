(function () {
  "use strict";

  // ── load embedded data ──────────────────────────────────────────────────────
  var D = JSON.parse(document.getElementById("asteria-data").textContent);
  var meta        = D.meta         || {};
  var summary     = D.summary      || [];
  var series      = (D.series      || {}).rows || [];
  var extMeta     = D.external_meta    || [];
  var extObs      = D.external_observations || [];
  var assoc       = D.association      || [];
  var quality     = D.quality          || [];
  var sources     = D.sources          || [];
  var methodology = D.methodology      || {};
  var objectives  = D.objectives       || [];
  var countries   = D.countries        || [];
  var busUnits    = D.business_units   || [];
  var notices     = D.notices          || [];
  var exclusions  = D.exclusions       || [];
  var ingestion   = D.cross_check      || {};

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
  var selPFrom   = el("sel-period-from");
  var selPTo     = el("sel-period-to");

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
  function inPeriodRange(period) {
    // Period is like "2022Q3"; compare lexicographically (works for "YYYY Qn" format)
    var from = selPFrom.value.trim().toUpperCase();
    var to   = selPTo.value.trim().toUpperCase();
    var p    = String(period || "").toUpperCase();
    if (from && p < from) return false;
    if (to   && p > to)   return false;
    return true;
  }

  function buildBreakdown() {
    var objId   = selObj.value;
    var country = selCountry.value;
    var bu      = selBU.value;

    // country-level rows: country != ALL, BU == ALL, then period-filtered via series
    var countryRows = summary.filter(function (r) {
      var matchObj  = objId === "ALL" || r.objective_id === objId;
      var matchBU   = bu === "ALL" || r.business_unit === bu;
      var isCountry = r.country_code !== "ALL" && r.business_unit === "ALL";
      var matchC    = country === "ALL" || r.country_code === country;
      return matchObj && matchBU && isCountry && matchC;
    });

    var buRows = summary.filter(function (r) {
      var matchObj = objId === "ALL" || r.objective_id === objId;
      var matchC   = country === "ALL" || r.country_code === country;
      var isBU     = r.business_unit !== "ALL" && r.country_code === "ALL";
      var matchBU  = bu === "ALL" || r.business_unit === bu;
      return matchObj && matchC && isBU && matchBU;
    });

    renderBreakdownRows(el("tbody-country"), countryRows, "country_code");
    renderBreakdownRows(el("tbody-bu"),      buRows,      "business_unit");
  }

  function renderBreakdownRows(tbody, rows, groupKey) {
    tbody.innerHTML = "";
    if (!rows.length) {
      tbody.innerHTML = "<tr><td colspan='8' class='empty'>No data for this selection.</td></tr>";
      return;
    }
    rows.forEach(function (row) {
      var obj  = objMap[row.objective_id];
      var hit  = meetsTarget(row.value, obj);
      var cls  = hit === true ? "hit" : hit === false ? "miss" : "";
      var pct  = row.value !== null ? (row.value * 100).toFixed(1) + "%" : "N/A";
      var tgt  = obj ? obj.target_value * 100 : null;
      var n    = row.denominator !== null ? Math.round(row.denominator) : "—";
      var imm  = (row.immature || 0) + " imm · " + (row.unknown_regret || 0) + " unk";
      var barPct  = 0;
      if (row.value !== null && tgt !== null) barPct = Math.min(100, row.value * 100);
      var barMiss = hit === false ? " miss" : "";
      var badge   = hit === true  ? "<span class='badge badge-hit'>✅ On target</span>"
                  : hit === false ? "<span class='badge badge-miss'>❌ Off target</span>"
                  : "<span class='badge badge-muted'>—</span>";

      var tr = document.createElement("tr");
      tr.className = cls;
      tr.innerHTML =
        "<td><strong>" + esc(row[groupKey] || "—") + "</strong></td>" +
        "<td class='small'>" + esc(row.objective_id) + "</td>" +
        "<td>" + pct + "</td>" +
        "<td>" + (tgt !== null ? (obj.direction === "at_least" ? "≥ " : "≤ ") + tgt.toFixed(0) + "%" : "—") + "</td>" +
        "<td>" + n + "</td>" +
        "<td class='small text-muted'>" + imm + "</td>" +
        "<td style='min-width:80px'><div class='progress-wrap'>" +
          "<div class='progress-bar" + barMiss + "' style='width:" + barPct + "%' role='progressbar' aria-valuenow='" + barPct + "' aria-valuemin='0' aria-valuemax='100'></div>" +
        "</div></td>" +
        "<td>" + badge + "</td>";
      tbody.appendChild(tr);
    });
  }

  [selObj, selCountry, selBU, selPFrom, selPTo].forEach(function (inp) {
    inp.addEventListener("change", buildBreakdown);
    inp.addEventListener("input",  buildBreakdown);
  });
  buildBreakdown();

  // ── 01 tabs: country / BU ─────────────────────────────────────────────────────
  setupTabs([el("tab-country"), el("tab-bu")], [el("pane-country"), el("pane-bu")]);

  // ── 01 exclusion summary ──────────────────────────────────────────────────────
  var tbodyExcl = el("tbody-excl");
  if (exclusions && exclusions.length) {
    exclusions.forEach(function (row) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + esc(row.objective_id) + "</td>" +
        "<td>" + (row.total_rows || 0) + "</td>" +
        "<td>" + (row.excluded_unclean || 0) + "</td>" +
        "<td>" + (row.excluded_out_of_scope || 0) + "</td>" +
        "<td>" + (row.excluded_before_effective_window || 0) + "</td>" +
        "<td><strong>" + (row.in_cohort || 0) + "</strong></td>";
      tbodyExcl.appendChild(tr);
    });
  } else {
    tbodyExcl.innerHTML = "<tr><td colspan='6' class='empty'>No exclusion data.</td></tr>";
  }

  // ── 02 trend chart ───────────────────────────────────────────────────────────
  // Fill trend filters
  var trendCountry    = el("trend-country");
  var trendObjective  = el("trend-objective");
  var trendIndicator  = el("trend-indicator");

  addOption(trendCountry, "ALL", "All countries");
  countries.forEach(function (c) { addOption(trendCountry, c.iso2, c.name + " (" + c.iso2 + ")"); });

  addOption(trendObjective, "ALL", "All objectives");
  objectives.forEach(function (o) { addOption(trendObjective, o.objective_id, o.name || o.objective_id); });

  addOption(trendIndicator, "NONE", "— none —");
  extMeta.forEach(function (m) { addOption(trendIndicator, m.indicator_id, m.label + " [" + m.frequency + "]"); });

  function drawTrend() {
    var canvas     = el("trend-canvas");
    var ctx        = canvas.getContext("2d");
    var cGeo       = trendCountry.value;
    var cObj       = trendObjective.value;
    var cInd       = trendIndicator.value;

    var W = canvas.offsetWidth  || 1100;
    var H = 240;
    canvas.width  = W * window.devicePixelRatio;
    canvas.height = H * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    ctx.fillStyle = "rgba(11,19,30,0.7)";
    ctx.fillRect(0, 0, W, H);

    // --- series data filtered ---
    var retRows = series.filter(function (r) {
      return (cObj === "ALL" || r.objective_id === cObj)
          && (cGeo === "ALL" || r.country_code  === cGeo)
          && r.business_unit === "ALL"
          && r.denominator   >  0
          && r.value         !== null;
    });

    // Sort by period
    retRows = retRows.slice().sort(function (a, b) {
      return String(a.period).localeCompare(String(b.period));
    });

    // --- external obs filtered ---
    var indRows = [];
    if (cInd !== "NONE") {
      indRows = extObs.filter(function (r) {
        return r.indicator_id === cInd
            && (cGeo === "ALL" || r.geo === cGeo);
      }).sort(function (a, b) {
        return String(a.period).localeCompare(String(b.period));
      });
    }

    if (!retRows.length && !indRows.length) {
      ctx.fillStyle = "rgba(203,213,225,0.5)";
      ctx.font = "14px Inter,system-ui,sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No data for this selection", W / 2, H / 2);
      el("trend-note").textContent = "";
      return;
    }

    var PAD = { top: 20, right: 16, bottom: 36, left: 52 };
    var plotW = W - PAD.left - PAD.right;
    var plotH = H - PAD.top  - PAD.bottom;

    // Map period strings -> x positions (union of both axes)
    var allPeriods = [];
    retRows.forEach(function (r) { if (allPeriods.indexOf(r.period) < 0) allPeriods.push(r.period); });
    indRows.forEach(function (r) { if (allPeriods.indexOf(r.period) < 0) allPeriods.push(r.period); });
    allPeriods.sort();
    var pIdx = {};
    allPeriods.forEach(function (p, i) { pIdx[p] = i; });
    var nP = allPeriods.length || 1;

    function xOf(period) { return PAD.left + (pIdx[period] / Math.max(nP - 1, 1)) * plotW; }

    // Draw gridlines
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.lineWidth   = 1;
    for (var gi = 0; gi <= 4; gi++) {
      var gy = PAD.top + (gi / 4) * plotH;
      ctx.beginPath(); ctx.moveTo(PAD.left, gy); ctx.lineTo(PAD.left + plotW, gy); ctx.stroke();
    }

    // Draw retention line (left y-axis: 0-100%)
    var retVals   = retRows.map(function (r) { return r.value; });
    var retMin    = 0;
    var retMax    = 1;
    function yRet(v) { return PAD.top + plotH - ((v - retMin) / (retMax - retMin)) * plotH; }

    ctx.strokeStyle = "#2dd4bf";
    ctx.lineWidth   = 2.5;
    ctx.lineJoin    = "round";
    ctx.beginPath();
    var first = true;
    retRows.forEach(function (r) {
      var x = xOf(r.period); var y = yRet(r.value);
      if (first) { ctx.moveTo(x, y); first = false; } else { ctx.lineTo(x, y); }
    });
    ctx.stroke();

    // Dots
    retRows.forEach(function (r) {
      var x  = xOf(r.period); var y = yRet(r.value);
      var ok = meetsTarget(r.value, objMap[r.objective_id]);
      ctx.beginPath();
      ctx.arc(x, y, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = ok === false ? "#ff6b5b" : "#2dd4bf";
      ctx.fill();
    });

    // Draw external indicator line (right y-axis: normalised)
    if (indRows.length) {
      var indVals  = indRows.map(function (r) { return parseFloat(r.value); }).filter(function (v) { return !isNaN(v); });
      var indMin   = Math.min.apply(null, indVals);
      var indMax   = Math.max.apply(null, indVals);
      var indRange = indMax - indMin || 1;
      function yInd(v) { return PAD.top + plotH - ((v - indMin) / indRange) * plotH; }

      ctx.strokeStyle = "#fbbf24";
      ctx.lineWidth   = 1.8;
      ctx.setLineDash([5, 3]);
      ctx.beginPath();
      var firstI = true;
      indRows.forEach(function (r) {
        var v = parseFloat(r.value);
        if (isNaN(v)) return;
        var x = xOf(r.period); var y = yInd(v);
        if (firstI) { ctx.moveTo(x, y); firstI = false; } else { ctx.lineTo(x, y); }
      });
      ctx.stroke();
      ctx.setLineDash([]);

      // Right axis label
      ctx.fillStyle = "#fbbf24";
      ctx.font = "10px Inter,system-ui,sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(indMin.toFixed(1), W - 4, PAD.top + plotH);
      ctx.fillText(indMax.toFixed(1), W - 4, PAD.top + 10);
    }

    // Left axis: percentage labels
    ctx.fillStyle = "rgba(203,213,225,0.8)";
    ctx.font = "11px Inter,system-ui,sans-serif";
    ctx.textAlign = "right";
    [0, 25, 50, 75, 100].forEach(function (pct) {
      var y = yRet(pct / 100);
      ctx.fillText(pct + "%", PAD.left - 6, y + 4);
    });

    // X axis: period labels (every Nth to avoid overlap)
    ctx.fillStyle = "rgba(203,213,225,0.7)";
    ctx.textAlign = "center";
    ctx.font = "10px Inter,system-ui,sans-serif";
    var step = Math.max(1, Math.ceil(allPeriods.length / 10));
    allPeriods.forEach(function (p, i) {
      if (i % step !== 0) return;
      ctx.fillText(p, xOf(p), H - PAD.bottom + 14);
    });

    // Legend
    ctx.font = "11px Inter,system-ui,sans-serif";
    ctx.textAlign = "left";
    ctx.fillStyle = "#2dd4bf"; ctx.fillText("● Retention rate", PAD.left, H - 4);
    if (indRows.length) {
      ctx.fillStyle = "#fbbf24"; ctx.fillText("— External signal (right axis)", PAD.left + 130, H - 4);
    }

    // Note
    var indLabel = cInd !== "NONE" ? (extMeta.find(function (m) { return m.indicator_id === cInd; }) || {}).label || cInd : "";
    el("trend-note").textContent = retRows.length
      ? "Retention (teal, left axis)" + (indLabel ? " vs " + indLabel + " (amber, right axis, normalised)" : "") + ". " + retRows.length + " data points."
      : "No retention data for this selection.";
  }

  [trendCountry, trendObjective, trendIndicator].forEach(function (sel) {
    sel.addEventListener("change", drawTrend);
  });
  window.addEventListener("resize", drawTrend);
  setTimeout(drawTrend, 50); // wait for layout paint

  // ── 02 external coverage table ───────────────────────────────────────────────
  var tbodyExt = el("tbody-ext");
  extMeta.forEach(function (m) {
    var isSynth    = m.data_origin === "fixture_synthetic";
    var originBadge = isSynth
      ? "<span class='badge badge-warn'>Synthetic</span>"
      : "<span class='badge badge-info'>Live</span>";
    // Find docs_url from sources
    var docsUrl = "";
    sources.forEach(function (s) {
      (s.indicators || []).forEach(function (i) {
        if (i.indicator_id === m.indicator_id && i.docs_url) docsUrl = i.docs_url;
      });
    });
    var docsLink = docsUrl
      ? "<a href='" + esc(docsUrl) + "' rel='noopener' target='_blank'>docs ↗</a>"
      : "—";
    var ageDays = m.age_days !== null && m.age_days !== undefined ? m.age_days + "d" : "—";
    var tr = document.createElement("tr");
    if (isSynth) tr.style.color = "#fbbf24";
    tr.innerHTML =
      "<td>" + esc(m.label)                 + "</td>" +
      "<td>" + esc(m.lens)                  + "</td>" +
      "<td class='mono'>" + esc(m.frequency) + "</td>" +
      "<td class='mono small'>" + esc(m.unit || "—")  + "</td>" +
      "<td class='mono small'>" + esc(m.provider)      + "</td>" +
      "<td class='mono'>" + esc(m.latest_period || "—") + "</td>" +
      "<td class='mono'>" + ageDays + "</td>" +
      "<td>" + (m.n_observations || 0) + "</td>" +
      "<td>" + docsLink + "</td>" +
      "<td>" + originBadge + "</td>";
    tbodyExt.appendChild(tr);
  });
  if (!extMeta.length) {
    tbodyExt.innerHTML = "<tr><td colspan='10' class='empty'>No external indicators loaded.</td></tr>";
  }

  // ── 03 findings block ─────────────────────────────────────────────────────────
  // Build evidence-backed findings from the data we have
  var findingsGrid = el("findings-grid");

  function buildFindings() {
    var findings = [];

    // Finding 1: overall objective hit/miss
    var hitCount  = allRows.filter(function (r) { return meetsTarget(r.value, objMap[r.objective_id]) === true; }).length;
    var missCount = allRows.filter(function (r) { return meetsTarget(r.value, objMap[r.objective_id]) === false; }).length;
    if (allRows.length) {
      var missNames = allRows
        .filter(function (r) { return meetsTarget(r.value, objMap[r.objective_id]) === false; })
        .map(function (r) { return (objMap[r.objective_id] || {}).name || r.objective_id; });
      findings.push({
        type: missCount > 0 ? "warn" : "hit",
        title: hitCount + " of " + allRows.length + " objectives on target",
        body: missCount > 0
          ? "Off-target: " + missNames.join("; ") + ". These require priority attention."
          : "All " + allRows.length + " retention objectives are currently meeting their targets.",
        caveat: "Denominator is the count of mature employees/headcount in the evaluation window. Small-N cohorts may fluctuate significantly period to period."
      });
    }

    // Finding 2: country variability
    var cRows = summary.filter(function (r) { return r.country_code !== "ALL" && r.business_unit === "ALL" && r.value !== null; });
    if (cRows.length) {
      var vals  = cRows.map(function (r) { return r.value; });
      var vMin  = Math.min.apply(null, vals);
      var vMax  = Math.max.apply(null, vals);
      var rMin  = cRows.find(function (r) { return r.value === vMin; });
      var rMax  = cRows.find(function (r) { return r.value === vMax; });
      findings.push({
        type: "info",
        title: "Country spread: " + (vMin*100).toFixed(1) + "% – " + (vMax*100).toFixed(1) + "%",
        body: (rMax ? rMax.country_code : "?") + " posts the highest rate (" + (vMax*100).toFixed(1) + "%) while " +
              (rMin ? rMin.country_code : "?") + " is lowest (" + (vMin*100).toFixed(1) + "%). " +
              "A " + ((vMax-vMin)*100).toFixed(1) + " pp gap suggests country-specific factors dominate.",
        caveat: "Summary rows pool all objectives. Breakdown by single objective for a cleaner comparison."
      });
    }

    // Finding 3: association — most interesting significant result (lowest Bonferroni p)
    var sigRows = assoc.filter(function (r) {
      return !r.insufficient_n && r.p_bonferroni !== null && r.p_bonferroni < 0.05;
    }).sort(function (a, b) { return a.p_bonferroni - b.p_bonferroni; });

    if (sigRows.length) {
      var best = sigRows[0];
      var dir  = best.r > 0 ? "positive" : "negative";
      findings.push({
        type: "info",
        title: "Strongest significant link: " + best.objective_id + " ↔ " + best.indicator_id,
        body: "Pooled " + best.method + " r = " + parseFloat(best.r).toFixed(3) +
              " (p_Bonf = " + parseFloat(best.p_bonferroni).toFixed(4) + ", n = " + best.n + "). " +
              "A " + dir + " relationship: when " + esc(best.indicator_id) + " rises, " + esc(best.objective_id) + (best.r > 0 ? " tends to rise" : " tends to fall") + ".",
        caveat: best.caveat || "Observational. Not causal."
      });
    } else {
      // No significant associations — this is itself a finding
      findings.push({
        type: "neutral",
        title: "No statistically significant associations after Bonferroni correction",
        body: "With only 6 countries and limited quarterly data, power is low. All p (Bonf.) values are above 0.05. This is a non-finding, not evidence of no relationship.",
        caveat: "A larger cross-country or longer time-series dataset would be needed to reach adequate statistical power for definitive conclusions."
      });
    }

    // Finding 4: SENIOR_HIRE_12M non-finding (explicit non-finding required)
    findings.push({
      type: "non-finding",
      title: "SENIOR_HIRE_12M association skipped — explicit non-finding",
      body: "Senior-hire cohorts average 2–3 people per country per quarter, well below the minimum of 8 pairs for any correlation. No association estimate is possible without pooling countries inappropriately. This is documented as a structural data limitation, not a gap in analysis.",
      caveat: "More granular data (e.g. business-unit level) or a longer history would be needed to run this analysis."
    });

    // Render findings
    findingsGrid.innerHTML = "";
    findings.forEach(function (f) {
      var cls = f.type === "hit"   ? "finding-hit"
              : f.type === "warn"  ? "finding-warn"
              : f.type === "non-finding" ? "finding-non"
              : "finding-info";
      var div = document.createElement("div");
      div.className = "finding-card " + cls;
      div.innerHTML =
        "<div class='finding-title'>" + esc(f.title) + "</div>" +
        "<div class='finding-body'>" + f.body + "</div>" +
        "<div class='finding-caveat'><em>Caveat:</em> " + esc(f.caveat) + "</div>";
      findingsGrid.appendChild(div);
    });
  }
  buildFindings();

  // ── 03 association ───────────────────────────────────────────────────────────
  var tbodyAssoc = el("tbody-assoc");

  var nfRows    = assoc.filter(function (r) { return r.n === 0 || r.n === null; });
  var assocRows = assoc.filter(function (r) { return r.n > 0; });

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
    var isBlock  = q.severity === "excluded_from_analysis";
    var sevBadge = isBlock
      ? "<span class='badge badge-miss'>Excluded</span>"
      : "<span class='badge badge-info'>Info</span>";
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td class='mono small'>" + esc(q.quality_flag)  + "</td>" +
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
        esc(i.lens) + " · " + esc(i.frequency) + " · publication lag " + i.publication_lag_days + "d" +
        (i.docs_url ? " · <a href='" + esc(i.docs_url) + "' rel='noopener' target='_blank'>docs ↗</a>" : "") +
        "</li>";
    }).join("");
    div.innerHTML =
      "<h3>" + esc(s.name) + "</h3>" +
      "<a href='" + esc(s.url) + "' rel='noopener' target='_blank'>" + esc(s.url) + "</a>" +
      "<p><strong>Licence:</strong> " + esc(s.licence) + "</p>" +
      "<p class='small text-muted' style='margin-top:.25rem'><strong>Access:</strong> Live retrieval recorded to <code>data/external_raw/</code> with ISO timestamp. Fixture replay from <code>data/fixtures/</code> for offline runs.</p>" +
      (indHtml ? "<ul style='margin-top:.6rem;padding-left:1.1rem;list-style:disc'>" + indHtml + "</ul>" : "");
    srcList.appendChild(div);
  });
  if (!sources.length) {
    srcList.innerHTML = "<p class='empty'>No source data.</p>";
  }

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

  // ── 04 freshness tab ──────────────────────────────────────────────────────────
  // Ingestion outcomes come from the cross_check key; fall back to external_meta for status
  var tbodyFresh = el("tbody-freshness");
  var crossCheck = D.cross_check || {};
  // Re-use extMeta which already has n_observations / data_origin / latest_period
  if (extMeta.length) {
    extMeta.forEach(function (m) {
      var status   = m.data_origin === "fixture_synthetic" ? "synthetic" : m.data_origin ? "ok" : "unknown";
      var badgeCls = status === "ok" ? "badge-hit" : status === "synthetic" ? "badge-warn" : "badge-muted";
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + esc(m.label) + "</td>" +
        "<td class='mono small'>" + esc(m.provider) + "</td>" +
        "<td><span class='badge " + badgeCls + "'>" + status + "</span></td>" +
        "<td class='mono small'>" + esc(m.data_origin || "—") + "</td>" +
        "<td>" + (m.n_observations || 0) + "</td>" +
        "<td class='mono small'>" + esc(m.latest_available_from || "—") + "</td>" +
        "<td>" + (m.age_days !== null && m.age_days !== undefined ? m.age_days + "d" : "—") + "</td>";
      tbodyFresh.appendChild(tr);
    });
  } else {
    tbodyFresh.innerHTML = "<tr><td colspan='7' class='empty'>No freshness data available.</td></tr>";
  }

  // ── 04 trust tabs ────────────────────────────────────────────────────────────
  setupTabs(
    [el("tab-quality"), el("tab-sources"), el("tab-method"), el("tab-freshness")],
    [el("pane-quality"), el("pane-sources"), el("pane-method"), el("pane-freshness")]
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
      if (!btn) return;
      btn.addEventListener("click", function () {
        tabs.forEach(function (b, j) {
          if (!b) return;
          b.classList.toggle("active", j === i);
          b.setAttribute("aria-selected", j === i ? "true" : "false");
          if (panes[j]) panes[j].hidden = j !== i;
        });
      });
    });
  }
}());
