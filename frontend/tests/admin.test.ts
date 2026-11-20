import { afterEach, expect, it, vi } from 'vitest'
import { BUNDLE } from '../src/api'
import { AdminError, BUNDLE as ADMIN_BUNDLE, call, newEpoch } from '../src/admin/adminApi'
import {
  NOT_SET, PENDING, UNSTORED, ariary, concession, correctionRequest, describe as summary, grantRequest, grouped, inHistory, keep,
  matches, month, moveRequest, newCorrection, newGrant, outcome, recorded, reference, refKey, release, sameRef, shaped, repayment, route, sentence,
  settle, stored, uncertain, whole, type Existing, type Item, type Pending, type Store,
} from '../src/admin/admin'

afterEach(() => { vi.unstubAllGlobals() })

// Every source file and entry page as text (Vite's glob: the project has no Node types).
const sources = import.meta.glob<string>(['../src/**/*.{ts,vue,css}', '../index.html', '../render.html', '../admin/index.html'],
  { query: '?raw', import: 'default', eager: true })
// Every address a file asks for: a script's from and import(), a stylesheet's @import and url() (quoted or not), a
// template's static src.
const imports = (text: string) => [...text.matchAll(/(?:\bfrom\s*|\bimport\s*\(?\s*|\bsrc=)['"]([^'"]+)['"]|\burl\(\s*['"]?([^'")\s]+)/g)].map(found => found[1] ?? found[2]!)
const own = (name: string) => name === 'vue' || /^\.\/[^/]+$/.test(name)
const links = (page: string) => [...sources[page]!.matchAll(/\b(?:src|href)="([^"]+)"/g)].map(found => found[1]!)
const admin = Object.entries(sources).filter(([path]) => path.startsWith('../src/admin/'))
// Every file of the folder, whatever its kind: the console's own copies of the font and the logo included (D-REDESIGN-005).
const folder = Object.keys(import.meta.glob('../src/admin/*'))

it('keeps the operator page and the shops apart: neither imports the other (D-ADMIN-005)', () => {
  expect(folder.sort()).toEqual(['Admin.vue', 'Confirm.vue', 'Overview.vue', 'Payments.vue', 'Service.vue', 'admin.css', 'admin.ts', 'adminApi.ts', 'main.ts',
    'Figtree-Variable.woff2', 'Figtree-OFL.txt', 'doka-horizontal-charcoal.svg', 'doka-horizontal-paper.svg', 'doka-symbol.svg'].map(name => `../src/admin/${name}`).sort())
  expect(admin.length).toBe(9)
  for (const [path, text] of admin)
    for (const name of imports(text)) expect(own(name), `${path} imports ${name}`).toBe(true)
  // The rule sees each way out of the folder, and lets the folder's own files through.
  for (const outside of ["@font-face { src: url(../outside.woff2) }", '@import "../style.css";', "@import url('/src/style.css');",
    '<img src="../assets/doka-horizontal.svg">', "import { BUNDLE } from '../api'", "const page = import('../App.vue')"])
    expect(imports(outside).length > 0 && !imports(outside).every(own), outside).toBe(true)
  for (const inside of ["src: url(./Figtree-Variable.woff2)", '<img src="./doka-symbol.svg" alt="">', "import Confirm from './Confirm.vue'"])
    expect(imports(inside).length > 0 && imports(inside).every(own), inside).toBe(true)
  const shops = Object.entries(sources).filter(([path]) => path.startsWith('../src/') && !path.startsWith('../src/admin/'))
  expect(shops.length).toBeGreaterThan(10)
  for (const [path, text] of shops)
    for (const name of imports(text)) expect(/(^|\/)admin(\/|$)/.test(name), `${path} imports ${name}`).toBe(false)
  expect(links('../admin/index.html')).toEqual(['/src/admin/main.ts'])
  for (const page of ['../index.html', '../render.html']) expect(links(page).filter(link => link.includes('admin'))).toEqual([])
})

it('splits each width by complementary conditions, in the stylesheet and the script, so a fractional width is on one side', () => {
  // Under zoom a width can be 1180.5 px: (max-width: 1180px) and (min-width: 1181px) would both miss it (D-REDESIGN-005).
  const queries = [...sources['../src/admin/admin.css']!.matchAll(/@media \(([^)]*width[^)]*)\)/g)].map(found => found[1])
  expect(new Set(queries)).toEqual(new Set(['width > 1180px', 'width <= 1180px', 'width >= 600px', 'width < 600px']))
  expect(sources['../src/admin/Admin.vue']).toContain("matchMedia('(width > 1180px)')")
})

it('names the same bundle as the shops, so that the server refuses both old pages together (ADR-103)', () => {
  expect(ADMIN_BUNDLE).toBe(BUNDLE)
})

// The router's cases apart (D-REDESIGN-006): the home, the list, the deep links, then what is malformed.
it('opens the overview on no hash, on # and on #/overview: the console’s home', () => {
  expect(route('')).toEqual({ view: 'overview' })
  expect(route('#')).toEqual({ view: 'overview' })
  expect(route('#/overview')).toEqual({ view: 'overview' })
})

it('opens the shop list on #/shops', () => {
  expect(route('#/shops')).toEqual({ view: 'shops' })
})

it('reads the deep links: one shop by its id, the payments, the service', () => {
  expect(route('#/shops/12')).toEqual({ view: 'shop', id: 12 })
  expect(route('#/shops/999999999')).toEqual({ view: 'shop', id: 999999999 })
  expect(route('#/money')).toEqual({ view: 'money' })
  expect(route('#/service')).toEqual({ view: 'service' })
})

it('opens the shop list on a malformed hash, as before the overview', () => {
  for (const hash of ['#/', '#/overview/', '#/Overview', '#overview', '#/shops/', '#/shops/0', '#/shops/012', '#/shops/12/x', '#/shops/-1',
    '#/shops/1e3', '#/shops/1000000000', '#/service/', '#/services', '#/money/', '#/payments'])
    expect(route(hash), hash).toEqual({ view: 'shops' })
})

it('renders what the server sends as text only: no v-html in the operator page (a shop or a stolen session writes some of it)', () => {
  for (const [path, text] of admin) expect(/v-html|innerHTML/.test(text), path).toBe(false)
})

it('says each refusal in English, and the operator’s refusals with their own detail', () => {
  const refused = (code: string, status: number, message = '', field?: string) => sentence(new AdminError(code, message, status, field))
  expect(NOT_SET).toContain('python -m affiche.shops operator-password')
  expect(refused('operator_not_set', 409, 'Aucun mot de passe…')).toBe(NOT_SET)
  expect(refused('wrong_credentials', 401)).toBe('Wrong password.')
  expect(refused('rate_limited', 429)).toContain('15 minutes')
  expect(refused('unauthenticated', 401)).toBe('Your session has ended. Sign in again.')
  expect(refused('bundle_outdated', 409)).toContain('Reload')
  expect(refused('operator_refused', 409, 'the identifier abc is already taken')).toBe('the identifier abc is already taken')
  expect(refused('validation_error', 422, 'Une valeur…', 'name')).toBe('The name was not accepted: 1 to 160 characters.')
  expect(refused('validation_error', 422, 'Une valeur…', 'body.welcome')).toBe('This value was not accepted: body.welcome.')
  expect(refused('internal_error', 500, 'Erreur')).toBe('The server failed (error 500).')
  expect(refused('storage_unavailable', 503)).toBe('The server’s storage is busy or unavailable.')
  expect(refused('something_new', 409)).toBe('Refused (something_new).')
  for (const [status, code, maybe] of [[0, 'network', true], [0, 'timeout', true], [503, 'storage_unavailable', true], [500, 'internal_error', true],
    [200, 'invalid_response', true], [401, 'unauthenticated', false], [409, 'operator_refused', false], [404, 'not_found', false]] as const)
    expect(uncertain(new AdminError(code, '', status)), code).toBe(maybe)
})

it('sends the bundle and the cookie the same-origin way, and carries what a refusal says', async () => {
  const fetch = vi.fn(async (_path: string, _init: RequestInit) => new Response(JSON.stringify({ shop: 1 }), { status: 201 }))
  vi.stubGlobal('fetch', fetch)
  expect(await call('/api/admin/shops', 'POST', { identifier: 'abc' })).toEqual({ shop: 1 })
  await call('/api/admin/shops')
  const [post, get] = fetch.mock.calls.map(([, init]) => init)
  expect(post).toMatchObject({ method: 'POST', credentials: 'same-origin', body: '{"identifier":"abc"}', headers: { 'X-Affiche-Bundle': '3', 'Content-Type': 'application/json' } })
  expect(get).toMatchObject({ method: 'GET', credentials: 'same-origin', body: undefined, headers: { 'X-Affiche-Bundle': '3' } })
  expect(post!.signal).toBeInstanceOf(AbortSignal)

  const refusal = (error: object, status = 409) => fetch.mockResolvedValueOnce(new Response(JSON.stringify({ error, request_id: 'r' }), { status }))
  const failed = () => call('/api/admin/shops/1/suspend', 'POST').catch((error: AdminError) => error)
  refusal({ code: 'operator_refused', message_fr: 'Refusé : rien n’a été écrit.', retryable: false, detail: 'no shop 9', existing: { id: 4 } })
  expect(await failed()).toMatchObject({ code: 'operator_refused', message: 'no shop 9', status: 409, existing: { id: 4 } })
  refusal({ code: 'unauthenticated', message_fr: 'Connectez-vous pour continuer.', retryable: false }, 401)
  expect(await failed()).toMatchObject({ code: 'unauthenticated', message: 'Connectez-vous pour continuer.', status: 401 })
  fetch.mockResolvedValueOnce(new Response('<html>Bad gateway</html>', { status: 502 }))
  expect(await failed()).toMatchObject({ code: 'invalid_response', status: 502 })
  fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  expect(await failed()).toMatchObject({ code: 'network', status: 0 })
  fetch.mockRejectedValueOnce(new DOMException('The operation timed out.', 'TimeoutError'))
  expect(await failed()).toMatchObject({ code: 'timeout', status: 0 })
})

it('drops every answer to a request sent before a new authentication state, a refusal as much as a success', async () => {
  const held: ((response: Response) => void)[] = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { held.push(resolve) })))
  const settled: string[] = []
  const watch = (name: string, request: Promise<unknown>) => request.then(() => settled.push(name), () => settled.push(name))
  void watch('earlier success', call('/api/admin/shops'))
  void watch('earlier refusal', call('/api/admin/shops/1/suspend', 'POST'))
  newEpoch()  // a sign-out, a session lost, a sign-in
  void watch('later', call('/api/admin/shops'))
  held[0]!(new Response('{"items":[{"id":1}]}'))
  held[1]!(new Response(JSON.stringify({ error: { code: 'operator_refused', detail: 'no' } }), { status: 409 }))
  held[2]!(new Response('{"items":[]}'))
  await new Promise(resolve => setTimeout(resolve, 20))
  expect(settled).toEqual(['later'])
})

