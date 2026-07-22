"""Checker-owned bounded NYSE calendar and monthly finalization calculation."""

from __future__ import annotations

from datetime import date, timedelta

CALENDAR_START_YEAR = 2013
CALENDAR_END_YEAR = 2027

_HOLIDAY_TEXT = """
2013-01-01 2013-01-21 2013-02-18 2013-03-29 2013-05-27 2013-07-04
2013-09-02 2013-11-28 2013-12-25
2014-01-01 2014-01-20 2014-02-17 2014-04-18 2014-05-26 2014-07-04
2014-09-01 2014-11-27 2014-12-25
2015-01-01 2015-01-19 2015-02-16 2015-04-03 2015-05-25 2015-07-03
2015-09-07 2015-11-26 2015-12-25
2016-01-01 2016-01-18 2016-02-15 2016-03-25 2016-05-30 2016-07-04
2016-09-05 2016-11-24 2016-12-26
2017-01-02 2017-01-16 2017-02-20 2017-04-14 2017-05-29 2017-07-04
2017-09-04 2017-11-23 2017-12-25
2018-01-01 2018-01-15 2018-02-19 2018-03-30 2018-05-28 2018-07-04
2018-09-03 2018-11-22 2018-12-05 2018-12-25
2019-01-01 2019-01-21 2019-02-18 2019-04-19 2019-05-27 2019-07-04
2019-09-02 2019-11-28 2019-12-25
2020-01-01 2020-01-20 2020-02-17 2020-04-10 2020-05-25 2020-07-03
2020-09-07 2020-11-26 2020-12-25
2021-01-01 2021-01-18 2021-02-15 2021-04-02 2021-05-31 2021-07-05
2021-09-06 2021-11-25 2021-12-24
2022-01-17 2022-02-21 2022-04-15 2022-05-30 2022-06-20 2022-07-04
2022-09-05 2022-11-24 2022-12-26
2023-01-02 2023-01-16 2023-02-20 2023-04-07 2023-05-29 2023-06-19
2023-07-04 2023-09-04 2023-11-23 2023-12-25
2024-01-01 2024-01-15 2024-02-19 2024-03-29 2024-05-27 2024-06-19
2024-07-04 2024-09-02 2024-11-28 2024-12-25
2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26
2025-06-19 2025-07-04 2025-09-01 2025-11-27 2025-12-25
2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 2026-06-19
2026-07-03 2026-09-07 2026-11-26 2026-12-25
2027-01-01 2027-01-18 2027-02-15 2027-03-26 2027-05-31 2027-06-18
2027-07-05 2027-09-06 2027-11-25 2027-12-24
"""
NYSE_HOLIDAYS = frozenset(date.fromisoformat(value) for value in _HOLIDAY_TEXT.split())


def _require_supported(day: date) -> None:
    if not CALENDAR_START_YEAR <= day.year <= CALENDAR_END_YEAR:
        raise ValueError(
            f"checker NYSE calendar supports {CALENDAR_START_YEAR} through {CALENDAR_END_YEAR}"
        )


def _assembly_for_friday(friday: date) -> date:
    _require_supported(friday)
    if friday.weekday() != 4:
        raise ValueError("assembly anchor must be Friday")
    candidate = friday
    while candidate.weekday() >= 5 or candidate in NYSE_HOLIDAYS:
        candidate += timedelta(days=1)
    return candidate


def _parse_month(month: str) -> tuple[int, int]:
    if len(month) != 7 or month[4] != "-":
        raise ValueError(f"canonical month must use YYYY-MM, got {month!r}")
    try:
        parsed = date(int(month[:4]), int(month[5:]), 1)
    except ValueError as exc:
        raise ValueError(f"canonical month must use YYYY-MM, got {month!r}") from exc
    if parsed.strftime("%Y-%m") != month:
        raise ValueError(f"canonical month must use YYYY-MM, got {month!r}")
    return parsed.year, parsed.month


def monthly_finalization_date(month: str) -> date:
    year, month_number = _parse_month(month)
    shifted = year * 12 + month_number - 1 + 2
    due_year, due_month_zero = divmod(shifted, 12)
    threshold = date(due_year, due_month_zero + 1, 15)
    _require_supported(threshold)
    friday = threshold - timedelta(days=(threshold.weekday() - 4) % 7)
    for week in range(2):
        candidate = _assembly_for_friday(friday + timedelta(days=7 * week))
        if candidate >= threshold:
            return candidate
    raise RuntimeError("checker monthly finalization search failed")


def next_month(month: str) -> str:
    year, month_number = _parse_month(month)
    if month_number == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month_number + 1:02d}"
