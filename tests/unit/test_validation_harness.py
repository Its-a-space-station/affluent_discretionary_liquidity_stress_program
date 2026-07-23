from __future__ import annotations

import json
import math
from dataclasses import replace

from adls.validation.harness import build_validation_artifact
from adls.validation.models import FrozenPoint, OutcomeGap
from adls.validation.spec import BASELINE_CONTRACT


def _points() -> tuple[FrozenPoint, ...]:
    result: list[FrozenPoint] = []
    for index in range(72):
        month_index = 2015 * 12 + index
        year, zero_based_month = divmod(month_index, 12)
        first = math.sin(index / 4.0)
        second = math.cos(index / 6.0)
        third = math.sin(index / 9.0) + index * 0.01
        result.append(
            FrozenPoint(
                month=f"{year:04d}-{zero_based_month + 1:02d}",
                tier_a_value=(first + second + third) / 3.0,
                published_band="Watch" if 40 <= index <= 43 else "Normal",
                family_values=(
                    ("census_retail", first),
                    ("household_liquidity", second),
                    ("umich_top_tercile", third),
                ),
                composite_abstained=False,
                flags=(),
                p70_threshold=0.2 if index >= 35 else None,
            )
        )
    return tuple(result)


def _outcomes() -> tuple[OutcomeGap, ...]:
    result: list[OutcomeGap] = []
    for year in range(2015, 2024):
        for quarter in range(1, 5):
            key = f"{year:04d}-Q{quarter}"
            event = key in {"2018-Q3", "2018-Q4", "2020-Q2"}
            gap = -3.0 if event else 0.0
            result.append(OutcomeGap(key, gap, gap, gap, event, None))
    return tuple(result)


def test_validation_harness_is_fail_closed_for_an_unapproved_contract() -> None:
    unapproved = replace(BASELINE_CONTRACT, pin_status="proposed")
    result = build_validation_artifact(
        _points(),
        _outcomes(),
        unapproved,
        frozen_sha256="a" * 64,
        outcome_vintage="2026-07-16",
        checker_label="Verified",
        checker_criteria_version="adls.checker.validation-assumption.v1",
        checker_check_count=2,
    )

    assert not result.validation.ok
    assert result.artifact_bytes == b""
    assert any("owner approval" in error for error in result.validation.errors)


def test_approved_fixture_run_is_byte_identical_complete_and_descriptive() -> None:
    contract = replace(BASELINE_CONTRACT, trial_count=20)

    first = build_validation_artifact(
        _points(),
        _outcomes(),
        contract,
        frozen_sha256="b" * 64,
        outcome_vintage="2026-07-16",
        checker_label="Verified",
        checker_criteria_version="adls.checker.validation-assumption.v1",
        checker_check_count=144,
    )
    second = build_validation_artifact(
        _points(),
        _outcomes(),
        contract,
        frozen_sha256="b" * 64,
        outcome_vintage="2026-07-16",
        checker_label="Verified",
        checker_criteria_version="adls.checker.validation-assumption.v1",
        checker_check_count=144,
    )

    assert first.validation.ok, first.validation.errors
    assert first.artifact_bytes == second.artifact_bytes
    assert first.artifact_bytes.endswith(b"\n")
    payload = json.loads(first.artifact_bytes)
    assert payload["schema_version"] == "adls.validation.artifact.v1"
    assert payload["source"]["checker_label"] == "Verified"
    assert payload["framing"]["claim_status"] == "descriptive_only"
    assert payload["framing"]["leading_claim_allowed"] is False
    assert len(payload["score_rows"]["primary"]) == len(_points())
    assert all(
        len(payload["score_rows"][model]) == len(_points())
        for model in ("seasonal_naive", "ar", "var")
    )
    assert len(payload["baseline_origins"]) == len(_points()) * 3
    assert len(payload["permutation"]["trials"]) == 20
    assert payload["power"]["descriptive_regardless_of_p_values"] is True
    assert payload["power"]["candidate_episode_upper_bound_met"] is True
    assert payload["power"]["evaluable_candidate_episode_count"] == 1
    assert payload["verification_debt"] == ["VD-002", "VD-004"]
