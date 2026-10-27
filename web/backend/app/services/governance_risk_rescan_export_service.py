"""Build the input-risk ``risk_corpus_rescan`` evidence pack (#164 T3 / #167).

The export never re-reads the registered asset and never re-runs an evaluator:
every artifact projects the persisted completion snapshot. This is the merged
v2 rescan export; the retired DynBench400-only evidence pack is gone (#169).
"""

from __future__ import annotations

import csv
import html
import io
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GovernanceCompletionRecord, GovernanceTask
from app.schemas.governance import RISK_RESCAN_CAPABILITY


class RiskRescanExportNotFoundError(ValueError):
    pass


def _issue_lists(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lists = report.get("issue_lists") or {}
    return {
        "risk_hit": list(lists.get("risk_hit") or []),
        "reference_label_disagreement": list(
            lists.get("reference_label_disagreement") or []
        ),
    }


def _render_html(report: dict[str, Any]) -> str:
    envelope = report.get("envelope") or {}
    evaluated = envelope.get("evaluated_object") or report.get("evaluation_object") or {}
    run_identity = envelope.get("run_identity") or {}
    lists = _issue_lists(report)

    def status_row(key: str) -> str:
        item = envelope.get(key) or {}
        return (
            f"<tr><th>{html.escape(key)}</th>"
            f"<td>{html.escape(str(item.get('code') or ''))}</td>"
            f"<td>{html.escape(str(item.get('label') or ''))}</td></tr>"
        )

    def issue_items(kind: str, title: str) -> str:
        items = lists[kind]
        if not items:
            return f"<h2>{html.escape(title)}（0）</h2><p>无</p>"
        rows = "".join(
            (
                "<li>"
                f"<strong>{html.escape(str(item.get('category') or ''))}</strong> "
                f"sample={html.escape(str(item.get('sample_id') or '—'))} "
                f"reference={html.escape(str(item.get('reference_label') or '—'))} "
                f"detected={html.escape(str(item.get('detected_label') or '—'))}<br>"
                f"{html.escape(str(item.get('judgment') or ''))}"
                "</li>"
            )
            for item in items
        )
        return f"<h2>{html.escape(title)}（{len(items)}）</h2><ul>{rows}</ul>"

    boundaries = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in envelope.get("claim_boundaries") or []
    )
    limitations = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in envelope.get("limitations") or []
    )
    report_title = "输入风险语料在线二次检测报告"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{report_title} {html.escape(str(report.get('task_id') or ''))}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.4rem 0.6rem; text-align: left; }}
    h1, h2 {{ margin-top: 1.5rem; }}
    .note {{ color: #4b5563; }}
  </style>
</head>
<body>
  <h1>{report_title}</h1>
  <p class="note">冻结快照 · internal_validation · 参考标注不是 ground truth</p>
  <p>任务 ID：{html.escape(str(report.get('task_id') or ''))}</p>
  <p>评测对象：{html.escape(str(evaluated.get('asset_id') or ''))}</p>
  <p>内容摘要：{html.escape(str(evaluated.get('content_sha256') or ''))}</p>
  <p>评估器：{html.escape(str(run_identity.get('evaluator') or report.get('evaluator') or ''))}</p>
  <h2>状态</h2>
  <table><tbody>
    {status_row('evaluation_run_status')}
    {status_row('integrity_status')}
    {status_row('delivery_readiness')}
    {status_row('review_task_status')}
  </tbody></table>
  {issue_items('risk_hit', '风险命中')}
  {issue_items('reference_label_disagreement', '参考标注分歧')}
  <h2>结论边界</h2><ul>{boundaries}</ul>
  <h2>局限</h2><ul>{limitations}</ul>
</body>
</html>
"""


def _render_issues_csv(lists: dict[str, list[dict[str, Any]]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "list_kind",
            "issue_id",
            "category",
            "sample_id",
            "reference_label",
            "detected_label",
            "judgment",
        ],
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for kind in ("risk_hit", "reference_label_disagreement"):
        for item in lists[kind]:
            writer.writerow({**item, "list_kind": item.get("list_kind") or kind})
    return buffer.getvalue()


def _statuses(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (envelope.get(key) or {}).get("code")
        for key in (
            "evaluation_run_status",
            "integrity_status",
            "delivery_readiness",
            "review_task_status",
        )
    }


def _render_manifest(report: dict[str, Any]) -> dict[str, Any]:
    envelope = report.get("envelope") or {}
    evaluated = dict(envelope.get("evaluated_object") or {})
    evaluation_object = report.get("evaluation_object") or {}
    evaluated.update(
        {
            key: evaluation_object.get(key)
            for key in (
                "asset_id",
                "content_sha256",
                "disclosure_level",
                "source_missing",
                "licence_missing",
            )
            if evaluation_object.get(key) is not None
        }
    )
    content_sha256 = str(evaluated.get("content_sha256") or "")
    evaluated["asset_version"] = content_sha256
    evaluated["version_kind"] = "content_sha256"
    samples = list(report.get("samples") or [])
    sample_ids = [str(item.get("sample_id") or "") for item in samples]
    lists = _issue_lists(report)
    run_identity = envelope.get("run_identity") or {}
    return {
        "task_id": report.get("task_id"),
        "capability": report.get("capability"),
        "capability_version": report.get("capability_version"),
        "report_type": report.get("report_type"),
        "evaluated_object": evaluated,
        "source_identity": envelope.get("source_identity") or {},
        "frozen_scope": {
            "filters": report.get("filters") or {},
            "sample_ids": sample_ids,
            "sample_count": len(sample_ids),
        },
        "evaluator": {
            "method": report.get("method") or run_identity.get("method"),
            "evaluator": report.get("evaluator") or run_identity.get("evaluator"),
        },
        "run_identity": {**run_identity, "task_id": report.get("task_id")},
        "source_refs": report.get("source_refs") or [],
        "statuses": _statuses(envelope),
        "claim_boundaries": envelope.get("claim_boundaries") or [],
        "limitations": envelope.get("limitations") or [],
        "disclosure_limits": report.get("disclosure_limits")
        or envelope.get("limitations")
        or [],
        "integrity_facts": report.get("integrity_facts") or [],
        "executor_identity": report.get("executor_identity") or {},
        "issue_counts": {key: len(value) for key, value in lists.items()},
        "files": ["report.html", "issues.csv", "issues.json", "manifest.json"],
        "completed_at": report.get("completed_at"),
    }


def build_rescan_evidence_pack(report: dict[str, Any]) -> dict[str, Any]:
    lists = _issue_lists(report)
    manifest = _render_manifest(report)
    artifacts = {
        "report.html": _render_html(report),
        "issues.csv": _render_issues_csv(lists),
        "issues.json": json.dumps(lists, ensure_ascii=False, indent=2) + "\n",
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    }
    return {
        "task_id": report.get("task_id"),
        "capability": report.get("capability") or RISK_RESCAN_CAPABILITY,
        "artifacts": artifacts,
        "manifest": manifest,
    }


async def get_input_risk_rescan_evidence_pack(
    db: AsyncSession, client_id: str, task_id: str
) -> dict[str, Any]:
    """v2 evidence pack: a projection of the persisted result, never a re-run."""
    task = (
        await db.execute(
            select(GovernanceTask).where(
                GovernanceTask.task_id == task_id,
                GovernanceTask.client_id == client_id,
            )
        )
    ).scalar_one_or_none()
    if task is None or task.capability != RISK_RESCAN_CAPABILITY:
        raise RiskRescanExportNotFoundError("输入风险在线二次检测任务不存在")

    completion = (
        await db.execute(
            select(GovernanceCompletionRecord).where(
                GovernanceCompletionRecord.task_id == task_id
            )
        )
    ).scalar_one_or_none()
    if completion is None or not completion.result_snapshot_json:
        raise RiskRescanExportNotFoundError("输入风险在线二次检测冻结报告不存在")
    try:
        report = json.loads(completion.result_snapshot_json)
    except json.JSONDecodeError as error:
        raise RiskRescanExportNotFoundError("输入风险在线二次检测冻结报告不可读") from error
    if (
        not isinstance(report, dict)
        or report.get("capability") != RISK_RESCAN_CAPABILITY
    ):
        raise RiskRescanExportNotFoundError("输入风险在线二次检测冻结报告不可读")
    return build_rescan_evidence_pack(report)
