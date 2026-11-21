import { expect, it } from 'vitest'
import { facebookCard } from '../src/facebook'

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
