# Backend README

## Overview

This directory contains the FastAPI backend service for the project.

- App entry: `app.main:app`
- Runtime server: `uvicorn`
- Default local database: `content_governance.db`
- Default local URL: `http://127.0.0.1:5800`
- API health check: `GET /health`
- Swagger UI: `http://127.0.0.1:5800/docs`

## Directory Notes

Topic 1 corpus-tool API adaptation and current acceptance boundaries:
[2026-10-20 integration notes](../../docs/integration/2026-10-20-topic1-corpus-tool-api.md).
The input page can explicitly probe configured services; an online service is
not proof of usable model weights. Public task execution and governance Skill
execution are not enabled by this adapter-only integration stage.

- `app/`: FastAPI application code
- `tests/`: pytest test cases
- `requirements.txt`: Python dependencies
- `content_governance.db`: local SQLite database file

## Governance Session Persistence

The `/api/governance` endpoints register an anonymous browser client, create a session only with its first non-empty request, append ordered user/assistant messages, list and restore sessions, and soft-delete them. The browser client ID is a grouping key, not authentication. Serve this API only behind an internal network, Cloudflare Access, or an explicit allowlist.

Each turn is interpreted by a configurable governance assistant that returns a structured intent, which the orchestrator validates against a per-domain capability registry before executing anything. The `input` domain currently exposes five capabilities: `value_corpus_overview`, `value_qa_search`, `value_qa_group_detail`, `risk_corpus_overview` and `risk_corpus_search`. The `output` domain exposes `risk_system_record_search` and `risk_system_record_detail`, which read risk-safety system prerun records straight from the Benchmark asset registry (`benchmark_type=risk_content_generation`, `source_mode=prerun_snapshot`) and return a reference plus an immutable presentation snapshot — system records are never copied into a user completion record and never appear in the left-hand session history. A record's `completed_at` is the latest imported `evaluated_at`, falling back to the asset registration time; opening a record whose version changed since the session's own list snapshot reports `source_status=changed`, and a missing record reports `source_status=missing` instead of a fabricated result. The assistant prompt injects each capability's parameter contract, including the allowed values for the static risk corpus filters (reference label, source, L1/L2 category); capability parameter models reject unknown fields, so a model that guesses a wrong field name fails with a `boundary` message instead of silently returning unfiltered results. Result payloads are persisted on the assistant message and rendered as structured cards, never as Markdown tables authored by the model. `risk_corpus_search` is paged: `limit` defaults to 20 with a maximum of 50, `offset` selects the page, and a `continuation` request reuses the filters of the latest risk search in the same session and advances the offset. `risk_system_record_search` is paged the same way against the latest system-record list in the session. Valid intents for the active domain execute against registered assets, while ambiguous, cross-domain, fabricated, or invalid-parameter requests produce `clarify` / `boundary` assistant messages. Exactly one model provider is active at a time, chosen via `GOVERNANCE_ASSISTANT_PROVIDER` (`qwen` | `deepseek` | `stub`); `stub` is the deterministic dev/test seam that makes no network call. Execution provenance (provider, model, latency, parse status, parameters) is recorded in `governance_tasks`, and each executed capability stores a snapshot in `governance_completion_records` — never API keys or credentials.

The risk corpus is the in-repo static pack `web/backend/data/input_corpora/input_dynbench400_eval_schema.jsonl` (asset id `topic2_dynbench400_static`). Its reference labels are read-only source facts (`original_label`, `safe` / `unsafe`) and are never rewritten as the current session's detection conclusion.

For local DeepSeek development, copy `web/backend/.env.example` to
`web/backend/.env`, set `GOVERNANCE_ASSISTANT_PROVIDER=deepseek`, and provide
`DEEPSEEK_API_KEY`. The local `.env` file is ignored by Git; only the placeholder
`.env.example` may be committed. Process environment variables override values in
the file, so deployments should inject the key through their secret manager rather
than ship a populated `.env`.

New governance tables are created by the ordered revisions in `app/db/migrations/versions/`, with applied versions recorded in `schema_migrations`. Startup applies pending revisions after the legacy table bootstrap; it does not use runtime column patches for governance tables. Existing anonymous records have no automatic expiry, and deletion marks a session without physically removing its messages.

