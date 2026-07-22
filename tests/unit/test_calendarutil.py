from __future__ import annotations

from datetime import date

import pytest

from adls.calendarutil import (
    assembly_for_week,
    canonical_month_for_assembly,
    is_assembly_date,
    monthly_finalization_date,
)


def test_friday_market_holiday_moves_assembly_to_next_business_day() -> None:
    assert assembly_for_week(date(2025, 4, 18)) == date(2025, 4, 21)
    assert assembly_for_week(date(2026, 6, 19)) == date(2026, 6, 22)
    assert assembly_for_week(date(2027, 12, 24)) == date(2027, 12, 27)


def test_open_friday_remains_the_assembly_date() -> None:
    assert assembly_for_week(date(2025, 4, 11)) == date(2025, 4, 11)
    assert is_assembly_date(date(2025, 4, 11))
    assert is_assembly_date(date(2025, 4, 21))
    assert not is_assembly_date(date(2025, 4, 22))


def test_monthly_finalization_handles_weekend_and_holiday_edges() -> None:
    # 2025-03-15 is Saturday, so January finalizes at the next Friday assembly.
    assert monthly_finalization_date("2025-01") == date(2025, 3, 21)
    # The first Friday after 2025-04-15 is Good Friday, shifted to Monday.
    assert monthly_finalization_date("2025-02") == date(2025, 4, 21)
    # A normal Friday threshold finalizes on the threshold itself.
    assert monthly_finalization_date("2024-01") == date(2024, 3, 15)


def test_only_monthly_finalization_assembly_has_a_canonical_month() -> None:
    assert canonical_month_for_assembly(date(2025, 4, 21)) == "2025-02"
    assert canonical_month_for_assembly(date(2025, 4, 25)) is None


def test_calendar_rejects_non_fridays_and_dates_outside_static_coverage() -> None:
    with pytest.raises(ValueError, match="Friday"):
        assembly_for_week(date(2025, 4, 17))
    with pytest.raises(ValueError, match="2013 through 2027"):
        assembly_for_week(date(2028, 1, 7))
    with pytest.raises(ValueError, match="YYYY-MM"):
        monthly_finalization_date("2025-2")
