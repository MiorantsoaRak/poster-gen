export type Palette = [string, string, string]
export const validColour = (value: unknown): value is string => typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value)
const hex = (rgb: number[]) => '#' + rgb.map(n => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0')).join('').toUpperCase()

export function colourPalette(colour: string): Palette {
  if (!validColour(colour)) throw new Error('Choisissez une couleur valide.')
  const rgb = [1, 3, 5].map(i => parseInt(colour.slice(i, i + 2), 16))
  return [hex(rgb.map(n => 255 * .96 + n * .04)), hex(rgb.map(n => 255 * .8 + n * .2)), colour.toUpperCase()]
}

export function photoPalette(pixels: Uint8ClampedArray, width: number, height: number): Palette {
  if (width < 1 || height < 1 || pixels.length !== width * height * 4) throw new Error('Photo illisible pour proposer les couleurs.')
  const points: { rgb: number[]; edge: boolean }[] = []
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const at = (y * width + x) * 4
    if (pixels[at + 3]! < 128) continue
    points.push({ rgb: Array.from(pixels.slice(at, at + 3)), edge: x < width * .1 || x >= width * .9 || y < height * .1 || y >= height * .9 })
  }
  if (!points.length) throw new Error('La photo est transparente : choisissez une couleur manuellement.')
  const dominant = (rgb: number[][]) => {
    const bins = new Map<string, { count: number; sum: number[] }>()
    for (const p of rgb) {
      const key = p.map(n => Math.floor(n / 32)).join(',')
      const bin = bins.get(key) ?? { count: 0, sum: [0, 0, 0] }
      bin.count++; bin.sum = bin.sum.map((n, i) => n + p[i]!); bins.set(key, bin)
    }
    const best = [...bins.values()].sort((a, b) => b.count - a.count)[0]!
    return best.sum.map(n => n / best.count)
  }
  const edges = points.filter(p => p.edge).map(p => p.rgb)
  const background = edges.length ? dominant(edges) : null
  const foreground = background ? points.filter(p => Math.max(...p.rgb.map((n, i) => Math.abs(n - background[i]!))) > 40) : points
  // shortcut: edge-colour rejection proposes a palette, not object segmentation; busy photos need the visible manual override.
  const rgb = dominant((foreground.length >= points.length * .05 ? foreground : points).map(p => p.rgb))
  if (Math.max(...rgb) - Math.min(...rgb) < 25) {
    const gray = Math.min(180, Math.round(rgb.reduce((a, b) => a + b) / 3))
    return colourPalette(hex([gray, gray, gray]))
  }
  return colourPalette(hex(rgb))
}

export async function samplePhoto(url: string, signal: AbortSignal): Promise<Palette> {
  const response = await fetch(url, { signal, credentials: 'same-origin' })
  if (!response.ok) throw new Error('La photo ne peut pas être chargée. Réessayez ou choisissez une couleur.')
  const bitmap = await createImageBitmap(await response.blob())
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 64; canvas.height = Math.max(1, Math.round(64 * bitmap.height / bitmap.width))
    // Bound portrait and landscape alike, even for a very thin source image.
    if (canvas.height > 64) { canvas.width = Math.max(1, Math.round(64 * bitmap.width / bitmap.height)); canvas.height = 64 }
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) throw new Error('Les couleurs ne peuvent pas être analysées ici. Choisissez une couleur.')
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    return photoPalette(ctx.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height)
  } finally { bitmap.close() }
}
