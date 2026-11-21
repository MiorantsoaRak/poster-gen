<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { api, ApiError, mutation, shopKey, shopStorage, type Terms } from './api'
import { captionFault, readCaption } from './share'
import { retryDelay } from './generation'
import {
  aloneLine, alreadyLine, answered, atLimit, codePoints, crossed, describe, emptyDraft, faultLine, inFlight, isCandidate,
  keptForSending, leftOutLines, limitLine, LOST, move, postLine, posterCount, publishAction, readStored, refusalOf, remove,
  requestOf, seenOf, takenOut, toggle, whyNot, without, type Candidate, type Candidates, type Draft, type Item, type LeftOut,
  type Page, type Post, type PostBody,
} from './publish'

// « Publier sur Facebook » (D-FB-POST-005): `#publier`, the draft of a post of one or several posters, or with `poster`
// (`#publier-<id>`) the page for that poster alone, whose description is its caption. What it keeps on the device is the
// draft (`post-draft`), whose stamp is the request's key, and for one poster its caption: nothing else.
const props = defineProps<{ poster: string | null; terms: Terms | null }>()
const emit = defineEmits<{ terms: []; poster: [id: string] }>()
const TIMEOUT = 20_000, DRAFT = 'post-draft', POSTS = '/api/facebook/posts'
const UNKEPT = 'Cet appareil n’a pas pu garder votre publication : rien n’a été envoyé. Libérez de la place ou quittez la navigation privée, puis réessayez.'
const UNREAD = 'Votre publication gardée sur cet appareil n’a pas pu être lue.'
const DRAFT_UNKEPT = 'Votre publication reste dans cet onglet, sans être gardée sur cet appareil.'
const CAPTION_UNKEPT = 'La légende reste dans cet onglet, sans être gardée sur cet appareil.'
const RULE = '2 000 caractères au plus. Les retours à la ligne et les émojis sont gardés. Les caractères de contrôle sont refusés, sauf les retours à la ligne et les tabulations.'
const RUNNING = 'Une publication est en cours : attendez son résultat.'
const message = (reason: unknown) => reason instanceof Error ? reason.message : 'La demande a échoué.'
const format = (stamp: string, options: Intl.DateTimeFormatOptions) => { const date = new Date(stamp); return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('fr-FR', options).format(date) }
const moment = (stamp: string) => format(stamp, { dateStyle: 'medium', timeStyle: 'short' })
const day = (stamp: string) => format(stamp, { dateStyle: 'long' })
const titleOf = (item: Candidate) => item.title || item.name

// ── one tab at a time holds the page, as « Par message » holds the chat (ChatView.vue) ────────────────────────────
// null until the lock is answered; false: the page is open in another tab of this device, and this one reads, writes,
// polls and sends nothing. Each hold has its own token: what began under an earlier one stays stopped. Without Web Locks
// there is no page, as there is no chat: two tabs would race on the draft.
const owner = ref<boolean | null>(null), lockless = !navigator.locks
let release: (() => void) | undefined, closed = false, token = 0
const holding = (at = token) => !closed && owner.value === true && at === token
function lost() { owner.value = false; clearTimeout(pollTimer); clearTimeout(checkTimer); sheet.value = null; absent.value = null }
const hold = (options: LockOptions) => navigator.locks.request('affiche-publish', options, lock => {
  if (closed) return
  if (!lock) { owner.value = false; return }
  token++; owner.value = true; begin()
  return new Promise<void>(done => { release = done })
}).catch(() => { if (!closed) lost() })  // taken over by another tab
function takeOver() { void hold({ steal: true }) }

// ── the draft: read three ways apart; written at each change; a write refused is said ─────────────────────────
const draft = shallowRef<Draft>(emptyDraft()), draftLine = ref(''), takenLines = ref<string[]>([])
// '': read (or nothing kept); otherwise the draft kept here could not be read: nothing is removed, written over or sent.
const unread = ref<'' | 'unreadable' | 'damaged'>(''), unreadLine = ref('')
const draftCount = ref(0)  // the page for one poster only says that a draft is kept
function readKept() {
  const found = readStored(() => shopStorage.getItem(shopKey(DRAFT)))
  if (props.poster) { draftCount.value = found.state === 'read' ? found.draft.items.length : 0; unread.value = ''; return }
  unread.value = found.state === 'unreadable' || found.state === 'damaged' ? found.state : ''
  draft.value = found.state === 'read' ? found.draft : emptyDraft()
}
function keep(next: Draft) {
  if (!holding() || unread.value) return
  draft.value = next
  try {
    if (next.items.length || next.description || next.post) shopStorage.setItem(shopKey(DRAFT), JSON.stringify(next))
    else shopStorage.removeItem(shopKey(DRAFT))
    draftLine.value = ''
  } catch { draftLine.value = DRAFT_UNKEPT }
}
// « Réessayer »: the draft read again. « Vider », for a damaged one only: the owner's own choice to drop it.
function readAgain() { readKept(); if (!unread.value) void readCandidates() }
function dropDamaged() {
  if (!holding() || unread.value !== 'damaged') return
  try { shopStorage.removeItem(shopKey(DRAFT)); unreadLine.value = '' } catch { unreadLine.value = DRAFT_UNKEPT; return }
  readAgain()
}
// The page for one poster keeps no draft: its stamp and its post live in the tab.
const alone = shallowRef<Candidate | LeftOut | null>(null)
const single = ref({ stamp: crypto.randomUUID(), post: null as string | null })

