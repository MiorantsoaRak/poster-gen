<script setup lang="ts">
// The operator's dashboard (D-ADMIN-005): sign-in, the shops, one shop's access. The view comes from the address's hash
// (admin.ts route). A 401 shows the sign-in form in place of the view, which stays mounted with what was typed; never
// with a password the server made or a shop's data (leave).
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import Confirm, { type Question } from './Confirm.vue'
import { AdminError, call, newEpoch } from './adminApi'
import { count, dollars, route as read, sentence, uncertain } from './admin'

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

/** Leaving an authentication state, by a sign-out or a session lost: a new epoch (adminApi), so that no answer to an
 *  earlier request lands; the password shown, an open question, the shops' data and the messages go at once. What was
 *  typed in the new-shop form is no secret: after a lost session it stays for the sign-in that follows. */
function leave(all: boolean) {
  newEpoch()
  confirm.value?.dismiss()
  session.value = { authenticated: false, configured: true }
  shown.value = undefined; shops.value = undefined; one.value = undefined; note.value = undefined
  copied.value = listMessage.value = createMessage.value = shopMessage.value = headerMessage.value = ''
  creating.value = busy.value = false
  if (all) draft.value = blank()
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
  if (route.value.view === 'shop') await loadShop(route.value.id)
  else await loadShops()
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
onMounted(() => { addEventListener('hashchange', navigate); document.addEventListener('visibilitychange', visible); void start() })
onUnmounted(() => { removeEventListener('hashchange', navigate); document.removeEventListener('visibilitychange', visible) })

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
</script>

<template>
  <p v-if="outdated" class="banner" role="alert">{{ outdated }} <button @click="reload">Reload</button></p>

  <main v-if="!session" class="page">
    <h1>Doka Studio · Operator</h1>
    <p role="status">{{ starting || 'Loading…' }}</p>
    <button v-if="starting" @click="start">Try again</button>
  </main>

  <main v-else-if="!signedIn" class="page">
    <h1>Doka Studio · Operator</h1>
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
      <p class="brand">Doka Studio · Operator</p>
      <nav aria-label="Dashboard"><a href="#/shops" :aria-current="route.view === 'shops' ? 'page' : undefined">Shops</a></nav>
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
            <td><a :href="`#/shops/${shop.id}`">{{ shop.identifier }}</a></td>
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

    <main v-else class="page">
      <p><a href="#/shops">← Shops</a></p>
      <h1 ref="heading" tabindex="-1">{{ current?.shop.identifier ?? 'Shop' }}</h1>
      <p class="refusal" role="alert">{{ shopMessage }}</p>
      <template v-if="current">
        <p class="name">{{ current.shop.name ?? 'No name' }}</p>
        <p>{{ current.shop.state }}<template v-if="!current.shop.has_password"> · no password</template> · {{ count(current.shop.sessions, 'live session') }}</p>
        <p>available {{ current.shop.available }} · <span lang="fr">en attente</span> {{ current.shop.pending }}</p>
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
