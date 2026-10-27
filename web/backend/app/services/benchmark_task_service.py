from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.benchmark.topic2_autobench import (
    AgentEvent,
    Topic2AutoBenchAdapter,
    Topic2AutoBenchProtocolError,
    Topic2AutoBenchUpstreamError,
)
from app.adapters.benchmark.topic3_difficulty import (
    Topic3DifficultyAdapter,
    Topic3DifficultyProtocolError,
    Topic3DifficultyUpstreamError,
)
from app.adapters.benchmark.topic3_cultural_corpus import (
    Topic3CulturalCorpusAdapter,
    Topic3CulturalCorpusProtocolError,
    Topic3CulturalCorpusUpstreamError,
)
from app.adapters.benchmark.topic1_value_qa import (
    Topic1ValueQaCliAdapter,
    Topic1ValueQaProtocolError,
    Topic1ValueQaUpstreamError,
)
from app.adapters.benchmark.topic3_risk import (
    Topic3RiskCliAdapter,
    Topic3RiskProtocolError,
    Topic3RiskUpstreamError,
)
from app.core.config import get_settings
from app.db.models import BenchmarkAsset, BenchmarkTask, BenchmarkTaskLog
from app.db.session import AsyncSessionLocal
from app.schemas.benchmark import BenchmarkTaskCreate
from app.services.benchmark_artifact_service import (
    BenchmarkArtifactError,
    FrozenBenchmarkArtifact,
    freeze_autobench_artifact,
    freeze_topic1_value_qa_artifact,
    freeze_topic3_cultural_live_artifact,
    freeze_topic3_difficulty_artifact,
    freeze_topic3_risk_live_artifact,
)
from app.services.topic1_value_qa_retrieval import resolve_topic1_retrieval

logger = logging.getLogger(__name__)


class BenchmarkAdapterProtocol(Protocol):
    async def health(self) -> dict[str, Any]: ...

    def stream_run(self, payload: dict[str, Any]): ...

    async def download_latest_artifact(self) -> bytes: ...


def summarize_event(
    event_type: str, data: dict[str, Any]
) -> tuple[str | None, str | None, int | None]:
    if event_type == "status":
        return data.get("state"), data.get("message"), None
    if event_type == "thinking":
        return "thinking", data.get("text"), data.get("turn")
    if event_type == "tool_call":
        return data.get("name"), f"tool_call:{data.get('name')}", data.get("turn")
    if event_type == "tool_result":
        return data.get("name"), f"tool_result:{data.get('name')}", data.get("turn")
    if event_type == "lifecycle":
        return data.get("stage"), data.get("sample_id"), None
    if event_type == "error":
        return "error", data.get("message") or data.get("error"), data.get("turn")
    if event_type == "done":
        return "done", data.get("reason") or data.get("text"), data.get("turn")
    return None, None, None


def build_upstream_payload(
    agent_id: str, parameters: dict[str, Any], task_id: str
) -> dict[str, Any]:
    if agent_id == "topic1-value-qa":
        return {"task_id": task_id, "parameters": dict(parameters)}
    if agent_id == "topic3-risk-benchmark-generation":
        return {"task_id": task_id, "parameters": dict(parameters)}
    if agent_id == "topic3-difficulty-generation":
        return build_topic3_difficulty_payload(parameters, task_id)
    if agent_id == "topic3-cultural-corpus-generation":
        return {**parameters, "task_id": task_id, "run_id": task_id}
    if agent_id == "topic2-autobench":
        return build_topic2_autobench_payload(parameters, task_id)
    return {**parameters, "task_id": task_id, "run_id": task_id}


TOPIC2_UPSTREAM_PARAMETER_KEYS = frozenset(
    {
        "l1",
        "seed_l1",
        "l2",
        "seed_l2",
        "domains",
        "seed_types",
        "moderators",
        "language",
        "budget",
        "sampling_seed",
        "seed_file",
        "model",
        "max_turns",
        "request",
        "enable_detox",
    }
)