Each user turn carries a client-scoped `request_id` (`POST /api/governance/sessions` and `POST /api/governance/sessions/{session_id}/turns`). Retrying the same request from the same client returns the original session or message instead of creating a duplicate, backed by the `(client_id, request_id)` unique constraint on `governance_messages`. When the field is omitted, the backend generates a fresh identifier so existing callers keep working.

When Skill Runtime needs another answer, the session response exposes a durable `clarification_plan` with a stable `plan_id`, state, question, and concurrency `version`. A continuation must echo `clarification_plan_id` and `clarification_plan_version`; omitting them starts a new goal and abandons the previous active plan. Terminal or stale plans fail with HTTP 409 and `data.error_code=planning_context_stale`. Plans do not expire on a timer, so `GET /api/governance/sessions/{session_id}` is the recovery source after refresh or an uncertain request result.

Confirmed governance skills run outside the API process. `POST /api/governance/tasks/{task_id}/confirm` returns `202` with the queued task ID. The recommended `node scripts/start-platform.mjs` launcher starts one independent worker by default after the backend is healthy; use `--no-governance-worker` only when intentionally debugging an API-only setup. For manual service debugging, run at least one worker from this directory with `python -m app.workers.governance_task_worker`. Workers claim tasks through expiring database leases, renew active leases, and recover abandoned work without relying on API-process memory. `GET /api/governance/tasks/{task_id}` returns the current snapshot and event cursor. `GET /api/governance/tasks/{task_id}/events` streams only already-persisted SSE events; reconnect with `Last-Event-ID` or `?after=<sequence>`. Task events contain only stages, counts, and controlled resource references—never sample text or upstream logs.

## Benchmark Management Import

`POST /api/admin/benchmark/deliveries` accepts a topic3 risk Benchmark delivery package (built by `scripts/package_topic3_risk_delivery.py`) as a multipart `file` plus its `delivery_id`, stages it under `BENCHMARK_DELIVERY_STAGING_ROOT` (default `benchmark-delivery-staging`), checks ZIP safety, extracts it and validates it; `GET /api/admin/benchmark/deliveries/{delivery_id}` returns the delivery status and validation report. Both require the header `X-Benchmark-Admin-Token` matching `BENCHMARK_ADMIN_TOKEN`, an independent credential that must be injected like any other secret; while it is unset the endpoints return 503. Delivery records store `BENCHMARK_ADMIN_LABEL` (default `benchmark-admin`) as `uploaded_by`. Upload and validation never change the current Benchmark version. Uploads must send `Content-Length` (chunked uploads get 411). A retry of an import still in progress returns 202; one untouched for `BENCHMARK_DELIVERY_STALE_SECONDS` (default 900) is taken over and re-validated. Size limits are configured with `BENCHMARK_DELIVERY_MAX_PACKAGE_BYTES`, `BENCHMARK_DELIVERY_MAX_ENTRIES`, `BENCHMARK_DELIVERY_MAX_ENTRY_BYTES`, `BENCHMARK_DELIVERY_MAX_TOTAL_BYTES` and `BENCHMARK_DELIVERY_MAX_COMPRESSION_RATIO`. See `docs/architecture/topic3/2026-10-15-课题三风险Benchmark管理导入接口说明.md`.

## Topic3 Benchmark Dependency

The output-eval endpoints in this backend depend on the topic3 Benchmark service.

- Benchmark repo: `Project_3_Risk_Hierarchical_Classification_Benchmark`
- Default upstream URL used by this backend: `http://127.0.0.1:6006`
- Affected endpoints include dataset loading, taxonomy loading, eval task creation, status polling, result loading, and export

If the Benchmark service is not running, the output-governance flow will be incomplete or return errors even if this backend itself starts successfully.

Before starting this backend for output-eval development, start the Benchmark service first.

### Output-Eval Source Policy

The output-governance endpoints use an explicit source policy.

