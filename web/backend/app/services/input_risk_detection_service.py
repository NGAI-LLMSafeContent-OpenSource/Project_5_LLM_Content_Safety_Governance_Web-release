"""Neutral input-risk detection domain service (#170).

One detection boundary shared by the input-side BFF (``/data-input`` and
``/input-guardrail``) and the governance secondary-detection path. It owns
method resolution, the upstream health preflight and explicit-text detection,
and returns presentation-free facts only: it never imports
``app.schemas.data_input`` or ``app.schemas.governance`` and carries no product
copy. Failures surface as neutral machine-readable tokens (``reason`` /
``failure_kind`` / ``InputRiskDetectionError.code``); callers compose the
user-facing copy.

Two caller-visible guarantees:

* an unreachable upstream is reported as ``connected=False`` with a
  diagnosable reason — never degraded into a fake success;
* an empty request raises :class:`InputRiskDetectionError` instead of
  fabricating placeholder samples.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Sequence

from app.adapters.topic2.activation_probe_client import (
    Topic2ActivationProbeUnavailable,
    build_topic2_activation_probe_client,
)
from app.adapters.topic2.filterguard_client import (
    Topic2FilterGuardUnavailable,
    build_topic2_filterguard_client,
)
from app.core.config import get_settings
from app.services.topic2_harm_labels import format_harm_category_l1

METHOD_KEYWORD = "keyword"
METHOD_ACTIVATION_PROBE = "activation_probe"
SUPPORTED_INPUT_RISK_METHODS: frozenset[str] = frozenset(
    {METHOD_KEYWORD, METHOD_ACTIVATION_PROBE}
)

# Upstream names for the same remote Activation Probe method.
_ACTIVATION_PROBE_ALIASES = frozenset(
    {"neuron", "activation-probe", "activation_probe__same_l1", "same_l1"}
)


class InputRiskDetectionError(Exception):
    """Detection could not be initiated (including an empty request).

    ``code`` is a neutral, machine-readable token; callers map it to their own
    product copy. Raising this is always better than fabricating a result:
    callers must report an explicit failure and must not degrade into mock
    samples.
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class InputRiskHealth:
    """Neutral health fact for one resolved detection method."""

    connected: bool
    method: str
    base_url: str = ""
    source: str = ""  # topic2_filterguard | topic2_activation_probe
    reason: str = ""  # neutral diagnostic token when not connected (never a fake success)
    detail: str = ""  # neutral upstream facts, e.g. method/model/max_batch
    offered_methods: tuple[str, ...] = ()  # upstream-advertised methods (method_missing)
    failure_kind: str = ""  # unreachable | method_missing | not_ready (when disconnected)


@dataclass(frozen=True)
class InputRiskHit:
    """One per-text detection fact, keyed by the caller's ``texts`` index."""

    index: int
    unsafe: bool
    score: float = 0.0
    threshold: float = 1.0
    hits: tuple[str, ...] = ()
    harm_category_l1: str = ""
    predicted_l1_id: str = ""


@dataclass(frozen=True)
class InputRiskDetection:
    """Whole-run detection fact for one explicit text sequence."""

    connected: bool
    method: str
    base_url: str = ""
    source: str = ""
    reason: str = ""
    items: tuple[InputRiskHit, ...] = ()


def resolve_input_risk_method(method: str | None = None) -> str:
    """Resolve the detection method: request first, else the registered default.

    Recognises the historical Activation Probe aliases (``neuron`` /
    ``activation-probe`` / ``activation_probe__same_l1`` / ``same_l1``) and falls
    back to ``activation_probe`` for anything unsupported.
    """

    raw = (method or "").strip().lower()
    if not raw:
        raw = (
            get_settings().topic2_risk_detect_method or METHOD_ACTIVATION_PROBE
        ).strip().lower()
    if raw in _ACTIVATION_PROBE_ALIASES:
        return METHOD_ACTIVATION_PROBE
    if raw in SUPPORTED_INPUT_RISK_METHODS:
        return raw
    return METHOD_ACTIVATION_PROBE


