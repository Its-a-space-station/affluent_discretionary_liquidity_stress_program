"""Frozen, reference-free clean-room packet preparation."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .contracts import (
    FROZEN_MONTH_SCHEMA_VERSION,
    INPUT_MANIFEST_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    CleanRoomError,
    JsonValue,
    ManifestDocument,
    canonical_json_bytes,
    descriptor_map,
    digest_file,
    load_input_manifest,
    month_count,
    validate_generated_at,
    validate_month,
)


@dataclass(frozen=True)
class PacketSources:
    cache_path: Path
    umich_workbook_path: Path
    umich_release_calendar_path: Path
    archive_log_path: Path
    indicator_basket_path: Path
    composite_spec_path: Path
    spec_errata_path: Path
    protocol_path: Path
    frozen_month_contract_path: Path
    input_manifest_contract_path: Path
    submission_contract_path: Path


@dataclass(frozen=True)
class PreparedPacket:
    packet_path: Path
    manifest_path: Path
    manifest_sha256: str
    created: bool


@dataclass(frozen=True)
class _CopySpec:
    artifact_id: str
    source_path: Path
    packet_path: str
    classification: str
    media_type: str
    sqlite_snapshot: bool = False


_FIXED_SPECIFICATION_NAMES = {
    "clean_room_frozen_month_contract": "clean_room_frozen_month.schema.json",
    "clean_room_input_manifest_contract": "clean_room_input_manifest.schema.json",
    "clean_room_protocol": "clean_room_verification.md",
    "clean_room_submission_contract": "clean_room_submission.schema.json",
    "composite_spec_v1": "composite_spec_v1.md",
    "indicator_basket_v1": "indicator_basket_proposal.md",
    "spec_errata": "spec_errata.md",
}


def _copy_specs(sources: PacketSources) -> tuple[tuple[_CopySpec, ...], tuple[_CopySpec, ...]]:
    specifications = (
        _CopySpec(
            "indicator_basket_v1",
            sources.indicator_basket_path,
            "spec/indicator_basket_proposal.md",
            "public_specification",
            "text/markdown",
        ),
        _CopySpec(
            "composite_spec_v1",
            sources.composite_spec_path,
            "spec/composite_spec_v1.md",
            "public_specification",
            "text/markdown",
        ),
        _CopySpec(
            "spec_errata",
            sources.spec_errata_path,
            "spec/spec_errata.md",
            "public_specification",
            "text/markdown",
        ),
        _CopySpec(
            "clean_room_protocol",
            sources.protocol_path,
            "spec/clean_room_verification.md",
            "public_specification",
            "text/markdown",
        ),
        _CopySpec(
            "clean_room_frozen_month_contract",
            sources.frozen_month_contract_path,
            "spec/clean_room_frozen_month.schema.json",
            "public_specification",
            "application/schema+json",
        ),
        _CopySpec(
            "clean_room_input_manifest_contract",
            sources.input_manifest_contract_path,
            "spec/clean_room_input_manifest.schema.json",
            "public_specification",
            "application/schema+json",
        ),
        _CopySpec(
            "clean_room_submission_contract",
            sources.submission_contract_path,
            "spec/clean_room_submission.schema.json",
            "public_specification",
            "application/schema+json",
        ),
    )
    evidence = (
        _CopySpec(
            "alfred_vintage_cache",
            sources.cache_path,
            "evidence/alfred_vintage_cache.sqlite",
            "internal_research_evidence",
            "application/vnd.sqlite3",
            sqlite_snapshot=True,
        ),
        _CopySpec(
            "umich_historical_workbook",
            sources.umich_workbook_path,
            "evidence/umich_historical_workbook.xls",
            "internal_use_only",
            "application/vnd.ms-excel",
        ),
        _CopySpec(
            "umich_release_calendar",
            sources.umich_release_calendar_path,
            "evidence/umich_release_calendar.pdf",
            "internal_use_only",
            "application/pdf",
        ),
        _CopySpec(
            "umich_archive_log",
            sources.archive_log_path,
            "evidence/umich_archive_log.md",
            "internal_research_evidence",
            "text/markdown",
        ),
    )
    return specifications, evidence


def _assert_source_shape(spec: _CopySpec) -> None:
    if spec.source_path.is_symlink():
        raise CleanRoomError(f"packet source {spec.source_path.name!r} cannot be a symlink")
    if not spec.source_path.is_file():
        raise CleanRoomError(f"packet source {spec.source_path.name!r} is not a regular file")
    expected_name = _FIXED_SPECIFICATION_NAMES.get(spec.artifact_id)
    if expected_name is not None and spec.source_path.name != expected_name:
        raise CleanRoomError(
            f"{spec.artifact_id} must come from the approved file {expected_name!r}"
        )
    suffix = spec.source_path.suffix.lower()
    if spec.artifact_id == "alfred_vintage_cache" and suffix not in {".sqlite", ".db"}:
        raise CleanRoomError("ALFRED cache must be an explicit SQLite file")
    if spec.artifact_id == "umich_historical_workbook" and suffix not in {".xls", ".xlsx"}:
        raise CleanRoomError("UMich workbook must be an Excel file")
    if spec.artifact_id == "umich_release_calendar" and suffix != ".pdf":
        raise CleanRoomError("UMich release calendar must be a PDF")
    if spec.artifact_id == "umich_archive_log" and spec.source_path.name != "ARCHIVE_LOG.md":
        raise CleanRoomError("UMich provenance source must be ARCHIVE_LOG.md")


def _copy_regular(source_path: Path, destination_path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    source_descriptor = os.open(source_path, flags)
    try:
        source_metadata = os.fstat(source_descriptor)
        destination_descriptor = os.open(
            destination_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with (
                os.fdopen(source_descriptor, "rb", closefd=False) as source,
                os.fdopen(destination_descriptor, "wb", closefd=False) as destination,
            ):
                shutil.copyfileobj(source, destination, length=1024 * 1024)
                destination.flush()
                os.fsync(destination_descriptor)
        finally:
            os.close(destination_descriptor)
        after = os.fstat(source_descriptor)
    finally:
        os.close(source_descriptor)
    if (
        source_metadata.st_ino,
        source_metadata.st_size,
        source_metadata.st_mtime_ns,
    ) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise CleanRoomError(f"packet source {source_path.name!r} changed while copied")


def _snapshot_sqlite(source_path: Path, destination_path: Path) -> None:
    source: sqlite3.Connection | None = None
    destination: sqlite3.Connection | None = None
    try:
        source = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
        source.execute("PRAGMA query_only = ON")
        source.execute("BEGIN")
        destination = sqlite3.connect(destination_path)
        source.backup(destination)
        result = destination.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise CleanRoomError("frozen ALFRED cache failed SQLite integrity_check")
        destination.commit()
    except sqlite3.Error as exc:
        raise CleanRoomError(f"cannot freeze ALFRED SQLite evidence: {exc}") from exc
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
    os.chmod(destination_path, 0o600)


def _descriptor(spec: _CopySpec, packet_root: Path) -> dict[str, JsonValue]:
    digest = digest_file(packet_root / spec.packet_path)
    return {
        "artifact_id": spec.artifact_id,
        "byte_count": digest.byte_count,
        "classification": spec.classification,
        "media_type": spec.media_type,
        "packet_path": spec.packet_path,
        "sha256": digest.sha256,
    }


def verify_packet(manifest_path: Path) -> ManifestDocument:
    manifest = load_input_manifest(manifest_path)
    if manifest_path.parent.is_symlink():
        raise CleanRoomError("clean-room packet root cannot be a symlink")
    root = manifest_path.parent.resolve()
    if not root.is_dir():
        raise CleanRoomError("clean-room packet root must be a real directory")
    if root.stat().st_mode & 0o077:
        raise CleanRoomError(
            "clean-room packet root permissions must not allow group/world access"
        )
    if manifest_path.stat().st_mode & 0o077:
        raise CleanRoomError("INPUT_MANIFEST.json permissions allow group/world access")
    descriptors = descriptor_map(manifest)
    expected_files = {"INPUT_MANIFEST.json"}
    expected_files.update(
        cast(str, descriptor["packet_path"]) for descriptor in descriptors.values()
    )
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for entry in manifest_path.parent.rglob("*"):
        relative = entry.relative_to(manifest_path.parent).as_posix()
        if entry.is_symlink():
            raise CleanRoomError(f"packet entry {relative!r} cannot be a symlink")
        if entry.is_dir():
            actual_directories.add(relative)
        elif entry.is_file():
            actual_files.add(relative)
        else:
            raise CleanRoomError(f"packet entry {relative!r} is not a regular file")
    if actual_directories != {"evidence", "spec"}:
        raise CleanRoomError("clean-room packet contains unexpected directories")
    if actual_files != expected_files:
        raise CleanRoomError("clean-room packet contains missing or unexpected files")
    for artifact_id, descriptor in sorted(descriptors.items()):
        relative = cast(str, descriptor["packet_path"])
        candidate = manifest_path.parent / relative
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise CleanRoomError(f"packet artifact {artifact_id} escapes the packet root")
        if candidate.stat().st_mode & 0o077:
            raise CleanRoomError(f"packet artifact {artifact_id} allows group/world access")
        digest = digest_file(candidate)
        if digest.byte_count != descriptor["byte_count"] or digest.sha256 != descriptor["sha256"]:
            raise CleanRoomError(f"packet artifact {artifact_id} differs from INPUT_MANIFEST.json")
    cache_descriptor = descriptors["alfred_vintage_cache"]
    cache_path = manifest_path.parent / cast(str, cache_descriptor["packet_path"])
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"{cache_path.resolve().as_uri()}?mode=ro", uri=True)
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise CleanRoomError("packet ALFRED cache failed SQLite integrity_check")
    except sqlite3.Error as exc:
        raise CleanRoomError(f"cannot verify packet ALFRED cache: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()
    return manifest


def prepare_packet(
    sources: PacketSources,
    output_dir: Path,
    *,
    start_month: str,
    end_month: str,
    generated_at: str,
) -> PreparedPacket:
    """Create one immutable local packet that contains no reference output."""
    validate_month(start_month, "start_month")
    validate_month(end_month, "end_month")
    expected_month_count = month_count(start_month, end_month)
    validate_generated_at(generated_at)
    specifications, evidence = _copy_specs(sources)
    for spec in (*specifications, *evidence):
        _assert_source_shape(spec)

    if output_dir.exists() or output_dir.is_symlink():
        raise CleanRoomError(f"clean-room packet directory {output_dir.name!r} already exists")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".adls-cleanroom-", dir=output_dir.parent))
    os.chmod(temporary, 0o700)
    try:
        (temporary / "spec").mkdir(mode=0o700)
        (temporary / "evidence").mkdir(mode=0o700)
        for spec in (*specifications, *evidence):
            destination = temporary / spec.packet_path
            if spec.sqlite_snapshot:
                _snapshot_sqlite(spec.source_path, destination)
            else:
                _copy_regular(spec.source_path, destination)
            os.chmod(destination, 0o600)

        specification_descriptors = [_descriptor(spec, temporary) for spec in specifications]
        evidence_descriptors = [_descriptor(spec, temporary) for spec in evidence]
        contract_descriptor = next(
            descriptor
            for descriptor in specification_descriptors
            if descriptor["artifact_id"] == "clean_room_frozen_month_contract"
        )
        specification_values: list[JsonValue] = list(specification_descriptors)
        evidence_values: list[JsonValue] = list(evidence_descriptors)
        payload: dict[str, JsonValue] = {
            "controls": {
                "contains_adls_source_or_tests": False,
                "contains_reference_output": False,
                "historical_umich_assumption": "unrevised_final_values",
                "licensed_evidence_must_remain_internal": True,
                "reference_withheld_until_submission_sealed": True,
            },
            "evidence": evidence_values,
            "generated_at": generated_at,
            "output_contract": {
                "artifact_id": "clean_room_frozen_month_contract",
                "schema_version": FROZEN_MONTH_SCHEMA_VERSION,
                "sha256": cast(str, contract_descriptor["sha256"]),
            },
            "protocol_version": PROTOCOL_VERSION,
            "reconstruction_window": {
                "end_month": end_month,
                "expected_month_count": expected_month_count,
                "start_month": start_month,
            },
            "schema_version": INPUT_MANIFEST_SCHEMA_VERSION,
            "specifications": specification_values,
        }
        manifest_path = temporary / "INPUT_MANIFEST.json"
        manifest_path.write_bytes(canonical_json_bytes(payload))
        os.chmod(manifest_path, 0o600)
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    final_manifest_path = output_dir / "INPUT_MANIFEST.json"
    manifest = verify_packet(final_manifest_path)
    return PreparedPacket(output_dir, final_manifest_path, manifest.sha256, True)
