"""Create a completed, frozen review of the Topic 3 risk v6 prerun record (#90/#91)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.topic3.risk_evaluation import (
    BASELINE_MODEL_ID,
    PRIMARY_MODEL_ID,
    load_risk_review_evidence,
    load_v6_sample_rows,
)
from app.db.models import (
    BenchmarkAsset,
    GovernanceCompletionRecord,
    GovernanceMessage,
    GovernanceTask,
    utc_now,
)
from app.schemas.governance import (
    RISK_PRERUN_REVIEW_CAPABILITY,
    RISK_PRERUN_REVIEW_MESSAGE_KIND,
    GovernanceReportEnvelope,
    GovernanceReportStatus,
    RiskEvaluatorMetrics,
    RiskPrerunReviewReport,
    RiskReviewIssue,
    RiskReviewIssueLists,
)
from app.services.benchmark_topic3_risk_identity import SERIES_ID
from app.services.benchmark_topic3_risk_taxonomy_service import TOPIC3_RISK_CATEGORIES
from app.services.benchmark_topic3_risk_v6_service import (
    ASSET_ID as RISK_V6_OFFICIAL_ASSET_ID,
    RELEASE_KIND as RISK_V6_RELEASE_KIND,
)
from app.services.governance_product_metrics import emit_product_event
from app.services.governance_system_record_service import (
    build_risk_system_record_detail,
    get_risk_system_record_asset,
)

_TAXONOMY_TITLES: dict[str, str] = dict(TOPIC3_RISK_CATEGORIES)


CAPABILITY_VERSION = "v1"
# Test fixture id used by system-record tests; production id is ASSET_ID above.
RISK_V6_TEST_ASSET_ID = "topic3_risk_v6_benchmark"
SUPPORTED_RISK_REVIEW_ASSET_IDS = {
    RISK_V6_OFFICIAL_ASSET_ID,
    RISK_V6_TEST_ASSET_ID,
}
RISK_REVIEW_UNSUPPORTED_REASON = (
    "该记录不支持审阅：仅官方课题三风险分级分类 Benchmark v6/v7 系列资产"
    "可创建风险识别器审阅任务。"
)

DIMENSION_SUMMARIES = [
    {
        "key": "binary_safe_unsafe",
        "label": "二分类安全/风险",
        "description": "safe / unsafe 二分类识别指标（准确率、召回、误报等）。",
    },
    {
        "key": "risk_level",
        "label": "风险等级",
        "description": "风险等级（safe / low / medium / high）分层识别指标。",
    },
    {
        "key": "multilabel_c01_c17",
        "label": "C01-C17 多标签",
        "description": "C01–C17 风险类别多标签识别（micro/macro F1 与分类别指标）。",
    },
    {
        "key": "asset_integrity",
        "label": "资产完整性",
        "description": "评测包文件、样本数与资产哈希一致性校验，不构成综合安全分。",
    },
]

_CATEGORY_RE = re.compile(r"C(0[1-9]|1[0-7])")
HIGH_RISK_LEVELS = frozenset({"medium", "high"})
EXCERPT_MAX_LEN = 48
SENSITIVITY_BOUNDARY = (
    "restricted benchmark asset：导出与冻结问题清单不得包含高风险样本的完整 prompt/response；"
    "仅允许稳定样本 ID、参考标签、V7 预测、差异类型、问题证据状态与脱敏/截断摘录。"
)


def _mask_excerpt(text: str, *, max_len: int = EXCERPT_MAX_LEN) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return (cleaned[:2] + "…") if len(cleaned) > 2 else "…"
    if len(cleaned) <= max_len:
        return cleaned[:4] + "…" + cleaned[-4:]
    half = max_len // 2
    return cleaned[:half] + "…" + cleaned[-half:]


def collect_forbidden_snippets(samples: list[dict[str, Any]]) -> list[str]:
    """In-memory prompt/response strings that must never appear in freeze/export."""
    snippets: list[str] = []
    seen: set[str] = set()
    for sample in samples:
        for key in ("prompt", "response"):
            value = str(sample.get(key) or "").strip()
            if len(value) < 12 or value in seen:
                continue
            seen.add(value)
            snippets.append(value)
    return snippets


def forbidden_text_sha256_list(snippets: list[str]) -> list[str]:
    return sorted(
        {
            hashlib.sha256(snippet.encode("utf-8")).hexdigest()
            for snippet in snippets
            if snippet
        }
    )


def assert_no_sensitive_plaintext(
    payload: Any, forbidden_snippets: list[str], *, context: str = "risk review"
) -> None:
    """Fail create/export if any live high-risk prompt/response leaked into JSON."""
    if isinstance(payload, dict) and all(isinstance(v, str) for v in payload.values()):
        blob = "\n".join(payload.values())
    elif isinstance(payload, str):
        blob = payload
    else:
        blob = json.dumps(payload, ensure_ascii=False)
    for snippet in forbidden_snippets:
        if snippet and snippet in blob:
            raise RiskReviewEvidenceError(
                f"{context} must not include full high-risk prompt/response"
            )


def _is_pred_safe(pred: dict[str, Any]) -> bool:
    safe_type = str(pred.get("predicted_safe_type") or "").lower()
    level = str(pred.get("predicted_risk_level") or "").lower()
    if safe_type == "safe" or level == "safe":
        return True
    if safe_type == "unsafe" or level in {"low", "medium", "high"}:
        return False
    return safe_type != "unsafe"


def _is_gold_safe(sample: dict[str, Any]) -> bool:
    return str(sample.get("response_safetype") or "").lower() == "safe"


def _category_titles_for_sample(sample: dict[str, Any]) -> list[str]:
    """Gold category titles from taxonomy + optional sample-provided labels."""
    titles: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        cleaned = " ".join(str(value or "").split()).strip()
        if len(cleaned) < 2:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        titles.append(cleaned)

    for code in sample.get("category_codes") or []:
        taxonomy_title = _TAXONOMY_TITLES.get(str(code) or "")
        if taxonomy_title:
            _add(taxonomy_title)
            _add(taxonomy_title.split("、")[0])
    for raw in sample.get("category_titles") or []:
        _add(str(raw))
    return titles


def _reason_aligned_with_categories(
    reason: str,
    codes: list[str],
    titles: list[str] | None = None,
) -> bool:
    """True when non-empty reason mentions a gold C-code or category title.

    When gold has category codes, a non-empty reason that shares neither gold
    C-codes nor titles is misaligned (标注理由与参考类别错位), even if it
    contains no foreign C-code at all.
    """
    cleaned = str(reason or "").strip()
    if not cleaned:
        return False
    if not codes:
        return True
    gold_codes = {str(code) for code in codes}
    reason_codes = {f"C{code}" for code in _CATEGORY_RE.findall(cleaned)}
    if reason_codes & gold_codes:
        return True
    reason_folded = cleaned.casefold()
    for title in titles or []:
        token = str(title or "").strip()
        if len(token) >= 2 and token.casefold() in reason_folded:
            return True
    return False


def _sample_integrity_flags(sample: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (code, message) integrity defects for one gold sample."""
    flags: list[tuple[str, str]] = []
    sample_id = str(sample.get("sample_id") or "")
    reason = str(sample.get("label_reason") or "").strip()
    codes = list(sample.get("category_codes") or [])
    titles = _category_titles_for_sample(sample)
    if not reason:
        flags.append(
            (
                "missing_label_reason",
                f"样本 {sample_id or '—'} 缺少 label_reason，无法确认参考依据。",
            )
        )
    elif not _reason_aligned_with_categories(reason, codes, titles):
        flags.append(
            (
                "misaligned_label_reason",
                f"样本 {sample_id or '—'} 的 label_reason 与参考类别不一致。",
            )
        )
    label_source = str(sample.get("label_source") or "").strip()
    source_index = str(sample.get("source_index") or "").strip()
    if not label_source or not source_index:
        flags.append(
            (
                "incomplete_provenance",
                f"样本 {sample_id or '—'} 缺少完整来源血缘（label_source / source_index）。",
            )
        )
    return flags


