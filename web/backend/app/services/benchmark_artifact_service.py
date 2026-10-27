from __future__ import annotations

import hashlib
import json
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from app.core.config import get_settings
from app.services.benchmark_topic2_empty_run import is_topic2_empty_run
from app.services.benchmark_topic3_risk_asset_service import (
    BenchmarkTopic3RiskAssetError,
    _load_and_validate_jsonl,
)


REQUIRED_MEMBERS = {"manifest.json", "report.md"}
OPTIONAL_MEMBERS = {"results.json", "dynbench.jsonl"}
ALLOWED_MEMBERS = REQUIRED_MEMBERS | OPTIONAL_MEMBERS
TOPIC3_REQUIRED_MEMBERS = {
    "samples.jsonl",
    "manifest.json",
    "worker_state.json",
    "generation_config.json",
    "worker.log",
}
TOPIC1_VALUE_QA_REQUIRED_MEMBERS = {
    "manifest.json",
    "samples.jsonl",
    "group_preview.jsonl",
    "quality_report.json",
    "lineage.jsonl",
    "worker.log",
}
TOPIC3_CULTURAL_REQUIRED_MEMBERS = {"samples.jsonl"}
TOPIC3_CULTURAL_ALLOWED_MEMBERS = {
    "samples.jsonl",
    "manifest.json",
    "generation_config.json",
    "worker_state.json",
    "worker.log",
}
TOPIC3_RISK_REQUIRED_MEMBERS = {
    "manifest.json",
    "samples.jsonl",
    "safe.jsonl",
    "low.jsonl",
    "qa_report.json",
    "worker.log",
}
TOPIC3_RISK_ALLOWED_MEMBERS = TOPIC3_RISK_REQUIRED_MEMBERS | {
    "canonical_taxonomy_17x60.md",
}


class BenchmarkArtifactError(RuntimeError):
    """Raised when an upstream artifact cannot be safely frozen."""


@dataclass(slots=True)
class FrozenBenchmarkArtifact:
    asset_id: str
    artifact_dir: Path
    artifact_zip_path: Path
    artifact_sha256: str
    manifest: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_autobench_zip(archive_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = _validated_members(archive)
        for name in sorted(members):
            target = output_dir / name
            target.write_bytes(archive.read(name))
            extracted.append(target)
    return extracted


def freeze_autobench_artifact(
    *,
    artifact_bytes: bytes,
    root_dir: Path,
    task_id: str,
    parameters: dict[str, Any],
    source_commit: str,
    upstream_base_url: str,
    source_repo: str | None = None,
    adapter_version: str = "topic2-autobench-adapter-v0.1",
) -> FrozenBenchmarkArtifact:
    settings = get_settings()
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    artifact_dir = root_dir / task_id / asset_id
    artifacts_dir = artifact_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    artifact_zip_path = artifacts_dir / "autobench_artifacts.zip"
    artifact_zip_path.write_bytes(artifact_bytes)
    artifact_sha256 = sha256_file(artifact_zip_path)

    safe_extract_autobench_zip(artifact_zip_path, artifact_dir)

    files: dict[str, str | None] = {
        "artifact_zip": "artifacts/autobench_artifacts.zip",
        "report": "report.md",
        "results": "results.json" if (artifact_dir / "results.json").exists() else None,
        "dynbench": "dynbench.jsonl" if (artifact_dir / "dynbench.jsonl").exists() else None,
    }
    warnings: list[str] = []
    upstream_manifest = _load_json_file(artifact_dir / "manifest.json")
    results_payload = _load_json_file(artifact_dir / "results.json")
    upstream_dynbench_count = upstream_manifest.get("dynbench_count")
    if not isinstance(upstream_dynbench_count, int) or isinstance(
        upstream_dynbench_count, bool
    ):
        upstream_dynbench_count = None
    dynbench_path = (
        artifact_dir / "dynbench.jsonl" if files["dynbench"] is not None else None
    )
    empty_run = is_topic2_empty_run(upstream_manifest, dynbench_path=dynbench_path)
    if files["results"] is None:
        warnings.append("results.json missing from upstream artifact")
    if empty_run:
        warnings.append(
            "dynbench.jsonl omitted by upstream (dynbench_count=0); run stored no samples"
        )
    elif files["dynbench"] is None:
        warnings.append("dynbench.jsonl missing from upstream artifact")
    mismatch_warning = _moderator_mismatch_warning(parameters, results_payload)
    if mismatch_warning:
        warnings.append(mismatch_warning)

    manifest = {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "name": "Topic2 AutoBench live run",
        "source_mode": "live_run",
        "task_id": task_id,
        "agent_id": "topic2-autobench",
        "adapter_version": adapter_version,
        "source_repo": source_repo or settings.topic2_autobench_source_repo,
        "source_commit": source_commit,
        "upstream_base_url": upstream_base_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": parameters,
        "upstream_manifest": upstream_manifest,
        "upstream_dynbench_count": upstream_dynbench_count,
        "files": files,
        "checksums": {"artifact_zip_sha256": artifact_sha256},
        "warnings": warnings,
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "note": "包含安全测试与攻击变体，默认只展示摘要和受控样本。",
        },
    }
    manifest_path = artifact_dir / "manifest.platform.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return FrozenBenchmarkArtifact(
        asset_id=asset_id,
        artifact_dir=artifact_dir,
        artifact_zip_path=artifact_zip_path,
        artifact_sha256=artifact_sha256,
        manifest=manifest,
    )


