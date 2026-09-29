# Asteria Retention Analytics — Software Emphasis

External labour-market signals × workforce retention: a reproducible data
product for Asteria Consumer Products (fictional), built for the
**software-emphasis** track of the Analytics & Insights engineering assessment.

---

## Problem

Leaders want to know whether public labour-market and macroeconomic signals
(unemployment, job vacancies, inflation, GDP, labour-force participation) can
meaningfully contextualise three workforce-retention objectives across six
European markets.

The brief deliberately left key terms undefined. The narrowing decisions are in
[`docs/requirements_refinement.md`](docs/requirements_refinement.md).

---

## Chosen scope

The full **Research → Ingest → Curate → Analyse → Explain** pipeline is
implemented end-to-end with software-emphasis depth:

- Clean adapter boundary for ingestion (one module owns the Eurostat API)
- World Bank as a second independent provider
- Resilient network handling (retries, backoff, partial-failure isolation)
- Typed, packaged, pip-installable codebase
- Automated tests (6 passing, covering the riskiest logic)
- Single-file dashboard with embedded data (no local server needed)
- Full source register, methodology log, and quality audit trail

What was deliberately **left out** — and why — is in
[`docs/requirements_refinement.md § Rejected scope`](docs/requirements_refinement.md#rejected-scope).

---

## Architecture

```
asteria-retention/
├── README.md                           # this file
├── AI_USAGE.md                         # tools, prompts, accepted/rejected, verification
├── pyproject.toml                      # packaging + dependencies (pip install -e ".[dev]")
├── docs/
│   ├── requirements_refinement.md      # questions, assumptions, definitions, decisions
│   ├── source_register.md              # providers, licences, indicators, cadence, lag, limits
│   ├── decisions_and_examples.md       # technical explainers with examples
│   └── architecture.md                # production ADF + Databricks + Power BI mapping
├── src/asteria_retention/
│   ├── config.py                       # paths, country map, indicators, publication lags (ONE place)
│   ├── cli.py                          # single pipeline entrypoint  (`python -m asteria_retention`)
│   ├── pipeline.py                     # stage orchestration (manifest → ingest → curate → metrics → report)
│   ├── ingestion/
│   │   ├── eurostat_client.py          # ONLY module that knows Eurostat's API
│   │   ├── worldbank_client.py         # ONLY module that knows the World Bank API
│   │   └── service.py                  # adapter dispatcher (picks client by provider)
│   ├── curate/canonicalize.py          # dirty CSV → quality-flagged canonical table
│   ├── domain/
│   │   ├── retention_metrics.py        # three objectives (cohort censoring, denominators)
│   │   └── temporal_alignment.py       # publication lag, no-future-leakage enforcement
│   ├── analysis/
│   │   ├── panel_builder.py            # as-of join: retention outcomes × external signals
│   │   ├── association_analysis.py     # Pearson / Spearman / within-country demeaned + Bonferroni
│   │   └── warehouse_validator.py      # DuckDB SQL cross-check (metrics reproduced in SQL)
│   └── reporting/
│       ├── dashboard_data.py           # payload builder → JSON embedded in dashboard
│       └── dashboard_build.py          # template.html + styles.css + app.js → index.html
├── dashboard/
│   ├── src/template.html               # four-section layout (Explore / Understand / Challenge / Trust)
│   ├── src/styles.css                  # high-contrast dark theme
│   ├── src/app.js                      # data binding + canvas trend chart + findings grid
│   └── index.html                      # GENERATED — open in any browser, no server needed
├── tests/
│   └── test_retention_pipeline.py      # 6 tests: manifest, curation, no-leakage, metric ranges,
│                                       #   non-findings recorded, SQL cross-check
├── data/
│   ├── raw/                            # official assessment files + manifest (SHA-256 verified)
│   ├── fixtures/                       # Eurostat/World Bank replay payloads (offline review)
│   ├── external_raw/                   # live API snapshots with ISO timestamps
│   └── curated/                        # GENERATED: canonical events, quality, series, association
└── presentation/presentation.md        # 15-minute deck + interview Q&A guide
```

**Data flow:**
```
data/raw (HR CSV)  ──►  curate (quality flags)  ──►  domain (metrics)  ──►┐
                                                                            ├──► dashboard
data/external_raw  ──►  ingestion (adapters)    ──►  temporal join    ──►──┘
  (Eurostat API /
   World Bank API /
   fixtures for offline)
```

---

## Prerequisites

```bash
pip install -e ".[dev]"    # Python 3.11+
```

---

## Running it

> [!TIP]
> All commands use `coke.bat` (cmd / double-click) or `.\coke.ps1` (PowerShell).
> No long Python commands needed — just `coke`.

| Command | What it does |
|---|---|
| `coke` | Full pipeline — offline fixtures, no network — **start here** |
| `coke live` | Full pipeline against live Eurostat + World Bank APIs |
| `coke test` | 6 automated tests only |
| `coke dash` | Rebuild `dashboard/index.html` only (after CSS/JS edits) |
| `coke open` | Open dashboard in default browser |
| `coke install` | `pip install -e ".[dev]"` |

After `coke`, open `dashboard/index.html` in any browser.
No local server required — data is embedded in the HTML.


---

## Outputs

After a run, `data/curated/` contains:

| File | Contents |
|---|---|
| `canonical_events.csv` | Quality-flagged HR rows (never deleted, always auditable) |
| `quality_report.csv` | One row per data-quality flag type: count, % of rows, treatment |
| `fact_objective_series.csv` | Metric values per objective × country × BU × period |
| `summary.csv` | Current status per objective × country × BU vs target |
| `association.csv` | Pearson / Spearman / within-country r, CI, p, Bonferroni p |
| `coverage.csv` | Which indicator × country series were loaded and their observation count |
| `analytics.duckdb` | DuckDB database for SQL cross-check |

`dashboard/index.html` — single self-contained HTML file, embeds all data.

---

## SQL demonstration

`warehouse_validator.py` runs real SQL (DuckDB) on every pipeline run:

1. **Independently recomputes `NEW_HIRE_6M`** in SQL and diffs against the pandas result — verified to match exactly (numerator and denominator agree to zero).
2. **GROUP BY** country summary of headcount and terminations.
3. **Window function** (`SUM(...) OVER (ORDER BY ...)`) — cumulative hire count by quarter.

All three queries are plain ANSI SQL and port to Databricks SQL / Spark SQL
with only trivial `CURRENT_DATE` → `'2025-12-31'::DATE` syntax changes.

---

## Key findings (current run, `--source fixtures`)

| Objective | Value | Target | Status |
|---|---|---|---|
| New-hire six-month retention | **87.1%** (n = 1,808 mature) | ≥ 86% | ✅ On target |
| Senior-hire twelve-month retention | **78.0%** (n = 259 mature) | ≥ 90% | ❌ **Off target** |
| Trailing regretted turnover (12 mo) | **5.1%** (n = 1,570) | ≤ 8% | ✅ On target |

**Why SENIOR_HIRE_12M misses by 12 pp:**  
57 of 259 mature Senior Leaders left within 12 months (median exit: 3.8 months
post-hire). The problem is structural — every country misses, every hire cohort
from 2021–2024 contributes similarly (17 / 15 / 13 / 12 exits). Bulgaria is
worst (72.0%), Italy best (82.9%). This is not a one-off quarter.

**Country spread:**  
All countries meet the new-hire and turnover targets. Romania is closest to
the edge on new-hire (80.0%). The 12–22 pp senior-hire gap is consistent
across all six markets.

**Explicit non-finding:**  
Association analysis between senior-hire retention and external indicators was
skipped — cohorts are 2–3 people per country-quarter, below the minimum of 8
pairs for any correlation. Documented in the dashboard Challenge section.

---

## Known limitations

- **Fixture data covers ≈3 years of synthetic-shape history.** Correlation
  results from a fixture run demonstrate pipeline mechanics, not real findings.
  Run `--source live` for real associations.
- **Publication-lag values are documented estimates**, not verified against
  Eurostat's live release calendar (offline build). Reconfirm before using the
  temporal join for a real decision.
- **No revision detection.** If Eurostat revises a previously-loaded monthly
  figure, the old value persists until a full re-ingest.
- **Static dashboard.** The output is a self-contained HTML file — appropriate
  for local review; not a live-refresh production service (see
  `docs/architecture.md` for the Power BI production path).
- **`Sr Mgmt` ambiguity.** 10 rows with `career_level = "Sr Mgmt"` are kept
  separate and excluded from `SENIOR_HIRE_12M`. If they are actually Senior
  Leaders, the denominator is understated by at most 10 hires — documented
  openly in `docs/requirements_refinement.md`.

---

## AI usage

See [`AI_USAGE.md`](AI_USAGE.md): which tools were used, what they produced,
what was rejected or corrected, and what risk remains for a human reviewer.
