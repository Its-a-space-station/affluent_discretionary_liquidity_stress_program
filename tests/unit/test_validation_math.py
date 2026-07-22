from __future__ import annotations

import math

import pytest

from adls.validation.baselines import (
    ar_forecast,
    mean_absolute_scaled_error,
    seasonal_naive_forecast,
    var_forecast,
)
from adls.validation.models import QuarterLevel
from adls.validation.outcomes import compute_outcome_gaps, event_within_two_quarters


def _quarter_at(year: int, quarter: int, offset: int) -> str:
    index = year * 4 + quarter - 1 + offset
    result_year, zero_based_quarter = divmod(index, 4)
    return f"{result_year:04d}-Q{zero_based_quarter + 1}"


def test_outcome_gap_is_componentwise_scale_invariant_and_non_additive() -> None:
    first: list[QuarterLevel] = []
    second: list[QuarterLevel] = []
    for offset in range(10):
        quarter = _quarter_at(2018, 1, offset)
        first_level = 100.0 * math.exp(0.02 * offset)
        second_level = 10_000.0 * math.exp(0.01 * offset)
        if offset == 8:
            first_level *= 0.97
            second_level *= 0.99
        first.append(QuarterLevel(quarter, first_level))
        second.append(QuarterLevel(quarter, second_level))

    gaps = compute_outcome_gaps(tuple(first), tuple(second))
    target = next(item for item in gaps if item.quarter == _quarter_at(2018, 1, 8))

    assert target.component_one_gap == pytest.approx(-3.0)
    assert target.component_two_gap == pytest.approx(-1.0)
    assert target.synthetic_gap == pytest.approx(-2.0)
    assert target.event is True

    rescaled = compute_outcome_gaps(
        tuple(QuarterLevel(item.quarter, item.level * 1_000.0) for item in first),
        tuple(QuarterLevel(item.quarter, item.level * 0.001) for item in second),
    )
    rescaled_target = next(item for item in rescaled if item.quarter == _quarter_at(2018, 1, 8))
    assert rescaled_target.synthetic_gap == pytest.approx(target.synthetic_gap)


def test_outcome_rows_retain_missing_or_invalid_components_as_abstentions() -> None:
    first = tuple(
        QuarterLevel(_quarter_at(2020, 1, offset), 100.0 + offset) for offset in range(10)
    )
    second = tuple(
        QuarterLevel(_quarter_at(2020, 1, offset), 200.0 + offset)
        for offset in range(10)
        if offset != 8
    )

    gaps = compute_outcome_gaps(first, second)
    target = next(item for item in gaps if item.quarter == _quarter_at(2020, 1, 8))

    assert target.synthetic_gap is None
    assert target.event is None
    assert target.reason == "missing_component"
    assert len(gaps) == 10


def test_event_mapping_uses_exactly_the_next_two_calendar_quarters() -> None:
    outcomes = compute_outcome_gaps(
        tuple(
            QuarterLevel(
                _quarter_at(2018, 1, offset),
                100.0 * math.exp(0.01 * offset) * (0.95 if offset == 9 else 1.0),
            )
            for offset in range(12)
        ),
        tuple(
            QuarterLevel(_quarter_at(2018, 1, offset), 200.0 * math.exp(0.01 * offset))
            for offset in range(12)
        ),
    )

    event, reason, quarters = event_within_two_quarters("2019-12", outcomes)

    assert quarters == ("2020-Q1", "2020-Q2")
    assert event is True
    assert reason is None


def test_ar_and_var_forecasts_recover_deterministic_linear_fixtures() -> None:
    ar_values = [0.2, -0.1]
    for _ in range(50):
        ar_values.append(0.75 + 0.6 * ar_values[-1] - 0.2 * ar_values[-2])

    ar_result = ar_forecast(tuple(ar_values), lag_count=2, horizon=3, minimum=20)

    assert ar_result.reason is None
    expected: list[float] = []
    working = list(ar_values)
    for _ in range(3):
        value = 0.75 + 0.6 * working[-1] - 0.2 * working[-2]
        expected.append(value)
        working.append(value)
    assert ar_result.values == pytest.approx(expected)

    vectors = [(1.0, 2.0, -1.0)]
    for _ in range(50):
        left, middle, right = vectors[-1]
        vectors.append(
            (
                0.2 + 0.5 * left + 0.1 * middle,
                -0.1 + 0.2 * left + 0.4 * middle + 0.1 * right,
                0.3 - 0.1 * middle + 0.6 * right,
            )
        )

    var_result = var_forecast(tuple(vectors), lag_count=1, horizon=2, minimum=20)

    assert var_result.reason is None
    expected_vectors: list[tuple[float, float, float]] = []
    working_vectors = list(vectors)
    for _ in range(2):
        left, middle, right = working_vectors[-1]
        value = (
            0.2 + 0.5 * left + 0.1 * middle,
            -0.1 + 0.2 * left + 0.4 * middle + 0.1 * right,
            0.3 - 0.1 * middle + 0.6 * right,
        )
        expected_vectors.append(value)
        working_vectors.append(value)
    for actual, expected_vector in zip(var_result.vectors, expected_vectors, strict=True):
        assert actual == pytest.approx(expected_vector)


def test_baselines_abstain_instead_of_dropping_incomplete_windows() -> None:
    seasonal = seasonal_naive_forecast(tuple(float(i) for i in range(12)), 6, season=12)
    assert seasonal.reason is None
    assert seasonal.values == pytest.approx(range(6))

    insufficient_ar = ar_forecast((1.0, 2.0, 3.0), lag_count=2, horizon=2, minimum=10)
    assert insufficient_ar.values == ()
    assert insufficient_ar.reason == "insufficient_history"

    incomplete_var = var_forecast(
        ((1.0, 2.0, 3.0), (2.0, math.nan, 4.0)),
        lag_count=1,
        horizon=1,
        minimum=3,
    )
    assert incomplete_var.vectors == ()
    assert incomplete_var.reason == "non_finite_history"


def test_mase_uses_only_prior_seasonal_differences_and_requires_full_horizon() -> None:
    training = tuple(float(index) for index in range(24))
    result = mean_absolute_scaled_error(
        training=training,
        actual=(24.0, 25.0),
        forecast=(23.0, 27.0),
        season=12,
    )
    assert result == pytest.approx(1.5 / 12.0)

    assert (
        mean_absolute_scaled_error(
            training=training,
            actual=(24.0,),
            forecast=(24.0, 25.0),
            season=12,
        )
        is None
    )
