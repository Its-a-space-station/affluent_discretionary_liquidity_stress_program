from __future__ import annotations

import math
from dataclasses import replace

from adls.validation.analysis import score_binary_signal_series
from adls.validation.baseline_eval import BASELINE_MODELS, evaluate_baselines
from adls.validation.baselines import forecast_path_signal
from adls.validation.models import FrozenPoint, OutcomeGap
from adls.validation.permutation_eval import evaluate_joint_permutation
from adls.validation.regimes import regime_for_month, summarize_regimes
from adls.validation.spec import BASELINE_CONTRACT


def _month_at(offset: int) -> str:
    index = 2015 * 12 + offset
    year, zero_based_month = divmod(index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def _points(count: int = 72) -> tuple[FrozenPoint, ...]:
    points: list[FrozenPoint] = []
    for index in range(count):
        first = math.sin(index / 4.0) + index * 0.01
        second = math.cos(index / 7.0) - index * 0.005
        third = math.sin(index / 9.0) + math.cos(index / 5.0)
        tier_a = (first + second + third) / 3.0
        points.append(
            FrozenPoint(
                month=_month_at(index),
                tier_a_value=tier_a,
                published_band=("Watch" if 40 <= index <= 42 else "Normal"),
                family_values=(
                    ("census_retail", first),
                    ("household_liquidity", second),
                    ("umich_top_tercile", third),
                ),
                composite_abstained=False,
                flags=(),
                p70_threshold=0.2 if index >= 35 else None,
            )
        )
    return tuple(points)


def _outcomes() -> tuple[OutcomeGap, ...]:
    values: list[OutcomeGap] = []
    for year in range(2015, 2024):
        for quarter in range(1, 5):
            key = f"{year:04d}-Q{quarter}"
            event = key in {"2018-Q3", "2018-Q4", "2020-Q2"}
            gap = -3.0 if event else 0.0
            values.append(OutcomeGap(key, gap, gap, gap, event, None))
    return tuple(values)


def test_owner_approved_baseline_contract_is_exact() -> None:
    assert BASELINE_CONTRACT.pin_status == "approved"
    assert BASELINE_CONTRACT.season_months == 12
    assert BASELINE_CONTRACT.ar_lags == 12
    assert BASELINE_CONTRACT.var_lags == 1
    assert BASELINE_CONTRACT.forecast_months == 6
    assert BASELINE_CONTRACT.block_months == 12
    assert BASELINE_CONTRACT.embargo_months == 12


def test_forecast_signal_mapping_requires_two_consecutive_threshold_crossings() -> None:
    assert forecast_path_signal((0.0, 1.0, 0.0, 1.0), 0.5, dwell_months=2) is False
    assert forecast_path_signal((0.0, 1.0, 1.0, 0.0), 0.5, dwell_months=2) is True
    assert forecast_path_signal((1.0,), 0.5, dwell_months=2) is None


def test_baseline_evaluation_retains_every_model_origin_and_tail_mase_abstention() -> None:
    points = _points()
    contract = replace(BASELINE_CONTRACT, trial_count=20)

    rows = evaluate_baselines(points, contract)

    assert len(rows) == len(points) * len(BASELINE_MODELS)
    assert {row.model for row in rows} == set(BASELINE_MODELS)
    first_scored = [row for row in rows if row.month == points[35].month]
    assert len(first_scored) == 3
    assert any(row.forecast_values for row in first_scored)
    tail = [row for row in rows if row.month == points[-1].month]
    assert all(row.mase is None for row in tail)
    assert {row.model: row.mase_reason for row in tail} == {
        "seasonal_naive": "future_horizon_unavailable",
        "ar": "forecast_abstention",
        "var": "future_horizon_unavailable",
    }

    gapped = list(points)
    gapped[50] = replace(gapped[50], tier_a_value=None, composite_abstained=True)
    before_gap = [
        row for row in evaluate_baselines(tuple(gapped), contract) if row.month == points[49].month
    ]
    seasonal = next(row for row in before_gap if row.model == "seasonal_naive")
    assert seasonal.mase is None
    assert seasonal.mase_reason == "future_actual_abstention"


def test_static_regimes_and_macro_reporting_cover_both_dimensions() -> None:
    assert regime_for_month("2020-03", turning_window_months=6) == (
        "recession",
        "turning_point",
    )
    assert regime_for_month("2022-01", turning_window_months=6) == (
        "expansion",
        "trend",
    )
    signals = tuple((point.month, point.published_band == "Watch") for point in _points())
    rows = score_binary_signal_series(signals, _outcomes(), source="fixture")

    report = summarize_regimes(rows)

    assert {item.dimension for item in report.slices} == {
        "business_cycle",
        "turning_context",
    }
    assert dict(report.macro_average_lead_rates).keys() == {
        "business_cycle",
        "turning_context",
    }


def test_permutation_distribution_is_deterministic_and_logs_every_trial() -> None:
    contract = replace(BASELINE_CONTRACT, trial_count=25)

    first = evaluate_joint_permutation(_points(), _outcomes(), contract)
    second = evaluate_joint_permutation(_points(), _outcomes(), contract)

    assert first == second
    assert first.requested_trials == 25
    assert len(first.trials) == 25
    assert first.scored_trials <= first.requested_trials
