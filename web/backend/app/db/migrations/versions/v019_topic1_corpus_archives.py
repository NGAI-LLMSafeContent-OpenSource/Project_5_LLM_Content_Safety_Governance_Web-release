"""Atomic, bounded output archives scoped through their owning job."""
from sqlalchemy.engine import Connection
from app.db.models import Topic1CorpusArchive

VERSION = "0019-topic1-corpus-archives"
TABLES = (Topic1CorpusArchive.__table__,)
TABLE_NAMES = tuple(table.name for table in TABLES)


def upgrade(conn: Connection) -> None:
    for table in TABLES:
        table.create(conn, checkfirst=True)
