"""Risk-track attribution for the input module.

Builds evidence chains from Topic 2 FilterGuard keyword results or
simple/hard prerun assets. This is attribution orchestration, not a
standalone causal model.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.data_input import (
    AttributionFinding,
    AttributionResponse,
    AttributionRow,
    AttributionStatItem,
    AttributionStep,
    IntegrationEndpoint,
    Topic2KeywordPrediction,
    Topic2PrerunSampleRow,
)
from app.services.data_input_topic2_service import (
    get_topic2_risk_scan_task,
    load_topic2_prerun_samples,
)
from app.services.topic2_harm_labels import format_harm_category_l1

RISK_TYPE_LABELS = {
    "dangerous_instruction_keyword": "危险指令风险",
    "privacy_keyword": "隐私泄露风险",
    "bias_or_hate_keyword": "偏见仇恨风险",
    "keyword_hit": "通用关键词风险",
    "activation_probe_predicted_l1": "Activation Probe L1 路由",
}

TOPIC2_ATTRIBUTION_ENDPOINTS = [
    IntegrationEndpoint(
        method="POST",
        path="/api/data-input/attribution/risk",
        purpose="基于 FilterGuard keyword 识别结果或 simple/hard 预跑资产生成风险归因证据链。",
    ),
]

UPSTREAM_NOTE = "上游不回显输入文本，也不将输入写入服务日志。"


async def build_risk_attribution(
    db: AsyncSession,
    *,
    task_id: str | None = None,
    predictions: list[Topic2KeywordPrediction] | None = None,
    use_prerun: bool = False,
    asset_id: str | None = None,
    limit: int = 20,
) -> AttributionResponse:
    if use_prerun:
        return await _from_prerun(db, asset_id=asset_id, limit=limit)

    if task_id:
        task = await get_topic2_risk_scan_task(task_id)
        if task is None or task.result is None:
            return _unavailable(
                message="未找到课题二风险识别任务结果，无法生成归因。",
                blocking_reason="task_id 无效，或任务尚未完成。",
                next_action="请先在评估页完成课题二风险识别，再进入归因。",
            )
        if not task.result.connected:
            return _unavailable(
                message=task.result.message,
                blocking_reason=task.result.blocking_reason,
                next_action=task.result.next_action,
            )
        return _from_predictions(
            task.result.predictions,
            source=_attribution_source_from_predictions(
                task.result.predictions,
                preferred=task.result.source or task.result.method,
            ),
        )

    if predictions:
        return _from_predictions(
            predictions,
            source=_attribution_source_from_predictions(predictions),
        )

    return _unavailable(
        message="缺少风险识别结果，无法生成归因。",
        blocking_reason="未提供 task_id、predictions，也未指定 use_prerun。",
        next_action="请先运行课题二风险识别（默认 Activation Probe），或载入 simple/hard 预跑资产作为静态归因样例。",
    )


def _attribution_source_from_predictions(
    predictions: list[Topic2KeywordPrediction],
    *,
    preferred: str | None = None,
) -> str:
    hint = (preferred or "").strip().lower()
    if "activation" in hint or hint == "activation_probe":
        return "topic2_activation_probe"
    if "keyword" in hint or "filterguard" in hint:
        return "topic2_filterguard"

    for item in predictions:
        method = (item.detect_method or "").strip().lower()
        if method == "activation_probe" or "activation" in method:
            return "topic2_activation_probe"
        if method == "keyword" or "filterguard" in method:
            return "topic2_filterguard"
        if any(finding.risk_type == "activation_probe_predicted_l1" for finding in item.findings):
            return "topic2_activation_probe"
    return "topic2_activation_probe"


def _from_predictions(
    predictions: list[Topic2KeywordPrediction],
    *,
    source: str,
) -> AttributionResponse:
    rows = [_row_from_prediction(item, source=source) for item in predictions]
    abnormal = sum(
        1
        for item, row in zip(predictions, rows, strict=False)
        if item.is_abnormal or row.status in {"异常", "高风险", "中风险"}
    )
    safe = len(rows) - abnormal
    l1_covered = sum(
        1
        for row in rows
        if (row.risk_category_l1 or "").strip() or (row.predicted_l1_id or "").strip()
    )
    return AttributionResponse(
        connected=True,
        track="risk",
        service="课题二风险归因",
        message="已基于课题二识别结果生成风险归因证据链。",
        source=source,
        total=len(rows),
        endpoints=TOPIC2_ATTRIBUTION_ENDPOINTS,
        stats=[
            AttributionStatItem(val=str(len(rows)), label="归因样本"),
            AttributionStatItem(val=str(abnormal), label="异常"),
            AttributionStatItem(val=str(safe), label="安全"),
            AttributionStatItem(val=str(l1_covered), label="已返回 L1"),
        ],
        rows=rows,
        next_action=(
            "可进入修正页做人工复核与改写；当前无自动 rewrite，"
            "处置建议仅供人工参考（pending_topic2_contract）。"
        ),
    )


async def _from_prerun(
    db: AsyncSession,
    *,
    asset_id: str | None,
    limit: int,
) -> AttributionResponse:
    payload = await load_topic2_prerun_samples(db, asset_id=asset_id, limit=limit)
    if not payload.connected:
        return AttributionResponse(
            connected=False,
            track="risk",
            service=payload.service,
            message=payload.message,
            source=payload.source,
            mode=payload.mode,
            fallback=False,
            blocking_reason=payload.blocking_reason,
            next_action=payload.next_action,
            endpoints=payload.endpoints or TOPIC2_ATTRIBUTION_ENDPOINTS,
            asset_id=payload.asset_id,
            asset_name=payload.asset_name,
        )

    rows = [_row_from_prerun(item) for item in payload.rows]
    abnormal = sum(1 for row in rows if row.status in {"异常", "高风险", "中风险"})
    return AttributionResponse(
        connected=True,
        track="risk",
        service="课题二 simple/hard 预跑风险归因",
        message="已基于课题二正式预跑评测资产生成静态风险归因样例。",
        source="topic2_prerun_snapshot",
        asset_id=payload.asset_id,
        asset_name=payload.asset_name,
        total=len(rows),
        endpoints=TOPIC2_ATTRIBUTION_ENDPOINTS,
        stats=[
            AttributionStatItem(val=str(payload.pair_count), label="简单/困难配对组"),
            AttributionStatItem(val=str(len(rows)), label="归因样本"),
            AttributionStatItem(val=str(abnormal), label="异常（漏检）"),
            AttributionStatItem(val=str(len(payload.l1_labels)), label="覆盖 L1 标签"),
        ],
        rows=rows,
        next_action="此为静态评测样例归因，不代表对本批次上传语料的实时识别结论。",
    )


def _row_from_prediction(item: Topic2KeywordPrediction, *, source: str) -> AttributionRow:
    findings = [
        AttributionFinding(
            keyword=finding.keyword,
            evidence=finding.evidence,
            risk_type=finding.risk_type,
            label=RISK_TYPE_LABELS.get(finding.risk_type, finding.risk_type or "通用关键词风险"),
        )
        for finding in item.findings
    ]
    method = item.detect_method or (
        "activation_probe"
        if any(finding.risk_type == "activation_probe_predicted_l1" for finding in item.findings)
        else "keyword"
    )
    method_label = "Activation Probe" if method == "activation_probe" else "FilterGuard keyword"
    l1_for_row = format_harm_category_l1(item.risk_category_l1) or item.risk_category_l1
    l1_detail = l1_for_row or "未返回 L1"
    if item.predicted_l1_id:
        l1_detail = f"{l1_detail}（id={item.predicted_l1_id}）"
    action = item.action or item.suggestion
    suggestion = item.suggestion or item.action or action
    lineage = item.lineage_node_label or item.lineage_node_id or "未绑定血缘节点"
    status = item.status or ("异常" if item.is_abnormal else "安全")

    steps = [
        AttributionStep(title="绑定血缘", detail=lineage),
        AttributionStep(title="课题二识别", detail=method_label),
        AttributionStep(title="L1 路由", detail=l1_detail),
        AttributionStep(title="判定", detail=f"{status} · 风险分 {item.score:.2f}"),
    ]
    if findings and method != "activation_probe":
        hit_text = "、".join(
            f"{finding.label or finding.risk_type}:{finding.keyword}"
            for finding in findings
            if finding.keyword
        ) or "无显式关键词命中"
        steps.insert(3, AttributionStep(title="关键词证据", detail=hit_text))
    if action:
        steps.append(AttributionStep(title="处置", detail=action))

    evidence_chain = [f"{step.title}：{step.detail}" for step in steps if step.detail]
    summary = f"{method_label} → {status} · {l1_detail}"

    return AttributionRow(
        id=item.id,
        track="risk",
        source=source,
        status=status,
        score=f"{item.score:.2f}",
        snippet=item.text,
        suggestion=suggestion,
        summary=summary,
        evidence_chain=evidence_chain,
        attribution_steps=steps,
        findings=findings,
        lineage_node_id=item.lineage_node_id,
        lineage_node_label=item.lineage_node_label,
        risk_category_l1=l1_for_row,
        risk_category_l2=item.risk_category_l2,
        predicted_l1_id=item.predicted_l1_id,
        detect_method=method,
        action=action,
        note=UPSTREAM_NOTE if method == "activation_probe" else "",
    )


def _row_from_prerun(item: Topic2PrerunSampleRow) -> AttributionRow:
    l1 = format_harm_category_l1(item.harm_category_l1) or item.harm_category_l1 or "未提供 L1"
    status = item.status or "安全"
    steps = [
        AttributionStep(
            title="预跑样本",
            detail=f"{item.difficulty_level or 'sample'} · 配对 {item.pair_id or item.id}",
        ),
        AttributionStep(title="危害类别", detail=f"{l1} / {item.harm_category_l2 or '未提供 L2'}"),
    ]
    if item.strategy_chain:
        steps.append(
            AttributionStep(title="改写策略", detail=" -> ".join(item.strategy_chain)),
        )
    if item.bypassed_moderators:
        steps.append(
            AttributionStep(
                title="漏检评测器",
                detail="、".join(item.bypassed_moderators),
            ),
        )
    else:
        steps.append(
            AttributionStep(title="漏检评测器", detail="无（样本被拦截或未返回 bypass）"),
        )
    steps.append(
        AttributionStep(title="预跑判定", detail=f"{status} · 风险分 {item.score:.2f}"),
    )
    if item.suggestion:
        steps.append(AttributionStep(title="处置", detail=item.suggestion))

    evidence_chain = [f"{step.title}：{step.detail}" for step in steps if step.detail]
    summary = f"预跑 {item.difficulty_level or 'sample'} → {status} · {l1}"

    return AttributionRow(
        id=item.id,
        track="risk",
        source="topic2_prerun_snapshot",
        status=status,
        score=f"{item.score:.2f}",
        snippet=item.snippet,
        suggestion=item.suggestion,
        summary=summary,
        evidence_chain=evidence_chain,
        attribution_steps=steps,
        risk_category_l1=l1,
        risk_category_l2=item.harm_category_l2,
        difficulty_level=item.difficulty_level,
        strategy_chain=list(item.strategy_chain),
        action=item.suggestion,
    )


def _unavailable(
    *,
    message: str,
    blocking_reason: str,
    next_action: str,
) -> AttributionResponse:
    return AttributionResponse(
        connected=False,
        track="risk",
        service="课题二风险归因",
        message=message,
        source="topic2_activation_probe",
        fallback=False,
        blocking_reason=blocking_reason,
        next_action=next_action,
        endpoints=TOPIC2_ATTRIBUTION_ENDPOINTS,
    )
