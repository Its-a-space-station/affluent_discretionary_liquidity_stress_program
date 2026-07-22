"""Cache-only weekly reconstruction and separate frozen-equivalent artifact."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from adls.calendarutil import (
    assembly_for_week,
    canonical_month_for_assembly,
    monthly_finalization_date,
)
from adls.contracts import PointInTimeResult, PointInTimeValue, ValidationResult
from adls.engine.canonical import FrozenRecord, freeze_canonical_month, load_frozen_sequence
from adls.engine.core import ENGINE_SPECS, HISTORICAL_FINAL_ASSUMPTION, assemble
from adls.inputs.archive import ArchiveDataset, ArchiveRow, load_archive_csv

from .models import FrozenPoint, ReconstructionResult, WeeklyAssemblyRow

UMICH_SERIES = "UMICH_SCA_T2N_TOP"
UMICH_ASSUMPTION_DEBT = "VD-002"


def _fridays_between(start: date, end: date) -> tuple[date, ...]:
    first = start - timedelta(days=(start.weekday() - 4) % 7)
    result: list[date] = []
    anchor = first
    while anchor <= end:
        assembly = assembly_for_week(anchor)
        if start <= assembly <= end:
            result.append(assembly)
        anchor += timedelta(days=7)
    return tuple(result)


class ValidationSources:
    """One read transaction plus the explicit historical-final archive view."""

    def __init__(self, cache_path: Path, archive: ArchiveDataset) -> None:
        self.validation = ValidationResult()
        self._archive = archive
        self._connection: sqlite3.Connection | None = None
        self.validation.extend(archive.validation)
        if not cache_path.is_file():
            self.validation.error(f"vintage cache does not exist: {cache_path}")
            return
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                f"{cache_path.resolve().as_uri()}?mode=ro",
                uri=True,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")
        except sqlite3.Error as exc:
            if connection is not None:
                connection.close()
            self.validation.error(f"cannot open vintage cache snapshot: {exc}")
            return
        self._connection = connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _alfred_history(self, series_id: str, assembly_date: str) -> PointInTimeResult:
        validation = ValidationResult()
        if self._connection is None:
            validation.error("vintage cache snapshot is unavailable")
            return PointInTimeResult((), validation)
        try:
            coverage = self._connection.execute(
                """
                SELECT complete_through_vintage
                FROM series_coverage
                WHERE series_id = ?
                """,
                (series_id,),
            ).fetchone()
            if coverage is None:
                validation.error(f"{series_id} has no declared cache coverage")
                return PointInTimeResult((), validation)
            complete_through = str(coverage["complete_through_vintage"])
            if complete_through < assembly_date:
                validation.error(
                    f"{series_id} assembly {assembly_date} exceeds cache coverage "
                    f"{complete_through}"
                )
                return PointInTimeResult((), validation)
            rows = self._connection.execute(
                """
                SELECT series_id, observation_date, realtime_start, realtime_end,
                       value_text, source, source_file
                FROM observation_spans
                WHERE series_id = ?
                  AND realtime_start <= ?
                  AND realtime_end >= ?
                ORDER BY observation_date, realtime_start
                """,
                (series_id, assembly_date, assembly_date),
            ).fetchall()
        except sqlite3.Error as exc:
            validation.error(f"cannot read {series_id} from vintage cache: {exc}")
            return PointInTimeResult((), validation)

        values: list[PointInTimeValue] = []
        observations: set[str] = set()
        for row in rows:
            observation = str(row["observation_date"])
            if observation in observations:
                validation.error(f"{series_id} has overlapping spans for {observation}")
                continue
            observations.add(observation)
            if str(row["series_id"]) != series_id or str(row["source"]) != "alfred":
                validation.error(f"{series_id} cache row has contradictory identity")
                continue
            release = str(row["realtime_start"])
            values.append(
                PointInTimeValue(
                    series_id=series_id,
                    observation_date=observation,
                    value_text=str(row["value_text"]),
                    release_date=release,
                    available_from=release,
                    available_through=assembly_date,
                    source="alfred",
                    source_file=(None if row["source_file"] is None else str(row["source_file"])),
                )
            )
        return PointInTimeResult(tuple(values), validation)

    def _assumed_umich_history(self, assembly_date: str) -> PointInTimeResult:
        validation = ValidationResult()
        if not self._archive.validation.ok:
            validation.error("normalized archive is invalid")
            return PointInTimeResult((), validation)
        coverage = self._archive.coverage_for(UMICH_SERIES)
        if coverage is None:
            validation.error(f"{UMICH_SERIES} has no declared archive coverage")
            return PointInTimeResult((), validation)
        if assembly_date > coverage:
            validation.error(
                f"{UMICH_SERIES} assembly {assembly_date} exceeds archive coverage {coverage}"
            )
            return PointInTimeResult((), validation)

        selected: dict[str, ArchiveRow] = {}
        for row in self._archive.rows:
            if (
                row.series_id != UMICH_SERIES
                or row.release_stage != "final"
                or row.release_date > assembly_date
            ):
                continue
            prior = selected.get(row.observation_date)
            if prior is not None and prior.value_text != row.value_text:
                validation.error(
                    f"{UMICH_SERIES} has multiple final values for {row.observation_date}"
                )
                continue
            selected[row.observation_date] = row
        values = tuple(
            PointInTimeValue(
                series_id=row.series_id,
                observation_date=row.observation_date,
                value_text=row.value_text,
                release_date=row.release_date,
                available_from=row.release_date,
                available_through=assembly_date,
                source="archive",
                source_file=row.source_file,
                release_stage=row.release_stage,
                retrieved_at=row.retrieved_at,
                availability_basis=HISTORICAL_FINAL_ASSUMPTION,
            )
            for row in sorted(
                selected.values(),
                key=lambda item: item.observation_date,
            )
        )
        return PointInTimeResult(values, validation)

    def histories_at(self, assembly_date: str) -> dict[str, PointInTimeResult]:
        return {
            spec.series_id: (
                self._assumed_umich_history(assembly_date)
                if spec.series_id == UMICH_SERIES
                else self._alfred_history(spec.series_id, assembly_date)
            )
            for spec in ENGINE_SPECS
        }


def point_from_frozen_record(record: FrozenRecord) -> FrozenPoint:
    tier_a_value = record.tier_a_value
    band = record.band
    thresholds = band.thresholds
    return FrozenPoint(
        month=record.month,
        tier_a_value=tier_a_value,
        published_band=band.published_band,
        family_values=tuple((family, state.z_score) for family, state in record.families),
        composite_abstained=record.composite_abstained,
        flags=record.assembly_flags,
        p70_threshold=None if thresholds is None else thresholds.p70,
    )


def reconstruct_frozen_equivalent(
    cache_path: Path,
    archive_path: Path,
    output_path: Path,
    *,
    start_month: str,
    end_month: str,
) -> ReconstructionResult:
    """Rebuild weekly PIT rows and a separate canonical-month JSONL sequence."""
    validation = ValidationResult()
    try:
        start = monthly_finalization_date(start_month)
        end = monthly_finalization_date(end_month)
    except ValueError as exc:
        validation.error(str(exc))
        return ReconstructionResult(b"", (), (), validation, (UMICH_ASSUMPTION_DEBT,))
    if start > end:
        validation.error("reconstruction start month is after end month")
        return ReconstructionResult(b"", (), (), validation, (UMICH_ASSUMPTION_DEBT,))

    archive = load_archive_csv(archive_path)
    sources = ValidationSources(cache_path, archive)
    validation.extend(sources.validation)
    if not validation.ok:
        sources.close()
        return ReconstructionResult(b"", (), (), validation, (UMICH_ASSUMPTION_DEBT,))

    weekly_rows: list[WeeklyAssemblyRow] = []
    frozen_bytes = b""
    points: tuple[FrozenPoint, ...] = ()
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="adls-validation-", dir=output_path.parent) as directory:
            temporary_path = Path(directory) / "frozen_equivalent.jsonl"
            for assembly_day in _fridays_between(start, end):
                assembly_text = assembly_day.isoformat()
                canonical_month = canonical_month_for_assembly(assembly_day)
                inputs = sources.histories_at(assembly_text)
                assembly = assemble(assembly_text, inputs)
                validation.extend(assembly.validation)
                weekly_rows.append(
                    WeeklyAssemblyRow(
                        assembly_date=assembly_text,
                        canonical_month=canonical_month,
                        composite_abstained=assembly.composite_abstained,
                        tier_a_value=assembly.tier_a_value,
                        flags=assembly.flags,
                    )
                )
                if canonical_month is None or not start_month <= canonical_month <= end_month:
                    continue
                frozen = freeze_canonical_month(temporary_path, canonical_month, assembly)
                validation.extend(frozen.validation)
            loaded = load_frozen_sequence(temporary_path)
            validation.extend(loaded.validation)
            expected_months = (end.year - start.year) * 12 + end.month - start.month + 1
            if len(loaded.records) != expected_months:
                validation.error(
                    f"frozen-equivalent reconstruction expected {expected_months} months, "
                    f"built {len(loaded.records)}"
                )
            if validation.ok:
                frozen_bytes = temporary_path.read_bytes()
                points = tuple(point_from_frozen_record(record) for record in loaded.records)
    except OSError as exc:
        validation.error(f"cannot build frozen-equivalent artifact: {exc}")
    finally:
        sources.close()

    if validation.ok:
        try:
            if output_path.exists():
                if output_path.read_bytes() != frozen_bytes:
                    validation.error(
                        "existing frozen-equivalent artifact differs from reconstruction"
                    )
            else:
                with TemporaryDirectory(
                    prefix="adls-frozen-equivalent-",
                    dir=output_path.parent,
                ) as directory:
                    staged_path = Path(directory) / output_path.name
                    staged_path.write_bytes(frozen_bytes)
                    staged_path.replace(output_path)
        except OSError as exc:
            validation.error(f"cannot persist frozen-equivalent artifact: {exc}")
    return ReconstructionResult(
        frozen_bytes if validation.ok else b"",
        points if validation.ok else (),
        tuple(weekly_rows),
        validation,
        (UMICH_ASSUMPTION_DEBT,),
    )
