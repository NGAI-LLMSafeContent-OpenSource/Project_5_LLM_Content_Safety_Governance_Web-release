"""Add the idempotency identity for explicit Benchmark sample disclosure."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

VERSION = "0016-benchmark-sample-disclosure-request-id"
TABLES: tuple = ()
TABLE_NAMES: tuple[str, ...] = ()

TABLE_NAME = "benchmark_sample_access_events"
UNIQUE_INDEX_NAME = "uq_benchmark_sample_access_events_disclosure_request_id"


def upgrade(conn: Connection) -> None:
    inspector = inspect(conn)
    if TABLE_NAME not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "disclosure_request_id" not in columns:
        conn.execute(
            text(
                "ALTER TABLE benchmark_sample_access_events "
                "ADD COLUMN disclosure_request_id VARCHAR(36) NULL"
            )
        )

    indexes = {index["name"] for index in inspect(conn).get_indexes(TABLE_NAME)}
    if UNIQUE_INDEX_NAME not in indexes:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX "
                "uq_benchmark_sample_access_events_disclosure_request_id "
                "ON benchmark_sample_access_events (disclosure_request_id)"
            )
        )
