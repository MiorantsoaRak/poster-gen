<script setup lang="ts">
// The operator's dashboard (D-ADMIN-005): sign-in, the shops, one shop's money and access, the service, the payments. The
// view comes from the address's hash (admin.ts route). A 401 shows the sign-in form in place of the view, which stays
// mounted with what was typed; never with a password the server made or a shop's data (leave).
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import Confirm, { type Question } from './Confirm.vue'
import Payments from './Payments.vue'
import Service from './Service.vue'
import { AdminError, call, newEpoch } from './adminApi'
import {
  CAP_WARNING, PENDING, UNSTORED, WHOLE, concession, correctionRequest, count, describe, dollars, grantRequest, grouped,
  headroom, inHistory, moveRequest, newCorrection, newGrant, newMove, route as read, recorded, release, repayment, sentence,
  settle, signed, stored, uncertain, when,
  type CorrectionDraft, type Existing, type Form, type GrantDraft, type Headroom, type Item, type JobItem, type Kept, type MoveDraft, type Pending,
} from './admin'

interface Shop {
  id: number; identifier: string; name: string | null; state: 'active' | 'suspended'; has_password: boolean; created_at: string
  available: number; pending: number; posters: number; last_poster_at: string | null; sessions: number
}
interface Limits { day_spent_micros: number; day_limit_micros: number; reads_today: number; reads_limit: number }
interface Session { authenticated: boolean; configured?: boolean; actor?: string; expires_at?: string }

const session = ref<Session>(), starting = ref('')  // undefined until the server has said; `starting` why it has not
const signedIn = computed(() => !!session.value?.authenticated)
const outdated = ref('')  // bundle_outdated: the page must be reloaded
const route = ref(read(location.hash))
const heading = ref<HTMLElement>(), passwordField = ref<HTMLInputElement>(), panel = ref<HTMLElement>(), newShop = ref<HTMLDetailsElement>()
const confirm = ref<InstanceType<typeof Confirm>>()

const signing = ref(false), signingOut = ref(false), signInMessage = ref(''), headerMessage = ref('')
const shops = ref<Shop[]>(), listMessage = ref('')
const blank = () => ({ identifier: '', name: '', welcome: '5' })
const draft = ref(blank()), creating = ref(false), createMessage = ref('')
const one = ref<{ shop: Shop; limits: Limits }>(), shopMessage = ref('')
const here = (id: number) => route.value.view === 'shop' && route.value.id === id
const current = computed(() => one.value && here(one.value.shop.id) ? one.value : undefined)
const busy = ref(false)
// An access action's word (its result or its refusal) belongs to its shop and shows on that shop's screen alone: an answer
// that arrives after the operator moved to another shop never reads as that shop's.
const note = ref<{ shop: number; text: string; refused: boolean }>()
const own = computed(() => note.value && note.value.shop === current.value?.shop.id ? note.value : undefined)
// A password the server made, shown once (R-ADMIN-002): in memory until closed, the session's end or the page is left;
// never stored.
const shown = ref<{ identifier: string; password: string }>(), copied = ref('')

// Money (D-ADMIN-005). A confirmed request is kept from before it leaves until a definite answer, in memory and in
// localStorage, one per shop; while a shop has one, its money forms wait for it (« Send again », « Discard »).
interface Balance { available: number; pending: number }
const store = () => localStorage
const kept = reactive<Pending>(stored(store))
// Some private modes refuse storage: a kept request then lives in this page only, and the form says so.
const storable = (() => { try { return !!store() } catch { return false } })()
// Shops whose kept request storage refused: this page's only, so another tab's storage says nothing of it.
const memoryOnly = reactive(new Set<number>())
const sending = reactive(new Set<number>())  // shops with a money request in flight: one at a time
const why = reactive<Record<number, string>>({})  // what the kept request's last answer said; memory only
const UNANSWERED = 'No definite answer has reached this page. It may have been recorded. Sending the same request again is safe: it is written once.'
const asking = ref(false)
// The three forms of the shop on screen; their references are made once, when the shop's screen opens with new drafts.
const drafts = ref<{ shop: number; grant: GrantDraft; correction: CorrectionDraft; move: MoveDraft }>()
const forms = computed(() => drafts.value && drafts.value.shop === current.value?.shop.id ? drafts.value : undefined)
const pendingHere = computed(() => current.value ? kept[current.value.shop.id] : undefined)
const others = computed(() => (shops.value ?? []).filter(shop => shop.id !== current.value?.shop.id))
const correctionFold = ref<HTMLDetailsElement>(), reasonField = ref<HTMLTextAreaElement>(), payments = ref<InstanceType<typeof Payments>>()
const service = ref<InstanceType<typeof Service>>(), purchaseDraft = ref<string>()  // the Service screen's text area
// A money answer belongs to its shop and its form, as an access action's note does.
const result = ref<{ shop: number; form: Form; lines: string[]; refused: boolean; warning?: string }>()
const said = (form: Form, refused: boolean) => {
  const answer = result.value
  return answer && answer.form === form && answer.refused === refused && answer.shop === current.value?.shop.id ? answer : undefined
}
const say = (shop: number, form: Form, lines: string[], refused = false, warning?: string) => { result.value = { shop, form, lines, refused, warning } }
const history = ref<{ shop: number; items: Item[]; next: string | null }>(), historyMessage = ref<{ shop: number; text: string }>(), older = ref(false)
const shopHistory = computed(() => history.value && history.value.shop === current.value?.shop.id ? history.value : undefined)
const find = (id: number) => shops.value?.find(shop => shop.id === id) ?? (one.value?.shop.id === id ? one.value.shop : undefined)
const named = (id: number) => find(id)?.identifier ?? `shop ${id}`

