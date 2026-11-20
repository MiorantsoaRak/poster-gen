import { afterEach, expect, it, vi } from 'vitest'
import { api, bind, BUNDLE, clockSkew, mutation, open, read, retained } from '../src/api'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
// The shop's requests leave only once the gate has opened on the bound shop (D-MULTI-SHOP-007): shop 1 here.
bind(1); open()
async function opened() {
  const module = await import('../src/api')
  module.bind(1); module.open()
  return module
}
const answer = (headers: Record<string, string> = {}) => async () => new Response(JSON.stringify({ id: 'saved' }), { headers })
it('names its bundle on every request, so that the server can refuse an older open tab (ADR-103)', async () => {
  const fetch = vi.fn(answer())
  vi.stubGlobal('fetch', fetch)
  await api('/api/creations')
  await api('/api/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
  await mutation('/api/creations/c', { a: 1 }, 3, 'k', 'PUT')
  await read({ key: 'r', body: '{}' })
  await api('/api/assets', { method: 'POST', body: new FormData() })
  const sent = fetch.mock.calls.map(call => (call as unknown as [string, RequestInit])[1].headers as Record<string, string>)
  expect(sent.map(headers => headers['X-Affiche-Bundle'])).toEqual(Array(5).fill(String(BUNDLE)))
  expect(BUNDLE).toBe(3)  // backend api.py BUNDLE: raised together
  expect(sent[2]).toMatchObject({ 'Idempotency-Key': 'k', 'If-Match': '"3"', 'Content-Type': 'application/json' })
  expect(sent[4]).toEqual({ 'X-Affiche-Shop': '1', 'X-Affiche-Bundle': '3' })  // an upload keeps the browser's own Content-Type
})
it('reuses an uncertain mutation key after a lost response, then starts a new action after success', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('lost')).mockImplementation(answer())
  vi.stubGlobal('fetch', fetch)
  await expect(mutation('/example', { value: 1 }, 2)).rejects.toThrow('Connexion')
  await mutation('/example', { value: 1 }, 2)
  await mutation('/example', { value: 1 }, 2)
  const requests = fetch.mock.calls.map(call => call[1] as RequestInit)
  expect(requests[0].headers).toEqual(requests[1].headers)
  expect(requests[2].headers).not.toEqual(requests[1].headers)
  expect(requests[0].body).toBe(requests[1].body)
})
it('keeps the key of a lost answer only: a refusal stored nothing, so the next tap is a new request (D-BALANCE-006)', async () => {
  const refused = async () => new Response(JSON.stringify({ error: { code: 'no_credit', message_fr: 'Plus de crédit.' } }), { status: 402 })
  const fetch = vi.fn().mockRejectedValueOnce(new Error('lost')).mockImplementationOnce(answer()).mockImplementationOnce(refused).mockImplementation(answer())
  vi.stubGlobal('fetch', fetch)
  await expect(mutation('/api/creations/c/scenes', { value: 1 }, 2)).rejects.toThrow('Connexion')
  expect(retained('/api/creations/c/scenes')).toBe(true)
  expect(retained('/api/creations/c/refinements')).toBe(false)
  await mutation('/api/creations/c/scenes', { value: 1 }, 2)  // the same key: the server answers what it stored
  expect(retained('/api/creations/c/scenes')).toBe(false)
  await expect(mutation('/api/creations/c/scenes', { value: 2 }, 2)).rejects.toThrow('Plus de crédit.')
  expect(retained('/api/creations/c/scenes')).toBe(false)
  await mutation('/api/creations/c/scenes', { value: 2 }, 2)
  const keys = fetch.mock.calls.map(call => ((call as unknown as [string, RequestInit])[1].headers as Record<string, string>)['Idempotency-Key'])
  expect(keys[0]).toBe(keys[1])
  expect(new Set(keys.slice(1)).size).toBe(3)  // after the refusal, a new key
})
it('reads the server clock from the Date header; a response without one keeps the last reading', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(answer({ Date: new Date(Date.now() + 30_000).toUTCString() })).mockImplementation(answer()))
  await api('/example')
  const skew = clockSkew!  // a live binding: the value of the last response
  expect(Math.abs(skew - 30_000)).toBeLessThanOrEqual(1000)  // the header has whole seconds
  await api('/example')
  expect(clockSkew).toBe(skew)
})

