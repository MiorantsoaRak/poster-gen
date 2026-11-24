<script setup lang="ts">
// Creation by message: the first poster, then its changes (D-TEXT-FIRST-003). The thread lives in this browser. Every poster action goes
// through the adapter, so the routes, guards and retries are the step editor's. No canvas and no poster font here:
// a version is shown as the server's display image.
// The chat never guesses what became of a paid request: a card keeps its /scenes or /refinements request exactly as it left (its id is
// the key) and, until the server has answered it, sends that same request again. One tab per device holds the chat
// (Web Locks), and a tab checks it still holds it right before anything paid leaves.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ApiError, displayUrl, mutation, preparedUrl, read, shopStorage } from './api'
import { amountsOf, cardButton, changes, chosenKit, complete, createName, effectOf, fate, final, identityLine, keepRequest, kitChips, kitDraft, kitOf, limitLine, linesLine, newLines, ownTitle, PRODUCT_PHOTOS, lines, modifications, movedTo, newPending, nextRole, nextStep, normal, paid, pendingFor, pendingKey, picturesOfRecap, productsOf, recapFormat, readPending, readThread, ROLE_NAMES, sceneLine, settled, spend, staleLine, STYLES, storeThread, supersede, swapLabel, swapRole, textOf, texts, threadKey, titleLine, TITLES, trim, unresolved, unsentKey, UNSTORED, versionsLeft, warns, wireDraft,
  type Card, type ChatAdapter, type Chip, type Draft, type Item, type JobRow, type Pending, type Picture, type Role, type SceneRequest, type Style, type Words, GONE } from './chat'
import { parsePrice, type Visual } from './document'
import { DRAW_TIME, ended, FEATURES_WARNING, ONCE } from './generation'

const props = defineProps<{ adapter: ChatAdapter }>()
const emit = defineEmits<{ steps: [] }>()
const state = props.adapter.state

interface Unsaved { id: string; role: Role; file: File; url: string; status: 'sending' | 'done' | 'failed'; asset?: string; warnings: string[]; error: string }
const items = ref<Item[]>([]), draft = reactive<Draft>({ name: null, price_ar: null, style: 'clair', identity: null, pictures: [], scene_fr: null, offer_lines: [], lines: true, look: null, title: null })
const tray = ref<Unsaved[]>([]), text = ref(''), reading = ref(false), starting = ref(false), copying = ref(false), typing = ref(false), smallAccepted = ref(false), needsAgreement = ref(false)
const root = ref<HTMLElement>(), thread = ref<HTMLElement>(), field = ref<HTMLTextAreaElement>(), picker = ref<HTMLInputElement>(), height = ref(0)
// The read on its way, apart from the text being typed; the ref is the copy that holds when storage fails.
const pending = ref<Pending | null>(null)
let key = threadKey(state.creation?.id), kept = true, checking = false, later: ReturnType<typeof setTimeout> | undefined
// null until the lock is answered; false: the chat is open in another tab of this device. Without Web Locks there is no
// chat: two tabs could each pay for the same wish. `closed`: unmounted; nothing that was on its way acts any more.
const owner = ref<boolean | null>(null), lockless = !navigator.locks
let release: (() => void) | undefined, closed = false, token = 0, heldAtClose = false
// Each hold of the lock has its own token: work begun under an earlier one stays stopped even when this tab holds the
// lock again (the thread may have moved on meanwhile, in the other tab).
const mine = (at = token) => !closed && !!owner.value && at === token
// The /scenes request this card did not send: the tab lost the chat right before it left.
class Stopped extends Error {}

const src = (asset: string) => preparedUrl(`/api/assets/${asset}`)
const price = (value?: number | null) => `${(value ?? 0).toLocaleString('fr-FR')} Ar`
const products = () => draft.pictures.filter(item => item.role === 'product')
// On an existing poster the style's model image is the editor's (the selected version's): what `start` sends. The
// thread's draft is not asked there: the bundle from before added every attached image to it (D-TEXT-FIRST-007).
const inspiration = computed(() => state.creation ? !!state.styleReference : [...draft.pictures, ...tray.value].some(item => item.role === 'inspiration'))
const intakePictures = computed<Picture[]>(() => [...draft.pictures, ...tray.value.flatMap(item => item.asset ? [{ asset: item.asset, role: item.role, warnings: item.warnings }] : [])])
const recapPictures = computed<Picture[]>(() => state.creation
  ? [...(state.productAssets ?? []).map(asset => ({ asset, role: 'product' as const })), ...(state.styleReference ? [{ asset: state.styleReference, role: 'inspiration' as const }] : [])]
  : intakePictures.value)
// The seller's kit for a new poster (D-KIT-009): the scene models, the most recently used first, and what the row chose.
// A style photo of the recap is its scene: no saved look then, and the model's own title by default.
const chips = computed(() => kitChips(state.looks, state.recent))
const chosen = computed(() => chosenKit(draft, state.looks, recapPictures.value.some(picture => picture.role === 'inspiration')))
const needsProduct = (item: Item) => !!state.creation && !state.productAssets?.length && !item.spent && !item.done && item.card?.kind === 'recap'
const picturesOf = (item: Item) => picturesOfRecap(item, recapPictures.value, state.creation?.id)
const smallPhoto = computed(() => needsAgreement.value || products().some(item => item.warnings?.includes('low_resolution')))
// Only the open poster's versions; the one shown is the one selected in its document.
const versions = computed(() => state.creation ? state.visuals : [])
// A poster with no version yet has a new poster's recap: its scene, title and shop lines, and the kit passed at every tap,
// so a « Réessayer » after a failure sends what the recap on screen shows (review t-kit-frontend r1, 1).
const newPoster = computed(() => !versions.value.length)
// `looked`: a version chosen in the list of modifications. Looking is free: the document's choice does not move.
const looked = ref<string | null>(null), listed = ref(false), left = ref<number | null>(null)
const shown = computed(() => versions.value.find(visual => visual.id === (looked.value ?? state.selected)) ?? versions.value[0])
const mods = computed(() => modifications(versions.value))
// What a change card costs: the server's word; a card from before follows the selected version (chat.ts effectOf).
const effect = (item: Item) => changes(item.card) ? effectOf(item.card!, versions.value.find(visual => visual.id === state.selected)) : null
const free = (item: Item) => effect(item) === 'free'
// The version a change card acts on: the one it was read for; a card from before has none, and takes the selected one.
const target = (card: Card) => ((card.effect || card.kind === 'restyle') && card.visual_id) || state.selected || ''
const numberOf = (visual: Visual) => versions.value.length - versions.value.indexOf(visual)
const versionOf = (item: Item) => versions.value.find(visual => visual.id === item.card?.visual_id)
const stateNames = { pending_review: 'à vérifier', approved: 'confirmée', rejected: 'refusée' }
const imageJob = computed(() => !!state.job && ['scene', 'refine'].includes(state.job.kind))
const openCard = () => items.value.find(unresolved)
// The read on its way belongs to one thread: the one of the poster its body names.
const awaited = computed(() => !!pending.value && pendingFor(pending.value) === (state.creation?.id ?? null))
// One paid tap, never two, and one read at a time: while anything runs, paid buttons are off and « Envoyer » waits
// (the server's own guard is image_job_running).
const working = computed(() => state.busy || !!state.job || reading.value || starting.value || copying.value)
const locked = computed(() => !owner.value || working.value || awaited.value)
// A paid card that still waits for its answer comes first: no message is read and no other card is tapped meanwhile,
// so no second card can pay for the same wish, and the card being followed is always the one open card.
const held = computed(() => locked.value || !!openCard())
// One pending read, never replaced: while it waits in another thread nothing is read here, and the way there is offered.
const elsewhere = computed(() => !!pending.value && !awaited.value)
const toPending = () => { const id = pending.value && pendingFor(pending.value); window.location.hash = id ? `message-${id}` : 'message' }
const waitLine = computed(() => reading.value ? 'Je lis votre message…' : copying.value ? 'Je copie l’affiche…'
  : imageJob.value ? state.offline ? 'Connexion interrompue. La demande continue.' : ({ queued: 'Je prépare la scène…', running: `Je dessine l’affiche… ${DRAW_TIME}`, receiving: 'Dernières finitions…' } as Record<string, string>)[state.phase ?? ''] ?? ''
  : state.job?.kind === 'render' ? 'Je prépare le fichier…'
  : state.job?.kind === 'look' ? 'Je lis votre modèle de style…'
  : starting.value ? state.paletteLoading ? 'Je lis les couleurs de la photo…' : 'Je prépare la scène…' : '')
