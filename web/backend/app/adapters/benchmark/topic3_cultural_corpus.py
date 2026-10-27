from __future__ import annotations

import asyncio
import io
import time
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.adapters.benchmark.topic2_autobench import AgentEvent
from app.adapters.topic3.cultural_corpus_generation import (
    get_framework_root,
    get_generation_job_status,
    get_runner_path,
    resolve_generation_api_key,
    start_generation_job,
)
from app.core.config import get_settings

ARTIFACT_MEMBER_NAMES = (
    "samples.jsonl",
    "manifest.json",
    "generation_config.json",
    "worker_state.json",
    "worker.log",
)


class Topic3CulturalCorpusUpstreamError(RuntimeError):
    """Raised when the cultural corpus local runner cannot start or progress."""


class Topic3CulturalCorpusProtocolError(RuntimeError):
    """Raised when cultural corpus job status or artifact is malformed."""


class Topic3CulturalCorpusAdapter:
    def __init__(
        self,
        *,
        timeout: float = 900.0,
        poll_interval: float = 2.0,
        framework_root: Path | None = None,
    ) -> None:
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._framework_root = framework_root
        self._last_job_id: str | None = None

    @classmethod
    def from_settings(cls) -> Topic3CulturalCorpusAdapter:
        settings = get_settings()
        timeout = float(
            getattr(settings, "topic3_cultural_timeout_seconds", 900.0) or 900.0
        )
        poll_interval = float(
            getattr(settings, "topic3_cultural_poll_interval_seconds", 2.0) or 2.0
        )
        return cls(timeout=timeout, poll_interval=poll_interval)

    def _resolve_framework_root(self) -> Path:
        if self._framework_root is not None:
            return self._framework_root
        return get_framework_root()

    async def health(self) -> dict[str, Any]:
        framework_root = self._resolve_framework_root()
        runner_path = get_runner_path(framework_root)
        if not framework_root.is_dir():
            raise Topic3CulturalCorpusUpstreamError(
                f"课题三文化语料 framework 目录不存在：{framework_root}；"
                "请配置 CULTURAL_CORPUS_GENERATOR_ROOT"
            )
        if not runner_path.is_file():
            raise Topic3CulturalCorpusUpstreamError(
                f"文化语料生成脚本不存在：{runner_path}"
            )
        api_key = resolve_generation_api_key(framework_root)
        if not api_key:
            api_key_env = (
                get_settings().cultural_corpus_generation_api_key_env.strip()
                or "DEEPSEEK_API_KEY"
            )
            raise Topic3CulturalCorpusUpstreamError(
                f"未在 Project_3 配置 {api_key_env}（请写入 framework/.env 或仓库根 .env，"
                f"或设置进程环境变量 {api_key_env}）"
            )
        return {
            "status": "ok",
            "service": "topic3-cultural-corpus-local",
            "framework_root": str(framework_root),
            "runner": str(runner_path),
            "api_key_configured": True,
        }

    async def stream_run(self, payload: dict[str, Any]) -> AsyncIterator[AgentEvent]:
        run_id = str(payload.get("run_id") or payload.get("task_id") or "").strip()
        if not run_id:
            raise Topic3CulturalCorpusProtocolError("stream_run payload missing run_id")

        try:
            job = await asyncio.to_thread(
                start_generation_job, {**payload, "run_id": run_id}, force_local=True
            )
        except FileExistsError as exc:
            raise Topic3CulturalCorpusUpstreamError(str(exc)) from exc
        except FileNotFoundError as exc:
            raise Topic3CulturalCorpusUpstreamError(str(exc)) from exc
        except RuntimeError as exc:
            raise Topic3CulturalCorpusUpstreamError(str(exc)) from exc
        except ValueError as exc:
            raise Topic3CulturalCorpusUpstreamError(str(exc)) from exc

        job_id = str(job.get("job_id") or run_id).strip()
        if not job_id:
            raise Topic3CulturalCorpusProtocolError("start job response missing job_id")
        self._last_job_id = job_id
        yield _status_event(job, message="topic3 cultural corpus job accepted")

        deadline = time.monotonic() + self.timeout
        last_progress_signature: tuple[Any, ...] | None = None

        while True:
            if time.monotonic() > deadline:
                yield AgentEvent(
                    "error",
                    {
                        "message": (
                            f"topic3 cultural corpus job timed out after {self.timeout:g}s"
                        ),
                        "job_id": job_id,
                    },
                )
                return

            await asyncio.sleep(self.poll_interval)
            try:
                status = await asyncio.to_thread(
                    get_generation_job_status, job_id, force_local=True
                )
            except KeyError:
                yield AgentEvent(
                    "error",
                    {
                        "message": f"unknown generation job: {job_id}",
                        "job_id": job_id,
                    },
                )
                return
            except RuntimeError as exc:
                yield AgentEvent(
                    "error",
                    {"message": str(exc), "job_id": job_id},
                )
                return

            yield _status_event(status)

            progress_event = _worker_progress_event(status)
            if progress_event is not None:
                signature = _worker_progress_signature(progress_event.data)
                if signature != last_progress_signature:
                    last_progress_signature = signature
                    yield progress_event

            if status.get("difficulty_level_counts"):
                yield AgentEvent(
                    "quality",
                    {
                        "job_id": job_id,
                        "difficulty_level_counts": status.get(
                            "difficulty_level_counts"
                        ),
                        "generated": status.get("generated"),
                        "total": status.get("total"),
                    },
                )

            state = str(status.get("status") or "").lower()
            if state == "completed":
                yield AgentEvent("done", {"reason": "completed", "job_id": job_id})
                return
            if state in {"failed", "error"}:
                yield AgentEvent(
                    "error",
                    {
                        "message": status.get("message")
                        or status.get("error")
                        or "topic3 cultural corpus job failed",
                        "job_id": job_id,
                    },
                )
                return
            if state == "stopped":
                yield AgentEvent(
                    "error",
                    {
                        "message": "topic3 cultural corpus job stopped before completion",
                        "job_id": job_id,
                    },
                )
                return

    async def download_latest_artifact(self) -> bytes:
        if not self._last_job_id:
            raise Topic3CulturalCorpusProtocolError(
                "cannot download artifact before job_id"
            )
        framework_root = self._resolve_framework_root()
        output_dir = framework_root / "runs" / self._last_job_id
        if not output_dir.is_dir():
            raise Topic3CulturalCorpusUpstreamError(
                f"generation output directory not found: {output_dir}"
            )
        samples_path = output_dir / "samples.jsonl"
        if not samples_path.is_file():
            raise Topic3CulturalCorpusUpstreamError(
                f"samples.jsonl missing under {output_dir}"
            )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ARTIFACT_MEMBER_NAMES:
                path = output_dir / name
                if path.is_file():
                    archive.write(path, arcname=name)
        return buffer.getvalue()


