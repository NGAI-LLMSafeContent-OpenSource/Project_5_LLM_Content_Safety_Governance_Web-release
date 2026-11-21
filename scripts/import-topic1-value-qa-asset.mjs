#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { loadRegistry, REPO_ROOT, resolveSiblingRepo } from './lib/registry.mjs'

const OFFICIAL_ASSET_ID = 'topic1_value_qa_marked_merged_round3'
const OFFICIAL_ASSET_NAME = 'Topic1 value_qa marked merged with round3 QC'
const DEMO_ASSET_ID = 'topic1_value_qa_risk_cause_demo0606'
const DEMO_ASSET_NAME = 'Topic1 value_qa from Risk Cause DEMO-0606'

function parseArgs(argv) {
  const options = {
    mode: '',
    assetId: '',
    name: '',
    backendUrl: '',
    pathStyle: process.platform === 'win32' ? 'windows' : 'wsl',
    dryRun: false,
    noTrace: false,
    help: false,
  }
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    const next = () => {
      index += 1
      if (index >= argv.length) {
        throw new Error(`${arg} requires a value`)
      }
      return argv[index]
    }
    switch (arg) {
      case '--mode':
        options.mode = next()
        break
      case '--asset-id':
        options.assetId = next()
        break
      case '--name':
        options.name = next()
        break
      case '--backend-url':
        options.backendUrl = next().replace(/\/$/, '')
        break
      case '--path-style':
        options.pathStyle = next()
        break
      case '--dry-run':
        options.dryRun = true
        break
      case '--no-trace':
        options.noTrace = true
        break
      case '--help':
      case '-h':
        options.help = true
        break
      default:
        throw new Error(`Unknown option: ${arg}`)
    }
  }
  if (!['windows', 'wsl', 'native'].includes(options.pathStyle)) {
    throw new Error('--path-style must be windows, wsl, or native')
  }
  if (options.mode && !['official', 'demo'].includes(options.mode)) {
    throw new Error('--mode must be official or demo')
  }
  return options
}

function printHelp() {
  console.log(`Import Topic1 value_qa prerun asset into Project 5 BenchmarkAsset registry.

Recommended:
  node scripts/import-topic1-value-qa-asset.mjs --mode official
  node scripts/import-topic1-value-qa-asset.mjs --mode demo

Sources:
  official -> web/backend/data/input_corpora/value_qa/verified.marked_merged.jsonl  (~222)
  demo     -> web/backend/data/input_corpora/value_qa_demo0606/verified.marked_20260601_031030.jsonl (~87)

Do NOT pass --asset-id=${DEMO_ASSET_ID} while importing the official pack.
That mismatch is what made servers show DEMO as 222 rows.

Options:
  --mode <official|demo>  Explicit pack selection (recommended)
  --asset-id <id>         Override asset id (defaults follow --mode)
  --name <name>           Display name
  --backend-url <url>     Override backend URL
  --path-style <style>    windows | wsl | native
  --no-trace              Omit Risk Cause trace files
  --dry-run               Print payload without importing
  -h, --help              Show this help
`)
}

function toWindowsPath(value) {
  const normalized = value.replaceAll('\\', '/')
  const match = normalized.match(/^\/mnt\/([a-zA-Z])\/(.*)$/)
  if (match) {
    return `${match[1].toUpperCase()}:\\${match[2].replaceAll('/', '\\')}`
  }
  return value
}

function toWslPath(value) {
  const normalized = value.replaceAll('\\', '/')
  const match = normalized.match(/^([a-zA-Z]):\/(.*)$/)
  if (match) {
    return `/mnt/${match[1].toLowerCase()}/${match[2]}`
  }
  return normalized
}

function payloadPath(nativePath, pathStyle) {
  const absolute = path.resolve(nativePath)
  if (pathStyle === 'windows') return toWindowsPath(absolute)
  if (pathStyle === 'wsl') return toWslPath(absolute)
  return absolute
}

function attachOptionalTraces(paths, options, traceRepo) {
  if (options.noTrace || !traceRepo) return
  const newPredictions = path.join(traceRepo, 'Data_predictions.jsonl')
  if (fs.existsSync(newPredictions)) {
    paths.trace_predictions_path = newPredictions
    return
  }
  const predictions = path.join(
    traceRepo,
    'DEMO-0606/ui_runs/ui_predictions_20260605_192016.jsonl',
  )
  const lowIssues = path.join(
    traceRepo,
    'DEMO-0606/ui_runs/ui_low_issues_20260605_192016.jsonl',
  )
  if (fs.existsSync(predictions)) paths.trace_predictions_path = predictions
  if (fs.existsSync(lowIssues)) paths.trace_low_issues_path = lowIssues
}

