"""CLI entry point.

Commands:
  run [--source auto|live|cache|fixtures]
      Full pipeline. --source fixtures works offline (no internet needed).

  verify-data
      Check manifest checksums and print a summary.

  doctor
      Check config and make a small live request per indicator.
      Prints OK/FAIL with actionable message. Use this to verify API access.

  build-dashboard
      Rebuild the dashboard from existing curated CSVs (no re-ingest).

Usage on any OS:
  python -m asteria_retention run --source fixtures
  python -m asteria_retention doctor
  python -m asteria_retention verify-data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asteria_retention.logging_setup import setup_logging


def cmd_run(args: argparse.Namespace) -> int:
    from asteria_retention.pipeline import run

    return run(source=args.source)


def cmd_verify_data(args: argparse.Namespace) -> int:
    from asteria_retention.config import DATA_RAW, MANIFEST_JSON
    from asteria_retention.curate import verify_manifest

    problems = verify_manifest(DATA_RAW, MANIFEST_JSON)
    if problems:
        print("FAIL — manifest check failed:")
        for p in problems:
            print(f"  • {p}")
        return 1
    print("OK — all data files match their checksums in the manifest")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Live connectivity check per indicator. Actionable failure messages."""
    from asteria_retention.config import CANONICAL_COUNTRIES, INDICATORS
    from asteria_retention.ingestion.eurostat import EurostatClient
    from asteria_retention.ingestion.worldbank import WorldBankClient

    clients = {
        "eurostat": EurostatClient(),
        "worldbank": WorldBankClient(),
    }

    all_ok = True
    for indicator in INDICATORS:
        client = clients[indicator.provider]
        print(f"  Checking {indicator.indicator_id} ({indicator.provider})...", end=" ", flush=True)
        try:
            # Just fetch 2 countries to keep the request small
            payload = client.fetch(indicator, CANONICAL_COUNTRIES[:2])
            obs = client.parse(indicator, payload)
            print(f"OK ({len(obs)} observations)")
        except Exception as exc:
            all_ok = False
            print(f"FAIL")
            print(f"    → {exc}")
            if "dimension" in str(exc).lower() or "filter" in str(exc).lower():
                print(f"    → Hint: check Indicator.filters and Indicator.prefer in config.py")
            elif "403" in str(exc) or "forbidden" in str(exc).lower():
                print(f"    → Hint: API may require authentication or is geo-blocked")
            elif "404" in str(exc):
                print(f"    → Hint: dataset code may have changed — check {indicator.docs_url}")

    if all_ok:
        print("\nAll indicators OK — live data access is working.")
        return 0
    else:
        print("\nSome indicators failed. Use --source fixtures to run offline.")
        return 3


def cmd_build_dashboard(args: argparse.Namespace) -> int:
    """Rebuild the dashboard from existing curated CSVs."""
    from asteria_retention.config import (
        DATA_CURATED,
        OBJECTIVES_CSV,
        WORKFORCE_AS_OF,
    )
    from asteria_retention.domain.retention_metrics import load_objectives
    from asteria_retention.ingestion.base import utc_now_iso
    from asteria_retention.reporting.dashboard_build import build_dashboard
    from asteria_retention.reporting.dashboard_data import (
        build_dashboard_payload,
        validate_payload_json,
    )

    import pandas as pd

    def _load_or_empty(path: Path, **kwargs) -> pd.DataFrame:
        return pd.read_csv(path, **kwargs) if path.exists() else pd.DataFrame()

    series = _load_or_empty(DATA_CURATED / "fact_objective_series.csv")
    summary = _load_or_empty(DATA_CURATED / "summary.csv")
    excl = _load_or_empty(DATA_CURATED / "exclusion_summary.csv")
    qual = _load_or_empty(DATA_CURATED / "quality_report.csv")
    coverage = _load_or_empty(DATA_CURATED / "coverage_report.csv")
    external = _load_or_empty(DATA_CURATED / "canonical_external.csv")
    panel = _load_or_empty(DATA_CURATED / "association_panel.csv")
    assoc = _load_or_empty(DATA_CURATED / "association_results.csv")

    if series.empty or summary.empty:
        print("ERROR: curated data not found. Run `python -m asteria_retention run` first.")
        return 1

    objectives = load_objectives(OBJECTIVES_CSV)

    # Fix period_end column to datetime
    for df in [series, summary, external, panel]:
        if "period_end" in df.columns:
            df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")

    payload = build_dashboard_payload(
        series=series,
        summary=summary,
        exclusions=excl,
        quality=qual,
        coverage=coverage,
        external_frame=external,
        panel=panel,
        association=assoc,
        ingestion_outcomes=[],
        cross_check={},
        source_mode="rebuild",
        run_timestamp=utc_now_iso(),
        objectives_config=objectives,
    )
    validate_payload_json(payload)
    out = build_dashboard(payload)
    print(f"Dashboard rebuilt: {out}")
    return 0


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="asteria-retention",
        description="Asteria Retention Analytics — pipeline & utilities",
    )
    parser.add_argument("--version", action="version", version="0.1.0")

    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Execute the full pipeline")
    run_p.add_argument(
        "--source",
        choices=["auto", "live", "cache", "fixtures"],
        default="auto",
        help=(
            "auto: try live, fall back to cache; "
            "fixtures: offline synthetic data (no internet needed); "
            "live: live only; "
            "cache: stored snapshots only"
        ),
    )
    run_p.set_defaults(func=cmd_run)

    vd_p = sub.add_parser("verify-data", help="Check manifest checksums")
    vd_p.set_defaults(func=cmd_verify_data)

    doc_p = sub.add_parser("doctor", help="Check live API connectivity per indicator")
    doc_p.set_defaults(func=cmd_doctor)

    bd_p = sub.add_parser("build-dashboard", help="Rebuild dashboard from curated CSVs")
    bd_p.set_defaults(func=cmd_build_dashboard)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
