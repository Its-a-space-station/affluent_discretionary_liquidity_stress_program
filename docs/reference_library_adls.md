# ADLS Reference Library Map — the bookshelf, slanted to liquidity-stress work

The full library index (20 books, tiers, offsets, reading order) lives in the
playbook: `~/Projects/decision_systems_playbook/docs/reference_library.md`.
This file is the **ADLS-specific lens**: a macro **leading-indicator** system's
core problems are regime/break detection, leakage-safe validation of "leading"
claims, calibration of stress probabilities, and disciplined indicator
selection. Page numbers are PDF pages (offsets in the playbook map).

## The five problems ADLS actually has, and where the shelf answers them

**1. Detecting stress episodes = regime & structural-break detection**
- Frequentist break tests (CUSUM, SADF explosiveness) — the deterministic
  detectors an MVP composite can use: de Prado Ch 17, PDF 276–287
- Bayesian complement (HMM stress/calm regimes, Viterbi audit trail of "which
  regime were we in," particle filters for non-Gaussian states): Dixon Ch 7,
  PDF 244–257
- The forgetting dial for stress estimates under drift (constant-α recency
  weighting): Sutton & Barto §2.5, PDF 54–55

**2. Validating a "leading indicator" claim without fooling yourself**
- Purged/embargoed CV — the mechanical no-lookahead protocol: de Prado Ch 7,
  PDF 130–138; formal statement (decisions measurable w.r.t. information
  actually available at t): Powell §9.12, PDF 379–383
- ADLS-specific application (inference, binding per CLAUDE.md §8): validate on
  **vintage/as-of data only** — revised macro series are lookahead in disguise
- Lead–lag claims across many candidate series = a multiple-comparisons
  problem: Monte-Carlo/permutation p-values (DasGupta §19.1.2, PDF ~643),
  ROPE/effect-size framing (Murphy-Intro §5.2.6, PDF 215–219), uniform-bound
  theory (Mohri Ch 3 + App D, PDF ~44/~452)

**3. Choosing the indicator basket = selection under noise**
- Optimizer's curse / winner's curse — the best-looking candidate series is
  systematically overrated; shrink or revalidate held-out before promotion:
  R&N printed 637–638 (PDF 656–657); same math as maximization bias +
  double-selection de-biasing: S&B §6.7, PDF 155–158
- Overlapping/correlated series must not double-count as confirmation —
  concurrency-discount the evidence: de Prado Ch 4, PDF 86–95 (the schema's
  `independence_group` field exists for exactly this)

**4. Stating stress probabilities honestly = calibration & intervals**
- Reliability diagrams, ECE, temperature scaling / isotonic fixes:
  Murphy-Advanced §14.2, PDF 605–611
- Conformal intervals — with the load-bearing caveat that exchangeability
  breaks under serial correlation (macro series are serially correlated; use
  time-series conformal variants): Murphy-Advanced §14.3, PDF 612
- Belief state as a distribution (the formal belief card), Bayes-factor
  evidence ladders for gate decisions: Powell §9.3 PDF 355–360; Dixon Ch 2,
  PDF 71–90
- When to escalate to `needs_human_review` = Value of Information: R&N §16.6,
  PDF 645–655

**5. Ingesting macro/policy text safely (if/when ADLS reads Fed & policy text)**
- Third-party text is untrusted input — indirect prompt-injection defenses,
  instruction hierarchy: Huyen Ch 5, PDF 470–487
- Stance classification under label scarcity (zero-shot NLI fragility,
  provenance-friendly embedding-kNN, fine-tune past ~50 labels): Tunstall
  Ch 9, PDF 300–317
- Any LLM in the pipeline is maker-only; deterministic/independent checker
  patterns: Huyen Ch 3 (LLM-judge limits) PDF 205–222, Ch 10 (guardrail
  architecture) PDF 858–875; constrained decoding keeps labels on-menu:
  Alammar Ch 6, PDF 270–277

## System-spec discipline

When blueprinting ADLS formally, use Powell's 5-element model (state, decision,
exogenous information, transition, objective): Powell Ch 9, PDF 353–404 — and
the base-model vs lookahead-model vocabulary (PDF 373) when stating what any
historical validation does and does not certify.

## ADLS reading order (first five)

1. de Prado Ch 7 (purge/embargo — the validation spine) — PDF 130–138
2. de Prado Ch 17 (CUSUM/SADF break detection) — PDF 276–287
3. Murphy-Advanced §14.2–14.3 (calibration + conformal, serial-correlation
   caveat) — PDF 605–612
4. R&N §16.5–16.7 (decision networks, VPI, optimizer's curse) — PDF 645–657
5. Dixon Ch 7 (HMM regimes as the Bayesian complement) — PDF 244–257

Library gaps that bite ADLS specifically (flagged in the playbook map): no
dedicated multiple-comparisons/FDR text and no classical time-series reference
(ARIMA/GARCH/cointegration) — both are acquisition candidates for exactly this
project's workload.
