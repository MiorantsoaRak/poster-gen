import { describe, expect, it } from 'vitest'
import { elapsedLabel, localTime, OVERDUE_MS, overdue, phase, retryDelay } from '../src/generation'

describe('phase of a generation, from the job and the image', () => {
  it.each([['queued', false, 'queued'], ['running', false, 'running'], ['succeeded', false, 'receiving'], ['succeeded', true, 'ready'],
    ['failed', false, 'failed'], ['interrupted', false, 'failed'], ['cancelled', true, 'failed']] as const)('%s, image loaded %s: %s', (status, loaded, expected) => {
    expect(phase({ status }, loaded)).toBe(expected)
  })
  it('never says ready before the image is loaded', () => expect(phase({ status: 'succeeded' }, false)).not.toBe('ready'))
})

describe('elapsed time', () => {
  it.each([[0, '0:00'], [999, '0:00'], [1000, '0:01'], [59_999, '0:59'], [60_000, '1:00'], [101_000, '1:41'], [3_725_000, '62:05']])('%d ms reads %s', (ms, label) => {
    expect(elapsedLabel(ms)).toBe(label)
  })
  it('is never negative', () => expect(elapsedLabel(-4000)).toBe('0:00'))
})

describe('long wait', () => {
  it('starts after 100 s of creation, not at 100 s', () => {
    expect(overdue('running', OVERDUE_MS)).toBe(false)
    expect(overdue('running', OVERDUE_MS + 1)).toBe(true)
  })
  it.each(['queued', 'receiving', 'ready', 'failed'] as const)('is never said while %s', current => expect(overdue(current, 10 * OVERDUE_MS)).toBe(false))
})

describe('server time on this device', () => {
  const now = Date.parse('2026-11-14T10:00:00Z')
  it('corrects a device clock 30 s ahead of the server', () => {
    expect(localTime('2026-11-14T09:59:00.000000+00:00', -30_000, now)).toBe(now - 30_000)
  })
  it('reads the microseconds the server writes', () => expect(localTime('2026-11-14T09:59:50.123456+00:00', 0, now)).toBe(now - 9877))
  // The device's zone must not shift it: at UTC+3 a stamp read as local time would be three hours off.
  it.each(['2026-11-14T09:59:50.123456', '2026-11-14T09:59:50.123456Z', '2026-11-14T12:59:50.123456+03:00', '2026-11-14T12:59:50.123456+0300'])('reads %s as the same UTC instant', stamp => {
    expect(localTime(stamp, 0, now)).toBe(now - 9877)
  })
  it('is never in the future (whole-second Date header)', () => expect(localTime('2026-11-14T10:00:00.900000+00:00', 0, now)).toBe(now))
  it.each([[null, 0], [undefined, 0], ['', 0], ['pas une date', 0], ['2026-11-14T09:00:00Z', null]] as const)('falls back to first sight (%s, skew %s)', (stamp, skew) => {
    expect(localTime(stamp, skew, now)).toBe(now)
  })
})

describe('next poll after a failure', () => {
  it.each([[1, 2000], [2, 4000], [3, 8000], [4, 10000], [40, 10000]])('after %d failures: %d ms', (failures, delay) => expect(retryDelay(failures)).toBe(delay))
})