// ---- Money (T-ADMIN-006) ----
const NB = String.fromCharCode(0xa0)  // the no-break space of grouped figures
const at = '2026-11-17T08:12:03.411Z'
const memoryStore = () => {
  const map = new Map<string, string>()
  return { getItem: (key: string) => map.get(key) ?? null, setItem: (key: string, value: string) => { map.set(key, value) }, removeItem: (key: string) => { map.delete(key) },
           key: (index: number) => [...map.keys()][index] ?? null, get length() { return map.size } }
}
const refusing = (): Store => { throw new DOMException('The operation is insecure.', 'SecurityError') }
const grantOf = (shop: number, ref = 'MV-123', credits = '10') => grantRequest(shop, { ...newGrant(), credits, amount: '20000', method: 'mvola', paymentRef: ref }, at)
const shopsByIds: Record<number, { identifier: string; name: string | null }> = { 3: { identifier: 'chezrado', name: 'Chez Rado' }, 5: { identifier: 'boutiquedeux', name: null } }
const find = (id: number) => shopsByIds[id]
const line = (over: Partial<Existing> = {}): Existing => ({ id: 7, shop_id: 3, identifier: 'chezrado', kind: 'grant', origin: 'bought', credits: 10,
  amount_ar: 20000, method: 'mvola', ref: 'MV-123', job_id: null, moved_to: null, ...over })