- Live Benchmark data is returned with `source=benchmark`.
- Single-sample inference failures are returned as `source=unavailable` with `ok=false`.
- Eval task creation, result loading, and export do not silently generate mock results when Benchmark is unavailable.
- Cultural Gen sample loading reads the data API configured by `CULTURAL_GEN_DATA_BASE_URL` (`6323 /samples` by default); analysis still uses `CULTURAL_GEN_BASE_URL` (`6322 /api/analyze`). If both the data API and legacy backend fallback are unavailable, Project 5 returns `502` instead of falling back to local mock samples.
- `GET /api/output/culture/corpus-samples` reads committed Topic 3 cultural corpus `samples.jsonl` runs as an explicit `corpus_static` source with `integration_mode=local_artifact_adapter`. It never triggers online generation and excludes Project 5 live runs whose directory names start with `topic5_` by default. Set `CULTURAL_CORPUS_RUNS_DIR` when the sibling repository is not located under the workspace root.
- Static cultural corpus samples are deduplicated by `run_id + sample_id`, not by `sample_id` alone, because different Topic 3 runs can reuse the same sample IDs.
- `POST /api/output/culture/corpus-generation/jobs` starts a live Topic 3 cultural corpus generation job and returns `source=corpus_live`. If `CULTURAL_CORPUS_GENERATOR_BASE_URL` is configured, Project 5 calls the Topic 3 HTTP job API and returns `integration_mode=upstream_service`. If it is not configured, Project 5 falls back to a local demo adapter that wraps `Project_3_Cultural_Diversity_Corpus_Generation_Tool/framework_v3/agent_framework/scripts/run_resumable_generation.py`, returns `integration_mode=local_demo_adapter`, and reads the DeepSeek key only from the backend environment variable configured by `CULTURAL_CORPUS_GENERATION_API_KEY_ENV` (`DEEPSEEK_API_KEY` by default).
- `GET /api/output/culture-assessment/datasets` and `GET /api/output/culture-assessment/static-views/{view_id}` read static assets from `Project_3_Cultural_Diversity_Assessment_Tool` as `source=culture_assessment_static`. These endpoints expose dataset catalogs and Direct vs 3-Agent benchmark results without starting DeepSeek jobs.
- Static snapshot endpoints may still return an explicit snapshot source such as `backend_snapshot` when a configured snapshot directory is available.
- `GET /api/output/static-results` and `GET /api/output/static-predictions` accept the same `task`, `dataset_id`, and `model_id` selector and mark pre-run Benchmark result browsing as `source=benchmark_static`.

This keeps demo fixtures, static assets, and live experimental results separate for reproducible output-governance experiments.

Typical startup flow based on the current integration docs:

```bash
cd /path/to/Project_3_Risk_Hierarchical_Classification_Benchmark
./run.sh
```

The current integration docs record that `./run.sh` starts the Benchmark service on port `6006`.

If your local Benchmark address is different, set `BENCHMARK_BASE_URL` before starting this backend.

### Cultural Corpus Live Generation

The backend can start a small live cultural corpus generation job after `DEEPSEEK_API_KEY` is available in the backend process environment. Do not store the key in source files, README files, or request bodies.

Optional environment variables:

| Variable                                 | Default                                                                 | Purpose                                                                                                     |
| ---------------------------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `CULTURAL_GEN_DATA_BASE_URL`             | `http://127.0.0.1:6323`                                                 | Cultural Gen json-server data API for `GET /samples`                                                        |
| `CULTURAL_CORPUS_GENERATOR_BASE_URL`     | `http://127.0.0.1:8766`                                                  | Optional Topic 3 corpus generator HTTP/job API; when set, Project 5 calls `/api/generation/jobs` and does not launch the local runner script |
| `CULTURAL_CORPUS_GENERATOR_ROOT`         | sibling `Project_3_Cultural_Diversity_Corpus_Generation_Tool/framework_v3` | Local demo adapter framework root, used only when `CULTURAL_CORPUS_GENERATOR_BASE_URL` is empty             |
| `CULTURAL_CORPUS_GENERATION_CONFIG`      | `configs/cultural_generation.json`                                      | generation template config, relative to generator root if not absolute                                      |
| `CULTURAL_CORPUS_GENERATION_PYTHON`      | current backend Python                                                  | Python executable used to launch the Topic 3 runner                                                         |
| `CULTURAL_CORPUS_GENERATION_API_KEY_ENV` | `DEEPSEEK_API_KEY`                                                      | environment variable name read by the Topic 3 runner                                                        |
| `CULTURAL_ASSESSMENT_ROOT`               | sibling `Project_3_Cultural_Diversity_Assessment_Tool`                  | Topic 3 cultural diversity assessment repository root                                                       |
| `CULTURAL_ASSESSMENT_CONSOLE_BASE_URL`   | `http://127.0.0.1:8877`                                                 | Topic 3 cultural assessment console runtime API for live Direct / 3-Agent jobs                              |

