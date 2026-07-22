"""Generate and expand the deterministic Slice 3 synthetic episode fixture."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from adls.contracts import PointInTimeResult, PointInTimeValue, ValidationResult

FIXTURE_PATH = Path(__file__).with_name("slice3_episode.json")

FIXTURE_CONFIG: dict[str, Any] = {
    "assembly_date": "2020-06-19",
    "monthly": {"count": 49, "start": "2016-04-01"},
    "quarterly": {"count": 21, "start": "2015-04-01"},
    "schema_version": "adls.slice3.fixture.v1",
    "series": {
        "DPSACBW027SBOG": {
            "base": "1000",
            "final": "650",
            "step": "8",
            "wiggle": "1.5",
        },
        "DRCCLACBS": {
            "base": "2.00",
            "final": "0.70",
            "step": "0.04",
            "wiggle": "0.05",
        },
        "REVOLSL": {
            "base": "400",
            "final": "250",
            "step": "2.5",
            "wiggle": "1.5",
        },
        "RSFSDP": {
            "base": "100",
            "final": "45",
            "step": "1.3",
            "wiggle": "0.4",
        },
        "RSFHFS": {
            "base": "80",
            "final": "30",
            "step": "0.9",
            "wiggle": "0.3",
        },
        "UMICH_SCA_T2N_TOP": {
            "base": "95",
            "final": "50",
            "step": "0.05",
            "wiggle": "1.2",
        },
        "VISASMIDSA": {
            "base": "101",
            "final": "80",
            "step": "0",
            "wiggle": "1.0",
        },
        "WRMFNS": {
            "base": "500",
            "final": "300",
            "step": "4",
            "wiggle": "0.8",
        },
    },
}


def fixture_bytes() -> bytes:
    return (json.dumps(FIXTURE_CONFIG, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _value(config: dict[str, str], index: int, count: int) -> Decimal:
    if index == count - 1:
        return Decimal(config["final"])
    wiggle = Decimal((index % 5) - 2) * Decimal(config["wiggle"])
    return Decimal(config["base"]) + Decimal(index) * Decimal(config["step"]) + wiggle


def _point(
    series_id: str,
    observation_date: date,
    value: Decimal,
    assembly_date: str,
) -> PointInTimeValue:
    archive = series_id == "UMICH_SCA_T2N_TOP"
    return PointInTimeValue(
        series_id=series_id,
        observation_date=observation_date.isoformat(),
        value_text=format(value.quantize(Decimal("0.001")), "f"),
        release_date=assembly_date,
        available_from=assembly_date,
        available_through=assembly_date,
        source="archive" if archive else "alfred",
        source_file="synthetic/umich_table_2n.xls" if archive else None,
        release_stage="final" if archive else None,
        retrieved_at=f"{assembly_date}T12:00:00Z" if archive else None,
    )


def _monthly_history(
    series_id: str,
    config: dict[str, str],
    start: date,
    count: int,
    assembly_date: str,
) -> tuple[PointInTimeValue, ...]:
    return tuple(
        _point(series_id, _add_months(start, index), _value(config, index, count), assembly_date)
        for index in range(count)
    )


def _quarterly_history(
    series_id: str,
    config: dict[str, str],
    start: date,
    count: int,
    assembly_date: str,
) -> tuple[PointInTimeValue, ...]:
    return tuple(
        _point(
            series_id,
            _add_months(start, index * 3),
            _value(config, index, count),
            assembly_date,
        )
        for index in range(count)
    )


def _weekly_history(
    series_id: str,
    config: dict[str, str],
    start: date,
    count: int,
    assembly_date: str,
) -> tuple[PointInTimeValue, ...]:
    values: list[PointInTimeValue] = []
    for index in range(count):
        month = _add_months(start, index)
        first_offset = (2 - month.weekday()) % 7
        canonical_wednesday = month + timedelta(days=first_offset)
        week_index = 0
        while canonical_wednesday.month == month.month:
            value = _value(config, index, count) + Decimal(week_index) * Decimal("0.1")
            observation_date = (
                canonical_wednesday - timedelta(days=2)
                if series_id == "WRMFNS"
                else canonical_wednesday
            )
            values.append(_point(series_id, observation_date, value, assembly_date))
            canonical_wednesday += timedelta(days=7)
            week_index += 1
    return tuple(values)


def load_fixture_inputs(
    path: Path = FIXTURE_PATH,
    *,
    include_visa: bool,
) -> tuple[str, dict[str, PointInTimeResult]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    assembly_date = str(config["assembly_date"])
    monthly = config["monthly"]
    quarterly = config["quarterly"]
    series = config["series"]
    monthly_start = date.fromisoformat(monthly["start"])
    quarterly_start = date.fromisoformat(quarterly["start"])

    histories: dict[str, tuple[PointInTimeValue, ...]] = {}
    for series_id in ("RSFSDP", "RSFHFS", "UMICH_SCA_T2N_TOP", "REVOLSL"):
        histories[series_id] = _monthly_history(
            series_id,
            series[series_id],
            monthly_start,
            int(monthly["count"]),
            assembly_date,
        )
    if include_visa:
        histories["VISASMIDSA"] = _monthly_history(
            "VISASMIDSA",
            series["VISASMIDSA"],
            monthly_start,
            int(monthly["count"]),
            assembly_date,
        )
    for series_id in ("DPSACBW027SBOG", "WRMFNS"):
        histories[series_id] = _weekly_history(
            series_id,
            series[series_id],
            monthly_start,
            int(monthly["count"]),
            assembly_date,
        )
    histories["DRCCLACBS"] = _quarterly_history(
        "DRCCLACBS",
        series["DRCCLACBS"],
        quarterly_start,
        int(quarterly["count"]),
        assembly_date,
    )
    return assembly_date, {
        series_id: PointInTimeResult(values, ValidationResult())
        for series_id, values in histories.items()
    }


if __name__ == "__main__":
    FIXTURE_PATH.write_bytes(fixture_bytes())
