# Server Deployment Notes

## Topic 3 Benchmark BFF remote mode

Project 5 business APIs use the BFF path:

```text
browser -> Project 5 /api/... -> Project 5 backend -> Topic 3 Benchmark
```

When the 176 server should call the online Topic 3 Benchmark service, set
`BENCHMARK_BASE_URL` and enable the Project 5 backend outbound proxy in
`scripts/server/deploy.env`:

```bash
BENCHMARK_BASE_URL=https://u288206-6f2x-63496cc3.weste.seetacloud.com:8443
OUTPUT_GUARDRAIL_DETECT_TIMEOUT_SECONDS=300
PROJECT5_BACKEND_PROXY_URL=http://<user>:<password>@proxy.example.invalid:1080
PROJECT5_BACKEND_NO_PROXY=127.0.0.1,localhost,platform.example.invalid,proxy.example.invalid
```

When using the local co-deployed Topic 3 Benchmark service, point the BFF back
to the local service and leave the proxy empty:

```bash
BENCHMARK_BASE_URL=http://127.0.0.1:6006
PROJECT5_BACKEND_PROXY_URL=
```

Then deploy as usual:

```bash
bash scripts/server/deploy-all.sh
```

## Deploy safety net (check / dry-run / subset / tolerate)

`deploy-all.sh` used to be all-or-nothing: one missing value in `deploy.env`
aborted the run *after* systemd and nginx had been modified, and one unavailable
integration repo stopped every other component.

Read-only pre-flight. No sudo, safe on a production host, works without a TTY:

```bash
bash scripts/server/check-config.sh
bash scripts/server/check-config.sh --dump      # resolved KEY=value config
bash scripts/server/check-config.sh --network   # also git ls-remote each repo
```

Preview a deploy, including on a host you must not touch:

```bash
bash scripts/server/deploy-all.sh --dry-run
bash scripts/server/deploy-all.sh --dump-config     # read-only, prints and exits
```

`--dry-run` shadows `sudo`, so `systemctl`, `nginx`, `rsync`, `git` and the
build steps only print `[dry-run] ...`. Config parsing, unit rendering and
validation still run. To prove that a deploy-script change does not alter how a
host resolves its config:

```bash
bash scripts/server/deploy-all.sh --dump-config > /tmp/before.conf   # old scripts
bash scripts/server/deploy-all.sh --dump-config > /tmp/after.conf    # new scripts
diff /tmp/before.conf /tmp/after.conf
```

Deploy a subset, or re-run only the component that failed:

```bash
bash scripts/server/deploy-all.sh --only=project5
bash scripts/server/deploy-all.sh --only=project5,topic3-benchmark
```

Keep going when optional integration pieces are unavailable:

```bash
bash scripts/server/deploy-all.sh --tolerate
# or: DEPLOY_STRICT=false in deploy.env
```

Tolerated steps print `tolerated failure: <label>` and the run still finishes
with the status summary. The default stays strict (abort on first failure),
which is what the 176 host has always done.

Components: `project5`, `topic1`, `topic1-value-qa`, `topic2-dynbench`,
`topic2-filterguard`, `topic2-showcase`, `topic3-benchmark`,
`topic3-cultural-gen`, `topic3-cultural-corpus`,
`topic3-cultural-assessment`, `topic3-compliance`, `topic3-difficulty`,
`topic3-risk`.

A hand-trimmed `deploy.env` (only the values that differ from
`deploy.env.example`) is supported: every `*_REPO_NAME` / `*_REPO_URL` defaults
to `git@github.com:${GITHUB_ORG:-NGAI-LLMSafeContent}/<repo name>.git`, so a
missing URL no longer aborts the deploy with `unbound variable`. `check-config.sh`
also flags `deploy.env` keys that no script reads (typical typo).

`bootstrap.sh` only enables a unit once its working directory exists; units for
repos that `deploy-all.sh` has not cloned yet are skipped with a warning instead
of restart-looping on a missing directory.

### nginx cannot read the deploy root

