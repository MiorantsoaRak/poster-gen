<script setup lang="ts">
// « Libre » : the seller's own words go to the image model, on the chat's shell (style.css .chat, as ChatView.vue): a
// thread, a pinned composer, the version beside it, one review before the file. Its logic is its own: there is no
// product to read, no recap, no layer.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, mutation, retained, displayUrl, upload } from './api'
import { nextRole, swapRole, type Role } from './chat'
import { DRAW_TIME, ended } from './generation'

interface Turn { words: string; status: string; error_code: string | null; credit: string | null; render_id: string | null; png_sha256: string | null }
interface Thread {
  revision: number; status: string; photos: string[]; turns: Turn[]
  document: { render_id: string | null; reference: string | null; default_style: boolean; offer: { title: string } }
  confirmation: { download_url: string } | null
}
interface Version extends Turn { number: number; render_id: string }
interface Unsent { id: string; role: Role; file: File; url: string; status: 'sending' | 'done' | 'failed'; asset?: string; error: string }
// A photo here need not be a product: « Photo ». The reference keeps the name it has everywhere else.
const NAMES: Record<Role, string> = { product: 'Photo', inspiration: 'Modèle de style' }
const FULL = 'Trois photos et un modèle de style au plus.'

const props = defineProps<{ id: string | null; publish: boolean; active: boolean; height: number }>()
const emit = defineEmits<{
  charge: [edit: boolean, again: boolean, run: () => Promise<void>]
  created: [id: string]
  changed: []
}>()
const thread = ref<Thread>(), tray = ref<Unsent[]>([]), style = ref(true), text = ref(''), error = ref('')
const working = ref(false), readFailed = ref(false), typing = ref(false), listed = ref(false)
const looked = ref<string | null>(null), reviewing = ref<Version | null>(null), seen = ref<string | null>(null), imageFailed = ref(false)
const root = ref<HTMLElement>(), log = ref<HTMLElement>(), panel = ref<HTMLElement>(), field = ref<HTMLTextAreaElement>(), picker = ref<HTMLInputElement>(), height = ref(0)

// Versions are numbered among the images made: a failed request takes no number.
const versions = computed(() => {
  let number = 0
  return (thread.value?.turns ?? []).flatMap(turn => turn.render_id ? [{ ...turn, number: ++number } as Version] : [])
})
const current = computed(() => versions.value.find(version => version.render_id === thread.value?.document.render_id))
const shown = computed(() => versions.value.find(version => version.render_id === looked.value) ?? current.value)
const confirmed = computed(() => !!thread.value?.confirmation)
const last = computed(() => thread.value?.turns.at(-1))
const waiting = computed(() => ['queued', 'running'].includes(last.value?.status ?? ''))
const sending = computed(() => tray.value.some(entry => entry.status !== 'done'))
const locked = computed(() => working.value || waiting.value || readFailed.value || (!!props.id && !thread.value) || thread.value?.status === 'abandoned')
const stateOf = (version: Version) => version !== current.value ? 'remplacée' : confirmed.value ? 'confirmée' : 'à vérifier'
const mods = computed(() => versions.value.map(version => ({ version, label: version.number === 1 ? 'Première affiche' : version.words, state: stateOf(version) })))
const preview = (version: Version) => `/api/renders/${version.render_id}/preview`
const errorText = (reason: unknown) => reason instanceof Error ? reason.message : 'Impossible de terminer cette action. Réessayez.'
/** What the review lists: every request that made an image, up to this version, in the seller's own words. */
const asked = (version: Version) => versions.value.filter(item => item.number <= version.number).map(item => item.words)

let reads = 0, alive = true, timer: ReturnType<typeof setTimeout>
async function refresh() {
  const read = ++reads
  if (!props.id || !props.active) return
  clearTimeout(timer)
  try {
    const value = await api<Thread>(`/api/free-creations/${props.id}`, { quiet: true, timeout: 20000 })
    if (!alive || read !== reads) return
    const wasWaiting = waiting.value
    thread.value = value
    readFailed.value = false; error.value = ''
    if (waiting.value) timer = setTimeout(refresh, 1600)
    else if (wasWaiting) { looked.value = null; emit('changed') }
  } catch (reason) {
    if (alive && read === reads) { readFailed.value = true; error.value = errorText(reason) }
  }
}
watch(() => props.active, active => {
  if (active) void refresh()
  else { reads++; clearTimeout(timer) }
}, { immediate: true })

