import { afterEach, expect, it, vi } from 'vitest'
import { api, clockSkew, mutation } from '../src/api'

afterEach(() => vi.unstubAllGlobals())
const answer = (headers: Record<string, string> = {}) => async () => new Response(JSON.stringify({ id: 'saved' }), { headers })
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
it('reads the server clock from the Date header; a response without one keeps the last reading', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(answer({ Date: new Date(Date.now() + 30_000).toUTCString() })).mockImplementation(answer()))
  await api('/example')
  const skew = clockSkew!  // a live binding: the value of the last response
  expect(Math.abs(skew - 30_000)).toBeLessThanOrEqual(1000)  // the header has whole seconds
  await api('/example')
  expect(clockSkew).toBe(skew)
})
