# ADLS Composite Stress Measure — Specification v1.1 (PROPOSED)

Status: **APPROVED — Composite Spec v1.1, owner-approved 2026-07-19 (all six
§13 decision points, as written).** Lineage: v1 drafted a priori, attacked by
an independent checker the same day (4 blockers, 8 majors — disposition in
§12), rebuilt as v1.1, then approved. Labels remain `research_only`. Defines
the deterministic composite over approved Basket v1
(`docs/indicator_basket_proposal.md`). Documentation only; no code authorized.

## 0. System frame (Powell 5-element form)

- **State S_t**: frozen as-published composite history + latest vintage-stamped
  inputs + current band.
- **Decision x_t**: none by the system — reports and canonical labels only.
- **Exogenous W_t**: data releases and revisions between assembly dates.
- **Transition**: deterministic recomputation per §2.
- **Objective**: calibrated, early, auditable surfacing of affluent
  discretionary liquidity stress — validated on lead quality AND calibration
  (§9), never on any trading metric.

## 1. Architecture

- **Leading composite** (the headline): equal-weighted mean of FOUR
  independence-family z-scores — the families are the basket's independence
  units, not thematic clusters:
  1. **Census retail pool** — RSFSDP + RSFHFS pooled (shared survey instrument)
  2. **Visa SMI-Discretionary** (bank-network genre)
  3. **Household liquidity pool** — H.8 + WRMFNS pooled (§3.3)
  4. **UMich top-tercile sentiment** (survey genre)
- **Confirming overlay** (severity anchor, NOT in the leading composite and
  excluded from all lead claims): Strain = REVOLSL + DRCCLACBS, reported
  alongside with its own documented onset-inversion caveat (§3.5).
- **Removed from composite entirely**: PSAVERT — S = Y − C is an accounting
  identity, so consumption pullback mechanically raises saving; as a composite
  member it partially cancels the spending signal in exactly the target
  episodes (2020 arithmetic, §8). It appears in report narrative only.
- **Two tiers**: Tier A = families 1, 3, 4 (history to ~2013); Tier B adds
  Visa (2024-05→). Headline value = Tier B when computable; **bands, labels,
  and escalations run on Tier A only** until Tier B has ≥ 60 monthly
  observations (B4 fix); Tier B is additionally shown mapped onto Tier A's
  band thresholds in composite-value space, with the A/B divergence reported.

## 2. Assembly, canonicalization, determinism (normative)

- **Assembly dates**: every Friday (next business day if a market holiday).
  Weekly assemblies produce **provisional nowcasts** — labeled as such, never
  driving bands or labels.
- **Canonical monthly value**: month M is finalized once, at the first
  assembly on/after the **15th of M+2** (by which G.19, retail, Visa, and
  UMich final for M are normally released). The canonical sequence is the
  **frozen as-published history**: once finalized, M's value never changes.
  A separate "as-recomputed" research view may be published, clearly labeled;
  bands, labels, and validation use the frozen sequence exclusively.
- **Point-in-time rule (binding)**: an assembly at date D uses only vintages
  released ≤ D; growth rates are computed within a single vintage's history
  (never across vintages — REVOLSL units break, benchmark revisions).
- **Weekly-input month assignment**: H.8/WRMFNS weeks belong to the month
  containing their Wednesday stamp; a month is complete at the first release
  covering its last Wednesday. Partial months never enter the composite.
- **UMich prelim/final**: canonical values use finals only; prelims may inform
  the provisional nowcast; the self-archive captures both.
- **Percentile convention**: empirical percentiles with linear interpolation;
  the current value is excluded from its own reference set.
- **DRCCLACBS carry**: last released value carried forward until replaced or
  stale (§7); z-scored on a quarterly window (rolling 40 quarters, min 20).

## 3. Family definitions, transforms, signings

All signings below were walked through 2008, 2020, and 2022 (lesson of
2026-07-19); positive = stress.

**3.1 Census retail pool.** Pooled nominal growth:
(ΔRSFSDP₁₂ₘ + ΔRSFHFS₁₂ₘ) / (RSFSDP + RSFHFS)ₜ₋₁₂ — scale-free, weights
implicit. Sign: decelerating discretionary spend = stress. Nominal by choice
(a priori): deflation would add a CPI dependency; instead the inflation-regime
caveat is documented (§8) and the quarterly real-PCE pair is wired into
validation as the cross-check (§9).

**3.2 Visa SMI-Discretionary.** Transform: **(100 − level)**, z-scored — SMI
is already a momentum-style index around a neutral 100, so differencing it
again would be a double difference (checker M6). `validation_pending`: confirm
against Visa's methodology note before composite lock; if SMI turns out to be
a level index, switch to 12-month change with written rationale.

