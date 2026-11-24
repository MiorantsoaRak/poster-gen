// Creation by message (D-TEXT-FIRST-003): what the chat keeps in this browser, and its rules that need no screen.
// The conversation is never sent whole to the server: the posters, their versions and states are already there.
import { shopKey } from './api'
import { FORMAT_NAMES, type Creation, type Format, type Visual } from './document'
import { asksText, type Phase } from './generation'
import { staleWords } from './words'

export type Role = 'product' | 'inspiration'
export type Style = 'clair' | 'couleur' | 'sombre'
export const STYLES: [Style, string][] = [['clair', 'Studio clair'], ['couleur', 'Couleurs du produit'], ['sombre', 'Luxe sombre']]
const isStyle = (value: unknown): value is Style => STYLES.some(([id]) => id === value)
/** The title styles of the kit (D-KIT-012). Not chosen: « Moderne » with a house style, the model's own lettering with a
 *  saved look or a style photo (« Celui du modèle »). */
export type Title = 'moderne' | 'condense' | 'sport' | 'serif'
export const TITLES: [Title, string][] = [['moderne', 'Moderne'], ['condense', 'Gras condensé'], ['sport', 'Italique sport'], ['serif', 'Élégant']]
const isTitle = (value: unknown): value is Title => TITLES.some(([id]) => id === value)
/** A scene model the shop saved (a look, ADR-046): its model image is the chip's picture. */
export interface Look { id: string; name: string; reference_asset: string }
export const PRODUCT_PHOTOS = 3
/** An image's label in the chat; its button says what a touch makes of it (D-KIT-006). */
export const ROLE_NAMES: Record<Role, string> = { product: 'Produit', inspiration: 'Modèle de style' }
export const swapLabel = (role: Role) => `${ROLE_NAMES[role]} : marquer comme ${role === 'product' ? 'modèle de style' : 'produit'}`

export interface Picture { asset: string; role: Role; warnings?: string[] }
/** A card is the server's answer to a message (`kind` and its data), or one the chat adds: `result` (a version to check)
 *  and `failed` (a message that could not be read; `retry` is its text). `error` is a paid tap that did not start.
 *  A `change` card (an existing poster, D-TEXT-FIRST-005) is the server's: `effect` says what it costs, `visual_id` the
 *  version it was read for, `words` the fields to set (`scene`: the four words of the new image, whole; `free`: the
 *  document's fields), `instruction_fr` a refinement. Without `effect` it is a card from before (see `normal`).
 *  A `restyle` card (D-TEXT-FIRST-006) is a whole new image in another `style`, on a fresh plan, with its `words`.
 *  `identity` (a recap): the shop's logo and contact were asked for the first poster (true), or asked to be left
 *  off (false).
 *  `said` is the owner's message, for « Annuler »; `whole`: a whole new scene because the drawn words changed.
 *  Images sent on an existing poster are not read (D-TEXT-FIRST-007): the chat adds a `photo` card with its `pictures`,
 *  which offers the editor's copy of the poster on them. Nothing paid; a kind the bundle from before shows as text.
 *  A `line` card (D-KIT-005) keeps its `lines` in the shop's profile, then redraws the poster with them: a paid card.
 *  The fields after `suggestions` are the seller's kit (D-KIT): a server from before sends none of them; the chat writes
 *  `look` and `title` on a new poster's recap (D-KIT-009). */
export type Effect = 'refine' | 'scene' | 'free'
export interface Words { title?: string; price_ar?: number; brand?: string | null; subtitle?: string | null }
export interface Card { kind: string; name?: string; price_ar?: number; format?: Format; style?: Style | null; identity?: boolean; visual_id?: string; code?: string; retry?: string; error?: string; fix?: boolean
  /** A `line` card whose line the server refused to keep: the shop's lines are corrected in « Mon compte ». */
  account?: boolean
  effect?: Effect; words?: Words; instruction_fr?: string; said?: string; whole?: boolean; pictures?: Picture[]
  /** `ask_photo` only: photos this shop already used for the same product (D-TEXT-FIRST-004). */
  suggestions?: { asset: string; name: string }[]
  /** `ask_price` only: the amounts read in the message, one button each (D-KIT-002). */
  amounts?: number[]
  /** The lines of `text_fr` that say a part of the message the poster will not use (D-KIT-004), each exactly as written
   *  there: the chat draws them apart, under the card. */
  unused_fr?: string[]
  /** A new poster's card: the shop's lines the message asked for, not kept yet (D-KIT-005). A recap: the owner's scene
   *  words, and at the tap the shop's lines drawn (`shop_lines`). A `line` card: the lines it keeps. */
  offer_lines?: string[]; scene_fr?: string; shop_lines?: string[]; lines?: string[]
  /** A new poster's recap: the saved look's name and the title style it uses, the title only when not the default. */
  look?: string; title?: Title }
