# Requirements refinement

This document is the "narrowing" step the assessment brief asks for:
what was ambiguous in the brief, the assumption made instead of guessing,
and the consequence of that choice.

## Clarification questions (would have been the one submitted batch)

1. For `SENIOR_HIRE_12M`, does "senior hire" mean `career_level ==
   "Senior Leader"` only, or does it also include `"Manager"`?
2. For `REGRETTED_TURNOVER_12M`, what denominator convention is expected —
   average headcount, point-in-time headcount, or something else?
3. Should employees with an unknown `country_code` (blank, or a code that
   doesn't map to one of the six ISO codes) be excluded from all metrics,
   or allocated to a default country?
4. Is a `termination_date` with no `termination_type` an active employee
   whose exit type hasn't been logged yet, or a data-entry error?

No answers were available (single-player exercise), so each question
below is answered with a documented assumption instead.

## Decisions and assumptions

| # | Question | Decision | Consequence |
|---|---|---|---|
| 1 | Senior-hire scope | `career_level == "Senior Leader"` only. The 10 `"Sr Mgmt"` rows are kept as a SEPARATE category (flagged `nonstandard_career_level_kept_separate`, not relabelled, not dropped) and are not counted as senior hires. An AI suggestion to merge them into "Senior Leader" was considered and rejected by the analyst | Managers and "Sr Mgmt" are excluded from `SENIOR_HIRE_12M`. If "Sr Mgmt" really is the same level, the denominator is understated by at most 10 hires (0.4% of rows); this is stated openly as a risk |
| 2 | Turnover denominator | Average of headcount at window-start and headcount at `as_of` | A standard, auditable proxy for average headcount without needing a full daily census; slightly under/over-states true average if headcount moved non-linearly within the window |
| 3 | Unknown country code | Row is kept (never dropped) but flagged `unknown_country_code` and excluded from `is_clean_for_analysis`, so it is invisible to per-country and overall metrics but visible in the quality report | Metrics are computed on a slightly smaller, cleaner base (0.37% of rows for this dataset); the excluded count is always reported alongside every metric, never hidden |
| 4 | Termination with no type | Flagged `termination_missing_type`, not auto-classified as voluntary/involuntary, and NOT excluded from `is_clean_for_analysis` (the ambiguity is about the *type*, not whether the termination happened) | Retention metrics (which only care about active/not-active) are unaffected; only `regretted_exit`-dependent slicing is affected, and those rows are separately reported under "unknown regret" rather than silently defaulted |
| 5 | Cohort maturity ("censoring") | A hire only enters a metric's denominator once its observation window (6 or 12 months) has fully elapsed relative to `WORKFORCE_AS_OF` (2025-12-31) | Recently hired employees are excluded rather than counted as a false "retained" or a false "left" — this is the single biggest lever on the reported metric value, and `excluded_rows` on every `MetricResult` makes its size visible |
| 6 | Duplicate `employee_id` | First occurrence kept as canonical; any repeat is flagged `duplicate_employee_id` and excluded from analysis | Avoids double-counting a person in headcount/retention math; assumes the first row is the authoritative one, which may not always be true for a real HCM export |
| 7 | Frequency mixing (monthly vs quarterly external indicators) | Monthly indicators are aggregated to a quarterly mean; never forward-filled into individual months | Prevents presenting one quarterly reading as three independently-measured monthly ones (the assessment brief calls this out explicitly as non-negotiable) |
| 8 | Publication lag for external indicators | Documented per-indicator lag in `config.PUBLICATION_LAG_DAYS` (conservative estimates, see `docs/source_register.md`) applied before a value is considered "available" for a given evaluation date | Prevents any external observation from leaking backward in time into a retention period before it would realistically have been published |

## Rejected scope

- **Per-employee predictive model of attrition risk** — out of scope for
  this exercise; the brief asks for descriptive association, not a
  trained classifier, and a small, synthetic, single-snapshot dataset is
  a poor basis for a model that would be presented as decision-ready.
- **Full six-country x six-year live Eurostat pull inside this repo's
  automated test run** — the ingestion adapter is written for the real
  API, but tests and the bundled dashboard run against small, checked-in
  replay fixtures (`data/fixtures/*.json`) so the suite is deterministic
  and needs no network access; a live run is one flag away
  (`--use-fixtures` omitted).
- **Power BI `.pbix` deliverable** — an HTML dashboard was chosen instead
  for the software-emphasis track, since it can be built, tested, and
  version-controlled with the same toolchain as the rest of the code
  (no proprietary desktop app required to review it).

## Acceptance criteria used to judge "done"

- `python -m asteria_retention.cli --use-fixtures` runs to completion,
  deterministically, with zero network access.
- All three retention objectives are computed with an explicit,
  documented cohort definition and are never silently dropped/null'd
  when the denominator is zero (returns `None`, not a fabricated 0).
- No external indicator value is ever attributed to a workforce period
  before it would legitimately have been published.
- Every excluded/flagged row is visible in `data/curated/quality_report.csv`,
  never silently discarded.
- `pytest` passes and covers the riskiest logic: country-code aliasing,
  cohort censoring, publication-lag enforcement, and small-sample
  correlation guards.
