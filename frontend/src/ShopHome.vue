<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, proxyRefs } from 'vue'
import { creditWord, sectionRead, stateBadges, stateNames, type Listing, type Summary } from './dashboard'
import { credit, type Balance } from './generation'

// The balance and the five latest posters are the application's, shared with its shell (D-REDESIGN-002).
const props = defineProps<{ funds: ReturnType<typeof sectionRead<Balance>>; recent: ReturnType<typeof sectionRead<Listing>>; busy: boolean; publish?: boolean }>()
const emit = defineEmits<{ poster: [id: string]; review: [id: string]; terms: []; guide: [event: MouseEvent] }>()
const summary = proxyRefs(sectionRead<Summary>('/api/shop-dashboard'))
const recent = proxyRefs(props.recent)
const emptyRecent = computed(() => recent.data?.total === 0 && !recent.data.items.length && !recent.loading && !recent.error)
const funds = proxyRefs(props.funds)
const blocker = computed(() => credit(funds.data, 'scene'))
const showFunds = computed(() => !funds.data || !!funds.error || blocker.value.stop || funds.data.available <= 3 || funds.data.pending > 0)
const attention = computed(() => {
  if (!summary.data) return []
  const groups = [
    { group: summary.data.review, review: true, status: 'À vérifier', action: 'Vérifier l’affiche', more: 'à vérifier' },
    { group: summary.data.failed, review: false, status: 'Génération échouée', action: 'Reprendre l’affiche', more: 'avec une génération échouée' },
  ]
  return groups.flatMap(entry => {
    const id = entry.group.first_creation_id
    if (!id) return []
    const poster = recent.data?.items.find(item => item.id === id)
    return [{ ...entry, id, title: entry.group.first_creation_title || poster?.title, thumbnail: poster?.thumbnail_url }]
  })
})
function refresh() { void summary.read(); void recent.read(); void funds.read() }
onMounted(refresh)
onBeforeUnmount(() => summary.clear())
defineExpose({ refresh })
</script>

<template>
  <section class="shop-home" aria-labelledby="titre-accueil">
    <header class="home-head">
      <h1 id="titre-accueil" class="page-title" tabindex="-1">Accueil</h1>
      <a class="download-button" href="#creer">Créer une affiche</a>
      <button v-if="emptyRecent" type="button" class="text-button home-guide" aria-haspopup="dialog" @click="emit('guide', $event)">Ma première affiche</button>
    </header>

    <section class="home-attention" aria-label="À votre attention">
      <h2 v-if="attention.length">Affiches à reprendre</h2>
      <p v-if="summary.loading" role="status">Recherche des affiches à vérifier…</p>
      <p v-if="summary.error" role="status">Suivi indisponible. {{ summary.error }} <button type="button" class="text-button" @click="summary.read">Réessayer le suivi</button></p>
      <div v-if="attention.length" class="attention-list">
        <button v-for="(item, index) in attention" :key="item.status" class="attention-row" type="button" :disabled="busy" @click="item.review ? emit('review', item.id) : emit('poster', item.id)">
          <img v-if="item.thumbnail" :src="item.thumbnail" alt="" width="56" height="70" />
          <span class="attention-info">
            <span class="attention-status">{{ item.status }}</span>
            <strong v-if="item.title" translate="no">{{ item.title }}</strong>
            <small v-if="item.group.total > 1">+ {{ item.group.total - 1 }} {{ item.more }}</small>
          </span>
          <span class="attention-action" :class="{ next: index === 0 }">{{ item.action }}</span>
        </button>
      </div>
      <div class="home-check">
        <span v-if="summary.data && !summary.loading && !summary.error && !summary.data.review.total && !summary.data.failed.total">Aucune affiche à vérifier.</span>
        <span v-if="summary.data">{{ summary.loading || summary.error ? 'Dernier suivi connu à' : 'Suivi des affiches vérifié à' }} {{ summary.checked }}.</span>
      </div>
    </section>

    <section v-if="showFunds" class="home-bal" aria-label="Mes crédits">
      <h2>Mes crédits</h2>
      <dl v-if="funds.data" class="home-numbers">
        <div><dt>Disponibles</dt><dd><strong>{{ funds.data.available }}</strong> {{ creditWord(funds.data.available) }}</dd></div>
        <div><dt>En attente</dt><dd><strong>{{ funds.data.pending }}</strong> {{ creditWord(funds.data.pending) }}</dd></div>
      </dl>
      <p v-if="funds.loading && !funds.data" role="status">Lecture du solde…</p>
      <p v-if="funds.error" role="status">Solde indisponible. {{ funds.error }} <button type="button" class="text-button" @click="funds.read">Réessayer le solde</button></p>
      <template v-if="funds.data && !funds.loading && !funds.error">
        <p v-if="blocker.stop" class="fund-note">{{ blocker.text }}
          <button v-if="blocker.terms" type="button" class="text-button" @click="emit('terms')">Lire les conditions</button>
          <a v-else-if="!funds.data.blocked.scene" href="#credits">Obtenir des crédits</a>
        </p>
        <p v-else-if="funds.data.available <= 3" class="fund-note">Votre solde est bas. <a href="#credits">Obtenir des crédits</a></p>
      </template>
      <p v-if="funds.data" class="meta">{{ funds.loading || funds.error ? 'Dernier solde connu à' : 'Solde vérifié à' }} {{ funds.checked }}.</p>
    </section>

    <section class="recent-posters" aria-labelledby="titre-recentes">
      <header class="home-section"><h2 id="titre-recentes">Affiches récentes</h2><a href="#affiches">Tout voir</a></header>
      <p v-if="recent.error" role="status">Affiches indisponibles. {{ recent.error }} <button class="text-button" @click="recent.read">Réessayer les affiches</button></p>
      <p v-else-if="recent.loading && !recent.data" role="status">Lecture des affiches…</p>
      <div v-if="emptyRecent" class="empty">
        <strong>Aucune affiche pour le moment.</strong>
        <p>Pour votre première affiche, préparez une photo du produit et son prix en ariary.</p>
      </div>
      <ul v-if="recent.data?.items.length" class="home-recent">
        <li v-for="item in recent.data.items" :key="item.id"><button :disabled="busy" @click="emit('poster', item.id)"><img v-if="item.thumbnail_url" :src="item.thumbnail_url" alt="" width="48" height="60" /><span v-else class="blank-poster" aria-hidden="true"></span><span><strong translate="no">{{ item.title }}</strong><span :class="stateBadges[item.state]">{{ stateNames[item.state] }}</span></span></button></li>
      </ul>
      <p v-if="recent.data" class="meta">{{ recent.loading || recent.error ? 'Dernière liste connue à' : 'Liste vérifiée à' }} {{ recent.checked }}.</p>
    </section>

    <footer class="home-links">
      <button type="button" class="text-button" @click="refresh">Actualiser</button>
      <a href="#credits">Voir mes crédits</a>
      <a v-if="publish" href="#publier">Publier sur Facebook</a>
      <a href="#compte">Mon compte</a>
    </footer>
  </section>