`deploy-all.sh` probes `www-data` readability of `PROJECT5_FRONTEND_ROOT` after
`rsync` and grants access when needed (ACL first, `chmod` fallback). Without it,
a deploy root created with a `027` umask (mode `750`) makes every page return
403/500 even though the build succeeded. The probe is a no-op on hosts that
already work.

### Firewall

`bootstrap.sh` only warns about public ports; opening them is a one-time sudo
step:

```bash
sudo ufw allow 5173/tcp
sudo ufw allow 5800/tcp
sudo ufw allow 6006/tcp
```

`deploy-all.sh` writes the Project 5 backend systemd deploy-env drop-in on every
run, so `BENCHMARK_BASE_URL` changes are applied without rerunning
`bootstrap.sh`. It includes proxy variables when `PROJECT5_BACKEND_PROXY_URL` is
non-empty, and omits them when the value is empty. After that it reloads systemd
and restarts the backend with the rest of the managed services.

## Benchmark management import credential

`/api/admin/benchmark/*` (Benchmark delivery upload and validation reports)
stays disabled (503) until `BENCHMARK_ADMIN_TOKEN` is set. It is an
independent secret: put it in the backend's `web/backend/.env` on the server
(`chmod 600`), not in `deploy.env` or the systemd unit, and restart
`llmsafe-project5-backend`. Staged deliveries go to
`BENCHMARK_DELIVERY_STAGING_ROOT` (default `benchmark-delivery-staging` under
the backend working directory). Limits and error codes:
`docs/architecture/topic3/2026-10-15-课题三风险Benchmark管理导入接口说明.md`.

## Project 5 governance task worker

Confirmed risk-corpus rescan (and other paid governance steps) are executed by a
separate process, not by the HTTP API:

```text
confirm → DB status=queued → llmsafe-project5-governance-worker → detect → result message
```

`bootstrap.sh` installs `llmsafe-project5-governance-worker`. Each
`deploy-all.sh` run (with `PROJECT5_GOVERNANCE_WORKER_ENABLED=true`, the default)
enables and restarts it alongside `llmsafe-project5-backend`, and writes the same
deploy-env drop-in (proxy / upstream URLs) into the worker unit.

If Activation Probe / FilterGuard / remote Topic 2 endpoints are down, the worker
still runs: tasks fail or complete partially with errors. Session browse and
other Project 5 APIs keep working.

Disable only the worker (leave API up):

```bash
PROJECT5_GOVERNANCE_WORKER_ENABLED=false
bash scripts/server/deploy-all.sh
```

Logs:

```bash
bash scripts/server/logs.sh llmsafe-project5-governance-worker
```

The `/integration` iframe path is a separate browser-direct entry and is not
covered by this BFF setting.

## Topic 3 Difficulty 182 remote router runtime

For August demo style runs, keep Project 5 and the public entry on the 176
server, and use `inference.example.invalid` only as the GPU inference side:

```text
Project 5 backend on 176
  -> 176 127.0.0.1:6332
  -> SSH tunnel
  -> 182 router 127.0.0.1:6332
  -> 182 generation worker 127.0.0.1:6333
  -> 182 guard worker 127.0.0.1:6334
```

Do not expose the 182 vLLM router or workers directly to the public internet.
They are OpenAI-compatible model endpoints and should stay behind SSH tunnel or
localhost-only access.

### 182 prerequisites

On `inference.example.invalid`, the expected default layout is:

```text
/home/zx/repos/Project_5_LLM_Content_Safety_Governance_Web
/home/zx/repos/Project_3_Dynamic_Difficulty_Question_Generation_Tool
/mnt/data1/zx/models/Qwen3.5-9B
/mnt/data1/zx/models/Qwen3Guard-Gen-4B
```

Both model directories must contain `config.json`, tokenizer files, and the
corresponding safetensors shards.

If GitHub SSH `22` is blocked on 182, configure the repo to use
`/home/zx/repos/ssh-keys/config` and GitHub SSH over `ssh.github.com:443`.
See `docs/guides/Server-182-GitHub-SSH-443拉代码配置.md` for the detailed
Git setup.

### Install/update the 182 runtime

On 182:

```bash
cd /home/zx/repos/Project_5_LLM_Content_Safety_Governance_Web

bash scripts/server/topic3-qwen35-remote-runtime.sh config
bash scripts/server/topic3-qwen35-remote-runtime.sh install
```

