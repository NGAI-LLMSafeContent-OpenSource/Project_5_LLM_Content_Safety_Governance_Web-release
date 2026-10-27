import os
from typing import Any

import httpx

PROJECT1_AGENTS_API_MODE = "project1_agents_api"
PROJECT1_START_MINING_PATH = "/api/agents/start-mining"

DEMAND_TO_PROJECT1 = {
    "level3": "level3",
    "三级指标": "level3",
    "三级指标挖掘": "level3",
}


def resolve_project1_start_mining_url() -> str:
    explicit_url = os.getenv("TOPIC1_ALGORITHM_URL", "").strip()
    if explicit_url:
        return explicit_url

    base_url = os.getenv("TOPIC1_PROJECT1_BASE_URL", "http://127.0.0.1:6102").strip()
    if not base_url:
        raise ValueError("Project1Adapter: TOPIC1_PROJECT1_BASE_URL is required")
    return f"{base_url.rstrip('/')}{PROJECT1_START_MINING_PATH}"


def build_project1_start_mining_payload(
    *,
    input_texts: list[str],
    input_sources: list[dict[str, Any]] | None = None,
    input_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    input_data = input_data or {}
    prepared_sources = input_sources or []
    standard_texts = _project1_standard_texts(
        input_texts=input_texts,
        input_sources=prepared_sources,
    )
    uploaded_documents = [
        {
            "name": str(source.get("name") or "uploaded-document"),
            "content": str(source.get("content") or "")[:20000],
            "source_type": str(source.get("source_type") or "upload"),
        }
        for source in prepared_sources
        if source.get("source_type") == "upload" and source.get("content")
    ]

    manual_policy = str(input_data.get("policy_text") or "").strip()
    manual_sample = str(input_data.get("sample_text") or "").strip()
    mining_demand = _project1_mining_demand(input_data.get("mining_demand"))

    return {
        "policy_texts": [manual_policy] if manual_policy else [],
        "standard_texts": standard_texts,
        "case_texts": [manual_sample] if manual_sample else [],
        "web_links": [link for link in input_data.get("web_links") or [] if link],
        "lookup_names": [name for name in input_data.get("lookup_names") or [] if name],
        "uploaded_documents": uploaded_documents,
        "mining_demand": mining_demand,
    }


def _project1_mining_demand(value: Any) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return "level3"
    if raw_value in DEMAND_TO_PROJECT1:
        return DEMAND_TO_PROJECT1[raw_value]
    raise ValueError(
        "Project1Adapter: unsupported mining_demand "
        f"{raw_value!r}; the formal Topic 1 workflow only supports level3 "
        "candidate mining under fixed level1/level2 ontology"
    )


def _project1_standard_texts(
    *,
    input_texts: list[str],
    input_sources: list[dict[str, Any]],
) -> list[str]:
    if not input_sources:
        return [text for text in input_texts if text]

    standard_source_types = {"lookup", "link", "link_fallback"}
    texts = [
        str(source.get("content") or "")[:20000]
        for source in input_sources
        if source.get("source_type") in standard_source_types and source.get("content")
    ]
    return texts


def normalize_project1_start_mining_result(
    payload: dict[str, Any],
    *,
    definition_type: str,
    input_texts: list[str],
) -> dict[str, Any]:
    if not payload.get("success", True):
        message = payload.get("message") or payload.get("detail") or "Project1 mining failed"
        raise ValueError(f"Project1Adapter: {message}")

    candidates = _normalize_project1_candidates(
        payload=payload,
        definition_type=definition_type,
    )
    project1_stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    stats = {
        **project1_stats,
        "adapter_mode": PROJECT1_AGENTS_API_MODE,
        "project1_task_id": payload.get("task_id", ""),
        "input_text_count": len(input_texts),
        "candidate_count": len(candidates),
        "imported_count": payload.get("imported_count", len(candidates)),
        "pending_review_count": payload.get("pending_review_count", len(candidates)),
    }

    dimension_data = payload.get("dimension_data") if isinstance(payload.get("dimension_data"), dict) else {}
    matched_paths = _extract_matched_paths(dimension_data, candidates)

    return {
        "logs": _build_project1_logs(payload, len(candidates)),
        "stats": stats,
        "candidate_indicators": candidates,
        "prepared_texts": input_texts,
        "matched_paths": matched_paths,
        "dimension_data": dimension_data,
        "agent_outputs": payload.get("agent_outputs") if isinstance(payload.get("agent_outputs"), dict) else {},
        "request_context": {
            **(
                payload.get("request_context")
                if isinstance(payload.get("request_context"), dict)
                else {}
            ),
            "adapter_mode": PROJECT1_AGENTS_API_MODE,
            "project1_task_id": payload.get("task_id", ""),
            "name_review_required": payload.get("name_review_required", True),
        },
    }


async def run_project1_agents_mining(
    *,
    definition_type: str,
    input_texts: list[str],
    input_sources: list[dict[str, Any]] | None = None,
    input_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    endpoint = resolve_project1_start_mining_url()
    timeout = float(os.getenv("TOPIC1_ALGORITHM_TIMEOUT_SECONDS", "300"))
    request_payload = build_project1_start_mining_payload(
        input_texts=input_texts,
        input_sources=input_sources,
        input_data=input_data,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(endpoint, json=request_payload)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise ValueError(f"Project1Adapter: start-mining request failed: {exc}") from exc

    try:
        result = normalize_project1_start_mining_result(
            payload,
            definition_type=definition_type,
            input_texts=input_texts,
        )
    except Exception as exc:
        raise ValueError(f"Project1Adapter: invalid start-mining response: {exc}") from exc

    result["request_context"] = {
        **result.get("request_context", {}),
        "adapter_source": "project1_agents_api",
        "input_summary": _payload_snapshot(request_payload),
    }
    return result


def _payload_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_text_count": len(payload.get("policy_texts") or []),
        "standard_text_count": len(payload.get("standard_texts") or []),
        "case_text_count": len(payload.get("case_texts") or []),
        "web_links": payload.get("web_links") or [],
        "lookup_names": payload.get("lookup_names") or [],
        "uploaded_document_count": len(payload.get("uploaded_documents") or []),
        "mining_demand": payload.get("mining_demand"),
    }


def _candidate_source_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    # Project 1 defines all_indicators as a full ontology/result snapshot for display
    # and debugging. The Project 5 review workflow should only consume candidate
    # collections: imported_indicators first, then new_indicators, then indicators.
    return _first_non_empty_candidate_list(
        payload,
        ("imported_indicators", "new_indicators", "indicators"),
    )


def _first_non_empty_candidate_list(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list) and value:
            return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_project1_candidates(
    *,
    payload: dict[str, Any],
    definition_type: str,
) -> list[dict[str, Any]]:
    from app.adapters.topic1.predefined_dimensions import normalize_level1, normalize_level2

    normalized = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in _candidate_source_items(payload):
        level1 = normalize_level1(_string_value(item, "level1", "dimension", "category"))
        level2 = normalize_level2(_string_value(item, "level2", "sub_dimension"))
        level3 = _string_value(item, "level3", "display_name", "projected_label", "name")
        name = _string_value(item, "name", "display_name", "projected_label", "level3") or level3
        if not name:
            continue

        key = (level1, level2, level3, name)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "definition_type": definition_type,
                "name": name,
                "level1": level1 or "未分组一级指标",
                "level2": level2 or "未分组二级指标",
                "level3": level3 or name,
                "definition": _string_value(item, "definition", "description"),
                "formula": _string_value(
                    item,
                    "formula",
                    "calculation_formula",
                    "scoring_rule",
                ),
                "source": _source_text(item),
                "rationale": _rationale_text(item),
                "evidence_text": _evidence_text(item),
                "confidence": _confidence_value(item),
            }
        )
    return normalized