// ── the candidates: the Page, the shop's limit, the grid, the draft's posters resolved by id ─────────────────────
const page = shallowRef<Page | undefined>(), limit = ref<number | null>(null), leftOut = shallowRef<Candidates['left_out'] | null>(null)
const known = shallowRef<Record<string, Candidate>>({}), grid = shallowRef<Candidate[]>([]), gridNext = ref<string | null>(null)
const readError = ref(''), reading = ref(false), gridLoading = ref(false)
// `stale`: a post settled, or the server refused what the page saw, since the marks (each poster's `last`) were read:
// « Publier… » stays off until they are read again.
const stale = ref(false)
const candidates = (query: string) => api<Candidates>(`/api/facebook/posts/candidates?${query}`, { quiet: true, timeout: TIMEOUT })
function learn(answer: Candidates) {
  page.value = answer.page; limit.value = answer.post_image_limit; leftOut.value = answer.left_out
  const found = answer.items.filter(isCandidate)
  if (found.length) known.value = { ...known.value, ...Object.fromEntries(found.map(item => [item.id, item])) }
  return answer
}
let readTurn = 0
async function readCandidates() {
  const at = token, turn = ++readTurn, counts = () => holding(at) && turn === readTurn
  reading.value = true; readError.value = ''
  try {
    if (props.poster) {
      const answer = await candidates(`ids=${props.poster}`)
      if (counts()) { alone.value = learn(answer).items[0] ?? { id: props.poster, reason: 'gone' }; stale.value = false }
      return
    }
    const ids = draft.value.items, chunks: string[][] = []
    for (let start = 0; start < ids.length; start += 200) chunks.push(ids.slice(start, start + 200))  // 200 ids a request at most
    const [first, ...resolved] = await Promise.all([candidates('limit=20'), ...chunks.map(chunk => candidates(`ids=${chunk.join(',')}`))])
    if (!counts()) return
    learn(first); grid.value = first.items.filter(isCandidate); gridNext.value = first.next_cursor; stale.value = false
    const gone = resolved.flatMap(answer => learn(answer).items.filter((item): item is LeftOut => !isCandidate(item)))
      .filter(item => draft.value.items.includes(item.id))
    if (gone.length) {
      takenLines.value = gone.map(item => takenOut(draft.value.items.indexOf(item.id), item.reason))
      keep(without(draft.value, new Set(gone.map(item => item.id))))
    }
  } catch (reason) { if (counts()) readError.value = message(reason) }
  finally { if (turn === readTurn) reading.value = false }
}
// « Voir plus »: one page at a time; an answer a full read has overtaken is dropped; a poster is never shown twice.
async function moreGrid() {
  if (gridLoading.value || reading.value || !gridNext.value) return
  const at = token, turn = readTurn, counts = () => holding(at) && turn === readTurn
  gridLoading.value = true; readError.value = ''
  try {
    const answer = await candidates(`limit=20&before=${encodeURIComponent(gridNext.value)}`)
    if (!counts()) return
    learn(answer)
    grid.value = [...grid.value, ...answer.items.filter(isCandidate).filter(item => !grid.value.some(shown => shown.id === item.id))]
    gridNext.value = answer.next_cursor
  } catch (reason) { if (counts()) readError.value = message(reason) }
  finally { gridLoading.value = false }
}
function marksMoved() { stale.value = true; void readCandidates() }
const connected = computed(() => page.value?.state === 'connected')
const chosen = computed(() => props.poster ? (alone.value && isCandidate(alone.value) ? [alone.value] : [])
  : draft.value.items.map(id => known.value[id]).filter((item): item is Candidate => !!item))
const full = computed(() => atLimit(draft.value, limit.value))
const left = computed(() => leftOutLines(leftOut.value))

// ── the description: the draft's, or the one poster's caption (« Partager »'s own key, its rules) ───────────────
const caption = ref(''), captionLine = ref('')
const description = computed(() => props.poster ? caption.value : draft.value.description)
function typeDescription(text: string) {
  if (!props.poster) { keep(describe(draft.value, text)); return }
  if (!holding()) return
  caption.value = text
  single.value = { stamp: crypto.randomUUID(), post: null }  // another description is another request
  const fault = captionFault(text)
  if (fault === 'bad_character' || fault === 'too_long') return  // not kept, as in « Partager »: the fault's line says why
  try {
    const key = shopKey('caption.' + props.poster)
    if (fault === 'blank') shopStorage.removeItem(key); else shopStorage.setItem(key, text)
    captionLine.value = ''
  } catch { captionLine.value = CAPTION_UNKEPT }
}
// « Reprendre la légende de… »: the chosen posters that have a caption on this device; a description not empty is asked first.
const captions = computed(() => props.poster ? [] : chosen.value.flatMap(item => {
  try { const text = readCaption(shopStorage.getItem(shopKey('caption.' + item.id))); return text ? [{ title: titleOf(item), text }] : [] } catch { return [] }
}))
const replacing = shallowRef<{ title: string; text: string } | null>(null)
function takeCaption(entry: { title: string; text: string }) {
  if (draft.value.description.trim()) replacing.value = entry
  else keep(describe(draft.value, entry.text))
}

