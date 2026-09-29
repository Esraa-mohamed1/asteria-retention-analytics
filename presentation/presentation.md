# Final interview presentation
### Asteria Consumer Products (fictional) · Software Engineer (Web) — Analytics & Insights
#### Software-emphasis track · 15 minutes

---

# Part 1 — Problem refinement and scope (3 min)

## Slide 1: The question
The business wants to know:

> "Can public labour-market and macroeconomic signals meaningfully contextualise
> three workforce-retention objectives across six European markets?"

Deliverable: a reproducible data pipeline + an interactive dashboard.
The brief asked for **software depth**, not surface area — so I built one
coherent end-to-end vertical slice and made all tradeoffs explicit.

---

## Slide 2: How I narrowed the brief

The brief left these terms undefined. I documented every decision before writing
any code.

| Ambiguity | My decision | Consequence |
|---|---|---|
| Who counts as a "senior hire"? | `career_level == "Senior Leader"` only | "Manager" and "Sr Mgmt" excluded; documented |
| The 10 "Sr Mgmt" rows | Kept as **its own category**, flagged `nonstandard_career_level_kept_separate` | Not counted as senior; denominator could be understated by ≤10 hires (0.4%) |
| Immature cohorts (hired < 6 or 12 months ago) | **Excluded from denominator**, not counted as a failure | They appear in the `immature` count on every metric result |
| Turnover denominator | Average headcount: (start + end) ÷ 2 | Standard auditable proxy; slightly off if headcount is non-linear |
| Blank `regretted_exit` | Not counted as regretted; reported as "unknown_regret" | Avoids silently inflating or deflating the rate |
| Dirty rows (unknown country, duplicates) | **Flagged, never deleted** | Visible in quality report; `is_clean_for_analysis` gate used everywhere |
| Frequency mixing (monthly vs quarterly indicators) | Monthly → quarterly mean; never forward-filled | Prevents presenting one quarterly reading as three independent monthly ones |

*Say: "The brief left these open intentionally so candidates would show their reasoning. I wrote each one down with its consequence before touching the code."*

---

## Slide 3: Scope cuts (deliberate)

- **No attrition prediction model** — the brief asks for association, not prediction. Small synthetic data is a poor basis for a model presented as decision-ready.
- **HTML dashboard instead of Power BI** — allowed by the brief; versionable, testable with the same toolchain, no proprietary software needed for review.
- **No full six-country live pull inside tests** — tests use checked-in replay fixtures; a live run is one flag away.

*Say: "A deliberate cut with a written reason is stronger evidence than an unfinished broad solution."*

---

# Part 2 — Architecture, lineage, and reliability (5 min)

## Slide 4: Pipeline stages

```
Research → Ingest → Curate → Analyse → Explain
```

```
data/raw (HR CSV)     ──► curate (quality flags)  ──► domain (metrics)  ──►┐
                                                                             ├──► dashboard
data/external_raw     ──► ingestion (adapters)     ──► temporal join    ──►─┘
  Eurostat API (3)         - eurostat_client.py          publication lag
  World Bank API (2)       - worldbank_client.py          no-leakage check
  fixtures (offline)       - service.py (dispatcher)
```

Five indicators across two providers, four lenses:
labour supply · labour demand · cost-of-living pressure · economic cycle

---

## Slide 5: Adapter boundary (software depth)

Only **one module per provider** knows that provider's API:

- `eurostat_client.py` — only this file knows that Greece is `EL`, that the HICP dataset code is `prc_hicp_manr`, etc.
- `worldbank_client.py` — only this file knows the World Bank URL pattern and ISO-3 country codes.
- `ingestion/service.py` — dispatcher; picks the right client from `config.INDICATORS`.

**Adding a third provider = one new adapter file + one line in `config.py`.**
No other module changes.

---

## Slide 6: Reliability choices

| Concern | Implementation |
|---|---|
| Network failure | Retries with exponential backoff; a failed indicator logs a warning and continues — does not abort the run |
| Offline review | Bundled replay fixtures (`data/fixtures/`) cover all five indicators; `--source fixtures` makes the run fully deterministic |
| Future data leakage | Every external observation carries `available_from = period_end + publication_lag_days`. The as-of join (`temporal_alignment.py`) only uses values where `available_from ≤ eval_date` |
| Frequency integrity | Monthly values are never forward-filled into fake monthly rows. Each observation keeps its native period label |
| Stale values | Each indicator has a `max_age_days`; observations older than that are excluded from the association panel |

