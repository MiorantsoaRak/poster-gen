"""Run from backend after the production frontend build. Stub stores and providers only."""
import json
import re
import subprocess
import tempfile
from urllib.parse import urlencode
from uuid import uuid4
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from affiche.posters.facebook_connect import STUB_CODE
import browser_smoke as smoke
import share_browser as sb
from terms_browser import open_atelier, set_terms


def home_account(page):
    """Accueil's own « Mon compte » link, the entry these walks were written for (the shell's is checked apart)."""
    page.get_by_role("region", name="Accueil", exact=True).get_by_role("link", name="Mon compte").click()


def set_theme(page, scheme):
    page.emulate_media(color_scheme=scheme)
    page.wait_for_function("theme => document.documentElement.dataset.theme === theme", arg="clair" if scheme == "light" else "sombre")


# The top bar's controls as drawn: each one's box, and whether its text is cut (D-REDESIGN-002, R-REDESIGN-003).
TOP_BAR_JS = r"""header => [...header.querySelectorAll(':scope > *')].filter(e => e.checkVisibility() && e.getBoundingClientRect().width)
  .filter(e => !e.matches('.grow')).map(e => { const box = e.getBoundingClientRect()
    return { name: e.getAttribute('aria-label') || e.textContent.trim(), text: e.matches('.top-title'), left: box.left, right: box.right, top: box.top, bottom: box.bottom,
             width: box.width, height: box.height, cut: [e, ...e.querySelectorAll('*')].some(x => x.scrollWidth > x.clientWidth + 1 && !x.matches('.top-title')) } })"""


def logo_of(locator, scheme):
    """The kit's horizontal logo of the theme, whole, at its minimum width (R-SHOP-DASH-008 amended by ADR-123)."""
    image = locator.locator("img:visible")
    expect(image).to_have_count(1)
    expect(image).to_have_js_property("complete", True)
    assert image.evaluate("e => e.naturalWidth > 0")
    assert image.bounding_box()["width"] >= 220
    assert ("reverse" in image.get_attribute("src")) == (scheme == "dark"), image.get_attribute("src")


