# data_archive/ — as-of self-archive for no-vintage sources

Approved by owner 2026-07-19. Purpose: several approved sources publish no
real-time vintage archive, so ADLS keeps its own. **A source snapshot we did
not archive on release day can never be as-of validated** (see
`docs/reference_library_adls.md`, problem 2).

Everything in this directory except this README is **git-ignored** (local
research data, never committed). This README documents the routine and is
committed.

## Layout

```
data_archive/YYYY-MM-DD/          # retrieval date (not reference-period date)
  ARCHIVE_LOG.md                  # URL, timestamp, bytes, SHA-256, response metadata
  <source>_<name>.<ext>           # the raw files, unmodified
```

Never overwrite a prior day's directory. The raw file is the evidence record;
transformations happen elsewhere.

Every successful log records the requested and effective URL, retrieval time,
byte count, SHA-256, HTTP status, and available server `Last-Modified` value.
Incorrect or incomplete pulls are marked invalid in place but retained; a
repair goes in a new retrieval-date directory.

## Weekly routine (manual until a read-only adapter is authorized)

Suggested slot: Friday afternoon (after the H.8 release lands).

| Source | What to grab | Where | Notes |
|---|---|---|---|
| ICI weekly MMF | `mm_summary_data_<yr>.xls` | ici.org/research/stats/mmf | **Scriptable** (works via curl); page holds only ~20 weeks — the one that decays |
| UMich SCA | Table 2n (income terciles) xls | data.sca.isr.umich.edu/tables.php | Manual (JS page). **License: internal use only, never redistribute** |
| FINRA margin | margin statistics Excel | finra.org → margin-statistics | Manual (no stable link); monthly is enough (3rd week) |
| NY Fed EGI | income-quartile delinquency XLSX | newyorkfed.org → equitable-growth-indicators | Manual; monthly schedule (3rd business day after last Friday) |
| JPMC Pulse / BofA Checkpoint | release PDFs | jpmorganchase.com/institute · institute.bankofamerica.com | Manual browser save; irregular/monthly cadence |

FRED/ALFRED core-basket series need **no** archiving — ALFRED is the vintage
archive (that's why the core basket was restricted to vintage-bearing series).

## Normalized CSV contract (implemented in Slice 2)

Raw evidence is never edited. A normalization step writes git-ignored CSVs
under `data/normalized_archive/` with these required columns:

`series_id, observation_date, value_text, release_date, release_stage, source_file, retrieved_at`

- `load_archive_csv()` consumes one cumulative canonical history CSV, which a
  normalization job may rebuild from any number of immutable raw snapshots.
  The file may contain multiple archive-backed series.
- `retrieved_at` is the actual UTC ISO-8601 retrieval timestamp; it is not
  reconstructed from a nominal release calendar.
- `release_stage` is one of `preliminary`, `final`, `revision`, or
  `not_applicable`.
- `source_file` is a safe relative provenance path; absolute paths and parent
  traversal are invalid. Release dates cannot precede observation dates or
  follow retrieval dates for these `observed_with_lag` inputs.
- Effective availability is `max(release_date, UTC date(retrieved_at))`. A late
  download is never treated as knowable before ADLS actually archived it.
- Canonical row sequence is `(series_id, observation_date,
  effective_available_date, release_stage, retrieved_at, release_date,
  source_file)`. Unsorted or duplicate rows are errors.
- For each `(series_id, observation_date)`, value episodes are ordered by
  effective availability. A later episode closes the prior one on the previous
  calendar day. Conflicting values on the same effective date are validation
  errors, never silently resolved.
- Each series' latest successfully processed retrieval date is its declared
  archive coverage. The final known episode is bounded by that coverage date; a
  loader must refuse an assembly date beyond that series' coverage. When a new
  snapshot contains no changed value, at least one provenance-bearing row for
  that series must still retain the newer `retrieved_at` and `source_file` to
  advance coverage.
- Canonical UMich input uses `final` rows only. A `preliminary` row may appear
  only in a clearly labeled provisional nowcast.
- Historical episode close dates are used internally for selection but are
  never exposed past the requested assembly date; doing so would leak a future
  revision. `load_archive_csv()` and `PointInTimeLoader.history_at()` implement
  these rules. The committed fixture is synthetic and contains no licensed
  provider values.

## First pull — 2026-07-19

The ICI pull used an obsolete 2025-named URL, so its provenance is invalid even
though its bytes match the later current-year retrieval. The raw evidence is
preserved. Correct 2026 provenance was captured on 2026-07-21; see both dated
logs. The internal-use UMich Table 2n historical workbook and provider release
calendar were also captured on 2026-07-21 and normalized only under ignored
paths. FINRA / EGI / JPMC / BofA remain manual first-pass items.
