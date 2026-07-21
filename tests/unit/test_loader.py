from __future__ import annotations

from pathlib import Path

from adls.alfred.cache import VintageCache
from adls.contracts import ObservationSpan, PointInTimeValue
from adls.inputs.archive import load_archive_csv
from adls.inputs.loader import PointInTimeLoader

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "archive" / "umich_synthetic_normalized.csv"
)


def _cache(tmp_path: Path) -> VintageCache:
    cache = VintageCache(tmp_path / "test.sqlite")
    cache.initialize()
    cache.upsert_spans(
        [
            ObservationSpan(
                series_id="RSFSDP",
                observation_date="2026-04-01",
                realtime_start="2026-05-20",
                realtime_end="9999-12-31",
                value_text="100.0",
                source="alfred",
            )
        ]
    )
    cache.mark_backfilled("RSFSDP", "2026-06-30")
    return cache


def test_alfred_pit_boundary_and_coverage_are_fail_closed(tmp_path: Path) -> None:
    loader = PointInTimeLoader(_cache(tmp_path))

    before = loader.history_at("RSFSDP", "2026-05-19")
    boundary = loader.history_at("RSFSDP", "2026-05-20")
    after_coverage = loader.history_at("RSFSDP", "2026-07-01")

    assert before.validation.ok and before.values == ()
    assert boundary.validation.ok and len(boundary.values) == 1
    assert isinstance(boundary.values[0], PointInTimeValue)
    assert boundary.values[0].available_from == "2026-05-20"
    assert boundary.values[0].available_through == "2026-05-20"
    assert boundary.values[0].release_date == "2026-05-20"
    assert not after_coverage.validation.ok
    assert after_coverage.values == ()
    assert any("exceeds complete coverage" in error for error in after_coverage.validation.errors)


def test_archive_late_retrieval_and_prelim_final_boundaries(tmp_path: Path) -> None:
    dataset = load_archive_csv(FIXTURE)
    loader = PointInTimeLoader(_cache(tmp_path), dataset)

    not_retrieved = loader.history_at("UMICH_SCA_T2N_TOP", "2026-05-19", provisional=True)
    preliminary = loader.history_at("UMICH_SCA_T2N_TOP", "2026-05-20", provisional=True)
    final = loader.history_at("UMICH_SCA_T2N_TOP", "2026-05-30", provisional=True)

    assert not_retrieved.validation.ok and not_retrieved.values == ()
    assert preliminary.values[0].release_stage == "preliminary"
    assert preliminary.values[0].available_from == "2026-05-20"
    assert preliminary.values[0].available_through == "2026-05-20"
    assert final.values[0].release_stage == "final"
    assert final.values[0].available_from == "2026-05-30"


def test_umich_canonical_view_is_final_only(tmp_path: Path) -> None:
    loader = PointInTimeLoader(_cache(tmp_path), load_archive_csv(FIXTURE))

    before_final = loader.history_at("UMICH_SCA_T2N_TOP", "2026-05-20")
    at_final = loader.history_at("UMICH_SCA_T2N_TOP", "2026-05-30")

    assert before_final.validation.ok and before_final.values == ()
    assert [value.release_stage for value in at_final.values] == ["final"]
    assert at_final.values[0].value_text == "11.0"


def test_archive_refuses_assembly_after_series_coverage(tmp_path: Path) -> None:
    loader = PointInTimeLoader(_cache(tmp_path), load_archive_csv(FIXTURE))

    at_coverage = loader.history_at("UMICH_SCA_T2N_TOP", "2026-06-30")
    after_coverage = loader.history_at("UMICH_SCA_T2N_TOP", "2026-07-01")

    assert at_coverage.validation.ok
    assert len(at_coverage.values) == 2
    assert not after_coverage.validation.ok
    assert after_coverage.values == ()
    assert any("archive coverage" in error for error in after_coverage.validation.errors)


def test_loader_collects_bad_date_and_unknown_series(tmp_path: Path) -> None:
    loader = PointInTimeLoader(_cache(tmp_path), load_archive_csv(FIXTURE))

    bad_date = loader.history_at("RSFSDP", "not-a-date")
    unknown = loader.history_at("NOT_A_SERIES", "2026-05-20")

    assert not bad_date.validation.ok and bad_date.values == ()
    assert not unknown.validation.ok and unknown.values == ()


def test_archive_errors_and_missing_dataset_are_collected(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    missing_dataset = PointInTimeLoader(cache).history_at("UMICH_SCA_T2N_TOP", "2026-05-20")
    invalid_dataset = PointInTimeLoader(
        cache, load_archive_csv(tmp_path / "missing.csv")
    ).history_at("UMICH_SCA_T2N_TOP", "2026-05-20")

    assert not missing_dataset.validation.ok and missing_dataset.values == ()
    assert not invalid_dataset.validation.ok and invalid_dataset.values == ()
    assert any("cannot read archive CSV" in error for error in invalid_dataset.validation.errors)
