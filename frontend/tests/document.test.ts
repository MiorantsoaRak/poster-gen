import { describe, expect, it } from 'vitest'
import { copy, drawOrder, fitCrop, FORMATS, formatPrice, History, nearestFormat, parsePrice, reformat, setIdentity, type Format, type PosterDocument } from '../src/document'
import { document } from './fixture'

describe('the format a model image is close to (8 % rule)', () => {
  it.each([[1080, 1350, 'feed'], [1500, 2000, 'feed'], [1080, 1080, 'square'], [1000, 1050, 'square'], [1050, 1000, 'square'],
    [1080, 1920, 'story'], [900, 1600, 'story'], [720, 1280, 'story']])('reads %i × %i as %s', (width, height, format) => {
    expect(nearestFormat(width, height)).toBe(format)
  })
  // 2:3 sits between Publication and Story; landscape is no format; nothing for a size that is not one.
  it.each([[1000, 1500], [1600, 900], [1350, 1080], [1200, 1000], [1000, 2400], [0, 100], [100, 0], [-100, 100], [NaN, 100], [Infinity, 100]])('asks nothing for %d × %d', (width, height) => {
    expect(nearestFormat(width, height)).toBeNull()
  })
  it('stops at 8 %, in both directions', () => {
    const at = (format: Format, factor: number) => nearestFormat(FORMATS[format][0] * factor, FORMATS[format][1])
    for (const format of Object.keys(FORMATS) as Format[]) {
      expect([at(format, Math.exp(.079)), at(format, Math.exp(-.079))]).toEqual([format, format])
      expect([at(format, Math.exp(.081)), at(format, Math.exp(-.081))]).toEqual([null, null])
    }
  })
})

describe('reformat: another format before the first version', () => {
  const layer = (role: 'title' | 'price' | 'shop_name' | 'contact', y: number, height: number, visible = true) => ({ id: role, kind: 'text' as const, role, x: 64, y, width: 952, height, z: 0, visible,
    font_id: 'noto-sans' as const, font_size: 40, weight: 700 as const, fill: '#FFFFFF', align: 'left' as const, line_height: 1.2, outline: null, shadow: null, texture_effect_id: null })
  const poster = (): PosterDocument => {
    const doc = document()
    doc.include.contact = true
    doc.formats.feed = { scene: { visual_id: 'scene', crop: { x: 0, y: 0, w: 1088, h: 1360 } },
      layers: [layer('title', 64, 192, false), layer('price', 970, 120, false), layer('shop_name', 1110, 64), layer('contact', 1186, 132, false)] }
    return doc
  }
  const ys = (doc: PosterDocument, format: Format) => doc.formats[format]!.layers.map(item => item.y)

  it('gives one layout without a scene, the top in place and the bottom at its distance from the bottom', () => {
    const before = poster(), kept = copy(before), story = reformat(before, 'story')
    expect(before).toEqual(kept)  // pure
    expect(story.primary_format).toBe('story')
    expect(Object.keys(story.formats)).toEqual(['story'])
    expect(story.formats.story!.scene).toEqual({ visual_id: null, crop: null })
    expect(ys(story, 'story')).toEqual([64, 970 + 570, 1110 + 570, 1186 + 570])
    expect(story.formats.story!.layers.map(item => [item.x, item.width])).toEqual(before.formats.feed!.layers.map(item => [item.x, item.width]))
    expect(story.offer).toEqual(before.offer)
    const square = reformat(story, 'square')
    expect(ys(square, 'square')).toEqual([64, 970 - 270, 1110 - 270, 1186 - 270])
    expect(reformat(square, 'feed').formats.feed!.layers.map(item => item.y)).toEqual(ys(before, 'feed'))
  })

  it('keeps every layer inside the new canvas', () => {
    const doc = document()
    doc.formats = { story: { scene: { visual_id: null, crop: null }, layers: [layer('title', 800, 318), layer('price', 1900, 120), { ...layer('contact', -40, 2000), x: 900 }] } }
    doc.primary_format = 'story'; doc.include.contact = true
    for (const to of Object.keys(FORMATS) as Format[]) {
      const [width, height] = FORMATS[to]
      for (const item of reformat(doc, to).formats[to]!.layers) {
        expect(item.x).toBeGreaterThanOrEqual(0); expect(item.y).toBeGreaterThanOrEqual(0)
        expect(item.x + item.width).toBeLessThanOrEqual(width); expect(item.y + item.height).toBeLessThanOrEqual(height)
      }
    }
    expect(ys(reformat(doc, 'square'), 'square')).toEqual([762, 960, 0])
  })

  it('shows again as layers what the scene had drawn, and the shop texts as they are ticked', () => {
    const doc = poster()
    doc.include.shop_name = false
    const layers = reformat(doc, 'story').formats.story!.layers
    expect(layers.map(item => [item.role, item.visible])).toEqual([['title', true], ['price', true], ['shop_name', false], ['contact', true]])
  })
})

it('cuts the undo history at the nearest state in another format', () => {
  const history = new History(), feed = document()
  history.record(feed)
  const story = reformat(feed, 'story')
  history.record(story)
  const edited = copy(story); edited.offer.title = 'Edited'
  history.record(edited)
  history.keepFormat('story')
  expect(history.past.map(doc => [doc.primary_format, doc.offer.title])).toEqual([['story', 'Soundcore R50i'], ['story', 'Edited']])
  const back = history.undo(edited)!
  history.undo(back); history.keepFormat('story')
  expect(history.past).toHaveLength(0)
  expect(history.future.every(doc => doc.primary_format === 'story')).toBe(true)
  // A redo that would bring Publication back is gone as well.
  const other = new History()
  other.record(story); other.undo(feed); other.keepFormat('story')
  expect(other.future).toHaveLength(0)
})

describe('exact Ariary values', () => {
  it('accepts integer groups without rounding', () => {
    expect(parsePrice('90 000')).toBe(90000)
    expect(parsePrice('9\u00a0007\u202f199\u202f254\u202f740\u202f991')).toBe(Number.MAX_SAFE_INTEGER)
    expect(formatPrice(90000)).toBe('90\u202f000 Ar')
  })
  // As prices are written in Madagascar and typed on a phone (first walk on the live pilot, 2026-11-13).
  it.each([['90.000', 90000], ['90 000 Ar', 90000], ['90000ar', 90000], [' 90 000 ', 90000], ['1.250.000 AR', 1250000],
    ['12 Ar', 12], [' 12', 12], ['190 000 ariary', 190000], ['5.000 MGA', 5000]])('reads %s as %d', (value, amount) => {
    expect(parsePrice(value as string)).toBe(amount)
  })
  it.each(['1e3', '1.5', '90,000', '90,5', '90 00', '9.0000', '1.000 000', '1 000.000', '-1', 'Ar', '', 'Ar 90 000', '90 000 € ', '9007199254740992'])('refuses %s', value => {
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

it('draws the price pill and the badge in front of every other layer, whatever their z', () => {
  const layer = (role: string, z: number, visible = true) => ({ role, z, visible })
  const order = drawOrder([layer('price', 1), layer('logo', 4), layer('title', 0), layer('contact', 7), layer('shop_name', 6), layer('product', 9), layer('contact', 8, false)])
  expect(order.map(item => item.role)).toEqual(['title', 'shop_name', 'contact', 'product', 'logo', 'price'])
  expect(drawOrder([layer('title', 2), layer('contact', 1)]).map(item => item.z)).toEqual([1, 2])
})
