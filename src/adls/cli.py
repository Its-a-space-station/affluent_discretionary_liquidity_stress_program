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

    try:
        specs = [by_id(s) for s in args.series] if args.series else list(alfred_series())
    except KeyError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    unsupported = [spec.series_id for spec in specs if spec.source != "alfred"]
    if unsupported:
        print(
            f"ERROR not an ALFRED series: {', '.join(unsupported)}",
            file=sys.stderr,
        )
        return 2

    cfg = Config()
    cfg.validate_for_fetch()
    cfg.ensure_dirs()
    cache = VintageCache(cfg.db_path)
    cache.initialize()
    client = AlfredClient(cfg.fred_api_key)

    failures = 0
    for spec in specs:
        vintage_started = _iso_now()
        try:
            vintages = client.get_vintage_dates(spec.series_id)
        except AlfredClientError as exc:  # message is URL-free by construction
            failures += 1
            cache.record_fetch_run(
                FetchSummary(
                    spec.series_id,
                    exc.stats.endpoint,
                    exc.stats.http_status,
                    0,
                    exc.stats.rate_limited,
                    "error",
                    str(exc),
                ),
                vintage_started,
            )
            print(f"{spec.series_id}: ERROR {exc}", file=sys.stderr)
            continue

        vintage_stats = client.last_request_stats
        if not vintages:
            failures += 1
            summary = "FRED returned no vintage dates"
            cache.record_fetch_run(
                FetchSummary(
                    spec.series_id,
                    vintage_stats.endpoint,
                    vintage_stats.http_status,
                    0,
                    vintage_stats.rate_limited,
                    "error",
                    summary,
                ),
                vintage_started,
            )
            print(f"{spec.series_id}: ERROR {summary}", file=sys.stderr)
            continue

        through_vintage = max(vintages)
        existing_coverage = cache.complete_through_vintage(spec.series_id)
        if existing_coverage is not None and through_vintage < existing_coverage:
            failures += 1
            summary = (
                f"latest returned vintage {through_vintage} predates cache coverage "
                f"{existing_coverage}"
            )
            cache.record_fetch_run(
                FetchSummary(
                    spec.series_id,
                    vintage_stats.endpoint,
                    vintage_stats.http_status,
                    0,
                    vintage_stats.rate_limited,
                    "error",
                    summary,
                ),
                vintage_started,
            )
            print(f"{spec.series_id}: ERROR {summary}", file=sys.stderr)
            continue

        vintage_count = cache.upsert_vintage_dates(spec.series_id, vintages)
        cache.record_fetch_run(
            FetchSummary(
                spec.series_id,
                vintage_stats.endpoint,
                vintage_stats.http_status,
                vintage_count,
                vintage_stats.rate_limited,
                "ok",
            ),
            vintage_started,
        )

        observation_started = _iso_now()
        try:
            observations = client.get_observations(
                spec.series_id, realtime_end=through_vintage
            )
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
            cache.mark_backfilled(spec.series_id, through_vintage)
            observation_stats = client.last_request_stats
            cache.record_fetch_run(
                FetchSummary(
                    spec.series_id,
                    observation_stats.endpoint,
                    observation_stats.http_status,
                    n,
                    observation_stats.rate_limited,
                    "ok",
                ),
                observation_started,
            )
            print(f"{spec.series_id}: {len(vintages)} vintages, {n} spans upserted")
        except AlfredClientError as exc:  # message is URL-free by construction
            failures += 1
            cache.record_fetch_run(
                FetchSummary(
                    spec.series_id,
                    exc.stats.endpoint,
                    exc.stats.http_status,
                    0,
                    exc.stats.rate_limited,
                    "error",
                    str(exc),
                ),
                observation_started,
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
    fetch.add_argument(
        "--series",
        nargs="+",
        default=None,
        help="series IDs (default: all ALFRED-source series)",
    )
    fetch.set_defaults(func=_cmd_fetch)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
