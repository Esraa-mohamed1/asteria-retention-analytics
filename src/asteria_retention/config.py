"""Central configuration: the single source of truth.

Nothing else in the codebase hardcodes a path, a country code, an indicator
id, an API dimension or a publication lag. Change behaviour here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# --- Filesystem layout -------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW = DATA_DIR / "raw"  # official assessment files, never edited
DATA_FIXTURES = DATA_DIR / "fixtures"  # offline replay payloads (synthetic values)
DATA_EXTERNAL_RAW = DATA_DIR / "external_raw"  # live snapshots kept as raw evidence
DATA_CURATED = DATA_DIR / "curated"  # generated outputs
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
EVIDENCE_DIR = PROJECT_ROOT / "docs" / "evidence"

EVENTS_CSV = DATA_RAW / "employee_lifecycle_events.csv"
OBJECTIVES_CSV = DATA_RAW / "retention_objectives.csv"
MANIFEST_JSON = DATA_RAW / "assessment_data_manifest.json"

# --- Dates -------------------------------------------------------------------

WORKFORCE_AS_OF = date(2025, 12, 31)
EXTERNAL_HISTORY_START_YEAR = 2019  # two years before the objectives take effect

# --- Countries ---------------------------------------------------------------


@dataclass(frozen=True)
class Country:
    iso2: str  # canonical code used everywhere in this project
    iso3: str  # World Bank uses ISO-3 in URLs
    name: str
    eurostat_geo: str  # Eurostat deviates from ISO-2 for Greece ("EL")


COUNTRIES: dict[str, Country] = {
    c.iso2: c
    for c in (
        Country("GR", "GRC", "Greece", "EL"),
        Country("RO", "ROU", "Romania", "RO"),
        Country("PL", "POL", "Poland", "PL"),
        Country("IT", "ITA", "Italy", "IT"),
        Country("IE", "IRL", "Ireland", "IE"),
        Country("BG", "BGR", "Bulgaria", "BG"),
    )
}
CANONICAL_COUNTRIES: list[str] = list(COUNTRIES)

# Dirty codes seen in the HR extract -> canonical ISO-2. Anything not listed
# (including blank) is flagged, never guessed.
COUNTRY_CODE_ALIASES: dict[str, str] = {
    **{iso2: iso2 for iso2 in COUNTRIES},
    "EL": "GR",  # Eurostat-style Greece
    "ROM": "RO",  # legacy non-ISO Romania
}

STANDARD_CAREER_LEVELS = frozenset({"Individual Contributor", "Manager", "Senior Leader"})

# --- External indicators -----------------------------------------------------

PROVIDER_EUROSTAT = "eurostat"
PROVIDER_WORLDBANK = "worldbank"


@dataclass(frozen=True)
class Indicator:
    indicator_id: str
    provider: str
    dataset: str  # Eurostat dataset code, or World Bank indicator code
    label: str
    lens: str
    frequency: str  # "M" monthly, "Q" quarterly, "A" annual
    unit: str
    publication_lag_days: int  # conservative assumption, see docs/source_register.md
    max_age_days: int  # older as-of values are treated as stale and excluded from analysis
    filters: Mapping[str, str] = field(default_factory=dict)  # sent to the API
    prefer: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # chosen client-side
    docs_url: str = ""


INDICATORS: tuple[Indicator, ...] = (
    Indicator(
        indicator_id="unemployment_rate",
        provider=PROVIDER_EUROSTAT,
        dataset="une_rt_m",
        label="Unemployment rate, seasonally adjusted (% of active population)",
        lens="labour supply",
        frequency="M",
        unit="% of active population",
        publication_lag_days=45,
        max_age_days=120,
        filters={"s_adj": "SA", "age": "TOTAL", "sex": "T", "unit": "PC_ACT"},
        docs_url="https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table",
    ),
    Indicator(
        indicator_id="job_vacancy_rate",
        provider=PROVIDER_EUROSTAT,
        dataset="jvs_q_nace2",
        label="Job vacancy rate (% of posts), all activities",
        lens="labour demand",
        frequency="Q",
        unit="% of posts",
        publication_lag_days=90,
        max_age_days=200,
        # Uses prefer for indic_em to handle both current Eurostat (JVR) and fixture fallback (JOBRATE).
        filters={},
        prefer={
            "indic_em": ("JVR", "JOBRATE"),  # JVR = current code; JOBRATE = old (fixtures)
            "s_adj": ("NSA", "SA"),
            "nace_r2": ("B-S", "A-S"),
            "sizeclas": ("TOTAL", "GE10"),
        },
        docs_url="https://ec.europa.eu/eurostat/databrowser/view/jvs_q_nace2/default/table",
    ),
    Indicator(
        indicator_id="hicp_inflation",
        provider=PROVIDER_EUROSTAT,
        dataset="prc_hicp_manr",
        label="HICP inflation, annual rate of change (%), all items",
        lens="cost-of-living pressure",
        frequency="M",
        unit="% year on year",
        publication_lag_days=30,
        max_age_days=120,
        filters={"unit": "RCH_A", "coicop": "CP00"},
        docs_url="https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_manr/default/table",
    ),
    Indicator(
        indicator_id="gdp_growth",
        provider=PROVIDER_WORLDBANK,
        dataset="NY.GDP.MKTP.KD.ZG",
        label="GDP growth (annual %)",
        lens="economic cycle",
        frequency="A",
        unit="% annual",
        publication_lag_days=300,
        max_age_days=760,
        docs_url="https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG",
    ),
    Indicator(
        indicator_id="labour_force_participation",
        provider=PROVIDER_WORLDBANK,
        dataset="SL.TLF.CACT.ZS",
        label="Labour force participation rate, total (% of population aged 15+, modelled ILO)",
        lens="labour supply",
        frequency="A",
        unit="% of population 15+",
        publication_lag_days=365,
        max_age_days=760,
        docs_url="https://data.worldbank.org/indicator/SL.TLF.CACT.ZS",
    ),
)
INDICATORS_BY_ID: dict[str, Indicator] = {i.indicator_id: i for i in INDICATORS}

# --- Analysis parameters -----------------------------------------------------

MIN_PAIRS_FOR_CORRELATION = 8
SMALL_SAMPLE_THRESHOLD = 30  # cohorts smaller than this are flagged "directional only"

SOURCE_ATTRIBUTION: dict[str, dict[str, str]] = {
    PROVIDER_EUROSTAT: {
        "name": "Eurostat (European Commission)",
        "url": "https://ec.europa.eu/eurostat",
        "licence": "Free reuse with acknowledgement of the source (EC reuse policy). "
        "Verify current terms at https://ec.europa.eu/eurostat/about-us/policies/copyright",
    },
    PROVIDER_WORLDBANK: {
        "name": "World Bank Open Data",
        "url": "https://data.worldbank.org",
        "licence": "Creative Commons Attribution 4.0 (CC BY 4.0) for most datasets. "
        "Verify at https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets",
    },
}
