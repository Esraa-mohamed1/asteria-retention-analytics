"""External macroeconomic and labour indicator schema definitions."""

from __future__ import annotations
from typing import Final

EXTERNAL_COLUMNS: Final[tuple[str, ...]] = (
    "provider",
    "indicator_id",
    "geo",
    "period",
    "frequency",
    "period_start",
    "period_end",
    "value",
    "unit",
    "obs_status",
    "publication_lag_days",
    "available_from",
    "retrieved_at",
    "source_url",
    "payload_sha256",
    "data_origin",
)

COVERAGE_COLUMNS: Final[tuple[str, ...]] = (
    "indicator_id",
    "geo",
    "n_observations",
    "min_period",
    "max_period",
    "latest_available_from",
    "is_stale",
)
