from __future__ import annotations

from pathlib import Path
from typing import Any

LOCAL_CORPUS = "local_corpus"
ONLINE_BAIKE = "online_baike"


def resolve_topic1_retrieval(
    *,
    project_root: Path,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Fill retrieval_mode when omitted; leave explicit local/online unchanged."""
    resolved = dict(parameters)
    mode = _explicit_retrieval_mode(resolved.get("retrieval_mode"))
    if mode in {LOCAL_CORPUS, ONLINE_BAIKE}:
        return resolved

    topic = resolved.get("topic")
    topic_text = topic.strip() if isinstance(topic, str) else ""
    if _local_corpus_exists(project_root, topic_text):
        resolved["retrieval_mode"] = LOCAL_CORPUS
        resolved["corpus_jsonl"] = f"data/corpus/baidu/{topic_text}.jsonl"
    else:
        resolved["retrieval_mode"] = ONLINE_BAIKE
        resolved.pop("corpus_jsonl", None)
    return resolved


def _explicit_retrieval_mode(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    mode = value.strip()
    return mode or None


def _local_corpus_exists(project_root: Path, topic: str) -> bool:
    if not topic or Path(topic).name != topic:
        return False
    candidate = project_root / "data" / "corpus" / "baidu" / f"{topic}.jsonl"
    try:
        return candidate.is_file() and candidate.stat().st_size > 0
    except OSError:
        return False
