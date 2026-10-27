"""Add Benchmark sample full-text detail access audit events."""

from sqlalchemy.engine import Connection

from app.db.models import BenchmarkSampleAccessEvent


VERSION = "0010-benchmark-sample-access-events"
TABLES = (BenchmarkSampleAccessEvent.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