def walk_header(browser):
    """The shell's logo, top bar and shop name (D-REDESIGN-002): signed out, the theme switch alone and the logo above the
    sign-in; over 1180 px the sidebar's logo and no name typed beside it, in Figtree; the top bar in one row at 360 px with
    a five-digit balance, on Accueil and in the chat, and at 800 px with the poster's name; a long shop name cut in the
    account row and kept whole in its title."""
    context = browser.new_context(viewport={"width": 1440, "height": 740})
    try:
        page = context.new_page()
        open_atelier(page, "#accueil")
        header = page.locator(".app-header")
        for width in (360, 1440):
            page.set_viewport_size({"width": width, "height": 740})
            for scheme in ("light", "dark"):
                set_theme(page, scheme)
                expect(page.get_by_label("Identifiant de la boutique")).to_be_visible()
                assert [item["name"] for item in header.evaluate(TOP_BAR_JS)] == ["Passer au thème sombre" if scheme == "light" else "Passer au thème clair"]
                expect(page.locator("aside.side, nav.phone-bar")).to_have_count(0)
                logo_of(page.locator("main.gate"), scheme)
                page.wait_for_function(smoke.NO_SIDEWAYS)
        def long_name(route):
            response = route.fetch()
            profile = response.json()
            profile["name"] = "Boutique " * 17
            route.fulfill(json=profile)
        page.route("**/api/shop-profile", long_name)
        page.route("**/api/balance", lambda route: route.fulfill(json={**route.fetch().json(), "available": 12345}))
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        side = page.locator("aside.side")
        brand = side.get_by_role("link", name="Doka Studio — Accueil", exact=True)
        for width in (1181, 1440):
            page.set_viewport_size({"width": width, "height": 740})
            for scheme in ("light", "dark"):
                set_theme(page, scheme)
                expect(brand).to_have_attribute("href", "#accueil")
                expect(brand.get_by_role("img")).to_have_count(0)
                logo_of(brand, scheme)
                assert "Doka Studio" not in side.inner_text()
                expect(header.get_by_role("link", name="Doka Studio — Accueil")).to_be_hidden()
                page.wait_for_function(smoke.NO_SIDEWAYS)
        assert page.evaluate("[...document.fonts].some(face => face.family.replace(/\"/g, '') === 'Figtree' && face.status === 'loaded')")
        assert side.get_by_role("link", name="Accueil", exact=True).evaluate("e => getComputedStyle(e).fontFamily").startswith("Figtree")
        # The phone's top bar: one row, nothing cut; menu, D, credits on Accueil; in the chat menu, switch, plus, credits.
        page.set_viewport_size({"width": 360, "height": 740})
        pill = header.get_by_role("link", name="12345 crédits")
        expect(pill).to_have_text("12345")
        def one_row(where, names, height=64):
            controls = header.evaluate(TOP_BAR_JS)
            assert [item["name"] for item in controls] == names, (where, controls)
            assert header.bounding_box()["height"] <= height, (where, header.bounding_box())
            assert all(not item["cut"] and (item["text"] or item["height"] >= 44 and item["width"] >= 44) for item in controls), (where, controls)
            assert all(left["right"] <= right["left"] + 1 for left, right in zip(controls, controls[1:])), (where, controls)
            assert len({round(item["top"] + item["height"] / 2) for item in controls}) == 1, (where, controls)
            assert controls[-1]["right"] <= page.viewport_size["width"], (where, controls)
            # Each button of the mode switch is a target of its own; the keyboard meets the controls in their visible order.
            for button in header.locator(".seg button").all() if page.viewport_size["width"] <= 420 else []:  # a phone's 44 px
                box = button.bounding_box()
                assert box["width"] >= 44 and box["height"] >= 44, (where, button.inner_text(), box)
            focusables = header.locator("a:visible, button:visible")
            named = "e => e.getAttribute('aria-label') || e.textContent.trim()"
            order = [control.evaluate(named) for control in focusables.all()]
            focusables.first.focus()
            met = [page.evaluate(f"({named})(document.activeElement)")]
            for _ in order[1:]:
                page.keyboard.press("Tab")
                met.append(page.evaluate(f"({named})(document.activeElement)"))
            assert met == order, (where, met, order)
            page.wait_for_function(smoke.NO_SIDEWAYS)
        one_row("Accueil, 360 px", ["Ouvrir le menu", "Doka Studio — Accueil", "12345 crédits"])
        page.goto(smoke.ORIGIN + "/#message")
        expect(page.get_by_label("Votre message")).to_be_visible()
        one_row("the chat, 360 px", ["Ouvrir le menu", "Façon de créer", "Nouvelle affiche", "12345 crédits"])
        # A poster's name in the creator from 721 px, cut by an ellipsis when long: aria-hidden, the page has its title.
        title = ("Casque " + "Sony WH-CH720N " * 8).strip()
        page.goto(smoke.ORIGIN + "/#etapes")
        page.get_by_label("Photos du produit").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        expect(page.locator(".photo-strip img")).to_have_count(1)
        page.get_by_label("Nom du produit", exact=True).fill(title)
        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
        page.get_by_label("Les photos correspondent").check()
        page.get_by_role("button", name="Préparer mon affiche").click()
        expect(page.get_by_label("Titre", exact=True)).to_have_value(title)
        page.goto(smoke.ORIGIN + "/#message-" + page.url.split("#")[1])
        expect(page.get_by_label("Votre message")).to_be_visible()
        one_row("the chat with a long poster name, 360 px", ["Ouvrir le menu", "Façon de créer", "Nouvelle affiche", "12345 crédits"])
        page.set_viewport_size({"width": 800, "height": 740})
        one_row("the chat with a long poster name, 800 px", ["Ouvrir le menu", "Doka Studio — Accueil", title, "Façon de créer", "12345 crédits", "Passer au thème clair"])
        top = header.locator(".top-title")
        expect(top).to_have_attribute("aria-hidden", "true")
        assert top.evaluate("e => e.scrollWidth > e.clientWidth && getComputedStyle(e).textOverflow === 'ellipsis'")
        # The shop's name in the account row: cut, and whole in its title.
        page.set_viewport_size({"width": 1440, "height": 740})
        account = side.locator("a.account")
        expect(account).to_have_attribute("title", "Boutique " * 17)
        assert account.locator(".label").evaluate("e => e.scrollWidth > e.clientWidth")
        # The next walks start from a shop with no poster: this one leaves the list.
        poster = page.request.get(smoke.ORIGIN + "/api/creations/" + page.url.split("#message-")[1]).json()
        removed = page.request.post(f"{smoke.ORIGIN}/api/creations/{poster['id']}/abandon", data={}, headers={
            "Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE), "If-Match": f'"{poster["revision"]}"', "Idempotency-Key": str(uuid4())})
        assert removed.ok, removed.text()
    finally:
        context.close()


# A poster's state in a list (D-REDESIGN-004): the four states on the first four rows, each row's word and tone.
STATES = (("draft", "Brouillon", "badge"), ("to_review", "À vérifier", "badge warn"), ("approved", "Approuvée", "badge ok"), ("confirmed", "Confirmée", "badge ok"))
# A row's title, badge and details in the document's order, with where each is drawn.
ROW_JS = """row => [...row.querySelectorAll('strong, .badge, .details')].map(e => { const box = e.getBoundingClientRect()
  return { kind: e.matches('strong') ? 'title' : e.matches('.badge') ? 'badge' : 'details', text: e.textContent.trim(), tone: e.className, top: box.top, bottom: box.bottom } })"""


def four_states(route):
    listing = route.fetch().json()
    for item, (state, _, _) in zip(listing["items"], STATES):
        item["state"] = state
    route.fulfill(json=listing)


def check_states(rows, details):
    """Each row reads its title, then its state's badge, then its details (none on Accueil), one under the other."""
    for index, (_, word, tone) in enumerate(STATES):
        parts = rows.nth(index).evaluate(ROW_JS)
        assert [part["kind"] for part in parts] == ["title", "badge", "details"][:3 if details else 2], parts
        assert (parts[1]["text"], parts[1]["tone"]) == (word, tone), parts
        assert all(after["top"] >= before["bottom"] - 1 for before, after in zip(parts, parts[1:])), parts
        if details:
            assert " Ar · " in parts[2]["text"] and word not in parts[2]["text"], parts


# The frame of the shop's five screens (D-POLISH-003). A title: its type, and what shows its focus.
TITLE_JS = """e => { const style = getComputedStyle(e)
  return [style.fontSize, style.lineHeight, style.fontWeight, style.outlineStyle, e.matches(':focus-visible'), style.textDecorationLine,
          style.textDecorationThickness, style.textUnderlineOffset] }"""
# The lines of text of a screen that come closer than 16 px to an edge of the window.
NEAR_EDGE_JS = r"""root => {
  const width = document.documentElement.clientWidth, near = [], range = document.createRange()
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.textContent.trim() || !node.parentElement.checkVisibility()) continue
    range.selectNodeContents(node)
    for (const line of range.getClientRects()) if (line.width && (line.left < 16 || line.right > width - 16)) near.push(`${line.left}–${line.right}: ${node.textContent.trim().slice(0, 40)}`)
  }
  return near
}"""
# Each link of the bottom bar: the text it paints, its smallest size, its lines as drawn (a DOM range, not a scroll width)
# and whether they stay inside the link and inside everything that clips them, and the link's box. A text is painted when
# it is visible, nothing up to the link is faded to nothing, and it is not in a 1 px box kept for a screen reader.
BAR_JS = r"""nav => [...nav.querySelectorAll('a')].map(link => {
  const chain = node => { const up = []; for (let e = node.parentElement; ; e = e.parentElement) { up.push(e); if (e === link) return up } }
  const clips = e => { const style = getComputedStyle(e); return style.overflowX !== 'visible' || style.overflowY !== 'visible' || style.clipPath !== 'none' }
  const painted = up => getComputedStyle(up[0]).visibility === 'visible' && up.every(e => { const style = getComputedStyle(e), box = e.getBoundingClientRect()
    return style.display !== 'none' && Number(style.opacity) > 0 && !(clips(e) && box.width <= 1 && box.height <= 1) })
  const walker = document.createTreeWalker(link, NodeFilter.SHOW_TEXT), range = document.createRange(), shown = [], lines = [], within = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const up = node.textContent.trim() && chain(node)
    if (!up || !painted(up)) continue
    shown.push(node)
    const bounds = up.filter(clips).concat(link).map(e => e.getBoundingClientRect())
    range.selectNodeContents(node)
    for (const line of [...range.getClientRects()].filter(line => line.width)) {
      lines.push(line)
      within.push(bounds.every(box => line.left >= box.left && line.right <= box.right && line.top >= box.top && line.bottom <= box.bottom))
    }
  }
  const box = link.getBoundingClientRect()
  return { text: shown.map(node => node.textContent).join('').trim(), size: Math.min(...shown.map(node => parseFloat(getComputedStyle(node.parentElement).fontSize))),
           lines: new Set(lines.map(line => Math.round(line.top))).size, width: box.width, height: box.height, inside: within.every(Boolean) }
})"""


def level_one(page):
    """The level-one headings of Chromium's own accessibility tree. Playwright's role queries keep an inert background
    (Playwright 1.64); this tree leaves it out, as a screen reader does."""
    cdp = page.context.new_cdp_session(page)
    try:
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
    finally:
        cdp.detach()
    return [node["name"]["value"] for node in nodes if not node.get("ignored") and node.get("role", {}).get("value") == "heading"
            and any(item["name"] == "level" and item["value"]["value"] == 1 for item in node.get("properties", []))]


def check_bar(nav, items, where):
    """The bottom bar on a phone (D-POLISH-003, D-REDESIGN-002): five items in order by their full French names. The four
    labelled ones each show their short text on one line inside their link at 11 px or more, a 44 × 44 px target, the name
    containing what is shown; the centre « Nouvelle affiche » is a painted plus on a target of 44 × 44 px or more."""
    links = nav.get_by_role("link")
    names = [name for _, name in items[:2]] + ["Nouvelle affiche"] + [name for _, name in items[2:]]
    expect(links).to_have_count(5)
    for link, name in zip(links.all(), names):
        expect(link).to_have_accessible_name(name)
    for shown, name in items:
        assert shown.casefold() in name.casefold(), (shown, name)
    measured = nav.evaluate(BAR_JS)
    labelled = measured[:2] + measured[3:]
    assert [item["text"] for item in labelled] == [shown for shown, _ in items], (where, measured)
    for item in labelled:
        assert item["size"] >= 11 and item["lines"] == 1 and item["inside"] and item["width"] >= 44 and item["height"] >= 44, (where, item)
    centre = links.nth(2)
    assert measured[2]["text"] == "" and measured[2]["width"] >= 44 and measured[2]["height"] >= 44, (where, measured[2])
    assert centre.evaluate("e => { const plus = e.querySelector('svg path'); const box = plus.getBoundingClientRect(); return box.width > 0 && box.height > 0 && getComputedStyle(plus).stroke !== 'none' }"), where


def walk_frame(browser):
    """One frame for the shop's five screens (D-POLISH-003), on a shop with no poster yet: one title each at one size,
    focused on arrival with no box and underlined for the keyboard, the next Tab on the screen's first control; one width
    and the same edges at 1440 px, 16 px from the edges at 360 px; then the phone's bottom bar, with four items and with
    five, for every balance and list size."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.add_init_script(smoke.STEPS_FIRST)
        open_atelier(page, "#accueil")
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        nav = page.get_by_role("navigation", name="Navigation", exact=True)
        home = page.get_by_role("region", name="Accueil", exact=True)
        expect(home).to_be_visible()
        title = page.get_by_role("heading", level=1)
        edges = []
        for name, link, first in (
                ("Mes affiches", nav.get_by_role("link", name=re.compile("^Mes affiches")), page.locator(".gallery").get_by_role("button", name="Nouvelle affiche")),  # the page's action, then its filter
                ("Styles", nav.get_by_role("link", name=re.compile("^Styles")), page.locator(".look-card").first),
                ("Accueil", nav.get_by_role("link", name="Accueil", exact=True), home.get_by_role("button", name="Actualiser")),
                ("Mes crédits", home.get_by_role("link", name="Voir mes crédits"), page.locator(".shop-credits").get_by_role("link", name="Retour à l’accueil")),
                ("Mon compte", home.get_by_role("link", name="Mon compte"), page.locator(".shop-account").get_by_role("link", name="Retour à l’accueil"))):
            if name == "Mon compte":
                page.go_back()
                expect(home).to_be_visible()
            # Arrived with the keyboard: the title has the focus, no box, a 2 px underline 6 px under it.
            link.focus()
            page.keyboard.press("Enter")
            expect(title).to_have_count(1)
            expect(title).to_have_accessible_name(name)
            expect(title).to_be_focused()
            assert title.evaluate(TITLE_JS) == ["26px", "32px", "800", "none", True, "underline", "2px", "6px"], (name, title.evaluate(TITLE_JS))
            page.keyboard.press("Tab")
            expect(first).to_be_focused()
            box = page.get_by_role("region", name=name, exact=True).bounding_box()
            edges.append((name, box["x"], box["x"] + box["width"]))
        assert all(right - left == 860 for _, left, right in edges), edges
        assert len({(left, right) for _, left, right in edges}) == 1, edges
        # A mouse arrival: the title has the focus, and nothing shows it.
        nav.get_by_role("link", name=re.compile("^Styles")).click()
        expect(title).to_be_focused()
        assert title.evaluate(TITLE_JS)[3:6] == ["none", False, "none"]
        # A page opened directly: until the first tap a browser counts the script's focus as the keyboard's, and the title
        # must still show nothing (every shop opening the app saw its title underlined; found in the after captures).
        page.reload()
        expect(title).to_have_accessible_name("Styles")
        expect(title).to_be_focused()
        assert title.evaluate(TITLE_JS)[3] == "none" and title.evaluate(TITLE_JS)[5] == "none", title.evaluate(TITLE_JS)

        page.set_viewport_size({"width": 360, "height": 740})
        for route, name, loaded in (("accueil", "Accueil", page.get_by_text("Aucune affiche pour le moment.")),
                                    ("affiches", "Mes affiches", page.get_by_text("Vos affiches apparaîtront ici dès la première création.")),
                                    ("styles", "Styles", page.locator(".look-card").first),
                                    ("credits", "Mes crédits", page.get_by_text("Disponibles", exact=True)),
                                    ("compte", "Mon compte", page.get_by_label("Nom de la boutique"))):
            page.goto(f"{smoke.ORIGIN}/#{route}")
            expect(loaded).to_be_visible()
            expect(title).to_have_accessible_name(name)
            page.wait_for_function(smoke.NO_SIDEWAYS)
            gutters = page.locator("main:not(.gate)").evaluate("e => [getComputedStyle(e).paddingLeft, getComputedStyle(e).paddingRight]")
            assert gutters == ["16px", "16px"], (name, gutters)
            near = page.get_by_role("region", name=name, exact=True).evaluate(NEAR_EDGE_JS)
            assert not near, f"{name} at 360 px, text closer than 16 px to an edge: {near}"

        # The bar: the same five items on the dashboard's screens and on the creator's form; the list as the server says.
        # The balance is the top bar's pill (D-REDESIGN-002): its number, or « Crédits » unread, named in full.
        balance = page.request.get(smoke.ORIGIN + "/api/balance").json()
        answers = {"available": 0, "posters": 0}
        def read_balance(route):
            if answers["available"] is None:
                route.abort()
            else:
                route.fulfill(json={**balance, "available": answers["available"]})
        page.route("**/api/balance", read_balance)
        page.route("**/api/creations?limit=50&status=active", lambda route: route.fulfill(json={"items": [], "total": answers["posters"], "next_cursor": None}))
        pill = page.locator(".app-header .credits-pill")
        nav = page.get_by_role("navigation", name="Navigation", exact=True).and_(page.locator("nav.phone-bar"))
        nav.get_by_role("link", name="Nouvelle affiche", exact=True).click()  # the creator reads the styles: their count is known from here on
        expect(page.get_by_label("Photos du produit")).to_be_enabled()
        for posters in (0, 3, 120):
            answers["posters"] = posters
            nav.get_by_role("link", name=re.compile("^Mes affiches")).click()
            expect(nav.get_by_role("link", name=f"Mes affiches {posters}", exact=True)).to_be_visible()
            for available in (-2, 0, 117, 12345, None):
                answers["available"] = available
                with page.expect_request("**/api/balance"):
                    nav.get_by_role("link", name="Accueil", exact=True).click()
                items = [("Accueil", "Accueil"), ("Affiches", f"Mes affiches {posters}"), ("Styles", "Styles 3"), ("Compte", "Mon compte")]
                credits = ("Crédits", "Mes crédits") if available is None else (str(available), f"{available} crédit" + ("" if abs(available) == 1 else "s"))
                where = f"{posters} affiches, solde {available}"
                expect(home.get_by_role("button", name="Réessayer le solde")).to_have_count(int(available is None))
                check_bar(nav, items, "Accueil, " + where)
                expect(pill).to_have_text(credits[0])
                expect(pill).to_have_accessible_name(credits[1])
                nav.get_by_role("link", name="Nouvelle affiche", exact=True).click()
                expect(page.get_by_label("Photos du produit")).to_be_enabled()
                check_bar(nav, items, "creator, " + where)
                expect(pill).to_have_text(credits[0])
        assert not errors, errors
    finally:
        context.close()


def walk(browser, out):
    context = browser.new_context(viewport={"width": 360, "height": 640}, color_scheme="light", timezone_id="UTC")
    try:
        page = context.new_page()
        held, reads, errors = [], [], []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("request", lambda request: reads.append(request.url.partition("/api/")[2]) if "/api/" in request.url else None)
        page.route("**/api/creations?limit=5", lambda route: held.append(route))
        open_atelier(page)
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        page.wait_for_url("**/#accueil")
        home = page.get_by_role("region", name="Accueil", exact=True)
        expect(home.get_by_text("Disponibles", exact=True)).to_be_visible()
        expect(home.get_by_text("Lecture des affiches…")).to_be_visible()
        all_clear = home.get_by_text("Aucune affiche à vérifier.", exact=True)
        expect(all_clear).to_be_visible()
        # A cold Accueil makes the requests it made before the shell, each once: the sidebar shares Accueil's reads
        # (D-REDESIGN-002), and nothing of the creator is read: the capabilities at most once, for the ways in to
        # « Publier sur Facebook » (D-FB-POST-005).
        cold = list(reads)
        assert [cold.count(path) for path in ("shop-dashboard", "creations?limit=5", "balance")] == [1, 1, 1], cold
        assert not any(path.startswith(("looks", "shop-profile", "creations?limit=50")) for path in cold) and cold.count("capabilities") <= 1, cold
        pending_summary = []
        page.route("**/api/shop-dashboard", lambda route: pending_summary.append(route))
        with page.expect_request("**/api/shop-dashboard"):
            home.get_by_role("button", name="Actualiser").click()
        expect(all_clear).to_have_count(0)
        expect(home.get_by_text("Dernier suivi connu à", exact=False)).to_be_visible()
        pending_summary.pop().abort()
        expect(home.get_by_role("button", name="Réessayer le suivi")).to_be_visible()
        expect(all_clear).to_have_count(0)
        page.unroute("**/api/shop-dashboard")
        home.get_by_role("button", name="Réessayer le suivi").click()
        expect(all_clear).to_be_visible()
        assert "shop-dashboard" in reads and "creations?limit=5" in reads
        assert not any(path.startswith(("looks", "shop-profile", "creations?limit=50")) for path in reads) and reads.count("capabilities") <= 1, reads
        while held:
            held.pop().abort()
        expect(home.get_by_text("Affiches indisponibles.", exact=False)).to_be_visible()
        assert home.get_by_text("Aucune affiche pour le moment.").count() == 0
        page.unroute("**/api/creations?limit=5")
        home.get_by_role("button", name="Réessayer les affiches").click()
        expect(home.get_by_text("Aucune affiche pour le moment.")).to_be_visible()
        for scheme in ("light", "dark"):
            set_theme(page, scheme)
            page.wait_for_function(smoke.NO_SIDEWAYS)
            smoke.check_contrast(page, f"Accueil 360, {scheme}")
            page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            page.screenshot(path=str(out / f"accueil-{scheme}.png"), full_page=True)
        # The home sections retain their last successful data when an explicit refresh fails.
        stamp = home.locator(".home-bal .meta")
        page.clock.set_fixed_time("2026-11-18T10:30:00Z")
        home.get_by_role("button", name="Actualiser").click()
        expect(stamp).to_have_text("Solde vérifié à 10:30.")
        page.clock.set_fixed_time("2026-11-18T10:40:00Z")
        page.route("**/api/balance", lambda route: route.abort())
        home.get_by_role("button", name="Actualiser").click()
        expect(home.get_by_role("button", name="Réessayer le solde")).to_be_visible()
        expect(stamp).to_have_text("Dernier solde connu à 10:30.")
        expect(home.get_by_text("Disponibles", exact=True)).to_be_visible()
        page.unroute("**/api/balance")
        home.get_by_role("button", name="Réessayer le solde").click()
        expect(home.get_by_role("button", name="Réessayer le solde")).to_have_count(0)
        expect(stamp).to_have_text("Solde vérifié à 10:40.")
        for title, link, route in (("Mes crédits", "Voir mes crédits", "credits"), ("Mon compte", "Mon compte", "compte")):
            home.get_by_role("link", name=link).click()
            page.wait_for_url(f"**/#{route}")
            expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()
            page.reload()
            expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()
            page.go_back()
            expect(home).to_be_visible()
        # A failed creator-only read belongs to the old destination once the user chooses another view.
        pending_caps = []
        page.route("**/api/capabilities", lambda route: pending_caps.append(route))
        with page.expect_request("**/api/capabilities"):
            home.get_by_role("link", name="Créer une affiche").click()
        home.get_by_role("link", name="Mon compte").click()
        pending_caps.pop().abort()
        expect(page.get_by_role("heading", name="Mon compte")).to_be_visible()
        page.wait_for_url("**/#compte")
        page.unroute("**/api/capabilities")
        smoke.go(page, "Accueil")
        home.get_by_role("link", name="Créer une affiche").click()
        expect(page.get_by_label("Votre message")).to_be_visible()
        page.locator(".chat input[type=file]").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        page.go_back()
        dialog = page.get_by_role("dialog", name="Quitter le message ?")
        expect(dialog).to_be_visible()
        assert level_one(page) == [], level_one(page)  # the chat's title is behind the dialog, inert (D-POLISH-003)
        dialog.get_by_role("button", name="Annuler").click()
        expect(page.locator(".chat .pic img").first).to_be_visible()
        assert level_one(page) == ["Créer une affiche"], level_one(page)
        page.go_back()
        dialog.get_by_role("button", name="Quitter sans les envoyer").click()
        expect(home).to_be_visible()
        home.get_by_role("link", name="Créer une affiche").click()
        expect(page.get_by_label("Votre message")).to_be_visible()
        page.locator(".chat input[type=file]").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        page.get_by_role("button", name="Pas à pas", exact=True).click()
        dialog.get_by_role("button", name="Annuler").click()
        expect(page.locator(".chat .pic img").first).to_be_visible()
        assert page.evaluate("localStorage.getItem('affiche.start')") != "steps"
        page.get_by_role("button", name="Pas à pas", exact=True).click()
        dialog.get_by_role("button", name="Quitter sans les envoyer").click()
        page.wait_for_url("**/#etapes")
        smoke.go(page, "Accueil")
        home.get_by_role("link", name="Créer une affiche").click()
        page.wait_for_url("**/#etapes")
        expect(page.get_by_label("Photos du produit")).to_be_enabled()
        # A genuine poster appears in the recent list and opens through the same path as its attention entry.
        headers = {"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE)}
        def post(path, body):
            answer = page.request.post(smoke.ORIGIN + path, headers={**headers, "Idempotency-Key": str(uuid4())}, data=body)
            assert answer.ok, answer.text()
            return answer.json()
        photo = page.request.post(smoke.ORIGIN + "/api/assets", headers=headers, multipart={"role": "original", "file": {
            "name": "photo.jpg", "mimeType": "image/jpeg", "buffer": (smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg").read_bytes()}})
        assert photo.ok, photo.text()
        product = post("/api/product-inputs", {"name": "Casque de la boutique", "variant": "Noir", "photo_assets": [photo.json()["asset"]]})
        made = post("/api/creations", {"input_id": product["id"], "offer": {"title": "Casque de la boutique", "price_ar": 120000},
                                       "brand_selection": {"logo": False, "shop_name": False, "contact": False}})
        recent_id = None
        for number in range(1, 6):
            recent_id = post("/api/creations", {"input_id": product["id"], "offer": {"title": f"Affiche {number}", "price_ar": 120000},
                             "brand_selection": {"logo": False, "shop_name": False, "contact": False}})["id"]
        poster_session = context.storage_state()
        summary = page.request.get(smoke.ORIGIN + "/api/shop-dashboard").json()
        summary["review"] = {"total": 3, "first_creation_id": made["id"], "first_creation_title": made["document"]["offer"]["title"]}
        summary["failed"] = {"total": 1, "first_creation_id": recent_id}  # dashboard response from an older build
        page.route("**/api/shop-dashboard", lambda route: route.fulfill(json=summary))
        smoke.go(page, "Accueil")
        review_action = home.get_by_role("button", name="Vérifier Casque de la boutique")
        expect(review_action).to_be_visible()
        expect(all_clear).to_have_count(0)
        expect(home.get_by_text("+ 2 à vérifier")).to_be_visible()
        expect(home.get_by_role("button", name="Génération échouée")).to_be_visible()
        poster = home.get_by_role("button", name="Affiche 5 Brouillon")
        expect(poster).to_be_visible()
        expect(home.locator(".home-recent button")).to_have_count(5)
        expect(home.locator(".home-recent")).not_to_contain_text("Casque de la boutique")
        page.route("**/api/creations?limit=5", four_states)
        home.get_by_role("button", name="Actualiser").click()
        expect(home.locator(".home-recent .badge.ok")).to_have_count(2)
        check_states(home.locator(".home-recent button"), details=False)
        page.unroute("**/api/creations?limit=5")
        home.get_by_role("button", name="Actualiser").click()
        expect(home.locator(".home-recent .badge.ok")).to_have_count(0)
        for button, target, title in ((review_action, made["id"], "Casque de la boutique"),
                                      (home.get_by_role("button", name="Génération échouée"), recent_id, "Affiche 5"),
                                      (poster, recent_id, "Affiche 5")):
            button.click()
            page.wait_for_url(f"**/#{target}")
            expect(page.get_by_label("Titre", exact=True)).to_have_value(title)
            with page.expect_response(lambda r: r.url.endswith("/api/balance")):
                page.evaluate(smoke.VISIBILITY, True)
                page.evaluate(smoke.VISIBILITY, False)
            page.go_back()
            expect(home).to_be_visible()
        # Summary titles remain available independently of recent posters, including a wrapping long title.
        title = "Offre " + "A" * 140
        summary["failed"]["first_creation_title"] = title
        page.route("**/api/creations?limit=5", lambda route: held.append(route))
        with page.expect_request("**/api/creations?limit=5"):
            home.get_by_role("button", name="Actualiser").click()
        expect(home.get_by_role("button", name="Génération échouée · " + title)).to_be_visible()
        page.wait_for_function(smoke.NO_SIDEWAYS)
        expect(home.get_by_role("link", name="Créer une affiche")).to_be_visible()
        held.pop().continue_()
        page.unroute("**/api/creations?limit=5")
        removed_url = "**/api/creations/" + made["id"]
        page.route(removed_url, lambda route: route.fulfill(status=404, json={"error": {"code": "not_found"}}))
        with page.expect_request("**/api/shop-dashboard"):
            review_action.click()
        expect(page.get_by_role("alert").filter(has_text="Cette affiche n’est plus disponible.")).to_be_visible()
        page.unroute(removed_url)
        # A slow opening poster cannot replace the account address selected while its read was held.
        detail_url = "**/api/creations/" + recent_id
        delayed = []
        page.route(detail_url, lambda route: delayed.append(route))
        with page.expect_request(lambda r: r.url.endswith("/" + recent_id)):
            poster.click()
        home.get_by_role("link", name="Mon compte").click()
        delayed.pop().continue_()
        expect(page.get_by_role("heading", name="Mon compte")).to_be_visible()
        page.wait_for_url("**/#compte")
        page.unroute(detail_url)
        # Updating contact details in Account never applies them retroactively to a saved poster.
        poster_url = smoke.ORIGIN + "/api/creations/" + made["id"]
        before_contact = page.request.get(poster_url).json()
        page.get_by_role("textbox", name="Contact de la boutique", exact=True).fill("Coordonnées actualisées")
        page.get_by_role("button", name="Enregistrer le profil").click()
        expect(page.get_by_text("Profil enregistré.", exact=True)).to_be_visible()
        after_contact = page.request.get(poster_url).json()
        assert after_contact["document"] == before_contact["document"] and after_contact["revision"] == before_contact["revision"]
        smoke.go(page, "Accueil")
        # A stalled or failed first gallery read must never present zeros or a fictitious empty library.
        gallery_url = "**/api/creations?limit=50&status=active"
        page.route(gallery_url, lambda route: delayed.append(route))
        with page.expect_request(lambda r: "limit=50&status=active" in r.url):
            home.get_by_role("link", name="Tout voir").click()
        gallery = page.get_by_role("region", name="Mes affiches")
        expect(gallery.get_by_text("Lecture des affiches…")).to_be_visible()
        delayed.pop().abort()
        expect(gallery.get_by_role("button", name="Réessayer la liste")).to_be_visible()
        expect(gallery.locator(".empty, .meta")).to_have_count(0)
        page.unroute(gallery_url)
        page.route(gallery_url, four_states)
        gallery.get_by_role("button", name="Réessayer la liste").click()
        expect(gallery.locator(".library-item")).to_have_count(6)
        check_states(gallery.locator(".library-item"), details=True)
        # From an open poster, a successful creator reload must yield to the later choice of the gallery.
        page.set_viewport_size({"width": 1366, "height": 768})
        check_states(gallery.locator(".library-item"), details=True)
        # In the 860 px frame a row's state, price and date are whole, under its title: beside it they were cut (D-POLISH-003).
        cut = page.eval_on_selector_all(".library-item :is(.badge, .details)", "parts => parts.filter(part => part.scrollWidth > part.clientWidth || !part.matches('.badge') && !part.textContent.includes(' Ar · ')).map(part => part.textContent)")
        assert not cut, cut
        for scheme in ("light", "dark"):
            set_theme(page, scheme)
            expect(gallery.locator(".library-item .badge").first).to_be_visible()
            smoke.check_contrast(page, f"Mes affiches 1366 with the four states, {scheme}")
        page.unroute(gallery_url)
        gallery.get_by_role("button", name="Affiche 5 Brouillon", exact=False).click()
        expect(page.get_by_label("Titre", exact=True)).to_have_value("Affiche 5")
        page.route("**/api/capabilities", lambda route: pending_caps.append(route))
        with page.expect_request("**/api/capabilities"):
            smoke.go(page, "Nouvelle affiche")
        smoke.go(page, "Mes affiches")
        pending_caps.pop().continue_()
        expect(gallery).to_be_visible()
        page.wait_for_url("**/#affiches")
        page.unroute("**/api/capabilities")
        page.set_viewport_size({"width": 360, "height": 640})
        smoke.go(page, "Accueil")
        balance = page.request.get(smoke.ORIGIN + "/api/balance").json()
        balance["available"] = 0
        balance["blocked"]["scene"] = {"reason": "terms", "message_fr": "Acceptez les conditions."}
        page.route("**/api/balance", lambda route: route.fulfill(json=balance))
        home.get_by_role("button", name="Actualiser").click()
        expect(home.get_by_role("button", name="Lire les conditions")).to_be_visible()
        expect(home.get_by_role("link", name="Obtenir des crédits")).to_have_count(0)
        page.route("**/api/balance", lambda route: route.abort(), times=1)
        home.get_by_role("button", name="Actualiser").click()
        retry = home.get_by_role("button", name="Réessayer le solde")
        expect(retry).to_be_visible()
        expect(home.get_by_role("button", name="Lire les conditions")).to_have_count(0)
        pending_balance = []
        page.route("**/api/balance", lambda route: pending_balance.append(route), times=1)
        with page.expect_request("**/api/balance"):
            retry.click()
        expect(stamp).to_have_text("Dernier solde connu à 10:40.")
        expect(home.locator(".home-numbers strong").first).to_have_text("0")
        expect(home.get_by_role("button", name="Lire les conditions")).to_have_count(0)
        expect(home.get_by_role("link", name="Obtenir des crédits")).to_have_count(0)
        balance["blocked"]["scene"] = None
        balance["available"] = 3
        pending_balance.pop().fulfill(json=balance)
        expect(home.locator(".home-numbers strong").first).to_have_text("3")
        expect(stamp).to_have_text("Solde vérifié à 10:40.")
        page.unroute("**/api/balance")
        page.unroute("**/api/shop-dashboard")
        home.get_by_role("link", name="Créer une affiche").click()
        expect(page.get_by_label("Photos du produit")).to_be_enabled()
        # A late list response cannot restore the dashboard after the identity has changed.
        page.route("**/api/creations?limit=5", lambda route: held.append(route))
        page.route("**/api/shop-dashboard", lambda route: route.fulfill(status=409, json={"error": {"code": "shop_changed"}}))
        smoke.go(page, "Accueil")
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        assert held
        held.pop().fulfill(json={"items": [{"title": "Ancienne boutique"}], "total": 1, "next_cursor": None})
        assert "Ancienne boutique" not in page.locator("body").inner_text()
        expect(home).to_have_count(0)
        assert not errors, errors
        credit_poster_paths(browser, poster_session, made["id"], recent_id)
        current_credit_poster(browser, poster_session, made["id"])
    finally:
        context.close()


# The creator's way to the credits on a phone (D-REDESIGN-002): the top bar's pill, or in the step editor, whose phone
# layout has no top bar, the rail's button.
CREDITS_OPENER = ".app-header .credits-pill:visible, .rail .creator-credits:visible"


def credit_poster_paths(browser, session, first, second):
    context = browser.new_context(storage_state=session, viewport={"width": 360, "height": 640})
    try:
        page = context.new_page()
        page.add_init_script("localStorage.setItem('affiche.start','chat')")
        base = {"type": "job", "id": str(uuid4()), "at": "2026-11-01T10:00:00Z", "creation_id": second,
                "title": "Affiche 5", "removed": False, "kind": "scene", "credit": "spent"}
        page.route("**/api/shop-credit-history?*", lambda r: r.fulfill(json={"items": [base], "next_cursor": None}))
        held = []
        page.route("**/api/assets", lambda r: held.append(r))
        page.goto(f"{smoke.ORIGIN}/#message-{first}")
        with page.expect_request("**/api/assets"):
            page.locator(".chat input[type=file]").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        opener = page.locator(CREDITS_OPENER)
        opener.click()
        panel = page.get_by_role("dialog", name="Mes crédits")
        target = panel.get_by_role("button", name="Affiche 5")
        target.click()
        discard = page.get_by_role("dialog", name="Quitter le message ?")
        discard.get_by_role("button", name="Annuler").click()
        expect(target).to_be_visible()
        expect(page.locator(".chat .pic img").first).to_have_count(1)
        target.click()
        discard.get_by_role("button", name="Quitter sans les envoyer").click()
        page.wait_for_url(f"**/#message-{second}")
        with page.expect_response("**/api/assets"):
            held.pop().continue_()
        expect(page.locator(".chat .pic img")).to_have_count(0)
        expect(page.get_by_role("button", name="Envoyer")).to_be_disabled()

        # The destination adopts the poster before reloading its jobs. A failure then belongs to the creator.
        page.goto("about:blank")
        page.goto(smoke.ORIGIN + "/#credits")
        jobs_url = f"**/api/creations/{second}/jobs"
        page.route(jobs_url, lambda r: r.fulfill(status=503, json={"error": {"code": "unavailable", "message_fr": "Suivi momentanément indisponible."}}))
        page.get_by_role("button", name="Affiche 5").click()
        page.wait_for_url(f"**/#message-{second}")
        expect(page.get_by_role("alert").filter(has_text="Suivi momentanément indisponible.").first).to_be_visible()
        page.unroute(jobs_url)

        # Complete a watched job while the panel is visible. Its newer revision must be adopted behind the panel.
        job_id = str(uuid4())
        pending = {"id": job_id, "kind": "scene", "status": "running", "credit": "pending", "result_ref": None,
                   "created_at": "2026-11-01T10:00:00Z", "started_at": "2026-11-01T10:00:01Z"}
        finished = {**pending, "status": "succeeded", "result_ref": str(uuid4()), "credit": "spent"}
        settled = False
        held_job = []
        page.route(jobs_url, lambda r: r.fulfill(json={"items": [finished if settled else pending]}))
        page.route("**/api/jobs/" + job_id, lambda r: held_job.append(r))
        page.goto("about:blank")
        with page.expect_request("**/api/jobs/" + job_id):
            page.goto(f"{smoke.ORIGIN}/#{second}")
        opener.click()
        expect(panel).to_be_visible()
        length = page.evaluate("history.length")
        url = f"{smoke.ORIGIN}/api/creations/{second}"
        creation = page.request.get(url).json()
        doc = creation["document"]
        doc["offer"]["price_ar"] += 100
        result = page.request.put(url, data=doc, headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE),
                                  "If-Match": f'"{creation["revision"]}"', "Idempotency-Key": str(uuid4())})
        assert result.ok, result.text()
        settled = True
        with page.expect_response(lambda r: r.url.endswith(f"/creations/{second}/jobs")), page.expect_response("**/api/shop-credit-history?*"):
            held_job.pop().fulfill(json=finished)
        expect(panel).to_be_visible()
        assert page.url.endswith("#credits") and page.evaluate("history.length") == length
        page.go_back()
        page.wait_for_url(f"**/#{second}")
        expect(opener).to_be_focused()

        # The initial creation may be assigned its id after the user has opened Credits from the steps form.
        page.unroute("**/api/assets")
        page.goto(smoke.ORIGIN + "/#etapes")
        expect(page.get_by_label("Photos du produit")).to_be_enabled()
        page.get_by_label("Photos du produit").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        expect(page.locator(".photo-strip img")).to_have_count(1)
        page.get_by_label("Nom du produit", exact=True).fill("Affiche en préparation")
        page.get_by_label("Prix en ariary", exact=True).fill("124000")
        page.get_by_label("Les photos correspondent").check()
        creations = []
        page.route("**/api/creations", lambda r: creations.append(r))
        with page.expect_request("**/api/creations"):
            page.get_by_role("button", name="Préparer mon affiche").click()
        opener.click()
        expect(panel).to_be_visible()
        before = page.evaluate("history.length")
        route = creations.pop()
        response = route.fetch()
        created_id = response.json()["id"]
        with page.expect_response(lambda r: r.url.endswith(f"/creations/{created_id}/jobs")):
            route.fulfill(response=response)
        assert page.url.endswith("#credits") and page.evaluate("history.length") == before
        expect(panel).to_be_visible()
        panel.get_by_role("button", name="Fermer").click()
        page.wait_for_url(f"**/#{created_id}")
        expect(opener).to_be_focused()
        expect(page.get_by_label("Titre", exact=True)).to_have_value("Affiche en préparation")

    finally:
        context.close()


def current_credit_poster(browser, session, poster_id):
    """A row for the currently mounted creator closes Credits, whatever the saved creator preference."""
    context = browser.new_context(storage_state=session, viewport={"width": 360, "height": 640})
    try:
        page = context.new_page()
        page.add_init_script("localStorage.setItem('affiche.start', 'steps')")
        row = {"type": "job", "id": str(uuid4()), "kind": "scene", "credit": "spent", "at": "2026-11-01T10:00:00Z",
               "creation_id": poster_id, "title": "Affiche en cours", "removed": False}
        page.route("**/api/shop-credit-history?*", lambda r: r.fulfill(json={"items": [row], "next_cursor": None}))
        opener = page.locator(CREDITS_OPENER)
        panel = page.get_by_role("dialog", name="Mes crédits")
        def select_current(address):
            reads = []
            def seen(request):
                if request.url.endswith("/api/creations/" + poster_id):
                    reads.append(request.method)
            page.on("request", seen)
            opener.click()
            panel.get_by_role("button", name="Affiche en cours").click()
            page.wait_for_url("**/#" + address)
            expect(opener).to_be_focused()
            page.remove_listener("request", seen)
            assert "GET" not in reads, reads
        page.goto(f"{smoke.ORIGIN}/#message-{poster_id}")
        with page.expect_response("**/api/assets"):
            page.locator(".chat input[type=file]").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        select_current("message-" + poster_id)
        expect(page.locator(".chat .pic img").first).to_be_visible()
        expect(page.get_by_role("button", name="Envoyer")).to_be_enabled()

        page.goto("about:blank")
        page.goto(f"{smoke.ORIGIN}/#{poster_id}")
        field = page.get_by_label("Titre", exact=True)
        expect(field).to_be_enabled()
        original = field.input_value()
        field.fill(original + " modifiée")
        undo = page.locator(".undo").get_by_role("button", name="Annuler", exact=True)
        expect(undo).to_be_enabled()
        select_current(poster_id)
        expect(field).to_have_value(original + " modifiée")
        undo.click()
        expect(field).to_have_value(original)
    finally:
        context.close()


def check_balance_explanation(page, view, balance):
    reserved = view.get_by_text("Les crédits en attente sont déjà déduits du solde disponible.")
    empty = view.get_by_text("Un crédit disponible est nécessaire", exact=False)
    for available, pending, reason in [(2, 1, None), (0, 0, "terms"), (-2, 1, "service")]:
        balance.update(available=available, pending=pending)
        restriction = "Acceptez les conditions." if reason == "terms" else "La génération est en pause."
        balance["blocked"]["scene"] = {"reason": reason, "message_fr": restriction} if reason else None
        with page.expect_response("**/api/balance"):
            view.get_by_role("button", name="Actualiser").click()
        expect(view.locator("dd")).to_have_text([f"{available} crédit{'' if abs(available) == 1 else 's'}", f"{pending} crédit{'' if abs(pending) == 1 else 's'}"])
        expect(reserved).to_have_count(int(pending > 0))
        expect(empty).to_have_count(int(available <= 0))
        expect(view.get_by_text(restriction, exact=True)).to_have_count(int(bool(reason)))
        expect(view.get_by_text(balance["purchase_fr"], exact=True)).to_have_count(1)
    checked = view.locator(".credit-balance .meta").inner_text().split(" à ")[-1]
    page.route("**/api/balance", lambda route: route.abort(), times=1)
    view.get_by_role("button", name="Actualiser").click()
    expect(view.get_by_role("button", name="Réessayer le solde")).to_be_visible()
    expect(view.get_by_text("Dernier solde connu à " + checked)).to_be_visible()
    expect(view.locator("dd")).to_have_text(["-2 crédits", "1 crédit"])  # the unit follows the count, as in the shell
    expect(empty).to_have_count(0)
    expect(view.get_by_text(restriction, exact=True)).to_have_count(0)
    view.get_by_role("button", name="Réessayer le solde").click()
    expect(empty).to_be_visible()


def walk_credits(browser, out):
    """Visit Credits during a real pending upload, page through history, then expire the session during a late read."""
    context = browser.new_context(viewport={"width": 360, "height": 640})
    try:
        page = context.new_page()
        requests, uploads, errors = [], [], []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("request", lambda req: requests.append(req.url) if req.method == "POST" else None)
        open_atelier(page, "#message")
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        field = page.get_by_label("Votre message")
        field.fill("Mon texte en cours")
        page.route("**/api/assets", lambda route: uploads.append(route))
        with page.expect_request("**/api/assets"):
            page.locator(".chat input[type=file]").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        opener = page.locator(CREDITS_OPENER)
        opener.click()
        panel = page.get_by_role("dialog", name="Mes crédits")
        expect(panel).to_be_visible()
        expect(panel.get_by_text("Crédits offerts")).to_be_visible()
        expect(panel.get_by_text("Ces 30 derniers jours")).to_be_visible()
        with page.expect_response("**/api/assets"):
            uploads.pop().continue_()
        page.go_back()
        expect(opener).to_be_focused()
        expect(field).to_have_value("Mon texte en cours")
        expect(page.locator(".chat .pic img").first).to_be_visible()
        expect(page.get_by_role("button", name="Envoyer")).to_be_enabled()
        page.go_forward()
        expect(panel).to_be_visible()
        page.keyboard.press("Escape")
        expect(opener).to_be_focused()
        assert sum(path.endswith("/api/assets") for path in requests) == 1
        assert not any(path.endswith(("/api/reads", "/scenes", "/refinements")) for path in requests)

        # A bookmarks-style entry renders the standalone screen, including signed balances and an accessible retry.
        balance = page.request.get(smoke.ORIGIN + "/api/balance").json()
        balance.update(available=-2, pending=1, purchase_fr="Appelez la boutique pour acheter des crédits.")
        page.route("**/api/balance", lambda route: route.fulfill(json=balance))
        opener.click()
        check_balance_explanation(page, panel, balance)
        panel.get_by_role("button", name="Fermer").click()
        expect(opener).to_be_focused()
        base = {"at": "2026-11-01T10:00:00Z", "creation_id": None, "title": None, "removed": None}
        line = dict(base, type="line", id=11, kind="grant", origin="bought", credits=3)
        old = dict(base, type="job", id="abandoned", kind="scene", credit="given_back", creation_id="abandoned", title="Annonce retirée", removed=True)
        pages = []
        def history(route):
            if "before=" in route.request.url:
                pages.append(route)
            else:
                route.fulfill(json={"items": [line], "next_cursor": "cursor"})
        page.route("**/api/shop-credit-history?*", history)
        page.goto("about:blank")
        page.route("**/api/balance", lambda route: route.abort(), times=1)
        page.goto(smoke.ORIGIN + "/#credits")
        view = page.get_by_role("region", name="Mes crédits")
        expect(view.get_by_role("button", name="Réessayer le solde")).to_be_visible()
        expect(view.locator("dd")).to_have_count(0)
        check_balance_explanation(page, view, balance)
        expect(view.locator("dd").first).to_have_text("-2 crédits")  # the figure with its unit
        expect(view.get_by_text(balance["purchase_fr"])).to_be_visible()
        expect(view.get_by_text("Achat de crédits")).to_be_visible()
        with page.expect_request("**/*before=cursor"):
            view.get_by_role("button", name="Voir plus").click()
        pages.pop().abort()
        expect(view.get_by_text("Achat de crédits")).to_be_visible()
        with page.expect_request("**/*before=cursor"):
            view.get_by_role("button", name="Réessayer la suite").click()
        pages.pop().fulfill(json={"items": [line, old], "next_cursor": None})
        expect(view.locator("li")).to_have_count(2)
        expect(view.get_by_text("Annonce retirée · Affiche retirée")).to_be_visible()
        expect(view.get_by_role("button", name="Annonce retirée")).to_have_count(0)
        for scheme in ("light", "dark"):
            set_theme(page, scheme)
            page.wait_for_function(smoke.NO_SIDEWAYS)
            smoke.check_contrast(page, "Crédits, " + scheme)
            page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            page.screenshot(path=str(out / f"credits-{scheme}.png"), full_page=True)
        late = []
        page.unroute("**/api/shop-credit-history?*")
        page.route("**/api/shop-credit-history?*", lambda route: late.append(route))
        page.route("**/api/shop-dashboard", lambda route: route.fulfill(status=409, json={"error": {"code": "shop_changed"}}))
        with page.expect_request("**/api/shop-credit-history?*"):
            view.get_by_role("button", name="Actualiser").click()
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        late.pop().fulfill(json={"items": [line], "next_cursor": None})
        expect(view).to_have_count(0)
        assert not errors, errors
    finally:
        context.close()


PHOTO = smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg"
INSIDE = "selector => document.querySelector(selector)?.contains(document.activeElement) ?? false"
# The frame (body::before) as drawn: its edges' distance to the window's, or null when there is none.
FRAME_JS = """() => { const frame = getComputedStyle(document.body, '::before'), body = document.body.getBoundingClientRect()
  if (frame.content === 'none' || frame.position !== 'absolute') return null
  return { left: body.left + parseFloat(frame.left), right: document.documentElement.clientWidth - body.right + parseFloat(frame.right) } }"""


def landmarks(page, role="navigation"):
    """The landmarks of Chromium's own accessibility tree, which leaves out what is inert or hidden, as a screen reader does."""
    cdp = page.context.new_cdp_session(page)
    try:
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
    finally:
        cdp.detach()
    return [node.get("name", {}).get("value") for node in nodes if not node.get("ignored") and node.get("role", {}).get("value") == role]


def to_review(page, message):
    """A poster made in the chat, its first version in the review panel."""
    page.goto(smoke.ORIGIN + "/#message")
    page.locator(".composer input[type=file]").set_input_files([PHOTO])
    expect(page.locator(".tray .pic")).to_have_count(1)
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    page.get_by_label("Votre message").fill(message)
    page.get_by_role("button", name="Envoyer").click()
    page.get_by_role("log").get_by_role("button", name="Créer l’affiche").click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    page.get_by_role("button", name="Vérifier", exact=True).click(timeout=30000)
    expect(page.get_by_role("heading", name=sb.REVIEW)).to_be_visible()
    return page.url.split("#message-")[1]


def never_reached(page, where, presses=40):
    """Tab and Shift+Tab never put the focus in the sidebar, nor give « Se déconnecter » to a key."""
    for key in ("Tab", "Shift+Tab"):
        for _ in range(presses):
            page.keyboard.press(key)
            assert not page.evaluate(INSIDE, "aside.side"), (where, key)
    expect(page.locator("aside.side")).to_have_attribute("inert", "")


def walk_shell(browser, out):
    """The shell over 1180 px, at its edges and around it (D-REDESIGN-002): the panels in front keep the sidebar out of reach;
    the top bar sticks after a document scroll and the frame scrolls away, a notice stays under the bar and a toast is
    centred on the content; the widths 1181/1180 and 721/720; the rail; the recent posters through the page's own
    departure questions; the credits from the pill and the rail's button; a cold « Mes affiches » reads the shell's two
    sections once."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.set_default_timeout(10000)
        open_atelier(page)
        sb.sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
        side, header = page.locator("aside.side"), page.locator(".app-header")
        # Under a panel in front (1440 px): the final panel, then the review panel.
        approved = sb.made_in_chat(page, PHOTO, "Casque Sony WH-CH720N noir, 289 000 Ar")
        expect(page.get_by_role("heading", name=sb.FINAL)).to_be_visible()
        never_reached(page, "the final panel")
        page.get_by_role("button", name="Fermer", exact=True).click()
        reviewed = to_review(page, "Écouteurs JBL Tune Flex blancs, 199 000 Ar")
        never_reached(page, "the review panel")
        page.locator(".review-panel").get_by_role("button", name="Fermer").click()
        expect(side).not_to_have_attribute("inert", "")

        # Sticky after a document scroll, on « Mes affiches » long enough to scroll: eight more drafts, made by the API.
        headers = {"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE)}
        source = page.request.get(f"{smoke.ORIGIN}/api/creations/{approved}").json()["document"]["input_id"]
        for number in range(8):
            made = page.request.post(smoke.ORIGIN + "/api/creations", headers={**headers, "Idempotency-Key": str(uuid4())}, data={
                "input_id": source, "offer": {"title": f"Défilement {number}", "price_ar": 1000}, "brand_selection": {"logo": False, "shop_name": False, "contact": False}})
            assert made.ok, made.text()
        page.set_viewport_size({"width": 1440, "height": 600})
        page.goto(smoke.ORIGIN + "/#affiches")
        expect(page.locator(".library-item").first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollHeight - innerHeight") >= 600, "not enough posters to scroll"
        assert header.bounding_box()["height"] == 64 and header.bounding_box()["y"] == 12, header.bounding_box()
        assert page.evaluate(FRAME_JS) == {"left": 12, "right": 12}, page.evaluate(FRAME_JS)
        sidebar = side.bounding_box()
        page.evaluate("window.scrollTo({ top: 600, behavior: 'instant' })")
        assert header.bounding_box()["y"] == 0 and header.bounding_box()["height"] == 64, header.bounding_box()
        assert side.bounding_box() == sidebar, (side.bounding_box(), sidebar)
        assert page.evaluate(FRAME_JS) == {"left": 12, "right": 12}, page.evaluate(FRAME_JS)
        # A notice under the bar at rest and after the scroll; a toast centred on the content, with the sidebar and the rail.
        main = page.locator("main:not(.gate)")
        def centred(where):
            toast, content = page.locator(".message.notice").bounding_box(), main.bounding_box()
            assert abs(toast["x"] + toast["width"] / 2 - content["x"] - content["width"] / 2) <= 1, (where, toast, content)
        # A removed poster opened by its address says so in a notice (App.vue openCreation); the list of removed posters
        # is short, so a spacer, added by the test, lets the page scroll.
        abandoned = page.request.get(f"{smoke.ORIGIN}/api/creations/{reviewed}").json()
        removed = page.request.post(f"{smoke.ORIGIN}/api/creations/{reviewed}/abandon", data={}, headers={
            "Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE), "If-Match": f'"{abandoned["revision"]}"', "Idempotency-Key": str(uuid4())})
        assert removed.ok, removed.text()
        page.goto(f"{smoke.ORIGIN}/#{reviewed}")
        notice = page.locator(".message.notice")
        expect(notice).to_contain_text("Cette affiche a été retirée de la liste.")
        page.evaluate("document.querySelector('main:not(.gate)').insertAdjacentHTML('beforeend', '<div class=\"test-spacer\" style=\"height: 2000px\"></div>')")
        for top in (0, 600):
            page.evaluate("top => window.scrollTo({ top, behavior: 'instant' })", top)
            assert page.evaluate("scrollY") == top
            bar = header.bounding_box()
            assert notice.bounding_box()["y"] >= bar["y"] + bar["height"], (top, notice.bounding_box(), bar)
            centred(f"sidebar, scroll {top}")
        page.get_by_role("button", name="Réduire le menu").click()
        expect(side).to_have_js_property("offsetWidth", 76)
        centred("rail")
        page.get_by_role("button", name="Agrandir le menu").click()
        expect(side).to_have_js_property("offsetWidth", 288)
        # 1024 px: no frame, the bar still sticks.
        page.set_viewport_size({"width": 1024, "height": 600})
        page.evaluate("window.scrollTo({ top: 600, behavior: 'instant' })")
        assert page.evaluate(FRAME_JS) is None and header.bounding_box()["y"] == 0, (page.evaluate(FRAME_JS), header.bounding_box())
        # The editor at 1440 px: the rail, and the sticky offset equal to the bar once stuck.
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{smoke.ORIGIN}/#{approved}")
        expect(page.locator(".poster-canvas canvas").first).to_be_visible()
        if page.get_by_role("heading", name=sb.FINAL).count():
            page.get_by_role("button", name="Fermer", exact=True).click()
        # A work surface: no frame's gap (the 12 px go to the poster); the sidebar column from the window's left edge, and
        # the poster's name only in the editor's own title row.
        assert header.bounding_box()["y"] == 0 and side.bounding_box()["x"] == 0, (header.bounding_box(), side.bounding_box())
        assert page.evaluate(FRAME_JS) == {"left": 0, "right": 0}, page.evaluate(FRAME_JS)
        expect(header.locator(".top-title")).to_have_count(0)
        page.evaluate("document.querySelector('main:not(.gate)').insertAdjacentHTML('beforeend', '<div class=\"test-spacer\" style=\"height: 2000px\"></div>')")
        page.evaluate("window.scrollTo({ top: 400, behavior: 'instant' })")
        page.wait_for_function("() => document.querySelector('.app-header').getBoundingClientRect().top === 0")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--sticky-top')") == f"{header.evaluate('e => e.offsetHeight')}px"

        # The widths. 1181: the sidebar; the editor before and after a version with the rail and its three columns; the chat
        # with its poster beside a thread of 460 px or more. 1180: the menu button, and no sidebar for a screen reader.
        draft = page.request.get(smoke.ORIGIN + "/api/creations?limit=50&status=active").json()["items"]
        draft = next(item["id"] for item in draft if item["state"] == "draft")
        page.set_viewport_size({"width": 1181, "height": 800})
        for poster in (draft, approved):
            page.goto(f"{smoke.ORIGIN}/#{poster}")
            expect(page.get_by_label("Titre", exact=True)).to_be_visible()
            expect(side).to_have_js_property("offsetWidth", 76)
            expect(page.get_by_role("button", name=re.compile("(Réduire|Agrandir) le menu"))).to_have_count(0)
            columns = page.locator(".work").evaluate("e => getComputedStyle(e).gridTemplateColumns").split()
            assert len(columns) == 3 and columns[0] == "360px" and columns[2] == "156px", columns
            page.wait_for_function(smoke.NO_SIDEWAYS)
        page.goto(f"{smoke.ORIGIN}/#message-{approved}")
        expect(page.locator(".chat-side")).to_be_visible()
        if page.get_by_role("heading", name=sb.FINAL).count():
            page.get_by_role("button", name="Fermer", exact=True).click()
        assert page.get_by_role("log").bounding_box()["width"] >= 460, page.get_by_role("log").bounding_box()
        page.wait_for_function(smoke.NO_SIDEWAYS)
        expect(side).to_have_js_property("offsetWidth", 288)
        expect(header.locator(".menu")).to_be_hidden()
        page.set_viewport_size({"width": 1180, "height": 800})
        expect(header.get_by_role("button", name="Ouvrir le menu")).to_be_visible()
        page.wait_for_timeout(400)  # the sidebar becomes the closed drawer: its slide out
        assert landmarks(page) == [], landmarks(page)
        assert page.evaluate("getComputedStyle(document.querySelector('aside.side')).visibility") == "hidden"
        page.goto(smoke.ORIGIN + "/#accueil")
        for width, bar in ((721, False), (720, True)):
            page.set_viewport_size({"width": width, "height": 800})
            expect(page.locator("nav.phone-bar")).to_be_visible() if bar else expect(page.locator("nav.phone-bar")).to_be_hidden()

        # The rail: one button, every name kept, kept after a reload, forced in the editor, and for the page alone when
        # the storage refuses.
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(smoke.ORIGIN + "/#accueil")
        expect(side.locator(".recent")).to_be_visible()
        page.get_by_role("button", name="Réduire le menu").click()
        expect(side).to_have_js_property("offsetWidth", 76)
        expect(side.locator(".recent")).to_be_hidden()
        # Every control left on the rail, in order, by its full accessible name; each link keeps a title as its tooltip.
        rail = side.locator("a:visible, button:visible")
        expected = [("link", re.compile("^Doka Studio — Accueil$")), ("link", re.compile("^Nouvelle affiche$")), ("link", re.compile("^Accueil$")),
                    ("link", re.compile("^Mes affiches \\d+$")), ("link", re.compile("^Styles( \\d+)?$")), ("link", re.compile("^(-?\\d+ crédits?|Mes crédits)$")),
                    ("link", re.compile("^" + re.escape(side.locator("a.account").get_attribute("title").strip()) + "$")), ("button", re.compile("^Se déconnecter$"))]
        expect(rail).to_have_count(len(expected))
        for control, (role, name) in zip(rail.all(), expected):
            assert control.evaluate("e => e.tagName") == ("A" if role == "link" else "BUTTON")
            expect(control).to_have_accessible_name(name)
            assert control.get_attribute("title"), control.evaluate("e => e.outerHTML.slice(0, 120)")
            expect(side.get_by_role(role, name=name)).to_have_count(1)
        page.reload()
        expect(side).to_have_js_property("offsetWidth", 76)
        assert page.evaluate("localStorage.getItem('affiche.rail')") == "1"
        page.get_by_role("button", name="Agrandir le menu").click()
        expect(side).to_have_js_property("offsetWidth", 288)
        assert page.evaluate("localStorage.getItem('affiche.rail')") is None
        page.goto(f"{smoke.ORIGIN}/#{draft}")
        expect(side).to_have_js_property("offsetWidth", 76)
        expect(page.get_by_role("button", name=re.compile("(Réduire|Agrandir) le menu"))).to_have_count(0)
        refusing = context.new_page()
        refusing.add_init_script("for (const name of ['getItem', 'setItem', 'removeItem']) Storage.prototype[name] = () => { throw new DOMException('denied', 'SecurityError') }")
        refusing.goto(smoke.ORIGIN + "/#accueil")
        expect(refusing.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        refusing.get_by_role("button", name="Réduire le menu").click()
        expect(refusing.locator("aside.side")).to_have_js_property("offsetWidth", 76)
        refusing.get_by_role("button", name="Agrandir le menu").click()
        expect(refusing.locator("aside.side")).to_have_js_property("offsetWidth", 288)
        refusing.close()

        # Recent posters go through the page's own questions: photos not sent in the chat, unsaved edits of the account.
        # Both start views: a row is #message-<id> with the chat preferred, #<id> with « Pas à pas »; either way another
        # poster is a departure. « Annuler » keeps the address and the photos; leaving discards them before the other opens.
        other = side.locator(".recent a:not([aria-current])").first
        leave = page.get_by_role("dialog", name="Quitter le message ?")
        for start, form in (("chat", r"#message-[0-9a-f-]{36}"), ("steps", r"#[0-9a-f-]{36}")):
            page.goto(smoke.ORIGIN + "/#accueil")
            page.evaluate("start => localStorage.setItem('affiche.start', start)", start)
            page.reload()
            expect(other).to_be_visible()
            target = other.get_attribute("href")
            assert re.fullmatch(form, target), (start, target)
            page.goto(smoke.ORIGIN + "/#message")
            page.locator(".composer input[type=file]").set_input_files([PHOTO])
            expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
            other.click()
            expect(leave).to_be_visible()
            leave.get_by_role("button", name="Annuler").click()
            expect(leave).to_have_count(0)
            assert page.url.endswith("#message"), (start, page.url)
            expect(page.locator(".tray .pic")).to_have_count(1)
            other.click()
            leave.get_by_role("button", name="Quitter sans les envoyer").click()
            page.wait_for_url("**/" + target)
            expect(page.get_by_label("Votre message") if start == "chat" else page.get_by_label("Titre", exact=True)).to_be_visible()
            expect(page.locator(".tray .pic")).to_have_count(0)
        page.goto(smoke.ORIGIN + "/#compte")
        name = page.get_by_role("region", name="Mon compte", exact=True).get_by_label("Nom de la boutique")
        expect(name).to_be_visible()
        kept = name.input_value()
        name.fill("Saisie non enregistrée")
        other.click()
        expect(page.locator("[aria-labelledby=titre-quitter-profil]")).to_be_visible()
        expect(page.get_by_role("button", name="Continuer la modification")).to_be_focused()
        page.get_by_role("button", name="Continuer la modification").click()
        assert page.url.endswith("#compte"), page.url
        expect(name).to_have_value("Saisie non enregistrée")
        name.fill(kept)

        # The credits from the creator: the pill (the chat with a draft kept), the editor rail's button; the panel over
        # the work, and closing gives the focus back to the opener.
        panel = page.get_by_role("dialog", name="Mes crédits")
        for opener, address in ((header.locator(".credits-pill"), "#message"), (page.locator(".rail .creator-credits"), f"#{draft}")):
            page.goto(smoke.ORIGIN + "/" + address)
            work = page.get_by_label("Votre message") if address == "#message" else page.get_by_label("Titre", exact=True)
            expect(work).to_be_visible()
            if address == "#message":
                work.fill("Brouillon à garder")
            before = work.input_value()
            opener.click()
            expect(panel).to_be_visible()
            panel.get_by_role("button", name="Fermer").click()
            expect(panel).to_have_count(0)
            expect(opener).to_be_focused()
            assert page.url.endswith(address), page.url
            expect(work).to_have_value(before)

        # The sidebar after a poster is made: the count and the rows of the server, not of « Mes affiches » read before; a
        # failed recent read after a success leaves the section and its count out.
        page.goto(smoke.ORIGIN + "/#affiches")
        expect(page.locator(".library-item").first).to_be_visible()
        listed = page.request.get(smoke.ORIGIN + "/api/creations?limit=1").json()["total"]
        mine = side.get_by_role("link", name=re.compile("^Mes affiches"))
        expect(mine).to_have_accessible_name(f"Mes affiches {listed}")
        page.goto(smoke.ORIGIN + "/#etapes")
        page.get_by_label("Photos du produit").set_input_files(PHOTO)
        expect(page.locator(".photo-strip img")).to_have_count(1)
        page.get_by_label("Nom du produit", exact=True).fill("Compte à jour")
        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
        page.get_by_label("Les photos correspondent").check()
        page.get_by_role("button", name="Préparer mon affiche").click()
        expect(page.get_by_label("Titre", exact=True)).to_have_value("Compte à jour")
        expect(mine).to_have_accessible_name(f"Mes affiches {listed + 1}")
        expect(side.locator(".recent a").first).to_contain_text("Compte à jour")
        smoke.go(page, "Accueil")
        page.route("**/api/creations?limit=5", lambda route: route.abort())
        page.get_by_role("region", name="Accueil", exact=True).get_by_role("button", name="Actualiser").click()
        expect(page.get_by_role("region", name="Accueil", exact=True).get_by_role("button", name="Réessayer les affiches")).to_be_visible()
        expect(side.locator(".recent")).to_have_count(0)
        expect(mine).to_have_accessible_name("Mes affiches")
        page.unroute("**/api/creations?limit=5")
        page.get_by_role("region", name="Accueil", exact=True).get_by_role("button", name="Réessayer les affiches").click()
        expect(side.locator(".recent a").first).to_contain_text("Compte à jour")
        # A removal whose list read then fails: the count is the recent read's, never the list's old one (review r2, D).
        page.goto(smoke.ORIGIN + "/#affiches")
        expect(page.locator(".library-item").first).to_be_visible()
        listed = page.request.get(smoke.ORIGIN + "/api/creations?limit=1").json()["total"]
        expect(mine).to_have_accessible_name(f"Mes affiches {listed}")
        page.route("**/api/creations?limit=50&status=active", lambda route: route.abort())
        page.locator(".library-row", has_text="Défilement 0").get_by_role("button", name=re.compile("^Retirer")).click()
        page.get_by_role("dialog").get_by_role("button", name="Retirer de la liste").click()
        expect(page.locator(".message.error")).to_be_visible()
        expect(mine).to_have_accessible_name(f"Mes affiches {listed - 1}")
        page.unroute("**/api/creations?limit=50&status=active")

        # Back and Forward with photos not sent (review r2, B), the chat preferred: A (Accueil) → B → C, two posters'
        # conversations. Back from C asks; « Annuler » returns to C with the history as it was; « Quitter sans les
        # envoyer » lands on B without the photos, and Forward still reaches C. From C a new conversation asks too.
        page.evaluate("localStorage.setItem('affiche.start', 'chat')")
        page.goto(smoke.ORIGIN + "/#accueil")
        page.reload()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        ids = {item["title"]: item["id"] for item in page.request.get(smoke.ORIGIN + "/api/creations?limit=50&status=active").json()["items"]}
        b, c = f"#message-{ids['Défilement 5']}", f"#message-{ids['Défilement 6']}"
        page.goto(smoke.ORIGIN + "/" + b)
        expect(page.get_by_label("Votre message")).to_be_visible()
        page.goto(smoke.ORIGIN + "/" + c)
        expect(page.get_by_role("heading", name="Défilement 6", level=1)).to_be_attached()
        tray = page.locator(".tray .pic")
        page.locator(".composer input[type=file]").set_input_files([PHOTO])
        expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
        length = page.evaluate("history.length")
        page.go_back()
        expect(leave).to_be_visible()
        leave.get_by_role("button", name="Annuler").click()
        page.wait_for_url("**/" + c)
        expect(tray).to_have_count(1)
        assert page.evaluate("history.length") == length
        page.go_back()
        expect(leave).to_be_visible()
        leave.get_by_role("button", name="Quitter sans les envoyer").click()
        page.wait_for_url("**/" + b)
        expect(page.get_by_role("heading", name="Défilement 5", level=1)).to_be_attached()
        expect(tray).to_have_count(0)
        page.go_forward()
        page.wait_for_url("**/" + c)
        expect(page.get_by_role("heading", name="Défilement 6", level=1)).to_be_attached()
        page.locator(".composer input[type=file]").set_input_files([PHOTO])
        expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
        # Back, then Forward while the question is open: it closes with the entry it was about; the next Back asks again
        # and nothing was discarded meanwhile (review r3, 1).
        page.go_back()
        expect(leave).to_be_visible()
        page.go_forward()
        page.wait_for_url("**/" + c)
        expect(leave).to_have_count(0)
        expect(tray).to_have_count(1)
        page.go_back()
        expect(leave).to_be_visible()
        leave.get_by_role("button", name="Annuler").click()
        page.wait_for_url("**/" + c)
        expect(tray).to_have_count(1)
        side.get_by_role("link", name="Nouvelle affiche").click()
        expect(leave).to_be_visible()
        leave.get_by_role("button", name="Annuler").click()
        page.wait_for_url("**/" + c)
        expect(tray).to_have_count(1)
        side.get_by_role("link", name="Nouvelle affiche").click()
        leave.get_by_role("button", name="Quitter sans les envoyer").click()
        page.wait_for_url("**/#message")
        expect(tray).to_have_count(0)
        # A recent row's message address on a shop without the chat: the editor opens under the poster's own address,
        # replaced, and one Back returns to Accueil (review r2, C).
        plain = context.new_page()
        plain.route("**/api/capabilities", lambda route: route.fulfill(json={**route.fetch().json(), "chat_available": False}))
        plain.goto(smoke.ORIGIN + "/#accueil")
        row = plain.locator("aside.side .recent a").first
        expect(row).to_be_visible()
        target = row.get_attribute("href")
        assert target.startswith("#message-"), target
        length = plain.evaluate("history.length")
        row.click()
        plain.wait_for_url("**/#" + target.removeprefix("#message-"))
        expect(plain.get_by_label("Titre", exact=True)).to_be_visible()
        assert plain.evaluate("history.length") == length + 1, (plain.evaluate("history.length"), length)
        plain.go_back()
        plain.wait_for_url("**/#accueil")
        expect(plain.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        plain.close()

        # A cold « Mes affiches »: one read of the five recent posters and one of the balance.
        cold = context.new_page()
        reads = []
        cold.on("request", lambda request: reads.append(request.url.partition("/api/")[2]) if "/api/" in request.url else None)
        cold.goto(smoke.ORIGIN + "/#affiches")
        expect(cold.locator(".library-item").first).to_be_visible()
        expect(cold.locator("aside.side .recent a").first).to_be_visible()
        expect(cold.locator(".app-header .credits-pill")).not_to_have_text("Crédits")
        cold.wait_for_timeout(500)
        assert [reads.count(path) for path in ("creations?limit=5", "balance")] == [1, 1], reads
        cold.close()
        page.screenshot(path=str(out / "shell-1440.png"))
        assert not errors, errors
        return approved, draft, reviewed
    finally:
        context.close()


def walk_drawer(browser, approved, draft, removed):
    """The drawer at 1024 and 360 px (D-REDESIGN-002): Tab stays inside, Escape, the scrim and its close button give the
    focus back to the menu button, a destination gives it to its title, Back closes it first, closed it is inert at once,
    a destination with unsaved account edits raises the account's question with the drawer closed, a wider window
    closes it and the focus goes to the rail's button; one navigation landmark when open, none when closed at 1024 px.
    The phone bar is inert under the drawer and under a dialog, absent in the chat and the editor; the credit card in the
    drawer opens the panel over the chat and gives the focus back to the menu button; the poster already open closes the
    drawer and changes nothing; the editor's full-screen look keeps the sidebar out of reach."""
    context = browser.new_context(viewport={"width": 1024, "height": 768}, color_scheme="dark")
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.set_default_timeout(10000)
        open_atelier(page)
        sb.sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
        side, menu = page.locator("aside.side"), page.get_by_role("button", name="Ouvrir le menu")
        bar = page.locator("nav.phone-bar")
        for width in (1024, 360):
            page.set_viewport_size({"width": width, "height": 768})
            page.goto(smoke.ORIGIN + "/#accueil")
            expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
            page.wait_for_timeout(400)
            assert landmarks(page) == ([] if width == 1024 else ["Navigation"]), (width, landmarks(page))
            smoke.open_drawer(page)
            expect(menu).to_have_attribute("aria-expanded", "true")
            assert landmarks(page) == ["Navigation"], (width, landmarks(page))
            if width == 360:
                expect(bar).to_have_attribute("inert", "")
            controls = side.locator("a:visible, button:visible").count()
            for key in ("Tab", "Shift+Tab"):
                for _ in range(controls + 2):
                    page.keyboard.press(key)
                    assert page.evaluate(INSIDE, "aside.side"), (width, key)
            for way in ("Escape", "scrim", "close"):
                if way != "Escape":
                    smoke.open_drawer(page)
                if way == "Escape":
                    page.keyboard.press("Escape")
                elif way == "scrim":
                    page.mouse.click(page.viewport_size["width"] - 10, 400)
                else:
                    page.get_by_role("button", name="Fermer le menu").click()
                expect(side).to_have_attribute("inert", "")  # at once, before its slide ends
                expect(menu).to_be_focused()
                expect(menu).to_have_attribute("aria-expanded", "false")
            # Closed, it is out of the keyboard's way at once.
            smoke.open_drawer(page)
            page.keyboard.press("Escape")
            page.keyboard.press("Shift+Tab")
            assert not page.evaluate(INSIDE, "aside.side"), width
            expect(page.get_by_role("button", name="Aller au contenu")).to_be_focused()  # the one control before the menu
            page.keyboard.press("Tab")  # back on the menu button: the skip link, shown, covered it
            expect(menu).to_be_focused()
            # A destination: its title has the focus; Back with the drawer open closes it first.
            smoke.open_drawer(page)
            side.get_by_role("link", name=re.compile("^Styles")).click()
            expect(page.get_by_role("heading", name="Styles", level=1)).to_be_focused()
            expect(side).to_have_attribute("inert", "")
            smoke.open_drawer(page)
            page.go_back()
            expect(page.get_by_role("heading", name="Accueil", level=1)).to_be_focused()
            expect(side).to_have_attribute("inert", "")
            # Another recent poster, a draft with no dialog of its own: its title has the focus (the chat's, then the
            # editor's for a device that starts « Pas à pas »).
            for start, title in (("chat", page.locator("main:not([hidden]) h1.visually-hidden")), ("steps", page.locator("main:not([hidden]) h1.poster-title"))):
                page.evaluate("start => localStorage.setItem('affiche.start', start)", start)
                page.goto(smoke.ORIGIN + "/#accueil")
                page.reload()
                expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
                smoke.open_drawer(page)
                side.locator(".recent a", has_text="Défilement 6").click()
                expect(title).to_have_text("Défilement 6")
                expect(title).to_be_focused()
                expect(side).to_have_attribute("inert", "")
            page.evaluate("localStorage.removeItem('affiche.start')")
            page.goto(smoke.ORIGIN + "/#accueil")
            page.reload()
            # The account's question, the drawer closed.
            page.goto(smoke.ORIGIN + "/#compte")
            name = page.get_by_role("region", name="Mon compte", exact=True).get_by_label("Nom de la boutique")
            kept = name.input_value()
            name.fill("Saisie non enregistrée")
            smoke.open_drawer(page)
            side.get_by_role("link", name="Accueil", exact=True).click()
            expect(page.get_by_role("button", name="Continuer la modification")).to_be_focused()
            expect(side).to_have_attribute("inert", "")
            page.get_by_role("button", name="Continuer la modification").click()
            name.fill(kept)
            # The poster already open: the drawer closes, the address stays, the menu button has the focus.
            page.goto(f"{smoke.ORIGIN}/#{draft}")
            expect(page.get_by_label("Titre", exact=True)).to_be_visible()
            if width == 360:
                expect(bar).to_have_count(0)
                page.goto(f"{smoke.ORIGIN}/#message-{draft}")
                expect(page.get_by_label("Votre message")).to_be_visible()
                expect(bar).to_have_count(0)
            address = page.url
            smoke.open_drawer(page)
            side.locator(".recent a[aria-current=page]").click()
            expect(menu).to_be_focused()
            assert page.url == address, (page.url, address)
            # The credit card in the drawer, in the creator: the panel over the work; closed, the focus to the menu button.
            if not address.split("#")[1].startswith("message-"):
                page.goto(f"{smoke.ORIGIN}/#message-{draft}")
            page.get_by_label("Votre message").fill("Brouillon du tiroir")
            smoke.open_drawer(page)
            side.locator(".credit-card").click()
            panel = page.get_by_role("dialog", name="Mes crédits")
            expect(panel).to_be_visible()
            expect(side).to_have_attribute("inert", "")
            panel.get_by_role("button", name="Fermer").click()
            expect(menu).to_be_focused()
            expect(page.get_by_label("Votre message")).to_have_value("Brouillon du tiroir")
        # A dialog on a phone: the bar is inert under it.
        page.goto(smoke.ORIGIN + "/#styles")
        page.locator(".look-card").first.click()
        expect(page.get_by_role("dialog")).to_be_visible()
        expect(bar).to_have_attribute("inert", "")
        page.keyboard.press("Escape")
        expect(bar).not_to_have_attribute("inert", "")
        # The editor's full-screen look (1024 px): the top bar and the sidebar are out of reach under it.
        page.set_viewport_size({"width": 1024, "height": 768})
        page.goto(f"{smoke.ORIGIN}/#{approved}")
        expect(page.get_by_role("heading", name=sb.FINAL)).to_be_visible()  # its file to check opens with it
        page.get_by_role("button", name="Fermer", exact=True).click()
        page.get_by_role("button", name="Voir l’affiche").first.click()
        expect(page.get_by_role("button", name="Revenir aux réglages")).to_be_visible()
        expect(page.locator(".app-header")).to_have_attribute("inert", "")
        never_reached(page, "the full-screen look", presses=12)
        page.get_by_role("button", name="Revenir aux réglages").click()
        # A notice showing, then the drawer opened: the drawer and its scrim are painted over the notice (review r1, 6).
        page.goto(f"{smoke.ORIGIN}/#{removed}")
        notice = page.locator(".message.notice")
        expect(notice).to_contain_text("Cette affiche a été retirée de la liste.")
        smoke.open_drawer(page)
        box = notice.bounding_box()
        for x in (box["x"] + 4, box["x"] + box["width"] / 2):
            assert page.evaluate("([x, y]) => !!document.elementFromPoint(x, y)?.closest('.side, .scrim')", [x, box["y"] + box["height"] / 2]), (x, box)
        page.keyboard.press("Escape")
        # Wider than 1180 px with the focus on « Fermer le menu »: the drawer closes, the focus goes to the rail's button.
        page.goto(smoke.ORIGIN + "/#accueil")
        smoke.open_drawer(page)
        page.set_viewport_size({"width": 1300, "height": 768})
        expect(page.get_by_role("button", name="Réduire le menu")).to_be_focused()
        expect(side).not_to_have_class(re.compile(r"\bopen\b"))
        assert not errors, errors
    finally:
        context.close()


def walk_gate(browser, data):
    """The shell and the identity gate (D-REDESIGN-002), each case apart, with markers of each shop: (a) signed out, and a
    late answer after the sign-out: no sidebar, no bottom bar, nothing of the shop in the page's markup; (b) a verification
    in progress with an unsaved account edit: the shell absent, the gate closed, the edit back once the shop is confirmed;
    (c) shop A signs out and shop B signs in: nothing of A anywhere."""
    engine = smoke.make_engine(Path(data))
    password = uuid4().hex
    with smoke.write_tx(engine) as conn:
        smoke.accepted(conn, smoke.shops.create_shop(conn, "troisieme", "Boutique Beta Marqueur", smoke.PASSWORDS.hash(password)))
    context = browser.new_context(viewport={"width": 360, "height": 740}, color_scheme="light")
    try:
        page = context.new_page()
        page.set_default_timeout(10000)
        # Shop A's markers: its name and its balance as answered here, a poster title of its own.
        shop = {"current": "A"}
        def named(route):
            profile = route.fetch().json()
            if shop["current"] == "A":
                profile["name"] = "Boutique Alpha Marqueur"
            route.fulfill(json=profile)
        def funded(route):
            answer = route.fetch().json()
            route.fulfill(json={**answer, "available": 4321} if shop["current"] == "A" else answer)
        page.route("**/api/shop-profile", named)
        page.route("**/api/balance", funded)
        a_markers = ["Boutique Alpha Marqueur", "Défilement 7", "4321"]  # the latest poster (walk_shell)
        open_atelier(page)
        sb.sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
        page.goto(smoke.ORIGIN + "/#etapes")  # the creator reads the profile: the account row has the shop's name
        expect(page.locator("aside.side a.account")).to_have_attribute("title", "Boutique Alpha Marqueur")
        page.goto(smoke.ORIGIN + "/#accueil")
        expect(page.locator("aside.side .recent").get_by_text("Défilement 7")).to_have_count(1)
        expect(page.locator(".app-header .credits-pill")).to_have_text("4321")
        latest = next(item["id"] for item in page.request.get(smoke.ORIGIN + "/api/creations?limit=50&status=active").json()["items"] if item["title"] == "Défilement 7")
        # (b) A verification in progress, an account edit unsaved.
        page.goto(smoke.ORIGIN + "/#compte")
        name = page.get_by_role("region", name="Mon compte", exact=True).get_by_label("Nom de la boutique")
        expect(name).to_have_value("Boutique Alpha Marqueur")
        name.fill("Saisie gardée pendant la vérification")
        held = []
        page.route("**/api/session", lambda route: held.append(route) if route.request.method == "GET" else route.continue_())
        page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))")
        page.evaluate(smoke.VISIBILITY, True)
        page.evaluate(smoke.VISIBILITY, False)
        page.wait_for_function("() => !document.querySelector('aside.side')")
        expect(page.locator("nav.phone-bar")).to_have_count(0)
        assert page.evaluate(smoke.GATE_CLOSED, a_markers), "the shell or the shop shown while the shop is verified"
        while not held:
            page.wait_for_timeout(50)
        page.unroute("**/api/session")
        for route in held:
            route.continue_()
        expect(page.locator("aside.side")).to_have_count(1)
        expect(name).to_have_value("Saisie gardée pendant la vérification")
        name.fill("Boutique Alpha Marqueur")  # back as loaded: nothing left to save
        smoke.go(page, "Accueil")
        # (a) Signed out on this page (the session ended from another tab of the device), the shop's recent read answering
        # after it: its turn is over, nothing of the shop is in the page.
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        late = []
        page.route("**/api/creations?limit=5", lambda route: late.append((route, route.fetch())))
        with page.expect_request("**/api/creations?limit=5"):
            page.get_by_role("region", name="Accueil", exact=True).get_by_role("button", name="Actualiser").click()
        while not late:
            page.wait_for_timeout(50)
        ended = context.request.delete(smoke.ORIGIN + "/api/session", headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE)})
        assert ended.ok, ended.text()
        page.evaluate(smoke.VISIBILITY, True)
        page.evaluate(smoke.VISIBILITY, False)
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        for route, answer in late:
            route.fulfill(response=answer)
        page.wait_for_timeout(300)
        expect(page.locator("aside.side, nav.phone-bar")).to_have_count(0)
        assert not page.evaluate(smoke.HOLDS, a_markers), page.evaluate(smoke.HOLDS, a_markers)
        assert page.evaluate(smoke.GATE_CLOSED, a_markers)
        # (a) again, from a populated phone editor and from « Mes affiches »: the shop's screen leaves the page with the
        # session (review r1, 2), and the theme switch stays reachable in the top bar (review r1, 5).
        for address in (f"#{latest}", "#affiches"):
            sb.sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
            page.goto(smoke.ORIGIN + "/" + address)
            expect(page.get_by_label("Titre", exact=True) if address != "#affiches" else page.locator(".library-item").first).to_be_visible()
            assert page.evaluate(smoke.HOLDS, a_markers), "the markers are on the screen before the sign-out"
            ended = context.request.delete(smoke.ORIGIN + "/api/session", headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE)})
            assert ended.ok, ended.text()
            page.evaluate(smoke.VISIBILITY, True)
            page.evaluate(smoke.VISIBILITY, False)
            expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
            assert not page.evaluate(smoke.HOLDS, a_markers), (address, page.evaluate(smoke.HOLDS, a_markers))
            switch = page.locator(".app-header .theme-toggle")
            expect(switch).to_be_visible()
            before = page.evaluate("document.documentElement.dataset.theme")
            switch.click()
            assert page.evaluate("document.documentElement.dataset.theme") != before, address
        # (c) Shop B signs in on the same page: nothing of A anywhere.
        shop["current"] = "B"
        sb.sign_in(page, "troisieme", password)
        page.goto(smoke.ORIGIN + "/#etapes")
        expect(page.locator("aside.side a.account")).to_have_attribute("title", "Boutique Beta Marqueur")
        assert not page.evaluate(smoke.HOLDS, a_markers), page.evaluate(smoke.HOLDS, a_markers)
    finally:
        context.close()
        engine.dispose()


