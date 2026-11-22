import { expect, it } from 'vitest'
import { ApiError } from '../src/api'
import {
  aloneLine, alreadyLine, answered, atLimit, codePoints, crossed, describe as described, dropIndex, moveTo, placeLine, reorder, SLACK, emptyDraft, faultLine, keptForSending,
  limitLine, move, postLine, publishAction, readDraft, readStored, refusalOf, remove, requestOf, seenOf, takenOut, toggle, whyNot,
  without, type Candidate, type Draft, type Post,
} from '../src/publish'

const [a, b, c, d] = Array.from({ length: 4 }, () => crypto.randomUUID())
const page = { id: '100000000000001', name: 'Page d’essai 1', state: 'connected' as const }
const candidate = (id: string, change: Partial<Candidate> = {}): Candidate => ({
  id, name: 'Casque', title: `Affiche ${id.slice(0, 4)}`, price_ar: 450000, confirmation_id: crypto.randomUUID(),
  thumbnail_url: '/api/thumbnails/x?v=1', download_url: '/api/confirmations/x/download', last: null, published_at: null, pending: false, ...change })
const post = (status: Post['status'], change: Partial<Post> = {}): Post => ({
  id: crypto.randomUUID(), status, page_id: page.id, page_name: page.name, sent_at: '2026-11-21T08:00:00+00:00',
  settled_at: null, count: 3, done: 0, failed_position: null, link: null, error_code: null, said_by_owner: false,
  stop_asked: false, message_fr: `ligne ${status}`, items: [], ...change })
const draft = (change: Partial<Draft> = {}): Draft => ({ items: [a, b], description: 'Texte', stamp: crypto.randomUUID(), post: null, ...change })

it('adds at the end, takes out, moves earlier and later, and makes another draft at each edit only', () => {
  let current = emptyDraft()
  const stamps = new Set([current.stamp])
  for (const id of [a, b, c]) { current = toggle(current, id, null); stamps.add(current.stamp) }
  expect(current.items).toEqual([a, b, c])
  current = move(current, c, -1); stamps.add(current.stamp)
  expect(current.items).toEqual([a, c, b])
  current = move(current, a, 1); stamps.add(current.stamp)
  expect(current.items).toEqual([c, a, b])
  expect(move(current, c, -1)).toBe(current)  // already first: nothing changes, not even the stamp
  expect(move(current, b, 1)).toBe(current)
  expect(move(current, d, 1)).toBe(current)
  current = toggle(current, a, null); stamps.add(current.stamp)  // a tap on a chosen poster takes it out
  expect(current.items).toEqual([c, b])
  current = remove(current, c); stamps.add(current.stamp)
  current = described(current, 'Texte'); stamps.add(current.stamp)
  expect(current).toMatchObject({ items: [b], description: 'Texte', post: null })
  expect(stamps.size).toBe(9)  // the empty draft's, then one per edit
  // An edit is another draft: the post made from the one before is not its own.
  expect(described({ ...current, post: d }, 'Autre').post).toBeNull()
  // Taken out at the opening: no longer the request its stamp was sent with, so a new stamp and no post; nothing taken
  // out, the very same draft.
  const resolved = without({ ...current, post: d }, new Set([b]))
  expect(resolved).toMatchObject({ items: [], description: 'Texte', post: null })
  expect(resolved.stamp).not.toBe(current.stamp)
  const untouched = { ...current, post: d }
  expect(without(untouched, new Set([a, c]))).toBe(untouched)
})

