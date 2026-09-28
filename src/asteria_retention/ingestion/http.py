"""Resilient HTTP for source APIs.

- bounded retries with backoff for timeouts, connection errors, 429 and 5xx
- honours `Retry-After` (capped)
- 4xx (other than 429) fails immediately: retrying a bad request is pointless
- every failure becomes a SourceFetchError that says what failed and why
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests

from asteria_retention.errors import SourceFetchError

logger = logging.getLogger(__name__)

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_SLEEP_SECONDS = 30.0


class ResilientHttp:
    def __init__(
        self,
        session: requests.Session | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        timeout: tuple[float, float] = (5.0, 30.0),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", "asteria-retention/1.0 (assessment)")
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._timeout = timeout
        self._sleep = sleep

    def get_json(
        self, url: str, params: dict[str, Any], provider: str, indicator_id: str
    ) -> tuple[Any, str]:
        """GET and decode JSON. Returns (body, final_url)."""
        last_reason = "unknown error"
        for attempt in range(1, self._max_retries + 1):
            delay = self._backoff * attempt
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_reason = f"network error: {type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    try:
                        return response.json(), response.url
                    except ValueError as exc:
                        raise SourceFetchError(
                            provider, indicator_id, f"response was not valid JSON: {exc}"
                        ) from exc
                excerpt = response.text[:300].replace("\n", " ")
                last_reason = f"HTTP {response.status_code}: {excerpt}"
                if response.status_code not in RETRY_STATUS:
                    raise SourceFetchError(provider, indicator_id, last_reason)
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = float(retry_after)
            logger.warning(
                "%s/%s attempt %d/%d failed: %s",
                provider,
                indicator_id,
                attempt,
                self._max_retries,
                last_reason,
            )
            if attempt < self._max_retries:
                self._sleep(min(delay, MAX_SLEEP_SECONDS))
        raise SourceFetchError(
            provider, indicator_id, f"gave up after {self._max_retries} attempts: {last_reason}"
        )
