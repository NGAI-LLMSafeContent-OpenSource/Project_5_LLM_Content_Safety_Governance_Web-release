/**
 * UUID compatibility smoke for browsers without crypto.randomUUID.
 *
 * Run with:
 *   node web/frontend/src/utils/__tests__/uuid.smoke.mjs
 */

import { createUuid } from '../uuid.ts'

function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

const nativeUuid = '11111111-1111-4111-8111-111111111111'
let fallbackCalled = false
const nativeResult = createUuid({
  randomUUID: () => nativeUuid,
  getRandomValues: () => {
    fallbackCalled = true
    throw new Error('native randomUUID should be preferred')
  },
})

assert(nativeResult === nativeUuid, 'native randomUUID result must be preserved')
assert(!fallbackCalled, 'getRandomValues must not run when randomUUID is available')

const fallbackResult = createUuid({
  getRandomValues: (bytes) => {
    bytes.fill(0)
    return bytes
  },
})

assert(
  fallbackResult === '00000000-0000-4000-8000-000000000000',
  'getRandomValues fallback must produce an RFC 4122 version 4 UUID',
)

const lastResortResult = createUuid(null)
assert(
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(lastResortResult),
  'last-resort fallback must preserve the UUID v4 contract',
)

console.log('uuid.smoke.mjs ok')
