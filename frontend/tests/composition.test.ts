import brandCases from './fixtures/brand-title-cases.json'
import { describe, expect, it } from 'vitest'
import { brandInTitle, logoPlacementStale, placeLogo } from '../src/composition'
import { colourPalette, photoPalette } from '../src/palette'
import { FORMATS, setIdentity, type Format, type Visual } from '../src/document'
import { document } from './fixture'

describe('brand word boundaries shared with Python', () => {
  const cases = brandCases as [string, string, boolean][]
  it.each(cases)('%s / %s => %s', (brand, title, expected) => expect(brandInTitle(brand, title)).toBe(expected))
})

describe('photo-derived palette', () => {
  function pixels(background: number[], product: number[]) {
    return new Uint8ClampedArray(Array.from({ length: 20 * 20 }, (_, i) => i % 20 >= 5 && i % 20 < 15 && i >= 100 && i < 300 ? product : background).flat())
  }
  it('keeps a black product neutral, ignoring the white border', () => {
    expect(photoPalette(pixels([255,255,255,255],[20,20,20,255]),20,20)[2]).toBe('#141414')
  })
  it('ignores transparent background and preserves red', () => {
    expect(photoPalette(pixels([0,0,255,0],[190,20,20,255]),20,20)[2]).toBe('#BE1414')
  })
  it('does not invent a chromatic accent for an all-white photo', () => {
    expect(photoPalette(pixels([255,255,255,255],[255,255,255,255]),20,20)[2]).toBe('#B4B4B4')
  })
  it('does not let a tiny gold detail change a black product palette', () => {
    const data=pixels([255,255,255,255],[20,20,20,255]); data.set([240,180,20,255], 210*4)
    expect(photoPalette(data,20,20)[2]).toBe('#141414')
  })
  it('rejects invalid/empty data instead of silently using another colour', () => {
    expect(() => photoPalette(new Uint8ClampedArray(16),2,2)).toThrow('transparente')
    expect(() => photoPalette(new Uint8ClampedArray(1),2,2)).toThrow('illisible')
    expect(() => colourPalette('red')).toThrow()
  })
  it('uses the exact manual colour in the displayed/sent palette', () => expect(colourPalette('#123456')[2]).toBe('#123456'))
})

describe('original logo corners', () => {
  it.each(Object.keys(FORMATS) as Format[])('keeps the original file and safe margins in %s', format => {
    const doc=document(), [width,height]=FORMATS[format]
    doc.formats={ [format]:doc.formats.feed! };doc.primary_format=format
    doc.brand_snapshot.logo_asset='a'.repeat(64);setIdentity(doc,'logo',true)
    for(const side of ['left','right'] as const){
      placeLogo(doc,side)
      const logo=doc.formats[format]!.layers.find(l=>l.kind==='logo')!
      expect(logo.y).toBe(height*(format==='story'?.13:.05))
      expect(logo.x).toBe(side==='left'?width*.05:width*.83)
      expect(logo.width).toBe(width*.12)
      expect('asset' in logo && logo.asset).toBe('a'.repeat(64))
      const visual={size:`${width}x${height}`,logo_box:{x:logo.x,y:logo.y,width:logo.width,height:logo.height}} as Visual
      expect(logoPlacementStale(doc,format,visual)).toBe(false)
      doc.formats[format]!.scene.crop={x:10,y:0,w:width-20,h:height}
      expect(logoPlacementStale(doc,format,visual)).toBe(true)
      doc.formats[format]!.scene.crop=null
      expect(logoPlacementStale(doc,format,{size:visual.size} as Visual)).toBe(true)
    }
  })
})