/** `done`: the card has its outcome, or a later card replaced it. A paid card records each step before the next request
 *  leaves: `spent` (tapped), `creation` (its poster's id), `request` (its /scenes or /refinements request exactly as it
 *  left; the card's id is its key), `job` (the job it made). */
export interface Item { id: string; role: 'owner' | 'app'; text: string; at: number; card?: Card; done?: boolean; pictures?: Picture[]
  spent?: boolean; creation?: string; request?: SceneRequest; job?: string }
export interface SceneRequest { path: string; body: unknown; revision: number }
/** `scene_fr`: the owner's scene words, as the reader kept them (D-KIT-003). `offer_lines`: the shop's lines the
 *  messages asked for, not kept yet; `lines`: the recap's switch, whether the shop's lines are drawn (D-KIT-005). Both
 *  stay on this device: the reader is never sent them. So do the kit row's `look` (a saved look's id, the scene in place
 *  of `style`, which the reader still gets) and `title` (null: the scene's default) (D-KIT-009). */
export interface Draft { name: string | null; price_ar: number | null; style: Style | null; identity: boolean | null; pictures: Picture[]
  scene_fr: string | null; offer_lines: string[]; lines: boolean; look: string | null; title: Title | null }
/** What a new poster's tap adds to the recap's request (D-KIT-004, 005, 009): the owner's scene words; the shop's lines
 *  as the recap shows them, to draw; the new ones among them, to keep in the shop's profile first; the saved look chosen
 *  as the scene (its id); the title style, absent for the scene's default. Each only when set. */
export interface Kit { scene?: string; lines?: string[]; keep?: string[]; look?: string; title?: Title }
/** A paid read on its way: its key and exact body, never changed, so that a retry is the same request for the server. */
export interface Pending { key: string; body: string; text: string }
export interface JobRow { id: string; kind: string; status: string; result_ref: string | null; error_code: string | null; credit?: string | null }

/** What App.vue hands to the chat: its own refs (unwrapped) and functions, so the routes, guards and retries stay the editor's. */
export interface ChatAdapter {
  state: {
    creation: Creation | null; format: Format; productAssets: string[] | undefined; productError: string; offer: { title: string; price_ar: number } | undefined; visuals: Visual[]; selected: string | undefined; job: { id: string; kind: string; status: string } | null; phase: Phase | null; offline: boolean
    /** The selected version's stored title and price, each only when it differs from the document's. */
    stale: Stale
    /** What a new image costs, as the editor's dialog says it (generation.ts credit); `stop`: no new paid tap; `terms`:
     *  stopped by the conditions of use, which the card offers to read. */
    busy: boolean; look: string; paletteLoading: boolean; credit: { stop: boolean; text: string; terms?: boolean }; height: number; error: string; notice: string
    intake: { name: string; price: string; confirmed: boolean }; photos: { asset: string; warnings: string[] }[]; styleReference: string | null
    /** What the shop's profile holds; `ticked`: the form of « Pas à pas » has the logo or the contact ticked. */
    shop: Shop
    /** Whether the texts are drawn in the image (`headline.on`; a poster not made yet draws them): the shop's lines are
     *  drawn only then. Not given: drawn. */
    drawn?: boolean
    /** The seller's kit (D-KIT-009), none given: the three house styles only. `looks`: the shop's saved looks (removed
     *  ones left out); `recent`: ids of house styles and looks, the most recently used first; `kit`: the last choices on
     *  this device, a new poster's first ones (`look` an id, `style` a house style, `title` a title style). */
    looks?: Look[]; recent?: string[]; kit?: { look?: string; style?: string; title?: string }
  }
  reloadProduct(): Promise<void>
  attach(file: File, role: Role): Promise<{ asset: string; warnings: string[] }>
  /** `sending` runs right before the editor's paid request leaves, nothing awaited in between; a throw there stops it.
   *  `identity`: a new poster is made with the logo and the contact that the shop's profile holds (true), or without
   *  them (false); not given, the form's own ticks decide, as before. `kit`: a new poster's scene words, shop lines, saved
   *  look and title style, given at every tap until the poster has a version and applied each time (none given: none of
   *  them is sent); `style` stays a house style, the one the reader was told.
   *  `look`: the name of the style model made from the recap's style photo, which the thread then names (D-KIT-006). */
  start(card: string, style: Style, smallPhotoAccepted: boolean, sending: (request: SceneRequest) => void, identity?: boolean, kit?: Kit): Promise<void | { look?: string }>
  /** `visual` becomes the poster's version, then the editor's « Ajuster la scène » on it.
   *  `owned` (here and below) runs right before the editor changes anything; a throw there stops it. */
  change(card: string, visual: string, instruction: string, owned: () => void, sending: (request: SceneRequest) => void): Promise<void>
  /** `visual` becomes the poster's version, the card's words are set in the editor, then its « Nouvelle version »:
   *  look, coloured word and contact stay the editor's. With `style`, a fresh plan in that style: the version's model
   *  image and kept adjustments are not carried. With `lines` (a `line` card), these are kept in the shop's profile
   *  first, then the new image draws the shop's lines. */
  revise(card: string, visual: string, words: Words, smallPhotoAccepted: boolean, owned: () => void, sending: (request: SceneRequest) => void, style?: Style, lines?: string[]): Promise<void>
  /** The editor's copy of the open poster on the same product with other photos, opened in « Pas à pas » without a
   *  version (D-TEXT-FIRST-007). Nothing paid. `owned` runs before each request; `made` once the copy exists. */
  remake(photos: string[], owned: () => void, made: () => void): Promise<void>
  /** `visual` becomes the poster's version and the document's words are set, saved. Nothing paid. */
  words(visual: string, values: Words, owned: () => void): Promise<void>
  /** The editor's choice of a version for the poster, saved. */
  select(visual: string, owned: () => void): Promise<void>
  /** The editor's unsaved edits, saved: a change is read against the stored poster. */
  saved(): Promise<void>
  /** The poster's jobs, for the version limit. */
  attempts(): Promise<{ kind: string; status: string }[]>
  job(id: string): Promise<JobRow>
  follow(job: JobRow): void
  /** Reads the shop's credits again (a 402 says the balance shown was stale). */
  recount(): void
  review(visual: Visual): void
  /** « Télécharger ou partager »: the poster's current confirmation; a file to check is rendered only without one. */
  download(): void
  /** « Lire les conditions »: the conditions of use read again and shown, unless the shop has accepted them meanwhile
   *  (then the credits are read again, and the card offers its tap). Nothing paid. */
  conditions(): void
  /** Set by the chat: whether a paid card of its thread waits for its answer (« Se déconnecter » says so before it signs
   *  out, ADR-108); undefined when this tab does not hold the chat (then the stored threads say, `waitingIn`). */
  waiting?: () => boolean | undefined
  hasUnsentPhotos?: () => boolean
  discardUnsentPhotos?: () => void
  /** Set by the chat: puts the cursor in « Votre message » (« Corriger l’affiche » from Message, D-KIT-007). */
  focus?: () => void
  /** The title style the seller chose in the kit row: the next poster's default on this device (D-KIT-012). Only his
   *  choice sets it, never a scene request. */
  keepTitle?: (title: Title | null) => void
}

