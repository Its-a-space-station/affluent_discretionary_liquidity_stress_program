"""Independent verification of frozen source assemblies and band history."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, DecimalException
from pathlib import Path
from typing import TypeAlias, cast

from .arithmetic import compute_assembly
from .bands import classify_band, decision_payload, evaluate_band, publication_float
from .calendar import monthly_finalization_date, next_month
from .constants import (
    LEADING_FAMILIES,
    LICENSE_NOTICES,
    SERIES_RULES,
    TIER_A_FAMILIES,
)
from .models import (
    AssemblyComputation,
    BandDecision,
    CheckerRules,
    CheckEvidence,
    CheckResult,
    FamilyComputation,
    VerificationLabel,
)
from .sources import EvidenceConflict, EvidenceSources, EvidenceUnavailable

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
FROZEN_KEYS = {
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
}
COMPOSITE_KEYS = {
    "abstained",
    "headline_tier",
    "headline_value",
    "tier_a_value",
    "tier_b_mapped_band",
    "tier_b_value",
}
BAND_KEYS = {
    "candidate_band",
    "candidate_count",
    "confirmed_band",
    "eligible",
    "published_band",
    "raw_band",
    "reference_count",
    "thresholds",
}
FAMILY_STATE_KEYS = {"abstained", "flags", "z_score"}
THRESHOLD_KEYS = {"p70", "p85", "p95"}
SOURCE_KEYS = {"assembly_date", "assembly_mode", "composite", "families", "schema_version"}
SOURCE_COMPOSITE_KEYS = {
    "abstained",
    "flags",
    "headline_tier",
    "headline_value",
    "tier_a_value",
    "tier_b_value",
}
SOURCE_FAMILY_KEYS = {
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
VALID_BANDS = {"Normal", "Watch", "Elevated", "High"}
SIX_PLACES = Decimal("0.000001")


def _render_number(value: float) -> str:
    try:
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite():
            raise ValueError("JSON number is not finite")
        rounded = decimal_value.quantize(SIX_PLACES, rounding=ROUND_HALF_EVEN)
    except (DecimalException, OverflowError, ValueError) as exc:
        raise ValueError("JSON number cannot be canonicalized") from exc
    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, "f")


def _render_json(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _render_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(_render_json(item) for item in value) + "]"
    return (
        "{"
        + ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{_render_json(value[key])}"
            for key in sorted(value)
        )
        + "}"
    )


def _canonical_json_bytes(value: dict[str, JsonValue]) -> bytes:
    return (_render_json(value) + "\n").encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _json_object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object")
    return cast(dict[str, object], value)


def _exact_keys(value: dict[str, object], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise ValueError(f"{field} has {'; '.join(details)}")


def _string_array(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be an array of strings")
    return cast(list[str], value)


def _band_value(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in VALID_BANDS:
        raise ValueError(f"{field} is not a canonical band")
    return value


def _validate_embedded_source(payload: dict[str, object], prefix: str) -> None:
    source_text = cast(str, payload["source_assembly_json"])
    source_hash = cast(str, payload["source_assembly_sha256"])
    if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != source_hash:
        raise ValueError(f"{prefix}.source_assembly_sha256 does not match embedded bytes")
    try:
        parsed = json.loads(source_text, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, RecursionError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{prefix}.source_assembly_json cannot be parsed: {exc}") from exc
    source = _json_object(parsed, f"{prefix}.source_assembly_json")
    if _canonical_json_bytes(cast(dict[str, JsonValue], source)) != source_text.encode("utf-8"):
        raise ValueError(f"{prefix}.source_assembly_json is not canonical JSON")
    _exact_keys(source, SOURCE_KEYS, f"{prefix}.source_assembly_json")
    if source["schema_version"] != "adls.engine.assembly.v1":
        raise ValueError(f"{prefix}.source_assembly_json has unsupported schema_version")
    for field in ("assembly_date", "assembly_mode"):
        if not isinstance(source[field], str):
            raise ValueError(f"{prefix}.source_assembly_json.{field} must be a string")
    if source["assembly_mode"] != "canonical":
        raise ValueError(f"{prefix}.source_assembly_json must be canonical")
    if source["assembly_date"] != payload["finalized_on"]:
        raise ValueError(f"{prefix}.source_assembly_json assembly date differs")
    try:
        finalization = date.fromisoformat(cast(str, source["assembly_date"]))
    except ValueError as exc:
        raise ValueError(f"{prefix}.source_assembly_json assembly date is invalid") from exc
    if finalization.isoformat() != source["assembly_date"]:
        raise ValueError(f"{prefix}.source_assembly_json assembly date is invalid")

    composite = _json_object(
        source["composite"],
        f"{prefix}.source_assembly_json.composite",
    )
    _exact_keys(
        composite,
        SOURCE_COMPOSITE_KEYS,
        f"{prefix}.source_assembly_json.composite",
    )
    if not isinstance(composite["abstained"], bool):
        raise ValueError(f"{prefix}.source_assembly_json.composite.abstained must be boolean")
    _string_array(composite["flags"], f"{prefix}.source_assembly_json.composite.flags")
    headline_tier = composite["headline_tier"]
    if headline_tier is not None and (
        not isinstance(headline_tier, str) or headline_tier not in {"A", "B"}
    ):
        raise ValueError(f"{prefix}.source_assembly_json.composite.headline_tier is invalid")
    for field in ("headline_value", "tier_a_value", "tier_b_value"):
        _number(
            composite[field],
            f"{prefix}.source_assembly_json.composite.{field}",
            optional=True,
            require_float=True,
        )

    families = source["families"]
    if not isinstance(families, list):
        raise ValueError(f"{prefix}.source_assembly_json.families must be an array")
    seen_families: set[str] = set()
    for position, raw_family in enumerate(families, 1):
        family_path = f"{prefix}.source_assembly_json.families[{position}]"
        family = _json_object(raw_family, family_path)
        _exact_keys(family, SOURCE_FAMILY_KEYS, family_path)
        family_name = family["family"]
        if not isinstance(family_name, str) or family_name in seen_families:
            raise ValueError(f"{family_path}.family is invalid or duplicated")
        seen_families.add(family_name)
        if not isinstance(family["abstained"], bool):
            raise ValueError(f"{family_path}.abstained must be boolean")
        if not isinstance(family["transformed_value_redacted"], bool):
            raise ValueError(f"{family_path}.transformed_value_redacted must be boolean")
        if not isinstance(family["role"], str) or family["role"] not in {
            "leading",
            "overlay",
        }:
            raise ValueError(f"{family_path}.role is invalid")
        tier = family["tier"]
        if tier is not None and (not isinstance(tier, str) or tier not in {"A", "B"}):
            raise ValueError(f"{family_path}.tier is invalid")
        observation_date = family["observation_date"]
        if observation_date is not None and not isinstance(observation_date, str):
            raise ValueError(f"{family_path}.observation_date is invalid")
        if isinstance(observation_date, str):
            try:
                parsed_observation = date.fromisoformat(observation_date)
            except ValueError as exc:
                raise ValueError(f"{family_path}.observation_date is invalid") from exc
            if (
                parsed_observation.isoformat() != observation_date
                or parsed_observation > finalization
            ):
                raise ValueError(f"{family_path}.observation_date is invalid")
        _string_array(family["flags"], f"{family_path}.flags")
        _string_array(family["member_series_ids"], f"{family_path}.member_series_ids")
        releases = _json_object(
            family["member_release_dates"],
            f"{family_path}.member_release_dates",
        )
        if any(not isinstance(value, str) for value in releases.values()):
            raise ValueError(f"{family_path}.member_release_dates values must be strings")
        for series_id, release_date in releases.items():
            try:
                parsed_release = date.fromisoformat(cast(str, release_date))
            except ValueError as exc:
                raise ValueError(
                    f"{family_path}.member_release_dates.{series_id} is invalid"
                ) from exc
            if parsed_release.isoformat() != release_date or parsed_release > finalization:
                raise ValueError(f"{family_path}.member_release_dates.{series_id} is invalid")
        components = _json_object(
            family["component_z_scores"],
            f"{family_path}.component_z_scores",
        )
        for series_id, value in components.items():
            _number(
                value,
                f"{family_path}.component_z_scores.{series_id}",
                require_float=True,
            )
        for field in ("transformed_value", "z_score"):
            _number(
                family[field],
                f"{family_path}.{field}",
                optional=True,
                require_float=True,
            )


def _validate_frozen_shape(payload: dict[str, object], prefix: str) -> None:
    _exact_keys(payload, FROZEN_KEYS, prefix)
    for field in ("month", "finalized_on", "source_assembly_json", "source_assembly_sha256"):
        if not isinstance(payload[field], str):
            raise ValueError(f"{prefix}.{field} must be a string")
    source_hash = cast(str, payload["source_assembly_sha256"])
    valid_hash = len(source_hash) == 64 and all(
        character in "0123456789abcdef" for character in source_hash
    )
    if not valid_hash:
        raise ValueError(f"{prefix}.source_assembly_sha256 must be a lowercase SHA-256")
    _string_array(payload["assembly_flags"], f"{prefix}.assembly_flags")
    _string_array(payload["license_notices"], f"{prefix}.license_notices")

    composite = _json_object(payload["composite"], f"{prefix}.composite")
    _exact_keys(composite, COMPOSITE_KEYS, f"{prefix}.composite")
    if not isinstance(composite["abstained"], bool):
        raise ValueError(f"{prefix}.composite.abstained must be boolean")
    headline_tier = composite["headline_tier"]
    if headline_tier is not None and (
        not isinstance(headline_tier, str) or headline_tier not in {"A", "B"}
    ):
        raise ValueError(f"{prefix}.composite.headline_tier must be A, B, or null")
    for field in ("headline_value", "tier_a_value", "tier_b_value"):
        _number(
            composite[field],
            f"{prefix}.composite.{field}",
            optional=True,
            require_float=True,
        )
    _band_value(composite["tier_b_mapped_band"], f"{prefix}.composite.tier_b_mapped_band")

    families = _json_object(payload["families"], f"{prefix}.families")
    for family, raw_state in families.items():
        state = _json_object(raw_state, f"{prefix}.families.{family}")
        _exact_keys(state, FAMILY_STATE_KEYS, f"{prefix}.families.{family}")
        if not isinstance(state["abstained"], bool):
            raise ValueError(f"{prefix}.families.{family}.abstained must be boolean")
        _string_array(state["flags"], f"{prefix}.families.{family}.flags")
        _number(
            state["z_score"],
            f"{prefix}.families.{family}.z_score",
            optional=True,
            require_float=True,
        )

    vintages = _json_object(payload["input_vintages"], f"{prefix}.input_vintages")
    if any(not isinstance(value, str) for value in vintages.values()):
        raise ValueError(f"{prefix}.input_vintages values must be strings")

    band = _json_object(payload["band"], f"{prefix}.band")
    _exact_keys(band, BAND_KEYS, f"{prefix}.band")
    if not isinstance(band["eligible"], bool):
        raise ValueError(f"{prefix}.band.eligible must be boolean")
    for field in ("candidate_count", "reference_count"):
        if isinstance(band[field], bool) or not isinstance(band[field], int):
            raise ValueError(f"{prefix}.band.{field} must be an integer")
    for field in ("candidate_band", "confirmed_band", "published_band", "raw_band"):
        _band_value(band[field], f"{prefix}.band.{field}")
    if band["thresholds"] is not None:
        thresholds = _json_object(band["thresholds"], f"{prefix}.band.thresholds")
        _exact_keys(thresholds, THRESHOLD_KEYS, f"{prefix}.band.thresholds")
        for field in THRESHOLD_KEYS:
            _number(
                thresholds[field],
                f"{prefix}.band.thresholds.{field}",
                require_float=True,
            )
    _validate_embedded_source(payload, prefix)


def _load_records(
    path: Path,
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    discrepancies: list[str] = []
    debts: list[str] = []
    if not path.exists():
        debts.append(f"frozen sequence does not exist: {path}")
        return [], discrepancies, debts
    try:
        blob = path.read_bytes()
    except OSError as exc:
        debts.append(f"cannot read frozen sequence: {exc}")
        return [], discrepancies, debts
    if not blob:
        debts.append("frozen sequence has no records")
        return [], discrepancies, debts
    if not blob.endswith(b"\n"):
        discrepancies.append("frozen sequence does not end with LF")
        return [], discrepancies, debts

    records: list[dict[str, object]] = []
    for line_number, line in enumerate(blob.splitlines(keepends=True), 1):
        prefix = f"frozen line {line_number}"
        try:
            parsed = json.loads(line.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
            payload = _json_object(parsed, prefix)
            _validate_frozen_shape(payload, prefix)
            if payload["schema_version"] != "adls.frozen.month.v1":
                raise ValueError("unsupported schema_version")
            canonical_payload = cast(dict[str, JsonValue], payload)
            if _canonical_json_bytes(canonical_payload) != line:
                raise ValueError("line is not canonical JSON")
        except (
            ArithmeticError,
            RecursionError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            discrepancies.append(f"{prefix}: {exc}")
            continue
        records.append(payload)
    return records, discrepancies, debts


def _label(
    records: Sequence[dict[str, object]],
    discrepancies: Sequence[str],
    debts: Sequence[str],
) -> VerificationLabel:
    if discrepancies:
        return "Conflicting"
    if not records:
        return "Unverified"
    if debts:
        return "Provisional"
    return "Verified"


def _number(
    value: object,
    field: str,
    *,
    optional: bool = False,
    require_float: bool = False,
) -> float | None:
    if value is None and optional:
        return None
    if require_float and not isinstance(value, float):
        raise ValueError(f"{field} must be a JSON float")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number" + (" or null" if optional else ""))
    try:
        converted = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field} must be representable as a finite number") from exc
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be finite")
    return converted


def _published_matches(expected: float | None, actual: object) -> bool:
    if expected is None:
        return actual is None
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        return False
    try:
        return float(actual) == publication_float(expected)
    except (ArithmeticError, ValueError):
        return False


def _close_match(expected: float | None, actual: object) -> bool:
    if expected is None:
        return actual is None
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        return False
    try:
        return abs(float(actual) - expected) <= 0.000001
    except (ArithmeticError, ValueError):
        return False


def _compare(
    expected: object,
    actual: object,
    path: str,
    discrepancies: list[str],
) -> None:
    if isinstance(expected, float):
        if not _published_matches(expected, actual):
            discrepancies.append(
                f"{path}: expected {publication_float(expected)!r}, got {actual!r}"
            )
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            discrepancies.append(f"{path}: expected an object, got {type(actual).__name__}")
            return
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            discrepancies.append(
                f"{path}: key set differs; expected {sorted(expected_keys)}, "
                f"got {sorted(actual_keys)}"
            )
            return
        for key in sorted(expected):
            _compare(expected[key], actual[key], f"{path}.{key}", discrepancies)
        return
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, list):
            discrepancies.append(f"{path}: expected an array, got {type(actual).__name__}")
            return
        if len(expected) != len(actual):
            discrepancies.append(f"{path}: expected {len(expected)} items, got {len(actual)}")
            return
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=True)):
            _compare(expected_item, actual_item, f"{path}[{index}]", discrepancies)
        return
    if type(expected) is not type(actual) or expected != actual:
        discrepancies.append(f"{path}: expected {expected!r}, got {actual!r}")


def _check_embedded_consistency(
    record: dict[str, object],
    prefix: str,
    discrepancies: list[str],
) -> None:
    source_text = cast(str, record["source_assembly_json"])
    source = _json_object(
        json.loads(source_text, object_pairs_hook=_reject_duplicate_keys),
        f"{prefix} source assembly",
    )
    source_composite = _json_object(source["composite"], f"{prefix} source composite")
    expected_composite = {
        "abstained": source_composite["abstained"],
        "headline_tier": source_composite["headline_tier"],
        "headline_value": source_composite["headline_value"],
        "tier_a_value": source_composite["tier_a_value"],
        "tier_b_value": source_composite["tier_b_value"],
    }
    outer_composite = _json_object(record["composite"], f"{prefix} composite")
    outer_subset = {key: outer_composite[key] for key in expected_composite}
    _compare(expected_composite, outer_subset, f"{prefix} source composite", discrepancies)
    _compare(
        source_composite["flags"],
        record["assembly_flags"],
        f"{prefix} source assembly_flags",
        discrepancies,
    )

    source_families: dict[str, object] = {}
    source_vintages: dict[str, str] = {}
    license_tags: set[str] = set()
    rule_by_id = {rule.series_id: rule for rule in SERIES_RULES}
    for raw_family in cast(list[object], source["families"]):
        family = _json_object(raw_family, f"{prefix} source family")
        family_name = cast(str, family["family"])
        source_families[family_name] = {
            "abstained": family["abstained"],
            "flags": family["flags"],
            "z_score": family["z_score"],
        }
        releases = _json_object(
            family["member_release_dates"],
            f"{prefix} source {family_name} releases",
        )
        for series_id, release_date in releases.items():
            if series_id in source_vintages:
                discrepancies.append(f"{prefix} source repeats input vintage {series_id}")
            else:
                source_vintages[series_id] = cast(str, release_date)
        member_ids = cast(list[str], family["member_series_ids"])
        expected_redaction = False
        for series_id in member_ids:
            rule = rule_by_id.get(series_id)
            if rule is None:
                discrepancies.append(f"{prefix} source has unknown series {series_id!r}")
                continue
            license_tags.add(rule.license_tag)
            expected_redaction = expected_redaction or rule.license_tag == "umich_internal"
        if family["transformed_value_redacted"] is not expected_redaction:
            discrepancies.append(f"{prefix} source {family_name} redaction flag differs")
        if expected_redaction and family["transformed_value"] is not None:
            discrepancies.append(f"{prefix} source {family_name} exposes a licensed level")

    _compare(source_families, record["families"], f"{prefix} source families", discrepancies)
    _compare(
        source_vintages,
        record["input_vintages"],
        f"{prefix} source input_vintages",
        discrepancies,
    )
    expected_notices = sorted(LICENSE_NOTICES[tag] for tag in license_tags)
    _compare(
        expected_notices,
        record["license_notices"],
        f"{prefix} source license_notices",
        discrepancies,
    )


def _family_payload(score: FamilyComputation) -> dict[str, object]:
    licenses = {
        rule.license_tag for rule in SERIES_RULES if rule.series_id in score.member_series_ids
    }
    redacted = "umich_internal" in licenses
    return {
        "abstained": score.abstained,
        "component_z_scores": dict(score.component_z_scores),
        "family": score.family,
        "flags": list(score.flags),
        "member_release_dates": dict(score.member_release_dates),
        "member_series_ids": list(score.member_series_ids),
        "observation_date": score.observation_date,
        "role": score.role,
        "tier": score.tier,
        "transformed_value": None if redacted else score.transformed_value,
        "transformed_value_redacted": redacted,
        "z_score": score.z_score,
    }


def _assembly_payload(assembly: AssemblyComputation) -> dict[str, object]:
    return {
        "assembly_date": assembly.assembly_date,
        "assembly_mode": "canonical",
        "composite": {
            "abstained": assembly.composite_abstained,
            "flags": list(assembly.flags),
            "headline_tier": assembly.headline_tier,
            "headline_value": assembly.headline_value,
            "tier_a_value": assembly.tier_a_value,
            "tier_b_value": assembly.tier_b_value,
        },
        "families": [_family_payload(score) for score in assembly.family_scores],
        "schema_version": "adls.engine.assembly.v1",
    }


def _expected_input_vintages(assembly: AssemblyComputation) -> dict[str, str]:
    result: dict[str, str] = {}
    for score in assembly.family_scores:
        for series_id, release_date in score.member_release_dates:
            prior = result.get(series_id)
            if prior is not None and prior != release_date:
                raise EvidenceConflict(f"checker computed conflicting vintages for {series_id}")
            result[series_id] = release_date
    return result


def _expected_license_notices(assembly: AssemblyComputation) -> list[str]:
    member_ids = {
        series_id for score in assembly.family_scores for series_id in score.member_series_ids
    }
    tags = {rule.license_tag for rule in SERIES_RULES if rule.series_id in member_ids}
    return sorted(LICENSE_NOTICES[tag] for tag in tags)


def _verify_source_record(
    record: dict[str, object],
    assembly: AssemblyComputation,
    prefix: str,
    discrepancies: list[str],
) -> None:
    source_text = record.get("source_assembly_json")
    source_hash = record.get("source_assembly_sha256")
    if not isinstance(source_text, str) or not isinstance(source_hash, str):
        discrepancies.append(f"{prefix} source assembly text or hash has the wrong type")
        return
    actual_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if actual_hash != source_hash:
        discrepancies.append(f"{prefix} source_assembly_sha256 does not match embedded bytes")
    try:
        source_value = json.loads(source_text, object_pairs_hook=_reject_duplicate_keys)
        source = _json_object(source_value, f"{prefix} source assembly")
        canonical_source = _canonical_json_bytes(cast(dict[str, JsonValue], source))
        if canonical_source != source_text.encode("utf-8"):
            discrepancies.append(f"{prefix} source assembly is not canonical JSON")
    except (
        ArithmeticError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        discrepancies.append(f"{prefix} source assembly cannot be parsed: {exc}")
        return

    _compare(_assembly_payload(assembly), source, f"{prefix} source_assembly", discrepancies)

    expected_families = {
        score.family: {
            "abstained": score.abstained,
            "flags": list(score.flags),
            "z_score": score.z_score,
        }
        for score in assembly.family_scores
    }
    _compare(expected_families, record.get("families"), f"{prefix} families", discrepancies)
    expected_composite = {
        "abstained": assembly.composite_abstained,
        "headline_tier": assembly.headline_tier,
        "headline_value": assembly.headline_value,
        "tier_a_value": assembly.tier_a_value,
        "tier_b_value": assembly.tier_b_value,
    }
    actual_composite = record.get("composite")
    if not isinstance(actual_composite, dict):
        discrepancies.append(f"{prefix} composite is not an object")
    else:
        actual_subset = {key: actual_composite.get(key) for key in expected_composite}
        _compare(expected_composite, actual_subset, f"{prefix} composite", discrepancies)
    _compare(
        list(assembly.flags),
        record.get("assembly_flags"),
        f"{prefix} assembly_flags",
        discrepancies,
    )
    _compare(
        _expected_input_vintages(assembly),
        record.get("input_vintages"),
        f"{prefix} input_vintages",
        discrepancies,
    )
    _compare(
        _expected_license_notices(assembly),
        record.get("license_notices"),
        f"{prefix} license_notices",
        discrepancies,
    )


def _check_outer_composite(
    record: dict[str, object],
    prefix: str,
    discrepancies: list[str],
) -> None:
    try:
        families = _json_object(record["families"], f"{prefix} families")
        composite = _json_object(record["composite"], f"{prefix} composite")
    except (KeyError, ValueError) as exc:
        discrepancies.append(f"{prefix}: {exc}")
        return
    expected_family_set = {*LEADING_FAMILIES, "strain"}
    if set(families) != expected_family_set:
        discrepancies.append(f"{prefix} family set does not match Basket v1")
        return

    states: dict[str, tuple[bool, float | None]] = {}
    try:
        for family, raw_state in families.items():
            state = _json_object(raw_state, f"{prefix} families.{family}")
            abstained = state.get("abstained")
            if not isinstance(abstained, bool):
                raise ValueError(f"{prefix} families.{family}.abstained must be boolean")
            z_score = _number(
                state.get("z_score"),
                f"{prefix} families.{family}.z_score",
                optional=True,
            )
            if abstained != (z_score is None):
                raise ValueError(f"{prefix} families.{family} abstention disagrees with z_score")
            states[family] = (abstained, z_score)
    except ValueError as exc:
        discrepancies.append(str(exc))
        return

    abstained_count = sum(states[family][0] for family in LEADING_FAMILIES)
    if abstained_count >= 2:
        if composite.get("abstained") is not True:
            discrepancies.append(f"{prefix} composite should abstain")
        for field in ("tier_a_value", "tier_b_value", "headline_value", "headline_tier"):
            if composite.get(field) is not None:
                discrepancies.append(f"{prefix} composite.{field} should be null")
        return

    tier_a_scores = [
        cast(float, states[family][1])
        for family in TIER_A_FAMILIES
        if not states[family][0] and states[family][1] is not None
    ]
    expected_tier_a = math.fsum(tier_a_scores) / len(tier_a_scores)
    if not _close_match(expected_tier_a, composite.get("tier_a_value")):
        discrepancies.append(f"{prefix} Tier-A composite arithmetic differs")
    visa_available = not states["visa_smi"][0]
    if visa_available:
        leading_scores = [
            cast(float, states[family][1])
            for family in LEADING_FAMILIES
            if not states[family][0] and states[family][1] is not None
        ]
        expected_tier_b = math.fsum(leading_scores) / len(leading_scores)
        expected_headline = expected_tier_b
        expected_tier = "B"
    else:
        expected_tier_b = None
        expected_headline = expected_tier_a
        expected_tier = "A"
    if not _close_match(expected_tier_b, composite.get("tier_b_value")):
        discrepancies.append(f"{prefix} Tier-B composite arithmetic differs")
    if not _close_match(expected_headline, composite.get("headline_value")):
        discrepancies.append(f"{prefix} headline arithmetic differs")
    if composite.get("headline_tier") != expected_tier:
        discrepancies.append(f"{prefix} headline tier differs")
    if composite.get("abstained") is not False:
        discrepancies.append(f"{prefix} available composite is marked abstained")


def _verify_bands(
    path: Path,
    rules: CheckerRules,
) -> tuple[CheckResult, list[dict[str, object]]]:
    records, discrepancies, debts = _load_records(path)
    if rules != CheckerRules():
        discrepancies.append(
            "checker criteria differ from adls.checker.v1; fault-injection results "
            "cannot be Verified"
        )
    checks: list[CheckEvidence] = []
    prior_values: list[float | None] = []
    previous: BandDecision | None = None
    previous_month: str | None = None
    for position, record in enumerate(records, 1):
        month = record.get("month")
        check_id = f"bands:{month}" if isinstance(month, str) else f"bands:line-{position}"
        before = len(discrepancies)
        prefix = check_id
        try:
            if not isinstance(month, str):
                raise ValueError("month must be a string")
            finalized_on = record.get("finalized_on")
            if not isinstance(finalized_on, str):
                raise ValueError("finalized_on must be a string")
            expected_final = monthly_finalization_date(month).isoformat()
            if finalized_on != expected_final:
                discrepancies.append(
                    f"{prefix} finalized_on should be {expected_final}, got {finalized_on!r}"
                )
            if previous_month is not None and month != next_month(previous_month):
                discrepancies.append(
                    f"{prefix} sequence expected {next_month(previous_month)}, got {month}"
                )

            _check_embedded_consistency(record, prefix, discrepancies)
            _check_outer_composite(record, prefix, discrepancies)
            composite = _json_object(record["composite"], f"{prefix} composite")
            current = _number(
                composite.get("tier_a_value"),
                f"{prefix} tier_a_value",
                optional=True,
            )
            tier_b = _number(
                composite.get("tier_b_value"),
                f"{prefix} tier_b_value",
                optional=True,
            )
            decision = evaluate_band(tuple(prior_values), previous, current, rules)
            _compare(
                decision_payload(decision),
                record.get("band"),
                f"{prefix} band",
                discrepancies,
            )
            expected_tier_b_band = None
            if tier_b is not None and decision.thresholds is not None:
                expected_tier_b_band = classify_band(tier_b, decision.thresholds)
            if composite.get("tier_b_mapped_band") != expected_tier_b_band:
                discrepancies.append(
                    f"{prefix} Tier-B mapped band should be {expected_tier_b_band!r}"
                )

            vintages = _json_object(record["input_vintages"], f"{prefix} input_vintages")
            for series_id, vintage in vintages.items():
                if not isinstance(vintage, str):
                    discrepancies.append(f"{prefix} {series_id} input vintage is invalid")
                    continue
                try:
                    parsed_vintage = date.fromisoformat(vintage)
                except ValueError:
                    discrepancies.append(f"{prefix} {series_id} input vintage is invalid")
                    continue
                if parsed_vintage.isoformat() != vintage or vintage > finalized_on:
                    discrepancies.append(f"{prefix} {series_id} input vintage is invalid")
            prior_values.append(current)
            previous = decision
            previous_month = month
        except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
            discrepancies.append(f"{prefix}: {exc}")
        passed = len(discrepancies) == before
        checks.append(
            CheckEvidence(
                check_id,
                passed,
                "independent band replay agrees" if passed else "independent band replay differs",
            )
        )

    result = CheckResult(
        _label(records, discrepancies, debts),
        tuple(checks),
        tuple(discrepancies),
        tuple(debts),
    )
    return result, records


def verify_band_sequence(
    frozen_path: Path,
    *,
    rules: CheckerRules | None = None,
) -> CheckResult:
    """Replay chronology, composite arithmetic, percentiles, and dwell."""
    result, _ = _verify_bands(frozen_path, rules or CheckerRules())
    return result


def verify_frozen_sequence(
    cache_path: Path,
    archive_paths: tuple[Path, ...],
    frozen_path: Path,
    *,
    rules: CheckerRules | None = None,
) -> CheckResult:
    """Recompute every frozen source assembly and its sequence-owned bands."""
    checker_rules = rules or CheckerRules()
    band_result, records = _verify_bands(frozen_path, checker_rules)
    checks = list(band_result.checks)
    discrepancies = list(band_result.discrepancies)
    debts = list(band_result.debts)
    if not records:
        return band_result

    try:
        sources = EvidenceSources(cache_path, archive_paths, checker_rules)
    except EvidenceUnavailable as exc:
        debts.append(str(exc))
        for position, record in enumerate(records, 1):
            month = record.get("month")
            check_id = f"source:{month}" if isinstance(month, str) else f"source:line-{position}"
            checks.append(CheckEvidence(check_id, False, "source evidence is unavailable"))
        return CheckResult(
            _label(records, discrepancies, debts),
            tuple(checks),
            tuple(discrepancies),
            tuple(debts),
        )
    except EvidenceConflict as exc:
        discrepancies.append(str(exc))
        debts.extend(exc.debts)
        for position, record in enumerate(records, 1):
            month = record.get("month")
            check_id = f"source:{month}" if isinstance(month, str) else f"source:line-{position}"
            checks.append(CheckEvidence(check_id, False, "source evidence is contradictory"))
        return CheckResult(
            _label(records, discrepancies, debts),
            tuple(checks),
            tuple(discrepancies),
            tuple(debts),
        )

    try:
        for position, record in enumerate(records, 1):
            month = record.get("month")
            check_id = f"source:{month}" if isinstance(month, str) else f"source:line-{position}"
            before = len(discrepancies)
            finalized_on = record.get("finalized_on")
            if not isinstance(finalized_on, str):
                discrepancies.append(f"{check_id} finalized_on must be a string")
                checks.append(CheckEvidence(check_id, False, "source record is malformed"))
                continue
            try:
                histories = sources.histories_at(finalized_on)
                assembly = compute_assembly(finalized_on, histories, checker_rules)
                _verify_source_record(record, assembly, check_id, discrepancies)
            except EvidenceUnavailable as exc:
                debts.append(f"{check_id}: {exc}")
            except EvidenceConflict as exc:
                discrepancies.append(f"{check_id}: {exc}")
                debts.extend(f"{check_id}: {debt}" for debt in exc.debts)
            except (ArithmeticError, TypeError, ValueError) as exc:
                discrepancies.append(
                    f"{check_id}: checker could not evaluate malformed evidence: {exc}"
                )
            passed = len(discrepancies) == before and not any(
                debt.startswith(f"{check_id}:") for debt in debts
            )
            checks.append(
                CheckEvidence(
                    check_id,
                    passed,
                    (
                        "independent source recomputation agrees"
                        if passed
                        else "independent source recomputation is incomplete or differs"
                    ),
                )
            )
    finally:
        sources.close()

    return CheckResult(
        _label(records, discrepancies, debts),
        tuple(checks),
        tuple(discrepancies),
        tuple(debts),
    )
