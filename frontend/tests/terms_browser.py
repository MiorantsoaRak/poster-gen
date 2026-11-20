"""The conditions of use in real Chromium (T-TERMS-003, D-TERMS-004): the production build (vite preview, so build
first) and the API on temporary stub data, no real env file, zero spend. Run from backend:
uv run python ../frontend/tests/terms_browser.py (ports 8000 and 5173 must be free). Pictures: outputs/terms-browser/.
The pilot shop's acceptance is written in the database between steps, as migration 0017 leaves it (NULL) or as
POST /api/terms writes it; a new version of the text is the server's own constant, changed in this process."""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

import browser_smoke as smoke
from affiche.api import MESSAGES
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import terms

OUT = smoke.ROOT / "outputs" / "terms-browser"
LOST = "L’acceptation n’a pas pu être confirmée."
UNREAD = "Les conditions n’ont pas pu être chargées."
REQUIRED, OUTDATED = MESSAGES["terms_required"], MESSAGES["terms_outdated"]
REVIEW, FINAL = "Vérifier la fidélité du produit", "Dernière vérification avant le téléchargement"
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
STEPS_FIRST = smoke.STEPS_FIRST
FOCUS_IN = "selector => !!document.querySelector(selector)?.contains(document.activeElement)"
# Two frames: what an answer already received changes is rendered by then (Vue renders in the same task).
FRAMES = "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
PAID = ("/scenes", "/refinements", "/text-effects")
TERMS, SHEET = ".terms-sheet", ".confirm-sheet:not(.terms-sheet)"
# Every control of the dialog a finger can reach is at least 44 × 44 px.
SMALL = "() => [...document.querySelectorAll('.terms-sheet button')].map(e => e.getBoundingClientRect()).filter(b => b.width < 44 || b.height < 44).length"
# The sheet scrolls on its own: nothing in it may be wider than it (a long unbroken contact wraps).
SHEET_FITS = "() => [...document.querySelectorAll('.terms-sheet, .terms-sheet .confirm, .terms-sheet p')].every(e => e.scrollWidth <= e.clientWidth)"
LONG_CONTACT = "whatsapp:+261340000000" + "0" * 90  # one unbroken word, wider than a phone
CONTACT = [smoke.SUPPORT]  # the contact the server puts in the last paragraph now
NEW_PARAGRAPH = "Version d’essai : ce paragraphe remplace le premier."


def said(version):
    year, month, day = map(int, version.split("-"))
    return f"Version du {'1er' if day == 1 else day} {MONTHS[month - 1]} {year}"


def set_terms(engine, version):
    """The pilot shop's acceptance: None, nothing accepted (migration 0017); a version, accepted now."""
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET terms_version=?, terms_accepted_at=? WHERE id=1",
                             (version, utc_now() if version else None))


def stored(engine):
    with engine.connect() as conn:
        return conn.exec_driver_sql("SELECT terms_version FROM shop_profile WHERE id=1").scalar()


def open_atelier(page, path=""):
    for attempt in range(60):
        try:
            page.goto(smoke.ORIGIN + path, timeout=2000)
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(.25)


def sign_in(page):
    open_atelier(page, "/#etapes")
    page.get_by_label("Identifiant de la boutique", exact=True).fill(smoke.IDENTIFIER)
    page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
    page.get_by_role("button", name="Ouvrir l’atelier").click()


def watch(context, errors):
    """Every POST to the API that leaves the browser: (path after /api/, Idempotency-Key)."""
    posts = []
    context.on("request", lambda r: posts.append((r.url.split("/api/", 1)[1], r.headers.get("idempotency-key")))
               if r.method == "POST" and "/api/" in r.url else None)
    page = context.new_page()
    page.set_default_timeout(15000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda r: print(f"HTTP {r.status} {r.request.method} {r.url}", flush=True) if r.status >= 400 and "/api/" in r.url else None)
    return page, posts


def count(posts, suffix):
    return sum(1 for path, _ in posts if path.endswith(suffix))


def until(page, check, seconds=20):
    """Waits for a condition while Playwright dispatches its events (a held route arrives only then)."""
    for _ in range(seconds * 10):
        if check():
            return
        page.wait_for_timeout(100)
    raise AssertionError("condition not met in time")


def scene_done(page, creation):
    """The poster's scene jobs have all ended (the stub makes one in about a second)."""
    jobs = page.request.get(f"{smoke.ORIGIN}/api/creations/{creation}/jobs").json()["items"]
    return all(job["status"] not in ("queued", "running") for job in jobs if job["kind"] == "scene")


