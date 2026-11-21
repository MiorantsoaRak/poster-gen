import { expect, it } from 'vitest'
import { facebookCard, lineOf, publishAction, publishedOn, seenOf, type Publication } from '../src/facebook'

const page = { id: '100000000000001', name: 'Page d’essai 1', state: 'connected' as const }
const choice = [{ id: '100000000000001', name: 'Page d’essai 1' }, { id: '100000000000002', name: 'Page d’essai 2' }]

it('gives the card the form of what the server says, a waiting choice first', () => {
  expect(facebookCard({ page: null, choice: null })).toBe('connect')
  expect(facebookCard({ page: null, choice: [] })).toBe('connect')
  expect(facebookCard({ page, choice: null })).toBe('connected')
  expect(facebookCard({ page: { ...page, state: 'reconnect' }, choice: null })).toBe('reconnect')
  expect(facebookCard({ page: null, choice })).toBe('choose')
  expect(facebookCard({ page, choice: choice.slice(1) })).toBe('choose')  // back from Facebook with a Page connected before
  expect(facebookCard({ page: null, choice: null, last_error: { code: 'facebook_failed', message_fr: 'x' } })).toBe('connect')
})

const item = (status: Publication['status'], change: Partial<Publication> = {}): Publication => ({
  id: crypto.randomUUID(), status, page_id: page.id, page_name: page.name, sent_at: '2026-11-21T08:00:00.000000+00:00',
  settled_at: null, link: null, error_code: null, said_by_owner: false, message_fr: `ligne ${status}`, ...change })
const elsewhere = (status: Publication['status']) => item(status, { page_id: '100000000000002', page_name: 'Page d’essai 2' })

it('leads to « Mon compte » without a connected Page, offers nothing while an outcome waits on this Page, else the sheet', () => {
  expect(publishAction(null, [])).toBe('account')
  expect(publishAction({ ...page, state: 'reconnect' }, [item('published')])).toBe('account')
  expect(publishAction(page, [])).toBe('sheet')
  expect(publishAction(page, [item('published'), item('failed')])).toBe('sheet')
  expect(publishAction(page, [item('published'), item('sending')])).toBe('wait')
  expect(publishAction(page, [item('unknown')])).toBe('wait')
  expect(publishAction(page, [elsewhere('unknown'), elsewhere('sending')])).toBe('sheet')  // another Page's wait is not this one's
})

it('sends as seen the last publication on this Page, and says the last one that is on it', () => {
  const [newest, published, older] = [item('failed'), item('published', { said_by_owner: true }), item('published')]
  expect(seenOf(page, [])).toBeNull()
  expect(seenOf(page, [elsewhere('published')])).toBeNull()
  expect(seenOf(page, [elsewhere('failed'), newest, published, older])).toBe(newest.id)
  expect(publishedOn(page, [elsewhere('published'), newest])).toBeNull()
  expect(publishedOn(page, [elsewhere('published'), newest, published, older])).toBe(published)
})

it('shows each line with its link and asks the owner only for an unknown outcome', () => {
  const post = 'https://www.facebook.com/100000000000001_42'
  expect(lineOf(item('published', { link: post }))).toEqual({ state: 'ligne published', link: { href: post, label: 'Voir la publication' }, ask: false })
  expect(lineOf(item('published', { link: 'https://www.facebook.com/100000000000001', said_by_owner: true })).link)
    .toEqual({ href: 'https://www.facebook.com/100000000000001', label: 'Ouvrir la Page' })
  expect(lineOf(item('unknown'))).toEqual({ state: 'ligne unknown', link: { href: 'https://www.facebook.com/100000000000001', label: 'Ouvrir ma Page' }, ask: true })
  for (const status of ['sending', 'failed'] as const) expect(lineOf(item(status, { link: post }))).toEqual({ state: `ligne ${status}`, link: null, ask: false })
  expect(lineOf(item('published', { link: 'https://evil.example/x' })).link).toBeNull()
  expect(lineOf(item('published', { link: null })).link).toBeNull()
})
