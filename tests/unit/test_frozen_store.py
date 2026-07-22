from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from pathlib import Path
from threading import Barrier

from adls.calendarutil import monthly_finalization_date
from adls.contracts import ValidationResult
from adls.engine.canonical import freeze_canonical_month, load_frozen_sequence
from adls.engine.models import AssemblyResult, FamilyScore
from adls.engine.serialize import canonical_json_bytes

UMICH_SENTINEL = 98765.4321


def _family(
    family: str,
    series_id: str,
    z_score: float | None,
    release_date: str,
    *,
    tier: str | None = "A",
    transformed_value: float | None = 1.0,
    abstained: bool = False,
) -> FamilyScore:
    return FamilyScore(
        family=family,
        role="overlay" if family == "strain" else "leading",
        tier=tier,
        member_series_ids=(series_id,),
        member_release_dates=((series_id, release_date),),
        observation_date=None if abstained else release_date,
        transformed_value=None if abstained else transformed_value,
        z_score=z_score,
        component_z_scores=(),
        abstained=abstained,
        flags=("fixture_abstention",) if abstained else (),
    )


def _assembly(
    month: str,
    tier_a: float | None,
    *,
    tier_b: float | None = None,
    provisional: bool = False,
) -> AssemblyResult:
    finalized_on = monthly_finalization_date(month).isoformat()
    abstained = tier_a is None
    visa_z = None
    if tier_a is not None and tier_b is not None:
        visa_z = 4 * tier_b - 3 * tier_a
    families = (
        _family(
            "census_retail",
            "RSFSDP",
            tier_a,
            finalized_on,
            abstained=abstained,
        ),
        _family(
            "visa_smi",
            "VISASMIDSA",
            visa_z,
            finalized_on,
            tier="B",
            abstained=tier_b is None,
        ),
        _family(
            "household_liquidity",
            "DPSACBW027SBOG",
            tier_a,
            finalized_on,
            abstained=abstained,
        ),
        _family(
            "umich_top_tercile",
            "UMICH_SCA_T2N_TOP",
            tier_a,
            finalized_on,
            transformed_value=UMICH_SENTINEL,
            abstained=abstained,
        ),
        _family("strain", "REVOLSL", 0.25, finalized_on, tier=None),
    )
    return AssemblyResult(
        assembly_date=finalized_on,
        provisional=provisional,
        family_scores=families,
        tier_a_value=tier_a,
        tier_b_value=tier_b,
        headline_value=tier_b if tier_b is not None else tier_a,
        headline_tier=None if abstained else ("B" if tier_b is not None else "A"),
        composite_abstained=abstained,
        flags=("fixture",),
        validation=ValidationResult(),
    )


