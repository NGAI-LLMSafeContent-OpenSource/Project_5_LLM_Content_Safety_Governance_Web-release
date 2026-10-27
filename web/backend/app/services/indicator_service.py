import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateIndicator, CandidateReviewEvent, Indicator
from app.schemas.indicators import CandidateUpdate


async def _add_review_event(
    db: AsyncSession,
    *,
    candidate_id: int,
    event_type: str,
    comment: str = "",
    payload: dict | None = None,
) -> None:
    db.add(
        CandidateReviewEvent(
            candidate_id=candidate_id,
            event_type=event_type,
            comment=comment,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
        )
    )
    await db.commit()


async def adopt_candidate(
    db: AsyncSession, candidate_id: int, comment: str = ""
) -> dict | None:
    result = await db.execute(
        select(CandidateIndicator).where(CandidateIndicator.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return None

    candidate.status = "adopted"
    candidate.review_comment = comment
    candidate.updated_at = datetime.utcnow()

    indicator = Indicator(
        name=candidate.name,
        definition_type=candidate.definition_type,
        level1=candidate.level1,
        level2=candidate.level2,
        level3=candidate.level3,
        definition=candidate.definition,
        source=candidate.source,
        formula=candidate.formula,
        rationale=candidate.rationale,
        source_task_id=candidate.task_id,
        adopted_from_candidate_id=candidate.id,
        status="active",
    )
    db.add(indicator)
    await db.commit()
    await db.refresh(indicator)
    await _add_review_event(
        db,
        candidate_id=candidate.id,
        event_type="adopted",
        comment=comment,
        payload={"indicator_id": indicator.id, "formula": indicator.formula},
    )

    return {
        "candidate_id": candidate.id,
        "candidate_status": candidate.status,
        "indicator_id": indicator.id,
    }


async def reject_candidate(
    db: AsyncSession, candidate_id: int, comment: str = ""
) -> dict | None:
    result = await db.execute(
        select(CandidateIndicator).where(CandidateIndicator.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return None

    candidate.status = "rejected"
    candidate.review_comment = comment
    candidate.updated_at = datetime.utcnow()
    await db.commit()
    await _add_review_event(
        db,
        candidate_id=candidate.id,
        event_type="rejected",
        comment=comment,
        payload={"status": candidate.status},
    )

    return {"candidate_id": candidate.id, "candidate_status": candidate.status}


async def update_candidate(
    db: AsyncSession, candidate_id: int, payload: CandidateUpdate
) -> dict | None:
    result = await db.execute(
        select(CandidateIndicator).where(CandidateIndicator.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return None

    candidate.name = payload.name
    candidate.level1 = payload.level1
    candidate.level2 = payload.level2
    candidate.level3 = payload.level3
    candidate.definition = payload.definition
    candidate.source = payload.source
    candidate.formula = payload.formula
    candidate.rationale = payload.rationale
    candidate.evidence_text = payload.evidence_text
    candidate.status = "edited"
    candidate.updated_at = datetime.utcnow()
    await db.commit()
    await _add_review_event(
        db,
        candidate_id=candidate.id,
        event_type="edited",
        payload={
            "name": candidate.name,
            "formula": candidate.formula,
            "rationale": candidate.rationale,
        },
    )

    return {"candidate_id": candidate.id, "candidate_status": candidate.status}


async def get_candidate_history(db: AsyncSession, candidate_id: int) -> dict | None:
    candidate = await db.execute(
        select(CandidateIndicator).where(CandidateIndicator.id == candidate_id)
    )
    row = candidate.scalar_one_or_none()
    if row is None:
        return None

    result = await db.execute(
        select(CandidateReviewEvent)
        .where(CandidateReviewEvent.candidate_id == candidate_id)
        .order_by(CandidateReviewEvent.id)
    )
    return {
        "candidate_id": candidate_id,
        "events": [
            {
                "event_type": event.event_type,
                "comment": event.comment,
                "payload": json.loads(event.payload_json or "{}"),
            }
            for event in result.scalars().all()
        ],
    }


async def get_indicator_framework(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Indicator).order_by(Indicator.level1, Indicator.level2, Indicator.level3)
    )

    tree_map: dict[str, dict] = {}
    for row in result.scalars().all():
        level1 = row.level1 or "未分类一级"
        level2 = row.level2 or "未分类二级"
        tree_map.setdefault(level1, {"name": level1, "children": {}})
        tree_map[level1]["children"].setdefault(
            level2, {"name": level2, "children": []}
        )
        tree_map[level1]["children"][level2]["children"].append(
            {
                "id": row.id,
                "name": row.level3 or row.name,
                "definition": row.definition,
                "source": row.source,
                "formula": row.formula,
                "rationale": row.rationale,
                "source_task_id": row.source_task_id,
            }
        )

    tree = [
        {"name": level1["name"], "children": list(level1["children"].values())}
        for level1 in tree_map.values()
    ]
    return {"tree": tree}
