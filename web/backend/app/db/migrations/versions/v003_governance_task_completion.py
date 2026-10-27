"""Create governance task and completion-record tables."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceCompletionRecord, GovernanceTask


VERSION = "0003-governance-task-completion"
TABLES = (
    GovernanceTask.__table__,
    GovernanceCompletionRecord.__table__,
)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)