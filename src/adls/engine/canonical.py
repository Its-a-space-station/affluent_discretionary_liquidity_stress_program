"""Append-only canonical-month store built from validated maker assemblies."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from adls.calendarutil import monthly_finalization_date
from adls.contracts import ValidationResult
from adls.engine.bands import (
    BandDecision,
    BandName,
    BandThresholds,
    classify_band,
    evaluate_band,
)
from adls.engine.models import AssemblyResult
from adls.engine.serialize import (
    JsonValue,
    canonical_json_bytes,
    canonicalize_float,
    serialize_assembly,
)
from adls.registry import LEADING_FAMILIES, by_id

SCHEMA_VERSION = "adls.frozen.month.v1"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
LICENSE_NOTICES = {
    "public": "Fed/Census inputs: public domain; cite by series ID",
    "visa_citation": "Visa SMI: cite Visa via FRED",
    "umich_internal": "UMich Table 2n: internal use only",
}
_THREAD_LOCKS: dict[Path, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class FrozenFamily:
    z_score: float | None
    abstained: bool
    flags: tuple[str, ...]


@dataclass(frozen=True)
class FrozenRecord:
    month: str
    finalized_on: str
    source_assembly_sha256: str
    source_assembly_json: str
    tier_a_value: float | None
    tier_b_value: float | None
    tier_b_mapped_band: BandName | None
    headline_value: float | None
    headline_tier: str | None
    composite_abstained: bool
    assembly_flags: tuple[str, ...]
    families: tuple[tuple[str, FrozenFamily], ...]
    input_vintages: tuple[tuple[str, str], ...]
    license_notices: tuple[str, ...]
    band: BandDecision


@dataclass(frozen=True)
class FrozenSequenceResult:
    records: tuple[FrozenRecord, ...]
    validation: ValidationResult


@dataclass(frozen=True)
class FreezeResult:
    appended: bool
    record: FrozenRecord | None
    validation: ValidationResult


def _optional_canonical_float(value: float | None) -> float | None:
    return None if value is None else canonicalize_float(value)


def _canonical_band(decision: BandDecision) -> BandDecision:
    thresholds = decision.thresholds
    canonical_thresholds = (
        None
        if thresholds is None
        else BandThresholds(
            canonicalize_float(thresholds.p70),
            canonicalize_float(thresholds.p85),
            canonicalize_float(thresholds.p95),
        )
    )
    return BandDecision(
        eligible=decision.eligible,
        reference_count=decision.reference_count,
        thresholds=canonical_thresholds,
        raw_band=decision.raw_band,
        published_band=decision.published_band,
        confirmed_band=decision.confirmed_band,
        candidate_band=decision.candidate_band,
        candidate_count=decision.candidate_count,
    )


def _band_payload(decision: BandDecision) -> dict[str, JsonValue]:
    thresholds: JsonValue = None
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


def serialize_frozen_record(record: FrozenRecord) -> bytes:
    """Serialize one append-only frozen month as canonical JSONL bytes."""
    families: dict[str, JsonValue] = {
        family: {
            "abstained": state.abstained,
            "flags": list(state.flags),
            "z_score": state.z_score,
        }
        for family, state in record.families
    }
    payload: dict[str, JsonValue] = {
        "assembly_flags": list(record.assembly_flags),
        "band": _band_payload(record.band),
        "composite": {
            "abstained": record.composite_abstained,
            "headline_tier": record.headline_tier,
            "headline_value": record.headline_value,
            "tier_a_value": record.tier_a_value,
            "tier_b_mapped_band": record.tier_b_mapped_band,
            "tier_b_value": record.tier_b_value,
        },
        "families": families,
        "finalized_on": record.finalized_on,
        "input_vintages": dict(record.input_vintages),
        "license_notices": list(record.license_notices),
        "month": record.month,
        "schema_version": SCHEMA_VERSION,
        "source_assembly_json": record.source_assembly_json,
        "source_assembly_sha256": record.source_assembly_sha256,
    }
    return canonical_json_bytes(payload)


def _expect_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object with string keys")
    return cast(dict[str, object], value)


def _expect_keys(value: dict[str, object], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise ValueError(f"{field} has {'; '.join(details)}")


def _expect_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _expect_optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _expect_string(value, field)


def _expect_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _expect_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _expect_optional_float(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number or null")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be finite or null")
    return converted


def _expect_string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be an array of strings")
    return tuple(cast(list[str], value))


def _expect_band(value: object, field: str) -> BandName | None:
    if value is None:
        return None
    if value not in {"Normal", "Watch", "Elevated", "High"}:
        raise ValueError(f"{field} is not a canonical band")
    return cast(BandName, value)


def _parse_band(value: object) -> BandDecision:
    payload = _expect_mapping(value, "band")
    _expect_keys(
        payload,
        {
            "candidate_band",
            "candidate_count",
            "confirmed_band",
            "eligible",
            "published_band",
            "raw_band",
            "reference_count",
            "thresholds",
        },
        "band",
    )
    thresholds_payload = payload["thresholds"]
    thresholds: BandThresholds | None = None
    if thresholds_payload is not None:
        threshold_map = _expect_mapping(thresholds_payload, "band.thresholds")
        _expect_keys(threshold_map, {"p70", "p85", "p95"}, "band.thresholds")
        p70 = _expect_optional_float(threshold_map["p70"], "band.thresholds.p70")
        p85 = _expect_optional_float(threshold_map["p85"], "band.thresholds.p85")
        p95 = _expect_optional_float(threshold_map["p95"], "band.thresholds.p95")
        if p70 is None or p85 is None or p95 is None:
            raise ValueError("band thresholds cannot contain null")
        thresholds = BandThresholds(p70, p85, p95)
    return BandDecision(
        eligible=_expect_bool(payload["eligible"], "band.eligible"),
        reference_count=_expect_int(payload["reference_count"], "band.reference_count"),
        thresholds=thresholds,
        raw_band=_expect_band(payload["raw_band"], "band.raw_band"),
        published_band=_expect_band(payload["published_band"], "band.published_band"),
        confirmed_band=_expect_band(payload["confirmed_band"], "band.confirmed_band"),
        candidate_band=_expect_band(payload["candidate_band"], "band.candidate_band"),
        candidate_count=_expect_int(payload["candidate_count"], "band.candidate_count"),
    )


def _parse_record(value: object) -> FrozenRecord:
    payload = _expect_mapping(value, "record")
    _expect_keys(
        payload,
        {
            "assembly_flags",
            "band",
            "composite",
            "families",
            "finalized_on",
            "input_vintages",
            "license_notices",
            "month",
            "schema_version",
            "source_assembly_json",
            "source_assembly_sha256",
        },
        "record",
    )
    schema_version = _expect_string(payload["schema_version"], "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {schema_version!r}")
    source_hash = _expect_string(payload["source_assembly_sha256"], "source hash")
    if SHA256_PATTERN.fullmatch(source_hash) is None:
        raise ValueError("source_assembly_sha256 must be a lowercase SHA-256")

    composite = _expect_mapping(payload["composite"], "composite")
    _expect_keys(
        composite,
        {
            "abstained",
            "headline_tier",
            "headline_value",
            "tier_a_value",
            "tier_b_mapped_band",
            "tier_b_value",
        },
        "composite",
    )
    family_payload = _expect_mapping(payload["families"], "families")
    families: list[tuple[str, FrozenFamily]] = []
    for family, raw_state in sorted(family_payload.items()):
        state = _expect_mapping(raw_state, f"families.{family}")
        _expect_keys(state, {"abstained", "flags", "z_score"}, f"families.{family}")
        families.append(
            (
                family,
                FrozenFamily(
                    z_score=_expect_optional_float(state["z_score"], f"families.{family}.z_score"),
                    abstained=_expect_bool(state["abstained"], f"families.{family}.abstained"),
                    flags=_expect_string_tuple(state["flags"], f"families.{family}.flags"),
                ),
            )
        )
    vintage_payload = _expect_mapping(payload["input_vintages"], "input_vintages")
    input_vintages = tuple(
        (series_id, _expect_string(vintage, f"input_vintages.{series_id}"))
        for series_id, vintage in sorted(vintage_payload.items())
    )
    return FrozenRecord(
        month=_expect_string(payload["month"], "month"),
        finalized_on=_expect_string(payload["finalized_on"], "finalized_on"),
        source_assembly_sha256=source_hash,
        source_assembly_json=_expect_string(
            payload["source_assembly_json"], "source_assembly_json"
        ),
        tier_a_value=_expect_optional_float(composite["tier_a_value"], "tier_a_value"),
        tier_b_value=_expect_optional_float(composite["tier_b_value"], "tier_b_value"),
        tier_b_mapped_band=_expect_band(composite["tier_b_mapped_band"], "tier_b_mapped_band"),
        headline_value=_expect_optional_float(composite["headline_value"], "headline_value"),
        headline_tier=_expect_optional_string(composite["headline_tier"], "headline_tier"),
        composite_abstained=_expect_bool(composite["abstained"], "composite.abstained"),
        assembly_flags=_expect_string_tuple(payload["assembly_flags"], "assembly_flags"),
        families=tuple(families),
        input_vintages=input_vintages,
        license_notices=_expect_string_tuple(payload["license_notices"], "license_notices"),
        band=_parse_band(payload["band"]),
    )


def _next_month(month: str) -> str:
    parsed = date.fromisoformat(f"{month}-01")
    year = parsed.year + (1 if parsed.month == 12 else 0)
    month_number = 1 if parsed.month == 12 else parsed.month + 1
    return f"{year:04d}-{month_number:02d}"


def _validate_persisted_vintages(
    record: FrozenRecord,
    position: int,
    validation: ValidationResult,
) -> None:
    try:
        finalization = date.fromisoformat(record.finalized_on)
    except ValueError:
        validation.error(f"frozen line {position}: finalized_on is not an ISO date")
        return
    if finalization.isoformat() != record.finalized_on:
        validation.error(f"frozen line {position}: finalized_on is not an ISO date")
        return
    for series_id, vintage in record.input_vintages:
        try:
            parsed = date.fromisoformat(vintage)
        except ValueError:
            validation.error(
                f"frozen line {position}: {series_id} input vintage is not an ISO date"
            )
            continue
        if parsed.isoformat() != vintage:
            validation.error(
                f"frozen line {position}: {series_id} input vintage is not an ISO date"
            )
        elif parsed > finalization:
            validation.error(
                f"frozen line {position}: {series_id} input vintage is after finalization"
            )


def _validate_source_assembly(
    record: FrozenRecord,
    position: int,
    validation: ValidationResult,
) -> None:
    try:
        finalization = date.fromisoformat(record.finalized_on)
        if finalization.isoformat() != record.finalized_on:
            raise ValueError("finalized_on is not an ISO date")
        source_bytes = record.source_assembly_json.encode("utf-8")
        if hashlib.sha256(source_bytes).hexdigest() != record.source_assembly_sha256:
            raise ValueError("hash does not match source_assembly_sha256")
        source_value = json.loads(source_bytes.decode("utf-8"))
        source = _expect_mapping(source_value, "source assembly")
        _expect_keys(
            source,
            {"assembly_date", "assembly_mode", "composite", "families", "schema_version"},
            "source assembly",
        )
        if canonical_json_bytes(cast(dict[str, JsonValue], source)) != source_bytes:
            raise ValueError("JSON is not canonical")
        if _expect_string(source["schema_version"], "source schema_version") != (
            "adls.engine.assembly.v1"
        ):
            raise ValueError("has unsupported schema_version")
        if _expect_string(source["assembly_mode"], "source assembly_mode") != "canonical":
            raise ValueError("is not canonical")
        if _expect_string(source["assembly_date"], "source assembly_date") != (
            record.finalized_on
        ):
            raise ValueError("date does not match finalized_on")

        source_composite = _expect_mapping(source["composite"], "source composite")
        _expect_keys(
            source_composite,
            {
                "abstained",
                "flags",
                "headline_tier",
                "headline_value",
                "tier_a_value",
                "tier_b_value",
            },
            "source composite",
        )
        composite_pairs = (
            (
                _expect_optional_float(source_composite["tier_a_value"], "source tier_a"),
                record.tier_a_value,
                "Tier-A value",
            ),
            (
                _expect_optional_float(source_composite["tier_b_value"], "source tier_b"),
                record.tier_b_value,
                "Tier-B value",
            ),
            (
                _expect_optional_float(source_composite["headline_value"], "source headline"),
                record.headline_value,
                "headline value",
            ),
        )
        for source_value_number, frozen_value, label in composite_pairs:
            if source_value_number != frozen_value:
                raise ValueError(f"{label} does not match frozen record")
        if (
            _expect_optional_string(source_composite["headline_tier"], "source headline_tier")
            != record.headline_tier
        ):
            raise ValueError("headline tier does not match frozen record")
        if _expect_bool(source_composite["abstained"], "source abstained") != (
            record.composite_abstained
        ):
            raise ValueError("abstention does not match frozen record")
        if _expect_string_tuple(source_composite["flags"], "source flags") != (
            record.assembly_flags
        ):
            raise ValueError("flags do not match frozen record")

        raw_families = source["families"]
        if not isinstance(raw_families, list):
            raise ValueError("families must be an array")
        source_families: dict[str, FrozenFamily] = {}
        source_vintages: dict[str, str] = {}
        source_license_tags: set[str] = set()
        family_keys = {
            "abstained",
            "component_z_scores",
            "family",
            "flags",
            "member_release_dates",
            "member_series_ids",
            "observation_date",
            "role",
            "tier",
            "transformed_value",
            "transformed_value_redacted",
            "z_score",
        }
        for family_position, raw_family in enumerate(raw_families, 1):
            family = _expect_mapping(raw_family, f"source family {family_position}")
            _expect_keys(family, family_keys, f"source family {family_position}")
            family_name = _expect_string(family["family"], "source family name")
            if family_name in source_families:
                raise ValueError(f"contains duplicate family {family_name!r}")
            source_families[family_name] = FrozenFamily(
                z_score=_expect_optional_float(family["z_score"], f"source {family_name} z_score"),
                abstained=_expect_bool(family["abstained"], f"source {family_name} abstained"),
                flags=_expect_string_tuple(family["flags"], f"source {family_name} flags"),
            )
            observation_text = _expect_optional_string(
                family["observation_date"], f"source {family_name} observation_date"
            )
            if observation_text is not None:
                try:
                    observation_date = date.fromisoformat(observation_text)
                except ValueError as exc:
                    raise ValueError(f"{family_name} observation date is not an ISO date") from exc
                if observation_date.isoformat() != observation_text:
                    raise ValueError(f"{family_name} observation date is not an ISO date")
                if observation_date > finalization:
                    raise ValueError(f"{family_name} observation date is after finalization")
            member_ids = _expect_string_tuple(
                family["member_series_ids"], f"source {family_name} member_series_ids"
            )
            redacted = _expect_bool(
                family["transformed_value_redacted"],
                f"source {family_name} transformed_value_redacted",
            )
            for series_id in member_ids:
                try:
                    license_tag = by_id(series_id).license
                except KeyError as exc:
                    raise ValueError(f"contains unknown series_id {series_id!r}") from exc
                source_license_tags.add(license_tag)
                if license_tag == "umich_internal" and (
                    family["transformed_value"] is not None or not redacted
                ):
                    raise ValueError("contains an unredacted internal-use level")
            releases = _expect_mapping(
                family["member_release_dates"],
                f"source {family_name} member_release_dates",
            )
            for series_id, raw_vintage in releases.items():
                vintage = _expect_string(raw_vintage, f"source vintage {series_id}")
                if series_id in source_vintages:
                    raise ValueError(f"contains duplicate input vintage {series_id}")
                source_vintages[series_id] = vintage

        if tuple(sorted(source_families.items())) != record.families:
            raise ValueError("family scores do not match frozen record")
        if tuple(sorted(source_vintages.items())) != record.input_vintages:
            raise ValueError("input vintages do not match frozen record")
        source_notices = tuple(sorted(LICENSE_NOTICES[tag] for tag in source_license_tags))
        if source_notices != record.license_notices:
            raise ValueError("license notices do not match frozen record")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        validation.error(f"frozen line {position}: source assembly {exc}")


def _values_match(actual: float | None, expected: float | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return abs(actual - expected) <= 0.000001


def _validate_composite_arithmetic(
    record: FrozenRecord,
    position: int,
    validation: ValidationResult,
) -> None:
    error_count = len(validation.errors)
    families = dict(record.families)
    expected_families = {*LEADING_FAMILIES, "strain"}
    if set(families) != expected_families:
        validation.error(
            f"frozen line {position}: family set does not match the registered engine"
        )
        return
    for family, state in families.items():
        if state.abstained != (state.z_score is None):
            validation.error(f"frozen line {position}: {family} abstention and z-score disagree")
    if len(validation.errors) > error_count:
        return

    leading = {family: families[family] for family in LEADING_FAMILIES}
    abstained_count = sum(state.abstained for state in leading.values())
    if abstained_count >= 2:
        if not record.composite_abstained or any(
            value is not None
            for value in (record.tier_a_value, record.tier_b_value, record.headline_value)
        ):
            validation.error(
                f"frozen line {position}: abstained composite arithmetic is inconsistent"
            )
        if record.headline_tier is not None:
            validation.error(
                f"frozen line {position}: abstained composite cannot have a headline tier"
            )
        return

    if record.composite_abstained:
        validation.error(f"frozen line {position}: available composite is marked abstained")
        return
    tier_a_families = ("census_retail", "household_liquidity", "umich_top_tercile")
    tier_a_scores: list[float] = []
    for family in tier_a_families:
        state = families[family]
        if not state.abstained and state.z_score is not None:
            tier_a_scores.append(state.z_score)
    expected_tier_a = math.fsum(tier_a_scores) / len(tier_a_scores)
    if not _values_match(record.tier_a_value, expected_tier_a):
        validation.error(f"frozen line {position}: Tier-A composite arithmetic is inconsistent")

    visa = families["visa_smi"]
    if visa.abstained:
        expected_tier_b = None
        expected_headline = expected_tier_a
        expected_headline_tier = "A"
    else:
        leading_scores = [
            state.z_score
            for state in leading.values()
            if not state.abstained and state.z_score is not None
        ]
        expected_tier_b = math.fsum(leading_scores) / len(leading_scores)
        expected_headline = expected_tier_b
        expected_headline_tier = "B"
    if not _values_match(record.tier_b_value, expected_tier_b):
        validation.error(f"frozen line {position}: Tier-B composite arithmetic is inconsistent")
    if not _values_match(record.headline_value, expected_headline):
        validation.error(f"frozen line {position}: headline arithmetic is inconsistent")
    if record.headline_tier != expected_headline_tier:
        validation.error(f"frozen line {position}: headline tier is inconsistent")


def _validate_record_sequence(
    records: list[FrozenRecord],
    validation: ValidationResult,
) -> None:
    prior_values: list[float | None] = []
    previous_band: BandDecision | None = None
    previous_month: str | None = None
    for position, record in enumerate(records, 1):
        try:
            expected_finalization = monthly_finalization_date(record.month).isoformat()
        except ValueError as exc:
            validation.error(f"frozen line {position}: {exc}")
            return
        if record.finalized_on != expected_finalization:
            validation.error(
                f"frozen line {position}: finalized_on must be {expected_finalization}"
            )
        _validate_persisted_vintages(record, position, validation)
        _validate_source_assembly(record, position, validation)
        _validate_composite_arithmetic(record, position, validation)
        if previous_month is not None and record.month != _next_month(previous_month):
            validation.error(
                f"frozen line {position}: expected month {_next_month(previous_month)}, "
                f"got {record.month}"
            )
        computed_band = evaluate_band(prior_values, previous_band, record.tier_a_value)
        expected_band = _canonical_band(computed_band)
        if record.band != expected_band:
            validation.error(f"frozen line {position}: band state does not match frozen history")
        expected_tier_b_band = None
        if record.tier_b_value is not None and computed_band.thresholds is not None:
            expected_tier_b_band = classify_band(record.tier_b_value, computed_band.thresholds)
        if record.tier_b_mapped_band != expected_tier_b_band:
            validation.error(
                f"frozen line {position}: Tier-B mapped band does not match Tier-A thresholds"
            )
        prior_values.append(record.tier_a_value)
        previous_band = record.band
        previous_month = record.month


def load_frozen_sequence(path: Path) -> FrozenSequenceResult:
    """Read and structurally validate canonical JSONL without raising on data defects."""
    validation = ValidationResult()
    if not path.exists():
        return FrozenSequenceResult((), validation)
    try:
        blob = path.read_bytes()
    except OSError as exc:
        validation.error(f"cannot read frozen store: {exc}")
        return FrozenSequenceResult((), validation)
    if not blob:
        return FrozenSequenceResult((), validation)
    if not blob.endswith(b"\n"):
        validation.error("frozen store must end with LF")
        return FrozenSequenceResult((), validation)

    records: list[FrozenRecord] = []
    for line_number, line in enumerate(blob.splitlines(keepends=True), 1):
        try:
            payload = json.loads(line.decode("utf-8"))
            record = _parse_record(payload)
            if serialize_frozen_record(record) != line:
                raise ValueError("line is not canonical JSON")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            validation.error(f"frozen line {line_number}: {exc}")
            continue
        records.append(record)
    if validation.ok:
        _validate_record_sequence(records, validation)
    return FrozenSequenceResult(tuple(records), validation)


def _validated_release_date(
    value: str,
    series_id: str,
    assembly_date: date,
    validation: ValidationResult,
) -> None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        validation.error(f"{series_id} input vintage is not an ISO date")
        return
    if parsed.isoformat() != value:
        validation.error(f"{series_id} input vintage is not an ISO date")
    elif parsed > assembly_date:
        validation.error(f"{series_id} input vintage is after the assembly date")


def _build_record(
    month: str,
    assembly: AssemblyResult,
    history: tuple[FrozenRecord, ...],
    validation: ValidationResult,
) -> FrozenRecord | None:
    for warning in assembly.validation.warnings:
        validation.warn(warning)
    for error in assembly.validation.errors:
        validation.error(f"assembly invalid: {error}")
    if not assembly.validation.ok:
        return None

    try:
        assembly_day = date.fromisoformat(assembly.assembly_date)
    except ValueError:
        validation.error(f"invalid assembly date {assembly.assembly_date!r}")
        return None
    if assembly_day.isoformat() != assembly.assembly_date:
        validation.error(f"invalid assembly date {assembly.assembly_date!r}")
        return None
    expected_finalization = monthly_finalization_date(month)
    if assembly.provisional:
        validation.error("provisional assemblies cannot enter the frozen canonical store")
    if assembly_day != expected_finalization:
        validation.error(
            f"assembly date must equal {month} finalization date "
            f"{expected_finalization.isoformat()}"
        )
    if not validation.ok:
        return None

    try:
        tier_a_value = _optional_canonical_float(assembly.tier_a_value)
        tier_b_value = _optional_canonical_float(assembly.tier_b_value)
        headline_value = _optional_canonical_float(assembly.headline_value)
    except ValueError as exc:
        validation.error(str(exc))
        return None
    if assembly.composite_abstained and any(
        value is not None for value in (tier_a_value, tier_b_value, headline_value)
    ):
        validation.error("abstained composite cannot carry tier or headline values")

    families: list[tuple[str, FrozenFamily]] = []
    input_vintages: dict[str, str] = {}
    license_tags: set[str] = set()
    seen_families: set[str] = set()
    for family in assembly.family_scores:
        if family.family in seen_families:
            validation.error(f"duplicate family {family.family!r} in assembly")
            continue
        seen_families.add(family.family)
        try:
            z_score = _optional_canonical_float(family.z_score)
        except ValueError as exc:
            validation.error(f"{family.family}: {exc}")
            z_score = None
        families.append(
            (
                family.family,
                FrozenFamily(z_score, family.abstained, tuple(family.flags)),
            )
        )
        for series_id, release_date in family.member_release_dates:
            prior_release = input_vintages.get(series_id)
            if prior_release is not None and prior_release != release_date:
                validation.error(f"conflicting input vintages for {series_id}")
                continue
            input_vintages[series_id] = release_date
            _validated_release_date(release_date, series_id, assembly_day, validation)
        for series_id in family.member_series_ids:
            try:
                license_tags.add(by_id(series_id).license)
            except KeyError:
                validation.error(f"unknown assembly series_id {series_id!r}")
    unknown_license_tags = sorted(license_tags - set(LICENSE_NOTICES))
    for license_tag in unknown_license_tags:
        validation.error(f"unknown license tag {license_tag!r}")
    if not validation.ok:
        return None

    prior_values = [record.tier_a_value for record in history]
    previous_band = history[-1].band if history else None
    decision = evaluate_band(prior_values, previous_band, tier_a_value)
    tier_b_mapped_band = None
    if tier_b_value is not None and decision.thresholds is not None:
        tier_b_mapped_band = classify_band(tier_b_value, decision.thresholds)
    canonical_decision = _canonical_band(decision)
    try:
        source_bytes = serialize_assembly(assembly)
    except ValueError as exc:
        validation.error(str(exc))
        return None
    record = FrozenRecord(
        month=month,
        finalized_on=assembly.assembly_date,
        source_assembly_sha256=hashlib.sha256(source_bytes).hexdigest(),
        source_assembly_json=source_bytes.decode("utf-8"),
        tier_a_value=tier_a_value,
        tier_b_value=tier_b_value,
        tier_b_mapped_band=tier_b_mapped_band,
        headline_value=headline_value,
        headline_tier=assembly.headline_tier,
        composite_abstained=assembly.composite_abstained,
        assembly_flags=tuple(assembly.flags),
        families=tuple(sorted(families)),
        input_vintages=tuple(sorted(input_vintages.items())),
        license_notices=tuple(sorted(LICENSE_NOTICES[tag] for tag in license_tags)),
        band=canonical_decision,
    )
    position = len(history) + 1
    _validate_source_assembly(record, position, validation)
    _validate_composite_arithmetic(record, position, validation)
    return record if validation.ok else None


def _thread_lock_for(path: Path) -> threading.Lock:
    absolute_path = path.absolute()
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(absolute_path)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[absolute_path] = lock
        return lock


@contextmanager
def _exclusive_store_lock(path: Path) -> Iterator[None]:
    thread_lock = _thread_lock_for(path)
    with thread_lock:
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            fcntl.flock(directory_fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(directory_fd, fcntl.LOCK_UN)
            os.close(directory_fd)


def _freeze_canonical_month_locked(
    path: Path,
    month: str,
    assembly: AssemblyResult,
) -> FreezeResult:
    loaded = load_frozen_sequence(path)
    validation = ValidationResult()
    validation.extend(loaded.validation)
    if not validation.ok:
        return FreezeResult(False, None, validation)

    existing_months = {record.month for record in loaded.records}
    if month in existing_months:
        validation.error(f"canonical month {month} is already frozen")
        return FreezeResult(False, None, validation)
    if loaded.records:
        expected_month = _next_month(loaded.records[-1].month)
        if month != expected_month:
            validation.error(f"next canonical month must be {expected_month}, got {month}")
            return FreezeResult(False, None, validation)

    try:
        record = _build_record(month, assembly, loaded.records, validation)
    except ValueError as exc:
        validation.error(str(exc))
        return FreezeResult(False, None, validation)
    if record is None or not validation.ok:
        return FreezeResult(False, None, validation)
    line = serialize_frozen_record(record)
    try:
        with path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        validation.error(f"cannot append frozen store: {exc}")
        return FreezeResult(False, None, validation)
    return FreezeResult(True, record, validation)


def freeze_canonical_month(
    path: Path,
    month: str,
    assembly: AssemblyResult,
) -> FreezeResult:
    """Append one due month; existing months and malformed histories are never rewritten."""
    validation = ValidationResult()
    try:
        with _exclusive_store_lock(path):
            return _freeze_canonical_month_locked(path, month, assembly)
    except OSError as exc:
        validation.error(f"cannot lock frozen store: {exc}")
        return FreezeResult(False, None, validation)
