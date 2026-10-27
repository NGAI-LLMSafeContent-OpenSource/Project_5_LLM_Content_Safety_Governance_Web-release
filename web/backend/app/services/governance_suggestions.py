"""Grounded, server-validated follow-up suggestions for governance sessions (#65).

Candidates are derived deterministically from the newest stable assistant result
of a session (or from one task's aggregated outcome). The server always
re-derives ``handling`` from the registered capability, drops unregistered
capabilities, and re-validates any provider ranking: a model may only reorder ids
and rewrite ``title``/``prompt``.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import GovernanceMessage, GovernanceSession, GovernanceTask
from app.schemas.governance import (
    RISK_RESCAN_STATUS_AWAITING,
    RISK_RESCAN_STATUS_CANCELLED,
    RISK_RESCAN_STATUS_CANCELLING,
    RISK_RESCAN_STATUS_COMPLETED_PARTIAL,
    RISK_RESCAN_STATUS_FAILED,
    RISK_RESCAN_STATUS_QUEUED,
    RISK_RESCAN_STATUS_RUNNING,
    RISK_RESCAN_STATUS_TIMEOUT,
    GovernanceTaskSuggestion,
    GovernanceTaskSuggestionResult,
)
from app.services.governance_assistant import chat_provider_config
from app.services.governance_capabilities import resolve_capability
from app.services.governance_llm_text import extract_chat_content, extract_json_object
from app.services.governance_run_aggregation import build_task_aggregated_result


MAX_SUGGESTIONS = 4
MIN_SUGGESTIONS = 2
RESCAN_CAPABILITY = "risk_corpus_rescan"
RESCAN_SKILL_KEY = "risk-corpus-rescan"

# A task is "in flight" until it reaches a terminal status. While in flight the
# plan and confirmation are already visible, so piling suggestions on top would
# only add noise or imply an action that is not actually available yet.
IN_FLIGHT_STATUSES = frozenset(
    {
        RISK_RESCAN_STATUS_AWAITING,
        RISK_RESCAN_STATUS_QUEUED,
        RISK_RESCAN_STATUS_RUNNING,
        RISK_RESCAN_STATUS_CANCELLING,
    }
)

# A same-task retry is only accepted from these terminal statuses, so the retry
# suggestion stays grounded in what the retry endpoint will actually allow.
RETRYABLE_TERMINAL_STATUSES = frozenset(
    {
        RISK_RESCAN_STATUS_FAILED,
        RISK_RESCAN_STATUS_CANCELLED,
        RISK_RESCAN_STATUS_TIMEOUT,
        RISK_RESCAN_STATUS_COMPLETED_PARTIAL,
    }
)

# Assistant messages that carry a landed, server-produced result. Clarify and
# boundary messages never anchor suggestions.
STABLE_RESULT_KINDS = frozenset(
    {
        "risk_corpus_overview",
        "risk_corpus_search",
        "risk_corpus_rescan",
        "value_corpus_overview",
        "value_qa_search",
        "value_qa_group_detail",
        "risk_system_record_search",
        "risk_system_record_detail",
        "cultural_system_record_search",
        "cultural_system_record_detail",
    }
)


def _candidate(
    candidate_id: str,
    title: str,
    prompt: str,
    *,
    capability: str | None = None,
    skill_key: str | None = None,
    parameters: Mapping[str, Any] | None = None,
    reason: str = "",
    priority: int = 0,
) -> dict:
    return {
        "id": candidate_id,
        "title": title,
        "prompt": prompt,
        "capability": capability,
        "skill_key": skill_key,
        "parameters": dict(parameters or {}),
        "reason": reason,
        "priority": priority,
    }


def _read_only_candidates(kind: str) -> list[dict]:
    """Server-authored templates for a landed read-only result.

    Each candidate binds a real capability; the handling is recomputed later, so
    a candidate that is not registered in the session domain is dropped instead
    of being mislabelled.
    """

    if kind in ("risk_corpus_search", "risk_corpus_overview"):
        return [
            _candidate(
                "risk-continue-browse",
                "浏览更多风险样本",
                "继续浏览下一页风险样本",
                capability="risk_corpus_search",
                parameters={"continuation": True},
                reason="延续当前的风险样本筛选范围，继续查看样本与来源",
                priority=10,
            ),
            _candidate(
                "risk-overview",
                "查看风险语料构成",
                "查看风险语料构成",
                capability="risk_corpus_overview",
                reason="了解当前风险语料的整体分布与来源构成",
                priority=20,
            ),
            _candidate(
                "risk-rescan-scope",
                "对当前筛选样本发起二次检测",
                "对当前筛选样本发起在线二次检测",
                capability=RESCAN_CAPABILITY,
                skill_key=RESCAN_SKILL_KEY,
                reason="当前筛选范围可冻结为一次在线二次检测计划，确认后才会执行",
                priority=30,
            ),
        ]
    if kind == "value_corpus_overview":
        return [
            _candidate(
                "value-search",
                "检索价值问题组",
                "检索价值问题组",
                capability="value_qa_search",
                reason="按关键词、主题或价值维度查看具体价值问题组",
                priority=10,
            ),
        ]
    if kind in ("value_qa_search", "value_qa_group_detail"):
        return [
            _candidate(
                "value-search-more",
                "继续检索价值问题组",
                "继续检索价值问题组",
                capability="value_qa_search",
                parameters={"continuation": True},
                reason="延续当前检索条件，继续查看价值问题组",
                priority=10,
            ),
            _candidate(
                "value-overview",
                "查看价值语料构成",
                "查看价值语料构成",
                capability="value_corpus_overview",
                reason="了解价值语料的整体规模与维度构成",
                priority=20,
            ),
        ]
    if kind == "risk_system_record_search":
        return [
            _candidate(
                "risk-records-continue",
                "继续浏览系统预跑记录",
                "继续浏览下一页系统预跑记录",
                capability="risk_system_record_search",
                parameters={"continuation": True},
                reason="延续当前筛选，继续查看风险安全系统预跑记录",
                priority=10,
            ),
        ]
    if kind == "risk_system_record_detail":
        return [
            _candidate(
                "risk-records-list",
                "返回系统预跑记录列表",
                "浏览与筛选系统预跑记录",
                capability="risk_system_record_search",
                reason="离开当前详情，查看其它风险安全系统预跑记录",
                priority=10,
            ),
        ]
    if kind == "cultural_system_record_search":
        return [
            _candidate(
                "cultural-records-continue",
                "继续浏览文化多样性系统预跑记录",
                "继续浏览下一页文化多样性系统预跑记录",
                capability="cultural_system_record_search",
                parameters={"continuation": True},
                reason="延续当前筛选，继续查看文化多样性系统预跑记录",
                priority=10,
            ),
        ]
    if kind == "cultural_system_record_detail":
        return [
            _candidate(
                "cultural-records-list",
                "返回系统预跑记录列表",
                "浏览与筛选文化多样性系统预跑记录",
                capability="cultural_system_record_search",
                reason="离开当前详情，查看其它文化多样性系统预跑记录",
                priority=10,
            ),
        ]
    return []


def _terminal_rescan_candidates(
    summary: Mapping[str, Any] | None, status: str
) -> list[dict]:
    """Templates for a terminal re-detection task (result or notice)."""

    summary = summary or {}
    failed = int(summary.get("failed_count") or 0)
    not_executed = int(summary.get("not_executed_count") or 0)
    retry = (
        status in RETRYABLE_TERMINAL_STATUSES or failed > 0 or not_executed > 0
    )
    candidates: list[dict] = []
    if retry:
        candidates.append(
            _candidate(
                "rescan-retry",
                "重试未完成样本",
                "重试未完成的风险样本在线二次检测",
                capability=RESCAN_CAPABILITY,
                skill_key=RESCAN_SKILL_KEY,
                reason="上次运行存在失败或未执行的样本，可在同一任务内规划重试",
                priority=10,
            )
        )
    candidates.append(
        _candidate(
            "rescan-overview",
            "查看风险语料构成",
            "查看风险语料构成",
            capability="risk_corpus_overview",
            reason="核对本次检测所依据的风险语料构成",
            priority=20,
        )
    )
    candidates.append(
        _candidate(
            "rescan-browse",
            "浏览更多风险样本",
            "浏览风险样本",
            capability="risk_corpus_search",
            reason="继续浏览相关风险样本与来源",
            priority=30,
        )
    )
    return candidates


class GovernanceSuggestionRanker(Protocol):
    """Seam a provider may implement to reorder/rewrite server candidates."""

    origin: str

    async def rank(
        self, candidates: Sequence[Mapping[str, Any]]
    ) -> list[Mapping[str, Any]]:
        ...


class DeterministicSuggestionRanker:
    """Default ranker: no rewrite, the server's priority order is authoritative."""

    origin = "deterministic"

    async def rank(
        self, candidates: Sequence[Mapping[str, Any]]
    ) -> list[Mapping[str, Any]]:
        return [dict(candidate) for candidate in candidates]


