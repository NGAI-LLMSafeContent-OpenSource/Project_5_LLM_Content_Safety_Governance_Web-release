import re

from app.adapters.topic1.predefined_indicators import get_predefined_indicators


def _clip(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _tokenize_keywords(text: str) -> set[str]:
    tokens = set()
    for chunk in re.split(r"[，。；：、,.!?（）()\[\]{}\s\-_\/]+", text or ""):
        part = chunk.strip()
        if len(part) >= 2 and not part.isdigit():
            tokens.add(part)
    return tokens


def _indicator_keywords(indicator: dict) -> set[str]:
    seeds = [
        indicator.get("name", ""),
        indicator.get("level1", ""),
        indicator.get("level2", ""),
        indicator.get("level3", ""),
        indicator.get("definition", ""),
        indicator.get("source", ""),
    ]
    keywords = set()
    for seed in seeds:
        keywords.update(_tokenize_keywords(seed))
    return {item for item in keywords if len(item) <= 20}


def _build_evidence_snippets(text: str, hits: list[str]) -> list[str]:
    snippets = []
    for hit in hits[:3]:
        idx = text.find(hit)
        if idx < 0:
            continue
        start = max(0, idx - 12)
        end = min(len(text), idx + len(hit) + 18)
        snippets.append(text[start:end])
    return snippets


def _resolve_threshold(input_texts: list[str], base_threshold: float) -> float:
    merged = "\n".join([text.strip() for text in input_texts if text and text.strip()])
    text_len = len(merged)
    bonus = 0.0
    if text_len < 80:
        bonus = -0.04
    elif text_len < 180:
        bonus = -0.02
    elif text_len > 800:
        bonus = 0.01

    return round(_clip(base_threshold + bonus, 0.18, 0.55), 3)


def match_indicator_paths(
    input_texts: list[str],
    confidence_threshold: float,
    definition_type: str = "value",
    top_k: int = 12,
) -> dict:
    merged = "\n".join([text.strip() for text in input_texts if text and text.strip()])
    if len(merged) < 10:
        return {
            "confidence_threshold": confidence_threshold,
            "max_confidence": 0.0,
            "matched_paths": [],
            "matched_level1": [],
            "matched_level2": [],
            "uncovered": True,
            "reason": "empty_or_too_short_input",
        }

    normalized_text = _normalize_text(merged)
    scored = []

    for indicator in get_predefined_indicators(definition_type):
        keywords = _indicator_keywords(indicator)
        hits = [word for word in keywords if word.lower() in normalized_text]

        weighted_bonus = 0.0
        if indicator["level1"].lower() in normalized_text:
            weighted_bonus += 0.06
        if indicator["level2"].lower() in normalized_text:
            weighted_bonus += 0.08
        if indicator["level3"].lower() in normalized_text:
            weighted_bonus += 0.18
        if indicator["name"].lower() in normalized_text:
            weighted_bonus += 0.12

        coverage = len(hits) / max(3, min(10, len(keywords)))
        confidence = round(min(1.0, coverage + weighted_bonus), 4)
        if confidence > 0:
            scored.append(
                {
                    **indicator,
                    "confidence": confidence,
                    "hits": hits,
                    "indicator_name": indicator["name"],
                    "evidence_hits": hits[:8],
                    "matched_keywords": hits[:8],
                    "evidence_snippets": _build_evidence_snippets(merged, hits),
                }
            )

    scored.sort(key=lambda item: item["confidence"], reverse=True)
    max_confidence = scored[0]["confidence"] if scored else 0.0
    effective_threshold = _resolve_threshold(input_texts, confidence_threshold)
    top_matches = [
        item for item in scored if item["confidence"] >= effective_threshold
    ][:top_k]

    if (
        not top_matches
        and scored
        and max_confidence >= max(0.18, effective_threshold - 0.05)
    ):
        top_matches = scored[: min(3, top_k)]

    uncovered = (not top_matches) or (max_confidence < confidence_threshold)

    return {
        "confidence_threshold": confidence_threshold,
        "effective_threshold": effective_threshold,
        "max_confidence": max_confidence,
        "matched_paths": top_matches,
        "matched_level1": sorted({item["level1"] for item in top_matches}),
        "matched_level2": sorted({item["level2"] for item in top_matches}),
        "uncovered": uncovered,
        "reason": "low_confidence_or_empty" if uncovered else "covered",
        "top_candidates": scored[:5],
    }