Endpoints:

- `GET /api/output/culture/corpus-samples?run_id=...&ethnic=...&difficulty=L1&limit=50`
- `POST /api/output/culture/corpus-generation/jobs`
- `GET /api/output/culture/corpus-generation/jobs/{job_id}`
- `GET /api/output/culture/corpus-generation/jobs/{job_id}/samples?limit=50`
- `POST /api/output/culture/corpus-generation/jobs/{job_id}/stop`

When Project 5 talks to a local Topic 3 generator service on `127.0.0.1` or `localhost`, the stop endpoint includes a Windows-compatible fallback that terminates the worker `pid` returned by the Topic 3 job status. This keeps the Project 5 UI stop button usable even if the upstream demo server uses POSIX-only process-group termination.
- `GET /api/output/culture-assessment/console/datasets`
- `POST /api/output/culture-assessment/console/jobs`
- `GET /api/output/culture-assessment/console/jobs/{job_id}`
- `GET /api/output/culture-assessment/console/jobs/{job_id}/results`
- `POST /api/output/culture-assessment/console/jobs/{job_id}/stop`

Static corpus query notes:

- `run_id`, `ethnic`, and `difficulty` can be repeated query parameters.
- `include_live_runs=true` includes Project 5 live generation folders such as `topic5_*`; leave it unset for reproducible pre-run corpus browsing.
- The response includes `ethnic_counts`, `difficulty_counts`, and `run_counts` for quick coverage checks.
- The frontend culture corpus workbench uses `include_live_runs=true` to build run history, then reuses a selected `run_id` as a diversity-track dataset source.

Minimal request body:

```json
{
  "total_sample_count": 1,
  "batch_size": 1,
  "allowed_ethnic_groups": ["蒙古族"],
  "difficulty_counts": {
    "L1": 1,
    "L2": 0,
    "L3": 0
  }
}
```

The generated samples are stored under the Topic 3 generator `runs/{job_id}/` directory and normalized to the same fields used by `corpus_static`. This path is for corpus generation only; it is not the final cultural diversity assessment service contract.

## Recommended Local Startup

Windows developers should enter WSL Ubuntu first. macOS, Linux, and WSL should all use the same POSIX startup path from the repository root:

```bash
cd /mnt/c/Users/64649/Desktop/project5/new/Project_5_LLM_Content_Safety_Governance_Web
node scripts/start-platform.mjs
```

The unified launcher reads `docs/integration/ports.registry.yaml`, starts or checks optional upstream services, injects the related backend environment variables, and then starts the Project 5 backend, frontend, and governance worker. The worker starts only after the backend health check confirms that startup migrations completed. This is the preferred path for local integration, demo rehearsal, and future Linux server deployment.

Common skip flags:

```bash
node scripts/start-platform.mjs --no-topic2-filterguard
node scripts/start-platform.mjs --no-topic4-input-workflow
node scripts/start-platform.mjs --no-topic2-filterguard --no-topic4-input-workflow
node scripts/start-platform.mjs --no-governance-worker
```

Use manual backend startup only when debugging a single service:

```bash
cd /mnt/c/Users/64649/Desktop/project5/new/Project_5_LLM_Content_Safety_Governance_Web/web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 5800
```

## Virtual Environment Rules

In this project, `web/backend/.venv` is reserved for Linux/WSL use. Native Windows PowerShell with `.venv-win` is kept only for legacy troubleshooting and should not be the main development path.

- Use `.venv` inside WSL, macOS, or Linux.
- Do not create `.venv-win` from WSL.
- Do not recreate `.venv` from native Windows PowerShell.
- If `.venv` contains `Scripts` instead of `bin`, it was created by Windows Python and should be rebuilt in WSL.

Quick way to tell environments apart:

- WSL/Linux virtual environments contain `.venv/bin/activate`
- Windows virtual environments contain `.venv\Scripts\Activate.ps1`

## Run Tests

```bash
cd /path/to/Project_5_LLM_Content_Safety_Governance_Web
cd web/backend
source .venv/bin/activate
PYTHONPATH=. python -m pytest -q
```

