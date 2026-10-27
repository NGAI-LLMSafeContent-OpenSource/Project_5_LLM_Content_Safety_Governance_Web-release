/**
 * Run with:
 *   node web/frontend/src/utils/__tests__/breakable-text.smoke.mjs
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { splitAfterSeparators } from '../breakable-text.ts'

const srcRoot = join(dirname(fileURLToPath(import.meta.url)), '../..')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

assert(
  splitAfterSeparators('Project_3_Dynamic_Risk_Benchmark_Generation').join('|') ===
    'Project_|3_|Dynamic_|Risk_|Benchmark_|Generation',
  'underscored identifiers must keep the underscore on the left segment',
)
assert(
  splitAfterSeparators('evaluations/qwen3_5_9b').join('|') === 'evaluations/|qwen3_|5_|9b',
  'paths must break after slashes and underscores',
)
assert(
  splitAfterSeparators('run_a · qwen3.5-9B').join('|') === 'run_|a ·| qwen3.5-9B',
  'the middle dot is a break opportunity and must stay with the left segment',
)
assert(splitAfterSeparators('v6').join('|') === 'v6', 'short tokens stay whole')
assert(splitAfterSeparators('').join('|') === '', 'empty text stays a single empty segment')
assert(splitAfterSeparators('___').join('|') === '_|_|_', 'consecutive separators each break')

const envelope = readFileSync(
  join(srcRoot, 'components/governance/GovernanceReportEnvelope.vue'),
  'utf8',
)
const riskCard = readFileSync(
  join(srcRoot, 'components/governance/GovernanceRiskPrerunReviewCard.vue'),
  'utf8',
)
const css = readFileSync(join(srcRoot, 'assets/styles/governance.css'), 'utf8')

assert(
  envelope.includes('BreakableText') && envelope.includes('file.path'),
  'the report envelope must break evidence paths',
)
assert(
  riskCard.includes('BreakableText') && riskCard.includes('primary_evaluator.run_id'),
  'the risk review card must break version run ids',
)
assert(
  css.includes('.risk-prerun-review__versions') &&
    css.includes('repeat(auto-fit, minmax(min(100%, 200px), 1fr))'),
  'version columns must follow the card width',
)
assert(
  !css.includes('.risk-prerun-review__versions {\n    grid-template-columns: 1fr;'),
  'version columns must not collapse from the viewport width',
)

console.log('breakable-text.smoke.mjs ok')