const JOB = '0b4d3c2a-1f2e-4d5c-8b7a-6f5e4d3c2b1a'

it('makes a reference once per form: the UTC second and a random suffix, so two in one second differ; never above 100', () => {
  const second = new Date('2026-11-17T08:12:03.999Z')
  const fixed = (byte: number) => (bytes: Uint8Array) => bytes.fill(byte)
  expect(reference('offered', second, fixed(0))).toBe('offered-20261117-081203-aaaaaa')
  expect(reference('offered', second, fixed(1))).toBe('offered-20261117-081203-bbbbbb')
  let calls = 0  // bytes from 248 up are drawn again, never folded onto the first letters
  expect(reference('correction', second, bytes => bytes.fill(calls++ ? 30 : 255))).toBe('correction-20261117-081203-999999')
  const made = Array.from({ length: 500 }, () => reference('offered'))
  expect(new Set(made).size).toBe(500)
  for (const ref of made) expect(ref).toMatch(/^offered-\d{8}-\d{6}-[a-hjkmnp-z2-9]{6}$/)
  expect(made[0]!.length).toBe(30)
  expect(reference('correction').length).toBe(33)
  expect(repayment(JOB)).toBe(`repay-${JOB}`)
  expect(repayment(JOB).length).toBe(42)
  // The concession after a refused move: deterministic, bounded at 100 (counted by code point, as the server counts).
  expect(concession('MV-123')).toBe('MV-123-geste')
  for (const length of [94, 95, 100]) expect(concession('x'.repeat(length)).length, String(length)).toBe(100)
  expect(concession('x'.repeat(95))).toBe(`${'x'.repeat(94)}-geste`)
  expect(concession('MV-123')).toBe(concession('MV-123'))
  // One payment, one concession, whatever its spaces: collapsed before the cut at 94.
  expect(concession(`${'A'.repeat(90)}  XYYYYY`)).toBe(concession(`${'A'.repeat(90)} XYYYYY`))
  expect(concession(`MV-123${String.fromCharCode(0x85)}`)).toBe('MV-123-geste')  // a space to Python that trim() keeps
  expect(concession(`${'A'.repeat(90)}  XYZ`).length).toBe(100)  // 95 typed, 94 collapsed: never 101
  expect([...concession('😀'.repeat(100))].length).toBe(100)
  for (let length = 1; length <= 100; length++) expect([...concession('y'.repeat(length))].length).toBeLessThanOrEqual(100)
})

