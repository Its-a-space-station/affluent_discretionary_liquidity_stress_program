# HANDOFF — session of 2026-07-19/20

For the next session. Read this WITH `STATE.md` (live snapshot) and
`tasks/todo.md` (slice checklist) — the SessionStart hook auto-injects those
two plus `tasks/lessons.md`; this file is the narrative connecting them.
Auto-memory also carries cross-session pointers (`adls-project`,
`claude-hooks-environment`, `kalshi-secrets-remediation`).

## The one-paragraph version

In one session the owner's global Claude workflow was built (CLAUDE.md +
verified SessionStart/Stop hooks), the Decision Systems Playbook's philosophy
was adopted globally, three literature collections (20 ML books, 39 coding-
agent papers, 26 time-series papers) were agent-reviewed into doctrine-mapped
reference docs, and ADLS went from an empty GitHub repo to: checklist-
compliant bootstrap → owner-approved Indicator Basket v1 → checker-hardened
Composite Spec v1.2 → **Phase 2 authorized** → **Slice 1 built, live-verified,
and pushed** (`537c1d0`). Everything below exists to let you continue from
Slice 2 without re-deriving any of it.

## What was decided (all owner-approved, in order)

1. **Purpose**: ADLS is a research-only macro **leading-indicator** system for
   affluent-household discretionary liquidity stress; advisory layer for the
   wider research family. Informs a human; never acts.
2. **CLAUDE.md §10 fields**: providers (read-only FRED/ALFRED vintages, retail
   & luxury releases, deposit flows — adapters were still gated then), 
   deterministic composite criteria, weekly report cadence.
3. **Indicator Basket v1** (`docs/indicator_basket_proposal.md`): 9-series
   vintage-validatable core across five stress dimensions + report-only
   affluent overlay (EGI income-quartile delinquency, JPMC/BofA, DFA, SCE,
   FINRA) + weekly manual self-archive for no-vintage sources. Every series
   checker-verified against its publisher. All inputs `observed_with_lag`.
4. **Composite Spec v1.1** (`docs/composite_spec_v1.md`): v1 was demolished by
   an adversarial checker (it would have read April 2020 as ~Normal — PSAVERT
   is identity-coupled and stress-inverted; strain is onset-inverted) and
   rebuilt: PSAVERT excluded, Strain = confirming overlay only, four leading
   independence families equal-weighted, frozen as-published canonical
   history, Tier-A-only bands (36m burn-in, 2m dwell), pre-registered
   single-claim validation with binding power statement.
5. **Spec v1.2 (§14)**: validation hardening from the TS-literature review —
   baseline floor (seasonal-naive/MASE, AR, VAR), per-regime macro-averaged
   reporting, cross-series joint permutation embargo, score-every-point,
   input-availability taxonomy.
6. **Phase 2 authorization** (2026-07-20, via approved plan at
   `~/.claude/plans/imperative-gathering-hummingbird.md`): scope-guard lifted
   for EXACTLY: read-only ALFRED adapter + vintage cache, deterministic
   engine (§1–§7), validation harness (§9+§14), weekly report. **Still
   gated**: schedulers/launchd, execution paths of any kind, forecasting
   models, schema (belief-card) adoption, external publication.
7. **Spec errata** (`canonical/spec_errata.md`, binding on maker AND checker):
   z-window excludes current obs, population σ; decimal(6) half-even +
   canonical JSON serialization; WRMFNS staleness 45d; weekly→monthly = mean
   of Wednesday observations; baseline exact specs must be pinned there
   BEFORE the first real-data validation run (item 5, still placeholder).

## Where the code stands (Slice 1 of 7, complete)

- `src/adls/`: config (only getenv site, never echoes), registry (Basket v1 as
  data), contracts, `alfred/client.py` (realtime-range observations +
  vintagedates, 429/timeout retry with backoff, **URL-free errors** — the key
  rides the query string), `alfred/cache.py` (span-based SQLite vintage cache:
  value at vintage V = span with realtime_start ≤ V ≤ realtime_end),
  `cli.py` (`adls fetch`).
- Tests 17/17 green + ruff + mypy (`.venv`, Python 3.14): unit + posture suite
  (env-token confinement, requests confined to alfred/, forbidden-vocabulary
  scan with sort_order/ORDER BY exemptions, no scheduler artifacts).
- **Live-verified**: RSFSDP (166 vintages/2,512 spans), RSFHFS (166/2,607),
  VISASMIDSA (27/176) cached in `data/adls.sqlite` (git-ignored).
- **Vintage-depth RESOLVED** (errata item 6): 2013-05-13 first vintages carry
  256 obs back to 1992 — 10y z-windows fully powered, no fallback.
- **Visa SMI methodology RESOLVED**: 0–200 diffusion index, neutral 100 →
  §3.2 `(100 − level)` transform locked.
- Live fire found+fixed one real bug: network timeouts bypassed the retry
  loop (now retried; regression tests pin it, including that timeout
  exceptions never leak the keyed URL).
