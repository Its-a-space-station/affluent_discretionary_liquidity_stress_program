"""Primary lead-rate null from joint time-axis block permutations."""

from __future__ import annotations

import random
import statistics
from collections.abc import Sequence

from .analysis import score_signal_series, summarize_scores
from .models import (
    BaselineContract,
    FrozenPoint,
    OutcomeGap,
    PermutationResult,
    PermutationTrial,
)
from .permutation import joint_block_permutation_indices

ROPE_IMPROVEMENT = 0.15


def evaluate_joint_permutation(
    points: Sequence[FrozenPoint],
    outcomes: Sequence[OutcomeGap],
    contract: BaselineContract,
) -> PermutationResult:
    primary_signals = tuple(
        (point.month, point.published_band, point.composite_abstained) for point in points
    )
    observed_rows = score_signal_series(
        primary_signals,
        outcomes,
        source="primary",
        turning_window_months=contract.turning_window_months,
    )
    observed = summarize_scores(observed_rows)
    rng = random.Random(contract.random_seed)
    trials: list[PermutationTrial] = []
    null_rates: list[float] = []
    for trial_number in range(1, contract.trial_count + 1):
        indices = joint_block_permutation_indices(
            len(points),
            block_size=contract.block_months,
            embargo=contract.embargo_months,
            rng=rng,
        )
        if not indices:
            trials.append(PermutationTrial(trial_number, None, 0, "embargo_abstention"))
            continue
        signals = tuple(
            (
                target.month,
                points[source].published_band,
                points[source].composite_abstained,
            )
            for target, source in zip(points, indices, strict=True)
        )
        rows = score_signal_series(
            signals,
            outcomes,
            source="permuted_primary",
            turning_window_months=contract.turning_window_months,
        )
        summary = summarize_scores(rows)
        status = "scored" if summary.lead_rate is not None else "no_signal_episode"
        trials.append(
            PermutationTrial(
                trial_number,
                summary.lead_rate,
                summary.signal_episode_count,
                status,
            )
        )
        if summary.lead_rate is not None:
            null_rates.append(summary.lead_rate)

    median = statistics.median(null_rates) if null_rates else None
    improvement = (
        observed.lead_rate - median
        if observed.lead_rate is not None and median is not None
        else None
    )
    rope_met = improvement >= ROPE_IMPROVEMENT if improvement is not None else None
    p_value = None
    if observed.lead_rate is not None and null_rates:
        exceedances = sum(value >= observed.lead_rate for value in null_rates)
        p_value = (exceedances + 1) / (len(null_rates) + 1)
    return PermutationResult(
        observed_lead_rate=observed.lead_rate,
        requested_trials=contract.trial_count,
        scored_trials=len(null_rates),
        null_median=median,
        improvement_over_median=improvement,
        rope_met=rope_met,
        descriptive_p_value=p_value,
        trials=tuple(trials),
    )
