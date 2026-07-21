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
      `data_archive/README.md`). First pull done: ICI secured; FINRA/UMich/
      EGI/JPMC/BofA are manual steps for the first full weekly pass.
- [x] Specify the deterministic composite stress measure — **v1.1 APPROVED
      2026-07-19** (`docs/composite_spec_v1.md`; all six decision points as
      written; checker-reviewed and rebuilt before approval).
- [ ] Resolve `validation_pending`: Visa SMI methodology note (confirm
      momentum-around-100 construction → level-vs-100 transform).
- [ ] Resolve `validation_pending`: confirm 2013-era RSFSDP/RSFHFS vintages
      carry full back-history for 10-year z-windows (ALFRED, read-only).
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
- [ ] Slice 2 — uniform input layer (archive CSV contract + PIT loader).
- [ ] Slice 3 — engine core (§3-§5, §7): named-episode sign tests, units-break
      fixture, byte-identity golden.
- [ ] Slice 4 — calendar, canonicalization, frozen store, bands (§2, §6).
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

- [!] Read-only provider adapters (FRED/ALFRED vintages, sales releases) —
      respect terms & rate limits; requires owner approval.
- [!] Cross-system advisory feed to the research family — human-cited reports
      only until explicitly approved.