**3.3 Household liquidity pool.** Pooled growth:
(ΔH.8₁₂ₘ + ΔWRMFNS₁₂ₘ) / (H.8 + WRMFNS)ₜ₋₁₂ — scale-free (fixes dollar-change
scale drift), nets deposit↔MMF rotation before signing. Sign: negative pooled
growth = buffer drawdown = stress. Documented limitations: H.8 includes
business deposits (proxy, labeled); SA/NSA mix largely absorbed by YoY;
**pre-registered false-positive regimes**: QT-era aggregate drain (2022-2023)
and bank-run repositioning (2023-03, SVB week) read as stress without
household distress (§8).

**3.4 UMich top-tercile sentiment.** Level, inverted, z-scored. Documented
false-positive regime: 2022-23 "vibecession" (record-low sentiment, resilient
affluent spending). Small-subsample noise (~200 respondents) accepted and
disclosed. License: internal use only (§10).

**3.5 Confirming Strain overlay.** REVOLSL YoY growth z + DRCCLACBS level z,
equal-weighted. Documented behavior: **onset-inverted** (2008-09, 2020: credit
contracts and delinquency falls under forbearance — Strain reads anti-stress
at acute onsets) and **normalization-elevated** (2023-25 delinquency
mean-reversion reads stressed); neither series has an income cut. Role:
severity anchor once stress is realized; excluded from lead claims; a
**launch-condition audit** (what each family and the overlay read today, and
why) is required before first publication.

## 4. Standardization

Transformed monthly series → z against trailing rolling 10-year window (or
full available history if shorter; minimum 36 monthly observations, else the
family abstains with flag), capped at ±3.

## 5. Aggregation

Leading composite = mean of available family z's (equal weights across the
four independence families — the a priori choice; any thesis-weighting may
only be adopted through §9 with multiple-comparison controls). Variance note
(checker M1): under equal family weights the single-series families (Visa,
UMich) each contribute ~25% of weight and more of variance than pooled
families; this is disclosed and accepted in preference to intra-family
double-counting. Confirming overlay is reported separately, never averaged in.

## 6. Bands, labels, escalation

- Bands on the **frozen Tier A** sequence's trailing percentiles: Normal
  (<70th), Watch (70–85th), Elevated (85–95th), High (>95th). **Band burn-in**:
  no band is published until the frozen sequence has ≥ 36 canonical months;
  earlier history is shown unbanded in validation plots.
- **Dwell rules** (anti-flapping): band entry is confirmed after 2 consecutive
  canonical months in the new band; exit likewise. The former ≥1.5σ jump
  trigger is deleted (σ was undefined; band machinery covers it).
- Labels (canonical vocabulary only): confirmed Watch → `watchlist`;
  confirmed Elevated/High → `needs_human_review` via the manual-review
  template, which must cite the affluent-overlay context (EGI quartile-4
  delinquency, JPMC/BofA reads) alongside the composite. Clear rule: two
  consecutive canonical months below Watch → `watchlist` cleared.
- Every published value carries: input vintage timestamps, abstention flags,
  tier values + divergence, and license notices (§10).

## 7. Staleness (binary, release-date anchored)

Linear decay is deleted (unearned complexity — checker M7). An input
**abstains** (with a mandatory report flag) when the time since its latest
*release* exceeds normal gap + one full missed cycle: monthly inputs 40 days;
weekly pool components 21 days; DRCCLACBS 110 days. Family/composite handling:
a family with all members abstaining drops out and the leading composite
renormalizes over remaining families **with a prominent flag**; if ≥ 2 of the
four families abstain, the composite itself abstains for that assembly.

## 8. Known construction behavior (pre-registered before validation)

Stated now so validation cannot quietly "discover" them:

1. **April 2020 (v1 arithmetic, retained as design rationale)**: spending
   families read max stress; PSAVERT-as-member and Strain would have read
   strongly anti-stress, netting the composite to ~Normal — the reason
   PSAVERT is out and Strain is confirming-only. The v1.1 leading composite
   reads 2020Q2 as high stress (spending + sentiment + liquidity-pool
   direction), which validation should confirm on vintages.
2. **2021-22 nominal masking / disinflation false-stress**: nominal spending
   growth overstated real activity in 2021-22 and will mechanically decelerate
   under disinflation; the real-PCE cross-check exists for this.
