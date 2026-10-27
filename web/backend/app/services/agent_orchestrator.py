def build_candidate_indicators(
    *,
    definition_type: str,
    text: str,
    level1: str | None,
    level2: str | None,
) -> list[dict]:
    base_level1 = level1 or "价值指标"
    base_level2 = level2 or "综合治理"
    candidates: list[dict] = []
    keyword_map = {
        "文化": "文化表达覆盖度",
        "安全": "内容安全约束度",
        "治理": "治理流程完备度",
        "人工智能": "人工智能适配度",
        "数据": "数据来源规范度",
    }

    for keyword, name in keyword_map.items():
        if keyword in text:
            candidates.append(
                {
                    "definition_type": definition_type,
                    "name": name,
                    "level1": base_level1,
                    "level2": base_level2,
                    "level3": name,
                    "definition": f"用于衡量输入材料中“{keyword}”相关要求的覆盖与可执行程度。",
                    "source": "第一期规则化 Agent",
                    "evidence_text": text[:160],
                    "confidence": 0.78,
                }
            )

    if not candidates:
        candidates.append(
            {
                "definition_type": definition_type,
                "name": "综合价值识别度",
                "level1": base_level1,
                "level2": base_level2,
                "level3": "综合价值识别度",
                "definition": "用于衡量输入材料中可抽取治理指标的整体充分程度。",
                "source": "第一期规则化 Agent",
                "evidence_text": text[:160],
                "confidence": 0.6,
            }
        )

    return candidates