def shows_conditions(page, heading="Conditions d’utilisation", version=None):
    """The dialog in front, with the server's text as text, its version, « J’accepte » and « Plus tard » and no sign-out."""
    dialog = page.locator(TERMS)
    expect(dialog).to_be_visible()
    expect(page.get_by_role("dialog", name=heading)).to_be_visible()
    expect(dialog).to_contain_text(said(version or terms.VERSION))
    texts = dialog.locator("p").all_inner_texts()
    for paragraph in terms.PARAGRAPHS_FR:
        assert paragraph.replace("{contact}", CONTACT[0]) in texts, (paragraph, texts)
    assert dialog.get_by_role("button").all_inner_texts() == ["J’accepte", "Plus tard"], dialog.get_by_role("button").all_inner_texts()
    data = dialog.get_by_role("link", name="Vos données", exact=True)  # D-TERMS-007: in a new tab, the dialog stays
    expect(data).to_have_attribute("href", "/donnees.html")
    expect(data).to_have_attribute("target", "_blank")
    expect(dialog.get_by_role("button", name="Se déconnecter")).to_have_count(0)
    page.wait_for_function(FOCUS_IN, arg=TERMS)
    expect(page.locator(".app-header")).to_have_attribute("inert", "")
    return dialog


def later(page):
    page.locator(TERMS).get_by_role("button", name="Plus tard").click()
    expect(page.locator(TERMS)).to_have_count(0)


def open_first(page, creation, reload=False):
    """The first poster in the editor. Its confirmed final check opens with it (App.vue adopt): closed."""
    if reload:
        page.reload()
    else:
        page.evaluate("id => { location.hash = id }", creation)
    expect(page.locator(".final-preview")).to_be_visible()
    page.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(page.locator(".final-preview")).to_have_count(0)


def new_version_sheet(page):
    page.get_by_role("button", name=re.compile("^Nouvelle version")).click()
    return page.locator(SHEET)


