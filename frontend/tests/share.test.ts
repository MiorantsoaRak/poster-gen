import { describe, expect, it } from 'vitest'
import { presentedAsCurrent } from '../src/share'

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
