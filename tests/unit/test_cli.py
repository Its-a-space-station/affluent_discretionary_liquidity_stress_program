from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from adls.alfred.client import RawObservation, RequestStats
from adls.cli import main


class FakeConfig:
    fred_api_key = "fake-key"
    db_path = Path("unused.sqlite")

    def validate_for_fetch(self) -> None:
        pass

    def ensure_dirs(self) -> None:
        pass


class FakeCache:
    def __init__(self) -> None:
        self.summaries: list[Any] = []
        self.coverage: list[tuple[str, str]] = []
        self.complete_vintage: str | None = None
        self.vintage_upserts = 0

    def initialize(self) -> None:
        pass

    def upsert_vintage_dates(self, series_id: str, vintages: list[str]) -> int:
        self.vintage_upserts += 1
        return len(vintages)

    def upsert_spans(self, spans: Any) -> int:
        return len(list(spans))

    def mark_backfilled(self, series_id: str, through_vintage: str) -> None:
        self.coverage.append((series_id, through_vintage))
        self.complete_vintage = through_vintage

    def complete_through_vintage(self, series_id: str) -> str | None:
        return self.complete_vintage

    def record_fetch_run(self, summary: Any, started_at: str) -> None:
        self.summaries.append(summary)


class FakeClient:
    def __init__(self, api_key: str) -> None:
        self.last_request_stats = RequestStats("", None, 0, 0)

    def get_vintage_dates(self, series_id: str) -> list[str]:
        self.last_request_stats = RequestStats("vintagedates", 200, 2, 1)
        return ["2026-07-18", "2026-07-20"]

    def get_observations(
        self,
        series_id: str,
        realtime_start: str = "1776-07-04",
        realtime_end: str = "9999-12-31",
    ) -> list[RawObservation]:
        assert realtime_end == "2026-07-20"
        self.last_request_stats = RequestStats("observations", 200, 1, 0)
        return [RawObservation("2026-06-01", "2026-07-20", "9999-12-31", "1.0")]


def test_fetch_uses_one_cutoff_and_audits_both_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    monkeypatch.setattr("adls.cli.Config", FakeConfig)
    monkeypatch.setattr("adls.alfred.cache.VintageCache", lambda path: cache)
    monkeypatch.setattr("adls.alfred.client.AlfredClient", FakeClient)

    assert main(["fetch", "--series", "RSFSDP"]) == 0
    assert cache.coverage == [("RSFSDP", "2026-07-20")]
    assert [summary.endpoint for summary in cache.summaries] == [
        "vintagedates",
        "observations",
    ]
    assert cache.summaries[0].rate_limited == 1
    assert all(summary.http_status == 200 for summary in cache.summaries)


def test_fetch_rejects_non_alfred_series(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["fetch", "--series", "UMICH_SCA_T2N_TOP"]) == 2
    assert "not an ALFRED series" in capsys.readouterr().err


def test_fetch_rejects_vintage_list_older_than_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    cache.complete_vintage = "2026-07-20"

    class OlderVintageClient(FakeClient):
        def get_vintage_dates(self, series_id: str) -> list[str]:
            self.last_request_stats = RequestStats("vintagedates", 200, 1, 0)
            return ["2026-07-01"]

        def get_observations(
            self,
            series_id: str,
            realtime_start: str = "1776-07-04",
            realtime_end: str = "9999-12-31",
        ) -> list[RawObservation]:
            raise AssertionError("observations must not be fetched after coverage regresses")

    monkeypatch.setattr("adls.cli.Config", FakeConfig)
    monkeypatch.setattr("adls.alfred.cache.VintageCache", lambda path: cache)
    monkeypatch.setattr("adls.alfred.client.AlfredClient", OlderVintageClient)

    assert main(["fetch", "--series", "RSFSDP"]) == 1
    assert cache.vintage_upserts == 0
    assert cache.coverage == []
    assert cache.summaries[0].status == "error"
    assert "predates cache coverage" in cache.summaries[0].error_summary


def test_series_option_requires_at_least_one_id() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["fetch", "--series"])
    assert exc_info.value.code == 2
