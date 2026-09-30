"""Dashboard HTML builder.

Reads dashboard/src/{template.html, app.js, styles.css}, inlines CSS + JS +
JSON data into a single self-contained dashboard/index.html that works from
file:// without a web server.

The JSON is embedded as:
    <script id="asteria-data" type="application/json">...</script>

Any </script> inside JSON strings must be escaped to prevent the browser's
HTML parser from ending the script block early. Use _escape_script() for this.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DASHBOARD_SRC = Path(__file__).resolve().parents[3] / "dashboard" / "src"
DASHBOARD_OUT = Path(__file__).resolve().parents[3] / "dashboard" / "index.html"


def _escape_script(json_str: str) -> str:
    """Escape <\\/script> inside a JSON string embedded in HTML."""
    return json_str.replace("</", "<\\/")


def build_dashboard(payload: dict, output_path: Path | None = None) -> Path:  # type: ignore[type-arg]
    """Inline CSS + JS + data into a single HTML file."""
    out_path = output_path or DASHBOARD_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data_json = json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=None)
    data_json_escaped = _escape_script(data_json)

    template_path = DASHBOARD_SRC / "template.html"
    js_path = DASHBOARD_SRC / "app.js"
    css_path = DASHBOARD_SRC / "styles.css"

    if template_path.exists() and js_path.exists() and css_path.exists():
        template = template_path.read_text(encoding="utf-8")
        js_content = js_path.read_text(encoding="utf-8")
        css_content = css_path.read_text(encoding="utf-8")
        html = template
        html = html.replace("/* INLINE_CSS */", css_content)
        html = html.replace("// INLINE_JS", js_content)
        html = html.replace("/* INLINE_DATA */", data_json_escaped)
    else:
        logger.warning("dashboard/src/ not found — writing minimal placeholder HTML")
        html = _minimal_html(data_json_escaped, payload)

    out_path.write_text(html, encoding="utf-8")
    logger.info("Dashboard written to %s (%d bytes)", out_path, len(html.encode("utf-8")))
    return out_path


def _fmt(val: object, fmt: str) -> str:
    """Format a numeric value or return 'N/A' if None."""
    if val is None:
        return "N/A"
    try:
        return format(float(val), fmt)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "N/A"


def _assoc_row(r: dict) -> str:  # type: ignore[type-arg]
    """Build one HTML table row for an association result."""
    return (
        "<tr>"
        "<td>" + str(r.get("objective_id", "")) + "</td>"
        "<td>" + str(r.get("indicator_id", "")) + "</td>"
        "<td>" + str(r.get("method", "")) + "</td>"
        "<td>" + str(r.get("n", "")) + "</td>"
        "<td>" + _fmt(r.get("r"), ".3f") + "</td>"
        "<td>" + _fmt(r.get("ci_lower"), ".3f") + "</td>"
        "<td>" + _fmt(r.get("ci_upper"), ".3f") + "</td>"
        "<td>" + _fmt(r.get("p_value"), ".4f") + "</td>"
        "<td>" + _fmt(r.get("p_bonferroni"), ".4f") + "</td>"
        "<td>" + str(r.get("note", "")) + "</td>"
        "</tr>"
    )


def _minimal_html(data_json_escaped: str, payload: dict) -> str:  # type: ignore[type-arg]
    """Fallback minimal dashboard with the full data payload embedded."""
    # Pre-compute all variable parts to avoid {{}} dict-in-f-string errors
    meta = payload.get("meta") or {}
    as_of_str = str(meta.get("as_of", ""))
    source_str = str(meta.get("source_mode", ""))
    run_str = str(meta.get("run_timestamp", ""))

    methodology = payload.get("methodology") or {}
    pub_lag_note = str(methodology.get("publication_lag_note", ""))
    freq_integrity = str(methodology.get("frequency_integrity", ""))

    decisions_html = "".join(
        "<dt style='font-weight:600;margin-top:.5rem'>" + str(d.get("topic", "")) + "</dt>"
        "<dd style='color:var(--muted);font-size:.85rem'>" + str(d.get("decision", "")) + "</dd>"
        for d in methodology.get("decisions", [])
    )

    sources_html = "".join(
        "<div style='margin-bottom:.75rem'><strong>" + str(s.get("name", "")) + "</strong> &mdash; "
        "<a href='" + str(s.get("url", "")) + "' rel='noopener'>" + str(s.get("url", "")) + "</a><br>"
        "<span style='font-size:.8rem;color:var(--muted)'>" + str(s.get("licence", "")) + "</span></div>"
        for s in payload.get("sources", [])
    )

    ext_meta_html = "".join(
        "<tr style='color:" + ("#f39c12" if m.get("data_origin") == "fixture_synthetic" else "inherit") + "'>"
        "<td>" + str(m.get("label", "")) + "</td>"
        "<td>" + str(m.get("lens", "")) + "</td>"
        "<td>" + str(m.get("frequency", "")) + "</td>"
        "<td>" + str(m.get("latest_period") or "N/A") + "</td>"
        "<td>" + str(m.get("data_origin") or "N/A") + "</td>"
        "<td>" + str(m.get("n_observations", 0)) + "</td></tr>"
        for m in payload.get("external_meta", [])
    )

    quality_html = "".join(
        "<tr>"
        "<td>" + str(q.get("quality_flag", "")) + "</td>"
        "<td>" + str(q.get("severity", "")) + "</td>"
        "<td>" + str(q.get("row_count", 0)) + "</td>"
        "<td>" + str(round(float(q.get("pct_of_rows") or 0), 2)) + "%</td>"
        "<td>" + str(q.get("treatment", "")) + "</td></tr>"
        for q in payload.get("quality", [])
    )

    assoc_html = "".join(_assoc_row(r) for r in payload.get("association", []))

    summary_rows = ""
    for row in payload.get("summary", []):
        if row.get("country_code") == "ALL" and row.get("business_unit") == "ALL":
            val = row.get("value")
            val_str = f"{val:.1%}" if val is not None else "N/A"
            target = row.get("target_value", "")
            status = row.get("status_text", "")
            summary_rows += (
                "<tr>"
                "<td>" + str(row.get("objective_id", "")) + "</td>"
                "<td>" + val_str + "</td>"
                "<td>" + str(target) + "</td>"
                "<td>" + str(row.get("numerator", "")) + "</td>"
                "<td>" + str(row.get("denominator", "")) + "</td>"
                "<td>" + status + "</td></tr>\n"
            )

    notices_html = ""
    for notice in payload.get("notices", []):
        color = "#c0392b" if notice.get("level") == "warning" else "#2980b9"
        notices_html += (
            "<div role='alert' style='background:" + color + ";color:#fff;"
            "padding:12px;border-radius:4px;margin-bottom:8px'>"
            + str(notice.get("message", "")) + "</div>\n"
        )

    return (
        "<!DOCTYPE html>\n"
        "<html lang='en'>\n"
        "<head>\n"
        "<meta charset='UTF-8'>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        "<title>Asteria Retention — Analytics Dashboard</title>\n"
        "<meta name='description' content='Retention objectives and external "
        "labour market signals for Asteria Consumer Products'>\n"
        "<style>\n"
        "  :root{--primary:#1a1a2e;--accent:#e94560;--card:#16213e;--text:#eee;--muted:#aaa}\n"
        "  *{box-sizing:border-box;margin:0;padding:0}\n"
        "  body{font-family:system-ui,sans-serif;background:var(--primary);color:var(--text);padding:1.5rem}\n"
        "  a:focus-visible{outline:3px solid var(--accent);outline-offset:2px}\n"
        "  h1{font-size:1.6rem;margin-bottom:0.4rem}\n"
        "  .subtitle{color:var(--muted);font-size:.85rem;margin-bottom:1.5rem}\n"
        "  table{border-collapse:collapse;width:100%;font-size:.85rem}\n"
        "  th,td{border:1px solid #333;padding:.5rem .75rem;text-align:left}\n"
        "  th{background:var(--card);color:var(--muted)}\n"
        "  section{margin-bottom:2rem}\n"
        "  .skip-link{position:absolute;left:-999px;top:auto;width:1px;height:1px;overflow:hidden}\n"
        "  .skip-link:focus{left:0;top:0;width:auto;height:auto;padding:.5rem 1rem;"
        "background:var(--accent);color:#fff;z-index:9999}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<a href='#main-content' class='skip-link'>Skip to main content</a>\n"
        "<header role='banner'>\n"
        "  <h1>Asteria Retention Analytics</h1>\n"
        "  <p class='subtitle'>As-of: " + as_of_str + " &middot; Source: " + source_str
        + " &middot; Run: " + run_str + "</p>\n"
        "</header>\n"
        + notices_html
        + "<main id='main-content'>\n"
        "<nav aria-label='Dashboard sections'>\n"
        "  <ul style='display:flex;gap:1rem;list-style:none;margin-bottom:1.5rem;flex-wrap:wrap'>\n"
        "    <li><a href='#explore'>Explore</a></li>\n"
        "    <li><a href='#understand'>Understand</a></li>\n"
        "    <li><a href='#challenge'>Challenge</a></li>\n"
        "    <li><a href='#trust'>Trust</a></li>\n"
        "  </ul>\n"
        "</nav>\n"
        "<section id='explore' aria-labelledby='explore-heading'>\n"
        "<h2 id='explore-heading'>Explore &mdash; Objective Status</h2>\n"
        "<div style='overflow-x:auto'><table aria-label='Objective summary'>\n"
        "<caption>Retention objectives &mdash; all countries combined</caption>\n"
        "<thead><tr><th>Objective</th><th>Value</th><th>Target</th>"
        "<th>Numerator</th><th>Denominator</th><th>Status</th></tr></thead>\n"
        "<tbody>\n" + summary_rows + "</tbody></table></div>\n"
        "</section>\n"
        "<section id='understand' aria-labelledby='understand-heading' style='margin-top:2rem'>\n"
        "<h2 id='understand-heading'>Understand &mdash; External Indicators</h2>\n"
        "<div style='overflow-x:auto'><table aria-label='External indicator coverage'>\n"
        "<caption>External indicators (orange = synthetic fixture data)</caption>\n"
        "<thead><tr><th>Indicator</th><th>Lens</th><th>Frequency</th>"
        "<th>Latest period</th><th>Origin</th><th>Observations</th></tr></thead>\n"
        "<tbody>\n" + ext_meta_html + "</tbody></table></div>\n"
        "</section>\n"
        "<section id='challenge' aria-labelledby='challenge-heading' style='margin-top:2rem'>\n"
        "<h2 id='challenge-heading'>Challenge &mdash; Association Analysis</h2>\n"
        "<p style='color:var(--muted);font-size:.8rem;margin:.5rem 0'>"
        "Observational only. Correlation does not imply causation. "
        "Synthetic data results are for demonstration only.</p>\n"
        "<div style='overflow-x:auto'><table aria-label='Association results'>\n"
        "<caption>Pearson / Spearman / within-country correlations</caption>\n"
        "<thead><tr><th>Objective</th><th>Indicator</th><th>Method</th><th>n</th><th>r</th>"
        "<th>CI lower</th><th>CI upper</th><th>p</th><th>p (Bonferroni)</th><th>Note</th></tr></thead>\n"
        "<tbody>\n" + assoc_html + "</tbody></table></div>\n"
        "</section>\n"
        "<section id='trust' aria-labelledby='trust-heading' style='margin-top:2rem'>\n"
        "<h2 id='trust-heading'>Trust &mdash; Data Quality &amp; Sources</h2>\n"
        "<h3 style='margin:1rem 0 .5rem'>Quality flags</h3>\n"
        "<div style='overflow-x:auto'><table aria-label='Quality flags'>\n"
        "<thead><tr><th>Flag</th><th>Severity</th><th>Count</th><th>%</th><th>Treatment</th></tr></thead>\n"
        "<tbody>\n" + quality_html + "</tbody></table></div>\n"
        "<h3 style='margin:1rem 0 .5rem'>Sources &amp; licences</h3>\n"
        + sources_html
        + "<h3 style='margin:1rem 0 .5rem'>Methodology</h3>\n"
        "<dl>\n" + decisions_html + "\n</dl>\n"
        "<p style='font-size:.8rem;color:var(--muted);margin-top:.75rem'>"
        "<strong>Publication lags:</strong> " + pub_lag_note + "</p>\n"
        "<p style='font-size:.8rem;color:var(--muted);margin-top:.4rem'>"
        "<strong>Frequency integrity:</strong> " + freq_integrity + "</p>\n"
        "</section>\n"
        "</main>\n"
        "<script id='asteria-data' type='application/json'>" + data_json_escaped + "</script>\n"
        "<script>\n"
        "const ASTERIA = JSON.parse(document.getElementById('asteria-data').textContent);\n"
        "console.log('Asteria data loaded:', ASTERIA.meta);\n"
        "</script>\n"
        "<footer role='contentinfo' style='margin-top:3rem;border-top:1px solid #333;"
        "padding-top:1rem;font-size:.75rem;color:var(--muted)'>\n"
        "  Asteria Consumer Products &mdash; Retention Analytics Assessment | Data as-of "
        + as_of_str + "\n"
        "</footer>\n"
        "</body>\n"
        "</html>"
    )
