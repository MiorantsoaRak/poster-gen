import { afterEach, expect, it, vi } from 'vitest'
import { bind, open } from '../src/api'
import { sectionRead } from '../src/dashboard'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

it('keeps the latest section result, ignores a late response after clearing it, and retains the last good value on timeout', async () => {
  bind(1); open()
  vi.useFakeTimers()
  const replies: Array<(value: Response) => void> = []
  vi.stubGlobal('fetch', (_: string, init: RequestInit) => new Promise<Response>((resolve, reject) => {
    replies.push(resolve)
    init.signal!.addEventListener('abort', () => reject(new Error('aborted')))
  }))
  const list = sectionRead<number>('/api/shop-dashboard')
  const slow = list.read(), fast = list.read()
  replies[1](Response.json(2)); await fast
  replies[0](Response.json(1)); await slow
  expect(list.data.value).toBe(2)
  const timed = list.read()
  await vi.advanceTimersByTimeAsync(20_000); await timed
  expect(list.error.value).toContain('trop de temps')
  expect(list.data.value).toBe(2)
  const pending = list.read()
  list.clear()
  replies[3](Response.json(3)); await pending
  expect(list.data.value).toBeNull()
  expect(list.checked.value).toBe('')
  expect(list.loading.value).toBe(false)
})
