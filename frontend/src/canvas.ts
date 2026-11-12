import Konva from 'konva'
import { FORMATS, layerText, type Format, type Layer, type PosterDocument, type TextLayer } from './document'
import { fontEntry, unsupportedGlyphs } from './fonts'

export interface LayoutIssue { id: string; layer_id: string; blocking: boolean; message: string }

export function textConfig(doc: PosterDocument, layer: TextLayer) {
  const font = fontEntry(layer.font_id, layer.weight)
  // Montserrat's upstream face has NBSP but no narrow NBSP; price grouping uses its real space glyph.
  const text = layer.role === 'price' && (layer.price_badge || layer.font_id === 'montserrat-black-italic')
    ? layerText(doc, layer.role).replaceAll('\u202f', '\u00a0') : layerText(doc, layer.role)
  return { text, width: layer.width, fontFamily: font.family,
    fontSize: layer.font_size, fontStyle: `${font.style} ${layer.weight}`, fill: layer.fill, align: layer.align, lineHeight: layer.line_height,
    wrap: layer.role === 'price' ? 'none' : 'word', ellipsis: false,
    stroke: layer.outline?.colour, strokeWidth: layer.outline?.width ?? 0,
    shadowColor: layer.shadow?.colour, shadowBlur: layer.shadow?.blur ?? 0, shadowOpacity: layer.shadow?.opacity ?? 0,
    shadowOffsetX: layer.shadow?.offset_x ?? 0, shadowOffsetY: layer.shadow?.offset_y ?? 0 }
}

export function badgeConfig(layer: TextLayer) {
  return { x: 2, y: 2, width: layer.width - 4, height: layer.height - 4, cornerRadius: Math.max(0, (layer.height - 4) / 2),
    fill: layer.price_badge!.fill, strokeWidth: 3, strokeLinearGradientStartPoint: { x: 0, y: 0 },
    strokeLinearGradientEndPoint: { x: layer.width, y: 0 },
    strokeLinearGradientColorStops: [0, layer.price_badge!.border_start, 1, layer.price_badge!.border_end] }
}

// Material Symbols "call" (Apache-2.0), in a 24-unit box whose ink spans units 3 to 21. A path, so no font needs it.
const PHONE = 'M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z'

// A contact with an icon is one line: handset as high as the digits, a gap of half that, then the text.
export function iconLine(doc: PosterDocument, layer: TextLayer) {
  const config = { ...textConfig(doc, layer), width: undefined, align: 'left', wrap: 'none' }
  const probe = new Konva.Text(config)
  const digit = probe.measureSize('0'), em = probe.measureSize('M'), lineHeight = layer.font_size * layer.line_height
  const size = digit.actualBoundingBoxAscent, gap = size / 2, total = size + gap + probe.width()
  const baseline = (em.fontBoundingBoxAscent - em.fontBoundingBoxDescent + lineHeight) / 2
  const start = layer.align === 'left' ? 0 : layer.align === 'right' ? layer.width - total : (layer.width - total) / 2
  probe.destroy()
  return { total, text: { ...config, x: start + size + gap, y: 0 },
    icon: { data: PHONE, fill: layer.fill, x: start - 3 * size / 18, y: baseline - size - 3 * size / 18, scaleX: size / 18, scaleY: size / 18 } }
}

export function textRuns(doc: PosterDocument, layer: TextLayer): Konva.TextConfig[] {
  if (layer.icon) return [iconLine(doc, layer).text]
  const config = textConfig(doc, layer)
  if (!layer.price_badge) return [config]
  const amount = { ...config, text: config.text.slice(0, -3), width: undefined, align: 'left' }
  const currency = { ...config, text: 'AR', width: undefined, align: 'left', fontSize: layer.font_size * .48,
    fontFamily: fontEntry('noto-sans', 400).family, fontStyle: '400' }
  const probes = [new Konva.Text(amount), new Konva.Text(currency)]
  const gap = layer.font_size * .2, padding = layer.font_size * .4
  const total = probes[0].width() + gap + probes[1].width()
  const start = layer.align === 'left' ? padding : layer.align === 'right' ? layer.width - padding - total : (layer.width - total) / 2
  const runs = [amount, currency].map((run, index) => ({ ...run,
    x: start + (index ? probes[0].width() + gap : 0), y: (layer.height - probes[index].height()) / 2 }))
  probes.forEach(probe => probe.destroy())
  return runs
}

