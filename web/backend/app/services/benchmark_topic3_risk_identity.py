"""Topic3 risk Benchmark series identity and file helpers, kept free of DB imports
so the local delivery packaging tool can share them."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SERIES_ID = "topic3_risk_hierarchical_classification"

_CHUNK_SIZE = 1024 * 1024


def hash_file(path: Path) -> tuple[str, int]:
    """SHA-256 hex digest and byte size of ``path``."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def sha256_file(path: Path) -> str:
    return hash_file(path)[0]


def read_json_object(
    path: Path, display_name: str, error: type[Exception]
) -> dict[str, Any]:
    """Strict JSON object read; invalid JSON or a non-object raises ``error``."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise error(f"{display_name} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise error(f"{display_name} must contain a JSON object")
    return payload
