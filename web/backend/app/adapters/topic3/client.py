"""Benchmark HTTP client + shared utilities for topic3 adapter."""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BENCHMARK_BASE = settings.benchmark_base_url
REQUEST_TIMEOUT = getattr(settings, "benchmark_timeout", 30.0)

ADAPTER_VERSION = "topic3-v1"

# 全局锁保护共享可变字典的并发写入
_map_lock = asyncio.Lock()

# task_id → benchmark_job_id 映射
_task_job_map: dict[str, str] = {}

# task_id → 任务元数据（selected_dimensions 等）
_task_meta: dict[str, dict] = {}

# Mock 任务注册表
_mock_task_registry: dict[str, float] = {}
STAGE_DURATION = 2.5

# 共享 httpx 客户端（连接池复用，避免每次请求重建 TCP/TLS）
_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
            verify=False,
            trust_env=False,
        )
    return _http_client


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"


async def register_task_job(task_id: str, job_id: str) -> None:
    async with _map_lock:
        _task_job_map[task_id] = job_id


async def resolve_job_id(task_id: str) -> str | None:
    async with _map_lock:
        job_id = _task_job_map.get(task_id)
    if job_id is not None:
        return job_id
    # 内存缓存未命中 → 回退 DB（服务重启/多 worker 恢复路径）
    from app.services.output_eval_store import get_task_job_id as _db_lookup
    db_job_id = await _db_lookup(task_id)
    if db_job_id:
        async with _map_lock:
            _task_job_map[task_id] = db_job_id
    return db_job_id


async def register_mock_task(task_id: str, ts: float) -> None:
    async with _map_lock:
        _mock_task_registry[task_id] = ts


async def get_mock_task_ts(task_id: str) -> float | None:
    async with _map_lock:
        return _mock_task_registry.get(task_id)


async def benchmark_get(path: str) -> dict | None:
    try:
        client = await _get_client()
        resp = await client.get(f"{BENCHMARK_BASE}{path}")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError:
        logger.warning("Benchmark GET %s HTTP error", path, exc_info=True)
        return None
    except httpx.TimeoutException:
        logger.warning("Benchmark GET %s timed out", path, exc_info=True)
        return None
    except httpx.RequestError:
        logger.warning("Benchmark GET %s request failed", path, exc_info=True)
        return None


async def benchmark_post(path: str, body: dict, timeout: float | None = None) -> dict | None:
    try:
        client = await _get_client()
        resp = await client.post(f"{BENCHMARK_BASE}{path}", json=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError:
        logger.warning("Benchmark POST %s HTTP error", path, exc_info=True)
        return None
    except httpx.TimeoutException:
        logger.warning("Benchmark POST %s timed out", path, exc_info=True)
        return None
    except httpx.RequestError:
        logger.warning("Benchmark POST %s request failed", path, exc_info=True)
        return None


async def store_task_meta(task_id: str, meta: dict) -> None:
    async with _map_lock:
        _task_meta[task_id] = meta


async def get_task_meta(task_id: str) -> dict | None:
    async with _map_lock:
        return _task_meta.get(task_id)
