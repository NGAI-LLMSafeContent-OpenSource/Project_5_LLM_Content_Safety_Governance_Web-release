"""Build a frozen risk prerun review evidence pack (#91).

Exports are derived only from the persisted completion snapshot so reopening a
task never re-reads Topic3. Restricted redaction: no full high-risk
prompt/response in any artifact.
"""

from __future__ import annotations

import csv
import html
import io
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.topic3.risk_evaluation import PRIMARY_MODEL_ID
from app.db.models import GovernanceCompletionRecord, GovernanceTask
from app.schemas.governance import RISK_PRERUN_REVIEW_CAPABILITY
from app.services.governance_risk_review_service import (
    EXCERPT_MAX_LEN,
    SENSITIVITY_BOUNDARY,
)

# Allow a small margin for ellipsis / whitespace in masked excerpts.
EXCERPT_EXPORT_MAX_LEN = EXCERPT_MAX_LEN + 8


class RiskExportNotFoundError(ValueError):
    pass


FORBIDDEN_EXPORT_KEYS = (
    "prompt",
    "response",
    "raw_output",
    "assignee",
    "owner",
    "assigned_to",
    "resolution_status",
    "ticket_status",
    "处理状态",
    "责任人",
)

_WORKFLOW_KEYS = frozenset(
    {
        "assignee",
        "owner",
        "assigned_to",
        "resolution_status",
        "ticket_status",
        "处理状态",
        "责任人",
    }
)

_SENSITIVE_CONTENT_KEYS = frozenset({"prompt", "response", "raw_output"})


