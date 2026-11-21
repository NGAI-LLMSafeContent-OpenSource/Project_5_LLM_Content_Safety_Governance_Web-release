#!/usr/bin/env python
"""Package a topic3 risk Benchmark CSV and its evaluation results into a delivery zip."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(_backend_root()))
    from app.services.benchmark_topic3_risk_delivery_package import (
        DEFAULT_PROVIDER,
        BenchmarkTopic3RiskDeliveryPackageError,
        build_delivery_package,
        build_evaluation_run_package,
    )

    parser = argparse.ArgumentParser(
        description=(
            "Build a Benchmark delivery package (zip) from a topic3 risk asset CSV and "
            "evaluation result directories, or an evaluation run package for appending a "
            "same-version run to an existing asset, and print a validation summary."
        )
    )
    parser.add_argument("--asset-csv", help="Benchmark asset CSV (not used with --runs-only).")
    parser.add_argument(
        "--result-dir",
        required=True,
        action="append",
        help="Evaluation result dir (the run dir or any dir containing exactly one run). Repeatable.",
    )
    parser.add_argument("--output", required=True, help="Output package path (.zip).")
    parser.add_argument(
        "--runs-only",
        action="store_true",
        help=(
            "Build an evaluation run package for POST "
            "/api/admin/benchmark/assets/{asset_id}/evaluations instead of a delivery package."
        ),
    )
    parser.add_argument(
        "--delivery-id",
        help="Delivery id. Default: <provider>-<asset id>-<content digest>.",
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help=f"Delivering provider recorded in the manifest. Default: {DEFAULT_PROVIDER}.",
    )
    parser.add_argument("--asset-id", help="Asset id. Default: the CSV filename stem.")
    parser.add_argument(
        "--asset-version", help="Evaluated-object version. Default: the asset id's _vN suffix."
    )
    parser.add_argument(
        "--generated-at",
        help="ISO 8601 timestamp (with timezone) recorded in the manifest. Default: the "
        "latest evaluated_at of the packaged runs in UTC, so repackaging the same "
        "content yields byte-identical packages.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output.")
    args = parser.parse_args(argv)

    try:
        if args.runs_only:
            result = build_evaluation_run_package(
                args.result_dir,
                args.output,
                overwrite=args.overwrite,
            )
        else:
            if not args.asset_csv:
                parser.error("--asset-csv is required unless --runs-only is set")
            result = build_delivery_package(
                args.asset_csv,
                args.result_dir,
                args.output,
                delivery_id=args.delivery_id,
                provider=args.provider,
                asset_id=args.asset_id,
                asset_version=args.asset_version,
                generated_at=args.generated_at,
                overwrite=args.overwrite,
            )
    except BenchmarkTopic3RiskDeliveryPackageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    summary_path = result.package_path.with_name(f"{result.package_path.name}.summary.txt")
    summary_path.write_text(result.summary, encoding="utf-8")
    sys.stdout.write(result.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