The script defaults to:

```text
conda env:          llmsafe-topic3-qwen35-vllm-py310
vLLM spec:          vllm==0.25.1
router port:        6332
generation port:    6333
guard port:         6334
generation model:   /mnt/data1/zx/models/Qwen3.5-9B
guard model:        /mnt/data1/zx/models/Qwen3Guard-Gen-4B
```

`install` does not require systemd or sudo. It creates/updates the conda env and
installs vLLM, FastAPI, Uvicorn, and HTTPX.

### Choose GPUs before starting

Check current GPU usage first:

```bash
nvidia-smi
```

Use GPUs with enough free memory. For example, if GPU 2 and GPU 3 are free:

```bash
TOPIC3_QWEN35_GENERATION_GPU=2 \
TOPIC3_QWEN35_GUARD_GPU=3 \
TOPIC3_QWEN35_GENERATION_GPU_MEMORY_UTILIZATION=0.75 \
TOPIC3_QWEN35_GUARD_GPU_MEMORY_UTILIZATION=0.60 \
bash scripts/server/topic3-qwen35-remote-runtime.sh start
```

If a previous runtime is still running, stop it first:

```bash
bash scripts/server/topic3-qwen35-remote-runtime.sh stop
```

Then start again with the selected GPU overrides. If vLLM reports free memory is
less than the requested utilization, lower the utilization values, for example
`0.65` for generation or `0.50` for guard, or choose emptier GPUs.

### Check 182 runtime status

After startup:

```bash
bash scripts/server/topic3-qwen35-remote-runtime.sh status
bash scripts/server/topic3-qwen35-remote-runtime.sh smoke
```

Expected readiness:

```text
ok generation http://127.0.0.1:6333/v1/models
ok guard      http://127.0.0.1:6334/v1/models
ok router     http://127.0.0.1:6332/healthz
```

`smoke` should show both routed model names from `6332/v1/models`:

```text
Qwen3.5-9B
Qwen3Guard-Gen-4B
```

Follow logs when startup or requests fail:

```bash
bash scripts/server/topic3-qwen35-remote-runtime.sh logs generation
bash scripts/server/topic3-qwen35-remote-runtime.sh logs guard
bash scripts/server/topic3-qwen35-remote-runtime.sh logs router
```

### Connect 176 to 182

There are two supported ways to connect 176 to 182.

Temporary test mode stops the 176 local router by hand and starts an SSH
tunnel in a terminal. This is useful to prove the diagnosis, but the next
`deploy-all.sh` can undo it if the deploy env is still in local mode:

```bash
sudo systemctl stop llmsafe-topic3-difficulty-router
sudo systemctl stop \
  llmsafe-topic3-difficulty-generation-worker \
  llmsafe-topic3-difficulty-guard-worker
ssh -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -L 6332:127.0.0.1:6332 \
  zx@inference.example.invalid
```

Run it inside tmux on 176 if you use this temporary mode:

```bash
tmux new -s topic3-182-tunnel
```

Use the durable `TOPIC3_DIFFICULTY_START_LOCAL_INFERENCE=false` mode below for
repeatable deploys; the temporary mode is only a quick manual proof.

The durable deployment mode is preferred for repeated `deploy-all.sh` runs when
the tunnel is managed outside these deployment scripts, for example by tmux,
WSL, autossh, or another supervisor. Set the 176 `scripts/server/deploy.env` to:

```bash
TOPIC3_DIFFICULTY_START_LOCAL_INFERENCE=false
TOPIC3_DIFFICULTY_BASE_URL=http://127.0.0.1:6331
TOPIC3_DIFFICULTY_VLLM_API_BASE=http://127.0.0.1:6332/v1
```

Then rerun:

```bash
bash scripts/server/bootstrap.sh
bash scripts/server/deploy-all.sh
```

