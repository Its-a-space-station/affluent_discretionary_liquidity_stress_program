# Time-Series Forecasting Papers Map — indexed against ADLS

Synthesized 2026-07-19 from a three-agent review of the 26 PDFs in
`~/Documents/Papers on Time Series Forecasting/`. Companion to
`reference_library_adls.md` (books). Governs the **gated v1.2+ forecasting
question** and hardens the current validation protocol. One paper is misfiled
(AIRS-Bench — an AI-agents benchmark; belongs in the coding-papers folder).

## The verdict in one paragraph

This literature, read honestly, endorses ADLS's deterministic-first posture.
DLinear (Zeng et al., AAAI 2023) showed a **one-layer linear model beat every
long-horizon transformer by 20–50%** — and that a naive repeat-last-value
baseline beat all of them on financial data; the survivors (TiDE, N-HiTS,
TimeMixer) are MLPs that adopted the linear models' tricks. TFB (PVLDB 2024)
found **VAR and linear regression beat PatchTST/FEDformer on economic/trend
data** and documents the field's evaluation sins. Every deep-model gain rides
on 10k+-point high-frequency data or pooling across thousands of series — ADLS
has 9 series × 150–450 monthly points, neither axis. And **zero of the eight
foundation-model/LLM-forecaster papers address vintage data or test cleanly on
monthly macro**: TimesFM trains on M4-monthly, Moirai's corpus contains an
Econ/Fin domain plus all of Monash, LLMTime evaluates on `fred_md` while its
own leakage defense covers none of the monthly series. The transferable value
is (a) evaluation protocol, (b) input vocabulary, (c) the baseline ladder any
future model must climb.

## What this changes now (PROPOSED v1.2 delta in composite_spec §14)

1. **Baseline floor** for the pre-registered claim: beat no-change/seasonal-
   naive, AR, and VAR — not just the permuted null. [TFB; DLinear; N-BEATS
   MASE/OWA discipline]
2. **Per-regime, macro-averaged reporting**: turning points are rare but ARE
   the use case; a pooled score drowns them in expansion months. [QUITOBENCH]
3. **Cross-series leakage embargo**: all 9 series share the business cycle —
   permutation blocks must embargo correlated periods jointly, not per-series.
   [QUITOBENCH direct/indirect leakage taxonomy]
4. **Score every test point; frozen pipeline** (no dropped windows — TFB's
   "Drop-Last" trick makes scores batch-dependent). [TFB]
5. **Input-availability taxonomy** (TFT): classify every input as
   known-future / observed-with-lag / static — operationalizes no-lookahead at
   the ragged edge and makes the PIT claim auditable. [TFT — the single most
   valuable lift for the current deterministic design]

## If forecasting is ever un-gated (v1.2+ docket, evidence-backed)

- **The ladder**: nothing ships until it beats seasonal-naive on MASE/OWA
  out-of-sample; the champion to beat is **decomposition + one-layer linear
  (DLinear/NLinear)**; the only architecture template worth considering at
  this scale is TiDE-shaped (channel-independent MLP with an explicit linear
  residual path and first-class covariates). Attention/graph models are
  off-regime (iTransformer needs many variates; MTGNN failed on its own
  8-series dataset). [DLinear; N-BEATS; TiDE; LSTNet's AR-ablation; MTGNN]
- **Variance honesty**: the deep TS literature tunes seeds (N-HiTS) and
  ensembles 180 models (N-BEATS) to stabilize results — any ADLS model must
  show seed/split variance small relative to its claimed edge. [N-BEATS; N-HiTS]
- **Intervals, when wanted**: quantile head + pinball loss + sorted quantiles
  (TFT / Toto 2.0 both converged here; Toto replaced its mixture head "for
  stability and calibration"); don't assume Gaussian. Pre-register coverage
  targets with the point claim. [TFT; Toto 2.0; Moirai]
- **Exogenous entry pattern**: endogenous/exogenous split with covariates at
  series-level representation (robust to ragged lags — no forced alignment);
  adapter-style injection (ChronosX IIB/OIB) is the published shape. Endogenous
  signal quality dominates — don't over-weight noisy covariates. [TimeXer; TFT;
  ChronosX]

## Foundation forecasters: the gate conditions (C1–C6)

A zero-shot foundation model may take at most a **shadow challenger** role,
logged and never wired to decisions, and only after ALL of:
- **C1** Demonstrated skill on genuinely unseen macro (post-cutoff data, or a
  provider that provably excluded public macro from pretraining — Toto 2.0's
  "no public forecasting data in pretraining" is the existence proof).
- **C2** Vintage/PIT evaluation on as-first-released values — every paper in
  this folder trains/tests on revised series; a model that memorized revised
  paths "forecasts" revisions it could not have known.
- **C3** Beats the incumbent composite AND the baseline ladder on our 9 series.
- **C4** Empirical interval coverage on our series (LLMTime: RLHF degraded
  GPT-4's calibration below GPT-3's — alignment can silently wreck intervals).
- **C5** Monthly-context adequacy (TimesFM caps monthly context at 64 points;
  Moirai's corpus is 0.04% monthly).
- **C6** Determinism/stability bounds for sampling-based forecasters.
These are the tests the playbook's `before_universal_forecaster_use` checklist
should encode (candidate playbook enrichment — owner decision).

## Tiered map

**Load-bearing (keep close):**
- DLinear / "Are Transformers Effective?" (Zeng) — the doctrinal cornerstone
- TFB (Qiu) — economic-data findings + the evaluation-sins catalog; includes
  FRED-MD monthly, the closest analog to ADLS anywhere in the folder
- QUITOBENCH (Xue) — regime-balanced macro-averaged evaluation, leakage
  taxonomy, effect-size-over-p-value (data irrelevant, method load-bearing)
- N-BEATS (Oreshkin) — the only model paper in ADLS's data regime (M3/M4/
  TOURISM monthly, 60–450 pts); source of the MASE/OWA beat-the-naive floor
  and interpretable trend+seasonality bases (caveat: its power is global
  training over thousands of series — untransplantable to 9)
- TFT (Lim) — input taxonomy (adopt now) + quantile/coverage template (v1.2+)
- LLMTime (Gruver) — only true zero-shot at our scale; read Appendix B for the
  leakage treatment and its gaps
- Toto 2.0 (Khwaja) — the how-to-evaluate paper: contamination-resistant
  design as the vendor standard C1 demands
- TiDE (Das) — the architecture template if the gate ever opens
- ChronosX (Arango) — the covariate-injection pattern

**One-idea keeps**: Autoformer (decomposition block), PatchTST (channel
independence + instance norm), LSTNet (linear-AR anchor does the work; deep
adds nothing on non-periodic data), PITS (param-light MLP more robust than
attention), Benitez review (tuned-simple ≈ tuned-complex; protocol only),
TimeXer (ragged-covariate handling).

**Historical context / skippable for ADLS**: Informer, iTransformer, N-HiTS,
TimeMixer, Deep-Transformer-influenza, MTGNN, TS2Vec, Time-LLM, Moirai,
TimesFM (the last two: skim only for the contamination-evidence specifics).

**Misfiled**: "A suite of tasks for frontier AI research science agents"
(AIRS-Bench, Lupidi et al.) — an LLM-agent research benchmark, not
forecasting; move to `~/Documents/Papers on Coding/`.
