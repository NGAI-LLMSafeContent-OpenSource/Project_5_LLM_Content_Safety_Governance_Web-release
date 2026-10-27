import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TaskArtifact


async def replace_task_artifacts(
    db: AsyncSession,
    *,
    task_id: str,
    artifacts: dict[str, dict | list],
) -> None:
    existing = await db.execute(select(TaskArtifact).where(TaskArtifact.task_id == task_id))
    for row in existing.scalars().all():
        await db.delete(row)

    for artifact_type, content in artifacts.items():
        db.add(
            TaskArtifact(
                task_id=task_id,
                artifact_type=artifact_type,
                content_json=json.dumps(content, ensure_ascii=False),
            )
        )

    await db.commit()


async def read_task_artifacts(db: AsyncSession, task_id: str) -> list[dict]:
    result = await db.execute(
        select(TaskArtifact).where(TaskArtifact.task_id == task_id).order_by(TaskArtifact.id)
    )
    return [
        {
            "artifact_type": row.artifact_type,
            "content": json.loads(row.content_json or "{}"),
        }
        for row in result.scalars().all()
    ]
