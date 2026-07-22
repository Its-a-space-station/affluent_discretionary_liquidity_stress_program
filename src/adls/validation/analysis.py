"""All-row lead-event scoring and calibration summaries."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import (
    BandName,
    CalibrationRow,
    CalibrationTable,
    OutcomeGap,
    ScoreRow,
    ScoreStatus,
    ScoreSummary,
)
from .outcomes import event_within_two_quarters
from .regimes import regime_for_month

BANDS: tuple[BandName, ...] = ("Normal", "Watch", "Elevated", "High")
POSITIVE_BANDS = frozenset({"Watch", "Elevated", "High"})


def score_signal_series(
    signals: Sequence[tuple[str, BandName | None, bool]],
    outcomes: Sequence[OutcomeGap],
    *,
    source: str,
    turning_window_months: int = 6,
) -> tuple[ScoreRow, ...]:
    rows: list[ScoreRow] = []
    previous_signal: bool | None = False
    outcome_index = {item.quarter: item for item in outcomes}
    for month, band, composite_abstained in signals:
        signal = None if composite_abstained or band is None else band in POSITIVE_BANDS
        outcome_event, outcome_reason, quarters = event_within_two_quarters(
            month,
            outcome_index,
        )
        episode_onset = signal is True and previous_signal is not True
        business_cycle, turning_context = regime_for_month(
            month,
            turning_window_months=turning_window_months,
        )
        status: ScoreStatus
        reason: str | None
        hit: bool | None
        if signal is None:
            status = "signal_abstention"
            reason = "composite_abstention" if composite_abstained else "band_unavailable"
            hit = None
        elif outcome_event is None:
            status = "outcome_abstention"
            reason = outcome_reason
            hit = None
        else:
            status = "scored"
            reason = None
            hit = bool(signal and outcome_event)
        rows.append(
            ScoreRow(
                month=month,
                source=source,
                band=band,
                signal=signal,
                outcome_event=outcome_event,
                outcome_quarters=quarters,
                episode_onset=episode_onset,
                hit=hit,
                score_status=status,
                reason=reason,
                business_cycle_regime=business_cycle,
                turning_point_regime=turning_context,
            )
        )
        previous_signal = signal
    return tuple(rows)


def score_binary_signal_series(
    signals: Sequence[tuple[str, bool | None]],
    outcomes: Sequence[OutcomeGap],
    *,
    source: str,
    turning_window_months: int = 6,
) -> tuple[ScoreRow, ...]:
    rows: list[ScoreRow] = []
    previous_signal: bool | None = False
    outcome_index = {item.quarter: item for item in outcomes}
    for month, signal in signals:
        outcome_event, outcome_reason, quarters = event_within_two_quarters(
            month,
            outcome_index,
        )
        episode_onset = signal is True and previous_signal is not True
        business_cycle, turning_context = regime_for_month(
            month,
            turning_window_months=turning_window_months,
        )
        status: ScoreStatus
        reason: str | None
        hit: bool | None
        if signal is None:
            status = "signal_abstention"
            reason = "baseline_abstention"
            hit = None
        elif outcome_event is None:
            status = "outcome_abstention"
            reason = outcome_reason
            hit = None
        else:
            status = "scored"
            reason = None
            hit = bool(signal and outcome_event)
        rows.append(
            ScoreRow(
                month=month,
                source=source,
                band=None,
                signal=signal,
                outcome_event=outcome_event,
                outcome_quarters=quarters,
                episode_onset=episode_onset,
                hit=hit,
                score_status=status,
                reason=reason,
                business_cycle_regime=business_cycle,
                turning_point_regime=turning_context,
            )
        )
        previous_signal = signal
    return tuple(rows)


def summarize_scores(rows: Sequence[ScoreRow]) -> ScoreSummary:
    scorable = tuple(row for row in rows if row.score_status == "scored")
    all_episodes = tuple(row for row in rows if row.episode_onset)
    scored_episodes = tuple(row for row in scorable if row.episode_onset)
    hits = sum(row.hit is True for row in scored_episodes)
    lead_rate = hits / len(scored_episodes) if scored_episodes else None
    return ScoreSummary(
        point_count=len(rows),
        scorable_point_count=len(scorable),
        signal_abstention_count=sum(row.score_status == "signal_abstention" for row in rows),
        outcome_abstention_count=sum(row.score_status == "outcome_abstention" for row in rows),
        signal_episode_count=len(all_episodes),
        scored_signal_episode_count=len(scored_episodes),
        signal_episode_hits=hits,
        lead_rate=lead_rate,
    )


def calibration_table(rows: Sequence[ScoreRow]) -> CalibrationTable:
    calibration_rows: list[CalibrationRow] = []
    probabilities: list[float] = []
    for band in BANDS:
        selected = tuple(
            row
            for row in rows
            if row.band == band and row.outcome_event is not None and row.signal is not None
        )
        events = sum(row.outcome_event is True for row in selected)
        probability = events / len(selected) if selected else None
        calibration_rows.append(CalibrationRow(band, len(selected), events, probability))
        if probability is not None:
            probabilities.append(probability)
    monotonic = (
        None
        if len(probabilities) != len(BANDS)
        else all(
            later >= earlier or math.isclose(later, earlier)
            for earlier, later in zip(probabilities, probabilities[1:], strict=False)
        )
    )
    return CalibrationTable(tuple(calibration_rows), monotonic)
