"""Launch Topic 3 cultural corpus generation jobs from Project 5."""

from __future__ import annotations

import json
import os
import random
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.topic3.cultural_corpus import read_cultural_corpus_run_samples
from app.core.config import get_settings

_SAFE_RUN_ID = re.compile(r"[^a-zA-Z0-9._-]")
_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = Lock()
_HTTP_TIMEOUT = httpx.Timeout(30.0)


def _generator_base_url() -> str:
    return get_settings().cultural_corpus_generator_base_url.strip().rstrip("/")


def _has_generator_service() -> bool:
    return bool(_generator_base_url())


def _local_adapter_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("runner", "local_subprocess_adapter")
    payload.setdefault("integration_mode", "local_demo_adapter")
    return payload


def _service_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("runner", "topic3_http_job_api")
    payload.setdefault("integration_mode", "upstream_service")
    if isinstance(payload.get("samples"), list):
        job_id = str(payload.get("job_id") or "")
        payload["samples"] = [_normalize_service_sample(sample, job_id=job_id) for sample in payload["samples"]]
    return payload


def _normalize_service_sample(sample: Any, *, job_id: str = "") -> Any:
    if not isinstance(sample, dict):
        return sample
    normalized = dict(sample)
    sample_id = normalized.get("sample_id") or normalized.get("id") or normalized.get("original_sample_id")
    ethnic = (
        normalized.get("ethnic")
        or normalized.get("implied_ethnic_group")
        or normalized.get("ethnic_group")
        or normalized.get("expected_ethnic_group")
    )
    question = (
        normalized.get("fullQuestion")
        or normalized.get("full_question")
        or normalized.get("user_query")
        or normalized.get("question")
        or ""
    )
    expected = (
        normalized.get("expected")
        or normalized.get("expected_answer")
        or normalized.get("reference_answer")
        or normalized.get("answer")
        or ""
    )
    normalized["id"] = str(sample_id or "")
    normalized.setdefault("fullQuestion", str(question))
    normalized.setdefault("ethnic", str(ethnic or ""))
    normalized.setdefault("inferred", str(ethnic or ""))
    normalized["expected"] = str(expected)
    normalized.setdefault("generated", str(normalized.get("generated_answer") or expected))
    normalized.setdefault("difficultyLevel", str(normalized.get("difficulty_level") or ""))
    normalized.setdefault("runId", str(normalized.get("run_id") or job_id))
    normalized.setdefault("category", str(normalized.get("domain") or normalized.get("query_type") or ""))
    normalized.setdefault("knowledge", _format_knowledge_points(normalized.get("cultural_knowledge_points")))
    return normalized


