import { expect, it } from 'vitest'

// The role table of D-REDESIGN-001 on the shop's interface (the Signal kit, the mockup's doka.css), so that a later edit
// cannot drift from it. Files as text through Vite's glob: the project has no Node types.
const files = import.meta.glob<string>(['../src/style.css', '../index.html', '../public/donnees.html'], { query: '?raw', import: 'default', eager: true })
const css = files['../src/style.css']!

// The stylesheet's rules, comments left out: those at the top level (at '') and those inside each @media or @supports
// (at its prelude). @font-face and @keyframes hold no token.
type Rule = { at: string, selector: string, body: string }
const rules: Rule[] = []
const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
const walk = (from: number, to: number, at: string) => {
  let start = from, depth = 0, open = -1
  for (let i = from; i < to; i++) {
    if (text[i] === '{' && depth++ === 0) open = i
    else if (text[i] === '}' && --depth === 0) {
      const prelude = text.slice(start, open).trim().replace(/\s+/g, ' ')
      if (/^@(media|supports)\b/.test(prelude)) walk(open + 1, i, prelude)
      else if (!prelude.startsWith('@')) rules.push({ at, selector: prelude, body: text.slice(open + 1, i) })
      start = i + 1
    }
  }
}
walk(0, text.length, '')
const declared = (body: string) => [...body.matchAll(/--([\w-]+)\s*:\s*([^;]+)/g)].map(([, name, value]) => [name!, value!.replace(/\s+/g, ' ').trim()] as const)
// A theme's tokens: every declaration outside @media and @supports in the rules of exactly this selector, each declared
// once, so that a later rule cannot change a value unseen.
const tokens = (selector: string) => {
  const all = rules.filter(rule => !rule.at && rule.selector === selector).flatMap(rule => declared(rule.body))
  const names = all.map(([name]) => name)
  expect(names.filter((name, i) => names.indexOf(name) !== i), `declared twice in ${selector}`).toEqual([])
  return Object.fromEntries(all) as Record<string, string>
}
const DARK = ':root', LIGHT = ':root[data-theme=clair]'
const dark = tokens(DARK), light = { ...dark, ...tokens(LIGHT) }  // the light theme overrides the dark one

const ROLES = {
  dark: {
    ground: '#20201d', surface: '#2b2b27', raised: '#36362f', text: '#f5f1e8', muted: '#d6d0c3', faint: '#c2bcaf',
    line: 'rgb(245 241 232 / .10)', control: '#8f8b80', edge: 'rgb(245 241 232 / .22)', active: 'rgb(245 241 232 / .10)', 'side-bg': 'rgb(0 0 0 / .22)',
    signal: '#f2c744', 'on-signal': '#20201d', 'signal-edge': '#f2c744', 'signal-hover': '#d5b03f', hue: '#f2c744',
    ok: '#8fddb0', 'ok-bg': '#1d3327', warn: '#f0c26a', 'warn-bg': '#3a2f14', bad: '#ff9a8f', 'bad-bg': '#3d2320', invert: '#f5f1e8',
    'patch-1': 'rgb(242 199 68 / .16)', 'patch-2': 'rgb(110 98 70 / .34)', 'patch-3': 'rgb(255 255 255 / .04)',
    'glass-strong': 'rgb(43 43 39 / .88)', lift: '0 2px 4px rgb(0 0 0 / .45), 0 28px 60px -28px rgb(0 0 0 / .9)',
  },
  light: {
    ground: '#f5f1e8', surface: '#fffdf8', raised: '#ece6d8', text: '#20201d', muted: '#4d4940', faint: '#5f5a50',
    line: 'rgb(32 32 29 / .10)', control: '#7d786d', edge: 'rgb(32 32 29 / .20)', active: 'rgb(32 32 29 / .08)', 'side-bg': 'rgb(32 32 29 / .045)',
    signal: '#f2c744', 'on-signal': '#20201d', 'signal-edge': '#d9b032', 'signal-hover': '#d5b03f', hue: '#8f6b00',
    ok: '#145c37', 'ok-bg': '#e2f2e8', warn: '#6b4600', 'warn-bg': '#fdf0cf', bad: '#a3271f', 'bad-bg': '#fbeae8', invert: '#20201d',
    'patch-1': 'rgb(242 199 68 / .28)', 'patch-2': 'rgb(222 204 168 / .55)', 'patch-3': 'rgb(255 255 255 / .7)',
    'glass-strong': 'rgb(255 253 248 / .86)', lift: '0 2px 4px rgb(60 44 16 / .08), 0 28px 60px -28px rgb(60 44 16 / .45)',
  },
}
const pick = (all: Record<string, string>) => Object.fromEntries(Object.keys(ROLES.dark).map(name => [name, all[name]]))

it('keeps the role table in both themes', () => {
  expect(pick(dark)).toEqual(ROLES.dark)
  expect(pick(light)).toEqual(ROLES.light)
  // The field behind the window: the three lights, one from each side. The light theme changes the lights, not the field.
  expect(light.ambient).toBe(dark.ambient)
  expect(dark.ambient).toBe('radial-gradient(52rem 34rem at 8% -6%, var(--patch-1), transparent 62%), radial-gradient(46rem 38rem at 104% 104%, var(--patch-2), transparent 60%), radial-gradient(34rem 26rem at 62% 34%, var(--patch-3), transparent 70%)')
})

