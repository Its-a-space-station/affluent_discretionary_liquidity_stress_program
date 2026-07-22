# CLAUDE.md — ADLS (Affluent Discretionary Liquidity Stress Program)

This file guides Claude Code sessions in this repository. It is documentation,
not executable automation. It inherits the shared **Decision Systems Playbook**
(`~/Projects/decision_systems_playbook/`); where this file and the playbook
disagree, the playbook's safety policy wins.

## 1. What this project is

ADLS is a **research-only** decision-support system that tracks **liquidity
stress in affluent-household discretionary spending** (e.g., credit and deposit
flows, luxury/discretionary sales, delinquency and drawdown behavior) and turns
it into verified, labeled findings and reports usable as a **leading-indicator
signal layer** for the wider research family. It informs a human; it never acts.
Current phase: **Phase 3A verification and operational hardening**. The exact authorized and gated scope
is recorded in `STATE.md`; do not infer broader operational authority from it.

## 2. Startup reading sequence

Read these before acting, in sequence:

1. This file (`CLAUDE.md`).
2. `STATE.md` — current phase, MVP scope, approved decisions, blockers.
3. `tasks/todo.md` and `tasks/lessons.md` — open work and accumulated lessons.
4. Local governing docs: `docs/safety_policy.md`, `docs/label_policy.md`,
   `docs/verification_policy.md`, `docs/maker_checker_policy.md`,
   `docs/report_policy.md`; the playbook repo for `architecture`,
   `loop_architecture`, and canonical `schemas/`.
5. `docs/reference_library_adls.md` — which book/chapter answers which ADLS
   question (built from the owner's AI/ML library).

## 3. Prime directives

1. **Research-only.** Outputs inform a human; they never trigger a financial
   action. This system does not buy, sell, trade, place an order, or move funds.
2. **No autonomous financial actions** — ever, including from any loop or
   schedule. No order placement, fund movement, or position changes.
3. **Human-in-the-loop for anything irreversible or outward-facing.** Surface
   evidence; let a human decide.
4. **Verify before asserting.** A candidate is not a finding until an independent
   check confirms it (maker ≠ checker).
5. **No secrets in the repo.** Credentials come from environment / local config
   that is git-ignored.

## 4. Language & labels

- Use only the canonical machine-readable labels from `docs/label_policy.md`:
  `reject`, `watchlist`, `trigger_ready_research_candidate`,
  `needs_human_review`, `paper_candidate`, `research_only`, `validation_pending`.
- Indicator **levels** (e.g., a stress index value or band) are data fields, not
  labels — belief-card labels stay canonical.
- Never use action words (buy / sell / trade / order / entry / exit /
  recommendation) as labels or field names — only inside safety negations.

## 5. Planning rules

- Restate the goal; identify the smallest next change; note which policies apply.
- If a request touches a safety boundary, **stop and ask** before proceeding.
- Prefer documentation, schemas, and deterministic logic over speculative code.

## 6. Narrow-diff rules

- One coherent change per step; keep diffs small and reviewable.
- Do not exceed the authorized scope for the current phase.
- No drive-by refactors bundled into a feature change.

## 7. Git rules (explicit paths)

- Stage **explicit paths** only — never `git add -A` or `git add .`.
- Before finishing a unit of work, run and report: `git status --short`,
  `git diff --stat` (or `git diff --cached --stat` when staged), `git diff --check`.
- **Ask before staging or committing.** Never push without approval.
- Suggested commit message style: `area: concise change`.

## 8. Verification rules

- Every finding records provenance (source + timestamp), the criteria applied,
  the checks run, and a confidence / validation status.
- Maker and checker are independent steps. Self-attested results are at most
  `validation_pending` / provisional.
- **Macro-data lookahead note:** economic series are revised; a leading-indicator
  claim is only valid against **as-of (vintage) data** — evaluating on revised
  series is lookahead bias. (Application of the playbook's no-lookahead rule to
  macro data; treat as binding.)
- Unverifiable items become tracked verification debt — never silent drops.

## 9. Human approval requirements

Explicit, in-context human approval is required before:

- relying on any `needs_human_review` item,
- publishing or sending a report outside the local environment,
- adding providers, brokers, or any execution-capable code,
- promoting anything to an operational / live-running state,
- wiring ADLS outputs into any other system in the research family (downstream
  systems may cite ADLS **reports**; no automated signal feed without approval).

## 10. Project-specific customization block

- **Domain / object type:** `macro_indicator` — **NOT yet in the canonical
  schema enums**; extending `object_type`/`project` in the playbook schemas
  requires a playbook-side change with owner approval (tracked in STATE blockers).
- **Project slug:** `adls`.
- **Providers (read-only; owner-approved 2026-07-19, Phase 2 implementation
  authorized 2026-07-20):** public macro/credit series (including the built
  FRED/ALFRED adapter and local self-archive), retail & luxury sales releases,
  and deposit-flow data. New providers still require §9 approval. Respect terms
  and rate limits; no scraping that evades provider terms.
- **Criteria summary (owner-approved 2026-07-19):** deterministic composite
  stress indicators with predefined thresholds and bands; every component
  series documented with provenance, release lag, and revision behavior.
- **Report cadence (owner-approved 2026-07-19):** weekly research report;
  ad-hoc `needs_human_review` escalations on regime-break signals.
- **Project-specific safety notes:** ADLS is an advisory signal layer only.
  Its outputs carry research disclaimers and are never consumed as automated
  triggers by any trading-adjacent system.
- **Out of scope for now:** per-security recommendations (belongs to the
  screener projects), live scheduled loops, execution-capable paths,
  cross-system integrations, forecasting models, schema adoption, and external
  publication. Additional providers require explicit approval. Phase 3A is
  limited to verification and manual operational hardening; it does not widen
  any provider, scheduling, publication, or action boundary.
