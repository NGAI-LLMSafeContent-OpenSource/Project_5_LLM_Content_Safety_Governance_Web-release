"""Read the reviewed Project 1 corpus-tool delivery catalog.

The catalog contains package identity and product readiness only. It never
discovers developer-local paths or treats delivered research code as a live
service.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.topic1_corpus_tools import (
    Topic1CorpusToolCatalogResult,
    Topic1CorpusToolSourceVerification,
    Topic1CorpusToolVerificationReport,
)


CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "topic1_tools" / "catalog.v1.json"
)

CATALOG_ERROR_CODE = "topic1_corpus_tool_catalog_unavailable"
CATALOG_ERROR_MESSAGE = "课题一训练语料工具目录暂时不可用，请稍后重试或联系平台管理员。"


class Topic1CorpusToolCatalogError(RuntimeError):
    """Stable, non-leaking failure raised for an invalid reviewed catalog."""

    code = CATALOG_ERROR_CODE
    public_message = CATALOG_ERROR_MESSAGE


def unavailable_topic1_corpus_tool_catalog() -> Topic1CorpusToolCatalogResult:
    return Topic1CorpusToolCatalogResult(
        available=False,
        error_code=CATALOG_ERROR_CODE,
        message=CATALOG_ERROR_MESSAGE,
        catalog_version="topic1-corpus-tools.v1",
        source_snapshot_date="",
        tools=[],
    )


def load_topic1_corpus_tool_catalog() -> Topic1CorpusToolCatalogResult:
    try:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return Topic1CorpusToolCatalogResult.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise Topic1CorpusToolCatalogError(CATALOG_ERROR_MESSAGE) from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_topic1_corpus_tool_sources(
    source_dir: Path,
) -> Topic1CorpusToolVerificationReport:
    """Verify delivered archives without exposing developer-local paths."""

    catalog = load_topic1_corpus_tool_catalog()
    results: list[Topic1CorpusToolSourceVerification] = []
    for tool in catalog.tools:
        if tool.delivery_status != "source_delivered":
            continue
        source_path = source_dir / tool.source_package
        actual_sha256 = _sha256(source_path) if source_path.is_file() else ""
        if not actual_sha256:
            status = "missing"
        elif actual_sha256 == tool.source_sha256:
            status = "verified"
        else:
            status = "hash_mismatch"
        results.append(
            Topic1CorpusToolSourceVerification(
                tool_key=tool.tool_key,
                source_package=tool.source_package,
                status=status,
                expected_sha256=tool.source_sha256,
                actual_sha256=actual_sha256,
            )
        )
    return Topic1CorpusToolVerificationReport(
        catalog_version=catalog.catalog_version,
        delivered_package_count=len(results),
        verified_package_count=sum(item.status == "verified" for item in results),
        results=results,
    )