---

## Slide 7: Quality and lineage

- **0 rows deleted.** Every quality problem is flagged and kept visible.
- **6 flag types**: `unknown_country_code`, `duplicate_employee_id`, `missing_hire_date`, `unknown_regret`, `nonstandard_career_level_kept_separate`, `termination_missing_type`
- `quality_report.csv` — one row per flag type: count, % of rows, treatment
- `is_clean_for_analysis` is the single gate used by every metric
- `canonical_events.csv` carries the flag columns so any exclusion is traceable back to the original row

---

## Slide 8: Tests and SQL cross-check

**6 automated tests** covering the highest-risk logic:

| Test | What it guards |
|---|---|
| `test_manifest_verification` | Input files have correct SHA-256 before any processing |
| `test_events_curation_clean_flags` | Country aliasing (EL→GR, ROM→RO), quality flags, `is_clean_for_analysis` |
| `test_no_future_information_in_panel` | `available_from > eval_date` never reaches the association panel |
| `test_retention_metrics_ranges` | All metric values in [0, 1]; denominator > 0 whenever value is not None |
| `test_association_non_findings_recorded` | `SENIOR_HIRE_12M` appears with `insufficient_n = True` |
| `test_sql_cross_check` | DuckDB SQL reproduction of `NEW_HIRE_6M` matches pandas exactly |

**SQL cross-check (DuckDB):**  
`warehouse_validator.py` runs SQL that independently recomputes `NEW_HIRE_6M`
(cohort filtering + maturity + retention) and asserts the result matches the
pandas metric to zero tolerance. SQL and pandas cannot both be wrong the same
way.

---

# Part 3 — Dashboard and key findings (4 min)

## Slide 9: Results vs targets

| Objective | Value | Target | Status |
|---|---|---|---|
| New-hire six-month retention | **87.1%** (n = 1,808) | ≥ 86% | ✅ On target |
| Senior-hire twelve-month retention | **78.0%** (n = 259) | ≥ 90% | ❌ Off target |
| Trailing regretted turnover (12 mo) | **5.1%** (n = 1,570) | ≤ 8% | ✅ On target |

48 Senior Leaders (2025 hires) are still within their window and excluded as immature.

---

## Slide 10: Three evidence-backed findings

**Finding 1 — Senior-hire retention misses in every country, structurally**

78.0% overall vs ≥ 90% target — a **12 pp gap**.  
57 of 259 mature Senior Leaders left within 12 months.  
**Median exit: 3.8 months** post-hire. This is fast attrition, not late-stage departures.  
Exits are evenly spread across all four hire cohorts 2021–2024 (17/15/13/12).  
Bulgaria is worst (72.0%), Italy best (82.9%). **All six countries miss.**

**Finding 2 — Country spread on new-hire retention: 20 pp range**

Romania lowest (80.0%), Greece/Poland comfortably above target.  
The 20 pp gap suggests country-specific factors (local labour market, onboarding process)
outweigh company-wide policy effects.

**Finding 3 — Regretted turnover is well-controlled (5.1% vs ≤ 8% target)**

Consistent across countries. Finance BU is lowest (3.8%); Supply Chain highest (6.9%).
No country is at risk of breaching the ceiling.

---

## Slide 11: Non-finding (documented explicitly)

**SENIOR_HIRE_12M association analysis — skipped. Explicit non-finding.**

Senior-hire cohorts average **2–3 people per country per quarter**, well below the
minimum of 8 pairs for any correlation. No association estimate is statistically
defensible.

This is **not a data gap**. It is a structural data-density limitation.
It appears in the dashboard Challenge section with a written caveat.

*Say: "A documented non-finding is better evidence than a made-up one."*

---

## Slide 12: Dashboard walk-through (1 min)

Four sections:

| Section | Shows |
|---|---|
| **Explore** | KPI cards, country/BU breakdown with progress bars, cohort exclusion audit, period range filter |
| **Understand** | Canvas trend chart (retention vs external signal overlay), indicator coverage table with docs links |
| **Challenge** | Findings grid (≥3 findings + explicit non-finding), full association table with CI and Bonferroni p |
| **Trust** | Quality flags, sources with licence/cadence/lag, methodology decisions, freshness status |

- Single static HTML file — no server, no build step for reviewers
- Accessible: semantic HTML, ARIA roles, skip link, keyboard-navigable tabs
- Graceful empty/error states on every table

