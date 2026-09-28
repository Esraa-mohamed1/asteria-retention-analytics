"""Metrics and cohort aggregation schema definitions."""

from __future__ import annotations
from typing import Final

METRIC_DIMENSIONS: Final[tuple[str, ...]] = ("country_code", "business_unit")

SERIES_COLUMNS: Final[tuple[str, ...]] = (
    "objective_id",
    "country_code",
    "business_unit",
    "period",
    "period_end",
    "denominator",
    "numerator",
    "value",
    "immature",
    "unknown_regret",
)

SUMMARY_COLUMNS: Final[tuple[str, ...]] = (
    "objective_id",
    "country_code",
    "business_unit",
    "denominator",
    "numerator",
    "value",
    "immature",
    "unknown_regret",
    "n_periods",
    "period_min",
    "period_max",
)

EXCLUSION_COLUMNS: Final[tuple[str, ...]] = (
    "objective_id",
    "total_rows",
    "clean_rows",
    "excluded_rows",
    "immature_rows",
)
