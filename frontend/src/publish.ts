// The « Publier sur Facebook » page (D-FB-POST-005): the draft of a post kept on this device (`post-draft`, the one object
// of this feature in the browser), whose stamp is the request's key, and what the page makes of the server's answers. A
// post's state is said in the server's words (message_fr), never in the page's.
import { ApiError } from './api'
import { captionFault } from './share'
import type { Format } from './document'

export type PostStatus = 'uploading' | 'posting' | 'published' | 'failed' | 'unknown'
export type Reason = 'other_format' | 'changed' | 'unconfirmed' | 'gone'
export interface Seen { id: string; status: PostStatus }
/** GET /api/facebook/posts/candidates: a poster that can go in a post, with the latest post that holds it on the Page
 *  (`last`, what `seen` sends) and `pending`: a post of it on the Page is unknown, whichever (the admission refuses it;
 *  after a restore it need not be the latest). */
export interface Candidate {
  id: string; name: string; title: string; price_ar: number; confirmation_id: string; thumbnail_url: string | null
  download_url: string; last: Seen | null; published_at: string | null; pending: boolean
}
/** With `ids`, a poster that cannot go, and why. */
export interface LeftOut { id: string; reason: Reason }
export interface ExcludedPoster {
  id: string; name: string; title: string; primary_format: Format; reason: Exclude<Reason, 'gone'>
}
export type Page = { id: string; name: string; state: 'connected' | 'reconnect' } | null
export interface Candidates {
  page: Page; post_image_limit: number | null; items: (Candidate | LeftOut)[]; next_cursor: string | null
  left_out: Record<Exclude<Reason, 'gone'>, number>
}
/** A post as the routes answer it. */
export interface Post {
  id: string; status: PostStatus; page_id: string; page_name: string; sent_at: string; settled_at: string | null
  count: number; done: number; failed_position: number | null; link: string | null; error_code: string | null
  said_by_owner: boolean; stop_asked: boolean; message_fr: string
  items: { position: number; creation_id: string; thumbnail_url: string | null }[]
}
/** `post-draft`: the posters' ids in order, the description, the stamp (a UUID made anew at each edit: the request's
 *  Idempotency-Key), and `post`, the id of the post made from this very stamp once an answer has named it. */
export interface Draft { items: string[]; description: string; stamp: string; post: string | null }
export type Item = { creation_id: string; confirmation_id: string; seen: Seen | null }
export interface PostBody { page_id: string; description: string; items: Item[] }

export const isCandidate = (item: Candidate | LeftOut): item is Candidate => 'confirmation_id' in item
/** What the page saw of a poster on the Page: the id and the status of its latest post there, or null. */
export const seenOf = (candidate: Candidate): Seen | null => candidate.last ? { id: candidate.last.id, status: candidate.last.status } : null
export const inFlight = (post: { status: PostStatus }) => post.status === 'uploading' || post.status === 'posting'

// ── the draft ───────────────────────────────────────────────────────────────────────────────────────────────
// An edit makes another draft: a new stamp (another request), and no post made from it yet.
const edited = (draft: Draft, change: Partial<Draft>): Draft => ({ ...draft, ...change, stamp: crypto.randomUUID(), post: null })
export const emptyDraft = (): Draft => ({ items: [], description: '', stamp: crypto.randomUUID(), post: null })
export const atLimit = (draft: Draft, limit: number | null) => limit !== null && draft.items.length >= limit
export const remove = (draft: Draft, id: string) => edited(draft, { items: draft.items.filter(item => item !== id) })
/** A tap on a poster of the grid: taken out when chosen, else added at the end; at the limit nothing is added. */
export function toggle(draft: Draft, id: string, limit: number | null) {
  if (draft.items.includes(id)) return remove(draft, id)
  return atLimit(draft, limit) ? draft : edited(draft, { items: [...draft.items, id] })
}
/** The list with its item at `from` put at `to`, the others closing up; a copy. */
export function reorder<T>(items: T[], from: number, to: number): T[] {
  const moved = [...items]
  moved.splice(to, 0, ...moved.splice(from, 1))
  return moved
}
/** A poster put at another place: one edit (a new stamp); at the same place, or out of range, the very same draft. */
export function moveTo(draft: Draft, from: number, to: number) {
  const last = draft.items.length - 1
  if (from === to || from < 0 || to < 0 || from > last || to > last) return draft
  return edited(draft, { items: reorder(draft.items, from, to) })
}
/** The handle's arrow keys: one place earlier (-1) or later (1); at an end nothing changes. */
export const move = (draft: Draft, id: string, by: -1 | 1) => { const at = draft.items.indexOf(id); return at < 0 ? draft : moveTo(draft, at, at + by) }
/** A drag starts only past this many pixels: a tap, or a finger that trembles, moves nothing. */
export const SLACK = 6
/** Sliding (D-FB-POST-005): the place a dragged row belongs at, from the rows' middles as laid out when the drag began
 *  (in page pixels, in their order), the dragged row's place then (`from`) and its middle now. It passes a neighbour
 *  when its middle crosses that neighbour's middle; within the slack it stays. */
