"""Add skill-run lineage and revision metadata for same-task retries."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

VERSION = "0007-governance-skill-run-lineage"
TABLE_NAMES = ()


def upgrade(conn: Connection) -> None:
    columns = {
        column["name"]
        for column in inspect(conn).get_columns("governance_skill_runs")
    }
    additions = (
        ("attempt", "INTEGER NOT NULL DEFAULT 1"),
        ("parent_run_id", "VARCHAR(36)"),
        ("scope_selection", "VARCHAR(32) NOT NULL DEFAULT 'full'"),
        ("revision_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("executor_fingerprint", "VARCHAR(128) NOT NULL DEFAULT ''"),
        ("result_schema", "VARCHAR(128) NOT NULL DEFAULT ''"),
        ("started_at", "DATETIME"),
    )
    for name, ddl in additions:
        if name not in columns:
            conn.execute(
                text(f"ALTER TABLE governance_skill_runs ADD COLUMN {name} {ddl}")
            )
