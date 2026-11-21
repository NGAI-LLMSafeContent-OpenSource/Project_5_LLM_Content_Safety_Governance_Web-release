#!/usr/bin/env node
import {
  findSystem,
  getTunnelPort,
  isPortListening,
  loadRegistry,
} from './lib/registry.mjs'

const [command = 'list', systemId] = process.argv.slice(2)

function printHeader() {
  console.log('Cross-topic demo port registry (docs/integration/ports.registry.yaml)')
  console.log('')
}

async function listPorts() {
  const registry = loadRegistry()
  printHeader()
  console.log(
    `Platform  FE ${registry.platform.frontend_port}  BE ${registry.platform.backend_port}`,
  )
  console.log('')
  console.log('ID                             UI     API    Tunnel  Status')
  console.log('------------------------------ ------ ------ ------- --------')
  for (const system of registry.systems) {
    const api = system.api_port != null ? String(system.api_port).padEnd(6) : '-     '
    const tunnel = String(getTunnelPort(registry, system.ui_port)).padEnd(7)
    console.log(
      `${system.id.padEnd(30)} ${String(system.ui_port).padEnd(6)} ${api} ${tunnel} ${system.integration_status}`,
    )
  }
}

async function checkPorts() {
  const registry = loadRegistry()
  printHeader()
  const targets = [
    { label: 'project5-fe', port: registry.platform.frontend_port },
    { label: 'project5-be', port: registry.platform.backend_port },
    ...registry.systems
      .filter((system) => system.integration_status === 'ready')
      .flatMap((system) => {
        const rows = [{ label: `${system.id}-ui`, port: system.ui_port }]
        if (system.api_port != null) {
          rows.push({ label: `${system.id}-api`, port: system.api_port })
        }
        return rows
      }),
  ]

  for (const target of targets) {
    const listening = await isPortListening(target.port)
    const status = listening ? 'LISTEN' : 'FREE'
    console.log(`${status.padEnd(6)} ${String(target.port).padEnd(6)} ${target.label}`)
  }
}

function envPorts() {
  const registry = loadRegistry()
  if (!systemId) {
    throw new Error('Usage: node scripts/ports.mjs env <system-id>')
  }
  const system = findSystem(registry, systemId)
  const ctx = {
    host: registry.host,
    ui_port: system.ui_port,
    api_port: system.api_port,
    port: system.ui_port,
  }
  console.log(`INTEGRATION_UI_PORT=${system.ui_port}`)
  if (system.api_port != null) {
    console.log(`INTEGRATION_API_PORT=${system.api_port}`)
  }
  console.log(`INTEGRATION_UI_URL=http://${registry.host}:${system.ui_port}`)
  if (system.api_port != null) {
    console.log(`INTEGRATION_API_URL=http://${registry.host}:${system.api_port}`)
  }
  console.log(`INTEGRATION_TUNNEL_PORT=${getTunnelPort(registry, system.ui_port)}`)
  if (system.start?.frontend?.env) {
    for (const [key, value] of Object.entries(system.start.frontend.env)) {
      const resolved = String(value).replace(/\{(\w+)\}/g, (_, k) => String(ctx[k] ?? ''))
      console.log(`${key}=${resolved}`)
    }
  }
  if (system.start?.backend?.env) {
    for (const [key, value] of Object.entries(system.start.backend.env)) {
      const resolved = String(value).replace(/\{(\w+)\}/g, (_, k) => String(ctx[k] ?? ''))
      console.log(`${key}=${resolved}`)
    }
  }
}

async function main() {
  switch (command) {
    case 'list':
      await listPorts()
      break
    case 'check':
      await checkPorts()
      break
    case 'env':
      envPorts()
      break
    default:
      console.error(`Unknown command: ${command}`)
      console.error('Usage: node scripts/ports.mjs [list|check|env <system-id>]')
      process.exit(1)
  }
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})
