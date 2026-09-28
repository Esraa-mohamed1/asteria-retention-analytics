"""Ingestion orchestration.

Source modes:
  auto      try live; if that fails fall back to the newest cached snapshot
            (marked "cache" with its age). Synthetic fixtures are NEVER used
            implicitly.
  live      live only.
  cache     newest stored snapshot only.
  fixtures  offline replay payloads (synthetic values), for review and CI.

One indicator failing never stops the others; each outcome is reported.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from asteria_retention.config import Indicator
from asteria_retention.errors import AsteriaError, ContractViolation
from asteria_retention.ingestion.base import (
    ORIGIN_CACHE,
    IndicatorClient,
    Observation,
    RawPayload,
)
from asteria_retention.ingestion.store import RawStore

logger = logging.getLogger(__name__)

SOURCES = ("auto", "live", "cache", "fixtures")


@dataclass
class IndicatorOutcome:
    indicator_id: str
    provider: str
    status: str  # "ok" | "failed"
    origin: str = ""
    n_observations: int = 0
    retrieved_at: str = ""
    snapshot_age_days: int | None = None
    error: str = ""
    note: str = ""


@dataclass
class IngestionResult:
    observations: list[Observation] = field(default_factory=list)
    outcomes: list[IndicatorOutcome] = field(default_factory=list)

    @property
    def failed(self) -> list[IndicatorOutcome]:
        return [o for o in self.outcomes if o.status != "ok"]

    @property
    def degraded(self) -> bool:
        return bool(self.failed) or any(o.origin == ORIGIN_CACHE for o in self.outcomes)


class IngestionService:
    def __init__(
        self,
        clients: Mapping[str, IndicatorClient],
        live_store: RawStore,
        fixture_store: RawStore,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._clients = clients
        self._live_store = live_store
        self._fixture_store = fixture_store
        self._today = today

    def ingest(
        self, indicators: Sequence[Indicator], countries: Sequence[str], source: str
    ) -> IngestionResult:
        if source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}, got '{source}'")
        result = IngestionResult()
        for indicator in indicators:
            outcome = IndicatorOutcome(indicator.indicator_id, indicator.provider, "failed")
            try:
                payload, note = self._payload(indicator, countries, source)
                client = self._clients[indicator.provider]
                observations = client.parse(indicator, payload)
            except (AsteriaError, KeyError) as exc:
                outcome.error = str(exc)
                logger.error("indicator %s FAILED: %s", indicator.indicator_id, exc)
            else:
                outcome.status = "ok"
                outcome.origin = payload.origin
                outcome.n_observations = len(observations)
                outcome.retrieved_at = payload.retrieved_at
                outcome.note = note
                outcome.snapshot_age_days = (
                    self._today() - datetime.fromisoformat(payload.retrieved_at.rstrip("Z")).date()
                ).days
                result.observations.extend(observations)
                logger.info(
                    "indicator %s ok: %d observations (%s)",
                    indicator.indicator_id,
                    len(observations),
                    payload.origin,
                )
            result.outcomes.append(outcome)
        return result

    def _payload(
        self, indicator: Indicator, countries: Sequence[str], source: str
    ) -> tuple[RawPayload, str]:
        pid, iid = indicator.provider, indicator.indicator_id
        if source == "fixtures":
            return self._require(self._fixture_store.latest(pid, iid), "fixture", indicator), ""
        if source == "cache":
            return self._require(self._live_store.latest(pid, iid), "cached snapshot", indicator), ""
        client = self._clients[pid]
        try:
            payload = client.fetch(indicator, countries)
        except AsteriaError as exc:
            if source == "live":
                raise
            cached = self._live_store.latest(pid, iid, origin_override=ORIGIN_CACHE)
            if cached is None:
                raise
            logger.warning("live fetch failed for %s (%s); using cached snapshot", iid, exc)
            return cached, f"live fetch failed, used cache: {exc}"
        self._live_store.save(payload)
        return payload, ""

    @staticmethod
    def _require(payload: RawPayload | None, what: str, indicator: Indicator) -> RawPayload:
        if payload is None:
            raise ContractViolation(f"no {what} available for {indicator.indicator_id}")
        return payload
