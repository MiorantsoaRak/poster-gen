import { afterEach, expect, it, vi } from 'vitest'
import { bind, open } from '../src/api'
import { clearFacebookOrigin, facebookCard, keepFacebookOrigin, manualReturnLine, panelLine, postsAddress, startFacebook, takeFacebookOrigin } from '../src/facebook'
import type { Post } from '../src/publish'

// The shop's requests leave only once the gate has opened on the bound shop: shop 2 here (before any storage is stubbed).
bind(2); open()

const page = { id: '100000000000001', name: 'Page d’essai 1', state: 'connected' as const }
const choice = [{ id: '100000000000001', name: 'Page d’essai 1' }, { id: '100000000000002', name: 'Page d’essai 2' }]

afterEach(() => vi.unstubAllGlobals())
function tabStorage() {
  const data = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  return data
}
it('restores a batch or single publication only once and only to the rebound shop', () => {
  const data = tabStorage()
  for (const origin of ['publier', 'publier-' + crypto.randomUUID()]) {
    expect(keepFacebookOrigin(2, origin)).toBe(true)
    expect(takeFacebookOrigin(2)).toBe(origin)
    expect(takeFacebookOrigin(2)).toBeNull()
    expect(keepFacebookOrigin(2, origin)).toBe(true)
    expect(takeFacebookOrigin(3)).toBeNull()
    expect(data.size).toBe(0)
    expect(keepFacebookOrigin(2, origin)).toBe(true)
    clearFacebookOrigin()
    expect(takeFacebookOrigin(2)).toBeNull()
  }
})
it('discards malformed storage and destinations outside the publication routes', () => {
  const data = tabStorage()
  for (const from of ['https://example.com', 'publier?code=123', 'publier-' + '-'.repeat(36)]) {
    expect(keepFacebookOrigin(2, from)).toBe(false)
    keepFacebookOrigin(2, 'publier')
    data.set([...data.keys()][0], JSON.stringify({ shop: 2, origin: from }))
    expect(takeFacebookOrigin(2)).toBeNull()
    expect(data.size).toBe(0)
  }
  keepFacebookOrigin(2, 'publier')
  data.set([...data.keys()][0], '{')
  expect(takeFacebookOrigin(2)).toBeNull()
  expect(data.size).toBe(0)
})
it('offers the manual return when the browser silently drops the marker', () => {
  vi.stubGlobal('sessionStorage', { setItem() {}, getItem: () => null })
  expect(keepFacebookOrigin(1, 'publier')).toBe(false)
})

it('uses ordinary navigation if the tab refuses storage', () => {
  vi.stubGlobal('sessionStorage', undefined)
  expect(keepFacebookOrigin(2, 'publier')).toBe(false)
  expect(takeFacebookOrigin(2)).toBeNull()
  expect(() => clearFacebookOrigin()).not.toThrow()
})

it('keeps the publish origin before it leaves for Facebook, and nothing when the request fails', async () => {
  const data = tabStorage(), dialog = 'https://www.facebook.com/v23.0/dialog/oauth?state=s'
  const leaving: string[] = []  // what this tab keeps at the moment it leaves
  const assign = vi.fn(() => { leaving.push(...data.values()) })
  vi.stubGlobal('location', { assign })
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ url: dialog }))))
  const origin = 'publier-' + crypto.randomUUID()
  expect(await startFacebook(2, origin)).toBe('left')
  expect(assign).toHaveBeenCalledWith(dialog)
  expect(leaving.map(record => JSON.parse(record))).toEqual([{ shop: 2, origin }])
  expect(takeFacebookOrigin(2)).toBe(origin)
  // « Mon compte » with no publish origin: it leaves, keeping nothing.
  expect(await startFacebook(2, null)).toBe('left')
  expect(data.size).toBe(0)
  // The page that asked is gone once the answer is in: nothing kept, the tab stays.
  expect(await startFacebook(2, 'publier', { still: () => false })).toBe('stopped')
  expect(data.size).toBe(0)
  expect(assign).toHaveBeenCalledTimes(2)
  // The request fails: its error is the caller's sentence; nothing kept, the tab stays.
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: { code: 'facebook_off', message_fr: 'Indisponible.' } }), { status: 503 })))
  await expect(startFacebook(2, 'publier')).rejects.toThrow('Indisponible.')
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('offline') }))
  await expect(startFacebook(2, 'publier')).rejects.toThrow('Connexion interrompue.')
  expect(data.size).toBe(0)
  expect(assign).toHaveBeenCalledTimes(2)
  // The tab refuses to leave: what was kept is taken back.
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ url: dialog }))))
  assign.mockImplementationOnce(() => { throw new DOMException('Refusé', 'SecurityError') })
  await expect(startFacebook(2, 'publier')).rejects.toThrow('Refusé')
  expect(data.size).toBe(0)
})

