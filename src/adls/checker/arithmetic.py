"""Independent transforms, standardization, and composite arithmetic."""

from __future__ import annotations

import math
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from .constants import FAMILY_SEQUENCE, LEADING_FAMILIES, TIER_A_FAMILIES, rules_for_family
from .models import (
    AssemblyComputation,
    CheckerRules,
    DatedValue,
    FamilyComputation,
    SeriesRule,
    SourceValue,
)
from .sources import EvidenceConflict


def _iso_date(text: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceConflict(f"{field} is not an ISO date: {text!r}") from exc
    if parsed.isoformat() != text:
        raise EvidenceConflict(f"{field} is not a canonical ISO date: {text!r}")
    return parsed


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _month_wednesdays(year: int, month: int) -> set[date]:
    first = date(year, month, 1)
    current = first + timedelta(days=(2 - first.weekday()) % 7)
    result: set[date] = set()
    while current.month == month:
        result.add(current)
        current += timedelta(days=7)
    return result


def _numeric_rows(
    rule: SeriesRule,
    history: tuple[SourceValue, ...],
    assembly: date,
) -> tuple[tuple[date, float], ...]:
    rows: list[tuple[date, float]] = []
    prior_observation: date | None = None
    seen: set[date] = set()
    latest_observation: date | None = None
    latest_numeric = True
    for position, value in enumerate(history, 1):
        if value.series_id != rule.series_id or value.source != rule.source:
            raise EvidenceConflict(f"{rule.series_id} row {position} has contradictory identity")
        observation = _iso_date(
            value.observation_date,
            f"{rule.series_id} observation_date",
        )
        release = _iso_date(value.release_date, f"{rule.series_id} release_date")
        available_from = _iso_date(
            value.available_from,
            f"{rule.series_id} available_from",
        )
        if prior_observation is not None and observation < prior_observation:
            raise EvidenceConflict(f"{rule.series_id} history is not sorted")
        prior_observation = observation
        if observation in seen:
            raise EvidenceConflict(
                f"{rule.series_id} repeats observation {observation.isoformat()}"
            )
        seen.add(observation)
        if release < observation:
            raise EvidenceConflict(f"{rule.series_id} release precedes observation")
        if release > assembly or available_from > assembly:
            raise EvidenceConflict(f"{rule.series_id} contains future information")
        if available_from < release:
            raise EvidenceConflict(f"{rule.series_id} availability precedes release")
        if rule.source == "archive" and value.release_stage != "final":
            raise EvidenceConflict(f"{rule.series_id} canonical history is not final-only")

        latest_observation = observation
        if value.value_text == ".":
            latest_numeric = False
            continue
        try:
            parsed = Decimal(value.value_text)
        except InvalidOperation as exc:
            raise EvidenceConflict(
                f"{rule.series_id} has invalid numeric value {value.value_text!r}"
            ) from exc
        if not parsed.is_finite():
            raise EvidenceConflict(f"{rule.series_id} has a non-finite value")
        try:
            numeric_value = float(parsed)
        except (OverflowError, ValueError) as exc:
            raise EvidenceConflict(f"{rule.series_id} value is outside float range") from exc
        if not math.isfinite(numeric_value):
            raise EvidenceConflict(f"{rule.series_id} value is outside float range")
        rows.append((observation, numeric_value))
        latest_numeric = True
    if latest_observation is not None and not latest_numeric:
        raise EvidenceConflict(f"{rule.series_id} latest observation is not numeric")
    return tuple(rows)


def _monthly_values(
    rule: SeriesRule,
    history: tuple[SourceValue, ...],
    assembly: date,
) -> tuple[DatedValue, ...]:
    rows = _numeric_rows(rule, history, assembly)
    if rule.frequency in {"m", "q"}:
        points: list[DatedValue] = []
        for observation, value in rows:
            if observation.day != 1:
                raise EvidenceConflict(f"{rule.series_id} observation is not on a month boundary")
            if rule.frequency == "q" and observation.month not in {1, 4, 7, 10}:
                raise EvidenceConflict(f"{rule.series_id} has a non-quarter observation")
            points.append(DatedValue(observation.isoformat(), value))
        return tuple(points)
    if rule.frequency != "w":
        raise EvidenceConflict(f"{rule.series_id} has unsupported frequency")

    grouped: dict[tuple[int, int], list[tuple[date, float]]] = {}
    for observation, value in rows:
        canonical = observation + timedelta(days=rule.canonical_date_shift_days)
        if canonical.weekday() != 2:
            raise EvidenceConflict(f"{rule.series_id} canonical weekly date is not Wednesday")
        grouped.setdefault((canonical.year, canonical.month), []).append((canonical, value))

    points = []
    for year, month in sorted(grouped):
        month_rows = grouped[(year, month)]
        observed = {day for day, _ in month_rows}
        expected = _month_wednesdays(year, month)
        last_wednesday = date(year, month, monthrange(year, month)[1])
        last_wednesday -= timedelta(days=(last_wednesday.weekday() - 2) % 7)
        if last_wednesday not in observed or observed != expected:
            continue
        points.append(
            DatedValue(
                date(year, month, 1).isoformat(),
                math.fsum(value for _, value in month_rows) / len(month_rows),
            )
        )
    return tuple(points)


def _yoy(
    points: tuple[DatedValue, ...],
    series_id: str,
) -> tuple[DatedValue, ...]:
    by_date = {date.fromisoformat(point.observation_date): point.value for point in points}
    result: list[DatedValue] = []
    for point in points:
        current_date = date.fromisoformat(point.observation_date)
        prior_date = _add_months(current_date, -12)
        if prior_date not in by_date:
            continue
        denominator = by_date[prior_date]
        if denominator == 0:
            raise EvidenceConflict(f"{series_id} has a zero YoY denominator")
        result.append(
            DatedValue(point.observation_date, (point.value - denominator) / denominator)
        )
    return tuple(result)


def _single_transform(
    rule: SeriesRule,
    history: tuple[SourceValue, ...],
    assembly: date,
) -> tuple[DatedValue, ...]:
    points = _monthly_values(rule, history, assembly)
    if rule.transform == "hundred_minus_level":
        return tuple(DatedValue(point.observation_date, 100.0 - point.value) for point in points)
    if rule.transform == "inverted_level":
        return tuple(DatedValue(point.observation_date, -point.value) for point in points)
    if rule.transform == "level":
        return points
    if rule.transform == "yoy_growth":
        return _yoy(points, rule.series_id)
    raise EvidenceConflict(f"{rule.series_id} has unsupported single-series transform")


def _pooled_transform(
    family_rules: tuple[SeriesRule, ...],
    histories: dict[str, tuple[SourceValue, ...]],
    assembly: date,
) -> tuple[DatedValue, ...]:
    monthly = {
        rule.series_id: {
            date.fromisoformat(point.observation_date): point.value
            for point in _monthly_values(rule, histories[rule.series_id], assembly)
        }
        for rule in family_rules
    }
    common_dates = set.intersection(*(set(values) for values in monthly.values()))
    result: list[DatedValue] = []
    for current_date in sorted(common_dates):
        prior_date = _add_months(current_date, -12)
        if any(prior_date not in values for values in monthly.values()):
            continue
        prior_total = math.fsum(values[prior_date] for values in monthly.values())
        if prior_total == 0:
            raise EvidenceConflict("pooled family has a zero YoY denominator")
        change = math.fsum(
            values[current_date] - values[prior_date] for values in monthly.values()
        )
        result.append(DatedValue(current_date.isoformat(), -(change / prior_total)))
    return tuple(result)


def _trailing_z(
    points: tuple[DatedValue, ...],
    minimum: int,
    rules: CheckerRules,
) -> tuple[float | None, str | None]:
    if not points:
        return None, "no_transformed_observations"
    current = points[-1]
    current_date = date.fromisoformat(current.observation_date)
    cutoff = _add_months(current_date, -120)
    references = [
        point.value
        for point in points[:-1]
        if cutoff <= date.fromisoformat(point.observation_date) < current_date
    ]
    count = len(references)
    if count < minimum:
        return None, f"insufficient_history:{count}<{minimum}"
    denominator = count - rules.z_ddof
    if denominator <= 0:
        return None, "invalid_variance_denominator"
    mean = math.fsum(references) / count
    variance = math.fsum((value - mean) ** 2 for value in references) / denominator
    if variance == 0:
        return None, "zero_population_sigma"
    uncapped = (current.value - mean) / math.sqrt(variance)
    return max(-3.0, min(3.0, uncapped)), None


def _abstained_family(
    family: str,
    family_rules: tuple[SeriesRule, ...],
    releases: tuple[tuple[str, str], ...],
    flags: tuple[str, ...],
) -> FamilyComputation:
    return FamilyComputation(
        family=family,
        role=family_rules[0].role,
        tier=family_rules[0].tier,
        member_series_ids=tuple(rule.series_id for rule in family_rules),
        member_release_dates=releases,
        observation_date=None,
        transformed_value=None,
        z_score=None,
        component_z_scores=(),
        abstained=True,
        flags=flags,
    )


def _family_inputs(
    family: str,
    family_rules: tuple[SeriesRule, ...],
    all_histories: dict[str, tuple[SourceValue, ...]],
    assembly: date,
    checker_rules: CheckerRules,
) -> tuple[
    dict[str, tuple[SourceValue, ...]],
    tuple[tuple[str, str], ...],
    tuple[str, ...],
]:
    histories: dict[str, tuple[SourceValue, ...]] = {}
    releases: list[tuple[str, str]] = []
    flags: list[str] = []
    for rule in family_rules:
        history = all_histories.get(rule.series_id, ())
        if not history:
            flags.append(f"missing_member:{rule.series_id}")
            continue
        # Full row validation is part of the independent arithmetic path.
        _numeric_rows(rule, history, assembly)
        histories[rule.series_id] = history
        release_dates = [
            _iso_date(value.release_date, f"{rule.series_id} release_date") for value in history
        ]
        latest_release = max(release_dates)
        releases.append((rule.series_id, latest_release.isoformat()))
        age_days = (assembly - latest_release).days
        if age_days < 0:
            raise EvidenceConflict(f"{rule.series_id} latest release is in the future")
        threshold = checker_rules.staleness_for(rule.series_id, rule.staleness_days)
        if age_days > threshold:
            flags.append(f"stale_member:{rule.series_id}")
    return histories, tuple(releases), tuple(flags)


def _score_leading(
    family: str,
    all_histories: dict[str, tuple[SourceValue, ...]],
    assembly: date,
    checker_rules: CheckerRules,
) -> FamilyComputation:
    family_rules = rules_for_family(family)
    histories, releases, flags = _family_inputs(
        family,
        family_rules,
        all_histories,
        assembly,
        checker_rules,
    )
    if flags:
        return _abstained_family(family, family_rules, releases, flags)
    transformed = (
        _pooled_transform(family_rules, histories, assembly)
        if len(family_rules) > 1
        else _single_transform(family_rules[0], histories[family_rules[0].series_id], assembly)
    )
    z_score, reason = _trailing_z(transformed, 36, checker_rules)
    if z_score is None:
        return _abstained_family(
            family,
            family_rules,
            releases,
            (f"z_abstention:{reason}",),
        )
    return FamilyComputation(
        family=family,
        role="leading",
        tier=family_rules[0].tier,
        member_series_ids=tuple(rule.series_id for rule in family_rules),
        member_release_dates=releases,
        observation_date=transformed[-1].observation_date,
        transformed_value=transformed[-1].value,
        z_score=z_score,
        component_z_scores=(),
        abstained=False,
        flags=(),
    )


def _score_strain(
    all_histories: dict[str, tuple[SourceValue, ...]],
    assembly: date,
    checker_rules: CheckerRules,
) -> FamilyComputation:
    family_rules = rules_for_family("strain")
    histories, releases, flags = _family_inputs(
        "strain",
        family_rules,
        all_histories,
        assembly,
        checker_rules,
    )
    if flags:
        return _abstained_family("strain", family_rules, releases, flags)

    scores: list[tuple[str, float]] = []
    observations: list[str] = []
    score_flags: list[str] = []
    for rule in family_rules:
        transformed = _single_transform(rule, histories[rule.series_id], assembly)
        minimum = 20 if rule.frequency == "q" else 36
        z_score, reason = _trailing_z(transformed, minimum, checker_rules)
        if z_score is None:
            score_flags.append(f"z_abstention:{rule.series_id}:{reason}")
            continue
        scores.append((rule.series_id, z_score))
        observations.append(transformed[-1].observation_date)
    if score_flags or len(scores) != len(family_rules):
        return _abstained_family("strain", family_rules, releases, tuple(score_flags))
    return FamilyComputation(
        family="strain",
        role="overlay",
        tier=None,
        member_series_ids=tuple(rule.series_id for rule in family_rules),
        member_release_dates=releases,
        observation_date=max(observations),
        transformed_value=None,
        z_score=math.fsum(value for _, value in scores) / len(scores),
        component_z_scores=tuple(scores),
        abstained=False,
        flags=(),
    )


def compute_assembly(
    assembly_date: str,
    histories: dict[str, tuple[SourceValue, ...]],
    rules: CheckerRules,
) -> AssemblyComputation:
    """Recompute one canonical assembly without calling maker code."""
    assembly = _iso_date(assembly_date, "assembly_date")
    family_scores = tuple(
        _score_strain(histories, assembly, rules)
        if family == "strain"
        else _score_leading(family, histories, assembly, rules)
        for family in FAMILY_SEQUENCE
    )
    leading = [score for score in family_scores if score.family in LEADING_FAMILIES]
    abstained = [score.family for score in leading if score.abstained]
    flags = [f"family_abstention:{family}" for family in abstained]
    if len(abstained) >= 2:
        flags.append(f"leading_abstained:{len(abstained)}_of_4_families")
        return AssemblyComputation(
            assembly_date=assembly_date,
            family_scores=family_scores,
            tier_a_value=None,
            tier_b_value=None,
            headline_value=None,
            headline_tier=None,
            composite_abstained=True,
            flags=tuple(flags),
        )

    available = [score for score in leading if not score.abstained and score.z_score is not None]
    tier_a_scores = [
        score.z_score
        for score in available
        if score.family in TIER_A_FAMILIES and score.z_score is not None
    ]
    tier_a = math.fsum(tier_a_scores) / len(tier_a_scores) if tier_a_scores else None
    visa_available = any(score.family == "visa_smi" for score in available)
    tier_b = (
        math.fsum(score.z_score for score in available if score.z_score is not None)
        / len(available)
        if visa_available
        else None
    )
    if abstained:
        flags.append(f"leading_renormalized:{','.join(abstained)}")
    return AssemblyComputation(
        assembly_date=assembly_date,
        family_scores=family_scores,
        tier_a_value=tier_a,
        tier_b_value=tier_b,
        headline_value=tier_b if visa_available else tier_a,
        headline_tier="B" if visa_available else "A",
        composite_abstained=False,
        flags=tuple(flags),
    )