it('freezes what a form makes: whole numbers only, the method as the server stores it, references trimmed', () => {
  for (const typed of ['', '0', '01', '1.5', '1e3', '-1', '+1', '1 000', '1000000001', '99999999999']) expect(() => whole(typed), typed).toThrow(RangeError)
  expect(whole('1')).toBe(1)
  expect(whole('1000000000')).toBe(1_000_000_000)
  const bought = grantRequest(3, { ...newGrant(), credits: '10', amount: '20000', method: ' MVola ', paymentRef: ' MV-123 ', note: '  ' }, at)
  expect(bought).toEqual({ shop: 3, form: 'grant', path: '/api/admin/shops/3/grants', at,
    body: { credits: 10, origin: 'bought', ref: 'MV-123', note: null, amount_ar: 20000, method: 'mvola' } })
  expect(Object.isFrozen(bought) && Object.isFrozen(bought.body)).toBe(true)
  expect(() => { (bought.body as { credits: number }).credits = 99 }).toThrow(TypeError)
  const draft = { ...newGrant(), origin: 'offered' as const, credits: '5', amount: '20000', method: 'mvola', paymentRef: 'MV-1', note: 'merci' }
  expect(grantRequest(3, draft, at).body).toEqual({ credits: 5, origin: 'offered', ref: draft.offeredRef, note: 'merci', amount_ar: null, method: null })
  const correction = { ...newCorrection(), sign: -1 as const, credits: '3', amount: '5000', paymentRef: ' MV-123 ', note: ' wrong shop ' }
  expect(correctionRequest(3, correction, at)).toEqual({ shop: 3, form: 'correction', path: '/api/admin/shops/3/corrections', at,
    body: { credits: -3, ref: correction.madeRef, note: 'wrong shop', amount_ar: null, job_id: null } })
  expect(correctionRequest(3, { ...correction, mode: 'amount' }, at).body).toEqual({ credits: 0, ref: 'MV-123', note: 'wrong shop', amount_ar: -5000, job_id: null })
  expect(correctionRequest(3, { ...correction, mode: 'repay', job: JOB }, at).body).toEqual({ credits: 1, ref: `repay-${JOB}`, note: 'wrong shop', amount_ar: null, job_id: JOB })
  expect(moveRequest(3, { ref: ' MV-9 ', to: '5', note: ' paid to the wrong shop ' }, at)).toEqual({ shop: 3, form: 'move', path: '/api/admin/payments/move', at,
    body: { ref: 'MV-9', from_shop: 3, to_shop: 5, note: 'paid to the wrong shop' } })
})

