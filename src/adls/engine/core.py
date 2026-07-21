"""Single-assembly deterministic maker for composite spec sections 3-5 and 7."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta

from adls.contracts import PointInTimeResult, PointInTimeValue, ValidationResult
from adls.engine.models import AssemblyResult, FamilyScore, FreshnessResult
from adls.engine.transforms import (
    evaluate_freshness,
    trailing_z,
    transform_history,
    transform_pooled_history,
)
from adls.registry import LEADING_FAMILIES, REGISTRY, SeriesSpec

FAMILY_SEQUENCE: tuple[str, ...] = (*LEADING_FAMILIES, "strain")
ENGINE_SPECS: tuple[SeriesSpec, ...] = tuple(
    spec for spec in REGISTRY if spec.role in {"leading", "overlay"}
)


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


def _specs_for_family(family: str) -> tuple[SeriesSpec, ...]:
    return tuple(spec for spec in ENGINE_SPECS if spec.family == family)


def _parse_utc_timestamp(
    text: str,
    series_id: str,
    validation: ValidationResult,
) -> date | None:
    candidate = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        validation.error(f"{series_id} retrieved_at must be a canonical UTC timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        validation.error(f"{series_id} retrieved_at must be a canonical UTC timestamp")
        return None
    utc_value = parsed.astimezone(UTC)
    timespec = "microseconds" if utc_value.microsecond else "seconds"
    canonical = utc_value.isoformat(timespec=timespec).replace("+00:00", "Z")
    if canonical != text:
        validation.error(f"{series_id} retrieved_at must be a canonical UTC timestamp")
        return None
    return utc_value.date()


def _validate_snapshot(
    spec: SeriesSpec,
    result: PointInTimeResult,
    assembly: date,
    provisional: bool,
    validation: ValidationResult,
) -> tuple[PointInTimeValue, ...]:
    error_count = len(validation.errors)
    validation.extend(result.validation)
    prior_observation: date | None = None
    seen_observations: set[date] = set()

    for position, value in enumerate(result.values, 1):
        if value.series_id != spec.series_id:
            validation.error(
                f"{spec.series_id} snapshot row {position} carries series_id {value.series_id!r}"
            )
        if value.source != spec.source:
            validation.error(
                f"{spec.series_id} snapshot row {position} has source {value.source!r}, "
                f"expected {spec.source!r}"
            )
        observation = _parse_date(
            value.observation_date,
            f"{spec.series_id} observation_date",
            validation,
        )
        release = _parse_date(value.release_date, f"{spec.series_id} release_date", validation)
        available_from = _parse_date(
            value.available_from,
            f"{spec.series_id} available_from",
            validation,
        )
        available_through = _parse_date(
            value.available_through,
            f"{spec.series_id} available_through",
            validation,
        )
        if observation is not None:
            if prior_observation is not None and observation < prior_observation:
                validation.error(f"{spec.series_id} snapshot is not sorted by observation_date")
            prior_observation = observation
            if observation in seen_observations:
                validation.error(
                    f"{spec.series_id} snapshot has duplicate observation_date "
                    f"{observation.isoformat()}"
                )
            seen_observations.add(observation)
        if observation is not None and release is not None and release < observation:
            validation.error(
                f"{spec.series_id} release {release.isoformat()} precedes observation "
                f"{observation.isoformat()}"
            )
        if release is not None and release > assembly:
            validation.error(
                f"{spec.series_id} release {release.isoformat()} is after assembly "
                f"{assembly.isoformat()}"
            )
        if available_from is not None and available_from > assembly:
            validation.error(
                f"{spec.series_id} value is unavailable at assembly {assembly.isoformat()}"
            )
        if available_through is not None and available_through != assembly:
            validation.error(
                f"{spec.series_id} available_through {available_through.isoformat()} does not "
                f"match assembly {assembly.isoformat()}"
            )
        if release is not None and available_from is not None and available_from < release:
            validation.error(
                f"{spec.series_id} available_from {available_from.isoformat()} precedes release "
                f"{release.isoformat()}"
            )
        if spec.source == "archive":
            if value.release_stage is None:
                validation.error(f"{spec.series_id} archive row has no release_stage")
            elif spec.license == "umich_internal":
                allowed_stages = {"preliminary", "final"} if provisional else {"final"}
                if value.release_stage not in allowed_stages:
                    mode = "provisional" if provisional else "canonical"
                    validation.error(
                        f"{spec.series_id} stage {value.release_stage!r} is invalid for {mode} "
                        "assembly"
                    )
            if value.retrieved_at is None:
                validation.error(f"{spec.series_id} archive row has no retrieved_at")
            else:
                retrieval_date = _parse_utc_timestamp(
                    value.retrieved_at,
                    spec.series_id,
                    validation,
                )
                if release is not None and retrieval_date is not None:
                    if release > retrieval_date:
                        validation.error(
                            f"{spec.series_id} release {release.isoformat()} is after retrieval "
                            f"{retrieval_date.isoformat()}"
                        )
                    effective_date = max(release, retrieval_date)
                    if available_from is not None and available_from != effective_date:
                        validation.error(
                            f"{spec.series_id} available_from {available_from.isoformat()} does "
                            f"not match effective availability {effective_date.isoformat()}"
                        )

    if len(validation.errors) > error_count:
        return ()
    return result.values


def _abstained_family(
    family: str,
    specs: Sequence[SeriesSpec],
    freshness: Sequence[FreshnessResult],
    flags: Sequence[str],
) -> FamilyScore:
    releases = tuple(
        (item.series_id, item.latest_release_date)
        for item in freshness
        if item.latest_release_date is not None
    )
    return FamilyScore(
        family=family,
        role=specs[0].role,
        tier=specs[0].tier,
        member_series_ids=tuple(spec.series_id for spec in specs),
        member_release_dates=releases,
        observation_date=None,
        transformed_value=None,
        z_score=None,
        component_z_scores=(),
        abstained=True,
        flags=tuple(flags),
    )


def _family_inputs(
    family: str,
    specs: Sequence[SeriesSpec],
    inputs: Mapping[str, PointInTimeResult],
    assembly: date,
    provisional: bool,
    validation: ValidationResult,
) -> tuple[
    dict[str, tuple[PointInTimeValue, ...]],
    tuple[FreshnessResult, ...],
    tuple[str, ...],
]:
    histories: dict[str, tuple[PointInTimeValue, ...]] = {}
    freshness: list[FreshnessResult] = []
    flags: list[str] = []
    for spec in specs:
        result = inputs.get(spec.series_id)
        if result is None:
            flag = f"missing_member:{spec.series_id}"
            flags.append(flag)
            validation.warn(f"{family} abstains: {flag}")
            freshness.append(FreshnessResult(spec.series_id, None, None, True, "missing_history"))
            continue
        if not result.values:
            validation.extend(result.validation)
            prefix = "invalid_member" if not result.validation.ok else "missing_member"
            flag = f"{prefix}:{spec.series_id}"
            flags.append(flag)
            validation.warn(f"{family} abstains: {flag}")
            freshness.append(
                FreshnessResult(
                    spec.series_id,
                    None,
                    None,
                    True,
                    "invalid_snapshot" if not result.validation.ok else "missing_history",
                )
            )
            continue
        error_count = len(validation.errors)
        history = _validate_snapshot(spec, result, assembly, provisional, validation)
        if not history:
            flag = f"invalid_member:{spec.series_id}"
            flags.append(flag)
            if len(validation.errors) == error_count:
                validation.error(f"{family} has no valid snapshot for {spec.series_id}")
            freshness.append(FreshnessResult(spec.series_id, None, None, True, "invalid_snapshot"))
            continue
        histories[spec.series_id] = history
        member_freshness = evaluate_freshness(
            spec,
            history,
            assembly.isoformat(),
            validation,
        )
        freshness.append(member_freshness)
        if member_freshness.stale:
            flag = f"stale_member:{spec.series_id}"
            flags.append(flag)
            validation.warn(f"{family} abstains: {flag} ({member_freshness.reason})")
    return histories, tuple(freshness), tuple(flags)


def _score_leading_family(
    family: str,
    specs: Sequence[SeriesSpec],
    inputs: Mapping[str, PointInTimeResult],
    assembly: date,
    provisional: bool,
    validation: ValidationResult,
) -> FamilyScore:
    histories, freshness, flags = _family_inputs(
        family,
        specs,
        inputs,
        assembly,
        provisional,
        validation,
    )
    if flags:
        return _abstained_family(family, specs, freshness, flags)

    error_count = len(validation.errors)
    if len(specs) > 1:
        transformed = transform_pooled_history(specs, histories, validation)
    else:
        spec = specs[0]
        transformed = transform_history(spec, histories[spec.series_id], validation)
    if len(validation.errors) > error_count:
        flag = "invalid_transform"
        validation.warn(f"{family} abstains: {flag}")
        return _abstained_family(family, specs, freshness, (flag,))

    z_score = trailing_z(transformed, window_months=120, min_observations=36)
    if z_score.value is None:
        flag = f"z_abstention:{z_score.reason}"
        validation.warn(f"{family} abstains: {flag}")
        return _abstained_family(family, specs, freshness, (flag,))

    return FamilyScore(
        family=family,
        role="leading",
        tier=specs[0].tier,
        member_series_ids=tuple(spec.series_id for spec in specs),
        member_release_dates=tuple(
            (item.series_id, item.latest_release_date)
            for item in freshness
            if item.latest_release_date is not None
        ),
        observation_date=transformed[-1].observation_date,
        transformed_value=transformed[-1].value,
        z_score=z_score.value,
        component_z_scores=(),
        abstained=False,
        flags=(),
    )


def _score_strain(
    specs: Sequence[SeriesSpec],
    inputs: Mapping[str, PointInTimeResult],
    assembly: date,
    provisional: bool,
    validation: ValidationResult,
) -> FamilyScore:
    histories, freshness, flags = _family_inputs(
        "strain",
        specs,
        inputs,
        assembly,
        provisional,
        validation,
    )
    if flags:
        return _abstained_family("strain", specs, freshness, flags)

    component_scores: list[tuple[str, float]] = []
    component_dates: list[str] = []
    component_flags: list[str] = []
    for spec in specs:
        error_count = len(validation.errors)
        transformed = transform_history(spec, histories[spec.series_id], validation)
        if len(validation.errors) > error_count:
            component_flags.append(f"invalid_transform:{spec.series_id}")
            continue
        minimum = 20 if spec.frequency == "q" else 36
        z_score = trailing_z(transformed, window_months=120, min_observations=minimum)
        if z_score.value is None:
            component_flags.append(f"z_abstention:{spec.series_id}:{z_score.reason}")
            continue
        component_scores.append((spec.series_id, z_score.value))
        component_dates.append(transformed[-1].observation_date)

    if component_flags or len(component_scores) != len(specs):
        for flag in component_flags:
            validation.warn(f"strain abstains: {flag}")
        return _abstained_family("strain", specs, freshness, component_flags)

    return FamilyScore(
        family="strain",
        role="overlay",
        tier=None,
        member_series_ids=tuple(spec.series_id for spec in specs),
        member_release_dates=tuple(
            (item.series_id, item.latest_release_date)
            for item in freshness
            if item.latest_release_date is not None
        ),
        observation_date=max(component_dates),
        transformed_value=None,
        z_score=math.fsum(score for _, score in component_scores) / len(component_scores),
        component_z_scores=tuple(component_scores),
        abstained=False,
        flags=(),
    )


def assemble(
    assembly_date: str,
    inputs: Mapping[str, PointInTimeResult],
    *,
    provisional: bool = False,
) -> AssemblyResult:
    """Compute one deterministic point-in-time assembly from Slice 2 snapshots."""
    validation = ValidationResult()
    assembly = _parse_date(assembly_date, "assembly date", validation)
    if assembly is None:
        return AssemblyResult(
            assembly_date=assembly_date,
            provisional=provisional,
            family_scores=(),
            tier_a_value=None,
            tier_b_value=None,
            headline_value=None,
            headline_tier=None,
            composite_abstained=True,
            flags=("invalid_assembly_date",),
            validation=validation,
        )

    expected_series = {spec.series_id for spec in ENGINE_SPECS}
    for series_id in sorted(set(inputs) - expected_series):
        validation.warn(f"ignored non-engine input {series_id!r}")

    family_scores: list[FamilyScore] = []
    for family in FAMILY_SEQUENCE:
        specs = _specs_for_family(family)
        if family == "strain":
            family_scores.append(_score_strain(specs, inputs, assembly, provisional, validation))
        else:
            family_scores.append(
                _score_leading_family(
                    family,
                    specs,
                    inputs,
                    assembly,
                    provisional,
                    validation,
                )
            )

    leading = [score for score in family_scores if score.role == "leading"]
    abstained = [score.family for score in leading if score.abstained]
    flags = [f"family_abstention:{family}" for family in abstained]
    if len(abstained) >= 2:
        flags.append(f"leading_abstained:{len(abstained)}_of_4_families")
        return AssemblyResult(
            assembly_date=assembly_date,
            provisional=provisional,
            family_scores=tuple(family_scores),
            tier_a_value=None,
            tier_b_value=None,
            headline_value=None,
            headline_tier=None,
            composite_abstained=True,
            flags=tuple(flags),
            validation=validation,
        )

    available = [score for score in leading if not score.abstained and score.z_score is not None]
    tier_a_scores = [
        score.z_score for score in available if score.tier == "A" and score.z_score is not None
    ]
    visa_available = any(score.family == "visa_smi" for score in available)
    tier_a_value = math.fsum(tier_a_scores) / len(tier_a_scores) if tier_a_scores else None
    tier_b_value = (
        math.fsum(score.z_score for score in available if score.z_score is not None)
        / len(available)
        if visa_available
        else None
    )
    if abstained:
        flags.append(f"leading_renormalized:{','.join(abstained)}")
    headline_tier = "B" if visa_available else "A"
    headline_value = tier_b_value if visa_available else tier_a_value
    return AssemblyResult(
        assembly_date=assembly_date,
        provisional=provisional,
        family_scores=tuple(family_scores),
        tier_a_value=tier_a_value,
        tier_b_value=tier_b_value,
        headline_value=headline_value,
        headline_tier=headline_tier,
        composite_abstained=False,
        flags=tuple(flags),
        validation=validation,
    )
