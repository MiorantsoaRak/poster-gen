import { expect, it } from 'vitest'
import { bind, open } from '../src/api'
import { cardButton, CHANGE_BUTTONS, changes, complete, effectOf, identityLine, isThread, keepRequest, paid, fate, final, limitLine, modifications, nextStep, normal, staleLine, staleOf, lines, movedTo, newPending, nextRole, pendingFor, pendingKey, readPending, readThread, settled, spend, storeThread, supersede, swapRole, threadKey, trim, unresolved, unsentKey, UNSTORED, versionsLeft, waitingIn, wireDraft, type Item, type Role } from '../src/chat'
import type { Visual } from '../src/document'
import { memory } from './fixture'

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
it('names the thread of a poster, of a new one, the unsent text and the pending read, under the open shop only', () => {
  bind(2)
  expect(() => threadKey('abc')).toThrow()  // the gate has not opened on shop 2 yet: no key is guessed
  open()
  expect(threadKey('abc')).toBe('affiche.shop2.chat.abc')
  expect(threadKey(null)).toBe('affiche.shop2.chat.new')
  expect(unsentKey()).toBe('affiche.shop2.chat.unsent')
  expect(pendingKey()).toBe('affiche.shop2.chat.pending')
  expect([threadKey('abc'), unsentKey(), pendingKey(), 'affiche.shop1.chat.abc', 'affiche.chat.abc'].map(isThread)).toEqual([true, false, false, false, false])
})
it('keeps the last 100 items of a thread', () => {
  const many = Array.from({ length: 130 }, (_, index) => item({ id: String(index) }))
  expect(trim(many)).toHaveLength(100)
  expect(trim(many)[0].id).toBe('30')
  expect(readThread(JSON.stringify({ items: many })).items).toHaveLength(100)
})
it('never trusts the storage: a damaged thread is empty and wrong fields are left out', () => {
  expect(readThread('{nope')).toEqual({ items: [], draft: { name: null, price_ar: null, style: null, identity: null, pictures: [] } })
  const read = readThread(JSON.stringify({ items: [item(), { id: 1, role: 'app', text: 'x' }, { id: 'b', role: 'robot', text: 'x' }, item({ id: 'c', card: {} as any }), null],
    draft: { name: 'Sony', price_ar: '700000', style: 'rose', pictures: [{ asset: 'a', role: 'product' }, { asset: 'b', role: 'logo' }, 7] } }))
  expect(read.items.map(entry => entry.id)).toEqual(['i'])
  expect(read.draft).toEqual({ name: 'Sony', price_ar: null, style: null, identity: null, pictures: [{ asset: 'a', role: 'product' }] })
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
  for (const code of ['read_failed', 'budget_exhausted', 'read_limit', 'chat_unavailable', 'validation_error', 'idempotency_reused',
    'shop_daily_limit', 'reads_busy']) expect(settled(code)).toBe(true)  // refused at admission: nothing kept under the key
})
it('leaves a pointer where the new thread went, and reads nothing else from it', () => {
  const id = '0b9f3c1e-2a4d-4e6f-8a1b-3c5d7e9f1a2b'
  expect(readThread(movedTo(id))).toEqual({ items: [], draft: { name: null, price_ar: null, style: null, identity: null, pictures: [] }, moved: id })
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
  // The request's own words against the document at its revision: asking again changes nothing (audit 2026-11-15).
  for (const code of ['invalid_headline', 'contact_unsupported']) expect(final(code), code).toBe(true)
  // A refusal stores nothing under the key: these may let a delivery still on its way pass later, so the card keeps it.
  for (const code of ['image_job_running', 'budget_exhausted', 'shop_daily_limit', 'no_credit', 'shop_suspended', 'rate_limited', 'provider_unavailable', 'unauthenticated', 'service_down',
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
  const draft = { name: 'Sony', price_ar: 700000, style: 'sombre' as const, identity: null, pictures: [{ asset: 'a', role: 'product' as Role }, { asset: 'b', role: 'inspiration' as Role }] }
  expect(wireDraft(draft)).toEqual({ name: 'Sony', price_ar: 700000, style: 'sombre', product_photos: 1, inspiration: true })
  // The shop's identity is sent only when the owner said it, on or off: without it the body is the one from before the
  // field (toEqual above would pass with `identity: undefined`; the key itself is checked here).
  expect('identity' in wireDraft(draft)).toBe(false)
  expect([wireDraft({ ...draft, identity: true }).identity, wireDraft({ ...draft, identity: false }).identity]).toEqual([true, false])
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
it('pays for a style change as for a change, and shows a kind it does not know as text (D-TEXT-FIRST-006)', () => {
  const restyle = item({ card: { kind: 'restyle', style: 'sombre', visual_id: 'v', words: { title: 'Sony' } } })
  expect(paid(restyle.card) && changes(restyle.card)).toBe(true)
  expect(cardButton(restyle)).toBe('create')
  expect(CHANGE_BUTTONS[effectOf(restyle.card!)]).toBe('Refaire l’affiche')
  expect(effectOf(restyle.card!, { headline: null })).toBe('scene')  // never free, whatever the selected version
  expect(cardButton(restyle, undefined, undefined, 0)).toBeNull()  // the version limit holds for it
  expect(cardButton({ ...restyle, spent: true, request })).toBe('resume')
  expect(cardButton({ ...restyle, spent: true, request, card: { ...restyle.card!, error: 'x' } })).toBe('retry')
  expect(cardButton({ ...restyle, done: true })).toBeNull()
  expect(normal(restyle.card!)).toEqual(restyle.card)
  // A card of a later bundle, with everything a paid card carries: no button, spent or not. This is what keeps a tab
  // on an older bundle from paying for a card it would carry out wrongly.
  const unknown = item({ card: { kind: 'recolour', style: 'sombre', visual_id: 'v', effect: 'scene', words: { title: 'Sony' } } })
  expect(paid(unknown.card) || changes(unknown.card)).toBe(false)
  for (const state of [{}, { spent: true }, { spent: true, request }, { done: true }]) expect(cardButton({ ...unknown, ...state })).toBeNull()
})
it('says on the recap what the shop’s profile gives the poster', () => {
  const shop = (logo: boolean, contact: boolean, ticked = false) => ({ logo, contact, ticked })
  expect(identityLine(shop(true, true), true)).toBe('Avec le logo et le contact de la boutique')
  expect(identityLine(shop(true, false), true)).toBe('Avec le logo de la boutique')
  expect(identityLine(shop(false, true), true)).toBe('Avec le contact de la boutique')
  expect(identityLine(shop(false, false, true), true)).toBe('La boutique n’a pas encore de logo ni de contact : ajoutez-les dans Pas à pas.')
  // Asked off: a line only when the form's ticks would have put one on.
  expect(identityLine(shop(true, true, true), false)).toBe('Sans le logo ni le contact de la boutique')
  expect(identityLine(shop(true, true), false)).toBe('')
  // The draft keeps the wish across a reload, on or off; anything else in the storage is "not said".
  const stored = (identity: unknown) => readThread(JSON.stringify({ items: [], draft: { name: 'Sony', identity } })).draft.identity
  expect([stored(true), stored(false), stored('true'), stored(undefined)]).toEqual([true, false, null, null])
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
  const change = item({ card: { kind: 'change', effect: 'refine', instruction_fr: 'fond plus sombre' } })
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
it('converts a card from before D-005 at both entries, and leaves the server\'s cards as they are', () => {
  const said = 'prix 650 000 Ar'
  // An old price card sets its price alone and has no effect of its own; the price the image showed is no longer kept.
  expect(normal({ kind: 'change', change: 'price', price_ar: 650000, previous: 700000, said } as any)).toEqual({ kind: 'change', words: { price_ar: 650000 }, said })
  expect(normal({ kind: 'change', change: 'price', price_ar: 650000, whole: true } as any)).toEqual({ kind: 'change', words: { price_ar: 650000 }, whole: true })
  expect(normal({ kind: 'change', change: 'scene', instruction_fr: 'fond plus sombre', said } as any)).toEqual({ kind: 'change', effect: 'refine', instruction_fr: 'fond plus sombre', said })
  const scene = { kind: 'change', effect: 'scene' as const, visual_id: 'v', words: { title: 'WH-CH720N', brand: 'Sony', subtitle: null, price_ar: 450000 } }
  expect(normal(scene)).toEqual(scene)
  expect(normal(normal({ kind: 'change', change: 'price', price_ar: 1 } as any))).toEqual({ kind: 'change', words: { price_ar: 1 } })  // twice is once
  expect(normal({ kind: 'recap', name: 'Sony', price_ar: 700000 })).toEqual({ kind: 'recap', name: 'Sony', price_ar: 700000 })
  // The stored thread goes through it; a spent card keeps its request untouched.
  const kept = { path: '/api/creations/c/scenes', body: { plan_id: 'p', headline: { price: true } }, revision: 2 }
  const [read] = readThread(JSON.stringify({ items: [item({ spent: true, request: kept, card: { kind: 'change', change: 'price', price_ar: 650000, previous: 700000 } as any })] })).items
  expect(read.card).toEqual({ kind: 'change', words: { price_ar: 650000 } })
  expect(read.request).toEqual(kept)
})
it('takes the effect of a change card from the server, and for a card from before from the selected version', () => {
  const old = normal({ kind: 'change', change: 'price', price_ar: 650000 } as any)
  expect(effectOf(old, { headline: { title: 'Sony', price_ar: 700000 } })).toBe('scene')  // drawn in the image: a new scene, paid
  expect(effectOf(old, { headline: { title: 'Sony' } })).toBe('free')  // the price is a layer of the poster
  expect(effectOf(old, { headline: null })).toBe('free')
  expect(effectOf(old)).toBe('free')
  expect(effectOf({ ...old, whole: true }, { headline: null })).toBe('scene')  // the drawn words changed: always a whole new scene
  expect(effectOf(normal({ kind: 'change', change: 'scene', instruction_fr: 'fond' } as any))).toBe('refine')
  // The server's word wins over what the selected version draws.
  expect(effectOf({ kind: 'change', effect: 'free', visual_id: 'v', words: { price_ar: 1 } }, { headline: { title: 'Sony', price_ar: 700000 } })).toBe('free')
  expect(effectOf({ kind: 'change', effect: 'scene', visual_id: 'v', words: {} }, { headline: null })).toBe('scene')
})
it('names the button of a change card by its effect', () => {
  expect(CHANGE_BUTTONS).toEqual({ refine: 'Créer', scene: 'Refaire l’affiche', free: 'Changer' })
  const free = item({ card: { kind: 'change', effect: 'free', visual_id: 'v', words: { title: 'Sony' } } })
  expect(cardButton(free, undefined, undefined, null)).toBe('create')  // the caller hides the version limit from a free change
  expect(cardButton(item({ card: { kind: 'change', effect: 'scene', visual_id: 'v', words: {} } }), undefined, undefined, 0)).toBeNull()
})
it('says what the image still shows, only from the stored words of the selected version', () => {
  const offer = { title: 'WH-CH720N', price_ar: 450000 }
  expect(staleOf({ title: 'Sony WH-CH720N', price_ar: 700000 }, offer)).toEqual({ title: 'Sony WH-CH720N', price_ar: 700000 })
  expect(staleOf({ title: 'WH-CH720N', price_ar: 700000 }, offer)).toEqual({ price_ar: 700000 })
  expect(staleOf({ title: 'Sony WH-CH720N' }, offer)).toEqual({ title: 'Sony WH-CH720N' })  // the price is a layer: nothing stored
  expect(staleOf({ title: 'WH-CH720N', price_ar: 450000 }, offer)).toEqual({})
  for (const none of [null, undefined]) expect(staleOf(none, offer)).toEqual({})  // a version without stored words
  expect(staleOf({ title: 'Sony' }, undefined)).toEqual({})
  expect(staleLine({ title: 'Sony WH-CH720N', price_ar: 700000 }).replace(/\s/g, ' ')).toBe('L’affiche montre encore : « Sony WH-CH720N », 700 000 Ar.')
  expect(staleLine({ price_ar: 700000 }).replace(/\s/g, ' ')).toBe('L’affiche montre encore : 700 000 Ar.')
  expect(staleLine({})).toBe('')
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
  // A version a chat card made from an older one says what changed against that one, not against the line below it.
  const branded = { title: 'WH-CH720N', brand: 'Sony', price_ar: 700000 }
  const made = modifications([version('c', { headline: branded, replaces_visual_id: 'a' }), version('b', { headline: branded }), version('a')])
  expect(made[0].label).toBe('Titre : WH-CH720N · Marque : Sony')
  expect(modifications([version('c', { headline: branded, replaces_visual_id: 'gone' }), version('b', { headline: branded }), version('a')])[0].label).toBe('Nouvelle version')
  expect(modifications([])).toEqual([])
  // A new scene is named by its drawn words that differ from the version before, in the field table's order.
  const words = modifications([
    version('e', { headline: { title: 'WH-CH720N', brand: 'Sony', price_ar: 700000 } }),
    version('d', { headline: { title: 'WH-CH720N', brand: 'Sony', subtitle: null, price_ar: 700000 } }),
    version('c', { headline: { title: 'WH-CH720N', brand: 'Sony', subtitle: 'Casque sans fil', price_ar: 450000 } }),
    version('b', { headline: { title: 'WH-CH720N', brand: 'Sony', price_ar: 700000 } }),
    version('a', { headline: { title: 'Sony WH-CH720N', brand: 'Sony', brand_in_title: true, price_ar: 700000 } }),
  ]).map(line => line.label.replace(/\s/g, ' '))
  expect(words).toEqual(['Nouvelle version', 'Sous-titre : retiré · Prix : 700 000 Ar', 'Sous-titre : Casque sans fil · Prix : 450 000 Ar', 'Titre : WH-CH720N · Marque : Sony', 'Première affiche'])
  expect(modifications([version('b', { headline: { title: 'Sony' } }), version('a')])[0].label).toBe('Nouvelle version')  // a price no longer drawn is not a word of the image
  expect(modifications([version('b', { headline: { title: 'Sony', brand: null, price_ar: 700000 } }), version('a', { headline: { title: 'Sony', brand: 'Sony', price_ar: 700000 } })])[0].label).toBe('Marque : retiré')
})
it('knows the poster a pending read was sent for', () => {
  expect(pendingFor(newPending({ text: 'fond plus sombre', creation_id: 'c' } as { text: string }))).toBe('c')
  expect(pendingFor(newPending({ text: 'Sony' }))).toBeNull()
  expect(pendingFor({ key: 'k', body: '{nope', text: 'x' })).toBeNull()
})

it('takes the identity choice back from the last recap when the draft was saved by an older bundle', () => {
  const recap = (identity?: boolean) => ({ id: String(identity), role: 'app', text: 'x', at: 1, card: { kind: 'recap', name: 'Sony', price_ar: 1, ...(identity === undefined ? {} : { identity }) } })
  const stored = (draft: object, ...items: object[]) => readThread(JSON.stringify({ items, draft })).draft.identity
  // An old tab, refused, rebuilt its recap and saved its draft without the key: the owner's choice is still in the thread.
  expect(stored({ name: 'Sony' }, recap(true), recap())).toBe(true)
  expect(stored({ name: 'Sony' }, recap(true), recap(false))).toBe(false)
  expect(stored({ name: 'Sony' }, recap())).toBeNull()
  // A draft saved by this bundle says it, null included: the thread is not asked.
  expect(stored({ name: 'Sony', identity: null }, recap(true))).toBeNull()
  expect(stored({ name: 'Sony', identity: false }, recap(true))).toBe(false)
})

// D-MULTI-SHOP-007: what stays on the device per shop. Shop 1 is open for these.
const open1 = () => { bind(1); open() }
const recapItem = (extra: Partial<Item> = {}) => item({ id: 'r', card: { kind: 'recap', name: 'Sony' }, ...extra })
it('calls unresolved a paid card that waits for its answer, followed or with its request kept, and nothing else', () => {
  expect(unresolved(recapItem({ spent: true, request, job: 'j' }))).toBe(true)  // followed
  expect(unresolved(recapItem({ spent: true, request }))).toBe(true)  // « Reprendre »
  expect(unresolved(item({ card: { kind: 'change', effect: 'scene' }, spent: true }))).toBe(true)
  expect(unresolved(recapItem({ spent: true, request, done: true }))).toBe(false)  // retired by a final refusal
  expect(unresolved(recapItem())).toBe(false)  // never tapped
  expect(unresolved(item({ card: { kind: 'steps' }, spent: true }))).toBe(false)  // a card that pays for nothing
})
// ADR-108: strict send. The adapter calls `sending` right before the paid request leaves (App.vue generateScene,
// refineScene); the chat's `sending` is keepRequest with its save.
it('lets a paid request leave only once the thread holding it and its key is written; a refused write keeps it from leaving', () => {
  open1()
  const leave = (item: Item, storage: Storage) => {
    const save = () => { try { storage.setItem(threadKey('c'), JSON.stringify({ at: 1, items: [item] })); return true } catch { return false } }
    keepRequest(item, request, save)
    return storage.getItem(threadKey('c'))  // what this device holds as the request leaves
  }
  const card = recapItem({ spent: true }), stored = leave(card, memory())
  expect(JSON.parse(stored!).items).toEqual([{ ...card, request }])  // the request and its key (the card's id), written first
  const refused = recapItem({ spent: true }), sent: unknown[] = []
  expect(() => sent.push(leave(refused, memory({}, () => true)))).toThrow(UNSTORED)
  expect([sent, refused.request]).toEqual([[], undefined])  // nothing left, and the card no longer holds a request
  expect(UNSTORED).toBe('Ce navigateur ne peut pas garder la demande : rien n’a été envoyé. Utilisez Pas à pas.')
})
// Review r5 P2-2: the cap never takes the thread just written, nor one whose paid card waits, whatever their dates (a
// device clock set back); and a thread counts as stored only when it is there as written.
it('writes a thread and caps the others: never the one just written nor one whose paid card waits; true only when stored', () => {
  open1()
  const ahead = Date.now() + 86_400_000, entries: Record<string, string> = {}
  for (let index = 0; index < 30; index++) entries[threadKey(`ahead${index}`)] = JSON.stringify({ at: ahead + index, items: [] })
  entries[threadKey('old-paid')] = JSON.stringify({ at: 1, items: [recapItem({ spent: true, request })] })
  entries[threadKey('old')] = JSON.stringify({ at: 2, items: [] })
  const storage = memory(entries), value = JSON.stringify({ at: Date.now(), items: [item()] })
  expect(storeThread(storage, storage, threadKey('c'), value)).toBe(true)
  expect(storage.getItem(threadKey('c'))).toBe(value)  // dated before the thirty: kept all the same
  expect(storage.getItem(threadKey('old-paid'))).not.toBeNull()  // its paid card waits
  expect(storage.getItem(threadKey('old'))).toBeNull()  // the oldest with nothing waiting goes
  const silent = memory()
  silent.setItem = () => {}  // takes the write without keeping it
  expect(storeThread(silent, silent, threadKey('c'), value)).toBe(false)
})
// Review r5 P2-3: « Se déconnecter » from a tab that does not hold the chat, or from the editor, reads the stored threads.
it('says that a paid image waits from the stored threads, read only; storage that cannot be read says yes', () => {
  open1()
  const waiting = JSON.stringify({ at: 1, items: [recapItem({ spent: true, request })] })
  expect(waitingIn(memory({ [threadKey('c')]: waiting }, () => true))).toBe(true)  // read only: every write would be refused
  expect(waitingIn(memory({ [threadKey('c')]: JSON.stringify({ at: 1, items: [recapItem({ spent: true, request, done: true })] }), [unsentKey()]: 'Sony' }))).toBe(false)
  const unlisted = memory({ [threadKey('c')]: waiting })
  Object.defineProperty(unlisted, 'length', { get: () => { throw new DOMException('denied', 'SecurityError') } })
  expect(waitingIn(unlisted)).toBe(true)
  expect(waitingIn(null)).toBe(true)
})
