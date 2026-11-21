"""Persist Topic 1 upstream jobs without modifying other task tables."""

from sqlalchemy.engine import Connection
from app.db.models import Topic1CorpusToolJob

VERSION = "0018-topic1-corpus-tool-jobs"
TABLES = (Topic1CorpusToolJob.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
