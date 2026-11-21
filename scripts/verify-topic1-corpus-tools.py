#!/usr/bin/env python3
"""Validate the canonical Topic 1 corpus-tool catalog and optional archives."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "web" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.topic1_corpus_tool_service import (  # noqa: E402
    Topic1CorpusToolCatalogError,
    load_topic1_corpus_tool_catalog,
    verify_topic1_corpus_tool_sources,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the reviewed Topic 1 tool catalog. Pass --source-dir to also "
            "verify delivered source archives against their recorded SHA-256 values."
        )
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing the original Topic 1 source archives.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog = load_topic1_corpus_tool_catalog()
    except Topic1CorpusToolCatalogError as exc:
        print(
            json.dumps(
                {"ok": False, "error_code": exc.code, "message": exc.public_message},
                ensure_ascii=False,
            )
        )
        return 2

    if args.source_dir is None:
        print(
            json.dumps(
                {
                    "ok": True,
                    "catalog_version": catalog.catalog_version,
                    "tool_count": len(catalog.tools),
                    "source_verification": "skipped",
                },
                ensure_ascii=False,
            )
        )
        return 0

    report = verify_topic1_corpus_tool_sources(args.source_dir)
    ok = report.verified_package_count == report.delivered_package_count
    print(
        json.dumps(
            {"ok": ok, **report.model_dump()},
            ensure_ascii=False,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
