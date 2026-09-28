"""Domain logic: retention metrics, temporal joins, and validation invariants."""

from asteria_retention.domain.retention_metrics import (
    load_objectives,
    build_series,
    summarise,
    exclusion_summary,
    meets_target,
)
from asteria_retention.domain.temporal_alignment import (
    as_of_join,
    assert_no_future_information,
)

__all__ = [
    "load_objectives",
    "build_series",
    "summarise",
    "exclusion_summary",
    "meets_target",
    "as_of_join",
    "assert_no_future_information",
]