def _recognition_categories(
    sample: dict[str, Any], pred: dict[str, Any]
) -> list[str]:
    """Classify V7 vs gold recognition diffs; Base is never consulted."""
    gold_safe = _is_gold_safe(sample)
    pred_safe = _is_pred_safe(pred)
    categories: list[str] = []
    if (not gold_safe) and pred_safe:
        categories.append("miss")
    elif gold_safe and (not pred_safe):
        categories.append("false_positive")
    elif (not gold_safe) and (not pred_safe):
        gold_level = str(sample.get("risk_level_id") or "").lower()
        pred_level = str(pred.get("predicted_risk_level") or "").lower()
        if gold_level and pred_level and gold_level != pred_level:
            categories.append("level_mismatch")
        gold_cats = set(sample.get("category_codes") or [])
        pred_cats = set(pred.get("predicted_category_codes") or [])
        if gold_cats - pred_cats:
            categories.append("category_miss")
        if pred_cats - gold_cats:
            categories.append("category_over_predict")
    return categories


def _judgment_for_recognition(category: str, sample_id: str) -> str:
    labels = {
        "miss": "参考为风险，V7 预测为安全（漏检）",
        "false_positive": "参考为安全，V7 预测为风险（误报）",
        "level_mismatch": "二分类一致但风险等级与参考不一致",
        "category_miss": "参考风险类别未被 V7 预测覆盖",
        "category_over_predict": "V7 预测了参考中不存在的风险类别",
    }
    return f"样本 {sample_id}：{labels.get(category, category)}"