def _string_value(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _confidence_value(item: dict[str, Any]) -> float:
    value = item.get("confidence", item.get("score", 0.75))
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.75


def _source_text(item: dict[str, Any]) -> str:
    source = item.get("source")
    if isinstance(source, list):
        return "；".join(str(part) for part in source if part)
    return str(source or "课题一主流价值评估体系").strip()


def _rationale_text(item: dict[str, Any]) -> str:
    parts = [
        _string_value(item, "rationale", "reason", "explanation", "explain_reason"),
        _format_examples(
            "正例",
            item.get("positive_examples", item.get("positive_example")),
        ),
        _format_examples(
            "反例",
            item.get("negative_examples", item.get("negative_example")),
        ),
    ]
    return "\n".join(part for part in parts if part)


def _evidence_text(item: dict[str, Any]) -> str:
    evidence = item.get("evidence_text", item.get("evidence"))
    if isinstance(evidence, list):
        return "\n".join(str(part) for part in evidence if part)
    return str(evidence or "").strip()


def _format_examples(label: str, value: Any) -> str:
    if isinstance(value, list) and value:
        return f"{label}：" + "；".join(str(part) for part in value if part)
    if isinstance(value, str) and value.strip():
        return f"{label}：{value.strip()}"
    return ""


def _extract_matched_paths(
    dimension_data: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from app.adapters.topic1.predefined_dimensions import normalize_level1, normalize_level2

    for key in ("matched_paths", "paths", "matched_indicators"):
        items = dimension_data.get(key)
        if isinstance(items, list):
            normalized_paths = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                path = dict(item)
                if "level1" in path:
                    path["level1"] = normalize_level1(str(path.get("level1") or ""))
                if "level2" in path:
                    path["level2"] = normalize_level2(str(path.get("level2") or ""))
                normalized_paths.append(path)
            return normalized_paths

    return [
        {
            "name": item["name"],
            "level1": item["level1"],
            "level2": item["level2"],
            "level3": item["level3"],
            "confidence": item["confidence"],
            "source": item["source"],
        }
        for item in candidates
    ]


def _build_project1_logs(payload: dict[str, Any], candidate_count: int) -> list[dict[str, str]]:
    agent_outputs = payload.get("agent_outputs") if isinstance(payload.get("agent_outputs"), dict) else {}
    stage_logs = [
        (
            "PolicyTextExtractor",
            "completed",
            "课题一已完成输入材料解析与政策文本整理",
        ),
        (
            "DimensionMatcher",
            "completed",
            "课题一已完成维度抽取与预置指标路径匹配",
        ),
        (
            "IndicatorGenerator",
            "completed",
            f"课题一已返回 {candidate_count} 条候选指标，等待平台侧逐条审核",
        ),
    ]

    logs = [
        {"agent_name": agent_name, "status": status, "message": message}
        for agent_name, status, message in stage_logs
    ]
    if agent_outputs:
        logs.append(
            {
                "agent_name": "Project1Adapter",
                "status": "completed",
                "message": "课题一 agent_outputs 已写入任务工件，供后续排查与展示使用",
            }
        )
    return logs