async def check_input_risk_health(method: str | None = None) -> InputRiskHealth:
    """Preflight the resolved method; an unreachable upstream is reported, not raised."""

    resolved = resolve_input_risk_method(method)
    if resolved == METHOD_ACTIVATION_PROBE:
        return await _check_activation_probe_health()
    return await _check_keyword_health()


async def _check_keyword_health() -> InputRiskHealth:
    client = build_topic2_filterguard_client()
    try:
        payload = await client.health()
    except Topic2FilterGuardUnavailable as exc:
        return InputRiskHealth(
            connected=False,
            method=METHOD_KEYWORD,
            base_url=client.base_url,
            source="topic2_filterguard",
            reason=str(exc) or "unreachable",
            failure_kind="unreachable",
        )

    methods = payload.get("methods", [])
    offered_methods = (
        tuple(str(item) for item in methods) if isinstance(methods, list) else ()
    )
    if client.method not in offered_methods:
        return InputRiskHealth(
            connected=False,
            method=METHOD_KEYWORD,
            base_url=client.base_url,
            source="topic2_filterguard",
            reason="method_not_loaded",
            detail=f"method={client.method}",
            offered_methods=offered_methods,
            failure_kind="method_missing",
        )

    return InputRiskHealth(
        connected=True,
        method=client.method,
        base_url=client.base_url,
        source="topic2_filterguard",
        detail=f"method={client.method}",
    )


async def _check_activation_probe_health() -> InputRiskHealth:
    client = build_topic2_activation_probe_client()
    try:
        payload = await client.health()
        info = await client.info()
    except Topic2ActivationProbeUnavailable as exc:
        return InputRiskHealth(
            connected=False,
            method=METHOD_ACTIVATION_PROBE,
            base_url=client.base_url,
            source="topic2_activation_probe",
            reason=str(exc),
            failure_kind="unreachable",
        )

    status = str(payload.get("status") or "").lower()
    if status not in {"ready", "ok", "running", "success"}:
        return InputRiskHealth(
            connected=False,
            method=METHOD_ACTIVATION_PROBE,
            base_url=client.base_url,
            source="topic2_activation_probe",
            reason=f"healthz status={status!r}",
            failure_kind="not_ready",
        )

    upstream_method = str(
        info.get("method")
        or payload.get("method")
        or (
            "、".join(
                str(item) for item in info.get("methods") or payload.get("methods") or []
            )
        )
        or "activation_probe__same_l1"
    )
    model = str(info.get("model") or "")
    max_batch = info.get("max_batch_size") or client.max_batch
    details = f"method={upstream_method}"
    if model:
        details += f"，model={model}"
    details += f"，max_batch={max_batch}"

    return InputRiskHealth(
        connected=True,
        method=METHOD_ACTIVATION_PROBE,
        base_url=client.base_url,
        source="topic2_activation_probe",
        detail=details,
    )


async def detect_input_risk(
    texts: Sequence[str], *, method: str | None = None
) -> InputRiskDetection:
    """Run online detection for an explicit text sequence.

    ``texts`` is detected in order; each :class:`InputRiskHit` reports the index
    into this sequence. An empty (or entirely blank) request raises
    :class:`InputRiskDetectionError` — no placeholder samples are ever invented.
    """

    normalized = [str(text) for text in texts]
    if not any(text.strip() for text in normalized):
        raise InputRiskDetectionError(
            "empty_texts", "no texts were provided; online detection was not called"
        )

    resolved = resolve_input_risk_method(method)
    if resolved == METHOD_ACTIVATION_PROBE:
        return await _run_activation_probe_detection(normalized)
    return await _run_keyword_detection(normalized)


