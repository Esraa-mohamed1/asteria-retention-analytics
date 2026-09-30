"""DuckDB analytics warehouse population and pandas-vs-SQL validation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from asteria_retention.analysis.sql_queries import (
    COUNTRY_SUMMARY_VIEW_SQL,
    QUARTERLY_HIRE_TREND_VIEW_SQL,
    get_new_hire_retention_sql,
    get_turnover_sql,
)
from asteria_retention.config import COUNTRIES, INDICATORS_BY_ID
from asteria_retention.errors import ContractViolation

logger = logging.getLogger(__name__)

CROSS_CHECK_TOLERANCE = 1e-9


def _sql_new_hire_retention(conn: duckdb.DuckDBPyConnection, months: int, levels_filter: str) -> pd.DataFrame:
    sql = get_new_hire_retention_sql(months, levels_filter)
    return conn.execute(sql).df()


def _sql_turnover(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    sql = get_turnover_sql()
    return conn.execute(sql).df()


def _populate_tables(
    conn: duckdb.DuckDBPyConnection,
    events_csv: Path,
    series_df: pd.DataFrame,
    external_df: pd.DataFrame,
    panel_df: pd.DataFrame,
    association_df: pd.DataFrame,
    quality_df: pd.DataFrame,
    coverage_df: pd.DataFrame,
) -> None:
    """Populate DuckDB dimension and fact tables from canonical inputs."""
    conn.execute(f"CREATE TABLE employee_events AS SELECT * FROM read_csv('{events_csv}', all_varchar=true)")

    conn.register("_series_df", series_df)
    conn.execute("CREATE TABLE fact_objective_series AS SELECT * FROM _series_df")

    if not external_df.empty:
        conn.register("_external_df", external_df)
        conn.execute("CREATE TABLE fact_external_observations AS SELECT * FROM _external_df")
    else:
        conn.execute("CREATE TABLE fact_external_observations (indicator_id VARCHAR)")

    if not panel_df.empty:
        conn.register("_panel_df", panel_df)
        conn.execute("CREATE TABLE fact_association_panel AS SELECT * FROM _panel_df")
    else:
        conn.execute("CREATE TABLE fact_association_panel (objective_id VARCHAR)")

    if not association_df.empty:
        conn.register("_assoc_df", association_df)
        conn.execute("CREATE TABLE association_results AS SELECT * FROM _assoc_df")
    else:
        conn.execute("CREATE TABLE association_results (objective_id VARCHAR)")

    if not quality_df.empty:
        conn.register("_quality_df", quality_df)
        conn.execute("CREATE TABLE quality_report AS SELECT * FROM _quality_df")
    else:
        conn.execute("CREATE TABLE quality_report (quality_flag VARCHAR)")

    if not coverage_df.empty:
        conn.register("_coverage_df", coverage_df)
        conn.execute("CREATE TABLE coverage_report AS SELECT * FROM _coverage_df")
    else:
        conn.execute("CREATE TABLE coverage_report (indicator_id VARCHAR)")

    # Dimensions
    dim_country = pd.DataFrame(
        [(c.iso2, c.iso3, c.name, c.eurostat_geo) for c in COUNTRIES.values()],
        columns=["iso2", "iso3", "name", "eurostat_geo"],
    )
    conn.register("_dim_country", dim_country)
    conn.execute("CREATE TABLE dim_country AS SELECT * FROM _dim_country")

    dim_indicator = pd.DataFrame(
        [
            {
                "indicator_id": i.indicator_id,
                "provider": i.provider,
                "dataset": i.dataset,
                "label": i.label,
                "lens": i.lens,
                "frequency": i.frequency,
                "unit": i.unit,
                "publication_lag_days": i.publication_lag_days,
                "max_age_days": i.max_age_days,
            }
            for i in INDICATORS_BY_ID.values()
        ]
    )
    conn.register("_dim_indicator", dim_indicator)
    conn.execute("CREATE TABLE dim_indicator AS SELECT * FROM _dim_indicator")

    # Views
    conn.execute(QUARTERLY_HIRE_TREND_VIEW_SQL)
    conn.execute(COUNTRY_SUMMARY_VIEW_SQL)


def _check_cohort_metric(
    conn: duckdb.DuckDBPyConnection,
    summary_df: pd.DataFrame,
    objective_id: str,
    months: int,
    levels_filter: str,
) -> dict[str, Any]:
    sql_df = _sql_new_hire_retention(conn, months, levels_filter)
    sql_num = float(sql_df["numerator"].iloc[0])
    sql_den = float(sql_df["denominator"].iloc[0])

    pan_row = summary_df[
        (summary_df["objective_id"] == objective_id)
        & (summary_df["country_code"] == "ALL")
        & (summary_df["business_unit"] == "ALL")
    ]
    if pan_row.empty:
        return {"status": "pandas_missing"}

    pan_num = float(pan_row["numerator"].iloc[0])
    pan_den = float(pan_row["denominator"].iloc[0])
    diff_num = abs(sql_num - pan_num)
    diff_den = abs(sql_den - pan_den)
    ok = diff_num < CROSS_CHECK_TOLERANCE and diff_den < CROSS_CHECK_TOLERANCE

    res = {
        "status": "PASS" if ok else "FAIL",
        "sql_numerator": sql_num,
        "sql_denominator": sql_den,
        "pandas_numerator": pan_num,
        "pandas_denominator": pan_den,
        "diff_numerator": diff_num,
        "diff_denominator": diff_den,
    }
    if not ok:
        raise ContractViolation(f"SQL vs pandas mismatch on {objective_id}: diff_num={diff_num}, diff_den={diff_den}")
    return res


def _check_turnover_metric(
    conn: duckdb.DuckDBPyConnection,
    series_df: pd.DataFrame,
) -> dict[str, Any]:
    sql_to = _sql_turnover(conn)
    sql_num = float(sql_to["numerator"].iloc[0])
    sql_den = float(sql_to["denominator"].iloc[0])

    turn_series = series_df[
        (series_df["objective_id"] == "REGRETTED_TURNOVER_12M")
        & (series_df["country_code"] == "ALL")
        & (series_df["business_unit"] == "ALL")
    ].sort_values("period_end")

    if turn_series.empty:
        return {"status": "pandas_missing"}

    first = turn_series.iloc[0]
    pan_num = float(first["numerator"])
    pan_den = float(first["denominator"])
    diff_num = abs(sql_num - pan_num)
    diff_den = abs(sql_den - pan_den)
    ok = diff_num < CROSS_CHECK_TOLERANCE and diff_den < CROSS_CHECK_TOLERANCE

    res = {
        "status": "PASS" if ok else "FAIL",
        "sql_numerator": sql_num,
        "sql_denominator": sql_den,
        "pandas_numerator": pan_num,
        "pandas_denominator": pan_den,
        "diff_numerator": diff_num,
        "diff_denominator": diff_den,
        "note": "spot-check on first evaluation date (2021-12-31 window)",
    }
    if not ok:
        raise ContractViolation(f"SQL vs pandas mismatch on REGRETTED_TURNOVER_12M: diff_num={diff_num}, diff_den={diff_den}")
    return res


def run_sql_analysis(
    events_csv: Path,
    series_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    external_df: pd.DataFrame,
    panel_df: pd.DataFrame,
    association_df: pd.DataFrame,
    quality_df: pd.DataFrame,
    coverage_df: pd.DataFrame,
    db_path: Path,
) -> dict[str, object]:
    """Load everything into DuckDB, cross-check SQL vs pandas, write the DB."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = duckdb.connect(str(db_path))
    try:
        _populate_tables(
            conn=conn,
            events_csv=events_csv,
            series_df=series_df,
            external_df=external_df,
            panel_df=panel_df,
            association_df=association_df,
            quality_df=quality_df,
            coverage_df=coverage_df,
        )

        cross_check: dict[str, object] = {}
        cross_check["NEW_HIRE_6M"] = _check_cohort_metric(conn, summary_df, "NEW_HIRE_6M", 6, "TRUE")
        cross_check["SENIOR_HIRE_12M"] = _check_cohort_metric(
            conn, summary_df, "SENIOR_HIRE_12M", 12, "career_level = 'Senior Leader'"
        )
        cross_check["REGRETTED_TURNOVER_12M"] = _check_turnover_metric(conn, series_df)

        logger.info("DuckDB written to %s (all cross checks passed)", db_path)
        return cross_check
    finally:
        conn.close()
