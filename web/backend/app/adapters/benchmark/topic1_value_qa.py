from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.benchmark.topic2_autobench import AgentEvent
from app.core.config import get_settings
from app.services.topic1_value_qa_retrieval import resolve_topic1_retrieval
from app.services.benchmark_topic1_value_qa_asset_service import (
    BenchmarkTopic1ValueQaAssetError,
    _build_quality_report,
    _group_preview,
    _load_jsonl,
    _normalize_sample_rows,
    _validate_complete_triplets,
    _write_jsonl,
)

logger = logging.getLogger(__name__)


class Topic1ValueQaUpstreamError(RuntimeError):
    """Raised when the topic1 value_qa CLI or runtime cannot run."""


class Topic1ValueQaProtocolError(RuntimeError):
    """Raised when the topic1 value_qa output cannot be adapted."""


class Topic1ValueQaCliAdapter:
    def __init__(
        self,
        *,
        project_root: Path,
        python_executable: str,
        timeout: float = 900.0,
        health_timeout: float = 5.0,
        llm_health_timeout: float = 2.0,
        llm_api_base: str = "",
        llm_model: str = "",
    ) -> None:
        self.project_root = project_root
        self.python_executable = python_executable
        self.timeout = timeout
        self.health_timeout = health_timeout
        self.llm_health_timeout = llm_health_timeout
        self.llm_api_base = llm_api_base
        self.llm_model = llm_model
        self._last_artifact_path: Path | None = None

    @classmethod
    def from_settings(cls) -> "Topic1ValueQaCliAdapter":
        settings = get_settings()
        project_root = _resolve_project_root(settings.topic1_value_qa_project_root)
        return cls(
            project_root=project_root,
            python_executable=_resolve_python_executable(
                project_root, settings.topic1_value_qa_python
            ),
            timeout=settings.topic1_value_qa_timeout_seconds,
            health_timeout=settings.topic1_value_qa_health_timeout_seconds,
            llm_health_timeout=settings.topic1_value_qa_llm_health_timeout_seconds,
            llm_api_base=settings.topic1_value_qa_llm_api_base,
            llm_model=settings.topic1_value_qa_llm_model,
        )

    async def health(self) -> dict[str, Any]:
        if not self.project_root.is_dir():
            raise Topic1ValueQaUpstreamError(
                f"topic1 value_qa project root not found: {self.project_root}"
            )
        cli_result = await _run_process(
            [
                self.python_executable,
                "-m",
                "benchmark.cli",
                "list-skills",
            ],
            cwd=self.project_root,
            timeout=self.health_timeout,
        )
        output = f"{cli_result.stdout}\n{cli_result.stderr}"
        if cli_result.returncode != 0:
            raise Topic1ValueQaUpstreamError(
                f"topic1 CLI health failed with code {cli_result.returncode}: "
                f"{_compact_text(output)}"
            )
        if "value_qa" not in output:
            raise Topic1ValueQaProtocolError("topic1 CLI list-skills missing value_qa")

        runtime = _read_topic1_runtime(
            self.project_root,
            llm_api_base_override=self.llm_api_base,
            llm_model_override=self.llm_model,
        )
        llm_status = await _probe_llm_runtime(runtime, timeout=self.llm_health_timeout)
        return {
            "status": "ok",
            "service": "topic1-value-qa-cli",
            "project_root": str(self.project_root),
            "python": self.python_executable,
            "llm_runtime": runtime,
            "llm_status": llm_status,
        }

    async def stream_run(self, payload: dict[str, Any]):
        task_id = str(payload.get("task_id") or "").strip()
        if not task_id:
            raise Topic1ValueQaProtocolError("payload missing task_id")
        parameters = dict(payload.get("parameters") or {})
        topics = _topic_list(parameters)
        if not topics:
            yield AgentEvent("error", {"message": "请填写主题"})
            return

        output_dir = self.project_root / "runs" / "project5_live_run" / task_id
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_samples_path = output_dir / "samples.raw.jsonl"
        worker_log_path = output_dir / "worker.log"
        log_parts: list[str] = []
        merged_rows: list[dict[str, Any]] = []
        deadline = time.monotonic() + float(self.timeout)

        for index, topic in enumerate(topics, 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                worker_log_path.write_text("\n\n".join(log_parts), encoding="utf-8")
                yield AgentEvent(
                    "error",
                    {"message": "主题生成超时，请减少主题数后重试"},
                )
                return

            yield AgentEvent(
                "status",
                {
                    "state": "starting" if index == 1 else "running",
                    "message": f"正在生成主题 {index}/{len(topics)}：{topic}",
                    "output_dir": str(output_dir),
                },
            )

            topic_parameters = dict(parameters)
            topic_parameters["topic"] = topic
            if str(topic_parameters.get("retrieval_mode") or "").strip() not in {
                "local_corpus",
                "online_baike",
            }:
                topic_parameters = resolve_topic1_retrieval(
                    project_root=self.project_root,
                    parameters=topic_parameters,
                )
            topic_raw = output_dir / f"samples.raw.{index}.jsonl"
            command = self._build_command(
                {**payload, "parameters": topic_parameters},
                topic_raw,
            )
            if index == 1:
                yield AgentEvent(
                    "status",
                    {
                        "state": "starting",
                        "message": "topic1 value_qa CLI starting",
                        "command": _redacted_command(command),
                        "output_dir": str(output_dir),
                    },
                )

            result = await _run_process(
                command,
                cwd=self.project_root,
                timeout=max(remaining, 1.0),
            )
            log_parts.append(_format_worker_log(command, result))
            for line in _interesting_log_lines(log_parts[-1]):
                yield AgentEvent("status", {"state": "running", "message": line})

            if result.returncode != 0:
                worker_log_path.write_text("\n\n".join(log_parts), encoding="utf-8")
                yield AgentEvent(
                    "error",
                    {"message": f"主题《{topic}》暂时无法生成"},
                )
                return

            if not topic_raw.is_file() or topic_raw.stat().st_size == 0:
                yield AgentEvent(
                    "status",
                    {
                        "state": "running",
                        "message": f"主题《{topic}》资料不足，已跳过",
                    },
                )
                continue
            try:
                merged_rows.extend(_load_jsonl(topic_raw, "samples_jsonl"))
            except (OSError, ValueError):
                yield AgentEvent(
                    "status",
                    {
                        "state": "running",
                        "message": f"主题《{topic}》资料不足，已跳过",
                    },
                )

        worker_log_path.write_text("\n\n".join(log_parts), encoding="utf-8")
        _write_jsonl(raw_samples_path, merged_rows)

        try:
            artifact_path, summary = self._build_artifact(
                payload=payload,
                output_dir=output_dir,
                raw_samples_path=raw_samples_path,
                worker_log_path=worker_log_path,
            )
        except (BenchmarkTopic1ValueQaAssetError, OSError, ValueError) as exc:
            yield AgentEvent("error", {"message": str(exc)})
            return

        self._last_artifact_path = artifact_path
        yield AgentEvent("quality", summary)
        yield AgentEvent("done", {"reason": "completed", **summary})

    async def download_latest_artifact(self) -> bytes:
        if self._last_artifact_path is None:
            raise Topic1ValueQaProtocolError("cannot download artifact before run")
        return self._last_artifact_path.read_bytes()

    def _build_command(self, payload: dict[str, Any], raw_samples_path: Path) -> list[str]:
        parameters = dict(payload.get("parameters") or {})
        command = [
            self.python_executable,
            "-m",
            "benchmark.cli",
            "generate-samples",
            "--skill-ids",
            "value_qa",
            "--samples-jsonl",
            str(raw_samples_path),
        ]
        generation_mode = str(parameters.get("generation_mode") or "topic")
        if generation_mode == "dimension":
            command.extend(["-d", str(parameters["dimension"])])
            command.extend(["-n", str(int(parameters.get("n_topics") or 1))])
        else:
            command.extend(["--topic", str(parameters["topic"])])

        command.extend(["-g", str(int(parameters["groups_per_topic"]))])
        language = _cli_language(str(parameters.get("language") or "zh"))
        command.extend(["--language", language])

        seed = parameters.get("seed")
        if seed is not None:
            command.extend(["--seed", str(int(seed))])

        if str(parameters.get("retrieval_mode") or "local_corpus") == "local_corpus":
            corpus_path = _resolve_corpus_path(
                self.project_root,
                str(parameters.get("corpus_jsonl") or ""),
            )
            command.extend(["--corpus-jsonl", str(corpus_path)])
        if str(parameters.get("scale") or "") in {"trial", "standard", "large"}:
            command.extend(["--skill-config", "facts_per_doc=2"])
        return command

    def _build_artifact(
        self,
        *,
        payload: dict[str, Any],
        output_dir: Path,
        raw_samples_path: Path,
        worker_log_path: Path,
    ) -> tuple[Path, dict[str, Any]]:
        parameters = dict(payload.get("parameters") or {})
        if not raw_samples_path.is_file():
            raise Topic1ValueQaProtocolError(
                _missing_raw_samples_message(worker_log_path)
            )
        rows = _load_jsonl(raw_samples_path, "samples_jsonl")
        normalized_rows = _normalize_sample_rows(
            rows,
            prompt_snapshot=get_settings().topic1_value_qa_prompt_snapshot,
        )
        groups = _validate_complete_triplets(normalized_rows)
        requested_group_count = _requested_group_count(parameters)
        generated_group_count = len(groups)
        if generated_group_count < 1:
            raise Topic1ValueQaProtocolError("topic1 value_qa generated 0 complete groups")

        warnings: list[str] = []
        if generated_group_count < requested_group_count:
            warnings.append(
                "generated_group_count is lower than requested_group_count; "
                "topic1 value_qa CLI uses best-effort generation"
            )

        samples_path = output_dir / "samples.jsonl"
        group_preview_path = output_dir / "group_preview.jsonl"
        quality_report_path = output_dir / "quality_report.json"
        lineage_path = output_dir / "lineage.jsonl"
        manifest_path = output_dir / "manifest.json"
        artifact_path = output_dir / "topic1_value_qa_artifacts.zip"

        _write_jsonl(samples_path, normalized_rows)
        _write_jsonl(group_preview_path, _group_preview(groups))
        quality_report = _build_quality_report(
            rows=normalized_rows,
            groups=groups,
            marks_summary={"status": "not_run", "marked_sample_count": 0},
            qc_summary={"status": "structure_only", "scope": "structure_only"},
            trace_summary={"status": "not_run", "scope": "not_run"},
        )
        quality_report["validation"] = {
            "scope": "structure_only",
            "passed": True,
            "requested_group_count": requested_group_count,
            "generated_group_count": generated_group_count,
        }
        quality_report_path.write_text(
            json.dumps(quality_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        lineage_rows = [
            {
                "role": "raw_cli_samples",
                "path": str(raw_samples_path),
                "status": "generated",
            },
            {
                "role": "worker_log",
                "path": str(worker_log_path),
                "status": "generated",
            },
        ]
        _write_jsonl(lineage_path, lineage_rows)

        runtime = _read_topic1_runtime(
            self.project_root,
            llm_api_base_override=self.llm_api_base,
            llm_model_override=self.llm_model,
        )
        manifest = {
            "schema_version": "topic1-value-qa-live-run-artifact-v0.1",
            "task_id": payload.get("task_id"),
            "agent_id": "topic1-value-qa",
            "benchmark_type": "value_qa",
            "schema_id": "topic1.value_qa.v0.1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters,
            "requested_group_count": requested_group_count,
            "generated_group_count": generated_group_count,
            "sample_count": len(normalized_rows),
            "quality_level_distribution": quality_report[
                "quality_level_distribution"
            ],
            "retrieval": {
                "mode": parameters.get("retrieval_mode") or "local_corpus",
                "corpus_jsonl": parameters.get("corpus_jsonl"),
            },
            "llm_runtime": runtime,
            "warnings": warnings,
            "files": {
                "samples": "samples.jsonl",
                "group_preview": "group_preview.jsonl",
                "quality_report": "quality_report.json",
                "lineage": "lineage.jsonl",
                "worker_log": "worker.log",
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with zipfile.ZipFile(artifact_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in (
                manifest_path,
                samples_path,
                group_preview_path,
                quality_report_path,
                lineage_path,
                worker_log_path,
            ):
                archive.write(path, arcname=path.name)

        return artifact_path, {
            "requested_group_count": requested_group_count,
            "generated_group_count": generated_group_count,
            "sample_count": len(normalized_rows),
            "warnings": warnings,
        }


async def read_topic1_llm_runtime(adapter: Topic1ValueQaCliAdapter) -> dict[str, Any]:
    """Read topic1 LLM env without running CLI health checks."""
    if not adapter.project_root.is_dir():
        return {
            "runtime_ready": False,
            "runtime_source": "missing",
            "project_root": str(adapter.project_root),
            "llm_runtime": _public_llm_runtime({}),
            "llm_status": {
                "status": "not_configured",
                "message": "topic1 value_qa project root not found",
            },
        }

    runtime = _read_topic1_runtime(
        adapter.project_root,
        llm_api_base_override=adapter.llm_api_base,
        llm_model_override=adapter.llm_model,
    )
    llm_runtime = _public_llm_runtime(runtime)
    if not llm_runtime["api_base"]:
        return {
            "runtime_ready": True,
            "runtime_source": "project1_env",
            "project_root": str(adapter.project_root),
            "llm_runtime": llm_runtime,
            "llm_status": {
                "status": "not_configured",
                "message": "LLM_API_BASE is not configured",
            },
        }

    try:
        llm_status = await _probe_llm_runtime(runtime, timeout=adapter.llm_health_timeout)
    except (Topic1ValueQaUpstreamError, httpx.RequestError) as exc:
        return {
            "runtime_ready": True,
            "runtime_source": "project1_env",
            "project_root": str(adapter.project_root),
            "llm_runtime": llm_runtime,
            "llm_status": {
                "status": "unreachable",
                "message": str(exc),
            },
        }

    return {
        "runtime_ready": True,
        "runtime_source": "project1_env",
        "project_root": str(adapter.project_root),
        "llm_runtime": llm_runtime,
        "llm_status": llm_status,
    }


class _ProcessResult:
    def __init__(self, *, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


async def _run_process(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
) -> _ProcessResult:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_child_env(),
        )
    except OSError as exc:
        raise Topic1ValueQaUpstreamError(f"cannot start topic1 CLI: {exc}") from exc
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise Topic1ValueQaUpstreamError(
            f"topic1 CLI timed out after {timeout:g}s"
        ) from exc
    return _ProcessResult(
        returncode=int(process.returncode or 0),
        stdout=_decode_output(stdout_bytes),
        stderr=_decode_output(stderr_bytes),
    )


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("NO_COLOR", "1")
    return env


def _resolve_project_root(value: str) -> Path:
    if value.strip():
        return Path(value).expanduser().resolve()
    current = Path(__file__).resolve()
    project5_root = current.parents[5]
    return (project5_root.parent / "Project_1_Sample_evaluation_Generation").resolve()


def _resolve_python_executable(project_root: Path, value: str) -> str:
    if value.strip():
        return str(Path(value).expanduser().resolve())
    candidates = [
        project_root / ".venv" / "bin" / "python",
        project_root / "venv" / "bin" / "python",
        project_root / ".venv-win" / "Scripts" / "python.exe",
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / "venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            # WSL-created venv symlinks are unreadable from native Windows.
            continue
    return "python3" if os.name != "nt" else "python"


def _resolve_corpus_path(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_root / path
    path = path.resolve()
    if not path.is_file():
        raise Topic1ValueQaUpstreamError(f"corpus_jsonl not found: {path}")
    return path


def _missing_raw_samples_message(worker_log_path: Path) -> str:
    log_text = ""
    if worker_log_path.is_file():
        try:
            log_text = worker_log_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            log_text = worker_log_path.read_text(encoding="utf-8", errors="replace")
    reason = _extract_zero_sample_reason(log_text)
    if reason:
        logger.warning("topic1 value_qa zero samples; cli_reason=%s", reason)
    # Keep user-facing copy free of CLI reason / retrieval impl terms.
    return (
        "当前主题公开资料不足，未能生成样本。"
        "请换一个资料更完整的主题后重试，或把任务 ID 发给对接人。"
    )


def _extract_zero_sample_reason(log_text: str) -> str:
    for line in log_text.splitlines():
        match = re.search(r"原因[:：]\s*(.+?)[。.]?$", line.strip())
        if match:
            return match.group(1).strip()
    for line in log_text.splitlines():
        if "Generated 0 samples" in line:
            return "CLI 返回 Generated 0 samples"
    return ""


def _public_llm_runtime(runtime: dict[str, Any]) -> dict[str, str]:
    api_base = str(runtime.get("api_base") or "").strip()
    parsed = urlparse(api_base)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    return {
        "provider": str(runtime.get("provider") or ""),
        "model": str(runtime.get("model") or ""),
        "api_base": api_base,
        "api_base_origin": origin,
    }


def _read_topic1_runtime(
    project_root: Path,
    *,
    llm_api_base_override: str = "",
    llm_model_override: str = "",
) -> dict[str, Any]:
    values = _read_env_file(project_root / ".env.example")
    values.update(_read_env_file(project_root / ".env"))
    api_base = llm_api_base_override.strip() or values.get("LLM_API_BASE", "")
    model = llm_model_override.strip() or values.get("LLM_MODEL", "")
    return {
        "enabled": values.get("LLM_ENABLED", "true"),
        "provider": values.get("LLM_PROVIDER", "openai_compatible"),
        "model": model,
        "api_base": api_base,
        "timeout_seconds": values.get("LLM_TIMEOUT_SECONDS", ""),
        "request_retries": values.get("LLM_REQUEST_RETRIES", ""),
    }


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


async def _probe_llm_runtime(runtime: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    api_base = str(runtime.get("api_base") or "").rstrip("/")
    if not api_base:
        raise Topic1ValueQaUpstreamError("topic1 LLM_API_BASE is not configured")
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(f"{api_base}/models")
    except httpx.RequestError as exc:
        raise Topic1ValueQaUpstreamError(
            f"topic1 LLM endpoint is not reachable: {api_base}"
        ) from exc
    if response.status_code >= 500:
        raise Topic1ValueQaUpstreamError(
            f"topic1 LLM endpoint failed with status {response.status_code}"
        )
    return {"status": "reachable", "status_code": response.status_code}


def _topic_list(parameters: dict[str, Any]) -> list[str]:
    raw = parameters.get("topics")
    if isinstance(raw, list):
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            text = str(item).strip() if item is not None else ""
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        if out:
            return out
    topic = str(parameters.get("topic") or "").strip()
    return [topic] if topic else []


def _requested_group_count(parameters: dict[str, Any]) -> int:
    generation_mode = str(parameters.get("generation_mode") or "topic")
    if generation_mode == "topic":
        n_topics = len(_topic_list(parameters)) or 1
    else:
        n_topics = int(parameters.get("n_topics") or 1)
    return n_topics * int(parameters.get("groups_per_topic") or 1)


def _cli_language(value: str) -> str:
    if value == "zh":
        return "zh-CN"
    return value


def _decode_output(value: bytes | None) -> str:
    text = (value or b"").decode("utf-8", errors="replace")
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _format_worker_log(command: list[str], result: _ProcessResult) -> str:
    return "\n".join(
        [
            "$ " + " ".join(_redacted_command(command)),
            f"exit_code={result.returncode}",
            "",
            "[stdout]",
            result.stdout,
            "",
            "[stderr]",
            result.stderr,
            "",
        ]
    )


def _interesting_log_lines(text: str) -> list[str]:
    lines = [_compact_text(line) for line in text.splitlines()]
    return [
        line
        for line in lines
        if line
        and (
            "Generated" in line
            or "verified" in line
            or "请求" in line
            or "warning" in line.lower()
            or "topic" in line.lower()
        )
    ][:20]


def _compact_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _redacted_command(command: list[str]) -> list[str]:
    return [str(item) for item in command]
