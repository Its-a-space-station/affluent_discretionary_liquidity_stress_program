"""Clean-room canonical bytes and input/output contract validation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, DecimalException
from pathlib import Path, PurePosixPath
from typing import TypeAlias, cast

PROTOCOL_VERSION = "adls.cleanroom.protocol.v1"
INPUT_MANIFEST_SCHEMA_VERSION = "adls.cleanroom.input-manifest.v1"
FROZEN_MONTH_SCHEMA_VERSION = "adls.cleanroom.frozen-month.v1"
SUBMISSION_SCHEMA_VERSION = "adls.cleanroom.submission.v1"
COMPARISON_SCHEMA_VERSION = "adls.cleanroom.comparison.v1"

TIER_A_FAMILIES = (
    "census_retail",
    "household_liquidity",
    "umich_top_tercile",
)
TIER_A_SERIES = (
    "DPSACBW027SBOG",
    "RSFHFS",
    "RSFSDP",
    "UMICH_SCA_T2N_TOP",
    "WRMFNS",
)
BAND_NAMES = frozenset(("Normal", "Watch", "Elevated", "High"))
DESCRIPTOR_CONTRACTS = {
    "alfred_vintage_cache": (
        "evidence/alfred_vintage_cache.sqlite",
        "internal_research_evidence",
        "application/vnd.sqlite3",
    ),
    "clean_room_frozen_month_contract": (
        "spec/clean_room_frozen_month.schema.json",
        "public_specification",
        "application/schema+json",
    ),
    "clean_room_input_manifest_contract": (
        "spec/clean_room_input_manifest.schema.json",
        "public_specification",
        "application/schema+json",
    ),
    "clean_room_protocol": (
        "spec/clean_room_verification.md",
        "public_specification",
        "text/markdown",
    ),
    "clean_room_submission_contract": (
        "spec/clean_room_submission.schema.json",
        "public_specification",
        "application/schema+json",
    ),
    "composite_spec_v1": (
        "spec/composite_spec_v1.md",
        "public_specification",
        "text/markdown",
    ),
    "indicator_basket_v1": (
        "spec/indicator_basket_proposal.md",
        "public_specification",
        "text/markdown",
    ),
    "spec_errata": (
        "spec/spec_errata.md",
        "public_specification",
        "text/markdown",
    ),
    "umich_archive_log": (
        "evidence/umich_archive_log.md",
        "internal_research_evidence",
        "text/markdown",
    ),
    "umich_historical_workbook": (
        "evidence/umich_historical_workbook.xls",
        "internal_use_only",
        "application/vnd.ms-excel",
    ),
    "umich_release_calendar": (
        "evidence/umich_release_calendar.pdf",
        "internal_use_only",
        "application/pdf",
    ),
}
SPECIFICATION_IDS = frozenset(
    (
        "clean_room_frozen_month_contract",
        "clean_room_input_manifest_contract",
        "clean_room_protocol",
        "clean_room_submission_contract",
        "composite_spec_v1",
        "indicator_basket_v1",
        "spec_errata",
    )
)
EVIDENCE_IDS = frozenset(
    (
        "alfred_vintage_cache",
        "umich_archive_log",
        "umich_historical_workbook",
        "umich_release_calendar",
    )
)

_SIX_PLACES = Decimal("0.000001")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_ID = re.compile(r"^[a-z0-9_]+$")
_IMPLEMENTATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_MAX_SMALL_FILE_BYTES = 16 * 1024 * 1024
_MAX_SEQUENCE_BYTES = 16 * 1024 * 1024

JsonValue: TypeAlias = (
    None | bool | int | Decimal | str | list["JsonValue"] | dict[str, "JsonValue"]
)


class CleanRoomError(ValueError):
    """A clean-room artifact violates the frozen protocol."""


@dataclass(frozen=True)
class FileDigest:
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class ManifestDocument:
    payload: dict[str, JsonValue]
    artifact_bytes: bytes
    sha256: str
    start_month: str
    end_month: str
    expected_month_count: int
    output_contract_sha256: str


@dataclass(frozen=True)
class SequenceDocument:
    records: tuple[dict[str, JsonValue], ...]
    artifact_bytes: bytes
    sha256: str
    first_month: str
    last_month: str


@dataclass(frozen=True)
class SubmissionDocument:
    payload: dict[str, JsonValue]
    artifact_bytes: bytes
    sha256: str


def _reject_constant(value: str) -> None:
    raise CleanRoomError(f"non-finite JSON number {value!r} is forbidden")


def _reject_duplicate_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise CleanRoomError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _render_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise CleanRoomError("canonical JSON cannot contain non-finite numbers")
    try:
        rounded = value.quantize(_SIX_PLACES, rounding=ROUND_HALF_EVEN)
    except DecimalException as exc:
        raise CleanRoomError("canonical JSON number exceeds decimal bounds") from exc
    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, "f")


def _render(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return _render_decimal(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(_render(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                f"{json.dumps(key, ensure_ascii=False)}:{_render(value[key])}"
                for key in sorted(value)
            )
            + "}"
        )
    raise CleanRoomError(f"unsupported canonical JSON value {type(value).__name__}")


def canonical_json_bytes(payload: dict[str, JsonValue]) -> bytes:
    """Return protocol-canonical JSON with one trailing LF."""
    try:
        return (_render(payload) + "\n").encode("utf-8")
    except (RecursionError, UnicodeError) as exc:
        raise CleanRoomError("canonical JSON contains invalid recursive or Unicode data") from exc


def parse_json_object(data: bytes, label: str, *, require_canonical: bool) -> dict[str, JsonValue]:
    if len(data) > _MAX_SMALL_FILE_BYTES:
        raise CleanRoomError(f"{label} exceeds the clean-room size limit")
    try:
        text = data.decode("utf-8")
        parsed = json.loads(
            text,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise CleanRoomError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise CleanRoomError(f"{label} must be a JSON object")
    result = cast(dict[str, JsonValue], parsed)
    if require_canonical and canonical_json_bytes(result) != data:
        raise CleanRoomError(f"{label} is not canonical JSON")
    return result


def _open_regular(path: Path) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CleanRoomError(f"cannot open regular file {path.name!r}: {exc}") from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise CleanRoomError(f"input {path.name!r} must be a regular file")
    return descriptor, metadata


def read_regular_file(path: Path, *, max_bytes: int = _MAX_SMALL_FILE_BYTES) -> bytes:
    descriptor, before = _open_regular(path)
    try:
        if before.st_size > max_bytes:
            raise CleanRoomError(f"input {path.name!r} exceeds the clean-room size limit")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            data = handle.read(max_bytes + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(data) > max_bytes:
        raise CleanRoomError(f"input {path.name!r} exceeds the clean-room size limit")
    if (
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise CleanRoomError(f"input {path.name!r} changed while it was read")
    return data


def digest_file(path: Path) -> FileDigest:
    descriptor, before = _open_regular(path)
    digest = hashlib.sha256()
    byte_count = 0
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                byte_count += len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise CleanRoomError(f"input {path.name!r} changed while it was hashed")
    if byte_count != before.st_size:
        raise CleanRoomError(f"input {path.name!r} changed length while it was hashed")
    return FileDigest(byte_count, digest.hexdigest())


def write_once(path: Path, data: bytes, *, mode: int = 0o600) -> bool:
    """Create an artifact once; an identical existing artifact is idempotent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, mode)
    except FileExistsError:
        existing = read_regular_file(path, max_bytes=max(len(data), 1))
        if existing != data:
            raise CleanRoomError(f"existing artifact {path.name!r} differs") from None
        return False
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(descriptor)
    except OSError:
        with suppress(OSError):
            path.unlink()
        raise
    finally:
        os.close(descriptor)
    os.chmod(path, mode)
    return True


