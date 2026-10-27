"""预定一/二/三级指标体系（与课题一「输入语料价值」现行总表对齐）。"""

PREDEFINED_DIMENSIONS = {
    "文化忠实度": {
        "description": "数据集对特定文化的真实表征能力，不含刻板印象、歪曲、遗漏或外来文化植入。",
        "sub_dimensions": {
            "文化元素符合度": [
                "文化实体真实性",
                "文化符号准确性",
                "语料本源性",
            ],
            "行为与社会规范符合度": [
                "行为礼仪规范性",
                "伦理关系合理性",
                "民俗禁忌规避度",
            ],
            "价值观忠实度": [
                "主流价值一致性",
                "历史客观性",
                "文明逻辑性",
            ],
        },
    },
    "伦理合规度": {
        "description": "评判数据及应用在公平、伤害风险与隐私等伦理框架下的合规水平（原「伦理敏感度」）。",
        "sub_dimensions": {
            "公平合规度": [
                "群体偏见抑制度",
                "机会均等表达度",
                "弱势群体关怀度",
            ],
            "伤害风险合规度": [
                "负面引导安全性",
                "公共利益保护度",
                "暴力极端过滤度",
            ],
            "隐私合规度": [
                "个人信息脱敏度",
                "敏感信息保护度",
                "过度采集控制度",
            ],
        },
    },
    "语义稀缺度": {
        "description": "在既定语义空间中，数据相对已有语义集合的低覆盖性、不可替代性与认知缺口价值。",
        "sub_dimensions": {
            "基于数据分布的语义稀缺度": [
                "长尾知识覆盖",
                "专业逻辑深度",
            ],
            "基于参考模型的语义稀缺度": [
                "模型认知缺口度",
                "知识补全贡献度",
                "能力增益度",
            ],
        },
    },
    "任务关联度": {
        "description": "数据分布特征与特定下游任务需求之间的对齐程度。",
        "sub_dimensions": {
            "指令形态适配度": [
                "指令适配度",
                "格式规范性",
                "约束明确性",
            ],
            "语义匹配度": [
                "行业知识匹配度",
                "语义关系覆盖度",
            ],
            "任务性能提升度": [
                "端到端任务增益",
                "错误抑制度",
            ],
        },
    },
}

# 课题一旧口径 → 现行口径（远端挖掘结果归一）
LEVEL1_ALIASES = {
    "伦理敏感度": "伦理合规度",
    "文化忠诚度": "文化忠实度",
}

LEVEL2_ALIASES = {
    "行为/社会规范符合度": "行为与社会规范符合度",
    "公平性敏感度": "公平合规度",
    "伤害风险敏感度": "伤害风险合规度",
    "隐私敏感度": "隐私合规度",
    "任务性能提升": "任务性能提升度",
}


def normalize_level1(level1: str) -> str:
    text = (level1 or "").strip()
    return LEVEL1_ALIASES.get(text, text)


def normalize_level2(level2: str) -> str:
    text = (level2 or "").strip()
    return LEVEL2_ALIASES.get(text, text)


def get_predefined_dimensions() -> dict:
    return PREDEFINED_DIMENSIONS


def export_dimension_paths() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for level1, level1_data in PREDEFINED_DIMENSIONS.items():
        for level2, level3_items in level1_data["sub_dimensions"].items():
            for level3 in level3_items:
                rows.append((level1, level2, level3))
    return rows
