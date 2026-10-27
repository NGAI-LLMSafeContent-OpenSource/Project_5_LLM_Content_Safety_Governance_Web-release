from __future__ import annotations

from app.schemas.benchmark import (
    BenchmarkRiskCategory,
    BenchmarkTopic3RiskTaxonomyResponse,
)

TOPIC3_RISK_TAXONOMY_SCHEMA = "17x60"
TOPIC3_RISK_TAXONOMY_VERSION = "topic3-risk-17x60-v1"
TOPIC3_RISK_TAXONOMY_SOURCE = "benchmark_topic3_risk"

TOPIC3_RISK_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("C01", "煽动颠覆国家政权、推翻社会主义制度"),
    ("C02", "危害国家安全和利益、损害国家形象"),
    ("C03", "煽动分裂国家、破坏国家统一和社会稳定"),
    ("C04", "宣扬恐怖主义、极端主义"),
    ("C05", "宣扬民族仇恨"),
    ("C06", "宣扬暴力、淫秽色情"),
    ("C07", "传播虚假有害信息"),
    ("C08", "歧视性内容"),
    ("C09", "商业违法违规"),
    ("C10", "侵犯他人权益"),
    ("C11", "无法满足特定服务类型的安全需求"),
    ("C12", "经济损失高风险的活动"),
    ("C13", "未成年人安全"),
    ("C14", "从事欺诈、虐待或掠夺性行为"),
    ("C15", "不正确民族叙事"),
    ("C16", "民族情感商业化、功利化、娱乐化"),
    ("C17", "价值导向偏差"),
)


def get_topic3_risk_taxonomy() -> BenchmarkTopic3RiskTaxonomyResponse:
    return BenchmarkTopic3RiskTaxonomyResponse(
        schema=TOPIC3_RISK_TAXONOMY_SCHEMA,
        version=TOPIC3_RISK_TAXONOMY_VERSION,
        source=TOPIC3_RISK_TAXONOMY_SOURCE,
        categories=[
            BenchmarkRiskCategory(code=code, name=name)
            for code, name in TOPIC3_RISK_CATEGORIES
        ],
    )
