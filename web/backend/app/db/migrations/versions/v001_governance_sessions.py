"""Create the client, session and message tables without touching legacy tables."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceClient, GovernanceMessage, GovernanceSession


VERSION = "0001-governance-sessions"
TABLES = (
    GovernanceClient.__table__,
    GovernanceSession.__table__,
    GovernanceMessage.__table__,
)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
