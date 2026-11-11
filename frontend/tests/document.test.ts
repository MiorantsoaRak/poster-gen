import { describe, expect, it } from 'vitest'
import { fitCrop, formatPrice, History, parsePrice, setIdentity } from '../src/document'
import { document } from './fixture'

describe('exact Ariary values', () => {
  it('accepts integer groups without rounding', () => {
    expect(parsePrice('90 000')).toBe(90000)
    expect(parsePrice('9\u00a0007\u202f199\u202f254\u202f740\u202f991')).toBe(Number.MAX_SAFE_INTEGER)
    expect(formatPrice(90000)).toBe('90\u202f000 Ar')
  })
  it.each(['1e3', '1.5', '90,000', '90 00', '-1', '12 Ar', '', ' 12', '9007199254740992'])('refuses %s', value => {
    expect(() => parsePrice(value)).toThrow()
  })
})

it('toggles every brand independently without losing layers or calling generation', () => {
  const doc = document()
  for (const role of ['logo', 'shop_name', 'contact'] as const) setIdentity(doc, role, true)
  const ids = doc.formats.feed!.layers.map(layer => layer.id)
  setIdentity(doc, 'logo', false); setIdentity(doc, 'logo', true)
  expect(doc.formats.feed!.layers.map(layer => layer.id)).toEqual(ids)
  expect(doc.formats.feed!.scene.visual_id).toBeNull()
  doc.brand_snapshot.contact = null
  expect(() => setIdentity(doc, 'contact', true)).toThrow()
})

it('preserves aspect ratio when reusing a scene', () => {
  const crop = fitCrop(1088, 1360, 'story')
  expect(crop.w / crop.h).toBeCloseTo(1080 / 1920)
  expect(crop.x).toBeGreaterThan(0)
  expect(crop.y).toBe(0)
})

it.each(Array.from({ length: 8 }, (_, value) => value))('keeps identity combination %i independent', mask => {
  const doc = document()
  const roles = ['logo', 'shop_name', 'contact'] as const
  roles.forEach((role, index) => setIdentity(doc, role, Boolean(mask & (1 << index))))
  for (const [index, role] of roles.entries()) {
    expect(doc.include[role]).toBe(Boolean(mask & (1 << index)))
    expect(doc.formats.feed!.layers.some(layer => layer.role === role && layer.visible)).toBe(doc.include[role])
  }
  expect(doc.offer).toEqual(document().offer)
})

it('coalesces typing and bounds undo history', () => {
  const history = new History(), doc = document()
  history.record(doc, 'title'); doc.offer.title = 'First'
  history.record(doc, 'title'); doc.offer.title = 'Second'
  const before = history.undo(doc)!
  expect(before.offer.title).toBe('Soundcore R50i')
  expect(history.redo(before)!.offer.title).toBe('Second')
  for (let i = 0; i < 120; i++) history.record(doc)
  expect(history.past).toHaveLength(100)
})
