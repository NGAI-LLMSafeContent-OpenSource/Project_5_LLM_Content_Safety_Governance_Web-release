import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import {
  buildRiskAttribution,
  buildTopic4Lineage,
  cancelTopic2RiskScanTask,
  getInputCorpusCatalog,
  getInputCorpusRecords,
  getTopic1CorpusToolCatalog,
  getTopic2FilterGuardHealth,
  getTopic2PrerunSamples,
  getTopic2RiskScanTask,
  getTopic4LineageHealth,
  getTopic4StaticLineage,
  getValueAssessment,
  getValueAttribution,
  getValueQaAssetStatus,
  getValueQaDimensions,
  parseTopic4LineageRecords,
  startTopic2RiskScanTask,
  submitDataInputWorkflow,
} from '@/api/dataInput'
import type {
  Topic2FilterGuardHealth,
  Topic2KeywordPrediction,
  Topic2RiskScanItem,
  Topic4LineageBuildPayload,
} from '@/api/dataInput'
import type { Topic1CorpusToolCatalogResult } from '@/types/topic1CorpusTools'
import { useDataInputWizard } from '@/composables/data-input/useDataInputWizard'
import { useInputStore } from '@/stores/input'
import { useStandardStore } from '@/stores/standard'
import type {
  CorrectionPreviewRange,
  InputFixItem,
  InputAssessmentRow,
} from '@/utils/inputMockData'
import { buildDataInputWorkflowPayload } from '@/utils/inputWorkflowPayload'
import type { DataInputTrack, ScreeningStandardViewModel } from '@/utils/dataInputConfig'
import type { StandardItem } from '@/stores/standard'
import { extractL1Code, formatHarmCategoryL1, formatHarmCategoryL2 } from '@/utils/topic2HarmLabels'

const STEP_DATASET = 1
const STEP_LINEAGE = 2
const STEP_SCREENING = 3
const STEP_ASSESSMENT = 4
const STEP_ATTRIBUTION = 5
const TOPIC2_RISK_SCAN_POLLING_INTERVAL_MS = 1000
const TOPIC2_RISK_SCAN_MAX_POLLING_ATTEMPTS = 120
const VALUE_QA_STANDARD_TAG = '课题一 value_qa'

const trackMeta = {
  value: {
    modeLabel: '价值侧',
    statsHint: '对接课题一返回：待提升占比 = 待提升条数 / 总条数。',
    radarTitleSuffix: '价值达成',
    radarAriaLabel: '价值评估雷达图',
    radarPalette: { area: 'rgba(21,101,192,.22)', dot: '#1565c0' },
  },
  risk: {
    modeLabel: '风险侧',
    statsHint: '对接课题二返回：异常率 = 异常样本 / 检测条数。',
    radarTitleSuffix: 'L1 风险分布',
    radarAriaLabel: '课题二 L1-1 至 L1-4 风险分布雷达图',
    radarPalette: { area: 'rgba(198,40,40,.18)', dot: '#c62828' },
  },
} as const satisfies Record<
  DataInputTrack,
  {
    modeLabel: string
    statsHint: string
    radarTitleSuffix: string
    radarAriaLabel: string
    radarPalette: { area: string; dot: string }
  }
>