function resolveOfficialBundle() {
  const inRepoRoot = path.join(REPO_ROOT, 'web/backend/data/input_corpora/value_qa')
  const inRepoSamples = path.join(inRepoRoot, 'verified.marked_merged.jsonl')
  const topic1Repo = resolveSiblingRepo('Project_1_Sample_evaluation_Generation')
  const primarySamples = path.join(
    topic1Repo,
    'data/samples/value_qa/verified.marked_merged.jsonl',
  )
  const paths = {}
  let sourceMode = 'missing'
  if (fs.existsSync(inRepoSamples)) {
    sourceMode = 'official_in_repo'
    paths.samples_path = inRepoSamples
    const optional = {
      marks_path: path.join(inRepoRoot, '_marks_verified.marked_merged.jsonl'),
      qc_index_path: path.join(inRepoRoot, 'qc/round3_gpt55_index.json'),
      qc_samples_path: path.join(inRepoRoot, 'qc/round3_gpt55_samples.jsonl'),
      qc_scores_path: path.join(inRepoRoot, 'qc/round3_gpt55_scores.jsonl'),
      qc_summary_path: path.join(inRepoRoot, 'qc/round3_gpt55_summary.md'),
    }
    for (const [key, value] of Object.entries(optional)) {
      if (fs.existsSync(value)) paths[key] = value
    }
  } else if (fs.existsSync(primarySamples)) {
    sourceMode = 'official_sibling'
    paths.samples_path = primarySamples
    const optional = {
      marks_path: path.join(
        topic1Repo,
        'data/samples/value_qa/_marks_verified.marked_merged.jsonl',
      ),
      qc_index_path: path.join(topic1Repo, 'data/qc/round3_gpt55_index.json'),
      qc_samples_path: path.join(topic1Repo, 'data/qc/round3_gpt55_samples.jsonl'),
      qc_scores_path: path.join(topic1Repo, 'data/qc/round3_gpt55_scores.jsonl'),
      qc_summary_path: path.join(topic1Repo, 'data/qc/round3_gpt55_summary.md'),
    }
    for (const [key, value] of Object.entries(optional)) {
      if (fs.existsSync(value)) paths[key] = value
    }
  }
  return {
    sourceMode,
    packRoot: inRepoRoot,
    paths,
    defaultAssetId: OFFICIAL_ASSET_ID,
    defaultAssetName: OFFICIAL_ASSET_NAME,
  }
}

function resolveDemoBundle() {
  const inRepoRoot = path.join(REPO_ROOT, 'web/backend/data/input_corpora/value_qa_demo0606')
  const inRepoSamples = path.join(inRepoRoot, 'verified.marked_20260601_031030.jsonl')
  const traceRepo = resolveSiblingRepo('Project_1_Risk_Cause_Determination')
  const siblingSamples = path.join(
    traceRepo,
    'DEMO-0606/verified.marked_20260601_031030.jsonl',
  )
  const paths = {}
  let sourceMode = 'missing'
  if (fs.existsSync(inRepoSamples)) {
    sourceMode = 'demo_in_repo'
    paths.samples_path = inRepoSamples
  } else if (fs.existsSync(siblingSamples)) {
    sourceMode = 'demo_sibling'
    paths.samples_path = siblingSamples
  }
  return {
    sourceMode,
    packRoot: inRepoRoot,
    paths,
    defaultAssetId: DEMO_ASSET_ID,
    defaultAssetName: DEMO_ASSET_NAME,
  }
}

function resolveSourceBundle(options) {
  const topic1Repo = resolveSiblingRepo('Project_1_Sample_evaluation_Generation')
  const traceRepo = resolveSiblingRepo('Project_1_Risk_Cause_Determination')
  const selected =
    options.mode === 'demo'
      ? resolveDemoBundle()
      : options.mode === 'official'
        ? resolveOfficialBundle()
        : (() => {
            const official = resolveOfficialBundle()
            if (Object.keys(official.paths).length > 0) return official
            return resolveDemoBundle()
          })()

  attachOptionalTraces(selected.paths, options, traceRepo)
  return {
    ...selected,
    topic1Repo,
    traceRepo,
  }
}

function validateNativeFiles(paths) {
  const missing = Object.entries(paths)
    .filter(([, value]) => !fs.existsSync(value))
    .map(([key, value]) => `${key}: ${value}`)
  if (missing.length > 0) {
    throw new Error(`Missing source files:\n${missing.join('\n')}`)
  }
}

