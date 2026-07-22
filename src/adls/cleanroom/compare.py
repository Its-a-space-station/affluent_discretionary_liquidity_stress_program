"""Blind submission sealing and post-disclosure exact comparison."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from .contracts import (
    COMPARISON_SCHEMA_VERSION,
    FROZEN_MONTH_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    SUBMISSION_SCHEMA_VERSION,
    TIER_A_FAMILIES,
    TIER_A_SERIES,
    CleanRoomError,
    JsonValue,
    SequenceDocument,
    canonical_json_bytes,
    canonical_sequence_bytes,
    load_cleanroom_sequence,
    load_submission,
    parse_json_object,
    read_regular_file,
    validate_generated_at,
    validate_implementation_id,
    write_once,
)
from .packet import verify_packet

_REFERENCE_SCHEMA_VERSION = "adls.frozen.month.v1"
_ASSUMPTION_FLAG = "validation_assumption:umich_unrevised_final"
_MAX_DIFFERENCES = 100


@dataclass(frozen=True)
class SealResult:
    artifact_path: Path
    artifact_bytes: bytes
    sha256: str
    created: bool


@dataclass(frozen=True)
class ComparisonResult:
    artifact_path: Path
    artifact_bytes: bytes
    verdict: str
    exact_match: bool
    created: bool


def seal_submission(
    *,
    input_manifest_path: Path,
    candidate_path: Path,
    implementation_id: str,
    generated_at: str,
    artifact_path: Path,
    attest_clean_room: bool,
) -> SealResult:
    """Bind a canonical candidate to its packet before reference disclosure."""
    if not attest_clean_room:
        raise CleanRoomError("clean-room attestation is required before sealing")
    manifest = verify_packet(input_manifest_path)
    candidate = load_cleanroom_sequence(
        candidate_path,
        manifest.start_month,
        manifest.end_month,
    )
    sealed_at = validate_generated_at(generated_at)
    manifest_generated_at = cast(str, manifest.payload["generated_at"])
    if sealed_at <= manifest_generated_at:
        raise CleanRoomError("submission seal timestamp must follow packet generation")
    payload: dict[str, JsonValue] = {
        "attestation": {
            "implemented_from_packet_only": True,
            "no_adls_source_or_tests_access": True,
            "no_reference_output_access": True,
        },
        "generated_at": sealed_at,
        "implementation_id": validate_implementation_id(implementation_id),
        "input_manifest_sha256": manifest.sha256,
        "output_contract_sha256": manifest.output_contract_sha256,
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": SUBMISSION_SCHEMA_VERSION,
        "sequence": {
            "byte_count": len(candidate.artifact_bytes),
            "first_month": candidate.first_month,
            "last_month": candidate.last_month,
            "record_count": len(candidate.records),
            "schema_version": FROZEN_MONTH_SCHEMA_VERSION,
            "sha256": candidate.sha256,
        },
    }
    artifact_bytes = canonical_json_bytes(payload)
    created = write_once(artifact_path, artifact_bytes)
    return SealResult(
        artifact_path,
        artifact_bytes,
        hashlib.sha256(artifact_bytes).hexdigest(),
        created,
    )


def _expect_mapping(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise CleanRoomError(f"{label} must be an object")
    return value


def _expect_string(value: JsonValue, label: str) -> str:
    if not isinstance(value, str):
        raise CleanRoomError(f"{label} must be a string")
    return value


def _project_reference(
    data: bytes,
    start_month: str,
    end_month: str,
) -> SequenceDocument:
    if not data or not data.endswith(b"\n") or b"\r" in data:
        raise CleanRoomError("reference sequence must be LF-terminated canonical JSONL")
    records: list[dict[str, JsonValue]] = []
    for position, line in enumerate(data.splitlines(keepends=True), 1):
        source = parse_json_object(line, f"reference line {position}", require_canonical=True)
        if source.get("schema_version") != _REFERENCE_SCHEMA_VERSION:
            raise CleanRoomError(f"reference line {position} schema_version is unsupported")
        month = _expect_string(source.get("month"), f"reference line {position}.month")
        finalized_on = _expect_string(
            source.get("finalized_on"), f"reference line {position}.finalized_on"
        )
        families = _expect_mapping(source.get("families"), f"reference line {position}.families")
        projected_families: dict[str, JsonValue] = {}
        for family in TIER_A_FAMILIES:
            state = _expect_mapping(
                families.get(family), f"reference line {position}.families.{family}"
            )
            projected_families[family] = {
                "abstained": state.get("abstained"),
                "flags": state.get("flags"),
                "z_score": state.get("z_score"),
            }
        composite = _expect_mapping(
            source.get("composite"), f"reference line {position}.composite"
        )
        tier_a_value = composite.get("tier_a_value")
        if tier_a_value is not None and not isinstance(tier_a_value, Decimal):
            raise CleanRoomError(f"reference line {position}.composite.tier_a_value is invalid")
        vintages = _expect_mapping(
            source.get("input_vintages"), f"reference line {position}.input_vintages"
        )
        projected_vintages: dict[str, JsonValue] = {}
        for series_id in TIER_A_SERIES:
            projected_vintages[series_id] = vintages.get(series_id)
        flags = source.get("assembly_flags")
        if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
            raise CleanRoomError(f"reference line {position}.assembly_flags is invalid")
        band = _expect_mapping(source.get("band"), f"reference line {position}.band")
        records.append(
            {
                "band": band,
                "families": projected_families,
                "finalized_on": finalized_on,
                "historical_umich_final_assumption": _ASSUMPTION_FLAG in flags,
                "input_vintages": projected_vintages,
                "month": month,
                "schema_version": FROZEN_MONTH_SCHEMA_VERSION,
                "tier_a_abstained": tier_a_value is None,
                "tier_a_value": tier_a_value,
            }
        )
    projected = tuple(records)
    projected_bytes = canonical_sequence_bytes(projected, start_month, end_month)
    return SequenceDocument(
        projected,
        projected_bytes,
        hashlib.sha256(projected_bytes).hexdigest(),
        cast(str, projected[0]["month"]),
        cast(str, projected[-1]["month"]),
    )


def _validate_reference_artifact(
    validation_artifact_path: Path,
    reference_bytes: bytes,
) -> tuple[str, int]:
    artifact = parse_json_object(
        read_regular_file(validation_artifact_path),
        "validation artifact",
        require_canonical=True,
    )
    source = _expect_mapping(artifact.get("source"), "validation artifact.source")
    reference_sha256 = hashlib.sha256(reference_bytes).hexdigest()
    if source.get("frozen_equivalent_sha256") != reference_sha256:
        raise CleanRoomError("reference sequence hash differs from the validation artifact")
    if source.get("checker_label") != "Verified":
        raise CleanRoomError("reference validation checker label is not Verified")
    criteria = source.get("checker_criteria_version")
    if criteria != "adls.checker.validation-assumption.v1":
        raise CleanRoomError("reference checker criteria version is unsupported")
    check_count = source.get("checker_check_count")
    if isinstance(check_count, bool) or not isinstance(check_count, int) or check_count < 1:
        raise CleanRoomError("reference validation checker evidence is incomplete")
    debts = artifact.get("verification_debt")
    if not isinstance(debts, list) or "VD-001" not in debts:
        raise CleanRoomError("reference validation artifact does not keep VD-001 open")
    return cast(str, criteria), check_count


def _validate_seal(
    submission: dict[str, JsonValue],
    candidate: SequenceDocument,
    manifest_sha256: str,
    output_contract_sha256: str,
) -> str:
    if submission["input_manifest_sha256"] != manifest_sha256:
        raise CleanRoomError("submission seal input manifest hash differs")
    if submission["output_contract_sha256"] != output_contract_sha256:
        raise CleanRoomError("submission seal output contract hash differs")
    sequence = _expect_mapping(submission["sequence"], "submission.sequence")
    expected: dict[str, JsonValue] = {
        "byte_count": len(candidate.artifact_bytes),
        "first_month": candidate.first_month,
        "last_month": candidate.last_month,
        "record_count": len(candidate.records),
        "schema_version": FROZEN_MONTH_SCHEMA_VERSION,
        "sha256": candidate.sha256,
    }
    if sequence != expected:
        raise CleanRoomError("candidate sequence differs from its pre-disclosure seal")
    return _expect_string(submission["implementation_id"], "submission.implementation_id")


def _pointer(path: str, component: str) -> str:
    escaped = component.replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}" if path else f"/{escaped}"


def _collect_differences(
    reference: JsonValue,
    candidate: JsonValue,
    path: str,
    month: str,
    examples: list[dict[str, JsonValue]],
) -> int:
    if type(reference) is not type(candidate):
        if len(examples) < _MAX_DIFFERENCES:
            examples.append({"kind": "type_mismatch", "month": month, "path": path or "/"})
        return 1
    if isinstance(reference, dict) and isinstance(candidate, dict):
        count = 0
        for key in sorted(set(reference) | set(candidate)):
            child_path = _pointer(path, key)
            if key not in candidate:
                if len(examples) < _MAX_DIFFERENCES:
                    examples.append(
                        {"kind": "missing_in_candidate", "month": month, "path": child_path}
                    )
                count += 1
            elif key not in reference:
                if len(examples) < _MAX_DIFFERENCES:
                    examples.append(
                        {"kind": "unexpected_in_candidate", "month": month, "path": child_path}
                    )
                count += 1
            else:
                count += _collect_differences(
                    reference[key], candidate[key], child_path, month, examples
                )
        return count
    if isinstance(reference, list) and isinstance(candidate, list):
        count = 0
        for index in range(max(len(reference), len(candidate))):
            child_path = _pointer(path, str(index))
            if index >= len(candidate):
                if len(examples) < _MAX_DIFFERENCES:
                    examples.append(
                        {"kind": "missing_in_candidate", "month": month, "path": child_path}
                    )
                count += 1
            elif index >= len(reference):
                if len(examples) < _MAX_DIFFERENCES:
                    examples.append(
                        {"kind": "unexpected_in_candidate", "month": month, "path": child_path}
                    )
                count += 1
            else:
                count += _collect_differences(
                    reference[index], candidate[index], child_path, month, examples
                )
        return count
    if reference != candidate:
        if len(examples) < _MAX_DIFFERENCES:
            examples.append({"kind": "value_mismatch", "month": month, "path": path or "/"})
        return 1
    return 0


def compare_submission(
    *,
    reference_path: Path,
    validation_artifact_path: Path,
    input_manifest_path: Path,
    candidate_path: Path,
    submission_path: Path,
    generated_at: str,
    artifact_path: Path,
) -> ComparisonResult:
    """Compare only after a sealed candidate exists; never close VD-001 automatically."""
    manifest = verify_packet(input_manifest_path)
    candidate = load_cleanroom_sequence(
        candidate_path,
        manifest.start_month,
        manifest.end_month,
    )
    submission = load_submission(submission_path)
    implementation_id = _validate_seal(
        submission.payload,
        candidate,
        manifest.sha256,
        manifest.output_contract_sha256,
    )
    reference_bytes = read_regular_file(reference_path)
    criteria_version, check_count = _validate_reference_artifact(
        validation_artifact_path,
        reference_bytes,
    )
    reference = _project_reference(
        reference_bytes,
        manifest.start_month,
        manifest.end_month,
    )
    compared_at = validate_generated_at(generated_at)
    submission_generated_at = cast(str, submission.payload["generated_at"])
    if compared_at <= submission_generated_at:
        raise CleanRoomError("comparison timestamp must follow the submission seal")

    differences: list[dict[str, JsonValue]] = []
    difference_count = 0
    for reference_record, candidate_record in zip(
        reference.records, candidate.records, strict=True
    ):
        difference_count += _collect_differences(
            reference_record,
            candidate_record,
            "",
            cast(str, reference_record["month"]),
            differences,
        )
    exact_match = reference.artifact_bytes == candidate.artifact_bytes
    if exact_match != (difference_count == 0):
        raise CleanRoomError("comparison byte and semantic results are contradictory")
    verdict = "exact_match" if exact_match else "different"
    difference_values: list[JsonValue] = list(differences)
    payload: dict[str, JsonValue] = {
        "candidate": {
            "byte_count": len(candidate.artifact_bytes),
            "record_count": len(candidate.records),
            "sha256": candidate.sha256,
        },
        "comparison": {
            "difference_count": difference_count,
            "differences": difference_values,
            "differences_truncated": difference_count > len(differences),
            "exact_canonical_bytes": exact_match,
            "verdict": verdict,
        },
        "decision_boundary": {
            "automatic_debt_change": False,
            "owner_review_required": True,
            "vd_001_status": ("open_pending_human_review" if exact_match else "open_conflicting"),
        },
        "generated_at": compared_at,
        "implementation_id": implementation_id,
        "input_manifest_sha256": manifest.sha256,
        "protocol_version": PROTOCOL_VERSION,
        "reference": {
            "checker_check_count": check_count,
            "checker_criteria_version": criteria_version,
            "checker_label": "Verified",
            "projection_byte_count": len(reference.artifact_bytes),
            "projection_record_count": len(reference.records),
            "projection_sha256": reference.sha256,
        },
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "submission_seal_sha256": submission.sha256,
    }
    artifact_bytes = canonical_json_bytes(payload)
    created = write_once(artifact_path, artifact_bytes)
    return ComparisonResult(artifact_path, artifact_bytes, verdict, exact_match, created)
