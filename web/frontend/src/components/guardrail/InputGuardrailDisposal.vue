<template>
  <section class="guardrail-section" aria-labelledby="guardrail-disposal-title">
    <header class="guardrail-section__header">
      <p class="guardrail-section__label">04</p>
      <h2 id="guardrail-disposal-title">修正与复核清单</h2>
      <p class="guardrail-section__desc">汇总本次未放行语料的后续处置动作。</p>
    </header>

    <p v-if="!disposalItems.length" class="detect-empty">运行后显示本批处置建议</p>

    <el-table v-else class="disposal-table" :data="disposalItems" border size="small">
      <el-table-column prop="id" label="ID" width="190" show-overflow-tooltip />
      <el-table-column prop="category" label="类型" width="150" show-overflow-tooltip />
      <el-table-column label="处置" width="96">
        <template #default="{ row }">
          <el-tag :type="dispositionTagType(row.disposition)" size="small">
            {{ row.disposition }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="problemSummary"
        label="问题摘要"
        min-width="230"
        show-overflow-tooltip
      />
      <el-table-column prop="suggestion" label="建议动作" min-width="260" show-overflow-tooltip />
      <el-table-column label="当前状态" width="120">
        <template #default="{ row }">
          <el-tag type="info" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FixItem } from '@/composables/guardrail/inputGuardrailDemoMap'

const props = defineProps<{
  valueFixItems: FixItem[]
  riskFixItems: FixItem[]
}>()

const disposalItems = computed(() => [...props.valueFixItems, ...props.riskFixItems])

function dispositionTagType(disposition?: string) {
  if (disposition === 'review') return 'warning'
  if (disposition === 'revise') return 'danger'
  if (disposition === 'pass') return 'success'
  return 'info'
}
</script>

<style scoped>
.guardrail-section {
  padding: 22px;
  border: 1px solid #dbe6f3;
  border-radius: 8px;
  background: #fff;
  scroll-margin-top: 24px;
}

.guardrail-section__header {
  margin-bottom: 14px;
}

.guardrail-section__label {
  margin: 0 0 10px;
  color: #1565c0;
  font-size: 13px;
  font-weight: 700;
}

.guardrail-section h2 {
  margin: 0 0 8px;
  color: #102a43;
  font-size: 20px;
  line-height: 1.35;
}

.guardrail-section__desc {
  margin: 0;
  color: #52677f;
  font-size: 14px;
  line-height: 1.7;
}

.detect-empty {
  margin: 0;
  color: #5b7088;
  font-size: 14px;
  line-height: 1.6;
}

.disposal-table {
  width: 100%;
}
</style>
