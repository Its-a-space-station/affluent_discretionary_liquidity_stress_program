# Spec Errata — owner-approved convention pins

Items 1-4 and 6 were approved 2026-07-20 with the Phase 2 plan. Item 5 was
finalized and owner-approved 2026-07-21 before the first real-data validation
run. Items 7-10 were approved as repair or implementation pins on 2026-07-21.
These close conventions the spec (v1.2) left open or stated incorrectly; each
entry is binding on both the engine (maker) and the checker.

1. **z-score window**: the trailing window EXCLUDES the current observation
   (consistent with §2's percentile convention); standard deviation is the
   population form (ddof = 0); minimum 36 monthly observations else the
   family abstains (spec §4 unchanged).
2. **Published-value serialization**: decimal arithmetic at the publication
   boundary, 6 decimal places, round-half-even. Canonical JSON: sorted keys,
   separators `(",", ":")`, LF line endings, UTF-8. Wall-clock timestamps and
   git hashes live only in unhashed manifest sidecars, never in hashed
   payloads.
3. **WRMFNS staleness threshold: 45 days** (not the generic 21-day weekly
   rule). Rationale: WRMFNS weekly data is published in monthly batches with
   the H.6; §7's own principle ("normal release gap + one full missed cycle")
   applied to its actual release cadence gives ~45 days. H.8 remains 21 days.
4. **Weekly→monthly aggregation and canonical weekday**: arithmetic mean of
   canonical-Wednesday observations belonging to a complete month. H.8
   (`DPSACBW027SBOG`) is natively Wednesday-stamped and receives no shift.
   `WRMFNS` is natively Monday-stamped and shifts **+2 calendar days** to its
   corresponding canonical Wednesday before month assignment. A month is
   complete only when the selected release covers its last canonical Wednesday.
5. **Baseline exact specs — APPROVED 2026-07-21 before first real-data run:**
   frozen Tier-A monthly target; seasonal naive m=12; AR(12); VAR(1) over the
   three Tier-A family z-score series; intercepts and expanding complete
   suffixes with minimum 36 months; six-month recursive horizon. A baseline
   signal requires two consecutive forecast months at or above the origin's
   frozen p70 threshold and is scored against the same event in either of the
   next two calendar quarters. Outcome uses the latest common cached vintage.
   Joint null uses 10,000 trials, seed 20260719, 12-month circular blocks, and a
   strict >12-month donor/target embargo. Turning context is ±6 months around
   the static NBER peak/trough table. These values are immutable for the first
   real-data run; later changes require a new pre-registered protocol version.
6. **2013 retail vintage depth — RESOLVED 2026-07-20 (live smoke, cached
   spans):** RSFSDP and RSFHFS earliest vintage is 2013-05-13, each carrying
   256 monthly observations back to 1992-01-01 — comfortably exceeding the
   120 months required by the 10-year z-window. The §4 fallback is not
   needed. VISASMIDSA first vintage confirmed 2024-05-09 with 124
   observations back to 2014-01-01 (z-window adequate; as-of run short per
   spec §6 two-tier design).
7. **Required-member staleness**: a pooled family is defined by all of its
   registered members. If any required member is missing or stale, the whole
   family abstains; it never degrades to a single-member substitute with changed
   economics or weight. The composite renormalizes only across complete
   families, and still abstains when at least two leading families are absent.
8. **Self-archive effective availability and stages**: normalized rows carry
   `release_stage` (`preliminary`, `final`, `revision`, or `not_applicable`) and
   `retrieved_at`. Effective availability is
   `max(release_date, UTC date(retrieved_at))`; late retrieval never creates
   synthetic hindsight. Episodes for one observation are non-overlapping, with
   each later episode closing the prior one on the previous day. The current
   episode is bounded by declared archive coverage. Canonical UMich uses finals
   only; preliminary rows are provisional-nowcast-only.
9. **Validation outcome (non-additive chained dollars)**: never add
   `DRCARX1Q020SBEA` and `DFSARX1Q020SBEA` levels. For each positive component
   independently, fit an OLS line to log levels over the eight completed
   quarters ending at `t-1`, extrapolate it to `t`, and compute
   `gap_c,t = 100 * (exp(log(x_c,t) - predicted_log_c,t) - 1)`. The synthetic
   outcome is the equal-weight mean of the two component gaps. Both components
   are required. The primary event is a synthetic gap at or below -2.0% in
   either of the next two quarters. This is a research outcome, not a BEA
   aggregate or contribution measure.
10. **Band reference, boundaries, and state**: Tier-A percentile thresholds use
    all prior numeric values in the expanding frozen canonical history; the
    current month is excluded. Linear-interpolation boundaries are Normal
    `<70`, Watch `>=70 and <85`, Elevated `>=85 and <=95`, and High `>95`.
    Banding requires at least 36 frozen canonical months and 35 prior numeric
    Tier-A values. The 36th month starts dwell, so the earliest confirmed band
    is month 37. Any raw-band change restarts the two-month dwell and direct
    band jumps are allowed. A month with no Tier-A value publishes no current
    band, clears pending dwell, and retains the prior confirmed state only for
    later state-machine continuity. Under item 2's publication rule,
    interpolated thresholds are rendered to six-place half-even precision
    before boundary classification so the persisted threshold and band replay
    without contradiction.