// ── the posts, and every answer about the draft's post through one handler, whichever read brought it ──────────
const posts = shallowRef<Post[]>([]), postsNext = ref<string | null>(null), postsError = ref(''), postsRead = ref(false), postsLine = ref('')
const lines = computed(() => posts.value.map(post => ({ post, ...postLine(post) })))
const running = computed(() => posts.value.some(inFlight))
/** The draft's post and the stamp it was made from (an edit forgets the post: `post` is always its own stamp's). */
const followedPost = () => props.poster ? single.value : { post: draft.value.post, stamp: draft.value.stamp }
function handle(post: Post, sent: string) {
  if (props.poster) {
    if (single.value.stamp !== sent) return
    // In flight or unknown: followed. Settled: the next « Publier » is a new request.
    single.value = inFlight(post) || post.status === 'unknown' ? { stamp: sent, post: post.id } : { stamp: crypto.randomUUID(), post: null }
    return
  }
  const next = answered(draft.value, post, sent)
  if (next.write) keep(next.draft ?? emptyDraft())
}
// A post answered on its own (the request, the polling, the stop, the owner's word) is numbered as it arrives: a list
// asked before it never takes its row away or its status back (the list may have left before the post was admitted).
let heard = 0
const heardAt = new Map<string, number>()
/** Answers about posts, from any read: each takes its place in the list; the draft's goes through the handler; a post
 *  whose status moved has the marks read again. `listed`: the turn at which the list's request left. */
function observe(answers: Post[], list: 'merge' | 'replace' | 'append' = 'merge', listed = heard) {
  if (list === 'merge') for (const post of answers) heardAt.set(post.id, ++heard)
  const before = new Map(posts.value.map(post => [post.id, post]))
  const newer = new Map(posts.value.filter(post => list !== 'merge' && (heardAt.get(post.id) ?? 0) > listed).map(post => [post.id, post]))
  const taken = answers.filter(post => !newer.has(post.id)), ids = new Set(answers.map(post => post.id))
  posts.value = list === 'replace' ? [...[...newer.values()].filter(post => !ids.has(post.id)), ...answers.map(post => newer.get(post.id) ?? post)]
    : list === 'append' ? [...posts.value, ...answers.filter(post => !before.has(post.id))]
      : [...answers.filter(post => !before.has(post.id)), ...posts.value.map(post => taken.find(item => item.id === post.id) ?? post)]
  let moved = false
  for (const post of taken) {
    const was = before.get(post.id)
    if (was && was.status !== post.status) moved = true
    const { post: id, stamp } = followedPost()
    if (post.id === id) handle(post, stamp)
  }
  if (moved) marksMoved()
  follow()
}
let pollTimer: ReturnType<typeof setTimeout> | undefined, pollFailures = 0
const pollFailed = ref(false)
async function readPosts(more = false) {
  const at = token, from = more ? postsNext.value : null, listed = heard
  postsError.value = ''
  try {
    const answer = await api<{ items: Post[]; next_cursor: string | null }>(`${POSTS}?limit=20${from ? `&before=${from}` : ''}`, { quiet: true, timeout: TIMEOUT })
    if (!holding(at)) return
    if (!more || from === postsNext.value) postsNext.value = answer.next_cursor
    observe(answer.items, more ? 'append' : 'replace', listed)
  } catch (reason) { if (holding(at)) postsError.value = message(reason) }
  finally { if (holding(at)) { postsRead.value = true; follow() } }
}
// The post in flight is read again every 2 s while the page is held, with the jobs' back-off after a failed read.
function follow() {
  clearTimeout(pollTimer)
  const flying = posts.value.find(inFlight), at = token
  if (holding(at) && flying) pollTimer = setTimeout(() => void poll(flying.id, at), pollFailures ? retryDelay(pollFailures) : 2000)
}
async function poll(id: string, at: number) {
  if (!holding(at)) return
  let answer: Post | null = null
  try { answer = await api<Post>(`${POSTS}/${id}`, { quiet: true, timeout: TIMEOUT }); pollFailures = 0 } catch { pollFailures++ }
  if (!holding(at)) return
  pollFailed.value = pollFailures > 0
  if (answer) observe([answer]); else follow()
}
// A post read by its id: at the opening the draft's own, or one the candidates name and the list does not hold. One
// the server no longer has is forgotten by the draft.
async function readOwnPost(id: string) {
  const at = token
  try { const answer = await api<Post>(`${POSTS}/${id}`, { quiet: true, timeout: TIMEOUT }); if (holding(at)) observe([answer]) }
  catch (reason) {
    if (holding(at) && reason instanceof ApiError && reason.status === 404 && draft.value.post === id) keep({ ...draft.value, post: null })
    /* otherwise the list's read brings it */
  }
}
// The candidates and the posts are read apart and may cross (a reload during the uploads): a chosen poster's `last` in
// flight that the posts show settled has the candidates read again; one they do not hold is read by its id and then
// followed. Once for each post in a hold: a read made after the post was seen settled cannot say it is in flight.
let remarked = new Set<string>(), sought = new Set<string>()
watch(() => [crossed(chosen.value, posts.value), reading.value, postsRead.value] as const, ([found, busy, listed]) => {
  if (!holding() || busy || !listed) return
  const settledSince = found.marks.filter(id => !remarked.has(id))
  if (settledSince.length) { settledSince.forEach(id => remarked.add(id)); marksMoved() }
  for (const id of found.posts.filter(id => !sought.has(id))) { sought.add(id); void readOwnPost(id) }
}, { flush: 'post' })

