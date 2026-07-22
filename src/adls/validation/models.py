"""Immutable Slice 6 validation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from adls.contracts import ValidationResult

BandName = Literal["Normal", "Watch", "Elevated", "High"]
ScoreStatus = Literal["scored", "signal_abstention", "outcome_abstention"]
PinStatus = Literal["proposed", "approved"]


@dataclass(frozen=True)
class QuarterLevel:
    quarter: str
    level: float


@dataclass(frozen=True)
class OutcomeGap:
    quarter: str
    component_one_gap: float | None
    component_two_gap: float | None
    synthetic_gap: float | None
    event: bool | None
    reason: str | None


@dataclass(frozen=True)
class ScalarForecast:
    values: tuple[float, ...]
    reason: str | None = None


@dataclass(frozen=True)
class VectorForecast:
    vectors: tuple[tuple[float, ...], ...]
    reason: str | None = None


@dataclass(frozen=True)
class FrozenPoint:
    month: str
    tier_a_value: float | None
    published_band: BandName | None
    family_values: tuple[tuple[str, float | None], ...]
    composite_abstained: bool
    flags: tuple[str, ...]
    p70_threshold: float | None = None


@dataclass(frozen=True)
class WeeklyAssemblyRow:
    assembly_date: str
    canonical_month: str | None
    composite_abstained: bool
    tier_a_value: float | None
    flags: tuple[str, ...]


@dataclass(frozen=True)
class ReconstructionResult:
    frozen_bytes: bytes
    points: tuple[FrozenPoint, ...]
    weekly_rows: tuple[WeeklyAssemblyRow, ...]
    validation: ValidationResult
    debt_ids: tuple[str, ...]


@dataclass(frozen=True)
class OutcomeSourceResult:
    vintage: str | None
    components: tuple[tuple[str, tuple[QuarterLevel, ...]], ...]
    validation: ValidationResult


@dataclass(frozen=True)
class ScoreRow:
    month: str
    source: str
    band: BandName | None
    signal: bool | None
    outcome_event: bool | None
    outcome_quarters: tuple[str, str]
    episode_onset: bool
    hit: bool | None
    score_status: ScoreStatus
    reason: str | None
    business_cycle_regime: str = "expansion"
    turning_point_regime: str = "trend"


@dataclass(frozen=True)
class ScoreSummary:
    point_count: int
    scorable_point_count: int
    signal_abstention_count: int
    outcome_abstention_count: int
    signal_episode_count: int
    scored_signal_episode_count: int
    signal_episode_hits: int
    lead_rate: float | None


@dataclass(frozen=True)
class CalibrationRow:
    band: BandName
    count: int
    event_count: int
    event_probability: float | None


@dataclass(frozen=True)
class CalibrationTable:
    rows: tuple[CalibrationRow, ...]
    monotonic: bool | None


@dataclass(frozen=True)
class BaselineContract:
    pin_status: PinStatus
    season_months: int
    ar_lags: int
    var_lags: int
    forecast_months: int
    minimum_months: int
    signal_dwell_months: int
    block_months: int
    embargo_months: int
    trial_count: int
    random_seed: int
    turning_window_months: int

    def __post_init__(self) -> None:
        dimensions = (
            self.season_months,
            self.ar_lags,
            self.var_lags,
            self.forecast_months,
            self.minimum_months,
            self.signal_dwell_months,
            self.block_months,
            self.trial_count,
        )
        if any(value < 1 for value in dimensions):
            raise ValueError("baseline dimensions must be positive")
        if self.embargo_months < 0 or self.turning_window_months < 0:
            raise ValueError("validation windows cannot be negative")
        if self.minimum_months < self.ar_lags + 2:
            raise ValueError("AR lags exceed the minimum fitting history")
        if self.minimum_months < self.var_lags + 2:
            raise ValueError("VAR lags exceed the minimum fitting history")
        if self.minimum_months < self.season_months:
            raise ValueError("season exceeds the minimum fitting history")
        if self.signal_dwell_months > self.forecast_months:
            raise ValueError("signal dwell exceeds the forecast horizon")


@dataclass(frozen=True)
class BaselineOrigin:
    month: str
    model: str
    forecast_values: tuple[float, ...]
    signal: bool | None
    mase: float | None
    reason: str | None
    mase_reason: str | None


@dataclass(frozen=True)
class RegimeSlice:
    dimension: str
    category: str
    summary: ScoreSummary


@dataclass(frozen=True)
class RegimeReport:
    slices: tuple[RegimeSlice, ...]
    macro_average_lead_rates: tuple[tuple[str, float | None], ...]


@dataclass(frozen=True)
class PermutationTrial:
    trial: int
    lead_rate: float | None
    signal_episode_count: int
    status: str


@dataclass(frozen=True)
class PermutationResult:
    observed_lead_rate: float | None
    requested_trials: int
    scored_trials: int
    null_median: float | None
    improvement_over_median: float | None
    rope_met: bool | None
    descriptive_p_value: float | None
    trials: tuple[PermutationTrial, ...]


@dataclass(frozen=True)
class ValidationRunResult:
    artifact_bytes: bytes
    validation: ValidationResult
