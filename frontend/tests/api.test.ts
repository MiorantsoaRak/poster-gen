import { afterEach, expect, it, vi } from 'vitest'
import { mutation } from '../src/api'

afterEach(() => vi.unstubAllGlobals())
it('reuses an uncertain mutation key after a lost response, then starts a new action after success', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('lost')).mockResolvedValue({ ok: true, json: async () => ({ id: 'saved' }) })
  vi.stubGlobal('fetch', fetch)
  await expect(mutation('/example', { value: 1 }, 2)).rejects.toThrow('Connexion')
  await mutation('/example', { value: 1 }, 2)
  await mutation('/example', { value: 1 }, 2)
  const requests = fetch.mock.calls.map(call => call[1] as RequestInit)
  expect(requests[0].headers).toEqual(requests[1].headers)
  expect(requests[2].headers).not.toEqual(requests[1].headers)
  expect(requests[0].body).toBe(requests[1].body)
})
