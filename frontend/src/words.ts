// The words typed before a poster's first version (brand, subtitle, accent word, its colour, the boxes for the next
// version) are kept in the browser, one entry per poster (ADR-083, T-KEEP-WORDS). Nothing else is stored there.
export const WORDS_PREFIX = 'affiche.words.', WORDS_KEPT = 30
export type KeptWords = { on: boolean; price: boolean; contact: boolean; brand_text: boolean; brand: string; subtitle: string; accent_word: string; accent_colour: string }

/** What a stored entry may give back for a poster with this title. The storage is never trusted: a field of the wrong
 *  type or size is left out, and so is an accent word that the title no longer contains (the server would refuse it). */
export function readWords(raw: string | null, title: string): Partial<KeptWords> {
  let saved: any
  try { saved = JSON.parse(raw ?? 'null') } catch { return {} }
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {}
  const words: Partial<KeptWords> = {}
  for (const key of ['on', 'price', 'contact', 'brand_text'] as const) if (typeof saved[key] === 'boolean') words[key] = saved[key]
  // 60 is what the two fields accept (maxlength) and what the image model can draw.
  for (const key of ['brand', 'subtitle'] as const) if (typeof saved[key] === 'string' && saved[key].length <= 60) words[key] = saved[key]
  if (typeof saved.accent_word === 'string' && (!saved.accent_word.trim() || title.includes(saved.accent_word.trim()))) words.accent_word = saved.accent_word.trim()
  if (typeof saved.accent_colour === 'string' && /^#[0-9A-Fa-f]{6}$/.test(saved.accent_colour)) words.accent_colour = saved.accent_colour.toLowerCase()
  return words
}

/** The keys to remove so that only the `keep` most recently written entries stay; an entry without a readable date goes first. */
export function staleWords(entries: [key: string, raw: string | null][], keep = WORDS_KEPT): string[] {
  const at = (raw: string | null) => { try { const value = JSON.parse(raw ?? 'null')?.at; return Number.isFinite(value) ? value as number : -Infinity } catch { return -Infinity } }
  return entries.map(([key, raw]) => ({ key, at: at(raw) })).sort((a, b) => b.at - a.at).slice(keep).map(entry => entry.key)
}
