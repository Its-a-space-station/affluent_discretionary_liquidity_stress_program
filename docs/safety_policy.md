# Safety Policy

The hard constraints. These are not guidelines — they are boundaries. Every
system, document, and session in this playbook operates inside them. When any
other document and this one disagree, this one wins.

## 1. Research-only mandate

Every system built from this playbook is **research and analysis only**. Its
outputs inform a human. They never constitute, trigger, or substitute for a
financial decision.

**These systems do not place orders. These systems do not buy, sell, trade, or
execute. These systems do not move funds or change positions.** (These are the
only sentences in the playbook where those action verbs are used — as explicit
negations of capability.)

## 2. No autonomous financial action

- No automated order placement, cancellation, or modification.
- No fund transfers, withdrawals, deposits, or allocation changes.
- No position sizing that is executed rather than merely described for research.
- No "paper" or "test" order that hits a live or simulated brokerage endpoint
  without a separate, explicit, future authorization phase.
- No scheduled or looped process may take any of the above actions; loops
  produce findings and reports only. See [loop_architecture.md](loop_architecture.md).

## 3. Human-in-the-loop for anything irreversible or outward-facing

A human reviews and decides. Claude Code surfaces options and evidence. Anything
hard to reverse — sending a message, publishing a report externally, contacting a
provider, or (later) any brokerage interaction — requires explicit, in-context
approval. Approval for one action does not extend to the next.

## 4. Secrets and sensitive data

- No credentials, API keys, tokens, account numbers, or personal financial data
  in any repository, commit, log, or report.
- Secrets are supplied at runtime via environment variables / local-only config
  that is git-ignored (see [../.gitignore](../.gitignore)).
- Never echo or print a secret. Never include one in an error message or report.

## 5. Provider and venue respect

- Honor each provider's terms of service and rate limits. See
  [provider_strategy.md](provider_strategy.md).
- No scraping that violates terms, no detection-evasion, no circumventing access
  controls. If data requires authorization we do not have, we do not take it.

## 6. Language and labeling

- Use research-only language throughout. See [label_policy.md](label_policy.md).
- Avoid Buy/Sell/Trade/Order as labels, identifiers, or report terms. They are
  permitted **only** in safety-policy negations like those in §1.
- Every report carries a research disclaimer and is explicitly **not financial
  advice**. See [report_policy.md](report_policy.md).

## 7. The IBKR / broker boundary

A broker connection, if ever built, is **read-only market and account data**
only, and only after a separate authorization phase with its own gates (see
[broker_strategy.md](broker_strategy.md) and
[promotion_policy.md](promotion_policy.md)). It is never wired to an execution
path. The default and current state is: no broker integration exists.

## 8. Fail safe

When uncertain whether something crosses a boundary, **stop and ask**. The safe
default is to do less, surface the question, and let the human decide. A missed
opportunity is recoverable; an unauthorized financial action may not be.

## 9. Precedence

Precedence of authority: **Safety Policy → CLAUDE.md → all other docs**. No blueprint,
template, or convenience overrides this file.

## 10. Playbook v2: passive by default

v2 restates this boundary as a **passive vs. active** distinction: all projects
are **passive** (observe, classify, report, audit), and active capability
(mutating money, credentials, accounts, listings, orders, config, or experiments)
requires a separate approval gate — never a side effect of adding an agent, tool,
or API. An API existing is not authorization to call it. See
[passive_active_policy.md](passive_active_policy.md). v2 adds reliability and
verification, **not autonomy**; every prohibition in this file stands unchanged.

## 11. Forecast-authority boundary (v2.1)

A forecast is an advisory estimate with uncertainty; it never becomes an action.
Forecasting modules may produce estimates, uncertainty bands, and comparison
reports, support Belief Cards, add manual-review reasons, lower confidence, and
raise audit flags. They may **not** place trades, create orders, buy / sell / bid /
offer, send messages, mutate broker / wallet / exchange state, promote strategies,
override contract text or resolution-source ambiguity, clear manual review, raise
confidence above the weakest-link evidence, or authorize live APIs or credentials.
See [time_series_forecasting_policy.md](time_series_forecasting_policy.md).

## 12. Macro / relationship / break authority boundary (v2.2)

Macro-policy text (regime signals), dynamic relationships, and structural-break
detection are **advisory**: they may raise a `risk_flag`, recommend `abstain`,
lower confidence, trigger manual review, or freeze / demote autonomy. They may
**not** place trades, create orders, buy / sell / bid / offer, take broker /
wallet / exchange action, schedule operational consequences, use credentials, write
a promotion state, bypass human approval, or override project-specific gates. Market
price is an input, not truth. See
[macro_policy_text_policy.md](macro_policy_text_policy.md),
[dynamic_relationship_policy.md](dynamic_relationship_policy.md), and
[structural_break_policy.md](structural_break_policy.md).