// D-POSTER-EDITOR-007 point 3: the top line answers a wait the owner sees, never a background one.
// A fresh module each time: the tests above leave real timers of their own in its state.
async function held() {
  vi.useFakeTimers(); vi.resetModules()
  const release: Array<() => void> = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => release.push(() => done(new Response('{}'))))))
  return { release, ...await opened() }
}
it('shows the progress line after 300 ms of waiting, through the gap between two requests, and hides it a frame after', async () => {
  const { release, api, progress } = await held()
  const action = (async () => { await api('/one'); await api('/two') })()
  await vi.advanceTimersByTimeAsync(299)
  expect(progress.value).toBe(false)
  await vi.advanceTimersByTimeAsync(1)
  expect(progress.value).toBe(true)
  release[0]()
  await vi.advanceTimersByTimeAsync(0)  // the second request starts within the frame: the line stays
  expect(release).toHaveLength(2)
  await vi.advanceTimersByTimeAsync(100)
  expect(progress.value).toBe(true)
  release[1](); await action
  await vi.advanceTimersByTimeAsync(16)
  expect(progress.value).toBe(false)
})
it('never shows the line for a quick answer or a quiet request', async () => {
  const { release, api, mutation, progress } = await held()
  const quick = api('/quick')
  await vi.advanceTimersByTimeAsync(100)
  release[0](); await quick
  await vi.advanceTimersByTimeAsync(1000)
  expect(progress.value).toBe(false)
  const polls = [api('/poll', { quiet: true }), mutation('/save', {}, 1, 'k', 'PUT', true)]
  await vi.advanceTimersByTimeAsync(1000)
  expect(progress.value).toBe(false)
  release[1](); release[2](); await Promise.all(polls)
  expect(vi.mocked(fetch).mock.calls[1][1]).not.toHaveProperty('quiet')  // not passed on to fetch
})
it('counts a failed request as finished: the line still hides after the next wait', async () => {
  const { release, api, progress } = await held()
  vi.mocked(fetch).mockRejectedValueOnce(new Error('lost'))
  await expect(api('/lost')).rejects.toThrow('Connexion')
  await vi.advanceTimersByTimeAsync(1000)
  expect(progress.value).toBe(false)
  const next = api('/next')
  await vi.advanceTimersByTimeAsync(300)
  expect(progress.value).toBe(true)
  release[0](); await next
  await vi.advanceTimersByTimeAsync(16)
  expect(progress.value).toBe(false)  // would stay on if the lost request were still counted
})
it('builds the image addresses with the server encoder versions', async () => {
  const { displayUrl, preparedUrl, thumbnailUrl } = await import('../src/api')
  expect(preparedUrl('/api/assets/ab')).toBe('/api/assets/ab?prepared=true&v=1')
  expect(displayUrl('/api/assets/ab')).toBe('/api/assets/ab?prepared=true&display=true&v=1')
  expect(thumbnailUrl('/api/assets/ab')).toBe('/api/thumbnails/ab?v=1')
})

// D-TEXT-FIRST-002 and 003: a read is paid and bounded at 30 s on the client; its record goes as it is.
it('gives up a read after 30 s with a timeout error, and leaves other calls without a limit', async () => {
  vi.useFakeTimers(); vi.resetModules()
  const signals: (AbortSignal | undefined)[] = []
  vi.stubGlobal('fetch', vi.fn((_path: string, init: RequestInit) => new Promise<Response>((_done, fail) => {
    signals.push(init.signal ?? undefined)
    init.signal?.addEventListener('abort', () => fail(new DOMException('aborted', 'AbortError')))
  })))
  const { api, read, ApiError } = await opened()
  const failure = read({ key: 'k', body: '{}' }).catch(reason => reason)
  void api('/slow')
  await vi.advanceTimersByTimeAsync(29_999)
  expect(signals[0]!.aborted).toBe(false)
  await vi.advanceTimersByTimeAsync(1)
  const reason = await failure as InstanceType<typeof ApiError>
  expect(reason).toBeInstanceOf(ApiError)
  expect(reason.code).toBe('timeout')
  expect(signals[1]).toBeUndefined()  // no opt-in, no signal: the call is as before
})
it('clears the limit once a read has answered', async () => {
  vi.useFakeTimers(); vi.resetModules()
  vi.stubGlobal('fetch', vi.fn(answer()))
  const { read } = await opened()
  await expect(read({ key: 'k', body: '{}' })).resolves.toEqual({ id: 'saved' })
  await vi.advanceTimersByTimeAsync(1000)  // the progress line's own short timers end
  expect(vi.getTimerCount()).toBe(0)
})
it('sends a read record with its own key and exact body, the same at each attempt', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('lost')).mockImplementation(answer())
  vi.stubGlobal('fetch', fetch)
  const { read } = await opened()
  const pending = { key: '0b9f3c1e-2a4d-4e6f-8a1b-3c5d7e9f1a2b', body: '{"text":"Sony, 700 000 Ar","draft":{"name":null}}' }
  await expect(read(pending)).rejects.toThrow('Connexion')
  await read(pending)
  const [one, two] = fetch.mock.calls.map(call => call[1] as RequestInit)
  expect(fetch.mock.calls[0][0]).toBe('/api/reads')
  expect((one.headers as Record<string, string>)['Idempotency-Key']).toBe(pending.key)
  expect(one.body).toBe(pending.body)
  expect(two.headers).toEqual(one.headers)
  expect(two.body).toBe(one.body)
})

