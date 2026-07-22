"""Static NBER regime labels and equal-weight macro summaries."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import RegimeReport, RegimeSlice, ScoreRow

NBER_RECESSIONS = (
    ("2007-12", "2009-06"),
    ("2020-02", "2020-04"),
)


def _month_index(month: str) -> int:
    if len(month) != 7 or month[4] != "-":
        raise ValueError(f"month must use YYYY-MM, got {month!r}")
    try:
        year = int(month[:4])
        month_number = int(month[5:])
    except ValueError as exc:
        raise ValueError(f"month must use YYYY-MM, got {month!r}") from exc
    if not 1 <= month_number <= 12 or f"{year:04d}-{month_number:02d}" != month:
        raise ValueError(f"month must use YYYY-MM, got {month!r}")
    return year * 12 + month_number - 1


def regime_for_month(month: str, *, turning_window_months: int) -> tuple[str, str]:
    if turning_window_months < 0:
        raise ValueError("turning window cannot be negative")
    index = _month_index(month)
    recession = any(
        _month_index(start) <= index <= _month_index(end) for start, end in NBER_RECESSIONS
    )
    boundaries = tuple(boundary for interval in NBER_RECESSIONS for boundary in interval)
    turning = any(
        abs(index - _month_index(boundary)) <= turning_window_months for boundary in boundaries
    )
    return (
        "recession" if recession else "expansion",
        "turning_point" if turning else "trend",
    )


def summarize_regimes(rows: Sequence[ScoreRow]) -> RegimeReport:
    from .analysis import summarize_scores

    dimensions = (
        ("business_cycle", ("recession", "expansion"), "business_cycle_regime"),
        ("turning_context", ("turning_point", "trend"), "turning_point_regime"),
    )
    slices: list[RegimeSlice] = []
    macro: list[tuple[str, float | None]] = []
    for dimension, categories, attribute in dimensions:
        rates: list[float] = []
        for category in categories:
            selected = tuple(row for row in rows if getattr(row, attribute) == category)
            summary = summarize_scores(selected)
            slices.append(RegimeSlice(dimension, category, summary))
            if summary.lead_rate is not None:
                rates.append(summary.lead_rate)
        complete = len(rates) == len(categories)
        macro.append((dimension, math.fsum(rates) / len(rates) if complete else None))
    return RegimeReport(tuple(slices), tuple(macro))