// Nothing in the thread and no poster: the greeting is the centred welcome (D-REDESIGN-003). A card imported from
// « Pas à pas » or a stored assistant-only thread is a conversation already.
const empty = computed(() => !shown.value && !items.value.length)
const preparedDraft = computed(() => empty.value && !!state.creation && !state.job)
const greeting = computed(() => state.creation ? 'Voici votre affiche. Dites ce qu’il faut changer.' : 'Ajoutez une photo du produit. Écrivez son nom, sa couleur ou son modèle, et son prix en ariary, puis touchez « Envoyer ».')
// The recap's scene (D-KIT-004): what the draft says while it waits for its tap, what was sent once spent. The owner's
// words, the style photo read into a model and the kit's saved look and title belong to a new poster only.
const sceneOf = (item: Item) => {
  const open = !item.spent && !item.done, photo = picturesOf(item).some(picture => picture.role === 'inspiration')
  const look = open ? newPoster.value ? chosen.value.look?.name : undefined : item.card?.look
  return sceneLine(photo ? null : look ?? STYLES.find(([id]) => id === (open ? draft.style : item.card?.style))?.[1] ?? STYLES[0][1],
    open ? newPoster.value ? draft.scene_fr : null : item.card?.scene_fr, open && newPoster.value)
}
const titleOf = (item: Item) => titleLine(!item.spent && !item.done ? newPoster.value ? chosen.value.title : undefined : item.card?.title)
// A chip of the kit row. A house style is also what the reader is told; a saved look stays on this device.
function pick(chip: Chip) {
  if (chip.asset) draft.look = chip.id
  else { draft.style = chip.id as Style; draft.look = null }
  save()
}
// The shop's lines a new poster's recap draws (D-KIT-005): the profile's, then the new ones the messages asked for, which
// the tap keeps for the shop first. Drawn only with the recap's switch on and the texts drawn in the image.
const offered = computed(() => newLines(draft.offer_lines, state.shop.lines))
const shopLines = computed(() => newPoster.value ? [...(state.shop.lines ?? []), ...offered.value] : [])
// A `line` card draws every line of the shop once its own are kept, those kept before included (D-KIT-005).
const lineCardLines = (card: Card) => [...(state.shop.lines ?? []), ...newLines(texts(card.lines), state.shop.lines)]
const drawsLines = computed(() => draft.lines && state.drawn !== false && shopLines.value.length > 0)
// While its own first request is on its way, a spent card shows the waiting line, not « Reprendre ».
const buttonOf = (item: Item) => { const button = cardButton(item, versionOf(item)?.status, state.selected, free(item) ? null : left.value, !free(item) && (state.credit.terms ? 'terms' : state.credit.stop)); return button === 'resume' && starting.value ? null : button }
const offersSteps = (card: Card) => card.kind === 'steps' || (card.kind === 'unclear' && !!state.creation) || ['read_failed', 'read_limit', 'chat_unavailable'].includes(card.code ?? '')
// An untapped change card can be taken back: « Annuler ».
const untapped = (item: Item) => changes(item.card) && !item.spent && !item.done
// The document holds words that the selected image does not show (a paid card that made no image, an edit in « Pas à
// pas »): said from the editor's own comparison, never from what a card remembers, on the newest untapped change card
// or under the poster. Not while a paid card waits for its answer: its image may still come.
const stale = computed(() => openCard() ? '' : staleLine(state.stale))
const staleCard = computed(() => items.value.filter(untapped).pop())
// A small photo is agreed before a whole new scene only: a refinement and a free change ask nothing.
const asksPhoto = (item: Item) => smallPhoto.value && [null, 'scene'].includes(effect(item))
// A card whose tap would be a new image request: it says what that costs, or what stops it in place of its button.
const costs = (item: Item) => paid(item.card) && !item.spent && !item.done && !free(item)
// A `photo` card that still offers its copy: what stops a new image is said on it.
const copies = (item: Item) => item.card?.kind === 'photo' && !item.done
const limitOf = (item: Item) => costs(item) ? limitLine(left.value) : ''
// A price card from before says the price is redrawn; a price that is a layer is only changed.
const lineOf = (item: Item) => !item.spent && !item.done && !item.card?.effect && free(item) ? `Je change le prix sur l’affiche : ${price(item.card!.words?.price_ar)}.` : item.text

// ── kept in this browser ─────────────────────────────────────────────────────────────────────────────────
// Only the tab that holds the chat writes it, and only while its shop is open on the page (api.ts shopStorage).
// true once the thread is stored as written (chat.ts storeThread): a paid request leaves only then (ADR-108).
function save() {
  if (!mine()) return false
  let stored = false
  try { stored = storeThread(localStorage, shopStorage, key, JSON.stringify({ at: Date.now(), items: trim(items.value), draft })) } catch { /* refused */ }
  if (!stored) {
    if (kept) state.notice = 'Ce navigateur ne peut pas garder la conversation : elle sera perdue à la fermeture.'
    kept = false
  }
  return stored
}
function setPending(value: Pending) {
  if (!mine()) return
  pending.value = value
  try { shopStorage.setItem(pendingKey(), JSON.stringify(value)) } catch { /* the ref holds it for this visit */ }
}
// Only the answer to the stored record's own key clears it: a later read may have replaced it.
function clearPending(done: string) {
  if (!mine()) return
  if (pending.value?.key === done) pending.value = null
  try { if (readPending(localStorage.getItem(pendingKey()))?.key === done) shopStorage.removeItem(pendingKey()) } catch { /* nothing was kept */ }
}
// Restoration only: what is stored, as it is. Nothing is built here (a recap least of all).
function load(id?: string | null) {
  key = threadKey(id)
  let raw: string | null = null
  try { raw = localStorage.getItem(key) } catch { /* nothing was kept */ }
  const saved = readThread(raw)
  items.value = saved.items; smallAccepted.value = false; needsAgreement.value = false; looked.value = null; listed.value = false; clearTimeout(later)
  // A refusal seen by an earlier view is not this one's: a kept request is offered again with « Reprendre ».
  for (const item of items.value) if (item.spent && item.request && !item.job && !item.done) delete item.card!.error
  // A thread begun here keeps its choices; a new one starts from the kit's last ones (D-KIT-009), a poster's from the
  // editor's style, as before.
  Object.assign(draft, saved.draft, saved.draft.style ? {} : kitDraft(state.creation ? undefined : state.kit, state.look))
  // A read left on its way (a reload, or another thread opened meanwhile): « Réessayer » sends the same record.
  if (awaited.value && !items.value.some(item => item.card?.kind === 'failed' && !item.done)) app('L’envoi a été interrompu.', { kind: 'failed', code: 'interrupted', retry: pending.value!.text })
}
const add = (item: Partial<Item> & { role: Item['role'] }) => { items.value.push({ id: crypto.randomUUID(), text: '', at: Date.now(), ...item }) }
const recapDetails = () => ({
  ...(state.offer ? { name: state.offer.title, price_ar: state.offer.price_ar } : {}),
  format: state.format, pictures: [...recapPictures.value], style: draft.style,
  ...(newPoster.value && draft.scene_fr ? { scene_fr: draft.scene_fr } : {}),
  // Written again at the tap: a chip may have changed since the recap came.
  ...(newPoster.value ? { look: chosen.value.look?.name, title: chosen.value.title } : {}),
})
const app = (line: string, card?: Card) => add({ role: 'app', text: line, card: card?.kind === 'recap' ? { ...card, ...recapDetails() } : card })
// A new question or recap replaces the open ones: only the latest may be tapped.
// On an existing poster it shows what the next scene draws: the document's own words, and, before its first version, the
// logo and contact it carries (a drawn contact leaves only with a new paid image: review r2, finding 3).
const recap = (line = '') => { supersede(items.value); app(line, { kind: 'recap', name: state.offer?.title ?? draft.name ?? undefined, price_ar: state.offer?.price_ar ?? draft.price_ar ?? undefined, style: draft.style, ...(draft.identity !== null && !state.creation ? { identity: draft.identity } : state.creation && newPoster.value && state.shop.ticked ? { identity: true } : {}), ...(newPoster.value ? { first: true } : {}) }) }
// The editor's form fields are the same refs: the draft fills them, so the switch to « Pas à pas » loses nothing.
function sync() {
  if (state.creation) return
  const all = intakePictures.value
  state.intake.name = draft.name ?? ''; state.intake.price = draft.price_ar === null ? '' : String(draft.price_ar)
  state.photos = all.filter(item => item.role === 'product').map(item => ({ asset: item.asset, warnings: item.warnings ?? [] }))
  state.styleReference = all.find(item => item.role === 'inspiration')?.asset ?? null
}
// And back, when the chat opens after « Pas à pas » (never at a reload, whose form is empty, nor from another tab): the
// form's name, price and photos are the product. If they changed, the open recap is replaced; no read is paid for it.
// Back on an existing poster, an unpaid recap takes the document's title and price; spent cards are history.
function importForm() {
  if (state.creation) {
    const card = items.value.find(item => item.card?.kind === 'recap' && !item.spent && !item.done)?.card
    if (card && state.offer && (card.name !== state.offer.title || card.price_ar !== state.offer.price_ar)) { Object.assign(card, { name: state.offer.title, price_ar: state.offer.price_ar }); save() }
    return
  }
  const { name, price } = state.intake
  if (openCard() || !(name.trim() || price.trim() || state.photos.length)) return
  let amount: number | null = null
  try { amount = price.trim() ? parsePrice(price) : null } catch { /* an unreadable price is asked again */ }
  const facts = () => JSON.stringify([draft.name, draft.price_ar, products().map(item => item.asset)]), before = facts()
  Object.assign(draft, { name: name.trim() || null, price_ar: amount, pictures: [...state.photos.map(photo => ({ asset: photo.asset, role: 'product' as Role, warnings: photo.warnings })), ...draft.pictures.filter(item => item.role === 'inspiration')] })
  if (facts() === before) return
  supersede(items.value)
  if (complete(draft)) recap()
  save()
}