/** The role of the next attached image: a product photo, up to three (D-KIT-006); the owner makes one the style model
 *  by a touch on its label. Past three product photos an image can only be the style model, so it is taken as one (a
 *  pack of three with a reference poster: the owner, 2026-11-24). null: nothing more is accepted. */
export const nextRole = (pictures: { role: Role }[]): Role | null =>
  pictures.filter(picture => picture.role === 'product').length < PRODUCT_PHOTOS ? 'product'
    : pictures.some(picture => picture.role === 'inspiration') ? null : 'inspiration'

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

// The shop's keys (D-MULTI-SHOP-007): built only once the page's shop is open (api.ts shopKey).
export const THREAD_ITEMS = 100
export const chatPrefix = () => shopKey('chat.'), unsentKey = () => shopKey('chat.unsent'), pendingKey = () => shopKey('chat.pending')
export const threadKey = (creation?: string | null) => `${chatPrefix()}${creation ?? 'new'}`
export const isThread = (key: string) => key.startsWith(chatPrefix()) && key !== unsentKey() && key !== pendingKey()
export const trim = (items: Item[]) => items.slice(-THREAD_ITEMS)

const picture = (value: any): value is Picture => !!value && typeof value.asset === 'string' && (value.role === 'product' || value.role === 'inspiration')
/** A list of words from the server or the storage: its non-empty strings only. */
export const texts = (value: unknown): string[] => Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string' && !!entry.trim()) : []
const emptyDraft = (): Draft => ({ name: null, price_ar: null, style: null, identity: null, pictures: [], scene_fr: null, offer_lines: [], lines: true, look: null, title: null })
/** An open recap follows the editor. A completed recap keeps its own format, including requests sent by older versions. */
export function recapFormat(item: Item, current: Format): string | undefined {
  if (!item.spent && !item.done) return FORMAT_NAMES[current].join(' ')
  const body = item.request?.body
  const format = body && typeof body === 'object' && 'format' in body ? body.format : item.card?.format
  if (typeof format === 'string' && Object.hasOwn(FORMAT_NAMES, format)) return FORMAT_NAMES[format as Format].join(' ')
}
/** Older sent recaps did not snapshot photos. Product inputs are immutable for their poster, and the sent
 *  request records the inspiration actually used. A newer style reference belongs to the current recap only. */