export function inspectLayout(doc: PosterDocument, format: Format): LayoutIssue[] {
  const issues: LayoutIssue[] = [], [width, height] = FORMATS[format]
  const layers = doc.formats[format]!.layers.filter(layer => layer.visible)
  for (const layer of layers) {
    const add = (code: string, message: string, blocking = true) => issues.push({ id: `${code}:${layer.id}`, layer_id: layer.id, blocking, message })
    if (layer.kind === 'text') {
      const text = textConfig(doc, layer).text
      if (unsupportedGlyphs(text, layer.font_id, layer.weight).length) add('glyph', 'Cette police ne contient pas tous les caractères du texte.')
      const probes = textRuns(doc, layer).map(config => new Konva.Text(config))
      if (layer.price_badge && unsupportedGlyphs('AR', 'noto-sans', 400).length) add('glyph', 'La police du prix est indisponible.')
      const group = new Konva.Group()
      if (layer.price_badge) group.add(new Konva.Rect(badgeConfig(layer)))
      group.add(...probes)
      // Italic ink can pass its advance box; measure it before deciding whether the canvas clips it.
      for (const probe of probes.filter(probe => probe.fontStyle().includes('italic'))) {
        const em = probe.measureSize('M'), lineHeight = probe.fontSize() * probe.lineHeight()
        const baseline = (em.fontBoundingBoxAscent - em.fontBoundingBoxDescent + lineHeight) / 2
        probe.textArr.forEach((line, index) => {
          const ink = probe.measureSize(line.text)
          const offset = probe.align() === 'right' ? probe.width() - line.width : probe.align() === 'center' ? (probe.width() - line.width) / 2 : 0
          group.add(new Konva.Rect({ x: probe.x() + offset - ink.actualBoundingBoxLeft,
            y: probe.y() + index * lineHeight + baseline - ink.actualBoundingBoxAscent,
            width: ink.actualBoundingBoxLeft + ink.actualBoundingBoxRight,
            height: ink.actualBoundingBoxAscent + ink.actualBoundingBoxDescent,
            stroke: probe.stroke(), strokeWidth: probe.strokeWidth(), shadowColor: probe.shadowColor(),
            shadowBlur: probe.shadowBlur(), shadowOpacity: probe.shadowOpacity(), shadowOffset: probe.shadowOffset() }))
        })
      }
      // Measure without a height limit so draft text stays visible and overflow cannot hide letters.
      const overflow = layer.icon
        // One line that never wraps: without this check a long contact would be cut at the layer's edge.
        ? iconLine(doc, layer).total > layer.width + .5 || probes[0].height() > layer.height + .5
        : layer.price_badge
        ? probes.some(probe => probe.x() < layer.font_size * .3 || probe.x() + probe.width() > layer.width - layer.font_size * .3
          || probe.y() < 6 || probe.y() + probe.height() > layer.height - 6)
        : probes[0].height() > layer.height + .5 || probes[0].measureSize(layer.role === 'price' ? text : '').width > layer.width + .5
      if (overflow) {
        add('text_fit', 'Le texte dépasse son cadre. Agrandissez le cadre ou réduisez la police.')
      }
      const rect = group.getClientRect()
      if (layer.x + rect.x < 0 || layer.y + rect.y < 0 || layer.x + rect.x + rect.width > width + .5
          || layer.y + rect.y + rect.height > height + .5) add('clipped', 'Le texte ou son effet dépasse le bord de l’affiche.')
      group.destroy()
    } else if (layer.x < 0 || layer.y < 0 || layer.x + layer.width > width || layer.y + layer.height > height) {
      add('clipped', 'L’image dépasse le bord de l’affiche.')
    }
  }
  for (let i = 0; i < layers.length; i++) for (const other of layers.slice(i + 1)) {
    const layer = layers[i]
    if (overlap(layer, other)) issues.push({ id: `overlap:${layer.id}:${other.id}`, layer_id: layer.id, blocking: false,
      message: 'Deux éléments se superposent. Vérifiez leur lisibilité.' })
  }
  return issues
}

function overlap(a: Layer, b: Layer) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
}