def _format_knowledge_points(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _request_service(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    base_url = _generator_base_url()
    if not base_url:
        raise RuntimeError("未配置 CULTURAL_CORPUS_GENERATOR_BASE_URL")
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=False) as client:
            response = client.request(method, f"{base_url}{path}", **kwargs)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as exc:
        raise RuntimeError(f"课题三文化语料生成服务不可达：{base_url}") from exc
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        raise RuntimeError("课题三文化语料生成服务返回格式不是对象")
    return _service_payload(data)


def _service_is_local() -> bool:
    parsed = urlparse(_generator_base_url())
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _stop_local_service_worker(job_id: str) -> dict[str, Any]:
    if not _service_is_local():
        raise RuntimeError("课题三文化语料生成停止接口失败，且上游不是本机服务，无法兜底停止")
    status = _request_service("GET", f"/api/generation/jobs/{job_id}")
    pid = status.get("pid")
    if not isinstance(pid, int):
        raise RuntimeError("课题三文化语料生成停止接口失败，且任务状态未返回可停止的 pid")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        raise RuntimeError(f"课题三文化语料生成停止接口失败，且本地 worker 停止失败：{pid}") from exc
    time.sleep(0.5)
    status["running"] = False
    status["pid"] = None
    status["status"] = "stopped"
    status.setdefault("source", "corpus_live")
    status["stop_fallback"] = "local_worker_pid"
    return _service_payload(status)


def _service_job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload.get("config")
    if isinstance(config, dict):
        return {"config": config}
    run_id = _safe_run_id(str(payload.get("run_id") or f"topic5_culture_{int(time.time())}"))
    config = _build_config(payload, run_id, _framework_root() / "runs" / run_id)
    output_dir = str(payload.get("output_dir") or f"runs/{run_id}").strip()
    config["output_dir"] = output_dir or f"runs/{run_id}"
    config["run_id"] = run_id

    generation = config.setdefault("generation", {})
    generation["language"] = str(payload.get("language") or generation.get("language") or "zh")
    generation["sample_mode"] = str(
        payload.get("sample_mode") or generation.get("sample_mode") or "cultural_mixed"
    )

    skill_path = str(payload.get("skill_path") or "").strip()
    if skill_path:
        config.setdefault("skill", {})["path"] = skill_path

    library_path = str(payload.get("cultural_knowledge_library_path") or "").strip()
    if library_path:
        config.setdefault("cultural_knowledge_library", {})["path"] = library_path
    seed_sources = payload.get("seed_sources")
    if isinstance(seed_sources, list):
        config.setdefault("cultural_knowledge_library", {})["sources"] = [
            str(item).strip() for item in seed_sources if str(item).strip()
        ]

    api_base = str(payload.get("api_base") or "").strip()
    model = str(payload.get("model") or "").strip()
    temperature = payload.get("temperature")
    max_tokens = payload.get("max_tokens")
    timeout = payload.get("timeout")
    composer_concurrency = payload.get("composer_concurrency")
    discard_retry_limit = payload.get("discard_retry_limit")
    for section in ("background_generator", "answer_generator", "cultural_reviewer", "llm_composer"):
        section_config = config.setdefault(section, {})
        if not isinstance(section_config, dict):
            continue
        if api_base:
            section_config["api_base"] = api_base
        if model:
            section_config["model"] = model
        if temperature is not None and section != "cultural_reviewer":
            section_config["temperature"] = float(temperature)
        if max_tokens is not None and section != "answer_generator":
            section_config["max_tokens"] = int(max_tokens)
        if timeout is not None:
            section_config["timeout"] = int(timeout)
    llm_composer = config.setdefault("llm_composer", {})
    if isinstance(llm_composer, dict):
        if composer_concurrency is not None:
            llm_composer["concurrency"] = max(1, int(composer_concurrency))
        if discard_retry_limit is not None:
            llm_composer["discard_retry_limit"] = max(1, int(discard_retry_limit))
    return {"config": config}


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _framework_root() -> Path:
    configured = get_settings().cultural_corpus_generator_root.strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (
        _workspace_root()
        / "Project_3_Cultural_Diversity_Corpus_Generation_Tool"
        / "framework_v3"
    )


def get_framework_root() -> Path:
    """Public alias for Benchmark adapter health/path checks."""
    return _framework_root()


def _default_config_path(framework_root: Path) -> Path:
    configured = get_settings().cultural_corpus_generation_config.strip()
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else framework_root / path
    return framework_root / "configs" / "cultural_generation.json"


def _python_executable() -> str:
    configured = get_settings().cultural_corpus_generation_python.strip()
    return configured or sys.executable


def _runner_path(framework_root: Path) -> Path:
    return framework_root / "agent_framework" / "scripts" / "run_resumable_generation.py"


def get_runner_path(framework_root: Path | None = None) -> Path:
    """Public alias for Benchmark adapter health/path checks."""
    return _runner_path(framework_root or _framework_root())


def _api_key_env_name() -> str:
    return get_settings().cultural_corpus_generation_api_key_env.strip() or "DEEPSEEK_API_KEY"


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE dotenv parser (no python-dotenv dependency)."""
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def resolve_generation_api_key(framework_root: Path | None = None) -> str | None:
    """Resolve DeepSeek/API key from process env, then framework/.env, then repo-root .env."""
    api_key_env = _api_key_env_name()
    existing = os.environ.get(api_key_env)
    if isinstance(existing, str) and existing.strip():
        return existing.strip()

    root = framework_root or _framework_root()
    for candidate in (root / ".env", root.parent / ".env"):
        value = _parse_dotenv(candidate).get(api_key_env)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_run_id(value: str) -> str:
    cleaned = _SAFE_RUN_ID.sub("_", value.strip())
    return cleaned[:80] or f"topic5_culture_{int(time.time())}"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _read_jsonl_count(path: Path) -> tuple[int, dict[str, int]]:
    if not path.is_file():
        return 0, {}
    count = 0
    level_counts: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            level = str(row.get("difficulty_level") or "unknown")
            level_counts[level] = level_counts.get(level, 0) + 1
    return count, level_counts


def _tail_text(path: Path, lines: int = 60) -> str:
    if not path.is_file():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _process_running(process: subprocess.Popen[str] | None) -> bool:
    return process is not None and process.poll() is None


def _infer_total(config: dict[str, Any], manifest: dict[str, Any]) -> int:
    if manifest.get("total_requested"):
        return int(manifest["total_requested"])
    generation = config.get("generation") if isinstance(config.get("generation"), dict) else {}
    counts = generation.get("difficulty_counts")
    if isinstance(counts, dict):
        total = sum(max(0, int(counts.get(level, 0))) for level in ("L1", "L2", "L3"))
        if total:
            return total
    return int(generation.get("total_sample_count", generation.get("sample_count", 0)))


def _status_from_files(
    generated: int,
    total: int,
    worker_state: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    if total and generated >= total:
        return "completed"
    if worker_state.get("status"):
        return str(worker_state["status"])
    if manifest.get("status"):
        return str(manifest["status"])
    return "created" if total else "unknown"


def _job_paths(job_id: str) -> tuple[Path, Path, Path]:
    framework_root = _framework_root()
    output_dir = framework_root / "runs" / job_id
    return framework_root, output_dir, output_dir / "generation_config.json"


def _build_config(payload: dict[str, Any], run_id: str, output_dir: Path) -> dict[str, Any]:
    framework_root = _framework_root()
    template_path = _default_config_path(framework_root)
    if not template_path.is_file():
        raise FileNotFoundError(f"文化语料生成模板配置不存在：{template_path}")

    config = _load_json(template_path)
    generation = config.setdefault("generation", {})
    config["run_id"] = run_id
    config["output_dir"] = str(output_dir.relative_to(framework_root))
    generation["resume"] = True
    generation["random_seed"] = int(payload.get("random_seed") or random.randint(1, 999_999_999))
    generation["match_offset_base"] = random.Random(generation["random_seed"]).randint(0, 10_000_000)

    total_sample_count = int(payload.get("total_sample_count") or 1)
    if total_sample_count < 1 or total_sample_count > 50:
        raise ValueError("total_sample_count 必须在 1 到 50 之间")
    generation["total_sample_count"] = total_sample_count
    generation["batch_size"] = max(1, int(payload.get("batch_size") or min(total_sample_count, 5)))
    generation["language"] = str(payload.get("language") or generation.get("language") or "zh")

    difficulty_counts = payload.get("difficulty_counts")
    if isinstance(difficulty_counts, dict) and difficulty_counts:
        generation["difficulty_counts"] = {
            level: max(0, int(difficulty_counts.get(level, 0)))
            for level in ("L1", "L2", "L3")
        }
    else:
        generation["difficulty_counts"] = {}

    allowed_ethnic_groups = payload.get("allowed_ethnic_groups")
    if isinstance(allowed_ethnic_groups, list):
        generation["allowed_ethnic_groups"] = [
            str(item).strip() for item in allowed_ethnic_groups if str(item).strip()
        ]

    allowed_dimensions = payload.get("allowed_dimensions")
    if isinstance(allowed_dimensions, list):
        generation["allowed_dimensions"] = [
            str(item).strip() for item in allowed_dimensions if str(item).strip()
        ]

    api_key_env = _api_key_env_name()
    for section in ("background_generator", "answer_generator", "cultural_reviewer", "llm_composer"):
        value = config.setdefault(section, {})
        if isinstance(value, dict):
            value["api_key_env"] = api_key_env

    return config


def start_generation_job(
    payload: dict[str, Any], *, force_local: bool = False
) -> dict[str, Any]:
    if not force_local and _has_generator_service():
        return _request_service("POST", "/api/generation/jobs", json=_service_job_payload(payload))

    framework_root = _framework_root()
    api_key_env = _api_key_env_name()
    api_key = resolve_generation_api_key(framework_root)
    if not api_key:
        raise RuntimeError(
            f"未在 Project_3 配置 {api_key_env}（请写入 framework/.env 或仓库根 .env，"
            f"或设置进程环境变量 {api_key_env}）"
        )

    runner_path = _runner_path(framework_root)
    if not runner_path.is_file():
        raise FileNotFoundError(f"文化语料生成脚本不存在：{runner_path}")

    raw_run_id = str(payload.get("run_id") or f"topic5_culture_{int(time.time())}")
    run_id = _safe_run_id(raw_run_id)
    output_dir = framework_root / "runs" / run_id
    if output_dir.exists():
        raise FileExistsError(f"生成目录已存在，请换一个 run_id：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    config = _build_config(payload, run_id, output_dir)
    config_path = output_dir / "generation_config.json"
    _write_json(config_path, config)

    child_env = os.environ.copy()
    child_env[api_key_env] = api_key

    log_path = output_dir / "worker.log"
    log_handle = log_path.open("a", encoding="utf-8")
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(
        [_python_executable(), str(runner_path), "--config", str(config_path)],
        cwd=framework_root,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=child_env,
        **kwargs,
    )

    with _JOBS_LOCK:
        _JOBS[run_id] = {
            "process": process,
            "config_path": config_path,
            "output_dir": output_dir,
            "started_at": time.time(),
        }
    return _local_adapter_payload(get_generation_job_status(run_id, force_local=True))


def get_generation_job_status(
    job_id: str, *, force_local: bool = False
) -> dict[str, Any]:
    if not force_local and _has_generator_service():
        safe_id = _safe_run_id(job_id)
        data = _request_service("GET", f"/api/generation/jobs/{safe_id}")
        data.setdefault("source", "corpus_live")
        return data

    safe_id = _safe_run_id(job_id)
    framework_root, output_dir, config_path = _job_paths(safe_id)
    if not output_dir.exists():
        raise KeyError(f"unknown generation job: {safe_id}")

    with _JOBS_LOCK:
        job = _JOBS.get(safe_id)
    process = job.get("process") if job else None
    manifest = _read_json(output_dir / "manifest.json")
    worker_state = _read_json(output_dir / "worker_state.json")
    config = _read_json(config_path)
    generated, level_counts = _read_jsonl_count(output_dir / "samples.jsonl")
    total = _infer_total(config, manifest)
    running = _process_running(process)
    status = "running" if running else _status_from_files(generated, total, worker_state, manifest)
    progress = round((generated / total) * 100, 2) if total else 0
    return _local_adapter_payload({
        "job_id": safe_id,
        "status": status,
        "running": running,
        "pid": process.pid if running else None,
        "generated": generated,
        "total": total,
        "progress": progress,
        "difficulty_level_counts": level_counts,
        "output_dir": str(output_dir.relative_to(framework_root)),
        "config_path": str(config_path.relative_to(framework_root)),
        "samples_path": str((output_dir / "samples.jsonl").relative_to(framework_root)),
        "manifest": manifest,
        "worker_state": worker_state,
        "log_tail": _tail_text(output_dir / "worker.log"),
        "samples": read_cultural_corpus_run_samples(output_dir)[-8:],
        "source": "corpus_live",
    })


def get_generation_job_samples(
    job_id: str, limit: int | None = None, *, force_local: bool = False
) -> dict[str, Any]:
    if not force_local and _has_generator_service():
        safe_id = _safe_run_id(job_id)
        params = {"limit": limit} if limit is not None else None
        data = _request_service("GET", f"/api/generation/jobs/{safe_id}/samples", params=params)
        data.setdefault("source", "corpus_live")
        return data

    safe_id = _safe_run_id(job_id)
    _, output_dir, _ = _job_paths(safe_id)
    if not output_dir.exists():
        raise KeyError(f"unknown generation job: {safe_id}")
    samples = read_cultural_corpus_run_samples(output_dir)
    if limit is not None and limit >= 0:
        samples = samples[-limit:]
    return _local_adapter_payload({
        "job_id": safe_id,
        "source": "corpus_live",
        "count": len(samples),
        "samples": samples,
    })


def stop_generation_job(job_id: str, *, force_local: bool = False) -> dict[str, Any]:
    if not force_local and _has_generator_service():
        safe_id = _safe_run_id(job_id)
        try:
            data = _request_service("POST", f"/api/generation/jobs/{safe_id}/stop")
        except RuntimeError:
            return _stop_local_service_worker(safe_id)
        data.setdefault("source", "corpus_live")
        return data

    safe_id = _safe_run_id(job_id)
    with _JOBS_LOCK:
        job = _JOBS.get(safe_id)
    if not job:
        raise KeyError(f"unknown generation job: {safe_id}")

    process = job.get("process")
    if _process_running(process):
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    return get_generation_job_status(safe_id, force_local=True)
