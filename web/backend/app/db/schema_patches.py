"""Lightweight column patches for create_all-only deployments."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection


async def ensure_mining_task_history_columns(conn: AsyncConnection) -> None:
    """Add definition-history columns to an existing mining_tasks table."""

    def column_names(sync_conn) -> set[str]:
        return {column["name"] for column in inspect(sync_conn).get_columns("mining_tasks")}

    existing = await conn.run_sync(column_names)
    statements: list[str] = []
    if "definition_scope" not in existing:
        statements.append(
            "ALTER TABLE mining_tasks ADD COLUMN definition_scope VARCHAR(40) NOT NULL "
            "DEFAULT 'input-value'"
        )
    if "saved_to_history" not in existing:
        statements.append(
            "ALTER TABLE mining_tasks ADD COLUMN saved_to_history BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "history_title" not in existing:
        statements.append("ALTER TABLE mining_tasks ADD COLUMN history_title VARCHAR(200)")
    if "saved_at" not in existing:
        statements.append("ALTER TABLE mining_tasks ADD COLUMN saved_at DATETIME")
    if "history_snapshot_json" not in existing:
        statements.append(
            "ALTER TABLE mining_tasks ADD COLUMN history_snapshot_json TEXT NOT NULL DEFAULT '{}'"
        )
    for statement in statements:
        await conn.execute(text(statement))
