"""HTTP contracts for the three independently deployed Topic 1 corpus tools.

This layer never loads models, retries task creation, follows returned URLs or
interprets scarcity scores as training-membership proof. Callers own durable
task records, input authorization and output-asset registration.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

Tool = Literal["refinement", "detox", "detection"]
MAX_ASSET_BYTES = 16 * 1024 * 1024


def result_assets(tool: Tool, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Construct download identities from known contracts, never returned URLs."""
    if tool == "detection":
        if not isinstance(payload.get("artifacts", {}), dict):
            raise CorpusToolError("invalid_contract", "结果文件清单不符合约定。")
        names = {"scores": "sample_scores.csv", "diagnostics": "bucket_diagnostics.csv", "report": "run_report.md"}
        return [{"key": key, "name": name} for key, name in names.items()
                if key in payload.get("artifacts", {})]
    items = payload.get("assets" if tool == "refinement" else "output_assets", [])
    if not isinstance(items, list) or len(items) > 20:
        raise CorpusToolError("invalid_contract", "结果文件清单不符合约定。")
    assets = []
    for item in items:
        if not isinstance(item, dict):
            raise CorpusToolError("invalid_contract", "结果文件清单不符合约定。")
        name = item.get("name" if tool == "refinement" else "filename")
        key = "output" if tool == "refinement" else _identifier(item.get("asset_id"))
        checksum = item.get("sha256")
        size = item.get("size_bytes")
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name)
                or name in {".", ".."} or (tool == "refinement" and name != "output.jsonl")
                or not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum)
                or isinstance(size, bool) or not isinstance(size, int) or size < 0):
            raise CorpusToolError("invalid_contract", "结果文件身份不符合约定。")
        assets.append({"key": key, "name": name, "sha256": checksum, "size_bytes": size})
    if len({item["key"] for item in assets}) != len(assets):
        raise CorpusToolError("invalid_contract", "结果文件标识重复。")
    return assets


