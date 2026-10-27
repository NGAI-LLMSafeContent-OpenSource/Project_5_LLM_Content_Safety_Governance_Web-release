"""Governance assistant interpretation layer.

A single interface turns a user prompt into a validated GovernanceIntent for the
active domain. Qwen and DeepSeek share one OpenAI-compatible client so both
providers return the same structured intent contract. The capability whitelist is
enforced later by the orchestrator; this layer only parses the model JSON.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from app.core.config import get_settings
from app.schemas.governance import RISK_RESCAN_MAX_SAMPLES, GovernanceIntent
from app.services.governance_capabilities import capabilities_for_domain, capability_prompt_block
from app.services.governance_llm_text import extract_chat_content, extract_json_object
from app.services.governance_system_record_service import (
    STATUS_IMPORTED,
    STATUS_PENDING,
)


@dataclass
class AssistantInterpretation:
    provider: str
    model: str
    latency_ms: int
    parse_status: str
    intent: GovernanceIntent | None = None
    raw: dict[str, Any] | None = None
    error: str | None = None


class AssistantInterpreter:
    name = "abstract"

    async def interpret(
        self, domain: str, prompt: str
    ) -> AssistantInterpretation:
        raise NotImplementedError


class DeepSeekConfigurationError(ValueError):
    """Raised when DeepSeek is selected without a usable API credential."""


@dataclass(frozen=True)
class ChatProviderConfig:
    """Resolved OpenAI-compatible chat settings shared by the assistant
    interpreter and the suggestion ranker.

    ``chat_provider_config`` only performs the shared field reads. Each caller
    keeps its own policy for a missing DeepSeek credential (the interpreter
    raises, the ranker opts out) and reads its own timeout, so neither path
    changes behaviour (#65).
    """

    provider: str
    name: str
    base_url: str
    model: str
    api_key: SecretStr | None = None


def chat_provider_config() -> ChatProviderConfig | None:
    """Resolve the shared chat provider fields; None for stub/unknown providers.

    Only the fields read by both the interpreter and the ranker are resolved
    here. ``timeout`` is deliberately excluded: the interpreter never read it at
    construction time, so reading it here would add a settings access that did
    not exist before.
    """

    settings = get_settings()
    provider = settings.governance_assistant_provider
    if provider == "qwen":
        return ChatProviderConfig(
            provider="qwen",
            name="qwen",
            base_url=settings.governance_assistant_qwen_base_url,
            model=settings.governance_assistant_qwen_model,
        )
    if provider == "deepseek":
        return ChatProviderConfig(
            provider="deepseek",
            name="deepseek",
            base_url=settings.governance_assistant_deepseek_base_url,
            model=settings.governance_assistant_deepseek_model,
            api_key=settings.governance_assistant_deepseek_api_key,
        )
    return None


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced JSON object from model output, tolerating
    markdown code fences and surrounding prose."""
    return extract_json_object(text)


# Input-corpus wording is a product boundary in the output domain. The live
# model otherwise treats 「查看风险语料构成」 as an underspecified system-record
# query and asks the user to clarify scope (rehearsal O0).
_OUTPUT_INPUT_CORPUS_MARKERS = (
    "价值语料",
    "价值问题",
    "语料构成",
    "输入语料",
    "风险语料",
    "风险样本",
    "dynbench",
)
_OUTPUT_INPUT_CORPUS_BOUNDARY = (
    "当前为输出内容治理，无法执行输入语料能力；"
    "可改为发送「查看最近的风险安全评测系统预跑记录」"
    "或「查看最近的文化多样性系统预跑记录」。"
)


def _output_input_corpus_boundary(domain: str, prompt: str) -> GovernanceIntent | None:
    if domain != "output":
        return None
    lowered = prompt.lower()
    if any(marker in lowered for marker in _OUTPUT_INPUT_CORPUS_MARKERS):
        return GovernanceIntent(kind="boundary", message=_OUTPUT_INPUT_CORPUS_BOUNDARY)
    return None


# Terms that name the evaluated asset in the output domain. The guard and the
# interpreter prompt share this vocabulary so a new domain term cannot be
# recognized by one and missed by the other.
ASSET_SCOPE_TERMS = (
    "课题三数据",
    "课题三",
    "资产",
    "数据集",
    "benchmark",
    "bench",
    "基准",
    "样本集",
)
ASSET_VERSION_PROMPT_FORMS = ("资产", "数据集", "Benchmark", "课题三", "课题三数据")

# A bare v7 is genuinely ambiguous: it can mean the evaluated asset series
# version (asset_version, e.g. v7) or the evaluator model version
# (Qwen3.5-9B-V7). Never guess a scope from it, even if the model does.
_BARE_ASSET_VERSION = re.compile(
    r"(?<![0-9a-z._-])v(\d+)(?:[._-][0-9a-z]+)*(?![0-9a-z])", re.IGNORECASE
)
_ASSET_SCOPE_PATTERN = "|".join(re.escape(term) for term in ASSET_SCOPE_TERMS)
_ASSET_VERSION_MARKERS = re.compile(
    rf"({_ASSET_SCOPE_PATTERN})\s*(?:的)?\s*(版本)?\s*[:：=]?\s*v7"
    r"|v7\s*(版本)?\s*(的)?\s*(资产|数据集|benchmark|bench|基准|样本集)"
    r"|asset_version\s*[:：=]\s*v7",
    re.IGNORECASE,
)
_EVALUATOR_VERSION_MARKERS = re.compile(
    r"(qwen|模型|评估器|识别器|分类器)[^。；;\n]{0,12}?v7"
    r"|v7[^。；;\n]{0,12}?(模型|评估器|识别器|分类器)",
    re.IGNORECASE,
)
_ASSET_VERSION_CLARIFICATION = (
    "你提到的「V7」是指评测对象资产版本（如数据集 v7），还是评估器模型版本"
    "（如 Qwen3.5-9B-V7）？请说明后再继续；省略时系统默认按当前资产版本处理。"
)
_ASSET_VERSION_PROMPT_RULE = (
    "版本语义："
    + "、".join(f"「{term} v7」" for term in ASSET_VERSION_PROMPT_FORMS)
    + "指评测对象资产版本，映射为 asset_version；"
    "「Qwen V7」「模型 V7」「评估器 V7」指评估器版本，不是资产版本。"
)


def ambiguous_asset_version_message(domain: str, prompt: str) -> str | None:
    """Return a clarification message for a bare v7 in the output domain.

    Explicit asset wording (资产 v7 / 数据集 v7) and evaluator wording
    (Qwen V7 / 模型 V7) stay executable. Only an unqualified v7 is blocked.
    """
    if domain != "output":
        return None
    if not any(match.group(1) == "7" for match in _BARE_ASSET_VERSION.finditer(prompt)):
        return None
    if _ASSET_VERSION_MARKERS.search(prompt):
        return None
    if _EVALUATOR_VERSION_MARKERS.search(prompt):
        return None
    return _ASSET_VERSION_CLARIFICATION


def ambiguous_asset_version_clarification(
    domain: str, prompt: str, intent: GovernanceIntent | None
) -> str | None:
    """Apply the bare-v7 guard only to executable interpreted turns."""
    if intent is None or intent.kind != "execute":
        return None
    return ambiguous_asset_version_message(domain, prompt)


def build_assistant_system_prompt(domain: str) -> str:
    """Instructions for the live interpreter.

    Optional value-qa filters mean browse the preferred asset. A missing group
    id must not become a clarification, and must not select group detail.
    """

    return (
        "你是内容安全治理平台的治理助手，只负责理解用户意图并返回 JSON，"
        "不生成任何治理结论。当前业务域可用的治理能力如下：\n"
        + capability_prompt_block(domain)
        + "\n\n请仅返回以下结构之一的 JSON（不要输出 Markdown、解释或多余文字）：\n"
        '{"kind":"execute","capability":"<能力key>","parameters":{...}}\n'
        '{"kind":"clarify","message":"<需要用户补充的信息>"}\n'
        '{"kind":"boundary","message":"<不支持该请求的原因与可行替代建议>"}\n'
        "规则：能力只能选上面列出的；parameters 只能使用对应能力列出的字段名与取值，"
        "禁止自造字段名；跨域、虚构或无法映射到任一能力时返回 clarify 或 boundary。"
        "可选参数未在用户请求中出现时省略该字段，不要为此返回 clarify。"
        + _ASSET_VERSION_PROMPT_RULE
        + "用户只说「V7」而没有说明是资产还是评估器时，返回 clarify 询问；"
        "省略 asset_version 时系统按当前资产版本处理，不要自行推断历史版本。"
        "value_qa_search 的关键词、主题和价值维度都可省略；省略表示浏览当前优选资产的全部价值问题组，"
        "并在结果中对照高、中、低三档回答。只有用户给出价值问题组 ID 时才选择 value_qa_group_detail。"
    )


def _parse_intent(content: str) -> tuple[GovernanceIntent | None, str, dict | None]:
    fragment = _extract_json_object(content)
    if fragment is None:
        text = (content or "").strip()
        return None, ("empty" if not text else "json_invalid"), None
    try:
        data = json.loads(fragment)
    except json.JSONDecodeError:
        return None, "json_invalid", None
    if not isinstance(data, dict):
        return None, "schema_violation", None
    try:
        intent = GovernanceIntent.model_validate(data)
    except ValidationError:
        return None, "schema_violation", data
    return intent, "ok", data


class OpenAiCompatibleInterpreter(AssistantInterpreter):
    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: SecretStr | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def interpret(self, domain: str, prompt: str) -> AssistantInterpretation:
        boundary = _output_input_corpus_boundary(domain, prompt)
        if boundary is not None:
            return AssistantInterpretation(
                provider=self.name,
                model=self.model,
                latency_ms=0,
                parse_status="ok",
                intent=boundary,
                raw=boundary.model_dump(),
            )

        settings = get_settings()
        started = time.monotonic()
        system_prompt = build_assistant_system_prompt(domain)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        headers = {"Content-Type": "application/json"}
        if self.api_key is not None:
            headers["Authorization"] = f"Bearer {self.api_key.get_secret_value()}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(
                timeout=settings.governance_assistant_timeout_seconds, trust_env=False
            ) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
            content = extract_chat_content(data)
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.monotonic() - started) * 1000)
            return AssistantInterpretation(
                provider=self.name,
                model=self.model,
                latency_ms=elapsed,
                parse_status="failure",
                error=_safe_error(exc),
            )

        elapsed = int((time.monotonic() - started) * 1000)
        intent, parse_status, raw = _parse_intent(content)
        return AssistantInterpretation(
            provider=self.name,
            model=self.model,
            latency_ms=elapsed,
            parse_status=parse_status,
            intent=intent,
            raw=raw,
        )


