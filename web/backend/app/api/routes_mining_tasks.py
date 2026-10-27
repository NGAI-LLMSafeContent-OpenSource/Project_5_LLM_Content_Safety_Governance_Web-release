import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ok
from app.db.session import get_db
from app.schemas.mining_tasks import (
    DefinitionScope,
    MiningTaskRerunRequest,
    MiningTaskSaveHistoryRequest,
    MiningTaskStart,
)
from app.services.mining_task_service import (
    get_task,
    get_task_artifacts,
    get_task_history_results,
    get_task_logs,
    get_task_results,
    list_saved_mining_tasks,
    rerun_task,
    create_mining_task,
    save_mining_task_to_history,
)
from app.services.mining_task_scheduler import schedule_mining_task


router = APIRouter(prefix="/api/mining-tasks", tags=["mining-tasks"])


@router.post("/start")
async def start_task(
    payload: MiningTaskStart,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await create_mining_task(
            db,
            task_type=payload.task_type,
            definition_scope=payload.definition_scope,
            input_id=payload.input_id,
            inline_input=payload.input,
        )
        schedule_mining_task(data["task_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ok(data)


@router.get("/history")
async def list_history(
    definition_scope: DefinitionScope,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    data = await list_saved_mining_tasks(
        db,
        definition_scope=definition_scope,
        limit=limit,
    )
    return ok(data)


@router.post("/{task_id}/save-history")
async def save_task_history(
    task_id: str,
    payload: MiningTaskSaveHistoryRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await save_mining_task_to_history(
            db,
            task_id=task_id,
            title=payload.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if data is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(data)


@router.get("/{task_id}/history-results")
async def read_task_history_results(
    task_id: str,
    definition_scope: DefinitionScope,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await get_task_history_results(
            db,
            task_id,
            definition_scope=definition_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if data is None:
        raise HTTPException(status_code=404, detail="未找到当前定义页签的历史记录")
    return ok(data)


@router.get("/{task_id}")
async def read_task(task_id: str, db: AsyncSession = Depends(get_db)):
    data = await get_task(db, task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(data)


@router.get("/{task_id}/results")
async def read_task_results(task_id: str, db: AsyncSession = Depends(get_db)):
    data = await get_task_results(db, task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(data)


@router.get("/{task_id}/artifacts")
async def read_task_artifacts(task_id: str, db: AsyncSession = Depends(get_db)):
    data = await get_task_artifacts(db, task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(data)


@router.post("/{task_id}/rerun")
async def rerun_task_route(
    task_id: str,
    payload: MiningTaskRerunRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await rerun_task(db, task_id=task_id, comment=payload.comment)
    if data is None:
        raise HTTPException(status_code=404, detail="task not found")
    schedule_mining_task(data["task_id"])
    return ok(data)


@router.get("/{task_id}/logs")
async def read_task_logs(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(await get_task_logs(db, task_id))


@router.websocket("/{task_id}/logs")
async def task_logs_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    last_count = 0

    try:
        while True:
            async for db in get_db():
                task = await get_task(db, task_id)
                if task is None:
                    await websocket.close(code=1008)
                    return
                logs = await get_task_logs(db, task_id)

            if len(logs) > last_count:
                for item in logs[last_count:]:
                    await websocket.send_text(json.dumps(item, ensure_ascii=False))
                last_count = len(logs)

            if task["status"] != "running" and last_count == len(logs):
                await websocket.close()
                return

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