it('slides a dragged row past the neighbours whose middles it crosses, and drops it as one edit only if the order changed', () => {
  const middles = [100, 200, 300, 400]  // four rows of 100 px, their middles in page pixels
  expect(dropIndex(middles, 0, 100)).toBe(0)
  expect(dropIndex(middles, 0, 100 + SLACK)).toBe(0)  // inside the slack: stays
  expect(dropIndex(middles, 1, 200 - SLACK)).toBe(1)
  expect(dropIndex(middles, 0, 199)).toBe(0)  // not yet past the next middle
  expect(dropIndex(middles, 0, 201)).toBe(1)  // down past one
  expect(dropIndex(middles, 0, 305)).toBe(2)  // down past two
  expect(dropIndex(middles, 3, 150)).toBe(1)  // up past two
  expect(dropIndex(middles, 2, 199)).toBe(1)  // up past one
  expect(dropIndex(middles, 1, -500)).toBe(0)  // the ends hold
  expect(dropIndex(middles, 1, 5000)).toBe(3)
  expect(dropIndex([100], 0, 400)).toBe(0)
  expect(reorder(['x', 'y', 'z'], 2, 0)).toEqual(['z', 'x', 'y'])
  expect(reorder(['x', 'y', 'z'], 0, 2)).toEqual(['y', 'z', 'x'])
  const list = ['x', 'y']
  expect(reorder(list, 1, 1)).toEqual(list)
  expect(reorder(list, 1, 1)).not.toBe(list)  // a copy
  const current = draft({ items: [a, b, c], post: d })
  const dropped = moveTo(current, 2, 0)
  expect(dropped).toMatchObject({ items: [c, a, b], post: null })
  expect(dropped.stamp).not.toBe(current.stamp)  // one edit: a new stamp
  for (const [from, to] of [[1, 1], [0, 3], [-1, 0]]) expect(moveTo(current, from, to)).toBe(current)  // no edit
  expect(placeLine('Casque Sony', 1, 3)).toBe('Casque Sony : place 1 sur 3.')
})

it('stops adding at the shop’s limit, and says the limit by what the draft holds', () => {
  const two = toggle(toggle(emptyDraft(), a, 2), b, 2)
  expect(atLimit(two, 2)).toBe(true)
  expect(toggle(two, c, 2)).toBe(two)
  expect(toggle(two, a, 2).items).toEqual([b])  // taking out still works at the limit
  expect(atLimit(two, null)).toBe(false)
  expect(limitLine(2, null)).toBe('')
  expect(limitLine(1, 2)).toBe('')
  expect(limitLine(2, 2)).toBe('Votre publication compte 2 images, le plus permis : retirez-en une pour en ajouter une autre.')
  expect(limitLine(3, 2)).toBe('Retirez des affiches : 2 images au plus par publication.')
})

it('trusts nothing of the storage', () => {
  const kept = draft({ description: 'Ligne 1\nLigne 2 😀', post: d })
  expect(readDraft(JSON.stringify(kept))).toEqual(kept)
  for (const raw of [null, '', '{', 'null', '[]', JSON.stringify({ ...kept, items: [a, a] }), JSON.stringify({ ...kept, items: ['x'] }),
    JSON.stringify({ ...kept, description: 3 }), JSON.stringify({ ...kept, stamp: 's1' }), JSON.stringify({ ...kept, post: 'x' }),
    JSON.stringify({ items: [a], description: '', stamp: kept.stamp })]) expect(readDraft(raw)).toBeNull()
})

it('makes the draft’s stamp the request’s key: the same draft twice is one key, an edit another', () => {
  const live = draft(), items = [{ creation_id: a, confirmation_id: c, seen: null }]
  const first = requestOf(live.stamp, page.id, live.description, items), again = requestOf(live.stamp, page.id, live.description, items)
  expect(first).toEqual(again)
  expect(first).toEqual({ key: live.stamp, body: { page_id: page.id, description: 'Texte', items } })
  expect(requestOf(described(live, 'Autre').stamp, page.id, 'Autre', items).key).not.toBe(first.key)
  expect(requestOf(live.stamp, page.id, ' \n\t', items).body.description).toBe('')  // only blanks is no description
})