def walk_account(browser, out, data):
    context = browser.new_context(viewport={"width": 360, "height": 640}, color_scheme="light")
    other = browser.new_context()
    engine = smoke.make_engine(Path(data))
    headers = {"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE)}
    set_terms(engine, None)
    try:
        page = context.new_page()
        errors, accepted, passwords = [], [], []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("request", lambda r: accepted.append(r.url) if r.method == "POST" and r.url.endswith("/terms") else None)
        page.on("request", lambda r: passwords.append(r.url) if r.url.endswith("/session/password") else None)
        open_atelier(page, "#compte")
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        account = page.get_by_role("region", name="Mon compte", exact=True)
        name, contact = account.get_by_label("Nom de la boutique"), account.get_by_role("textbox", name="Contact de la boutique", exact=True)
        save = account.get_by_role("button", name="Enregistrer le profil")
        expect(name).to_be_visible()
        # Postponing is respected on Account entry. Another device accepts while this tab is away.
        page.get_by_role("button", name="Plus tard").click()
        expect(account.get_by_text("Conditions à accepter.")).to_be_visible()
        smoke.go(page, "Accueil")
        home_account(page)
        expect(account.get_by_text("Conditions à accepter.")).to_be_visible()
        expect(page.get_by_role("dialog")).to_have_count(0)
        # Back during the conditions keeps that dialog in charge of a dirty Account.
        before_terms = name.input_value()
        name.fill("Saisie pendant les conditions")
        account.get_by_role("button", name="Lire les conditions").click()
        conditions = page.get_by_role("dialog", name="Conditions d’utilisation")
        expect(conditions).to_be_visible()
        page.evaluate("() => new Promise(done => { addEventListener('hashchange', () => done(true), {once: true}); history.back() })")
        page.wait_for_function("location.hash === '#compte'")
        expect(page.get_by_role("dialog")).to_have_count(1)
        expect(conditions).to_be_visible()
        page.keyboard.press("Escape")
        expect(name).to_have_value("Saisie pendant les conditions")
        name.fill(before_terms)
        session = other.request.post(smoke.ORIGIN + "/api/session", headers=headers, data={"identifier": smoke.IDENTIFIER, "password": smoke.PASSWORD})
        assert session.ok
        version = other.request.get(smoke.ORIGIN + "/api/terms").json()["version"]
        assert other.request.post(smoke.ORIGIN + "/api/terms", headers=headers, data={"version": version}).ok
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
        page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
        expect(account.get_by_text("Conditions acceptées le", exact=False)).to_be_visible()
        # The first response is already unaccepted on the wire when a different device accepts.
        set_terms(engine, None)
        held_opening = []
        def hold_opening(route):
            if not held_opening:
                answer = route.fetch()
                assert answer.json()["accepted_at"] is None
                held_opening.append((route, answer))
            else:
                route.continue_()
        page.route("**/api/terms", hold_opening)
        with page.expect_request("**/api/terms"):
            page.reload()
        expect(name).to_be_visible()
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
        second_acceptance = other.request.post(smoke.ORIGIN + "/api/terms", headers=headers, data={"version": version})
        assert second_acceptance.ok
        at = second_acceptance.json()["accepted_at"]
        page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
        expect(account.locator("time")).to_have_attribute("datetime", at)
        old, snapshot = held_opening[0]
        with page.expect_response("**/api/terms"):
            old.fulfill(response=snapshot)
        expect(account.locator("time")).to_have_attribute("datetime", at)
        expect(page.get_by_role("dialog")).to_have_count(0)
        assert not accepted
        page.unroute("**/api/terms")
        account.get_by_text("Lire les conditions", exact=True).click()
        expect(account.get_by_text("Version du", exact=False)).to_be_visible()
        assert not accepted
        expect(account.get_by_role("link", name="Vos données")).to_have_attribute("href", "/donnees.html")
        expect(contact).to_have_accessible_description("Ces coordonnées peuvent apparaître sur vos affiches si vous choisissez de les inclure.")
        support = account.get_by_role("region", name="Assistance Doka Studio")
        expect(support.get_by_text(f"Contactez {smoke.SUPPORT}.", exact=True)).to_be_visible()
        def without_operator(route):
            response = route.fetch()
            session = response.json()
            session.pop("support_fr", None)
            route.fulfill(json=session)
        page.route("**/api/session", without_operator)
        page.evaluate(smoke.VISIBILITY, True)
        page.evaluate(smoke.VISIBILITY, False)
        expect(support.get_by_text("Contactez l’opérateur qui vous a remis votre identifiant.", exact=True)).to_be_visible()
        page.unroute("**/api/session")
        page.evaluate(smoke.VISIBILITY, True)
        page.evaluate(smoke.VISIBILITY, False)
        expect(support.get_by_text(f"Contactez {smoke.SUPPORT}.", exact=True)).to_be_visible()
        for scheme in ("light", "dark"):
            set_theme(page, scheme)
            page.wait_for_function(smoke.NO_SIDEWAYS)
            smoke.check_contrast(page, f"Compte 360, {scheme}")
            page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            page.screenshot(path=str(out / f"compte-{scheme}.png"), full_page=True)

        home_link = account.get_by_role("link", name="Retour à l’accueil")
        keep = page.get_by_role("button", name="Continuer la modification")
        discard = page.get_by_role("button", name="Abandonner", exact=True)
        original_name, original_contact = name.input_value(), contact.input_value()
        profile_writes = []
        page.on("request", lambda r: profile_writes.append(r) if r.method == "PUT" and r.url.endswith("/shop-profile") else None)

        contact.fill("Saisie à garder")
        home_link.click()
        expect(keep).to_be_focused()
        page.wait_for_url("**/#compte")
        page.keyboard.press("Escape")
        expect(contact).to_be_focused()
        expect(contact).to_have_value("Saisie à garder")
        # Reaching an older Account hash is still a different entry: keep must return to the editing one.
        position = page.evaluate("history.state.position")
        page.evaluate("history.back()")
        expect(keep).to_be_focused()
        page.evaluate("history.back()")
        page.wait_for_function("p => history.state.position === p - 2 && location.hash === '#compte'", arg=position)
        expect(keep).to_be_focused()
        keep.click()
        page.wait_for_function("p => history.state.position === p", arg=position)
        expect(contact).to_be_focused()
        expect(contact).to_have_value("Saisie à garder")
        account.get_by_role("button", name="Se déconnecter").click()
        sign_out = page.get_by_role("dialog", name="Se déconnecter ?")
        expect(sign_out).to_be_visible()
        page.evaluate("() => new Promise(done => { addEventListener('hashchange', () => done(true), {once: true}); history.back() })")
        page.wait_for_function("p => history.state.position === p", arg=position)
        expect(page.get_by_role("dialog")).to_have_count(1)
        cancel = sign_out.get_by_role("button", name="Annuler")
        expect(cancel).to_be_focused()
        page.keyboard.press("Tab")
        expect(sign_out.get_by_role("button", name="Se déconnecter quand même")).to_be_focused()
        page.keyboard.press("Shift+Tab")
        expect(cancel).to_be_focused()
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).to_have_count(0)
        expect(contact).to_have_value("Saisie à garder")
        # The browser's warning protects full-document navigation without copying the form to storage.
        warnings = []
        def stay(dialog):
            warnings.append(dialog.type)
            dialog.dismiss()
        page.once("dialog", stay)
        account.get_by_role("link", name="Vos données").click()
        assert warnings == ["beforeunload"]
        expect(contact).to_have_value("Saisie à garder")

        # Cancel Back, then Back again to the original Home entry. Forward returns to saved details.
        page.evaluate("history.back()")
        expect(keep).to_be_focused()
        keep.click()
        page.wait_for_url("**/#compte")
        expect(contact).to_be_focused()
        page.evaluate("history.back()")
        discard.click()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        page.evaluate("history.forward()")
        expect(contact).to_have_value(original_contact)
        # Visit Home through a normal link, go Back to Account, then cancel and repeat Forward.
        name.fill("Nom provisoire")
        name.fill(original_name)
        home_link.click()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        page.evaluate("history.back()")
        expect(contact).to_be_visible()
        name.fill("Nom abandonné")
        page.evaluate("history.forward()")
        keep.click()
        page.wait_for_url("**/#compte")
        expect(name).to_be_focused()
        page.evaluate("history.forward()")
        discard.click()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        home_account(page)
        expect(name).to_have_value(original_name)
        assert not profile_writes

        # A committed save with a lost answer is read back if the intended destination fails.
        page.route("**/api/capabilities", lambda route: route.abort())
        lost = []
        def lose_committed_profile(route):
            if route.request.method == "PUT":
                assert route.fetch().ok
                lost.append(route)
            else:
                route.continue_()
        page.route("**/api/shop-profile", lose_committed_profile)
        name.fill("Nom déjà enregistré")
        with page.expect_request("**/api/shop-profile"):
            save.click()
        smoke.go(page, "Styles")
        expect(keep).to_have_count(0)
        lost.pop().abort()
        expect(discard).to_be_visible()
        discard.click()
        expect(name).to_be_enabled()
        expect(name).to_have_value("Nom déjà enregistré")
        expect(save).to_be_disabled()
        expect(page.get_by_role("button", name="Réessayer l’enregistrement")).to_have_count(0)
        page.wait_for_url("**/#compte")
        page.unroute("**/api/shop-profile")
        page.unroute("**/api/capabilities")

        # Failed Styles left adjacent #compte entries. Back between them fires only popstate.
        recovered = page.evaluate("history.state.position")
        page.evaluate("history.back()")
        page.wait_for_function("p => location.hash === '#compte' && history.state.position === p - 1", arg=recovered)
        contact.fill("Saisie sur l’entrée précédente")
        page.evaluate("history.back()")
        expect(keep).to_be_focused()
        keep.click()
        page.wait_for_function("p => location.hash === '#compte' && history.state.position === p - 1", arg=recovered)
        expect(contact).to_have_value("Saisie sur l’entrée précédente")
        contact.fill(original_contact)

        # A clean departure can also fail. Start editing on the recovered entry before pressing Back.
        clean_position = page.evaluate("history.state.position")
        page.route("**/api/capabilities", lambda route: route.abort())
        with page.expect_request("**/api/capabilities"):
            smoke.go(page, "Styles")
        page.wait_for_function("p => location.hash === '#compte' && history.state.position === p + 1", arg=clean_position)
        contact.fill("Saisie après retour sur erreur")
        page.evaluate("history.back()")
        expect(keep).to_be_focused()
        keep.click()
        page.wait_for_function("p => location.hash === '#compte' && history.state.position === p + 1", arg=clean_position)
        expect(contact).to_be_focused()
        expect(contact).to_have_value("Saisie après retour sur erreur")
        contact.fill(original_contact)
        page.unroute("**/api/capabilities")

        # Another device updates contact while this owner is editing the name.
        url = smoke.ORIGIN + "/api/shop-profile"
        original = page.request.get(url).json()
        headers = {"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE)}
        name.fill("Mon nouveau nom")
        changed = page.request.put(url, headers={**headers, "If-Match": f'"{original["revision"]}"', "Idempotency-Key": str(uuid4())},
                                   data={"name": original["name"], "contact": "Contact modifié ailleurs", "logo_asset": original["logo_asset"]})
        assert changed.ok, changed.status
        save.click()
        reload_profile = account.get_by_role("button", name="Relire le profil enregistré")
        expect(reload_profile).to_be_visible()
        expect(name).to_have_value("Mon nouveau nom")
        reload_profile.click()
        expect(contact).to_have_value("Contact modifié ailleurs")
        expect(name).to_have_value("Mon nouveau nom")
        # The requested departure waits until the selected logo finishes uploading.
        uploads = []
        page.route("**/api/assets", lambda route: uploads.append(route))
        with page.expect_request("**/api/assets"):
            account.locator("input[type=file]").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        home_link.click()
        expect(keep).to_have_count(0)
        uploads.pop().continue_()
        expect(keep).to_be_focused()
        keep.click()
        page.unroute("**/api/assets")
        expect(account.get_by_alt_text("Logo de la boutique")).to_be_visible()
        # An unreadable 409 asks for identity verification and keeps the draft editable.
        page.route("**/api/shop-profile", lambda route: route.fulfill(status=409, body="broken"))
        save.click()
        expect(account.get_by_role("alert").filter(has_text="illisible")).to_be_visible()
        expect(name).to_be_enabled()
        expect(name).to_have_value("Mon nouveau nom")
        expect(account.get_by_role("button", name="Réessayer l’enregistrement")).to_have_count(0)
        home_link.click()
        keep.click()
        expect(name).to_have_value("Mon nouveau nom")
        page.unroute("**/api/shop-profile")
        # Commit the first save and lose only its answer. Explicit retry must replay the same payload and key.
        writes = []
        def lose_save(route):
            if route.request.method != "PUT":
                route.continue_()
                return
            writes.append((route.request.headers["idempotency-key"], route.request.post_data_json))
            if len(writes) == 1:
                assert route.fetch().ok
                route.abort()
            else:
                route.continue_()
        page.route("**/api/shop-profile", lose_save)
        save.click()
        expect(account.get_by_role("button", name="Réessayer l’enregistrement")).to_be_visible()
        home_link.click()
        keep.click()
        account.get_by_role("button", name="Réessayer l’enregistrement").click()
        expect(account.get_by_text("Profil enregistré.", exact=True)).to_be_visible()
        assert len(writes) == 2 and writes[0] == writes[1]
        actual = page.request.get(url).json()
        assert actual["name"] == "Mon nouveau nom" and actual["contact"] == "Contact modifié ailleurs" and actual["logo_asset"]
        assert actual["revision"] == original["revision"] + 2
        assert not accepted

        # Two edits to the same field need an explicit choice, including a removed logo versus its replacement.
        name.fill("Mon choix local")
        contact.fill("Mon numéro")
        account.get_by_role("button", name="Retirer le logo").click()
        new_logo = page.request.post(smoke.ORIGIN + "/api/assets", headers=headers,
            multipart={"role": "logo", "file": {"name": "logo.jpg", "mimeType": "image/jpeg", "buffer": (smoke.ROOT / "backend/fixtures/examples/phone-bleu.jpg").read_bytes()}})
        assert new_logo.ok, new_logo.status
        new_logo_id = new_logo.json()["asset"]
        assert new_logo_id != actual["logo_asset"]
        changed = page.request.put(url, headers={**headers, "If-Match": f'"{actual["revision"]}"', "Idempotency-Key": str(uuid4())},
                                   data={"name": "Nom de l’autre appareil", "contact": "Autre numéro", "logo_asset": new_logo_id})
        assert changed.ok
        page.unroute("**/api/shop-profile")
        save.click()
        reload_profile.click()
        expect(save).to_be_disabled()
        fields = (
            ("Nom de la boutique", "Mon choix local", "Nom de l’autre appareil", "Garder ma saisie"),
            ("Contact de la boutique", "Mon numéro", "Autre numéro", "Garder la version enregistrée"))
        for label, before, after, choice in fields:
            field = account.get_by_role("group", name=f"{label} modifié sur les deux appareils")
            expect(field.get_by_text(before, exact=True)).to_be_visible()
            expect(field.get_by_text(after, exact=True)).to_be_visible()
            field.get_by_role("button", name=choice).click()
            expect(save).to_be_disabled()
        logo_choice = account.get_by_role("group", name="Logo modifié sur les deux appareils")
        expect(logo_choice.get_by_text("Aucun logo")).to_be_visible()
        expect(logo_choice.get_by_alt_text("Logo enregistré")).to_have_attribute("src", f"/api/assets/{new_logo_id}")
        logo_choice.get_by_role("button", name="Garder la version enregistrée").click()
        expect(name).to_have_value("Mon choix local")
        expect(contact).to_have_value("Autre numéro")
        expect(account.get_by_alt_text("Logo de la boutique")).to_have_attribute("src", f"/api/assets/{new_logo_id}")
        save.click()
        expect(account.get_by_text("Profil enregistré.", exact=True)).to_be_visible()
        assert page.request.get(url).json()["name"] == "Mon choix local"
        # The last edit's control gone with the logo, a cancelled departure gives the focus back to « Ma boutique »: a section
        # title, it keeps its ring (D-POLISH-003). Leaving without the edit brings the saved logo back.
        account.get_by_role("button", name="Retirer le logo").click()
        home_link.click()
        expect(keep).to_be_focused()
        page.keyboard.press("Escape")
        profile_title = account.get_by_role("heading", name="Ma boutique", exact=True)
        expect(profile_title).to_be_focused()
        assert profile_title.evaluate("e => e.matches(':focus-visible') && getComputedStyle(e).outlineStyle !== 'none'")
        home_link.click()
        discard.click()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        home_account(page)
        expect(account.get_by_alt_text("Logo de la boutique")).to_have_attribute("src", f"/api/assets/{new_logo_id}")
        # The transparent file input on the French picker remains keyboard accessible.
        contact.focus()
        page.keyboard.press("Tab")
        expect(account.locator("input[type=file]")).to_be_focused()

        # Each known refusal is the server's own message. A lost password answer is never replayed.
        change = account.get_by_role("button", name="Modifier le mot de passe")
        current = account.get_by_label("Mot de passe actuel")
        replacement = account.get_by_label("Nouveau mot de passe")
        for status, code, text in ((403, "wrong_password", "Mot de passe actuel incorrect."),
                                   (422, "password_too_short", "Le nouveau mot de passe est trop court."),
                                   (429, "rate_limited", "Attendez avant de réessayer.")):
            page.route("**/api/session/password", lambda route: route.fulfill(status=status, json={"error": {"code": code, "message_fr": text}}))
            current.fill(smoke.PASSWORD)
            replacement.fill("remplacement-local")
            change.click()
            expect(account.get_by_role("alert").filter(has_text=text)).to_be_visible()
            expect(current).to_be_empty()
            page.unroute("**/api/session/password")
        page.route("**/api/session/password", lambda route: route.abort())
        current.fill(smoke.PASSWORD)
        replacement.fill("remplacement-local")
        change.click()
        expect(account.get_by_role("alert").filter(has_text="n’a pas pu être confirmée")).to_be_visible()
        expect(replacement).to_be_empty()
        assert len(passwords) == 4
        page.unroute("**/api/session/password")
        auth = other.request.post(smoke.ORIGIN + "/api/session", headers=headers, data={"identifier": smoke.IDENTIFIER, "password": smoke.PASSWORD})
        assert auth.ok
        current.fill(smoke.PASSWORD)
        replacement.fill("remplacement-local")
        change.click()
        expect(account.get_by_text("Mot de passe modifié.", exact=False)).to_be_visible()
        assert page.request.get(url).ok and other.request.get(url).status == 401
        # Leave the common fixture ready for any later visitor.
        current.fill("remplacement-local")
        replacement.fill(smoke.PASSWORD)
        change.click()
        expect(current).to_be_empty()
        assert len(passwords) == 6
        # A successful in-flight save completes the requested departure exactly once.
        page.unroute("**/api/shop-profile")
        pending_saves = []
        page.route("**/api/shop-profile", lambda route: pending_saves.append(route) if route.request.method == "PUT" else route.continue_())
        contact.fill("Contact de départ")
        with page.expect_request("**/api/shop-profile"):
            save.click()
        home_link.click()
        expect(account).to_be_visible()
        expect(keep).to_have_count(0)
        pending_saves.pop().continue_()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        page.unroute("**/api/shop-profile")
        home_account(page)
        expect(contact).to_have_value("Contact de départ")
        name.fill("Nom avant déconnexion")
        account.get_by_role("button", name="Se déconnecter").click()
        expect(page.get_by_role("dialog").get_by_text("Les modifications non enregistrées", exact=False)).to_be_visible()
        page.get_by_role("button", name="Se déconnecter quand même").click()
        expect(page.get_by_label("Identifiant de la boutique")).to_be_visible()
        expect(account).to_have_count(0)
        # One cookie switches to a distinct shop while an old tab still awaits shop A's profile.
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        held = []
        page.route("**/api/shop-profile", lambda route: held.append((route, route.fetch())))
        with page.expect_request("**/api/shop-profile"):
            home_account(page)
        page.wait_for_function("location.hash === '#compte'")
        dirty_tab = context.new_page()
        open_atelier(dirty_tab, "#compte")
        dirty_tab.get_by_label("Nom de la boutique").fill("Saisie privée")
        dirty_tab.get_by_label("Mot de passe actuel").fill("secret local")
        dirty_tab.get_by_role("link", name="Retour à l’accueil").click()
        expect(dirty_tab.get_by_role("button", name="Continuer la modification")).to_be_focused()
        new_secret = uuid4().hex
        hashed = smoke.PASSWORDS.hash(new_secret)
        with smoke.write_tx(engine) as conn:
            smoke.accepted(conn, smoke.shops.create_shop(conn, "Deuxieme", "Autre boutique", hashed))
        signed = context.request.post(smoke.ORIGIN + "/api/session", headers=headers, data={"identifier": "Deuxieme", "password": new_secret})
        assert signed.ok
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
        page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
        expect(page.get_by_label("Identifiant de la boutique")).to_be_visible()
        dirty_tab.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        expect(dirty_tab.get_by_label("Identifiant de la boutique")).to_be_visible()
        expect(dirty_tab.get_by_role("region", name="Mon compte", include_hidden=True)).to_have_count(0)
        expect(dirty_tab.get_by_role("dialog", include_hidden=True)).to_have_count(0)
        old, result = held.pop()
        old.fulfill(response=result)
        expect(account).to_have_count(0)
        expect(page.get_by_alt_text("Logo de la boutique")).to_have_count(0)
        assert "Mon choix local" not in page.locator("body").inner_text()
        assert "Autre boutique" not in page.locator("body").inner_text()
        assert not errors, errors
    finally:
        engine.dispose()
        other.close()
        context.close()


def walk_facebook(browser):
    """D-FB-PUBLISH-002 and 004 on the stand-in, whose dialog sends the owner straight back to /facebook.html with a code.
    The return page's address is clean before it sends anything, no request carries the code or the state, and nothing
    of the feature is kept in the browser. The card offers both Pages by name, connects the one chosen, keeps it after a
    reload and disconnects it; a return page loaded again, and a cancelled dialog, are said on the card."""
    context = browser.new_context(viewport={"width": 360, "height": 640})
    try:
        page = context.new_page()
        page.set_default_timeout(15000)
        errors, referrers = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: referrers.append(request.headers.get("referer") or ""))
        open_atelier(page, "#compte")
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        card = page.get_by_role("region", name="Page Facebook", exact=True)
        connect = card.get_by_role("button", name="Connecter ma Page Facebook")
        expect(connect).to_be_visible()
        for line in ("Facebook vous demandera quelles Pages autoriser.",
                     "Si Facebook refuse l’accès, votre Page doit d’abord être autorisée par Doka Studio : demandez-le à l’opérateur."):
            expect(card.get_by_text(line, exact=True)).to_be_visible()
        stored = lambda: page.evaluate("() => [{...localStorage}, {...sessionStorage}]")  # noqa: E731
        before, held = stored(), []
        # Facebook sends the owner back: the return page's request is held while its address and storage are read.
        page.route("**/api/facebook/code", lambda route: held.append(route))
        with page.expect_request("**/api/facebook/code") as sent:
            connect.click()
        body = sent.value.post_data_json
        assert set(body) == {"code", "state"} and body["code"] == STUB_CODE, body
        assert page.evaluate("location.href") == smoke.ORIGIN + "/facebook.html"
        assert stored() == before and not any(value in json.dumps(before) for value in body.values())
        held[0].continue_()
        page.wait_for_url(smoke.ORIGIN + "/#compte")
        page.unroute("**/api/facebook/code")
        assert page.evaluate("location.search") == ""  # the application loads without a code
        expect(card.get_by_role("radio")).to_have_count(2)
        choose = card.get_by_role("button", name="Connecter cette Page")
        expect(choose).to_be_disabled()  # two Pages: none is chosen for the owner
        card.get_by_role("radio", name="Page d’essai 2").check()
        choose.click()
        expect(card).to_contain_text("Page connectée : Page d’essai 2")
        expect(card.get_by_role("radio")).to_have_count(0)
        page.reload()
        expect(card).to_contain_text("Page connectée : Page d’essai 2")
        # The same return address loaded again: refused before any call, said once on the card, the Page kept.
        page.goto(smoke.ORIGIN + "/facebook.html?" + urlencode(body))
        page.wait_for_url(smoke.ORIGIN + "/#compte")
        expect(card.get_by_role("alert")).to_have_text("Recommencez la connexion.")
        expect(card).to_contain_text("Page connectée : Page d’essai 2")
        card.get_by_role("button", name="Déconnecter").click()
        expect(connect).to_be_visible()
        expect(card.get_by_role("alert")).to_have_count(0)
        page.reload()
        expect(connect).to_be_visible()

        # Facebook's dialog cancelled: the stand-in's address with Facebook's error in place of the code.
        def cancelled(route):
            answer = route.fetch()
            route.fulfill(response=answer, json={"url": answer.json()["url"].replace(f"code={STUB_CODE}", "error=access_denied")})

        page.route("**/api/facebook/connect", cancelled)
        with page.expect_request("**/api/facebook/code"):
            connect.click()
        expect(card.get_by_role("alert")).to_have_text("Connexion annulée.")
        expect(connect).to_be_visible()
        # The return page's request never arrives: no sentence is kept anywhere for the card, so the return page says it
        # itself, its address clean, with the way back.
        page.unroute("**/api/facebook/connect")
        page.route("**/api/facebook/code", lambda route: route.abort())
        connect.click()
        expect(page.get_by_text("La connexion à Facebook n’a pas pu être enregistrée.")).to_be_visible()
        assert page.evaluate("location.href") == smoke.ORIGIN + "/facebook.html"
        expect(page.get_by_text("Connexion à Facebook…")).to_be_hidden()
        page.get_by_role("link", name="Retourner à Mon compte").click()
        page.wait_for_url(smoke.ORIGIN + "/#compte")
        page.unroute("**/api/facebook/code")
        expect(connect).to_be_visible()
        # The return page's script cannot be loaded: its first lines, in the page itself, have already cleaned the
        # address, and the way back is shown.
        page.route(re.compile(r"/assets/facebook[^/]*\.js$|/src/facebook-return\.ts"), lambda route: route.abort())
        connect.click()
        expect(page.get_by_text("La connexion à Facebook n’a pas pu être enregistrée.")).to_be_visible()
        assert page.evaluate("location.href") == smoke.ORIGIN + "/facebook.html"
        page.unroute(re.compile(r"/assets/facebook[^/]*\.js$|/src/facebook-return\.ts"))
        page.get_by_role("link", name="Retourner à Mon compte").click()
        page.wait_for_url(smoke.ORIGIN + "/#compte")
        expect(connect).to_be_visible()
        kept = json.dumps(stored())
        assert "facebook" not in kept.lower() and not any(value in kept for value in body.values()), kept
        assert not any(value in referrer for referrer in referrers for value in body.values()), referrers
        assert not errors, errors
    finally:
        context.close()


def run():
    out = smoke.ROOT / "outputs" / "shop-dash"
    out.mkdir(exist_ok=True, parents=True)
    with (tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as facebook_data,
          (out / "home-preview.log").open("w") as log):
        server = smoke.serve(Path(data))
        try:
            vite = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1",
                                     "--port", str(smoke.WEB_PORT), "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    try:
                        walk_header(browser)
                        walk_frame(browser)
                        walk_credits(browser, out)
                        walk(browser, out)
                        approved, draft, removed = walk_shell(browser, out)
                        walk_drawer(browser, approved, draft, removed)
                        walk_gate(browser, data)
                        walk_account(browser, out, data)
                        # The Facebook card exists only with the feature on: a server of its own, on the stand-in.
                        smoke.stop(*server)
                        server = smoke.serve(Path(facebook_data), facebook_provider="stub")
                        walk_facebook(browser)
                    finally:
                        browser.close()
            finally:
                vite.terminate()
                vite.wait(timeout=10)
        finally:
            smoke.stop(*server)
    print("Shop dashboard browser checks passed.")


if __name__ == "__main__":
    run()
