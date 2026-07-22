# HANDOFF — sessions of 2026-07-19 through 2026-07-22

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
and pushed** (`537c1d0`) → **Slice 1 repaired and pushed** (`ef69c8c`) →
**Slice 2 built and pushed** (`7927586`) → **Slice 3 built, independently
reviewed, and pushed** (`8621898`) → **Slice 4 built, independently reviewed,
repaired, and pushed** (`c4bb2e7`) → **Slice 5 built, reviewed, repaired, and
pushed** (`7bd5f46`) → **Slice 6 built, real-data executed, and independently
checker-Verified under its explicit historical-final assumption** → **Slice 7
built, live-verified, owner-reviewed, and pushed with Slice 6** (`0d95cec`). The
pre-registered result is `coincident_monitor`: 2/4 episode hits, better than
seasonal-naive and VAR but worse than AR(12), with non-monotonic calibration.
The owner selected a cold live-store start; the first local weekly report is
complete and external publication remains gated.

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
   canonical JSON serialization; WRMFNS staleness 45d and Monday→Wednesday
   mapping; complete pooled families only; archive availability is the later of
   release/retrieval with explicit stages and bounded coverage; validation uses
   an equal mean of independently detrended real-PCE component gaps, never a
   sum of chained-dollar levels. Baseline exact specs were owner-approved in
   item 5 on 2026-07-21, before the first real-data validation run.

## Where the code stands (Slices 1-7 complete)

- `src/adls/`: config (only getenv site, never echoes), registry (Basket v1 as
  data, including WRMFNS +2-day canonical shift), contracts,
  `alfred/client.py` (realtime-range observations + vintagedates, 429/timeout
  retry with backoff, per-call status telemetry, **URL-free errors** — the key
  rides the query string), `alfred/cache.py` (span-based SQLite vintage cache
  with declared, non-regressing coverage), `cli.py` (`adls fetch`). Fetches now
  pin discovery and observations to one explicit fetch-date cutoff, mark
  completeness through that cutoff after both succeed, and audit the endpoints
  separately. This correctly handles series whose last change predates the
  requested point-in-time date.
- `inputs/archive.py` validates normalized CSVs with collected errors/warnings,
  canonical UTC/date/stage/provenance rules, deterministic sequence and
  duplicate/conflict checks, frequency-gap warnings, non-overlapping episodes,
  and per-series coverage. `inputs/loader.py` returns one PIT value shape for
  ALFRED and archive inputs, converts coverage problems to validation errors,
  applies final-only canonical UMich, and hides future episode close dates.
- `engine/` is the Slice 3 maker: one complete PIT snapshot produces pooled
  retail/liquidity stress, Visa and UMich scores, a separate Strain overlay,
  Tier A/B aggregation, and explicit staleness/dropout flags. Z windows exclude
  the current observation and use population sigma with ±3 caps. Canonical and
  provisional archive modes are distinct; late retrieval is rechecked; raw or
  reversibly transformed UMich levels never enter canonical bytes. Serialization
  is six-place half-even canonical JSON, pinned at SHA-256
  `d568528a50258674a29a8b943680dfe71c76dad3462896ed8e88b93326a78dc8`
  after Slice 4 moved the synthetic April 2020 fixture to its proper 2020-06-19
  canonical finalization date.
- `calendarutil.py` provides the static 2013-2027 NYSE closure table, shifted
  weekly assemblies, and M+2/15 finalization. Assembly mode is calendar-derived;
  ordinary weekly outputs cannot be mislabeled canonical.
- `engine/bands.py` and `engine/canonical.py` implement expanding frozen Tier-A
  percentiles, publication-precision thresholds, burn-in/dwell state, Tier-B
  mapping, and the append-only canonical store. Each line embeds its redacted
  canonical source assembly and hash. Reads revalidate chronology, source,
  PIT dates, redaction/licenses, composite arithmetic, and band replay. Thread
  and process locks cover validation through fsync. The committed live store is
  intentionally empty under the owner-approved cold start.
- `checker/` independently reconstructs cache/archive PIT histories, all five
  family scores, Tier A/B composites, finalization dates, and frozen band/dwell
  state from checker-owned SQL, constants, calendar, and arithmetic. It holds
  one SQLite read snapshot, validates exact embedded/outer schemas and hashes,
  audits all evidence before applying conflict-over-debt labels, and is posture-
  barred from maker/input/ALFRED/registry/contracts/calendar imports. The five
  planned defect seeds all produce `Conflicting`; the remaining two-implementer
  acceptance gap is tracked in `docs/verification_debt.md` VD-001. Slice 7 adds
  checker-owned verification of standalone canonical and provisional weekly
  assemblies without weakening that import boundary.