it('reads the stored draft three ways apart: only nothing kept is an empty draft', () => {
  const kept = draft({ post: d })
  expect(readStored(() => JSON.stringify(kept))).toEqual({ state: 'read', draft: kept })
  expect(readStored(() => null)).toEqual({ state: 'absent' })
  expect(readStored(() => { throw new DOMException('refusé', 'SecurityError') })).toEqual({ state: 'unreadable' })
  for (const raw of ['{', '', 'null', JSON.stringify({ ...kept, stamp: 'x' })]) expect(readStored(() => raw)).toEqual({ state: 'damaged' })
})

it('sends nothing when the device does not keep the draft, written and read back', () => {
  const storage = (refuse: 'write' | 'read' | null = null) => ({ value: null as string | null,
    get() { if (refuse === 'read') throw new DOMException('refusé', 'SecurityError'); return this.value },
    set(value: string) { if (refuse === 'write') throw new DOMException('plein', 'QuotaExceededError'); this.value = value } })
  const live = draft(), fine = storage()
  expect(keptForSending(fine, live)).toBe('kept')
  expect(readDraft(fine.value)).toEqual(live)
  expect(keptForSending(storage('write'), live)).toBe('unkept')
  expect(keptForSending(storage('read'), live)).toBe('unkept')
  expect(keptForSending({ get: () => JSON.stringify({ ...live, stamp: d }), set: () => undefined }, live)).toBe('unkept')  // written, not kept
  for (const change of [{ description: live.description + '…' }, { items: [...live.items].reverse() }, { post: d }]) {
    expect(keptForSending({ get: () => JSON.stringify({ ...live, ...change }), set: () => undefined }, live)).toBe('unkept')
  }
})

it('handles every answer about the draft’s post by its status, against the stamp it was sent with', () => {
  const live = draft(), sent = live.stamp
  for (const status of ['uploading', 'posting', 'unknown'] as const) {
    const answer = post(status)
    expect(answered(live, answer, sent)).toEqual({ draft: { ...live, post: answer.id }, write: true })  // followed, stamp kept
    expect(answered({ ...live, post: answer.id }, answer, sent)).toEqual({ draft: { ...live, post: answer.id }, write: false })
  }
  const failed = answered({ ...live, post: d }, post('failed', { id: d }), sent)
  expect(failed.write).toBe(true)
  expect(failed.draft).toMatchObject({ items: live.items, description: live.description, post: null })
  expect(failed.draft!.stamp).not.toBe(sent)  // « Publier » is a new try
  expect(answered(live, post('published'), sent)).toEqual({ draft: null, write: true })
  // Edited since (kept on the device or not): left as it is, whatever the answer.
  const edited = described(live, 'Autre')
  for (const status of ['published', 'failed', 'unknown'] as const)
    expect(answered(edited, post(status), sent)).toEqual({ draft: edited, write: false })
})

it('names in the sheet what is already on the Page, by the latest date, and asks to publish again', () => {
  const day = (stamp: string) => stamp.slice(0, 10)
  const on = (stamp: string | null) => ({ published_at: stamp })
  expect(alreadyLine([], day)).toEqual({ line: '', label: 'Publier' })
  expect(alreadyLine([on(null), on(null)], day)).toEqual({ line: '', label: 'Publier' })
  expect(alreadyLine([on('2026-11-20T08:00:00+00:00')], day)).toEqual({ label: 'Publier à nouveau',
    line: 'Cette affiche est déjà sur votre Page depuis le 2026-11-20. Publier à nouveau ?' })
  expect(alreadyLine([on(null), on('2026-11-20T08:00:00+00:00')], day).line).toBe('Une de ces affiches est déjà sur votre Page (le 2026-11-20). Publier à nouveau ?')
  expect(alreadyLine([on('2026-11-19T08:00:00+00:00'), on(null), on('2026-11-21T08:00:00+00:00')], day)).toEqual({ label: 'Publier à nouveau',
    line: '2 de ces affiches sont déjà sur votre Page (la dernière le 2026-11-21). Publier à nouveau ?' })
})

