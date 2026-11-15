import { afterEach, expect, it, vi } from 'vitest'
import { api, BUNDLE, clockSkew, mutation, read } from '../src/api'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
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
  expect(BUNDLE).toBe(2)  // backend api.py BUNDLE: raised together
  expect(sent[2]).toMatchObject({ 'Idempotency-Key': 'k', 'If-Match': '"3"', 'Content-Type': 'application/json' })
  expect(sent[4]).toEqual({ 'X-Affiche-Bundle': '2' })  // an upload keeps the browser's own Content-Type
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

// D-TEXT-FIRST-002 and 003: a read is paid and bounded at 30 s on the client; its record goes as it is.
it('gives up a read after 30 s with a timeout error, and leaves other calls without a limit', async () => {
  vi.useFakeTimers(); vi.resetModules()
  const signals: (AbortSignal | undefined)[] = []
  vi.stubGlobal('fetch', vi.fn((_path: string, init: RequestInit) => new Promise<Response>((_done, fail) => {
    signals.push(init.signal ?? undefined)
    init.signal?.addEventListener('abort', () => fail(new DOMException('aborted', 'AbortError')))
  })))
  const { api, read, ApiError } = await import('../src/api')
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
  const { read } = await import('../src/api')
  await expect(read({ key: 'k', body: '{}' })).resolves.toEqual({ id: 'saved' })
  await vi.advanceTimersByTimeAsync(1000)  // the progress line's own short timers end
  expect(vi.getTimerCount()).toBe(0)
})
it('sends a read record with its own key and exact body, the same at each attempt', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('lost')).mockImplementation(answer())
  vi.stubGlobal('fetch', fetch)
  const { read } = await import('../src/api')
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
