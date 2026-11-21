import fs from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const REPO_ROOT = path.resolve(__dirname, '../..')
export const REGISTRY_PATH = path.join(REPO_ROOT, 'docs/integration/ports.registry.yaml')
const require = createRequire(import.meta.url)

function loadYaml() {
  try {
    return require('yaml')
  } catch {
    try {
      return require(path.join(REPO_ROOT, 'web/frontend/node_modules/yaml'))
    } catch {
      return require(path.join(REPO_ROOT, 'web/frontend/node_modules/.pnpm/node_modules/yaml'))
    }
  }
}

export function loadRegistry() {
  const raw = fs.readFileSync(REGISTRY_PATH, 'utf8')
  const YAML = loadYaml()
  return YAML.parse(raw)
}

export function resolveSiblingRepo(repoName) {
  const candidates = [
    path.resolve(REPO_ROOT, '..', repoName),
    path.resolve(REPO_ROOT, '..', '..', repoName),
  ]
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate
    }
  }
  return candidates[0]
}

export function formatTemplate(value, ctx) {
  if (typeof value !== 'string') {
    return value
  }
  return value.replace(/\{(\w+)\}/g, (_, key) => {
    if (key in ctx) {
      return String(ctx[key])
    }
    throw new Error(`Unknown template key: {${key}}`)
  })
}

export function systemContext(registry, system) {
  const ctx = {
    host: registry.host,
    port: system.ui_port,
  }
  for (const [key, value] of Object.entries(system)) {
    if (key.endsWith('_port') && value != null) {
      ctx[key] = value
    }
  }
  return ctx
}

export function getTunnelPort(registry, uiPort) {
  return registry.tunnel_offset + uiPort
}

export async function isPortListening(port, host = '127.0.0.1') {
  const net = await import('node:net')
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host }, () => {
      socket.end()
      resolve(true)
    })
    socket.on('error', () => resolve(false))
    socket.setTimeout(500, () => {
      socket.destroy()
      resolve(false)
    })
  })
}

export function findSystem(registry, systemId) {
  const system = registry.systems.find((item) => item.id === systemId)
  if (!system) {
    throw new Error(`Unknown system id: ${systemId}`)
  }
  return system
}
