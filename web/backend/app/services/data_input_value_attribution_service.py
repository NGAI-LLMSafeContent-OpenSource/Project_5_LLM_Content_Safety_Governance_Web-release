"""Value-track attribution for the input module.

Uses Topic 1 value_qa benchmark assets joined with Risk Cause Determination
trace fields (predicted level + low-issue spans) when available.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.data_input import (
    AttributionIssueSpan,
    AttributionResponse,
    AttributionRow,
    AttributionStatItem,
    IntegrationEndpoint,
)
from app.services.benchmark_topic1_value_qa_sample_service import (
    BenchmarkTopic1ValueQaSampleError,
    BenchmarkTopic1ValueQaSampleNotFoundError,
    BenchmarkTopic1ValueQaSampleService,
)
from app.services.data_input_value_qa_common import (
    IMPORT_NEXT_ACTION,
    VALUE_LEVEL_DISPLAY,
    VALUE_LEVEL_SCORE,
    resolve_value_qa_asset,
)

TOPIC1_ATTRIBUTION_ENDPOINTS = [
    IntegrationEndpoint(
        method="GET",
        path="/api/data-input/attribution/value",
        purpose="从课题一 value_qa 资产与 Risk Cause 溯因字段生成价值归因证据链。",
    ),
]


async def build_value_attribution(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
    limit: int = 24,
    prefer_low: bool = True,
) -> AttributionResponse:
    asset = await resolve_value_qa_asset(db, asset_id=asset_id)
    if asset is None:
        return AttributionResponse(
            connected=False,
            track="value",
            service="课题一价值归因",
            message="尚未导入课题一 value_qa 预跑资产，无法生成价值归因。",
            source="topic1_value_qa",
            fallback=False,
            blocking_reason="Benchmark 资产库中没有可用的 value_qa 资产。",
            next_action=IMPORT_NEXT_ACTION,
            endpoints=TOPIC1_ATTRIBUTION_ENDPOINTS,
        )

    sample_service = BenchmarkTopic1ValueQaSampleService()
    try:
        listed = await sample_service.list_groups(
            db,
            asset_id=asset.asset_id,
            limit=max(1, min(limit, 50)),
            offset=0,
        )
    except (BenchmarkTopic1ValueQaSampleError, BenchmarkTopic1ValueQaSampleNotFoundError) as exc:
        return AttributionResponse(
            connected=False,
            track="value",
            service="课题一价值归因",
            message=str(exc),
            source="topic1_value_qa",
            asset_id=asset.asset_id,
            asset_name=asset.name,
            fallback=False,
            blocking_reason="value_qa 资产可读，但样本分组加载失败。",
            next_action="请检查资产目录中的 samples.jsonl / group_preview.jsonl 是否完整。",
            endpoints=TOPIC1_ATTRIBUTION_ENDPOINTS,
        )

    rows: list[AttributionRow] = []
    for group_item in listed.get("groups", []):
        group_id = str(group_item.get("group_id") or "")
        try:
            detail = await sample_service.get_group(
                db,
                asset_id=asset.asset_id,
                group_id=group_id,
            )
        except BenchmarkTopic1ValueQaSampleError:
            continue
        rows.extend(rows_from_group(detail, prefer_low=prefer_low))

    if prefer_low:
        rows.sort(key=lambda row: (0 if row.status == "待提升" else 1, row.id))

    excellent = sum(1 for row in rows if row.status == "优")
    good = sum(1 for row in rows if row.status == "良")
    needs = sum(1 for row in rows if row.status == "待提升")
    traced = sum(1 for row in rows if row.predicted_label or row.issue_spans)

    return AttributionResponse(
        connected=True,
        track="value",
        service="课题一 value_qa / Risk Cause 价值归因",
        message=(
            "已基于课题一 value_qa 资产生成价值归因；"
            + (
                "已拼入 Risk Cause 档位复判与 low 问题片段。"
                if traced
                else "当前资产未拼入 Risk Cause 溯因字段，仅展示价值档位与维度证据。"
            )
        ),
        source="topic1_risk_cause_trace" if traced else "topic1_value_qa",
        asset_id=asset.asset_id,
        asset_name=asset.name,
        total=len(rows),
        endpoints=TOPIC1_ATTRIBUTION_ENDPOINTS,
        stats=[
            AttributionStatItem(val=str(len(rows)), label="归因样本"),
            AttributionStatItem(val=str(excellent), label="优档"),
            AttributionStatItem(val=str(good), label="良档"),
            AttributionStatItem(val=str(needs), label="待提升"),
            AttributionStatItem(val=str(traced), label="含溯因字段"),
        ],
        rows=rows,
        next_action=(
            "待提升样本可结合 issue spans 进入修正预览；"
            "若需完整档位复判，请确认资产导入时附带了 Risk Cause ui_predictions / ui_low_issues。"
        ),
    )


def rows_from_group(detail: dict[str, Any], *, prefer_low: bool) -> list[AttributionRow]:
    levels = detail.get("levels") if isinstance(detail.get("levels"), dict) else {}
    ordered = ("low", "medium", "high") if prefer_low else ("high", "medium", "low")
    high_sample = levels.get("high") if isinstance(levels.get("high"), dict) else {}
    high_reference = _sample_text(high_sample)
    rows: list[AttributionRow] = []
    for level in ordered:
        sample = levels.get(level)
        if not isinstance(sample, dict):
            continue
        rows.append(
            row_from_sample(
                detail,
                level=level,
                sample=sample,
                high_reference=high_reference,
            )
        )
    return rows


def row_from_sample(
    detail: dict[str, Any],
    *,
    level: str,
    sample: dict[str, Any],
    high_reference: str = "",
) -> AttributionRow:
    display = VALUE_LEVEL_DISPLAY.get(level, "待提升")
    predicted = normalize_level_label(sample.get("trace_predicted_level"))
    true_label = normalize_level_label(sample.get("trace_true_label")) or display
    issue_spans = issue_spans_from_raw(sample.get("trace_low_issue_spans"))
    dimension = " / ".join(
        part
        for part in (
            str(detail.get("primary_dimension") or "").strip(),
            str(detail.get("secondary_dimension") or "").strip(),
        )
        if part
    )
    topic = str(detail.get("topic") or "").strip()
    snippet = _sample_text(sample)
    sample_id = str(sample.get("sample_id") or f"{detail.get('group_id')}-{level}")

    evidence_chain = [
        f"样本 ID：{sample_id}",
        f"分组：{detail.get('group_id') or '未分组'}",
        f"主题：{topic or '未标注'}",
        f"价值维度：{dimension or '未标注'}",
        f"语料档位（gold）：{display}",
    ]
    if predicted:
        evidence_chain.append(f"Risk Cause 复判档位：{predicted}")
    if true_label and true_label != display:
        evidence_chain.append(f"溯因对照真值：{true_label}")
    if issue_spans:
        for issue in issue_spans[:5]:
            tip = issue.span or issue.sentence or issue.type
            evidence_chain.append(f"问题片段：[{issue.type or 'issue'}] {tip}")
    elif level == "low":
        evidence_chain.append("问题片段：资产未提供 Risk Cause low_issues，仅按 low 档位展示。")

    status = predicted if predicted in {"优", "良", "待提升"} else display
    action = suggestion_for(status, issue_spans, dimension)
    # Prefer same-group high answer as editable correction draft for weaker tiers.
    use_high_draft = (
        level in {"low", "medium"}
        and bool(high_reference)
        and high_reference != snippet
    )
    suggestion = high_reference if use_high_draft else action
    note = "对照同组优档答案" if use_high_draft else ""
    if use_high_draft:
        evidence_chain.append("修正对照：已填入同组优档答案，可人工改写后采纳。")

    summary = (
        f"价值归因：value_qa {level} -> 展示档位 {status}；"
        f"维度 {dimension or '未标注'}。"
        + (f" Risk Cause 定位 {len(issue_spans)} 处问题片段。" if issue_spans else "")
        + (" 修正稿默认对齐同组优档。" if use_high_draft else "")
    )

    return AttributionRow(
        id=sample_id,
        track="value",
        source="topic1_risk_cause_trace" if (predicted or issue_spans) else "topic1_value_qa",
        status=status,
        score=VALUE_LEVEL_SCORE.get(level, "0.50"),
        snippet=snippet[:400],
        suggestion=suggestion,
        summary=summary,
        evidence_chain=evidence_chain,
        issue_spans=issue_spans,
        dimension=dimension,
        topic=topic,
        true_label=true_label,
        predicted_label=predicted,
        quality_level=level,
        group_id=str(detail.get("group_id") or ""),
        action=action,
        note=note,
    )


def _sample_text(sample: dict[str, Any] | None) -> str:
    if not isinstance(sample, dict):
        return ""
    answer = str(sample.get("answer") or "").strip()
    question = str(sample.get("question") or "").strip()
    return answer or question


def issue_spans_from_raw(raw: Any) -> list[AttributionIssueSpan]:
    if not isinstance(raw, list):
        return []
    spans: list[AttributionIssueSpan] = []
    for item in raw:
        if isinstance(item, dict) and "issues" in item and isinstance(item["issues"], list):
            for nested in item["issues"]:
                spans.extend(issue_spans_from_raw([nested]))
            continue
        if not isinstance(item, dict):
            continue
        spans.append(
            AttributionIssueSpan(
                type=str(item.get("type") or item.get("issue_type") or ""),
                sentence=str(item.get("sentence") or ""),
                span=str(item.get("span") or item.get("text") or ""),
            )
        )
    return spans


def normalize_level_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"high", "优", "excellent"}:
        return "优"
    if text in {"medium", "良", "good"}:
        return "良"
    if text in {"low", "待提升", "needsimprovement", "needs_improvement"}:
        return "待提升"
    return ""


def suggestion_for(status: str, issues: list[AttributionIssueSpan], dimension: str) -> str:
    dim = f"围绕维度「{dimension}」" if dimension else "围绕当前价值维度"
    if status == "优":
        return f"{dim}保持现有表达，可作为高档对照样本。"
    if status == "良":
        return f"{dim}补充背景与解释完整度，向优档对齐。"
    if issues:
        tip = issues[0].span or issues[0].sentence or "问题片段"
        return f"{dim}优先改写或删除定位片段「{tip[:40]}」，再复核档位。"
    return f"{dim}拆分语义角色并补齐价值标注后，再进入人工复核。"
