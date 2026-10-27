"""Shared Topic2 empty-run predicate for freeze + evalset export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_topic2_upstream_manifest(artifact_dir: Path) -> dict[str, Any] | None:
    """Load upstream ``manifest.json``. None = missing / unreadable / invalid JSON."""
    path = artifact_dir / "manifest.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def is_topic2_empty_run(
    manifest: dict[str, Any] | None,
    *,
    dynbench_path: Path | None,
) -> bool:
    """True only when upstream explicitly reports dynbench_count=0 and no sample rows.

    Fail closed for missing count, non-int count, bad/missing manifest, or
    a non-empty dynbench.jsonl on disk.
    """
    if not isinstance(manifest, dict):
        return False
    count = manifest.get("dynbench_count")
    if not (isinstance(count, int) and not isinstance(count, bool) and count == 0):
        return False
    if dynbench_path is None or not dynbench_path.is_file():
        return True
    return _jsonl_nonempty_line_count(dynbench_path) == 0


def resolve_topic2_dynbench_path(artifact_dir: Path) -> Path | None:
    for path in (
        artifact_dir / "dynbench.jsonl",
        artifact_dir / "raw" / "dynbench.jsonl",
    ):
        if path.is_file():
            return path
    return None


def _jsonl_nonempty_line_count(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return -1
