from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from adls.contracts import PointInTimeResult, ValidationResult
from adls.engine.core import assemble
from adls.engine.serialize import serialize_assembly
from fixtures.engine.gen_slice3_fixture import load_fixture_inputs


def _replace_release(
    inputs: dict[str, PointInTimeResult],
    series_id: str,
    release_date: str,
) -> dict[str, PointInTimeResult]:
    changed = dict(inputs)
    result = inputs[series_id]
    changed[series_id] = PointInTimeResult(
        tuple(
            replace(value, release_date=release_date, available_from=release_date)
            for value in result.values
        ),
        result.validation,
    )
    return changed


def test_synthetic_april_2020_signs_and_structural_exclusions() -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=False)
    inputs["PSAVERT"] = PointInTimeResult((), ValidationResult())

    result = assemble(assembly_date, inputs)
    families = {family.family: family for family in result.family_scores}

    assert result.validation.ok
    assert families["census_retail"].z_score is not None
    assert families["census_retail"].z_score > 0
    assert families["household_liquidity"].z_score is not None
    assert families["household_liquidity"].z_score > 0
    assert families["umich_top_tercile"].z_score is not None
    assert families["umich_top_tercile"].z_score > 0
    assert families["strain"].z_score is not None
    assert families["strain"].z_score < 0
    assert families["visa_smi"].abstained
    assert result.headline_tier == "A"
    assert result.headline_value is not None and result.headline_value > 0
    members = {
        series_id for family in result.family_scores for series_id in family.member_series_ids
    }
    assert "PSAVERT" not in members
    assert "ignored non-engine input 'PSAVERT'" in result.validation.warnings


def test_required_member_staleness_drops_family_and_renormalizes_once() -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    assembly = date.fromisoformat(assembly_date)
    stale_retail = (assembly - timedelta(days=41)).isoformat()
    one_family_out = _replace_release(inputs, "RSFHFS", stale_retail)

    result = assemble(assembly_date, one_family_out)
    families = {family.family: family for family in result.family_scores}
    available = [
        family.z_score
        for family in result.family_scores
        if family.role == "leading" and not family.abstained
    ]

    assert families["census_retail"].abstained
    assert "stale_member:RSFHFS" in families["census_retail"].flags
    assert len(available) == 3
    assert result.headline_value == pytest.approx(sum(available) / 3)
    assert result.headline_tier == "B"
    assert "leading_renormalized:census_retail" in result.flags


def test_two_leading_family_abstentions_force_composite_abstention() -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    assembly = date.fromisoformat(assembly_date)
    inputs = _replace_release(inputs, "RSFHFS", (assembly - timedelta(days=41)).isoformat())
    inputs = _replace_release(
        inputs,
        "DPSACBW027SBOG",
        (assembly - timedelta(days=22)).isoformat(),
    )

    result = assemble(assembly_date, inputs)

    assert result.composite_abstained
    assert result.headline_value is None
    assert result.tier_a_value is None
    assert result.tier_b_value is None
    assert "leading_abstained:2_of_4_families" in result.flags


def test_missing_required_pool_member_never_degrades_to_single_series() -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    del inputs["RSFHFS"]

    result = assemble(assembly_date, inputs)
    retail = next(family for family in result.family_scores if family.family == "census_retail")

    assert retail.abstained
    assert retail.z_score is None
    assert "missing_member:RSFHFS" in retail.flags


def test_empty_invalid_loader_result_propagates_coverage_error() -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    invalid = ValidationResult()
    invalid.error("RSFSDP assembly exceeds complete coverage")
    inputs["RSFSDP"] = PointInTimeResult((), invalid)

    result = assemble(assembly_date, inputs)
    retail = next(family for family in result.family_scores if family.family == "census_retail")

    assert not result.validation.ok
    assert "RSFSDP assembly exceeds complete coverage" in result.validation.errors
    assert "invalid_member:RSFSDP" in retail.flags


def test_canonical_rejects_preliminary_umich_but_provisional_is_marked() -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    umich = inputs["UMICH_SCA_T2N_TOP"]
    inputs["UMICH_SCA_T2N_TOP"] = PointInTimeResult(
        tuple(replace(value, release_stage="preliminary") for value in umich.values),
        umich.validation,
    )

    canonical = assemble(assembly_date, inputs)
    provisional = assemble(assembly_date, inputs, provisional=True)
    canonical_umich = next(
        family for family in canonical.family_scores if family.family == "umich_top_tercile"
    )

    assert not canonical.validation.ok
    assert canonical_umich.abstained
    assert any("invalid for canonical assembly" in error for error in canonical.validation.errors)
    assert provisional.validation.ok
    assert not next(
        family for family in provisional.family_scores if family.family == "umich_top_tercile"
    ).abstained
    assert b'"assembly_mode":"provisional"' in serialize_assembly(provisional)


def test_archive_effective_availability_is_rechecked_at_engine_boundary() -> None:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    umich = inputs["UMICH_SCA_T2N_TOP"]
    inputs["UMICH_SCA_T2N_TOP"] = PointInTimeResult(
        tuple(
            replace(
                value,
                release_date="2020-05-28",
                available_from="2020-05-28",
            )
            for value in umich.values
        ),
        umich.validation,
    )

    result = assemble(assembly_date, inputs)

    assert not result.validation.ok
    assert any(
        "does not match effective availability" in error for error in result.validation.errors
    )