it('says exactly what a request writes, figures grouped for reading only', () => {
  expect([grouped(0), grouped(999), grouped(1000), grouped(1_000_000_000), grouped(-20000)]).toEqual(['0', '999', `1${NB}000`, `1${NB}000${NB}000${NB}000`, `−20${NB}000`])
  expect(ariary(20000)).toBe(`20${NB}000${NB}Ar`)
  expect(summary(grantOf(3), find)).toBe(`Grant 10 bought credits to chezrado (Chez Rado)? 20${NB}000${NB}Ar by mvola, reference MV-123.`)
  const offered = grantRequest(5, { ...newGrant(), origin: 'offered', credits: '1' }, at)
  expect(summary(offered, find)).toBe(`Grant 1 offered credit to boutiquedeux? Reference ${offered.body.ref}.`)
  const correction = { ...newCorrection(), madeRef: 'geste-1', credits: '1500', amount: '5000', paymentRef: 'MV-123', note: 'r' }
  expect(summary(correctionRequest(3, correction, at), find)).toBe(`Add 1${NB}500 credits to chezrado (Chez Rado)? Reference geste-1.`)
  expect(summary(correctionRequest(3, { ...correction, sign: -1 }, at), find)).toBe(`Take back 1${NB}500 credits from chezrado (Chez Rado)? Reference geste-1.`)
  expect(summary(correctionRequest(3, { ...correction, sign: -1, mode: 'amount' }, at), find)).toBe(`Change the amount of the payment MV-123 in chezrado (Chez Rado) by −5${NB}000${NB}Ar? No credit changes.`)
  expect(summary(correctionRequest(3, { ...correction, mode: 'repay', job: JOB }, at), find)).toBe(`Repay 1 credit to chezrado (Chez Rado) for the job ${JOB}? Reference repay-${JOB}.`)
  expect(summary(moveRequest(3, { ref: 'MV-9', to: '9', note: 'r' }, at), find)).toBe('Move the payment MV-9 from chezrado (Chez Rado) to shop 9? Its credits and its ariary leave the first shop for the second.')
  expect(month(new Date('2026-02-10T23:59:59Z'))).toEqual({ start: '2026-02-01', end: '2026-02-28' })
  expect(month(new Date('2028-02-29T00:00:00Z'))).toEqual({ start: '2028-02-01', end: '2028-02-29' })
  expect(month(new Date('2026-12-31T23:59:59Z'))).toEqual({ start: '2026-12-01', end: '2026-12-31' })
})

const GRANTED = { line: 1, balance: { available: 10, pending: 0 },
  headroom: { cap: 1, spent: 0, left: 1, outstanding: 10, unit: 0.1, cost: 1, images: 0, warning: false } }

it('reads a money answer only in the shape the server gives it', () => {
  const balance = { available: 1, pending: 0 }, move = moveRequest(3, { ref: 'MV-9', to: '9', note: 'r' }, at)
  const correction = correctionRequest(3, { ...newCorrection(), credits: '1', note: 'r' }, at)
  expect(shaped(grantOf(3), GRANTED)).toBe(true)
  expect(shaped(correction, { line: 2, balance })).toBe(true)
  expect(shaped(move, { lines: [3, 4], balances: { from: balance, to: balance } })).toBe(true)
  for (const bad of [null, {}, { line: '2', balance }, { line: 2 }, { line: 2, balance: { available: 1 } }]) expect(shaped(correction, bad)).toBe(false)
  for (const bad of [null, {}, { lines: [3], balances: { from: balance, to: balance } }, { lines: [3, 4], balances: { from: balance } }]) expect(shaped(move, bad)).toBe(false)
})