// ── images: uploaded when attached, one request each ─────────────────────────────────────────────────────
function attach(event: Event) {
  const input = event.target as HTMLInputElement
  take([...(input.files ?? [])]); input.value = ''
}
// An image copied from a page (« Copier l'image », then Ctrl+V) or dragged from a folder is attached like a picked
// one: the owner's reference poster of 2026-11-24 was in his clipboard, and the composer took nothing.
const images = (data: DataTransfer | null) => [...(data?.files ?? [])].filter(file => file.type.startsWith('image/'))
function pasted(event: ClipboardEvent) {
  const files = images(event.clipboardData)
  if (files.length) { event.preventDefault(); take(files) }  // text alone is pasted as usual
}
function take(files: File[]) {
  if (copying.value) return  // the poster is about to change
  for (const file of files) {
    // On an existing poster every image is a product photo, the copy's (D-TEXT-FIRST-007).
    const role = state.creation ? tray.value.length < PRODUCT_PHOTOS ? 'product' : null : nextRole([...draft.pictures, ...tray.value])
    if (!role) { state.notice = state.creation ? 'Trois photos du produit au plus.' : 'Trois photos du produit et un modèle de style au plus.'; break }
    tray.value.push({ id: crypto.randomUUID(), role, file, url: URL.createObjectURL(file), status: 'sending', warnings: [], error: '' })
    void sendFile(tray.value[tray.value.length - 1])
  }
}
async function sendFile(entry: Unsaved) {
  Object.assign(entry, { status: 'sending', error: '', asset: undefined })
  try { Object.assign(entry, await props.adapter.attach(entry.file, entry.role), { status: 'done' }) }
  catch (reason) { Object.assign(entry, { status: 'failed', error: reason instanceof Error ? reason.message : 'Envoi impossible. Réessayez.' }) }
  sendWaiting()
}
// « Envoyer » asked while a photo is still on its way is kept, and leaves once every photo is in: before, « Entrée »
// did nothing then and the button was off, which read as a lost key press (second walk, 2026-11-24). A photo that
// fails, or one taken out, drops the wish: the owner decides again. Until it leaves, the field is held as it was at
// the press and a line says why: typed on meanwhile, the message would leave in the middle of a word.
const waiting = ref(false)
function sendWaiting() {
  if (!waiting.value || tray.value.some(item => item.status === 'sending')) return
  waiting.value = false
  if (!tray.value.some(item => item.status === 'failed')) void send()
}
// A photo this shop already used for the same product: attached without an upload, and no read is paid for it.
function reuse(asset: string) {
  // Not with photos waiting in the tray: they would go with it and the recap would not show them (review r1).
  if (locked.value || tray.value.length || !/^[a-f0-9]{64}$/.test(asset) || products().length >= PRODUCT_PHOTOS || draft.pictures.some(item => item.asset === asset)) return
  const picture: Picture = { asset, role: 'product' }
  supersede(items.value)
  add({ role: 'owner', pictures: [picture] }); draft.pictures.push(picture)
  if (complete(draft)) recap(); else app('Photo ajoutée.')
  save()
}
// An amount read in the message, chosen by a tap (D-KIT-002): the owner's own figure, so no read is paid for it; the
// recap shows it large before any credit. The price is asked before the photo: a missing photo is asked next.
function pickPrice(item: Item, amount: number) {
  if (locked.value || item.done) return
  supersede(items.value)
  add({ role: 'owner', text: price(amount) }); draft.price_ar = amount
  if (complete(draft)) recap(); else app('Il me faut une photo du produit.', { kind: 'ask_photo' })
  save()
}
// « Ne pas garder »: that new line is neither kept for the shop nor drawn (a poster draws only the shop's lines).
function unkeep(line: string) { draft.offer_lines = draft.offer_lines.filter(entry => entry !== line); save() }
// The server keeps an image under its role: a swapped one is sent again under the other.
function swap(entry: Unsaved) {
  const next = swapRole(tray.value, entry.id, draft.pictures)
  if (next === tray.value) { state.notice = 'Trois photos du produit et un modèle de style au plus.'; return }
  for (const [index, item] of tray.value.entries()) if (item.role !== next[index].role) { item.role = next[index].role; void sendFile(item) }
}
function drop(entry: Unsaved) { URL.revokeObjectURL(entry.url); tray.value = tray.value.filter(item => item !== entry); waiting.value = false }

