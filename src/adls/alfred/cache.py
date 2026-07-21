"""Durable SQLite vintage cache (span-based, mirroring ALFRED realtime
semantics). Idioms from ebay card_scanner/storage.py: schema-as-constant,
idempotent initialize(), UPSERT preserving first_fetched_at, run-audit table.

The SQLite file is cache/audit only — byte-identity applies to exported
artifacts, never this file. No URLs and no key material are ever stored.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from adls.contracts import FetchSummary, ObservationSpan

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observation_spans (
    series_id        TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    realtime_start   TEXT NOT NULL,
    realtime_end     TEXT NOT NULL,
    value_text       TEXT NOT NULL,
    source           TEXT NOT NULL,
    source_file      TEXT,
    first_fetched_at TEXT NOT NULL,
    last_fetched_at  TEXT NOT NULL,
    PRIMARY KEY (series_id, observation_date, realtime_start)
);
CREATE INDEX IF NOT EXISTS idx_spans_series_obs
    ON observation_spans (series_id, observation_date);

CREATE TABLE IF NOT EXISTS vintage_dates (
    series_id    TEXT NOT NULL,
    vintage_date TEXT NOT NULL,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (series_id, vintage_date)
);

CREATE TABLE IF NOT EXISTS series_coverage (
    series_id                TEXT PRIMARY KEY,
    complete_through_vintage TEXT,
    last_backfill_at         TEXT
);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    completed_at  TEXT,
    series_id     TEXT,
    endpoint      TEXT,
    http_status   INTEGER,
    rows_upserted INTEGER,
    rate_limited  INTEGER,
    status        TEXT,
    error_summary TEXT
);
"""


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class VintageCoverageError(LookupError):
    """Raised when a PIT lookup falls outside declared cache coverage."""


class VintageCache:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- writes -------------------------------------------------------------

    def upsert_spans(self, spans: Iterable[ObservationSpan]) -> int:
        now = _iso_now()
        count = 0
        with self._connect() as conn:
            for s in spans:
                conn.execute(
                    """
                    INSERT INTO observation_spans (
                        series_id, observation_date, realtime_start,
                        realtime_end, value_text, source, source_file,
                        first_fetched_at, last_fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (series_id, observation_date, realtime_start)
                    DO UPDATE SET
                        realtime_end   = excluded.realtime_end,
                        value_text     = excluded.value_text,
                        last_fetched_at = excluded.last_fetched_at
                    """,
                    (s.series_id, s.observation_date, s.realtime_start,
                     s.realtime_end, s.value_text, s.source, s.source_file,
                     now, now),
                )
                count += 1
        return count

    def upsert_vintage_dates(self, series_id: str, vintages: Iterable[str]) -> int:
        now = _iso_now()
        count = 0
        with self._connect() as conn:
            for v in vintages:
                conn.execute(
                    """
                    INSERT INTO vintage_dates (series_id, vintage_date, fetched_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT (series_id, vintage_date) DO NOTHING
                    """,
                    (series_id, v, now),
                )
                count += 1
        return count

    def record_fetch_run(self, summary: FetchSummary, started_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fetch_runs (
                    started_at, completed_at, series_id, endpoint, http_status,
                    rows_upserted, rate_limited, status, error_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (started_at, _iso_now(), summary.series_id, summary.endpoint,
                 summary.http_status, summary.rows_upserted,
                 summary.rate_limited, summary.status, summary.error_summary),
            )

    def mark_backfilled(self, series_id: str, through_vintage: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO series_coverage (series_id, complete_through_vintage, last_backfill_at)
                VALUES (?, ?, ?)
                ON CONFLICT (series_id) DO UPDATE SET
                    complete_through_vintage = CASE
                        WHEN series_coverage.complete_through_vintage IS NULL
                          OR excluded.complete_through_vintage
                             > series_coverage.complete_through_vintage
                        THEN excluded.complete_through_vintage
                        ELSE series_coverage.complete_through_vintage
                    END,
                    last_backfill_at = excluded.last_backfill_at
                """,
                (series_id, through_vintage, _iso_now()),
            )

    # -- reads --------------------------------------------------------------

    def vintages_for(self, series_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT vintage_date FROM vintage_dates WHERE series_id = ? "
                "ORDER BY vintage_date",
                (series_id,),
            ).fetchall()
        return [r["vintage_date"] for r in rows]

    def complete_through_vintage(self, series_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT complete_through_vintage FROM series_coverage "
                "WHERE series_id = ?",
                (series_id,),
            ).fetchone()
        return row["complete_through_vintage"] if row else None

    def series_history_at_vintage(
        self, series_id: str, vintage: str
    ) -> list[tuple[str, str]]:
        """[(observation_date, value_text)] as knowable at `vintage`."""
        complete_through = self.complete_through_vintage(series_id)
        if complete_through is None:
            raise VintageCoverageError(
                f"{series_id} has no declared coverage; cannot serve vintage {vintage}"
            )
        if vintage > complete_through:
            raise VintageCoverageError(
                f"{series_id} vintage {vintage} exceeds complete coverage "
                f"through {complete_through}"
            )
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT observation_date, value_text FROM observation_spans
                WHERE series_id = ? AND realtime_start <= ? AND realtime_end >= ?
                ORDER BY observation_date
                """,
                (series_id, vintage, vintage),
            ).fetchall()
        return [(r["observation_date"], r["value_text"]) for r in rows]

    def first_fetched_at(self, series_id: str, observation_date: str,
                         realtime_start: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT first_fetched_at FROM observation_spans
                WHERE series_id = ? AND observation_date = ? AND realtime_start = ?
                """,
                (series_id, observation_date, realtime_start),
            ).fetchone()
        return row["first_fetched_at"] if row else None