class ModelSuggestionRanker:
    """Provider-backed ranker seam.

    It may only return an id order and rewritten ``title``/``prompt``. The server
    re-validates every value, so a misbehaving or unreachable provider cannot
    introduce candidates or change ``handling``/``capability``; any failure falls
    back to the server order.
    """

    origin = "model"

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        model: str,
        api_key: Any | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self._timeout = timeout

    def _payload(self, candidates: Sequence[Mapping[str, Any]]) -> dict:
        rendered = [
            {
                "id": candidate["id"],
                "title": candidate["title"],
                "prompt": candidate["prompt"],
                "handling": candidate["handling"],
                "capability": candidate.get("capability"),
            }
            for candidate in candidates
        ]
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是治理会话的后续建议排序器。只能返回候选 id 的顺序"
                        "与改写后的 title/prompt，不得新增、删除候选，"
                        "不得修改 handling 或 capability。只返回 JSON："
                        '{"order":["<id>",...],"rewrites":{"<id>":{"title":...,"prompt":...}}}。'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(rendered, ensure_ascii=False),
                },
            ],
            "temperature": 0,
            "stream": False,
        }

    async def rank(
        self, candidates: Sequence[Mapping[str, Any]]
    ) -> list[Mapping[str, Any]]:
        import httpx  # local import keeps the deterministic default import-light

        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key.get_secret_value()}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, trust_env=False
            ) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=self._payload(candidates),
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
            content = extract_chat_content(data)
            parsed = json.loads(extract_json_object(content) or "{}")
        except Exception:  # noqa: BLE001 - any failure keeps the server order
            return [dict(candidate) for candidate in candidates]

        order = parsed.get("order") if isinstance(parsed.get("order"), list) else []
        rewrites = parsed.get("rewrites") if isinstance(parsed.get("rewrites"), dict) else {}
        items: list[dict] = []
        for raw_id in order:
            candidate_id = str(raw_id)
            item: dict = {"id": candidate_id}
            rewrite = rewrites.get(candidate_id)
            if isinstance(rewrite, dict):
                if isinstance(rewrite.get("title"), str):
                    item["title"] = rewrite["title"]
                if isinstance(rewrite.get("prompt"), str):
                    item["prompt"] = rewrite["prompt"]
            items.append(item)
        return items


