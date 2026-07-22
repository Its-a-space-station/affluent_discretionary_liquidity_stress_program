from __future__ import annotations

from pathlib import Path

from adls.alfred.cache import VintageCache
from adls.contracts import ObservationSpan
from adls.validation.cache import load_latest_outcome_levels


def _write_outcome_cache(path: Path) -> None:
    cache = VintageCache(path)
    cache.initialize()
    for series_id, coverage in (
        ("DRCARX1Q020SBEA", "2025-06-01"),
        ("DFSARX1Q020SBEA", "2025-05-01"),
    ):
        cache.upsert_spans(
            (
                ObservationSpan(
                    series_id=series_id,
                    observation_date="2023-10-01",
                    realtime_start="2024-01-01",
                    realtime_end="9999-12-31",
                    value_text=".",
                    source="alfred",
                ),
                ObservationSpan(
                    series_id=series_id,
                    observation_date="2024-01-01",
                    realtime_start="2024-04-01",
                    realtime_end="2025-04-30",
                    value_text="100.0",
                    source="alfred",
                ),
                ObservationSpan(
                    series_id=series_id,
                    observation_date="2024-01-01",
                    realtime_start="2025-05-01",
                    realtime_end="9999-12-31",
                    value_text="110.0",
                    source="alfred",
                ),
            )
        )
        cache.mark_backfilled(series_id, coverage)


def test_latest_outcome_uses_one_common_vintage_and_latest_revision(tmp_path: Path) -> None:
    path = tmp_path / "outcomes.sqlite"
    _write_outcome_cache(path)

    result = load_latest_outcome_levels(path)

    assert result.validation.ok, result.validation.errors
    assert result.vintage == "2025-05-01"
    assert tuple(series_id for series_id, _ in result.components) == (
        "DRCARX1Q020SBEA",
        "DFSARX1Q020SBEA",
    )
    assert all(levels[0].level == 110.0 for _, levels in result.components)
    assert len(result.validation.warnings) == 2
    assert all("missing-value sentinels" in warning for warning in result.validation.warnings)


def test_outcome_cache_refuses_mixed_or_uncovered_vintage(tmp_path: Path) -> None:
    path = tmp_path / "outcomes.sqlite"
    _write_outcome_cache(path)

    result = load_latest_outcome_levels(path, vintage="2025-05-02")

    assert not result.validation.ok
    assert result.components == ()
    assert any("exceeds coverage" in error for error in result.validation.errors)
