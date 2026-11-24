import { computed, ref } from 'vue'

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public currentRevision?: number, public field?: string) { super(message) }
}

// The server's clock minus this device's, from the last response's Date header (whole seconds); null until one is read.
export let clockSkew: number | null = null

// The top progress line (D-POSTER-EDITOR-007 point 3): on once requests the owner waits for have been in flight for
// 300 ms, off when none has been for a frame (sequential requests of one action leave gaps of a few microtasks).
// Background requests (job polls, autosave) pass quiet and never show it.
export const progress = ref(false)
let inFlight = 0, showing: ReturnType<typeof setTimeout> | undefined, hiding: ReturnType<typeof setTimeout> | undefined
function begin() {
  inFlight++; clearTimeout(hiding); hiding = undefined
  if (!showing && !progress.value) showing = setTimeout(() => { showing = undefined; if (inFlight) progress.value = true }, 300)
}
function end() {
  if (--inFlight) return
  hiding = setTimeout(() => { hiding = undefined; clearTimeout(showing); showing = undefined; progress.value = false }, 16)
}

// Sent with every request (X-Affiche-Bundle); the server refuses a state-changing request from a lower one with
// `bundle_outdated` (backend api.py BUNDLE). Raise both together when a change makes an older open tab unsafe: one that
// would pay beside a card it does not know, or carry out a card without what it promises (ADR-103), or sign in without
// the shop's identifier (D-MULTI-SHOP-002).
export const BUNDLE = 3

// ── the identity gate (D-MULTI-SHOP-007) ─────────────────────────────────────────────────────────────────
// `bound` is the tab's shop for the page's whole life: a shop id; null, bound to nobody (signed out on this page); undefined
// before the first session answer. Kept in sessionStorage (per tab, across reloads and Back); in memory where it is refused,
// and a reload is then a new page life.
const BOUND_KEY = 'affiche.bound'
/** The device key written at every sign-in and sign-out: the other tabs ask the session again (`storage` event). */
export const IDENTITY_KEY = 'affiche.identity'
export const bound = ref<number | null | undefined>(readBinding())
function readBinding() {
  try {
    const raw = sessionStorage.getItem(BOUND_KEY), shop = Number(raw)
    return raw === 'none' ? null : raw !== null && Number.isSafeInteger(shop) && shop > 0 ? shop : undefined
  } catch { return undefined }
}
// `generation` changes with the binding: an answer counts only under the binding its request left with.
let opened = false, generation = 0
export function bind(shop: number | null) {
  bound.value = shop; opened = false; generation++
  try { sessionStorage.setItem(BOUND_KEY, shop === null ? 'none' : String(shop)) } catch { /* the binding lives in memory for this page */ }
}
/** The gate opened on the bound shop: its storage keys may be built from now on. */
export function open() { opened = typeof bound.value === 'number' }
/** Every key of what the application keeps for a shop on this device. It throws until the gate has opened on the bound
 *  shop: a key built before the session answer would be a guess, and finds nothing rather than another shop's data. */
export function shopKey(name: string) {
  if (!opened || typeof bound.value !== 'number') throw new Error('No shop is open on this page.')
  return `affiche.shop${bound.value}.${name}`
}
/** Every write of a shop's key goes through here (review r2 P2-4): refused unless the key is the open shop's at the
 *  moment of writing, so that work begun before a change of binding (a late answer, a timer) writes nothing after it,
 *  whenever its key was built; refused too from another tab's identity event until the shop is confirmed again
 *  (`changedElsewhere`). Reads are plain: they only ever reach the page's own memory. */
export const shopStorage = {
  getItem: (key: string) => localStorage.getItem(key),
  setItem: (key: string, value: string) => localStorage.setItem(current(key), value),
  removeItem: (key: string) => localStorage.removeItem(current(key)),
}
function current(key: string) {
  if (!opened || typeof bound.value !== 'number' || confirmAfter !== null || !key.startsWith(`affiche.shop${bound.value}.`)) throw new Error('No shop is open on this page.')
  return key
}
/** The last session answer as the gate reads it: a shop, nobody (null, or a 401), another shop not named (a 409). */
export type Seen = number | null | 'other'
/** One rule: shop content is shown only while the last answer names the bound shop (a tab without a binding takes its
 *  first answer's); hidden before an answer, while one is awaited, and when it failed; any other identity, or a page
 *  bound to nobody, is the signed-out screen. */
