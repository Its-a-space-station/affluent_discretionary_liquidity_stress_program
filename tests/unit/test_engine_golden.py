"""Pinned Slice 3 bytes; see tests/fixtures/engine/README.md before regeneration."""

from __future__ import annotations

import hashlib
import json

from adls.engine.core import assemble
from adls.engine.serialize import canonical_json_bytes, serialize_assembly
from fixtures.engine.gen_slice3_fixture import (
    FIXTURE_PATH,
    fixture_bytes,
    load_fixture_inputs,
)

PINNED_ASSEMBLY_SHA256 = "d568528a50258674a29a8b943680dfe71c76dad3462896ed8e88b93326a78dc8"


def _golden_bytes() -> bytes:
    assembly_date, inputs = load_fixture_inputs(include_visa=True)
    return serialize_assembly(assemble(assembly_date, inputs))


def test_fixture_matches_generator() -> None:
    assert FIXTURE_PATH.read_bytes() == fixture_bytes()


def test_canonical_json_uses_sorted_keys_half_even_six_places_and_lf() -> None:
    payload = {"b": 1.2345675, "a": 1.2345665, "negative_zero": -0.0}

    assert canonical_json_bytes(payload) == (
        b'{"a":1.234566,"b":1.234568,"negative_zero":0.000000}\n'
    )


def test_assembly_is_byte_identical_across_runs() -> None:
    assert _golden_bytes() == _golden_bytes()


def test_internal_umich_level_is_redacted_from_payload() -> None:
    payload = json.loads(_golden_bytes())
    families = {family["family"]: family for family in payload["families"]}

    assert families["umich_top_tercile"]["transformed_value"] is None
    assert families["umich_top_tercile"]["transformed_value_redacted"] is True
    assert families["census_retail"]["transformed_value"] is not None
    assert families["census_retail"]["transformed_value_redacted"] is False


def test_assembly_bytes_match_pinned_sha() -> None:
    blob = _golden_bytes()

    assert blob.endswith(b"\n")
    payload = json.loads(blob)
    assert payload["schema_version"] == "adls.engine.assembly.v1"
    assert payload["assembly_mode"] == "canonical"
    assert hashlib.sha256(blob).hexdigest() == PINNED_ASSEMBLY_SHA256