class StubInterpreter(AssistantInterpreter):
    """Deterministic dev/test seam; never makes a network call."""

    name = "stub"

    async def interpret(self, domain: str, prompt: str) -> AssistantInterpretation:
        started = time.monotonic()
        intent = self._intent_for(domain, prompt.lower())
        return AssistantInterpretation(
            provider=self.name,
            model="stub-governance-model",
            latency_ms=int((time.monotonic() - started) * 1000),
            parse_status="ok",
            intent=intent,
            raw=intent.model_dump(),
        )

    def _intent_for(self, domain: str, lowered: str) -> GovernanceIntent:
        capabilities = capabilities_for_domain(domain)
        if not capabilities:
            return GovernanceIntent(
                kind="boundary", message="当前业务域暂无可用的治理能力。"
            )
        if any(marker in lowered for marker in ("导出", "上传", "生成报告", "不存在的")):
            return GovernanceIntent(
                kind="boundary",
                message="当前治理能力不支持该请求，可检索价值问题组、浏览风险样本或查看语料构成。",
            )
        if domain == "output":
            return self._output_intent(lowered)
        if "课题一" in lowered and any(
            marker in lowered for marker in ("工具", "去噪", "去害", "稀缺", "数据选择")
        ):
            return GovernanceIntent(
                kind="execute",
                capability="topic1_corpus_tool_catalog",
                parameters={},
            )
        if _is_cbrne_prompt(lowered):
            return self._cbrne_intent(lowered)
        if _is_risk_prompt(lowered):
            return self._risk_intent(lowered)
        if any(marker in lowered for marker in ("检索", "搜索", "查找")):
            keyword = _extract_keyword(lowered)
            parameters = {"keyword": keyword} if keyword else {}
            return GovernanceIntent(
                kind="execute", capability="value_qa_search", parameters=parameters
            )
        group_id = _extract_group_id(lowered)
        if group_id or ("打开" in lowered and "组" in lowered):
            return GovernanceIntent(
                kind="execute",
                capability="value_qa_group_detail",
                parameters={"group_id": group_id or ""},
            )
        if "价值语料" in lowered or "语料构成" in lowered:
            return GovernanceIntent(
                kind="execute", capability=capabilities[0].key, parameters={}
            )
        return GovernanceIntent(
            kind="clarify",
            message="请补充要执行的治理动作，例如“检索价值问题组”“浏览风险样本”或“查看语料构成”。",
        )

    def _output_intent(self, lowered: str) -> GovernanceIntent:
        """Output-domain routing over the registered system-record types.

        Input-domain wording stays a boundary; cultural wording must reach the
        cultural capability instead of being coerced into a risk-safety query."""
        boundary = _output_input_corpus_boundary("output", lowered)
        if boundary is not None:
            return boundary
        cultural = _is_cultural_prompt(lowered)
        search_capability = (
            "cultural_system_record_search" if cultural else "risk_system_record_search"
        )
        detail_capability = (
            "cultural_system_record_detail" if cultural else "risk_system_record_detail"
        )
        if any(marker in lowered for marker in ("下一页", "加载更多", "再看", "继续浏览", "继续查看", "继续")):
            return GovernanceIntent(
                kind="execute",
                capability=search_capability,
                parameters={"continuation": True},
            )
        if any(marker in lowered for marker in ("详情", "打开")):
            record_id = _extract_record_id(lowered)
            if record_id:
                return GovernanceIntent(
                    kind="execute",
                    capability=detail_capability,
                    parameters={"record_id": record_id},
                )

        parameters: dict[str, Any] = {}
        source = _extract_source(lowered)
        if source:
            parameters["source"] = source
        status = _extract_status(lowered)
        if status:
            parameters["status"] = status
        if cultural:
            difficulty_level = _extract_difficulty_level(lowered)
            if difficulty_level:
                parameters["difficulty_level"] = difficulty_level
            ethnic_group = _extract_ethnic_group(lowered)
            if ethnic_group:
                parameters["ethnic_group"] = ethnic_group
        return GovernanceIntent(
            kind="execute",
            capability=search_capability,
            parameters=parameters,
        )

    def _cbrne_intent(self, lowered: str) -> GovernanceIntent:
        """Read-only CBRNE dataset capabilities; never rescan / Activation Probe."""
        if any(
            marker in lowered
            for marker in ("activation probe", "二次检测", "发起评测", "执行评测", "跑评测")
        ):
            return GovernanceIntent(
                kind="boundary",
                message=(
                    "CBRNE 异常数据查询是只读治理能力，不能从检索结果发起 Activation Probe "
                    "或其他评测执行。请改用资产发现、总览或摘要筛选。"
                ),
            )
        if any(marker in lowered for marker in ("全文", "完整文本", "原文", "prompt 全文")):
            sample_id = _extract_cbrne_sample_id(lowered) or "unknown"
            asset_id = _extract_cbrne_asset_id(lowered)
            parameters: dict[str, Any] = {"sample_id": sample_id}
            if asset_id:
                parameters["asset_id"] = asset_id
            return GovernanceIntent(
                kind="execute",
                capability="cbrne_dataset_full_text",
                parameters=parameters,
            )
        if any(
            marker in lowered
            for marker in ("下一页", "加载更多", "再看", "继续浏览", "继续查看", "继续")
        ):
            return GovernanceIntent(
                kind="execute",
                capability="cbrne_dataset_search",
                parameters={"continuation": True},
            )
        if any(
            marker in lowered
            for marker in ("发现", "有哪些", "可用资产", "登记了哪些", "资产列表")
        ):
            return GovernanceIntent(
                kind="execute", capability="cbrne_dataset_discover", parameters={}
            )
        if any(
            marker in lowered
            for marker in ("构成", "概览", "分布", "规模", "总览")
        ) and not any(
            marker in lowered for marker in ("筛选", "过滤", "查询样本", "样本摘要")
        ):
            parameters = {}
            asset_id = _extract_cbrne_asset_id(lowered)
            if asset_id:
                parameters["asset_id"] = asset_id
            return GovernanceIntent(
                kind="execute",
                capability="cbrne_dataset_overview",
                parameters=parameters,
            )
        parameters = _extract_cbrne_filters(lowered)
        return GovernanceIntent(
            kind="execute",
            capability="cbrne_dataset_search",
            parameters=parameters,
        )

    def _risk_intent(self, lowered: str) -> GovernanceIntent:
        if any(marker in lowered for marker in ("下一页", "加载更多", "再看", "继续浏览", "继续查看")):
            return GovernanceIntent(
                kind="execute",
                capability="risk_corpus_search",
                parameters={"continuation": True},
            )
        # DynBench400 input-eval wording now routes to the merged v2
        # risk_corpus_rescan capability (one execution mode, one contract); the
        # independent dynbench400_eval entry no longer starts new work (#167).
        if _is_dynbench_eval_prompt(lowered):
            parameters: dict[str, Any] = {}
            keyword = _extract_keyword(lowered)
            if keyword:
                parameters["keyword"] = keyword
            reference_label = _extract_reference_label(lowered)
            if reference_label:
                parameters["reference_label"] = reference_label
            count = _extract_rescan_count(lowered)
            if count:
                parameters["limit"] = count
            return GovernanceIntent(
                kind="execute", capability="risk_corpus_rescan", parameters=parameters
            )
        if _is_rescan_prompt(lowered):
            parameters = {}
            keyword = _extract_keyword(lowered)
            if keyword:
                parameters["keyword"] = keyword
            reference_label = _extract_reference_label(lowered)
            if reference_label:
                parameters["reference_label"] = reference_label
            count = _extract_rescan_count(lowered)
            if count:
                parameters["limit"] = count
            return GovernanceIntent(
                kind="execute", capability="risk_corpus_rescan", parameters=parameters
            )
        if any(marker in lowered for marker in ("构成", "概览", "范围", "分布")):
            return GovernanceIntent(
                kind="execute", capability="risk_corpus_overview", parameters={}
            )
        parameters = {}
        keyword = _extract_keyword(lowered)
        if keyword:
            parameters["keyword"] = keyword
        reference_label = _extract_reference_label(lowered)
        if reference_label:
            parameters["reference_label"] = reference_label
        return GovernanceIntent(
            kind="execute", capability="risk_corpus_search", parameters=parameters
        )


