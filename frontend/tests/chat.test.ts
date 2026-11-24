import { expect, it } from 'vitest'
import { bind, open } from '../src/api'
import { amountsOf, cardButton, CHANGE_BUTTONS, changes, chosenKit, complete, createName, effectOf, productsOf, identityLine, isThread, keepRequest, kitChips, kitDraft, kitOf, linesLine, newLines, ownTitle, paid, fate, final, limitLine, modifications, nextStep, normal, ROLE_NAMES, sceneLine, staleLine, staleOf, lines, movedTo, newPending, nextRole, pendingFor, pendingKey, picturesOfRecap, recapFormat, readPending, readThread, settled, spend, storeThread, supersede, swapLabel, swapRole, textOf, threadKey, titleLine, TITLES, trim, unresolved, unsentKey, UNSTORED, versionsLeft, waitingIn, warns, wireDraft, type Item, type Role } from '../src/chat'
import type { Visual } from '../src/document'
import { memory } from './fixture'

const pictures = (...roles: Role[]) => roles.map((role, index) => ({ id: `p${index}`, role, asset: `a${index}` }))
const item = (extra: Partial<Item> = {}): Item => ({ id: 'i', role: 'app', text: 'x', at: 1, ...extra })

it('makes every attached image a product photo, three at most; a style model only by a touch on its label (D-KIT-006)', () => {
  expect(nextRole([])).toBe('product')
  expect(nextRole(pictures('product'))).toBe('product')  // never a style model by its position
  expect(nextRole(pictures('product', 'product'))).toBe('product')
  expect(nextRole(pictures('product', 'product', 'product'))).toBeNull()
  expect(nextRole(pictures('inspiration', 'product', 'product'))).toBe('product')  // the style photo is not a product
  expect(nextRole(pictures('product', 'inspiration', 'product', 'product'))).toBeNull()
  expect([ROLE_NAMES.product, ROLE_NAMES.inspiration]).toEqual(['Produit', 'Modèle de style'])
  // The touch's name begins with what the label shows (the name holds the visible words).
  expect(swapLabel('product')).toBe('Produit : marquer comme modèle de style')
  expect(swapLabel('inspiration')).toBe('Modèle de style : marquer comme produit')
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
it('shows the current request format on an open recap and the original format on a historical recap', () => {
  const [legacy, snapshot] = readThread(JSON.stringify({ items: [
    item({ card: { kind: 'recap' } }),
    item({ card: { kind: 'recap', format: 'square' }, done: true }),
  ] })).items
  expect(recapFormat(legacy, 'feed')).toBe('Publication 4:5')
  expect(recapFormat(legacy, 'story')).toBe('Story 9:16')
  expect(recapFormat(snapshot, 'story')).toBe('Carré 1:1')
  expect(recapFormat({ ...legacy, done: true }, 'feed')).toBeUndefined()
  const sent = { ...snapshot, spent: true, request: { path: '/scenes', revision: 1, body: { format: 'story' } } }
  expect(recapFormat(sent, 'feed')).toBe('Story 9:16')
  expect(recapFormat({ ...sent, request: { ...sent.request, body: { format: 'unknown' } } }, 'feed')).toBeUndefined()
})

it('restores older recap photos using the original poster and its sent inspiration', () => {
  const current = pictures('product', 'inspiration')
  const body = { format: 'feed', style_reference_asset: 'old-reference' }
  const legacy = item({ creation: 'p', spent: true, request: { path: '/scenes', body, revision: 2 }, card: { kind: 'recap' } })
  expect(picturesOfRecap(legacy, current, 'p')).toEqual([current[0], { role: 'inspiration', asset: 'old-reference' }])
  expect(picturesOfRecap(legacy, current, 'other')).toEqual([{ role: 'inspiration', asset: 'old-reference' }])
  const [snapshot] = readThread(JSON.stringify({ items: [{ ...item({ done: true }), card: { kind: 'recap', pictures: [{ role: 'product', asset: 'before' }, null] } }] })).items
  expect(picturesOfRecap(snapshot, current, 'p')).toEqual([{ role: 'product', asset: 'before' }])
  expect(picturesOfRecap(item({ card: { kind: 'recap' } }), current)).toEqual(current)
})

it('keeps the last 100 items of a thread', () => {
  const many = Array.from({ length: 130 }, (_, index) => item({ id: String(index) }))
  expect(trim(many)).toHaveLength(100)
  expect(trim(many)[0].id).toBe('30')
  expect(readThread(JSON.stringify({ items: many })).items).toHaveLength(100)
})
it('never trusts the storage: a damaged thread is empty and wrong fields are left out', () => {
  expect(readThread('{nope')).toEqual({ items: [], draft: { name: null, price_ar: null, style: null, identity: null, pictures: [], scene_fr: null, offer_lines: [], lines: true, look: null, title: null } })
  const read = readThread(JSON.stringify({ items: [item(), { id: 1, role: 'app', text: 'x' }, { id: 'b', role: 'robot', text: 'x' }, item({ id: 'c', card: {} as any }), null],
    draft: { name: 'Sony', price_ar: '700000', style: 'rose', pictures: [{ asset: 'a', role: 'product' }, { asset: 'b', role: 'logo' }, 7], scene_fr: 5, offer_lines: ['Garantie 6 mois', 3, ' '], lines: 'off', look: 7, title: 'gothique' } }))
  expect(read.items.map(entry => entry.id)).toEqual(['i'])
  expect(read.draft).toEqual({ name: 'Sony', price_ar: null, style: null, identity: null, pictures: [{ asset: 'a', role: 'product' }], scene_fr: null, offer_lines: ['Garantie 6 mois'], lines: true, look: null, title: null })
  // The owner's scene words, his switch and his kit row come back as he left them.
  expect(readThread(JSON.stringify({ items: [], draft: { scene_fr: 'fond rouge', lines: false, look: 'L1', title: 'condense' } })).draft).toMatchObject({ scene_fr: 'fond rouge', offer_lines: [], lines: false, look: 'L1', title: 'condense' })
  // Scene words over the reader's 500 characters are left out: sent back, every read of the thread would be refused.
  expect(readThread(JSON.stringify({ items: [], draft: { scene_fr: 'a'.repeat(500) } })).draft.scene_fr).toBe('a'.repeat(500))
  expect(readThread(JSON.stringify({ items: [], draft: { scene_fr: 'a'.repeat(501) } })).draft.scene_fr).toBeNull()
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
  expect(readThread(movedTo(id))).toEqual({ items: [], draft: { name: null, price_ar: null, style: null, identity: null, pictures: [], scene_fr: null, offer_lines: [], lines: true, look: null, title: null }, moved: id })
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
  // The request's lines against the shop's profile: the same old lines are refused again; a new card shows the shop's own.
  for (const code of ['shop_lines_changed', 'shop_lines_missing']) expect(final(code), code).toBe(true)
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
  const draft = { name: 'Sony', price_ar: 700000, style: 'sombre' as const, identity: null, pictures: [{ asset: 'a', role: 'product' as Role }, { asset: 'b', role: 'inspiration' as Role }],
    scene_fr: null, offer_lines: ['Garantie 6 mois'], lines: true, look: 'L1', title: 'condense' as const }
  expect(wireDraft(draft)).toEqual({ name: 'Sony', price_ar: 700000, style: 'sombre', product_photos: 1, inspiration: true })
  // The scene words go back to the reader only once it gave some (a server from before refuses an unknown key); the
  // offered lines, the switch, the saved look and the title never leave this device (the reader's style stays a house one).
  expect('scene_fr' in wireDraft(draft)).toBe(false)
  expect(wireDraft({ ...draft, scene_fr: 'fond rouge' })).toEqual({ name: 'Sony', price_ar: 700000, style: 'sombre', product_photos: 1, inspiration: true, scene_fr: 'fond rouge' })
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
it('offers the editor’s free copy on a photo card; never a paid card (D-TEXT-FIRST-007)', () => {
  const a = 'a'.repeat(64), b = 'b'.repeat(64)
  const photo = item({ card: { kind: 'photo', pictures: [{ asset: a, role: 'product' }] } })
  expect(cardButton(photo)).toBe('copy')
  expect(cardButton({ ...photo, done: true })).toBeNull()
  // What stops a new image stops the copy: it would stay without one. The conditions are offered, as on a paid card.
  expect(cardButton(photo, undefined, undefined, null, true)).toBeNull()
  expect(cardButton(photo, undefined, undefined, null, 'terms')).toBe('conditions')
  // Nothing of it is a paid card: no request is kept, followed or waited for.
  expect([paid(photo.card), changes(photo.card), unresolved({ ...photo, spent: true })]).toEqual([false, false, false])
  // Its product photos, as stored data: distinct, three at most, and nothing that is not a product photo.
  expect(productsOf({ kind: 'photo', pictures: [{ asset: a, role: 'product' }, { asset: a, role: 'product' }, { asset: b, role: 'inspiration' }, { asset: 5 } as any, null as any] })).toEqual([a])
  expect(productsOf({ kind: 'photo', pictures: ['1', '2', '3', '4'].map(asset => ({ asset, role: 'product' as const })) })).toEqual(['1', '2', '3'])
  expect(productsOf({ kind: 'photo', pictures: 'x' as any })).toEqual([])
  expect(cardButton(item({ card: { kind: 'photo', pictures: [{ asset: b, role: 'inspiration' }] } }))).toBeNull()
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
it('warns about unlisted features on a scene adjustment until it has its outcome, never on another card (D-TERMS-005)', () => {
  const offered = item({ card: { kind: 'change', effect: 'refine', instruction_fr: 'ajoute ses caractéristiques', visual_id: 'v' } })
  expect(warns(offered)).toBe(true)
  // Restored from the device, in today's shape and in the shape from before `effect` (normal makes it a refinement).
  const stored = readThread(JSON.stringify({ items: [offered, { ...offered, id: 'old', card: { kind: 'change', change: 'scene', instruction_fr: 'ajoute 4 specs' } }] })).items
  expect(stored.map(warns)).toEqual([true, true])
  // Only when the words could ask for features or text (ADR-125): the owner's message or the instruction read from it.
  expect(warns(item({ card: { kind: 'change', effect: 'refine', instruction_fr: 'Podium plus petit', said: 'Podium smaller', visual_id: 'v' } }))).toBe(false)
  expect(warns(item({ card: { kind: 'change', effect: 'refine', instruction_fr: 'Ajouter les points forts', said: 'mets ce qu’il faut', visual_id: 'v' } }))).toBe(true)
  expect(warns(item({ card: { kind: 'change', effect: 'refine', instruction_fr: 'fond bleu', said: 'fond bleu et ajoute la config', visual_id: 'v' } }))).toBe(true)
  expect(warns(item({ card: { kind: 'change', effect: 'refine', visual_id: 'v' } }))).toBe(false)  // a stored card without its words
  // Tapped and kept for « Réessayer » or « Reprendre »: still a request for an adjustment.
  const kept = { path: '/api/creations/c/refinements', body: {}, revision: 2 }
  expect(warns({ ...offered, spent: true, request: kept })).toBe(true)
  expect(warns({ ...offered, spent: true, request: kept, card: { ...offered.card!, error: 'Connexion interrompue' } })).toBe(true)
  // Refused, then offered again as a new card (ChatView again): the old one is done, the new one warns.
  expect(warns({ ...offered, spent: true, done: true, card: { ...offered.card!, error: 'x' } })).toBe(false)
  expect(warns({ ...offered, id: 'again' })).toBe(true)
  expect(warns({ ...offered, done: true })).toBe(false)  // its version came, or a later card replaced it
  // A new scene, a free change, a restyle, a card from before that sets the price, the recap and a result send no adjustment.
  for (const card of [{ kind: 'change', effect: 'scene' as const, words: { title: 'Sony' } }, { kind: 'change', effect: 'free' as const, words: { price_ar: 650000 } },
    { kind: 'restyle', style: 'sombre' as const }, { kind: 'change', words: { price_ar: 550000 } }, { kind: 'recap' }, { kind: 'result', visual_id: 'v' }])
    expect(warns(item({ card })), card.kind).toBe(false)
  expect(warns(item())).toBe(false)
})
it('stops only a new paid tap at zero credits or while blocked; « Reprendre » and « Réessayer » stay (D-BALANCE-006)', () => {
  const kept = { path: '/api/creations/c/scenes', body: {}, revision: 2 }
  for (const card of [{ kind: 'recap' }, { kind: 'change', effect: 'refine' as const }, { kind: 'change', effect: 'scene' as const }, { kind: 'restyle', style: 'sombre' as const }]) {
    expect(cardButton(item({ card }), undefined, undefined, null, true)).toBeNull()  // its sentence in place of the button
    expect(cardButton(item({ card }), undefined, undefined, null, false)).toBe('create')
    // A kept request is not a new one: the server answers what it stored, or refuses it with its own sentence.
    expect(cardButton(item({ card, spent: true, request: kept }), undefined, undefined, 0, true)).toBe('resume')
    expect(cardButton(item({ card: { ...card, error: 'Il ne vous reste plus de crédit' }, spent: true, request: kept }), undefined, undefined, 0, true)).toBe('retry')
  }
  // A free price change costs nothing: ChatView never passes `stop` for it (`!free(item) && state.credit.stop`).
  const free = item({ card: { kind: 'change', effect: 'free', words: { price_ar: 650000 } } })
  expect(effectOf(free.card!)).toBe('free')
  expect(cardButton(free, undefined, undefined, null, false)).toBe('create')
  // Other cards do not pay, and are as they were.
  expect(cardButton(item({ card: { kind: 'ask_photo' } }), undefined, undefined, null, true)).toBe('photo')
  expect(cardButton(item({ card: { kind: 'result', visual_id: 'v' } }), 'approved', 'v', null, true)).toBe('download')
})
it('offers the conditions on a fresh paid card they stop, and keeps the same-key action of a retained one (D-TERMS-004)', () => {
  const kept = { path: '/api/creations/c/scenes', body: {}, revision: 2 }
  for (const card of [{ kind: 'recap' }, { kind: 'change', effect: 'refine' as const }, { kind: 'change', effect: 'scene' as const }, { kind: 'restyle', style: 'sombre' as const }]) {
    expect(cardButton(item({ card }), undefined, undefined, null, 'terms')).toBe('conditions')  // never a dead end
    expect(cardButton(item({ card }), undefined, undefined, 3, 'terms')).toBe('conditions')
    // Retained: sent again as it is; the server replays an admitted key, or refuses a new one with 403 (the dialog).
    expect(cardButton(item({ card, spent: true, request: kept }), undefined, undefined, null, 'terms')).toBe('resume')
    expect(cardButton(item({ card: { ...card, error: 'Acceptez d’abord les conditions' }, spent: true, request: kept }), undefined, undefined, null, 'terms')).toBe('retry')
    expect(cardButton(item({ card, spent: true, request: kept, job: 'j' }), undefined, undefined, null, 'terms')).toBeNull()  // followed
    expect(cardButton(item({ card, done: true }), undefined, undefined, null, 'terms')).toBeNull()
    expect(cardButton(item({ card, spent: true }), undefined, undefined, null, 'terms')).toBeNull()
  }
  // Cards that pay for nothing are as they were.
  expect(cardButton(item({ card: { kind: 'ask_photo' } }), undefined, undefined, null, 'terms')).toBe('photo')
  expect(cardButton(item({ card: { kind: 'result', visual_id: 'v' } }), 'pending_review', undefined, null, 'terms')).toBe('review')
  expect(cardButton(item({ card: { kind: 'failed', retry: 'Sony' } }), undefined, undefined, null, 'terms')).toBe('resend')
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

it('says on the recap the scene and the shop’s lines it will draw (D-KIT-004, D-KIT-005, D-KIT-006)', () => {
  expect(sceneLine('Studio clair')).toBe('Scène : Studio clair')
  expect(sceneLine('Luxe sombre', 'fond rouge avec des flammes')).toBe('Scène : Luxe sombre, avec vos mots : « fond rouge avec des flammes »')
  expect(sceneLine(null, null, true)).toBe('Scène : votre modèle de style (lu, puis gardé dans votre kit)')
  expect(sceneLine(null, 'sur une table en bois')).toBe('Scène : votre modèle de style, avec vos mots : « sur une table en bois »')
  expect(linesLine(['Garantie 6 mois', 'Paiement Mvola'])).toBe('Lignes de la boutique : Garantie 6 mois · Paiement Mvola')
  expect(linesLine([])).toBe('')
})
it('offers only the lines the shop does not hold yet, compared without case (D-KIT-005)', () => {
  // A tap kept « Garantie 6 mois », then failed before the poster: the next recap draws it once, as a shop line.
  expect(newLines(['garantie 6 MOIS', 'Paiement Mvola'], ['Garantie 6 mois'])).toEqual(['Paiement Mvola'])
  expect(newLines(['Garantie 6 mois'])).toEqual(['Garantie 6 mois'])  // a shop with no line known
  expect(newLines([], ['Garantie 6 mois'])).toEqual([])
})
it('pays for a shop line as for a new scene, under its own button (D-KIT-005)', () => {
  const line = item({ card: { kind: 'line', visual_id: 'v', lines: ['Garantie 6 mois'], words: { title: 'Sony' }, effect: 'scene' } })
  expect([paid(line.card), changes(line.card)]).toEqual([true, true])
  expect(effectOf({ kind: 'line' }, { headline: null })).toBe('scene')  // never free, even without its effect
  expect(cardButton(line)).toBe('create')
  expect(cardButton(line, undefined, undefined, 0)).toBeNull()  // the version limit holds for it
  expect(cardButton({ ...line, spent: true, request })).toBe('resume')
  // Its line refused by the server: the way to « Mon compte », where the shop's lines are, never « Pas à pas ».
  expect(cardButton({ ...line, spent: true, done: true, card: { ...line.card!, error: 'refusée', account: true } })).toBe('account')
  expect(unresolved({ ...line, spent: true, request })).toBe(true)
  expect(warns(line)).toBe(false)
  expect(createName(line.card!, 'scene')).toBe('Garder et refaire l’affiche')
  expect([createName({ kind: 'recap' }, null), createName({ kind: 'change' }, 'refine'), createName({ kind: 'restyle' }, 'scene')]).toEqual(['Créer l’affiche', 'Créer', 'Refaire l’affiche'])
})
it('offers one button per amount read, from the card as stored (D-KIT-002)', () => {
  expect(amountsOf({ kind: 'ask_price', amounts: [13_700_000, 700_000] })).toEqual([13_700_000, 700_000])
  expect(amountsOf({ kind: 'ask_price', amounts: [250_000, 250_000, 0, -5, 1.5, '9' as any, 1, 2, 3, 4] })).toEqual([250_000, 1, 2, 3])
  expect(amountsOf({ kind: 'ask_price' })).toEqual([])  // a server from before: the question alone, no button
  expect(amountsOf({ kind: 'ask_price', amounts: 'x' as any })).toEqual([])
  expect(cardButton(item({ card: { kind: 'ask_price', amounts: [250_000] } }))).toBeNull()  // a tap is free: no paid button
})
it('draws the unused parts apart from the card’s sentence, and a card from before as it is (D-KIT-004)', () => {
  const unused = '« publie-la sur Facebook » : je ne sais pas le mettre sur l’affiche. Dites-le autrement.'
  expect(textOf(`Voici l’affiche que je vais créer.\n${unused}\nJ’ai changé : le style (avant : Studio clair).`, { kind: 'recap', unused_fr: [unused] }))
    .toBe('Voici l’affiche que je vais créer.\nJ’ai changé : le style (avant : Studio clair).')
  expect(textOf(`Écrivez le produit et son prix.\n${unused}`, { kind: 'unclear' })).toBe(`Écrivez le produit et son prix.\n${unused}`)
  expect(textOf('Écrivez le produit et son prix.')).toBe('Écrivez le produit et son prix.')
})

// D-KIT-009: the kit in the message box.
const looks = [{ id: 'L1', name: 'Style 1', reference_asset: 'a1' }, { id: 'L2', name: 'Vitrine rouge', reference_asset: 'a2' }]
it('offers the house styles and the shop’s looks, the most recently used first; an unknown id is skipped (D-KIT-009)', () => {
  const ids = (...args: Parameters<typeof kitChips>) => kitChips(...args).map(chip => chip.id)
  expect(ids()).toEqual(['clair', 'couleur', 'sombre'])  // an adapter with no kit: the three house chips, as before
  expect(ids(looks)).toEqual(['clair', 'couleur', 'sombre', 'L1', 'L2'])
  expect(ids(looks, ['L2', 'sombre'])).toEqual(['L2', 'sombre', 'clair', 'couleur', 'L1'])
  // A removed look, another shop's id or a repeat in the list takes no place.
  expect(ids(looks, ['gone', 'L1', 'clair', 'L1'])).toEqual(['L1', 'clair', 'couleur', 'sombre', 'L2'])
  expect(ids([looks[1]], ['L1', 'couleur'])).toEqual(['couleur', 'clair', 'sombre', 'L2'])
  expect(kitChips(looks, ['L2'])[0]).toEqual({ id: 'L2', name: 'Vitrine rouge', asset: 'a2' })  // its model image
  expect(kitChips()[0]).toEqual({ id: 'clair', name: 'Studio clair' })  // a house style has none
})
it('takes the title of the scene by default: « Moderne » with a house style, the model’s own with a look or a style photo (D-KIT-012)', () => {
  expect(TITLES.map(([, name]) => name)).toEqual(['Moderne', 'Gras condensé', 'Italique sport', 'Élégant'])
  const draft = (look: string | null, title: 'moderne' | 'condense' | null = null) => ({ look, title })
  expect(chosenKit(draft(null))).toEqual({ look: undefined, model: false, title: undefined })
  expect(chosenKit(draft('L2'), looks)).toEqual({ look: looks[1], model: true, title: undefined })
  expect(chosenKit(draft(null), looks, true)).toEqual({ look: undefined, model: true, title: undefined })  // the style photo
  // A look the shop no longer has (or not read yet) is no scene: the house style is.
  expect(chosenKit(draft('gone'), looks)).toEqual({ look: undefined, model: false, title: undefined })
  // A style photo is the scene, whatever look the row held.
  expect(chosenKit(draft('L1'), looks, true)).toMatchObject({ look: undefined, model: true })
  // « Moderne » is a choice only with a model, whose default is its own lettering.
  expect(chosenKit(draft(null, 'moderne'))).toMatchObject({ title: undefined })
  expect(chosenKit(draft('L1', 'moderne'), looks)).toMatchObject({ title: 'moderne' })
  expect(chosenKit(draft(null, 'condense'))).toMatchObject({ title: 'condense' })
  expect(chosenKit(draft('L1', 'condense'), looks)).toMatchObject({ title: 'condense' })
  // The select keeps a title only when it is not the scene's default: the default follows the scene when it changes.
  expect([ownTitle('moderne', false), ownTitle('moderne', true), ownTitle('', true), ownTitle('sport', false), ownTitle('gothique', true)]).toEqual([null, 'moderne', null, 'sport', null])
})
it('says the title on the recap only when it is not the default (D-KIT-009)', () => {
  expect(titleLine('condense')).toBe('Titre : Gras condensé')
  expect(titleLine('serif')).toBe('Titre : Élégant')
  expect(titleLine(chosenKit({ look: null, title: null }).title)).toBe('')  // « Moderne » with a house style
  expect(titleLine(chosenKit({ look: 'L1', title: null }, looks).title)).toBe('')  // the model's own
  expect(titleLine(chosenKit({ look: 'L1', title: 'moderne' }, looks).title)).toBe('Titre : Moderne')
  expect(titleLine('gothique')).toBe('')  // a stored card is never trusted
})
it('passes the kit at the tap: the look chosen, the title when not the default, each part only when set (D-KIT-009)', () => {
  const house = chosenKit({ look: null, title: null }, looks)
  expect(kitOf(null, house, [], [])).toEqual({})
  expect(kitOf('fond rouge', house, ['Garantie 6 mois', 'Paiement Mvola'], ['Paiement Mvola'])).toEqual({ scene: 'fond rouge', lines: ['Garantie 6 mois', 'Paiement Mvola'], keep: ['Paiement Mvola'] })
  expect(kitOf(null, chosenKit({ look: 'L2', title: null }, looks), [], [])).toEqual({ look: 'L2' })
  expect(kitOf(null, chosenKit({ look: 'L2', title: 'sport' }, looks), [], [])).toEqual({ look: 'L2', title: 'sport' })
  expect(kitOf(null, chosenKit({ look: null, title: 'serif' }, looks), [], [])).toEqual({ title: 'serif' })
  // With a style photo the adapter reads the photo into a look: no saved look is sent beside it.
  expect(kitOf(null, chosenKit({ look: 'L2', title: null }, looks, true), [], [])).toEqual({})
  expect(kitOf(null, chosenKit({ look: 'gone', title: 'moderne' }, looks), [], [])).toEqual({})
})
it('starts a new poster from the kit’s last choices; the editor’s house style without them (D-KIT-009)', () => {
  expect(kitDraft()).toEqual({ style: 'clair', look: null, title: null })
  expect(kitDraft(undefined, 'sombre')).toEqual({ style: 'sombre', look: null, title: null })  // as before the kit
  expect(kitDraft(undefined, 'L1')).toEqual({ style: 'clair', look: null, title: null })  // a look id is not a house style
  expect(kitDraft({ look: 'L1', style: 'couleur', title: 'condense' }, 'sombre')).toEqual({ style: 'couleur', look: 'L1', title: 'condense' })
  expect(kitDraft({ look: 7, style: 'rose', title: 'gothique' }, 'sombre')).toEqual({ style: 'sombre', look: null, title: null })
})
