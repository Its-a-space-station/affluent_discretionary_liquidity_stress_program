"""Checker-owned percentile and dwell replay."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_EVEN, Decimal

from .models import BandDecision, BandName, BandThresholds, CheckerRules

SIX_PLACES = Decimal("0.000001")


def publication_float(value: float) -> float:
    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite():
        raise ValueError("publication value must be finite")
    rounded = decimal_value.quantize(SIX_PLACES, rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        rounded = abs(rounded)
    return float(format(rounded, "f"))


def _percentile(values: tuple[float, ...], percentile_numerator: int) -> Decimal:
    if not values:
        raise ValueError("percentile requires values")
    if not 0 <= percentile_numerator <= 100:
        raise ValueError("percentile numerator must be between 0 and 100")
    ordered = sorted(Decimal(str(value)) for value in values)
    position = Decimal(len(ordered) - 1) * Decimal(percentile_numerator) / Decimal(100)
    lower = int(position)
    if lower == len(ordered) - 1:
        return ordered[lower]
    weight = position - Decimal(lower)
    return ordered[lower] + (ordered[lower + 1] - ordered[lower]) * weight


def _publication_decimal(value: Decimal) -> float:
    rounded = value.quantize(SIX_PLACES, rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        rounded = abs(rounded)
    return float(format(rounded, "f"))


def _thresholds(values: tuple[float, ...]) -> BandThresholds:
    return BandThresholds(
        _publication_decimal(_percentile(values, 70)),
        _publication_decimal(_percentile(values, 85)),
        _publication_decimal(_percentile(values, 95)),
    )


def classify_band(value: float, thresholds: BandThresholds) -> BandName:
    if value < thresholds.p70:
        return "Normal"
    if value < thresholds.p85:
        return "Watch"
    if value <= thresholds.p95:
        return "Elevated"
    return "High"


def evaluate_band(
    prior_values: tuple[float | None, ...],
    previous: BandDecision | None,
    current: float | None,
    rules: CheckerRules,
) -> BandDecision:
    reference_source = prior_values
    if rules.percentile_includes_current:
        reference_source = (*prior_values, current)
    numeric_reference = tuple(value for value in reference_source if value is not None)
    if any(not math.isfinite(value) for value in numeric_reference):
        raise ValueError("band history contains a non-finite value")
    if current is not None and not math.isfinite(current):
        raise ValueError("current band value is non-finite")

    reference_count = len(numeric_reference)
    eligible = len(prior_values) + 1 >= 36 and reference_count >= 35
    confirmed = previous.confirmed_band if previous is not None else None
    if not eligible:
        return BandDecision(
            False,
            reference_count,
            None,
            None,
            None,
            confirmed,
            None,
            0,
        )

    thresholds = _thresholds(numeric_reference)
    if current is None:
        return BandDecision(
            True,
            reference_count,
            thresholds,
            None,
            None,
            confirmed,
            None,
            0,
        )
    raw_band = classify_band(current, thresholds)
    if raw_band == confirmed:
        return BandDecision(
            True,
            reference_count,
            thresholds,
            raw_band,
            confirmed,
            confirmed,
            None,
            0,
        )

    prior_candidate = previous.candidate_band if previous is not None else None
    prior_count = previous.candidate_count if previous is not None else 0
    candidate_count = prior_count + 1 if prior_candidate == raw_band else 1
    if candidate_count >= rules.dwell_months:
        return BandDecision(
            True,
            reference_count,
            thresholds,
            raw_band,
            raw_band,
            raw_band,
            None,
            0,
        )
    return BandDecision(
        True,
        reference_count,
        thresholds,
        raw_band,
        confirmed,
        confirmed,
        raw_band,
        candidate_count,
    )


def decision_payload(decision: BandDecision) -> dict[str, object]:
    thresholds: dict[str, float] | None = None
    if decision.thresholds is not None:
        thresholds = {
            "p70": decision.thresholds.p70,
            "p85": decision.thresholds.p85,
            "p95": decision.thresholds.p95,
        }
    return {
        "candidate_band": decision.candidate_band,
        "candidate_count": decision.candidate_count,
        "confirmed_band": decision.confirmed_band,
        "eligible": decision.eligible,
        "published_band": decision.published_band,
        "raw_band": decision.raw_band,
        "reference_count": decision.reference_count,
        "thresholds": thresholds,
    }
