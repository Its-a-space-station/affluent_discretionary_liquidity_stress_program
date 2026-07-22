"""Manual CLI. No scheduler exists or is authorized (spec gating).

adls fetch [--series ID ...]   backfill vintage cache from ALFRED (read-only)
adls validate                  run the local cache-only validation harness
adls report                    generate a local weekly research report
adls cleanroom-prepare         freeze a reference-free VD-001 evidence packet
adls cleanroom-seal            seal an independent candidate before disclosure
adls cleanroom-compare         compare a sealed candidate after disclosure
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


def _cmd_cleanroom_prepare(args: argparse.Namespace) -> int:
    from pathlib import Path

    from adls.cleanroom import CleanRoomError, PacketSources, prepare_packet

    sources = PacketSources(
        cache_path=Path(args.cache),
        umich_workbook_path=Path(args.umich_workbook),
        umich_release_calendar_path=Path(args.umich_release_calendar),
        archive_log_path=Path(args.archive_log),
        indicator_basket_path=Path(args.indicator_basket),
        composite_spec_path=Path(args.composite_spec),
        spec_errata_path=Path(args.spec_errata),
        protocol_path=Path(args.protocol),
        frozen_month_contract_path=Path(args.frozen_month_contract),
        input_manifest_contract_path=Path(args.input_manifest_contract),
        submission_contract_path=Path(args.submission_contract),
    )
    try:
        result = prepare_packet(
            sources,
            Path(args.output_dir),
            start_month=args.start_month,
            end_month=args.end_month,
            generated_at=args.generated_at,
        )
    except (CleanRoomError, OSError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"clean-room packet: {result.packet_path}")
    print(f"input manifest: {result.manifest_path}")
    print(f"input manifest sha256: {result.manifest_sha256}")
    return 0


def _cmd_cleanroom_seal(args: argparse.Namespace) -> int:
    from pathlib import Path

    from adls.cleanroom import CleanRoomError, seal_submission

    try:
        result = seal_submission(
            input_manifest_path=Path(args.input_manifest),
            candidate_path=Path(args.candidate),
            implementation_id=args.implementation_id,
            generated_at=args.generated_at,
            artifact_path=Path(args.artifact),
            attest_clean_room=args.attest_clean_room,
        )
    except (CleanRoomError, OSError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"sealed submission: {result.artifact_path}")
    print(f"sealed submission sha256: {result.sha256}")
    return 0


def _cmd_cleanroom_compare(args: argparse.Namespace) -> int:
    from pathlib import Path

    from adls.cleanroom import CleanRoomError, compare_submission

    try:
        result = compare_submission(
            reference_path=Path(args.reference),
            validation_artifact_path=Path(args.validation_artifact),
            input_manifest_path=Path(args.input_manifest),
            candidate_path=Path(args.candidate),
            submission_path=Path(args.submission),
            generated_at=args.generated_at,
            artifact_path=Path(args.artifact),
        )
    except (CleanRoomError, OSError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(f"clean-room comparison: {result.artifact_path}")
    print(f"comparison verdict: {result.verdict}")
    return 0 if result.exact_match else 1


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

    cleanroom_prepare = sub.add_parser(
        "cleanroom-prepare",
        help="freeze a local reference-free VD-001 clean-room packet",
    )
    cleanroom_prepare.add_argument("--cache", required=True, help="ALFRED SQLite cache")
    cleanroom_prepare.add_argument(
        "--umich-workbook",
        required=True,
        help="provider-authored historical Table 2n workbook",
    )
    cleanroom_prepare.add_argument(
        "--umich-release-calendar",
        required=True,
        help="provider-authored UMich release calendar PDF",
    )
    cleanroom_prepare.add_argument(
        "--archive-log",
        required=True,
        help="retrieval-day ARCHIVE_LOG.md",
    )
    cleanroom_prepare.add_argument("--start-month", required=True, help="first YYYY-MM")
    cleanroom_prepare.add_argument("--end-month", required=True, help="last YYYY-MM")
    cleanroom_prepare.add_argument(
        "--generated-at",
        required=True,
        help="explicit canonical UTC packet timestamp",
    )
    cleanroom_prepare.add_argument(
        "--output-dir",
        required=True,
        help="new ignored local packet directory",
    )
    cleanroom_prepare.add_argument(
        "--indicator-basket",
        default="docs/indicator_basket_proposal.md",
        help=argparse.SUPPRESS,
    )
    cleanroom_prepare.add_argument(
        "--composite-spec",
        default="docs/composite_spec_v1.md",
        help=argparse.SUPPRESS,
    )
    cleanroom_prepare.add_argument(
        "--spec-errata",
        default="canonical/spec_errata.md",
        help=argparse.SUPPRESS,
    )
    cleanroom_prepare.add_argument(
        "--protocol",
        default="docs/clean_room_verification.md",
        help=argparse.SUPPRESS,
    )
    cleanroom_prepare.add_argument(
        "--frozen-month-contract",
        default="docs/clean_room_frozen_month.schema.json",
        help=argparse.SUPPRESS,
    )
    cleanroom_prepare.add_argument(
        "--input-manifest-contract",
        default="docs/clean_room_input_manifest.schema.json",
        help=argparse.SUPPRESS,
    )
    cleanroom_prepare.add_argument(
        "--submission-contract",
        default="docs/clean_room_submission.schema.json",
        help=argparse.SUPPRESS,
    )
    cleanroom_prepare.set_defaults(func=_cmd_cleanroom_prepare)

    cleanroom_seal = sub.add_parser(
        "cleanroom-seal",
        help="seal an independent candidate before reference disclosure",
    )
    cleanroom_seal.add_argument("--input-manifest", required=True)
    cleanroom_seal.add_argument("--candidate", required=True)
    cleanroom_seal.add_argument("--implementation-id", required=True)
    cleanroom_seal.add_argument("--generated-at", required=True)
    cleanroom_seal.add_argument("--artifact", required=True)
    cleanroom_seal.add_argument(
        "--attest-clean-room",
        action="store_true",
        required=True,
        help="attest packet-only implementation before sealing",
    )
    cleanroom_seal.set_defaults(func=_cmd_cleanroom_seal)

    cleanroom_compare = sub.add_parser(
        "cleanroom-compare",
        help="compare a sealed candidate after reference disclosure",
    )
    cleanroom_compare.add_argument("--reference", required=True)
    cleanroom_compare.add_argument("--validation-artifact", required=True)
    cleanroom_compare.add_argument("--input-manifest", required=True)
    cleanroom_compare.add_argument("--candidate", required=True)
    cleanroom_compare.add_argument("--submission", required=True)
    cleanroom_compare.add_argument("--generated-at", required=True)
    cleanroom_compare.add_argument("--artifact", required=True)
    cleanroom_compare.set_defaults(func=_cmd_cleanroom_compare)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
