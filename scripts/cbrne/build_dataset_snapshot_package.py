#!/usr/bin/env python3
"""Build a formal CBRNE dataset_snapshot delivery zip (#121 / Spec #116 T5).

Usage (normalized JSONL already containing platform fields):

  python scripts/cbrne/build_dataset_snapshot_package.py \\
    --dataset-jsonl /path/to/normalized.jsonl \\
    --output /path/to/cbrne_dataset_snapshot.zip \\
    --asset-id topic2_cbrne_anomaly_seedbank_v1 \\
    --source-repo Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction \\
    --source-commit <frozen-sha> \\
    --version 1

This script never invents missing exposure_tier / evaluator_relative_difficulty
fields and never hard-codes a 12,420 count into product code.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from cbrne_package_lib import (  # noqa: E402
    CbrnePackageError,
    build_manifest,
    default_dataset_note,
    load_normalized_jsonl,
    write_package_members,
    zip_package_members,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a CBRNE dataset_snapshot delivery package"
    )
    parser.add_argument(
        "--dataset-jsonl",
        required=True,
        type=Path,
        help="Platform-normalized JSONL (required fields present)",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output zip path")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--version", default="1")
    parser.add_argument(
        "--source-repo",
        default="Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction",
    )
    parser.add_argument("--source-commit", default=None)
    parser.add_argument("--source-tag", default=None)
    parser.add_argument(
        "--original-filename",
        default=None,
        help="Recorded original filename (defaults to dataset-jsonl name)",
    )
    parser.add_argument(
        "--licence-notes",
        default=(
            "Source licences and intended uses vary across contributing datasets. "
            "Some sources are evaluation-only or carry contamination risk. "
            "Import success does not imply blanket training permission."
        ),
    )
    parser.add_argument(
        "--source-limitation",
        action="append",
        default=[],
        help="Repeatable source/use caveat (e.g. evaluation_only:FORTRESS)",
    )
    parser.add_argument(
        "--note-file",
        type=Path,
        default=None,
        help="Optional DATASET_NOTE.md override",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        help="Optional directory to keep unpacked members",
    )
    parser.add_argument("--name", default="Topic2 CBRNE anomaly seedbank")
    parser.add_argument(
        "--mark-as-current",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args(argv)

    try:
        rows = load_normalized_jsonl(args.dataset_jsonl)
        limitations = list(args.source_limitation) or [
            "mixed_source_licences",
            "no_blanket_training_permission",
            "evaluation_use_preferred_until_source_cleared",
        ]
        manifest = build_manifest(
            asset_id=args.asset_id,
            version=args.version,
            source_repo=args.source_repo,
            source_commit=args.source_commit,
            source_tag=args.source_tag,
            sample_count=len(rows),
            original_filename=args.original_filename or args.dataset_jsonl.name,
            licence_notes=args.licence_notes,
            source_limitations=limitations,
            name=args.name,
            mark_as_current=args.mark_as_current,
        )
        if args.note_file is not None:
            note_text = args.note_file.read_text(encoding="utf-8")
        else:
            note_text = default_dataset_note(
                source_repo=args.source_repo,
                source_commit=args.source_commit,
                source_tag=args.source_tag,
            )

        if args.staging_dir is not None:
            staging = args.staging_dir
            staging.mkdir(parents=True, exist_ok=True)
            cleanup = False
        else:
            staging_ctx = tempfile.TemporaryDirectory(prefix="cbrne-package-")
            staging = Path(staging_ctx.name)
            cleanup = True

        try:
            profile = write_package_members(
                staging,
                rows=rows,
                manifest=manifest,
                note_text=note_text,
            )
            hashes = zip_package_members(staging, args.output)
        finally:
            if cleanup:
                staging_ctx.cleanup()
    except CbrnePackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    summary = {
        "output": str(args.output.resolve()),
        "asset_id": args.asset_id,
        "sample_count": profile["sample_count"],
        "unique_id_count": profile["unique_id_count"],
        "label_counts": profile["label_counts"],
        "cbrne_category_counts": profile["cbrne_category_counts"],
        "source_counts": profile["source_counts"],
        "hashes": hashes,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