// The balance card is the dark surface in the light theme too: there, and only there, a rule writes the table's tokens
// again, each with the dark theme's value.
const INVERSE = ':root[data-theme=clair] .balance-card'

it('declares a token of the table only in the two themes, in the solid fallback and on the balance card', () => {
  const fallback = /^@(supports not|media \(prefers-reduced-transparency: reduce\))/
  const elsewhere = rules.filter(rule => declared(rule.body).some(([name]) => name in ROLES.dark || name === 'ambient'))
    .filter(rule => !(rule.at === '' && [DARK, LIGHT, INVERSE].includes(rule.selector)) && !(fallback.test(rule.at) && rule.selector === ':root:root'))
  expect(elsewhere.map(rule => `${rule.at} ${rule.selector}`)).toEqual([])
})

it('gives the balance card the dark theme\'s values in the light theme', () => {
  const again = Object.entries(tokens(INVERSE)).filter(([name]) => name in ROLES.dark)
  expect(again.map(([name]) => name)).toContain('text')
  for (const [name, value] of again) expect(value, name).toBe(dark[name])
})

it('makes what floats opaque and still where the browser cannot blur or the person asked for less', () => {
  const solid = rules.filter(rule => rule.selector === ':root:root').map(rule => [rule.at, Object.fromEntries(declared(rule.body))])
  expect(solid).toEqual([
    ['@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))', { 'glass-strong': 'var(--surface)' }],
    ['@media (prefers-reduced-transparency: reduce), (prefers-reduced-motion: reduce)', { 'glass-strong': 'var(--surface)', 'blur-panel': 'none' }],
  ])
})

// WCAG 2 contrast from the pinned values: #rrggbb, or rgb(r g b / a).
const colour = (value: string) => {
  const hex = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(value), fn = /^rgb\((\d+) (\d+) (\d+)(?: \/ ([\d.]+))?\)$/.exec(value)
  expect(hex || fn, `a colour this test reads: ${value}`).toBeTruthy()
  return hex ? [...hex.slice(1).map(h => parseInt(h, 16)), 1] : [Number(fn![1]), Number(fn![2]), Number(fn![3]), fn![4] === undefined ? 1 : Number(fn![4])]
}
const over = (top: number[], under: number[]) => [0, 1, 2].map(i => top[i]! * top[3]! + under[i]! * (1 - top[3]!))
const luminance = (c: number[]) => c.slice(0, 3).map(v => (v /= 255) <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i]!, 0)
const ratio = (a: number[], b: number[]) => { const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m); return (x! + .05) / (y! + .05) }

it('keeps the text of what floats at 4.5:1 whatever is behind it, black or white', () => {
  for (const [theme, all] of [['dark', dark], ['light', light]] as const) {
    for (const behind of [[0, 0, 0], [255, 255, 255]]) {
      const glass = over(colour(all['glass-strong']!), behind)
      for (const role of ['text', 'muted', 'faint']) expect(ratio(colour(all[role]!), glass), `${role} on ${theme} glass over rgb(${behind})`).toBeGreaterThanOrEqual(4.5)
    }
  }
})

// The sidebar's column is painted by the frame, a pseudo-element of body that the browser's contrast check cannot see.
it('keeps the sidebar’s secondary text at 4.5:1 on its tint over the ground', () => {
  for (const [theme, all] of [['dark', dark], ['light', light]] as const) {
    const column = over(colour(all['side-bg']!), colour(all.ground!))
    for (const role of ['muted', 'faint']) expect(ratio(colour(all[role]!), column), `${role} on the ${theme} sidebar`).toBeGreaterThanOrEqual(4.5)
  }
})

// The rail is the device's choice, applied before the first paint (D-REDESIGN-002): read inside a try, so that a storage
// that refuses leaves the sidebar, and before the application's script.
it('applies the kept rail in the inline script, before the app', () => {
  const page = files['../index.html']!, inline = /<script>([\s\S]*?)<\/script>/.exec(page)!
  expect(inline[1]).toMatch(/try \{ if \(localStorage\.getItem\('affiche\.rail'\) === '1'\) document\.documentElement\.dataset\.rail = '' \} catch \(e\) \{\}/)
  expect(inline.index).toBeLessThan(page.indexOf('<script type="module"'))
})

it('gives the browser’s bar the theme’s ground in both pages', () => {
  for (const page of ['../index.html', '../public/donnees.html']) {
    expect(files[page], page).toContain('<meta name="theme-color" content="#f5f1e8" media="(prefers-color-scheme: light)" />')
    expect(files[page], page).toContain('<meta name="theme-color" content="#20201d" media="(prefers-color-scheme: dark)" />')
  }
  expect(files['../index.html']).toContain("theme === 'clair' ? '#f5f1e8' : '#20201d'")
})