3. **QT / SVB liquidity false-positives** (§3.3).
4. **Vibecession sentiment false-positive** (§3.4).
5. **Revision-event band moves**: annual Census benchmarks and NIPA summer
   revisions can legitimately jump current-edge YoY under PIT rules; reports
   must attribute band moves caused by revision events.

## 9. Validation protocol (pre-registered, executable)

- **Reconstruction**: frozen-equivalent Tier A from mid-2013 on true vintages
  (ALFRED) for the Census and liquidity pools. **UMich enters under a
  documented assumption** — SCA finals are treated as unrevised (historically
  true; logged as verification debt) with a reconstructed release calendar;
  there is no vintage archive (checker B2). Visa joins 2024-05→.
  `validation_pending` (m2): confirm the 2013-era retail vintages contain
  full back-history for the 10-year z-windows.
- **One primary claim** (the only confirmatory test): *a confirmed Watch-or-
  higher band on the frozen Tier A leading composite precedes declines of
  ≥ 2% below 8-quarter trend in combined real discretionary-services PCE
  (DRCARX1Q020SBEA + DFSARX1Q020SBEA), within 1-2 quarters.* Method: circular
  block permutation (block = 12 months), embargo = 12 months around tested
  episodes, ROPE = lead-rate improvement of ≥ 15 percentage points over the
  permuted distribution's median. Trial count logged in a verification-debt
  entry.
- **Power statement (binding honesty)**: the window contains ≤ 4 candidate
  episodes; results are **descriptive** regardless of p-values, and the label
  "leading" may only be claimed after out-of-sample episodes accrue. If the
  primary claim fails, the composite is re-labeled a **coincident monitor**
  and remains published (failure clause with a real trigger).
- **Exploratory (labeled as such, no confirmatory claims)**: NBER event-study
  descriptives; ex-Strain composite vs subsequent delinquency deterioration
  (the delinquency outcome is excluded from any composite containing Strain —
  circularity, checker M5).
- **Calibration test** (checker M8): monotonicity of P(primary outcome within
  2 quarters | band) across Normal→High plus a reliability-style table,
  reported with episode counts.

## 10. Licenses & publication constraints

- UMich Table 2n: **internal use only** — weekly reports quoting it are
  internal documents; any external publication requires stripping/aggregating
  UMich content and passes the CLAUDE.md §9 approval gate regardless.
- Visa SMI: copyrighted, citation required — cite "Visa via FRED" in every
  report table.
- All Fed/Census/BEA inputs: public domain, cited by series ID.

## 11. Non-goals / v1.1+ docket

No interaction terms (the basket's conditional strain definition — revolving
acceleration *while spending falls* — is the first v1.2 candidate), no CUSUM
regime flags, no forecasting heads, no thesis weights. Each addition must pass
`before_complexity_increase` reasoning and the §9 controls.

## 12. Checker disposition (v1 → v1.1)

Independent checker review 2026-07-19: **B1** signing failures (PSAVERT
removed; Strain re-scoped confirming; named-episode walkthroughs now
mandatory — see tasks/lessons.md) · **B2** unexecutable validation (UMich
assumption pre-registered; §6 binding-constraint claim corrected) · **B3**
determinism gaps (frozen history, canonicalization rule, conventions pinned
in §2; pool weights made scale-free) · **B4** Tier B band pathology (bands on
Tier A only, burn-in, dwell rules) · **M1-M8** adopted as specified (family
weighting with variance disclosure, pool formula, nominal-with-cross-check,
one primary claim + block permutation + power statement, Visa transform
corrected to level-vs-100 pending methodology confirmation, staleness
simplified to binary, calibration test added). Acceptance test for the final
spec: two independent implementers reconstructing 2013-2026 Tier A must get
identical frozen sequences and bands.

## 13. Owner decision points (all approved as written, 2026-07-19)

1. **PSAVERT out of the composite** (narrative only) and **Strain as
   confirming overlay** excluded from lead claims — the two big v1→v1.1
   structural changes.
2. Equal weights across the four independence families, with the disclosed
   ~25% single-series weights (alternative: down-weight single-series
   families — a priori choice, must be made now if at all).
3. Canonicalization: frozen as-published history; month M finalized at first
   assembly on/after the 15th of M+2; weekly assemblies as labeled nowcasts.
4. Bands on Tier A only (until Tier B ≥ 60 months), 36-month burn-in,
   2-month dwell/exit rules, jump-trigger deleted.
5. Validation as pre-registered in §9 — including the binding power statement
   (descriptive until out-of-sample episodes accrue) and the coincident-
   monitor failure clause.
6. Nominal spending with real-PCE cross-check (vs deflating inputs).