it('keeps a confirmed request before it leaves, and releases it only on a definite answer (D-ADMIN-005 state machine)', async () => {
  const refusal = (code: string, status: number) => () => Promise.reject(new AdminError(code, 'detail', status, undefined, code === 'already_recorded' ? { id: 1 } : undefined))
  const cases: [string, () => Promise<unknown>, string, boolean][] = [
    ['201', () => Promise.resolve(GRANTED), 'done', false],
    // A 2xx the page cannot read is no definite answer: kept, never released and then lost in a thrown defect.
    ['a 201 of another shape', () => Promise.resolve({}), 'uncertain', true],
    ['a 201 with no headroom', () => Promise.resolve({ ...GRANTED, headroom: undefined }), 'uncertain', true],
    ['already_recorded', refusal('already_recorded', 409), 'recorded', false],
    ['operator_refused', refusal('operator_refused', 409), 'refused', false],
    ['validation_error', refusal('validation_error', 422), 'refused', false],
    ['not_found', refusal('not_found', 404), 'refused', false],
    ['forbidden_origin', refusal('forbidden_origin', 403), 'refused', false],
    ['500', refusal('internal_error', 500), 'uncertain', true],
    ['503', refusal('storage_unavailable', 503), 'uncertain', true],
    ['network', refusal('network', 0), 'uncertain', true],
    ['timeout', refusal('timeout', 0), 'uncertain', true],
    ['an unreadable 201', refusal('invalid_response', 201), 'uncertain', true],
    ['401', refusal('unauthenticated', 401), 'resend', true],
    ['bundle_outdated', refusal('bundle_outdated', 409), 'resend', true],
  ]
  for (const [name, answer, expected, keeps] of cases) {
    const storage = memoryStore(), memory: Pending = {}, request = grantOf(3)
    let before: string | null = null
    const settled = await settle(memory, () => storage, request, async sent => { before = storage.getItem(PENDING + 3); expect(sent).toBe(request); return answer() })
    expect(JSON.parse(before!), `${name}: stored before it left`).toEqual(request)
    expect(settled.outcome, name).toBe(expected)
    expect(memory[3], name).toBe(keeps ? request : undefined)
    // Nothing else stays: the key itself goes with the last request.
    expect(storage.length, name).toBe(keeps ? 1 : 0)
    expect(stored(() => storage)[3], name).toEqual(keeps ? request : undefined)
  }
  // An answer that never comes (adminApi drops those of an earlier session) leaves it kept.
  const storage = memoryStore(), memory: Pending = {}, request = grantOf(3)
  void settle(memory, () => storage, request, () => new Promise(() => {}))
  await new Promise(resolve => setTimeout(resolve, 10))
  expect(memory[3]).toBe(request)
  expect(stored(() => storage)).toEqual({ 3: request })
  // A defect is not an answer: thrown, and the request stays.
  await expect(settle(memory, () => storage, request, () => Promise.reject(new TypeError('defect')))).rejects.toThrow('defect')
  expect(stored(() => storage)).toEqual({ 3: request })
})

it('keeps one unresolved request per shop, across tabs, and releases only that request', async () => {
  const storage = memoryStore(), tab: Pending = {}, other: Pending = {}
  expect(keep(tab, () => storage, grantOf(3))).toBe('stored')
  expect(keep(tab, () => storage, grantOf(3))).toBe('stored')  // the same request, sent again
  expect(keep(tab, () => storage, grantOf(3, 'MV-124'))).toBe('busy')
  expect(keep(tab, () => storage, grantOf(5))).toBe('stored')
  expect(keep(other, () => storage, grantOf(3, 'MV-125'))).toBe('busy')  // another tab sees it through storage
  const post = vi.fn()
  expect(await settle(other, () => storage, grantOf(5, 'MV-126'), post)).toEqual({ outcome: 'busy' })
  expect(post).not.toHaveBeenCalled()
  release(other, () => storage, grantOf(3, 'MV-125'))  // not the kept one: nothing changes
  expect(Object.keys(stored(() => storage))).toEqual(['3', '5'])
  release(tab, () => storage, grantOf(3))
  expect(Object.keys(stored(() => storage))).toEqual(['5'])
  expect(tab[3]).toBeUndefined()
  release(tab, () => storage, grantOf(5))
  expect(storage.length).toBe(0)
  // One key per shop: a release that another shop's keep interleaves with cannot remove that other request (each
  // touches its own key only), and an entry that is not ours under the prefix stays out.
  keep(tab, () => storage, grantOf(3)); keep(other, () => storage, grantOf(5))
  release(tab, () => storage, grantOf(3))
  expect(stored(() => storage)).toEqual({ 5: grantOf(5) })
  release(other, () => storage, grantOf(5))
  // What storage holds that is not a request of this page is never sent.
  const valid = grantOf(3)
  const entries: Record<string, unknown> = { 3: valid, 4: { ...grantOf(4), path: '/api/admin/shops/4/password' }, 5: grantOf(6), 6: 'x', 7: null, x: grantOf(8) }
  for (const [key, value] of Object.entries(entries)) storage.setItem(PENDING + key, JSON.stringify(value))
  storage.setItem(`${PENDING}9`, '{not json'); storage.setItem('elsewhere', JSON.stringify(grantOf(10)))
  expect(stored(() => storage)).toEqual({ 3: valid })
})

