"""Manual CLI. No scheduler exists or is authorized (spec gating).

adls fetch [--series ID ...]   backfill vintage cache from ALFRED (read-only)
"""

from __future__ import annotations

import argparse
import sys

from adls.config import Config
from adls.contracts import FetchSummary, ObservationSpan
from adls.registry import alfred_series, by_id


def _cmd_fetch(args: argparse.Namespace) -> int:
    from adls.alfred.cache import VintageCache, _iso_now
    from adls.alfred.client import AlfredClient, AlfredClientError

    cfg = Config()
    cfg.validate_for_fetch()
    cfg.ensure_dirs()
    cache = VintageCache(cfg.db_path)
    cache.initialize()
    client = AlfredClient(cfg.fred_api_key)

    specs = [by_id(s) for s in args.series] if args.series else list(alfred_series())
    failures = 0
    for spec in specs:
        started = _iso_now()
        try:
            vintages = client.get_vintage_dates(spec.series_id)
            cache.upsert_vintage_dates(spec.series_id, vintages)
            observations = client.get_observations(spec.series_id)
            n = cache.upsert_spans(
                ObservationSpan(
                    series_id=spec.series_id,
                    observation_date=o.observation_date,
                    realtime_start=o.realtime_start,
                    realtime_end=o.realtime_end,
                    value_text=o.value_text,
                    source="alfred",
                )
                for o in observations
            )
            if vintages:
                cache.mark_backfilled(spec.series_id, vintages[-1])
            cache.record_fetch_run(
                FetchSummary(spec.series_id, "observations", 200, n, 0, "ok"),
                started,
            )
            print(f"{spec.series_id}: {len(vintages)} vintages, {n} spans upserted")
        except AlfredClientError as exc:  # message is URL-free by construction
            failures += 1
            cache.record_fetch_run(
                FetchSummary(spec.series_id, "observations", None, 0, 0,
                             "error", str(exc)),
                started,
            )
            print(f"{spec.series_id}: ERROR {exc}", file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adls",
        description="ADLS research-only pipeline (informs a human; never acts)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="backfill the ALFRED vintage cache")
    fetch.add_argument("--series", nargs="*", default=None,
                       help="series IDs (default: all ALFRED-source series)")
    fetch.set_defaults(func=_cmd_fetch)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
