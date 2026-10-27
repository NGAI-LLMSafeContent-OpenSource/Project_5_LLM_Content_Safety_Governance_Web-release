import asyncio

from app.services.mining_task_service import run_mining_task_in_background


def schedule_mining_task(task_id: str) -> asyncio.Task[None]:
    return asyncio.create_task(run_mining_task_in_background(task_id))