/** Leaving an authentication state, by a sign-out or a session lost: a new epoch (adminApi), so that no answer to an
 *  earlier request lands; the password shown, an open question, the shops' data and the messages go at once. What was
 *  typed in the new-shop form is no secret: after a lost session it stays for the sign-in that follows. A kept money
 *  request stays: its answer, if it ever comes, is dropped, so it is unresolved and is sent again after the sign-in. */
function leave(all: boolean) {
  newEpoch()
  confirm.value?.dismiss()
  session.value = { authenticated: false, configured: true }
  shown.value = undefined; shops.value = undefined; one.value = undefined; note.value = undefined
  history.value = undefined; historyMessage.value = undefined; result.value = undefined
  copied.value = listMessage.value = createMessage.value = shopMessage.value = headerMessage.value = ''
  creating.value = busy.value = asking.value = older.value = false
  sending.clear()
  if (all) { draft.value = blank(); drafts.value = undefined; purchaseDraft.value = undefined }
}

/** What a refused request says. A 401 is shown on the sign-in form, which takes the view's place; a defect is not an
 *  answer and is not turned into one. */
function failure(error: unknown): string {
  if (!(error instanceof AdminError)) throw error
  if (error.code === 'unauthenticated') {
    leave(false)
    signInMessage.value = sentence(error)
    void nextTick(() => passwordField.value?.focus())
    return ''
  }
  if (error.code === 'bundle_outdated') outdated.value = sentence(error)
  return sentence(error)
}

async function start() {
  starting.value = ''
  try { session.value = await call<Session>('/api/admin/session') }
  catch (error) { starting.value = failure(error); return }
  await load()
}
async function load() {
  if (!signedIn.value) return
  const at = route.value
  if (at.view === 'shop') {
    if (drafts.value?.shop !== at.id) drafts.value = { shop: at.id, grant: newGrant(), correction: newCorrection(), move: newMove() }
    await Promise.all([loadShop(at.id), loadHistory(at.id), loadShops()])  // the shops: the move's destinations
  } else if (at.view === 'shops') await loadShops()
  else if (at.view === 'service') await service.value?.read()
  else await payments.value?.read()  // on its first opening each reads itself, once mounted
}
async function loadShops() {
  try { shops.value = (await call<{ items: Shop[] }>('/api/admin/shops')).items; listMessage.value = '' }
  catch (error) { listMessage.value = failure(error) }
}
async function loadShop(id: number) {
  try {
    const answer = await call<{ shop: Shop; limits: Limits }>(`/api/admin/shops/${id}`)
    if (here(id)) { one.value = answer; shopMessage.value = '' }
  } catch (error) {
    const said = failure(error)
    if (here(id)) shopMessage.value = said
  }
}
/** The shop's history, newest first; `before`: the page after the one shown (« Older »). */
async function loadHistory(id: number, before?: string) {
  try {
    const page = await call<{ items: Item[]; next_cursor: string | null }>(`/api/admin/shops/${id}/history${before ? `?before=${encodeURIComponent(before)}` : ''}`)
    if (!here(id)) return
    historyMessage.value = undefined
    if (!before) {
      history.value = { shop: id, items: page.items, next: page.next_cursor }
      resolve(id, page.items)
    } else if (history.value?.shop === id && history.value.next === before)  // still after the page shown
    { history.value = { shop: id, items: [...history.value.items, ...page.items], next: page.next_cursor }; resolve(id, page.items) }
  } catch (error) {
    const said = failure(error)
    if (here(id)) historyMessage.value = { shop: id, text: said }
  }
}
async function olderPage() {
  const page = shopHistory.value
  if (!page?.next || older.value) return
  older.value = true
  await loadHistory(page.shop, page.next)
  older.value = false
}