// ── a message ────────────────────────────────────────────────────────────────────────────────────────────
// A change is read against the stored poster (D-TEXT-FIRST-005): an unsaved edit of « Pas à pas » is saved before a new
// read is made. false: nothing may be read (the save failed and the editor's sentence is shown, the chat was taken, or
// another thread is open); what was typed stays where it is.
async function savedFirst() {
  if (!state.creation) return true
  const at = token, from = key
  let failure: unknown
  reading.value = true
  try { await props.adapter.saved() } catch (reason) { failure = reason }
  if (!mine(at)) return false
  reading.value = false
  if (failure) state.error = failure instanceof Error && failure.message ? failure.message : 'L’affiche n’a pas pu être enregistrée. Vérifiez-la dans Pas à pas.'
  return !failure && key === from
}
const sendable = () => !(held.value || pending.value || tray.value.some(item => item.status !== 'done') || (!text.value.trim() && !tray.value.length))
async function send() {
  if (!held.value && !pending.value && tray.value.some(item => item.status === 'sending') && !tray.value.some(item => item.status === 'failed')) { waiting.value = true; return }
  // Saved first only for words that will be read: images on a poster are not (the copy saves by itself).
  if (!sendable() || (text.value.trim() && versions.value.length && !tray.value.length && !(await savedFirst() && sendable()))) return
  const message = text.value.trim()
  const history = lines(items.value), pictures: Picture[] = tray.value.map(item => ({ asset: item.asset!, role: item.role, warnings: item.warnings }))
  add({ role: 'owner', text: message, pictures })
  if (!state.creation) draft.pictures.push(...pictures)
  tray.value.forEach(item => URL.revokeObjectURL(item.url)); tray.value = []; text.value = ''
  nextTick(() => { if (field.value) field.value.style.height = 'auto'; field.value?.focus() })
  // No read is paid for what the chat cannot carry out: images sent on a poster are never read past (the chat's own
  // card says what they are for, D-TEXT-FIRST-007), and a change needs a version.
  if (state.creation && pictures.length) offer(pictures, message)
  else if (state.creation && !versions.value.length) app('L’affiche n’a pas encore de version.')
  else if (!message) { if (complete(draft)) recap(); else app('Photo ajoutée.') }
  else setPending(readOf(message, history))
  // The bubble and the draft with its uploaded images are stored before the read leaves.
  save()
  if (awaited.value) void ask()
}
// Images on an existing poster (D-TEXT-FIRST-007): never read past. A version belongs to its product's photos, so the
// chat offers the editor's copy of the poster on the new ones; the words sent with them are shown and not read.
function offer(pictures: Picture[], said: string) {
  supersede(items.value)
  app(`Cette affiche garde sa photo. Je peux en faire une copie avec ${pictures.length > 1 ? 'les nouvelles photos' : 'la nouvelle photo'} : même titre, même prix. La copie s’ouvre dans Pas à pas, où vous créez son image. L’affiche actuelle reste dans Mes affiches.${said ? ' Votre message n’est pas lu avec une photo : envoyez-le ensuite.' : ''}`,
    { kind: 'photo', pictures, said })
}
// « Copier avec cette photo »: nothing paid, and no paid card follows it here. The copy is the editor's own action, as
// « Refaire en … »: it opens in « Pas à pas », where « Générer » makes its image. The card is over once the copy exists.
async function copyWith(item: Item) {
  const at = token, card = item.card!
  if (held.value || tray.value.length) return
  card.error = undefined; copying.value = true
  let failure: unknown
  const made = () => { if (!mine(at)) return; item.done = true; item.text = 'La copie est créée : retrouvez-la dans Mes affiches. Cette affiche reste telle quelle.'; save() }
  try { await props.adapter.remake(productsOf(card), () => { if (!mine(at)) throw new Stopped() }, made) } catch (reason) { failure = reason }
  if (!mine(at)) return  // opened in « Pas à pas »: this view is closed
  copying.value = false
  // Refused before the copy existed: the card stays and says why. Once it exists, the editor says what stopped its opening.
  if (failure && !item.done) { card.error = failure instanceof Error && failure.message ? failure.message : 'La copie n’a pas pu être faite. Réessayez.'; save() }
}
// A read's record; on a poster it names it, and the answer is a change card.
// It also names the version the owner looks at; a refused one is not changed: the poster's own version then.
const readOf = (text: string, history: ReturnType<typeof lines>) => newPending({ text, ...(state.creation ? { creation_id: state.creation.id, visual_id: (shown.value?.status === 'rejected' ? state.selected : undefined) ?? shown.value?.id } : {}), draft: wireDraft(draft), history } as { text: string })
// Sends the pending record, as it is: the first time, and at each « Réessayer » until an answer settles it.
async function ask() {
  const record = pending.value, from = key, at = token
  if (!record || !awaited.value || working.value || !mine()) return
  for (const item of items.value) if (item.card?.kind === 'failed') item.done = true
  reading.value = true
  try {
    // Sent in the same turn as the check above: nothing is awaited in between.
    const answer = await read<{ card: Card & { text_fr: string }; draft: { name: string | null; price_ar: number | null; style: Style | null; identity?: boolean; scene_fr?: string | null } }>(record)
    if (!mine(at) || key !== from) return  // closed, taken, or another thread: the record stays, its answer is asked again, unpaid
    clearPending(record.key)
    // A house style named in this message wins over the kit's saved look (the message first, then the kit).
    if (answer.draft.style && answer.draft.style !== draft.style) draft.look = null
    Object.assign(draft, { name: answer.draft.name, price_ar: answer.draft.price_ar, style: answer.draft.style ?? draft.style, identity: answer.draft.identity ?? null, scene_fr: answer.draft.scene_fr || null })
    const { text_fr, ...card } = answer.card
    // The shop's lines this message asked for replace those offered before; a card without the field leaves them.
    if (!state.creation && card.offer_lines !== undefined) draft.offer_lines = texts(card.offer_lines)
    if (card.kind !== 'unclear') supersede(items.value)
    app(text_fr, changes(card) ? { ...normal(card), said: record.text } : card)
  } catch (reason) {
    const code = reason instanceof ApiError ? reason.code : ''
    if (!mine(at) || key !== from) {
      // The session ended here (a 401): the gate closed and unmounted this chat, releasing its lock, before the answer's
      // body came back. Its card is still kept, so that the thread restored after the sign-in says to sign in and offers
      // « Réessayer » (multi-shop.md), but only under the chat's lock taken again, only while the stored request is still
      // this one, and added to the thread as it is stored: another tab that took the chat meanwhile owns it (review r3).
      // shopStorage writes nothing once another tab has signed out (api.ts).
      if (code === 'unauthenticated' && closed && heldAtClose && at === token && key === from && navigator.locks) {
        const thread = key, line = (reason as Error).message
        void navigator.locks.request('affiche-chat', { ifAvailable: true }, lock => {
          if (!lock) return
          try {
            if (readPending(localStorage.getItem(pendingKey()))?.key !== record.key) return
            const saved = readThread(localStorage.getItem(thread))
            if (saved.moved) return
            const card: Item = { id: crypto.randomUUID(), role: 'app', text: line, at: Date.now(), card: { kind: 'failed', code, retry: record.text } as Card }
            if (storeThread(localStorage, shopStorage, thread, JSON.stringify({ at: Date.now(), items: trim([...saved.items, card]), draft: saved.draft }))) shopStorage.removeItem(pendingKey())
          } catch { /* no shop open on this page any more: nothing of it is written */ }
        })
      }
      return
    }
    // The server's sentence for a refused value is the editor's (brand and subtitle): the chat has its own.
    const sentence = code === 'validation_error' ? 'Ce message ne peut pas être lu tel quel. Écrivez-le plus court : le produit et son prix, ou le changement voulu.'
      : reason instanceof Error ? reason.message : 'La demande a échoué.'
    if (reason instanceof ApiError && settled(code)) clearPending(record.key)
    // Refused before anything was read or reserved, until the service, the shop's day, its other reads or the conditions
    // of use (D-TERMS-004) allow it: the text goes back to the field, to be sent again as it is.
    if (['budget_exhausted', 'shop_daily_limit', 'reads_busy', 'terms_required'].includes(code)) {
      const at = items.value.map(item => item.role === 'owner' && item.text === record.text).lastIndexOf(true)
      if (at >= 0) items.value.splice(at, 1)
      text.value = record.text; app(sentence)
    } else app(sentence, { kind: 'failed', code, ...(pending.value || code === 'read_failed' || code === 'unauthenticated' ? { retry: record.text } : {}) })
  } finally { if (mine(at)) { reading.value = false; save() } }
}
// A failed read is settled: its retry is a new paid read. Any other retry is the record that is still pending.
async function resend(item: Item) {
  if (working.value || elsewhere.value) return
  if (!pending.value) {
    if (!await savedFirst() || working.value || elsewhere.value || pending.value || !items.value.includes(item)) return
    setPending(readOf(item.card!.retry!, lines(items.value.filter(entry => entry !== item))))
  }
  void ask()
}
watch(text, value => { if (!mine()) return; try { if (value) shopStorage.setItem(unsentKey(), value); else shopStorage.removeItem(unsentKey()) } catch { /* the text holds for this visit */ } })

