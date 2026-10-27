from app.adapters.topic1.mining_pipeline import run_topic1_mining
from app.services.topic1_input_assembler import build_topic1_input_bundle


TOPIC1_ADAPTER_VERSION = "topic1-midroute-v1"


async def run_topic1_task(*, db, task_id: str, input_data: dict) -> dict:
    input_bundle = await build_topic1_input_bundle(db, input_data)
    input_texts = input_bundle["prepared_texts"]
    result = await run_topic1_mining(
        definition_type=input_data["definition_type"],
        input_texts=input_texts,
        confidence_threshold=0.2,
        input_sources=input_bundle.get("prepared_sources", []),
        input_data=input_data,
    )
    if not result.get("prepared_texts"):
        raise ValueError("PolicyTextExtractor: no usable input text")
    result["artifacts"] = {
        "input_snapshot": input_data,
        "prepared_texts": result.get("prepared_texts", []),
        "input_sources": input_bundle.get("input_sources", []),
        "matched_paths": result.get("matched_paths", []),
        "candidate_snapshot": result["candidate_indicators"],
        "dimension_data": result.get("dimension_data", {}),
        "agent_outputs": result.get("agent_outputs", {}),
        "request_context": result.get("request_context", {}),
    }
    result["adapter_version"] = TOPIC1_ADAPTER_VERSION
    return result