async function signIn() {
  const field = passwordField.value!
  // Not while a sign-out is out: its answer deletes the cookie, and could delete the new session's.
  if (signing.value || signingOut.value) return
  signing.value = true; signInMessage.value = ''
  let answer: Session
  try { answer = await call<Session>('/api/admin/session', 'POST', { password: field.value }) }
  catch (error) { signInMessage.value = failure(error); return }
  finally {
    field.value = ''  // the password lives in the field until its request has left, never longer
    signing.value = false
  }
  newEpoch()  // a new authentication state: nothing asked before it lands in it
  session.value = answer
  await nextTick(); heading.value?.focus()
  await load()
}
async function signOut() {
  if (signingOut.value) return
  signingOut.value = true
  leave(true)  // at once, whatever the answer: nothing of this session stays on the page
  signInMessage.value = ''
  try { await call('/api/admin/session', 'DELETE') }
  catch (error) { await unsure(error) }
  finally { signingOut.value = false }
  await nextTick(); passwordField.value?.focus()
}
/** « End all operator sessions » answered (Service): the server ended this session with the others and deleted its
 *  cookie, so the page is signed out as by « Sign out ». */
async function ended() {
  leave(true)
  signInMessage.value = 'Every operator session has ended, this device’s too. Sign in again.'
  await nextTick(); passwordField.value?.focus()
}
const ask = (question: Question) => confirm.value!.ask(question)
/** A sign-out refused or unanswered: whether the server ended the session is not known here, so the server is asked.
 *  Until it says, and if it cannot, the page stays signed out. */
async function unsure(error: unknown) {
  if (!(error instanceof AdminError)) throw error
  let now: Session
  try { now = await call<Session>('/api/admin/session') }
  catch (again) {
    if (!(again instanceof AdminError)) throw again
    signInMessage.value = `The sign-out’s outcome is unknown. ${sentence(error)} Reload the page to know whether this browser is still signed in.`
    return
  }
  if (!now.authenticated) {
    signInMessage.value = 'The sign-out’s answer was lost; the server then confirmed that this browser is signed out.'
    return
  }
  session.value = now
  headerMessage.value = `Not signed out. ${sentence(error)} Try again.`
  await load()
}

function navigate() {
  route.value = read(location.hash)
  shopMessage.value = ''
  void nextTick(() => heading.value?.focus())
  void load()
}
// Fresh data when the tab comes back (D-ADMIN-005); a session ended meanwhile answers 401 and shows the sign-in form.
const visible = () => { if (document.visibilityState === 'visible') void load() }
// Another tab of this browser kept or resolved a money request (D-ADMIN-005, « Two tabs »).
function shared(event: StorageEvent) {
  if (event.key !== null && !event.key.startsWith(PENDING)) return
  const now = stored(store)
  for (const shop of Object.keys(kept).map(Number)) if (!(shop in now) && !memoryOnly.has(shop)) delete kept[shop]
  for (const request of Object.values(now)) if (!memoryOnly.has(request.shop)) kept[request.shop] = request
}
onMounted(() => {
  addEventListener('hashchange', navigate); addEventListener('storage', shared); document.addEventListener('visibilitychange', visible)
  void start()
})
onUnmounted(() => {
  removeEventListener('hashchange', navigate); removeEventListener('storage', shared); document.removeEventListener('visibilitychange', visible)
})

async function show(identifier: string, password: string) {
  shown.value = { identifier, password }; copied.value = ''
  await nextTick(); panel.value?.focus()
}
async function copy() {
  try { await navigator.clipboard.writeText(shown.value!.password); copied.value = 'Copied.' }
  catch { copied.value = 'This browser did not allow the copy: select the password and copy it by hand.' }
}
const reload = () => location.reload()
function closeShown() { shown.value = undefined; heading.value?.focus() }

async function create() {
  if (creating.value) return
  creating.value = true; createMessage.value = ''
  const { identifier, name, welcome } = draft.value
  try {
    const made = await call<{ shop: Shop; password: string }>('/api/admin/shops', 'POST', { identifier, name: name.trim() || null, welcome: Number(welcome) })
    draft.value = blank()
    if (newShop.value) newShop.value.open = false
    await show(made.shop.identifier, made.password)
  } catch (error) {
    const said = failure(error)
    if (!signedIn.value) return  // the session ended: the sign-in form says so, and what was typed stays
    createMessage.value = error instanceof AdminError && uncertain(error)
      ? `${said} The shop may have been created: the list below was read again. If it is there, its password is lost: open it and set a new password.`
      : said
  }
  creating.value = false
  await load()
}

