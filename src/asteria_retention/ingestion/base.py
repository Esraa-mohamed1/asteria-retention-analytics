"""Provider-neutral contracts. A new data source = one new class implementing
`IndicatorClient`; nothing downstream changes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from asteria_retention.config import Indicator

ORIGIN_LIVE = "live"
ORIGIN_CACHE = "cache"
ORIGIN_FIXTURE = "fixture_synthetic"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(body: Any) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_of(body: Any) -> str:
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RawPayload:
    """A source response exactly as received, plus how and when we got it."""

    provider: str
    indicator_id: str
    url: str
    params: dict[str, Any]
    retrieved_at: str
    body: Any
    origin: str
    sha256: str = field(default="")

    @classmethod
    def create(
        cls,
        provider: str,
        indicator_id: str,
        url: str,
        params: dict[str, Any],
        retrieved_at: str,
        body: Any,
        origin: str,
    ) -> RawPayload:
        return cls(provider, indicator_id, url, params, retrieved_at, body, origin, sha256_of(body))


@dataclass(frozen=True)
class Observation:
    """One published reading, in the source's own frequency and period semantics."""

    provider: str
    indicator_id: str
    geo: str  # canonical ISO-2
    period: str  # "2023-04", "2023-Q2" or "2023"
    frequency: str
    value: float
    unit: str
    obs_status: str  # provider flag, e.g. "p" provisional, "b" break; "" if none
    source_url: str
    retrieved_at: str
    payload_sha256: str
    data_origin: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class IndicatorClient(Protocol):
    provider: str

    def fetch(self, indicator: Indicator, countries: Sequence[str]) -> RawPayload:
        """Call the source. Raises SourceFetchError, never a raw requests error."""
        ...

    def parse(self, indicator: Indicator, payload: RawPayload) -> list[Observation]:
        """Decode a payload. Raises ContractViolation on any unexpected shape."""
        ...
