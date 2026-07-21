# Indicator Basket Proposal — ADLS composite candidates

Status: **Basket v1 approved by owner 2026-07-19** (all four decision points,
with recommendations as written; see Decisions at the end). Labels remain
`research_only`. Method: maker draft
(candidate universe from economic reasoning) → two independent checker agents
verified every series against its publisher on 2026-07-19 (FRED/ALFRED, Fed
Board, BEA, Census, NY Fed, FINRA, UMich, ICI, Visa/BLS/BofA/JPMC pages).
Unverifiable fields are marked `validation_pending`. Nothing here is fitted to
market outcomes — see Selection discipline at the end.

## Stress dimensions (the composite's conceptual axes)

- **A. Discretionary spending pullback** (flow — the earliest behavioral signal)
- **B. Liquidity buffers** (stock — deposits, money funds, saving flow)
- **C. Credit strain** (revolving balances accelerating while spending falls; delinquency)
- **D. Leverage amplifiers** (margin debt)
- **E. Sentiment & credit access** (survey-leading psychology)
- **F. Affluent-sliced overlays** (the few genuinely income/wealth-cut sources)

## Approved core basket (vintage-validatable; 9 series)

Composite inputs must survive as-of validation. All have ALFRED vintages except
where noted.

| # | Series | ID / source | Dim | Freq (lag) | Vintages | Note |
|---|---|---|---|---|---|---|
| 1 | Visa SMI — Discretionary | `VISASMIDSA` (FRED) | A | M (~6 wk) | **2024-05-09→** (verified 2026-07-19) | Most on-target discretionary flow; data to 2014 but as-of history only ~2 yrs — composite spec must choose: two-tier composite (long-history 8-series + Visa-augmented from 2024) vs short validation window. License: Visa copyright, citation required (not public domain) |
| 2 | Advance retail: food services & drinking places | `RSFSDP` | A | M (~16 d) | 2013→ | Advance estimate, revised twice then benchmarked |
| 3 | Advance retail: furniture & home furnishings | `RSFHFS` | A | M (~16 d) | 2013→ | Housing-linked discretionary; RSEAS is the alternate |
| 4 | Personal saving rate | `PSAVERT` | B | M (~4 wk) | 1997→ | Heavily revised residual — the poster child for as-of validation |
| 5 | Deposits, all commercial banks (H.8) | `DPSACBW027SBOG` | B | **W (~9 d)** | 2012→ | Highest-frequency series in the basket; bank-side, all-holder |
| 6 | Retail money market funds | `WRMFNS` | B | W, batch-published monthly (~3 wk stale) | 2002→ | NSA; retail-only = household cash proxy; same liquidity family as #5 |
| 7 | Revolving consumer credit | `REVOLSL` | C | M (~5.5 wk) | 1996→ | Strain reads as growth accelerating while A-dim falls. Units break at 2025-02-07 vintage |
| 8 | Card delinquency, all banks | `DRCCLACBS` | C | Q (~7 wk) | 2011→ | Confirming/lagging by design; anchors severity |
| 9 | UMich sentiment, **top income tercile** | SCA Table 2n (data.sca.isr.umich.edu) | E/F | M (mid+final) | none — **self-archive from release day** | The one affluent-sliced monthly. Internal use only (UMich license; FRED mirror is 1-mo delayed) |