Run a single test:

```bash
cd /path/to/Project_5_LLM_Content_Safety_Governance_Web
cd web/backend
source .venv/bin/activate
PYTHONPATH=. python -m pytest tests/test_health.py -q
```

## Local Data Behavior

- On startup, the app creates database tables automatically
- Local data is stored in `content_governance.db`
- If you want a clean local database, stop the service and remove that file before restarting
- Definition module uploads support text, HTML, JSON, CSV, DOCX, PPTX, XLSX, and PDF files. PDF parsing requires the `pypdf` dependency from `requirements.txt`.

## Topic 1 Algorithm Adapter

The definition module integrates Topic 1 indicator mining through the Project 5 task API. By default it calls the current Project 1 system through `project1_agents_api` and its existing `/api/agents/start-mining` endpoint. If the Topic 1 system is not running, the frontend should show a clear connection failure instead of silently falling back to local preset data. For local development or demos that intentionally skip Project 1, set `TOPIC1_ALGORITHM_MODE=local_adapter`. If a future algorithm-only service is provided, use `remote_algorithm_api` and keep the frontend/task API unchanged.

Topic 1 is currently wired only to the Definition module's `input-value` workflow. It covers input-side data, training corpus, policy text, standard text, and case material mining for value, ethics, cultural fit, and task-scenario support. Output-side risk and cultural-diversity tabs must not silently reuse this adapter because their evaluation object and evidence source are different.

| Variable                           | Default                                         | Options                                                        | Description                                                                                                                                                                                                                 |
| ---------------------------------- | ----------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TOPIC1_ALGORITHM_MODE`            | `project1_agents_api`                           | `project1_agents_api`, `local_adapter`, `remote_algorithm_api` | Selects whether Topic 1 mining calls the current Project 1 Agents API, runs locally for development, or calls a future normalized algorithm service.                                                                        |
| `TOPIC1_PROJECT1_BASE_URL`         | `http://127.0.0.1:6102`                         | HTTP base URL                                                  | Used only when `TOPIC1_ALGORITHM_MODE=project1_agents_api` and `TOPIC1_ALGORITHM_URL` is not set. The adapter calls `/api/agents/start-mining` under this base URL.                                                         |
| `TOPIC1_ALGORITHM_URL`             | empty                                           | HTTP endpoint                                                  | Optional override for `project1_agents_api`; required for `remote_algorithm_api`. In `remote_algorithm_api` mode, the endpoint must return normalized logs, stats, candidate indicators, prepared texts, and matched paths. |
| `TOPIC1_ALGORITHM_TIMEOUT_SECONDS` | `30` for normalized remote, `300` for Project 1 | positive number                                                | Timeout for the remote adapter request. Project 1 runs multiple LLM stages in one synchronous request, so the platform timeout must cover the whole pipeline rather than one model call.                                    |

POSIX example for the current Project 1 system:

```bash
export TOPIC1_PROJECT1_BASE_URL=http://127.0.0.1:6102
export TOPIC1_ALGORITHM_TIMEOUT_SECONDS=300
uvicorn app.main:app --reload --host 127.0.0.1 --port 5800
```

If Project 1 uses DeepSeek through a local proxy, set proxy variables before starting the Project 1 backend process. Otherwise `/api/agents/llm-health` may return `reachable=false` with `Connection error` even when `/health` is healthy:

```bash
export HTTP_PROXY=http://127.0.0.1:7892
export HTTPS_PROXY=http://127.0.0.1:7892
export ALL_PROXY=http://127.0.0.1:7892
python main.py
```

POSIX example for local development without starting Project 1:

```bash
export TOPIC1_ALGORITHM_MODE=local_adapter
uvicorn app.main:app --reload --host 127.0.0.1 --port 5800
```

POSIX example for a future normalized algorithm service:

```bash
export TOPIC1_ALGORITHM_MODE=remote_algorithm_api
export TOPIC1_ALGORITHM_URL=http://127.0.0.1:9000/topic1/mining
export TOPIC1_ALGORITHM_TIMEOUT_SECONDS=60
uvicorn app.main:app --reload --host 127.0.0.1 --port 5800
```

### Topic 1 Training-Corpus Tool Catalog

The input-governance module exposes the Topic 1 scarcity evaluation, data denoising,
data detoxification, and data selection deliveries through one versioned catalog:

