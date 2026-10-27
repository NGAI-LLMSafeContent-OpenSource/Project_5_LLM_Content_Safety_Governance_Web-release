from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Topic1MiningResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    logs: list[dict[str, Any]]
    stats: dict[str, Any]
    candidate_indicators: list[dict[str, Any]]
    prepared_texts: list[str]
    matched_paths: list[dict[str, Any]]
    dimension_data: dict[str, Any] = Field(default_factory=dict)
    agent_outputs: dict[str, Any] = Field(default_factory=dict)
    request_context: dict[str, Any] = Field(default_factory=dict)


def normalize_topic1_remote_result(payload: dict[str, Any]) -> dict[str, Any]:
    return Topic1MiningResult.model_validate(payload).model_dump()
