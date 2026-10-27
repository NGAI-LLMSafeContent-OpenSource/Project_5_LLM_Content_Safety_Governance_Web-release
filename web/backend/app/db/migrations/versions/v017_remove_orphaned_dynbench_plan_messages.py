"""Delete orphaned plan messages for the retired DynBench capability (#164).

``v015`` removed the ``dynbench400_eval`` task graph, but historical plan
messages store the retired capability inside ``payload_json`` while their
message kind is ``governance_skill_plan``.  Parse only those plan payloads and
delete exact structured matches; free text that merely names the DynBench400
asset remains historical conversation context.
"""

from __future__ import annotations

import json

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

VERSION = "0017-remove-orphaned-dynbench-plan-messages"
TABLES: tuple = ()
TABLE_NAMES: tuple[str, ...] = ()

PLAN_MESSAGE_KIND = "governance_skill_plan"
RETIRED_SKILL_KEY = "dynbench400-eval"
RETIRED_CAPABILITY = "dynbench400_eval"


def _is_retired_plan_payload(raw_payload: str | None) -> bool:
    try:
        payload = json.loads(raw_payload or "{}")
    except (TypeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return (
        payload.get("skill_key") == RETIRED_SKILL_KEY
        or payload.get("capability") == RETIRED_CAPABILITY
    )


def orphaned_plan_message_ids(conn: Connection) -> list[int]:
    """Return exact legacy plan-message matches in stable order."""

    rows = conn.execute(
        text(
            "SELECT id, payload_json FROM governance_messages "
            "WHERE kind = :kind ORDER BY id"
        ),
        {"kind": PLAN_MESSAGE_KIND},
    )
    return [int(row[0]) for row in rows if _is_retired_plan_payload(row[1])]


def upgrade(conn: Connection) -> None:
    message_ids = orphaned_plan_message_ids(conn)
    if not message_ids:
        return
    statement = text(
        "DELETE FROM governance_messages WHERE id IN :message_ids"
    ).bindparams(bindparam("message_ids", expanding=True))
    conn.execute(statement, {"message_ids": message_ids})
