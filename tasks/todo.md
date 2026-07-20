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
- [ ] Specify the deterministic composite stress measure (weights, thresholds,
      bands) — deterministic, reproducible, vintage-data-only.
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
