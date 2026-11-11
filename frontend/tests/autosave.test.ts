import { afterEach, expect, it, vi } from 'vitest'
import { DraftSaver } from '../src/autosave'
import { ApiError } from '../src/api'
import { document } from './fixture'

afterEach(() => vi.useRealTimers())

it('serialises writes and sends edits made while saving with the next revision', async () => {
  let release!: (value: { revision: number }) => void
  const send = vi.fn().mockImplementationOnce(() => new Promise(resolve => { release = resolve }))
    .mockResolvedValueOnce({ revision: 3 })
  const saver = new DraftSaver(1, send), doc = document()
  saver.queue(doc)
  const flushed = saver.flush()
  doc.offer.price_ar = 100000; saver.queue(doc)
  expect(send).toHaveBeenCalledTimes(1)
  release({ revision: 2 }); await flushed
  expect(send).toHaveBeenCalledTimes(2)
  expect(send.mock.calls[0][0].document.offer.price_ar).toBe(90000)
  expect(send.mock.calls[1][0].revision).toBe(2)
  expect(saver.revision).toBe(3)
  saver.dispose()
})

it('replays an uncertain save before sending newer local edits', async () => {
  const send = vi.fn().mockRejectedValueOnce(new ApiError('network', 'offline', 0))
    .mockResolvedValueOnce({ revision: 2 }).mockResolvedValueOnce({ revision: 3 })
  const saver = new DraftSaver(1, send), doc = document()
  saver.queue(doc); await expect(saver.flush()).rejects.toThrow('offline')
  doc.offer.title = 'Changed'; saver.queue(doc)
  await saver.flush()
  expect(send.mock.calls[1][0]).toEqual(send.mock.calls[0][0])
  expect(send.mock.calls[2][0].document.offer.title).toBe('Changed')
  expect(send.mock.calls[2][0].key).not.toBe(send.mock.calls[0][0].key)
  expect(saver.state).toBe('saved')
})

it('retains conflict changes without retrying an overwrite', async () => {
  const send = vi.fn().mockRejectedValue(new ApiError('revision_conflict', 'newer revision', 409, 5))
  const saver = new DraftSaver(1, send)
  saver.queue(document()); await expect(saver.flush()).rejects.toThrow()
  await expect(saver.flush()).rejects.toThrow()
  expect(send).toHaveBeenCalledTimes(1)
  expect(saver.state).toBe('conflict'); expect(saver.unsaved).toBe(true)
})

it('waits for 750 ms idle', async () => {
  vi.useFakeTimers()
  const send = vi.fn().mockResolvedValue({ revision: 2 }), saver = new DraftSaver(1, send)
  saver.queue(document()); await vi.advanceTimersByTimeAsync(749)
  expect(send).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1)
  expect(send).toHaveBeenCalledTimes(1); expect(saver.state).toBe('saved')
})
