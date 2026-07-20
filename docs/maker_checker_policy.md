# Maker / Checker Policy

Separation of duties for analysis. The component that *produces* a conclusion is
not the only component that *confirms* it. This is the structural backbone of
[verification_policy.md](verification_policy.md).

## 1. Roles

- **Maker** — the analysis step that applies the system's criteria to normalized
  data and emits *candidate* findings. The maker proposes; it never publishes a
  verified result on its own authority.
- **Checker** — an independent step that re-derives or cross-checks each
  candidate and assigns a confidence label. The checker can confirm, downgrade,
  flag as conflicting, or send to verification debt.

The two roles must be **independent**: different code paths and, where possible,
different inputs or methods. A maker that grades its own work produces at most a
`Provisional` result.

## 2. The handoff

```text
  data ──▶ MAKER ──▶ candidate(+evidence) ──▶ CHECKER ──▶ labeled finding
                                                 │
                                                 ├─ confirm   → Verified
                                                 ├─ partial   → Provisional
                                                 ├─ disagree  → Conflicting (→ human)
                                                 └─ cannot    → Verification debt
```

The checker receives the candidate **and** its evidence trail (sources,
timestamps, criteria version) so it can retrace the maker's reasoning rather than
trust its conclusion.

## 3. What the checker verifies

At minimum (per [verification_policy.md](verification_policy.md)): source
provenance, freshness, correct criteria application, internal consistency, and
reproducibility. The checker's checks should be **independent** of the maker's
computation wherever feasible (recompute from raw inputs, or use a second
source).

## 4. Outcomes

| Checker outcome | Confidence label | Next step |
| --- | --- | --- |
| Independent recheck agrees | `Verified` | eligible for report |
| Some checks incomplete | `Provisional` | report with caveat or hold |
| Sources/checks disagree | `Conflicting` | escalate to human |
| Cannot complete checks | (unchanged) | record as verification debt |
| Underlying data too old | `Stale` | refresh before use |

## 5. Human as ultimate checker

For `Conflicting` results, anything novel, or anything near a safety boundary,
the human is the final checker. The system surfaces evidence and its
disagreement; the human adjudicates. No automated tie-breaking on safety-relevant
calls.

## 6. Applicability

This policy applies to analytical conclusions. It also applies, in spirit, to
*this playbook's own changes*: a non-trivial doc or schema change benefits from a
second-pass review against the policies before it is treated as settled.

It also extends to **dynamic multi-agent workflows**: worker agents are makers and
evaluator agents are checkers, and the independence requirement holds across
agents — a checker must not merely re-run the maker's computation, and a
synthesizer that merges results is not a checker. See
[dynamic_workflow_policy.md](dynamic_workflow_policy.md).

## 7. Anti-patterns to avoid

- Maker and checker sharing the same buggy computation (no real independence).
- Treating "the maker is confident" as verification.
- Auto-resolving `Conflicting` to keep a pipeline "clean."
- Dropping un-checkable candidates instead of recording them as debt.

## 8. Playbook v2: verifier as ranker, roles separated

A **verifier is a checker that ranks and critiques** candidates — it selects for
human review and never approves a promotion, config change, or other consequential
change ([verifier_and_trajectory_policy.md](verifier_and_trajectory_policy.md)). In
staged and multi-agent work the maker/checker split maps onto separated roles —
planner, localizer, maker, executor / verifier, checker, synthesizer — and **no
role approves its own consequential work**
([agent_workflow_policy.md](agent_workflow_policy.md)).

## 9. Cross-references

[verification_policy.md](verification_policy.md) ·
[loop_architecture.md](loop_architecture.md) ·
[label_policy.md](label_policy.md) ·
[verification_debt_policy.md](verification_debt_policy.md)
