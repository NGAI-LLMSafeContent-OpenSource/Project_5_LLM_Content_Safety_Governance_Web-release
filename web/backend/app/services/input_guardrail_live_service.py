"""Input guardrail live-run orchestration for small demo batches."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.data_input import InputGuardrailLiveRunItem, Topic2RiskScanItem
from app.services.data_input_topic2_service import run_topic2_keyword_detection

PACKS_DIR = Path(__file__).resolve().parents[2] / "data" / "input_guardrail_packs"
DEFAULT_PACK_ID = "demo-mixed-10"
DEFAULT_MAX_SAMPLES = 10
MIN_SAMPLES = 5
MAX_SAMPLES = 10

TERMINAL_STATUSES = {"finished", "partial", "error"}
_jobs: dict[str, dict[str, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


class InputGuardrailLiveRunError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _lock_for(job_id: str) -> asyncio.Lock:
    lock = _locks.get(job_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[job_id] = lock
    return lock


def load_pack(pack_id: str) -> dict[str, Any]:
    path = PACKS_DIR / f"{pack_id}.json"
    if not path.is_file():
        raise InputGuardrailLiveRunError(400, f"输入护栏演示包不存在: {pack_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputGuardrailLiveRunError(400, f"输入护栏演示包无法读取: {pack_id}") from exc
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise InputGuardrailLiveRunError(400, f"输入护栏演示包缺少 samples: {pack_id}")
    return {
        "pack_id": str(data.get("pack_id") or pack_id),
        "title": str(data.get("title") or pack_id),
        "language": str(data.get("language") or "zh"),
        "mode": str(data.get("mode") or "demo_adapter"),
        "description": str(data.get("description") or ""),
        "samples": samples,
    }


def list_demo_packs() -> list[dict[str, Any]]:
    if not PACKS_DIR.is_dir():
        return []
    packs: list[dict[str, Any]] = []
    for path in sorted(PACKS_DIR.glob("*.json")):
        try:
            pack = load_pack(path.stem)
        except InputGuardrailLiveRunError:
            continue
        packs.append(
            {
                "pack_id": pack["pack_id"],
                "title": pack["title"],
                "language": pack["language"],
                "mode": pack["mode"],
                "sample_count": len(pack["samples"]),
                "description": pack["description"],
            }
        )
    return packs


async def start_live_run(
    *,
    pack_id: str = DEFAULT_PACK_ID,
    items: list[InputGuardrailLiveRunItem] | None = None,
    max_samples: int | None = None,
) -> dict[str, Any]:
    selected = _select_items(pack_id=pack_id, items=items or [], max_samples=max_samples)
    job_id = f"iglive_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": job_id,
        "pack_id": pack_id if not items else "custom",
        "status": "pending",
        "source": "live",
        "mode": "demo_adapter",
        "service_status": {},
        "progress": {"detect_done": 0, "detect_total": len(selected)},
        "samples": [_empty_sample(item, index) for index, item in enumerate(selected)],
        "created_at": now,
        "finished_at": None,
    }
    _jobs[job_id] = job
    asyncio.create_task(_run_job(job_id))
    return {
        "job_id": job_id,
        "pack_id": job["pack_id"],
        "status": job["status"],
        "source": job["source"],
        "mode": job["mode"],
        "sample_count": len(selected),
        "created_at": now,
    }


async def get_live_run(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise InputGuardrailLiveRunError(404, "输入护栏 live run 不存在")
    return job


def _select_items(
    *,
    pack_id: str,
    items: list[InputGuardrailLiveRunItem],
    max_samples: int | None,
) -> list[dict[str, Any]]:
    limit = min(max(max_samples or DEFAULT_MAX_SAMPLES, MIN_SAMPLES), MAX_SAMPLES)
    if items:
        selected = [item.model_dump() for item in items if item.text.strip()][:limit]
        if len(selected) < MIN_SAMPLES:
            raise InputGuardrailLiveRunError(400, f"自定义语料至少需要 {MIN_SAMPLES} 条")
        return selected
    pack = load_pack(pack_id or DEFAULT_PACK_ID)
    selected = [item for item in pack["samples"] if isinstance(item, dict) and item.get("text")][
        :limit
    ]
    if len(selected) < MIN_SAMPLES:
        raise InputGuardrailLiveRunError(400, f"输入护栏演示包有效样本不足 {MIN_SAMPLES} 条")
    return selected


def _empty_sample(raw: dict[str, Any], index: int) -> dict[str, Any]:
    sample_id = str(raw.get("id") or f"sample-{index + 1:03d}")
    return {
        "id": sample_id,
        "text": str(raw.get("text") or ""),
        "demo_category": str(raw.get("demo_category") or ""),
        "language": str(raw.get("language") or ""),
        "track": str(raw.get("track") or "general"),
        "domain": str(raw.get("domain") or ""),
        "source_asset_id": str(raw.get("source_asset_id") or ""),
        "source_file": str(raw.get("source_file") or ""),
        "source_sample_id": str(raw.get("source_sample_id") or sample_id),
        "source_label": str(raw.get("source_label") or ""),
        "source_name": str(raw.get("source_name") or ""),
        "ethnic_group": str(raw.get("ethnic_group") or ""),
        "difficulty_level": str(raw.get("difficulty_level") or ""),
        "background_type": str(raw.get("background_type") or ""),
        "cultural_knowledge_points": raw.get("cultural_knowledge_points") or [],
        "expected_issue": str(raw.get("expected_issue") or ""),
        "expected_disposition": str(raw.get("expected_disposition") or ""),
        "demo_note": str(raw.get("demo_note") or ""),
        "value_dimension": raw.get("value_dimension") or None,
        "culture_dimension": raw.get("culture_dimension") or None,
        "detect_status": "pending",
        "value_result": {},
        "risk_result": {},
        "lineage_result": {},
        "evidence": [],
        "fix_suggestion": "",
        "disposition": "",
        "error": None,
    }


async def _run_job(job_id: str) -> None:
    try:
        await _mutate(job_id, lambda job: job.update({"status": "running"}))
        risk_predictions, risk_service_status = await _run_risk_track(job_id)
        await _mutate(
            job_id,
            lambda job: job.update({"service_status": {"risk": risk_service_status}}),
        )
        job = _jobs.get(job_id)
        if job is None:
            return
        for index, sample in enumerate(job["samples"]):
            await _mutate(
                job_id,
                lambda current, i=index: current["samples"][i].update({"detect_status": "running"}),
            )
            result = _evaluate_sample(sample, risk_predictions.get(sample["id"]))
            await _mutate(job_id, lambda current, i=index, data=result: _finish_sample(current, i, data))
        await _mutate(job_id, _finish_job)
    except Exception as exc:  # pragma: no cover - defensive task boundary
        await _mutate(
            job_id,
            lambda job: job.update(
                {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "service_status": {"error": str(exc)},
                }
            ),
        )


async def _run_risk_track(job_id: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    job = _jobs.get(job_id) or {}
    risk_samples = [sample for sample in job.get("samples", []) if sample.get("track") == "risk"]
    if not risk_samples:
        return {}, {"connected": True, "mode": "not_required", "message": "本批无风险轨样本。"}
    scan_items = [
        Topic2RiskScanItem(
            text=sample["text"],
            lineage_node_id=sample["id"],
            lineage_node_label=sample.get("source_name") or sample["id"],
            risk_category_l1="",
            risk_category_l2="",
        )
        for sample in risk_samples
    ]
    try:
        result = await run_topic2_keyword_detection(scan_items=scan_items)
    except Exception as exc:
        return {}, _fallback_risk_status(f"课题二风险检测调用失败：{exc}")
    if not result.connected:
        return {}, _fallback_risk_status(result.message)
    predictions: dict[str, dict[str, Any]] = {}
    for prediction in result.predictions:
        source_index = prediction.source_index
        if 0 <= source_index < len(risk_samples):
            predictions[risk_samples[source_index]["id"]] = prediction.model_dump()
    return predictions, {
        "connected": True,
        "mode": result.method or "live",
        "source": result.source,
        "message": result.message,
        "fallback": False,
    }


def _fallback_risk_status(message: str) -> dict[str, Any]:
    return {
        "connected": False,
        "mode": "demo_adapter",
        "source": "project5_input_guardrail_demo_adapter",
        "message": message,
        "fallback": True,
        "next_action": "现场演示可继续查看本地 demo adapter 结果；联调时请检查课题二服务。",
    }


def _evaluate_sample(sample: dict[str, Any], risk_prediction: dict[str, Any] | None) -> dict[str, Any]:
    value_result = _evaluate_value(sample)
    risk_result = _evaluate_risk(sample, risk_prediction)
    lineage_result = _build_lineage(sample)
    evidence = _merge_evidence(sample, value_result, risk_result, lineage_result)
    disposition = _disposition(value_result, risk_result, sample)
    fix_suggestion = _fix_suggestion(value_result, risk_result, disposition)
    return {
        "value_result": value_result,
        "risk_result": risk_result,
        "lineage_result": lineage_result,
        "evidence": evidence,
        "fix_suggestion": fix_suggestion,
        "disposition": disposition,
    }


def _evaluate_value(sample: dict[str, Any]) -> dict[str, Any]:
    label = sample.get("source_label", "").lower()
    if sample.get("track") != "value":
        return {
            "status": "not_applicable",
            "quality_level": "not_applicable",
            "score": 0,
            "adapter": "project5_demo_adapter",
        }
    if label == "high":
        return {
            "status": "pass",
            "quality_level": "high",
            "score": 0.92,
            "adapter": "project5_demo_adapter",
            "reason": "文本事实清楚，文化元素和证据表达完整。",
        }
    if label == "medium":
        return {
            "status": "review",
            "quality_level": "medium",
            "score": 0.64,
            "adapter": "project5_demo_adapter",
            "reason": "文本基本可用，但文化来源和价值语义展开不足。",
        }
    return {
        "status": "fail",
        "quality_level": "low",
        "score": 0.28,
        "adapter": "project5_demo_adapter",
        "reason": "文本存在事实错配或价值表达不当，需要修正后复核。",
    }


def _evaluate_risk(
    sample: dict[str, Any],
    risk_prediction: dict[str, Any] | None,
) -> dict[str, Any]:
    if sample.get("track") != "risk":
        return {
            "status": "not_applicable",
            "is_abnormal": False,
            "score": 0,
            "adapter": "project5_demo_adapter",
        }
    borderline = sample.get("expected_issue") == "borderline_review"
    if risk_prediction:
        status = risk_prediction.get("status") or "安全"
        score = risk_prediction.get("score") or 0
        evidence_chain = risk_prediction.get("evidence_chain") or []
        if borderline and not risk_prediction.get("is_abnormal"):
            status = "待复核"
            score = max(float(score or 0), 0.48)
            evidence_chain = [
                *evidence_chain,
                "原始标签为 safe，但问题询问难以发现的财务审查方法，需人工确认意图。",
            ]
        return {
            "status": status,
            "is_abnormal": bool(risk_prediction.get("is_abnormal")),
            "score": score,
            "category_l1": risk_prediction.get("risk_category_l1") or ("输入风险" if borderline else ""),
            "category_l2": risk_prediction.get("risk_category_l2") or sample.get("expected_issue") or "",
            "adapter": risk_prediction.get("detect_method") or "topic2_live",
            "fallback": False,
            "evidence_chain": evidence_chain,
            "findings": risk_prediction.get("findings") or [],
        }
    unsafe = sample.get("source_label") == "unsafe"
    return {
        "status": "异常" if unsafe else ("待复核" if borderline else "安全"),
        "is_abnormal": unsafe,
        "score": 0.86 if unsafe else (0.48 if borderline else 0.08),
        "category_l1": "输入风险" if unsafe or borderline else "",
        "category_l2": sample.get("expected_issue") or "",
        "adapter": "project5_demo_adapter",
        "fallback": True,
        "evidence_chain": [
            f"来源标签：{sample.get('source_label') or 'unknown'}",
            f"来源样本：{sample.get('source_sample_id') or sample.get('id')}",
        ],
        "findings": [],
    }


def _build_lineage(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "batch_minimal_lineage",
        "nodes": [
            {"id": sample.get("source_asset_id") or "custom_batch", "type": "source_asset"},
            {"id": sample["id"], "type": "sample"},
            {"id": f"{sample['id']}:chunk:0", "type": "chunk"},
            {"id": f"{sample['id']}:detect", "type": "detect_result"},
        ],
        "edges": [
            [sample.get("source_asset_id") or "custom_batch", sample["id"]],
            [sample["id"], f"{sample['id']}:chunk:0"],
            [f"{sample['id']}:chunk:0", f"{sample['id']}:detect"],
        ],
    }


def _merge_evidence(
    sample: dict[str, Any],
    value_result: dict[str, Any],
    risk_result: dict[str, Any],
    lineage_result: dict[str, Any],
) -> list[dict[str, str]]:
    evidence = [
        {
            "type": "source",
            "title": sample.get("source_name") or "本批输入",
            "detail": sample.get("source_sample_id") or sample["id"],
        },
        {
            "type": "span",
            "title": "触发片段",
            "detail": _truncate(sample["text"], 120),
        },
        {
            "type": "lineage",
            "title": "本批血缘链",
            "detail": " -> ".join(node["type"] for node in lineage_result["nodes"]),
        },
    ]
    if value_result.get("reason"):
        evidence.append({"type": "value", "title": "价值判断", "detail": value_result["reason"]})
    if risk_result.get("evidence_chain"):
        evidence.append(
            {
                "type": "risk",
                "title": "风险证据",
                "detail": "；".join(str(item) for item in risk_result["evidence_chain"][:2]),
            }
        )
    return evidence


def _disposition(
    value_result: dict[str, Any],
    risk_result: dict[str, Any],
    sample: dict[str, Any],
) -> str:
    if risk_result.get("is_abnormal"):
        return "review"
    if value_result.get("status") == "fail":
        return "revise"
    if value_result.get("status") == "review" or risk_result.get("status") == "待复核":
        return "review"
    return "pass"


def _fix_suggestion(
    value_result: dict[str, Any],
    risk_result: dict[str, Any],
    disposition: str,
) -> str:
    if disposition == "pass":
        return "本条语料可进入低风险抽检或候选入库。"
    if risk_result.get("is_abnormal"):
        return "建议从训练正样本剔除，保留证据链后进入人工复核；必要时脱敏或改写后复跑。"
    if value_result.get("status") == "fail":
        return "建议修正事实错配和价值表达，再由人工确认是否入库。"
    return "建议补充来源证据或人工核对边界语义后再入库。"


async def _mutate(job_id: str, mutator) -> dict[str, Any]:
    async with _lock_for(job_id):
        job = _jobs.get(job_id)
        if job is None:
            raise InputGuardrailLiveRunError(404, "输入护栏 live run 不存在")
        mutator(job)
        return job


def _finish_sample(current: dict[str, Any], index: int, data: dict[str, Any]) -> None:
    row = current["samples"][index]
    row.update(data)
    row["detect_status"] = "done"
    row["error"] = None
    current["progress"] = _progress_from(current["samples"])


def _finish_job(job: dict[str, Any]) -> None:
    samples = job["samples"]
    failed = any(sample["detect_status"] == "error" for sample in samples)
    done = any(sample["detect_status"] == "done" for sample in samples)
    job["status"] = "partial" if failed and done else ("error" if failed else "finished")
    job["progress"] = _progress_from(samples)
    job["finished_at"] = datetime.now(timezone.utc).isoformat()


def _progress_from(samples: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "detect_done": sum(1 for sample in samples if sample["detect_status"] in {"done", "error"}),
        "detect_total": len(samples),
    }


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit]}..."
