<template>
  <div class="benchmark-overview">
    <section class="overview-band">
      <div>
        <h2>当前展示状态</h2>
        <p>
          本页说明动态 Benchmark
          当前可演示的资产范围、来源状态和可信依据。当前系统已接入现场运行资产、 预跑快照、课题一
          value_qa 和课题三 risk 可信资产；所有资产以 manifest、SHA-256、来源
          commit、样本数和展示权限作为可信锚点。课题三风险内容分级分类资产以服务端登记的当前版本为准，
          版本、样本数与同版本模型评测结果在资产区展示；其他课题按交付状态展示待导入或已导入状态。
        </p>
        <div class="status-row">
          <span v-for="status in statusTags" :key="status">{{ status }}</span>
        </div>
      </div>
      <div class="overview-actions">
        <el-button type="primary" @click="$emit('start-agent-run', 'topic1-value-qa')">
          启动价值语料生成
        </el-button>
        <el-button type="primary" @click="$emit('start-agent-run', 'topic3-difficulty-generation')">
          启动动态难度出题
        </el-button>
        <el-button type="primary" @click="$emit('start-agent-run', 'topic2-autobench')">
          启动异常语料改写
        </el-button>
      </div>
    </section>

    <section class="trust-grid" aria-label="展示状态说明">
      <article v-for="item in trustStates" :key="item.title" class="trust-card">
        <span class="trust-card__tag">{{ item.tag }}</span>
        <h3>{{ item.title }}</h3>
        <p>{{ item.desc }}</p>
      </article>
    </section>

    <section class="notice-band">
      <strong>受控样本展示</strong>
      <span>
        风险样本全文仅在本地或受控环境查看；总览页展示统计摘要、来源口径和状态标识，默认不提供风险样本下载。
      </span>
    </section>

    <section class="overview-section">
      <h3>演示路径</h3>
      <div class="flow-grid">
        <article v-for="step in flowSteps" :key="step.title" class="flow-card">
          <div class="flow-card__index">{{ step.index }}</div>
          <div>
            <h4>{{ step.title }}</h4>
            <p>{{ step.desc }}</p>
          </div>
        </article>
      </div>
    </section>

    <section class="overview-section">
      <h3>动态性来源</h3>
      <div class="mechanism-grid">
        <article v-for="item in dynamicMechanisms" :key="item.title" class="mechanism-card">
          <span>{{ item.tag }}</span>
          <h4>{{ item.title }}</h4>
          <p>{{ item.desc }}</p>
        </article>
      </div>
    </section>

    <section class="overview-section">
      <h3>已接入资产概览</h3>
      <p class="section-intro">
        每个资产卡片都应能回答：来源是什么、样本数是多少、是否有 manifest 与
        SHA、能否下载、是否属于正式模型评测。
      </p>
      <div class="asset-summary-grid">
        <article v-for="asset in assetSummaries" :key="asset.title" class="asset-summary-card">
          <div>
            <h4>{{ asset.title }}</h4>
            <span class="status-pill" :class="asset.statusClass">{{ asset.status }}</span>
          </div>
          <p>{{ asset.desc }}</p>
        </article>
      </div>
    </section>

    <section class="overview-section">
      <h3>五类 Agent 能力矩阵</h3>
      <div class="agent-grid">
        <article v-for="agent in agents" :key="agent.name" class="agent-card">
          <div class="agent-card__header">
            <div>
              <h4>{{ agent.name }}</h4>
              <span>{{ agent.source }}</span>
            </div>
          </div>
          <dl class="agent-status-grid">
            <div>
              <dt>生成能力</dt>
              <dd>{{ agent.generation }}</dd>
            </div>
            <div>
              <dt>资产状态</dt>
              <dd>{{ agent.asset }}</dd>
            </div>
            <div>
              <dt>评测状态</dt>
              <dd>{{ agent.evaluation }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { BenchmarkAgentId } from '@/types'

defineEmits<{
  (event: 'start-agent-run', agentId: BenchmarkAgentId): void
}>()

const statusTags = ['现场运行', '预跑快照', '可信资产', '课题三评测已导入']

const trustStates = [
  {
    tag: '现场任务',
    title: '现场运行',
    desc: 'value_qa、异常语料改写与动态难度出题可触发小预算任务，完成后冻结为带日志、manifest 和 SHA 的 artifact。',
  },
  {
    tag: '预跑快照',
    title: '预跑资产',
    desc: 'simple / hard、value_qa、课题三四档风险资产以预跑或可信资产进入平台，承载样本摘要和来源状态。',
  },
  {
    tag: '证据锚点',
    title: '可信锚点',
    desc: '资产统一保留 manifest、SHA-256、source commit、样本数、来源模式和展示权限。',
  },
  {
    tag: '按状态展示',
    title: '评测状态',
    desc: '课题三风险内容资产按服务端登记的当前版本与同版本评测结果展示；其他正式模型评测结果按交付状态展示，未导入前不包装为正式跑分。',
  },
]

const flowSteps = [
  {
    index: '01',
    title: '选择任务',
    desc: '选择现场 live_run 或已导入预跑资产，明确本次演示对象和来源模式。',
  },
  {
    index: '02',
    title: '生成或导入',
    desc: 'live_run 走 Agent 现场运行；prerun_snapshot、topic3 risk 和既有 value_qa 预跑资产走资产导入。',
  },
  {
    index: '03',
    title: '质量检查',
    desc: '检查样本结构、覆盖分布、字段完整性、QA gate 或人工复判线索，缺失项保持真实空态。',
  },
  {
    index: '04',
    title: '冻结证据',
    desc: '将运行或导入结果冻结为带 manifest、source commit、SHA-256 和样本数的可信资产。',
  },
  {
    index: '05',
    title: '状态展示',
    desc: '展示样本摘要、质量状态、下载策略和正式评测导入状态，不把待导入结果包装成跑分。',
  },
]

const dynamicMechanisms = [
  {
    tag: 'freshness',
    title: '新样本生成',
    desc: '通过 SeedBank、时间切片或任务参数生成新样本，避免只展示固定题库。',
  },
  {
    tag: 'prompt loop',
    title: '生成策略迭代',
    desc: 'Agent 根据配置、质量反馈和评审意见组织下一轮生成策略，形成可追踪任务记录。',
  },
  {
    tag: 'coverage',
    title: '覆盖约束',
    desc: '按语言、风险类、难度层级或 safe / low / medium / high 分布检查覆盖，避免样本结构塌缩。',
  },
  {
    tag: 'difficulty',
    title: '结构复杂度',
    desc: 'simple / hard 或 H1-H4 用于组织样本结构和展示分层；正式模型表现差异等待评测结果导入。',
  },
]

const assetSummaries = [
  {
    title: '课题一 value_qa',
    status: '非正式评测',
    statusClass: 'is-valueqa',
    desc: '高 / 中 / 低三档回答对照资产已接入，可查看 preview；当前是语料资产与复判线索，模型评测结果待导入。',
  },
  {
    title: '课题二 simple / hard',
    status: '预跑快照',
    statusClass: 'is-prerun',
    desc: 'simple / hard 成对资产通过导入校验，展示配对血缘、difficulty basis 和 QA gate；正式评测以 evaluation_summary 导入状态为准。',
  },
  {
    title: '课题三风险内容',
    status: '按版本展示',
    statusClass: 'is-risk',
    desc: '四档风险等级与 C01-C17 分类体系由服务端当前版本提供；样本数、分布与同版本评测结果在资产区按所选版本展示。',
  },
  {
    title: 'live_run 资产',
    status: '现场任务产物',
    statusClass: 'is-live',
    desc: 'value_qa、异常语料改写、动态难度出题或文化多样性任务完成后，可冻结为现场运行资产。',
  },
]

const agents = [
  {
    name: '价值评测语料生成',
    source: '课题一',
    generation: 'live_run / 预跑',
    asset: 'value_qa 已导入，可冻结 live_run',
    evaluation: '正式评测待外部导入',
  },
  {
    name: '异常语料改写 Agent',
    source: '课题二 AutoBench',
    generation: 'live_run',
    asset: 'simple / hard 已导入',
    evaluation: 'Moderator 结果按导入状态展示',
  },
  {
    name: '风险内容生成',
    source: '课题三',
    generation: '预跑可信资产 / 试跑 live_run',
    asset: '四档风险资产按服务端当前版本展示；试跑 live_run 10 条',
    evaluation: '同版本评测结果按资产标识与内容哈希展示',
  },
  {
    name: '动态难度出题',
    source: '课题三',
    generation: 'live_run',
    asset: '可冻结 live_run 资产',
    evaluation: '合规编辑指标待对齐导入',
  },
  {
    name: '文化多样性生成',
    source: '课题三',
    generation: 'live_run / 预跑可信资产',
    asset: '文化多样性预跑资产已导入',
    evaluation: '文化感知准确率待外部导入',
  },
]
</script>

<style scoped>
.benchmark-overview {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.overview-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border: 1px solid #d9e6f4;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(21, 101, 192, 0.08), rgba(255, 255, 255, 0.96));
}

.overview-band h2,
.overview-section h3,
.flow-card h4,
.asset-summary-card h4,
.agent-card h4,
.mechanism-card h4 {
  margin: 0;
  color: var(--text-primary);
}

.overview-band p {
  margin: 8px 0 0;
  max-width: 880px;
  color: var(--text-secondary);
  line-height: 1.8;
  font-size: 14px;
}

.status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.status-row span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 800;
}

