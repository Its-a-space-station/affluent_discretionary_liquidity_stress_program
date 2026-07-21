from __future__ import annotations

from pathlib import Path

import pytest

from adls.alfred.cache import VintageCache, VintageCoverageError
from adls.contracts import FetchSummary, ObservationSpan


def _span(value: str = "1.0", rt_start: str = "2013-05-13",
          rt_end: str = "9999-12-31") -> ObservationSpan:
    return ObservationSpan(
        series_id="RSFSDP", observation_date="2013-04-01",
        realtime_start=rt_start, realtime_end=rt_end,
        value_text=value, source="alfred",
    )


def _cache(tmp_path: Path) -> VintageCache:
    cache = VintageCache(tmp_path / "test.sqlite")
    cache.initialize()
    return cache


def test_initialize_idempotent(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    cache.initialize()  # second call must not raise or clobber
    cache.upsert_spans([_span()])
    cache.mark_backfilled("RSFSDP", "2013-05-13")
    cache.initialize()
    assert cache.series_history_at_vintage("RSFSDP", "2013-05-13") == [
        ("2013-04-01", "1.0")
    ]


def test_upsert_preserves_first_fetched_at(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    cache.upsert_spans([_span("1.0")])
    cache.mark_backfilled("RSFSDP", "2013-07-01")
    first = cache.first_fetched_at("RSFSDP", "2013-04-01", "2013-05-13")
    cache.upsert_spans([_span("1.0", rt_end="2013-06-12")])  # span closed by revision
    assert cache.first_fetched_at("RSFSDP", "2013-04-01", "2013-05-13") == first
    # updated realtime_end visible: vintage after close no longer matches
    assert cache.series_history_at_vintage("RSFSDP", "2013-07-01") == []


def test_vintage_span_lookup(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    cache.upsert_spans([
        _span("1.0", rt_start="2013-05-13", rt_end="2013-06-12"),
        _span("1.1", rt_start="2013-06-13", rt_end="9999-12-31"),
    ])
    cache.mark_backfilled("RSFSDP", "2026-01-01")
    assert cache.series_history_at_vintage("RSFSDP", "2013-05-20") == [
        ("2013-04-01", "1.0")
    ]
    assert cache.series_history_at_vintage("RSFSDP", "2026-01-01") == [
        ("2013-04-01", "1.1")
    ]
    # PIT boundary: vintage before first release sees nothing
    assert cache.series_history_at_vintage("RSFSDP", "2013-05-12") == []


def test_vintage_lookup_requires_declared_coverage(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    cache.upsert_spans([_span()])

    with pytest.raises(VintageCoverageError, match="no declared coverage"):
        cache.series_history_at_vintage("RSFSDP", "2013-05-13")

    cache.mark_backfilled("RSFSDP", "2013-06-30")
    assert cache.complete_through_vintage("RSFSDP") == "2013-06-30"
    assert cache.series_history_at_vintage("RSFSDP", "2013-06-30") == [
        ("2013-04-01", "1.0")
    ]
    with pytest.raises(VintageCoverageError, match="exceeds complete coverage"):
        cache.series_history_at_vintage("RSFSDP", "2013-07-01")


def test_coverage_marker_never_regresses(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    cache.mark_backfilled("RSFSDP", "2026-07-20")
    cache.mark_backfilled("RSFSDP", "2026-07-01")
    assert cache.complete_through_vintage("RSFSDP") == "2026-07-20"


def test_vintage_dates_and_fetch_run(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    cache.upsert_vintage_dates("RSFSDP", ["2013-05-13", "2013-06-13"])
    cache.upsert_vintage_dates("RSFSDP", ["2013-06-13"])  # idempotent
    assert cache.vintages_for("RSFSDP") == ["2013-05-13", "2013-06-13"]
    cache.record_fetch_run(
        FetchSummary("RSFSDP", "observations", 200, 2, 0, "ok"),
        started_at="2026-07-20T00:00:00Z",
    )
