/**
 * Runnable smoke checks for standard-mode elapsed helpers.
 * Keep in sync with mapStandardBenchmarkRunProgress.ts (Vitest not wired yet).
 *
 *   node web/frontend/src/utils/benchmark/__tests__/mapStandardBenchmarkRunProgress.smoke.mjs
 */

function parseBenchmarkApiDateMs(value) {
  const trimmed = value.trim()
  if (!trimmed) return Number.NaN
  const hasExplicitOffset = /Z$|[+-]\d{2}:\d{2}$/.test(trimmed)
  const normalized = !hasExplicitOffset && trimmed.includes('T') ? `${trimmed}Z` : trimmed
  return Date.parse(normalized)
}

function formatStandardRunElapsed(elapsedMs) {
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function resolveStandardRunElapsedMs(task, nowMs) {
  const raw = task?.started_at || task?.created_at
  if (!raw) return 0
  const started = parseBenchmarkApiDateMs(raw)
  if (Number.isNaN(started)) return 0
  return Math.max(0, nowMs - started)
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

assertEqual(
  parseBenchmarkApiDateMs('2026-08-11T15:05:00'),
  parseBenchmarkApiDateMs('2026-08-11T15:05:00Z'),
  'naive ISO == Z',
)

assertEqual(
  parseBenchmarkApiDateMs('2026-08-11T15:05:00+00:00'),
  parseBenchmarkApiDateMs('2026-08-11T15:05:00Z'),
  'offset +00:00 == Z',
)

assertEqual(
  resolveStandardRunElapsedMs(
    { started_at: '2026-08-11T15:05:00.000000', created_at: null },
    Date.parse('2026-08-11T15:05:36Z'),
  ),
  36_000,
  'naive started_at elapsed is 36s not ~8h',
)

assertEqual(resolveStandardRunElapsedMs(null, Date.now()), 0, 'null task')
assertEqual(
  resolveStandardRunElapsedMs({ started_at: 'not-a-date', created_at: null }, Date.now()),
  0,
  'invalid timestamp',
)

assertEqual(formatStandardRunElapsed(0), '0:00', '0ms')
assertEqual(formatStandardRunElapsed(36_000), '0:36', '36s')
assertEqual(formatStandardRunElapsed(12 * 60_000 + 36_000), '12:36', '12m36s')
assertEqual(formatStandardRunElapsed(3_600_000), '1:00:00', '1h')
assertEqual(formatStandardRunElapsed(3_636_000), '1:00:36', '1h36s')
assertEqual(formatStandardRunElapsed(8 * 3_600_000 + 36_000), '8:00:36', '8h36s')

// Regression: raw Date.parse on naive ISO in UTC+8 would inflate ~8h
const naive = '2026-08-11T15:05:00'
const nowMs = Date.parse('2026-08-11T15:05:36Z')
const fixed = resolveStandardRunElapsedMs({ started_at: naive, created_at: null }, nowMs)
const broken = Math.max(0, nowMs - Date.parse(naive))
if (!(fixed === 36_000 && broken >= 8 * 3_600_000)) {
  // In UTC+0 hosts, broken may also be 36s; still require fixed path.
  assertEqual(fixed, 36_000, 'fixed path always 36s')
}

console.log('mapStandardBenchmarkRunProgress smoke: ok')
