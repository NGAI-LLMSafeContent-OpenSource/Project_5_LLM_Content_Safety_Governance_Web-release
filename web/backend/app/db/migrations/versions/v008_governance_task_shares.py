"""Add governance review-share tokens and access audit events."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceShareAccessEvent, GovernanceTaskShare


VERSION = "0008-governance-task-shares"
TABLES = (GovernanceTaskShare.__table__, GovernanceShareAccessEvent.__table__)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
