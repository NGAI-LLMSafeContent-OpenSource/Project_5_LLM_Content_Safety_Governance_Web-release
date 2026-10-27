"""Add durable pre-task governance clarification plans."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceClarificationPlan


VERSION = "0011-governance-clarification-plans"
TABLES = (GovernanceClarificationPlan.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
