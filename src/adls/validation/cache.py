"""Read the validation outcome at one latest common SQLite vintage."""

from __future__ import annotations

import math
import sqlite3
from datetime import date
from pathlib import Path

from adls.contracts import ValidationResult

from .models import OutcomeSourceResult, QuarterLevel

OUTCOME_SERIES = ("DRCARX1Q020SBEA", "DFSARX1Q020SBEA")


def _canonical_date(value: str) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value


def _quarter_from_observation(value: str) -> str | None:
    if not _canonical_date(value):
        return None
    parsed = date.fromisoformat(value)
    if parsed.day != 1 or parsed.month not in {1, 4, 7, 10}:
        return None
    return f"{parsed.year:04d}-Q{(parsed.month - 1) // 3 + 1}"


def load_latest_outcome_levels(
    cache_path: Path,
    *,
    vintage: str | None = None,
) -> OutcomeSourceResult:
    validation = ValidationResult()
    if vintage is not None and not _canonical_date(vintage):
        validation.error(f"invalid outcome vintage {vintage!r}")
        return OutcomeSourceResult(None, (), validation)
    if not cache_path.is_file():
        validation.error(f"vintage cache does not exist: {cache_path}")
        return OutcomeSourceResult(None, (), validation)

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{cache_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        coverage: dict[str, str] = {}
        for series_id in OUTCOME_SERIES:
            row = connection.execute(
                """
                SELECT complete_through_vintage
                FROM series_coverage
                WHERE series_id = ?
                """,
                (series_id,),
            ).fetchone()
            if row is None:
                validation.error(f"{series_id} has no declared cache coverage")
                continue
            through = str(row["complete_through_vintage"])
            if not _canonical_date(through):
                validation.error(f"{series_id} cache coverage is not an ISO date")
                continue
            coverage[series_id] = through
        if not validation.ok:
            return OutcomeSourceResult(None, (), validation)

        selected_vintage = vintage or min(coverage.values())
        for series_id, through in coverage.items():
            if selected_vintage > through:
                validation.error(
                    f"{series_id} outcome vintage {selected_vintage} exceeds coverage {through}"
                )
        if not validation.ok:
            return OutcomeSourceResult(selected_vintage, (), validation)

        components: list[tuple[str, tuple[QuarterLevel, ...]]] = []
        for series_id in OUTCOME_SERIES:
            rows = connection.execute(
                """
                SELECT series_id, observation_date, value_text, source
                FROM observation_spans
                WHERE series_id = ?
                  AND realtime_start <= ?
                  AND realtime_end >= ?
                ORDER BY observation_date, realtime_start
                """,
                (series_id, selected_vintage, selected_vintage),
            ).fetchall()
            levels: list[QuarterLevel] = []
            seen: set[str] = set()
            missing_sentinels = 0
            for row in rows:
                observation = str(row["observation_date"])
                quarter = _quarter_from_observation(observation)
                if quarter is None:
                    validation.error(
                        f"{series_id} observation {observation!r} is not a quarter start"
                    )
                    continue
                if quarter in seen:
                    validation.error(f"{series_id} has overlapping spans for {quarter}")
                    continue
                seen.add(quarter)
                if str(row["series_id"]) != series_id or str(row["source"]) != "alfred":
                    validation.error(f"{series_id} cache row has contradictory identity")
                    continue
                value_text = str(row["value_text"])
                if value_text == ".":
                    missing_sentinels += 1
                    continue
                try:
                    level = float(value_text)
                except ValueError:
                    validation.error(f"{series_id} has a nonnumeric value for {quarter}")
                    continue
                if not math.isfinite(level) or level <= 0.0:
                    validation.error(f"{series_id} has a nonpositive value for {quarter}")
                    continue
                levels.append(QuarterLevel(quarter, level))
            if missing_sentinels:
                validation.warn(
                    f"{series_id} omitted {missing_sentinels} ALFRED missing-value sentinels"
                )
            components.append((series_id, tuple(levels)))
        return OutcomeSourceResult(selected_vintage, tuple(components), validation)
    except sqlite3.Error as exc:
        validation.error(f"cannot read validation outcome snapshot: {exc}")
        return OutcomeSourceResult(None, (), validation)
    finally:
        if connection is not None:
            connection.close()