// ── the paid tap ─────────────────────────────────────────────────────────────────────────────────────────
async function create(item: Item) {
  const at = token, card = item.card!, kind = effect(item), visual = target(card)
  // Its own sentence stays on a card from before: the server's said the price is redrawn.
  if (kind === 'free') return setWords(visual, card.words ?? {}, 'C’est changé sur l’affiche.', Object.assign(item, { text: lineOf(item) }), true)
  // A recap made before the first version, tapped once the poster has one (made in « Pas à pas » or on another device):
  // it shows no kit any more and would still draw one. Retired with a sentence, nothing paid (review r2, N3).
  if (card.kind === 'recap' && card.first && !newPoster.value) { item.done = true; app('Cette affiche a déjà une version. Dites ce qu’il faut changer.'); save(); return }
  if (held.value || needsProduct(item) || !spend(items.value, item.id)) return
  const photo = recapPictures.value.find(picture => picture.role === 'inspiration')?.asset
  const style = photo ? 'clair' : draft.style ?? 'clair'
  // A new poster's scene words, shop lines, saved look and title, as the recap shows them (D-KIT-004, 005, 009), at every
  // tap until the poster has a version; the card keeps the lines drawn.
  const drawn = drawsLines.value ? [...shopLines.value] : [], keep = drawn.length ? [...offered.value] : []
  const kit = card.kind === 'recap' && newPoster.value ? kitOf(draft.scene_fr, chosen.value, drawn, keep) : undefined
  if (card.kind === 'recap') Object.assign(card, recapDetails(), { style }, drawn.length ? { shop_lines: drawn } : {})
  item.creation = state.creation?.id; looked.value = null
  // Spent and saved before anything leaves (strict send, chat.ts keepRequest): a browser that cannot store the card sends
  // nothing at all, not even the poster or its plan. The poster's id and the job's id are added by the two watchers below.
  if (!save()) return conclude(item, new Error(UNSTORED))
  // The tap on the recap (photos, name and price in view) is the agreement the form asks with its checkbox.
  if (!state.creation) { sync(); state.intake.confirmed = true }
  starting.value = true
  let failure: unknown, made: { look?: string } | undefined
  // Right before the paid request leaves, with nothing awaited until it does: still this tab's chat, and the request kept as sent.
  const owned = () => { if (!mine(at)) throw new Stopped() }
  const sending = (request: SceneRequest) => { owned(); keepRequest(item, request, save) }
  try {
    made = await (card.kind === 'recap' ? props.adapter.start(item.id, style, smallAccepted.value, sending, card.identity, kit)
      : kind === 'refine' ? props.adapter.change(item.id, visual, card.instruction_fr!, owned, sending)
      : props.adapter.revise(item.id, visual, card.words ?? {}, smallAccepted.value, owned, sending, card.kind === 'restyle' ? card.style! : undefined, card.kind === 'line' ? texts(card.lines) : undefined)) ?? undefined
  } catch (reason) { failure = reason }
  if (!mine(at)) return  // closed, or the chat was taken (even if taken back since): the tab holding it goes on from what was kept
  starting.value = false
  if (failure) return conclude(item, failure)
  if (made?.look) {
    // The style photo is a model of the kit now, and the request has taken it: if the image fails, the next recap names it.
    draft.look = state.looks?.find(look => look.reference_asset === photo)?.id ?? draft.look
    app(`Votre modèle de style est gardé dans votre kit : « ${made.look} ».`)
  }
  if (card.kind === 'recap' && style === 'couleur' && state.look === 'clair') app('Couleurs illisibles : Studio clair à la place.')
  save()
}
// « Annuler »: the owner's words go back to the field and the card goes. Nothing was paid for the change; the read was.
function cancel(item: Item) {
  if (!mine()) return
  // A photo card may have come without words: what was typed since stays in the field.
  if (item.card!.kind !== 'photo' || !text.value.trim()) text.value = item.card!.said ?? ''
  items.value = items.value.filter(entry => entry !== item); save()
  nextTick(() => { grow(); field.value?.focus() })
}
// The editor's own edit of the document's words, nothing paid: a free change (`close`: its card is over), and « Remettre
// les textes de l’image » (back to what the selected image shows; a card beside it stays as it is).
async function setWords(visual: string, values: Words, said: string, item?: Item, close = false) {
  const at = token
  if (held.value) return
  let failure: unknown
  try { await props.adapter.words(visual, values, () => { if (!mine(at)) throw new Stopped() }) } catch (reason) { failure = reason }
  if (!mine(at)) return
  const sentence = failure ? failure instanceof Error && failure.message ? failure.message : 'Le changement n’a pas pu être fait. Réessayez.' : undefined
  if (item) { item.card!.error = sentence; if (!failure && close) item.done = true } else if (sentence) state.error = sentence
  if (!failure) app(said)
  save()
}
// The card's kept request, sent again exactly as it first left (same key, body and revision): the server answers what it
// stored, or runs it now if it never arrived. Nothing else ever pays for this card.
async function replay(item: Item) {
  const request = item.request!, at = token
  if (working.value || !mine()) return
  starting.value = true
  let answer: { job_id?: unknown } | undefined, failure: unknown
  // Sent in the same turn as the check above: nothing is awaited in between.
  try { answer = await mutation<{ job_id?: unknown }>(request.path, request.body, request.revision, item.id) } catch (reason) { failure = reason }
  if (!mine(at)) return
  starting.value = false
  // A request the server never took, refused for want of credit: the balance shown was stale. The card keeps its request.
  if (failure instanceof ApiError && failure.code === 'no_credit') props.adapter.recount()
  if (typeof answer?.job_id !== 'string') return conclude(item, failure)
  item.job = answer.job_id; item.card!.error = undefined; save()
  props.adapter.follow({ id: answer.job_id, kind: request.path.endsWith('/refinements') ? 'refine' : 'scene', status: 'queued', result_ref: null, error_code: null })
}
// What the card's request ended with. Kept (so perhaps sent): only a refusal for good retires it; otherwise it waits with
// the server's sentence and « Réessayer », the same request. Never kept: never sent, and a new card is offered.
function conclude(item: Item, failure: unknown) {
  const sentence = failure instanceof Error ? failure.message : '', code = failure instanceof ApiError ? failure.code : ''
  if (item.request && !final(code)) { item.card!.error = sentence || 'La demande n’a pas abouti.'; return save() }
  item.done = true
  // The server asks the agreement to a small photo: a new card asks it.
  if (code === 'acknowledgement_required') { item.card!.error = sentence; needsAgreement.value = true; again(item) }
  // A new line the server refused to keep for the shop, before anything was paid: its sentence, then the recap again,
  // whose « Ne pas garder » drops it (« Pas à pas » has no lines to correct).
  else if (code === 'shop_line_refused' && item.card!.kind === 'recap') { item.card!.error = sentence; again(item) }
  // On a poster the `line` card has no « Ne pas garder »: its sentence, and the way to the shop's lines.
  else if (code === 'shop_line_refused' && item.card!.kind === 'line') Object.assign(item.card!, { error: sentence, account: true })
  // A rule refused the poster's words: a new attempt cannot change that, the editor can. A card from before sets its
  // price alone, so it is offered again; the server's card would set the refused words again.
  else if (failure instanceof ApiError && failure.status === 422) { Object.assign(item.card!, { error: sentence, fix: true }); if (!item.card!.effect && item.card!.kind === 'change') again(item) }
  else if (sentence === GONE) app(sentence, { kind: 'steps' })  // the same card could only be refused again
  else { if (code !== 'headline_stale') app(sentence || 'Rien n’a été envoyé pour cette demande.'); again(item, code) }
  save()
}
// After a retired card: never an attempt, always a new card with its cost.
function again(item: Item, code = '') {
  const { error, fix, ...card } = item.card!
  if (card.kind === 'recap') return recap()
  supersede(items.value)
  // A refinement keeps the words drawn in its base: with other words in the document only a whole new scene can be
  // made, by the editor's « Nouvelle version » at the document's price (a card with no `effect`: chat.ts effectOf).
  if (card.effect === 'refine' && code === 'headline_stale') app('Le texte a changé : je refais l’affiche entière.', { kind: card.kind, whole: true, words: { price_ar: state.offer?.price_ar }, said: card.said })
  // The same card again, as it was read. Its words may be in the document under the old image: `stale` says so.
  else if (card.effect !== 'refine' || code !== 'attempt_limit') app(item.text, card)
}
// The poster and the job of the card being started, written on it at once (sync): before the next request leaves.
watch(() => state.creation?.id, (id, old) => {
  if (!mine()) return
  const open = starting.value && id && !old ? openCard() : undefined
  if (!open) { load(id); void reconcile(); return }
  // The new poster's thread takes its poster's key; the other tabs are told where it went.
  const from = key
  open.creation = id; key = threadKey(id); save()
  try { shopStorage.setItem(from, movedTo(id!)) } catch { /* a tab left behind shows its own copy */ }
}, { flush: 'sync' })
watch(() => state.job, job => {
  const open = starting.value && ['scene', 'refine'].includes(job?.kind ?? '') ? openCard() : undefined
  if (open && !open.job) { open.job = job!.id; save() }
}, { flush: 'sync' })
// What became of the spent card, from what it kept and the server only: its job's state; else, its request kept, the
// owner's « Reprendre » (never sent by itself); else nothing paid left, and a new card is offered.
async function reconcile() {
  const open = openCard(), from = key, at = token
  if (!mine() || !open || state.busy || starting.value || checking || open.creation !== state.creation?.id) return
  const step = nextStep(open)
  if (step === 'new') return conclude(open, undefined)
  if (step === 'replay' || state.job?.id === open.job) return  // the owner decides / the editor is following it
  let job: JobRow
  checking = true
  try { job = await props.adapter.job(open.job!) }
  catch { if (mine(at)) { checking = false; clearTimeout(later); later = setTimeout(reconcile, 10_000) } return }  // not known yet: asked again
  if (!mine(at)) return
  checking = false
  if (key !== from || openCard() !== open) return void reconcile()  // the thread changed meanwhile
  const outcome = fate(job)
  if (outcome === 'running') props.adapter.follow(job)
  else if (outcome === 'made') {
    // A change's version becomes the poster's, as a tap on it in the editor (the export renders the selected one). The
    // choice is saved before the card is closed: after a reload in between, it is made again.
    if (changes(open.card) && job.result_ref) {
      checking = true
      try { await props.adapter.select(job.result_ref, () => { if (!mine(at)) throw new Stopped() }) }
      catch (reason) {
        if (!mine(at)) return
        checking = false
        // The job is known to have made its version, and the poster does not list it: trying again cannot help, and no
        // new paid card is offered for an image that exists. The card is closed; the editor is the way on.
        if (reason instanceof Error && reason.message === GONE) { open.done = true; open.card!.error = undefined; app('La nouvelle version est faite, mais elle n’apparaît pas dans cette affiche. Ouvrez Pas à pas pour la retrouver.', { kind: 'steps' }); return save() }
        open.card!.error = 'La nouvelle version n’est pas encore choisie pour l’affiche. Nouvel essai dans un instant.'; clearTimeout(later); later = setTimeout(reconcile, 10_000); return
      }
      if (!mine(at)) return
      checking = false
      if (key !== from || openCard() !== open) return void reconcile()
    }
    open.done = true; open.card!.error = undefined
    app('Le produit, le titre et le prix sont-ils exacts ?', { kind: 'result', visual_id: job.result_ref ?? undefined })
  }
  // The editor's sentence when it followed the end (poll); else the same one, for a job that ended while no page was open.
  else { open.done = true; app(state.error || ended(job)); state.error = ''; again(open) }
  save()
}

