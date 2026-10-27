"""Shared OpenAI-compatible chat text helpers for the governance LLM layer.

The assistant interpreter and the suggestion ranker both read an
OpenAI-compatible chat completion: they need the assistant text out of the
completion envelope and the first JSON object out of a model reply. Keeping one
implementation here avoids the two copies drifting apart (#65 review finding).
"""

from __future__ import annotations

import re
from typing import Any, Mapping

_FENCED_BLOCK = re.compile(r"^\s*```(?:json|JSON)?\s*(.*?)\s*```\s*$", re.DOTALL)


def extract_json_object(text: str) -> str | None:
    """Return the first balanced JSON object from model output, tolerating
    markdown code fences and surrounding prose."""
    text = (text or "").strip()
    fenced = _FENCED_BLOCK.match(text)
    if fenced:
        text = fenced.group(1).strip()

    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_chat_content(data: Mapping[str, Any]) -> str:
    """Return ``choices[0].message.content`` safely, or "" when absent.

    A provider reply may omit any level of the envelope; every level is checked
    so a malformed completion degrades to an empty string instead of raising.
    """

    if not isinstance(data, Mapping):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    message = first.get("message")
    if not isinstance(message, Mapping):
        return ""
    content = message.get("content")
    return "" if content is None else str(content)