- `validation/` now performs one-snapshot weekly/frozen reconstruction, marks
  the historical UMich-final assumption in canonical source flags, independently
  detrends both real-PCE components, retains every score origin and abstention,
  evaluates seasonal-naive/AR/VAR controls, static NBER regimes, calibration,
  and a joint embargoed block null, and emits deterministic descriptive-only
  bytes. The explicit checker assumption mode verifies fixture and real
  reconstructions; ordinary mode rejects both. The first real run used the
  approved contract unchanged across 155 canonical months (2013-05 through
  2026-03), repeated byte-identically, and passed 310/310 checker checks. Its
  four episodes produced two hits; the primary beat seasonal-naive and VAR but
  not AR(12), invoking the binding `coincident_monitor` failure clause. See
  `docs/validation_harness.md`.
- `reporting/` snapshots the cache and file evidence once, builds and
  independently verifies the current assembly, and emits exact assembly JSON,
  canonical evidence-bearing report JSON, and Markdown. Every finding carries
  result/confidence labels, evidence IDs, and a timestamp. The launch audit
  keeps the `coincident_monitor`, non-monotonic calibration, open debt, cold
  history, and external-publication gate visible. See
  `docs/weekly_reporting.md`.
- 149/149 unit + posture tests, ruff, explicit touched-file format check, and
  mypy across 43 source files are green (`.venv`, Python 3.14).
  (env-token confinement, requests confined to alfred/, forbidden-vocabulary
  scan with sort_order/ORDER BY exemptions, validation network/wall-clock
  confinement, no scheduler artifacts).
- **Live cache**: all nine ALFRED series are complete through the explicit
  2026-07-22 fetch cutoff in ignored `data/adls.sqlite`; the two PCE outcomes
  still share latest common change vintage 2026-06-25. SQLite integrity is
  `ok` and span overlaps are zero. The live
  smoke found and fixed valid ALFRED `.` sentinels being misclassified as
  fatal outcome corruption.
- **UMich historical source READY**: the official Table 2n workbook and
  provider-authored 1991-2026 final-release calendar are preserved in ignored
  `data_archive/2026-07-21/`; 425 normalized finals live only under ignored
  `data/normalized_archive/`. Licensed levels are absent from tracked files and
  generated canonical bytes.
- **Vintage-depth RESOLVED** (errata item 6): 2013-05-13 first vintages carry
  256 obs back to 1992 — 10y z-windows fully powered, no fallback.
- **Visa SMI methodology RESOLVED**: 0–200 diffusion index, neutral 100 →
  §3.2 `(100 − level)` transform locked.
- Live fire found+fixed one real bug: network timeouts bypassed the retry
  loop (now retried; regression tests pin it, including that timeout
  exceptions never leak the keyed URL).
- Whole-repo review found+fixed additional defects: arbitrary future cache
  vintages were accepted despite a coverage table; observation and vintage-date
  calls could straddle releases; audit rows hard-coded status/endpoint/429 data;
  `--series` accepted an empty list and archive-only IDs; the ICI log recorded an
  obsolete 2025 URL; and four spec conventions were incomplete or invalid.
- `FRED_API_KEY` is in `.env` (git-ignored, owner-entered via hidden prompt;
  **never read or log it** — source it: `set -a; source .env; set +a`).

## Immediate next step: first operational weekly cycle

1. Phase 2 is complete. Slices 6 and 7 were owner-reviewed, committed, and
   pushed to `origin/main` as `0d95cec`; there is no authorized Slice 8.
2. On Friday 2026-07-24, run the manual archive routine, refresh ALFRED, advance
   normalized archive coverage with provenance-bearing evidence, and generate
   the local report using the 2026-07-17 report as the previous artifact.
   Prioritize the decaying ICI window and the outstanding FINRA, EGI, JPMC, and
   BofA first-pass captures.
3. Keep the historical reconstruction separate, preserve the cold-start
   boundary, and leave scheduling and external publication gated. After the
   operational cycle, the next phase requires owner authorization; VD-001's
   genuinely independent reconstruction is the recommended first priority.

## Deferred owner decisions (raise at the flagged moment, not before)

- Live-store decision resolved 2026-07-22: start cold. Reconsidering or seeding
  later requires a new explicit owner decision and adjudication of open debt.
- statsmodels choice resolved to the default pinned-fixture-only path; the
  one-time 0.14.5 cross-check is committed, with no runtime dependency.
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
  — ICI is the source that decays (20-week window). The 2026-07-19 ICI log used
  an obsolete 2025-named URL; the raw file was preserved and correct current-
  year provenance was captured in `2026-07-21/` (byte-identical). UMich's
  historical workbook and release calendar were captured there as well. FINRA/
  EGI/JPMC/BofA are still manual steps.

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

You should be able to: read this + STATE + todo, `cd` here, run
`.venv/bin/pytest -q` (expect 149 green), and repeat `adls validate` against the
ignored normalized UMich archive with byte-identical outputs. The explicit
assumption checker must return `Verified`; ordinary mode must return
`Conflicting`. Keep the live store cold; never promote the separate Slice 6
frozen-equivalent validation artifact into live history.
