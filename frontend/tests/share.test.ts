import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { canShareFiles, captionFault, linesOf, presentedAsCurrent, readCaption, shareFile, weight, type Attempt } from '../src/share'

describe('canShareFiles', () => {
  const share = () => Promise.resolve()
  it('is true only with both functions and canShare accepting a JPEG file', () => {
    const asked: ShareData[] = []
    expect(canShareFiles({ share, canShare: data => { asked.push(data!); return true } })).toBe(true)
    expect(asked[0].files![0].type).toBe('image/jpeg')
  })
  it('is false when share or canShare is missing, refuses, or throws', () => {
    expect(canShareFiles({ share: undefined as never, canShare: () => true })).toBe(false)
    expect(canShareFiles({ share, canShare: undefined as never })).toBe(false)
    expect(canShareFiles({ share, canShare: () => false })).toBe(false)
    expect(canShareFiles({ share, canShare: () => { throw new TypeError('no') } })).toBe(false)
    expect(canShareFiles({ share, canShare: (() => 'yes') as never })).toBe(false)
  })
  it('asks about the given file', () => {
    const file = new File(['x'], 'affiche-feed-12345678.jpg', { type: 'image/jpeg' })
    expect(canShareFiles({ share, canShare: data => data!.files![0] === file }, file)).toBe(true)
  })
})

describe('weight', () => {
  it('is said over 1 000 000 bytes only, in tenths rounded up', () => {
    expect(weight(1_000_000)).toBe('')
    expect(weight(1_000_001)).toBe('Image de 1,1 Mo')
    expect(weight(1_400_000)).toBe('Image de 1,4 Mo')
    expect(weight(2_000_000)).toBe('Image de 2,0 Mo')
  })
})

