"""Independent point-in-time reads from SQLite cache and normalized archives."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath

from .constants import SERIES_RULES
from .models import CheckerRules, SeriesRule, SourceValue

ARCHIVE_COLUMNS = (
    "series_id",
    "observation_date",
    "value_text",
    "release_date",
    "release_stage",
    "source_file",
    "retrieved_at",
)


class EvidenceUnavailable(RuntimeError):
    """Required evidence cannot be checked from the supplied local artifacts."""


class EvidenceConflict(RuntimeError):
    """Supplied evidence violates the checker's independent source contract."""

    def __init__(self, message: str, *, debts: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.debts = debts


@dataclass(frozen=True)
class _ArchiveEntry:
    series_id: str
    observation_date: str
    value_text: str
    release_date: str
    release_stage: str
    source_file: str
    retrieved_at: str
    retrieval_date: str
    effective_date: str

    def sort_key(self) -> tuple[str, ...]:
        return (
            self.series_id,
            self.observation_date,
            self.effective_date,
            self.release_stage,
            self.retrieved_at,
            self.release_date,
            self.source_file,
        )


def _iso_date(text: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceConflict(f"{field} is not an ISO date: {text!r}") from exc
    if parsed.isoformat() != text:
        raise EvidenceConflict(f"{field} is not a canonical ISO date: {text!r}")
    return parsed


def _utc_timestamp(text: str, field: str) -> tuple[datetime, str]:
    candidate = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise EvidenceConflict(f"{field} is not a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise EvidenceConflict(f"{field} is not a UTC timestamp")
    utc_value = parsed.astimezone(UTC)
    timespec = "microseconds" if utc_value.microsecond else "seconds"
    canonical = utc_value.isoformat(timespec=timespec).replace("+00:00", "Z")
    return utc_value, canonical


def _parse_archive_entry(raw: dict[str, str | None], location: str) -> _ArchiveEntry:
    missing = [field for field in ARCHIVE_COLUMNS if raw.get(field) is None]
    if missing:
        raise EvidenceConflict(f"{location} is missing values for {', '.join(missing)}")
    fields = {field: str(raw[field]) for field in ARCHIVE_COLUMNS}
    series_id = fields["series_id"].strip()
    matching = [rule for rule in SERIES_RULES if rule.series_id == series_id]
    if len(matching) != 1 or matching[0].source != "archive":
        raise EvidenceConflict(f"{location} has unsupported archive series {series_id!r}")

    observation = _iso_date(fields["observation_date"].strip(), f"{location} observation_date")
    release = _iso_date(fields["release_date"].strip(), f"{location} release_date")
    retrieved, retrieved_text = _utc_timestamp(
        fields["retrieved_at"].strip(),
        f"{location} retrieved_at",
    )
    if release < observation:
        raise EvidenceConflict(f"{location} release precedes observation")
    if release > retrieved.date():
        raise EvidenceConflict(f"{location} release is after retrieval")

    value_text = fields["value_text"]
    if not value_text.strip():
        raise EvidenceConflict(f"{location} value_text is empty")
    release_stage = fields["release_stage"].strip()
    if release_stage not in {"preliminary", "final"}:
        raise EvidenceConflict(f"{location} has unsupported release_stage {release_stage!r}")
    source_file = fields["source_file"].strip()
    source_path = PurePosixPath(source_file)
    if not source_file or source_path.is_absolute() or ".." in source_path.parts:
        raise EvidenceConflict(f"{location} source_file is not a safe relative path")

    retrieval_date = retrieved.date().isoformat()
    return _ArchiveEntry(
        series_id=series_id,
        observation_date=observation.isoformat(),
        value_text=value_text,
        release_date=release.isoformat(),
        release_stage=release_stage,
        source_file=source_file,
        retrieved_at=retrieved_text,
        retrieval_date=retrieval_date,
        effective_date=max(release.isoformat(), retrieval_date),
    )


def _read_archive(path: Path) -> tuple[_ArchiveEntry, ...]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as exc:
        raise EvidenceUnavailable(f"cannot read archive CSV {path.name}: {exc}") from exc

    entries: list[_ArchiveEntry] = []
    with handle:
        try:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            if headers is None:
                raise EvidenceConflict(f"archive CSV {path.name} has no header")
            duplicates = sorted(header for header in set(headers) if headers.count(header) > 1)
            if duplicates:
                raise EvidenceConflict(
                    f"archive CSV {path.name} repeats columns: {', '.join(duplicates)}"
                )
            missing = sorted(set(ARCHIVE_COLUMNS) - set(headers))
            if missing:
                raise EvidenceConflict(
                    f"archive CSV {path.name} misses columns: {', '.join(missing)}"
                )
            prior_key: tuple[str, ...] | None = None
            for line_number, raw in enumerate(reader, 2):
                if None in raw:
                    raise EvidenceConflict(
                        f"archive CSV {path.name}:{line_number} has unexpected extra values"
                    )
                entry = _parse_archive_entry(raw, f"{path.name}:{line_number}")
                key = entry.sort_key()
                if prior_key is not None and key < prior_key:
                    raise EvidenceConflict(
                        f"archive CSV {path.name}:{line_number} is not canonically sorted"
                    )
                prior_key = key
                entries.append(entry)
        except (UnicodeError, csv.Error) as exc:
            raise EvidenceConflict(f"cannot parse archive CSV {path.name}: {exc}") from exc
        except OSError as exc:
            raise EvidenceUnavailable(f"cannot read archive CSV {path.name}: {exc}") from exc
    if not entries:
        raise EvidenceConflict(f"archive CSV {path.name} has no data rows")
    return tuple(entries)


def _read_archives(paths: tuple[Path, ...]) -> tuple[_ArchiveEntry, ...]:
    if not paths:
        raise EvidenceUnavailable("no normalized archive CSV was supplied")
    entries: list[_ArchiveEntry] = []
    conflicts: list[str] = []
    debts: list[str] = []
    for path in paths:
        try:
            entries.extend(_read_archive(path))
        except EvidenceConflict as exc:
            conflicts.append(str(exc))
            debts.extend(exc.debts)
        except EvidenceUnavailable as exc:
            debts.append(str(exc))

    seen_rows: set[_ArchiveEntry] = set()
    seen_effective: set[tuple[str, str, str]] = set()
    for entry in entries:
        if entry in seen_rows:
            conflicts.append("archive contains a duplicate row")
        else:
            seen_rows.add(entry)
        effective_key = (entry.series_id, entry.observation_date, entry.effective_date)
        if effective_key in seen_effective:
            conflicts.append("archive contains conflicting episodes at one effective date")
        else:
            seen_effective.add(effective_key)
    if conflicts:
        raise EvidenceConflict("; ".join(conflicts), debts=tuple(debts))
    if debts:
        raise EvidenceUnavailable("; ".join(debts))
    return tuple(sorted(entries, key=_ArchiveEntry.sort_key))


class EvidenceSources:
    """Reusable, read-only evidence handle for a sequence of checker assemblies."""

    def __init__(
        self,
        cache_path: Path,
        archive_paths: tuple[Path, ...],
        rules: CheckerRules,
    ) -> None:
        archive_entries: tuple[_ArchiveEntry, ...] = ()
        archive_conflict: EvidenceConflict | None = None
        debts: list[str] = []
        try:
            archive_entries = _read_archives(archive_paths)
        except EvidenceConflict as exc:
            archive_conflict = exc
        except EvidenceUnavailable as exc:
            debts.append(str(exc))

        connection: sqlite3.Connection | None = None
        if not cache_path.is_file():
            debts.append(f"vintage cache does not exist: {cache_path}")
        else:
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
                connection = None
                debts.append(f"cannot open a vintage cache snapshot: {exc}")

        if archive_conflict is not None:
            if connection is not None:
                connection.close()
            raise EvidenceConflict(
                str(archive_conflict),
                debts=(*archive_conflict.debts, *debts),
            )
        if debts:
            if connection is not None:
                connection.close()
            raise EvidenceUnavailable("; ".join(debts))
        if connection is None:
            raise EvidenceUnavailable("vintage cache snapshot is unavailable")

        self._connection = connection
        self._archive_entries = archive_entries
        self._rules = rules

    def close(self) -> None:
        self._connection.close()

    def histories_at(self, assembly_date: str) -> dict[str, tuple[SourceValue, ...]]:
        _iso_date(assembly_date, "assembly_date")
        histories: dict[str, tuple[SourceValue, ...]] = {}
        conflicts: list[str] = []
        debts: list[str] = []
        for rule in SERIES_RULES:
            try:
                histories[rule.series_id] = self._history_at(rule, assembly_date)
            except EvidenceConflict as exc:
                conflicts.append(str(exc))
                debts.extend(exc.debts)
            except EvidenceUnavailable as exc:
                debts.append(str(exc))
        if conflicts:
            raise EvidenceConflict("; ".join(conflicts), debts=tuple(debts))
        if debts:
            raise EvidenceUnavailable("; ".join(debts))
        return histories

    def _history_at(
        self,
        rule: SeriesRule,
        assembly_date: str,
    ) -> tuple[SourceValue, ...]:
        if rule.source == "archive":
            return self._archive_history(rule, assembly_date)
        return self._alfred_history(rule, assembly_date)

    def _alfred_history(
        self,
        rule: SeriesRule,
        assembly_date: str,
    ) -> tuple[SourceValue, ...]:
        try:
            coverage_row = self._connection.execute(
                """
                SELECT complete_through_vintage
                FROM series_coverage
                WHERE series_id = ?
                """,
                (rule.series_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise EvidenceUnavailable(f"cannot read vintage cache coverage: {exc}") from exc
        if coverage_row is None:
            raise EvidenceUnavailable(f"{rule.series_id} has no declared cache coverage")
        coverage = str(coverage_row["complete_through_vintage"])
        _iso_date(coverage, f"{rule.series_id} cache coverage")
        if coverage < assembly_date:
            raise EvidenceUnavailable(
                f"{rule.series_id} assembly {assembly_date} exceeds cache coverage {coverage}"
            )

        operator = "<=" if self._rules.pit_inclusive else "<"
        sql = f"""
            SELECT series_id, observation_date, realtime_start, realtime_end,
                   value_text, source, source_file
            FROM observation_spans
            WHERE series_id = ?
              AND realtime_start {operator} ?
              AND realtime_end >= ?
            ORDER BY observation_date, realtime_start
        """
        try:
            rows = self._connection.execute(
                sql,
                (rule.series_id, assembly_date, assembly_date),
            ).fetchall()
        except sqlite3.Error as exc:
            raise EvidenceUnavailable(f"cannot read vintage cache spans: {exc}") from exc

        values: list[SourceValue] = []
        seen_observations: set[str] = set()
        for row in rows:
            series_id = str(row["series_id"])
            observation_date = str(row["observation_date"])
            realtime_start = str(row["realtime_start"])
            realtime_end = str(row["realtime_end"])
            source = str(row["source"])
            _iso_date(observation_date, f"{series_id} observation_date")
            _iso_date(realtime_start, f"{series_id} realtime_start")
            _iso_date(realtime_end, f"{series_id} realtime_end")
            if series_id != rule.series_id or source != "alfred":
                raise EvidenceConflict(f"{rule.series_id} cache span has contradictory identity")
            if observation_date in seen_observations:
                raise EvidenceConflict(
                    f"{rule.series_id} has overlapping spans for {observation_date}"
                )
            seen_observations.add(observation_date)
            values.append(
                SourceValue(
                    series_id=series_id,
                    observation_date=observation_date,
                    value_text=str(row["value_text"]),
                    release_date=realtime_start,
                    available_from=realtime_start,
                    source=source,
                    source_file=(None if row["source_file"] is None else str(row["source_file"])),
                )
            )
        return tuple(values)

    def _archive_history(
        self,
        rule: SeriesRule,
        assembly_date: str,
    ) -> tuple[SourceValue, ...]:
        series_rows = tuple(
            entry for entry in self._archive_entries if entry.series_id == rule.series_id
        )
        if not series_rows:
            raise EvidenceUnavailable(f"{rule.series_id} has no declared archive coverage")
        coverage = max(entry.retrieval_date for entry in series_rows)
        if coverage < assembly_date:
            raise EvidenceUnavailable(
                f"{rule.series_id} assembly {assembly_date} exceeds archive coverage {coverage}"
            )

        eligible: dict[str, _ArchiveEntry] = {}
        for entry in series_rows:
            if entry.release_stage != "final":
                continue
            available = (
                entry.effective_date <= assembly_date
                if self._rules.pit_inclusive
                else entry.effective_date < assembly_date
            )
            if not available:
                continue
            prior = eligible.get(entry.observation_date)
            if prior is None or entry.sort_key() > prior.sort_key():
                eligible[entry.observation_date] = entry

        return tuple(
            SourceValue(
                series_id=entry.series_id,
                observation_date=entry.observation_date,
                value_text=entry.value_text,
                release_date=entry.release_date,
                available_from=entry.effective_date,
                source="archive",
                source_file=entry.source_file,
                release_stage=entry.release_stage,
                retrieved_at=entry.retrieved_at,
            )
            for entry in sorted(eligible.values(), key=lambda item: item.observation_date)
        )
