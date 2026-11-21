/**
 * Minimal frontend smoke for CBRNE controlled sample detail (#119 / Spec #116 T3).
 *
 * Run with:
 *   node web/frontend/src/utils/__tests__/cbrne-sample-detail.smoke.mjs
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const srcRoot = join(dirname(fileURLToPath(import.meta.url)), '../..')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const panelSource = readFileSync(
  join(srcRoot, 'components/benchmark/BenchmarkAssetPanel.vue'),
  'utf8',
)
const drawerSource = readFileSync(
  join(srcRoot, 'components/benchmark/BenchmarkCbrneSampleDrawer.vue'),
  'utf8',
)
const apiSource = readFileSync(join(srcRoot, 'api/benchmark.ts'), 'utf8')
const typesSource = readFileSync(join(srcRoot, 'types/index.ts'), 'utf8')
const disclosureModuleSource = readFileSync(
  join(srcRoot, 'composables/benchmark/useCbrneSampleDisclosure.ts'),
  'utf8',
)

assert(
  panelSource.includes('BenchmarkCbrneSampleDrawer') &&
    panelSource.includes('openCbrneSamples') &&
    panelSource.includes('data-testid="cbrne-open-controlled-detail"'),
  'Benchmark asset panel must expose an explicit CBRNE controlled-detail action',
)

assert(
  !panelSource.includes('full_text') ||
    !/cbrneDatasetAssets[\s\S]{0,800}full_text/.test(panelSource),
  'CBRNE overview cards must not render full_text inline',
)

assert(
  drawerSource.includes('discloseCbrneSample') &&
    !drawerSource.includes('getCbrneSampleDetail') &&
    drawerSource.includes('getCbrneSampleRefs') &&
    drawerSource.includes('查看全文并记录访问') &&
    drawerSource.includes('data-testid="cbrne-open-detail"') &&
    drawerSource.includes('data-testid="cbrne-full-text"'),
  'CBRNE drawer must use the disclosure command only after the explicit audited action',
)

assert(
  drawerSource.includes('handleClosed') &&
    drawerSource.includes('handleVisibilityChange') &&
    drawerSource.includes('drawerSession.close()') &&
    drawerSource.includes('destroy-on-close'),
  'closing the CBRNE drawer must immediately invalidate and clear full-text state',
)

assert(
  drawerSource.includes('modal-class="cbrne-sample-drawer-modal"') &&
    drawerSource.includes('.cbrne-sample-drawer-modal.el-overlay') &&
    drawerSource.includes('--cbrne-drawer-header-offset') &&
    drawerSource.includes('calc(100% - var(--cbrne-drawer-header-offset))') &&
    !/\.cbrne-sample-drawer-host\.el-drawer\s*\{[^}]*top:/.test(drawerSource),
  'CBRNE overlay must sit below AppHeader (drawer fills overlay; do not double-offset the panel)',
)

assert(
  !drawerSource.includes('useRoute(') &&
    !drawerSource.includes('router.push') &&
    !drawerSource.includes('full_text=') &&
    !drawerSource.includes('query.'),
  'CBRNE detail must not copy full text into the route/URL',
)

assert(
  drawerSource.includes('原始字段（raw）') &&
    drawerSource.includes('平台规范化字段（platform_normalized）') &&
    drawerSource.includes('selectedDetail.raw') &&
    drawerSource.includes('selectedDetail.platform_normalized'),
  'detail pane must separately identify raw and platform-normalized fields',
)

assert(
  drawerSource.includes('aria-live') &&
    drawerSource.includes('drawerSessionState.disclosure') &&
    drawerSource.includes('role="alert"'),
  'disclosure loading/success/error must be exposed as accessible live status',
)

assert(
  apiSource.includes('discloseCbrneSample') &&
    apiSource.includes('/cbrne/samples/') &&
    apiSource.includes('/disclosures') &&
    apiSource.includes('disclosureRequestId') &&
    apiSource.includes('getCbrneSampleRefs') &&
    apiSource.includes('/cbrne/sample-refs'),
  'benchmark API client must expose CBRNE disclosure POST and sample-refs endpoints',
)

assert(
  typesSource.includes('export interface BenchmarkCbrneSampleDetail') &&
    typesSource.includes('BenchmarkCbrneSampleDisclosureRequest') &&
    typesSource.includes('disclosure_request_id') &&
    typesSource.includes('platform_normalized') &&
    typesSource.includes('access_event'),
  'TypeScript types must cover CBRNE detail, normalization, and access event fields',
)

assert(
  disclosureModuleSource.includes("'idle' | 'loading' | 'success' | 'error'") &&
    disclosureModuleSource.includes('generation') &&
    disclosureModuleSource.includes('createRequestId()') &&
    disclosureModuleSource.includes('activeDisclosureRequestId'),
  'disclosure lifecycle must expose stable states, request identities, and stale-response invalidation',
)

assert(
  /createCbrneSampleDrawerSession/.test(disclosureModuleSource) &&
    /function close\(\)[\s\S]*?disclosureController\.reset\(\)/.test(disclosureModuleSource) &&
    /async function loadRefs\(\)[\s\S]*?listSampleRefs/.test(disclosureModuleSource),
  'drawer session must own refs loading, restore/pagination, and full-text clearing separately from disclosure',
)

const restoreBody = disclosureModuleSource.match(/async function restore\([\s\S]*?\n {2}\}/)
const loadRefsBody = disclosureModuleSource.match(/async function loadRefs\(\)[\s\S]*?\n {2}\}/)
assert(
  restoreBody && !restoreBody[0].includes('disclosureController.disclose('),
  'restoring the drawer (open / page / asset restore) must never disclose full text',
)
assert(
  loadRefsBody && !loadRefsBody[0].includes('disclosureController'),
  'the sample-ref read path must never touch the disclosure controller',
)

assert(
  /@click\.stop="loadDetail\(row\)"/.test(drawerSource) &&
    /async function loadDetail\([\s\S]*?drawerSession\.disclose\(/.test(drawerSource) &&
    /async function retryDisclosure\([\s\S]*?drawerSession\.retry\(/.test(drawerSource) &&
    (drawerSource.match(/drawerSession\.disclose\(/g) || []).length === 1 &&
    (drawerSource.match(/drawerSession\.retry\(/g) || []).length === 1 &&
    !/@click[^=]*="[^"]*disclose/i.test(drawerSource),
  'only the explicit per-sample action and its retry may invoke the disclosure command',
)
assert(
  /@opened="openDrawerSession"/.test(drawerSource) &&
    /@current-change="handlePageChange"/.test(drawerSource) &&
    /@size-change="handlePageSizeChange"/.test(drawerSource) &&
    /function handlePageChange\(page: number\)[\s\S]*?drawerSession\.goToPage\(page\)/.test(
      drawerSource,
    ) &&
    /function handlePageSizeChange\(size: number\)[\s\S]*?drawerSession\.changePageSize\(size\)/.test(
      drawerSource,
    ) &&
    !/@(opened|current-change|size-change)="[^"]*(loadDetail|disclose)/.test(drawerSource),
  'opening the drawer, paging and page-size changes must only read sample refs, never disclose full text',
)

assert(
  drawerSource.includes('data-testid="cbrne-masked-ref"') &&
    drawerSource.includes('脱敏摘要') &&
    /props\.focusSample/.test(drawerSource) &&
    /drawerSession\.restore\([\s\S]*?props\.focusSample/.test(drawerSource),
  'a deep-linked sample must open as a masked reference without invoking disclosure',
)

assert(
  /@row-click="handleRowSelect"/.test(drawerSource) &&
    /function handleRowSelect\(row: BenchmarkCbrneSampleRefItem\)[\s\S]*?drawerSession\.selectSample\(row\)/.test(
      drawerSource,
    ),
  'selecting a sample row must only select its masked reference',
)

console.log('cbrne-sample-detail.smoke.mjs ok')