export function picturesOfRecap(item: Item, current: Picture[], creation?: string): Picture[] {
  if (!item.spent && !item.done) return current
  if (item.card?.pictures) return item.card.pictures
  const photos = creation && item.creation === creation ? current.filter(photo => photo.role === 'product') : []
  const body = item.request?.body
  if (body && typeof body === 'object' && 'style_reference_asset' in body && typeof body.style_reference_asset === 'string') {
    photos.push({ asset: body.style_reference_asset, role: 'inspiration' })
  }
  return photos
}
/** A stored thread. The storage is never trusted: what has the wrong shape is left out. */
export function readThread(raw: string | null): { items: Item[]; draft: Draft; moved?: string } {
  let saved: any
  try { saved = JSON.parse(raw ?? 'null') } catch { saved = null }
  // The new poster's thread went to its poster's key: the other tabs follow this pointer instead of rebuilding anything.
  if (typeof saved?.moved === 'string' && /^[a-f0-9-]{36}$/.test(saved.moved)) return { items: [], draft: emptyDraft(), moved: saved.moved }
  const items: Item[] = Array.isArray(saved?.items) ? saved.items.filter((item: any) => item && typeof item.id === 'string' && (item.role === 'owner' || item.role === 'app')
    && typeof item.text === 'string' && (item.card === undefined || typeof item.card?.kind === 'string')).map((item: Item) => item.card ? { ...item, card: normal(item.card) } : item) : []
  const draft = saved?.draft ?? {}
  return { items: trim(items), draft: { ...emptyDraft(), name: typeof draft.name === 'string' && draft.name ? draft.name : null, price_ar: Number.isSafeInteger(draft.price_ar) && draft.price_ar >= 0 ? draft.price_ar : null,
    // A draft saved by a bundle from before `identity` has no such key: the choice the owner made is still on the last
    // recap of the thread (an old tab that was refused rebuilds its recap without it).
    style: isStyle(draft.style) ? draft.style : null, identity: typeof draft.identity === 'boolean' ? draft.identity
      : 'identity' in draft ? null : [...items].reverse().find(item => typeof item.card?.identity === 'boolean')?.card!.identity ?? null, pictures: Array.isArray(draft.pictures) ? draft.pictures.filter(picture) : [],
    // At most the reader's 500 characters: a longer one would make every read of the thread refused.
    ...(typeof draft.scene_fr === 'string' && draft.scene_fr.trim() && draft.scene_fr.length <= 500 ? { scene_fr: draft.scene_fr } : {}), offer_lines: texts(draft.offer_lines), lines: draft.lines !== false,
    look: typeof draft.look === 'string' && draft.look ? draft.look : null, title: isTitle(draft.title) ? draft.title : null } }
}
/** A new poster's first choices (D-KIT-009): the kit's last ones, which the adapter keeps on this device; else `style`,
 *  the editor's look when it is a house style, as before. What is not a style, a title or an id is left out. */
export const kitDraft = (kit: { look?: unknown; style?: unknown; title?: unknown } = {}, style?: string) => ({
  style: isStyle(kit.style) ? kit.style : isStyle(style) ? style : 'clair' as Style,
  look: typeof kit.look === 'string' && kit.look ? kit.look : null, title: isTitle(kit.title) ? kit.title : null })
/** A chip of the kit row: a house style, or a saved look with its model image (`asset`). */
export interface Chip { id: string; name: string; asset?: string }
/** The kit row's scene models (D-KIT-009): the house styles, then the shop's looks, the most recently used first. An id
 *  in `recent` that names no style and no look (removed, from another shop) is skipped. */
export function kitChips(looks: Look[] = [], recent: string[] = []): Chip[] {
  const rank = (chip: Chip) => { const at = recent.indexOf(chip.id); return at < 0 ? recent.length : at }
  return [...STYLES.map(([id, name]) => ({ id, name })), ...looks.map(look => ({ id: look.id, name: look.name, asset: look.reference_asset }))]
    .sort((one, other) => rank(one) - rank(other))  // stable: the rest keep their order
}
/** A title as the kit keeps it: null when it is the scene's default (« Moderne » with a house style; with a model, the
 *  model's own), so that the default follows the scene when it changes (D-KIT-012). */
export const ownTitle = (value: unknown, model: boolean): Title | null => isTitle(value) && (model || value !== 'moderne') ? value : null
/** What the kit row chooses for a new poster: the saved look, only when it is one of the shop's and no style photo
 *  takes the scene (`model`: either is the scene); the title, only when it is not that scene's default. */
export interface Chosen { look?: Look; model: boolean; title?: Title }
export function chosenKit(draft: Pick<Draft, 'look' | 'title'>, looks: Look[] = [], photo = false): Chosen {
  const look = photo ? undefined : looks.find(item => item.id === draft.look), model = photo || !!look
  return { look, model, title: ownTitle(draft.title, model) ?? undefined }
}
/** The kit a new poster's tap passes to the adapter (D-KIT-004, 005, 009), each part only when set. */
export const kitOf = (scene: string | null, { look, title }: Chosen, lines: string[], keep: string[]): Kit => ({
  ...(scene ? { scene } : {}), ...(lines.length ? { lines } : {}), ...(keep.length ? { keep } : {}), ...(look ? { look: look.id } : {}), ...(title ? { title } : {}) })
