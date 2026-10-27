const TABS = [
  { id: 'overview', label: '成果总览' },
  { id: 'dynbench', label: 'DynBench 评测' },
  { id: 'cbrne', label: 'AI4Sci / CBRNE' },
  { id: 'explicit', label: '显式有害注入案例' },
]

const READINESS_LABELS = {
  ready: '就绪',
  missing: '缺失',
  offline: '离线',
  invalid: '异常',
}

const MODE_LABELS = {
  dynamic: '动态演示',
  prerun: '预跑结果',
  'static-only': '纯静态',
}

const IFRAME_LOAD_TIMEOUT_MS = 60_000

const state = {
  activeTab: 'overview',
  overview: null,
  status: null,
  cbrneStats: null,
  prerun: null,
  prerunReport: null,
  iframeFallbackTriggered: false,
  iframeLoaded: false,
}

let dynbenchIframeTimer = null

function $(selector) {
  return document.querySelector(selector)
}

async function fetchJson(url) {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`请求失败：${url} (${response.status})`)
  }
  return response.json()
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

function renderModeratorChips(moderators) {
  return moderators
    .map((name) => `<span class="meta-chip">${escapeHtml(name)}</span>`)
    .join('')
}

function renderPrerunMetadata(metadata) {
  const attackStrategies = metadata.attack_strategies.join(', ')

  return `
    <section class="meta-section">
      <h3 class="meta-section__title">运行标识</h3>
      <div class="meta-grid meta-grid--prerun">
        <div class="meta-item meta-item--full">
          <span class="meta-item__label">Run ID</span>
          <span class="meta-item__value meta-item__value--mono">${escapeHtml(metadata.run_id)}</span>
        </div>
        <div class="meta-item meta-item--full">
          <span class="meta-item__label">Commit</span>
          <span class="meta-item__value meta-item__value--mono">${escapeHtml(metadata.commit)}</span>
        </div>
      </div>
    </section>
    <section class="meta-section">
      <h3 class="meta-section__title">实验参数</h3>
      <div class="meta-grid meta-grid--params">
        <div class="meta-item">
          <span class="meta-item__label">Budget</span>
          <span class="meta-item__value">${metadata.budget}</span>
        </div>
        <div class="meta-item">
          <span class="meta-item__label">Sampling Seed</span>
          <span class="meta-item__value">${metadata.sampling_seed}</span>
        </div>
        <div class="meta-item meta-item--full">
          <span class="meta-item__label">Attack Strategies</span>
          <span class="meta-item__value">${escapeHtml(attackStrategies)}</span>
        </div>
        <div class="meta-item meta-item--full">
          <span class="meta-item__label">Moderators</span>
          <div class="meta-chips">${renderModeratorChips(metadata.moderators)}</div>
        </div>
      </div>
    </section>
  `
}

function readinessClass(readiness) {
  if (readiness === 'ready') {
    return 'is-ready'
  }
  if (readiness === 'invalid') {
    return 'is-invalid'
  }
  return 'is-offline'
}

function renderStatsTable(title, stats) {
  const sections = [
    ['标签分布', stats.labels],
    ['L2 分类', stats.l2_categories],
    ['来源 Benchmark', stats.source_benchmarks],
    ['Seed 类型', stats.seed_types],
  ]

  return `
    <div class="stats-section">
      <h3 class="stats-section__title">${escapeHtml(title)}（${stats.total} 条）</h3>
      ${sections
        .map(([sectionTitle, bucket]) => renderBucketTable(sectionTitle, bucket))
        .join('')}
    </div>
  `
}

function renderBucketTable(title, bucket) {
  const entries = Object.entries(bucket || {}).sort((left, right) => right[1] - left[1])
  if (entries.length === 0) {
    return `<p class="card__hint">${escapeHtml(title)}：暂无统计数据</p>`
  }

  const rows = entries
    .map(
      ([name, count]) => `
        <tr>
          <td>${escapeHtml(name)}</td>
          <td>${count}</td>
        </tr>
      `,
    )
    .join('')

  return `
    <table class="stats-table" aria-label="${escapeHtml(title)}">
      <thead>
        <tr>
          <th>${escapeHtml(title)}</th>
          <th>数量</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `
}

