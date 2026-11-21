import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import {
  bashQuote,
  shellQuoteCommand,
} from './python-runtime.mjs'
import {
  formatTemplate,
  isPortListening,
  resolveSiblingRepo,
} from './registry.mjs'
import { buildSpawnEnv } from './spawn-env.mjs'

export const TOPIC2_FILTERGUARD_SYSTEM_ID = 'topic2-filterguard'
export const TOPIC2_FILTERGUARD_HEALTH_POLL_ATTEMPTS = 40
export const TOPIC2_FILTERGUARD_HEALTH_POLL_INTERVAL_MS = 500

function joinUrl(host, port, pathValue) {
  const normalizedPath = pathValue?.startsWith('/')
    ? pathValue
    : `/${pathValue ?? ''}`
  return `http://${host}:${port}${normalizedPath}`
}

function filterGuardContext(registry, system) {
  return {
    host: registry.host,
    ui_port: system.ui_port,
    api_port: system.api_port ?? system.ui_port,
    port: system.api_port ?? system.ui_port,
    method: system.method ?? 'keyword',
  }
}

export function buildTopic2FilterGuardEnv(registry, system) {
  const ctx = filterGuardContext(registry, system)
  return {
    TOPIC2_FILTERGUARD_BASE_URL: `http://${registry.host}:${ctx.port}`,
    TOPIC2_FILTERGUARD_METHOD: ctx.method,
    TOPIC2_FILTERGUARD_TIMEOUT_SECONDS: String(system.timeout_seconds ?? 10),
    TOPIC2_ACTIVATION_PROBE_BASE_URL:
      process.env.TOPIC2_ACTIVATION_PROBE_BASE_URL ||
      'https://u165979-8749-15195365.westc.seetacloud.com:8443',
    TOPIC2_ACTIVATION_PROBE_TIMEOUT_SECONDS:
      process.env.TOPIC2_ACTIVATION_PROBE_TIMEOUT_SECONDS || '60',
    TOPIC2_ACTIVATION_PROBE_MAX_BATCH:
      process.env.TOPIC2_ACTIVATION_PROBE_MAX_BATCH || '30',
    TOPIC2_RISK_DETECT_METHOD:
      process.env.TOPIC2_RISK_DETECT_METHOD || 'activation_probe',
  }
}

export function buildTopic2FilterGuardSpec(system, registry) {
  const start = system.start?.single
  if (!start) {
    return null
  }

  const ctx = filterGuardContext(registry, system)
  const cwd = path.join(resolveSiblingRepo(system.repo), start.cwd ?? '')
  const healthPath = system.health_path ?? start.health_path ?? '/health'

  return {
    id: system.id,
    cwd,
    command: formatTemplate(start.command, ctx),
    port: ctx.port,
    host: registry.host,
    method: ctx.method,
    healthUrl: joinUrl(registry.host, ctx.port, healthPath),
    optional: start.optional !== false,
    logPath: path.join(cwd, start.log_path ?? '.project5-filterguard.log'),
  }
}

export function normalizeFilterGuardCommand({
  command,
  cwd,
  platform = process.platform,
  wslDistro = 'Ubuntu',
  existsSync = fs.existsSync,
  resolveWslPath,
}) {
  const match = command.match(/^filterguard(?<args>(\s.*)?$)/)
  if (!match) {
    return command
  }

  const args = match.groups?.args?.trim() ?? ''
  const linuxVenvScript = path.join(cwd, '.venv', 'bin', 'filterguard')
  if (!existsSync(linuxVenvScript)) {
    if (platform === 'win32') {
      return null
    }
    return command
  }

  const venvCommand = `'.venv/bin/filterguard'${args ? ` ${args}` : ''}`
  if (platform === 'win32') {
    if (!resolveWslPath) {
      throw new Error('resolveWslPath is required for Windows WSL FilterGuard startup')
    }
    const wslCwd = resolveWslPath(cwd)
    const bashScript = `cd ${bashQuote(wslCwd)} && ${venvCommand}`
    return `wsl.exe -d ${shellQuoteCommand(wslDistro)} -- bash -lc ${shellQuoteCommand(bashScript)}`
  }

  return venvCommand
}

