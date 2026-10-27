import asyncio

from app.services.benchmark_task_service import run_benchmark_task_in_background


def schedule_benchmark_task(task_id: str) -> asyncio.Task[None]:
    return asyncio.create_task(run_benchmark_task_in_background(task_id))