function renderOverviewPanel() {
  const overview = state.overview
  if (!overview) {
    return '<div class="card"><p class="card__hint">正在加载总览数据…</p></div>'
  }

  const status = overview.status
  const lifecycleLinks = overview.lifecycle_cases
    .map((item) => {
      const path =
        item.id === 'cbrne'
          ? '/lifecycle/cbrne'
          : '/lifecycle/explicit-harmful-injection'
      return `
        <button
          type="button"
          class="btn btn-secondary lifecycle-open"
          data-lifecycle-url="${path}"
          data-lifecycle-title="${escapeHtml(item.title)}"
        >
          ${escapeHtml(item.title)}（${item.case_count} 例）
        </button>
      `
    })
    .join('')

  const workflow = overview.workflow
    .map(
      (step, index) => `
        ${index > 0 ? '<span class="workflow__arrow">→</span>' : ''}
        <span class="workflow__step">${escapeHtml(step)}</span>
      `,
    )
    .join('')

  return `
    <div class="card">
      <h2 class="card__title">数据规模</h2>
      <div class="metric-grid">
        <div class="metric-card">
          <span class="metric-card__value">${overview.cbrne_full_total}</span>
          <span class="metric-card__label">CBRNE 全量样本</span>
        </div>
        <div class="metric-card">
          <span class="metric-card__value">${overview.cbrne_filtered_total}</span>
          <span class="metric-card__label">CBRNE 过滤集</span>
        </div>
        <div class="metric-card">
          <span class="metric-card__value">${overview.lifecycle_case_total}</span>
          <span class="metric-card__label">生命周期案例</span>
        </div>
      </div>
    </div>

    <div class="card">
      <h2 class="card__title">就绪状态</h2>
      <div class="status-grid">
        ${renderStatusItem('静态资产', status.static_assets)}
        ${renderStatusItem('预跑工件', status.prerun)}
        ${renderStatusItem('DynBench', status.dynbench)}
      </div>
    </div>

    <div class="card">
      <h2 class="card__title">评测流程</h2>
      <div class="workflow">${workflow}</div>
    </div>

    <div class="card">
      <h2 class="card__title">生命周期入口</h2>
      <p class="card__hint">点击下方按钮查看完整生命周期 HTML（保留 Mermaid 依赖）。</p>
      <div class="lifecycle-links">${lifecycleLinks}</div>
    </div>
  `
}

function renderStatusItem(label, readiness) {
  return `
    <div class="status-item">
      <span class="status-item__label">${escapeHtml(label)}</span>
      <span class="status-item__value ${readinessClass(readiness)}">
        ${escapeHtml(READINESS_LABELS[readiness] || readiness)}
      </span>
    </div>
  `
}

function currentDynbenchView() {
  if (state.iframeFallbackTriggered && state.prerun) {
    return 'prerun-fallback'
  }
  if (!state.status) {
    return 'loading'
  }
  if (state.status.mode === 'dynamic' && !state.iframeFallbackTriggered) {
    return 'dynamic'
  }
  if (state.status.mode === 'prerun' || state.prerun) {
    return 'prerun'
  }
  return 'static-only'
}

