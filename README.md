# Asteria retention pipeline — software emphasis

External signals × workforce retention: a small, reproducible data
product for Asteria Consumer Products (fictional), built for the
agentic engineering assessment's **software-emphasis** track.

## Problem

Leaders want to know whether external labour-market and macroeconomic
conditions (unemployment, job vacancies, inflation) can meaningfully
contextualise three workforce-retention objectives across six European
markets. See [`docs/requirements_refinement.md`](docs/requirements_refinement.md)
for how the ambiguous parts of that brief were narrowed into concrete,
auditable definitions.

## Chosen scope

The full research → ingest → curate → analyse → explain pipeline is
implemented end to end, with software-emphasis depth: a clean adapter
boundary for ingestion, resilient network handling, a typed/packaged
codebase, automated tests, and an accessible dashboard. See
[`docs/requirements_refinement.md`](docs/requirements_refinement.md) for
what was deliberately left out and why.

## Architecture

```
asteria-retention/
├── README.md                     # this file
├── AI_USAGE.md                   # AI tools, prompts, rejected suggestions, verification
├── pyproject.toml                # packaging + dependencies
├── docs/
│   ├── requirements_refinement.md  # questions, assumptions, metric definitions, decisions
│   ├── source_register.md          # provider, licence, indicators, cadence, lag, limits
│   ├── architecture.md             # ADF + Databricks + Power BI production mapping
│   └── work_log.md                 # step-by-step record of what was done
├── src/asteria_retention/
│   ├── config.py                   # paths, country map, indicators, publication lags
│   ├── cli.py                      # single pipeline entrypoint
│   ├── ingestion/eurostat_client.py  # the ONLY module that knows the Eurostat API
│   ├── curate/canonicalize.py      # dirty CSV -> canonical, quality-flagged table
│   ├── domain/retention_metrics.py # the 3 objectives (cohort, censoring, denominators)
│   ├── domain/temporal_join.py     # publication lag, no future leakage
│   └── analysis/association.py, sql_analysis.py   # correlation + DuckDB SQL cross-check
├── scripts/
│   ├── run_all.sh                  # THE one command
│   ├── run_sql_analysis.py, run_association.py
│   ├── build_dashboard_data.py, build_dashboard.py
│   └── dev/generate_fixtures.js    # one-off helper (not part of the pipeline)
├── tests/                          # 24 tests
├── data/
│   ├── raw/                        # official CSVs + manifest (never edited)
│   ├── fixtures/                   # Eurostat replay payloads (offline review)
│   └── curated/                    # generated: canonical events, quality + coverage
│                                   #   reports, objective results, association results
├── dashboard/                      # template.html + data.json -> index.html
└── presentation/presentation.md    # 15-minute deck + interview Q&A
```

See [`docs/architecture.md`](docs/architecture.md) for how this local
shape maps to a production ADF + Databricks + Power BI stack.

## Prerequisites

- Python 3.11+
- `pip install -e ".[dev]"`

## Running it

**One command, deterministic, no network access required:**

```bash
./scripts/run_all.sh
```

This runs the pipeline against the bundled replay fixtures, rebuilds the
dashboard data bundle, rebuilds `dashboard/index.html`, and runs the test
suite. Then open `dashboard/index.html` directly in a browser (no local
server needed — the data is embedded, not fetched).

**To run against live Eurostat data instead of fixtures:**

```bash
python -m asteria_retention.cli   # omit --use-fixtures
```

(Requires outbound network access to `ec.europa.eu`, not required for
review of this repo.)

**Tests only:**

```bash
python -m pytest tests/ -v
```

## Outputs

After a run, `data/curated/` contains:

- `employee_events_canonical.csv` — canonicalised, quality-flagged events
- `quality_report.csv` — one row per data-quality issue with counts
- `retention_objective_results.csv` — the three objectives, with target
  comparison and full audit notes
- `external_indicators_raw.csv` / `external_indicators_quarterly.csv` —
  source-shaped and quarterly-aggregated external signals
- `indicator_coverage_report.csv` — which indicator/country series were loaded
- `association_results.csv` — correlation with sample size and CI (a documented
  non-finding in the offline run)

## SQL demonstration

The brief asks the software-emphasis track to "demonstrate SQL concepts".
`scripts/run_sql_analysis.py` runs real SQL (via embedded DuckDB,
directly against the curated CSV) that:

1. **Independently recomputes `NEW_HIRE_6M` in pure SQL** and diffs it
   against the pandas result — the run above shows **exact agreement**
   (numerator 1939, denominator 2220 on both sides), which is stronger
   evidence of correctness than either implementation checked alone.
2. Runs a **GROUP BY** country summary (headcount, terminations).
3. Runs a **window function** (`SUM(...) OVER (ORDER BY ...)`) producing
   a running cumulative hire total by quarter.

All three queries are plain ANSI SQL and port to Databricks SQL / Spark
SQL with only trivial syntax changes — see comments in
`src/asteria_retention/analysis/sql_analysis.py`.

## Key findings (from this run, `--use-fixtures`)

- **New-hire six-month retention**: 87.3% overall (n=2,220), above the
  86% target — but Romania sits below target while Poland and Greece
  are comfortably above it.
- **Senior-hire twelve-month retention**: 78.3% overall (n=318), below
  the 90% target in every single country — the clearest signal in this
  dataset.
- **Trailing regretted turnover**: 5.1%, comfortably under the 7.5%
  ceiling in every country.
- **Limitation / non-finding**: senior-hire cohorts are small per country
  (46–59 hires); country-level differences on that metric should be read
  as directional, not conclusive. The bundled indicator fixtures cover a
  small illustrative window, so correlation results in this offline run
  demonstrate the pipeline's mechanics rather than a load-bearing finding
  — a live run has fuller history.

## Known limitations

- **Offline fixtures cover only 2 of 6 countries (GR, RO).** The other four have no
  external data in this run, so no association is claimed. Run without
  `--use-fixtures` (needs internet) to load all six.
- A dashboard screenshot is not included; add one to `docs/` after opening
  `dashboard/index.html`.

- Publication-lag assumptions for external indicators are documented
  estimates, not re-verified against Eurostat's live release calendar in
  this offline build (see `docs/source_register.md`).
- No revision-detection for previously-ingested indicator periods.
- The dashboard is a single static HTML file rather than a live-refreshing
  service — sufficient for local review, not for production consumption
  (see `docs/architecture.md` for the production mapping via Power BI).

## AI usage

See [`AI_USAGE.md`](AI_USAGE.md) for how an AI coding agent was directed,
what it got wrong along the way, and how those failures were caught and
fixed (not hidden).