/** The recap's title line: said only for a title that is not the scene's default (D-KIT-009). */
export const titleLine = (title?: unknown) => { const name = TITLES.find(([id]) => id === title)?.[1]; return name ? `Titre : ${name}` : '' }
export const movedTo = (creation: string) => JSON.stringify({ moved: creation })
export function readPending(raw: string | null): Pending | null {
  let saved: any
  try { saved = JSON.parse(raw ?? 'null') } catch { return null }
  return typeof saved?.key === 'string' && typeof saved.body === 'string' && typeof saved.text === 'string' ? Object.freeze({ key: saved.key, body: saved.body, text: saved.text }) : null
}
export const newPending = (body: { text: string }): Pending => Object.freeze({ key: crypto.randomUUID(), body: JSON.stringify(body), text: body.text })
/** The poster a pending read was sent for, as its body says; null: a new poster's thread. */
export function pendingFor(pending: Pending): string | null {
  try { const id = JSON.parse(pending.body)?.creation_id; return typeof id === 'string' ? id : null } catch { return null }
}
/** Whether a refused read is settled. A lost or unreadable answer, and a read still running, are not: the server may
 *  have read the message, so the record is kept and « Réessayer » sends it again as it is. */
export const settled = (code: string) => !['network', 'timeout', 'invalid_response', 'server_error', 'read_running'].includes(code)

/** What a spent card waits for: its job to follow; its kept request, sent again as it is (the server answers what it
 *  stored, or runs it if it never arrived); or nothing, as no request was kept, so nothing paid left. */
export const nextStep = (item: Item): 'follow' | 'replay' | 'new' => item.job ? 'follow' : item.request ? 'replay' : 'new'
/** Whether a refused /scenes or /refinements request is refused for good: an earlier delivery of the same request, still
 *  on its way, would be refused too, so the card may be retired. A refusal stores nothing under the key, so anything else
 *  (busy, budget, session, 429, 5xx, lost, unlisted) may still let that delivery pass later: the card keeps its request. */
// Not here on purpose: creation_abandoned and format_unavailable can be undone without a new revision (review r5).
// The second line is the refinement route's: each compares the document at the request's own revision with a version or
// a plan that never changes. asset_missing and asset_corrupt (a file on the disk) are not: they can be repaired.
const FINAL = ['plan_stale', 'revision_conflict', 'attempt_limit', 'acknowledgement_required', 'validation_error', 'format_locked', 'not_found', 'idempotency_reused',
  'invalid_headline', 'contact_unsupported',  // the request's own words against the document at its revision
  'adjustments_limit', 'adjustment_refused',  // the chain of the card's version, which a retry cannot change
  'headline_stale', 'base_not_selected', 'scene_format_mismatch', 'logo_disc_uncovered', 'logo_placement_stale', 'invalid_plan', 'invalid_reference', 'unsupported_visual', 'format_missing',
  // The lines the request carries against the shop's profile (D-KIT-005): sent again, the same old lines are refused again,
  // so the card retires and a new one shows the shop's lines as read since. ponytail: lines changed back on another device
  // would let a delivery still on its way pass; the lead's choice (review t-kit-frontend r1, 2), as nothing else frees the card.
  'shop_lines_changed', 'shop_lines_missing']
export const final = (code: string) => FINAL.includes(code) || code.startsWith('title_')
export type Fate = 'running' | 'made' | 'failed'
export const fate = (job: { status: string }): Fate => job.status === 'queued' || job.status === 'running' ? 'running' : job.status === 'succeeded' ? 'made' : 'failed'

/** The last six lines, for the reader (POST /api/reads `history`). */
export const lines = (items: Item[]) => items.filter(item => item.text.trim()).slice(-6).map(item => ({ role: item.role, text: item.text.trim().slice(0, 500) }))
/** The draft as the reader takes it: only uploaded pictures count. `identity` and `scene_fr` only when set: the body is
 *  otherwise the one from before the field. The shop's lines offered and the recap's switch stay on this device. */
export const wireDraft = (draft: Draft) => ({ name: draft.name, price_ar: draft.price_ar, style: draft.style,
  product_photos: Math.min(PRODUCT_PHOTOS, draft.pictures.filter(item => item.role === 'product').length), inspiration: draft.pictures.some(item => item.role === 'inspiration'),
  ...(draft.identity === null ? {} : { identity: draft.identity }), ...(draft.scene_fr ? { scene_fr: draft.scene_fr } : {}) })