export function dropIndex(middles: number[], from: number, middle: number) {
  if (Math.abs(middle - middles[from]) <= SLACK) return from
  let to = from
  while (to > 0 && middle < middles[to - 1]) to--
  while (to < middles.length - 1 && middle > middles[to + 1]) to++
  return to
}
/** What the assistive technology hears after a poster moved by its handle. */
export const placeLine = (title: string, place: number, total: number) => `${title} : place ${place} sur ${total}.`
export const describe = (draft: Draft, description: string) => edited(draft, { description })
/** The posters resolved at the opening that can no longer go are taken out. A draft that lost one is no longer the
 *  request its stamp was sent with (the server would answer that key `idempotency_reused`): a new stamp, no post. */
export function without(draft: Draft, gone: Set<string>): Draft {
  const items = draft.items.filter(id => !gone.has(id))
  return items.length === draft.items.length ? draft : { ...draft, items, stamp: crypto.randomUUID(), post: null }
}
/** The reads may cross after a reload: a chosen poster's `last` says a post is in flight while the posts' reads know
 *  more. `marks`: those posts they show settled (the candidates are read again); `posts`: those none of them holds
 *  (each is read by its id, then followed). A post the reads also show in flight is followed by the polling. */
export function crossed(chosen: Candidate[], known: Post[]) {
  const flying = [...new Set(chosen.flatMap(item => item.last && inFlight(item.last) ? [item.last.id] : []))]
  const byId = new Map(known.map(post => [post.id, post]))
  return { marks: flying.filter(id => byId.has(id) && !inFlight(byId.get(id)!)), posts: flying.filter(id => !byId.has(id)) }
}

// The storage is never trusted: anything of another shape is no draft.
const ID = /^[a-f0-9-]{36}$/
export function readDraft(raw: string | null): Draft | null {
  try {
    const value = JSON.parse(raw ?? 'null')
    if (value && Array.isArray(value.items) && value.items.every((id: unknown) => typeof id === 'string' && ID.test(id))
      && new Set(value.items).size === value.items.length && typeof value.description === 'string'
      && typeof value.stamp === 'string' && ID.test(value.stamp) && (value.post === null || typeof value.post === 'string' && ID.test(value.post)))
      return { items: value.items, description: value.description, stamp: value.stamp, post: value.post }
  } catch { /* no draft */ }
  return null
}
/** The stored draft, read three ways apart: `absent` (nothing kept: an empty draft), `unreadable` (the read throws) and
 *  `damaged` (it does not parse). Neither of the last two is an empty draft: nothing is removed, written over or sent. */
export type Stored = { state: 'absent' } | { state: 'unreadable' } | { state: 'damaged' } | { state: 'read'; draft: Draft }
export function readStored(read: () => string | null): Stored {
  let raw: string | null
  try { raw = read() } catch { return { state: 'unreadable' } }
  if (raw === null) return { state: 'absent' }
  const draft = readDraft(raw)
  return draft ? { state: 'read', draft } : { state: 'damaged' }
}
/** The request of a draft: its key is the draft's stamp, so the same draft sent again (a second tap, a reload after a
 *  lost answer) is answered the post the server already made. Only blanks is no description. */
export const requestOf = (stamp: string, page: string, description: string, items: Item[]): { key: string; body: PostBody } =>
  ({ key: stamp, body: { page_id: page, description: description.trim() ? description : '', items } })
/** Before a request leaves, the live draft is written and read back: nothing is sent unless the device keeps it. One tab
 *  at a time holds the page, so the stored draft is this tab's own. */
