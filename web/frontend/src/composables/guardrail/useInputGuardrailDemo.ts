import { computed, ref } from 'vue'
import {
  buildRiskAttribution,
  getInputCorpusCatalog,
  getInputCorpusRecords,
  getTopic2PrerunSamples,
  getTopic4StaticLineage,
  getValueAssessment,
  getValueAttribution,
  type AttributionRow,
  type InputCorpusCatalogItem,
  type InputCorpusRecord,
} from '@/api/dataInput'
import {
  ASSESSMENT_LIMIT,
  ATTRIBUTION_LIMIT,
  EMPTY_CATALOG,
  ERR_CATALOG,
  ERR_LINEAGE,
  ERR_RISK,
  ERR_VALUE,
  ERR_VALUE_EVIDENCE,
  ERR_RISK_EVIDENCE,
  PRERUN_LIMIT,
  RECORDS_LIMIT,
  type AbnormalSlice,
  type EvidenceTrack,
  type FixItem,
  type InputGuardrailEvidenceView,
  type LineageSlice,
  type PoisonSlice,
  isLowValueRow,
  isRiskRow,
  mapAbnormalSlice,
  mapFixItems,
  mapLineageSlice,
  mapPoisonSlice,
  mapQualityDistribution,
  mapRadarScores,
  mapRiskEvidenceFromAttribution,
  mapRiskEvidenceFromPrerun,
  mapValueEvidence,
  nextIndex,
  pickDefaultValueAsset,
  pickEvidenceIndex,
  pickValueCatalogItems,
  truncateText,
} from './inputGuardrailDemoMap'

