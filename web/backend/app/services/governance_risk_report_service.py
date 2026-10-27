"""Input-risk online re-detection report builder (#164 T3 / #167).

The merged v2 ``risk_corpus_rescan`` surface: the completed product projection is
a ``GovernanceReportEnvelope`` with dual problem lists (risk_hit /
reference_label_disagreement). Reference labels are not treated as ground truth;
no accuracy metrics are emitted.

Evaluator choice (``activation_probe`` default vs ``keyword``) is frozen into
scope, drives independent preflight / run identity / issue categories, and
never silently merges results across evaluators (#111).

Failure / partial paths (#110) enrich notices and reports with sample-range
diagnostics so a frozen-sample failure never masquerades as a full completed
governance eval record.

This module owns the one surviving input-risk report contract; the retired
DynBench400-only entry and its second report shape are gone (#169, W5/W7), so
the name follows the capability it now serves.
"""

from __future__ import annotations

from typing import Any, Literal

from app.schemas.governance import (
    RISK_RESCAN_CAPABILITY,
    RISK_RESCAN_CAPABILITY_VERSION,
    RISK_RESCAN_STATUS_CANCELLING,
    RISK_RESCAN_STATUS_CANCELLED,
    GovernanceReportEnvelope,
    GovernanceReportStatus,
    RiskCorpusRescanNoticeResult,
    RiskCorpusRescanRunResult,
    RiskRescanExecutionSummary,
    RiskRescanFailureDiagnostics,
    RiskRescanIssue,
    RiskRescanIssueLists,
)
from app.services.data_input_corpus_catalog_service import (
    build_dynbench400_evaluation_object,
)
from app.services.input_risk_detection_service import (
    METHOD_ACTIVATION_PROBE,
    METHOD_KEYWORD,
    resolve_input_risk_method,
)

RiskRescanEvaluator = Literal["activation_probe", "keyword"]

_EVALUATOR_LABELS = {
    METHOD_ACTIVATION_PROBE: "Activation Probe",
    METHOD_KEYWORD: "FilterGuard keyword",
}
_COMPLETED_SAMPLE_STATUSES = frozenset({"consistent", "inconsistent"})


def resolve_rescan_evaluator(
    value: str | None = None, *, scope: dict[str, Any] | None = None
) -> RiskRescanEvaluator:
    """Normalize a frozen evaluator choice; default remains activation_probe."""
    raw = value
    if raw is None and scope is not None:
        raw = scope.get("evaluator")
    resolved = resolve_input_risk_method(str(raw) if raw is not None else None)
    if resolved == METHOD_KEYWORD:
        return METHOD_KEYWORD
    return METHOD_ACTIVATION_PROBE


def evaluator_display_name(evaluator: str) -> str:
    return _EVALUATOR_LABELS.get(evaluator, evaluator or "Activation Probe")