def walk_journey(browser, engine, errors, product, model):
    """The journey once, at 1280 (the design's T-TERMS-003 row): the races and every way to the dialog."""
    context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="light", accept_downloads=True)
    context.add_init_script(STEPS_FIRST)
    page, posts = watch(context, errors)

    # Nothing accepted: the dialog at the opening after a sign-in, without a sign-out button; « Plus tard » stores nothing.
    set_terms(engine, None)
    sign_in(page)
    shows_conditions(page)
    page.screenshot(path=str(OUT / "opening-1280.png"))
    # Away from the tab and back: the shop is hidden until the session answers again, then the dialog is in front again
    # and takes the focus back (it was lost meanwhile).
    page.evaluate(smoke.VISIBILITY, True)
    expect(page.locator(TERMS)).to_be_hidden()
    page.evaluate("() => document.activeElement?.blur()")
    page.evaluate(smoke.VISIBILITY, False)
    shows_conditions(page)
    later(page)
    assert count(posts, "terms") == 0 and stored(engine) is None

    # A poster with a version still to check (accepted meanwhile, as another device would).
    set_terms(engine, terms.VERSION)
    expect(page.get_by_label("Photos du produit")).to_be_enabled()  # not while the page is busy loading
    page.get_by_label("Photos du produit").set_input_files(product)
    expect(page.locator(".photo-strip img")).to_have_count(1)
    page.get_by_label("Nom du produit", exact=True).fill("Casque Bose QC")
    page.get_by_label("Prix en ariary", exact=True).fill("1 150 000")
    page.get_by_label("Les photos correspondent").check()
    page.get_by_role("button", name="Préparer mon affiche").click()
    expect(page.get_by_role("heading", name="Casque Bose QC", exact=True)).to_be_visible()
    first = page.url.split("#")[1]
    for _ in range(2):
        page.get_by_role("button", name="Continuer", exact=True).click()
    page.get_by_role("button", name="Générer l’affiche", exact=True).click()
    page.get_by_role("button", name="Lancer la génération", exact=True).click()
    expect(page.get_by_role("heading", name=REVIEW)).to_be_visible(timeout=30000)
    page.locator(".review-panel").get_by_role("button", name="Fermer").click()

    # Not accepted again, on the session that lasts: the dialog at the opening. After « Plus tard », free work goes on:
    # an edit saved, the version approved, the final check confirmed, the file downloaded. No acceptance is sent.
    set_terms(engine, None)
    page.reload()
    shows_conditions(page)
    later(page)
    page.get_by_role("tab", name="Réglages", exact=True).click()
    with page.expect_response(lambda r: r.request.method == "PUT" and f"/api/creations/{first}" in r.url) as saved:
        page.get_by_label("Zoom", exact=True).press("ArrowRight")
    assert saved.value.ok, saved.value.text()
    expect(page.get_by_text("Enregistré", exact=True)).to_be_visible()
    page.get_by_role("button", name="Vérifier la fidélité", exact=True).click()
    page.get_by_role("button", name="Tout est conforme, approuver").click()
    expect(page.get_by_role("heading", name=REVIEW)).to_have_count(0)
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Tout est conforme, confirmer").click()
    with page.expect_download() as download:
        page.get_by_role("link", name="Télécharger le PNG confirmé").click()
    assert Path(download.value.path()).stat().st_size > 1000
    page.locator(".final-preview").get_by_role("button", name="Fermer").click()
    expect(page.locator(TERMS)).to_have_count(0)
    assert count(posts, "terms") == 0 and stored(engine) is None

    # A fresh chat card (the form's product, no read paid): « Lire les conditions » in place of « Créer l’affiche »,
    # and no /scenes request leaves. The button opens the dialog; « Plus tard » gives the focus back to it.
    made = count(posts, "/scenes")  # the first poster's
    page.get_by_role("navigation", name="Navigation").get_by_role("link", name="Créer").click()
    expect(page.get_by_label("Photos du produit")).to_be_enabled()  # not while the page is busy loading
    page.get_by_label("Photos du produit").set_input_files(product)
    expect(page.locator(".photo-strip img")).to_have_count(1)
    page.get_by_label("Nom du produit", exact=True).fill("Sony WH-1000XM6")
    page.get_by_label("Prix en ariary", exact=True).fill("700 000")
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Message").click()
    log = page.get_by_role("log")
    card = log.locator(".bubble", has=page.locator(".recap"))
    expect(card.get_by_role("button", name="Lire les conditions")).to_be_visible()
    expect(card.get_by_role("button", name="Créer l’affiche")).to_have_count(0)
    expect(card).to_contain_text(REQUIRED)
    reader = card.get_by_role("button", name="Lire les conditions").element_handle()
    reader.click()
    shows_conditions(page)
    expect(page.locator(".chat")).to_have_attribute("inert", "")
    later(page)
    page.wait_for_function("button => document.activeElement === button", arg=reader)
    assert count(posts, "/scenes") == made

    # A chat message refused (403 terms_required): its text goes back to the field, and the dialog opens.
    message = "Casque Sony noir, 700 000 Ar"
    page.get_by_label("Votre message").fill(message)
    page.get_by_role("button", name="Envoyer").click()
    shows_conditions(page)
    later(page)
    expect(page.get_by_label("Votre message")).to_have_value(message)
    expect(log).to_contain_text(REQUIRED)
    assert count(posts, "reads") == 1

    # A free Claude button (a style from a model poster): 403, the dialog.
    open_first(page, first)
    page.get_by_role("tab", name="Style", exact=True).click()
    page.get_by_text("Créer un style depuis une affiche", exact=True).click()
    page.locator(".new-look input[type=file]").set_input_files(model)
    expect(page.get_by_alt_text("Affiche modèle pour le nouveau style")).to_be_visible()
    page.get_by_role("button", name="Enregistrer ce style").click()
    page.get_by_role("button", name="Créer le style", exact=True).click()
    shows_conditions(page)
    later(page)
    expect(page.locator(".message.error")).to_contain_text(REQUIRED)
    page.locator(".message.error").get_by_role("button", name="Fermer").click()
    assert count(posts, "/looks") == 1

    # The balance read late: the paid sheet opens on a balance that allowed it, then the answer says `terms`: « Lire les
    # conditions » beside « Fermer », in place of the paid button. It closes the sheet and opens the dialog.
    set_terms(engine, terms.VERSION)
    sheet = new_version_sheet(page)
    expect(sheet.get_by_role("button", name="Lancer la génération")).to_be_visible()
    sheet.get_by_role("button", name="Annuler").click()
    set_terms(engine, None)
    held = []
    page.route("**/api/balance", lambda route: held.append(route))
    origin = page.get_by_role("button", name=re.compile("^Nouvelle version")).element_handle()
    sheet = new_version_sheet(page)
    until(page, lambda: held)
    expect(sheet.get_by_role("button", name="Lancer la génération")).to_be_visible()
    held.pop().continue_()
    expect(sheet.get_by_role("button", name="Lire les conditions")).to_be_visible()
    expect(sheet.get_by_role("button", name="Lancer la génération")).to_have_count(0)
    expect(sheet.get_by_role("button", name="Fermer")).to_be_visible()
    expect(sheet).to_contain_text(REQUIRED)
    page.unroute("**/api/balance")
    sheet.get_by_role("button", name="Lire les conditions").click()
    expect(sheet).to_have_count(0)
    shows_conditions(page)
    later(page)
    page.wait_for_function("button => document.activeElement === button", arg=origin)  # the control itself, not the page

    # The text cannot be fetched: « Réessayer » beside « Plus tard ». Read again, the server's words are text only.
    page.route("**/api/terms", lambda route: route.fulfill(status=503, json={"error": {"code": "storage_unavailable", "message_fr": "Indisponible.", "retryable": True}}))
    new_version_sheet(page).get_by_role("button", name="Lire les conditions").click()
    dialog = page.locator(TERMS)
    expect(dialog).to_contain_text(UNREAD)
    assert dialog.get_by_role("button").all_inner_texts() == ["Réessayer", "Plus tard"]
    page.unroute("**/api/terms")

    def marked(route):
        response = route.fetch()
        body = response.json()
        body["paragraphs_fr"].append("<b>gras</b>")
        route.fulfill(response=response, json=body)
    page.route("**/api/terms", marked)
    dialog.get_by_role("button", name="Réessayer").click()
    expect(dialog.get_by_text("<b>gras</b>", exact=True)).to_be_visible()
    assert page.evaluate(FOCUS_IN, TERMS), "« Réessayer » replaced: the focus left the dialog"
    expect(dialog.locator("b")).to_have_count(0)
    page.unroute("**/api/terms")
    later(page)

    # Accepted from a fresh card it blocks: the same card, still in view, offers « Créer l’affiche » with nothing else
    # done (the acceptance itself reads the credits again).
    with page.expect_response("**/api/balance"):  # leaving the poster reads the credits again (fresh, loadShop)
        page.evaluate("() => { location.hash = 'message' }")
    card = page.get_by_role("log").locator(".bubble", has=page.locator(".recap"))
    expect(card.get_by_role("button", name="Lire les conditions")).to_be_visible()
    bubble = card.element_handle()
    card.get_by_role("button", name="Lire les conditions").click()
    shows_conditions(page)
    page.locator(TERMS).get_by_role("button", name="J’accepte").click()
    expect(page.locator(TERMS)).to_have_count(0)
    expect(card.get_by_role("button", name="Créer l’affiche")).to_be_visible()
    assert bubble.evaluate("b => b.isConnected && [...b.querySelectorAll('button')].map(x => x.textContent).join() === 'Créer l’affiche'")
    # A `terms` balance held, then released, while that fresh card is in view (read on the way back to the tab): the
    # card's paid button gives way to « Lire les conditions ».
    set_terms(engine, None)
    held = []
    page.route("**/api/balance", lambda route: held.append(route))
    page.evaluate(smoke.VISIBILITY, True)
    page.evaluate(smoke.VISIBILITY, False)
    until(page, lambda: held)
    expect(card.get_by_role("button", name="Créer l’affiche")).to_be_visible()
    held.pop().continue_()
    expect(card.get_by_role("button", name="Lire les conditions")).to_be_visible()
    expect(card.get_by_role("button", name="Créer l’affiche")).to_have_count(0)
    page.unroute("**/api/balance")
    # A request the server admitted, its 202 lost, then an older version stored: « Reprendre » sends the same key, the
    # server answers what it stored, the job is followed; no dialog. On the way, a stale balance: « Lire les conditions »
    # finds the shop accepted, shows nothing and reads the credits again, and the card offers its tap.
    set_terms(engine, terms.VERSION)
    card.get_by_role("button", name="Lire les conditions").click()
    expect(card.get_by_role("button", name="Créer l’affiche")).to_be_visible()
    expect(page.locator(TERMS)).to_have_count(0)
    page.route("**/scenes", lambda route: (route.fetch(), route.abort("failed")))
    card.get_by_role("button", name="Créer l’affiche").click()
    expect(card.get_by_role("button", name="Réessayer")).to_be_visible(timeout=30000)
    page.unroute("**/scenes")
    second = page.url.split("#message-")[1]
    until(page, lambda: scene_done(page, second))
    set_terms(engine, "2026-01-01")
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Pas à pas").click()
    expect(page.get_by_role("heading", name="Sony WH-1000XM6", exact=True)).to_be_visible()
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Message").click()
    card = page.get_by_role("log").locator(".bubble", has=page.locator(".recap"))
    card.get_by_role("button", name="Reprendre").click()
    expect(page.get_by_role("log")).to_contain_text("Version 1 prête.", timeout=30000)
    scenes = [key for path, key in posts if path.endswith("/scenes")][made:]
    assert len(scenes) == 2 and scenes[0] == scenes[1], scenes
    jobs = page.request.get(f"{smoke.ORIGIN}/api/creations/{second}/jobs").json()["items"]
    assert [job["kind"] for job in jobs].count("scene") == 1, jobs
    expect(page.locator(TERMS)).to_have_count(0)

    # « Lire les conditions » on a paid sheet whose read finds the shop accepted meanwhile, answered after the owner went
    # to another poster: no sheet comes back, nothing paid leaves; only the credits are read again.
    open_first(page, first)
    with page.expect_response("**/api/balance"):  # the sheet reads them: still `terms` (an older version stored)
        sheet = new_version_sheet(page)
    expect(sheet.get_by_role("button", name="Lire les conditions")).to_be_visible()
    set_terms(engine, terms.VERSION)
    held = []
    page.route("**/api/terms", lambda route: held.append(route))
    sheet.get_by_role("button", name="Lire les conditions").click()
    expect(sheet).to_have_count(0)
    until(page, lambda: held)
    page.evaluate("id => { location.hash = id }", second)
    expect(page.get_by_role("heading", name="Sony WH-1000XM6", exact=True)).to_be_visible()
    sent = sum(count(posts, path) for path in PAID)
    with page.expect_response("**/api/balance"):  # the read found it accepted: the credits, read again
        held.pop().continue_()
    page.evaluate(FRAMES)
    expect(page.locator(SHEET)).to_have_count(0)
    expect(page.locator(TERMS)).to_have_count(0)
    assert sum(count(posts, path) for path in PAID) == sent
    page.unroute("**/api/terms")

    # The opening read held, then answered after an acceptance made from a paid control: the dialog stays closed. A
    # double tap on « J’accepte » sends once. After it, the refused control works without a reload: a scene is admitted.
    # The read is held only while that acceptance is made, well inside its 20 s (api.ts TERMS_TIMEOUT_MS).
    set_terms(engine, "2026-01-01")
    open_first(page, first)
    reads = []
    page.route("**/api/terms", lambda route: reads.append((route, route.fetch(), time.monotonic())) if not reads and route.request.method == "GET" else route.continue_())
    finished = []
    page.on("requestfinished", lambda r: finished.append(r) if r.url.endswith("/api/terms") and r.method == "GET" else None)
    open_first(page, first, reload=True)
    until(page, lambda: reads)
    expect(page.locator(TERMS)).to_have_count(0)
    new_version_sheet(page).get_by_role("button", name="Lire les conditions").click()
    shows_conditions(page, "Les conditions d’utilisation ont changé")
    accepted = count(posts, "terms")
    page.evaluate("""() => { const button = [...document.querySelectorAll('.terms-sheet button')].find(b => b.textContent === 'J’accepte')
      button.click(); button.click() }""")
    expect(page.locator(TERMS)).to_have_count(0)
    until(page, lambda: stored(engine) == terms.VERSION)
    route, response, since = reads.pop()
    assert time.monotonic() - since < 12, "the opening read was held too close to its 20 s timeout"
    before = len(finished)
    route.fulfill(response=response)
    until(page, lambda: len(finished) > before)
    page.evaluate(FRAMES)  # its answer received and rendered: an absence is checked now
    expect(page.locator(TERMS)).to_have_count(0)
    page.unroute("**/api/terms")
    assert count(posts, "terms") == accepted + 1, posts
    new_version_sheet(page).get_by_role("button", name="Lancer la génération").click()
    expect(page.get_by_role("heading", name=REVIEW)).to_be_visible(timeout=30000)
    page.locator(".review-panel").get_by_role("button", name="Fermer").click()

    # A new version of the text between the reading and the tap: 409, its sentence, the new text (its date and a changed
    # paragraph) shown before the next acceptance; then accepted.
    set_terms(engine, None)
    new_version_sheet(page).get_by_role("button", name="Lire les conditions").click()
    shows_conditions(page)
    expect(page.locator(TERMS)).not_to_contain_text(NEW_PARAGRAPH)
    terms.VERSION = "2026-12-01"
    terms.PARAGRAPHS_FR = (NEW_PARAGRAPH,) + terms.PARAGRAPHS_FR[1:]
    page.locator(TERMS).get_by_role("button", name="J’accepte").click()
    expect(page.locator(TERMS)).to_contain_text(OUTDATED)
    assert page.evaluate(FOCUS_IN, TERMS), "after the 409 the focus left the dialog"
    expect(page.locator(TERMS)).to_contain_text(said("2026-12-01"))
    expect(page.locator(TERMS).get_by_text(NEW_PARAGRAPH, exact=True)).to_be_visible()
    shows_conditions(page)
    assert stored(engine) is None
    page.locator(TERMS).get_by_role("button", name="J’accepte").click()
    expect(page.locator(TERMS)).to_have_count(0)
    assert stored(engine) == "2026-12-01"

    # The acceptance committed and its answer lost: the sentence, then the read finds it accepted and closes the dialog.
    set_terms(engine, None)
    new_version_sheet(page).get_by_role("button", name="Lire les conditions").click()
    shows_conditions(page)
    rereads = []
    page.route("**/api/terms", lambda route: (route.fetch(), route.abort("failed")) if route.request.method == "POST" else rereads.append(route))
    page.locator(TERMS).get_by_role("button", name="J’accepte").click()
    expect(page.locator(TERMS)).to_contain_text(LOST)
    until(page, lambda: rereads)
    assert stored(engine) == terms.VERSION
    expect(page.locator(TERMS)).to_be_visible()
    rereads.pop().continue_()
    expect(page.locator(TERMS)).to_have_count(0)
    page.unroute("**/api/terms")
    context.close()
    return first


