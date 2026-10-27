"""Add client-scoped idempotent request_id to governance messages."""

from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


VERSION = "0002-governance-message-request-id"
TABLE_NAMES = ()


def upgrade(conn: Connection) -> None:
    columns = {column["name"] for column in inspect(conn).get_columns("governance_messages")}
    if "request_id" not in columns:
        conn.execute(text("ALTER TABLE governance_messages ADD COLUMN client_id VARCHAR(36)"))
        conn.execute(
            text("ALTER TABLE governance_messages ADD COLUMN request_id VARCHAR(36)")
        )
        conn.execute(
            text(
                "UPDATE governance_messages SET client_id = ("
                "SELECT client_id FROM governance_sessions "
                "WHERE governance_sessions.session_id = governance_messages.session_id)"
            )
        )
        for (message_id,) in conn.execute(
            text("SELECT id FROM governance_messages")
        ).fetchall():
            conn.execute(
                text("UPDATE governance_messages SET request_id = :request_id WHERE id = :id"),
                {"request_id": str(uuid4()), "id": message_id},
            )

    index_names = {
        index["name"] for index in inspect(conn).get_indexes("governance_messages")
    }
    if "uq_governance_messages_client_request" not in index_names:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX uq_governance_messages_client_request "
                "ON governance_messages (client_id, request_id)"
            )
        )