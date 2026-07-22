# VD-001 Clean-Room Verification Protocol

Status: **OWNER-AUTHORIZED PHASE 3A PROTOCOL** (2026-07-22).

This protocol prepares a blind handoff for the Composite Spec v1.2 section 12
acceptance test. It does not implement the second reconstruction, attest to an
implementer's independence, close VD-001, seed the live store, or authorize
publication.

## 1. Roles and separation

- The **coordinator** prepares the frozen packet, withholds the current ADLS
  reference sequence, receives the candidate output, seals the submission, and
  runs the comparison.
- The **independent implementer** works only from the packet. They must not read
  this repository's `src/`, `tests/`, generated validation output, checker
  output, commits, or comparison results before their candidate is sealed.
- The **owner** reviews the independence attestation and technical comparison.
  Only the owner may decide that VD-001 discharge criteria are met.

The coordinator and implementer cannot be the same person or implementation
effort. A second code path written by the existing maker/checker author is not
independent for this purpose.

## 2. Frozen packet

`adls cleanroom-prepare` creates one ignored local directory with mode `0700`.
It contains only:

- the approved indicator basket, Composite Spec v1.2, and binding errata;
- this protocol and the machine-readable manifest/output/submission contracts;
- a transactionally copied ALFRED SQLite evidence snapshot;
- the provider-authored UMich historical workbook and release calendar; and
- the retrieval-day archive log carrying source provenance.

`INPUT_MANIFEST.json` records packet-relative names, byte counts, SHA-256
digests, classifications, the reconstruction window, and the explicit
historical-final assumption. It never records local absolute paths.

The packet deliberately excludes:

- `src/`, `tests/`, and repository history;
- `outputs/validation_frozen_equivalent.jsonl` and all expected month values;
- validation/checker artifacts and their reference hashes; and
- secrets, `.env` files, network credentials, reports, and live-store history.

The packet is local research evidence. The UMich workbook and release calendar
remain internal-use-only. Preparation does not authorize upload, email,
publication, or transfer to anyone not covered by the provider terms and owner
approval.

## 3. Independent output contract

The implementer emits one canonical JSON object per line under
`adls.cleanroom.frozen-month.v1`. The neutral projection includes exactly:

- canonical month and finalization date;
- the z-score, abstention, and flags for each Tier-A family;
- the five Tier-A input vintages;
- the Tier-A composite value and abstention state;
- whether the historical UMich-final assumption was applied; and
- the complete percentile/dwell band state and thresholds.

The JSONL rules are sorted object keys, compact separators, UTF-8, one LF after
every record, and decimal values rendered to six places with round-half-even.
Months must be consecutive and exactly cover the manifest window. The schema
is `docs/clean_room_frozen_month.schema.json`.

This is an acceptance projection, not a replacement canonical-store schema.
It covers the Tier-A frozen sequence and bands named by spec section 12 without
requiring the implementer to reproduce ADLS's internal record wrapper.

## 4. Blind submission sequence

1. The coordinator prepares the packet and records the manifest SHA-256.
2. The owner confirms that any transfer is permitted by the source licenses.
3. The implementer acknowledges the manifest hash and builds from the packet
   only, using independently chosen code and tests.
4. The candidate JSONL is delivered while the ADLS reference remains hidden.
5. The coordinator runs `adls cleanroom-seal`. The seal verifies the packet,
   validates canonical candidate bytes, binds the candidate SHA-256 to the
   input-manifest SHA-256, and records the clean-room attestation.
6. Only after the seal exists may the coordinator run
   `adls cleanroom-compare` against the checker-Verified local reference.

The comparator produces hashes, validation status, and value-free JSON paths
for differences. It never copies differing values into the report.

## 5. Technical acceptance and debt disposition

Technical acceptance requires all of the following:

- the input packet still matches its manifest;
- the candidate still matches its pre-disclosure seal;
- the reference hash matches a validation artifact whose checker result is
  `Verified` under `adls.checker.validation-assumption.v1`;
- both sequences cover the exact manifest window and satisfy the canonical
  output contract; and
- the candidate bytes exactly equal the canonical Tier-A projection of the
  reference.

An exact match makes VD-001 **eligible for human review**. It does not close the
debt automatically. The owner must also confirm implementer independence and
the evidence-transfer record. Any mismatch remains `Conflicting` until every
difference is adjudicated and regression-tested.

## 6. Manual commands

All timestamps are explicit canonical UTC values. Paths below are local and
git-ignored.

```sh
.venv/bin/adls cleanroom-prepare \
  --cache data/adls.sqlite \
  --umich-workbook data_archive/2026-07-21/umich_sca_table_2n_historical_2026-05.xls \
  --umich-release-calendar data_archive/2026-07-21/umich_sca_release_dates_1991_2026.pdf \
  --archive-log data_archive/2026-07-21/ARCHIVE_LOG.md \
  --start-month 2013-05 \
  --end-month 2026-03 \
  --generated-at YYYY-MM-DDTHH:MM:SSZ \
  --output-dir outputs/cleanroom_packet_2013-05_2026-03
```

After the independent output is received:

```sh
.venv/bin/adls cleanroom-seal \
  --input-manifest outputs/cleanroom_packet_2013-05_2026-03/INPUT_MANIFEST.json \
  --candidate /path/from/independent-implementer/candidate.jsonl \
  --implementation-id IMPLEMENTATION_ID \
  --generated-at YYYY-MM-DDTHH:MM:SSZ \
  --attest-clean-room \
  --artifact outputs/cleanroom_submission.json

.venv/bin/adls cleanroom-compare \
  --reference outputs/validation_frozen_equivalent.jsonl \
  --validation-artifact outputs/validation_results.json \
  --input-manifest outputs/cleanroom_packet_2013-05_2026-03/INPUT_MANIFEST.json \
  --candidate /path/from/independent-implementer/candidate.jsonl \
  --submission outputs/cleanroom_submission.json \
  --generated-at YYYY-MM-DDTHH:MM:SSZ \
  --artifact outputs/cleanroom_comparison.json
```

No command performs network access, sends files, changes the live frozen store,
or changes a verification-debt status.