it('says when this tab cannot keep the return, then leaves without it on the next tap', async () => {
  vi.stubGlobal('sessionStorage', { setItem() {}, getItem: () => null, removeItem() {} })
  const assign = vi.fn()
  vi.stubGlobal('location', { assign })
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ url: 'https://www.facebook.com/dialog' }))))
  expect(await startFacebook(2, 'publier')).toBe('unkept')
  expect(assign).not.toHaveBeenCalled()
  expect(await startFacebook(2, 'publier', { unkept: true })).toBe('left')
  expect(assign).toHaveBeenCalledOnce()
  expect(manualReturnLine('publier')).toBe('Ce navigateur ne peut pas mémoriser le retour. Après Facebook, ouvrez « Publier » depuis le menu.')
  expect(manualReturnLine('publier-' + crypto.randomUUID())).toBe('Ce navigateur ne peut pas mémoriser le retour. Après Facebook, ouvrez « Mes affiches », puis l’affiche à publier.')
})

it('gives the card the form of what the server says, a waiting choice first', () => {
  expect(facebookCard({ page: null, choice: null })).toBe('connect')
  expect(facebookCard({ page: null, choice: [] })).toBe('connect')
  expect(facebookCard({ page, choice: null })).toBe('connected')
  expect(facebookCard({ page: { ...page, state: 'reconnect' }, choice: null })).toBe('reconnect')
  expect(facebookCard({ page: null, choice })).toBe('choose')
  expect(facebookCard({ page, choice: choice.slice(1) })).toBe('choose')  // back from Facebook with a Page connected before
  expect(facebookCard({ page: null, choice: null, last_error: { code: 'facebook_failed', message_fr: 'x' } })).toBe('connect')
})

const post = (status: Post['status'], change: Partial<Post> = {}): Post => ({
  id: crypto.randomUUID(), status, page_id: page.id, page_name: page.name, sent_at: '2026-11-21T08:00:00.000000+00:00',
  settled_at: null, count: 1, done: 1, failed_position: null, link: null, error_code: null, said_by_owner: false,
  stop_asked: false, message_fr: `ligne ${status}`, items: [], ...change })

it('says on the final panel whether the poster went alone, the state, Facebook’s link, and an unknown one to answer', () => {
  const link = 'https://www.facebook.com/100000000000001_42'
  expect(panelLine(post('published', { link }))).toEqual({ alone: 'seule', state: 'ligne published', link, answer: false })
  expect(panelLine(post('published', { link, count: 3 })).alone).toBe('dans une publication de 3 images')
  // The owner's word links to the Page, not to a post: no « Voir la publication ».
  expect(panelLine(post('published', { link: 'https://www.facebook.com/100000000000001', said_by_owner: true })).link).toBeNull()
  expect(panelLine(post('published', { link: 'https://evil.example/x' })).link).toBeNull()
  expect(panelLine(post('unknown'))).toEqual({ alone: 'seule', state: 'ligne unknown', link: null, answer: true })
  for (const status of ['uploading', 'posting', 'failed'] as const)
    expect(panelLine(post(status, { link }))).toEqual({ alone: 'seule', state: `ligne ${status}`, link: null, answer: false })
})

it('reads the posts of a poster a page at a time, the next one after the last post shown', () => {
  expect(postsAddress('c1', null)).toBe('/api/facebook/posts?creation=c1')
  expect(postsAddress('c1', 'p 20')).toBe('/api/facebook/posts?creation=c1&before=p%2020')
})
