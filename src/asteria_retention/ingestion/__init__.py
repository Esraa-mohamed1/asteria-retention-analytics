"""Ingestion layer: resilient HTTP client, external API adapters, raw payload storage, and orchestration."""

from asteria_retention.ingestion.base import (
    Observation,
    RawPayload,
    IndicatorClient,
    ORIGIN_FIXTURE,
    ORIGIN_CACHE,
    ORIGIN_LIVE,
    utc_now_iso,
    sha256_of,
    canonical_json,
)
from asteria_retention.ingestion.eurostat import EurostatClient
from asteria_retention.ingestion.worldbank import WorldBankClient
from asteria_retention.ingestion.http import ResilientHttp
from asteria_retention.ingestion.store import RawStore
from asteria_retention.ingestion.service import IngestionService, IngestionResult, IndicatorOutcome

__all__ = [
    "Observation",
    "RawPayload",
    "IndicatorClient",
    "ORIGIN_FIXTURE",
    "ORIGIN_CACHE",
    "ORIGIN_LIVE",
    "utc_now_iso",
    "sha256_of",
    "canonical_json",
    "EurostatClient",
    "WorldBankClient",
    "ResilientHttp",
    "RawStore",
    "IngestionService",
    "IngestionResult",
    "IndicatorOutcome",
]
