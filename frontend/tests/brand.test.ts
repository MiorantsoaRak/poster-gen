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
  // /favicon.ico by itself, and the page's mark is that origin's /favicon.svg.
  for (const page of ['../index.html', '../public/donnees.html'])
    for (const link of ['href="/favicon.ico"', 'href="/favicon.svg"']) expect(pages[page], page).toContain(link)
  const drawing = /<path fill-rule="evenodd" d="([^"]+)"/.exec(pages['../public/favicon.svg']!)![1]!
  expect(pages['../src/admin/admin.css'], 'the operator’s mark is not the kit’s drawing').toContain(drawing)
  expect(pages['../src/admin/Admin.vue']!.match(/class="[^"]*\bmarked\b/g)).toHaveLength(3)
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
