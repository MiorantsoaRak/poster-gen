import { describe, expect, it } from 'vitest'
import { POSTER_STRIP, posterHeight } from '../src/viewport'

describe('height of the poster kept on top of the controls', () => {
  // The compact preview leaves room for visible tools (R-EDITOR-REFINEMENTS-001).
  it.each([[740, 163], [844, 180], [640, 141], [1000, 180]])('leaves room for tools at %d px: %d px', (visible, height) => {
    expect(posterHeight(visible)).toBe(height)
  })
  it('keeps a useful preview on the phone', () => expect(posterHeight(740)).toBeGreaterThan(POSTER_STRIP))
  it.each([1236, 1400, 2200])('never exceeds 180 px (%d px visible)', visible => expect(posterHeight(visible)).toBe(180))
  it.each([[360, 96], [282, 96], [200, 96], [0, 96]])('keeps the strip as its floor on a short screen (%d px): %d px', (visible, height) => {
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
