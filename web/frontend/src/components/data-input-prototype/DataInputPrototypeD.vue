<template>
  <section class="dip-variant dip-assistant" aria-labelledby="dip-d-title">
    <header class="dip-assistant__hero">
      <div class="dip-assistant__mark" aria-hidden="true"><Compass /></div>
      <div>
        <p class="dip-eyebrow">输入治理助手</p>
        <h1 id="dip-d-title">告诉我你想查看或检测什么</h1>
        <p>我可以帮你查看价值语料，或使用在线服务复核风险语料。</p>
      </div>
      <div class="dip-assistant__scope">
        <span>当前可使用</span>
        <strong>74 组价值问题</strong>
        <strong>400 条风险样本</strong>
      </div>
    </header>

    <div class="dip-assistant__canvas">
      <form class="dip-command" novalidate @submit.prevent="submitCommand()">
        <label for="dip-assistant-input">输入你的问题或操作</label>
        <div class="dip-command__field">
          <Search aria-hidden="true" />
          <input
            id="dip-assistant-input"
            ref="commandInput"
            v-model="command"
            type="text"
            autocomplete="off"
            placeholder="例如：查找文化忠实度相关问题组"
            @compositionstart="isComposing = true"
            @compositionend="isComposing = false"
          />
          <button
            type="submit"
            class="dip-primary-button"
            :disabled="!command.trim() || isComposing"
          >
            <Position />
            发送
          </button>
        </div>
      </form>

      <div v-if="history.length === 0" class="dip-quick-start" aria-label="示例问题">
        <button
          v-for="prompt in quickPrompts"
          :key="prompt"
          type="button"
          @click="submitCommand(prompt)"
        >
          <span>{{ prompt }}</span>
          <ArrowRight />
        </button>
      </div>

      <div v-else class="dip-conversation" aria-live="polite">
        <article
          v-for="(message, index) in history"
          :key="`${message.role}-${index}`"
          :class="`is-${message.role}`"
        >
          <span>{{ message.role === 'user' ? '你' : '助手' }}</span>
          <p>{{ message.text }}</p>
        </article>
      </div>

      <div
        v-if="pendingDetection"
        class="dip-confirmation dip-confirmation--assistant"
        role="status"
      >
        <div>
          <span>将使用：风险语料</span>
          <strong>确认运行二次校验</strong>
          <p>
            将检测当前结果前
            {{ assistantRiskTargets.length }} 条。参考标注不会被修改，检测结果仅供当前会话查看。
          </p>
        </div>
        <div>
          <button type="button" class="dip-secondary-button" @click="cancelDetection">取消</button>
          <button type="button" class="dip-primary-button" @click="confirmDetection">
            <VideoPlay />
            开始检测
          </button>
        </div>
      </div>

      <section v-if="panel === 'value-overview'" class="dip-answer-panel">
        <header>
          <span>来自已有资产</span>
          <h2>价值判别评测集</h2>
        </header>
        <div class="dip-fact-grid">
          <div>
            <strong>74</strong>
            <span>个问题组</span>
          </div>
          <div>
            <strong>222</strong>
            <span>条对照回答</span>
          </div>
          <div>
            <strong>3</strong>
            <span>档回答 / 每组</span>
          </div>
        </div>
        <p>每组包含高、中、低价值回答，用于检验模型能否识别价值档位，而不是等待人工修改的数据。</p>
      </section>

      <section v-else-if="panel === 'value-list'" class="dip-answer-panel">
        <header>
          <span>来自已有资产</span>
          <h2>找到 {{ assistantValueGroups.length }} 个代表问题组</h2>
        </header>
        <div class="dip-assistant-list">
          <button
            v-for="(group, index) in assistantValueGroups"
            :key="group.id"
            type="button"
            @click="openValueGroup(index)"
          >
            <span>{{ index + 1 }}</span>
            <div>
              <strong>{{ group.answers.high.question }}</strong>
              <small>{{ group.topic }} · {{ group.secondaryDimension }}</small>
            </div>
            <ArrowRight />
          </button>
        </div>
      </section>

      <ValueGroupDetail
        v-else-if="panel === 'value-detail' && activeAssistantValueGroup"
        :group="activeAssistantValueGroup"
        :evidence-open="valueEvidenceOpen"
      />

      <section v-else-if="panel === 'risk-overview'" class="dip-answer-panel">
        <header>
          <span>来自已有资产</span>
          <h2>课题二 DynBench400 风险语料</h2>
        </header>
        <div class="dip-fact-grid">
          <div>
            <strong>400</strong>
            <span>条风险样本</span>
          </div>
          <div>
            <strong>30</strong>
            <span>条 / 单次检测上限</span>
          </div>
          <div>
            <strong>2</strong>
            <span>套结果并排核对</span>
          </div>
        </div>
        <p>可以查看已有参考标注和来源信息，并通过课题二在线服务进行小批量二次校验。</p>
      </section>

      <section v-else-if="panel === 'risk-list'" class="dip-answer-panel">
        <header>
          <span>来自已有资产</span>
          <h2>找到 {{ assistantRiskTargets.length }} 条代表样本</h2>
        </header>
        <div class="dip-table-frame">
          <table>
            <thead>
              <tr>
                <th scope="col">样本文本</th>
                <th scope="col">参考标注</th>
                <th scope="col">风险分类</th>
                <th scope="col">来源</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="sample in assistantRiskTargets" :key="sample.id">
                <td>
                  <strong>{{ sample.text }}</strong>
                  <small>{{ sample.id }}</small>
                </td>
                <td>
                  <span class="dip-label" :class="`is-${sample.referenceLabel}`">
                    {{ riskLabelLabels[sample.referenceLabel] }}
                  </span>
                </td>
                <td>
                  {{ sample.l1 }}
                  <small>{{ sample.l2 }}</small>
                </td>
                <td>{{ sample.source }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <RiskResultsTable
        v-else-if="panel === 'risk-results' && assistantDetectionRows.length"
        :key="resultFilter"
        :rows="assistantDetectionRows"
        :initial-filter="resultFilter"
      />

      <section v-else-if="panel === 'boundary'" class="dip-boundary">
        <CircleCloseFilled />
        <div>
          <strong>{{ boundaryTitle }}</strong>
          <p>{{ boundaryDetail }}</p>
        </div>
      </section>

      <div v-if="history.length" class="dip-session-note">
        <Clock />
        当前筛选、打开的问题组和检测演示结果只保留在本次页面会话中。
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import {
  ArrowRight,
  CircleCloseFilled,
  Clock,
  Compass,
  Position,
  Search,
  VideoPlay,
} from '@element-plus/icons-vue'
import RiskResultsTable from './RiskResultsTable.vue'
import ValueGroupDetail from './ValueGroupDetail.vue'
import type { DetectionState, RiskDetectionRow, RiskSample, ValueGroup } from './prototypeData'
import { buildDemoDetectionRows, riskLabelLabels, riskSamples, valueGroups } from './prototypeData'

type Panel =
  | 'none'
  | 'value-overview'
  | 'value-list'
  | 'value-detail'
  | 'risk-overview'
  | 'risk-list'
  | 'risk-results'
  | 'boundary'

interface ConversationMessage {
  role: 'user' | 'assistant'
  text: string
}

const quickPrompts = [
  '这套价值语料是怎么构成的？',
  '比较一组高 / 中 / 低回答',
  '查看风险语料的参考标注',
  '检测风险语料前 30 条',
]

const command = ref('')
const isComposing = ref(false)
const commandInput = ref<HTMLInputElement | null>(null)
const history = ref<ConversationMessage[]>([])
const panel = ref<Panel>('none')
const assistantValueGroups = ref<ValueGroup[]>(valueGroups)
const activeAssistantValueIndex = ref(0)
const valueEvidenceOpen = ref(false)
const assistantRiskTargets = ref<RiskSample[]>(riskSamples)
const assistantDetectionRows = ref<RiskDetectionRow[]>([])
const pendingDetection = ref(false)
const resultFilter = ref<DetectionState | 'all'>('all')
const boundaryTitle = ref('当前请求不在原型能力范围内')
const boundaryDetail = ref('你可以查看价值问题组，或筛选风险样本并运行小批量检测。')

const activeAssistantValueGroup = computed(
  () => assistantValueGroups.value[activeAssistantValueIndex.value],
)

function addExchange(userText: string, assistantText: string) {
  history.value.push({ role: 'user', text: userText }, { role: 'assistant', text: assistantText })
}

function submitCommand(provided?: string) {
  if (isComposing.value) return
  const text = (provided ?? command.value).trim()
  if (!text) return
  command.value = ''
  pendingDetection.value = false
  routeCommand(text)
  void nextTick(() => commandInput.value?.focus())
}

function routeCommand(text: string) {
  const normalized = text.replaceAll(' ', '').toLocaleLowerCase('zh-CN')

  if (containsAny(normalized, ['上传', '修改', '生成新', '导出', '全量检测', '全部400'])) {
    showBoundary(
      text,
      '当前不能执行这项操作',
      normalized.includes('全量') || normalized.includes('全部400')
        ? '在线检测单次最多支持 30 条。你可以先缩小范围，或检测当前结果的前 30 条。'
        : '当前只支持查看课题一价值语料，以及查询和小批量复核课题二风险语料。',
    )
    return
  }

  if (containsAny(normalized, ['下一组', '上一组'])) {
    if (panel.value !== 'value-detail') {
      showBoundary(text, '还没有打开价值问题组', '可以先输入“比较一组高 / 中 / 低回答”。')
      return
    }
    const offset = normalized.includes('下一组') ? 1 : -1
    activeAssistantValueIndex.value =
      (activeAssistantValueIndex.value + offset + assistantValueGroups.value.length) %
      assistantValueGroups.value.length
    valueEvidenceOpen.value = false
    panel.value = 'value-detail'
    addExchange(text, `已打开${normalized.includes('下一组') ? '下一组' : '上一组'}价值问题。`)
    return
  }

  const groupNumber = readOrdinal(normalized, '组')
  if (groupNumber !== null && containsAny(normalized, ['打开', '查看', '第'])) {
    if (groupNumber < 1 || groupNumber > assistantValueGroups.value.length) {
      showBoundary(
        text,
        '没有找到这个问题组',
        `当前结果共有 ${assistantValueGroups.value.length} 个代表问题组，可以打开第 1 至 ${assistantValueGroups.value.length} 组。`,
      )
      return
    }
    openValueGroup(groupNumber - 1, text)
    return
  }

  if (
    containsAny(normalized, ['样本依据', '来源依据', '证据片段']) &&
    panel.value === 'value-detail'
  ) {
    valueEvidenceOpen.value = true
    addExchange(text, '已展开当前问题组的来源信息与样本依据。')
    return
  }

  if (containsAny(normalized, ['不一致', '检测失败', '一致结果'])) {
    if (!assistantDetectionRows.value.length) {
      showBoundary(text, '当前还没有检测结果', '可以先输入“检测风险语料前 30 条”。')
      return
    }
    resultFilter.value = normalized.includes('不一致')
      ? 'mismatch'
      : normalized.includes('失败')
        ? 'failed'
        : 'match'
    panel.value = 'risk-results'
    addExchange(text, `已按“${resultFilterLabel(resultFilter.value)}”筛选本次检测结果。`)
    return
  }

  if (containsAny(normalized, ['检测', '校验', '复核'])) {
    assistantRiskTargets.value = filterRiskSamples(normalized)
    pendingDetection.value = true
    panel.value = 'risk-list'
    addExchange(
      text,
      `已识别为风险语料二次校验，将使用当前结果前 ${assistantRiskTargets.value.length} 条，请确认后开始检测。`,
    )
    return
  }

  if (containsAny(normalized, ['风险', '参考标注', '不安全', '安全样本', 'l1', 'l2'])) {
    assistantRiskTargets.value = filterRiskSamples(normalized)
    panel.value = normalized.includes('构成') ? 'risk-overview' : 'risk-list'
    addExchange(
      text,
      panel.value === 'risk-overview'
        ? '已打开风险语料构成说明。'
        : `已从风险语料中找到 ${assistantRiskTargets.value.length} 条代表样本。`,
    )
    return
  }

  if (containsAny(normalized, ['构成', '多少组', '多少条']) && normalized.includes('价值')) {
    panel.value = 'value-overview'
    addExchange(text, '已打开价值判别评测集的构成说明。')
    return
  }

  if (containsAny(normalized, ['价值', '高中低', '高/中/低', '文化忠实', '伦理合规', '问题组'])) {
    assistantValueGroups.value = filterValueGroups(normalized)
    activeAssistantValueIndex.value = 0
    if (containsAny(normalized, ['比较', '对比', '回答', '一组'])) {
      panel.value = 'value-detail'
      addExchange(text, '已打开一个价值问题组，下面按高、中、低三档展示已有回答。')
    } else {
      panel.value = 'value-list'
      addExchange(text, `已找到 ${assistantValueGroups.value.length} 个代表问题组。`)
    }
    return
  }

  showBoundary(
    text,
    '暂时无法识别这个请求',
    '当前原型支持查看价值评测集、比较高 / 中 / 低回答、筛选风险样本，以及检测风险语料前 30 条。',
  )
}

function openValueGroup(index: number, originalText?: string) {
  activeAssistantValueIndex.value = index
  valueEvidenceOpen.value = false
  panel.value = 'value-detail'
  addExchange(originalText ?? `打开第 ${index + 1} 组`, `已打开第 ${index + 1} 个价值问题组。`)
}

function confirmDetection() {
  assistantDetectionRows.value = buildDemoDetectionRows(assistantRiskTargets.value)
  pendingDetection.value = false
  resultFilter.value = 'all'
  panel.value = 'risk-results'
  history.value.push({
    role: 'assistant',
    text: `检测演示已完成：${assistantDetectionRows.value.length} 条结果可供核对。`,
  })
}

function cancelDetection() {
  pendingDetection.value = false
  history.value.push({ role: 'assistant', text: '已取消本次检测，没有产生检测结果。' })
}

function showBoundary(userText: string, title: string, detail: string) {
  boundaryTitle.value = title
  boundaryDetail.value = detail
  panel.value = 'boundary'
  addExchange(userText, detail)
}

function filterValueGroups(normalized: string) {
  if (normalized.includes('中秋')) return valueGroups.filter((group) => group.topic === '中秋节')
  if (normalized.includes('端午')) return valueGroups.filter((group) => group.topic === '端午节')
  if (normalized.includes('行为') || normalized.includes('规范')) {
    return valueGroups.filter((group) => group.secondaryDimension.includes('行为'))
  }
  return valueGroups
}

function filterRiskSamples(normalized: string) {
  let samples = riskSamples
  if (normalized.includes('不安全'))
    samples = samples.filter((sample) => sample.referenceLabel === 'unsafe')
  else if (normalized.includes('安全样本'))
    samples = samples.filter((sample) => sample.referenceLabel === 'safe')
  if (normalized.includes('l1-3') || normalized.includes('偏见')) {
    samples = samples.filter((sample) => sample.l1.includes('L1-3'))
  }
  return samples.slice(0, 30)
}

function containsAny(text: string, terms: string[]) {
  return terms.some((term) => text.includes(term))
}

function readOrdinal(text: string, unit: string) {
  const match = text.match(new RegExp(`第?(\\d+)${unit}`))
  return match ? Number.parseInt(match[1], 10) : null
}

function resultFilterLabel(value: DetectionState | 'all') {
  return { all: '全部', match: '一致', mismatch: '不一致', failed: '检测失败' }[value]
}
</script>
