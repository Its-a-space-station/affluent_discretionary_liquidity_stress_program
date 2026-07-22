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