// ── the images of the first request ──────────────────────────────────────────────────────────────────────
const images = (data: DataTransfer | null) => [...(data?.files ?? [])].filter(file => file.type.startsWith('image/'))
function pasted(event: ClipboardEvent) {
  const files = images(event.clipboardData)
  if (files.length) { event.preventDefault(); take(files) }
}
function take(files: File[]) {
  if (props.id) return  // the images belong to the first request; later ones change the image made
  error.value = ''
  for (const file of files) {
    const role = nextRole(tray.value)
    if (!role) { error.value = FULL; break }
    tray.value.push({ id: crypto.randomUUID(), role, file, url: URL.createObjectURL(file), status: 'sending', error: '' })
    void sendFile(tray.value[tray.value.length - 1])
  }
}
function attach(event: Event) {
  const input = event.target as HTMLInputElement
  take([...(input.files ?? [])]); input.value = ''
}
// The server keeps an image under its role: a role changed is the image sent again.
async function sendFile(entry: Unsent) {
  Object.assign(entry, { status: 'sending', error: '', asset: undefined })
  try { Object.assign(entry, { asset: (await upload(entry.file, entry.role === 'product' ? 'original' : 'style', 45000)).asset, status: 'done' }) }
  catch (reason) { Object.assign(entry, { status: 'failed', error: reason instanceof Error ? reason.message : 'Envoi impossible. Réessayez.' }) }
}
function swap(entry: Unsent) {
  const next = swapRole(tray.value, entry.id)
  if (next === tray.value) { error.value = FULL; return }
  for (const [index, item] of tray.value.entries()) if (item.role !== next[index].role) { item.role = next[index].role; void sendFile(item) }
}
function drop(entry: Unsent) { URL.revokeObjectURL(entry.url); tray.value = tray.value.filter(item => item !== entry) }

// ── a request: one image, one credit, asked in the app's own dialog ──────────────────────────────────────
function ask(words: string) {
  words = words.trim()
  if (locked.value || sending.value || !words) return
  const path = props.id ? `/api/free-creations/${props.id}/turns` : '/api/free-creations'
  const body = props.id ? { words } : {
    words, photos: tray.value.filter(entry => entry.role === 'product').map(entry => entry.asset),
    reference: tray.value.find(entry => entry.role === 'inspiration')?.asset ?? null, default_style: style.value }
  const revision = thread.value?.revision
  emit('charge', !!current.value, retained(path), async () => {
    if (!alive) return
    working.value = true; error.value = ''
    try {
      const result = await mutation<{ creation_id: string }>(path, body, revision)
      if (!alive) return
      if (words === text.value.trim()) { text.value = ''; void nextTick(grow) }
      emit('changed')
      if (props.id) await refresh()
      else emit('created', result.creation_id)
    } catch (reason) {
      const message = errorText(reason)
      if (props.id) await refresh()
      error.value = message
    } finally { working.value = false }
  })
}

// ── the review: the image, the photos and the seller's requests together, then the file ──────────────────
function review(version: Version) { seen.value = null; imageFailed.value = false; reviewing.value = version }
const reviewed = computed(() => reviewing.value && reviewing.value.render_id === current.value?.render_id ? confirmed.value ? 'confirmed' : 'check' : 'earlier')
const mayConfirm = computed(() => reviewed.value === 'check' && seen.value === reviewing.value?.render_id && !working.value && !waiting.value)
async function confirm(then: 'download' | 'publish' | 'library') {
  const version = reviewing.value
  if (!version || !mayConfirm.value) return
  working.value = true; error.value = ''
  try {
    // One reading of the whole image answers the four points of the shared confirmation.
    await mutation(`/api/creations/${props.id}/confirmations`, { render_id: version.render_id, png_sha256: version.png_sha256,
      checks: { framing: true, content: true, identity: true, readability: true } }, thread.value?.revision)
    if (!alive) return
    await refresh(); emit('changed')
    const file = thread.value?.confirmation?.download_url
    panel.value?.scrollTo(0, 0)  // the panel now says « Affiche confirmée », from its top
    if (then === 'publish') { reviewing.value = null; window.location.hash = `publier-${props.id}` }
    else if (then === 'download' && file) Object.assign(document.createElement('a'), { href: file, download: '' }).click()
  } catch (reason) { error.value = errorText(reason) }
  finally { working.value = false }
}
function correct() { reviewing.value = null; void nextTick(() => field.value?.focus()) }
// The panel in front takes the focus and gives it back; Tab goes round inside (as App.vue's and ShopPublish.vue's).
const vModal = {
  mounted(el: HTMLElement & { back?: Element | null }) { el.back = document.activeElement; el.tabIndex = -1; (el.querySelector<HTMLElement>('[data-focus]') ?? el).focus() },
  unmounted(el: HTMLElement & { back?: Element | null }) { (el.back as HTMLElement | null)?.focus?.() },
}
function keepTab(event: KeyboardEvent) {
  const dialog = event.currentTarget as HTMLElement, controls = [...dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]')].filter(control => control.checkVisibility())
  const at = document.activeElement, to = event.shiftKey ? (at === controls[0] || at === dialog ? controls.at(-1) : null) : at === controls.at(-1) ? controls[0] : null
  if (to) { event.preventDefault(); to.focus() }
}
defineExpose({ modal: computed(() => !!reviewing.value), title: computed(() => thread.value?.document.offer.title ?? '') })

