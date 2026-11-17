// The operator's page: what it reads from the address and what it says of a refusal (D-ADMIN-005). English, for the
// operator (owner decision 10).
import { AdminError } from './adminApi'

export type Route = { view: 'shops' } | { view: 'shop'; id: number } | { view: 'money' }
/** The view of an address's hash: `#/shops/<id>` is one shop, `#/money` the payments, anything else the shop list. */
export function route(hash: string): Route {
  if (hash === '#/money') return { view: 'money' }
  const found = /^#\/shops\/([1-9][0-9]{0,8})$/.exec(hash)
  return found ? { view: 'shop', id: Number(found[1]) } : { view: 'shops' }
}

export const NOT_SET = 'No operator password is set. On the server run: python -m affiche.shops operator-password (deploy/README.md, « Operator dashboard »).'
const SENTENCES: Record<string, string> = {
  wrong_credentials: 'Wrong password.',
  rate_limited: 'Too many wrong passwords from this address. Wait 15 minutes, then try again.',
  operator_not_set: NOT_SET,
  unauthenticated: 'Your session has ended. Sign in again.',
  bundle_outdated: 'This page is out of date: nothing was saved. Reload it, then try again.',
  forbidden_origin: 'The server refused a request from this page’s address.',
  not_found: 'This shop does not exist.',
  network: 'No answer from the server: the connection was lost.',
  timeout: 'No answer from the server within 30 seconds.',
  invalid_response: 'The server’s answer could not be read.',
  storage_unavailable: 'The server’s storage is busy or unavailable.',
}
/** What a refusal says: the page's own sentence for the codes it knows, else the server's `detail` (the operator's
 *  refusals, in English), else its French sentence, else the code. Server text is shown as text, never as HTML. */
export function sentence(error: AdminError): string {
  if (error.code === 'validation_error')
    return error.field?.endsWith('name') ? 'The name was not accepted: 1 to 160 characters.' : `This value was not accepted: ${error.field ?? 'unknown field'}.`
  return SENTENCES[error.code] ?? (error.status >= 500 ? `The server failed (error ${error.status}).` : error.message || `Refused (${error.code}).`)
}
/** No definite answer: the server may have done it (a 5xx proves no rollback, D-ADMIN-005). */
export const uncertain = (error: AdminError) => error.status === 0 || error.status >= 500 || error.code === 'invalid_response'