it('keeps a request in memory alone when the browser refuses storage, and says so', async () => {
  expect(UNSTORED).toBe('This browser cannot keep an unanswered request across a reload.')
  const memory: Pending = {}, request = grantOf(3)
  expect(stored(refusing)).toEqual({})
  const settled = await settle(memory, refusing, request, () => Promise.reject(new AdminError('storage_unavailable', '', 503)))
  expect(settled).toMatchObject({ outcome: 'uncertain', stored: false })
  // Said before the request leaves, not with an answer that may never come; not said when storage took it.
  const told = vi.fn()
  void settle({}, refusing, request, () => new Promise(() => {}), told)
  expect(told.mock.calls).toEqual([[false]])
  const kept = memoryStore()
  await settle({}, () => kept, request, () => Promise.resolve(GRANTED), told)
  expect(told.mock.calls).toEqual([[false], [true]])
  // Not admitted, not told: the mark of the request that still lives in the page stays as it was.
  keep({}, () => kept, grantOf(3, 'MV-124'))
  expect(await settle({ 3: request }, () => kept, request, vi.fn(), told)).toEqual({ outcome: 'busy' })
  expect(told).toHaveBeenCalledTimes(2)
  expect(memory[3]).toBe(request)
  expect(keep(memory, refusing, grantOf(3, 'MV-124'))).toBe('busy')
  const throwing = { ...memoryStore(), setItem: () => { throw new DOMException('full', 'QuotaExceededError') } }
  expect(keep({}, () => throwing, request)).toBe('memory')
  release(memory, refusing, request)
  expect(memory[3]).toBeUndefined()
})

it('resolves a kept request from the history as the server compares references, never a move', () => {
  const items: Item[] = [
    { type: 'job', id: JOB, kind: 'scene', status: 'succeeded', credit: 'spent', creation_id: 'c', result_ref: null, error_code: null, at, finished_at: at, repaid_by: 9 },
    { type: 'line', id: 8, kind: 'correction', origin: null, credits: 0, amount_ar: -5000, method: null, ref: 'mv  123', job_id: null, note: 'r', actor: 'operator', at },
    { type: 'line', id: 9, kind: 'correction', origin: null, credits: 1, amount_ar: null, method: null, ref: 'defect', job_id: JOB, note: 'r', actor: 'operator', at },
    { type: 'line', id: 7, kind: 'grant', origin: 'bought', credits: 10, amount_ar: 20000, method: 'mvola', ref: ' mv  123 ', job_id: null, note: null, actor: 'operator', at },
  ]
  expect(refKey(' MV \t 123 ')).toBe('mv 123')
  // Beyond ASCII the page's key is not the server's: two letters that toLowerCase folds together and Python 3.12's
  // casefold keeps apart must not resolve one payment's request by the other's line. The same text still does.
  const [a, b] = [String.fromCodePoint(0x1c89), String.fromCodePoint(0x1c8a)]
  expect(sameRef(`MV-${a}`, `MV-${b}`)).toBe(false)
  expect(sameRef('MV-ß', 'mv-ß')).toBe(false)
  expect(sameRef('MV-ß', 'MV-ß')).toBe(true)
  expect(sameRef(' MV  123', 'mv 123')).toBe(true)
  expect(inHistory(grantOf(3, `MV-${a}`), [{ ...(items[3] as any), ref: `MV-${b}` }])).toBeUndefined()
  expect(refKey(`MV${String.fromCharCode(0xfeff)}123`)).not.toBe(refKey('MV 123'))  // not a space to Python
  expect(refKey(`MV${String.fromCharCode(0x1f)}123`)).toBe(refKey('MV 123'))  // a space to Python, not to \s
  expect(inHistory(grantOf(3, 'MV 123'), items)?.id).toBe(7)  // a grant: the grant line, not the correction
  expect(inHistory(grantOf(3, 'MV-123'), items)).toBeUndefined()  // MV-123 and MV 123 are two references
  const correction = { ...newCorrection(), mode: 'amount' as const, amount: '5000', paymentRef: 'MV 123', note: 'r' }
  expect(inHistory(correctionRequest(3, correction, at), items)?.id).toBe(8)
  expect(inHistory(correctionRequest(3, { ...correction, mode: 'repay', job: JOB }, at), items)?.id).toBe(9)  // its job, whatever the reference
  expect(inHistory(moveRequest(3, { ref: 'MV 123', to: '5', note: 'r' }, at), items)).toBeUndefined()
})

