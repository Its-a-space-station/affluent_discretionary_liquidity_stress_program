"""Checker-owned data contracts.

These types deliberately do not reuse maker, input-layer, or cache contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VerificationLabel = Literal[
    "Verified",
    "Provisional",
    "Conflicting",
    "Unverified",
    "Stale",
]
BandName = Literal["Normal", "Watch", "Elevated", "High"]


@dataclass(frozen=True)
class CheckerRules:
    """Rule settings, with injectable mutations used by seeded-defect tests."""

    z_ddof: int = 0
    percentile_includes_current: bool = False
    dwell_months: int = 2
    pit_inclusive: bool = True
    staleness_days: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if self.z_ddof < 0:
            raise ValueError("z_ddof cannot be negative")
        if self.dwell_months < 1:
            raise ValueError("dwell_months must be positive")
        names = [series_id for series_id, _ in self.staleness_days]
        if len(names) != len(set(names)):
            raise ValueError("staleness_days cannot repeat a series")
        if any(days < 0 for _, days in self.staleness_days):
            raise ValueError("staleness thresholds cannot be negative")

    def staleness_for(self, series_id: str, default: int) -> int:
        for candidate, days in self.staleness_days:
            if candidate == series_id:
                return days
        return default


@dataclass(frozen=True)
class CheckEvidence:
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class CheckResult:
    label: VerificationLabel
    checks: tuple[CheckEvidence, ...]
    discrepancies: tuple[str, ...]
    debts: tuple[str, ...]
    criteria_version: str = "adls.checker.v1"


@dataclass(frozen=True)
class SeriesRule:
    series_id: str
    family: str
    role: str
    source: str
    frequency: str
    staleness_days: int
    tier: str | None
    transform: str
    license_tag: str
    canonical_date_shift_days: int = 0


@dataclass(frozen=True)
class SourceValue:
    series_id: str
    observation_date: str
    value_text: str
    release_date: str
    available_from: str
    source: str
    source_file: str | None = None
    release_stage: str | None = None
    retrieved_at: str | None = None


@dataclass(frozen=True)
class DatedValue:
    observation_date: str
    value: float


@dataclass(frozen=True)
class FamilyComputation:
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
class AssemblyComputation:
    assembly_date: str
    family_scores: tuple[FamilyComputation, ...]
    tier_a_value: float | None
    tier_b_value: float | None
    headline_value: float | None
    headline_tier: str | None
    composite_abstained: bool
    flags: tuple[str, ...]


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