function renderDynbenchPanel() {
  const view = currentDynbenchView()

  if (view === 'loading') {
    return '<div class="card"><p class="card__hint">正在检测 DynBench 与预跑状态…</p></div>'
  }

  if (view === 'dynamic') {
    const notice = state.iframeLoaded
      ? ''
      : '<p class="dynbench-panel__notice">正在加载 DynBench WebUI，若 60 秒内未完成将自动切换至预跑结果。</p>'
    return `
      <div class="card">
        <h2 class="card__title">DynBench 动态评测</h2>
        <p class="card__hint">当前为动态演示模式，嵌入课题二 DynBench WebUI（8766）。</p>
        ${notice}
        <div class="dynbench-iframe-wrap">
          <iframe
            id="dynbench-iframe"
            class="dynbench-iframe"
            title="DynBench WebUI"
            src="${escapeHtml(state.status.dynbench_webui_url || '')}"
          ></iframe>
        </div>
      </div>
    `
  }

  if (view === 'prerun' || view === 'prerun-fallback') {
    if (!state.prerun) {
      return renderStaticOnlyPanel('预跑工件暂不可用。')
    }

    const metadata = state.prerun.metadata
    const metrics = Object.entries(metadata.metrics || {})
      .map(
        ([key, value]) => `
          <div class="meta-item">
            <span class="meta-item__label">${escapeHtml(key)}</span>
            <span class="meta-item__value">${escapeHtml(value)}</span>
          </div>
        `,
      )
      .join('')

    const fallbackNotice =
      view === 'prerun-fallback'
        ? '<p class="dynbench-panel__notice">动态界面加载超时，已切换至预跑结果展示。</p>'
        : '<p class="card__hint">当前展示预跑结果（DynBench 动态环境不可用）。</p>'

    return `
      <div class="card">
        <h2 class="card__title">当前展示预跑结果</h2>
        ${fallbackNotice}
        ${renderPrerunMetadata(metadata)}
        <h3 class="stats-section__title">指标摘要</h3>
        <div class="meta-grid">${metrics}</div>
        <h3 class="stats-section__title">预跑报告</h3>
        <pre class="report-block">${escapeHtml(state.prerunReport || '报告暂不可用')}</pre>
      </div>
    `
  }

  return renderStaticOnlyPanel(
    '动态评测与预跑结果暂不可用，可通过其他页签查看 CBRNE 统计与生命周期案例。',
  )
}

function renderStaticOnlyPanel(message) {
  return `
    <div class="card">
      <h2 class="card__title">DynBench 暂不可用</h2>
      <p class="card__hint">${escapeHtml(message)}</p>
      <div class="lifecycle-links">
        <button
          type="button"
          class="btn btn-secondary lifecycle-open"
          data-lifecycle-url="/lifecycle/cbrne"
          data-lifecycle-title="AI4Sci / CBRNE"
        >
          查看 CBRNE 生命周期
        </button>
        <button
          type="button"
          class="btn btn-secondary lifecycle-open"
          data-lifecycle-url="/lifecycle/explicit-harmful-injection"
          data-lifecycle-title="显式有害注入"
        >
          查看显式有害注入案例
        </button>
      </div>
    </div>
  `
}

function renderCbrnePanel() {
  if (!state.cbrneStats) {
    return '<div class="card"><p class="card__hint">正在加载 CBRNE 统计…</p></div>'
  }

  return `
    <div class="card">
      <h2 class="card__title">AI4Sci / CBRNE 数据统计</h2>
      <p class="card__hint">仅展示聚合统计，不提供原始 JSONL 下载。</p>
      ${renderStatsTable('全量集', state.cbrneStats.full)}
      ${renderStatsTable('过滤集', state.cbrneStats.filtered)}
      <div class="lifecycle-links">
        <button
          type="button"
          class="btn btn-primary lifecycle-open"
          data-lifecycle-url="/lifecycle/cbrne"
          data-lifecycle-title="AI4Sci / CBRNE 生命周期"
        >
          查看 CBRNE 生命周期案例
        </button>
      </div>
    </div>
  `
}

function renderExplicitPanel() {
  const explicitCase = state.overview?.lifecycle_cases?.find(
    (item) => item.id === 'explicit-harmful-injection',
  )

  const caseCount = explicitCase?.case_count ?? '—'

  return `
    <div class="card">
      <h2 class="card__title">显式有害注入案例</h2>
      <p class="card__hint">
        展示 ${caseCount} 个典型生命周期案例，包含 query、改写文本与 Moderator 结果。
      </p>
      <div class="lifecycle-links">
        <button
          type="button"
          class="btn btn-primary lifecycle-open"
          data-lifecycle-url="/lifecycle/explicit-harmful-injection"
          data-lifecycle-title="显式有害注入生命周期"
        >
          打开生命周期案例页
        </button>
      </div>
    </div>
  `
}

function renderTabs() {
  const nav = $('#tab-nav')
  nav.innerHTML = TABS.map((tab) => {
    const activeClass = tab.id === state.activeTab ? 'is-active' : ''
    return `
      <button
        type="button"
        class="tab-nav__button ${activeClass}"
        data-tab="${tab.id}"
      >
        ${escapeHtml(tab.label)}
      </button>
    `
  }).join('')
}