def build_topic2_autobench_payload(
    parameters: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Forward only AutoBench-known fields; keep scale/rewrite_strength on platform."""
    upstream = {
        key: parameters[key]
        for key in TOPIC2_UPSTREAM_PARAMETER_KEYS
        if key in parameters
    }
    upstream["task_id"] = task_id
    upstream["run_id"] = task_id
    return upstream


def build_topic3_difficulty_payload(
    parameters: dict[str, Any], task_id: str
) -> dict[str, Any]:
    settings = get_settings()
    total_sample_count = int(parameters["total_sample_count"])
    language = str(parameters["language"])
    difficulty_counts = dict(parameters["difficulty_counts"])
    generation_model = str(parameters["generation_model"])
    guard_model = str(parameters["guard_model"])
    risk_categories = [
        str(item).strip()
        for item in parameters.get("risk_categories") or []
        if str(item).strip()
    ]
    return {
        "run_id": task_id,
        "output_dir": f"runs/{task_id}",
        "harmful_seed_library": {
            "path": f"seed_data/{parameters['seed_dataset']}",
            "sources": [],
            "deduplicate": True,
        },
        "skill": {"path": "skills", "fail_on_quality_error": True},
        "generation": {
            "total_sample_count": total_sample_count,
            "resume": True,
            "language": language,
            "random_seed": int(parameters.get("sampling_seed") or 20260713),
            "sample_mode": "paired_mixed",
            "metric_targets": ["edit_success", "harmless_retention"],
            "data_origin_modes": ["splice_constructed"],
            "difficulty_sequence": ["H1", "H2", "H3", "H4"],
            "difficulty_counts": difficulty_counts,
            "risk_categories": risk_categories,
        },
        "harmless_companion_generator": {
            "api_base": settings.topic3_difficulty_vllm_api_base,
            "api_key_env": settings.topic3_difficulty_vllm_api_key_env,
            "model": generation_model,
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 768,
            "timeout": 180,
            "retries": 2,
            "max_attempts": 4,
            "harmful_candidate_window": 10,
            "min_chars": 24,
            "max_chars": 260,
            "chat_template_kwargs": {"enable_thinking": False},
            "guard": {
                "enabled": True,
                "api_base": settings.topic3_difficulty_vllm_api_base,
                "api_key_env": settings.topic3_difficulty_vllm_api_key_env,
                "model": guard_model,
                "timeout": 120,
                "retries": 2,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        },
        "final_guard": {
            "api_base": settings.topic3_difficulty_vllm_api_base,
            "api_key_env": settings.topic3_difficulty_vllm_api_key_env,
            "model": guard_model,
            "max_tokens": 64,
            "timeout": 120,
            "retries": 2,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "llm_composer": {
            "enabled": True,
            "api_base": settings.topic3_difficulty_vllm_api_base,
            "api_key_env": settings.topic3_difficulty_vllm_api_key_env,
            "model": generation_model,
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 768,
            "timeout": 180,
            "retries": 2,
            "concurrency": max(1, min(total_sample_count, 8)),
            "discard_retry_limit": 24,
            "bridge_review": {
                "enabled": True,
                "temperature": 0,
                "max_tokens": 256,
            },
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "llm": {"enabled": False},
        "seed_generation": {"enabled": False},
    }


def new_benchmark_task_id() -> str:
    return f"bench_{uuid.uuid4().hex[:12]}"


class BenchmarkTaskService:
    def __init__(
        self,
        *,
        adapter: BenchmarkAdapterProtocol | None = None,
        artifact_root: Path | None = None,
    ) -> None:
        self._adapter = adapter
        self._artifact_root = artifact_root

    def _get_adapter(self) -> BenchmarkAdapterProtocol:
        if self._adapter is not None:
            return self._adapter
        return Topic2AutoBenchAdapter.from_settings()

    def _get_adapter_for_agent(self, agent_id: str) -> BenchmarkAdapterProtocol:
        if self._adapter is not None:
            return self._adapter
        if agent_id == "topic1-value-qa":
            return Topic1ValueQaCliAdapter.from_settings()
        if agent_id == "topic3-risk-benchmark-generation":
            return Topic3RiskCliAdapter.from_settings()
        if agent_id == "topic3-difficulty-generation":
            return Topic3DifficultyAdapter.from_settings()
        if agent_id == "topic3-cultural-corpus-generation":
            return Topic3CulturalCorpusAdapter.from_settings()
        return Topic2AutoBenchAdapter.from_settings()

    def _get_artifact_root(self) -> Path:
        if self._artifact_root is not None:
            return self._artifact_root
        settings = get_settings()
        return Path(settings.benchmark_artifact_root)

    async def create_task(
        self, db: AsyncSession, request: BenchmarkTaskCreate
    ) -> BenchmarkTask:
        settings = get_settings()
        task = BenchmarkTask(
            task_id=new_benchmark_task_id(),
            agent_id=request.agent_id,
            mode=request.mode,
            status="pending",
            parameters_json=json.dumps(request.parameters, ensure_ascii=False),
            upstream_base_url=_agent_upstream_base_url(request.agent_id, settings),
            source_repo=_agent_source_repo(request.agent_id, settings),
            source_commit=_agent_source_commit(request.agent_id, settings),
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    async def run_task(self, db: AsyncSession, task_id: str) -> None:
        task = await self._get_task(db, task_id)
        if task is None:
            return

        await self._set_status(db, task, "validating")

        try:
            parameters = json.loads(task.parameters_json or "{}")
            BenchmarkTaskCreate(
                agent_id=task.agent_id,
                mode="live_run",
                parameters=parameters,
            )
        except Exception as exc:
            await self._fail_task(
                db,
                task,
                status="rejected",
                message=str(exc),
                event_type="validation",
            )
            return

        adapter = self._get_adapter_for_agent(task.agent_id)
        if task.agent_id == "topic1-value-qa":
            project_root = getattr(adapter, "project_root", None)
            if project_root is None:
                await self._fail_task(
                    db,
                    task,
                    status="failed",
                    message="topic1 value_qa adapter project_root is not configured",
                    event_type="validation",
                )
                return
            raw_topics = parameters.get("topics")
            topic_count = (
                len(
                    [
                        item
                        for item in raw_topics
                        if isinstance(item, str) and item.strip()
                    ]
                )
                if isinstance(raw_topics, list)
                else 1
            )
            if topic_count <= 1:
                parameters = resolve_topic1_retrieval(
                    project_root=Path(project_root),
                    parameters=parameters,
                )
                task.parameters_json = json.dumps(parameters, ensure_ascii=False)
                await db.commit()
                await db.refresh(task)

        try:
            await adapter.health()
        except _adapter_errors() as exc:
            await self._fail_task(
                db,
                task,
                status="failed",
                message=str(exc),
                event_type="upstream",
            )
            return
        except Exception as exc:
            await self._fail_task(
                db,
                task,
                status="failed",
                message=str(exc),
                event_type="upstream",
            )
            return

        await self._set_status(db, task, "running", started=True)
        saw_terminal_event = False
        artifact_url: str | None = None
        upstream_payload = build_upstream_payload(task.agent_id, parameters, task.task_id)
        logger.info(
            "Benchmark live run starting: task_id=%s agent_id=%s moderators=%s language=%s budget=%s model=%s",
            task.task_id,
            task.agent_id,
            parameters.get("moderators"),
            parameters.get("language"),
            parameters.get("budget"),
            parameters.get("model"),
        )

        try:
            async for event in adapter.stream_run(upstream_payload):
                await self._append_event_log(db, task_id, event)
                if event.event_type == "error":
                    saw_terminal_event = True
                    await self._fail_task(
                        db,
                        task,
                        status="failed",
                        message=event.data.get("message") or event.data.get("error"),
                        event_type="error",
                        write_log=False,
                    )
                    return
                if event.event_type == "done":
                    saw_terminal_event = True
                    if isinstance(event.data.get("artifact_url"), str):
                        artifact_url = event.data["artifact_url"]
                    logger.info(
                        "Benchmark live run done: task_id=%s agent_id=%s artifact_url=%s",
                        task.task_id,
                        task.agent_id,
                        artifact_url,
                    )
                    await self._set_status(db, task, "packaging")
                    await self._package_artifact(
                        db,
                        task,
                        adapter,
                        parameters,
                        artifact_url=artifact_url,
                    )
                    return
        except _adapter_errors() as exc:
            await self._fail_task(
                db,
                task,
                status="failed",
                message=str(exc),
                event_type="upstream",
            )
            return
        except Exception as exc:
            await self._fail_task(
                db,
                task,
                status="failed",
                message=str(exc),
                event_type="runtime",
            )
            return

        if not saw_terminal_event:
            await self._fail_task(
                db,
                task,
                status="failed",
                message="upstream SSE ended without done or error",
                event_type="upstream",
            )

    async def get_task(self, db: AsyncSession, task_id: str) -> BenchmarkTask | None:
        return await self._get_task(db, task_id)

    async def list_logs(
        self,
        db: AsyncSession,
        task_id: str,
        after_id: int | None = None,
        limit: int = 200,
    ) -> list[BenchmarkTaskLog]:
        query = (
            select(BenchmarkTaskLog)
            .where(BenchmarkTaskLog.task_id == task_id)
            .order_by(BenchmarkTaskLog.id.asc())
            .limit(limit)
        )
        if after_id is not None:
            query = query.where(BenchmarkTaskLog.id > after_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_artifacts(
        self, db: AsyncSession, task_id: str
    ) -> list[BenchmarkAsset]:
        result = await db.execute(
            select(BenchmarkAsset)
            .where(BenchmarkAsset.task_id == task_id)
            .order_by(BenchmarkAsset.id.asc())
        )
        return list(result.scalars().all())

    async def _package_artifact(
        self,
        db: AsyncSession,
        task: BenchmarkTask,
        adapter: BenchmarkAdapterProtocol,
        parameters: dict[str, Any],
        *,
        artifact_url: str | None = None,
    ) -> None:
        try:
            download_artifact = getattr(adapter, "download_artifact", None)
            if artifact_url and callable(download_artifact):
                logger.info(
                    "Downloading benchmark artifact: task_id=%s source=run artifact_url=%s",
                    task.task_id,
                    artifact_url,
                )
                artifact_bytes = await download_artifact(artifact_url)
            else:
                logger.info(
                    "Downloading benchmark artifact: task_id=%s source=latest",
                    task.task_id,
                )
                artifact_bytes = await adapter.download_latest_artifact()
            frozen = freeze_benchmark_artifact_for_agent(
                agent_id=task.agent_id,
                artifact_bytes=artifact_bytes,
                root_dir=self._get_artifact_root(),
                task_id=task.task_id,
                parameters=parameters,
                source_commit=task.source_commit or "",
                upstream_base_url=task.upstream_base_url or "",
                source_repo=task.source_repo,
            )
        except _artifact_errors() as exc:
            await self._fail_task(
                db,
                task,
                status="failed",
                message=str(exc),
                event_type="packaging",
            )
            return
        except Exception as exc:
            await self._fail_task(
                db,
                task,
                status="failed",
                message=str(exc),
                event_type="packaging",
            )
            return

        asset = BenchmarkAsset(
            asset_id=frozen.asset_id,
            task_id=task.task_id,
            source_mode=task.mode,
            name=str(frozen.manifest.get("name") or "Topic2 AutoBench live run"),
            manifest_json=json.dumps(frozen.manifest, ensure_ascii=False),
            artifact_dir=str(frozen.artifact_dir),
            artifact_zip_path=str(frozen.artifact_zip_path),
            artifact_sha256=frozen.artifact_sha256,
            source_repo=task.source_repo,
            source_commit=task.source_commit,
        )
        db.add(asset)
        task.asset_id = frozen.asset_id
        task.status = "completed"
        task.finished_at = datetime.utcnow()
        task.error_message = None
        db.add(
            BenchmarkTaskLog(
                task_id=task.task_id,
                event_type="artifact",
                stage="completed",
                message=_artifact_completed_message(frozen.manifest),
                turn=None,
                raw_json=json.dumps(
                    {
                        "asset_id": frozen.asset_id,
                        "sample_count": frozen.manifest.get("sample_count"),
                        "difficulty_distribution": frozen.manifest.get(
                            "difficulty_distribution"
                        ),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        await db.commit()

    async def _append_event_log(
        self, db: AsyncSession, task_id: str, event: AgentEvent
    ) -> None:
        stage, message, turn = summarize_event(event.event_type, event.data)
        db.add(
            BenchmarkTaskLog(
                task_id=task_id,
                event_type=event.event_type,
                stage=stage,
                message=message,
                turn=turn,
                raw_json=json.dumps(event.data, ensure_ascii=False),
            )
        )
        await db.commit()

    async def _set_status(
        self,
        db: AsyncSession,
        task: BenchmarkTask,
        status: str,
        *,
        started: bool = False,
    ) -> None:
        task.status = status
        task.updated_at = datetime.utcnow()
        if started and task.started_at is None:
            task.started_at = datetime.utcnow()
        await db.commit()

    async def _fail_task(
        self,
        db: AsyncSession,
        task: BenchmarkTask,
        *,
        status: str,
        message: str | None,
        event_type: str,
        write_log: bool = True,
    ) -> None:
        if write_log:
            db.add(
                BenchmarkTaskLog(
                    task_id=task.task_id,
                    event_type=event_type,
                    stage=status,
                    message=message,
                    turn=None,
                    raw_json=json.dumps({"message": message}, ensure_ascii=False),
                )
            )
        task.status = status
        task.error_message = message
        task.finished_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        await db.commit()

    async def _get_task(
        self, db: AsyncSession, task_id: str
    ) -> BenchmarkTask | None:
        result = await db.execute(
            select(BenchmarkTask).where(BenchmarkTask.task_id == task_id)
        )
        return result.scalar_one_or_none()


async def run_benchmark_task_in_background(task_id: str) -> None:
    async with AsyncSessionLocal() as db:
        service = BenchmarkTaskService()
        await service.run_task(db, task_id)


def _agent_upstream_base_url(agent_id: str, settings: Any) -> str:
    if agent_id == "topic1-value-qa":
        return settings.topic1_value_qa_llm_api_base or "cli://topic1-value-qa"
    if agent_id == "topic3-risk-benchmark-generation":
        return settings.topic3_risk_agent_url or "cli://topic3-risk-benchmark"
    if agent_id == "topic3-difficulty-generation":
        return settings.topic3_difficulty_base_url
    if agent_id == "topic3-cultural-corpus-generation":
        return "local://topic3-cultural-corpus"
    return settings.topic2_autobench_base_url


def _agent_source_repo(agent_id: str, settings: Any) -> str:
    if agent_id == "topic1-value-qa":
        return settings.topic1_value_qa_source_repo
    if agent_id == "topic3-risk-benchmark-generation":
        return settings.topic3_risk_benchmark_source_repo
    if agent_id == "topic3-difficulty-generation":
        return settings.topic3_difficulty_source_repo
    if agent_id == "topic3-cultural-corpus-generation":
        return settings.topic3_cultural_source_repo
    return settings.topic2_autobench_source_repo


def _agent_source_commit(agent_id: str, settings: Any) -> str:
    if agent_id == "topic1-value-qa":
        return settings.topic1_value_qa_source_commit
    if agent_id == "topic3-risk-benchmark-generation":
        return settings.topic3_risk_benchmark_source_commit
    if agent_id == "topic3-difficulty-generation":
        return settings.topic3_difficulty_source_commit
    if agent_id == "topic3-cultural-corpus-generation":
        return settings.topic3_cultural_source_commit
    return settings.topic2_autobench_source_commit


def _adapter_errors() -> tuple[type[Exception], ...]:
    return (
        Topic2AutoBenchProtocolError,
        Topic2AutoBenchUpstreamError,
        Topic3DifficultyProtocolError,
        Topic3DifficultyUpstreamError,
        Topic1ValueQaProtocolError,
        Topic1ValueQaUpstreamError,
        Topic3RiskProtocolError,
        Topic3RiskUpstreamError,
        Topic3CulturalCorpusProtocolError,
        Topic3CulturalCorpusUpstreamError,
    )


def _artifact_errors() -> tuple[type[Exception], ...]:
    return (BenchmarkArtifactError, *_adapter_errors())


def freeze_benchmark_artifact_for_agent(
    *,
    agent_id: str,
    artifact_bytes: bytes,
    root_dir: Path,
    task_id: str,
    parameters: dict[str, Any],
    source_commit: str,
    upstream_base_url: str,
    source_repo: str | None,
) -> FrozenBenchmarkArtifact:
    if agent_id == "topic1-value-qa":
        return freeze_topic1_value_qa_artifact(
            artifact_bytes=artifact_bytes,
            root_dir=root_dir,
            task_id=task_id,
            parameters=parameters,
            source_commit=source_commit,
            upstream_base_url=upstream_base_url,
            source_repo=source_repo,
        )
    if agent_id == "topic3-risk-benchmark-generation":
        return freeze_topic3_risk_live_artifact(
            artifact_bytes=artifact_bytes,
            root_dir=root_dir,
            task_id=task_id,
            parameters=parameters,
            source_commit=source_commit,
            upstream_base_url=upstream_base_url,
            source_repo=source_repo,
        )
    if agent_id == "topic3-difficulty-generation":
        return freeze_topic3_difficulty_artifact(
            artifact_bytes=artifact_bytes,
            root_dir=root_dir,
            task_id=task_id,
            parameters=parameters,
            source_commit=source_commit,
            upstream_base_url=upstream_base_url,
            source_repo=source_repo,
        )
    if agent_id == "topic3-cultural-corpus-generation":
        return freeze_topic3_cultural_live_artifact(
            artifact_bytes=artifact_bytes,
            root_dir=root_dir,
            task_id=task_id,
            parameters=parameters,
            source_commit=source_commit,
            upstream_base_url=upstream_base_url,
            source_repo=source_repo,
        )
    return freeze_autobench_artifact(
        artifact_bytes=artifact_bytes,
        root_dir=root_dir,
        task_id=task_id,
        parameters=parameters,
        source_commit=source_commit,
        upstream_base_url=upstream_base_url,
        source_repo=source_repo,
    )


def _artifact_completed_message(manifest: dict[str, Any]) -> str:
    sample_count = manifest.get("sample_count")
    distribution = manifest.get("difficulty_distribution")
    if isinstance(distribution, dict) and distribution:
        parts = ", ".join(f"{key}:{value}" for key, value in sorted(distribution.items()))
        if sample_count is not None:
            return f"artifact frozen; generated {sample_count} samples ({parts})"
        return f"artifact frozen ({parts})"
    if sample_count is not None:
        return f"artifact frozen; generated {sample_count} samples"
    return "artifact frozen"