With `TOPIC3_DIFFICULTY_START_LOCAL_INFERENCE=false`, 176 runs the Topic 3
difficulty agent on `6331`, but `deploy-all.sh` stops and disables the 176 local
vLLM router/workers on `6332/6333/6334`. Port `127.0.0.1:6332` on 176 must be
provided by the external tunnel to 182's router. This avoids the failure mode
where 176's local router accepts `/v1/models` but then tries to proxy inference
to missing local workers on `127.0.0.1:6333` and `127.0.0.1:6334`.

Verify from 176 with an actual inference request, not only `/v1/models`:

```bash
curl -sS http://127.0.0.1:6332/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen3.5-9B","messages":[{"role":"user","content":"请用一句话介绍安全评测。"}],"max_tokens":64,"temperature":0.2}'
```

If you use the WSL bridge below, keep that tmux session running independently.
`deploy-all.sh` will not create or restart the tunnel; it only keeps 176's local
router/workers out of the way when local inference is disabled.

If 176 cannot login to 182, but a desktop WSL can login to both 176 and 182, use
WSL as a bridge:

```text
176 127.0.0.1:6332
  -> SSH reverse tunnel
  -> WSL 127.0.0.1:6332
  -> SSH local tunnel
  -> 182 127.0.0.1:6332
```

In WSL:

```bash
tmux kill-session -t topic3-bridge 2>/dev/null || true
tmux new -s topic3-bridge
```

Window `to-182`:

```bash
tmux rename-window to-182
ssh -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -L 6332:127.0.0.1:6332 \
  zx@inference.example.invalid
```

Create a second tmux window with `Ctrl+B C`, then run:

```bash
tmux rename-window to-176
ssh -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -R 6332:127.0.0.1:6332 \
  zx@platform.example.invalid
```

Detach with `Ctrl+B D`. Reattach with:

```bash
tmux attach -t topic3-bridge
```

Verify from WSL:

```bash
curl -fsS http://127.0.0.1:6332/v1/models
```

Verify from 176:

```bash
curl -fsS http://127.0.0.1:6332/v1/models
```

### Configure Project 5 backend on 176

In `scripts/server/deploy.env` on 176, keep:

```bash
TOPIC3_DIFFICULTY_BASE_URL=http://127.0.0.1:6331
TOPIC3_DIFFICULTY_VLLM_API_BASE=http://127.0.0.1:6332/v1
```

`TOPIC3_DIFFICULTY_BASE_URL` points to the Topic 3 difficulty agent API on 176.
`TOPIC3_DIFFICULTY_VLLM_API_BASE` points to the localhost side of the tunnel
that ultimately reaches the 182 router.

After env changes:

```bash
sudo systemctl restart llmsafe-project5-backend
curl -fsS http://127.0.0.1:5173/api/health
curl -fsS http://127.0.0.1:6332/v1/models
```

Then open:

```text
http://platform.example.invalid:5173/benchmark
```

Start `topic3-difficulty-generation` live_run.

### Long-running progress note

Upstream Project 3 PR #6 switched generation from batch writes to continuous
concurrency. Samples are appended to `samples.jsonl` as soon as each item
passes quality checks, controlled by `llm_composer.concurrency` (Project 5 no
longer sends `generation.batch_size`). Progress should advance sample-by-sample;
if `generated` stays at `0` while `worker_state.discard_counts` grows, the
pipeline is rejecting candidates rather than waiting for a full batch:

```bash
curl -fsS http://127.0.0.1:6331/api/generation/jobs/<job_id> | jq .
tail -n 120 -f /data/zhangxu/repos/Project_3_Dynamic_Difficulty_Question_Generation_Tool/runs/<job_id>/worker.log
```

For demo runs, lower `llm_composer.concurrency` / retry settings in the
Project 5 payload rather than waiting indefinitely.

## Topic 3 Cultural Corpus

`deploy-all.sh` also clones or updates
`Project_3_Cultural_Diversity_Corpus_Generation_Tool`. Project 5 reads
pre-run corpus assets from its local `framework/runs` directory through:

```text
CULTURAL_CORPUS_RUNS_DIR=/data/zhangxu/repos/Project_3_Cultural_Diversity_Corpus_Generation_Tool/framework/runs
```

This is an artifact path, not a public service. The corresponding Project 5
BFF endpoint is:

