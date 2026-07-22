"""Owner-approved exact baseline pin for the first real-data validation."""

from __future__ import annotations

from .models import BaselineContract

BASELINE_CONTRACT = BaselineContract(
    pin_status="approved",
    season_months=12,
    ar_lags=12,
    var_lags=1,
    forecast_months=6,
    minimum_months=36,
    signal_dwell_months=2,
    block_months=12,
    embargo_months=12,
    trial_count=10_000,
    random_seed=20_260_719,
    turning_window_months=6,
)

BASELINE_TARGET = "frozen_tier_a_monthly"
FORECAST_EVENT_MAPPING = (
    "two consecutive forecast months at or above the origin's frozen p70 threshold; "
    "score against the same next-two-calendar-quarter outcome"
)
OUTCOME_VINTAGE_POLICY = "latest_common_cached_vintage"
