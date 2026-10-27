"""Add versioned Benchmark asset series and their current-version pointer."""

from sqlalchemy.engine import Connection

from app.db.models import BenchmarkAssetSeries, BenchmarkAssetVersion


VERSION = "0012-benchmark-asset-series"
TABLES = (BenchmarkAssetSeries.__table__, BenchmarkAssetVersion.__table__)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
