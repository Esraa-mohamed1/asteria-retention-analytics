"""Build the analytical panel joining retention outcomes with external indicator observations."""

from __future__ import annotations

import pandas as pd

from asteria_retention.domain.temporal_alignment import as_of_join, assert_no_future_information
from asteria_retention.schemas.panel_schema import PANEL_COLUMNS

NEW_HIRE_OBJECTIVE = "NEW_HIRE_6M"
TURNOVER_OBJECTIVE = "REGRETTED_TURNOVER_12M"
SENIOR_OBJECTIVE = "SENIOR_HIRE_12M"


def _outcome_requests(series_rows: pd.DataFrame) -> pd.DataFrame:
    """Convert series rows into (geo, eval_date) requests for the as-of join."""
    out = series_rows[["country_code", "period_end", "period", "numerator", "denominator", "value"]].copy()
    out = out.rename(columns={"country_code": "geo", "period_end": "eval_date"})
    out["eval_date"] = pd.to_datetime(out["eval_date"])
    return out


def build_panel(
    series: pd.DataFrame,
    observations: pd.DataFrame,
) -> pd.DataFrame:
    """Join retention outcomes to external observations at native frequency without future information."""
    # --- NEW_HIRE_6M panel ---
    new_hire_rows = series[
        (series["objective_id"] == NEW_HIRE_OBJECTIVE)
        & (series["country_code"] != "ALL")
        & (series["business_unit"] == "ALL")
        & (series["denominator"] > 0)
    ].copy()
    new_hire_req = _outcome_requests(new_hire_rows)

    # --- TURNOVER panel (Dec-31 eval dates only) ---
    turn_rows = series[
        (series["objective_id"] == TURNOVER_OBJECTIVE)
        & (series["country_code"] != "ALL")
        & (series["business_unit"] == "ALL")
    ].copy()
    turn_rows = turn_rows[
        pd.to_datetime(turn_rows["period_end"]).dt.month == 12
    ].copy()
    turn_req = _outcome_requests(turn_rows)

    pieces: list[pd.DataFrame] = []
    for obj_id, req_df in [
        (NEW_HIRE_OBJECTIVE, new_hire_req),
        (TURNOVER_OBJECTIVE, turn_req),
    ]:
        if req_df.empty:
            continue
        joined = as_of_join(observations, req_df)
        assert_no_future_information(joined)
        if joined.empty:
            continue
        joined["objective_id"] = obj_id
        pieces.append(joined)

    if not pieces:
        return pd.DataFrame(columns=list(PANEL_COLUMNS))

    panel = pd.concat(pieces, ignore_index=True)
    keep_cols = [c for c in PANEL_COLUMNS if c in panel.columns]
    return panel[keep_cols].reset_index(drop=True)