```bash
curl -fsS "http://127.0.0.1:5800/api/output/culture/corpus-samples?include_live_runs=true&limit=1"
```

If the repository is present but the endpoint still reports a missing
`CULTURAL_CORPUS_RUNS_DIR`, check the backend systemd environment:

```bash
sudo systemctl show llmsafe-project5-backend -p Environment
```

Then rerun:

```bash
bash scripts/server/deploy-all.sh
```

## Topic 3 Dynamic Risk (local snapshot)

`Project_3_Dynamic_Risk_Benchmark_Generation` is an offline generation package.
`deploy-all.sh` **never** `git clone` / `git pull`s it from GitHub. It only
checks that `${TOPIC3_RISK_DIR}` already exists under `REPOS_DIR`; if missing,
deploy continues with a warning and risk live_run CLI stays unavailable.

Sync that tree onto amax with the bare-repo workflow in
`docs/operations/2026-08-19-课题三动态风险Benchmark-amax裸仓Git同步方案.md`
(local `git push`, server worktree `git pull`). Then point:

```bash
TOPIC3_RISK_BENCHMARK_PROJECT_ROOT=/data/zhangxu/repos/Project_3_Dynamic_Risk_Benchmark_Generation
TOPIC3_RISK_REUSE_DIFFICULTY_QWEN=true
TOPIC3_RISK_AGENT_URL=http://127.0.0.1:6351/chat
TOPIC3_RISK_QWEN_API_BASE=http://127.0.0.1:6332/v1
```

When the snapshot contains `qwen_agent_server/agent_server.py` and
`live_run_adapter.py`, `deploy-all.sh` installs conda env
`llmsafe-topic3-risk-py310`, writes `llmsafe-topic3-risk-agent`, and starts it
on `127.0.0.1:6351`. The Agent process gets `QWEN_BASE_URL` from the difficulty
router (`6332`) and `QWEN_MODEL=Qwen3.5-9B`. Do **not** point
`TOPIC3_RISK_AGENT_URL` at the difficulty Agent on `6331`.

Dedicated Qwen `:6352` stays reserved. Set
`TOPIC3_RISK_REUSE_DIFFICULTY_QWEN=false` only if you actually start a separate
vLLM on `6352`.

## Topic 3 Cultural Assessment

`deploy-all.sh` also clones or updates
`Project_3_Cultural_Diversity_Assessment_Tool` and restarts the local-only
console service:

```text
llmsafe-topic3-cultural-assessment-console    -> http://127.0.0.1:8877
llmsafe-topic3-cultural-assessment-console-v2 -> http://127.0.0.1:8878
```

Project 5 reads static assessment assets through `CULTURAL_ASSESSMENT_ROOT` and
proxies runtime console APIs through `CULTURAL_ASSESSMENT_CONSOLE_BASE_URL`
and `CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL`. Keep `8877` and `8878` bound
to `127.0.0.1`; browser access should go through Project 5's
`/api/output/culture-assessment/*` BFF endpoints.

The two console services are not interchangeable. The v1 service runs
`culture_eval_console/server.py` on `8877` for the original cultural assessment
console tasks. The v2 service runs `culture_eval_console_v2/server.py` on
`8878`; Project 5 routes
`framework_cultural_diversity_evaluation_dataset_v1*` datasets to v2 directly,
and also falls back to v2 for `target_mode=reference` jobs that v1 rejects.
This includes the Cultural Diversity Evaluation Dataset V1(1/10/100/500)
realtime benchmark validation and model-comparison flows. Port `8878` is
registered in `docs/integration/ports.registry.yaml`.

Dynamic assessment jobs read provider secrets from the assessment project's own
environment file, not from Project 5's deploy env:

```bash
sudo tee /data/zhangxu/repos/Project_3_Cultural_Diversity_Assessment_Tool/.env >/dev/null <<'EOF'
DEEPSEEK_API_KEY=sk-...
EOF
sudo chmod 600 /data/zhangxu/repos/Project_3_Cultural_Diversity_Assessment_Tool/.env
sudo systemctl restart llmsafe-topic3-cultural-assessment-console
sudo systemctl restart llmsafe-topic3-cultural-assessment-console-v2
```
