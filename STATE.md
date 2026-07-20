# STATE.md — ADLS (Affluent Discretionary Liquidity Stress Program)

*Last updated: 2026-07-19.*

## Phase

**Bootstrap (documentation-only).** Repo scaffolded from the Decision Systems
Playbook templates; purpose confirmed by owner; no code, providers, or loops
exist or are authorized yet.

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
- Indicator basket not yet selected — owner input needed on candidate series.

## Last checkpoint

- 2026-07-19 — Documentation-only bootstrap committed and pushed with owner
  approval: 3 commits (inherited governance / operating scaffold / library map),
  explicit paths only.

## Next recommended action

- Indicator basket selection: owner picks the candidate affluent-discretionary
  liquidity-stress series; each gets provenance / release-lag / revision-behavior
  documentation before entering the composite. (Requires owner input on the
  candidate list; see docs/reference_library_adls.md problems 2–3 for the
  validation and selection discipline.)