function buildPayload(options) {
  const bundle = resolveSourceBundle(options)
  if (!bundle.paths.samples_path) {
    throw new Error(
      `No source pack found for mode=${options.mode || 'auto'}. ` +
        'Expected bundled value_qa / value_qa_demo0606 files under web/backend/data/input_corpora/.',
    )
  }
  validateNativeFiles(bundle.paths)
  const assetId = options.assetId || bundle.defaultAssetId
  const isOfficialSource =
    bundle.sourceMode === 'official_in_repo' || bundle.sourceMode === 'official_sibling'
  const isDemoSource =
    bundle.sourceMode === 'demo_in_repo' || bundle.sourceMode === 'demo_sibling'
  if (assetId === DEMO_ASSET_ID && isOfficialSource) {
    throw new Error(
      `Refusing to register ${DEMO_ASSET_ID} with official/round3 samples. Use --mode demo.`,
    )
  }
  if (assetId === OFFICIAL_ASSET_ID && isDemoSource) {
    throw new Error(
      `Refusing to register ${OFFICIAL_ASSET_ID} with DEMO-0606 samples. Use --mode official.`,
    )
  }
  const payload = {
    ...Object.fromEntries(
      Object.entries(bundle.paths).map(([key, value]) => [
        key,
        payloadPath(value, options.pathStyle),
      ]),
    ),
    asset_id: assetId,
    name: options.name || bundle.defaultAssetName,
  }
  return { payload, nativePaths: bundle.paths, bundle }
}

function backendUrl(options) {
  if (options.backendUrl) return options.backendUrl
  const registry = loadRegistry()
  return `http://${registry.host}:${registry.platform.backend_port}`
}

async function readJsonResponse(response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}

async function requestJson(url, init) {
  const response = await fetch(url, init)
  const body = await readJsonResponse(response)
  if (!response.ok) {
    const message = body?.detail || body?.msg || body?.raw || response.statusText
    const error = new Error(`${response.status} ${message}`)
    error.status = response.status
    error.body = body
    throw error
  }
  return body
}

async function getAsset(baseUrl, assetId) {
  try {
    const body = await requestJson(
      `${baseUrl}/api/benchmark/assets/${encodeURIComponent(assetId)}`,
    )
    return body?.data ?? null
  } catch (error) {
    if (error.status === 404) return null
    throw error
  }
}

function assetSummary(asset) {
  const manifest = asset?.manifest ?? {}
  return {
    asset_id: asset?.asset_id,
    source_mode: asset?.source_mode,
    benchmark_type: manifest.benchmark_type,
    schema_id: manifest.schema_id,
    sample_count: manifest.sample_count,
    group_count: manifest.group_count,
    quality_level_distribution: manifest.quality_level_distribution,
    qc_status: manifest.qc_status,
    trace_status: manifest.trace_status,
    model_eval_status: manifest.model_eval_status,
  }
}

async function importAsset(baseUrl, payload) {
  const body = await requestJson(`${baseUrl}/api/benchmark/assets/topic1-value-qa/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return body?.data?.asset
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  if (options.help) {
    printHelp()
    return
  }

  const baseUrl = backendUrl(options)
  const { payload, nativePaths, bundle } = buildPayload(options)
  const importUrl = `${baseUrl}/api/benchmark/assets/topic1-value-qa/import`

  console.log(`Project root: ${REPO_ROOT}`)
  console.log(`Backend URL:  ${baseUrl}`)
  console.log(`Path style:   ${options.pathStyle}`)
  console.log(`Mode:         ${options.mode || 'auto'}`)
  console.log(`Source mode:  ${bundle.sourceMode}`)
  console.log(`Pack root:    ${bundle.packRoot}`)
  console.log(`Asset ID:     ${payload.asset_id}`)

  if (options.dryRun) {
    console.log('\nNative source files:')
    for (const [key, value] of Object.entries(nativePaths)) {
      console.log(`- ${key}: ${value}`)
    }
    console.log('\nPOST', importUrl)
    console.log(JSON.stringify(payload, null, 2))
    return
  }

  const existing = await getAsset(baseUrl, payload.asset_id)
  if (existing) {
    console.log('\nAsset already exists; no import performed.')
    console.log(JSON.stringify(assetSummary(existing), null, 2))
    return
  }

  const imported = await importAsset(baseUrl, payload)
  const verified = await getAsset(baseUrl, payload.asset_id)
  console.log('\nImported and verified Topic1 value_qa asset:')
  console.log(JSON.stringify(assetSummary(verified ?? imported), null, 2))
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})
