<template>
  <section class="tool-execution" aria-label="语料处理任务">
    <header>
      <h3>语料处理任务</h3>
      <el-button :icon="Refresh" :disabled="busy" @click="refresh">刷新任务</el-button>
    </header>
    <div class="controls">
      <label>
        语料来源
        <el-select v-model="source">
          <el-option label="价值轨语料" value="value" />
          <el-option label="风险轨语料" value="risk" />
          <el-option label="自定义上传文档" value="upload" />
        </el-select>
      </label>
      <label>
        处理工具
        <el-select v-model="operation">
          <el-option
            v-for="item in corpusOperations"
            :key="item.key"
            :value="item.key"
            :label="item.label"
          />
        </el-select>
      </label>
      <label v-if="operation === 'score'">
        被测模型
        <el-select v-model="model" placeholder="选择已配置模型">
          <el-option
            v-for="item in models"
            :key="item.alias"
            :label="item.label"
            :value="item.alias"
          />
        </el-select>
      </label>
      <el-button
        type="primary"
        :icon="VideoPlay"
        :loading="busy"
        :disabled="!records.length || records.length > 500 || (operation === 'score' && !model)"
        @click="submit"
      >
        确认并执行
      </el-button>
    </div>
    <p>
      {{ sourceName }} · {{ records.length }} 条文本
      <span v-if="records.length > 500">（单次上限500条，不会自动截断）</span>
    </p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <small v-if="lastUpdated">任务状态更新于 {{ lastUpdated }}</small>
    <div class="task-filters">
      <el-input
        v-model="search"
        :prefix-icon="Search"
        clearable
        placeholder="搜索已加载任务的语料、工具或编号"
        aria-label="搜索任务"
      />
      <el-select v-model="statusFilter" clearable placeholder="全部状态" aria-label="任务状态">
        <el-option
          v-for="(label, status) in corpusJobStatus"
          :key="status"
          :value="status"
          :label="label"
        />
      </el-select>
      <small>已加载 {{ jobs.length }} 个任务 · 匹配 {{ filteredJobs.length }} 个</small>
    </div>
    <el-table
      :data="filteredJobs"
      :empty-text="jobs.length ? '已加载任务中暂无匹配项' : '暂无处理任务'"
      row-key="id"
    >
      <el-table-column prop="source_name" label="语料" min-width="150" />
      <el-table-column label="工具" min-width="110">
        <template #default="{ row }">
          {{ corpusOperations.find((item) => item.key === row.operation)?.label }}
        </template>
      </el-table-column>
      <el-table-column label="状态" min-width="130">
        <template #default="{ row }">
          {{ corpusJobStatus[row.status] || '未知状态' }}
          <small v-if="row.status === 'submission_unknown'">
            请联系管理员核对上游任务，勿重复提交。
          </small>
        </template>
      </el-table-column>
      <el-table-column prop="sample_count" label="文本数" width="85" />
      <el-table-column label="创建时间" min-width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="进度" width="140">
        <template #default="{ row }">
          <el-progress v-if="row.progress !== null" :percentage="row.progress" />
          <span v-else>等待进度</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190">
        <template #default="{ row }">
          <div class="actions">
            <el-button
              v-if="row.result_available"
              :icon="View"
              :disabled="busy"
              @click="showResult(row)"
            >
              结果
            </el-button>
            <el-button
              v-if="active(row) && row.status !== 'submitting'"
              :icon="Close"
              :disabled="busy"
              @click="cancel(row)"
            >
              取消
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <el-button v-if="hasMore" :disabled="busy" @click="loadMore">加载更早任务</el-button>
    <section v-if="result" class="result">
      <header>
        <h4>结果样例 · {{ result.job.source_name }}</h4>
        <el-button
          :icon="Close"
          :disabled="busy"
          aria-label="关闭结果"
          title="关闭结果"
          @click="result = null"
        />
      </header>
      <small>
        任务 {{ result.job.id }} ·
        {{ corpusOperations.find((item) => item.key === result?.job.operation)?.label }}
      </small>
      <div class="actions">
        <div v-for="asset in result.result.assets || []" :key="asset.key" class="actions">
          <el-button :icon="Download" :disabled="busy" @click="download(asset.key, asset.name)">
            下载 {{ asset.name }}
          </el-button>
          <el-tag v-if="asset.archived" type="success">已保存到平台</el-tag>
          <el-button
            v-else
            :icon="FolderChecked"
            :disabled="busy"
            @click="archive(asset.key, asset.name)"
          >
            保存到平台
          </el-button>
        </div>
      </div>
      <p>上游返回的预览样例，不是完整数据集；原语料未被覆盖，样本对应关系尚未核验。</p>
      <p v-if="result.job.tool === 'detection'">
        分数表示相对熟悉度与稀缺度，不证明是否参与训练；小样本结果仅供探索。
      </p>
      <dl v-for="(sample, index) in visibleSamples" :key="`${samplePage}-${index}`">
        <template v-for="(value, key) in sample" :key="key">
          <dt>{{ fieldLabels[key] || key }}</dt>
          <dd>{{ value }}</dd>
        </template>
      </dl>
      <p v-if="!result.result.samples.length">本次没有可展示的结果样例。</p>
      <el-pagination
        v-if="result.result.samples.length > samplePageSize"
        v-model:current-page="samplePage"
        :page-size="samplePageSize"
        :total="result.result.samples.length"
        layout="prev, pager, next"
        small
      />
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Refresh,
  VideoPlay,
  View,
  Close,
  Download,
  FolderChecked,
  Search,
} from '@element-plus/icons-vue'
import {
  corpusOperations,
  corpusJobStatus,
  useTopic1CorpusJobs,
} from '@/composables/data-input/useTopic1CorpusJobs'
const {
  source,
  operation,
  model,
  models,
  jobs,
  search,
  statusFilter,
  filteredJobs,
  result,
  busy,
  error,
  lastUpdated,
  hasMore,
  loadMore,
  records,
  sourceName,
  refresh,
  submit,
  cancel,
  showResult,
  download,
  archive,
  active,
} = useTopic1CorpusJobs()
const samplePage = ref(1)
const samplePageSize = 5
watch(result, () => {
  samplePage.value = 1
})
const visibleSamples = computed(
  () =>
    result.value?.result.samples.slice(
      (samplePage.value - 1) * samplePageSize,
      samplePage.value * samplePageSize,
    ) || [],
)
function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString()
}
const fieldLabels: Record<string, string> = {
  id: '样本标识',
  sample_id: '样本标识',
  text: '文本',
  raw_text: '原文',
  executed_text: '提质后文本',
  program: '处理程序',
  program_status: '处理状态',
  detoxified_texts: '去毒后文本',
  toxicity: '毒性评分',
  familiarity: '熟悉度',
  scarcity: '稀缺度',
  confidence_flag: '置信标记',
  familiarity_score: '熟悉度分数',
  scarcity_score: '稀缺度分数',
  scarcity_score_0_100: '稀缺度百分位',
  familiarity_percentile: '熟悉度百分位',
  scarcity_percentile: '稀缺度百分位',
  scarcity_label: '稀缺度标签',
  high_confidence_label: '高置信标签',
  method: '评估方法',
  raw_id_ex_toxicity: '显式毒性评分',
  raw_implicit_toxicity: '隐式毒性评分',
}
</script>

<style scoped>
.tool-execution {
  padding: 16px;
  border-top: 1px solid #e7edf4;
}
header,
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
header {
  justify-content: space-between;
  margin-bottom: 16px;
}
h3 {
  font-size: 15px;
  margin: 0;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: end;
}
label {
  display: grid;
  gap: 6px;
  width: 190px;
  font-size: 13px;
}
p,
small {
  color: #5c7188;
  font-size: 12px;
  line-height: 1.6;
}
small {
  display: block;
}
.actions .el-button + .el-button {
  margin-left: 0;
}
.result {
  margin-top: 20px;
}
.task-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin: 16px 0;
}
.task-filters .el-input {
  width: min(100%, 320px);
}
.task-filters .el-select {
  width: 160px;
}
dl {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr);
  gap: 8px;
  border-bottom: 1px solid #e7edf4;
  padding-bottom: 12px;
  font-size: 13px;
}
dd {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  label {
    width: 100%;
  }
  dl {
    grid-template-columns: 1fr;
  }
}
</style>
