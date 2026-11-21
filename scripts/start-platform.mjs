#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import {
  benchmarkEnvironment,
  benchmarkUrlForMode,
  buildBenchmarkStartScript,
  buildBenchmarkStopScript,
  checkBenchmarkHealth,
} from './lib/benchmark-startup.mjs'
import {
  createChildExitHandler,
  shouldCleanupBeforeExit,
} from './lib/process-lifecycle.mjs'
import { isHttpOk, waitForHttpOk } from './lib/http-health.mjs'
import { hasNodeModules } from './lib/frontend-dependencies.mjs'
import {
  bashQuote,
  isLinuxPythonExecutable,
  replaceLeadingPythonCommandForBash,
  replaceLeadingPythonCommand,
  resolvePythonExecutable,
  toPosixRelativePath,
} from './lib/python-runtime.mjs'
import {
  findSystem,
  formatTemplate,
  isPortListening,
  loadRegistry,
  REPO_ROOT,
  systemContext,
} from './lib/registry.mjs'
import { buildSystemStartSpecs } from './lib/system-start-spec.mjs'
import { buildSpawnEnv, describeProxySanitize } from './lib/spawn-env.mjs'
import { parsePlatformArgs } from './lib/platform-args.mjs'
import { startTopic1CorpusTools } from './lib/topic1-corpus-tools-start.mjs'
import { startRegisteredSystem } from './lib/registered-system-start.mjs'
import { startTopic2AutoBenchUpstream } from './lib/topic2-autobench-upstream.mjs'
import {
  buildTopic2FilterGuardEnv,
  startTopic2FilterGuard,
  TOPIC2_FILTERGUARD_SYSTEM_ID,
} from './lib/topic2-filterguard-upstream.mjs'
import {
  buildTopic4InputWorkflowEnv,
  startTopic4InputWorkflow,
  TOPIC4_INPUT_WORKFLOW_SYSTEM_ID,
} from './lib/topic4-input-workflow-upstream.mjs'
import {
  TOPIC3_DIFFICULTY_RUNTIME_HINT,
  checkTopic3DifficultyRuntime,
  summarizeTopic3DifficultyRuntime,
} from './lib/topic3-difficulty-runtime.mjs'

const SHOWCASE_SYSTEM_ID = 'topic2-dynbench'
const TOPIC1_SYSTEM_ID = 'topic1-indicator-mining'
const TOPIC3_DIVERSITY_SYSTEM_ID = 'topic3-diversity-rewrite'
const TOPIC3_COMPLIANCE_SYSTEM_ID = 'topic3-compliance-edit'
const TOPIC3_DIFFICULTY_SYSTEM_ID = 'topic3-dynamic-difficulty-agent'
const TOPIC3_RISK_SYSTEM_ID = 'topic3-dynamic-risk-benchmark'
const TOPIC3_RISK_RUNTIME_HINT =
  'topic3 risk live_run requires server-side Agent/Qwen; local start-platform does not start them'
const TOPIC3_COMPLIANCE_RUNTIME_HINT =
  'topic3 compliance edit requires the 6332 router with Qwen3.5-9B and Qwen3Guard-Gen-4B workers'
const TOPIC3_CULTURAL_ASSESSMENT_SYSTEM_ID = 'topic3-cultural-assessment-console'
const TOPIC3_CULTURAL_ASSESSMENT_V2_SYSTEM_ID =
  'topic3-cultural-assessment-console-v2'
const HEALTH_POLL_INTERVAL_MS = 250
const HEALTH_POLL_ATTEMPTS = 12
const TOPIC1_BACKEND_HEALTH_POLL_ATTEMPTS = 60
const TOPIC1_BACKEND_HEALTH_POLL_INTERVAL_MS = 500
const TOPIC1_FRONTEND_HEALTH_POLL_ATTEMPTS = 40
const TOPIC1_FRONTEND_HEALTH_POLL_INTERVAL_MS = 250
const PROJECT5_BACKEND_HEALTH_POLL_ATTEMPTS = 60
const PROJECT5_BACKEND_HEALTH_POLL_INTERVAL_MS = 500
const BACKEND_RELATIVE_PATH = 'web/backend'
const SCRIPTS_BIN_DIR = path.join(REPO_ROOT, 'scripts/node_modules/.bin')
const USER_LOCAL_BIN_DIR = path.join(os.homedir(), '.local/bin')
const BENCHMARK_SYSTEM_ID = 'topic3-benchmark'
const BENCHMARK_HEALTH_POLL_ATTEMPTS = 60
const BENCHMARK_HEALTH_POLL_INTERVAL_MS = 500
const WSL_DISTRIBUTION = process.env.PROJECT5_WSL_DISTRO ?? 'Ubuntu'

const ownedChildren = new Set()
let ownedBenchmark = null
let cleanupStarted = false

