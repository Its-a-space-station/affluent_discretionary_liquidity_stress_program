"""Checker-owned transcription of the approved Basket v1 constants."""

from __future__ import annotations

from .models import SeriesRule

SERIES_RULES: tuple[SeriesRule, ...] = (
    SeriesRule(
        "RSFSDP",
        "census_retail",
        "leading",
        "alfred",
        "m",
        40,
        "A",
        "pooled_yoy_growth",
        "public",
    ),
    SeriesRule(
        "RSFHFS",
        "census_retail",
        "leading",
        "alfred",
        "m",
        40,
        "A",
        "pooled_yoy_growth",
        "public",
    ),
    SeriesRule(
        "VISASMIDSA",
        "visa_smi",
        "leading",
        "alfred",
        "m",
        40,
        "B",
        "hundred_minus_level",
        "visa_citation",
    ),
    SeriesRule(
        "DPSACBW027SBOG",
        "household_liquidity",
        "leading",
        "alfred",
        "w",
        21,
        "A",
        "pooled_yoy_growth",
        "public",
    ),
    SeriesRule(
        "WRMFNS",
        "household_liquidity",
        "leading",
        "alfred",
        "w",
        45,
        "A",
        "pooled_yoy_growth",
        "public",
        canonical_date_shift_days=2,
    ),
    SeriesRule(
        "UMICH_SCA_T2N_TOP",
        "umich_top_tercile",
        "leading",
        "archive",
        "m",
        40,
        "A",
        "inverted_level",
        "umich_internal",
    ),
    SeriesRule(
        "REVOLSL",
        "strain",
        "overlay",
        "alfred",
        "m",
        40,
        None,
        "yoy_growth",
        "public",
    ),
    SeriesRule(
        "DRCCLACBS",
        "strain",
        "overlay",
        "alfred",
        "q",
        110,
        None,
        "level",
        "public",
    ),
)

FAMILY_SEQUENCE: tuple[str, ...] = (
    "census_retail",
    "visa_smi",
    "household_liquidity",
    "umich_top_tercile",
    "strain",
)
LEADING_FAMILIES: tuple[str, ...] = FAMILY_SEQUENCE[:-1]
TIER_A_FAMILIES: tuple[str, ...] = (
    "census_retail",
    "household_liquidity",
    "umich_top_tercile",
)

LICENSE_NOTICES: dict[str, str] = {
    "public": "Fed/Census inputs: public domain; cite by series ID",
    "visa_citation": "Visa SMI: cite Visa via FRED",
    "umich_internal": "UMich Table 2n: internal use only",
}


def rules_for_family(family: str) -> tuple[SeriesRule, ...]:
    return tuple(rule for rule in SERIES_RULES if rule.family == family)
