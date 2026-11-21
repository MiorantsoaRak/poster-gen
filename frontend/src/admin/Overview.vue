<script setup lang="ts">
// The console's home (D-REDESIGN-006, R-REDESIGN-006): four figures, « Needs you », the shops by last poster, the service
// and this month's payments, from three reads made together. Each block shows its own read; a failed read says so in its
// blocks, and « Needs you » never says it is empty when what it reads was not read by the current refresh.
import { computed, h, onMounted, ref, type FunctionalComponent, type Ref } from 'vue'
import { call } from './adminApi'
import {
  count, dollars, grouped, perImage, signed, state, when, type Payments, type Pending, type ServiceView, type Shop,
} from './admin'

const props = defineProps<{ failure: (error: unknown) => string; kept: Pending }>()
// A read's last word: its answer, or the line that says it failed (never empty, a 401's included); `pending` until the
// current refresh has answered it, the last word staying shown meanwhile.
type Read<T> = { answer?: T; failed?: string; pending?: boolean }
const shops = ref<Read<{ items: Shop[] }>>({}), service = ref<Read<ServiceView>>({}), payments = ref<Read<Payments>>({})

// Each refresh takes a number; only the newest one's answers are shown, in success and in failure. Every refusal still
// goes to the page's failure(), so that a 401 of this session opens the sign-in whatever its number (adminApi drops the
// answers of an earlier session).
let refreshes = 0
function read() {
  const mine = ++refreshes
  for (const each of [shops, service, payments] as Ref<Read<unknown>>[]) each.value = { ...each.value, pending: true }
  const one = <T,>(name: string, path: string, into: Ref<Read<T>>) => call<T>(path).then(
    answer => { if (mine === refreshes) into.value = { answer } },
    error => { const said = props.failure(error); if (mine === refreshes) into.value = { failed: `${name}: ${said}` } })
  return Promise.all([one('Shops', '/api/admin/shops', shops), one('Service', '/api/admin/service', service),
                      one('Payments', '/api/admin/payments', payments)])  // no parameter: the current UTC month
}
onMounted(read)
defineExpose({ read })  // also on « Refresh » and when the tab comes back (Admin.vue load)

/** A block whose read has not answered: waiting, or failed with a way to read again. */
const Unread: FunctionalComponent<{ from: Read<unknown> }> = ({ from }) => from.failed
  ? [h('p', { class: 'refusal' }, 'Could not be read.'), h('button', { type: 'button', onClick: read }, 'Try again')]
  : h('p', 'Loading…')

const failures = computed(() => [shops, service, payments].map(each => each.value.failed).filter(Boolean))
const room = computed(() => service.value.answer?.headroom)
const active = computed(() => shops.value.answer?.items.filter(shop => shop.state === 'active').length)
const month = computed(() => payments.value.answer && new Date(`${payments.value.answer.start}T00:00:00Z`).toLocaleString('en', { month: 'long', timeZone: 'UTC' }))
const spent = computed(() => room.value ? room.value.spent / room.value.cap * 100 : 0)
// Code-unit order, as the server sorts identifiers; an ISO time sorts as its text, and none ('') goes last.
const order = (x: string, y: string) => x < y ? -1 : x > y ? 1 : 0
const latest = computed(() => [...shops.value.answer?.items ?? []]
  .sort((a, b) => order(b.last_poster_at ?? '', a.last_poster_at ?? '') || order(a.identifier, b.identifier)).slice(0, 8))
const recent = computed(() => payments.value.answer?.items.slice(-5).reverse())  // in ledger order: the last five, newest first