class CorpusToolError(RuntimeError):
    """Non-sensitive error suitable for conversion at the service boundary."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RemoteTask:
    task_id: str
    status: str
    progress: float | None


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise CorpusToolError("invalid_contract", "工具返回了无效的任务标识。")
    return value


def normalize_task(tool: Tool, payload: dict[str, Any]) -> RemoteTask:
    task_id = _identifier(payload.get("job_id" if tool == "detection" else "task_id"))
    status = payload.get("state" if tool == "detox" else "status")
    if (tool == "detox" and status == "succeeded") or (tool == "refinement" and status == "success"):
        status = "completed"
    if not isinstance(status, str) or status not in {"queued", "running", "cancelling", "completed", "failed", "cancelled"}:
        raise CorpusToolError("invalid_contract", "工具返回了未知任务状态。")
    progress = payload.get("progress")
    if tool == "refinement" and progress is not None:
        if not isinstance(progress, dict):
            raise CorpusToolError("invalid_contract", "工具返回了无效进度。")
        progress = progress.get("percent")
    if progress is not None:
        maximum = 1 if tool == "detox" else 100
        if (isinstance(progress, bool) or not isinstance(progress, (int, float))
                or not math.isfinite(progress) or not 0 <= progress <= maximum):
            raise CorpusToolError("invalid_contract", "工具返回了无效进度。")
        progress = float(progress) * (100 if tool == "detox" else 1)
    return RemoteTask(task_id, status, progress)


class CorpusToolClient:
    def __init__(
        self, tool: Tool, base_url: str, *, api_key: str = "",
        timeout: float = 10, transport: httpx.AsyncBaseTransport | None = None,
    ):
        if tool not in {"refinement", "detox", "detection"}:
            raise ValueError("Unsupported corpus tool")
        try:
            parsed = urlsplit(base_url)
            parsed.port
        except ValueError as exc:
            raise CorpusToolError("not_configured", "工具服务地址尚未正确配置。") from exc
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise CorpusToolError("not_configured", "工具服务地址尚未正确配置。")
        self.tool = tool
        try:
            self._client = httpx.AsyncClient(
                base_url=base_url.rstrip("/") + "/", timeout=timeout,
                headers={"X-API-Key": api_key} if tool == "refinement" and api_key else {},
                follow_redirects=False, trust_env=False, transport=transport,
            )
        except (httpx.InvalidURL, ValueError, UnicodeError) as exc:
            raise CorpusToolError("not_configured", "工具服务地址或凭据格式不正确。") from exc

    async def __aenter__(self) -> "CorpusToolClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise CorpusToolError("upstream_timeout", "工具服务响应超时，请查询已有任务状态后再决定是否重试。") from exc
        except httpx.HTTPStatusError as exc:
            code = {401: "unauthorized", 403: "unauthorized", 404: "not_found",
                    409: "not_ready", 429: "busy", 503: "not_ready"}.get(
                        exc.response.status_code, "upstream_error")
            raise CorpusToolError(code, "工具请求未完成，请检查服务配置或稍后重试。") from exc
        except httpx.RequestError as exc:
            raise CorpusToolError("unreachable", "暂时无法连接工具服务。") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise CorpusToolError("invalid_contract", "工具返回的内容不是有效 JSON。") from exc
        if not isinstance(payload, dict):
            raise CorpusToolError("invalid_contract", "工具返回的数据结构不符合约定。")
        return payload

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "api/health" if self.tool == "detection" else "health")

    async def capabilities(self) -> dict[str, Any]:
        return await self._request("GET", "api/capabilities" if self.tool == "detection" else "capabilities")

    async def start(
        self, records: list[dict[str, str]], *, operation: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> RemoteTask:
        # These are server-owned parameters, not a public arbitrary-URL/model API.
        if not records or len(records) > 10000:
            raise ValueError("Expected 1..10000 records")
        ids: set[str] = set()
        for record in records:
            if (not isinstance(record.get("id"), str) or not record["id"].strip()
                    or record["id"] in ids or not isinstance(record.get("text"), str)
                    or not record["text"].strip()):
                raise ValueError("Records require unique IDs and nonempty text")
            ids.add(record["id"])
        content = ("\n".join(json.dumps(r, ensure_ascii=False, allow_nan=False) for r in records) + "\n").encode("utf-8")
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("Input exceeds 10 MiB")
        params = dict(parameters or {})
        if self.tool == "detox":
            if operation not in {"preprocess", "detox", "evaluate"}:
                raise ValueError("Explicit detox operation is required")
            payload = await self._request("POST", "start", json={
                "tool": operation, "input": {"records": records, "text_field": "text"},
                "parameters": params,
            })
        elif self.tool == "refinement":
            payload = await self._request("POST", "start", data={
                "tool": "refinemodel_clean", "params": json.dumps(params, allow_nan=False),
            }, files={"input_file": ("input.jsonl", content, "application/x-ndjson")})
        else:
            if not params.get("model") or params.get("backend") not in {"hf", "vllm"}:
                raise ValueError("Detection requires an explicitly configured model and backend")
            params.update(mapping_mode="text", text_column="text", id_column="id")
            payload = await self._request("POST", "api/jobs", data=params,
                                          files={"file": ("input.jsonl", content, "application/x-ndjson")})
        return normalize_task(self.tool, payload)

    def _path(self, task_id: str, action: str) -> str:
        task_id = _identifier(task_id)
        if self.tool == "detection":
            return f"api/jobs/{task_id}" + (f"/{action}" if action != "status" else "")
        return f"{action}/{task_id}"

    async def status(self, task_id: str) -> RemoteTask:
        result = normalize_task(self.tool, await self._request("GET", self._path(task_id, "status")))
        if result.task_id != task_id:
            raise CorpusToolError("invalid_contract", "工具任务标识与请求不一致。")
        return result

    async def cancel(self, task_id: str) -> dict[str, Any]:
        # Cancellation responses differ from status responses; the caller polls
        # status afterwards instead of assuming cancellation has completed.
        return await self._request("POST", self._path(task_id, "cancel"))

    async def result(self, task_id: str) -> dict[str, Any]:
        if (await self.status(task_id)).status != "completed":
            raise CorpusToolError("not_ready", "任务尚未成功完成，不能读取处理结果。")
        payload = await self._request("GET", self._path(task_id, "result"))
        if payload.get("job_id" if self.tool == "detection" else "task_id") != task_id:
            raise CorpusToolError("invalid_contract", "结果不属于当前任务。")
        if self.tool == "detox" and payload.get("backend") != "real":
            raise CorpusToolError("demo_result", "当前服务未返回真实处理结果。")
        return payload

    async def logs(self, task_id: str, cursor: int = 0) -> dict[str, Any]:
        if cursor < 0:
            raise ValueError("Negative log cursor")
        params = {"after" if self.tool == "detox" else "cursor": cursor, "limit": 100}
        return await self._request("GET", self._path(task_id, "logs"),
                                   params={} if self.tool == "detection" else params)

    async def download(self, task_id: str, asset: dict[str, Any]) -> bytes:
        current = result_assets(self.tool, await self.result(task_id))
        if asset not in current:
            raise CorpusToolError("invalid_contract", "结果文件已变化，请联系管理员核对。")
        task_id = _identifier(task_id)
        if self.tool == "refinement":
            path = f"assets/{task_id}/output.jsonl"
        elif self.tool == "detox":
            path = f"assets/{_identifier(asset['key'])}/download"
        else:
            path = f"api/jobs/{task_id}/download/{asset['key']}"
        if asset.get("size_bytes", 0) > MAX_ASSET_BYTES:
            raise CorpusToolError("asset_too_large", "结果文件超过16MB在线下载限制，请联系管理员导出。")
        content = bytearray()
        try:
            async with self._client.stream("GET", path) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if len(content) + len(chunk) > MAX_ASSET_BYTES:
                        raise CorpusToolError("asset_too_large", "结果文件超过16MB在线下载限制。")
                    content.extend(chunk)
        except httpx.HTTPError as exc:
            raise CorpusToolError("download_failed", "结果文件下载失败，请稍后重试。") from exc
        if ("size_bytes" in asset and len(content) != asset["size_bytes"]) or (
            "sha256" in asset and hashlib.sha256(content).hexdigest() != asset["sha256"]
        ):
            raise CorpusToolError("invalid_contract", "结果文件完整性校验失败。")
        return bytes(content)