def _build_model_ranker() -> ModelSuggestionRanker | None:
    """Build the model ranker from the shared chat provider config.

    The assistant interpreter and the ranker resolve the same provider fields;
    only the missing-credential policy differs (the ranker opts out, the
    interpreter raises) and stays at each call site (#65)."""

    config = chat_provider_config()
    if config is None:
        return None
    if config.provider == "deepseek" and (
        config.api_key is None or not config.api_key.get_secret_value().strip()
    ):
        return None
    return ModelSuggestionRanker(
        name=config.name,
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout=get_settings().governance_assistant_timeout_seconds,
    )


def get_suggestion_ranker() -> GovernanceSuggestionRanker:
    """Return the configured ranker, defaulting to the deterministic one."""

    if get_settings().governance_suggestion_ranker == "model":
        ranker = _build_model_ranker()
        if ranker is not None:
            return ranker
    return DeterministicSuggestionRanker()


def _resolve_handling(domain: str, capability_key: str | None) -> str | None:
    """Re-derive handling from the registry; None means the candidate is dropped."""

    if not capability_key:
        return None
    capability = resolve_capability(domain, capability_key)
    if capability is None:
        return None
    return "plan" if capability.requires_confirmation else "direct"


def _resolve_candidates(
    domain: str, candidates: Sequence[Mapping[str, Any]]
) -> list[dict]:
    resolved: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        if not candidate_id or candidate_id in seen:
            continue
        handling = _resolve_handling(domain, candidate.get("capability"))
        if handling is None:
            continue
        seen.add(candidate_id)
        parameters = candidate.get("parameters")
        resolved.append(
            {
                "id": candidate_id,
                "title": str(candidate.get("title") or ""),
                "prompt": str(candidate.get("prompt") or ""),
                "handling": handling,
                "capability": candidate.get("capability"),
                "skill_key": candidate.get("skill_key"),
                "parameters": dict(parameters) if isinstance(parameters, Mapping) else {},
                "reason": str(candidate.get("reason") or ""),
                "priority": int(candidate.get("priority") or 0),
            }
        )
    resolved.sort(key=lambda item: (item["priority"], item["id"]))
    return resolved


