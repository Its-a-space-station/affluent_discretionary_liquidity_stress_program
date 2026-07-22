from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from adls.alfred.client import RawObservation, RequestStats
from adls.cli import main
from adls.contracts import ValidationResult
from adls.reporting import ReportRunResult


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
        self.coverage_cutoff = ""

    def get_vintage_dates(
        self,
        series_id: str,
        realtime_end: str = "9999-12-31",
    ) -> list[str]:
        self.coverage_cutoff = realtime_end
        self.last_request_stats = RequestStats("vintagedates", 200, 2, 1)
        return ["2026-07-18", "2026-07-20"]

    def get_observations(
        self,
        series_id: str,
        realtime_start: str = "1776-07-04",
        realtime_end: str = "9999-12-31",
    ) -> list[RawObservation]:
        assert realtime_end == self.coverage_cutoff == "2026-07-22"
        self.last_request_stats = RequestStats("observations", 200, 1, 0)
        return [RawObservation("2026-06-01", "2026-07-20", "9999-12-31", "1.0")]


def test_fetch_uses_one_cutoff_and_audits_both_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    monkeypatch.setattr("adls.cli.Config", FakeConfig)
    monkeypatch.setattr("adls.alfred.cache.VintageCache", lambda path: cache)
    monkeypatch.setattr("adls.alfred.client.AlfredClient", FakeClient)
    monkeypatch.setattr("adls.alfred.cache._iso_now", lambda: "2026-07-22T12:00:00Z")

    assert main(["fetch", "--series", "RSFSDP"]) == 0
    assert cache.coverage == [("RSFSDP", "2026-07-22")]
    assert [summary.endpoint for summary in cache.summaries] == [
        "vintagedates",
        "observations",
    ]
    assert cache.summaries[0].rate_limited == 1
    assert all(summary.http_status == 200 for summary in cache.summaries)


def test_fetch_rejects_non_alfred_series(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["fetch", "--series", "UMICH_SCA_T2N_TOP"]) == 2
    assert "not an ALFRED series" in capsys.readouterr().err


def test_fetch_rejects_cutoff_older_than_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    cache.complete_vintage = "2026-07-20"

    class OlderVintageClient(FakeClient):
        def get_vintage_dates(
            self,
            series_id: str,
            realtime_end: str = "9999-12-31",
        ) -> list[str]:
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
    monkeypatch.setattr("adls.alfred.cache._iso_now", lambda: "2026-07-19T12:00:00Z")

    assert main(["fetch", "--series", "RSFSDP"]) == 1
    assert cache.vintage_upserts == 0
    assert cache.coverage == []
    assert cache.summaries[0].status == "error"
    assert "predates cache coverage" in cache.summaries[0].error_summary


def test_fetch_advances_coverage_when_latest_change_is_older(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    cache.complete_vintage = "2026-07-20"

    class UnchangedSeriesClient(FakeClient):
        def get_vintage_dates(
            self,
            series_id: str,
            realtime_end: str = "9999-12-31",
        ) -> list[str]:
            self.coverage_cutoff = realtime_end
            self.last_request_stats = RequestStats("vintagedates", 200, 1, 0)
            return ["2026-07-01"]

    monkeypatch.setattr("adls.cli.Config", FakeConfig)
    monkeypatch.setattr("adls.alfred.cache.VintageCache", lambda path: cache)
    monkeypatch.setattr("adls.alfred.client.AlfredClient", UnchangedSeriesClient)
    monkeypatch.setattr("adls.alfred.cache._iso_now", lambda: "2026-07-22T12:00:00Z")

    assert main(["fetch", "--series", "RSFSDP"]) == 0
    assert cache.coverage == [("RSFSDP", "2026-07-22")]


def test_fetch_rejects_vintage_after_explicit_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()

    class FutureVintageClient(FakeClient):
        def get_vintage_dates(
            self,
            series_id: str,
            realtime_end: str = "9999-12-31",
        ) -> list[str]:
            self.last_request_stats = RequestStats("vintagedates", 200, 1, 0)
            return ["2026-07-23"]

        def get_observations(
            self,
            series_id: str,
            realtime_start: str = "1776-07-04",
            realtime_end: str = "9999-12-31",
        ) -> list[RawObservation]:
            raise AssertionError("observations must not follow a future vintage")

    monkeypatch.setattr("adls.cli.Config", FakeConfig)
    monkeypatch.setattr("adls.alfred.cache.VintageCache", lambda path: cache)
    monkeypatch.setattr("adls.alfred.client.AlfredClient", FutureVintageClient)
    monkeypatch.setattr("adls.alfred.cache._iso_now", lambda: "2026-07-22T12:00:00Z")

    assert main(["fetch", "--series", "RSFSDP"]) == 1
    assert cache.coverage == []
    assert cache.summaries[0].status == "error"
    assert "exceeds fetch cutoff" in cache.summaries[0].error_summary


def test_series_option_requires_at_least_one_id() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["fetch", "--series"])
    assert exc_info.value.code == 2


def test_validate_reaches_archive_gate_after_owner_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ValidationConfig:
        db_path = tmp_path / "cache.sqlite"
        outputs_dir = tmp_path / "outputs"

        def ensure_dirs(self) -> None:
            self.outputs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("adls.cli.Config", ValidationConfig)
    result = main(
        [
            "validate",
            "--archive",
            str(tmp_path / "missing.csv"),
            "--start-month",
            "2013-05",
            "--end-month",
            "2026-05",
        ]
    )

    assert result == 1
    stderr = capsys.readouterr().err
    assert "cannot read archive CSV" in stderr
    assert "owner approval is required" not in stderr


def test_report_cli_uses_local_defaults_and_explicit_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ReportingConfig:
        db_path = tmp_path / "data" / "adls.sqlite"
        canonical_dir = tmp_path / "canonical"
        outputs_dir = tmp_path / "outputs"

        def ensure_dirs(self) -> None:
            self.outputs_dir.mkdir(parents=True, exist_ok=True)

    captured: dict[str, Any] = {}

    def fake_run_weekly_report(**kwargs: Any) -> ReportRunResult:
        captured.update(kwargs)
        return ReportRunResult(b"assembly\n", b"artifact\n", "report\n", ValidationResult())

    monkeypatch.setattr("adls.cli.Config", ReportingConfig)
    monkeypatch.setattr("adls.reporting.run_weekly_report", fake_run_weekly_report)

    result = main(
        [
            "report",
            "--archive",
            str(tmp_path / "umich.csv"),
            "--assembly-date",
            "2026-07-17",
            "--generated-at",
            "2026-07-22T12:00:00Z",
        ]
    )

    assert result == 0
    assert captured["generated_at"] == "2026-07-22T12:00:00Z"
    assert captured["frozen_path"] == tmp_path / "canonical" / "frozen_sequence.jsonl"
    assert captured["assembly_artifact_path"].name == "weekly_assembly_2026-07-17.json"
    assert captured["report_artifact_path"].name == "weekly_report_2026-07-17.json"
    assert captured["markdown_path"].name == "weekly_report_2026-07-17.md"
    assert "weekly report markdown" in capsys.readouterr().out
