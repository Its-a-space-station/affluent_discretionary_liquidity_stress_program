# STATE.md — ADLS (Affluent Discretionary Liquidity Stress Program)

*Last updated: 2026-07-22.* **New session? Read `HANDOFF.md` first** - the
full narrative of how this repo completed all seven Phase 2 slices and entered
Phase 3A.

## Phase

**Phase 3A - Verification and operational hardening (authorized 2026-07-22).**
The seven Phase 2 implementation slices are complete. Phase 3A is limited to a
blind VD-001 clean-room handoff and exact comparison harness, plus hardening of
the existing manual archive/report workflow. Still gated: schedulers/launchd,
new provider adapters, any execution path, forecasting models, schema adoption,
cross-system feeds, and external publication.

## Current MVP scope

- In scope: the approved read-only FRED/ALFRED adapter and durable vintage
  cache; a uniform local-archive/PIT input layer; the deterministic composite
  engine in spec §1-§7; the §9/§14 validation harness; and a local weekly
  research-report generator. Phase 3A adds coordinator-only clean-room packet,
  submission-seal, and post-submission comparison tooling for VD-001, plus
  manual operational hardening.
- Explicitly deferred: any scheduled loop, new provider, forecasting model,
  schema adoption, external publication, cross-system signal feed, or anything
  execution-capable unless separately approved.

## Approved decisions

- 2026-07-19 — Purpose confirmed by owner: macro/market **leading-indicator
  research system** for affluent-household discretionary liquidity stress;
  research-only advisory layer for the wider research family.
- 2026-07-21 — Owner approved the repair bundle: preserve and correct ICI
  archive provenance; pin WRMFNS weekday mapping, pooled-family staleness,
  archive release-stage/effective-availability rules, and a non-additive-safe
  validation outcome; then harden ALFRED cache coverage and fetch auditing.
- 2026-07-21 — Before the first real-data validation run, owner approved the
  exact errata item 5 baseline contract: seasonal m=12, AR(12), VAR(1),
  36-month minimum, six-month recursive horizon, two-month p70 signal mapping,
  latest-common outcome vintage, NBER ±6-month context, and 10,000 seeded joint
  block trials with strict >12-month embargo.
- 2026-07-19 — Bootstrap scaffold adopted from playbook templates; governing
  policy docs copied locally (safety, label, verification, maker_checker, report).
- 2026-07-22 — Owner selected a cold start for the live canonical sequence.
  `canonical/frozen_sequence.jsonl` remains intentionally empty; the Slice 6
  frozen-equivalent reconstruction remains validation evidence under
  `outputs/` and is not promoted into live history.
- 2026-07-22 - Owner authorized narrow Phase 3A verification and operational
  hardening. The first priority is a blind, spec-only VD-001 clean-room packet
  and exact post-submission comparison harness. Preparing the packet does not
  constitute the second implementation and cannot itself close VD-001.
- 2026-07-19 — Owner approved the CLAUDE.md §10 operating fields: providers
  (read-only public macro/credit series incl. FRED/ALFRED vintages, retail &
  luxury sales releases, deposit-flow data), deterministic composite criteria,
  and weekly report cadence. Phase 2 later authorized the scoped implementation.
- 2026-07-19 — Owner approved **Spec v1.2 delta** (§14): validation baseline
  floor (seasonal-naive/AR/VAR), per-regime macro-averaged reporting,
  cross-series permutation embargo, score-every-point, and the TFT
  input-availability taxonomy (applied to the basket doc — all nine inputs
  classified `observed-with-lag`). Source: TS-papers review
  (docs/reference_library_timeseries.md).
- 2026-07-19 — Owner approved **Composite Spec v1.1** (all six §13 decision
  points as written): PSAVERT excluded / Strain confirming-only, equal weights
  across four independence families, frozen as-published canonical history,
  Tier-A-only bands with burn-in and dwell rules, pre-registered single-claim
  validation with binding power statement, nominal inputs with real-PCE
  cross-check. Spec was independently checker-reviewed and rebuilt before
  approval (disposition in spec §12).
- 2026-07-19 — Owner approved **Indicator Basket v1** (all four decision points
  of `docs/indicator_basket_proposal.md`): 9-series vintage-validatable core,
  affluent overlay as report-context-only, weekly manual self-archive routine
  (first pull executed; ICI provenance repaired 2026-07-21), DFA conflict
  resolved (FRED live for percentile headline series; liquid-asset detail via
  federalreserve.gov CSV).

## Safety rules (in force)

- Research-only; no autonomous financial actions (this system does not
  buy/sell/trade/order or move funds).
- Human approval required before any outward-facing or irreversible step.
- No secrets or credentials in the repo.
- Canonical labels only (see `docs/label_policy.md`).

## Non-goals