// ── the screen: what is left of the visible height, the composer always in view (as ChatView.vue) ────────
function measure() {
  if (!root.value) return
  const bottom = parseFloat(getComputedStyle(document.body).paddingBottom) || 0
  height.value = Math.max(0, Math.floor(props.height - root.value.getBoundingClientRect().top - window.scrollY - bottom - 12))
}
const resized = () => nextTick(measure)
function focused() { typing.value = matchMedia('(pointer: coarse)').matches }
function blurred() { setTimeout(() => { if (document.activeElement !== field.value) typing.value = false }, 150) }
function grow() { const area = field.value; if (area) { area.style.height = 'auto'; area.style.height = `${area.scrollHeight}px` } }
watch(() => [props.height, props.active, typing.value, !!shown.value, listed.value, !!thread.value], resized, { flush: 'post' })
watch(() => [thread.value?.turns.length, last.value?.status], () => nextTick(() => { if (log.value) log.value.scrollTop = log.value.scrollHeight }), { flush: 'post' })
onMounted(() => { window.addEventListener('resize', resized); resized() })
onBeforeUnmount(() => { alive = false; clearTimeout(timer); window.removeEventListener('resize', resized); tray.value.forEach(entry => URL.revokeObjectURL(entry.url)) })
</script>

<template>
  <section ref="root" class="chat" :class="{ 'has-poster': !!shown, typing, welcome: !id }" :style="{ height: `${height}px` }" aria-label="Création libre">
    <aside v-if="shown" class="chat-side" :inert="!!reviewing">
      <button type="button" class="chat-poster" aria-label="Agrandir l’affiche" @click="review(shown)"><img :src="preview(shown)" :alt="`Affiche, version ${shown.number}`" /></button>
      <p><b>Version {{ shown.number }} · {{ stateOf(shown) }}</b><span translate="no">{{ thread?.document.offer.title }}</span></p>
      <button type="button" class="mods-toggle" :aria-expanded="listed" aria-controls="libre-mods" @click="listed = !listed">Modifications ({{ mods.length }})</button>
      <div id="libre-mods" class="mods" :class="{ open: listed }" role="group" aria-label="Modifications">
        <h2>Modifications</h2>
        <button v-for="line in mods" :key="line.version.render_id" type="button" class="mod" :aria-current="line.version === shown || undefined" @click="looked = line.version.render_id"><i>V{{ line.version.number }}</i><span translate="no">{{ line.label }}</span><small :class="{ approved: line.state === 'confirmée' }">{{ line.state[0].toUpperCase() + line.state.slice(1) }}</small></button>
      </div>
    </aside>
    <div ref="log" class="chat-thread" :inert="!!reviewing" role="log" aria-live="polite" aria-label="Conversation" tabindex="0">
      <div v-if="!id" class="hello">
        <img src="/favicon.svg" width="56" height="56" alt="" />
        <p class="hello-q">Que voulez-vous créer ?</p>
        <p>Décrivez l’affiche avec vos mots : les produits, les textes et les prix à écrire. Vous pouvez joindre des photos et un modèle de style.</p>
        <small>Le format Publication est déjà choisi pour Facebook et le téléchargement.</small>
      </div>
      <div v-else-if="!thread" class="bubble bot"><p v-if="!readFailed" role="status">Ouverture de la conversation…</p><template v-else><p class="why" role="alert">{{ error }}</p><div class="acts"><button type="button" class="primary" @click="refresh">Réessayer</button></div></template></div>
      <template v-for="(turn, index) in thread?.turns" :key="index">
        <div class="bubble me">
          <div v-if="index === 0 && (thread!.photos.length || thread!.document.reference)" class="pics">
            <span v-for="(photo, n) in thread!.photos" :key="photo" class="pic"><img :src="displayUrl('/api/assets/' + photo)" width="68" height="68" :alt="`Photo ${n + 1}`" />Photo {{ n + 1 }}</span>
            <span v-if="thread!.document.reference" class="pic"><img :src="displayUrl('/api/assets/' + thread!.document.reference)" width="68" height="68" alt="Modèle de style" />Modèle de style</span>
          </div>
          <p class="lines" translate="no">{{ turn.words }}</p>
        </div>
        <div v-for="version in versions.filter(item => item.render_id === turn.render_id)" :key="version.render_id" class="bubble bot">
          <button type="button" class="chat-poster small" aria-label="Agrandir l’affiche" @click="review(version)"><img :src="preview(version)" :alt="`Affiche, version ${version.number}`" /></button>
          <template v-if="version === current">
            <p>Version {{ version.number }} prête. Les photos, les textes et les montants sont-ils exacts ?</p>
            <p v-if="confirmed" class="chat-state approved">Confirmée</p>
            <div v-if="!waiting" class="acts">
              <button v-if="!confirmed" type="button" class="primary" @click="review(version)">Vérifier</button>
              <template v-else>
                <a class="download-button" :href="thread!.confirmation!.download_url" download>Télécharger le PNG</a>
                <a v-if="publish" class="download-button secondary" :href="`#publier-${id}`">Publier sur ma Page</a>
              </template>
            </div>
          </template>
          <small v-else>Version {{ version.number }} · une version plus récente la remplace.</small>
        </div>
        <div v-if="!turn.render_id && !['queued', 'running', 'succeeded'].includes(turn.status)" class="bubble bot">
          <p>{{ ended({ status: turn.status, kind: 'scene', error_code: turn.error_code, credit: turn.credit }) }}</p>
          <div v-if="turn === last" class="acts"><button type="button" class="primary" :disabled="locked" @click="ask(turn.words)">Réessayer</button></div>
          <small v-if="turn === last">1 crédit pour la nouvelle image.</small>
        </div>
      </template>
      <p v-if="thread?.status === 'abandoned'" class="why" role="status">Cette affiche a été retirée de la liste. Remettez-la dans la liste depuis « Mes affiches » pour la modifier.</p>
      <div v-if="waiting" class="bubble bot chat-wait"><i aria-hidden="true" /><p>{{ last?.status === 'queued' ? 'Je prépare l’image…' : `Je dessine l’affiche… ${DRAW_TIME}` }}</p></div>
    </div>
    <form v-if="thread?.status !== 'abandoned'" class="composer" :inert="!!reviewing" @submit.prevent="ask(text)" @paste="pasted" @dragover.prevent @drop.prevent="take(images($event.dataTransfer))">
      <div v-if="!id" class="kit-row"><label class="switch"><input v-model="style" type="checkbox" :disabled="locked" />Style de base pour ce que vous ne précisez pas</label></div>
      <div v-if="tray.length" class="tray">
        <span v-for="entry in tray" :key="entry.id" class="pic" :aria-busy="entry.status === 'sending' || undefined">
          <img :src="entry.url" width="68" height="68" :alt="NAMES[entry.role]" />
          <button v-if="entry.status === 'failed'" type="button" class="pic-role" @click="sendFile(entry)">Réessayer</button>
          <button v-else type="button" class="pic-role" :class="entry.role" :disabled="entry.status === 'sending' || locked" :aria-label="`${NAMES[entry.role]} : marquer comme ${entry.role === 'product' ? 'modèle de style' : 'photo'}`" title="Toucher pour changer" @click="swap(entry)">{{ NAMES[entry.role] }}</button>
          <button type="button" class="pic-drop" aria-label="Retirer cette image" :disabled="locked" @click="drop(entry)"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
        </span>
      </div>
      <p v-for="entry in tray.filter(item => item.error)" :key="entry.id" class="why" role="alert">{{ entry.error }}</p>
      <p v-if="error && (thread || !id)" class="why" role="alert">{{ error }}</p>
      <textarea ref="field" v-model="text" rows="1" maxlength="6000" enterkeyhint="send" aria-label="Votre message" :readonly="locked" :placeholder="current ? 'Dites ce qu’il faut corriger.' : 'Décrivez votre affiche.'"
        @input="grow" @keydown.enter.exact.prevent="ask(text)" @focus="focused" @blur="blurred" />
      <div class="tools">
        <button v-if="!id" type="button" class="ghost attach first-photos" aria-label="Ajouter des photos" :disabled="locked" @click="picker?.click()"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l9-9a3.7 3.7 0 0 1 5.2 5.2l-9 9a1.8 1.8 0 0 1-2.6-2.6l8.3-8.3" /></svg><span class="lbl">Photos</span></button>
        <small v-if="!locked && text.trim()">1 crédit</small>
        <button type="submit" class="send" aria-label="Envoyer" :aria-busy="working || sending || undefined" :disabled="locked || sending || !text.trim()" @mousedown.prevent><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg></button>
      </div>
      <input v-if="!id" ref="picker" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden aria-label="Photos à joindre" @change="attach" />
    </form>
    <section v-if="reviewing" ref="panel" v-modal class="review-panel final-preview" role="dialog" aria-modal="true" aria-labelledby="libre-review-title" @keydown.esc="reviewing = null" @keydown.tab="keepTab">
      <div class="section-heading">
        <div>
          <h2 id="libre-review-title" tabindex="-1">{{ reviewed === 'check' ? 'Vérifier votre affiche' : reviewed === 'confirmed' ? 'Affiche confirmée' : `Version ${reviewing.number}, remplacée` }}</h2>
          <p class="lede" translate="no">{{ thread?.document.offer.title }}</p>
        </div>
        <button type="button" class="ghost" @click="reviewing = null">Fermer</button>
      </div>
      <div class="final-grid file-layout" :class="{ inspecting: reviewed === 'check' }">
        <div class="file-controls">
          <dl class="facts file-facts"><div><dt>Format</dt><dd>Publication <small>1080 × 1350 px · PNG</small></dd></div></dl>
          <div v-if="reviewed === 'check' && thread?.photos.length" class="file-originals">
            <h3>{{ thread.photos.length === 1 ? 'Photo d’origine' : 'Photos d’origine' }}</h3>
            <div><a v-for="(photo, n) in thread.photos" :key="photo" :href="displayUrl('/api/assets/' + photo)" target="_blank" rel="noopener"><img :src="displayUrl('/api/assets/' + photo)" width="80" height="80" :alt="`Photo originale ${n + 1} à comparer`" /></a></div>
          </div>
          <div v-if="reviewed === 'confirmed'" class="file-outputs">
            <a v-if="publish" class="primary" :href="`#publier-${id}`" @click="reviewing = null">Publier sur ma Page</a>
            <a class="download-button" :class="{ secondary: publish }" :href="thread!.confirmation!.download_url" download>Télécharger le PNG</a>
          </div>
          <p v-if="reviewed === 'earlier'" class="help">Une version plus récente la remplace : c’est elle que vous confirmez et téléchargez.</p>
        </div>
        <div class="shot"><a :href="preview(reviewing)" target="_blank" rel="noopener"><img :key="reviewing.render_id" :src="preview(reviewing)" width="1080" height="1350" alt="Aperçu final du fichier à télécharger" @load="seen = reviewing.render_id" @error="imageFailed = true" /><small>Agrandir l’affiche</small></a></div>
        <div class="file-details">
          <template v-if="reviewed === 'check'">
            <p class="review-instruction">Comparez l’image à vos photos. L’IA a dessiné tous les textes : relisez chaque mot et chaque montant, et vérifiez qu’elle n’a rien ajouté.</p>
            <details open><summary>Vos demandes, à retrouver dans l’image</summary><ul class="points"><li v-for="(words, n) in asked(reviewing)" :key="n" translate="no">{{ words }}</li></ul></details>
            <p v-if="imageFailed" class="why" role="alert">L’image n’a pas pu être chargée. Fermez et rouvrez la vérification.</p>
            <p v-else-if="seen !== reviewing.render_id" class="help" role="status">Chargement de l’image à vérifier…</p>
            <p v-if="error" class="why" role="alert">{{ error }}</p>
            <p class="help review-consent">Retrouvez-la ensuite dans « Mes affiches ».</p>
            <div class="file-outputs">
              <button v-if="publish" type="button" class="primary" :disabled="!mayConfirm" @click="confirm('publish')">Confirmer et préparer la publication</button>
              <button type="button" :class="publish ? 'secondary' : 'primary'" :disabled="!mayConfirm" @click="confirm('download')">Confirmer et télécharger le PNG</button>
            </div>
            <div class="review-options">
              <button type="button" class="text-button" :disabled="!mayConfirm" @click="confirm('library')">Confirmer pour plus tard</button>
              <button type="button" class="text-button" @click="correct">Corriger l’affiche</button>
            </div>
          </template>
        </div>
      </div>
    </section>
  </section>
</template>
