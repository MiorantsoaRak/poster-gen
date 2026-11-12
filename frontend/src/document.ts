export type Format = 'feed' | 'square' | 'story'
export const FORMATS: Record<Format, [number, number]> = { feed: [1080, 1350], square: [1080, 1080], story: [1080, 1920] }
export type TextRole = 'title' | 'price' | 'shop_name' | 'contact'
export type FontId = 'noto-sans' | 'noto-serif' | 'montserrat-black-italic'
export interface Box { x: number; y: number; width: number; height: number }
export interface BaseLayer extends Box { id: string; visible: boolean; z: number }
export interface TextLayer extends BaseLayer {
  kind: 'text'; role: TextRole; font_id: FontId; font_size: number; weight: 400 | 700 | 900
  fill: string; align: 'left' | 'center' | 'right'; line_height: number
  outline: { colour: string; width: number } | null
  shadow: { colour: string; blur: number; offset_x: number; offset_y: number; opacity: number } | null
  texture_effect_id: string | null
  price_badge?: { fill: string; border_start: string; border_end: string } | null
  icon?: 'phone' | null
}
export interface ImageLayer extends BaseLayer { kind: 'logo' | 'product_cutout'; role: 'logo' | 'product'; asset: string; keep_aspect: true }
export type Layer = TextLayer | ImageLayer
export interface Crop { x: number; y: number; w: number; h: number }
export interface Layout { scene: { visual_id: string | null; crop: Crop | null }; layers: Layer[] }
export interface PosterDocument {
  schema_version: 1; input_id: string
  offer: { title: string; price_ar: number; currency: 'MGA' }
  brand_snapshot: { profile_revision: number; name: string | null; contact: string | null; logo_asset: string | null }
  include: { logo: boolean; shop_name: boolean; contact: boolean }
  primary_format: Format; formats: Partial<Record<Format, Layout>>
}
export interface Creation { id: string; revision: number; status: 'active' | 'abandoned'; parent_creation_id: string | null; document: PosterDocument }
export interface Visual { id: string; status: 'pending_review' | 'approved' | 'rejected'; image_url: string; original_urls: string[]; style_reference_asset?: string | null; headline?: { title: string; brand?: string | null; shop_name?: string; contact?: string; signature_align?: 'left' | 'centre' | 'right'; price_ar?: number } | null; size: string; base_visual_id: string | null }

// Documents are JSON values; this also accepts Vue proxies, unlike structuredClone.
export const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value))

export function parsePrice(value: string): number {
  if (!/^(?:[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+)$/.test(value)) throw new Error('Saisissez un montant entier en ariary.')
  const result = Number(value.replace(/[ \u00a0\u202f]/g, ''))
  if (!Number.isSafeInteger(result) || result < 0) throw new Error('Montant trop élevé ou invalide.')
  return result
}

export function formatPrice(value: number): string {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Prix invalide.')
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, '\u202f') + ' Ar'
}

export function layerText(doc: PosterDocument, role: TextRole): string {
  if (role === 'title') return doc.offer.title
  if (role === 'price') return formatPrice(doc.offer.price_ar)
  return (role === 'shop_name' ? doc.brand_snapshot.name : doc.brand_snapshot.contact) ?? ''
}

export function setIdentity(doc: PosterDocument, role: keyof PosterDocument['include'], enabled: boolean) {
  const source = role === 'logo' ? doc.brand_snapshot.logo_asset : role === 'shop_name' ? doc.brand_snapshot.name : doc.brand_snapshot.contact
  if (enabled && !source) throw new Error('Complétez cette information dans les détails de la boutique.')
  doc.include[role] = enabled
  for (const [format, layout] of Object.entries(doc.formats) as [Format, Layout][]) {
    const existing = layout.layers.find(layer => layer.role === role)
    if (existing) { existing.visible = enabled; continue }
    if (!enabled) continue
    const [width, height] = FORMATS[format]
    const base = { id: crypto.randomUUID(), x: 64, y: height - (role === 'contact' ? 150 : 230), width: width - 128, height: 100, z: layout.layers.length, visible: true }
    if (role === 'logo') layout.layers.push({ ...base, kind: 'logo', role: 'logo', x: width - 180, width: 116, height: 116, asset: source!, keep_aspect: true })
    else layout.layers.push({ ...base, kind: 'text', role, font_id: 'noto-sans', font_size: role === 'shop_name' ? 36 : 24,
      weight: 400, fill: '#FFFFFF', align: 'left', line_height: 1.2, outline: null, shadow: null, texture_effect_id: null })
  }
}

export function fitCrop(imageWidth: number, imageHeight: number, format: Format): Crop {
  const [w, h] = FORMATS[format]
  const scale = Math.min(imageWidth / w, imageHeight / h)
  return { x: (imageWidth - w * scale) / 2, y: (imageHeight - h * scale) / 2, w: w * scale, h: h * scale }
}

export class History {
  past: PosterDocument[] = []
  future: PosterDocument[] = []
  private lastKey = ''
  private lastAt = 0
  record(before: PosterDocument, mergeKey = '') {
    const now = Date.now()
    if (!mergeKey || mergeKey !== this.lastKey || now - this.lastAt > 750) {
      this.past.push(copy(before)); if (this.past.length > 100) this.past.shift()
    }
    this.lastKey = mergeKey; this.lastAt = now; this.future = []
  }
  undo(current: PosterDocument) {
    const previous = this.past.pop()
    if (!previous) return null
    this.future.push(copy(current)); this.lastKey = ''; return previous
  }
  redo(current: PosterDocument) {
    const next = this.future.pop()
    if (!next) return null
    this.past.push(copy(current)); this.lastKey = ''; return next
  }
}
