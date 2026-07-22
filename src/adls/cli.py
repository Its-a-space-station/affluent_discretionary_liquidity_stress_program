"""Manual CLI. No scheduler exists or is authorized (spec gating).

adls fetch [--series ID ...]   backfill vintage cache from ALFRED (read-only)
adls validate                  run the local cache-only validation harness
adls report                    generate a local weekly research report
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
        coverage_cutoff = vintage_started[:10]
        try:
            vintages = client.get_vintage_dates(
                spec.series_id,
                realtime_end=coverage_cutoff,
            )
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

        latest_vintage = max(vintages)
        if latest_vintage > coverage_cutoff:
            failures += 1
            summary = (
                f"latest returned vintage {latest_vintage} exceeds fetch cutoff {coverage_cutoff}"
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
        existing_coverage = cache.complete_through_vintage(spec.series_id)
        if existing_coverage is not None and coverage_cutoff < existing_coverage:
            failures += 1
            summary = f"fetch cutoff {coverage_cutoff} predates cache coverage {existing_coverage}"
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
                spec.series_id,
                realtime_end=coverage_cutoff,
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
            cache.mark_backfilled(spec.series_id, coverage_cutoff)
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


def _cmd_validate(args: argparse.Namespace) -> int:
    from pathlib import Path

    from adls.validation.harness import run_validation
    from adls.validation.reconstruction import reconstruct_frozen_equivalent
    from adls.validation.spec import BASELINE_CONTRACT

    contract = BASELINE_CONTRACT
    if contract.pin_status != "approved":
        print(
            "ERROR baseline exact spec is still proposed; owner approval is required",
            file=sys.stderr,
        )
        return 2

    cfg = Config()
    cfg.ensure_dirs()
    archive_path = Path(args.archive)
    frozen_path = (
        Path(args.frozen_equivalent)
        if args.frozen_equivalent is not None
        else cfg.outputs_dir / "validation_frozen_equivalent.jsonl"
    )
    artifact_path = (
        Path(args.artifact)
        if args.artifact is not None
        else cfg.outputs_dir / "validation_results.json"
    )
    reconstruction = reconstruct_frozen_equivalent(
        cfg.db_path,
        archive_path,
        frozen_path,
        start_month=args.start_month,
        end_month=args.end_month,
    )
    if not reconstruction.validation.ok:
        for error in reconstruction.validation.errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    result = run_validation(
        frozen_path,
        cfg.db_path,
        archive_path,
        artifact_path,
        contract,
    )
    if not result.validation.ok:
        for error in result.validation.errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"validation artifact: {artifact_path}")
    print(f"frozen-equivalent sequence: {frozen_path}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from pathlib import Path

    from adls.reporting import run_weekly_report

    cfg = Config()
    cfg.ensure_dirs()
    assembly_path = (
        Path(args.assembly_artifact)
        if args.assembly_artifact is not None
        else cfg.outputs_dir / f"weekly_assembly_{args.assembly_date}.json"
    )
    report_path = (
        Path(args.artifact)
        if args.artifact is not None
        else cfg.outputs_dir / f"weekly_report_{args.assembly_date}.json"
    )
    markdown_path = (
        Path(args.markdown)
        if args.markdown is not None
        else cfg.outputs_dir / f"weekly_report_{args.assembly_date}.md"
    )
    result = run_weekly_report(
        cache_path=cfg.db_path,
        archive_path=Path(args.archive),
        frozen_path=(
            Path(args.frozen_store)
            if args.frozen_store is not None
            else cfg.canonical_dir / "frozen_sequence.jsonl"
        ),
        validation_artifact_path=(
            Path(args.validation_artifact)
            if args.validation_artifact is not None
            else cfg.outputs_dir / "validation_results.json"
        ),
        assembly_date=args.assembly_date,
        generated_at=args.generated_at,
        assembly_artifact_path=assembly_path,
        report_artifact_path=report_path,
        markdown_path=markdown_path,
        previous_report_path=(
            None if args.previous_artifact is None else Path(args.previous_artifact)
        ),
    )
    if not result.validation.ok:
        for error in result.validation.errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"weekly assembly: {assembly_path}")
    print(f"weekly report artifact: {report_path}")
    print(f"weekly report markdown: {markdown_path}")
    return 0


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

    validate = sub.add_parser(
        "validate",
        help="run cache-only historical validation after the owner pin",
    )
    validate.add_argument("--archive", required=True, help="normalized UMich CSV")
    validate.add_argument("--start-month", required=True, help="first canonical YYYY-MM")
    validate.add_argument("--end-month", required=True, help="last canonical YYYY-MM")
    validate.add_argument(
        "--frozen-equivalent",
        default=None,
        help="separate reconstruction artifact path",
    )
    validate.add_argument(
        "--artifact",
        default=None,
        help="validation artifact path",
    )
    validate.set_defaults(func=_cmd_validate)

    report = sub.add_parser(
        "report",
        help="generate a deterministic local weekly research report",
    )
    report.add_argument("--archive", required=True, help="normalized UMich CSV")
    report.add_argument("--assembly-date", required=True, help="scheduled assembly YYYY-MM-DD")
    report.add_argument(
        "--generated-at",
        required=True,
        help="explicit canonical UTC report timestamp",
    )
    report.add_argument(
        "--frozen-store",
        default=None,
        help="live frozen-sequence path",
    )
    report.add_argument(
        "--validation-artifact",
        default=None,
        help="Slice 6 validation artifact path",
    )
    report.add_argument(
        "--previous-artifact",
        default=None,
        help="prior weekly report artifact for change detection",
    )
    report.add_argument(
        "--assembly-artifact",
        default=None,
        help="current assembly output path",
    )
    report.add_argument("--artifact", default=None, help="canonical report artifact path")
    report.add_argument("--markdown", default=None, help="human-readable report path")
    report.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
