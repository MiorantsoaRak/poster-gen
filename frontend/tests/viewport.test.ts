import { describe, expect, it } from 'vitest'
import { POSTER_STRIP, posterHeight } from '../src/viewport'

describe('height of the poster kept on top of the controls', () => {
  // 360 × 740 is the measured low-end Android phone (R-POSTER-EDITOR-007): at least 200 px with nothing focused.
  it.each([[740, 252], [844, 287], [640, 218], [1000, 340]])('takes about a third of %d px: %d px', (visible, height) => {
    expect(posterHeight(visible)).toBe(height)
  })
  it('stays at least 200 px on the phone the requirement is measured on', () => expect(posterHeight(740)).toBeGreaterThanOrEqual(200))
  it.each([1236, 1400, 2200])('never exceeds 420 px (%d px visible)', visible => expect(posterHeight(visible)).toBe(420))
  it.each([[360, 122], [282, 96], [200, 96], [0, 96]])('keeps the strip as its floor on a short screen (%d px): %d px', (visible, height) => {
    expect(posterHeight(visible)).toBe(height)
  })
  it('never falls under the strip and grows with the screen', () => {
    let previous = 0
    for (let visible = 0; visible <= 2000; visible += 7) {
      const height = posterHeight(visible)
      expect(height).toBeGreaterThanOrEqual(POSTER_STRIP)
      expect(height).toBeGreaterThanOrEqual(previous)
      previous = height
    }
  })
})