</template>

<style scoped>
.shop-home { max-width: var(--page); margin: 0 auto; padding: clamp(18px, 4vw, 46px) 0; overflow-wrap: anywhere }
.home-head, .home-section { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap }
.home-head { margin-bottom: 24px }
.home-head h1, h2, .home-bal p, .empty p { margin: 0 }
.home-head h1 { margin-inline-end: auto }
.home-attention, .home-bal { margin-bottom: 24px }
.attention-list { margin-top: 10px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
.attention-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 16px; width: 100%; margin: 0; border: 0; border-radius: 0; padding: 16px 20px; text-align: start; background: transparent }
.attention-row:first-child { border-start-start-radius: inherit; border-start-end-radius: inherit }
.attention-row:last-child { border-end-start-radius: inherit; border-end-end-radius: inherit }
.attention-row + .attention-row, .home-recent li + li { border-top: 1px solid var(--line) }
.attention-info { flex: 1 1 9rem; min-width: 0; display: grid; gap: 3px; overflow-wrap: anywhere }
.attention-status, .attention-info small { font-size: 13px; font-weight: 550; line-height: 1.4; color: var(--muted) }
.attention-info strong { font-size: 18px; line-height: 1.3 }
.attention-action { display: inline-flex; align-items: center; gap: 8px; font-weight: 650 }
.attention-action::after, .home-recent button::after { content: ''; width: 7px; height: 7px; flex: none; border: solid currentColor; border-width: 1.6px 1.6px 0 0; rotate: 45deg }
.attention-action.next { color: var(--accent-ink) }
.attention-row img, .home-recent img, .blank-poster { flex: none; object-fit: contain; border-radius: 5px; background: var(--raised) }
.home-check { display: flex; align-items: baseline; flex-wrap: wrap; gap: 3px 12px; color: var(--muted); font-size: 13px }
.attention-list + .home-check { margin-top: 8px }
.home-bal { padding: 14px 18px; border: 1px solid var(--edge); border-radius: var(--field); background: var(--surface) }
.home-bal h2 { font-size: 16px }
.home-numbers, .home-links { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 18px }
.home-numbers { margin: 4px 0; color: var(--muted); font-size: 14px }
.home-numbers > div { display: flex; gap: 6px }
.home-numbers dd { margin: 0 }
.home-numbers strong { font-variant-numeric: tabular-nums; color: var(--text) }
.fund-note { font-size: 14px }
.home-section { margin-bottom: 6px }
a:not(.download-button) { display: inline-flex; min-height: 44px; align-items: center; color: var(--text); text-underline-offset: 3px }
.shop-home button.text-button { min-height: 44px; padding: 0; }
.home-recent { padding: 0; margin: 0; list-style: none; border-block: 1px solid var(--line) }
.home-recent button { width: 100%; border: 0; border-radius: 0; display: flex; justify-content: flex-start; text-align: left; padding: 10px 4px; gap: 16px; background: transparent }
.home-recent img, .blank-poster { width: 48px; height: 60px }
.home-recent button > span:last-child { flex: 1; min-width: 0 }
.home-recent strong { display: block }
.home-recent .badge { margin-top: 4px }
.home-recent button::after { color: var(--faint); margin-inline: 8px }
.home-links { margin-top: 24px; padding: 4px 0; border-top: 1px solid var(--line); font-size: 14px; }
.home-links a { color: var(--muted) }
.recent-posters .empty { text-align: start; margin: 0 }
.recent-posters .empty p { margin-top: 4px; font-size: 14px; color: var(--muted) }
@media (hover: hover) {
  .attention-row:hover:not(:disabled), .home-recent button:hover:not(:disabled) { background: var(--active) }
}
@media (width <= 540px) {
  .home-head { row-gap: 2px }
  .home-guide { margin-inline-start: auto }
  .attention-row { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px 14px; padding: 14px 16px; }
  .attention-info, .attention-action { grid-column: 2; }
  .attention-row img { grid-row: 1 / 3 }
  .attention-row:not(:has(img)) > span { grid-column: 1 / -1 }
}
</style>
