import logging
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.topic1.policy_text_extractor import extract_mining_texts
from app.db.models import SourceDocument
from app.services.document_parser import clean_text, extract_text_from_bytes

logger = logging.getLogger(__name__)


async def resolve_lookup_documents(
    db: AsyncSession, lookup_names: list[str]
) -> list[dict[str, str]]:
    names = [clean_text(name) for name in lookup_names if clean_text(name)]
    if not names:
        return []

    result = await db.execute(
        select(SourceDocument).where(SourceDocument.title.in_(names))
    )
    rows_by_title = {row.title: row for row in result.scalars().all()}
    return [
        {
            "id": str(rows_by_title[name].id),
            "name": name,
            "content": rows_by_title[name].content,
            "source_type": rows_by_title[name].source_type,
        }
        for name in names
        if name in rows_by_title
    ]


async def fetch_link_document_text(link: str) -> str:
    normalized_link = clean_text(link)
    if not normalized_link:
        return ""

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(normalized_link)
            response.raise_for_status()
    except httpx.HTTPError:
        return ""

    parsed = urlparse(normalized_link)
    filename = parsed.path.rsplit("/", 1)[-1] or "index.html"
    content_type = response.headers.get("content-type", "")
    try:
        return extract_text_from_bytes(filename, response.content, content_type)
    except ValueError as exc:
        logger.warning("Failed to parse linked document %s: %s", normalized_link, exc)
        return ""


async def _read_uploaded_documents(
    db: AsyncSession, uploaded_document_ids: list[int]
) -> list[dict[str, str]]:
    if not uploaded_document_ids:
        return []

    result = await db.execute(
        select(SourceDocument).where(SourceDocument.id.in_(uploaded_document_ids))
    )
    rows_by_id = {row.id: row for row in result.scalars().all()}
    return [
        {
            "id": str(document_id),
            "name": rows_by_id[document_id].title,
            "content": rows_by_id[document_id].content,
            "source_type": rows_by_id[document_id].source_type,
        }
        for document_id in uploaded_document_ids
        if document_id in rows_by_id
    ]


def _source_snapshot(item: dict[str, str]) -> dict[str, str]:
    content = item.get("content", "")
    return {
        key: value
        for key, value in {
            **item,
            "content_preview": content[:300],
        }.items()
        if key != "content"
    }


def _prepared_source(item: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in item.items()
        if key in {"name", "content", "source_type", "source_url"} and value
    }


async def build_topic1_input_bundle(db: AsyncSession, input_data: dict) -> dict:
    texts: list[str] = []
    sources: list[dict[str, str]] = []

    policy = clean_text(input_data.get("policy_text", ""))
    if policy:
        texts.append(policy)
        sources.append(
            {"source_type": "manual_policy", "name": "policy_text", "content": policy}
        )

    sample = clean_text(input_data.get("sample_text", ""))
    if sample:
        texts.append(sample)
        sources.append(
            {"source_type": "manual_sample", "name": "sample_text", "content": sample}
        )

    for item in await resolve_lookup_documents(
        db, input_data.get("lookup_names") or []
    ):
        content = clean_text(item.get("content", ""))
        if content:
            texts.append(content)
            sources.append({**item, "content": content})

    for item in await _read_uploaded_documents(
        db, input_data.get("uploaded_document_ids") or []
    ):
        content = clean_text(item.get("content", ""))
        if content:
            texts.append(content)
            sources.append({**item, "content": content})

    for link in input_data.get("web_links") or []:
        normalized_link = clean_text(link)
        if not normalized_link:
            continue
        try:
            fetched = clean_text(await fetch_link_document_text(normalized_link))
        except Exception as exc:
            logger.warning(
                "Failed to fetch linked document %s: %s", normalized_link, exc
            )
            fetched = ""
        if fetched:
            texts.append(fetched)
            sources.append(
                {
                    "source_type": "link",
                    "name": normalized_link,
                    "source_url": normalized_link,
                    "content": fetched,
                }
            )
        else:
            fallback = f"网页链接参考：{normalized_link}"
            texts.append(fallback)
            sources.append(
                {
                    "source_type": "link_fallback",
                    "name": normalized_link,
                    "source_url": normalized_link,
                    "content": fallback,
                }
            )

    return {
        "prepared_texts": extract_mining_texts(texts),
        "prepared_sources": [_prepared_source(item) for item in sources],
        "input_sources": [_source_snapshot(item) for item in sources],
    }


async def build_topic1_input_texts(db: AsyncSession, input_data: dict) -> list[str]:
    return (await build_topic1_input_bundle(db, input_data))["prepared_texts"]