describe('shareFile', () => {
  const file = new File([new Uint8Array(4)], 'affiche-feed-12345678.jpg', { type: 'image/jpeg' })
  const error = (name: string) => new DOMException('essai', name)
  // A navigator whose share and copy are settled by hand; `calls` in the order they happened.
  function phone(copy: 'held' | 'throws' | 'none' = 'held') {
    const calls: string[] = [], shared: unknown[] = []
    let shareDone!: (value?: unknown) => void, shareFail!: (reason: unknown) => void, copyDone!: () => void, copyFail!: (reason: unknown) => void
    const nav = {
      share: (data: ShareData) => { calls.push('share'); shared.push(data); return new Promise<void>((ok, ko) => { shareDone = ok as never; shareFail = ko }) },
      clipboard: { writeText: (text: string) => {
        calls.push('copy ' + text)
        if (copy === 'throws') throw error('NotAllowedError')
        return new Promise<void>((ok, ko) => { copyDone = ok; copyFail = ko })
      } },
    } as unknown as Navigator
    if (copy === 'none') (nav as { clipboard?: unknown }).clipboard = undefined
    return { nav, calls, shared, share: { done: () => shareDone(), fail: (name: string) => shareFail(error(name)) }, copy: { done: () => copyDone(), fail: () => copyFail(error('NotAllowedError')) } }
  }
  let seen: Attempt[]
  const changed = (attempt: Attempt) => seen.push(attempt)
  const last = () => seen.at(-1)!
  const settle = () => vi.advanceTimersByTimeAsync(0)
  beforeEach(() => { seen = []; vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('calls share before returning, with the file alone, the copy held', () => {
    const { nav, calls, shared } = phone()
    const made = shareFile(file, 'Galaxy A15', nav, changed).attempt
    expect(calls).toEqual(['copy Galaxy A15', 'share'])
    expect(shared).toEqual([{ files: [file] }])
    expect(Object.keys(shared[0] as object)).toEqual(['files'])
    expect(made).toMatchObject({ share: 'pending', copy: 'pending' })
  })
  it('calls share when the copy throws at once, and records that copy as failed', () => {
    const { nav, calls } = phone('throws')
    const made = shareFile(file, 'Galaxy A15', nav, changed).attempt
    expect(calls).toEqual(['copy Galaxy A15', 'share'])
    expect(made.copy).toBe('not_copied')
  })
  it('calls share without a clipboard at all', () => {
    const { nav, calls } = phone('none')
    expect(shareFile(file, 'Galaxy A15', nav, changed).attempt.copy).toBe('not_copied')
    expect(calls).toEqual(['share'])
  })
  it('copies nothing for a blank or refused caption', () => {
    for (const caption of ['', '   \n', 'a\x00b', '😀'.repeat(2001)]) {
      const { nav, calls } = phone()
      expect(shareFile(file, caption, nav, changed).attempt.copy).toBe('none')
      expect(calls).toEqual(['share'])
    }
  })
  it('says copied or not copied once the share resolves', async () => {
    for (const [settleCopy, line] of [['done', 'copied'], ['fail', 'not_copied']] as const) {
      const { nav, share, copy } = phone()
      shareFile(file, 'Légende', nav, changed)
      copy[settleCopy](); await settle()
      expect(linesOf(last(), false)).toEqual({ share: null, copy: null })  // the share still pending: nothing yet
      share.done(); await settle()
      expect(linesOf(last(), false)).toEqual({ share: null, copy: line })
    }
  })
  it('never claims a copy still pending: copy_unknown 3 s after the share, replaced when it settles', async () => {
    const { nav, share, copy } = phone()
    shareFile(file, 'Légende', nav, changed)
    share.done(); await settle()
    expect(linesOf(last(), false)).toEqual({ share: null, copy: null })
    await vi.advanceTimersByTimeAsync(2999)
    expect(linesOf(last(), false).copy).toBeNull()
    await vi.advanceTimersByTimeAsync(1)
    expect(linesOf(last(), false).copy).toBe('copy_unknown')
    copy.done(); await settle()
    expect(linesOf(last(), false).copy).toBe('copied')
  })
  it('stays copy_unknown while the copy never settles', async () => {
    const { nav, share } = phone()
    shareFile(file, 'Légende', nav, changed)
    share.done()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(linesOf(last(), false)).toEqual({ share: null, copy: 'copy_unknown' })
  })
  it('says nothing on AbortError, whatever the copy does, early or late', async () => {
    for (const settleCopy of ['done', 'fail', 'late'] as const) {
      const { nav, share, copy } = phone()
      shareFile(file, 'Légende', nav, changed)
      if (settleCopy !== 'late') copy[settleCopy]()
      share.fail('AbortError'); await settle()
      expect(linesOf(last(), true)).toEqual({ share: null, copy: null })  // a provisional stuck withdrawn too
      await vi.advanceTimersByTimeAsync(5000)
      if (settleCopy === 'late') { copy.fail(); await settle() }
      expect(linesOf(last(), false)).toEqual({ share: null, copy: null })
    }
  })
  it('says stuck on InvalidStateError, failed on any other error with the copy outcome', async () => {
    const stuck = phone()
    shareFile(file, 'Légende', stuck.nav, changed)
    stuck.copy.done(); stuck.share.fail('InvalidStateError'); await settle()
    expect(linesOf(last(), false)).toEqual({ share: 'stuck', copy: null })
    for (const name of ['NotAllowedError', 'TypeError', 'DataError', 'OtherError']) {
      const { nav, share, copy } = phone()
      shareFile(file, 'Légende', nav, changed)
      copy.done(); share.fail(name); await settle()
      expect(linesOf(last(), false)).toEqual({ share: 'failed', copy: 'copied' })
    }
  })
  it('treats a share that throws at once like a rejection', async () => {
    const nav = { share: () => { throw new TypeError('bad data') }, clipboard: { writeText: () => Promise.resolve() } } as unknown as Navigator
    shareFile(file, '', nav, changed); await settle()
    expect(linesOf(last(), false)).toEqual({ share: 'failed', copy: null })
  })
  it('says a provisional stuck only while pending and slow, replaced by the outcome', async () => {
    const { nav, share, copy } = phone()
    const made = shareFile(file, 'Légende', nav, changed).attempt
    expect(linesOf(made, false).share).toBeNull()
    expect(linesOf(made, true).share).toBe('stuck')
    copy.done(); share.done(); await settle()
    expect(linesOf(last(), true)).toEqual({ share: null, copy: 'copied' })
  })
  it('gives each tap its own id (the panel keeps the current one’s: share_browser.py settles tap one after tap two)', () => {
    const first = shareFile(file, 'Un', phone().nav, changed).attempt, second = shareFile(file, 'Deux', phone().nav, changed).attempt
    expect(second.id).not.toBe(first.id)
  })
  it('arms the copy timer only where copy_unknown can show, and clears it when the copy settles', async () => {
    for (const name of ['AbortError', 'InvalidStateError']) {
      const { nav, share } = phone()
      shareFile(file, 'Légende', nav, changed)
      share.fail(name); await settle()
      expect(vi.getTimerCount()).toBe(0)
    }
    const { nav, share, copy } = phone()
    shareFile(file, 'Légende', nav, changed)
    share.done(); await settle()
    expect(vi.getTimerCount()).toBe(1)
    copy.done(); await settle()
    expect(vi.getTimerCount()).toBe(0)
  })
  it('once disposed, clears its timer and tells nothing more', async () => {
    const { nav, share, copy } = phone()
    const { dispose } = shareFile(file, 'Légende', nav, changed)
    share.done(); await settle()
    const told = seen.length
    dispose()
    expect(vi.getTimerCount()).toBe(0)
    copy.fail(); await vi.advanceTimersByTimeAsync(5000)
    expect(seen.length).toBe(told)
  })
})

describe('presentedAsCurrent', () => {
  it('is current only when made from the saved revision with nothing waiting to be saved', () => {
    expect(presentedAsCurrent({ id: 'r', source_revision: 7 }, 7, false, null)).toBe(true)
  })
  it('is an earlier version while an edit waits or is being saved', () => {
    expect(presentedAsCurrent({ id: 'r', source_revision: 7 }, 7, true, null)).toBe(false)
    expect(presentedAsCurrent({ id: 'r', source_revision: 5 }, 7, true, { render_id: 'r', revision: 7 })).toBe(false)
  })
  it('is an earlier version when made from another revision, older or newer', () => {
    expect(presentedAsCurrent({ id: 'r', source_revision: 6 }, 7, false, null)).toBe(false)
    expect(presentedAsCurrent({ id: 'r', source_revision: 8 }, 7, false, null)).toBe(false)
  })
  it('is current when the poster read at the saved revision names it (an undo back to the same image)', () => {
    expect(presentedAsCurrent({ id: 'r', source_revision: 5 }, 7, false, { render_id: 'r', revision: 7 })).toBe(true)
  })
  it('is an earlier version once a later save follows that read', () => {
    expect(presentedAsCurrent({ id: 'r', source_revision: 5 }, 8, false, { render_id: 'r', revision: 7 })).toBe(false)
  })
  it('is an earlier version once a read shows a revision ahead of the saved one, even naming nothing', () => {
    expect(presentedAsCurrent({ id: 'r', source_revision: 7 }, 7, false, { render_id: null, revision: 8 })).toBe(false)
    expect(presentedAsCurrent({ id: 'r', source_revision: 7 }, 7, false, { render_id: 'r', revision: 8 })).toBe(false)
    expect(presentedAsCurrent({ id: 'r', source_revision: 7 }, 7, false, { render_id: null, revision: 7 })).toBe(true)
  })
  it('is an earlier version when the read naming it was of an older revision, or named another render', () => {
    expect(presentedAsCurrent({ id: 'r', source_revision: 5 }, 7, false, { render_id: 'r', revision: 6 })).toBe(false)
    expect(presentedAsCurrent({ id: 'r', source_revision: 5 }, 7, false, { render_id: 's', revision: 7 })).toBe(false)
  })
})

describe('captionFault', () => {
  const emoji = '😀'  // one code point, two UTF-16 units
  it('counts code points: 2 000 supplementary-plane emoji pass, 2 001 are too long', () => {
    expect(captionFault(emoji.repeat(2000))).toBeNull()
    expect(captionFault(emoji.repeat(2001))).toBe('too_long')
    expect(captionFault('a'.repeat(2001))).toBe('too_long')
  })
  it('allows line feeds and tabs', () => {
    expect(captionFault('Galaxy A15\n\tLivraison à Tana 📦')).toBeNull()
  })
  it('refuses NUL after a valid prefix, ESC, DEL and C1 controls', () => {
    for (const text of ['Galaxy\x00', 'a\x1Bb', 'a\x7F', 'a\u0085', 'a\u009F', 'a\r\nb']) expect(captionFault(text)).toBe('bad_character')
  })
  it('checks characters before the length and the blank rule', () => {
    expect(captionFault('\x00   ')).toBe('bad_character')
    expect(captionFault(emoji.repeat(2001) + '\x00')).toBe('bad_character')
  })
  it('is blank for an empty or whitespace-only text', () => {
    for (const text of ['', '   ', '\n\t \n']) expect(captionFault(text)).toBe('blank')
  })
})

describe('readCaption', () => {
  it('gives back a stored caption the rule keeps', () => {
    expect(readCaption('Ligne 1\nLigne 2')).toBe('Ligne 1\nLigne 2')
    expect(readCaption('😀'.repeat(2000))).toBe('😀'.repeat(2000))
  })
  it('opens empty on nothing stored or an invalid stored value', () => {
    for (const raw of [null, undefined, 42, {}, '😀'.repeat(2001), 'a\x00b', '  ']) expect(readCaption(raw)).toBe('')
  })
})
