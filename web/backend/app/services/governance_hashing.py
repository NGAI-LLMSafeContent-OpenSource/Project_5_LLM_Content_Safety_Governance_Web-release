"""Canonical hashing shared by the governance skill, registry and executor seams.

A frozen governance plan is only meaningful if every producer hashes identical
inputs to identical strings: the plan fingerprint, the skill/contract digests,
the asset version, the sample content digests and the executor fingerprint all
run through this module. Keeping one implementation also keeps secrets out of
fingerprints, because callers hash explicit, reviewed dictionaries rather than
whole objects.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["canonical_digest", "canonical_hash", "canonical_text", "text_digest"]


def canonical_text(value: str) -> str:
    """Server-side normalization for any text that will be hashed.

    Line endings are the only difference that is normalized away: two samples
    that differ only by ``\\r\\n`` are the same corpus record, while any change
    to the actual characters changes the digest.
    """

    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def canonical_hash(value: Any) -> str:
    """Deterministic sorted-JSON SHA-256 hex digest, without a prefix."""

    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_digest(value: Any) -> str:
    """``canonical_hash`` with the explicit ``sha256:`` prefix used in records."""

    return f"sha256:{canonical_hash(value)}"


def text_digest(text: str) -> str:
    """``sha256:``-prefixed digest of normalized text."""

    normalized = canonical_text(text)
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"
