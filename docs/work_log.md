# Work log: what was done, in order

Each step says WHAT was done, WHY, and the RESULT. Numbers are from the
real run on the official files (`python -m asteria_retention.cli --use-fixtures`).

| # | Step | Why | Result |
|---|---|---|---|
| 1 | Read the assignment; chose **Software Emphasis** | The email required it; it fits a web-developer background | Focus = clean structure, error handling, tests, accessible dashboard |
| 2 | Checked the tech stack in the brief | Brief says Python 3.11+, SQL concepts, pandas or PySpark, Power BI **or HTML** | Chose Python + pandas + DuckDB (SQL) + HTML dashboard |
| 3 | Verified the 4 supplied files with SHA-256 | Prove the data was not corrupted or altered | All 3 checksums match the manifest (2,407 event rows) |
| 4 | Read each file line by line | Understand the data before touching it | Learned the columns, nullable fields, and the 3 objectives |
| 5 | Explored `country_code` and `career_level` | Find the deliberate data problems | Found `EL`, `ROM`, blanks, and `Sr Mgmt` (10 rows) |
| 6 | Cleaned the data with **flags, not deletion** | Brief: do not assume blanks are errors | 6 flag types; no row deleted (see `quality_report.csv`) |
| 7 | Defined the 3 metrics before coding | Brief grades problem framing | Cohort, maturity (censoring) and denominator rules in `requirements_refinement.md` |
| 8 | Built NEW_HIRE_6M, SENIOR_HIRE_12M, REGRETTED_TURNOVER_12M | Core analysis | 87.3% (target ≥86%), 78.3% (target ≥90%), 5.1% (target ≤7.5%) |
| 9 | Built the Eurostat adapter with retries and replay fixtures | Resilient API handling; works offline | 3 indicators load; partial failure is handled safely |
| 10 | Built the temporal join (publication lag, no future leakage) | Brief: frequency integrity is non-negotiable | Monthly data averaged to quarters, never forward-filled |
| 11 | Added SQL (DuckDB) cross-check | Brief: demonstrate SQL concepts | SQL and pandas agree exactly (1939 / 2220) |
| 12 | Wrote 24 automated tests | Software emphasis | 24 pass |
| 13 | Built the accessible HTML dashboard | Required deliverable | Filters, KPIs, quality table, source notes, empty states |
| 14 | Verified dashboard findings against real numbers | Avoid claiming things the data does not show | All findings match `data.json` |
| 15 | Wrote README, AI_USAGE, source register, architecture doc | Required deliverables | See `docs/` |
| 16 | Hardening pass: accessibility, CI, error UX, linting | Code quality and submission polish | aria-live filter announcements; try/catch dashboard data parse; `ci.yml` workflow; `coke` CLI runner support; `ruff` added to dev deps and zero errors; bare `except (ContractViolation, Exception)` split into two typed handlers; all SourceFetchError messages follow WHAT+WHY+NEXT; `docs/error_messages.md` created; `stale_count` unused variable removed |

## Bugs found and fixed along the way (real ones)

1. Tests compared a numpy boolean with `is True`, which fails; changed to `==`.
2. A temporal-join test used a date before the publication lag ended; the code was right, the test date was wrong.
3. Re-reading the saved CSV turned `"true"/"false"` into booleans and silently broke a comparison; fixed by always loading with `dtype=str`.
4. The pipeline merged `Sr Mgmt` into `Senior Leader` against the analyst's decision; fixed (see AI_USAGE.md).

## What is NOT done or NOT verified (be honest about this in the interview)

- Live Eurostat calls were never run (the build environment had no access). Only replay fixtures were used, so **no real external-signal finding is claimed**.
- Publication-lag values are documented estimates, not checked against Eurostat's release calendar.
- Power BI was not used (HTML chosen, allowed by the brief).
