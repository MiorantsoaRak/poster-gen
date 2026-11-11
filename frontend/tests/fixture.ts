import type { PosterDocument } from '../src/document'

export function document(): PosterDocument {
  return { schema_version: 1, input_id: 'input', offer: { title: 'Soundcore R50i', price_ar: 90000, currency: 'MGA' },
    brand_snapshot: { profile_revision: 1, name: 'Original Phone Mada', contact: '034 93 028 00', logo_asset: 'logo' },
    include: { logo: false, shop_name: false, contact: false }, primary_format: 'feed',
    formats: { feed: { scene: { visual_id: null, crop: null }, layers: [] } } }
}
