"""Analysis package: analytical panel generation, correlation statistics, and SQL validation."""

from asteria_retention.analysis.panel_builder import (
    build_panel,
    NEW_HIRE_OBJECTIVE,
    TURNOVER_OBJECTIVE,
    SENIOR_OBJECTIVE,
)
from asteria_retention.analysis.association_analysis import (
    correlate,
    AssociationResult,
)
from asteria_retention.analysis.warehouse_validator import (
    run_sql_analysis,
)
from asteria_retention.analysis.sql_queries import (
    get_new_hire_retention_sql,
    get_turnover_sql,
    QUARTERLY_HIRE_TREND_VIEW_SQL,
    COUNTRY_SUMMARY_VIEW_SQL,
)

__all__ = [
    "build_panel",
    "correlate",
    "run_sql_analysis",
    "AssociationResult",
    "NEW_HIRE_OBJECTIVE",
    "TURNOVER_OBJECTIVE",
    "SENIOR_OBJECTIVE",
    "get_new_hire_retention_sql",
    "get_turnover_sql",
    "QUARTERLY_HIRE_TREND_VIEW_SQL",
    "COUNTRY_SUMMARY_VIEW_SQL",
]