async def _run_keyword_detection(texts: list[str]) -> InputRiskDetection:
    client = build_topic2_filterguard_client()
    try:
        payload = await client.predict(texts)
    except Topic2FilterGuardUnavailable as exc:
        return InputRiskDetection(
            connected=False,
            method=METHOD_KEYWORD,
            base_url=client.base_url,
            source="topic2_filterguard",
            reason=str(exc) or "unreachable",
        )

    return InputRiskDetection(
        connected=True,
        method=str(payload.get("method") or client.method),
        base_url=client.base_url,
        source="topic2_filterguard",
        items=tuple(_normalize_keyword_hits(payload, source_count=len(texts))),
    )


async def _run_activation_probe_detection(texts: list[str]) -> InputRiskDetection:
    client = build_topic2_activation_probe_client()
    try:
        payload = await client.moderate(texts)
    except Topic2ActivationProbeUnavailable as exc:
        return InputRiskDetection(
            connected=False,
            method=METHOD_ACTIVATION_PROBE,
            base_url=client.base_url,
            source="topic2_activation_probe",
            reason=str(exc),
        )

    return InputRiskDetection(
        connected=True,
        method=METHOD_ACTIVATION_PROBE,
        base_url=client.base_url,
        source="topic2_activation_probe",
        items=tuple(_normalize_activation_probe_hits(payload, source_count=len(texts))),
    )


def _iter_normalized_items(
    payload: dict[str, Any], *, source_count: int
) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield ``(source_index, item)`` for each usable upstream result row.

    Shared walk for every method's normalizer: it guards the ``results`` payload,
    maps each row back to the caller's ``texts`` index and drops rows whose index
    cannot be resolved. Each normalizer keeps only its own field mapping.
    """
    raw_items = payload.get("results", [])
    if not isinstance(raw_items, list):
        return
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        source_index = _source_index_for_item(
            item, fallback=index, source_count=source_count
        )
        if source_index is None:
            continue
        yield source_index, item


def _normalize_keyword_hits(
    payload: dict[str, Any], *, source_count: int
) -> list[InputRiskHit]:
    return [
        InputRiskHit(
            index=source_index,
            unsafe=_is_keyword_unsafe(item),
            score=_to_float(item.get("score")),
            threshold=_to_float(item.get("threshold"), default=1.0),
            hits=tuple(_extract_hits(item)),
        )
        for source_index, item in _iter_normalized_items(
            payload, source_count=source_count
        )
    ]


def _normalize_activation_probe_hits(
    payload: dict[str, Any], *, source_count: int
) -> list[InputRiskHit]:
    hits: list[InputRiskHit] = []
    for source_index, item in _iter_normalized_items(
        payload, source_count=source_count
    ):
        is_abnormal = bool(item.get("unsafe")) or int(item.get("label") or 0) == 1
        harm_l1 = str(
            item.get("harm_category_L1") or item.get("harm_category_l1") or ""
        ).strip()
        hits.append(
            InputRiskHit(
                index=source_index,
                unsafe=is_abnormal,
                score=1.0 if is_abnormal else 0.0,
                threshold=0.5,
                harm_category_l1=format_harm_category_l1(harm_l1) or harm_l1,
                predicted_l1_id=str(item.get("predicted_l1_id") or "").strip(),
            )
        )
    return hits


def _is_keyword_unsafe(item: dict[str, Any]) -> bool:
    return bool(item.get("is_abnormal") or int(item.get("prediction") or 0) == 1)


def _source_index_for_item(
    item: dict[str, Any], fallback: int, source_count: int
) -> int | None:
    raw_index = item.get("index")
    if isinstance(raw_index, int) and 0 <= raw_index < source_count:
        return raw_index
    if isinstance(raw_index, str) and raw_index.isdigit():
        parsed_index = int(raw_index)
        if 0 <= parsed_index < source_count:
            return parsed_index
    if 0 <= fallback < source_count:
        return fallback
    return None


def _extract_hits(item: dict[str, Any]) -> list[str]:
    details = item.get("details", {})
    if not isinstance(details, dict):
        return []
    hits = details.get("hits", [])
    if not isinstance(hits, list):
        return []
    return [str(hit) for hit in hits if str(hit).strip()]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
