"""Governance risk-corpus online re-detection service (#55).

The capability runner only resolves and freezes an explicit sample scope; it
never calls the online detector. ``execute_confirmed_rescan`` runs the existing
Topic-2 secondary-detection service after the user confirms, compares each
per-sample result with the read-only reference label, and returns a per-sample
outcome. Reference labels are never written back, and the frozen scope can
never exceed the server-side 30-sample cap.

The detection call goes through a replaceable runner seam so integration tests
can use a service double instead of the real online service.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app.core.config import get_settings
from app.schemas.governance import (
    RISK_REFERENCE_LABELS,
    RISK_RESCAN_CAPABILITY_VERSION,
    RISK_RESCAN_MAX_SAMPLES,
    RiskCorpusRescanParams,
)
from app.services.data_input_corpus_catalog_service import (
    RISK_STATIC_ASSET_ID,
    RISK_STATIC_ASSET_NAME,
    RISK_STATIC_MAX_RECORDS,
    build_dynbench400_evaluation_object,
    list_risk_static_records,
)
from app.services.input_risk_detection_service import (
    InputRiskDetectionError,
    InputRiskHit,
    check_input_risk_health,
    detect_input_risk,
    resolve_input_risk_method,
)
from app.services.governance_risk_report_service import (
    evaluator_display_name,
    resolve_rescan_evaluator,
)
from app.services.governance_hashing import canonical_digest, canonical_text, text_digest


RISK_RESCAN_FILTER_KEYS = (
    "keyword",
    "reference_label",
    "source",
    "harm_category_L1",
    "harm_category_L2",
)

RISK_DETECTED_LABELS = ("safe", "unsafe")

PreflightChecker = Callable[[str], Awaitable[dict]]

# ``None`` means "auto": a real online run is preflighted, while an injected
# detection double (tests / offline) skips the network preflight.
_preflight_checker: PreflightChecker | None = None


def get_risk_preflight_checker() -> PreflightChecker | None:
    return _preflight_checker


def set_risk_preflight_checker(checker: PreflightChecker | None) -> None:
    """Replace the evaluator health preflight (test/dev seam only)."""
    global _preflight_checker
    _preflight_checker = checker


async def preflight_rescan_evaluator(evaluator: str) -> dict:
    """Require the selected Topic-2 evaluator health before any detection call."""
    method = resolve_rescan_evaluator(evaluator)
    health = await check_input_risk_health(method=method)
    return {
        "ok": bool(health.connected),
        "method": health.method or method,
        "reason": health.reason,
        "base_url": health.base_url,
    }


def normalize_sample_text(text: str) -> str:
    """Server-side text normalization used before hashing a sample fact."""
    return canonical_text(text)


def sample_content_digest(text: str) -> str:
    """Stable, non-reversible digest of a sample's normalized text."""
    return text_digest(text)


def derive_source_revision(source: str, sample_id: str, content_digest: str) -> str:
    """Secret-free revision for an asset record without its own version string."""
    return canonical_digest(
        {
            "source": str(source or ""),
            "sample_id": str(sample_id or ""),
            "content_digest": str(content_digest or ""),
        }
    )


@dataclass(frozen=True)
class RiskDetectionItem:
    """One per-sample detection outcome, normalized to the corpus label space."""

    source_index: int
    detected_label: str
    detail: str = ""


@dataclass(frozen=True)
class RiskDetectionRun:
    """Whole-run outcome of one online detection call."""

    ok: bool
    method: str = ""
    reason: str = ""
    items: tuple[RiskDetectionItem, ...] = field(default_factory=tuple)


async def _topic2_detection_runner(
    texts: list[str], *, method: str | None = None
) -> RiskDetectionRun:
    """Default runner: the shared neutral input-risk detection service.

    An unreachable upstream reports ``connected=False`` instead of raising; that
    is a real failure and must not degrade into a fake success. ``method`` lets
    DynBench (#93 T2) select ``activation_probe`` or ``keyword`` without relying
    on the process-wide settings default."""
    try:
        detection = await detect_input_risk(list(texts), method=method)
    except InputRiskDetectionError as exc:
        return RiskDetectionRun(
            ok=False,
            method=resolve_input_risk_method(method),
            reason=str(exc),
        )
    if not detection.connected:
        return RiskDetectionRun(
            ok=False,
            method=detection.method,
            reason=detection.reason,
        )
    items = tuple(
        RiskDetectionItem(
            source_index=hit.index,
            detected_label="unsafe" if hit.unsafe else "safe",
            detail=_neutral_hit_detail(hit),
        )
        for hit in detection.items
    )
    return RiskDetectionRun(ok=True, method=detection.method, items=items)


