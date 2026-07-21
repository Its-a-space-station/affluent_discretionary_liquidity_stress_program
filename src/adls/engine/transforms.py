"""Pure-stdlib transforms and standardization for the maker engine."""

from __future__ import annotations

import math
from calendar import monthrange
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from adls.contracts import PointInTimeValue, ValidationResult
from adls.engine.models import DatedValue, FreshnessResult, ZScoreResult
from adls.registry import SeriesSpec


def _parse_date(text: str, field: str, validation: ValidationResult) -> date | None:
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        validation.error(f"invalid {field} {text!r}")
        return None
    if parsed.isoformat() != text:
        validation.error(f"invalid {field} {text!r}")
        return None
    return parsed


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _last_wednesday(year: int, month: int) -> date:
    final_day = date(year, month, monthrange(year, month)[1])
    return final_day - timedelta(days=(final_day.weekday() - 2) % 7)


def _month_wednesdays(year: int, month: int) -> set[date]:
    first_day = date(year, month, 1)
    current = first_day + timedelta(days=(2 - first_day.weekday()) % 7)
    wednesdays: set[date] = set()
    while current.month == month:
        wednesdays.add(current)
        current += timedelta(days=7)
    return wednesdays


def _numeric_observations(
    spec: SeriesSpec,
    history: Sequence[PointInTimeValue],
    validation: ValidationResult,
) -> tuple[tuple[date, float], ...]:
    parsed_rows: list[tuple[date, float]] = []
    seen_dates: set[date] = set()
    observed_dates: list[date] = []
    prior_date: date | None = None
    latest_missing = False

    for position, row in enumerate(history, 1):
        if row.series_id != spec.series_id:
            validation.error(
                f"{spec.series_id} row {position} carries series_id {row.series_id!r}"
            )
            continue
        observation_date = _parse_date(
            row.observation_date,
            f"{spec.series_id} observation_date",
            validation,
        )
        if observation_date is None:
            continue
        observed_dates.append(observation_date)
        if prior_date is not None and observation_date < prior_date:
            validation.error(f"{spec.series_id} history is not sorted by observation_date")
        prior_date = observation_date
        if observation_date in seen_dates:
            validation.error(
                f"{spec.series_id} duplicate observation_date {observation_date.isoformat()}"
            )
            continue
        seen_dates.add(observation_date)

        if row.value_text == ".":
            validation.warn(
                f"{spec.series_id} missing vendor value at {observation_date.isoformat()}"
            )
            latest_missing = True
            continue
        try:
            decimal_value = Decimal(row.value_text)
        except InvalidOperation:
            validation.error(
                f"{spec.series_id} invalid numeric value {row.value_text!r} "
                f"at {observation_date.isoformat()}"
            )
            latest_missing = True
            continue
        if not decimal_value.is_finite():
            validation.error(
                f"{spec.series_id} non-finite value {row.value_text!r} "
                f"at {observation_date.isoformat()}"
            )
            latest_missing = True
            continue
        parsed_rows.append((observation_date, float(decimal_value)))
        latest_missing = False

    if observed_dates and latest_missing and observed_dates[-1] == max(observed_dates):
        validation.error(f"{spec.series_id} latest observation has no numeric value")
    return tuple(parsed_rows)


def monthly_values(
    spec: SeriesSpec,
    history: Sequence[PointInTimeValue],
    validation: ValidationResult,
) -> tuple[DatedValue, ...]:
    """Normalize native observations to dated monthly or quarterly values."""
    rows = _numeric_observations(spec, history, validation)
    if spec.frequency in {"m", "q"}:
        points: list[DatedValue] = []
        for observation_date, value in rows:
            if observation_date.day != 1:
                validation.error(
                    f"{spec.series_id} {spec.frequency} observation is not month-start: "
                    f"{observation_date.isoformat()}"
                )
                continue
            if spec.frequency == "q" and observation_date.month not in {1, 4, 7, 10}:
                validation.error(
                    f"{spec.series_id} quarterly observation has invalid month: "
                    f"{observation_date.isoformat()}"
                )
                continue
            points.append(DatedValue(observation_date.isoformat(), value))
        return tuple(points)

    if spec.frequency != "w":
        validation.error(f"{spec.series_id} has unsupported frequency {spec.frequency!r}")
        return ()

    grouped: dict[tuple[int, int], list[tuple[date, float]]] = {}
    for observation_date, value in rows:
        canonical_date = observation_date + timedelta(days=spec.canonical_date_shift_days)
        if canonical_date.weekday() != 2:
            validation.error(
                f"{spec.series_id} canonical weekly date is not Wednesday: "
                f"{canonical_date.isoformat()}"
            )
            continue
        grouped.setdefault((canonical_date.year, canonical_date.month), []).append(
            (canonical_date, value)
        )

    points = []
    for year, month in sorted(grouped):
        month_rows = grouped[(year, month)]
        complete_through = _last_wednesday(year, month)
        observed_wednesdays = {day for day, _ in month_rows}
        if complete_through not in observed_wednesdays or observed_wednesdays != _month_wednesdays(
            year, month
        ):
            validation.warn(f"{spec.series_id} incomplete weekly month {year:04d}-{month:02d}")
            continue
        mean_value = math.fsum(value for _, value in month_rows) / len(month_rows)
        points.append(DatedValue(date(year, month, 1).isoformat(), mean_value))
    return tuple(points)


