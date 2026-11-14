<script setup lang="ts">
// Creation by message, first request (D-TEXT-FIRST-003). The thread lives in this browser. Every poster action goes
// through the adapter, so the routes, guards and retries are the step editor's. No canvas and no poster font here:
// a version is shown as the server's display image.
// The chat never guesses what became of a paid request: a card keeps its /scenes request exactly as it left (its id is
// the key) and, until the server has answered it, sends that same request again. One tab per device holds the chat
// (Web Locks), and a tab checks it still holds it right before anything paid leaves.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ApiError, displayUrl, mutation, preparedUrl, read } from './api'
import { cardButton, CHAT_PREFIX, complete, fate, final, lines, movedTo, newPending, nextRole, nextStep, PENDING_KEY, readPending, readThread, settled, spend, STYLES, supersede, swapRole, threadKey, trim, UNSENT_KEY, wireDraft,
  type Card, type ChatAdapter, type Draft, type Item, type JobRow, type Pending, type Picture, type Role, type Style } from './chat'
import { parsePrice, type Visual } from './document'
import { staleWords } from './words'

const props = defineProps<{ adapter: ChatAdapter }>()
const emit = defineEmits<{ steps: [] }>()
const state = props.adapter.state

interface Unsaved { id: string; role: Role; file: File; url: string; status: 'sending' | 'done' | 'failed'; asset?: string; warnings: string[]; error: string }
const items = ref<Item[]>([]), draft = reactive<Draft>({ name: null, price_ar: null, style: 'clair', pictures: [] })
const tray = ref<Unsaved[]>([]), text = ref(''), reading = ref(false), starting = ref(false), typing = ref(false), smallAccepted = ref(false), needsAgreement = ref(false)
const root = ref<HTMLElement>(), thread = ref<HTMLElement>(), field = ref<HTMLTextAreaElement>(), picker = ref<HTMLInputElement>(), height = ref(0)
// The read on its way, apart from the text being typed; the ref is the copy that holds when storage fails.
const pending = ref<Pending | null>(null)
let key = threadKey(state.creation?.id), kept = true, checking = false, later: ReturnType<typeof setTimeout> | undefined
// null until the lock is answered; false: the chat is open in another tab of this device. Without Web Locks there is no
// chat: two tabs could each pay for the same wish. `closed`: unmounted; nothing that was on its way acts any more.
const owner = ref<boolean | null>(null), lockless = !navigator.locks
let release: (() => void) | undefined, closed = false, token = 0
// Each hold of the lock has its own token: work begun under an earlier one stays stopped even when this tab holds the
// lock again (the thread may have moved on meanwhile, in the other tab).
const mine = (at = token) => !closed && !!owner.value && at === token
// The /scenes request this card did not send: the tab lost the chat right before it left.
class Stopped extends Error {}

const roleNames: Record<Role, string> = { product: 'Produit', inspiration: 'Inspiration' }
const src = (asset: string) => preparedUrl(`/api/assets/${asset}`)
const price = (value?: number | null) => `${(value ?? 0).toLocaleString('fr-FR')} Ar`
const products = () => draft.pictures.filter(item => item.role === 'product')
const inspiration = computed(() => [...draft.pictures, ...tray.value].some(item => item.role === 'inspiration'))
const smallPhoto = computed(() => needsAgreement.value || products().some(item => item.warnings?.includes('low_resolution')))
// Only the open poster's versions; the one shown is the one selected in its document.
const versions = computed(() => state.creation ? state.visuals : [])
const shown = computed(() => versions.value.find(visual => visual.id === state.selected) ?? versions.value[0])
const numberOf = (visual: Visual) => versions.value.length - versions.value.indexOf(visual)
const versionOf = (item: Item) => versions.value.find(visual => visual.id === item.card?.visual_id)
const stateNames = { pending_review: 'à vérifier', approved: 'approuvée', rejected: 'refusée' }
const imageJob = computed(() => !!state.job && ['scene', 'refine'].includes(state.job.kind))
const openCard = () => items.value.find(item => item.card?.kind === 'recap' && item.spent && !item.done)
// One paid tap, never two, and one read at a time: while anything runs, paid buttons are off and « Envoyer » waits
// (the server's own guard is image_job_running).
const working = computed(() => state.busy || !!state.job || reading.value || starting.value)
const locked = computed(() => !owner.value || working.value || (!!pending.value && !state.creation))
const waitLine = computed(() => reading.value ? 'Je lis votre message…'
  : imageJob.value ? state.offline ? 'Connexion interrompue. La demande continue.' : ({ queued: 'Je prépare la scène…', running: 'Je dessine l’affiche…', receiving: 'Dernières finitions…' } as Record<string, string>)[state.phase ?? ''] ?? ''
  : state.job?.kind === 'render' ? 'Je prépare le fichier…'
  : starting.value ? state.paletteLoading ? 'Je lis les couleurs de la photo…' : 'Je prépare la scène…' : '')