it('tells a refusal, after which the draft and its stamp stay, from no answer, after which the same request goes again', () => {
  const error = (code: string, status: number) => new ApiError(code, 'phrase', status)
  for (const [code, status] of [['facebook_stale', 409], ['facebook_running', 409], ['facebook_too_many', 422], ['caption_invalid', 422],
    ['terms_required', 403], ['idempotency_reused', 409], ['export_missing', 503], ['rate_limited', 429]] as const) expect(refusalOf(error(code, status))).not.toBeNull()
  for (const [code, status] of [['network', 0], ['timeout', 0], ['server_error', 500], ['provider_unavailable', 503], ['invalid_response', 409]] as const)
    expect(refusalOf(error(code, status))).toBeNull()
  expect(refusalOf(new Error('x'))).toBeNull()
})

it('after crossed reads, re-reads the marks of a post known settled and reads a post the list does not hold', () => {
  const [x, y, z] = [crypto.randomUUID(), crypto.randomUUID(), crypto.randomUUID()]
  const flying = (id: string, status: 'uploading' | 'posting' = 'uploading') => ({ last: { id, status } })
  expect(crossed([], [])).toEqual({ marks: [], posts: [] })
  expect(crossed([candidate(a), candidate(b, { last: { id: x, status: 'published' } })], [])).toEqual({ marks: [], posts: [] })  // nothing in flight
  // The candidates say X is in flight: the list shows it published (read the marks again), or still in flight (the
  // polling follows it), or does not hold it (read it by its id). One post shared by two posters is named once.
  for (const status of ['published', 'failed', 'unknown'] as const)
    expect(crossed([candidate(a, flying(x))], [post(status, { id: x })])).toEqual({ marks: [x], posts: [] })
  expect(crossed([candidate(a, flying(x, 'posting'))], [post('uploading', { id: x })])).toEqual({ marks: [], posts: [] })
  expect(crossed([candidate(a, flying(x)), candidate(b, flying(x))], [post('published', { id: y })])).toEqual({ marks: [], posts: [x] })
  expect(crossed([candidate(a, flying(x)), candidate(b, flying(z)), candidate(c, flying(y))],
    [post('published', { id: x }), post('posting', { id: y })])).toEqual({ marks: [x], posts: [z] })
})

it('sends as seen the id and the status of the latest post that holds the poster, or null', () => {
  expect(seenOf(candidate(a))).toBeNull()
  expect(seenOf(candidate(a, { last: { id: b, status: 'unknown' }, published_at: '2026-11-20T08:00:00+00:00' }))).toEqual({ id: b, status: 'unknown' })
})

