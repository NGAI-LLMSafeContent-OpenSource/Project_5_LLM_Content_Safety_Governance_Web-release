"""Create database leases and sanitized persistent task events."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceTaskEvent, GovernanceTaskLease


VERSION = "0005-governance-task-runtime"
TABLES = (GovernanceTaskLease.__table__, GovernanceTaskEvent.__table__)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