Deliberately excluded from core: `TDSP` (modeled composite, 2024 series
redesign truncated history to 2005; double-counts #4/#7 inputs) — context only.
Quarterly real PCE pair (`DRCARX1Q020SBEA`, `DFSARX1Q020SBEA`) — independently
detrended components of a synthetic validation cross-check, never summed as
chained-dollar levels; not composite inputs (no monthly on FRED; BEA monthly
Table 2.4.6U has no vintage archive). `BOGZ1FL193020005Q` household checkable deposits —
vintages only since 2019; revisit when depth accrues. `RSEAS` — same family as
#2/#3; adding it double-counts the retail cluster.

## AFFLUENT OVERLAY (report context; not composite inputs yet)

These are the genuinely income/wealth-sliced reads. None has a usable as-of
archive today, so they inform weekly reports and `needs_human_review`
escalations but stay out of the deterministic composite until our own archive
accrues history.

| Source | What | Freq | Access | Caveat |
|---|---|---|---|---|
| NY Fed **EGI** | 90+ delinquency by county **income quartile** (Q4 = affluent areas) | M schedule, quarterly data | free XLSX | Same CCP data as HHDC (one credit-file cluster); **2026Q1 VantageScore 4.0 break** |
| JPMC Institute Household Finances Pulse | Median cash balances by **income quartile** (4.7M households) | irregular (~2–4/yr) | free, chart-based | Most direct affluent-liquidity flow read; no raw download |
| BofA Institute Consumer Checkpoint | Card spend + deposits by **income cohort** | M | free PDF | Proprietary; could stop at will |
| Fed **DFA** | Liquid assets by **wealth percentile** | Q (~10–11 wk) | free CSV (federalreserve.gov) | `Conflicting` label **resolved 2026-07-19** by direct FRED check: the DFA release is live on FRED (net worth / assets / shares by percentile through Q1 2026, updated Jun 18) but a ~36-series subset is discontinued (~2022) — including the checkable-deposits-by-percentile detail. Use FRED for headline percentile series; **federalreserve.gov CSV for liquid-asset detail**. SCF re-benchmark revisions |
| NY Fed SCE Credit Access | Rejection/discouraged rates, income splits | every 4 mo | free | Slow; exact income cutoffs `validation_pending` |
| FINRA margin statistics | Margin debt + free credit balances | M (~3rd wk) | free XLSX, **no feed** | Affluent-skewed proxy; pre-2010 NYSE/FINRA splice |
| BLS CE income-quintile spending | Discretionary category weights, top quintile | annual (long lag) | free XLSX | Structure/weights only, never timing |

Alt-data (archive-only candidates, no vintage source): OpenTable weekly seated
diners (free page), TSA daily throughput (free), STR RevPAR (topline free,
detail paid), Mastercard SpendingPulse (topline free). Rejected outright:
monthly jewelry retail (`MRTSSM44831USS` dead since Feb 2021), Amex (no public
tracker).

## Input-availability taxonomy (spec §14.5, applied 2026-07-19)

Per TFT vocabulary (known-future / observed-with-lag / static): **all nine
core inputs are `observed-with-lag`** — each becomes known only at its
publication release, with the lags documented in the core table above. The
basket currently contains no known-future inputs (calendar/seasonal features
would be the only candidates, and none are members) and no static inputs.
Consequence: at any assembly date the ragged edge is governed entirely by the
release calendar — no input may be treated as available for a reference period
before its release date.

## Independence clusters (for composite weighting)

Per the concurrency-discount doctrine (library map problem 3), members of one
cluster must not count as independent confirmation:

1. **BEA cluster**: PSAVERT ↔ PCE categories ↔ (TDSP denominator)
2. **Liquidity-stock cluster**: H.8 deposits ↔ retail MMF ↔ Z.1 checkable ↔ DFA liquid assets
3. **Retail/PCE flow family**: RSFSDP ↔ RSFHFS ↔ RSEAS ↔ PCE food services (source-data identity)
4. **Credit-file cluster**: HHDC ↔ EGI (same Equifax panel)
5. **Bank-internal genre**: BofA ↔ JPMC ↔ Visa SMI (different networks, same genre)
6. **Survey cluster**: UMich ↔ SCE (different samples — weak coupling)

Core basket spans clusters 1, 2, 3, 5, 6 + standalone delinquency — at most
two members per cluster, weighted as families.

## Vintage-pipeline hazards (verified)

- `REVOLSL`: billions→millions units change at the 2025-02-07 vintage
- `TDSP`: 2024 release redesign; history truncated to 2005Q1; FOR discontinued
- PCE chained-dollar base changes across vintages (2005$→2009$→2012$→2017$) —
  work in within-component growth/trend gaps and never add component levels
- NY Fed credit data: Equifax Risk Score 3.0 → **VantageScore 4.0 at 2026Q1**
- ICI weekly MMF page holds **only the last 20 weeks** — self-archiving must start immediately
- FRED API: key required; vintages via `realtime_start`/`realtime_end`; rate limit unpublished (handle 429 with backoff)

## Approved archive routine

Start a dated self-archive **now** for the no-vintage sources (ICI weekly XLS,
UMich Table 2n, EGI XLSX, JPMC/BofA releases, FINRA XLSX): a manual weekly
download into `data_archive/` (git-ignored) with retrieval timestamps, until a
read-only adapter is authorized. Every week not archived is a week these
sources can never be as-of validated.

## Selection discipline (binding)

This basket is **hypothesis-driven, chosen a priori** on economic reasoning —
not selected by fitting to market outcomes. Composite weights and thresholds
will be specified before any outcome data is examined. Any later data-driven
refinement goes through purged/embargoed CV with multiple-comparison controls
(permutation p-values; trial count logged) per `docs/reference_library_adls.md`
problems 2–3. The optimizer's-curse rule applies: candidates that "look best"
in-sample get shrunk or held-out-revalidated before promotion, and every
rejected candidate stays documented here (no silent drops).

## Decisions (owner-approved 2026-07-19)

1. **9-series core approved** as proposed (RSFHFS retained; RSEAS stays the
   documented alternate). Open sub-item: verify VISASMIDSA ALFRED vintage depth
   before the composite is locked.
2. **Overlay approved** as report-context-only until self-archived as-of
   history accrues.
3. **Weekly self-archive authorized** (manual). The first ICI log used an
   obsolete 2025-named URL; correct 2026 provenance was captured 2026-07-21
   without overwriting the original evidence. FINRA/UMich/EGI/JPMC/BofA remain
   documented manual steps — see `data_archive/README.md`.
4. **DFA conflict resolved** by direct FRED check (see overlay table): release
   live, liquid-asset percentile detail discontinued on FRED ~2022 → use
   federalreserve.gov CSV for that detail.