/** Surfaces ERR_* messages: 语料目录不可达, 价值预跑评估不可达, 课题二预跑样本不可达, 静态血缘图谱暂不可用. */
export function useInputGuardrailDemo() {
  const valueCatalog = ref<InputCorpusCatalogItem[]>([])
  const selectedValue = ref<InputCorpusCatalogItem | null>(null)
  const valueRecords = ref<InputCorpusRecord[]>([])
  const ingestLoading = ref(false)
  const ingestError = ref('')
  const riskAssetName = ref('')
  const riskAssetId = ref('')
  const riskPairCount = ref(0)
  const riskTotal = ref(0)
  const riskSnippets = ref<string[]>([])
  const valueLoading = ref(false)
  const valueError = ref('')
  const valueStats = ref<Array<{ val: string; label: string }>>([])
  const valueQuality = ref<Array<{ label: string; count: number }>>([])
  const valueRadar = ref<Array<{ name: string; score: number }>>([])
  const riskLoading = ref(false)
  const riskError = ref('')
  const abnormal = ref<AbnormalSlice | null>(null)
  const poison = ref<PoisonSlice | null>(null)
  const lineageLoading = ref(false)
  const lineageError = ref('')
  const lineage = ref<LineageSlice | null>(null)
  const evidenceTrack = ref<EvidenceTrack>('risk')
  const evidenceError = ref('')
  const valueEvidenceRows = ref<InputGuardrailEvidenceView[]>([])
  const riskEvidenceRows = ref<InputGuardrailEvidenceView[]>([])
  const evidenceIndex = ref(-1)
  const valueFixItems = ref<FixItem[]>([])
  const riskFixItems = ref<FixItem[]>([])
  let valueToken = 0

  const evidenceRows = computed(() =>
    evidenceTrack.value === 'value' ? valueEvidenceRows.value : riskEvidenceRows.value,
  )
  const evidence = computed(() => evidenceRows.value[evidenceIndex.value] || null)
  /** Evidence spinner follows the active track's own source load only. */
  const evidenceLoading = computed(() =>
    evidenceTrack.value === 'value' ? valueLoading.value : riskLoading.value,
  )

  function syncEvidenceError() {
    if (evidence.value) {
      evidenceError.value = ''
      return
    }
    evidenceError.value = evidenceTrack.value === 'value' ? ERR_VALUE_EVIDENCE : ERR_RISK_EVIDENCE
  }

  function setEvidenceTrack(track: EvidenceTrack) {
    evidenceTrack.value = track
    evidenceIndex.value = evidenceRows.value.length ? 0 : -1
    syncEvidenceError()
  }

  function showNextEvidence() {
    evidenceIndex.value = nextIndex(evidenceRows.value.length, evidenceIndex.value)
    syncEvidenceError()
  }

  function reconcileEvidenceTrack() {
    if (riskEvidenceRows.value.length) {
      evidenceTrack.value = 'risk'
      evidenceIndex.value = pickEvidenceIndex(riskEvidenceRows.value, (row) =>
        isRiskRow({ status: row.qualityLevel }),
      )
    } else if (valueEvidenceRows.value.length) {
      evidenceTrack.value = 'value'
      evidenceIndex.value = 0
    } else {
      evidenceIndex.value = -1
    }
    syncEvidenceError()
  }

  async function loadValueAsset(item: InputCorpusCatalogItem) {
    const token = ++valueToken
    selectedValue.value = item
    valueLoading.value = true
    valueError.value = ''
    valueRecords.value = []
    valueStats.value = []
    valueQuality.value = []
    valueRadar.value = []
    valueEvidenceRows.value = []
    valueFixItems.value = []
    try {
      const [records, assessment, attribution] = await Promise.all([
        getInputCorpusRecords({ asset_id: item.asset_id, kind: 'value_qa', limit: RECORDS_LIMIT }),
        getValueAssessment({ asset_id: item.asset_id, limit: ASSESSMENT_LIMIT }),
        getValueAttribution({
          asset_id: item.asset_id,
          limit: ATTRIBUTION_LIMIT,
          prefer_low: true,
        }),
      ])
      if (token !== valueToken) return
      if (records.connected) valueRecords.value = records.records || []
      if (!assessment.connected) {
        valueError.value = ERR_VALUE
      } else {
        valueStats.value = assessment.stats || []
        valueQuality.value = mapQualityDistribution(assessment.quality_level_distribution)
        valueRadar.value = mapRadarScores(assessment.radar_scores)
        valueFixItems.value = mapFixItems(assessment.fix_rows || [])
        const sourceRows =
          attribution.connected && attribution.rows.length
            ? attribution.rows
            : (assessment.rows || []).filter((row: AttributionRow) => isLowValueRow(row))
        valueEvidenceRows.value = sourceRows.map((row) => mapValueEvidence(row))
      }
    } catch {
      if (token !== valueToken) return
      valueError.value = ERR_VALUE
    } finally {
      if (token === valueToken) {
        valueLoading.value = false
        if (!riskEvidenceRows.value.length && valueEvidenceRows.value.length) {
          evidenceTrack.value = 'value'
          evidenceIndex.value = 0
          syncEvidenceError()
        } else if (evidenceTrack.value === 'value') {
          evidenceIndex.value = valueEvidenceRows.value.length ? 0 : -1
          syncEvidenceError()
        }
      }
    }
  }

  async function loadCatalog() {
    ingestLoading.value = true
    ingestError.value = ''
    try {
      const catalog = await getInputCorpusCatalog()
      valueCatalog.value = pickValueCatalogItems(catalog.items || [])
      const selected = pickDefaultValueAsset(valueCatalog.value)
      if (!selected) {
        ingestError.value = catalog.connected === false ? ERR_CATALOG : EMPTY_CATALOG
        return
      }
      await loadValueAsset(selected)
    } catch {
      ingestError.value = ERR_CATALOG
    } finally {
      ingestLoading.value = false
    }
  }

  async function loadRisk() {
    riskLoading.value = true
    riskError.value = ''
    abnormal.value = null
    poison.value = null
    riskEvidenceRows.value = []
    riskFixItems.value = []
    riskSnippets.value = []
    try {
      const prerun = await getTopic2PrerunSamples({ limit: PRERUN_LIMIT })
      if (!prerun.connected) {
        riskError.value = ERR_RISK
        return
      }
      const prerunRows = prerun.rows || []
      riskAssetId.value = prerun.asset_id || ''
      riskAssetName.value = prerun.asset_name || ''
      riskPairCount.value = prerun.pair_count || 0
      riskTotal.value = prerun.total || 0
      riskSnippets.value = prerunRows
        .map((row) => truncateText(row.snippet || ''))
        .filter(Boolean)
        .slice(0, 3)
      abnormal.value = mapAbnormalSlice(
        prerunRows,
        prerun.pair_count || 0,
        prerun.total || 0,
        prerun.l1_labels || [],
      )
      poison.value = mapPoisonSlice(prerunRows)
      // Prerun evidence/fix first so attribution failure cannot wipe detect cards.
      riskEvidenceRows.value = prerunRows.map((row) => mapRiskEvidenceFromPrerun(row))
      riskFixItems.value = mapFixItems(prerunRows.filter((row) => isRiskRow(row)))
      try {
        const attribution = await buildRiskAttribution({
          use_prerun: true,
          limit: ATTRIBUTION_LIMIT,
        })
        const attrRows = attribution.connected ? attribution.rows || [] : []
        if (attrRows.length) {
          riskEvidenceRows.value = attrRows.map((row) => mapRiskEvidenceFromAttribution(row))
          riskFixItems.value = mapFixItems(attrRows.filter((row) => isRiskRow(row)))
        }
      } catch {
        // Keep prerun slices/evidence; riskError only when prerun itself failed.
      }
    } catch {
      riskError.value = ERR_RISK
    } finally {
      riskLoading.value = false
      reconcileEvidenceTrack()
    }
  }

  async function loadLineage() {
    lineageLoading.value = true
    lineageError.value = ''
    lineage.value = null
    try {
      const result = await getTopic4StaticLineage()
      if (!result.connected) {
        lineageError.value = ERR_LINEAGE
        return
      }
      lineage.value = mapLineageSlice(result.summary, result.reportSummary)
    } catch {
      lineageError.value = ERR_LINEAGE
    } finally {
      lineageLoading.value = false
    }
  }

  async function loadDemo() {
    await Promise.all([loadCatalog(), loadRisk(), loadLineage()])
    reconcileEvidenceTrack()
  }

  async function selectValueAsset(assetId: string) {
    const item = valueCatalog.value.find((entry) => entry.asset_id === assetId)
    if (!item) return
    await loadValueAsset(item)
  }

  return {
    valueCatalog,
    selectedValue,
    valueRecords,
    ingestLoading,
    ingestError,
    riskAssetName,
    riskAssetId,
    riskPairCount,
    riskTotal,
    riskSnippets,
    valueLoading,
    valueError,
    valueStats,
    valueQuality,
    valueRadar,
    riskLoading,
    riskError,
    abnormal,
    poison,
    lineageLoading,
    lineageError,
    lineage,
    evidenceTrack,
    evidenceLoading,
    evidenceError,
    evidence,
    valueEvidenceRows,
    riskEvidenceRows,
    valueFixItems,
    riskFixItems,
    loadDemo,
    selectValueAsset,
    setEvidenceTrack,
    showNextEvidence,
  }
}