// ── D-MULTI-SHOP-007: the identity gate, the binding, the shop's keys ────────────────────────────────────
import { memory } from './fixture'
// A fresh module with this tab's sessionStorage: the binding is read when the module loads.
async function page(session: Storage | (() => never) = memory()) {
  vi.resetModules()
  vi.stubGlobal('sessionStorage', typeof session === 'function' ? new Proxy({}, { get: session }) : session)
  return import('../src/api')
}
it('opens the gate only while the last answer names the bound shop, hides it while unknown, and signs out on any other identity', async () => {
  const { gate } = await page()
  // A tab without a binding takes its first answer's shop; nobody is the signed-out screen.
  expect([gate(undefined, undefined, true, false), gate(undefined, 3, false, false), gate(undefined, null, false, false)]).toEqual(['hidden', 'shown', 'out'])
  expect(gate(3, 3, false, false)).toBe('shown')
  expect([gate(3, undefined, true, false), gate(3, 3, true, false), gate(3, 3, false, true), gate(3, undefined, false, true)]).toEqual(['hidden', 'hidden', 'hidden', 'hidden'])
  expect(gate(3, 4, false, false)).toBe('out')  // an answer naming another shop
  expect(gate(3, null, false, false)).toBe('out')  // nobody, or a 401 on any request
  expect(gate(3, 'other', false, false)).toBe('out')  // a 409 shop_changed
  expect([gate(3, 4, true, false), gate(3, 'other', false, true)]).toEqual(['out', 'out'])  // evidence wins over a pending or failed answer
  // Bound to nobody after « Se déconnecter »: no answer shows a shop until an explicit sign-in.
  expect([gate(null, undefined, true, false), gate(null, 3, false, false), gate(null, null, false, false)]).toEqual(['out', 'out', 'out'])
})
it('keeps the binding in sessionStorage across reloads, and in memory when it is refused', async () => {
  const session = memory({ 'affiche.bound': '7' })
  let api = await page(session)
  expect(api.bound.value).toBe(7)
  api.bind(null)
  expect(session.getItem('affiche.bound')).toBe('none')
  expect((await page(session)).bound.value).toBeNull()  // a reload stays bound to nobody
  api = await page(session)
  api.bind(2)
  expect((await page(session)).bound.value).toBe(2)
  for (const raw of ['0', '-1', '1.5', 'x', '']) expect((await page(memory({ 'affiche.bound': raw }))).bound.value).toBeUndefined()
  // Refused (some private modes): held in memory for this page; a reload is a new page life.
  api = await page(() => { throw new DOMException('denied', 'SecurityError') })
  expect(api.bound.value).toBeUndefined()
  api.bind(5)
  expect(api.bound.value).toBe(5)
})
it('builds a shop key only once the gate opened on the bound shop', async () => {
  const api = await page()
  expect(() => api.shopKey('style')).toThrow()  // no binding yet
  api.bind(4)
  expect(() => api.shopKey('style')).toThrow()  // bound, but the session has not said so on this page
  api.open()
  expect(api.shopKey('style')).toBe('affiche.shop4.style')
  api.bind(null); api.open()
  expect(() => api.shopKey('style')).toThrow()  // bound to nobody
})
it('sends X-Affiche-Shop once bound to a shop, and hands any other identity to the gate', async () => {
  const api = await page()
  const fetch = vi.fn(async (path: string, init: RequestInit) => path === '/api/gone' ? new Response(JSON.stringify({ error: { code: 'unauthenticated' } }), { status: 401 })
    : path === '/api/other' ? new Response(JSON.stringify({ error: { code: 'shop_changed', message_fr: 'Une autre boutique est connectée dans ce navigateur. Connectez-vous pour continuer.' } }), { status: 409 })
    : path === '/api/session' && init.method === 'POST' ? new Response(JSON.stringify({ error: { code: 'wrong_credentials' } }), { status: 401 })
    : path === '/api/session' ? new Response('{"authenticated":true,"shop_id":3}') : new Response('{}'))
  vi.stubGlobal('fetch', fetch)
  await api.api('/api/session')  // the first answer binds the tab
  api.open()
  await api.api('/api/creations')
  const headers = fetch.mock.calls.map(call => (call as unknown as [string, RequestInit])[1].headers as Record<string, string>)
  expect(headers[0]['X-Affiche-Shop']).toBeUndefined()
  expect(headers[1]['X-Affiche-Shop']).toBe('3')
  await expect(api.api('/api/session', { method: 'POST', body: '{}' })).rejects.toMatchObject({ code: 'wrong_credentials' })
  expect(api.seen.value).toBe(3)  // a wrong password is not another identity
  await expect(api.api('/api/gone')).rejects.toMatchObject({ status: 401 })
  expect(api.seen.value).toBeNull()
  await expect(api.api('/api/other', { method: 'PUT' })).rejects.toMatchObject({ code: 'shop_changed' })
  expect(api.seen.value).toBe('other')
})
it('moves the pilot phone’s keys to shop 1: never over a newer one, never losing one whose copy failed', async () => {
  const { moveLegacy } = await page()
  const storage = memory({ 'affiche.chat.c': 'thread', 'affiche.chat.pending': 'read', 'affiche.words.c': 'words', 'affiche.palette.c': 'colour', 'affiche.style': 'style',
    'affiche.shop1.words.c': 'newer', 'affiche.theme': 'sombre', 'affiche.start': 'chat', 'affiche.identity': 'x', 'affiche.styles': 'other', 'other.chat.c': 'other' },
    key => key === 'affiche.shop1.palette.c')
  moveLegacy(storage)
  expect(Object.fromEntries(storage.map)).toEqual({ 'affiche.shop1.chat.c': 'thread', 'affiche.shop1.chat.pending': 'read', 'affiche.shop1.words.c': 'newer', 'affiche.shop1.style': 'style',
    'affiche.palette.c': 'colour',  // its copy was refused: kept, for the next start
    'affiche.theme': 'sombre', 'affiche.start': 'chat', 'affiche.identity': 'x', 'affiche.styles': 'other', 'other.chat.c': 'other' })
  storage.setItem = (key, value) => { storage.map.set(key, value) }
  moveLegacy(storage)  // the next start resumes
  expect([storage.getItem('affiche.shop1.palette.c'), storage.getItem('affiche.palette.c')]).toEqual(['colour', null])
})
it('names a legacy key only in api.ts: every other site builds its key per shop', () => {
  const sources = import.meta.glob<string>('../src/*.{ts,vue}', { query: '?raw', import: 'default', eager: true })
  expect(Object.keys(sources)).toContain('../src/App.vue')  // the files are read, so that no match means none
  const named = Object.entries(sources).filter(([, text]) => /['"`]affiche\.(chat\.|words\.|palette\.|style\b)/.test(text)).map(([path]) => path)
  expect(named).toEqual(['../src/api.ts'])
})
it('changes the identity under the affiche-identity lock, released only once the answer and the session have answered', async () => {
  const api = await page(), order: string[] = []
  let granted: Promise<unknown> | undefined
  vi.stubGlobal('navigator', { locks: { request: vi.fn((name: string, options: LockOptions, work: () => Promise<unknown>) => {
    order.push(`lock ${name} ${options.mode}`); granted = work().finally(() => order.push('released')); return granted }) } })
  vi.stubGlobal('fetch', vi.fn(async (path: string, init: RequestInit) => {
    const asked = `${init.method ?? 'GET'} ${path}`
    order.push(asked)
    await new Promise(done => setTimeout(done, 5))  // an answer that takes its time
    order.push(`${asked} answered`)
    return new Response(JSON.stringify({ authenticated: true, shop_id: 2 }))
  }))
  await expect(api.identityChange(() => api.api('/api/session', { method: 'POST', body: '{}' }))).resolves.toEqual({ authenticated: true, shop_id: 2 })
  expect(order).toEqual(['lock affiche-identity exclusive', 'POST /api/session', 'POST /api/session answered', 'GET /api/session', 'GET /api/session answered', 'released'])
  // The change refused: the lock still waits for the session's answer, and the refusal is the caller's.
  order.length = 0
  await expect(api.identityChange(async () => { throw new Error('refused') })).rejects.toThrow('refused')
  expect(order).toEqual(['lock affiche-identity exclusive', 'GET /api/session', 'GET /api/session answered', 'released'])
  // Without Web Locks the same steps run, unserialised.
  vi.stubGlobal('navigator', {})
  order.length = 0
  await api.identityChange(() => api.api('/api/session', { method: 'DELETE' }))
  expect(order).toEqual(['DELETE /api/session', 'DELETE /api/session answered', 'GET /api/session', 'GET /api/session answered'])
})
it('gives a sign-in or sign-out 30 s inside the lock, then lets the lock go', async () => {
  vi.useFakeTimers()
  const api = await page()
  vi.stubGlobal('navigator', {})
  vi.stubGlobal('fetch', vi.fn((_path: string, init: RequestInit) => new Promise<Response>((_done, fail) => init.signal?.addEventListener('abort', () => fail(new DOMException('aborted', 'AbortError'))))))
  const outcome = api.identityChange(() => api.api('/api/session', { method: 'POST', body: '{}', timeout: api.IDENTITY_TIMEOUT_MS })).catch(reason => reason)
  await vi.advanceTimersByTimeAsync(30_000)  // the sign-in is given up
  await vi.advanceTimersByTimeAsync(30_000)  // and so is the session asked after it
  expect(await outcome).toMatchObject({ code: 'timeout' })
})
it('signs out on the server and nothing else: a lost answer is checked against the session (ADR-108)', async () => {
  const api = await page()
  let signedIn = true  // what GET /api/session says after the sign-out
  const fetch = vi.fn(async (_path: string, init?: RequestInit) => new Response(init?.method === 'DELETE' || !signedIn ? '{"authenticated":false}' : '{"authenticated":true,"shop_id":1}'))
  vi.stubGlobal('fetch', fetch)
  api.bind(1); api.open()
  await api.endSession()
  expect(fetch.mock.calls.map(([path, init]) => [path, (init as RequestInit | undefined)?.method])).toEqual([['/api/session', 'DELETE']])
  // Offline, the session still this shop's: still signed in, and the sentence says so.
  fetch.mockRejectedValueOnce(new Error('offline'))
  await expect(api.endSession()).rejects.toThrow('Déconnexion impossible : la connexion au serveur est interrompue. Réessayez.')
  // Its answer lost while the server ended the session (review r2 P1-1): the session says so, and the sign-out goes on.
  // The session's own answer lost too: not known, still signed in.
  signedIn = false
  fetch.mockRejectedValueOnce(new Error('lost'))
  await expect(api.endSession()).resolves.toBeUndefined()
  fetch.mockRejectedValueOnce(new Error('lost')).mockRejectedValueOnce(new Error('lost'))
  await expect(api.endSession()).rejects.toThrow('Déconnexion impossible')
  // Another tab already changed the shop: this shop's session is gone, and the sign-out goes on.
  fetch.mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'shop_changed' } }), { status: 409 }))
  await expect(api.endSession()).resolves.toBeUndefined()
})

