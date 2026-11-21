export const TOPIC3_DIFFICULTY_RUNTIME_HINT =
  'topic3 difficulty live_run requires server-side router/workers; local start-platform does not manage them'

export function buildTopic3DifficultyRuntimeChecks(system, registry) {
  const host = registry.host
  return [
    {
      key: 'router',
      label: 'vLLM router',
      url: `http://${host}:${system.model_router_port}/healthz`,
    },
    {
      key: 'generation_worker',
      label: 'generation worker',
      url: `http://${host}:${system.generation_worker_port}/v1/models`,
    },
    {
      key: 'guard_worker',
      label: 'guard worker',
      url: `http://${host}:${system.guard_worker_port}/v1/models`,
    },
  ]
}

export async function checkTopic3DifficultyRuntime(system, registry, isHttpOk) {
  const checks = buildTopic3DifficultyRuntimeChecks(system, registry)
  const results = []
  for (const check of checks) {
    results.push({
      ...check,
      ready: await isHttpOk(check.url),
    })
  }
  return results
}

export function summarizeTopic3DifficultyRuntime(results) {
  const missing = results.filter((item) => !item.ready)
  return {
    ready: missing.length === 0,
    missing,
  }
}