_KEYWORD_BEFORE = re.compile(r"关键词\s*[:：]?\s*([^\s，,。；;]+)")


def _extract_keyword(lowered: str) -> str | None:
    match = _KEYWORD_BEFORE.search(lowered)
    return match.group(1) if match else None


_GROUP_ID_IN_PROMPT = re.compile(r"[a-z0-9_]+#[a-f0-9]{6,}")


def _extract_group_id(lowered: str) -> str | None:
    match = _GROUP_ID_IN_PROMPT.search(lowered)
    return match.group(0) if match else None


_RECORD_ID_EXPLICIT = re.compile(r"record_id\s*[:：=]\s*([A-Za-z0-9_-]{3,})")
_RECORD_ID_LABELLED = re.compile(r"(?:资产|记录)\s*[:：=]\s*([A-Za-z0-9_-]{3,})")
_SOURCE_IN_PROMPT = re.compile(r"来源\s*[:：=]?\s*([^\s，,。；;]+)")


def _extract_record_id(lowered: str) -> str | None:
    for pattern in (_RECORD_ID_EXPLICIT, _RECORD_ID_LABELLED):
        match = pattern.search(lowered)
        if match:
            return match.group(1)
    return None


def _extract_source(lowered: str) -> str | None:
    match = _SOURCE_IN_PROMPT.search(lowered)
    return match.group(1) if match else None


