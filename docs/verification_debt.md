# Verification Debt

This project-local register keeps incomplete verification visible without
adopting the still-gated playbook schemas. Entries remain open until their
discharge criteria are met and reviewed by a human.

## VD-001 — Two-independent-implementer reconstruction

- **Status:** Open
- **Opened:** 2026-07-21
- **Scope:** Composite Spec v1.2 §12 acceptance criterion for the frozen
  2013-present sequence and bands.
- **Evidence available:** `src/adls/checker/` independently reads the SQLite
  cache and normalized archive, selects point-in-time vintages, recomputes all
  transforms, population z-scores, composites, finalization dates,
  percentiles, and dwell state without importing maker, input, ALFRED,
  registry, contracts, or calendar implementations. Seeded ddof, percentile,
  dwell, PIT-boundary, and staleness defects each produce `Conflicting`.
- **Gap:** The maker and checker are separate code paths but were developed in
  the same repository during one implementation effort. This does not satisfy
  §12's requirement for two independent implementers. The live frozen store
  also remains intentionally empty pending the post-Slice-6 owner decision.
- **Consequence:** A checker `Verified` result establishes deterministic local
  source-to-sequence agreement under `adls.checker.v1`; it must not be described
  as satisfying the full §12 acceptance criterion or as authorizing external
  publication.
- **Discharge:** A second implementer, working from the approved spec and raw
  source artifacts rather than this implementation, reconstructs the full
  2013-present frozen-equivalent sequence and bands. Both outputs match exactly
  or every difference is adjudicated and regression-tested before the owner
  decides whether to seed the live frozen store.

## VD-002 — Historical UMich final-release reconstruction

- **Status:** Open
- **Opened:** 2026-07-21
- **Scope:** Composite Spec v1.2 §9 historical Tier-A reconstruction.
- **Evidence available:** Slice 6 accepts only normalized `final` rows and
  records `validation_assumption:umich_unrevised_final` in every affected source
  assembly. The official Table 2n historical workbook and provider-authored
  1991-2026 preliminary/final release calendar are preserved under ignored
  archive paths. The 425-row normalized history passed the archive contract;
  the real 155-month reconstruction is byte-deterministic and explicit
  assumption mode returned `Verified` with 310/310 checks. The ordinary checker
  still rejects it, as required.
- **Gap:** ADLS did not self-archive Table 2n on each historical release date,
  and no provider value-vintage archive exists. The provider calendar now
  substantiates exact release dates, but treating the current historical
  workbook's final values as unrevised remains an approved protocol assumption,
  not observed point-in-time value evidence.
- **Consequence:** The reconstruction can be verified relative to the stated
  assumption but cannot establish historical UMich provenance as observed.
- **Discharge:** Obtain provider-authoritative value-vintage/revision evidence
  or a second release-dated value archive; adjudicate differences before the
  historical-final assumption can be removed.

## VD-003 — Exact validation baseline pin

- **Status:** Closed 2026-07-21
- **Opened:** 2026-07-21
- **Scope:** Spec §14.1 and errata item 5.
- **Evidence available:** `docs/validation_harness.md` records the approved
  Slice 6 contract; the pure-stdlib AR/VAR fixture matches statsmodels 0.14.5
  to far below publication precision.
- **Resolution:** Before the first real-data run, the owner approved the exact
  AR/VAR lags, six-month mapping, regime window, latest-common outcome vintage,
  seed, trial count, block size, and embargo recorded in errata item 5. The
  accepted values were used unchanged for the completed first real-data run;
  VD-003 is omitted from its validation artifact.

## VD-004 — Limited episodes and finite permutation evidence

- **Status:** Open
- **Opened:** 2026-07-21
- **Scope:** Spec §9 power statement and §14 joint permutation.
- **Evidence available:** The real artifact logs all 10,000 requested and
  scored trials (zero abstentions), four candidate/evaluable episodes, the null
  median, descriptive p-value, and 15-percentage-point ROPE result. The primary
  recorded two hits; the ROPE passed, while the AR baseline floor failed.
- **Gap:** The historical window is expected to contain no more than four
  candidate episodes; permutation evidence cannot create independent episodes.
- **Consequence:** Results remain descriptive regardless of p-values. The term
  "leading" is not allowed by the artifact; a failed floor/ROPE marks the system
  as a coincident monitor.
- **Discharge:** Pre-registered out-of-sample episodes accrue and are evaluated
  without changing the frozen protocol; a human reviews the resulting power and
  calibration evidence.
