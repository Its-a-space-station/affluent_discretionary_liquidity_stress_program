# STATE.md — ADLS (Affluent Discretionary Liquidity Stress Program)

*Last updated: 2026-07-19.*

## Phase

**Phase 2 — Implementation (authorized 2026-07-20 via approved plan).** The
bootstrap scope guard is lifted for exactly this scope: read-only FRED/ALFRED
adapter with durable vintage cache, deterministic composite engine (spec
§1–§7), §9/§14 validation harness, weekly report generator — built in seven
verified slices. Still gated: schedulers/launchd, any execution path,
forecasting models, schema adoption, external publication.

## Current MVP scope

- In scope (definition work only): select the candidate indicator basket
  (affluent discretionary liquidity stress components), document each series'
  provenance / release lag / revision behavior, and specify one deterministic
  composite stress measure with thresholds — on historical **vintage (as-of)**
  data, producing a research-only report.
- Explicitly deferred: provider adapters, any scheduled loop, forecasting
  models, cross-system signal feeds, anything execution-capable.

## Approved decisions

- 2026-07-19 — Purpose confirmed by owner: macro/market **leading-indicator
  research system** for affluent-household discretionary liquidity stress;
  research-only advisory layer for the wider research family.
- 2026-07-19 — Bootstrap scaffold adopted from playbook templates; governing
  policy docs copied locally (safety, label, verification, maker_checker, report).
- 2026-07-19 — Owner approved the CLAUDE.md §10 operating fields: providers
  (read-only public macro/credit series incl. FRED/ALFRED vintages, retail &
  luxury sales releases, deposit-flow data — adapters still gated), deterministic
  composite criteria, weekly report cadence.
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
  (first pull executed; ICI secured), DFA conflict resolved (FRED live for
  percentile headline series; liquid-asset detail via federalreserve.gov CSV).

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
| (none) | — | — | Not authorized in Bootstrap |

## Blockers

- Canonical schema enums (`object_type`, `project`) do not include
  `macro_indicator` / `adls` — playbook-side extension needs owner approval
  before schema adoption can be checked off.

## Last checkpoint

- 2026-07-20 — Phase 2 Slice 1 complete: ALFRED adapter + span-based vintage
  cache built and live-verified (17/17 tests, ruff, mypy; three series
  backfilled; 2013 vintage depth resolved — full history to 1992, no fallback
  needed). Timeout-retry bug found by live fire and fixed with regression
  tests. Next: Slice 2 (uniform input layer).
- 2026-07-19 — Documentation-only bootstrap committed and pushed with owner
  approval: 3 commits (inherited governance / operating scaffold / library map),
  explicit paths only.

## Next recommended action

- Execute Phase 2 Slice 1 (skeleton, config, ALFRED client, vintage cache)
  per the approved plan (~/.claude/plans/imperative-gathering-hummingbird.md,
  mirrored in tasks/todo.md). Visa SMI methodology resolved during planning
  (0–200 diffusion index centered at 100 → §3.2 transform locked); the 2013
  vintage-depth question is Slice 1's live-smoke exit criterion. Spec
  convention pins live in canonical/spec_errata.md (approved with the plan).
