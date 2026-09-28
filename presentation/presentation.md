# External signals × workforce retention
### Asteria Consumer Products (fictional) · Software Engineer (Web), Analytics & Insights
Software-emphasis track · 15 minutes

---

# Part 1: Problem and scope (3 min)

## Slide 1: The question
- Can public labour-market and economic data add useful context to **3 retention objectives** across **6 countries**?
- Deliverable: a small, reproducible data product plus an interactive dashboard.

## Slide 2: How I narrowed it down
| Ambiguity in the brief | My decision |
|---|---|
| Who is a "senior hire"? | `Senior Leader` only |
| `Sr Mgmt` (10 rows) | Kept as **its own category**, flagged, not counted as senior |
| Immature cohorts (hired < 6 or 12 months ago) | **Excluded**, not counted as a failure |
| Turnover denominator | Average headcount (start + end) ÷ 2 |
| Blank `regretted_exit` | Not counted as regretted; reported separately |
| Bad rows (unknown country, duplicates…) | **Flagged, never deleted** |

*Say:* "The brief left these open on purpose, so I wrote each decision down with its consequence."

## Slide 3: Scope cuts (deliberate)
- No attrition prediction model (small synthetic data, brief asks for description).
- HTML dashboard instead of Power BI (allowed; fits the software track).

---

# Part 2: Architecture, lineage, reliability (5 min)

## Slide 4: Pipeline
`Research → Ingest → Curate → Analyse → Explain`

```
data/raw  →  curate (flags)  →  domain (metrics, temporal join)  →  analysis  →  dashboard
                 ↑ Eurostat adapter (retries, replay fixtures)
```

## Slide 5: Software-emphasis choices
- **Adapter boundary:** only one module knows Eurostat's API (Greece = `EL` translated there).
- **Resilience:** retries with backoff, clear errors, a failed indicator does not stop the run.
- **Config in one place:** paths, country map, indicators, lag days.
- **One command:** `./scripts/run_all.sh`.

## Slide 6: Data integrity rules
- **No future leakage:** each external value carries `available_from` = period end + publication lag.
- **Frequency integrity:** monthly → quarterly mean; never forward-filled into fake monthly values.
- **Cross-check:** SQL (DuckDB) recomputes NEW_HIRE_6M and matches pandas exactly (1939 / 2220).

## Slide 7: Quality and tests
- 6 flag types, 0 rows deleted (`quality_report.csv`).
- 24 automated tests: parsing, retries, country mapping, cohort maturity, lag rules, SQL agreement.

## Slide 8: Production mapping
ADF (orchestration) → Databricks lakehouse (raw / curated / gold) → Power BI. Secrets in Key Vault, alerts on partial failure. Details in `docs/architecture.md`.

---

# Part 3: Dashboard and findings (4 min)

## Slide 9: Results vs targets
| Objective | Result | Target | Status |
|---|---|---|---|
| New-hire 6-month retention | **87.3%** (1939 / 2220) | ≥ 86% | Met |
| Senior-hire 12-month retention | **78.3%** (249 / 318) | ≥ 90% | **Missed** |
| Regretted turnover (12 mo) | **5.1%** (80 / 1570) | ≤ 7.5% | Met |

## Slide 10: Three findings
1. **Senior-hire retention misses target in every country** (best IT 84.6%, worst BG 71.9%).
2. **Regretted turnover is under 7.5% everywhere**; Greece (2.8%) and Poland (3.4%) lowest, Romania highest (6.9%).
3. **Romania is the only country below the 86% new-hire target** (84.7%).

## Slide 11: Limitation / non-finding
- Senior cohorts are small per country (46–59), so country differences are **directional only**.
- External indicators came from **replay fixtures**, so **I claim no association** between external signals and retention. A live run is the next step.

## Slide 12: Dashboard demo (1 min)
Filters (country, unit, objective) → KPI cards → country bars → quality table → source notes. Keyboard-usable, semantic HTML, empty states.

---

# Part 4: Trade-offs, AI usage, next steps (3 min)

## Slide 13: How I used AI (see `AI_USAGE.md`)
- AI wrote code; **I made the scoping decisions.**
- **Rejected:** letting AI build everything; merging `Sr Mgmt` into `Senior Leader`.
- **Caught:** 4 real bugs (numpy bool, test date, CSV type round-trip, my own merge of `Sr Mgmt`).
- **Verified by:** running the pipeline, 24 tests, SQL vs pandas, SHA-256 of inputs.

## Slide 14: Risks and honesty
- Live Eurostat calls never run; lag values are estimates.
- `Sr Mgmt` treatment could understate the senior denominator by at most 10 hires.

## Slide 15: Next steps
1. Run against live Eurostat, then test associations with proper uncertainty.
2. Add World Bank as a second adapter.
3. Detect revisions to already-loaded indicator periods.
4. Move to Power BI over a gold table.

---

# Likely interview questions (prepare a 1–2 sentence answer for each)

1. **Why exclude recent hires instead of counting them as retained?** Their window has not finished; counting them either way would be a guess.
2. **Why is the denominator different for turnover?** It measures the whole workforce, not one hiring cohort.
3. **Why keep bad rows?** Deleting hides problems; flags make every exclusion auditable.
4. **Why `Sr Mgmt` separate?** I would not assume it equals `Senior Leader` without evidence; it is documented, small (10 rows) and easy to change.
5. **How do you prevent future data leaking in?** `available_from` = period end + lag; joins only use values available by the evaluation date.
6. **Why did you not claim a link to unemployment or inflation?** Only fixtures were available; a claim would be invented.
7. **How do you know the code is right?** Tests, SQL cross-check, and I can walk through any function.
8. **What would you do with more time?** Slide 15.
9. **What did AI get wrong?** Slide 13.
10. **Why HTML and not Power BI?** Allowed by the brief; versionable and testable with the rest of the code.
