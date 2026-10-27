def _build_rationale(item: dict) -> str:
    keywords = item.get("matched_keywords", [])[:3]
    snippets = item.get("evidence_snippets", [])[:2]
    parts = []

    if keywords:
        parts.append(f"Matched keywords: {', '.join(keywords)}.")
    if snippets:
        parts.append(f"Evidence snippets: {' '.join(snippets)}")

    return " ".join(parts)


def generate_candidate_indicators(
    definition_type: str, matched_paths: list[dict], text: str
) -> dict:
    from app.adapters.topic1.predefined_indicators import normalize_indicator_levels

    candidates = []
    seen = set()
    dropped_duplicate_count = 0

    for raw in matched_paths:
        item = normalize_indicator_levels(raw)
        key = (item["level1"], item["level2"], item["level3"])
        if key in seen:
            dropped_duplicate_count += 1
            continue
        seen.add(key)
        candidates.append(
            {
                "definition_type": definition_type,
                "name": item["name"],
                "level1": item["level1"],
                "level2": item["level2"],
                "level3": item["level3"],
                "definition": item["definition"],
                "formula": item.get("formula", ""),
                "source": item["source"],
                "rationale": _build_rationale(item),
                "evidence_text": "\n".join(item.get("evidence_snippets", []))
                or text[:200],
                "confidence": item.get("confidence", 0.0),
            }
        )

    return {
        "candidate_indicators": candidates,
        "stats": {
            "candidate_count": len(candidates),
            "dropped_duplicate_count": dropped_duplicate_count,
        },
    }
