"""Series registry — Basket v1 encoded as data (docs/indicator_basket_proposal.md).

Every input is availability-class `observed_with_lag` (spec section 14.5,
applied 2026-07-19): nothing is known before its release date. Staleness
thresholds are release-date anchored per spec section 7 and the errata
(canonical/spec_errata.md item 3: WRMFNS = 45 days).
"""

from __future__ import annotations

from dataclasses import dataclass

AVAILABILITY = "observed_with_lag"  # uniform for Basket v1; see spec section 14.5


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    name: str
    # family: census_retail | visa_smi | household_liquidity |
    #         umich_top_tercile | strain | outcome
    family: str
    role: str  # leading | overlay | outcome
    source: str  # alfred | archive
    frequency: str  # m | w | q
    staleness_days: int
    tier: str | None  # "A" | "B" | None (overlay/outcome are tierless)
    transform: str  # tag consumed by engine.transforms
    license: str  # public | visa_citation | umich_internal


REGISTRY: tuple[SeriesSpec, ...] = (
    # Leading family: census_retail (pooled before signing; spec 3.1)
    SeriesSpec("RSFSDP", "Advance retail: food services & drinking places",
               "census_retail", "leading", "alfred", "m", 40, "A", "pooled_yoy_growth", "public"),
    SeriesSpec("RSFHFS", "Advance retail: furniture & home furnishings",
               "census_retail", "leading", "alfred", "m", 40, "A", "pooled_yoy_growth", "public"),
    # Leading family: visa_smi (spec 3.2 — diffusion index, neutral 100; confirmed 2026-07-20)
    SeriesSpec("VISASMIDSA", "Visa SMI: discretionary (SA)",
               "visa_smi", "leading", "alfred", "m", 40, "B",
               "hundred_minus_level", "visa_citation"),
    # Leading family: household_liquidity (pooled before signing; spec 3.3)
    SeriesSpec("DPSACBW027SBOG", "Deposits, all commercial banks (H.8)",
               "household_liquidity", "leading", "alfred", "w", 21, "A",
               "pooled_yoy_growth", "public"),
    SeriesSpec("WRMFNS", "Retail money market funds (H.6, NSA)",
               "household_liquidity", "leading", "alfred", "w", 45, "A",
               "pooled_yoy_growth", "public"),
    # Leading family: umich_top_tercile (spec 3.4; manual archive; internal-use license)
    SeriesSpec("UMICH_SCA_T2N_TOP", "UMich ICS, top income tercile (Table 2n)",
               "umich_top_tercile", "leading", "archive", "m", 40, "A",
               "inverted_level", "umich_internal"),
    # Confirming strain overlay (spec 3.5 — NEVER aggregated into the leading composite)
    SeriesSpec("REVOLSL", "Revolving consumer credit (G.19)",
               "strain", "overlay", "alfred", "m", 40, None, "yoy_growth", "public"),
    SeriesSpec("DRCCLACBS", "Card delinquency rate, all banks",
               "strain", "overlay", "alfred", "q", 110, None, "level", "public"),
    # Validation outcome series (spec 9 — ground truth, not composite inputs)
    SeriesSpec("DRCARX1Q020SBEA", "Real PCE: recreation services (Q)",
               "outcome", "outcome", "alfred", "q", 0, None, "outcome_component", "public"),
    SeriesSpec("DFSARX1Q020SBEA", "Real PCE: food services & accommodations (Q)",
               "outcome", "outcome", "alfred", "q", 0, None, "outcome_component", "public"),
)

LEADING_FAMILIES: tuple[str, ...] = (
    "census_retail", "visa_smi", "household_liquidity", "umich_top_tercile"
)


def by_id(series_id: str) -> SeriesSpec:
    for spec in REGISTRY:
        if spec.series_id == series_id:
            return spec
    raise KeyError(f"unknown series_id: {series_id}")


def alfred_series() -> tuple[SeriesSpec, ...]:
    return tuple(s for s in REGISTRY if s.source == "alfred")
