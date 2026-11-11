import manifest from './font-manifest.json'
import type { FontId } from './document'

export { manifest as fontManifest }
let loaded: Promise<void> | null = null

export function fontEntry(id: FontId, weight: number) {
  const entry = manifest.fonts.find(font => font.id === id && font.weight === weight)
  if (!entry) throw new Error('Police non prise en charge.')
  return entry
}

export function unsupportedGlyphs(text: string, id: FontId, weight: number): string[] {
  const ranges = fontEntry(id, weight).ranges
  return [...new Set([...text].filter(char => !['\n', '\r'].includes(char)
    && !ranges.some(([start, end]) => char.codePointAt(0)! >= start && char.codePointAt(0)! <= end)))]
}

export async function loadFonts(injected?: Record<string, string>): Promise<void> {
  if (loaded) return loaded
  loaded = Promise.all(manifest.fonts.map(async entry => {
    const response = await fetch(injected?.[entry.file] ?? `/fonts/${entry.file}`)
    if (!response.ok) throw new Error(`Police introuvable : ${entry.file}`)
    const bytes = await response.arrayBuffer()
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(n => n.toString(16).padStart(2, '0')).join('')
    if (digest !== entry.sha256) throw new Error(`Police endommagée : ${entry.file}`)
    const face = new FontFace(entry.family, bytes, { weight: String(entry.weight), style: entry.style })
    await face.load(); document.fonts.add(face)
  })).then(async () => { await document.fonts.ready })
  try { await loaded }
  catch (error) { loaded = null; throw error }
}