/** One access action of the shop on screen, confirmed first; nothing is sent on Cancel or Esc. */
async function act(question: Question, path: string, method: string, done: (answer: any) => Promise<string> | string) {
  const shop = current.value?.shop
  if (!shop || busy.value || !await confirm.value!.ask(question)) return
  busy.value = true; note.value = undefined
  const say = (text: string, refused: boolean) => { note.value = { shop: shop.id, text, refused } }
  try { say(await done(await call(`/api/admin/shops/${shop.id}/${path}`, method)), false) }
  catch (error) {
    const said = failure(error)
    if (!signedIn.value) return
    say(error instanceof AdminError && uncertain(error) ? `${said} It may have been done: the shop was read again.` : said, true)
  }
  busy.value = false
  await load()
}
const sessionsEnd = (n: number) => n === 1 ? 'Its 1 session ends.' : `Its ${n} sessions end.`
function setPassword(shop: Shop) {
  return act({ title: 'Set a new password?', text: `A new password for ${shop.identifier}. ${sessionsEnd(shop.sessions)}`, action: 'Set a new password' },
    'password', 'POST', async (answer: { password: string; sessions_ended: number }) => {
      await show(shop.identifier, answer.password)
      return `New password set; ${count(answer.sessions_ended, 'session')} ended.`
    })
}
function endSessions(shop: Shop) {
  return act({ title: 'End its sessions?', text: `${shop.identifier} is signed out everywhere. ${sessionsEnd(shop.sessions)} Its owner signs in again with the same password.`, action: 'End its sessions' },
    'sessions', 'DELETE', (answer: { ended: number }) => `${count(answer.ended, 'session')} ended.`)
}
function suspendOrEnable(shop: Shop) {
  if (shop.state === 'active')
    return act({ title: 'Suspend this shop?', text: `${shop.identifier} cannot sign in. Its sessions stop working. Its queued images are cancelled and their credits come back. An image being made finishes.`, action: 'Suspend' },
      'suspend', 'POST', (answer: { changed: boolean; cancelled_jobs: number }) =>
        answer.changed ? `Suspended; ${count(answer.cancelled_jobs, 'queued image')} cancelled, credits back.` : 'It was already suspended: nothing changed.')
  return act({ title: 'Enable this shop?', text: `${shop.identifier} can sign in again, and its sessions work again.`, action: 'Enable' },
    'enable', 'POST', (answer: { changed: boolean }) => answer.changed ? 'Enabled.' : 'It was already enabled: nothing changed.')
}

/** A form's request, frozen when its button is pressed, confirmed, then sent exactly as shown. Cancel or Esc sends
 *  nothing and leaves the form, its reference included, as it was. */
async function confirmAndSend(make: (shop: number) => Kept, title: string, action: string) {
  const shop = current.value?.shop
  if (!shop || asking.value || kept[shop.id]) return
  const request = make(shop.id)
  asking.value = true
  const yes = await confirm.value!.ask({ title, text: describe(request, find), action })
  asking.value = false
  if (yes) await send(request)
}
const submitGrant = () => confirmAndSend(id => grantRequest(id, forms.value!.grant), 'Grant credits?', 'Grant')
const submitMove = () => reasoned(forms.value!.move.note, 'move') && confirmAndSend(id => moveRequest(id, forms.value!.move), 'Move this payment?', 'Move')
const submitCorrection = () => reasoned(forms.value!.correction.note, 'correction') && confirmAndSend(id => correctionRequest(id, forms.value!.correction), 'Write this correction?', 'Correct')
/** `required` lets a reason of spaces through; the server would refuse it as a field. */
function reasoned(note: string, form: Form) {
  if (!note.trim()) say(current.value!.shop.id, form, ['Write the reason: it is kept with the line.'], true)
  return !!note.trim()
}
const again = (request: Kept) => { if (!asking.value) void send(request) }

/** Sends a confirmed request, or the kept one again, and reads its answer by the design's state machine (admin.ts
 *  settle and outcome). One in flight per shop. */
