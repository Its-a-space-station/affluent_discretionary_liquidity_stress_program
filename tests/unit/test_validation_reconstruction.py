from __future__ import annotations

import csv
import json
import math
from dataclasses import replace
from datetime import date
from pathlib import Path

from adls.alfred.cache import VintageCache
from adls.checker import verify_frozen_sequence
from adls.contracts import ObservationSpan
from adls.validation.harness import run_validation
from adls.validation.reconstruction import _fridays_between, reconstruct_frozen_equivalent
from adls.validation.spec import BASELINE_CONTRACT
from fixtures.engine.gen_slice3_fixture import load_fixture_inputs


def _write_sources(cache_path: Path, archive_path: Path) -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    cache = VintageCache(cache_path)
    cache.initialize()
    for series_id, result in sorted(inputs.items()):
        if series_id == "UMICH_SCA_T2N_TOP":
            continue
        cache.upsert_spans(
            ObservationSpan(
                series_id=value.series_id,
                observation_date=value.observation_date,
                realtime_start=value.release_date,
                realtime_end="9999-12-31",
                value_text=value.value_text,
                source="alfred",
            )
            for value in result.values
        )
        cache.mark_backfilled(series_id, assembly_date)

    for series_id, scale in (
        ("DRCARX1Q020SBEA", 1.0),
        ("DFSARX1Q020SBEA", 10.0),
    ):
        spans: list[ObservationSpan] = []
        for offset in range(20):
            index = 2017 * 4 + offset
            year, zero_based_quarter = divmod(index, 4)
            release_year, release_quarter = divmod(index + 1, 4)
            spans.append(
                ObservationSpan(
                    series_id=series_id,
                    observation_date=f"{year:04d}-{zero_based_quarter * 3 + 1:02d}-01",
                    realtime_start=(f"{release_year:04d}-{release_quarter * 3 + 1:02d}-01"),
                    realtime_end="9999-12-31",
                    value_text=str(scale * 100.0 * math.exp(0.01 * offset)),
                    source="alfred",
                )
            )
        cache.upsert_spans(spans)
        cache.mark_backfilled(series_id, "2022-02-01")

    rows = [
        {
            "series_id": value.series_id,
            "observation_date": value.observation_date,
            "value_text": value.value_text,
            "release_date": value.release_date,
            "release_stage": "final",
            "source_file": "synthetic/umich_table_2n.xls",
            "retrieved_at": "2026-07-19T12:00:00Z",
        }
        for value in inputs["UMICH_SCA_T2N_TOP"].values
    ]
    rows.sort(
        key=lambda row: (
            row["series_id"],
            row["observation_date"],
            row["retrieved_at"][:10],
            row["release_stage"],
            row["retrieved_at"],
            row["release_date"],
            row["source_file"],
        )
    )
    with archive_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_weekly_iterator_includes_a_holiday_shifted_monday_boundary() -> None:
    shifted_monday = date(2014, 4, 21)

    assert _fridays_between(shifted_monday, shifted_monday) == (shifted_monday,)


