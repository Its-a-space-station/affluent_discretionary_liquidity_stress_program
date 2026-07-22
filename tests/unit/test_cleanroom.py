from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from adls.cleanroom import (
    CleanRoomError,
    PacketSources,
    compare_submission,
    prepare_packet,
    seal_submission,
    verify_packet,
)
from adls.cleanroom.contracts import canonical_json_bytes


def _write_packet_sources(tmp_path: Path) -> PacketSources:
    tmp_path.mkdir(parents=True, exist_ok=True)
    cache_path = tmp_path / "source.sqlite"
    connection = sqlite3.connect(cache_path)
    connection.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO evidence(value) VALUES ('source-value')")
    connection.commit()
    connection.close()

    workbook = tmp_path / "umich.xls"
    release_calendar = tmp_path / "releases.pdf"
    archive_log = tmp_path / "ARCHIVE_LOG.md"
    workbook.write_bytes(b"synthetic workbook bytes\n")
    release_calendar.write_bytes(b"%PDF-1.4\nsynthetic calendar\n")
    archive_log.write_text("# Synthetic provenance\n", encoding="utf-8")

    specification_paths: dict[str, Path] = {}
    for name in (
        "indicator_basket_proposal.md",
        "composite_spec_v1.md",
        "spec_errata.md",
        "clean_room_verification.md",
        "clean_room_frozen_month.schema.json",
        "clean_room_input_manifest.schema.json",
        "clean_room_submission.schema.json",
    ):
        path = tmp_path / name
        path.write_text("{}\n" if name.endswith(".json") else f"# {name}\n", encoding="utf-8")
        specification_paths[name] = path

    return PacketSources(
        cache_path=cache_path,
        umich_workbook_path=workbook,
        umich_release_calendar_path=release_calendar,
        archive_log_path=archive_log,
        indicator_basket_path=specification_paths["indicator_basket_proposal.md"],
        composite_spec_path=specification_paths["composite_spec_v1.md"],
        spec_errata_path=specification_paths["spec_errata.md"],
        protocol_path=specification_paths["clean_room_verification.md"],
        frozen_month_contract_path=specification_paths["clean_room_frozen_month.schema.json"],
        input_manifest_contract_path=specification_paths["clean_room_input_manifest.schema.json"],
        submission_contract_path=specification_paths["clean_room_submission.schema.json"],
    )


def _prepare_packet(tmp_path: Path, *, name: str = "packet") -> Path:
    result = prepare_packet(
        _write_packet_sources(tmp_path),
        tmp_path / name,
        start_month="2020-04",
        end_month="2020-04",
        generated_at="2026-07-22T15:00:00Z",
    )
    return result.manifest_path


def _cleanroom_record(*, tier_a_value: str = "1.000000") -> dict[str, object]:
    family_states = {
        "census_retail": {
            "abstained": False,
            "flags": [],
            "z_score": Decimal("0.100000"),
        },
        "household_liquidity": {
            "abstained": False,
            "flags": [],
            "z_score": Decimal("0.200000"),
        },
        "umich_top_tercile": {
            "abstained": False,
            "flags": ["validation_assumption:umich_unrevised_final"],
            "z_score": Decimal("0.300000"),
        },
    }
    return {
        "band": {
            "candidate_band": None,
            "candidate_count": 0,
            "confirmed_band": None,
            "eligible": False,
            "published_band": None,
            "raw_band": None,
            "reference_count": 0,
            "thresholds": None,
        },
        "families": family_states,
        "finalized_on": "2020-06-19",
        "historical_umich_final_assumption": True,
        "input_vintages": {
            "DPSACBW027SBOG": "2020-06-17",
            "RSFHFS": "2020-06-16",
            "RSFSDP": "2020-06-16",
            "UMICH_SCA_T2N_TOP": "2020-05-29",
            "WRMFNS": "2020-06-18",
        },
        "month": "2020-04",
        "schema_version": "adls.cleanroom.frozen-month.v1",
        "tier_a_abstained": False,
        "tier_a_value": Decimal(tier_a_value),
    }


