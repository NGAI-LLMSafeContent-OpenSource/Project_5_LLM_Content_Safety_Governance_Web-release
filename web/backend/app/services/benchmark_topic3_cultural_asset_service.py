from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import BenchmarkAsset

SOURCE_MODE = "prerun_snapshot"
AGENT_ID = "topic3-cultural-corpus-generation"
BENCHMARK_TYPE = "cultural_diversity_generation"
RELEASE_KIND = "demo_ui_batch_prerun"
DEFAULT_RUN_ID = "cultural_evaluation_ui_batch"
DEFAULT_ASSET_ID = "topic3_cultural_corpus_ui_batch_20260711"


class BenchmarkTopic3CulturalAssetError(RuntimeError):
    """Raised when topic3 cultural prerun asset cannot be prepared."""


class BenchmarkTopic3CulturalAssetService:
    def _artifact_root(self) -> Path:
        return Path(get_settings().benchmark_artifact_root)

    async def ensure_default_asset(
        self,
        db: AsyncSession,
        *,
        asset_id: str = DEFAULT_ASSET_ID,
        run_id: str = DEFAULT_RUN_ID,
    ) -> BenchmarkAsset:
        existing = await db.execute(
            select(BenchmarkAsset).where(BenchmarkAsset.asset_id == asset_id)
        )
        asset = existing.scalar_one_or_none()
        if asset is not None:
            return asset

        run_dir = _resolve_run_dir(run_id)
        samples_path = run_dir / "samples.jsonl"
        upstream_manifest_path = run_dir / "manifest.json"
        generation_config_path = run_dir / "generation_config.json"
        for required in (samples_path, upstream_manifest_path, generation_config_path):
            if not required.is_file():
                raise BenchmarkTopic3CulturalAssetError(f"required file missing: {required}")

        upstream_manifest = _read_json_file(upstream_manifest_path, "manifest.json")
        generation_config = _read_json_file(generation_config_path, "generation_config.json")
        raw_rows = _read_jsonl_rows(samples_path)
        if not raw_rows:
            raise BenchmarkTopic3CulturalAssetError("samples.jsonl is empty")

        normalized_rows = [_normalize_row(item, run_id=run_id) for item in raw_rows]
        summary = _build_summary(normalized_rows, upstream_manifest)

        root_dir = self._artifact_root() / "prerun" / asset_id
        artifacts_dir = root_dir / "artifacts"
        archive_path = artifacts_dir / "topic3_cultural_corpus_prerun_artifacts.zip"

        if root_dir.exists():
            raise BenchmarkTopic3CulturalAssetError(f"asset directory already exists: {root_dir}")

        try:
            (root_dir / "raw").mkdir(parents=True, exist_ok=False)
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            _write_jsonl(root_dir / "samples.jsonl", normalized_rows)
            _write_json(root_dir / "quality_report.json", _build_quality_report(summary, upstream_manifest))
            _write_jsonl(
                root_dir / "lineage.jsonl",
                [
                    {
                        "source": "topic3_cultural_corpus_generation",
                        "run_id": run_id,
                        "source_samples_path": str(samples_path),
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            )
            (root_dir / "README.md").write_text(
                "Topic3 cultural corpus prerun snapshot for Dynamic Benchmark.\n",
                encoding="utf-8",
            )

            shutil.copy2(samples_path, root_dir / "raw" / "samples.jsonl")
            shutil.copy2(upstream_manifest_path, root_dir / "raw" / "manifest.json")
            shutil.copy2(generation_config_path, root_dir / "raw" / "generation_config.json")

            manifest = _build_manifest(
                asset_id=asset_id,
                run_id=run_id,
                source_samples_path=samples_path,
                summary=summary,
                upstream_manifest=upstream_manifest,
            )
            _write_json(root_dir / "manifest.platform.json", manifest)

            _write_zip(
                root_dir,
                archive_path,
                files=(
                    "manifest.platform.json",
                    "samples.jsonl",
                    "quality_report.json",
                    "lineage.jsonl",
                    "README.md",
                    "raw/samples.jsonl",
                    "raw/manifest.json",
                    "raw/generation_config.json",
                ),
            )
            manifest["checksums"] = {"artifact_zip_sha256": _sha256_file(archive_path)}
            _write_json(root_dir / "manifest.platform.json", manifest)
        except Exception:
            shutil.rmtree(root_dir, ignore_errors=True)
            raise

        created = BenchmarkAsset(
            asset_id=asset_id,
            task_id=f"prerun_{asset_id[:56]}",
            source_mode=SOURCE_MODE,
            name=str(manifest["name"]),
            manifest_json=json.dumps(manifest, ensure_ascii=False),
            artifact_dir=str(root_dir),
            artifact_zip_path=str(archive_path),
            artifact_sha256=str(manifest["checksums"]["artifact_zip_sha256"]),
            source_repo=str(manifest["source_repo"]),
            source_commit=str(manifest["source_commit"]),
        )
        db.add(created)
        await db.commit()
        await db.refresh(created)
        return created


def _resolve_run_dir(run_id: str) -> Path:
    settings = get_settings()
    configured = settings.cultural_corpus_runs_dir.strip()
    if configured:
        runs_dir = Path(configured).expanduser().resolve()
    else:
        workspace = Path(__file__).resolve().parents[4]
        candidate_paths = [
            workspace
            / "Project_3_Cultural_Diversity_Corpus_Generation_Tool"
            / "framework"
            / "runs",
            workspace.parent
            / "Project_3_Cultural_Diversity_Corpus_Generation_Tool"
            / "framework"
            / "runs",
        ]
        runs_dir = next((path for path in candidate_paths if path.is_dir()), candidate_paths[0])
    run_dir = (runs_dir / run_id).resolve()
    if not run_dir.is_dir():
        raise BenchmarkTopic3CulturalAssetError(f"run directory not found: {run_dir}")
    return run_dir


def _read_json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkTopic3CulturalAssetError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BenchmarkTopic3CulturalAssetError(f"{label} must be a JSON object")
    return payload


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkTopic3CulturalAssetError(
                f"samples.jsonl line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise BenchmarkTopic3CulturalAssetError(
                f"samples.jsonl line {line_number} must be a JSON object"
            )
        rows.append(payload)
    return rows


def _normalize_row(raw: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    sample_id = str(raw.get("sample_id") or raw.get("id") or "").strip()
    if not sample_id:
        raise BenchmarkTopic3CulturalAssetError("sample missing sample_id")
    background = str(raw.get("background") or "")
    user_query = str(raw.get("user_query") or "")
    prompt = "\n".join([item for item in (background, user_query) if item]).strip()
    rubric = raw.get("scoring_rubric") if isinstance(raw.get("scoring_rubric"), dict) else {}
    review = raw.get("review_result") if isinstance(raw.get("review_result"), dict) else {}
    points = raw.get("cultural_knowledge_points")
    return {
        "sample_id": sample_id,
        "prompt": prompt,
        "background": background,
        "user_query": user_query,
        "expected_answer": str(raw.get("expected_answer") or ""),
        "ethnic_group": str(
            raw.get("implied_ethnic_group") or raw.get("ethnic_group") or ""
        ),
        "difficulty_level": str(raw.get("difficulty_level") or ""),
        "background_type": str(raw.get("background_type") or ""),
        "persona": str(raw.get("persona") or ""),
        "query_type": str(raw.get("query_type") or ""),
        "cultural_knowledge_points": [str(item) for item in points] if isinstance(points, list) else [],
        "rubric": {
            "must_have": _to_string_list(rubric.get("must_have")),
            "penalty": _to_string_list(rubric.get("penalty")),
        },
        "review": {
            "overall_passed": review.get("overall_passed") is True,
            "cultural_accuracy": review.get("cultural_accuracy"),
            "reason": str(review.get("reason") or ""),
            "consistency": str(review.get("consistency") or ""),
        },
        "run_id": run_id,
        "batch_id": str(raw.get("batch_id") or ""),
    }


def _to_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _build_summary(rows: list[dict[str, Any]], upstream_manifest: dict[str, Any]) -> dict[str, Any]:
    difficulty = Counter(str(item.get("difficulty_level") or "") for item in rows)
    ethnic = Counter(str(item.get("ethnic_group") or "") for item in rows)
    background_type = Counter(str(item.get("background_type") or "") for item in rows)
    persona = Counter(str(item.get("persona") or "") for item in rows)
    query_type = Counter(str(item.get("query_type") or "") for item in rows)
    review_passed_count = sum(1 for item in rows if (item.get("review") or {}).get("overall_passed"))
    return {
        "sample_count": len(rows),
        "difficulty_distribution": dict(difficulty),
        "ethnic_distribution": dict(ethnic),
        "background_type_distribution": dict(background_type),
        "persona_distribution": dict(persona),
        "query_type_distribution": dict(query_type),
        "review_passed_count": review_passed_count,
        "review_passed_rate": review_passed_count / max(1, len(rows)),
        "discard_counts": upstream_manifest.get("discard_counts")
        if isinstance(upstream_manifest.get("discard_counts"), dict)
        else {},
    }


def _build_quality_report(summary: dict[str, Any], upstream_manifest: dict[str, Any]) -> dict[str, Any]:
    batches = upstream_manifest.get("batches")
    batch_quality = {}
    if isinstance(batches, list) and batches and isinstance(batches[0], dict):
        quality = batches[0].get("quality_report")
        if isinstance(quality, dict):
            batch_quality = quality
    return {
        "sample_count": summary["sample_count"],
        "review_passed_count": summary["review_passed_count"],
        "difficulty_distribution": summary["difficulty_distribution"],
        "ethnic_distribution": summary["ethnic_distribution"],
        "background_type_distribution": summary["background_type_distribution"],
        "persona_distribution": summary["persona_distribution"],
        "query_type_distribution": summary["query_type_distribution"],
        "discard_counts": summary["discard_counts"],
        "upstream_batch_quality": batch_quality,
        "notes": [
            "Imported from cultural_evaluation_ui_batch; model evaluation results are not included."
        ],
    }


def _build_manifest(
    *,
    asset_id: str,
    run_id: str,
    source_samples_path: Path,
    summary: dict[str, Any],
    upstream_manifest: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    quality_gate_overall = "unknown"
    batches = upstream_manifest.get("batches")
    if isinstance(batches, list) and batches and isinstance(batches[0], dict):
        quality = batches[0].get("quality_report")
        if isinstance(quality, dict):
            quality_gate_overall = str(quality.get("overall") or "unknown")
    return {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "task_id": f"prerun_{asset_id[:56]}",
        "name": "Topic3 Cultural Corpus UI Batch (30 samples)",
        "source_mode": SOURCE_MODE,
        "agent_id": AGENT_ID,
        "benchmark_type": BENCHMARK_TYPE,
        "release_kind": RELEASE_KIND,
        "sample_count": summary["sample_count"],
        "difficulty_distribution": summary["difficulty_distribution"],
        "ethnic_distribution": summary["ethnic_distribution"],
        "background_type_distribution": summary["background_type_distribution"],
        "persona_distribution": summary["persona_distribution"],
        "query_type_distribution": summary["query_type_distribution"],
        "review_passed_count": summary["review_passed_count"],
        "review_passed_rate": summary["review_passed_rate"],
        "quality_gate_overall": quality_gate_overall,
        "model_eval_status": "pending_import",
        "source_repo": settings.topic3_cultural_source_repo,
        "source_commit": settings.topic3_cultural_source_commit,
        "source_run_id": run_id,
        "source_samples_path": str(source_samples_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "samples": "samples.jsonl",
            "quality_report": "quality_report.json",
            "lineage": "lineage.jsonl",
            "readme": "README.md",
            "artifact_zip": "artifacts/topic3_cultural_corpus_prerun_artifacts.zip",
        },
        "ui_hints": {
            "sample_drawer": "cultural_corpus_detail",
            "badge": "prerun_snapshot",
            "model_eval_label": "pending_import",
        },
        "checksums": {},
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_zip(root_dir: Path, archive_path: Path, *, files: tuple[str, ...]) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive.write(root_dir / relative, arcname=relative)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
