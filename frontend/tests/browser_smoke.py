"""Real Chromium + Vue + HTTP API smoke, isolated stub data; run from backend with uv run python ../frontend/tests/browser_smoke.py."""
import json
import base64
import copy
import io
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time

import uvicorn
from playwright.sync_api import sync_playwright, expect
from PIL import Image, ImageChops, ImageDraw

from uuid import uuid4

from affiche import shops
from affiche.api import BUNDLE, MESSAGES, create_app
from affiche.config import Settings
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import credits, terms
from affiche.posters.auth import PASSWORDS
from affiche.visuals.gateway import StubProvider

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs" / "editor-smoke"
# The two ports, from the environment when it names them (as frontend/vite.config.ts reads them): two checkouts can then
# run their smokes at the same time. Every smoke takes them from here.
WEB_PORT, API_PORT = int(os.environ.get("SMOKE_WEB_PORT", "5173")), int(os.environ.get("SMOKE_API_PORT", "8000"))
ORIGIN = f"http://127.0.0.1:{WEB_PORT}"
PASSWORD = os.urandom(12).hex()  # a throwaway credential per run against temporary stub data
IDENTIFIER = "originalphone"  # the pilot shop's (migration 0013)
SUPPORT = "l’administrateur au 034 00 000 00"  # SUPPORT_CONTACT_FR of the smokes' server


def check_material_pixels(page, document):
    fixture = copy.deepcopy(document)
    target = next(layer for layer in fixture["formats"]["feed"]["layers"] if layer["role"] == "title")
    target.update(x=64, y=64, width=950, height=140, font_size=72, fill="#FFFFFF", outline=None, shadow=None)
    fixture["offer"]["title"] = "Écouteurs R50i"
    fixture["formats"]["feed"]["scene"] = {"visual_id": None, "crop": None}
    swatch = Image.new("RGB", (32, 32), "#edc45e")
    drawing = ImageDraw.Draw(swatch)
    for x in range(0, 32, 4):
        drawing.line((x, 0, x, 31), fill="#84601b", width=2)
    stream = io.BytesIO()
    swatch.save(stream, format="PNG")
    sources = {"effect:material": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()}
    def render(doc):
        result = page.evaluate("async ([document, sources]) => (await import('/src/render.ts')).render(document, sources)", [doc, sources])
        assert not [issue for issue in result["issues"] if issue["blocking"]], result["issues"]
        return Image.open(io.BytesIO(base64.b64decode(result["png"].split(",", 1)[1]))).convert("RGB")
    plain = render(fixture)
    target["texture_effect_id"] = "material"
    material = render(fixture)
    box = ImageChops.difference(plain, material).getbbox()
    assert box and box[0] >= 64 and box[1] >= 64 and box[2] <= 1014 and box[3] <= 204, box
    # The native pattern fill cannot introduce pixels in the holes or space outside exact glyphs.
    background = Image.new("RGB", plain.size, "#17324D")
    def support(image):
        r, g, b = ImageChops.difference(image, background).split()
        return ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda value: 255 if value else 0)
    plain_glyphs, material_glyphs = support(plain), support(material)
    # Darker colours can round a faint antialias edge to zero; they may never paint outside the glyph.
    assert ImageChops.subtract(material_glyphs, plain_glyphs).getbbox() is None
    fixture["offer"]["price_ar"] += 1000
    edited = render(fixture)
    price = next(layer for layer in fixture["formats"]["feed"]["layers"] if layer["role"] == "price")
    box = ImageChops.difference(material, edited).getbbox()
    assert box and box[0] >= price["x"] and box[1] >= price["y"] and box[3] <= price["y"] + price["height"], box
    material.save(OUTPUT / "glyph-material-test.png")
    price.update(font_id="montserrat-black-italic", weight=900, font_size=72, x=240, width=600, height=150,
                 price_badge={"fill": "#FFFFFF", "border_start": "#009FE3", "border_end": "#1853BD"})
    plain_price = render(fixture)
    price["texture_effect_id"] = "material"
    textured_price = render(fixture)
    box = ImageChops.difference(plain_price, textured_price).getbbox()
    assert box and box[0] > price["x"] + 6 and box[2] < price["x"] + price["width"] - 6, box
    assert box[1] > price["y"] + 6 and box[3] < price["y"] + price["height"] - 6, box
    textured_price.save(OUTPUT / "capsule-material-test.png")


# Contrast of every visible text and placeholder against the colour behind it (WCAG: 4.5:1, or 3:1 from 24 px, or from
# 18.66 px in bold; a placeholder 4.5:1 whatever its size, its colour and opacity together, and under a typed value's ratio).
# Not measured: disabled controls, text over an image (the poster itself).
# Glass is translucent over soft colour patches (ADR-077): a text must read over the darkest and the lightest point of
# that backdrop, so it is measured over the bare ground and over each patch at its strongest, and the worst ratio counts.
# The patches are the colours of a gradient background, or of the fixed ::before layer of the page. A glass surface's
# saturate() acts on what is behind it before its fill is laid over (sRGB matrix of Filter Effects, as Chromium draws
# it); its blur only averages the backdrop towards less extreme colours, so leaving it out keeps the worst case.
BACKDROP_JS = r"""
  // Only rgb() and rgba() are read. Any other computed colour (a color-mix() computes to color(srgb …), and lab(), oklch()…)
  // stops the check with its value: a colour it cannot read must never become a passing ratio.
  const unread = value => { if (/\b(?:color|color-mix|lab|lch|oklab|oklch|hsla?|hwb)\(/.test(value)) throw new Error(`a computed colour the check cannot read: ${value}`) }
  const parse = value => {
    unread(value)
    if (!/^rgba?\(/.test(value.trim())) throw new Error(`a computed colour the check cannot read: ${value}`)
    const n = (value.match(/[\d.]+/g) || []).map(Number); return n.length < 4 ? [...n, 1] : n }
  const channel = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4 }
  const luminance = c => .2126 * channel(c[0]) + .7152 * channel(c[1]) + .0722 * channel(c[2])
  const over = (top, under) => [0, 1, 2].map(i => top[i] * top[3] + under[i] * (1 - top[3]))
  const patches = style => { unread(style.backgroundImage); return (style.backgroundImage.match(/rgba?\([^)]*\)/g) || []).map(parse).filter(colour => colour[3] > 0) }
  const spread = (bases, colours) => bases.flatMap(base => [base, ...colours.map(colour => over(colour, base))])
  const saturation = e => { const found = [getComputedStyle(e).backdropFilter, getComputedStyle(e, '::before').backdropFilter].join(' ').match(/saturate\(([\d.]+)(%?)\)/); return found ? Number(found[1]) / (found[2] ? 100 : 1) : 1 }
  const saturate = (c, s) => [[.213 + .787 * s, .715 - .715 * s, .072 - .072 * s], [.213 - .213 * s, .715 + .285 * s, .072 - .072 * s], [.213 - .213 * s, .715 - .715 * s, .072 + .928 * s]]
    .map(row => Math.min(255, Math.max(0, row[0] * c[0] + row[1] * c[1] + row[2] * c[2])))
  const fold = (layers, bases) => layers.reverse().reduce((under, [top, extra, s]) => spread(under.map(base => over(top, saturate(base, s))), extra), bases)
  const backdrop = element => {
    const layers = []
    for (let e = element; e; e = e.parentElement) {
      const style = getComputedStyle(e)
      if (style.backgroundImage.includes('url(') || e.matches('canvas, img, .poster-canvas')) return null
      const colour = parse(style.backgroundColor)
      if (colour[3] === 1) {
        const before = getComputedStyle(e, '::before')
        let bases = spread([colour], patches(style))
        if (before.content !== 'none') bases = spread(bases, patches(before))
        return fold(layers, bases)
      }
      layers.push([colour, patches(style), saturation(e)])
    }
    return fold(layers, [parse(getComputedStyle(document.documentElement).backgroundColor)])
  }
  // The worst ratio of a colour laid over each point of a backdrop, and that point.
  const lowest = (colour, bases) => bases.map(base => {
    const a = luminance(over(colour, base)), b = luminance(base)
    return [(Math.max(a, b) + .05) / (Math.min(a, b) + .05), base]
  }).reduce((low, item) => item[0] < low[0] ? item : low)
"""
CONTRAST_JS = "(expected = []) => {" + BACKDROP_JS + r"""
  const failures = [], seen = new Set(), measured = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const element = node.parentElement, text = node.textContent.trim()
    if (!text || seen.has(element) || element.closest(':disabled, [aria-disabled=true], [inert], script, style')) continue
    seen.add(element)
    const style = getComputedStyle(element), box = element.getBoundingClientRect()
    if (!box.width || !box.height || style.visibility !== 'visible' || !element.checkVisibility({ opacityProperty: true })) continue
    const behind = backdrop(element)
    if (!behind) continue
    const [ratio, worst] = lowest(parse(style.color), behind)
    const size = parseFloat(style.fontSize), needed = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700) ? 3 : 4.5
    if (ratio < needed) failures.push(`${ratio.toFixed(2)} < ${needed}: "${text.slice(0, 40)}" <${element.tagName.toLowerCase()} class="${element.className}"> ${style.color} on rgb(${worst.map(Math.round)})`)
  }
  for (const field of document.querySelectorAll('input:placeholder-shown, textarea:placeholder-shown')) {
    if (field.closest(':disabled, [aria-disabled=true], [inert]')) continue
    const style = getComputedStyle(field), box = field.getBoundingClientRect()
    if (!box.width || !box.height || style.visibility !== 'visible' || !field.checkVisibility({ opacityProperty: true })) continue
    const behind = backdrop(field)
    if (!behind) continue
    measured.push(field)
    const hint = getComputedStyle(field, '::placeholder'), colour = parse(hint.color)
    colour[3] *= Number(hint.opacity)
    const [ratio, worst] = lowest(colour, behind), typed = lowest(parse(style.color), behind)[0]
    if (ratio < 4.5 || ratio >= typed) failures.push(`placeholder ${ratio.toFixed(2)} < 4.5 or not under the typed value's ${typed.toFixed(2)}: "${field.placeholder.slice(0, 40)}" ${hint.color} at opacity ${hint.opacity} on rgb(${worst.map(Math.round)})`)
  }
  // A walk that knows an empty field is on screen names it: a placeholder not measured is a failure, not a pass.
  for (const selector of expected) if (!measured.some(field => field.matches(selector))) failures.push(`no placeholder measured for ${selector}`)
  return failures
}"""

# The accent's marks (D-POLISH-002): a line (--hue) at least 3:1 against what is behind it, a glyph on a Signal fill 4.5:1.
# Behind a mark: its parent's backdrop (a border, an outer ring), its own (an inset ring, a spinner's arc, a glyph on its
# fill), or what lies under a fixed line at the line's own place. What is painted is measured: the colour times the
# opacity of the mark and of its ancestors, a box that is not empty, a border that is drawn, a shadow that spreads. A
# repeating mark is read at a known frame, the given fraction of its animation: the dot at the smallest of its pulse, a
# moving segment half-way. The wait bar's moving part against its track: before the Signal colours the amber gave 1.85:1
# light and 6.57:1 dark (measured 2026-11-20); no less now, and in the light theme a line's 3:1 is the stricter.
MARKS = [
    [".load-line span", "backgroundColor", "under", 3, .5],
    [".chip[aria-pressed=true]", "borderTopColor", "parent", 3],
    [".format-choice label.chip:has(input:checked)", "borderTopColor", "parent", 3],
    [".layer-list button[aria-pressed=true]", "borderTopColor", "parent", 3],
    [".gen-pill i", "backgroundColor", "parent", 3, .5],
    [".wait-rail.moving span", "backgroundColor", "parent", {"clair": 3, "sombre": 6.57}, .5],
    [".wait-steps .now .n", "boxShadow", "self", 3],
    [".chat-wait i", "borderTopColor", "self", 3],
    [".chat .send:not(:disabled) svg path", "stroke", "self", 4.5],
    # The main action's label and icon on its Signal fill (D-REDESIGN-001).
    [":is(button.primary:not(:disabled), a.primary, .download-button:not(.secondary))", "color", "self", 4.5],
]
MARKS_JS = "marks => {" + BACKDROP_JS + r"""
  const theme = document.documentElement.dataset.theme, seen = new Set(), failures = [], ratios = {}
  for (const [selector, property, against, needed, at] of marks) {
    for (const e of document.querySelectorAll(selector)) {
      if (!e.checkVisibility({ visibilityProperty: true })) continue
      seen.add(selector)
      // A repeating mark is held at its frame for the reading, then put back where it was, also if the reading throws.
      const held = at === undefined ? [] : e.getAnimations().filter(a => a.playState === 'running').map(a => [a, a.currentTime])
      let style, box, value, found, drawn, behind, opacity = 1
      try {
        held.forEach(([a]) => { a.pause(); a.currentTime = at * a.effect.getTiming().duration })
        style = getComputedStyle(e), box = e.getBoundingClientRect()
        // Of several shadows the first, the one painted on top: its colour and its own spread (the fourth length).
        value = property === 'boxShadow' ? style.boxShadow.split(/,(?![^(]*\))/)[0] : style[property]
        unread(value)
        found = value.match(/rgba?\([^)]*\)/)
        drawn = property === 'borderTopColor' ? !['none', 'hidden'].includes(style.borderTopStyle) && parseFloat(style.borderTopWidth) > 0
          : property === 'boxShadow' ? parseFloat((value.replace(found?.[0], '').match(/-?[\d.]+px/g) || [])[3]) > 0
          : property === 'stroke' ? parseFloat(style.strokeWidth) > 0 : true
        for (let a = e; a; a = a.parentElement) opacity *= Number(getComputedStyle(a).opacity)
        if (property === 'stroke') opacity *= Number(style.strokeOpacity)
        const x = Math.min(innerWidth - 1, Math.max(0, box.left + box.width / 2)), y = box.top + box.height / 2
        behind = backdrop(against === 'self' ? e : against === 'parent' ? e.parentElement
          : document.elementsFromPoint(x, y).find(under => !under.contains(e)) ?? e.parentElement)
      } finally { held.forEach(([a, time]) => { a.currentTime = time; a.play() }) }
      if (!found || !behind || !box.width || !box.height || !drawn) {
        failures.push(`${selector}: not painted (${property} ${value}, ${box.width} × ${box.height} px), or an image behind`)
        continue
      }
      const colour = parse(found[0]), floor = typeof needed === 'number' ? needed : needed[theme]
      colour[3] *= opacity
      const [ratio, worst] = lowest(colour, behind)
      ratios[selector] = Math.min(ratios[selector] ?? Infinity, ratio)
      if (ratio < floor) failures.push(`${ratio.toFixed(2)} < ${floor}: ${selector} ${property} ${found[0]} at opacity ${opacity.toFixed(2)} on rgb(${worst.map(Math.round)})`)
    }
  }
  return { seen: [...seen], failures, ratios }
}"""

# Every tappable element of the editor is at least 44 × 44 px on a phone (ADR-077). A box in a label is tapped through
# its label, so the label is measured; hidden and inert elements cannot be tapped.
SMALL_TARGETS_JS = r"""() => [...document.querySelectorAll('.editor :is(button, a[href], input, select, textarea, summary)')]
  .map(e => ['checkbox', 'radio', 'color', 'file'].includes(e.type) && e.closest('label') || e)
  .filter((e, i, all) => all.indexOf(e) === i && !e.closest('[inert]') && e.checkVisibility({ visibilityProperty: true }))
  .map(e => [e, e.getBoundingClientRect()])
  .filter(([, box]) => box.width < 44 || box.height < 44)
  .map(([e, box]) => `${Math.round(box.width)} x ${Math.round(box.height)} <${e.tagName.toLowerCase()} class="${e.className}"> ${(e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 40)}`)"""
# Glass blurs once (code review 2026-11-14): nothing that blurs sits inside a surface that already blurs (its own or its
# ::before). Sticky and fixed bars are surfaces of their own over moving content; the pills over the poster blur the poster.
NESTED_BLUR_JS = r"""() => {
  const blurs = (e, pseudo) => getComputedStyle(e, pseudo).backdropFilter !== 'none'
  return [...document.querySelectorAll('body *')]
    .filter(e => blurs(e) && !['fixed', 'sticky'].includes(getComputedStyle(e).position) && !e.matches('.frame :is(.badge, .gen-pill)') && e.checkVisibility())
    .filter(e => { for (let a = e.parentElement; a; a = a.parentElement) if (blurs(a) || blurs(a, '::before')) return true; return false })
    .map(e => `<${e.tagName.toLowerCase()} class="${e.className}"> ${(e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 30)}`)
}"""
NO_SIDEWAYS = "document.documentElement.scrollWidth <= innerWidth"
# The editor's poster as drawn, and whatever between it and the stage would change how it looks: an opacity under 1, a
# filter or a blend mode, and from the canvas up to its frame a ::before or ::after laid over it (none while nothing runs).
POSTER_JS = r"""() => {
  const canvas = document.querySelector('.poster-canvas canvas'), frame = canvas.closest('.frame'), veiled = []
  for (let e = canvas; e && e !== canvas.closest('.stage').parentElement; e = e.parentElement) {
    const style = getComputedStyle(e)
    if (style.opacity !== '1' || style.filter !== 'none' || style.mixBlendMode !== 'normal')
      veiled.push(`<${e.tagName.toLowerCase()} class="${e.className}"> opacity ${style.opacity}, filter ${style.filter}, blend ${style.mixBlendMode}`)
    if (frame.contains(e)) for (const pseudo of ['::before', '::after']) {
      const over = getComputedStyle(e, pseudo)
      if (over.content !== 'none' && over.display !== 'none' && !(parseFloat(over.width) === 0 || parseFloat(over.height) === 0))
        veiled.push(`<${e.tagName.toLowerCase()} class="${e.className}">${pseudo} content ${over.content}, ${over.width} × ${over.height}`)
    }
  }
  return [canvas.toDataURL(), veiled]
}"""
GROUNDS = {"clair": "#f5f1e8", "sombre": "#20201d"}
# D-REDESIGN-001 as Chromium computes it, read on the rendered elements in each theme. The main action is charcoal on
# Signal Yellow with its edge; a secondary action (« Télécharger » beside « Partager ») is outlined, not yellow.
SIGNAL, ON_SIGNAL, CLEAR = "rgb(242, 199, 68)", "rgb(32, 32, 29)", "rgba(0, 0, 0, 0)"
PAINT = {
    "clair": {"ground": "rgb(245, 241, 232)", "surface": "rgb(255, 253, 248)", "text": "rgb(32, 32, 29)", "line": "rgba(32, 32, 29, 0.1)",
              "edge": "rgba(32, 32, 29, 0.2)", "control": "rgb(125, 120, 109)", "signal-edge": "rgb(217, 176, 50)"},
    "sombre": {"ground": "rgb(32, 32, 29)", "surface": "rgb(43, 43, 39)", "text": "rgb(245, 241, 232)", "line": "rgba(245, 241, 232, 0.1)",
               "edge": "rgba(245, 241, 232, 0.22)", "control": "rgb(143, 139, 128)", "signal-edge": "rgb(242, 199, 68)"},
}
PAINT_JS = r"""e => { const style = getComputedStyle(e)
  return { fill: style.backgroundColor, text: style.color, edge: style.borderTopColor, off: !!e.disabled || !!e.closest('[inert]'), label: e.textContent.trim().slice(0, 40) } }"""
# Cards, lists and panels at rest: an opaque fill of the surface, a hairline on each side, no blur and no shadow on
# themselves or their ::before and ::after.
RESTING = ".sign-in, .intake, .empty, .look-card, .rows, .card, .group, .comparison figure, .shot, .facts, .job-state, .rail"
RESTING_JS = r"""([selectors, surface, line]) => [...document.querySelectorAll(selectors)].filter(e => e.checkVisibility()).flatMap(e => {
  const style = getComputedStyle(e), faults = []
  const flat = matchMedia('(max-width: 720px)').matches && e.matches('.inspecting .shot, .inspecting .file-facts')
  if (style.backgroundColor !== (flat ? 'rgba(0, 0, 0, 0)' : surface)) faults.push(`fill ${style.backgroundColor}`)
  for (const side of ['Top', 'Right', 'Bottom', 'Left'])
    if (flat ? style[`border${side}Width`] !== '0px' :
        style[`border${side}Style`] !== 'solid' || !(parseFloat(style[`border${side}Width`]) > 0) || style[`border${side}Color`] !== line)
      faults.push(`border-${side.toLowerCase()} ${style[`border${side}Width`]} ${style[`border${side}Style`]} ${style[`border${side}Color`]}`)
  for (const [part, look] of [['itself', style], ['::before', getComputedStyle(e, '::before')], ['::after', getComputedStyle(e, '::after')]])
    for (const property of ['backdropFilter', 'boxShadow']) if (look[property] !== 'none') faults.push(`${part} ${property} ${look[property]}`)
  return faults.length ? [`<${e.tagName.toLowerCase()} class="${e.className}"> ${faults.join('; ')}`] : []
})"""
SHOWN_JS = "selector => [...document.querySelectorAll(selector)].some(e => e.checkVisibility())"
# The controls keep their place while a poster is made (T-WAIT-DEFORM, user report 2026-11-14): the rail's size and its
# place in its column, each row of the open tab inside the rail, the poster's size and the bottom bar's size. On one
# column the waiting block sits above the controls (D-POSTER-EDITOR-006): there the rail's place down the column is left out.
STILL_JS = r"""() => {
  const box = e => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height] }
  const inside = (e, to) => { const a = box(e), b = box(to); return [a[0] - b[0], a[1] - b[1], a[2], a[3]] }
  const rail = document.querySelector('.rail'), place = inside(rail, document.querySelector('.work'))
  const bar = [...document.querySelectorAll('.main-action')].find(e => e.checkVisibility() && getComputedStyle(e).display !== 'contents')
  return {
    rail: innerWidth > 1080 ? place : [place[0], place[2], place[3]],
    rows: [...document.querySelectorAll('#panneau > *')].filter(e => e.checkVisibility()).map(e => inside(e, rail)),
    poster: box(document.querySelector('.frame')).slice(2),
    bar: bar ? box(bar).slice(2) : null,
  }
}"""


# A colour still in its 150 ms transition is neither the old nor the new one. The waiting's rail and dot repeat forever
# (D-POSTER-EDITOR-006) and move no text colour: only animations that end are waited for. Polled every 100 ms: while
# they run, a wait polled on animation frames was seen to stop polling (Playwright 1.64's Chromium, 2026-11-14).
SETTLED = "document.getAnimations().every(animation => animation.effect.getTiming().iterations === Infinity)"


# Nothing in the editor's panel may stick out of its padding box (user, 2026-11-14: an auto grid column grew to the step
# tabs' width and pushed the panel's contents and its bottom bar 17 px out). Fixed and scrolling parts are excluded.
RAIL_FITS_JS = """() => {
  const rail = document.querySelector('.rail')
  if (!rail || !rail.getClientRects().length) return []
  const r = rail.getBoundingClientRect(), cs = getComputedStyle(rail)
  const left = r.left + parseFloat(cs.paddingLeft) - 1, right = r.right - parseFloat(cs.paddingRight) + 1
  const bad = []
  for (const e of rail.querySelectorAll('*')) {
    const b = e.getBoundingClientRect()
    if (!b.width || !b.height || e.closest('.main-action')) continue
    let fixed = false
    for (let a = e; a && a !== rail; a = a.parentElement) if (getComputedStyle(a).position === 'fixed') { fixed = true; break }
    if (fixed) continue
    let clipped = false  // inside a horizontally scrolling box, the box itself is what must fit
    for (let a = e.parentElement; a && a !== rail; a = a.parentElement) if (/auto|scroll|hidden/.test(getComputedStyle(a).overflowX)) { clipped = true; break }
    if (clipped) continue
    if (b.left < left || b.right > right) bad.push(`${e.tagName.toLowerCase()}.${String(e.className).replace(/ /g, '.')} [${(e.closest('label')?.innerText || e.getAttribute('aria-label') || e.parentElement.className || '').slice(0, 40).split('\\n').join(' ')}; parent ${e.parentElement.tagName}.${e.parentElement.className} ${Math.round(e.parentElement.getBoundingClientRect().left)}-${Math.round(e.parentElement.getBoundingClientRect().right)}] ${Math.round(b.left)}-${Math.round(b.right)} outside ${Math.round(left)}-${Math.round(right)}`)
  }
  const bar = rail.querySelector('.main-action.step-nav')
  if (bar && getComputedStyle(bar).position !== 'fixed') {
    const b = bar.getBoundingClientRect()
    if (Math.abs(b.left - r.left) > 1 || Math.abs(b.right - r.right) > 1) bad.push(`step bar ${Math.round(b.left)}-${Math.round(b.right)} not the panel's ${Math.round(r.left)}-${Math.round(r.right)}`)
  }
  return bad.slice(0, 6)
}"""


def check_marks(page, where, *expected, marks=MARKS, show=False):
    """The accent's marks on screen, measured; those expected must be among them. Returns the selectors measured; `show`
    prints the lowest ratio of each, for the record."""
    found = page.evaluate(MARKS_JS, marks)
    assert not found["failures"], f"accent marks on {where}:\n" + "\n".join(found["failures"])
    missing = [selector for selector in expected if selector not in found["seen"]]
    assert not missing, f"not on screen to be measured on {where}: {missing}"
    if show:
        print(f"Marks on {where}: " + ", ".join(f"{selector} {ratio:.2f}:1" for selector, ratio in found["ratios"].items()), flush=True)
    return set(found["seen"])


def check_contrast(page, where, *marks, placeholders=()):
    """Texts, placeholders (those of the fields named must be measured) and accent marks (those named must be on screen)."""
    page.wait_for_function(SETTLED, polling=100)
    failures = page.evaluate(CONTRAST_JS, list(placeholders))
    assert not failures, f"contrast on {where}:\n" + "\n".join(failures)
    seen = check_marks(page, where, *marks)
    outside = page.evaluate(RAIL_FITS_JS)
    assert not outside, f"panel contents outside the panel on {where}:\n" + "\n".join(outside)
    return seen


def shot(page, name, full_page=True):
    # A picture for a person to judge: from the top of the page, and not in the middle of a colour transition.
    if full_page:
        page.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
    page.wait_for_function(SETTLED, polling=100)
    page.screenshot(path=str(OUTPUT / name), full_page=full_page)


def open_drawer(page):
    """The drawer at 1180 px and under (D-REDESIGN-002): opened by the top bar's menu button, which gives the focus to
    « Fermer le menu »."""
    page.get_by_role("button", name="Ouvrir le menu").click()
    expect(page.get_by_role("button", name="Fermer le menu")).to_be_focused()
    return page.locator("aside.side")


# The shell's controls whose name in the sidebar is not the destination's: the account row is named by the shop, the
# credit card by the balance.
SIDE_ONLY = {"Mon compte": "a.account", "Mes crédits": "a.credit-card"}


def go(page, name, tap=False):
    """A destination or a control of the shell by its name, through what a person sees at the window's width
    (D-REDESIGN-002): the bottom bar at 720 px and under when it is shown and holds it, else the sidebar over 1180 px,
    else the drawer, opened first. A count after the name (« Mes affiches 3 ») is allowed."""
    pattern = re.compile("^" + re.escape(name) + r"(?: -?\d+)?$")
    press = (lambda control: control.tap()) if tap else (lambda control: control.click())
    bar = page.locator("nav.phone-bar")
    phone_link = bar.get_by_role("link", name="Créer", exact=True) if name == "Nouvelle affiche" else bar.get_by_role("link", name=pattern)
    if bar.is_visible() and phone_link.count():
        return press(phone_link)
    # The phone's chat has « Nouvelle affiche » in its top bar; the phone's step editor has no top bar, and its own bar
    # holds « Se déconnecter ».
    for there in (page.locator(".app-header").get_by_role("link", name=pattern), page.locator(".bar").get_by_role("button", name=pattern)):
        if there.count() and there.is_visible():
            return press(there)
    side = page.locator("aside.side")
    if not side.is_visible():
        open_drawer(page)
    target = side.locator(SIDE_ONLY[name]) if name in SIDE_ONLY else side.get_by_role("link", name=pattern).or_(side.get_by_role("button", name=pattern))
    press(target)


def toggle_theme(page, name, hidden=False):
    # A real click on the one visible theme button: the header's, or on a phone the drawer's (its menu then closed again
    # by Escape), or in the editor on a phone the one in « Réglages » (D-POSTER-EDITOR-005). During the steps on a phone
    # there is no « Réglages » and the header gives way to the editor's bar: there, and only where the caller says so, the
    # hidden header button receives the click event itself, so that the contrast of the steps can still be measured in
    # both themes.
    if hidden:
        button = page.locator(".app-header .theme-toggle")
        expect(button).to_be_hidden()
        expect(button).to_have_attribute("aria-label", name)
        button.dispatch_event("click")
        expect(button).not_to_have_attribute("aria-label", name)
    elif page.get_by_role("button", name=name, exact=True).count() == 0 and page.get_by_role("button", name="Ouvrir le menu").is_visible():
        open_drawer(page).get_by_role("button", name=name, exact=True).click()
        page.keyboard.press("Escape")
        expect(page.locator("aside.side")).to_have_attribute("inert", "")
    else:
        page.get_by_role("button", name=name, exact=True).click()
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(0)


