#!/usr/bin/env python3
"""Verify a CBRNE dataset_snapshot delivery zip and print computed stats (#121)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from cbrne_package_lib import CbrnePackageError, verify_package  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify CBRNE dataset_snapshot package integrity and stats"
    )
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument(
        "--expect-count",
        type=int,
        default=None,
        help="Optional expected sample_count (e.g. 12420 when full freeze is available)",
    )
    args = parser.parse_args(argv)

    try:
        report = verify_package(args.package)
    except CbrnePackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.expect_count is not None and report["sample_count"] != args.expect_count:
        print(
            "ERROR: sample_count mismatch: "
            f"expected {args.expect_count}, got {report['sample_count']}",
            file=sys.stderr,
        )
        return 3

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