def freeze_topic3_difficulty_artifact(
    *,
    artifact_bytes: bytes,
    root_dir: Path,
    task_id: str,
    parameters: dict[str, Any],
    source_commit: str,
    upstream_base_url: str,
    source_repo: str | None = None,
    adapter_version: str = "topic3-difficulty-adapter-v0.1",
) -> FrozenBenchmarkArtifact:
    settings = get_settings()
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    artifact_dir = root_dir / task_id / asset_id
    artifacts_dir = artifact_dir / "artifacts"
    raw_dir = artifact_dir / "raw"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    artifact_zip_path = artifacts_dir / "topic3_difficulty_artifacts.zip"
    artifact_zip_path.write_bytes(artifact_bytes)
    artifact_sha256 = sha256_file(artifact_zip_path)

    safe_extract_topic3_difficulty_zip(artifact_zip_path, raw_dir)

    upstream_manifest = _load_json_file(raw_dir / "manifest.json")
    sample_stats = _summarize_topic3_samples(raw_dir / "samples.jsonl")
    files = {
        "artifact_zip": "artifacts/topic3_difficulty_artifacts.zip",
        "samples": "raw/samples.jsonl",
        "upstream_manifest": "raw/manifest.json",
        "worker_state": "raw/worker_state.json",
        "generation_config": "raw/generation_config.json",
        "worker_log": "raw/worker.log",
        "batches": "raw/batches" if (raw_dir / "batches").exists() else None,
    }
    platform_label = str(parameters.get("difficulty_preset") or "custom")
    manifest = {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "name": "Topic3 dynamic difficulty live run",
        "source_mode": "live_run",
        "task_id": task_id,
        "agent_id": "topic3-difficulty-generation",
        "adapter_version": adapter_version,
        "benchmark_type": "dynamic_difficulty",
        "native_difficulty_schema": "H1-H4",
        "platform_difficulty_label": platform_label,
        "platform_difficulty_basis": _topic3_difficulty_basis(platform_label),
        "difficulty_distribution": sample_stats["difficulty_distribution"],
        "sample_count": sample_stats["sample_count"],
        "source_repo": source_repo or settings.topic3_difficulty_source_repo,
        "source_commit": source_commit,
        "upstream_base_url": upstream_base_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": parameters,
        "upstream_manifest": upstream_manifest,
        "files": files,
        "checksums": {"artifact_zip_sha256": artifact_sha256},
        "warnings": sample_stats["warnings"],
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "note": "包含有害与无害混合编辑安全评测样本，默认只展示摘要、标签和 span 元数据。",
        },
    }
    manifest_path = artifact_dir / "manifest.platform.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return FrozenBenchmarkArtifact(
        asset_id=asset_id,
        artifact_dir=artifact_dir,
        artifact_zip_path=artifact_zip_path,
        artifact_sha256=artifact_sha256,
        manifest=manifest,
    )