- BFF endpoint: `GET /api/data-input/topic1/corpus-tools`
- Governance Agent capability: `topic1_corpus_tool_catalog`
- Canonical catalog: `data/topic1_tools/catalog.v1.json`

Both UI surfaces read the same catalog. A delivered source archive is not treated as
an online executable service: until Topic 1 provides a stable API or a platform-owned
Worker contract, the catalog remains read-only and reports the real integration gap.
Malformed or missing catalog data returns a stable unavailable response without
exposing local paths or Python exception details.

Validate the repository catalog from the repository root:

```bash
python scripts/verify-topic1-corpus-tools.py
```

Optionally verify the delivered source archives against the registered SHA-256 values:

```bash
python scripts/verify-topic1-corpus-tools.py --source-dir /path/to/topic1-packages
```

The normalized upstream task/status/result contract and the per-tool delivery checklist
are documented in `docs/integration/2026-10-10-课题一训练语料工具接入契约.md`.

## Topic 4 Input Workflow Adapter

The data-input module can call Topic 4 `Project_4_Input_workflow` for input-side file-to-record parsing, lineage graph generation, risk annotation merging, cleaning, and report summary. Project 5 keeps Topic 4 as an external service and only normalizes the response for the data-input workflow.

Current first-phase integration scope:

- Project 5 endpoint: `GET /api/data-input/topic4/lineage/health`
- Project 5 endpoint: `POST /api/data-input/topic4/lineage/build`
- Upstream service: Topic 4 `GET /api/health`
- Upstream service: Topic 4 `POST /api/workflow/full_v2`
- Upstream service: Topic 4 `POST /api/build_graph` and `POST /api/graph/merge` for explicit annotation/debug paths
- Current UI usage: data-input Step 2 lineage graph generation

Topic 4 confirmed that the service entry is `app.py`, `dataflow` comes from `pip install open-dataflow`, and the workflow APIs are synchronous. Project 5 now calls `/api/workflow/full_v2` by default so that Topic 4 owns annotation, graph building, risk merge, cleaning, and report generation. If Topic 4 is not running or a workflow stage fails, Project 5 returns a clear connection or workflow failure message and does not silently replace the result with fake Topic 4 output.

Recommended local integration path is the unified platform launcher:

```bash
node scripts/start-platform.mjs
```

The launcher reads `docs/integration/ports.registry.yaml`, injects `TOPIC4_INPUT_WORKFLOW_BASE_URL=http://127.0.0.1:8081` into the Project 5 backend, and tries to reuse or start the optional Topic 4 input workflow service. To skip Topic 4 during unrelated development:

```bash
node scripts/start-platform.mjs --no-topic4-input-workflow
```

| Variable                                | Default                 | Description                                                                                        |
| --------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------- |
| `TOPIC4_INPUT_WORKFLOW_BASE_URL`        | `http://127.0.0.1:8081` | Base URL of the Topic 4 input workflow Flask service.                                              |
| `TOPIC4_INPUT_WORKFLOW_TIMEOUT_SECONDS` | `30`                    | Timeout for Topic 4 health and workflow requests. Increase this for LLM-backed full workflow runs. |

POSIX troubleshooting example for starting Topic 4 locally:

```bash
cd /mnt/c/Users/64649/Desktop/project5/Project_4_Input_workflow
python3 -m venv .venv
source .venv/bin/activate
pip install flask flasgger flask-cors httpx openai open-dataflow
python app.py --host 127.0.0.1 --port 8081
```

If Topic 4 only needs the minimal lineage endpoints for integration and `open-dataflow` still blocks startup, Topic 4's current guidance is to temporarily comment out the dataflow cleaning calls because that package is mainly used by the cleaning pipeline.

Then start this backend with the same base URL:

```bash
cd /mnt/c/Users/64649/Desktop/project5/new/Project_5_LLM_Content_Safety_Governance_Web/web/backend
source .venv/bin/activate
export TOPIC4_INPUT_WORKFLOW_BASE_URL=http://127.0.0.1:8081
uvicorn app.main:app --reload --host 127.0.0.1 --port 5800
```

### Definition mining history

