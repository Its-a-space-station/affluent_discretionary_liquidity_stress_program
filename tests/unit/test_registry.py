from adls.registry import by_id


def test_weekly_series_map_to_canonical_wednesday() -> None:
    assert by_id("DPSACBW027SBOG").canonical_date_shift_days == 0
    assert by_id("WRMFNS").canonical_date_shift_days == 2