def _month_at(start_year: int, start_month: int, offset: int) -> str:
    index = start_year * 12 + start_month - 1 + offset
    year, zero_based_month = divmod(index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def test_frozen_line_is_canonical_complete_and_redacts_internal_level(tmp_path: Path) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    result = freeze_canonical_month(path, "2020-03", _assembly("2020-03", 1.25, tier_b=1.5))

    assert result.appended
    assert result.validation.ok
    blob = path.read_bytes()
    assert blob.endswith(b"\n")
    assert str(UMICH_SENTINEL).encode() not in blob
    payload = json.loads(blob)
    assert payload["schema_version"] == "adls.frozen.month.v1"
    assert payload["month"] == "2020-03"
    assert payload["finalized_on"] == "2020-05-15"
    assert payload["composite"]["tier_a_value"] == 1.25
    assert payload["families"]["umich_top_tercile"]["z_score"] == 1.25
    assert payload["input_vintages"]["UMICH_SCA_T2N_TOP"] == "2020-05-15"
    assert "UMich Table 2n: internal use only" in payload["license_notices"]


def test_rewrite_is_refused_and_later_revision_cannot_change_frozen_value(
    tmp_path: Path,
) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    original = _assembly("2020-03", 1.25)
    assert freeze_canonical_month(path, "2020-03", original).appended
    frozen_bytes = path.read_bytes()

    revised = replace(original, tier_a_value=9.5, headline_value=9.5)
    refusal = freeze_canonical_month(path, "2020-03", revised)

    assert not refusal.appended
    assert not refusal.validation.ok
    assert any("already frozen" in error for error in refusal.validation.errors)
    assert path.read_bytes() == frozen_bytes
    loaded = load_frozen_sequence(path)
    assert loaded.validation.ok
    assert loaded.records[0].tier_a_value == 1.25


def test_replay_refuses_future_input_vintage_and_composite_corruption(tmp_path: Path) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    assert freeze_canonical_month(path, "2020-03", _assembly("2020-03", 1.25)).appended
    original_payload = json.loads(path.read_bytes())

    future_vintage = json.loads(json.dumps(original_payload))
    future_vintage["input_vintages"]["UMICH_SCA_T2N_TOP"] = "2099-01-01"
    path.write_bytes(canonical_json_bytes(future_vintage))
    future_result = load_frozen_sequence(path)
    assert not future_result.validation.ok
    assert any("after finalization" in error for error in future_result.validation.errors)

    changed_composite = json.loads(json.dumps(original_payload))
    changed_composite["composite"]["tier_a_value"] = 9.5
    path.write_bytes(canonical_json_bytes(changed_composite))
    changed_result = load_frozen_sequence(path)
    assert not changed_result.validation.ok
    assert any("source assembly" in error for error in changed_result.validation.errors)


def test_source_observation_cannot_extend_beyond_finalization(tmp_path: Path) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    valid_assembly = _assembly("2020-03", 1.25)
    future_family = replace(valid_assembly.family_scores[0], observation_date="2099-01-01")
    future_assembly = replace(
        valid_assembly,
        family_scores=(future_family, *valid_assembly.family_scores[1:]),
    )

    refused = freeze_canonical_month(path, "2020-03", future_assembly)
    assert not refused.appended
    assert any(
        "observation date is after finalization" in error for error in refused.validation.errors
    )

    assert freeze_canonical_month(path, "2020-03", valid_assembly).appended
    payload = json.loads(path.read_bytes())
    source = json.loads(payload["source_assembly_json"])
    source["families"][0]["observation_date"] = "2099-01-01"
    source_bytes = canonical_json_bytes(source)
    payload["source_assembly_json"] = source_bytes.decode("utf-8")
    payload["source_assembly_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    path.write_bytes(canonical_json_bytes(payload))

    replayed = load_frozen_sequence(path)
    assert not replayed.validation.ok
    assert any(
        "observation date is after finalization" in error for error in replayed.validation.errors
    )


def test_malformed_persisted_finalization_is_collected_not_raised(tmp_path: Path) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    assert freeze_canonical_month(path, "2020-03", _assembly("2020-03", 1.25)).appended
    payload = json.loads(path.read_bytes())
    payload["finalized_on"] = "not-a-date"
    path.write_bytes(canonical_json_bytes(payload))

    loaded = load_frozen_sequence(path)

    assert not loaded.validation.ok
    assert any("finalized_on is not an ISO date" in error for error in loaded.validation.errors)


def test_concurrent_writers_cannot_append_the_same_month_twice(tmp_path: Path) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    workers = 8
    barrier = Barrier(workers)

    def append_once() -> bool:
        barrier.wait()
        return freeze_canonical_month(path, "2020-03", _assembly("2020-03", 1.25)).appended

    with ThreadPoolExecutor(max_workers=workers) as executor:
        appended = list(executor.map(lambda _: append_once(), range(workers)))

    assert sum(appended) == 1
    loaded = load_frozen_sequence(path)
    assert loaded.validation.ok
    assert len(loaded.records) == 1


def test_provisional_wrong_date_and_month_gap_are_refused_without_mutation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    provisional = freeze_canonical_month(
        path,
        "2020-01",
        _assembly("2020-01", 0.1, provisional=True),
    )
    assert not provisional.appended
    assert any("provisional" in error for error in provisional.validation.errors)

    wrong_date_assembly = replace(_assembly("2020-01", 0.1), assembly_date="2020-03-27")
    wrong_date = freeze_canonical_month(path, "2020-01", wrong_date_assembly)
    assert not wrong_date.appended
    assert any("finalization date" in error for error in wrong_date.validation.errors)
    assert not path.exists()

    assert freeze_canonical_month(path, "2020-01", _assembly("2020-01", 0.1)).appended
    frozen_bytes = path.read_bytes()
    gap = freeze_canonical_month(path, "2020-03", _assembly("2020-03", 0.3))
    assert not gap.appended
    assert any("next canonical month must be 2020-02" in error for error in gap.validation.errors)
    assert path.read_bytes() == frozen_bytes


def test_store_integrates_burn_in_dwell_and_tier_b_mapping(tmp_path: Path) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    for offset in range(35):
        month = _month_at(2019, 1, offset)
        result = freeze_canonical_month(path, month, _assembly(month, float(offset)))
        assert result.appended, result.validation.errors

    month_36 = _month_at(2019, 1, 35)
    month_37 = _month_at(2019, 1, 36)
    assert freeze_canonical_month(
        path,
        month_36,
        _assembly(month_36, 100.0, tier_b=101.0),
    ).appended
    assert freeze_canonical_month(
        path,
        month_37,
        _assembly(month_37, 102.0, tier_b=103.0),
    ).appended

    loaded = load_frozen_sequence(path)
    assert loaded.validation.ok
    assert len(loaded.records) == 37
    assert loaded.records[35].band.raw_band == "High"
    assert loaded.records[35].band.published_band is None
    assert loaded.records[35].band.candidate_count == 1
    assert loaded.records[36].band.confirmed_band == "High"
    assert loaded.records[36].band.published_band == "High"
    assert loaded.records[36].tier_b_mapped_band == "High"


def test_missing_tier_a_month_is_stored_unbanded_and_clears_pending_dwell(
    tmp_path: Path,
) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    for offset in range(36):
        month = _month_at(2019, 1, offset)
        value = 100.0 if offset == 35 else float(offset)
        assert freeze_canonical_month(path, month, _assembly(month, value)).appended

    missing_month = _month_at(2019, 1, 36)
    assert freeze_canonical_month(path, missing_month, _assembly(missing_month, None)).appended

    record = load_frozen_sequence(path).records[-1]
    assert record.tier_a_value is None
    assert record.band.raw_band is None
    assert record.band.published_band is None
    assert record.band.candidate_band is None
    assert record.band.candidate_count == 0


def test_tier_b_mapping_uses_published_interpolated_threshold(
    tmp_path: Path,
) -> None:
    path = tmp_path / "frozen_sequence.jsonl"
    # With 37 references, p70 lands 20% between ranks 25 and 26. Its exact
    # interpolation is 0.0000002 and its publication value is 0.000000.
    for offset in range(37):
        month = _month_at(2019, 1, offset)
        value = 0.0 if offset < 26 else 0.000001
        assert freeze_canonical_month(path, month, _assembly(month, value)).appended

    current_month = _month_at(2019, 1, 37)
    appended = freeze_canonical_month(
        path,
        current_month,
        _assembly(current_month, 2.0, tier_b=0.0),
    )

    assert appended.appended
    assert appended.record is not None
    assert appended.record.band.thresholds is not None
    assert appended.record.band.thresholds.p70 == 0.0
    assert appended.record.tier_b_mapped_band == "Watch"
    assert load_frozen_sequence(path).validation.ok


def test_month_helper_fixture_stays_inside_static_calendar() -> None:
    assert _month_at(2019, 1, 36) == "2022-01"
    assert monthly_finalization_date("2022-01") == date(2022, 3, 18)