export function gate(binding: number | null | undefined, seen: Seen | undefined, pending: boolean, failed: boolean): 'shown' | 'hidden' | 'out' {
  if (binding === null || seen === null || seen === 'other' || (typeof binding === 'number' && seen !== undefined && seen !== binding)) return 'out'
  return pending || failed || seen === undefined ? 'hidden' : 'shown'
}
// The gate's state: `seen` the last session answer applied, `pending` an answer awaited (the first one, or after the
// page or the tab was left), `failed` why the last one failed, `support` whom to call for a forgotten password.
export interface SessionAnswer { authenticated: boolean; shop_id?: number; support_fr?: string }
export const seen = ref<Seen>(), pending = ref(true), failed = ref<'' | 'down' | 'lost'>(''), support = ref('')
export const state = computed(() => gate(bound.value, seen.value, pending.value, !!failed.value))
export const failureOf = (reason: unknown) => reason instanceof ApiError && [502, 503, 504].includes(reason.status) ? 'down' as const : 'lost' as const
// `asked` numbers each GET /api/session as it leaves, `applied` the latest one applied; `asking` the latest ask().
let asked = 0, applied = 0, asking = 0
/** The one function that applies the gate's rule to what the session says (review r2 P1-1). Every answer of
 *  GET /api/session, whoever asked (the start, a return to the tab, another tab's change, a sign-in, a sign-out, an
 *  image that failed), and every failure of one, comes here through api(). An answer older than one already applied may
 *  close the gate, never open it: a page that saw another identity stays signed out until an explicit sign-in (rule 4),
 *  `failed` is cleared only by the latest answer, and `pending` only by the latest ask(). */
function settle(seq: number, answer?: SessionAnswer, reason?: unknown) {
  const latest = seq > applied
  if (latest) applied = seq
  if (!answer) { if (latest) failed.value = failureOf(reason); return }
  support.value = answer.support_fr ?? ''
  if (latest) failed.value = ''
  if (state.value === 'out' && bound.value !== null) return
  const shop = answer.authenticated && answer.shop_id ? answer.shop_id : null
  if (bound.value === undefined) bind(shop)  // a tab without a binding takes its first answer's (rule 1)
  seen.value = shop
  if (confirmAfter !== null && seq > confirmAfter && shop !== null && shop === bound.value) confirmAfter = null
}
/** Another tab changed this device's identity (its `storage` event on affiche.identity). Its sign-out may have deleted
 *  the shop's keys: from this moment this page writes nothing of its shop (shopStorage) until an answer asked after the
 *  event names its shop (settle), however long that check takes and if it fails (review r5 P2-1). A session that only
 *  ended here (a 401, no other tab) deleted nothing: its writes go on, for the card that says to sign in again. */
let confirmAfter: number | null = null
export function changedElsewhere() { confirmAfter = asked; return ask() }
/** Asks the session again, the shop hidden until it answers (rules 2 and 5). */
export async function ask() {
  const turn = ++asking
  pending.value = true
  try { await api('/api/session', { quiet: true }) } catch { /* settled: the gate shows « Réessayer » */ }
  finally { if (turn === asking) pending.value = false }
}
/** Leaving the page or the tab: the shop is hidden until the session has answered again. */
export function close() { asking++; pending.value = true }
/** Asks the session without hiding the shop, for what may or may not be a change of identity (an image that failed):
 *  its answer is settled like any other. */
export function verify() { void api('/api/session', { quiet: true }).catch(() => undefined /* settled */) }

// What the pilot's phone kept before the shops: it can only be shop 1's. Copied when shop 1 has no such key yet, and
// removed only once its copy is written: an interrupted move resumes at the next start and never overwrites.
const LEGACY = ['affiche.chat.', 'affiche.words.', 'affiche.palette.']
const legacy = (key: string) => key === 'affiche.style' || LEGACY.some(prefix => key.startsWith(prefix))
export function moveLegacy(storage: Storage) {
  const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index)!)
  for (const key of keys.filter(legacy)) {
    const to = `affiche.shop1.${key.slice('affiche.'.length)}`, value = storage.getItem(key)
    try {
      if (value !== null && storage.getItem(to) === null) storage.setItem(to, value)
      storage.removeItem(key)
    } catch { /* kept as it is: the next start tries it again */ }
  }
}