def theme_checks(page, where):
    for theme in ("sombre", "clair"):
        page.evaluate("theme => { document.documentElement.dataset.theme = theme }", theme)
        assert page.evaluate(smoke.NO_SIDEWAYS), f"sideways scroll on {where}, {theme}"
        assert page.evaluate(SHEET_FITS), f"the sheet scrolls sideways on {where}, {theme}"
        assert page.evaluate(SMALL) == 0, f"targets under 44 px on {where}"
        smoke.check_contrast(page, f"{where}, {theme}")
        page.screenshot(path=str(OUT / f"{where.replace(' ', '-')}-{theme}.png"))


def tab_stays(page, presses=6):
    for key in ["Tab"] * presses + ["Shift+Tab"] * presses:
        page.keyboard.press(key)
        assert page.evaluate(FOCUS_IN, TERMS), f"{key} left the dialog: {page.evaluate('document.activeElement?.outerHTML.slice(0, 80)')}"


def focus_button(page, name, presses=6):
    for _ in range(presses):
        if page.evaluate("name => document.activeElement?.textContent === name", name):
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"« {name} » not reached by Tab")


def data_page(page):
    """« Vos données » from the sign-in screen, signed out (T-TERMS-004, D-TERMS-007): the static page in the same tab, in
    both themes (it follows the device: no script reads the atelier's choice), nothing wider than the phone; back to the
    sign-in."""
    open_atelier(page)
    link = page.locator("form.sign-in").get_by_role("link", name="Vos données", exact=True)
    expect(link).not_to_have_attribute("target", "_blank")
    link.click()
    page.wait_for_url(f"{smoke.ORIGIN}/donnees.html")
    expect(page.get_by_role("heading", name="Vos données", level=1)).to_be_visible()
    expect(page.locator("script")).to_have_count(0)
    for scheme, ground in (("dark", "rgb(16, 15, 14)"), ("light", "rgb(245, 241, 232)")):
        page.emulate_media(color_scheme=scheme)
        assert page.evaluate("getComputedStyle(document.documentElement).backgroundColor") == ground, scheme
        assert page.evaluate(smoke.NO_SIDEWAYS), f"the data page scrolls sideways, {scheme}"
        smoke.check_contrast(page, f"data page 360, {scheme}")
        page.screenshot(path=str(OUT / f"data-page-360-{scheme}.png"), full_page=True)
    page.emulate_media(color_scheme="dark")  # the context's own, for what follows
    page.get_by_role("link", name="Retour à l’atelier", exact=True).click()
    expect(page.get_by_label("Identifiant de la boutique", exact=True)).to_be_visible()