def _write_candidate(path: Path, *, tier_a_value: str = "1.000000") -> None:
    path.write_bytes(canonical_json_bytes(_cleanroom_record(tier_a_value=tier_a_value)))


def _write_reference(reference_path: Path, validation_path: Path) -> None:
    projected = _cleanroom_record()
    reference = {
        "assembly_flags": ["validation_assumption:umich_unrevised_final"],
        "band": projected["band"],
        "composite": {"tier_a_value": projected["tier_a_value"]},
        "families": projected["families"],
        "finalized_on": projected["finalized_on"],
        "input_vintages": projected["input_vintages"],
        "month": projected["month"],
        "schema_version": "adls.frozen.month.v1",
    }
    reference_bytes = canonical_json_bytes(reference)
    reference_path.write_bytes(reference_bytes)
    validation_path.write_bytes(
        canonical_json_bytes(
            {
                "source": {
                    "checker_check_count": 2,
                    "checker_criteria_version": "adls.checker.validation-assumption.v1",
                    "checker_label": "Verified",
                    "frozen_equivalent_sha256": hashlib.sha256(reference_bytes).hexdigest(),
                },
                "verification_debt": ["VD-001"],
            }
        )
    )


def _seal(
    manifest_path: Path,
    candidate_path: Path,
    submission_path: Path,
) -> None:
    seal_submission(
        input_manifest_path=manifest_path,
        candidate_path=candidate_path,
        implementation_id="independent-fixture-v1",
        generated_at="2026-07-22T16:00:00Z",
        artifact_path=submission_path,
        attest_clean_room=True,
    )


def test_packet_is_frozen_reference_free_and_path_independent(tmp_path: Path) -> None:
    first_sources = _write_packet_sources(tmp_path / "first-sources")
    second_sources = _write_packet_sources(tmp_path / "second-sources")
    first = prepare_packet(
        first_sources,
        tmp_path / "first-packet",
        start_month="2020-04",
        end_month="2020-04",
        generated_at="2026-07-22T15:00:00Z",
    )
    second = prepare_packet(
        second_sources,
        tmp_path / "second-packet",
        start_month="2020-04",
        end_month="2020-04",
        generated_at="2026-07-22T15:00:00Z",
    )

    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    assert first.manifest_sha256 == second.manifest_sha256
    manifest_text = first.manifest_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in manifest_text
    assert "validation_frozen_equivalent" not in manifest_text
    assert '"contains_reference_output":false' in manifest_text
    assert not (first.packet_path.stat().st_mode & 0o077)
    assert verify_packet(first.manifest_path).expected_month_count == 1


def test_packet_refuses_existing_directory_symlinks_and_tampering(tmp_path: Path) -> None:
    sources = _write_packet_sources(tmp_path)
    output = tmp_path / "packet"
    prepared = prepare_packet(
        sources,
        output,
        start_month="2020-04",
        end_month="2020-04",
        generated_at="2026-07-22T15:00:00Z",
    )

    with pytest.raises(CleanRoomError, match="already exists"):
        prepare_packet(
            sources,
            output,
            start_month="2020-04",
            end_month="2020-04",
            generated_at="2026-07-22T15:00:00Z",
        )

    workbook = output / "evidence" / "umich_historical_workbook.xls"
    workbook.write_bytes(b"tampered\n")
    with pytest.raises(CleanRoomError, match="differs from INPUT_MANIFEST"):
        verify_packet(prepared.manifest_path)

    symlink = tmp_path / "linked.xls"
    symlink.symlink_to(sources.umich_workbook_path)
    linked_sources = replace(sources, umich_workbook_path=symlink)
    with pytest.raises(CleanRoomError, match="symlink"):
        prepare_packet(
            linked_sources,
            tmp_path / "linked-packet",
            start_month="2020-04",
            end_month="2020-04",
            generated_at="2026-07-22T15:00:00Z",
        )

    extra_manifest = _prepare_packet(tmp_path / "extra-case")
    (extra_manifest.parent / "reference.jsonl").write_text("not allowed\n", encoding="utf-8")
    with pytest.raises(CleanRoomError, match="unexpected files"):
        verify_packet(extra_manifest)

    permissions_manifest = _prepare_packet(tmp_path / "permissions-case")
    contract = permissions_manifest.parent / "spec" / "clean_room_frozen_month.schema.json"
    contract.chmod(0o644)
    with pytest.raises(CleanRoomError, match="group/world access"):
        verify_packet(permissions_manifest)

    classification_manifest = _prepare_packet(tmp_path / "classification-case")
    payload = json.loads(classification_manifest.read_bytes())
    workbook_descriptor = next(
        descriptor
        for descriptor in payload["evidence"]
        if descriptor["artifact_id"] == "umich_historical_workbook"
    )
    workbook_descriptor["classification"] = "public_specification"
    classification_manifest.write_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    with pytest.raises(CleanRoomError, match="descriptor contract"):
        verify_packet(classification_manifest)


