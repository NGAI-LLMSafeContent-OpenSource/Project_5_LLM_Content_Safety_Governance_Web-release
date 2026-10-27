"""Add immutable per-run sample outcomes and skill-run completion time."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from app.db.models import GovernanceRunSampleResult


VERSION = "0006-governance-run-sample-results"
TABLES = (GovernanceRunSampleResult.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)

    columns = {
        column["name"]
        for column in inspect(conn).get_columns("governance_skill_runs")
    }
    if "finished_at" not in columns:
        conn.execute(
            text("ALTER TABLE governance_skill_runs ADD COLUMN finished_at DATETIME")
        )
