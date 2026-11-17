import { afterEach, expect, it, vi } from 'vitest'
import { BUNDLE } from '../src/api'
import { AdminError, BUNDLE as ADMIN_BUNDLE, call, newEpoch } from '../src/admin/adminApi'
import { NOT_SET, route, sentence, uncertain } from '../src/admin/admin'

afterEach(() => { vi.unstubAllGlobals() })

// Every source file and entry page as text (Vite's glob: the project has no Node types).
const sources = import.meta.glob<string>(['../src/**/*.{ts,vue,css}', '../index.html', '../render.html', '../admin/index.html'],
  { query: '?raw', import: 'default', eager: true })
const imports = (text: string) => [...text.matchAll(/(?:\bfrom\s*|\bimport\s*\(?\s*|url\(\s*)['"]([^'"]+)['"]/g)].map(found => found[1]!)
const links = (page: string) => [...sources[page]!.matchAll(/\b(?:src|href)="([^"]+)"/g)].map(found => found[1]!)
const admin = Object.entries(sources).filter(([path]) => path.startsWith('../src/admin/'))

it('keeps the operator page and the shops apart: neither imports the other (D-ADMIN-005)', () => {
  expect(admin.map(([path]) => path).sort()).toEqual(['Admin.vue', 'Confirm.vue', 'admin.css', 'admin.ts', 'adminApi.ts', 'main.ts'].map(name => `../src/admin/${name}`).sort())
  for (const [path, text] of admin)
    for (const name of imports(text)) expect(name === 'vue' || /^\.\/[^/]+$/.test(name), `${path} imports ${name}`).toBe(true)
  const shops = Object.entries(sources).filter(([path]) => path.startsWith('../src/') && !path.startsWith('../src/admin/'))
  expect(shops.length).toBeGreaterThan(10)
  for (const [path, text] of shops)
    for (const name of imports(text)) expect(/(^|\/)admin(\/|$)/.test(name), `${path} imports ${name}`).toBe(false)
  expect(links('../admin/index.html')).toEqual(['/src/admin/main.ts'])
  for (const page of ['../index.html', '../render.html']) expect(links(page).filter(link => link.includes('admin'))).toEqual([])
})

it('names the same bundle as the shops, so that the server refuses both old pages together (ADR-103)', () => {
  expect(ADMIN_BUNDLE).toBe(BUNDLE)
})

it('reads the view from the hash: one shop by its id, anything else the shop list', () => {
  expect(route('#/shops/12')).toEqual({ view: 'shop', id: 12 })
  for (const hash of ['', '#', '#/shops', '#/shops/', '#/shops/0', '#/shops/012', '#/shops/12/x', '#/shops/-1', '#/shops/1e3', '#/service'])
    expect(route(hash), hash).toEqual({ view: 'shops' })
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