it('reads already_recorded per action: as sent, other values, another shop, where a move went', () => {
  const request = grantOf(3)
  expect(matches(request, line())).toBe(true)
  expect(recorded(request, line(), find)).toEqual({ text: 'Already recorded as line 7, as sent. Nothing more to do.', same: true })
  const differs = 'Line 7 already holds this reference with other values. To change them, write a correction (or fix the amount). Do not use another reference.'
  for (const other of [{ credits: 11 }, { amount_ar: 20001 }, { method: 'orange' }, { origin: 'offered' }, { kind: 'correction' }] as Partial<Existing>[]) {
    expect(matches(request, line(other)), JSON.stringify(other)).toBe(false)
    expect(recorded(request, line(other), find), JSON.stringify(other)).toEqual({ text: differs, same: false })
  }
  expect(recorded(request, line({ shop_id: 5, identifier: 'boutiquedeux', id: 4 }), find))
    .toEqual({ text: 'This payment is recorded for boutiquedeux, line 4. If it belongs here, move it.', same: false })
  const repay = correctionRequest(3, { ...newCorrection(), mode: 'repay', job: JOB, note: 'r' }, at)
  expect(recorded(repay, line({ kind: 'correction', origin: null, credits: 1, amount_ar: null, method: null, ref: 'defect', job_id: JOB }), find).same).toBe(true)
  expect(recorded(repay, line({ kind: 'correction', origin: null, credits: 1, amount_ar: null, method: null, job_id: null }), find).same).toBe(false)

  const move = moveRequest(3, { ref: 'MV-123', to: '5', note: 'r' }, at)
  const reversal = line({ id: 42, kind: 'correction', origin: null, credits: -10, amount_ar: -20000, method: null })
  expect(recorded(move, { ...reversal, moved_to: { id: 43, shop_id: 5, identifier: 'boutiquedeux' } }, find))
    .toEqual({ text: 'Already moved to boutiquedeux, line 43, as sent.', same: true })
  expect(recorded(move, { ...reversal, moved_to: { id: 44, shop_id: 6, identifier: 'boutiquetrois' } }, find))
    .toEqual({ text: 'Already moved to boutiquetrois (line 44), not to boutiquedeux. See the payment’s history.', same: false })
  expect(recorded(move, { ...reversal, credits: 0, amount_ar: -500 }, find))
    .toEqual({ text: 'The payment was corrected in chezrado (an amount fix, line 42), not moved. See the payment’s history.', same: false })
  expect(recorded(move, reversal, find))
    .toEqual({ text: 'The payment was already corrected in chezrado (line 42). See the payment’s history.', same: false })
  expect(matches(move, reversal)).toBe(false)  // a move never reads « as sent » without its destination
})

it('tells a definite answer from an uncertain one', () => {
  expect(outcome()).toBe('done')
  for (const [code, status, expected] of [['already_recorded', 409, 'recorded'], ['operator_refused', 409, 'refused'], ['validation_error', 422, 'refused'],
    ['unauthenticated', 401, 'resend'], ['bundle_outdated', 409, 'resend'], ['storage_unavailable', 503, 'uncertain'], ['internal_error', 500, 'uncertain'],
    ['network', 0, 'uncertain'], ['timeout', 0, 'uncertain'], ['invalid_response', 201, 'uncertain']] as const)
    expect(outcome(new AdminError(code, '', status)), code).toBe(expected)
})
