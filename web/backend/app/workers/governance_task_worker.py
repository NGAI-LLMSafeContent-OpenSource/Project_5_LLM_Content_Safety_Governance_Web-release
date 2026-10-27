"""Run the database-backed governance task worker as a separate process.

Usage: ``python -m app.workers.governance_task_worker``
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
from uuid import uuid4

from app.services.governance_task_runtime import GovernanceTaskWorker


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run governance task worker")
    parser.add_argument("--once", action="store_true", help="claim at most one task")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--lease-seconds", type=int, default=30)
    parser.add_argument("--worker-id", default="")
    return parser


async def run(args: argparse.Namespace) -> None:
    worker_id = args.worker_id or os.environ.get("GOVERNANCE_WORKER_ID") or (
        f"{socket.gethostname()}-{os.getpid()}-{str(uuid4())[:8]}"
    )
    worker = GovernanceTaskWorker(worker_id, lease_seconds=args.lease_seconds)
    while True:
        claimed = await worker.run_once()
        if args.once:
            return
        if not claimed:
            await asyncio.sleep(max(0.1, args.poll_seconds))


def main() -> None:
    asyncio.run(run(_parser().parse_args()))


if __name__ == "__main__":
    main()
