"""Analysis package: analytical panel generation, correlation statistics, and SQL validation."""

from asteria_retention.analysis.association_analysis import (
    AssociationResult,
    correlate,
)
from asteria_retention.analysis.panel_builder import (
    NEW_HIRE_OBJECTIVE,
    SENIOR_OBJECTIVE,
    TURNOVER_OBJECTIVE,
    build_panel,
)
from asteria_retention.analysis.sql_queries import (
    COUNTRY_SUMMARY_VIEW_SQL,
    QUARTERLY_HIRE_TREND_VIEW_SQL,
    get_new_hire_retention_sql,
    get_turnover_sql,
)
from asteria_retention.analysis.warehouse_validator import (
    run_sql_analysis,
)

__all__ = [
    "COUNTRY_SUMMARY_VIEW_SQL",
    "NEW_HIRE_OBJECTIVE",
    "QUARTERLY_HIRE_TREND_VIEW_SQL",
    "SENIOR_OBJECTIVE",
    "TURNOVER_OBJECTIVE",
    "AssociationResult",
    "build_panel",
    "correlate",
    "get_new_hire_retention_sql",
    "get_turnover_sql",
    "run_sql_analysis",
]
