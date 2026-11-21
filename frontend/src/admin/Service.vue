<script setup lang="ts">
// The Service screen (D-ADMIN-004, D-ADMIN-005; R-ADMIN-001, R-ADMIN-005, R-ADMIN-006): what runs, the last backup, the
// spend against the cap, the pause, the purchase text as shops read it, the daily limits, and the live operator sessions
// with « End all operator sessions ». One write at a time; an answer that never came is said as such, never as done or
// refused, and the service is read again.
import { onMounted, ref } from 'vue'
import type { Question } from './Confirm.vue'
import { AdminError, call } from './adminApi'
import { CAP_WARNING, dollars, headroom, uncertain, when, type ServiceView as View } from './admin'

type Where = 'pause' | 'text' | 'sessions'

// `reload` reads the Service screen that is on the page now: this one, or the one opened after the operator left and
// came back while a write was out, which must not keep showing the state from before that write.
const props = defineProps<{ failure: (error: unknown) => string; ask: (question: Question) => Promise<boolean>; ended: () => void; reload: () => Promise<void> }>()
// What is typed in the text area: the page keeps it across a lost session (no secret) and drops it at the sign-out.
const draft = defineModel<string>('draft')
const shown = ref<View>(), message = ref(''), busy = ref(false)
const said = ref<{ where: Where; text: string; refused: boolean }>()
const MAYBE: Record<Where, string> = {
  pause: 'It may have been done. Read the state here; « Refresh » reads it again.',
  text: 'It may have been saved. Read the text here; « Refresh » reads it again.',
  sessions: 'They may have ended. « Refresh » reads the service again.',
}

let reads = 0
async function read() {
  const mine = ++reads  // the last read only is shown, in success and in failure
  try {
    const answer = await call<View>('/api/admin/service')
    if (mine !== reads) return
    shown.value = answer; message.value = ''
    draft.value ??= answer.purchase_text.stored ?? ''
  } catch (error) { const text = props.failure(error); if (mine === reads) message.value = text }
}
onMounted(read)
defineExpose({ read })  // read again when the tab comes back (D-ADMIN-005: fresh data, no polling)

/** One write, confirmed first when it asks. `send` says what was done, or nothing when this session is over. */
async function act(where: Where, question: Question | undefined, send: () => Promise<string | void>) {
  if (busy.value || question && !await props.ask(question)) return
  busy.value = true; said.value = undefined
  try {
    try {
      const text = await send()
      if (typeof text !== 'string') return  // « End all »: the page is signed out, nothing more to read
      said.value = { where, text, refused: false }
    } catch (error) {
      const text = props.failure(error)
      if (!text) return  // a 401: the sign-in form says it
      said.value = { where, text: error instanceof AdminError && uncertain(error) ? `${text} ${MAYBE[where]}` : text, refused: true }
    }
    await props.reload()  // busy until the state is read again: a failed read shows its own message above
  } finally { busy.value = false }
}
const at = (where: Where, refused: boolean) => said.value?.where === where && said.value.refused === refused ? said.value.text : ''

const pause = () => act('pause', {
  title: 'Pause new requests?', action: 'Pause',
  text: 'No new request reaches the AI for any shop: images, styles, text proposals, reading messages. What was admitted finishes. Shops can still edit and download.',
}, async () => (await call<{ changed: boolean }>('/api/admin/service/pause', 'POST')).changed ? 'Paused.' : 'It was already paused: nothing changed.')
const resume = () => act('pause', { title: 'Resume the service?', text: 'New requests reach the AI again, for every shop.', action: 'Resume' },
  async () => (await call<{ changed: boolean }>('/api/admin/service/resume', 'POST')).changed ? 'Resumed.' : 'It was not paused: nothing changed.')
const save = () => act('text', undefined, async () => {
  const sent = draft.value ?? ''
  const answer = await call<{ stored: string }>('/api/admin/service/purchase-text', 'PUT', { text: sent })
  if (draft.value === sent) draft.value = answer.stored  // as stored (trimmed), unless typed over meanwhile
  return 'Saved. Every shop reads it from now on.'
})
const endAll = () => act('sessions', { title: 'End all operator sessions?', text: 'Every operator session ends, this device’s too. You will sign in again.', action: 'End all' },
  async () => { await call('/api/admin/sessions', 'DELETE'); props.ended() })
