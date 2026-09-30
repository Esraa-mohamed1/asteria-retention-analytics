"""World Bank Indicators API adapter (v2, JSON).

Response shape: `[meta, rows]` where `meta` carries paging info and `rows` is a
list of {indicator, country, countryiso3code, date, value, obs_status, ...}.
Errors come back as HTTP 200 with `[{"message": [...]}]`, so we check for that.
World Bank series here are annual; the period is the calendar year.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from asteria_retention.config import COUNTRIES, WORKFORCE_AS_OF, Indicator
from asteria_retention.errors import ContractViolation, SourceFetchError
from asteria_retention.ingestion.base import (
    ORIGIN_LIVE,
    Observation,
    RawPayload,
    utc_now_iso,
)
from asteria_retention.ingestion.eurostat import (
    EXTERNAL_HISTORY_START_YEAR,
    PERIOD_PATTERNS,
)
from asteria_retention.ingestion.http import ResilientHttp

WORLDBANK_BASE_URL = "https://api.worldbank.org/v2"
PER_PAGE = 1000
MAX_PAGES = 10
_ISO3_TO_ISO2 = {c.iso3: c.iso2 for c in COUNTRIES.values()}


def _split(body: Any, indicator_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(body, list) or not body:
        raise ContractViolation(f"{indicator_id}: World Bank response is not a non-empty list")
    head = body[0]
    if isinstance(head, dict) and "message" in head:
        raise ContractViolation(f"{indicator_id}: World Bank API error: {head['message']}")
    if len(body) < 2 or not isinstance(head, dict):
        raise ContractViolation(f"{indicator_id}: World Bank response has no data section")
    rows = body[1]
    if rows is None:
        raise ContractViolation(f"{indicator_id}: World Bank returned no data rows")
    if not isinstance(rows, list):
        raise ContractViolation(f"{indicator_id}: World Bank data section is not a list")
    return head, rows


class WorldBankClient:
    provider = "worldbank"

    def __init__(
        self, http: ResilientHttp | None = None, clock: Callable[[], str] = utc_now_iso
    ) -> None:
        self._http = http or ResilientHttp()
        self._clock = clock

    @staticmethod
    def build_request(indicator: Indicator, countries: Sequence[str]) -> tuple[str, dict[str, Any]]:
        iso3 = ";".join(COUNTRIES[c].iso3 for c in countries)
        url = f"{WORLDBANK_BASE_URL}/country/{iso3}/indicator/{indicator.dataset}"
        params: dict[str, Any] = {
            "format": "json",
            "per_page": PER_PAGE,
            "date": f"{EXTERNAL_HISTORY_START_YEAR}:{WORKFORCE_AS_OF.year}",
        }
        return url, params

    def fetch(self, indicator: Indicator, countries: Sequence[str]) -> RawPayload:
        url, params = self.build_request(indicator, countries)
        body, final_url = self._http.get_json(url, params, self.provider, indicator.indicator_id)
        try:
            meta, rows = _split(body, indicator.indicator_id)
        except ContractViolation as exc:
            raise SourceFetchError(self.provider, indicator.indicator_id, str(exc)) from exc

        pages = int(meta.get("pages", 1) or 1)
        for page in range(2, min(pages, MAX_PAGES) + 1):
            more, _ = self._http.get_json(
                url, {**params, "page": page}, self.provider, indicator.indicator_id
            )
            try:
                _, extra_rows = _split(more, indicator.indicator_id)
            except ContractViolation as exc:
                raise SourceFetchError(self.provider, indicator.indicator_id, str(exc)) from exc
            rows = [*rows, *extra_rows]
        merged = [{**meta, "pages": 1, "merged_pages": pages}, rows]
        return RawPayload.create(
            self.provider, indicator.indicator_id, final_url, params, self._clock(), merged, ORIGIN_LIVE
        )

    def parse(self, indicator: Indicator, payload: RawPayload) -> list[Observation]:
        _, rows = _split(payload.body, indicator.indicator_id)
        observations: list[Observation] = []
        for row in rows:
            try:
                iso2 = _ISO3_TO_ISO2.get(str(row.get("countryiso3code", "")))
                period = str(row["date"])
                value = row.get("value")
            except (KeyError, AttributeError) as exc:
                raise ContractViolation(
                    f"{indicator.indicator_id}: malformed World Bank row {row!r}"
                ) from exc
            if iso2 is None or value is None:
                continue  # other country, or year not yet published
            if not PERIOD_PATTERNS["A"].match(period):
                raise ContractViolation(f"{indicator.indicator_id}: bad World Bank date '{period}'")
            observations.append(
                Observation(
                    provider=self.provider,
                    indicator_id=indicator.indicator_id,
                    geo=iso2,
                    period=period,
                    frequency="A",
                    value=float(value),
                    unit=indicator.unit,
                    obs_status=str(row.get("obs_status") or ""),
                    source_url=payload.url,
                    retrieved_at=payload.retrieved_at,
                    payload_sha256=payload.sha256,
                    data_origin=payload.origin,
                )
            )
        if not observations:
            raise ContractViolation(f"{indicator.indicator_id}: no usable World Bank observations")
        return observations
