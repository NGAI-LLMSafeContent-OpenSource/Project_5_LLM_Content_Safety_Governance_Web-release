"""Add anonymized governance product-funnel events (#67 / #83)."""

from sqlalchemy.engine import Connection

from app.db.models import GovernanceProductEvent


VERSION = "0009-governance-product-events"
TABLES = (GovernanceProductEvent.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
