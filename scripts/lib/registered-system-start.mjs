import { buildSystemStartSpecs } from './system-start-spec.mjs'
import { findSystem } from './registry.mjs'

const DEFAULT_ROLE_OPTIONS = {
  data: {},
  backend: {
    exactEnv: true,
  },
  frontend: {},
}

function mergeRoleOptions(role, roleOptions, normalizeTopicBackendCommand) {
  const base = DEFAULT_ROLE_OPTIONS[role] ?? {}
  const override = roleOptions[role] ?? {}
  const normalizeCommand =
    override.normalizeCommand ??
    (role === 'data' ? (spec) => spec : normalizeTopicBackendCommand)

  return {
    ...base,
    ...override,
    normalizeCommand,
  }
}

export async function startRegisteredSystem({
  systemId,
  registry,
  roles,
  healthChecks,
  roleOptions = {},
  deps,
}) {
  const {
    startSystemRole,
    normalizeTopicBackendCommand,
    findSystem: findSystemImpl = findSystem,
    buildSystemStartSpecs: buildSpecs = buildSystemStartSpecs,
  } = deps

  const system = findSystemImpl(registry, systemId)
  const specs = buildSpecs(system, registry)
  const iframeUrl = `http://${registry.host}:${system.ui_port}`

  console.log(`[${systemId}] starting registered multi-role service`)

  let allReady = true
  for (const role of roles) {
    const check = healthChecks[role]
    if (!check) {
      console.warn(`[${systemId}] missing health check for role: ${role}`)
      allReady = false
      continue
    }

    const options = mergeRoleOptions(role, roleOptions, normalizeTopicBackendCommand)
    const ready = await startSystemRole({
      label: `${systemId}:${role}`,
      spec: specs[role],
      healthUrl: check.url,
      port: check.port,
      host: registry.host,
      ...options,
    })

    if (!ready) {
      allReady = false
    }
  }

  if (!allReady) {
    console.warn(`[${systemId}] iframe will be unavailable at ${iframeUrl}`)
  }

  return allReady
}
