import { afterEach, expect, it, vi } from 'vitest'
import { api, clockSkew, mutation } from '../src/api'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
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

// D-POSTER-EDITOR-007 point 3: the top line answers a wait the owner sees, never a background one.
// A fresh module each time: the tests above leave real timers of their own in its state.
async function held() {
  vi.useFakeTimers(); vi.resetModules()
  const release: Array<() => void> = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => release.push(() => done(new Response('{}'))))))
  return { release, ...await import('../src/api') }
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