def _extract_status(lowered: str) -> str | None:
    if any(token in lowered for token in ("待导入", "未完成", "pending")):
        return STATUS_PENDING
    if any(token in lowered for token in ("已完成", "完成", "已导入", "completed", "imported")):
        return STATUS_IMPORTED
    return None


_CULTURAL_MARKERS = ("文化", "多样性", "民族", "ethnic")
_DIFFICULTY_IN_PROMPT = re.compile(r"(?:难度|level)\s*[:：=]?\s*(l[0-9])", re.IGNORECASE)
_DIFFICULTY_LEVEL_TOKEN = re.compile(r"\bl([1-9])\b")
# Only an explicit "民族：X" value is read. A bare demonym ("藏族") cannot be
# told apart from a verb + 族 by regex, so guessing risks a phantom filter; the
# real provider handles that语义, the stub stays conservative.
_ETHNIC_EXPLICIT = re.compile(r"民族\s*[:：=]\s*([^\s，,。；;]+)")


def _is_cultural_prompt(lowered: str) -> bool:
    return any(marker in lowered for marker in _CULTURAL_MARKERS)


def _extract_difficulty_level(lowered: str) -> str | None:
    labelled = _DIFFICULTY_IN_PROMPT.search(lowered)
    if labelled:
        return labelled.group(1).upper()
    token = _DIFFICULTY_LEVEL_TOKEN.search(lowered)
    return f"L{token.group(1)}" if token else None