async function send(request: Kept) {
  const shop = request.shop
  if (sending.has(shop)) return
  sending.add(shop); delete why[shop]
  if (result.value?.shop === shop) result.value = undefined
  const settled = await settle(kept, store, request, sent => call(sent.path, 'POST', sent.body), 
    // Once it is admitted only: a 'busy' answer leaves the mark of the request that still lives here.
    isStored => { if (isStored) memoryOnly.delete(shop); else memoryOnly.add(shop) })
  sending.delete(shop)
  if (!kept[shop]) memoryOnly.delete(shop)
  if (settled.outcome === 'busy') {
    say(shop, request.form, ['This shop already has a request with no definite answer: nothing was sent. Send that one again or discard it first.'], true)
    return
  }
  const error = settled.error!
  if (settled.outcome === 'done') answered(request, settled.answer)
  else if (settled.outcome === 'recorded') resolved(request, error.existing as Existing | undefined, error)
  else if (settled.outcome === 'refused') refused(request, error)
  else if (settled.outcome === 'resend') {
    why[shop] = (error.status === 401 ? 'Not sent: your session had ended. Send it again.' : 'Not sent: this page was out of date. Reload it, then send it again.')
    failure(error)  // a 401: the sign-in form in place; bundle_outdated: the reload banner
  } else why[shop] = `${sentence(error)} It may have been recorded: the history is read again below. Sending the same request again is safe: it is written once.`
  await load()
}
/** A definite answer: the form that made the request starts again, with a new reference. */
function renew(request: Kept) {
  const shop = drafts.value
  if (shop?.shop !== request.shop) return
  if (request.form === 'grant') shop.grant = newGrant()
  else if (request.form === 'correction') shop.correction = newCorrection()
  else shop.move = newMove()
}
const balance = (now: Balance) => `available ${grouped(now.available)} · en attente ${grouped(now.pending)}`
function answered(request: Kept, answer: any) {
  if (request.form === 'grant') {
    const room: Headroom = answer.headroom
    say(request.shop, 'grant', [`Granted: line ${answer.line}. Balance: ${balance(answer.balance)}.`, headroom(room)], false, room.warning ? CAP_WARNING : undefined)
  } else if (request.form === 'correction') say(request.shop, 'correction', [`Corrected: line ${answer.line}. Balance: ${balance(answer.balance)}.`])
  else {
    const from = named(request.body.from_shop), to = named(request.body.to_shop)
    say(request.shop, 'move', [`Moved: line ${answer.lines[0]} takes the payment back from ${from}, line ${answer.lines[1]} grants it to ${to}.`,
      `${from}: ${balance(answer.balances.from)}. ${to}: ${balance(answer.balances.to)}.`])
  }
  renew(request)
}
/** Already recorded, by the server's answer or by the shop's history: compared with what was sent. */
function resolved(request: Kept, line: Existing | undefined, error?: AdminError) {
  const reading = line ? recorded(request, line, find) : { text: error ? sentence(error) : '', same: false }
  say(request.shop, request.form, [reading.text], !reading.same)
  renew(request)
}
function refused(request: Kept, error: AdminError) {
  // Refused because the source spent some of the payment's credits (credits.move's own sentence): the right shop is
  // served by an offered grant under the concession reference, filled in on its screen, for the operator to read.
  if (request.form === 'move' && error.code === 'operator_refused' && / credits left of the payment's /.test(error.message)) {
    const to = request.body.to_shop, ref = concession(request.body.ref)
    drafts.value = { shop: to, grant: { ...newGrant(), origin: 'offered', offeredRef: ref }, correction: newCorrection(), move: newMove() }
    say(to, 'grant', [`The move from ${named(request.shop)} was refused: ${error.message}.`,
      `To serve ${named(to)} anyway, the form below holds an offered grant under the reference ${ref}, with no note: type the credits, read it, then grant it.`], true)
    location.hash = `#/shops/${to}`
    route.value = { view: 'shop', id: to }  // now: the read that follows this answer must not open the source's drafts
    return
  }
  say(request.shop, request.form, [sentence(error)], true)
}
/** A kept request whose line the shop's history holds is resolved as recorded; not while its own answer is awaited,
 *  which decides. */
function resolve(id: number, items: Item[]) {
  const request = kept[id]
  const line = request && !sending.has(id) ? inHistory(request, items) : undefined
  if (!request || !line) return
  release(kept, store, request); delete why[id]; memoryOnly.delete(id)
  resolved(request, { ...line, shop_id: id, identifier: named(id), moved_to: null })
}
async function discard(request: Kept) {
  if (sending.has(request.shop) || asking.value) return
  asking.value = true
  const yes = await confirm.value!.ask({ title: 'Discard this request?', text: 'If the first send was recorded, a new one writes a second line. Read the history first.', action: 'Discard' })
  asking.value = false
  if (!yes || sending.has(request.shop)) return
  release(kept, store, request); delete why[request.shop]; memoryOnly.delete(request.shop)
}
/** « Repay » on a job of the history: the correction form filled from it, never typed by hand. */
async function repay(job: JobItem) {
  const shop = forms.value
  if (!shop || kept[shop.shop]) return
  shop.correction = { ...newCorrection(), mode: 'repay', job: job.id }
  correctionFold.value!.open = true
  await nextTick(); reasonField.value?.focus()
}
</script>

