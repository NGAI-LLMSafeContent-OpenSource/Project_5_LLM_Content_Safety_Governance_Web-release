#!/usr/bin/env python3
"""Map Topic2 ``seeds_L1-1_new.jsonl`` rows onto platform dataset_snapshot fields.

The upstream freeze (``bfa54ca``, ``data/seedbank/seeds_L1-1_new.jsonl``) already
has ``id``, ``label``, ``prompt`` and ``difficulty``. It does not have
``exposure_tier``. That value is derived from ``source_benchmark`` using
section 1.6 of ``seeds_L1-1_new_说明.md``. Unknown sources and categories fail
instead of being guessed.

This module does not hard-code a product sample count. ``NOTES_SCALE`` is the
published distribution of that one freeze, checked only when
``--check-delivery-notes`` is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from cbrne_package_lib import (  # noqa: E402
    CbrnePackageError,
    build_manifest,
    dumps_jsonl_record,
    sha256_file,
    write_package_members,
    zip_package_members,
)


# Upstream ``harm_category_L2`` values in seeds_L1-1_new.jsonl.
CATEGORY_BY_L2 = {
    "B: Biological Risk": "Biological",
    "C: Chemical Risk": "Chemical",
    "E: Explosives Risk": "Explosives",
    "R: Radiological Risk": "Radiological",
    "N: Nuclear Risk": "Nuclear",
    "R/N: Radiological and Nuclear Risk": "Radiological/Nuclear",
}

# Section 1.6: T1–T4 means whether public Guard training has seen the source.
# It is not difficulty. Names are the upstream ``source_benchmark`` strings.
# "Do-Not-Answer" and "Chinese Do-Not-Answer" are different sources.
# The note's "ROK" is stored as "ROK-FORTRESS"; "AIR-Bench" is "AIR-Bench 2024".
EXPOSURE_TIER_BY_SOURCE = {
    "Aegis 2.0": "T1",
    "SafeSci": "T2",
    "LabSafety": "T2",
    "HarmBench": "T2",
    "Do-Not-Answer": "T2",
    "OR-Bench": "T3",
    "ClearHarm": "T3",
    "XSTest": "T3",
    "StrongREJECT": "T3",
    "AIR-Bench 2024": "T3",
    "Chinese Do-Not-Answer": "T3",
    "RefusalBench": "T3",
    "ForesightSafety": "T3",
    "WMDP": "T4",
    "ChemBench": "T4",
    "LAB-Bench": "T4",
    "BioLP": "T4",
    "SPIKE": "T4",
    "NuclearQA": "T4",
    "FORTRESS": "T4",
    "ROK-FORTRESS": "T4",
    "SOSBench": "T4",
    "SciHazard": "T4",
    "RNE-Practice": "T4",
    "RNE-Synth": "T4",
}

# Published counts for the 2026-09-28 L1-1 freeze. Used only by the optional check.
NOTES_SCALE = {
    "sample_count": 12420,
    "label_counts": {"unsafe": 6568, "safe": 5852},
    "exposure_tier_counts": {"T1": 643, "T2": 2825, "T3": 1683, "T4": 7269},
    "cbrne_category_counts": {
        "Biological": 5607,
        "Chemical": 3627,
        "Explosives": 1415,
        "Radiological": 905,
        "Nuclear": 514,
        "Radiological/Nuclear": 352,
    },
}


def normalize_native_row(raw: dict[str, Any], *, line_number: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CbrnePackageError(f"line {line_number} must be a JSON object")

    sample_id = raw.get("id")
    if not isinstance(sample_id, str) or not sample_id.strip():
        raise CbrnePackageError(f"line {line_number}.id must be a non-empty string")

    label = raw.get("label")
    if label not in {"safe", "unsafe"}:
        raise CbrnePackageError(f"line {line_number}.label must be safe or unsafe")

    category_raw = raw.get("harm_category_L2")
    category = CATEGORY_BY_L2.get(category_raw)
    if category is None:
        raise CbrnePackageError(
            f"line {line_number}.harm_category_L2 is not a known L1-1 category: {category_raw!r}"
        )

    source = raw.get("source_benchmark")
    if not isinstance(source, str) or not source.strip():
        raise CbrnePackageError(f"line {line_number}.source_benchmark must be a non-empty string")
    tier = EXPOSURE_TIER_BY_SOURCE.get(source)
    if tier is None:
        raise CbrnePackageError(
            f"line {line_number}.source_benchmark has no T1–T4 rule in notes §1.6: {source!r}"
        )

    difficulty = raw.get("difficulty")
    if isinstance(difficulty, bool) or not isinstance(difficulty, int) or difficulty < 0:
        raise CbrnePackageError(
            f"line {line_number}.difficulty must be an integer >= 0"
        )

    prompt = raw.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise CbrnePackageError(f"line {line_number}.prompt must be a non-empty string")

    normalized = dict(raw)
    normalized["id"] = sample_id.strip()
    normalized["cbrne_category"] = category
    normalized["source"] = source
    normalized["exposure_tier"] = tier
    normalized["evaluator_relative_difficulty"] = difficulty
    return normalized


def normalize_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    # Split on LF only. Prompts may contain U+2028, which str.splitlines()
    # would treat as a record boundary.
    for line_number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CbrnePackageError(f"{path}:{line_number} is not valid JSON") from exc
        rows.append(normalize_native_row(raw, line_number=line_number))
    if not rows:
        raise CbrnePackageError(f"{path} contains no rows")
    return rows


def profile_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sample_count": len(rows),
        "label_counts": dict(Counter(str(row["label"]) for row in rows)),
        "cbrne_category_counts": dict(Counter(str(row["cbrne_category"]) for row in rows)),
        "exposure_tier_counts": dict(Counter(str(row["exposure_tier"]) for row in rows)),
        "source_counts": dict(Counter(str(row["source"]) for row in rows)),
    }


def assert_matches_delivery_notes(rows: list[dict[str, Any]]) -> None:
    actual = profile_counts(rows)
    for key in ("sample_count", "label_counts", "exposure_tier_counts", "cbrne_category_counts"):
        if actual[key] != NOTES_SCALE[key]:
            raise CbrnePackageError(
                f"normalized {key} does not match seeds_L1-1_new notes: "
                f"{actual[key]!r} != {NOTES_SCALE[key]!r}"
            )


def delivery_note(
    *,
    source_repo: str,
    source_commit: str,
    upstream_filename: str,
    upstream_sha256: str,
) -> str:
    return (
        "# Topic2 CBRNE anomaly seedbank — delivery note\n\n"
        "## Provenance\n\n"
        f"- Source repository: `{source_repo}`\n"
        f"- Frozen revision: `{source_commit}`\n"
        f"- Upstream file: `{upstream_filename}`\n"
        f"- Upstream SHA-256: `{upstream_sha256}`\n"
        "- Asset type: `dataset_snapshot` / `anomaly_seedbank`\n"
        "- Schema: `topic2.cbrne.anomaly_seedbank.v1`\n\n"
        "## Field mapping\n\n"
        "- `id`, `label`, and `prompt` are copied from the upstream row.\n"
        "- `cbrne_category` is mapped from `harm_category_L2` "
        "(Biological, Chemical, Explosives, Radiological, Nuclear, Radiological/Nuclear).\n"
        "- `source` is the upstream `source_benchmark` string.\n"
        "- `evaluator_relative_difficulty` is the upstream `difficulty` integer: "
        "how many of the ten Guards were wrong or null. It is not a human difficulty label.\n"
        "- `exposure_tier` is **not** a column in the upstream JSONL. "
        "It is derived from `source_benchmark` using section 1.6 of "
        "`seeds_L1-1_new_说明.md`. T1–T4 records whether public Guard training "
        "is believed to have seen that source. It is not difficulty.\n"
        "- The note's short names `ROK` and `AIR-Bench` are the upstream values "
        "`ROK-FORTRESS` and `AIR-Bench 2024`.\n"
        "- `Do-Not-Answer` is T2. `Chinese Do-Not-Answer` is T3.\n"
        "- Original upstream fields, including `harm_category_L2`, "
        "`source_benchmark`, `difficulty`, and per-Guard judgments, are kept "
        "on each row.\n\n"
        "## Licence / use caveats\n\n"
        "- Contributing sources have mixed licences and intended uses.\n"
        "- FORTRESS is evaluation-only. Several other sources carry contamination risk.\n"
        "- Successful import does **not** imply blanket training permission.\n\n"
        "## Disclosure\n\n"
        "- Sample full text is restricted CBRNE content.\n"
        "- Governance lists show masked excerpts only.\n"
        "- Full text is available only through an explicit Benchmark detail action.\n"
    )


def write_normalized_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(dumps_jsonl_record(row) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def build_zip(
    *,
    rows: list[dict[str, Any]],
    output_zip: Path,
    asset_id: str,
    version: str,
    source_repo: str,
    source_commit: str,
    original_filename: str,
    note_text: str,
    source_limitations: list[str],
) -> dict[str, Any]:
    manifest = build_manifest(
        asset_id=asset_id,
        version=version,
        source_repo=source_repo,
        source_commit=source_commit,
        source_tag=None,
        sample_count=len(rows),
        original_filename=original_filename,
        licence_notes=(
            "Source licences and intended uses vary. FORTRESS is evaluation-only. "
            "Import success does not imply blanket training permission. "
            "exposure_tier is derived from Topic2 notes section 1.6, not stored upstream."
        ),
        source_limitations=source_limitations,
        name="Topic2 CBRNE anomaly seedbank",
    )
    with tempfile.TemporaryDirectory(prefix="cbrne-package-") as staging_name:
        staging = Path(staging_name)
        profile = write_package_members(
            staging,
            rows=rows,
            manifest=manifest,
            note_text=note_text,
        )
        hashes = zip_package_members(staging, output_zip)
    return {"profile": profile, "hashes": hashes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Topic2 L1-1 CBRNE seedbank rows and optionally zip them"
    )
    parser.add_argument("--input", required=True, type=Path, help="seeds_L1-1_new.jsonl")
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=None,
        help="Write the platform-normalized JSONL here",
    )
    parser.add_argument("--output-zip", type=Path, default=None)
    parser.add_argument("--asset-id", default="topic2_cbrne_anomaly_seedbank_v1")
    parser.add_argument("--version", default="1")
    parser.add_argument(
        "--source-repo",
        default="Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction",
    )
    parser.add_argument("--source-commit", default="bfa54ca00e9fc0c03844499d66be749c942df3f8")
    parser.add_argument(
        "--check-delivery-notes",
        action="store_true",
        help="Require the published 12,420-row L1-1 distribution",
    )
    args = parser.parse_args(argv)
    if args.output_jsonl is None and args.output_zip is None:
        print("ERROR: pass --output-jsonl and/or --output-zip", file=sys.stderr)
        return 2

    try:
        rows = normalize_jsonl(args.input)
        if args.check_delivery_notes:
            assert_matches_delivery_notes(rows)
        if args.output_jsonl is not None:
            write_normalized_jsonl(args.output_jsonl, rows)
        summary: dict[str, Any] = {
            "input": str(args.input),
            "upstream_sha256": sha256_file(args.input),
            "sample_count": len(rows),
            "label_counts": dict(Counter(row["label"] for row in rows)),
            "cbrne_category_counts": dict(Counter(row["cbrne_category"] for row in rows)),
            "exposure_tier_counts": dict(Counter(row["exposure_tier"] for row in rows)),
        }
        if args.output_zip is not None:
            note = delivery_note(
                source_repo=args.source_repo,
                source_commit=args.source_commit,
                upstream_filename=args.input.name,
                upstream_sha256=summary["upstream_sha256"],
            )
            built = build_zip(
                rows=rows,
                output_zip=args.output_zip,
                asset_id=args.asset_id,
                version=args.version,
                source_repo=args.source_repo,
                source_commit=args.source_commit,
                original_filename=args.input.name,
                note_text=note,
                source_limitations=[
                    "no_blanket_training_permission",
                    "evaluation_only:FORTRESS",
                    "exposure_tier_derived_from_topic2_notes_section_1_6",
                    "mixed_source_licences",
                ],
            )
            summary["output_zip"] = str(args.output_zip.resolve())
            summary["hashes"] = built["hashes"]
        if args.output_jsonl is not None:
            summary["output_jsonl"] = str(args.output_jsonl.resolve())
    except CbrnePackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