- Security-level directional research calls (screener projects own
  security-level work; ADLS stays at the macro/segment level).
- Automated signal feeds into other systems (reports may be cited by humans;
  no machine-to-machine triggers without explicit approval).
- Nowcasting/forecasting models in the MVP (deterministic composite first).

## Active loops

Loops produce findings and reports only — never actions.

| Loop | Cadence | Bounds / stop conditions | Status |
| --- | --- | --- | --- |
| (none) | — | — | Scheduling remains gated in Phase 3A |

## Blockers

- Canonical schema enums (`object_type`, `project`) do not include
  `macro_indicator` / `adls` — playbook-side extension needs owner approval
  before schema adoption can be checked off.
- VD-001 requires a genuinely independent implementer. The local packet and
  comparator cannot satisfy that independence criterion by themselves.

## Last checkpoint

- 2026-07-22 - Phase 3A clean-room coordinator slice complete. The stdlib-only
  `cleanroom/` package and three manual CLI commands prepare a reference-free
  packet, seal a canonical candidate before disclosure, and compare it against
  one snapshotted checker-Verified reference. The neutral contract covers all
  three Tier-A family states, five input vintages, Tier-A value, the historical
  UMich assumption, and complete band/dwell state for 2013-05 through 2026-03.
  Tampered packets/submissions, extra files, relaxed permissions, path leakage,
  noncanonical JSONL, malformed decimals, impossible timestamp ordering, and
  unverified references fail closed. Difference reports contain paths but no
  differing values, and no result changes debt automatically. The real ignored
  32 MB packet verifies across 155 months at manifest SHA-256
  `ed8ebc3ca3c7da9474708b64ac85a78d7fa65e872479f9e9f1a53ec48a4f531b`;
  no independent candidate exists yet, so VD-001 remains open. Verification:
  163 tests, ruff, touched-file format check, and mypy across 47 source files.
- 2026-07-22 - Phase 2 Slices 6 and 7 were owner-reviewed, committed, and
  pushed to `origin/main` as `0d95cec`. The owner selected a cold live-store
  start, and the live JSONL remains zero bytes. `adls report` now snapshots all
  local evidence, builds a calendar-derived canonical or provisional assembly,
  obtains an independent checker result, and emits deterministic redacted
  assembly JSON, canonical report JSON, and Markdown. Every finding has an
  approved result label, confidence label, evidence IDs, and source timestamp;
  UMich levels stay redacted and Visa is cited as `Visa via FRED`. The first
  local report used the 2026-07-17 canonical assembly: the current assembly was
  checker-`Verified`, three leading families were available, UMich correctly
  abstained due to post-assembly retrieval, and the live band remained
  `Unverified` under the cold start. Internal weekly reporting is ready with
  those caveats; external publication is not. Live smoke also exposed and
  repaired a cache watermark bug: completeness now advances through one
  explicit fetch-date cutoff even when a series did not change that day. All
  nine ALFRED series are complete through 2026-07-22; SQLite integrity is `ok`
  with zero overlaps. Verification: 149 tests, ruff, touched-file format check,
  and mypy across 43 source files.
- 2026-07-21 — Phase 2 Slice 6 complete. The official internal-use UMich Table
  2n historical workbook and the provider's 1991-2026 final-release calendar
  were archived locally, then normalized into 425 final rows (1991-01 through
  2026-05) under ignored paths. The approved real run reconstructed 155 frozen
  months from 2013-05 through 2026-03 twice with identical bytes. Explicit
  historical-final checker mode returned `Verified` with 310/310 checks; the
  ordinary checker correctly returned `Conflicting`. All 155 records carry the
  assumption flag, none expose licensed transformed levels, and none abstain.
  The descriptive primary result found four evaluable episodes and two hits
  (50%); it beat seasonal-naive (25%) and VAR(1) (38.4615%) but not AR(12)
  (60%), so the pre-registered failure clause sets `coincident_monitor`.
  Calibration is non-monotonic; the 10,000-trial joint null met the 15-point
  ROPE, but all conclusions remain descriptive. Frozen/artifact SHA-256 values
  are `9737d722...e49265` and `a6939894...79af`. Open debt remains VD-001,
  VD-002, VD-004. The owner later selected a cold live-store start.
