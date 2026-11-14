import { expect, it } from 'vitest'
import { cardButton, complete, fate, final, nextStep, lines, movedTo, newPending, nextRole, PENDING_KEY, readPending, readThread, settled, spend, supersede, swapRole, threadKey, trim, UNSENT_KEY, wireDraft, type Item, type Role } from '../src/chat'

const pictures = (...roles: Role[]) => roles.map((role, index) => ({ id: `p${index}`, role, asset: `a${index}` }))
const item = (extra: Partial<Item> = {}): Item => ({ id: 'i', role: 'app', text: 'x', at: 1, ...extra })

it('gives the first image to the product, the second to the inspiration, then product photos up to three', () => {
  expect(nextRole([])).toBe('product')
  expect(nextRole(pictures('product'))).toBe('inspiration')
  expect(nextRole(pictures('product', 'inspiration'))).toBe('product')
  expect(nextRole(pictures('product', 'inspiration', 'product'))).toBe('product')
  expect(nextRole(pictures('product', 'inspiration', 'product', 'product'))).toBeNull()
  expect(nextRole(pictures('inspiration'))).toBe('product')  // the first one was swapped: a product is still missing
})
it('swaps a role and never keeps two inspirations', () => {
  expect(swapRole(pictures('product', 'inspiration'), 'p0').map(picture => picture.role)).toEqual(['inspiration', 'product'])
  expect(swapRole(pictures('product', 'inspiration'), 'p1').map(picture => picture.role)).toEqual(['product', 'product'])
  expect(swapRole(pictures('product'), 'p0').map(picture => picture.role)).toEqual(['inspiration'])
})
it('refuses a swap that a sent image or the three-photo limit forbids', () => {
  const one = pictures('product')
  expect(swapRole(one, 'p0', [{ role: 'inspiration' }])).toBe(one)  // the sent inspiration cannot be sent again as a product
  const full = pictures('inspiration')
  expect(swapRole(full, 'p0', [{ role: 'product' }, { role: 'product' }, { role: 'product' }])).toBe(full)
  expect(swapRole(one, 'unknown')).toBe(one)
})
it('names the thread of a poster, of a new one, and the unsent text', () => {
  expect(threadKey('abc')).toBe('affiche.chat.abc')
  expect(threadKey(null)).toBe('affiche.chat.new')
  expect(UNSENT_KEY).toBe('affiche.chat.unsent')
  expect(PENDING_KEY).toBe('affiche.chat.pending')
})
it('keeps the last 100 items of a thread', () => {
  const many = Array.from({ length: 130 }, (_, index) => item({ id: String(index) }))
  expect(trim(many)).toHaveLength(100)
  expect(trim(many)[0].id).toBe('30')
  expect(readThread(JSON.stringify({ items: many })).items).toHaveLength(100)
})
it('never trusts the storage: a damaged thread is empty and wrong fields are left out', () => {
  expect(readThread('{nope')).toEqual({ items: [], draft: { name: null, price_ar: null, style: null, pictures: [] } })
  const read = readThread(JSON.stringify({ items: [item(), { id: 1, role: 'app', text: 'x' }, { id: 'b', role: 'robot', text: 'x' }, item({ id: 'c', card: {} as any }), null],
    draft: { name: 'Sony', price_ar: '700000', style: 'rose', pictures: [{ asset: 'a', role: 'product' }, { asset: 'b', role: 'logo' }, 7] } }))
  expect(read.items.map(entry => entry.id)).toEqual(['i'])
  expect(read.draft).toEqual({ name: 'Sony', price_ar: null, style: null, pictures: [{ asset: 'a', role: 'product' }] })
})
it('keeps a pending read as one unchangeable record of its key and exact body', () => {
  const pending = newPending({ text: 'Sony, 700 000 Ar', draft: { name: null } } as { text: string })
  expect(pending.key).toMatch(/^[0-9a-f-]{36}$/)
  expect(JSON.parse(pending.body)).toEqual({ text: 'Sony, 700 000 Ar', draft: { name: null } })
  expect(() => { (pending as { key: string }).key = 'other' }).toThrow()
  expect(readPending(JSON.stringify(pending))).toEqual(pending)  // the same key and body after a reload
  expect(newPending({ text: 'Sony, 700 000 Ar' }).key).not.toBe(pending.key)  // the same text typed again is another request
  for (const raw of [null, '{nope', '{"key":"k","text":"Sony"}', '{"key":1,"body":"{}","text":"Sony"}']) expect(readPending(raw)).toBeNull()
})
it('keeps the pending read while its outcome is unknown, and drops it on a definite answer', () => {
  for (const code of ['network', 'timeout', 'invalid_response', 'server_error', 'read_running']) expect(settled(code)).toBe(false)
  for (const code of ['read_failed', 'budget_exhausted', 'read_limit', 'chat_unavailable', 'validation_error', 'idempotency_reused']) expect(settled(code)).toBe(true)
})
it('leaves a pointer where the new thread went, and reads nothing else from it', () => {
  const id = '0b9f3c1e-2a4d-4e6f-8a1b-3c5d7e9f1a2b'
  expect(readThread(movedTo(id))).toEqual({ items: [], draft: { name: null, price_ar: null, style: null, pictures: [] }, moved: id })
  expect(readThread(JSON.stringify({ moved: '../x', items: [item()] })).moved).toBeUndefined()
  expect(readThread(JSON.stringify({ items: [item()] })).moved).toBeUndefined()
})
const request = { path: '/api/creations/c/scenes', body: { plan_id: 'p' }, revision: 3 }
it('decides what a spent card waits for: its job, its kept request sent again, or nothing paid left', () => {
  const card = item({ card: { kind: 'recap' }, spent: true, creation: 'c' })
  expect(nextStep({ ...card, request, job: 'j' })).toBe('follow')
  expect(nextStep({ ...card, request })).toBe('replay')  // a 404 or a silence never stands for « not sent » once it may have left
  expect(nextStep(card)).toBe('new')  // spent before its request was kept: it never left
})
it('retires a card only on a refusal that an earlier delivery of the same request would meet too', () => {
  for (const code of ['plan_stale', 'revision_conflict', 'attempt_limit', 'acknowledgement_required', 'title_too_long', 'title_commercial_text',
    'title_unsupported', 'validation_error', 'format_locked', 'not_found', 'idempotency_reused']) expect(final(code), code).toBe(true)
  // A refusal stores nothing under the key: these may let a delivery still on its way pass later, so the card keeps it.
  for (const code of ['image_job_running', 'budget_exhausted', 'rate_limited', 'provider_unavailable', 'unauthenticated', 'service_down',
    'server_error', 'network', 'timeout', 'invalid_response', 'something_new', '', 'creation_abandoned', 'format_unavailable']) expect(final(code), code).toBe(false)
})
it('names the outcome of the job a card recorded', () => {
  for (const status of ['queued', 'running']) expect(fate({ status })).toBe('running')
  expect(fate({ status: 'succeeded' })).toBe('made')
  for (const status of ['failed', 'interrupted', 'cancelled']) expect(fate({ status })).toBe('failed')
})
it('sends the reader the last six lines and the draft with its uploaded pictures counted', () => {
  const thread = Array.from({ length: 8 }, (_, index) => item({ id: String(index), role: index % 2 ? 'app' : 'owner', text: index === 7 ? ' ' : `m${index}` }))
  expect(lines(thread)).toEqual([1, 2, 3, 4, 5, 6].map(index => ({ role: index % 2 ? 'app' : 'owner', text: `m${index}` })))
  const draft = { name: 'Sony', price_ar: 700000, style: 'sombre' as const, pictures: [{ asset: 'a', role: 'product' as Role }, { asset: 'b', role: 'inspiration' as Role }] }
  expect(wireDraft(draft)).toEqual({ name: 'Sony', price_ar: 700000, style: 'sombre', product_photos: 1, inspiration: true })
  expect(complete(draft)).toBe(true)
  expect(complete({ ...draft, pictures: draft.pictures.slice(1) })).toBe(false)
  expect(complete({ ...draft, price_ar: null })).toBe(false)
})
it('spends a card once: the second tap is refused', () => {
  const thread = [item({ id: 'a', card: { kind: 'recap' } })]
  expect(spend(thread, 'a')).toBe(true)
  expect(spend(thread, 'a')).toBe(false)
  expect(spend(thread, 'missing')).toBe(false)
  expect(thread[0].spent).toBe(true)
})
it('shows one button per card, and none on a spent or replaced one', () => {
  const recap = item({ card: { kind: 'recap' } })
  expect(cardButton(recap)).toBe('create')
  expect(cardButton({ ...recap, spent: true })).toBeNull()  // spent: its outcome, never its button
  // A rule refused the words: no retry, the editor corrects them.
  expect(cardButton({ ...recap, spent: true, done: true, card: { kind: 'recap', error: 'refusé', fix: true } })).toBe('fix')
  expect(cardButton({ ...recap, done: true })).toBeNull()
  // Its request may have left and its outcome is unknown: « Réessayer » sends that same request again.
  expect(cardButton({ ...recap, spent: true, request, card: { kind: 'recap', error: 'Connexion interrompue' } })).toBe('retry')
  expect(cardButton({ ...recap, spent: true, request })).toBe('resume')  // a later view: the owner sends it again, never the chat
  expect(cardButton({ ...recap, spent: true, request, job: 'j', card: { kind: 'recap', error: 'x' } })).toBeNull()
  expect(cardButton({ ...recap, spent: true, card: { kind: 'recap', error: 'x' } })).toBeNull()
  expect(cardButton(item({ card: { kind: 'ask_photo' } }))).toBe('photo')
  expect(cardButton(item({ card: { kind: 'ask_price' } }))).toBeNull()
  expect(cardButton(item({ card: { kind: 'failed', retry: 'Sony' } }))).toBe('resend')
  expect(cardButton(item({ card: { kind: 'failed', code: 'read_limit' } }))).toBeNull()
  expect(cardButton(item())).toBeNull()
})
it('follows the version of a result card: check, then download of the selected version only, nothing once refused', () => {
  const result = item({ done: true, card: { kind: 'result', visual_id: 'v' } })
  expect(cardButton(result, 'pending_review')).toBe('review')
  expect(cardButton(result, 'approved', 'v')).toBe('download')
  expect(cardButton(result, 'approved', 'other')).toBeNull()  // the export would render the other version
  expect(cardButton(result, 'approved')).toBeNull()
  expect(cardButton(result, 'rejected')).toBeNull()
  expect(cardButton(result)).toBeNull()
})
it('replaces open cards with a new one, leaving spent cards and results as they are', () => {
  const thread = [item({ id: 'a', card: { kind: 'recap' } }), item({ id: 'b', card: { kind: 'recap' }, spent: true }), item({ id: 'c', card: { kind: 'result' } }), item({ id: 'd' })]
  supersede(thread)
  expect(thread.map(entry => !!entry.done)).toEqual([true, false, false, false])
})
