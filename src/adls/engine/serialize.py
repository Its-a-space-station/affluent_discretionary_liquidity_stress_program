"""Canonical publication-boundary bytes for a Slice 3 assembly."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_EVEN, Decimal
from typing import TypeAlias

from adls.engine.models import AssemblyResult, FamilyScore
from adls.registry import by_id

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
SIX_PLACES = Decimal("0.000001")


def _render_number(value: float) -> str:
    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite():
        raise ValueError("canonical JSON cannot contain non-finite numbers")
    rounded = decimal_value.quantize(SIX_PLACES, rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, "f")


def canonicalize_float(value: float) -> float:
    """Return the six-place, half-even value represented at publication boundaries."""
    return float(_render_number(value))


def _render(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _render_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(_render(item) for item in value) + "]"
    return (
        "{"
        + ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{_render(value[key])}" for key in sorted(value)
        )
        + "}"
    )


def canonical_json_bytes(payload: dict[str, JsonValue]) -> bytes:
    """Sorted-key, compact UTF-8 JSON with six-place half-even float rendering."""
    return (_render(payload) + "\n").encode("utf-8")


def _family_payload(score: FamilyScore) -> dict[str, JsonValue]:
    transformed_value_redacted = any(
        by_id(series_id).license == "umich_internal" for series_id in score.member_series_ids
    )
    return {
        "abstained": score.abstained,
        "component_z_scores": dict(score.component_z_scores),
        "family": score.family,
        "flags": list(score.flags),
        "member_release_dates": dict(score.member_release_dates),
        "member_series_ids": list(score.member_series_ids),
        "observation_date": score.observation_date,
        "role": score.role,
        "tier": score.tier,
        "transformed_value": None if transformed_value_redacted else score.transformed_value,
        "transformed_value_redacted": transformed_value_redacted,
        "z_score": score.z_score,
    }


def serialize_assembly(result: AssemblyResult) -> bytes:
    """Serialize the deterministic hashed payload; wall-clock metadata stays outside it."""
    payload: dict[str, JsonValue] = {
        "assembly_date": result.assembly_date,
        "assembly_mode": "provisional" if result.provisional else "canonical",
        "composite": {
            "abstained": result.composite_abstained,
            "flags": list(result.flags),
            "headline_tier": result.headline_tier,
            "headline_value": result.headline_value,
            "tier_a_value": result.tier_a_value,
            "tier_b_value": result.tier_b_value,
        },
        "families": [_family_payload(score) for score in result.family_scores],
        "schema_version": "adls.engine.assembly.v1",
    }
    return canonical_json_bytes(payload)
