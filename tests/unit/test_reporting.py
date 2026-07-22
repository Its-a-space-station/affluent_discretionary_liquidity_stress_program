from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

from adls.alfred.cache import VintageCache
from adls.contracts import ObservationSpan, PointInTimeResult
from adls.engine.serialize import canonical_json_bytes
from adls.reporting import run_weekly_report
from fixtures.engine.gen_slice3_fixture import load_fixture_inputs


def _build_cache(
    path: Path,
    assembly_date: str,
    inputs: dict[str, PointInTimeResult],
) -> None:
    cache = VintageCache(path)
    cache.initialize()
    for series_id, raw_result in sorted(inputs.items()):
        if series_id == "UMICH_SCA_T2N_TOP":
            continue
        values = raw_result.values
        cache.upsert_spans(
            ObservationSpan(
                series_id=value.series_id,
                observation_date=value.observation_date,
                realtime_start=value.available_from,
                realtime_end="9999-12-31",
                value_text=value.value_text,
                source=value.source,
                source_file=value.source_file,
            )
            for value in values
        )
        cache.mark_backfilled(series_id, assembly_date)


def _build_archive(path: Path, raw_result: PointInTimeResult) -> str:
    values = list(raw_result.values)
    distinctive_raw = "987654.321"
    values[-1] = replace(values[-1], value_text=distinctive_raw)
    rows = [
        {
            "series_id": value.series_id,
            "observation_date": value.observation_date,
            "value_text": value.value_text,
            "release_date": value.release_date,
            "release_stage": value.release_stage,
            "source_file": value.source_file,
            "retrieved_at": value.retrieved_at,
        }
        for value in values
    ]
    rows.sort(
        key=lambda row: (
            str(row["series_id"]),
            str(row["observation_date"]),
            max(str(row["release_date"]), str(row["retrieved_at"])[:10]),
            str(row["release_stage"]),
            str(row["retrieved_at"]),
            str(row["source_file"]),
        )
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "series_id",
                "observation_date",
                "value_text",
                "release_date",
                "release_stage",
                "source_file",
                "retrieved_at",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return distinctive_raw


def _build_validation_artifact(path: Path) -> None:
    payload = {
        "baseline_floor": [
            {
                "baseline": "ar",
                "baseline_lead_rate": 0.6,
                "passed": False,
                "primary_lead_rate": 0.5,
            }
        ],
        "calibration": {"monotonic": False, "rows": []},
        "criteria_version": "adls.validation.v1",
        "framing": {
            "claim_status": "descriptive_only",
            "leading_claim_allowed": False,
            "monitor_status": "coincident_monitor",
            "research_label": "research_only",
        },
        "primary_summary": {
            "lead_rate": 0.5,
            "signal_episode_count": 4,
            "signal_episode_hits": 2,
        },
        "schema_version": "adls.validation.artifact.v1",
        "source": {
            "checker_criteria_version": "adls.checker.validation-assumption.v1",
            "checker_label": "Verified",
            "outcome_vintage": "2020-06-18",
        },
        "verification_debt": ["VD-001", "VD-002", "VD-004"],
    }
    path.write_bytes(canonical_json_bytes(payload))


def test_weekly_report_is_deterministic_redacted_and_cold_start_explicit(
    tmp_path: Path,
) -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    cache_path = tmp_path / "adls.sqlite"
    archive_path = tmp_path / "umich.csv"
    frozen_path = tmp_path / "frozen_sequence.jsonl"
    validation_path = tmp_path / "validation_results.json"
    _build_cache(cache_path, assembly_date, inputs)
    distinctive_raw = _build_archive(archive_path, inputs["UMICH_SCA_T2N_TOP"])
    frozen_path.write_bytes(b"")
    _build_validation_artifact(validation_path)

    first = run_weekly_report(
        cache_path=cache_path,
        archive_path=archive_path,
        frozen_path=frozen_path,
        validation_artifact_path=validation_path,
        assembly_date=assembly_date,
        generated_at="2020-06-19T20:00:00Z",
        assembly_artifact_path=tmp_path / "assembly-1.json",
        report_artifact_path=tmp_path / "report-1.json",
        markdown_path=tmp_path / "report-1.md",
    )
    second = run_weekly_report(
        cache_path=cache_path,
        archive_path=archive_path,
        frozen_path=frozen_path,
        validation_artifact_path=validation_path,
        assembly_date=assembly_date,
        generated_at="2020-06-19T20:00:00Z",
        assembly_artifact_path=tmp_path / "assembly-2.json",
        report_artifact_path=tmp_path / "report-2.json",
        markdown_path=tmp_path / "report-2.md",
    )

    assert first.validation.ok, first.validation.errors
    assert second.validation.ok, second.validation.errors
    assert first.assembly_bytes == second.assembly_bytes
    assert first.artifact_bytes == second.artifact_bytes
    assert first.markdown == second.markdown
    assert frozen_path.read_bytes() == b""

    artifact = json.loads(first.artifact_bytes)
    assert artifact["assembly_checker"]["label"] == "Verified"
    assert artifact["live_sequence_checker"]["label"] == "Unverified"
    assert artifact["launch_condition_audit"]["ready_for_internal_weekly_reporting"]
    assert not artifact["launch_condition_audit"]["ready_for_external_publication"]
    live_condition = next(
        row
        for row in artifact["launch_condition_audit"]["conditions"]
        if row["condition_id"] == "live_history_available"
    )
    assert not live_condition["met"]
    live_finding = next(row for row in artifact["findings"] if row["finding_id"] == "live_band")
    assert live_finding["source_timestamp"] == assembly_date
    launch_finding = next(
        row for row in artifact["findings"] if row["finding_id"] == "launch_condition_audit"
    )
    assert launch_finding["confidence_label"] == "Unverified"

    evidence_ids = {row["evidence_id"] for row in artifact["evidence"]}
    live_evidence = next(
        row for row in artifact["evidence"] if row["kind"] == "live_canonical_sequence"
    )
    assert live_evidence["as_of"] == assembly_date
    approved_results = {
        "reject",
        "watchlist",
        "trigger_ready_research_candidate",
        "needs_human_review",
        "paper_candidate",
        "research_only",
        "validation_pending",
    }
    approved_confidence = {
        "Verified",
        "Provisional",
        "Conflicting",
        "Unverified",
        "Stale",
    }
    for finding in artifact["findings"]:
        assert finding["result_label"] in approved_results
        assert finding["confidence_label"] in approved_confidence
        assert set(finding["evidence_ids"]) <= evidence_ids

    assert distinctive_raw.encode("utf-8") not in first.assembly_bytes
    assert distinctive_raw.encode("utf-8") not in first.artifact_bytes
    assert distinctive_raw not in first.markdown
    assert b'"transformed_value":null' in first.assembly_bytes
    assert first.markdown.startswith("> **Research only. Not financial advice.")
    assert "Visa via FRED (VISASMIDSA)" in first.markdown


def test_weekly_report_rejects_output_collision_without_touching_live_store(
    tmp_path: Path,
) -> None:
    frozen_path = tmp_path / "frozen_sequence.jsonl"
    frozen_path.write_bytes(b"")

    result = run_weekly_report(
        cache_path=tmp_path / "missing.sqlite",
        archive_path=tmp_path / "missing.csv",
        frozen_path=frozen_path,
        validation_artifact_path=tmp_path / "missing-validation.json",
        assembly_date="2020-06-19",
        generated_at="2020-06-19T20:00:00Z",
        assembly_artifact_path=frozen_path,
        report_artifact_path=tmp_path / "report.json",
        markdown_path=tmp_path / "report.md",
    )

    assert not result.validation.ok
    assert result.validation.errors == ["report input and output paths must be distinct"]
    assert frozen_path.read_bytes() == b""
