"""Create a completed, frozen review of the Topic 3 cultural prerun record."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.topic3.cultural_assessment import load_assessment_review_evidence
from app.db.models import (
    BenchmarkAsset,
    GovernanceCompletionRecord,
    GovernanceMessage,
    GovernanceTask,
    utc_now,
)
from app.schemas.governance import (
    CULTURAL_PRERUN_REVIEW_CAPABILITY,
    CULTURAL_PRERUN_REVIEW_MESSAGE_KIND,
    CulturalPrerunReviewReport,
    CulturalReviewIssue,
    CulturalReviewIssueLists,
    CulturalSourceMetric,
    GovernanceReportEnvelope,
    GovernanceReportStatus,
)
from app.services.governance_product_metrics import emit_product_event
from app.services.governance_system_record_service import (
    build_cultural_system_record_detail,
    get_cultural_system_record_asset,
)


CAPABILITY_VERSION = "v1"
STATIC_VIEW_ID = "ui_batch_30_direct_vs_agent"
EXPECTED_SAMPLE_COUNT = 30
CULTURAL_REVIEW_UNSUPPORTED_REASON = (
    "该记录不支持审阅：未登记到受支持的静态对比视图。"
)
# Explicit record → static-view registry. Do not infer support from sample_id
# overlap; only listed asset IDs or dataset IDs may freeze a view.
CULTURAL_REVIEW_VIEW_BY_ASSET_ID = {
    "topic3_cultural_ui_batch_30": STATIC_VIEW_ID,
    "topic3_cultural_corpus_ui_batch_20260711": STATIC_VIEW_ID,
}
CULTURAL_REVIEW_VIEW_BY_DATASET_ID = {
    "cultural_evaluation_ui_batch_30": STATIC_VIEW_ID,
}


class CulturalReviewNotFoundError(ValueError):
    pass


class CulturalReviewConflictError(ValueError):
    pass


class CulturalReviewEvidenceError(ValueError):
    pass


def _manifest_dict(asset: BenchmarkAsset) -> dict[str, Any]:
    try:
        payload = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_cultural_review_view_id(asset: BenchmarkAsset) -> str | None:
    """Return the registered static view for this record, or None if unbound."""
    mapped = CULTURAL_REVIEW_VIEW_BY_ASSET_ID.get(asset.asset_id)
    if mapped:
        return mapped
    dataset_id = str(_manifest_dict(asset).get("dataset_id") or "").strip()
    return CULTURAL_REVIEW_VIEW_BY_DATASET_ID.get(dataset_id)


def cultural_review_support_fields(asset: BenchmarkAsset) -> dict[str, Any]:
    view_id = resolve_cultural_review_view_id(asset)
    if view_id:
        return {
            "review_supported": True,
            "review_view_id": view_id,
            "review_unavailable_reason": "",
        }
    return {
        "review_supported": False,
        "review_view_id": None,
        "review_unavailable_reason": CULTURAL_REVIEW_UNSUPPORTED_REASON,
    }


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _row_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("sample_id") or "").strip() for row in rows]


def _asset_sample_ids(asset: BenchmarkAsset) -> list[str]:
    path = Path(asset.artifact_dir or "") / "samples.jsonl"
    if not path.is_file():
        return []
    ids: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            ids.append(str(row.get("sample_id") or row.get("id") or "").strip())
    return ids


def _warning(code: str, message: str, **facts: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **facts}


def _population_warnings(
    *,
    asset_ids: list[str],
    corpus_rows: list[dict[str, Any]],
    direct_rows: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    populations = {
        "record_corpus": asset_ids,
        "assessment_corpus": _row_ids(corpus_rows),
        "direct": _row_ids(direct_rows),
        "three_agent": _row_ids(agent_rows),
    }
    warnings: list[dict[str, Any]] = []
    for name, ids in populations.items():
        if len(ids) != EXPECTED_SAMPLE_COUNT:
            warnings.append(
                _warning(
                    "sample_count_mismatch",
                    f"{name} 应为 {EXPECTED_SAMPLE_COUNT} 条，实际为 {len(ids)} 条。",
                    population=name,
                    expected=EXPECTED_SAMPLE_COUNT,
                    actual=len(ids),
                )
            )
        missing_ids = sum(1 for sample_id in ids if not sample_id)
        if missing_ids:
            warnings.append(
                _warning(
                    "missing_sample_id",
                    f"{name} 有 {missing_ids} 条记录缺少 sample_id。",
                    population=name,
                    count=missing_ids,
                )
            )
        duplicates = sorted(
            sample_id
            for sample_id, count in Counter(ids).items()
            if sample_id and count > 1
        )
        if duplicates:
            warnings.append(
                _warning(
                    "duplicate_sample_id",
                    f"{name} 存在重复 sample_id。",
                    population=name,
                    sample_ids=duplicates,
                )
            )

    reference = set(populations["assessment_corpus"])
    for name in ("record_corpus", "direct", "three_agent"):
        current = set(populations[name])
        if current != reference:
            warnings.append(
                _warning(
                    "sample_identity_mismatch",
                    f"{name} 与评测语料的 sample_id 集合不一致。",
                    population=name,
                    missing=sorted(reference - current),
                    extra=sorted(current - reference),
                )
            )
    return warnings


def _reason_contradicts_score(score: Any, reason: str) -> bool:
    try:
        numeric = int(score)
    except (TypeError, ValueError):
        return True
    positive = (
        "正确识别",
        "明确提到并正确",
        "具有实质文化响应",
        "三个维度均通过",
    )
    # Check negative phrases first: they contain positive substrings
    # (e.g. 「未正确识别」 contains 「正确识别」).
    negative = ("未正确识别", "没有正确识别", "不具有实质文化响应")
    if numeric == 0:
        if any(token in reason for token in negative):
            return False
        return any(token in reason for token in positive)
    if numeric == 1:
        return any(token in reason for token in negative)
    return True


def _judge_warnings(
    direct_rows: list[dict[str, Any]], agent_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for method, rows in (("direct", direct_rows), ("three_agent", agent_rows)):
        for row in rows:
            for dimension in ("ethnic_group_judge", "cultural_difference_judge"):
                judge = row.get(dimension)
                if not isinstance(judge, dict):
                    warnings.append(
                        _warning(
                            "judge_result_missing",
                            "Judge 结果缺失或格式错误。",
                            method=method,
                            sample_id=str(row.get("sample_id") or ""),
                            dimension=dimension,
                        )
                    )
                    continue
                reason = str(judge.get("reason") or "")
                if not reason or _reason_contradicts_score(judge.get("score"), reason):
                    warnings.append(
                        _warning(
                            "judge_score_reason_inconsistent",
                            "Judge 分数与理由缺失或语义矛盾；保留来源分数，不重新判分。",
                            method=method,
                            sample_id=str(row.get("sample_id") or ""),
                            dimension=dimension,
                            score=judge.get("score"),
                        )
                    )
    return warnings


def _metric(method: str, label: str, summary: dict[str, Any]) -> CulturalSourceMetric:
    return CulturalSourceMetric(
        method=method,
        label=label,
        ethnic_recognition_rate=float(summary.get("ethnic_group_metric_rate") or 0),
        cultural_specificity_rate=float(summary.get("cultural_difference_rate") or 0),
        composite_pass_rate=float(summary.get("composite_pass_rate") or 0),
        composite_percentage=float(summary.get("composite_percentage") or 0),
        composite_pass_count=int(summary.get("composite_pass_count") or 0),
        total_samples=int(summary.get("total_samples") or 0),
    )


_DIMENSION_TO_CATEGORY = {
    "ethnic_recognition": "ethnic_recognition_gap",
    "cultural_specificity": "cultural_specificity_gap",
}
_DIMENSION_LABEL = {
    "ethnic_recognition": "民族识别",
    "cultural_specificity": "文化特异性",
    "ethnic_group_judge": "民族识别",
    "cultural_difference_judge": "文化特异性",
}
_METHOD_LABEL = {"direct": "Direct", "three_agent": "3-Agent"}


def _score_value(judge: dict[str, Any]) -> int | None:
    try:
        return int(judge.get("score"))
    except (TypeError, ValueError):
        return None


def _build_issue_lists(
    *,
    bindings: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> CulturalReviewIssueLists:
    """Split content-governance findings from evaluation-integrity defects (#89)."""
    integrity: list[CulturalReviewIssue] = []
    contradicted: set[tuple[str, str, str]] = set()
    for index, warning in enumerate(warnings):
        sample_id = str(warning.get("sample_id") or "")
        method = warning.get("method")
        dimension = warning.get("dimension")
        method_s = str(method) if method else None
        dimension_s = str(dimension) if dimension else None
        if (
            warning.get("code") == "judge_score_reason_inconsistent"
            and sample_id
            and method_s
            and dimension_s
        ):
            contradicted.add((sample_id, method_s, dimension_s))
        integrity.append(
            CulturalReviewIssue(
                issue_id=f"integrity-{index + 1}-{warning.get('code') or 'warning'}",
                list_kind="integrity",
                category=str(warning.get("code") or "integrity_warning"),
                sample_id=sample_id,
                method=method_s,
                dimension=dimension_s,
                judgment=str(warning.get("message") or ""),
                evidence={
                    key: value
                    for key, value in warning.items()
                    if key not in {"code", "message"}
                },
                source_refs=[],
            )
        )

    content: list[CulturalReviewIssue] = []
    content_index = 0
    for binding in bindings:
        sample_id = str(binding.get("sample_id") or "")
        judge_block = binding.get("judge") or {}
        for method in ("direct", "three_agent"):
            method_judge = judge_block.get(method) or {}
            for dim_key, category in _DIMENSION_TO_CATEGORY.items():
                judge = method_judge.get(dim_key) or {}
                if not isinstance(judge, dict) or not judge:
                    continue
                reason = str(judge.get("reason") or "")
                score = _score_value(judge)
                warning_dim = (
                    "ethnic_group_judge"
                    if dim_key == "ethnic_recognition"
                    else "cultural_difference_judge"
                )
                if (sample_id, method, warning_dim) in contradicted:
                    continue
                if score != 0 or not reason or _reason_contradicts_score(score, reason):
                    continue
                content_index += 1
                content.append(
                    CulturalReviewIssue(
                        issue_id=f"content-{content_index}-{category}",
                        list_kind="content",
                        category=category,
                        sample_id=sample_id,
                        method=method,
                        dimension=dim_key,
                        judgment=(
                            f"{_METHOD_LABEL.get(method, method)} "
                            f"{_DIMENSION_LABEL.get(dim_key, dim_key)}未通过："
                            f"{reason}"
                        ),
                        evidence={
                            "direct": (judge_block.get("direct") or {}),
                            "three_agent": (judge_block.get("three_agent") or {}),
                            "focus": {
                                "method": method,
                                "dimension": dim_key,
                                "score": score,
                                "reason": reason,
                            },
                        },
                        source_refs=[
                            {
                                "ref_type": "frozen_sample",
                                "ref_id": sample_id,
                                "name": sample_id,
                            }
                        ],
                    )
                )
    return CulturalReviewIssueLists(content=content, integrity=integrity)


def _run_identity(evidence: dict[str, Any]) -> dict[str, Any]:
    direct_config = evidence["direct"]["config"]
    agent_config = evidence["agent"]["config"]
    judges = direct_config.get("judges") if isinstance(direct_config, dict) else {}
    return {
        "direct": {
            "run_id": str(direct_config.get("run_id") or ""),
            "method": "Direct",
            "model": str((direct_config.get("target") or {}).get("model") or ""),
        },
        "three_agent": {
            "run_id": str(agent_config.get("run_id") or ""),
            "method": "3-Agent",
            "pipeline": "culture_recognition -> knowledge_retrieval -> response_composition",
        },
        "judge": {
            "ethnic_recognition_model": str(
                ((judges or {}).get("ethnic_group_judge") or {}).get("model") or ""
            ),
            "cultural_specificity_model": str(
                ((judges or {}).get("cultural_difference_judge") or {}).get("model")
                or ""
            ),
            "scope": ["ethnic_recognition", "cultural_specificity"],
        },
    }


def build_cultural_review_report(
    *, task_id: str, asset: BenchmarkAsset, evidence: dict[str, Any], completed_at: str
) -> CulturalPrerunReviewReport:
    detail = build_cultural_system_record_detail(asset)
    corpus_rows = list(evidence["dataset"].get("rows") or [])
    direct_rows = list(evidence["direct"].get("rows") or [])
    agent_rows = list(evidence["agent"].get("rows") or [])
    warnings = _population_warnings(
        asset_ids=_asset_sample_ids(asset),
        corpus_rows=corpus_rows,
        direct_rows=direct_rows,
        agent_rows=agent_rows,
    )
    warnings.extend(_judge_warnings(direct_rows, agent_rows))

    corpus_by_id = {str(row.get("sample_id") or ""): row for row in corpus_rows}
    direct_by_id = {str(row.get("sample_id") or ""): row for row in direct_rows}
    agent_by_id = {str(row.get("sample_id") or ""): row for row in agent_rows}
    bindings = []
    for sample_id in sorted(set(corpus_by_id) | set(direct_by_id) | set(agent_by_id)):
        direct = direct_by_id.get(sample_id) or {}
        agent = agent_by_id.get(sample_id) or {}
        bindings.append(
            {
                "sample_id": sample_id,
                "corpus_sha256": _canonical_digest(corpus_by_id.get(sample_id) or {}),
                "direct_output_sha256": _canonical_digest(
                    {key: direct.get(key) for key in ("answer_a", "answer_b", "target_metadata")}
                ),
                "three_agent_output_sha256": _canonical_digest(
                    {key: agent.get(key) for key in ("answer_a", "answer_b", "target_metadata")}
                ),
                "judge": {
                    "direct": {
                        "ethnic_recognition": direct.get("ethnic_group_judge") or {},
                        "cultural_specificity": direct.get("cultural_difference_judge") or {},
                    },
                    "three_agent": {
                        "ethnic_recognition": agent.get("ethnic_group_judge") or {},
                        "cultural_specificity": agent.get("cultural_difference_judge") or {},
                    },
                },
            }
        )

    integrity_code = "passed" if not warnings else "warning"
    delivery_ready = not warnings
    envelope = GovernanceReportEnvelope(
        evaluated_object={
            "record_id": detail["record_id"],
            "record_name": detail["name"],
            "record_version": detail["record_version"],
            "dataset_id": evidence["view"].get("dataset_id"),
            "dataset_label": evidence["view"].get("dataset_label"),
            # The report states the scope it actually froze. `EXPECTED_SAMPLE_COUNT`
            # is only the target used for integrity warnings, so a population
            # defect must never be papered over by reporting the nominal 30.
            "sample_count": len(bindings),
        },
        source_identity={
            "source_repo": detail["source_repo"],
            "source_commit": detail["source_commit"],
            "asset_sha256": detail["asset_sha256"],
            "static_view_id": evidence["view"].get("id"),
            "evidence_files": evidence.get("files") or [],
        },
        run_identity=_run_identity(evidence),
        evaluation_run_status=GovernanceReportStatus(
            code="completed",
            label="来源评测已完成",
            detail="审阅读取既有 Direct、3-Agent 与 Judge 结果，没有重新运行模型。",
        ),
        integrity_status=GovernanceReportStatus(
            code=integrity_code,
            label="完整性通过" if not warnings else "存在完整性告警",
            detail=f"共 {len(warnings)} 条告警；告警不会改写来源指标。",
        ),
        delivery_readiness=GovernanceReportStatus(
            code="ready" if delivery_ready else "not_ready",
            label="可交付" if delivery_ready else "暂不可作为无保留交付结论",
            detail="交付准备度由证据完整性独立决定，与审阅任务是否完成无关。",
        ),
        review_task_status=GovernanceReportStatus(
            code="completed", label="审阅任务已完成"
        ),
        claim_boundaries=[
            "仅比较民族识别与文化特异性两项来源评测指标。",
            "3-Agent 表示文化识别、知识检索、回答生成三个协作阶段，不是三个评估器。",
            "不评价事实正确性、安全性或合规性。",
        ],
        limitations=[
            "来源指标由上游 Judge 产生，平台仅保留并验证证据一致性。",
            "完整性告警不触发重新判分，也不修改底层评测状态。",
            "本任务不重新调用生成模型或 Judge。",
        ],
    )
    source_refs = list(detail.get("source_refs") or [])
    source_refs.extend(
        {
            "ref_type": "cultural_assessment_evidence",
            "ref_id": str(item.get("sha256") or ""),
            "name": str(item.get("path") or item.get("role") or ""),
            "source_repo": "Project_3_Cultural_Diversity_Assessment_Tool",
            "source_commit": "",
        }
        for item in evidence.get("files") or []
    )
    issue_lists = _build_issue_lists(bindings=bindings, warnings=warnings)
    return CulturalPrerunReviewReport(
        task_id=task_id,
        envelope=envelope,
        source_metrics=[
            _metric("direct", "Direct", evidence["direct"].get("summary") or {}),
            _metric(
                "three_agent", "3-Agent", evidence["agent"].get("summary") or {}
            ),
        ],
        three_agent_stages=[
            {"key": "culture_recognition", "label": "文化识别", "description": "识别民族背景与文化问题。"},
            {"key": "knowledge_retrieval", "label": "知识检索", "description": "检索与场景相关的文化知识。"},
            {"key": "response_composition", "label": "回答生成", "description": "基于识别和知识组织最终回答。"},
        ],
        integrity_warnings=warnings,
        issue_lists=issue_lists,
        frozen_evidence={
            "sample_count": len(bindings),
            "sample_ids": [item["sample_id"] for item in bindings],
            "bindings": bindings,
            "evidence_files": evidence.get("files") or [],
        },
        source_refs=source_refs,
        completed_at=completed_at,
    )


async def create_cultural_prerun_review(
    db: AsyncSession,
    *,
    client_id: str,
    session: Any,
    record_id: str,
    record_version: str,
) -> dict[str, Any]:
    if session.domain != "output":
        raise CulturalReviewConflictError("文化预跑审阅任务只能在输出内容治理会话创建")
    asset = await get_cultural_system_record_asset(db, record_id)
    if asset is None:
        raise CulturalReviewNotFoundError("文化多样性系统预跑记录不存在")
    detail = build_cultural_system_record_detail(asset)
    if detail["record_version"] != record_version:
        raise CulturalReviewConflictError("来源记录版本已变化，请刷新详情后重新创建审阅任务")
    view_id = resolve_cultural_review_view_id(asset)
    if not view_id:
        raise CulturalReviewConflictError(CULTURAL_REVIEW_UNSUPPORTED_REASON)
    try:
        evidence = load_assessment_review_evidence(view_id)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise CulturalReviewEvidenceError(f"文化预跑评测证据不可用：{error}") from error

    now = utc_now()
    task_id = str(uuid4())
    completed_at = now.isoformat() + "Z"
    report = build_cultural_review_report(
        task_id=task_id, asset=asset, evidence=evidence, completed_at=completed_at
    )
    snapshot = report.model_dump()
    task = GovernanceTask(
        task_id=task_id,
        client_id=client_id,
        session_id=session.session_id,
        capability=CULTURAL_PRERUN_REVIEW_CAPABILITY,
        parameters_json=json.dumps(
            {"record_id": record_id, "record_version": record_version},
            ensure_ascii=False,
        ),
        status="completed",
        provider="static_prerun_review",
        model="",
        latency_ms=0,
        parse_status="not_applicable",
        created_at=now,
        finished_at=now,
    )
    message = GovernanceMessage(
        session_id=session.session_id,
        client_id=client_id,
        request_id=str(uuid4()),
        role="assistant",
        kind=CULTURAL_PRERUN_REVIEW_MESSAGE_KIND,
        content=report.render_content(),
        payload_json=json.dumps(snapshot, ensure_ascii=False),
        created_at=now,
    )
    session.updated_at = now
    db.add(task)
    db.add(message)
    await db.flush()
    db.add(
        GovernanceCompletionRecord(
            completion_id=str(uuid4()),
            task_id=task_id,
            session_id=session.session_id,
            message_id=message.id,
            capability=CULTURAL_PRERUN_REVIEW_CAPABILITY,
            capability_version=CAPABILITY_VERSION,
            result_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
            source_refs_json=json.dumps(snapshot["source_refs"], ensure_ascii=False),
            completed_at=now,
        )
    )
    await emit_product_event(
        db,
        "task_completed",
        session_id=session.session_id,
        task_id=task_id,
        attributes={
            "domain": "output",
            "capability": CULTURAL_PRERUN_REVIEW_CAPABILITY,
            "status": "completed",
            "provider": "static_prerun_review",
        },
        occurred_at=now,
    )
    await db.commit()
    return snapshot
