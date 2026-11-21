# AutoDL Deployment Scripts

These scripts are the AutoDL-only deployment path for the August 1 demo. They
are intentionally separate from `scripts/server` and from the local
`node scripts/start-platform.mjs` workflow.

## Phase 1 Scope

Phase 1 created the command surface and deployment configuration skeleton.
Phase 2 adds a Project 5-only no-GPU runtime:

- `deploy.env.example`
- `common.sh`
- `bootstrap.sh`
- `services.sh`
- `difficulty-runtime.sh`
- `gateway.conf.template`

The Project 5 service path does not launch GPU workers. Topic 3 vLLM remains
manual and is controlled by `difficulty-runtime.sh`.

## First Commands on AutoDL

```bash
cd /root/autodl-tmp/llmsafe/repos/Project_5_LLM_Content_Safety_Governance_Web
cp scripts/autodl/deploy.env.example scripts/autodl/deploy.env
bash scripts/autodl/bootstrap.sh config
bash scripts/autodl/bootstrap.sh prepare
bash scripts/autodl/bootstrap.sh check
bash scripts/autodl/bootstrap.sh install-project5
bash scripts/autodl/services.sh plan
bash scripts/autodl/services.sh start-project5
bash scripts/autodl/services.sh smoke
```

To prepare the other non-GPU demo dependencies without starting them:

```bash
bash scripts/autodl/bootstrap.sh install-topic1
bash scripts/autodl/bootstrap.sh install-topic2
bash scripts/autodl/bootstrap.sh install-topic3-light
```

Or run the whole non-vLLM install profile:

```bash
bash scripts/autodl/bootstrap.sh install-light
```

## Deployment Invariants

- `scripts/server/*` remains the 176-server deployment path.
- `scripts/start-platform.mjs` remains the local development path.
- AutoDL gateway owns port `6006`.
- Topic 3 Benchmark uses internal port `6106` only in the AutoDL path.
- vLLM generation and guard workers are manual opt-in services.

## Project 5 No-GPU Runtime

`services.sh start-project5` starts:

- Project 5 backend on `127.0.0.1:5800`
- a Node gateway on `0.0.0.0:6006`

The gateway serves the built frontend and proxies:

- `/api/health` -> backend `/health`
- `/api/*` -> backend `/api/*`

## Light Install Profile

`bootstrap.sh install-light` installs and builds Project 5, Topic 1, Topic 2,
and the non-vLLM Topic 3 services. It does not start any service and does not
touch the Topic 3 dynamic difficulty GPU workers.

## Planned GPU Phase

The next GPU phase will fill in manual `install`, `start`, `stop`, `status`,
and `smoke` for vLLM in `difficulty-runtime.sh`.