const greeting = computed(() => state.creation ? 'Voici votre affiche. Pour la changer, passez par Pas à pas.' : 'Quel produit, à quel prix ? Ajoutez sa photo, et une affiche qui vous inspire si vous en avez une.')
const styleName = (item: Item) => inspiration.value ? 'comme votre inspiration' : STYLES.find(([id]) => id === (item.spent ? item.card?.style : draft.style))?.[1] ?? STYLES[0][1]
// While its own first request is on its way, a spent card shows the waiting line, not « Reprendre ».
const buttonOf = (item: Item) => { const button = cardButton(item, versionOf(item)?.status, state.selected); return button === 'resume' && starting.value ? null : button }
const offersSteps = (card: Card) => card.kind === 'steps' || ['read_failed', 'read_limit', 'chat_unavailable'].includes(card.code ?? '')

// ── kept in this browser ─────────────────────────────────────────────────────────────────────────────────
// Only the tab that holds the chat writes it.
function save() {
  if (!mine()) return
  try {
    localStorage.setItem(key, JSON.stringify({ at: Date.now(), items: trim(items.value), draft }))
    // Capped like the kept words: the oldest threads go first.
    const threads = Object.keys(localStorage).filter(name => name.startsWith(CHAT_PREFIX) && name !== UNSENT_KEY && name !== PENDING_KEY)
    for (const name of staleWords(threads.map(name => [name, localStorage.getItem(name)]))) localStorage.removeItem(name)
  } catch {
    if (kept) state.notice = 'Ce navigateur ne peut pas garder la conversation : elle sera perdue à la fermeture.'
    kept = false
  }
}
function setPending(value: Pending) {
  if (!mine()) return
  pending.value = value
  try { localStorage.setItem(PENDING_KEY, JSON.stringify(value)) } catch { /* the ref holds it for this visit */ }
}
// Only the answer to the stored record's own key clears it: a later read may have replaced it.
function clearPending(done: string) {
  if (!mine()) return
  if (pending.value?.key === done) pending.value = null
  try { if (readPending(localStorage.getItem(PENDING_KEY))?.key === done) localStorage.removeItem(PENDING_KEY) } catch { /* nothing was kept */ }
}
// Restoration only: what is stored, as it is. Nothing is built here (a recap least of all).
function load(id?: string | null) {
  key = threadKey(id)
  let raw: string | null = null
  try { raw = localStorage.getItem(key) } catch { /* nothing was kept */ }
  const saved = readThread(raw)
  items.value = saved.items; smallAccepted.value = false; needsAgreement.value = false; clearTimeout(later)
  // A refusal seen by an earlier view is not this one's: a kept request is offered again with « Reprendre ».
  for (const item of items.value) if (item.spent && item.request && !item.job && !item.done) delete item.card!.error
  Object.assign(draft, saved.draft, { style: saved.draft.style ?? (STYLES.some(([style]) => style === state.look) ? state.look as Style : 'clair') })
  // A read left on its way (a reload, or another thread opened meanwhile): « Réessayer » sends the same record.
  if (pending.value && !id && !items.value.some(item => item.card?.kind === 'failed' && !item.done)) app('L’envoi a été interrompu.', { kind: 'failed', code: 'interrupted', retry: pending.value.text })
}
const add = (item: Partial<Item> & { role: Item['role'] }) => { items.value.push({ id: crypto.randomUUID(), text: '', at: Date.now(), ...item }) }
const app = (line: string, card?: Card) => add({ role: 'app', text: line, card })
// A new question or recap replaces the open ones: only the latest may be tapped.
// On an existing poster it shows what the next scene draws: the document's own words.
const recap = (line = '') => { supersede(items.value); app(line, { kind: 'recap', name: state.offer?.title ?? draft.name ?? undefined, price_ar: state.offer?.price_ar ?? draft.price_ar ?? undefined, style: draft.style }) }
// The editor's form fields are the same refs: the draft fills them, so the switch to « Pas à pas » loses nothing.
function sync() {
  if (state.creation) return
  const all: Picture[] = [...draft.pictures, ...tray.value.flatMap(item => item.asset ? [{ asset: item.asset, role: item.role, warnings: item.warnings }] : [])]
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
  for (const file of [...(input.files ?? [])]) {
    const role = nextRole([...draft.pictures, ...tray.value])
    if (!role) { state.notice = 'Trois photos du produit et une image d’inspiration au plus.'; break }
    tray.value.push({ id: crypto.randomUUID(), role, file, url: URL.createObjectURL(file), status: 'sending', warnings: [], error: '' })
    void sendFile(tray.value[tray.value.length - 1])
  }
  input.value = ''
}
async function sendFile(entry: Unsaved) {
  Object.assign(entry, { status: 'sending', error: '', asset: undefined })
  try { Object.assign(entry, await props.adapter.attach(entry.file, entry.role), { status: 'done' }) }
  catch (reason) { Object.assign(entry, { status: 'failed', error: reason instanceof Error ? reason.message : 'Envoi impossible. Réessayez.' }) }
}
// The server keeps an image under its role: a swapped one is sent again under the other.
function swap(entry: Unsaved) {
  const next = swapRole(tray.value, entry.id, draft.pictures)
  for (const [index, item] of tray.value.entries()) if (item.role !== next[index].role) { item.role = next[index].role; void sendFile(item) }
}
function drop(entry: Unsaved) { URL.revokeObjectURL(entry.url); tray.value = tray.value.filter(item => item !== entry) }

