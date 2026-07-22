"""Synthetic real-PCE outcome construction from latest-vintage component levels."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .models import OutcomeGap, QuarterLevel

TREND_QUARTERS = 8
EVENT_THRESHOLD = -2.0


def _parse_quarter(value: str) -> tuple[int, int]:
    if len(value) != 7 or value[4:6] != "-Q":
        raise ValueError(f"quarter must use YYYY-Qn, got {value!r}")
    try:
        year = int(value[:4])
        quarter = int(value[6])
    except ValueError as exc:
        raise ValueError(f"quarter must use YYYY-Qn, got {value!r}") from exc
    if year < 1 or quarter not in {1, 2, 3, 4}:
        raise ValueError(f"quarter must use YYYY-Qn, got {value!r}")
    return year, quarter


def _shift_quarter(value: str, offset: int) -> str:
    year, quarter = _parse_quarter(value)
    index = year * 4 + quarter - 1 + offset
    shifted_year, zero_based_quarter = divmod(index, 4)
    return f"{shifted_year:04d}-Q{zero_based_quarter + 1}"


def _month_quarter(month: str) -> str:
    if len(month) != 7 or month[4] != "-":
        raise ValueError(f"month must use YYYY-MM, got {month!r}")
    try:
        year = int(month[:4])
        month_number = int(month[5:])
    except ValueError as exc:
        raise ValueError(f"month must use YYYY-MM, got {month!r}") from exc
    if year < 1 or not 1 <= month_number <= 12 or f"{year:04d}-{month_number:02d}" != month:
        raise ValueError(f"month must use YYYY-MM, got {month!r}")
    return f"{year:04d}-Q{(month_number - 1) // 3 + 1}"


def _component_gap(history: Sequence[float], current: float) -> float | None:
    if len(history) != TREND_QUARTERS:
        return None
    if current <= 0.0 or not math.isfinite(current):
        return None
    if any(value <= 0.0 or not math.isfinite(value) for value in history):
        return None
    logged = tuple(math.log(value) for value in history)
    mean_x = (TREND_QUARTERS - 1) / 2.0
    mean_y = math.fsum(logged) / TREND_QUARTERS
    denominator = math.fsum((index - mean_x) ** 2 for index in range(TREND_QUARTERS))
    slope = (
        math.fsum((index - mean_x) * (value - mean_y) for index, value in enumerate(logged))
        / denominator
    )
    predicted_log = mean_y + slope * (TREND_QUARTERS - mean_x)
    return 100.0 * (math.exp(math.log(current) - predicted_log) - 1.0)


def _level_map(values: Sequence[QuarterLevel]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in values:
        _parse_quarter(item.quarter)
        if item.quarter in result:
            raise ValueError(f"duplicate quarter {item.quarter}")
        result[item.quarter] = item.level
    return result


def compute_outcome_gaps(
    component_one: Sequence[QuarterLevel],
    component_two: Sequence[QuarterLevel],
) -> tuple[OutcomeGap, ...]:
    """Apply errata item 9 independently to both non-additive components."""
    first = _level_map(component_one)
    second = _level_map(component_two)
    quarters = sorted(set(first) | set(second), key=_parse_quarter)
    results: list[OutcomeGap] = []
    for quarter in quarters:
        if quarter not in first or quarter not in second:
            results.append(OutcomeGap(quarter, None, None, None, None, "missing_component"))
            continue
        prior_quarters = tuple(
            _shift_quarter(quarter, offset) for offset in range(-TREND_QUARTERS, 0)
        )
        if any(candidate not in first or candidate not in second for candidate in prior_quarters):
            results.append(OutcomeGap(quarter, None, None, None, None, "insufficient_history"))
            continue
        first_gap = _component_gap(tuple(first[item] for item in prior_quarters), first[quarter])
        second_gap = _component_gap(
            tuple(second[item] for item in prior_quarters), second[quarter]
        )
        if first_gap is None or second_gap is None:
            results.append(
                OutcomeGap(
                    quarter,
                    first_gap,
                    second_gap,
                    None,
                    None,
                    "invalid_component",
                )
            )
            continue
        synthetic = math.fsum((first_gap, second_gap)) / 2.0
        event = synthetic <= EVENT_THRESHOLD + 1e-12
        results.append(OutcomeGap(quarter, first_gap, second_gap, synthetic, event, None))
    return tuple(results)


def event_within_two_quarters(
    month: str,
    outcomes: Sequence[OutcomeGap] | Mapping[str, OutcomeGap],
) -> tuple[bool | None, str | None, tuple[str, str]]:
    current = _month_quarter(month)
    targets = (_shift_quarter(current, 1), _shift_quarter(current, 2))
    by_quarter = (
        outcomes if isinstance(outcomes, Mapping) else {item.quarter: item for item in outcomes}
    )
    selected = tuple(by_quarter.get(quarter) for quarter in targets)
    if any(item is None for item in selected):
        return None, "outcome_unavailable", targets
    if any(item.event is None for item in selected if item is not None):
        return None, "outcome_abstention", targets
    return any(bool(item.event) for item in selected if item is not None), None, targets
