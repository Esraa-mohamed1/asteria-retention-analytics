"""External macroeconomic and labour indicator curation, contract validation, and coverage reporting."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd

from asteria_retention.config import CANONICAL_COUNTRIES, INDICATORS_BY_ID
from asteria_retention.errors import ContractViolation
from asteria_retention.ingestion.base import Observation
from asteria_retention.schemas.indicator_schema import EXTERNAL_COLUMNS


def period_bounds(period: str, frequency: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """First and last day covered by a period label."""
    try:
        if frequency == "M":
            start = pd.Timestamp(f"{period}-01")
            return start, start + pd.offsets.MonthEnd(0)
        if frequency == "Q":
            year, quarter = period.split("-Q")
            start = pd.Timestamp(year=int(year), month=3 * int(quarter) - 2, day=1)
            return start, start + pd.offsets.QuarterEnd(0)
        if frequency == "A":
            return pd.Timestamp(f"{period}-01-01"), pd.Timestamp(f"{period}-12-31")
    except ValueError as exc:
        raise ContractViolation(f"invalid period '{period}' for frequency '{frequency}'") from exc
    raise ContractViolation(f"unsupported frequency '{frequency}'")


def build_external_frame(observations: Iterable[Observation]) -> pd.DataFrame:
    """Transform raw observation records into canonical tabular structure with audit trail."""
    rows = [o.as_dict() for o in observations]
    if not rows:
        return pd.DataFrame(columns=list(EXTERNAL_COLUMNS))
    df = pd.DataFrame(rows)
    bounds = [period_bounds(p, f) for p, f in zip(df["period"], df["frequency"], strict=True)]
    df["period_start"] = pd.to_datetime([b[0] for b in bounds])
    df["period_end"] = pd.to_datetime([b[1] for b in bounds])
    df["publication_lag_days"] = df["indicator_id"].map(
        {k: v.publication_lag_days for k, v in INDICATORS_BY_ID.items()}
    )
    df["available_from"] = df["period_end"] + pd.to_timedelta(df["publication_lag_days"], unit="D")
    df["value"] = df["value"].astype(float)
    df = df[list(EXTERNAL_COLUMNS)].sort_values(["indicator_id", "geo", "period_end"], kind="stable")
    return df.reset_index(drop=True)


def validate_external_frame(df: pd.DataFrame, indicator_ids: Sequence[str] | None = None) -> None:
    """Validate data integrity and consistency against schema contracts."""
    problems: list[str] = []
    missing = set(EXTERNAL_COLUMNS) - set(df.columns)
    if missing:
        raise ContractViolation(f"external frame missing columns: {sorted(missing)}")
    if df.empty:
        return
    if not set(df["geo"]) <= set(CANONICAL_COUNTRIES):
        problems.append(f"unknown geo codes: {sorted(set(df['geo']) - set(CANONICAL_COUNTRIES))}")
    if not set(df["frequency"]) <= {"M", "Q", "A"}:
        problems.append("frequency must be one of M, Q, A")
    if df["value"].isna().any() or not df["value"].map(pd.notna).all():
        problems.append("value contains missing numbers")
    if df.duplicated(["indicator_id", "geo", "period"]).any():
        problems.append("duplicate (indicator_id, geo, period) keys")
    if (df["available_from"] <= df["period_end"]).any():
        problems.append("available_from must be after period_end")
    if indicator_ids is not None and not set(df["indicator_id"]) <= set(indicator_ids):
        problems.append("unexpected indicator_id present")
    if problems:
        raise ContractViolation("external data contract violated: " + "; ".join(problems))


def coverage_report(df: pd.DataFrame) -> pd.DataFrame:
    """Compute indicator x country coverage metrics for transparency and uncertainty reporting."""
    rows = []
    for indicator_id, indicator in INDICATORS_BY_ID.items():
        for geo in CANONICAL_COUNTRIES:
            sub = df[(df["indicator_id"] == indicator_id) & (df["geo"] == geo)]
            rows.append(
                {
                    "indicator_id": indicator_id,
                    "provider": indicator.provider,
                    "frequency": indicator.frequency,
                    "geo": geo,
                    "observations": len(sub),
                    "first_period": sub["period"].iloc[0] if len(sub) else "",
                    "last_period": sub["period"].iloc[-1] if len(sub) else "",
                    "provisional_or_flagged": int((sub["obs_status"] != "").sum()) if len(sub) else 0,
                }
            )
    return pd.DataFrame(rows)
