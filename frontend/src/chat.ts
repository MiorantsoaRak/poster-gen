// Creation by message (D-TEXT-FIRST-003): what the chat keeps in this browser, and its rules that need no screen.
// The conversation is never sent whole to the server: the posters, their versions and states are already there.
import type { Creation, Visual } from './document'
import type { Phase } from './generation'

export type Role = 'product' | 'inspiration'
export type Style = 'clair' | 'couleur' | 'sombre'
export const STYLES: [Style, string][] = [['clair', 'Studio clair'], ['couleur', 'Couleurs du produit'], ['sombre', 'Luxe sombre']]
const isStyle = (value: unknown): value is Style => STYLES.some(([id]) => id === value)
export const PRODUCT_PHOTOS = 3

export interface Picture { asset: string; role: Role; warnings?: string[] }
/** A card is the server's answer to a message (`kind` and its data), or one the chat adds: `result` (a version to check)
 *  and `failed` (a message that could not be read; `retry` is its text). `error` is a paid tap that did not start. */
export interface Card { kind: string; name?: string; price_ar?: number; style?: Style | null; visual_id?: string; code?: string; retry?: string; error?: string; fix?: boolean }
/** `done`: the card has its outcome, or a later card replaced it. A paid card records each step before the next request
 *  leaves: `spent` (tapped), `creation` (its poster's id), `request` (its /scenes request exactly as it left; the card's id
 *  is its key), `job` (the job it made). */
export interface Item { id: string; role: 'owner' | 'app'; text: string; at: number; card?: Card; done?: boolean; pictures?: Picture[]
  spent?: boolean; creation?: string; request?: SceneRequest; job?: string }
export interface SceneRequest { path: string; body: unknown; revision: number }
export interface Draft { name: string | null; price_ar: number | null; style: Style | null; pictures: Picture[] }
/** A paid read on its way: its key and exact body, never changed, so that a retry is the same request for the server. */
export interface Pending { key: string; body: string; text: string }
export interface JobRow { id: string; kind: string; status: string; result_ref: string | null; error_code: string | null }

/** What App.vue hands to the chat: its own refs (unwrapped) and functions, so the routes, guards and retries stay the editor's. */
export interface ChatAdapter {
  state: {
    creation: Creation | null; offer: { title: string; price_ar: number } | undefined; visuals: Visual[]; selected: string | undefined; job: { id: string; kind: string; status: string } | null; phase: Phase | null; offline: boolean
    busy: boolean; look: string; paletteLoading: boolean; cost: string; height: number; error: string; notice: string
    intake: { name: string; price: string; confirmed: boolean }; photos: { asset: string; warnings: string[] }[]; styleReference: string | null
  }
  attach(file: File, role: Role): Promise<{ asset: string; warnings: string[] }>
  /** `sending` runs right before the editor's /scenes request leaves, nothing awaited in between; a throw there stops it. */
  start(card: string, style: Style, smallPhotoAccepted: boolean, sending: (request: SceneRequest) => void): Promise<void>
  job(id: string): Promise<JobRow>
  follow(job: JobRow): void
  review(visual: Visual): void
  download(): void
}

/** The role of the next attached image: the first is the product, the second the inspiration, later ones product photos
 *  up to three. null: nothing more is accepted. */
export function nextRole(pictures: { role: Role }[]): Role | null {
  const products = pictures.filter(picture => picture.role === 'product').length
  if (!products) return 'product'
  if (!pictures.some(picture => picture.role === 'inspiration')) return 'inspiration'
  return products < PRODUCT_PHOTOS ? 'product' : null
}

/** A tap on an unsent image's label swaps its role. There is one inspiration at most: the other unsent one becomes a
 *  product photo. Refused (the same list comes back) when a sent image holds the place, or for a fourth product photo. */
export function swapRole<T extends { id: string; role: Role }>(unsent: T[], id: string, sent: { role: Role }[] = []): T[] {
  const target = unsent.find(picture => picture.id === id)
  if (!target) return unsent
  const to: Role = target.role === 'product' ? 'inspiration' : 'product'
  if (to === 'inspiration' && sent.some(picture => picture.role === 'inspiration')) return unsent
  const next = unsent.map(picture => picture === target ? { ...picture, role: to } : to === 'inspiration' && picture.role === 'inspiration' ? { ...picture, role: 'product' as Role } : picture)
  return [...sent, ...next].filter(picture => picture.role === 'product').length > PRODUCT_PHOTOS ? unsent : next
}

export const CHAT_PREFIX = 'affiche.chat.', UNSENT_KEY = `${CHAT_PREFIX}unsent`, PENDING_KEY = `${CHAT_PREFIX}pending`, THREAD_ITEMS = 100
export const threadKey = (creation?: string | null) => `${CHAT_PREFIX}${creation ?? 'new'}`
export const trim = (items: Item[]) => items.slice(-THREAD_ITEMS)

