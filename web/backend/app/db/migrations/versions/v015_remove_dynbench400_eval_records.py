"""Delete the retired DynBench400 input-eval task graph (#169, W6).

ADR-0012 retires the standalone ``dynbench400_eval`` capability: new work is the
merged ``risk_corpus_rescan`` v2 capability. Sessions and stored recommendations
created before the switch can still point at the retired capability, so this
migration removes the whole legacy task graph — and nothing else.

The delete is keyed on ``governance_tasks.capability == 'dynbench400_eval'`` and
cascades only to rows that hang off those tasks (or off their skill runs), plus
the assistant messages that named the retired capability as their ``kind``. An
unrelated session, task, message, result, share, clarification plan or product
event is untouched.

``governance_product_events`` are anonymized funnel metrics; only the rows that
carried one of the deleted task ids are removed, so task-agnostic counts stay.
"""

from __future__ import annotations

from hashlib import sha256

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

VERSION = "0015-remove-dynbench400-eval-records"
TABLES: tuple = ()
TABLE_NAMES: tuple[str, ...] = ()

RETIRED_CAPABILITY = "dynbench400_eval"


def _select_column(
    conn: Connection, sql: str, column: str, values: list[str]
) -> list[str]:
    statement = text(sql).bindparams(bindparam(column, expanding=True))
    return [str(row[0]) for row in conn.execute(statement, {column: values})]


def _delete_in(conn: Connection, table: str, column: str, values: list[str]) -> None:
    if not values:
        return
    statement = text(f"DELETE FROM {table} WHERE {column} IN :values").bindparams(
        bindparam("values", expanding=True)
    )
    conn.execute(statement, {"values": values})


def retired_task_ids(conn: Connection) -> list[str]:
    """The governance tasks the retired capability owns, in stable order."""

    return [
        str(row[0])
        for row in conn.execute(
            text(
                "SELECT task_id FROM governance_tasks "
                "WHERE capability = :capability ORDER BY task_id"
            ),
            {"capability": RETIRED_CAPABILITY},
        )
    ]


def upgrade(conn: Connection) -> None:
    # Assistant replies named the retired capability as their message kind; the
    # user's own text turns never carry it, so this cannot eat a conversation.
    conn.execute(
        text("DELETE FROM governance_messages WHERE kind = :kind"),
        {"kind": RETIRED_CAPABILITY},
    )

    task_ids = retired_task_ids(conn)
    if not task_ids:
        return

    run_ids = _select_column(
        conn,
        "SELECT run_id FROM governance_skill_runs "
        "WHERE task_id IN :task_ids ORDER BY run_id",
        "task_ids",
        task_ids,
    )
    capability_run_ids = _select_column(
        conn,
        "SELECT run_id FROM governance_capability_runs "
        "WHERE task_id IN :task_ids ORDER BY run_id",
        "task_ids",
        task_ids,
    )
    share_ids = _select_column(
        conn,
        "SELECT share_id FROM governance_task_shares "
        "WHERE task_id IN :task_ids ORDER BY share_id",
        "task_ids",
        task_ids,
    )
    # A step belongs to whichever run produced it: a skill run (legacy package)
    # or a direct capability run (capability-native). Sweep both id spaces.
    step_run_ids = sorted({*run_ids, *capability_run_ids})
    task_hashes = sorted(
        {sha256(task_id.encode("utf-8")).hexdigest() for task_id in task_ids}
    )

    # Leaf-first: audit rows, then the run graph, then the task itself.
    _delete_in(conn, "governance_share_access_events", "share_id", share_ids)
    _delete_in(conn, "governance_run_sample_results", "task_id", task_ids)
    _delete_in(conn, "governance_capability_steps", "run_id", step_run_ids)
    _delete_in(conn, "governance_capability_runs", "task_id", task_ids)
    _delete_in(conn, "governance_task_events", "task_id", task_ids)
    _delete_in(conn, "governance_completion_records", "task_id", task_ids)
    _delete_in(conn, "governance_task_leases", "task_id", task_ids)
    _delete_in(conn, "governance_task_shares", "share_id", share_ids)
    _delete_in(conn, "governance_product_events", "task_id_hash", task_hashes)
    _delete_in(conn, "governance_skill_runs", "run_id", run_ids)
    _delete_in(conn, "governance_tasks", "task_id", task_ids)
