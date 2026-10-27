"""Presentation of topic3 risk evaluator metrics: primary metric catalog,
supporting metrics and model display names."""

from __future__ import annotations

from typing import Any


PRIMARY_METRICS = [
    {
        "key": "risk_class_accuracy_v4_first_label",
        "display_name": "风险内容分层识别准确率",
    },
    {
        "key": "risk_recall",
        "display_name": "风险内容合规预警覆盖率",
    },
    {
        "key": "risk_false_positive_rate",
        "display_name": "风险内容误报率",
    },
]

SUPPORTING_METRIC_KEYS = [
    "accuracy_safe_unsafe",
    "precision_safe_unsafe",
    "recall_safe_unsafe",
    "f1_safe_unsafe",
    "risk_false_positive_count",
    "tp",
    "tn",
    "fp",
    "fn",
    "risk_severity_accuracy",
    "level_accuracy_total",
    "micro_f1",
    "macro_f1",
]


def primary_metric_values(metrics: dict[str, Any]) -> dict[str, Any]:
    return {metric["key"]: metrics.get(metric["key"]) for metric in PRIMARY_METRICS}


def supporting_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: metrics.get(key) for key in SUPPORTING_METRIC_KEYS}


def model_display_name(entry: dict[str, Any]) -> str:
    if entry.get("model_id") == "qwen3.5-9B-V7":
        return "课题三当前风险识别算法（Qwen3.5-9B-V7）"
    if entry.get("model_id") == "qwen3.5-9B-base":
        return "Qwen3.5-9B Base 基线"
    return str(entry.get("model_name") or entry.get("model_id") or "unknown")