// The shop's requests (every route but /api/session) leave only once the gate has opened on the bound shop, and an
// answer counts only under the binding its request left with: before the session's answer, or after a change of binding,
// it could be another shop's (review r1 P1-1).
const notOpen = () => new ApiError('gate_closed', 'La boutique de cette page n’est pas encore confirmée. Réessayez dans un instant.', 0)
// timeout (ms) is opt-in: the request is given up after it, headers and body together. Without it nothing changes.
// as 'blob': the shop's images (review r2 P1-3), asked like every request of the shop so that identity loss reaches the gate.
type Options = RequestInit & { quiet?: boolean; timeout?: number; as?: 'blob' }
export async function api<T>(path: string, options: Options = {}): Promise<T> {
  if (path !== '/api/session' || (options.method ?? 'GET') !== 'GET') return request<T>(path, options)
  const seq = ++asked
  try { const answer = await request<SessionAnswer>(path, options); settle(seq, answer); return answer as T }
  catch (reason) { settle(seq, undefined, reason); throw reason }
}
async function request<T>(path: string, { quiet = false, timeout, as, ...options }: Options): Promise<T> {
  const session = path === '/api/session', at = generation
  if (!session && !opened) throw notOpen()
  if (!quiet) begin()
  const limit = timeout ? new AbortController() : undefined, timer = limit && setTimeout(() => limit.abort(), timeout)
  const late = () => new ApiError('timeout', 'Le serveur met trop de temps à répondre. Réessayez.', 0)
  // The server answers only while the cookie's session is this page's shop (409 shop_changed otherwise, D-MULTI-SHOP-002).
  const shop: Record<string, string> = typeof bound.value === 'number' ? { 'X-Affiche-Shop': String(bound.value) } : {}
  try {
    let response: Response
    try { response = await fetch(path, { ...options, headers: { ...options.headers as Record<string, string> | undefined, ...shop, 'X-Affiche-Bundle': String(BUNDLE) }, credentials: 'same-origin', ...(limit ? { signal: limit.signal } : {}) }) }
    catch { throw limit?.signal.aborted ? late() : new ApiError('network', 'Connexion interrompue. Vos modifications restent dans cet onglet.', 0) }
    if (!session && at !== generation) throw notOpen()
    // Before the body is read (review r1 P1-4): a 401 needs none, and one that never comes must not keep a shop shown.
    // The sign-in's own 401 is a wrong password, not another identity.
    if (response.status === 401 && !(session && options.method === 'POST')) seen.value = null
    const date = Date.parse(response.headers.get('Date') ?? '')
    if (!Number.isNaN(date)) clockSkew = date - Date.now()
    let data: any
    try { data = response.ok && as === 'blob' ? await response.blob() : await response.json() }
    catch {
      // A 409 is another shop only when its body says so (rule 3 names shop_changed); unreadable, it may be one, so the
      // session is asked again and the shop stays hidden until it answers (rule 2).
      if (response.status === 409) void ask()
      throw limit?.signal.aborted ? late() : new ApiError('invalid_response', 'Réponse du serveur illisible. Réessayez.', response.status)
    }
    if (!session && at !== generation) throw notOpen()
    if (!response.ok) {
      const failure = new ApiError(data.error?.code ?? 'server_error', data.error?.message_fr ?? 'La demande a échoué.', response.status, data.error?.current_revision, data.error?.field)
      if (failure.code === 'shop_changed') seen.value = 'other'
      if (failure.code === 'terms_required') termsAsked.value++
      throw failure
    }
    return data as T
  } finally { clearTimeout(timer); if (!quiet) end() }
}

// ── the conditions of use (D-TERMS-004) ────────────────────────────────────────────────────────────────────
/** Moves at every `terms_required` refusal, whatever request it answers (a Claude button, a chat message, a stale
 *  balance, a retained request the server never took): the page reads the conditions again and shows them. */
export const termsAsked = ref(0)
/** Both requests give up after this (ApiError 'timeout'), body included: « J’accepte » and « Réessayer » are never
 *  left waiting for ever. An expired acceptance may have been made: it is treated as a lost answer. */