// ── the screen ───────────────────────────────────────────────────────────────────────────────────────────
// The chat fills what is left of the visible screen (the keyboard shrinks it), so the composer is always in view.
function measure() {
  if (!root.value) return
  // The page's bottom padding: the frame's gap over 1180 px (D-REDESIGN-002).
  const bottom = parseFloat(getComputedStyle(document.body).paddingBottom) || 0
  height.value = Math.max(0, Math.floor(state.height - root.value.getBoundingClientRect().top - window.scrollY - bottom - 12))
}
function focused() { typing.value = matchMedia('(pointer: coarse)').matches }
// A tap elsewhere takes the focus before its click lands: the layout stays as it is until the tap is over, otherwise the
// button under the finger moves away and the tap is lost (on a touch screen the click follows the blur at once).
function blurred() { setTimeout(() => { if (document.activeElement !== field.value) typing.value = false }, 150) }
function grow() { const area = field.value!; area.style.height = 'auto'; area.style.height = `${area.scrollHeight}px` }
const resized = () => nextTick(measure)

// The tab that holds the chat reads it from storage, as it is; one that takes it over follows the new poster's thread.
function begin(takenOver = false) {
  reading.value = starting.value = copying.value = false; checking = false  // what an earlier hold had begun is not this one's
  try { pending.value = readPending(localStorage.getItem(pendingKey())); text.value = localStorage.getItem(unsentKey()) ?? '' } catch { /* nothing was kept */ }
  const moved = takenOver && !state.creation ? (() => { try { return readThread(localStorage.getItem(key)).moved } catch { return undefined } })() : undefined
  if (moved) { window.location.hash = `message-${moved}`; return }
  load(state.creation?.id)
  importForm()
  void reconcile()
  nextTick(() => { measure(); if (thread.value) thread.value.scrollTop = thread.value.scrollHeight })
}
// One chat per device: a second tab gets no lock and says so; « Continuer ici » takes it (the first tab then says so).
const hold = (options: LockOptions, takenOver = false) => navigator.locks.request('affiche-chat', options, lock => {
  if (closed) return
  if (!lock) { owner.value = false; return }
  token++; owner.value = true; begin(takenOver)
  return new Promise<void>(done => { release = done })
}).catch(() => { owner.value = false })  // taken over by another tab
function takeOver() { void hold({ steal: true }, true) }
if (!lockless) void hold({ ifAvailable: true })
props.adapter.hasUnsentPhotos = () => !closed && tray.value.length > 0
props.adapter.discardUnsentPhotos = () => { if (!closed) tray.value.forEach(drop) }
props.adapter.waiting = () => mine() ? !!openCard() : undefined
// « Corriger l’affiche » from Message (D-KIT-007): the correction is written here. After the render that ends the review.
props.adapter.focus = () => { if (!closed) void nextTick(() => field.value?.focus()) }
// The agreement to a small photo is for one product and its photos.
watch(() => [draft.name, products().map(item => item.asset).join()], () => { smallAccepted.value = false })
watch(() => [draft.name, draft.price_ar, draft.pictures.length, tray.value.map(item => `${item.asset}${item.role}`).join()], sync)
// A deep link can mount the chat before the poster finishes loading. Update its open recap when the offer arrives.
watch(() => [state.creation?.id, state.offer?.title, state.offer?.price_ar], () => { if (mine() && state.creation) importForm() })
watch(() => [state.busy, state.job, state.creation?.id], () => void reconcile(), { flush: 'post', immediate: true })
// The versions this poster may still ask for, by the server's rule. Not known (a failed read of its jobs): no line, and
// the server's own refusal still holds.
// Only the latest request's answer counts: an older one may arrive last.
let counting = 0
async function count() {
  const turn = ++counting
  left.value = null
  if (!state.creation) return
  try { const jobs = await props.adapter.attempts(); if (turn === counting) left.value = versionsLeft(jobs) } catch { /* said above */ }
}
watch(() => [state.creation?.id, state.job?.id], () => void count(), { immediate: true })
watch(() => state.selected, () => { looked.value = null })
// A refused version is followed by a new card with its cost; never by a new attempt, and only once no paid card waits
// for its answer.
watch(() => [versions.value, !!openCard()], () => {
  if (!mine() || openCard()) return
  for (const item of items.value) if (item.card?.kind === 'result' && !item.done && versionOf(item)?.status === 'rejected') { item.done = true; recap('Version refusée. Je peux en refaire une.'); save() }
}, { flush: 'post', immediate: true })
watch(() => [items.value.length, waitLine.value], () => nextTick(() => { if (thread.value) thread.value.scrollTop = thread.value.scrollHeight }), { flush: 'post' })
watch(() => [state.height, typing.value, !!shown.value, listed.value, state.error, state.notice], resized)
onMounted(() => window.addEventListener('resize', resized))
// Ownership goes before the lock: what was on its way when the view closed finds it closed, and does nothing.
onBeforeUnmount(() => { heldAtClose = owner.value === true; closed = true; owner.value = false; release?.(); clearTimeout(later); window.removeEventListener('resize', resized); tray.value.forEach(item => URL.revokeObjectURL(item.url)) })
</script>