- `FRED_API_KEY` is in `.env` (git-ignored, owner-entered via hidden prompt;
  **never read or log it** — source it: `set -a; source .env; set +a`).

## Immediate next step: Slice 2 — uniform input layer

Per the approved plan (full text in the plan file; slices also in todo):
- `src/adls/inputs/archive.py`: normalized-CSV contract for manual
  `data_archive/` sources — columns `series_id, observation_date, value_text,
  release_date, source_file, retrieved_at`; ValidationResult (collect
  errors/warnings, NEVER raise on data issues — Trading_consultant
  data_contract.py shape, already in `contracts.py`).
- `src/adls/inputs/loader.py`: uniform PIT view — for assembly date D, per
  series: latest vintage ≤ D (ALFRED via cache) or rows with release_date ≤ D
  (archive), one row shape for both. Archive rows are spans with
  realtime_start = release_date.
- Tests: contract fixtures (missing column/unsorted/duplicate/gap →
  collected, not raised); PIT boundaries (vintage == D inclusive; D+1
  provably unselectable); UMich rows from `data_archive/2026-07-19/` load
  end-to-end.
- Also: update `data_archive/README.md` with the normalize-to-CSV step for
  the weekly routine.
Then Slices 3–7: engine core → calendar/canonicalization/frozen store/bands →
independent checker → validation harness → weekly report. Slice details,
tests, and exit criteria are all in the plan file.

## Deferred owner decisions (raise at the flagged moment, not before)

- Seed the live frozen store from the checker-Verified §9 reconstruction, or
  start cold? → after Slice 6.
- statsmodels as optional `[validation]` extra vs pinned-fixture cross-check
  only? → Slice 6 (default: pinned fixtures).
- Playbook schema enums (`object_type: macro_indicator`, `project: adls`) —
  playbook-side change, blocks canonical schema adoption only.
- Optional: enrich playbook `before_universal_forecaster_use` with gate
  conditions C1–C6 (`docs/reference_library_timeseries.md`).
- launchd scheduling — separate gate, not Phase 2.

## Session conventions that MUST carry forward

- **Ask before staging/committing; explicit paths; push only on approval.**
  The rhythm all day: present → owner approves → commit → offer push.
- **Maker≠checker before anything settles**: every proposal today went
  through an independent checker agent, and it caught real errors every time
  (basket: nonexistent NY Fed cut; spec: the 2020 sign inversion; papers:
  contamination). Do not present significant conclusions unchecked.
- **Errata is binding**: any convention ambiguity gets pinned in
  `canonical/spec_errata.md` with owner approval, never resolved silently.
- **Never** read `.env` files (any repo), log request URLs, or copy Kalshi
  execution/sizing code. UMich data is internal-use-only (no raw levels in
  committed files or external-able reports).
- Weekly manual archive routine is due each Friday (`data_archive/README.md`)
  — ICI is the source that decays (20-week window). First pull was
  2026-07-19 (ICI secured; FINRA/UMich/EGI/JPMC/BofA are manual steps).

## Beyond this repo (context the next session may need)

- **Global setup** (`~/.claude/CLAUDE.md`, 72 lines + hooks): SessionStart
  injects STATE/state + lessons + todo (150-line caps, head for STATE, tail
  for the rest); Stop hook blocks completion on unchecked todo items once per
  turn. Both verified live. Hook scripts in `~/.claude/hooks/` are clean
  (diagnostics stripped).
- **Playbook repo**: reference maps committed (`e30526b`) — books
  (`reference_library.md`) + coding-agent papers
  (`reference_papers_coding_agents.md`); AGENTS.md now tracked. Its STATE.md
  remains stale (says blueprints "not written") and ADLS has no blueprint
  there yet — candidate playbook catch-up bundle.
- **Kalshi remediation** (separate session, executed): no leak anywhere; PEM
  copied to `~/.config/kalshi-trading-bot/` (600) and `.env` repointed; the
  stray `~/Projects/Kalshi-trading-bot` dir is QUARANTINED at
  `~/.config/kalshi-trading-bot/quarantine-20260719/`. **User still owes**: a
  scanner restart (self-verifying at startup) and, after a clean restart,
  purging the quarantine + env-backup. Rollback commands are in the home-dir
  `~/tasks/todo.md` and the memory file.
- **Housekeeping queue** (owner deletions, never do unasked): duplicate
  Sutton & Barto PDF (85MB), duplicate AlexNet PDF, stray leading-space ADLS
  folder in `~/Projects` (its Boris docx is fully encoded in the global
  setup), misfiled AIRS-Bench paper (TS folder → coding folder).

## The acid test

You should be able to: read this + STATE + todo, `cd` here, `source .env`
safely, run `.venv/bin/pytest -q` (expect 17 green), and start writing
`src/adls/inputs/archive.py` against the plan — without re-opening any
question settled above.