def _build_issue_lists(
    samples: list[dict[str, Any]], *, evaluator: str
) -> RiskRescanIssueLists:
    label = evaluator_display_name(evaluator)
    if evaluator == METHOD_KEYWORD:
        risk_category = "keyword_unsafe"
        disagree_category = "keyword_vs_reference_label"
    else:
        risk_category = "activation_probe_unsafe"
        disagree_category = "probe_vs_reference_label"

    risk_hit: list[RiskRescanIssue] = []
    disagreement: list[RiskRescanIssue] = []
    for sample in samples:
        sample_id = str(sample.get("sample_id") or "")
        detected = str(sample.get("detected_label") or "")
        reference = str(sample.get("reference_label") or "")
        status = str(sample.get("status") or "")
        if status == "failed" or not detected:
            continue
        source_refs = [
            {
                "ref_type": "risk_static_sample",
                "ref_id": sample_id,
                "name": sample_id,
            }
        ]
        if detected == "unsafe":
            risk_hit.append(
                RiskRescanIssue(
                    issue_id=f"risk_hit:{sample_id}",
                    list_kind="risk_hit",
                    category=risk_category,
                    sample_id=sample_id,
                    judgment=f"{label} 判定为 unsafe。",
                    reference_label=reference,
                    detected_label=detected,
                    evidence={
                        "content_digest": str(sample.get("content_digest") or ""),
                        "reason": str(sample.get("reason") or ""),
                        "evaluator": evaluator,
                    },
                    source_refs=source_refs,
                )
            )
        if (
            status == "inconsistent"
            or (reference in {"safe", "unsafe"} and detected != reference)
        ):
            disagreement.append(
                RiskRescanIssue(
                    issue_id=f"label_disagreement:{sample_id}",
                    list_kind="reference_label_disagreement",
                    category=disagree_category,
                    sample_id=sample_id,
                    judgment=(
                        f"{label} 标签 {detected} 与参考标注 "
                        f"{reference or '（空）'} 不一致。"
                    ),
                    reference_label=reference,
                    detected_label=detected,
                    evidence={
                        "content_digest": str(sample.get("content_digest") or ""),
                        "reason": str(sample.get("reason") or ""),
                        "evaluator": evaluator,
                    },
                    source_refs=source_refs,
                )
            )
    return RiskRescanIssueLists(
        risk_hit=risk_hit,
        reference_label_disagreement=disagreement,
    )


