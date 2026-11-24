import { afterEach, expect, it, vi } from 'vitest'
import { bind, open } from '../src/api'
import { creditHistory, historyEntry, sectionRead, stateBadges, stateNames, type HistoryEntry } from '../src/dashboard'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

it('names each list state with one word, « Confirmée » only for a poster whose file is this revision', () => {
  expect(stateNames).toEqual({ draft: 'Brouillon', to_review: 'À vérifier', approved: 'À confirmer', confirmed: 'Confirmée' })
  expect(stateBadges).toEqual({ draft: 'badge', to_review: 'badge warn', approved: 'badge', confirmed: 'badge ok' })
})

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

it('keeps a credit history page on timeout, deduplicates the retry and drops an overtaken page', async () => {
  bind(1); open(); vi.useFakeTimers()
  const replies: Array<(value: Response) => void> = []
  const fetch = vi.fn((_path: string, init: RequestInit) => new Promise<Response>((resolve, reject) => {
    replies.push(resolve); init.signal!.addEventListener('abort', () => reject(new Error('aborted')))
  }))
  vi.stubGlobal('fetch', fetch)
  const history = creditHistory(), job = { type: 'job', id: 'uuid' }, grant = { type: 'line', id: 1 }
  const answer = (i: number, items: unknown[], next_cursor: string | null) => replies[i](Response.json({ items, next_cursor }))
  vi.setSystemTime(new Date(2026, 0, 1, 10, 0))
  const first = history.read(); answer(0, [job], 'instant|line|1'); await first
  expect(history.checked.value).toBe('10:00')
  vi.setSystemTime(new Date(2026, 0, 1, 11, 0))
  const slow = history.read(true)
  expect(fetch.mock.calls[1][0]).toContain('before=instant%7Cline%7C1')
  await vi.advanceTimersByTimeAsync(20_000); await slow
  expect(history.error.value).toContain('trop de temps'); expect(history.page.value?.items).toEqual([job])
  const retry = history.read(true); answer(2, [job, grant], 'cursor'); await retry
  expect(history.page.value?.items).toEqual([job, grant])
  expect(history.checked.value).toBe('10:00')
  const old = history.read(true), fresh = history.read(); answer(4, [grant], null); await fresh
  expect(history.checked.value).toBe('11:00')
  answer(3, [job], null); await old
  expect(history.page.value?.items).toEqual([grant])
  const late = history.read(); history.clear(); answer(5, [job], null); await late
  expect(history.page.value).toBeNull()
})

it('distinguishes bought, offered, reserved, spent, released and corrected credits', () => {
  const base = { at: '', creation_id: null, removed: null, title: null }
  const entries: HistoryEntry[] = [
    { ...base, type: 'line', id: 1, origin: 'bought', kind: 'grant', credits: 5 },
    { ...base, type: 'line', id: 2, origin: 'offered', kind: 'grant', credits: 10 },
    { ...base, type: 'line', id: 3, origin: null, kind: 'correction', credits: -3 },
    { ...base, type: 'line', id: 4, origin: null, kind: 'correction', credits: 0 },
    { ...base, type: 'line', id: 5, origin: null, kind: 'correction', credits: 1, creation_id: 'c' },
    ...(['pending', 'spent', 'given_back'] as const).map(credit => ({ ...base, type: 'job' as const, id: 'j', kind: 'scene', credit })),
  ]
  expect(entries.map(row => Object.values(historyEntry(row)))).toEqual([
    ['Achat de crédits', '+5'], ['Crédits offerts', '+10'], ['Correction', '-3'], ['Correction', '0'],
    ['Remboursement', '+1'], ['Crédit réservé', '1 en attente'], ['Crédit dépensé', '−1'], ['Réservation libérée', '1 rendu'],
  ])
})
