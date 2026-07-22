# Lessons — ADLS

> Append durable insights a future session would be worse off not knowing.
> Prefer adding a dated note over rewriting history. Not executable automation.

## Format

```text
### YYYY-MM-DD — Short title
**Context:** what we were doing.
**Lesson:** what we learned.
**Apply:** how to act on it next time.
```

## Workflow lessons

### 2026-07-19 — Born from the playbook; library map exists

**Context:** ADLS bootstrapped from the Decision Systems Playbook templates in
the same session that (a) adopted the playbook philosophy into the owner's
global Claude setup and (b) indexed the owner's 20-book AI/ML library against
playbook doctrine.
**Lesson:** Two reference docs predate this repo's first commit:
`docs/reference_library_adls.md` (ADLS-slanted) and the full map in
`~/Projects/decision_systems_playbook/docs/reference_library.md`.
**Apply:** Check the library map before re-deriving methodology (regime
detection, calibration, leakage discipline) from scratch.

## Safety lessons

### 2026-07-19 — Macro revisions are a lookahead trap

**Context:** Defining the MVP validation protocol for a leading-indicator claim.
**Lesson:** Economic series get revised; validating a "leading" relationship on
revised (current-vintage) data silently uses information that did not exist at
decision time — the macro-data form of lookahead bias.
**Apply:** All historical validation uses as-of/vintage data (e.g., ALFRED-style
vintages), and every series' revision behavior is documented before it enters
the composite.

## Project-specific lessons

### 2026-07-21 — Provider missing sentinels are abstentions, not corruption

**Context:** The first live Slice 6 outcome smoke loaded latest-vintage PCE
histories after the missing ALFRED series were backfilled.
**Lesson:** ALFRED legitimately carries `.` before a series begins. Treating the
sentinel as malformed numeric data made an otherwise valid common-vintage
snapshot fail; silently dropping the affected score origins would have violated
§14's score-every-point rule.
**Apply:** Aggregate provider missing sentinels as source warnings, omit them
from level histories, and let each dependent outcome/score row abstain visibly.
Keep arbitrary nonnumeric text and nonpositive PCE levels as hard errors.

### 2026-07-21 — Unpinned validation choices must stop before data access

**Context:** Errata item 5 deliberately left AR/VAR lags and the forecast-to-
event mapping open until Slice 6.
**Lesson:** A default selected after reading outcomes is indistinguishable from
researcher degrees of freedom, even when the code is deterministic.
**Apply:** Encode the complete proposal and fixture-test it, but keep the
real-data CLI fail-closed until the owner approves the exact pin. Record every
tail/model/source gap as an abstention row rather than deleting the origin.

### 2026-07-21 — Defect seeds need discriminating fixtures

**Context:** Slice 5 first seeded sample variance (`ddof=1`) into the checker,
but the synthetic episode's five family z-scores were all capped at ±3 under
both population and sample variance.
**Lesson:** A seeded defect is not demonstrated merely because the test toggles
a rule. The fixture must put the affected calculation away from clipping,
rounding ties, abstention, or another invariant that can mask the mutation.
**Apply:** Require each seeded-defect test to assert a concrete field-level
difference in addition to the `Conflicting` label. Noncanonical checker rules
can never return `Verified`, even when a mutation happens to be observationally
equivalent for one fixture.

### 2026-07-21 — Append-only requires replay validation and one locked transaction

**Context:** Slice 4's first frozen-store writer refused a sequential duplicate,
but concurrent callers could both validate an empty store and append the same
month. Persisted vintage and source fields were trusted because the writer had
validated them once.
**Lesson:** Immutability is a read-time property as well as a write-time one.
Validation, duplicate detection, append, and fsync must share one lock; every
replay must recheck dates, source bytes/hash, redaction, family values, and
composite arithmetic before a prior value can influence a new band. Calendar
mode must also be inferred, not left to a caller-controlled default.
**Apply:** Test simultaneous writers and independently corrupted canonical
lines, including future observation metadata and malformed dates. Keep the
source assembly embedded in canonical-safe form so a frozen line can prove its
own internal consistency while git history supplies external tamper evidence.

### 2026-07-21 — A transformed licensed level can still be the raw level

**Context:** Slice 3 initially serialized UMich's inverted level alongside its
z-score. Negation changes the sign but is exactly reversible, so the supposedly
derived field still disclosed an internal-use source value.
**Lesson:** Licensing boundaries apply to reversible transforms, not only to
verbatim inputs. An explicit canonical/provisional mode is also necessary when
the same input layer can return preliminary or final releases.
**Apply:** Redact reversible internal-license transforms at the publication
boundary, retain only non-reversible scores, and pin both redaction and assembly
mode in canonical-byte tests.

### 2026-07-21 — Historical span endpoints are future knowledge

**Context:** Building the uniform point-in-time loader in Slice 2. A historical
preliminary value can be selected correctly at assembly D while its cached
episode still carries the later date on which a final value replaced it.
**Lesson:** Returning that eventual close date at D leaks a future release even
when the selected value itself is point-in-time correct.
**Apply:** Use full span endpoints internally for selection, but cap all exposed
`available_through` metadata at the requested assembly date. Test the metadata
boundary as well as the selected value.

### 2026-07-19 — Series signings must be walked through named episodes, not intuited

**Context:** Composite spec v1 signed PSAVERT as "falling = stress" and revolving
credit as "accelerating = stress." Checker walked the arithmetic through April
2020 and 2022: the composite read the anchor stress episode as ~Normal and the
affluent boom as ~High.
**Lesson:** Macro series are regime-conditional; several invert at stress onsets
(precautionary saving spikes, credit contracts, delinquency falls under
forbearance). Worse, accounting identities (S = Y − C) can wire two basket
members to mechanically cancel in exactly the target episodes.
**Apply:** Every signing must be walked through at least 2008, 2020, and 2022
before a spec leaves the maker; identity-coupled series pairs don't belong in
the same additive composite.

## A missing normalized artifact is not a missing source contract

**Context:** Slice 6 initially treated the absent expected UMich CSV filename as
if the source inputs themselves were unavailable. The repo already named the
provider table, archive layout, normalized schema, exact target series, license
boundary, and reconstructed release-calendar requirement. Following those
pointers led to the official workbook and provider-authored release calendar.
**Lesson:** Distinguish an absent derived artifact from absent source knowledge.
**Apply:** Before declaring a data blocker, trace registry -> spec -> archive
contract -> provenance log -> provider references, including ignored paths.

## A coverage watermark is not the last change date

**Context:** The first Slice 7 cache refresh succeeded for every series, but
several coverage rows did not advance because `series/vintagedates` reports only
dates on which values changed. A later report date was therefore rejected even
though the refresh had established that the unchanged value remained current.
**Lesson:** Completeness is a property of the bounded query, not the latest
event returned inside that query. Conflating the two makes quiet series appear
unavailable between releases.
**Apply:** Pin discovery and observation calls to one explicit as-of cutoff,
mark coverage through that cutoff only after both succeed, reject responses
beyond it, and regression-test an unchanged series whose last change predates
the requested point-in-time date.

## Repeated mistakes to avoid

- Signing a series from intuition without named-episode walkthroughs.
- Pre-registering a validation step against data whose vintage limitations the
  basket doc already recorded (UMich has no vintage archive; the protocol cited
  it anyway).
- Treating a missing derived filename as proof that the repo lacks the source
  contract or enough provenance to reconstruct it.