// ── « Publier… », its confirmation, and the request: the draft's stamp is its key ─────────────────────────────
const accepted = computed(() => props.terms ? !!props.terms.accepted_at : null)
const checking = ref(false), line = ref('')
const action = computed(() => publishAction({ page: page.value ?? null, accepted: accepted.value, checking: checking.value,
  running: running.value, stale: stale.value && !reading.value, chosen: chosen.value, limit: props.poster ? null : limit.value, description: description.value }))
const why = computed(() => whyNot(action.value, limit.value, description.value))
const gridLine = computed(() => props.poster ? '' : limitLine(draft.value.items.length, limit.value))
// Where a refusal is said: beside « Publier… » when it is shown, else under the title.
const beside = computed(() => connected.value && !unread.value && (!props.poster || chosen.value.length > 0))
interface Sheet {
  page: { id: string; name: string }; description: string; stamp: string; line: string; already: string; label: string
  items: (Item & { title: string; thumb: string; file: string; shot: 'loading' | 'loaded' | 'failed'; tries: number })[]
}
// What the sheet shows is frozen as it opens: the items, their `seen`, the description, the stamp, what is already on the Page.
const sheet = ref<Sheet | null>(null), sending = ref(false)
const shown = computed(() => !!sheet.value?.items.every(item => item.shot === 'loaded'))
const sheetWhy = computed(() => running.value ? RUNNING : checking.value ? LOST : shown.value ? '' : 'Le bouton s’active quand toutes les images sont affichées.')
function openSheet() {
  line.value = ''
  if (!holding() || action.value !== 'ready' || reading.value || unread.value || !page.value) return
  const items = chosen.value.map(item => ({ creation_id: item.id, confirmation_id: item.confirmation_id, seen: seenOf(item), title: titleOf(item),
    thumb: item.thumbnail_url ?? item.download_url, file: item.download_url, shot: 'loading' as const, tries: 0 }))
  const already = alreadyLine(chosen.value, day)
  sheet.value = { page: { id: page.value.id, name: page.value.name }, items, line: '', stamp: followedPost().stamp, description: description.value,
    already: already.line, label: already.label }
}
function closeSheet() { sheet.value = null }
// « Réessayer » goes with the failure it answers: the sheet itself takes the focus first, so that Tab and Escape stay in it.
function retryShots() {
  document.querySelector<HTMLElement>('[aria-labelledby="titre-publier-sur"]')?.focus()
  for (const item of sheet.value?.items ?? []) if (item.shot === 'failed') { item.shot = 'loading'; item.tries++ }
}
let checkTimer: ReturnType<typeof setTimeout> | undefined, checkFailures = 0
/** The request, with the draft's stamp as its key. An answer goes through the handler; a refusal is said, the draft and
 *  its stamp kept, and the marks read again before « Publier… » comes back; no answer is said, and the same request goes
 *  again while the draft is still that stamp. */
async function send(body: PostBody, stamp: string, quiet = false) {
  const at = token
  clearTimeout(checkTimer)
  if (!holding(at)) return
  try {
    const post = await mutation<Post>(POSTS, body, undefined, stamp, 'POST', quiet, TIMEOUT)
    if (!holding(at)) return
    checking.value = false; checkFailures = 0; line.value = ''
    handle(post, stamp)
    observe([post])
    if (!inFlight(post)) marksMoved()  // an earlier answer of this key, settled since
  } catch (reason) {
    if (!holding(at)) return
    const refusal = refusalOf(reason)
    if (refusal) {
      // Said beside « Publier… ». terms_required opens the conditions in front (api.ts termsAsked).
      checking.value = false; checkFailures = 0; line.value = refusal.message
      marksMoved(); void readPosts()
      return
    }
    checking.value = true
    checkTimer = setTimeout(() => {
      if (!holding(at)) return
      if (followedPost().stamp === stamp) void send(body, stamp, true)
      else { checking.value = false; void readPosts() }  // another draft now: the list says what became of that one
    }, retryDelay(++checkFailures))
  }
}
async function publishNow() {
  const open = sheet.value
  if (!open || sending.value || !shown.value || running.value || checking.value || !holding()) return
  sending.value = true; open.line = ''
  try {
    // Written and read back before it leaves: nothing is sent unless the device keeps this very draft.
    if (!props.poster && keptForSending({ get: () => shopStorage.getItem(shopKey(DRAFT)), set: value => shopStorage.setItem(shopKey(DRAFT), value) }, draft.value) === 'unkept') {
      open.line = UNKEPT
      return
    }
    const { key, body } = requestOf(open.stamp, open.page.id, open.description, open.items.map(({ creation_id, confirmation_id, seen }) => ({ creation_id, confirmation_id, seen })))
    await send(body, key)
    if (sheet.value === open) sheet.value = null
  } finally { sending.value = false }
}

