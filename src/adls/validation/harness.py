"""Deterministic Slice 6 validation artifact, with owner-pin enforcement."""

from __future__ import annotations

import hashlib
import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from adls.checker import verify_frozen_sequence
from adls.contracts import ValidationResult
from adls.engine.canonical import load_frozen_sequence
from adls.engine.serialize import JsonValue, canonical_json_bytes

from .analysis import (
    calibration_table,
    score_binary_signal_series,
    score_signal_series,
    summarize_scores,
)
from .baseline_eval import BASELINE_MODELS, evaluate_baselines
from .cache import OUTCOME_SERIES, load_latest_outcome_levels
from .models import (
    BaselineContract,
    BaselineOrigin,
    FrozenPoint,
    OutcomeGap,
    ScoreRow,
    ValidationRunResult,
)
from .outcomes import compute_outcome_gaps
from .permutation_eval import evaluate_joint_permutation
from .reconstruction import point_from_frozen_record
from .regimes import summarize_regimes
from .spec import BASELINE_TARGET, FORECAST_EVENT_MAPPING, OUTCOME_VINTAGE_POLICY

CRITERIA_VERSION = "adls.validation.v1"
SCHEMA_VERSION = "adls.validation.artifact.v1"
DEBT_IDS = ("VD-002", "VD-004")


