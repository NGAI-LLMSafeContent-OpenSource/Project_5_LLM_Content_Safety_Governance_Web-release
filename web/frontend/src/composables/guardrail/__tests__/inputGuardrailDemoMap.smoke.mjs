/**
 *   node --experimental-strip-types web/frontend/src/composables/guardrail/__tests__/inputGuardrailDemoMap.smoke.mjs
 */
import {
  DISPOSAL_NOTICE,
  SOURCE_NOTICE,
  isLowValueRow,
  isRiskRow,
  mapAbnormalSlice,
  mapFixItems,
  mapPoisonSlice,
  mapRadarScores,
  nextIndex,
  pickDefaultValueAsset,
  pickEvidenceIndex,
  pickValueCatalogItems,
} from '../inputGuardrailDemoMap.ts'

function assertEqual(actual, expected, label) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

assertEqual(
  DISPOSAL_NOTICE,
  '以下为预跑检测生成的修正建议，不表示语料已写入本地库。',
  'DISPOSAL_NOTICE',
)
assertEqual(
  SOURCE_NOTICE,
  '价值证据、风险证据与血缘图谱来自不同预跑资产，不表示同一条语料已同时完成三维检测。',
  'SOURCE_NOTICE',
)

const catalog = [
  { asset_id: 'static', name: 'dynbench', kind: 'risk_static_dynbench', ready: true },
  { asset_id: 'v2', name: 'qa-b', kind: 'value_qa', ready: false },
  { asset_id: 'v1', name: 'qa-a', kind: 'value_qa', ready: true },
]
const valueItems = pickValueCatalogItems(catalog)
assertEqual(valueItems.map((item) => item.asset_id), ['v2', 'v1'], 'value catalog excludes static')
assertEqual(pickDefaultValueAsset(catalog)?.asset_id, 'v1', 'prefer ready value_qa')
assertEqual(pickDefaultValueAsset(valueItems.filter((item) => !item.ready))?.asset_id, 'v2', 'fallback first value_qa')

assertEqual(mapRadarScores({}), [], 'empty radar omitted')
assertEqual(mapRadarScores({ a: 0.2, b: 0.8 }).map((item) => item.name), ['a', 'b'], 'radar keeps listed dims')

const prerun = [
  { status: '异常', strategy_chain: ['jailbreak'], bypassed_moderators: ['mod-a'] },
  { status: '安全', strategy_chain: [], bypassed_moderators: [] },
]
const abnormal = mapAbnormalSlice(prerun, 10, 2, ['危害1', '危害2', '危害3', '危害4'])
assertEqual(abnormal.abnormalCount, 1, 'abnormal count')
assertEqual(abnormal.l1Labels.length, 3, 'l1 cap')
assertEqual(abnormal.hasDetail, true, 'abnormal hasDetail')

const poison = mapPoisonSlice(prerun)
assertEqual(poison.strategyCount, 1, 'strategy count')
assertEqual(poison.bypassCount, 1, 'bypass count')
assertEqual(poison.hasDetail, true, 'poison hasDetail')
assertEqual(mapPoisonSlice([{ strategy_chain: [], bypassed_moderators: [] }]).hasDetail, false, 'poison empty is not zeros')

assertEqual(isLowValueRow({ quality_level: 'low' }), true, 'low quality')
assertEqual(isLowValueRow({ status: '待提升' }), true, '待提升')
assertEqual(isRiskRow({ status: '异常' }), true, 'risk 异常')
assertEqual(isRiskRow({ status: '安全' }), false, 'risk 安全')

const rows = [{ id: 'a', status: '安全' }, { id: 'b', status: '异常' }]
assertEqual(pickEvidenceIndex(rows, (row) => isRiskRow(row)), 1, 'pick first matching')
assertEqual(nextIndex(2, 1), 0, 'wrap')
assertEqual(mapFixItems([{ snippet: 'x', suggestion: 'y' }, { snippet: 'z', suggestion: 'w' }], 1).length, 1, 'fix cap')

console.log('inputGuardrailDemoMap.smoke.mjs ok')
