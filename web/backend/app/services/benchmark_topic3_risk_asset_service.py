from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkAsset


FINAL_FIELDS = [
    "index",
    "version",
    "culture",
    "language",
    "prompt",
    "response",
    "response_safetype",
    "risk_category",
    "risk_sub_category",
    "risk_level_id",
    "label_source",
    "response_text_original",
    "response_text_source",
    "source_index",
    "safe_type",
    "safe_mode",
    "label_reason",
]

REQUIRED_FINAL_FILES = {
    "safe": "safe_400.jsonl",
    "low": "low_400.jsonl",
    "taxonomy": "canonical_taxonomy_17x60.md",
    "qa_report": "final_qa_report.json",
    "upstream_manifest": "FINAL_MANIFEST.md",
}

SOURCE_MODE = "prerun_snapshot"
AGENT_ID = "topic3-risk-benchmark-generation"
BENCHMARK_TYPE = "risk_content_generation"


class BenchmarkTopic3RiskAssetError(RuntimeError):
    """Raised when a topic3 dynamic risk final dataset cannot be imported."""


class BenchmarkTopic3RiskAssetService:
    def _artifact_root(self) -> Path:
        return Path(get_settings().benchmark_artifact_root)

    async def import_final_dataset(
        self,
        db: AsyncSession,
        *,
        final_dir: Path | str | None = None,
        asset_id: str | None = None,
        name: str | None = None,
    ) -> BenchmarkAsset:
        settings = get_settings()
        source_dir = _resolve_final_dir(
            final_dir or settings.topic3_risk_benchmark_default_final_dir
        )
        resolved_asset_id = _clean_asset_id(asset_id) or (
            f"topic3_risk_{uuid.uuid4().hex[:12]}"
        )

        existing = await db.execute(
            select(BenchmarkAsset).where(BenchmarkAsset.asset_id == resolved_asset_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise BenchmarkTopic3RiskAssetError(
                f"asset already exists: {resolved_asset_id}"
            )

        paths = _required_paths(source_dir)
        safe_rows = _load_and_validate_jsonl(
            paths["safe"],
            expected_level="safe",
            expected_safetype="safe",
        )
        low_rows = _load_and_validate_jsonl(
            paths["low"],
            expected_level="low",
            expected_safetype="unsafe",
        )
        qa_report = _load_json_object(paths["qa_report"], "final_qa_report.json")
        qa_summary = _validate_qa_report(
            qa_report,
            safe_path=paths["safe"],
            low_path=paths["low"],
            safe_count=len(safe_rows),
            low_count=len(low_rows),
        )

        root_dir = self._artifact_root() / "prerun" / resolved_asset_id
        if root_dir.exists():
            raise BenchmarkTopic3RiskAssetError(
                f"asset directory already exists: {root_dir}"
            )
        artifacts_dir = root_dir / "artifacts"

        try:
            root_dir.mkdir(parents=True, exist_ok=False)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            for source_name in REQUIRED_FINAL_FILES.values():
                shutil.copy2(source_dir / source_name, root_dir / source_name)

            preview_rows = _preview_rows(safe_rows, low_rows)
            preview_path = root_dir / "samples_preview.jsonl"
            preview_path.write_text(
                "".join(
                    json.dumps(row, ensure_ascii=False) + "\n" for row in preview_rows
                ),
                encoding="utf-8",
            )

            category_distribution = {
                "safe": _category_distribution(safe_rows),
                "low": _category_distribution(low_rows),
            }
            manifest = _build_platform_manifest(
                asset_id=resolved_asset_id,
                name=name or "Topic3 Dynamic Risk Benchmark safe/low 400",
                source_repo=settings.topic3_risk_benchmark_source_repo,
                source_commit=settings.topic3_risk_benchmark_source_commit,
                safe_count=len(safe_rows),
                low_count=len(low_rows),
                category_distribution=category_distribution,
                qa_summary=qa_summary,
                source_dir=source_dir,
            )
            (root_dir / "manifest.platform.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            archive_path = artifacts_dir / "topic3_risk_prerun_artifacts.zip"
            _write_asset_zip(root_dir, archive_path)
            artifact_sha256 = _sha256_file(archive_path)
            manifest["checksums"] = {"artifact_zip_sha256": artifact_sha256}
            (root_dir / "manifest.platform.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            shutil.rmtree(root_dir, ignore_errors=True)
            raise

        asset = BenchmarkAsset(
            asset_id=resolved_asset_id,
            task_id=f"prerun_{resolved_asset_id[:56]}",
            source_mode=SOURCE_MODE,
            name=str(manifest["name"]),
            manifest_json=json.dumps(manifest, ensure_ascii=False),
            artifact_dir=str(root_dir),
            artifact_zip_path=str(archive_path),
            artifact_sha256=artifact_sha256,
            source_repo=str(manifest["source_repo"]),
            source_commit=str(manifest["source_commit"]),
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return asset


def _resolve_final_dir(value: str | Path | None) -> Path:
    if not value:
        raise BenchmarkTopic3RiskAssetError(
            "final_dir is required when no default topic3 risk benchmark dir is configured"
        )
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise BenchmarkTopic3RiskAssetError(f"final_dir not found: {path}")
    return path


def _clean_asset_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cleaned):
        raise BenchmarkTopic3RiskAssetError(
            "asset_id must contain only letters, numbers, '_' or '-' and be <= 64 chars"
        )
    return cleaned


def _required_paths(final_dir: Path) -> dict[str, Path]:
    paths = {
        key: final_dir / filename for key, filename in REQUIRED_FINAL_FILES.items()
    }
    missing = [path.name for path in paths.values() if not path.is_file()]
    if missing:
        raise BenchmarkTopic3RiskAssetError(
            f"final dataset is missing required files: {', '.join(sorted(missing))}"
        )
    return paths


def _load_and_validate_jsonl(
    path: Path,
    *,
    expected_level: str,
    expected_safetype: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic3RiskAssetError(
                f"{path.name}:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(row, dict):
            raise BenchmarkTopic3RiskAssetError(
                f"{path.name}:{line_number} must contain a JSON object"
            )
        _validate_row(path.name, line_number, row, expected_level, expected_safetype)
        rows.append(row)
    if not rows:
        raise BenchmarkTopic3RiskAssetError(f"{path.name} must not be empty")
    return rows


def _validate_row(
    file_name: str,
    line_number: int,
    row: dict[str, Any],
    expected_level: str,
    expected_safetype: str,
) -> None:
    keys = list(row.keys())
    if keys != FINAL_FIELDS:
        missing = [field for field in FINAL_FIELDS if field not in row]
        extra = [field for field in keys if field not in FINAL_FIELDS]
        raise BenchmarkTopic3RiskAssetError(
            f"{file_name}:{line_number} schema mismatch; missing={missing}; extra={extra}"
        )
    for field in FINAL_FIELDS:
        if field == "response_text_original":
            continue
        value = row.get(field)
        if value is None or value == "" or value == []:
            raise BenchmarkTopic3RiskAssetError(
                f"{file_name}:{line_number}.{field} must not be empty"
            )
    if row.get("risk_level_id") != expected_level:
        raise BenchmarkTopic3RiskAssetError(
            f"{file_name}:{line_number}.risk_level_id must be {expected_level}"
        )
    if row.get("response_safetype") != expected_safetype:
        raise BenchmarkTopic3RiskAssetError(
            f"{file_name}:{line_number}.response_safetype must be {expected_safetype}"
        )
    category = str(row.get("risk_category", ""))
    if not re.search(r"C(0[1-9]|1[0-7])\b", category):
        raise BenchmarkTopic3RiskAssetError(
            f"{file_name}:{line_number}.risk_category must contain C01-C17"
        )
    subcategory = str(row.get("risk_sub_category", ""))
    if "其他" in subcategory:
        raise BenchmarkTopic3RiskAssetError(
            f"{file_name}:{line_number}.risk_sub_category must not contain 其他"
        )


def _load_json_object(path: Path, display_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkTopic3RiskAssetError(f"{display_name} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BenchmarkTopic3RiskAssetError(f"{display_name} must contain a JSON object")
    return payload


def _validate_qa_report(
    report: dict[str, Any],
    *,
    safe_path: Path,
    low_path: Path,
    safe_count: int,
    low_count: int,
) -> dict[str, Any]:
    allowed_subcategories = report.get("allowed_subcategories")
    if allowed_subcategories != 60:
        raise BenchmarkTopic3RiskAssetError(
            "final_qa_report.allowed_subcategories must be 60"
        )
    files = report.get("files")
    if not isinstance(files, list):
        raise BenchmarkTopic3RiskAssetError("final_qa_report.files must be a list")

    expected = {
        safe_path.name: safe_count,
        low_path.name: low_count,
    }
    issue_counts_total = 0
    rows_by_file: dict[str, int] = {}
    for item in files:
        if not isinstance(item, dict):
            continue
        name = Path(str(item.get("file", ""))).name
        if name not in expected:
            continue
        rows = item.get("rows")
        if rows != expected[name]:
            raise BenchmarkTopic3RiskAssetError(
                f"final_qa_report row count mismatch for {name}: {rows} != {expected[name]}"
            )
        issue_counts = item.get("issue_counts") or {}
        if not isinstance(issue_counts, dict):
            raise BenchmarkTopic3RiskAssetError(
                f"final_qa_report issue_counts for {name} must be an object"
            )
        issue_counts_total += sum(
            int(value) for value in issue_counts.values() if isinstance(value, int)
        )
        rows_by_file[name] = rows

    missing = sorted(set(expected) - set(rows_by_file))
    if missing:
        raise BenchmarkTopic3RiskAssetError(
            f"final_qa_report missing file entries: {', '.join(missing)}"
        )
    if issue_counts_total != 0:
        raise BenchmarkTopic3RiskAssetError(
            f"final_qa_report contains {issue_counts_total} QA issues"
        )
    return {
        "allowed_subcategories": allowed_subcategories,
        "schema_issue_count": 0,
        "taxonomy_issue_count": 0,
        "issue_count": 0,
        "rows_by_file": rows_by_file,
    }


def _category_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        match = re.search(r"C(0[1-9]|1[0-7])\b", str(row.get("risk_category", "")))
        if match:
            counts[match.group(0)] += 1
    return dict(sorted(counts.items()))


def _preview_rows(
    safe_rows: list[dict[str, Any]],
    low_rows: list[dict[str, Any]],
    per_level: int = 20,
) -> list[dict[str, Any]]:
    return safe_rows[:per_level] + low_rows[:per_level]


def _build_platform_manifest(
    *,
    asset_id: str,
    name: str,
    source_repo: str,
    source_commit: str,
    safe_count: int,
    low_count: int,
    category_distribution: dict[str, dict[str, int]],
    qa_summary: dict[str, Any],
    source_dir: Path,
) -> dict[str, Any]:
    category_min_max = {
        level: {
            "min": min(distribution.values()) if distribution else 0,
            "max": max(distribution.values()) if distribution else 0,
        }
        for level, distribution in category_distribution.items()
    }
    return {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "task_id": f"prerun_{asset_id[:56]}",
        "name": name,
        "source_mode": SOURCE_MODE,
        "agent_id": AGENT_ID,
        "benchmark_type": BENCHMARK_TYPE,
        "release_kind": "verified_final_dataset",
        "taxonomy_schema": "17x60",
        "risk_levels": ["safe", "low"],
        "sample_count": safe_count + low_count,
        "safe_count": safe_count,
        "low_count": low_count,
        "category_distribution": category_distribution,
        "category_min_max": category_min_max,
        "qa": qa_summary,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "source_final_dir": str(source_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "safe": REQUIRED_FINAL_FILES["safe"],
            "low": REQUIRED_FINAL_FILES["low"],
            "taxonomy": REQUIRED_FINAL_FILES["taxonomy"],
            "qa_report": REQUIRED_FINAL_FILES["qa_report"],
            "upstream_manifest": REQUIRED_FINAL_FILES["upstream_manifest"],
            "preview": "samples_preview.jsonl",
            "artifact_zip": "artifacts/topic3_risk_prerun_artifacts.zip",
        },
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "note": (
                "详情页可查看样本全文和 label_reason；low 样本显示低风险边界提示；"
                "不开放批量下载。"
            ),
        },
        "checksums": {},
    }


def _write_asset_zip(root_dir: Path, archive_path: Path) -> None:
    names = [
        "manifest.platform.json",
        *REQUIRED_FINAL_FILES.values(),
        "samples_preview.jsonl",
    ]
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(root_dir / name, arcname=name)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
