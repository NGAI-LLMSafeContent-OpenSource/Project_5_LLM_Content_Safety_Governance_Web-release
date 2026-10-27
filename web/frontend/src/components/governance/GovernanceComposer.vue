<template>
  <form class="governance-composer" novalidate @submit.prevent="submit()">
    <div
      v-if="canStartNewGoal"
      id="governance-composer-context"
      class="governance-composer__context"
      :class="{ 'is-new-goal': !answeringClarification }"
      aria-live="polite"
    >
      <span class="governance-composer__context-label">
        <QuestionFilled v-if="answeringClarification" aria-hidden="true" />
        <CirclePlus v-else aria-hidden="true" />
        <span v-if="answeringClarification">
          正在回答：{{ clarificationQuestion || '治理助手提出的待补充问题' }}
        </span>
        <span v-else>准备开始新事项</span>
      </span>
      <button
        class="governance-composer__context-action"
        type="button"
        :disabled="blocked || busy || restoring"
        @click="toggleClarificationMode"
      >
        {{ answeringClarification ? '结束当前问题' : '继续回答当前问题' }}
      </button>
    </div>
    <label class="sr-only" for="governance-prompt">{{ domainLabel }}任务要求</label>
    <textarea
      id="governance-prompt"
      ref="textareaRef"
      class="governance-composer__input resize-none"
      :value="modelValue"
      :placeholder="composerPlaceholder"
      :disabled="blocked || busy || restoring"
      :aria-invalid="Boolean(error)"
      :aria-describedby="composerDescriptionIds"
      aria-keyshortcuts="Enter"
      rows="2"
      @input="handleInput"
      @keydown="handleKeydown"
    ></textarea>
    <div class="governance-composer__footer">
      <span id="governance-composer-status" :class="{ 'is-error': Boolean(error) }" role="status">
        {{
          error ||
          (blocked
            ? '浏览器无法保存客户端标识，暂不能创建可恢复会话。'
            : restoring
              ? '正在恢复治理会话…'
              : canStartNewGoal
                ? 'Enter 发送，Shift+Enter 换行。'
                : '请求将由治理助手按业务域执行受控治理能力。Enter 发送，Shift+Enter 换行。')
        }}
      </span>
      <button
        type="submit"
        :disabled="blocked || busy || restoring || !modelValue.trim()"
        :aria-busy="busy"
      >
        <Promotion aria-hidden="true" />
        <span>{{ busy ? '发送中' : '发送' }}</span>
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { CirclePlus, Promotion, QuestionFilled } from '@element-plus/icons-vue'
import { computed, nextTick, ref, watch } from 'vue'

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const props = defineProps<{
  modelValue: string
  domainLabel: string
  placeholder: string
  busy: boolean
  blocked: boolean
  restoring: boolean
  error: string
  canStartNewGoal: boolean
  clarificationPlanId?: string | null
  clarificationPlanVersion?: number | null
  clarificationQuestion?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'submit', continueClarification: boolean): void
}>()

const answeringClarification = ref(true)
const composerPlaceholder = computed(() =>
  props.canStartNewGoal && !answeringClarification.value ? '描述新的治理事项…' : props.placeholder,
)
const composerDescriptionIds = computed(() =>
  props.canStartNewGoal
    ? 'governance-composer-context governance-composer-status'
    : 'governance-composer-status',
)

watch(
  () => [props.clarificationPlanId, props.clarificationPlanVersion, props.canStartNewGoal],
  () => {
    answeringClarification.value = true
  },
)

function handleInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}

function submit(value?: string) {
  // Prefer the live textarea value: committing an IME candidate can deliver the
  // final input and the send gesture in the same turn, before `modelValue` has
  // propagated from the parent (#70). The parent already owns the newer text.
  const prompt = value ?? textareaRef.value?.value ?? props.modelValue
  if (props.restoring || props.blocked || props.busy || !prompt.trim()) return
  emit('submit', !props.canStartNewGoal || answeringClarification.value)
}

function toggleClarificationMode() {
  if (props.restoring || props.blocked || props.busy) return
  answeringClarification.value = !answeringClarification.value
  void nextTick(() => textareaRef.value?.focus())
}

function handleKeydown(event: KeyboardEvent) {
  // Chinese IMEs fire Enter while the candidate window is open. `isComposing`
  // covers modern browsers and `keyCode === 229` covers the process-key case
  // that some IMEs still emit (#70).
  if (event.isComposing || event.keyCode === 229) return
  if (event.key !== 'Enter') return
  // Shift+Enter keeps the newline; Enter and Ctrl/Cmd+Enter both send.
  const isSendShortcut = !event.shiftKey || event.ctrlKey || event.metaKey
  if (!isSendShortcut) return
  event.preventDefault()
  submit((event.target as HTMLTextAreaElement | null)?.value)
}
</script>
