"""Ingestion layer: resilient HTTP client, external API adapters, raw payload storage, and orchestration."""

from asteria_retention.ingestion.base import (
    ORIGIN_CACHE,
    ORIGIN_FIXTURE,
    ORIGIN_LIVE,
    IndicatorClient,
    Observation,
    RawPayload,
    canonical_json,
    sha256_of,
    utc_now_iso,
)
from asteria_retention.ingestion.eurostat import EurostatClient
from asteria_retention.ingestion.http import ResilientHttp
from asteria_retention.ingestion.service import (
    IndicatorOutcome,
    IngestionResult,
    IngestionService,
)
from asteria_retention.ingestion.store import RawStore
from asteria_retention.ingestion.worldbank import WorldBankClient

__all__ = [
    "ORIGIN_CACHE",
    "ORIGIN_FIXTURE",
    "ORIGIN_LIVE",
    "EurostatClient",
    "IndicatorClient",
    "IndicatorOutcome",
    "IngestionResult",
    "IngestionService",
    "Observation",
    "RawPayload",
    "RawStore",
    "ResilientHttp",
    "WorldBankClient",
    "canonical_json",
    "sha256_of",
    "utc_now_iso",
]
