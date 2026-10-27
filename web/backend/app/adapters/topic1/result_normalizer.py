def normalize_topic1_result(
    *,
    prepared_texts: list[str],
    matched_paths: list[dict],
    candidates: list[dict],
    extra_stats: dict | None = None,
) -> dict:
    stats = {
        "input_text_count": len(prepared_texts),
        "matched_path_count": len(matched_paths),
        "candidate_count": len(candidates),
    }
    if extra_stats:
        stats.update(extra_stats)

    return {
        "logs": [
            {
                "agent_name": "PolicyTextExtractor",
                "status": "completed",
                "message": f"清洗得到 {len(prepared_texts)} 段可挖掘文本",
            },
            {
                "agent_name": "DimensionMatcher",
                "status": "completed",
                "message": f"匹配到 {len(matched_paths)} 条路径",
            },
            {
                "agent_name": "IndicatorGenerator",
                "status": "completed",
                "message": f"生成 {len(candidates)} 个候选指标",
            },
        ],
        "stats": stats,
        "candidate_indicators": candidates,
    }