---

# Part 4 — Tradeoffs, AI usage, next steps (3 min)

## Slide 13: How I used AI (see AI_USAGE.md)

The AI agent produced all code. **I made all scoping, data, and analytical decisions.**

**Accepted from AI:**
- Fisher-z confidence intervals on Pearson r (instead of bare coefficients)
- Within-country demeaned Pearson as a stricter association test
- Canvas 2D trend chart instead of a charting library dependency

**Rejected:**
- Building the full pipeline in one pass without review (I ran each stage before the next)
- Merging "Sr Mgmt" into "Senior Leader" (considered twice, rejected both times)
- Defaulting zero-denominator cohorts to `0.0` retention (changed to `None`)

**Bugs caught (not hidden):**
1. `numpy.bool_` not `is`-comparable to Python `True` in tests
2. Test evaluation date was one day inside the publication lag — test was wrong, logic was right
3. `regretted_exit` column upcasted from strings to booleans on CSV re-read
4. Eurostat `job_vacancy_rate` API schema changed (new `indic_em` code `JVR` replaced `JOBRATE`) — fixed with `prefer` fallback

---

## Slide 14: Tradeoffs and honest risks

| Decision | Alternative considered | Why I chose this |
|---|---|---|
| HTML dashboard | Power BI `.pbix` | Versionable, testable, no proprietary tool for reviewers |
| Fixtures for CI | Live API in tests | Deterministic, network-independent, fast |
| Conservative publication lags | Exact Eurostat release calendar | Calendar needs network access; lags err on the side of caution |
| `Senior Leader` only | Include `Manager` or `Sr Mgmt` | Cannot assume equivalence without confirmation; documented as a risk |
| Pearson + Spearman + within-country | Pearson only | Within-country demeaning is a stricter, more defensible test |

**Remaining risk:**  
Publication-lag estimates are not verified against Eurostat's live calendar.
The `hicp_inflation` dataset is deprecated — one-line fix in `config.py`.

---

## Slide 15: What's next (given more time)

1. **Run against live APIs** and report real associations with proper uncertainty.
2. **Migrate HICP to `prc_hicp_minr`** (Eurostat's replacement dataset — one line in `config.py`).
3. **Revision detection**: compare newly fetched periods against the last stored value; alert on unexpected backward revisions.
4. **Production path**: ADF orchestration → Databricks lakehouse (raw / curated / gold) → Power BI. See `docs/architecture.md`.
5. **Exit-reason data**: a single field (resignation / redundancy / performance) would let us explain the Senior Leader attrition pattern with evidence, not inference.

---

# Interview Q&A — prepared answers

| Question | One-sentence answer |
|---|---|
| Why exclude immature hires? | Their observation window hasn't closed; counting them as retained or failed is a guess, not a measurement. |
| Why is the turnover denominator different? | Turnover measures the whole active workforce, not a specific hiring cohort — average headcount is the correct base. |
| Why keep bad rows instead of deleting them? | Deletion hides problems; flags make every exclusion auditable and the denominator boundary visible. |
| Why is "Sr Mgmt" separate? | I can't assume it equals "Senior Leader" without evidence; 10 rows flagged, easy to change, consequence documented. |
| How do you prevent future data leaking in? | `available_from = period_end + lag_days`; the as-of join only uses values where `available_from ≤ eval_date`, enforced by an assertion in tests. |
| Why no association claim with indicators? | The fixture run has too few data points; any number produced would be a demonstration of pipeline mechanics, not a real finding — so I said so explicitly. |
| How do you know the metric code is correct? | SQL cross-check: DuckDB independently recomputes `NEW_HIRE_6M` and the result must match pandas to zero tolerance, or the run fails. |
| What did the AI get wrong? | Four bugs caught and fixed (see `AI_USAGE.md` and Slide 13); none hidden. |
| What would you do with more time? | Run live, migrate HICP dataset, add revision detection, connect to Power BI — Slide 15. |
| Why HTML instead of Power BI? | Versionable with the code, testable in CI, no proprietary tool required for a reviewer to open it. |
| How would you harden this for production? | ADF for scheduling, Databricks for scale, Key Vault for any future credentials, alerting on partial indicator failure — `docs/architecture.md` has the diagram. |
| What's the most important limitation? | The publication-lag values are estimates, not verified against the live release calendar. A wrong lag means an observation could be used before it was actually published. |