function shellQuote(value) {
  if (process.platform === 'win32') {
    return `"${String(value).replace(/"/g, '\\"')}"`
  }
  return `'${String(value).replace(/'/g, `'\\''`)}'`
}

function backendPythonExecutable() {
  const backendRoot = path.join(REPO_ROOT, BACKEND_RELATIVE_PATH)
  const candidates =
    process.platform === 'win32'
      ? [
          path.join(backendRoot, '.venv-win', 'Scripts', 'python.exe'),
          path.join(backendRoot, '.venv', 'Scripts', 'python.exe'),
        ]
      : [
          path.join(backendRoot, '.venv', 'bin', 'python'),
          path.join(backendRoot, '.venv-win', 'bin', 'python'),
        ]

  const venvPython = candidates.find((candidate) => fs.existsSync(candidate))
  if (venvPython) {
    return shellQuote(venvPython)
  }

  return process.platform === 'win32' ? 'python' : 'python3'
}

function normalizeBackendCommand(command) {
  if (command.startsWith('uvicorn ')) {
    return `${backendPythonExecutable()} -m ${command}`
  }
  return command
}

function resolveRepoPath(repoName) {
  if (path.basename(REPO_ROOT) === repoName) {
    return REPO_ROOT
  }
  return path.resolve(REPO_ROOT, '..', repoName)
}

function loadDotEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {}
  }
  const env = {}
  const content = fs.readFileSync(filePath, 'utf8')
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) {
      continue
    }
    const separator = line.indexOf('=')
    if (separator <= 0) {
      continue
    }
    const key = line.slice(0, separator).trim()
    let value = line.slice(separator + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    env[key] = value
  }
  return env
}

function buildSingleStartSpec(system, registry, extraEnv = {}) {
  const block = system.start?.single
  if (!block) {
    return null
  }

  const ctx = systemContext(registry, system)
  const blockEnv = {}
  if (block.env) {
    for (const [key, value] of Object.entries(block.env)) {
      blockEnv[key] = formatTemplate(String(value), ctx)
    }
  }
  const env = buildSpawnEnv(process.env, { ...extraEnv, ...blockEnv })

  return {
    cwd: path.join(resolveRepoPath(system.repo), block.cwd ?? ''),
    command: normalizeBackendCommand(formatTemplate(block.command, ctx)),
    env,
  }
}

function trackChild(child, label, { critical = false } = {}) {
  ownedChildren.add(child)
  const handleExit = createChildExitHandler({
    label,
    critical,
    isCleanupStarted: () => cleanupStarted,
    onCriticalExit: ({ label: exitedLabel, code, signal }) => {
      console.error(
        `[${exitedLabel}] critical process exited unexpectedly (code=${code}, signal=${signal})`,
      )
      cleanup(1)
    },
    onWarning: ({ label: exitedLabel, code, signal }) => {
      console.warn(
        `[${exitedLabel}] optional process exited (code=${code}, signal=${signal})`,
      )
    },
  })
  child.once('exit', (code, signal) => {
    ownedChildren.delete(child)
    handleExit(code, signal)
  })

  if (cleanupStarted) {
    terminateChild(child)
  }
  return child
}

function run(
  label,
  cwd,
  command,
  extraEnv = {},
  { critical = false, exactEnv = false } = {},
) {
  if (!fs.existsSync(cwd)) {
    console.error(`[${label}] missing directory: ${cwd}`)
    return null
  }

  console.log(`[${label}] cd ${cwd}`)
  console.log(`[${label}] ${command}`)

  const childEnv = buildSpawnEnv(process.env, extraEnv, { exactEnv })
  if (!exactEnv) {
    const pathKey = process.platform === 'win32' ? 'Path' : 'PATH'
    const extraPathEntries = [SCRIPTS_BIN_DIR, USER_LOCAL_BIN_DIR].filter(
      (candidate) => fs.existsSync(candidate),
    )
    if (extraPathEntries.length) {
      childEnv[pathKey] = `${extraPathEntries.join(path.delimiter)}${path.delimiter}${childEnv[pathKey] ?? ''}`
    }
  }

  const child = spawn(command, {
    cwd,
    env: childEnv,
    shell: true,
    stdio: 'inherit',
  })
  return trackChild(child, label, { critical })
}

async function isHttpServiceHealthy(url, expectedService) {
  try {
    const response = await fetch(url, {
      signal: AbortSignal.timeout(1500),
    })
    if (!response.ok) {
      return false
    }
    const body = await response.json()
    return body?.status === 'ok' && body?.service === expectedService
  } catch {
    return false
  }
}

async function waitForHealth(url, expectedService) {
  for (let attempt = 0; attempt < HEALTH_POLL_ATTEMPTS; attempt += 1) {
    if (await isHttpServiceHealthy(url, expectedService)) {
      return true
    }
    await new Promise((resolve) => {
      setTimeout(resolve, HEALTH_POLL_INTERVAL_MS)
    })
  }
  return false
}

async function assertPortFree(label, port, host) {
  if (await isPortListening(port, host)) {
    throw new Error(
      `[${label}] port ${port} is already in use on ${host}; stop the existing service before running start-platform`,
    )
  }
}

async function startTopic2Showcase(registry) {
  const label = 'topic2-showcase'

  try {
    if (cleanupStarted) {
      return null
    }
    const system = findSystem(registry, SHOWCASE_SYSTEM_ID)
    const healthUrl = `http://${registry.host}:${system.ui_port}/health`

    if (await isHttpServiceHealthy(healthUrl, 'topic2-showcase')) {
      console.log(`[${label}] reusing healthy service at ${healthUrl}`)
      return null
    }

    if (await isPortListening(system.ui_port, registry.host)) {
      console.warn(
        `[${label}] port ${system.ui_port} is occupied but health check failed; skipping start`,
      )
      return null
    }

    const assetRoot =
      process.env.TOPIC2_SHOWCASE_ASSET_ROOT ??
      path.join(REPO_ROOT, 'web/backend/topic2-showcase-assets')
    const spec = buildSingleStartSpec(system, registry, {
      PYTHONPATH: '.',
      TOPIC2_SHOWCASE_ASSET_ROOT: assetRoot,
    })

    if (!spec) {
      console.warn(
        `[${label}] missing start.single config in ports.registry.yaml`,
      )
      return null
    }
    if (!fs.existsSync(spec.cwd)) {
      console.warn(`[${label}] missing directory: ${spec.cwd}`)
      return null
    }

    if (!fs.existsSync(assetRoot)) {
      console.warn(`[${label}] asset root missing: ${assetRoot}`)
      console.warn(
        `[${label}] copy test fixtures: cp -R tests/fixtures/topic2_showcase/protected-assets/* topic2-showcase-assets/`,
      )
    }

    const logPath = path.join(REPO_ROOT, 'web/backend/.topic2-showcase.log')
    fs.writeFileSync(
      logPath,
      `[${new Date().toISOString()}] ${spec.command}\n`,
      { flag: 'a' },
    )
    const logFd = fs.openSync(logPath, 'a')

    console.log(`[${label}] starting on port ${system.ui_port}`)
    console.log(`[${label}] cd ${spec.cwd}`)
    console.log(`[${label}] ${spec.command}`)
    console.log(`[${label}] log ${logPath}`)

    if (cleanupStarted) {
      return null
    }

    const child = spawn(spec.command, {
      cwd: spec.cwd,
      env: spec.env,
      shell: true,
      detached: true,
      stdio: ['ignore', logFd, logFd],
      windowsHide: true,
    })
    trackChild(child, label)
    child.unref()

    const healthy = await waitForHealth(healthUrl, 'topic2-showcase')
    if (healthy) {
      console.log(
        `[${label}] ready at http://${registry.host}:${system.ui_port}`,
      )
      return child
    }

    console.warn(
      `[${label}] started but health check did not pass before timeout`,
    )
    console.warn(`[${label}] see log: ${logPath}`)
    return child
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn(`[${label}] failed to start: ${message}`)
    return null
  }
}

