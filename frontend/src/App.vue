<script setup lang="ts">
import { computed, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import PosterCanvas from './PosterCanvas.vue'
import { api, ApiError, mutation, upload } from './api'
import { DraftSaver } from './autosave'
import { copy, fitCrop, FORMATS, History, parsePrice, setIdentity, type Creation, type FontId, type Layer, type PosterDocument, type Visual } from './document'
import type { LayoutIssue } from './canvas'

interface Profile { revision: number; name: string | null; contact: string | null; logo_asset: string | null }
interface Capabilities { image_mode: string; planner_mode: string; planner_available: boolean; scene_estimate_micros: number; plan_estimate_micros: number; texture_estimate_micros: number }
interface LibraryItem { id: string; revision: number; state: 'draft' | 'to_review' | 'approved' | 'confirmed'; title: string; variant: string; price_ar: number; created_at: string; thumbnail_url: string | null }
interface Listing { items: LibraryItem[]; total: number; next_cursor: string | null }
const stateNames = { draft: 'Brouillon', to_review: 'À vérifier', approved: 'Approuvée', confirmed: 'Confirmée' }
interface Job { id: string; kind: string; status: string; result_ref: string | null; error_code: string | null }
const roleNames: Record<string, string> = { title: 'Titre', price: 'Prix', shop_name: 'Nom de la boutique', contact: 'Contact', logo: 'Logo', product: 'Produit' }
const checkNames: Record<string, string> = { colour: 'Couleurs fidèles', markings: 'Marque et inscriptions fidèles', hardware: 'Boutons et détails fidèles', shape: 'Forme et proportions fidèles', extras_text: 'Aucun objet ni texte ajouté par l’IA', integration: 'Intégration naturelle dans la scène' }
const authenticated = ref(false), checking = ref(true), down = ref(false), password = ref(''), error = ref(''), notice = ref(''), busy = ref(false), priceError = ref('')
const caps = ref<Capabilities>(), library = ref<LibraryItem[]>([])
const profile = reactive<Profile>({ revision: 1, name: null, contact: null, logo_asset: null })
let profileSaved = '', noticeTimer: ReturnType<typeof setTimeout> | undefined
// A notice leaves by itself; an error stays until it is closed or the next action starts.
watch(notice, value => { clearTimeout(noticeTimer); if (value) noticeTimer = setTimeout(() => { if (notice.value === value) notice.value = '' }, 8000) })
const intake = reactive({ name: '', variant: 'Conforme à la photo', price: '', confirmed: false })
// The logo identifies the shop, and without one the footer carries the contact only (ADR-053): the name starts unticked.
const include = reactive({ logo: false, shop_name: false, contact: true })
// A contact typed for the first time is put on the poster, as an uploaded logo is; its box can still be unticked.
watch(() => !!profile.contact?.trim(), filled => { include.contact = filled })
let pendingInput: { signature: string; id: string } | null = null
const photos = ref<{ asset: string; warnings: string[] }[]>([])
const creation = ref<Creation | null>(null), doc = shallowRef<PosterDocument | null>(null), selected = ref<string | null>(null)
const visuals = ref<Visual[]>([]), direction = ref('Studio clair et épuré, dégradé doux, grandes courbes discrètes derrière le produit.'), plannerMode = ref<'fixed' | 'claude'>('fixed')
const styleReference = ref<string | null>(null)
// The image model sets brand, product name and subtitle itself; the price stays an exact editable layer.
const headline = ref({ on: true, price: true, contact: true, brand_text: false, brand: '', subtitle: '', accent_word: '', accent_colour: '#1E6FE0' })
const profileValue = (role: 'shop_name' | 'contact') => doc.value?.include[role] ? (role === 'shop_name' ? doc.value.brand_snapshot.name : doc.value.brand_snapshot.contact) ?? undefined : undefined
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
// A poster made with a style that was removed since keeps it for its new versions (D-CREATION-LIBRARY-004). It is held
// apart, for the open poster only: never in the picker, never in the style remembered for the next poster.
const keptLook = ref<SavedLook | null>(null)
const savedLook = computed(() => savedLooks.value.find(item => item.id === look.value) ?? (look.value === 'libre' ? keptLook.value ?? undefined : undefined))
function pickLook(id: string) {
  look.value = id; keptLook.value = null
  const saved = savedLooks.value.find(item => item.id === id)
  if (saved) { direction.value = saved.brief.direction_fr; headline.value.accent_colour = saved.brief.accent_colour.toLowerCase(); return }
  const chosen = LOOKS.find(item => item.id === id)!
  if (chosen.direction) direction.value = chosen.direction
  if (id === 'sombre') headline.value.accent_colour = '#C8A45A'
}
// A style brings its own accent colour. It applies when the owner left the colour alone; once he has picked
// one himself, in « Textes », his stays and the style's is only proposed, one tap away (ADR-073).
const accentPicked = ref(false), styleAccent = ref('')
function pickAccent(value: string) { headline.value.accent_colour = value.toLowerCase(); accentPicked.value = true; styleAccent.value = '' }
function chooseLook(id: string) {
  const mine = headline.value.accent_colour
  pickLook(id)
  const proposed = headline.value.accent_colour.toLowerCase()
  styleAccent.value = ''
  if (accentPicked.value && proposed !== mine.toLowerCase()) { headline.value.accent_colour = mine; styleAccent.value = proposed }
}
function useStyleAccent() { headline.value.accent_colour = styleAccent.value; accentPicked.value = false; styleAccent.value = '' }
// A reopened poster brings back what its scene was made with (brand, subtitle, accent, look), so that a new
// scene after a price change is the same poster and not a different one.
async function restoreHeadline() {
  const drawn = currentVisual.value?.headline as Record<string, any> | null | undefined
  if (!drawn) return
  if (drawn.look_id && savedLooks.value.some(item => item.id === drawn.look_id)) pickLook(drawn.look_id)
  else if (drawn.look_id) {
    // Removed since: the server still has it. If it cannot be read, the poster opens without it and says nothing false.
    try {
      const kept = await api<SavedLook>(`/api/looks/${drawn.look_id}`)
      pickLook('libre'); direction.value = kept.brief.direction_fr; keptLook.value = kept
    } catch { keptLook.value = null }
  }
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
  try { localStorage.setItem(STYLE_KEY, JSON.stringify({ look: look.value, accent_colour: headline.value.accent_colour, brand: headline.value.brand, brand_text: headline.value.brand_text, contact_align: rememberedAlign.value })) } catch { /* convenience only */ }
}
// By default the image model draws the contact as one compact line, so it composes it with the price
// (ADR-055). Unticked, or when it cannot be drawn, it is the same line written by the renderer as a layer.
// The position is remembered on the device; for a layer it is the layer's own alignment.
type Align = 'left' | 'center' | 'right'
const rememberedAlign = ref<Align | null>(null)
try {
  const saved = JSON.parse(localStorage.getItem(STYLE_KEY) ?? 'null')
  if (['left', 'center', 'right'].includes(saved?.contact_align)) rememberedAlign.value = saved.contact_align
  headline.value.brand_text = saved?.brand_text === true
} catch { /* convenience only */ }
const defaultAlign = (document: PosterDocument): Align => rememberedAlign.value ?? (document.include.logo ? 'right' : 'center')
function compactContact(document: PosterDocument, align: Align) {
  const layer = document.formats[format.value]!.layers.find(item => item.role === 'contact')
  if (layer?.kind !== 'text') return
  layer.align = align
  // A contact typed on several lines keeps the plain layer: the icon line never wraps.
  if (/[\r\n]/.test(document.brand_snapshot.contact ?? '')) return
  // 32 px bold Noto Sans gives digits about 23 px high on the poster (22 px minimum, R-CATALOGUE-BRAND-003).
  Object.assign(layer, { font_id: 'noto-sans', weight: 700, font_size: 32, height: 48, icon: 'phone', outline: null, shadow: null })
}
// Same footer as the server's first plan: the logo at the left, the texts in the span to its right.
function placeFooter(document: PosterDocument) {
  const layers = document.formats[format.value]!.layers, [width] = FORMATS[format.value]
  const logo = layers.find(layer => layer.role === 'logo' && layer.visible)
  const contact = layers.find(layer => layer.role === 'contact')
  const left = width * .05, x = logo ? left + logo.width + width * .025 : left
  for (const layer of layers) if (layer.role === 'shop_name' || layer.role === 'contact') { layer.x = x; layer.width = width * .95 - x }
  if (logo) { logo.x = left; if (contact) logo.y = contact.y + contact.height - logo.height }
}
function moveContact(event: Event) {
  const align = rememberedAlign.value = (event.target as HTMLSelectElement).value as Align
  // A drawn contact moves with the next version; a rendered one moves now.
  if (contactLayer.value?.visible) edit(document => compactContact(document, align))
  rememberStyle()
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
        Object.assign(footer, { fill: look.value === 'sombre' ? '#FFFFFF' : '#22262E', outline: null, shadow: null })
  })
}
// The server refuses an accent that is not in the title, so the choice is made among the title's own words.
// A reopened poster may carry a longer accent ("Buds 2a"): it stays offered while the title still contains it.
const accentWord = computed(() => (doc.value?.offer.title ?? '').includes(headline.value.accent_word.trim()) ? headline.value.accent_word.trim() : '')
const accentWords = computed(() => [...new Set([...(doc.value?.offer.title ?? '').split(/\s+/).filter(Boolean), ...(accentWord.value ? [accentWord.value] : [])])])
const ACCENTS = [['#1e6fe0', 'Bleu'], ['#1f3250', 'Bleu nuit'], ['#d92b2b', 'Rouge'], ['#f08a1c', 'Orange'], ['#c8a45a', 'Or']] as const
const headlineBody = () => headline.value.on ? { headline: { brand: headline.value.brand.trim() || null, ...(headline.value.brand.trim() && headline.value.brand_text ? { brand_text: true } : {}), subtitle: headline.value.subtitle.trim() || null, accent_word: accentWord.value || null, accent_colour: accentWord.value ? headline.value.accent_colour.toUpperCase() : null, price: headline.value.price, ...(drawContact.value ? { signature: true, signature_align: sealOn.value ? 'right' : chosenAlign.value === 'center' ? 'centre' : chosenAlign.value, ...(sealOn.value ? { logo_seal: true } : {}) } : {}), ...(savedLook.value ? { look_id: savedLook.value.id } : {}) } } : {}
let savedPlanSnapshot = ''
const plan = ref<any>(null), job = ref<Job | null>(null), priceText = ref(''), refinement = ref('')
const finalPreview = ref<any>(null), confirmedDownload = ref(''), previewLoaded = ref(false)
const finalPoints = { framing: 'Le produit est entier, bien cadré et dégagé du texte', content: 'Le titre et le prix sont exacts', identity: 'Les détails de la boutique sont corrects', readability: 'Tous les éléments sont lisibles' }
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
const review = ref<Visual | null>(null), rejection = ref(''), rejecting = ref(false), zoomed = ref(false)
const issues = ref<LayoutIssue[]>([]), canvasReady = ref(false), dragEnabled = ref(false)
const canvasHost = ref<HTMLElement>(), canvasWidth = ref(540), viewportHeight = ref(window.innerHeight), viewportWidth = ref(window.innerWidth), savingTick = ref(0)
let saver: DraftSaver | null = null, history = new History(), pollTimer: ReturnType<typeof setTimeout> | undefined, observer: ResizeObserver | undefined
const format = computed(() => doc.value?.primary_format ?? 'feed')
const layout = computed(() => doc.value?.formats[format.value])
const currentVisual = computed(() => visuals.value.find(item => item.id === layout.value?.scene.visual_id))
const contactLayer = computed(() => layout.value?.layers.find(layer => layer.role === 'contact'))
const drawnContact = computed(() => currentVisual.value?.headline?.contact !== undefined)
const logoShown = computed(() => layout.value?.layers.find(layer => layer.role === 'logo' && layer.visible))
// One drawn line holds about 23 px per character plus the icon: the same estimate as the server's rule.
const whyNoDrawnContact = computed(() => {
  const value = doc.value?.include.contact ? doc.value.brand_snapshot.contact ?? '' : ''
  if (/["\r\n]/.test(value)) return 'Un contact sur plusieurs lignes ou avec des guillemets ne peut pas être dessiné : il reste un texte ajouté sur l’affiche.'
  const [width] = FORMATS[format.value], room = width * .9 - (logoShown.value ? logoShown.value.width + width * .025 : 0)
  return value.length > Math.floor((room - 50) / 23) ? 'Ce contact est trop long pour une seule ligne dessinée : il reste un texte ajouté sur l’affiche.' : ''
})
const drawContact = computed(() => headline.value.on && headline.value.contact && !!doc.value?.include.contact && !!doc.value.brand_snapshot.contact && !whyNoDrawnContact.value)
const sealLayer = computed(() => layout.value?.layers.find(layer => layer.kind === 'logo' && layer.shape === 'circle'))
const logoLayer = computed(() => layout.value?.layers.find(layer => layer.kind === 'logo'))
// The seal is offered only for the footer the design vouches for, and is chosen before the first version.
const SEAL_NEEDS_TEXTS = 'Le sceau a besoin du titre et du prix dessinés dans l’image.'
const whyNoSeal = computed(() => !doc.value?.include.logo ? ''
  : layout.value?.scene.visual_id ? 'Le sceau se choisit avant la première version : créez une copie de l’affiche pour le changer.'
  : doc.value.include.shop_name ? 'Le sceau remplace le nom de la boutique : décochez « Nom de la boutique ».'
  : !headline.value.on || !headline.value.price ? SEAL_NEEDS_TEXTS
  : !doc.value.include.contact ? 'Le sceau a besoin du contact : cochez « Contact » ci-dessus.'
  : !drawContact.value ? 'Le sceau a besoin du contact dessiné dans l’image.' : '')
const sealNeedsTexts = computed(() => whyNoSeal.value === SEAL_NEEDS_TEXTS)
const sealOn = computed(() => !!sealLayer.value && !!doc.value?.include.logo && !doc.value.include.shop_name && headline.value.on && headline.value.price && drawContact.value)
const discUncovered = computed(() => {
  const disc = currentVisual.value?.logo_disc, logo = logoLayer.value
  if (!disc) return false
  return !logo?.visible || Math.hypot(logo.x + logo.width / 2 - disc.x, logo.y + logo.height / 2 - disc.y) + disc.d / 2 > Math.min(logo.width, logo.height) / 2 + 2
})
function setSeal(event: Event) {
  const on = (event.target as HTMLInputElement).checked
  edit(document => { const logo = document.formats[format.value]!.layers.find(layer => layer.kind === 'logo'); if (logo?.kind === 'logo') { if (on) logo.shape = 'circle'; else delete logo.shape } })
}
const chosenAlign = computed<Align>(() => contactLayer.value?.kind === 'text' && contactLayer.value.visible ? contactLayer.value.align : doc.value ? defaultAlign(doc.value) : 'center')
// The server refuses to export a hidden title unless the selected scene carries exactly the current one.
// The logo as a round seal (ADR-057): the scene provides an empty white disc and the real file is printed on it.
function sealOnDisc(document: PosterDocument, disc: { x: number; y: number; d: number }) {
  const logo = document.formats[format.value]!.layers.find(layer => layer.role === 'logo')
  if (!logo) return
  // Printed at the size the owner chose (12 % of the width), centred on the disc; never smaller than the disc.
  const size = Math.max(disc.d + 4, FORMATS[format.value][0] * .12)
  Object.assign(logo, { x: disc.x - size / 2, y: disc.y - size / 2, width: size, height: size })
}
function toggleIdentity(document: PosterDocument, role: 'logo' | 'shop_name' | 'contact', enabled: boolean) {
  setIdentity(document, role, enabled)
  const seal = document.formats[format.value]!.layers.find(layer => layer.kind === 'logo' && layer.shape === 'circle')
  // A seal goes back on its disc; it has no place in the footer. A plain logo takes the footer's left.
  if (role === 'logo' && seal) { if (enabled && currentVisual.value?.logo_disc) sealOnDisc(document, currentVisual.value.logo_disc) }
  else if (role === 'logo') placeFooter(document)
  // Ticking back a name/contact that the current scene already shows must not add a second copy as a layer.
  const layer = document.formats[format.value]!.layers.find(item => item.role === role)
  if (layer && role !== 'logo' && currentVisual.value?.headline?.[role] !== undefined) layer.visible = false
}
// One outline icon set, 16px, drawn in the text colour (ADR-050). Paths only: no icon dependency.
const ICONS: Record<string, string> = {
  plus: 'M8 3v10M3 8h10', check: 'M3.5 8.5l3 3 6-7', close: 'M4 4l8 8M12 4l-8 8', chevron: 'M6 3.5l4.5 4.5L6 12.5',
  grid: 'M2.5 2.5h4.5v6h-4.5zM9 2.5h4.5v6H9zM2.5 11h4.5M9 11h4.5M2.5 13.5h3', text: 'M3 4V3h10v1M8 3v10M6 13h4',
  palette: 'M8 2.5a5.5 5.5 0 1 0 0 11c1 0 1.3-.7.9-1.4-.5-.9.1-1.8 1.1-1.8h1.2a2.3 2.3 0 0 0 2.3-2.4A5.5 5.5 0 0 0 8 2.5zM5.5 7h.01M8 5h.01M10.5 7h.01',
  image: 'M2.5 3h11v10h-11zM2.5 10.5l3.5-3 3 2.5 2-1.5 2.5 2', download: 'M8 2.5v8M4.5 7.5L8 11l3.5-3.5M3 13.5h10',
  eye: 'M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8zM8 6.2a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6z',
  spark: 'M8 2l1.4 4.1L13.5 7.5 9.4 8.9 8 13 6.6 8.9 2.5 7.5l4.1-1.4z', clock: 'M8 2.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM8 5v3.5l2 1.5',
  undo: 'M6 4L3 7l3 3M3 7h6.5a3.5 3.5 0 0 1 0 7H7', redo: 'M10 4l3 3-3 3M13 7H6.5a3.5 3.5 0 0 0 0 7H9',
  sliders: 'M3 4.5h6M12 4.5h1M3 11.5h1M7 11.5h6M10.5 3v3M5.5 10v3', pen: 'M3 13l.6-2.8L11 2.8l2.2 2.2-7.4 7.4zM9.8 4l2.2 2.2',
  box: 'M3 3h10v10H3zM8 6.2a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6z', sun: 'M8 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1',
  moon: 'M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z',
}
const Icon = (props: { n: string }) => h('svg', { class: 'i', viewBox: '0 0 16 16', 'aria-hidden': 'true' }, [h('path', { d: ICONS[props.n] })])
Icon.props = ['n']
// The editor shows one group of controls at a time (R-POSTER-EDITOR-004): steps while the poster has no usable
// version, tabs afterwards. Presentation only: nothing here is saved or put in the address.
type Group = 'textes' | 'boutique' | 'style' | 'reglages'
const GROUPS: [Group, string][] = [['textes', 'Textes'], ['boutique', 'Boutique'], ['style', 'Style'], ['reglages', 'Réglages']]
const groupNames = Object.fromEntries(GROUPS) as Record<Group, string>
const PHASES = ['Préparation', 'Génération', 'Fidélité', 'Téléchargement']
const IDENTITY = ['logo', 'shop_name', 'contact'] as const
const group = ref<Group>('textes'), visited = ref<Group[]>(['textes']), panel = ref<HTMLElement>(), rail = ref<HTMLElement>()
const stepping = computed(() => !visuals.value.some(item => item.status !== 'rejected'))
const shownGroups = computed(() => stepping.value ? GROUPS.slice(0, 3) : GROUPS)
const stepAt = computed(() => GROUPS.findIndex(item => item[0] === group.value))
// A poster that already had a version went through every step.
const reachable = (id: Group) => !stepping.value || visuals.value.length > 0 || visited.value.includes(id)
function go(target: Group, focus = true) {
  peek.value = false  // the group is behind the phone's poster sheet
  group.value = target
  if (!visited.value.includes(target)) visited.value.push(target)
  // Opened from elsewhere (« Continuer », a reason, a refusal): the group is shown from its top and takes the focus.
  if (focus) nextTick(() => {
    panel.value?.focus({ preventScroll: true })
    const top = rail.value?.getBoundingClientRect().top ?? 0
    if (top < 56 || top > window.innerHeight - 200) rail.value?.scrollIntoView()
  })
}
watch(stepping, on => { if (on && group.value === 'reglages') group.value = 'style' })
function tabKey(event: KeyboardEvent) {
  const tabs = [...(event.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('[role=tab]:not(:disabled)')]
  const move = ({ ArrowRight: 1, ArrowLeft: -1 } as Record<string, number>)[event.key]
  const target = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[tabs.length - 1] : move ? tabs[(tabs.indexOf(event.target as HTMLElement) + move + tabs.length) % tabs.length] : undefined
  if (target) { event.preventDefault(); target.focus(); target.click() }
}
// On one column the poster is small during the steps; this opens it in front of the step, which stays as it was.
const peek = ref(false)
const peeking = computed(() => peek.value && !!doc.value && stepping.value && viewportWidth.value <= 1080)
watch(peeking, on => { if (!on) peek.value = false })
let peekFrom: HTMLElement | null = null
function setPeek(on: boolean) {
  if (on) peekFrom = document.activeElement as HTMLElement | null
  peek.value = on
  nextTick(() => (on ? document.getElementById('fermer-affiche') : peekFrom)?.focus())
}
// A refusal that names a field, or whose only fix is in one group, opens that group and is written there, not in
// the general message.
const REFUSAL_GROUP: Record<string, Group> = { 'offer.title': 'textes', 'offer.price_ar': 'textes', title_missing: 'textes', price_stale: 'textes',
  contact: 'boutique', shop_name: 'boutique', logo: 'boutique', signature_missing: 'boutique', logo_disc_uncovered: 'boutique', layout_not_plannable: 'boutique', unsupported_font: 'reglages' }
const refusalGroup = (reason: ApiError) => REFUSAL_GROUP[reason.field ?? ''] ?? (reason.field?.startsWith('body.headline') ? 'textes' : REFUSAL_GROUP[reason.code])
const fieldError = ref<{ group: Group; text: string } | null>(null)
// The shop's details are copied into the poster when it is made: one that was empty then cannot be ticked here.
const identitySource = (role: typeof IDENTITY[number]) => role === 'logo' ? doc.value?.brand_snapshot.logo_asset : role === 'shop_name' ? doc.value?.brand_snapshot.name : doc.value?.brand_snapshot.contact
const view = ref<'create' | 'posters' | 'styles'>('create')
// The address says where the owner is: '' new poster, 'affiches', 'styles', or an open poster's id. Reload,
// back and a new tab then work, and the navigation is made of real links.
const VIEWS: Record<string, 'create' | 'posters' | 'styles'> = { '': 'create', affiches: 'posters', styles: 'styles' }
const here = () => creation.value?.id ?? (view.value === 'posters' ? 'affiches' : view.value === 'styles' ? 'styles' : '')
let routeDue = false
async function route() {
  const hash = window.location.hash.slice(1)
  try {
    if (/^[a-f0-9-]{36}$/.test(hash)) { if (creation.value?.id !== hash) await openCreation(hash); return }
    if (doc.value) await fresh()
    view.value = VIEWS[hash] ?? 'create'
    nextTick(() => document.querySelector('main')?.focus())
  } catch (reason) { window.history.replaceState(null, '', `#${here()}`); throw reason }
}
function onHash() { if (window.location.hash.slice(1) !== here()) { if (busy.value) routeDue = true; else perform(route) } }
function leave(hash: string) { window.location.hash = hash }
// A panel in front of the page takes the focus and gives it back; the page behind is inert meanwhile.
const vModal = {
  mounted(el: HTMLElement & { back?: Element | null }) { el.back = document.activeElement; el.tabIndex = -1; (el.querySelector<HTMLElement>('[data-focus]') ?? el).focus() },
  unmounted(el: HTMLElement & { back?: Element | null }) { (el.back as HTMLElement | null)?.focus?.() },
}
// A paid call is never one tap: the owner sees what it does and what it costs, then confirms.
const paid = ref<{ title: string; text: string; cost: string; label: string; run: () => Promise<void> } | null>(null)
const costLine = (micros?: number) => micros ? `Coût estimé : au plus ${dollars(micros)}.` : 'Mode de démonstration : aucune dépense.'
function askScene() {
  if (whyNoHeadline.value) { error.value = whyNoHeadline.value; go('textes'); return }  // also for « Nouvelle version »
  paid.value = { title: visuals.value.length ? 'Créer une nouvelle version ?' : 'Générer l’affiche ?', label: 'Lancer la génération', cost: costLine(caps.value?.scene_estimate_micros),
    text: visuals.value.length ? 'Mêmes textes et même style, un autre essai. Vos autres versions sont conservées et vous choisissez celle à exporter.' : 'L’IA compose l’affiche à partir de votre photo, de vos textes et du style choisi. Cela prend environ une minute.', run: createScene }
}
function askLook() {
  paid.value = { title: 'Créer un style depuis cette affiche ?', label: 'Créer le style', cost: costLine(caps.value?.plan_estimate_micros),
    text: 'Claude décrit le style de l’affiche modèle, jamais son produit ni ses textes. Le style est enregistré à côté des autres.', run: createLook }
}
function askRefine() {
  paid.value = { title: 'Ajuster la scène ?', label: 'Lancer l’ajustement', cost: costLine(caps.value?.scene_estimate_micros),
    text: 'L’IA refait la scène selon votre consigne. C’est une nouvelle version : les autres sont conservées.', run: refineScene }
}
function askText() {
  paid.value = { title: 'Proposer un ajustement du texte ?', label: 'Lancer la proposition', cost: costLine(caps.value?.plan_estimate_micros),
    text: 'Claude propose un réglage pour le texte sélectionné. Rien ne change sur l’affiche avant votre accord.', run: proposeText }
}
function askEffect() {
  paid.value = { title: 'Générer la matière du texte ?', label: 'Générer la matière', cost: costLine(caps.value?.texture_estimate_micros),
    text: 'L’IA crée une matière pour les lettres. Vous la vérifiez avant de l’appliquer.', run: generateEffect }
}
function askDiscard() {
  paid.value = { title: 'Abandonner vos modifications ?', label: 'Abandonner et recharger', cost: '',
    text: 'Les modifications non enregistrées de cette affiche seront perdues. La version enregistrée est rechargée.', run: discardAndReload }
}
const modalOpen = computed(() => !!(paid.value || review.value || finalPreview.value || opened.value))
// "Styles": a style opens in a panel; one made by the shop can be renamed or removed there.
const openedId = ref<string | null>(null), renameText = ref(''), renameError = ref('')
const opened = computed(() => {
  const own = savedLooks.value.find(item => item.id === openedId.value)
  if (own) return { id: own.id, name: own.name, image: `/api/assets/${own.reference_asset}?prepared=true`, direction: own.brief.direction_fr, brief: own.brief, own: true }
  const given = LOOKS.find(item => item.id === openedId.value && item.image)
  return given ? { id: given.id as string, name: given.label as string, image: given.image as string, direction: given.direction as string, brief: null, own: false } : null
})
function openLook(id: string) { openedId.value = id; renameText.value = opened.value?.name ?? ''; renameError.value = '' }
function useLook(id: string) { pickLook(id); rememberStyle(); openedId.value = null; leave('') }
const reloadLooks = async () => { savedLooks.value = (await api<{ items: SavedLook[] }>('/api/looks')).items }
// Renaming and removing are safe to repeat: each attempt has its own key.
async function renameLook() {
  const name = renameText.value.trim(), id = openedId.value!
  if (LOOKS.some(item => item.label.toLowerCase() === name.toLowerCase())) { renameError.value = 'Ce nom est celui d’un style fourni. Choisissez-en un autre.'; return }
  try {
    await mutation(`/api/looks/${id}`, { name }, undefined, crypto.randomUUID(), 'PUT')
    renameError.value = ''; await reloadLooks(); renameText.value = opened.value?.name ?? ''
  } catch (reason) {
    if (!(reason instanceof ApiError)) throw reason
    if (reason.code === 'look_name_taken') renameError.value = reason.message
    else if (reason.code === 'validation_error') renameError.value = 'Le nom doit compter de 1 à 40 caractères.'
    else if (reason.code === 'look_removed') { openedId.value = null; await reloadLooks(); throw new Error('Ce style a été retiré entre-temps. La liste est à jour.') }
    else throw reason
  }
}
function askRemoveLook() {
  const target = opened.value!
  paid.value = { title: `Retirer le style « ${target.name} » ?`, label: 'Retirer ce style', cost: '',
    text: 'Il ne sera plus proposé pour de nouvelles affiches. Les affiches faites avec ce style le gardent. Cette action ne peut pas être annulée.',
    run: async () => {
      await mutation(`/api/looks/${target.id}`, {}, undefined, crypto.randomUUID(), 'DELETE')
      openedId.value = null; await reloadLooks()
      if (look.value === target.id) { pickLook('clair'); rememberStyle() }
    } }
}
function confirmPaid() { const action = paid.value; paid.value = null; if (action) perform(action.run) }
function changePriceLater() {
  finalPreview.value = null
  notice.value = 'Modifiez le prix dans « Textes », puis créez une nouvelle version : le prix est dessiné dans l’image.'
  group.value = 'textes'
  nextTick(() => document.getElementById('champ-prix')?.focus())
}
const exportBlocked = computed(() => busy.value || !!job.value || !canvasReady.value || previewPolish.value || currentVisual.value?.status !== 'approved' || staleHeadline.value || discUncovered.value || issues.value.some(issue => issue.blocking))
// A title or price that the image model is drawing right now must not change under it: the scene would arrive stale.
const drawingTexts = computed(() => !!job.value && ['scene', 'refine'].includes(job.value.kind) && headline.value.on)
const stage = computed(() => !currentVisual.value ? (job.value && ['scene', 'refine'].includes(job.value.kind) ? 1 : 0) : currentVisual.value.status === 'approved' ? 3 : 2)
// The image model draws these words, and the server refuses what it cannot draw. Said here, before the paid step.
const headlineFaults = computed(() => {
  if (!headline.value.on || !doc.value) return { title: '', brand: '', subtitle: '' }
  const check = (label: string, value: string) => value.length > 60 ? `${label} dépasse 60 caractères (${value.length}) : l’IA ne peut pas le dessiner dans l’image. Raccourcissez-le.`
    : /["\r\n]/.test(value) ? `${label} contient un guillemet droit (") ou un retour à la ligne : l’IA ne peut pas le dessiner. Écrivez par exemple « 32 pouces ».` : ''
  return { title: check('Le titre', doc.value.offer.title.trim()), brand: check('La marque', headline.value.brand.trim()), subtitle: check('Le sous-titre', headline.value.subtitle.trim()) }
})
const whyNoHeadline = computed(() => headlineFaults.value.title || headlineFaults.value.brand || headlineFaults.value.subtitle)
const mainAction = computed(() => {
  const visual = currentVisual.value
  if (!visual || visual.status === 'rejected') return { label: 'Générer l’affiche', icon: 'spark', disabled: busy.value || !!job.value || !!whyNoHeadline.value, run: askScene }
  if (visual.status === 'pending_review') return { label: 'Vérifier la fidélité', icon: 'check', disabled: false, run: () => { review.value = visual; resetChecks() } }
  return { label: 'Vérifier l’aperçu final', icon: 'eye', disabled: exportBlocked.value, run: () => { perform(renderFinal) } }
})
const mainWhy = computed(() => !mainAction.value.disabled ? '' : currentVisual.value?.status === 'approved' ? whyNoExport.value : busy.value || job.value ? whyBusy.value : whyNoHeadline.value || whyBusy.value)
// The group that holds the control which unblocks the main action: its reason opens it.
const mainFix = computed<Group | null>(() => {
  if (!mainWhy.value || busy.value || job.value) return null
  if (currentVisual.value?.status !== 'approved') return whyNoHeadline.value ? 'textes' : null
  return staleTitle.value || stalePrice.value ? 'textes' : staleSignature.value || discUncovered.value ? 'boutique' : null
})
const textChecks = computed(() => {
  const drawn = review.value?.headline as Record<string, any> | null | undefined
  if (!drawn) return []
  const items = [{ key: 'text_title', label: drawn.brand ? 'Marque, titre et sous-titre' : 'Titre et sous-titre', value: [drawn.brand, drawn.title, drawn.subtitle].filter(Boolean).join(' · ') }]
  if (drawn.price_ar !== undefined) items.push({ key: 'text_price', label: 'Prix', value: `${Number(drawn.price_ar).toLocaleString('fr-FR')}\u00a0AR` })
  if (drawn.shop_name !== undefined || drawn.contact !== undefined) items.push({ key: 'text_signature', label: drawn.shop_name !== undefined ? 'Boutique et contact' : 'Contact', value: [drawn.shop_name, drawn.contact].filter(Boolean).join(' · ') })
  return items
})
const reviewKeys = computed(() => [...Object.keys(checkNames), ...textChecks.value.map(item => item.key)])
const waiting = 'Une tâche est en cours : patientez quelques instants.'
const whyBusy = computed(() => job.value ? waiting : '')
const whyNoText = computed(() => job.value ? waiting : !polish.value.trim() ? 'Écrivez d’abord votre consigne ci-dessus.' : '')
const whyNoRefine = computed(() => job.value ? waiting : !refinement.value.trim() ? 'Décrivez d’abord l’ajustement souhaité ci-dessus.' : '')
const whyNoLook = computed(() => job.value ? waiting : !lookReference.value ? 'Choisissez d’abord une affiche modèle ci-dessus.' : '')
const whyNoDraft = computed(() => !photos.value.length ? 'Ajoutez au moins une photo du produit.' : !intake.confirmed ? 'Cochez la case « Les photos correspondent… » pour continuer.' : '')
const whyNoExport = computed(() => job.value ? waiting
  : !currentVisual.value ? 'Générez d’abord l’affiche.'
  : currentVisual.value.status === 'pending_review' ? 'Comparez d’abord la version à votre photo et approuvez la fidélité du produit.'
  : currentVisual.value.status === 'rejected' ? 'Cette version a été refusée : choisissez une autre version ou générez-en une nouvelle.'
  : staleHeadline.value ? 'Un texte dessiné dans l’image a changé : générez une nouvelle version.'
  : discUncovered.value ? 'L’image contient un disque prévu pour le logo : replacez le logo dessus (cochez « Logo ») ou générez une nouvelle version.'
  : issues.value.some(issue => issue.blocking) ? 'Corrigez d’abord les éléments signalés sous l’affiche.'
  : previewPolish.value ? 'Appliquez ou refusez d’abord l’ajustement en cours.' : '')
const nextStep = computed(() => job.value && ['scene', 'refine'].includes(job.value.kind) ? 'Votre affiche est en cours de création. Cela prend environ une minute.'
  : !currentVisual.value ? 'Vérifiez les textes, choisissez un style, puis appuyez sur « Générer l’affiche ».'
  : currentVisual.value.status === 'pending_review' ? 'Comparez le produit à votre photo, puis approuvez sa fidélité.'
  : currentVisual.value.status === 'approved' ? 'Dernière étape : vérifiez l’aperçu final, puis téléchargez votre affiche.'
  : 'Choisissez une autre version sous l’affiche, ou générez une nouvelle version.')
const staleTitle = computed(() => { const baked = currentVisual.value?.headline?.title; return baked !== undefined ? baked !== doc.value?.offer.title : !!layout.value?.layers.some(layer => layer.role === 'title' && !layer.visible) })
const staleSignature = computed(() => (['shop_name', 'contact'] as const).some(role => { const baked = currentVisual.value?.headline?.[role]; return baked !== undefined ? baked !== profileValue(role) : !!profileValue(role) && !!layout.value?.layers.some(layer => layer.role === role && !layer.visible) }))
const stalePrice = computed(() => { const baked = currentVisual.value?.headline?.price_ar; return baked !== undefined ? baked !== doc.value?.offer.price_ar : !!layout.value?.layers.some(layer => layer.role === 'price' && !layer.visible) })
const staleHeadline = computed(() => !!currentVisual.value && (staleTitle.value || staleSignature.value || stalePrice.value))
// A hidden layer (the title, once the image carries it) has no properties panel.
const chosen = computed(() => layout.value?.layers.find(layer => layer.id === selected.value && layer.visible))
// « Retirer de l’affiche » (R-POSTER-EDITOR-005) for the element selected on the poster. What a version's image
// holds is never erased: the owner is told so and can leave the element out of the next version.
const inImage = (layer: Layer) => layer.role === 'logo' ? layer.kind === 'logo' && layer.shape === 'circle' && !!currentVisual.value?.logo_disc
  : (layer.role === 'shop_name' || layer.role === 'contact') && currentVisual.value?.headline?.[layer.role] !== undefined
const listed = computed(() => layout.value?.layers.filter(layer => layer.visible || inImage(layer)) ?? [])
const asked = ref(false)
function pick(id: string | null) { selected.value = id; asked.value = true }
const removal = computed(() => {
  const layer = layout.value?.layers.find(item => item.id === selected.value)
  if (!layer || !doc.value || layer.role === 'product') return null
  if (layer.role === 'title' || layer.role === 'price') return layer.visible && asked.value ? { role: layer.role, fixed: true, drawn: false, on: true } : null
  return { role: layer.role, fixed: false, drawn: inImage(layer), on: doc.value.include[layer.role] }
})
function removeFromPoster() {
  const role = removal.value?.role
  if (role && role !== 'title' && role !== 'price') edit(document => toggleIdentity(document, role, false))
}
const scale = computed(() => Math.min(canvasWidth.value / FORMATS[format.value][0], viewportWidth.value > 850 ? Math.max(.25, (viewportHeight.value - 300) / FORMATS[format.value][1]) : .62, .62))
const sources = computed(() => Object.fromEntries([
  ...Object.entries(effectSources.value).map(([id, url]) => [id, `${url}?prepared=true`]),
  ...visuals.value.map(item => [`scene:${item.id}`, `${item.image_url}?prepared=true`]),
  ...Object.values(doc.value?.formats ?? {}).flatMap(layout => layout.layers.filter(layer => layer.kind !== 'text').map(layer => [(layer as any).asset, `/api/assets/${(layer as any).asset}?prepared=true`])),
]))
const saveState = computed(() => { savingTick.value; return saver?.state ?? 'saved' })
const saveLabel = computed(() => ({ saved: 'Enregistré', dirty: 'Modifications en attente', saving: 'Enregistrement…', failed: 'Échec de l’enregistrement', conflict: 'Une autre version existe' }[saveState.value]))
const shownPrice = (value: number) => value.toLocaleString('fr-FR')
function tidyPrice() { try { priceText.value = shownPrice(parsePrice(priceText.value)) } catch { /* the error is already beside the field */ } }
const day = (stamp: string) => { const date = new Date(stamp); return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium' }).format(date) }
const dollars = (micros = 0) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'USD' }).format(micros / 1e6)

// An error already written beside its field is not repeated in the general message.
class Shown extends Error {}
// Why a generation failed, in the owner's words: what he can do differs with the cause.
function jobFailure(code: string | null) {
  const kept = ' Vos images et votre affiche sont conservées.'
  if (code === 'refused') return 'Le service d’images a refusé cette demande (photo ou texte non accepté). Essayez une autre photo, ou changez le titre ou l’ambiance.' + kept
  if (['timeout', 'provider_error', 'rate_limited', 'invalid_response'].includes(code ?? '')) return 'Le service d’images n’a pas répondu correctement. Réessayez dans une minute.' + kept
  if (['quota', 'auth', 'budget_exhausted'].includes(code ?? '')) return 'Le compte du service d’images doit être vérifié par l’administrateur (quota, clé ou budget). Vous pouvez encore modifier et télécharger vos affiches.'
  return `La tâche n’a pas abouti${code ? ` (code : ${code})` : ''}.${kept} Vous pouvez réessayer.`
}
function checkedPrice(text: string, field?: string) {
  try { const value = parsePrice(text); priceError.value = ''; return value }
  catch (reason) {
    priceError.value = (reason as Error).message
    // The price of an open poster is in « Textes »: the error is beside a field that must be on screen.
    if (field) { if (doc.value) group.value = 'textes'; nextTick(() => document.getElementById(field)?.focus()) }
    throw new Shown()
  }
}
async function perform(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''; fieldError.value = null
  try { await action() } catch (reason) {
    // Behind an open dialog the groups are inert: there the refusal goes to the message above the dialog.
    const held = doc.value && !modalOpen.value && reason instanceof ApiError ? refusalGroup(reason) : undefined
    if (held) { fieldError.value = { group: held, text: (reason as ApiError).message }; go(held) }
    else if (!(reason instanceof Shown)) error.value = reason instanceof Error ? reason.message : 'La demande a échoué. Réessayez ; si l’erreur persiste, rechargez la page.'
  }
  finally { busy.value = false; if (routeDue) { routeDue = false; onHash() } }
}
async function loadShop() {
  const [saved, capabilities, list] = await Promise.all([api<Profile>('/api/shop-profile'), api<Capabilities>('/api/capabilities'), api<Listing>('/api/creations?limit=50')])
  Object.assign(profile, saved); profileSaved = JSON.stringify(saved); caps.value = capabilities; library.value = list.items; libraryNext.value = list.next_cursor; activeTotal.value = list.total; showRemoved.value = false
  savedLooks.value = (await api<{ items: SavedLook[] }>('/api/looks')).items
  // The remembered style may be one of the shop's own looks, known only now.
  try { const remembered = JSON.parse(localStorage.getItem(STYLE_KEY) ?? 'null'); if (savedLooks.value.some(item => item.id === remembered?.look)) pickLook(remembered.look) } catch { /* convenience only */ }
  include.shop_name = false; include.contact = !!saved.contact; include.logo = !!saved.logo_asset
}
async function signIn() {
  await api('/api/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: password.value }) })
  password.value = ''; authenticated.value = true; await loadShop(); await route()
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
  if (whyNoDraft.value) { document.getElementById(photos.value.length ? 'champ-conforme' : 'champ-photos')?.focus(); throw new Error(whyNoDraft.value) }
  const price = checkedPrice(intake.price, 'prix-nouveau')
  await saveProfile()
  const inputBody = { name: intake.name, variant: intake.variant, photo_assets: photos.value.map(photo => photo.asset) }
  const signature = JSON.stringify(inputBody)
  if (pendingInput?.signature !== signature) pendingInput = { signature, id: (await mutation<{ id: string }>('/api/product-inputs', inputBody)).id }
  const input = pendingInput
  const result = await mutation<Creation>('/api/creations', { input_id: input.id, offer: { title: intake.name, price_ar: price }, brand_selection: include, primary_format: 'feed' })
  await adopt(result)
  if (photos.value.some(photo => photo.warnings.includes('low_resolution'))) smallPhotoOf.value = result.id
  if (doc.value?.include.contact) edit(document => {
    compactContact(document, defaultAlign(document))
    // The seal is the default for the footer it was designed for: a logo and a contact, no shop name.
    const logo = document.formats[format.value]!.layers.find(layer => layer.kind === 'logo')
    if (logo?.kind === 'logo' && document.include.logo && !document.include.shop_name) logo.shape = 'circle'
  })
}
async function adopt(result: Creation) {
  // Steps or tabs depend on the versions: for another poster they are read before the editor shows it.
  const opening = creation.value?.id !== result.id
  const known = opening ? (await api<{ items: Visual[] }>(`/api/creations/${result.id}/visuals`)).items : visuals.value
  if (opening) { group.value = 'textes'; visited.value = ['textes']; peek.value = false; fieldError.value = null; styleAccent.value = ''; accentPicked.value = false; asked.value = false }
  finalPreview.value = null; confirmedDownload.value = ''; previewLoaded.value = false; priceError.value = ''
  clearTimeout(pollTimer); job.value = null; review.value = null; proposal.value = null; effect.value = null; previewPolish.value = false
  saver?.dispose(); creation.value = result; visuals.value = known; doc.value = copy(result.document); priceText.value = shownPrice(result.document.offer.price_ar)
  selected.value = result.document.formats[result.document.primary_format]!.layers.find(layer => layer.role === 'title')?.id ?? null
  history = new History(); plan.value = null; styleReference.value = null
  saver = new DraftSaver(result.revision, request => mutation<Creation>(`/api/creations/${result.id}`, request.document, request.revision, request.key, 'PUT'), () => { savingTick.value++; if (saver?.error) error.value = saver.error })
  window.location.hash = result.id
  if (!opening) await refreshVisuals()
  styleReference.value = currentVisual.value?.style_reference_asset ?? null
  keptLook.value = null
  await restoreHeadline()
  await refreshEffects(); await nextTick()
  if (opening) window.scrollTo(0, 0)
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
async function openCreation(id: string) {
  await flush()
  const found = await api<Creation>(`/api/creations/${id}`)
  if (found.status === 'active') return adopt(found)
  // A removed poster refuses every save: show where it is and how to bring it back instead of an editor that cannot save.
  if (doc.value) await fresh()
  view.value = 'posters'; showRemoved.value = true; window.history.replaceState(null, '', '#affiches')
  await loadLibrary()
  notice.value = 'Cette affiche a été retirée de la liste. Remettez-la dans la liste pour l’ouvrir.'
}
// "Mes affiches": the shown list (in use or removed), its next page, and the count for the navigation.
const libraryNext = ref<string | null>(null), activeTotal = ref(0), shownTotal = ref(0), showRemoved = ref(false)
const listUrl = (extra = '') => `/api/creations?limit=50&status=${showRemoved.value ? 'abandoned' : 'active'}${extra}`
async function loadLibrary() {
  const list = await api<Listing>(listUrl())
  library.value = list.items; libraryNext.value = list.next_cursor; shownTotal.value = list.total
  activeTotal.value = showRemoved.value ? (await api<Listing>('/api/creations?limit=1')).total : list.total
}
async function moreLibrary() {
  const list = await api<Listing>(listUrl(`&before=${encodeURIComponent(libraryNext.value!)}`))
  library.value = [...library.value, ...list.items]; libraryNext.value = list.next_cursor
}
// The list is reloaded after every action, done or refused. Removing and restoring are safe to repeat, so each
// attempt has its own key; only the copy keeps its key, so that a lost answer cannot make two copies.
async function onRow(action: () => Promise<unknown>) {
  try { await action() }
  catch (reason) {
    await loadLibrary()
    if (reason instanceof ApiError && reason.code === 'revision_conflict') throw new Error('Cette affiche a changé depuis l’affichage de la liste. La liste est à jour : réessayez.')
    if (reason instanceof ApiError && reason.code === 'image_job_running') throw new Error('Une génération est en cours pour cette affiche : attendez sa fin.')
    throw reason
  }
  await loadLibrary()
}
const duplicate = (item: LibraryItem) => perform(async () => {
  let copied: Creation | undefined
  await onRow(async () => { copied = await mutation<Creation>(`/api/creations/${item.id}/copies`, { source_revision: item.revision, reason: 'new_campaign' }) })
  if (copied) await adopt(copied)
})
const restore = (item: LibraryItem) => perform(() => onRow(() => mutation(`/api/creations/${item.id}/restore`, {}, item.revision, crypto.randomUUID())))
function askRemove(item: LibraryItem) {
  paid.value = { title: `Retirer « ${item.title} » de la liste ?`, label: 'Retirer de la liste', cost: '',
    text: 'Rien n’est effacé : l’affiche et son fichier confirmé sont conservés. Pour l’ouvrir ou la télécharger à nouveau, remettez-la dans la liste.',
    run: () => onRow(() => mutation(`/api/creations/${item.id}/abandon`, {}, item.revision, crypto.randomUUID())) }
}
async function fresh() { await flush(); keptLook.value = null; finalPreview.value = null; confirmedDownload.value = ''; saver?.dispose(); doc.value = null; creation.value = null; plan.value = null; clearTimeout(pollTimer); job.value = null; await loadShop() }
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
    const next = copy(doc.value); change(next); previewPolish.value = false; history.record(doc.value, mergeKey); doc.value = next; saver!.queue(next); error.value = ''; fieldError.value = null
  } catch (reason) { error.value = reason instanceof Error ? reason.message : 'Modification invalide : elle n’a pas été appliquée.' }
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
// A new capsule must not hide the digits: light digits get the dark pill, dark digits the white one.
function capsuleFill() {
  const text = chosen.value?.kind === 'text' ? chosen.value.fill : '#000000'
  const [r, g, b] = [1, 3, 5].map(at => parseInt(text.slice(at, at + 2), 16))
  return (r * 299 + g * 587 + b * 114) / 1000 > 150 ? '#22262E' : '#FFFFFF'
}
function badgeColour(field: 'fill' | 'border_start' | 'border_end', event: Event) {
  if (chosen.value?.kind !== 'text' || !chosen.value.price_badge) return
  patchLayer(selected.value!, { price_badge: { ...chosen.value.price_badge, [field]: (event.target as HTMLInputElement).value } }, 'badge-colour')
}
function numeric(field: 'x' | 'y' | 'width' | 'height' | 'font_size', event: Event) {
  const value = Number((event.target as HTMLInputElement).value)
  const min = field === 'font_size' ? 24 : field === 'width' || field === 'height' ? 1 : -4000
  if (!Number.isFinite(value) || value < min || value > (field === 'font_size' ? 240 : 4000)) { error.value = `Valeur hors limites : saisissez un nombre entre ${min} et ${field === 'font_size' ? 240 : 4000}.`; return }
  patchLayer(selected.value!, { [field]: value }, field)
}
function changePrice() { try { const value = checkedPrice(priceText.value); edit(document => { document.offer.price_ar = value }, 'price') } catch { /* written beside the field */ } }
async function flush() { if (doc.value && checkedPrice(priceText.value, 'champ-prix') !== doc.value.offer.price_ar) throw new Error('Vérifiez le prix avant de continuer.'); await saver?.flush() }
function undo() { if (doc.value) { const previous = history.undo(doc.value); if (previous) { doc.value = previous; priceText.value = shownPrice(previous.offer.price_ar); priceError.value = ''; saver!.queue(previous) } } }
function redo() { if (doc.value) { const next = history.redo(doc.value); if (next) { doc.value = next; priceText.value = shownPrice(next.offer.price_ar); priceError.value = ''; saver!.queue(next) } } }
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
let planSignature = ''
// One tap for the simple composition. An unchanged request reuses its plan, so a retry after a lost
// response sends the same scene body and key instead of paying for a second image.
async function createScene() {
  stylePill()
  // A seal whose footer conditions are not met cannot be asked for: it becomes a plain logo before the plan is made,
  // so that the plan keeps a place for it.
  if (sealLayer.value && !sealOn.value && !layout.value?.scene.visual_id) edit(document => {
    const logo = document.formats[format.value]!.layers.find(layer => layer.kind === 'logo')
    if (logo?.kind === 'logo') { delete logo.shape; placeFooter(document) }
  })
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
  let result: any
  try { result = await mutation<any>(`/api/creations/${creation.value!.id}/scenes`, { plan_id: plan.value.id, format: format.value, ...(styleReference.value ? { style_reference_asset: styleReference.value } : {}), ...headlineBody(), acknowledged_warnings: lowResAccepted.value ? ['low_resolution'] : [] }, saver!.revision) }
  catch (reason) {
    // A reopened poster does not know its photo is small until the server says so: ask in the same dialog.
    if (!(reason instanceof ApiError && reason.code === 'acknowledgement_required')) throw reason
    smallPhotoOf.value = creation.value!.id; askScene(); throw new Shown()
  }
  follow({ id: result.job_id, kind: 'scene', status: 'queued', result_ref: null, error_code: null })
}
// A product photo under the server's minimum needs an explicit agreement before a paid generation. Both flags
// hold the id of the poster they were set for, so an agreement never carries over to another poster.
const smallPhotoOf = ref(''), lowResAcceptedOf = ref('')
const smallPhoto = computed(() => !!creation.value && smallPhotoOf.value === creation.value.id)
const lowResAccepted = computed({ get: () => !!creation.value && lowResAcceptedOf.value === creation.value.id,
  set: (agreed: boolean) => { lowResAcceptedOf.value = agreed ? creation.value?.id ?? '' : '' } })
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
        chooseLook(made.id); lookName.value = ''; lookReference.value = null
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
        // No notice here: the review opens in front and a notice would cover its instructions.
        review.value = visuals.value.find(item => item.id === completed.result_ref) ?? null; resetChecks()
      }
      if (job.value?.id === jobId) job.value = null
      return
    }
    if (['failed', 'interrupted', 'cancelled'].includes(job.value.status)) {
      error.value = job.value.status === 'interrupted' ? 'La génération a été interrompue. Aucun nouvel appel automatique n’a été lancé.' : job.value.kind === 'look' ? 'Le style n’a pas pu être décrit à partir de cette affiche. Essayez une autre image ; rien n’est perdu.' : jobFailure(job.value.error_code)
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
  finalPreview.value = value; previewLoaded.value = false; confirmedDownload.value = value.download_url ?? ''
}
async function renderFinal() {
  await flush()
  const result: any = await mutation(`/api/creations/${creation.value!.id}/renders`, { format: format.value }, saver!.revision)
  follow({ id: result.job_id, kind: 'render', status: 'queued', result_ref: null, error_code: null })
}
async function confirmFinal() {
  await flush()
  const result: any = await mutation(`/api/creations/${creation.value!.id}/confirmations`, {
    render_id: finalPreview.value.id, png_sha256: finalPreview.value.png_sha256, // One confirmation covers every listed point and warning (ADR-051); the server still requires each one.
    checks: Object.fromEntries(Object.keys(finalPoints).map(key => [key, true])),
    acknowledged_warning_ids: finalPreview.value.warnings.map((issue: LayoutIssue) => issue.id),
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
    // A contact that an older scene had drawn comes back as a layer: give it the compact style.
    const contact = document.formats[format.value]!.layers.find(layer => layer.role === 'contact')
    if (contact?.kind === 'text' && contact.visible && !contact.icon) compactContact(document, defaultAlign(document))
    // A seal follows the disc of the chosen version; without a disc nothing is printed at a guessed place.
    const logo = document.formats[format.value]!.layers.find(layer => layer.kind === 'logo')
    if (logo?.kind === 'logo' && logo.shape === 'circle') {
      document.include.logo = logo.visible = !!visual.logo_disc
      if (visual.logo_disc) sealOnDisc(document, visual.logo_disc)
    }
  })
  selected.value = null
}
function resetChecks() { rejection.value = ''; rejecting.value = false; zoomed.value = false }
async function decide(action: 'approve' | 'reject') {
  await mutation(`/api/visuals/${review.value!.id}/decision`, action === 'approve' ? { action, checks: Object.fromEntries(reviewKeys.value.map(key => [key, true])) } : { action, note: rejection.value })
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
function resized() { viewportHeight.value = window.innerHeight; viewportWidth.value = window.innerWidth }
const theme = ref(document.documentElement.dataset.theme === 'clair' ? 'clair' : 'sombre')
function toggleTheme() {
  theme.value = theme.value === 'clair' ? 'sombre' : 'clair'
  if (theme.value === 'clair') document.documentElement.dataset.theme = 'clair'; else delete document.documentElement.dataset.theme
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', theme.value === 'clair' ? '#f4f2ef' : '#0e0d0c')
  try { localStorage.setItem('affiche.theme', theme.value) } catch { /* convenience only */ }
}
function warnUnload(event: BeforeUnloadEvent) { if (saver?.unsaved) { event.preventDefault(); event.returnValue = '' } }
// The page's files can load while the application's own process is down or restarting (the front server answers
// 502 to 504, or nothing): say so with a retry, instead of a sign-in form that cannot work.
async function start() {
  checking.value = true; down.value = false
  try { authenticated.value = (await api<{ authenticated: boolean }>('/api/session')).authenticated; if (authenticated.value) { await loadShop(); await route() } }
  catch (reason) { const failure = reason as ApiError; if (failure.code === 'network' || [502, 503, 504].includes(failure.status)) down.value = true; else error.value = failure.message }
  finally { checking.value = false }
}
onMounted(() => {
  window.addEventListener('beforeunload', warnUnload); window.addEventListener('resize', resized); window.addEventListener('hashchange', onHash)
  return start()
})
onBeforeUnmount(() => { saver?.dispose(); clearTimeout(pollTimer); observer?.disconnect(); window.removeEventListener('beforeunload', warnUnload); window.removeEventListener('resize', resized); window.removeEventListener('hashchange', onHash) })
</script>

<template>
  <button class="skip" type="button" @click="($refs.main as HTMLElement).focus()">Aller au contenu</button>
  <header class="app-header" :inert="modalOpen || peeking"><a href="#" class="wordmark" translate="no"><svg class="mark" viewBox="0 0 20 24" aria-hidden="true"><path d="M2 1h11l5 5v17H2z" /><path d="M13 1v5h5" /><rect class="hue" x="5.5" y="10" width="9" height="2" rx="1" /><rect class="ink" x="5.5" y="15" width="6" height="4" rx="2" /></svg>Affiche Atelier</a><span v-if="authenticated" class="shop-label">{{ profile.name || 'Votre boutique' }}</span>
    <nav v-if="authenticated" class="nav" aria-label="Navigation"><a href="#" :aria-current="doc || view === 'create' ? 'page' : undefined"><Icon n="plus" />Créer</a><a href="#affiches" :aria-current="!doc && view === 'posters' ? 'page' : undefined"><Icon n="grid" />Mes affiches <span class="count">{{ activeTotal }}</span></a><a href="#styles" :aria-current="!doc && view === 'styles' ? 'page' : undefined"><Icon n="palette" />Styles <span class="count">{{ LOOKS.length - 1 + savedLooks.length }}</span></a></nav>
    <button class="ghost icon theme-toggle" type="button" :aria-label="theme === 'clair' ? 'Passer au thème sombre' : 'Passer au thème clair'" @click="toggleTheme"><Icon :n="theme === 'clair' ? 'moon' : 'sun'" /></button></header>
  <main ref="main" tabindex="-1">
    <p v-if="checking" role="status">Ouverture de l’atelier…</p>
    <div v-if="error" class="message error" role="alert">{{ error }}<button class="text-button" type="button" @click="error = ''">Fermer</button></div>
    <div v-if="notice" class="message notice" role="status">{{ notice }}<button class="text-button" type="button" @click="notice = ''">Fermer</button></div>
    <div v-if="caps?.image_mode === 'stub'" class="demo-notice">Mode de démonstration : les images sont simulées, sans dépense.</div>
    <section v-if="!checking && down" class="sign-in" role="alert"><h1>Service indisponible</h1><p>Le service est momentanément indisponible. Réessayez dans quelques minutes.</p><button type="button" class="primary" @click="start">Réessayer</button></section>
    <form v-if="!checking && !authenticated && !down" class="sign-in" @submit.prevent="perform(signIn)"><h1>Votre atelier d’affiches</h1><p>Connectez-vous pour retrouver les visuels de la boutique.</p><label>Mot de passe<input v-model="password" name="password" type="password" autocomplete="current-password" required /></label><button class="primary" :disabled="busy">Ouvrir l’atelier</button></form>
    <div v-if="authenticated && !doc && view === 'create'" class="intake-layout">
      <form class="intake" @submit.prevent="perform(createPoster)">
        <h1>Votre produit.<br />Une affiche à votre image.</h1><p class="intro">Ajoutez vos photos, votre titre et le prix. Vous pourrez ensuite ajuster chaque élément.</p>
        <label class="upload-zone">Photos du produit<input id="champ-photos" :disabled="busy" type="file" accept="image/jpeg,image/png,image/webp" multiple @change="event => perform(() => choosePhotos(event))" /><span>1 à 3 photos · JPEG, PNG ou WebP · 10 Mo maximum</span></label>
        <div class="photo-strip"><span v-for="(photo, index) in photos" :key="photo.asset" class="mini"><img :src="`/api/assets/${photo.asset}`" width="76" height="76" alt="Photo originale du produit" /><button type="button" class="text-button" :aria-label="`Retirer la photo ${index + 1}`" @click="photos.splice(index, 1)">Retirer</button></span></div>
        <p v-if="photos.some(photo => photo.warnings.includes('low_resolution'))" class="help" role="status">Photo petite (moins de 800 px de côté) : l’affiche peut manquer de netteté. Si vous avez une photo plus grande, préférez-la.</p>
        <label>Nom du produit<input v-model="intake.name" name="product" autocomplete="off" maxlength="160" required placeholder="Ex. Soundcore R50i…" /></label>
        <div class="form-row"><label>Variante confirmée<input v-model="intake.variant" name="variant" autocomplete="off" maxlength="160" required /></label><label>Prix en ariary<input id="prix-nouveau" v-model="intake.price" name="price" autocomplete="off" inputmode="numeric" required placeholder="90 000…" :aria-invalid="!!priceError || undefined" aria-describedby="erreur-prix" @input="priceError = ''" /></label></div>
        <p v-if="priceError" id="erreur-prix" class="why" role="alert">{{ priceError }}</p>
        <label class="check"><input id="champ-conforme" v-model="intake.confirmed" type="checkbox" />Les photos correspondent au produit et à la variante indiqués.</label>
        <details open><summary>Identité de la boutique</summary><label>Nom de la boutique<input v-model="profile.name" name="shop" autocomplete="off" maxlength="160" /></label><label>Contact<textarea v-model="profile.contact" name="contact" autocomplete="off" rows="2" maxlength="500" placeholder="Téléphone, adresse ou WhatsApp…" /></label><label>Logo<input :disabled="busy" type="file" accept="image/jpeg,image/png,image/webp" @change="event => perform(() => chooseLogo(event))" /></label><img v-if="profile.logo_asset" class="logo-preview" :src="`/api/assets/${profile.logo_asset}`" width="120" height="80" alt="Logo de la boutique" /><div class="checks-row"><label v-for="role in (['logo','shop_name','contact'] as const)" :key="role" class="check"><input v-model="include[role]" type="checkbox" />{{ roleNames[role] }}</label></div></details>
        <button class="primary wide" :disabled="busy">{{ busy ? 'Préparation…' : 'Préparer mon affiche' }}</button><p v-if="whyNoDraft" class="why" role="status">{{ whyNoDraft }}</p>
      </form>
    </div>
    <section v-if="authenticated && !doc && view === 'posters'" class="gallery" aria-labelledby="titre-affiches">
      <div class="titlerow"><div class="what"><h1 id="titre-affiches">Mes affiches</h1><p class="meta">{{ activeTotal }} {{ activeTotal > 1 ? 'affiches' : 'affiche' }} · ouvrez-en une pour la modifier, changer son prix ou la télécharger à nouveau</p></div><label class="check"><input v-model="showRemoved" type="checkbox" :disabled="busy" @change="perform(loadLibrary)" />Afficher les affiches retirées</label><button class="primary" @click="leave('')"><Icon n="plus" />Nouvelle affiche</button></div>
      <p v-if="!library.length" class="empty">{{ showRemoved ? 'Aucune affiche retirée.' : 'Vos affiches apparaîtront ici dès la première création.' }}</p>
      <div class="rows"><div v-for="item in library" :key="item.id" class="library-row">
        <component :is="showRemoved ? 'div' : 'button'" class="library-item" :type="showRemoved ? undefined : 'button'" @click="showRemoved || perform(() => openCreation(item.id))"><img v-if="item.thumbnail_url" :src="item.thumbnail_url" width="48" height="60" alt="" loading="lazy" /><Icon v-else n="image" /><strong translate="no">{{ item.title }}</strong><span>{{ [showRemoved ? 'Retirée' : stateNames[item.state], `${shownPrice(item.price_ar)} Ar`, day(item.created_at), item.variant].filter(Boolean).join(' · ') }}</span><Icon v-if="!showRemoved" n="chevron" /><i v-else /></component>
        <div class="row-actions"><button type="button" :disabled="busy" :aria-label="`Dupliquer « ${item.title} »`" @click="duplicate(item)">Dupliquer</button><button v-if="showRemoved" type="button" :disabled="busy" :aria-label="`Remettre « ${item.title} » dans la liste`" @click="restore(item)">Remettre dans la liste</button><button v-else type="button" :disabled="busy" :aria-label="`Retirer « ${item.title} » de la liste`" @click="askRemove(item)">Retirer de la liste</button></div>
      </div></div>
      <p v-if="libraryNext" class="more"><button type="button" :disabled="busy" @click="perform(moreLibrary)">Voir plus ({{ shownTotal - library.length }} de plus)</button></p>
    </section>
    <section v-if="authenticated && !doc && view === 'styles'" class="gallery" aria-labelledby="titre-styles">
      <div class="titlerow"><div class="what"><h1 id="titre-styles">Styles</h1><p class="meta">{{ LOOKS.length - 1 }} styles fournis · {{ savedLooks.length }} {{ savedLooks.length > 1 ? 'créés' : 'créé' }} depuis vos affiches modèles</p></div></div>
      <div class="look-wall"><button v-for="item in LOOKS.filter(item => item.image)" :key="item.id" type="button" class="look-card" @click="openLook(item.id)"><img :src="item.image!" width="180" height="180" alt="" loading="lazy" /><span>{{ item.label }}<small>Fourni</small></span></button><button v-for="item in savedLooks" :key="item.id" type="button" class="look-card" @click="openLook(item.id)"><img :src="`/api/assets/${item.reference_asset}?prepared=true`" width="180" height="180" alt="" loading="lazy" /><span translate="no">{{ item.name }}<small translate="yes">Créé depuis une affiche</small></span></button></div>
      <p class="help">Ouvrez un style pour voir sa description. Pour créer un style, ouvrez une affiche puis « Créer un style depuis une affiche » dans « Style ».</p>
    </section>
    <div v-if="doc" class="editor" :class="{ stepping }" :inert="modalOpen">
      <div class="titlerow" :inert="peeking">
        <div class="what"><h1 translate="no">{{ doc.offer.title || 'Affiche sans titre' }}</h1><p class="meta"><span class="step-short">{{ PHASES[stage] }} · </span>Publication · 1080 × 1350 · <span role="status" aria-live="polite">{{ saveLabel }}</span></p></div>
        <ol class="progress" aria-label="Avancement"><li v-for="(name, index) in PHASES" :key="name" :class="{ done: index < stage, now: index === stage }" :aria-current="index === stage ? 'step' : undefined"><Icon v-if="index < stage" n="check" />{{ name }}</li></ol>
        <div class="undo"><button class="ghost icon" :disabled="!history.past.length" aria-label="Annuler" title="Annuler" @click="undo"><Icon n="undo" /></button><button class="ghost icon" :disabled="!history.future.length" aria-label="Rétablir" title="Rétablir" @click="redo"><Icon n="redo" /></button></div>
      </div>
      <div class="work">
        <aside ref="rail" class="rail card" :inert="peeking">
          <p v-if="stepping" class="step-count">Étape {{ stepAt + 2 }} sur 4</p>
          <div class="tabs"><span v-if="stepping" class="tab done"><Icon n="check" />Produit</span>
            <div role="tablist" :aria-label="stepping ? 'Étapes de l’affiche' : 'Groupes de réglages'" @keydown="tabKey"><button v-for="([id, name], index) in shownGroups" :id="`onglet-${id}`" :key="id" type="button" class="tab" role="tab" :aria-selected="group === id" aria-controls="panneau" :tabindex="group === id ? 0 : -1" :disabled="!reachable(id)" @click="go(id, false)"><span v-if="stepping" class="n" aria-hidden="true">{{ index + 2 }}</span>{{ name }}</button></div></div>
          <div id="panneau" ref="panel" class="panel" role="tabpanel" tabindex="-1" :aria-labelledby="`onglet-${group}`">
            <p v-if="fieldError?.group === group" class="why refusal" role="alert">{{ fieldError.text }}</p>
            <template v-if="group === 'textes'">
            <p class="help lead">Les mots de l’affiche. Seuls le titre et le prix sont obligatoires.</p>
            <label>Titre<textarea :value="doc.offer.title" name="title" autocomplete="off" maxlength="240" rows="2" :disabled="drawingTexts" :aria-invalid="!!headlineFaults.title || undefined" @input="event => edit(d => { d.offer.title = (event.target as HTMLTextAreaElement).value }, 'title')" /></label>
            <p v-if="headlineFaults.title" class="why" role="status">{{ headlineFaults.title }}</p>
            <p v-if="staleTitle" class="why" role="status">Le titre est dessiné dans l’image<template v-if="currentVisual?.headline"> (« {{ currentVisual.headline.title }} »)</template>. Pour le changer, générez une nouvelle version, ou remettez l’ancien titre.</p>
            <label>Prix en ariary<span class="unit"><input id="champ-prix" v-model="priceText" name="price" autocomplete="off" inputmode="numeric" :disabled="drawingTexts && headline.price" :aria-invalid="!!priceError || undefined" aria-describedby="erreur-prix" @input="changePrice" @blur="tidyPrice" /></span></label>
            <p v-if="priceError" id="erreur-prix" class="why" role="alert">{{ priceError }}</p>
            <p v-if="stalePrice" class="why" role="status">Le prix est dessiné dans l’image<template v-if="currentVisual?.headline?.price_ar !== undefined"> ({{ currentVisual.headline.price_ar.toLocaleString('fr-FR') }} AR)</template>. Pour le changer, générez une nouvelle version.</p>
            <template v-if="headline.on"><label>Marque (facultative)<input v-model="headline.brand" name="brand" autocomplete="off" spellcheck="false" maxlength="60" placeholder="JBL…" :disabled="busy || !!job" :aria-invalid="!!headlineFaults.brand || undefined" /></label><p v-if="headlineFaults.brand" class="why" role="status">{{ headlineFaults.brand }}</p><label v-if="headline.brand.trim()" class="check"><input v-model="headline.brand_text" type="checkbox" :disabled="busy || !!job" />Écrire la marque en texte simple (si l’IA ne connaît pas son logo)</label><label>Sous-titre (facultatif)<input v-model="headline.subtitle" name="subtitle" autocomplete="off" maxlength="60" placeholder="CASQUE SANS FIL…" :disabled="busy || !!job" :aria-invalid="!!headlineFaults.subtitle || undefined" /></label><p v-if="headlineFaults.subtitle" class="why" role="status">{{ headlineFaults.subtitle }}</p><div class="choice"><span id="accent-word-label">Mot du titre en couleur</span><div class="chips" role="group" aria-labelledby="accent-word-label"><button v-for="word in accentWords" :key="word" type="button" class="chip" translate="no" :aria-pressed="accentWord === word" :disabled="busy || !!job" @click="headline.accent_word = word">{{ word }}</button><button type="button" class="chip" :aria-pressed="!accentWord" :disabled="busy || !!job" @click="headline.accent_word = ''">Aucun</button></div></div></template>
            <div class="choice"><span id="accent-colour-label">Couleur d’accent</span><div class="chips" role="group" aria-labelledby="accent-colour-label"><button v-for="[value, name] in ACCENTS" :key="value" type="button" class="sw" :style="{ background: value }" :aria-label="name" :title="name" :aria-pressed="headline.accent_colour.toLowerCase() === value" :disabled="busy || !!job" @click="pickAccent(value)" /><label class="other" :class="{ on: !ACCENTS.some(([value]) => value === headline.accent_colour.toLowerCase()) }">Autre…<input :value="headline.accent_colour" type="color" aria-label="Autre couleur d’accent" @input="pickAccent(($event.target as HTMLInputElement).value)" :disabled="busy || !!job" /></label></div></div>
            <p class="sub">Ce que l’IA dessine dans l’image</p><p class="help">Par défaut, l’IA compose le titre et le prix avec la scène, comme sur une affiche de marque. Vérifiez chaque mot et chaque chiffre avant d’approuver la version ; pour corriger, générez une nouvelle version.</p>
            <label class="check"><input v-model="headline.on" type="checkbox" :disabled="busy || !!job" /> Laisser l’IA composer le titre dans l’image</label>
            <label v-if="headline.on" class="check"><input v-model="headline.price" type="checkbox" :disabled="busy || !!job" /> Dessiner aussi le prix dans l’image</label>
            </template>
            <template v-else-if="group === 'boutique'">
            <p class="help lead">Ce qui identifie votre boutique sur l’affiche.</p>
            <div class="checks-row"><label v-for="role in IDENTITY" :key="role" class="check"><input :checked="doc.include[role]" type="checkbox" :disabled="!identitySource(role)" @change="event => edit(d => toggleIdentity(d, role, (event.target as HTMLInputElement).checked))" />{{ roleNames[role] }}</label></div>
            <p v-if="IDENTITY.some(role => !identitySource(role))" class="help">Une case grisée : cette information n’était pas enregistrée à la création de cette affiche. Renseignez-la sur l’écran « Créer », puis préparez une nouvelle affiche.</p>
            <p v-if="staleSignature" class="why" role="status">{{ currentVisual?.headline?.shop_name !== undefined ? 'Le nom de la boutique ou le contact' : 'Le contact' }} est dessiné dans l’image. Pour le changer ou le retirer, générez une nouvelle version.</p>
            <label v-if="doc.include.contact && contactLayer?.kind === 'text'">Position du contact<select aria-label="Position du contact" :value="sealOn ? 'right' : chosenAlign" :disabled="sealOn" @change="moveContact"><option value="left">Gauche</option><option value="center">Centre</option><option value="right">Droite</option></select></label>
            <p v-if="doc.include.contact && sealOn" class="help">Avec le sceau, le contact est à droite.</p>
            <p v-else-if="doc.include.contact && drawnContact" class="help">Le contact est dessiné dans l’image : la position s’applique à la prochaine version.<template v-if="logoShown && !sealLayer"> Gardez le logo à l’écart du contact, ou générez une nouvelle version.</template></p>
            <p v-else-if="doc.include.contact && doc.include.logo && !sealLayer" class="help">Le contact se place dans l’espace à droite du logo.</p>
            <label v-if="doc.include.logo && logoLayer" class="check"><input type="checkbox" :checked="layout?.scene.visual_id ? !!sealLayer : sealOn" :disabled="busy || !!job || !!whyNoSeal" @change="setSeal" />Logo en sceau rond dans l’image</label>
            <p v-if="doc.include.logo && whyNoSeal" class="why" role="status">{{ whyNoSeal }} <button v-if="sealNeedsTexts" type="button" class="text-button" @click="go('textes')">Ouvrir « Textes »</button></p>
            <p v-else-if="sealLayer" class="help">L’image prévoit un disque blanc vide et votre logo y est imprimé tel quel, découpé en rond.</p>
            <template v-if="headline.on && doc.include.contact"><p class="sub">Ce que l’IA dessine dans l’image</p><label class="check"><input v-model="headline.contact" type="checkbox" :disabled="busy || !!job || !!whyNoDrawnContact" /> Dessiner aussi le contact dans l’image</label><p v-if="whyNoDrawnContact" class="why" role="status">{{ whyNoDrawnContact }}</p><p v-else class="help">Dessiné par l’IA, le contact est composé avec le prix. Décoché, il est écrit par-dessus l’image, tel que vous l’avez saisi.</p></template>
            </template>
            <template v-else-if="group === 'style'">
            <p class="help lead">L’allure de l’affiche : choisissez un style, ou décrivez l’ambiance vous-même.</p>
            <div class="look-grid"><button v-for="item in LOOKS" :key="item.id" type="button" class="look" :class="{ selected: look === item.id }" :aria-pressed="look === item.id" :disabled="busy || !!job" @click="chooseLook(item.id)"><img v-if="item.image" :src="item.image" width="96" height="96" alt="" /><span v-else class="add"><Icon n="pen" /></span><span>{{ item.label }}</span></button><button v-for="item in savedLooks" :key="item.id" type="button" class="look" :class="{ selected: look === item.id }" :aria-pressed="look === item.id" :disabled="busy || !!job" @click="chooseLook(item.id)"><img :src="`/api/assets/${item.reference_asset}?prepared=true`" width="96" height="96" alt="" /><span translate="no">{{ item.name }}</span></button></div>
            <p v-if="styleAccent" class="help" role="status">Ce style propose sa couleur d’accent ; la vôtre est conservée. <button type="button" class="text-button" @click="useStyleAccent">Utiliser la couleur du style</button></p>
            <p v-if="keptLook && look === 'libre'" class="help">Le style « <span translate="no">{{ keptLook.name }}</span> » a été retiré : cette affiche le garde tant que vous ne changez pas l’ambiance ni le style.</p>
            <label class="ambiance">{{ look === 'libre' ? 'Ambiance souhaitée' : 'Ambiance (modifiable)' }}<textarea v-model="direction" name="direction" autocomplete="off" rows="3" maxlength="400" @input="look = 'libre'; keptLook = null" /></label>
            <details v-if="caps?.planner_available" class="new-look"><summary>Créer un style depuis une affiche</summary><p class="help">Choisissez une affiche que vous aimez. Claude décrit son style (fond, lumière, couleurs, typographie), jamais son produit ni ses textes. Le style est enregistré à côté des autres et réutilisable.</p><label>Affiche modèle<input :disabled="busy || !!job" type="file" accept="image/jpeg,image/png,image/webp" @change="event => perform(() => chooseLookReference(event))" /></label><div v-if="lookReference" class="photo-strip"><img :src="`/api/assets/${lookReference}?prepared=true`" width="76" height="76" alt="Affiche modèle pour le nouveau style" /></div><label>Nom du style (facultatif)<input v-model="lookName" name="look" autocomplete="off" maxlength="40" placeholder="Vagues bleues…" :disabled="busy || !!job" /></label><button class="secondary" :disabled="busy || !!job || !lookReference" @click="askLook"><Icon n="plus" />Enregistrer ce style</button><p v-if="whyNoLook" class="why" role="status">{{ whyNoLook }}</p></details>
            </template>
            <template v-else>
            <p class="help lead">Choisissez l’élément à régler, ici ou sous l’affiche.</p>
            <div class="layer-list" role="group" aria-label="Élément à régler"><button type="button" :aria-pressed="selected === null" @click="pick(null)">Scène</button><button v-for="layer in listed" :key="layer.id" type="button" :aria-pressed="selected === layer.id" @click="pick(layer.id)">{{ roleNames[layer.role] }}</button></div>
            <label class="check"><input v-model="dragEnabled" type="checkbox" />Déplacer les éléments</label>
            <div v-if="chosen" class="layer-properties">
              <template v-if="chosen.kind === 'text'"><p class="sub">Typographie</p><label>Police<select aria-label="Police" :value="chosen.font_id" @change="changeFont"><option value="noto-sans">Noto Sans</option><option value="noto-serif">Noto Serif</option><option value="montserrat-black-italic">Montserrat Black Italic</option></select></label><div class="form-row"><label>Taille<input type="number" min="24" max="240" :value="chosen.font_size" @change="numeric('font_size', $event)" /></label><label>Couleur<input type="color" :value="chosen.fill" @input="event => patchLayer(selected!, { fill: (event.target as HTMLInputElement).value }, 'colour')" /></label></div><div class="form-row"><label>Graisse<select :value="chosen.weight" @change="event => patchLayer(selected!, { weight: Number((event.target as HTMLSelectElement).value) as 400 | 700 | 900 })"><template v-if="chosen.font_id !== 'montserrat-black-italic'"><option :value="400">Normal</option><option :value="700">Gras</option></template><option v-else :value="900">Très gras italique</option></select></label><label>Alignement<select :value="chosen.align" @change="event => patchLayer(selected!, { align: (event.target as HTMLSelectElement).value as any })"><option value="left">Gauche</option><option value="center">Centré</option><option value="right">Droite</option></select></label></div><template v-if="chosen.role === 'price'"><label>Présentation du prix<select aria-label="Présentation du prix" :value="chosen.price_badge ? 'capsule' : 'simple'" @change="event => patchLayer(selected!, { price_badge: (event.target as HTMLSelectElement).value === 'capsule' ? { fill: capsuleFill(), border_start: '#009FE3', border_end: '#1853BD' } : null })"><option value="simple">Texte simple — Ar</option><option value="capsule">Capsule — AR plus petit</option></select></label><div v-if="chosen.price_badge" class="form-row"><label v-for="field in (['fill', 'border_start', 'border_end'] as const)" :key="field">{{ { fill: 'Fond du prix', border_start: 'Contour début', border_end: 'Contour fin' }[field] }}<input type="color" :value="chosen.price_badge[field]" @input="event => badgeColour(field, event)" /></label></div></template><div class="checks-row"><label class="check"><input type="checkbox" :checked="!!chosen.outline" @change="event => patchLayer(selected!, { outline: (event.target as HTMLInputElement).checked ? { colour: '#17324D', width: 2 } : null })" />Contour</label><label class="check"><input type="checkbox" :checked="!!chosen.shadow" @change="event => patchLayer(selected!, { shadow: (event.target as HTMLInputElement).checked ? { colour: '#000000', blur: 6, offset_x: 0, offset_y: 4, opacity: .5 } : null })" />Ombre</label></div><button v-if="chosen.texture_effect_id" class="quiet" @click="patchLayer(chosen.id, { texture_effect_id: null })">Retirer la matière du texte</button></template>
              <p class="sub">Position et dimensions</p><div class="form-row" v-for="pair in ([['x','y'],['width','height']] as const)" :key="pair[0]"><label v-for="field in pair" :key="field">{{ { x:'Position X', y:'Position Y', width:'Largeur', height:'Hauteur' }[field] }}<input type="number" :value="Math.round(chosen[field])" @change="numeric(field, $event)" /></label></div>
              <template v-if="chosen.kind === 'text' && ['title','price'].includes(chosen.role)"><p class="sub">Ajuster ce texte avec une consigne</p><p class="help">Seul le {{ chosen.role === 'price' ? 'prix' : 'titre' }} sélectionné sera ajusté. La scène reste intacte.</p><label>Votre consigne<textarea v-model="polish" name="polish" autocomplete="off" maxlength="500" rows="3" placeholder="Ex. Un titre doré avec une ombre légère…" /></label><button :disabled="busy || !!job || !polish.trim() || !caps?.planner_available" @click="askText">Proposer un ajustement</button><small v-if="caps?.planner_available">Estimation Claude : {{ dollars(caps?.plan_estimate_micros) }}</small><p v-else class="help">Les consignes seront disponibles une fois Claude configuré. Les réglages manuels restent disponibles.</p>
              <p v-if="caps?.planner_available && whyNoText" class="why" role="status">{{ whyNoText }}</p>
              <div v-if="proposal && proposal.layer_id === selected" class="plan"><p>{{ proposal.patch.summary_fr }}</p><template v-if="proposal.status === 'pending'"><div v-if="proposal.patch.content_change"><p><strong>Contenu partagé modifié</strong> · Toutes les tailles de cette affiche sont concernées.</p><p>Avant : {{ proposal.before.offer[proposal.patch.content_change.field] }}<br />Après : {{ proposal.patch.content_change.value }}</p><label class="check"><input v-model="acknowledgeContent" type="checkbox" />Je confirme ce nouveau contenu.</label></div><button :disabled="busy || (!!proposal.patch.content_change && !acknowledgeContent)" @click="perform(applyProposal)">Appliquer au texte</button><button class="quiet" :disabled="busy" @click="perform(rejectProposal)">Refuser l’ajustement</button></template><template v-else-if="proposal.status === 'applied' && proposal.patch.texture_request"><p>Matière proposée : {{ proposal.patch.texture_request.description }}</p><button :disabled="busy || !!job" @click="askEffect">Générer la matière du texte</button><small>Appel image distinct : {{ dollars(caps?.texture_estimate_micros) }}</small></template></div>
              <div v-if="effect?.status === 'proposed' && effect.layer_id === selected" class="plan"><p>Vérifiez la matière dans l’aperçu. Les lettres et le montant restent exacts.</p><button :disabled="busy" @click="perform(() => decideEffect('apply'))">Appliquer la matière</button><button class="quiet" :disabled="busy" @click="perform(() => decideEffect('reject'))">Refuser la matière</button></div>
              </template>
            </div>
            <div v-else-if="currentVisual"><p class="sub">Cadrage de la scène</p><p class="help">Le produit fait partie de la scène. Ajustez son cadrage ou demandez une nouvelle version.</p><label>Zoom<input type="range" min="1" max="2" step="0.01" :value="sceneZoom" @input="zoomScene" /></label><label>Position horizontale<input type="range" min="0" max="1" step="0.01" :value="scenePan.x" @input="panScene('x', $event)" /></label><label>Position verticale<input type="range" min="0" max="1" step="0.01" :value="scenePan.y" @input="panScene('y', $event)" /></label><label>Ajustement de la scène<textarea v-model="refinement" name="refinement" autocomplete="off" rows="3" maxlength="500" placeholder="Ex. Une lumière plus chaude, en conservant la composition…" /></label><button :disabled="busy || !!job || !refinement.trim()" @click="askRefine">Ajuster la scène</button><small>Appel image estimé : {{ dollars(caps?.scene_estimate_micros) }}</small><p v-if="whyNoRefine" class="why" role="status">{{ whyNoRefine }}</p></div>
            <p v-else class="help">Choisissez un élément sous l’affiche pour le régler.</p>
            </template>
          </div>
          <div v-if="stepping" class="main-action step-nav">
            <button v-if="group !== 'textes'" type="button" class="secondary" @click="go(GROUPS[stepAt - 1][0])">Retour</button>
            <button type="button" class="ghost icon see" aria-label="Voir l’affiche" title="Voir l’affiche" @click="setPeek(true)"><Icon n="image" /></button>
            <button v-if="group !== 'style'" type="button" class="primary" @click="go(GROUPS[stepAt + 1][0])">Continuer<Icon n="chevron" /></button>
            <button v-else type="button" class="primary" :disabled="mainAction.disabled" @click="mainAction.run"><Icon :n="mainAction.icon" />{{ mainAction.label }}</button>
            <p v-if="group === 'style' && mainWhy" class="why" role="status">{{ mainWhy }} <button v-if="mainFix && mainFix !== group" type="button" class="text-button" @click="go(mainFix)">Ouvrir « {{ groupNames[mainFix] }} »</button></p>
          </div>
        </aside>
        <section class="stage" :class="{ peek: peeking }" aria-label="Affiche" :role="peeking ? 'dialog' : undefined" :aria-modal="peeking || undefined" @keydown.esc="peeking && setPeek(false)">
          <button v-if="peeking" id="fermer-affiche" type="button" class="secondary back" @click="setPeek(false)"><Icon n="close" />Revenir à l’étape</button>
          <div class="stage-head"><p class="coach" role="status"><Icon n="clock" /><span><b>À faire :</b> {{ nextStep }}</span></p>
            <div v-if="!stepping" class="main-action"><button type="button" class="primary" :disabled="mainAction.disabled" @click="mainAction.run"><Icon :n="mainAction.icon" />{{ mainAction.label }}</button>
            <p v-if="mainWhy" class="why" role="status">{{ mainWhy }} <button v-if="mainFix && mainFix !== group" type="button" class="text-button" @click="go(mainFix)">Ouvrir « {{ groupNames[mainFix] }} »</button></p></div></div>
          <div class="proof">
            <figure v-if="currentVisual?.original_urls?.length" class="photo"><img :src="currentVisual.original_urls[0]" width="120" height="120" alt="Photo d’origine du produit" /><figcaption>Votre photo</figcaption></figure>
            <div ref="canvasHost" class="canvas-host" :class="{ generating: !!job && ['scene', 'refine'].includes(job.kind) }"><PosterCanvas :document="previewDoc!" :readonly="previewPolish" :format="format" :sources="sources" :selected="selected" :scale="scale" :drag-enabled="dragEnabled" @select="pick" @change="patchLayer" @issues="issues = $event" @ready="canvasReady = $event" @error="error = $event" /></div>
          </div>
          <button type="button" class="text-button see-big" @click="setPeek(true)">Voir l’affiche en grand</button>
          <div class="selection">
            <div class="layer-list" role="group" aria-label="Éléments de l’affiche"><button type="button" :aria-pressed="selected === null" @click="pick(null)">Scène</button><button v-for="layer in listed" :key="layer.id" type="button" :aria-pressed="selected === layer.id" @click="pick(layer.id)">{{ roleNames[layer.role] }}<template v-if="!layer.visible"> ({{ layer.role === 'logo' ? 'retiré' : 'dans l’image' }})</template></button></div>
            <p v-if="removal?.fixed" class="help">{{ removal.role === 'title' ? 'Le titre' : 'Le prix' }} ne se retire pas : une affiche annonce toujours le produit et son prix.</p>
            <template v-else-if="removal && !removal.drawn">
              <button v-if="removal.on" type="button" class="remove" @click="removeFromPoster"><Icon n="close" />Retirer de l’affiche</button>
              <p v-else class="help">{{ roleNames[removal.role] }} retiré de l’affiche. <button type="button" class="text-button" @click="go('boutique')">Le remettre depuis « Boutique »</button></p>
            </template>
            <template v-else-if="removal">
              <p class="help">{{ removal.role === 'logo' ? 'Le logo est imprimé sur un disque dessiné dans l’image de cette version : ce disque' : `L’image de cette version contient ${removal.role === 'contact' ? 'le contact' : 'le nom de la boutique'} : il` }} ne peut pas en être effacé.<template v-if="!removal.on"> Il sera absent de la prochaine version. Cette version-ci ne peut plus être téléchargée tant qu’il n’est pas remis : générez une nouvelle version, ou remettez-le depuis « Boutique ».</template><template v-else> Si vous le retirez, cette version-ci ne pourra plus être téléchargée : il faudra générer une nouvelle version.</template></p>
              <button v-if="removal.on" type="button" class="remove" @click="removeFromPoster">Ne plus le mettre dans la prochaine version</button>
              <button v-else type="button" class="text-button" @click="go('boutique')">Ouvrir « Boutique »</button>
            </template>
          </div>
          <div v-if="job" class="job-state" role="status"><strong>{{ { plan:'Préparation de la composition…', look:'Description du style par Claude…', scene:'Création de votre affiche…', refine:'Ajustement de la scène…', text_patch:'Préparation de l’ajustement du texte…', text_texture:'Création de la matière du texte…', render:'Préparation de l’aperçu final…' }[job.kind] }}</strong><p>{{ drawingTexts ? 'Le titre et le prix sont en train d’être dessinés : ils se modifient à nouveau dès la fin.' : 'Le titre et le prix restent modifiables. Les choix de style et ce que l’IA dessine reviennent à la fin de la tâche.' }}</p><button v-if="job.status === 'queued'" class="quiet" @click="perform(cancelJob)">Annuler la demande</button></div>
          <div v-if="proposal?.status === 'pending' || effect?.status === 'proposed'" class="polish-preview"><strong>Ajustement à vérifier</strong><label class="check"><input v-model="previewPolish" type="checkbox" />Voir la proposition sur l’affiche</label><button v-if="!stepping" type="button" class="text-button" @click="selected = (effect?.status === 'proposed' ? effect : proposal).layer_id; go('reglages')">Ouvrir l’ajustement</button></div>
          <div v-if="saveState === 'failed' || saveState === 'conflict'" class="save-recovery"><button v-if="saveState === 'failed'" @click="perform(flush)">Réessayer l’enregistrement</button><template v-else><button @click="perform(conflictCopy)">Conserver mes modifications dans une copie</button><button class="quiet" @click="askDiscard">Abandonner mes modifications et recharger</button></template></div>
          <ul v-if="issues.length" class="issues"><li v-for="issue in issues" :key="issue.id" :class="{ blocking: issue.blocking }"><button class="text-button" @click="pick(issue.layer_id)">{{ issue.message }}</button></li></ul>
          <p v-if="currentVisual" class="help">{{ currentVisual.status === 'approved' ? 'Fidélité du produit approuvée.' : currentVisual.status === 'rejected' ? 'Cette version a été refusée. Choisissez une autre version ou générez-en une nouvelle.' : 'Comparez le produit avec la photo originale avant d’approuver sa fidélité.' }}</p>
        </section>
        <aside class="versions" aria-labelledby="titre-versions" :inert="peeking">
          <h2 id="titre-versions">Versions <span class="count">{{ visuals.length }} sur 12</span></h2>
          <p v-if="!visuals.length" class="help">Chaque génération crée une version. Vous choisirez celle à exporter.</p>
          <article v-for="visual in visuals" :key="visual.id" class="version" :class="{ selected: currentVisual?.id === visual.id }">
            <button type="button" class="thumb" :aria-pressed="currentVisual?.id === visual.id" :aria-label="`Choisir cette version (${ { approved:'approuvée', pending_review:'à vérifier', rejected:'refusée' }[visual.status] })`" @click="chooseVisual(visual)"><img :src="visual.image_url" width="104" height="130" loading="lazy" alt="Version générée de la scène" /></button>
            <span class="state" :class="visual.status">{{ { approved:'Approuvée', pending_review:'À vérifier', rejected:'Refusée' }[visual.status] }}</span>
            <strong v-if="currentVisual?.id === visual.id" class="pick">Choisie pour l’export</strong>
            <button class="text-button" @click="review = visual; resetChecks()">Comparer</button>
          </article>
          <button v-if="visuals.length && visuals.length < 12" type="button" class="version new" :disabled="busy || !!job" @click="askScene"><span class="add"><Icon n="plus" /></span>Nouvelle version<small>Même produit, autre essai</small></button>
          <p v-else-if="visuals.length" class="help">Douze versions au plus par affiche. Pour d’autres essais, dupliquez l’affiche depuis « Mes affiches ».</p>
        </aside>
      </div>
    </div>
    <div v-if="paid" v-modal class="confirm-sheet" role="dialog" aria-modal="true" aria-labelledby="titre-confirmation" @keydown.esc="paid = null"><div class="confirm">
      <h2 id="titre-confirmation">{{ paid.title }}</h2><p>{{ paid.text }}</p><p v-if="paid.cost" class="cost">{{ paid.cost }}</p>
      <label v-if="smallPhoto && paid.run === createScene" class="check"><input v-model="lowResAccepted" type="checkbox" />La photo du produit est petite : l’affiche peut manquer de netteté. J’accepte une qualité réduite.</label>
      <div class="row"><button class="primary" :disabled="busy || (smallPhoto && paid.run === createScene && !lowResAccepted)" @click="confirmPaid">{{ paid.label }}</button><button class="secondary" data-focus @click="paid = null">Annuler</button></div>
    </div></div>
    <section v-if="finalPreview" v-modal class="review-panel final-preview" role="dialog" aria-modal="true" aria-labelledby="final-title" :inert="!!paid" @keydown.esc="finalPreview = null">
      <div class="section-heading"><div><h2 id="final-title">{{ confirmedDownload ? 'Votre affiche est prête' : 'Dernière vérification avant le téléchargement' }}</h2><p class="lede">{{ confirmedDownload ? 'Le fichier confirmé ne changera plus, même si vous modifiez l’affiche ensuite.' : 'Ce fichier est celui qui sera téléchargé après votre confirmation.' }}</p></div><button class="ghost" @click="finalPreview = null"><Icon n="close" />Fermer</button></div>
      <div class="final-grid">
        <div class="shot"><a :href="finalPreview.preview_url" target="_blank" rel="noopener"><img :src="finalPreview.preview_url" width="1080" height="1350" alt="Aperçu final du fichier à télécharger" @load="previewLoaded = true" @error="error = 'Le fichier d’aperçu ne peut pas être chargé.'; previewLoaded = false" /></a><p class="help">Ouvrir l’image pour vérifier les détails à pleine taille.</p></div>
        <div>
          <p v-if="confirmedDownload" class="done" role="status"><Icon n="check" />Affiche confirmée. Elle reste disponible dans « Mes affiches ».</p>
          <dl class="facts"><div><dt>Format</dt><dd>1080 × 1350 px</dd></div><div><dt>Fichier</dt><dd>PNG</dd></div><div><dt>Prix affiché</dt><dd>{{ doc ? doc.offer.price_ar.toLocaleString('fr-FR') : '' }} Ar</dd></div></dl>
          <template v-if="!confirmedDownload">
          <div class="group"><h3><Icon n="check" />À vérifier sur ce fichier</h3><ul class="points"><li v-for="(label, point) in finalPoints" :key="point">{{ label }}</li><li v-if="currentVisual?.logo_disc">Le logo recouvre bien son disque</li><li v-for="warning in finalPreview.warnings" :key="warning.id" class="warn">{{ warning.message }}</li></ul></div>
          <div class="actions"><span class="count">Un seul accord pour tous les points ci-dessus.</span><button class="primary" :disabled="busy || !previewLoaded" @click="perform(confirmFinal)"><Icon n="check" />Tout est conforme, confirmer</button><p v-if="!previewLoaded" class="why" role="status">La confirmation s’active dès que l’aperçu est affiché.</p></div>
          </template>
          <div v-if="confirmedDownload" class="after"><a :href="confirmedDownload" class="download-button" download><Icon n="download" />Télécharger le PNG confirmé</a><button class="secondary" @click="leave('')"><Icon n="plus" />Nouvelle affiche</button><button class="secondary" @click="changePriceLater">Changer le prix</button><p class="help">Changer le prix crée une nouvelle version, car le prix est dessiné dans l’image.</p></div>
        </div>
      </div>
    </section>
    <section v-if="opened" v-modal class="review-panel look-panel" role="dialog" aria-modal="true" aria-labelledby="titre-style-ouvert" :inert="!!paid" @keydown.esc="openedId = null">
      <div class="section-heading"><div><h2 id="titre-style-ouvert" translate="no">{{ opened.name }}</h2><p class="lede">{{ opened.own ? 'Style créé depuis une de vos affiches modèles.' : 'Style fourni : il ne peut pas être renommé ni retiré.' }}</p></div><button class="ghost" @click="openedId = null"><Icon n="close" />Fermer</button></div>
      <div class="final-grid">
        <div class="shot"><img :src="opened.image" alt="Affiche modèle de ce style" /></div>
        <div class="stack">
          <div class="group"><h3><Icon n="palette" />Description</h3><ul class="points"><li>Ambiance<small>{{ opened.direction }}</small></li><template v-if="opened.brief"><li>Surface<small>{{ opened.brief.surface_fr }}</small></li><li>Couleurs<small class="swatches"><span v-for="colour in opened.brief.palette" :key="colour"><i :style="{ background: colour }" />{{ colour }}</span></small></li><li>Titre et prix<small>{{ opened.brief.alignment === 'left' ? 'Alignés à gauche' : 'Centrés' }}</small></li></template></ul></div>
          <div v-if="opened.own" class="group"><label>Nom du style<input v-model="renameText" name="look-name" autocomplete="off" maxlength="40" :aria-invalid="!!renameError || undefined" aria-describedby="erreur-nom-style" @keydown.enter="perform(renameLook)" /></label><p v-if="renameError" id="erreur-nom-style" class="why" role="alert">{{ renameError }}</p><button :disabled="busy || !renameText.trim() || renameText.trim() === opened.name" @click="perform(renameLook)">Renommer</button></div>
          <div class="after"><button class="primary" @click="useLook(opened.id)"><Icon n="plus" />Créer une affiche avec ce style</button><button v-if="opened.own" :disabled="busy" @click="askRemoveLook">Retirer ce style</button></div>
        </div>
      </div>
    </section>
    <section v-if="review" v-modal class="review-panel" role="dialog" aria-modal="true" aria-labelledby="review-title" :inert="!!paid" @keydown.esc="review = null">
      <div class="section-heading"><div><h2 id="review-title">Vérifier la fidélité du produit</h2><p class="lede">Regardez les deux images côte à côte et relisez chaque texte que l’IA a dessiné. Au moindre écart, signalez un problème.</p></div><button class="ghost" @click="review = null"><Icon n="close" />Fermer</button></div>
      <div class="comparison" :class="{ zoomed }"><figure><a v-for="(url, index) in review.original_urls" :key="url" :href="url" target="_blank" rel="noopener" @click.exact.prevent="zoomed = !zoomed"><img :src="url" width="540" height="380" :alt="`Photo originale ${index + 1} à comparer`" /></a><figcaption>Votre photo · appuyez pour {{ zoomed ? 'réduire' : 'agrandir' }}</figcaption></figure><figure><a :href="review.image_url" target="_blank" rel="noopener" @click.exact.prevent="zoomed = !zoomed"><img :src="review.image_url" width="540" height="380" alt="Version générée à vérifier" /></a><figcaption>Version générée · appuyez pour {{ zoomed ? 'réduire' : 'agrandir' }}</figcaption></figure></div>
      <template v-if="review.status === 'pending_review'">
        <div class="review-checks groups">
          <div class="group"><h3><Icon n="box" />Le produit</h3><p class="help">Comparé à votre photo.</p><ul class="points"><li v-for="check in (['colour', 'shape', 'hardware', 'markings'] as const)" :key="check">{{ checkNames[check] }}</li></ul></div>
          <div v-if="textChecks.length" class="group"><h3><Icon n="text" />Les textes dessinés</h3><p class="help">Ce que vous avez saisi, à retrouver lettre pour lettre.</p><ul class="points"><li v-for="item in textChecks" :key="item.key">{{ item.label }}<small translate="no">{{ item.value }}</small></li><li>Aucun autre texte que ceux ci-dessus</li></ul></div>
          <div class="group"><h3><Icon n="image" />L’image</h3><p class="help">L’ensemble de la scène.</p><ul class="points"><li v-for="check in (['extras_text', 'integration'] as const)" :key="check">{{ checkNames[check] }}</li><li v-if="review.logo_disc">Un disque blanc vide est prévu pour le logo : rien ne doit être dessiné dedans</li><li v-if="review.logo_disc === null" class="warn">Le disque du logo n’a pas été trouvé dans l’image : le logo a été retiré de cette affiche. Cochez « Logo » pour le placer vous-même, ou générez une nouvelle version.</li></ul></div>
        </div>
        <div class="actions"><span class="count">Un seul accord pour tous les points ci-dessus.</span><button class="secondary" :disabled="busy" @click="rejecting = !rejecting">Signaler un problème</button><button class="primary" :disabled="busy" @click="perform(() => decide('approve'))"><Icon n="check" />Tout est conforme, approuver</button></div>
        <div v-if="rejecting" class="group"><label>Ce qui doit être corrigé<textarea v-model="rejection" name="rejection" autocomplete="off" rows="2" maxlength="500" /></label><button class="secondary" :disabled="busy || !rejection.trim()" @click="perform(() => decide('reject'))">Refuser cette version</button><p v-if="!rejection.trim()" class="why" role="status">Décrivez d’abord ce qui doit être corrigé.</p></div>
      </template>
      <p v-else>{{ review.status === 'approved' ? 'La fidélité de cette version a été approuvée.' : 'Cette version a été refusée.' }}</p>
    </section>
  </main>
</template>
