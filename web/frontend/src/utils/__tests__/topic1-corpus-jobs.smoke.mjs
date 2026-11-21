import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const code = ts.transpileModule(
  fs.readFileSync(
    new URL('../../composables/data-input/useTopic1CorpusJobs.ts', import.meta.url),
    'utf8',
  ),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } },
).outputText

function setup(api) {
  let seq = 0
  const timers = []
  const memory = new Map()
  let dispose = () => {}
  const store = {
    valueCorpusRecords: [{ id: 'a', text: 'A' }],
    valueSelectedCorpus: { name: 'source' },
  }
  const context = {
    exports: {},
    require: (name) => {
      if (name === 'vue')
        return {
          ref: (value) => ({ value }),
          computed: (fn) => ({
            get value() {
              return fn()
            },
          }),
          onMounted: () => {},
          onBeforeUnmount: (fn) => {
            dispose = fn
          },
        }
      if (name === 'element-plus') return { ElMessageBox: { confirm: async () => {} } }
      if (name === '@/api/request') return { ApiRequestError: class extends Error {} }
      if (name === '@/stores/input') return { useInputStore: () => store }
      if (name === '@/utils/uuid') return { createUuid: () => String(++seq) }
      return api
    },
    sessionStorage: {
      getItem: (k) => memory.get(k) || null,
      setItem: (k, v) => memory.set(k, v),
      removeItem: (k) => memory.delete(k),
    },
    setTimeout: (fn) => {
      timers.push(fn)
      return timers.length
    },
    clearTimeout: () => {},
    Date,
    Map,
    // No browser crypto: supported intranet HTTP deployment.
  }
  vm.runInNewContext(code, context)
  return { flow: context.exports.useTopic1CorpusJobs(), store, timers, dispose: () => dispose() }
}

const calls = []
const a = setup({
  fingerprintCorpusRequest: async (p) => p.records[0].text,
  startCorpusJob: async (p) => {
    calls.push({ text: p.records[0].text, id: p.request_id })
    return { status: p.records[0].text === 'A' ? 'submission_unknown' : 'queued' }
  },
  listCorpusJobs: async () => ({ items: [], active: [], has_more: false }),
})
await a.flow.submit()
a.store.valueCorpusRecords[0].text = 'B'
await a.flow.submit()
a.store.valueCorpusRecords[0].text = 'A'
await a.flow.submit()
assert.equal(calls[0].id, calls[2].id)
assert.notEqual(calls[0].id, calls[1].id)

let finish
let submitted = false
const old = { id: 'old', status: 'running', created_at: '2026-01-01' }
const fresh = { id: 'new', status: 'queued', created_at: '2026-01-02' }
const b = setup({
  listCorpusJobs: async () => ({ items: submitted ? [fresh] : [old], active: [], has_more: false }),
  refreshCorpusJob: (id) =>
    id === 'old'
      ? new Promise((resolve) => {
          finish = resolve
        })
      : Promise.resolve(fresh),
  fingerprintCorpusRequest: async () => 'signature',
  startCorpusJob: async () => {
    submitted = true
    return fresh
  },
})
const pending = b.flow.refresh()
await new Promise((resolve) => setImmediate(resolve))
await b.flow.submit()
finish({ ...old, status: 'completed' })
await pending
assert.equal(b.timers.length, 1)
await b.flow.refresh()
assert.equal(b.flow.jobs.value[0].id, 'new')
console.log('PASS: HTTP without crypto, per-fingerprint idempotency, submit/refresh race')

let resultCalls = 0
let resolveResult
const c = setup({
  getCorpusJobResult: () => {
    resultCalls += 1
    return new Promise((resolve) => {
      resolveResult = resolve
    })
  },
})
c.flow.jobs.value = [
  { id: 'one', source_name: 'Corpus A', operation: 'score', status: 'completed' },
  { id: 'two', source_name: 'Corpus B', operation: 'detox', status: 'failed' },
]
c.flow.search.value = '  corpus  '
assert.equal(c.flow.filteredJobs.value.length, 2)
c.flow.statusFilter.value = 'failed'
assert.equal(c.flow.filteredJobs.value[0].id, 'two')
c.flow.search.value = 'ONE'
assert.equal(c.flow.filteredJobs.value.length, 0)
c.flow.statusFilter.value = ''
assert.equal(c.flow.filteredJobs.value[0].id, 'one')
assert.equal(c.flow.jobs.value.length, 2)
c.flow.error.value = 'previous failure'
const loading = c.flow.showResult({ id: 'one' })
assert.equal(c.flow.error.value, '')
await c.flow.showResult({ id: 'two' })
assert.equal(resultCalls, 1)
c.dispose()
resolveResult({ job: { id: 'one' }, result: { samples: [] } })
await loading
assert.equal(c.flow.result.value, null)
assert.equal(c.flow.busy.value, false)
console.log('PASS: task filters, single result request, cleared errors and unmount protection')
