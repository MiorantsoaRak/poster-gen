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
    <form class="stack" @submit.prevent="read">
      <label for="period-start">First day (UTC)</label>
      <input id="period-start" v-model="period.start" type="date" required :max="period.end">
      <label for="period-end">Last day, included</label>
      <input id="period-end" v-model="period.end" type="date" required :min="period.start">
      <button class="primary">Show</button>
      <p class="refusal" role="alert">{{ message }}</p>
    </form>
  </div>
  <section v-if="shown" class="card" aria-labelledby="payments-title">
    <h2 id="payments-title">Payments from {{ shown.start }} to {{ shown.end }}</h2>
    <p><strong>Received: {{ ariary(shown.received_ar) }}</strong></p>
    <ul v-if="shown.items.length" class="lines">
      <li v-for="payment in shown.items" :key="payment.line">
        <p><strong>{{ signed(payment.amount_ar) }}&nbsp;Ar</strong> · {{ payment.identifier }} · {{ payment.kind }}{{ payment.origin ? ` ${payment.origin}` : '' }} · line {{ payment.line }}</p>
        <p>{{ signed(payment.credits) }} {{ Math.abs(payment.credits) === 1 ? 'credit' : 'credits' }}<template v-if="payment.method"> · by {{ payment.method }}</template></p>
        <p>Reference <code>{{ payment.ref }}</code></p>
        <p v-if="payment.note">{{ payment.note }}</p>
        <small>{{ when(payment.at) }} · {{ payment.actor }}</small>
      </li>
    </ul>
    <p v-else>No payment in this period.</p>
  </section>
</template>