def _build_risk_issue_lists(
    *,
    samples: list[dict[str, Any]],
    v7_predictions: list[dict[str, Any]],
    package_warnings: list[dict[str, Any]],
) -> RiskReviewIssueLists:
    """Split recognition differences from asset integrity problems (#91).

    Base predictions are never included. When reference evidence conflicts or
    is missing, recognition findings are demoted to pending-human-confirmation
    (never confirmed-difference asserting V7 is wrong).
    """
    integrity: list[RiskReviewIssue] = []
    conflicted_samples: set[str] = set()

    for index, warning in enumerate(package_warnings):
        integrity.append(
            RiskReviewIssue(
                issue_id=f"integrity-{index + 1}-{warning.get('code') or 'warning'}",
                list_kind="integrity",
                category=str(warning.get("code") or "integrity_warning"),
                sample_id=str(warning.get("sample_id") or ""),
                evidence_state="pending-human-confirmation",
                judgment=str(warning.get("message") or ""),
                evidence={
                    key: value
                    for key, value in warning.items()
                    if key not in {"code", "message"}
                },
                source_refs=[],
            )
        )

    sample_by_id = {
        str(item.get("sample_id") or ""): item
        for item in samples
        if str(item.get("sample_id") or "")
    }
    misaligned_samples: set[str] = set()
    for sample in samples:
        sample_id = str(sample.get("sample_id") or "")
        flags = _sample_integrity_flags(sample)
        misaligned = any(code == "misaligned_label_reason" for code, _message in flags)
        if misaligned:
            misaligned_samples.add(sample_id)
        for code, message in flags:
            conflicted_samples.add(sample_id)
            integrity.append(
                RiskReviewIssue(
                    issue_id=f"integrity-{len(integrity) + 1}-{code}",
                    list_kind="integrity",
                    category=code,
                    sample_id=sample_id,
                    evidence_state="pending-human-confirmation",
                    judgment=message,
                    ref_labels={
                        "safe_type": sample.get("response_safetype") or "",
                        "risk_level_id": sample.get("risk_level_id") or "",
                        "category_codes": list(sample.get("category_codes") or []),
                    },
                    excerpt_masked=(
                        ""
                        if misaligned
                        else _mask_excerpt(str(sample.get("label_reason") or ""))
                    ),
                    evidence={
                        "label_source": sample.get("label_source") or "",
                        "source_index": sample.get("source_index") or "",
                    },
                    source_refs=[
                        {
                            "ref_type": "frozen_sample",
                            "ref_id": sample_id,
                            "name": sample_id,
                        }
                    ],
                )
            )

    if samples and not sample_by_id:
        integrity.append(
            RiskReviewIssue(
                issue_id=f"integrity-{len(integrity) + 1}-incomplete_provenance",
                list_kind="integrity",
                category="incomplete_provenance",
                evidence_state="pending-human-confirmation",
                judgment="资产样本缺少可用 sample_id，无法完成参考标签对齐。",
            )
        )

    recognition: list[RiskReviewIssue] = []
    recognition_index = 0
    for pred in v7_predictions:
        sample_id = str(pred.get("sample_id") or "")
        sample = sample_by_id.get(sample_id)
        if sample is None:
            continue
        for category in _recognition_categories(sample, pred):
            recognition_index += 1
            pending = sample_id in conflicted_samples
            evidence_state = (
                "pending-human-confirmation"
                if pending
                else "confirmed-difference"
            )
            level = str(sample.get("risk_level_id") or "").lower()
            reason = str(sample.get("label_reason") or "")
            # Conflicting reasons stay out of automatic explanation excerpts.
            # The integrity judgment may still say the categories disagree.
            if sample_id in misaligned_samples or not reason:
                excerpt = ""
            elif level in HIGH_RISK_LEVELS:
                excerpt = _mask_excerpt(reason, max_len=24)
            else:
                excerpt = _mask_excerpt(reason)
            recognition.append(
                RiskReviewIssue(
                    issue_id=f"recognition-{recognition_index}-{category}",
                    list_kind="recognition",
                    category=category,
                    sample_id=sample_id,
                    evidence_state=evidence_state,
                    judgment=_judgment_for_recognition(category, sample_id),
                    ref_labels={
                        "safe_type": sample.get("response_safetype") or "",
                        "risk_level_id": sample.get("risk_level_id") or "",
                        "category_codes": list(sample.get("category_codes") or []),
                    },
                    v7_prediction={
                        "safe_type": pred.get("predicted_safe_type") or "",
                        "risk_level": pred.get("predicted_risk_level") or "",
                        "category_codes": list(
                            pred.get("predicted_category_codes") or []
                        ),
                    },
                    excerpt_masked=excerpt,
                    evidence={"evaluator_role": "primary", "model_id": PRIMARY_MODEL_ID},
                    source_refs=[
                        {
                            "ref_type": "frozen_sample",
                            "ref_id": sample_id,
                            "name": sample_id,
                        }
                    ],
                )
            )

    return RiskReviewIssueLists(recognition=recognition, integrity=integrity)


