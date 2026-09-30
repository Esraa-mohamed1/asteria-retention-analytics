"""Eurostat adapter (JSON-stat 2.0 over the public dissemination API).

This is the ONLY module that knows Eurostat's URL shape, its JSON-stat layout
and its quirks (Greece is "EL").

Robustness against dataset drift:
- `Indicator.filters` are sent to the API to narrow the cube.
- `Indicator.prefer` lists acceptable categories per dimension; the client picks
  the first one present. This survives Eurostat renaming e.g. size class
  "TOTAL" -> "GE10" without silently mixing two measures.
- After selection every non geo/time dimension must be single-valued, otherwise
  we raise a ContractViolation naming the dimension and its categories, so the
  fix is a one-line config change, not a silent wrong number.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from asteria_retention.config import COUNTRIES, EXTERNAL_HISTORY_START_YEAR, Indicator
from asteria_retention.errors import ContractViolation, SourceFetchError
from asteria_retention.ingestion.base import (
    ORIGIN_LIVE,
    Observation,
    RawPayload,
    utc_now_iso,
)
from asteria_retention.ingestion.http import ResilientHttp

EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

PERIOD_PATTERNS = {
    "M": re.compile(r"^\d{4}-\d{2}$"),
    "Q": re.compile(r"^\d{4}-Q[1-4]$"),
    "A": re.compile(r"^\d{4}$"),
}
_SINCE = {
    "M": f"{EXTERNAL_HISTORY_START_YEAR}-01",
    "Q": f"{EXTERNAL_HISTORY_START_YEAR}-Q1",
    "A": str(EXTERNAL_HISTORY_START_YEAR),
}
_EUROSTAT_GEO_TO_ISO = {c.eurostat_geo: c.iso2 for c in COUNTRIES.values()}


def _categories(dimension: dict[str, Any]) -> list[str]:
    """JSON-stat allows category.index as an object {code: position} or a list."""
    index = dimension["category"]["index"]
    if isinstance(index, dict):
        return [code for code, _ in sorted(index.items(), key=lambda item: item[1])]
    return [str(code) for code in index]


def _unflatten(flat_index: int, sizes: Sequence[int]) -> list[int]:
    """Invert JSON-stat's row-major flattening of a multi-dimensional array."""
    coords = [0] * len(sizes)
    remainder = flat_index
    for dim in reversed(range(len(sizes))):
        coords[dim] = remainder % sizes[dim]
        remainder //= sizes[dim]
    return coords


class EurostatClient:
    provider = "eurostat"

    def __init__(
        self, http: ResilientHttp | None = None, clock: Callable[[], str] = utc_now_iso
    ) -> None:
        self._http = http or ResilientHttp()
        self._clock = clock

    # -- request -----------------------------------------------------------

    @staticmethod
    def build_request(indicator: Indicator, countries: Sequence[str]) -> tuple[str, dict[str, Any]]:
        url = f"{EUROSTAT_BASE_URL}/{indicator.dataset}"
        params: dict[str, Any] = {
            "format": "JSON",
            "lang": "EN",
            "geo": [COUNTRIES[c].eurostat_geo for c in countries],
            "sinceTimePeriod": _SINCE[indicator.frequency],
            **indicator.filters,
        }
        return url, params

    def fetch(self, indicator: Indicator, countries: Sequence[str]) -> RawPayload:
        url, params = self.build_request(indicator, countries)
        body, final_url = self._http.get_json(url, params, self.provider, indicator.indicator_id)
        if isinstance(body, dict) and "error" in body:
            raise SourceFetchError(
                self.provider, indicator.indicator_id, f"Eurostat returned an error: {body['error']}"
            )
        return RawPayload.create(
            self.provider, indicator.indicator_id, final_url, params, self._clock(), body, ORIGIN_LIVE
        )

    # -- parsing -----------------------------------------------------------

    def parse(self, indicator: Indicator, payload: RawPayload) -> list[Observation]:
        body = payload.body
        try:
            ids = [str(i) for i in body["id"]]
            sizes = [int(s) for s in body["size"]]
            dimensions = body["dimension"]
            cats = {dim: _categories(dimensions[dim]) for dim in ids}
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractViolation(
                f"{indicator.indicator_id}: unexpected Eurostat response shape ({exc!r})"
            ) from exc
        if "geo" not in ids or "time" not in ids:
            raise ContractViolation(f"{indicator.indicator_id}: response lacks geo/time dimensions")

        chosen = self._choose_fixed_dimensions(indicator, ids, cats)
        geo_pos, time_pos = ids.index("geo"), ids.index("time")
        chosen_positions = {ids.index(dim): pos for dim, pos in chosen.items()}

        values = body.get("value", {})
        if isinstance(values, list):  # dense form
            values = {str(i): v for i, v in enumerate(values)}
        statuses = body.get("status", {}) or {}
        if isinstance(statuses, list):
            statuses = {str(i): s for i, s in enumerate(statuses)}

        observations: list[Observation] = []
        for key, raw_value in values.items():
            if raw_value is None:
                continue
            coords = _unflatten(int(key), sizes)
            if any(coords[dim_pos] != pos for dim_pos, pos in chosen_positions.items()):
                continue
            iso = _EUROSTAT_GEO_TO_ISO.get(cats["geo"][coords[geo_pos]])
            if iso is None:
                continue  # aggregate or country we do not operate in
            period = cats["time"][coords[time_pos]]
            if not PERIOD_PATTERNS[indicator.frequency].match(period):
                raise ContractViolation(
                    f"{indicator.indicator_id}: period '{period}' does not match "
                    f"expected frequency '{indicator.frequency}'"
                )
            observations.append(
                Observation(
                    provider=self.provider,
                    indicator_id=indicator.indicator_id,
                    geo=iso,
                    period=period,
                    frequency=indicator.frequency,
                    value=float(raw_value),
                    unit=indicator.unit,
                    obs_status=str(statuses.get(key, "") or ""),
                    source_url=payload.url,
                    retrieved_at=payload.retrieved_at,
                    payload_sha256=payload.sha256,
                    data_origin=payload.origin,
                )
            )
        if not observations:
            raise ContractViolation(
                f"{indicator.indicator_id}: no observations for our countries after applying "
                f"filters {dict(indicator.filters)} and preferences {dict(indicator.prefer)}"
            )
        return observations

    @staticmethod
    def _choose_fixed_dimensions(
        indicator: Indicator, ids: list[str], cats: dict[str, list[str]]
    ) -> dict[str, int]:
        chosen: dict[str, int] = {}
        for dim in ids:
            if dim in ("geo", "time"):
                continue
            codes = cats[dim]
            if len(codes) == 1:
                chosen[dim] = 0
                continue
            for candidate in indicator.prefer.get(dim, ()):
                if candidate in codes:
                    chosen[dim] = codes.index(candidate)
                    break
            else:
                shown = ", ".join(codes[:8]) + ("..." if len(codes) > 8 else "")
                raise ContractViolation(
                    f"{indicator.indicator_id}: Eurostat's '{dim}' dimension now has "
                    f"{len(codes)} categories ({shown}) but only 1 was expected. "
                    f"The dataset schema likely changed since this pipeline was configured. "
                    f"Fix: add '{dim}' to Indicator.filters or Indicator.prefer in config.py "
                    f"to select the correct category. See docs/source_register.md for guidance."
                )
        return chosen