export function keptForSending(storage: { get(): string | null; set(value: string): void }, live: Draft): 'kept' | 'unkept' {
  try {
    storage.set(JSON.stringify(live))
    const saved = readDraft(storage.get())
    return saved && saved.stamp === live.stamp && saved.description === live.description && saved.post === live.post
      && saved.items.length === live.items.length && saved.items.every((id, index) => id === live.items[index]) ? 'kept' : 'unkept'
  } catch { return 'unkept' }
}
/** The one handler of every answer about the draft's post (the request's answer, the polling, the list, the stop, the
 *  owner's word), `sent` being the stamp it was made from. `draft` null: cleared; `write`: the result is to be stored.
 *  A draft edited since (another stamp, kept on the device or not) is left as it is. Else: in flight or unknown, the
 *  post is the draft's, followed and its stamp kept; failed, the draft stays and its stamp is made anew, so that
 *  « Publier » is a new try; published, it is cleared. */
export function answered(live: Draft, post: Post, sent: string): { draft: Draft | null; write: boolean } {
  if (live.stamp !== sent) return { draft: live, write: false }
  if (post.status === 'published') return { draft: null, write: true }
  if (post.status === 'failed') return { draft: { ...live, stamp: crypto.randomUUID(), post: null }, write: true }
  return live.post === post.id ? { draft: live, write: false } : { draft: { ...live, post: post.id }, write: true }
}
/** An answer of the server about the request (a refusal: no row was written, the draft and its stamp stay), as opposed
 *  to no answer (network, timeout, a server fault), when the same request is sent again. */
export function refusalOf(reason: unknown) {
  if (!(reason instanceof ApiError)) return null
  return reason.code === 'export_missing' || reason.status >= 400 && reason.status < 500 && reason.code !== 'invalid_response' ? reason : null
}

// ── « Publier… » ────────────────────────────────────────────────────────────────────────────────────────────
export type Action = 'account' | 'terms' | 'checking' | 'running' | 'stale' | 'empty' | 'over' | 'pending' | 'description' | 'ready'
/** The description's fault: a caption's rules (D-SHARE-003), an empty one allowed. */
export function descriptionFault(text: string) { const fault = captionFault(text); return fault === 'blank' ? null : fault }
export const codePoints = (text: string) => [...text].length
/** What « Publier… » does, in this order: no Page or one to reconnect (« Mon compte »); the conditions not accepted
 *  (`accepted` false; null while unread: the server decides); a request whose answer is awaited; a post in flight (one of
 *  the list's, or the latest post of a chosen poster: a reload of the page for one poster during its uploads knows it
 *  with no key of its own); the posters' marks not read again since a post settled; nothing chosen; more than the shop's
 *  limit; a poster held by an unknown post (`pending`); the description refused; else the confirmation. */
export function publishAction(state: { page: Page; accepted: boolean | null; checking: boolean; running: boolean; stale: boolean; chosen: Candidate[]; limit: number | null; description: string }): Action {
  if (!state.page || state.page.state !== 'connected') return 'account'
  if (state.accepted === false) return 'terms'
  if (state.checking) return 'checking'
  if (state.running || state.chosen.some(item => item.last && inFlight(item.last))) return 'running'
  if (state.stale) return 'stale'
  if (!state.chosen.length) return 'empty'
  if (state.limit !== null && state.chosen.length > state.limit) return 'over'
  if (state.chosen.some(item => item.pending)) return 'pending'
  return descriptionFault(state.description) ? 'description' : 'ready'
}
export const LOST = 'La réponse n’est pas arrivée. Je vérifie…'
const why: Record<Exclude<Action, 'ready' | 'account' | 'over' | 'description'>, string> = {
  terms: 'Acceptez d’abord les conditions d’utilisation.',
  checking: LOST,
  running: 'Une publication est en cours : attendez son résultat.',
  stale: 'Vos affiches n’ont pas pu être relues : touchez « Réessayer ».',
  empty: 'Choisissez au moins une affiche.',
  pending: 'Une de ces affiches attend votre réponse sur une publication au résultat inconnu : répondez plus bas.',
}
const FAULTS = { too_long: 'La description dépasse 2 000 caractères.', bad_character: 'La description contient un caractère de contrôle refusé.' }
const over = (limit: number | null) => `Retirez des affiches : ${limit} images au plus par publication.`
/** Why « Publier… » is off, beside it; '' when it is on (or leads to « Mon compte »). */
export function whyNot(action: Action, limit: number | null, description: string) {
  if (action === 'ready' || action === 'account') return ''
  if (action === 'over') return over(limit)
  if (action === 'description') return FAULTS[descriptionFault(description) as keyof typeof FAULTS]
  return why[action]
}
export const faultLine = (description: string) => { const fault = descriptionFault(description); return fault ? FAULTS[fault] : '' }
/** Over the grid: at the limit exactly, why it adds no more; over it, what to take out. Never a count it does not hold. */
export function limitLine(count: number, limit: number | null) {
  if (limit === null || count < limit) return ''
  return count === limit ? `Votre publication compte ${limit} images, le plus permis : retirez-en une pour en ajouter une autre.` : over(limit)
}