function normalizeTopicBackendCommand(spec) {
  if (!spec?.command) {
    return spec
  }
  const pythonExecutable = resolvePythonExecutable(spec.cwd)
  if (
    process.platform === 'win32' &&
    isLinuxPythonExecutable(pythonExecutable)
  ) {
    const wslCwd = resolveWslPath(spec.cwd)
    const pythonRelativePath = toPosixRelativePath(spec.cwd, pythonExecutable)
    const envAssignments = Object.entries(spec.env)
      .filter(([key]) => /^(APP_|POLICY_|DEBUG$)/.test(key))
      .map(([key, value]) => `${key}=${bashQuote(value)}`)
      .join(' ')
    const bashScript = [
      `cd ${bashQuote(wslCwd)}`,
      `${envAssignments} ${replaceLeadingPythonCommandForBash(spec.command, pythonRelativePath)}`,
    ].join(' && ')

    return {
      ...spec,
      command: `wsl.exe -d ${shellQuote(WSL_DISTRIBUTION)} -- bash -lc ${shellQuote(bashScript)}`,
    }
  }
  return {
    ...spec,
    command: replaceLeadingPythonCommand(spec.command, pythonExecutable),
  }
}

async function startSystemRole({
  label,
  spec,
  healthUrl,
  port,
  host,
  normalizeCommand = (value) => value,
  waitAttempts = HEALTH_POLL_ATTEMPTS,
  waitIntervalMs = HEALTH_POLL_INTERVAL_MS,
  exactEnv = false,
  requireNodeModules = false,
}) {
  if (!spec) {
    console.warn(`[${label}] missing start config`)
    return false
  }
  if (!fs.existsSync(spec.cwd)) {
    console.warn(`[${label}] missing directory: ${spec.cwd}`)
    return false
  }
  if (await isHttpOk(healthUrl)) {
    console.log(`[${label}] reusing healthy service at ${healthUrl}`)
    return true
  }
  if (await isPortListening(port, host)) {
    console.warn(
      `[${label}] port ${port} is occupied but health check failed; skipping start`,
    )
    return false
  }
  if (requireNodeModules && !hasNodeModules(spec.cwd)) {
    console.warn(
      `[${label}] frontend dependencies may be missing. Run npm install in Project_1/frontend.`,
    )
    return false
  }

  const normalizedSpec = normalizeCommand(spec)
  const child = run(
    label,
    normalizedSpec.cwd,
    normalizedSpec.command,
    normalizedSpec.env,
    {
      exactEnv,
    },
  )
  if (!child) {
    return false
  }

  if (
    await waitForHttpOk(healthUrl, {
      attempts: waitAttempts,
      intervalMs: waitIntervalMs,
    })
  ) {
    console.log(`[${label}] ready at ${healthUrl}`)
    return true
  }

  console.warn(
    `[${label}] started but health check did not pass before timeout`,
  )
  if (label.endsWith(':backend')) {
    if (label.startsWith('topic3-diversity-rewrite')) {
      console.warn(
        `[${label}] Python runtime or dependencies may be missing. Run pip install -r requirements.txt in Project_3_Cultural_Generation_Tool.`,
      )
    } else {
      console.warn(
        `[${label}] Python runtime or dependencies may be missing. Run pip install -r backend/requirements.txt in Project_1.`,
      )
    }
  }
  return false
}

