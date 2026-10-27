"""Add first-class governance capability runs (#164 T2)."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceCapabilityRun


VERSION = "0014-governance-capability-runs"
TABLES = (GovernanceCapabilityRun.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
