"""Run report: machine-readable record of one pipeline execution.

Written to data/curated/run_report.json after every run.
Contains: stages, timings, row counts, indicator outcomes, exit code.
Used by CI and the dashboard's Trust panel to verify freshness.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class RunReport:
    """Accumulates pipeline stage results then writes to JSON."""

    def __init__(self, run_timestamp: str, source_mode: str) -> None:
        self.run_timestamp = run_timestamp
        self.source_mode = source_mode
        self.stages: list[dict[str, Any]] = []
        self._start = time.monotonic()

    def record_stage(
        self,
        name: str,
        status: str,
        *,
        duration_s: float | None = None,
        rows: int | None = None,
        detail: str = "",
    ) -> None:
        self.stages.append(
            {
                "stage": name,
                "status": status,
                "duration_s": round(duration_s, 3) if duration_s is not None else None,
                "rows": rows,
                "detail": detail,
            }
        )

    def write(
        self,
        path: Path,
        *,
        exit_code: int,
        ingestion_outcomes: list[dict[str, Any]],
        cross_check: dict[str, Any],
        notes: list[str] | None = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        total_s = round(time.monotonic() - self._start, 2)
        report = {
            "run_timestamp": self.run_timestamp,
            "source_mode": self.source_mode,
            "total_duration_s": total_s,
            "exit_code": exit_code,
            "stages": self.stages,
            "ingestion_outcomes": ingestion_outcomes,
            "cross_check": cross_check,
            "notes": notes or [],
        }
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