// ── a post's controls ─────────────────────────────────────────────────────────────────────────────────────────
const stopping = ref<string | null>(null), absent = shallowRef<Post | null>(null), answering = ref(false)
async function stopPost(post: Post) {
  if (stopping.value || !holding()) return
  const at = token
  stopping.value = post.id; postsLine.value = ''
  try { const answer = await api<Post>(`${POSTS}/${post.id}/stop`, { method: 'POST', timeout: TIMEOUT }); if (holding(at)) observe([answer]) }
  catch (reason) { if (holding(at)) postsLine.value = message(reason) }
  finally { stopping.value = null }
}
// The owner's word on an unknown post; « Elle n’y est pas » is asked once more, with what publishing again risks.
async function sayOutcome(post: Post, present: boolean) {
  if (answering.value || !holding()) return
  const at = token
  answering.value = true; postsLine.value = ''
  try {
    const answer = await mutation<Post>(`${POSTS}/${post.id}/outcome`, { present }, undefined, undefined, 'POST', false, TIMEOUT)
    absent.value = null
    if (holding(at)) observe([answer])
  } catch (reason) { absent.value = null; if (holding(at)) { postsLine.value = message(reason); void readPosts(); marksMoved() } }
  finally { answering.value = false }
}
// The draft's buttons keep the focus on the poster moved.
function shift(id: string, by: -1 | 1) {
  keep(move(draft.value, id, by))
  void nextTick(() => {
    const row = document.querySelector(`[data-chosen="${id}"]`)
    const same = row?.querySelector<HTMLButtonElement>(by < 0 ? '.earlier' : '.later'), other = row?.querySelector<HTMLButtonElement>(by < 0 ? '.later' : '.earlier')
    ;(same && !same.disabled ? same : other)?.focus()
  })
}
function drop(id: string) {
  keep(remove(draft.value, id))
  void nextTick(() => document.getElementById('titre-votre-publication')?.focus())
}
const followed = computed(() => { const id = followedPost().post; return posts.value.find(post => post.id === id)?.message_fr ?? '' })

// The page's sheets, as App.vue's: focus in on opening and back on closing; Tab goes round inside.
const vModal = {
  mounted(el: HTMLElement & { back?: Element | null }) { el.back = document.activeElement; el.tabIndex = -1; (el.querySelector<HTMLElement>('[data-focus]') ?? el).focus() },
  unmounted(el: HTMLElement & { back?: Element | null }) { (el.back as HTMLElement | null)?.focus?.() },
}
function keepTab(event: KeyboardEvent) {
  const dialog = event.currentTarget as HTMLElement, controls = [...dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled)')].filter(control => control.checkVisibility())
  const at = document.activeElement, to = event.shiftKey ? (at === controls[0] || at === dialog ? controls.at(-1) : null) : at === controls.at(-1) ? controls[0] : null
  if (to) { event.preventDefault(); to.focus() }
}
const modal = computed(() => !!sheet.value || !!absent.value)
defineExpose({ modal })

// Each hold starts afresh: what an earlier one had begun is not this one's.
function begin() {
  clearTimeout(pollTimer); clearTimeout(checkTimer)
  sheet.value = null; absent.value = null; replacing.value = null; checking.value = false; checkFailures = 0; pollFailures = 0
  line.value = ''; postsLine.value = ''; draftLine.value = ''; unreadLine.value = ''; takenLines.value = []; stale.value = false
  single.value = { stamp: crypto.randomUUID(), post: null }; alone.value = null; remarked = new Set(); sought = new Set()
  if (props.poster) { try { caption.value = readCaption(shopStorage.getItem(shopKey('caption.' + props.poster))); captionLine.value = '' } catch { captionLine.value = CAPTION_UNKEPT } }
  readKept()
  const own = props.poster || unread.value ? null : draft.value.post
  void Promise.all([readCandidates(), readPosts(), own && readOwnPost(own)])
}
if (!lockless) void hold({ ifAvailable: true })
// One page for both addresses (`#publier`, `#publier-<id>`), under the same hold: a remount would ask for the lock
// before this instance had given it back. Another poster starts afresh, and what the earlier one began stays stopped.
watch(() => props.poster, () => { if (holding()) { token++; begin() } })
// Ownership goes before the lock: what was on its way when the view closed finds it closed, and does nothing.
onBeforeUnmount(() => { closed = true; owner.value = false; release?.(); clearTimeout(pollTimer); clearTimeout(checkTimer) })
</script>