<template>
  <p v-if="outdated" class="banner" role="alert">{{ outdated }} <button @click="reload">Reload</button></p>

  <main v-if="!session" class="page">
    <h1 class="marked">Doka Studio · Operator</h1>
    <p role="status">{{ starting || 'Loading…' }}</p>
    <button v-if="starting" @click="start">Try again</button>
  </main>

  <main v-else-if="!signedIn" class="page">
    <h1 class="marked">Doka Studio · Operator</h1>
    <p v-if="session.configured === false" class="note">No operator password is set. On the server run: <code>python -m affiche.shops operator-password</code> (deploy/README.md, « Operator dashboard »).</p>
    <form class="stack" @submit.prevent="signIn">
      <!-- For password managers: the one account's name. -->
      <input type="text" name="username" autocomplete="username" value="operator" hidden>
      <label for="password">Operator password</label>
      <input id="password" ref="passwordField" type="password" name="password" autocomplete="current-password" required maxlength="1024" autocapitalize="none" spellcheck="false" enterkeyhint="go">
      <button class="primary" :aria-disabled="signing || signingOut">Sign in</button>
      <p class="refusal" role="alert">{{ signInMessage }}</p>
    </form>
  </main>

  <div v-show="signedIn">
    <header class="bar">
      <p class="brand marked">Doka Studio · Operator</p>
      <nav aria-label="Dashboard">
        <a href="#/shops" :aria-current="route.view === 'shops' ? 'page' : undefined">Shops</a> ·
        <a href="#/service" :aria-current="route.view === 'service' ? 'page' : undefined">Service</a> ·
        <a href="#/money" :aria-current="route.view === 'money' ? 'page' : undefined">Money</a>
      </nav>
      <span class="actor">{{ session?.actor }}</span>
      <button :aria-disabled="signingOut" @click="signOut">Sign out</button>
      <p class="refusal" role="alert">{{ headerMessage }}</p>
    </header>

    <section v-if="shown" ref="panel" class="shown" tabindex="-1" aria-labelledby="shown-password">
      <p id="shown-password">Password for <strong>{{ shown.identifier }}</strong>, shown once: <code class="secret">{{ shown.password }}</code></p>
      <p>It will not be shown again. Give it to the owner in person.</p>
      <div class="actions"><button class="primary" @click="copy">Copy</button><button @click="closeShown">Close</button></div>
      <p role="status">{{ copied }}</p>
    </section>

    <main v-if="route.view === 'shops'" class="page">
      <h1 ref="heading" tabindex="-1">Shops</h1>
      <details ref="newShop" class="fold">
        <summary>New shop</summary>
        <form class="stack" @submit.prevent="create">
          <label for="identifier">Identifier</label>
          <input id="identifier" v-model="draft.identifier" required maxlength="64" autocomplete="off" autocapitalize="none" spellcheck="false" aria-describedby="identifier-help">
          <small id="identifier-help">3 to 32 letters or digits; case, accents, spaces and punctuation do not count. The owner signs in with it.</small>
          <label for="name">Name (optional)</label>
          <input id="name" v-model="draft.name" maxlength="160" autocomplete="off">
          <label for="welcome">Welcome credits</label>
          <input id="welcome" v-model="draft.welcome" required inputmode="numeric" pattern="[0-9]{1,9}" autocomplete="off">
          <button class="primary" :aria-disabled="creating">Create the shop</button>
          <p class="refusal" role="alert">{{ createMessage }}</p>
        </form>
      </details>
      <p class="refusal" role="alert">{{ listMessage }}</p>
      <table v-if="shops?.length" class="shops">
        <thead><tr><th>Identifier</th><th>Name</th><th>State</th><th>Available</th><th lang="fr">En attente</th><th>Posters</th><th>Last poster</th><th>Sessions</th></tr></thead>
        <tbody>
          <tr v-for="shop in shops" :key="shop.id">
            <td><a :href="`#/shops/${shop.id}`">{{ shop.identifier }}</a><strong v-if="kept[shop.id]"> · unresolved request</strong></td>
            <td data-label="Name">{{ shop.name ?? '—' }}</td>
            <td data-label="State">{{ shop.state }}<template v-if="!shop.has_password"> · no password</template></td>
            <td data-label="Available">{{ shop.available }}</td>
            <td data-label="En attente">{{ shop.pending }}</td>
            <td data-label="Posters">{{ shop.posters }}</td>
            <td data-label="Last poster">{{ shop.last_poster_at?.slice(0, 10) ?? '—' }}</td>
            <td data-label="Sessions">{{ shop.sessions }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="shops">No shop yet.</p>
    </main>

    <main v-else-if="route.view === 'money'" class="page">
      <h1 ref="heading" tabindex="-1">Money</h1>
      <Payments v-if="signedIn" ref="payments" :failure="failure" />
    </main>

    <main v-else-if="route.view === 'service'" class="page">
      <h1 ref="heading" tabindex="-1">Service</h1>
      <Service v-if="signedIn" ref="service" v-model:draft="purchaseDraft" :failure="failure" :ask="ask" :ended="ended" :reload="load" />
    </main>

    <main v-else class="page">
      <p><a href="#/shops">← Shops</a></p>
      <h1 ref="heading" tabindex="-1">{{ current?.shop.identifier ?? 'Shop' }}</h1>
      <p class="refusal" role="alert">{{ shopMessage }}</p>
      <template v-if="current">
        <p class="name">{{ current.shop.name ?? 'No name' }}</p>
        <p>{{ current.shop.state }}<template v-if="!current.shop.has_password"> · no password</template> · {{ count(current.shop.sessions, 'live session') }}</p>
        <p>available {{ grouped(current.shop.available) }} · <span lang="fr">en attente</span> {{ grouped(current.shop.pending) }}</p>

        <section v-if="pendingHere" class="kept" aria-labelledby="kept-title">
          <h2 id="kept-title">A request with no definite answer</h2>
          <p>{{ describe(pendingHere, find) }}</p>
          <p>{{ why[current.shop.id] ?? UNANSWERED }}</p>
          <p v-if="memoryOnly.has(current.shop.id)" class="note">{{ UNSTORED }}</p>
          <div class="actions">
            <button class="primary" :aria-disabled="sending.has(current.shop.id)" @click="again(pendingHere)">Send again</button>
            <button :aria-disabled="sending.has(current.shop.id)" @click="discard(pendingHere)">Discard</button>
          </div>
          <p role="status">{{ sending.has(current.shop.id) ? 'Sending…' : '' }}</p>
        </section>

        <section aria-labelledby="grant-title">
          <h2 id="grant-title">Grant credits</h2>
          <p v-if="!storable" class="note">{{ UNSTORED }}</p>
          <p v-if="pendingHere">Waiting for the request above: send it again or discard it.</p>
          <form v-else-if="forms" class="stack" @submit.prevent="submitGrant">
            <label for="grant-credits">Credits</label>
            <input id="grant-credits" v-model="forms.grant.credits" required inputmode="numeric" :pattern="WHOLE" title="A whole number from 1 to 1 000 000 000, digits only." autocomplete="off">
            <label for="grant-origin">Bought or offered</label>
            <select id="grant-origin" v-model="forms.grant.origin"><option value="bought">Bought: a payment</option><option value="offered">Offered: a gift</option></select>
            <template v-if="forms.grant.origin === 'bought'">
              <label for="grant-amount">Amount received, in ariary</label>
              <input id="grant-amount" v-model="forms.grant.amount" required inputmode="numeric" :pattern="WHOLE" title="A whole number from 1 to 1 000 000 000, digits only." autocomplete="off">
              <label for="grant-method">Method</label>
              <input id="grant-method" v-model="forms.grant.method" required maxlength="40" pattern=".*\S.*" list="methods" autocomplete="off" autocapitalize="none" spellcheck="false">
              <datalist id="methods"><option value="mvola" /><option value="orange" /><option value="airtel" /><option value="cash" /></datalist>
              <label for="grant-ref">The payment’s reference</label>
              <input id="grant-ref" v-model="forms.grant.paymentRef" required maxlength="100" pattern=".*\S.*" autocomplete="off" autocapitalize="none" spellcheck="false" aria-describedby="grant-ref-help">
              <small id="grant-ref-help">Exactly as the payment shows it. Case and spaces do not count, every other character does: MV-123 and MV123 are two references.</small>
            </template>
            <template v-else>
              <label for="grant-ref">Reference</label>
              <input id="grant-ref" v-model="forms.grant.offeredRef" required maxlength="100" pattern=".*\S.*" autocomplete="off" autocapitalize="none" spellcheck="false">
            </template>
            <label for="grant-note">Note (optional)</label>
            <textarea id="grant-note" v-model="forms.grant.note" maxlength="500"></textarea>
            <button class="primary" :aria-disabled="asking">Grant…</button>
          </form>
          <div role="status"><template v-if="said('grant', false)"><p v-for="line in said('grant', false)!.lines" :key="line">{{ line }}</p><p v-if="said('grant', false)!.warning"><strong>{{ said('grant', false)!.warning }}</strong></p></template></div>
          <div class="refusal" role="alert"><p v-for="line in said('grant', true)?.lines" :key="line">{{ line }}</p></div>
        </section>

        <details ref="correctionFold" class="fold">
          <summary>Correction</summary>
          <p v-if="pendingHere">Waiting for the request above: send it again or discard it.</p>
          <form v-else-if="forms" class="stack" @submit.prevent="submitCorrection">
            <template v-if="forms.correction.mode === 'repay'">
              <p>Repay the job <code>{{ forms.correction.job }}</code>: +1 credit, reference <code>{{ repayment(forms.correction.job) }}</code>.</p>
              <button type="button" @click="forms.correction = newCorrection()">Not a repayment</button>
            </template>
            <template v-else>
              <label for="correction-mode">It changes</label>
              <select id="correction-mode" v-model="forms.correction.mode"><option value="credits">Credits</option><option value="amount">A payment’s amount (0 credits)</option></select>
              <label for="correction-sign">Add or take back</label>
              <select id="correction-sign" v-model="forms.correction.sign"><option :value="1">Add</option><option :value="-1">Take back</option></select>
              <template v-if="forms.correction.mode === 'credits'">
                <label for="correction-credits">Credits</label>
                <input id="correction-credits" v-model="forms.correction.credits" required inputmode="numeric" :pattern="WHOLE" title="A whole number from 1 to 1 000 000 000, digits only." autocomplete="off">
                <label for="correction-ref">Reference</label>
                <input id="correction-ref" v-model="forms.correction.madeRef" required maxlength="100" pattern=".*\S.*" autocomplete="off" autocapitalize="none" spellcheck="false">
              </template>
              <template v-else>
                <label for="correction-amount">Ariary</label>
                <input id="correction-amount" v-model="forms.correction.amount" required inputmode="numeric" :pattern="WHOLE" title="A whole number from 1 to 1 000 000 000, digits only." autocomplete="off">
                <label for="correction-ref">The payment’s reference</label>
                <input id="correction-ref" v-model="forms.correction.paymentRef" required maxlength="100" pattern=".*\S.*" autocomplete="off" autocapitalize="none" spellcheck="false">
              </template>
            </template>
            <label for="correction-note">Reason</label>
            <textarea id="correction-note" ref="reasonField" v-model="forms.correction.note" required maxlength="500"></textarea>
            <button class="primary" :aria-disabled="asking">Correct…</button>
          </form>
          <div role="status"><p v-for="line in said('correction', false)?.lines" :key="line">{{ line }}</p></div>
          <div class="refusal" role="alert"><p v-for="line in said('correction', true)?.lines" :key="line">{{ line }}</p></div>
        </details>

        <details class="fold">
          <summary>Move a payment</summary>
          <p v-if="pendingHere">Waiting for the request above: send it again or discard it.</p>
          <form v-else-if="forms" class="stack" @submit.prevent="submitMove">
            <label for="move-ref">The payment’s reference</label>
            <input id="move-ref" v-model="forms.move.ref" required maxlength="100" pattern=".*\S.*" autocomplete="off" autocapitalize="none" spellcheck="false">
            <label for="move-to">To the shop</label>
            <select id="move-to" v-model="forms.move.to" required>
              <option value="">Choose a shop</option>
              <option v-for="shop in others" :key="shop.id" :value="String(shop.id)">{{ shop.identifier }}{{ shop.name ? ` (${shop.name})` : '' }}</option>
            </select>
            <p class="refusal" role="alert">{{ listMessage }}</p>
            <label for="move-note">Reason</label>
            <textarea id="move-note" v-model="forms.move.note" required maxlength="500"></textarea>
            <button class="primary" :aria-disabled="asking">Move…</button>
          </form>
          <div role="status"><p v-for="line in said('move', false)?.lines" :key="line">{{ line }}</p></div>
          <div class="refusal" role="alert"><p v-for="line in said('move', true)?.lines" :key="line">{{ line }}</p></div>
        </details>

        <section aria-labelledby="history-title">
          <h2 id="history-title">History</h2>
          <p class="refusal" role="alert">{{ historyMessage?.shop === current.shop.id ? historyMessage.text : '' }}</p>
          <ul v-if="shopHistory?.items.length" class="lines">
            <li v-for="item in shopHistory.items" :key="`${item.type}${item.id}`">
              <template v-if="item.type === 'line'">
                <p><strong>{{ signed(item.credits) }} {{ Math.abs(item.credits) === 1 ? 'credit' : 'credits' }}</strong> · {{ item.kind }}{{ item.origin ? ` ${item.origin}` : '' }} · line {{ item.id }}</p>
                <p v-if="item.amount_ar !== null">{{ signed(item.amount_ar) }}&nbsp;Ar<template v-if="item.method"> by {{ item.method }}</template></p>
                <p>Reference <code>{{ item.ref }}</code><template v-if="item.job_id"> · job <code>{{ item.job_id }}</code></template></p>
                <p v-if="item.note">{{ item.note }}</p>
                <small>{{ when(item.at) }} · {{ item.actor }}</small>
              </template>
              <template v-else>
                <p><strong>{{ item.kind.replace('_', ' ') }}</strong> · {{ item.status }} · credit {{ item.credit.replace('_', ' ') }}<template v-if="item.repaid_by !== null"> · repaid by line {{ item.repaid_by }}</template></p>
                <p>Poster <code>{{ item.creation_id }}</code></p>
                <p>Job <code class="copyable">{{ item.id }}</code></p>
                <small>{{ when(item.at) }}</small>
                <button v-if="item.status === 'succeeded' && item.repaid_by === null && !pendingHere" @click="repay(item)">Repay</button>
              </template>
            </li>
          </ul>
          <p v-else-if="shopHistory">No line and no image yet.</p>
          <button v-if="shopHistory?.next" :aria-disabled="older" @click="olderPage">Older</button>
        </section>

        <details class="fold">
          <summary>Access</summary>
          <div class="actions">
            <button :aria-disabled="busy" @click="setPassword(current.shop)">Set a new password</button>
            <button :aria-disabled="busy" @click="endSessions(current.shop)">End its sessions</button>
            <button :aria-disabled="busy" @click="suspendOrEnable(current.shop)">{{ current.shop.state === 'active' ? 'Suspend' : 'Enable' }}</button>
          </div>
          <p role="status">{{ own && !own.refused ? own.text : '' }}</p>
          <p class="refusal" role="alert">{{ own?.refused ? own.text : '' }}</p>
        </details>
        <section aria-labelledby="limits">
          <h2 id="limits">Today’s limits (UTC day)</h2>
          <p>Provider spend: {{ dollars(current.limits.day_spent_micros) }} of {{ dollars(current.limits.day_limit_micros) }}</p>
          <p>Messages read: {{ current.limits.reads_today }} of {{ current.limits.reads_limit }}</p>
        </section>
      </template>
    </main>
  </div>

  <Confirm ref="confirm" />
</template>
