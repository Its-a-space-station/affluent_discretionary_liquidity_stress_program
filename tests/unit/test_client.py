from __future__ import annotations

from typing import Any

import pytest

from adls.alfred.client import AlfredClient, AlfredClientError, parse_value


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Scripted transport; records nothing sensitive, hits no network."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls = 0
        self.safe_params: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls += 1
        self.safe_params.append({k: v for k, v in params.items() if k != "api_key"})
        return self._responses.pop(0)


def _client(responses: list[FakeResponse]) -> AlfredClient:
    return AlfredClient(
        "fake-key-abc", session=FakeSession(responses), sleep_fn=lambda s: None
    )


def test_parse_value_sentinel() -> None:
    assert parse_value(".") is None
    assert parse_value("") is None
    assert parse_value(" 42.5 ") == 42.5


def test_observations_single_page() -> None:
    payload = {"observations": [
        {"date": "2013-04-01", "realtime_start": "2013-05-13",
         "realtime_end": "9999-12-31", "value": "100.0"},
    ]}
    client = _client([FakeResponse(200, payload)])
    rows = client.get_observations("RSFSDP", realtime_end="2026-07-20")
    assert len(rows) == 1
    assert rows[0].realtime_start == "2013-05-13"
    assert client.last_request_stats.endpoint == "observations"
    assert client.last_request_stats.http_status == 200
    assert client.last_request_stats.requests_made == 1
    assert client._session.safe_params[-1]["realtime_end"] == "2026-07-20"


def test_429_backoff_then_success() -> None:
    ok = FakeResponse(200, {"observations": []})
    client = _client([FakeResponse(429), FakeResponse(429), ok])
    assert client.get_observations("RSFSDP") == []
    assert client.last_request_stats.rate_limited == 2
    assert client.last_request_stats.requests_made == 3
    assert client.last_request_stats.http_status == 200


def test_errors_never_contain_urls_or_key() -> None:
    client = _client([FakeResponse(403), ])
    with pytest.raises(AlfredClientError) as exc_info:
        client.get_observations("RSFSDP")
    message = str(exc_info.value)
    assert "http" not in message.lower()
    assert "api_key" not in message
    assert "fake-key-abc" not in message
    assert "status=403" in message
    assert exc_info.value.stats.endpoint == "observations"
    assert exc_info.value.stats.http_status == 403


def test_exhausted_retries_raise_urlfree() -> None:
    client = _client([FakeResponse(500), FakeResponse(500), FakeResponse(500)])
    with pytest.raises(AlfredClientError) as exc_info:
        client.get_vintage_dates("RSFSDP")
    assert "http" not in str(exc_info.value).lower()
    assert exc_info.value.stats.endpoint == "vintagedates"
    assert exc_info.value.stats.requests_made == 3


class TimeoutThenOkSession:
    """First call raises a network timeout; second succeeds."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls = 0

    def get(self, url: str, params: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls += 1
        if self.calls == 1:
            import requests

            raise requests.ReadTimeout("secret-url-would-be-here")
        return FakeResponse(200, self._payload)


def test_network_timeout_retries_then_succeeds() -> None:
    session = TimeoutThenOkSession({"observations": []})
    client = AlfredClient("fake-key-abc", session=session, sleep_fn=lambda s: None)
    assert client.get_observations("RSFHFS") == []
    assert session.calls == 2


def test_all_timeouts_raise_urlfree() -> None:
    class AlwaysTimeout:
        def get(self, url: str, params: dict[str, Any], timeout: int) -> FakeResponse:
            import requests

            raise requests.ConnectTimeout("https://secret-url-with-key")

    client = AlfredClient("fake-key-abc", session=AlwaysTimeout(), sleep_fn=lambda s: None)
    with pytest.raises(AlfredClientError) as exc_info:
        client.get_observations("RSFHFS")
    message = str(exc_info.value)
    assert "ConnectTimeout" in message
    assert "secret-url" not in message
    assert "http" not in message.lower()
