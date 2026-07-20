# Label Policy

The controlled vocabulary for describing results. Labels shape intent, so they
are governed. This complements the *confidence* labels in
[verification_policy.md](verification_policy.md): confidence says *how sure we
are*; result labels say *what we observed*.

## 1. Forbidden vocabulary

Do **not** use these as labels, field names, enum values, identifiers, file
names, or report terms anywhere in the playbook or downstream systems:

> **Buy · Sell · Trade · Order · Execute · Fill · Entry · Exit · Recommendation ·
> Position (as an action) · Long/Short (as a directive)**

These imply directives or actions. They are permitted **only** inside
safety-policy negations (e.g., "this system does not place orders") or inside a
schema `description` that explicitly forbids them. See
[safety_policy.md](safety_policy.md).

## 2. Approved result vocabulary (canonical)

The canonical labels are **machine-readable `lower_snake_case` strings** and are
the single source of truth shared with code and stored data. They match the
`decision_label` / `allowed_decision_label` / `reviewer_decision` enums in the
[../schemas/](../schemas/) **exactly** — change them only by editing this table
and the schema enums together. The display name is an **optional** human-readable
rendering with no authority of its own.

| Canonical label (use this) | Optional display name | Meaning (research framing) |
| --- | --- | --- |
| `reject` | Reject | Ruled out of research consideration; does not meet criteria. |
| `watchlist` | Watchlist | Notable; monitor, but not yet a research candidate. |
| `trigger_ready_research_candidate` | Trigger-Ready Research Candidate | Meets the system's criteria; ready for closer **research** (never action). |
| `needs_human_review` | Needs Human Review | Requires human adjudication before reliance (conflict, low confidence, near a boundary). |
| `paper_candidate` | Paper Candidate | Eligible for paper / simulated **research study only** — never live execution. |
| `research_only` | Research Only | Retained purely for research / learning; no further triage implied. |
| `validation_pending` | Validation Pending | Surfaced, but verification is incomplete; awaiting validation. |

These seven are the complete approved set. Do **not** introduce a new label
without updating this table **and** the schema enums in the same change.
Confidence / validation state is a *separate* axis — see
[verification_policy.md](verification_policy.md).

## 3. Per-system framing (research-only)

| System | Example approved framing | Never |
| --- | --- | --- |
| eBay Scanner | `watchlist`, `trigger_ready_research_candidate` | "buy this listing" |
| Minervini Screener | `trigger_ready_research_candidate`, `watchlist`, `needs_human_review` | "buy/sell signal" |
| Polymarket Intel | `research_only`, `needs_human_review` | "place order" |
| Kalshi Intel | `watchlist`, `reject`, `validation_pending` | "trade contract" |
| IBKR (future) | read-only `research_only`, `needs_human_review` | any execution label |

## 4. Naming rules

- The **canonical, machine-readable** form is the `lower_snake_case` value in §2.
  Code, schemas, and stored records use exactly those strings — nothing else.
- **Display names are optional presentation only.** They must map 1:1 to a
  canonical value, carry no authority, and are never stored or branched on.
- One concept, one canonical label. Do not invent synonyms. Adding or renaming a
  label means editing §2 and the schema enums in the same change.
- Pair a result/decision label with a confidence/validation label on every
  finding (e.g., `watchlist` / `provisional`).

## 5. Why this matters

Vocabulary is a safety control. A field named `buy_signal` invites someone — or
some future automation — to act on it. A field whose value is `watchlist` or
`research_only` describes a research state and leaves the decision with the
human. Keep the language research-only and the system stays research-only.

## 6. Playbook v2 note

v2 does **not** change this vocabulary. The seven canonical labels in §2 and the
forbidden action words in §1 are unchanged; v2's new policies (verifiers, object
memory, evaluators) assign only these canonical labels and continue to treat
buy / sell / trade / order / entry / exit / recommendation as forbidden except in
safety negations, forbidden-label examples, or clearly qualified domain phrases.

## 7. Cross-references

[safety_policy.md](safety_policy.md) · [verification_policy.md](verification_policy.md)
· [report_policy.md](report_policy.md) · [architecture.md](architecture.md)
