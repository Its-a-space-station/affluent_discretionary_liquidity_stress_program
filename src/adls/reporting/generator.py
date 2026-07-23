"""Snapshot, verify, and render one local weekly research report."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from adls.alfred.cache import VintageCache
from adls.calendarutil import canonical_month_for_assembly
from adls.checker import verify_assembly, verify_frozen_sequence
from adls.checker.models import CheckResult, VerificationLabel
from adls.contracts import PointInTimeResult, ValidationResult
from adls.engine.canonical import FrozenRecord, load_frozen_sequence
from adls.engine.core import assemble
from adls.engine.models import AssemblyResult, FamilyScore
from adls.engine.serialize import JsonValue, canonical_json_bytes, serialize_assembly
from adls.inputs.archive import ArchiveDataset, load_archive_csv
from adls.inputs.loader import PointInTimeLoader
from adls.registry import REGISTRY, SeriesSpec

from .models import ReportRunResult

SCHEMA_VERSION = "adls.weekly_report.v1"
DISCLAIMER = (
    "Research only. Not financial advice. This report summarizes automated "
    "observations for human review. It does not recommend, initiate, or execute "
    "any financial action. Verify independently before making any decision."
)
RESULT_LABELS = (
    "reject",
    "watchlist",
    "trigger_ready_research_candidate",
    "needs_human_review",
    "paper_candidate",
    "research_only",
    "validation_pending",
)
CONFIDENCE_LABELS = (
    "Verified",
    "Provisional",
    "Conflicting",
    "Unverified",
    "Stale",
)
DEBT_DETAILS = {
    "VD-001": (
        "The source validation artifact predates the owner-accepted independent "
        "reconstruction; see the current debt register."
    ),
    "VD-002": "Historical UMich values rely on the declared unrevised-final assumption.",
    "VD-004": "Only four candidate episodes are available; inference remains descriptive.",
}
ENGINE_SPECS: tuple[SeriesSpec, ...] = tuple(
    spec for spec in REGISTRY if spec.role in {"leading", "overlay"}
)


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object")
    return cast(dict[str, object], value)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be an array of strings")
    return cast(list[str], value)


def _canonical_timestamp(value: str) -> datetime:
    candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("generated_at must be a canonical UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("generated_at must be a canonical UTC timestamp")
    utc_value = parsed.astimezone(UTC)
    timespec = "microseconds" if utc_value.microsecond else "seconds"
    canonical = utc_value.isoformat(timespec=timespec).replace("+00:00", "Z")
    if canonical != value:
        raise ValueError("generated_at must be a canonical UTC timestamp")
    return utc_value


def _canonical_date(value: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a canonical ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be a canonical ISO date")
    return parsed


def _load_canonical_json(
    blob: bytes,
    field: str,
    validation: ValidationResult,
) -> dict[str, object] | None:
    try:
        parsed = json.loads(blob.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        payload = _mapping(parsed, field)
        canonical = canonical_json_bytes(cast(dict[str, JsonValue], payload))
        if canonical != blob:
            raise ValueError(f"{field} is not canonical JSON")
        return payload
    except (
        ArithmeticError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        validation.error(f"cannot load {field}: {exc}")
        return None


def _validate_validation_artifact(payload: dict[str, object]) -> None:
    if payload.get("schema_version") != "adls.validation.artifact.v1":
        raise ValueError("validation artifact schema_version is unsupported")
    framing = _mapping(payload.get("framing"), "validation artifact framing")
    _string(framing.get("claim_status"), "validation artifact claim_status")
    _bool(framing.get("leading_claim_allowed"), "validation artifact leading_claim_allowed")
    _string(framing.get("monitor_status"), "validation artifact monitor_status")
    research_label = _string(
        framing.get("research_label"),
        "validation artifact research_label",
    )
    if research_label not in RESULT_LABELS:
        raise ValueError("validation artifact uses an unapproved result label")

    source = _mapping(payload.get("source"), "validation artifact source")
    checker_label = _string(source.get("checker_label"), "validation artifact checker_label")
    if checker_label not in CONFIDENCE_LABELS:
        raise ValueError("validation artifact uses an unknown checker label")
    _string(
        source.get("checker_criteria_version"),
        "validation artifact checker_criteria_version",
    )
    _string(source.get("outcome_vintage"), "validation artifact outcome_vintage")
    _mapping(payload.get("primary_summary"), "validation artifact primary_summary")
    calibration = _mapping(payload.get("calibration"), "validation artifact calibration")
    _bool(calibration.get("monotonic"), "validation artifact calibration.monotonic")
    if not isinstance(payload.get("baseline_floor"), list):
        raise ValueError("validation artifact baseline_floor must be an array")
    _string_list(payload.get("verification_debt"), "validation artifact verification_debt")


def _snapshot_cache(source_path: Path, target_path: Path, validation: ValidationResult) -> None:
    if not source_path.is_file():
        validation.error(f"vintage cache does not exist: {source_path}")
        return
    source: sqlite3.Connection | None = None
    target: sqlite3.Connection | None = None
    try:
        source = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
        source.execute("BEGIN")
        target = sqlite3.connect(target_path)
        source.backup(target)
    except sqlite3.Error as exc:
        validation.error(f"cannot snapshot vintage cache: {exc}")
    finally:
        if target is not None:
            target.close()
        if source is not None:
            source.close()


def _read_required(path: Path, label: str, validation: ValidationResult) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        validation.error(f"cannot read {label}: {exc}")
        return b""


def _write_atomic(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(blob)
    temporary.replace(path)


def _engine_inputs(
    cache_path: Path,
    archive: ArchiveDataset,
    assembly_date: str,
    provisional: bool,
) -> dict[str, PointInTimeResult]:
    loader = PointInTimeLoader(VintageCache(cache_path), archive)
    return {
        spec.series_id: loader.history_at(
            spec.series_id,
            assembly_date,
            provisional=provisional,
        )
        for spec in ENGINE_SPECS
    }


def _checker_payload(result: CheckResult) -> dict[str, JsonValue]:
    return {
        "checks": [
            {
                "check_id": check.check_id,
                "detail": check.detail,
                "passed": check.passed,
            }
            for check in result.checks
        ],
        "criteria_version": result.criteria_version,
        "debts": list(result.debts),
        "discrepancies": list(result.discrepancies),
        "label": result.label,
    }


def _series_citation(series_id: str) -> str:
    spec = next(spec for spec in REGISTRY if spec.series_id == series_id)
    if spec.license == "visa_citation":
        return f"Visa via FRED ({series_id})"
    if spec.license == "umich_internal":
        return f"UMich Table 2n, internal use only ({series_id})"
    return f"FRED/ALFRED ({series_id})"


def _family_evidence(
    score: FamilyScore,
    assembly: AssemblyResult,
    assembly_hash: str,
) -> dict[str, JsonValue]:
    releases = dict(score.member_release_dates)
    evidence_id = f"assembly:{assembly_hash}:family:{score.family}"
    return {
        "as_of": assembly.assembly_date,
        "evidence_id": evidence_id,
        "family": score.family,
        "kind": "point_in_time_family",
        "member_release_dates": cast(dict[str, JsonValue], releases),
        "sources": [_series_citation(series_id) for series_id in score.member_series_ids],
    }


def _family_finding(
    score: FamilyScore,
    assembly: AssemblyResult,
    assembly_hash: str,
    checker_label: VerificationLabel,
) -> dict[str, JsonValue]:
    releases = dict(score.member_release_dates)
    source_timestamp = max(releases.values()) if releases else assembly.assembly_date
    result_label = "validation_pending" if score.abstained else "research_only"
    note = (
        "The family abstained under the point-in-time availability and freshness rules."
        if score.abstained
        else (
            "The family reading is descriptive and contributes only under the fixed "
            "composite rules."
        )
    )
    return {
        "confidence_label": checker_label,
        "evidence_ids": [f"assembly:{assembly_hash}:family:{score.family}"],
        "finding_id": f"family:{score.family}",
        "key_evidence": {
            "abstained": score.abstained,
            "flags": list(score.flags),
            "member_release_dates": cast(dict[str, JsonValue], releases),
            "member_series_ids": list(score.member_series_ids),
            "observation_date": score.observation_date,
            "z_score": score.z_score,
        },
        "note": note,
        "result_label": result_label,
        "source_timestamp": source_timestamp,
        "subject": score.family,
    }


def _composite_finding(
    assembly: AssemblyResult,
    assembly_hash: str,
    checker: CheckResult,
) -> dict[str, JsonValue]:
    if checker.label == "Conflicting":
        result_label = "needs_human_review"
    elif assembly.composite_abstained:
        result_label = "validation_pending"
    else:
        result_label = "research_only"
    return {
        "confidence_label": checker.label,
        "evidence_ids": [f"assembly:{assembly_hash}"],
        "finding_id": "current_composite",
        "key_evidence": {
            "abstained": assembly.composite_abstained,
            "assembly_mode": "provisional" if assembly.provisional else "canonical",
            "flags": list(assembly.flags),
            "headline_tier": assembly.headline_tier,
            "headline_value": assembly.headline_value,
            "tier_a_value": assembly.tier_a_value,
            "tier_b_value": assembly.tier_b_value,
        },
        "note": ("This is a point-in-time descriptive composite, not a validated leading claim."),
        "result_label": result_label,
        "source_timestamp": assembly.assembly_date,
        "subject": "ADLS current composite",
    }


def _band_result_label(record: FrozenRecord | None) -> str:
    if record is None or record.band.published_band is None:
        return "validation_pending"
    if record.band.published_band == "Watch":
        return "watchlist"
    if record.band.published_band in {"Elevated", "High"}:
        return "needs_human_review"
    return "research_only"


def _live_sequence_finding(
    latest: FrozenRecord | None,
    frozen_hash: str,
    frozen_check: CheckResult,
    as_of: str,
) -> dict[str, JsonValue]:
    cold_start = latest is None
    return {
        "confidence_label": frozen_check.label,
        "evidence_ids": [f"live-sequence:{frozen_hash}"],
        "finding_id": "live_band",
        "key_evidence": {
            "cold_start": cold_start,
            "latest_month": None if latest is None else latest.month,
            "published_band": None if latest is None else latest.band.published_band,
        },
        "note": (
            "The owner-selected cold start has no live band history yet."
            if cold_start
            else "The latest band comes only from the append-only live sequence."
        ),
        "result_label": _band_result_label(latest),
        "source_timestamp": as_of if latest is None else latest.finalized_on,
        "subject": "Live canonical band",
    }


def _validation_finding(
    payload: dict[str, object],
    validation_hash: str,
) -> dict[str, JsonValue]:
    framing = _mapping(payload["framing"], "validation framing")
    source = _mapping(payload["source"], "validation source")
    checker_label = cast(VerificationLabel, source["checker_label"])
    return {
        "confidence_label": checker_label,
        "evidence_ids": [f"validation:{validation_hash}"],
        "finding_id": "historical_validation",
        "key_evidence": {
            "baseline_floor": cast(JsonValue, payload["baseline_floor"]),
            "calibration": cast(JsonValue, payload["calibration"]),
            "claim_status": cast(str, framing["claim_status"]),
            "leading_claim_allowed": cast(bool, framing["leading_claim_allowed"]),
            "monitor_status": cast(str, framing["monitor_status"]),
            "primary_summary": cast(JsonValue, payload["primary_summary"]),
        },
        "note": (
            "The binding failure clause classifies the system as a descriptive coincident monitor."
        ),
        "result_label": cast(str, framing["research_label"]),
        "source_timestamp": cast(str, source["outcome_vintage"]),
        "subject": "Historical validation",
    }


def _combined_confidence(labels: Sequence[str]) -> VerificationLabel:
    for candidate in ("Conflicting", "Unverified", "Stale", "Provisional"):
        if candidate in labels:
            return cast(VerificationLabel, candidate)
    return "Verified"


def _launch_audit(
    assembly: AssemblyResult,
    assembly_hash: str,
    assembly_check: CheckResult,
    latest: FrozenRecord | None,
    frozen_hash: str,
    frozen_check: CheckResult,
    validation_payload: dict[str, object],
    validation_hash: str,
) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    framing = _mapping(validation_payload["framing"], "validation framing")
    source = _mapping(validation_payload["source"], "validation source")
    calibration = _mapping(validation_payload["calibration"], "validation calibration")
    debts = cast(list[str], validation_payload["verification_debt"])
    leading = tuple(score for score in assembly.family_scores if score.role == "leading")
    conditions: list[dict[str, JsonValue]] = [
        {
            "condition_id": "current_assembly_verified",
            "evidence_ids": [f"assembly:{assembly_hash}"],
            "met": assembly_check.label == "Verified",
            "note": "The independent checker must reproduce the current assembly.",
        },
        {
            "condition_id": "current_composite_available",
            "evidence_ids": [f"assembly:{assembly_hash}"],
            "met": not assembly.composite_abstained,
            "note": "At least three leading families must remain usable.",
        },
        {
            "condition_id": "all_leading_families_available",
            "evidence_ids": [
                f"assembly:{assembly_hash}:family:{score.family}" for score in leading
            ],
            "met": all(not score.abstained for score in leading),
            "note": "Every leading family must have a current non-stale reading.",
        },
        {
            "condition_id": "live_history_available",
            "evidence_ids": [f"live-sequence:{frozen_hash}"],
            "met": latest is not None,
            "note": "A cold-start store has no live percentile or dwell history.",
        },
        {
            "condition_id": "validation_checker_verified",
            "evidence_ids": [f"validation:{validation_hash}"],
            "met": source["checker_label"] == "Verified",
            "note": "Historical validation evidence must retain checker verification.",
        },
        {
            "condition_id": "leading_claim_allowed",
            "evidence_ids": [f"validation:{validation_hash}"],
            "met": framing["leading_claim_allowed"] is True,
            "note": "The current artifact explicitly disallows a leading claim.",
        },
        {
            "condition_id": "calibration_monotonic",
            "evidence_ids": [f"validation:{validation_hash}"],
            "met": calibration["monotonic"] is True,
            "note": "Observed band calibration must be monotonic before stronger reliance.",
        },
        {
            "condition_id": "verification_debt_closed",
            "evidence_ids": [f"validation:{validation_hash}"],
            "met": not debts,
            "note": "Open protocol and power debt remains visible.",
        },
        {
            "condition_id": "external_publication_approved",
            "evidence_ids": [],
            "met": False,
            "note": "External publication remains a separate explicit approval gate.",
        },
    ]
    internal_ready = (
        assembly_check.label == "Verified"
        and not assembly.composite_abstained
        and source["checker_label"] == "Verified"
    )
    external_ready = all(cast(bool, condition["met"]) for condition in conditions)
    audit: dict[str, JsonValue] = {
        "conditions": cast(list[JsonValue], conditions),
        "ready_for_external_publication": external_ready,
        "ready_for_internal_weekly_reporting": internal_ready,
    }
    confidence = _combined_confidence(
        (
            assembly_check.label,
            frozen_check.label,
            cast(str, source["checker_label"]),
        )
    )
    finding: dict[str, JsonValue] = {
        "confidence_label": confidence,
        "evidence_ids": [
            f"assembly:{assembly_hash}",
            f"live-sequence:{frozen_hash}",
            f"validation:{validation_hash}",
        ],
        "finding_id": "launch_condition_audit",
        "key_evidence": audit,
        "note": (
            "Internal reporting can proceed with the stated caveats; external publication "
            "is not ready."
            if internal_ready
            else "Current evidence does not support starting the internal weekly reporting loop."
        ),
        "result_label": "validation_pending",
        "source_timestamp": assembly.assembly_date,
        "subject": "Launch-condition audit",
    }
    return audit, finding


def _cache_operational_notes(cache_path: Path) -> dict[str, JsonValue]:
    coverage: dict[str, JsonValue] = {}
    latest_runs: list[JsonValue] = []
    anomalies: list[JsonValue] = []
    try:
        connection = sqlite3.connect(f"{cache_path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            coverage_rows = connection.execute(
                "SELECT series_id, complete_through_vintage, last_backfill_at "
                "FROM series_coverage ORDER BY series_id"
            ).fetchall()
            coverage = {
                str(row["series_id"]): {
                    "complete_through_vintage": row["complete_through_vintage"],
                    "last_backfill_at": row["last_backfill_at"],
                }
                for row in coverage_rows
            }
            has_fetch_runs = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'fetch_runs'"
            ).fetchone()
            if has_fetch_runs is not None:
                rows = connection.execute(
                    """
                    SELECT started_at, completed_at, series_id, endpoint, http_status,
                           rows_upserted, rate_limited, status, error_summary
                    FROM fetch_runs
                    WHERE id IN (
                        SELECT MAX(id) FROM fetch_runs GROUP BY series_id, endpoint
                    )
                    ORDER BY series_id, endpoint
                    """
                ).fetchall()
                latest_runs = [
                    {
                        "completed_at": row["completed_at"],
                        "endpoint": row["endpoint"],
                        "error_summary": row["error_summary"],
                        "http_status": row["http_status"],
                        "rate_limited": row["rate_limited"],
                        "rows_upserted": row["rows_upserted"],
                        "series_id": row["series_id"],
                        "started_at": row["started_at"],
                        "status": row["status"],
                    }
                    for row in rows
                ]
        finally:
            connection.close()
    except sqlite3.Error as exc:
        anomalies.append(f"cannot read cache operational metadata: {exc}")
    provider_health = "unknown"
    if latest_runs:
        provider_health = (
            "ok"
            if all(cast(dict[str, object], row).get("status") == "ok" for row in latest_runs)
            else "degraded"
        )
    return {
        "anomalies": anomalies,
        "cache_coverage": coverage,
        "latest_fetch_runs": latest_runs,
        "network_called_during_report": False,
        "provider_health": provider_health,
        "rate_limit_events_in_latest_runs": sum(
            int(cast(int, cast(dict[str, object], row).get("rate_limited") or 0))
            for row in latest_runs
        ),
    }


def _verification_debt(
    validation_payload: dict[str, object],
    assembly_check: CheckResult,
    frozen_check: CheckResult,
) -> list[JsonValue]:
    rows: list[JsonValue] = [
        {
            "debt_id": debt_id,
            "detail": DEBT_DETAILS.get(debt_id, "See the project verification-debt register."),
            "scope": "historical_validation",
            "status": "open",
        }
        for debt_id in cast(list[str], validation_payload["verification_debt"])
    ]
    rows.extend(
        {
            "debt_id": f"run:current_assembly:{index}",
            "detail": detail,
            "scope": "current_assembly",
            "status": "open",
        }
        for index, detail in enumerate(assembly_check.debts, 1)
    )
    rows.extend(
        {
            "debt_id": f"run:live_sequence:{index}",
            "detail": detail,
            "scope": "live_sequence",
            "status": "open",
        }
        for index, detail in enumerate(frozen_check.debts, 1)
    )
    return rows


def _change_summary(
    previous_payload: dict[str, object] | None,
    findings: Sequence[dict[str, JsonValue]],
) -> dict[str, JsonValue]:
    if previous_payload is None:
        return {
            "basis": "no_prior_report",
            "changed_finding_ids": [],
            "previous_run_id": None,
        }
    previous_findings = previous_payload.get("findings")
    if not isinstance(previous_findings, list):
        raise ValueError("previous report findings must be an array")
    prior_by_id: dict[str, object] = {}
    for raw in previous_findings:
        finding = _mapping(raw, "previous report finding")
        finding_id = _string(finding.get("finding_id"), "previous report finding_id")
        prior_by_id[finding_id] = finding
    current_by_id = {cast(str, finding["finding_id"]): finding for finding in findings}
    changed = sorted(
        finding_id
        for finding_id in set(prior_by_id) | set(current_by_id)
        if prior_by_id.get(finding_id) != current_by_id.get(finding_id)
    )
    return {
        "basis": "previous_report",
        "changed_finding_ids": cast(list[JsonValue], changed),
        "previous_run_id": cast(JsonValue, previous_payload.get("run_id")),
    }


def _counts(
    findings: Sequence[dict[str, JsonValue]],
    field: str,
    canonical_order: Sequence[str],
) -> dict[str, JsonValue]:
    counts = Counter(cast(str, finding[field]) for finding in findings)
    return {label: counts[label] for label in canonical_order if counts[label]}


def _build_report_payload(
    *,
    assembly: AssemblyResult,
    assembly_bytes: bytes,
    assembly_check: CheckResult,
    archive_blob: bytes,
    archive_name: str,
    frozen_blob: bytes,
    frozen_records: tuple[FrozenRecord, ...],
    frozen_check: CheckResult,
    validation_blob: bytes,
    validation_payload: dict[str, object],
    validation_name: str,
    generated_at: str,
    previous_payload: dict[str, object] | None,
    operational_notes: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    assembly_hash = _sha256(assembly_bytes)
    archive_hash = _sha256(archive_blob)
    frozen_hash = _sha256(frozen_blob)
    validation_hash = _sha256(validation_blob)
    latest = frozen_records[-1] if frozen_records else None
    run_seed: dict[str, JsonValue] = {
        "archive_sha256": archive_hash,
        "assembly_sha256": assembly_hash,
        "frozen_sha256": frozen_hash,
        "generated_at": generated_at,
        "validation_sha256": validation_hash,
    }
    run_hash = _sha256(canonical_json_bytes(run_seed))

    evidence: list[dict[str, JsonValue]] = [
        {
            "as_of": assembly.assembly_date,
            "criteria_version": assembly_check.criteria_version,
            "evidence_id": f"assembly:{assembly_hash}",
            "kind": "point_in_time_assembly",
            "sha256": assembly_hash,
            "source": "read-only local vintage cache plus normalized archive",
        },
        *[_family_evidence(score, assembly, assembly_hash) for score in assembly.family_scores],
        {
            "as_of": assembly.assembly_date,
            "evidence_id": f"archive:{archive_hash}",
            "kind": "normalized_archive",
            "sha256": archive_hash,
            "source": archive_name,
        },
        {
            "as_of": assembly.assembly_date if latest is None else latest.finalized_on,
            "evidence_id": f"live-sequence:{frozen_hash}",
            "kind": "live_canonical_sequence",
            "record_count": len(frozen_records),
            "sha256": frozen_hash,
            "source": "canonical/frozen_sequence.jsonl",
        },
        {
            "as_of": cast(
                JsonValue,
                cast(dict[str, object], validation_payload["source"])["outcome_vintage"],
            ),
            "criteria_version": cast(JsonValue, validation_payload["criteria_version"]),
            "evidence_id": f"validation:{validation_hash}",
            "kind": "historical_validation",
            "sha256": validation_hash,
            "source": validation_name,
        },
    ]
    findings: list[dict[str, JsonValue]] = [
        _composite_finding(assembly, assembly_hash, assembly_check),
        *[
            _family_finding(score, assembly, assembly_hash, assembly_check.label)
            for score in assembly.family_scores
        ],
        _live_sequence_finding(
            latest,
            frozen_hash,
            frozen_check,
            assembly.assembly_date,
        ),
        _validation_finding(validation_payload, validation_hash),
    ]
    launch_audit, launch_finding = _launch_audit(
        assembly,
        assembly_hash,
        assembly_check,
        latest,
        frozen_hash,
        frozen_check,
        validation_payload,
        validation_hash,
    )
    findings.append(launch_finding)
    escalations = [
        cast(str, finding["finding_id"])
        for finding in findings
        if finding["confidence_label"] == "Conflicting"
        or finding["result_label"] == "needs_human_review"
    ]
    payload: dict[str, JsonValue] = {
        "assembly_checker": _checker_payload(assembly_check),
        "conflicts_and_escalations": cast(list[JsonValue], escalations),
        "data_window": {
            "assembly_date": assembly.assembly_date,
            "assembly_mode": "provisional" if assembly.provisional else "canonical",
            "latest_live_month": None if latest is None else latest.month,
        },
        "disclaimer": DISCLAIMER,
        "evidence": cast(list[JsonValue], evidence),
        "findings": cast(list[JsonValue], findings),
        "generated_at": generated_at,
        "launch_condition_audit": launch_audit,
        "live_sequence_checker": _checker_payload(frozen_check),
        "operational_notes": operational_notes,
        "run_id": f"adls-weekly-{assembly.assembly_date}-{run_hash[:12]}",
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "change": _change_summary(previous_payload, findings),
            "confidence_label_counts": _counts(
                findings,
                "confidence_label",
                CONFIDENCE_LABELS,
            ),
            "result_label_counts": _counts(findings, "result_label", RESULT_LABELS),
        },
        "verification_debt": _verification_debt(
            validation_payload,
            assembly_check,
            frozen_check,
        ),
    }
    return payload


def _markdown_cell(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_markdown(payload: dict[str, JsonValue]) -> str:
    data_window = cast(dict[str, object], payload["data_window"])
    summary = cast(dict[str, object], payload["summary"])
    change = cast(dict[str, object], summary["change"])
    findings = cast(list[dict[str, object]], payload["findings"])
    audit = cast(dict[str, object], payload["launch_condition_audit"])
    debt = cast(list[dict[str, object]], payload["verification_debt"])
    operational = cast(dict[str, object], payload["operational_notes"])
    escalations = cast(list[str], payload["conflicts_and_escalations"])

    lines = [
        f"> **{DISCLAIMER}**",
        "",
        "# ADLS Weekly Research Report",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Assembly date: `{data_window['assembly_date']}` ({data_window['assembly_mode']})",
        f"- Latest live month: `{_markdown_cell(data_window['latest_live_month'])}`",
        "",
        "## Summary",
        "",
        f"- Result labels: `{json.dumps(summary['result_label_counts'], sort_keys=True)}`",
        f"- Confidence labels: `{json.dumps(summary['confidence_label_counts'], sort_keys=True)}`",
        f"- Change basis: `{change['basis']}`",
        f"- Changed findings: `{_markdown_cell(change['changed_finding_ids'])}`",
        "",
        "## Findings",
        "",
        "| Finding | Result | Confidence | Source timestamp | Evidence | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for finding in findings:
        lines.append(
            (
                "| {subject} | `{result}` | `{confidence}` | `{timestamp}` | "
                "`{evidence}` | {note} |"
            ).format(
                subject=_markdown_cell(finding["subject"]),
                result=finding["result_label"],
                confidence=finding["confidence_label"],
                timestamp=_markdown_cell(finding["source_timestamp"]),
                evidence=_markdown_cell(finding["evidence_ids"]),
                note=_markdown_cell(finding["note"]),
            )
        )

    family_findings = [
        finding for finding in findings if str(finding["finding_id"]).startswith("family:")
    ]
    lines.extend(
        [
            "",
            "## Family Readings",
            "",
            "| Family | Reading (z) | Observation | Sources | Flags |",
            "| --- | ---: | --- | --- | --- |",
        ]
    )
    evidence_by_id = {
        cast(str, row["evidence_id"]): row
        for row in cast(list[dict[str, object]], payload["evidence"])
    }
    for finding in family_findings:
        key = cast(dict[str, object], finding["key_evidence"])
        evidence_id = cast(list[str], finding["evidence_ids"])[0]
        family_evidence = evidence_by_id[evidence_id]
        lines.append(
            "| {family} | {z_score} | `{observation}` | {sources} | `{flags}` |".format(
                family=_markdown_cell(finding["subject"]),
                z_score=_markdown_cell(key["z_score"]),
                observation=_markdown_cell(key["observation_date"]),
                sources=_markdown_cell(family_evidence["sources"]),
                flags=_markdown_cell(key["flags"]),
            )
        )

    lines.extend(["", "## Conflicts And Escalations", ""])
    if escalations:
        lines.extend(f"- `{finding_id}`" for finding_id in escalations)
    else:
        lines.append("- None in this run.")

    lines.extend(["", "## Verification Debt", ""])
    if debt:
        lines.extend(f"- `{row['debt_id']}` ({row['scope']}): {row['detail']}" for row in debt)
    else:
        lines.append("- None recorded.")

    lines.extend(
        [
            "",
            "## Launch-Condition Audit",
            "",
            "- Ready for internal weekly reporting: "
            f"`{audit['ready_for_internal_weekly_reporting']}`",
            f"- Ready for external publication: `{audit['ready_for_external_publication']}`",
            "",
            "| Condition | Met | Note |",
            "| --- | --- | --- |",
        ]
    )
    for condition in cast(list[dict[str, object]], audit["conditions"]):
        lines.append(
            f"| `{condition['condition_id']}` | `{condition['met']}` | "
            f"{_markdown_cell(condition['note'])} |"
        )

    lines.extend(
        [
            "",
            "## Operational Notes",
            "",
            f"- Provider health: `{operational['provider_health']}`",
            f"- Network called during report: `{operational['network_called_during_report']}`",
            "- Rate-limit events in latest runs: "
            f"`{operational['rate_limit_events_in_latest_runs']}`",
            f"- Anomalies: `{_markdown_cell(operational['anomalies'])}`",
            "",
            "This local report preserves the cold-start boundary and does not publish externally.",
            "",
        ]
    )
    return "\n".join(lines)


def run_weekly_report(
    *,
    cache_path: Path,
    archive_path: Path,
    frozen_path: Path,
    validation_artifact_path: Path,
    assembly_date: str,
    generated_at: str,
    assembly_artifact_path: Path,
    report_artifact_path: Path,
    markdown_path: Path,
    previous_report_path: Path | None = None,
) -> ReportRunResult:
    """Generate three local artifacts from one cache-only evidence snapshot."""
    validation = ValidationResult()
    try:
        parsed_assembly_date = _canonical_date(assembly_date, "assembly_date")
        parsed_generated_at = _canonical_timestamp(generated_at)
        if parsed_generated_at.date() < parsed_assembly_date:
            raise ValueError("generated_at cannot predate assembly_date")
    except ValueError as exc:
        validation.error(str(exc))
        return ReportRunResult(b"", b"", "", validation)

    input_paths = {
        path.resolve()
        for path in (cache_path, archive_path, frozen_path, validation_artifact_path)
    }
    output_paths = {
        path.resolve() for path in (assembly_artifact_path, report_artifact_path, markdown_path)
    }
    if len(output_paths) != 3 or input_paths & output_paths:
        validation.error("report input and output paths must be distinct")
        return ReportRunResult(b"", b"", "", validation)

    archive_blob = _read_required(archive_path, "normalized archive", validation)
    frozen_blob = _read_required(frozen_path, "live frozen sequence", validation)
    validation_blob = _read_required(
        validation_artifact_path,
        "validation artifact",
        validation,
    )
    previous_blob = (
        None
        if previous_report_path is None
        else _read_required(previous_report_path, "previous report", validation)
    )
    if not validation.ok:
        return ReportRunResult(b"", b"", "", validation)

    validation_payload = _load_canonical_json(
        validation_blob,
        "validation artifact",
        validation,
    )
    previous_payload = (
        None
        if previous_blob is None
        else _load_canonical_json(previous_blob, "previous report", validation)
    )
    if validation_payload is not None:
        try:
            _validate_validation_artifact(validation_payload)
        except ValueError as exc:
            validation.error(str(exc))
    if previous_payload is not None and previous_payload.get("schema_version") != SCHEMA_VERSION:
        validation.error("previous report schema_version is unsupported")
    if not validation.ok or validation_payload is None:
        return ReportRunResult(b"", b"", "", validation)

    assembly_bytes = b""
    artifact_bytes = b""
    markdown = ""
    with TemporaryDirectory(prefix="adls-weekly-report-") as directory:
        temporary = Path(directory)
        cache_snapshot = temporary / "cache.sqlite"
        archive_snapshot = temporary / archive_path.name
        frozen_snapshot = temporary / "frozen_sequence.jsonl"
        archive_snapshot.write_bytes(archive_blob)
        frozen_snapshot.write_bytes(frozen_blob)
        _snapshot_cache(cache_path, cache_snapshot, validation)
        if not validation.ok:
            return ReportRunResult(b"", b"", "", validation)

        archive = load_archive_csv(archive_snapshot)
        if not archive.validation.ok:
            validation.extend(archive.validation)
            return ReportRunResult(b"", b"", "", validation)
        provisional = canonical_month_for_assembly(parsed_assembly_date) is None
        inputs = _engine_inputs(
            cache_snapshot,
            archive,
            assembly_date,
            provisional,
        )
        assembly = assemble(
            assembly_date,
            inputs,
            provisional=provisional,
        )
        assembly_bytes = serialize_assembly(assembly)
        assembly_check = verify_assembly(
            cache_snapshot,
            (archive_snapshot,),
            assembly_bytes,
        )

        frozen = load_frozen_sequence(frozen_snapshot)
        frozen_records = frozen.records if frozen.validation.ok else ()
        frozen_check = verify_frozen_sequence(
            cache_snapshot,
            (archive_snapshot,),
            frozen_snapshot,
        )
        operational_notes = _cache_operational_notes(cache_snapshot)
        if assembly.validation.errors:
            operational_notes["anomalies"] = [
                *cast(list[JsonValue], operational_notes["anomalies"]),
                *assembly.validation.errors,
            ]
        if assembly.validation.warnings:
            operational_notes["anomalies"] = [
                *cast(list[JsonValue], operational_notes["anomalies"]),
                *assembly.validation.warnings,
            ]
        if frozen.validation.errors:
            operational_notes["anomalies"] = [
                *cast(list[JsonValue], operational_notes["anomalies"]),
                *frozen.validation.errors,
            ]

        try:
            report_payload = _build_report_payload(
                assembly=assembly,
                assembly_bytes=assembly_bytes,
                assembly_check=assembly_check,
                archive_blob=archive_blob,
                archive_name=archive_path.name,
                frozen_blob=frozen_blob,
                frozen_records=frozen_records,
                frozen_check=frozen_check,
                validation_blob=validation_blob,
                validation_payload=validation_payload,
                validation_name=validation_artifact_path.name,
                generated_at=generated_at,
                previous_payload=previous_payload,
                operational_notes=operational_notes,
            )
            artifact_bytes = canonical_json_bytes(report_payload)
            markdown = _render_markdown(report_payload)
        except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
            validation.error(f"cannot build weekly report: {exc}")
            return ReportRunResult(assembly_bytes, b"", "", validation)

    try:
        _write_atomic(assembly_artifact_path, assembly_bytes)
        _write_atomic(report_artifact_path, artifact_bytes)
        _write_atomic(markdown_path, markdown.encode("utf-8"))
    except OSError as exc:
        validation.error(f"cannot write weekly report artifacts: {exc}")
    return ReportRunResult(assembly_bytes, artifact_bytes, markdown, validation)