def _issue_lists(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lists = report.get("issue_lists") or {}
    return {
        "recognition": list(lists.get("recognition") or []),
        "integrity": list(lists.get("integrity") or []),
    }


def _walk_dicts(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_dicts(item)


def _assert_no_sensitive_leak(
    artifacts: dict[str, str],
    forbidden_snippets: list[str],
    *,
    report: dict[str, Any] | None = None,
) -> None:
    """Reject export if full high-risk texts or sensitive keys leak into artifacts.

    Create-time passes live ``forbidden_snippets``. Export-from-snapshot relies on
    structural guards (no prompt/response keys, excerpt length bounds) plus any
    snippets still supplied by the caller (unit tests / create dry-run).
    """
    blob = "\n".join(artifacts.values())
    for key in _WORKFLOW_KEYS:
        if f'"{key}"' in blob or f",{key}," in blob or blob.startswith(f"{key},"):
            raise ValueError(f"risk evidence pack must not include workflow key {key}")
    for key in _SENSITIVE_CONTENT_KEYS:
        # JSON object keys or CSV column headers.
        if f'"{key}"' in blob or blob.startswith(f"{key},") or f"\n{key}," in blob:
            raise ValueError(
                f"risk evidence pack must not include sensitive content key {key}"
            )
    for snippet in forbidden_snippets:
        if snippet and snippet in blob:
            raise ValueError(
                "risk evidence pack must not include full high-risk prompt/response"
            )

    lists = _issue_lists(report or {})
    for kind in ("recognition", "integrity"):
        for item in lists.get(kind) or []:
            excerpt = str(item.get("excerpt_masked") or "")
            if len(excerpt) > EXCERPT_EXPORT_MAX_LEN:
                raise ValueError(
                    "risk evidence pack excerpt_masked exceeds restricted length bound"
                )
            for key in _SENSITIVE_CONTENT_KEYS:
                if key in item:
                    raise ValueError(
                        f"risk evidence pack issue must not include {key}"
                    )

    frozen = (report or {}).get("frozen_evidence") or {}
    for node in _walk_dicts(frozen):
        for key in _SENSITIVE_CONTENT_KEYS:
            if key in node:
                raise ValueError(
                    f"risk evidence pack frozen_evidence must not include {key}"
                )
        if "prediction_rows" in node:
            raise ValueError(
                "risk evidence pack frozen_evidence must not include prediction_rows"
            )


def _render_html(report: dict[str, Any]) -> str:
    envelope = report.get("envelope") or {}
    lists = _issue_lists(report)
    claim_boundaries = envelope.get("claim_boundaries") or []
    limitations = envelope.get("limitations") or []
    primary = report.get("primary_evaluator") or {}
    baseline = report.get("baseline_evaluator") or {}
    baseline_available = bool(baseline)

    def status_row(key: str) -> str:
        item = envelope.get(key) or {}
        return (
            f"<tr><th>{html.escape(key)}</th>"
            f"<td>{html.escape(str(item.get('code') or ''))}</td>"
            f"<td>{html.escape(str(item.get('label') or ''))}</td></tr>"
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
                f"evidence_state={html.escape(str(item.get('evidence_state') or '—'))}<br>"
                f"{html.escape(str(item.get('judgment') or ''))}"
                + (
                    f"<br><em>{html.escape(str(item.get('excerpt_masked') or ''))}</em>"
                    if item.get("excerpt_masked")
                    else ""
                )
                + "</li>"
            )
            for item in items
        )
        return f"<h2>{html.escape(title)}（{len(items)}）</h2><ul>{rows}</ul>"

    boundaries = "".join(f"<li>{html.escape(str(item))}</li>" for item in claim_boundaries)
    limits = "".join(f"<li>{html.escape(str(item))}</li>" for item in limitations)
    evaluated = envelope.get("evaluated_object") or {}
    comparison_note = (
        "Base 不进入正式问题清单"
        if baseline_available
        else "本版本暂无同版本基线"
    )
    baseline_row = (
        "<tr><td>Base 基线（baseline，仅对照）</td>"
        f"<td>{html.escape(str(baseline.get('model_id') or ''))}</td>"
        f"<td>{html.escape(str(baseline.get('run_id') or ''))}</td></tr>"
        if baseline_available
        else '<tr><td colspan="3">本版本暂无同版本基线</td></tr>'
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>风险预跑审阅报告 {html.escape(str(report.get('task_id') or ''))}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.4rem 0.6rem; text-align: left; }}
    h1, h2 {{ margin-top: 1.5rem; }}
    .note {{ color: #4b5563; }}
  </style>
</head>
<body>
  <h1>风险识别器交叉核对 · 预跑记录审阅报告</h1>
  <p class="note">冻结快照 · 不重新读取上游 · 受限导出 · {comparison_note}</p>
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
  <h2>评估器身份</h2>
  <table>
    <thead><tr><th>角色</th><th>model_id</th><th>run_id</th></tr></thead>
    <tbody>
      <tr><td>V7 正式（primary）</td>
        <td>{html.escape(str(primary.get('model_id') or ''))}</td>
        <td>{html.escape(str(primary.get('run_id') or ''))}</td></tr>
      {baseline_row}
    </tbody>
  </table>
  <p class="note">{html.escape(SENSITIVITY_BOUNDARY)}</p>
  {issue_items('recognition', '风险识别差异')}
  {issue_items('integrity', '资产完整性问题')}
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
            "evidence_state",
            "judgment",
            "excerpt_masked",
        ],
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for kind in ("recognition", "integrity"):
        for item in lists.get(kind) or []:
            writer.writerow(
                {
                    "list_kind": item.get("list_kind") or kind,
                    "issue_id": item.get("issue_id") or "",
                    "category": item.get("category") or "",
                    "sample_id": item.get("sample_id") or "",
                    "evidence_state": item.get("evidence_state") or "",
                    "judgment": item.get("judgment") or "",
                    "excerpt_masked": item.get("excerpt_masked") or "",
                }
            )
    return buffer.getvalue()


def _render_manifest(report: dict[str, Any]) -> dict[str, Any]:
    envelope = report.get("envelope") or {}
    evaluated = dict(envelope.get("evaluated_object") or {})
    source_identity = envelope.get("source_identity") or {}
    run_identity = envelope.get("run_identity") or {}
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
    frozen = report.get("frozen_evidence") or {}
    primary = report.get("primary_evaluator") or {}
    baseline = report.get("baseline_evaluator") or {}
    return {
        "task_id": report.get("task_id"),
        "capability": report.get("capability"),
        "capability_version": report.get("capability_version"),
        "report_type": report.get("report_type"),
        "evaluated_object": evaluated,
        "asset": {
            "asset_id": evaluated.get("record_id")
            or (frozen.get("asset") or {}).get("asset_id"),
            "benchmark_version": evaluated.get("benchmark_version")
            or (frozen.get("asset") or {}).get("asset_version")
            or "v6",
            "asset_sha256": evaluated.get("asset_sha256")
            or (frozen.get("asset") or {}).get("asset_sha256"),
            "disclosure_level": evaluated.get("disclosure_level")
            or frozen.get("disclosure_level")
            or "restricted",
        },
        "primary_run": {
            "role": "primary",
            "model_id": primary.get("model_id")
            or (run_identity.get("primary") or {}).get("model_id"),
            "run_id": primary.get("run_id")
            or (run_identity.get("primary") or {}).get("run_id"),
        },
        "baseline_run": (
            {
                "role": "baseline",
                "model_id": baseline.get("model_id")
                or (run_identity.get("baseline") or {}).get("model_id"),
                "run_id": baseline.get("run_id")
                or (run_identity.get("baseline") or {}).get("run_id"),
                "note": "baseline display only; excluded from formal issue lists",
            }
            if baseline or run_identity.get("baseline")
            else None
        ),
        "source_identity": source_identity,
        "run_identity": run_identity,
        "statuses": statuses,
        "sensitivity_boundary": frozen.get("sensitivity_boundary")
        or SENSITIVITY_BOUNDARY,
        "claim_boundaries": envelope.get("claim_boundaries") or [],
        "limitations": envelope.get("limitations") or [],
        "issue_counts": {
            "recognition": len((report.get("issue_lists") or {}).get("recognition") or []),
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


def build_risk_evidence_pack(
    report: dict[str, Any],
    *,
    forbidden_snippets: list[str] | None = None,
) -> dict[str, Any]:
    lists = _issue_lists(report)
    # Guard: Base predictions must not enter formal recognition rows.
    # Package-level integrity warnings may mention role=baseline (the package under
    # check); that is not a Base prediction attribution and must not trip this gate.
    for item in lists.get("recognition") or []:
        evidence = item.get("evidence") or {}
        if str(evidence.get("evaluator_role") or "") == "baseline":
            raise ValueError("Base predictions must not enter formal issue lists")
        model_id = str(evidence.get("model_id") or "").lower()
        if model_id and "base" in model_id and PRIMARY_MODEL_ID.lower() not in model_id:
            raise ValueError("Base predictions must not enter formal issue lists")
    for item in lists.get("integrity") or []:
        evidence = item.get("evidence") or {}
        if str(evidence.get("evaluator_role") or "") == "baseline":
            raise ValueError("Base predictions must not enter formal issue lists")

    manifest = _render_manifest(report)
    artifacts = {
        "report.html": _render_html(report),
        "issues.csv": _render_issues_csv(lists),
        "issues.json": json.dumps(lists, ensure_ascii=False, indent=2) + "\n",
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    }
    _assert_no_sensitive_leak(
        artifacts,
        list(forbidden_snippets or []),
        report=report,
    )
    return {
        "task_id": report.get("task_id"),
        "capability": RISK_PRERUN_REVIEW_CAPABILITY,
        "artifacts": artifacts,
        "manifest": manifest,
    }


async def get_risk_evidence_pack(
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
    if task is None or task.capability != RISK_PRERUN_REVIEW_CAPABILITY:
        raise RiskExportNotFoundError("风险预跑审阅任务不存在")

    completion = (
        await db.execute(
            select(GovernanceCompletionRecord).where(
                GovernanceCompletionRecord.task_id == task_id
            )
        )
    ).scalar_one_or_none()
    if completion is None or not completion.result_snapshot_json:
        raise RiskExportNotFoundError("风险预跑审阅冻结报告不存在")
    try:
        report = json.loads(completion.result_snapshot_json)
    except json.JSONDecodeError as error:
        raise RiskExportNotFoundError("风险预跑审阅冻结报告不可读") from error
    if not isinstance(report, dict):
        raise RiskExportNotFoundError("风险预跑审阅冻结报告不可读")
    # Tolerate pre-#91 snapshots: missing issue_lists → empty lists.
    if "issue_lists" not in report or not isinstance(report.get("issue_lists"), dict):
        report = {
            **report,
            "issue_lists": {"recognition": [], "integrity": []},
        }
    return build_risk_evidence_pack(report)