export const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`
/** Micro-USD as the operator reads dollars, to the cent (`round` picks the direction, as the command line does). */
export const dollars = (micros: number, round = Math.round) => `$${(round(micros / 1e4) / 100).toFixed(2)}`
/** Thousands grouped by a no-break space (« 20 000 »), for display only: what is sent stays the integer. */
export const grouped = (n: number) => (n < 0 ? '−' : '') + String(Math.abs(n)).replace(/\B(?=(\d{3})+$)/g, '\u00a0')
export const signed = (n: number) => (n > 0 ? '+' : '') + grouped(n)
export const ariary = (n: number) => `${grouped(n)}\u00a0Ar`
const credits = (n: number, kind = '') => `${grouped(n)} ${kind}${n === 1 ? 'credit' : 'credits'}`
/** A stored UTC time as the operator reads it. */
export const when = (at: string) => `${at.slice(0, 10)} ${at.slice(11, 16)} UTC`
/** The current UTC month, as whole days (the payments' default period). */
export function month(now = new Date()) {
  const day = (date: Date) => date.toISOString().slice(0, 10)
  return { start: day(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1))),
           end: day(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0))) }
}

// ---- Money requests (D-ADMIN-005, R-ADMIN-003) ----

/** credits.MOST: the most one line carries, in credits or in ariary. */
export const MOST = 1_000_000_000
/** A whole number from 1 to MOST, typed as digits only: the fields' native `pattern`, so the browser bounds it. */
export const WHOLE = '[1-9][0-9]{0,8}|1000000000'
export function whole(typed: string): number {
  if (!new RegExp(`^(?:${WHOLE})$`).test(typed)) throw new RangeError(`not a whole number from 1 to ${MOST}: ${typed}`)
  return Number(typed)
}

// Python's str.split() whitespace, which the server's credits._key collapses (JavaScript's \s differs by a few).
const SPACE = /[\t\n\v\f\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/
const ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  // the shops' password alphabet (shops.py ALPHABET), 31 characters
type Random = (bytes: Uint8Array) => Uint8Array
const random: Random = bytes => crypto.getRandomValues(bytes)
/** A reference made once when a form opens: the UTC second, then six random characters, so that two made in one
 *  second differ (about 887 million suffixes). 30 characters for `offered`, 33 for `correction`. */
export function reference(kind: 'offered' | 'correction', now = new Date(), source = random): string {
  let suffix = ''
  while (suffix.length < 6)  // bytes from 248 up are dropped: 248 = 8 × 31, so every character is equally likely
    for (const byte of source(new Uint8Array(6))) if (byte < 248 && suffix.length < 6) suffix += ALPHABET[byte % 31]
  return `${kind}-${now.toISOString().slice(0, 19).replace(/[-:]/g, '').replace('T', '-')}-${suffix}`
}
/** One per job, as `job_id UNIQUE` is: the whole job id (42 characters for a UUID). */
export const repayment = (job: string) => `repay-${job}`
/** The offered grant that serves the right shop when a move is refused: deterministic, so that the same payment's
 *  concession made twice is refused by its reference, and never above 100 characters (counted as Python counts). */
export function concession(ref: string): string {
  // Spaces collapsed first, as the server's key does: one payment's spellings make one concession.
  return [...ref.split(SPACE).filter(Boolean).join(' ')].slice(0, 94).join('') + '-geste'
}
/** A reference as the server compares it: spaces collapsed, case folded. Exact for ASCII only: beyond it, toLowerCase
 *  and Python's casefold differ both ways (« ß », and letters one Unicode version folds and the other does not). */
export const refKey = (ref: string) => ref.split(SPACE).filter(Boolean).join(' ').toLowerCase()
const ASCII = /^[\x00-\x7f]*$/
/** Whether two references are surely one to the server: the same text, or the same key when both are ASCII. A miss
 *  leaves the request kept, and « Send again » asks the server; a false match would forget an unanswered request. */
export const sameRef = (a: string, b: string) => a === b || ASCII.test(a) && ASCII.test(b) && refKey(a) === refKey(b)

export interface GrantBody { credits: number; origin: 'offered' | 'bought'; ref: string; note: string | null; amount_ar: number | null; method: string | null }
export interface CorrectionBody { credits: number; ref: string; note: string; amount_ar: number | null; job_id: string | null }
export interface MoveBody { ref: string; from_shop: number; to_shop: number; note: string }
export type Form = 'grant' | 'correction' | 'move'
/** A confirmed money request, frozen: what the confirmation showed is what is sent, and sent again, unchanged. The
 *  shape kept in localStorage under PENDING + its shop's id (D-ADMIN-005): a shop id, a path, the reference and the figures. */
export type Kept = { shop: number; path: string; at: string } &
  ({ form: 'grant'; body: GrantBody } | { form: 'correction'; body: CorrectionBody } | { form: 'move'; body: MoveBody })

const path = (form: Form, shop: number) => form === 'move' ? '/api/admin/payments/move' : `/api/admin/shops/${shop}/${form}s`
const frozen = <T extends Kept>(request: T): T => { Object.freeze(request.body); return Object.freeze(request) }

export interface GrantDraft { credits: string; origin: 'offered' | 'bought'; amount: string; method: string; offeredRef: string; paymentRef: string; note: string }
export interface CorrectionDraft { mode: 'credits' | 'amount' | 'repay'; sign: 1 | -1; credits: string; amount: string; madeRef: string; paymentRef: string; job: string; note: string }
export interface MoveDraft { ref: string; to: string; note: string }
export const newGrant = (): GrantDraft => ({ credits: '', origin: 'bought', amount: '', method: '', offeredRef: reference('offered'), paymentRef: '', note: '' })
export const newCorrection = (): CorrectionDraft => ({ mode: 'credits', sign: 1, credits: '', amount: '', madeRef: reference('correction'), paymentRef: '', job: '', note: '' })
export const newMove = (): MoveDraft => ({ ref: '', to: '', note: '' })

/** The request a form's draft makes, at the moment it is confirmed. A bought grant's method is lowercased here, as the
 *  server stores it, so that the confirmation shows what is written. */
export function grantRequest(shop: number, draft: GrantDraft, at = new Date().toISOString()): Kept {
  const bought = draft.origin === 'bought'
  return frozen({ shop, form: 'grant', path: path('grant', shop), at, body: {
    credits: whole(draft.credits), origin: draft.origin, ref: (bought ? draft.paymentRef : draft.offeredRef).trim(),
    note: draft.note.trim() || null, amount_ar: bought ? whole(draft.amount) : null,
    method: bought ? draft.method.trim().toLowerCase() : null } })
}
export function correctionRequest(shop: number, draft: CorrectionDraft, at = new Date().toISOString()): Kept {
  const note = draft.note.trim()
  const body: CorrectionBody = draft.mode === 'repay' ? { credits: 1, ref: repayment(draft.job), note, amount_ar: null, job_id: draft.job }
    : draft.mode === 'amount' ? { credits: 0, ref: draft.paymentRef.trim(), note, amount_ar: draft.sign * whole(draft.amount), job_id: null }
    : { credits: draft.sign * whole(draft.credits), ref: draft.madeRef.trim(), note, amount_ar: null, job_id: null }
  return frozen({ shop, form: 'correction', path: path('correction', shop), at, body })
}
export function moveRequest(from: number, draft: MoveDraft, at = new Date().toISOString()): Kept {
  return frozen({ shop: from, form: 'move', path: path('move', from), at,
                  body: { ref: draft.ref.trim(), from_shop: from, to_shop: Number(draft.to), note: draft.note.trim() } })
}

export interface Named { identifier: string; name: string | null }
type Find = (id: number) => Named | undefined
const called = (find: Find, id: number) => {
  const shop = find(id)
  return !shop ? `shop ${id}` : shop.name ? `${shop.identifier} (${shop.name})` : shop.identifier
}
/** The plain-English summary of exactly what a request writes: the confirmation, and the kept request's card. */
export function describe(request: Kept, find: Find): string {
  const shop = called(find, request.shop)
  if (request.form === 'grant') {
    const b = request.body
    return b.origin === 'bought'
      ? `Grant ${credits(b.credits, 'bought ')} to ${shop}? ${ariary(b.amount_ar!)} by ${b.method}, reference ${b.ref}.`
      : `Grant ${credits(b.credits, 'offered ')} to ${shop}? Reference ${b.ref}.`
  }
  if (request.form === 'move')
    return `Move the payment ${request.body.ref} from ${shop} to ${called(find, request.body.to_shop)}? Its credits and its ariary leave the first shop for the second.`
  const b = request.body
  if (b.job_id !== null) return `Repay 1 credit to ${shop} for the job ${b.job_id}? Reference ${b.ref}.`
  if (b.amount_ar !== null) return `Change the amount of the payment ${b.ref} in ${shop} by ${signed(b.amount_ar)}\u00a0Ar? No credit changes.`
  return b.credits > 0 ? `Add ${credits(b.credits)} to ${shop}? Reference ${b.ref}.` : `Take back ${credits(-b.credits)} from ${shop}? Reference ${b.ref}.`
}

// ---- Kept until resolved: in memory and in this browser's localStorage, one per shop ----

/** The storage key of a shop's kept request: this prefix, then the shop's id. One key per shop, so that no write
 *  for one shop (in this tab or another) can rewrite or remove another shop's request. */
export const PENDING = 'affiche.admin.pending.'
export const UNSTORED = 'This browser cannot keep an unanswered request across a reload.'
export type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem' | 'key' | 'length'>
export type Pending = Record<number, Kept>
const same = (a: Kept | undefined, b: Kept) => !!a && JSON.stringify(a) === JSON.stringify(b)

/** A shop's kept request in storage. None when the browser refuses storage; an entry of another shape is not ours to send. */
function read(storage: () => Store, shop: number): Kept | undefined {
  let request: Kept
  try { request = JSON.parse(storage().getItem(PENDING + shop) ?? 'null') } catch { return undefined }
  return request && request.shop === shop && ['grant', 'correction', 'move'].includes(request.form)
    && request.path === path(request.form, shop) && typeof request.at === 'string'
    && typeof request.body?.ref === 'string' && (request.form !== 'move' || request.body.from_shop === shop) ? frozen(request) : undefined
}
/** Every kept request in storage. */
export function stored(storage: () => Store): Pending {
  const kept: Pending = {}
  try {
    const store = storage()
    for (let index = 0; index < store.length; index++) {
      const key = store.key(index), shop = key?.startsWith(PENDING) ? Number(key.slice(PENDING.length)) : NaN
      const request = Number.isInteger(shop) ? read(storage, shop) : undefined
      if (request) kept[shop] = request
    }
  } catch { /* storage refused: none */ }
  return kept
}
/** Before a request leaves: kept in memory and in storage. 'busy' when its shop already has another unresolved request
 *  (here or in another tab): nothing new starts for that shop. 'memory' when storage refused it. */
export function keep(memory: Pending, storage: () => Store, request: Kept): 'busy' | 'stored' | 'memory' {
  for (const there of [memory[request.shop], read(storage, request.shop)]) if (there && !same(there, request)) return 'busy'
  memory[request.shop] = request
  try { storage().setItem(PENDING + request.shop, JSON.stringify(request)); return 'stored' } catch { return 'memory' }
}
/** Its definite answer came, or it is discarded: removed, but only if it is still this request (another tab may have
 *  replaced it). A storage that refuses the removal leaves an entry that the next page resolves by its reference. */
export function release(memory: Pending, storage: () => Store, request: Kept) {
  if (same(memory[request.shop], request)) delete memory[request.shop]
  try { if (same(read(storage, request.shop), request)) storage().removeItem(PENDING + request.shop) } catch { /* left for the next page */ }
}

const whole_ = Number.isInteger, balanced = (b: any) => whole_(b?.available) && whole_(b?.pending)
/** Whether a 2xx holds what the page then reads of it. */
export const shaped = (request: Kept, a: any): boolean => request.form === 'move'
  ? Array.isArray(a?.lines) && a.lines.length === 2 && a.lines.every(whole_) && balanced(a.balances?.from) && balanced(a.balances?.to)
  : whole_(a?.line) && balanced(a.balance) && (request.form !== 'grant'
    || ['cap', 'spent', 'left', 'outstanding', 'unit', 'cost', 'images'].every(key => typeof a.headroom?.[key] === 'number'))

export type Outcome = 'done' | 'recorded' | 'refused' | 'resend' | 'uncertain'
/** What an answer says of a money request (D-ADMIN-005): a 2xx, `already_recorded` and any other 4xx are definite;
 *  a 401 and `bundle_outdated` wrote nothing, and the same request is sent again; a 5xx, a network failure, a timeout
 *  or an unreadable answer prove no rollback. */
export function outcome(error?: AdminError): Outcome {
  if (!error) return 'done'
  if (uncertain(error)) return 'uncertain'
  if (error.code === 'already_recorded') return 'recorded'
  if (error.status === 401 || error.code === 'bundle_outdated') return 'resend'
  return 'refused'
}
/** Kept before it leaves, sent, and released only on a definite answer. An answer that never comes (the epoch rule of
 *  adminApi drops those of an earlier session) leaves it kept. */
export async function settle<T>(memory: Pending, storage: () => Store, request: Kept, post: (request: Kept) => Promise<T>, persisted = (_stored: boolean) => {}) {
  const kept = keep(memory, storage, request)
  if (kept === 'busy') return { outcome: 'busy' as const }
  persisted(kept === 'stored')
  let answer: T | undefined, error: AdminError | undefined
  try {
    answer = await post(request)
    if (!shaped(request, answer)) throw new AdminError('invalid_response', '', 200)  // read before it is released
  }
  catch (thrown) { if (!(thrown instanceof AdminError)) throw thrown; error = thrown }
  const said = outcome(error)
  if (said === 'done' || said === 'recorded' || said === 'refused') release(memory, storage, request)
  return { outcome: said, answer, error, stored: kept === 'stored' }
}

// ---- Reading what is already recorded ----

export interface LineItem { type: 'line'; id: number; kind: 'grant' | 'correction'; origin: 'offered' | 'bought' | null; credits: number; amount_ar: number | null; method: string | null; ref: string; job_id: string | null; note: string | null; actor: string; at: string }
export interface JobItem { type: 'job'; id: string; kind: string; status: string; credit: string; creation_id: string; result_ref: string | null; error_code: string | null; at: string; finished_at: string | null; repaid_by: number | null }
export type Item = LineItem | JobItem
/** `already_recorded`'s `existing`: the line that holds the request's place, maybe another shop's. */
export interface Existing { id: number; shop_id: number; identifier: string; kind: string; origin: string | null; credits: number; amount_ar: number | null; method: string | null; ref: string; job_id: string | null; moved_to: { id: number; shop_id: number; identifier: string } | null }

/** The line of the shop's history that holds a kept request's place, as the server would find it: same kind, same
 *  reference key (a repayment: also the same job). Never for a move: the source's correction does not say where the
 *  payment went, so « Send again » asks the server, which says. */
export function inHistory(request: Kept, items: Item[]): LineItem | undefined {
  if (request.form === 'move') return undefined
  const ref = request.body.ref, job = request.form === 'correction' ? request.body.job_id : null
  return items.find((item): item is LineItem => item.type === 'line' && item.kind === request.form
    && (sameRef(item.ref, ref) || job !== null && item.job_id === job))
}
/** Whether the existing line is what the request would have written: shop, kind, origin, credits, ariary, method, job. */
export function matches(request: Kept, line: Existing): boolean {
  if (request.form === 'move' || line.shop_id !== request.shop || line.kind !== request.form) return false
  const b = request.body
  return line.credits === b.credits && line.amount_ar === b.amount_ar
    && (request.form === 'grant' ? line.origin === request.body.origin && line.method === request.body.method : line.job_id === request.body.job_id)
}
/** What `already_recorded` means for this request (D-ADMIN-005, « Reading already_recorded »): `same` only when the
 *  line is what was sent; a way out by a correction or a move, never by another reference. */
export function recorded(request: Kept, line: Existing, find: Find): { text: string; same: boolean } {
  if (request.form === 'move') {
    const to = line.moved_to
    if (to?.shop_id === request.body.to_shop) return { text: `Already moved to ${to.identifier}, line ${to.id}, as sent.`, same: true }
    if (to) return { text: `Already moved to ${to.identifier} (line ${to.id}), not to ${find(request.body.to_shop)?.identifier ?? `shop ${request.body.to_shop}`}. See the payment’s history.`, same: false }
    return { text: line.credits === 0
      ? `The payment was corrected in ${line.identifier} (an amount fix, line ${line.id}), not moved. See the payment’s history.`
      : `The payment was already corrected in ${line.identifier} (line ${line.id}). See the payment’s history.`, same: false }
  }
  if (line.shop_id !== request.shop)
    return { text: `This payment is recorded for ${line.identifier}, line ${line.id}. If it belongs here, move it.`, same: false }
  return matches(request, line)
    ? { text: `Already recorded as line ${line.id}, as sent. Nothing more to do.`, same: true }
    : { text: `Line ${line.id} already holds this reference with other values. To change them, write a correction (or fix the amount). Do not use another reference.`, same: false }
}

export interface Headroom { cap: number; spent: number; left: number; outstanding: number; unit: number; cost: number; images: number; warning: boolean }
/** The cap's headroom after a grant, as the command line prints it: what is left rounded down, the cost up. */
export function headroom(room: Headroom): string {
  const unit = room.images ? `average of the last ${room.images} images` : 'ESTIMATE_SCENE_USD: no image cost yet'
  return `Service cap ${dollars(room.cap)}: ${dollars(room.spent)} spent, ${dollars(room.left, Math.floor)} left. Credits outstanding in all shops: ${grouped(room.outstanding)} × $${(room.unit / 1e6).toFixed(3)} (${unit}) = ${dollars(room.cost, Math.ceil)}.`
}
export const CAP_WARNING = 'Warning: the outstanding credits would cost more than what is left of the cap. Raise SPEND_CAP_USD (deploy/README.md).'
