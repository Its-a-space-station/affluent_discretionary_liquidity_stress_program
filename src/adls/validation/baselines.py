"""Pure-stdlib simple baseline math for the validation floor."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import ScalarForecast, VectorForecast

PIVOT_TOLERANCE = 1e-12


def forecast_path_signal(
    values: Sequence[float],
    threshold: float | None,
    *,
    dwell_months: int,
) -> bool | None:
    if dwell_months < 1:
        raise ValueError("dwell months must be positive")
    if threshold is None or not math.isfinite(threshold):
        return None
    if len(values) < dwell_months or not _finite(values):
        return None
    above = tuple(value >= threshold for value in values)
    return any(
        all(above[start : start + dwell_months]) for start in range(len(above) - dwell_months + 1)
    )


def _finite(values: Sequence[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def _solve(matrix: list[list[float]], vector: list[float]) -> tuple[float, ...] | None:
    size = len(vector)
    if size == 0 or len(matrix) != size or any(len(row) != size for row in matrix):
        return None
    augmented = [row[:] + [value] for row, value in zip(matrix, vector, strict=True)]
    scale = max((abs(value) for row in augmented for value in row[:-1]), default=0.0)
    tolerance = PIVOT_TOLERANCE * max(1.0, scale)

    for column in range(size):
        pivot_row = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        pivot = augmented[pivot_row][column]
        if abs(pivot) <= tolerance:
            return None
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]
        pivot = augmented[column][column]
        augmented[column] = [value / pivot for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            augmented[row] = [
                current - factor * pivot_value
                for current, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    result = tuple(row[-1] for row in augmented)
    return result if _finite(result) else None


def _ols(
    features: Sequence[Sequence[float]],
    targets: Sequence[float],
) -> tuple[float, ...] | None:
    if not features or len(features) != len(targets):
        return None
    width = len(features[0])
    if width == 0 or any(len(row) != width for row in features):
        return None
    if any(not _finite(row) for row in features) or not _finite(targets):
        return None
    normal = [[0.0 for _ in range(width)] for _ in range(width)]
    right = [0.0 for _ in range(width)]
    for row, target in zip(features, targets, strict=True):
        for left in range(width):
            right[left] += row[left] * target
            for column in range(width):
                normal[left][column] += row[left] * row[column]
    return _solve(normal, right)


def seasonal_naive_forecast(
    history: Sequence[float],
    horizon: int,
    *,
    season: int = 12,
) -> ScalarForecast:
    if horizon < 1 or season < 1:
        raise ValueError("horizon and season must be positive")
    if not _finite(history):
        return ScalarForecast((), "non_finite_history")
    if len(history) < season:
        return ScalarForecast((), "insufficient_history")
    values = tuple(history[len(history) - season + (step % season)] for step in range(horizon))
    return ScalarForecast(values)


def ar_forecast(
    history: Sequence[float],
    *,
    lag_count: int,
    horizon: int,
    minimum: int,
) -> ScalarForecast:
    if lag_count < 1 or horizon < 1 or minimum < lag_count + 2:
        raise ValueError("invalid AR dimensions")
    if not _finite(history):
        return ScalarForecast((), "non_finite_history")
    if len(history) < minimum:
        return ScalarForecast((), "insufficient_history")

    features: list[tuple[float, ...]] = []
    targets: list[float] = []
    for index in range(lag_count, len(history)):
        features.append((1.0, *(history[index - lag] for lag in range(1, lag_count + 1))))
        targets.append(history[index])
    coefficients = _ols(features, targets)
    if coefficients is None:
        return ScalarForecast((), "singular_fit")

    working = list(history)
    forecast: list[float] = []
    for _ in range(horizon):
        row = (1.0, *(working[-lag] for lag in range(1, lag_count + 1)))
        value = math.fsum(
            coefficient * feature for coefficient, feature in zip(coefficients, row, strict=True)
        )
        if not math.isfinite(value):
            return ScalarForecast((), "non_finite_forecast")
        forecast.append(value)
        working.append(value)
    return ScalarForecast(tuple(forecast))


def var_forecast(
    history: Sequence[Sequence[float]],
    *,
    lag_count: int,
    horizon: int,
    minimum: int,
) -> VectorForecast:
    if lag_count < 1 or horizon < 1 or minimum < lag_count + 2:
        raise ValueError("invalid VAR dimensions")
    if not history:
        return VectorForecast((), "insufficient_history")
    width = len(history[0])
    if width < 1 or any(len(vector) != width for vector in history):
        return VectorForecast((), "inconsistent_vector_width")
    if any(not _finite(vector) for vector in history):
        return VectorForecast((), "non_finite_history")
    if len(history) < minimum:
        return VectorForecast((), "insufficient_history")

    features: list[tuple[float, ...]] = []
    targets: list[list[float]] = [[] for _ in range(width)]
    for index in range(lag_count, len(history)):
        feature_row: list[float] = [1.0]
        for lag in range(1, lag_count + 1):
            feature_row.extend(history[index - lag])
        features.append(tuple(feature_row))
        for component in range(width):
            targets[component].append(history[index][component])

    equations = tuple(_ols(features, target) for target in targets)
    if any(equation is None for equation in equations):
        return VectorForecast((), "singular_fit")

    working = [tuple(vector) for vector in history]
    forecast: list[tuple[float, ...]] = []
    for _ in range(horizon):
        row_values: list[float] = [1.0]
        for lag in range(1, lag_count + 1):
            row_values.extend(working[-lag])
        forecast_row = tuple(row_values)
        next_vector = tuple(
            math.fsum(
                coefficient * feature
                for coefficient, feature in zip(equation or (), forecast_row, strict=True)
            )
            for equation in equations
        )
        if not _finite(next_vector):
            return VectorForecast((), "non_finite_forecast")
        forecast.append(next_vector)
        working.append(next_vector)
    return VectorForecast(tuple(forecast))


def mean_absolute_scaled_error(
    *,
    training: Sequence[float],
    actual: Sequence[float],
    forecast: Sequence[float],
    season: int = 12,
) -> float | None:
    if season < 1:
        raise ValueError("season must be positive")
    if len(actual) != len(forecast) or not actual:
        return None
    if len(training) <= season:
        return None
    if not _finite(training) or not _finite(actual) or not _finite(forecast):
        return None
    scale_terms = [
        abs(training[index] - training[index - season]) for index in range(season, len(training))
    ]
    scale = math.fsum(scale_terms) / len(scale_terms)
    if scale <= 0.0:
        return None
    error = math.fsum(
        abs(observed - predicted) for observed, predicted in zip(actual, forecast, strict=True)
    ) / len(actual)
    return error / scale