def test_reconstruction_is_separate_deterministic_flagged_and_checker_verified(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "cache.sqlite"
    archive_path = tmp_path / "umich.csv"
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    _write_sources(cache_path, archive_path)

    first = reconstruct_frozen_equivalent(
        cache_path,
        archive_path,
        first_path,
        start_month="2020-04",
        end_month="2020-04",
    )
    second = reconstruct_frozen_equivalent(
        cache_path,
        archive_path,
        second_path,
        start_month="2020-04",
        end_month="2020-04",
    )

    assert first.validation.ok, first.validation.errors
    assert second.validation.ok, second.validation.errors
    assert first.frozen_bytes == second.frozen_bytes
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.debt_ids == ("VD-002",)
    assert len(first.weekly_rows) == 1
    payload = json.loads(first.frozen_bytes)
    assert "validation_assumption:umich_unrevised_final" in payload["assembly_flags"]
    assert "2026-07-19T12:00:00Z" not in payload["source_assembly_json"]

    ordinary = verify_frozen_sequence(cache_path, (archive_path,), first_path)
    assumed = verify_frozen_sequence(
        cache_path,
        (archive_path,),
        first_path,
        assume_unrevised_archive_finals=True,
    )
    assert ordinary.label == "Conflicting"
    assert assumed.label == "Verified"
    assert assumed.criteria_version == "adls.checker.validation-assumption.v1"


def test_checker_marks_the_assumption_only_after_an_assumed_row_is_available(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "cache.sqlite"
    archive_path = tmp_path / "umich.csv"
    frozen_path = tmp_path / "frozen.jsonl"
    _write_sources(cache_path, archive_path)

    reconstruction = reconstruct_frozen_equivalent(
        cache_path,
        archive_path,
        frozen_path,
        start_month="2020-03",
        end_month="2020-03",
    )
    checked = verify_frozen_sequence(
        cache_path,
        (archive_path,),
        frozen_path,
        assume_unrevised_archive_finals=True,
    )

    assert reconstruction.validation.ok, reconstruction.validation.errors
    assert (
        "validation_assumption:umich_unrevised_final"
        not in (json.loads(reconstruction.frozen_bytes)["assembly_flags"])
    )
    assert checked.label == "Verified"


def test_reconstruction_does_not_replace_a_different_existing_artifact(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "cache.sqlite"
    archive_path = tmp_path / "umich.csv"
    output_path = tmp_path / "frozen.jsonl"
    _write_sources(cache_path, archive_path)
    output_path.write_bytes(b"different\n")

    result = reconstruct_frozen_equivalent(
        cache_path,
        archive_path,
        output_path,
        start_month="2020-04",
        end_month="2020-04",
    )

    assert not result.validation.ok
    assert output_path.read_bytes() == b"different\n"
    assert any("differs" in error for error in result.validation.errors)


def test_reconstruction_reports_an_invalid_output_path_as_validation_data(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "cache.sqlite"
    archive_path = tmp_path / "umich.csv"
    output_path = tmp_path / "frozen.jsonl"
    _write_sources(cache_path, archive_path)
    output_path.mkdir()

    result = reconstruct_frozen_equivalent(
        cache_path,
        archive_path,
        output_path,
        start_month="2020-04",
        end_month="2020-04",
    )

    assert not result.validation.ok
    assert result.frozen_bytes == b""
    assert any("cannot persist" in error for error in result.validation.errors)


def test_validation_run_snapshots_then_checker_verifies_all_evidence(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    archive_path = tmp_path / "umich.csv"
    frozen_path = tmp_path / "frozen.jsonl"
    artifact_path = tmp_path / "nested" / "validation.json"
    _write_sources(cache_path, archive_path)
    reconstruction = reconstruct_frozen_equivalent(
        cache_path,
        archive_path,
        frozen_path,
        start_month="2020-04",
        end_month="2020-04",
    )
    contract = replace(BASELINE_CONTRACT, trial_count=2)

    first = run_validation(
        frozen_path,
        cache_path,
        archive_path,
        artifact_path,
        contract,
    )
    second = run_validation(
        frozen_path,
        cache_path,
        archive_path,
        artifact_path,
        contract,
    )

    assert reconstruction.validation.ok, reconstruction.validation.errors
    assert first.validation.ok, first.validation.errors
    assert second.validation.ok, second.validation.errors
    assert first.artifact_bytes == second.artifact_bytes == artifact_path.read_bytes()
    payload = json.loads(first.artifact_bytes)
    assert payload["source"]["checker_label"] == "Verified"
    assert payload["source"]["checker_criteria_version"] == (
        "adls.checker.validation-assumption.v1"
    )
    assert payload["source"]["checker_check_count"] == 2
    assert payload["source"]["outcome_vintage"] == "2022-02-01"

    directory_artifact = tmp_path / "artifact-directory"
    directory_artifact.mkdir()
    failed = run_validation(
        frozen_path,
        cache_path,
        archive_path,
        directory_artifact,
        contract,
    )
    assert not failed.validation.ok
    assert any("cannot persist" in error for error in failed.validation.errors)
