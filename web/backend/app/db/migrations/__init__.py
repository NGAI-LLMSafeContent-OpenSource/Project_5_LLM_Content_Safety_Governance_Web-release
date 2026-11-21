"""Versioned database changes for new governance entities."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models import SchemaMigration
from app.db.migrations.versions import (
    v001_governance_sessions,
    v002_governance_message_request_id,
    v003_governance_task_completion,
    v004_governance_skill_runtime,
    v005_governance_task_runtime,
    v006_governance_run_sample_results,
    v007_governance_skill_run_lineage,
    v008_governance_task_shares,
    v009_governance_product_events,
    v010_benchmark_sample_access_events,
    v011_governance_clarification_plans,
    v012_benchmark_asset_series,
    v013_benchmark_deliveries,
    v014_governance_capability_runs,
    v015_remove_dynbench400_eval_records,
    v016_benchmark_sample_disclosure_request_id,
    v017_remove_orphaned_dynbench_plan_messages,
    v018_topic1_corpus_tool_jobs,
    v019_topic1_corpus_archives,
)


REVISIONS = (
    v001_governance_sessions,
    v002_governance_message_request_id,
    v003_governance_task_completion,
    v004_governance_skill_runtime,
    v005_governance_task_runtime,
    v006_governance_run_sample_results,
    v007_governance_skill_run_lineage,
    v008_governance_task_shares,
    v009_governance_product_events,
    v010_benchmark_sample_access_events,
    v011_governance_clarification_plans,
    v012_benchmark_asset_series,
    v013_benchmark_deliveries,
    v014_governance_capability_runs,
    v015_remove_dynbench400_eval_records,
    v016_benchmark_sample_disclosure_request_id,
    v017_remove_orphaned_dynbench_plan_messages,
    v018_topic1_corpus_tool_jobs,
    v019_topic1_corpus_archives,
)
MIGRATED_TABLES = frozenset(
    v001_governance_sessions.TABLE_NAMES
    + v003_governance_task_completion.TABLE_NAMES
    + v004_governance_skill_runtime.TABLE_NAMES
    + v005_governance_task_runtime.TABLE_NAMES
    + v006_governance_run_sample_results.TABLE_NAMES
    + v007_governance_skill_run_lineage.TABLE_NAMES
    + v008_governance_task_shares.TABLE_NAMES
    + v009_governance_product_events.TABLE_NAMES
    + v010_benchmark_sample_access_events.TABLE_NAMES
    + v011_governance_clarification_plans.TABLE_NAMES
    + v012_benchmark_asset_series.TABLE_NAMES
    + v013_benchmark_deliveries.TABLE_NAMES
    + v014_governance_capability_runs.TABLE_NAMES
    + v015_remove_dynbench400_eval_records.TABLE_NAMES
    + v016_benchmark_sample_disclosure_request_id.TABLE_NAMES
    + v017_remove_orphaned_dynbench_plan_messages.TABLE_NAMES
    + v018_topic1_corpus_tool_jobs.TABLE_NAMES
    + v019_topic1_corpus_archives.TABLE_NAMES
)


async def apply_migrations(conn: AsyncConnection) -> None:
    applied = set((await conn.execute(select(SchemaMigration.version))).scalars())
    for revision in REVISIONS:
        if revision.VERSION in applied:
            continue
        await conn.run_sync(revision.upgrade)
        await conn.execute(SchemaMigration.__table__.insert().values(version=revision.VERSION))
