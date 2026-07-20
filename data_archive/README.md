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
  ARCHIVE_LOG.md                  # what was pulled, exact URL, timestamp, bytes
  <source>_<name>.<ext>           # the raw files, unmodified
```

Never overwrite a prior day's directory. The raw file is the evidence record;
transformations happen elsewhere.

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

## First pull — 2026-07-19

ICI MMF secured (the time-sensitive one). FINRA / UMich / EGI / JPMC / BofA
logged as manual for the first weekly pass. See `2026-07-19/ARCHIVE_LOG.md`.