it('says what « Publier… » does in each state, in order', () => {
  const ready = { page, accepted: true, checking: false, running: false, stale: false, chosen: [candidate(a), candidate(b)], limit: null, description: '' }
  expect(publishAction(ready)).toBe('ready')
  expect(publishAction({ ...ready, accepted: null })).toBe('ready')  // unread: the server decides
  expect(publishAction({ ...ready, page: null })).toBe('account')
  expect(publishAction({ ...ready, page: { ...page, state: 'reconnect' } })).toBe('account')
  expect(publishAction({ ...ready, accepted: false, checking: true })).toBe('terms')
  expect(publishAction({ ...ready, checking: true, running: true })).toBe('checking')
  expect(publishAction({ ...ready, running: true, stale: true })).toBe('running')
  // A chosen poster's latest post in flight (a reload of the page for one poster during its uploads): the same.
  for (const status of ['uploading', 'posting'] as const)
    expect(publishAction({ ...ready, chosen: [candidate(a, { last: { id: c, status } })] })).toBe('running')
  expect(publishAction({ ...ready, stale: true, chosen: [] })).toBe('stale')  // never back on with a stale `seen`
  expect(publishAction({ ...ready, chosen: [] })).toBe('empty')
  expect(publishAction({ ...ready, limit: 1 })).toBe('over')
  expect(publishAction({ ...ready, limit: 2 })).toBe('ready')
  expect(publishAction({ ...ready, chosen: [candidate(a, { last: { id: c, status: 'unknown' }, pending: true })] })).toBe('pending')
  // After a restore: an older post unknown while the latest is settled. `pending` holds it, whatever `last` says.
  expect(publishAction({ ...ready, chosen: [candidate(a), candidate(b, { last: { id: c, status: 'published' }, pending: true })] }))
    .toBe('pending')
  expect(whyNot('pending', null, '')).toBe('Une de ces affiches attend votre réponse sur une publication au résultat inconnu : répondez plus bas.')
  expect(publishAction({ ...ready, chosen: [candidate(a, { last: { id: c, status: 'failed' } })] })).toBe('ready')
  expect(publishAction({ ...ready, description: 'a\u0007b' })).toBe('description')
  expect(publishAction({ ...ready, description: '😀'.repeat(2001) })).toBe('description')
  expect(publishAction({ ...ready, description: '😀'.repeat(2000) + '\n\t' })).toBe('description')
  expect(publishAction({ ...ready, description: '😀'.repeat(1999) + '\n' })).toBe('ready')
  expect(publishAction({ ...ready, description: '   ' })).toBe('ready')  // only blanks is an empty description
  expect(whyNot('ready', null, '')).toBe('')
  expect(whyNot('account', null, '')).toBe('')
  expect(whyNot('over', 2, '')).toBe('Retirez des affiches : 2 images au plus par publication.')
  expect(whyNot('checking', null, '')).toBe('La réponse n’est pas arrivée. Je vérifie…')
  expect(whyNot('stale', null, '')).toBe('Vos affiches n’ont pas pu être relues : touchez « Réessayer ».')
  expect(whyNot('description', null, 'a\u0000')).toBe('La description contient un caractère de contrôle refusé.')
  expect(faultLine('x'.repeat(2001))).toBe('La description dépasse 2 000 caractères.')
  expect(faultLine('')).toBe('')
  expect(codePoints('😀é\n')).toBe(3)
})

it('names a poster taken out of a draft and whether its file can still be opened', () => {
  expect(takenOut(1, 'changed')).toBe('L’affiche 2 de votre publication a été retirée : elle a été modifiée depuis sa vérification.')
  expect(aloneLine('gone')).toEqual({ text: 'Cette affiche n’est plus dans vos affiches.', open: false })
  expect(aloneLine('other_format').open).toBe(true)
})

it('shows a post’s line in the server’s words, with Facebook’s own link and the controls of its state', () => {
  const link = 'https://www.facebook.com/100000000000001_42'
  expect(postLine(post('published', { link, count: 1 }))).toEqual({ state: 'ligne published', link: { href: link, label: 'Voir la publication' },
    count: '1 image', ask: false, stop: false, stopping: false })
  expect(postLine(post('published', { link: 'https://www.facebook.com/100000000000001', said_by_owner: true })).link)
    .toEqual({ href: 'https://www.facebook.com/100000000000001', label: 'Ouvrir la Page' })
  expect(postLine(post('published', { link: 'https://evil.example/x' })).link).toBeNull()
  expect(postLine(post('unknown'))).toMatchObject({ link: { href: 'https://www.facebook.com/100000000000001', label: 'Ouvrir ma Page' }, ask: true, stop: false })
  expect(postLine(post('uploading'))).toMatchObject({ link: null, ask: false, stop: true, stopping: false, count: '3 images' })
  expect(postLine(post('uploading', { stop_asked: true }))).toMatchObject({ stop: false, stopping: true })
  for (const status of ['posting', 'failed'] as const) expect(postLine(post(status, { link }))).toMatchObject({ link: null, ask: false, stop: false })
})
