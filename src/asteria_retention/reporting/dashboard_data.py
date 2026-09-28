"""Dashboard data payload builder.

Produces one big JSON-serialisable dict that the dashboard JS reads from
the embedded <script id="asteria-data"> tag.

Rules:
- NaN -> null (json.dumps allow_nan=False enforced)
- Timestamps converted to ISO strings
- Synthetic fixture origin triggers a red banner notice
- Failed indicators appear in warnings list
"""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Any

import pandas as pd

from asteria_retention.config import (
    CANONICAL_COUNTRIES,
    COUNTRIES,
    INDICATORS,
    INDICATORS_BY_ID,
    SOURCE_ATTRIBUTION,
    WORKFORCE_AS_OF,
)
from asteria_retention.domain.retention_metrics import meets_target


def _nan_to_null(obj: Any) -> Any:
    """Recursively replace float NaN/Inf and numpy types with JSON-safe Python types."""
    import numpy as np  # local import to keep module importable without numpy

    if isinstance(obj, bool):  # check bool before int (bool is subclass of int)
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _nan_to_null(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nan_to_null(v) for v in obj]
    return obj


def _ts(val: Any) -> str | None:
    """Convert Timestamp/date/str to ISO string."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    return str(val)


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> list of dicts with NaN -> None, Timestamps -> ISO strings."""
    records = []
    for row in df.to_dict("records"):
        clean = {}
        for k, v in row.items():
            if isinstance(v, pd.Timestamp):
                clean[k] = _ts(v)
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean[k] = None
            elif isinstance(v, (pd.Period,)):
                clean[k] = str(v)
            else:
                clean[k] = v
        records.append(clean)
    return records


