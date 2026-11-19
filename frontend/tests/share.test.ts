import { describe, expect, it } from 'vitest'
import { captionFault, presentedAsCurrent, readCaption } from '../src/share'

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
