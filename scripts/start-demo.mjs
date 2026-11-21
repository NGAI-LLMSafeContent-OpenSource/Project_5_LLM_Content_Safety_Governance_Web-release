#!/usr/bin/env node
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import {
  findSystem,
  loadRegistry,
  resolveSiblingRepo,
  systemContext,
} from './lib/registry.mjs'
import {
  buildSystemStartSpec,
  buildSystemStartSpecs,
} from './lib/system-start-spec.mjs'

const args = process.argv.slice(2)
const systemId = args.find((arg) => !arg.startsWith('--'))
const portOverrideIndex = args.indexOf('--port')
const portOverride = portOverrideIndex >= 0 ? Number(args[portOverrideIndex + 1]) : undefined

if (!systemId) {
  console.error('Usage: node scripts/start-demo.mjs <system-id> [--port <ui-port>]')
  process.exit(1)
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`
}

function buildCommand(system, registry, role) {
  return buildSystemStartSpec(system, registry, role, {
    uiPortOverride: portOverride,
  })
}

function applyUiPortOverride(ctx, system, portOverride) {
  if (portOverride == null) {
    return ctx
  }
  ctx.ui_port = portOverride
  ctx.port = portOverride
  if (system.api_port != null) {
    ctx.api_port = portOverride + 1
  }
  if (system.data_port != null) {
    ctx.data_port = portOverride + 2
  }
  return ctx
}

function printManualInstructions(system, registry) {
  const repoPath = system.repo ? resolveSiblingRepo(system.repo) : null
  const ctx = applyUiPortOverride(systemContext(registry, system), system, portOverride)

  console.log(`# Manual start for ${system.id}`)
  console.log(`# Repo: ${repoPath ?? 'not registered'}`)
  console.log(`# iframe URL: http://${registry.host}:${ctx.ui_port}`)
  console.log('')

  if (!repoPath) {
    console.log('! Source repo is not registered yet; keep this system pending.')
    return
  }

  if (!fs.existsSync(repoPath)) {
    console.log(`! Clone sibling repo first: ${system.repo}`)
    console.log('')
  }

  if (system.start?.data) {
    const spec = buildCommand(system, registry, 'data')
    console.log('## Data')
    console.log(`cd ${shellQuote(spec.cwd)}`)
    console.log(spec.command)
    console.log('')
  }

  if (system.start?.backend) {
    const spec = buildCommand(system, registry, 'backend')
    console.log('## Backend')
    for (const [key, value] of Object.entries(spec.env)) {
      if (key.startsWith('APP_') || key.startsWith('POLICY_') || key === 'PORT') {
        console.log(`export ${key}=${shellQuote(value)}`)
      }
    }
    console.log(`cd ${shellQuote(spec.cwd)}`)
    console.log(spec.command)
    console.log('')
  }

  if (system.start?.frontend) {
    const spec = buildCommand(system, registry, 'frontend')
    console.log('## Frontend')
    for (const [key, value] of Object.entries(spec.env)) {
      if (key.startsWith('VITE_') || key === 'PORT') {
        console.log(`export ${key}=${shellQuote(value)}`)
      }
    }
    console.log(`cd ${shellQuote(spec.cwd)}`)
    console.log(spec.command)
    console.log('')
  }

  if (system.start?.single) {
    const spec = buildCommand(system, registry, 'single')
    console.log('## Service')
    for (const [key, value] of Object.entries(spec.env)) {
      console.log(`export ${key}=${shellQuote(value)}`)
    }
    console.log(`cd ${shellQuote(spec.cwd)}`)
    console.log(spec.command)
    console.log('')
  }

  if (!system.start) {
    console.log(`PORT=${ctx.ui_port} # pass to the topic repo start command when supported`)
    if (system.api_port != null) {
      console.log(`API_PORT=${ctx.api_port}`)
    }
    if (system.data_port != null) {
      console.log(`DATA_PORT=${ctx.data_port}`)
    }
  }
}

function runProcess(label, spec) {
  if (!fs.existsSync(spec.cwd)) {
    console.error(`[${label}] missing directory: ${spec.cwd}`)
    return null
  }

  console.log(`[${label}] cd ${spec.cwd}`)
  console.log(`[${label}] ${spec.command}`)

  const child = spawn(spec.command, {
    cwd: spec.cwd,
    env: spec.env,
    shell: true,
    stdio: 'inherit',
  })

  child.on('exit', (code) => {
    console.log(`[${label}] exited with code ${code ?? 0}`)
  })

  return child
}

function main() {
  const registry = loadRegistry()
  const system = findSystem(registry, systemId)

  if (!system.start) {
    printManualInstructions(system, registry)
    return
  }

  if (!system.repo) {
    printManualInstructions(system, registry)
    process.exit(1)
  }

  const repoPath = resolveSiblingRepo(system.repo)
  if (!fs.existsSync(repoPath)) {
    printManualInstructions(system, registry)
    process.exit(1)
  }

  const children = []
  const {
    data: dataSpec,
    backend: backendSpec,
    frontend: frontendSpec,
    single: singleSpec,
  } = buildSystemStartSpecs(system, registry, { uiPortOverride: portOverride })

  if (dataSpec) {
    children.push(runProcess('data', dataSpec))
  }
  if (backendSpec) {
    children.push(runProcess('backend', backendSpec))
  }
  if (frontendSpec) {
    children.push(runProcess('frontend', frontendSpec))
  }
  if (singleSpec) {
    children.push(runProcess('service', singleSpec))
  }

  if (children.every((child) => child == null)) {
    printManualInstructions(system, registry)
    process.exit(1)
  }

  const ctx = applyUiPortOverride(systemContext(registry, system), system, portOverride)
  console.log('')
  console.log(`iframe URL: http://${registry.host}:${ctx.ui_port}`)
}

main()