</script>

<template>
  <button class="title-action" @click="read">Refresh</button>
  <p class="refusal" role="alert">{{ message }}</p>
  <template v-if="shown">
    <section class="card" aria-labelledby="health-title">
      <h2 id="health-title">Health</h2>
      <p>Version <code>{{ shown.commit }}</code> · schema <code>{{ shown.migration }}</code> · started {{ when(shown.started_at) }}</p>
      <p v-if="shown.backup">Last backup: {{ shown.backup.age_hours }} hours ago ({{ when(shown.backup.finished_at) }})<strong v-if="shown.backup.late"> · late</strong></p>
      <p v-else>Last backup: unknown</p>
      <p>Jobs failed or interrupted in the last 24 hours: {{ shown.failed_jobs_24h }}</p>
    </section>

    <section class="card" aria-labelledby="spend-title">
      <h2 id="spend-title">Spend</h2>
      <p>{{ headroom(shown.headroom) }} Counted from {{ shown.spend.since }}.</p>
      <p v-if="shown.headroom.warning"><strong>{{ CAP_WARNING }}</strong></p>
    </section>

    <section class="card" aria-labelledby="pause-title">
      <h2 id="pause-title">New requests to the AI</h2>
      <p v-if="shown.paused_since"><strong>Paused</strong> since {{ when(shown.paused_since) }}: no new request reaches the AI for any shop.</p>
      <p v-else>Running: new requests reach the AI.</p>
      <!-- One control whose word changes, so that the focus it gets back after the confirmation stays on it. -->
      <button :aria-disabled="busy" @click="shown.paused_since ? resume() : pause()">{{ shown.paused_since ? 'Resume' : 'Pause new requests…' }}</button>
      <p role="status">{{ at('pause', false) }}</p>
      <p class="refusal" role="alert">{{ at('pause', true) }}</p>
    </section>

    <section class="card" aria-labelledby="text-title">
      <h2 id="text-title">Purchase text</h2>
      <p>What a shop reads to get credits<template v-if="shown.purchase_text.stored === null"> (none set: every shop reads this fallback)</template>:</p>
      <p class="purchase" lang="fr">{{ shown.purchase_text.shown }}</p>
      <form class="stack" @submit.prevent="save">
        <label for="purchase-text">New text, 1 to 500 characters</label>
        <textarea id="purchase-text" v-model="draft" required lang="fr"></textarea>
        <button class="primary" :aria-disabled="busy">Save</button>
      </form>
      <p role="status">{{ at('text', false) }}</p>
      <p class="refusal" role="alert">{{ at('text', true) }}</p>
    </section>

    <section class="card" aria-labelledby="limits-title">
      <h2 id="limits-title">Daily limits (UTC day)</h2>
      <p>Provider spend per shop: {{ dollars(shown.limits.shop_daily_spend_micros) }} · messages read per shop: {{ shown.limits.reads_per_day }}</p>
      <small>The same for every shop. They change in the box’s secrets file (SHOP_DAILY_SPEND_USD) or in the code.</small>
    </section>

    <section class="card" aria-labelledby="sessions-title">
      <h2 id="sessions-title">Operator sessions</h2>
      <ul class="lines">
        <li v-for="item in shown.operator_sessions" :key="item.actor + item.created_at">
          <p><strong>{{ item.actor }}</strong><strong v-if="item.current"> · this device</strong></p>
          <p>Signed in {{ when(item.created_at) }} · ends {{ when(item.expires_at) }}</p>
          <p>Address {{ item.address }}</p>
          <p>{{ item.agent ?? 'Browser unknown' }}</p>
        </li>
      </ul>
      <button :aria-disabled="busy" @click="endAll">End all operator sessions</button>
      <p class="refusal" role="alert">{{ at('sessions', true) }}</p>
    </section>
  </template>
</template>
