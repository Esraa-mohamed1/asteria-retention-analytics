# AI usage

## Tools/models

- **Claude** (Anthropic), used conversationally as the coding agent for
  this entire repository — architecture, code, tests, docs, and the
  dashboard were all produced through direction-and-review turns in a
  single chat session, not generated once and left unchecked.

## How the work was directed

The task was decomposed roughly in this order, each step run and
inspected before moving to the next:

1. Extract the official assessment fixtures from the assignment page's
   embedded generator (Node) and verify their SHA-256 checksums against
   `assessment_data_manifest.json` before trusting them as inputs.
2. Scaffold the package (`pyproject.toml`, `src/asteria_retention/...`)
   with an explicit adapter boundary for the Eurostat ingestion so a
   second provider could be added later without touching curation or
   metrics code.
3. Write the curation layer to flag data-quality issues rather than
   silently drop or "fix" them.
4. Write the three retention-objective calculations with an explicit,
   documented cohort/censoring rule for each.
5. Write the temporal-join logic enforcing publication-lag / no-leakage
   and frequency integrity (no forward-filling a quarterly figure into
   individual months).
6. Write the CLI orchestrator, then the test suite, then the dashboard —
   in that order, so the dashboard could reuse already-tested domain
   functions rather than re-implementing any metric.

## Verification performed

- `python -m asteria_retention.cli --use-fixtures` was actually executed
  (not just written) after each significant change, and its log output
  was inspected for plausibility (row counts, quality-flag counts,
  objective values) before proceeding.
- `pytest` (21 tests) was run to completion; failures were read and
  fixed, not ignored (see "Failures found and how they were handled").
- The official uploaded fixture files were checksum-verified against
  `assessment_data_manifest.json` (`sha256sum`) before being used as the
  pipeline's input, rather than assumed correct.
- The dashboard's embedded JSON was parsed back and spot-checked after
  the build step, to confirm the injection script produced valid JSON
  rather than trusting string-replacement blindly.

## Failures found and how they were handled

Real failures surfaced during development, not staged for this document:

1. **`is_clean_for_analysis` comparison failure.** Initial tests asserted
   `result is True` / `result is False`; pandas stores boolean columns as
   `numpy.bool_`, which is not `is`-identical to Python's `True`/`False`.
   The tests were rewritten to use `==` instead of `is` (the correct fix —
   the underlying data was already right; the test's comparison was
   wrong).
2. **Publication-lag test failure.** A temporal-join test used an
   evaluation date one day before the indicator's publication lag had
   actually elapsed, so the "no leakage" logic correctly refused to
   return a value — but the test expected one. This was a test-authoring
   mistake, not a bug in `add_available_from_date`; the test's evaluation
   date was moved forward and the test now passes for the right reason.
3. **CSV round-trip surprise (caught during manual exploration, not a
   test failure).** Re-reading the already-written curated CSV with
   default `pandas.read_csv` silently upcast the `regretted_exit` column
   from the string values `"true"`/`"false"` to native booleans,
   silently breaking a `== "true"` string comparison used elsewhere.
   Rejected fix: patching the comparison to also accept booleans, which
   would have hidden the dtype inconsistency. Actual fix: the dashboard
   data-build script (`scripts/build_dashboard_data.py`) re-derives
   canonical events from the original raw CSV via the same
   `dtype=str`-disciplined loader the CLI uses, instead of re-reading the
   curated CSV — so the pipeline and the dashboard can never see
   different types for the same column.

## Accepted vs. rejected suggestions

- **Accepted**: using `scipy.stats.pearsonr` with a Fisher-z confidence
  interval for the association analysis, rather than reporting a bare
  correlation coefficient with no uncertainty measure.
- **Rejected**: an early draft of the retention-metric functions
  defaulted a zero-denominator cohort to a metric value of `0.0`. This
  was deliberately changed to return `None` — a zero-denominator cohort
  is a non-finding, not evidence of 0% retention, and conflating the two
  would misrepresent an empty cohort as a failed one.

## Suggestions the analyst REJECTED or CHANGED (human decisions)

These are decisions the candidate made against, or on top of, what the AI suggested.

| # | AI suggestion | Analyst decision | Why | Consequence |
|---|---|---|---|---|
| 1 | Build the whole pipeline for the candidate in one go | **Rejected.** Candidate wanted to work by herself, with the AI only assisting and explaining | She must explain every line in the interview | Work was redone as guided steps; code is explained line by line |
| 2 | Merge `Sr Mgmt` into `Senior Leader` (looks like an alias: 10 rows, similar name) | **Rejected, twice** (kept it after seeing the counter-argument) | She sees it as its own category and does not want to assume it is the same level | Code changed: the 10 rows are kept, flagged `nonstandard_career_level_kept_separate`, and not counted as senior hires. Senior-hire retention moved from 78.7% to 78.3% |
| 3 | Fill-in-the-blank (TODO) exercises so she writes code herself | **Rejected.** She asked for complete code with an explanation of each step | She had forgotten Python and had little time | Switched to full code plus line-by-line explanation |
| 4 | Count an unknown-country employee in the turnover headcount (her first answer) | **Changed after discussion** | One "clean row" rule across all three objectives is easier to defend than a different rule per objective | One rule (`is_clean_for_analysis`) is used everywhere |
| 5 | Study guides for C# and Python performance | **Not needed for the task** | The brief only requires Python 3.11+, SQL, pandas/PySpark and HTML/Power BI | Kept as optional extra reading only; not part of the deliverable |

**Open point (to confirm before the interview):** whether `Sr Mgmt` should count as a "senior hire". Current default = no. If she changes it, edit the one filter in `domain/retention_metrics.py` and update `requirements_refinement.md`.

### AI mistakes caught while working

- An early version of the dashboard had its findings typed by hand. They were re-checked against the real numbers; one vague sentence was rewritten.
- The AI first used two chat display widgets (a chart and comparison cards) that did not fit the content and were dropped in favour of plain tables.
- The pipeline merged `Sr Mgmt` contrary to the analyst's decision until this was noticed and fixed.

## Follow-up addition: SQL demonstration

After initial review, the user pointed out the brief's "demonstrate SQL
concepts" requirement had not actually been met (everything was pandas).
Added `analysis/sql_analysis.py` (DuckDB) with a query that independently
recomputes `NEW_HIRE_6M` and is diffed against the pandas result at run
time (`scripts/run_sql_analysis.py`) — verified to match exactly
(1939/2220 both sides) rather than assumed correct, plus a GROUP BY and a
window-function query. 3 new tests added and passing.

## Remaining risk / what a human should still check

- Publication-lag values in `config.PUBLICATION_LAG_DAYS` are documented
  estimates, not verified against Eurostat's live release calendar from
  this offline environment — see `docs/source_register.md`.
- The bundled indicator fixtures cover a small illustrative date range,
  not the full history a live API call would return; correlation
  results computed against them should be treated as a pipeline
  demonstration, not a real finding, until run live.
- No secrets are used or required by this pipeline (Eurostat's public
  API needs no key), so no credential-handling risk applies here — but
  the adapter pattern in `ingestion/eurostat_client.py` is written so a
  future keyed provider would take its key from an environment variable,
  never a hardcoded string.
