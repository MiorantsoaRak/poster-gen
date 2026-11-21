<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, proxyRefs } from 'vue'
import { creditWord, sectionRead, stateBadges, stateNames, type Listing, type Summary } from './dashboard'
import { credit, type Balance } from './generation'

// The balance and the five latest posters are the application's, shared with its shell (D-REDESIGN-002).
const props = defineProps<{ funds: ReturnType<typeof sectionRead<Balance>>; recent: ReturnType<typeof sectionRead<Listing>>; busy: boolean }>()
const emit = defineEmits<{ poster: [id: string]; terms: [] }>()
const summary = proxyRefs(sectionRead<Summary>('/api/shop-dashboard'))
const recent = proxyRefs(props.recent)
const funds = proxyRefs(props.funds)
const blocker = computed(() => credit(funds.data, 'scene'))
const attention = computed(() => summary.data ? [
  { group: summary.data.review, label: summary.data.review.first_creation_title ? `Vérifier ${summary.data.review.first_creation_title}` : 'Affiche à vérifier', more: 'à vérifier' },
  { group: summary.data.failed, label: summary.data.failed.first_creation_title ? `Génération échouée · ${summary.data.failed.first_creation_title}` : 'Génération échouée', more: 'avec une génération échouée' },
].filter(item => item.group.first_creation_id) : [])
function refresh() { void summary.read(); void recent.read(); void funds.read() }
onMounted(refresh)
onBeforeUnmount(() => summary.clear())
defineExpose({ refresh })
</script>

<template>
  <section class="shop-home" aria-labelledby="titre-accueil">
    <header class="home-head"><h1 id="titre-accueil" class="page-title" tabindex="-1">Accueil</h1><button type="button" class="secondary" @click="refresh">Actualiser</button></header>
    <section class="home-attention" aria-label="À votre attention">
      <p v-if="summary.loading" role="status">Recherche des affiches à vérifier…</p>
      <p v-if="summary.error" role="status">Suivi indisponible. {{ summary.error }} <button type="button" class="text-button" @click="summary.read">Réessayer le suivi</button></p>
      <div v-for="{ group, label, more } in attention" :key="label" class="attention-row"><button type="button" :disabled="busy" @click="emit('poster', group.first_creation_id!)">{{ label }}</button><span v-if="group.total > 1">+ {{ group.total - 1 }} {{ more }}</span></div>
      <p v-if="summary.data && !summary.loading && !summary.error && !summary.data.review.total && !summary.data.failed.total">Aucune affiche à vérifier.</p>
      <p v-if="summary.data" class="meta">{{ summary.loading || summary.error ? 'Dernier suivi connu à' : 'Suivi des affiches vérifié à' }} {{ summary.checked }}.</p>
      <div v-if="funds.data && !funds.loading && !funds.error && blocker.stop" class="why"><span>{{ blocker.text }}</span> <button v-if="blocker.terms" class="text-button" @click="emit('terms')">Lire les conditions</button><a v-else-if="!funds.data.blocked.scene" href="#credits">Obtenir des crédits</a></div>
    </section>
    <div class="home-bal balance-card">
      <div><h2>Mes crédits</h2>
        <div v-if="funds.data" class="home-numbers balance-figures"><div><span class="label">Disponibles</span><strong class="value">{{ funds.data.available }}</strong> <span class="credit-unit">{{ creditWord(funds.data.available) }}</span></div><div><span class="label">En attente</span><strong class="value">{{ funds.data.pending }}</strong> <span class="credit-unit">{{ creditWord(funds.data.pending) }}</span></div></div>
        <p v-else-if="funds.loading" role="status">Lecture du solde…</p>
        <p v-if="funds.error" role="status">Solde indisponible. {{ funds.error }} <button type="button" class="text-button" @click="funds.read">Réessayer le solde</button></p>
        <p v-if="funds.data" class="meta">{{ funds.loading || funds.error ? 'Dernier solde connu à' : 'Solde vérifié à' }} {{ funds.checked }}.</p>
        <a href="#credits">Voir mes crédits</a>
      </div>
      <a class="download-button" href="#creer">Créer une affiche</a>
    </div>
    <div class="home-section"><h2>Affiches récentes</h2><a href="#affiches">Tout voir</a></div>
    <p v-if="recent.error" role="status">Affiches indisponibles. {{ recent.error }} <button class="text-button" @click="recent.read">Réessayer les affiches</button></p>
    <p v-else-if="recent.loading && !recent.data" role="status">Lecture des affiches…</p>
    <p v-if="recent.data" class="meta">Liste vérifiée à {{ recent.checked }}.</p>
    <p v-if="recent.data && !recent.data.items.length" class="empty">Aucune affiche pour le moment.</p>
    <ul v-if="recent.data?.items.length" class="home-recent">
      <li v-for="item in recent.data.items" :key="item.id"><button :disabled="busy" @click="emit('poster', item.id)"><img v-if="item.thumbnail_url" :src="item.thumbnail_url" alt="" width="48" height="60" /><span v-else class="blank-poster" aria-hidden="true"></span><span><strong translate="no">{{ item.title }}</strong><span :class="stateBadges[item.state]">{{ stateNames[item.state] }}</span></span></button></li>
    </ul>
    <a class="account-link" href="#compte">Mon compte</a>
  </section>
</template>
<style scoped>
.shop-home { max-width: var(--page); margin: 0 auto; padding: clamp(18px, 4vw, 46px) 0; overflow-wrap: anywhere }
.home-head, .home-section, .attention-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap }
.home-head h1, h2 { margin: 0 }
.home-attention:has(> *) { margin: 16px 0 }
.attention-row button { max-width: 100%; overflow-wrap: anywhere; text-align: start }
/* The balance card (style.css .balance-card): here the figures, then the action under them (beside them when wide). */
.home-bal { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 20px 32px; margin: 24px 0 32px }
.home-bal > div { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; column-gap: 16px; min-width: 0 }
.home-bal > div > :not(.meta, a) { grid-column: 1 / -1 }
.home-recent strong { display: block }
@media (width <= 720px) {
  .home-bal { grid-template-columns: minmax(0, 1fr) }
  .home-bal .download-button { justify-content: center }
}
.home-recent .badge { margin-top: 4px }
a:not(.download-button) { display: inline-flex; min-height: 44px; align-items: center; color: var(--text) }
.home-section { margin-bottom: 8px }
.home-recent { padding: 0; margin: 0; list-style: none }
.home-recent button { width: 100%; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; display: flex; justify-content: flex-start; text-align: left; padding: 10px 2px; gap: 16px; background: transparent }
.home-recent img, .blank-poster { flex: none; width: 48px; height: 60px; object-fit: cover; border-radius: 4px; background: var(--raised) }
.home-recent button > span:last-child { flex: 1; min-width: 0 }
/* A row that opens something says so at its end: the same chevron as a row of « Mes affiches ». Drawn, not a letter. */
.home-recent button::after, a.account-link::after { content: ''; flex: none; width: 7px; height: 7px; margin: 0 8px; border: solid var(--faint); border-width: 1.6px 1.6px 0 0; rotate: 45deg }
/* The account: a row of its own under the list, not a lone underlined word. */
a.account-link { display: flex; justify-content: space-between; min-height: 56px; margin-top: 24px; padding: 0 2px; border-block: 1px solid var(--line); font-weight: 650; text-decoration: none }
@media (hover: hover) { a.account-link:hover { background: var(--active) } }
</style>