// « Needs you »: what the operator can act on, from three inputs. Shops gives the missing passwords; Service the purchase
// text, the backup, the failed jobs and the cap; the page's memory the unanswered requests (storage refused included).
const needs = computed(() => {
  const items = shops.value.answer?.items, view = service.value.answer
  const list: { text: string; detail: string; href: string }[] = Object.values(props.kept).map(request => ({
    text: 'A request with no definite answer', detail: items?.find(shop => shop.id === request.shop)?.identifier ?? `shop ${request.shop}`,
    href: `#/shops/${request.shop}` }))
  for (const shop of items ?? []) if (!shop.has_password) list.push({ text: 'No password', detail: shop.identifier, href: `#/shops/${shop.id}` })
  if (view) {
    if (view.purchase_text.stored == null) list.push({ text: 'No purchase text', detail: 'Shops read the fallback sentence', href: '#/service' })
    if (!view.backup) list.push({ text: 'Last backup unknown', detail: 'No backup marker could be read', href: '#/service' })
    else if (view.backup.late) list.push({ text: 'Backup late', detail: `Last backup ${count(view.backup.age_hours, 'hour')} ago`, href: '#/service' })
    if (view.failed_jobs_24h > 0) list.push({ text: count(view.failed_jobs_24h, 'failed job'), detail: 'Failed or interrupted in the last 24 hours', href: '#/service' })
    if (view.headroom.warning) list.push({ text: 'Cap warning', detail: 'The outstanding credits would cost more than what is left of the cap', href: '#/service' })
  }
  return list
})
// Empty only when both of its reads answered this refresh: never from one refresh's shops and another's service.
const checked = computed(() => !!shops.value.answer && !!service.value.answer && !shops.value.pending && !service.value.pending)
</script>

