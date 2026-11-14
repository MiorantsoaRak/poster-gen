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

from affiche.api import create_app
from affiche.config import Settings
from affiche.posters.auth import PASSWORDS

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs" / "editor-smoke"
ORIGIN = "http://127.0.0.1:5173"
PASSWORD = os.urandom(12).hex()  # a throwaway credential per run against temporary stub data


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


# Contrast of every visible text against the colour behind it (WCAG: 4.5:1, or 3:1 from 24 px, or from 18.66 px
# in bold). Not measured: disabled controls, text over an image (the poster itself), placeholders.
# Glass is translucent over soft colour patches (ADR-077): a text must read over the darkest and the lightest point of
# that backdrop, so it is measured over the bare ground and over each patch at its strongest, and the worst ratio counts.
# The patches are the colours of a gradient background, or of the fixed ::before layer of the page. A glass surface's
# saturate() acts on what is behind it before its fill is laid over (sRGB matrix of Filter Effects, as Chromium draws
# it); its blur only averages the backdrop towards less extreme colours, so leaving it out keeps the worst case.
CONTRAST_JS = r"""() => {
  const parse = value => { const n = (value.match(/[\d.]+/g) || []).map(Number); return n.length < 4 ? [...n, 1] : n }
  const channel = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4 }
  const luminance = c => .2126 * channel(c[0]) + .7152 * channel(c[1]) + .0722 * channel(c[2])
  const over = (top, under) => [0, 1, 2].map(i => top[i] * top[3] + under[i] * (1 - top[3]))
  const patches = style => (style.backgroundImage.match(/rgba?\([^)]*\)/g) || []).map(parse).filter(colour => colour[3] > 0)
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
  const failures = [], seen = new Set()
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const element = node.parentElement, text = node.textContent.trim()
    if (!text || seen.has(element) || element.closest(':disabled, [aria-disabled=true], [inert], script, style')) continue
    seen.add(element)
    const style = getComputedStyle(element), box = element.getBoundingClientRect()
    if (!box.width || !box.height || style.visibility !== 'visible' || !element.checkVisibility({ opacityProperty: true })) continue
    const behind = backdrop(element)
    if (!behind) continue
    const [ratio, worst] = behind.map(base => {
      const a = luminance(over(parse(style.color), base)), b = luminance(base)
      return [(Math.max(a, b) + .05) / (Math.min(a, b) + .05), base]
    }).reduce((low, item) => item[0] < low[0] ? item : low)
    const size = parseFloat(style.fontSize), needed = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700) ? 3 : 4.5
    if (ratio < needed) failures.push(`${ratio.toFixed(2)} < ${needed}: "${text.slice(0, 40)}" <${element.tagName.toLowerCase()} class="${element.className}"> ${style.color} on rgb(${worst.map(Math.round)})`)
  }
  return failures
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
GROUNDS = {"clair": "#f4f1ec", "sombre": "#100f0e"}
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


def check_contrast(page, where):
    page.wait_for_function(SETTLED, polling=100)
    failures = page.evaluate(CONTRAST_JS)
    assert not failures, f"contrast on {where}:\n" + "\n".join(failures)


def shot(page, name, full_page=True):
    # A picture for a person to judge: from the top of the page, and not in the middle of a colour transition.
    if full_page:
        page.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
    page.wait_for_function(SETTLED, polling=100)
    page.screenshot(path=str(OUTPUT / name), full_page=full_page)


def toggle_theme(page, name, hidden=False):
    # A real click on the one visible theme button: the header's, or on a phone in the editor the one in « Réglages »
    # (D-POSTER-EDITOR-005). During the steps on a phone there is no « Réglages » and the header gives way to the
    # editor's bar: there, and only where the caller says so, the hidden header button receives the click event itself,
    # so that the contrast of the steps can still be measured in both themes.
    if hidden:
        button = page.locator(".theme-toggle")
        expect(button).to_be_hidden()
        expect(button).to_have_attribute("aria-label", name)
        button.dispatch_event("click")
        expect(button).not_to_have_attribute("aria-label", name)
    else:
        page.get_by_role("button", name=name, exact=True).click()
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(0)


def topmost(locator):
    # Nothing covers it: the element hit at its centre is the element itself (ADR-076).
    return locator.evaluate("e => { const r = e.getBoundingClientRect(); return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === e }")


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
    device.goto(ORIGIN)
    expect(device.get_by_label("Photos du produit")).to_be_attached()
    assert theme_of(device) == theme and bar_colour(device) == GROUNDS[theme], (theme_of(device), bar_colour(device))
    assert device.evaluate("getComputedStyle(document.body).fontFamily").startswith("Figtree")
    device.wait_for_function("document.fonts.check('16px Figtree')")
    check_one_blur(device, f"intake at 360 px, {theme}")
    check_contrast(device, f"intake at 360 px, {theme}, no stored choice")
    shot(device, f"look-360-{theme}-creer.png", full_page=False)
    device.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
    expect(device.locator(".photo-strip img")).to_have_count(1)
    device.get_by_label("Nom du produit", exact=True).fill(f"CMF Buds 2a {theme}")
    device.get_by_label("Prix en ariary", exact=True).fill("190 000")
    device.get_by_label("Les photos correspondent").check()
    device.get_by_role("button", name="Préparer mon affiche").tap()
    proceed = device.get_by_role("button", name="Continuer", exact=True)
    for number, step in ((2, "textes"), (3, "boutique"), (4, "style")):
        expect(device.locator(".step-count")).to_have_text(f"Étape {number} sur 4")
        device.wait_for_function(NO_SIDEWAYS)
        check_one_blur(device, f"step {step} at 360 px, {theme}")
        check_contrast(device, f"step {step} at 360 px, {theme}")
        check_targets(device, f"step {step} at 360 px, {theme}")
        shot(device, f"look-360-{theme}-etape-{step}.png", full_page=False)
        if step != "style":
            proceed.tap()
    # Changes that act at once are switches; what acts on the next version stays a checkbox under its heading.
    device.get_by_role("tab", name="Boutique", exact=True).tap()
    expect(device.locator("label.switch")).to_have_count(3)
    expect(device.get_by_role("checkbox", name="Contact", exact=True)).to_be_checked()
    expect(device.get_by_text("Pour la prochaine version", exact=True)).to_be_visible()
    expect(device.locator("label.check:not(.switch)", has_text="Dessiner aussi le contact dans l’image")).to_be_visible()
    device.get_by_role("tab", name="Style", exact=True).tap()
    device.get_by_role("button", name="Générer l’affiche").tap()
    device.get_by_role("button", name="Lancer la génération").tap()
    expect(device.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
    check_one_blur(device, f"review at 360 px, {theme}")
    check_contrast(device, f"review at 360 px, {theme}")
    shot(device, f"look-360-{theme}-verifier.png", full_page=False)
    device.get_by_role("button", name="Tout est conforme, approuver").tap()
    expect(device.get_by_role("tab")).to_have_count(4)
    device.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 200")
    for name in ("Textes", "Boutique", "Style", "Réglages"):
        device.get_by_role("tab", name=name, exact=True).tap()
        expect(device.get_by_role("tab", name=name, exact=True)).to_have_attribute("aria-selected", "true")
        device.wait_for_function(NO_SIDEWAYS)
        check_one_blur(device, f"tab {name} at 360 px, {theme}")
        check_contrast(device, f"tab {name} at 360 px, {theme}")
        check_targets(device, f"tab {name} at 360 px, {theme}")
        shot(device, f"look-360-{theme}-onglet-{name.lower().replace('é', 'e')}.png", full_page=False)
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
        check_contrast(page, f"{where}, {theme}")

    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark", storage_state=session)
    watch(context)
    device = context.new_page()
    device.set_default_timeout(10000)
    device.on("pageerror", lambda error: errors.append(str(error)))
    device.goto(ORIGIN)
    device.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
    expect(device.locator(".photo-strip img")).to_have_count(1)
    device.get_by_label("Nom du produit", exact=True).fill("Écouteurs attente")
    device.get_by_label("Prix en ariary", exact=True).fill("90 000")
    device.get_by_label("Les photos correspondent").check()
    device.get_by_role("button", name="Préparer mon affiche").tap()
    proceed = device.get_by_role("button", name="Continuer", exact=True)
    proceed.tap()
    proceed.tap()
    block, pill, badge = device.locator(".wait"), device.locator(".frame .gen-pill"), device.locator(".frame .badge")
    words, elapsed = block.locator("[role=status]"), block.locator(".wait-time")
    cancel = device.get_by_role("button", name="Annuler la demande")
    review = device.get_by_role("heading", name="Vérifier la fidélité du produit")
    # The first generation, asked from far down the last step: the page goes back to the top, where the draft stays as the
    # thumbnail of the steps (« Aperçu ») with the state pill in front, and the waiting block under it.
    device.evaluate("scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })")
    still = device.evaluate(STILL_JS)
    device.get_by_role("button", name="Générer l’affiche").tap()
    device.get_by_role("button", name="Lancer la génération").tap()
    expect(words).to_contain_text("Votre demande est en attente.")
    expect(pill).to_have_text("En attente")
    expect(badge).to_have_text("Aperçu")
    expect(block.locator("li[aria-current=step]")).to_contain_text("Demande enregistrée")
    expect(cancel).to_be_visible()
    device.wait_for_function("scrollY === 0")
    check_still(device, still, "while the first generation is queued at 360 px")
    expect(block).to_be_in_viewport()
    assert topmost(pill) and topmost(badge)
    expect(device.locator(".frame[aria-busy=true]")).to_have_count(1)
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
    waiting_checks(device, "first generation at 360 px", "sombre", "dark")
    check_targets(device, "first generation at 360 px")
    shot(device, "wait-360-sombre-premiere.png", full_page=False)
    # Reduced motion: nothing repeats, the rail is a still line.
    device.emulate_media(reduced_motion="reduce")
    device.wait_for_function("document.getAnimations().length === 0")
    assert block.locator(".wait-rail span").evaluate("e => getComputedStyle(e).opacity") == "0.6"
    device.emulate_media(reduced_motion="no-preference")
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
    device.get_by_role("button", name="Tout est conforme, approuver").tap()
    expect(device.get_by_role("tab")).to_have_count(4)
    # A new version once one exists: the version shown is said to be kept, the pills are in front in both themes.
    still = device.evaluate(STILL_JS)
    held["status"] = "queued"
    device.get_by_role("button", name="Nouvelle version").tap()
    device.get_by_role("button", name="Lancer la génération").tap()
    expect(words).to_contain_text("Votre demande est en attente.")
    check_still(device, still, "while a new version is queued at 360 px")
    held["status"] = "running"
    expect(words).to_contain_text("Votre affiche prend forme.")
    check_still(device, still, "while a new version runs at 360 px", samples=6)
    expect(badge).to_have_text("Version précédente conservée")
    # On a phone the poster is narrow: the badge shows « Version précédente » on one line; screen readers hear it whole.
    assert badge.bounding_box()["height"] <= 30, badge.bounding_box()
    expect(block).to_be_in_viewport()
    assert topmost(pill) and topmost(badge)
    # One voice at a time: while the waiting block speaks, the coach line is not a live region.
    expect(device.locator(".coach[role=status]")).to_have_count(0)
    for theme, scheme in (("sombre", "dark"), ("clair", "light")):
        waiting_checks(device, "new version at 360 px", theme, scheme)
        check_targets(device, f"new version at 360 px, {theme}")
        shot(device, f"wait-360-{theme}.png", full_page=False)
    poster = device.url.split("#")[1]
    # After 100 s of creation a sentence says it is long, still running, and useless to start again. The fake clock is
    # installed only now, so that it governs nothing else in this walk.
    waiting_checks(device, "new version at 360 px", "sombre", "dark")
    expect(words).not_to_contain_text("plus long que d’habitude")
    context.clock.install()
    device.clock.fast_forward("01:41")
    expect(words).to_contain_text("C’est plus long que d’habitude. La demande est toujours en cours : inutile de la relancer.")
    device.screenshot(path=str(OUTPUT / "wait-360-sombre-longue.png"))
    held["status"] = None
    expect(review).to_be_visible(timeout=30000)
    device.get_by_role("button", name="Tout est conforme, approuver").tap()
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
    # A refusal of the poll does not change by asking again: on a session that ended the editor stops following, says
    # why and shows the sign-in; it never polls again nor starts another generation.
    screen.locator(".review-panel").get_by_role("button", name="Fermer").click()
    check_still(screen, still, "after a new version at 1366 px")
    held["status"] = "running"
    screen.get_by_role("button", name="Nouvelle version").click()
    screen.get_by_role("button", name="Lancer la génération").click()
    expect(screen.locator(".wait [role=status]")).to_contain_text("Votre affiche prend forme.")
    held["signed_out"] = True
    expect(screen.get_by_label("Mot de passe", exact=True)).to_be_visible()
    expect(screen.locator(".message.error")).to_contain_text("Connectez-vous pour continuer.")
    expect(screen.locator(".wait")).to_have_count(0)
    asked = len(polls)
    screen.wait_for_timeout(3000)
    assert len(polls) == asked and len(scenes) == 4, (polls[asked:], scenes)
    desk.close()
    # The elapsed time rests on what the real answers carried: UTC stamps with their offset, the server's Date header.
    assert stamps and all(re.search(r"\+00:00$", created) and (started is None or re.search(r"\+00:00$", started)) and date
                          for created, started, date in stamps), stamps


def walk_words(browser, session, errors):
    """One poster's words never reach the next one (T-BLANK-WORDS, user report 2026-11-14): poster A is made with a brand,
    a subtitle and an accent word; poster B, made next from the form, starts blank and its scene request carries none of
    them; A reopened shows its own words again."""
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    scenes = []
    page.on("request", lambda request: scenes.append(request.post_data_json) if request.method == "POST" and request.url.endswith("/scenes") else None)
    brand, subtitle = page.get_by_label("Marque (facultative)"), page.get_by_label("Sous-titre (facultatif)")
    words = page.get_by_role("group", name="Mot du titre en couleur").get_by_role("button")
    review = page.get_by_role("heading", name="Vérifier la fidélité du produit")

    def make(name, price):
        page.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
        expect(page.locator(".photo-strip img")).to_have_count(1)
        page.get_by_label("Nom du produit", exact=True).fill(name)
        page.get_by_label("Prix en ariary", exact=True).fill(price)
        page.get_by_label("Les photos correspondent").check()
        page.get_by_role("button", name="Préparer mon affiche").click()
        expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()

    def generate():
        page.get_by_role("button", name="Continuer", exact=True).click()
        page.get_by_role("button", name="Continuer", exact=True).click()
        page.get_by_role("button", name="Générer l’affiche").click()
        page.get_by_role("button", name="Lancer la génération").click()
        expect(review).to_be_visible(timeout=30000)
        page.get_by_role("button", name="Tout est conforme, approuver").click()
        expect(page.get_by_role("tab")).to_have_count(4)

    page.goto(ORIGIN)
    make("Casque Alpha", "120 000")
    brand.fill("MarqueAlpha")
    subtitle.fill("SOUS-TITRE ALPHA")
    words.filter(has_text="Casque").click()
    expect(words.filter(has_text="Casque")).to_have_attribute("aria-pressed", "true")
    generate()
    poster_a = page.url.split("#")[1]
    assert (scenes[-1]["headline"]["brand"], scenes[-1]["headline"]["subtitle"], scenes[-1]["headline"]["accent_word"]) == ("MarqueAlpha", "SOUS-TITRE ALPHA", "Casque"), scenes[-1]
    # The form waits for the next product: nothing of A's photos, name, price or agreement is left in it.
    page.locator(".nav a", has_text="Créer").click()
    expect(page.locator(".photo-strip img")).to_have_count(0)
    expect(page.get_by_label("Nom du produit", exact=True)).to_have_value("")
    expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("")
    expect(page.get_by_label("Variante confirmée")).to_have_value("Conforme à la photo")
    expect(page.get_by_label("Les photos correspondent")).not_to_be_checked()
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
    expect(page.get_by_role("heading", name="Casque Alpha", exact=True)).to_be_visible()
    expect(brand).to_have_value("MarqueAlpha")
    expect(subtitle).to_have_value("SOUS-TITRE ALPHA")
    expect(words.filter(has_text="Casque")).to_have_attribute("aria-pressed", "true")
    context.close()


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="affiche-browser-") as data:
        settings = Settings(_env_file=None, image_provider="stub", planner_provider="stub", openai_api_key=None,
                            anthropic_api_key=None, stub_fail=None, spend_cap_usd="20", spend_cap_since="2026-11-06",
                            data_dir=data, app_origin=ORIGIN, shop_password_hash=PASSWORDS.hash(PASSWORD))
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=8000, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        with (OUTPUT / "vite.log").open("w", encoding="utf-8") as log:
            vite = subprocess.Popen(["node", str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1"],
                                    cwd=ROOT / "frontend", stdout=log, stderr=log,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                with sync_playwright() as playwright:
                    # SMOKE_CHANNEL=msedge runs the same flow in the installed Microsoft Edge.
                    browser = playwright.chromium.launch(headless=True, channel=os.environ.get("SMOKE_CHANNEL") or None)
                    print("Browser:", browser.browser_type.name, os.environ.get("SMOKE_CHANNEL") or "bundled", browser.version, flush=True)
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
                                page.goto(ORIGIN, timeout=2000)
                                break
                            except Exception:
                                if attempt == 59:
                                    raise
                                time.sleep(.25)
                        # The files load but the application's own process does not answer: a French message with a retry.
                        page.route("**/api/session", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":{"code":"service_down","message_fr":"Le service est momentanément indisponible.","retryable":true}}'))
                        page.reload()
                        expect(page.get_by_role("alert")).to_contain_text("momentanément indisponible")
                        expect(page.get_by_label("Mot de passe", exact=True)).to_have_count(0)
                        page.unroute("**/api/session")
                        page.get_by_role("button", name="Réessayer").click()
                        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
                        check_contrast(page, "sign-in")
                        # A dark device and no choice stored: the dark theme, and the browser's bar says so (it took the
                        # light colour before T-THEME-COLOR).
                        assert theme_of(page) == "sombre" and bar_colour(page) == GROUNDS["sombre"], (theme_of(page), bar_colour(page))
                        # The home-screen manifest and its icons are served.
                        manifest = page.request.get(f"{ORIGIN}/manifest.webmanifest").json()
                        assert manifest["display"] == "standalone" and manifest["lang"] == "fr", manifest
                        for icon in [*manifest["icons"], {"src": "/icons/apple-touch-icon.png"}]:
                            served = page.request.get(ORIGIN + icon["src"])
                            assert served.status == 200 and served.headers["content-type"] == "image/png", icon
                        page.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
                        page.get_by_role("button", name="Ouvrir l’atelier").click()
                        expect(page.get_by_label("Photos du produit")).to_be_enabled()
                        check_contrast(page, "intake")
                        page.screenshot(path=str(OUTPUT / "intake.png"), full_page=True)
                        # Glass on every surface, the header and the panels alike (ADR-077); all solid for a person who
                        # asked for less motion (R-POSTER-EDITOR-006).
                        blur = "selector => getComputedStyle(document.querySelector(selector)).backdropFilter"
                        assert page.evaluate(blur, ".app-header") != "none" and page.evaluate(blur, ".intake") != "none"
                        page.emulate_media(reduced_motion="reduce")
                        assert page.evaluate(blur, ".app-header") == "none" and page.evaluate(blur, ".intake") == "none"
                        assert page.evaluate("getComputedStyle(document.querySelector('.app-header')).backgroundColor").startswith("rgb(")
                        check_contrast(page, "intake, solid chrome")
                        page.emulate_media(reduced_motion="no-preference")
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
                        # A new poster is walked one step at a time (R-POSTER-EDITOR-004): « Textes », « Boutique », « Style ».
                        # Each step shows its own controls only; the main action waits on the last one.
                        def tab(name):
                            return page.get_by_role("tab", name=name, exact=True)
                        def open_group(name):
                            tab(name).click()
                            expect(tab(name)).to_have_attribute("aria-selected", "true")
                        step_count = page.locator(".step-count")
                        proceed = page.get_by_role("button", name="Continuer", exact=True)
                        generate = page.get_by_role("button", name="Générer l’affiche")
                        expect(step_count).to_have_text("Étape 2 sur 4")
                        expect(page.get_by_role("tab")).to_have_count(3)
                        expect(tab("Textes")).to_have_attribute("aria-selected", "true")
                        expect(tab("Boutique")).to_be_disabled()
                        expect(tab("Style")).to_be_disabled()
                        expect(generate).to_have_count(0)
                        expect(page.get_by_role("button", name="Retour", exact=True)).to_have_count(0)
                        expect(page.get_by_label("Position du contact")).to_have_count(0)
                        expect(page.locator(".look-grid")).to_have_count(0)
                        # The coach line and the reasons under blocked buttons tell a new owner what to do.
                        expect(page.locator(".coach")).to_contain_text("choisissez un style")
                        # Several versions are possible and announced before the first one exists.
                        expect(page.get_by_role("heading", name="Versions 0 sur 12")).to_be_visible()
                        expect(page.get_by_text("Vous choisirez celle à exporter.", exact=False)).to_be_visible()
                        assert page.get_by_text("S’inspirer d’une affiche").count() == 0 and page.get_by_label("Préparation").count() == 0
                        check_contrast(page, "step Textes")
                        shot(page, "step-textes.png")
                        # "Brand as plain text" is offered only once a brand is typed.
                        plain_brand = page.get_by_label("Écrire la marque en texte simple", exact=False)
                        page.get_by_label("Marque (facultative)").fill("")
                        expect(plain_brand).to_have_count(0)
                        page.get_by_label("Marque (facultative)").fill("JBL")
                        expect(plain_brand).to_be_visible()
                        page.get_by_label("Marque (facultative)").fill("")
                        # The accent is chosen among the title's own words and a few colours, never typed; the colour
                        # sits with the word it colours.
                        chips = page.get_by_role("group", name="Mot du titre en couleur").get_by_role("button")
                        expect(chips.last).to_have_text("Aucun")
                        expect(chips.last).to_have_attribute("aria-pressed", "true")
                        accent = chips.first.inner_text()
                        chips.first.click()
                        expect(chips.first).to_have_attribute("aria-pressed", "true")
                        page.get_by_role("button", name="Rouge", exact=True).click()
                        proceed.click()
                        expect(step_count).to_have_text("Étape 3 sur 4")
                        expect(tab("Boutique")).to_have_attribute("aria-selected", "true")
                        expect(page.get_by_role("button", name="Retour", exact=True)).to_be_visible()
                        expect(generate).to_have_count(0)
                        expect(page.get_by_label("Titre", exact=True)).to_have_count(0)
                        assert page.get_by_label("Dessiner aussi le nom de la boutique et le contact dans l’image").count() == 0
                        page.get_by_label("Position du contact").select_option("right")
                        until(lambda: footer("contact")["align"] == "right")
                        assert json.loads(page.evaluate("localStorage.getItem('affiche.style')"))["contact_align"] == "right"
                        # By default the contact is drawn in the composition, at the chosen position, without the
                        # shop name (ADR-055). The option is in view: no section has to be opened to find it.
                        expect(page.get_by_text("Pour la prochaine version", exact=True)).to_be_visible()
                        expect(page.get_by_label("Dessiner aussi le contact dans l’image")).to_be_checked()
                        check_contrast(page, "step Boutique")
                        shot(page, "step-boutique.png")
                        proceed.click()
                        expect(step_count).to_have_text("Étape 4 sur 4")
                        expect(tab("Style")).to_have_attribute("aria-selected", "true")
                        expect(proceed).to_have_count(0)
                        expect(generate).to_be_enabled()
                        expect(page.get_by_label("Position du contact")).to_have_count(0)
                        check_contrast(page, "step Style")
                        shot(page, "step-style.png")
                        # A poster the shop likes becomes a saved look beside the built-in ones (stub brief, no spend).
                        page.get_by_text("Créer un style depuis une affiche", exact=True).click()
                        expect(page.get_by_text("Choisissez d’abord une affiche modèle ci-dessus.")).to_be_visible()
                        page.get_by_label("Affiche modèle").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
                        expect(page.get_by_alt_text("Affiche modèle pour le nouveau style")).to_be_visible()
                        expect(page.get_by_text("Choisissez d’abord une affiche modèle ci-dessus.")).to_have_count(0)
                        page.get_by_label("Nom du style").fill("Vagues bleues")
                        page.get_by_role("button", name="Enregistrer ce style").click()
                        # A paid action is confirmed first, with its cost; cancelling does nothing.
                        expect(page.get_by_role("dialog")).to_contain_text("Créer un style depuis cette affiche ?")
                        expect(page.get_by_role("dialog")).to_contain_text("aucune dépense")
                        check_contrast(page, "paid confirmation")
                        shot(page, "confirm.png", full_page=False)
                        page.get_by_role("dialog").get_by_role("button", name="Annuler").click()
                        assert page.request.get(f"{ORIGIN}/api/looks").json()["items"] == []
                        page.get_by_role("button", name="Enregistrer ce style").click()
                        page.get_by_role("button", name="Créer le style").click()
                        expect(page.get_by_text("Style « Vagues bleues » enregistré", exact=False)).to_be_visible(timeout=15000)
                        check_contrast(page, "notice")
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
                        expect(step_count).to_have_text("Étape 2 sur 4")
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
                        expect(step_count).to_have_text("Étape 3 sur 4")
                        expect(page.locator(".panel .refusal")).to_contain_text("Le contact est trop long")
                        shot(page, "refus.png")
                        expect(page.locator(".message.error")).to_have_count(0)
                        page.unroute("**/api/creations/*/scenes", refuse_contact)
                        # A visited step is reopened from the indicator, and what was chosen there is still chosen.
                        tab("Textes").click()
                        expect(step_count).to_have_text("Étape 2 sur 4")
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
                        expect(page.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
                        # One agreement covers the listed points (ADR-051): a summary to read, no boxes to tick.
                        expect(page.locator(".review-checks .points li")).to_have_count(6)
                        expect(page.locator(".review-panel input[type=checkbox]")).to_have_count(0)
                        page.screenshot(path=str(OUTPUT / "review.png"))
                        page.get_by_role("button", name="Signaler un problème").click()
                        expect(page.get_by_role("button", name="Refuser cette version")).to_be_disabled()
                        page.get_by_role("button", name="Tout est conforme, approuver").click()
                        expect(page.get_by_text("Fidélité du produit approuvée.", exact=False)).to_be_visible()
                        # With a version, the same groups are tabs beside the poster, plus « Réglages »; no step is left.
                        expect(page.get_by_role("tab")).to_have_count(4)
                        expect(step_count).to_have_count(0)
                        expect(proceed).to_have_count(0)
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
                        assert logo["x"] == 54 and beside["x"] >= logo["x"] + logo["width"] + 20 and beside["x"] + beside["width"] <= 1026.5, (logo, beside)
                        assert abs(logo["y"] + logo["height"] - beside["y"] - beside["height"]) < 1, (logo, beside)
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
                        expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("90\u202f000")
                        saved = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert saved["document"]["formats"]["feed"]["scene"] == scene_before
                        visual = page.request.get(f"{ORIGIN}/api/visuals/{scene_before['visual_id']}").json()
                        # The editor no longer sends a separate style-reference image (the API still accepts one).
                        assert visual["style_reference_asset"] is None and len(visual["original_urls"]) == 1
                        expect(page.locator(".coach")).to_contain_text("Dernière étape")
                        # The chosen version is named, and another one is one confirmed tap away.
                        expect(page.get_by_role("heading", name="Versions 1 sur 12")).to_be_visible()
                        expect(page.get_by_text("Choisie pour l’export", exact=True)).to_be_visible()
                        expect(page.get_by_role("button", name="Nouvelle version")).to_be_enabled()
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
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
                            check_contrast(page, f"tab {name}")
                            shot(page, f"tab-{name.lower().replace('é', 'e')}.png")
                        page.get_by_role("button", name="Passer au thème clair").click()
                        check_contrast(page, "editor, light theme")
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
                        expect(page.locator(".theme-toggle")).to_be_hidden()
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
                            headers={"Origin": ORIGIN, "If-Match": f'"{remote["revision"]}"', "Idempotency-Key": str(uuid4())})
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
                        # Every paid call is confirmed with its cost first; Escape or "Annuler" backs out.
                        expect(page.get_by_role("dialog")).to_contain_text("aucune dépense")
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
                        assert styled["document"] == expected_styled
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
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
                        page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
                        expect(page.get_by_role("heading", name="Dernière vérification avant le téléchargement")).to_be_visible(timeout=40000)
                        preview_url = page.locator(".final-preview img").get_attribute("src")
                        preview_bytes = page.request.get(ORIGIN + preview_url).body()
                        expect(page.locator(".final-preview .points li")).not_to_have_count(0)
                        expect(page.locator(".final-preview input[type=checkbox]")).to_have_count(0)
                        expect(page.locator(".final-preview img")).to_be_visible()
                        page.screenshot(path=str(OUTPUT / "final-mobile.png"))
                        check_contrast(page, "final screen at phone width")
                        page.set_viewport_size({"width": 1440, "height": 1050})
                        page.screenshot(path=str(OUTPUT / "final.png"))
                        page.set_viewport_size({"width": 390, "height": 844})
                        # A refusal while this panel is open is written above it, not in the groups that are inert behind it.
                        page.route("**/api/creations/*/confirmations", lambda route: route.fulfill(status=409, content_type="application/json", body='{"error":{"code":"price_stale","message_fr":"Le prix dessiné dans l’image ne correspond plus au prix de l’affiche.","retryable":false}}'))
                        page.get_by_role("button", name="Tout est conforme, confirmer", exact=True).click()
                        expect(page.locator(".message.error")).to_contain_text("ne correspond plus au prix")
                        expect(page.locator(".message.error")).to_be_in_viewport()
                        page.unroute("**/api/creations/*/confirmations")
                        page.get_by_role("button", name="Tout est conforme, confirmer", exact=True).click()
                        link = page.get_by_role("link", name="Télécharger le PNG confirmé")
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
                        expect(page.get_by_role("button", name="Tout est conforme, confirmer", exact=True)).to_have_count(0)
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
                        page.locator(".nav a", has_text="Mes affiches").click()
                        # The view is in the address: a reload stays on the list.
                        assert page.url.endswith("#affiches"), page.url
                        page.reload()
                        thumbnail = page.locator('.library-item img[src^="/api/thumbnails/"]').first
                        expect(thumbnail).to_be_visible()
                        check_contrast(page, "Mes affiches")
                        # At 360 px the list's title row wraps instead of squeezing its subtitle to one word per line under the checkbox.
                        page.set_viewport_size({"width": 360, "height": 740})
                        heading = page.get_by_role("heading", name="Mes affiches", exact=True).bounding_box()
                        removed = page.locator("label.check", has_text="Afficher les affiches retirées").bounding_box()
                        assert heading["y"] + heading["height"] <= removed["y"] + 1, (heading, removed)
                        assert page.locator(".gallery .titlerow .meta").bounding_box()["width"] > 300
                        shot(page, "mes-affiches-360.png", full_page=False)
                        page.set_viewport_size({"width": 1440, "height": 1000})
                        page.get_by_role("button", name="Passer au thème clair").click()
                        check_contrast(page, "Mes affiches, light theme")
                        page.get_by_role("button", name="Passer au thème sombre").click()
                        expect(thumbnail).to_be_visible()
                        # A small resized image of the 1080 x 1350 preview, not the full file.
                        page.wait_for_function("image => image.complete && image.naturalWidth === 192 && image.naturalHeight === 240", arg=thumbnail.element_handle())
                        assert len(page.request.get(ORIGIN + thumbnail.get_attribute("src")).body()) < 40_000
                        page.screenshot(path=str(OUTPUT / "mes-affiches.png"))
                        # Managing the list (R-CREATION-LIBRARY-003): state in words, copy, remove with confirmation, restore.
                        rows = page.locator(".library-row")
                        before = rows.count()
                        expect(page.locator(".library-item span").first).to_contain_text(re.compile("Brouillon|À vérifier|Approuvée|Confirmée"))
                        expect(page.locator(".nav a", has_text="Mes affiches")).to_contain_text(str(before))
                        rows.first.get_by_role("button", name=re.compile("^Dupliquer")).click()
                        expect(page.locator(".poster-canvas canvas").first).to_be_visible()
                        copy_id = page.url.split("#")[1]
                        page.locator(".nav a", has_text="Mes affiches").click()
                        expect(rows).to_have_count(before + 1)
                        rows.first.get_by_role("button", name=re.compile("^Retirer")).click()
                        expect(page.get_by_role("dialog")).to_contain_text("Rien n’est effacé")
                        page.get_by_role("dialog").get_by_role("button", name="Retirer de la liste").click()
                        expect(rows).to_have_count(before)
                        # A removed poster is not opened by its address: the list of removed posters is shown instead.
                        page.goto(f"{ORIGIN}/#{copy_id}")
                        expect(page.get_by_text("Cette affiche a été retirée de la liste.", exact=False)).to_be_visible()
                        expect(page.get_by_label("Afficher les affiches retirées")).to_be_checked()
                        expect(rows).to_have_count(1)
                        rows.first.get_by_role("button", name=re.compile("^Remettre")).click()
                        expect(rows).to_have_count(0)
                        page.get_by_label("Afficher les affiches retirées").uncheck()
                        expect(rows).to_have_count(before + 1)
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
                        # The logo as a round seal (ADR-057): a new poster with the logo and the contact, no shop name.
                        page.locator(".nav a", has_text="Créer").click()
                        page.get_by_label("Photos du produit").set_input_files(ROOT / "backend/fixtures/examples/phone-noir.jpg")
                        expect(page.locator(".photo-strip img")).to_have_count(1)
                        page.get_by_label("Nom du produit", exact=True).fill("Soundcore R50i sceau")
                        page.get_by_label("Variante confirmée").fill("Noir")
                        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
                        page.get_by_label("Les photos correspondent").check()
                        expect(page.get_by_role("checkbox", name="Logo", exact=True)).to_be_checked()
                        expect(page.get_by_role("checkbox", name="Nom de la boutique", exact=True)).not_to_be_checked()
                        page.get_by_role("button", name="Préparer mon affiche").click()
                        expect(page.get_by_role("heading", name="Soundcore R50i sceau", exact=True)).to_be_visible()
                        # This poster goes straight through the steps on its defaults: nothing is ticked, opened or filled.
                        # On a phone (360 px) a step fits the width, « Continuer » stays at the bottom of the screen, and
                        # the poster opens in front of the step and gives the step back as it was.
                        expect(step_count).to_have_text("Étape 2 sur 4")
                        page.set_viewport_size({"width": 360, "height": 740})
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        expect(proceed).to_be_in_viewport()
                        expect(page.get_by_label("Titre", exact=True)).to_be_in_viewport()
                        check_contrast(page, "step Textes at phone width")
                        shot(page, "step-textes-mobile.png", full_page=False)
                        proceed.click()
                        expect(step_count).to_have_text("Étape 3 sur 4")
                        seal_option = page.get_by_label("Logo en sceau rond dans l’image")
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
                        sheet.get_by_role("button", name="Revenir à l’étape").click()
                        expect(page.get_by_role("dialog")).to_have_count(0)
                        expect(step_count).to_have_text("Étape 3 sur 4")
                        expect(seal_option).to_be_checked()
                        # From the poster sheet, taking the contact off and following the link back: the sheet closes and the
                        # « Boutique » step shows the unticked box (the link used to change the group behind the sheet only).
                        page.get_by_role("button", name="Voir l’affiche", exact=True).click()
                        sheet.get_by_role("group", name="Éléments de l’affiche").get_by_role("button", name="Contact").click()
                        sheet.get_by_role("button", name="Retirer de l’affiche").click()
                        sheet.get_by_role("button", name="Le remettre depuis « Boutique »").click()
                        expect(page.get_by_role("dialog")).to_have_count(0)
                        expect(step_count).to_have_text("Étape 3 sur 4")
                        expect(page.get_by_role("checkbox", name="Contact", exact=True)).not_to_be_checked()
                        page.get_by_role("checkbox", name="Contact", exact=True).check()
                        expect(seal_option).to_be_checked()
                        toggle_theme(page, "Passer au thème clair", hidden=True)
                        check_contrast(page, "step Boutique at phone width, light theme")
                        shot(page, "step-boutique-mobile-clair.png", full_page=False)
                        toggle_theme(page, "Passer au thème sombre", hidden=True)
                        proceed.click()
                        expect(step_count).to_have_text("Étape 4 sur 4")
                        expect(generate).to_be_in_viewport()
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        shot(page, "step-style-mobile.png", full_page=False)
                        # Generated from the phone's bottom bar, confirmed and reviewed at 360 px (the bar was never used at phone width).
                        sent = []
                        page.on("request", lambda request: sent.append(request.post_data_json) if request.method == "POST" and request.url.endswith("/scenes") else None)
                        generate.click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
                        assert sent[-1]["headline"]["logo_seal"] is True and sent[-1]["headline"]["signature_align"] == "right", sent[-1]
                        expect(page.get_by_text("Un disque blanc vide est prévu pour le logo", exact=False)).to_be_visible()
                        # The review is two screens tall on a phone: its decision stays at the bottom of the screen, without scrolling.
                        approve = page.get_by_role("button", name="Tout est conforme, approuver")
                        expect(approve).to_be_in_viewport()
                        expect(page.get_by_role("button", name="Signaler un problème")).to_be_in_viewport()
                        shot(page, "review-mobile.png", full_page=False)
                        approve.click()
                        expect(page.get_by_text("Fidélité du produit approuvée.", exact=False)).to_be_visible()
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
                        expect(page.get_by_role("heading", name="Dernière vérification avant le téléchargement")).to_be_visible(timeout=40000)
                        expect(page.get_by_text("Le logo recouvre bien son disque", exact=True)).to_be_visible()
                        expect(page.locator(".final-preview img")).to_be_visible()
                        page.screenshot(path=str(OUTPUT / "seal-final.png"))
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        # Managing styles (R-CREATION-LIBRARY-004): open, rename with its refusals, remove with confirmation.
                        page.locator(".final-preview").wait_for(state="detached")
                        page.locator(".nav a", has_text="Styles").click()
                        cards = page.locator(".look-card")
                        expect(cards).to_have_count(4)
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
                        expect(page.locator(".nav a", has_text="Styles")).to_contain_text("3")
                        assert page.request.get(f"{ORIGIN}/api/looks").json()["items"] == []
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
                        page.screenshot(path=str(OUTPUT / "styles.png"))
                        assert not errors, errors
                        (OUTPUT / "result.json").write_text(json.dumps({"ok": True, "revision": saved["revision"], "page_errors": errors}, indent=2), encoding="utf-8")
                        # A small product photo (first thing met on the live pilot, 2026-11-13: a 474 px picture). It is said at the
                        # upload, and the paid confirmation asks for the agreement itself instead of failing with a vague message.
                        page.locator(".nav a", has_text="Créer").click()
                        Image.new("RGB", (474, 474), (200, 200, 205)).save(OUTPUT / "small.png")
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
                        # A title the image model cannot draw is said at the field, then beside the main button on the last step,
                        # before the paid step, with the reason; from there the reason opens the step that holds the title.
                        page.get_by_label("Titre", exact=True).fill('Petite photo 32"')
                        expect(page.get_by_text("contient un guillemet droit", exact=False)).to_be_visible()
                        proceed.click()
                        proceed.click()
                        expect(page.get_by_role("button", name="Générer l’affiche")).to_be_disabled()
                        expect(page.locator(".step-nav .why")).to_contain_text("contient un guillemet droit")
                        check_contrast(page, "blocked main action")
                        shot(page, "bloque.png")
                        page.locator(".step-nav .why").get_by_role("button", name="Ouvrir « Textes »").click()
                        expect(step_count).to_have_text("Étape 2 sur 4")
                        expect(tab("Textes")).to_have_attribute("aria-selected", "true")
                        page.get_by_label("Titre", exact=True).fill("Petite photo")
                        expect(page.get_by_text("contient un guillemet droit", exact=False)).to_have_count(0)
                        tab("Style").click()
                        expect(page.get_by_role("button", name="Générer l’affiche")).to_be_enabled()
                        expect(page.locator(".step-nav .why")).to_have_count(0)
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        agree = page.get_by_role("dialog").get_by_label("J’accepte une qualité réduite", exact=False)
                        page.get_by_role("button", name="Générer l’affiche").click()
                        expect(agree).to_be_visible()
                        expect(page.get_by_role("button", name="Lancer la génération")).to_be_disabled()
                        page.get_by_role("dialog").get_by_role("button", name="Annuler").click()
                        # After a reload the editor no longer knows the photo is small: the server refuses, and the same dialog
                        # comes back with the agreement. No generation starts without it.
                        page.reload()
                        expect(page.get_by_role("heading", name="Petite photo", exact=True)).to_be_visible()
                        before = len(sent)
                        # A poster without a version reopens on its first step; the walk is the same.
                        expect(step_count).to_have_text("Étape 2 sur 4")
                        proceed.click()
                        proceed.click()
                        page.get_by_role("button", name="Générer l’affiche").click()
                        expect(agree).to_have_count(0)
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(agree).to_be_visible()
                        expect(page.get_by_role("button", name="Lancer la génération")).to_be_disabled()
                        assert sent[before]["acknowledged_warnings"] == [], sent[before]
                        agree.check()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
                        assert sent[-1]["acknowledged_warnings"] == ["low_resolution"], sent[-1]
                        # The phone-first editor (R-POSTER-EDITOR-007, D-POSTER-EDITOR-005 part A) on a low-end Android
                        # phone: 360 × 740 with a touch pointer, same session.
                        phone = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True,
                                                    color_scheme="dark", storage_state=page.context.storage_state())
                        mobile = phone.new_page()
                        mobile.set_default_timeout(10000)
                        mobile.on("pageerror", lambda error: errors.append(str(error)))
                        mobile.goto(ORIGIN)
                        no_sideways = "document.documentElement.scrollWidth <= innerWidth"
                        assert mobile.evaluate("matchMedia('(pointer: coarse)').matches")
                        # Outside the editor « Créer », « Mes affiches » and « Styles » are a bar at the bottom, the current
                        # one marked; the header does not blur (it would hold the bar), the bar does; the page ends above it.
                        nav = mobile.locator(".nav")
                        expect(nav).to_be_visible()
                        expect(mobile.get_by_label("Photos du produit")).to_be_attached()
                        bottom_bar = nav.bounding_box()
                        assert abs(bottom_bar["y"] + bottom_bar["height"] - 740) < 1 and bottom_bar["width"] == 360, bottom_bar
                        expect(nav.locator("a[aria-current=page]")).to_have_text("Créer")
                        assert all(link.bounding_box()["height"] >= 44 for link in nav.locator("a").all())
                        assert mobile.evaluate(blur, ".app-header") == "none" and mobile.evaluate(blur, ".nav") != "none"
                        assert mobile.evaluate("parseFloat(getComputedStyle(document.querySelector('main')).paddingBottom)") >= bottom_bar["height"]
                        mobile.wait_for_function(no_sideways)
                        check_contrast(mobile, "intake at 360 px with the bottom navigation")
                        shot(mobile, "phone-intake.png", full_page=False)
                        toggle_theme(mobile, "Passer au thème clair")
                        check_contrast(mobile, "intake at 360 px, light theme")
                        toggle_theme(mobile, "Passer au thème sombre")
                        nav.locator("a", has_text="Mes affiches").tap()
                        expect(nav.locator("a[aria-current=page]")).to_contain_text("Mes affiches")
                        nav.locator("a", has_text="Créer").tap()
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
                        # On arrival in « Textes » the first field starts in the upper 60 % of the screen.
                        expect(mobile.locator(".step-count")).to_have_text("Étape 2 sur 4")
                        first_field = mobile.get_by_label("Titre", exact=True).bounding_box()
                        assert first_field["y"] < 444, first_field
                        mobile.wait_for_function(no_sideways)
                        check_contrast(mobile, "step Textes at 360 px with a touch pointer")
                        shot(mobile, "phone-step-textes.png", full_page=False)
                        # The draft is a preview: its « Aperçu » pill is in front of everything at its centre.
                        pill = mobile.locator(".frame .badge")
                        expect(pill).to_have_text("Aperçu")
                        assert topmost(pill)
                        mobile.evaluate("scrollTo({ top: 400, behavior: 'instant' })")
                        assert top_bar.bounding_box()["y"] == 0
                        mobile.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
                        # A tap on the thumbnail opens the poster large instead of selecting an element.
                        mobile.locator(".frame").tap()
                        sheet = mobile.get_by_role("dialog", name="Affiche")
                        expect(sheet).to_be_visible()
                        sheet.get_by_role("button", name="Revenir à l’étape").tap()
                        expect(mobile.get_by_role("dialog")).to_have_count(0)
                        proceed_phone = mobile.get_by_role("button", name="Continuer", exact=True)
                        proceed_phone.tap()
                        proceed_phone.tap()
                        mobile.get_by_role("button", name="Générer l’affiche").tap()
                        mobile.get_by_role("button", name="Lancer la génération").tap()
                        expect(mobile.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
                        # The review shows one image at a time, at full width, « La version » first.
                        version_image = mobile.get_by_alt_text("Version générée à vérifier")
                        photo_image = mobile.get_by_alt_text("Photo originale 1 à comparer")
                        expect(version_image).to_be_visible()
                        expect(photo_image).to_be_hidden()
                        expect(mobile.get_by_role("button", name="La version", exact=True)).to_have_attribute("aria-pressed", "true")
                        assert version_image.bounding_box()["width"] >= 300
                        check_contrast(mobile, "review at 360 px, the version")
                        shot(mobile, "phone-review.png", full_page=False)
                        mobile.get_by_role("button", name="Votre photo", exact=True).tap()
                        expect(photo_image).to_be_visible()
                        expect(version_image).to_be_hidden()
                        expect(mobile.get_by_role("button", name="Tout est conforme, approuver")).to_be_in_viewport()
                        mobile.get_by_role("button", name="Tout est conforme, approuver").tap()
                        expect(mobile.get_by_role("tab")).to_have_count(4)
                        # Once a version exists the real image stays on screen, at least 200 px tall, while the controls
                        # scroll under it; its state badge is in front; the versions are a row of small thumbnails under
                        # it; the groups are a row of tools with icons; nothing scrolls sideways.
                        canvas_phone = mobile.locator(".poster-canvas canvas").first
                        poster_box = lambda: canvas_phone.bounding_box()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 200")
                        expect(canvas_phone).to_be_in_viewport(ratio=1)
                        state_badge = mobile.locator(".frame .badge")
                        expect(state_badge).to_have_text("Version 1 · approuvée")
                        assert topmost(state_badge)
                        thumb = mobile.locator(".version img").first.bounding_box()
                        assert (round(thumb["width"]), round(thumb["height"])) == (56, 70), thumb
                        assert thumb["y"] > poster_box()["y"] + poster_box()["height"]
                        expect(mobile.locator(".versions .state").first).to_have_text("Approuvée")
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
                        assert poster_box()["height"] >= 200 and poster_box()["y"] >= top_bar.bounding_box()["height"] - 1
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
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 200")
                        expect(main_bar).to_be_visible()
                        # And a focus that leaves without a tap brings it back too.
                        price_field.focus()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height <= 100")
                        price_field.blur()
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 200")
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
                        mobile.wait_for_function("document.querySelector('.poster-canvas canvas').getBoundingClientRect().height >= 200")
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
                        desk = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
                        screen = desk.new_page()
                        screen.set_default_timeout(10000)
                        screen.on("pageerror", lambda error: errors.append(str(error)))
                        for address, name in ((f"#{light_poster}", "editeur"), ("#", "creer")):
                            screen.goto(f"{ORIGIN}/{address}")
                            if name == "editeur":
                                expect(screen.get_by_role("tab", name="Textes", exact=True)).to_have_attribute("aria-selected", "true")
                                # The poster is drawn once its scene is loaded; the main action waits for it.
                                expect(screen.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_enabled()
                            else:
                                expect(screen.get_by_label("Photos du produit")).to_be_attached()
                            for theme, scheme in (("clair", "light"), ("sombre", "dark")):
                                screen.emulate_media(color_scheme=scheme)
                                screen.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
                                screen.wait_for_function(NO_SIDEWAYS)
                                check_one_blur(screen, f"{name} at 1366 px, {theme}")
                                check_contrast(screen, f"{name} at 1366 px, {theme}")
                                shot(screen, f"look-1366-{theme}-{name}.png", full_page=False)
                        desk.close()
                        assert not errors, errors
                        # A poster's address opened without a session: after the sign-in the owner is on that poster.
                        other = browser.new_page(viewport={"width": 390, "height": 844})
                        other.goto(f"{ORIGIN}/#{copy_id}")
                        other.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
                        other.get_by_role("button", name="Ouvrir l’atelier").click()
                        expect(other.get_by_label("Titre", exact=True)).to_be_visible()
                        assert other.url.endswith(f"#{copy_id}"), other.url
                        other.close()
                        print("Browser smoke passed: upload, identity, lost-response replay, scene/review, price undo, keyboard, autosave/reopen/conflict copy, overflow/glyph warnings, desktop/mobile, zero spend.")
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
                server.should_exit = True
                thread.join(timeout=20)
                assert not thread.is_alive(), "API did not stop"


if __name__ == "__main__":
    run()
