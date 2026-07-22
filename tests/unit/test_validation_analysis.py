from __future__ import annotations

import random

from adls.validation.analysis import calibration_table, score_signal_series, summarize_scores
from adls.validation.models import FrozenPoint, OutcomeGap
from adls.validation.permutation import joint_block_permutation_indices


def _month_at(year: int, month: int, offset: int) -> str:
    index = year * 12 + month - 1 + offset
    result_year, zero_based_month = divmod(index, 12)
    return f"{result_year:04d}-{zero_based_month + 1:02d}"


def _outcome(quarter: str, event: bool | None) -> OutcomeGap:
    value = -3.0 if event else 0.0
    return OutcomeGap(
        quarter=quarter,
        component_one_gap=value if event is not None else None,
        component_two_gap=value if event is not None else None,
        synthetic_gap=value if event is not None else None,
        event=event,
        reason=None if event is not None else "missing_component",
    )


def test_score_every_point_retains_burn_in_tail_and_signal_abstentions() -> None:
    signals = (
        ("2019-12", None, None),
        ("2020-01", "Normal", False),
        ("2020-02", "Watch", False),
        ("2020-03", "Watch", False),
        ("2020-04", None, True),
        ("2020-05", "Normal", False),
    )
    outcomes = (
        _outcome("2020-Q1", False),
        _outcome("2020-Q2", True),
        _outcome("2020-Q3", False),
        _outcome("2020-Q4", None),
    )

    rows = score_signal_series(signals, outcomes, source="primary")
    summary = summarize_scores(rows)

    assert len(rows) == len(signals)
    assert rows[0].signal is None
    assert rows[0].score_status == "signal_abstention"
    assert rows[2].episode_onset is True
    assert rows[3].episode_onset is False
    assert rows[4].signal is None
    assert rows[4].score_status == "signal_abstention"
    assert summary.point_count == len(signals)
    assert summary.signal_episode_count == 1
    assert summary.scored_signal_episode_count == 1
    assert summary.signal_episode_hits == 1
    assert summary.lead_rate == 1.0


def test_calibration_reports_empty_bands_and_monotonicity_without_hiding_counts() -> None:
    signals = (
        ("2019-01", "Normal", False),
        ("2019-02", "Normal", False),
        ("2019-03", "Watch", False),
        ("2019-04", "Elevated", False),
        ("2019-05", "High", False),
    )
    outcomes = (
        _outcome("2019-Q2", False),
        _outcome("2019-Q3", True),
        _outcome("2019-Q4", True),
        _outcome("2020-Q1", False),
    )
    rows = score_signal_series(signals, outcomes, source="primary")

    result = calibration_table(rows)

    assert tuple(item.band for item in result.rows) == (
        "Normal",
        "Watch",
        "Elevated",
        "High",
    )
    assert sum(item.count for item in result.rows) <= len(rows)
    assert result.monotonic is not None


def test_joint_block_permutation_is_bijective_deterministic_joint_and_embargoed() -> None:
    length = 72
    first = joint_block_permutation_indices(
        length,
        block_size=12,
        embargo=12,
        rng=random.Random(41),
    )
    second = joint_block_permutation_indices(
        length,
        block_size=12,
        embargo=12,
        rng=random.Random(41),
    )

    assert first == second
    assert sorted(first) == list(range(length))
    for target, source in enumerate(first):
        circular_distance = min((target - source) % length, (source - target) % length)
        assert circular_distance > 12

    points = tuple(
        FrozenPoint(
            month=_month_at(2015, 1, index),
            tier_a_value=float(index),
            published_band="Watch" if index % 5 == 0 else "Normal",
            family_values=(("a", float(index)), ("b", float(index + 1))),
            composite_abstained=False,
            flags=(),
        )
        for index in range(length)
    )
    permuted = tuple(points[source] for source in first)
    for point in permuted:
        assert dict(point.family_values)["b"] == dict(point.family_values)["a"] + 1.0


def test_joint_block_permutation_fails_closed_when_embargo_is_impossible() -> None:
    assert (
        joint_block_permutation_indices(
            24,
            block_size=12,
            embargo=12,
            rng=random.Random(1),
        )
        == ()
    )