def _neutral_hit_detail(hit: InputRiskHit) -> str:
    """Neutral per-sample fact; never the input-side presentation string."""

    parts = [f"unsafe={str(hit.unsafe).lower()}", f"score={hit.score:g}"]
    if hit.predicted_l1_id:
        parts.append(f"predicted_l1_id={hit.predicted_l1_id}")
    if hit.harm_category_l1:
        parts.append(f"harm_category_L1={hit.harm_category_l1}")
    if hit.hits:
        parts.append(f"keyword_hits={len(hit.hits)}")
    return "，".join(parts)


_detection_runner: Callable[[list[str]], Awaitable[RiskDetectionRun]] = (
    _topic2_detection_runner
)


def get_risk_detection_runner() -> Callable[[list[str]], Awaitable[RiskDetectionRun]]:
    return _detection_runner


def set_risk_detection_runner(
    runner: Callable[[list[str]], Awaitable[RiskDetectionRun]],
) -> None:
    """Replace the online detection call (test/dev seam only)."""
    global _detection_runner
    _detection_runner = runner


def resolve_rescan_scope(params: RiskCorpusRescanParams) -> dict:
    """Resolve a detection request into an explicit, frozen sample scope.

    This never calls the online service. The 30-sample cap is enforced here a
    second time — on top of parameter validation — so the frozen scope cannot
    exceed the server-side maximum no matter who produced the parameters."""
    filters = {
        key: value for key in RISK_RESCAN_FILTER_KEYS if (value := getattr(params, key))
    }
    evaluator = resolve_rescan_evaluator(getattr(params, "evaluator", None))
    export_requested = bool(getattr(params, "export_requested", False))
    requested_ids = params.sample_ids
    list_limit = (
        RISK_STATIC_MAX_RECORDS
        if requested_ids
        else min(max(int(params.limit), 1), RISK_RESCAN_MAX_SAMPLES)
    )
    listed = list_risk_static_records(
        keyword=filters.get("keyword"),
        reference_label=filters.get("reference_label"),
        source=filters.get("source"),
        harm_category_L1=filters.get("harm_category_L1"),
        harm_category_L2=filters.get("harm_category_L2"),
        limit=list_limit,
        offset=0,
    )
    if not listed.get("available"):
        return {
            "available": False,
            "asset_id": None,
            "asset_name": None,
            "total_matched": 0,
            "sample_count": 0,
            "capped": False,
            "filters": filters,
            "samples": [],
            "source_refs": [],
            "evaluation_object": {},
            "evaluator": evaluator,
            "export_requested": export_requested,
        }

    records = listed.get("records") or []
    samples_by_id: dict[str, dict] = {}
    for record in records:
        text = str(record.get("text") or "")
        sample_id = str(record.get("sample_id") or "")
        source = str(record.get("source") or "")
        content_digest = sample_content_digest(text)
        samples_by_id[sample_id] = {
            "sample_id": sample_id,
            "text": text,
            "reference_label": str(record.get("reference_label") or ""),
            "harm_category_L1": str(record.get("harm_category_L1") or ""),
            "harm_category_L2": str(record.get("harm_category_L2") or ""),
            "source": source,
            "content_digest": content_digest,
            "source_revision": derive_source_revision(
                source, sample_id, content_digest
            ),
        }
    if requested_ids:
        missing = [sample_id for sample_id in requested_ids if sample_id not in samples_by_id]
        if missing:
            return {
                "available": False,
                "asset_id": None,
                "asset_name": None,
                "total_matched": 0,
                "sample_count": 0,
                "capped": False,
                "filters": filters,
                "samples": [],
                "source_refs": [],
                "evaluation_object": {},
                "evaluator": evaluator,
                "export_requested": export_requested,
            }
        samples = [samples_by_id[sample_id] for sample_id in requested_ids]
        total_matched = len(samples)
        capped = False
    else:
        safe_limit = min(max(int(params.limit), 1), RISK_RESCAN_MAX_SAMPLES)
        samples = list(samples_by_id.values())[:safe_limit]
        total_matched = int(listed.get("total") or 0)
        capped = total_matched > len(samples)
    return {
        "available": True,
        "asset_id": RISK_STATIC_ASSET_ID,
        "asset_name": RISK_STATIC_ASSET_NAME,
        "total_matched": total_matched,
        "sample_count": len(samples),
        "capped": capped,
        "filters": filters,
        "samples": samples,
        "source_refs": [
            {
                "ref_type": "risk_static_corpus",
                "ref_id": RISK_STATIC_ASSET_ID,
                "name": RISK_STATIC_ASSET_NAME,
                "source_repo": "",
                "source_commit": "",
            }
        ],
        "evaluation_object": build_dynbench400_evaluation_object(),
        "evaluator": evaluator,
        "export_requested": export_requested,
    }