// ── review r1 of T-MULTI-SHOP-006 ─────────────────────────────────────────────────────────────────────
// P1-1: a request sent before the page knows its shop could bring another shop's data into it.
it('sends no shop request before the gate has opened, and never returns an answer sent under another binding', async () => {
  const api = await page(), sent: string[] = []
  let release: (() => void) | undefined
  vi.stubGlobal('fetch', vi.fn((path: string) => {
    sent.push(path)
    return path === '/api/creations/b' ? new Promise<Response>(done => { release = () => done(new Response('{"id":"b"}')) })
      : Promise.resolve(new Response('{"authenticated":true,"shop_id":3}'))
  }))
  await expect(api.api('/api/creations/b')).rejects.toMatchObject({ code: 'gate_closed' })  // no binding yet
  await api.api('/api/session')  // the session itself is always asked
  api.bind(3)
  await expect(api.api('/api/creations/b')).rejects.toMatchObject({ code: 'gate_closed' })  // bound, the gate not open yet
  expect(sent).toEqual(['/api/session'])
  api.open()
  const late = api.api('/api/creations/b')
  api.bind(null)  // « Se déconnecter » while its answer is on its way
  release!()
  await expect(late).rejects.toMatchObject({ code: 'gate_closed' })
})
// P1-4: identity evidence is acted on before the body is read.
it('hands a 401 to the gate before its body is read, and asks the session again for a 409 it cannot read', async () => {
  const api = await page(), sent: string[] = []
  api.bind(1); api.open(); api.seen.value = 1
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    sent.push(path)
    return path === '/api/slow' ? new Response(new ReadableStream(), { status: 401 })  // a body that never comes
      : path === '/api/session' ? new Response('{"authenticated":true,"shop_id":1}') : new Response('<html>proxy</html>', { status: path === '/api/garbled' ? 401 : 409 })
  }))
  void api.api('/api/slow')
  await vi.waitFor(() => expect(api.seen.value).toBeNull())
  api.seen.value = 1
  await expect(api.api('/api/garbled')).rejects.toMatchObject({ code: 'invalid_response' })
  expect(api.seen.value).toBeNull()
  api.seen.value = 1
  await expect(api.api('/api/conflict', { method: 'PUT' })).rejects.toMatchObject({ code: 'invalid_response' })
  expect(api.seen.value).toBe(1)  // a 409 that cannot be read is not said to be another shop: the session decides
  await vi.waitFor(() => expect(sent.at(-1)).toBe('/api/session'))
})