function renderPanels() {
  const panels = {
    overview: renderOverviewPanel(),
    dynbench: renderDynbenchPanel(),
    cbrne: renderCbrnePanel(),
    explicit: renderExplicitPanel(),
  }

  for (const tab of TABS) {
    const panel = document.getElementById(`panel-${tab.id}`)
    if (!(panel instanceof HTMLElement)) {
      continue
    }
    panel.innerHTML = panels[tab.id]
    panel.classList.toggle('panel--hidden', tab.id !== state.activeTab)
  }
}

function updateHeader() {
  if (state.overview) {
    $('#showcase-title').textContent = state.overview.title
    $('#showcase-subtitle').textContent =
      'DynBench 动态评测 · 预跑结果 · CBRNE 统计 · 生命周期案例'
  }

  const badge = $('#mode-badge')
  if (!state.status) {
    badge.hidden = true
    return
  }

  badge.hidden = false
  badge.textContent = `当前模式：${MODE_LABELS[state.status.mode] || state.status.mode}`
}

function clearDynbenchIframeTimer() {
  if (dynbenchIframeTimer !== null) {
    clearTimeout(dynbenchIframeTimer)
    dynbenchIframeTimer = null
  }
}

function setupDynbenchIframeWatch() {
  clearDynbenchIframeTimer()

  if (currentDynbenchView() !== 'dynamic') {
    return
  }

  const iframe = $('#dynbench-iframe')
  if (!(iframe instanceof HTMLIFrameElement)) {
    return
  }

  state.iframeLoaded = false
  iframe.addEventListener(
    'load',
    () => {
      state.iframeLoaded = true
      clearDynbenchIframeTimer()
    },
    { once: true },
  )

  dynbenchIframeTimer = window.setTimeout(() => {
    if (state.iframeLoaded || !state.prerun) {
      return
    }
    state.iframeFallbackTriggered = true
    render()
  }, IFRAME_LOAD_TIMEOUT_MS)
}

function openLifecycleViewer(url, title) {
  const viewer = $('#lifecycle-viewer')
  const frame = $('#lifecycle-frame')
  $('#lifecycle-viewer-title').textContent = title
  frame.src = url
  viewer.classList.remove('panel--hidden')
}

function closeLifecycleViewer() {
  const viewer = $('#lifecycle-viewer')
  const frame = $('#lifecycle-frame')
  frame.src = 'about:blank'
  viewer.classList.add('panel--hidden')
}

function bindEvents() {
  $('#tab-nav').addEventListener('click', (event) => {
    const button = event.target.closest('.tab-nav__button')
    if (!(button instanceof HTMLElement) || !button.dataset.tab) {
      return
    }
    state.activeTab = button.dataset.tab
    render()
  })

  document.body.addEventListener('click', (event) => {
    const lifecycleButton = event.target.closest('.lifecycle-open')
    if (lifecycleButton instanceof HTMLElement) {
      openLifecycleViewer(
        lifecycleButton.dataset.lifecycleUrl,
        lifecycleButton.dataset.lifecycleTitle || '生命周期案例',
      )
    }
  })

  $('#lifecycle-back').addEventListener('click', () => {
    closeLifecycleViewer()
  })
}

function showError(message) {
  const error = $('#showcase-error')
  error.textContent = message
  error.classList.remove('panel--hidden')
}

async function loadPrerunData() {
  try {
    state.prerun = await fetchJson('/api/prerun')
    state.prerunReport = (await fetchJson('/api/prerun/report')).report
  } catch {
    state.prerun = null
    state.prerunReport = null
  }
}

async function bootstrap() {
  bindEvents()

  try {
    const [overview, status, cbrneStats] = await Promise.all([
      fetchJson('/api/overview'),
      fetchJson('/api/status'),
      fetchJson('/api/cbrne/stats'),
    ])

    state.overview = overview
    state.status = status
    state.cbrneStats = cbrneStats

    if (status.mode === 'dynamic' || status.mode === 'prerun') {
      await loadPrerunData()
    }

    render()
  } catch (error) {
    showError(error instanceof Error ? error.message : '展示页面初始化失败')
  }
}

function render() {
  renderTabs()
  renderPanels()
  updateHeader()
  setupDynbenchIframeWatch()
}

document.addEventListener('DOMContentLoaded', bootstrap)
