"""Integration and domain unit tests for the retention analytics pipeline."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from asteria_retention.config import (
    INDICATORS_BY_ID,
    COUNTRIES,
    DATA_RAW,
    DATA_CURATED,
    EVENTS_CSV,
    OBJECTIVES_CSV,
    MANIFEST_JSON,
    WORKFORCE_AS_OF,
)
from asteria_retention.curate import (
    verify_manifest,
    load_events,
    canonicalize_events,
    quality_report,
)
from asteria_retention.domain import (
    load_objectives,
    build_series,
    summarise,
    as_of_join,
    assert_no_future_information,
)
from asteria_retention.analysis import (
    build_panel,
    correlate,
    run_sql_analysis,
)
from asteria_retention.errors import ContractViolation


@pytest.fixture(scope="session")
def curated_data():
    raw_events = load_events(EVENTS_CSV)
    events = canonicalize_events(raw_events)
    dq = quality_report(events)
    objectives = load_objectives(OBJECTIVES_CSV)
    as_of = pd.Timestamp(WORKFORCE_AS_OF)
    series = build_series(events, objectives, as_of)
    summary = summarise(series, objectives)
    
    # Load external observations from curated CSV
    ext_csv = DATA_CURATED / "canonical_external.csv"
    if ext_csv.exists():
        obs = pd.read_csv(ext_csv)
    else:
        obs = pd.DataFrame()
        
    panel = build_panel(series, obs)
    assoc = correlate(panel)
    return {
        "events": events,
        "dq": dq,
        "obs": obs,
        "series": series,
        "summary": summary,
        "panel": panel,
        "assoc": assoc,
        "as_of": as_of,
    }


def test_manifest_verification():
    """Verify that all fixture / raw files match their declared SHA-256 hashes."""
    problems = verify_manifest(DATA_RAW, MANIFEST_JSON)
    assert not problems, f"Manifest verification failed: {problems}"


def test_events_curation_clean_flags(curated_data):
    """Verify that dirty records are flagged and clean records are preserved."""
    events = curated_data["events"]
    assert "is_clean_for_analysis" in events.columns
    assert "country_code" in events.columns
    # Check that ISO-2 codes are 2 characters
    clean = events[events["is_clean_for_analysis"] == True]
    assert len(clean) > 0
    assert clean["country_code"].str.len().eq(2).all()


def test_no_future_information_in_panel(curated_data):
    """Ensure that in all panel observations, available_from <= eval_date."""
    panel = curated_data["panel"]
    assert not panel.empty
    assert_no_future_information(panel)
    # Check explicit date condition
    assert (pd.to_datetime(panel["ind_available_from"]) <= pd.to_datetime(panel["eval_date"])).all()


def test_retention_metrics_ranges(curated_data):
    """Check that calculated retention rates and turnover rates are within [0, 1]."""
    series = curated_data["series"]
    valid_values = series["value"].dropna()
    assert (valid_values >= 0.0).all()
    assert (valid_values <= 1.0).all()


def test_association_non_findings_recorded(curated_data):
    """Check that SENIOR_HIRE_12M has an explicit non-finding record."""
    assoc = curated_data["assoc"]
    sh_record = assoc[assoc["objective_id"] == "SENIOR_HIRE_12M"]
    assert not sh_record.empty
    assert sh_record.iloc[0]["insufficient_n"] == True


def test_sql_cross_check(curated_data, tmp_path):
    """Check that DuckDB SQL recomputation matches Pandas metrics within tolerance."""
    db_file = tmp_path / "test_analytics.duckdb"
    events_csv = DATA_CURATED / "canonical_events.csv"
    
    cross_check = run_sql_analysis(
        events_csv=events_csv,
        series_df=curated_data["series"],
        summary_df=curated_data["summary"],
        external_df=curated_data["obs"],
        panel_df=curated_data["panel"],
        association_df=curated_data["assoc"],
        quality_df=curated_data["dq"],
        coverage_df=pd.DataFrame(),
        db_path=db_file,
    )
    
    for obj, res in cross_check.items():
        if isinstance(res, dict) and "status" in res:
            assert res["status"] == "PASS", f"Cross check failed for {obj}: {res}"
