"""Immutable values produced inside the Slice 3 maker engine."""

from __future__ import annotations

from dataclasses import dataclass

from adls.contracts import ValidationResult


@dataclass(frozen=True)
class DatedValue:
    observation_date: str
    value: float


@dataclass(frozen=True)
class ZScoreResult:
    value: float | None
    uncapped_value: float | None
    reference_count: int
    reason: str | None = None


@dataclass(frozen=True)
class FreshnessResult:
    series_id: str
    latest_release_date: str | None
    age_days: int | None
    stale: bool
    reason: str | None = None


@dataclass(frozen=True)
class FamilyScore:
    family: str
    role: str
    tier: str | None
    member_series_ids: tuple[str, ...]
    member_release_dates: tuple[tuple[str, str], ...]
    observation_date: str | None
    transformed_value: float | None
    z_score: float | None
    component_z_scores: tuple[tuple[str, float], ...]
    abstained: bool
    flags: tuple[str, ...]


@dataclass(frozen=True)
class AssemblyResult:
    assembly_date: str
    provisional: bool
    family_scores: tuple[FamilyScore, ...]
    tier_a_value: float | None
    tier_b_value: float | None
    headline_value: float | None
    headline_tier: str | None
    composite_abstained: bool
    flags: tuple[str, ...]
    validation: ValidationResult
