"""Panel and association statistical results schema definitions."""

from __future__ import annotations
from typing import Final

PANEL_COLUMNS: Final[tuple[str, ...]] = (
    "objective_id",
    "geo",
    "eval_date",
    "period",
    "numerator",
    "denominator",
    "value",
    "indicator_id",
    "ind_period",
    "ind_period_end",
    "ind_available_from",
    "ind_value",
    "ind_unit",
    "ind_obs_status",
    "ind_data_origin",
    "age_days",
    "stale",
)

ASSOCIATION_COLUMNS: Final[tuple[str, ...]] = (
    "objective_id",
    "indicator_id",
    "scope",
    "method",
    "n",
    "r",
    "ci_lower",
    "ci_upper",
    "p_value",
    "p_bonferroni",
    "insufficient_n",
    "note",
    "caveat",
)
