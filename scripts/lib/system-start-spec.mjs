import path from 'node:path'
import {
  formatTemplate,
  resolveSiblingRepo,
  systemContext,
} from './registry.mjs'

const FRONTEND_ENV_BLOCKLIST = ['VITE_API_BASE_URL', 'VITE_WS_BASE_URL']

function sanitizeInheritedEnv(env, role) {
  const sanitized = { ...env }
  if (role !== 'frontend') {
    return sanitized
  }
  for (const key of FRONTEND_ENV_BLOCKLIST) {
    delete sanitized[key]
  }
  return sanitized
}

export function buildSystemStartSpec(system, registry, role, options = {}) {
  const block = system.start?.[role]
  if (!block) {
    return null
  }

  const ctx = systemContext(registry, system)
  if (options.uiPortOverride != null) {
    ctx.ui_port = options.uiPortOverride
    ctx.port = options.uiPortOverride
    if (system.api_port != null) {
      ctx.api_port = options.uiPortOverride + 1
    }
    if (system.data_port != null) {
      ctx.data_port = options.uiPortOverride + 2
    }
  }

  const env = sanitizeInheritedEnv(process.env, role)
  if (block.env) {
    for (const [key, value] of Object.entries(block.env)) {
      env[key] = formatTemplate(String(value), ctx)
    }
  }

  return {
    cwd: path.join(resolveSiblingRepo(system.repo), block.cwd ?? ''),
    command: formatTemplate(block.command, ctx),
    env,
  }
}

export function buildSystemStartSpecs(system, registry, options = {}) {
  return {
    data: buildSystemStartSpec(system, registry, 'data', options),
    backend: buildSystemStartSpec(system, registry, 'backend', options),
    frontend: buildSystemStartSpec(system, registry, 'frontend', options),
    single: buildSystemStartSpec(system, registry, 'single', options),
  }
}