async function startTopic1IndicatorMining(registry) {
  const system = findSystem(registry, TOPIC1_SYSTEM_ID)
  const specs = buildSystemStartSpecs(system, registry)
  const backendHealthUrl = `http://${registry.host}:${system.api_port}/health`
  const frontendHealthUrl = `http://${registry.host}:${system.ui_port}`

  console.log(`[${TOPIC1_SYSTEM_ID}] starting registered dual-stack service`)

  const backendReady = await startSystemRole({
    label: `${TOPIC1_SYSTEM_ID}:backend`,
    spec: specs.backend,
    healthUrl: backendHealthUrl,
    port: system.api_port,
    host: registry.host,
    normalizeCommand: normalizeTopicBackendCommand,
    waitAttempts: TOPIC1_BACKEND_HEALTH_POLL_ATTEMPTS,
    waitIntervalMs: TOPIC1_BACKEND_HEALTH_POLL_INTERVAL_MS,
    exactEnv: true,
  })

  if (!backendReady) {
    console.warn(
      `[${TOPIC1_SYSTEM_ID}] iframe will be unavailable at ${frontendHealthUrl}`,
    )
    return false
  }

  const frontendReady = await startSystemRole({
    label: `${TOPIC1_SYSTEM_ID}:frontend`,
    spec: specs.frontend,
    healthUrl: frontendHealthUrl,
    port: system.ui_port,
    host: registry.host,
    waitAttempts: TOPIC1_FRONTEND_HEALTH_POLL_ATTEMPTS,
    waitIntervalMs: TOPIC1_FRONTEND_HEALTH_POLL_INTERVAL_MS,
    exactEnv: true,
    requireNodeModules: true,
  })

  if (!frontendReady) {
    console.warn(
      `[${TOPIC1_SYSTEM_ID}] iframe will be unavailable at ${frontendHealthUrl}`,
    )
    return false
  }

  return true
}

function buildTopic3DiversityHealthChecks(system, registry) {
  return {
    data: {
      port: system.data_port,
      url: `http://${registry.host}:${system.data_port}/samples`,
    },
    backend: {
      port: system.api_port,
      url: `http://${registry.host}:${system.api_port}/api/health`,
    },
    frontend: {
      port: system.ui_port,
      url: `http://${registry.host}:${system.ui_port}`,
    },
  }
}

async function startTopic3DiversityRewrite(registry) {
  const system = findSystem(registry, TOPIC3_DIVERSITY_SYSTEM_ID)

  return startRegisteredSystem({
    systemId: TOPIC3_DIVERSITY_SYSTEM_ID,
    registry,
    roles: ['data', 'backend', 'frontend'],
    healthChecks: buildTopic3DiversityHealthChecks(system, registry),
    roleOptions: {
      backend: {
        normalizeCommand: normalizeTopicBackendCommand,
        exactEnv: true,
        waitAttempts: TOPIC1_BACKEND_HEALTH_POLL_ATTEMPTS,
        waitIntervalMs: TOPIC1_BACKEND_HEALTH_POLL_INTERVAL_MS,
      },
      frontend: {
        normalizeCommand: normalizeTopicBackendCommand,
        waitAttempts: TOPIC1_FRONTEND_HEALTH_POLL_ATTEMPTS,
        waitIntervalMs: TOPIC1_FRONTEND_HEALTH_POLL_INTERVAL_MS,
      },
    },
    deps: {
      startSystemRole,
      normalizeTopicBackendCommand,
      findSystem,
      buildSystemStartSpecs,
    },
  })
}

async function startTopic3DynamicDifficulty(registry) {
  const system = findSystem(registry, TOPIC3_DIFFICULTY_SYSTEM_ID)
  const specs = buildSystemStartSpecs(system, registry)
  const healthUrl = `http://${registry.host}:${system.ui_port}/api/health`

  console.log(
    `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] starting registered single service`,
  )

  const ready = await startSystemRole({
    label: `${TOPIC3_DIFFICULTY_SYSTEM_ID}:single`,
    spec: specs.single,
    healthUrl,
    port: system.ui_port,
    host: registry.host,
    normalizeCommand: normalizeTopicBackendCommand,
    waitAttempts: TOPIC1_BACKEND_HEALTH_POLL_ATTEMPTS,
    waitIntervalMs: TOPIC1_BACKEND_HEALTH_POLL_INTERVAL_MS,
    exactEnv: true,
  })

  if (!ready) {
    console.warn(
      `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] Agent API unavailable at ${healthUrl}`,
    )
    console.warn(
      `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] ${TOPIC3_DIFFICULTY_RUNTIME_HINT}`,
    )
    console.warn(
      `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] /benchmark topic3 live_run can still be opened, but tasks may fail until the server-side runtime is ready`,
    )
    return ready
  }

  const runtimeResults = await checkTopic3DifficultyRuntime(
    system,
    registry,
    isHttpOk,
  )
  const runtimeSummary = summarizeTopic3DifficultyRuntime(runtimeResults)
  if (!runtimeSummary.ready) {
    console.warn(
      `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] ${TOPIC3_DIFFICULTY_RUNTIME_HINT}`,
    )
    for (const item of runtimeSummary.missing) {
      console.warn(
        `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] ${item.label} unavailable at ${item.url}`,
      )
    }
    console.warn(
      `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] /benchmark topic3 live_run may fail during job start or generation until these services are started on the server`,
    )
  } else {
    console.log(
      `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] router/workers ready for topic3 live_run`,
    )
  }

  return ready
}

