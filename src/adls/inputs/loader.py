"""Uniform point-in-time view across ALFRED and normalized archives."""

from __future__ import annotations

from datetime import date

from adls.alfred.cache import VintageCache, VintageCoverageError
from adls.contracts import (
    ObservationSpan,
    PointInTimeResult,
    PointInTimeValue,
    ValidationResult,
)
from adls.inputs.archive import UMICH_STAGES, ArchiveDataset
from adls.registry import by_id


def _parse_assembly_date(text: str, validation: ValidationResult) -> str | None:
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        validation.error(f"invalid assembly date {text!r}")
        return None
    if parsed.isoformat() != text:
        validation.error(f"invalid assembly date {text!r}")
        return None
    return parsed.isoformat()


def _to_value(span: ObservationSpan, assembly_date: str) -> PointInTimeValue:
    return PointInTimeValue(
        series_id=span.series_id,
        observation_date=span.observation_date,
        value_text=span.value_text,
        release_date=span.release_date or span.realtime_start,
        available_from=span.realtime_start,
        available_through=min(span.realtime_end, assembly_date),
        source=span.source,
        source_file=span.source_file,
        release_stage=span.release_stage,
        retrieved_at=span.retrieved_at,
    )


class PointInTimeLoader:
    def __init__(
        self,
        cache: VintageCache,
        archive: ArchiveDataset | None = None,
    ) -> None:
        self._cache = cache
        self._archive = archive

    def history_at(
        self,
        series_id: str,
        assembly_date: str,
        *,
        provisional: bool = False,
    ) -> PointInTimeResult:
        validation = ValidationResult()
        as_of = _parse_assembly_date(assembly_date, validation)
        if as_of is None:
            return PointInTimeResult((), validation)

        try:
            spec = by_id(series_id)
        except KeyError:
            validation.error(f"unknown series_id {series_id!r}")
            return PointInTimeResult((), validation)

        if spec.source == "alfred":
            try:
                spans = self._cache.series_spans_at_vintage(series_id, as_of)
            except VintageCoverageError as exc:
                validation.error(str(exc))
                return PointInTimeResult((), validation)
            return PointInTimeResult(tuple(_to_value(span, as_of) for span in spans), validation)

        if spec.source != "archive":
            validation.error(f"unsupported source {spec.source!r} for {series_id}")
            return PointInTimeResult((), validation)
        if self._archive is None:
            validation.error(f"no archive dataset loaded for {series_id}")
            return PointInTimeResult((), validation)

        validation.extend(self._archive.validation)
        if not validation.ok:
            return PointInTimeResult((), validation)
        complete_through = self._archive.coverage_for(series_id)
        if complete_through is None:
            validation.error(f"{series_id} has no declared archive coverage")
            return PointInTimeResult((), validation)
        if as_of > complete_through:
            validation.error(
                f"{series_id} assembly {as_of} exceeds archive coverage through {complete_through}"
            )
            return PointInTimeResult((), validation)

        stages: frozenset[str] | None = None
        if spec.license == "umich_internal":
            stages = UMICH_STAGES if provisional else frozenset({"final"})
        archive_spans = self._archive.spans_for(series_id, stages)
        active = tuple(
            _to_value(span, as_of)
            for span in archive_spans
            if span.realtime_start <= as_of <= span.realtime_end
        )
        return PointInTimeResult(active, validation)
