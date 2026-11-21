<script setup lang="ts">
// The Payments screen (D-ADMIN-005, R-ADMIN-003; « Money » until D-REDESIGN-005, still at #/money): the payments recorded
// in a period of whole UTC days, and what was received.
// A moved payment's three lines (+A, −A, +A) are all listed; the server's total counts it once.
import { onMounted, ref } from 'vue'
import { call } from './adminApi'
import { ariary, month, signed, when, type Payments } from './admin'

const props = defineProps<{ failure: (error: unknown) => string }>()
const period = ref(month())
const shown = ref<Payments>(), message = ref('')

let reads = 0
async function read() {
  const { start, end } = period.value, mine = ++reads  // the last read only is shown, in success and in failure
  message.value = ''
  try {
    const answer = await call<Payments>(`/api/admin/payments?start=${start}&end=${end}`)
    if (mine === reads) shown.value = answer
  } catch (error) { const said = props.failure(error); if (mine === reads) message.value = said }
}
onMounted(read)
defineExpose({ read })  // read again when the tab comes back (D-ADMIN-005: fresh data, no polling)
</script>

<template>
  <div class="card">
    <form class="range" @submit.prevent="read">
      <div><label for="period-start">First day (UTC)</label>
        <input id="period-start" v-model="period.start" type="date" required :max="period.end"></div>
      <div><label for="period-end">Last day, included</label>
        <input id="period-end" v-model="period.end" type="date" required :min="period.start"></div>
      <button class="primary">Show</button>
      <p class="refusal" role="alert">{{ message }}</p>
    </form>
  </div>
  <section v-if="shown" class="card" aria-labelledby="payments-title">
    <h2 id="payments-title">Payments from {{ shown.start }} to {{ shown.end }}</h2>
    <p><strong>Received: {{ ariary(shown.received_ar) }}</strong></p>
    <!-- A ledger is a table: one payment a row, the amounts on one right edge. Under 600 px each row is a block of
         labelled values (admin.css .shops). -->
    <table v-if="shown.items.length" class="shops payments">
      <thead><tr><th>When</th><th>Shop</th><th>Entry</th><th>Method</th><th>Reference</th><th class="num">Credits</th><th class="num">Amount</th></tr></thead>
      <tbody>
        <tr v-for="payment in shown.items" :key="payment.line">
          <td data-label="When">{{ when(payment.at) }}<small>{{ payment.actor }}</small></td>
          <td data-label="Shop" class="who">{{ payment.identifier }}</td>
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