def test_seal_requires_attestation_and_canonical_candidate(tmp_path: Path) -> None:
    manifest_path = _prepare_packet(tmp_path)
    candidate_path = tmp_path / "candidate.jsonl"
    _write_candidate(candidate_path)

    with pytest.raises(CleanRoomError, match="attestation"):
        seal_submission(
            input_manifest_path=manifest_path,
            candidate_path=candidate_path,
            implementation_id="candidate-v1",
            generated_at="2026-07-22T16:00:00Z",
            artifact_path=tmp_path / "seal.json",
            attest_clean_room=False,
        )

    candidate_path.write_bytes(candidate_path.read_bytes().replace(b"1.000000", b"1.0"))
    with pytest.raises(CleanRoomError, match="not canonical JSON"):
        seal_submission(
            input_manifest_path=manifest_path,
            candidate_path=candidate_path,
            implementation_id="candidate-v1",
            generated_at="2026-07-22T16:00:00Z",
            artifact_path=tmp_path / "seal.json",
            attest_clean_room=True,
        )

    _write_candidate(candidate_path)
    candidate_path.write_bytes(candidate_path.read_bytes().replace(b"1.000000", b"1e999999"))
    with pytest.raises(CleanRoomError, match="decimal bounds"):
        seal_submission(
            input_manifest_path=manifest_path,
            candidate_path=candidate_path,
            implementation_id="candidate-v1",
            generated_at="2026-07-22T16:00:00Z",
            artifact_path=tmp_path / "seal.json",
            attest_clean_room=True,
        )


def test_seal_and_comparison_timestamps_are_strictly_ordered(tmp_path: Path) -> None:
    manifest_path = _prepare_packet(tmp_path)
    candidate_path = tmp_path / "candidate.jsonl"
    _write_candidate(candidate_path)

    with pytest.raises(CleanRoomError, match="must follow packet"):
        seal_submission(
            input_manifest_path=manifest_path,
            candidate_path=candidate_path,
            implementation_id="candidate-v1",
            generated_at="2026-07-22T15:00:00Z",
            artifact_path=tmp_path / "seal.json",
            attest_clean_room=True,
        )

    submission_path = tmp_path / "submission.json"
    reference_path = tmp_path / "reference.jsonl"
    validation_path = tmp_path / "validation.json"
    _seal(manifest_path, candidate_path, submission_path)
    _write_reference(reference_path, validation_path)
    with pytest.raises(CleanRoomError, match="must follow the submission"):
        compare_submission(
            reference_path=reference_path,
            validation_artifact_path=validation_path,
            input_manifest_path=manifest_path,
            candidate_path=candidate_path,
            submission_path=submission_path,
            generated_at="2026-07-22T16:00:00Z",
            artifact_path=tmp_path / "comparison.json",
        )


def test_exact_comparison_stays_open_for_owner_review(tmp_path: Path) -> None:
    manifest_path = _prepare_packet(tmp_path)
    candidate_path = tmp_path / "candidate.jsonl"
    submission_path = tmp_path / "submission.json"
    reference_path = tmp_path / "reference.jsonl"
    validation_path = tmp_path / "validation.json"
    comparison_path = tmp_path / "comparison.json"
    _write_candidate(candidate_path)
    _seal(manifest_path, candidate_path, submission_path)
    _write_reference(reference_path, validation_path)

    result = compare_submission(
        reference_path=reference_path,
        validation_artifact_path=validation_path,
        input_manifest_path=manifest_path,
        candidate_path=candidate_path,
        submission_path=submission_path,
        generated_at="2026-07-22T17:00:00Z",
        artifact_path=comparison_path,
    )

    assert result.exact_match
    assert result.verdict == "exact_match"
    payload = json.loads(result.artifact_bytes)
    assert payload["comparison"]["difference_count"] == 0
    assert payload["decision_boundary"] == {
        "automatic_debt_change": False,
        "owner_review_required": True,
        "vd_001_status": "open_pending_human_review",
    }