export const TERMS_TIMEOUT_MS = 20_000
// Reads are numbered as they leave. One counts only if it is the latest read and left after `voided`, the last read
// started before a confirmed acceptance or a « Plus tard »: a read that may predate the acceptance, or that the owner
// dismissed, never opens or keeps the dialog. A confirmed acceptance itself always counts.
let readTurn = 0, voided = 0
/** Every read on its way stops counting (« Plus tard », a confirmed acceptance, a session gone). */
export function voidReads() { voided = readTurn }
/** GET /api/terms; quiet: no progress line (the page's own read at opening). undefined: overtaken or voided. */
export async function conditions<T>(quiet = false): Promise<T | undefined> {
  const turn = ++readTurn, counts = () => turn === readTurn && turn > voided
  try {
    const answer = await api<T>('/api/terms', { quiet, timeout: TERMS_TIMEOUT_MS })
    return counts() ? answer : undefined
  } catch (reason) {
    if (counts()) throw reason
    return undefined
  }
}
/** POST /api/terms. Its success voids every read started before it. */
export async function acceptConditions<T>(version: string): Promise<T> {
  const answer = await api<T>('/api/terms', { method: 'POST', timeout: TERMS_TIMEOUT_MS,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version }) })
  voidReads()
  return answer
}

// Sign-in sets the cookie and sign-out deletes it; a late answer's Set-Cookie applies even when its body is dropped. So
// both run one at a time on this device, under one lock held until the answer is read and then until the session has
// answered; each request gets 30 s, so that a lost answer cannot hold the lock for ever. Without Web Locks they run
// unserialised: the gate still shows only the bound shop (D-MULTI-SHOP-007 rule 6).
export const IDENTITY_TIMEOUT_MS = 30_000
export function identityChange<T>(change: () => Promise<T>): Promise<T> {
  const run = async () => {
    try { return await change() }
    // The lock is held until the cookie is the server's word; its answer, or its failure, is settled by the gate.
    finally { await api('/api/session', { quiet: true, timeout: IDENTITY_TIMEOUT_MS }).catch(() => undefined /* settled */) }
  }
  return navigator.locks ? navigator.locks.request('affiche-identity', { mode: 'exclusive' }, run) as Promise<T> : run()
}
/** Tells the other tabs of this device that the identity changed (their `storage` event). */
export function announce() {
  try { localStorage.setItem(IDENTITY_KEY, crypto.randomUUID()) } catch { /* they find out at their next request or return */ }
}
/** « Se déconnecter », inside the identity lock (D-MULTI-SHOP-007, ADR-108): the session ends on the server first, the
 *  shop's keys go after (forgetShop). A refusal leaves the page signed in, nothing changed. */
export async function endSession() {
  try { await api('/api/session', { method: 'DELETE', timeout: IDENTITY_TIMEOUT_MS }) }
  catch (reason) {
    // Another tab already changed the shop: this shop's session on the device is gone.
    if (reason instanceof ApiError && reason.code === 'shop_changed') return
    // A lost answer may hide a sign-out the server made (review r2 P1-1): the session's own answer says (the gate has it
    // too). Gone: the sign-out happened.
    if (await gone()) return
    throw reason instanceof ApiError && ['network', 'timeout'].includes(reason.code) ? new Error('Déconnexion impossible : la connexion au serveur est interrompue. Réessayez.') : reason
  }
}

async function gone() {
  try { const answer = await api<SessionAnswer>('/api/session', { quiet: true, timeout: IDENTITY_TIMEOUT_MS }); return !answer.authenticated || answer.shop_id !== bound.value }
  catch { return false }  // not known: the page stays signed in, and the gate shows « Réessayer » (settled)
}
/** « Se déconnecter »'s cleanup (review r2 P2-5, ADR-108): every key of that shop, listed afresh at each try, and for
 *  shop 1 the keys from before the shops that a move could not remove (they would come back at the next start).
 *  false when anything could not be listed or removed: the cleanup is unfinished. */
export function forgetShop(storage: Storage | null, shop: number) {
  try {
    const prefix = `affiche.shop${shop}.`, keys = Array.from({ length: storage!.length }, (_, index) => storage!.key(index)!)
    let whole = true
    for (const key of keys.filter(key => key.startsWith(prefix) || (shop === 1 && legacy(key))))
      try { storage!.removeItem(key) } catch { whole = false }
    return whole
  } catch { return false }
}