def topmost(locator):
    # Its own text/icon children count as visible; an unrelated covering element does not (ADR-076).
    return locator.evaluate("e => { const r = e.getBoundingClientRect(); return e.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)) }")


def check_targets(page, where):
    small = page.evaluate(SMALL_TARGETS_JS)
    assert not small, f"tappable elements under 44 px on {where}:\n" + "\n".join(small)


def same_boxes(a, b):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_boxes(a[key], b[key]) for key in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(same_boxes(x, y) for x, y in zip(a, b))
    return a is b if a is None or b is None else abs(a - b) <= 1


def check_still(page, before, where, samples=1):
    # Sampled every 250 ms: the rail's segment, the pulsing dot and the 1 s clock run meanwhile.
    for index in range(samples):
        now = page.evaluate(STILL_JS)
        assert same_boxes(before, now), f"the controls moved {where}:\nbefore {before}\nnow    {now}"
        assert page.evaluate(NO_SIDEWAYS), f"sideways scroll {where}"
        if index < samples - 1:
            page.wait_for_timeout(250)


def check_one_blur(page, where):
    nested = page.evaluate(NESTED_BLUR_JS)
    assert not nested, f"blur inside a blurred surface on {where}:\n" + "\n".join(nested)


def both_themes(page, check):
    """`check(theme)` in the theme shown, then in the other one, set on the page itself (the owner's choice and the
    device's are left alone); the theme shown is put back, also after a failure."""
    first = theme_of(page)
    try:
        for theme in (first, "clair" if first == "sombre" else "sombre"):
            page.evaluate("theme => { document.documentElement.dataset.theme = theme }", theme)
            page.wait_for_function(SETTLED, polling=100)
            ground = page.evaluate("getComputedStyle(document.documentElement).backgroundColor")
            assert ground == PAINT[theme]["ground"], f"the page is painted {ground}, not the {theme} ground"
            check(theme)
    finally:
        page.evaluate("theme => { document.documentElement.dataset.theme = theme }", first)
        page.wait_for_function(SETTLED, polling=100)


def check_primary(page, where, action, secondary=None):
    """The named main action (a locator inside the form or the dialog in use) is charcoal on Signal Yellow with its edge,
    on screen, usable, out of hover, in both themes; the named secondary action is outlined, in the text colour, not
    yellow (R-REDESIGN-001)."""
    for control in filter(None, (action, secondary)):
        control.scroll_into_view_if_needed()
        expect(control).to_be_in_viewport()
    page.mouse.move(0, 0)

    def check(theme):
        paint = action.evaluate(PAINT_JS)
        assert not paint["off"], f"the main action « {paint['label']} » on {where} is disabled or inert"
        assert (paint["fill"], paint["text"], paint["edge"]) == (SIGNAL, ON_SIGNAL, PAINT[theme]["signal-edge"]), f"main action on {where}, {theme}: {paint}"
        if secondary:
            paint = secondary.evaluate(PAINT_JS)
            assert (paint["fill"], paint["text"], paint["edge"]) == (CLEAR, PAINT[theme]["text"], PAINT[theme]["edge"]), f"secondary action on {where}, {theme}: {paint}"
    both_themes(page, check)


def check_field(page, selector, where):
    """An empty field's boundary is 3:1 against what is around it, at rest and focused by the keyboard, in both themes
    (R-REDESIGN-001). A field that is not there fails."""
    field = page.locator(selector)
    expect(field).to_have_value("")
    mark, paint = [[selector, "borderTopColor", "parent", 3]], "e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).borderTopColor]"
    page.mouse.move(0, 0)

    def check(theme):
        field.evaluate("e => e.blur()")
        field.scroll_into_view_if_needed()
        expect(field).to_be_in_viewport(ratio=1)
        page.wait_for_function(SETTLED, polling=100)
        assert field.evaluate(paint) == [PAINT[theme]["surface"], PAINT[theme]["control"]], f"{selector} at rest on {where}, {theme}: {field.evaluate(paint)}"
        check_marks(page, f"the boundary of {selector} on {where}, {theme}", selector, marks=mark)
        field.focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        assert field.evaluate("e => e === document.activeElement && e.matches(':focus-visible')"), f"{selector} not focused by the keyboard on {where}"
        page.wait_for_function(SETTLED, polling=100)
        assert field.evaluate(paint) == [PAINT[theme]["surface"], PAINT[theme]["text"]], f"{selector} focused on {where}, {theme}: {field.evaluate(paint)}"
        check_marks(page, f"the boundary of {selector}, focused, on {where}, {theme}", selector, marks=mark)
    both_themes(page, check)
    field.evaluate("e => e.blur()")


def check_resting(page, where, *required):
    """Every card, list or panel at rest on screen is opaque in the surface colour with a hairline on each side, and
    neither it nor its ::before or ::after blurs or casts a shadow, in both themes (R-REDESIGN-001). Those named must be
    on screen."""
    missing = [selector for selector in required if not page.evaluate(SHOWN_JS, selector)]
    assert not missing, f"not on screen to be checked on {where}: {missing}"

    def check(theme):
        found = page.evaluate(RESTING_JS, [RESTING, PAINT[theme]["surface"], PAINT[theme]["line"]])
        assert not found, f"a surface at rest on {where}, {theme}:\n" + "\n".join(found)
    both_themes(page, check)


def bar_colour(page):
    # The browser's bar colour in use: the theme-color meta whose media matches the device now.
    return page.evaluate("[...document.querySelectorAll('meta[name=theme-color]')].find(meta => !meta.media || matchMedia(meta.media).matches).content.toLowerCase()")


def theme_of(page):
    return page.evaluate("document.documentElement.dataset.theme")


def walk_look(browser, session, scheme, errors):
    """A phone that never picked a theme follows its own setting (R-POSTER-EDITOR-006 amendment). A new poster is walked
    at 360 × 740 with a touch pointer: contrast on every glass surface, 44 px targets in the editor, and the pictures
    of the look (look-*.png). Returns the poster's id."""
    theme = "clair" if scheme == "light" else "sombre"
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme=scheme, storage_state=session)
    device = context.new_page()
    device.set_default_timeout(10000)
    device.on("pageerror", lambda error: errors.append(str(error)))
    device.goto(ORIGIN + "/#etapes")
    expect(device.get_by_label("Photos du produit")).to_be_attached()
    assert theme_of(device) == theme and bar_colour(device) == GROUNDS[theme], (theme_of(device), bar_colour(device))
    assert device.evaluate("getComputedStyle(document.body).fontFamily").startswith("Figtree")
    device.wait_for_function("document.fonts.check('16px Figtree')")
    check_one_blur(device, f"intake at 360 px, {theme}")
    check_contrast(device, f"intake at 360 px, {theme}, no stored choice", placeholders=("input[name=product]", "input[name=price]"))
    shot(device, f"look-360-{theme}-creer.png", full_page=False)
    expect(device.get_by_label("Photos du produit")).to_be_enabled()  # the page's opening is over (perform drops a busy tap)
    device.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
    expect(device.locator(".photo-strip img")).to_have_count(1)
    device.get_by_label("Nom du produit", exact=True).fill(f"CMF Buds 2a {theme}")
    device.get_by_label("Prix en ariary", exact=True).fill("190 000")
    device.get_by_label("Les photos correspondent").check()
    device.get_by_role("button", name="Préparer mon affiche").tap()
    expect(device.get_by_role("tab", name="Style", exact=True)).to_have_attribute("aria-selected", "true")
    marks = set()
    for step in ("textes", "boutique", "style"):
        device.get_by_role("tab", name=step.capitalize(), exact=True).tap()
        device.wait_for_function(NO_SIDEWAYS)
        check_one_blur(device, f"step {step} at 360 px, {theme}")
        marks |= check_contrast(device, f"step {step} at 360 px, {theme}", placeholders=("input[name=brand]", "input[name=subtitle]") if step == "textes" else ())
        check_targets(device, f"step {step} at 360 px, {theme}")
        shot(device, f"look-360-{theme}-etape-{step}.png", full_page=False)
    # Changes that act at once are switches; what acts on the next version stays a checkbox under its heading.
    device.get_by_role("tab", name="Boutique", exact=True).tap()
    expect(device.locator("label.switch")).to_have_count(3)
    expect(device.get_by_role("checkbox", name="Contact", exact=True)).not_to_be_checked()
    expect(device.locator("label.check:not(.switch)", has_text="Dessiner aussi le contact dans l’image")).to_have_count(0)
    device.get_by_role("tab", name="Style", exact=True).tap()
    device.get_by_role("button", name="Générer l’affiche").tap()
    device.get_by_role("button", name="Lancer la génération").tap()
    expect(device.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)
    check_one_blur(device, f"review at 360 px, {theme}")
    check_contrast(device, f"review at 360 px, {theme}")
    shot(device, f"look-360-{theme}-verifier.png", full_page=False)
    download_review(device)
    device.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(device.get_by_role("tab")).to_have_count(4)
    device.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 140")
    for name in ("Textes", "Boutique", "Style", "Réglages"):
        device.get_by_role("tab", name=name, exact=True).tap()
        expect(device.get_by_role("tab", name=name, exact=True)).to_have_attribute("aria-selected", "true")
        device.wait_for_function(NO_SIDEWAYS)
        check_one_blur(device, f"tab {name} at 360 px, {theme}")
        marks |= check_contrast(device, f"tab {name} at 360 px, {theme}")
        check_targets(device, f"tab {name} at 360 px, {theme}")
        shot(device, f"look-360-{theme}-onglet-{name.lower().replace('é', 'e')}.png", full_page=False)
    # The chosen word chip was measured on the way (D-POLISH-002); the chosen element is in run()'s editor.
    assert ".chip[aria-pressed=true]" in marks, (theme, marks)
    poster = device.url.split("#")[1]
    device.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
    shot(device, f"look-360-{theme}-affiche.png", full_page=False)
    device.get_by_role("link", name="Retour à Mes affiches").tap()
    expect(device.get_by_role("heading", name="Mes affiches", exact=True)).to_be_visible()
    check_one_blur(device, f"Mes affiches at 360 px, {theme}")
    check_contrast(device, f"Mes affiches at 360 px, {theme}")
    shot(device, f"look-360-{theme}-mes-affiches.png", full_page=False)
    if scheme == "light":
        # Nothing stored: a change of the device's setting is followed at once, bar colour included.
        device.emulate_media(color_scheme="dark")
        device.wait_for_function("document.documentElement.dataset.theme === 'sombre'")
        assert bar_colour(device) == GROUNDS["sombre"]
        check_contrast(device, "Mes affiches after the device turned dark")
        device.emulate_media(color_scheme="light")
        device.wait_for_function("document.documentElement.dataset.theme === 'clair'")
        # Once the owner picks with the theme button, his choice wins over the device, bar colour included.
        toggle_theme(device, "Passer au thème sombre")
        device.emulate_media(color_scheme="light")
        assert theme_of(device) == "sombre" and bar_colour(device) == GROUNDS["sombre"], (theme_of(device), bar_colour(device))
        device.reload()
        expect(device.get_by_role("heading", name="Mes affiches", exact=True)).to_be_visible()
        assert theme_of(device) == "sombre" and bar_colour(device) == GROUNDS["sombre"], (theme_of(device), bar_colour(device))
    context.close()
    return poster


