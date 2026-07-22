"""Tier-A percentile bands over the frozen canonical sequence."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from adls.engine.serialize import canonicalize_float

BandName = Literal["Normal", "Watch", "Elevated", "High"]


@dataclass(frozen=True)
class BandThresholds:
    p70: float
    p85: float
    p95: float


@dataclass(frozen=True)
class BandDecision:
    eligible: bool
    reference_count: int
    thresholds: BandThresholds | None
    raw_band: BandName | None
    published_band: BandName | None
    confirmed_band: BandName | None
    candidate_band: BandName | None
    candidate_count: int


def linear_percentile(values: Sequence[float], percentile: float) -> float:
    """Empirical percentile using linear interpolation between adjacent ranks."""
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= percentile <= 1.0:
        raise ValueError("percentile must be between 0 and 1")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("percentile values must be finite")

    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    weight = position - lower_index
    return ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * weight


def classify_band(value: float, thresholds: BandThresholds) -> BandName:
    """Map a finite composite value onto the owner-approved threshold boundaries."""
    if not math.isfinite(value):
        raise ValueError("band value must be finite")
    if value < thresholds.p70:
        return "Normal"
    if value < thresholds.p85:
        return "Watch"
    if value <= thresholds.p95:
        return "Elevated"
    return "High"


def _thresholds(values: Sequence[float]) -> BandThresholds:
    return BandThresholds(
        p70=canonicalize_float(linear_percentile(values, 0.70)),
        p85=canonicalize_float(linear_percentile(values, 0.85)),
        p95=canonicalize_float(linear_percentile(values, 0.95)),
    )


def evaluate_band(
    prior_tier_a_values: Sequence[float | None],
    previous: BandDecision | None,
    current_tier_a_value: float | None,
) -> BandDecision:
    """Advance burn-in and two-month dwell using frozen history only."""
    numeric_reference = tuple(value for value in prior_tier_a_values if value is not None)
    if any(not math.isfinite(value) for value in numeric_reference):
        raise ValueError("prior Tier-A values must be finite or null")
    if current_tier_a_value is not None and not math.isfinite(current_tier_a_value):
        raise ValueError("current Tier-A value must be finite or null")

    reference_count = len(numeric_reference)
    eligible = len(prior_tier_a_values) + 1 >= 36 and reference_count >= 35
    confirmed = previous.confirmed_band if previous is not None else None
    if not eligible:
        return BandDecision(
            eligible=False,
            reference_count=reference_count,
            thresholds=None,
            raw_band=None,
            published_band=None,
            confirmed_band=confirmed,
            candidate_band=None,
            candidate_count=0,
        )

    thresholds = _thresholds(numeric_reference)
    if current_tier_a_value is None:
        return BandDecision(
            eligible=True,
            reference_count=reference_count,
            thresholds=thresholds,
            raw_band=None,
            published_band=None,
            confirmed_band=confirmed,
            candidate_band=None,
            candidate_count=0,
        )

    raw_band = classify_band(current_tier_a_value, thresholds)
    if raw_band == confirmed:
        return BandDecision(
            eligible=True,
            reference_count=reference_count,
            thresholds=thresholds,
            raw_band=raw_band,
            published_band=confirmed,
            confirmed_band=confirmed,
            candidate_band=None,
            candidate_count=0,
        )

    prior_candidate = previous.candidate_band if previous is not None else None
    prior_count = previous.candidate_count if previous is not None else 0
    candidate_count = prior_count + 1 if prior_candidate == raw_band else 1
    if candidate_count >= 2:
        return BandDecision(
            eligible=True,
            reference_count=reference_count,
            thresholds=thresholds,
            raw_band=raw_band,
            published_band=raw_band,
            confirmed_band=raw_band,
            candidate_band=None,
            candidate_count=0,
        )
    return BandDecision(
        eligible=True,
        reference_count=reference_count,
        thresholds=thresholds,
        raw_band=raw_band,
        published_band=confirmed,
        confirmed_band=confirmed,
        candidate_band=raw_band,
        candidate_count=candidate_count,
    )
