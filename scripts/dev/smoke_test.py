"""Quick smoke test of the pipeline."""
from asteria_retention.curate import load_events, canonicalize_events, quality_report, verify_manifest
from asteria_retention.config import EVENTS_CSV, MANIFEST_JSON, DATA_RAW, OBJECTIVES_CSV, WORKFORCE_AS_OF
from asteria_retention.domain import build_series, load_objectives, summarise
import pandas as pd

print("=== MANIFEST ===")
problems = verify_manifest(DATA_RAW, MANIFEST_JSON)
print("OK" if not problems else problems)

print("\n=== EVENTS ===")
events_raw = load_events(EVENTS_CSV)
print(f"Loaded {len(events_raw)} events")
events = canonicalize_events(events_raw)
clean = events["is_clean_for_analysis"].sum()
excluded = (~events["is_clean_for_analysis"]).sum()
print(f"Clean: {clean}, Excluded: {excluded}")

print("\n=== QUALITY FLAGS ===")
q = quality_report(events)
print(q.to_string(index=False))

print("\n=== OBJECTIVES ===")
objectives = load_objectives(OBJECTIVES_CSV)
for obj_id, obj in objectives.items():
    print(f"  {obj_id}: target={obj.target_value} ({obj.direction})")

print("\n=== SERIES ===")
as_of = pd.Timestamp(WORKFORCE_AS_OF)
series = build_series(events, objectives, as_of)
print(f"Series rows: {len(series)}")

print("\n=== SUMMARY ===")
summary = summarise(series, objectives)
totals = summary[(summary["country_code"] == "ALL") & (summary["business_unit"] == "ALL")]
print(totals[["objective_id", "numerator", "denominator", "value", "target_value", "meets_target"]].to_string(index=False))
