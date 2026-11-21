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

export const TOPIC2_AUTOBENCH_SYSTEM_ID = 'topic2-dynbench'
export const TOPIC2_UPSTREAM_HEALTH_POLL_ATTEMPTS = 60
export const TOPIC2_UPSTREAM_HEALTH_POLL_INTERVAL_MS = 500

function joinUrl(host, port, pathValue) {
  const normalizedPath = pathValue?.startsWith('/')
    ? pathValue
    : `/${pathValue ?? ''}`
  return `http://${host}:${port}${normalizedPath}`
}

function upstreamContext(registry, upstream) {
  return {
    host: registry.host,
    ui_port: upstream.ui_port,
    port: upstream.ui_port,
  }
}

export function buildTopic2AutoBenchUpstreamSpec(system, registry) {
  const upstream = system.start?.upstream
  if (!upstream) {
    return null
  }

  const ctx = upstreamContext(registry, upstream)
  const cwd = path.join(resolveSiblingRepo(upstream.repo), upstream.cwd ?? '')
  const healthPath = upstream.health_path ?? '/api/health'
  const webuiPath = upstream.webui_path ?? '/agent'

  return {
    id: upstream.id,
    cwd,
    command: formatTemplate(upstream.command, ctx),
    port: upstream.ui_port,
    host: registry.host,
    healthUrl: joinUrl(registry.host, upstream.ui_port, healthPath),
    webuiUrl: joinUrl(registry.host, upstream.ui_port, webuiPath),
    expected: upstream.expected ?? { status: 'ok', service: 'autobench-agent' },
    optional: upstream.optional !== false,
    logPath: path.join(cwd, upstream.log_path ?? '.project5-autobench-web.log'),
  }
}

export function normalizeAutoBenchCommand({
  command,
  cwd,
  platform = process.platform,
  wslDistro = 'Ubuntu',
  existsSync = fs.existsSync,
  resolveWslPath,
}) {
  const match = command.match(/^autobench-web(?<args>(\s.*)?$)/)
  if (!match) {
    return command
  }

  const args = match.groups?.args?.trim() ?? ''
  const linuxVenvScript = path.join(cwd, '.venv', 'bin', 'autobench-web')
  if (!existsSync(linuxVenvScript)) {
    if (platform === 'win32') {
      return null
    }
    return command
  }

  const venvCommand = `'.venv/bin/autobench-web'${args ? ` ${args}` : ''}`
  if (platform === 'win32') {
    if (!resolveWslPath) {
      throw new Error('resolveWslPath is required for Windows WSL AutoBench startup')
    }
    const wslCwd = resolveWslPath(cwd)
    const bashScript = `cd ${bashQuote(wslCwd)} && ${venvCommand}`
    return `wsl.exe -d ${shellQuoteCommand(wslDistro)} -- bash -lc ${shellQuoteCommand(bashScript)}`
  }

  return venvCommand
}

export async function checkTopic2AutoBenchHealth({
  url,
  expected,
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
    return (
      body?.status === expected.status &&
      body?.service === expected.service
    )
  } catch {
    return false
  }
}

async function waitForTopic2AutoBenchHealth({
  spec,
  attempts,
  intervalMs,
  fetchImpl,
}) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (
      await checkTopic2AutoBenchHealth({
        url: spec.healthUrl,
        expected: spec.expected,
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

export async function startTopic2AutoBenchUpstream({
  system,
  registry,
  label = 'topic2-autobench-web',
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
  attempts = TOPIC2_UPSTREAM_HEALTH_POLL_ATTEMPTS,
  intervalMs = TOPIC2_UPSTREAM_HEALTH_POLL_INTERVAL_MS,
}) {
  try {
    const spec = buildTopic2AutoBenchUpstreamSpec(system, registry)
    if (!spec) {
      console.warn(`[${label}] missing start.upstream config in ports.registry.yaml`)
      return null
    }

    if (
      await checkTopic2AutoBenchHealth({
        url: spec.healthUrl,
        expected: spec.expected,
        fetchImpl,
      })
    ) {
      console.log(`[${label}] reusing healthy service at ${spec.healthUrl}`)
      return null
    }

    if (await isPortListeningImpl(spec.port, spec.host)) {
      console.warn(
        `[${label}] port ${spec.port} is occupied but health check failed; skipping optional upstream`,
      )
      console.warn(
        `[${label}] if a stale WSL process owns 8766, stop it manually before retrying`,
      )
      return null
    }

    if (!existsSync(spec.cwd)) {
      console.warn(`[${label}] optional upstream repo missing: ${spec.cwd}`)
      return null
    }

    const command = normalizeAutoBenchCommand({
      command: spec.command,
      cwd: spec.cwd,
      platform,
      wslDistro,
      resolveWslPath,
      existsSync,
    })

    if (!command) {
      console.warn(`[${label}] AutoBench dependencies may be missing.`)
      console.warn(
        `[${label}] Run pip install -e . in Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction.`,
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
      await waitForTopic2AutoBenchHealth({
        spec,
        attempts,
        intervalMs,
        fetchImpl,
      })
    ) {
      console.log(`[${label}] ready at ${spec.webuiUrl}`)
      return child
    }

    console.warn(
      `[${label}] started but health check did not pass before timeout; continuing platform startup`,
    )
    console.warn(`[${label}] see log: ${spec.logPath}`)
    return child
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn(`[${label}] optional upstream failed: ${message}`)
    return null
  }
}