def _json_ready(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_ready(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    raise TypeError(f"cannot serialize validation value {type(value).__name__}")


def _mean_mase(origins: Sequence[BaselineOrigin]) -> tuple[float | None, int]:
    values = tuple(item.mase for item in origins if item.mase is not None)
    return (math.fsum(values) / len(values), len(values)) if values else (None, 0)


def _baseline_rows(
    origins: Sequence[BaselineOrigin],
    outcomes: Sequence[OutcomeGap],
    contract: BaselineContract,
) -> dict[str, tuple[ScoreRow, ...]]:
    result: dict[str, tuple[ScoreRow, ...]] = {}
    for model in BASELINE_MODELS:
        selected = tuple(item for item in origins if item.model == model)
        result[model] = score_binary_signal_series(
            tuple((item.month, item.signal) for item in selected),
            outcomes,
            source=model,
            turning_window_months=contract.turning_window_months,
        )
    return result


def build_validation_artifact(
    points: Sequence[FrozenPoint],
    outcomes: Sequence[OutcomeGap],
    contract: BaselineContract,
    *,
    frozen_sha256: str,
    outcome_vintage: str,
    checker_label: str,
    checker_criteria_version: str,
    checker_check_count: int,
) -> ValidationRunResult:
    validation = ValidationResult()
    if contract.pin_status != "approved":
        validation.error(
            "baseline exact spec is still proposed; owner approval is required before a "
            "real-data validation run"
        )
        return ValidationRunResult(b"", validation)
    valid_hash = len(frozen_sha256) == 64 and all(
        character in "0123456789abcdef" for character in frozen_sha256
    )
    if not valid_hash:
        validation.error("frozen-equivalent SHA-256 is invalid")
    try:
        parsed_vintage = date.fromisoformat(outcome_vintage)
    except ValueError:
        validation.error("outcome vintage is not an ISO date")
    else:
        if parsed_vintage.isoformat() != outcome_vintage:
            validation.error("outcome vintage is not an ISO date")
    if checker_label != "Verified":
        validation.error("frozen-equivalent reconstruction is not checker-Verified")
    if not checker_criteria_version or checker_check_count < 1:
        validation.error("checker evidence is incomplete")
    if not points:
        validation.error("frozen-equivalent sequence has no points")
    if not outcomes:
        validation.error("validation outcome has no rows")
    if not validation.ok:
        return ValidationRunResult(b"", validation)

    primary_rows = score_signal_series(
        tuple((point.month, point.published_band, point.composite_abstained) for point in points),
        outcomes,
        source="primary",
        turning_window_months=contract.turning_window_months,
    )
    primary_summary = summarize_scores(primary_rows)
    origins = evaluate_baselines(points, contract)
    scored_baselines = _baseline_rows(origins, outcomes, contract)
    baseline_summaries: dict[str, object] = {}
    floor_rows: list[dict[str, object]] = []
    for model in BASELINE_MODELS:
        selected_origins = tuple(item for item in origins if item.model == model)
        score_summary = summarize_scores(scored_baselines[model])
        mean_mase, mase_count = _mean_mase(selected_origins)
        baseline_summaries[model] = {
            "mean_mase": mean_mase,
            "mase_count": mase_count,
            "score": score_summary,
        }
        passed = (
            primary_summary.lead_rate > score_summary.lead_rate
            if primary_summary.lead_rate is not None and score_summary.lead_rate is not None
            else None
        )
        floor_rows.append(
            {
                "baseline": model,
                "baseline_lead_rate": score_summary.lead_rate,
                "primary_lead_rate": primary_summary.lead_rate,
                "passed": passed,
            }
        )

    permutation = evaluate_joint_permutation(points, outcomes, contract)
    definitive_failures = [row for row in floor_rows if row["passed"] is False]
    if permutation.rope_met is False or definitive_failures:
        monitor_status = "coincident_monitor"
    else:
        monitor_status = "validation_pending"

    score_sets = {"primary": primary_rows, **scored_baselines}
    regime_reports = {source: summarize_regimes(rows) for source, rows in score_sets.items()}
    payload = {
        "baseline_contract": contract,
        "baseline_floor": floor_rows,
        "baseline_origins": origins,
        "baseline_summaries": baseline_summaries,
        "calibration": calibration_table(primary_rows),
        "criteria_version": CRITERIA_VERSION,
        "framing": {
            "claim_status": "descriptive_only",
            "leading_claim_allowed": False,
            "monitor_status": monitor_status,
            "research_label": "research_only",
        },
        "input_contract": {
            "baseline_target": BASELINE_TARGET,
            "forecast_event_mapping": FORECAST_EVENT_MAPPING,
            "outcome_vintage_policy": OUTCOME_VINTAGE_POLICY,
        },
        "outcomes": outcomes,
        "permutation": permutation,
        "power": {
            "candidate_episode_count": primary_summary.signal_episode_count,
            "candidate_episode_upper_bound": 4,
            "candidate_episode_upper_bound_met": primary_summary.signal_episode_count <= 4,
            "descriptive_regardless_of_p_values": True,
            "evaluable_candidate_episode_count": primary_summary.scored_signal_episode_count,
            "out_of_sample_episode_required_for_leading_claim": True,
        },
        "primary_summary": primary_summary,
        "regime_reports": regime_reports,
        "schema_version": SCHEMA_VERSION,
        "score_rows": score_sets,
        "source": {
            "checker_check_count": checker_check_count,
            "checker_criteria_version": checker_criteria_version,
            "checker_label": checker_label,
            "frozen_equivalent_sha256": frozen_sha256,
            "outcome_vintage": outcome_vintage,
        },
        "verification_debt": list(DEBT_IDS),
    }
    ready = _json_ready(payload)
    if not isinstance(ready, dict):
        raise TypeError("validation artifact payload must be an object")
    return ValidationRunResult(canonical_json_bytes(cast(dict[str, JsonValue], ready)), validation)


def run_validation(
    frozen_path: Path,
    cache_path: Path,
    archive_path: Path,
    artifact_path: Path,
    contract: BaselineContract,
) -> ValidationRunResult:
    if contract.pin_status != "approved":
        return build_validation_artifact(
            (),
            (),
            contract,
            frozen_sha256="",
            outcome_vintage="",
            checker_label="Unverified",
            checker_criteria_version="",
            checker_check_count=0,
        )
    validation = ValidationResult()
    try:
        frozen_blob = frozen_path.read_bytes()
        archive_blob = archive_path.read_bytes()
    except OSError as exc:
        validation.error(f"cannot snapshot validation evidence: {exc}")
        return ValidationRunResult(b"", validation)
    if not cache_path.is_file():
        validation.error(f"vintage cache does not exist: {cache_path}")
        return ValidationRunResult(b"", validation)

    try:
        with TemporaryDirectory(prefix="adls-validation-run-") as directory:
            temporary = Path(directory)
            cache_snapshot = temporary / "cache.sqlite"
            frozen_snapshot = temporary / "frozen.jsonl"
            archive_snapshot = temporary / "archive.csv"
            frozen_snapshot.write_bytes(frozen_blob)
            archive_snapshot.write_bytes(archive_blob)
            source: sqlite3.Connection | None = None
            destination: sqlite3.Connection | None = None
            try:
                source = sqlite3.connect(
                    f"{cache_path.resolve().as_uri()}?mode=ro",
                    uri=True,
                )
                source.execute("BEGIN")
                destination = sqlite3.connect(cache_snapshot)
                source.backup(destination)
            except sqlite3.Error as exc:
                validation.error(f"cannot snapshot vintage cache: {exc}")
            finally:
                if destination is not None:
                    destination.close()
                if source is not None:
                    source.close()
            if not validation.ok:
                return ValidationRunResult(b"", validation)

            checked = verify_frozen_sequence(
                cache_snapshot,
                (archive_snapshot,),
                frozen_snapshot,
                assume_unrevised_archive_finals=True,
            )
            if checked.label != "Verified":
                validation.errors.extend(checked.discrepancies)
                validation.errors.extend(checked.debts)
                validation.ok = False
                if not checked.discrepancies and not checked.debts:
                    validation.error("frozen-equivalent reconstruction was not Verified")
                return ValidationRunResult(b"", validation)

            frozen = load_frozen_sequence(frozen_snapshot)
            validation.extend(frozen.validation)
            if not frozen.records:
                validation.error("frozen-equivalent sequence has no records")
            outcome_source = load_latest_outcome_levels(cache_snapshot)
            validation.extend(outcome_source.validation)
            if not validation.ok or outcome_source.vintage is None:
                return ValidationRunResult(b"", validation)

            components = dict(outcome_source.components)
            if any(series_id not in components for series_id in OUTCOME_SERIES):
                validation.error("validation outcome components are incomplete")
                return ValidationRunResult(b"", validation)
            outcomes = compute_outcome_gaps(
                components[OUTCOME_SERIES[0]],
                components[OUTCOME_SERIES[1]],
            )
            points = tuple(point_from_frozen_record(record) for record in frozen.records)
            result = build_validation_artifact(
                points,
                outcomes,
                contract,
                frozen_sha256=hashlib.sha256(frozen_blob).hexdigest(),
                outcome_vintage=outcome_source.vintage,
                checker_label=checked.label,
                checker_criteria_version=checked.criteria_version,
                checker_check_count=len(checked.checks),
            )
    except OSError as exc:
        validation.error(f"cannot create validation evidence snapshot: {exc}")
        return ValidationRunResult(b"", validation)
    validation.extend(result.validation)
    if not validation.ok:
        return ValidationRunResult(b"", validation)

    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_path.exists():
            if artifact_path.read_bytes() != result.artifact_bytes:
                validation.error("existing validation artifact differs from deterministic rerun")
                return ValidationRunResult(b"", validation)
        else:
            with TemporaryDirectory(
                prefix="adls-artifact-",
                dir=artifact_path.parent,
            ) as directory:
                temporary_path = Path(directory) / artifact_path.name
                temporary_path.write_bytes(result.artifact_bytes)
                temporary_path.replace(artifact_path)
    except OSError as exc:
        validation.error(f"cannot persist validation artifact: {exc}")
        return ValidationRunResult(b"", validation)
    return ValidationRunResult(result.artifact_bytes, validation)