async function startTopic3ComplianceEdit(registry) {
  const system = findSystem(registry, TOPIC3_COMPLIANCE_SYSTEM_ID)
  const specs = buildSystemStartSpecs(system, registry)
  const healthUrl = `http://${registry.host}:${system.ui_port}${system.health_path || '/healthz'}`

  console.log(
    `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] starting registered single service`,
  )

  const ready = await startSystemRole({
    label: `${TOPIC3_COMPLIANCE_SYSTEM_ID}:single`,
    spec: specs.single,
    healthUrl,
    port: system.ui_port,
    host: registry.host,
    normalizeCommand: (spec) => spec,
    waitAttempts: TOPIC1_BACKEND_HEALTH_POLL_ATTEMPTS,
    waitIntervalMs: TOPIC1_BACKEND_HEALTH_POLL_INTERVAL_MS,
    exactEnv: false,
  })

  if (!ready) {
    console.warn(
      `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] API unavailable at ${healthUrl}`,
    )
    console.warn(
      `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] /output culture guardrail can still be opened, but unsafe samples will fall back until compliance edit is ready`,
    )
    return false
  }

  const topic3DifficultySystem = findSystem(
    registry,
    TOPIC3_DIFFICULTY_SYSTEM_ID,
  )
  const qwenUrl = `http://${registry.host}:${topic3DifficultySystem.model_router_port}/v1/models`
  if (!(await isHttpOk(qwenUrl))) {
    console.warn(
      `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] ${TOPIC3_COMPLIANCE_RUNTIME_HINT}`,
    )
    console.warn(
      `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] model router unavailable at ${qwenUrl}`,
    )
    console.warn(
      `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] healthz is OK, but edit requests may fail until the 176 tunnel / 182 router is ready`,
    )
  } else {
    console.log(
      `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] API and model router ready for compliance edit`,
    )
  }

  return true
}

async function checkTopic3RiskRuntime(registry) {
  const system = findSystem(registry, TOPIC3_RISK_SYSTEM_ID)
  const projectRoot = resolveRepoPath(system.repo)
  const generateScript = path.join(
    projectRoot,
    'qwen_agent_server',
    'live_run_adapter.py',
  )
  if (!fs.existsSync(generateScript)) {
    console.warn(
      `[${TOPIC3_RISK_SYSTEM_ID}] generate script missing (${generateScript}); clone sibling repo or set TOPIC3_RISK_BENCHMARK_PROJECT_ROOT`,
    )
  }
  const healthUrl = `http://${registry.host}:${system.ui_port}${system.health_path || '/health'}`
  const topic3DifficultySystem = findSystem(
    registry,
    TOPIC3_DIFFICULTY_SYSTEM_ID,
  )
  const qwenUrl = `http://${registry.host}:${topic3DifficultySystem.model_router_port}/v1/models`
  const agentOk = await isHttpOk(healthUrl)
  const qwenOk = await isHttpOk(qwenUrl)
  if (!agentOk || !qwenOk) {
    console.warn(
      `[${TOPIC3_RISK_SYSTEM_ID}] Agent/Qwen unavailable (agent=${healthUrl} qwen=${qwenUrl})`,
    )
    console.warn(`[${TOPIC3_RISK_SYSTEM_ID}] ${TOPIC3_RISK_RUNTIME_HINT}`)
    console.warn(
      `[${TOPIC3_RISK_SYSTEM_ID}] /benchmark topic3-risk-benchmark-generation live_run can still be opened, but tasks will fail until the server-side runtime is ready`,
    )
    return false
  }
  console.log(`[${TOPIC3_RISK_SYSTEM_ID}] Agent and Qwen ready for risk live_run`)
  return true
}

async function startTopic3CulturalAssessment(registry) {
  const system = findSystem(registry, TOPIC3_CULTURAL_ASSESSMENT_SYSTEM_ID)
  const v2System = findSystem(registry, TOPIC3_CULTURAL_ASSESSMENT_V2_SYSTEM_ID)
  const v1Ready = await startTopic3CulturalAssessmentSingle(
    registry,
    system,
    TOPIC3_CULTURAL_ASSESSMENT_SYSTEM_ID,
  )
  const v2Ready = await startTopic3CulturalAssessmentSingle(
    registry,
    v2System,
    TOPIC3_CULTURAL_ASSESSMENT_V2_SYSTEM_ID,
  )

  return v1Ready || v2Ready
}

