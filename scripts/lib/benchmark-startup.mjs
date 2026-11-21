export const LOCAL_BENCHMARK_URL = 'http://127.0.0.1:6006'
export const REMOTE_BENCHMARK_URL =
  'https://u288206-6f2x-63496cc3.weste.seetacloud.com:8443'
export const LOCAL_OUTPUT_GUARDRAIL_DETECT_TIMEOUT_SECONDS = '60'
export const REMOTE_OUTPUT_GUARDRAIL_DETECT_TIMEOUT_SECONDS = '300'

const VALID_MODES = new Set(['local', 'remote'])

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`
}

export function parseBenchmarkMode(args) {
  let mode = 'local'
  let seenBenchmark = false

  for (const arg of args) {
    if (!arg.startsWith('--benchmark=')) {
      throw new Error(`Unknown argument: ${arg}`)
    }
    if (seenBenchmark) {
      throw new Error('--benchmark may only be provided once')
    }

    mode = arg.slice('--benchmark='.length)
    if (!VALID_MODES.has(mode)) {
      throw new Error(
        `Invalid benchmark mode: ${mode}. Expected local or remote.`,
      )
    }
    seenBenchmark = true
  }

  return mode
}

export function benchmarkUrlForMode(mode) {
  if (mode === 'local') {
    return LOCAL_BENCHMARK_URL
  }
  if (mode === 'remote') {
    return REMOTE_BENCHMARK_URL
  }
  throw new Error(`Invalid benchmark mode: ${mode}`)
}

export function benchmarkEnvironment(baseUrl) {
  const detectTimeoutSeconds =
    baseUrl === REMOTE_BENCHMARK_URL
      ? REMOTE_OUTPUT_GUARDRAIL_DETECT_TIMEOUT_SECONDS
      : LOCAL_OUTPUT_GUARDRAIL_DETECT_TIMEOUT_SECONDS
  return {
    backend: {
      BENCHMARK_BASE_URL: baseUrl,
      OUTPUT_GUARDRAIL_DETECT_TIMEOUT_SECONDS: detectTimeoutSeconds,
    },
    frontend: { VITE_TOPIC3_BENCHMARK_URL: baseUrl },
  }
}

export function isTaxonomyResponse(body) {
  return (
    Array.isArray(body) &&
    body.length > 0 &&
    body.some(
      (item) =>
        typeof item?.id === 'number' &&
        typeof item?.name === 'string' &&
        item.name.trim().length > 0,
    )
  )
}

export async function checkBenchmarkHealth(
  baseUrl,
  fetchImpl = globalThis.fetch,
) {
  try {
    const response = await fetchImpl(
      `${baseUrl.replace(/\/+$/, '')}/api/taxonomies`,
      { signal: AbortSignal.timeout(2000) },
    )
    if (!response.ok) {
      return false
    }
    return isTaxonomyResponse(await response.json())
  } catch {
    return false
  }
}

export function buildBenchmarkStartScript(repoPath) {
  return [
    `cd ${shellQuote(repoPath)}`,
    'test -x .venv/bin/python',
    'rm -f .project5-benchmark.pid',
    '( EVAL_PYTHON=.venv/bin/python ./run.sh >> server.log 2>&1 </dev/null & echo $! > .project5-benchmark.pid )',
  ].join(' && ')
}

/** @deprecated Use buildBenchmarkStartScript */
export function buildWslBenchmarkScript(wslRepoPath) {
  return buildBenchmarkStartScript(wslRepoPath)
}

export function buildBenchmarkStopScript(repoPath) {
  return [
    `cd ${shellQuote(repoPath)}`,
    'test -f .project5-benchmark.pid || exit 0',
    'pid="$(cat .project5-benchmark.pid)"',
    'case "$pid" in (*[!0-9]*|"") exit 1;; esac',
    'if kill -0 "$pid" 2>/dev/null; then',
    '  if [ -r "/proc/$pid/cwd" ]; then',
    '    cwd="$(readlink -f "/proc/$pid/cwd")"',
    '    cmd="$(tr "\\0" " " < "/proc/$pid/cmdline")"',
    '    test "$cwd" = "$PWD"',
    '  else',
    '    cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n \'s/^n//p\')"',
    '    cmd="$(ps -p "$pid" -o args= 2>/dev/null | sed \'s/^[[:space:]]*//\')"',
    '    test "$(cd "$cwd" 2>/dev/null && pwd -P)" = "$(pwd -P)"',
    '  fi',
    '  case "$cmd" in (*"uvicorn app:app"*) kill "$pid";; (*) exit 1;; esac',
    '  for attempt in {1..20}; do',
    '    kill -0 "$pid" 2>/dev/null || break',
    '    sleep 0.25',
    '  done',
    '  kill -0 "$pid" 2>/dev/null && kill -KILL "$pid"',
    'fi',
    'rm -f .project5-benchmark.pid',
  ].join('\n')
}

/** @deprecated Use buildBenchmarkStopScript */
export function buildWslStopScript(wslRepoPath) {
  return buildBenchmarkStopScript(wslRepoPath)
}
