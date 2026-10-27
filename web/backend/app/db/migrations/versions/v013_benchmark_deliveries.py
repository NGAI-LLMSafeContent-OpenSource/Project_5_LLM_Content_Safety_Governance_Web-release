"""Add Benchmark delivery records for the management import."""

from sqlalchemy.engine import Connection

from app.db.models import BenchmarkDelivery


VERSION = "0013-benchmark-deliveries"
TABLES = (BenchmarkDelivery.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
