# Todo — ADLS

> Conventions: `[ ]` open · `[~]` in progress · `[x]` done · `[!]` blocked /
> needs decision. Nothing here authorizes leaving the current phase.

## Bootstrap docs

- [x] Copy & adapt `CLAUDE.md`, `STATE.md`, `tasks/todo.md`, `tasks/lessons.md`
      from the playbook templates. (2026-07-19)
- [x] Copy governing policies locally: safety, label, verification,
      maker_checker, report. (2026-07-19)
- [x] Owner confirms PROPOSED fields in `CLAUDE.md` §10 (providers, criteria
      summary, report cadence). (Approved 2026-07-19.)
- [x] Documentation-only first commit (explicit paths; owner approved 2026-07-19;
      3 commits: governance / scaffold / library map, pushed to origin main).

## Schema adoption

- [!] Extend playbook schema enums (`object_type` += `macro_indicator`,
      `project` += `adls`) — playbook-side change, needs owner approval.
- [ ] Adopt canonical `schemas/` (evidence_record, belief_card, decision_card,
      manual_review, postmortem, verification_debt) once enums are extended.

## Indicator definition (MVP)

- [x] Owner selects candidate indicator basket — **Basket v1 approved
      2026-07-19** (`docs/indicator_basket_proposal.md`: 9-series core +
      report-only affluent overlay; maker draft + two independent checker
      agents; DFA conflict resolved by direct FRED check).
- [x] Verify `VISASMIDSA` ALFRED vintage depth — vintages since 2024-05-09
      (verified on ALFRED 2026-07-19); Visa copyright, citation required.
      Consequence for composite spec: choose two-tier composite (long-history
      8-series + Visa-augmented from 2024-05) vs single short-window design.
- [~] Weekly as-of self-archive (owner-approved 2026-07-19; manual — see
      `data_archive/README.md`). Original ICI log used an obsolete 2025-named
      URL; correct 2026 provenance captured 2026-07-21 without overwriting the
      evidence. FINRA/UMich/EGI/JPMC/BofA remain manual first-pass steps.
- [x] Specify the deterministic composite stress measure — **v1.1 APPROVED
      2026-07-19** (`docs/composite_spec_v1.md`; all six decision points as
      written; checker-reviewed and rebuilt before approval).
- [x] Resolve Visa SMI methodology: 0-200 diffusion index centered at 100;
      level-vs-100 transform locked. (2026-07-20)
- [x] Confirm 2013-era RSFSDP/RSFHFS vintages carry full back-history for
      10-year z-windows: both reach 1992. (2026-07-20)
- [x] Phase 2 (implementation) authorization — **granted 2026-07-20** via
      approved plan (scope-guard lift for adapter/engine/validation/report;
      schedulers, execution paths, forecasting, schemas, publication stay gated).

## Phase 2 slices (approved plan; each slice: fail-before/pass-after, ask before commit)

- [x] Slice 1 — skeleton, config, ALFRED client, SQLite vintage cache.
      Complete 2026-07-20: 17/17 tests + ruff + mypy green; live smoke
      backfilled RSFSDP/RSFHFS/VISASMIDSA (166/166/27 vintages); vintage-depth
      question RESOLVED (2013 vintages carry history to 1992 — errata item 6);
      live fire caught + fixed a real bug (network timeouts bypassed the retry
      loop; now retried with backoff, regression-tested).
- [x] Slice 1 repair — preserve/correct ICI evidence; pin WRMFNS calendar,
      required-member staleness, archive availability/stages, and non-additive
      validation outcome; enforce coherent ALFRED cutoff, truthful endpoint
      audit telemetry, and non-regressing cache coverage. (2026-07-21)
- [x] Slice 2 — uniform input layer (archive CSV contract + PIT loader).
      Complete 2026-07-21: data defects collect without raising; UTC/date,
      stages, canonical sort, duplicates/conflicts, gaps, safe provenance paths,
      late retrieval, bounded coverage, prelim/final, final-only canonical
      UMich, and both provider coverage boundaries are regression-tested.
      Provider-neutral outputs cap episode visibility at assembly D so eventual
      revision dates cannot leak backward. 36/36 tests + ruff + mypy green.
- [x] Slice 3 — engine core (§3-§5, §7). Complete 2026-07-21: one PIT snapshot
      feeds pooled/sign-correct transforms, complete weekly months, trailing
      population z-scores, release-anchored staleness, required-member dropout,
      Tier A/B renormalization, and separate Strain. Canonical/provisional
      archive modes are explicit; internal UMich levels are redacted. The
      REVOLSL cache-vintage boundary, named April 2020 signs, all staleness
      thresholds, run-twice bytes, fixture generator, and pinned SHA are tested.
      Independent review findings repaired; 57/57 tests + ruff + mypy green.
- [x] Slice 4 — calendar, canonicalization, frozen store, bands (§2, §6).
      Complete 2026-07-21: bounded NYSE Friday/holiday assemblies, calendar-
      inferred canonical/provisional mode, M+2/15 finalization, a locked
      append-only frozen JSONL store with embedded canonical source/hash replay,
      expanding Tier-A percentiles, 36-month burn-in, and two-month dwell.
      Revision rewrites, concurrent duplicate appends, future vintages and
      observations, malformed persisted dates, licensed-level leakage, and
      threshold-rounding contradictions are regression-tested. Independent
      review findings repaired; 79/79 tests + ruff + format + mypy green.
- [ ] Slice 5 — independent checker (maker≠checker in code; seeded-defect tests).
- [ ] Slice 6 — validation harness (§9+§14); then owner decision: seed frozen
      store from checker-Verified reconstruction?
- [ ] Slice 7 — weekly report + launch-condition audit.
- [x] Visa SMI methodology confirmed (0-200 diffusion index, neutral 100) —
      §3.2 (100 − level) transform locked. (Resolved in planning, 2026-07-20.)
- [x] Spec §14 v1.2 delta **approved 2026-07-19** (baseline floor, per-regime
      reporting, cross-series embargo, score-every-point, input-availability
      taxonomy — taxonomy applied to basket doc same day).
- [ ] Optional (playbook-side, owner call): enrich the playbook's
      `before_universal_forecaster_use` checklist with gate conditions C1–C6
      from the TS review (contamination datasheet, vintage-vs-revised eval,
      post-cutoff skill, coverage calibration, monthly-context adequacy,
      determinism bounds).
- [ ] Housekeeping (owner call): move the misfiled AIRS-Bench paper from
      "Papers on Time Series Forecasting" to "Papers on Coding".
- [ ] Maker/checker split defined: composite computation (maker) vs independent
      recomputation + range/sanity checks (checker).
- [ ] Canonical labels only in belief cards; indicator levels stay data fields.

## Reports

- [ ] Weekly research report from the playbook `weekly_report` template
      (research-only warning + safety footer).
- [ ] `needs_human_review` escalation path for regime-break signals via the
      `manual_review` template.

## Calibration & validation (after MVP definition)

- [ ] Historical validation protocol on vintage data (no revised-series
      lookahead); document leading-lagging relationship claims as hypotheses
      with explicit invalidation conditions.
- [ ] Postmortems for resolved stress-episode theses; track verification debt.

## Future integrations (gated — not authorized by this list)

- [!] Additional read-only provider adapters beyond the authorized ALFRED/local
      archive scope — respect terms and rate limits; require owner approval.
- [!] Cross-system advisory feed to the research family — human-cited reports
      only until explicitly approved.
