import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { findSystem, resolveSiblingRepo, isPortListening } from './registry.mjs'
import { buildSpawnEnv } from './spawn-env.mjs'

export const CORPUS_TOOLS = ['refinement', 'detox', 'detection']

export async function corpusHealth(url, tool, fetchImpl = fetch) {
  try {
    const response = await fetchImpl(`${url}${tool === 'detection' ? '/api/health' : '/health'}`, {
      signal: AbortSignal.timeout(2000), redirect: 'error',
    })
    if (!response.ok) return false
    const body = await response.json()
    if (tool === 'refinement') return body.status === 'healthy' && body.scheduler === 'running'
    if (tool === 'detox') return body.status === 'ok' && body.service === 'data-detox' && body.backend === 'real'
    return body.status === 'ok' && body.service === 'scdc-pdd'
  } catch { return false }
}

// Only pre-installed POSIX environments; never install packages or download weights.
export async function startTopic1CorpusTools({ registry, enabled, trackChild, env = process.env }) {
  const backendEnv = {}
  for (const tool of CORPUS_TOOLS) {
    const id = `topic1-corpus-${tool}`
    try {
    const system = findSystem(registry, id)
    const key = `TOPIC1_${tool.toUpperCase()}_BASE_URL`
    const url = (env[key] || `http://${registry.host}:${system.api_port}`).replace(/\/$/, '')
    backendEnv[key] = url
    if (!enabled) { console.log(`[${id}] skipped by --no-topic1-corpus-tools`); continue }
    if (await corpusHealth(url, tool)) { console.log(`[${id}] ready (model readiness checked separately)`); continue }
    if (env[key]) { console.warn(`[${id}] health failed for configured service; not starting another instance`); continue }
    if (process.platform === 'win32') { console.warn(`[${id}] skipped: run unified startup inside WSL Ubuntu`); continue }
    if (await isPortListening(system.api_port, registry.host)) { console.warn(`[${id}] port occupied, health failed`); continue }
    const root = resolveSiblingRepo(system.repo)
    if (!fs.existsSync(root)) { console.warn(`[${id}] repo missing: ${system.repo}`); continue }
    const python = path.join(root, '.venv', 'bin', 'python')
    if (!fs.existsSync(python)) { console.warn(`[${id}] skipped: missing POSIX .venv; install upstream requirements first`); continue }
    const cwd = path.join(root, system.runtime.cwd)
    const args = system.runtime.args.map((value) => String(value).replaceAll('{port}', String(system.api_port)))
    const runtimeEnv = Object.fromEntries(Object.entries(system.runtime.env || {}).map(([k, v]) => [k, String(v).replaceAll('{port}', String(system.api_port))]))
    const logPath = path.join(root, `.project5-${tool}.log`)
    const fd = fs.openSync(logPath, 'a')
    try {
      const child = spawn(python, args, { cwd, env: buildSpawnEnv({ ...env, ...runtimeEnv }), stdio: ['ignore', fd, fd], detached: true, windowsHide: true })
      child.on('error', () => console.warn(`[${id}] startup failed; see ${logPath}`))
      trackChild(child, id, { critical: false })
      child.unref()
    } finally { fs.closeSync(fd) }
    let ready = false
    for (let attempt = 0; attempt < 20; attempt++) {
      if (await corpusHealth(url, tool)) { ready = true; break }
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
    console.log(`[${id}] ${ready ? 'ready' : 'health failed; inspect log'}: ${logPath}`)
    } catch {
      console.warn(`[${id}] optional startup failed; inspect service configuration and permissions`)
    }
  }
  return backendEnv
}
