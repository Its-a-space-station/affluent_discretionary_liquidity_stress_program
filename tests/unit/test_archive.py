from __future__ import annotations

from pathlib import Path

from adls.inputs.archive import load_archive_csv

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "archive" / "umich_synthetic_normalized.csv"
)


def _write_csv(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "archive.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_valid_csv_builds_bounded_nonoverlapping_spans() -> None:
    dataset = load_archive_csv(FIXTURE)

    assert dataset.validation.ok
    assert dataset.validation.warnings == []
    assert dataset.coverage_for("UMICH_SCA_T2N_TOP") == "2026-06-30"
    april = [span for span in dataset.spans if span.observation_date == "2026-04-01"]
    assert [(span.realtime_start, span.realtime_end, span.release_stage) for span in april] == [
        ("2026-05-20", "2026-05-29", "preliminary"),
        ("2026-05-30", "2026-06-30", "final"),
    ]


def test_missing_columns_are_collected_not_raised(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "series_id,observation_date,release_date\nUMICH_SCA_T2N_TOP,2026-04-01,2026-05-15\n",
    )

    dataset = load_archive_csv(path)

    assert not dataset.validation.ok
    assert any("missing required columns" in error for error in dataset.validation.errors)
    assert dataset.rows == ()
    assert dataset.spans == ()


def test_contract_collects_stage_sort_duplicate_and_conflict_errors(
    tmp_path: Path,
) -> None:
    path = _write_csv(
        tmp_path,
        "series_id,observation_date,value_text,release_date,release_stage,"
        "source_file,retrieved_at\n"
        "UMICH_SCA_T2N_TOP,2026-05-01,30,2026-06-30,final,synth.xls,"
        "2026-06-30T12:00:00Z\n"
        "UMICH_SCA_T2N_TOP,2026-04-01,9,2026-05-15,draft,synth.xls,"
        "2026-05-15T12:00:00\n"
        "UMICH_SCA_T2N_TOP,2026-04-01,10,2026-05-30,final,synth.xls,"
        "2026-05-30T12:00:00Z\n"
        "UMICH_SCA_T2N_TOP,2026-04-01,10,2026-05-30,final,synth.xls,"
        "2026-05-30T12:00:00Z\n"
        "UMICH_SCA_T2N_TOP,2026-04-01,11,2026-05-20,preliminary,synth.xls,"
        "2026-05-30T13:00:00Z\n",
    )

    validation = load_archive_csv(path).validation

    assert not validation.ok
    assert any("invalid release_stage" in error for error in validation.errors)
    assert any("UTC timestamp" in error for error in validation.errors)
    assert any("canonical sort sequence" in error for error in validation.errors)
    assert any("duplicate row" in error for error in validation.errors)
    assert any("same effective date" in error for error in validation.errors)


def test_monthly_observation_gap_is_collected_as_warning(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "series_id,observation_date,value_text,release_date,release_stage,"
        "source_file,retrieved_at\n"
        "UMICH_SCA_T2N_TOP,2026-01-01,10,2026-02-28,final,synth.xls,"
        "2026-02-28T12:00:00Z\n"
        "UMICH_SCA_T2N_TOP,2026-03-01,12,2026-04-30,final,synth.xls,"
        "2026-04-30T12:00:00Z\n",
    )

    dataset = load_archive_csv(path)

    assert dataset.validation.ok
    assert any("observation gap" in warning for warning in dataset.validation.warnings)


def test_missing_file_is_collected_not_raised(tmp_path: Path) -> None:
    dataset = load_archive_csv(tmp_path / "missing.csv")
    assert not dataset.validation.ok
    assert any("cannot read archive CSV" in error for error in dataset.validation.errors)


def test_row_chronology_path_and_extra_values_are_collected(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "series_id,observation_date,value_text,release_date,release_stage,"
        "source_file,retrieved_at\n"
        "UMICH_SCA_T2N_TOP,2026-05-01,10,2026-04-30,final,../raw.xls,"
        "2026-05-01T12:00:00Z\n"
        "UMICH_SCA_T2N_TOP,2026-06-01,11,2026-06-30,final,synth.xls,"
        "2026-06-30T12:00:00Z,unexpected\n",
    )

    validation = load_archive_csv(path).validation

    assert not validation.ok
    assert any("precedes observation_date" in error for error in validation.errors)
    assert any("safe relative path" in error for error in validation.errors)
    assert any("unexpected extra values" in error for error in validation.errors)