async def execute_input_risk_rescan(scope: dict) -> dict:
    """Preflight the frozen evaluator, then run the bounded online detection.

    The v2 entry point. A failed preflight fails the run — never a fixture or
    mock completion. When a detection double is installed (tests / offline) and
    no explicit preflight checker is set, the network preflight is skipped."""
    evaluator = resolve_rescan_evaluator(scope.get("evaluator"))
    checker = get_risk_preflight_checker()
    # With a detection double installed (tests / offline) and no explicit
    # preflight checker, skip the network preflight; otherwise require the
    # selected Topic-2 evaluator to be healthy first.
    if checker is None and get_risk_detection_runner() is _topic2_detection_runner:
        checker = preflight_rescan_evaluator
    if checker is not None:
        preflight = await checker(evaluator)
        if not preflight.get("ok"):
            return {
                "status": "failed",
                "method": str(preflight.get("method") or evaluator),
                "evaluator": evaluator,
                "reason": (
                    "评估器不可用，输入风险语料在线二次检测未执行："
                    f"{evaluator_display_name(evaluator)}"
                    f"（{preflight.get('reason') or 'health check failed'}）。"
                ),
                "failure_phase": "preflight",
            }
    outcome = await execute_confirmed_rescan(scope, method=evaluator)
    return {**outcome, "evaluator": evaluator}


async def execute_confirmed_rescan(
    scope: dict, *, method: str | None = None
) -> dict:
    """Run the online detection for a confirmed, frozen scope.

    Returns one of: ``{"status": "completed", ...outcomes}``,
    ``{"status": "timeout", "reason": ...}`` or ``{"status": "failed", ...}``.
    Only the completed branch carries per-sample outcomes; the other two keep
    the task's status and reason instead of fabricating partial results.

    ``method`` is optional and used by DynBench to pin the Topic-2 evaluator.
    When the default runner is installed it is forwarded; test doubles that
    replace the runner keep the prior ``(texts)`` call shape."""
    samples = list(scope.get("samples") or [])
    texts = [str(sample.get("text") or "") for sample in samples]
    timeout_seconds = get_settings().governance_risk_rescan_timeout_seconds
    runner = get_risk_detection_runner()
    try:
        if method is not None and runner is _topic2_detection_runner:
            run = await asyncio.wait_for(
                _topic2_detection_runner(list(texts), method=method),
                timeout=timeout_seconds,
            )
        else:
            run = await asyncio.wait_for(runner(list(texts)), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "method": "",
            "reason": (
                f"在线二次检测超过 {timeout_seconds:g} 秒未返回，已停止等待；"
                "任务保留超时状态，可重试创建新任务。"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "method": "",
            "reason": f"在线二次检测服务调用失败（{exc.__class__.__name__}），未产生检测结果。",
        }

    if not run.ok:
        return {
            "status": "failed",
            "method": run.method,
            "reason": run.reason or "在线二次检测服务不可用，未产生检测结果。",
        }

    by_index = {item.source_index: item for item in run.items}
    outcomes: list[dict] = []
    for index, sample in enumerate(samples):
        reference = str(sample.get("reference_label") or "")
        item = by_index.get(index)
        detected = item.detected_label if item is not None else ""
        outcome = {
            "sample_id": str(sample.get("sample_id") or ""),
            "text": str(sample.get("text") or ""),
            "reference_label": reference,
            "source": str(sample.get("source") or ""),
            "content_digest": str(sample.get("content_digest") or ""),
            "source_revision": str(sample.get("source_revision") or ""),
        }
        if item is None or detected not in RISK_DETECTED_LABELS:
            outcome.update(
                {
                    "detected_label": "",
                    "status": "failed",
                    "reason": "在线服务未返回该样本的有效检测结果。",
                }
            )
        elif reference not in RISK_REFERENCE_LABELS:
            # A sample without a readable reference label cannot be judged for
            # agreement; calling it "不一致" would invent a disagreement.
            outcome.update(
                {
                    "detected_label": detected,
                    "status": "failed",
                    "reason": "样本缺少参考标注，无法判定是否一致。",
                }
            )
        else:
            status = "consistent" if detected == reference else "inconsistent"
            outcome.update(
                {"detected_label": detected, "status": status, "reason": item.detail}
            )
        outcomes.append(outcome)

    return {
        "status": "completed",
        "method": run.method,
        "samples": outcomes,
    }


def capability_version_from_scope(scope: dict) -> str:
    version = scope.get("capability_version")
    return str(version) if version else RISK_RESCAN_CAPABILITY_VERSION
