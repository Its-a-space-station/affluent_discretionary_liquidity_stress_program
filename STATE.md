# STATE.md — ADLS (Affluent Discretionary Liquidity Stress Program)

*Last updated: 2026-07-21.* **New session? Read `HANDOFF.md` first** — the
full narrative of how this repo got here and the Slice 5 starting point.

## Phase

**Phase 2 — Implementation (authorized 2026-07-20 via approved plan).** The
bootstrap scope guard is lifted for exactly this scope: read-only FRED/ALFRED
adapter with durable vintage cache, deterministic composite engine (spec
§1–§7), §9/§14 validation harness, weekly report generator — built in seven
verified slices. Still gated: schedulers/launchd, any execution path,
forecasting models, schema adoption, external publication.

## Current MVP scope

- In scope: the approved read-only FRED/ALFRED adapter and durable vintage
  cache; a uniform local-archive/PIT input layer; the deterministic composite
  engine in spec §1-§7; the §9/§14 validation harness; and a local weekly
  research-report generator.
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
- 2026-07-19 — Bootstrap scaffold adopted from playbook templates; governing
  policy docs copied locally (safety, label, verification, maker_checker, report).
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
| (none) | — | — | Scheduling remains gated in Phase 2 |

## Blockers

- Canonical schema enums (`object_type`, `project`) do not include
  `macro_indicator` / `adls` — playbook-side extension needs owner approval
  before schema adoption can be checked off.

## Last checkpoint

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

- Execute Phase 2 Slice 5: build the independent checker with its own SQL,
  vintage selection, arithmetic, constants, percentile, and dwell paths;
  posture-enforce that it imports nothing from maker/input/ALFRED modules, then
  prove seeded ddof, percentile, dwell, PIT-boundary, and staleness defects are
  all reported as Conflicting.
