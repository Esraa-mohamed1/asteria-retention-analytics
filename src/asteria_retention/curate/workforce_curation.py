"""Workforce lifecycle event curation, data hygiene flags, and quality reporting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from asteria_retention.config import (
    COUNTRY_CODE_ALIASES,
    STANDARD_CAREER_LEVELS,
)
from asteria_retention.errors import ContractViolation
from asteria_retention.schemas.event_schema import (
    BLOCKING_FLAGS,
    FLAG_DESCRIPTIONS,
    INFORMATIONAL_FLAGS,
    REQUIRED_EVENT_COLUMNS,
)

REQUIRED_COLUMNS = REQUIRED_EVENT_COLUMNS


def load_events(csv_path: Path) -> pd.DataFrame:
    """Read as text only: no type guessing, blanks stay blank ("true" stays "true")."""
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ContractViolation(f"{csv_path} is missing columns: {sorted(missing)}")
    return df


def verify_manifest(raw_dir: Path, manifest_path: Path) -> list[str]:
    """Return a list of problems (empty = every supplied file matches its checksum)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for entry in manifest["files"]:
        path = raw_dir / entry["name"]
        if not path.exists():
            problems.append(f"{entry['name']}: file missing")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"{entry['name']}: sha256 does not match the manifest")
        line_count = data.decode("utf-8").count("\n")
        if line_count != entry["rows_including_header"]:
            problems.append(
                f"{entry['name']}: {line_count} lines, manifest says {entry['rows_including_header']}"
            )
    return problems


def canonicalize_events(raw: pd.DataFrame) -> pd.DataFrame:
    """Return the canonical events table with typed dates, `quality_flags` and
    `is_clean_for_analysis`. Row count is always identical to the input."""
    df = raw.copy()

    df["country_code_raw"] = df["country_code"]
    df["country_code"] = df["country_code_raw"].map(COUNTRY_CODE_ALIASES)

    df["career_level_raw"] = df["career_level"]

    hire_text = df["hire_date"].astype(str)
    term_text = df["termination_date"].astype(str)
    df["hire_date"] = pd.to_datetime(hire_text, errors="coerce", format="%Y-%m-%d")
    df["termination_date"] = pd.to_datetime(term_text, errors="coerce", format="%Y-%m-%d")

    masks = pd.DataFrame(index=df.index)
    masks["unknown_country_code"] = df["country_code"].isna()
    masks["missing_hire_date"] = hire_text.str.strip() == ""
    masks["unparseable_hire_date"] = df["hire_date"].isna() & ~masks["missing_hire_date"]
    masks["unparseable_termination_date"] = df["termination_date"].isna() & (term_text.str.strip() != "")
    masks["termination_before_hire"] = (
        df["hire_date"].notna()
        & df["termination_date"].notna()
        & (df["termination_date"] < df["hire_date"])
    )
    masks["duplicate_employee_id"] = df["employee_id"].duplicated(keep="first")
    masks["termination_missing_type"] = df["termination_date"].notna() & (
        df["termination_type"].astype(str).str.strip() == ""
    )
    masks["nonstandard_career_level_kept_separate"] = ~df["career_level"].isin(
        list(STANDARD_CAREER_LEVELS)
    )
    masks["voluntary_exit_missing_regret_flag"] = (df["termination_type"] == "Voluntary") & (
        df["regretted_exit"].astype(str).str.strip() == ""
    )

    columns = list(masks.columns)
    df["quality_flags"] = [",".join(c for c, hit in zip(columns, row, strict=True) if hit) for row in masks.to_numpy()]
    df["is_clean_for_analysis"] = ~masks[list(BLOCKING_FLAGS)].any(axis=1)
    return df


def quality_report(canonical: pd.DataFrame) -> pd.DataFrame:
    """One row per flag (including zero-count flags) for the dashboard's Trust panel."""
    total = len(canonical)
    rows = []
    for flag in (*BLOCKING_FLAGS, *INFORMATIONAL_FLAGS):
        count = int(canonical["quality_flags"].str.split(",").map(lambda f, fl=flag: fl in f).sum())
        rows.append(
            {
                "quality_flag": flag,
                "severity": "excluded_from_analysis" if flag in BLOCKING_FLAGS else "informational",
                "row_count": count,
                "pct_of_rows": round(count / total * 100, 2) if total else 0.0,
                "treatment": FLAG_DESCRIPTIONS[flag],
            }
        )
    return pd.DataFrame(rows)