<template>
  <button type="button" class="title-action" @click="read">Refresh</button>
  <div class="refusal" role="alert"><p v-for="line in failures" :key="line">{{ line }}</p></div>

  <!-- The four figures: one card split by hairlines, a label over each value. -->
  <dl class="card kpis">
    <div class="kpi">
      <dt>Active shops</dt>
      <dd v-if="shops.answer" class="value">{{ grouped(active!) }} <small>of {{ grouped(shops.answer.items.length) }}</small></dd>
      <dd v-else><Unread :from="shops" /></dd>
    </div>
    <div class="kpi">
      <dt>Credits outstanding</dt>
      <template v-if="room">
        <dd class="value">{{ grouped(room.outstanding) }}</dd>
        <dd>≈ {{ dollars(room.cost, Math.ceil) }} at {{ perImage(room.unit) }} an image</dd>
      </template>
      <dd v-else><Unread :from="service" /></dd>
    </div>
    <div class="kpi">
      <dt>Received in {{ month ?? 'this month' }} (UTC)</dt>
      <dd v-if="payments.answer" class="value">{{ grouped(payments.answer.received_ar) }} <small>Ar</small></dd>
      <dd v-else><Unread :from="payments" /></dd>
    </div>
    <div class="kpi">
      <dt>Provider spend</dt>
      <template v-if="room && service.answer">
        <dd class="value">{{ dollars(room.spent) }} <small>of {{ dollars(room.cap) }}</small></dd>
        <dd>since {{ service.answer.spend.since }}</dd>
        <!-- The figure is the real spend; the meter stops when full. -->
        <dd><div class="meter" role="img" :aria-label="`${Math.round(spent)}% of the cap spent`"><i :style="{ width: `${Math.min(spent, 100)}%` }"></i></div></dd>
      </template>
      <dd v-else><Unread :from="service" /></dd>
    </div>
  </dl>

  <!-- What needs action comes first, the full width, at every width: one order for the eye, the keyboard and a phone. -->
  <section class="card needs" aria-labelledby="overview-needs">
    <h2 id="overview-needs">Needs you</h2>
    <ul v-if="needs.length" class="lines">
      <li v-for="need in needs" :key="need.href + need.text">
        <a :href="need.href"><span><strong>{{ need.text }}</strong> <small>{{ need.detail }}</small></span>
          <svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg></a>
      </li>
    </ul>
    <p v-if="shops.pending">Checking shops…</p>
    <p v-else-if="shops.failed">Shops not read: passwords not checked.</p>
    <p v-if="service.pending">Checking service…</p>
    <p v-else-if="service.failed">Service not read: purchase text, backup, jobs and cap not checked.</p>
    <p v-if="!needs.length && checked">Nothing needs you.</p>
  </section>

  <!-- Below it: the shops and the service, then the payments; two columns over 1180 px. -->
  <div class="cols">
    <div>
      <section class="card table-card" aria-labelledby="overview-shops">
        <div class="head">
          <h2 id="overview-shops">Shops</h2>
          <a v-if="shops.answer" href="#/shops">View all {{ grouped(shops.answer.items.length) }}</a>
        </div>
        <table v-if="latest.length" class="shops">
          <thead><tr><th>Shop</th><th>State</th><th class="num">Available</th><th class="num">Posters</th><th>Last poster</th></tr></thead>
          <tbody>
            <tr v-for="shop in latest" :key="shop.id">
              <td class="shop"><a :href="`#/shops/${shop.id}`" :title="shop.identifier">{{ shop.identifier }}</a><small :title="shop.name ?? undefined">{{ shop.name ?? '—' }}</small></td>
              <td data-label="State">
                <span class="badge" :class="state(shop).tone">{{ state(shop).word }}</span>
                <strong v-if="kept[shop.id]" class="unresolved">unresolved request</strong>
              </td>
              <td class="num" data-label="Available">{{ shop.available }}</td>
              <td class="num" data-label="Posters">{{ shop.posters }}</td>
              <td data-label="Last poster">{{ shop.last_poster_at?.slice(0, 10) ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="shops.answer" class="pad">No shop yet.</p>
        <div v-else class="pad"><Unread :from="shops" /></div>
      </section>

      <section class="card" aria-labelledby="overview-service">
        <h2 id="overview-service">Service</h2>
        <dl v-if="service.answer" class="facts">
          <div><dt>New AI requests</dt><dd>{{ service.answer.paused_since ? `Paused since ${when(service.answer.paused_since)}` : 'Running' }}</dd></div>
          <div><dt>Version</dt><dd><code>{{ service.answer.commit }}</code> · schema <code>{{ service.answer.migration }}</code></dd></div>
          <div><dt>Last backup</dt><dd>{{ service.answer.backup ? `${count(service.answer.backup.age_hours, 'hour')} ago${service.answer.backup.late ? ' · late' : ''}` : 'unknown' }}</dd></div>
          <div><dt>Failed jobs, 24 hours</dt><dd>{{ service.answer.failed_jobs_24h }}</dd></div>
          <div><dt>Daily limits per shop</dt><dd>{{ dollars(service.answer.limits.shop_daily_spend_micros) }} · {{ service.answer.limits.reads_per_day }} messages read</dd></div>
        </dl>
        <Unread v-else :from="service" />
      </section>
    </div>

    <section class="card" aria-labelledby="overview-payments">
      <div class="head">
        <h2 id="overview-payments">Payments this month</h2>
        <a href="#/money">View all</a>
      </div>
      <ul v-if="recent?.length" class="lines">
        <li v-for="payment in recent" :key="payment.line" class="paid">
          <div>
            <p><strong>{{ payment.identifier }}</strong> · {{ signed(payment.credits) }} {{ Math.abs(payment.credits) === 1 ? 'credit' : 'credits' }}</p>
            <small>{{ payment.kind }}{{ payment.origin ? ` ${payment.origin}` : '' }}<template v-if="payment.method"> · {{ payment.method }}</template> · <code>{{ payment.ref }}</code> · {{ payment.at.slice(0, 10) }}</small>
          </div>
          <strong class="amount">{{ signed(payment.amount_ar) }}&nbsp;Ar</strong>
        </li>
      </ul>
      <p v-else-if="recent">No payment this month.</p>
      <Unread v-else :from="payments" />
    </section>
  </div>
</template>