class RiskReviewNotFoundError(ValueError):
    pass


class RiskReviewConflictError(ValueError):
    pass


class RiskReviewEvidenceError(ValueError):
    pass


def _manifest_dict(asset: BenchmarkAsset) -> dict[str, Any]:
    try:
        payload = json.loads(asset.manifest_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def risk_review_support_fields(asset: BenchmarkAsset) -> dict[str, Any]:
    """Return review_supported for official v6/v7 series risk records."""
    from app.services.governance_system_record_service import _is_risk_record

    manifest = _manifest_dict(asset)
    if not _is_risk_record(asset, manifest):
        return {
            "review_supported": False,
            "review_unavailable_reason": RISK_REVIEW_UNSUPPORTED_REASON,
        }
    release_ok = manifest.get("release_kind") == RISK_V6_RELEASE_KIND
    series_ok = manifest.get("series_id") == SERIES_ID
    id_ok = asset.asset_id in SUPPORTED_RISK_REVIEW_ASSET_IDS
    if release_ok or series_ok or id_ok:
        return {
            "review_supported": True,
            "review_unavailable_reason": "",
        }
    return {
        "review_supported": False,
        "review_unavailable_reason": RISK_REVIEW_UNSUPPORTED_REASON,
    }


def _warning(code: str, message: str, **facts: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **facts}


def _integrity_warnings(
    *,
    detail: dict[str, Any],
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    primary = evidence.get("primary") or {}
    baseline = evidence.get("baseline") or {}

    if not primary:
        warnings.append(
            _warning(
                "missing_primary_evaluator",
                f"缺少 V7 正式评测包（model_id={PRIMARY_MODEL_ID}）。",
            )
        )
    if not baseline:
        warnings.append(
            _warning(
                "missing_baseline_evaluator",
                f"缺少 Base 基线评测包（model_id={BASELINE_MODEL_ID}）。",
            )
        )

    sample_count = int((detail.get("dataset") or {}).get("sample_count") or 0)
    for role_name, package in (("primary", primary), ("baseline", baseline)):
        if not package:
            continue
        predictions_count = int(package.get("predictions_count") or 0)
        if sample_count and predictions_count != sample_count:
            warnings.append(
                _warning(
                    "predictions_count_mismatch",
                    (
                        f"{role_name} 预测条数 {predictions_count} "
                        f"与资产样本数 {sample_count} 不一致。"
                    ),
                    role=role_name,
                    expected=sample_count,
                    actual=predictions_count,
                )
            )
        metrics_keys = package.get("metrics_keys_present") or []
        if not metrics_keys:
            warnings.append(
                _warning(
                    "missing_metrics_file",
                    f"{role_name} 评测包缺少可用 metrics。",
                    role=role_name,
                )
            )
        if not package.get("report_present"):
            warnings.append(
                _warning(
                    "missing_report_file",
                    f"{role_name} 评测包缺少 report.md。",
                    role=role_name,
                )
            )
        package_sha = str(package.get("asset_sha256") or "")
        asset_sha = str(detail.get("asset_sha256") or "")
        if package_sha and asset_sha and package_sha != asset_sha:
            warnings.append(
                _warning(
                    "asset_sha256_drift",
                    f"{role_name} 评测包 asset_sha256 与资产登记值不一致。",
                    role=role_name,
                    package_sha256=package_sha,
                    asset_sha256=asset_sha,
                )
            )

    if primary.get("model_id") and primary.get("model_id") != PRIMARY_MODEL_ID:
        warnings.append(
            _warning(
                "primary_model_id_unexpected",
                f"正式摘要模型应为 {PRIMARY_MODEL_ID}，实际为 {primary.get('model_id')}。",
            )
        )
    if baseline.get("model_id") and baseline.get("model_id") != BASELINE_MODEL_ID:
        warnings.append(
            _warning(
                "baseline_model_id_unexpected",
                f"基线对照模型应为 {BASELINE_MODEL_ID}，实际为 {baseline.get('model_id')}。",
            )
        )
    return warnings


def _reference_sample_warnings(
    *,
    samples: list[dict[str, Any]],
    primary: dict[str, Any],
) -> list[dict[str, Any]]:
    """Without gold rows joined to every V7 prediction, an empty recognition
    list means "not compared", never "no differences"."""
    predictions = list(primary.get("prediction_rows") or [])
    if not predictions:
        return []
    if not samples:
        return [
            _warning(
                "missing_reference_samples",
                "资产缺少可读取的参考样本文件，V7 预测无法与参考标签对齐，识别差异未计算。",
            )
        ]
    gold_ids = {
        str(sample.get("sample_id") or "") for sample in samples
    } - {""}
    aligned = sum(
        1 for pred in predictions if str(pred.get("sample_id") or "") in gold_ids
    )
    if aligned < len(predictions):
        return [
            _warning(
                "reference_samples_unaligned",
                (
                    f"V7 预测 {len(predictions)} 条中仅 {aligned} 条能与参考样本对齐，"
                    "未对齐样本的识别差异未计算。"
                ),
                expected=len(predictions),
                actual=aligned,
            )
        ]
    return []


def _evaluator_from_package(
    package: dict[str, Any], role: Literal["primary", "baseline"]
) -> RiskEvaluatorMetrics:
    return RiskEvaluatorMetrics(
        role=role,
        model_id=str(package.get("model_id") or ""),
        model_version=str(package.get("model_version") or ""),
        display_name=str(package.get("display_name") or ""),
        run_id=str(package.get("run_id") or ""),
        evaluated_at=str(package.get("evaluated_at") or ""),
        predictions_count=int(package.get("predictions_count") or 0),
        binary_metrics=dict(package.get("binary_metrics") or {}),
        level_metrics=dict(package.get("level_metrics") or {}),
        multilabel_metrics=dict(package.get("multilabel_metrics") or {}),
        primary_metrics=dict(package.get("primary_metrics") or {}),
        supporting_metrics=dict(package.get("supporting_metrics") or {}),
        per_category_metrics=dict(package.get("per_category_metrics") or {}),
    )


def _run_identity(
    evidence: dict[str, Any], benchmark_version: str = "v6"
) -> dict[str, Any]:
    primary = evidence.get("primary") or {}
    baseline = evidence.get("baseline") or {}
    return {
        "benchmark_version": benchmark_version,
        "primary": {
            "role": "primary",
            "model_id": primary.get("model_id"),
            "model_version": primary.get("model_version"),
            "display_name": primary.get("display_name"),
            "run_id": primary.get("run_id"),
            "evaluated_at": primary.get("evaluated_at"),
        },
        "baseline": {
            "role": "baseline",
            "model_id": baseline.get("model_id"),
            "model_version": baseline.get("model_version"),
            "display_name": baseline.get("display_name"),
            "run_id": baseline.get("run_id"),
            "evaluated_at": baseline.get("evaluated_at"),
        },
    }


def build_risk_review_report(
    *,
    task_id: str,
    asset: BenchmarkAsset,
    detail: dict[str, Any],
    evidence: dict[str, Any],
    completed_at: str,
    samples: list[dict[str, Any]] | None = None,
    forbidden_text_sha256: list[str] | None = None,
    benchmark_version: str = "v6",
) -> RiskPrerunReviewReport:
    sample_rows = list(samples if samples is not None else load_v6_sample_rows(asset))
    primary = evidence["primary"]
    baseline = evidence["baseline"]
    warnings = _integrity_warnings(detail=detail, evidence=evidence)
    warnings.extend(_reference_sample_warnings(samples=sample_rows, primary=primary))
    # prediction_rows are used only to build issue_lists at create time; they are
    # not copied into frozen_evidence once issue_lists exist on the report.
    issue_lists = _build_risk_issue_lists(
        samples=sample_rows,
        v7_predictions=list(primary.get("prediction_rows") or []),
        package_warnings=warnings,
    )
    # Sample-level integrity defects also affect delivery readiness.
    sample_integrity_n = sum(
        1
        for item in issue_lists.integrity
        if item.category
        in {
            "missing_label_reason",
            "misaligned_label_reason",
            "incomplete_provenance",
        }
    )
    integrity_code = "passed" if not warnings and sample_integrity_n == 0 else "warning"
    delivery_ready = integrity_code == "passed"
    sample_count = int((detail.get("dataset") or {}).get("sample_count") or 0)

    envelope = GovernanceReportEnvelope(
        evaluated_object={
            "record_id": detail["record_id"],
            "record_name": detail["name"],
            "record_version": detail["record_version"],
            "dataset_id": detail["record_id"],
            "dataset_label": detail["name"],
            "sample_count": sample_count,
            "benchmark_version": benchmark_version,
            "taxonomy_schema": (detail.get("dataset") or {}).get("taxonomy_schema")
            or "C01-C17",
            "disclosure_level": "restricted",
        },
        source_identity={
            "source_repo": detail["source_repo"],
            "source_commit": detail["source_commit"],
            "asset_sha256": detail["asset_sha256"],
            "benchmark_version": benchmark_version,
            "evidence_files": evidence.get("files") or [],
        },
        run_identity=_run_identity(evidence, benchmark_version),
        evaluation_run_status=GovernanceReportStatus(
            code="completed",
            label="来源评测已完成",
            detail="审阅读取既有 V7 / Base 静态导入结果，没有重新运行模型。",
        ),
        integrity_status=GovernanceReportStatus(
            code=integrity_code,
            label="完整性通过" if integrity_code == "passed" else "存在完整性告警",
            detail=(
                f"包级告警 {len(warnings)} 条，样本级完整性问题 {sample_integrity_n} 条；"
                "告警不会改写来源指标。"
            ),
        ),
        delivery_readiness=GovernanceReportStatus(
            code="ready" if delivery_ready else "not_ready",
            label="可交付" if delivery_ready else "暂不可作为可保留交付结论",
            detail="交付准备度由证据完整性独立决定，与审阅任务是否完成无关。",
        ),
        review_task_status=GovernanceReportStatus(
            code="completed", label="审阅任务已完成"
        ),
        claim_boundaries=[
            f"本报告验证风险识别器在 {benchmark_version} 基准上的四维表现，"
            "不是对生成模型整体安全性的评价。",
            "不以综合安全分汇总或排名；正式摘要与问题清单仅采用 V7 指标。",
            "Base（qwen3.5-9B-base）仅作为基线对照段落，不得进入正式问题清单或与 V7 静默合并。",
            "不评价生成模型的内容质量、事实正确性或合规处置能力。",
            SENSITIVITY_BOUNDARY,
        ],
        limitations=[
            "来源指标由上游评测包产生，平台仅保留并验证证据一致性。",
            "完整性告警不触发重新评测，也不修改底层 evaluation_status。",
            "本任务不重新调用 Topic3 在线服务或风险识别模型。",
            "参考证据缺失或冲突时，识别差异仅标记为待人工确认，不宣称 V7 判定错误。",
        ],
    )

    source_refs = list(detail.get("source_refs") or [])
    source_refs.extend(
        {
            "ref_type": "risk_evaluation_evidence",
            "ref_id": str(item.get("sha256") or ""),
            "name": str(item.get("path") or item.get("role") or ""),
            "source_repo": detail.get("source_repo") or "",
            "source_commit": detail.get("source_commit") or "",
        }
        for item in evidence.get("files") or []
    )

    # Freeze evaluator identity / shas / counts / sample_ids for restore identity.
    # Do NOT freeze full v6 gold join or V7 prediction_rows — issue_lists on the
    # report already carry redacted recognition/integrity facts for export.
    digests = list(forbidden_text_sha256 or [])
    if not digests:
        digests = forbidden_text_sha256_list(collect_forbidden_snippets(sample_rows))
    frozen_evidence = {
        "benchmark_version": benchmark_version,
        "sample_count": sample_count,
        "disclosure_level": "restricted",
        "sensitivity_boundary": SENSITIVITY_BOUNDARY,
        "forbidden_text_sha256": digests,
        "asset": {
            "asset_id": detail["record_id"],
            "asset_version": benchmark_version,
            "asset_sha256": detail["asset_sha256"],
        },
        "evaluation_runs": {
            "primary": primary.get("run_id"),
            "baseline": baseline.get("run_id"),
        },
        "primary": {
            "model_id": primary.get("model_id"),
            "run_id": primary.get("run_id"),
            "predictions_count": primary.get("predictions_count"),
            "sample_ids": list(primary.get("sample_ids") or []),
            "prediction_row_sha256": list(primary.get("prediction_row_sha256") or []),
            "asset_sha256": primary.get("asset_sha256"),
        },
        "baseline": {
            "model_id": baseline.get("model_id"),
            "run_id": baseline.get("run_id"),
            "predictions_count": baseline.get("predictions_count"),
            "sample_ids": list(baseline.get("sample_ids") or []),
            "prediction_row_sha256": list(baseline.get("prediction_row_sha256") or []),
            "asset_sha256": baseline.get("asset_sha256"),
        },
        "evidence_files": evidence.get("files") or [],
    }

    return RiskPrerunReviewReport(
        task_id=task_id,
        envelope=envelope,
        primary_evaluator=_evaluator_from_package(primary, "primary"),
        baseline_evaluator=_evaluator_from_package(baseline, "baseline"),
        dimension_summaries=list(DIMENSION_SUMMARIES),
        integrity_warnings=warnings,
        issue_lists=issue_lists,
        frozen_evidence=frozen_evidence,
        source_refs=source_refs,
        completed_at=completed_at,
    )


async def create_risk_prerun_review(
    db: AsyncSession,
    *,
    client_id: str,
    session: Any,
    record_id: str,
    record_version: str,
) -> dict[str, Any]:
    if session.domain != "output":
        raise RiskReviewConflictError("风险预跑审阅任务只能在输出内容治理会话创建")
    asset = await get_risk_system_record_asset(db, record_id)
    if asset is None:
        raise RiskReviewNotFoundError("风险安全系统预跑记录不存在")
    detail = await build_risk_system_record_detail(db, asset)
    if detail["record_version"] != record_version:
        raise RiskReviewConflictError("来源记录版本已变化，请刷新详情后重新创建审阅任务")
    support = risk_review_support_fields(asset)
    if not support.get("review_supported"):
        raise RiskReviewConflictError(
            support.get("review_unavailable_reason") or RISK_REVIEW_UNSUPPORTED_REASON
        )
    try:
        evidence = load_risk_review_evidence(asset)
        samples = load_v6_sample_rows(asset)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise RiskReviewEvidenceError(f"风险预跑评测证据不可用：{error}") from error

    forbidden_snippets = collect_forbidden_snippets(samples)
    forbidden_digests = forbidden_text_sha256_list(forbidden_snippets)

    now = utc_now()
    task_id = str(uuid4())
    completed_at = now.isoformat() + "Z"
    report = build_risk_review_report(
        task_id=task_id,
        asset=asset,
        detail=detail,
        evidence=evidence,
        completed_at=completed_at,
        samples=samples,
        forbidden_text_sha256=forbidden_digests,
        benchmark_version=str(detail.get("asset_version") or "v6"),
    )
    snapshot = report.model_dump()
    # Create-time redaction gate: scan frozen snapshot before persist.
    assert_no_sensitive_plaintext(
        snapshot, forbidden_snippets, context="risk prerun review freeze"
    )
    # Dry-run export builders so a poisoned issue_lists/excerpt cannot land.
    from app.services.governance_risk_export_service import build_risk_evidence_pack

    try:
        build_risk_evidence_pack(snapshot, forbidden_snippets=forbidden_snippets)
    except ValueError as error:
        raise RiskReviewEvidenceError(str(error)) from error
    task = GovernanceTask(
        task_id=task_id,
        client_id=client_id,
        session_id=session.session_id,
        capability=RISK_PRERUN_REVIEW_CAPABILITY,
        parameters_json=json.dumps(
            {"record_id": record_id, "record_version": record_version},
            ensure_ascii=False,
        ),
        status="completed",
        provider="static_prerun_review",
        model="",
        latency_ms=0,
        parse_status="not_applicable",
        created_at=now,
        finished_at=now,
    )
    message = GovernanceMessage(
        session_id=session.session_id,
        client_id=client_id,
        request_id=str(uuid4()),
        role="assistant",
        kind=RISK_PRERUN_REVIEW_MESSAGE_KIND,
        content=report.render_content(),
        payload_json=json.dumps(snapshot, ensure_ascii=False),
        created_at=now,
    )
    session.updated_at = now
    db.add(task)
    db.add(message)
    await db.flush()
    db.add(
        GovernanceCompletionRecord(
            completion_id=str(uuid4()),
            task_id=task_id,
            session_id=session.session_id,
            message_id=message.id,
            capability=RISK_PRERUN_REVIEW_CAPABILITY,
            capability_version=CAPABILITY_VERSION,
            result_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
            source_refs_json=json.dumps(snapshot["source_refs"], ensure_ascii=False),
            completed_at=now,
        )
    )
    await emit_product_event(
        db,
        "task_completed",
        session_id=session.session_id,
        task_id=task_id,
        attributes={
            "domain": "output",
            "capability": RISK_PRERUN_REVIEW_CAPABILITY,
            "status": "completed",
            "provider": "static_prerun_review",
        },
        occurred_at=now,
    )
    await db.commit()
    return snapshot