// ── a message ────────────────────────────────────────────────────────────────────────────────────────────
function send() {
  const message = text.value.trim()
  if (locked.value || tray.value.some(item => item.status !== 'done') || (!message && !tray.value.length)) return
  const history = lines(items.value), pictures: Picture[] = tray.value.map(item => ({ asset: item.asset!, role: item.role, warnings: item.warnings }))
  add({ role: 'owner', text: message, pictures })
  draft.pictures.push(...pictures); tray.value.forEach(item => URL.revokeObjectURL(item.url)); tray.value = []; text.value = ''
  nextTick(() => { if (field.value) field.value.style.height = 'auto'; field.value?.focus() })
  // ponytail: a change to an existing poster is T-CHAT-004; no read is paid for a request the chat cannot carry out yet.
  if (state.creation) app('Pour changer cette affiche, passez par Pas à pas.', { kind: 'steps' })
  else if (!message) { if (complete(draft)) recap(); else app('Photo ajoutée.') }
  else setPending(newPending({ text: message, draft: wireDraft(draft), history } as { text: string }))
  // The bubble and the draft with its uploaded images are stored before the read leaves.
  save()
  if (pending.value) void ask()
}
// Sends the pending record, as it is: the first time, and at each « Réessayer » until an answer settles it.
async function ask() {
  const record = pending.value, from = key, at = token
  if (!record || working.value || !mine()) return
  for (const item of items.value) if (item.card?.kind === 'failed') item.done = true
  reading.value = true
  try {
    // Sent in the same turn as the check above: nothing is awaited in between.
    const answer = await read<{ card: Card & { text_fr: string }; draft: { name: string | null; price_ar: number | null; style: Style | null } }>(record)
    if (!mine(at) || key !== from) return  // closed, taken, or another thread: the record stays, its answer is asked again, unpaid
    clearPending(record.key)
    Object.assign(draft, { name: answer.draft.name, price_ar: answer.draft.price_ar, style: answer.draft.style ?? draft.style })
    const { text_fr, ...card } = answer.card
    if (card.kind !== 'unclear') supersede(items.value)
    app(text_fr, card)
  } catch (reason) {
    if (!mine(at) || key !== from) return
    const code = reason instanceof ApiError ? reason.code : '', sentence = reason instanceof Error ? reason.message : 'La demande a échoué.'
    if (reason instanceof ApiError && settled(code)) clearPending(record.key)
    if (code === 'budget_exhausted') {  // nothing can be read until the budget is raised: the text goes back to the field
      const at = items.value.map(item => item.role === 'owner' && item.text === record.text).lastIndexOf(true)
      if (at >= 0) items.value.splice(at, 1)
      text.value = record.text; app(sentence)
    } else app(sentence, { kind: 'failed', code, ...(pending.value || code === 'read_failed' ? { retry: record.text } : {}) })
  } finally { if (mine(at)) { reading.value = false; save() } }
}
// A failed read is settled: its retry is a new paid read. Any other retry is the record that is still pending.
function resend(item: Item) {
  if (working.value) return
  if (!pending.value) setPending(newPending({ text: item.card!.retry!, draft: wireDraft(draft), history: lines(items.value.filter(entry => entry !== item)) } as { text: string }))
  void ask()
}
watch(text, value => { if (!mine()) return; try { if (value) localStorage.setItem(UNSENT_KEY, value); else localStorage.removeItem(UNSENT_KEY) } catch { /* the text holds for this visit */ } })

