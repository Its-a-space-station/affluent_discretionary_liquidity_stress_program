# Spec Errata — owner-approved convention pins

Approved 2026-07-20 with the Phase 2 plan. These pin conventions the spec
(v1.2) leaves open; without them "byte-identical sequences" is undefined.
Each entry is binding on both the engine (maker) and the checker.

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
4. **Weekly→monthly aggregation**: arithmetic mean of Wednesday-stamped
   observations belonging to a complete month (confirms spec §1 "averaged";
   month completeness per §2's last-Wednesday rule).
5. **Baseline exact specs** (to be filled IN THIS FILE before the first
   real-data validation run, per §14.1 — placeholders intentionally not
   pre-filled with numbers chosen after seeing data):
   - seasonal-naive: m = 12, scored via MASE — PENDING final forecast→
     lead-event mapping
   - AR: fixed order, PENDING
   - VAR: small fixed order over the three long-history family series, PENDING
6. **2013 retail vintage depth — RESOLVED 2026-07-20 (live smoke, cached
   spans):** RSFSDP and RSFHFS earliest vintage is 2013-05-13, each carrying
   256 monthly observations back to 1992-01-01 — comfortably exceeding the
   120 months required by the 10-year z-window. The §4 fallback is not
   needed. VISASMIDSA first vintage confirmed 2024-05-09 with 124
   observations back to 2014-01-01 (z-window adequate; as-of run short per
   spec §6 two-tier design).
