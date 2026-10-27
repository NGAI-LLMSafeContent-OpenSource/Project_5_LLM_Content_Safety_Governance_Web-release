<template>
  <div class="rules-section">
    <div class="rules-header">
      <span class="rules-icon">📝</span>
      <span class="rules-title">自定义规则</span>
      <el-button size="small" :loading="loading" @click="loadActiveTaxonomy">
        从标准体系加载
      </el-button>
      <el-button size="small" type="primary" @click="openAddForm">新增规则</el-button>
    </div>

    <!-- 加载 / 错误状态 -->
    <div v-if="loading" class="rules-empty">加载标准体系中...</div>
    <div v-else-if="displayedRules.length === 0 && errorMsg" class="rules-empty">
      {{ errorMsg }}
      <el-button size="small" text type="primary" @click="loadActiveTaxonomy">重试</el-button>
    </div>
    <div v-else-if="displayedRules.length === 0" class="rules-empty">
      暂无自定义规则，点击「从标准体系加载」从 Benchmark 导入
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
            <div class="rule-field-label">大类定义</div>
            <div class="rule-field-value">{{ rule.definition || '（未填写）' }}</div>
          </div>
          <div v-if="rule.subcategories && rule.subcategories.length > 0" class="rule-field">
            <div class="rule-field-label">子类</div>
            <div class="rule-subs">
              <span v-for="sub in rule.subcategories" :key="sub.id" class="rule-sub-tag">
                {{ sub.name }}
              </span>
            </div>
          </div>
          <div v-if="rule.levels" class="rule-field">
            <div class="rule-field-label">四级定义</div>
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

    <!-- 新增规则弹窗 -->
    <el-dialog v-model="showAddForm" title="新增规则" width="560px" append-to-body destroy-on-close>
      <div class="add-rule-form">
        <label class="add-field">
          编号
          <el-input v-model="newRuleForm.id" placeholder="如 C18" size="small" />
        </label>
        <label class="add-field">
          大类名称
          <el-input v-model="newRuleForm.name" placeholder="新风险大类名称" size="small" />
        </label>
        <label class="add-field">
          大类定义
          <el-input
            v-model="newRuleForm.definition"
            type="textarea"
            rows="3"
            placeholder="大类定义描述"
          />
        </label>
        <div class="add-subsection">
          <div class="add-subsection-title">
            子类
            <el-button size="small" text @click="addSub">+ 新增子类</el-button>
          </div>
          <div v-for="(sub, i) in newRuleForm.subcategories" :key="i" class="add-sub-row">
            <el-input v-model="sub.name" size="small" placeholder="子类名称" />
            <el-button
              size="small"
              type="danger"
              text
              @click="newRuleForm.subcategories.splice(i, 1)"
            >
              删除
            </el-button>
          </div>
        </div>
        <div class="add-subsection">
          <div class="add-subsection-title">四级定义</div>
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
import { ref, reactive } from 'vue'
import { useOutputStore } from '@/stores/output'
import { fetchRiskTaxonomies } from '@/api/output'

const store = useOutputStore()

interface Subcategory {
  id: string
  name: string
}

interface Rule {
  id: string
  name: string
  definition: string
  subcategories: Subcategory[]
  levels: Record<string, string>
}

const levelList = [
  { key: 'safe', label: '安全' },
  { key: 'low', label: '低风险' },
  { key: 'medium', label: '中风险' },
  { key: 'high', label: '高风险' },
]

const displayedRules = ref<Rule[]>([])
const expandedId = ref<string | null>(null)
const loading = ref(false)
const errorMsg = ref('')

const showAddForm = ref(false)
const newRuleForm = reactive({
  id: '',
  name: '',
  definition: '',
  subcategories: [] as Subcategory[],
  levels: Object.fromEntries(levelList.map((lv) => [lv.key, ''])),
})

function openAddForm() {
  newRuleForm.id = ''
  newRuleForm.name = ''
  newRuleForm.definition = ''
  newRuleForm.subcategories = []
  newRuleForm.levels = Object.fromEntries(levelList.map((lv) => [lv.key, '']))
  showAddForm.value = true
}

function addSub() {
  const idx = newRuleForm.subcategories.length + 1
  newRuleForm.subcategories.push({ id: `S${idx}`, name: '' })
}

function confirmAddRule() {
  const id = newRuleForm.id.trim() || `CUSTOM-${Date.now()}`
  const name = newRuleForm.name.trim() || '未命名规则'
  displayedRules.value.push({
    id,
    name,
    definition: newRuleForm.definition.trim(),
    subcategories: newRuleForm.subcategories.filter((s) => s.name.trim()),
    levels: { ...newRuleForm.levels },
  })
  store.addCustomRiskRule(id)
  errorMsg.value = ''
  showAddForm.value = false
}

function toggleRule(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function removeRule(id: string) {
  displayedRules.value = displayedRules.value.filter((r) => r.id !== id)
  store.removeCustomRiskRule(id)
}

async function loadActiveTaxonomy() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await fetchRiskTaxonomies()
    const categories =
      (data as unknown as { categories?: Array<Record<string, unknown>> })?.categories || []
    if (categories.length === 0) {
      errorMsg.value = '标准体系中无分类数据'
      return
    }
    // 按前 3 条模板追加到已有规则（已存在的 id 跳过）
    const preset = categories.slice(0, 3).map((cat) => ({
      id: cat.key || cat.id,
      name: cat.label || cat.name,
      definition: (cat.definition as string) || '',
      subcategories: ((cat.subcategories || []) as Array<Record<string, unknown>>).map((s) => ({
        id: s.key || s.id,
        name: s.label || s.name,
      })),
      levels: (cat.levels as Record<string, string>) || {},
    }))
    const existing = new Set(displayedRules.value.map((r) => r.id))
    for (const p of preset) {
      if (!existing.has(p.id as string)) {
        displayedRules.value.push(p as unknown as Rule)
      }
    }
  } catch {
    errorMsg.value = '无法连接标准体系服务，请检查后端是否启动'
  } finally {
    loading.value = false
  }
}
</script>

<style src="./TaxonomyRuleBuilder.css" scoped></style>
