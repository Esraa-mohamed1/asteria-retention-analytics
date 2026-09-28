"""Temporal alignment: join external indicator values to outcome dates without future data leakage."""

from __future__ import annotations

import pandas as pd

from asteria_retention.config import INDICATORS_BY_ID
from asteria_retention.errors import ContractViolation


def as_of_join(
    observations: pd.DataFrame,
    requests: pd.DataFrame,
    *,
    indicator_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Join external observations to outcome requests without future information."""
    if observations.empty or "indicator_id" not in observations.columns:
        return pd.DataFrame()

    if indicator_ids is None:
        indicator_ids = list(INDICATORS_BY_ID.keys())

    obs = observations[observations["indicator_id"].isin(indicator_ids)].copy()
    if obs.empty:
        base = requests.copy()
        base["indicator_id"] = pd.NA
        base["period"] = pd.NA
        base["period_end"] = pd.NaT
        base["available_from"] = pd.NaT
        base["value"] = float("nan")
        base["unit"] = pd.NA
        base["obs_status"] = pd.NA
        base["data_origin"] = pd.NA
        base["age_days"] = float("nan")
        base["stale"] = True
        return base.iloc[0:0]

    obs["available_from"] = pd.to_datetime(obs["available_from"])
    obs["period_end"] = pd.to_datetime(obs["period_end"])

    req = requests.copy()
    req["eval_date"] = pd.to_datetime(req["eval_date"])

    pieces: list[pd.DataFrame] = []
    for iid in indicator_ids:
        ind_obs = obs[obs["indicator_id"] == iid].sort_values("available_from")
        if ind_obs.empty:
            continue
        for geo in req["geo"].unique():
            geo_obs = ind_obs[ind_obs["geo"] == geo].reset_index(drop=True)
            geo_req = req[req["geo"] == geo].sort_values("eval_date").reset_index(drop=True)
            if geo_obs.empty or geo_req.empty:
                continue
            obs_for_merge = geo_obs[
                [
                    "available_from",
                    "period",
                    "period_end",
                    "value",
                    "unit",
                    "obs_status",
                    "data_origin",
                ]
            ].rename(
                columns={
                    "period": "ind_period",
                    "period_end": "ind_period_end",
                    "available_from": "ind_available_from",
                    "value": "ind_value",
                    "unit": "ind_unit",
                    "obs_status": "ind_obs_status",
                    "data_origin": "ind_data_origin",
                }
            )
            joined = pd.merge_asof(
                geo_req,
                obs_for_merge,
                left_on="eval_date",
                right_on="ind_available_from",
                direction="backward",
            )
            joined["indicator_id"] = iid
            pieces.append(joined)

    if not pieces:
        return pd.DataFrame()

    result = pd.concat(pieces, ignore_index=True)
    result = result[result["ind_value"].notna()].copy()
    result["age_days"] = (result["eval_date"] - result["ind_period_end"]).dt.days

    max_ages: dict[str, int] = {iid: INDICATORS_BY_ID[iid].max_age_days for iid in indicator_ids if iid in INDICATORS_BY_ID}
    result["stale"] = result.apply(
        lambda r: bool(r["age_days"] > max_ages.get(r["indicator_id"], 9999)),
        axis=1,
    )
    return result.reset_index(drop=True)


def assert_no_future_information(joined: pd.DataFrame) -> None:
    """Anti-look-ahead invariant: verify no joined value was available_from > eval_date."""
    if joined.empty:
        return
    avail_col = "ind_available_from" if "ind_available_from" in joined.columns else "available_from"
    if avail_col not in joined.columns or "eval_date" not in joined.columns:
        return
    bad = joined[
        joined[avail_col].notna()
        & joined["eval_date"].notna()
        & (joined[avail_col] > joined["eval_date"])
    ]
    if not bad.empty:
        sample = bad[["geo", "indicator_id", "eval_date", avail_col]].head(5).to_dict("records")
        raise ContractViolation(
            f"Future information detected in as_of_join! {len(bad)} rows have "
            f"{avail_col} > eval_date. Sample: {sample}"
        )