def validate_generated_at(value: str, label: str = "generated_at") -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise CleanRoomError(f"{label} must be canonical UTC second precision") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise CleanRoomError(f"{label} must be canonical UTC second precision")
    return value


def validate_month(value: str, label: str) -> str:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise CleanRoomError(f"{label} must be YYYY-MM") from exc
    if f"{parsed.year:04d}-{parsed.month:02d}" != value:
        raise CleanRoomError(f"{label} must be YYYY-MM")
    return value


def validate_date(value: str, label: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise CleanRoomError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise CleanRoomError(f"{label} must be an ISO date")
    return value


def next_month(value: str) -> str:
    parsed = date.fromisoformat(f"{value}-01")
    year = parsed.year + (1 if parsed.month == 12 else 0)
    month = 1 if parsed.month == 12 else parsed.month + 1
    return f"{year:04d}-{month:02d}"


def month_count(start_month: str, end_month: str) -> int:
    start = date.fromisoformat(f"{validate_month(start_month, 'start_month')}-01")
    end = date.fromisoformat(f"{validate_month(end_month, 'end_month')}-01")
    if start > end:
        raise CleanRoomError("start_month must not follow end_month")
    return (end.year - start.year) * 12 + end.month - start.month + 1


def validate_implementation_id(value: str) -> str:
    if _IMPLEMENTATION_ID.fullmatch(value) is None:
        raise CleanRoomError("implementation_id must match [A-Za-z0-9._-]{1,80}")
    return value


def _expect_mapping(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise CleanRoomError(f"{label} must be an object")
    return value


def _expect_exact_keys(value: dict[str, JsonValue], expected: set[str], label: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise CleanRoomError(f"{label} has {'; '.join(details)}")


def _expect_string(value: JsonValue, label: str) -> str:
    if not isinstance(value, str):
        raise CleanRoomError(f"{label} must be a string")
    return value


def _expect_bool(value: JsonValue, label: str) -> bool:
    if not isinstance(value, bool):
        raise CleanRoomError(f"{label} must be boolean")
    return value


def _expect_int(value: JsonValue, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CleanRoomError(f"{label} must be an integer")
    return value


def _expect_decimal_or_none(value: JsonValue, label: str) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise CleanRoomError(f"{label} must be a six-place decimal or null")
    if not value.is_finite():
        raise CleanRoomError(f"{label} must be finite or null")
    return value


def _expect_sha256(value: JsonValue, label: str) -> str:
    text = _expect_string(value, label)
    if _SHA256.fullmatch(text) is None:
        raise CleanRoomError(f"{label} must be a lowercase SHA-256")
    return text


def _expect_string_array(value: JsonValue, label: str) -> list[JsonValue]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CleanRoomError(f"{label} must be an array of strings")
    return value


def _validate_band_name(value: JsonValue, label: str) -> None:
    if value is not None and value not in BAND_NAMES:
        raise CleanRoomError(f"{label} is not a canonical band")


def validate_frozen_month(record: dict[str, JsonValue], label: str) -> None:
    expected = {
        "band",
        "families",
        "finalized_on",
        "historical_umich_final_assumption",
        "input_vintages",
        "month",
        "schema_version",
        "tier_a_abstained",
        "tier_a_value",
    }
    _expect_exact_keys(record, expected, label)
    if record["schema_version"] != FROZEN_MONTH_SCHEMA_VERSION:
        raise CleanRoomError(f"{label}.schema_version is unsupported")
    validate_month(_expect_string(record["month"], f"{label}.month"), f"{label}.month")
    finalized_on = validate_date(
        _expect_string(record["finalized_on"], f"{label}.finalized_on"),
        f"{label}.finalized_on",
    )
    _expect_bool(
        record["historical_umich_final_assumption"],
        f"{label}.historical_umich_final_assumption",
    )
    abstained = _expect_bool(record["tier_a_abstained"], f"{label}.tier_a_abstained")
    tier_a_value = _expect_decimal_or_none(record["tier_a_value"], f"{label}.tier_a_value")
    if abstained != (tier_a_value is None):
        raise CleanRoomError(f"{label} Tier-A abstention contradicts its value")

    families = _expect_mapping(record["families"], f"{label}.families")
    _expect_exact_keys(families, set(TIER_A_FAMILIES), f"{label}.families")
    for family in TIER_A_FAMILIES:
        state = _expect_mapping(families[family], f"{label}.families.{family}")
        _expect_exact_keys(state, {"abstained", "flags", "z_score"}, f"{label}.families.{family}")
        family_abstained = _expect_bool(state["abstained"], f"{label}.families.{family}.abstained")
        z_score = _expect_decimal_or_none(state["z_score"], f"{label}.families.{family}.z_score")
        _expect_string_array(state["flags"], f"{label}.families.{family}.flags")
        if family_abstained != (z_score is None):
            raise CleanRoomError(f"{label}.families.{family} abstention contradicts z_score")

    vintages = _expect_mapping(record["input_vintages"], f"{label}.input_vintages")
    _expect_exact_keys(vintages, set(TIER_A_SERIES), f"{label}.input_vintages")
    for series_id in TIER_A_SERIES:
        vintage = validate_date(
            _expect_string(vintages[series_id], f"{label}.input_vintages.{series_id}"),
            f"{label}.input_vintages.{series_id}",
        )
        if vintage > finalized_on:
            raise CleanRoomError(f"{label}.input_vintages.{series_id} is after finalization")

    band = _expect_mapping(record["band"], f"{label}.band")
    _expect_exact_keys(
        band,
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
        f"{label}.band",
    )
    eligible = _expect_bool(band["eligible"], f"{label}.band.eligible")
    reference_count = _expect_int(band["reference_count"], f"{label}.band.reference_count")
    candidate_count = _expect_int(band["candidate_count"], f"{label}.band.candidate_count")
    if reference_count < 0 or candidate_count < 0:
        raise CleanRoomError(f"{label}.band counts cannot be negative")
    for name in ("candidate_band", "confirmed_band", "published_band", "raw_band"):
        _validate_band_name(band[name], f"{label}.band.{name}")
    thresholds = band["thresholds"]
    if thresholds is None:
        if eligible:
            raise CleanRoomError(f"{label}.band eligible state requires thresholds")
    else:
        threshold_map = _expect_mapping(thresholds, f"{label}.band.thresholds")
        _expect_exact_keys(threshold_map, {"p70", "p85", "p95"}, f"{label}.band.thresholds")
        values = [
            _expect_decimal_or_none(threshold_map[name], f"{label}.band.thresholds.{name}")
            for name in ("p70", "p85", "p95")
        ]
        if any(value is None for value in values):
            raise CleanRoomError(f"{label}.band thresholds cannot contain null")
        numeric = cast(list[Decimal], values)
        if numeric != sorted(numeric):
            raise CleanRoomError(f"{label}.band thresholds must be nondecreasing")
        if not eligible:
            raise CleanRoomError(f"{label}.band ineligible state cannot carry thresholds")


def _validate_record_window(
    records: tuple[dict[str, JsonValue], ...],
    start_month: str,
    end_month: str,
) -> None:
    expected_count = month_count(start_month, end_month)
    if len(records) != expected_count:
        raise CleanRoomError(
            f"sequence expected {expected_count} records but contains {len(records)}"
        )
    expected_month = start_month
    previous_finalization: str | None = None
    for position, record in enumerate(records, 1):
        label = f"sequence line {position}"
        validate_frozen_month(record, label)
        month = cast(str, record["month"])
        if month != expected_month:
            raise CleanRoomError(f"{label} expected month {expected_month}, found {month}")
        finalized_on = cast(str, record["finalized_on"])
        if previous_finalization is not None and finalized_on <= previous_finalization:
            raise CleanRoomError(f"{label} finalization dates are not strictly increasing")
        previous_finalization = finalized_on
        expected_month = next_month(expected_month)
    if cast(str, records[-1]["month"]) != end_month:
        raise CleanRoomError("sequence does not end at the manifest end_month")


def load_cleanroom_sequence(path: Path, start_month: str, end_month: str) -> SequenceDocument:
    data = read_regular_file(path, max_bytes=_MAX_SEQUENCE_BYTES)
    if not data or not data.endswith(b"\n") or b"\r" in data:
        raise CleanRoomError("candidate sequence must use LF-terminated JSONL")
    lines = data.splitlines(keepends=True)
    if any(line == b"\n" for line in lines):
        raise CleanRoomError("candidate sequence cannot contain blank lines")
    records = tuple(
        parse_json_object(line, f"candidate line {position}", require_canonical=True)
        for position, line in enumerate(lines, 1)
    )
    _validate_record_window(records, start_month, end_month)
    return SequenceDocument(
        records,
        data,
        hashlib.sha256(data).hexdigest(),
        cast(str, records[0]["month"]),
        cast(str, records[-1]["month"]),
    )


def canonical_sequence_bytes(
    records: tuple[dict[str, JsonValue], ...],
    start_month: str,
    end_month: str,
) -> bytes:
    _validate_record_window(records, start_month, end_month)
    return b"".join(canonical_json_bytes(record) for record in records)


def _validate_packet_path(value: str, label: str) -> str:
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or len(candidate.parts) < 2:
        raise CleanRoomError(f"{label} must be a safe packet-relative path")
    if candidate.parts[0] not in {"spec", "evidence"}:
        raise CleanRoomError(f"{label} must be under spec/ or evidence/")
    return value


def _validate_descriptor(value: JsonValue, label: str) -> dict[str, JsonValue]:
    descriptor = _expect_mapping(value, label)
    _expect_exact_keys(
        descriptor,
        {"artifact_id", "byte_count", "classification", "media_type", "packet_path", "sha256"},
        label,
    )
    artifact_id = _expect_string(descriptor["artifact_id"], f"{label}.artifact_id")
    if _ARTIFACT_ID.fullmatch(artifact_id) is None:
        raise CleanRoomError(f"{label}.artifact_id is invalid")
    byte_count = _expect_int(descriptor["byte_count"], f"{label}.byte_count")
    if byte_count < 1:
        raise CleanRoomError(f"{label}.byte_count must be positive")
    classification = _expect_string(descriptor["classification"], f"{label}.classification")
    if classification not in {
        "public_specification",
        "internal_research_evidence",
        "internal_use_only",
    }:
        raise CleanRoomError(f"{label}.classification is invalid")
    if not _expect_string(descriptor["media_type"], f"{label}.media_type"):
        raise CleanRoomError(f"{label}.media_type cannot be empty")
    _validate_packet_path(
        _expect_string(descriptor["packet_path"], f"{label}.packet_path"),
        f"{label}.packet_path",
    )
    _expect_sha256(descriptor["sha256"], f"{label}.sha256")
    return descriptor


def load_input_manifest(path: Path) -> ManifestDocument:
    data = read_regular_file(path)
    payload = parse_json_object(data, "input manifest", require_canonical=True)
    _expect_exact_keys(
        payload,
        {
            "controls",
            "evidence",
            "generated_at",
            "output_contract",
            "protocol_version",
            "reconstruction_window",
            "schema_version",
            "specifications",
        },
        "input manifest",
    )
    if payload["schema_version"] != INPUT_MANIFEST_SCHEMA_VERSION:
        raise CleanRoomError("input manifest schema_version is unsupported")
    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise CleanRoomError("input manifest protocol_version is unsupported")
    validate_generated_at(_expect_string(payload["generated_at"], "input manifest.generated_at"))

    controls = _expect_mapping(payload["controls"], "input manifest.controls")
    _expect_exact_keys(
        controls,
        {
            "contains_adls_source_or_tests",
            "contains_reference_output",
            "historical_umich_assumption",
            "licensed_evidence_must_remain_internal",
            "reference_withheld_until_submission_sealed",
        },
        "input manifest.controls",
    )
    required_controls: dict[str, JsonValue] = {
        "contains_adls_source_or_tests": False,
        "contains_reference_output": False,
        "historical_umich_assumption": "unrevised_final_values",
        "licensed_evidence_must_remain_internal": True,
        "reference_withheld_until_submission_sealed": True,
    }
    if controls != required_controls:
        raise CleanRoomError("input manifest clean-room controls are not binding")

    window = _expect_mapping(payload["reconstruction_window"], "reconstruction_window")
    _expect_exact_keys(
        window,
        {"end_month", "expected_month_count", "start_month"},
        "reconstruction_window",
    )
    start_month = validate_month(
        _expect_string(window["start_month"], "reconstruction_window.start_month"),
        "reconstruction_window.start_month",
    )
    end_month = validate_month(
        _expect_string(window["end_month"], "reconstruction_window.end_month"),
        "reconstruction_window.end_month",
    )
    expected_month_count = _expect_int(
        window["expected_month_count"], "reconstruction_window.expected_month_count"
    )
    if expected_month_count != month_count(start_month, end_month):
        raise CleanRoomError("input manifest expected_month_count is contradictory")

    all_ids: set[str] = set()
    all_paths: set[str] = set()
    descriptor_sets: list[tuple[str, frozenset[str]]] = [
        ("specifications", SPECIFICATION_IDS),
        ("evidence", EVIDENCE_IDS),
    ]
    descriptors_by_id: dict[str, dict[str, JsonValue]] = {}
    for collection_name, expected_ids in descriptor_sets:
        collection = payload[collection_name]
        if not isinstance(collection, list):
            raise CleanRoomError(f"input manifest.{collection_name} must be an array")
        found: set[str] = set()
        for position, raw_descriptor in enumerate(collection, 1):
            descriptor = _validate_descriptor(
                raw_descriptor, f"input manifest.{collection_name}[{position}]"
            )
            artifact_id = cast(str, descriptor["artifact_id"])
            if artifact_id not in expected_ids:
                raise CleanRoomError(
                    f"input manifest.{collection_name} contains unsupported artifact id"
                )
            expected_path, expected_classification, expected_media_type = DESCRIPTOR_CONTRACTS[
                artifact_id
            ]
            if (
                descriptor["packet_path"] != expected_path
                or descriptor["classification"] != expected_classification
                or descriptor["media_type"] != expected_media_type
            ):
                raise CleanRoomError(
                    f"input manifest descriptor contract differs for {artifact_id}"
                )
            packet_path = cast(str, descriptor["packet_path"])
            if artifact_id in all_ids or packet_path in all_paths:
                raise CleanRoomError("input manifest repeats an artifact id or packet path")
            all_ids.add(artifact_id)
            all_paths.add(packet_path)
            found.add(artifact_id)
            descriptors_by_id[artifact_id] = descriptor
        if found != expected_ids:
            raise CleanRoomError(
                f"input manifest.{collection_name} ids differ from the protocol contract"
            )

    output_contract = _expect_mapping(payload["output_contract"], "output_contract")
    _expect_exact_keys(
        output_contract,
        {"artifact_id", "schema_version", "sha256"},
        "output_contract",
    )
    if output_contract["artifact_id"] != "clean_room_frozen_month_contract":
        raise CleanRoomError("output_contract artifact_id is unsupported")
    if output_contract["schema_version"] != FROZEN_MONTH_SCHEMA_VERSION:
        raise CleanRoomError("output_contract schema_version is unsupported")
    output_contract_sha256 = _expect_sha256(output_contract["sha256"], "output_contract.sha256")
    contract_descriptor = descriptors_by_id["clean_room_frozen_month_contract"]
    if output_contract_sha256 != contract_descriptor["sha256"]:
        raise CleanRoomError("output_contract hash differs from its specification descriptor")

    return ManifestDocument(
        payload,
        data,
        hashlib.sha256(data).hexdigest(),
        start_month,
        end_month,
        expected_month_count,
        output_contract_sha256,
    )


def load_submission(path: Path) -> SubmissionDocument:
    data = read_regular_file(path)
    payload = parse_json_object(data, "submission seal", require_canonical=True)
    _expect_exact_keys(
        payload,
        {
            "attestation",
            "generated_at",
            "implementation_id",
            "input_manifest_sha256",
            "output_contract_sha256",
            "protocol_version",
            "schema_version",
            "sequence",
        },
        "submission seal",
    )
    if payload["schema_version"] != SUBMISSION_SCHEMA_VERSION:
        raise CleanRoomError("submission schema_version is unsupported")
    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise CleanRoomError("submission protocol_version is unsupported")
    validate_generated_at(_expect_string(payload["generated_at"], "submission.generated_at"))
    validate_implementation_id(
        _expect_string(payload["implementation_id"], "submission.implementation_id")
    )
    _expect_sha256(payload["input_manifest_sha256"], "submission.input_manifest_sha256")
    _expect_sha256(payload["output_contract_sha256"], "submission.output_contract_sha256")

    attestation = _expect_mapping(payload["attestation"], "submission.attestation")
    expected_attestation: dict[str, JsonValue] = {
        "implemented_from_packet_only": True,
        "no_adls_source_or_tests_access": True,
        "no_reference_output_access": True,
    }
    _expect_exact_keys(attestation, set(expected_attestation), "submission.attestation")
    if attestation != expected_attestation:
        raise CleanRoomError("submission clean-room attestation is incomplete")

    sequence = _expect_mapping(payload["sequence"], "submission.sequence")
    _expect_exact_keys(
        sequence,
        {"byte_count", "first_month", "last_month", "record_count", "schema_version", "sha256"},
        "submission.sequence",
    )
    if sequence["schema_version"] != FROZEN_MONTH_SCHEMA_VERSION:
        raise CleanRoomError("submission sequence schema_version is unsupported")
    for name in ("byte_count", "record_count"):
        if _expect_int(sequence[name], f"submission.sequence.{name}") < 1:
            raise CleanRoomError(f"submission.sequence.{name} must be positive")
    validate_month(
        _expect_string(sequence["first_month"], "submission.sequence.first_month"),
        "submission.sequence.first_month",
    )
    validate_month(
        _expect_string(sequence["last_month"], "submission.sequence.last_month"),
        "submission.sequence.last_month",
    )
    _expect_sha256(sequence["sha256"], "submission.sequence.sha256")
    return SubmissionDocument(payload, data, hashlib.sha256(data).hexdigest())


def descriptor_map(manifest: ManifestDocument) -> dict[str, dict[str, JsonValue]]:
    result: dict[str, dict[str, JsonValue]] = {}
    for collection_name in ("specifications", "evidence"):
        collection = cast(list[JsonValue], manifest.payload[collection_name])
        for raw_descriptor in collection:
            descriptor = cast(dict[str, JsonValue], raw_descriptor)
            result[cast(str, descriptor["artifact_id"])] = descriptor
    return result