- 2026-07-21 — Phase 2 Slice 5 complete: `src/adls/checker/` independently
  reads one consistent SQLite snapshot plus normalized archive evidence,
  selects active point-in-time episodes, and recomputes the full source
  assembly and frozen band sequence from checker-owned constants, calendar,
  transforms, population z-scores, composite arithmetic, percentiles, and
  dwell. Posture tests prevent imports from maker/input/ALFRED/registry/
  contracts/calendar code, network/environment access, and static or dynamic
  import escapes. Exact nested schemas, source bytes/hash, six-place numeric
  types, source-to-outer consistency, archive stages/effective dates, and
  future episodes are checked without uncaught malformed-evidence failures.
  All five planned defect seeds return `Conflicting`; noncanonical rules cannot
  return `Verified`. Adversarial review drove repairs for false-Verified nested
  fields and integer encodings, mixed SQLite snapshots, archive parsing/UTC,
  malformed evidence, future-episode coverage, and posture bypasses. The honest
  §12 two-independent-implementer gap is open as verification debt VD-001.
  Verification: 109/109 tests, ruff, touched-file format check, and mypy.
- 2026-07-21 — Phase 2 Slice 4 complete: a static 2013-2027 NYSE calendar
  enforces Friday/next-business-day assemblies and derives canonical versus
  provisional mode; canonical month M finalizes only at the first assembly on
  or after the 15th of M+2. The live `canonical/frozen_sequence.jsonl` remains
  intentionally empty pending the post-Slice-6 seeding decision. Its writer is
  append-only under thread and process locks, embeds the redacted canonical
  source assembly plus SHA-256, and revalidates source, vintages, observations,
  licenses, composite arithmetic, chronology, and band replay on every read.
  Tier-A bands use expanding prior frozen values, six-place thresholds, a
  36-month/35-reference burn-in, and two-month dwell. Independent review found
  and drove repairs for concurrent duplicate appends, persisted lookahead,
  source/value corruption, threshold replay, caller-controlled mode, future
  observations, and malformed dates; its final pass found no remaining issues.
  The April 2020 canonical fixture now uses 2020-06-19 and is pinned at SHA-256
  `d568528a50258674a29a8b943680dfe71c76dad3462896ed8e88b93326a78dc8`.
  Verification: 79/79 tests, ruff, touched-file format check, and mypy.
- 2026-07-21 — Phase 2 Slice 3 complete: the pure-stdlib maker engine computes
  one PIT assembly with pooled/sign-correct transforms, complete weekly-month
  aggregation, trailing population z-scores excluding the current observation,
  release-anchored staleness, required-member dropout, Tier A/B renormalization,
  and a separate Strain overlay. Canonical/provisional UMich modes are explicit;
  late-retrieval availability is rechecked; licensed transformed levels are
  redacted at serialization. Canonical JSON is six-place half-even, run-twice
  byte-identical; Slice 4 later moved the fixture to its proper monthly
  finalization date and re-pinned its SHA above.
  Independent review found and drove repairs for preliminary-stage leakage and
  incomplete weekly grids. Verification: 57/57 tests, ruff, and mypy.
- 2026-07-21 — Phase 2 Slice 2 complete: normalized archive CSVs are validated
  without raising on data defects; release stages, late retrieval, canonical
  sorting, duplicate/conflict detection, gap warnings, bounded per-series
  coverage, and final-only canonical UMich are enforced. A provider-neutral PIT
  loader now covers ALFRED and archives and hides future episode close dates.
  Verification: 36/36 tests, ruff, mypy, SQLite integrity, zero cache overlaps.
- 2026-07-21 — Slice 1 repair complete: current-year ICI provenance captured
  without overwriting prior evidence; deterministic spec gaps pinned; ALFRED
  observation fetches capped to the vintage-date snapshot; endpoint audit rows
  now carry actual status/rate-limit telemetry; cache PIT reads enforce declared
  non-regressing coverage. Verification: 24/24 tests, ruff, mypy, SQLite
  integrity, and zero overlapping spans. Next: Slice 2 against the repaired
  archive contract.
- 2026-07-20 — Phase 2 Slice 1 complete: ALFRED adapter + span-based vintage
  cache built and live-verified (17/17 tests, ruff, mypy; three series
  backfilled; 2013 vintage depth resolved — full history to 1992, no fallback
  needed). Timeout-retry bug found by live fire and fixed with regression
  tests.
- 2026-07-19 — Documentation-only bootstrap committed and pushed with owner
  approval: 3 commits (inherited governance / operating scaffold / library map),
  explicit paths only.

## Next recommended action

- Keep the reference and implementation repository hidden while an authorized,
  genuinely independent implementer works only from the frozen clean-room
  packet. Seal the returned candidate before running the comparison; VD-001
  remains open until owner review even after an exact technical match.
- Run the first operational weekly cycle on Friday 2026-07-24: capture the
  manual no-vintage sources,
  refresh ALFRED, advance normalized archive coverage with provenance-bearing
  evidence, and generate the local report using the 2026-07-17 report as its
  previous artifact. Prioritize ICI plus the outstanding FINRA, EGI, JPMC, and
  BofA first-pass captures.
- Preserve the cold-start boundary and keep scheduling, new providers,
  forecasting, schema adoption, cross-system feeds, and external publication
  gated.
