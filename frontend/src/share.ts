// « Partager » (docs/project/designs/share-poster.md).

/** The final panel's one rule (D-SHARE-001): a render is presented as the poster's current file (« Votre affiche est prête »,
 *  the live « Prix affiché », its confirmation as current) only when no edit waits to be saved or is being saved, no poster
 *  read has shown a revision ahead of the one this tab saved (another tab saved), and it was made from the saved revision,
 *  or it is the confirmation a poster read named at that same revision (the server checked its image against that
 *  revision: an undo back to the same image). Otherwise the image may show another price than the editor: it is an
 *  earlier version, confirmed or not. `read`: the last poster read, its revision and the render it named (or null). */
export function presentedAsCurrent(render: { id: string; source_revision: number }, saved: number, dirty: boolean,
                                   read: { revision: number; render_id: string | null } | null) {
  if (dirty || (read && read.revision > saved)) return false
  return render.source_revision === saved || (read?.render_id === render.id && read.revision === saved)
}

/** The caption's one rule (D-SHARE-003), in this order, for the field, the reader and the copy: a control character other
 *  than line feed and tab (C0 with NUL, DEL, C1) first, so that such a text is never blank and never erases the stored
 *  caption; then more than 2 000 code points (not UTF-16 units: an emoji counts once; no `maxlength`, a paste is never
 *  cut); then blank. null: a text to keep and copy. */
export const CAPTION_MAX = 2000
export function captionFault(text: string): 'bad_character' | 'too_long' | 'blank' | null {
  if (/[\x00-\x08\x0B-\x1F\x7F-\x9F]/.test(text)) return 'bad_character'
  let points = 0
  for (const _ of text) if (++points > CAPTION_MAX) return 'too_long'  // stops at 2 001: a huge paste is not spread
  return text.trim() === '' ? 'blank' : null
}
/** What a stored caption gives the field: the storage is never trusted, and anything the rule would not keep opens empty. */
export const readCaption = (raw: unknown) => typeof raw === 'string' && captionFault(raw) === null ? raw : ''
