from __future__ import annotations

import pytest

from adls.engine.bands import (
    BandDecision,
    BandThresholds,
    classify_band,
    evaluate_band,
    linear_percentile,
)


def _decision(
    *,
    confirmed: str | None,
    candidate: str | None = None,
    candidate_count: int = 0,
) -> BandDecision:
    return BandDecision(
        eligible=True,
        reference_count=35,
        thresholds=BandThresholds(23.8, 28.9, 32.3),
        raw_band=confirmed,
        published_band=confirmed,
        confirmed_band=confirmed,
        candidate_band=candidate,
        candidate_count=candidate_count,
    )


def test_linear_percentile_and_exact_band_boundaries_are_pinned() -> None:
    assert linear_percentile((0.0, 10.0), 0.70) == pytest.approx(7.0)
    thresholds = BandThresholds(p70=70.0, p85=85.0, p95=95.0)

    assert classify_band(69.999, thresholds) == "Normal"
    assert classify_band(70.0, thresholds) == "Watch"
    assert classify_band(84.999, thresholds) == "Watch"
    assert classify_band(85.0, thresholds) == "Elevated"
    assert classify_band(95.0, thresholds) == "Elevated"
    assert classify_band(95.001, thresholds) == "High"


def test_percentile_half_quantum_uses_exact_decimal_type_7_arithmetic() -> None:
    prior_values = (-1.0,) * 31 + (-0.100000, -0.099985) + (1.0,) * 13

    assert linear_percentile(prior_values, 0.70) == -0.0999925
    decision = evaluate_band(prior_values, None, 0.0)

    assert decision.thresholds is not None
    assert decision.thresholds.p70 == -0.099992


def test_current_value_is_excluded_and_month_36_only_starts_dwell() -> None:
    thirty_four_prior = tuple(float(value) for value in range(34))
    before_burn_in = evaluate_band(thirty_four_prior, None, 1_000_000.0)

    assert not before_burn_in.eligible
    assert before_burn_in.thresholds is None
    assert before_burn_in.published_band is None

    thirty_five_prior = (*thirty_four_prior, 34.0)
    month_36 = evaluate_band(thirty_five_prior, None, 1_000_000.0)

    assert month_36.eligible
    assert month_36.reference_count == 35
    assert month_36.thresholds is not None
    assert month_36.thresholds.p95 < 35.0
    assert month_36.raw_band == "High"
    assert month_36.candidate_band == "High"
    assert month_36.candidate_count == 1
    assert month_36.published_band is None

    month_37 = evaluate_band((*thirty_five_prior, 1_000_000.0), month_36, 1_000_001.0)
    assert month_37.confirmed_band == "High"
    assert month_37.published_band == "High"
    assert month_37.candidate_band is None


def test_raw_band_change_restarts_dwell_and_allows_a_direct_jump() -> None:
    prior_values = tuple(float(value) for value in range(35))
    watch_candidate = _decision(confirmed="Normal", candidate="Watch", candidate_count=1)

    first_elevated = evaluate_band(prior_values, watch_candidate, 30.0)
    assert first_elevated.confirmed_band == "Normal"
    assert first_elevated.published_band == "Normal"
    assert first_elevated.candidate_band == "Elevated"
    assert first_elevated.candidate_count == 1

    second_elevated = evaluate_band((*prior_values, 30.0), first_elevated, 31.0)
    assert second_elevated.confirmed_band == "Elevated"
    assert second_elevated.published_band == "Elevated"
    assert second_elevated.candidate_band is None


def test_two_month_exit_and_missing_value_behavior() -> None:
    prior_values = tuple(float(value) for value in range(35))
    elevated = _decision(confirmed="Elevated")

    first_normal = evaluate_band(prior_values, elevated, -1.0)
    assert first_normal.confirmed_band == "Elevated"
    assert first_normal.published_band == "Elevated"
    assert first_normal.candidate_band == "Normal"

    missing = evaluate_band((*prior_values, -1.0), first_normal, None)
    assert missing.raw_band is None
    assert missing.published_band is None
    assert missing.confirmed_band == "Elevated"
    assert missing.candidate_band is None
    assert missing.candidate_count == 0

    restart = evaluate_band((*prior_values, -1.0, None), missing, -2.0)
    confirmed_exit = evaluate_band((*prior_values, -1.0, None, -2.0), restart, -3.0)
    assert restart.candidate_count == 1
    assert confirmed_exit.confirmed_band == "Normal"
    assert confirmed_exit.published_band == "Normal"