def _extract_ethnic_group(lowered: str) -> str | None:
    explicit = _ETHNIC_EXPLICIT.search(lowered)
    return explicit.group(1) if explicit else None


_CBRNE_MARKERS = (
    "cbrne",
    "异常数据",
    "种子库",
    "anomaly_seedbank",
    "dataset_snapshot",
    "课题二异常",
)

_CBRNE_ASSET_ID = re.compile(
    r"(?:asset_id|资产)\s*[:：=]\s*([A-Za-z0-9_.-]{3,})",
    re.IGNORECASE,
)
_CBRNE_SAMPLE_ID = re.compile(
    r"(?:sample_id|样本)\s*[:：=]\s*([A-Za-z0-9_.-]{3,})",
    re.IGNORECASE,
)
_CBRNE_CATEGORY = re.compile(
    r"(?:类别|cbrne_category)\s*[:：=]\s*([A-Za-z]+)",
    re.IGNORECASE,
)
_CBRNE_TIER = re.compile(r"\b(T[1-4])\b", re.IGNORECASE)
_CBRNE_DIFFICULTY_RANGE = re.compile(
    r"难度\s*[:：]?\s*(\d+)\s*[-~到至]\s*(\d+)"
)


def _is_cbrne_prompt(lowered: str) -> bool:
    return any(marker in lowered for marker in _CBRNE_MARKERS)