<template>
  <section class="gallery shop-publish" aria-labelledby="titre-page-publier">
    <div class="titlerow"><div class="what"><h1 id="titre-page-publier" class="page-title" tabindex="-1">Publier sur Facebook</h1>
      <p v-if="owner && connected" class="meta">Sur la Page <span translate="no">{{ page!.name }}</span></p></div></div>
    <div v-if="lockless" class="empty chat-elsewhere"><p role="status">Ce navigateur ne permet pas la page Publier. Ouvrez l’atelier dans un navigateur à jour.</p></div>
    <div v-else-if="owner === false" class="empty chat-elsewhere"><p role="status">La page Publier est ouverte dans un autre onglet.</p><button type="button" class="primary" @click="takeOver">Continuer ici</button></div>
    <template v-else-if="owner">
    <p v-if="reading && page === undefined" role="status">Lecture de votre Page et de vos affiches…</p>
    <p v-if="readError" class="why lead" role="alert">{{ readError }} <button class="text-button" @click="readCandidates">Réessayer</button></p>
    <div v-if="page !== undefined && !connected" class="refusal"><p>{{ page ? 'Reconnectez votre Page dans « Mon compte ».' : 'Aucune Page Facebook n’est connectée. Connectez votre Page dans « Mon compte ».' }}</p><a href="#compte">Mon compte</a></div>
    <p v-if="line && !beside" class="why lead" role="alert">{{ line }}</p>
    <div v-if="connected && accepted === false" class="refusal"><p>Acceptez d’abord les conditions d’utilisation pour publier.</p><button class="secondary" @click="emit('terms')">Lire les conditions</button></div>

    <section v-if="connected" class="group" aria-labelledby="titre-votre-publication">
      <h2 id="titre-votre-publication" tabindex="-1">Votre publication</h2>
      <template v-if="poster">
        <template v-if="alone && !isCandidate(alone)"><p>{{ aloneLine(alone.reason).text }}</p>
          <button v-if="aloneLine(alone.reason).open" class="secondary" @click="emit('poster', alone.id)">Ouvrir l’affiche</button></template>
      </template>
      <!-- A draft kept here that cannot be read is never an empty one: nothing is removed, written over or sent. -->
      <template v-else-if="unread"><p class="why" role="alert">{{ UNREAD }}</p>
        <div class="row"><button type="button" class="secondary" @click="readAgain">Réessayer</button><button v-if="unread === 'damaged'" type="button" class="secondary" @click="dropDamaged">Vider</button></div>
        <p v-if="unreadLine" class="why" role="alert">{{ unreadLine }}</p></template>
      <template v-else>
        <p v-for="taken in takenLines" :key="taken" class="why" role="status">{{ taken }}</p>
        <p v-if="!chosen.length" class="help">Choisissez vos affiches plus bas, dans l’ordre de la publication.</p>
        <ol v-else class="chosen">
          <li v-for="(item, index) in chosen" :key="item.id" :data-chosen="item.id">
            <img v-if="item.thumbnail_url" :src="item.thumbnail_url" width="48" height="60" alt="" /><span v-else class="blank" aria-hidden="true" />
            <span class="name"><span class="number" aria-hidden="true">{{ index + 1 }}</span><strong translate="no">{{ titleOf(item) }}</strong><span v-if="index === 0" class="badge">En tête</span></span>
            <span class="moves">
              <button type="button" class="earlier" :disabled="index === 0" :aria-label="`Plus tôt « ${titleOf(item)} »`" @click="shift(item.id, -1)">Plus tôt</button>
              <button type="button" class="later" :disabled="index === chosen.length - 1" :aria-label="`Plus tard « ${titleOf(item)} »`" @click="shift(item.id, 1)">Plus tard</button>
              <button type="button" :aria-label="`Retirer « ${titleOf(item)} »`" @click="drop(item.id)">Retirer</button>
            </span>
          </li>
        </ol>
        <p v-if="limit !== null" class="help">{{ limit }} images au plus par publication</p>
      </template>
      <!-- For one poster, its image beside the field on a wide screen: the card is never half empty. -->
      <div v-if="poster ? chosen.length : !unread" class="describe">
        <figure v-if="poster" class="single"><img :src="chosen[0].thumbnail_url ?? chosen[0].download_url" width="200" height="250" alt="" /><figcaption translate="no">{{ titleOf(chosen[0]) }}</figcaption></figure>
        <div class="fields">
        <label>Description de la publication<textarea :value="description" name="description" autocomplete="off" rows="6" aria-describedby="regle-description compte-description etat-description" :aria-invalid="!!faultLine(description) || undefined" @input="typeDescription(($event.target as HTMLTextAreaElement).value)" /></label>
        <p id="regle-description" class="help">{{ RULE }}</p>
        <p id="compte-description" class="meta">{{ codePoints(description).toLocaleString('fr-FR') }} / 2 000</p>
        <p id="etat-description" class="why" role="status">{{ faultLine(description) || draftLine || captionLine }}</p>
        <p v-if="poster" class="help">C’est la légende de cette affiche, la même que dans « Partager ».</p>
        <div v-if="captions.length" class="row"><button v-for="entry in captions" :key="entry.title" type="button" @click="takeCaption(entry)">Reprendre la légende de « {{ entry.title }} »</button></div>
        <div v-if="replacing" class="refusal" role="group" aria-labelledby="question-remplacer"><p id="question-remplacer">Remplacer la description par la légende de « {{ replacing.title }} » ?</p>
          <div class="row"><button class="secondary" @click="keep(describe(draft, replacing.text)); replacing = null">Remplacer</button><button class="secondary" @click="replacing = null">Garder la description</button></div></div>
        <div class="row"><button class="primary" :disabled="action !== 'ready' || reading || sending" :aria-describedby="why ? 'pourquoi-publier' : undefined" @click="openSheet">Publier…</button>
          <button v-if="!poster" class="secondary" :disabled="!draft.items.length && !draft.description" @click="keep(emptyDraft()); replacing = null">Vider</button></div>
        <p v-if="why" id="pourquoi-publier" class="why">{{ why }}</p>
        <p v-if="line" class="why" role="alert">{{ line }}</p>
        </div>
      </div>
      <template v-if="poster">
        <p v-if="draftCount" class="help">Votre publication en préparation ({{ posterCount(draftCount) }}) est gardée. <a href="#publier">La voir</a></p>
        <a class="way" href="#publier">Publier plusieurs affiches</a>
      </template>
    </section>

    <section v-if="connected && !poster && !unread" class="group" aria-labelledby="titre-confirmees">
      <h2 id="titre-confirmees">Affiches confirmées</h2>
      <p v-if="gridLine" class="why">{{ gridLine }}</p>
      <p v-if="!grid.length" class="help">Aucune affiche confirmée au format Publication pour le moment.</p>
      <ul v-else class="tiles">
        <li v-for="item in grid" :key="item.id"><button type="button" class="tile" :aria-pressed="draft.items.includes(item.id)"
          :disabled="!draft.items.includes(item.id) && (full || item.last?.status === 'unknown')" @click="keep(toggle(draft, item.id, limit))">
          <img v-if="item.thumbnail_url" :src="item.thumbnail_url" width="150" height="188" alt="" loading="lazy" /><span v-else class="blank" aria-hidden="true" />
          <span v-if="draft.items.includes(item.id)" class="number" aria-hidden="true">{{ draft.items.indexOf(item.id) + 1 }}</span>
          <strong translate="no">{{ titleOf(item) }}</strong>
          <span v-if="item.last?.status === 'unknown'" class="mark">Résultat inconnu : répondez plus bas</span>
          <span v-else-if="item.published_at" class="mark">Publiée le {{ day(item.published_at) }}</span>
        </button></li>
      </ul>
      <p v-if="gridNext" class="more"><button type="button" :disabled="gridLoading || reading" :aria-busy="gridLoading || undefined" @click="moreGrid">Voir plus</button></p>
      <div v-if="left" class="left-out"><p>{{ left.lead }}</p><ul><li v-for="entry in left.lines" :key="entry.reason"><a href="#affiches">{{ entry.text }}</a></li></ul></div>
    </section>

    <!-- Always shown: an unknown post must be answerable with no Page connected (after a restore every connection is gone). -->
    <section class="group" aria-labelledby="titre-publications">
      <h2 id="titre-publications">Publications</h2>
      <p v-if="checking" class="why" role="status">{{ LOST }}</p>
      <p v-if="postsLine" class="why" role="alert">{{ postsLine }}</p>
      <p v-if="postsError" class="why" role="alert">{{ postsError }} <button class="text-button" @click="readPosts()">Réessayer</button></p>
      <p v-else-if="!postsRead" role="status">Lecture des publications…</p>
      <p v-else-if="!posts.length" class="help">Aucune publication pour le moment.</p>
      <ol v-if="posts.length" class="posts">
        <li v-for="entry in lines" :key="entry.post.id" :data-post="entry.post.id">
          <img v-if="entry.post.items[0]?.thumbnail_url" :src="entry.post.items[0].thumbnail_url" width="48" height="60" alt="" /><span v-else class="blank" aria-hidden="true" />
          <small><time :datetime="entry.post.sent_at">{{ moment(entry.post.sent_at) }}</time> · <span translate="no">{{ entry.post.page_name }}</span> · {{ entry.count }}</small>
          <span class="said">{{ entry.state }}</span>
          <span v-if="entry.stopping" class="help">Arrêt demandé.</span>
          <span v-if="pollFailed && inFlight(entry.post)" class="help">Lecture interrompue : nouvel essai dans quelques secondes.</span>
          <div v-if="entry.link || entry.ask || entry.stop" class="row">
            <a v-if="entry.link" :href="entry.link.href" target="_blank" rel="noopener">{{ entry.link.label }}</a>
            <button v-if="entry.stop" class="secondary" :disabled="stopping === entry.post.id" @click="stopPost(entry.post)">Arrêter l’envoi</button>
            <template v-if="entry.ask"><button class="secondary" :disabled="answering" @click="sayOutcome(entry.post, true)">Elle est sur ma Page</button><button class="secondary" :disabled="answering" @click="absent = entry.post">Elle n’y est pas</button></template>
          </div>
        </li>
      </ol>
      <p v-if="postsNext" class="more"><button type="button" @click="readPosts(true)">Voir plus</button></p>
      <p class="visually-hidden" role="status">{{ followed }}</p>
    </section>

    <div v-if="sheet" v-modal class="confirm-sheet" role="dialog" aria-modal="true" aria-labelledby="titre-publier-sur" @keydown.esc="sending || closeSheet()" @keydown.tab="keepTab"><div class="confirm">
      <h2 id="titre-publier-sur">Publier sur <span translate="no">{{ sheet.page.name }}</span> ?</h2>
      <ol class="strip" aria-label="Les images, dans l’ordre de la publication">
        <li v-for="(item, index) in sheet.items" :key="item.creation_id"><a :href="item.file" target="_blank" rel="noopener">
          <img :key="item.tries" :src="item.thumb" width="88" height="110" :alt="`Image ${index + 1} : ${item.title}`" @load="item.shot = 'loaded'" @error="item.shot = 'failed'" /></a>
          <span class="number" aria-hidden="true">{{ index + 1 }}</span></li>
      </ol>
      <template v-if="sheet.items.some(item => item.shot === 'failed')"><p class="why" role="alert">Une image n’a pas pu être affichée : elle doit être vue avant d’être publiée.</p><button class="secondary" @click="retryShots">Réessayer</button></template>
      <p class="label">Description</p>
      <p class="sent-text">{{ sheet.description || 'Sans description.' }}</p>
      <p v-if="sheet.already" class="why">{{ sheet.already }}</p>
      <p v-if="sheet.line" class="why" role="alert">{{ sheet.line }}</p>
      <p v-else-if="sheetWhy" class="why">{{ sheetWhy }}</p>
      <div class="row"><button class="primary" :disabled="sending || !shown || running || checking" :aria-busy="sending || undefined" @click="publishNow">{{ sheet.label }}</button><button class="secondary" data-focus :disabled="sending" @click="closeSheet">Annuler</button></div>
    </div></div>
    <div v-if="absent" v-modal class="confirm-sheet" role="dialog" aria-modal="true" aria-labelledby="titre-absente" @keydown.esc="answering || (absent = null)" @keydown.tab="keepTab"><div class="confirm">
      <h2 id="titre-absente">Elle n’est pas sur votre Page ?</h2><p>Si elle apparaît plus tard, publier à nouveau créera un doublon.</p>
      <div class="row"><button class="primary" :disabled="answering" @click="sayOutcome(absent, false)">Elle n’y est pas</button><button class="secondary" data-focus :disabled="answering" @click="absent = null">Annuler</button></div>
    </div></div>
    </template>
  </section>
