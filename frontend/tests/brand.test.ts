import { expect, it } from 'vitest'

// The name and the mark (D-POLISH-001). Files as text or as data URLs through Vite's glob: the project has no Node types.
const pages = import.meta.glob<string>(['../index.html', '../admin/index.html', '../public/donnees.html', '../public/manifest.webmanifest', '../public/favicon.svg', '../src/**/*.{ts,vue,css}'],
  { query: '?raw', import: 'default', eager: true })
const shipped = import.meta.glob<string>(['../public/icons/*.png', '../public/favicon.*'], { query: '?inline', import: 'default', eager: true })
// The Signal kit's files, copied byte for byte from docs/project/brand/doka-studio-signal/web/ on 2026-11-20: their SHA-256,
// pinned here because that folder is not committed yet (a comparison with it would vanish on a fresh clone).
const KIT: Record<string, string> = {
  'icons/icon-192.png': 'd60e399df3d77e80b519bc70e04da4d7c7e531ba14b846bac3b54b8b68e24866',
  'icons/icon-512.png': '660cfd6d331f310485eb5c8f3785bf5d898e67a177c51d5fcf155be9707f7b10',
  'icons/apple-touch-icon.png': '3de51f233465eec7545dedd681fabe5d2d906543b586d4762ae2af96a141600c',
  'icons/icon-maskable-512.png': '9002325998cb5580546546071171530ed6fc110c7f59204867793afdd8f1374f',  // the kit's maskable-512.png
  'favicon.ico': 'cef2443255938703f29f24fb68092c58e4d22dc421f62458fbec41fc057f960a',
  'favicon.svg': '038974c86cdac55e704981df3899b1c514dc35c8d74939cb7781ebef29e6ed30',
}
const sha256 = async (bytes: Uint8Array<ArrayBuffer>) => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2, '0')).join('')

it('names the product Doka Studio in every page a browser reads', () => {
  expect(pages['../index.html']).toContain('<title>Doka Studio</title>')
  expect(pages['../admin/index.html']).toContain('<title>Doka Studio · Operator</title>')
  expect(pages['../public/donnees.html']).toContain('<title>Vos données · Doka Studio</title>')
  const manifest = JSON.parse(pages['../public/manifest.webmanifest']!)
  expect([manifest.name, manifest.short_name, manifest.lang]).toEqual(['Doka Studio', 'Doka', 'fr'])
  for (const [path, text] of Object.entries(pages)) expect(text.includes('Affiche Gen'), `${path} still says the old name`).toBe(false)
})

it('links the kit’s icons from the three pages and the manifest', () => {
  // The operator's page links nothing but its own script (admin.test.ts, D-ADMIN-005): a browser asks the origin for
  // /favicon.ico by itself. Its logo is its own copies of the kit's files, below.
  for (const page of ['../index.html', '../public/donnees.html'])
    for (const link of ['href="/favicon.ico"', 'href="/favicon.svg"']) expect(pages[page], page).toContain(link)
  expect(pages['../index.html']).toContain('href="/icons/apple-touch-icon.png"')
  const manifest = JSON.parse(pages['../public/manifest.webmanifest']!)
  expect(manifest.icons.map((icon: { src: string }) => icon.src)).toEqual(['/icons/icon-192.png', '/icons/icon-512.png', '/icons/icon-maskable-512.png'])
  for (const name of Object.keys(KIT)) expect(shipped[`../public/${name}`], `${name} is not shipped`).toBeTruthy()
})

it('ships the kit’s files byte for byte', async () => {
  for (const [name, digest] of Object.entries(KIT)) {
    // The SVG as text (Vite rewrites an inlined SVG); the others from their base64 data address.
    const url = shipped[`../public/${name}`]!
    const bytes = name.endsWith('.svg') ? new TextEncoder().encode(pages['../public/favicon.svg']!) : Uint8Array.from(atob(url.slice(url.indexOf(',') + 1)), char => char.charCodeAt(0))
    expect(await sha256(bytes), `${name} is not the kit's file`).toBe(digest)
  }
})

// ---- The operator's console (D-REDESIGN-005): its own copies, its tokens ----

// Copied byte for byte on 2026-11-20: the two horizontal logos from the kit's digital/ folder; doka-symbol.svg is the
// kit's web/favicon.svg (the D, charcoal on yellow: the rail's mark in both themes, as in the mockup); Figtree and its
// licence from the shops' public/fonts/.
const CONSOLE: Record<string, string> = {
  'doka-horizontal-charcoal.svg': 'c8307082e02cf2de4633f56c35b5966a388b414c8a4f554cc8cc2eb473792cbc',
  'doka-horizontal-paper.svg': '5185fe222409c08d1754b512f6fb0fc69cc3fd4e219d9ab64633f746aa9b6c8f',
  'doka-symbol.svg': '038974c86cdac55e704981df3899b1c514dc35c8d74939cb7781ebef29e6ed30',
  'Figtree-OFL.txt': '140d37233e7f3ce7313798befa9600893bcceaf41a55fa0fa5ad52f7f657a268',
  'Figtree-Variable.woff2': '4ba7d3d096695818fe0686be4f1e82c6b05134e18a22260336130335027462dd',
}
const consoleText = import.meta.glob<string>(['../src/admin/*.svg', '../src/admin/*.txt'], { query: '?raw', import: 'default', eager: true })
const consoleFont = import.meta.glob<string>('../src/admin/*.woff2', { query: '?inline', import: 'default', eager: true })

