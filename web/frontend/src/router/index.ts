import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/governance',
  },
  {
    path: '/governance',
    name: 'governance',
    component: () => import('@/views/GovernanceView.vue'),
    meta: { title: '治理会话' },
  },
  {
    path: '/governance/review/:shareToken',
    name: 'governance-review',
    component: () => import('@/views/GovernanceReviewShareView.vue'),
    meta: { title: '治理任务评审' },
  },
  {
    path: '/home',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/definition',
    name: 'definition',
    component: () => import('@/views/DefinitionView.vue'),
    meta: { title: '治理标准体系' },
  },
  {
    path: '/input-guardrail',
    name: 'input-guardrail',
    component: () => import('@/views/InputGuardrailView.vue'),
    meta: { title: '输入数据治理' },
  },
  {
    path: '/output-guardrail',
    name: 'output-guardrail',
    component: () => import('@/views/OutputGuardrailView.vue'),
    meta: { title: '输出内容治理' },
  },
  {
    path: '/data-input',
    name: 'data-input',
    component: () => import('@/views/DataInputView.vue'),
    meta: { title: '输入语料治理' },
  },
  {
    path: '/data-input-prototype',
    name: 'data-input-prototype',
    component: () => import('@/views/DataInputPrototypeView.vue'),
    meta: { title: '输入数据治理概念原型' },
  },
  {
    path: '/output',
    name: 'output',
    component: () => import('@/views/OutputView.vue'),
    meta: { title: '输出内容治理' },
  },
  {
    path: '/benchmark',
    name: 'benchmark',
    component: () => import('@/views/BenchmarkView.vue'),
    meta: { title: '动态 Benchmark' },
  },
  {
    path: '/benchmark/assets/:assetId',
    name: 'benchmark-asset',
    component: () => import('@/views/BenchmarkView.vue'),
    meta: { title: 'Benchmark 资产' },
  },
  {
    path: '/benchmark/assets/:assetId/samples/:sampleId',
    name: 'benchmark-sample',
    component: () => import('@/views/BenchmarkView.vue'),
    meta: { title: 'Benchmark 样本' },
  },
  {
    path: '/integration',
    name: 'integration',
    component: () => import('@/views/IntegrationView.vue'),
    meta: { title: '课题集成' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const routeAssetId = Array.isArray(to.params.assetId) ? to.params.assetId[0] : to.params.assetId
  const routeSampleId = Array.isArray(to.params.sampleId)
    ? to.params.sampleId[0]
    : to.params.sampleId
  const title =
    to.name === 'benchmark-sample' && routeSampleId
      ? `Benchmark 样本 ${routeSampleId}`
      : to.name === 'benchmark-asset' && routeAssetId
        ? `Benchmark 资产 ${routeAssetId}`
        : to.meta.title
  document.title = title ? `${title} | 内容安全治理平台` : '内容安全治理平台'
})

export default router