// ── what is said ────────────────────────────────────────────────────────────────────────────────────────────
const plural = (count: number, one: string, many: string) => count > 1 ? many : one
/** The sheet names what is already on the Page: the chosen posters that have a `published_at`, the latest of their
 *  dates said by `day`; its button then reads « Publier à nouveau ». Publishing again is always the owner's stated choice. */
export function alreadyLine(chosen: { published_at: string | null }[], day: (stamp: string) => string) {
  const dates = chosen.map(item => item.published_at).filter((stamp): stamp is string => !!stamp)
  if (!dates.length) return { line: '', label: 'Publier' }
  const latest = dates.reduce((last, stamp) => Date.parse(stamp) > Date.parse(last) ? stamp : last)
  const line = chosen.length === 1 ? `Cette affiche est déjà sur votre Page depuis le ${day(latest)}. Publier à nouveau ?`
    : dates.length === 1 ? `Une de ces affiches est déjà sur votre Page (le ${day(latest)}). Publier à nouveau ?`
      : `${dates.length} de ces affiches sont déjà sur votre Page (la dernière le ${day(latest)}). Publier à nouveau ?`
  return { line, label: 'Publier à nouveau' }
}
const GONE: Record<Reason, string> = {
  other_format: 'elle a été vérifiée dans un autre format', changed: 'elle a été modifiée depuis sa vérification',
  unconfirmed: 'elle n’a jamais été vérifiée', gone: 'elle n’est plus dans vos affiches',
}
/** A poster of the draft that can no longer go, taken out at the opening: named by its place in the draft. */
export const takenOut = (position: number, reason: Reason) => `L’affiche ${position + 1} de votre publication a été retirée : ${GONE[reason]}.`
const ALONE: Record<Reason, string> = {
  other_format: 'Pour publier sur votre Page, vérifiez cette affiche au format Publication.',
  changed: 'Cette affiche a été modifiée depuis sa vérification : vérifiez-la à nouveau pour la publier.',
  unconfirmed: 'Cette affiche n’a jamais été vérifiée : vérifiez-la pour la publier.',
  gone: 'Cette affiche n’est plus dans vos affiches.',
}
/** The page for one poster that cannot go: why, and whether the way to the poster is offered. */
export const aloneLine = (reason: Reason) => ({ text: ALONE[reason], open: reason !== 'gone' })
export const imageCount = (count: number) => `${count} ${plural(count, 'image', 'images')}`
export const posterCount = (count: number) => `${count} ${plural(count, 'affiche', 'affiches')}`
/** A post's line: its state in the server's words, the link it carries (Facebook's own only), and its controls: the
 *  owner's three for an unknown outcome, « Arrêter l’envoi » while the images are sent and no stop was asked. */
export function postLine(post: Post) {
  const page = `https://www.facebook.com/${post.page_id}`
  const link = post.status === 'unknown' ? { href: page, label: 'Ouvrir ma Page' }
    : post.status === 'published' && post.link?.startsWith('https://www.facebook.com/') ? { href: post.link, label: post.said_by_owner ? 'Ouvrir la Page' : 'Voir la publication' } : null
  return { state: post.message_fr, link, count: imageCount(post.count), ask: post.status === 'unknown',
    stop: post.status === 'uploading' && !post.stop_asked, stopping: post.status === 'uploading' && post.stop_asked }
}
