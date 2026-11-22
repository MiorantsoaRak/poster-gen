import { afterEach, expect, it, vi } from 'vitest'
import { clearFacebookOrigin, facebookCard, keepFacebookOrigin, panelLine, postsAddress, takeFacebookOrigin } from '../src/facebook'
import type { Post } from '../src/publish'

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