/** `lines`: the shop's lines (D-KIT-005); not given, the shop has none the chat knows of. */
export interface Shop { logo: boolean; contact: boolean; ticked: boolean; lines?: string[] }
/** The recap's line for the shop's logo and contact. Asked for: what the profile holds is what the poster gets. Asked
 *  off: said only when the form's ticks would have put one on; otherwise there is nothing to say. */
export const identityLine = (shop: Shop, asked: boolean) => !asked ? shop.ticked ? 'Sans le logo ni le contact de la boutique' : ''
  : shop.logo && shop.contact ? 'Avec le logo et le contact de la boutique'
  : shop.logo ? 'Avec le logo de la boutique' : shop.contact ? 'Avec le contact de la boutique'
  : 'La boutique n’a pas encore de logo ni de contact : ajoutez-les dans Pas à pas.'
/** The recap's scene (D-KIT-004, D-KIT-006): the style's name, or null for the owner's style photo, then his own words.
 *  `open`: the recap waits for its tap, which reads the style photo and keeps it as a model. */
export const sceneLine = (style: string | null, words?: string | null, open = false) =>
  `Scène : ${style ?? `votre modèle de style${open ? ' (lu, puis gardé dans votre kit)' : ''}`}${words ? `, avec vos mots : « ${words} »` : ''}`
/** The offered lines the shop does not hold yet (without case): one kept by a tap whose next step failed is a shop line
 *  now, never offered a second time (D-KIT-005). */
export const newLines = (offered: string[], shop: string[] = []) => offered.filter(line => !shop.some(kept => kept.toLowerCase() === line.toLowerCase()))
/** The recap's shop lines, as they will be drawn (D-KIT-005); nothing to say without any. */
export const linesLine = (lines: string[]) => lines.length ? `Lignes de la boutique : ${lines.join(' · ')}` : ''
/** The amounts of an `ask_price` card, one button each (D-KIT-002): whole and positive, distinct, four at most. */
export const amountsOf = (card: Card) => [...new Set(Array.isArray(card.amounts) ? card.amounts.filter(amount => Number.isSafeInteger(amount) && amount > 0) : [])].slice(0, 4)
/** A card's text without the lines of its unused parts, which the chat draws apart under the card (D-KIT-004). */
export const textOf = (text: string, card?: Card) => {
  const apart = texts(card?.unused_fr)
  return apart.length ? text.split('\n').filter(line => !apart.includes(line)).join('\n') : text
}
export const complete = (draft: Draft) => !!draft.name && draft.price_ar !== null && draft.pictures.some(item => item.role === 'product')

/** One paid tap, never two: true only for the first tap on a card. The caller saves the thread before the request leaves. */
export function spend(items: Item[], id: string) {
  const item = items.find(entry => entry.id === id)
  if (!item || item.spent) return false
  return item.spent = true
}
/** Strict send (ADR-108): a paid request leaves only once the thread holding it and its key (the card's id) is written,
 *  `save` saying so. Not written: the card loses it again and the caller sends nothing, so nothing is paid that this
 *  device could not find again. */
export const UNSTORED = 'Ce navigateur ne peut pas garder la demande : rien n’a été envoyé. Utilisez Pas à pas.'
export function keepRequest(item: Item, request: SceneRequest, save: () => boolean) {
  item.request = request
  if (save()) return
  delete item.request
  throw new Error(UNSTORED)
}
/** Whether a stored thread of the shop holds a paid card that waits for its answer: « Se déconnecter » from a tab that
 *  does not hold the chat, or from the editor (review r5 P2-3). Read only. Storage that cannot be listed or read says
 *  yes: the owner is asked rather than not told. */
export function waitingIn(storage: Storage | null) {
  try {
    return Array.from({ length: storage!.length }, (_, index) => storage!.key(index)!).filter(isThread)
      .some(key => readThread(storage!.getItem(key)).items.some(unresolved))
  } catch { return true }
}
/** Writes a thread, then caps the stored ones (the 30 newest stay): never the thread just written, nor one whose paid
 *  card waits for its answer, whatever their dates say (a device clock set back makes a new thread look old, review r5
 *  P2-2). true only when the thread is stored as written once the cap is done: strict send relies on it (keepRequest). A
 *  refused write throws; a refused cap waits for the next save. */
export function storeThread(device: Storage, write: Pick<Storage, 'setItem' | 'removeItem'>, key: string, value: string) {
  write.setItem(key, value)
  try {
    const others = Array.from({ length: device.length }, (_, index) => device.key(index)!).filter(name => isThread(name) && name !== key)
    const evictable = others.map(name => [name, device.getItem(name)] as [string, string | null]).filter(([, raw]) => !readThread(raw).items.some(unresolved))
    for (const name of staleWords(evictable)) write.removeItem(name)
  } catch { /* the next save tries the cap again */ }
  return device.getItem(key) === value
}
/** A `photo` card's product photos, as assets: distinct, three at most. The storage is never trusted. */
export const productsOf = (card: Card) => [...new Set((Array.isArray(card.pictures) ? card.pictures : []).filter(picture).filter(item => item.role === 'product').map(item => item.asset))].slice(0, PRODUCT_PHOTOS)
/** The cards of an existing poster's change. */
export const changes = (card?: Card) => card?.kind === 'change' || card?.kind === 'restyle' || card?.kind === 'line'
/** The cards that pay for a version. A kind this bundle does not know is text: it pays for nothing. */
export const paid = (card?: Card) => card?.kind === 'recap' || changes(card)
/** A paid card that still waits for its answer (ADR-097): followed, or its request kept for « Reprendre ». A card
 *  retired by a final refusal is `done`, even with its request still attached. */