const picture = (value: any): value is Picture => !!value && typeof value.asset === 'string' && (value.role === 'product' || value.role === 'inspiration')
/** A stored thread. The storage is never trusted: what has the wrong shape is left out. */
export function readThread(raw: string | null): { items: Item[]; draft: Draft; moved?: string } {
  let saved: any
  try { saved = JSON.parse(raw ?? 'null') } catch { saved = null }
  // The new poster's thread went to its poster's key: the other tabs follow this pointer instead of rebuilding anything.
  if (typeof saved?.moved === 'string' && /^[a-f0-9-]{36}$/.test(saved.moved)) return { items: [], draft: { name: null, price_ar: null, style: null, pictures: [] }, moved: saved.moved }
  const items: Item[] = Array.isArray(saved?.items) ? saved.items.filter((item: any) => item && typeof item.id === 'string' && (item.role === 'owner' || item.role === 'app')
    && typeof item.text === 'string' && (item.card === undefined || typeof item.card?.kind === 'string')) : []
  const draft = saved?.draft ?? {}
  return { items: trim(items), draft: { name: typeof draft.name === 'string' && draft.name ? draft.name : null, price_ar: Number.isSafeInteger(draft.price_ar) && draft.price_ar >= 0 ? draft.price_ar : null,
    style: isStyle(draft.style) ? draft.style : null, pictures: Array.isArray(draft.pictures) ? draft.pictures.filter(picture) : [] } }
}
export const movedTo = (creation: string) => JSON.stringify({ moved: creation })
export function readPending(raw: string | null): Pending | null {
  let saved: any
  try { saved = JSON.parse(raw ?? 'null') } catch { return null }
  return typeof saved?.key === 'string' && typeof saved.body === 'string' && typeof saved.text === 'string' ? Object.freeze({ key: saved.key, body: saved.body, text: saved.text }) : null
}
export const newPending = (body: { text: string }): Pending => Object.freeze({ key: crypto.randomUUID(), body: JSON.stringify(body), text: body.text })
/** Whether a refused read is settled. A lost or unreadable answer, and a read still running, are not: the server may
 *  have read the message, so the record is kept and « Réessayer » sends it again as it is. */
export const settled = (code: string) => !['network', 'timeout', 'invalid_response', 'server_error', 'read_running'].includes(code)

/** What a spent card waits for: its job to follow; its kept request, sent again as it is (the server answers what it
 *  stored, or runs it if it never arrived); or nothing, as no request was kept, so nothing paid left. */
export const nextStep = (item: Item): 'follow' | 'replay' | 'new' => item.job ? 'follow' : item.request ? 'replay' : 'new'
/** Whether a refused /scenes request is refused for good: an earlier delivery of the same request, still on its way,
 *  would be refused too, so the card may be retired. A refusal stores nothing under the key, so anything else (busy,
 *  budget, session, 429, 5xx, lost, unlisted) may still let that delivery pass later: the card keeps its request. */
// Not here on purpose: creation_abandoned and format_unavailable can be undone without a new revision (review r5).
const FINAL = ['plan_stale', 'revision_conflict', 'attempt_limit', 'acknowledgement_required', 'validation_error', 'format_locked', 'not_found', 'idempotency_reused']
export const final = (code: string) => FINAL.includes(code) || code.startsWith('title_')
export type Fate = 'running' | 'made' | 'failed'
export const fate = (job: { status: string }): Fate => job.status === 'queued' || job.status === 'running' ? 'running' : job.status === 'succeeded' ? 'made' : 'failed'

/** The last six lines, for the reader (POST /api/reads `history`). */
export const lines = (items: Item[]) => items.filter(item => item.text.trim()).slice(-6).map(item => ({ role: item.role, text: item.text.trim().slice(0, 500) }))
/** The draft as the reader takes it: only uploaded pictures count. */
export const wireDraft = (draft: Draft) => ({ name: draft.name, price_ar: draft.price_ar, style: draft.style,
  product_photos: Math.min(PRODUCT_PHOTOS, draft.pictures.filter(item => item.role === 'product').length), inspiration: draft.pictures.some(item => item.role === 'inspiration') })
export const complete = (draft: Draft) => !!draft.name && draft.price_ar !== null && draft.pictures.some(item => item.role === 'product')

/** One paid tap, never two: true only for the first tap on a card. The caller saves the thread before the request leaves. */
export function spend(items: Item[], id: string) {
  const item = items.find(entry => entry.id === id)
  if (!item || item.spent) return false
  return item.spent = true
}
/** A new message or card replaces the open questions and recaps before it: only the latest may be tapped. */
export function supersede(items: Item[]) {
  for (const item of items) if (item.card && item.card.kind !== 'result' && !item.spent) item.done = true
}

export type CardButton = 'photo' | 'create' | 'retry' | 'resume' | 'fix' | 'resend' | 'review' | 'download'
/** The one action a card shows; null when it only shows its text or its outcome. `version` is the state of a result's
 *  version; it is downloaded only while it is the one `selected` in the document (the export renders that one). */
export function cardButton(item: Item, version?: Visual['status'], selected?: string): CardButton | null {
  const card = item.card
  if (!card) return null
  if (card.kind === 'result') return version === 'pending_review' ? 'review' : version === 'approved' && card.visual_id === selected ? 'download' : null
  if (card.fix) return 'fix'  // refused by a rule that a retry cannot change: corrected in the editor
  if (item.done) return null
  // A spent card whose request may have left without an answer: that same request again, never by itself. « Réessayer »
  // after a refusal seen here, « Reprendre » in a later view (a reload, a return from « Pas à pas »).
  if (card.kind === 'recap') return !item.spent ? 'create' : item.request && !item.job ? card.error ? 'retry' : 'resume' : null
  if (card.kind === 'ask_photo') return 'photo'
  return card.kind === 'failed' && card.retry ? 'resend' : null
}
