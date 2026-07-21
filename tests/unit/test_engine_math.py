from __future__ import annotations

import math
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from adls.alfred.cache import VintageCache
from adls.contracts import ObservationSpan, PointInTimeValue, ValidationResult
from adls.engine.models import DatedValue
from adls.engine.transforms import (
    evaluate_freshness,
    monthly_values,
    trailing_z,
    transform_history,
    transform_pooled_history,
)
from adls.inputs.loader import PointInTimeLoader
from adls.registry import by_id


def _dated(count: int, *, current: float | None = None) -> tuple[DatedValue, ...]:
    start = date(2020, 1, 1)
    points = [
        DatedValue(
            date(start.year + index // 12, index % 12 + 1, 1).isoformat(),
            float(index),
        )
        for index in range(count)
    ]
    if current is not None:
        points[-1] = replace(points[-1], value=current)
    return tuple(points)


def _pit(series_id: str, observation_date: str, value: str) -> PointInTimeValue:
    return PointInTimeValue(
        series_id=series_id,
        observation_date=observation_date,
        value_text=value,
        release_date="2024-02-09",
        available_from="2024-02-09",
        available_through="2024-02-09",
        source="alfred",
    )


def test_trailing_z_excludes_current_uses_population_sigma_and_requires_36() -> None:
    insufficient = trailing_z(_dated(36), window_months=120, min_observations=36)
    scored = trailing_z(_dated(37), window_months=120, min_observations=36)

    expected_mean = sum(range(36)) / 36
    expected_sigma = math.sqrt(sum((value - expected_mean) ** 2 for value in range(36)) / 36)
    assert insufficient.value is None
    assert insufficient.reference_count == 35
    assert insufficient.reason == "insufficient_history:35<36"
    assert scored.reference_count == 36
    assert scored.uncapped_value == pytest.approx((36 - expected_mean) / expected_sigma)
    assert scored.value == scored.uncapped_value


def test_trailing_z_caps_at_three_and_abstains_on_zero_sigma() -> None:
    capped = trailing_z(_dated(37, current=1000.0), window_months=120, min_observations=36)
    flat = trailing_z(
        tuple(DatedValue(point.observation_date, 5.0) for point in _dated(37)),
        window_months=120,
        min_observations=36,
    )

    assert capped.uncapped_value is not None and capped.uncapped_value > 3
    assert capped.value == 3.0
    assert flat.value is None
    assert flat.reason == "zero_population_sigma"


def test_revolsl_growth_stays_within_loader_snapshot_across_units_break(
    tmp_path: Path,
) -> None:
    cache = VintageCache(tmp_path / "units-break.sqlite")
    cache.initialize()
    spans: list[ObservationSpan] = []
    for index in range(13):
        observation_date = date(2023 + index // 12, index % 12 + 1, 1).isoformat()
        value = 100 + index
        spans.extend(
            (
                ObservationSpan(
                    "REVOLSL",
                    observation_date,
                    "2024-02-01",
                    "2025-02-06",
                    str(value),
                    "alfred",
                ),
                ObservationSpan(
                    "REVOLSL",
                    observation_date,
                    "2025-02-07",
                    "9999-12-31",
                    str(value * 1000),
                    "alfred",
                ),
            )
        )
    cache.upsert_spans(spans)
    cache.mark_backfilled("REVOLSL", "2025-02-07")
    loader = PointInTimeLoader(cache)
    old_snapshot = loader.history_at("REVOLSL", "2025-02-06")
    new_snapshot = loader.history_at("REVOLSL", "2025-02-07")
    original_validation = ValidationResult()
    rescaled_validation = ValidationResult()

    original_growth = transform_history(by_id("REVOLSL"), old_snapshot.values, original_validation)
    rescaled_growth = transform_history(by_id("REVOLSL"), new_snapshot.values, rescaled_validation)

    assert old_snapshot.validation.ok and new_snapshot.validation.ok
    assert original_validation.ok and rescaled_validation.ok
    assert [point.observation_date for point in original_growth] == [
        point.observation_date for point in rescaled_growth
    ]
    assert [point.value for point in original_growth] == pytest.approx(
        [point.value for point in rescaled_growth]
    )


def test_pooled_growth_uses_change_over_prior_combined_level_before_signing() -> None:
    a = tuple(
        _pit("RSFSDP", day.isoformat(), str(80 if index == 12 else 100))
        for index in range(13)
        for day in (date(2023 + index // 12, index % 12 + 1, 1),)
    )
    b = tuple(
        _pit("RSFHFS", day.isoformat(), str(330 if index == 12 else 300))
        for index in range(13)
        for day in (date(2023 + index // 12, index % 12 + 1, 1),)
    )
    validation = ValidationResult()

    transformed = transform_pooled_history(
        (by_id("RSFSDP"), by_id("RSFHFS")),
        {"RSFSDP": a, "RSFHFS": b},
        validation,
    )

    assert validation.ok
    assert transformed == (DatedValue("2024-01-01", -0.025),)


def test_weekly_monthly_mean_applies_wrmmf_shift_and_requires_last_wednesday() -> None:
    h8 = tuple(
        _pit("DPSACBW027SBOG", day, str(value))
        for day, value in (
            ("2024-01-03", 1),
            ("2024-01-10", 2),
            ("2024-01-17", 3),
            ("2024-01-24", 4),
            ("2024-01-31", 5),
            ("2024-02-07", 99),
        )
    )
    wrmmf = tuple(
        _pit("WRMFNS", day, str(value))
        for day, value in (
            ("2024-01-01", 2),
            ("2024-01-08", 4),
            ("2024-01-15", 6),
            ("2024-01-22", 8),
            ("2024-01-29", 10),
            ("2024-02-05", 99),
        )
    )
    validation = ValidationResult()

    h8_months = monthly_values(by_id("DPSACBW027SBOG"), h8, validation)
    wrmmf_months = monthly_values(by_id("WRMFNS"), wrmmf, validation)

    assert validation.ok
    assert h8_months == (DatedValue("2024-01-01", 3.0),)
    assert wrmmf_months == (DatedValue("2024-01-01", 6.0),)

    interior_gap = tuple(row for row in h8 if row.observation_date != "2024-01-17")
    gap_validation = ValidationResult()
    assert monthly_values(by_id("DPSACBW027SBOG"), interior_gap, gap_validation) == ()
    assert "DPSACBW027SBOG incomplete weekly month 2024-01" in gap_validation.warnings


@pytest.mark.parametrize(
    ("series_id", "threshold"),
    (
        ("DPSACBW027SBOG", 21),
        ("RSFSDP", 40),
        ("WRMFNS", 45),
        ("DRCCLACBS", 110),
    ),
)
def test_staleness_is_release_anchored_and_threshold_is_inclusive(
    series_id: str,
    threshold: int,
) -> None:
    assembly = date(2024, 5, 29)
    base = _pit(series_id, "2024-01-01", "1")
    at_limit_date = (assembly - timedelta(days=threshold)).isoformat()
    over_limit_date = (assembly - timedelta(days=threshold + 1)).isoformat()
    at_limit = replace(base, release_date=at_limit_date, available_from=at_limit_date)
    over_limit = replace(base, release_date=over_limit_date, available_from=over_limit_date)

    fresh = evaluate_freshness(by_id(series_id), (at_limit,), assembly.isoformat())
    stale = evaluate_freshness(by_id(series_id), (over_limit,), assembly.isoformat())

    assert fresh.age_days == threshold and not fresh.stale
    assert stale.age_days == threshold + 1 and stale.stale
