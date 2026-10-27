import os

import httpx

from app.adapters.topic1.contracts import normalize_topic1_remote_result
from app.adapters.topic1.dimension_matcher import match_indicator_paths
from app.adapters.topic1.indicator_generator import generate_candidate_indicators
from app.adapters.topic1.project1_remote_adapter import (
    PROJECT1_AGENTS_API_MODE,
    run_project1_agents_mining,
)
from app.adapters.topic1.result_normalizer import normalize_topic1_result

LOCAL_ADAPTER_MODE = "local_adapter"
REMOTE_ADAPTER_MODE = "remote_algorithm_api"


def get_topic1_adapter_mode() -> str:
    mode = (
        os.getenv("TOPIC1_ALGORITHM_MODE", PROJECT1_AGENTS_API_MODE).strip()
        or PROJECT1_AGENTS_API_MODE
    )
    allowed_modes = {LOCAL_ADAPTER_MODE, REMOTE_ADAPTER_MODE, PROJECT1_AGENTS_API_MODE}
    if mode not in allowed_modes:
        raise ValueError(
            "Topic1AlgorithmAdapter: invalid TOPIC1_ALGORITHM_MODE "
            f"{mode!r}; expected one of {sorted(allowed_modes)}"
        )
    return mode


async def _run_remote_topic1_mining(
    definition_type: str, input_texts: list[str], confidence_threshold: float
) -> dict:
    endpoint = os.getenv("TOPIC1_ALGORITHM_URL", "").strip()
    if not endpoint:
        raise ValueError("Topic1AlgorithmAdapter: TOPIC1_ALGORITHM_URL is required")

    timeout = float(os.getenv("TOPIC1_ALGORITHM_TIMEOUT_SECONDS", "30"))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                endpoint,
                json={
                    "definition_type": definition_type,
                    "input_texts": input_texts,
                    "confidence_threshold": confidence_threshold,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise ValueError(f"Topic1AlgorithmAdapter: remote algorithm request failed: {exc}") from exc

    try:
        payload = normalize_topic1_remote_result(payload)
    except Exception as exc:
        raise ValueError(f"Topic1AlgorithmAdapter: invalid remote response: {exc}") from exc
    payload["stats"] = {**payload.get("stats", {}), "adapter_mode": REMOTE_ADAPTER_MODE}
    return payload


async def run_topic1_mining(
    definition_type: str,
    input_texts: list[str],
    confidence_threshold: float = 0.2,
    input_sources: list[dict] | None = None,
    input_data: dict | None = None,
) -> dict:
    adapter_mode = get_topic1_adapter_mode()
    if adapter_mode == PROJECT1_AGENTS_API_MODE:
        return await run_project1_agents_mining(
            definition_type=definition_type,
            input_texts=input_texts,
            input_sources=input_sources,
            input_data=input_data,
        )
    if adapter_mode == REMOTE_ADAPTER_MODE:
        return await _run_remote_topic1_mining(definition_type, input_texts, confidence_threshold)

    prepared_texts = input_texts
    merged_text = "\n".join(prepared_texts)
    matched = match_indicator_paths(
        input_texts=prepared_texts,
        confidence_threshold=confidence_threshold,
        definition_type=definition_type,
    )
    candidate_result = generate_candidate_indicators(
        definition_type=definition_type,
        matched_paths=matched["matched_paths"],
        text=merged_text,
    )
    return {
        **normalize_topic1_result(
            prepared_texts=prepared_texts,
            matched_paths=matched["matched_paths"],
            candidates=candidate_result["candidate_indicators"],
            extra_stats={**candidate_result["stats"], "adapter_mode": LOCAL_ADAPTER_MODE},
        ),
        "prepared_texts": prepared_texts,
        "matched_paths": matched["matched_paths"],
        "dimension_data": {
            "matched_paths": matched["matched_paths"],
            "matched_level1": matched.get("matched_level1", []),
            "matched_level2": matched.get("matched_level2", []),
            "uncovered": matched.get("uncovered", False),
        },
        "agent_outputs": {
            "dimension_matcher": {
                "matched_paths_count": len(matched["matched_paths"]),
                "uncovered": matched.get("uncovered", False),
            },
            "indicator_generator": candidate_result["stats"],
        },
        "request_context": {
            "definition_type": definition_type,
            "confidence_threshold": confidence_threshold,
            "adapter_mode": LOCAL_ADAPTER_MODE,
        },
    }