.overview-actions {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.notice-band {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  border: 1px solid rgba(251, 140, 0, 0.22);
  border-radius: 10px;
  background: rgba(251, 140, 0, 0.08);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.notice-band strong {
  flex: 0 0 auto;
  color: #9a5600;
}

.trust-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.trust-card {
  padding: 16px;
  border: 1px solid #dbe5f1;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(21, 101, 192, 0.06);
}

.trust-card__tag {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  margin-bottom: 10px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-size: 12px;
  font-weight: 800;
}

.trust-card h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
}

.trust-card p,
.section-intro {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 13px;
}

.overview-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.overview-section h3 {
  font-size: 18px;
}

.flow-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.flow-card,
.agent-card,
.asset-summary-card,
.mechanism-card {
  border: 1px solid #dbe5f1;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(21, 101, 192, 0.06);
}

.flow-card {
  display: flex;
  gap: 12px;
  padding: 16px;
}

.flow-card__index {
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(21, 101, 192, 0.1);
  color: var(--accent-blue);
  font-weight: 800;
}

.flow-card p,
.agent-card p,
.asset-summary-card p,
.mechanism-card p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 13px;
}

.mechanism-grid,
.asset-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.mechanism-card,
.asset-summary-card {
  padding: 16px;
}

.mechanism-card > span {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  margin-bottom: 10px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
  font-size: 12px;
  font-weight: 800;
}

