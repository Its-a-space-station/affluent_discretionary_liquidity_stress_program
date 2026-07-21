"""Shared dataclasses. Data problems are collected, never raised
(Trading_consultant data_contract.py shape): loaders return a
ValidationResult; only programming errors raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ObservationSpan:
    """One value-episode in ALFRED realtime semantics.

    The value for (series, observation_date) at vintage V is the span with
    realtime_start <= V <= realtime_end. Archive rows use
    realtime_start = release_date and an open realtime_end.
    """

    series_id: str
    observation_date: str  # ISO date of the reference period
    realtime_start: str
    realtime_end: str  # '9999-12-31' when currently live
    value_text: str  # vendor text verbatim ('.' preserved); parsed at compute time
    source: str  # 'alfred' | 'archive'
    source_file: str | None = None


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


@dataclass(frozen=True)
class FetchSummary:
    series_id: str
    endpoint: str  # 'observations' | 'vintagedates'
    http_status: int | None
    rows_upserted: int
    rate_limited: int
    status: str  # 'ok' | 'error'
    error_summary: str | None = None  # NEVER contains URLs or key material
