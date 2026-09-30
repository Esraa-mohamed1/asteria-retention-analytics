# Error message style guide

Every user-visible error in this project follows this shape:

> **[WHAT failed]** + **[WHY it likely happened]** + **[WHAT to do next]**

No raw stack traces. No bare HTTP codes. No jargon without a plain-language gloss.

---

## Before → After: the 5 most important messages

### 1. Manifest checksum mismatch

| | Message |
|---|---|
| **Before** | `Manifest check failed: ['employees.csv: sha256 does not match the manifest']` |
| **After** | `Fatal: Manifest check failed: ['employees.csv: sha256 does not match the manifest']` + pipeline exits with code 1 and writes a `run_report.json` explaining the failure. The log makes clear this is a fatal, not degraded, result. |

**What to do:** Verify the file was not corrupted or altered during transfer. Re-download the official assessment files and re-run.

---

### 2. Live fetch failure after retries (network or API error)

| | Message |
|---|---|
| **Before** | `[eurostat/job_vacancy_rate] gave up after 3 attempts: HTTP 503: ...` |
| **After** | `[eurostat/job_vacancy_rate] Gave up after 3 attempts. Check your internet connection, or use '--source fixtures' to run without live data. Last failure: HTTP 503 ...` |

**What to do:** Use `coke` (offline fixtures) for a fully offline run. Try `coke live` again when connectivity is restored.

---

### 3. Empty external data (dataset schema change)

| | Message |
|---|---|
| **Before** | `job_vacancy_rate: dimension 'nace_r2' has 4 categories (B-S, A-S, ...). Add it to Indicator.filters or Indicator.prefer in config.py.` |
| **After** | `job_vacancy_rate: Eurostat's 'nace_r2' dimension now has 4 categories (B-S, A-S, ...) but only 1 was expected. The dataset schema likely changed since this pipeline was configured. Fix: add 'nace_r2' to Indicator.filters or Indicator.prefer in config.py to select the correct category. See docs/source_register.md for guidance.` |

**What to do:** Open `src/asteria_retention/config.py`, find the `job_vacancy_rate` indicator, and add the correct category code to its `prefer` dict.

---

### 4. SQL / pandas cross-check mismatch

| | Message |
|---|---|
| **Before** | `SQL cross-check FAILED for: ['new_hire_6m_match']` |
| **After** | Pipeline raises `ContractViolation` with the same message, exits with code 1, and writes `run_report.json` with `exit_code: 1`. The log line reads: `CRITICAL Fatal: SQL cross-check FAILED for: ['new_hire_6m_match']` — distinguishing it clearly from a degraded (exit 3) result. |

**What to do:** This means the pandas and SQL metric computations disagree. Do not trust the dashboard output. Compare `data/curated/canonical_events.csv` against the DuckDB query in `warehouse_validator.py` and identify the divergence.

---

### 5. Dashboard data parse failure (browser-side)

| | Message |
|---|---|
| **Before** | *(blank page, or browser console only)* `Uncaught SyntaxError: Unexpected token '<', "<!DOCTYPE "... is not valid JSON` |
| **After** | On-page red error banner: **"Dashboard data could not be loaded."** `(The embedded data element (#asteria-data) is missing from the page.)` Rebuild it by running `coke dash` (or `python -m asteria_retention build-dashboard`) and reopen this page. |

**What to do:** Run `coke dash` to rebuild the dashboard HTML from the curated CSVs, then refresh the browser.

---

## Rule summary (for code review)

- Every `SourceFetchError` must include: provider name, indicator ID, plain-language reason, and what to try next.
- Every `ContractViolation` must say what field/dimension was unexpected and exactly what config change fixes it.
- Every `DataIntegrityError` must say which file failed and why.
- No error message should reference internal variable names or raw Python exception class names as the primary explanation.
