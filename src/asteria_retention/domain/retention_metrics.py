"""Retention objective calculations.

Definitions (also in docs/requirements_refinement.md):

NEW_HIRE_6M / SENIOR_HIRE_12M  (cohort retention)
  Cohort   clean employees hired inside the objective's effective window
           [effective_from, effective_to]; SENIOR_HIRE_12M keeps only
           career_level == "Senior Leader" ("Sr Mgmt" and Managers excluded).
  Mature   hire_date + N months <= as_of. Immature hires are NOT failures; they
           are excluded from the denominator and reported separately (censoring).
  Retained no termination, or termination strictly after hire_date + N months.
  Value    retained / mature, grouped by hire quarter.

REGRETTED_TURNOVER_12M  (workforce rate)
  Window   (evaluation_date - 12 months, evaluation_date]
  Numerator exits in the window with regretted_exit == "true". Blank/unknown
           regret is never counted as regretted; it is reported separately.
  Denominator average of headcount at window start and at window end.
  First evaluation date = end of the first full year of the objective.

Every table has the same grain: objective x country x business_unit x period,
where country/business_unit can be "ALL" (a roll-up computed from row-level data,
never an average of averages).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd

from asteria_retention.errors import ContractViolation
from asteria_retention.schemas.metric_schema import METRIC_DIMENSIONS, SERIES_COLUMNS

DIMS = METRIC_DIMENSIONS


@dataclass(frozen=True)
class Objective:
    objective_id: str
    name: str
    direction: str  # "at_least" | "at_most"
    target_value: float
    unit: str
    scope: str
    effective_from: pd.Timestamp
    effective_to: pd.Timestamp


@dataclass(frozen=True)
class CohortRule:
    objective_id: str
    months: int
    levels: frozenset[str] | None  # None = every career level


COHORT_RULES = (
    CohortRule("NEW_HIRE_6M", 6, None),
    CohortRule("SENIOR_HIRE_12M", 12, frozenset({"Senior Leader"})),
)
TURNOVER_ID = "REGRETTED_TURNOVER_12M"


def load_objectives(path) -> dict[str, Objective]:  # type: ignore[no-untyped-def]
    df = pd.read_csv(path, dtype=str)
    objectives = {
        row.objective_id: Objective(
            objective_id=row.objective_id,
            name=row.objective_name,
            direction=row.direction,
            target_value=float(row.target_value),
            unit=row.unit,
            scope=row.scope,
            effective_from=pd.Timestamp(row.effective_from),
            effective_to=pd.Timestamp(row.effective_to),
        )
        for row in df.itertuples(index=False)
    }
    known = {r.objective_id for r in COHORT_RULES} | {TURNOVER_ID}
    if set(objectives) != known:
        raise ContractViolation(
            f"objectives file has {sorted(objectives)}, code implements {sorted(known)}"
        )
    for objective in objectives.values():
        if objective.direction not in ("at_least", "at_most"):
            raise ContractViolation(f"{objective.objective_id}: unknown direction {objective.direction}")
    return objectives


def analysis_base(events: pd.DataFrame) -> pd.DataFrame:
    """Rows usable by any metric: clean and with a hire date."""
    return events[events["is_clean_for_analysis"] & events["hire_date"].notna()]


def _with_all(df: pd.DataFrame) -> pd.DataFrame:
    """Stack copies of `df` where each subset of DIMS is replaced by "ALL"."""
    frames = []
    for mask in product((False, True), repeat=len(DIMS)):
        copy = df.copy()
        for dim, is_all in zip(DIMS, mask, strict=True):
            if is_all:
                copy[dim] = "ALL"
        frames.append(copy)
    return pd.concat(frames, ignore_index=True)


def _quarter_end(period: pd.PeriodDtype | pd.Series) -> pd.Series:
    return period.dt.end_time.dt.normalize()  # type: ignore[union-attr]


def cohort_series(
    events: pd.DataFrame, rule: CohortRule, objective: Objective, as_of: pd.Timestamp
) -> pd.DataFrame:
    base = analysis_base(events)
    if rule.levels is not None:
        base = base[base["career_level"].isin(rule.levels)]
    base = base[(base["hire_date"] >= objective.effective_from) & (base["hire_date"] <= objective.effective_to)]

    mark = base["hire_date"] + pd.DateOffset(months=rule.months)
    matured = mark <= as_of
    retained = (base["termination_date"].isna() | (base["termination_date"] > mark)) & matured
    frame = base[list(DIMS)].copy()
    frame["period"] = base["hire_date"].dt.to_period("Q")
    frame["_matured"] = matured.astype(int)
    frame["_retained"] = retained.astype(int)
    frame["_rows"] = 1

    grouped = (
        _with_all(frame)
        .groupby([*DIMS, "period"], observed=True)
        .agg(denominator=("_matured", "sum"), numerator=("_retained", "sum"), rows=("_rows", "sum"))
        .reset_index()
    )
    grouped["immature"] = grouped["rows"] - grouped["denominator"]
    grouped["unknown_regret"] = 0
    grouped["value"] = np.where(
        grouped["denominator"] > 0, grouped["numerator"] / grouped["denominator"].where(grouped["denominator"] > 0, 1), np.nan
    )
    grouped["period_end"] = _quarter_end(grouped["period"])
    grouped["period"] = grouped["period"].astype(str)
    grouped["objective_id"] = rule.objective_id
    return grouped[list(SERIES_COLUMNS)]


def turnover_dates(objective: Objective, as_of: pd.Timestamp) -> pd.DatetimeIndex:
    first = objective.effective_from + pd.DateOffset(years=1) - pd.Timedelta(days=1)
    return pd.date_range(first, min(as_of, objective.effective_to), freq="QE")


def turnover_series(
    events: pd.DataFrame, objective: Objective, as_of: pd.Timestamp
) -> pd.DataFrame:
    base = analysis_base(events)
    hire = base["hire_date"]
    term = base["termination_date"]
    pieces = []
    for evaluation_date in turnover_dates(objective, as_of):
        start = evaluation_date - pd.DateOffset(months=12)
        active_start = (hire <= start) & (term.isna() | (term > start))
        active_end = (hire <= evaluation_date) & (term.isna() | (term > evaluation_date))
        exited = term.notna() & (term > start) & (term <= evaluation_date)
        frame = base[list(DIMS)].copy()
        frame["_hc_start"] = active_start.astype(int)
        frame["_hc_end"] = active_end.astype(int)
        frame["_regretted"] = (exited & (base["regretted_exit"] == "true")).astype(int)
        frame["_unknown"] = (exited & ~base["regretted_exit"].isin(["true", "false"])).astype(int)
        grouped = (
            _with_all(frame)
            .groupby(list(DIMS), observed=True)
            .sum(numeric_only=True)
            .reset_index()
        )
        grouped["period_end"] = evaluation_date
        pieces.append(grouped)
    if not pieces:
        return pd.DataFrame(columns=list(SERIES_COLUMNS))
    out = pd.concat(pieces, ignore_index=True)
    out["denominator"] = (out["_hc_start"] + out["_hc_end"]) / 2
    out["numerator"] = out["_regretted"]
    out["value"] = np.where(out["denominator"] > 0, out["numerator"] / out["denominator"].where(out["denominator"] > 0, 1), np.nan)
    out["immature"] = 0
    out["unknown_regret"] = out["_unknown"]
    out["period"] = out["period_end"].dt.to_period("Q").astype(str)
    out["objective_id"] = TURNOVER_ID
    return out[list(SERIES_COLUMNS)]


def build_series(
    events: pd.DataFrame, objectives: dict[str, Objective], as_of: pd.Timestamp
) -> pd.DataFrame:
    """All objectives, all country/unit roll-ups, all periods."""
    parts = [
        cohort_series(events, rule, objectives[rule.objective_id], as_of) for rule in COHORT_RULES
    ]
    parts.append(turnover_series(events, objectives[TURNOVER_ID], as_of))
    series = pd.concat(parts, ignore_index=True)
    return series.sort_values(["objective_id", "country_code", "business_unit", "period_end"], kind="stable").reset_index(drop=True)


def meets_target(value: float | None, objective: Objective) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if objective.direction == "at_least":
        return bool(value >= objective.target_value)
    return bool(value <= objective.target_value)


def summarise(series: pd.DataFrame, objectives: dict[str, Objective]) -> pd.DataFrame:
    """Current status per objective x country x unit.

    Cohort objectives pool every mature cohort (sum of numerators / sum of
    denominators). Turnover uses the latest evaluation date.
    """
    rows = []
    for objective_id, objective in objectives.items():
        sub = series[series["objective_id"] == objective_id]
        if objective_id == TURNOVER_ID:
            latest = sub[sub["period_end"] == sub["period_end"].max()]
            agg = latest.set_index([*DIMS])[["numerator", "denominator", "immature", "unknown_regret"]]
        else:
            agg = sub.groupby(list(DIMS))[["numerator", "denominator", "immature", "unknown_regret"]].sum()
        for (country, unit), r in agg.iterrows():  # type: ignore[misc]
            value = r["numerator"] / r["denominator"] if r["denominator"] > 0 else float("nan")
            rows.append(
                {
                    "objective_id": objective_id,
                    "country_code": country,
                    "business_unit": unit,
                    "numerator": float(r["numerator"]),
                    "denominator": float(r["denominator"]),
                    "value": value,
                    "target_value": objective.target_value,
                    "direction": objective.direction,
                    "meets_target": meets_target(value, objective),
                    "immature": int(r["immature"]),
                    "unknown_regret": int(r["unknown_regret"]),
                }
            )
    return pd.DataFrame(rows)


def exclusion_summary(events: pd.DataFrame, objectives: dict[str, Objective]) -> pd.DataFrame:
    """Where the rows went, per objective (feeds the Trust panel)."""
    total = len(events)
    unclean = int((~events["is_clean_for_analysis"] | events["hire_date"].isna()).sum())
    base = analysis_base(events)
    rows = []
    for rule in COHORT_RULES:
        objective = objectives[rule.objective_id]
        in_scope = base if rule.levels is None else base[base["career_level"].isin(rule.levels)]
        out_of_scope = len(base) - len(in_scope)
        before_window = int((in_scope["hire_date"] < objective.effective_from).sum())
        rows.append(
            {
                "objective_id": rule.objective_id,
                "total_rows": total,
                "excluded_unclean": unclean,
                "excluded_out_of_scope": out_of_scope,
                "excluded_before_effective_window": before_window,
                "in_cohort": len(in_scope) - before_window,
            }
        )
    rows.append(
        {
            "objective_id": TURNOVER_ID,
            "total_rows": total,
            "excluded_unclean": unclean,
            "excluded_out_of_scope": 0,
            "excluded_before_effective_window": 0,
            "in_cohort": len(base),
        }
    )
    return pd.DataFrame(rows)
