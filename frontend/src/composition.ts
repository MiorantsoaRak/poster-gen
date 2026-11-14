import { FORMATS, type Format, type PosterDocument, type Visual } from './document'

export function brandInTitle(brand: string, title: string): boolean {
  const words = (value: string) => value.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []
  const needle = words(brand), haystack = words(title)
  return !!needle.length && haystack.some((_, i) => needle.every((word, n) => haystack[i + n] === word))
}

export function placeLogo(document: PosterDocument, side: 'left' | 'right') {
  for (const [format, layout] of Object.entries(document.formats)) {
    const logo = layout.layers.find(layer => layer.kind === 'logo')
    if (logo?.kind !== 'logo') continue
    const [width, height] = FORMATS[format as Format], size = width * .12
    Object.assign(logo, { x: side === 'left' ? width * .05 : width * .95 - size, y: height * (format === 'story' ? .13 : .05), width: size, height: size })
    delete logo.shape
  }
}

export function logoPlacementStale(document: PosterDocument, format: Format, visual?: Visual): boolean {
  if (!visual) return false
  const layout = document.formats[format]!, logo = layout.layers.find(layer => layer.kind === 'logo' && layer.visible)
  if (logo?.kind !== 'logo') return false
  const reserved = visual.logo_box
  if (!reserved && (logo.shape === 'circle' || logo.y >= FORMATS[format][1] / 2)) return false
  if (!reserved || logo.shape === 'circle' || (['x', 'y', 'width', 'height'] as const).some(key => Math.abs(logo[key] - reserved[key]) > 2)) return true
  const [width, height] = visual.size.split('x').map(Number), crop = layout.scene.crop
  return !!crop && [crop.x, crop.y, crop.w - width!, crop.h - height!].some(n => Math.abs(n) > 2)
}
