# AI usage

## Tools and models

- **Cursor** (AI code editor) with **Claude Sonnet** (Anthropic) as the
  underlying model, used as an agentic coding assistant throughout this
  repository. Architecture, code, tests, docs, and the dashboard were all
  produced through direction-and-review turns in a single session, not
  generated once and left unchecked.

---

## How the work was directed

The task was decomposed into stages, each run and inspected before moving to
the next:

1. Extract the official assessment fixtures and verify SHA-256 checksums against
   `assessment_data_manifest.json` before trusting them as inputs.
2. Scaffold the package (`pyproject.toml`, adapter boundary) so ingestion and
   domain logic are cleanly separated.
3. Write the curation layer to flag data-quality problems rather than silently
   drop or correct them.
4. Write the three retention-objective calculations with an explicit,
   documented cohort/censoring rule for each.
5. Write the temporal-join logic enforcing publication-lag and no-future-leakage.
6. Write two ingestion adapters (Eurostat, World Bank) behind a single
   dispatcher, so the domain layer never knows which provider it is talking to.
7. Write the CLI orchestrator, then the test suite, then the dashboard — in
   that order, so the dashboard reuses already-tested domain functions.
8. Build and verify the dashboard interactively, inspecting the embedded JSON
   and the rendered output after each rebuild.

---

## Verification performed

- `python -m asteria_retention run --source fixtures` was executed (not just
  written) after each significant change; log output was inspected for
  plausible row counts, quality-flag counts, and objective values.
- `pytest tests/ -v` was run to completion; failures were read and fixed, not
  ignored (see failures section below).
- Input fixture files were SHA-256 verified against
  `assessment_data_manifest.json` before use.
- The dashboard's embedded JSON was parsed back and spot-checked after each
  build step, to confirm the injection produced valid JSON.
- SQL (DuckDB) cross-check asserts that an independent SQL reproduction of
  `NEW_HIRE_6M` matches the pandas result exactly on every run.

---

## Failures found and how they were handled

Real failures surfaced during development, not staged for this document:

1. **`numpy.bool_` not `is`-comparable to Python `True`.**  
   Initial tests used `result is True`. Pandas stores boolean columns as
   `numpy.bool_`, which is not `is`-identical to Python's `True`. The tests
   were rewritten to use `==`. The underlying data was correct; the test
   comparison was wrong.

2. **Publication-lag test used an evaluation date inside the lag window.**  
   A temporal-join test expected a value for a date one day before the
   indicator's `available_from`. The no-leakage logic correctly refused to
   return it. This was a test-authoring mistake, not a bug in the join logic;
   the evaluation date was moved forward and the test now passes for the right
   reason.

3. **`regretted_exit` column upcasted from string to bool on CSV re-read.**  
   Re-reading the curated CSV with default `pandas.read_csv` silently
   converted `"true"`/`"false"` strings to native booleans, breaking a
   `== "true"` comparison downstream. Rejected fix: patching the comparison
   to accept both types. Actual fix: the dashboard data builder re-derives
   canonical events from the original raw CSV using the same `dtype=str`
   loader as the CLI, so the pipeline and dashboard can never see different
   types for the same column.

4. **Eurostat `job_vacancy_rate` API schema change.**  
   The `indic_em` dimension changed from `JOBRATE` to `JVR` in a Eurostat
   release. The API returned 0 results without error. Fixed by adding a
   `prefer` fallback in `config.py` that accepts both codes client-side, so
   neither the live API nor the fixture can silently return empty results.

---

## Accepted vs rejected AI suggestions

| # | AI suggestion | Decision | Why | Consequence |
|---|---|---|---|---|
| 1 | Fisher-z confidence intervals on Pearson r | **Accepted** | Reporting a bare correlation without uncertainty is misleading at small n | CI is shown in the association table alongside r |
| 2 | Within-country demeaned Pearson as a third association method | **Accepted** | Controls for fixed country effects; a stricter test than pooled correlation | Three methods run per indicator pair |
| 3 | Build the full pipeline in one pass | **Rejected** | Cannot verify correctness of step N+1 if step N hasn't been run | Work done in stages; each stage verified before the next |
| 4 | Merge `Sr Mgmt` into `Senior Leader` | **Rejected twice** | Cannot assume equivalence without evidence | 10 rows flagged `nonstandard_career_level_kept_separate`, excluded from `SENIOR_HIRE_12M`, documented as an open risk |
| 5 | Default zero-denominator cohort value to `0.0` | **Rejected** | A zero-denominator cohort is a non-finding, not evidence of 0% retention; conflating the two misrepresents an empty cohort as a failed one | Returns `None` instead; the dashboard shows "N/A" |
| 6 | Count unknown-country employee in the turnover headcount | **Changed after discussion** | One `is_clean_for_analysis` rule across all three objectives is easier to defend than a different rule per objective | One gate used everywhere; exclusion always reported |
| 7 | Canvas 2D trend chart in the dashboard | **Accepted** | Avoids a charting-library dependency and keeps the dashboard self-contained | Trend chart implemented with plain Canvas 2D API |

---

## Human decisions that override or constrain AI output

The following analytical decisions are the candidate's, not the AI's:

- **"Sr Mgmt" classification**: the AI suggested merging it. I rejected this
  because I cannot tell from the data whether "Sr Mgmt" is an alias for
  "Senior Leader" or a distinct level. The consequence is documented in
  `docs/requirements_refinement.md`.
- **Fixture vs live for CI**: I chose fixtures so the test suite is
  deterministic and network-independent. The tradeoff (smaller date range,
  no real associations in the test run) is documented openly.
- **Publication-lag estimates**: I chose conservative values rather than
  verifying against the live Eurostat release calendar, because the pipeline
  is running offline. These are documented as estimates, not facts.
- **SENIOR_HIRE_12M association skipped**: I made the call to record this as
  an explicit non-finding rather than attempting a correlation with 2–3
  data points per country-quarter.

---

## Remaining risk — what a human should still verify

- **Publication-lag values** in `config.py` are estimates; verify against
  Eurostat's and the World Bank's official release calendars before relying
  on the temporal join for a real decision.
- **`hicp_inflation` dataset (`prc_hicp_manr`)** is deprecated by Eurostat
  as of May 2026. The replacement is `prc_hicp_minr`. Migration is a one-line
  change in `config.py`; the data structure is the same.
- **No secrets are used** — Eurostat's and World Bank's public APIs require no
  key. The adapter pattern is written so a future keyed provider would take
  its key from an environment variable, never a hardcoded string.
- **Fixture data covers synthetic values**, not a full live history. Any
  association results from a fixture run demonstrate pipeline mechanics, not
  real findings. Run `--source live` to produce real associations.