it('ships the console’s own copies of the logo, the D and Figtree, byte for byte, and uses them', async () => {
  for (const [name, digest] of Object.entries(CONSOLE)) {
    const path = `../src/admin/${name}`, url = consoleFont[path]
    const bytes = url ? Uint8Array.from(atob(url.slice(url.indexOf(',') + 1)), char => char.charCodeAt(0)) : new TextEncoder().encode(consoleText[path]!)
    expect(await sha256(bytes), `${name} is not the copied file`).toBe(digest)
  }
  const page = pages['../src/admin/Admin.vue']!, css = pages['../src/admin/admin.css']!
  for (const name of ['doka-horizontal-charcoal.svg', 'doka-horizontal-paper.svg', 'doka-symbol.svg']) expect(page).toContain(`src="./${name}"`)
  expect(css).toContain("url('./Figtree-Variable.woff2')")
  // The old mark (the name typed beside an inline drawing) is gone.
  expect(page).not.toMatch(/\bmarked\b/)
  expect(css).not.toContain('data:image/svg+xml')
})

// The table of D-REDESIGN-001, as tokens.test.ts pins it for the shops: [light, dark]. A token written once for both.
const TABLE: Record<string, [string, string]> = {
  ground: ['#f5f1e8', '#20201d'], surface: ['#fffdf8', '#2b2b27'], raised: ['#ece6d8', '#36362f'], text: ['#20201d', '#f5f1e8'],
  muted: ['#4d4940', '#d6d0c3'], faint: ['#5f5a50', '#c2bcaf'], line: ['rgb(32 32 29 / .10)', 'rgb(245 241 232 / .10)'],
  control: ['#7d786d', '#8f8b80'], edge: ['rgb(32 32 29 / .20)', 'rgb(245 241 232 / .22)'], active: ['rgb(32 32 29 / .08)', 'rgb(245 241 232 / .10)'],
  'side-bg': ['rgb(32 32 29 / .045)', 'rgb(0 0 0 / .22)'], signal: ['#f2c744', '#f2c744'], 'on-signal': ['#20201d', '#20201d'],
  'signal-edge': ['#d9b032', '#f2c744'], hue: ['#8f6b00', '#f2c744'],
  ok: ['#145c37', '#8fddb0'], 'ok-bg': ['#e2f2e8', '#1d3327'], warn: ['#6b4600', '#f0c26a'], 'warn-bg': ['#fdf0cf', '#3a2f14'],
  bad: ['#a3271f', '#ff9a8f'], 'bad-bg': ['#fbeae8', '#3d2320'],
  glass: ['rgb(255 253 248 / .66)', 'rgb(43 43 39 / .62)'], 'glass-strong': ['rgb(255 253 248 / .86)', 'rgb(43 43 39 / .88)'],
  'yellow-light': ['rgb(242 199 68 / .28)', 'rgb(242 199 68 / .16)'], 'sand-light': ['rgb(222 204 168 / .55)', 'rgb(110 98 70 / .34)'],
  'white-light': ['rgb(255 255 255 / .7)', 'rgb(255 255 255 / .04)'],
}
const consoleTokens = () => {
  const block = /^:root \{([^}]*)\}/m.exec(pages['../src/admin/admin.css']!)![1]!
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*([^;]+);/g)].map(([, name, value]) => {
    const pair = /^light-dark\((.+), (.+)\)$/.exec(value!.trim())
    return [name, pair ? [pair[1], pair[2]] : [value!.trim(), value!.trim()]]
  }))
}

it('pins the console’s colours to the table of D-REDESIGN-001, each written once for both themes', () => {
  const tokens = consoleTokens()
  for (const [name, values] of Object.entries(TABLE)) expect(tokens[name], `--${name}`).toEqual(values)
  const css = pages['../src/admin/admin.css']!
  expect(css).toContain(':root[data-theme=light] { color-scheme: light }')
  expect(css).toContain(':root[data-theme=dark] { color-scheme: dark }')
  // No second block of colours for the dark theme: the switch changes color-scheme only.
  expect(css.match(/--ground:/g)).toHaveLength(1)
})

// sRGB luminance and contrast (WCAG 2), on colours as the table writes them: #rrggbb or rgb(r g b / a).
const rgba = (value: string) => value.startsWith('#') ? [1, 3, 5].map(i => parseInt(value.slice(i, i + 2), 16)).concat(1) : value.match(/[\d.]+/g)!.map(Number)
const over = (top: number[], under: number[]) => [0, 1, 2].map(i => top[i]! * top[3]! + under[i]! * (1 - top[3]!)).concat(1)
const luminance = (c: number[]) => [.2126, .7152, .0722].reduce((sum, weight, i) => { const v = c[i]! / 255; return sum + weight * (v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4) }, 0)
const contrast = (a: number[], b: number[]) => { const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m); return (x! + .05) / (y! + .05) }

it('keeps the sidebar’s texts at 4.5:1 on the frame’s tint, which the browser checks cannot see', () => {
  // Over 1180 px the sidebar is transparent on the frame, a pseudo-element of body: its column is --side-bg over --ground.
  const tokens = consoleTokens()
  for (const theme of [0, 1]) {
    const column = over(rgba(tokens['side-bg']![theme]!), rgba(tokens.ground![theme]!))
    for (const name of ['muted', 'faint']) expect(contrast(rgba(tokens[name]![theme]!), column), `--${name}, theme ${theme}`).toBeGreaterThanOrEqual(4.5)
    // The current item: --text on --active over that column.
    expect(contrast(rgba(tokens.text![theme]!), over(rgba(tokens.active![theme]!), column))).toBeGreaterThanOrEqual(4.5)
  }
})