def build_dashboard_payload(
    series: pd.DataFrame,
    summary: pd.DataFrame,
    exclusions: pd.DataFrame,
    quality: pd.DataFrame,
    coverage: pd.DataFrame,
    external_frame: pd.DataFrame,
    panel: pd.DataFrame,
    association: pd.DataFrame,
    ingestion_outcomes: list[dict[str, Any]],
    cross_check: dict[str, Any],
    source_mode: str,
    run_timestamp: str,
    objectives_config: dict[str, Any],
) -> dict[str, Any]:
    """Build the complete dashboard payload dict."""

    # ---- meta ----
    # Detect if any external data came from synthetic fixtures
    has_synthetic = not external_frame.empty and (
        external_frame["data_origin"].eq("fixture_synthetic").any()
    )
    failed_indicators = [o for o in ingestion_outcomes if o.get("status") != "ok"]
    stale_count = 0 if external_frame.empty else int(
        external_frame.get("obs_status", pd.Series(dtype=str)).eq("").eq(False).sum()
        if "obs_status" in external_frame else 0
    )

    notices: list[dict[str, str]] = []
    if has_synthetic:
        notices.append({
            "level": "warning",
            "message": (
                "⚠️ Some external data comes from SYNTHETIC fixture files. "
                "Any association results shown are for demonstration only. "
                "Run with --source live for real data."
            ),
        })
    for failed in failed_indicators:
        notices.append({
            "level": "warning",
            "message": f"External indicator failed: {failed.get('indicator_id', '?')} — {failed.get('error', '')}",
        })

    # ---- countries ----
    countries_data = [
        {"iso2": c.iso2, "iso3": c.iso3, "name": c.name}
        for c in COUNTRIES.values()
    ]

    # ---- business_units ----
    bus_units = sorted(
        [u for u in series["business_unit"].unique() if u != "ALL"],
        key=str,
    )

    # ---- objectives ----
    objectives_data = []
    for obj_id, obj in objectives_config.items():
        objectives_data.append({
            "objective_id": obj_id,
            "name": obj.name,
            "direction": obj.direction,
            "target_value": obj.target_value,
            "unit": obj.unit,
            "effective_from": _ts(obj.effective_from),
            "effective_to": _ts(obj.effective_to),
        })

    # ---- series ----
    series_cols = [
        "objective_id", "country_code", "business_unit", "period", "period_end",
        "numerator", "denominator", "value", "immature", "unknown_regret",
    ]
    series_for_dash = series[[c for c in series_cols if c in series.columns]].copy()
    series_data = {
        "columns": [c for c in series_cols if c in series.columns],
        "rows": _df_to_records(series_for_dash),
    }

    # ---- summary ----
    summary_data = _df_to_records(summary)
    for row in summary_data:
        # Add human-readable status
        if row.get("value") is not None:
            obj_cfg = objectives_config.get(row["objective_id"])
            if obj_cfg:
                row["status_text"] = (
                    "✅ On target" if meets_target(row["value"], obj_cfg) else "❌ Off target"
                )
        small_n = (row.get("denominator") or 0) < 30
        row["small_n_warning"] = small_n

    # ---- external ----
    ext_meta = []
    for ind in INDICATORS:
        # Find the latest observation for this indicator across all countries
        if external_frame.empty:
            ext_meta.append({
                "indicator_id": ind.indicator_id,
                "label": ind.label,
                "lens": ind.lens,
                "frequency": ind.frequency,
                "unit": ind.unit,
                "provider": ind.provider,
                "latest_period": None,
                "latest_available_from": None,
                "age_days": None,
                "data_origin": None,
                "n_observations": 0,
                "n_stale": 0,
            })
            continue
        sub = external_frame[external_frame["indicator_id"] == ind.indicator_id]
        if sub.empty:
            latest_period = None
            latest_avail = None
            age_days = None
            origin = None
            n_stale = 0
        else:
            latest = sub.sort_values("period_end").iloc[-1]
            latest_period = latest["period"]
            latest_avail = _ts(latest["available_from"])
            age_days = None
            # age relative to as_of
            as_of_ts = pd.Timestamp(WORKFORCE_AS_OF)
            period_end_ts = pd.to_datetime(latest["period_end"])
            age_days = (as_of_ts - period_end_ts).days if pd.notna(period_end_ts) else None
            origin = latest["data_origin"]
            # Count observations where obs_status != "" as "flagged"
            n_stale = int((sub["obs_status"] != "").sum()) if "obs_status" in sub else 0

        ext_meta.append({
            "indicator_id": ind.indicator_id,
            "label": ind.label,
            "lens": ind.lens,
            "frequency": ind.frequency,
            "unit": ind.unit,
            "provider": ind.provider,
            "latest_period": latest_period,
            "latest_available_from": latest_avail,
            "age_days": age_days,
            "data_origin": origin,
            "n_observations": len(sub) if not external_frame.empty else 0,
            "n_stale": n_stale,
        })

    # Observations for the trend chart (external overlay)
    ext_obs = []
    if not external_frame.empty:
        obs_cols = ["indicator_id", "geo", "period", "period_end", "value", "unit", "obs_status", "data_origin"]
        ext_obs_df = external_frame[[c for c in obs_cols if c in external_frame.columns]].copy()
        ext_obs = _df_to_records(ext_obs_df)

    # ---- panel ----
    panel_data = _df_to_records(panel) if not panel.empty else []

    # ---- association ----
    assoc_data = _df_to_records(association) if not association.empty else []

    # ---- quality ----
    quality_data = _df_to_records(quality)

    # ---- exclusions ----
    exclusions_data = _df_to_records(exclusions)

    # ---- coverage ----
    coverage_data = _df_to_records(coverage)

    # ---- sources ----
    sources_data = [
        {
            "provider": provider,
            **info,
            "indicators": [
                {
                    "indicator_id": i.indicator_id,
                    "label": i.label,
                    "dataset": i.dataset,
                    "lens": i.lens,
                    "frequency": i.frequency,
                    "publication_lag_days": i.publication_lag_days,
                    "docs_url": i.docs_url,
                }
                for i in INDICATORS
                if i.provider == provider
            ],
        }
        for provider, info in SOURCE_ATTRIBUTION.items()
    ]

    # ---- methodology ----
    methodology = {
        "decisions": [
            {
                "topic": "Blank/invalid rows",
                "decision": "Flag, never delete or guess. Blocking flags exclude a row from every metric.",
            },
            {
                "topic": "Country aliases",
                "decision": "EL→GR, ROM→RO. Anything else (including blank) = unknown_country_code (blocking).",
            },
            {
                "topic": "Sr Mgmt career level",
                "decision": "Kept as its own category (nonstandard_career_level_kept_separate). Not counted as a Senior hire.",
            },
            {
                "topic": "Cohort maturity",
                "decision": "hire_date + N months <= as_of. Immature hires are excluded and reported (not counted as failures).",
            },
            {
                "topic": "Effective window",
                "decision": "Cohorts hired inside [effective_from, effective_to] only. Hires before 2021-01-01 excluded.",
            },
            {
                "topic": "Retained definition",
                "decision": "No termination, or termination strictly after hire_date + N months.",
            },
            {
                "topic": "Senior scope",
                "decision": "career_level == 'Senior Leader' only. Managers and Sr Mgmt excluded.",
            },
            {
                "topic": "Turnover",
                "decision": "Trailing 12 months; numerator = exits with regretted_exit == 'true'; denominator = average headcount at window start and end.",
            },
            {
                "topic": "External data frequency",
                "decision": "Native frequency preserved. Never resampled. As-of join on available_from = period_end + publication_lag. Stale values excluded from analysis.",
            },
            {
                "topic": "SENIOR_HIRE_12M association",
                "decision": "Skipped — cohorts of 2-3 per country-quarter, below the minimum of 8 pairs. Recorded as explicit non-finding.",
            },
        ],
        "publication_lag_note": (
            "Publication lags are conservative assumptions (unemployment 45d, HICP 30d, "
            "job vacancy 90d, WB GDP 300d, WB LFP 365d). Not verified against official "
            "release calendars. Use --source live and `doctor` to verify."
        ),
        "frequency_integrity": (
            "Annual World Bank values are never presented as 12 new monthly values. "
            "Each observation keeps its native period label and publication_lag_days."
        ),
    }

    # ---- cross-check ----
    cross_check_data = _nan_to_null(cross_check)

    payload = {
        "meta": {
            "as_of": str(WORKFORCE_AS_OF),
            "run_timestamp": run_timestamp,
            "source_mode": source_mode,
            "has_synthetic_external": has_synthetic,
            "n_indicators": len(INDICATORS),
            "n_countries": len(CANONICAL_COUNTRIES),
        },
        "notices": notices,
        "countries": countries_data,
        "business_units": bus_units,
        "objectives": objectives_data,
        "series": series_data,
        "summary": summary_data,
        "external_meta": ext_meta,
        "external_observations": ext_obs,
        "panel": panel_data,
        "association": assoc_data,
        "quality": quality_data,
        "exclusions": exclusions_data,
        "coverage": coverage_data,
        "sources": sources_data,
        "methodology": methodology,
        "cross_check": cross_check_data,
    }

    return _nan_to_null(payload)


def validate_payload_json(payload: dict[str, Any]) -> str:
    """Serialise to JSON and verify no NaN sneaked through. Returns the JSON string."""
    return json.dumps(payload, allow_nan=False, ensure_ascii=False)
