from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

import pytest

from adls.validation.baselines import ar_forecast, var_forecast

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "validation"
    / "baseline_statsmodels_v0_14_5.json"
)
FIXTURE_SHA256 = "7a30cf67b4e0ebf4415682c935c3c0229f785b80ed10901b5086048702051533"


def test_stdlib_baselines_match_pinned_statsmodels_forecasts() -> None:
    fixture_bytes = FIXTURE.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA256
    fixture = json.loads(fixture_bytes)
    rng = random.Random(fixture["random_seed"])
    length = fixture["fixture_length"]
    ar_history = tuple(
        math.sin(index / 5) + 0.03 * index + 0.2 * math.cos(index / 3) + rng.uniform(-0.05, 0.05)
        for index in range(length)
    )
    var_history = tuple(
        (
            math.sin(index / 4) + 0.01 * index + rng.uniform(-0.04, 0.04),
            math.cos(index / 6) - 0.005 * index + rng.uniform(-0.04, 0.04),
            math.sin(index / 9) + math.cos(index / 5) + rng.uniform(-0.04, 0.04),
        )
        for index in range(length)
    )

    ar_result = ar_forecast(
        ar_history,
        lag_count=fixture["ar_lags"],
        horizon=fixture["forecast_months"],
        minimum=36,
    )
    var_result = var_forecast(
        var_history,
        lag_count=fixture["var_lags"],
        horizon=fixture["forecast_months"],
        minimum=36,
    )

    assert ar_result.reason is None
    assert var_result.reason is None
    assert ar_result.values == pytest.approx(
        fixture["ar_expected"], abs=fixture["tolerance"], rel=0.0
    )
    for actual, expected in zip(var_result.vectors, fixture["var_expected"], strict=True):
        assert actual == pytest.approx(expected, abs=fixture["tolerance"], rel=0.0)
