import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MiningInput, SourceDocument
from app.schemas.mining_inputs import MiningInputSave
from app.services.document_parser import content_hash


def serialize_input(row: MiningInput) -> dict:
    return {
        "id": row.id,
        "definition_type": row.definition_type,
        "policy_text": row.policy_text,
        "sample_text": row.sample_text,
        "uploaded_document_ids": json.loads(row.uploaded_document_ids_json or "[]"),
        "web_links": json.loads(row.web_links_json or "[]"),
        "lookup_names": json.loads(row.lookup_names_json or "[]"),
        "mining_demand": row.mining_demand,
        "level1": row.level1,
        "level2": row.level2,
        "status": row.status,
    }


async def save_mining_input(db: AsyncSession, payload: MiningInputSave) -> dict:
    row = MiningInput(
        definition_type=payload.definition_type,
        policy_text=payload.policy_text,
        sample_text=payload.sample_text,
        uploaded_document_ids_json=json.dumps(
            payload.uploaded_document_ids, ensure_ascii=False
        ),
        web_links_json=json.dumps(payload.web_links, ensure_ascii=False),
        lookup_names_json=json.dumps(payload.lookup_names, ensure_ascii=False),
        mining_demand=payload.mining_demand,
        level1=payload.level1,
        level2=payload.level2,
        status="draft",
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return serialize_input(row)


async def get_mining_input(db: AsyncSession, input_id: int) -> dict | None:
    result = await db.execute(select(MiningInput).where(MiningInput.id == input_id))
    row = result.scalar_one_or_none()
    return serialize_input(row) if row else None


async def save_source_document(
    db: AsyncSession,
    *,
    title: str,
    content: str,
    source_type: str,
    source_url: str | None = None,
) -> dict:
    digest = content_hash(content)
    existing = await db.execute(
        select(SourceDocument).where(SourceDocument.content_hash == digest)
    )
    row = existing.scalar_one_or_none()

    if row is None:
        row = SourceDocument(
            title=title[:200],
            content=content,
            source_type=source_type,
            source_url=source_url,
            content_hash=digest,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

    return {
        "id": row.id,
        "name": row.title,
        "content": row.content,
        "source_type": row.source_type,
        "source_url": row.source_url,
    }
