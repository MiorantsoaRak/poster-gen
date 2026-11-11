<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import PosterCanvas from './PosterCanvas.vue'
import { api, mutation, upload } from './api'
import { DraftSaver } from './autosave'
import { copy, fitCrop, FORMATS, History, parsePrice, setIdentity, type Creation, type FontId, type Layer, type PosterDocument, type Visual } from './document'
import type { LayoutIssue } from './canvas'

interface Profile { revision: number; name: string | null; contact: string | null; logo_asset: string | null }
interface Capabilities { image_mode: string; planner_mode: string; planner_available: boolean; scene_estimate_micros: number; plan_estimate_micros: number; texture_estimate_micros: number }
interface Job { id: string; kind: string; status: string; result_ref: string | null; error_code: string | null }
const roleNames: Record<string, string> = { title: 'Titre', price: 'Prix', shop_name: 'Nom de la boutique', contact: 'Contact', logo: 'Logo', product: 'Produit' }
const checkNames: Record<string, string> = { colour: 'Couleurs fidèles', markings: 'Marque et inscriptions fidèles', hardware: 'Boutons et détails fidèles', shape: 'Forme et proportions fidèles', extras_text: 'Aucun ajout indésirable', integration: 'Intégration naturelle dans la scène' }
const authenticated = ref(false), checking = ref(true), password = ref(''), error = ref(''), notice = ref(''), busy = ref(false)
const caps = ref<Capabilities>(), library = ref<{ id: string; title: string; variant: string }[]>([])
const profile = reactive<Profile>({ revision: 1, name: null, contact: null, logo_asset: null })
let profileSaved = ''
const intake = reactive({ name: '', variant: 'Conforme à la photo', price: '', confirmed: false })
const include = reactive({ logo: false, shop_name: true, contact: true })
let pendingInput: { signature: string; id: string } | null = null
const photos = ref<{ asset: string; warnings: string[] }[]>([])
const creation = ref<Creation | null>(null), doc = shallowRef<PosterDocument | null>(null), selected = ref<string | null>(null)
const visuals = ref<Visual[]>([]), direction = ref('Studio clair et épuré, dégradé doux, grandes courbes discrètes derrière le produit.'), plannerMode = ref<'fixed' | 'claude'>('fixed')
const styleReference = ref<string | null>(null)
// The image model sets brand, product name and subtitle itself; the price stays an exact editable layer.
const headline = ref({ on: true, signature: true, price: true, brand: '', subtitle: '', accent_word: '', accent_colour: '#1E6FE0' })
const profileValue = (role: 'shop_name' | 'contact') => doc.value?.include[role] ? (role === 'shop_name' ? doc.value.brand_snapshot.name : doc.value.brand_snapshot.contact) ?? undefined : undefined
// The image model draws one short line each; anything else stays an editable layer.
const signable = computed(() => (['shop_name', 'contact'] as const).some(role => profileValue(role)) && (['shop_name', 'contact'] as const).every(role => { const value = profileValue(role); return !value || (value.length <= 80 && !/["\r\n]/.test(value)) }))
// Looks measured on real shop products (docs/project/reviews/style-study-2026-11-11.md): the owner picks a picture, not a prompt.
const tint = (hex: string) => '#' + [1, 3, 5].map(i => Math.round(parseInt(hex.slice(i, i + 2), 16) * .14 + 255 * .86).toString(16).padStart(2, '0')).join('').toUpperCase()
const LOOKS = [
  { id: 'clair', label: 'Studio clair', image: '/styles/clair.jpg', direction: 'Studio clair et épuré, dégradé doux, grandes courbes discrètes derrière le produit.', palette: () => ['#FFFFFF', '#E6E7EB', '#55585F'] },
  { id: 'couleur', label: 'Aux couleurs du produit', image: '/styles/couleur.jpg', direction: 'Studio clair teinté de la couleur d’accent, dégradé doux, grandes courbes discrètes derrière le produit.', palette: () => ['#FFFFFF', tint(headline.value.accent_colour), headline.value.accent_colour.toUpperCase()] },
  { id: 'sombre', label: 'Luxe sombre', image: '/styles/sombre.jpg', direction: 'Fond noir charbon très sombre, fins arcs de lumière dorée chaude derrière le produit, ambiance luxe, léger reflet au sol.', palette: () => ['#0B0B0D', '#1B1B20', '#C8A45A'] },
  { id: 'libre', label: 'Décrire moi-même', image: null, direction: null, palette: null },
] as const
// Looks the shop made from posters it likes (Claude writes the brief once; it is reused from then on).
interface SavedLook { id: string; name: string; reference_asset: string; brief: { direction_fr: string; surface_fr: string; lighting: string; camera: string; palette: string[]; accent_colour: string; alignment: string } }
const savedLooks = ref<SavedLook[]>([]), lookName = ref(''), lookReference = ref<string | null>(null)
const look = ref<string>('clair')
const savedLook = computed(() => savedLooks.value.find(item => item.id === look.value))
function pickLook(id: string) {
  look.value = id
  const saved = savedLooks.value.find(item => item.id === id)
  if (saved) { direction.value = saved.brief.direction_fr; headline.value.accent_colour = saved.brief.accent_colour.toLowerCase(); return }
  const chosen = LOOKS.find(item => item.id === id)!
  if (chosen.direction) direction.value = chosen.direction
  if (id === 'sombre') headline.value.accent_colour = '#C8A45A'
}
// A reopened poster brings back what its scene was made with (brand, subtitle, accent, look), so that a new
// scene after a price change is the same poster and not a different one.
function restoreHeadline() {
  const drawn = currentVisual.value?.headline as Record<string, any> | null | undefined
  if (!drawn) return
  if (drawn.look_id && savedLooks.value.some(item => item.id === drawn.look_id)) pickLook(drawn.look_id)
  Object.assign(headline.value, { on: true, brand: drawn.brand ?? '', subtitle: drawn.subtitle ?? '', accent_word: drawn.accent_word ?? '',
    price: drawn.price_ar !== undefined, signature: drawn.shop_name !== undefined || drawn.contact !== undefined })
  if (/^#[0-9A-Fa-f]{6}$/.test(drawn.accent_colour ?? '')) headline.value.accent_colour = drawn.accent_colour.toLowerCase()
}
async function chooseLookReference(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) lookReference.value = (await upload(file, 'style')).asset
}
async function createLook() {
  await flush()
  const result = await mutation<any>(`/api/creations/${creation.value!.id}/looks`, { name: lookName.value.trim() || `Style ${savedLooks.value.length + 1}`, reference_asset: lookReference.value }, saver!.revision)
  follow({ id: result.job_id, kind: 'look', status: 'queued', result_ref: null, error_code: null })
}
// The owner's last look, colour and brand come back on the next poster ("same style as last time").
const STYLE_KEY = 'affiche.style'
try {
  const saved = JSON.parse(localStorage.getItem(STYLE_KEY) ?? 'null')
  if (saved && LOOKS.some(item => item.id === saved.look) && /^#[0-9A-Fa-f]{6}$/.test(saved.accent_colour)) {
    headline.value.accent_colour = saved.accent_colour; headline.value.brand = String(saved.brand ?? '').slice(0, 60); pickLook(saved.look)
    headline.value.accent_colour = saved.accent_colour
  }
} catch { /* private mode or damaged entry: start from the defaults */ }
function rememberStyle() {
  try { localStorage.setItem(STYLE_KEY, JSON.stringify({ look: look.value, accent_colour: headline.value.accent_colour, brand: headline.value.brand })) } catch { /* convenience only */ }
}
const shade = (hex: string) => '#' + [1, 3, 5].map(i => Math.round(parseInt(hex.slice(i, i + 2), 16) * .5).toString(16).padStart(2, '0')).join('').toUpperCase()
let autoPill = ''
// The look also dresses the price as the shop's dark pill. A pill the owner restyled by hand is left alone.
function stylePill() {
  const price = layout.value?.layers.find(layer => layer.role === 'price')
  if (!price || price.kind !== 'text' || look.value === 'libre') return
  if (price.price_badge && JSON.stringify(price.price_badge) !== autoPill) return
  const accent = headline.value.accent_colour.toUpperCase()
  const badge = look.value === 'sombre' ? { fill: '#111114', border_start: '#C8A45A', border_end: '#C8A45A' }
    : look.value === 'couleur' ? { fill: shade(accent), border_start: shade(accent), border_end: accent }
    : { fill: '#22262E', border_start: '#22262E', border_end: '#55585F' }
  if (price.price_badge && JSON.stringify(badge) === autoPill) return
  const [width, height] = FORMATS[format.value]
  autoPill = JSON.stringify(badge)
  edit(document => {
    const layer = document.formats[format.value]!.layers.find(item => item.role === 'price')
    if (layer?.kind !== 'text') return
    // Before the first scene the server centres this box in the plan's price band; afterwards keep its place.
    const placed = !!document.formats[format.value]!.scene.visual_id
    Object.assign(layer, { width: width / 2, height: 112, font_id: 'noto-sans', weight: 700, font_size: 62, fill: '#FFFFFF', align: 'center', outline: null, shadow: null, texture_effect_id: null, price_badge: badge },
      placed ? { x: layer.x + (layer.width - width / 2) / 2 } : { x: width / 4, y: height - 190 })
    // Shop name and contact follow the look too: white text would vanish on the light looks.
    for (const footer of document.formats[format.value]!.layers)
      if (footer.kind === 'text' && (footer.role === 'shop_name' || footer.role === 'contact'))
        Object.assign(footer, { fill: look.value === 'sombre' ? '#FFFFFF' : '#22262E', align: 'center', outline: null, shadow: null })
  })
}
const headlineBody = () => headline.value.on ? { headline: { brand: headline.value.brand.trim() || null, subtitle: headline.value.subtitle.trim() || null, accent_word: headline.value.accent_word.trim() || null, accent_colour: headline.value.accent_word.trim() ? headline.value.accent_colour.toUpperCase() : null, signature: headline.value.signature && signable.value, price: headline.value.price, ...(savedLook.value ? { look_id: savedLook.value.id } : {}) } } : {}
let savedPlanSnapshot = ''
const plan = ref<any>(null), job = ref<Job | null>(null), priceText = ref(''), refinement = ref('')
const finalPreview = ref<any>(null), confirmedDownload = ref(''), previewLoaded = ref(false)
const finalChecks = reactive({ framing: false, content: false, identity: false, readability: false }), warningsAccepted = ref(false)
const proposal = ref<any>(null), effect = ref<any>(null), polish = ref(''), acknowledgeContent = ref(false), previewPolish = ref(false)
const effectSources = ref<Record<string, string>>({})
const previewDoc = computed(() => {
  if (!previewPolish.value || !doc.value) return doc.value
  if (effect.value?.status === 'proposed') {
    const preview = copy(doc.value), layer = preview.formats[effect.value.format as keyof typeof preview.formats]?.layers.find(layer => layer.id === effect.value.layer_id)
    if (layer?.kind === 'text') layer.texture_effect_id = effect.value.id
    return preview
  }
  return proposal.value?.status === 'pending' ? proposal.value.after as PosterDocument : doc.value
})
const review = ref<Visual | null>(null), checks = reactive<Record<string, boolean>>({}), rejection = ref('')
const issues = ref<LayoutIssue[]>([]), canvasReady = ref(false), dragEnabled = ref(false)
const canvasHost = ref<HTMLElement>(), canvasWidth = ref(540), viewportHeight = ref(window.innerHeight), savingTick = ref(0)
let saver: DraftSaver | null = null, history = new History(), pollTimer: ReturnType<typeof setTimeout> | undefined, observer: ResizeObserver | undefined
const format = computed(() => doc.value?.primary_format ?? 'feed')
const layout = computed(() => doc.value?.formats[format.value])
const currentVisual = computed(() => visuals.value.find(item => item.id === layout.value?.scene.visual_id))
// The server refuses to export a hidden title unless the selected scene carries exactly the current one.
function toggleIdentity(document: PosterDocument, role: 'logo' | 'shop_name' | 'contact', enabled: boolean) {
  setIdentity(document, role, enabled)
  // Ticking back a name/contact that the current scene already shows must not add a second copy as a layer.
  const layer = document.formats[format.value]!.layers.find(item => item.role === role)
  if (layer && role !== 'logo' && currentVisual.value?.headline?.[role] !== undefined) layer.visible = false
}
const waiting = 'Une tâche est en cours : patientez quelques instants.'
const whyBusy = computed(() => job.value ? waiting : '')
const whyNoLook = computed(() => job.value ? waiting : !lookReference.value ? 'Choisissez d’abord une affiche modèle ci-dessus.' : '')
const whyNoDraft = computed(() => !photos.value.length ? 'Ajoutez au moins une photo du produit.' : !intake.confirmed ? 'Cochez la case « Les photos correspondent… » pour continuer.' : '')
const whyNoExport = computed(() => job.value ? waiting
  : !currentVisual.value ? 'Générez d’abord une scène à l’étape 02.'
  : currentVisual.value.status === 'pending_review' ? 'Comparez d’abord la scène à votre photo et approuvez la fidélité du produit.'
  : currentVisual.value.status === 'rejected' ? 'Cette scène a été refusée : choisissez une autre version ou générez-en une nouvelle.'
  : staleHeadline.value ? 'Un texte dessiné dans l’image a changé : générez une nouvelle scène.'
  : issues.value.some(issue => issue.blocking) ? 'Corrigez d’abord les éléments signalés sous l’affiche.'
  : previewPolish.value ? 'Appliquez ou refusez d’abord l’ajustement en cours.' : '')
const nextStep = computed(() => job.value && ['scene', 'refine'].includes(job.value.kind) ? 'Votre scène est en cours de création. Cela prend environ une minute.'
  : !currentVisual.value ? 'Vérifiez les textes (01), choisissez un style (02), puis appuyez sur « Générer la scène ».'
  : currentVisual.value.status === 'pending_review' ? 'Comparez le produit à votre photo, puis approuvez sa fidélité.'
  : currentVisual.value.status === 'approved' ? 'Dernière étape (03) : vérifiez l’aperçu final, puis téléchargez votre affiche.'
  : 'Choisissez une autre version sous l’affiche, ou générez une nouvelle scène.')
const staleTitle = computed(() => { const baked = currentVisual.value?.headline?.title; return baked !== undefined ? baked !== doc.value?.offer.title : !!layout.value?.layers.some(layer => layer.role === 'title' && !layer.visible) })
const staleSignature = computed(() => (['shop_name', 'contact'] as const).some(role => { const baked = currentVisual.value?.headline?.[role]; return baked !== undefined ? baked !== profileValue(role) : !!profileValue(role) && !!layout.value?.layers.some(layer => layer.role === role && !layer.visible) }))
const stalePrice = computed(() => { const baked = currentVisual.value?.headline?.price_ar; return baked !== undefined ? baked !== doc.value?.offer.price_ar : !!layout.value?.layers.some(layer => layer.role === 'price' && !layer.visible) })
const staleHeadline = computed(() => !!currentVisual.value && (staleTitle.value || staleSignature.value || stalePrice.value))
// A hidden layer (the title, once the image carries it) has no properties panel.
const chosen = computed(() => layout.value?.layers.find(layer => layer.id === selected.value && layer.visible))
const scale = computed(() => Math.min(canvasWidth.value / FORMATS[format.value][0], window.innerWidth > 850 ? Math.max(.25, (viewportHeight.value - 300) / FORMATS[format.value][1]) : .62, .62))
const sources = computed(() => Object.fromEntries([
  ...Object.entries(effectSources.value).map(([id, url]) => [id, `${url}?prepared=true`]),
  ...visuals.value.map(item => [`scene:${item.id}`, `${item.image_url}?prepared=true`]),
  ...Object.values(doc.value?.formats ?? {}).flatMap(layout => layout.layers.filter(layer => layer.kind !== 'text').map(layer => [(layer as any).asset, `/api/assets/${(layer as any).asset}?prepared=true`])),
]))
const saveState = computed(() => { savingTick.value; return saver?.state ?? 'saved' })
const saveLabel = computed(() => ({ saved: 'Enregistré', dirty: 'Modifications en attente', saving: 'Enregistrement…', failed: 'Échec de l’enregistrement', conflict: 'Une autre version existe' }[saveState.value]))
const dollars = (micros = 0) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'USD' }).format(micros / 1e6)

async function perform(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await action() } catch (reason) { error.value = reason instanceof Error ? reason.message : 'La demande a échoué.' }
  finally { busy.value = false }
}
async function loadShop() {
  const [saved, capabilities, list] = await Promise.all([api<Profile>('/api/shop-profile'), api<Capabilities>('/api/capabilities'), api<{ items: typeof library.value }>('/api/creations')])
  Object.assign(profile, saved); profileSaved = JSON.stringify(saved); caps.value = capabilities; library.value = list.items
  savedLooks.value = (await api<{ items: SavedLook[] }>('/api/looks')).items
  // The remembered style may be one of the shop's own looks, known only now.
  try { const remembered = JSON.parse(localStorage.getItem(STYLE_KEY) ?? 'null'); if (savedLooks.value.some(item => item.id === remembered?.look)) pickLook(remembered.look) } catch { /* convenience only */ }
  include.shop_name = !!saved.name; include.contact = !!saved.contact; include.logo = !!saved.logo_asset
}
async function signIn() {
  await api('/api/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: password.value }) })
  password.value = ''; authenticated.value = true; await loadShop()
}
async function saveProfile() {
  if (JSON.stringify(profile) === profileSaved) return
  const result = await mutation<Profile>('/api/shop-profile', { name: profile.name?.trim() || null, contact: profile.contact?.trim() || null, logo_asset: profile.logo_asset }, profile.revision, undefined, 'PUT')
  Object.assign(profile, result); profileSaved = JSON.stringify(result)
}
async function choosePhotos(event: Event) {
  const files = [...((event.target as HTMLInputElement).files ?? [])]
  if (!files.length || files.length > 3) throw new Error('Choisissez une à trois photos du même produit.')
  const uploaded = []
  for (const file of files) uploaded.push(await upload(file, 'original'))
  photos.value = uploaded
}
async function chooseLogo(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) { profile.logo_asset = (await upload(file, 'logo')).asset; include.logo = true }
}
async function chooseStyle(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) styleReference.value = (await upload(file, 'style')).asset
}
async function createPoster() {
  if (!photos.value.length || !intake.confirmed) throw new Error('Ajoutez une photo et confirmez le produit.')
  const price = parsePrice(intake.price)
  await saveProfile()
  const inputBody = { name: intake.name, variant: intake.variant, photo_assets: photos.value.map(photo => photo.asset) }
  const signature = JSON.stringify(inputBody)
  if (pendingInput?.signature !== signature) pendingInput = { signature, id: (await mutation<{ id: string }>('/api/product-inputs', inputBody)).id }
  const input = pendingInput
  const result = await mutation<Creation>('/api/creations', { input_id: input.id, offer: { title: intake.name, price_ar: price }, brand_selection: include, primary_format: 'feed' })
  await adopt(result)
}
async function adopt(result: Creation) {
  finalPreview.value = null; confirmedDownload.value = ''; previewLoaded.value = false
  clearTimeout(pollTimer); job.value = null; review.value = null; proposal.value = null; effect.value = null; previewPolish.value = false
  saver?.dispose(); creation.value = result; doc.value = copy(result.document); priceText.value = String(result.document.offer.price_ar)
  selected.value = result.document.formats[result.document.primary_format]!.layers.find(layer => layer.role === 'title')?.id ?? null
  history = new History(); plan.value = null; styleReference.value = null
  saver = new DraftSaver(result.revision, request => mutation<Creation>(`/api/creations/${result.id}`, request.document, request.revision, request.key, 'PUT'), () => { savingTick.value++; if (saver?.error) error.value = saver.error })
  window.location.hash = result.id
  await refreshVisuals(); styleReference.value = currentVisual.value?.style_reference_asset ?? null
  restoreHeadline()
  await refreshEffects(); await nextTick()
  observer?.disconnect()
  if (canvasHost.value) { observer = new ResizeObserver(entries => { canvasWidth.value = entries[0].contentRect.width }); observer.observe(canvasHost.value) }
  const jobs = await api<{ items: Job[] }>(`/api/creations/${result.id}/jobs`)
  const previousRender = jobs.items.find(item => item.kind === 'render' && item.status === 'succeeded')
  if (previousRender) openFinalPreview(await api(`/api/renders/${previousRender.result_ref}`))
  const active = jobs.items.find(item => ['queued', 'running'].includes(item.status))
  const previousProposal = jobs.items.find(item => item.kind === 'text_patch' && item.status === 'succeeded')
  if (previousProposal) proposal.value = await api(`/api/text-proposals/${previousProposal.result_ref}`)
  const previousEffect = jobs.items.find(item => item.kind === 'text_texture' && item.status === 'succeeded')
  if (previousEffect) {
    effect.value = await api(`/api/text-effects/${previousEffect.result_ref}`)
    effectSources.value[`effect:${effect.value.id}`] = effect.value.image_url
  }
  if (active) follow(active)
  else {
    const previousPlan = jobs.items.find(item => item.kind === 'plan' && item.status === 'succeeded')
    if (previousPlan) acceptPlan(await api(`/api/plans/${previousPlan.result_ref}`))
  }
}
async function openCreation(id: string) { await flush(); await adopt(await api<Creation>(`/api/creations/${id}`)) }
async function fresh() { await flush(); finalPreview.value = null; confirmedDownload.value = ''; saver?.dispose(); doc.value = null; creation.value = null; plan.value = null; clearTimeout(pollTimer); job.value = null; window.location.hash = ''; await loadShop() }
async function refreshVisuals() {
  const id = creation.value?.id
  if (!id) return
  const result = await api<{ items: Visual[] }>(`/api/creations/${id}/visuals`)
  if (creation.value?.id === id) visuals.value = result.items
}
async function discardAndReload() { await adopt(await api<Creation>(`/api/creations/${creation.value!.id}`)) }
function edit(change: (document: PosterDocument) => void, mergeKey = '') {
  if (!doc.value) return
  try {
    const next = copy(doc.value); change(next); previewPolish.value = false; history.record(doc.value, mergeKey); doc.value = next; saver!.queue(next); error.value = ''
  } catch (reason) { error.value = reason instanceof Error ? reason.message : 'Modification invalide.' }
}
function patchLayer(id: string, patch: Partial<Layer>, mergeKey = '') {
  edit(document => { Object.assign(document.formats[format.value]!.layers.find(layer => layer.id === id)!, patch) }, mergeKey)
}
function changeFont(event: Event) {
  if (chosen.value?.kind !== 'text') return
  const font_id = (event.target as HTMLSelectElement).value as FontId
  const weight = font_id === 'montserrat-black-italic' ? 900 : chosen.value.weight === 900 ? 700 : chosen.value.weight
  patchLayer(selected.value!, { font_id, weight })
}
function badgeColour(field: 'fill' | 'border_start' | 'border_end', event: Event) {
  if (chosen.value?.kind !== 'text' || !chosen.value.price_badge) return
  patchLayer(selected.value!, { price_badge: { ...chosen.value.price_badge, [field]: (event.target as HTMLInputElement).value } }, 'badge-colour')
}
function numeric(field: 'x' | 'y' | 'width' | 'height' | 'font_size', event: Event) {
  const value = Number((event.target as HTMLInputElement).value)
  const min = field === 'font_size' ? 24 : field === 'width' || field === 'height' ? 1 : -4000
  if (!Number.isFinite(value) || value < min || value > (field === 'font_size' ? 240 : 4000)) { error.value = 'Valeur hors limites.'; return }
  patchLayer(selected.value!, { [field]: value }, field)
}
function changePrice() { try { const value = parsePrice(priceText.value); edit(document => { document.offer.price_ar = value }, 'price') } catch (reason) { error.value = (reason as Error).message } }
async function flush() { if (doc.value && parsePrice(priceText.value) !== doc.value.offer.price_ar) throw new Error('Vérifiez le prix avant de continuer.'); await saver?.flush() }
function undo() { if (doc.value) { const previous = history.undo(doc.value); if (previous) { doc.value = previous; priceText.value = String(previous.offer.price_ar); saver!.queue(previous) } } }
function redo() { if (doc.value) { const next = history.redo(doc.value); if (next) { doc.value = next; priceText.value = String(next.offer.price_ar); saver!.queue(next) } } }
async function conflictCopy() {
  const result = await mutation<Creation>(`/api/creations/${creation.value!.id}/copies`, { source_revision: saver!.revision, reason: 'save_conflict', unsaved_document: doc.value })
  await adopt(result); notice.value = 'Vos modifications ont été conservées dans une copie.'
}
async function prepareScene() {
  await flush()
  const result = await mutation<any>(`/api/creations/${creation.value!.id}/plans`, { mode: plannerMode.value, direction: direction.value, format: format.value }, saver!.revision)
  if (result.job_id) follow({ id: result.job_id, kind: 'plan', status: 'queued', result_ref: null, error_code: null })
  else {
    acceptPlan(result)
    // The chosen look owns the colours of a simple composition; generateScene saves this as a plan revision.
    const brief = savedLook.value?.brief
    if (brief) {
      plan.value.plan.palette = brief.palette
      Object.assign(plan.value.plan.scene, { surface: brief.surface_fr, lighting: brief.lighting, camera: brief.camera })
    } else {
      const palette = LOOKS.find(item => item.id === look.value)?.palette
      if (palette) plan.value.plan.palette = palette()
    }
  }
}
// A signature drawn by the image model is two short lines. The default layer boxes reserve far more, which
// pushed the price band up onto the product (live Edge run 2); give the plan the real footprint instead.
function fitSignature() {
  if (!(headline.value.on && headline.value.signature && signable.value)) return
  const heights: Record<string, number> = { shop_name: 48, contact: 56 }
  const pending = (layer: Layer) => layer.role in heights && doc.value!.include[layer.role as 'shop_name' | 'contact'] && layer.height !== heights[layer.role]
  if (!layout.value?.layers.some(pending)) return
  edit(document => { for (const layer of document.formats[format.value]!.layers) if (pending(layer)) layer.height = heights[layer.role]! })
}
let planSignature = ''
// One tap for the simple composition. An unchanged request reuses its plan, so a retry after a lost
// response sends the same scene body and key instead of paying for a second image.
async function createScene() {
  stylePill()
  fitSignature()
  await flush()
  const signature = JSON.stringify([creation.value!.id, saver!.revision, direction.value, look.value, headline.value.accent_colour, format.value])
  if (!plan.value || planSignature !== signature) { await prepareScene(); planSignature = signature }
  rememberStyle()
  await generateScene()
}
function acceptPlan(value: any) { plan.value = value; savedPlanSnapshot = JSON.stringify(value.plan) }
async function savePlan() {
  await flush()
  if (plan.value.origin_revision === saver!.revision && JSON.stringify(plan.value.plan) === savedPlanSnapshot) return
  const { scene, product_region, overlay_regions, palette } = plan.value.plan
  acceptPlan(await mutation(`/api/plans/${plan.value.id}/revisions`, { scene, product_region, overlay_regions, palette }, saver!.revision))
}
async function generateScene() {
  await savePlan()
  // The explicit low-resolution checkbox below is required even after reopening a draft.
  const result = await mutation<any>(`/api/creations/${creation.value!.id}/scenes`, { plan_id: plan.value.id, format: format.value, ...(styleReference.value ? { style_reference_asset: styleReference.value } : {}), ...headlineBody(), acknowledged_warnings: lowResAccepted.value ? ['low_resolution'] : [] }, saver!.revision)
  follow({ id: result.job_id, kind: 'scene', status: 'queued', result_ref: null, error_code: null })
}
const lowResAccepted = ref(false)
async function refineScene() {
  await flush()
  const result = await mutation<any>(`/api/creations/${creation.value!.id}/refinements`, { base_visual_id: currentVisual.value!.id, instruction_fr: refinement.value, format: format.value, ...(styleReference.value ? { style_reference_asset: styleReference.value } : {}) }, saver!.revision)
  follow({ id: result.job_id, kind: 'refine', status: 'queued', result_ref: null, error_code: null })
}
function follow(value: Job) { clearTimeout(pollTimer); job.value = value; pollTimer = setTimeout(poll, 250) }
async function poll() {
  if (!job.value || !creation.value) return
  if (document.hidden) { pollTimer = setTimeout(poll, 10000); return }
  const creationId = creation.value.id, jobId = job.value.id
  try {
    const response = await api<Job>(`/api/jobs/${jobId}`)
    if (creation.value?.id !== creationId || job.value?.id !== jobId) return
    job.value = response
    if (job.value.status === 'succeeded') {
      const completed = job.value
      if (completed.kind === 'render') {
        const result = await api(`/api/renders/${completed.result_ref}`)
        if (creation.value?.id !== creationId || job.value?.id !== jobId) return
        openFinalPreview(result)
      }
      else if (completed.kind === 'text_patch' || completed.kind === 'text_texture') {
        const result: any = await api(`/api/${completed.kind === 'text_patch' ? 'text-proposals' : 'text-effects'}/${completed.result_ref}`)
        if (creation.value?.id !== creationId || job.value?.id !== jobId) return
        if (completed.kind === 'text_patch') { proposal.value = result; effect.value = null; acknowledgeContent.value = false }
        else { effect.value = result; effectSources.value[`effect:${result.id}`] = result.image_url }
        previewPolish.value = true
        notice.value = 'Aperçu de l’ajustement : vérifiez-le avant de l’appliquer.'
      }
      else if (completed.kind === 'look') {
        const made = await api<SavedLook>(`/api/looks/${completed.result_ref}`)
        if (creation.value?.id !== creationId || job.value?.id !== jobId) return
        savedLooks.value = [made, ...savedLooks.value.filter(item => item.id !== made.id)]
        pickLook(made.id); lookName.value = ''; lookReference.value = null
        notice.value = `Style « ${made.name} » enregistré. Il est sélectionné et restera disponible pour vos prochaines affiches.`
      }
      else if (completed.kind === 'plan') {
        const result = await api(`/api/plans/${completed.result_ref}`)
        if (creation.value?.id !== creationId || job.value?.id !== jobId) return
        acceptPlan(result)
      }
      else {
        await refreshVisuals()
        if (creation.value?.id !== creationId || job.value?.id !== jobId) return
        if (!saver?.unsaved) {
          const saved = await api<Creation>(`/api/creations/${creation.value.id}`)
          if (creation.value?.id !== creationId || job.value?.id !== jobId) return
          if (saved.revision !== saver?.revision && !saver?.unsaved) await adopt(saved)
        }
        notice.value = 'Votre nouvelle scène est prête à comparer.'
        review.value = visuals.value.find(item => item.id === completed.result_ref) ?? null; resetChecks()
      }
      if (job.value?.id === jobId) job.value = null
      return
    }
    if (['failed', 'interrupted', 'cancelled'].includes(job.value.status)) {
      error.value = job.value.status === 'interrupted' ? 'La génération a été interrompue. Aucun nouvel appel automatique n’a été lancé.' : job.value.kind === 'look' ? 'Le style n’a pas pu être décrit à partir de cette affiche. Essayez une autre image ; rien n’est perdu.' : 'La tâche n’a pas abouti. Vos images et votre brouillon sont conservés. Vous pouvez réessayer.'
      job.value = null; return
    }
    pollTimer = setTimeout(poll, 2000)
  } catch (reason) {
    if (creation.value?.id === creationId && job.value?.id === jobId) { error.value = (reason as Error).message; pollTimer = setTimeout(poll, 10000) }
  }
}
async function cancelJob() { await mutation(`/api/jobs/${job.value!.id}/cancel`, {}); job.value = null; clearTimeout(pollTimer) }
async function refreshEffects() {
  const ids = [...new Set(Object.values(doc.value?.formats ?? {}).flatMap(layout => layout.layers.flatMap(layer => layer.kind === 'text' && layer.texture_effect_id ? [layer.texture_effect_id] : [])))]
  const entries = await Promise.all(ids.map(async id => { const value: any = await api(`/api/text-effects/${id}`); return [`effect:${id}`, value.image_url] as const }))
  effectSources.value = Object.fromEntries(entries)
}
async function proposeText() {
  await flush()
  const result: any = await mutation(`/api/creations/${creation.value!.id}/text-proposals`, { format: format.value, layer_id: selected.value, instruction_fr: polish.value }, saver!.revision)
  follow({ id: result.job_id, kind: 'text_patch', status: 'queued', result_ref: null, error_code: null })
}
async function applyProposal() {
  await flush()
  const id = proposal.value.id, before = copy(doc.value!), previousHistory = history
  const result = await mutation<Creation>(`/api/text-proposals/${id}/apply`, { acknowledged_content_change: acknowledgeContent.value }, saver!.revision)
  await adopt(result); previousHistory.record(before); history = previousHistory; proposal.value = await api(`/api/text-proposals/${id}`)
}
async function rejectProposal() {
  await mutation(`/api/text-proposals/${proposal.value.id}/reject`, {})
  proposal.value = null; previewPolish.value = false
}
async function generateEffect() {
  await flush()
  const result: any = await mutation(`/api/creations/${creation.value!.id}/text-effects`, { format: format.value, layer_id: proposal.value.layer_id, proposal_id: proposal.value.id }, saver!.revision)
  follow({ id: result.job_id, kind: 'text_texture', status: 'queued', result_ref: null, error_code: null })
}
async function decideEffect(action: 'apply' | 'reject') {
  await flush()
  const before = copy(doc.value!), previousHistory = history
  const result = await mutation<Creation>(`/api/text-effects/${effect.value.id}/${action}`, {}, action === 'apply' ? saver!.revision : undefined)
  if (action === 'apply') { await adopt(result); previousHistory.record(before); history = previousHistory }
  effect.value = null; previewPolish.value = false
}
function openFinalPreview(value: any) {
  finalPreview.value = value; previewLoaded.value = false; confirmedDownload.value = value.download_url ?? ''; warningsAccepted.value = false
  for (const key of Object.keys(finalChecks) as (keyof typeof finalChecks)[]) finalChecks[key] = false
}
async function renderFinal() {
  await flush()
  const result: any = await mutation(`/api/creations/${creation.value!.id}/renders`, { format: format.value }, saver!.revision)
  follow({ id: result.job_id, kind: 'render', status: 'queued', result_ref: null, error_code: null })
}
async function confirmFinal() {
  await flush()
  const result: any = await mutation(`/api/creations/${creation.value!.id}/confirmations`, {
    render_id: finalPreview.value.id, png_sha256: finalPreview.value.png_sha256, checks: finalChecks,
    acknowledged_warning_ids: warningsAccepted.value ? finalPreview.value.warnings.map((issue: LayoutIssue) => issue.id) : [],
  }, saver!.revision)
  confirmedDownload.value = result.download_url
}
function chooseVisual(visual: Visual) {
  const [width, height] = visual.size.split('x').map(Number)
  edit(document => {
    document.formats[format.value]!.scene = { visual_id: visual.id, crop: fitCrop(width, height, format.value) }
    // A scene with an integrated headline replaces the title layer; any other scene needs the layer back.
    const title = document.formats[format.value]!.layers.find(layer => layer.role === 'title')
    if (title) title.visible = !visual.headline
    const price = document.formats[format.value]!.layers.find(layer => layer.role === 'price')
    if (price) price.visible = visual.headline?.price_ar === undefined
    for (const role of ['shop_name', 'contact'] as const) {
      const layer = document.formats[format.value]!.layers.find(item => item.role === role)
      if (layer) layer.visible = document.include[role] && visual.headline?.[role] === undefined
    }
  })
  selected.value = null
}
function resetChecks() { for (const check of Object.keys(checkNames)) checks[check] = false; rejection.value = '' }
async function decide(action: 'approve' | 'reject') {
  await mutation(`/api/visuals/${review.value!.id}/decision`, action === 'approve' ? { action, checks } : { action, note: rejection.value })
  await refreshVisuals(); review.value = null
}
function zoomScene(event: Event) {
  if (!currentVisual.value) return
  const zoom = Number((event.target as HTMLInputElement).value), [w, h] = currentVisual.value.size.split('x').map(Number)
  const base = fitCrop(w, h, format.value)
  edit(document => { const crop = document.formats[format.value]!.scene.crop!; const cx = crop.x + crop.w/2, cy = crop.y + crop.h/2; crop.w = base.w/zoom; crop.h = base.h/zoom; crop.x = Math.max(0, Math.min(w-crop.w, cx-crop.w/2)); crop.y = Math.max(0, Math.min(h-crop.h, cy-crop.h/2)) }, 'zoom')
}
const sceneZoom = computed(() => {
  if (!currentVisual.value || !layout.value?.scene.crop) return 1
  const [w, h] = currentVisual.value.size.split('x').map(Number)
  return fitCrop(w, h, format.value).w / layout.value.scene.crop.w
})
const scenePan = computed(() => {
  if (!currentVisual.value || !layout.value?.scene.crop) return { x: .5, y: .5 }
  const [w, h] = currentVisual.value.size.split('x').map(Number), crop = layout.value.scene.crop
  return { x: w === crop.w ? .5 : crop.x / (w - crop.w), y: h === crop.h ? .5 : crop.y / (h - crop.h) }
})
function panScene(axis: 'x' | 'y', event: Event) {
  if (!currentVisual.value) return
  const [w, h] = currentVisual.value.size.split('x').map(Number), fraction = Number((event.target as HTMLInputElement).value)
  edit(document => { const crop = document.formats[format.value]!.scene.crop!; crop[axis] = fraction * (axis === 'x' ? w - crop.w : h - crop.h) }, 'pan')
}
function resized() { viewportHeight.value = window.innerHeight }
const theme = ref(document.documentElement.dataset.theme === 'clair' ? 'clair' : 'sombre')
function toggleTheme() {
  theme.value = theme.value === 'clair' ? 'sombre' : 'clair'
  if (theme.value === 'clair') document.documentElement.dataset.theme = 'clair'; else delete document.documentElement.dataset.theme
  try { localStorage.setItem('affiche.theme', theme.value) } catch { /* convenience only */ }
}
function warnUnload(event: BeforeUnloadEvent) { if (saver?.unsaved) { event.preventDefault(); event.returnValue = '' } }
onMounted(async () => {
  window.addEventListener('beforeunload', warnUnload); window.addEventListener('resize', resized)
  try { authenticated.value = (await api<{ authenticated: boolean }>('/api/session')).authenticated; if (authenticated.value) { await loadShop(); const id = window.location.hash.slice(1); if (/^[a-f0-9-]{36}$/.test(id)) await openCreation(id) } }
  catch (reason) { error.value = (reason as Error).message }
  finally { checking.value = false }
})
onBeforeUnmount(() => { saver?.dispose(); clearTimeout(pollTimer); observer?.disconnect(); window.removeEventListener('beforeunload', warnUnload); window.removeEventListener('resize', resized) })
</script>

<template>
  <header class="app-header"><a href="#" @click.prevent="perform(fresh)" class="wordmark">Affiche<span>Atelier</span></a><span v-if="authenticated" class="shop-label">{{ profile.name || 'Votre boutique' }}</span><button class="quiet theme-toggle" type="button" :aria-pressed="theme === 'clair'" @click="toggleTheme">{{ theme === 'clair' ? 'Thème sombre' : 'Thème clair' }}</button><button v-if="doc" class="quiet" @click="perform(fresh)" :disabled="busy">Nouvelle affiche</button></header>
  <main>
    <p v-if="checking" role="status">Ouverture de l’atelier…</p>
    <div v-if="error" class="message error" role="alert">{{ error }}<button class="text-button" type="button" @click="error = ''">Fermer</button></div>
    <div v-if="notice" class="message notice" role="status">{{ notice }}<button class="text-button" type="button" @click="notice = ''">Fermer</button></div>
    <div v-if="caps?.image_mode === 'stub'" class="demo-notice">Mode de démonstration : les images sont simulées, sans dépense.</div>
    <form v-if="!checking && !authenticated" class="sign-in" @submit.prevent="perform(signIn)"><h1>Votre atelier d’affiches</h1><p>Connectez-vous pour retrouver les visuels de la boutique.</p><label>Mot de passe<input v-model="password" type="password" autocomplete="current-password" required /></label><button :disabled="busy">Ouvrir l’atelier</button></form>
    <div v-if="authenticated && !doc" class="intake-layout">
      <form class="intake" @submit.prevent="perform(createPoster)">
        <h1>Votre produit.<br />Une affiche à votre image.</h1><p class="intro">Ajoutez vos photos, votre titre et le prix. Vous pourrez ensuite ajuster chaque élément.</p>
        <label class="upload-zone">Photos du produit<input :disabled="busy" type="file" accept="image/jpeg,image/png,image/webp" multiple @change="event => perform(() => choosePhotos(event))" /><span>1 à 3 photos · JPEG, PNG ou WebP · 10 Mo maximum</span></label>
        <div class="photo-strip"><img v-for="photo in photos" :key="photo.asset" :src="`/api/assets/${photo.asset}`" alt="Photo originale du produit" /></div>
        <label>Nom du produit<input v-model="intake.name" maxlength="160" required placeholder="Ex. Soundcore R50i" /></label>
        <div class="form-row"><label>Variante confirmée<input v-model="intake.variant" maxlength="160" required /></label><label>Prix en ariary<input v-model="intake.price" inputmode="numeric" required placeholder="90 000" /></label></div>
        <label class="check"><input v-model="intake.confirmed" type="checkbox" />Les photos correspondent au produit et à la variante indiqués.</label>
        <details open><summary>Identité de la boutique</summary><label>Nom de la boutique<input v-model="profile.name" maxlength="160" /></label><label>Contact<textarea v-model="profile.contact" rows="2" maxlength="500" placeholder="Téléphone, adresse ou WhatsApp" /></label><label>Logo<input :disabled="busy" type="file" accept="image/jpeg,image/png,image/webp" @change="event => perform(() => chooseLogo(event))" /></label><img v-if="profile.logo_asset" class="logo-preview" :src="`/api/assets/${profile.logo_asset}`" alt="Logo de la boutique" /><div class="checks-row"><label v-for="role in (['logo','shop_name','contact'] as const)" :key="role" class="check"><input v-model="include[role]" type="checkbox" />{{ roleNames[role] }}</label></div></details>
        <button class="primary wide" :disabled="busy || !photos.length || !intake.confirmed">{{ busy ? 'Préparation…' : 'Créer mon brouillon' }}</button><p v-if="whyNoDraft" class="why" role="status">{{ whyNoDraft }}</p>
      </form>
      <aside class="library"><h2>Vos affiches</h2><p v-if="!library.length">Vos brouillons et vos scènes apparaîtront ici.</p><button v-for="item in library" :key="item.id" class="library-item" @click="perform(() => openCreation(item.id))"><strong>{{ item.title }}</strong><span>{{ item.variant }}</span></button></aside>
    </div>
    <div v-if="doc" class="studio">
      <section class="workspace">
        <div class="canvas-toolbar"><h2>Votre affiche</h2><span>Publication · 1080 × 1350</span><div><button class="quiet" :disabled="!history.past.length" @click="undo">Annuler</button><button class="quiet" :disabled="!history.future.length" @click="redo">Rétablir</button></div></div>
        <p class="coach" role="status"><b>À faire</b>{{ nextStep }}</p>
        <div ref="canvasHost" class="canvas-host" :class="{ generating: !!job && ['scene', 'refine'].includes(job.kind) }"><PosterCanvas :document="previewDoc!" :readonly="previewPolish" :format="format" :sources="sources" :selected="selected" :scale="scale" :drag-enabled="dragEnabled" @select="selected = $event" @change="patchLayer" @issues="issues = $event" @ready="canvasReady = $event" @error="error = $event" /></div>
        <div v-if="proposal?.status === 'pending' || effect?.status === 'proposed'" class="polish-preview"><strong>Ajustement à vérifier</strong><label class="check"><input v-model="previewPolish" type="checkbox" />Voir la proposition sur l’affiche</label></div>
        <div class="canvas-footer"><span role="status" aria-live="polite">{{ saveLabel }}</span><label class="check"><input v-model="dragEnabled" type="checkbox" />Déplacer les éléments</label></div>
        <details v-if="visuals.length" open class="filmstrip"><summary>Versions de la scène ({{ visuals.length }})</summary><div class="visual-list"><article v-for="visual in visuals" :key="visual.id"><img :src="visual.image_url" alt="Version générée de la scène" /><span>{{ { approved:'Approuvée', pending_review:'À vérifier', rejected:'Refusée' }[visual.status] }}</span><div><button class="quiet" @click="chooseVisual(visual)">Choisir</button><button class="quiet" @click="review = visual; resetChecks()">Comparer</button></div></article></div></details>
        <div v-if="saveState === 'failed' || saveState === 'conflict'" class="save-recovery"><button v-if="saveState === 'failed'" @click="perform(flush)">Réessayer l’enregistrement</button><template v-else><button @click="perform(conflictCopy)">Conserver mes modifications dans une copie</button><button class="quiet" @click="perform(discardAndReload)">Abandonner mes modifications et recharger</button></template></div>
        <ul v-if="issues.length" class="issues"><li v-for="issue in issues" :key="issue.id" :class="{ blocking: issue.blocking }"><button class="text-button" @click="selected = issue.layer_id">{{ issue.message }}</button></li></ul>
        <p v-if="!currentVisual" class="help">Préparez une scène à partir de vos photos pour compléter le brouillon.</p>
        <p v-else class="help">{{ currentVisual.status === 'approved' ? 'Fidélité du produit approuvée.' : currentVisual.status === 'rejected' ? 'Cette scène a été refusée. Choisissez une autre version ou ajustez la scène.' : 'Comparez le produit avec la photo originale avant de valider sa fidélité.' }} <button class="text-button" @click="review = currentVisual!; resetChecks()">Comparer</button></p>
      </section>
      <aside class="properties">
        <nav class="steps" aria-label="Étapes de création"><a href="#etape-textes"><b>01</b>Textes</a><a href="#etape-style"><b>02</b>Style</a><a href="#etape-final"><b>03</b>Finaliser</a></nav>
        <section id="etape-textes" class="step-card" aria-labelledby="titre-textes"><header><b aria-hidden="true">01</b><h2 id="titre-textes">Textes de l’affiche</h2></header>
          <label>Titre<textarea :value="doc.offer.title" maxlength="240" rows="2" @input="event => edit(d => { d.offer.title = (event.target as HTMLTextAreaElement).value }, 'title')" /></label><label>Prix en ariary<input v-model="priceText" inputmode="numeric" @input="changePrice" /></label>
          <template v-if="headline.on"><label>Marque (facultative)<input v-model="headline.brand" maxlength="60" placeholder="JBL" :disabled="busy || !!job" /></label><label>Sous-titre (facultatif)<input v-model="headline.subtitle" maxlength="60" placeholder="CASQUE SANS FIL" :disabled="busy || !!job" /></label><label>Mot du titre à mettre en couleur (facultatif)<input v-model="headline.accent_word" maxlength="60" placeholder="770NC" :disabled="busy || !!job" /></label></template>
          <h3>Boutique sur l’affiche</h3>
        <div class="checks-row"><label v-for="role in (['logo','shop_name','contact'] as const)" :key="role" class="check"><input :checked="doc.include[role]" type="checkbox" @change="event => edit(d => toggleIdentity(d, role, (event.target as HTMLInputElement).checked))" />{{ roleNames[role] }}</label></div>
          <details class="ai-draws"><summary>Ce que l’IA dessine dans l’image</summary><p class="help">Par défaut, l’IA compose le titre, le prix et la signature de la boutique avec la scène, comme sur une affiche de marque. Vérifiez chaque mot et chaque chiffre avant de valider la scène ; pour corriger, générez une nouvelle scène.</p><label class="check"><input v-model="headline.on" type="checkbox" :disabled="busy || !!job" /> Laisser l’IA composer le titre dans l’image</label><template v-if="headline.on"><label class="check"><input v-model="headline.price" type="checkbox" :disabled="busy || !!job" /> Dessiner aussi le prix dans l’image</label><label v-if="signable" class="check"><input v-model="headline.signature" type="checkbox" :disabled="busy || !!job" /> Dessiner aussi le nom de la boutique et le contact dans l’image</label></template></details>
        </section>
        <section id="etape-style" class="step-card" aria-labelledby="titre-style"><header><b aria-hidden="true">02</b><h2 id="titre-style">Style et génération</h2></header>
        <details :open="!currentVisual"><summary>Composer une scène</summary><h3>Choisir un style</h3><div class="look-grid"><button v-for="item in LOOKS" :key="item.id" type="button" class="look" :class="{ selected: look === item.id }" :aria-pressed="look === item.id" :disabled="busy || !!job" @click="pickLook(item.id)"><img v-if="item.image" :src="item.image" alt="" /><span>{{ item.label }}</span></button><button v-for="item in savedLooks" :key="item.id" type="button" class="look" :class="{ selected: look === item.id }" :aria-pressed="look === item.id" :disabled="busy || !!job" @click="pickLook(item.id)"><img :src="`/api/assets/${item.reference_asset}?prepared=true`" alt="" /><span>{{ item.name }}</span></button></div><details v-if="caps?.planner_available" class="new-look"><summary>Créer un style depuis une affiche</summary><p class="help">Choisissez une affiche que vous aimez. Claude décrit son style (fond, lumière, couleurs, typographie), jamais son produit ni ses textes. Le style est enregistré à côté des autres et réutilisable.</p><label>Affiche modèle<input :disabled="busy || !!job" type="file" accept="image/jpeg,image/png,image/webp" @change="event => perform(() => chooseLookReference(event))" /></label><div v-if="lookReference" class="photo-strip"><img :src="`/api/assets/${lookReference}?prepared=true`" alt="Affiche modèle pour le nouveau style" /></div><label>Nom du style (facultatif)<input v-model="lookName" maxlength="40" placeholder="Vagues bleues" :disabled="busy || !!job" /></label><button :disabled="busy || !!job || !lookReference" @click="perform(createLook)">Enregistrer ce style</button><p v-if="whyNoLook" class="why" role="status">{{ whyNoLook }}</p><small>Estimation : {{ dollars(caps?.plan_estimate_micros) }}</small></details><label>Couleur d’accent<input v-model="headline.accent_colour" type="color" :disabled="busy || !!job" /></label><label>{{ look === 'libre' ? 'Ambiance souhaitée' : 'Ambiance (modifiable)' }}<textarea v-model="direction" rows="3" maxlength="400" @input="look = 'libre'" /></label><template v-if="plannerMode === 'fixed'"><label class="check"><input v-model="lowResAccepted" type="checkbox" />J’accepte une qualité réduite si la photo source est petite.</label><button class="wide" :disabled="busy || !!job" @click="perform(createScene)">Générer la scène</button><p v-if="whyBusy" class="why" role="status">{{ whyBusy }}</p><small>Estimation : {{ dollars(caps?.scene_estimate_micros) }}</small></template><template v-else><button :disabled="busy || !!job" @click="perform(prepareScene)">Préparer la composition</button><small>Estimation : {{ dollars(caps?.plan_estimate_micros) }}</small></template><div v-if="plan && plannerMode === 'claude'" class="plan"><label>Description de la scène<textarea v-model="plan.plan.scene.setting" rows="3" maxlength="400" /></label><p>{{ plan.plan.summary_fr }}</p><label class="check"><input v-model="lowResAccepted" type="checkbox" />J’accepte une qualité réduite si la photo source est petite.</label><button :disabled="busy || !!job" @click="perform(generateScene)">Générer la scène</button><small>Estimation : {{ dollars(caps?.scene_estimate_micros) }}</small></div></details>
        <div v-if="job" class="job-state" role="status"><strong>{{ { plan:'Préparation de la composition…', scene:'Création de votre scène…', refine:'Ajustement de la scène…', text_patch:'Préparation de l’ajustement du texte…', text_texture:'Création de la matière du texte…', render:'Préparation de l’aperçu final…' }[job.kind] }}</strong><p>Vous pouvez continuer à ajuster le texte.</p><button v-if="job.status === 'queued'" class="quiet" @click="perform(cancelJob)">Annuler la demande</button></div>
        </section>
        <section id="etape-final" class="step-card" aria-labelledby="titre-final"><header><b aria-hidden="true">03</b><h2 id="titre-final">Vérifier et télécharger</h2></header>
          <button class="wide export-button" :disabled="busy || !!job || !canvasReady || previewPolish || currentVisual?.status !== 'approved' || staleHeadline || issues.some(issue => issue.blocking)" @click="perform(renderFinal)">Vérifier l’aperçu final</button><p v-if="whyNoExport" class="why" role="status">{{ whyNoExport }}</p><p class="help">PNG 1080 × 1350 · sans nouvelle génération</p><p v-if="stalePrice" class="help" role="status">Le prix est dessiné dans l’image<template v-if="currentVisual?.headline?.price_ar !== undefined"> ({{ currentVisual.headline.price_ar.toLocaleString('fr-FR') }} Ar)</template>. Pour le changer, générez une nouvelle scène dans « Composer une scène ».</p><p v-if="staleSignature" class="help" role="status">Le nom de la boutique ou le contact est dessiné dans l’image. Pour le changer ou le retirer, générez une nouvelle scène dans « Composer une scène ».</p><p v-if="staleTitle" class="help" role="status">Le titre est dessiné dans l’image<template v-if="currentVisual?.headline"> (« {{ currentVisual.headline.title }} »)</template>. Pour le changer, générez une nouvelle scène dans « Composer une scène », ou remettez l’ancien titre.</p>
          <details class="advanced"><summary>Réglages avancés</summary><p class="help">Retoucher un texte resté en calque, recadrer la scène ou déplacer un élément.</p>
        <h3>Éléments</h3><div class="layer-list"><button :class="{ selected: selected === null }" @click="selected = null">Scène</button><button v-for="layer in layout?.layers.filter(layer => layer.visible)" :key="layer.id" :class="{ selected: selected === layer.id }" @click="selected = layer.id">{{ roleNames[layer.role] }}</button></div>
        <div v-if="chosen" class="layer-properties">
          <h3>{{ roleNames[chosen.role] }}</h3>
          <template v-if="chosen.kind === 'text'"><label>Police<select aria-label="Police" :value="chosen.font_id" @change="changeFont"><option value="noto-sans">Noto Sans</option><option value="noto-serif">Noto Serif</option><option value="montserrat-black-italic">Montserrat Black Italic</option></select></label><div class="form-row"><label>Taille<input type="number" min="24" max="240" :value="chosen.font_size" @change="numeric('font_size', $event)" /></label><label>Couleur<input type="color" :value="chosen.fill" @input="event => patchLayer(selected!, { fill: (event.target as HTMLInputElement).value }, 'colour')" /></label></div><div class="form-row"><label>Graisse<select :value="chosen.weight" @change="event => patchLayer(selected!, { weight: Number((event.target as HTMLSelectElement).value) as 400 | 700 | 900 })"><template v-if="chosen.font_id !== 'montserrat-black-italic'"><option :value="400">Normal</option><option :value="700">Gras</option></template><option v-else :value="900">Très gras italique</option></select></label><label>Alignement<select :value="chosen.align" @change="event => patchLayer(selected!, { align: (event.target as HTMLSelectElement).value as any })"><option value="left">Gauche</option><option value="center">Centré</option><option value="right">Droite</option></select></label></div><template v-if="chosen.role === 'price'"><label>Présentation du prix<select aria-label="Présentation du prix" :value="chosen.price_badge ? 'capsule' : 'simple'" @change="event => patchLayer(selected!, { price_badge: (event.target as HTMLSelectElement).value === 'capsule' ? { fill: '#FFFFFF', border_start: '#009FE3', border_end: '#1853BD' } : null })"><option value="simple">Texte simple — Ar</option><option value="capsule">Capsule — AR plus petit</option></select></label><div v-if="chosen.price_badge" class="form-row"><label v-for="field in (['fill', 'border_start', 'border_end'] as const)" :key="field">{{ { fill: 'Fond du prix', border_start: 'Contour début', border_end: 'Contour fin' }[field] }}<input type="color" :value="chosen.price_badge[field]" @input="event => badgeColour(field, event)" /></label></div></template><div class="checks-row"><label class="check"><input type="checkbox" :checked="!!chosen.outline" @change="event => patchLayer(selected!, { outline: (event.target as HTMLInputElement).checked ? { colour: '#17324D', width: 2 } : null })" />Contour</label><label class="check"><input type="checkbox" :checked="!!chosen.shadow" @change="event => patchLayer(selected!, { shadow: (event.target as HTMLInputElement).checked ? { colour: '#000000', blur: 6, offset_x: 0, offset_y: 4, opacity: .5 } : null })" />Ombre</label></div></template>
          <details v-if="chosen.kind === 'text' && ['title','price'].includes(chosen.role)"><summary>Ajuster ce texte avec une consigne</summary><p class="help">Seul le {{ chosen.role === 'price' ? 'prix' : 'titre' }} sélectionné sera ajusté. La scène reste intacte.</p><label>Votre consigne<textarea v-model="polish" maxlength="500" rows="3" placeholder="Ex. Un titre doré avec une ombre légère" /></label><button :disabled="busy || !!job || !polish.trim() || !caps?.planner_available" @click="perform(proposeText)">Proposer un ajustement</button><small v-if="caps?.planner_available">Estimation Claude : {{ dollars(caps?.plan_estimate_micros) }}</small><p v-else class="help">Les consignes seront disponibles une fois Claude configuré. Les réglages manuels restent disponibles.</p>
            <div v-if="proposal && proposal.layer_id === selected" class="plan"><p>{{ proposal.patch.summary_fr }}</p><template v-if="proposal.status === 'pending'"><div v-if="proposal.patch.content_change"><p><strong>Contenu partagé modifié</strong> · Toutes les tailles de cette affiche sont concernées.</p><p>Avant : {{ proposal.before.offer[proposal.patch.content_change.field] }}<br />Après : {{ proposal.patch.content_change.value }}</p><label class="check"><input v-model="acknowledgeContent" type="checkbox" />Je confirme ce nouveau contenu.</label></div><button :disabled="busy || (!!proposal.patch.content_change && !acknowledgeContent)" @click="perform(applyProposal)">Appliquer au texte</button><button class="quiet" :disabled="busy" @click="perform(rejectProposal)">Refuser l’ajustement</button></template><template v-else-if="proposal.status === 'applied' && proposal.patch.texture_request"><p>Matière proposée : {{ proposal.patch.texture_request.description }}</p><button :disabled="busy || !!job" @click="perform(generateEffect)">Générer la matière du texte</button><small>Appel image distinct : {{ dollars(caps?.texture_estimate_micros) }}</small></template></div>
            <div v-if="effect?.status === 'proposed' && effect.layer_id === selected" class="plan"><p>Vérifiez la matière dans l’aperçu. Les lettres et le montant restent exacts.</p><button :disabled="busy" @click="perform(() => decideEffect('apply'))">Appliquer la matière</button><button class="quiet" :disabled="busy" @click="perform(() => decideEffect('reject'))">Refuser la matière</button></div>
          </details>
          <button v-if="chosen.kind === 'text' && chosen.texture_effect_id" class="quiet" @click="patchLayer(chosen.id, { texture_effect_id: null })">Retirer la matière du texte</button>
          <details><summary>Position et dimensions</summary><div class="form-row" v-for="pair in ([['x','y'],['width','height']] as const)" :key="pair[0]"><label v-for="field in pair" :key="field">{{ { x:'Position X', y:'Position Y', width:'Largeur', height:'Hauteur' }[field] }}<input type="number" :value="Math.round(chosen[field])" @change="numeric(field, $event)" /></label></div></details>
        </div>
        <div v-else-if="currentVisual"><h3>Cadrage de la scène</h3><p class="help">Le produit fait partie de la scène. Ajustez son cadrage ou demandez une nouvelle version.</p><label>Zoom<input type="range" min="1" max="2" step="0.01" :value="sceneZoom" @input="zoomScene" /></label><label>Position horizontale<input type="range" min="0" max="1" step="0.01" :value="scenePan.x" @input="panScene('x', $event)" /></label><label>Position verticale<input type="range" min="0" max="1" step="0.01" :value="scenePan.y" @input="panScene('y', $event)" /></label><label>Ajustement de la scène<textarea v-model="refinement" rows="3" maxlength="500" placeholder="Ex. Une lumière plus chaude, en conservant la composition" /></label><button :disabled="busy || !!job || !refinement.trim()" @click="perform(refineScene)">Ajuster la scène</button><small>Appel image estimé : {{ dollars(caps?.scene_estimate_micros) }}</small></div>
          </details>
        </section>
      </aside>
    </div>
    <section v-if="finalPreview" class="review-panel final-preview" aria-labelledby="final-title"><div class="section-heading"><h2 id="final-title">Votre affiche, prête à vérifier</h2><button class="quiet" @click="finalPreview = null">Fermer</button></div><p>Ce fichier est celui qui sera téléchargé après votre confirmation.</p><a :href="finalPreview.preview_url" target="_blank" rel="noopener"><img :src="finalPreview.preview_url" alt="Aperçu final du fichier à télécharger" @load="previewLoaded = true" @error="error = 'Le fichier d’aperçu ne peut pas être chargé.'; previewLoaded = false" /></a><p class="help">Ouvrir l’image pour vérifier les détails à pleine taille.</p><div class="review-checks"><label v-for="(label, check) in ({ framing:'Le produit est entier, bien cadré et dégagé du texte', content:'Le titre et le prix sont exacts', identity:'Les détails de la boutique sont corrects', readability:'Tous les éléments sont lisibles' } as const)" :key="check" class="check"><input v-model="finalChecks[check]" type="checkbox" />{{ label }}</label></div><div v-if="finalPreview.warnings.length"><ul><li v-for="warning in finalPreview.warnings" :key="warning.id">{{ warning.message }}</li></ul><label class="check"><input v-model="warningsAccepted" type="checkbox" />J’ai vérifié ces superpositions et la lisibilité.</label></div><button :disabled="busy || !previewLoaded || !Object.values(finalChecks).every(Boolean) || (!!finalPreview.warnings.length && !warningsAccepted)" @click="perform(confirmFinal)">Confirmer cette version</button><a v-if="confirmedDownload" :href="confirmedDownload" class="download-button" download>Télécharger le PNG confirmé</a></section>
    <section v-if="review" class="review-panel" aria-labelledby="review-title"><div class="section-heading"><h2 id="review-title">Vérifier la fidélité du produit</h2><button class="quiet" @click="review = null">Fermer</button></div><div class="comparison"><figure><a v-for="(url, index) in review.original_urls" :key="url" :href="url" target="_blank" rel="noopener"><img :src="url" :alt="`Photo originale ${index + 1} à comparer`" /></a><figcaption>Photos originales · ouvrir pour agrandir</figcaption></figure><figure><a :href="review.image_url" target="_blank" rel="noopener"><img :src="review.image_url" alt="Scène générée à vérifier" /></a><figcaption>Scène générée · ouvrir pour agrandir</figcaption></figure></div><template v-if="review.status === 'pending_review'"><div class="review-checks"><label v-for="(label, check) in checkNames" :key="check" class="check"><input v-model="checks[check]" type="checkbox" />{{ label }}</label></div><button :disabled="busy || !Object.keys(checkNames).every(key => checks[key])" @click="perform(() => decide('approve'))">Approuver la fidélité</button><details><summary>Signaler un problème</summary><label>Ce qui doit être corrigé<textarea v-model="rejection" rows="2" maxlength="500" /></label><button class="secondary" :disabled="busy || !rejection.trim()" @click="perform(() => decide('reject'))">Refuser cette version</button></details></template><p v-else>{{ review.status === 'approved' ? 'La fidélité de cette version a été approuvée.' : 'Cette version a été refusée.' }}</p></section>
  </main>
</template>