def freeze_topic1_value_qa_artifact(
    *,
    artifact_bytes: bytes,
    root_dir: Path,
    task_id: str,
    parameters: dict[str, Any],
    source_commit: str,
    upstream_base_url: str,
    source_repo: str | None = None,
    adapter_version: str = "topic1-value-qa-cli-adapter-v0.1",
) -> FrozenBenchmarkArtifact:
    settings = get_settings()
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    artifact_dir = root_dir / task_id / asset_id
    artifacts_dir = artifact_dir / "artifacts"
    raw_dir = artifact_dir / "raw"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    artifact_zip_path = artifacts_dir / "topic1_value_qa_artifacts.zip"
    artifact_zip_path.write_bytes(artifact_bytes)
    artifact_sha256 = sha256_file(artifact_zip_path)

    safe_extract_topic1_value_qa_zip(artifact_zip_path, raw_dir)

    upstream_manifest = _load_json_file(raw_dir / "manifest.json")
    quality_report = _load_json_file(raw_dir / "quality_report.json")
    sample_stats = _summarize_topic1_value_qa_samples(raw_dir / "samples.jsonl")
    warnings = list(upstream_manifest.get("warnings") or [])
    warnings.extend(sample_stats["warnings"])
    generated_group_count = int(
        upstream_manifest.get("generated_group_count")
        or quality_report.get("group_count")
        or sample_stats["group_count"]
    )
    requested_group_count = int(
        upstream_manifest.get("requested_group_count")
        or _requested_topic1_group_count(parameters)
    )

    files = {
        "artifact_zip": "artifacts/topic1_value_qa_artifacts.zip",
        "samples": "raw/samples.jsonl",
        "group_preview": "raw/group_preview.jsonl",
        "quality_report": "raw/quality_report.json",
        "lineage": "raw/lineage.jsonl",
        "worker_log": "raw/worker.log",
        "upstream_manifest": "raw/manifest.json",
    }
    manifest = {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "name": "Topic1 value_qa live run",
        "source_mode": "live_run",
        "task_id": task_id,
        "agent_id": "topic1-value-qa",
        "adapter_version": adapter_version,
        "benchmark_type": "value_qa",
        "schema_id": "topic1.value_qa.v0.1",
        "release_kind": "value_qa_live_run_structure_checked",
        "quality_levels": ["high", "medium", "low"],
        "sample_count": sample_stats["sample_count"],
        "group_count": generated_group_count,
        "requested_group_count": requested_group_count,
        "generated_group_count": generated_group_count,
        "quality_level_distribution": sample_stats["quality_level_distribution"],
        "validation": {
            "scope": "structure_only",
            "passed": generated_group_count >= 1,
        },
        "retrieval": upstream_manifest.get("retrieval") or {},
        "llm_runtime": upstream_manifest.get("llm_runtime") or {},
        "source_repo": source_repo or settings.topic1_value_qa_source_repo,
        "source_commit": source_commit,
        "upstream_base_url": upstream_base_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": parameters,
        "upstream_manifest": upstream_manifest,
        "quality_report": quality_report,
        "files": files,
        "checksums": {"artifact_zip_sha256": artifact_sha256},
        "warnings": warnings,
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "note": "包含价值评测三档问答样本，默认只展示摘要和受控样本。",
        },
        "ui_hints": {
            "sample_drawer": "compare_high_medium_low",
            "badge": "live_run",
            "validation_label": "structure_only",
        },
    }
    manifest_path = artifact_dir / "manifest.platform.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return FrozenBenchmarkArtifact(
        asset_id=asset_id,
        artifact_dir=artifact_dir,
        artifact_zip_path=artifact_zip_path,
        artifact_sha256=artifact_sha256,
        manifest=manifest,
    )


