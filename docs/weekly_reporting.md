# Weekly Reporting

Slice 7 implements the local, manual weekly research report. It consumes only
local point-in-time evidence, informs a human, and has no scheduler, delivery,
publication, or execution path.

## Run contract

One run requires:

- a scheduled assembly date;
- an explicit canonical UTC `generated_at` timestamp;
- the local ALFRED vintage cache;
- one normalized UMich archive CSV;
- the live append-only frozen sequence; and
- the canonical Slice 6 validation artifact.

The generator snapshots the SQLite cache and all file evidence before reading
them. The maker builds one current assembly from that snapshot. The independent
checker then re-reads the snapshot through checker-owned SQL, archive parsing,
calendar rules, and arithmetic. Canonical and provisional weekly assemblies are
both supported, but the mode is inferred from the checker calendar rather than
accepted from the caller.

The run writes three ignored, local artifacts:

1. `outputs/weekly_assembly_YYYY-MM-DD.json` - exact redacted assembly bytes;
2. `outputs/weekly_report_YYYY-MM-DD.json` - canonical evidence-bearing report;
3. `outputs/weekly_report_YYYY-MM-DD.md` - human-readable report.

No artifact writes to `canonical/frozen_sequence.jsonl`. The owner selected a
cold start on 2026-07-22, so the historical frozen-equivalent validation
sequence remains separate evidence and is never copied into the live store.

## Manual command

Load the ignored `.env` without printing it, refresh cache coverage, and then
run the report with explicit dates:

```sh
set -a
source .env
set +a
.venv/bin/adls fetch
.venv/bin/adls report \
  --archive data/normalized_archive/umich_sca_table_2n_top_final_1991_2026-05.csv \
  --assembly-date YYYY-MM-DD \
  --generated-at YYYY-MM-DDTHH:MM:SSZ
```

Use `--previous-artifact` to compare findings with a prior canonical report.
Output paths may be overridden, but input and output paths must remain distinct.
Repeating a run against unchanged evidence with the same explicit timestamp
must produce identical bytes.

## Findings and labels

The report contains a current composite finding, one finding per leading
family, the Strain overlay, the live-band state, the binding historical
validation result, and the launch-condition audit. Every finding carries:

- one approved result label;
- one confidence label;
- one or more resolvable evidence IDs;
- a source timestamp; and
- a neutral note.

UMich raw and reversibly transformed levels are never included. UMich evidence
is marked internal-use-only. The Visa family cites `Visa via FRED`.

## Launch-condition audit

The audit separately records readiness for internal weekly reporting and
external publication. Internal reporting requires a checker-Verified current
assembly, an available composite, and checker-Verified validation evidence.
External readiness additionally requires all leading families, live band
history, an allowed leading claim, monotonic calibration, closed verification
debt, and separate publication approval.

The binding validation artifact generated before VD-001 owner review says:

- `monitor_status = coincident_monitor`;
- `leading_claim_allowed = false`;
- calibration is non-monotonic; and
- VD-001, VD-002, and VD-004 were open when that artifact was generated.

The owner discharged VD-001 on 2026-07-22 after accepting the exact independent
reconstruction. New validation artifacts carry only VD-002 and VD-004; the
pre-review artifact remains preserved as clean-room evidence.

Therefore external publication is not ready regardless of the current
composite reading. The report remains local and research-only.

## Coverage watermark

FRED's `series/vintagedates` endpoint returns dates when values changed; it
does not return every date on which the unchanged series was knowable. FRED
also permits observations to be requested at an arbitrary point-in-time
vintage. See the official
[vintage-date documentation](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html)
and
[observation documentation](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).

Accordingly, `adls fetch` pins both endpoint calls to one explicit UTC fetch-date
cutoff. It marks a series complete through that cutoff only after both calls
succeed. The coverage watermark is not the last date on which the series
changed. Existing coverage never regresses, and a provider response containing
a vintage later than the requested cutoff is rejected.

## First local run

The first report used the 2026-07-17 canonical assembly and a cache complete
through 2026-07-22. The independent checker returned `Verified`. Three leading
families were available; UMich correctly abstained because the historical file
was retrieved after the assembly date. The composite renormalized over the
three available families. The cold live store had no published band. Internal
weekly reporting was ready with those caveats; external publication was not.