def _validate_ranked(
    resolved: Sequence[Mapping[str, Any]],
    ranked: Sequence[Mapping[str, Any]],
    *,
    origin: str,
) -> list[GovernanceTaskSuggestion]:
    """Apply a ranker result without letting it widen the server's candidate set."""

    by_id = {candidate["id"]: candidate for candidate in resolved}
    suggestions: list[GovernanceTaskSuggestion] = []
    used: set[str] = set()

    def _add(candidate: Mapping[str, Any], item: Mapping[str, Any]) -> None:
        candidate_id = str(candidate["id"])
        if candidate_id in used:
            return
        used.add(candidate_id)
        title = item.get("title")
        prompt = item.get("prompt")
        suggestions.append(
            GovernanceTaskSuggestion(
                id=candidate_id,
                title=(
                    title.strip()
                    if isinstance(title, str) and title.strip()
                    else str(candidate["title"])
                ),
                prompt=(
                    prompt.strip()
                    if isinstance(prompt, str) and prompt.strip()
                    else str(candidate["prompt"])
                ),
                handling=candidate["handling"],
                capability=candidate.get("capability"),
                skill_key=candidate.get("skill_key"),
                parameters=candidate.get("parameters") or {},
                reason=str(candidate.get("reason") or ""),
                origin=origin,
            )
        )

    for item in ranked:
        if not isinstance(item, Mapping):
            continue
        candidate = by_id.get(str(item.get("id") or ""))
        if candidate is None:
            # Unknown ids are dropped: a ranker can never invent a candidate.
            continue
        _add(candidate, item)
    for candidate in resolved:
        _add(candidate, candidate)
    return suggestions


async def _ranked_suggestions(
    domain: str, candidates: Sequence[Mapping[str, Any]]
) -> list[GovernanceTaskSuggestion]:
    resolved = _resolve_candidates(domain, candidates)
    if len(resolved) < MIN_SUGGESTIONS:
        return []
    resolved = resolved[:MAX_SUGGESTIONS]
    ranker = get_suggestion_ranker()
    try:
        ranked = list(await ranker.rank(resolved))
    except Exception:  # noqa: BLE001 - ranking is best-effort; order is optional
        ranked = [dict(candidate) for candidate in resolved]
    origin = getattr(ranker, "origin", "model")
    if origin not in ("deterministic", "model"):
        origin = "model"
    return _validate_ranked(resolved, ranked, origin=origin)


def _loads_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


async def _latest_stable_message(
    db: AsyncSession, session_id: str
) -> GovernanceMessage | None:
    result = await db.execute(
        select(GovernanceMessage)
        .where(
            GovernanceMessage.session_id == session_id,
            GovernanceMessage.role == "assistant",
            GovernanceMessage.kind.in_(tuple(sorted(STABLE_RESULT_KINDS))),
        )
        .order_by(GovernanceMessage.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_task(
    db: AsyncSession, client_id: str, task_id: str
) -> GovernanceTask | None:
    if not task_id:
        return None
    result = await db.execute(
        select(GovernanceTask).where(
            GovernanceTask.task_id == task_id,
            GovernanceTask.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


def _aggregated_summary(aggregated: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(aggregated, Mapping):
        return None
    summary = aggregated.get("summary")
    return summary if isinstance(summary, Mapping) else None


async def build_session_suggestions(
    db: AsyncSession, session: GovernanceSession
) -> list[dict]:
    """Return 0 or 2-4 grounded follow-ups for the newest landed result."""

    message = await _latest_stable_message(db, session.session_id)
    if message is None:
        return []
    if message.kind == "risk_corpus_rescan":
        payload = _loads_json(message.payload_json)
        task = await _load_task(
            db, session.client_id, str(payload.get("task_id") or "")
        )
        if task is None or task.status in IN_FLIGHT_STATUSES:
            return []
        aggregated = await build_task_aggregated_result(db, task)
        candidates = _terminal_rescan_candidates(
            _aggregated_summary(aggregated), task.status
        )
    else:
        candidates = _read_only_candidates(message.kind)
    suggestions = await _ranked_suggestions(session.domain, candidates)
    return [suggestion.model_dump(mode="json") for suggestion in suggestions]


async def build_task_suggestions(
    db: AsyncSession, client_id: str, task_id: str
) -> GovernanceTaskSuggestionResult | None:
    """Return grounded follow-ups for one task, or None when it does not exist."""

    task = await _load_task(db, client_id, task_id)
    if task is None:
        return None
    if task.capability != RESCAN_CAPABILITY or task.status in IN_FLIGHT_STATUSES:
        return GovernanceTaskSuggestionResult(
            task_id=task_id, session_id=task.session_id
        )
    session = await db.get(GovernanceSession, task.session_id)
    domain = session.domain if session is not None else "input"
    aggregated = await build_task_aggregated_result(db, task)
    candidates = _terminal_rescan_candidates(
        _aggregated_summary(aggregated), task.status
    )
    suggestions = await _ranked_suggestions(domain, candidates)
    return GovernanceTaskSuggestionResult(
        task_id=task_id,
        session_id=task.session_id,
        has_candidates=bool(suggestions),
        suggestions=suggestions,
    )