def freeze_topic3_risk_live_artifact(
    *,
    artifact_bytes: bytes,
    root_dir: Path,
    task_id: str,
    parameters: dict[str, Any],
    source_commit: str,
    upstream_base_url: str,
    source_repo: str | None = None,
    adapter_version: str = "topic3-risk-cli-adapter-v0.1",
) -> FrozenBenchmarkArtifact:
    settings = get_settings()
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    artifact_dir = root_dir / task_id / asset_id
    artifacts_dir = artifact_dir / "artifacts"
    raw_dir = artifact_dir / "raw"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    artifact_zip_path = artifacts_dir / "topic3_risk_artifacts.zip"
    artifact_zip_path.write_bytes(artifact_bytes)
    artifact_sha256 = sha256_file(artifact_zip_path)

    safe_extract_topic3_risk_zip(artifact_zip_path, raw_dir)

    for name in ("safe.jsonl", "low.jsonl", "samples.jsonl"):
        source = raw_dir / name
        if source.is_file():
            shutil.copy2(source, artifact_dir / name)

    try:
        safe_rows = _load_and_validate_jsonl(
            artifact_dir / "safe.jsonl",
            expected_level="safe",
            expected_safetype="safe",
        )
        low_rows = _load_and_validate_jsonl(
            artifact_dir / "low.jsonl",
            expected_level="low",
            expected_safetype="unsafe",
        )
    except BenchmarkTopic3RiskAssetError as exc:
        raise BenchmarkArtifactError(str(exc)) from exc

    target_per_kind = int(parameters.get("target_per_kind") or 5)
    if len(safe_rows) != target_per_kind or len(low_rows) != target_per_kind:
        raise BenchmarkArtifactError(
            "trial row counts differ from target_per_kind; "
            f"expected {target_per_kind}+{target_per_kind}, "
            f"got {len(safe_rows)}+{len(low_rows)}"
        )

    upstream_manifest = _load_json_file(raw_dir / "manifest.json")
    qa_report_path = raw_dir / "qa_report.json"
    if not qa_report_path.is_file():
        raise BenchmarkArtifactError("artifact is missing required members: qa_report.json")
    qa_report = _load_json_file(qa_report_path)
    if not qa_report:
        raise BenchmarkArtifactError("qa_report.json is empty or invalid JSON object")

    issue_count = _sum_topic3_risk_qa_issues(qa_report)
    warnings: list[str] = []
    if issue_count > 0:
        warnings.append(
            f"trial QA reported {issue_count} issue(s); "
            "recorded for display only (freeze still succeeds)"
        )

    files = {
        "artifact_zip": "artifacts/topic3_risk_artifacts.zip",
        "samples": "samples.jsonl",
        "safe": "safe.jsonl",
        "low": "low.jsonl",
        "qa_report": "raw/qa_report.json",
        "taxonomy": (
            "raw/canonical_taxonomy_17x60.md"
            if (raw_dir / "canonical_taxonomy_17x60.md").is_file()
            else None
        ),
        "worker_log": "raw/worker.log",
        "upstream_manifest": "raw/manifest.json",
    }
    manifest = {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "name": "Topic3 dynamic risk live run",
        "source_mode": "live_run",
        "task_id": task_id,
        "agent_id": "topic3-risk-benchmark-generation",
        "adapter_version": adapter_version,
        "benchmark_type": "risk_content_generation",
        "release_kind": "live_run_trial",
        "taxonomy_schema": "17x60",
        "risk_levels": ["safe", "low"],
        "qa_mode": "trial",
        "category_balance_required": False,
        "sample_count": len(safe_rows) + len(low_rows),
        "safe_count": len(safe_rows),
        "low_count": len(low_rows),
        "source_repo": source_repo or settings.topic3_risk_benchmark_source_repo,
        "source_commit": source_commit,
        "upstream_base_url": upstream_base_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": parameters,
        "upstream_manifest": upstream_manifest,
        "qa": {
            "mode": qa_report.get("mode") or "trial",
            "schema_issue_count": issue_count,
            "issue_count": issue_count,
            "taxonomy_balance_enforced": False,
        },
        "files": files,
        "checksums": {"artifact_zip_sha256": artifact_sha256},
        "warnings": warnings,
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "note": (
                "试跑 live_run，仅 5 safe + 5 low；不代表 17×60 均衡集。"
                "详情页可查看全文和 label_reason；low 样本显示低风险边界提示。"
            ),
        },
    }
    manifest_path = artifact_dir / "manifest.platform.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return FrozenBenchmarkArtifact(
        asset_id=asset_id,
        artifact_dir=artifact_dir,
        artifact_zip_path=artifact_zip_path,
        artifact_sha256=artifact_sha256,
        manifest=manifest,
    )


