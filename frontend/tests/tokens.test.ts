import { expect, it } from 'vitest'

// The Signal kit's colours on the shop's interface (D-POLISH-002), so that a later edit cannot drift from the kit. The
// dark theme keeps its own ground (ADR-091). Files as text through Vite's glob: the project has no Node types.
const files = import.meta.glob<string>(['../src/style.css', '../index.html', '../public/donnees.html'], { query: '?raw', import: 'default', eager: true })
const css = files['../src/style.css']!
const tokens = (selector: string) => {
  const block = new RegExp(`^${selector.replace(/[[\]]/g, '\\$&')} \\{([^}]*)\\}`, 'm').exec(css)
  expect(block, `${selector} not found`).toBeTruthy()
  return Object.fromEntries([...block![1]!.matchAll(/--([\w-]+):\s*([^;]+);/g)].map(([, name, value]) => [name, value!.trim()]))
}

it('keeps the kit’s values for the ground, the text and the Signal', () => {
  const pick = (all: Record<string, string>) => ['ground', 'text', 'invert', 'signal', 'on-signal'].map(name => all[name])
  const dark = tokens(':root'), light = { ...dark, ...tokens(':root[data-theme=clair]') }  // the light theme overrides the dark one
  expect(pick(dark)).toEqual(['#100f0e', '#f5f1e8', '#f5f1e8', '#f2c744', '#20201d'])
  expect(pick(light)).toEqual(['#f5f1e8', '#20201d', '#20201d', '#f2c744', '#20201d'])
})

it('gives the browser’s bar the light ground in both pages', () => {
  for (const page of ['../index.html', '../public/donnees.html']) {
    expect(files[page], page).toContain('<meta name="theme-color" content="#f5f1e8" media="(prefers-color-scheme: light)" />')
  }
  expect(files['../index.html']).toContain("theme === 'clair' ? '#f5f1e8' : '#100f0e'")
})