// Reading a chat message is a paid call (D-TEXT-FIRST-002), bounded at 30 s here. The caller owns the record (key and
// exact body, chat.ts `Pending`) and sends it again unchanged after a lost answer: the server then answers what it stored.
export const READ_TIMEOUT_MS = 30_000
export const read = <T>(pending: { key: string; body: string }) => api<T>('/api/reads', { method: 'POST', timeout: READ_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: pending.body })

const uncertain = new Map<string, string>()
export async function mutation<T>(path: string, body: unknown, revision?: number, key?: string, method = 'POST', quiet = false, timeout?: number) {
  const signature = JSON.stringify([path, body, revision, method])
  const operation = key ?? uncertain.get(signature) ?? crypto.randomUUID()
  if (!key) uncertain.set(signature, operation)
  let result: T
  try {
    result = await api<T>(path, { method, quiet, timeout, headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operation,
      ...(revision === undefined ? {} : { 'If-Match': `"${revision}"` }) }, body: JSON.stringify(body) })
  } catch (reason) {
    // A refusal (4xx) stored nothing under the key (the server stores only what it accepted): the key is not kept, so
    // that `retained` means a lost answer only.
    if (reason instanceof ApiError && reason.status >= 400 && reason.status < 500) uncertain.delete(signature)
    throw reason
  }
  uncertain.delete(signature)
  return result
}
/** Whether a request to `path` lost its answer and keeps its key: sent again unchanged, the server answers what it stored
 *  (an admitted image, whatever the balance says now: D-BALANCE-006). */
export const retained = (path: string) => [...uncertain.keys()].some(signature => JSON.parse(signature)[0] === path)

// Addresses of images made by the server, with its encoder's version: the browser keeps them a year (ADR-087). Keep in
// step with backend/src/affiche/api.py (THUMBNAIL_VERSION, DISPLAY_VERSION) and rendering.CANVAS_IMAGE_VERSION; an
// address at another version still works, it is only not kept.
const IMAGE_VERSIONS = { prepared: '1', display: '1', thumbnail: '1' }
export const preparedUrl = (url: string) => `${url}?prepared=true&v=${IMAGE_VERSIONS.prepared}`
export const displayUrl = (url: string) => `${url}?prepared=true&display=true&v=${IMAGE_VERSIONS.display}`
export const thumbnailUrl = (url: string) => `${url.replace('/api/assets/', '/api/thumbnails/')}?v=${IMAGE_VERSIONS.thumbnail}`

export async function upload(file: File, role: 'original' | 'logo' | 'style', timeout?: number) {
  const body = new FormData(); body.set('file', file); body.set('role', role)
  return api<{ asset: string; width: number; height: number; warnings: string[] }>('/api/assets', { method: 'POST', body, timeout })
}

// `lines`: the shop's own lines (D-KIT-005), always in the server's answer; optional for a profile built on the page.
export interface Profile { revision: number; name: string | null; contact: string | null; logo_asset: string | null; lines?: string[] }
export interface Terms { version: string; paragraphs_fr: string[]; accepted_at: string | null; changed: boolean }
/** The lines as sent: each field trimmed, the empty ones left out (the server refuses an empty line), in their order. */
export const shopLines = (fields: readonly string[] = []) => fields.map(line => line.trim()).filter(Boolean)
/** `lines` leave only when given: absent, the server keeps the shop's lines (a caller that does not edit them erases none). */
export function writeProfile(profile: Profile, lines?: readonly string[]) {
  return mutation<Profile>('/api/shop-profile', { name: profile.name?.trim() || null, contact: profile.contact?.trim() || null,
    logo_asset: profile.logo_asset, ...(lines && { lines: shopLines(lines) }) }, profile.revision, undefined, 'PUT', false, 20_000)
}

export async function changePassword(current: string, replacement: string) {
  // A password-bearing body must never enter mutation()'s retry signatures.
  const answer = await api<{ changed: boolean }>('/api/session/password', { method: 'POST', timeout: 20_000,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ current_password: current, new_password: replacement }) })
  if (answer?.changed !== true) throw new ApiError('invalid_response', 'Réponse du serveur illisible.', 200)
}