.asset-summary-card > div {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.agent-card {
  padding: 18px;
}

.agent-card__header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.agent-card__header span {
  display: inline-flex;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.agent-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0 0;
}

.agent-status-grid div {
  min-width: 0;
  padding: 10px;
  border: 1px solid #dbe5f1;
  border-radius: 8px;
  background: #f8fbff;
}

.agent-status-grid dt {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}

.agent-status-grid dd {
  margin: 5px 0 0;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.status-pill.is-live {
  background: rgba(46, 125, 50, 0.12);
  color: var(--accent-green);
}

.status-pill.is-prerun {
  background: rgba(251, 140, 0, 0.12);
  color: #b86600;
}

.status-pill.is-risk {
  background: rgba(126, 87, 194, 0.12);
  color: #5e35b1;
}

.status-pill.is-valueqa {
  background: rgba(0, 121, 107, 0.12);
  color: #00796b;
}

@media (max-width: 1280px) {
  .flow-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .trust-grid,
  .mechanism-grid,
  .asset-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .overview-band,
  .notice-band {
    align-items: flex-start;
    flex-direction: column;
  }

  .overview-actions {
    justify-content: flex-start;
  }

  .flow-grid,
  .agent-grid,
  .agent-status-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .trust-grid,
  .mechanism-grid,
  .asset-summary-grid {
    grid-template-columns: 1fr;
  }

  .asset-summary-card > div {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
