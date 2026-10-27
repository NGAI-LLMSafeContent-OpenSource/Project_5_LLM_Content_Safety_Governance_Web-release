"""Output guardrail live-batch orchestration: detect then rewrite unsafe samples."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

import httpx

from app.adapters.topic3.client import benchmark_post
from app.core.config import get_settings
from app.adapters.topic3.compliance_client import ComplianceEditError, edit_compliance_text
from app.schemas.output_eval import InferSampleRequest
from app.services import output_guardrail_live_store as store

logger = logging.getLogger(__name__)

PACKS_DIR = Path(__file__).resolve().parents[2] / "data" / "output_guardrail_packs"
DEFAULT_PACK_ID = "demo-zh-8"
DEFAULT_MAX_SAMPLES = 8
MIN_SAMPLES = 5
MAX_SAMPLES = 20
DETECT_CONCURRENCY = 4
REWRITE_CONCURRENCY = 2
DETECT_TIMEOUT_SECONDS = get_settings().output_guardrail_detect_timeout_seconds

_job_locks: dict[str, asyncio.Lock] = {}


class LiveBatchError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _lock_for(job_id: str) -> asyncio.Lock:
    lock = _job_locks.get(job_id)
    if lock is None:
        lock = asyncio.Lock()
        _job_locks[job_id] = lock
    return lock


def _empty_sample(raw: dict) -> dict:
    return {
        "id": str(raw.get("id") or ""),
        "prompt": str(raw.get("prompt") or ""),
        "response": str(raw.get("response") or ""),
        "detect_status": "pending",
        "pred_safe_type": None,
        "pred_risk_level": None,
        "pred_category": None,
        "pred_category_code": None,
        "risk_evidence": [],
        "rewrite_status": "pending",
        "disposition": "",
        "edited_text": "",
        "post_safety_label": "",
        "error": None,
    }


def _progress_from(samples: list[dict], rewrite_total: int | None = None) -> dict:
    detect_done = sum(1 for row in samples if row["detect_status"] in {"done", "error"})
    unsafe_done = [
        row
        for row in samples
        if row["detect_status"] == "done" and str(row.get("pred_safe_type") or "").lower() != "safe"
    ]
    total_rewrite = len(unsafe_done) if rewrite_total is None else rewrite_total
    rewrite_done = sum(
        1
        for row in unsafe_done
        if row["rewrite_status"] in {"done", "error", "skipped"}
    )
    return {
        "detect_done": detect_done,
        "detect_total": len(samples),
        "rewrite_done": rewrite_done,
        "rewrite_total": total_rewrite if detect_done == len(samples) else (rewrite_total or 0),
    }


def _all_terminal(samples: list[dict]) -> bool:
    return all(
        row["detect_status"] in {"done", "error"}
        and row["rewrite_status"] in {"done", "skipped", "error"}
        for row in samples
    )


def _final_status(samples: list[dict]) -> str:
    detect_ok = any(row["detect_status"] == "done" for row in samples)
    failed = any(
        row["detect_status"] == "error" or row["rewrite_status"] == "error"
        for row in samples
    )
    if failed and detect_ok:
        return "partial"
    if failed:
        return "error"
    return "finished"


def _mark_rewrite_failed(
    row: dict, message: str = "合规改写失败", *, clear_edited_text: bool = True
) -> None:
    row["rewrite_status"] = "error"
    row["disposition"] = "failed"
    if clear_edited_text:
        row["edited_text"] = ""
    row["error"] = message


def load_pack(pack_id: str) -> dict:
    path = PACKS_DIR / f"{pack_id}.json"
    if not path.is_file():
        raise LiveBatchError(400, f"预置包不存在: {pack_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveBatchError(400, f"预置包无法读取: {pack_id}") from exc
    if not isinstance(data, dict):
        raise LiveBatchError(400, f"预置包格式无效: {pack_id}")
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise LiveBatchError(400, f"预置包缺少 samples: {pack_id}")
    return {
        "pack_id": str(data.get("pack_id") or pack_id),
        "title": str(data.get("title") or pack_id),
        "model_id": str(data.get("model_id") or "qwen3.5-9b"),
        "language": str(data.get("language") or "zh"),
        "samples": samples,
    }


def list_demo_packs() -> list[dict]:
    if not PACKS_DIR.is_dir():
        return []
    packs: list[dict] = []
    for path in sorted(PACKS_DIR.glob("*.json")):
        try:
            pack = load_pack(path.stem)
        except LiveBatchError:
            continue
        packs.append(
            {
                "pack_id": pack["pack_id"],
                "title": pack["title"],
                "model_id": pack["model_id"],
                "language": pack["language"],
                "sample_count": len(pack["samples"]),
            }
        )
    return packs


def _select_samples(pack: dict, max_samples: int | None) -> list[dict]:
    raw = pack["samples"]
    if len(raw) < MIN_SAMPLES:
        raise LiveBatchError(400, f"预置包样本不足 {MIN_SAMPLES} 条")
    if max_samples is None:
        count = min(DEFAULT_MAX_SAMPLES, len(raw))
    else:
        count = min(max(max_samples, MIN_SAMPLES), MAX_SAMPLES, len(raw))
    selected = []
    for item in raw[:count]:
        if not isinstance(item, dict):
            continue
        sample = _empty_sample(item)
        if not sample["id"] or not sample["response"]:
            continue
        selected.append(sample)
    if len(selected) < MIN_SAMPLES:
        raise LiveBatchError(400, f"预置包有效样本不足 {MIN_SAMPLES} 条")
    return selected


def _is_safe(pred_safe_type: object) -> bool:
    return str(pred_safe_type or "").lower() == "safe"


def normalize_detection_result(data: dict) -> dict:
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    evidence = data.get("risk_evidence")
    if evidence is None:
        evidence = result.get("risk_evidence")
    if evidence is None:
        evidence = result.get("evidence", {}).get("items") if isinstance(result.get("evidence"), dict) else []
    if not isinstance(evidence, list):
        evidence = []
    return {
        "ok": True,
        "pred_safe_type": (
            data.get("pred_safe_type")
            or data.get("safe_type")
            or result.get("safe_type")
        ),
        "pred_risk_level": (
            data.get("pred_risk_level")
            or data.get("risk_level")
            or result.get("risk_level")
            or result.get("risk_level_id")
        ),
        "pred_category": (
            data.get("pred_category")
            or data.get("risk_category_name")
            or result.get("risk_category_name")
        ),
        "pred_category_code": (
            data.get("pred_category_code")
            or data.get("risk_category")
            or result.get("risk_category")
        ),
        "risk_evidence": evidence,
        "error": None,
    }


async def detect_one(sample: dict, model_id: str) -> dict:
    payload = InferSampleRequest(
        model_id=model_id or "qwen3.5-9b",
        prompt=sample.get("prompt") or "",
        response=sample.get("response") or "",
    )
    data = await benchmark_post(
        "/api/demo/infer",
        {
            "task": payload.task,
            "model_id": payload.model_id,
            "prompt": payload.prompt,
            "response": payload.response,
            "template_policy": payload.template_policy,
            "use_vllm": payload.use_vllm,
            "use_api": payload.use_api,
            "max_new_tokens": payload.max_new_tokens,
            "severity_max_new_tokens": payload.severity_max_new_tokens,
            "evidence_max_new_tokens": payload.evidence_max_new_tokens,
            "max_model_len": payload.max_model_len,
        },
        timeout=DETECT_TIMEOUT_SECONDS,
    )
    if not data or not data.get("ok"):
        message = ""
        if isinstance(data, dict):
            message = str(data.get("stderr") or data.get("raw_response") or "检测失败")
        else:
            message = "Benchmark 推理服务不可达"
        return {"ok": False, "error": message}
    return normalize_detection_result(data)


async def rewrite_one(
    text: str,
    request_id: str,
    language: str = "zh",
    pre_safety_label: str = "unsafe",
) -> dict:
    return await edit_compliance_text(
        text,
        request_id=request_id,
        language=language,
        pre_safety_label=pre_safety_label,
    )


async def _mutate(job_id: str, mutator) -> dict:
    async with _lock_for(job_id):
        job = await store.get_job(job_id)
        if job is None:
            raise LiveBatchError(404, "任务不存在")
        mutator(job)
        return await store.save_job(job)


async def _run_job(job_id: str, model_id: str, language: str) -> None:
    job = await store.get_job(job_id)
    if job is None:
        return
    samples = job["samples"]

    async def mark_running():
        def mutator(current: dict) -> None:
            current["status"] = "running"

        await _mutate(job_id, mutator)

    await mark_running()
    detect_gate = asyncio.Semaphore(DETECT_CONCURRENCY)

    async def detect_sample(index: int) -> None:
        async with detect_gate:

            def start(current: dict) -> None:
                current["samples"][index]["detect_status"] = "running"
                current["status"] = "running"

            await _mutate(job_id, start)
            sample = (await store.get_job(job_id))["samples"][index]
            try:
                result = await detect_one(sample, model_id)
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}

            def finish(current: dict) -> None:
                row = current["samples"][index]
                if result.get("ok"):
                    row["detect_status"] = "done"
                    row["pred_safe_type"] = result.get("pred_safe_type")
                    row["pred_risk_level"] = result.get("pred_risk_level")
                    row["pred_category"] = result.get("pred_category")
                    row["pred_category_code"] = result.get("pred_category_code")
                    row["risk_evidence"] = result.get("risk_evidence") or []
                    row["error"] = None
                    if _is_safe(row["pred_safe_type"]):
                        row["rewrite_status"] = "skipped"
                        row["disposition"] = "pass"
                    else:
                        row["rewrite_status"] = "pending"
                else:
                    row["detect_status"] = "error"
                    row["rewrite_status"] = "skipped"
                    row["disposition"] = "failed"
                    row["error"] = str(result.get("error") or "检测失败")
                current["progress"] = _progress_from(current["samples"])

            await _mutate(job_id, finish)

    await asyncio.gather(*(detect_sample(index) for index in range(len(samples))))

    job = await store.get_job(job_id)
    if job is None:
        return
    unsafe_indexes = [
        index
        for index, row in enumerate(job["samples"])
        if row["detect_status"] == "done" and not _is_safe(row.get("pred_safe_type"))
    ]

    def set_rewrite_total(current: dict) -> None:
        current["progress"] = _progress_from(current["samples"], rewrite_total=len(unsafe_indexes))

    await _mutate(job_id, set_rewrite_total)

    rewrite_gate = asyncio.Semaphore(REWRITE_CONCURRENCY)

    async def rewrite_sample(index: int) -> None:
        async with rewrite_gate:

            def start(current: dict) -> None:
                current["samples"][index]["rewrite_status"] = "running"

            await _mutate(job_id, start)
            sample = (await store.get_job(job_id))["samples"][index]
            request_id = f"{job_id}:{sample['id']}"
            try:
                result = await rewrite_one(sample.get("response") or "", request_id, language)
                quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
                edited = str(result.get("edited_text") or "")
                disposition = str(result.get("disposition") or "rewrite")
                post_label = str(quality.get("post_safety_label") or "")

                def finish(current: dict) -> None:
                    row = current["samples"][index]
                    row["rewrite_status"] = "done"
                    row["disposition"] = disposition or "rewrite"
                    row["edited_text"] = edited
                    row["post_safety_label"] = post_label
                    row["error"] = None
                    current["progress"] = _progress_from(
                        current["samples"], rewrite_total=len(unsafe_indexes)
                    )

                await _mutate(job_id, finish)
            except (httpx.TimeoutException, httpx.RequestError, ComplianceEditError) as exc:
                message = "合规服务不可达"
                if isinstance(exc, httpx.TimeoutException):
                    message = "合规服务不可达（超时）"
                elif isinstance(exc, ComplianceEditError):
                    message = exc.message

                def fail(current: dict) -> None:
                    row = current["samples"][index]
                    _mark_rewrite_failed(row, message)
                    current["progress"] = _progress_from(
                        current["samples"], rewrite_total=len(unsafe_indexes)
                    )

                await _mutate(job_id, fail)
            except Exception:
                logger.exception(
                    "Unexpected output guardrail rewrite failure",
                    extra={"job_id": job_id, "sample_index": index},
                )

                def fail(current: dict) -> None:
                    row = current["samples"][index]
                    _mark_rewrite_failed(row)
                    current["progress"] = _progress_from(
                        current["samples"], rewrite_total=len(unsafe_indexes)
                    )

                await _mutate(job_id, fail)

    if unsafe_indexes:
        await asyncio.gather(*(rewrite_sample(index) for index in unsafe_indexes))

    def finalize(current: dict) -> None:
        current["progress"] = _progress_from(
            current["samples"], rewrite_total=len(unsafe_indexes)
        )
        if _all_terminal(current["samples"]):
            current["status"] = _final_status(current["samples"])
        else:
            current["status"] = "error"

    await _mutate(job_id, finalize)


async def _run_job_with_fail_safe(job_id: str, model_id: str, language: str) -> None:
    try:
        await _run_job(job_id, model_id, language)
    except Exception:
        logger.exception(
            "Output guardrail live-batch job failed before finalization",
            extra={"job_id": job_id},
        )

        def fail_non_terminal(current: dict) -> None:
            for row in current["samples"]:
                if row["detect_status"] == "running":
                    row["detect_status"] = "error"
                    row["rewrite_status"] = "skipped"
                    row["disposition"] = "failed"
                    row["error"] = row.get("error") or "检测失败"
                elif row["detect_status"] == "pending":
                    row["detect_status"] = "error"
                    row["rewrite_status"] = "skipped"
                    row["disposition"] = "failed"
                    row["error"] = row.get("error") or "检测未完成"
                elif row["detect_status"] == "done" and row["rewrite_status"] in {
                    "pending",
                    "running",
                }:
                    _mark_rewrite_failed(row)
            current["progress"] = _progress_from(current["samples"])
            current["status"] = (
                _final_status(current["samples"])
                if _all_terminal(current["samples"])
                else "error"
            )

        try:
            await _mutate(job_id, fail_non_terminal)
        except Exception:
            logger.exception(
                "Output guardrail live-batch fail-safe could not persist job status",
                extra={"job_id": job_id},
            )


async def start_live_batch(pack_id: str, max_samples: int | None = None) -> dict:
    pack = load_pack(pack_id or DEFAULT_PACK_ID)
    samples = _select_samples(pack, max_samples)
    job_id = f"oglive_{uuid.uuid4().hex[:16]}"
    job = {
        "job_id": job_id,
        "pack_id": pack["pack_id"],
        "status": "pending",
        "source": "live",
        "progress": {
            "detect_done": 0,
            "detect_total": len(samples),
            "rewrite_done": 0,
            "rewrite_total": 0,
        },
        "samples": samples,
    }
    saved = await store.create_job(job)
    asyncio.create_task(_run_job_with_fail_safe(job_id, pack["model_id"], pack["language"]))
    return {
        "job_id": saved["job_id"],
        "status": saved["status"],
        "pack_id": saved["pack_id"],
        "sample_count": len(saved["samples"]),
    }


async def get_live_batch(job_id: str) -> dict:
    job = await store.get_job(job_id)
    if job is None:
        raise LiveBatchError(404, "任务不存在")
    return job


async def edit_compliance_public(
    text: str,
    request_id: str,
    language: str,
    pre_safety_label: str,
) -> dict:
    try:
        return await rewrite_one(
            text,
            request_id=request_id or "manual",
            language=language or "zh",
            pre_safety_label=pre_safety_label or "unsafe",
        )
    except httpx.TimeoutException as exc:
        raise LiveBatchError(502, "合规服务不可达（超时）") from exc
    except httpx.RequestError as exc:
        raise LiveBatchError(502, "合规服务不可达") from exc
    except ComplianceEditError as exc:
        raise LiveBatchError(502, exc.message) from exc