def _yoy_growth(
    points: Sequence[DatedValue],
    series_id: str,
    validation: ValidationResult,
) -> tuple[DatedValue, ...]:
    by_date = {date.fromisoformat(point.observation_date): point.value for point in points}
    growth: list[DatedValue] = []
    for point in points:
        current_date = date.fromisoformat(point.observation_date)
        prior_date = _add_months(current_date, -12)
        if prior_date not in by_date:
            continue
        prior = by_date[prior_date]
        if prior == 0:
            validation.error(
                f"{series_id} zero denominator at {prior_date.isoformat()} for YoY growth"
            )
            continue
        growth.append(DatedValue(point.observation_date, (point.value - prior) / prior))
    return tuple(growth)


def transform_history(
    spec: SeriesSpec,
    history: Sequence[PointInTimeValue],
    validation: ValidationResult,
) -> tuple[DatedValue, ...]:
    """Transform one complete point-in-time history; vintages cannot be mixed here."""
    points = monthly_values(spec, history, validation)
    if spec.transform == "hundred_minus_level":
        return tuple(DatedValue(point.observation_date, 100.0 - point.value) for point in points)
    if spec.transform == "inverted_level":
        return tuple(DatedValue(point.observation_date, -point.value) for point in points)
    if spec.transform == "level":
        return points
    if spec.transform == "yoy_growth":
        return _yoy_growth(points, spec.series_id, validation)
    validation.error(f"{spec.series_id} unsupported single-series transform {spec.transform!r}")
    return ()


def transform_pooled_history(
    specs: Sequence[SeriesSpec],
    histories: Mapping[str, Sequence[PointInTimeValue]],
    validation: ValidationResult,
) -> tuple[DatedValue, ...]:
    """Pool registered family members before YoY growth and stress signing."""
    if not specs or any(spec.transform != "pooled_yoy_growth" for spec in specs):
        validation.error("pooled transform requires pooled_yoy_growth members")
        return ()

    monthly_by_series = {
        spec.series_id: {
            date.fromisoformat(point.observation_date): point.value
            for point in monthly_values(spec, histories[spec.series_id], validation)
        }
        for spec in specs
    }
    common_dates = set.intersection(
        *(set(series_values) for series_values in monthly_by_series.values())
    )
    transformed: list[DatedValue] = []
    for current_date in sorted(common_dates):
        prior_date = _add_months(current_date, -12)
        if any(prior_date not in values for values in monthly_by_series.values()):
            continue
        prior_total = math.fsum(values[prior_date] for values in monthly_by_series.values())
        if prior_total == 0:
            members = ",".join(spec.series_id for spec in specs)
            validation.error(
                f"pooled family {members} has zero denominator at {prior_date.isoformat()}"
            )
            continue
        change = math.fsum(
            values[current_date] - values[prior_date] for values in monthly_by_series.values()
        )
        transformed.append(DatedValue(current_date.isoformat(), -(change / prior_total)))
    return tuple(transformed)


def trailing_z(
    points: Sequence[DatedValue],
    *,
    window_months: int,
    min_observations: int,
) -> ZScoreResult:
    """Score the latest point against prior dated observations, excluding itself."""
    if not points:
        return ZScoreResult(None, None, 0, "no_transformed_observations")
    current = points[-1]
    current_date = date.fromisoformat(current.observation_date)
    cutoff = _add_months(current_date, -window_months)
    references = [
        point.value
        for point in points[:-1]
        if cutoff <= date.fromisoformat(point.observation_date) < current_date
    ]
    reference_count = len(references)
    if reference_count < min_observations:
        return ZScoreResult(
            None,
            None,
            reference_count,
            f"insufficient_history:{reference_count}<{min_observations}",
        )
    if not math.isfinite(current.value) or any(not math.isfinite(value) for value in references):
        return ZScoreResult(None, None, reference_count, "non_finite_value")

    mean = math.fsum(references) / reference_count
    variance = math.fsum((value - mean) ** 2 for value in references) / reference_count
    if variance == 0:
        return ZScoreResult(None, None, reference_count, "zero_population_sigma")
    uncapped = (current.value - mean) / math.sqrt(variance)
    return ZScoreResult(max(-3.0, min(3.0, uncapped)), uncapped, reference_count)


def evaluate_freshness(
    spec: SeriesSpec,
    history: Sequence[PointInTimeValue],
    assembly_date: str,
    validation: ValidationResult | None = None,
) -> FreshnessResult:
    """Apply the registered release-anchored staleness threshold."""
    result = validation if validation is not None else ValidationResult()
    assembly = _parse_date(assembly_date, "assembly date", result)
    if assembly is None:
        return FreshnessResult(spec.series_id, None, None, True, "invalid_assembly_date")
    if not history:
        return FreshnessResult(spec.series_id, None, None, True, "missing_history")

    release_dates: list[date] = []
    for row in history:
        release = _parse_date(row.release_date, f"{spec.series_id} release_date", result)
        if release is not None:
            release_dates.append(release)
    if len(release_dates) != len(history):
        return FreshnessResult(spec.series_id, None, None, True, "invalid_release_date")

    latest_release = max(release_dates)
    age_days = (assembly - latest_release).days
    if age_days < 0:
        result.error(
            f"{spec.series_id} latest release {latest_release.isoformat()} is after assembly "
            f"{assembly.isoformat()}"
        )
        return FreshnessResult(
            spec.series_id,
            latest_release.isoformat(),
            age_days,
            True,
            "future_release",
        )
    stale = age_days > spec.staleness_days
    reason = f"stale:{age_days}>{spec.staleness_days}" if stale else None
    return FreshnessResult(
        spec.series_id,
        latest_release.isoformat(),
        age_days,
        stale,
        reason,
    )
