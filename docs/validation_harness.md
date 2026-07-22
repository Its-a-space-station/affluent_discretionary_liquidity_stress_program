# Slice 6 validation harness

Status: **implemented and real-data executed under the approved exact pin**.
The harness is research-only and cache-only. It cannot use a network client,
schedule itself, publish a result, or alter `canonical/frozen_sequence.jsonl`.

## Pipeline

1. `adls.validation.reconstruction` opens one read-only SQLite transaction and
   one validated normalized archive. It evaluates every weekly assembly from
   the requested start through end month and writes a separate
   frozen-equivalent JSONL artifact.
2. Historical UMich finals are available only under the pre-registered
   unrevised-final/reconstructed-release-calendar assumption. Every affected
   assembly carries `validation_assumption:umich_unrevised_final`; the ordinary
   checker rejects it, while the checker's explicit validation-assumption mode
   independently recomputes it. Debt remains open as VD-002.
3. The two real-PCE components are read from one latest common cached vintage.
   Each component is independently detrended in log space over the prior eight
   completed quarters; their percentage gaps are averaged. Chained-dollar
   levels are never added.
4. Every frozen month is retained as a score row. Burn-in, source, model, and
   outcome gaps become explicit abstentions. Signal episodes are counted at
   onset; evaluable and unevaluable episode counts remain separate.
5. The artifact includes the primary lead-rate table, seasonal-naive/MASE,
   fixed-AR, and small-VAR controls, recession/expansion and turning/trend
   regime tables with equal-weight macro summaries, calibration counts, the
   joint circular-block null, baseline-floor decisions, and the binding power
   statement.

## Approved exact baseline pin

The owner approved the following exact pin on 2026-07-21, before the first
real-data validation run:

- monthly target: frozen Tier-A composite;
- seasonal naive: `m=12`;
- AR: 12 fixed lags, intercept, expanding complete suffix;
- VAR: one fixed lag over the three Tier-A family z-score series, intercept,
  expanding complete suffix;
- minimum history: 36 complete months; recursive horizon: six months;
- baseline signal: at least two consecutive forecast months at or above the
  origin's frozen p70 threshold;
- outcome mapping: the same event in either of the next two calendar quarters;
- permutation: 10,000 seeded trials (`20260719`), joint 12-month circular
  blocks, with every donor month more than 12 months from its target;
- turning-point context: within six months of a static NBER peak or trough;
- outcome vintage: latest common cached vintage of both PCE components.

The AR/VAR implementation has no runtime numerical dependency. A one-time
offline comparison against `statsmodels==0.14.5` is pinned under
`tests/fixtures/validation/`; maximum absolute forecast differences were below
`1.7e-13` (AR) and `4.9e-15` (VAR).

## First real-data result

The local ignored SQLite cache covers all nine ALFRED series and passes
integrity/overlap checks. The internal-use Table 2n workbook was normalized
against UMich's provider-authored 1991-2026 final-release calendar into 425
monthly final rows. Raw and normalized values remain ignored; raw or reversibly
transformed levels must not enter committed artifacts or externally usable
reports.

The approved run spans 2013-05 through 2026-03 (155 canonical months, bounded
by common cache coverage). Repeating the run produced identical bytes. The
assumption-mode checker returned `Verified` with 310/310 checks; ordinary mode
returned `Conflicting`, as required. Every record is assumption-flagged, no
record abstains, and the licensed transformed field is redacted throughout.

The primary signal produced four evaluable episodes and two hits (50%). It beat
seasonal-naive (25%) and VAR(1) (38.4615%) but not AR(12) (60%). Therefore the
approved baseline floor invokes the binding `coincident_monitor` failure clause.
Calibration is non-monotonic. The 10,000-trial joint permutation completed with
no abstentions and met the 15-percentage-point ROPE, but the result remains
descriptive and does not authorize a leading claim.

The frozen-equivalent and validation artifact SHA-256 values are respectively
`9737d722168e4916312f197b7fe8bfb2c1a61ee6a359b99a1e61dab1e7e49265` and
`a6939894a185970a743bbbe9ed657ad8070343d7507be4b26406cf8fc28f79af`.

Both generated files remain under ignored `outputs/` by default. Promotion of
the frozen-equivalent JSONL into the live store still requires a separate owner
decision; no code path performs that promotion.
