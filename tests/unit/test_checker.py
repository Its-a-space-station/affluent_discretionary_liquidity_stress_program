from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from adls.calendarutil import monthly_finalization_date
from adls.checker import CheckerRules, verify_band_sequence, verify_frozen_sequence
from adls.checker.sources import EvidenceSources
from adls.contracts import PointInTimeResult, ValidationResult
from adls.engine.canonical import freeze_canonical_month
from adls.engine.core import assemble
from adls.engine.models import AssemblyResult, FamilyScore
from adls.engine.serialize import canonical_json_bytes
from fixtures.engine.gen_slice3_fixture import load_fixture_inputs


def _write_cache(path: Path, inputs: dict[str, PointInTimeResult], assembly_date: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE observation_spans (
            series_id TEXT NOT NULL,
            observation_date TEXT NOT NULL,
            realtime_start TEXT NOT NULL,
            realtime_end TEXT NOT NULL,
            value_text TEXT NOT NULL,
            source TEXT NOT NULL,
            source_file TEXT,
            first_fetched_at TEXT NOT NULL,
            last_fetched_at TEXT NOT NULL,
            PRIMARY KEY (series_id, observation_date, realtime_start)
        );
        CREATE TABLE series_coverage (
            series_id TEXT PRIMARY KEY,
            complete_through_vintage TEXT NOT NULL,
            last_backfill_at TEXT NOT NULL
        );
        """
    )
    for series_id, result in sorted(inputs.items()):
        if series_id == "UMICH_SCA_T2N_TOP":
            continue
        connection.executemany(
            """
            INSERT INTO observation_spans (
                series_id, observation_date, realtime_start, realtime_end,
                value_text, source, source_file, first_fetched_at, last_fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    value.series_id,
                    value.observation_date,
                    value.available_from,
                    "9999-12-31",
                    value.value_text,
                    value.source,
                    value.source_file,
                    f"{assembly_date}T12:00:00Z",
                    f"{assembly_date}T12:00:00Z",
                )
                for value in result.values
            ],
        )
        connection.execute(
            """
            INSERT INTO series_coverage (
                series_id, complete_through_vintage, last_backfill_at
            ) VALUES (?, ?, ?)
            """,
            (series_id, assembly_date, f"{assembly_date}T12:00:00Z"),
        )

    assembly = date.fromisoformat(assembly_date)
    latest_visa = inputs["VISASMIDSA"].values[-1]
    prior_start = (assembly - timedelta(days=10)).isoformat()
    prior_end = (assembly - timedelta(days=1)).isoformat()
    future_start = (assembly + timedelta(days=1)).isoformat()
    connection.execute(
        """
        UPDATE observation_spans
        SET realtime_end = ?
        WHERE series_id = ? AND observation_date = ? AND realtime_start = ?
        """,
        (
            assembly_date,
            latest_visa.series_id,
            latest_visa.observation_date,
            assembly_date,
        ),
    )
    connection.executemany(
        """
        INSERT INTO observation_spans (
            series_id, observation_date, realtime_start, realtime_end,
            value_text, source, source_file, first_fetched_at, last_fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                latest_visa.series_id,
                latest_visa.observation_date,
                prior_start,
                prior_end,
                "80.000",
                "alfred",
                None,
                f"{prior_start}T12:00:00Z",
                f"{prior_start}T12:00:00Z",
            ),
            (
                latest_visa.series_id,
                latest_visa.observation_date,
                future_start,
                "9999-12-31",
                "70.000",
                "alfred",
                None,
                f"{future_start}T12:00:00Z",
                f"{future_start}T12:00:00Z",
            ),
        ),
    )
    connection.execute(
        """
        UPDATE series_coverage
        SET complete_through_vintage = ?
        WHERE series_id = 'VISASMIDSA'
        """,
        (future_start,),
    )
    connection.commit()
    connection.close()


def _write_archive(path: Path, result: PointInTimeResult, assembly_date: str) -> None:
    assembly = date.fromisoformat(assembly_date)
    latest = result.values[-1]
    preliminary_date = (assembly - timedelta(days=2)).isoformat()
    future_date = (assembly + timedelta(days=1)).isoformat()
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
        for value in result.values
    ]
    rows.extend(
        (
            {
                "series_id": latest.series_id,
                "observation_date": latest.observation_date,
                "value_text": "40.000",
                "release_date": preliminary_date,
                "release_stage": "preliminary",
                "source_file": latest.source_file,
                "retrieved_at": f"{preliminary_date}T12:00:00Z",
            },
            {
                "series_id": latest.series_id,
                "observation_date": latest.observation_date,
                "value_text": "10.000",
                "release_date": future_date,
                "release_stage": "final",
                "source_file": latest.source_file,
                "retrieved_at": f"{future_date}T12:00:00Z",
            },
        )
    )
    rows.sort(
        key=lambda row: (
            str(row["series_id"]),
            str(row["observation_date"]),
            max(str(row["release_date"]), str(row["retrieved_at"])[:10]),
            str(row["release_stage"]),
            str(row["retrieved_at"]),
            str(row["release_date"]),
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


@pytest.fixture
def checker_episode(tmp_path: Path) -> tuple[Path, Path, Path]:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    visa = inputs["VISASMIDSA"]
    inputs["VISASMIDSA"] = PointInTimeResult(
        (*visa.values[:-1], replace(visa.values[-1], value_text="102.000")),
        visa.validation,
    )
    h8 = inputs["DPSACBW027SBOG"]
    h8_release = "2020-05-29"  # Exactly 21 days old at the 2020-06-19 assembly.
    inputs["DPSACBW027SBOG"] = PointInTimeResult(
        tuple(
            replace(
                value,
                release_date=h8_release,
                available_from=h8_release,
            )
            for value in h8.values
        ),
        h8.validation,
    )
    umich = inputs["UMICH_SCA_T2N_TOP"]
    umich_release = (date.fromisoformat(assembly_date) - timedelta(days=1)).isoformat()
    inputs["UMICH_SCA_T2N_TOP"] = PointInTimeResult(
        tuple(replace(value, release_date=umich_release) for value in umich.values),
        umich.validation,
    )

    cache_path = tmp_path / "vintages.sqlite3"
    archive_path = tmp_path / "umich.csv"
    frozen_path = tmp_path / "frozen_sequence.jsonl"
    _write_cache(cache_path, inputs, assembly_date)
    _write_archive(archive_path, inputs["UMICH_SCA_T2N_TOP"], assembly_date)

    assembly = assemble(assembly_date, inputs)
    assert assembly.validation.ok, assembly.validation.errors
    frozen = freeze_canonical_month(frozen_path, "2020-04", assembly)
    assert frozen.appended, frozen.validation.errors
    return cache_path, archive_path, frozen_path


def test_checker_recomputes_frozen_record_from_independent_sources(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    connection = sqlite3.connect(cache_path)
    future_cache_value = connection.execute(
        """
        SELECT value_text
        FROM observation_spans
        WHERE series_id = 'VISASMIDSA' AND realtime_start > '2020-06-19'
        """
    ).fetchone()
    connection.close()
    assert future_cache_value == ("70.000",)
    assert "2020-06-20T12:00:00Z" in archive_path.read_text(encoding="utf-8")

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Verified"
    assert result.criteria_version == "adls.checker.v1"
    assert result.discrepancies == ()
    assert result.debts == ()
    assert {check.check_id for check in result.checks} == {
        "bands:2020-04",
        "source:2020-04",
    }


@pytest.mark.parametrize(
    "rules, expected_fragment",
    [
        (CheckerRules(z_ddof=1), "z_score"),
        (CheckerRules(pit_inclusive=False), "source"),
        (
            CheckerRules(staleness_days=(("DPSACBW027SBOG", 20),)),
            "household_liquidity",
        ),
    ],
)
def test_checker_flags_seeded_source_defects_as_conflicting(
    checker_episode: tuple[Path, Path, Path],
    rules: CheckerRules,
    expected_fragment: str,
) -> None:
    cache_path, archive_path, frozen_path = checker_episode

    result = verify_frozen_sequence(
        cache_path,
        (archive_path,),
        frozen_path,
        rules=rules,
    )

    assert result.label == "Conflicting"
    assert any(expected_fragment in item for item in result.discrepancies)


def test_observationally_equivalent_rule_mutation_cannot_be_verified(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode

    result = verify_frozen_sequence(
        cache_path,
        (archive_path,),
        frozen_path,
        rules=CheckerRules(staleness_days=(("DPSACBW027SBOG", 21),)),
    )

    assert result.label == "Conflicting"
    assert result.checks[-1].passed
    assert any("criteria differ" in item for item in result.discrepancies)


def test_checker_detects_source_value_changed_after_freeze(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    connection = sqlite3.connect(cache_path)
    connection.execute(
        """
        UPDATE observation_spans
        SET value_text = '999999'
        WHERE series_id = 'RSFSDP' AND observation_date = '2020-04-01'
        """
    )
    connection.commit()
    connection.close()

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Conflicting"
    assert any("census_retail" in item for item in result.discrepancies)


def test_unexpected_nested_frozen_field_is_conflicting(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    payload = json.loads(frozen_path.read_bytes())
    payload["composite"]["unexpected"] = "not in schema"
    frozen_path.write_bytes(canonical_json_bytes(payload))

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Conflicting"
    assert any("unexpected" in item for item in result.discrepancies)


def test_integer_substitution_for_published_float_is_conflicting(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    payload = json.loads(frozen_path.read_bytes())
    payload["families"]["census_retail"]["z_score"] = 3
    source = json.loads(payload["source_assembly_json"])
    source["families"][0]["z_score"] = 3
    source_bytes = canonical_json_bytes(source)
    payload["source_assembly_json"] = source_bytes.decode("utf-8")
    payload["source_assembly_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    frozen_path.write_bytes(canonical_json_bytes(payload))

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Conflicting"
    assert any("must be a JSON float" in item for item in result.discrepancies)


def test_malformed_embedded_source_outranks_missing_external_evidence(
    checker_episode: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    _, archive_path, frozen_path = checker_episode
    payload = json.loads(frozen_path.read_bytes())
    source = json.loads(payload["source_assembly_json"])
    source["composite"]["unexpected"] = "not in schema"
    source_bytes = canonical_json_bytes(source)
    payload["source_assembly_json"] = source_bytes.decode("utf-8")
    payload["source_assembly_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    frozen_path.write_bytes(canonical_json_bytes(payload))

    result = verify_frozen_sequence(
        tmp_path / "missing.sqlite3",
        (archive_path,),
        frozen_path,
    )

    assert result.label == "Conflicting"
    assert any("unexpected" in item for item in result.discrepancies)


def test_embedded_source_mismatch_outranks_missing_external_evidence(
    checker_episode: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    _, archive_path, frozen_path = checker_episode
    payload = json.loads(frozen_path.read_bytes())
    source = json.loads(payload["source_assembly_json"])
    source["families"][0]["z_score"] = -1.234567
    source_bytes = canonical_json_bytes(source)
    payload["source_assembly_json"] = source_bytes.decode("utf-8")
    payload["source_assembly_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    frozen_path.write_bytes(canonical_json_bytes(payload))

    result = verify_frozen_sequence(
        tmp_path / "missing.sqlite3",
        (archive_path,),
        frozen_path,
    )

    assert result.label == "Conflicting"
    assert any("source families" in item for item in result.discrepancies)


def test_archive_trailing_values_are_conflicting(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    lines = archive_path.read_text(encoding="utf-8").splitlines()
    archive_path.write_text(
        "\n".join((lines[0], *(f"{line},unexpected" for line in lines[1:]))) + "\n",
        encoding="utf-8",
    )

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Conflicting"
    assert any("extra values" in item for item in result.discrepancies)


def test_each_supplied_archive_csv_must_have_data_rows(
    checker_episode: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    empty_archive = tmp_path / "header_only.csv"
    empty_archive.write_text(
        archive_path.read_text(encoding="utf-8").splitlines()[0] + "\n",
        encoding="utf-8",
    )

    result = verify_frozen_sequence(
        cache_path,
        (archive_path, empty_archive),
        frozen_path,
    )

    assert result.label == "Conflicting"
    assert any("no data rows" in item for item in result.discrepancies)


def test_invalid_archive_utf8_returns_conflicting_instead_of_raising(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    archive_path.write_bytes(b"\xff\xfe\x00")

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Conflicting"
    assert result.discrepancies


def test_archive_conflict_outranks_missing_cache_but_preserves_debt(
    checker_episode: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    _, archive_path, frozen_path = checker_episode
    archive_path.write_bytes(b"\xff\xfe\x00")

    result = verify_frozen_sequence(
        tmp_path / "missing.sqlite3",
        (archive_path,),
        frozen_path,
    )

    assert result.label == "Conflicting"
    assert result.discrepancies
    assert any("vintage cache does not exist" in debt for debt in result.debts)


def test_later_archive_conflict_outranks_earlier_archive_debt(
    checker_episode: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    cache_path, _, frozen_path = checker_episode
    malformed_archive = tmp_path / "malformed.csv"
    malformed_archive.write_bytes(b"\xff\xfe\x00")

    result = verify_frozen_sequence(
        cache_path,
        (tmp_path / "missing.csv", malformed_archive),
        frozen_path,
    )

    assert result.label == "Conflicting"
    assert result.discrepancies
    assert any("missing.csv" in debt for debt in result.debts)


def test_later_source_conflict_outranks_earlier_coverage_debt(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    connection = sqlite3.connect(cache_path)
    connection.execute("DELETE FROM series_coverage WHERE series_id = 'RSFSDP'")
    connection.execute(
        """
        UPDATE observation_spans
        SET source = 'archive'
        WHERE series_id = 'VISASMIDSA' AND realtime_start = '2020-06-19'
        """
    )
    connection.commit()
    connection.close()

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Conflicting"
    assert any("VISASMIDSA" in item for item in result.discrepancies)
    assert any("RSFSDP" in debt for debt in result.debts)


def test_equivalent_zero_offset_archive_timestamps_are_normalized(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, frozen_path = checker_episode
    archive_path.write_text(
        archive_path.read_text(encoding="utf-8").replace("Z", "+00:00"),
        encoding="utf-8",
    )

    result = verify_frozen_sequence(cache_path, (archive_path,), frozen_path)

    assert result.label == "Verified"


def test_oversized_frozen_numeric_returns_conflicting_instead_of_raising(
    band_sequence: Path,
) -> None:
    payloads = [json.loads(line) for line in band_sequence.read_text().splitlines()]
    payloads[-1]["composite"]["tier_a_value"] = 10**400
    band_sequence.write_bytes(b"".join(canonical_json_bytes(payload) for payload in payloads))

    result = verify_band_sequence(band_sequence)

    assert result.label == "Conflicting"
    assert result.discrepancies


def test_extreme_float_canonicalization_returns_conflicting_instead_of_raising(
    band_sequence: Path,
) -> None:
    payloads = [json.loads(line) for line in band_sequence.read_text().splitlines()]
    payloads[-1]["composite"]["tier_a_value"] = 1e308
    band_sequence.write_text(
        "".join(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
            for payload in payloads
        ),
        encoding="utf-8",
    )

    result = verify_band_sequence(band_sequence)

    assert result.label == "Conflicting"
    assert result.discrepancies


def test_missing_source_evidence_is_provisional(
    checker_episode: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    _, archive_path, frozen_path = checker_episode

    result = verify_frozen_sequence(
        tmp_path / "missing.sqlite3",
        (archive_path,),
        frozen_path,
    )

    assert result.label == "Provisional"
    assert result.debts
    assert any(check.check_id == "source:2020-04" and not check.passed for check in result.checks)


def test_checker_holds_one_sqlite_snapshot_across_sequence_reads(
    checker_episode: tuple[Path, Path, Path],
) -> None:
    cache_path, archive_path, _ = checker_episode
    sources = EvidenceSources(cache_path, (archive_path,), CheckerRules())
    try:
        first = sources.histories_at("2020-06-19")["RSFSDP"][-1].value_text
        writer = sqlite3.connect(cache_path)
        writer.execute(
            """
            UPDATE observation_spans
            SET value_text = '999999'
            WHERE series_id = 'RSFSDP' AND observation_date = '2020-04-01'
            """
        )
        writer.commit()
        writer.close()
        second = sources.histories_at("2020-06-19")["RSFSDP"][-1].value_text
    finally:
        sources.close()

    fresh_sources = EvidenceSources(cache_path, (archive_path,), CheckerRules())
    try:
        after_reopen = fresh_sources.histories_at("2020-06-19")["RSFSDP"][-1].value_text
    finally:
        fresh_sources.close()

    assert first == second
    assert after_reopen == "999999"


def _family(family: str, z_score: float, finalized_on: str) -> FamilyScore:
    tier = "B" if family == "visa_smi" else (None if family == "strain" else "A")
    role = "overlay" if family == "strain" else "leading"
    series_id = {
        "census_retail": "RSFSDP",
        "visa_smi": "VISASMIDSA",
        "household_liquidity": "DPSACBW027SBOG",
        "umich_top_tercile": "UMICH_SCA_T2N_TOP",
        "strain": "REVOLSL",
    }[family]
    return FamilyScore(
        family=family,
        role=role,
        tier=tier,
        member_series_ids=(series_id,),
        member_release_dates=((series_id, finalized_on),),
        observation_date=finalized_on,
        transformed_value=1.0,
        z_score=z_score,
        component_z_scores=(),
        abstained=False,
        flags=(),
    )


def _band_assembly(month: str, tier_a: float) -> AssemblyResult:
    finalized_on = monthly_finalization_date(month).isoformat()
    families = (
        _family("census_retail", tier_a, finalized_on),
        _family("visa_smi", tier_a, finalized_on),
        _family("household_liquidity", tier_a, finalized_on),
        _family("umich_top_tercile", tier_a, finalized_on),
        _family("strain", 0.0, finalized_on),
    )
    return AssemblyResult(
        assembly_date=finalized_on,
        provisional=False,
        family_scores=families,
        tier_a_value=tier_a,
        tier_b_value=tier_a,
        headline_value=tier_a,
        headline_tier="B",
        composite_abstained=False,
        flags=(),
        validation=ValidationResult(),
    )


def _month_at(offset: int) -> str:
    index = 2019 * 12 + offset
    year, month_zero = divmod(index, 12)
    return f"{year:04d}-{month_zero + 1:02d}"


@pytest.fixture
def band_sequence(tmp_path: Path) -> Path:
    path = tmp_path / "bands.jsonl"
    for offset in range(35):
        month = _month_at(offset)
        assert freeze_canonical_month(path, month, _band_assembly(month, float(offset))).appended
    for offset, value in ((35, 100.0), (36, 102.0)):
        month = _month_at(offset)
        assert freeze_canonical_month(path, month, _band_assembly(month, value)).appended
    return path


def test_checker_replays_band_sequence_without_maker_band_code(band_sequence: Path) -> None:
    result = verify_band_sequence(band_sequence)

    assert result.label == "Verified"
    assert result.discrepancies == ()


@pytest.mark.parametrize(
    "rules, expected_fragment",
    [
        (CheckerRules(percentile_includes_current=True), "reference_count"),
        (CheckerRules(dwell_months=1), "published_band"),
    ],
)
def test_checker_flags_seeded_band_defects_as_conflicting(
    band_sequence: Path,
    rules: CheckerRules,
    expected_fragment: str,
) -> None:
    result = verify_band_sequence(band_sequence, rules=rules)

    assert result.label == "Conflicting"
    assert any(expected_fragment in item for item in result.discrepancies)


def test_empty_sequence_is_unverified(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.touch()

    result = verify_band_sequence(path)

    assert result.label == "Unverified"
    assert result.debts == ("frozen sequence has no records",)


def test_checker_reports_malformed_frozen_json_as_conflicting(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text(json.dumps({"month": "2020-01"}) + "\n", encoding="utf-8")

    result = verify_band_sequence(path)

    assert result.label == "Conflicting"
    assert any("frozen line 1" in item for item in result.discrepancies)


def test_deeply_nested_json_returns_conflicting_instead_of_raising(tmp_path: Path) -> None:
    path = tmp_path / "deep.jsonl"
    path.write_text("[" * 2000 + "0" + "]" * 2000 + "\n", encoding="utf-8")

    result = verify_band_sequence(path)

    assert result.label == "Conflicting"
    assert result.discrepancies
