<template>
  <div class="rules-section">
    <div class="rules-header">
      <span class="rules-icon">📝</span>
      <span class="rules-title">自定义规则</span>
      <el-button size="small" @click="loadStandardTemplates">从标准体系加载</el-button>
      <el-button size="small" type="primary" @click="openAddForm">新增规则</el-button>
    </div>

    <div v-if="displayedRules.length === 0" class="rules-empty">
      暂无自定义规则，点击「从标准体系加载」导入文化多样性标准模板
    </div>

    <template v-else>
      <div v-for="rule in displayedRules" :key="rule.id" class="rule-card">
        <div class="rule-summary" @click="toggleRule(rule.id)">
          <span class="rule-code">{{ rule.id }}</span>
          <span class="rule-name">{{ rule.name }}</span>
          <span class="rule-arrow">{{ expandedId === rule.id ? '▾' : '▸' }}</span>
        </div>
        <div v-if="expandedId === rule.id" class="rule-detail">
          <div class="rule-field">
            <div class="rule-field-label">标准定义</div>
            <div class="rule-field-value">{{ rule.definition || '（未填写）' }}</div>
          </div>
          <div v-if="rule.criteria.length > 0" class="rule-field">
            <div class="rule-field-label">判定要点</div>
            <div class="rule-subs">
              <span v-for="criterion in rule.criteria" :key="criterion.id" class="rule-sub-tag">
                {{ criterion.name }}
              </span>
            </div>
          </div>
          <div v-if="rule.levels" class="rule-field">
            <div class="rule-field-label">评分定义</div>
            <div class="rule-levels">
              <div v-for="lv in levelList" :key="lv.key" class="rule-level-row">
                <span class="rule-level-key">{{ lv.label }}</span>
                <span class="rule-level-val">{{ rule.levels[lv.key] || '—' }}</span>
              </div>
            </div>
          </div>
          <el-button size="small" type="danger" text @click="removeRule(rule.id)">
            删除此规则
          </el-button>
        </div>
      </div>
    </template>

    <el-dialog v-model="showAddForm" title="新增规则" width="560px" append-to-body destroy-on-close>
      <div class="add-rule-form">
        <label class="add-field">
          编号
          <el-input v-model="newRuleForm.id" placeholder="如 CD-03" size="small" />
        </label>
        <label class="add-field">
          标准名称
          <el-input v-model="newRuleForm.name" placeholder="新文化多样性标准名称" size="small" />
        </label>
        <label class="add-field">
          标准定义
          <el-input
            v-model="newRuleForm.definition"
            type="textarea"
            rows="3"
            placeholder="标准定义描述"
          />
        </label>
        <div class="add-subsection">
          <div class="add-subsection-title">
            判定要点
            <el-button size="small" text @click="addCriterion">+ 新增要点</el-button>
          </div>
          <div v-for="(criterion, i) in newRuleForm.criteria" :key="i" class="add-sub-row">
            <el-input v-model="criterion.name" size="small" placeholder="判定要点" />
            <el-button size="small" type="danger" text @click="newRuleForm.criteria.splice(i, 1)">
              删除
            </el-button>
          </div>
        </div>
        <div class="add-subsection">
          <div class="add-subsection-title">评分定义</div>
          <div v-for="lv in levelList" :key="lv.key" class="add-level-row">
            <span class="add-level-label">{{ lv.label }}</span>
            <el-input v-model="newRuleForm.levels[lv.key]" size="small" placeholder="定义描述" />
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showAddForm = false">取消</el-button>
        <el-button type="primary" @click="confirmAddRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useOutputStore } from '@/stores/output'
import { diversityStandards } from './diversityStandards'

const store = useOutputStore()

interface Criterion {
  id: string
  name: string
}

interface DiversityRule {
  id: string
  name: string
  definition: string
  criteria: Criterion[]
  levels: Record<string, string>
}

const levelList = [
  { key: 'excellent', label: '优秀' },
  { key: 'good', label: '达标' },
  { key: 'weak', label: '不足' },
]

const standardTemplates: DiversityRule[] = diversityStandards.map((standard) => ({
  id: standard.code,
  name: standard.label,
  definition: standard.definition,
  criteria: standard.criteria.map((criterion) => ({ ...criterion })),
  levels: { ...standard.levels },
}))

const displayedRules = ref<DiversityRule[]>([])
const expandedId = ref<string | null>(null)
const showAddForm = ref(false)
const newRuleForm = reactive({
  id: '',
  name: '',
  definition: '',
  criteria: [] as Criterion[],
  levels: Object.fromEntries(levelList.map((lv) => [lv.key, ''])),
})

function openAddForm() {
  newRuleForm.id = ''
  newRuleForm.name = ''
  newRuleForm.definition = ''
  newRuleForm.criteria = []
  newRuleForm.levels = Object.fromEntries(levelList.map((lv) => [lv.key, '']))
  showAddForm.value = true
}

function addCriterion() {
  const idx = newRuleForm.criteria.length + 1
  newRuleForm.criteria.push({ id: `P${idx}`, name: '' })
}

function confirmAddRule() {
  const id = newRuleForm.id.trim() || `CD-CUSTOM-${Date.now()}`
  const name = newRuleForm.name.trim() || '未命名规则'
  displayedRules.value.push({
    id,
    name,
    definition: newRuleForm.definition.trim(),
    criteria: newRuleForm.criteria.filter((criterion) => criterion.name.trim()),
    levels: { ...newRuleForm.levels },
  })
  store.addCustomDiversityRule(id)
  showAddForm.value = false
}

function toggleRule(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function removeRule(id: string) {
  displayedRules.value = displayedRules.value.filter((rule) => rule.id !== id)
  store.removeCustomDiversityRule(id)
}

function loadStandardTemplates() {
  const existing = new Set(displayedRules.value.map((rule) => rule.id))
  for (const template of standardTemplates) {
    if (!existing.has(template.id)) {
      displayedRules.value.push({
        ...template,
        criteria: template.criteria.map((criterion) => ({ ...criterion })),
        levels: { ...template.levels },
      })
      store.addCustomDiversityRule(template.id)
    }
  }
}
</script>

<style src="../step1-dataset/TaxonomyRuleBuilder.css" scoped></style>