export async function checkTopic2FilterGuardHealth({
  url,
  method = 'keyword',
  fetchImpl = globalThis.fetch,
}) {
  try {
    const response = await fetchImpl(url, {
      signal: AbortSignal.timeout(1500),
    })
    if (!response.ok) {
      return false
    }
    const body = await response.json()
    const methods = Array.isArray(body?.methods) ? body.methods.map(String) : []
    return body?.status === 'ok' && methods.includes(method)
  } catch {
    return false
  }
}

async function waitForTopic2FilterGuardHealth({
  spec,
  attempts,
  intervalMs,
  fetchImpl,
}) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (
      await checkTopic2FilterGuardHealth({
        url: spec.healthUrl,
        method: spec.method,
        fetchImpl,
      })
    ) {
      return true
    }
    if (attempt < attempts - 1) {
      await new Promise((resolve) => {
        setTimeout(resolve, intervalMs)
      })
    }
  }
  return false
}

export async function startTopic2FilterGuard({
  system,
  registry,
  label = 'topic2-filterguard',
  platform = process.platform,
  wslDistro = 'Ubuntu',
  resolveWslPath,
  trackChild = (child) => child,
  spawnImpl = spawn,
  fetchImpl = globalThis.fetch,
  existsSync = fs.existsSync,
  openSync = fs.openSync,
  writeFileSync = fs.writeFileSync,
  isPortListeningImpl = isPortListening,
  attempts = TOPIC2_FILTERGUARD_HEALTH_POLL_ATTEMPTS,
  intervalMs = TOPIC2_FILTERGUARD_HEALTH_POLL_INTERVAL_MS,
}) {
  try {
    const spec = buildTopic2FilterGuardSpec(system, registry)
    if (!spec) {
      console.warn(`[${label}] missing start.single config in ports.registry.yaml`)
      return null
    }

    if (
      await checkTopic2FilterGuardHealth({
        url: spec.healthUrl,
        method: spec.method,
        fetchImpl,
      })
    ) {
      console.log(`[${label}] ready: reusing healthy service at ${spec.healthUrl}`)
      return null
    }

    if (await isPortListeningImpl(spec.port, spec.host)) {
      console.warn(
        `[${label}] port ${spec.port} is occupied but health check failed; status=port occupied`,
      )
      return null
    }

    if (!existsSync(spec.cwd)) {
      console.warn(`[${label}] repo missing: ${spec.cwd}`)
      return null
    }

    const command = normalizeFilterGuardCommand({
      command: spec.command,
      cwd: spec.cwd,
      platform,
      wslDistro,
      resolveWslPath,
      existsSync,
    })

    if (!command) {
      console.warn(`[${label}] dependencies missing; status=skipped`)
      console.warn(
        `[${label}] In WSL/POSIX run: cd Project_2_Anomaly_Data_Identification && python -m venv .venv && . .venv/bin/activate && pip install -e .`,
      )
      return null
    }

    writeFileSync(
      spec.logPath,
      `[${new Date().toISOString()}] ${command}\n`,
      { flag: 'a' },
    )
    const logFd = openSync(spec.logPath, 'a')

    console.log(`[${label}] starting optional upstream on port ${spec.port}`)
    console.log(`[${label}] cd ${spec.cwd}`)
    console.log(`[${label}] ${command}`)
    console.log(`[${label}] log: ${spec.logPath}`)

    const child = spawnImpl(command, {
      cwd: spec.cwd,
      env: buildSpawnEnv(process.env),
      shell: true,
      detached: true,
      stdio: ['ignore', logFd, logFd],
      windowsHide: true,
    })
    child.on?.('error', (error) => {
      const message = error instanceof Error ? error.message : String(error)
      console.warn(`[${label}] optional upstream process error: ${message}`)
    })
    trackChild(child, label, { critical: false })
    child.unref?.()

    if (
      await waitForTopic2FilterGuardHealth({
        spec,
        attempts,
        intervalMs,
        fetchImpl,
      })
    ) {
      console.log(`[${label}] ready at ${spec.healthUrl}`)
      return child
    }

    console.warn(
      `[${label}] started but health check failed before timeout; status=health failed`,
    )
    console.warn(`[${label}] see log: ${spec.logPath}`)
    return child
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn(`[${label}] optional upstream failed: ${message}`)
    return null
  }
}