async function startTopic3CulturalAssessmentSingle(registry, system, systemId) {
  const specs = buildSystemStartSpecs(system, registry)
  const healthUrl = `http://${registry.host}:${system.ui_port}/api/health`

  console.log(
    `[${systemId}] starting registered single service`,
  )

  const ready = await startSystemRole({
    label: `${systemId}:single`,
    spec: specs.single,
    healthUrl,
    port: system.ui_port,
    host: registry.host,
    normalizeCommand: normalizeTopicBackendCommand,
    waitAttempts: TOPIC1_BACKEND_HEALTH_POLL_ATTEMPTS,
    waitIntervalMs: TOPIC1_BACKEND_HEALTH_POLL_INTERVAL_MS,
    exactEnv: false,
  })

  if (!ready) {
    console.warn(
      `[${systemId}] console unavailable at ${healthUrl}`,
    )
  }

  return ready
}

function runWsl(args, options = {}) {
  const result = spawnSync('wsl.exe', ['-d', WSL_DISTRIBUTION, '--', ...args], {
    encoding: 'utf8',
    windowsHide: true,
    ...options,
  })
  if (result.error) {
    throw result.error
  }
  return result
}

function runBash(script, options = {}) {
  const result = spawnSync('bash', ['-lc', script], {
    encoding: 'utf8',
    stdio: 'ignore',
    ...options,
  })
  if (result.error) {
    throw result.error
  }
  return result
}

function resolveWslPath(windowsPath) {
  const result = runWsl(['wslpath', '-a', windowsPath])
  if (result.status !== 0) {
    throw new Error(
      `WSL path conversion failed: ${result.stderr?.trim() || 'unknown error'}`,
    )
  }
  return result.stdout.trim()
}

async function waitForBenchmark(baseUrl) {
  for (
    let attempt = 0;
    attempt < BENCHMARK_HEALTH_POLL_ATTEMPTS;
    attempt += 1
  ) {
    if (await checkBenchmarkHealth(baseUrl)) {
      return true
    }
    await new Promise((resolve) => {
      setTimeout(resolve, BENCHMARK_HEALTH_POLL_INTERVAL_MS)
    })
  }
  return false
}

async function ensureBenchmark(registry, mode) {
  const baseUrl = benchmarkUrlForMode(mode)
  console.log(`Benchmark mode: ${mode}`)
  console.log(`Benchmark:      ${baseUrl}`)

  if (await checkBenchmarkHealth(baseUrl)) {
    console.log(`[benchmark] reusing healthy service at ${baseUrl}`)
    return baseUrl
  }

  if (mode === 'remote') {
    throw new Error(`Remote Benchmark is unavailable: ${baseUrl}`)
  }

  const system = findSystem(registry, BENCHMARK_SYSTEM_ID)
  const repoPath = resolveRepoPath(system.repo)
  const logPath = path.join(repoPath, 'server.log')

  if (!fs.existsSync(repoPath)) {
    throw new Error(`Benchmark repository is missing: ${repoPath}`)
  }
  if (await isPortListening(system.ui_port, registry.host)) {
    throw new Error(
      `Port ${system.ui_port} is occupied by a non-Benchmark service`,
    )
  }
  const benchmarkRepoPath =
    process.platform === 'win32' ? resolveWslPath(repoPath) : repoPath
  const startScript = buildBenchmarkStartScript(benchmarkRepoPath)
  if (process.platform === 'win32') {
    console.log(`[benchmark] WSL distribution: ${WSL_DISTRIBUTION}`)
  } else {
    console.log('[benchmark] native shell: bash')
  }
  console.log(`[benchmark] repository: ${benchmarkRepoPath}`)
  console.log('[benchmark] EVAL_PYTHON=.venv/bin/python ./run.sh')
  console.log(`[benchmark] log: ${logPath}`)

  const result =
    process.platform === 'win32'
      ? runWsl(['bash', '-lc', startScript], { stdio: 'ignore' })
      : runBash(startScript)
  if (result.status !== 0) {
    throw new Error(
      `Benchmark failed to start (${result.stderr?.trim() || `exit ${result.status}`}). Log: ${logPath}`,
    )
  }

  ownedBenchmark = {
    logPath,
    repoPath: benchmarkRepoPath,
    viaWsl: process.platform === 'win32',
  }
  if (!(await waitForBenchmark(baseUrl))) {
    throw new Error(
      `Benchmark health check timed out at ${baseUrl}. Log: ${logPath}`,
    )
  }

  console.log(`[benchmark] ready at ${baseUrl}`)
  return baseUrl
}

function terminateChild(child) {
  if (!child?.pid || child.exitCode !== null) {
    return
  }
  if (process.platform === 'win32') {
    spawnSync('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], {
      stdio: 'ignore',
      windowsHide: true,
    })
    return
  }
  child.kill('SIGTERM')
}

function stopOwnedBenchmark() {
  if (!ownedBenchmark) {
    return
  }
  const stopScript = buildBenchmarkStopScript(ownedBenchmark.repoPath)
  const result = ownedBenchmark.viaWsl
    ? runWsl(['bash', '-lc', stopScript])
    : runBash(stopScript)
  if (result.status === 0) {
    console.log('[benchmark] stopped service started by this run')
  } else {
    console.warn(
      `[benchmark] precise shutdown failed; inspect ${ownedBenchmark.logPath}`,
    )
  }
  ownedBenchmark = null
}

