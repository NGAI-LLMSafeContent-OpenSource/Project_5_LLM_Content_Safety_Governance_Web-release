"""Proxy Topic 3 cultural assessment console runtime APIs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings


_TIMEOUT = httpx.Timeout(30.0)
_JOB_BASE_URLS: dict[str, str] = {}
_JOB_CACHE_KEYS: dict[str, str] = {}
_CACHE_JOB_PREFIX = "cached-culture-assessment-"
_CACHE_VERSION = 1
_CACHE_PATH = Path(
    os.environ.get(
        "OUTPUT_CULTURE_ASSESSMENT_CACHE_PATH",
        Path(__file__).resolve().parents[3] / ".cache" / "output_culture_assessment_cache.json",
    )
)


def _base_url() -> str:
    return get_settings().cultural_assessment_console_base_url.strip().rstrip("/")


def _v2_base_url() -> str:
    return get_settings().cultural_assessment_console_v2_base_url.strip().rstrip("/")


async def _request(
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    base = (base_url or _base_url()).strip().rstrip("/")
    if not base:
        raise RuntimeError("文化评测控制台地址未配置")
    try:
        async with httpx.AsyncClient(base_url=base, timeout=_TIMEOUT, trust_env=False) as client:
            response = await client.request(method, path, json=json)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] if exc.response is not None else str(exc)
        raise RuntimeError(f"文化评测控制台返回异常：{detail}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"文化评测控制台不可达：{exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("文化评测控制台返回非对象 JSON")
    return data


async def health() -> dict[str, Any]:
    responses = await _request_all("GET", "/api/health")
    if not responses:
        raise RuntimeError("文化评测控制台不可达：v1/v2 均不可用")
    primary = responses[0]
    return {
        **primary,
        "ok": any(bool(item.get("ok")) for item in responses),
        "active_jobs": sum(int(item.get("active_jobs") or 0) for item in responses),
        "dataset_count": sum(int(item.get("dataset_count") or 0) for item in responses),
        "static_view_count": sum(int(item.get("static_view_count") or 0) for item in responses),
        "sources": [item.get("source") for item in responses if item.get("source")],
    }


async def datasets() -> dict[str, Any]:
    responses = await _request_all("GET", "/api/datasets")
    if not responses:
        raise RuntimeError("文化评测控制台数据集不可达：v1/v2 均不可用")
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for data in responses:
        for item in data.get("datasets") or []:
            if not isinstance(item, dict):
                continue
            dataset_id = str(item.get("id") or "")
            if dataset_id and dataset_id not in seen:
                seen.add(dataset_id)
                merged.append(item)
    return {
        **responses[0],
        "datasets": merged,
        "dataset_count": len(merged),
        "sources": [item.get("source") for item in responses if item.get("source")],
    }


async def jobs() -> dict[str, Any]:
    responses = await _request_all("GET", "/api/jobs")
    if not responses:
        raise RuntimeError("文化评测控制台任务列表不可达：v1/v2 均不可用")
    merged: list[dict[str, Any]] = []
    for data in responses:
        for job in data.get("jobs") or []:
            if isinstance(job, dict):
                _remember_job_base(job, str(data.get("_base_url") or _base_url()))
                merged.append(job)
    return {
        **responses[0],
        "jobs": merged,
        "sources": [item.get("source") for item in responses if item.get("source")],
    }


async def start_job(payload: dict[str, Any]) -> dict[str, Any]:
    cache_key = _job_cache_key(payload)
    cached_entry = _read_cache().get(cache_key)
    if cached_entry:
        return _cached_job(cache_key, cached_entry, payload)

    if _is_v2_dataset(payload):
        base_url = _v2_base_url()
        data = await _request("POST", "/api/jobs", json=payload, base_url=base_url)
        _remember_job_base(data, base_url)
        _remember_job_cache(data, cache_key)
        return data
    try:
        data = await _request("POST", "/api/jobs", json=payload)
        _remember_job_base(data, _base_url())
        _remember_job_cache(data, cache_key)
        return data
    except RuntimeError as exc:
        if payload.get("target_mode") != "reference" or "target_mode must be direct or agent" not in str(exc):
            raise
        base_url = _v2_base_url()
        data = await _request("POST", "/api/jobs", json=payload, base_url=base_url)
        _remember_job_base(data, base_url)
        _remember_job_cache(data, cache_key)
        return data


async def job_status(job_id: str) -> dict[str, Any]:
    cached_entry = _cached_entry_from_job_id(job_id)
    if cached_entry:
        return _cached_job(_cache_key_from_job_id(job_id), cached_entry)
    return await _request_with_known_or_fallback("GET", f"/api/jobs/{job_id}", job_id=job_id)


async def job_results(job_id: str) -> dict[str, Any]:
    cached_entry = _cached_entry_from_job_id(job_id)
    if cached_entry:
        return _cached_result(_cache_key_from_job_id(job_id), cached_entry)

    data = await _request_with_known_or_fallback("GET", f"/api/jobs/{job_id}/results", job_id=job_id)
    cache_key = _JOB_CACHE_KEYS.get(job_id)
    if cache_key and data.get("summary"):
        _save_cache_entry(cache_key, data)
        data["cached"] = False
        data["cache_key"] = cache_key
    return data


async def stop_job(job_id: str) -> dict[str, Any]:
    cached_entry = _cached_entry_from_job_id(job_id)
    if cached_entry:
        return _cached_job(_cache_key_from_job_id(job_id), cached_entry)
    return await _request_with_known_or_fallback("POST", f"/api/jobs/{job_id}/stop", job_id=job_id)


def _remember_job_base(data: dict[str, Any], base_url: str) -> None:
    job_id = data.get("job_id")
    if isinstance(job_id, str) and job_id:
        _JOB_BASE_URLS[job_id] = base_url


def _remember_job_cache(data: dict[str, Any], cache_key: str) -> None:
    job_id = data.get("job_id")
    if isinstance(job_id, str) and job_id:
        _JOB_CACHE_KEYS[job_id] = cache_key


def _is_v2_dataset(payload: dict[str, Any]) -> bool:
    dataset_id = str(payload.get("dataset_id") or "")
    return dataset_id.startswith("framework_cultural_diversity_evaluation_dataset_v1")


def _normalize_optional_int(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _job_cache_key(payload: dict[str, Any]) -> str:
    dataset_id = str(payload.get("dataset_id") or "").strip()
    body = {
        "version": _CACHE_VERSION,
        "dataset_id": dataset_id,
        "target_mode": str(payload.get("target_mode") or "").strip(),
        "limit": _normalize_optional_int(payload.get("limit")),
        "offset": _normalize_optional_int(payload.get("offset"), 0) or 0,
        "runtime": "culture_eval_console_v2" if dataset_id.startswith("framework_") else "culture_eval_console",
    }
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_cache() -> dict[str, Any]:
    if not _CACHE_PATH.is_file():
        return {}
    try:
        with _CACHE_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_cache(data: dict[str, Any]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=_CACHE_PATH.parent, delete=False) as tmp:
        json.dump(data, tmp, ensure_ascii=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(_CACHE_PATH)


def _save_cache_entry(cache_key: str, result: dict[str, Any]) -> None:
    cache = _read_cache()
    result_copy = dict(result)
    result_copy.pop("cached", None)
    result_copy.pop("cache_key", None)
    cache[cache_key] = {
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "result": result_copy,
    }
    _write_cache(cache)


def _cache_key_from_job_id(job_id: str) -> str:
    return job_id.removeprefix(_CACHE_JOB_PREFIX)


def _cached_entry_from_job_id(job_id: str) -> dict[str, Any] | None:
    if not job_id.startswith(_CACHE_JOB_PREFIX):
        return None
    entry = _read_cache().get(_cache_key_from_job_id(job_id))
    return entry if isinstance(entry, dict) else None


def _cached_job(
    cache_key: str,
    entry: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
    return {
        "job_id": f"{_CACHE_JOB_PREFIX}{cache_key}",
        "status": "completed",
        "running": False,
        "progress": 100,
        "dataset_id": result.get("dataset_id") or (payload or {}).get("dataset_id"),
        "dataset_label": result.get("dataset_label"),
        "target_mode": result.get("target_mode") or (payload or {}).get("target_mode"),
        "run_id": f"cache_{cache_key[:12]}",
        "log_tail": [
            "已命中课题5本地缓存，跳过重复 DeepSeek 评测。",
            f"缓存写入时间：{entry.get('saved_at') or '-'}",
        ],
        "cached": True,
        "cache_key": cache_key,
        "cache_saved_at": entry.get("saved_at"),
    }


def _cached_result(cache_key: str, entry: dict[str, Any]) -> dict[str, Any]:
    result = dict(entry.get("result") or {})
    result["cached"] = True
    result["cache_key"] = cache_key
    result["cache_saved_at"] = entry.get("saved_at")
    return result


async def _request_all(method: str, path: str) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    errors: list[str] = []
    for base_url in (_base_url(), _v2_base_url()):
        if not base_url:
            continue
        try:
            data = await _request(method, path, base_url=base_url)
            data["_base_url"] = base_url
            data.setdefault(
                "source",
                "culture_assessment_console_v2" if base_url == _v2_base_url() else "culture_assessment_console",
            )
            responses.append(data)
        except RuntimeError as exc:
            errors.append(str(exc))
    if responses:
        return responses
    if errors:
        raise RuntimeError("；".join(errors))
    return []


async def _request_with_known_or_fallback(method: str, path: str, job_id: str) -> dict[str, Any]:
    known_base = _JOB_BASE_URLS.get(job_id)
    if known_base:
        return await _request(method, path, base_url=known_base)

    errors: list[str] = []
    for base_url in (_base_url(), _v2_base_url()):
        try:
            data = await _request(method, path, base_url=base_url)
            _remember_job_base(data, base_url)
            return data
        except RuntimeError as exc:
            errors.append(str(exc))
    raise RuntimeError("；".join(errors) or f"文化评测任务不可达：{job_id}")