// ── review r2 of T-MULTI-SHOP-006 ─────────────────────────────────────────────────────────────────────
const reply = (body: object) => new Response(JSON.stringify(body))
// P1-1: every answer of GET /api/session, whoever asks, and every failure of one, goes through the gate's one function.
it('applies to the gate the session answer asked inside a sign-out whose own answer was lost', async () => {
  const api = await page()
  let signedIn = true
  vi.stubGlobal('fetch', vi.fn(async (_path: string, init?: RequestInit) => init?.method === 'DELETE' ? Promise.reject(new Error('lost'))
    : reply(signedIn ? { authenticated: true, shop_id: 1 } : { authenticated: false })))
  await api.ask()
  expect([api.bound.value, api.state.value]).toEqual([1, 'shown'])
  api.open()
  signedIn = false  // the server ended the session; its answer never came
  await expect(api.identityChange(api.endSession)).resolves.toBeUndefined()
  expect(api.state.value).toBe('out')
})
it('lets a late session answer close the gate, never open it; a failed one hides the shop; another shop signs it out', async () => {
  const api = await page(), calls: { resolve: (response: Response) => void; reject: (reason: Error) => void }[] = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve, reject) => calls.push({ resolve, reject }))))
  const shop = { authenticated: true, shop_id: 1 }
  const first = api.ask(); calls[0].resolve(reply(shop)); await first
  expect(api.state.value).toBe('shown')
  // Two on their way: the newer fails first, then the older names the shop. Hidden, « Réessayer ».
  const older = api.api('/api/session').catch(() => undefined), newer = api.ask()
  calls[2].reject(new Error('offline')); await newer
  calls[1].resolve(reply(shop)); await older
  expect([api.state.value, api.failed.value]).toEqual(['hidden', 'lost'])
  // The newer names the shop, then the older names nobody: that closes it.
  const older2 = api.api('/api/session').catch(() => undefined), newer2 = api.ask()
  calls[4].resolve(reply(shop)); await newer2
  expect(api.state.value).toBe('shown')
  calls[3].resolve(reply({ authenticated: false })); await older2
  expect(api.state.value).toBe('out')
  // Signed out stays signed out: showing the shop again takes an explicit sign-in on the page (rule 4).
  const again = api.ask(); calls[5].resolve(reply(shop)); await again
  expect(api.state.value).toBe('out')
  // Another shop's answer, whoever asked, is the signed-out screen too.
  const other = await page(), more: ((response: Response) => void)[] = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => more.push(resolve))))
  const start = other.ask(); more[0](reply(shop)); await start
  const change = other.identityChange(async () => undefined)
  await vi.waitFor(() => expect(more).toHaveLength(2))
  more[1](reply({ authenticated: true, shop_id: 2 })); await change
  expect([other.state.value, other.seen.value]).toEqual(['out', 2])
})
// P1-3: the shop's images are asked like any request of the shop.
it('asks for the shop’s images with its header, behind the gate, and hands a 401 to the gate', async () => {
  const api = await page()
  const fetch = vi.fn(async (path: string) => path === '/api/assets/a' ? new Response(new Blob(['png'])) : new Response('{"error":{"code":"unauthenticated"}}', { status: 401 }))
  vi.stubGlobal('fetch', fetch)
  await expect(api.api('/api/assets/a', { as: 'blob' })).rejects.toMatchObject({ code: 'gate_closed' })
  api.bind(2); api.open(); api.seen.value = 2
  expect(await (await api.api<Blob>('/api/assets/a', { as: 'blob' })).text()).toBe('png')
  expect((fetch.mock.calls[0] as unknown as [string, RequestInit])[1].headers).toMatchObject({ 'X-Affiche-Shop': '2' })
  await expect(api.api('/api/assets/b', { as: 'blob' })).rejects.toMatchObject({ status: 401 })
  expect(api.seen.value).toBeNull()
})
it('fetches nothing of the server outside api.ts: the canvas and the palette go through it, fonts and data: addresses aside', () => {
  const sources = import.meta.glob<string>('../src/*.{ts,vue}', { query: '?raw', import: 'default', eager: true })
  const fetching = Object.entries(sources).filter(([, text]) => /\bfetch\(/.test(text)).map(([path]) => path).sort()
  expect(fetching).toEqual(['../src/PosterCanvas.vue', '../src/api.ts', '../src/fonts.ts'])
  expect(sources['../src/fonts.ts']).toMatch(/fetch\(injected\?\.\[entry\.file\] \?\? `\/fonts\//)  // public files
  expect(sources['../src/PosterCanvas.vue']).toMatch(/startsWith\('\/api\/'\)\) return api<Blob>/)  // a data: address otherwise (the renderer)
})
// P2-4: no write of a shop's key once the page is no longer bound to that shop, whenever the key was built.
it('writes a shop key only while that shop is open on the page, whenever the key was built', async () => {
  const api = await page(), storage = memory()
  vi.stubGlobal('localStorage', storage)
  api.bind(1); api.open()
  const key = api.shopKey('chat.c')
  api.shopStorage.setItem(key, 'thread')
  api.bind(null)  // « Se déconnecter »
  expect(() => api.shopStorage.setItem(key, 'late')).toThrow()
  expect(() => api.shopStorage.removeItem(key)).toThrow()
  api.bind(2); api.open()
  expect(() => api.shopStorage.setItem(key, 'another shop')).toThrow()
  expect(storage.getItem(key)).toBe('thread')
})
// ADR-108: a sign-out in another tab deletes the shop's keys; a late answer in this tab, still bound, writes none back.
// A session that only ended here (a 401) deleted nothing: the chat still writes what it will show after the sign-in.
it('writes no shop key once another tab changed the identity and the gate is out; a session that only ended still writes', async () => {
  const api = await page(), storage = memory()
  vi.stubGlobal('localStorage', storage)
  let signedIn = true
  vi.stubGlobal('fetch', vi.fn(async () => reply(signedIn ? { authenticated: true, shop_id: 1 } : { authenticated: false })))
  await api.ask()
  api.open()
  const key = api.shopKey('chat.c')
  api.shopStorage.setItem(key, 'thread')
  signedIn = false  // the session ended: this page alone finds out
  await api.ask()
  expect([api.bound.value, api.state.value]).toEqual([1, 'out'])
  api.shopStorage.setItem(key, 'the card that says to sign in')
  expect(storage.getItem(key)).toBe('the card that says to sign in')
})
// Review r5 P2-1: from another tab's identity event on, nothing of the shop is written here until an answer asked after
// that event names this page's shop: not while that check is on its way (hidden), nor after it failed, nor after one
// asked before the event confirms the shop late.
it('writes no shop key from another tab’s identity event until a later session answer confirms the shop', async () => {
  const api = await page(), storage = memory()
  vi.stubGlobal('localStorage', storage)
  const answers: ((response: Response) => void)[] = []
  const fetch = vi.fn(() => new Promise<Response>(done => answers.push(done)))
  vi.stubGlobal('fetch', fetch)
  const confirm = () => reply({ authenticated: true, shop_id: 1 })
  const first = api.ask(); answers.shift()!(confirm()); await first
  api.open()
  const key = api.shopKey('chat.c'), write = (value: string) => api.shopStorage.setItem(key, value)
  const early = api.api('/api/session', { quiet: true })  // asked before the event: it confirms the shop, late
  const check = api.changedElsewhere()  // another tab signed out and deleted the shop's keys
  expect(api.state.value).toBe('hidden')
  expect(() => write('late answer, check on its way')).toThrow()
  answers.shift()!(confirm()); await early
  expect(() => write('late answer after an earlier confirmation')).toThrow()
  answers.shift()!(Promise.reject(new Error('lost')) as unknown as Response); await check
  expect([api.state.value, api.failed.value]).toEqual(['hidden', 'lost'])
  expect(() => write('late answer, check failed')).toThrow()
  expect(storage.getItem(key)).toBeNull()
  const again = api.ask(); answers.shift()!(confirm()); await again  // « Réessayer »: this shop, confirmed
  expect(api.state.value).toBe('shown')
  write('the shop again')
  expect(storage.getItem(key)).toBe('the shop again')
})
it('writes a shop key nowhere but through shopStorage; plain writes are the device’s own keys', () => {
  const sources = import.meta.glob<string>('../src/*.{ts,vue}', { query: '?raw', import: 'default', eager: true })
  const plain = Object.entries(sources).filter(([path]) => path !== '../src/api.ts')
    .flatMap(([path, text]) => [...text.matchAll(/localStorage\.(?:setItem|removeItem)\((\w+)/g)].map(match => `${path} ${match[1]}`))
  // RAIL_KEY twice: set when the rail is chosen, removed when the sidebar comes back (D-REDESIGN-002).
  expect(plain.sort()).toEqual(['../src/App.vue RAIL_KEY', '../src/App.vue RAIL_KEY', '../src/App.vue START_KEY', '../src/App.vue THEME_KEY'])
})
// P2-5: the cleanup at sign-out is by prefix, listed afresh, and says when it is unfinished.
it('forgets every key of a shop by its prefix, with no exception, and shop 1’s keys from before the shops; unfinished when anything refuses', async () => {
  const api = await page()
  // A thread whose paid card waits goes like the rest (ADR-108).
  const waiting = JSON.stringify({ at: 1, items: [{ id: 'paid', role: 'app', text: '', at: 1, spent: true, request: { path: '/api/creations/c/scenes', body: {}, revision: 1 }, card: { kind: 'recap' } }] })
  const storage = memory({ 'affiche.shop1.chat.c': waiting, 'affiche.shop1.style': 's', 'affiche.style': 'old', 'affiche.words.x': 'old',
    'affiche.shop2.style': 'b', 'affiche.theme': 'sombre', 'affiche.start': 'chat', 'affiche.identity': 'i' })
  expect(api.forgetShop(storage, 1)).toBe(true)
  expect([...storage.map.keys()].sort()).toEqual(['affiche.identity', 'affiche.shop2.style', 'affiche.start', 'affiche.theme'])
  const refusing = memory({ 'affiche.shop2.style': 'b', 'affiche.shop2.words.x': 'w', 'affiche.style': 'shop 1’s' }), remove = refusing.removeItem
  refusing.removeItem = key => { if (key === 'affiche.shop2.style') throw new DOMException('denied', 'SecurityError'); remove(key) }
  expect(api.forgetShop(refusing, 2)).toBe(false)  // unfinished
  refusing.removeItem = remove
  expect(api.forgetShop(refusing, 2)).toBe(true)  // the next try lists the shop's keys again
  expect([...refusing.map.keys()]).toEqual(['affiche.style'])  // another shop's sign-out never touches shop 1's
  const unlisted = memory({ 'affiche.shop1.style': 's' })
  Object.defineProperty(unlisted, 'length', { get: () => { throw new DOMException('denied', 'SecurityError') } })
  expect(api.forgetShop(unlisted, 1)).toBe(false)  // not listed: unfinished, never an empty success
  expect(api.forgetShop(null, 1)).toBe(false)
})

// D-TERMS-004: a refusal for want of the conditions, whatever request it answers, has the page read and show them.
it('moves termsAsked on a terms_required refusal only', async () => {
  vi.resetModules()
  const refusal = (status: number, code: string) => async () => new Response(JSON.stringify({ error: { code, message_fr: 'Refusé.' } }), { status })
  vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(refusal(403, 'terms_required')).mockImplementationOnce(refusal(403, 'forbidden_origin'))
    .mockImplementationOnce(refusal(402, 'no_credit')).mockImplementationOnce(answer()).mockImplementationOnce(refusal(403, 'terms_required')))
  const { api, mutation, read, termsAsked } = await opened()
  expect(termsAsked.value).toBe(0)
  await expect(mutation('/api/creations/c/scenes', {}, 1)).rejects.toThrow('Refusé.')
  expect(termsAsked.value).toBe(1)
  await expect(api('/api/terms', { method: 'POST', body: '{}' })).rejects.toThrow('Refusé.')
  await expect(api('/api/creations/c/scenes', { method: 'POST' })).rejects.toThrow('Refusé.')
  await api('/api/balance')
  expect(termsAsked.value).toBe(1)
  await expect(read({ key: 'r', body: '{}' })).rejects.toThrow('Refusé.')  // a chat message too
  expect(termsAsked.value).toBe(2)
})
// The turn rule: among reads only the latest counts; a confirmed acceptance always counts and voids every read started
// before it, whichever answers first; « Plus tard » voids the reads on their way.
it('lets a confirmed acceptance win over every read started before it, and keeps the order among reads', async () => {
  vi.resetModules()
  const release: Array<(body: unknown, status?: number) => void> = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => release.push((body, status = 200) => done(new Response(JSON.stringify(body), { status }))))))
  const { acceptConditions, conditions, voidReads } = await opened()
  const unaccepted = { version: '2026-11-17', paragraphs_fr: ['…'], accepted_at: null, changed: false }
  const accepted = { version: '2026-11-17', accepted_at: 'now' }
  // « J’accepte », « Plus tard », « Lire les conditions »: the read reaches the server before the acceptance commits.
  const accepting = acceptConditions('2026-11-17'), overlapping = conditions()
  release[0](accepted)
  expect(await accepting).toEqual(accepted)
  release[1](unaccepted)
  expect(await overlapping).toBeUndefined()  // answered after the confirmation: it never reopens the dialog
  // The other order: the read answers first and counts (the dialog shows it); the confirmation still counts after it.
  const second = acceptConditions('2026-11-17'), first = conditions()
  release[3](unaccepted)
  expect(await first).toEqual(unaccepted)
  release[2](accepted)
  expect(await second).toEqual(accepted)
  const after = conditions()  // a read started after the confirmation counts
  release[4]({ ...unaccepted, accepted_at: 'now' })
  expect((await after as { accepted_at: string }).accepted_at).toBe('now')
  // Among reads, the latest: an older answer arriving last is ignored, and an overtaken failure is not thrown.
  const older = conditions(), latest = conditions()
  release[6](unaccepted); release[5]({ error: { code: 'storage_unavailable', message_fr: 'Indisponible.' } }, 503)
  expect([await latest, await older]).toEqual([unaccepted, undefined])
  const failing = conditions()
  release[7]({ error: { code: 'storage_unavailable', message_fr: 'Indisponible.' } }, 503)
  await expect(failing).rejects.toThrow('Indisponible.')
  // « Plus tard »: the reads on their way count no more, success or failure; the next one does.
  const retry = conditions(), reread = conditions()
  voidReads()
  release[8](unaccepted); release[9]({ error: { code: 'timeout', message_fr: 'Trop long.' } }, 503)
  expect([await retry, await reread]).toEqual([undefined, undefined])
  const next = conditions()
  release[10](unaccepted)
  expect(await next).toEqual(unaccepted)
  const sent = vi.mocked(fetch).mock.calls.map(call => [call[0], (call[1] as RequestInit).method ?? 'GET', (call[1] as RequestInit).body])
  expect(sent[0]).toEqual(['/api/terms', 'POST', JSON.stringify({ version: '2026-11-17' })])
  expect(sent[1]).toEqual(['/api/terms', 'GET', undefined])
})
// Neither request waits for ever: « J’accepte » is enabled again, and a read asked by a control ends in « Réessayer ».
// The page's own read at opening is quiet: no progress line for a shop that has accepted.
it('gives up both conditions requests after TERMS_TIMEOUT_MS, and reads quietly at opening', async () => {
  vi.useFakeTimers(); vi.resetModules()
  vi.stubGlobal('fetch', vi.fn((_path: string, init: RequestInit) => new Promise<Response>((_done, fail) => {
    init.signal?.addEventListener('abort', () => fail(new DOMException('aborted', 'AbortError')))
  })))
  const { acceptConditions, conditions, progress, TERMS_TIMEOUT_MS } = await opened()
  const opening = conditions(true).catch(reason => reason)
  await vi.advanceTimersByTimeAsync(1000)
  expect(progress.value).toBe(false)
  await vi.advanceTimersByTimeAsync(TERMS_TIMEOUT_MS - 1000)
  expect(await opening).toMatchObject({ code: 'timeout' })
  let ended = false
  const accept = acceptConditions('2026-11-17').catch(reason => reason), read = conditions().catch(reason => reason)
  void Promise.race([accept, read]).then(() => { ended = true })
  await vi.advanceTimersByTimeAsync(300)
  expect(progress.value).toBe(true)  // asked by a control: the owner waits for it
  await vi.advanceTimersByTimeAsync(TERMS_TIMEOUT_MS - 301)
  expect(ended).toBe(false)
  await vi.advanceTimersByTimeAsync(1)
  expect([await accept, await read]).toEqual([expect.objectContaining({ code: 'timeout' }), expect.objectContaining({ code: 'timeout' })])
})

it('times out a password change once and keeps no replay signature', async () => {
  vi.useFakeTimers(); vi.resetModules()
  const fetch = vi.fn((_path: string, init: RequestInit) => new Promise<Response>((_, fail) => {
    init.signal?.addEventListener('abort', () => fail(new DOMException('aborted', 'AbortError')))
  }))
  vi.stubGlobal('fetch', fetch)
  const { changePassword, retained } = await opened()
  const outcome = changePassword('old', 'replacement').catch(reason => reason)
  await vi.advanceTimersByTimeAsync(20_000)
  expect(await outcome).toMatchObject({ code: 'timeout' })
  expect(fetch).toHaveBeenCalledTimes(1)
  const [url, init] = fetch.mock.calls[0]!
  expect(url).toBe('/api/session/password')
  expect(init.headers).not.toHaveProperty('Idempotency-Key')
  expect(retained(url)).toBe(false)
})
