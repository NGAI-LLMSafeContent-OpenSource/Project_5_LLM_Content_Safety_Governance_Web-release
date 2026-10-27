"""Create the versioned governance skill-run and capability-step tables."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceCapabilityStep, GovernanceSkillRun


VERSION = "0004-governance-skill-runtime"
TABLES = (
    GovernanceSkillRun.__table__,
    GovernanceCapabilityStep.__table__,
)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