def _status_event(payload: dict[str, Any], *, message: str | None = None) -> AgentEvent:
    job_id = payload.get("job_id")
    generated = payload.get("generated")
    total = payload.get("total")
    progress = payload.get("progress")
    status = str(payload.get("status") or "running")
    parts = []
    if generated is not None and total is not None:
        parts.append(f"{generated}/{total}")
    if progress is not None:
        parts.append(f"{progress}%")
    return AgentEvent(
        "status",
        {
            "state": status,
            "message": message or " ".join(parts) or status,
            "job_id": job_id,
            "generated": generated,
            "total": total,
            "progress": progress,
        },
    )


def _worker_progress_event(payload: dict[str, Any]) -> AgentEvent | None:
    worker_state = payload.get("worker_state")
    if not isinstance(worker_state, dict):
        return None
    active_sample = worker_state.get("active_sample")
    if not isinstance(active_sample, dict):
        return None

    return AgentEvent(
        "lifecycle",
        {
            "stage": worker_state.get("phase") or "active_sample",
            "sample_id": active_sample.get("sample_id"),
            "job_id": payload.get("job_id"),
            "generated": payload.get("generated"),
            "total": payload.get("total"),
            "progress": payload.get("progress"),
            "attempt": worker_state.get("attempt"),
            "difficulty_level": active_sample.get("difficulty_level"),
            "ethnic_group": active_sample.get("implied_ethnic_group")
            or active_sample.get("ethnic_group"),
            "message": worker_state.get("message"),
        },
    )


def _worker_progress_signature(data: dict[str, Any]) -> tuple[Any, ...]:
    return (
        data.get("job_id"),
        data.get("sample_id"),
        data.get("attempt"),
        data.get("generated"),
        data.get("stage"),
        data.get("difficulty_level"),
        data.get("ethnic_group"),
    )
