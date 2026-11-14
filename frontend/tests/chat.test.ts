import { expect, it } from 'vitest'
import { cardButton, complete, fate, final, freePrice, limitLine, modifications, nextStep, lines, movedTo, newPending, nextRole, PENDING_KEY, pendingFor, readPending, readThread, settled, spend, supersede, swapRole, threadKey, trim, UNSENT_KEY, versionsLeft, wireDraft, type Item, type Role } from '../src/chat'
import type { Visual } from '../src/document'

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
  // The refinement route: the document at the request's revision against a version or a plan that never changes.
  for (const code of ['headline_stale', 'base_not_selected', 'scene_format_mismatch', 'logo_disc_uncovered', 'logo_placement_stale', 'invalid_plan',
    'invalid_reference', 'unsupported_visual', 'format_missing']) expect(final(code), code).toBe(true)
  for (const code of ['asset_missing', 'asset_corrupt', 'unknown_asset', 'provider_mode_mismatch']) expect(final(code), code).toBe(false)
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
it('gives a change card the paid button of a recap, and none once the poster has its twelve versions', () => {
  const change = item({ card: { kind: 'change', change: 'scene', instruction_fr: 'fond plus sombre' } })
  expect(cardButton(change)).toBe('create')
  expect(cardButton(change, undefined, undefined, 1)).toBe('create')
  expect(cardButton(change, undefined, undefined, 0)).toBeNull()
  expect(cardButton(item({ card: { kind: 'recap' } }), undefined, undefined, 0)).toBeNull()
  expect(cardButton({ ...change, done: true })).toBeNull()
  const kept = { path: '/api/creations/c/refinements', body: {}, revision: 2 }
  expect(cardButton({ ...change, spent: true, request: kept }, undefined, undefined, 0)).toBe('resume')  // its request may have left: the limit does not hide it
  expect(cardButton({ ...change, spent: true, request: kept, card: { ...change.card!, error: 'x' } })).toBe('retry')
  expect(cardButton({ ...change, spent: true, request: kept, job: 'j' })).toBeNull()
})
it('changes a price for free only when the selected version does not draw it', () => {
  const card = { kind: 'change', change: 'price' as const, price_ar: 650000 }
  expect(freePrice(card, undefined)).toBe(true)  // the price is a layer of the poster
  expect(freePrice(card, null)).toBe(true)
  expect(freePrice(card, 700000)).toBe(false)  // drawn in the image: a new scene, paid
  expect(freePrice({ ...card, whole: true }, undefined)).toBe(false)  // the drawn words changed: always a whole new scene
  expect(freePrice({ ...card, previous: 700000 }, undefined)).toBe(false)  // the retry of a paid redraw
  expect(freePrice({ kind: 'change', change: 'scene' }, undefined)).toBe(false)
  expect(freePrice({ kind: 'recap' }, undefined)).toBe(false)
  expect(freePrice(undefined, undefined)).toBe(false)
})
it('counts the versions left by the server rule, and says so only near the limit', () => {
  const jobs = (count: number) => [...Array.from({ length: count }, (_, index) => ({ kind: index % 2 ? 'refine' : 'scene', status: index ? 'succeeded' : 'running' })),
    { kind: 'scene', status: 'failed' }, { kind: 'refine', status: 'interrupted' }, { kind: 'scene', status: 'cancelled' }, { kind: 'render', status: 'succeeded' }, { kind: 'plan', status: 'succeeded' }]
  expect(versionsLeft(jobs(0))).toBe(12)
  expect(versionsLeft(jobs(10))).toBe(2)
  expect(versionsLeft(jobs(12))).toBe(0)
  expect(limitLine(null)).toBe('')  // not known: the server's refusal still holds
  expect(limitLine(3)).toBe('')
  expect(limitLine(2)).toBe('Il reste 2 versions pour cette affiche.')
  expect(limitLine(1)).toBe('Il reste 1 version pour cette affiche.')
  expect(limitLine(0)).toMatch(/^Douze scènes ont déjà été demandées/)
  expect(limitLine(-1)).toBe(limitLine(0))
})
it('lists the modifications from the versions: number, state and what changed', () => {
  const version = (id: string, extra: Partial<Visual> = {}): Visual => ({ id, status: 'approved', image_url: '', original_urls: [], size: '1080x1350', base_visual_id: null, headline: { title: 'Sony', price_ar: 700000 }, ...extra })
  const list = modifications([  // newest first, as the server lists them
    version('e', { status: 'pending_review' }),
    version('d', { status: 'rejected', headline: { title: 'Sony', price_ar: 650000 } }),
    version('c', { base_visual_id: 'b' }),
    version('b', { base_visual_id: 'a', instruction_fr: 'fond plus sombre' }),
    version('a'),
  ])
  expect(list.map(line => [line.id, line.number, line.state])).toEqual([['e', 5, 'À vérifier'], ['d', 4, 'Refusée'], ['c', 3, 'Confirmée'], ['b', 2, 'Confirmée'], ['a', 1, 'Confirmée']])
  expect(list.map(line => line.label.replace(/\s/g, ' '))).toEqual(['Prix : 700 000 Ar', 'Prix : 650 000 Ar', 'Scène ajustée', 'fond plus sombre', 'Première affiche'])
  // The same price drawn again, or a price that is a layer: a new version, nothing invented.
  expect(modifications([version('b'), version('a')])[0].label).toBe('Nouvelle version')
  expect(modifications([version('b', { headline: null }), version('a')])[0].label).toBe('Nouvelle version')
  expect(modifications([])).toEqual([])
})
it('knows the poster a pending read was sent for', () => {
  expect(pendingFor(newPending({ text: 'fond plus sombre', creation_id: 'c' } as { text: string }))).toBe('c')
  expect(pendingFor(newPending({ text: 'Sony' }))).toBeNull()
  expect(pendingFor({ key: 'k', body: '{nope', text: 'x' })).toBeNull()
})