export function useDataInputPage() {
  const standardStore = useStandardStore()
  const inputStore = useInputStore()
  const router = useRouter()
  const {
    activeDataInputStep,
    currentDataInputTrack,
    valueTrackStepLabels,
    riskTrackStepLabels,
    nextStepButtonLabel,
    goToSharedStep: goToSharedStepBase,
    activateTrackStep: activateTrackStepBase,
    goToPreviousStep: goToPreviousStepBase,
    goToNextStep: goToNextStepBase,
  } = useDataInputWizard()
  const inputRefs = storeToRefs(inputStore)
  const lastLineageRequestSignature = ref('')
  const lastValueTrackLoadedSignature = ref('')
  const lastValueAttributionLoadedSignature = ref('')
  const lastRiskScanSignature = ref('')
  const lastRiskAttributionLoadedSignature = ref('')
  const lastRiskScreeningSignature = ref('')
  const inputWorkflowSaving = ref(false)
  const topic1ToolCatalog = ref<Topic1CorpusToolCatalogResult | null>(null)
  const topic1ToolCatalogLoading = ref(false)
  const topic1ToolCatalogError = ref('')

  const corpusContext = computed(() => {
    const valueSelected = inputRefs.valueSelectedCorpus.value
    const riskSelected = inputRefs.riskSelectedCorpus.value
    const uploadedCount = inputRefs.uploadedFiles.value.length
    const valueRecordCount = inputRefs.valueCorpusRecords.value.length
    const riskRecordCount = inputRefs.riskCorpusRecords.value.length
    const customTrack = inputRefs.customCorpusTrack.value
    const lineageSource = inputRefs.lineageCorpusSource.value
    const lineageReady =
      inputRefs.topic4LineageStatus.value.connected && inputRefs.lineageNodes.value.length > 0
    const datasetName = inputRefs.datasetForm.value.name?.trim()
    const lineageSourceLabel =
      lineageSource === 'risk'
        ? '风险语料'
        : lineageSource === 'topic4_static'
          ? '课题四静态'
          : '价值语料'

    if (valueSelected || riskSelected) {
      const titleParts = [
        valueSelected ? `价值：${valueSelected.name}` : '',
        riskSelected ? `风险：${riskSelected.name}` : '',
      ].filter(Boolean)
      return {
        title: titleParts.join(' / '),
        description: '价值轨与风险轨分轨绑定语料，后续轨道各自承接对应样本，不再共用同一批语料。',
        chips: [
          valueSelected ? `价值 ${valueSelected.total || valueRecordCount || 0} 条` : '价值未选',
          riskSelected ? `风险 ${riskSelected.total || riskRecordCount || 0} 条` : '风险未选',
          `血缘源：${lineageSourceLabel}`,
          lineageReady ? '血缘已生成' : '待生成血缘',
        ].filter(Boolean),
      }
    }

    if (uploadedCount > 0) {
      return {
        title: datasetName || `已上传 ${uploadedCount} 个文件`,
        description: `自定义语料已归入${customTrack === 'value' ? '价值侧' : '风险侧'}，血缘图谱由当前上传文档构建。`,
        chips: [
          `${uploadedCount} 个文件`,
          customTrack === 'value' ? '价值侧语料' : '风险侧语料',
          inputRefs.datasetForm.value.domain,
          `血缘源：${lineageSourceLabel}`,
          lineageReady ? '血缘已生成' : '待生成血缘',
        ].filter(Boolean),
      }
    }

    return {
      title: datasetName || '尚未选择训练语料',
      description: '请先在第 1 步分别为价值 / 风险轨选择预跑语料或上传文件，再进入后续轨道。',
      chips: [inputRefs.datasetForm.value.domain, inputRefs.datasetForm.value.volume].filter(
        Boolean,
      ),
    }
  })

  const stepOneStatusCards = computed(() => {
    const catalogCount = inputRefs.corpusCatalog.value.length
    const valueSelected = inputRefs.valueSelectedCorpus.value
    const riskSelected = inputRefs.riskSelectedCorpus.value
    const uploadedCount = inputRefs.uploadedFiles.value.length
    const customTrack = inputRefs.customCorpusTrack.value
    const hasCustomValue = uploadedCount > 0 && customTrack === 'value'
    const hasCustomRisk = uploadedCount > 0 && customTrack === 'risk'
    return [
      {
        key: 'catalog',
        label: '预跑语料目录',
        sub: catalogCount > 0 ? `可选用 ${catalogCount} 个资产` : '等待导入 value_qa / 风险预跑',
        tone: catalogCount > 0 ? 'ok' : 'warn',
      },
      {
        key: 'value-corpus',
        label: '价值语料绑定',
        sub: valueSelected
          ? `${valueSelected.name} · ${valueSelected.total} 条`
          : hasCustomValue
            ? `未选预跑；已上传 ${uploadedCount} 个文件`
            : '尚未选择价值语料',
        tone: valueSelected || hasCustomValue ? 'ok' : 'warn',
      },
      {
        key: 'risk-corpus',
        label: '风险语料绑定',
        sub: riskSelected
          ? `${riskSelected.name} · ${riskSelected.total} 条`
          : hasCustomRisk
            ? `未选预跑；已上传 ${uploadedCount} 个文件`
            : '尚未选择风险语料',
        tone: riskSelected || hasCustomRisk ? 'ok' : 'warn',
      },
      {
        key: 'value',
        label: '价值轨承接',
        sub:
          valueSelected?.kind === 'value_qa' ? '进入后自动刷新维度与样本' : '可对接已导入 value_qa',
        tone: 'info',
      },
      {
        key: 'risk',
        label: '风险轨承接',
        sub: riskSelected
          ? '进入后按静态预跑标签筛选与评估'
          : '可对接课题二静态预跑 / neuron / keyword',
        tone: 'info',
      },
    ] as Array<{ key: string; label: string; sub: string; tone: 'ok' | 'warn' | 'info' }>
  })

  const trackEntryAvailability = computed(() => {
    const hasUploads = inputRefs.uploadedFiles.value.length > 0
    return {
      value:
        Boolean(inputRefs.valueSelectedCorpus.value) ||
        (hasUploads && inputRefs.customCorpusTrack.value === 'value'),
      risk:
        Boolean(inputRefs.riskSelectedCorpus.value) ||
        (hasUploads && inputRefs.customCorpusTrack.value === 'risk'),
    }
  })

  const currentRuleDraft = computed({
    get: () =>
      currentDataInputTrack.value === 'value'
        ? inputRefs.newValueRule.value
        : inputRefs.newRiskRule.value,
    set: (value: string) => {
      if (currentDataInputTrack.value === 'value') inputRefs.newValueRule.value = value
      else inputRefs.newRiskRule.value = value
    },
  })

  const currentTrackModel = computed(() => {
    const isValueTrack = currentDataInputTrack.value === 'value'
    const meta = trackMeta[currentDataInputTrack.value]
    const enabledL1 = standardStore.enabledRiskL1Codes()
    const riskRows = filterRiskAssessmentRowsByScreening(
      inputRefs.riskAssessmentRows.value,
      enabledL1,
      inputRefs.riskScienceStandards.value,
    )
    const valueRows = filterValueAssessmentRowsByScreening(
      inputRefs.valueAssessmentRows.value,
      standardStore.enabledValuePrimaryNames(),
      inputRefs.valueScienceStandards.value,
    )
    const valueSummary = {
      ...buildFilteredValueSummary(valueRows),
      ready: inputRefs.valueAssessmentSummary.value.ready,
    }
    const valueRadarScores = buildValueDimensionRadarScores(
      valueRows,
      standardStore.selectedValueRadarIndicators,
    )
    const riskRadarScores = pickRadarScoresByKeys(inputRefs.radarScores.value, enabledL1)
    const riskL2ShareBars = buildRiskL2ShareBars(riskRows, inputRefs.riskScienceStandards.value)

    return {
      ...meta,
      isValueMode: isValueTrack,
      primaryStandards: isValueTrack
        ? toScreeningStandards(standardStore.valueStandardGroups)
        : toScreeningStandards(standardStore.riskStandards),
      scienceStandards: isValueTrack
        ? toScienceScreeningStandards(inputRefs.valueScienceStandards.value, 'value')
        : toScienceScreeningStandards(inputRefs.riskScienceStandards.value, 'risk'),
      customRules: isValueTrack
        ? inputRefs.valueCustomRules.value
        : inputRefs.riskCustomRules.value,
      newRule: currentRuleDraft.value,
      assessmentStats: isValueTrack
        ? buildFilteredValueStats(valueRows)
        : buildFilteredRiskStats(riskRows),
      riskAssessmentSummary: isValueTrack
        ? null
        : {
            ...inputRefs.riskAssessmentSummary.value,
            total: riskRows.length,
            abnormal: riskRows.filter((row) => row.isAbnormal).length,
            normal: riskRows.filter((row) => !row.isAbnormal).length,
            highRisk: riskRows.filter((row) => row.isAbnormal).length,
            l1Covered: riskRows.filter((row) => Boolean(row.riskCategoryL1?.trim())).length,
            anomalyRate:
              riskRows.length > 0
                ? riskRows.filter((row) => row.isAbnormal).length / riskRows.length
                : 0,
          },
      valueAssessmentSummary: isValueTrack ? valueSummary : null,
      assessmentRows: isValueTrack ? valueRows : riskRows,
      radarIndicators: isValueTrack
        ? standardStore.valueRadarIndicators
        : standardStore.riskRadarIndicators,
      selectedRadarIndicators: isValueTrack
        ? standardStore.selectedValueRadarIndicators
        : standardStore.selectedRiskRadarIndicators,
      displayRadarScores: isValueTrack ? valueRadarScores : riskRadarScores,
      riskL2ShareBars: isValueTrack ? [] : riskL2ShareBars,
      enabledL1Codes: enabledL1,
      enabledValuePrimaries: standardStore.enabledValuePrimaryNames(),
      enabledScienceNames: isValueTrack
        ? inputRefs.valueScienceStandards.value
            .filter((item) => item.enabled)
            .map((item) => item.name)
        : inputRefs.riskScienceStandards.value
            .filter((item) => item.enabled && item.parentEnabled !== false)
            .map((item) => item.name),
    }
  })

  const riskScreeningStatus = computed(() => {
    const selected = inputRefs.riskSelectedCorpus.value
    const recordCount = inputRefs.riskCorpusRecords.value.length
    const aligned = standardStore.riskStandards.some((item) => item.id.startsWith('topic2-l1-'))
    const enabledCount = standardStore.enabledRiskL1Codes().length
    return {
      checked: true,
      connected: Boolean(selected) || aligned,
      loading: false,
      service: '课题二 L1 风险筛选',
      baseUrl: '',
      message: selected
        ? `已按风险语料对齐 L1（已勾选 ${enabledCount}/4）：${selected.name}`
        : aligned
          ? `已载入课题二 L1 维度（已勾选 ${enabledCount}/4），请绑定风险语料以统计本批覆盖。`
          : '进入本页后将按风险语料自动对齐 L1-1～L1-4。',
      source: 'risk_static_dynbench',
      mode: 'l1_taxonomy',
      fallback: false,
      blockingReason: '',
      nextAction: '可勾选 L1（主控雷达）与下属 L2（辅区细类）；取消 L1 时其子 L2 自动失效。',
      endpoints: [],
      track: 'risk' as const,
      assetId: selected?.assetId || '',
      assetName: selected?.name || '',
      total: recordCount || selected?.total || 0,
    }
  })

  const dataInputWorkflowPayload = computed(() =>
    buildDataInputWorkflowPayload({
      datasetForm: inputRefs.datasetForm.value,
      customCorpusTrack: inputRefs.customCorpusTrack.value,
      uploadedFiles: inputRefs.uploadedFiles.value,
      selectedLineageNodeId: inputRefs.selectedLineageNodeId.value,
      lineageNodes: inputRefs.lineageNodes.value,
      valueStandards: standardStore.valueStandards,
      riskStandards: standardStore.riskStandards,
      valueScienceStandards: inputRefs.valueScienceStandards.value,
      riskScienceStandards: inputRefs.riskScienceStandards.value,
      valueCustomRules: inputRefs.valueCustomRules.value,
      riskCustomRules: inputRefs.riskCustomRules.value,
      valueThresholdExcellent: inputRefs.valueThresholdExcellent.value,
      valueThresholdGood: inputRefs.valueThresholdGood.value,
      riskThresholdHigh: inputRefs.riskThresholdHigh.value,
      riskThresholdMid: inputRefs.riskThresholdMid.value,
      riskThresholdLow: inputRefs.riskThresholdLow.value,
      valueAssessmentStats: inputRefs.valueStats.value,
      riskAssessmentStats: inputRefs.riskStats.value,
      valueAssessmentRows: inputRefs.valueAssessmentRows.value,
      riskAssessmentRows: inputRefs.riskAssessmentRows.value,
      valueFixes: inputRefs.valueFixes.value,
      riskFixes: inputRefs.riskFixes.value,
    }),
  )

  function isSharedStepActive(targetStep: number) {
    return activeDataInputStep.value === targetStep
  }

  function isTrackStepActive(targetTrack: DataInputTrack, targetStep: number) {
    return currentDataInputTrack.value === targetTrack && activeDataInputStep.value === targetStep
  }

  function goToSharedStep(targetStep: number) {
    const previousStep = activeDataInputStep.value
    goToSharedStepBase(targetStep)
    resetLineageToStaticWhenEnteringFromDataset(previousStep, targetStep)
    void ensureTopic4LineageWhenEnteringStep()
    void ensureValueTrackWhenEnteringStep()
    void ensureRiskTrackWhenEnteringStep()
  }

  function activateTrackStep(targetTrack: DataInputTrack, targetStep: number) {
    activateTrackStepBase(targetTrack, targetStep)
    void ensureTopic4LineageWhenEnteringStep()
    void ensureValueTrackWhenEnteringStep()
    void ensureRiskTrackWhenEnteringStep()
  }

  function goToPreviousStep() {
    goToPreviousStepBase()
    void ensureTopic4LineageWhenEnteringStep()
    void ensureValueTrackWhenEnteringStep()
    void ensureRiskTrackWhenEnteringStep()
  }

  function goToNextStep() {
    const previousStep = activeDataInputStep.value
    goToNextStepBase()
    resetLineageToStaticWhenEnteringFromDataset(previousStep, activeDataInputStep.value)
    void ensureTopic4LineageWhenEnteringStep()
    void ensureValueTrackWhenEnteringStep()
    void ensureRiskTrackWhenEnteringStep()
  }

  function resetLineageToStaticWhenEnteringFromDataset(previousStep: number, targetStep: number) {
    if (previousStep !== STEP_DATASET || targetStep !== STEP_LINEAGE) return
    inputStore.setLineageCorpusSource('topic4_static')
    lastLineageRequestSignature.value = ''
    inputStore.clearTopic4LineageResult()
  }

  function togglePrimaryStandardForCurrentTrack(id = '') {
    if (!id) return
    if (currentDataInputTrack.value === 'value') {
      standardStore.toggleValueStandardGroup(id)
      return
    }
    standardStore.toggleStandardEnabled('input-risk', id)
    inputStore.syncRiskL2WithParentL1(standardStore.enabledRiskL1Codes())
  }

  function toggleScienceStandardForCurrentTrack(id = '') {
    if (!id) return
    if (currentDataInputTrack.value === 'risk') {
      const item = inputRefs.riskScienceStandards.value.find((row) => row.id === id)
      if (item && item.parentEnabled === false) {
        ElMessage.warning('请先勾选该 L2 所属的 L1 大类，再选择细类。')
        return
      }
    }
    inputStore.toggleScienceStandard(currentDataInputTrack.value, id)
    if (currentDataInputTrack.value !== 'value') return
    const science = inputRefs.valueScienceStandards.value.find((item) => item.id === id)
    if (science) {
      standardStore.setValueRadarIndicatorEnabled(science.id, science.enabled)
      standardStore.setValueRadarIndicatorEnabled(science.name, science.enabled)
    }
  }

  function toggleRadarIndicatorForCurrentTrack(id = '') {
    if (!id) return
    const item = standardStore.toggleRadarIndicator(currentDataInputTrack.value, id)
    if (currentDataInputTrack.value === 'risk') {
      inputStore.syncRiskL2WithParentL1(standardStore.enabledRiskL1Codes())
      return
    }
    if (!item) return
    // Keep AI-for-Science checklist in sync with radar chips.
    inputStore.setScienceStandardEnabled('value', item.id, item.enabled)
    inputStore.setScienceStandardEnabled('value', item.name, item.enabled)
  }

  function addCustomRuleForCurrentTrack(value = '') {
    inputStore.addRule(currentDataInputTrack.value, value)
    currentRuleDraft.value = ''
  }

  function removeCustomRuleForCurrentTrack(index = -1) {
    if (index < 0) return
    inputStore.removeRule(currentDataInputTrack.value, index)
  }

  function updateCustomRuleDraftForCurrentTrack(value = '') {
    currentRuleDraft.value = value
  }

  function updateValueExcellentThreshold(value = '') {
    inputStore.updateValueThreshold('excellent', value)
  }

  function updateValueGoodThreshold(value = '') {
    inputStore.updateValueThreshold('good', value)
  }

  function updateRiskHighThreshold(value = '') {
    inputStore.updateRiskThreshold('high', value)
  }

  function updateRiskMidThreshold(value = '') {
    inputStore.updateRiskThreshold('medium', value)
  }

  function updateRiskLowThreshold(value = '') {
    inputStore.updateRiskThreshold('low', value)
  }

  function selectLineageNode(id: string) {
    inputRefs.selectedLineageNodeId.value = id
  }

  async function ensureTopic4LineageWhenEnteringStep() {
    if (activeDataInputStep.value !== STEP_LINEAGE) return
    if (inputRefs.topic4LineageStatus.value.loading) return

    const signature = currentLineageInputSignature()
    const hasFreshResult =
      inputRefs.topic4LineageStatus.value.connected &&
      inputRefs.lineageNodes.value.length > 0 &&
      lastLineageRequestSignature.value === signature

    if (hasFreshResult) return
    await generateTopic4LineageForCurrentDataset({ silentSuccess: true })
  }

  async function ensureValueTrackWhenEnteringStep() {
    if (currentDataInputTrack.value !== 'value') return
    const step = activeDataInputStep.value
    if (step < STEP_SCREENING || step > STEP_ATTRIBUTION) return

    if (step === STEP_SCREENING || step === STEP_ASSESSMENT || step === STEP_ATTRIBUTION) {
      await ensureTopic1ValueTrackLoaded()
    }
    if (step === STEP_ATTRIBUTION) {
      await ensureValueAttributionLoaded()
    }
  }

  async function ensureTopic1ValueTrackLoaded() {
    if (inputRefs.topic1ValueQaAssetStatus.value.loading) return
    const signature = currentValueAssetSignature()
    const hasFreshResult =
      inputRefs.topic1ValueQaAssetStatus.value.connected &&
      lastValueTrackLoadedSignature.value === signature &&
      standardStore.valueStandardGroups.some((item) => item.tag === VALUE_QA_STANDARD_TAG)
    if (hasFreshResult) return
    await loadTopic1ValueTrackForInput({ silentSuccess: true })
  }

  async function ensureValueAttributionLoaded() {
    if (inputRefs.valueAttributionStatus.value.loading) return
    const signature = currentValueAssetSignature()
    const hasFreshResult =
      inputRefs.valueAttributionStatus.value.connected &&
      lastValueAttributionLoadedSignature.value === signature
    if (hasFreshResult) return
    await loadValueAttributionSamples({ silentSuccess: true })
  }

  async function ensureRiskTrackWhenEnteringStep() {
    if (currentDataInputTrack.value !== 'risk') return
    const step = activeDataInputStep.value
    if (step < STEP_SCREENING || step > STEP_ATTRIBUTION) return

    if (step === STEP_SCREENING || step === STEP_ASSESSMENT || step === STEP_ATTRIBUTION) {
      ensureRiskScreeningDimensionsLoaded()
    }
    if (step === STEP_ASSESSMENT || step === STEP_ATTRIBUTION) {
      await ensureTopic2RiskScanLoaded()
    }
    if (step === STEP_ATTRIBUTION) {
      await ensureRiskAttributionLoaded()
    }
  }

  function ensureRiskScreeningDimensionsLoaded() {
    const signature = currentRiskScreeningSignature()
    const alreadyTopic2 = standardStore.riskStandards.some((item) =>
      item.id.startsWith('topic2-l1-'),
    )
    if (alreadyTopic2 && lastRiskScreeningSignature.value === signature) return
    syncRiskScreeningFromCorpus()
    lastRiskScreeningSignature.value = signature
  }

  function currentRiskScreeningSignature() {
    const selected = inputRefs.riskSelectedCorpus.value
    return `${selected?.assetId || 'none'}:${inputRefs.riskCorpusRecords.value.length}`
  }

  function syncRiskScreeningFromCorpus() {
    const records = inputRefs.riskCorpusRecords.value
    const l1Count = new Map<string, number>()
    const l2Count = new Map<string, { count: number; l1Code: string }>()

    records.forEach((row) => {
      const l1Raw = row.meta?.harm_category_l1 || row.meta?.harm_category_L1 || ''
      const l1Code = extractL1Code(l1Raw)
      if (l1Code) l1Count.set(l1Code, (l1Count.get(l1Code) || 0) + 1)

      const l2Raw = (row.meta?.harm_category_l2 || row.meta?.harm_category_L2 || '').trim()
      if (l2Raw) {
        const prev = l2Count.get(l2Raw) || { count: 0, l1Code: l1Code || '' }
        l2Count.set(l2Raw, { count: prev.count + 1, l1Code: prev.l1Code || l1Code || '' })
      }
    })

    standardStore.applyTopic2RiskScreeningDimensions(
      ['L1-1', 'L1-2', 'L1-3', 'L1-4'].map((code) => ({
        code,
        label: formatHarmCategoryL1(code),
        count: l1Count.get(code) || 0,
      })),
    )

    const l2Items = Array.from(l2Count.entries())
      .map(([name, info]) => ({
        name,
        count: info.count,
        l1Code: info.l1Code,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 12)
    inputStore.applyRiskL2ScienceStandards(l2Items)
    inputStore.syncRiskL2WithParentL1(standardStore.enabledRiskL1Codes())
  }

  async function ensureTopic2RiskScanLoaded() {
    if (inputRefs.topic2FilterGuardStatus.value.loading) return

    const riskRecords = inputRefs.riskCorpusRecords.value
    const assessmentSource = inputRefs.riskAssessmentSource.value
    const rowsEmpty = inputRefs.riskAssessmentRows.value.length === 0

    // 有风险静态语料时优先落静态预跑，不自动跑 neuron
    if (
      riskRecords.length > 0 &&
      (assessmentSource === '' || assessmentSource === 'static' || rowsEmpty)
    ) {
      const signature = currentRiskScanSignature(riskRecords.length)
      const hasFreshStatic =
        assessmentSource === 'static' &&
        inputRefs.riskAssessmentSummary.value.ready &&
        lastRiskScanSignature.value === signature
      if (hasFreshStatic) return
      inputStore.applyRiskStaticCorpusResult(riskRecords, inputRefs.riskSelectedCorpus.value)
      lastRiskScanSignature.value = signature
      return
    }

    // 仅在没有风险静态语料、但血缘/上传可扫时，才自动跑 neuron
    if (riskRecords.length > 0) return

    const scanItems = buildTopic2RiskScanItems()
    if (scanItems.length === 0) return

    const signature = currentRiskScanSignature(scanItems.length)
    const hasFreshResult =
      inputRefs.riskAssessmentSummary.value.ready && lastRiskScanSignature.value === signature
    if (hasFreshResult) return
    await runTopic2KeywordForRiskSamples({ silentSuccess: true })
  }

  async function ensureRiskAttributionLoaded() {
    if (inputRefs.riskAttributionStatus.value.loading) return
    if (
      !inputRefs.riskAssessmentSummary.value.ready &&
      inputRefs.topic2KeywordPredictions.value.length === 0
    ) {
      return
    }
    const signature = currentRiskScanSignature(inputRefs.riskAssessmentRows.value.length)
    const hasFreshResult =
      inputRefs.riskAttributionStatus.value.connected &&
      lastRiskAttributionLoadedSignature.value === signature
    if (hasFreshResult) return
    await loadRiskAttributionSamples({ silentSuccess: true })
  }

  function currentValueAssetSignature() {
    const selected = inputRefs.valueSelectedCorpus.value
    if (selected?.kind === 'value_qa' && selected.assetId) return selected.assetId
    return inputRefs.topic1ValueQaAssetStatus.value.assetId || 'default-value-qa'
  }

  function currentRiskScanSignature(itemCount: number) {
    const selected = inputRefs.riskSelectedCorpus.value
    const corpusKey = selected ? `${selected.assetId}:${selected.total}` : 'upload-or-lineage'
    const method = inputRefs.topic2RiskDetectMethod.value
    const source = inputRefs.riskAssessmentSource.value || 'none'
    return `${method}|${source}|${corpusKey}|${itemCount}|${inputRefs.lineageNodes.value.length}`
  }

  function invalidateValueTrackCache() {
    lastValueTrackLoadedSignature.value = ''
    lastValueAttributionLoadedSignature.value = ''
  }

  function invalidateRiskTrackCache() {
    lastRiskScanSignature.value = ''
    lastRiskAttributionLoadedSignature.value = ''
    lastRiskScreeningSignature.value = ''
  }

  async function generateTopic4LineageForCurrentDataset(options: { silentSuccess?: boolean } = {}) {
    const requestSignature = currentLineageInputSignature()
    let topic4HealthConnected = false
    inputStore.setTopic4LineageLoading(true)
    try {
      if (inputRefs.lineageCorpusSource.value === 'topic4_static') {
        inputStore.clearTopic4LineageResult()
        const result = await getTopic4StaticLineage()
        inputStore.applyTopic4LineageResult(result)
        if (result.connected) {
          lastLineageRequestSignature.value = requestSignature
        } else {
          ElMessage.warning(result.message)
        }
        return
      }

      const health = await getTopic4LineageHealth()
      topic4HealthConnected = health.connected
      inputStore.setTopic4LineageStatus({
        connected: health.connected,
        service: health.service,
        baseUrl: health.base_url,
        message: health.message,
        source: health.source,
        mode: health.mode,
        fallback: health.fallback,
        blockingReason: health.blocking_reason,
        nextAction: health.next_action,
        endpoints: health.endpoints,
      })

      inputStore.clearTopic4LineageResult()

      if (!health.connected) {
        ElMessage.warning(health.message)
        return
      }

      const payload = await buildTopic4LineagePayload()
      const result = await buildTopic4Lineage(payload)
      inputStore.applyTopic4LineageResult(result)
      if (result.connected) {
        lastLineageRequestSignature.value = requestSignature
        if (!options.silentSuccess) ElMessage.success('已获取课题四血缘图谱结果。')
      } else ElMessage.warning(result.message)
    } catch (error) {
      const message = error instanceof Error ? error.message : '课题四血缘图谱生成请求失败'
      if (
        inputRefs.lineageCorpusSource.value !== 'topic4_static' &&
        topic4HealthConnected &&
        isRequestTimeoutMessage(message)
      ) {
        const timeoutMessage =
          '课题四服务已连接，但本次完整工作流生成超时，结果未返回；当前不展示旧图谱或中性风险结果。'
        inputStore.setTopic4LineageStatus({
          connected: true,
          message: timeoutMessage,
          blockingReason: '课题四 full_v2 同步工作流耗时较长，前端请求已超时。',
          nextAction: '请稍后重试生成，或确认课题四是否提供异步任务状态接口。',
        })
        inputStore.clearTopic4LineageResult()
        ElMessage.warning(timeoutMessage)
        return
      }
      inputStore.setTopic4LineageStatus({
        connected: false,
        message,
      })
      inputStore.clearTopic4LineageResult()
      ElMessage.error(message)
    } finally {
      inputStore.setTopic4LineageLoading(false)
    }
  }

  function currentLineageInputSignature() {
    const dataset = inputRefs.datasetForm.value
    const files = inputRefs.uploadedFiles.value.map((item) => item.signature).join('|')
    const lineageSource = inputRefs.lineageCorpusSource.value
    if (lineageSource === 'topic4_static') {
      return [
        dataset.name,
        dataset.domain,
        dataset.volume,
        dataset.desc,
        files,
        'topic4_static',
      ].join('::')
    }
    const selected =
      lineageSource === 'risk'
        ? inputRefs.riskSelectedCorpus.value
        : inputRefs.valueSelectedCorpus.value
    const recordCount =
      lineageSource === 'risk'
        ? inputRefs.riskCorpusRecords.value.length
        : inputRefs.valueCorpusRecords.value.length
    const corpus = selected ? `${lineageSource}:${selected.assetId}:${recordCount}` : lineageSource
    return [dataset.name, dataset.domain, dataset.volume, dataset.desc, files, corpus].join('::')
  }

  async function buildTopic4LineagePayload(): Promise<Topic4LineageBuildPayload> {
    const dataset = inputRefs.datasetForm.value
    const uploadedFiles = inputRefs.uploadedFiles.value
    if (uploadedFiles.length) {
      if (inputRefs.parsedUploadRecords.value.length > 0) {
        return { records: inputRefs.parsedUploadRecords.value }
      }
      const formData = new FormData()
      uploadedFiles.forEach((item) => formData.append('files', item.file))
      formData.append('dataset_name', dataset.name)
      formData.append('dataset_domain', dataset.domain)
      formData.append('dataset_volume', dataset.volume)
      formData.append('dataset_desc', dataset.desc)

      const parsed = await parseTopic4LineageRecords(formData)
      if (parsed.failures.length) {
        ElMessage.warning(
          `部分文件未能提取文本：${parsed.failures.map((item) => item.name).join('、')}`,
        )
      }
      inputStore.setParsedUploadRecords(parsed.records)
      return { records: parsed.records }
    }

    const lineageSource = inputRefs.lineageCorpusSource.value
    const corpusRecords =
      lineageSource === 'risk'
        ? inputRefs.riskCorpusRecords.value
        : inputRefs.valueCorpusRecords.value
    const selectedCorpus =
      lineageSource === 'risk'
        ? inputRefs.riskSelectedCorpus.value
        : inputRefs.valueSelectedCorpus.value

    if (corpusRecords.length) {
      const corpusSource =
        selectedCorpus?.name ||
        dataset.name ||
        (lineageSource === 'risk' ? '课题二风险预跑语料' : '课题一 value_qa 预跑语料')
      const records = corpusRecords.map((row, index) => {
        const fingerprint = `${row.id}-${index}`
        const chunkId = `P5_CORPUS_${String(index + 1).padStart(3, '0')}_${fingerprint}_CHUNK`
        const cleanedChunkId = `P5_CORPUS_${String(index + 1).padStart(3, '0')}_${fingerprint}_CLEANED`
        const baseRecord: Record<string, unknown> = {
          source: corpusSource,
          dataset_name: dataset.name,
          dataset_domain: dataset.domain,
          dataset_volume: dataset.volume,
          chunk_id: chunkId,
          cleaned_chunk_id: cleanedChunkId,
          raw_chunk: row.text,
          cleaned_chunk: row.text,
          QA_pairs: [
            {
              question: '【血缘元数据】该训练语料样本对应的数据集场景是什么？',
              answer: dataset.domain || '未填写数据场景',
              type: 'dataset_context',
              supporting_facts: [dataset.name, dataset.domain, corpusSource].filter(Boolean),
            },
            {
              question: '该训练语料片段的主要内容是什么？',
              answer: row.text.slice(0, 240),
              type: 'chunk_summary',
              supporting_facts: [row.id],
            },
            {
              question: '该片段中的关键信息 1 是什么？',
              answer: row.meta?.primary_dimension
                ? `一级维度：${row.meta.primary_dimension}`
                : `样本编号：${row.id}`,
              type: 'chunk_fact',
              supporting_facts: [
                row.meta?.primary_dimension || '',
                row.meta?.secondary_dimension || '',
                row.id,
              ].filter(Boolean),
            },
          ],
        }

        if (lineageSource === 'risk') {
          const originalLabel = String(row.meta?.original_label || '')
          const isRisky = originalLabel === 'unsafe' || String(row.meta?.is_risky || '') === 'true'
          const l1 = row.meta?.harm_category_L1 || row.meta?.harm_category_l1 || ''
          baseRecord.is_risky = isRisky
          baseRecord.original_label = originalLabel
          baseRecord.harm_category_L1 = l1
          baseRecord.harm_category_l1 = l1
        } else if (lineageSource === 'value') {
          const qualityLevel = String(row.meta?.quality_level || '').trim()
          const qualityNorm = qualityLevel.toLowerCase()
          const needsImprove =
            qualityNorm === 'low' ||
            qualityLevel === '待提升' ||
            String(row.meta?.status || '') === '待提升'
          baseRecord.quality_level = qualityLevel
          baseRecord.primary_dimension = row.meta?.primary_dimension || ''
          baseRecord.secondary_dimension = row.meta?.secondary_dimension || ''
          if (needsImprove) {
            baseRecord.quality_status = '待提升'
            baseRecord.needs_improvement = true
          }
        }

        return baseRecord
      })

      const riskAnnotations =
        lineageSource === 'risk'
          ? corpusRecords
              .map((row, index) => {
                const originalLabel = String(row.meta?.original_label || '')
                const isRisky =
                  originalLabel === 'unsafe' || String(row.meta?.is_risky || '') === 'true'
                if (!isRisky) return null
                const fingerprint = `${row.id}-${index}`
                const chunkId = `P5_CORPUS_${String(index + 1).padStart(3, '0')}_${fingerprint}_CHUNK`
                const l1 = row.meta?.harm_category_L1 || row.meta?.harm_category_l1 || 'UNSAFE'
                return {
                  case_id: chunkId,
                  risk_num: 1,
                  risk_list: [
                    {
                      type: l1 || 'UNSAFE',
                      content: row.text.slice(0, 500),
                    },
                  ],
                }
              })
              .filter((item): item is NonNullable<typeof item> => item !== null)
          : []

      return riskAnnotations.length > 0
        ? { records, risk_annotations: riskAnnotations }
        : { records }
    }

    const baseChunk = [
      `数据集名称：${dataset.name || '未命名训练语料'}`,
      `数据场景：${dataset.domain || '未填写'}`,
      `数据量级：${dataset.volume || '未填写'}`,
      `数据集描述：${dataset.desc || '未填写'}`,
    ].join('\n')

    return {
      records: [
        {
          source: `${dataset.name || '训练语料'}-表单输入`,
          dataset_name: dataset.name,
          dataset_domain: dataset.domain,
          dataset_volume: dataset.volume,
          chunk_id: 'P5_DATASET_FORM_CHUNK',
          cleaned_chunk_id: 'P5_DATASET_FORM_CLEANED',
          raw_chunk: baseChunk,
          cleaned_chunk: dataset.desc || dataset.name || '训练语料样本',
          QA_pairs: [
            {
              question: '【血缘元数据】该训练语料样本对应的数据集场景是什么？',
              answer: dataset.domain || '未填写数据场景',
              type: 'dataset_context',
              supporting_facts: [dataset.name, dataset.domain].filter(Boolean),
            },
            {
              question: '该训练语料片段的主要内容是什么？',
              answer: dataset.desc || dataset.name || '训练语料样本',
              type: 'chunk_summary',
              supporting_facts: [dataset.desc || dataset.name || '训练语料样本'].filter(Boolean),
            },
            {
              question: '该片段中的关键信息 1 是什么？',
              answer: `数据量级：${dataset.volume || '未填写'}`,
              type: 'chunk_fact',
              supporting_facts: [dataset.volume || '未填写'],
            },
          ],
        },
      ],
    }
  }

  async function runTopic2KeywordForRiskSamples(options: { silentSuccess?: boolean } = {}) {
    inputStore.setTopic2FilterGuardLoading(true)
    const scanItems = buildTopic2RiskScanItems()
    const method = inputRefs.topic2RiskDetectMethod.value
    const requestSignature = currentRiskScanSignature(scanItems.length)
    inputStore.clearTopic2KeywordResult()
    inputStore.clearTopic2RiskScanTaskState()
    try {
      const serviceReady = await checkTopic2RiskServiceHealth({
        manageLoading: false,
        showFailureToast: true,
        silentSuccess: true,
      })
      if (!serviceReady) {
        lastRiskScanSignature.value = ''
        inputStore.clearTopic2KeywordResult()
        return
      }

      if (scanItems.length === 0) {
        lastRiskScanSignature.value = ''
        ElMessage.warning('当前没有可用于风险识别的语料样本，请先完成第 1 步或血缘图谱。')
        return
      }

      const task = await startTopic2RiskScanTask(scanItems, { method })
      inputStore.setTopic2FilterGuardStatus({
        taskId: task.task_id,
        taskStatus: task.status,
        progress: task.progress,
        cancellable: task.cancellable,
        message: task.message,
        method: task.method || method,
      })

      const finishedTask = await pollTopic2RiskScanTask(task.task_id, (currentTask) => {
        inputStore.setTopic2FilterGuardStatus({
          taskId: currentTask.task_id,
          taskStatus: currentTask.status,
          progress: currentTask.progress,
          cancellable: currentTask.cancellable,
          message: currentTask.message,
        })
      })
      if (finishedTask.status === 'completed' && finishedTask.result) {
        inputStore.applyTopic2KeywordResult(finishedTask.result)
        inputStore.setTopic2FilterGuardStatus({
          taskId: finishedTask.task_id,
          taskStatus: finishedTask.status,
          progress: finishedTask.progress,
          cancellable: finishedTask.cancellable,
          message: finishedTask.message,
          method: finishedTask.result.method || method,
        })
        lastRiskScanSignature.value = requestSignature
        lastRiskAttributionLoadedSignature.value = ''
        const methodLabel = method === 'activation_probe' ? 'neuron' : 'keyword'
        if (!options.silentSuccess) {
          ElMessage.success(`已获取课题二 ${methodLabel} 识别结果。`)
        }
        return
      }

      lastRiskScanSignature.value = ''
      inputStore.clearTopic2KeywordResult()
      inputStore.setTopic2FilterGuardStatus({
        taskId: finishedTask.task_id,
        taskStatus: finishedTask.status,
        progress: finishedTask.progress,
        cancellable: finishedTask.cancellable,
        connected: false,
        message: finishedTask.message,
      })
      ElMessage.warning(finishedTask.message)
    } catch (error) {
      lastRiskScanSignature.value = ''
      const message = error instanceof Error ? error.message : '课题二输入风险识别请求失败'
      inputStore.clearTopic2KeywordResult()
      inputStore.setTopic2FilterGuardStatus({
        connected: false,
        message,
      })
      ElMessage.error(message)
    } finally {
      inputStore.setTopic2FilterGuardLoading(false)
    }
  }

  async function checkTopic2RiskServiceHealth(
    options: {
      manageLoading?: boolean
      showFailureToast?: boolean
      silentSuccess?: boolean
    } = {},
  ) {
    const method = inputRefs.topic2RiskDetectMethod.value
    if (options.manageLoading) inputStore.setTopic2FilterGuardLoading(true)
    try {
      const health = await getTopic2FilterGuardHealth({ method })
      inputStore.setTopic2FilterGuardStatus({
        connected: health.connected,
        service: health.service,
        baseUrl: health.base_url,
        message: health.message,
        source: health.source,
        mode: health.mode,
        method: health.method,
        fallback: health.fallback,
        blockingReason: health.blocking_reason,
        nextAction: health.next_action,
        endpoints: health.endpoints,
      })

      if (!health.connected) {
        if (options.showFailureToast) {
          ElMessage({
            type: 'warning',
            message: formatTopic2HealthFailureMessage(health),
            duration: 8000,
            showClose: true,
          })
        }
        return false
      }

      if (!options.silentSuccess) {
        ElMessage.success(health.message)
      }
      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : '课题二输入风险识别健康检查失败'
      inputStore.setTopic2FilterGuardStatus({
        connected: false,
        message,
        blockingReason: message,
        nextAction: '请确认课题五后端可用后重新检测。',
      })
      if (options.showFailureToast) {
        ElMessage({
          type: 'error',
          message,
          duration: 8000,
          showClose: true,
        })
      }
      return false
    } finally {
      if (options.manageLoading) inputStore.setTopic2FilterGuardLoading(false)
    }
  }

  async function loadTopic2PrerunAssetForRiskSamples() {
    inputStore.setTopic2PrerunAssetLoading(true)
    inputStore.clearTopic2KeywordResult()
    try {
      const result = await getTopic2PrerunSamples({
        asset_id:
          inputRefs.riskSelectedCorpus.value?.kind === 'topic2_prerun'
            ? inputRefs.riskSelectedCorpus.value.assetId
            : undefined,
        limit: 20,
      })
      inputStore.applyTopic2PrerunAssetResult(result)
      if (result.connected) ElMessage.success('已载入课题二正式预跑评测资产。')
      else ElMessage.warning(result.message)
    } catch (error) {
      const message = error instanceof Error ? error.message : '课题二正式预跑评测资产载入失败'
      inputStore.clearTopic2KeywordResult()
      inputStore.clearTopic2PrerunAssetResult()
      inputStore.setTopic2PrerunAssetStatus({
        connected: false,
        message,
      })
      ElMessage.error(message)
    } finally {
      inputStore.setTopic2PrerunAssetLoading(false)
    }
  }

  async function loadValueAttributionSamples(options: { silentSuccess?: boolean } = {}) {
    inputStore.setValueAttributionLoading(true)
    try {
      const assetId =
        (inputRefs.valueSelectedCorpus.value?.kind === 'value_qa'
          ? inputRefs.valueSelectedCorpus.value.assetId
          : undefined) ||
        inputRefs.topic1ValueQaAssetStatus.value.assetId ||
        undefined
      const result = await getValueAttribution({
        asset_id: assetId,
        limit: 24,
        prefer_low: true,
      })
      inputStore.applyAttributionResult(result)
      if (result.connected) {
        lastValueAttributionLoadedSignature.value = currentValueAssetSignature()
        if (!options.silentSuccess) ElMessage.success('已载入课题一价值归因样本。')
      } else ElMessage.warning(result.message)
    } catch (error) {
      const message = error instanceof Error ? error.message : '课题一价值归因载入失败'
      lastValueAttributionLoadedSignature.value = ''
      inputStore.applyAttributionResult({
        connected: false,
        track: 'value',
        service: '课题一价值归因',
        message,
        source: 'topic1_value_qa',
        mode: 'attribution_module',
        fallback: false,
        blocking_reason: message,
        next_action: '请确认后端可用，并已导入 value_qa 资产。',
        endpoints: [],
        asset_id: '',
        asset_name: '',
        total: 0,
        stats: [],
        rows: [],
      })
      ElMessage.error(message)
    } finally {
      inputStore.setValueAttributionLoading(false)
    }
  }

  async function loadTopic1ValueTrackForInput(options: { silentSuccess?: boolean } = {}) {
    inputStore.setTopic1ValueQaAssetLoading(true)
    try {
      const assetId =
        (inputRefs.valueSelectedCorpus.value?.kind === 'value_qa'
          ? inputRefs.valueSelectedCorpus.value.assetId
          : undefined) ||
        inputRefs.topic1ValueQaAssetStatus.value.assetId ||
        undefined

      // 分步加载：任一步失败不拖垮整卡，避免筛选/评估显示「等待资产」而归因仍可用
      const status = await getValueQaAssetStatus({ asset_id: assetId })
      inputStore.applyTopic1ValueQaAssetStatus(status)
      if (!status.connected) {
        lastValueTrackLoadedSignature.value = ''
        ElMessage.warning(status.message)
        return
      }

      let dimensionCount = 0
      let assessmentTotal = 0
      const partialErrors: string[] = []

      try {
        const dimensions = await getValueQaDimensions({
          asset_id: status.asset_id || assetId,
        })
        if (dimensions.connected) {
          standardStore.applyValueQaScreeningDimensions(dimensions.dimensions)
          inputStore.applyValueQaScienceStandards(dimensions.dimensions)
          if (inputRefs.valueScienceStandards.value.length > 0) {
            standardStore.syncValueRadarFromScienceStandards(inputRefs.valueScienceStandards.value)
          }
          dimensionCount = dimensions.dimensions?.length || 0
        } else if (dimensions.message) {
          partialErrors.push(dimensions.message)
        }
      } catch (error) {
        partialErrors.push(error instanceof Error ? error.message : '维度载入失败')
      }

      try {
        const enabledPrimaries = standardStore.enabledValuePrimaryNames()
        const enabledSecondaries = inputRefs.valueScienceStandards.value
          .filter((item) => item.enabled)
          .map((item) => item.name)
        const assessment = await getValueAssessment({
          asset_id: status.asset_id || assetId,
          primary_dimension: enabledPrimaries.length > 0 ? enabledPrimaries : undefined,
          secondary_dimension: enabledSecondaries.length > 0 ? enabledSecondaries : undefined,
          limit: 48,
        })
        if (assessment.connected) {
          inputStore.applyValueAssessmentResult(assessment)
          assessmentTotal = assessment.total || 0
        } else if (assessment.message) {
          partialErrors.push(assessment.message)
        }
      } catch (error) {
        partialErrors.push(error instanceof Error ? error.message : '评估样本载入失败')
      }

      lastValueTrackLoadedSignature.value = currentValueAssetSignature()
      if (partialErrors.length > 0) {
        ElMessage.warning(`价值资产已接入，但部分数据未就绪：${partialErrors[0]}`)
      } else if (!options.silentSuccess) {
        ElMessage.success(
          `已接入课题一 value_qa：维度 ${dimensionCount} 个，评估样本 ${assessmentTotal} 条。`,
        )
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '课题一价值轨道资产载入失败'
      lastValueTrackLoadedSignature.value = ''
      inputStore.applyTopic1ValueQaAssetStatus({
        connected: false,
        service: '课题一 value_qa 价值评测语料',
        message,
        source: 'topic1_value_qa',
        mode: 'asset_registry',
        fallback: false,
        blocking_reason: message,
        next_action: '请确认后端可用，并已导入 value_qa 资产。',
        endpoints: [],
        asset_id: '',
        asset_name: '',
        total: 0,
        group_count: 0,
        qc_status: '',
        trace_status: '',
        quality_level_distribution: {},
        primary_dimension_distribution: {},
        secondary_dimension_distribution: {},
      })
      ElMessage.error(message)
    } finally {
      inputStore.setTopic1ValueQaAssetLoading(false)
    }
  }

  async function loadRiskAttributionSamples(options: { silentSuccess?: boolean } = {}) {
    inputStore.setRiskAttributionLoading(true)
    try {
      const taskId = inputRefs.topic2FilterGuardStatus.value.taskId
      const predictions = inputRefs.topic2KeywordPredictions.value
      const staticRows = inputRefs.riskAssessmentRows.value
      const assessmentSource = inputRefs.riskAssessmentSource.value

      let effectivePredictions: Topic2KeywordPrediction[] = predictions
      if (predictions.length === 0 && assessmentSource === 'static' && staticRows.length > 0) {
        effectivePredictions = staticRows.map((row, index) =>
          mapRiskAssessmentRowToPrediction(row, index),
        )
      }

      const usePrerun =
        effectivePredictions.length === 0 && inputRefs.topic2PrerunAssetStatus.value.connected
      const result = await buildRiskAttribution({
        task_id: effectivePredictions.length === 0 && taskId ? taskId : undefined,
        predictions: effectivePredictions.length > 0 ? effectivePredictions : undefined,
        use_prerun: usePrerun,
        asset_id: usePrerun
          ? inputRefs.riskSelectedCorpus.value?.kind === 'topic2_prerun'
            ? inputRefs.riskSelectedCorpus.value.assetId
            : inputRefs.topic2PrerunAssetStatus.value.assetId || undefined
          : undefined,
        limit: Math.min(Math.max(effectivePredictions.length || staticRows.length || 20, 1), 500),
      })
      inputStore.applyAttributionResult(result)
      if (result.connected) {
        lastRiskAttributionLoadedSignature.value = currentRiskScanSignature(
          inputRefs.riskAssessmentRows.value.length,
        )
        if (!options.silentSuccess) ElMessage.success('已生成课题二风险归因证据链。')
      } else ElMessage.warning(result.message)
    } catch (error) {
      lastRiskAttributionLoadedSignature.value = ''
      const message = error instanceof Error ? error.message : '课题二风险归因生成失败'
      inputStore.applyAttributionResult({
        connected: false,
        track: 'risk',
        service: '课题二风险归因',
        message,
        source:
          inputRefs.riskAssessmentSource.value === 'static'
            ? 'risk_static_dynbench'
            : inputRefs.topic2RiskDetectMethod.value === 'activation_probe'
              ? 'topic2_activation_probe'
              : 'topic2_filterguard',
        mode: 'attribution_module',
        fallback: false,
        blocking_reason: message,
        next_action: '请先完成风险评估识别，再自动或手动生成风险归因。',
        endpoints: [],
        asset_id: '',
        asset_name: '',
        total: 0,
        stats: [],
        rows: [],
      })
      ElMessage.error(message)
    } finally {
      inputStore.setRiskAttributionLoading(false)
    }
  }

  function buildTopic2RiskScanItems(): Topic2RiskScanItem[] {
    const corpusItems = inputRefs.riskCorpusRecords.value
      .map((row) => ({
        text: row.text,
        lineage_node_id: '',
        lineage_node_label: row.id,
        risk_category_l1: row.meta?.harm_category_l1 || row.meta?.harm_category_L1 || '',
        risk_category_l2: row.meta?.harm_category_l2 || row.meta?.harm_category_L2 || '',
      }))
      .filter((item) => item.text.trim())
    const dedupedCorpusItems = dedupeRiskScanItemsByText(corpusItems)
    if (dedupedCorpusItems.length > 0) return dedupedCorpusItems

    const lineageNodes = inputRefs.lineageNodes.value
    const preferredNodes = lineageNodes.filter((node) => isCleanedChunkLineageNode(node.type))
    const fallbackNodes = lineageNodes.filter((node) => isRawChunkLineageNode(node.type))
    const scanNodes = preferredNodes.length > 0 ? preferredNodes : fallbackNodes

    const lineageItems = scanNodes
      .map((node) => ({
        text: node.summary,
        lineage_node_id: node.id,
        lineage_node_label: `${node.type} · ${node.docName || node.id}`,
        risk_category_l1: '',
        risk_category_l2: '',
      }))
      .filter((item) => item.text.trim())

    const dedupedLineageItems = dedupeRiskScanItemsByText(lineageItems)
    if (dedupedLineageItems.length > 0) return dedupedLineageItems

    return dedupeRiskScanItemsByText(
      inputRefs.riskAssessmentRows.value
        .map((row) => ({
          text: row.snippet,
          lineage_node_id: row.lineageNodeId || '',
          lineage_node_label: row.lineageNodeLabel || row.id,
          risk_category_l1: row.riskCategoryL1 || '',
          risk_category_l2: row.riskCategoryL2 || '',
        }))
        .filter((item) => item.text.trim()),
    )
  }

  async function loadInputCorpusCatalog() {
    inputStore.setCorpusCatalogLoading(true)
    try {
      const result = await getInputCorpusCatalog()
      inputStore.applyCorpusCatalog(result)
      if (!result.connected) ElMessage.warning(result.message)
    } catch (error) {
      const message = error instanceof Error ? error.message : '预跑语料目录加载失败'
      inputStore.applyCorpusCatalog({ connected: false, message, items: [] })
      ElMessage.error(message)
    } finally {
      inputStore.setCorpusCatalogLoading(false)
    }
  }

  async function loadTopic1CorpusTools() {
    if (topic1ToolCatalogLoading.value) return
    topic1ToolCatalogLoading.value = true
    topic1ToolCatalogError.value = ''
    try {
      topic1ToolCatalog.value = await getTopic1CorpusToolCatalog()
    } catch (error) {
      topic1ToolCatalog.value = null
      topic1ToolCatalogError.value =
        error instanceof Error ? error.message : '训练语料处理工具状态加载失败'
    } finally {
      topic1ToolCatalogLoading.value = false
    }
  }

  async function selectInputCorpusAsset(
    payload: { assetId: string; kind: string },
    options: { silentSuccess?: boolean } = {},
  ) {
    inputStore.setCorpusSelectLoading(true)
    try {
      const isRiskCorpus =
        payload.kind === 'risk_static_dynbench' || payload.kind === 'topic2_prerun'
      const catalogItem = inputRefs.corpusCatalog.value.find(
        (item) => item.assetId === payload.assetId,
      )
      // Load the complete cataloged corpus for both tracks. The API keeps 500
      // as a transport safety ceiling, while the catalog count remains the
      // source of truth for the requested sample size.
      const limit = Math.min(
        Math.max(catalogItem?.sampleCount || (isRiskCorpus ? 400 : 500), 1),
        500,
      )
      const result = await getInputCorpusRecords({
        asset_id: payload.assetId,
        kind: payload.kind,
        limit,
      })
      if (!result.connected) {
        ElMessage.warning(result.message)
        return
      }
      const track: 'value' | 'risk' =
        payload.kind === 'value_qa'
          ? 'value'
          : payload.kind === 'risk_static_dynbench' || payload.kind === 'topic2_prerun'
            ? 'risk'
            : result.kind === 'value_qa'
              ? 'value'
              : 'risk'
      inputStore.applySelectedCorpus(result, track)
      if (track === 'value') {
        invalidateValueTrackCache()
        if (result.kind === 'value_qa') {
          inputStore.applyTopic1ValueQaAssetStatus({
            connected: true,
            service: '课题一 value_qa 价值评测语料',
            message: `已在第 1 步绑定 value_qa 资产：${result.asset_name}`,
            source: 'topic1_value_qa',
            mode: 'asset_registry',
            fallback: false,
            blocking_reason: '',
            next_action: '进入价值轨后将自动载入筛选维度与评估样本。',
            endpoints: [],
            asset_id: result.asset_id,
            asset_name: result.asset_name,
            total: result.total,
            group_count: 0,
            qc_status: '',
            trace_status: '',
            quality_level_distribution: {},
            primary_dimension_distribution: {},
            secondary_dimension_distribution: {},
          })
        }
      } else {
        invalidateRiskTrackCache()
        syncRiskScreeningFromCorpus()
        lastRiskScreeningSignature.value = currentRiskScreeningSignature()
      }
      lastLineageRequestSignature.value = ''
      if (!options.silentSuccess) ElMessage.success(result.message)
    } catch (error) {
      const message = error instanceof Error ? error.message : '选用预跑语料失败'
      ElMessage.error(message)
    } finally {
      inputStore.setCorpusSelectLoading(false)
    }
  }

  function clearSelectedInputCorpus(track?: 'value' | 'risk') {
    if (track === 'value') {
      inputStore.clearValueSelectedCorpus()
      invalidateValueTrackCache()
      ElMessage.info('已取消价值语料选择，可改用上传或重新选择。')
      return
    }
    if (track === 'risk') {
      inputStore.clearRiskSelectedCorpus()
      invalidateRiskTrackCache()
      ElMessage.info('已取消风险语料选择，可改用上传或重新选择。')
      return
    }
    inputStore.clearSelectedCorpus()
    invalidateValueTrackCache()
    invalidateRiskTrackCache()
    ElMessage.info('已取消预跑语料选择，可改用上传或重新选择。')
  }

  function clearValueSelectedInputCorpus() {
    clearSelectedInputCorpus('value')
  }

  function clearRiskSelectedInputCorpus() {
    clearSelectedInputCorpus('risk')
  }

  async function setLineageCorpusSourceAndRebuild(source: 'value' | 'risk' | 'topic4_static') {
    inputStore.setLineageCorpusSource(source)
    lastLineageRequestSignature.value = ''
    await generateTopic4LineageForCurrentDataset()
  }

  function updateCustomCorpusTrack(track: DataInputTrack) {
    inputStore.setCustomCorpusTrack(track)
    lastLineageRequestSignature.value = ''
    inputStore.clearTopic4LineageResult()
    invalidateValueTrackCache()
    invalidateRiskTrackCache()
  }

  async function cancelTopic2RiskScanForRiskSamples() {
    const taskId = inputRefs.topic2FilterGuardStatus.value.taskId
    if (!taskId) return
    try {
      const task = await cancelTopic2RiskScanTask(taskId)
      inputStore.setTopic2FilterGuardStatus({
        taskId: task.task_id,
        taskStatus: task.status,
        progress: task.progress,
        cancellable: task.cancellable,
        message: task.message,
      })
      if (task.status === 'cancelled' || task.status === 'cancel_requested') {
        inputStore.clearTopic2KeywordResult()
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '取消课题二输入风险识别任务失败'
      ElMessage.error(message)
    }
  }

  function setDatasetFileDragState(value: boolean) {
    inputStore.setDraggingFiles(value)
  }

  function appendSelectedDatasetFiles(event: Event) {
    const input = event.target as HTMLInputElement
    void appendDatasetFiles(normalizeFiles(input.files))
    input.value = ''
  }

  function appendDroppedDatasetFiles(event: DragEvent) {
    inputStore.setDraggingFiles(false)
    void appendDatasetFiles(normalizeFiles(event.dataTransfer?.files))
  }

  function normalizeFiles(files: FileList | File[] | null | undefined) {
    return Array.from(files ?? []).filter((file) => file.name)
  }

  async function appendDatasetFiles(files: File[]) {
    const result = inputStore.appendFiles(files)
    invalidateRiskTrackCache()
    if (result.rejected.length > 0) {
      ElMessage.warning(
        result.rejected.map((item) => `${item.fileName}：${item.reason}`).join('；'),
      )
    }
    if (result.accepted.length === 0) return

    const acceptedIds = result.accepted.map((item) => item.id)
    inputStore.markUploadsParsing(acceptedIds)
    inputStore.setUploadParseLoading(true)
    try {
      const dataset = inputRefs.datasetForm.value
      const formData = new FormData()
      result.accepted.forEach((item) => formData.append('files', item.file))
      formData.append('dataset_name', dataset.name)
      formData.append('dataset_domain', dataset.domain)
      formData.append('dataset_volume', dataset.volume)
      formData.append('dataset_desc', dataset.desc)

      const parsed = await parseTopic4LineageRecords(formData)
      inputStore.applyUploadParseOutcome({
        fileIds: acceptedIds,
        records: parsed.records,
        failures: parsed.failures,
      })

      const parsedCount = result.accepted.filter((item) => {
        const current = inputRefs.uploadedFiles.value.find((row) => row.id === item.id)
        return current?.parseStatus === 'parsed'
      }).length

      if (parsed.failures.length) {
        ElMessage.warning(
          `已接收 ${result.accepted.length} 个文档，其中 ${parsed.failures.length} 个文件文本提取不完整。`,
        )
      } else {
        ElMessage.success(`已解析 ${parsedCount || result.accepted.length} 个文档`)
      }
    } catch (error) {
      inputStore.applyUploadParseOutcome({
        fileIds: acceptedIds,
        records: [],
        failures: result.accepted.map((item) => ({
          name: item.file.name,
          reason: error instanceof Error ? error.message : '文档上传解析失败',
        })),
      })
      ElMessage.error(error instanceof Error ? error.message : '文档上传解析失败')
    } finally {
      inputStore.setUploadParseLoading(false)
    }
  }

  function updateCorrectionPreviewRange(value: CorrectionPreviewRange) {
    inputRefs.correctionPreviewRange.value = value
  }

  function toggleFixExpansion(id: string) {
    inputStore.setExpandedFixId(id)
  }

  function updateSuggestedFixTextForCurrentTrack(id: string, value: string) {
    inputStore.updateSuggestedFixText(currentDataInputTrack.value, id, value)
  }

  function applyRecommendedFixForCurrentTrack(id: string) {
    inputStore.applyRecommendedFix(currentDataInputTrack.value, id)
  }

  function resetFixTextForCurrentTrack(id: string) {
    inputStore.resetFixText(currentDataInputTrack.value, id)
  }

  function markFixStatusForCurrentTrack(id: string, status: InputFixItem['status']) {
    inputStore.markFixStatus(currentDataInputTrack.value, id, status)
  }

  async function finishInputWorkflowAndReturnHome() {
    if (inputWorkflowSaving.value) return
    inputWorkflowSaving.value = true
    try {
      const result = await submitDataInputWorkflow(dataInputWorkflowPayload.value, {
        title: dataInputWorkflowPayload.value.dataset.name || '输入语料治理草稿',
        source: 'wizard',
        summary: {
          valueIssueCount: inputRefs.valueAssessmentRows.value.length,
          riskIssueCount: inputRefs.riskAssessmentRows.value.length,
          fixCount: inputRefs.valueFixes.value.length + inputRefs.riskFixes.value.length,
          lineageNodeCount: inputRefs.lineageNodes.value.length,
        },
        asset_refs: {
          value: inputRefs.valueSelectedCorpus.value,
          risk: inputRefs.riskSelectedCorpus.value,
          lineage: {
            source: inputRefs.lineageCorpusSource.value,
            selectedNodeId: inputRefs.selectedLineageNodeId.value,
          },
        },
      })
      inputStore.rememberWorkflowSubmission(dataInputWorkflowPayload.value)
      ElMessage.success(`已提交待复核草稿：${result.workflowId}`)
      router.push('/')
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '保存输入护栏草稿失败')
    } finally {
      inputWorkflowSaving.value = false
    }
  }

  onMounted(() => {
    void loadInputCorpusCatalog()
    void loadTopic1CorpusTools()
    void checkTopic2RiskServiceHealth({
      manageLoading: true,
      showFailureToast: true,
      silentSuccess: true,
    })
  })

  const screenedCurrentFixes = computed(() => {
    if (currentDataInputTrack.value === 'value') return inputRefs.valueFixes.value
    return filterRiskFixesByScreening(
      inputRefs.riskFixes.value,
      standardStore.enabledRiskL1Codes(),
      inputRefs.riskScienceStandards.value,
    )
  })

  const screenedFilteredFixes = computed(() => {
    const range = inputRefs.correctionPreviewRange.value
    if (range === 'all') return screenedCurrentFixes.value
    return screenedCurrentFixes.value.filter((item) => item.status === range)
  })

  return {
    ...inputRefs,
    currentFixes: screenedCurrentFixes,
    filteredFixes: screenedFilteredFixes,
    activeDataInputStep,
    currentDataInputTrack,
    valueTrackStepLabels,
    riskTrackStepLabels,
    nextStepButtonLabel,
    corpusContext,
    topic1ToolCatalog,
    topic1ToolCatalogLoading,
    topic1ToolCatalogError,
    inputWorkflowSaving,
    stepOneStatusCards,
    trackEntryAvailability,
    riskScreeningStatus,
    valueSelectedCorpus: inputRefs.valueSelectedCorpus,
    riskSelectedCorpus: inputRefs.riskSelectedCorpus,
    lineageCorpusSource: inputRefs.lineageCorpusSource,
    riskAssessmentSource: inputRefs.riskAssessmentSource,
    goToSharedStep,
    activateTrackStep,
    goToPreviousStep,
    goToNextStep,
    isSharedStepActive,
    isTrackStepActive,
    currentTrackModel,
    dataInputWorkflowPayload,
    togglePrimaryStandardForCurrentTrack,
    toggleScienceStandardForCurrentTrack,
    addCustomRuleForCurrentTrack,
    removeCustomRuleForCurrentTrack,
    updateCustomRuleDraftForCurrentTrack,
    updateValueExcellentThreshold,
    updateValueGoodThreshold,
    updateRiskHighThreshold,
    updateRiskMidThreshold,
    updateRiskLowThreshold,
    toggleRadarIndicatorForCurrentTrack,
    selectLineageNode,
    generateTopic4LineageForCurrentDataset,
    setLineageCorpusSourceAndRebuild,
    updateCustomCorpusTrack,
    runTopic2KeywordForRiskSamples,
    cancelTopic2RiskScanForRiskSamples,
    loadTopic2PrerunAssetForRiskSamples,
    loadValueAttributionSamples,
    loadTopic1ValueTrackForInput,
    loadRiskAttributionSamples,
    setTopic2RiskDetectMethod: (method: 'activation_probe' | 'keyword') => {
      inputStore.setTopic2RiskDetectMethod(method)
      invalidateRiskTrackCache()
      void checkTopic2RiskServiceHealth({
        manageLoading: true,
        showFailureToast: true,
        silentSuccess: true,
      })
    },
    setDatasetFileDragState,
    appendSelectedDatasetFiles,
    appendDroppedDatasetFiles,
    updateCorrectionPreviewRange,
    toggleFixExpansion,
    updateSuggestedFixTextForCurrentTrack,
    applyRecommendedFixForCurrentTrack,
    resetFixTextForCurrentTrack,
    markFixStatusForCurrentTrack,
    finishInputWorkflowAndReturnHome,
    removeUploadedFile: inputStore.removeUploadedFile,
    loadInputCorpusCatalog,
    loadTopic1CorpusTools,
    selectInputCorpusAsset,
    clearSelectedInputCorpus,
    clearValueSelectedInputCorpus,
    clearRiskSelectedInputCorpus,
  }
}

function toScreeningStandards(items: StandardItem[]): ScreeningStandardViewModel[] {
  return items.map((item) => {
    const isValueQa = item.tag.includes('value_qa') || item.tag.includes('课题一')
    const isRiskL1 = item.id.startsWith('topic2-l1-')
    const coverageMatch = item.desc.match(/(\d+)\s*(组|条)/)
    return {
      id: item.id,
      name: item.name,
      desc: item.desc,
      tag: item.tag,
      enabled: item.enabled,
      detailKind: isRiskL1 ? '课题二 L1' : isValueQa ? '价值一级维度' : '筛选维度',
      coverageText: coverageMatch
        ? `${coverageMatch[1]} ${coverageMatch[2]}`
        : item.desc || '暂无覆盖统计',
      sourceText: isRiskL1
        ? '课题二风险 taxonomy（本批语料对齐）'
        : isValueQa
          ? '课题一 value_qa 资产 · primary_metric'
          : item.tag || '标准体系',
      roleText: isRiskL1
        ? '勾选后进入风险评估雷达轴，并过滤异常样本 / 归因分布。'
        : '勾选后用于过滤评估与归因样本范围（不直接作为雷达轴）。',
    }
  })
}

function toScienceScreeningStandards(
  items: Array<{
    id: string
    name: string
    desc: string
    tag: string
    enabled: boolean
    rawName?: string
    l1Code?: string
    parentEnabled?: boolean
  }>,
  track: 'value' | 'risk',
): ScreeningStandardViewModel[] {
  return items.map((item) => {
    const coverageMatch = item.desc.match(/(\d+)\s*(组|条)/)
    const isValue = track === 'value'
    const parentOff = track === 'risk' && item.parentEnabled === false
    return {
      id: item.id,
      name: item.name,
      desc: item.desc,
      tag: item.tag,
      enabled: item.enabled,
      rawName: item.rawName,
      l1Code: item.l1Code,
      disabled: parentOff,
      groupLabel: item.l1Code ? formatHarmCategoryL1(item.l1Code) || item.l1Code : '',
      detailKind: isValue ? '价值二级维度' : '课题二 L2',
      coverageText: coverageMatch
        ? `${coverageMatch[1]} ${coverageMatch[2]}`
        : item.desc || '暂无覆盖统计',
      sourceText: isValue
        ? '课题一 value_qa 资产 · evaluation_dimension'
        : '课题二本批语料 L2 标签',
      roleText: isValue
        ? '勾选后进入评估雷达轴，并同步归因页「已选维度分布」。'
        : parentOff
          ? '所属 L1 未勾选：细类不可用。请先勾选对应 L1。'
          : '可选细类：进入评估页 L2 辅区占比；部分勾选时同步过滤异常样本。',
    }
  })
}

function filterRiskFixesByScreening(
  fixes: InputFixItem[],
  enabledCodes: string[],
  scienceStandards: Array<{
    name: string
    rawName?: string
    enabled: boolean
    l1Code?: string
    parentEnabled?: boolean
  }>,
): InputFixItem[] {
  if (!enabledCodes.length) return []
  const enabled = new Set(enabledCodes)
  const byL1 =
    enabled.size >= 4
      ? fixes
      : fixes.filter((item) => {
          const code = extractL1Code(item.predictedL1Id) || extractL1Code(item.riskCategoryL1)
          if (!code) return true
          return enabled.has(code)
        })

  const enabledL1 = new Set(enabledCodes)
  const relevant = scienceStandards.filter((item) => !item.l1Code || enabledL1.has(item.l1Code))
  if (relevant.length === 0) return byL1
  const enabledL2 = relevant.filter((item) => item.enabled && item.parentEnabled !== false)
  if (enabledL2.length === 0 || enabledL2.length >= relevant.length) return byL1

  return byL1.filter((item) => {
    const raw = String(item.riskCategoryL2 || '').trim()
    if (!raw) return true
    const zh = formatHarmCategoryL2(raw)
    return enabledL2.some((row) => row.rawName === raw || row.name === zh || row.name === raw)
  })
}

function filterRiskAssessmentRowsByScreening(
  rows: InputAssessmentRow[],
  enabledCodes: string[],
  scienceStandards: Array<{
    name: string
    rawName?: string
    enabled: boolean
    l1Code?: string
    parentEnabled?: boolean
  }>,
): InputAssessmentRow[] {
  const byL1 = filterRiskAssessmentRowsByEnabledL1(rows, enabledCodes)
  const enabledL1 = new Set(enabledCodes)
  const relevant = scienceStandards.filter((item) => !item.l1Code || enabledL1.has(item.l1Code))
  if (relevant.length === 0) return byL1

  const enabledL2 = relevant.filter((item) => item.enabled && item.parentEnabled !== false)
  // No L2 focus or all L2 selected → only L1 filter
  if (enabledL2.length === 0 || enabledL2.length >= relevant.length) return byL1

  return byL1.filter((row) => {
    if (!row.isAbnormal) return true
    const raw = String(row.riskCategoryL2 || '').trim()
    if (!raw) return true
    const zh = formatHarmCategoryL2(raw)
    return enabledL2.some((item) => item.rawName === raw || item.name === zh || item.name === raw)
  })
}

function buildRiskL2ShareBars(
  rows: InputAssessmentRow[],
  scienceStandards: Array<{
    name: string
    rawName?: string
    enabled: boolean
    l1Code?: string
    parentEnabled?: boolean
  }>,
): Array<{ label: string; l1Code: string; count: number; pct: string; width: string }> {
  const active = scienceStandards.filter((item) => item.enabled && item.parentEnabled !== false)
  if (active.length === 0) return []

  const abnormal = rows.filter((row) => row.isAbnormal)
  const denom = Math.max(abnormal.length, 1)
  return active
    .map((item) => {
      const count = abnormal.filter((row) => {
        const raw = String(row.riskCategoryL2 || '').trim()
        if (!raw) return false
        const zh = formatHarmCategoryL2(raw)
        return item.rawName === raw || item.name === zh || item.name === raw
      }).length
      const ratio = count / denom
      return {
        label: item.name,
        l1Code: item.l1Code || '',
        count,
        pct: abnormal.length === 0 ? '0%' : `${Math.round(ratio * 100)}%`,
        width: `${Math.min(Math.max(ratio * 100, 0), 100)}%`,
      }
    })
    .sort((a, b) => b.count - a.count)
}

function filterRiskAssessmentRowsByEnabledL1(
  rows: InputAssessmentRow[],
  enabledCodes: string[],
): InputAssessmentRow[] {
  if (!enabledCodes.length) return []
  const enabled = new Set(enabledCodes)
  // 若四类全开，不过滤；否则按勾选 L1 过滤（无 L1 的安全样本仍保留）
  if (enabled.size >= 4) return rows
  return rows.filter((row) => {
    const code = extractL1Code(row.riskCategoryL1) || extractL1Code(row.predictedL1Id)
    if (!code) return true
    return enabled.has(code)
  })
}

function parseValueDimensionParts(row: InputAssessmentRow): {
  primary: string
  secondary: string
} {
  const raw = String(row.dimension || row.topic || '').trim()
  if (!raw) return { primary: '', secondary: '' }
  const parts = raw
    .split(/\s*\/\s*/)
    .map((part) => part.trim())
    .filter(Boolean)
  if (parts.length >= 2) {
    return { primary: parts[0], secondary: parts[parts.length - 1] }
  }
  return { primary: parts[0] || '', secondary: parts[0] || '' }
}

function filterValueAssessmentRowsByScreening(
  rows: InputAssessmentRow[],
  enabledPrimaries: string[],
  scienceStandards: Array<{ name: string; enabled: boolean }>,
): InputAssessmentRow[] {
  if (!enabledPrimaries.length) return []
  const primarySet = new Set(enabledPrimaries)
  const enabledScience = scienceStandards.filter((item) => item.enabled).map((item) => item.name)
  const allScience = scienceStandards.map((item) => item.name)
  if (allScience.length > 0 && enabledScience.length === 0) return []
  const scienceActive =
    allScience.length > 0 && enabledScience.length > 0 && enabledScience.length < allScience.length
  const scienceSet = new Set(enabledScience)

  return rows.filter((row) => {
    const { primary, secondary } = parseValueDimensionParts(row)
    const primaryMatched =
      !primary ||
      primarySet.has(primary) ||
      [...primarySet].some(
        (name) =>
          primary.includes(name) ||
          name.includes(primary) ||
          formatValuePrimaryAlias(primary) === formatValuePrimaryAlias(name),
      )
    if (!primaryMatched) return false
    if (!scienceActive) return true
    if (!secondary) return true
    return scienceSet.has(secondary)
  })
}

function formatValuePrimaryAlias(raw: string): string {
  const text = String(raw || '').trim()
  if (text === '伦理敏感度' || text === '伦理合规度') return '伦理合规度'
  if (text === '文化忠诚度' || text === '文化忠实度') return '文化忠实度'
  return text
}

function buildFilteredValueSummary(rows: InputAssessmentRow[]) {
  const excellent = rows.filter((row) => row.status === '优').length
  const good = rows.filter((row) => row.status === '良').length
  const improve = rows.filter((row) => row.status === '待提升').length
  const total = rows.length
  return {
    total,
    excellent,
    good,
    improve,
    improveRate: total > 0 ? improve / total : 0,
    ready: total > 0 || rows.length === 0,
  }
}

function buildFilteredValueStats(
  rows: InputAssessmentRow[],
): Array<{ val: string; label: string }> {
  const summary = buildFilteredValueSummary(rows)
  return [
    {
      val: `${Math.round(summary.improveRate * 100)}%`,
      label: '待提升占比',
    },
    { val: String(summary.total), label: '总数据条数' },
    { val: String(summary.excellent), label: '优档条数' },
    { val: String(summary.good), label: '良档条数' },
  ]
}

function buildValueDimensionRadarScores(
  rows: InputAssessmentRow[],
  selectedKeys: string[],
): Record<string, number> {
  const scoreMap: Record<string, number> = { 优: 0.92, 良: 0.74, 待提升: 0.42 }
  const buckets = new Map<string, number[]>()
  const preferSecondary = selectedKeys.some((key) =>
    rows.some((row) => {
      const { secondary } = parseValueDimensionParts(row)
      return secondary === key
    }),
  )

  rows.forEach((row) => {
    const { primary, secondary } = parseValueDimensionParts(row)
    const key = preferSecondary
      ? secondary || primary || '价值达成'
      : primary || secondary || '价值达成'
    const list = buckets.get(key) || []
    list.push(scoreMap[row.status] ?? 0.5)
    buckets.set(key, list)
  })

  const scores: Record<string, number> = {}
  const keys = selectedKeys.length > 0 ? selectedKeys : Array.from(buckets.keys())
  keys.forEach((key) => {
    const values = buckets.get(key) || []
    scores[key] = values.length
      ? Math.round((values.reduce((sum, item) => sum + item, 0) / values.length) * 100) / 100
      : 0
  })
  return scores
}

function pickRadarScoresByKeys(
  scores: Record<string, number>,
  keys: string[],
): Record<string, number> {
  const next: Record<string, number> = {}
  keys.forEach((key) => {
    if (key in scores) next[key] = scores[key]
    else next[key] = 0
  })
  return next
}

function buildFilteredRiskStats(rows: InputAssessmentRow[]): Array<{ val: string; label: string }> {
  const total = rows.length
  const abnormal = rows.filter((row) => row.isAbnormal).length
  const normal = Math.max(total - abnormal, 0)
  const anomalyRate = total > 0 ? abnormal / total : 0
  return [
    { val: `${Math.round(anomalyRate * 100)}%`, label: '异常率' },
    { val: String(total), label: '检测条数' },
    { val: String(normal), label: '安全样本' },
    { val: String(abnormal), label: '异常条数' },
  ]
}

function isCleanedChunkLineageNode(type: string) {
  const normalized = type.toLowerCase().replace(/\s+/g, '')
  return normalized === 'cleanedchunk'
}

function isRawChunkLineageNode(type: string) {
  const normalized = type.toLowerCase().replace(/\s+/g, '')
  return normalized === 'chunk'
}

function dedupeRiskScanItemsByText(items: Topic2RiskScanItem[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = item.text.replace(/\s+/g, ' ').trim()
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function mapRiskAssessmentRowToPrediction(
  row: InputAssessmentRow,
  index: number,
): Topic2KeywordPrediction {
  const isAbnormal = Boolean(row.isAbnormal)
  const score = Number(row.score)
  return {
    id: row.id,
    text: row.snippet,
    source_index: index,
    lineage_node_id: row.lineageNodeId || '',
    lineage_node_label: row.lineageNodeLabel || row.id,
    risk_category_l1: row.riskCategoryL1 || '',
    risk_category_l2: row.riskCategoryL2 || '',
    predicted_l1_id: row.predictedL1Id || '',
    detect_method: row.detectMethod || 'static_prerun',
    action: row.action || row.suggestion,
    score: Number.isFinite(score) ? score : isAbnormal ? 1 : 0,
    threshold: 0.5,
    prediction: isAbnormal ? 1 : 0,
    is_abnormal: isAbnormal,
    status: row.status,
    suggestion: row.suggestion,
    evidence_chain: row.evidenceChain || [],
    correction_contract_status: '',
    findings: (row.findings || []).map((finding) => ({
      keyword: finding.keyword,
      evidence: finding.evidence,
      risk_type: finding.riskType,
    })),
  }
}

function isRequestTimeoutMessage(message: string) {
  const normalized = message.toLowerCase()
  return normalized.includes('timeout') || normalized.includes('超时')
}

async function pollTopic2RiskScanTask(
  taskId: string,
  onUpdate: (task: Awaited<ReturnType<typeof getTopic2RiskScanTask>>) => void,
) {
  for (let attempt = 0; attempt < TOPIC2_RISK_SCAN_MAX_POLLING_ATTEMPTS; attempt += 1) {
    await wait(TOPIC2_RISK_SCAN_POLLING_INTERVAL_MS)
    const task = await getTopic2RiskScanTask(taskId)
    onUpdate(task)
    if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
      return task
    }
    if (task.status === 'cancel_requested') return task
  }

  throw new Error('课题二输入风险识别任务仍在后端执行，请稍后重新点击识别以刷新任务结果。')
}

function wait(durationMs: number) {
  return new Promise((resolve) => window.setTimeout(resolve, durationMs))
}

function formatTopic2HealthFailureMessage(health: Topic2FilterGuardHealth) {
  const detail = health.blocking_reason || health.message
  return detail ? `${health.message} 原因：${detail}` : health.message
}
