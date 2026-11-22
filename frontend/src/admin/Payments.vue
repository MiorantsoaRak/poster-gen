<script setup lang="ts">
// The Payments screen (D-ADMIN-005, R-ADMIN-003; « Money » until D-REDESIGN-005, still at #/money): the payments recorded
// in a period of whole UTC days, and what was received.
// A moved payment's three lines (+A, −A, +A) are all listed; the server's total counts it once.
import { computed, onMounted, ref } from 'vue'
import { call } from './adminApi'
import { ariary, month, signed, when, type Payments } from './admin'

const props = defineProps<{ failure: (error: unknown) => string }>()
const submitted = ref(month()), period = ref({ ...submitted.value })
const edited = computed(() => period.value.start !== submitted.value.start || period.value.end !== submitted.value.end)
const shown = ref<Payments>(), message = ref(''), loading = ref(false)

let reads = 0
function applyDates() {
  submitted.value = { ...period.value }
  void read()
}
async function read() {
  const { start, end } = submitted.value, mine = ++reads  // a background refresh keeps the last submitted range
  message.value = ''; loading.value = true
  try {
    const answer = await call<Payments>(`/api/admin/payments?start=${start}&end=${end}`)
    if (mine === reads) shown.value = answer
  } catch (error) {
    const said = props.failure(error)
    if (mine === reads && said) message.value = `Payments from ${start} to ${end}: ${said}`
  } finally { if (mine === reads) loading.value = false }
}
onMounted(read)
defineExpose({ read })  // read again when the tab comes back (D-ADMIN-005: fresh data, no polling)
</script>

<template>
  <div class="card">
    <div v-if="shown" aria-live="polite" aria-atomic="true">
      <h2 id="payments-title">Payments from <time :datetime="shown.start">{{ shown.start }}</time> to <time :datetime="shown.end">{{ shown.end }}</time> UTC</h2>
      <p class="received">Received: <strong>{{ ariary(shown.received_ar) }}</strong></p>
    </div>
    <p v-if="loading" role="status">Loading payments…</p>
    <p v-if="message" class="refusal" role="alert">{{ message }}</p>
    <button v-if="message" type="button" @click="read">Retry payments</button>
    <details>
      <summary>Change dates</summary>
      <form class="range" @submit.prevent="applyDates">
        <div><label for="period-start">First day (UTC)</label>
          <input id="period-start" v-model="period.start" type="date" required :max="period.end"></div>
        <div><label for="period-end">Last day, included</label>
          <input id="period-end" v-model="period.end" type="date" required :min="period.start"></div>
        <button class="primary">Show</button>
      </form>
      <small v-if="edited" role="status">Dates edited. Choose Show to apply them.</small>
    </details>
  </div>
  <section v-if="shown" class="card" aria-labelledby="payments-title">
    <!-- A ledger is a table: one payment a row, the amounts on one right edge. Under 600 px each row is a block of
         labelled values (admin.css .shops). -->
    <table v-if="shown.items.length" class="shops payments">
      <caption class="vh">Payments from {{ shown.start }} to {{ shown.end }}, inclusive UTC</caption>
      <thead><tr><th>When</th><th>Shop</th><th>Entry</th><th>Method</th><th>Reference</th><th class="num">Credits</th><th class="num">Amount</th></tr></thead>
      <tbody>
        <tr v-for="payment in shown.items" :key="payment.line">
          <td data-label="When">{{ when(payment.at) }}<small>{{ payment.actor }}</small></td>
          <td data-label="Shop" class="who"><a :href="`#/shops/${payment.shop_id}`">{{ payment.identifier }}</a></td>
          <td data-label="Entry">{{ payment.kind }}{{ payment.origin ? ` ${payment.origin}` : '' }} · line {{ payment.line }}</td>
          <td data-label="Method">{{ payment.method || '—' }}</td>
          <td data-label="Reference"><code>{{ payment.ref }}</code><small v-if="payment.note">{{ payment.note }}</small></td>
          <td data-label="Credits" class="num">{{ signed(payment.credits) }}</td>
          <td data-label="Amount" class="num amount">{{ signed(payment.amount_ar) }}&nbsp;Ar</td>
        </tr>
      </tbody>
    </table>
    <p v-else>No payment in this period.</p>
  </section>
</template>

<style scoped>
.received { color: var(--muted) }
#payments-title { margin-top: 0 }
time { white-space: nowrap }
.received strong { margin-left: .25em; color: var(--text); font-size: 28px; line-height: 1.2; font-variant-numeric: tabular-nums }
details { border-top: 1px solid var(--line) }
details small { margin-top: 8px }
@media (width >= 600px) { .who a { max-width: 100%; overflow-wrap: anywhere } }
@media (width < 600px) {
  .payments td[data-label] { align-items: center }
  .payments small { text-align: right }
}
</style>
