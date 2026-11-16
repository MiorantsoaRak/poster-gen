import type { PosterDocument } from '../src/document'

export function document(): PosterDocument {
  return { schema_version: 1, input_id: 'input', offer: { title: 'Soundcore R50i', price_ar: 90000, currency: 'MGA' },
    brand_snapshot: { profile_revision: 1, name: 'Original Phone Mada', contact: '034 93 028 00', logo_asset: 'logo' },
    include: { logo: false, shop_name: false, contact: false }, primary_format: 'feed',
    formats: { feed: { scene: { visual_id: null, crop: null }, layers: [] } } }
}

/** A browser storage in memory; `refuse` makes setItem throw for the keys it names, as a full or private one does. */
export function memory(entries: Record<string, string> = {}, refuse: (key: string) => boolean = () => false) {
  const map = new Map(Object.entries(entries))
  return { map, get length() { return map.size }, key: (index: number) => [...map.keys()][index] ?? null, getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => { if (refuse(key)) throw new DOMException('full', 'QuotaExceededError'); map.set(key, String(value)) },
    removeItem: (key: string) => { map.delete(key) }, clear: () => map.clear() } as Storage & { map: Map<string, string> }
}