<template>
  <section v-if="lockless" class="empty chat-elsewhere" aria-label="Création par message"><p role="status">Ce navigateur ne permet pas le chat.</p><button type="button" class="primary" @click="emit('steps')">Pas à pas</button></section>
  <section v-else-if="owner === false" class="empty chat-elsewhere" aria-label="Création par message"><p role="status">Le chat est ouvert dans un autre onglet.</p><button type="button" class="primary" @click="takeOver">Continuer ici</button></section>
  <section v-else-if="owner" ref="root" class="chat" :class="{ 'has-poster': !!shown, typing, welcome: empty }" :style="{ height: `${height}px` }" aria-label="Création par message">
    <aside v-if="shown" class="chat-side">
      <button type="button" class="chat-poster" aria-label="Agrandir l’affiche" @click="adapter.review(shown)"><img :src="displayUrl(shown.image_url)" :alt="`Affiche, version ${numberOf(shown)}`" /></button>
      <p><b>Version {{ numberOf(shown) }} · {{ stateNames[shown.status] }}</b><span translate="no">{{ shown.headline?.title ?? state.offer?.title }} · {{ price(shown.headline?.price_ar ?? state.offer?.price_ar) }}</span></p>
      <button type="button" class="mods-toggle" :aria-expanded="listed" aria-controls="chat-mods" @click="listed = !listed">Modifications ({{ mods.length }})</button>
      <div id="chat-mods" class="mods" :class="{ open: listed }" role="group" aria-label="Modifications">
        <h2>Modifications</h2>
        <button v-for="line in mods" :key="line.id" type="button" class="mod" :aria-current="line.id === shown.id || undefined" @click="looked = line.id"><i>V{{ line.number }}</i><span translate="no">{{ line.label }}</span><small :class="line.status">{{ line.state }}</small></button>
      </div>
      <div v-if="stale && !staleCard" class="chat-stale"><p class="why" role="status">{{ stale }}</p><button type="button" class="secondary" :disabled="held" @click="setWords(state.selected!, state.stale, 'Les textes de l’image sont remis.')">Remettre les textes de l’image</button></div>
    </aside>
    <div ref="thread" class="chat-thread" role="log" aria-live="polite" aria-label="Conversation" tabindex="0">
      <div v-if="empty" class="hello">
        <img src="/favicon.svg" width="56" height="56" alt="" />
        <template v-if="preparedDraft">
          <p class="hello-q" translate="no">{{ state.offer?.title || 'Votre brouillon' }}</p>
          <p>Retrouvez la photo, le prix et le style dans Pas à pas pour créer la première image.</p>
          <button type="button" class="secondary" @click="emit('steps')">Vérifier l’offre</button>
        </template>
        <template v-else>
          <p class="hello-q">Quel produit vendez-vous ?</p>
          <p>{{ greeting }}</p>
          <small v-if="!state.creation">Le format Publication est déjà choisi pour Facebook et le téléchargement.</small>
        </template>
      </div>
      <div v-else class="bubble bot"><p>{{ greeting }}</p></div>
      <div v-for="item in items" :key="item.id" class="bubble" :class="item.role === 'owner' ? 'me' : 'bot'">
        <div v-if="item.pictures?.length" class="pics"><span v-for="picture in item.pictures" :key="picture.asset" class="pic"><img :src="src(picture.asset)" width="68" height="68" :alt="picture.role === 'product' ? 'Photo du produit' : 'Modèle de style'" />{{ ROLE_NAMES[picture.role] }}</span></div>
        <p v-if="item.text && item.card?.kind !== 'result'" :class="{ lines: item.role === 'app' }">{{ textOf(lineOf(item), item.card) }}</p>
        <template v-if="item.card?.kind === 'recap'">
          <div v-if="picturesOf(item).length" class="pics"><span v-for="picture in picturesOf(item)" :key="picture.asset" class="pic"><img :src="src(picture.asset)" width="68" height="68" :alt="picture.role === 'product' ? 'Photo du produit' : 'Modèle de style'" />{{ ROLE_NAMES[picture.role] }}</span></div>
          <p v-if="needsProduct(item)" class="why" role="status">
            {{ state.productError || state.productAssets ? 'Les photos du produit sont indisponibles.' : 'Chargement des photos du produit…' }}
            <button v-if="state.productError || state.productAssets" type="button" class="text-button" @click="adapter.reloadProduct()">Recharger le produit</button>
          </p>
          <p class="recap"><b translate="no">{{ item.card.name }}</b><span v-if="item.card.price_ar != null" class="recap-price">{{ price(item.card.price_ar) }}</span><small v-if="recapFormat(item, state.format)" class="recap-format">{{ recapFormat(item, state.format) }}</small></p>
          <small>{{ sceneOf(item) }}</small>
          <small v-if="titleOf(item)">{{ titleOf(item) }}</small>
          <!-- The shop's lines (D-KIT-005): a switch while the recap waits for its tap, the lines drawn once spent. -->
          <template v-if="!item.spent && !item.done && shopLines.length">
            <label v-if="state.drawn !== false" class="switch"><input type="checkbox" :checked="draft.lines" @change="draft.lines = ($event.target as HTMLInputElement).checked; save()" />{{ linesLine(shopLines) }}</label>
            <p v-for="line in state.drawn !== false && draft.lines ? offered : []" :key="line" class="recap-offer">« {{ line }} » : nouvelle, gardée pour la boutique.<button type="button" class="text-button" :aria-label="`Ne pas garder « ${line} »`" @click="unkeep(line)">Ne pas garder</button></p>
            <p v-if="state.drawn === false && offered.length" class="why">Les lignes de la boutique sont dessinées dans l’image : cette affiche n’a pas de textes dessinés.</p>
          </template>
          <small v-else-if="item.spent && texts(item.card.shop_lines).length">{{ linesLine(texts(item.card.shop_lines)) }}</small>
          <small v-if="item.card.identity !== undefined && identityLine(state.shop, item.card.identity)">{{ identityLine(state.shop, item.card.identity) }}</small>
        </template>
        <small v-if="item.card?.kind === 'line' && !item.spent && !item.done">{{ linesLine(lineCardLines(item.card)) }}</small>
        <!-- What the message asked that the poster will not use (D-KIT-004): the server's lines, apart, before any button. -->
        <div v-if="texts(item.card?.unused_fr).length" class="refusal" role="note"><p v-for="line in texts(item.card?.unused_fr)" :key="line" class="why">{{ line }}</p></div>
        <div v-if="item.card?.kind === 'ask_price' && !item.done && amountsOf(item.card).length" class="acts">
          <button v-for="amount in amountsOf(item.card)" :key="amount" type="button" class="secondary" :disabled="locked" @click="pickPrice(item, amount)">{{ price(amount) }}</button>
        </div>
        <template v-for="version in item.card?.kind === 'result' ? [versionOf(item)] : []" :key="item.id">
          <template v-if="version">
            <button type="button" class="chat-poster small" aria-label="Agrandir l’affiche" @click="adapter.review(version)"><img :src="displayUrl(version.image_url)" :alt="`Affiche, version ${numberOf(version)}`" /></button>
            <p>Version {{ numberOf(version) }} prête. {{ item.text }}</p>
            <p v-if="version.status !== 'pending_review'" class="chat-state" :class="version.status">{{ version.status === 'approved' ? 'Confirmée' : 'Refusée' }}</p>
            <small v-if="version.status === 'approved' && version.id !== state.selected">Ce n’est pas la version choisie pour l’affiche.</small>
          </template>
          <p v-else-if="!working">Cette version n’est plus disponible.</p>
        </template>
        <div v-if="item.card?.kind === 'ask_photo' && !item.done && item.card.suggestions?.length" class="pics" role="group" aria-label="Photos déjà utilisées pour ce produit">
          <button v-for="photo in item.card.suggestions" :key="photo.asset" type="button" class="pic reuse" :disabled="locked || tray.length > 0" @click="reuse(photo.asset)"><img :src="src(photo.asset)" width="68" height="68" alt="Photo déjà utilisée" />Reprendre cette photo</button>
        </div>
        <p v-if="item.card?.error" class="why" role="alert">{{ item.card.error }}</p>
        <p v-if="stale && item === staleCard" class="why" role="status">{{ stale }}</p>
        <template v-for="button in [buttonOf(item)]" :key="button ?? ''">
          <p v-if="button === 'resume'">L’affiche n’a peut-être pas été lancée.</p>
          <p v-if="limitOf(item)" class="chat-limit">{{ limitOf(item) }}</p>
          <p v-if="(costs(item) || copies(item)) && state.credit.stop" class="why" role="status">{{ state.credit.text }}</p>
          <p v-if="warns(item)" :id="'avertissement-' + item.id" class="why">{{ FEATURES_WARNING }}</p>
          <label v-if="button === 'create' && asksPhoto(item)" class="check"><input v-model="smallAccepted" type="checkbox" />La photo du produit est petite : l’affiche peut manquer de netteté. J’accepte une qualité réduite.</label>
          <div v-if="button || untapped(item) || copies(item) || (item.card && !item.done && offersSteps(item.card))" class="acts">
            <button v-if="button === 'create'" :aria-describedby="[warns(item) && 'avertissement-' + item.id, !free(item) && 'cout-' + item.id].filter(Boolean).join(' ') || undefined" type="button" class="primary" :disabled="held || needsProduct(item) || (asksPhoto(item) && !smallAccepted)" @click="create(item)">{{ createName(item.card!, effect(item)) }}</button>
            <button v-else-if="button === 'conditions'" type="button" class="primary" @click="adapter.conditions()">Lire les conditions</button>
            <button v-else-if="button === 'retry' || button === 'resume'" :aria-describedby="[warns(item) && 'avertissement-' + item.id, 'une-fois-' + item.id].filter(Boolean).join(' ')" type="button" class="primary" :disabled="locked" @click="replay(item)">{{ button === 'retry' ? 'Réessayer' : 'Reprendre' }}</button>
            <button v-else-if="button === 'fix'" type="button" class="primary" @click="emit('steps')">Corriger dans Pas à pas</button>
            <a v-else-if="button === 'account'" href="#compte" class="primary">Modifier les lignes dans Mon compte</a>
            <button v-else-if="button === 'resend'" type="button" class="primary" :disabled="working || elsewhere" @click="resend(item)">Réessayer</button>
            <button v-else-if="button === 'photo'" type="button" class="primary" @click="picker?.click()">Ajouter une photo</button>
            <button v-else-if="button === 'copy'" :aria-describedby="'copie-' + item.id" type="button" class="primary" :disabled="held || tray.length > 0" @click="copyWith(item)">{{ productsOf(item.card!).length > 1 ? 'Copier avec ces photos' : 'Copier avec cette photo' }}</button>
            <button v-else-if="button === 'review'" type="button" class="primary" @click="adapter.review(versionOf(item)!)">Vérifier</button>
            <button v-else-if="button === 'download'" type="button" class="primary" :disabled="locked" @click="adapter.download()">Télécharger ou partager</button>
            <button v-if="untapped(item) || (copies(item) && !copying)" type="button" class="secondary" @click="cancel(item)">Annuler</button>
            <button v-if="stale && item === staleCard" type="button" class="secondary" :disabled="held" @click="setWords(state.selected!, state.stale, 'Les textes de l’image sont remis.', item)">Remettre les textes de l’image</button>
            <button v-if="item.card && !item.done && offersSteps(item.card)" type="button" class="secondary" @click="emit('steps')">Pas à pas</button>
          </div>
          <small v-if="button === 'create' && !free(item)" :id="'cout-' + item.id">{{ state.credit.text }}</small>
          <small v-else-if="button === 'retry' || button === 'resume'" :id="'une-fois-' + item.id">{{ ONCE }}</small>
          <small v-else-if="button === 'copy'" :id="'copie-' + item.id">La copie est gratuite. Sa nouvelle image coûtera 1 crédit.</small>
          <small v-if="button === 'create' && item.card?.kind === 'recap'">Une erreur ? Écrivez la correction.</small>
        </template>
      </div>
      <div v-if="waitLine" class="bubble bot chat-wait"><i aria-hidden="true" /><p>{{ waitLine }}</p></div>
    </div>
    <form class="composer" @submit.prevent="send()" @paste="pasted" @dragover.prevent @drop.prevent="take(images($event.dataTransfer))">
      <!-- The seller's kit (D-KIT-009), for the first version only: the scene models (a style photo takes their place) and
           the title's style. -->
      <div v-if="!state.creation" class="kit-row">
        <div class="style-row" :role="inspiration ? undefined : 'group'" :aria-label="inspiration ? undefined : 'Style de l’affiche'">
          <span v-if="inspiration" class="style-pill plain">Scène : votre modèle de style</span>
          <button v-for="chip in inspiration ? [] : chips" :key="chip.id" type="button" class="style-pill" :translate="chip.asset ? 'no' : undefined" :aria-pressed="chip.asset ? chosen.look?.id === chip.id : !chosen.look && draft.style === chip.id" @click="pick(chip)"><img :src="chip.asset ? src(chip.asset) : `/styles/${chip.id}.jpg`" width="36" height="36" alt="" />{{ chip.name }}</button>
        </div>
        <label class="kit-title">Titre<select :value="chosen.title ?? (chosen.model ? '' : 'moderne')" @change="draft.title = ownTitle(($event.target as HTMLSelectElement).value, chosen.model); adapter.keepTitle?.(draft.title); save()">
          <option v-if="chosen.model" value="">Celui du modèle</option><option v-for="[id, name] in TITLES" :key="id" :value="id">{{ name }}</option>
        </select></label>
      </div>
      <div v-if="tray.length" class="tray">
        <span v-for="entry in tray" :key="entry.id" class="pic" :aria-busy="entry.status === 'sending' || undefined">
          <img :src="entry.url" width="68" height="68" :alt="entry.role === 'product' ? 'Photo du produit' : 'Modèle de style'" />
          <button v-if="entry.status === 'failed'" type="button" class="pic-role" @click="sendFile(entry)">Réessayer</button>
          <template v-else-if="state.creation">{{ ROLE_NAMES[entry.role] }}</template>
          <button v-else type="button" class="pic-role" :class="entry.role" :disabled="entry.status === 'sending'" :aria-label="swapLabel(entry.role)" title="Toucher pour changer" @click="swap(entry)">{{ ROLE_NAMES[entry.role] }}</button>
          <button type="button" class="pic-drop" aria-label="Retirer cette image" @click="drop(entry)"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
        </span>
      </div>
      <p v-for="entry in tray.filter(item => item.error)" :key="entry.id" class="why" role="alert">{{ entry.error }}</p>
      <p v-if="elsewhere" class="chat-elsewhere-read" role="status">Un message attend encore sur une autre affiche.<button type="button" class="secondary" @click="toPending">Ouvrir cette affiche</button></p>
      <p v-if="waiting" class="help" role="status">Envoi dès que la photo est prête…</p>
      <textarea ref="field" v-model="text" rows="1" maxlength="500" enterkeyhint="send" aria-label="Votre message" :readonly="waiting" :placeholder="state.creation ? 'Dites ce qu’il faut corriger.' : 'Ex. Téléphone noir 128 Go, 899 000 Ar'"
        @input="grow" @keydown.enter.exact.prevent="send()" @focus="focused" @blur="blurred" />
      <div class="tools">
        <button type="button" class="ghost attach" :class="{ 'first-photos': !state.creation }" aria-label="Ajouter des photos" :disabled="copying" @click="picker?.click()"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l9-9a3.7 3.7 0 0 1 5.2 5.2l-9 9a1.8 1.8 0 0 1-2.6-2.6l8.3-8.3" /></svg><span class="lbl">Photos</span></button>
        <!-- mousedown is held back so that the tap keeps the focus, and the keyboard, on the field. -->
        <button type="submit" class="send" aria-label="Envoyer" :aria-busy="reading || waiting || undefined" :disabled="held || !!pending || tray.some(item => item.status === 'failed') || (!text.trim() && !tray.length)" @mousedown.prevent><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg></button>
      </div>
      <input ref="picker" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden @change="attach" />
    </form>
  </section>
</template>
