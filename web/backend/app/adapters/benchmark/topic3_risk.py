from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse, urlunparse

import httpx

from app.adapters.benchmark.topic2_autobench import AgentEvent
from app.core.config import get_settings
from app.services.benchmark_topic3_risk_asset_service import (
    BenchmarkTopic3RiskAssetError,
    _load_and_validate_jsonl,
)


GENERATE_SCRIPT = Path("qwen_agent_server") / "live_run_adapter.py"
QA_SCRIPT = Path("qwen_agent_server") / "qa_risk_dataset.py"
TAXONOMY_CANDIDATES = (
    Path("risk_skills_v3") / "memory" / "canonical_taxonomy_17x60.md",
    Path("generated_data") / "workflow_v3" / "final" / "canonical_taxonomy_17x60.md",
)
TRIAL_TARGET_PER_KIND = 5
AGENT_ID = "topic3-risk-benchmark-generation"
BENCHMARK_TYPE = "risk_content_generation"


class Topic3RiskUpstreamError(RuntimeError):
    """Raised when the topic3 risk CLI or Agent runtime cannot run."""


class Topic3RiskProtocolError(RuntimeError):
    """Raised when the topic3 risk output cannot be adapted."""


class Topic3RiskCliAdapter:
    def __init__(
        self,
        *,
        project_root: Path,
        python_executable: str,
        agent_url: str,
        qwen_api_base: str = "",
        timeout: float = 900.0,
        health_timeout: float = 5.0,
        workers: int = 1,
    ) -> None:
        self.project_root = project_root
        self.python_executable = python_executable
        self.agent_url = agent_url
        self.qwen_api_base = qwen_api_base
        self.timeout = timeout
        self.health_timeout = health_timeout
        self.workers = workers
        self._last_artifact_path: Path | None = None

    @classmethod
    def from_settings(cls) -> "Topic3RiskCliAdapter":
        settings = get_settings()
        project_root = _resolve_project_root(
            getattr(settings, "topic3_risk_benchmark_project_root", "") or ""
        )
        return cls(
            project_root=project_root,
            python_executable=_resolve_python_executable(
                project_root,
                getattr(settings, "topic3_risk_benchmark_python", "") or "",
            ),
            agent_url=str(
                getattr(settings, "topic3_risk_agent_url", "")
                or "http://127.0.0.1:6351/chat"
            ),
            qwen_api_base=str(
                getattr(settings, "topic3_risk_qwen_api_base", "")
                or "http://127.0.0.1:6352/v1"
            ),
            timeout=float(
                getattr(settings, "topic3_risk_timeout_seconds", 900.0) or 900.0
            ),
            health_timeout=float(
                getattr(settings, "topic3_risk_health_timeout_seconds", 5.0) or 5.0
            ),
            workers=int(getattr(settings, "topic3_risk_workers", 1) or 1),
        )

    async def health(self) -> dict[str, Any]:
        if not self.project_root.is_dir():
            raise Topic3RiskUpstreamError(
                f"课题三动态风险仓库不存在：{self.project_root}。"
                "请配置 TOPIC3_RISK_BENCHMARK_PROJECT_ROOT。"
            )
        generate_script = self.project_root / GENERATE_SCRIPT
        qa_script = self.project_root / QA_SCRIPT
        if not generate_script.is_file():
            raise Topic3RiskUpstreamError(
                f"动态风险生成脚本不存在：{generate_script}。"
                "live_run 需要课题三完成参数化 CLI（见 2026-08-14 CLI 契约）。"
            )
        if not qa_script.is_file():
            raise Topic3RiskUpstreamError(
                f"动态风险 QA 脚本不存在：{qa_script}。"
            )

        await self._assert_generate_cli_parameterized(generate_script)

        health_url = _agent_health_url(self.agent_url)
        agent_status = await _probe_http(health_url, timeout=self.health_timeout)
        if agent_status != "ok":
            raise Topic3RiskUpstreamError(
                f"课题三动态风险 Agent 不可用（{health_url}）。"
                "请在 176 启动 llmsafe-topic3-risk-agent（:6351）；"
                "不要把 TOPIC3_RISK_AGENT_URL 改成动态难度 Agent :6331。"
            )

        qwen_status = "skipped"
        if self.qwen_api_base.strip():
            models_url = self.qwen_api_base.rstrip("/") + "/models"
            qwen_status = await _probe_http(models_url, timeout=min(self.health_timeout, 2.0))
            if qwen_status != "ok":
                raise Topic3RiskUpstreamError(
                    f"课题三动态风险 Qwen 接口不可用（{models_url}）。"
                    "176+182 应复用动态难度 router :6332，而不是单独起 :6352。"
                )

        return {
            "status": "ok",
            "service": "topic3-risk-benchmark-cli",
            "project_root": str(self.project_root),
            "python": self.python_executable,
            "agent_url": self.agent_url,
            "agent_health": health_url,
            "qwen_api_base": self.qwen_api_base,
            "qwen_status": qwen_status,
        }

    async def _assert_generate_cli_parameterized(self, generate_script: Path) -> None:
        # Keep project cwd so real argparse scripts can import; isolate OUT_DIR so a
        # legacy script that treats --help as a normal run cannot append shared jsonl.
        with tempfile.TemporaryDirectory(prefix="topic3-risk-cli-help-") as tmp:
            help_out = Path(tmp)
            help_result = await _run_process(
                [self.python_executable, str(generate_script), "--help"],
                cwd=self.project_root,
                timeout=min(max(self.health_timeout, 1.0), 8.0),
                extra_env={"OUT_DIR": str(help_out)},
            )
        if help_result.returncode != 0:
            raise Topic3RiskUpstreamError(
                "动态风险生成脚本 --help 失败（exit "
                f"{help_result.returncode}）：{_compact_text(help_result.stderr or help_result.stdout)}"
            )
        help_text = f"{help_result.stdout}\n{help_result.stderr}"
        if not re.search(r"(?i)\busage:", help_text):
            raise Topic3RiskUpstreamError(
                "动态风险生成脚本 --help 未输出 usage:，可能不是参数化 argparse CLI。"
                "见 2026-08-14 CLI 契约；请勿用旧版 generate_safe_low_400.py 开跑。"
            )
        required_flags = ("--task-id", "--out-dir", "--target-per-kind")
        missing = [
            flag for flag in required_flags if not _help_text_has_cli_flag(help_text, flag)
        ]
        if missing:
            raise Topic3RiskUpstreamError(
                "动态风险生成脚本尚未完成参数化 CLI（缺少 "
                + ", ".join(missing)
                + "）。见 2026-08-14 CLI 契约；请勿用旧版 generate_safe_low_400.py 开跑。"
            )

    async def stream_run(self, payload: dict[str, Any]):
        task_id = str(payload.get("task_id") or "").strip()
        if not task_id:
            raise Topic3RiskProtocolError("payload missing task_id")
        parameters = dict(payload.get("parameters") or {})
        target_per_kind = int(parameters.get("target_per_kind") or TRIAL_TARGET_PER_KIND)
        workers = int(parameters.get("workers") or self.workers)
        output_dir = self.project_root / "runs" / "project5_live_run" / task_id
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            _clear_stale_live_run_outputs(output_dir)
        except Topic3RiskProtocolError as exc:
            yield AgentEvent("error", {"message": str(exc)})
            return
        worker_log_path = output_dir / "worker.log"

        generate_command = self._build_generate_command(
            task_id=task_id,
            output_dir=output_dir,
            target_per_kind=target_per_kind,
            workers=workers,
        )
        yield AgentEvent(
            "status",
            {
                "state": "starting",
                "message": "topic3 risk CLI starting",
                "command": _redacted_command(generate_command),
                "output_dir": str(output_dir),
            },
        )

        event_queue: asyncio.Queue[AgentEvent] = asyncio.Queue()

        async def _on_generate_event(event: AgentEvent) -> None:
            await event_queue.put(event)

        generate_task = asyncio.create_task(
            _run_process(
                generate_command,
                cwd=self.project_root,
                timeout=self.timeout,
                extra_env={
                    "AGENT_URL": self.agent_url,
                    "OUT_DIR": str(output_dir),
                    "QWEN_API_BASE": self.qwen_api_base,
                },
                on_event=_on_generate_event,
            )
        )
        generate_result: _ProcessResult | None = None
        cli_error_message: str | None = None
        log_chunks: list[str] = []
        try:
            while True:
                if generate_task.done() and event_queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    if generate_task.done():
                        break
                    continue
                yield event
                if event.event_type == "error":
                    cli_error_message = str(
                        event.data.get("message")
                        or event.data.get("error")
                        or "upstream error"
                    )
                    break

            try:
                generate_result = await generate_task
            except Topic3RiskUpstreamError:
                worker_log_path.write_text(
                    "generate timed out or failed before completion\n",
                    encoding="utf-8",
                )
                raise

            while not event_queue.empty():
                event = event_queue.get_nowait()
                yield event
                if event.event_type == "error" and cli_error_message is None:
                    cli_error_message = str(
                        event.data.get("message")
                        or event.data.get("error")
                        or "upstream error"
                    )

            assert generate_result is not None
            log_chunks = [_format_worker_log("generate", generate_command, generate_result)]
            if cli_error_message is not None:
                worker_log_path.write_text("\n\n".join(log_chunks), encoding="utf-8")
                return

            if generate_result.returncode != 0:
                worker_log_path.write_text("\n\n".join(log_chunks), encoding="utf-8")
                yield AgentEvent(
                    "error",
                    {
                        "message": (
                            f"topic3 risk generate CLI failed with code "
                            f"{generate_result.returncode}: "
                            f"{_compact_text(generate_result.stderr or generate_result.stdout)}"
                        )
                    },
                )
                return
        finally:
            if not generate_task.done():
                generate_task.cancel()
                try:
                    await generate_task
                except (asyncio.CancelledError, Topic3RiskUpstreamError):
                    pass

        assert generate_result is not None
        if _trial_qa_report_ready(output_dir):
            yield AgentEvent(
                "status",
                {"state": "running", "message": "topic3 risk QA skipped (wrapper report present)"},
            )
            worker_log_path.write_text("\n\n".join(log_chunks), encoding="utf-8")
        else:
            qa_command = self._build_qa_command(output_dir)
            yield AgentEvent(
                "status",
                {"state": "running", "message": "topic3 risk QA starting"},
            )
            qa_result = await _run_process(
                qa_command,
                cwd=self.project_root,
                timeout=min(self.timeout, 120.0),
            )
            log_chunks.append(_format_worker_log("qa", qa_command, qa_result))
            worker_log_path.write_text("\n\n".join(log_chunks), encoding="utf-8")
            for event in _events_from_output(qa_result.stdout):
                yield event
            if qa_result.returncode != 0:
                yield AgentEvent(
                    "error",
                    {
                        "message": (
                            f"topic3 risk QA failed with code {qa_result.returncode}: "
                            f"{_compact_text(qa_result.stderr or qa_result.stdout)}"
                        )
                    },
                )
                return

        try:
            artifact_path, summary = self._build_artifact(
                payload=payload,
                output_dir=output_dir,
                worker_log_path=worker_log_path,
                target_per_kind=target_per_kind,
            )
        except (Topic3RiskProtocolError, BenchmarkTopic3RiskAssetError, OSError, ValueError) as exc:
            yield AgentEvent("error", {"message": str(exc)})
            return

        self._last_artifact_path = artifact_path
        yield AgentEvent("quality", summary)
        yield AgentEvent("done", {"reason": "completed", **summary})

    async def download_latest_artifact(self) -> bytes:
        if self._last_artifact_path is None:
            raise Topic3RiskProtocolError("cannot download artifact before run")
        return self._last_artifact_path.read_bytes()

    def _build_generate_command(
        self,
        *,
        task_id: str,
        output_dir: Path,
        target_per_kind: int,
        workers: int,
    ) -> list[str]:
        return [
            self.python_executable,
            str(self.project_root / GENERATE_SCRIPT),
            "--task-id",
            task_id,
            "--target-per-kind",
            str(target_per_kind),
            "--workers",
            str(workers),
            "--out-dir",
            str(output_dir),
            "--agent-url",
            self.agent_url,
        ]

    def _build_qa_command(self, output_dir: Path) -> list[str]:
        return [
            self.python_executable,
            str(self.project_root / QA_SCRIPT),
            str(output_dir / "safe.jsonl"),
            str(output_dir / "low.jsonl"),
            "--mode",
            "trial",
            "--out",
            str(output_dir / "qa_report.json"),
        ]

    def _build_artifact(
        self,
        *,
        payload: dict[str, Any],
        output_dir: Path,
        worker_log_path: Path,
        target_per_kind: int,
    ) -> tuple[Path, dict[str, Any]]:
        parameters = dict(payload.get("parameters") or {})
        safe_path = output_dir / "safe.jsonl"
        low_path = output_dir / "low.jsonl"
        if not safe_path.is_file() or not low_path.is_file():
            raise Topic3RiskProtocolError(
                f"topic3 risk CLI did not write safe.jsonl/low.jsonl under {output_dir}"
            )

        safe_rows = _load_and_validate_jsonl(
            safe_path, expected_level="safe", expected_safetype="safe"
        )
        low_rows = _load_and_validate_jsonl(
            low_path, expected_level="low", expected_safetype="unsafe"
        )
        if len(safe_rows) != target_per_kind or len(low_rows) != target_per_kind:
            raise Topic3RiskProtocolError(
                "topic3 risk trial expected "
                f"{target_per_kind} safe + {target_per_kind} low rows, "
                f"got {len(safe_rows)} safe + {len(low_rows)} low"
            )

        samples_path = output_dir / "samples.jsonl"
        samples_path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False) + "\n"
                for row in [*safe_rows, *low_rows]
            ),
            encoding="utf-8",
        )

        taxonomy_path = output_dir / "canonical_taxonomy_17x60.md"
        if not taxonomy_path.is_file():
            source = _find_taxonomy(self.project_root)
            if source is not None:
                taxonomy_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        qa_path = output_dir / "qa_report.json"
        if not qa_path.is_file():
            raise Topic3RiskProtocolError(
                f"topic3 risk QA did not write qa_report.json under {output_dir}"
            )
        qa_report = _load_json_object(qa_path)
        manifest_path = output_dir / "manifest.json"
        manifest = {
            "schema_version": "topic3-risk-live-run-artifact-v0.1",
            "task_id": payload.get("task_id"),
            "agent_id": AGENT_ID,
            "benchmark_type": BENCHMARK_TYPE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters,
            "qa_mode": "trial",
            "category_balance_required": False,
            "target_per_kind": target_per_kind,
            "safe_count": len(safe_rows),
            "low_count": len(low_rows),
            "sample_count": len(safe_rows) + len(low_rows),
            "qa_report": qa_report,
            "files": {
                "safe": "safe.jsonl",
                "low": "low.jsonl",
                "samples": "samples.jsonl",
                "qa_report": "qa_report.json",
                "taxonomy": (
                    "canonical_taxonomy_17x60.md" if taxonomy_path.is_file() else None
                ),
                "worker_log": "worker.log",
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        artifact_path = output_dir / "topic3_risk_artifacts.zip"
        members = [
            manifest_path,
            samples_path,
            safe_path,
            low_path,
            qa_path,
            worker_log_path,
        ]
        if taxonomy_path.is_file():
            members.append(taxonomy_path)
        with zipfile.ZipFile(artifact_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in members:
                archive.write(path, arcname=path.name)

        return artifact_path, {
            "sample_count": len(safe_rows) + len(low_rows),
            "safe_count": len(safe_rows),
            "low_count": len(low_rows),
            "qa_mode": "trial",
        }


_STALE_LIVE_RUN_OUTPUTS = (
    "qa_report.json",
    "safe.jsonl",
    "low.jsonl",
    "samples.jsonl",
    "manifest.json",
    "topic3_risk_artifacts.zip",
)


def _clear_stale_live_run_outputs(output_dir: Path) -> None:
    for name in _STALE_LIVE_RUN_OUTPUTS:
        path = output_dir / name
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise Topic3RiskProtocolError(
                f"could not clear stale live_run output {path.name}: {exc}"
            ) from exc


def _trial_qa_report_ready(output_dir: Path) -> bool:
    path = output_dir / "qa_report.json"
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(payload, dict) and str(payload.get("mode") or "").strip() == "trial"


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
    extra_env: dict[str, str] | None = None,
    on_event: Callable[[AgentEvent], Awaitable[None]] | None = None,
) -> _ProcessResult:
    env = _child_env()
    if extra_env:
        env.update(extra_env)
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except OSError as exc:
        raise Topic3RiskUpstreamError(f"cannot start topic3 risk CLI: {exc}") from exc

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    saw_cli_error = False

    def _kill_process() -> None:
        if process.returncode is not None:
            return
        try:
            process.kill()
        except ProcessLookupError:
            return

    async def pump_stdout() -> None:
        nonlocal saw_cli_error
        assert process.stdout is not None
        while True:
            raw = await process.stdout.readline()
            if not raw:
                break
            line = _decode_output(raw).rstrip("\r\n")
            stdout_parts.append(line)
            if on_event is None or saw_cli_error:
                continue
            for event in _events_from_output(line + "\n"):
                await on_event(event)
                if event.event_type == "error":
                    saw_cli_error = True
                    _kill_process()
                    # Keep draining so a noisy CLI cannot block the pipe forever.

    async def pump_stderr() -> None:
        assert process.stderr is not None
        while True:
            raw = await process.stderr.readline()
            if not raw:
                break
            stderr_parts.append(_decode_output(raw).rstrip("\r\n"))

    try:
        await asyncio.wait_for(
            asyncio.gather(pump_stdout(), pump_stderr()),
            timeout=timeout,
        )
        if process.returncode is None:
            if saw_cli_error:
                _kill_process()
            await asyncio.wait_for(process.wait(), timeout=max(1.0, timeout / 10))
    except asyncio.TimeoutError as exc:
        _kill_process()
        await process.wait()
        raise Topic3RiskUpstreamError(
            f"topic3 risk CLI timed out after {timeout:g}s"
        ) from exc
    except asyncio.CancelledError:
        _kill_process()
        await process.wait()
        raise

    return _ProcessResult(
        returncode=int(process.returncode or (1 if saw_cli_error else 0)),
        stdout="\n".join(stdout_parts),
        stderr="\n".join(stderr_parts),
    )


def _help_text_has_cli_flag(help_text: str, flag: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", help_text) is not None


async def _probe_http(url: str, *, timeout: float) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return "unreachable"
    return "ok" if 200 <= response.status_code < 400 else f"http_{response.status_code}"


def _resolve_project_root(value: str) -> Path:
    if value.strip():
        return Path(value).expanduser().resolve()
    current = Path(__file__).resolve()
    project5_root = current.parents[5]
    return (project5_root.parent / "Project_3_Dynamic_Risk_Benchmark_Generation").resolve()


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
        if candidate.is_file():
            return str(candidate)
    return "python3" if os.name != "nt" else "python"


def _agent_health_url(agent_url: str) -> str:
    parsed = urlparse(agent_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/chat"):
        path = path[: -len("/chat")] + "/health"
    elif not path or path == "/":
        path = "/health"
    else:
        path = path + "/health"
    return urlunparse(parsed._replace(path=path, query="", fragment=""))


def _find_taxonomy(project_root: Path) -> Path | None:
    for relative in TAXONOMY_CANDIDATES:
        candidate = project_root / relative
        if candidate.is_file():
            return candidate
    return None


def _events_from_output(stdout: str) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    for line in stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            events.append(AgentEvent("status", {"state": "running", "message": text[:300]}))
            continue
        if not isinstance(payload, dict):
            continue
        event_name = str(payload.get("event") or "").strip()
        if event_name == "progress":
            done = payload.get("done")
            target = payload.get("target")
            kind = payload.get("kind") or ""
            message = f"progress {done}/{target}"
            if kind:
                message = f"{kind} {message}"
            events.append(
                AgentEvent(
                    "status",
                    {"state": "running", "message": message, **payload},
                )
            )
        elif event_name == "error":
            events.append(
                AgentEvent(
                    "error",
                    {
                        "message": str(payload.get("message") or "upstream error"),
                    },
                )
            )
        elif event_name == "done":
            events.append(
                AgentEvent("status", {"state": "running", "message": "upstream done"})
            )
        else:
            events.append(
                AgentEvent("status", {"state": "running", "message": text[:300]})
            )
    return events


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("NO_COLOR", "1")
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _decode_output(value: bytes | None) -> str:
    if not value:
        return ""
    return value.decode("utf-8", errors="replace")


def _compact_text(value: str, limit: int = 400) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _redacted_command(command: list[str]) -> list[str]:
    return list(command)


def _format_worker_log(stage: str, command: list[str], result: _ProcessResult) -> str:
    return (
        f"# {stage}\n"
        f"command: {' '.join(command)}\n"
        f"exit: {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
