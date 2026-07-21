# Report Policy

How findings reach a human. A report is the system's primary, human-facing
output — and the only thing it "does." Reports inform; they never direct.

## 1. Principles

- **Research-only.** A report describes observations and confidence. It is
  explicitly **not financial advice** and never recommends an action.
- **Evidence-bearing.** Every finding cites its sources, timestamps, applied
  criteria, and confidence label. A reader can retrace it.
- **Honest about uncertainty.** Provisional, conflicting, and stale findings are
  shown as such — never laundered into apparent certainty.
- **No forbidden vocabulary.** No Buy/Sell/Trade/Order framing; use the approved
  labels in [label_policy.md](label_policy.md).

## 2. Required disclaimer

Every report begins with, verbatim or in close paraphrase:

> **Research only. Not financial advice.** This report summarizes automated
> observations for human review. It does not recommend, initiate, or execute any
> financial action. Verify independently before making any decision.

## 3. Standard report structure

1. **Header** — system name, run/loop id, generated-at timestamp, data window.
2. **Disclaimer** — as in §2.
3. **Summary** — counts by result label and confidence label; what changed since
   last report.
4. **Findings** — each with: subject/identifier, result label, confidence label,
   key evidence, source + timestamp, and a plain-language note.
5. **Conflicts & escalations** — `Conflicting` (confidence) and
   `needs_human_review` (result) items for human adjudication, surfaced prominently.
6. **Verification debt** — what could not be verified this run, and why
   (see [verification_debt_policy.md](verification_debt_policy.md)).
7. **Operational notes** — provider health, rate-limit status, anomalies, loop
   metrics.

## 4. Labeling in reports

- Pair every finding's **result label** (what we saw) with its **confidence
  label** (how sure we are): e.g., `watchlist` / `provisional`.
- Sort or group so the highest-confidence, highest-interest items are easy to
  find, but never hide low-confidence items.

## 5. Distribution

- Reports are generated for human review. **Publishing or sending a report
  outside the local environment is an outward-facing action** and requires
  explicit, in-context approval (see [safety_policy.md](safety_policy.md)).
- Reports must not contain secrets, credentials, or personal financial account
  data. Redact identifiers that are not necessary for the research purpose.

## 6. Tone

Neutral, observational, and specific. State what was measured and how confident
we are. Avoid persuasive or directive language. The reader decides.

## 7. Phase 2 status

The weekly report generator is authorized but not implemented yet. This remains
its binding contract and a prerequisite for the reporting gate in
[promotion_policy.md](promotion_policy.md); external publication still requires
explicit approval.

## 8. Playbook v2: evidence alignment, pointers, canonical order

- **Evidence alignment** — every finding names the Evidence Records (by
  `evidence_id`) that support or contradict it
  ([evidence_representation_policy.md](evidence_representation_policy.md)).
- **Object pointers** — reference existing objects by ID / pointer, not by
  re-describing them in prose ([object_memory_policy.md](object_memory_policy.md)).
- **Canonical ordering** — a report that lists a set uses a stated canonical order,
  so output is stable and auditable.

## 9. Forecast report requirements (v2.1)

A report that includes a forecast: states point **and** uncertainty (quantiles /
intervals), calibration, and horizon degradation; declares the target support and
any impossible-value clipping; carries a **leakage-audit** note; and restates the
**advisory-only** boundary — the forecast supports review and never authorizes an
action or promotion. See
[probabilistic_forecasting_policy.md](probabilistic_forecasting_policy.md) and
[time_series_forecasting_policy.md](time_series_forecasting_policy.md).

## 10. Macro / relationship / break report requirements (v2.2)

A report using a macro stance, a dynamic relationship, or a structural break states
provenance and uncertainty, carries the **advisory-only** boundary, and — for
breaks — shows **pre / post-break** results separately with the recommended action
(continue / recalibrate / demote / freeze_autonomy / manual_review / retire). See
[macro_policy_text_policy.md](macro_policy_text_policy.md),
[dynamic_relationship_policy.md](dynamic_relationship_policy.md), and
[structural_break_policy.md](structural_break_policy.md).

## 11. Cross-references

[safety_policy.md](safety_policy.md) · [label_policy.md](label_policy.md) ·
[verification_policy.md](verification_policy.md) ·
[verification_debt_policy.md](verification_debt_policy.md) ·
[architecture.md](architecture.md)
