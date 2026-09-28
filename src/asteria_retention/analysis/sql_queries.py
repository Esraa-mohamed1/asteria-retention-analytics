"""DuckDB SQL queries and view definitions for retention analytics and cross-validation."""

from __future__ import annotations


def get_new_hire_retention_sql(months: int, levels_filter: str) -> str:
    """SQL query to recompute new hire cohort retention."""
    effective_from = "2021-01-01"
    effective_to = "2025-12-31"
    as_of = "2025-12-31"
    return f"""
    WITH base AS (
        SELECT *
        FROM employee_events
        WHERE lower(is_clean_for_analysis) = 'true'
          AND hire_date IS NOT NULL
          AND hire_date != ''
          AND {levels_filter}
          AND hire_date >= '{effective_from}'
          AND hire_date <= '{effective_to}'
    ),
    marks AS (
        SELECT *,
               (TRY_CAST(hire_date AS DATE)
                + INTERVAL '{months}' MONTH)                       AS mark_date,
               TRY_CAST(hire_date AS DATE)                         AS hire_dt,
               CASE WHEN termination_date != '' AND termination_date IS NOT NULL
                    THEN TRY_CAST(termination_date AS DATE)
                    ELSE NULL END                                   AS term_dt
        FROM base
    ),
    calc AS (
        SELECT *,
               mark_date <= DATE '{as_of}'                         AS matured,
               (term_dt IS NULL OR term_dt > mark_date)
                 AND mark_date <= DATE '{as_of}'                   AS retained
        FROM marks
    )
    SELECT
        COUNT(*) FILTER (WHERE matured)   AS denominator,
        COUNT(*) FILTER (WHERE retained)  AS numerator,
        COUNT(*) FILTER (WHERE NOT matured) AS immature
    FROM calc
    """


def get_turnover_sql() -> str:
    """SQL query to recompute regretted turnover for 12-month window ending 2021-12-31."""
    return """
    WITH base AS (
        SELECT *
        FROM employee_events
        WHERE lower(is_clean_for_analysis) = 'true'
          AND hire_date IS NOT NULL AND hire_date != ''
    ),
    calc AS (
        SELECT *,
               TRY_CAST(hire_date AS DATE)        AS hire_dt,
               CASE WHEN termination_date != '' AND termination_date IS NOT NULL
                    THEN TRY_CAST(termination_date AS DATE)
                    ELSE NULL END                 AS term_dt
        FROM base
    ),
    window_calc AS (
        SELECT *,
               -- 12-month window ending 2021-12-31 (first evaluation date)
               DATE '2020-12-31' AS win_start,
               DATE '2021-12-31' AS win_end,
               hire_dt <= DATE '2020-12-31' AND (term_dt IS NULL OR term_dt > DATE '2020-12-31')
                                              AS active_start,
               hire_dt <= DATE '2021-12-31' AND (term_dt IS NULL OR term_dt > DATE '2021-12-31')
                                              AS active_end,
               term_dt IS NOT NULL AND term_dt > DATE '2020-12-31' AND term_dt <= DATE '2021-12-31'
                                              AS exited,
               lower(COALESCE(regretted_exit, '')) = 'true' AS is_regretted
        FROM calc
    )
    SELECT
        COUNT(*) FILTER (WHERE active_start)          AS hc_start,
        COUNT(*) FILTER (WHERE active_end)            AS hc_end,
        COUNT(*) FILTER (WHERE exited AND is_regretted) AS regretted_exits,
        (COUNT(*) FILTER (WHERE active_start) + COUNT(*) FILTER (WHERE active_end)) / 2.0
                                                      AS denominator,
        COUNT(*) FILTER (WHERE exited AND is_regretted) AS numerator
    FROM window_calc
    """


QUARTERLY_HIRE_TREND_VIEW_SQL = """
CREATE VIEW quarterly_hire_trend AS
SELECT
    country_code,
    DATE_TRUNC('quarter', TRY_CAST(hire_date AS DATE)) AS quarter_start,
    COUNT(*) AS total_hires,
    COUNT(*) FILTER (WHERE lower(is_clean_for_analysis) = 'true') AS clean_hires
FROM employee_events
WHERE hire_date IS NOT NULL AND hire_date != ''
GROUP BY country_code, DATE_TRUNC('quarter', TRY_CAST(hire_date AS DATE))
ORDER BY country_code, quarter_start
"""

COUNTRY_SUMMARY_VIEW_SQL = """
CREATE VIEW country_summary AS
SELECT
    country_code,
    COUNT(*) AS total_events,
    COUNT(*) FILTER (WHERE lower(is_clean_for_analysis) = 'true') AS clean_events,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND termination_date != '') AS terminations
FROM employee_events
GROUP BY country_code
ORDER BY country_code
"""
