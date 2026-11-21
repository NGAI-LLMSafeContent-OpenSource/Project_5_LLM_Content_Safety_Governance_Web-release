import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { formatTemplate, isPortListening, resolveSiblingRepo } from './registry.mjs'
import { buildSpawnEnv } from './spawn-env.mjs'

export const TOPIC4_INPUT_WORKFLOW_SYSTEM_ID = 'topic4-input-workflow'
export const TOPIC4_INPUT_WORKFLOW_HEALTH_POLL_ATTEMPTS = 40
export const TOPIC4_INPUT_WORKFLOW_HEALTH_POLL_INTERVAL_MS = 500

function joinUrl(host, port, pathValue) {
  const normalizedPath = pathValue?.startsWith('/') ? pathValue : `/${pathValue ?? ''}`
  return `http://${host}:${port}${normalizedPath}`
}

function topic4Context(registry, system) {
  return {
    host: registry.host,
    api_port: system.api_port,
    port: system.api_port,
  }
}

export function buildTopic4InputWorkflowEnv(registry, system) {
  const ctx = topic4Context(registry, system)
  return {
    TOPIC4_INPUT_WORKFLOW_BASE_URL: `http://${registry.host}:${ctx.port}`,
  }
}

export function buildTopic4InputWorkflowSpec(system, registry) {
  const start = system.start?.single
  if (!start) {
    return null
  }

  const ctx = topic4Context(registry, system)
  const cwd = path.join(resolveSiblingRepo(system.repo), start.cwd ?? '')
  const healthPath = system.health_path ?? start.health_path ?? '/api/health'

  return {
    id: system.id,
    cwd,
    command: formatTemplate(start.command, ctx),
    port: ctx.port,
    host: registry.host,
    healthUrl: joinUrl(registry.host, ctx.port, healthPath),
    optional: start.optional !== false,
    logPath: path.join(cwd, start.log_path ?? '.project5-topic4-input-workflow.log'),
  }
}

export function normalizeTopic4InputWorkflowCommand({
  command,
  cwd,
  platform = process.platform,
  existsSync = fs.existsSync,
}) {
  if (!command.startsWith('python ')) {
    return command
  }

  const pythonExecutable =
    platform === 'win32'
      ? path.join(cwd, '.venv-win', 'Scripts', 'python.exe')
      : path.join(cwd, '.venv', 'bin', 'python')

  if (!existsSync(pythonExecutable)) {
    return null
  }

  return `"${pythonExecutable}"${command.slice('python'.length)}`
}

export function buildTopic4InputWorkflowSetupHint({ cwd, platform = process.platform }) {
  if (platform === 'win32') {
    return [
      `cd "${cwd}"`,
      'py -3 -m venv .venv-win',
      '.venv-win\\Scripts\\python.exe -m pip install --upgrade pip',
      '.venv-win\\Scripts\\python.exe -m pip install flask flasgger flask-cors httpx openai open-dataflow',
      '.venv-win\\Scripts\\python.exe app.py --host 0.0.0.0 --port 8081',
    ]
  }

  return [
    `cd "${cwd}"`,
    'python3 -m venv .venv',
    '. .venv/bin/activate',
    'python -m pip install --upgrade pip',
    'python -m pip install flask flasgger flask-cors httpx openai open-dataflow',
    'python app.py --host 0.0.0.0 --port 8081',
  ]
}

export async function checkTopic4InputWorkflowHealth({
  url,
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
    return body?.status === 'healthy'
  } catch {
    return false
  }
}

async function waitForTopic4InputWorkflowHealth({
  spec,
  attempts,
  intervalMs,
  fetchImpl,
}) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await checkTopic4InputWorkflowHealth({ url: spec.healthUrl, fetchImpl })) {
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

export async function startTopic4InputWorkflow({
  system,
  registry,
  label = 'topic4-input-workflow',
  platform = process.platform,
  trackChild = (child) => child,
  spawnImpl = spawn,
  fetchImpl = globalThis.fetch,
  existsSync = fs.existsSync,
  openSync = fs.openSync,
  writeFileSync = fs.writeFileSync,
  isPortListeningImpl = isPortListening,
  consoleWarn = console.warn,
  attempts = TOPIC4_INPUT_WORKFLOW_HEALTH_POLL_ATTEMPTS,
  intervalMs = TOPIC4_INPUT_WORKFLOW_HEALTH_POLL_INTERVAL_MS,
}) {
  try {
    const spec = buildTopic4InputWorkflowSpec(system, registry)
    if (!spec) {
      consoleWarn(`[${label}] missing start.single config in ports.registry.yaml`)
      return null
    }

    if (await checkTopic4InputWorkflowHealth({ url: spec.healthUrl, fetchImpl })) {
      console.log(`[${label}] ready: reusing healthy service at ${spec.healthUrl}`)
      return null
    }

    if (await isPortListeningImpl(spec.port, spec.host)) {
      consoleWarn(
        `[${label}] port ${spec.port} is occupied but health check failed; status=port occupied`,
      )
      return null
    }

    if (!existsSync(spec.cwd)) {
      consoleWarn(`[${label}] repo missing: ${spec.cwd}`)
      return null
    }

    const command = normalizeTopic4InputWorkflowCommand({
      command: spec.command,
      cwd: spec.cwd,
      platform,
      existsSync,
    })

    if (!command) {
      consoleWarn(`[${label}] dependencies missing; status=skipped`)
      consoleWarn(
        `[${label}] expected python environment is missing; create it with:`,
      )
      for (const line of buildTopic4InputWorkflowSetupHint({ cwd: spec.cwd, platform })) {
        consoleWarn(`[${label}]   ${line}`)
      }
      return null
    }

    writeFileSync(spec.logPath, `[${new Date().toISOString()}] ${command}\n`, { flag: 'a' })
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
      consoleWarn(`[${label}] optional upstream process error: ${message}`)
    })
    trackChild(child, label, { critical: false })
    child.unref?.()

    if (
      await waitForTopic4InputWorkflowHealth({
        spec,
        attempts,
        intervalMs,
        fetchImpl,
      })
    ) {
      console.log(`[${label}] ready at ${spec.healthUrl}`)
      return child
    }

    consoleWarn(
      `[${label}] started but health check failed before timeout; status=health failed`,
    )
    consoleWarn(`[${label}] see log: ${spec.logPath}`)
    return child
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    consoleWarn(`[${label}] optional upstream failed: ${message}`)
    return null
  }
}