export const unresolved = (item: Item) => paid(item.card) && !!item.spent && !item.done

/** A card as the chat uses it, at the two places one enters (the stored thread, a read's answer). A card from before
 *  D-TEXT-FIRST-005 had a kind: `change: 'scene'` is a refinement; `change: 'price'` sets the price alone and has no
 *  `effect` (see `effectOf`). `previous` is no longer kept: `state.stale` says what the image still shows. */
export function normal({ change, previous, ...card }: Card & { change?: unknown; previous?: unknown }): Card {
  if (card.kind === 'recap' && card.pictures !== undefined) return { ...card, pictures: Array.isArray(card.pictures) ? card.pictures.filter(picture) : [] }
  if (card.kind !== 'change' || change !== 'scene' && change !== 'price') return card
  if (change === 'scene') return { ...card, effect: 'refine' }
  const { price_ar, ...rest } = card
  return { ...rest, words: { price_ar } }
}
/** What a change card costs: the server's `effect`. A card from before has none and follows the rule it was made
 *  under, on the selected version: a price drawn in the image (an integer `headline.price_ar`), or `whole`, is a new
 *  scene; a price that is a layer changes without a new image, nothing to pay. A style change and a shop line are always
 *  a new scene. */
export const effectOf = (card: Card, selected?: Pick<Visual, 'headline'>): Effect => card.kind === 'restyle' || card.kind === 'line' ? 'scene' : card.effect ?? (card.whole || Number.isInteger(selected?.headline?.price_ar) ? 'scene' : 'free')
export const CHANGE_BUTTONS: Record<Effect, string> = { refine: 'Créer', scene: 'Refaire l’affiche', free: 'Changer' }
/** The paid button of a card: a recap, or a change by its effect (null: a recap has none). */
export const createName = (card: Card, effect: Effect | null) => card.kind === 'recap' ? 'Créer l’affiche' : card.kind === 'line' ? 'Garder et refaire l’affiche' : CHANGE_BUTTONS[effect ?? 'scene']
/** Whether a card shows the features warning (generation.ts FEATURES_WARNING, D-TERMS-005): a scene adjustment whose
 *  words could ask for features or text (ADR-125: the owner's message and the instruction read from it), until it has
 *  its outcome, whether offered, restored from the device, re-offered after a refusal or kept for « Réessayer » /
 *  « Reprendre ». A new scene or a free change sends no adjustment. */
export const warns = (item: Item) => changes(item.card) && effectOf(item.card!) === 'refine' && !item.done && asksText(`${item.card!.said ?? ''} ${item.card!.instruction_fr ?? ''}`)
/** A new message or card replaces the open questions and recaps before it: only the latest may be tapped. */
export function supersede(items: Item[]) {
  for (const item of items) if (item.card && item.card.kind !== 'result' && !item.spent) item.done = true
}

export type CardButton = 'photo' | 'copy' | 'create' | 'conditions' | 'retry' | 'resume' | 'fix' | 'account' | 'resend' | 'review' | 'download'
/** The one action a card shows; null when it only shows its text or its outcome. `version` is the state of a result's
 *  version; it is downloaded only while it is the one `selected` in the document (the export renders that one).
 *  `left`: the versions the poster may still ask for; at none, no card offers a new one. `stop`: the shop's credits or
 *  what blocks an image stop a new request (generation.ts credit); a kept request is never stopped by it (D-BALANCE-006):
 *  the server answers what it stored, or refuses it with its own sentence. 'terms': what stops it is the conditions of
 *  use, not accepted: the card offers to read them, the server's order (D-TERMS-003, D-TERMS-004). */