def _extract_cbrne_asset_id(lowered: str) -> str | None:
    match = _CBRNE_ASSET_ID.search(lowered)
    return match.group(1) if match else None


def _extract_cbrne_sample_id(lowered: str) -> str | None:
    match = _CBRNE_SAMPLE_ID.search(lowered)
    return match.group(1) if match else None


def _extract_cbrne_filters(lowered: str) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    asset_id = _extract_cbrne_asset_id(lowered)
    if asset_id:
        parameters["asset_id"] = asset_id
    label = _extract_reference_label(lowered)
    if label:
        parameters["label"] = label
    source = _extract_source(lowered)
    if source:
        parameters["source"] = source
    category = _CBRNE_CATEGORY.search(lowered)
    if category:
        parameters["cbrne_category"] = category.group(1)
    tier = _CBRNE_TIER.search(lowered)
    if tier:
        parameters["exposure_tier"] = tier.group(1).upper()
    difficulty = _CBRNE_DIFFICULTY_RANGE.search(lowered)
    if difficulty:
        parameters["difficulty_min"] = int(difficulty.group(1))
        parameters["difficulty_max"] = int(difficulty.group(2))
    return parameters


_RISK_MARKERS = ("风险语料", "风险样本", "风险", "dynbench", "不安全样本", "安全样本")