Definition mining history is an explicit snapshot workflow. A completed mining task is not
automatically archived; users save the reviewed indicator system from Step 3. Snapshots are
isolated by `definition_scope` (`input-value`, `input-risk`, `output-risk`, or
`output-culture`) so histories from different tabs cannot be mixed.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/mining-tasks/history?definition_scope=...` | List saved snapshots for one definition tab |
| `POST /api/mining-tasks/{task_id}/save-history` | Save the current reviewed candidates as an immutable snapshot |
| `GET /api/mining-tasks/{task_id}/history-results?definition_scope=...` | Read the saved snapshot without exposing later candidate edits |

The database startup patch adds the history columns for existing local databases. New mining
tasks should always send `definition_scope`; the backend keeps a compatibility default only for
older clients.

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`

Run commands from the `web/backend` directory and set `PYTHONPATH=.`

### `python` is not recognized in PowerShell

Install Python for Windows first, then reopen PowerShell and recreate `.venv-win`

### `.venv` has `Scripts` but no `bin`

That means `.venv` was recreated in Windows and is no longer the WSL environment.

From PowerShell, move the mistaken environment out of the way:

```powershell
cd <your-repo-root>\Project_5_LLM_Content_Safety_Governance_Web\web\backend
Rename-Item .venv .venv-win-backup-<date>
```

Then rebuild `.venv` inside WSL:

```bash
cd /mnt/<drive>/<path>/Project_5_LLM_Content_Safety_Governance_Web/web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### PowerShell cannot activate scripts

If script execution is blocked, run PowerShell as yourself and execute:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then reopen PowerShell and try activation again.

### Topic2 FilterGuard 输入风险识别

课题五输入模块风险轨道可通过 BFF 调用课题二 `Project_2_Anomaly_Data_Identification` 的 FilterGuard keyword 服务。本轮只接入轻量 keyword 方法；neuron、onion 等模型型方法暂不纳入默认链路。

推荐使用仓库根目录的统一 POSIX 启动入口：

```bash
node scripts/start-platform.mjs
```

统一入口会读取 `docs/integration/ports.registry.yaml` 中的 `topic2-filterguard` 注册信息，默认尝试启动或复用：

```bash
filterguard serve --methods keyword --host 0.0.0.0 --port 6211
```

并向课题五后端注入 `TOPIC2_FILTERGUARD_BASE_URL`、`TOPIC2_FILTERGUARD_METHOD`、`TOPIC2_FILTERGUARD_TIMEOUT_SECONDS`。如需临时跳过课题二 FilterGuard，可执行：

```bash
node scripts/start-platform.mjs --no-topic2-filterguard
```

PowerShell 手动设置环境变量和单独启动 `filterguard` 仅建议作为本地排障方式使用，避免和 WSL / Linux 部署路径产生两套启动口径。

Activation Probe 默认直连固定远端入口 `TOPIC2_ACTIVATION_PROBE_BASE_URL`。如果本机网络必须经由显式出口才能访问该固定入口，可只为 Activation Probe 配置局部代理；平台启动脚本仍会消毒全局代理变量，其他本地上游不会受影响：

```bash
TOPIC2_ACTIVATION_PROBE_PROXY_URL=http://127.0.0.1:7897 node scripts/start-platform.mjs
```

输入模块页面主流程使用任务化接口：

| 接口 | 说明 |
| --- | --- |
| `GET /api/data-input/topic2/filterguard/health` | 检查 FilterGuard 服务是否可达 |
| `POST /api/data-input/topic2/risk-scan-tasks` | 创建批量输入风险识别任务 |
| `GET /api/data-input/topic2/risk-scan-tasks/{task_id}` | 查询任务进度和结果 |
| `POST /api/data-input/topic2/risk-scan-tasks/{task_id}/cancel` | 请求取消识别任务 |

旧的 `POST /api/data-input/topic2/filterguard/predict` 只作为兼容接口保留；新增页面能力应优先接入任务接口，避免长时间同步请求阻塞前端。

该兼容端点已不再固定使用 `keyword`：请求体的 `method` 优先，缺省时回落到服务端登记默认值（`TOPIC2_RISK_DETECT_METHOD`），非法值回落到 `activation_probe`；`texts` 为空时返回 `400`（「未提供待检测文本」），不再伪造占位样本。在线检测统一走共用领域服务 `app/services/input_risk_detection_service.py`，与治理会话二次检测同源。
