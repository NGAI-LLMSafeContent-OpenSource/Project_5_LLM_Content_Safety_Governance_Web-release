<template>
  <main class="main-content">
    <div id="page-home" class="page active">
      <DashboardStats :items="dashboardStats" />

      <section class="home-section">
        <h2 class="section-title">数据分类统计</h2>
        <div class="module-grid module-grid--two-columns">
          <article
            v-for="category in categories"
            :key="category.id"
            class="module-card"
            :class="category.theme"
          >
            <div class="module-card__header">
              <div class="module-card-icon module-card-icon--compact">{{ category.icon }}</div>
              <div>
                <div class="module-card-title">{{ category.title }}</div>
                <div class="module-card-desc">{{ category.desc }}</div>
                <div class="category-card__meta">
                  <div>
                    <span class="category-card__value">{{ category.datasets }}</span>
                    <span class="category-card__label">数据集</span>
                  </div>
                  <div>
                    <span class="category-card__value">{{ category.score }}</span>
                    <span class="category-card__label">平均评分</span>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="home-section">
        <h2 class="section-title">核心功能模块</h2>
        <div class="module-grid">
          <router-link to="/definition" class="module-card blue">
            <div class="module-card-icon">📋</div>
            <div class="module-card-title">治理标准体系</div>
            <div class="module-card-desc">
              基于政策规范和行业标准，构建输入语料价值/风险与输出内容风险、文化多样性等多维指标体系
            </div>
            <div class="module-card-tags">
              <span class="module-tag">输入语料（价值）</span
              ><span class="module-tag">输入/输出风险</span
              ><span class="module-tag">多Agent挖掘</span>
            </div>
          </router-link>
          <router-link to="/data-input" class="module-card blue">
            <div class="module-card-icon">📥</div>
            <div class="module-card-title">输入语料治理</div>
            <div class="module-card-desc">
              训练语料构建 → 血缘图谱生成 → 价值/风险并行：标准体系筛选、评估、归因、修正
            </div>
            <div class="module-card-tags">
              <span class="module-tag">血缘图谱</span><span class="module-tag">标准体系筛选</span
              ><span class="module-tag">评估与修正</span>
            </div>
          </router-link>
          <router-link to="/output" class="module-card purple">
            <div class="module-card-icon">📤</div>
            <div class="module-card-title">输出内容治理</div>
            <div class="module-card-desc">
              模型推理评估与归因分析，输出综合安全报告与后训练策略建议
            </div>
            <div class="module-card-tags">
              <span class="module-tag">LLM评估</span><span class="module-tag">归因分析</span
              ><span class="module-tag">策略建议</span>
            </div>
          </router-link>
        </div>
      </section>

      <section class="home-section">
        <h2 class="section-title">近期活动</h2>
        <div class="timeline home-timeline">
          <article
            v-for="activity in activities"
            :key="activity.id"
            class="timeline-item"
            :class="activity.ok ? 'success' : ''"
          >
            <div class="timeline-time">{{ activity.time }}</div>
            <div class="timeline-title">{{ activity.title }}</div>
            <div class="timeline-desc">{{ activity.desc }}</div>
          </article>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import type { StatItem } from '@/components/home/DashboardStats.vue'

const dashboardStats: StatItem[] = [
  {
    id: 'metric-definitions',
    title: '已定义指标体系',
    icon: '📊',
    value: 156,
    change: 12,
    unit: '%',
    trend: 'up',
  },
  {
    id: 'processed-datasets',
    title: '已处理数据集',
    icon: '📁',
    value: 2384,
    change: 8,
    unit: '%',
    trend: 'up',
  },
  {
    id: 'risk-samples',
    title: '风险样本识别',
    icon: '⚠️',
    value: 1267,
    change: 5,
    unit: '%',
    trend: 'down',
  },
  {
    id: 'safety-score',
    title: '模型安全评分',
    icon: '🎯',
    value: '87.6',
    change: 3.2,
    unit: '',
    trend: 'up',
  },
]

const categories = [
  {
    id: 'ethnic-language-diversity',
    title: '多民族语言文化多样性',
    desc: '涵盖56个民族的语言文字、传统文化、民俗风情等数据资产',
    icon: '🌍',
    theme: 'blue',
    border: 'var(--accent-blue)',
    datasets: 1284,
    score: 89.2,
  },
  {
    id: 'ai-for-science',
    title: 'AI for Science',
    desc: '涵盖科研数据、学术论文、实验记录、科学知识库等数据资产',
    icon: '🔬',
    theme: 'blue',
    border: 'var(--accent-blue)',
    datasets: 1100,
    score: 92.7,
  },
]

const activities = [
  {
    id: 'activity-1432',
    time: '今天 14:32',
    title: '指标体系更新完成',
    desc: '新增12项三级指标，覆盖文化多样性风险维度',
    ok: true,
  },
  {
    id: 'activity-1115',
    time: '今天 11:15',
    title: '数据集清洗完成',
    desc: '教育领域数据集清洗完成，共处理12,847条记录',
    ok: true,
  },
  {
    id: 'activity-0942',
    time: '今天 09:42',
    title: '模型安全评估完成',
    desc: '综合安全评分87.6分，发现3项需关注的风险点',
    ok: false,
  },
  {
    id: 'activity-yesterday-1628',
    time: '昨天 16:28',
    title: '风险报告生成',
    desc: '生成文化敏感性风险报告，包含27项具体风险样本',
    ok: false,
  },
]
</script>