</template>

<style scoped>
.shop-publish { padding: clamp(18px, 4vw, 46px) 0 30px; overflow-wrap: anywhere }
.shop-publish > .group, .shop-publish > .refusal { margin-top: 20px }
.group { display: grid; gap: 12px }
.group > :is(h2, p, label, figure, ol, ul) { margin: 0 }
.group label { margin: 0 }
.refusal { display: grid; gap: 8px; justify-items: start; color: var(--warn) }
.refusal p { margin: 0; font-weight: 600 }
.refusal a { display: inline-flex; align-items: center; min-height: 44px; font-weight: 600 }
.why.lead { text-align: left }
.group .why, .group .row { margin-top: 0 }
.label { font-size: 13px; font-weight: 650; color: var(--muted) }
/* A number on a chosen poster: the disc of a chosen style (DESIGN.md « Style tile »), with its place in the post. */
.number { display: inline-grid; place-items: center; flex: none; min-width: 24px; height: 24px; padding: 0 6px; border-radius: 999px; background: var(--invert); color: var(--invert-ink); font-size: 12.5px; font-weight: 700 }
.blank { display: block; background: var(--raised); border-radius: 4px }
.chosen, .posts, .tiles, .strip, .left-out ul { list-style: none; margin: 0; padding: 0 }
.chosen li, .posts li { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: 6px 14px; align-items: start; padding: 12px 0 }
.chosen li + li, .posts li + li { border-top: 1px solid var(--line) }
.chosen :is(img, .blank), .posts :is(img, .blank) { width: 48px; height: 60px; object-fit: contain; border-radius: 4px; grid-row: span 4 }
.chosen .name { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0 }
.chosen .moves { display: flex; flex-wrap: wrap; gap: 8px }
.describe, .fields { display: grid; gap: 12px; min-width: 0 }
.fields > :is(p, label) { margin: 0 }
.group:has(.single) .describe { grid-template-columns: 200px minmax(0, 1fr); gap: 24px; align-items: start }
@media (width <= 720px) { .group:has(.single) .describe { grid-template-columns: minmax(0, 1fr) } }
.single { display: grid; gap: 8px; justify-items: start; margin: 0 }
.single img { width: min(100%, 200px); height: auto; border-radius: 5px; box-shadow: var(--poster-shadow) }
.single figcaption { font-weight: 700 }
.way { display: inline-flex; align-items: center; min-height: 44px; justify-self: start; font-weight: 600 }
/* The grid: a tap adds the poster at the end or takes it out; chosen, the selection ring of a chosen style and its number. */
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(150px, calc(50% - 6px)), 1fr)); gap: 12px }
.tile { position: relative; display: grid; gap: 6px; align-content: start; justify-content: stretch; width: 100%; height: 100%; min-height: 0; padding: 6px 6px 10px; border: 1px solid var(--line); border-radius: 18px; background: var(--surface); text-align: left; overflow-wrap: anywhere }
.tile[aria-pressed=true] { box-shadow: 0 0 0 2px var(--ground), 0 0 0 5px var(--text) }
.tile:focus-visible { outline-offset: 6px }  /* outside the selection ring, as a style tile's */
.tile :is(img, .blank) { width: 100%; height: auto; aspect-ratio: 4 / 5; object-fit: contain; border-radius: 12px }
.tile strong { padding: 0 4px }
.tile .number { position: absolute; top: 12px; left: 12px }
.tile .mark { padding: 0 4px; font-size: 12.5px; font-weight: 600; color: var(--muted) }
.tile:disabled .mark { color: var(--faint) }
.left-out { display: grid; gap: 4px; color: var(--muted) }
.left-out p { margin: 0 }
.left-out a { display: inline-flex; align-items: center; min-height: 44px }
.posts small { color: var(--muted) }
.posts .said { font-weight: 600 }
.posts .row { align-items: center }
.posts .row a, .confirm a { display: inline-flex; align-items: center; min-height: 44px; color: var(--text) }
/* The sheet's strip scrolls sideways inside the sheet, never the page. */
.strip { display: flex; gap: 10px; overflow-x: auto; overscroll-behavior-x: contain; padding: 4px 2px 8px }
.strip li { position: relative; flex: none }
.strip img { display: block; width: 88px; height: 110px; object-fit: contain; border-radius: 5px; background: var(--raised) }
.strip .number { position: absolute; top: 6px; left: 6px; pointer-events: none }
.sent-text { max-height: 30vh; overflow: auto; padding: 10px 14px; border: 1px solid var(--line); border-radius: var(--field); background: var(--surface); color: var(--text); white-space: pre-wrap }
</style>