// ── the paid tap ─────────────────────────────────────────────────────────────────────────────────────────
async function create(item: Item) {
  const at = token
  if (locked.value || !spend(items.value, item.id)) return
  const style = item.card!.style = inspiration.value ? 'clair' : draft.style ?? 'clair'
  item.creation = state.creation?.id
  // Spent and saved before anything leaves; the poster's id and the job's id are added by the two watchers below.
  save()
  // The tap on the recap (photos, name and price in view) is the agreement the form asks with its checkbox.
  if (!state.creation) { sync(); state.intake.confirmed = true }
  starting.value = true
  let failure: unknown
  try {
    await props.adapter.start(item.id, style, smallAccepted.value, request => {
      // Right before /scenes leaves, with nothing awaited until it does: still this tab's chat, and the request kept as sent.
      if (!mine(at)) throw new Stopped()
      item.request = request; save()
    })
  } catch (reason) { failure = reason }
  if (!mine(at)) return  // closed, or the chat was taken (even if taken back since): the tab holding it goes on from what was kept
  starting.value = false
  if (failure) return conclude(item, failure)
  if (style === 'couleur' && state.look === 'clair') app('Couleurs illisibles : Studio clair à la place.')
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
  if (typeof answer?.job_id !== 'string') return conclude(item, failure)
  item.job = answer.job_id; item.card!.error = undefined; save()
  props.adapter.follow({ id: answer.job_id, kind: 'scene', status: 'queued', result_ref: null, error_code: null })
}
// What the card's request ended with. Kept (so perhaps sent): only a refusal for good retires it; otherwise it waits with
// the server's sentence and « Réessayer », the same request. Never kept: never sent, and a new card is offered.
function conclude(item: Item, failure: unknown) {
  const sentence = failure instanceof Error ? failure.message : ''
  if (item.request && !final(failure instanceof ApiError ? failure.code : '')) { item.card!.error = sentence || 'La demande n’a pas abouti.'; return save() }
  item.done = true
  // The server asks the agreement to a small photo: a new card asks it.
  if (failure instanceof ApiError && failure.code === 'acknowledgement_required') { item.card!.error = sentence; needsAgreement.value = true; recap() }
  // A rule refused the poster's words: a new attempt cannot change that, the editor can.
  else if (failure instanceof ApiError && failure.status === 422) Object.assign(item.card!, { error: sentence, fix: true })
  else { app(sentence || 'Rien n’a été envoyé pour cette demande.'); recap() }
  save()
}
// The poster and the job of the card being started, written on it at once (sync): before the next request leaves.
watch(() => state.creation?.id, (id, old) => {
  if (!mine()) return
  const open = starting.value && id && !old ? openCard() : undefined
  if (!open) { load(id); void reconcile(); return }
  // The new poster's thread takes its poster's key; the other tabs are told where it went.
  const from = key
  open.creation = id; key = threadKey(id); save()
  try { localStorage.setItem(from, movedTo(id!)) } catch { /* a tab left behind shows its own copy */ }
}, { flush: 'sync' })
watch(() => state.job, job => {
  const open = starting.value && job?.kind === 'scene' ? openCard() : undefined
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
  else if (outcome === 'made') { open.done = true; app('Le produit, le titre et le prix sont-ils exacts ?', { kind: 'result', visual_id: job.result_ref ?? undefined }) }
  else { open.done = true; app(state.error || 'Cette version n’a pas abouti. Aucune image n’a été ajoutée.'); state.error = ''; recap() }
  save()
}

// ── the screen ───────────────────────────────────────────────────────────────────────────────────────────
// The chat fills what is left of the visible screen (the keyboard shrinks it), so the composer is always in view.
function measure() {
  if (!root.value) return
  const nav = document.querySelector<HTMLElement>('.nav'), fixed = nav && getComputedStyle(nav).position === 'fixed' ? nav.offsetHeight : 0
  height.value = Math.max(240, Math.floor(state.height - root.value.getBoundingClientRect().top - window.scrollY - fixed - 12))
}
function focused() { typing.value = matchMedia('(pointer: coarse)').matches }
// A tap elsewhere takes the focus before its click lands: the layout stays as it is until the tap is over, otherwise the
// button under the finger moves away and the tap is lost (on a touch screen the click follows the blur at once).
function blurred() { setTimeout(() => { if (document.activeElement !== field.value) typing.value = false }, 150) }
function grow() { const area = field.value!; area.style.height = 'auto'; area.style.height = `${area.scrollHeight}px` }
const resized = () => nextTick(measure)

// The tab that holds the chat reads it from storage, as it is; one that takes it over follows the new poster's thread.
function begin(takenOver = false) {
  reading.value = starting.value = false; checking = false  // what an earlier hold had begun is not this one's
  try { pending.value = readPending(localStorage.getItem(PENDING_KEY)); text.value = localStorage.getItem(UNSENT_KEY) ?? '' } catch { /* nothing was kept */ }
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
// The agreement to a small photo is for one product and its photos.
watch(() => [draft.name, products().map(item => item.asset).join()], () => { smallAccepted.value = false })
watch(() => [draft.name, draft.price_ar, draft.pictures.length, tray.value.map(item => `${item.asset}${item.role}`).join()], sync)
watch(() => [state.busy, state.job, state.creation?.id], () => void reconcile(), { flush: 'post', immediate: true })
// A refused version is followed by a new card with its cost; never by a new attempt.
watch(versions, () => {
  if (!mine()) return
  for (const item of items.value) if (item.card?.kind === 'result' && !item.done && versionOf(item)?.status === 'rejected') { item.done = true; recap('Version refusée. Je peux en refaire une.'); save() }
}, { flush: 'post', immediate: true })
watch(() => [items.value.length, waitLine.value], () => nextTick(() => { if (thread.value) thread.value.scrollTop = thread.value.scrollHeight }), { flush: 'post' })
watch(() => [state.height, typing.value, !!shown.value], resized)
onMounted(() => window.addEventListener('resize', resized))
// Ownership goes before the lock: what was on its way when the view closed finds it closed, and does nothing.
onBeforeUnmount(() => { closed = true; owner.value = false; release?.(); clearTimeout(later); window.removeEventListener('resize', resized); tray.value.forEach(item => URL.revokeObjectURL(item.url)) })
</script>

<template>
  <section v-if="lockless" class="empty chat-elsewhere" aria-label="Création par message"><p role="status">Ce navigateur ne permet pas le chat.</p><button type="button" class="primary" @click="emit('steps')">Pas à pas</button></section>
  <section v-else-if="owner === false" class="empty chat-elsewhere" aria-label="Création par message"><p role="status">Le chat est ouvert dans un autre onglet.</p><button type="button" class="primary" @click="takeOver">Continuer ici</button></section>
  <section v-else-if="owner" ref="root" class="chat" :class="{ 'has-poster': !!shown, typing }" :style="{ height: `${height}px` }" aria-label="Création par message">
    <aside v-if="shown" class="chat-side">
      <button type="button" class="chat-poster" aria-label="Agrandir l’affiche" @click="adapter.review(shown)"><img :src="displayUrl(shown.image_url)" :alt="`Affiche, version ${numberOf(shown)}`" /></button>
      <p><b>Version {{ numberOf(shown) }} · {{ stateNames[shown.status] }}</b><span translate="no">{{ state.creation?.document.offer.title }} · {{ price(state.creation?.document.offer.price_ar) }}</span></p>
    </aside>
    <div ref="thread" class="chat-thread" role="log" aria-live="polite" aria-label="Conversation" tabindex="0">
      <div class="bubble bot"><p>{{ greeting }}</p></div>
      <div v-for="item in items" :key="item.id" class="bubble" :class="item.role === 'owner' ? 'me' : 'bot'">
        <div v-if="item.pictures?.length" class="pics"><span v-for="picture in item.pictures" :key="picture.asset" class="pic"><img :src="src(picture.asset)" width="68" height="68" :alt="picture.role === 'product' ? 'Photo du produit' : 'Image d’inspiration'" />{{ roleNames[picture.role] }}</span></div>
        <p v-if="item.text && item.card?.kind !== 'result'">{{ item.text }}</p>
        <template v-if="item.card?.kind === 'recap'">
          <div v-if="draft.pictures.length" class="pics"><span v-for="picture in draft.pictures" :key="picture.asset" class="pic"><img :src="src(picture.asset)" width="68" height="68" :alt="picture.role === 'product' ? 'Photo du produit' : 'Image d’inspiration'" />{{ roleNames[picture.role] }}</span></div>
          <p class="recap"><b translate="no">{{ item.card.name }}</b><span class="recap-price">{{ price(item.card.price_ar) }}</span><small>Style : {{ styleName(item) }}</small></p>
        </template>
        <template v-for="version in item.card?.kind === 'result' ? [versionOf(item)] : []" :key="item.id">
          <template v-if="version">
            <button type="button" class="chat-poster small" aria-label="Agrandir l’affiche" @click="adapter.review(version)"><img :src="displayUrl(version.image_url)" :alt="`Affiche, version ${numberOf(version)}`" /></button>
            <p>Version {{ numberOf(version) }} prête. {{ item.text }}</p>
            <p v-if="version.status !== 'pending_review'" class="chat-state" :class="version.status">{{ version.status === 'approved' ? 'Approuvée' : 'Refusée' }}</p>
            <small v-if="version.status === 'approved' && version.id !== state.selected">Ce n’est pas la version choisie pour l’affiche.</small>
          </template>
          <p v-else-if="!working">Cette version n’est plus disponible.</p>
        </template>
        <p v-if="item.card?.error" class="why" role="alert">{{ item.card.error }}</p>
        <template v-for="button in [buttonOf(item)]" :key="button ?? ''">
          <p v-if="button === 'resume'">L’affiche n’a peut-être pas été lancée.</p>
          <label v-if="button === 'create' && smallPhoto" class="check"><input v-model="smallAccepted" type="checkbox" />La photo du produit est petite : l’affiche peut manquer de netteté. J’accepte une qualité réduite.</label>
          <div v-if="button || (item.card && !item.done && offersSteps(item.card))" class="acts">
            <button v-if="button === 'create'" type="button" class="primary" :disabled="locked || (smallPhoto && !smallAccepted)" @click="create(item)">Créer l’affiche</button>
            <button v-else-if="button === 'retry' || button === 'resume'" type="button" class="primary" :disabled="locked" @click="replay(item)">{{ button === 'retry' ? 'Réessayer' : 'Reprendre' }}</button>
            <button v-else-if="button === 'fix'" type="button" class="primary" @click="emit('steps')">Corriger dans Pas à pas</button>
            <button v-else-if="button === 'resend'" type="button" class="primary" :disabled="working" @click="resend(item)">Réessayer</button>
            <button v-else-if="button === 'photo'" type="button" class="primary" @click="picker?.click()">Ajouter une photo</button>
            <button v-else-if="button === 'review'" type="button" class="primary" @click="adapter.review(versionOf(item)!)">Vérifier</button>
            <button v-else-if="button === 'download'" type="button" class="primary" :disabled="locked" @click="adapter.download()">Télécharger</button>
            <button v-if="item.card && !item.done && offersSteps(item.card)" type="button" class="secondary" @click="emit('steps')">Pas à pas</button>
          </div>
          <small v-if="button === 'create' || button === 'retry' || button === 'resume'">{{ state.cost }}</small>
          <small v-if="button === 'create'">Une erreur ? Écrivez la correction.</small>
        </template>
      </div>
      <div v-if="waitLine" class="bubble bot chat-wait"><i aria-hidden="true" /><p>{{ waitLine }}</p></div>
    </div>
    <form class="composer" @submit.prevent="send()">
      <div v-if="tray.length" class="tray">
        <span v-for="entry in tray" :key="entry.id" class="pic" :aria-busy="entry.status === 'sending' || undefined">
          <img :src="entry.url" width="68" height="68" :alt="entry.role === 'product' ? 'Photo du produit' : 'Image d’inspiration'" />
          <button v-if="entry.status === 'failed'" type="button" class="pic-role" @click="sendFile(entry)">Réessayer</button>
          <button v-else type="button" class="pic-role" :class="entry.role" :disabled="entry.status === 'sending'" :aria-label="`${roleNames[entry.role]} : changer le rôle de cette image`" title="Toucher pour changer" @click="swap(entry)">{{ roleNames[entry.role] }}</button>
          <button type="button" class="pic-drop" aria-label="Retirer cette image" @click="drop(entry)"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
        </span>
      </div>
      <p v-for="entry in tray.filter(item => item.error)" :key="entry.id" class="why" role="alert">{{ entry.error }}</p>
      <!-- The style is chosen for the first version only; an inspiration image takes its place. -->
      <div v-if="!state.creation" class="style-row" :role="inspiration ? undefined : 'group'" :aria-label="inspiration ? undefined : 'Style de l’affiche'">
        <span v-if="inspiration" class="style-pill plain">Style : comme votre inspiration</span>
        <button v-for="[id, name] in inspiration ? [] : STYLES" :key="id" type="button" class="style-pill" :aria-pressed="draft.style === id" @click="draft.style = id; save()"><img :src="`/styles/${id}.jpg`" width="26" height="26" alt="" />{{ name }}</button>
      </div>
      <div class="compose-row">
        <button type="button" class="ghost icon" aria-label="Ajouter des images" @click="picker?.click()"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l9-9a3.7 3.7 0 0 1 5.2 5.2l-9 9a1.8 1.8 0 0 1-2.6-2.6l8.3-8.3" /></svg></button>
        <textarea ref="field" v-model="text" rows="1" maxlength="500" enterkeyhint="send" aria-label="Votre message" :placeholder="state.creation ? 'Votre message…' : 'Produit et prix…'"
          @input="grow" @keydown.enter.exact.prevent="send()" @focus="focused" @blur="blurred" />
        <!-- mousedown is held back so that the tap keeps the focus, and the keyboard, on the field. -->
        <button type="submit" class="send" aria-label="Envoyer" :aria-busy="reading || undefined" :disabled="locked || tray.some(item => item.status !== 'done') || (!text.trim() && !tray.length)" @mousedown.prevent><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg></button>
      </div>
      <input ref="picker" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden @change="attach" />
    </form>
  </section>
</template>
