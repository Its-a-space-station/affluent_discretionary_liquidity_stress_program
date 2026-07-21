"""ALFRED/FRED HTTP client. Read-only GETs to api.stlouisfed.org.

Security invariants (from Kalshi data/realtime.py:309-351 lessons):
- The API key travels in the query string, so request URLs are secrets.
  No exception, log line, or artifact may ever contain a URL or params.
  requests exceptions are re-wrapped by class name only.
- raise_for_status() is never used (its message embeds the full URL).

Request shape adapted from Kalshi FredFeed (data/realtime.py:1013-1053),
extended with ALFRED realtime_start/realtime_end and the vintagedates
endpoint (no as-of support existed anywhere to reuse).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import requests

BASE = "https://api.stlouisfed.org/fred"
FULL_REALTIME_START = "1776-07-04"  # ALFRED convention: full vintage history
FULL_REALTIME_END = "9999-12-31"
PAGE_LIMIT = 10000
MAX_RETRIES = 3
MIN_INTERVAL_S = 0.7  # politeness; rate limit is unpublished (handle 429s)


@dataclass(frozen=True)
class RawObservation:
    observation_date: str
    realtime_start: str
    realtime_end: str
    value_text: str


@dataclass(frozen=True)
class RequestStats:
    endpoint: str
    http_status: int | None
    requests_made: int
    rate_limited: int


class AlfredClientError(RuntimeError):
    """Raised on request failure. Message NEVER contains URLs/params/keys."""

    def __init__(self, message: str, stats: RequestStats) -> None:
        super().__init__(message)
        self.stats = stats


def parse_value(value_text: str) -> float | None:
    """FRED missing-value sentinel '.' (and empty) -> None."""
    text = value_text.strip()
    if text in {".", ""}:
        return None
    return float(text)


class AlfredClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._sleep = sleep_fn
        self._last_request_at = 0.0
        self._active_endpoint = ""
        self._last_http_status: int | None = None
        self._requests_made = 0
        self._rate_limited = 0

    # -- public API ---------------------------------------------------------

    def get_observations(
        self,
        series_id: str,
        realtime_start: str = FULL_REALTIME_START,
        realtime_end: str = FULL_REALTIME_END,
    ) -> list[RawObservation]:
        """All observation spans for a series across the realtime range."""
        self._begin_call("observations")
        rows: list[RawObservation] = []
        offset = 0
        while True:
            payload = self._get_json(
                "series/observations",
                {
                    "series_id": series_id,
                    "realtime_start": realtime_start,
                    "realtime_end": realtime_end,
                    "limit": PAGE_LIMIT,
                    "offset": offset,
                },
            )
            batch = payload.get("observations", [])
            rows.extend(
                RawObservation(
                    observation_date=o["date"],
                    realtime_start=o["realtime_start"],
                    realtime_end=o["realtime_end"],
                    value_text=o["value"],
                )
                for o in batch
            )
            if len(batch) < PAGE_LIMIT:
                return rows
            offset += PAGE_LIMIT

    def get_vintage_dates(self, series_id: str) -> list[str]:
        self._begin_call("vintagedates")
        dates: list[str] = []
        offset = 0
        while True:
            payload = self._get_json(
                "series/vintagedates",
                {"series_id": series_id, "limit": PAGE_LIMIT, "offset": offset},
            )
            batch = payload.get("vintage_dates", [])
            dates.extend(batch)
            if len(batch) < PAGE_LIMIT:
                return dates
            offset += PAGE_LIMIT

    # -- internals ----------------------------------------------------------

    @property
    def last_request_stats(self) -> RequestStats:
        return RequestStats(
            endpoint=self._active_endpoint,
            http_status=self._last_http_status,
            requests_made=self._requests_made,
            rate_limited=self._rate_limited,
        )

    def _begin_call(self, endpoint: str) -> None:
        self._active_endpoint = endpoint
        self._last_http_status = None
        self._requests_made = 0
        self._rate_limited = 0

    def _get_json(self, endpoint: str, params: dict[str, str | int]) -> dict:
        full_params: dict[str, str | int] = {
            "api_key": self._api_key, "file_type": "json", **params
        }
        url = f"{BASE}/{endpoint}"
        last_status: int | None = None
        last_exc_name: str | None = None
        for attempt in range(MAX_RETRIES):
            self._politeness_wait()
            self._requests_made += 1
            try:
                resp = self._session.get(url, params=full_params, timeout=60)
            except requests.RequestException as exc:  # message may embed URL
                # Timeouts/connection drops are retryable; never re-raise the
                # original (its message can embed the full URL incl. the key).
                last_exc_name = exc.__class__.__name__
                self._sleep(2.0 * (attempt + 1))
                continue
            last_status = resp.status_code
            self._last_http_status = resp.status_code
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    raise AlfredClientError(
                        f"FRED response not JSON: {endpoint} status=200",
                        self.last_request_stats,
                    ) from None
            if resp.status_code == 429:
                self._rate_limited += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                self._sleep(2.0 * (attempt + 1))
                continue
            break  # 4xx other than 429: not retryable
        detail = f"status={last_status}" if last_status else f"({last_exc_name})"
        raise AlfredClientError(
            f"FRED request failed: {endpoint} {detail} after {attempt + 1} attempt(s)",
            self.last_request_stats,
        )

    def _politeness_wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_INTERVAL_S:
            self._sleep(MIN_INTERVAL_S - elapsed)
        self._last_request_at = time.monotonic()
