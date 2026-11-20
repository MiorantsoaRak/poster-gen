<script setup lang="ts">
import { onBeforeUnmount, onMounted, proxyRefs, ref } from 'vue'
import { creditHistory, historyEntry, sectionRead, type Summary } from './dashboard'
import type { Balance } from './generation'

const props = defineProps<{ funds: ReturnType<typeof sectionRead<Balance>>; panel: boolean; busy: boolean }>()
const emit = defineEmits<{ close: []; poster: [id: string] }>()
const funds = proxyRefs(props.funds), summary = proxyRefs(sectionRead<Summary>('/api/shop-dashboard'))
const history = proxyRefs(creditHistory()), posterError = ref('')
const date = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
function refresh() { void funds.read(); void summary.read(); void history.read() }
function unavailable(message: string) { posterError.value = message; void history.read() }
onMounted(refresh)
onBeforeUnmount(() => { summary.clear(); history.clear() })
defineExpose({ refresh, unavailable })
</script>

<template>
  <section class="shop-credits" aria-labelledby="titre-credits">
    <header><h1 id="titre-credits" class="page-title" tabindex="-1">Mes crédits</h1><button v-if="panel" type="button" class="secondary" autofocus @click="emit('close')">Fermer</button><a v-else href="#accueil">Retour à l’accueil</a></header>
    <section class="credit-balance" aria-labelledby="titre-solde">
      <header><h2 id="titre-solde">Solde</h2><button type="button" class="secondary" @click="refresh">Actualiser</button></header>
      <dl v-if="funds.data"><div><dt>Disponibles</dt><dd>{{ funds.data.available }}</dd></div><div><dt>En attente</dt><dd>{{ funds.data.pending }}</dd></div></dl>
      <p v-if="funds.loading && !funds.data" role="status">Lecture du solde…</p>
      <p v-if="funds.error" role="status">Solde indisponible. {{ funds.error }} <button class="text-button" @click="funds.read">Réessayer le solde</button></p>
      <p v-if="funds.checked" class="meta">{{ funds.loading || funds.error ? 'Dernier solde connu à' : 'Solde vérifié à' }} {{ funds.checked }}.</p>
      <p v-if="funds.data && funds.data.pending > 0">Les crédits en attente sont déjà déduits du solde disponible.</p>
      <template v-if="funds.data && !funds.loading && !funds.error">
        <p v-if="funds.data.blocked.scene" class="why">{{ funds.data.blocked.scene.message_fr }}</p>
        <p v-if="funds.data.available <= 0">Un crédit disponible est nécessaire pour générer une nouvelle image. Vos affiches restent accessibles.</p>
      </template>
      <template v-if="funds.data"><h3>Obtenir des crédits</h3><p class="instructions">{{ funds.data.purchase_fr }}</p></template>
    </section>
    <section aria-labelledby="titre-usage"><h2 id="titre-usage">Ces 30 derniers jours</h2>
      <p v-if="summary.data">{{ summary.data.usage.posters_created }} affiche{{ summary.data.usage.posters_created > 1 ? 's' : '' }} créée{{ summary.data.usage.posters_created > 1 ? 's' : '' }} · {{ summary.data.usage.images_generated }} image{{ summary.data.usage.images_generated > 1 ? 's' : '' }} générée{{ summary.data.usage.images_generated > 1 ? 's' : '' }} · {{ summary.data.usage.credits_spent }} crédit{{ summary.data.usage.credits_spent > 1 ? 's' : '' }} dépensé{{ summary.data.usage.credits_spent > 1 ? 's' : '' }}</p>
      <p v-if="summary.loading && !summary.data" role="status">Lecture de l’activité…</p>
      <p v-if="summary.error" role="status">Activité indisponible. {{ summary.error }} <button class="text-button" @click="summary.read">Réessayer l’activité</button></p>
      <p v-if="summary.checked" class="meta">Activité vérifiée à {{ summary.checked }}.</p>
    </section>
    <section aria-labelledby="titre-historique"><h2 id="titre-historique">Historique</h2>
      <p v-if="posterError" role="alert">{{ posterError }}</p>
      <ul v-if="history.page?.items.length">
        <li v-for="row in history.page.items" :key="row.type + ':' + row.id">
          <div><strong>{{ historyEntry(row).label }}</strong> <span>{{ historyEntry(row).amount }}</span></div>
          <time :datetime="row.at">{{ date.format(new Date(row.at)) }}</time>
          <button v-if="row.creation_id && !row.removed" class="text-button" :disabled="busy" @click="posterError = ''; emit('poster', row.creation_id)">{{ row.title || 'Ouvrir l’affiche' }}</button>
          <small v-else-if="row.removed">{{ row.title }} · Affiche retirée</small>
        </li>
      </ul>
      <p v-else-if="history.page">Aucun mouvement de crédits pour le moment.</p>
      <p v-if="history.loading" role="status">Lecture de l’historique…</p>
      <p v-if="history.error" role="status">{{ history.error }} <button class="text-button" @click="history.read(history.retryMore)">{{ history.retryMore ? 'Réessayer la suite' : 'Actualiser l’historique' }}</button></p>
      <button v-if="history.page?.next_cursor && !history.error" class="secondary" :disabled="history.loading" @click="history.read(true)">Voir plus</button>
      <p v-if="history.checked" class="meta">Historique vérifié à {{ history.checked }}.</p>
    </section>
  </section>
</template>

<style scoped>
/* As a page, the frame's width; as the creator's panel, its dialog's 680 px (style.css). */
.shop-credits { max-width: var(--page); margin: auto; padding: 16px 0; overflow-wrap: anywhere }
header, li > div, dl { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap }
h1, h2, h3, dl, dd, ul { margin: 0 }
section > section { margin-top: 24px }
.credit-balance { padding: 16px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface) }
dl { justify-content: flex-start; gap: 36px; margin: 14px 0 }
dd { font-size: 1.8rem; font-weight: 700; line-height: 1.3; font-variant-numeric: tabular-nums }
.instructions { white-space: pre-line }
ul { list-style: none; padding: 0 }
li { padding: 10px 0; border-bottom: 1px solid var(--line) }
li span { font-variant-numeric: tabular-nums }
li time, li small { display: block; color: var(--muted) }
a { display: inline-flex; align-items: center; min-height: 44px; color: var(--text) }
</style>
