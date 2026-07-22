"""Expanding-origin seasonal-naive, AR, and small-VAR baseline evaluation."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .baselines import (
    ar_forecast,
    forecast_path_signal,
    mean_absolute_scaled_error,
    seasonal_naive_forecast,
    var_forecast,
)
from .models import BaselineContract, BaselineOrigin, FrozenPoint

TIER_A_FAMILIES = ("census_retail", "household_liquidity", "umich_top_tercile")
BASELINE_MODELS = ("seasonal_naive", "ar", "var")


def _scalar_suffix(points: Sequence[FrozenPoint], end: int) -> tuple[float, ...]:
    values: list[float] = []
    for point in reversed(points[: end + 1]):
        if point.composite_abstained or point.tier_a_value is None:
            break
        if not math.isfinite(point.tier_a_value):
            break
        values.append(point.tier_a_value)
    return tuple(reversed(values))


def _vector_suffix(points: Sequence[FrozenPoint], end: int) -> tuple[tuple[float, ...], ...]:
    values: list[tuple[float, ...]] = []
    for point in reversed(points[: end + 1]):
        families = dict(point.family_values)
        vector = tuple(families.get(family) for family in TIER_A_FAMILIES)
        if any(value is None or not math.isfinite(value) for value in vector):
            break
        values.append(tuple(float(value) for value in vector if value is not None))
    return tuple(reversed(values))


def _future_actual(
    points: Sequence[FrozenPoint],
    origin: int,
    horizon: int,
) -> tuple[tuple[float, ...], str | None]:
    selected = points[origin + 1 : origin + 1 + horizon]
    if len(selected) != horizon:
        return (), "future_horizon_unavailable"
    if any(point.composite_abstained or point.tier_a_value is None for point in selected):
        return (), "future_actual_abstention"
    return (
        tuple(float(point.tier_a_value) for point in selected if point.tier_a_value is not None),
        None,
    )


def _origin(
    point: FrozenPoint,
    model: str,
    values: tuple[float, ...],
    reason: str | None,
    training: tuple[float, ...],
    actual: tuple[float, ...],
    actual_reason: str | None,
    contract: BaselineContract,
) -> BaselineOrigin:
    forecast_reason = reason
    signal = (
        forecast_path_signal(
            values,
            point.p70_threshold,
            dwell_months=contract.signal_dwell_months,
        )
        if reason is None
        else None
    )
    if reason is None and signal is None:
        reason = "threshold_unavailable"
    mase_reason: str | None
    if forecast_reason is not None:
        mase = None
        mase_reason = "forecast_abstention"
    elif actual_reason is not None:
        mase = None
        mase_reason = actual_reason
    else:
        mase = mean_absolute_scaled_error(
            training=training,
            actual=actual,
            forecast=values,
            season=contract.season_months,
        )
        mase_reason = None if mase is not None else "undefined_scale"
    return BaselineOrigin(
        point.month,
        model,
        values,
        signal,
        mase,
        reason,
        mase_reason,
    )


def evaluate_baselines(
    points: Sequence[FrozenPoint],
    contract: BaselineContract,
) -> tuple[BaselineOrigin, ...]:
    results: list[BaselineOrigin] = []
    for index, point in enumerate(points):
        scalar = _scalar_suffix(points, index)
        vectors = _vector_suffix(points, index)
        actual, actual_reason = _future_actual(points, index, contract.forecast_months)

        if len(scalar) < contract.minimum_months:
            seasonal_values: tuple[float, ...] = ()
            seasonal_reason: str | None = "insufficient_history"
        else:
            seasonal = seasonal_naive_forecast(
                scalar,
                contract.forecast_months,
                season=contract.season_months,
            )
            seasonal_values = seasonal.values
            seasonal_reason = seasonal.reason
        results.append(
            _origin(
                point,
                "seasonal_naive",
                seasonal_values,
                seasonal_reason,
                scalar,
                actual,
                actual_reason,
                contract,
            )
        )

        ar_result = ar_forecast(
            scalar,
            lag_count=contract.ar_lags,
            horizon=contract.forecast_months,
            minimum=contract.minimum_months,
        )
        results.append(
            _origin(
                point,
                "ar",
                ar_result.values,
                ar_result.reason,
                scalar,
                actual,
                actual_reason,
                contract,
            )
        )

        var_result = var_forecast(
            vectors,
            lag_count=contract.var_lags,
            horizon=contract.forecast_months,
            minimum=contract.minimum_months,
        )
        var_values = tuple(math.fsum(vector) / len(vector) for vector in var_result.vectors)
        results.append(
            _origin(
                point,
                "var",
                var_values,
                var_result.reason,
                scalar,
                actual,
                actual_reason,
                contract,
            )
        )
    return tuple(results)