function cleanup(exitCode = 0) {
  if (cleanupStarted) {
    return
  }
  cleanupStarted = true

  for (const child of ownedChildren) {
    terminateChild(child)
  }
  ownedChildren.clear()
  stopOwnedBenchmark()
  process.exitCode = exitCode
}

function installCleanupHandlers() {
  process.once('SIGINT', () => cleanup(130))
  process.once('SIGTERM', () => cleanup(143))
  process.once('uncaughtException', (error) => {
    console.error(error instanceof Error ? error.message : error)
    cleanup(1)
  })
  process.once('unhandledRejection', (error) => {
    console.error(error instanceof Error ? error.message : error)
    cleanup(1)
  })
  process.once('beforeExit', (code) => {
    if (
      shouldCleanupBeforeExit({
        cleanupStarted,
        ownedChildCount: ownedChildren.size,
        ownsBenchmark: ownedBenchmark !== null,
      })
    ) {
      console.warn('[platform] event loop ended before explicit cleanup')
      cleanup(code || 1)
    }
  })
}

async function main() {
  const platformArgs = parsePlatformArgs(process.argv.slice(2))
  const registry = loadRegistry()
  const backendPort = registry.platform.backend_port
  const frontendPort = registry.platform.frontend_port

  const backendCwd = path.join(REPO_ROOT, BACKEND_RELATIVE_PATH)
  const frontendCwd = path.join(REPO_ROOT, 'web/frontend')

  console.log('Starting Project 5 platform from ports.registry.yaml')
  console.log(`Frontend: http://${registry.host}:${frontendPort}`)
  console.log(`Backend:  http://${registry.host}:${backendPort}`)
  const proxySanitize = describeProxySanitize(process.env)
  console.log(
    `[proxy] sanitized child env for localhost (stripped=${proxySanitize.stripped ? 'yes' : 'no'}, no_proxy=set)`,
  )
  console.log('')

  installCleanupHandlers()
  const benchmarkBaseUrl = await ensureBenchmark(
    registry,
    platformArgs.benchmarkMode,
  )
  const benchmarkEnv = benchmarkEnvironment(benchmarkBaseUrl)
  const topic3DifficultySystem = findSystem(
    registry,
    TOPIC3_DIFFICULTY_SYSTEM_ID,
  )
  const topic3DifficultyEnv = {
    TOPIC3_DIFFICULTY_BASE_URL: `http://${registry.host}:${topic3DifficultySystem.ui_port}`,
    TOPIC3_DIFFICULTY_VLLM_API_BASE: `http://${registry.host}:${topic3DifficultySystem.model_router_port}/v1`,
  }
  const topic3RiskSystem = findSystem(registry, TOPIC3_RISK_SYSTEM_ID)
  const topic3RiskEnv = {
    TOPIC3_RISK_AGENT_URL: `http://${registry.host}:${topic3RiskSystem.ui_port}/chat`,
    TOPIC3_RISK_QWEN_API_BASE: `http://${registry.host}:${topic3DifficultySystem.model_router_port}/v1`,
    TOPIC3_RISK_BENCHMARK_PROJECT_ROOT: resolveRepoPath(topic3RiskSystem.repo),
    ...(process.env.TOPIC3_RISK_BENCHMARK_PYTHON
      ? {
          TOPIC3_RISK_BENCHMARK_PYTHON:
            process.env.TOPIC3_RISK_BENCHMARK_PYTHON,
        }
      : {}),
  }
  const topic3ComplianceSystem = findSystem(
    registry,
    TOPIC3_COMPLIANCE_SYSTEM_ID,
  )
  const topic3ComplianceEnv = {
    COMPLIANCE_EDIT_BASE_URL: `http://${registry.host}:${topic3ComplianceSystem.ui_port}`,
    COMPLIANCE_EDIT_TIMEOUT_SECONDS: '300',
  }
  const topic3DiversitySystem = findSystem(
    registry,
    TOPIC3_DIVERSITY_SYSTEM_ID,
  )
  const topic3DiversityEnv = {
    CULTURAL_GEN_BASE_URL: `http://${registry.host}:${topic3DiversitySystem.api_port}`,
    CULTURAL_GEN_DATA_BASE_URL: `http://${registry.host}:${topic3DiversitySystem.data_port}`,
  }
  const topic2FilterGuardSystem = findSystem(
    registry,
    TOPIC2_FILTERGUARD_SYSTEM_ID,
  )
  const topic2FilterGuardEnv = buildTopic2FilterGuardEnv(
    registry,
    topic2FilterGuardSystem,
  )
  const topic4InputWorkflowSystem = findSystem(
    registry,
    TOPIC4_INPUT_WORKFLOW_SYSTEM_ID,
  )
  const topic4InputWorkflowEnv = buildTopic4InputWorkflowEnv(
    registry,
    topic4InputWorkflowSystem,
  )
  const topic3CulturalAssessmentSystem = findSystem(
    registry,
    TOPIC3_CULTURAL_ASSESSMENT_SYSTEM_ID,
  )
  const topic3CulturalAssessmentV2System = findSystem(
    registry,
    TOPIC3_CULTURAL_ASSESSMENT_V2_SYSTEM_ID,
  )
  const topic3CulturalAssessmentEnv = {
    CULTURAL_ASSESSMENT_ROOT: resolveRepoPath(topic3CulturalAssessmentSystem.repo),
    CULTURAL_ASSESSMENT_CONSOLE_BASE_URL: `http://${registry.host}:${topic3CulturalAssessmentSystem.ui_port}`,
    CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL: `http://${registry.host}:${topic3CulturalAssessmentV2System.ui_port}`,
  }
  const topic3CulturalAssessmentSecretEnv = loadDotEnvFile(
    path.join(resolveRepoPath(topic3CulturalAssessmentSystem.repo), '.env'),
  )
  Object.assign(process.env, topic3CulturalAssessmentSecretEnv)

  if (platformArgs.startTopic2FilterGuard) {
    await startTopic2FilterGuard({
      system: topic2FilterGuardSystem,
      registry,
      wslDistro: WSL_DISTRIBUTION,
      resolveWslPath,
      trackChild,
    })
  } else {
    console.log('[topic2-filterguard] skipped by --no-topic2-filterguard')
  }

  if (platformArgs.startTopic4InputWorkflow) {
    await startTopic4InputWorkflow({
      system: topic4InputWorkflowSystem,
      registry,
      trackChild,
    })
  } else {
    console.log('[topic4-input-workflow] skipped by --no-topic4-input-workflow')
  }

  const corpusToolEnv = await startTopic1CorpusTools({
    registry, enabled: platformArgs.startTopic1CorpusTools, trackChild,
  })
  const backendEnv = {
    ...corpusToolEnv,
    ...benchmarkEnv.backend,
    ...topic3DiversityEnv,
    ...topic3DifficultyEnv,
    ...topic3RiskEnv,
    ...topic3ComplianceEnv,
    ...topic2FilterGuardEnv,
    ...topic4InputWorkflowEnv,
    ...topic3CulturalAssessmentEnv,
  }
  const backend = run(
    'backend',
    backendCwd,
    normalizeBackendCommand(
      `uvicorn app.main:app --reload --host 127.0.0.1 --port ${backendPort}`,
    ),
    backendEnv,
    { critical: true },
  )

  await assertPortFree('frontend', frontendPort, registry.host)
  const frontend = run(
    'frontend',
    frontendCwd,
    `pnpm dev --host 127.0.0.1 --port ${frontendPort} --strictPort`,
    benchmarkEnv.frontend,
    { critical: true },
  )
  if (!backend || !frontend) {
    throw new Error('Project 5 frontend or backend failed to start')
  }

  const backendHealthUrl = `http://${registry.host}:${backendPort}/health`
  const backendReady = await waitForHttpOk(backendHealthUrl, {
    attempts: PROJECT5_BACKEND_HEALTH_POLL_ATTEMPTS,
    intervalMs: PROJECT5_BACKEND_HEALTH_POLL_INTERVAL_MS,
  })
  if (!backendReady) {
    throw new Error(`Project 5 backend health check timed out at ${backendHealthUrl}`)
  }
  console.log(`[backend] ready at ${backendHealthUrl}`)

  if (platformArgs.startTopic2Upstream) {
    await startTopic2AutoBenchUpstream({
      system: findSystem(registry, SHOWCASE_SYSTEM_ID),
      registry,
      wslDistro: WSL_DISTRIBUTION,
      resolveWslPath,
      trackChild,
    })
  } else {
    console.log('[topic2-autobench-web] skipped by --no-topic2-upstream')
  }

  await startTopic2Showcase(registry)
  await startTopic1IndicatorMining(registry)

  if (platformArgs.startTopic3Diversity) {
    await startTopic3DiversityRewrite(registry)
  } else {
    console.log(
      `[${TOPIC3_DIVERSITY_SYSTEM_ID}] skipped by --no-topic3-diversity`,
    )
  }

  if (platformArgs.startTopic3Difficulty) {
    await startTopic3DynamicDifficulty(registry)
  } else {
    console.log(
      `[${TOPIC3_DIFFICULTY_SYSTEM_ID}] skipped by --no-topic3-difficulty`,
    )
  }

  if (platformArgs.startTopic3Compliance) {
    await startTopic3ComplianceEdit(registry)
  } else {
    console.log(
      `[${TOPIC3_COMPLIANCE_SYSTEM_ID}] skipped by --no-topic3-compliance`,
    )
  }

  if (platformArgs.startTopic3CulturalAssessment) {
    await startTopic3CulturalAssessment(registry)
  } else {
    console.log(
      `[${TOPIC3_CULTURAL_ASSESSMENT_SYSTEM_ID}] skipped by --no-topic3-cultural-assessment`,
    )
  }

  await checkTopic3RiskRuntime(registry)

  if (platformArgs.startGovernanceWorker) {
    const governanceWorker = run(
      'governance-worker',
      backendCwd,
      `${backendPythonExecutable()} -m app.workers.governance_task_worker`,
      {
        ...backendEnv,
        PYTHONPATH: '.',
        PYTHONUNBUFFERED: '1',
      },
      { critical: true },
    )
    if (!governanceWorker) {
      throw new Error('Project 5 governance worker failed to start')
    }
  } else {
    console.log('[governance-worker] skipped by --no-governance-worker')
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  cleanup(1)
})
