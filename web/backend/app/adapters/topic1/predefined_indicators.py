"""预定三级指标明细（与定义模块「输入语料（价值）」前端种子一致）。"""

from app.adapters.topic1.predefined_dimensions import (
    export_dimension_paths,
    normalize_level1,
    normalize_level2,
)

# culture = 文化忠实度 / 伦理合规度；scene = 语义稀缺度 / 任务关联度
# definition_type=value 时返回全部，供输入语料（价值）挖掘使用
_INDICATOR_META: dict[str, dict] = {
    "文化实体真实性": {
        "definition": "评估训练语料中人物、地名、器物等文化实体是否真实可核验。",
        "formula": "X = A/B；A=实体可核验样本数；B=涉及文化实体的样本总数",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "文化符号准确性": {
        "definition": "评估文化符号、图腾、节庆意象等表达是否准确、完整。",
        "formula": "X = A/B；A=符号表达准确样本数；B=涉及文化符号的样本总数",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "语料本源性": {
        "definition": "评估语料是否来源于对应文化语境，避免移花接木或失真转述。",
        "formula": "S = 1 − 篡改/错置率",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "行为礼仪规范性": {
        "definition": "评估样本对礼仪、称呼与交往规范的表达是否符合对应文化习惯。",
        "formula": "X = A/B；A=礼仪规范符合样本数；B=涉及行为礼仪的样本总数",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "伦理关系合理性": {
        "definition": "评估家庭、社群等伦理关系叙述是否合理，避免错位或冒犯。",
        "formula": "X = A/B；A=伦理关系合理样本数；B=涉及伦理关系的样本总数",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "民俗禁忌规避度": {
        "definition": "评估语料是否规避民俗禁忌与不当戏谑表达。",
        "formula": "E = 1 − N禁忌冒犯样本数/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "主流价值一致性": {
        "definition": "评估样本是否与对应文化主流价值叙事保持一致。",
        "formula": "X = A/B；A=主流价值一致样本数；B=涉及价值表达的样本总数",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "历史客观性": {
        "definition": "评估历史叙述是否客观可核，避免歪曲与虚构。",
        "formula": "S = N客观/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "文明逻辑性": {
        "definition": "评估文明演进、制度与观念表达是否自洽、合乎逻辑。",
        "formula": "S = N合理/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "群体偏见抑制度": {
        "definition": "评估语料对群体刻板印象与偏见表达的抑制程度。",
        "formula": "E = 1 − N偏见样本数/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "机会均等表达度": {
        "definition": "评估不同群体在机会、能力与贡献方面的表达是否均等。",
        "formula": "X = A/B；A=机会均等差叙样本数；B=涉及群体机会的样本总数",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "弱势群体关怀度": {
        "definition": "评估对弱势群体的表述是否体现尊重与必要关怀。",
        "formula": "E = 1 − N歧视样本数/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "负面引导安全性": {
        "definition": "评估语料是否避免不当负面引导与危险示范。",
        "formula": "E = 1 − N危险引导样本数/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "公共利益保护度": {
        "definition": "评估表达是否维护公共利益与公共秩序底线。",
        "formula": "X = A/B；A=公共利益保护充分样本数；B=涉及公共议题的样本总数",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "暴力极端过滤度": {
        "definition": "评估对暴力、极端内容的过滤与边界提示是否充分。",
        "formula": "E = 1 − N暴力极端样本数/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "个人信息脱敏度": {
        "definition": "评估个人身份信息是否经过必要脱敏处理。",
        "formula": "E = N脱敏充分/N涉个信",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "敏感信息保护度": {
        "definition": "评估敏感信息（健康、信仰、行踪等）保护是否到位。",
        "formula": "E = N保护充分/N涉敏",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "过度采集控制度": {
        "definition": "评估是否避免非必要的个人信息过度采集与暴露。",
        "formula": "E = 1 − N过度采集样本数/N总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "长尾知识覆盖": {
        "definition": "评估低频但有价值的长尾知识在语料中的覆盖程度。",
        "formula": "X = A稀有/B总",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "专业逻辑深度": {
        "definition": "评估专业领域表达是否具备足够推理与逻辑深度。",
        "formula": "X = ∑逻辑节点/B抽样",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "模型认知缺口度": {
        "definition": "结合参考模型识别当前语料相对模型能力的认知缺口。",
        "formula": "X = 模型错误/分歧率",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "知识补全贡献度": {
        "definition": "评估样本对知识补全与覆盖扩展的贡献程度。",
        "formula": "X = A补全贡献/B抽样",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "能力增益度": {
        "definition": "评估样本对模型能力增益的潜在贡献。",
        "formula": "X = Δ能力指标",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "指令适配度": {
        "definition": "评估语料指令形态与目标训练任务的适配程度。",
        "formula": "X = A适配/B抽样",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "格式规范性": {
        "definition": "评估问答/指令格式是否规范、稳定、可解析。",
        "formula": "X = A格式规范/B抽样",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "约束明确性": {
        "definition": "评估任务约束、输出边界是否清晰可执行。",
        "formula": "X = A约束明确/B抽样",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "行业知识匹配度": {
        "definition": "评估语料与目标行业知识体系的匹配程度。",
        "formula": "X = A匹配实体/B全实体",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "语义关系覆盖度": {
        "definition": "评估问题、证据与答案之间语义关系的覆盖完整性。",
        "formula": "X = A关系覆盖/B抽样",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "端到端任务增益": {
        "definition": "评估样本对端到端任务表现提升的贡献潜力。",
        "formula": "X = Δ任务指标",
        "source": "课题一多维度综合评价三级指标总表",
    },
    "错误抑制度": {
        "definition": "评估样本对常见错误模式的抑制与纠偏作用。",
        "formula": "X = 1 − 错误率增量",
        "source": "课题一多维度综合评价三级指标总表",
    },
}

_LEVEL1_TO_DEFINITION_TYPE = {
    "文化忠实度": "culture",
    "伦理合规度": "culture",
    "语义稀缺度": "scene",
    "任务关联度": "scene",
}


def _build_predefined_indicators() -> list[dict]:
    rows: list[dict] = []
    for level1, level2, level3 in export_dimension_paths():
        meta = _INDICATOR_META.get(
            level3,
            {
                "definition": f"评估语料在「{level3}」方面的表现。",
                "formula": "X = A/B",
                "source": "课题一多维度综合评价三级指标总表",
            },
        )
        rows.append(
            {
                "name": f"{level3}指标",
                "definition_type": _LEVEL1_TO_DEFINITION_TYPE[level1],
                "level1": level1,
                "level2": level2,
                "level3": level3,
                "definition": meta["definition"],
                "formula": meta["formula"],
                "source": meta["source"],
            }
        )
    return rows


PREDEFINED_INDICATORS = _build_predefined_indicators()


def get_predefined_indicators(definition_type: str | None = None) -> list[dict]:
    if not definition_type or definition_type == "value":
        # 输入语料（价值）tab 使用完整三级表
        return list(PREDEFINED_INDICATORS)
    return [
        item
        for item in PREDEFINED_INDICATORS
        if item["definition_type"] == definition_type
    ]


def get_indicator_path_map(
    definition_type: str | None = None,
) -> dict[tuple[str, str, str], dict]:
    return {
        (item["level1"], item["level2"], item["level3"]): item
        for item in get_predefined_indicators(definition_type)
    }


def get_indicators_by_level1(
    level1: str, definition_type: str | None = None
) -> list[dict]:
    normalized = normalize_level1(level1)
    return [
        item
        for item in get_predefined_indicators(definition_type)
        if item["level1"] == normalized
    ]


def normalize_indicator_levels(item: dict) -> dict:
    """归一旧口径层级命名，便于挂到预定树上。"""
    normalized = dict(item)
    normalized["level1"] = normalize_level1(str(normalized.get("level1") or ""))
    normalized["level2"] = normalize_level2(str(normalized.get("level2") or ""))
    return normalized
