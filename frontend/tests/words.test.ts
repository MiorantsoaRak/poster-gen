import { describe, expect, it } from 'vitest'
import { readWords, staleWords } from '../src/words'

const stored = { on: true, price: false, contact: true, brand_text: true, brand: 'JBL', subtitle: 'CASQUE SANS FIL', accent_word: 'Tune', accent_colour: '#D92B2B', at: 5 }

describe('words read back from the browser', () => {
  it('gives back a whole entry, the colour in lower case, and nothing else', () => {
    expect(readWords(JSON.stringify({ ...stored, price_ar: 1000, contact_text: '034' }), 'JBL Tune 520')).toEqual({ on: true, price: false, contact: true, brand_text: true, brand: 'JBL', subtitle: 'CASQUE SANS FIL', accent_word: 'Tune', accent_colour: '#d92b2b' })
  })
  it.each([null, '', '{', 'null', '[]', '"text"', '7'])('gives nothing for a missing or damaged entry: %s', raw => expect(readWords(raw, 'JBL Tune 520')).toEqual({}))
  it('drops an accent word that is no longer in the title, and keeps the rest', () => {
    expect(readWords(JSON.stringify(stored), 'JBL Flip 6')).toEqual({ on: true, price: false, contact: true, brand_text: true, brand: 'JBL', subtitle: 'CASQUE SANS FIL', accent_colour: '#d92b2b' })
  })
  it('keeps "no accent word" and an accent of several words of the title', () => {
    expect(readWords('{"accent_word":""}', 'JBL Tune 520')).toEqual({ accent_word: '' })
    expect(readWords('{"accent_word":" Tune 520 "}', 'JBL Tune 520')).toEqual({ accent_word: 'Tune 520' })
  })
  it('drops fields of the wrong type or size', () => {
    expect(readWords(JSON.stringify({ on: 'yes', price: 1, brand: 7, subtitle: 'x'.repeat(61), accent_word: ['Tune'], accent_colour: 'red' }), 'JBL Tune 520')).toEqual({})
    expect(readWords(JSON.stringify({ brand: 'x'.repeat(60), accent_colour: '#12345' }), 'JBL')).toEqual({ brand: 'x'.repeat(60) })
    expect(readWords('{"accent_colour":"#1E6FE0;x"}', 'JBL')).toEqual({})
  })
})

describe('the number of posters whose words are kept', () => {
  const entry = (at: unknown) => JSON.stringify({ brand: 'x', at })
  it('removes nothing up to the limit', () => {
    expect(staleWords(Array.from({ length: 30 }, (_, index) => [`k${index}`, entry(index)]))).toEqual([])
  })
  it('removes the oldest entries beyond the limit', () => {
    expect(staleWords(Array.from({ length: 32 }, (_, index) => [`k${index}`, entry(index)])).sort()).toEqual(['k0', 'k1'])
    expect(staleWords([['a', entry(3)], ['b', entry(1)], ['c', entry(2)]], 2)).toEqual(['b'])
  })
  it('removes first an entry without a readable date', () => {
    expect(staleWords([['a', entry(1)], ['bad', '{'], ['none', null], ['text', entry('now')], ['b', entry(2)]], 2).sort()).toEqual(['bad', 'none', 'text'])
  })
})
