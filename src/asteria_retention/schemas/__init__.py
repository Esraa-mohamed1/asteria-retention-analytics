"""Schemas package: central domain definitions for tabular contracts, columns, and quality flags."""

from asteria_retention.schemas.event_schema import (
    REQUIRED_EVENT_COLUMNS,
    BLOCKING_FLAGS,
    INFORMATIONAL_FLAGS,
    FLAG_DESCRIPTIONS,
)
from asteria_retention.schemas.indicator_schema import (
    EXTERNAL_COLUMNS,
    COVERAGE_COLUMNS,
)
from asteria_retention.schemas.metric_schema import (
    METRIC_DIMENSIONS,
    SERIES_COLUMNS,
    SUMMARY_COLUMNS,
    EXCLUSION_COLUMNS,
)
from asteria_retention.schemas.panel_schema import (
    PANEL_COLUMNS,
    ASSOCIATION_COLUMNS,
)

__all__ = [
    "REQUIRED_EVENT_COLUMNS",
    "BLOCKING_FLAGS",
    "INFORMATIONAL_FLAGS",
    "FLAG_DESCRIPTIONS",
    "EXTERNAL_COLUMNS",
    "COVERAGE_COLUMNS",
    "METRIC_DIMENSIONS",
    "SERIES_COLUMNS",
    "SUMMARY_COLUMNS",
    "EXCLUSION_COLUMNS",
    "PANEL_COLUMNS",
    "ASSOCIATION_COLUMNS",
]
