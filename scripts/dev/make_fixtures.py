"""Generate deterministic synthetic fixture payloads for all 6 countries.

These are SYNTHETIC values, clearly labelled in every file. They match the
EXACT API response format so the parsers can be tested fully offline.

Eurostat JSON-stat 2.0 fixtures:
  - unemployment_rate  (une_rt_m): monthly, M
  - job_vacancy_rate   (jvs_q_nace2): quarterly, Q — includes multi-category
    dims to exercise the `prefer` selection logic
  - hicp_inflation     (prc_hicp_manr): monthly, M

World Bank [meta, rows] fixtures:
  - gdp_growth            (NY.GDP.MKTP.KD.ZG): annual, A
  - labour_force_participation (SL.TLF.CACT.ZS): annual, A

Run: python scripts/dev/make_fixtures.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

# ---- Configuration -------------------------------------------------------
SEED = 42
GEO_CODES = ["EL", "RO", "PL", "IT", "IE", "BG"]  # Eurostat codes (EL = GR)
ISO3_CODES = {
    "EL": "GRC",
    "RO": "ROU",
    "PL": "POL",
    "IT": "ITA",
    "IE": "IRL",
    "BG": "BGR",
}
ISO2_CODES = {
    "EL": "GR",
    "RO": "RO",
    "PL": "PL",
    "IT": "IT",
    "IE": "IE",
    "BG": "BG",
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"
RETRIEVED_AT = "2026-01-15T08:00:00Z"  # fixed, deterministic
LABEL_WARNING = "SYNTHETIC DATA — for offline testing only. Values are random and do NOT represent real statistics."

rng = random.Random(SEED)


def _monthly_periods(start: str, end: str) -> list[str]:
    """Generate YYYY-MM periods from start to end inclusive."""
    from datetime import date
    year, month = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    periods = []
    while (year, month) <= (ey, em):
        periods.append(f"{year}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return periods


def _quarterly_periods(start: str, end: str) -> list[str]:
    """Generate YYYY-QN periods."""
    year, q = int(start[:4]), int(start[6])
    ey, eq = int(end[:4]), int(end[6])
    periods = []
    while (year, q) <= (ey, eq):
        periods.append(f"{year}-Q{q}")
        q += 1
        if q > 4:
            q = 1
            year += 1
    return periods


def _annual_periods(start_year: int, end_year: int) -> list[str]:
    return [str(y) for y in range(start_year, end_year + 1)]


def make_eurostat_monthly(
    dataset: str,
    geo_codes: list[str],
    periods: list[str],
    value_range: tuple[float, float],
    extra_dims: dict[str, list[str]] | None = None,
    preferred: dict[str, str] | None = None,
    provisional_indices: set[int] | None = None,
) -> dict:
    """Build a Eurostat JSON-stat 2.0 response.

    extra_dims: additional dimensions beyond geo/time. Each maps dim_name -> list of category codes.
    preferred: the single category from each extra_dim that contains real values (others get None).
    """
    if extra_dims is None:
        extra_dims = {}
    if preferred is None:
        preferred = {k: v[0] for k, v in extra_dims.items()}

    n_geo = len(geo_codes)
    n_time = len(periods)
    extra_sizes = [len(v) for v in extra_dims.values()]
    extra_names = list(extra_dims.keys())

    # Build dimension section
    dimensions = {}

    # Extra dims first (they appear before geo/time in the cube)
    for name, codes in extra_dims.items():
        dimensions[name] = {
            "label": name.upper(),
            "category": {
                "index": {code: i for i, code in enumerate(codes)},
                "label": {code: code for code in codes},
            },
        }

    dimensions["geo"] = {
        "label": "Geographic area",
        "category": {
            "index": {g: i for i, g in enumerate(geo_codes)},
            "label": {g: g for g in geo_codes},
        },
    }
    dimensions["time"] = {
        "label": "Time period",
        "category": {
            "index": {p: i for i, p in enumerate(periods)},
            "label": {p: p for p in periods},
        },
    }

    ids = extra_names + ["geo", "time"]
    sizes = extra_sizes + [n_geo, n_time]
    total = 1
    for s in sizes:
        total *= s

    # Build sparse value dict — only populate the preferred slice
    values: dict[str, float | None] = {}
    statuses: dict[str, str] = {}

    # Preferred positions for each extra dim
    pref_pos = {}
    for name, codes in extra_dims.items():
        pref_pos[name] = codes.index(preferred[name])

    # Iterate through all flat indices
    for flat_idx in range(total):
        # Unflatten
        remainder = flat_idx
        coords = []
        for s in reversed(sizes):
            coords.insert(0, remainder % s)
            remainder //= s

        # Check if this is in the preferred slice
        skip = False
        for dim_idx, name in enumerate(extra_names):
            if coords[dim_idx] != pref_pos[name]:
                skip = True
                break

        if skip:
            # Leave as None (sparse — just don't add to dict)
            continue

        val = round(rng.uniform(*value_range), 2)
        values[str(flat_idx)] = val
        if provisional_indices and flat_idx in provisional_indices:
            statuses[str(flat_idx)] = "p"

    return {
        "version": "2.0",
        "class": "dataset",
        "label": f"SYNTHETIC: {dataset} — {LABEL_WARNING}",
        "id": ids,
        "size": sizes,
        "dimension": dimensions,
        "value": values,
        "status": statuses,
    }


def make_worldbank_response(
    indicator_code: str,
    iso3_codes: list[str],
    years: list[str],
    value_range: tuple[float, float],
) -> list:
    """Build a World Bank [meta, rows] response."""
    rows = []
    for iso3 in iso3_codes:
        iso2 = [k for k, v in ISO3_CODES.items() if v == iso3]
        for year in years:
            val = round(rng.uniform(*value_range), 2) if rng.random() > 0.05 else None
            rows.append({
                "indicator": {"id": indicator_code, "value": f"SYNTHETIC {indicator_code}"},
                "country": {"id": iso3[:2], "value": iso3},
                "countryiso3code": iso3,
                "date": year,
                "value": val,
                "unit": "",
                "obs_status": "p" if rng.random() < 0.1 else "",
                "decimal": 2,
            })
    meta = {
        "page": 1,
        "pages": 1,
        "per_page": 1000,
        "total": len(rows),
        "merged_pages": 1,
        "sourceid": "2",
        "lastupdated": "2025-01-01",
    }
    return [meta, rows]


def save_fixture(directory: Path, provider: str, indicator_id: str, body: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body_path = directory / "fixture.json"
    meta_path = directory / "fixture.meta.json"
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    import hashlib
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    body_path.write_text(canonical, encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "provider": provider,
                "indicator_id": indicator_id,
                "url": f"SYNTHETIC/{indicator_id}",
                "params": {},
                "retrieved_at": RETRIEVED_AT,
                "sha256": sha,
                "origin": "fixture_synthetic",
                "label": LABEL_WARNING,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  Written: {body_path}")


def main() -> None:
    monthly_periods = _monthly_periods("2019-01", "2025-11")
    quarterly_periods = _quarterly_periods("2019-Q1", "2025-Q3")
    annual_periods = _annual_periods(2019, 2024)
    iso3_all = list(ISO3_CODES.values())

    print("Generating Eurostat fixtures...")

    # -- unemployment_rate (une_rt_m): simple 3 filter dims already fixed by filters ---
    # The API returns already-filtered for s_adj=SA, age=TOTAL, sex=T, unit=PC_ACT
    # So the JSON-stat will have single-valued dims for those (already filtered server-side)
    ue_body = make_eurostat_monthly(
        "une_rt_m", GEO_CODES, monthly_periods,
        value_range=(2.5, 18.0),
        # Simulate server-side filtering: no extra dims returned
    )
    save_fixture(FIXTURES_DIR / "eurostat" / "unemployment_rate", "eurostat", "unemployment_rate", ue_body)

    # -- hicp_inflation (prc_hicp_manr): unit=RCH_A, coicop=CP00 already filtered ---
    hicp_body = make_eurostat_monthly(
        "prc_hicp_manr", GEO_CODES, monthly_periods,
        value_range=(-1.0, 12.0),
        provisional_indices={10, 25, 100},
    )
    save_fixture(FIXTURES_DIR / "eurostat" / "hicp_inflation", "eurostat", "hicp_inflation", hicp_body)

    # -- job_vacancy_rate (jvs_q_nace2): multi-category dims to exercise `prefer` ---
    # indic_em already in filters -> JOBRATE only (server-side)
    # s_adj: NSA, SA  (prefer NSA)
    # nace_r2: B-S, A-S  (prefer B-S)
    # sizeclas: TOTAL, GE10  (prefer TOTAL)
    jvs_body = make_eurostat_monthly(
        "jvs_q_nace2", GEO_CODES, quarterly_periods,
        value_range=(0.5, 5.0),
        extra_dims={
            "s_adj": ["NSA", "SA"],
            "nace_r2": ["B-S", "A-S"],
            "sizeclas": ["TOTAL", "GE10"],
        },
        preferred={"s_adj": "NSA", "nace_r2": "B-S", "sizeclas": "TOTAL"},
        provisional_indices={5, 50},
    )
    save_fixture(FIXTURES_DIR / "eurostat" / "job_vacancy_rate", "eurostat", "job_vacancy_rate", jvs_body)

    print("Generating World Bank fixtures...")

    # -- gdp_growth ---
    gdp_body = make_worldbank_response(
        "NY.GDP.MKTP.KD.ZG", iso3_all, annual_periods, value_range=(-5.0, 8.0)
    )
    save_fixture(FIXTURES_DIR / "worldbank" / "gdp_growth", "worldbank", "gdp_growth", gdp_body)

    # -- labour_force_participation ---
    lfp_body = make_worldbank_response(
        "SL.TLF.CACT.ZS", iso3_all, annual_periods, value_range=(55.0, 80.0)
    )
    save_fixture(FIXTURES_DIR / "worldbank" / "labour_force_participation", "worldbank", "labour_force_participation", lfp_body)

    print(f"\nAll fixtures written to {FIXTURES_DIR}")
    print("WARNING: These are SYNTHETIC values for offline testing only.")
    print("Any association results computed from these fixtures are for demonstration only.")


if __name__ == "__main__":
    main()
