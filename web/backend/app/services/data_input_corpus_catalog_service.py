"""Catalog and load prerun corpora for input Step 1 (value/risk tracks separately)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.schemas.data_input import (
    InputCorpusCatalogItem,
    InputCorpusCatalogResponse,
    InputCorpusRecord,
    InputCorpusSelectResponse,
)
from app.schemas.governance import RISK_STATIC_ASSET_DISPLAY_NAME
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_topic1_value_qa_sample_service import (
    BenchmarkTopic1ValueQaSampleError,
    BenchmarkTopic1ValueQaSampleService,
)
from app.services.data_input_value_qa_builtin import ensure_preferred_value_qa_assets
from app.services.data_input_value_qa_common import PREFERRED_VALUE_QA_ASSET_IDS

KIND_VALUE_QA = "value_qa"
KIND_RISK_STATIC = "risk_static_dynbench"
RISK_STATIC_ASSET_ID = "topic2_dynbench400_static"
# Single source of truth: `RISK_STATIC_ASSET_DISPLAY_NAME` in app/schemas/governance.py.
RISK_STATIC_ASSET_NAME = RISK_STATIC_ASSET_DISPLAY_NAME
RISK_STATIC_FILENAME = "input_dynbench400_eval_schema.jsonl"
# Demo loads the full DynBench400 pack (catalog card and workflow must agree).
RISK_STATIC_MAX_RECORDS = 500
# Keep the same transport ceiling as the records route. This is not a
# business limit on the number of value_qa samples selected in Step 1.
VALUE_QA_MAX_RECORDS = 500


async def list_input_corpus_catalog(db: AsyncSession) -> InputCorpusCatalogResponse:
    await ensure_preferred_value_qa_assets(db)
    registry = BenchmarkAssetRegistryService()
    items: list[InputCorpusCatalogItem] = []

    # Input Step 1 only exposes the curated Topic1 value_qa packs.
    # Other value_qa rows (live_run / old imports) stay in Benchmark registry but
    # must not appear as selectable corpora.
    for preferred_id in PREFERRED_VALUE_QA_ASSET_IDS:
        asset = await registry.get_asset(db, preferred_id)
        if asset is None:
            continue
        manifest = _loads_json_object(asset.manifest_json)
        if manifest.get("benchmark_type") != KIND_VALUE_QA:
            continue
        items.append(
            InputCorpusCatalogItem(
                asset_id=asset.asset_id,
                name=asset.name or asset.asset_id,
                kind=KIND_VALUE_QA,
                source_label="课题一 value_qa 预跑",
                sample_count=_manifest_int(manifest, "sample_count", "group_count"),
                ready=_value_qa_asset_files_ready(asset),
                description="价值评测语料；仅绑定到价值轨道（标准体系筛选 / 评估 / 归因）。",
                track_hint="价值轨",
                track="value",
            )
        )

    risk_item = _risk_static_catalog_item()
    if risk_item is not None:
        items.append(risk_item)

    items.sort(key=_catalog_sort_key)
    if not items:
        return InputCorpusCatalogResponse(
            connected=False,
            message="尚未导入可用的预跑语料资产。",
            next_action=(
                "请先导入课题一 value_qa，或确认 web/backend/data/input_corpora 下存在课题二静态 dynbench400 jsonl，"
                "也可改用本页上传自定义语料。"
            ),
        )

    value_count = sum(1 for item in items if item.track == "value")
    risk_count = sum(1 for item in items if item.track == "risk")
    return InputCorpusCatalogResponse(
        connected=True,
        message=f"已发现价值语料 {value_count} 个、风险语料 {risk_count} 个。",
        items=items,
        next_action="价值轨与风险轨请分别选择语料；血缘图谱可任选一侧构建。",
    )


async def select_input_corpus(
    db: AsyncSession,
    *,
    asset_id: str,
    kind: str | None = None,
    limit: int = 500,
) -> InputCorpusSelectResponse:
    resolved_kind = kind or ""
    if asset_id == RISK_STATIC_ASSET_ID or resolved_kind == KIND_RISK_STATIC:
        return _select_risk_static(limit=limit)

    registry = BenchmarkAssetRegistryService()
    asset = await registry.get_asset(db, asset_id)
    if asset is None:
        return InputCorpusSelectResponse(
            connected=False,
            message="未找到指定预跑资产。",
            blocking_reason=f"asset_id={asset_id} 不在 Benchmark 注册表中。",
            next_action="刷新预跑列表，或改用上传自定义语料。",
        )

    resolved_kind = kind or _detect_kind(asset)
    if resolved_kind == KIND_VALUE_QA:
        if asset.asset_id not in PREFERRED_VALUE_QA_ASSET_IDS:
            return InputCorpusSelectResponse(
                connected=False,
                message="该 value_qa 资产不在输入模块白名单中。",
                asset_id=asset.asset_id,
                asset_name=asset.name or asset.asset_id,
                kind=KIND_VALUE_QA,
                source_label="课题一 value_qa 预跑",
                blocking_reason=(
                    f"asset_id={asset.asset_id} 不是输入模块允许的预跑语料。"
                    f"允许列表：{', '.join(PREFERRED_VALUE_QA_ASSET_IDS)}"
                ),
                next_action=(
                    "请选择官方预跑包 "
                    f"{PREFERRED_VALUE_QA_ASSET_IDS[0]} 或 {PREFERRED_VALUE_QA_ASSET_IDS[1]}。"
                ),
            )
        return await _select_value_qa(db, asset=asset, limit=limit)

    return InputCorpusSelectResponse(
        connected=False,
        message="该资产不是输入模块支持的预跑语料类型。",
        asset_id=asset.asset_id,
        asset_name=asset.name or asset.asset_id,
        kind=resolved_kind,
        blocking_reason=f"unsupported kind={resolved_kind}",
        next_action="请选择课题一 value_qa 或课题二静态风险兜底语料。",
    )


async def _select_value_qa(
    db: AsyncSession,
    *,
    asset: BenchmarkAsset,
    limit: int,
) -> InputCorpusSelectResponse:
    try:
        listed = await BenchmarkTopic1ValueQaSampleService().list_groups(
            db,
            asset_id=asset.asset_id,
            limit=max(1, min(limit, VALUE_QA_MAX_RECORDS)),
            offset=0,
        )
    except BenchmarkTopic1ValueQaSampleError as exc:
        return InputCorpusSelectResponse(
            connected=False,
            message="课题一 value_qa 资产无法读取样本。",
            asset_id=asset.asset_id,
            asset_name=asset.name or asset.asset_id,
            kind=KIND_VALUE_QA,
            source_label="课题一 value_qa 预跑",
            blocking_reason=str(exc),
            next_action="检查该资产 artifacts 是否包含 samples.jsonl / group_preview.jsonl。",
        )

    records: list[InputCorpusRecord] = []
    for group in listed.get("groups", []):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("group_id") or "")
        levels = group.get("levels") if isinstance(group.get("levels"), dict) else {}
        for level_name, level in levels.items():
            if not isinstance(level, dict):
                continue
            question = str(level.get("question_preview") or "").strip()
            answer = str(level.get("answer_preview") or "").strip()
            text = "\n".join(part for part in (question, answer) if part).strip()
            if not text:
                continue
            records.append(
                InputCorpusRecord(
                    id=f"{group_id}-{level_name}-{level.get('sample_id') or len(records)}",
                    text=text,
                    meta={
                        "group_id": group_id,
                        "quality_level": level_name,
                        "topic": str(group.get("topic") or ""),
                        "primary_dimension": str(group.get("primary_dimension") or ""),
                        "secondary_dimension": str(group.get("secondary_dimension") or ""),
                        "track": "value",
                    },
                )
            )
            if len(records) >= limit:
                break
        if len(records) >= limit:
            break

    return InputCorpusSelectResponse(
        connected=True,
        message=f"已选用课题一 value_qa 语料：{asset.name or asset.asset_id}",
        asset_id=asset.asset_id,
        asset_name=asset.name or asset.asset_id,
        kind=KIND_VALUE_QA,
        source_label="课题一 value_qa 预跑",
        total=len(records),
        records=records,
        next_action="该语料仅用于价值轨；血缘图谱也可选用本侧语料展示。",
    )


def _select_risk_static(*, limit: int) -> InputCorpusSelectResponse:
    path = _resolve_risk_static_path()
    if path is None:
        return InputCorpusSelectResponse(
            connected=False,
            message="未找到课题二静态风险兜底语料文件。",
            asset_id=RISK_STATIC_ASSET_ID,
            asset_name="课题二 DynBench400 静态兜底",
            kind=KIND_RISK_STATIC,
            source_label="课题二静态预跑",
            blocking_reason=f"missing {RISK_STATIC_FILENAME}",
            next_action=(
                "请将 input_dynbench400_eval_schema.jsonl 放到 "
                "web/backend/data/input_corpora/（课题五仓库内）。"
            ),
        )

    records: list[InputCorpusRecord] = []
    total_in_file = 0
    max_records = max(1, min(limit, RISK_STATIC_MAX_RECORDS))
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                total_in_file += 1
                if len(records) >= max_records:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                text = str(payload.get("text") or "").strip()
                if not text:
                    continue
                sample_id = str(payload.get("id") or f"dynbench-{len(records) + 1}")
                original_label = str(payload.get("original_label") or "").strip().lower()
                harm_l1 = str(payload.get("harm_category_L1") or "").strip()
                harm_l2 = str(payload.get("harm_category_L2") or "").strip()
                records.append(
                    InputCorpusRecord(
                        id=sample_id,
                        text=text,
                        meta={
                            "track": "risk",
                            "original_label": original_label,
                            "harm_category_l1": harm_l1,
                            "harm_category_L1": harm_l1,
                            "harm_category_l2": harm_l2,
                            "harm_category_L2": harm_l2,
                            "is_risky": "true" if original_label == "unsafe" else "false",
                            "source": str(payload.get("source") or "dynbench400"),
                        },
                    )
                )
    except OSError as exc:
        return InputCorpusSelectResponse(
            connected=False,
            message="读取课题二静态风险兜底语料失败。",
            asset_id=RISK_STATIC_ASSET_ID,
            asset_name="课题二 DynBench400 静态兜底",
            kind=KIND_RISK_STATIC,
            source_label="课题二静态预跑",
            blocking_reason=str(exc),
            next_action="检查 web/backend/data/input_corpora 下文件权限与编码。",
        )

    if not records:
        return InputCorpusSelectResponse(
            connected=False,
            message="课题二静态风险兜底语料为空或无法解析。",
            asset_id=RISK_STATIC_ASSET_ID,
            asset_name="课题二 DynBench400 静态兜底",
            kind=KIND_RISK_STATIC,
            source_label="课题二静态预跑",
            blocking_reason="empty_or_unparseable",
            next_action="确认 jsonl 含 text / original_label / harm_category_L1 字段。",
        )

    shown = len(records)
    label_total = total_in_file or shown
    if shown >= label_total:
        message = f"已选用课题二静态风险兜底：全部 {shown} 条。"
    else:
        message = f"已选用课题二静态风险兜底：展示 {shown} / {label_total} 条。"
    return InputCorpusSelectResponse(
        connected=True,
        message=message,
        asset_id=RISK_STATIC_ASSET_ID,
        asset_name="课题二 DynBench400 静态兜底",
        kind=KIND_RISK_STATIC,
        source_label="课题二静态预跑",
        total=shown,
        records=records,
        next_action="风险轨默认展示静态标签；也可再调用 Activation Probe（neuron）实时识别。",
    )


def _read_risk_static_all() -> list[dict[str, Any]]:
    path = _resolve_risk_static_path()
    if path is None:
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                text = str(payload.get("text") or "").strip()
                if not text:
                    continue
                original_label = str(payload.get("original_label") or "").strip().lower()
                records.append(
                    {
                        "sample_id": str(payload.get("id") or "").strip(),
                        "text": text,
                        "reference_label": original_label,
                        "original_label": original_label,
                        "harm_category_L1": str(payload.get("harm_category_L1") or "").strip(),
                        "harm_category_L2": str(payload.get("harm_category_L2") or "").strip(),
                        "source": str(payload.get("source") or "dynbench400"),
                        "is_risky": original_label == "unsafe",
                    }
                )
    except OSError:
        return []
    return records


def _normalize_match_value(value: str | None) -> str | None:
    """Normalize a filter value for case-insensitive, whitespace-insensitive
    matching. Display values stay untouched; only comparisons use this form."""
    if value is None:
        return None
    normalized = " ".join(str(value).strip().casefold().split())
    return normalized or None


def _filter_risk_records(
    records: list[dict[str, Any]],
    *,
    keyword: str | None,
    reference_label: str | None,
    source: str | None,
    harm_category_L1: str | None,
    harm_category_L2: str | None,
) -> list[dict[str, Any]]:
    normalized_keyword = _normalize_match_value(keyword)
    normalized_label = _normalize_match_value(reference_label)
    normalized_source = _normalize_match_value(source)
    normalized_l1 = _normalize_match_value(harm_category_L1)
    normalized_l2 = _normalize_match_value(harm_category_L2)

    filtered: list[dict[str, Any]] = []
    for record in records:
        if normalized_label and _normalize_match_value(record["reference_label"]) != normalized_label:
            continue
        if normalized_source and _normalize_match_value(record["source"]) != normalized_source:
            continue
        if normalized_l1 and _normalize_match_value(record["harm_category_L1"]) != normalized_l1:
            continue
        if normalized_l2 and _normalize_match_value(record["harm_category_L2"]) != normalized_l2:
            continue
        if normalized_keyword:
            haystack = "\n".join((record["text"], record["sample_id"])).casefold()
            if normalized_keyword not in haystack:
                continue
        filtered.append(record)
    return filtered


def list_risk_static_records(
    *,
    keyword: str | None = None,
    reference_label: str | None = None,
    source: str | None = None,
    harm_category_L1: str | None = None,
    harm_category_L2: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    available = _resolve_risk_static_path() is not None
    if not available:
        return {
            "available": False,
            "total": 0,
            "limit": 0,
            "offset": 0,
            "records": [],
        }
    records = _read_risk_static_all()
    filtered = _filter_risk_records(
        records,
        keyword=keyword,
        reference_label=reference_label,
        source=source,
        harm_category_L1=harm_category_L1,
        harm_category_L2=harm_category_L2,
    )
    safe_limit = max(1, min(limit, RISK_STATIC_MAX_RECORDS))
    safe_offset = max(0, offset)
    page = filtered[safe_offset : safe_offset + safe_limit]
    return {
        "available": True,
        "total": len(filtered),
        "limit": safe_limit,
        "offset": safe_offset,
        "records": list(page),
    }


def risk_static_overview() -> dict[str, Any]:
    available = _resolve_risk_static_path() is not None
    if not available:
        return {
            "available": False,
            "sample_count": 0,
            "reference_label_distribution": {},
            "harm_category_L1_distribution": {},
            "harm_category_L2_distribution": {},
            "source_distribution": {},
        }
    records = _read_risk_static_all()
    return {
        "available": True,
        "sample_count": len(records),
        "reference_label_distribution": dict(Counter(r["reference_label"] for r in records)),
        "harm_category_L1_distribution": dict(Counter(r["harm_category_L1"] for r in records)),
        "harm_category_L2_distribution": dict(Counter(r["harm_category_L2"] for r in records)),
        "source_distribution": dict(Counter(r["source"] for r in records)),
    }


def _risk_static_catalog_item() -> InputCorpusCatalogItem | None:
    path = _resolve_risk_static_path()
    if path is None:
        return None
    sample_count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    sample_count += 1
    except OSError:
        return None
    return InputCorpusCatalogItem(
        asset_id=RISK_STATIC_ASSET_ID,
        name=RISK_STATIC_ASSET_NAME,
        kind=KIND_RISK_STATIC,
        source_label="课题二静态预跑",
        sample_count=sample_count,
        ready=True,
        description=(
            "风险识别静态兜底语料（text / harm_category_L1 / original_label）；"
            "仅绑定到风险轨道，默认可直接展示预跑结论。"
        ),
        track_hint="风险轨",
        track="risk",
    )


def _resolve_risk_static_path() -> Path | None:
    """Resolve dynbench400 static corpus from in-repo paths only."""
    here = Path(__file__).resolve()
    backend_root = here.parents[2]  # .../web/backend
    project_root = here.parents[4]  # .../Project_5_LLM_Content_Safety_Governance_Web
    candidates = [
        backend_root / "data" / "input_corpora" / RISK_STATIC_FILENAME,
        backend_root / "data" / RISK_STATIC_FILENAME,
        project_root / "data" / "input_corpora" / RISK_STATIC_FILENAME,
        project_root / "data" / RISK_STATIC_FILENAME,
        Path.cwd() / "data" / "input_corpora" / RISK_STATIC_FILENAME,
        Path.cwd() / "data" / RISK_STATIC_FILENAME,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def risk_static_content_sha256() -> str | None:
    """SHA-256 of the DynBench400 jsonl file bytes (governance freeze helper).

    Not part of the ``/data-input`` catalog list response shape.
    """
    path = _resolve_risk_static_path()
    if path is None:
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def build_dynbench400_evaluation_object() -> dict[str, Any]:
    """Freezable evaluation-object metadata for DynBench400 input eval (#92).

    Additive helper only — catalog list / select contracts stay unchanged.
    """
    content_sha256 = risk_static_content_sha256() or ""
    return {
        "asset_id": RISK_STATIC_ASSET_ID,
        "name": RISK_STATIC_ASSET_NAME,
        "filename": RISK_STATIC_FILENAME,
        "content_sha256": content_sha256,
        "disclosure_level": "internal_validation",
        "source_missing": True,
        "licence_missing": True,
        "source_message": (
            "评测包未登记独立来源元数据；样本级 source 字段仅作语料内标注，"
            "不得当作包级出处证明。"
        ),
        "licence_message": (
            "评测包未登记 licence / 授权元数据；本轮仅作平台内部验证用途。"
        ),
    }


def _detect_kind(asset: BenchmarkAsset) -> str:
    manifest = _loads_json_object(asset.manifest_json)
    if manifest.get("benchmark_type") == KIND_VALUE_QA:
        return KIND_VALUE_QA
    return str(manifest.get("benchmark_type") or "unknown")


def _value_qa_asset_files_ready(asset: BenchmarkAsset) -> bool:
    root = Path(str(asset.artifact_dir or "").strip())
    if not root.is_dir():
        return False
    return (root / "samples.jsonl").is_file() and (root / "group_preview.jsonl").is_file()


def _catalog_sort_key(item: InputCorpusCatalogItem) -> tuple[int, int, int, str]:
    track_rank = 0 if item.track == "value" else 1 if item.track == "risk" else 2
    preferred_rank = 0 if item.asset_id in PREFERRED_VALUE_QA_ASSET_IDS else 1
    return (track_rank, preferred_rank, 0 if item.ready else 1, item.name)


def _manifest_int(manifest: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = manifest.get(key)
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return 0


def _loads_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
