from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.adapters.benchmark.topic1_value_qa import _resolve_project_root
from app.core.config import get_settings

DEFAULT_TOPIC = "中秋节"
KEYWORDS_RELATIVE_PATH = Path("configs") / "value_qa_keywords_5001.yaml"
BUNDLED_KEYWORDS_PATH = Path(__file__).resolve().parent.parent / "data" / "value_qa_keywords_5001.yaml"


def load_topic1_value_qa_topics(
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Load the 5001-used topic catalog.

    Prefer Project_1 configs/value_qa_keywords_5001.yaml, then the platform
    bundled copy. Never fall back to the legacy 435-word yaml.
    """
    root = project_root
    if root is None:
        settings = get_settings()
        root = _resolve_project_root(settings.topic1_value_qa_project_root)

    candidates = [Path(root) / KEYWORDS_RELATIVE_PATH, BUNDLED_KEYWORDS_PATH]
    for yaml_path in candidates:
        payload = _try_load_keywords(yaml_path)
        if payload is not None:
            return payload
    return _unavailable_payload()


def _try_load_keywords(yaml_path: Path) -> dict[str, Any] | None:
    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return _normalize_keywords_payload(raw, source="keywords_5001")
    except ValueError:
        return None


def _unavailable_payload() -> dict[str, Any]:
    return {
        "version": "unavailable",
        "topic_count": 0,
        "default_topic": "",
        "groups": [],
        "topics": [],
        "source": "unavailable",
    }


def _normalize_keywords_payload(raw: dict[str, Any], *, source: str) -> dict[str, Any]:
    keywords = raw.get("keywords")
    if not isinstance(keywords, dict) or not keywords:
        raise ValueError("keywords missing")

    primary_dimensions = raw.get("primary_dimensions")
    secondary_to_primary: dict[str, str] = {}
    if isinstance(primary_dimensions, dict):
        for primary, secondaries in primary_dimensions.items():
            if not isinstance(secondaries, list):
                continue
            for secondary in secondaries:
                if isinstance(secondary, str) and secondary.strip():
                    secondary_to_primary[secondary.strip()] = str(primary).strip()

    groups: list[dict[str, Any]] = []
    flat: list[str] = []
    seen: set[str] = set()

    for dimension, scenes in keywords.items():
        if not isinstance(dimension, str) or not dimension.strip():
            continue
        if not isinstance(scenes, dict):
            continue
        dim_topics: list[str] = []
        for topic_list in scenes.values():
            if not isinstance(topic_list, list):
                continue
            for item in topic_list:
                topic = str(item).strip()
                if not topic or topic in seen:
                    continue
                seen.add(topic)
                dim_topics.append(topic)
                flat.append(topic)
        if dim_topics:
            groups.append(
                {
                    "dimension": dimension.strip(),
                    "primary_dimension": secondary_to_primary.get(dimension.strip(), ""),
                    "topics": dim_topics,
                }
            )

    if not flat:
        raise ValueError("no topics")

    default_topic = DEFAULT_TOPIC if DEFAULT_TOPIC in seen else flat[0]
    version = raw.get("version")
    return {
        "version": str(version).strip()
        if isinstance(version, str) and version.strip()
        else "unknown",
        "topic_count": len(flat),
        "default_topic": default_topic,
        "groups": groups,
        "topics": flat,
        "source": source,
    }
