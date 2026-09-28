"""Full pipeline: manifest -> ingest -> curate -> metrics -> analysis -> report.

Exit codes:
  0  everything succeeded
  3  completed but with degraded external data (failed indicators or cached snapshots)
  1  fatal error (manifest mismatch, SQL cross-check failure, etc.)

Reruns are deterministic: same inputs => identical curated CSV bytes.
retrieved_at comes from the payload metadata (not from time.time() at write time).
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import pandas as pd

from asteria_retention.config import (
    CANONICAL_COUNTRIES,
    DATA_CURATED,
    DATA_EXTERNAL_RAW,
    DATA_FIXTURES,
    DATA_RAW,
    EVENTS_CSV,
    INDICATORS,
    MANIFEST_JSON,
    OBJECTIVES_CSV,
    WORKFORCE_AS_OF,
)
from asteria_retention.curate import (
    build_external_frame,
    coverage_report,
    validate_external_frame,
    canonicalize_events,
    load_events,
    quality_report,
    verify_manifest,
)
from asteria_retention.domain import (
    build_series,
    exclusion_summary,
    load_objectives,
    summarise,
)
from asteria_retention.errors import AsteriaError, ContractViolation, DataIntegrityError
from asteria_retention.ingestion.base import ORIGIN_FIXTURE
from asteria_retention.ingestion.eurostat import EurostatClient
from asteria_retention.ingestion.service import IngestionService
from asteria_retention.ingestion.store import RawStore
from asteria_retention.ingestion.worldbank import WorldBankClient
from asteria_retention.logging_setup import setup_logging
from asteria_retention.reporting.dashboard_build import build_dashboard
from asteria_retention.reporting.dashboard_data import (
    build_dashboard_payload,
    validate_payload_json,
)
from asteria_retention.reporting.run_report import RunReport

logger = logging.getLogger(__name__)


def _stage_timer() -> "StageTimer":
    return StageTimer()


class StageTimer:
    def __init__(self) -> None:
        self._t = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self._t


def run(source: str = "auto") -> int:
    """Execute the full pipeline. Returns exit code (0, 1, or 3)."""
    from asteria_retention.ingestion.base import utc_now_iso

    setup_logging()
    run_ts = utc_now_iso()
    report = RunReport(run_ts, source)
    exit_code = 0

    # --- 1. Manifest verification ---
    t = _stage_timer()
    try:
        problems = verify_manifest(DATA_RAW, MANIFEST_JSON)
        if problems:
            for p in problems:
                logger.error("Manifest: %s", p)
            raise DataIntegrityError(f"Manifest check failed: {problems}")
        report.record_stage("manifest_verify", "ok", duration_s=t.elapsed())
        logger.info("Manifest OK")
    except DataIntegrityError as exc:
        report.record_stage("manifest_verify", "fatal", duration_s=t.elapsed(), detail=str(exc))
        report.write(
            DATA_CURATED / "run_report.json",
            exit_code=1,
            ingestion_outcomes=[],
            cross_check={},
        )
        logger.critical("Fatal: %s", exc)
        return 1

    # --- 2. Ingest external data ---
    t = _stage_timer()
    live_store = RawStore(DATA_EXTERNAL_RAW)
    fixture_store = RawStore(DATA_FIXTURES)
    clients = {
        "eurostat": EurostatClient(),
        "worldbank": WorldBankClient(),
    }
    service = IngestionService(clients, live_store, fixture_store)

    ingest_result = service.ingest(INDICATORS, CANONICAL_COUNTRIES, source)
    ingestion_outcomes = [
        {
            "indicator_id": o.indicator_id,
            "provider": o.provider,
            "status": o.status,
            "origin": o.origin,
            "n_observations": o.n_observations,
            "retrieved_at": o.retrieved_at,
            "snapshot_age_days": o.snapshot_age_days,
            "error": o.error,
            "note": o.note,
        }
        for o in ingest_result.outcomes
    ]
    stage_status = "ok"
    if ingest_result.failed:
        stage_status = "degraded"
        exit_code = max(exit_code, 3)
        logger.warning("%d indicator(s) failed: %s", len(ingest_result.failed), [f.indicator_id for f in ingest_result.failed])
    report.record_stage(
        "ingest_external",
        stage_status,
        duration_s=t.elapsed(),
        rows=len(ingest_result.observations),
        detail=f"source={source}, failed={[f.indicator_id for f in ingest_result.failed]}",
    )

    # --- 3. Build and validate external frame ---
    t = _stage_timer()
    try:
        external_frame = build_external_frame(ingest_result.observations)
        if not external_frame.empty:
            validate_external_frame(external_frame, [i.indicator_id for i in INDICATORS])
        cov_report = coverage_report(external_frame)
        report.record_stage("curate_external", "ok", duration_s=t.elapsed(), rows=len(external_frame))
    except ContractViolation as exc:
        logger.error("External frame contract violated: %s", exc)
        external_frame = pd.DataFrame()
        cov_report = pd.DataFrame()
        exit_code = max(exit_code, 3)
        report.record_stage("curate_external", "degraded", duration_s=t.elapsed(), detail=str(exc))

    # --- 4. Curate workforce events ---
    t = _stage_timer()
    try:
        raw_events = load_events(EVENTS_CSV)
        events = canonicalize_events(raw_events)
        qual_report = quality_report(events)
        report.record_stage("curate_workforce", "ok", duration_s=t.elapsed(), rows=len(events))
        logger.info("Events: %d total, %d clean", len(events), events["is_clean_for_analysis"].sum())
    except (ContractViolation, OSError) as exc:
        logger.critical("Cannot load workforce data: %s", exc)
        report.record_stage("curate_workforce", "fatal", duration_s=t.elapsed(), detail=str(exc))
        report.write(DATA_CURATED / "run_report.json", exit_code=1, ingestion_outcomes=ingestion_outcomes, cross_check={})
        return 1

    # --- 5. Compute retention metrics ---
    t = _stage_timer()
    try:
        objectives = load_objectives(OBJECTIVES_CSV)
        as_of = pd.Timestamp(WORKFORCE_AS_OF)
        series = build_series(events, objectives, as_of)
        summary = summarise(series, objectives)
        excl = exclusion_summary(events, objectives)
        report.record_stage("compute_metrics", "ok", duration_s=t.elapsed(), rows=len(series))
    except (ContractViolation, Exception) as exc:
        logger.critical("Metrics computation failed: %s", exc)
        report.record_stage("compute_metrics", "fatal", duration_s=t.elapsed(), detail=str(exc))
        report.write(DATA_CURATED / "run_report.json", exit_code=1, ingestion_outcomes=ingestion_outcomes, cross_check={})
        return 1

    # --- 6. Panel and association ---
    t = _stage_timer()
    panel = pd.DataFrame()
    assoc = pd.DataFrame()
    try:
        from asteria_retention.analysis import correlate, build_panel, run_sql_analysis

        panel = build_panel(series, external_frame)
        assoc = correlate(panel)
        report.record_stage("analysis_panel_association", "ok", duration_s=t.elapsed(), rows=len(panel))
    except Exception as exc:
        logger.error("Panel/association failed: %s", exc, exc_info=True)
        exit_code = max(exit_code, 3)
        report.record_stage("analysis_panel_association", "degraded", duration_s=t.elapsed(), detail=str(exc))

    # --- 7. SQL cross-check ---
    t = _stage_timer()
    cross_check: dict = {}
    try:
        DATA_CURATED.mkdir(parents=True, exist_ok=True)
        cross_check = run_sql_analysis(
            events_csv=DATA_CURATED / "canonical_events.csv",  # canonical, not raw
            series_df=series,
            summary_df=summary,
            external_df=external_frame,
            panel_df=panel,
            association_df=assoc,
            quality_df=qual_report,
            coverage_df=cov_report,
            db_path=DATA_CURATED / "analytics.duckdb",
        )
        failed_checks = [k for k, v in cross_check.items() if isinstance(v, dict) and v.get("status") not in ("PASS", "error", "pandas_missing")]
        if failed_checks:
            raise ContractViolation(f"SQL cross-check FAILED for: {failed_checks}")
        report.record_stage("sql_cross_check", "ok", duration_s=t.elapsed(), detail=str({k: v.get("status") for k, v in cross_check.items() if isinstance(v, dict)}))
    except ContractViolation as exc:
        logger.critical("SQL cross-check mismatch: %s", exc)
        report.record_stage("sql_cross_check", "fatal", duration_s=t.elapsed(), detail=str(exc))
        report.write(DATA_CURATED / "run_report.json", exit_code=1, ingestion_outcomes=ingestion_outcomes, cross_check=cross_check)
        return 1
    except Exception as exc:
        logger.error("SQL cross-check error: %s", exc, exc_info=True)
        exit_code = max(exit_code, 3)
        report.record_stage("sql_cross_check", "degraded", duration_s=t.elapsed(), detail=str(exc))

    # --- 8. Write curated CSVs ---
    t = _stage_timer()
    try:
        DATA_CURATED.mkdir(parents=True, exist_ok=True)
        events.to_csv(DATA_CURATED / "canonical_events.csv", index=False)
        series.to_csv(DATA_CURATED / "fact_objective_series.csv", index=False)
        summary.to_csv(DATA_CURATED / "summary.csv", index=False)
        excl.to_csv(DATA_CURATED / "exclusion_summary.csv", index=False)
        qual_report.to_csv(DATA_CURATED / "quality_report.csv", index=False)
        if not external_frame.empty:
            external_frame.to_csv(DATA_CURATED / "canonical_external.csv", index=False)
        if not cov_report.empty:
            cov_report.to_csv(DATA_CURATED / "coverage_report.csv", index=False)
        if not panel.empty:
            panel.to_csv(DATA_CURATED / "association_panel.csv", index=False)
        if not assoc.empty:
            assoc.to_csv(DATA_CURATED / "association_results.csv", index=False)
        report.record_stage("write_curated_csvs", "ok", duration_s=t.elapsed())
    except OSError as exc:
        logger.error("Write curated CSVs failed: %s", exc)
        exit_code = max(exit_code, 3)
        report.record_stage("write_curated_csvs", "degraded", duration_s=t.elapsed(), detail=str(exc))

    # --- 9. Build dashboard ---
    t = _stage_timer()
    try:
        payload = build_dashboard_payload(
            series=series,
            summary=summary,
            exclusions=excl,
            quality=qual_report,
            coverage=cov_report,
            external_frame=external_frame,
            panel=panel,
            association=assoc,
            ingestion_outcomes=ingestion_outcomes,
            cross_check=cross_check,
            source_mode=source,
            run_timestamp=run_ts,
            objectives_config=objectives,
        )
        validate_payload_json(payload)
        build_dashboard(payload)
        report.record_stage("build_dashboard", "ok", duration_s=t.elapsed())
        logger.info("Dashboard built")
    except Exception as exc:
        logger.error("Dashboard build failed: %s", exc, exc_info=True)
        exit_code = max(exit_code, 3)
        report.record_stage("build_dashboard", "degraded", duration_s=t.elapsed(), detail=str(exc))

    # --- 10. Write run report ---
    notes = []
    if exit_code == 3:
        notes.append("Pipeline completed with degraded external data. Workforce outputs are complete and reliable.")
    report.write(
        DATA_CURATED / "run_report.json",
        exit_code=exit_code,
        ingestion_outcomes=ingestion_outcomes,
        cross_check=cross_check,
        notes=notes,
    )

    if exit_code == 0:
        logger.info("Pipeline completed successfully (exit 0)")
    elif exit_code == 3:
        logger.warning("Pipeline completed with degraded external data (exit 3)")
    return exit_code
