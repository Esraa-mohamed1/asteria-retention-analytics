"""Event schemas, required columns, and quality flags for workforce data."""

from __future__ import annotations

from typing import Final

REQUIRED_EVENT_COLUMNS: Final[tuple[str, ...]] = (
    "employee_id",
    "country_code",
    "business_unit",
    "job_family",
    "career_level",
    "employment_type",
    "hire_date",
    "termination_date",
    "termination_type",
    "regretted_exit",
    "source_system",
    "record_updated_at",
)

# Blocking flags exclude rows from analysis; informational flags retain rows.
BLOCKING_FLAGS: Final[tuple[str, ...]] = (
    "unknown_country_code",
    "missing_hire_date",
    "unparseable_hire_date",
    "unparseable_termination_date",
    "termination_before_hire",
    "duplicate_employee_id",
)

INFORMATIONAL_FLAGS: Final[tuple[str, ...]] = (
    "termination_missing_type",
    "nonstandard_career_level_kept_separate",
    "voluntary_exit_missing_regret_flag",
)

FLAG_DESCRIPTIONS: Final[dict[str, str]] = {
    "unknown_country_code": "Country code blank or not one of the six operating countries; excluded.",
    "missing_hire_date": "hire_date blank; cannot place the person in any cohort; excluded.",
    "unparseable_hire_date": "hire_date present but not a valid date; excluded.",
    "unparseable_termination_date": "termination_date present but not a valid date; excluded.",
    "termination_before_hire": "termination_date earlier than hire_date (impossible); excluded.",
    "duplicate_employee_id": "Repeat of an employee_id already seen; first occurrence kept, repeat excluded.",
    "termination_missing_type": "Exit recorded without a termination_type; kept (retention only needs the date).",
    "nonstandard_career_level_kept_separate": "'Sr Mgmt' style label kept as its own category, not merged, not counted as senior.",
    "voluntary_exit_missing_regret_flag": "Voluntary exit with blank regretted_exit; kept, counted as not regretted.",
}