def walk_wait(browser, session, errors):
    """Waiting while a poster is generated (R-POSTER-EDITOR-008, D-POSTER-EDITOR-006). The stub makes a scene in about a
    second and its delay is not a setting: the job's state is held by rewriting the answers to GET /api/jobs/{id} while
    the real job runs and ends behind; a poll can be made to fail, and the new image's load held. A clock installed in the
    page at the end lets 100 s pass at once. Pictures wait-*.png at 360 × 740 and 1366 × 768, both themes."""
    held = {"status": "queued", "lost": False, "images": None, "signed_out": False}
    scenes, polls, stamps = [], [], []

    def hold_job(route):
        polls.append(route.request.url)
        if held["lost"]:
            return route.abort("failed")
        if held["signed_out"]:
            return route.fulfill(status=401, json={"error": {"code": "unauthenticated", "message_fr": "Connectez-vous pour continuer.", "retryable": False}})
        if not held["status"]:
            return route.continue_()
        response = route.fetch()
        body = response.json()
        stamps.append((body["created_at"], body["started_at"], response.headers.get("date")))
        if body["kind"] in ("scene", "refine"):
            body.update(status=held["status"], result_ref=None, error_code=None, finished_at=None)
            if held["status"] == "queued":
                body["started_at"] = None
        route.fulfill(response=response, json=body)

    def hold_image(route):
        if held["images"] is None:
            return route.continue_()
        held["images"].append(route)

    def watch(context):
        context.route("**/api/jobs/*", hold_job)
        context.route("**/api/assets/**", hold_image)
        context.on("request", lambda request: scenes.append(request.url) if request.method == "POST" and request.url.endswith("/scenes") else None)

    def waiting_checks(page, where, theme, scheme):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
        page.wait_for_function(NO_SIDEWAYS)
        check_one_blur(page, f"{where}, {theme}")
        check_contrast(page, f"{where}, {theme}", ".gen-pill i", ".wait-rail.moving span", ".wait-steps .now .n")

    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark", storage_state=session)
    watch(context)
    device = context.new_page()
    device.set_default_timeout(10000)
    device.on("pageerror", lambda error: errors.append(str(error)))
    device.goto(ORIGIN + "/#etapes")
    expect(device.get_by_label("Photos du produit")).to_be_enabled()  # the page's opening is over
    device.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
    expect(device.locator(".photo-strip img")).to_have_count(1)
    device.get_by_label("Nom du produit", exact=True).fill("Écouteurs attente")
    device.get_by_label("Prix en ariary", exact=True).fill("90 000")
    device.get_by_label("Les photos correspondent").check()
    device.get_by_role("button", name="Préparer mon affiche").tap()
    block, pill, badge = device.locator(".wait"), device.locator(".frame .gen-pill"), device.locator(".frame .badge")
    words, elapsed = block.locator("[role=status]"), block.locator(".wait-time")
    cancel = device.get_by_role("button", name="Annuler la demande")
    review = device.get_by_role("heading", name="Vérifier votre affiche")
    # The draft opens asynchronously. Its original offer is replaced by the waiting status when a scene is requested.
    offer = device.get_by_role("region", name="Offre à générer")
    generate = device.get_by_role("button", name="Générer l’affiche")
    expect(offer).to_be_visible()
    expect(generate).to_be_enabled()
    poster = device.url.split("#")[1]
    endpoint = f"{ORIGIN}/api/creations/{poster}"
    first_draft = device.request.get(endpoint).json()
    device.evaluate("scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })")
    generate.tap()
    device.get_by_role("button", name="Lancer la génération").tap()
    expect(words).to_contain_text("Votre demande est en attente.")
    expect(offer).to_have_count(0)
    # The polls are background requests: once the request that started the job has its answer, the top progress line
    # never shows for them (D-POSTER-EDITOR-007).
    expect(device.locator(".load-line")).to_have_count(0)
    device.evaluate(LINE_SEEN_JS)
    polls_before = len(polls)
    expect(pill).to_have_text("En attente")
    expect(badge).to_have_text("Aperçu")
    expect(block.locator("li[aria-current=step]")).to_contain_text("Demande enregistrée")
    expect(cancel).to_be_visible()
    device.wait_for_function("scrollY === 0")
    expect(block).to_be_in_viewport()
    check_resting(device, "waiting at 360 px", ".job-state")
    assert topmost(pill) and topmost(badge)
    expect(device.locator(".frame[aria-busy=true]")).to_have_count(1)
    still = device.evaluate(STILL_JS)
    # The server stub may already have finished. Reopen the same first draft at the queued point in time
    # represented by our held poll, including its matching version list, document and job-list response.
    jobs = device.request.get(endpoint + "/jobs").json()
    pending = next(item for item in jobs["items"] if item["kind"] == "scene")
    pending.update(status="queued", started_at=None, finished_at=None, result_ref=None, error_code=None)
    resumed = context.new_page()
    resumed.route(endpoint, lambda route: route.fulfill(json=first_draft))
    resumed.route(endpoint + "/visuals", lambda route: route.fulfill(json={"items": []}))
    resumed.route(endpoint + "/jobs", lambda route: route.fulfill(json=jobs))
    resumed.goto(f"{ORIGIN}/#{poster}")
    expect(resumed.locator(".wait [role=status]")).to_contain_text("Votre demande est en attente.")
    expect(resumed.locator(".wait")).to_be_in_viewport()
    expect(resumed.locator(".frame .gen-pill")).to_have_text("En attente")
    expect(resumed.locator(".frame .badge")).to_have_text("Aperçu")
    assert topmost(resumed.locator(".frame .gen-pill")) and topmost(resumed.locator(".frame .badge"))
    resumed.get_by_role("button", name="Voir l’affiche", exact=True).tap()
    preview = resumed.get_by_role("dialog", name="Affiche")
    expect(preview.locator(".poster-canvas canvas").first).to_be_in_viewport()
    preview.get_by_role("button", name="Revenir aux réglages").tap()
    expect(resumed.get_by_role("button", name="Annuler la demande")).to_be_visible()
    resumed.close()
    assert len(scenes) == 1, scenes
    # Screen readers hear the state when it changes, not the time every second.
    assert elapsed.evaluate("e => !e.closest('[role=status], [role=alert], [aria-live]')")
    held["status"] = "running"
    expect(words).to_contain_text("Votre affiche prend forme.")
    expect(pill).to_have_text("Création en cours")
    expect(block.locator("li[aria-current=step]")).to_contain_text("Création de l’affiche")
    expect(cancel).to_have_count(0)
    shown = elapsed.text_content()
    assert re.fullmatch(r"Temps écoulé : \d+:\d\d", shown), shown
    expect(elapsed).not_to_have_text(shown)
    check_still(device, still, "while the first generation runs at 360 px", samples=6)
    assert len(polls) > polls_before and not device.evaluate("window.lineSeen"), (len(polls), polls_before)
    waiting_checks(device, "first generation at 360 px", "sombre", "dark")
    check_targets(device, "first generation at 360 px")
    shot(device, "wait-360-sombre-premiere.png", full_page=False)
    # Reduced motion: nothing repeats; the rail is a still line and the dot a still dot, as visible as when they move (still,
    # not dimmed). With motion: the dot at the smallest of its pulse, the segment half-way. Both themes (D-POLISH-002).
    for motion in ("reduce", "no-preference"):
        device.emulate_media(reduced_motion=motion)
        for scheme, theme in (("light", "clair"), ("dark", "sombre")):
            device.emulate_media(color_scheme=scheme)
            device.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
            device.wait_for_function("document.getAnimations().length === 0" if motion == "reduce" else SETTLED, polling=100)
            check_marks(device, f"waiting at 360 px, {theme}, motion {motion}", ".gen-pill i", ".wait-rail.moving span", show=True)
    # A lost poll is its own state: the job is kept, no error, no new request; the first answer brings the state back.
    held["lost"] = True
    expect(block.locator(".offline")).to_contain_text("Connexion interrompue. La demande continue")
    expect(pill).to_have_count(0)
    expect(device.locator(".message.error")).to_have_count(0)
    shot(device, "wait-360-sombre-connexion.png", full_page=False)
    held["lost"] = False
    expect(block.locator(".offline")).to_have_count(0)
    expect(pill).to_have_text("Création en cours")
    assert len(scenes) == 1, scenes
    # The job ends: « Réception » while the image is decoded. This one cannot be: the version is shown the usual way,
    # with a notice (the later arrivals decode normally).
    held["images"] = []
    held["status"] = None
    expect(words).to_contain_text("Réception de votre affiche…")
    expect(pill).to_have_text("Réception")
    expect(block.locator("li[aria-current=step]")).to_contain_text("Image prête à vérifier")
    for _ in range(50):
        if held["images"]:
            break
        device.wait_for_timeout(100)
    images, held["images"] = held["images"], None
    images[0].abort("failed")
    for image in images[1:]:
        image.continue_()
    expect(device.locator(".message.notice")).to_contain_text("son image tarde à se charger")
    expect(review).to_be_visible(timeout=30000)
    expect(block).to_have_count(0)
    expect(device.locator(".frame[aria-busy=true]")).to_have_count(0)
    download_review(device)
    device.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(device.get_by_role("tab")).to_have_count(4)
    # A new version once one exists: the version shown is said to be kept, the pills are in front in both themes.
    device.get_by_role("button", name=re.compile(r"^Versions ")).tap()
    still = device.evaluate(STILL_JS)
    held["status"] = "queued"
    device.get_by_role("button", name="Nouvelle version").tap()
    device.get_by_role("button", name="Lancer la génération").tap()
    expect(words).to_contain_text("Votre demande est en attente.")
    check_still(device, still, "while a new version is queued at 360 px")
    held["status"] = "running"
    expect(words).to_contain_text("Votre affiche prend forme.")
    check_still(device, still, "while a new version runs at 360 px", samples=6)
    expect(badge).to_contain_text("Version précédente conservée")
    # The compact phone badge shows its version number on one line; screen readers hear that it is kept.
    assert badge.bounding_box()["height"] <= 30, badge.bounding_box()
    expect(block).to_be_in_viewport()
    assert topmost(pill) and topmost(badge)
    # One voice at a time: while the waiting block speaks, the coach line is not a live region.
    expect(device.locator(".coach[role=status]")).to_have_count(0)
    for theme, scheme in (("sombre", "dark"), ("clair", "light")):
        waiting_checks(device, "new version at 360 px", theme, scheme)
        check_targets(device, f"new version at 360 px, {theme}")
        shot(device, f"wait-360-{theme}.png", full_page=False)
    # After 100 s of creation a sentence says it is long, still running, and useless to start again. The fake clock is
    # installed only now, so that it governs nothing else in this walk.
    waiting_checks(device, "new version at 360 px", "sombre", "dark")
    expect(words).not_to_contain_text("plus long que d’habitude")
    context.clock.install()
    device.clock.fast_forward("01:41")
    expect(words).to_contain_text("C’est plus long que d’habitude. La demande est toujours en cours : inutile de la relancer.")
    device.screenshot(path=str(OUTPUT / "wait-360-sombre-longue.png"))
    held["status"] = None
    alternative = device.get_by_role("dialog", name="Vérifier la fidélité du produit")
    expect(alternative).to_be_visible(timeout=30000)
    alternative.get_by_role("button", name="Tout est conforme, approuver").tap()
    device.get_by_role("dialog", name="Fidélité approuvée").get_by_role("button", name="Fermer").tap()
    expect(block).to_have_count(0)
    check_still(device, still, "after a new version at 360 px")
    assert len(scenes) == 2, scenes
    context.close()
    # 1366 × 768: the waiting block's state is in view under the poster, which keeps its size, in both themes.
    desk = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    watch(desk)
    screen = desk.new_page()
    screen.set_default_timeout(10000)
    screen.on("pageerror", lambda error: errors.append(str(error)))
    screen.goto(f"{ORIGIN}/#{poster}")
    screen.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(screen.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_enabled()
    still = screen.evaluate(STILL_JS)
    held["status"] = "queued"
    screen.get_by_role("button", name="Nouvelle version").click()
    screen.get_by_role("button", name="Lancer la génération").click()
    expect(screen.locator(".wait [role=status]")).to_contain_text("Votre demande est en attente.")
    check_still(screen, still, "while a new version is queued at 1366 px")
    held["status"] = "running"
    expect(screen.locator(".wait [role=status]")).to_contain_text("Votre affiche prend forme.")
    check_still(screen, still, "while a new version runs at 1366 px", samples=6)
    expect(screen.locator(".frame .badge")).to_have_text("Version précédente conservée")
    expect(screen.locator(".frame .badge .visually-hidden")).to_have_count(0)
    assert topmost(screen.locator(".frame .gen-pill")) and topmost(screen.locator(".frame .badge"))
    expect(screen.locator(".coach[role=status]")).to_have_count(0)
    for theme, scheme in (("clair", "light"), ("sombre", "dark")):
        waiting_checks(screen, "waiting at 1366 px", theme, scheme)
        # The poster keeps its size: under it the state, the time and the rail are in view; the steps may need a scroll.
        for part in (".wait strong", ".wait-time", ".wait-rail"):
            expect(screen.locator(part)).to_be_in_viewport(ratio=1)
        shot(screen, f"wait-1366-{theme}.png", full_page=False)
    held["status"] = None
    expect(screen.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
    assert len(scenes) == 3, scenes
    expect(screen.locator(".coach[role=status]")).to_have_count(1)
    # A refusal of the poll does not change by asking again: on a session that ended the editor stops following and the
    # sign-in takes the screen, the shop's content hidden (D-MULTI-SHOP-007 rule 3); it never polls again nor starts
    # another generation.
    screen.get_by_role("dialog", name="Vérifier la fidélité du produit").get_by_role("button", name="Fermer").click()
    check_still(screen, still, "after a new version at 1366 px")
    # « Annuler la demande »: the cancellation's answer says the credit is back, which is said, and the balance is read
    # again (T-BALANCE-006 review r1). The scheduler claims a queued job within a second, so a real one cannot be cancelled
    # from here: the job is held at « queued » and the answer is the server's for a queued job (its view with status
    # cancelled and its credit given back, test_poster_jobs.py), while the real job runs and ends behind.
    balance_reads = []
    screen.on("request", lambda request: balance_reads.append(request.url) if request.url.endswith("/api/balance") else None)
    screen.route("**/api/jobs/*/cancel", lambda route: route.fulfill(json=screen.request.get(route.request.url.removesuffix("/cancel")).json()
                                                                     | {"status": "cancelled", "credit": "given_back"}))
    held["status"] = "queued"
    screen.get_by_role("button", name="Nouvelle version").click()
    screen.get_by_role("button", name="Lancer la génération").click()
    expect(screen.locator(".wait [role=status]")).to_contain_text("Votre demande est en attente.")
    reads = len(balance_reads)
    screen.get_by_role("button", name="Annuler la demande").click()
    expect(screen.locator(".message.notice")).to_contain_text("Votre crédit vous a été rendu.")
    expect(screen.locator(".wait")).to_have_count(0)
    for _ in range(50):  # the real job ends before the next request: one image at a time per poster
        jobs = screen.request.get(f"{ORIGIN}/api/creations/{poster}/jobs").json()["items"]
        if len(balance_reads) > reads and not any(job["status"] in ("queued", "running") for job in jobs):
            break
        screen.wait_for_timeout(200)
    else:
        raise AssertionError(("no balance read after the cancellation, or the job still runs", balance_reads[reads:]))
    screen.unroute("**/api/jobs/*/cancel")
    held["status"] = "running"
    screen.get_by_role("button", name="Nouvelle version").click()
    screen.get_by_role("button", name="Lancer la génération").click()
    expect(screen.locator(".wait [role=status]")).to_contain_text("Votre affiche prend forme.")
    held["signed_out"] = True
    expect(screen.get_by_label("Mot de passe", exact=True)).to_be_visible()
    expect(screen.locator("main:not(.gate)")).to_have_count(0)  # signed out: the shop's screen leaves (D-REDESIGN-002 r1)
    expect(screen.locator(".wait")).to_have_count(0)
    asked = len(polls)
    screen.wait_for_timeout(3000)
    assert len(polls) == asked and len(scenes) == 5, (polls[asked:], scenes)
    desk.close()
    # The elapsed time rests on what the real answers carried: UTC stamps with their offset, the server's Date header.
    assert stamps and all(re.search(r"\+00:00$", created) and (started is None or re.search(r"\+00:00$", started)) and date
                          for created, started, date in stamps), stamps


# Records whether the top progress line was ever on screen from now on.
LINE_SEEN_JS = "() => { window.lineSeen = !!document.querySelector('.load-line'); new MutationObserver(() => { if (document.querySelector('.load-line')) window.lineSeen = true }).observe(document.body, { childList: true, subtree: true }) }"
# A control answers a press at once and shows it is working (R-POSTER-EDITOR-009): aria-busy, the spinner after 120 ms,
# the top line after 300 ms of waiting. Times are taken in the page from the press.
PRESSED_JS = "() => { window.pressedAt = null; addEventListener('pointerdown', () => { window.pressedAt ??= performance.now() }, { capture: true, once: true }) }"
WORKING_JS = """e => e.getAttribute('aria-busy') === 'true' && getComputedStyle(e, '::after').opacity === '1' && !!document.querySelector('.load-line')
  && performance.now() - window.pressedAt"""
LAYOUT_JS = "e => [e.offsetWidth, e.offsetHeight]"


def check_working(page, control, held, posts, where, picture, *also, sized=True):
    """With the request held: the control works within 300 ms (the line from 300 ms on, so 450 ms for it), a second tap
    sends nothing, nothing changes size; once released no control is still working and the line is gone."""
    sizes = [item.evaluate(LAYOUT_JS) for item in ((control,) if sized else ()) + also]
    page.evaluate(PRESSED_JS)
    control.tap()
    page.wait_for_function("() => document.querySelector('[aria-busy=true]:is(button, a)')", polling=10, timeout=300)
    took = page.wait_for_function(WORKING_JS, arg=control.element_handle(), polling=10, timeout=1000).json_value()
    assert took < 450, f"{where}: working after {took:.0f} ms"
    assert page.locator(".load-line").get_attribute("role") == "progressbar"
    page.screenshot(path=str(OUTPUT / picture))  # not shot(): the spinner's start never settles while it works
    scheme = "dark" if page.evaluate("matchMedia('(prefers-color-scheme: dark)').matches") else "light"
    # The line against what is under it, in both themes: moving (held half-way), then still (D-POLISH-002).
    for other in ("light", "dark"):
        page.emulate_media(color_scheme=other)
        page.wait_for_function("theme => document.documentElement.dataset.theme === theme", arg="clair" if other == "light" else "sombre")
        for motion in ("no-preference", "reduce"):
            page.emulate_media(reduced_motion=motion)
            check_marks(page, f"{where}, {other}, motion {motion}", ".load-line span", show=True)
    page.emulate_media(color_scheme=scheme, reduced_motion="no-preference")
    count = len(posts)
    control.tap(force=True)  # disabled, or the same address: nothing new is asked
    page.wait_for_timeout(300)
    assert len(posts) == count, f"{where}: a second tap sent {posts[count:]}"
    assert [item.evaluate(LAYOUT_JS) for item in ((control,) if sized else ()) + also] == sizes, f"{where}: a size changed"
    while held:
        held.pop().continue_()
    expect(page.locator("[aria-busy=true]:is(button, a)")).to_have_count(0)
    expect(page.locator(".load-line")).to_have_count(0)


def pressed_look(page, cdp, selector, reduced=False, read=None):
    """The computed look of an element with :active forced through the DevTools protocol (or what `read` returns then)."""
    page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
    root = cdp.send("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
    node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})["nodeId"]
    assert node, selector
    cdp.send("CSS.forcePseudoState", {"nodeId": node, "forcedPseudoClasses": ["active"]})
    try:  # a failed reading must not leave the press or the media forced for the checks after it
        if not reduced:
            page.wait_for_timeout(300)  # past the 160 ms ease; reduced motion has no transition
        return read() if read else page.eval_on_selector(selector, "e => [getComputedStyle(e).transform, getComputedStyle(e).opacity, getComputedStyle(e).backgroundColor]")
    finally:
        cdp.send("CSS.forcePseudoState", {"nodeId": node, "forcedPseudoClasses": []})
        page.emulate_media(reduced_motion="no-preference")


def walk_tap(browser, session, errors):
    """Every tap answers at once, a slow action shows it is working (R-POSTER-EDITOR-009, D-POSTER-EDITOR-007), at 360 px
    on a touch screen: « Dupliquer », opening a poster, a bottom navigation link, each with its request held; the press
    itself through a forced :active. Pictures tap-*.png."""
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    held, posts = [], []
    page.on("request", lambda request: posts.append(request.url) if "/api/" in request.url and not re.search("/api/(assets|thumbnails)/", request.url) else None)
    page.goto(f"{ORIGIN}/#affiches")
    rows = page.locator(".library-row")
    expect(rows.first).to_be_visible()
    count = rows.count()
    # « Dupliquer » (the user's report): its POST held.
    page.route("**/api/creations/*/copies", lambda route: held.append(route))
    rows.first.get_by_role("button", name=re.compile("^Actions pour")).tap()
    duplicate = rows.first.get_by_role("button", name=re.compile("^Dupliquer"))
    check_working(page, duplicate, held, posts, "« Dupliquer »", "tap-360-sombre-dupliquer.png", rows.first, page.locator(".rows"))
    page.unroute("**/api/creations/*/copies")
    assert sum(url.endswith("/copies") for url in posts) == 1, posts
    expect(page.locator(".poster-title")).to_be_visible()
    # Leaving the editor asks for the gallery's active page. Hold that read to check the link's busy state.
    page.set_viewport_size({"width": 1366, "height": 768})
    listing = "**/api/creations?limit=50&status=active"
    page.route(listing, lambda route: held.append(route))
    check_working(page, page.locator("aside.side .nav a", has_text="Mes affiches"), held, posts, "the sidebar's navigation link at 1366 px", "tap-1366-sombre-navigation.png", sized=False)
    page.unroute(listing)
    expect(rows).to_have_count(count + 1)
    page.set_viewport_size({"width": 360, "height": 740})
    # Opening a poster from « Mes affiches »: its GET held.
    opened = rows.nth(1).locator(".library-item")
    page.route(re.compile(r"/api/creations/[0-9a-f-]{36}$"), lambda route: held.append(route) if route.request.method == "GET" else route.continue_())
    check_working(page, opened, held, posts, "a row of « Mes affiches »", "tap-360-sombre-ouvrir.png", page.locator(".rows"))
    page.unroute(re.compile(r"/api/creations/[0-9a-f-]{36}$"))
    expect(page.locator(".poster-title")).to_be_visible()
    return_to_work(page)
    shot(page, "tap-360-sombre-ouverte.png", full_page=False)
    # The press: scale .97 at once on a button, a link, a tab; a row of the list takes a colour step instead; nothing on a
    # disabled button; with reduced motion a change of opacity, not of size.
    cdp = context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    scaled = "matrix(0.97, 0, 0, 0.97, 0, 0)"
    tab = ".rail [role=tab][aria-selected=false]"
    expect(page.locator(tab).first).to_be_visible()
    undo = "button[aria-label=Annuler]"
    expect(page.locator(undo)).to_be_disabled()
    assert pressed_look(page, cdp, undo)[0] == "none"
    # With reduced motion the pressed main button wears a ring of the line colour (D-POLISH-002), in both themes.
    main = ".main-action button.primary"
    expect(page.locator(main)).to_be_enabled()
    for scheme, theme in (("light", "clair"), ("dark", "sombre")):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
        pressed_look(page, cdp, main, reduced=True, read=lambda: check_marks(page, f"pressed main button, {theme}", main, marks=[[main, "boxShadow", "parent", 3]]))
    for where in ("editor", "list"):
        if where == "list":
            page.locator(".back-link").tap()
            expect(rows).to_have_count(count + 1)
        for selector in ((tab,) if where == "editor" else (".phone-bar a:not([aria-current])", ".row-options")):
            assert pressed_look(page, cdp, selector)[0] == scaled, selector
            resting = page.eval_on_selector(selector, "e => getComputedStyle(e).backgroundColor")
            reduced = pressed_look(page, cdp, selector, reduced=True)
            assert reduced[0] == "none" and reduced[2] != resting, (selector, reduced, resting)  # a colour step, no size
    resting = page.eval_on_selector(".library-item", "e => getComputedStyle(e).backgroundColor")
    row = pressed_look(page, cdp, ".library-item")
    assert row[0] == "none" and row[2] != resting, (row, resting)
    for scheme, theme in (("dark", "sombre"), ("light", "clair")):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
        check_contrast(page, f"Mes affiches at 360 px after the taps, {theme}")
    context.close()


def walk_words(browser, session, errors):
    """One poster's words never reach the next one (T-BLANK-WORDS, user report 2026-11-14): poster A is made with a brand,
    a subtitle and an accent word; poster B, made next from the form, starts blank and its scene request carries none of
    them; A reopened shows its own words again. Typed before the first version, the words survive a reload (T-KEEP-WORDS):
    they are kept in the browser under the poster's own id until its version carries them."""
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    scenes = []
    page.on("request", lambda request: scenes.append(request.post_data_json) if request.method == "POST" and request.url.endswith("/scenes") else None)
    brand, subtitle = page.get_by_label("Marque (facultative)"), page.get_by_label("Sous-titre (facultatif)")
    words = page.get_by_role("group", name="Mot du titre en couleur").get_by_role("button")
    review = page.get_by_role("heading", name="Vérifier votre affiche")

    def make(name, price):
        expect(page.get_by_label("Photos du produit")).to_be_enabled()  # the way to « Créer » is over (perform drops a busy tap)
        page.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
        expect(page.locator(".photo-strip img")).to_have_count(1)
        page.get_by_label("Nom du produit", exact=True).fill(name)
        page.get_by_label("Prix en ariary", exact=True).fill(price)
        page.get_by_label("Les photos correspondent").check()
        page.get_by_role("button", name="Préparer mon affiche").click()
        expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
        page.get_by_role("tab", name="Textes", exact=True).click()

    def generate():
        page.get_by_role("button", name="Générer l’affiche").click()
        page.get_by_role("button", name="Lancer la génération").click()
        expect(review).to_be_visible(timeout=30000)
        download_review(page)
        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
        expect(page.get_by_role("tab")).to_have_count(4)

    kept = "id => JSON.parse(localStorage.getItem('affiche.shop1.words.' + id))"

    page.goto(ORIGIN + "/#etapes")
    make("Casque Alpha", "120 000")
    brand.fill("MarqueAlpha")
    subtitle.fill("SOUS-TITRE ALPHA")
    words.filter(has_text="Casque").click()
    expect(words.filter(has_text="Casque")).to_have_attribute("aria-pressed", "true")
    poster_a = page.url.split("#")[1]
    # Not generated yet: the words are in the browser, under this poster's id, with nothing else of the poster.
    page.wait_for_function("id => localStorage.getItem('affiche.shop1.words.' + id)?.includes('Casque')", arg=poster_a)
    entry = page.evaluate(kept, poster_a)
    assert (entry["brand"], entry["subtitle"], entry["accent_word"]) == ("MarqueAlpha", "SOUS-TITRE ALPHA", "Casque"), entry
    assert sorted(entry) == ["accent_colour", "accent_word", "at", "brand", "brand_text", "contact", "on", "price", "subtitle"], entry
    assert not re.search("120|034|phone-noir", json.dumps(entry | {"at": 0})), entry
    page.reload()
    expect(page.get_by_role("heading", name="Casque Alpha", exact=True)).to_be_visible()
    page.get_by_role("tab", name="Textes", exact=True).click()
    expect(brand).to_have_value("MarqueAlpha")
    expect(subtitle).to_have_value("SOUS-TITRE ALPHA")
    expect(words.filter(has_text="Casque")).to_have_attribute("aria-pressed", "true")
    assert not scenes, scenes
    generate()
    assert len(scenes) == 1, scenes
    assert (scenes[-1]["headline"]["brand"], scenes[-1]["headline"]["subtitle"], scenes[-1]["headline"]["accent_word"]) == ("MarqueAlpha", "SOUS-TITRE ALPHA", "Casque"), scenes[-1]
    # The form waits for the next product: nothing of A's photos, name, price or agreement is left in it.
    go(page, "Nouvelle affiche")
    expect(page.locator(".photo-strip img")).to_have_count(0)
    expect(page.get_by_label("Nom du produit", exact=True)).to_have_value("")
    expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("")
    expect(page.get_by_label("Variante confirmée")).to_have_value("Conforme à la photo")
    expect(page.get_by_label("Les photos correspondent")).not_to_be_checked()
    # The version carries A's words now: its entry is gone.
    assert page.evaluate(kept, poster_a) is None, page.evaluate(kept, poster_a)
    make("Enceinte Beta", "80 000")
    expect(brand).to_have_value("")
    expect(subtitle).to_have_value("")
    expect(words.filter(has_text="Aucun")).to_have_attribute("aria-pressed", "true")
    asked = len(scenes)
    generate()
    sent = scenes[asked]
    assert (sent["headline"]["brand"], sent["headline"]["subtitle"], sent["headline"]["accent_word"]) == (None, None, None), sent
    assert not re.search("Alpha|ALPHA|Casque", json.dumps(sent)), sent
    # A reopened poster brings back the words its version was made with.
    page.goto(f"{ORIGIN}/#{poster_a}")
    page.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(page.get_by_role("heading", name="Casque Alpha", exact=True)).to_be_visible()
    expect(brand).to_have_value("MarqueAlpha")
    expect(subtitle).to_have_value("SOUS-TITRE ALPHA")
    expect(words.filter(has_text="Casque")).to_have_attribute("aria-pressed", "true")
    # The same after a reload, from the version alone: nothing of A is in the browser's storage.
    page.reload()
    page.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(page.get_by_role("heading", name="Casque Alpha", exact=True)).to_be_visible()
    expect(brand).to_have_value("MarqueAlpha")
    expect(subtitle).to_have_value("SOUS-TITRE ALPHA")
    expect(words.filter(has_text="Casque")).to_have_attribute("aria-pressed", "true")
    assert not page.evaluate("() => Object.keys(localStorage).some(key => key.startsWith('affiche.shop1.words.') && /Alpha|ALPHA|Casque/.test(localStorage.getItem(key)))")
    assert page.evaluate(kept, poster_a) is None
    context.close()


BOX_JS = "e => { const b = e.getBoundingClientRect(); return [b.width, b.height] }"
# Resolves once scrollY has not changed for six frames in a row.
STILL_SCROLL = "() => new Promise(done => { let last = -1, still = 0; const tick = () => { still = scrollY === last ? still + 1 : 0; last = scrollY; if (still > 5) done(); else requestAnimationFrame(tick) }; tick() })"


def check_shape(locator, ratio, where):
    width, height = locator.evaluate(BOX_JS)
    assert height and abs(width / height - ratio) / ratio < .02, f"{where}: {width} x {height}, not {ratio:.4f}"
    return width, height


def return_to_work(page):
    # A cold open can resume a previous file; switching views in this tab can keep the editor open.
    page.wait_for_load_state("networkidle")
    panel = page.locator(".final-preview")
    if panel.is_visible():
        panel.get_by_role("button", name="Fermer").tap()


def check_file_actions(panel, *actions):
    """On a short phone the seller can scroll from the image to every output and focus it."""
    for action in actions:
        action.scroll_into_view_if_needed()
        expect(action).to_be_in_viewport(ratio=1)
        assert topmost(action), action.inner_text()
        action.focus()
        expect(action).to_be_focused()
    panel.evaluate("el => el.scrollTo({top: 0, behavior: 'instant'})")


def download_review(page):
    """One decision downloads the exact visible PNG. The confirmed file can be reopened."""
    panel = page.locator(".final-preview")
    image = panel.locator(".shot img")
    expect(image).to_be_visible(timeout=30000)
    rendered = page.request.get(image.evaluate("el => el.src"), fail_on_status_code=True).body()
    with page.expect_download() as download:
        panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    assert download.value.path().read_bytes() == rendered
    expect(panel.get_by_role("heading", name="Affiche confirmée")).to_be_visible()


def walk_formats(browser, errors):
    """Three formats enabled (FORMATS_ENABLED=feed,square,story; T-FMT-005, T-FMT-006, ADR-080), on an API of its own.
    The format is chosen in « Style » only: a Story and a Square poster go to their confirmed PNG at their own size; a 9:16
    model asks on a Publication poster, « Utiliser Story » changes the saved format, « Garder Publication » is remembered,
    a 3:4 or a landscape model asks nothing; a refused format change reloads the stored poster; a version locks the format
    and « Refaire en Story » makes a new poster of the same product. Then each shape at 360 × 740 and 1366 × 768, both
    themes (format-*.png)."""
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(ORIGIN + "/#etapes")
    page.get_by_label("Identifiant de la boutique", exact=True).fill(IDENTIFIER)
    page.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Ouvrir l’atelier").click()
    expect(page.get_by_label("Photos du produit")).to_be_enabled()
    get = lambda path: page.request.get(ORIGIN + path).json()
    here = lambda: page.url.split("#")[1]
    saved = lambda: get(f"/api/creations/{here()}")["document"]

    def until(check):
        for _ in range(50):
            if check():
                return
            page.wait_for_timeout(200)
        raise AssertionError("condition not reached")

    formats = page.get_by_role("radiogroup", name="Format")
    page_format_hint = page.locator("#aide-format")
    radio = lambda name: formats.get_by_role("radio", name=name, exact=True)
    question = page.locator(".format-ask")
    sizes = {"feed": (1080, 1350), "square": (1080, 1080), "story": (1080, 1920)}
    scene_sizes = {"feed": "1088x1360", "square": "1088x1088", "story": "1152x2048"}
    # One place to choose: the intake form has no format.
    expect(formats).to_have_count(0)
    assert get("/api/capabilities")["formats_enabled"] == ["feed", "square", "story"]

    def make(name):
        go(page, "Nouvelle affiche")
        expect(page.get_by_label("Photos du produit")).to_be_enabled()  # the way back from a poster is over
        page.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
        expect(page.locator(".photo-strip img")).to_have_count(1)
        page.get_by_label("Nom du produit", exact=True).fill(name)
        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
        page.get_by_label("Les photos correspondent").check()
        page.get_by_role("button", name="Préparer mon affiche").click()
        expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
        expect(page.get_by_role("tab", name="Style", exact=True)).to_have_attribute("aria-selected", "true")
        # A new poster starts in Publication; the three formats are offered.
        expect(formats.get_by_role("radio")).to_have_count(3)
        expect(radio("Publication 4:5")).to_be_checked()
        expect(page_format_hint).to_contain_text("Gardez Publication pour télécharger le PNG ou publier directement sur votre Page Facebook.")
        assert saved()["primary_format"] == "feed"

    def choose(name, value):
        radio(name).check()
        until(lambda: saved()["primary_format"] == value)
        layouts = saved()["formats"]
        assert list(layouts) == [value] and layouts[value]["scene"]["visual_id"] is None, layouts
        expect(page.locator(".bar .format")).to_contain_text(f"{name.split()[0]} · {sizes[value][0]} × {sizes[value][1]}")
        expect(page.get_by_role("region", name="Offre à générer")).to_contain_text(name.split()[0])

    def running(route):
        response = route.fetch()
        body = response.json()
        if body["kind"] in ("scene", "refine"):
            body.update(status="running", result_ref=None, error_code=None, finished_at=None)
        route.fulfill(response=response, json=body)

    def generate(check_file=False):
        page.get_by_role("button", name="Générer l’affiche").click()
        page.get_by_role("button", name="Lancer la génération").click()
        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)
        if check_file:
            return
        download_review(page)
        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
        expect(page.get_by_role("tab")).to_have_count(4)

    def confirm(value):
        size = sizes[value]
        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=40000)
        expect(page.locator(".final-preview .facts")).to_contain_text(f"{size[0]} × {size[1]} px")
        preview = page.locator(".final-preview .shot img")
        page.wait_for_function("e => e.complete && e.naturalWidth > 0", arg=preview.element_handle())
        assert preview.evaluate("e => [e.naturalWidth, e.naturalHeight]") == list(size)
        check_shape(preview, size[0] / size[1], f"final preview of {value} at 1366 px")
        page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
        link = page.get_by_role("link", name="Télécharger le PNG")
        expect(link).to_be_visible()
        png = page.request.get(ORIGIN + link.get_attribute("href")).body()
        assert Image.open(io.BytesIO(png)).size == size, Image.open(io.BytesIO(png)).size
        (OUTPUT / f"format-{value}-confirmed.png").write_bytes(png)
        page.locator(".final-preview").get_by_role("button", name="Fermer").click()

    def tab(name):
        page.get_by_role("tab", name=name, exact=True).click()
        expect(page.get_by_role("tab", name=name, exact=True)).to_have_attribute("aria-selected", "true")

    locked_sentence = page.get_by_text("Le format ne change plus après la première version : le titre, le prix et le contact sont dessinés dans une image à cette taille.")
    posters = {}
    # A Story and a Square poster, chosen in « Style », generated with the stub, checked, confirmed, downloaded.
    for value, name, title in (("story", "Story 9:16", "Enceinte Story"), ("square", "Carré 1:1", "Enceinte Carré")):
        make(title)
        choose(name, value)
        expect(locked_sentence).to_have_count(0)
        generate(check_file=True)
        if value == "square":
            unchanged = get(f"/api/creations/{here()}")
            page.get_by_role("button", name="Corriger l’affiche").click()
            assert get(f"/api/creations/{here()}") == unchanged and unchanged["confirmation"] is None
            assert get(f"/api/creations/{here()}/visuals")["items"][0]["status"] == "pending_review"
            page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
        confirm(value)
        # The version has the format's own scene size.
        assert [visual["size"] for visual in get(f"/api/creations/{here()}/visuals")["items"]] == [scene_sizes[value]]
        # A version fixes the format: the group says why and offers the other formats as new posters.
        tab("Style")
        expect(radio(name)).to_be_checked()
        expect(radio(name)).to_be_disabled()
        expect(radio("Publication 4:5")).to_be_disabled()
        expect(locked_sentence).to_be_visible()
        others = [label for key, label in (("feed", "Publication"), ("square", "Carré"), ("story", "Story")) if key != value]
        expect(page.get_by_role("button", name=re.compile("^Refaire en "))).to_have_text([f"Refaire en {label}" for label in others])
        posters[value] = here()

    # Once a scene of this size is on its way, undo stops before the format step (v2 point 8). On a poster of its own, left
    # afterwards: an edit saved during the first generation meets the revision the server writes when the scene arrives.
    make("Essai annuler")
    choose("Carré 1:1", "square")
    page.route("**/api/jobs/*", running)
    page.get_by_role("button", name="Générer l’affiche").click()
    page.get_by_role("button", name="Lancer la génération").click()
    expect(page.locator(".wait [role=status]")).to_contain_text("Votre affiche prend forme.")
    undo, undone = page.get_by_role("button", name="Annuler", exact=True), 0
    while undo.is_enabled():
        undo.click()
        undone += 1
    assert undone, "nothing to undo"
    expect(page.locator(".bar .format")).to_contain_text("Carré · 1080 × 1080")
    expect(radio("Carré 1:1")).to_be_checked()
    expect(page_format_hint).to_contain_text("Carré permet de télécharger votre affiche en PNG.")
    page.unroute("**/api/jobs/*", running)
    # Undo left the returned scene unselected. Inspecting it must not silently apply it.
    alternative = page.get_by_role("dialog", name="Vérifier la fidélité du produit")
    expect(alternative.get_by_role("button", name="Choisir cette version")).to_be_visible(timeout=30000)
    page.reload()
    expect(page.get_by_role("heading", name="Essai annuler", exact=True)).to_be_visible()
    assert saved()["primary_format"] == "square"

    # The model's shape. Files made here: two 9:16 ones (different pixels, so two assets) and a landscape one.
    models = {}
    for key, size, colour in (("story-a", (900, 1600), (30, 60, 140)), ("story-b", (720, 1280), (140, 60, 30)), ("story-c", (1080, 1920), (40, 120, 60)), ("landscape", (1600, 900), (90, 90, 90))):
        models[key] = OUTPUT / f"model-{key}.png"
        Image.new("RGB", size, colour).save(models[key])
    picker = page.get_by_label("Affiche modèle")

    def pick_model(path):
        with page.expect_response("**/api/assets"):
            picker.set_input_files(path)
        page.wait_for_function("!document.querySelector('.new-look input[type=file]').disabled")

    asks = "Votre modèle est au format Story (9:16). Utiliser ce format pour l’affiche ?"
    # The section may stay open from an earlier visit of « Style »: opened, never toggled.
    open_models = lambda: page.locator("details.new-look").evaluate("e => { e.open = true }")
    make("Casque modèle")
    open_models()
    # A 3:4 model counts as Publication: nothing to ask on a Publication poster.
    pick_model(ROOT / "backend/fixtures/examples/phone-noir.jpg")
    expect(question).to_have_count(0)
    pick_model(models["story-a"])
    expect(question.get_by_role("status")).to_have_text(asks)
    expect(question.get_by_role("button")).to_have_text(["Utiliser Story", "Garder Publication"])
    check_one_blur(page, "the format question at 1366 px")
    check_contrast(page, "the format question at 1366 px")
    question.scroll_into_view_if_needed()
    shot(page, "format-question-1366-clair.png", full_page=False)
    question.get_by_role("button", name="Garder Publication").click()
    expect(question).to_have_count(0)
    assert saved()["primary_format"] == "feed"
    # A landscape model asks nothing; the declined one, picked again, asks nothing on this poster (the same file twice in a
    # row fires no change: another file goes between).
    pick_model(models["landscape"])
    expect(question).to_have_count(0)
    pick_model(models["story-a"])
    expect(question).to_have_count(0)
    pick_model(models["story-b"])
    expect(question.get_by_role("status")).to_have_text(asks)
    question.get_by_role("button", name="Utiliser Story").click()
    expect(question).to_have_count(0)
    until(lambda: saved()["primary_format"] == "story")
    expect(radio("Story 9:16")).to_be_checked()
    expect(page_format_hint).to_contain_text("Story permet de télécharger votre affiche en PNG.")
    expect(page.locator(".bar .format")).to_contain_text("Story · 1080 × 1920")
    # A style saved from that model is picked: it is Story already, nothing to ask.
    page.get_by_label("Nom du style").fill("Modèle Story")
    page.get_by_role("button", name="Enregistrer ce style").click()
    page.get_by_role("button", name="Créer le style").click()
    expect(page.get_by_text("Style « Modèle Story » enregistré", exact=False)).to_be_visible(timeout=15000)
    look = get("/api/looks")["items"][0]
    assert (look["reference_width"], look["reference_height"]) == (720, 1280), look
    expect(question).to_have_count(0)
    # Back to Publication, the saved style is picked again: it asks, under the styles; « Garder » is remembered there too.
    choose("Publication 4:5", "feed")
    page.get_by_role("button", name="Modèle Story", exact=True).click()
    expect(question.get_by_role("status")).to_have_text(asks)
    assert question.evaluate("e => !!e.previousElementSibling?.matches('.look-grid')")
    question.get_by_role("button", name="Garder Publication").click()
    page.get_by_role("button", name="Studio clair", exact=True).click()
    page.get_by_role("button", name="Modèle Story", exact=True).click()
    expect(question).to_have_count(0)
    assert saved()["primary_format"] == "feed"
    # A format change the server refuses (a version made meanwhile elsewhere): the stored poster comes back, with the reason.
    poster = here()

    def refuse(route):
        if route.request.method != "PUT":
            return route.continue_()
        route.fulfill(status=409, json={"error": {"code": "format_locked", "retryable": False,
                      "message_fr": "Le format ne change plus après la première version : le titre, le prix et le contact sont dessinés dans une image à cette taille."}})
    page.route(f"**/api/creations/{poster}", refuse)
    radio("Story 9:16").check()
    expect(page.locator(".message.error")).to_contain_text("Vos dernières modifications n’ont pas été enregistrées : l’affiche enregistrée a été rechargée.")
    expect(radio("Publication 4:5")).to_be_checked()
    expect(page.locator(".bar .format")).to_contain_text("Publication · 1080 × 1350")
    page.unroute(f"**/api/creations/{poster}", refuse)
    page.locator(".message.error").get_by_role("button", name="Fermer").click()
    assert saved()["primary_format"] == "feed"
    expect(page.locator(".bar .meta [role=status]")).to_have_text("Enregistré")
    expect(page.get_by_role("button", name="Générer l’affiche")).to_be_enabled()
    tab("Style")
    generate()
    # With a version: a model of another shape is only said to differ; the poster keeps its format.
    tab("Style")
    open_models()
    pick_model(models["story-c"])
    expect(question.get_by_role("status")).to_have_text("Ce modèle est au format Story. Cette affiche garde son format : il se choisit avant la première version.")
    expect(question.get_by_role("button")).to_have_text(["Fermer"])
    expect(locked_sentence).to_be_visible()
    expect(formats).to_have_attribute("aria-describedby", "aide-format format-lock")
    expect(locked_sentence).to_have_attribute("id", "format-lock")
    question.scroll_into_view_if_needed()
    shot(page, "format-question-locked-1366-clair.png", full_page=False)
    question.get_by_role("button", name="Fermer").click()
    expect(question).to_have_count(0)
    source_input = saved()["input_id"]
    assert [visual["size"] for visual in get(f"/api/creations/{poster}/visuals")["items"]] == [scene_sizes["feed"]]
    # « Refaire en Story » whose last step fails (the copy's format change is refused once): the copy made is opened and
    # said, in Publication, its title a layer again, its format free in « Style »; the source is untouched.
    failed = []

    def fail_once(route):
        if route.request.method != "PUT" or failed or poster in route.request.url:
            return route.continue_()
        failed.append(route.request.url)
        route.fulfill(status=503, json={"error": {"code": "service_down", "message_fr": "Le service est momentanément indisponible.", "retryable": True}})
    page.route("**/api/creations/*", fail_once)
    page.get_by_role("button", name="Refaire en Story", exact=True).click()
    page.wait_for_function(f"location.hash !== '#{poster}'")
    expect(page.locator(".message.error")).to_contain_text("Une copie au format Publication a été créée, sans version, mais elle n’a pas pu passer au format Story (Le service est momentanément indisponible.). Choisissez son format dans « Style ».")
    assert len(failed) == 1 and here() in failed[0], failed
    page.unroute("**/api/creations/*", fail_once)
    expect(radio("Publication 4:5")).to_be_checked()
    expect(radio("Publication 4:5")).to_be_focused()
    expect(radio("Story 9:16")).to_be_enabled()
    until(lambda: all(layer["visible"] for layer in saved()["formats"]["feed"]["layers"] if layer["role"] in ("title", "price")))
    assert saved()["input_id"] != source_input and get(f"/api/creations/{here()}/visuals")["items"] == []
    assert next(layer for layer in get(f"/api/creations/{poster}")["document"]["formats"]["feed"]["layers"] if layer["role"] == "title")["visible"] is False
    page.locator(".message.error").get_by_role("button", name="Fermer").click()
    page.goto(f"{ORIGIN}/#{poster}")
    page.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(page.get_by_role("tab")).to_have_count(4)
    tab("Style")
    page.get_by_role("button", name="Refaire en Story", exact=True).click()
    page.wait_for_function(f"location.hash !== '#{poster}'")
    expect(page.locator(".message.notice")).to_contain_text("Nouvelle affiche au format Story")
    remade = saved()
    assert remade["primary_format"] == "story" and list(remade["formats"]) == ["story"], remade
    assert remade["input_id"] != source_input and remade["offer"]["title"] == "Casque modèle"
    assert remade["formats"]["story"]["scene"]["visual_id"] is None
    assert get(f"/api/creations/{here()}/visuals")["items"] == []
    product = get(f"/api/product-inputs/{remade['input_id']}")
    assert (product["name"], product["photo_assets"]) == (get(f"/api/product-inputs/{source_input}")["name"], get(f"/api/product-inputs/{source_input}")["photo_assets"])
    expect(page.get_by_role("tab", name="Style", exact=True)).to_have_attribute("aria-selected", "true")
    expect(radio("Story 9:16")).to_be_checked()
    expect(radio("Story 9:16")).to_be_enabled()
    expect(radio("Story 9:16")).to_be_focused()
    expect(locked_sentence).to_have_count(0)
    # The poster left behind is unchanged: Publication, its version kept.
    source = get(f"/api/creations/{poster}")["document"]
    assert source["primary_format"] == "feed" and [visual["size"] for visual in get(f"/api/creations/{poster}/visuals")["items"]] == [scene_sizes["feed"]]
    posters["remade"] = here()
    session = {"cookies": context.storage_state()["cookies"], "origins": []}
    context.close()

    # Shapes (T-FMT-006): each poster in its own shape at 360 × 740 (touch) and 1366 × 768, light and dark: the confirmed
    # file (shown on opening), the poster, the versions strip and its « Nouvelle version » tile, the locked « Style » tab,
    # on a phone the large view; the library's thumbnails; a draft Story on the preparation screen.
    ratios, titles = {"story": 1080 / 1920, "square": 1.0}, {"story": "Enceinte Story", "square": "Enceinte Carré"}
    for width, height in ((360, 740), (1366, 768)):
        phone = width == 360
        view = browser.new_context(viewport={"width": width, "height": height}, is_mobile=phone, has_touch=phone, color_scheme="light", storage_state=session)
        screen = view.new_page()
        screen.set_default_timeout(10000)
        screen.on("pageerror", lambda error: errors.append(str(error)))
        press = (lambda locator: locator.tap()) if phone else (lambda locator: locator.click())
        for theme, scheme in (("clair", "light"), ("sombre", "dark")):
            screen.emulate_media(color_scheme=scheme)
            for value in ("story", "square"):
                ratio, where = ratios[value], f"{value} at {width} px, {theme}"
                screen.goto(f"{ORIGIN}/#{posters[value]}")
                screen.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
                final = screen.locator(".final-preview")
                expect(final.get_by_role("heading", name="Affiche confirmée")).to_be_visible()
                image = final.locator(".shot img")
                screen.wait_for_function("e => e.complete && e.naturalWidth > 0", arg=image.element_handle())
                assert check_shape(image, ratio, f"final preview, {where}")[1] <= height * .7 + 1
                check_one_blur(screen, f"final preview, {where}")
                check_contrast(screen, f"final preview, {where}")
                shot(screen, f"format-{value}-{width}-{theme}-final.png", full_page=False)
                press(final.get_by_role("button", name="Fermer"))
                expect(final).to_have_count(0)
                expect(screen.get_by_role("tab")).to_have_count(4)
                expect(screen.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_enabled()
                canvas = screen.locator(".poster-canvas canvas").first
                check_shape(canvas, ratio, f"poster, {where}")
                expect(canvas).to_be_in_viewport(ratio=1)
                if phone:
                    press(screen.get_by_role("button", name=re.compile(r"^Versions ")))
                thumb = check_shape(screen.locator(".version img").first, ratio, f"version, {where}")
                check_shape(screen.locator(".version.new .add"), ratio, f"« Nouvelle version », {where}")
                assert abs(thumb[1] - 70) < 1 if phone else thumb[1] <= 196, (where, thumb)
                if phone:
                    press(screen.get_by_role("button", name=re.compile(r"^Versions ")))
                    # The version's badge stays on the poster, in front, also on a Story's narrow one.
                    badge, poster = screen.locator(".frame .badge").bounding_box(), canvas.bounding_box()
                    assert badge["x"] + badge["width"] <= poster["x"] + poster["width"] + 1, (where, badge, poster)
                    assert topmost(screen.locator(".frame .badge"))
                screen.wait_for_function(NO_SIDEWAYS)
                check_one_blur(screen, f"editor, {where}")
                check_contrast(screen, f"editor, {where}")
                # The focus given back by the closed preview may still be scrolling the page (smoothly, and an instant scroll
                # does not stop it): once the page is still, it goes to the top for the picture.
                screen.evaluate(STILL_SCROLL)
                screen.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
                shot(screen, f"format-{value}-{width}-{theme}-editeur.png", full_page=False)
                press(screen.get_by_role("tab", name="Style", exact=True))
                expect(screen.get_by_text("Le format ne change plus après la première version", exact=False)).to_be_visible()
                screen.wait_for_function(NO_SIDEWAYS)
                check_one_blur(screen, f"Style tab, {where}")
                check_contrast(screen, f"Style tab, {where}")
                if phone:
                    check_targets(screen, f"Style tab, {where}")
                screen.locator(".format-choice").evaluate("e => e.scrollIntoView({ block: 'start', behavior: 'instant' })")
                shot(screen, f"format-{value}-{width}-{theme}-style.png", full_page=False)
                if phone:
                    press(screen.get_by_role("button", name="Voir l’affiche", exact=True))
                    sheet = screen.get_by_role("dialog", name="Affiche")
                    expect(sheet).to_be_visible()
                    screen.wait_for_function("document.querySelector('.stage.peek .poster-canvas canvas')?.getBoundingClientRect().width > 250")
                    check_shape(sheet.locator(".poster-canvas canvas").first, ratio, f"large view, {where}")
                    check_contrast(screen, f"large view, {where}")
                    shot(screen, f"format-{value}-{width}-{theme}-grand.png", full_page=False)
                    press(sheet.get_by_role("button", name="Revenir aux réglages"))
                    expect(screen.get_by_role("dialog")).to_have_count(0)
            # The library: each thumbnail whole, in its poster's shape, inside the same 64 × 80 place.
            screen.goto(f"{ORIGIN}/#affiches")
            expect(screen.get_by_role("heading", name="Mes affiches", exact=True)).to_be_visible()
            for value, title in titles.items():
                picture = screen.locator(".library-item", has_text=title).locator("img")
                screen.wait_for_function("e => e.complete && e.naturalWidth > 0", arg=picture.element_handle())
                natural = picture.evaluate("e => e.naturalWidth / e.naturalHeight")
                assert abs(natural - ratios[value]) / ratios[value] < .02 and picture.evaluate("e => getComputedStyle(e).objectFit") == "contain", (value, natural)
                assert [round(side) for side in picture.evaluate(BOX_JS)] == [64, 80]
            check_contrast(screen, f"Mes affiches at {width} px, {theme}")
            shot(screen, f"format-mes-affiches-{width}-{theme}.png", full_page=False)
            # A draft Story retains its ratio in the editor and in the mobile full-screen preview.
            screen.goto(f"{ORIGIN}/#{posters['remade']}")
            expect(screen.get_by_role("tab", name="Style", exact=True)).to_have_attribute("aria-selected", "true")
            canvas = screen.locator(".poster-canvas canvas").first
            if phone:
                expect(screen.get_by_role("button", name="Générer l’affiche")).to_be_in_viewport()
                screen.get_by_role("button", name="Voir l’affiche", exact=True).tap()
                sheet = screen.get_by_role("dialog", name="Affiche")
                expect(sheet).to_be_visible()
                screen.wait_for_function("document.querySelector('.stage.peek canvas')?.getBoundingClientRect().width > 250")
                check_shape(canvas, ratios["story"], f"draft preview, story at {width} px, {theme}")
                sheet.get_by_role("button", name="Revenir aux réglages").tap()
            else:
                canvas.scroll_into_view_if_needed()
                expect(canvas).to_be_in_viewport(ratio=1)
                check_shape(canvas, ratios["story"], f"draft, story at {width} px, {theme}")
            check_contrast(screen, f"steps, story at {width} px, {theme}")
            shot(screen, f"format-story-{width}-{theme}-etape.png", full_page=False)
            expect(screen.get_by_role("radio", name="Story 9:16", exact=True)).to_be_enabled()
            screen.wait_for_function(NO_SIDEWAYS)
            check_one_blur(screen, f"Style step, story at {width} px, {theme}")
            check_contrast(screen, f"Style step, story at {width} px, {theme}", ".format-choice label.chip:has(input:checked)")
            if phone:
                check_targets(screen, f"Style step, story at {width} px, {theme}")
            shot(screen, f"format-story-{width}-{theme}-etape-style.png", full_page=False)
        view.close()
    assert not errors, errors


OTHER_SHOP = "Une autre boutique est connectée dans ce navigateur. Connectez-vous pour continuer."
# While the gate is not open nothing of a shop is displayed or in the accessibility tree: the shop's part of the page is
# absent or under `hidden`, and no word of either shop is in the page's text.
GATE_CLOSED = """markers => !document.querySelector('aside.side, nav.phone-bar, .app-header :is(.credits-pill, .seg, .top-title, .menu)')
  && [...document.querySelectorAll('main:not(.gate)')].every(e => e.closest('[hidden]'))
  && !markers.some(marker => document.body.innerText.includes(marker))"""
# Shown or hidden: what the document holds of these words.
HOLDS = "markers => markers.filter(marker => document.documentElement.outerHTML.includes(marker))"
SHOP_KEYS = "prefix => Object.keys(localStorage).filter(key => key.startsWith(prefix))"
BOUND = "sessionStorage.getItem('affiche.bound')"
# The tab hidden, then shown (a headless page stays visible otherwise).
VISIBILITY = """hidden => { for (const [name, value] of [['hidden', hidden], ['visibilityState', hidden ? 'hidden' : 'visible']])
  Object.defineProperty(document, name, { value, configurable: true }); document.dispatchEvent(new Event('visibilitychange')) }"""
NO_LOCKS = "Object.defineProperty(Navigator.prototype, 'locks', { get: () => undefined, configurable: true })"


class replaced:
    """Around an action, waits for the fresh page that replaces this one. Playwright's expect_navigation also ends at a
    same-document change of address, which the gate makes (the poster's address cleared) before a sign-out loads the
    page fresh."""
    def __init__(self, page):
        self.page = page

    def __enter__(self):
        self.page.evaluate("window.replacedFrom = true")

    def __exit__(self, kind, *_):
        if kind is None:
            self.page.wait_for_function("!window.replacedFrom")
# removeItem refused for some keys, as a browser may refuse it; restoreRemoval() gives it back.
REFUSE_REMOVAL = """pattern => { const refused = new RegExp(pattern), remove = Storage.prototype.removeItem
  window.restoreRemoval = () => { Storage.prototype.removeItem = remove }
  Storage.prototype.removeItem = function (key) { if (refused.test(key)) throw new DOMException('denied', 'SecurityError'); return remove.call(this, key) } }"""
LEFT_BEHIND = "Vous êtes déconnecté, mais ce navigateur a gardé des données de la boutique : elles n’ont pas pu être effacées."


def walk_two_shops(browser, errors, data):
    """Two shops in one browser (D-MULTI-SHOP-007): the identity gate's cases at 360 px. In each case the document holds
    nothing of a shop the page is not bound to, and nothing of any shop while the gate is not open.
    Cookies: Playwright's route.fetch() applies a response's Set-Cookie to the context at once, before route.fulfill and
    even when the fulfilled answer drops it (checked on Chromium 156 for T-MULTI-SHOP-006), so a held fetch cannot hold a
    cookie. A late answer is held by not continuing its route, and its cookie change is delivered by hand at the moment it
    arrives (context.add_cookies, clear_cookies). That proves the application's reaction to any change of the cookie at
    any moment, and that the lock serialises sign-in and sign-out across two tabs of desktop Chromium; not whether a real
    browser applies or drops the Set-Cookie of an aborted or late request, nor the lock in mobile browsers."""
    engine = make_engine(Path(data))
    password_b = os.urandom(12).hex()
    hashed = PASSWORDS.hash(password_b)  # Argon2 outside the transaction, as the operator's command does
    with write_tx(engine) as conn:
        accepted(conn, shops.create_shop(conn, "Boutique Deux", "Boutique Deux", hashed))
    a_title, b_title = "Alpha Porte 7", "Bravo Porte 9"
    a_words, b_words = [a_title, "Original Phone Mada", "Casque à garder"], [b_title, "Boutique Deux"]
    both = a_words + b_words
    headers = {"Origin": ORIGIN, "X-Affiche-Bundle": str(BUNDLE)}
    aside = browser.new_context()  # the API, as another device

    def cookie_of(identifier, password):
        aside.clear_cookies()
        answer = aside.request.post(f"{ORIGIN}/api/session", headers=headers, data={"identifier": identifier, "password": password})
        assert answer.ok, answer.text()
        return aside.cookies()

    def deliver(context, identifier, password):
        """A sign-in's late Set-Cookie, delivered now: the device's session cookie becomes that shop's."""
        cookies = cookie_of(identifier, password)
        context.clear_cookies()
        context.add_cookies(cookies)
        assert [cookie["name"] for cookie in context.cookies()] == ["affiche_session"], context.cookies()

    def poster(identifier, password, title):
        cookie_of(identifier, password)
        photo = aside.request.post(f"{ORIGIN}/api/assets", headers=headers, multipart={"role": "original", "file": {
            "name": "phone.jpg", "mimeType": "image/jpeg", "buffer": (ROOT / "backend/fixtures/examples/phone-noir.jpg").read_bytes()}})
        assert photo.ok, photo.text()

        def post(path, body):
            answer = aside.request.post(f"{ORIGIN}{path}", headers={**headers, "Idempotency-Key": str(uuid4())}, data=body)
            assert answer.ok, answer.text()
            return answer.json()
        made = post("/api/product-inputs", {"name": title, "variant": "Noir", "photo_assets": [photo.json()["asset"]]})
        return post("/api/creations", {"input_id": made["id"], "offer": {"title": title, "price_ar": 120000},
                                       "brand_selection": {"logo": False, "shop_name": False, "contact": False}, "primary_format": "feed"})["id"]

    def revision(creation):
        with engine.connect() as conn:
            return conn.exec_driver_sql("SELECT current_revision FROM creations WHERE id=?", (creation,)).scalar_one()

    a_poster = poster(IDENTIFIER, PASSWORD, a_title)
    b_poster = poster("Boutique Deux", password_b, b_title)
    phone = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark")

    def tab(context=phone):
        page = context.new_page()
        page.set_default_timeout(10000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(ORIGIN)
        return page

    def until(page, check, seconds=15):
        end = time.monotonic() + seconds
        while not check():
            assert time.monotonic() < end, "timed out"
            page.wait_for_timeout(50)  # route handlers run while Playwright waits

    def sign_in(page, identifier, password):
        page.get_by_label("Identifiant de la boutique", exact=True).fill(identifier)
        page.get_by_label("Mot de passe", exact=True).fill(password)
        page.get_by_role("button", name="Ouvrir l’atelier").click()

    def showing(page, other, timeout=10000):
        expect(page.locator("main:not(.gate)")).to_be_visible(timeout=timeout)
        expect(page.locator("main.gate")).to_have_count(0)
        assert not page.evaluate(HOLDS, other), page.evaluate(HOLDS, other)

    def signed_out(page, other, elsewhere=True):
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        expect(page.locator("main.gate").get_by_text(OTHER_SHOP)).to_have_count(1 if elsewhere else 0)
        # Whom to call for a forgotten password, on every sign-in form (review r1 P2-6).
        expect(page.locator("main.gate").get_by_text(f"Mot de passe oublié ? Contactez {SUPPORT}.")).to_be_visible()
        assert page.evaluate(GATE_CLOSED, both), "shop content shown while the gate is closed"
        assert not page.evaluate(HOLDS, other), page.evaluate(HOLDS, other)
        assert page.evaluate("location.hash") == "", page.url  # no poster's address kept for whoever signs in next

    def themes(page, where, name):
        for scheme, theme in (("dark", "sombre"), ("light", "clair")):
            page.emulate_media(color_scheme=scheme)
            page.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
            page.wait_for_function(NO_SIDEWAYS)
            check_contrast(page, f"{where}, {theme}")
            shot(page, f"two-shops-{name}-{theme}.png", full_page=False)
        page.emulate_media(color_scheme="dark")

    def nav(page, name):
        go(page, name)

    def sign_out(page):
        """« Se déconnecter », to the fresh page bound to nobody: the old page may show the signed-out screen a moment
        before it is replaced (a request of its own refused once the session is gone)."""
        with replaced(page):
            go(page, "Se déconnecter")
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()

    def ask_server(page):
        """The page's next request: « Mes affiches » shows the list it holds, its removed posters are asked for. Its
        thumbnails are requests too: refused, they alone can sign the page out (review r2 P1-3) while the click is on its
        way, so the click is dispatched, not waited on; a page already signed out sends nothing (api.ts, gate_closed)."""
        form = page.get_by_label("Mot de passe", exact=True)
        posters = page.locator("nav.phone-bar").get_by_role("link", name=re.compile(r"^Mes affiches(?: -?\d+)?$"))
        removed = page.get_by_role("button", name="Retirées", exact=True)
        for control in (posters, removed):
            expect(control.or_(form)).not_to_have_count(0)
            # A refusal can sign the shop out between locating the control and clicking it.
            control.evaluate_all("elements => elements[0]?.click()")

    def come_back(page):
        """The tab hidden and shown again: the session is asked again."""
        page.evaluate(VISIBILITY, True)
        page.evaluate(VISIBILITY, False)

    def hold_first(method, store):
        """A route handler that holds the first request of this method in `store` and lets every other one through."""
        caught = []

        def handle(route):
            if route.request.method == method and not caught:
                caught.append(route)
                store.append(route)
            else:
                route.continue_()
        return handle

    # 0. Nothing of a shop is asked before the page knows its shop (review r1 P1-1): a new tab's session answer is late,
    # its address is changed to B's poster meanwhile, the device's session being B's; then the device's session becomes
    # A's and the answer names A. The tab shows A, and nothing of B is in it.
    deliver(phone, "Boutique Deux", password_b)
    early, asked = phone.new_page(), []
    early.set_default_timeout(10000)
    early.on("pageerror", lambda error: errors.append(str(error)))
    early.route("**/api/session", lambda route: asked.append(route) if route.request.method == "GET" and not asked else route.continue_())
    early.goto(ORIGIN)
    until(early, lambda: asked)
    early.evaluate("id => { location.hash = id }", b_poster)
    early.wait_for_timeout(1500)  # time enough for B's poster to be asked and answered, were it asked
    deliver(phone, IDENTIFIER, PASSWORD)
    asked.pop().continue_()
    showing(early, b_words)
    assert early.evaluate(BOUND) == "1"
    early.close()
    # And no route before the shop is loaded: an address given meanwhile is routed once the shop is there, so the chat's
    # address opens the chat (routed earlier, it became the empty address: the chat's availability was not known yet).
    early, asked = phone.new_page(), []
    early.set_default_timeout(10000)
    early.on("pageerror", lambda error: errors.append(str(error)))
    early.route("**/api/session", lambda route: asked.append(route) if route.request.method == "GET" and not asked else route.continue_())
    early.goto(ORIGIN)
    until(early, lambda: asked)
    early.evaluate("location.hash = 'message'")
    early.wait_for_timeout(500)
    asked.pop().continue_()
    expect(early.get_by_label("Votre message")).to_be_visible()
    assert early.url.endswith("#message"), early.url
    early.close()
    phone.clear_cookies()

    # Basics: A signs in as it says its identifier, keeps a poster's words and an unsent message, signs out: the form
    # shows nothing of A, A's keys are gone and the tab is bound to nobody.
    one = tab()
    expect(one.get_by_label("Mot de passe", exact=True)).to_be_visible()
    assert one.evaluate(BOUND) == "none"
    sign_in(one, "Original Phone", PASSWORD)
    showing(one, b_words)
    assert one.evaluate(BOUND) == "1"
    one.goto(f"{ORIGIN}/#{a_poster}")
    one.get_by_role("tab", name="Textes", exact=True).click()
    expect(one.get_by_label("Titre", exact=True)).to_have_value(a_title)
    one.wait_for_function("id => localStorage.getItem('affiche.shop1.words.' + id) !== null", arg=a_poster)
    one.goto(f"{ORIGIN}/#message")
    one.get_by_label("Votre message").fill("Casque à garder pour moi")
    one.wait_for_function("localStorage.getItem('affiche.shop1.chat.unsent') === 'Casque à garder pour moi'")
    themes(one, "a shop's header with « Se déconnecter », 360 px", "header-360")
    # From the poster's editor, whose phone layout has no application header: « Se déconnecter » is in its bar (review r1 P2-5).
    one.goto(f"{ORIGIN}/#{a_poster}")
    expect(one.locator(".app-header")).to_be_hidden()
    expect(one.locator(".bar").get_by_role("button", name="Se déconnecter")).to_be_visible()
    check_targets(one, "the editor's bar with « Se déconnecter », 360 px")
    sign_out(one)
    assert one.evaluate(SHOP_KEYS, "affiche.shop1.") == [], one.evaluate(SHOP_KEYS, "affiche.shop1.")
    assert one.evaluate(BOUND) == "none"
    signed_out(one, both, elsewhere=False)
    # A key the browser refuses to remove (review r1 P2-7): the session ends all the same, the page says that the browser
    # kept data of the shop and offers another try, which removes it and loads the page fresh.
    sign_in(one, IDENTIFIER, PASSWORD)
    showing(one, b_words)
    one.evaluate("localStorage.setItem('affiche.shop1.style', '{}')")
    one.evaluate(REFUSE_REMOVAL, r"^affiche\.shop1\.style$")
    go(one, "Se déconnecter")
    expect(one.locator("main.gate").get_by_text(LEFT_BEHIND)).to_be_visible()
    assert one.evaluate("fetch('/api/session').then(answer => answer.json())")["authenticated"] is False
    assert one.evaluate(SHOP_KEYS, "affiche.shop1.") == ["affiche.shop1.style"] and one.evaluate(BOUND) == "none"
    assert one.evaluate(GATE_CLOSED, both)
    one.evaluate("restoreRemoval()")
    with replaced(one):
        one.get_by_role("button", name="Réessayer l’effacement").click()
    signed_out(one, both, elsewhere=False)
    assert one.evaluate(SHOP_KEYS, "affiche.shop1.") == []

    # 4. Two tabs. Tab 2 opened signed out is bound to nobody: A's sign-in in tab 1 shows it no shop.
    two = tab()
    sign_in(one, IDENTIFIER, PASSWORD)
    showing(one, b_words)
    signed_out(two, a_words)
    themes(two, "signed out, another shop connected, 360 px", "another-shop-360")
    held = []
    one.route(f"**/api/creations/{a_poster}", hold_first("PUT", held))
    one.goto(f"{ORIGIN}/#{a_poster}")
    one.get_by_role("tab", name="Textes", exact=True).click()
    before = revision(a_poster)
    one.get_by_label("Titre", exact=True).fill(f"{a_title} bis")
    until(one, lambda: held)
    sign_in(two, "Boutique Deux", password_b)
    showing(two, a_words)
    signed_out(one, b_words)  # its storage event: bound to A, the answer names B
    # The save held across the switch is refused and changes nothing.
    with one.expect_response(lambda response: response.request.method == "PUT" and a_poster in response.url) as refused:
        held.pop().continue_()
    assert refused.value.status == 409 and refused.value.json()["error"]["code"] == "shop_changed", refused.value.status
    assert revision(a_poster) == before
    # A's explicit sign-in loads A fresh; its unsaved edit is sent first, with A's session (rule 4). Tab 2 is out in turn.
    sign_in(one, IDENTIFIER, PASSWORD)
    showing(one, b_words)
    assert revision(a_poster) == before + 1
    signed_out(two, a_words)
    one.unroute(f"**/api/creations/{a_poster}")

    # Cookies, with the lock: tab 1's sign-out, its answer held, keeps tab 2's sign-in from being sent until it is over.
    deletes, posts = [], []
    one.route("**/api/session", lambda route: deletes.append(route) if route.request.method == "DELETE" else route.continue_())
    two.on("request", lambda request: posts.append(request.url) if request.method == "POST" and request.url.endswith("/api/session") else None)
    go(one, "Se déconnecter")
    until(one, lambda: deletes)
    sign_in(two, "Boutique Deux", password_b)
    two.wait_for_timeout(1500)
    assert not posts, "tab 2's sign-in left while tab 1 held the identity lock"
    with replaced(one):
        deletes.pop().continue_()
    showing(two, a_words)
    assert len(posts) == 1, posts
    expect(one.get_by_label("Mot de passe", exact=True)).to_be_visible()
    one.unroute("**/api/session")

    # 1. A's sign-in held past its 30 s; B signs in in tab 2 meanwhile (after the lock), then A's answer arrives.
    sign_out(two)
    held = []
    one.route("**/api/session", lambda route: held.append(route) if route.request.method == "POST" else route.continue_())
    sign_in(one, IDENTIFIER, PASSWORD)
    until(one, lambda: held)
    started = time.monotonic()
    sign_in(two, "Boutique Deux", password_b)
    showing(two, a_words, timeout=45000)
    assert time.monotonic() - started > 25, "tab 2 signed in before tab 1's lock was given up"
    expect(one.locator("main.gate .message.error")).to_contain_text("Le serveur met trop de temps à répondre.")
    deliver(phone, IDENTIFIER, PASSWORD)  # A's late answer arrives now
    ask_server(two)
    signed_out(two, a_words)
    one.unroute("**/api/session")
    # The same with tab 1 closed while its sign-in is held: its lock goes with it.
    three = tab()
    showing(three, b_words)  # a new tab takes the device's session, A's
    sign_out(three)
    held = []
    three.route("**/api/session", lambda route: held.append(route) if route.request.method == "POST" else route.continue_())
    sign_in(three, IDENTIFIER, PASSWORD)
    until(three, lambda: held)
    three.close()
    sign_in(two, "Boutique Deux", password_b)
    showing(two, a_words)
    deliver(phone, IDENTIFIER, PASSWORD)
    come_back(two)
    signed_out(two, a_words)

    # 2. A, away to another page; B signs in elsewhere; Back. While the session answer is held nothing of A or B is
    # shown; then the signed-out screen (bound to A, the answer names B). Then the same with the answer failing.
    four = tab()
    showing(four, b_words)
    # Playwright's Chromium restores nothing from the back-forward cache (checked on 156, with and without its flag): the
    # two events are also dispatched by hand. pagehide hides the shop at once; pageshow with persisted reloads.
    four.evaluate("dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))")
    assert four.evaluate(GATE_CLOSED, both), "pagehide left the shop shown"
    with four.expect_navigation():
        four.evaluate("dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))")
    showing(four, b_words)
    four.goto("about:blank")
    sign_in(two, "Boutique Deux", password_b)
    showing(two, a_words)
    asked = []
    four.route("**/api/session", lambda route: asked.append(route) if route.request.method == "GET" else route.continue_())
    four.go_back()  # a load of the same tab: its binding is kept
    until(four, lambda: asked)
    four.wait_for_timeout(500)
    assert four.evaluate(GATE_CLOSED, both) and not four.evaluate(HOLDS, b_words), four.evaluate(HOLDS, both)
    for route in asked:
        try:
            route.continue_()
        except Exception:  # the request of the page left by the reload
            pass
    signed_out(four, b_words)
    four.unroute("**/api/session")
    # A signs in again in another tab: this tab saw another identity and stays signed out until its own sign-in (rule 4).
    sign_out(two)
    sign_in(two, IDENTIFIER, PASSWORD)
    showing(two, b_words)
    come_back(four)
    four.wait_for_timeout(500)
    signed_out(four, b_words)
    sign_out(two)
    sign_in(four, IDENTIFIER, PASSWORD)
    showing(four, b_words)
    four.goto("about:blank")
    sign_in(two, "Boutique Deux", password_b)
    showing(two, a_words)
    four.route("**/api/session", lambda route: route.abort("failed") if route.request.method == "GET" else route.continue_())
    four.go_back()
    expect(four.get_by_text("Connexion au serveur impossible.")).to_be_visible()
    assert four.evaluate(GATE_CLOSED, both) and not four.evaluate(HOLDS, b_words)
    themes(four, "session answer failed, 360 px", "session-failed-360")
    four.unroute("**/api/session")
    four.get_by_role("button", name="Réessayer").click()
    signed_out(four, b_words)

    # 3. Offline: A's editor holds an edit whose save is on its way; the tab is hidden and shown with the network cut.
    sign_in(four, IDENTIFIER, PASSWORD)
    showing(four, b_words)
    four.goto(f"{ORIGIN}/#{a_poster}")
    four.get_by_role("tab", name="Textes", exact=True).click()
    title = four.get_by_label("Titre", exact=True)
    saves = []
    four.route(f"**/api/creations/{a_poster}", hold_first("PUT", saves))
    title.fill(f"{a_title} hors ligne")
    until(four, lambda: saves)
    phone.set_offline(True)
    come_back(four)
    expect(four.get_by_text("Connexion au serveur impossible.")).to_be_visible()
    assert four.evaluate(GATE_CLOSED, both)
    phone.set_offline(False)
    four.get_by_role("button", name="Réessayer").click()
    expect(title).to_have_value(f"{a_title} hors ligne")  # the hidden editor kept its edit
    saves.pop().continue_()
    expect(four.get_by_text("Enregistré", exact=True)).to_be_visible()
    four.unroute(f"**/api/creations/{a_poster}")

    # 5. Expiry, then another shop: A's sessions end while its editor follows a job; the next poll is the signed-out
    # screen; B signs in there, fresh, and nothing is sent to A's poster.
    polls, puts = [], []
    four.route("**/api/jobs/*", lambda route: polls.append(route))
    four.get_by_role("button", name="Générer l’affiche").click()
    four.get_by_role("button", name="Lancer la génération").click()
    until(four, lambda: polls)
    four.on("request", lambda request: puts.append(request.url) if request.method == "PUT" and a_poster in request.url else None)
    before = revision(a_poster)
    with write_tx(engine) as conn:
        shops.end_sessions(conn, 1)
    polls.pop().continue_()
    signed_out(four, b_words, elsewhere=False)
    four.unroute("**/api/jobs/*")
    sign_in(four, "Boutique Deux", password_b)
    showing(four, a_words)
    nav(four, "Mes affiches")
    expect(four.locator("main").get_by_text(b_title)).to_be_visible()  # the sidebar's recent row has it too
    assert not four.evaluate(HOLDS, a_words) and not puts and revision(a_poster) == before, puts

    # 6. Suspension: the next action is the signed-out screen; signing in says why; enabled, a reload is A again.
    sign_in(one, IDENTIFIER, PASSWORD)
    showing(one, b_words)
    with write_tx(engine) as conn:
        shops.suspend(conn, 1)
    ask_server(one)
    signed_out(one, b_words, elsewhere=False)
    sign_in(one, IDENTIFIER, PASSWORD)
    expect(one.locator("main.gate .message.error")).to_contain_text("Cette boutique est suspendue. Contactez l’administrateur.")
    with write_tx(engine) as conn:
        shops.enable(conn, 1)
    one.reload()
    showing(one, b_words)
    assert one.evaluate(BOUND) == "1"

    # 8. Sign-out with a conflicting save offers to discard it; with the chat held by another tab it is refused.
    one.set_viewport_size({"width": 1366, "height": 768})  # the phone's editor has no header: its bar goes back
    conflict = poster(IDENTIFIER, PASSWORD, f"{a_title} conflit")  # a poster no job of the cases above follows
    one.goto(f"{ORIGIN}/#{conflict}")
    one.get_by_role("tab", name="Textes", exact=True).click()
    title = one.get_by_label("Titre", exact=True)
    expect(title).to_have_value(f"{a_title} conflit")
    current = aside.request.get(f"{ORIGIN}/api/creations/{conflict}").json()
    current["document"]["offer"]["title"] = f"{a_title} ailleurs"
    assert aside.request.put(f"{ORIGIN}/api/creations/{conflict}", headers={**headers, "Idempotency-Key": str(uuid4()), "If-Match": f'"{current["revision"]}"'},
                             data=current["document"]).ok
    title.fill(f"{a_title} ici")
    expect(one.get_by_text("Une autre version existe")).to_be_visible()
    go(one, "Se déconnecter")
    dialog = one.get_by_role("dialog")
    expect(dialog).to_contain_text("Des modifications de l’affiche n’ont pas pu être enregistrées : elles seront perdues.")
    expect(dialog).not_to_contain_text("Une image demandée")
    themes(one, "sign-out confirmation, 1366 px", "sign-out-unsaved-1366")
    with replaced(one):
        dialog.get_by_role("button", name="Se déconnecter quand même").click()
    expect(one.get_by_label("Mot de passe", exact=True)).to_be_visible()
    assert one.evaluate(BOUND) == "none" and one.evaluate(SHOP_KEYS, "affiche.shop1.") == []
    one.set_viewport_size({"width": 360, "height": 740})
    sign_in(one, IDENTIFIER, PASSWORD)
    showing(one, b_words)
    chatting = tab()
    showing(chatting, b_words)
    chatting.goto(f"{ORIGIN}/#message")
    expect(chatting.get_by_label("Votre message")).to_be_visible()  # this tab holds the chat
    # Signing out from a tab that does not hold the chat (ADR-108): nothing of the shop stays, in either tab.
    with replaced(one):
        go(one, "Se déconnecter")
    expect(one.get_by_label("Mot de passe", exact=True)).to_be_visible()
    expect(chatting.get_by_label("Mot de passe", exact=True)).to_be_visible()
    assert one.evaluate(SHOP_KEYS, "affiche.shop1.") == [], one.evaluate(SHOP_KEYS, "affiche.shop1.")
    chatting.close()
    phone.close()

    # Cookies without Web Locks: case 1, and a late sign-out answer after B's sign-in.
    bare = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark")
    bare.add_init_script(NO_LOCKS)
    first, second = tab(bare), tab(bare)
    held = []
    first.route("**/api/session", lambda route: held.append(route) if route.request.method in ("POST", "DELETE") else route.continue_())
    sign_in(first, IDENTIFIER, PASSWORD)
    until(first, lambda: held)
    sign_in(second, "Boutique Deux", password_b)
    showing(second, a_words)  # no lock to wait for
    deliver(bare, IDENTIFIER, PASSWORD)  # A's late answer: its cookie first, the page's next request finds it
    ask_server(second)
    signed_out(second, a_words)
    held.pop().fulfill(status=200, json={"authenticated": True, "shop_id": 1})  # then its body
    showing(first, b_words)  # A, by its own explicit sign-in on that tab
    go(first, "Se déconnecter")
    until(first, lambda: held)  # the sign-out's answer held
    sign_in(second, "Boutique Deux", password_b)
    showing(second, a_words)
    bare.clear_cookies()  # the late sign-out's Set-Cookie: it deletes the device's cookie, now B's
    ask_server(second)
    signed_out(second, a_words, elsewhere=False)
    with replaced(first):
        held.pop().fulfill(status=200, json={"authenticated": False})
    expect(first.get_by_label("Mot de passe", exact=True)).to_be_visible()
    bare.close()
    aside.close()
    engine.dispose()


def walk_review_r2(browser, errors, data, only=()):
    """Review r2 of T-MULTI-SHOP-006, each case on its own tab of shop 1 at 360 px: a sign-out whose answer is lost after
    the server ended the session; a canvas image refused (401); an <img> failing once the session ended; late chat work
    after a sign-out; storage that cannot be listed at sign-out; a key from before the shops that cannot be removed."""
    engine = make_engine(Path(data))
    headers = {"Origin": ORIGIN, "X-Affiche-Bundle": str(BUNDLE)}
    aside = browser.new_context()

    def poster(title, logo=False):
        """A poster of shop 1 made through the API; with `logo`, the shop's logo on it: an image layer the canvas asks for
        from the start (until a version exists the other layers are text)."""
        aside.request.post(f"{ORIGIN}/api/session", headers=headers, data={"identifier": IDENTIFIER, "password": PASSWORD})
        if logo:
            mark = aside.request.post(f"{ORIGIN}/api/assets", headers=headers, multipart={"role": "logo", "file": {
                "name": "logo.png", "mimeType": "image/png", "buffer": (ROOT / "frontend/public/icons/apple-touch-icon.png").read_bytes()}}).json()
            profile = aside.request.get(f"{ORIGIN}/api/shop-profile").json()
            assert aside.request.put(f"{ORIGIN}/api/shop-profile", headers={**headers, "Idempotency-Key": str(uuid4()), "If-Match": f'"{profile["revision"]}"'},
                                     data={"name": profile["name"], "contact": profile["contact"], "logo_asset": mark["asset"]}).ok
        photo = aside.request.post(f"{ORIGIN}/api/assets", headers=headers, multipart={"role": "original", "file": {
            "name": "phone.jpg", "mimeType": "image/jpeg", "buffer": (ROOT / "backend/fixtures/examples/phone-noir.jpg").read_bytes()}}).json()

        def post(path, body):
            answer = aside.request.post(f"{ORIGIN}{path}", headers={**headers, "Idempotency-Key": str(uuid4())}, data=body)
            assert answer.ok, answer.text()
            return answer.json()
        made = post("/api/product-inputs", {"name": title, "variant": "Noir", "photo_assets": [photo["asset"]]})
        return post("/api/creations", {"input_id": made["id"], "offer": {"title": title, "price_ar": 120000},
                                       "brand_selection": {"logo": logo, "shop_name": False, "contact": False}, "primary_format": "feed"})["id"]

    def signed_in(script=None):
        context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark")
        if script:
            context.add_init_script(script)
        page = context.new_page()
        page.set_default_timeout(10000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(ORIGIN)
        page.get_by_label("Identifiant de la boutique", exact=True).fill(IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        expect(page.locator("main:not(.gate)")).to_be_visible()
        return context, page

    def until(page, check, seconds=15):
        end = time.monotonic() + seconds
        while not check():
            assert time.monotonic() < end, "timed out"
            page.wait_for_timeout(50)

    def signed_out(page):
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        expect(page.locator("main:not(.gate)")).to_have_count(0)  # nothing of the shop is even mounted
        assert page.evaluate(BOUND) == "none"

    def lost_answer():
        # P1-1: the server ends the session, its answer is lost; the session's own answer says so, and the sign-out goes on.
        context, page = signed_in()
        page.evaluate("localStorage.setItem('affiche.shop1.style', '{}')")

        def lose(route):
            if route.request.method != "DELETE":
                return route.continue_()
            route.fetch()  # the server ends the session
            route.abort("failed")  # the answer never reaches the page
        page.route("**/api/session", lose)
        with replaced(page):
            go(page, "Se déconnecter")
        signed_out(page)
        assert page.evaluate(SHOP_KEYS, "affiche.shop1.") == []
        context.close()

    def canvas_refused():
        # P1-3: the canvas's image is refused for a session gone (401): the gate takes it, not an image error.
        made = poster("Canvas Refus 401", logo=True)
        context, page = signed_in()
        # A colour remembered for this poster: the palette does not ask for the photo, only the canvas does.
        page.evaluate("id => localStorage.setItem('affiche.shop1.palette.' + id, JSON.stringify({ colour: '#1E6FE0', at: 1 }))", made)
        page.route("**/api/assets/**", lambda route: route.fulfill(status=401, json={"error": {"code": "unauthenticated", "message_fr": "Connectez-vous pour continuer.", "retryable": False}}))
        page.goto(f"{ORIGIN}/#{made}")
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        expect(page.locator("main:not(.gate)")).to_have_count(0)  # signed out: the shop's screen leaves (D-REDESIGN-002 r1)
        context.close()

    def palette_refused():
        # P1-3: the photo the palette samples is refused (401): the gate takes it too.
        made = poster("Palette Refus 401")
        context, page = signed_in()
        page.route("**/api/assets/**", lambda route: route.fulfill(status=401, json={"error": {"code": "unauthenticated", "message_fr": "Connectez-vous pour continuer.", "retryable": False}}))
        page.goto(f"{ORIGIN}/#{made}")
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        expect(page.locator("main:not(.gate)")).to_have_count(0)  # signed out: the shop's screen leaves (D-REDESIGN-002 r1)
        context.close()

    def image_after_expiry():
        # P1-3: an image the browser fetches itself (<img>) fails once the session ended: the session is asked again.
        context, page = signed_in()
        page.wait_for_load_state("networkidle")
        image = "/api/assets/" + "f" * 64
        held = []
        page.route(ORIGIN + image, lambda route: held.append(route))
        page.locator("main:not(.gate)").evaluate("(main, src) => main.append(Object.assign(new Image(), { src }))", image)
        until(page, lambda: held)
        with write_tx(engine) as conn:
            shops.end_sessions(conn, 1)
        with page.expect_response(ORIGIN + image) as response:
            held[0].continue_()
        assert response.value.status == 401
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        expect(page.locator("main:not(.gate)")).to_have_count(0)  # signed out: the shop's screen leaves (D-REDESIGN-002 r1)
        context.close()

    def late_chat():
        # P2-4: a read on its way when the shop signs out answers late: nothing of the shop is written again.
        context, page = signed_in()
        page.goto(f"{ORIGIN}/#message")
        held = []
        page.route("**/api/reads", lambda route: held.append(route))
        page.get_by_label("Votre message").fill("Sony WH-1000XM6, 700 000 Ar")
        page.get_by_role("button", name="Envoyer").click()
        until(page, lambda: held)
        page.evaluate("localStorage.setItem('affiche.shop1.style', '{}')")
        page.evaluate(REFUSE_REMOVAL, r"^affiche\.shop1\.style$")  # the page stays, its cleanup to finish
        go(page, "Se déconnecter")
        expect(page.locator("main.gate").get_by_text(LEFT_BEHIND)).to_be_visible()
        expect(page.locator("main:not(.gate)")).to_have_count(0)  # the shop's part is gone from the page, its chat with it
        held.pop().continue_()
        page.wait_for_timeout(1500)
        assert page.evaluate(SHOP_KEYS, "affiche.shop1.") == ["affiche.shop1.style"], page.evaluate(SHOP_KEYS, "affiche.shop1.")
        page.evaluate("restoreRemoval()")
        with replaced(page):
            page.get_by_role("button", name="Réessayer l’effacement").click()
        signed_out(page)
        assert page.evaluate(SHOP_KEYS, "affiche.shop1.") == []
        context.close()

    def unlisted():
        # P2-5: the browser refuses to list its storage at sign-out: the cleanup is said to be unfinished, and its retry
        # deletes by the shop's prefix, a thread whose paid card waits included (ADR-108: nothing is kept).
        context, page = signed_in()
        page.evaluate("localStorage.setItem('affiche.shop1.style', '{}')")
        page.evaluate("localStorage.setItem('affiche.shop1.chat.c', JSON.stringify({ at: 1, items: [{ id: 'paid', role: 'app', text: '', at: 1, card: { kind: 'recap', name: 'Sony' }, spent: true, request: { path: '/api/creations/x/scenes', body: {}, revision: 1 } }] }))")
        page.evaluate("""() => { const keys = Object.keys, key = Storage.prototype.key
          window.restoreListing = () => { Object.keys = keys; Storage.prototype.key = key }
          Object.keys = value => { if (value instanceof Storage) throw new DOMException('denied', 'SecurityError'); return keys(value) }
          Storage.prototype.key = () => { throw new DOMException('denied', 'SecurityError') } }""")
        go(page, "Se déconnecter")
        # Storage that cannot be listed cannot say that nothing waits: the owner is asked (review r5 P2-3).
        expect(page.get_by_role("dialog")).to_contain_text("Une image demandée attend encore sa réponse.")
        page.get_by_role("dialog").get_by_role("button", name="Se déconnecter quand même").click()
        expect(page.locator("main.gate").get_by_text(LEFT_BEHIND)).to_be_visible()
        page.evaluate("restoreListing()")
        with replaced(page):
            page.get_by_role("button", name="Réessayer l’effacement").click()
        signed_out(page)
        assert page.evaluate(SHOP_KEYS, "affiche.shop1.") == [], page.evaluate(SHOP_KEYS, "affiche.shop1.")
        context.close()

    def retry_in_use():
        # P2-5: the retry asks first: once the shop is signed in again in another tab, its keys are in use and stay.
        context, page = signed_in()
        page.evaluate("localStorage.setItem('affiche.shop1.style', '{}')")
        page.evaluate(REFUSE_REMOVAL, r"^affiche\.shop1\.style$")
        go(page, "Se déconnecter")
        expect(page.locator("main.gate").get_by_text(LEFT_BEHIND)).to_be_visible()
        other = context.new_page()
        other.set_default_timeout(10000)
        other.goto(ORIGIN)
        other.get_by_label("Identifiant de la boutique", exact=True).fill(IDENTIFIER)
        other.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
        other.get_by_role("button", name="Ouvrir l’atelier").click()
        expect(other.locator("main:not(.gate)")).to_be_visible()
        page.evaluate("restoreRemoval()")
        page.get_by_role("button", name="Réessayer l’effacement").click()
        expect(page.locator("main.gate").get_by_text(LEFT_BEHIND)).to_have_count(0)
        assert "affiche.shop1.style" in page.evaluate(SHOP_KEYS, "affiche.shop1.")
        context.close()

    def legacy_left():
        # P2-5: a key from before the shops that the move could not remove would come back as shop 1's after its sign-out.
        context, page = signed_in("""if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); sessionStorage.setItem('refuse', '1')
            localStorage.setItem('affiche.style', '{"look":"sombre","accent_colour":"#C8A45A"}') }
          const remove = Storage.prototype.removeItem
          Storage.prototype.removeItem = function (key) { if (key === 'affiche.style' && sessionStorage.getItem('refuse')) throw new DOMException('denied', 'SecurityError'); return remove.call(this, key) }""")
        assert page.evaluate("localStorage.getItem('affiche.style')") is not None  # the move could not remove it
        go(page, "Se déconnecter")
        expect(page.locator("main.gate").get_by_text(LEFT_BEHIND)).to_be_visible()
        page.evaluate("sessionStorage.removeItem('refuse')")
        with replaced(page):
            page.get_by_role("button", name="Réessayer l’effacement").click()
        signed_out(page)
        assert page.evaluate(SHOP_KEYS, "affiche.shop1.") == [] and page.evaluate("localStorage.getItem('affiche.style')") is None
        context.close()

    def undecodable(logo):
        """Review r3 #3: an image of the shop answered (200) but undecodable, once the session has ended: the session is
        asked again and the gate takes it. With `logo`, the canvas's image (a colour remembered: the palette asks for
        nothing); without, the photo the palette samples (the canvas then has text layers only)."""
        made = poster("Image Illisible", logo=logo)
        context, page = signed_in()
        if logo:
            page.evaluate("id => localStorage.setItem('affiche.shop1.palette.' + id, JSON.stringify({ colour: '#1E6FE0', at: 1 }))", made)
        garbage = {"status": 200, "content_type": "image/png", "body": b"not an image"}
        held = {"routes": [], "open": False}
        page.route("**/api/assets/**", lambda route: route.fulfill(**garbage) if held["open"] else held["routes"].append(route))
        page.goto(f"{ORIGIN}/#{made}")
        until(page, lambda: held["routes"])
        with write_tx(engine) as conn:
            shops.end_sessions(conn, 1)
        held["open"] = True
        for route in held["routes"]:
            route.fulfill(**garbage)
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        expect(page.locator("main:not(.gate)")).to_have_count(0)  # signed out: the shop's screen leaves (D-REDESIGN-002 r1)
        context.close()

    def canvas_undecodable():
        undecodable(logo=True)

    def palette_undecodable():
        undecodable(logo=False)

    def race(script):
        """Review r3 #2: « Réessayer l’effacement »'s session answer (nobody) is held; the same shop signs in in another
        tab, whose new session writes a draft once shown; then the answer arrives. The draft stays."""
        context, page = signed_in(script)
        page.evaluate("localStorage.setItem('affiche.shop1.style', '{}')")
        page.evaluate(REFUSE_REMOVAL, r"^affiche\.shop1\.style$")
        go(page, "Se déconnecter")
        expect(page.locator("main.gate").get_by_text(LEFT_BEHIND)).to_be_visible()
        page.evaluate("restoreRemoval()")
        held = []
        page.route("**/api/session", lambda route: held.append((route, route.fetch())) if route.request.method == "GET" and not held else route.continue_())
        page.get_by_role("button", name="Réessayer l’effacement").click()
        until(page, lambda: held)
        route, answer = held[0]
        assert answer.json()["authenticated"] is False, answer.json()
        other = context.new_page()
        other.set_default_timeout(10000)
        other.goto(ORIGIN)
        other.get_by_label("Identifiant de la boutique", exact=True).fill(IDENTIFIER)
        other.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
        other.get_by_role("button", name="Ouvrir l’atelier").click()
        shown, draft = other.locator("main:not(.gate)"), "localStorage.setItem('affiche.shop1.chat.unsent', 'Une affiche pour le casque')"
        written = False
        try:
            expect(shown).to_be_visible(timeout=3000)  # signed in while the retry waits for its answer
            other.evaluate(draft)
            written = True
        except AssertionError:
            pass  # the sign-in waits for the retry
        route.fulfill(response=answer)
        expect(page.locator("main.gate").get_by_text(LEFT_BEHIND)).to_have_count(0)  # the retry is over, whatever it did
        if not written:
            expect(shown).to_be_visible()
            other.evaluate(draft)
        assert other.evaluate("localStorage.getItem('affiche.shop1.chat.unsent')") == "Une affiche pour le casque"
        context.close()

    def offline_sign_out():
        # ADR-108: the session ends first, the keys go after. The sign-out cannot reach the server: still signed in, and
        # nothing of the shop is deleted from the device.
        context, page = signed_in()
        page.evaluate("localStorage.setItem('affiche.shop1.style', '{}')")
        page.route("**/api/session", lambda route: route.abort("failed") if route.request.method == "DELETE" else route.continue_())
        go(page, "Se déconnecter")
        expect(page.locator(".message.error")).to_contain_text("Déconnexion impossible : la connexion au serveur est interrompue. Réessayez.")
        expect(page.locator("main:not(.gate)")).to_be_visible()
        assert page.evaluate(SHOP_KEYS, "affiche.shop1.") == ["affiche.shop1.style"] and page.evaluate(BOUND) == "1"
        context.close()

    def retry_race_locked():
        # With Web Locks; the other tab's announce (affiche.identity) refused, so that only the lock is tested.
        race("""(() => { const set = Storage.prototype.setItem; Storage.prototype.setItem = function (key, value) {
          if (key === 'affiche.identity') throw new DOMException('full', 'QuotaExceededError'); return set.call(this, key, value) } })()""")

    def retry_race_lockless():
        # Without Web Locks: the retry sees the sign-in announced (affiche.identity) and asks the session again.
        race(NO_LOCKS)

    for case in (lost_answer, canvas_refused, palette_refused, image_after_expiry, late_chat, unlisted, retry_in_use, legacy_left,
                 canvas_undecodable, palette_undecodable, retry_race_locked, retry_race_lockless, offline_sign_out):
        if not only or case.__name__ in only:
            case()
    aside.close()
    engine.dispose()


def walk_credits(browser, errors, data, app):
    """The prepaid balance in the browser (D-BALANCE-006) at 360 × 740 with a touch pointer, on a shop of its own granted 5
    credits: the cost and what is left; « Bientôt à court » with the purchase text at 3; a refused image's credit given
    back; the service's pause told before the tap; a free change by message kept while paused and at zero; nothing sent
    at zero; a lost answer taken up at zero, and while paused, in the editor and in the chat (« Reprendre »), one job each;
    a chat retry refused for want of credit, kept, with the balance read again; checking, editing, downloading and « Mes
    affiches » at zero. Each dialog in both themes. No « $ » or « USD » on any screen (a check of the screens:
    test_two_shops.py walks every answer of the API)."""
    engine = make_engine(Path(data))
    password = os.urandom(12).hex()
    hashed = PASSWORDS.hash(password)  # Argon2 outside the transaction, as the operator's command does
    with write_tx(engine) as conn:
        shop = shops.create_shop(conn, "Boutique Credits", "Boutique Credits", hashed)
        credits.grant(conn, shop, 5, origin="offered", ref="smoke", actor="tests")
        accepted(conn, shop)
    purchase = f"Pour obtenir des crédits, contactez {SUPPORT}."
    zero = f"Il ne vous reste plus de crédit : rien ne sera envoyé. Vos affiches restent disponibles. {purchase}"
    once = "1 crédit, une seule fois pour cette demande"
    sent, balance_reads = [], []  # every new image request that left the browser (its path and its key); each balance read
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark")
    context.on("request", lambda request: sent.append((request.url.rsplit("/", 1)[1], request.headers.get("idempotency-key")))
               if request.method == "POST" and re.search(r"/(scenes|refinements|text-effects)$", request.url) else None)
    context.on("request", lambda request: balance_reads.append(request.url) if request.url.endswith("/api/balance") else None)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(ORIGIN + "/#etapes")
    page.get_by_label("Identifiant de la boutique", exact=True).fill("Boutique Credits")
    page.get_by_label("Mot de passe", exact=True).fill(password)
    page.get_by_role("button", name="Ouvrir l’atelier").click()
    dialog, cost, thread = page.get_by_role("dialog"), page.locator(".confirm .cost"), page.get_by_role("log")
    review = page.get_by_role("heading", name="Vérifier votre affiche")
    balance = lambda: page.request.get(f"{ORIGIN}/api/balance").json()  # noqa: E731
    jobs = lambda kind: [job for job in page.request.get(f"{ORIGIN}/api/creations/{poster}/jobs").json()["items"] if job["kind"] == kind]  # noqa: E731

    def looks(where, name):
        for scheme, theme in (("light", "clair"), ("dark", "sombre")):
            page.emulate_media(color_scheme=scheme)
            page.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
            page.wait_for_function(NO_SIDEWAYS)
            check_contrast(page, f"{where} at 360 px, {theme}")
            shot(page, f"credits-360-{theme}-{name}.png", full_page=False)
        assert all(button.bounding_box()["height"] >= 44 for button in dialog.get_by_role("button").all()), where
        shown = page.locator("body").inner_text()
        assert "$" not in shown and "USD" not in shown, (where, shown)

    def adjust():  # « Ajuster la scène » opens its dialog, which reads the balance again
        page.get_by_role("tab", name="Réglages", exact=True).tap()
        page.get_by_label("Ajustement de la scène").fill("Une lumière plus chaude")
        page.get_by_role("button", name="Ajuster la scène", exact=True).tap()
        expect(dialog).to_contain_text("Ajuster la scène ?")

    def approve():
        alternative = page.get_by_role("dialog", name="Vérifier la fidélité du produit")
        expect(review.or_(alternative)).to_be_visible(timeout=30000)
        if alternative.is_visible():
            alternative.get_by_role("button", name="Choisir cette version").tap()
        download_review(page)
        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
        expect(review).to_have_count(0)

    def say(text):
        page.get_by_label("Votre message").fill(text)
        page.get_by_role("button", name="Envoyer").click()
        return thread.locator(".bubble.bot").last

    def priced(price):  # a free change is saved in the document; no image is asked
        for _ in range(50):
            if page.request.get(f"{ORIGIN}/api/creations/{poster}").json()["document"]["offer"]["price_ar"] == price:
                return
            page.wait_for_timeout(200)
        raise AssertionError(f"the price {price} was not saved")

    # A first poster: what it costs and what is left, then one credit spent. Its price is not drawn in the image, so that
    # a price change by message is free (further down).
    expect(page.get_by_label("Photos du produit")).to_be_enabled()  # the page's opening is over (perform drops a busy tap)
    page.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
    expect(page.locator(".photo-strip img")).to_have_count(1)
    page.get_by_label("Nom du produit", exact=True).fill("Casque Kilo")
    page.get_by_label("Prix en ariary", exact=True).fill("150 000")
    page.get_by_label("Les photos correspondent").check()
    page.get_by_role("button", name="Préparer mon affiche").tap()
    page.get_by_role("tab", name="Textes", exact=True).tap()
    page.get_by_label("Dessiner aussi le prix dans l’image").uncheck()
    page.get_by_role("button", name="Générer l’affiche").tap()
    expect(cost).to_have_text("1 crédit · il vous en reste 5")
    looks("the first poster's dialog", "5")
    page.get_by_role("button", name="Lancer la génération").tap()
    approve()
    poster = page.url.split("#")[1]
    # One more version: 4 left, then 3, where the dialog says how to buy and its button stays.
    adjust()
    expect(cost).to_have_text("1 crédit · il vous en reste 4")
    page.get_by_role("button", name="Lancer l’ajustement").tap()
    approve()
    assert balance()["available"] == 3
    adjust()
    expect(cost).to_have_text(f"1 crédit · il vous en reste 3. Bientôt à court : {purchase}")
    expect(dialog.get_by_role("button", name="Lancer l’ajustement")).to_be_visible()
    looks("« Bientôt à court »", "3")
    # The image service refuses the next one (a stub that fails once, as STUB_FAIL=refused would every time): the job ends
    # without an image, and its credit is back.
    service = app.state.poster_service
    kept, service.provider = service.provider, StubProvider(["refused"])
    try:
        page.get_by_role("button", name="Lancer l’ajustement").tap()
        expect(page.locator(".message.error")).to_contain_text("Le service d’images a refusé cette demande", timeout=30000)
    finally:
        service.provider = kept
    expect(page.locator(".message.error")).to_contain_text("Votre crédit vous a été rendu.")
    assert [job["credit"] for job in jobs("refine") if job["status"] == "failed"] == ["given_back"] and balance()["available"] == 3
    page.locator(".message.error").get_by_role("button", name="Fermer").tap()
    # A free change by message (the price is not drawn) is read, then the operator pauses the service. Its button stays,
    # although a new image is stopped (ChatView.vue buttonOf: `!free(item)`); the price is changed and no image is asked.
    page.goto(f"{ORIGIN}/#message-{poster}")
    return_to_work(page)
    card = say("prix 160 000 Ar")
    expect(card.get_by_role("button")).to_have_text(["Changer", "Annuler"])
    with write_tx(engine) as conn:
        shops.pause(conn)
    before = len(sent)
    with page.expect_response("**/api/balance"):
        page.reload()  # the pause is read with the page
    return_to_work(page)
    page.wait_for_timeout(500)  # the read balance is applied: a card it stops loses its button by now
    card = thread.locator(".bubble.bot").last
    expect(card.get_by_role("button")).to_have_text(["Changer", "Annuler"])
    expect(card).not_to_contain_text(MESSAGES["budget_exhausted"])
    card.get_by_role("button", name="Changer").tap()
    expect(thread).to_contain_text("C’est changé sur l’affiche.")
    priced(160000)
    # Paused, the editor's dialog says so before the tap, without the purchase text, and offers « Fermer » only.
    page.goto(f"{ORIGIN}/#{poster}")
    return_to_work(page)
    adjust()
    expect(cost).to_have_text(MESSAGES["budget_exhausted"])
    expect(dialog).not_to_contain_text(purchase)
    expect(dialog.get_by_role("button")).to_have_text(["Fermer"])
    looks("paused", "pause")
    dialog.get_by_role("button", name="Fermer").tap()
    with write_tx(engine) as conn:
        shops.resume(conn)
    assert len(sent) == before, sent

    # The editor's last credit, its answer lost (the server takes the request, the connection drops): at zero, and while
    # paused, reopening the dialog still offers that request (api.ts retained), and the server answers it with the job it
    # made. One job, one key (T-BALANCE-006 review r1).
    with write_tx(engine) as conn:
        credits.correct(conn, shop, -2, ref="smoke-two", note="the last credit", actor="tests")
    page.reload()  # the operator's correction is read with the page, as after any return to it
    return_to_work(page)
    adjust()
    expect(cost).to_have_text(f"1 crédit · il vous en reste 1. Bientôt à court : {purchase}")

    def drop_answer(route):
        route.fetch()  # the server has taken the request
        route.abort()  # and the page never hears of it
    context.route("**/refinements", drop_answer)
    refines = len(jobs("refine"))
    page.get_by_role("button", name="Lancer l’ajustement").tap()
    expect(page.locator(".message.error")).to_contain_text("Connexion interrompue")
    context.unroute("**/refinements")
    assert balance()["available"] == 0 and len(jobs("refine")) == refines + 1
    page.locator(".message.error").get_by_role("button", name="Fermer").tap()
    adjust()
    expect(cost).to_have_text(once)
    expect(dialog.get_by_role("button")).to_have_text(["Lancer l’ajustement", "Annuler"])
    dialog.get_by_role("button", name="Annuler").tap()
    with write_tx(engine) as conn:
        shops.pause(conn)
    adjust()
    expect(cost).to_have_text(once)
    looks("a lost answer at zero, paused", "perdue")
    page.get_by_role("button", name="Lancer l’ajustement").tap()
    approve()
    with write_tx(engine) as conn:
        shops.resume(conn)
    assert len(jobs("refine")) == refines + 1 and sent[-1] == sent[-2] and sent[-1][0] == "refinements", sent

    # By message, a credit again (the operator's). The card's request never reaches the server (the connection drops):
    # « Réessayer ». Another device spends the credit meanwhile, so the balance shown is stale: the retry is refused (402)
    # with how to buy, stays offered, and the balance is read again.
    with write_tx(engine) as conn:
        credits.correct(conn, shop, 1, ref="smoke-three", note="one more", actor="tests")
    page.goto(f"{ORIGIN}/#message-{poster}")
    page.reload()
    return_to_work(page)
    card = say("fond plus sombre")
    expect(card).to_contain_text(f"1 crédit · il vous en reste 1. Bientôt à court : {purchase}")
    context.route("**/refinements", lambda route: route.abort())
    card.get_by_role("button", name="Créer", exact=True).tap()
    retry = thread.get_by_role("button", name="Réessayer")
    expect(retry).to_be_visible()
    context.unroute("**/refinements")
    with write_tx(engine) as conn:
        credits.correct(conn, shop, -1, ref="smoke-four", note="spent on another device", actor="tests")
    reads = len(balance_reads)
    retry.tap()
    expect(thread).to_contain_text(f"{MESSAGES['no_credit']} {purchase}")
    expect(retry).to_be_visible()
    for _ in range(50):
        if len(balance_reads) > reads:
            break
        page.wait_for_timeout(100)
    else:
        raise AssertionError("the balance was not read again after the chat's 402")
    # The credit is back; the same request takes it, and its answer is lost: the page reloaded at zero still offers
    # « Reprendre », which sends it with its key; the server answers what it stored, one job.
    with write_tx(engine) as conn:
        credits.correct(conn, shop, 1, ref="smoke-five", note="one more", actor="tests")
    stuck = []

    def lose_answer(route):
        route.fetch()  # the server has taken the request
        stuck.append(route)  # and the page never hears of it
    context.route("**/refinements", lose_answer)
    retry.tap()
    for _ in range(100):
        if stuck:
            break
        page.wait_for_timeout(100)
    assert stuck and balance()["available"] == 0
    refines = len(jobs("refine"))
    page.reload()
    context.unroute("**/refinements")
    return_to_work(page)
    resume = thread.get_by_role("button", name="Reprendre")
    expect(resume).to_be_visible()
    expect(resume.locator("xpath=../..")).to_contain_text(once)
    looks("« Reprendre » at zero", "reprendre")
    resume.tap()
    expect(thread).to_contain_text("Version 4 prête.", timeout=30000)
    assert len(jobs("refine")) == refines and sent[-1] == sent[-2] == sent[-3] and sent[-1][0] == "refinements", sent
    # A new card at zero says so in place of its button; nothing is sent.
    before = len(sent)
    card = say("fond plus clair")
    expect(card).to_contain_text(zero)
    expect(card.get_by_role("button")).to_have_text(["Annuler"])
    looks("a chat card at zero", "chat-zero")
    card.get_by_role("button", name="Annuler").tap()
    # A free change at zero keeps its button: the price is changed and no image is asked.
    card = say("prix 180 000 Ar")
    expect(card.get_by_role("button")).to_have_text(["Changer", "Annuler"])
    expect(card).not_to_contain_text(zero)
    card.get_by_role("button", name="Changer").tap()
    priced(180000)
    assert len(sent) == before, sent
    # Checking is free at zero: the new version is approved.
    thread.get_by_role("button", name="Vérifier", exact=True).tap()
    approve()

    # Resume the same poster in the editor after checking and downloading in Message.
    page.get_by_role("button", name="Pas à pas", exact=True).tap()
    page.wait_for_url(f"{ORIGIN}/#{poster}")
    # The editor at zero: the dialog says how to buy, offers « Fermer » only, and nothing leaves.
    adjust()
    expect(cost).to_have_text(zero)
    expect(dialog.get_by_role("button")).to_have_text(["Fermer"])
    looks("the editor at zero", "zero")
    dialog.get_by_role("button", name="Fermer").tap()
    assert len(sent) == before, sent
    # Editing is free at zero: the scene's zoom, saved.
    revision = page.request.get(f"{ORIGIN}/api/creations/{poster}").json()["revision"]
    page.get_by_label("Zoom").evaluate("e => { e.value = '1.3'; e.dispatchEvent(new Event('input', { bubbles: true })) }")
    for _ in range(50):
        if page.request.get(f"{ORIGIN}/api/creations/{poster}").json()["revision"] > revision:
            break
        page.wait_for_timeout(200)
    else:
        raise AssertionError("the edit at zero was not saved")
    # And so is downloading.
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).tap()
    expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=40000)
    page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).tap()
    link = page.get_by_role("link", name="Télécharger le PNG")
    expect(link).to_be_visible()
    downloaded = page.request.get(ORIGIN + link.get_attribute("href"))
    assert downloaded.status == 200 and downloaded.headers["content-type"] == "image/png", downloaded.status
    page.locator(".final-preview").get_by_role("button", name="Fermer").tap()
    # « Mes affiches » lists the poster at zero.
    page.goto(f"{ORIGIN}/#affiches")
    expect(page.get_by_role("heading", name="Mes affiches", exact=True)).to_be_visible()
    expect(page.locator("main").get_by_text("Casque Kilo").first).to_be_visible()
    shown = page.locator("body").inner_text()
    assert "$" not in shown and "USD" not in shown, shown
    assert balance() | {"blocked": None} == {"available": 0, "pending": 0, "purchase_fr": purchase, "blocked": None}
    context.close()
    engine.dispose()


def credited(engine):
    """100 offered credits for the pilot shop, as the operator grants them: a shop starts at zero, and every image job
    takes one (D-BALANCE-002); and the conditions accepted."""
    with write_tx(engine) as conn:
        credits.grant(conn, 1, 100, origin="offered", ref="tests", actor="tests")
        accepted(conn, 1)


def accepted(conn, shop):
    """The current conditions of use accepted, as POST /api/terms writes it (D-TERMS-002): without them nothing new is
    asked of the AI (D-TERMS-003)."""
    conn.exec_driver_sql("UPDATE shop_profile SET terms_version=?, terms_accepted_at=? WHERE id=?",
                         (terms.VERSION, utc_now(), shop))


def serve(data, **extra):
    """The API on loopback port API_PORT (8000 unless the environment says; Vite proxies /api there), stub providers, temporary data, the pilot shop funded;
    the defaults unless told."""
    settings = Settings(_env_file=None, image_provider="stub", planner_provider="stub", openai_api_key=None,
                        anthropic_api_key=None, spend_cap_usd="20", spend_cap_since="2026-11-06",
                        data_dir=data, app_origin=ORIGIN, shop_password_hash=PASSWORDS.hash(PASSWORD),
                        support_contact_fr=SUPPORT, **{"stub_fail": None, **extra})
    server = uvicorn.Server(uvicorn.Config(create_app(settings, prepare=credited), host="127.0.0.1", port=API_PORT, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started or not thread.is_alive():
            break
        time.sleep(.05)
    assert server.started, "API did not start"
    return server, thread


# The stub planner makes the chat available, and a device that never chose its start view is asked once
# (D-TEXT-FIRST-001). This run is the step editor's: each of its contexts starts as a device that chose « Pas à pas ».
# The chat and the choice itself have their own run (chat_browser.py).
STEPS_FIRST = "try { localStorage.getItem('affiche.start') || localStorage.setItem('affiche.start', 'steps') } catch {}"


def steps_first(browser):
    make = browser.new_context

    def context(**options):
        made = make(**options)
        made.add_init_script(STEPS_FIRST)
        return made
    browser.new_context = context
    browser.new_page = lambda **options: context(**options).new_page()


def stop(server, thread):
    server.should_exit = True
    thread.join(timeout=20)
    assert not thread.is_alive(), "API did not stop"


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="affiche-browser-") as data:
        servers = [serve(data)]
        with (OUTPUT / "vite.log").open("w", encoding="utf-8") as log:
            vite = subprocess.Popen(["node", str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1"],
                                    cwd=ROOT / "frontend", stdout=log, stderr=log,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                with sync_playwright() as playwright:
                    # SMOKE_CHANNEL=msedge runs the same flow in the installed Microsoft Edge.
                    browser = playwright.chromium.launch(headless=True, channel=os.environ.get("SMOKE_CHANNEL") or None)
                    print("Browser:", browser.browser_type.name, os.environ.get("SMOKE_CHANNEL") or "bundled", browser.version, flush=True)
                    steps_first(browser)
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 1050}, color_scheme="dark")
                        errors = []
                        page.set_default_timeout(10000)
                        page.on("response", lambda response: print(f"HTTP {response.status} {response.url}", flush=True) if response.status >= 400 else None)
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        for attempt in range(60):
                            if vite.poll() is not None:
                                raise RuntimeError("Vite stopped; inspect outputs/editor-smoke/vite.log")
                            try:
                                page.goto(ORIGIN + "/#etapes", timeout=2000)
                                break
                            except Exception:
                                if attempt == 59:
                                    raise
                                time.sleep(.25)
                        # The files load but the application's own process does not answer: a French message with a retry.
                        # A fresh tab's case: the first answer (signed out) binds this tab to nobody (D-MULTI-SHOP-007), and
                        # a tab bound to nobody shows the sign-in form whatever the service says. Wait for that answer, then
                        # forget the binding, so the reload below is a fresh page whichever finished first.
                        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
                        page.route("**/api/session", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":{"code":"service_down","message_fr":"Le service est momentanément indisponible.","retryable":true}}'))
                        page.evaluate("sessionStorage.removeItem('affiche.bound')")
                        page.reload()
                        expect(page.get_by_role("alert")).to_contain_text("momentanément indisponible")
                        expect(page.get_by_label("Mot de passe", exact=True)).to_have_count(0)
                        page.unroute("**/api/session")
                        page.get_by_role("button", name="Réessayer").click()
                        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
                        check_contrast(page, "sign-in")
                        check_primary(page, "sign-in", page.locator("form.sign-in").get_by_role("button", name="Ouvrir l’atelier"))
                        check_field(page, "input[name=username]", "sign-in")
                        check_resting(page, "sign-in", ".sign-in")
                        # A dark device and no choice stored: the dark theme, and the browser's bar says so (it took the
                        # light colour before T-THEME-COLOR).
                        assert theme_of(page) == "sombre" and bar_colour(page) == GROUNDS["sombre"], (theme_of(page), bar_colour(page))
                        # The home-screen manifest and its icons are served.
                        manifest = page.request.get(f"{ORIGIN}/manifest.webmanifest").json()
                        assert manifest["display"] == "standalone" and manifest["lang"] == "fr", manifest
                        for icon in [*manifest["icons"], {"src": "/icons/apple-touch-icon.png"}]:
                            served = page.request.get(ORIGIN + icon["src"])
                            assert served.status == 200 and served.headers["content-type"] == "image/png", icon
                        # Whom to call for a forgotten password; one sentence for a wrong identifier and for a wrong
                        # password, so nothing says whether a shop exists (R-MULTI-SHOP-001).
                        expect(page.get_by_text(f"Mot de passe oublié ? Contactez {SUPPORT}.")).to_be_visible()
                        for identifier, password in (("inconnue", PASSWORD), ("Original Phone", PASSWORD[::-1])):
                            page.get_by_label("Identifiant de la boutique", exact=True).fill(identifier)
                            page.get_by_label("Mot de passe", exact=True).fill(password)
                            page.get_by_role("button", name="Ouvrir l’atelier").click()
                            expect(page.locator(".message.error")).to_contain_text("Identifiant ou mot de passe incorrect.")
                            page.locator(".message.error").get_by_role("button", name="Fermer").click()
                            expect(page.locator(".message.error")).to_have_count(0)
                        page.get_by_label("Identifiant de la boutique", exact=True).fill(IDENTIFIER)
                        page.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
                        page.get_by_role("button", name="Ouvrir l’atelier").click()
                        expect(page.get_by_label("Photos du produit")).to_be_enabled()
                        check_contrast(page, "intake")
                        check_primary(page, "intake", page.locator("form.intake").get_by_role("button", name="Préparer mon affiche"))
                        check_field(page, "input[name=product]", "intake")
                        check_resting(page, "intake", ".intake")
                        page.screenshot(path=str(OUTPUT / "intake.png"), full_page=True)
                        # Glass on what floats (the header, painted by its ::before since D-REDESIGN-002), none on a card
                        # at rest (D-REDESIGN-001); all solid for a person who asked for less motion (R-POSTER-EDITOR-006).
                        blur = "selector => getComputedStyle(document.querySelector(selector)).backdropFilter"
                        bar_glass = "property => getComputedStyle(document.querySelector('.app-header'), '::before')[property]"
                        assert page.evaluate(bar_glass, "backdropFilter") != "none" and page.evaluate(blur, ".intake") == "none"
                        page.emulate_media(reduced_motion="reduce")
                        assert page.evaluate(bar_glass, "backdropFilter") == "none" and page.evaluate(blur, ".intake") == "none"
                        assert page.evaluate(bar_glass, "backgroundColor").startswith("rgb(")
                        check_contrast(page, "intake, solid chrome", placeholders=("input[name=product]", "input[name=price]"))
                        page.emulate_media(reduced_motion="no-preference")
                        # Accueil before the first poster: its empty list is a card at rest too.
                        go(page, "Accueil")
                        expect(page.locator(".shop-home .empty")).to_be_visible()
                        check_resting(page, "Accueil", ".empty")
                        go(page, "Nouvelle affiche")
                        expect(page.get_by_label("Photos du produit")).to_be_enabled()  # the way back is over
                        # The browser's own file control (« Choose Files ») is not shown: the label shows a French button.
                        expect(page.locator(".upload-zone .pick-button")).to_have_text("Ajouter des photos")
                        assert page.locator("#champ-photos").evaluate("e => getComputedStyle(e).opacity") == "0"
                        page.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
                        expect(page.locator(".photo-strip img")).to_have_count(1)
                        expect(page.locator(".upload-zone .pick-button")).to_have_text("Changer les photos")
                        page.get_by_label("Nom du produit", exact=True).fill("Soundcore R50i")
                        page.get_by_label("Variante confirmée").fill("Noir · écouteurs et boîtier")
                        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
                        page.get_by_label("Les photos correspondent").check()
                        # A logo is saved in the profile but left off this poster; it is ticked after the scene, further down.
                        identity = page.locator(".intake details")
                        assert not identity.evaluate("node => node.open")
                        identity.locator("summary").press("Enter")
                        Image.new("RGBA", (256, 256), (20, 120, 220, 255)).save(OUTPUT / "logo.png")
                        page.locator("details input[type=file]").set_input_files(OUTPUT / "logo.png")
                        expect(page.get_by_alt_text("Logo de la boutique")).to_be_visible()
                        page.get_by_role("checkbox", name="Logo", exact=True).uncheck()
                        # The logo or the contact identifies the shop: its name starts unticked (ADR-053).
                        expect(page.get_by_role("checkbox", name="Nom de la boutique", exact=True)).not_to_be_checked()
                        page.get_by_label("Nom de la boutique", exact=True).first.fill("Original Phone Mada")
                        page.get_by_label("Contact", exact=True).first.fill("038 93 028 00 / 034 93 028 00")
                        page.get_by_role("checkbox", name="Nom de la boutique", exact=True).check()
                        page.get_by_role("checkbox", name="Contact", exact=True).check()
                        admissions = []
                        page.on("request", lambda req: admissions.append(req.url) if req.method == "POST" and req.url.endswith(("/plans", "/scenes")) else None)
                        page.get_by_role("button", name="Préparer mon affiche").click()
                        expect(page.get_by_role("heading", name="Soundcore R50i", exact=True)).to_be_visible()
                        expect(page.locator(".poster-canvas canvas").first).to_be_visible()
                        # The contact is one compact line written by the renderer; its position is free and remembered.
                        def footer(role):
                            layers = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]["formats"]["feed"]["layers"]
                            return next((layer for layer in layers if layer["role"] == role), None)
                        def until(check):
                            for _ in range(50):
                                if check():
                                    return
                                page.wait_for_timeout(200)
                            raise AssertionError("condition not reached")
                        until(lambda: footer("contact").get("icon") == "phone")
                        compact = footer("contact")
                        assert (compact["font_size"], compact["weight"], compact["height"], compact["align"]) == (32, 700, 48, "center"), compact
                        def tab(name):
                            return page.get_by_role("tab", name=name, exact=True)
                        def open_group(name):
                            tab(name).click()
                            expect(tab(name)).to_have_attribute("aria-selected", "true")
                        generate = page.get_by_role("button", name="Générer l’affiche")
                        offer = page.get_by_role("region", name="Offre à générer")
                        expect(tab("Style")).to_have_attribute("aria-selected", "true")
                        expect(page.get_by_role("tab")).to_have_count(3)
                        expect(tab("Textes")).to_be_enabled()
                        expect(tab("Boutique")).to_be_enabled()
                        expect(page.get_by_label("Titre", exact=True)).to_have_count(0)
                        expect(page.get_by_label("Position du contact")).to_have_count(0)
                        expect(offer).to_contain_text("Soundcore R50i")
                        expect(offer).to_contain_text("Noir · écouteurs et boîtier")
                        expect(offer).to_contain_text(re.compile(r"90\s000\s*Ar", re.IGNORECASE))
                        expect(offer.locator("img")).to_have_count(1)
                        page.wait_for_function("img => img.complete && img.naturalWidth > 0", arg=offer.locator("img").element_handle())
                        expect(offer).to_contain_text("Original Phone Mada")
                        expect(offer).to_contain_text("038 93 028 00")
                        expect(offer).to_contain_text("Publication")
                        expect(offer).to_contain_text("Studio clair")
                        expect(page.get_by_role("heading", name="Versions 0 sur 12")).to_be_visible()
                        expect(page.get_by_text("Vous choisirez celle à exporter.", exact=False)).to_be_visible()
                        expect(page.get_by_role("button", name="Continuer", exact=True)).to_have_count(0)
                        expect(generate).to_be_enabled()
                        # The offer is ready on arrival. Opening and cancelling the cost confirmation creates no plan or scene.
                        generate.click()
                        cost = page.get_by_role("dialog")
                        expect(cost.get_by_role("button", name="Lancer la génération", exact=True)).to_be_enabled()
                        expect(cost).to_contain_text("1 crédit")
                        cost.get_by_role("button", name="Annuler").click()
                        assert not admissions, admissions
                        open_group("Textes")
                        check_contrast(page, "step Textes")
                        check_resting(page, "step editor at 1440 px", ".rail")
                        shot(page, "step-textes.png")
                        # "Brand as plain text" is offered only once a brand is typed.
                        plain_brand = page.get_by_label("Écrire la marque en texte simple", exact=False)
                        page.get_by_label("Marque (facultative)").fill("")
                        expect(plain_brand).to_have_count(0)
                        page.get_by_label("Marque (facultative)").fill("JBL")
                        expect(plain_brand).to_be_visible()
                        expect(offer).to_contain_text("JBL")
                        page.get_by_label("Marque (facultative)").fill("")
                        expect(offer).not_to_contain_text("JBL")
                        # The accent is chosen among the title's own words and a few colours, never typed; the colour
                        # sits with the word it colours.
                        chips = page.get_by_role("group", name="Mot du titre en couleur").get_by_role("button")
                        expect(chips.last).to_have_text("Aucun")
                        expect(chips.last).to_have_attribute("aria-pressed", "true")
                        accent = chips.first.inner_text()
                        chips.first.click()
                        expect(chips.first).to_have_attribute("aria-pressed", "true")
                        page.get_by_role("button", name="Rouge", exact=True).click()
                        open_group("Boutique")
                        expect(generate).to_be_enabled()
                        expect(page.get_by_label("Titre", exact=True)).to_have_count(0)
                        assert page.get_by_label("Dessiner aussi le nom de la boutique et le contact dans l’image").count() == 0
                        shop_name = page.get_by_role("checkbox", name="Nom de la boutique", exact=True)
                        shop_name.uncheck()
                        expect(offer).not_to_contain_text("Original Phone Mada")
                        shop_name.check()
                        expect(offer).to_contain_text("Original Phone Mada")
                        page.get_by_label("Position du contact").select_option("right")
                        until(lambda: footer("contact")["align"] == "right")
                        assert json.loads(page.evaluate("localStorage.getItem('affiche.shop1.style')"))["contact_align"] == "right"
                        # By default the contact is drawn in the composition, at the chosen position, without the
                        # shop name (ADR-055). The option is in view: no section has to be opened to find it.
                        expect(page.get_by_text("Pour la prochaine version", exact=True)).to_be_visible()
                        expect(page.get_by_label("Dessiner aussi le contact dans l’image")).to_be_checked()
                        check_contrast(page, "step Boutique")
                        shot(page, "step-boutique.png")
                        open_group("Style")
                        expect(generate).to_be_enabled()
                        expect(page.get_by_label("Position du contact")).to_have_count(0)
                        # One format enabled (the pilot's default, FORMATS_ENABLED=feed): no format is offered, nothing asked.
                        expect(page.get_by_role("radiogroup", name="Format")).to_have_count(0)
                        expect(page.locator(".bar .format")).to_contain_text("Publication · 1080 × 1350")
                        expect(page.locator("#aide-format")).to_have_text("Publication permet de télécharger votre affiche en PNG.")
                        check_contrast(page, "step Style")
                        shot(page, "step-style.png")
                        # A poster the shop likes becomes a saved look beside the built-in ones (stub brief, no spend).
                        page.get_by_text("Créer un style depuis une affiche", exact=True).click()
                        expect(page.get_by_text("Choisissez d’abord une affiche modèle ci-dessus.")).to_be_visible()
                        # A 9:16 model with one format enabled: uploaded, shown, and nothing is asked.
                        Image.new("RGB", (900, 1600), (30, 60, 140)).save(OUTPUT / "model-story-feed-only.png")
                        with page.expect_response("**/api/assets") as uploaded:
                            page.get_by_label("Affiche modèle").set_input_files(OUTPUT / "model-story-feed-only.png")
                        assert (uploaded.value.json()["width"], uploaded.value.json()["height"]) == (900, 1600)
                        expect(page.get_by_alt_text("Affiche modèle pour le nouveau style")).to_be_visible()
                        page.wait_for_function("!document.querySelector('.new-look input[type=file]').disabled")
                        expect(page.locator(".format-ask")).to_have_count(0)
                        with page.expect_response("**/api/assets"):
                            page.get_by_label("Affiche modèle").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
                        expect(page.get_by_alt_text("Affiche modèle pour le nouveau style")).to_be_visible()
                        expect(page.get_by_text("Choisissez d’abord une affiche modèle ci-dessus.")).to_have_count(0)
                        expect(page.locator(".format-ask")).to_have_count(0)
                        page.get_by_label("Nom du style").fill("Vagues bleues")
                        page.get_by_role("button", name="Enregistrer ce style").click()
                        # A paid action is confirmed first, with its cost (a style takes no credit); cancelling does nothing.
                        expect(page.get_by_role("dialog")).to_contain_text("Créer un style depuis cette affiche ?")
                        expect(page.get_by_role("dialog")).to_contain_text("Sans crédit.")
                        check_contrast(page, "paid confirmation")
                        shot(page, "confirm.png", full_page=False)
                        page.get_by_role("dialog").get_by_role("button", name="Annuler").click()
                        assert page.request.get(f"{ORIGIN}/api/looks").json()["items"] == []
                        page.get_by_role("button", name="Enregistrer ce style").click()
                        page.get_by_role("button", name="Créer le style").click()
                        expect(page.get_by_text("Style « Vagues bleues » enregistré", exact=False)).to_be_visible(timeout=15000)
                        # The style's name, emptied by the save, is a field on a field: the lightest field ground of the
                        # dark theme. Its placeholder is measured in both themes (D-POLISH-002).
                        check_contrast(page, "notice", placeholders=("input[name=look]",))
                        page.emulate_media(color_scheme="light")
                        page.wait_for_function("document.documentElement.dataset.theme === 'clair'")
                        check_contrast(page, "notice, light theme", placeholders=("input[name=look]",))
                        page.emulate_media(color_scheme="dark")
                        page.wait_for_function("document.documentElement.dataset.theme === 'sombre'")
                        shot(page, "notice.png", full_page=False)
                        expect(page.get_by_role("button", name="Vagues bleues")).to_have_attribute("aria-pressed", "true")
                        expect(page.get_by_label("Ambiance (modifiable)")).to_have_value(re.compile("vagues translucides"))
                        looks = page.request.get(f"{ORIGIN}/api/looks").json()["items"]
                        assert [item["name"] for item in looks] == ["Vagues bleues"] and looks[0]["brief"]["alignment"] == "left"
                        # The look picker sets the art direction; this flow then tests the editable title layer.
                        page.get_by_role("button", name="Luxe sombre").click()
                        expect(page.get_by_label("Ambiance (modifiable)")).to_have_value(re.compile("Fond noir charbon"))
                        page.screenshot(path=str(OUTPUT / "studio-start.png"), full_page=True)
                        # This style has its own accent colour, but the owner picked red two steps earlier: his colour stays,
                        # and the style's is proposed, one tap away (ADR-073). Taking it and picking red again both work.
                        proposal = page.get_by_text("Ce style propose sa couleur d’accent ; la vôtre est conservée.", exact=False)
                        expect(proposal).to_be_visible()
                        tab("Textes").click()
                        expect(tab("Textes")).to_have_attribute("aria-selected", "true")
                        expect(page.get_by_role("button", name="Rouge", exact=True)).to_have_attribute("aria-pressed", "true")
                        tab("Style").click()
                        page.get_by_role("button", name="Utiliser la couleur du style").click()
                        expect(proposal).to_have_count(0)
                        tab("Textes").click()
                        expect(page.get_by_role("button", name="Or", exact=True)).to_have_attribute("aria-pressed", "true")
                        page.get_by_role("button", name="Rouge", exact=True).click()
                        tab("Style").click()
                        expect(proposal).to_have_count(0)
                        # The request is caught here and refused, so no scene is made by it.
                        asked = []
                        def catch_scene(route):
                            asked.append(route.request.post_data_json)
                            route.fulfill(status=409, content_type="application/json", body='{"detail": {"code": "plan_stale"}}')
                        page.route("**/api/creations/*/scenes", catch_scene)
                        page.get_by_role("button", name="Générer l’affiche").click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        until(lambda: asked)
                        page.unroute("**/api/creations/*/scenes", catch_scene)
                        assert asked[0]["headline"]["signature"] is True and asked[0]["headline"]["signature_align"] == "right", asked
                        assert "brand_text" not in asked[0]["headline"], asked
                        assert asked[0]["headline"]["accent_word"] == accent and asked[0]["headline"]["accent_colour"] == "#D92B2B", asked
                        expect(page.get_by_role("alert")).to_be_visible()
                        # A refusal that names a field opens the step holding that field and is written there.
                        def refuse_contact(route):
                            route.fulfill(status=422, content_type="application/json", body=json.dumps({"error": {
                                "code": "contact_unsupported", "field": "contact", "retryable": False,
                                "message_fr": "Le contact est trop long ou contient un guillemet : l’IA ne peut pas le dessiner."}}))
                        page.route("**/api/creations/*/scenes", refuse_contact)
                        generate.click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(tab("Boutique")).to_have_attribute("aria-selected", "true")
                        expect(page.locator(".panel .refusal")).to_contain_text("Le contact est trop long")
                        shot(page, "refus.png")
                        expect(page.locator(".message.error")).to_have_count(0)
                        page.unroute("**/api/creations/*/scenes", refuse_contact)
                        # Reopening a detail keeps its previous choices.
                        tab("Textes").click()
                        expect(tab("Textes")).to_have_attribute("aria-selected", "true")
                        expect(chips.first).to_have_attribute("aria-pressed", "true")
                        expect(page.get_by_role("button", name="Rouge", exact=True)).to_have_attribute("aria-pressed", "true")
                        page.get_by_label("Laisser l’IA composer le titre dans l’image").uncheck()
                        tab("Style").click()
                        expect(page.get_by_role("button", name="Luxe sombre")).to_have_attribute("aria-pressed", "true")
                        # One tap: the plan is made on the way and reused by the retry below.
                        # Lose the first paid-action response after the server accepted it; retry must reuse its key.
                        def lose_response(route):
                            route.fetch()
                            route.abort("failed")
                            page.unroute("**/api/creations/*/scenes", lose_response)
                        page.route("**/api/creations/*/scenes", lose_response)
                        page.get_by_role("button", name="Générer l’affiche").click()
                        expect(page.get_by_role("dialog")).to_contain_text("Générer l’affiche ?")
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("alert")).to_contain_text("Connexion interrompue")
                        page.get_by_role("button", name="Générer l’affiche").click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)
                        # One agreement covers the listed points (ADR-051): a summary to read, no boxes to tick.
                        expect(page.locator(".file-originals img")).to_be_visible()
                        expect(page.locator(".final-preview .shot img")).to_be_visible()
                        expect(page.locator(".final-preview input[type=checkbox]")).to_have_count(0)
                        page.screenshot(path=str(OUTPUT / "review.png"))
                        check_resting(page, "review at 1440 px", ".shot", ".facts")
                        page.get_by_role("button", name="Signaler un problème").click()
                        expect(page.get_by_role("button", name="Refuser cette version")).to_be_disabled()
                        download_review(page)
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        assert page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["confirmation"]
                        # With a version, the same groups are tabs beside the poster, plus « Réglages »; no step is left.
                        expect(page.get_by_role("tab")).to_have_count(4)
                        expect(offer).to_have_count(0)
                        expect(tab("Réglages")).to_be_enabled()
                        expect(page.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_visible()
                        # The arrow keys move between the tabs.
                        tab("Style").focus()
                        page.keyboard.press("ArrowRight")
                        expect(tab("Réglages")).to_have_attribute("aria-selected", "true")
                        expect(tab("Réglages")).to_be_focused()
                        page.keyboard.press("ArrowRight")
                        expect(tab("Textes")).to_have_attribute("aria-selected", "true")
                        # The position survived the scene request, and a logo ticked now stays clear of the contact.
                        assert footer("contact")["align"] == "right" and footer("contact")["visible"]
                        open_group("Boutique")
                        page.get_by_role("checkbox", name="Logo", exact=True).check()
                        until(lambda: footer("logo") and footer("logo")["visible"])
                        logo, beside = footer("logo"), footer("contact")
                        assert logo["x"] == 896.4 and beside["x"] == 54 and beside["width"] == 972, (logo, beside)
                        assert logo["y"] == 67.5 and logo["y"] + logo["height"] < beside["y"], (logo, beside)
                        expect(page.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_disabled()
                        # « Retirer de l’affiche » (R-POSTER-EDITOR-005): the logo is selected on the poster itself and
                        # taken off; its box in « Boutique » follows, and « Annuler » brings it back.
                        canvas = page.locator(".poster-canvas canvas").first.bounding_box()
                        ratio = canvas["width"] / 1080
                        page.mouse.click(canvas["x"] + (logo["x"] + logo["width"] / 2) * ratio, canvas["y"] + (logo["y"] + logo["height"] / 2) * ratio)
                        remove = page.get_by_role("button", name="Retirer de l’affiche", exact=True)
                        expect(remove).to_be_visible()
                        shot(page, "retirer.png")
                        remove.click()
                        until(lambda: not footer("logo")["visible"])
                        expect(page.get_by_role("checkbox", name="Logo", exact=True)).not_to_be_checked()
                        expect(page.get_by_text("Logo retiré de l’affiche.", exact=False)).to_be_visible()
                        expect(remove).to_have_count(0)
                        page.get_by_role("button", name="Annuler", exact=True).click()
                        until(lambda: footer("logo")["visible"])
                        expect(page.get_by_role("checkbox", name="Logo", exact=True)).to_be_checked()
                        expect(remove).to_be_visible()
                        # The title and the price stay: no removal is offered, and a line says why.
                        elements = page.get_by_role("group", name="Éléments de l’affiche")
                        elements.get_by_role("button", name="Titre", exact=True).click()
                        expect(remove).to_have_count(0)
                        expect(page.get_by_text("Le titre ne se retire pas : une affiche annonce toujours le produit et son prix.")).to_be_visible()
                        elements.get_by_role("button", name="Prix", exact=True).click()
                        expect(remove).to_have_count(0)
                        expect(page.get_by_text("Le prix ne se retire pas", exact=False)).to_be_visible()
                        page.get_by_role("checkbox", name="Logo", exact=True).uncheck()
                        until(lambda: footer("contact")["x"] == 54 and footer("contact")["width"] == 972)
                        jobs = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}/jobs").json()["items"]
                        assert len([job for job in jobs if job["kind"] == "scene"]) == 1
                        scene_before = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]["formats"]["feed"]["scene"]
                        open_group("Textes")
                        page.get_by_label("Prix en ariary", exact=True).fill("95 000")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.get_by_role("button", name="Annuler", exact=True).click()
                        expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("90\u202f000")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.reload()
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("90\u202f000")
                        saved = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert saved["document"]["formats"]["feed"]["scene"] == scene_before
                        visual = page.request.get(f"{ORIGIN}/api/visuals/{scene_before['visual_id']}").json()
                        # The editor no longer sends a separate style-reference image (the API still accepts one).
                        assert visual["style_reference_asset"] is None and len(visual["original_urls"]) == 1
                        expect(page.locator(".coach")).to_contain_text("Vérifiez le produit et le prix")
                        # The chosen version is named, and another one is one confirmed tap away.
                        expect(page.get_by_role("heading", name="Versions 1 sur 12")).to_be_visible()
                        expect(page.get_by_text("Choisie pour l’export", exact=True)).to_be_visible()
                        expect(page.get_by_role("button", name="Nouvelle version")).to_be_enabled()
                        assert page.request.get(f"{ORIGIN}/api/status").json()["spend"]["recorded_micros"] == 0
                        page.locator(".poster-canvas").focus()
                        page.keyboard.press("ArrowRight")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        moved = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert moved["document"]["formats"]["feed"]["layers"][0]["x"] == saved["document"]["formats"]["feed"]["layers"][0]["x"] + 1
                        page.evaluate("scrollTo(0, 0)")
                        page.screenshot(path=str(OUTPUT / "desktop.png"), full_page=True)
                        # On a wide screen the version's badge is not over the poster: it would hide its corner from the pointer.
                        expect(page.locator(".frame .badge")).to_be_hidden()
                        # Each tab holds its own kind of control, and the poster with its main action stays in view.
                        for name, held in (("Boutique", page.get_by_label("Position du contact")), ("Style", page.locator(".look-grid")),
                                           ("Réglages", page.get_by_label("Police", exact=True)), ("Textes", page.get_by_label("Titre", exact=True))):
                            open_group(name)
                            expect(held).to_be_visible()
                            expect(page.get_by_role("tabpanel")).to_have_count(1)
                            expect(page.locator(".poster-canvas canvas").first).to_be_in_viewport()
                            expect(page.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_in_viewport()
                            check_contrast(page, f"tab {name}", ".layer-list button[aria-pressed=true]")
                            shot(page, f"tab-{name.lower().replace('é', 'e')}.png")
                        page.get_by_role("button", name="Passer au thème clair").click()
                        check_contrast(page, "editor, light theme", ".layer-list button[aria-pressed=true]")
                        shot(page, "desktop-clair.png")
                        page.get_by_role("button", name="Passer au thème sombre").click()
                        page.set_viewport_size({"width": 390, "height": 844})
                        expect(page.get_by_label("Titre", exact=True)).to_be_visible()
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        page.screenshot(path=str(OUTPUT / "mobile.png"), full_page=True)
                        check_contrast(page, "editor at phone width")
                        # On a phone the editor's theme button is in « Réglages » (the header gives way to the editor's bar).
                        open_group("Réglages")
                        expect(page.locator(".panel .panel-theme")).to_be_visible()
                        expect(page.locator(".app-header .theme-toggle")).to_be_hidden()
                        toggle_theme(page, "Passer au thème clair")
                        check_contrast(page, "editor at phone width, light theme")
                        shot(page, "mobile-clair.png")
                        toggle_theme(page, "Passer au thème sombre")
                        open_group("Textes")
                        # A second tab changes the saved version. Local work must remain available for a copy.
                        creation_id = page.url.split("#")[1]
                        remote = page.request.get(f"{ORIGIN}/api/creations/{creation_id}").json()
                        remote["document"]["offer"]["title"] = "Titre modifié dans un autre onglet"
                        from uuid import uuid4
                        response = page.request.put(f"{ORIGIN}/api/creations/{creation_id}", data=remote["document"],
                            headers={"Origin": ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "If-Match": f'"{remote["revision"]}"', "Idempotency-Key": str(uuid4())})
                        assert response.status == 200
                        page.get_by_label("Titre", exact=True).fill("Mon titre conservé")
                        # With a mouse there is no on-screen keyboard: the poster does not collapse for a focused field.
                        assert not page.evaluate("matchMedia('(pointer: coarse)').matches")
                        expect(page.locator(".editor.typing")).to_have_count(0)
                        expect(page.get_by_role("button", name="Conserver mes modifications dans une copie")).to_be_visible(timeout=10000)
                        page.get_by_role("button", name="Conserver mes modifications dans une copie").click()
                        expect(page.get_by_text("Vos modifications ont été conservées dans une copie.")).to_be_visible()
                        assert page.url.split("#")[1] != creation_id
                        expect(page.get_by_label("Titre", exact=True)).to_have_value("Mon titre conservé")
                        # Layer-level editing lives in the « Réglages » tab; the instruction is in view there, in no closed section.
                        open_group("Réglages")
                        # The stub proposal is explicitly labelled as a simulation and needs an apply decision.
                        expect(page.get_by_text("Ajuster ce texte avec une consigne", exact=True)).to_be_visible()
                        expect(page.get_by_text("Écrivez d’abord votre consigne ci-dessus.")).to_be_visible()
                        page.get_by_label("Votre consigne").fill("Une couleur dorée")
                        before_polish = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        page.get_by_role("button", name="Proposer un ajustement", exact=True).click()
                        # Every paid call is confirmed with its cost first (a text proposal takes no credit); Escape or
                        # "Annuler" backs out.
                        expect(page.get_by_role("dialog")).to_contain_text("Sans crédit.")
                        page.keyboard.press("Escape")
                        expect(page.get_by_role("dialog")).to_have_count(0)
                        page.get_by_role("button", name="Proposer un ajustement", exact=True).click()
                        page.get_by_role("button", name="Lancer la proposition", exact=True).click()
                        expect(page.get_by_role("button", name="Appliquer au texte")).to_be_visible(timeout=15000)
                        unchanged = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert unchanged == before_polish
                        page.get_by_role("button", name="Appliquer au texte").click()
                        expect(page.get_by_role("button", name="Appliquer au texte")).to_have_count(0)
                        after_polish = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        expected = copy.deepcopy(before_polish["document"])
                        next(layer for layer in expected["formats"]["feed"]["layers"] if layer["role"] == "title")["fill"] = "#FFCC66"
                        assert after_polish["document"] == expected
                        check_material_pixels(page, expected)
                        page.get_by_role("button", name="Générer la matière du texte", exact=True).click()
                        page.get_by_role("button", name="Générer la matière", exact=True).click()
                        expect(page.get_by_role("button", name="Appliquer la matière", exact=True)).to_be_visible(timeout=15000)
                        still = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert still == after_polish
                        page.get_by_role("button", name="Appliquer la matière", exact=True).click()
                        expect(page.get_by_role("button", name="Retirer la matière du texte", exact=True)).to_be_visible()
                        with_effect = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        effect_id = next(layer for layer in with_effect["document"]["formats"]["feed"]["layers"] if layer["role"] == "title")["texture_effect_id"]
                        assert effect_id
                        expected_effect = copy.deepcopy(expected)
                        next(layer for layer in expected_effect["formats"]["feed"]["layers"] if layer["role"] == "title")["texture_effect_id"] = effect_id
                        assert with_effect["document"] == expected_effect
                        page.get_by_role("button", name="Annuler", exact=True).click()
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        undone = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert undone["document"] == expected
                        # Reference typography is a manual single-layer edit, saved and undoable without generation.
                        page.get_by_role("group", name="Élément à régler").get_by_role("button", name="Prix", exact=True).click()
                        # The chosen look already dressed the price as its dark pill, at half the canvas width.
                        auto_pill = next(layer for layer in expected["formats"]["feed"]["layers"] if layer["role"] == "price")
                        assert auto_pill["price_badge"] == {"fill": "#111114", "border_start": "#C8A45A", "border_end": "#C8A45A"}
                        assert (auto_pill["width"], auto_pill["x"], auto_pill["fill"]) == (540, 270, "#FFFFFF")
                        expect(page.get_by_label("Présentation du prix", exact=True)).to_have_value("capsule")
                        page.get_by_label("Présentation du prix", exact=True).select_option("simple")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        expected = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]
                        page.get_by_label("Police", exact=True).select_option("montserrat-black-italic")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.get_by_label("Présentation du prix", exact=True).select_option("capsule")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        styled = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        expected_styled = copy.deepcopy(expected)
                        price_layer = next(layer for layer in expected_styled["formats"]["feed"]["layers"] if layer["role"] == "price")
                        # The look left white digits, so the new capsule is dark: the price must stay readable.
                        assert price_layer["fill"] == "#FFFFFF"
                        price_layer.update(font_id="montserrat-black-italic", weight=900,
                                           price_badge={"fill": "#22262E", "border_start": "#009FE3", "border_end": "#1853BD"})
                        assert styled["document"] == expected_styled, (styled["document"], expected_styled)
                        runs = page.evaluate("""async doc => {
                            const { textRuns } = await import('/src/canvas.ts');
                            return textRuns(doc, doc.formats.feed.layers.find(layer => layer.role === 'price'));
                        }""", styled["document"])
                        assert [run["text"] for run in runs] == ["90\u00a0000", "AR"]
                        assert runs[0]["fontStyle"] == "italic 900" and runs[1]["fontStyle"] == "400"
                        assert runs[1]["fontSize"] < runs[0]["fontSize"]
                        page.get_by_role("button", name="Annuler", exact=True).click()
                        expect(page.get_by_label("Présentation du prix", exact=True)).to_have_value("simple")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.get_by_role("button", name="Rétablir", exact=True).click()
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.reload()
                        expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("90\u202f000")
                        open_group("Réglages")
                        page.get_by_role("group", name="Élément à régler").get_by_role("button", name="Prix", exact=True).click()
                        expect(page.get_by_label("Police", exact=True)).to_have_value("montserrat-black-italic")
                        expect(page.get_by_label("Présentation du prix", exact=True)).to_have_value("capsule")
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        assert page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"] == expected_styled
                        assert page.request.get(f"{ORIGIN}/api/status").json()["spend"]["recorded_micros"] == 0
                        page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
                        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=40000)
                        preview_url = page.locator(".final-preview .shot img").get_attribute("src")
                        preview_bytes = page.request.get(ORIGIN + preview_url).body()
                        expect(page.locator(".final-preview")).to_contain_text(re.compile("vérifiez le prix", re.IGNORECASE))
                        expect(page.locator(".final-preview input[type=checkbox]")).to_have_count(0)
                        expect(page.locator(".final-preview .shot img")).to_be_visible()
                        page.screenshot(path=str(OUTPUT / "final-mobile.png"))
                        check_contrast(page, "final screen at phone width")
                        confirm_final = page.locator(".final-preview").get_by_role("button", name="Confirmer et télécharger le PNG", exact=True)
                        expect(confirm_final).to_be_enabled()
                        check_primary(page, "final panel", confirm_final)
                        check_resting(page, "final panel", ".shot", ".facts")
                        page.set_viewport_size({"width": 360, "height": 640})
                        check_file_actions(page.locator(".final-preview"), confirm_final)
                        page.set_viewport_size({"width": 1440, "height": 1050})
                        page.screenshot(path=str(OUTPUT / "final.png"))
                        page.set_viewport_size({"width": 390, "height": 844})
                        # A refusal while this panel is open is written above it, not in the groups that are inert behind it.
                        failed_downloads = []
                        page.once("download", lambda event: failed_downloads.append(event))
                        page.route("**/api/creations/*/confirmations", lambda route: route.fulfill(status=409, content_type="application/json", body='{"error":{"code":"price_stale","message_fr":"Le prix dessiné dans l’image ne correspond plus au prix de l’affiche.","retryable":false}}'))
                        page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
                        expect(page.locator(".message.error")).to_contain_text("ne correspond plus au prix")
                        expect(page.locator(".message.error")).to_be_in_viewport()
                        assert not failed_downloads
                        page.unroute("**/api/creations/*/confirmations")
                        download_review(page)
                        link = page.get_by_role("link", name="Télécharger le PNG")
                        expect(link).to_be_visible()
                        downloaded = page.request.get(ORIGIN + link.get_attribute("href"))
                        assert downloaded.status == 200 and downloaded.body() == preview_bytes
                        assert Image.open(io.BytesIO(preview_bytes)).size == (1080, 1350)
                        (OUTPUT / "confirmed-stub-poster.png").write_bytes(preview_bytes)
                        # The page behind an open panel is inert: close it, change the price, and reopen by reloading.
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        open_group("Textes")
                        page.get_by_label("Prix en ariary", exact=True).fill("91 000")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.reload()
                        expect(link).to_be_visible()
                        # A confirmed poster offers no second confirmation; the server's
                        # preview_stale refusal is covered in backend/tests/test_exports.py.
                        expect(page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True)).to_have_count(0)
                        expect(page.locator(".final-preview .points")).to_have_count(0)
                        assert page.request.get(ORIGIN + link.get_attribute("href")).body() == preview_bytes
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        page.get_by_label("Titre", exact=True).fill("Écouteurs " * 25)
                        expect(page.get_by_text("Le texte dépasse son cadre.", exact=False)).to_be_visible()
                        page.get_by_label("Titre", exact=True).fill("Son 🎵")
                        expect(page.get_by_text("Cette police ne contient pas tous les caractères du texte.")).to_be_visible()
                        # "Mes affiches" shows each poster itself: the confirmed one by its final preview.
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.set_viewport_size({"width": 1440, "height": 1000})
                        go(page, "Mes affiches")
                        # The view is in the address: a reload stays on the list.
                        assert page.url.endswith("#affiches"), page.url
                        page.reload()
                        thumbnail = page.locator('.library-item img[src^="/api/thumbnails/"]').first
                        expect(thumbnail).to_be_visible()
                        check_contrast(page, "Mes affiches")
                        check_resting(page, "Mes affiches", ".rows")
                        # At 360 px both library filters and the creation action stay in reach.
                        page.set_viewport_size({"width": 360, "height": 740})
                        heading = page.get_by_role("heading", name="Mes affiches", exact=True).bounding_box()
                        removed = page.get_by_role("button", name="Retirées", exact=True).bounding_box()
                        assert heading["y"] + heading["height"] <= removed["y"] + 1, (heading, removed)
                        expect(page.locator(".library-heading").get_by_role("button", name="Nouvelle affiche")).to_be_in_viewport()
                        assert page.evaluate(NO_SIDEWAYS)
                        shot(page, "mes-affiches-360.png", full_page=False)
                        page.set_viewport_size({"width": 1440, "height": 1000})
                        page.get_by_role("button", name="Passer au thème clair").click()
                        check_contrast(page, "Mes affiches, light theme")
                        page.get_by_role("button", name="Passer au thème sombre").click()
                        expect(thumbnail).to_be_visible()
                        # A small resized image of the 1080 x 1350 preview, not the full file.
                        page.wait_for_function("image => image.complete && image.naturalWidth === 320 && image.naturalHeight === 400", arg=thumbnail.element_handle())
                        assert len(page.request.get(ORIGIN + thumbnail.get_attribute("src")).body()) < 40_000
                        page.screenshot(path=str(OUTPUT / "mes-affiches.png"))
                        # Managing the list (R-CREATION-LIBRARY-003): state in words, copy, remove with confirmation, restore.
                        rows = page.locator(".library-row")
                        before = rows.count()
                        expect(page.locator(".library-item .badge").first).to_have_text(re.compile("Brouillon|À vérifier|Approuvée|Confirmée"))
                        expect(page.locator("aside.side .nav a", has_text="Mes affiches")).to_contain_text(str(before))
                        options = rows.first.get_by_role("button", name=re.compile("^Actions pour"))
                        duplicate = rows.first.get_by_role("button", name=re.compile("^Dupliquer"))
                        expect(duplicate).to_have_count(0)
                        options.focus()
                        page.keyboard.press("Enter")
                        page.keyboard.press("Tab")
                        expect(duplicate).to_be_focused()
                        page.keyboard.press("Escape")
                        expect(options).to_be_focused()
                        expect(options).to_have_attribute("aria-expanded", "false")
                        options.click()
                        duplicate.click()
                        expect(page.locator(".poster-canvas canvas").first).to_be_visible()
                        copy_id = page.url.split("#")[1]
                        go(page, "Mes affiches")
                        expect(rows).to_have_count(before + 1)
                        options.click()
                        rows.first.get_by_role("button", name=re.compile("^Retirer")).click()
                        page.get_by_role("dialog").get_by_role("button", name="Annuler", exact=True).click()
                        expect(options).to_be_focused()
                        options.click()
                        rows.first.get_by_role("button", name=re.compile("^Retirer")).click()
                        expect(page.get_by_role("dialog")).to_contain_text("Rien n’est effacé")
                        page.get_by_role("dialog").get_by_role("button", name="Retirer de la liste").click()
                        expect(rows).to_have_count(before)
                        # A removed poster is not opened by its address: the list of removed posters is shown instead.
                        page.goto(f"{ORIGIN}/#{copy_id}")
                        expect(page.get_by_text("Cette affiche a été retirée de la liste.", exact=False)).to_be_visible()
                        expect(page.get_by_role("button", name="Retirées", exact=True)).to_have_attribute("aria-pressed", "true")
                        expect(rows).to_have_count(1)
                        options.click()
                        expect(rows.first.get_by_role("button", name=re.compile("^Dupliquer"))).to_be_visible()
                        rows.first.get_by_role("button", name=re.compile("^Remettre")).click()
                        expect(rows).to_have_count(0)
                        page.get_by_role("button", name="Actives", exact=True).click()
                        expect(rows).to_have_count(before + 1)
                        assert page.request.get(f"{ORIGIN}/api/status").json()["spend"]["recorded_micros"] == 0
                        # The logo as a round seal (ADR-057): a new poster with the logo and the contact, no shop name.
                        go(page, "Nouvelle affiche")
                        expect(page.get_by_label("Photos du produit")).to_be_enabled()  # the way back is over
                        page.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
                        expect(page.locator(".photo-strip img")).to_have_count(1)
                        page.get_by_label("Nom du produit", exact=True).fill("Soundcore R50i sceau")
                        page.get_by_label("Variante confirmée").fill("Noir")
                        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
                        page.get_by_label("Les photos correspondent").check()
                        page.locator(".intake details > summary").click()
                        expect(page.get_by_role("checkbox", name="Logo", exact=True)).not_to_be_checked()
                        page.get_by_role("checkbox", name="Logo", exact=True).check()
                        page.get_by_role("checkbox", name="Contact", exact=True).check()
                        expect(page.get_by_role("checkbox", name="Nom de la boutique", exact=True)).not_to_be_checked()
                        page.get_by_role("button", name="Préparer mon affiche").click()
                        expect(page.get_by_role("heading", name="Soundcore R50i sceau", exact=True)).to_be_visible()
                        # The seal is an explicit choice; new posters keep the original rectangular logo by default.
                        # The main generation action stays reachable on a phone while each optional section remains editable.
                        expect(tab("Style")).to_have_attribute("aria-selected", "true")
                        page.set_viewport_size({"width": 360, "height": 740})
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        expect(generate).to_be_in_viewport()
                        open_group("Textes")
                        expect(page.get_by_label("Titre", exact=True)).to_be_visible()
                        check_contrast(page, "step Textes at phone width")
                        shot(page, "step-textes-mobile.png", full_page=False)
                        open_group("Boutique")
                        seal_option = page.get_by_label("Logo en sceau rond dans l’image")
                        expect(seal_option).not_to_be_checked()
                        seal_option.check()
                        expect(seal_option).to_be_checked()
                        expect(page.get_by_label("Position du contact")).to_be_disabled()
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        shot(page, "step-boutique-mobile.png", full_page=False)
                        page.get_by_role("button", name="Voir l’affiche", exact=True).click()
                        sheet = page.get_by_role("dialog", name="Affiche")
                        expect(sheet).to_be_visible()
                        expect(sheet.locator(".poster-canvas canvas").first).to_be_in_viewport()
                        page.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().width > 250")
                        check_contrast(page, "poster opened over a step")
                        shot(page, "step-affiche-mobile.png", full_page=False)
                        sheet.get_by_role("button", name="Revenir aux réglages").click()
                        expect(page.get_by_role("dialog")).to_have_count(0)
                        expect(tab("Boutique")).to_have_attribute("aria-selected", "true")
                        expect(seal_option).to_be_checked()
                        # From the poster sheet, taking the contact off and following the link back: the sheet closes and the
                        # « Boutique » step shows the unticked box (the link used to change the group behind the sheet only).
                        page.get_by_role("button", name="Voir l’affiche", exact=True).click()
                        sheet.get_by_role("group", name="Éléments de l’affiche").get_by_role("button", name="Contact").click()
                        sheet.get_by_role("button", name="Retirer de l’affiche").click()
                        sheet.get_by_role("button", name="Le remettre depuis « Boutique »").click()
                        expect(page.get_by_role("dialog")).to_have_count(0)
                        expect(tab("Boutique")).to_have_attribute("aria-selected", "true")
                        expect(page.get_by_role("checkbox", name="Contact", exact=True)).not_to_be_checked()
                        page.get_by_role("checkbox", name="Contact", exact=True).check()
                        expect(seal_option).to_be_checked()
                        toggle_theme(page, "Passer au thème clair", hidden=True)
                        check_contrast(page, "step Boutique at phone width, light theme")
                        shot(page, "step-boutique-mobile-clair.png", full_page=False)
                        toggle_theme(page, "Passer au thème sombre", hidden=True)
                        open_group("Style")
                        expect(generate).to_be_in_viewport()
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        shot(page, "step-style-mobile.png", full_page=False)
                        # Generated from the phone's bottom bar, confirmed and reviewed at 360 px (the bar was never used at phone width).
                        sent = []
                        page.on("request", lambda request: sent.append(request.post_data_json) if request.method == "POST" and request.url.endswith("/scenes") else None)
                        generate.click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)
                        assert sent[-1]["headline"]["logo_seal"] is True and sent[-1]["headline"]["signature_align"] == "right", sent[-1]
                        expect(page.get_by_text("Le logo doit recouvrir tout son disque", exact=False)).to_be_visible()
                        # The rendered image and its actions share one scrollable panel on a short phone.
                        approve = page.locator(".final-preview").get_by_role("button", name="Confirmer et télécharger le PNG", exact=True)
                        expect(page.locator(".final-preview .shot img")).to_be_visible()
                        shot(page, "review-mobile.png", full_page=False)
                        page.set_viewport_size({"width": 360, "height": 640})
                        check_file_actions(page.locator(".final-preview"), approve, page.get_by_role("button", name="Signaler un problème"))
                        page.set_viewport_size({"width": 360, "height": 740})
                        download_review(page)
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        assert page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["confirmation"]
                        page.set_viewport_size({"width": 1440, "height": 1000})
                        sealed = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]
                        disc = page.request.get(f"{ORIGIN}/api/visuals/{sealed['formats']['feed']['scene']['visual_id']}").json()["logo_disc"]
                        seal = footer("logo")
                        assert disc and seal["shape"] == "circle" and seal["visible"] and abs(seal["width"] - disc["d"] - 4) < .1, (disc, seal)
                        assert abs(seal["x"] + seal["width"] / 2 - disc["x"]) < .1 and abs(seal["y"] + seal["height"] / 2 - disc["y"]) < .1
                        # What this version's image holds is never erased (R-POSTER-EDITOR-005): for the seal on its disc and
                        # for the drawn contact the poster says so and offers the next version, not a removal.
                        elements = page.get_by_role("group", name="Éléments de l’affiche")
                        leave_out = page.get_by_role("button", name="Ne plus le mettre dans la prochaine version")
                        elements.get_by_role("button", name="Logo", exact=True).click()
                        expect(page.get_by_text("un disque dessiné dans l’image de cette version", exact=False)).to_be_visible()
                        expect(leave_out).to_be_visible()
                        expect(page.get_by_role("button", name="Retirer de l’affiche", exact=True)).to_have_count(0)
                        elements.get_by_role("button", name="Contact (dans l’image)", exact=True).click()
                        expect(page.get_by_text("L’image de cette version contient le contact", exact=False)).to_be_visible()
                        expect(leave_out).to_be_visible()
                        expect(page.get_by_role("button", name="Retirer de l’affiche", exact=True)).to_have_count(0)
                        # The seal is locked once a version exists; removing the logo would leave an empty disc, so export is blocked.
                        open_group("Boutique")
                        expect(seal_option).to_be_disabled()
                        page.get_by_role("checkbox", name="Logo", exact=True).uncheck()
                        until(lambda: not footer("logo")["visible"])
                        expect(page.get_by_text("L’image contient un disque prévu pour le logo", exact=False)).to_be_visible()
                        expect(page.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_disabled()
                        # The reason beside the blocked action opens the group that holds the fix.
                        open_group("Textes")
                        page.locator(".main-action .why").get_by_role("button", name="Ouvrir « Boutique »").click()
                        expect(tab("Boutique")).to_have_attribute("aria-selected", "true")
                        page.get_by_role("checkbox", name="Logo", exact=True).check()
                        until(lambda: footer("logo")["visible"] and abs(footer("logo")["x"] - seal["x"]) < .1)
                        expect(page.get_by_text("L’image contient un disque prévu pour le logo", exact=False)).to_have_count(0)
                        page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
                        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=40000)
                        expect(page.get_by_text("Le logo doit recouvrir tout son disque.", exact=True)).to_be_visible()
                        expect(page.locator(".final-preview .shot img")).to_be_visible()
                        page.screenshot(path=str(OUTPUT / "seal-final.png"))
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        # Selecting a historical disc scene repairs even a plain logo moved away from it.
                        seal_endpoint = f"{ORIGIN}/api/creations/{page.url.split('#')[1]}"
                        historical = page.request.get(seal_endpoint).json()
                        altered = copy.deepcopy(historical['document'])
                        moved_logo = next(l for l in altered['formats']['feed']['layers'] if l['role'] == 'logo')
                        moved_logo.pop('shape', None)
                        moved_logo.update(x=54, y=67.5)
                        response = page.request.put(seal_endpoint, data=altered, headers={"Origin": ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "If-Match": f'"{historical["revision"]}"', "Idempotency-Key": str(uuid4())})
                        assert response.ok, response.text()
                        page.reload()
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        expect(page.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_disabled()
                        page.get_by_role("button", name=re.compile(r"^Choisir la version 1")).click()
                        expect(page.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_enabled()
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible()
                        assert next(l for l in page.request.get(seal_endpoint).json()['document']['formats']['feed']['layers'] if l['role'] == 'logo')['shape'] == 'circle'
                        # Converting an existing seal makes a new composition and preserves its source.
                        original_seal_id = page.url.split('#')[1]
                        original_seal = page.request.get(f"{ORIGIN}/api/creations/{original_seal_id}").json()
                        open_group("Boutique")
                        page.get_by_role("button", name="Créer une copie avec le logo en haut").click()
                        expect(page.get_by_role("button", name="En haut à droite", exact=True)).to_have_attribute("aria-pressed", "true")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible()
                        copied_seal = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert copied_seal['id'] != original_seal_id and copied_seal['document']['input_id'] != original_seal['document']['input_id']
                        assert copied_seal['document']['formats']['feed']['scene']['visual_id'] is None
                        assert next(l for l in copied_seal['document']['formats']['feed']['layers'] if l['role'] == 'logo').get('shape') != 'circle'
                        assert page.request.get(f"{ORIGIN}/api/creations/{original_seal_id}").json() == original_seal
                        # Managing styles (R-CREATION-LIBRARY-004): open, rename with its refusals, remove with confirmation.
                        page.locator(".final-preview").wait_for(state="detached")
                        go(page, "Styles")
                        cards = page.locator(".look-card")
                        expect(cards).to_have_count(4)
                        check_resting(page, "Styles", ".look-card")
                        cards.filter(has_text="Studio clair").click()
                        panel = page.get_by_role("dialog")
                        expect(panel).to_contain_text("ne peut pas être renommé ni retiré")
                        expect(panel.get_by_role("button", name="Retirer ce style")).to_have_count(0)
                        page.keyboard.press("Escape")
                        cards.filter(has_text="Vagues bleues").click()
                        expect(panel).to_contain_text("Ambiance")
                        panel.get_by_label("Nom du style").fill("Luxe sombre")
                        panel.get_by_role("button", name="Renommer").click()
                        expect(panel.get_by_role("alert")).to_contain_text("style fourni")
                        panel.get_by_label("Nom du style").fill("Vagues du soir")
                        panel.get_by_role("button", name="Renommer").click()
                        expect(panel.get_by_role("heading", name="Vagues du soir")).to_be_visible()
                        panel.get_by_role("button", name="Retirer ce style").click()
                        expect(page.locator(".confirm")).to_contain_text("le gardent")
                        page.locator(".confirm").get_by_role("button", name="Retirer ce style").click()
                        expect(cards).to_have_count(3)
                        expect(page.locator("aside.side .nav a", has_text="Styles")).to_contain_text("3")
                        assert page.request.get(f"{ORIGIN}/api/looks").json()["items"] == []
                        assert page.request.get(f"{ORIGIN}/api/status").json()["spend"]["recorded_micros"] == 0
                        page.screenshot(path=str(OUTPUT / "styles.png"))
                        assert not errors, errors
                        (OUTPUT / "result.json").write_text(json.dumps({"ok": True, "revision": saved["revision"], "page_errors": errors}, indent=2), encoding="utf-8")
                        # A small product photo (first thing met on the live pilot, 2026-11-13: a 474 px picture). It is said at the
                        # upload, and the paid confirmation asks for the agreement itself instead of failing with a vague message.
                        go(page, "Nouvelle affiche")
                        Image.new("RGB", (474, 474), (200, 200, 205)).save(OUTPUT / "small.png")
                        expect(page.get_by_label("Photos du produit")).to_be_enabled()  # the way back is over
                        page.get_by_label("Photos du produit").set_input_files(OUTPUT / "small.png")
                        expect(page.get_by_text("Photo petite", exact=False)).to_be_visible()
                        page.get_by_label("Nom du produit", exact=True).fill("Petite photo")
                        page.get_by_label("Variante confirmée").fill("Gris")
                        # A price written as in Madagascar: « 10.000 Ar » is 10 000 ariary.
                        page.get_by_label("Prix en ariary", exact=True).fill("10.000 Ar")
                        page.get_by_label("Les photos correspondent").check()
                        page.get_by_role("button", name="Préparer mon affiche").click()
                        expect(page.get_by_role("heading", name="Petite photo", exact=True)).to_be_visible()
                        assert page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]["offer"]["price_ar"] == 10000
                        # Either invalid field blocks generation from another tab; its repair link focuses the actual input.
                        open_group("Textes")
                        admissions_before = len(admissions)
                        price = page.get_by_label("Prix en ariary", exact=True)
                        price.fill("prix inconnu")
                        expect(price).to_have_attribute("aria-invalid", "true")
                        open_group("Style")
                        expect(generate).to_be_disabled()
                        repair = page.locator(".step-nav .why").get_by_role("button", name="Ouvrir « Textes »")
                        repair.click()
                        expect(price).to_be_focused()
                        price.fill("10 000")
                        page.get_by_label("Titre", exact=True).fill('Petite photo 32"')
                        expect(page.locator("#erreur-titre")).to_contain_text("contient un guillemet droit")
                        open_group("Style")
                        expect(generate).to_be_disabled()
                        expect(page.locator(".step-nav .why")).to_contain_text("contient un guillemet droit")
                        check_contrast(page, "blocked main action")
                        shot(page, "bloque.png")
                        repair.click()
                        expect(tab("Textes")).to_have_attribute("aria-selected", "true")
                        expect(page.get_by_label("Titre", exact=True)).to_be_focused()
                        page.get_by_label("Titre", exact=True).fill("Petite photo")
                        expect(page.get_by_text("contient un guillemet droit", exact=False)).to_have_count(0)
                        tab("Style").click()
                        expect(page.get_by_role("button", name="Générer l’affiche")).to_be_enabled()
                        expect(page.locator(".step-nav .why")).to_have_count(0)
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        assert len(admissions) == admissions_before
                        agree = page.get_by_role("dialog").get_by_label("J’accepte une qualité réduite", exact=False)
                        page.get_by_role("button", name="Générer l’affiche").click()
                        expect(agree).to_be_visible()
                        confirm = page.get_by_role("button", name="Lancer la génération")
                        expect(confirm).to_be_disabled()
                        expect(page.get_by_role("dialog").get_by_role("button", name="Annuler")).to_be_focused()
                        page.keyboard.press("Tab")
                        expect(agree).to_be_focused()
                        page.keyboard.press("Space")
                        expect(agree).to_be_checked()
                        page.keyboard.press("Tab")
                        expect(confirm).to_be_focused()
                        page.keyboard.press("Escape")
                        # After a reload the editor no longer knows the photo is small: the server refuses, and the same dialog
                        # comes back with the agreement. No generation starts without it.
                        source_read = "**/api/product-inputs/*"
                        page.route(source_read, lambda route: route.fulfill(status=503, json={"error": {"code": "unavailable"}}))
                        page.reload()
                        expect(page.get_by_role("heading", name="Petite photo", exact=True)).to_be_visible()
                        expect(offer).to_contain_text("Les photos et la variante sont indisponibles.")
                        expect(offer).to_contain_text("Petite photo")
                        expect(offer).to_contain_text(re.compile(r"10\s000\s*Ar", re.IGNORECASE))
                        expect(generate).to_be_disabled()
                        page.unroute(source_read)
                        offer.get_by_role("button", name="Recharger le produit").click()
                        expect(offer).to_contain_text("Gris")
                        expect(offer.locator("img").first).to_be_visible()
                        page.wait_for_function("img => img.complete && img.naturalWidth > 0", arg=offer.locator("img").first.element_handle())
                        expect(generate).to_be_enabled()
                        assert len(admissions) == admissions_before
                        before = len(sent)
                        expect(tab("Style")).to_have_attribute("aria-selected", "true")
                        page.get_by_role("button", name="Générer l’affiche").click()
                        expect(agree).to_have_count(0)
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(agree).to_be_visible()
                        expect(page.get_by_role("button", name="Lancer la génération")).to_be_disabled()
                        assert sent[before]["acknowledged_warnings"] == [], sent[before]
                        agree.check()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)
                        assert sent[-1]["acknowledged_warnings"] == ["low_resolution"], sent[-1]
                        # The phone-first editor (R-POSTER-EDITOR-007, D-POSTER-EDITOR-005 part A) on a low-end Android
                        # phone: 360 × 740 with a touch pointer, same session.
                        phone = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True,
                                                    color_scheme="dark", storage_state=page.context.storage_state())
                        mobile = phone.new_page()
                        mobile.set_default_timeout(10000)
                        mobile.on("pageerror", lambda error: errors.append(str(error)))
                        mobile.goto(ORIGIN + "/#etapes")
                        no_sideways = "document.documentElement.scrollWidth <= innerWidth"
                        assert mobile.evaluate("matchMedia('(pointer: coarse)').matches")
                        # Outside the editor the destinations are a bar at the bottom, the current one marked (« Nouvelle
                        # affiche » never is: D-REDESIGN-002); the top bar blurs by its ::before only, the bar itself does;
                        # the page ends above it.
                        nav = mobile.locator(".phone-bar")
                        expect(nav).to_be_visible()
                        expect(mobile.get_by_label("Photos du produit")).to_be_attached()
                        bottom_bar = nav.bounding_box()
                        assert abs(bottom_bar["y"] + bottom_bar["height"] - 740) < 1 and bottom_bar["width"] == 360, bottom_bar
                        expect(nav.locator("a[aria-current=page]")).to_have_count(0)
                        assert all(link.bounding_box()["height"] >= 44 for link in nav.locator("a").all())
                        assert mobile.evaluate(blur, ".app-header") == "none" and mobile.evaluate(blur, ".phone-bar") != "none"
                        assert mobile.evaluate("parseFloat(getComputedStyle(document.querySelector('main')).paddingBottom)") >= bottom_bar["height"]
                        mobile.wait_for_function(no_sideways)
                        check_contrast(mobile, "intake at 360 px with the bottom navigation")
                        shot(mobile, "phone-intake.png", full_page=False)
                        toggle_theme(mobile, "Passer au thème clair")
                        check_contrast(mobile, "intake at 360 px, light theme")
                        toggle_theme(mobile, "Passer au thème sombre")
                        go(mobile, "Mes affiches", tap=True)
                        expect(nav.locator("a[aria-current=page]")).to_contain_text("Mes affiches")
                        go(mobile, "Nouvelle affiche", tap=True)
                        expect(mobile.get_by_label("Photos du produit")).to_be_enabled()  # the way back is over
                        mobile.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
                        expect(mobile.locator(".photo-strip img")).to_have_count(1)
                        mobile.get_by_label("Nom du produit", exact=True).fill("Soundcore R50i téléphone")
                        mobile.get_by_label("Prix en ariary", exact=True).fill("90 000")
                        mobile.get_by_label("Les photos correspondent").check()
                        mobile.get_by_role("button", name="Préparer mon affiche").tap()
                        expect(mobile.get_by_role("heading", name="Soundcore R50i téléphone", exact=True)).to_be_visible()
                        # One bar at the top of the editor: back, name, save state, undo, redo; the header, the bottom
                        # navigation and the long demo notice leave; the bar stays on top while the step scrolls.
                        back = mobile.get_by_role("link", name="Retour à Mes affiches")
                        expect(back).to_be_visible()
                        expect(mobile.locator(".app-header")).to_be_hidden()
                        expect(nav).to_be_hidden()
                        expect(mobile.locator(".demo-notice")).to_be_hidden()
                        expect(mobile.locator(".titlerow.bar .demo-badge")).to_have_text("Démo")
                        top_bar = mobile.locator(".titlerow.bar")
                        assert top_bar.bounding_box()["y"] == 0 and 50 <= top_bar.bounding_box()["height"] <= 64, top_bar.bounding_box()
                        assert back.bounding_box()["height"] >= 44
                        expect(mobile.get_by_role("tab", name="Style", exact=True)).to_have_attribute("aria-selected", "true")
                        expect(mobile.get_by_role("region", name="Offre à générer")).to_contain_text("Soundcore R50i téléphone")
                        expect(mobile.get_by_role("button", name="Générer l’affiche")).to_be_in_viewport()
                        mobile.wait_for_function(no_sideways)
                        check_contrast(mobile, "preparation at 360 px with a touch pointer")
                        shot(mobile, "phone-preparation.png", full_page=False)
                        mobile.evaluate("scrollTo({ top: 400, behavior: 'instant' })")
                        assert top_bar.bounding_box()["y"] == 0
                        mobile.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
                        mobile.get_by_role("button", name="Voir l’affiche", exact=True).tap()
                        sheet = mobile.get_by_role("dialog", name="Affiche")
                        expect(sheet).to_be_visible()
                        expect(sheet.locator(".poster-canvas canvas").first).to_be_in_viewport()
                        expect(sheet.locator(".frame .badge")).to_have_text("Aperçu")
                        expect(sheet.locator(".frame .badge")).to_be_hidden()
                        sheet.get_by_role("button", name="Revenir aux réglages").tap()
                        expect(mobile.get_by_role("dialog")).to_have_count(0)
                        mobile.get_by_role("button", name="Générer l’affiche").tap()
                        mobile.get_by_role("button", name="Lancer la génération").tap()
                        expect(mobile.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)
                        preview = mobile.locator(".final-preview")
                        expect(preview.locator(".shot img")).to_be_visible()
                        expect(preview.get_by_alt_text("Photo originale 1 à comparer")).to_be_visible()
                        check_contrast(mobile, "single review at 360 px")
                        shot(mobile, "phone-review.png", full_page=False)
                        download_review(mobile)
                        preview.get_by_role("button", name="Fermer").tap()
                        expect(mobile.get_by_role("tab")).to_have_count(4)
                        # Once a version exists the real image stays on screen, compact (at least 140 px here), while the controls
                        # scroll under it; its state badge is in front; the versions are a row of small thumbnails under
                        # it; the groups are a row of tools with icons; nothing scrolls sideways.
                        canvas_phone = mobile.locator(".poster-canvas canvas").first
                        poster_box = lambda: canvas_phone.bounding_box()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 140")
                        expect(canvas_phone).to_be_in_viewport(ratio=1)
                        state_badge = mobile.locator(".frame .badge")
                        expect(state_badge).to_have_text("Version 1 · approuvée")
                        assert topmost(state_badge)
                        mobile.get_by_role("button", name=re.compile(r"^Versions ")).tap()
                        thumb = mobile.locator(".version img").first.bounding_box()
                        assert (round(thumb["width"]), round(thumb["height"])) == (56, 70), thumb
                        assert thumb["y"] > poster_box()["y"] + poster_box()["height"]
                        expect(mobile.locator(".versions .state").first).to_have_text("Approuvée")
                        mobile.get_by_role("button", name=re.compile(r"^Versions ")).tap()
                        expect(mobile.locator(".tab .tool")).to_have_count(4)
                        assert all(tool.is_visible() for tool in mobile.locator(".tab .tool").all())
                        assert all(item.bounding_box()["height"] >= 44 for item in mobile.get_by_role("tab").all())
                        mobile.wait_for_function(no_sideways)
                        check_contrast(mobile, "tabs at 360 px")
                        shot(mobile, "phone-tabs.png", full_page=False)
                        # The theme is switched from « Réglages » on a phone. (Not from « Style »: its closed section
                        # « Créer un style… » is not rendered, and its colours would stay in transition after the change.)
                        mobile.get_by_role("tab", name="Réglages", exact=True).tap()
                        expect(mobile.locator(".panel .panel-theme")).to_be_visible()
                        mobile.evaluate("scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })")
                        expect(canvas_phone).to_be_in_viewport(ratio=1)
                        assert poster_box()["height"] >= 140 and poster_box()["y"] >= top_bar.bounding_box()["height"] - 1
                        toggle_theme(mobile, "Passer au thème clair")
                        check_contrast(mobile, "tabs at 360 px, light theme")
                        shot(mobile, "phone-tabs-clair.png", full_page=False)
                        toggle_theme(mobile, "Passer au thème sombre")
                        # Typing: « Prix » takes the focus, the poster collapses to a strip and the bottom bar hides; the
                        # field is not under the poster; both come back when the focus leaves.
                        main_bar = mobile.locator(".stage-head .main-action")
                        mobile.get_by_role("tab", name="Textes", exact=True).tap()
                        expect(main_bar).to_be_visible()
                        price_field = mobile.get_by_label("Prix en ariary", exact=True)
                        price_field.tap()
                        expect(price_field).to_be_focused()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height <= 100")
                        expect(main_bar).to_be_hidden()
                        expect(canvas_phone).to_be_in_viewport(ratio=1)
                        pin_bottom = mobile.locator(".pin").bounding_box()
                        assert price_field.bounding_box()["y"] >= pin_bottom["y"] + pin_bottom["height"] - 1, (price_field.bounding_box(), pin_bottom)
                        shot(mobile, "phone-typing.png", full_page=False)
                        # The tap that takes the focus away lands where it was aimed, although the poster grows back.
                        word = mobile.get_by_role("group", name="Mot du titre en couleur").get_by_role("button").first
                        word.tap()
                        expect(word).to_have_attribute("aria-pressed", "true")
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 140")
                        expect(main_bar).to_be_visible()
                        # And a focus that leaves without a tap brings it back too.
                        price_field.focus()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height <= 100")
                        price_field.blur()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 140")
                        expect(main_bar).to_be_visible()
                        # « Voir l’affiche » shows the poster large in the tabs too: full width, no bottom bar inside,
                        # the page behind inert.
                        mobile.get_by_role("button", name="Voir l’affiche", exact=True).tap()
                        expect(sheet).to_be_visible()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().width > 300")
                        expect(sheet.locator(".main-action")).to_be_hidden()
                        expect(sheet.locator(".frame .badge")).to_be_hidden()
                        assert mobile.locator(".rail").get_attribute("inert") is not None and top_bar.get_attribute("inert") is not None
                        check_contrast(mobile, "poster opened large over the tabs")
                        shot(mobile, "phone-large-tabs.png", full_page=False)
                        sheet.get_by_role("button", name="Revenir aux réglages").tap()
                        expect(mobile.get_by_role("dialog")).to_have_count(0)
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 140")
                        # Back to « Mes affiches » from the bar: the bottom navigation is there again.
                        back.tap()
                        expect(mobile.get_by_role("heading", name="Mes affiches", exact=True)).to_be_visible()
                        assert mobile.url.endswith("#affiches"), mobile.url
                        expect(nav).to_be_visible()
                        expect(nav.locator("a[aria-current=page]")).to_contain_text("Mes affiches")
                        mobile.wait_for_function(no_sideways)
                        check_contrast(mobile, "Mes affiches at 360 px with the bottom navigation")
                        shot(mobile, "phone-mes-affiches.png", full_page=False)
                        phone.close()
                        # The look (D-POSTER-EDITOR-005 part B): phones that never picked a theme, light then dark, and a
                        # 1366 × 768 screen. Same session, no theme stored.
                        session = {"cookies": page.context.storage_state()["cookies"], "origins": []}
                        light_poster = walk_look(browser, session, "light", errors)
                        walk_look(browser, session, "dark", errors)
                        walk_wait(browser, session, errors)
                        walk_words(browser, session, errors)
                        walk_tap(browser, session, errors)
                        desk = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
                        screen = desk.new_page()
                        screen.set_default_timeout(10000)
                        screen.on("pageerror", lambda error: errors.append(str(error)))
                        for address, name in ((f"#{light_poster}", "editeur"), ("#etapes", "creer")):
                            screen.goto(f"{ORIGIN}/{address}")
                            if name == "editeur":
                                screen.locator(".final-preview").get_by_role("button", name="Fermer").click()
                                expect(screen.get_by_role("tab", name="Textes", exact=True)).to_have_attribute("aria-selected", "true")
                                # The poster is drawn once its scene is loaded; the main action waits for it.
                                expect(screen.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_enabled()
                            else:
                                expect(screen.get_by_label("Photos du produit")).to_be_attached()
                            pixels = set()
                            for theme, scheme in (("clair", "light"), ("sombre", "dark")):
                                screen.emulate_media(color_scheme=scheme)
                                screen.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
                                screen.wait_for_function(NO_SIDEWAYS)
                                check_one_blur(screen, f"{name} at 1366 px, {theme}")
                                check_contrast(screen, f"{name} at 1366 px, {theme}")
                                shot(screen, f"look-1366-{theme}-{name}.png", full_page=False)
                                if name == "editeur":
                                    drawn, veiled = screen.evaluate(POSTER_JS)
                                    assert not veiled, f"the poster is veiled at 1366 px, {theme}:\n" + "\n".join(veiled)
                                    pixels.add(drawn)
                            # A page token never reaches the poster (R-POLISH-002): the same pixels in both themes.
                            assert name != "editeur" or len(pixels) == 1, "the poster's pixels change with the theme"
                        desk.close()
                        assert not errors, errors
                        # A poster's address opened without a session: after the sign-in the owner is on that poster.
                        other = browser.new_page(viewport={"width": 390, "height": 844})
                        other.goto(f"{ORIGIN}/#{copy_id}")
                        other.get_by_label("Identifiant de la boutique", exact=True).fill(IDENTIFIER)
                        other.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
                        other.get_by_role("button", name="Ouvrir l’atelier").click()
                        other.get_by_role("tab", name="Textes", exact=True).click()
                        expect(other.get_by_label("Titre", exact=True)).to_be_visible()
                        assert other.url.endswith(f"#{copy_id}"), other.url
                        other.close()
                        walk_credits(browser, errors, data, servers[0][0].config.app)
                        # Last on this server: it ends shop 1's sessions and suspends it for a while.
                        walk_two_shops(browser, errors, data)
                        walk_review_r2(browser, errors, data)
                        assert not errors, errors
                        # The three formats (ADR-080) on an API of their own, fresh data: FORMATS_ENABLED=feed,square,story.
                        stop(*servers.pop())
                        with tempfile.TemporaryDirectory(prefix="affiche-formats-") as formats_data:
                            formats_server = serve(formats_data, formats_enabled="feed,square,story", facebook_provider="stub")
                            try:
                                walk_formats(browser, errors)
                            finally:
                                stop(*formats_server)  # before its data directory is removed
                        assert not errors, errors
                        print("Browser smoke passed: upload, identity, lost-response replay, scene/review, price undo, keyboard, autosave/reopen/conflict copy, overflow/glyph warnings, desktop/mobile, the prepaid balance at 360 px (cost, few left, a credit given back, the pause, zero, « Reprendre » at zero), two shops in one browser (the identity gate, sign-out, cookies with and without the lock), three formats, zero spend.")
                    except Exception:
                        page.screenshot(path=str(OUTPUT / "failure.png"), full_page=True)
                        print(page.locator("body").inner_text(), flush=True)
                        print("Page errors:", errors, flush=True)
                        raise
                    finally:
                        browser.close()
            finally:
                vite.terminate()
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill()
                    vite.wait(timeout=10)
                for server in servers:
                    stop(*server)


if __name__ == "__main__":
    run()
