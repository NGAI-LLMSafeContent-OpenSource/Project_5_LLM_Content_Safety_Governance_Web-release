"""Build a frozen cultural prerun review evidence pack (#89).

Exports are derived only from the persisted completion / message snapshot so
reopening a task never re-reads Project 3.
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
from app.schemas.governance import CULTURAL_PRERUN_REVIEW_CAPABILITY


class CulturalExportNotFoundError(ValueError):
    pass


def _issue_lists(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lists = report.get("issue_lists") or {}
    return {
        "content": list(lists.get("content") or []),
        "integrity": list(lists.get("integrity") or []),
    }


def _render_html(report: dict[str, Any]) -> str:
    envelope = report.get("envelope") or {}
    metrics = report.get("source_metrics") or []
    lists = _issue_lists(report)
    claim_boundaries = envelope.get("claim_boundaries") or []
    limitations = envelope.get("limitations") or []

    def status_row(key: str) -> str:
        item = envelope.get(key) or {}
        return (
            f"<tr><th>{html.escape(key)}</th>"
            f"<td>{html.escape(str(item.get('code') or ''))}</td>"
            f"<td>{html.escape(str(item.get('label') or ''))}</td></tr>"
        )

    metric_rows = "".join(
        (
            "<tr>"
            f"<th>{html.escape(str(metric.get('label') or metric.get('method') or ''))}</th>"
            f"<td>{html.escape(str(metric.get('ethnic_recognition_rate')))}</td>"
            f"<td>{html.escape(str(metric.get('cultural_specificity_rate')))}</td>"
            f"<td>{html.escape(str(metric.get('composite_pass_count')))}"
            f" / {html.escape(str(metric.get('total_samples')))}</td>"
            f"<td>{html.escape(str(metric.get('composite_percentage')))}%</td>"
            "</tr>"
        )
        for metric in metrics
    )

    def issue_items(kind: str, title: str) -> str:
        items = lists.get(kind) or []
        if not items:
            return f"<h2>{html.escape(title)}（0）</h2><p>无</p>"
        rows = "".join(
            (
                "<li>"
                f"<strong>{html.escape(str(item.get('category') or ''))}</strong> "
                f"sample={html.escape(str(item.get('sample_id') or '—'))} "
                f"method={html.escape(str(item.get('method') or '—'))}<br>"
                f"{html.escape(str(item.get('judgment') or ''))}"
                "</li>"
            )
            for item in items
        )
        return f"<h2>{html.escape(title)}（{len(items)}）</h2><ul>{rows}</ul>"

    boundaries = "".join(f"<li>{html.escape(str(item))}</li>" for item in claim_boundaries)
    limits = "".join(f"<li>{html.escape(str(item))}</li>" for item in limitations)
    evaluated = envelope.get("evaluated_object") or {}
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>文化预跑审阅报告 {html.escape(str(report.get('task_id') or ''))}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.4rem 0.6rem; text-align: left; }}
    h1, h2 {{ margin-top: 1.5rem; }}
    .note {{ color: #4b5563; }}
  </style>
</head>
<body>
  <h1>文化生成方法对比 · 预跑记录审阅报告</h1>
  <p class="note">冻结快照 · 不重新读取上游 · 不评价事实正确性、安全性或合规性</p>
  <p>任务 ID：{html.escape(str(report.get('task_id') or ''))}</p>
  <p>评测对象：{html.escape(str(evaluated.get('record_id') or ''))}
    （版本 {html.escape(str(evaluated.get('record_version') or '—'))}）</p>
  <h2>状态</h2>
  <table>
    <tbody>
      {status_row('evaluation_run_status')}
      {status_row('integrity_status')}
      {status_row('delivery_readiness')}
      {status_row('review_task_status')}
    </tbody>
  </table>
  <h2>来源指标对比</h2>
  <table>
    <thead>
      <tr><th>方法</th><th>民族识别</th><th>文化特异性</th><th>综合通过</th><th>综合百分比</th></tr>
    </thead>
    <tbody>{metric_rows}</tbody>
  </table>
  <p class="note">综合百分比为上游评测原始值，原样展示；完整性检查只追加告警，不重算或改写。</p>
  {issue_items('content', '内容问题')}
  {issue_items('integrity', '评测完整性问题')}
  <h2>结论边界</h2>
  <ul>{boundaries}</ul>
  <h2>局限</h2>
  <ul>{limits}</ul>
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
            "method",
            "dimension",
            "judgment",
        ],
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for kind in ("content", "integrity"):
        for item in lists.get(kind) or []:
            writer.writerow(
                {
                    "list_kind": item.get("list_kind") or kind,
                    "issue_id": item.get("issue_id") or "",
                    "category": item.get("category") or "",
                    "sample_id": item.get("sample_id") or "",
                    "method": item.get("method") or "",
                    "dimension": item.get("dimension") or "",
                    "judgment": item.get("judgment") or "",
                }
            )
    return buffer.getvalue()


def _render_manifest(report: dict[str, Any]) -> dict[str, Any]:
    envelope = report.get("envelope") or {}
    evaluated = dict(envelope.get("evaluated_object") or {})
    source_identity = envelope.get("source_identity") or {}
    evaluated["asset_sha256"] = source_identity.get("asset_sha256") or evaluated.get(
        "asset_sha256"
    )
    statuses = {
        "evaluation_run_status": (envelope.get("evaluation_run_status") or {}).get(
            "code"
        ),
        "integrity_status": (envelope.get("integrity_status") or {}).get("code"),
        "delivery_readiness": (envelope.get("delivery_readiness") or {}).get("code"),
        "review_task_status": (envelope.get("review_task_status") or {}).get("code"),
    }
    return {
        "task_id": report.get("task_id"),
        "capability": report.get("capability"),
        "capability_version": report.get("capability_version"),
        "report_type": report.get("report_type"),
        "evaluated_object": evaluated,
        "source_identity": source_identity,
        "run_identity": envelope.get("run_identity") or {},
        "statuses": statuses,
        "claim_boundaries": envelope.get("claim_boundaries") or [],
        "limitations": envelope.get("limitations") or [],
        "source_metrics": report.get("source_metrics") or [],
        "issue_counts": {
            "content": len((report.get("issue_lists") or {}).get("content") or []),
            "integrity": len((report.get("issue_lists") or {}).get("integrity") or []),
        },
        "files": [
            "report.html",
            "issues.csv",
            "issues.json",
            "manifest.json",
        ],
        "completed_at": report.get("completed_at"),
    }


def build_cultural_evidence_pack(report: dict[str, Any]) -> dict[str, Any]:
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
        "capability": CULTURAL_PRERUN_REVIEW_CAPABILITY,
        "artifacts": artifacts,
        "manifest": manifest,
    }


async def get_cultural_evidence_pack(
    db: AsyncSession, client_id: str, task_id: str
) -> dict[str, Any]:
    task = (
        await db.execute(
            select(GovernanceTask).where(
                GovernanceTask.task_id == task_id,
                GovernanceTask.client_id == client_id,
            )
        )
    ).scalar_one_or_none()
    if task is None or task.capability != CULTURAL_PRERUN_REVIEW_CAPABILITY:
        raise CulturalExportNotFoundError("文化预跑审阅任务不存在")

    completion = (
        await db.execute(
            select(GovernanceCompletionRecord).where(
                GovernanceCompletionRecord.task_id == task_id
            )
        )
    ).scalar_one_or_none()
    if completion is None or not completion.result_snapshot_json:
        raise CulturalExportNotFoundError("文化预跑审阅冻结报告不存在")
    try:
        report = json.loads(completion.result_snapshot_json)
    except json.JSONDecodeError as error:
        raise CulturalExportNotFoundError("文化预跑审阅冻结报告不可读") from error
    if not isinstance(report, dict):
        raise CulturalExportNotFoundError("文化预跑审阅冻结报告不可读")
    return build_cultural_evidence_pack(report)
