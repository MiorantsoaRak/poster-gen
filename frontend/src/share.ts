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

/** Whether this browser can hand an image file to another application (D-SHARE-004): by capability, never by user agent.
 *  Both functions must exist and `canShare` must accept a JPEG file (`file`, or a one-byte stand-in); a throw is a no. */
export function canShareFiles(nav: Pick<Navigator, 'share' | 'canShare'>, file?: File) {
  try {
    return typeof nav.share === 'function' && typeof nav.canShare === 'function'
      && nav.canShare({ files: [file ?? new File([new Uint8Array(1)], 'affiche.jpg', { type: 'image/jpeg' })] }) === true
  } catch { return false }
}

/** A JPEG of the loaded preview at its natural size (D-SHARE-002), or null on any failure: a natural size other than the
 *  render's, no 2D context, a throw, a null blob, a blob that is not JPEG (the canvas falls back to PNG for a type it
 *  cannot write), or no callback within `ms`. A callback after the deadline is dropped. The ground is the poster's own
 *  (#17324D), so a transparent pixel never turns black. The element itself is drawn: a new Image would download the
 *  no-store PNG again. The canvas is released (sized 0) as soon as toBlob has returned: toBlob takes a copy of the bitmap
 *  when called (HTML standard, canvas serialization), so no full-size canvas outlives its call, whatever its callback
 *  does, and two openings never hold two. */
export function jpegOf(image: HTMLImageElement, width: number, height: number, ms = 10_000): Promise<Blob | null> {
  return new Promise(resolve => {
    if (image.naturalWidth !== width || image.naturalHeight !== height) return resolve(null)
    const canvas = document.createElement('canvas')
    let settled = false, timer: ReturnType<typeof setTimeout> | undefined = undefined
    const end = (blob: Blob | null) => {
      if (settled) return
      settled = true; clearTimeout(timer); canvas.width = canvas.height = 0
      resolve(blob?.type === 'image/jpeg' ? blob : null)
    }
    timer = setTimeout(() => end(null), ms)
    try {
      canvas.width = width; canvas.height = height
      const drawing = canvas.getContext('2d')
      if (!drawing) return end(null)
      drawing.fillStyle = '#17324D'; drawing.fillRect(0, 0, width, height); drawing.drawImage(image, 0, 0)
      canvas.toBlob(end, 'image/jpeg', 0.9)
    } catch { end(null) }
    canvas.width = canvas.height = 0
  })
}

/** The weight line beside « Partager »: over 1 000 000 bytes only, in megabytes, tenths rounded up. */
export const weight = (bytes: number) => bytes > 1_000_000 ? `Image de ${(Math.ceil(bytes / 100_000) / 10).toFixed(1).replace('.', ',')} Mo` : ''

/** One tap of « Partager » (D-SHARE-004). `late`: the copy still pending 3 s after the share settled. */
export interface Attempt { id: number; share: 'pending' | 'shared' | 'aborted' | 'stuck' | 'failed'; copy: 'none' | 'pending' | 'copied' | 'not_copied'; late: boolean }
let attempts = 0
/** The tap, synchronous up to `share` so that the tap's user activation reaches it: the copy of a caption the rule keeps is
 *  started, never awaited, its failure handled on its own (a synchronous throw included); then `share` is called with the
 *  file alone (no text, title or url: the caption goes by the clipboard), whatever the copy did. Every later change of
 *  this attempt is given to `changed` as a new value; `attempt` is its state when `share` has been called. `dispose`
 *  (another tap, another opening, the page going) stops its timer and its later answers. */
export function shareFile(file: File, caption: string, nav: Pick<Navigator, 'share' | 'clipboard'>, changed: (attempt: Attempt) => void) {
  const state: Attempt = { id: ++attempts, share: 'pending', copy: 'none', late: false }
  let disposed = false, timer: ReturnType<typeof setTimeout> | undefined = undefined
  const tell = () => { if (!disposed) changed({ ...state }) }
  const copied = (outcome: 'copied' | 'not_copied') => { if (state.copy === 'pending') { state.copy = outcome; clearTimeout(timer); tell() } }
  if (captionFault(caption) === null) {
    state.copy = 'pending'
    try { nav.clipboard.writeText(caption).then(() => copied('copied'), () => copied('not_copied')) }
    catch { copied('not_copied') }
  }
  let shared: Promise<void>
  try { shared = nav.share({ files: [file] }) } catch (reason) { shared = Promise.reject(reason) }
  Promise.resolve(shared).then(() => 'shared' as const, (reason: unknown) => {
    const name = (reason as { name?: unknown } | null)?.name
    return name === 'AbortError' ? 'aborted' as const : name === 'InvalidStateError' ? 'stuck' as const : 'failed' as const
  }).then(outcome => {
    state.share = outcome; tell()
    // Only where `copy_unknown` can show (linesOf): never after a cancel or a `stuck`.
    if (state.copy === 'pending' && !disposed && (outcome === 'shared' || outcome === 'failed'))
      timer = setTimeout(() => { if (state.copy === 'pending') { state.late = true; tell() } }, 3000)
  })
  return { attempt: { ...state }, dispose: () => { disposed = true; clearTimeout(timer) } }
}

/** What the panel says of an attempt: the share's line, and the copy's. A cancel (AbortError) says nothing, a later copy
 *  outcome included. While the share is pending, nothing, unless `slow` (15 s of visible waiting): a provisional `stuck`.
 *  The copy is spoken of only once the share has resolved or failed, and never claimed while pending. */
export function linesOf(attempt: Attempt | null, slow: boolean): { share: 'failed' | 'stuck' | null; copy: 'copied' | 'not_copied' | 'copy_unknown' | null } {
  if (!attempt || attempt.share === 'aborted') return { share: null, copy: null }
  if (attempt.share === 'pending' || attempt.share === 'stuck') return { share: attempt.share === 'stuck' || slow ? 'stuck' : null, copy: null }
  const copy = attempt.copy === 'copied' || attempt.copy === 'not_copied' ? attempt.copy : attempt.copy === 'pending' && attempt.late ? 'copy_unknown' : null
  return { share: attempt.share === 'failed' ? 'failed' : null, copy }
}