export function cardButton(item: Item, version?: Visual['status'], selected?: string, left: number | null = null, stop: boolean | 'terms' = false): CardButton | null {
  const card = item.card
  if (!card) return null
  if (card.kind === 'result') return version === 'pending_review' ? 'review' : version === 'approved' && card.visual_id === selected ? 'download' : null
  if (card.fix) return 'fix'  // refused by a rule that a retry cannot change: corrected in the editor
  if (card.account) return 'account'  // a shop line refused: « Pas à pas » has no lines, « Mon compte » has
  if (item.done) return null
  // A spent card whose request may have left without an answer: that same request again, never by itself. « Réessayer »
  // after a refusal seen here, « Reprendre » in a later view (a reload, a return from « Pas à pas »).
  if (paid(card)) return !item.spent ? stop === 'terms' ? 'conditions' : (left !== null && left <= 0) || stop ? null : 'create' : item.request && !item.job ? card.error ? 'retry' : 'resume' : null
  if (card.kind === 'ask_photo') return 'photo'
  // Free: the editor's copy on the card's photos. What stops a new image stops it too: the copy would stay without one.
  if (card.kind === 'photo') return !productsOf(card).length ? null : stop === 'terms' ? 'conditions' : stop ? null : 'copy'
  return card.kind === 'failed' && card.retry ? 'resend' : null
}

// ── an existing poster: the version limit and the list of modifications ───────────────────────────────────
/** The server's rule (jobs.SCENE_LIMIT): twelve scene or refine jobs queued, running or succeeded per poster. */
/** The adapter's refusal for a card whose version the poster no longer lists: no new card can do better. */
export const GONE = 'Cette version n’existe plus.'
export const SCENE_LIMIT = 12
export const versionsLeft = (jobs: { kind: string; status: string }[]) =>
  SCENE_LIMIT - jobs.filter(job => ['scene', 'refine'].includes(job.kind) && ['queued', 'running', 'succeeded'].includes(job.status)).length
/** Under a card that pays for a version: nothing while more than two are left; at none, the server's own `attempt_limit`
 *  sentence (api.py MESSAGES; copied, as the server only says it in a refusal). null: the count is not known. */
export const limitLine = (left: number | null) => left === null || left > 2 ? ''
  : left > 0 ? `Il reste ${left} version${left > 1 ? 's' : ''} pour cette affiche.`
  : 'Douze scènes ont déjà été demandées pour cette affiche. Conservez une version ou créez une copie pour continuer.'

export interface Modification { id: string; number: number; status: Visual['status']; state: string; label: string }
const STATES: Record<Visual['status'], string> = { pending_review: 'À vérifier', approved: 'Confirmée', rejected: 'Refusée' }
/** A version's drawn words: a brand that was inside the title was not drawn apart; a price that is a layer is none. */
const drawn = (headline: Visual['headline']): Words => headline ? { title: headline.title, brand: headline.brand_in_title ? null : headline.brand || null, subtitle: headline.subtitle || null, price_ar: headline.price_ar } : {}
/** The drawn words of a version that differ from the one before, with the labels and the order of the server's
 *  field table (reads.py FIELDS), as on a change card. */
function differences(headline: Visual['headline'], before: Visual['headline']) {
  const now = drawn(headline), old = drawn(before)
  return ([['title', 'Titre'], ['brand', 'Marque'], ['subtitle', 'Sous-titre'], ['price_ar', 'Prix']] as const).flatMap(([field, label]) => {
    const value = now[field]
    return value === undefined || value === old[field] || (value === null && old[field] === undefined) ? []
      : [`${label} : ${value === null ? 'retiré' : typeof value === 'number' ? `${value.toLocaleString('fr-FR')} Ar` : value}`]
  })
}
/** What the image still shows while the document says otherwise: the version's stored title and price, each only
 *  when it differs. A version without stored words gives nothing (its hidden layers are the editor's matter). */
export type Stale = { title?: string; price_ar?: number }
export const staleOf = (headline: Visual['headline'], offer?: { title: string; price_ar: number }): Stale => !headline || !offer ? {} : {
  ...(headline.title !== offer.title ? { title: headline.title } : {}),
  ...(headline.price_ar !== undefined && headline.price_ar !== offer.price_ar ? { price_ar: headline.price_ar } : {}) }
export const staleLine = (stale: Stale) => {
  const shown = [...(stale.title === undefined ? [] : [`« ${stale.title} »`]), ...(stale.price_ar === undefined ? [] : [`${stale.price_ar.toLocaleString('fr-FR')} Ar`])]
  return shown.length ? `L’affiche montre encore : ${shown.join(', ')}.` : ''
}
/** The list of modifications, from the poster's versions as the server lists them (newest first): the first poster, a
 *  refinement by the owner's words, a new scene by its drawn words that differ from the version it was made from (the
 *  one a chat card redrew; otherwise the version before it in the list). */
export function modifications(visuals: Visual[]): Modification[] {
  return visuals.map((visual, index) => {
    const before = visuals[index + 1], from = visuals.find(other => other.id === visual.replaces_visual_id) ?? before
    const label = !before ? 'Première affiche' : visual.instruction_fr ? visual.instruction_fr
      : visual.base_visual_id ? 'Scène ajustée'  // a refinement older than the kept instruction
      : differences(visual.headline, from.headline).join(' · ') || 'Nouvelle version'
    return { id: visual.id, number: visuals.length - index, status: visual.status, state: STATES[visual.status], label }
  })
}