def test_mismatch_report_names_paths_without_echoing_values(tmp_path: Path) -> None:
    manifest_path = _prepare_packet(tmp_path)
    candidate_path = tmp_path / "candidate.jsonl"
    submission_path = tmp_path / "submission.json"
    reference_path = tmp_path / "reference.jsonl"
    validation_path = tmp_path / "validation.json"
    _write_candidate(candidate_path, tier_a_value="2.000000")
    _seal(manifest_path, candidate_path, submission_path)
    _write_reference(reference_path, validation_path)

    result = compare_submission(
        reference_path=reference_path,
        validation_artifact_path=validation_path,
        input_manifest_path=manifest_path,
        candidate_path=candidate_path,
        submission_path=submission_path,
        generated_at="2026-07-22T17:00:00Z",
        artifact_path=tmp_path / "comparison.json",
    )

    assert not result.exact_match
    payload = json.loads(result.artifact_bytes)
    assert payload["comparison"]["differences"] == [
        {"kind": "value_mismatch", "month": "2020-04", "path": "/tier_a_value"}
    ]
    report_text = result.artifact_bytes.decode("utf-8")
    assert "1.000000" not in report_text
    assert "2.000000" not in report_text
    assert payload["decision_boundary"]["vd_001_status"] == "open_conflicting"


def test_post_seal_candidate_mutation_and_unverified_reference_are_rejected(
    tmp_path: Path,
) -> None:
    manifest_path = _prepare_packet(tmp_path)
    candidate_path = tmp_path / "candidate.jsonl"
    submission_path = tmp_path / "submission.json"
    reference_path = tmp_path / "reference.jsonl"
    validation_path = tmp_path / "validation.json"
    _write_candidate(candidate_path)
    _seal(manifest_path, candidate_path, submission_path)
    _write_reference(reference_path, validation_path)

    _write_candidate(candidate_path, tier_a_value="2.000000")
    with pytest.raises(CleanRoomError, match="pre-disclosure seal"):
        compare_submission(
            reference_path=reference_path,
            validation_artifact_path=validation_path,
            input_manifest_path=manifest_path,
            candidate_path=candidate_path,
            submission_path=submission_path,
            generated_at="2026-07-22T17:00:00Z",
            artifact_path=tmp_path / "comparison.json",
        )

    _write_candidate(candidate_path)
    validation = json.loads(validation_path.read_bytes())
    validation["source"]["checker_label"] = "Unverified"
    validation_path.write_bytes(
        json.dumps(validation, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    with pytest.raises(CleanRoomError, match="not Verified"):
        compare_submission(
            reference_path=reference_path,
            validation_artifact_path=validation_path,
            input_manifest_path=manifest_path,
            candidate_path=candidate_path,
            submission_path=submission_path,
            generated_at="2026-07-22T17:00:00Z",
            artifact_path=tmp_path / "comparison.json",
        )


def test_committed_clean_room_contracts_are_valid_json() -> None:
    root = Path(__file__).resolve().parents[2]
    for name in (
        "clean_room_frozen_month.schema.json",
        "clean_room_input_manifest.schema.json",
        "clean_room_submission.schema.json",
    ):
        payload = json.loads((root / "docs" / name).read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_packet_permissions_are_not_relaxed_by_process_umask(tmp_path: Path) -> None:
    previous = os.umask(0)
    try:
        manifest_path = _prepare_packet(tmp_path)
    finally:
        os.umask(previous)

    assert not (manifest_path.parent.stat().st_mode & 0o077)
    assert not (manifest_path.stat().st_mode & 0o077)
