# Verification Policy

How a claim earns the right to be called a finding. Verification is a first-class
pipeline stage (see [architecture.md](architecture.md)), not an afterthought.

## 1. Principle

**Nothing is asserted that has not been checked against a source.** Analysis
produces *candidates*; verification turns candidates into *findings* with an
explicit confidence label. Unverified material is never silently promoted; it is
either downgraded or tracked as debt
(see [verification_debt_policy.md](verification_debt_policy.md)).

## 2. What must be verified

- **Source provenance** — the datum came from the provider it claims to, at a
  known time, through a known interface.
- **Freshness** — the data is within the acceptable age for its use; stale data
  is labeled stale.
- **Criteria application** — the system's rules were applied correctly to the
  data (recomputable from inputs).
- **Internal consistency** — derived values agree with their inputs; no
  contradictions across fields.
- **Reproducibility** — given the same inputs, the same candidate is produced.

## 3. Confidence labels

Every finding carries exactly one confidence label:

| Label | Meaning |
| --- | --- |
| `Verified` | Checked against source; criteria reproducibly satisfied. |
| `Provisional` | Plausible but one or more checks are incomplete. |
| `Unverified` | Surfaced for transparency; checks not yet done. |
| `Conflicting` | Sources or checks disagree; needs human adjudication. |
| `Stale` | Was verified, but the underlying data is now too old. |

Labels only move *downward* automatically (e.g., `Verified` → `Stale`). Moving a
label upward requires a fresh verification pass. These confidence labels are
distinct from the *result* labels in [label_policy.md](label_policy.md).

## 4. Maker / checker separation

The step that produced a candidate may not be the sole step that verifies it.
An independent checker re-derives or cross-checks the result. See
[maker_checker_policy.md](maker_checker_policy.md). Self-attested results without
an independent pass are at most `Provisional`.

In dynamic multi-agent workflows, **adversarial verification** — independent
skeptic agents that each try to refute a finding — is an encouraged technique for
high-stakes findings, provided the skeptics are independent of the maker and do
not replace a deterministic check where one exists. See
[dynamic_workflow_policy.md](dynamic_workflow_policy.md).

## 5. Evidence trail

Each finding records: the source(s) and timestamps, the criteria/version
applied, the checks run and their outcomes, and the resulting confidence label.
A reviewer must be able to retrace the path from raw observation to finding.

## 6. Handling failure

- A failed check **downgrades** the label and records *why*.
- Findings that cannot be verified within policy are logged as **verification
  debt**, not dropped — so coverage gaps stay visible.
- A `Conflicting` finding is escalated to a human, never auto-resolved.

## 7. Verification in Phase 2 and Phase 3A

Verification now covers code, point-in-time data behavior, deterministic
artifacts, and documentation consistency. Every implementation slice requires
focused regression tests plus the repository posture, lint, and type checks;
real-data smoke checks must record coverage and provenance without exposing
credentials.

Phase 3A adds a blind two-implementer acceptance protocol. Coordinator tooling
may freeze and hash a spec-only evidence packet, seal an independently produced
candidate before reference disclosure, and compare value-free paths afterward.
It may not produce the candidate, attest to independence, reveal the reference
early, or close verification debt without human review.

## 8. Playbook v2 additions

- **Fail-before / pass-after** — where applicable, verify a check fails now and
  passes after the change, with regressions staying green
  ([task_execution_policy.md](task_execution_policy.md)).
- **Verifier / reranking** — a verifier ranks and critiques candidates for review;
  it never approves a consequential change
  ([verifier_and_trajectory_policy.md](verifier_and_trajectory_policy.md)).
- **Failure taxonomy** — stuck loop, empty patch, weak / missing verification,
  incorrect localization / edit, over-broad refactor, unauthorized config change,
  safety-boundary violation. Classify them and keep failed trajectories.

## 9. Forecast evaluation (v2.1)

Forecast evaluation follows the same execution-observed discipline, plus:
**temporal split only**, **no drop-last** (it biases results across batch sizes),
and **fixed + rolling** evaluation with a declared stride and regime / horizon
breakdowns. Low forecastability is a **fail-safe abstention** signal — recommend
manual review rather than a confident forecast. See
[forecast_benchmark_policy.md](forecast_benchmark_policy.md).

## 10. Structural breaks as validation events (v2.2)

Report performance **by regime and by pre / post-break period** — never pooled;
aggregate backtests hide pre / post-break failure. A detected macro / policy /
liquidity / regulatory / platform / process change triggers revalidation, and a
major **unvalidated** break freezes or demotes autonomy until post-break validation
passes. See [structural_break_policy.md](structural_break_policy.md).

## 11. Cross-references

[architecture.md](architecture.md) · [maker_checker_policy.md](maker_checker_policy.md)
· [label_policy.md](label_policy.md) · [report_policy.md](report_policy.md) ·
[verification_debt_policy.md](verification_debt_policy.md)
