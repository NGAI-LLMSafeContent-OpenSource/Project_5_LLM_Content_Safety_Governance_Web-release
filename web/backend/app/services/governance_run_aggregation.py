"""Task-level aggregation of compatible governance skill runs."""

from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GovernanceTask
from app.schemas.governance import (
    AssetSourceRef,
    GovernanceTaskAggregatedResult,
    GovernanceTaskResultGroup,
    RiskRescanRunProvenance,
    RiskRescanSampleOutcome,
    RiskRescanSummary,
)
from app.services.governance_run_results import (
    aggregate_task_run_groups,
    list_task_run_groups,
)


def _loads_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _frozen_sample_order(task: GovernanceTask) -> list[str]:
    parameters = _loads_json(task.parameters_json)
    scope = parameters.get("root_frozen_scope") or parameters.get("frozen_scope")
    if not isinstance(scope, dict):
        return []
    ordered: list[str] = []
    for sample in scope.get("samples") or []:
        if isinstance(sample, dict) and sample.get("sample_id"):
            ordered.append(str(sample["sample_id"]))
    return ordered


def _frozen_source_refs(task: GovernanceTask) -> list[AssetSourceRef]:
    """Read the frozen scope's ``source_refs`` for the aggregated result card.

    The result message payload carries no provenance, so the task-level
    aggregated result is the only place the result card can read 来源 from
    (#65 review finding). Non-dict or blank refs are skipped so a malformed
    scope can never break aggregation.
    """

    parameters = _loads_json(task.parameters_json)
    scope = parameters.get("root_frozen_scope") or parameters.get("frozen_scope")
    if not isinstance(scope, dict):
        return []
    refs: list[AssetSourceRef] = []
    for ref in scope.get("source_refs") or []:
        if not isinstance(ref, dict) or not ref.get("ref_id") or not ref.get("name"):
            continue
        refs.append(AssetSourceRef(**ref))
    return refs


def aggregated_has_executed_samples(aggregated: Mapping[str, Any]) -> bool:
    summary = aggregated.get("summary") or {}
    return (
        int(summary.get("consistent_count") or 0)
        + int(summary.get("inconsistent_count") or 0)
        + int(summary.get("failed_count") or 0)
    ) > 0


async def build_task_aggregated_result(
    db: AsyncSession, task: GovernanceTask
) -> dict[str, Any] | None:
    """Merge compatible runs into one task result with provenance sidecars."""

    if task.capability != "risk_corpus_rescan":
        return None

    run_groups = await list_task_run_groups(db, task.task_id)
    if not any(run.get("sample_results") for run in run_groups):
        return None

    aggregated = aggregate_task_run_groups(
        run_groups, sample_order=_frozen_sample_order(task)
    )
    primary = aggregated.get("primary_group")
    if primary is None:
        primary = next(
            (group for group in aggregated["groups"] if group.get("samples")), None
        )
    if primary is None and aggregated["groups"]:
        fallback = aggregated["groups"][0]
        primary = {
            **fallback,
            "samples": [],
            "summary": {
                "consistent_count": 0,
                "inconsistent_count": 0,
                "failed_count": 0,
                "not_executed_count": 0,
            },
            "sample_count": 0,
        }
    elif primary is None:
        return None

    summary = RiskRescanSummary(**primary["summary"])
    partial = summary.failed_count > 0 or summary.not_executed_count > 0
    payload = GovernanceTaskAggregatedResult(
        task_id=task.task_id,
        status=task.status,
        method=str(primary.get("method") or ""),
        asset_id=primary.get("asset_id"),
        asset_name=primary.get("asset_name"),
        filters=dict(primary.get("filters") or {}),
        sample_count=len(primary.get("samples") or []),
        summary=summary,
        samples=[
            RiskRescanSampleOutcome(**sample) for sample in (primary.get("samples") or [])
        ],
        source_refs=_frozen_source_refs(task),
        completed_at=str(primary.get("completed_at") or ""),
        capability_version=str(primary.get("capability_version") or ""),
        partial=partial,
        runs=[
            RiskRescanRunProvenance(**item)
            for item in (aggregated.get("run_provenance") or [])
        ],
        groups=[
            GovernanceTaskResultGroup(
                **{
                    **group,
                    "summary": RiskRescanSummary(**group["summary"]),
                    "samples": [
                        RiskRescanSampleOutcome(**sample)
                        for sample in (group.get("samples") or [])
                    ],
                }
            )
            for group in (aggregated.get("groups") or [])
        ],
    )
    return payload.model_dump(mode="json")
