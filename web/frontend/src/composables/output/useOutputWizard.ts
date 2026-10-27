import { computed, onMounted } from 'vue'
import { useOutputStore } from '@/stores/output'
import { useToast } from '@/composables/common/useToast'
import { OutputTrack } from '@/types'
import type { StepItem } from '@/types'

// ============================================================
// 步骤语义常量（避免魔法数字）
// ============================================================
export const STEP_DATASET_SELECT = 1
export const STEP_DIMENSION_FILTER = 2
export const STEP_EVALUATION = 3
export const STEP_ATTRIBUTION = 4
export const STEP_CORRECTION = 5
export const TRACK_STEP_START = 2
export const TRACK_STEP_END = 5

/**
 * 输出页向导导航逻辑。
 * 管理 5 步骤 + 双并行轨道（多样性/风险）的导航与面板显隐。
 * 导航为自由跳转模式：同轨跳步给出 toast 提醒但不阻止。
 */
export function useOutputWizard() {
  const store = useOutputStore()
  const toast = useToast()

  onMounted(async () => {
    // 1. 先加载已接通真实接口的模块（datasets / risk taxonomy）
    await Promise.all([store.loadOutputDatasets(), store.loadTaxonomyDimensions()])

    // 2. 再为尚无 API 的模块注入示例数据（diversity 维度 / 评估 / 归因 / 修正）
    //    真实接口模块绝不在此处灌 mock；接口失败时由 store 暴露的 error ref 告知 UI。
    store.initPlaceholderMockData()

    // 3. 尝试从 Cultural Gen BFF 加载真实多样性数据（评估样本 / 雷达 / 归因）
    //    不可达时自动保留 Step 2 注入的 Mock 数据
    await store.loadDiversityData()
  })

  // ============================================================
  // 步骤定义
  // ============================================================

  const diversityTrackSteps = computed<StepItem[]>(() => [
    { id: STEP_DIMENSION_FILTER, label: '治理标准体系', icon: '2' },
    { id: STEP_EVALUATION, label: '评估', icon: '3' },
    { id: STEP_ATTRIBUTION, label: '归因', icon: '4' },
    { id: STEP_CORRECTION, label: '修正', icon: '5' },
  ])

  const riskTrackSteps: StepItem[] = [
    { id: STEP_DIMENSION_FILTER, label: '治理标准体系', icon: '2' },
    { id: STEP_EVALUATION, label: '评估', icon: '3' },
    { id: STEP_ATTRIBUTION, label: '归因', icon: '4' },
    { id: STEP_CORRECTION, label: '修正', icon: '5' },
  ]

  // ============================================================
  // 当前状态
  // ============================================================

  const currentStep = computed(() => store.currentStep)
  const currentTrack = computed(() => store.currentTrack)
  const previousTrack = computed(() => store.previousTrack)

  // ============================================================
  // 面板显隐
  // ============================================================

  function isPanelActive(step: number, track?: OutputTrack): boolean {
    if (step === STEP_DATASET_SELECT) return store.currentStep === step
    const t = track ?? store.currentTrack ?? OutputTrack.DIVERSITY
    return store.currentStep === step && store.currentTrack === t
  }

  function isTrackInactive(track: OutputTrack): boolean {
    if (store.currentStep < TRACK_STEP_START || store.currentStep > TRACK_STEP_END) return false
    return store.currentTrack !== track
  }

  // ============================================================
  // 底层导航（仅内部使用，不对外暴露）
  // ============================================================

  function goToStep(step: number, track?: OutputTrack) {
    if (step < STEP_DATASET_SELECT || step > STEP_CORRECTION) return
    store.goToStep(step, track)
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }

  // ============================================================
  // 导航
  // ============================================================

  /** 步骤条自由导航：不阻止跳转，但同轨跳步时给出提醒 */
  function navigateToStep(targetStep: number, track?: OutputTrack) {
    if (targetStep === store.currentStep && (!track || track === store.currentTrack))
      return { valid: true }

    const activeTrack = track ?? store.currentTrack
    const isSameTrack = !track || track === store.currentTrack

    // 同轨前进跳步（跳超过 1 步）→ 提醒但不阻止
    if (isSameTrack && activeTrack && targetStep > store.currentStep + 1) {
      toast.info('建议按序操作', '请先完成当前步骤再进入后续环节')
    }

    goToStep(targetStep, track)
    return { valid: true }
  }

  // ============================================================
  // 上一步 / 下一步
  // ============================================================

  function goToPrevStep() {
    const step = store.currentStep
    if (step <= STEP_DATASET_SELECT) return
    const prev = step - 1
    const track =
      prev >= TRACK_STEP_START && prev <= TRACK_STEP_END
        ? (store.currentTrack ?? OutputTrack.DIVERSITY)
        : undefined
    goToStep(prev, track)
  }

  function goToNextStep() {
    const step = store.currentStep
    if (step >= STEP_CORRECTION) return

    // Step 1 gating: 需要先选择至少一个可进入轨道的数据资产
    if (step === STEP_DATASET_SELECT && store.selectedDatasets.length === 0) {
      toast.info(
        '请先选择可进入轨道的数据集',
        '当前已选列表为空。左侧标记为“可进入轨道”的风险或多样性数据可进入后续流程。',
      )
      return
    }

    const next = step + 1
    const track =
      next >= TRACK_STEP_START && next <= TRACK_STEP_END
        ? (store.currentTrack ?? OutputTrack.DIVERSITY)
        : undefined
    goToStep(next, track)
  }

  function finishOutput() {
    // TODO: 对接后端保存 API，持久化输出治理结果
  }

  // ============================================================
  // 对外暴露
  // ============================================================

  return {
    // 步骤定义
    diversityTrackSteps,
    riskTrackSteps,

    // 当前状态
    currentStep,
    currentTrack,
    previousTrack,

    // 面板显隐
    isPanelActive,
    isTrackInactive,

    // 导航
    navigateToStep,
    goToPrevStep,
    goToNextStep,
    finishOutput,
  }
}
