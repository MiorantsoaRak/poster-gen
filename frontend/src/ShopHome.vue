<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, proxyRefs } from 'vue'
import { sectionRead, stateNames, type Listing, type Summary } from './dashboard'
import { credit, type Balance } from './generation'

const props = defineProps<{ funds: ReturnType<typeof sectionRead<Balance>>; busy: boolean }>()
const emit = defineEmits<{ poster: [id: string]; terms: [] }>()
const summary = proxyRefs(sectionRead<Summary>('/api/shop-dashboard'))
const recent = proxyRefs(sectionRead<Listing>('/api/creations?limit=5'))
const funds = proxyRefs(props.funds)
const blocker = computed(() => credit(funds.data, 'scene'))
const attention = computed(() => summary.data ? [
  { group: summary.data.review, label: summary.data.review.first_creation_title ? `Vérifier ${summary.data.review.first_creation_title}` : 'Affiche à vérifier', more: 'à vérifier' },
  { group: summary.data.failed, label: summary.data.failed.first_creation_title ? `Génération échouée · ${summary.data.failed.first_creation_title}` : 'Génération échouée', more: 'avec une génération échouée' },
].filter(item => item.group.first_creation_id) : [])
function refresh() { void summary.read(); void recent.read(); void funds.read() }
onMounted(refresh)
onBeforeUnmount(() => { summary.clear(); recent.clear() })
defineExpose({ refresh })
</script>

<template>
  <section class="shop-home" aria-labelledby="titre-accueil">
    <header class="home-head"><h1 id="titre-accueil" tabindex="-1">Accueil</h1><button type="button" class="secondary" @click="refresh">Actualiser</button></header>
    <section class="home-attention" aria-label="À votre attention">
      <p v-if="summary.loading" role="status">Recherche des affiches à vérifier…</p>
      <p v-if="summary.error" role="status">Suivi indisponible. {{ summary.error }} <button type="button" class="text-button" @click="summary.read">Réessayer le suivi</button></p>
      <div v-for="{ group, label, more } in attention" :key="label" class="attention-row"><button type="button" :disabled="busy" @click="emit('poster', group.first_creation_id!)">{{ label }}</button><span v-if="group.total > 1">+ {{ group.total - 1 }} {{ more }}</span></div>
      <p v-if="summary.data && !summary.loading && !summary.error && !summary.data.review.total && !summary.data.failed.total">Aucune affiche à vérifier.</p>
      <p v-if="summary.data" class="meta">{{ summary.loading || summary.error ? 'Dernier suivi connu à' : 'Suivi des affiches vérifié à' }} {{ summary.checked }}.</p>
      <div v-if="funds.data && !funds.loading && !funds.error && blocker.stop" class="why"><span>{{ blocker.text }}</span> <button v-if="blocker.terms" class="text-button" @click="emit('terms')">Lire les conditions</button><a v-else-if="!funds.data.blocked.scene" href="#credits">Obtenir des crédits</a></div>
    </section>
    <div class="home-bal">
      <div><h2>Mes crédits</h2>
        <div v-if="funds.data" class="home-numbers"><div><strong>{{ funds.data.available }}</strong><span>Disponibles</span></div><div><strong>{{ funds.data.pending }}</strong><span>En attente</span></div></div>
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
      <li v-for="item in recent.data.items" :key="item.id"><button :disabled="busy" @click="emit('poster', item.id)"><img v-if="item.thumbnail_url" :src="item.thumbnail_url" alt="" width="56" height="70" /><span v-else class="blank-poster" aria-hidden="true"></span><span><strong translate="no">{{ item.title }}</strong><small>{{ stateNames[item.state] }}</small></span></button></li>
    </ul>
    <a class="account-link" href="#compte">Mon compte</a>
  </section>
</template>
<style scoped>
.shop-home { max-width: 860px; margin: 0 auto; padding: clamp(18px, 4vw, 46px) 0; overflow-wrap: anywhere }
.home-head, .home-section, .home-bal, .home-numbers, .attention-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap }
.home-head h1, h2 { margin: 0 }
.home-head h1 { font-size: clamp(2rem, 5vw, 3rem) }
.home-attention:has(> *) { margin: 16px 0 }
.attention-row button { max-width: 100%; overflow-wrap: anywhere; text-align: start }
.home-bal { margin: 24px 0 32px; padding: clamp(16px, 3vw, 32px); border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface) }
.home-numbers { justify-content: flex-start; gap: 36px; margin: 12px 0 }
.home-numbers strong, .home-numbers span, .home-recent small { display: block }
.home-numbers strong { font-size: 2rem; line-height: 1.2; font-variant-numeric: tabular-nums }
.home-numbers span, .home-recent small { color: var(--muted) }
a:not(.download-button) { display: inline-flex; min-height: 44px; align-items: center; color: var(--text) }
.home-section { margin-bottom: 8px }
.home-recent { padding: 0; margin: 0; list-style: none }
.home-recent button { width: 100%; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; display: flex; justify-content: flex-start; text-align: left; padding: 10px 2px; gap: 16px; background: transparent }
.home-recent img, .blank-poster { flex: none; width: 44px; height: 55px; object-fit: cover; border-radius: 5px; background: var(--raised) }
.account-link { margin-top: 20px }
</style>