def walk_keyboard(browser, engine, errors, product, model, first):
    """The keyboard at 360 × 640, both themes, without repeating the races (the design's second T-TERMS-003 row)."""
    context = browser.new_context(viewport={"width": 360, "height": 640}, color_scheme="dark")
    context.add_init_script(STEPS_FIRST)
    page, posts = watch(context, errors)
    data_page(page)
    # The widest contact: one unbroken word in the last paragraph, as the server would give it (SUPPORT_CONTACT_FR).
    terms.paragraphs = lambda settings: [paragraph.replace("{contact}", LONG_CONTACT) for paragraph in terms.PARAGRAPHS_FR]
    CONTACT[0] = LONG_CONTACT
    set_terms(engine, None)
    sign_in(page)
    shows_conditions(page)
    theme_checks(page, "opening 360")
    tab_stays(page)
    focus_button(page, "Plus tard")
    page.keyboard.press("Enter")
    expect(page.locator(TERMS)).to_have_count(0)

    # From an open review, a late 403 (a style asked before the review was opened): the dialog takes the focus and keeps
    # Tab; the review behind is inert; « Plus tard » gives the focus back to the review, where free work goes on.
    open_first(page, first)
    page.get_by_role("tab", name="Style", exact=True).click()
    page.get_by_text("Créer un style depuis une affiche", exact=True).click()
    page.locator(".new-look input[type=file]").set_input_files(model)
    expect(page.get_by_alt_text("Affiche modèle pour le nouveau style")).to_be_visible()
    held = []
    page.route("**/looks", lambda route: held.append((route, route.fetch())) if route.request.method == "POST" else route.continue_())
    page.get_by_role("button", name="Enregistrer ce style").click()
    page.get_by_role("button", name="Créer le style", exact=True).click()
    until(page, lambda: held)
    page.get_by_role("button", name=re.compile(r"^Versions ")).click()
    page.get_by_role("button", name="Comparer la version 2", exact=True).click()  # the one still to check
    review = page.locator("[aria-labelledby=review-title]")
    expect(review).to_be_visible()
    page.wait_for_function(FOCUS_IN, arg="[aria-labelledby=review-title]")
    route, response = held.pop()
    route.fulfill(response=response)
    shows_conditions(page)
    expect(review).to_have_attribute("inert", "")
    theme_checks(page, "over the review 360")
    tab_stays(page)
    focus_button(page, "Plus tard")
    page.keyboard.press("Enter")
    expect(page.locator(TERMS)).to_have_count(0)
    page.wait_for_function(FOCUS_IN, arg="[aria-labelledby=review-title]")
    page.unroute("**/looks")
    approve = review.get_by_role("button", name="Tout est conforme, approuver")
    approve.focus()
    page.keyboard.press("Enter")
    expect(review).to_have_count(0)

    # A chat request the server never took, refused (403), kept with its key; its « Réessayer » held. Meanwhile the
    # sign-out confirmation opens; the late 403 opens the dialog behind it: the confirmation keeps the front and the
    # focus; closing it focuses the dialog. Accepted, the same « Réessayer » is the request's first admission.
    with page.expect_response("**/api/balance"):  # leaving the poster reads the credits again (fresh, loadShop)
        page.evaluate("() => { location.hash = 'etapes' }")
    expect(page.get_by_label("Photos du produit")).to_be_enabled()  # not while the page is busy loading
    page.get_by_label("Photos du produit").set_input_files(product)
    expect(page.locator(".photo-strip img")).to_have_count(1)
    page.get_by_label("Nom du produit", exact=True).fill("JBL Tune 520")
    page.get_by_label("Prix en ariary", exact=True).fill("250 000")
    page.evaluate("() => { location.hash = 'message' }")
    card = page.get_by_role("log").locator(".bubble", has=page.locator(".recap"))
    expect(card.get_by_role("button", name="Lire les conditions")).to_be_visible()
    set_terms(engine, terms.VERSION)
    card.get_by_role("button", name="Lire les conditions").click()
    expect(card.get_by_role("button", name="Créer l’affiche")).to_be_visible()  # the read found it accepted
    set_terms(engine, None)  # the balance shown is now stale
    card.get_by_role("button", name="Créer l’affiche").click()
    shows_conditions(page)
    page.keyboard.press("Escape")
    expect(page.locator(TERMS)).to_have_count(0)
    expect(card.get_by_role("button", name="Réessayer")).to_be_visible()
    held = []
    page.route("**/scenes", lambda route: held.append((route, route.fetch())))
    card.get_by_role("button", name="Réessayer").click()
    until(page, lambda: held)
    page.locator(".app-header .sign-out").click()
    confirmation = page.locator("[aria-labelledby=titre-confirmation]")
    expect(confirmation).to_contain_text("Se déconnecter ?")
    page.wait_for_function(FOCUS_IN, arg="[aria-labelledby=titre-confirmation]")
    route, response = held.pop()
    route.fulfill(response=response)
    expect(page.locator(TERMS)).to_have_attribute("inert", "")
    page.evaluate(FRAMES)  # mounted, and its focus attempts done (v-modal, the front watcher's next tick)
    assert page.evaluate(FOCUS_IN, "[aria-labelledby=titre-confirmation]")
    assert smoke.topmost(confirmation.locator(".confirm"))
    page.keyboard.press("Escape")
    expect(confirmation).to_have_count(0)
    page.wait_for_function(FOCUS_IN, arg=TERMS)
    shows_conditions(page)
    assert page.evaluate(smoke.NO_SIDEWAYS)
    page.unroute("**/scenes")
    focus_button(page, "J’accepte")
    page.keyboard.press("Enter")
    expect(page.locator(TERMS)).to_have_count(0)
    card.get_by_role("button", name="Réessayer").click()
    expect(page.get_by_role("log")).to_contain_text("Version 1 prête.", timeout=30000)
    scenes = [key for path, key in posts if path.endswith("/scenes")]
    assert len(scenes) == 3 and len(set(scenes)) == 1, scenes  # one key: refused twice, then admitted once
    creation = page.url.split("#message-")[1]
    jobs = page.request.get(f"{smoke.ORIGIN}/api/creations/{creation}/jobs").json()["items"]
    assert [job["kind"] for job in jobs].count("scene") == 1, jobs
    context.close()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    assert (smoke.ROOT / "frontend/dist/index.html").is_file(), "build first: corepack npm@10 run build"
    product = OUT / "product.png"
    photo = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(photo).rounded_rectangle((250, 160, 750, 840), 50, fill="#202020")
    photo.save(product)
    model = smoke.ROOT / "frontend/public/styles/sombre.jpg"
    errors, version, paragraphs, text = [], terms.VERSION, terms.paragraphs, terms.PARAGRAPHS_FR
    with tempfile.TemporaryDirectory(prefix="affiche-terms-") as data:
        server = smoke.serve(data)
        engine = make_engine(Path(data))
        with (OUT / "preview.log").open("w") as log:
            vite = subprocess.Popen(["node", str(smoke.ROOT / "frontend/node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1",
                                     "--port", str(smoke.WEB_PORT), "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        first = walk_journey(browser, engine, errors, product, model)
                        walk_keyboard(browser, engine, errors, product, model, first)
                        assert not errors, errors
                    finally:
                        browser.close()
                (OUT / "results.json").write_text(json.dumps({"errors": errors, "viewports": [1280, 360]}, indent=2))
            finally:
                terms.VERSION, terms.paragraphs, terms.PARAGRAPHS_FR = version, paragraphs, text
                vite.terminate()
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill()
                    vite.wait(timeout=10)
                engine.dispose()
                smoke.stop(*server)
    print("Conditions browser checks passed (stub only): the dialog at the opening after a sign-in and on a session that "
          "lasts, no sign-out in it; « Plus tard » then an edit, the check, the final check and the download; a fresh chat "
          "card offering « Lire les conditions » with no /scenes sent; a refused chat message back in the field; a free "
          "Claude button refused; the balance answering late on an open paid sheet; the text not fetched, then read again "
          "as text only; an admitted request's lost 202 taken up with « Reprendre » after an older version, no dialog; a "
          "stale balance; a held opening read answered after the acceptance; a double tap sent once; a scene admitted "
          "after it; a new version (409) shown; a lost acceptance found by the read. At 360 × 640 in both themes by "
          "keyboard: from an open review, and behind the sign-out confirmation; a never-admitted request's first "
          "admission after acceptance. « Vos données » from the sign-in screen, signed out, in both themes at 360.")


if __name__ == "__main__":
    run()
