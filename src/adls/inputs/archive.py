"""Validation and episode construction for normalized self-archive CSVs."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath

from adls.contracts import ObservationSpan, ValidationResult
from adls.registry import by_id

REQUIRED_COLUMNS: tuple[str, ...] = (
    "series_id",
    "observation_date",
    "value_text",
    "release_date",
    "release_stage",
    "source_file",
    "retrieved_at",
)
RELEASE_STAGES = frozenset({"preliminary", "final", "revision", "not_applicable"})
UMICH_STAGES = frozenset({"preliminary", "final"})


@dataclass(frozen=True)
class ArchiveRow:
    series_id: str
    observation_date: str
    value_text: str
    release_date: str
    release_stage: str
    source_file: str
    retrieved_at: str

    @property
    def retrieval_date(self) -> str:
        return self.retrieved_at[:10]

    @property
    def effective_available_date(self) -> str:
        return max(self.release_date, self.retrieval_date)

    def sort_key(self) -> tuple[str, ...]:
        return (
            self.series_id,
            self.observation_date,
            self.effective_available_date,
            self.release_stage,
            self.retrieved_at,
            self.release_date,
            self.source_file,
        )


@dataclass(frozen=True)
class ArchiveDataset:
    rows: tuple[ArchiveRow, ...]
    spans: tuple[ObservationSpan, ...]
    coverage: tuple[tuple[str, str], ...]
    validation: ValidationResult

    def coverage_for(self, series_id: str) -> str | None:
        for candidate, complete_through in self.coverage:
            if candidate == series_id:
                return complete_through
        return None

    def spans_for(
        self,
        series_id: str,
        release_stages: frozenset[str] | None = None,
    ) -> tuple[ObservationSpan, ...]:
        if not self.validation.ok:
            return ()
        selected = tuple(
            row
            for row in self.rows
            if row.series_id == series_id
            and (release_stages is None or row.release_stage in release_stages)
        )
        coverage = self.coverage_for(series_id)
        if coverage is None:
            return ()
        return _rows_to_spans(selected, {series_id: coverage})


def _empty_dataset(validation: ValidationResult) -> ArchiveDataset:
    return ArchiveDataset((), (), (), validation)


def _parse_iso_date(text: str) -> date:
    parsed = date.fromisoformat(text)
    if parsed.isoformat() != text:
        raise ValueError("date is not canonical ISO")
    return parsed


def _parse_utc_timestamp(text: str) -> tuple[datetime, str]:
    candidate = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp is not UTC")
    utc_value = parsed.astimezone(UTC)
    timespec = "microseconds" if utc_value.microsecond else "seconds"
    canonical = utc_value.isoformat(timespec=timespec).replace("+00:00", "Z")
    return utc_value, canonical


def _parse_row(
    raw: dict[str, str | None], line_number: int, validation: ValidationResult
) -> ArchiveRow | None:
    fields: dict[str, str] = {}
    missing_values: list[str] = []
    for column in REQUIRED_COLUMNS:
        value = raw.get(column)
        if value is None:
            missing_values.append(column)
        else:
            fields[column] = value
    if missing_values:
        validation.error(
            f"line {line_number}: missing values for {', '.join(sorted(missing_values))}"
        )
        return None

    invalid = False
    series_id = fields["series_id"].strip()
    value_text = fields["value_text"]
    release_stage = fields["release_stage"].strip()
    source_file = fields["source_file"].strip()

    try:
        spec = by_id(series_id)
    except KeyError:
        validation.error(f"line {line_number}: unknown series_id {series_id!r}")
        spec = None
        invalid = True
    else:
        if spec is not None and spec.source != "archive":
            validation.error(f"line {line_number}: series {series_id} is not archive-backed")
            invalid = True

    if not value_text.strip():
        validation.error(f"line {line_number}: value_text is empty")
        invalid = True
    if not source_file:
        validation.error(f"line {line_number}: source_file is empty")
        invalid = True
    elif PurePosixPath(source_file).is_absolute() or ".." in PurePosixPath(source_file).parts:
        validation.error(f"line {line_number}: source_file must be a safe relative path")
        invalid = True
    if release_stage not in RELEASE_STAGES:
        validation.error(f"line {line_number}: invalid release_stage {release_stage!r}")
        invalid = True
    elif (
        spec is not None and spec.license == "umich_internal" and release_stage not in UMICH_STAGES
    ):
        validation.error(f"line {line_number}: UMich release_stage must be preliminary or final")
        invalid = True

    observation_date: date | None = None
    release_date: date | None = None
    retrieved_at: datetime | None = None
    retrieved_text = ""
    try:
        observation_date = _parse_iso_date(fields["observation_date"].strip())
    except ValueError:
        validation.error(f"line {line_number}: invalid observation_date")
        invalid = True
    try:
        release_date = _parse_iso_date(fields["release_date"].strip())
    except ValueError:
        validation.error(f"line {line_number}: invalid release_date")
        invalid = True
    try:
        retrieved_at, retrieved_text = _parse_utc_timestamp(fields["retrieved_at"].strip())
    except ValueError:
        validation.error(f"line {line_number}: retrieved_at must be a UTC timestamp")
        invalid = True

    if (
        observation_date is not None
        and release_date is not None
        and release_date < observation_date
    ):
        validation.error(f"line {line_number}: release_date precedes observation_date")
        invalid = True
    if (
        release_date is not None
        and retrieved_at is not None
        and release_date > retrieved_at.date()
    ):
        validation.error(f"line {line_number}: release_date is after retrieved_at")
        invalid = True

    if invalid or observation_date is None or release_date is None or retrieved_at is None:
        return None
    return ArchiveRow(
        series_id=series_id,
        observation_date=observation_date.isoformat(),
        value_text=value_text,
        release_date=release_date.isoformat(),
        release_stage=release_stage,
        source_file=source_file,
        retrieved_at=retrieved_text,
    )


def _coverage_for_rows(rows: Iterable[ArchiveRow]) -> dict[str, str]:
    coverage: dict[str, str] = {}
    for row in rows:
        coverage[row.series_id] = max(
            coverage.get(row.series_id, row.retrieval_date), row.retrieval_date
        )
    return coverage


def _rows_to_spans(
    rows: Iterable[ArchiveRow], coverage: dict[str, str]
) -> tuple[ObservationSpan, ...]:
    grouped: dict[tuple[str, str], list[ArchiveRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.series_id, row.observation_date)].append(row)

    spans: list[ObservationSpan] = []
    for key in sorted(grouped):
        episodes = sorted(grouped[key], key=ArchiveRow.sort_key)
        for index, row in enumerate(episodes):
            if index + 1 < len(episodes):
                next_date = date.fromisoformat(episodes[index + 1].effective_available_date)
                realtime_end = (next_date - timedelta(days=1)).isoformat()
            else:
                realtime_end = coverage[row.series_id]
            spans.append(
                ObservationSpan(
                    series_id=row.series_id,
                    observation_date=row.observation_date,
                    realtime_start=row.effective_available_date,
                    realtime_end=realtime_end,
                    value_text=row.value_text,
                    source="archive",
                    source_file=row.source_file,
                    release_date=row.release_date,
                    release_stage=row.release_stage,
                    retrieved_at=row.retrieved_at,
                )
            )
    return tuple(spans)


def _has_frequency_gap(frequency: str, earlier: date, later: date) -> bool:
    if frequency == "m":
        return (later.year * 12 + later.month) - (earlier.year * 12 + earlier.month) > 1
    if frequency == "q":
        earlier_q = earlier.year * 4 + (earlier.month - 1) // 3
        later_q = later.year * 4 + (later.month - 1) // 3
        return later_q - earlier_q > 1
    if frequency == "w":
        return (later - earlier).days > 8
    return False


def _collect_gap_warnings(rows: Iterable[ArchiveRow], validation: ValidationResult) -> None:
    observations: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        observations[row.series_id].add(row.observation_date)
    for series_id in sorted(observations):
        dates = sorted(date.fromisoformat(value) for value in observations[series_id])
        frequency = by_id(series_id).frequency
        for earlier, later in zip(dates, dates[1:], strict=False):
            if _has_frequency_gap(frequency, earlier, later):
                validation.warn(
                    f"{series_id}: observation gap from {earlier.isoformat()} "
                    f"to {later.isoformat()}"
                )


def load_archive_csv(path: Path) -> ArchiveDataset:
    """Load and validate one normalized CSV without raising on data problems."""
    validation = ValidationResult()
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as exc:
        validation.error(f"cannot read archive CSV ({exc.__class__.__name__})")
        return _empty_dataset(validation)

    rows_with_lines: list[tuple[int, ArchiveRow]] = []
    try:
        with handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            if headers is None:
                validation.error("archive CSV has no header")
                return _empty_dataset(validation)
            duplicate_headers = sorted(
                header for header in set(headers) if headers.count(header) > 1
            )
            if duplicate_headers:
                validation.error(
                    f"archive CSV has duplicate columns: {', '.join(duplicate_headers)}"
                )
            missing_columns = sorted(set(REQUIRED_COLUMNS) - set(headers))
            if missing_columns:
                validation.error(
                    f"archive CSV missing required columns: {', '.join(missing_columns)}"
                )
                return _empty_dataset(validation)
            extra_columns = sorted(set(headers) - set(REQUIRED_COLUMNS))
            if extra_columns:
                validation.warn(f"archive CSV has ignored columns: {', '.join(extra_columns)}")
            for line_number, raw in enumerate(reader, start=2):
                if len(raw) > len(headers):
                    validation.error(f"line {line_number}: row has unexpected extra values")
                    continue
                parsed = _parse_row(raw, line_number, validation)
                if parsed is not None:
                    rows_with_lines.append((line_number, parsed))
    except (OSError, csv.Error, UnicodeError) as exc:
        validation.error(f"cannot parse archive CSV ({exc.__class__.__name__})")

    if not rows_with_lines and validation.ok:
        validation.error("archive CSV has no data rows")
        return _empty_dataset(validation)

    previous_key: tuple[str, ...] | None = None
    seen_rows: dict[ArchiveRow, int] = {}
    seen_effective: dict[tuple[str, str, str], int] = {}
    unique_rows: list[ArchiveRow] = []
    for line_number, row in rows_with_lines:
        sort_key = row.sort_key()
        if previous_key is not None and sort_key < previous_key:
            validation.error(f"line {line_number}: row is not in canonical sort sequence")
        previous_key = sort_key

        duplicate_line = seen_rows.get(row)
        if duplicate_line is not None:
            validation.error(
                f"line {line_number}: duplicate row first seen on line {duplicate_line}"
            )
            continue
        seen_rows[row] = line_number

        effective_key = (
            row.series_id,
            row.observation_date,
            row.effective_available_date,
        )
        conflict_line = seen_effective.get(effective_key)
        if conflict_line is not None:
            validation.error(
                f"line {line_number}: multiple episodes share the same effective date; "
                f"first seen on line {conflict_line}"
            )
        else:
            seen_effective[effective_key] = line_number
        unique_rows.append(row)

    sorted_rows = tuple(sorted(unique_rows, key=ArchiveRow.sort_key))
    _collect_gap_warnings(sorted_rows, validation)
    coverage_map = _coverage_for_rows(sorted_rows)
    coverage = tuple(sorted(coverage_map.items()))
    spans = _rows_to_spans(sorted_rows, coverage_map) if validation.ok else ()
    return ArchiveDataset(sorted_rows, spans, coverage, validation)