def freeze_topic3_cultural_live_artifact(
    *,
    artifact_bytes: bytes,
    root_dir: Path,
    task_id: str,
    parameters: dict[str, Any],
    source_commit: str,
    upstream_base_url: str,
    source_repo: str | None = None,
    adapter_version: str = "topic3-cultural-corpus-adapter-v0.1",
) -> FrozenBenchmarkArtifact:
    from app.services.benchmark_topic3_cultural_asset_service import (
        AGENT_ID as CULTURAL_AGENT_ID,
        BENCHMARK_TYPE as CULTURAL_BENCHMARK_TYPE,
        BenchmarkTopic3CulturalAssetError,
        _build_quality_report,
        _build_summary,
        _normalize_row,
    )

    settings = get_settings()
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    artifact_dir = root_dir / task_id / asset_id
    artifacts_dir = artifact_dir / "artifacts"
    raw_dir = artifact_dir / "raw"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    artifact_zip_path = artifacts_dir / "topic3_cultural_corpus_live_artifacts.zip"
    artifact_zip_path.write_bytes(artifact_bytes)
    artifact_sha256 = sha256_file(artifact_zip_path)

    safe_extract_topic3_cultural_zip(artifact_zip_path, raw_dir)

    upstream_manifest = _load_json_file(raw_dir / "manifest.json")
    raw_samples_path = raw_dir / "samples.jsonl"
    raw_rows = _load_jsonl_objects(raw_samples_path)
    if not raw_rows:
        raise BenchmarkArtifactError("samples.jsonl is empty")

    warnings: list[str] = []
    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows, start=1):
        try:
            normalized_rows.append(_normalize_row(row, run_id=task_id))
        except BenchmarkTopic3CulturalAssetError as exc:
            warnings.append(f"skip sample at line {index}: {exc}")

    if not normalized_rows:
        raise BenchmarkArtifactError("no valid cultural samples after normalization")

    summary = _build_summary(normalized_rows, upstream_manifest)
    quality_report = _build_quality_report(summary, upstream_manifest)

    samples_path = artifact_dir / "samples.jsonl"
    with samples_path.open("w", encoding="utf-8") as handle:
        for row in normalized_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    quality_report_path = artifact_dir / "quality_report.json"
    quality_report_path.write_text(
        json.dumps(quality_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    files = {
        "artifact_zip": "artifacts/topic3_cultural_corpus_live_artifacts.zip",
        "samples": "samples.jsonl",
        "quality_report": "quality_report.json",
        "raw_samples": "raw/samples.jsonl",
        "upstream_manifest": "raw/manifest.json"
        if (raw_dir / "manifest.json").exists()
        else None,
        "worker_state": "raw/worker_state.json"
        if (raw_dir / "worker_state.json").exists()
        else None,
        "generation_config": "raw/generation_config.json"
        if (raw_dir / "generation_config.json").exists()
        else None,
        "worker_log": "raw/worker.log" if (raw_dir / "worker.log").exists() else None,
    }
    manifest = {
        "schema_version": "benchmark-manifest-v0.1",
        "asset_id": asset_id,
        "name": "Topic3 cultural diversity corpus live run",
        "source_mode": "live_run",
        "task_id": task_id,
        "agent_id": CULTURAL_AGENT_ID,
        "adapter_version": adapter_version,
        "benchmark_type": CULTURAL_BENCHMARK_TYPE,
        "sample_count": summary["sample_count"],
        "difficulty_distribution": summary["difficulty_distribution"],
        "ethnic_distribution": summary["ethnic_distribution"],
        "background_type_distribution": summary["background_type_distribution"],
        "persona_distribution": summary["persona_distribution"],
        "query_type_distribution": summary["query_type_distribution"],
        "review_passed_count": summary["review_passed_count"],
        "review_passed_rate": summary["review_passed_rate"],
        "source_repo": source_repo or settings.topic3_cultural_source_repo,
        "source_commit": source_commit,
        "upstream_base_url": upstream_base_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": parameters,
        "upstream_manifest": upstream_manifest,
        "files": files,
        "checksums": {"artifact_zip_sha256": artifact_sha256},
        "warnings": warnings,
        "sensitivity": {
            "level": "restricted",
            "download_allowed": False,
            "note": "包含文化多样性评测语料，默认只展示摘要和受控样本。",
        },
        "ui_hints": {
            "sample_drawer": "cultural_corpus_detail",
            "badge": "live_run",
        },
    }
    manifest_path = artifact_dir / "manifest.platform.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return FrozenBenchmarkArtifact(
        asset_id=asset_id,
        artifact_dir=artifact_dir,
        artifact_zip_path=artifact_zip_path,
        artifact_sha256=artifact_sha256,
        manifest=manifest,
    )


def _validated_members(archive: zipfile.ZipFile) -> dict[str, str]:
    members: dict[str, str] = {}
    seen: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            raise BenchmarkArtifactError(f"directory members are not allowed: {info.filename}")
        name = info.filename
        if _is_unsafe_member(name):
            raise BenchmarkArtifactError(f"unsafe zip member: {name}")
        duplicate_key = name.replace("\\", "/").casefold()
        if duplicate_key in seen:
            raise BenchmarkArtifactError(f"duplicate zip member: {name}")
        seen.add(duplicate_key)
        if name not in ALLOWED_MEMBERS:
            raise BenchmarkArtifactError(f"unsupported zip member: {name}")
        members[name] = name

    missing = REQUIRED_MEMBERS - set(members)
    if missing:
        raise BenchmarkArtifactError(
            f"artifact is missing required members: {', '.join(sorted(missing))}"
        )
    return members


def safe_extract_topic3_difficulty_zip(
    archive_path: Path, output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = _validated_topic3_members(archive)
        for name in sorted(members):
            target = output_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            extracted.append(target)
    return extracted


def safe_extract_topic1_value_qa_zip(
    archive_path: Path, output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = _validated_topic1_value_qa_members(archive)
        for name in sorted(members):
            target = output_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            extracted.append(target)
    return extracted


def safe_extract_topic3_cultural_zip(
    archive_path: Path, output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = _validated_topic3_cultural_members(archive)
        for name in sorted(members):
            target = output_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            extracted.append(target)
    return extracted


def safe_extract_topic3_risk_zip(
    archive_path: Path, output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = _validated_topic3_risk_members(archive)
        for name in sorted(members):
            target = output_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            extracted.append(target)
    return extracted


def _validated_topic3_risk_members(archive: zipfile.ZipFile) -> dict[str, str]:
    members: dict[str, str] = {}
    seen: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            raise BenchmarkArtifactError(
                f"directory members are not allowed: {info.filename}"
            )
        name = info.filename.replace("\\", "/")
        if _is_unsafe_member(name):
            raise BenchmarkArtifactError(f"unsafe zip member: {info.filename}")
        duplicate_key = name.casefold()
        if duplicate_key in seen:
            raise BenchmarkArtifactError(f"duplicate zip member: {info.filename}")
        seen.add(duplicate_key)
        if name not in TOPIC3_RISK_ALLOWED_MEMBERS:
            raise BenchmarkArtifactError(f"unsupported zip member: {info.filename}")
        members[name] = name

    missing = TOPIC3_RISK_REQUIRED_MEMBERS - set(members)
    if missing:
        raise BenchmarkArtifactError(
            f"artifact is missing required members: {', '.join(sorted(missing))}"
        )
    return members


def _validated_topic3_cultural_members(archive: zipfile.ZipFile) -> dict[str, str]:
    members: dict[str, str] = {}
    seen: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            raise BenchmarkArtifactError(
                f"directory members are not allowed: {info.filename}"
            )
        name = info.filename.replace("\\", "/")
        if _is_unsafe_member(name):
            raise BenchmarkArtifactError(f"unsafe zip member: {info.filename}")
        duplicate_key = name.casefold()
        if duplicate_key in seen:
            raise BenchmarkArtifactError(f"duplicate zip member: {info.filename}")
        seen.add(duplicate_key)
        if name not in TOPIC3_CULTURAL_ALLOWED_MEMBERS:
            raise BenchmarkArtifactError(f"unsupported zip member: {info.filename}")
        members[name] = name

    missing = TOPIC3_CULTURAL_REQUIRED_MEMBERS - set(members)
    if missing:
        raise BenchmarkArtifactError(
            f"artifact is missing required members: {', '.join(sorted(missing))}"
        )
    return members


def _validated_topic3_members(archive: zipfile.ZipFile) -> dict[str, str]:
    members: dict[str, str] = {}
    seen: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            raise BenchmarkArtifactError(f"directory members are not allowed: {info.filename}")
        name = info.filename.replace("\\", "/")
        if _is_unsafe_member(name):
            raise BenchmarkArtifactError(f"unsafe zip member: {info.filename}")
        duplicate_key = name.casefold()
        if duplicate_key in seen:
            raise BenchmarkArtifactError(f"duplicate zip member: {info.filename}")
        seen.add(duplicate_key)
        if name not in TOPIC3_REQUIRED_MEMBERS and not name.startswith("batches/"):
            raise BenchmarkArtifactError(f"unsupported zip member: {info.filename}")
        members[name] = name

    missing = TOPIC3_REQUIRED_MEMBERS - set(members)
    if missing:
        raise BenchmarkArtifactError(
            f"artifact is missing required members: {', '.join(sorted(missing))}"
        )
    return members


def _validated_topic1_value_qa_members(archive: zipfile.ZipFile) -> dict[str, str]:
    members: dict[str, str] = {}
    seen: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            raise BenchmarkArtifactError(f"directory members are not allowed: {info.filename}")
        name = info.filename.replace("\\", "/")
        if _is_unsafe_member(name):
            raise BenchmarkArtifactError(f"unsafe zip member: {info.filename}")
        duplicate_key = name.casefold()
        if duplicate_key in seen:
            raise BenchmarkArtifactError(f"duplicate zip member: {info.filename}")
        seen.add(duplicate_key)
        if name not in TOPIC1_VALUE_QA_REQUIRED_MEMBERS:
            raise BenchmarkArtifactError(f"unsupported zip member: {info.filename}")
        members[name] = name

    missing = TOPIC1_VALUE_QA_REQUIRED_MEMBERS - set(members)
    if missing:
        raise BenchmarkArtifactError(
            f"artifact is missing required members: {', '.join(sorted(missing))}"
        )
    return members


def _is_unsafe_member(name: str) -> bool:
    if not name or "\x00" in name:
        return True
    windows_path = PureWindowsPath(name)
    posix_path = PurePosixPath(name.replace("\\", "/"))
    if windows_path.is_absolute() or posix_path.is_absolute():
        return True
    return ".." in posix_path.parts


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sum_topic3_risk_qa_issues(qa_report: dict[str, Any]) -> int:
    """Best-effort issue total for display; does not gate freeze."""
    for key in ("issue_count", "schema_issue_count"):
        value = qa_report.get(key)
        if isinstance(value, int) and value >= 0:
            return value

    files = qa_report.get("files")
    if not isinstance(files, list):
        return 0

    total = 0
    for item in files:
        if not isinstance(item, dict):
            continue
        issue_counts = item.get("issue_counts")
        if isinstance(issue_counts, dict):
            total += sum(
                int(value) for value in issue_counts.values() if isinstance(value, int)
            )
            continue
        row_issue_count = item.get("issue_count")
        if isinstance(row_issue_count, int):
            total += row_issue_count
    return total


def _load_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise BenchmarkArtifactError(
                        f"invalid JSONL at line {line_number}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise BenchmarkArtifactError(
                        f"non-object sample at line {line_number}"
                    )
                rows.append(payload)
    except OSError as exc:
        raise BenchmarkArtifactError(f"cannot read samples.jsonl: {exc}") from exc
    return rows


def _moderator_mismatch_warning(
    parameters: dict[str, Any], results_payload: dict[str, Any]
) -> str | None:
    requested = _string_list(parameters.get("moderators"))
    actual = _result_moderator_names(results_payload)
    if not requested or not actual:
        return None

    requested_keys = {_canonical_moderator_name(item) for item in requested}
    actual_keys = {_canonical_moderator_name(item) for item in actual}
    if requested_keys == actual_keys:
        return None

    return (
        "results.json moderators do not match requested moderators: "
        f"requested={', '.join(requested)}; results={', '.join(actual)}"
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _result_moderator_names(results_payload: dict[str, Any]) -> list[str]:
    moderators = results_payload.get("moderators")
    if not isinstance(moderators, list):
        return []
    names: list[str] = []
    for item in moderators:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
        elif isinstance(item, str):
            names.append(item)
    return names


def _canonical_moderator_name(name: str) -> str:
    aliases = {
        "keyword": "keyword_baseline",
        "random": "random_baseline",
    }
    normalized = name.strip().lower()
    return aliases.get(normalized, normalized)


def _summarize_topic3_samples(path: Path) -> dict[str, Any]:
    distribution = {"H1": 0, "H2": 0, "H3": 0, "H4": 0}
    warnings: list[str] = []
    sample_count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"invalid JSONL at line {line_number}")
                    continue
                if not isinstance(sample, dict):
                    warnings.append(f"non-object sample at line {line_number}")
                    continue
                sample_count += 1
                level = str(sample.get("difficulty_level") or "")
                if level in distribution:
                    distribution[level] += 1
    except OSError as exc:
        raise BenchmarkArtifactError(f"cannot read samples.jsonl: {exc}") from exc
    return {
        "sample_count": sample_count,
        "difficulty_distribution": distribution,
        "warnings": warnings,
    }


def _summarize_topic1_value_qa_samples(path: Path) -> dict[str, Any]:
    distribution = {"high": 0, "medium": 0, "low": 0}
    group_ids: set[str] = set()
    warnings: list[str] = []
    sample_count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"invalid JSONL at line {line_number}")
                    continue
                if not isinstance(sample, dict):
                    warnings.append(f"non-object sample at line {line_number}")
                    continue
                sample_count += 1
                level = str(sample.get("quality_level") or "")
                if level in distribution:
                    distribution[level] += 1
                else:
                    warnings.append(f"unsupported quality_level at line {line_number}: {level}")
                group_id = sample.get("group_id")
                if group_id:
                    group_ids.add(str(group_id))
    except OSError as exc:
        raise BenchmarkArtifactError(f"cannot read samples.jsonl: {exc}") from exc
    return {
        "sample_count": sample_count,
        "group_count": len(group_ids),
        "quality_level_distribution": distribution,
        "warnings": warnings,
    }


def _requested_topic1_group_count(parameters: dict[str, Any]) -> int:
    generation_mode = str(parameters.get("generation_mode") or "topic")
    if generation_mode == "topic":
        raw_topics = parameters.get("topics")
        if isinstance(raw_topics, list):
            n_topics = len(
                [
                    str(item).strip()
                    for item in raw_topics
                    if item is not None and str(item).strip()
                ]
            ) or 1
        else:
            n_topics = 1
    else:
        n_topics = int(parameters.get("n_topics") or 1)
    return n_topics * int(parameters.get("groups_per_topic") or 1)


def _topic3_difficulty_basis(label: str) -> str:
    if label == "demo_small":
        return "balanced H1-H4 small live_run"
    if label == "balanced_h1h4":
        return "balanced H1-H4"
    if label == "hard_h3h4":
        return "H3/H4-dominant"
    return "custom difficulty_counts"