# Re-detection wording must reach risk_corpus_rescan (which only freezes a
# scope and waits for confirmation), never risk_corpus_search. Two tiers: an
# explicit detection phrase always wins, while a bare "检测" only counts when
# the prompt is not asking for an overview/构成/分布 answer (read-only overview
# wins ties over the paid capability).
_RESCAN_EXPLICIT_MARKERS = (
    "二次检测",
    "重新检测",
    "复检",
    "发起检测",
    "在线检测",
    "批量检测",
    "做检测",
    "进行检测",
    "跑检测",
    "检测一遍",
    "检测一下",
    "检测这批",
    "检测这些",
    "检测全部",
    "检一下",
)

# Input-eval wording for DynBench400 (#92). Checked before rescan so prompts
# like "对 DynBench400 做输入评测" are not captured by bare 检测 markers.
_DYNBENCH_EVAL_MARKERS = (
    "输入评测",
    "dynbench400",
    "dynbench 评测",
    "对 dynbench",
)

_OVERVIEW_MARKERS = ("构成", "概览", "分布")

_RESCAN_COUNT = re.compile(r"(\d+)\s*条")


def _is_dynbench_eval_prompt(lowered: str) -> bool:
    return any(marker in lowered for marker in _DYNBENCH_EVAL_MARKERS)


def _is_rescan_prompt(lowered: str) -> bool:
    if any(marker in lowered for marker in _RESCAN_EXPLICIT_MARKERS):
        return True
    return "检测" in lowered and not any(
        marker in lowered for marker in _OVERVIEW_MARKERS
    )


def _extract_rescan_count(lowered: str) -> int | None:
    """Read an explicit "N 条" sample count, clamped to the server-side cap.

    The server-side maximum stays authoritative; the stub merely avoids
    emitting a parameter the capability contract would reject."""
    match = _RESCAN_COUNT.search(lowered)
    if match is None:
        return None
    return min(int(match.group(1)), RISK_RESCAN_MAX_SAMPLES)


def _is_risk_prompt(lowered: str) -> bool:
    return any(marker in lowered for marker in _RISK_MARKERS)


def _extract_reference_label(lowered: str) -> str | None:
    if any(token in lowered for token in ("不安全", "unsafe")):
        return "unsafe"
    if any(token in lowered for token in ("安全", "safe")):
        return "safe"
    return None


def _safe_error(exc: Exception) -> str:
    """Return a bounded, non-leaking error label: type name only, never the
    upstream message/response body, which may embed unrelated raw content."""
    return exc.__class__.__name__


def get_assistant_interpreter() -> AssistantInterpreter:
    settings = get_settings()
    provider = settings.governance_assistant_provider
    if provider == "stub":
        return StubInterpreter()
    config = chat_provider_config()
    if config is None:
        raise ValueError(f"未知的治理助手 provider: {provider}")
    if config.provider == "deepseek" and (
        config.api_key is None or not config.api_key.get_secret_value().strip()
    ):
        raise DeepSeekConfigurationError(
            "DeepSeek 治理助手未配置 DEEPSEEK_API_KEY。"
        )
    return OpenAiCompatibleInterpreter(
        name=config.name,
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
    )