def _sample_ids_by_status(
    samples: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    completed: list[str] = []
    failed: list[str] = []
    not_executed: list[str] = []
    for sample in samples:
        sample_id = str(sample.get("sample_id") or "")
        if not sample_id:
            continue
        status = str(sample.get("status") or "")
        if status in _COMPLETED_SAMPLE_STATUSES:
            completed.append(sample_id)
        elif status == "not_executed":
            not_executed.append(sample_id)
        elif status == "failed":
            failed.append(sample_id)
    return completed, failed, not_executed


def _sample_rows_from_persisted(
    *,
    scope: dict[str, Any] | None,
    persisted: list[dict[str, Any]] | None,
    outcome_samples: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if outcome_samples:
        return list(outcome_samples)
    frozen = list((scope or {}).get("samples") or [])
    if not persisted:
        return [
            {
                "sample_id": str(sample.get("sample_id") or ""),
                "status": "not_executed",
            }
            for sample in frozen
            if str(sample.get("sample_id") or "")
        ]
    by_id = {
        str(row.get("sample_id") or ""): row
        for row in persisted
        if str(row.get("sample_id") or "")
    }
    rows: list[dict[str, Any]] = []
    for sample in frozen:
        sample_id = str(sample.get("sample_id") or "")
        if not sample_id:
            continue
        row = by_id.get(sample_id) or {}
        rows.append(
            {
                "sample_id": sample_id,
                "status": str(row.get("status") or "not_executed"),
                "reason": str(row.get("reason") or ""),
                "adapter_status": str(
                    (row.get("outcome") or {}).get("adapter_status") or ""
                ),
            }
        )
    if rows:
        return rows
    return [
        {
            "sample_id": str(row.get("sample_id") or ""),
            "status": str(row.get("status") or "not_executed"),
            "reason": str(row.get("reason") or ""),
        }
        for row in persisted
        if str(row.get("sample_id") or "")
    ]


def _infer_failure_phase(
    *,
    run_status: str,
    reason: str,
    sample_rows: list[dict[str, Any]],
    explicit_phase: str | None = None,
) -> str:
    if explicit_phase:
        return explicit_phase
    if run_status == "cancelled" or run_status == RISK_RESCAN_STATUS_CANCELLING:
        return "cancelled"
    if run_status == "timeout":
        return "timeout"
    lowered = reason.lower()
    if "不可用" in reason or "preflight" in lowered or "health" in lowered:
        return "preflight"
    completed, failed, not_executed = _sample_ids_by_status(sample_rows)
    if failed and not_executed:
        return "transport_abort"
    if failed and not completed:
        if any(
            str(row.get("adapter_status") or "") not in {"", "completed"}
            for row in sample_rows
            if str(row.get("status") or "") == "failed"
        ):
            return "transport_abort"
        return "sample_detection"
    if failed:
        return "sample_detection"
    if not_executed and not completed and not failed:
        return "preflight" if ("不可用" in reason or "未执行" in reason) else "unknown"
    return "unknown"


def _frozen_scope_snapshot(scope: dict[str, Any] | None) -> dict[str, Any]:
    scope = scope or {}
    evaluation_object = dict(scope.get("evaluation_object") or {})
    sample_ids = [
        str(sample.get("sample_id") or "")
        for sample in (scope.get("samples") or [])
        if str(sample.get("sample_id") or "")
    ]
    evaluator = resolve_rescan_evaluator(scope=scope)
    return {
        "asset_id": scope.get("asset_id"),
        "asset_name": scope.get("asset_name"),
        "filters": dict(scope.get("filters") or {}),
        "sample_ids": sample_ids,
        "sample_count": int(scope.get("sample_count") or len(sample_ids) or 0),
        "content_sha256": str(evaluation_object.get("content_sha256") or ""),
        "disclosure_level": str(
            evaluation_object.get("disclosure_level") or "internal_validation"
        ),
        "evaluator": evaluator,
    }


def _evaluator_identity(
    method: str,
    scope: dict[str, Any] | None = None,
    *,
    evaluator: str = "",
) -> dict[str, Any]:
    resolved = resolve_rescan_evaluator(evaluator or None, scope=scope)
    return {
        "capability": RISK_RESCAN_CAPABILITY,
        "method": method or resolved,
        "evaluator": resolved,
    }


def build_failure_diagnostics(
    *,
    scope: dict[str, Any] | None = None,
    run_status: str = "failed",
    reason: str = "",
    method: str = "",
    evaluator: str = "",
    persisted: list[dict[str, Any]] | None = None,
    outcome_samples: list[dict[str, Any]] | None = None,
    failure_phase: str | None = None,
) -> RiskRescanFailureDiagnostics:
    """Build append-only diagnostics for notice / partial / failed reports."""
    sample_rows = _sample_rows_from_persisted(
        scope=scope,
        persisted=persisted,
        outcome_samples=outcome_samples,
    )
    completed, failed, not_executed = _sample_ids_by_status(sample_rows)
    phase = _infer_failure_phase(
        run_status=run_status,
        reason=reason,
        sample_rows=sample_rows,
        explicit_phase=failure_phase,
    )
    fallback = "输入风险语料在线二次检测未完整完成。"
    diagnosis = reason or {
        "preflight": "评测前健康检查未通过，冻结样本未执行检测。",
        "transport_abort": "上游检测中断，后续冻结样本未执行。",
        "sample_detection": "部分或全部冻结样本检测失败。",
        "cancelled": "任务已取消，未执行样本已保留。",
        "timeout": "在线检测超时，任务未完整完成。",
        "unknown": fallback,
    }.get(phase, fallback)
    resolved_evaluator = resolve_rescan_evaluator(evaluator or None, scope=scope)
    resolved_method = method or resolved_evaluator
    return RiskRescanFailureDiagnostics(
        failure_phase=phase,  # type: ignore[arg-type]
        diagnosis=diagnosis,
        completed_sample_ids=completed,
        failed_sample_ids=failed,
        not_executed_sample_ids=not_executed,
        evaluator_identity=_evaluator_identity(
            resolved_method, scope, evaluator=resolved_evaluator
        ),
        frozen_scope_snapshot=_frozen_scope_snapshot(scope),
    )


def _is_full_completion(run_status: str, partial: bool) -> bool:
    return run_status == "completed" and not partial


def _build_envelope(
    *,
    scope: dict[str, Any],
    evaluation_object: dict[str, Any],
    sample_count: int,
    method: str,
    evaluator: str,
    issue_lists: RiskRescanIssueLists,
    run_status: str,
    partial: bool,
    diagnostics: RiskRescanFailureDiagnostics | None,
) -> GovernanceReportEnvelope:
    risk_n = len(issue_lists.risk_hit)
    disagree_n = len(issue_lists.reference_label_disagreement)
    label = evaluator_display_name(evaluator)
    full = _is_full_completion(run_status, partial)
    if full:
        evaluation_run_status = GovernanceReportStatus(
            code="completed",
            label="评测运行已完成",
            detail=f"已对全部冻结样本调用 {label}。",
        )
        review_task_status = GovernanceReportStatus(
            code="completed",
            label="输入评测任务已完成",
        )
    elif run_status == "completed_partial" or (
        partial and run_status in {"completed", "cancelled"}
    ):
        evaluation_run_status = GovernanceReportStatus(
            code="completed_partial",
            label="评测运行部分完成",
            detail=(
                f"仅部分冻结样本完成 {label} 检测；不得视为完整治理评测完成。"
                + (
                    f" 已完成 {len(diagnostics.completed_sample_ids)} 条，"
                    f"失败 {len(diagnostics.failed_sample_ids)} 条，"
                    f"未执行 {len(diagnostics.not_executed_sample_ids)} 条。"
                    if diagnostics
                    else ""
                )
            ),
        )
        review_task_status = GovernanceReportStatus(
            code="completed_partial",
            label="输入评测任务未完整完成",
            detail="存在失败或未执行的冻结样本，可基于冻结范围重试。",
        )
    elif run_status == "cancelled":
        evaluation_run_status = GovernanceReportStatus(
            code="cancelled",
            label="评测运行已取消",
            detail="用户取消后保留已完成与未执行样本范围。",
        )
        review_task_status = GovernanceReportStatus(
            code="cancelled",
            label="输入评测任务已取消",
        )
    elif run_status == "timeout":
        evaluation_run_status = GovernanceReportStatus(
            code="timeout",
            label="评测运行超时",
            detail="在线检测超时，不得视为完整治理评测完成。",
        )
        review_task_status = GovernanceReportStatus(
            code="timeout",
            label="输入评测任务超时",
        )
    else:
        evaluation_run_status = GovernanceReportStatus(
            code="failed",
            label="评测运行失败",
            detail=(
                diagnostics.diagnosis
                if diagnostics and diagnostics.diagnosis
                else "存在冻结样本失败；不得视为完整治理评测完成。"
            ),
        )
        review_task_status = GovernanceReportStatus(
            code="failed",
            label="输入评测任务失败",
            detail="失败诊断与冻结范围快照已保留，可同范围重试。",
        )

    return GovernanceReportEnvelope(
        evaluated_object={
            "asset_id": evaluation_object.get("asset_id") or scope.get("asset_id"),
            "name": evaluation_object.get("name") or scope.get("asset_name"),
            "filename": evaluation_object.get("filename") or "",
            "sample_count": sample_count,
            "content_sha256": evaluation_object.get("content_sha256") or "",
            "disclosure_level": evaluation_object.get("disclosure_level")
            or "internal_validation",
            "source_missing": bool(evaluation_object.get("source_missing", True)),
            "licence_missing": bool(evaluation_object.get("licence_missing", True)),
        },
        source_identity={
            "asset_id": scope.get("asset_id"),
            "asset_sha256": evaluation_object.get("content_sha256") or "",
            "disclosure_level": "internal_validation",
            "source_message": evaluation_object.get("source_message") or "",
            "licence_message": evaluation_object.get("licence_message") or "",
        },
        run_identity={
            "method": method,
            "evaluator": evaluator,
            "capability": RISK_RESCAN_CAPABILITY,
            "partial": partial or not full,
            "failure_phase": diagnostics.failure_phase if diagnostics else None,
        },
        evaluation_run_status=evaluation_run_status,
        integrity_status=GovernanceReportStatus(
            code="passed",
            label="评测对象摘要已冻结",
            detail="content_sha256 与 internal_validation 披露已随预览/完成一并冻结。",
        ),
        delivery_readiness=GovernanceReportStatus(
            code="internal_only",
            label="仅内部验证",
            detail="不得作为对外准确率或合规结论交付。",
        ),
        review_task_status=review_task_status,
        claim_boundaries=[
            "本报告为输入风险语料在线二次检测视图，不评价模型整体安全性。",
            "不计算、不展示准确率、精确率、召回率或一致率等评价指标。",
            "参考标注不是已证明的真实标签（ground truth）。",
            f"风险命中清单仅表示 {label} 判定 unsafe，不等于人工确认有害。",
            f"与参考标注分歧清单仅表示 {label} 标签与语料标注不一致，不判定哪一侧正确。",
            "Activation Probe 与 keyword 评估器结果互斥独立，禁止静默合并对照。",
            "任一冻结样本失败时，本报告不是完整治理评测完成记录。",
        ],
        limitations=[
            "评测对象披露级别为 internal_validation；缺少包级来源与 licence 元数据。",
            f"问题清单规模：风险命中 {risk_n} 条，参考标注分歧 {disagree_n} 条（同一条样本可同时出现在两份清单）。",
            f"{label} 不可用时任务失败，不会降级为 mock 完成结果。",
            "单次最多 30 条冻结样本；超出部分不在本报告范围内。",
        ],
    )


def _execution_summary(samples: list[dict[str, Any]]) -> RiskRescanExecutionSummary:
    """Execution-progress facts over the persisted sample outcomes."""
    executed = sum(
        1 for sample in samples if str(sample.get("status") or "") in _COMPLETED_SAMPLE_STATUSES
    )
    failed = sum(1 for sample in samples if str(sample.get("status") or "") == "failed")
    not_executed = sum(
        1 for sample in samples if str(sample.get("status") or "") == "not_executed"
    )
    return RiskRescanExecutionSummary(
        executed_count=executed,
        failed_count=failed,
        not_executed_count=not_executed,
    )


def build_completed_payload(
    scope: dict[str, Any],
    outcome: dict[str, Any],
    task_id: str,
    completed_at: str,
    *,
    run_status: str = "completed",
    partial: bool = False,
    capability_version: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Project the merged v2 result from the frozen scope and run outcome.

    The page summary and the evidence pack both derive from this one persisted
    payload; nothing here re-reads the asset or re-runs the evaluator.
    """

    samples = list(outcome.get("samples") or [])
    evaluation_object = dict(
        scope.get("evaluation_object") or build_dynbench400_evaluation_object()
    )
    evaluator = resolve_rescan_evaluator(
        str(outcome.get("evaluator") or "") or None, scope=scope
    )
    issue_lists = _build_issue_lists(samples, evaluator=evaluator)
    method = str(outcome.get("method") or evaluator)
    full = _is_full_completion(run_status, partial)
    diagnostics: RiskRescanFailureDiagnostics | None = None
    if not full:
        failed_reason = next(
            (
                str(sample.get("reason") or "")
                for sample in samples
                if sample.get("status") == "failed" and sample.get("reason")
            ),
            "",
        )
        diagnostics = build_failure_diagnostics(
            scope=scope,
            run_status=run_status,
            reason=failed_reason or str(outcome.get("reason") or ""),
            method=method,
            evaluator=evaluator,
            outcome_samples=samples,
            failure_phase=(str(outcome.get("failure_phase") or "") or None),
        )
    envelope = _build_envelope(
        scope=scope,
        evaluation_object=evaluation_object,
        sample_count=len(samples),
        method=method,
        evaluator=evaluator,
        issue_lists=issue_lists,
        run_status=run_status,
        partial=partial,
        diagnostics=diagnostics,
    )
    common = dict(
        task_id=task_id,
        status=run_status,  # type: ignore[arg-type]
        partial=partial or not full,
        method=method,
        evaluator=evaluator,
        asset_id=scope.get("asset_id"),
        asset_name=scope.get("asset_name"),
        filters=scope.get("filters") or {},
        sample_count=len(samples),
        samples=samples,
        envelope=envelope,
        issue_lists=issue_lists,
        evaluation_object=evaluation_object,
        source_refs=scope.get("source_refs") or [],
        completed_at=completed_at,
        failure_diagnostics=diagnostics,
    )
    export_requested = bool(scope.get("export_requested"))
    summary = _execution_summary(samples)
    evaluated = envelope.evaluated_object
    content_sha256 = str(evaluated.get("content_sha256") or "")
    disclosure_level = str(evaluated.get("disclosure_level") or "internal_validation")
    integrity_facts = [
        (
            f"评测对象 content_sha256 已随冻结范围写入，披露级别 {disclosure_level}。"
            if content_sha256
            else "评测对象未提供 content_sha256，冻结范围不含内容摘要。"
        ),
        (
            f"冻结样本 {len(samples)} 条，执行完成 {summary.executed_count} 条、"
            f"失败 {summary.failed_count} 条、未执行 {summary.not_executed_count} 条；"
            "参考标注为只读比较事实，未经验证为 ground truth。"
        ),
    ]
    result = RiskCorpusRescanRunResult(
        capability_version=capability_version or RISK_RESCAN_CAPABILITY_VERSION,
        ordered_sample_ids=[str(sample.get("sample_id") or "") for sample in samples],
        execution_summary=summary,
        executor_identity=dict(scope.get("executor_identity") or {}),
        disclosure_limits=list(envelope.limitations),
        integrity_facts=integrity_facts,
        export_requested=export_requested,
        export_available=export_requested,
        export_path=(
            f"/api/governance/tasks/{task_id}/input-risk-rescan/evidence-pack"
            if export_requested
            else ""
        ),
        **common,
    )
    return dict(result.model_dump()), result.render_content()


def build_cancelling_payload(
    task_id: str, capability_version: str, *, evaluator: str = ""
) -> tuple[dict[str, Any], str]:
    reason = "取消请求已提交，正在等待当前在线二次检测步骤结束。"
    notice = RiskCorpusRescanNoticeResult(
        task_id=task_id,
        phase="cancelling",
        status=RISK_RESCAN_STATUS_CANCELLING,
        reason=reason,
        evaluator=evaluator,
    )
    payload = dict(notice.model_dump(), capability_version=capability_version)
    return payload, notice.render_content()


def build_notice_payload(
    task_id: str,
    status: str,
    reason: str,
    capability_version: str,
    *,
    evaluator: str = "",
    scope: dict[str, Any] | None = None,
    persisted: list[dict[str, Any]] | None = None,
    outcome_samples: list[dict[str, Any]] | None = None,
    method: str = "",
    failure_phase: str | None = None,
) -> tuple[dict[str, Any], str]:
    phase = "cancelled" if status == RISK_RESCAN_STATUS_CANCELLED else "failed"
    resolved_evaluator = resolve_rescan_evaluator(evaluator or None, scope=scope)
    diagnostics = build_failure_diagnostics(
        scope=scope,
        run_status=status,
        reason=reason,
        method=method or resolved_evaluator,
        evaluator=resolved_evaluator,
        persisted=persisted,
        outcome_samples=outcome_samples,
        failure_phase=failure_phase,
    )
    notice = RiskCorpusRescanNoticeResult(
        task_id=task_id,
        phase=phase,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        reason=reason,
        evaluator=resolved_evaluator,
        failure_diagnostics=diagnostics,
    )
    payload = dict(notice.model_dump(), capability_version=capability_version)
    return payload, notice.render_content()
