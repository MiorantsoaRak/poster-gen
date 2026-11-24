"""Creation by message in a real browser (T-CHAT-003 and 004, D-TEXT-FIRST-001 and 003): stub providers, temporary data, zero
spend. From backend/: uv run python ../frontend/tests/chat_browser.py (ports 8000 and 5173 must be free).
Pictures: outputs/chat-smoke/."""
import base64
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

import browser_smoke as smoke

OUT = smoke.ROOT / "outputs" / "chat-smoke"
REVIEW, FINAL = "Vérifier la fidélité du produit", "Vérifier votre affiche"
THREAD = "id => JSON.parse(localStorage.getItem('affiche.shop1.chat.' + id))"
START = "localStorage.getItem('affiche.start')"
PENDING = "() => JSON.parse(localStorage.getItem('affiche.shop1.chat.pending'))?.key ?? null"
SCENE_JOBS = "id => fetch('/api/creations/' + id + '/jobs').then(r => r.json()).then(body => body.items.filter(job => job.kind === 'scene').length)"
POSTER_FONTS = re.compile(r"/fonts/(NotoSerif|Montserrat|NotoSans-Bold)")
PLAN_STALE = "L’affiche a changé depuis la préparation de cette génération."
INVALID_PLAN = "Cette composition n’est pas valable (un élément sort de l’affiche ou en recouvre un autre). Annulez le dernier déplacement et réessayez."
UNLISTED = "La nouvelle version est faite, mais elle n’apparaît pas dans cette affiche. Ouvrez Pas à pas pour la retrouver."
# What a card that pays for an image says (D-BALANCE-006): its credit and what is left (the smokes' shop has 100), and under
# « Reprendre » or « Réessayer » that the kept request is paid once.
COST, ONCE = re.compile(r"1 crédit · il vous en reste \d+"), "1 crédit, une seule fois pour cette demande"
# Whether an element is wholly inside the visible viewport, and is what a tap at its centre reaches.
REACH_JS = r"""e => { const b = e.getBoundingClientRect(), v = visualViewport
  return { inside: b.left >= v.offsetLeft - .5 && b.top >= v.offsetTop - .5 && b.right <= v.offsetLeft + v.width + .5 && b.bottom <= v.offsetTop + v.height + .5,
    hit: e.contains(document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)), box: [b.x, b.y, b.width, b.height].map(Math.round) } }"""
# Above the button of every scene adjustment still to be had, whatever brought the card (D-TERMS-005, generation.ts).
WARNING = "Vous demandez des caractéristiques sans les lister ? L’IA choisira les caractéristiques : vérifiez-les avant de publier."
# The price question of a message with no amount read in it (D-KIT-002).
NO_PRICE = "Je ne vois pas de prix dans votre message. Écrivez-le en chiffres, par exemple 250 000 Ar."
# The last line of a card whose words are drawn again in a whole new image (D-KIT-007).
REDRAW = "Le texte est dessiné dans l’image : cette correction refait toute l’image, pour 1 crédit."


def sign_in(page):
    page.goto(smoke.ORIGIN)
    page.get_by_label("Identifiant de la boutique", exact=True).fill(smoke.IDENTIFIER)
    page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
    page.get_by_role("button", name="Ouvrir l’atelier").click()


def looks_right(page, where, name=None, marks=(), placeholders=()):
    """No sideways scroll, readable text, placeholders and accent marks (those named must be measured), one blur per
    surface; a picture for a person to judge."""
    assert page.evaluate(smoke.NO_SIDEWAYS), f"sideways scroll on {where}"
    page.wait_for_function("document.documentElement.scrollHeight <= innerHeight + 1")  # the page never scrolls behind the chat
    smoke.check_contrast(page, where, *marks, placeholders=placeholders)
    smoke.check_one_blur(page, where)
    if name:
        page.screenshot(path=str(OUT / name))


def both_themes(page, where, name, marks=(), placeholders=()):
    first = smoke.theme_of(page)
    for theme in (first, "clair" if first == "sombre" else "sombre"):
        if smoke.theme_of(page) != theme:
            smoke.toggle_theme(page, "Passer au thème clair" if theme == "clair" else "Passer au thème sombre")
        looks_right(page, f"{where}, {theme}", f"{name}-{theme}.png", marks, placeholders)


SEND, ARROW = ".chat .send:not(:disabled)", ".chat .send:not(:disabled) svg path"
COMPOSER = [[".composer", "borderTopColor", "parent", 3]]


def composer_edge(page, where):
    """The composer is a field: its boundary is 3:1 against what is around it at rest and while its words have the
    keyboard's focus, in both themes (R-REDESIGN-001)."""
    field, edge = page.get_by_label("Votre message"), "e => getComputedStyle(e).borderTopColor"

    def check(theme):
        field.evaluate("e => e.blur()")
        page.wait_for_function(smoke.SETTLED, polling=100)
        assert page.locator(".composer").evaluate(edge) == smoke.PAINT[theme]["control"], f"the composer's edge at rest, {where}, {theme}"
        smoke.check_marks(page, f"the composer's boundary, {where}, {theme}", ".composer", marks=COMPOSER)
        field.focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        assert field.evaluate("e => e === document.activeElement && e.matches(':focus-visible')"), f"the composer's field not focused by the keyboard, {where}"
        page.wait_for_function(smoke.SETTLED, polling=100)
        assert page.locator(".composer").evaluate(edge) == smoke.PAINT[theme]["text"], f"the focused composer's edge, {where}, {theme}"
        smoke.check_marks(page, f"the composer's boundary, focused, {where}, {theme}", ".composer", marks=COMPOSER)
    smoke.both_themes(page, check)
    field.evaluate("e => e.blur()")


def pressed_send(page, where):
    """With reduced motion a pressed « Envoyer » keeps its Signal fill and wears a ring of the line colour: the arrow's own
    stroke at 4.5:1 on the fill, the ring at 3:1 on what is around it, in both themes (D-POLISH-002)."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    toggle = lambda theme: smoke.toggle_theme(page, "Passer au thème clair" if theme == "clair" else "Passer au thème sombre")
    first = smoke.theme_of(page)
    for theme in (first, "clair" if first == "sombre" else "sombre"):
        if smoke.theme_of(page) != theme:
            toggle(theme)
        def read():
            fill = page.eval_on_selector(SEND, "e => getComputedStyle(e).backgroundColor")
            assert fill == "rgb(242, 199, 68)", (where, theme, fill)  # the Signal, not the grey step of other buttons
            smoke.check_marks(page, f"pressed « Envoyer », {where}, {theme}", ARROW, SEND, show=True,
                              marks=[[ARROW, "stroke", "self", 4.5], [SEND, "boxShadow", "parent", 3]])
        smoke.pressed_look(page, cdp, SEND, reduced=True, read=read)
    toggle(first)
    cdp.detach()


def say(page, text):
    page.get_by_label("Votre message").fill(text)
    page.get_by_role("button", name="Envoyer").click()


# A 401 to the chat's read whose body is held until the test lets it go: its headers alone close the gate (api.ts).
LATE_401 = """const real = window.fetch; window.bodyGate = new Promise(done => { window.releaseBody = done })
window.fetch = (input, init) => !(window.hold401 && String(input).includes('/api/reads')) ? real(input, init) : Promise.resolve(new Response(
  new ReadableStream({ async start(out) { await window.bodyGate; out.enqueue(new TextEncoder().encode(JSON.stringify({ error: { code: 'unauthenticated',
    message_fr: 'Connectez-vous pour continuer.', retryable: false } }))); out.close() } }), { status: 401, headers: { 'Content-Type': 'application/json' } }))"""


def walk_late_401(browser, errors, session):
    """Tab A's read meets a 401 whose body comes late: A's chat leaves with the gate and lets the chat go; tab B takes it
    and writes the thread. When A's body arrives, A writes nothing: B's thread and request stay as B left them (review
    r3, 2). The one-tab case, the card « Connectez-vous pour continuer. », is walk_changes'."""
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    shop_keys = "() => Object.fromEntries(Object.keys(localStorage).filter(key => key.startsWith('affiche.shop1.chat.')).map(key => [key, localStorage.getItem(key)]))"
    try:
        first = context.new_page()
        first.set_default_timeout(10000)
        first.on("pageerror", lambda error: errors.append(str(error)))
        first.add_init_script(LATE_401)
        first.goto(smoke.ORIGIN + "/#message")
        expect(first.get_by_label("Votre message")).to_be_visible()
        first.evaluate("window.hold401 = true")
        say(first, "Casque d’essai, 90 000 Ar")
        expect(first.locator(".chat")).to_have_count(0)  # the gate closed on the 401's headers
        expect(first.get_by_label("Mot de passe", exact=True)).to_be_visible()
        second = context.new_page()
        second.set_default_timeout(10000)
        second.on("pageerror", lambda error: errors.append(str(error)))
        second.goto(smoke.ORIGIN + "/#message")
        expect(second.get_by_label("Votre message")).to_be_visible()
        expect(second.get_by_text("Le chat est ouvert dans un autre onglet.")).to_have_count(0)  # it holds the chat
        # B finds A's read interrupted and sends it again itself: its answer settles it in B's thread.
        log = second.get_by_role("log")
        expect(log).to_contain_text("L’envoi a été interrompu.")
        log.get_by_role("button", name="Réessayer", exact=True).click()
        second.wait_for_function("() => !localStorage.getItem('affiche.shop1.chat.pending')")  # its read answered
        second.wait_for_timeout(500)
        written = second.evaluate(shop_keys)
        first.evaluate("window.releaseBody()")
        first.wait_for_timeout(1000)
        assert second.evaluate(shop_keys) == written, "the late 401 wrote over the other tab's chat"
        assert "Connectez-vous pour continuer." not in json.dumps(written, ensure_ascii=False) and "Connectez-vous pour continuer." not in json.dumps(second.evaluate(shop_keys), ensure_ascii=False)
    finally:
        context.close()


def walk_desktop(browser, errors, product, inspiration):
    held = {"on": False, "look": False}
    reads, scenes, fonts, looks = [], [], [], []

    # The stub makes a scene in about a second: its state is held at « running » in the answers (one job, and the
    # poster's list of jobs read at a reload) while the real job ends behind. The style model's reading too.
    def hold_job(route):
        if not held["on"] and not held["look"]:
            return route.continue_()
        response = route.fetch()
        body = response.json()
        for job in body.get("items", [body]):
            if (job["kind"] == "scene" and held["on"]) or (job["kind"] == "look" and held["look"]):
                job.update(status="running", result_ref=None, error_code=None, finished_at=None)
        route.fulfill(response=response, json=body)

    def seen(request):
        if request.method == "POST" and request.url.endswith("/api/reads"):
            reads.append(request.headers["idempotency-key"])
        if request.method == "POST" and request.url.endswith("/scenes"):
            scenes.append(request.headers["idempotency-key"])
        if request.method == "POST" and request.url.endswith("/looks"):
            looks.append(request.post_data_json)
        if POSTER_FONTS.search(request.url) or "PosterCanvas" in request.url:  # a font file, or the canvas's code (the dev server's module here)
            fonts.append(request.url)

    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    context.route("**/api/jobs/*", hold_job)
    context.route("**/api/creations/*/jobs", hold_job)
    context.on("request", seen)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: print(f"HTTP {response.status} {response.url}", flush=True) if response.status >= 400 else None)
    for attempt in range(60):
        try:
            page.goto(smoke.ORIGIN, timeout=2000)
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(.25)
    sign_in(page)

    home = page.get_by_role("heading", name="Accueil", exact=True)
    expect(home).to_be_visible()
    expect(page.get_by_label("Photos du produit")).to_have_count(0)
    expect(page.locator(".seg")).to_have_count(0)
    assert page.evaluate(START) is None
    page.get_by_role("link", name="Créer une affiche").click()
    chat = page.locator(".chat")
    expect(chat).to_be_visible()
    assert page.url.endswith("#message") and page.evaluate(START) is None, page.url
    switch = page.get_by_role("group", name="Façon de créer")
    expect(switch.get_by_role("button", name="Message")).to_have_attribute("aria-pressed", "true")
    thread, field, send = page.get_by_role("log"), page.get_by_label("Votre message"), page.get_by_role("button", name="Envoyer")
    expect(thread).to_contain_text("Ajoutez une photo du produit.")
    expect(send).to_be_disabled()
    # The chat reloads in place. The empty address opens Home and its creator defaults to chat.
    page.reload()
    expect(chat).to_be_visible()
    page.goto(smoke.ORIGIN + "/#")
    expect(home).to_be_visible()
    page.get_by_role("link", name="Créer une affiche").click()
    expect(chat).to_be_visible()
    page.wait_for_url("**/#message")
    expect(home).to_have_count(0)
    both_themes(page, "empty chat, desktop", "chat-empty-1366", placeholders=(".composer textarea",))
    composer_edge(page, "empty chat, desktop")

    # The unsent text survives a reload.
    field.fill("Sony WH-1000XM6 noir, 700 000 Ar")
    page.reload()
    expect(field).to_have_value("Sony WH-1000XM6 noir, 700 000 Ar")
    # Two images: both are product photos, never a style model by their position (D-KIT-006); each is uploaded at once.
    # One touch on a label makes that photo the style model; one on another moves the model there; one on the model
    # makes it a product photo again.
    # The first is pasted (an image copied from a page), the second dropped on the composer: attached like picked ones.
    # Pasted text stays text.
    handed = """([kind, name, mime, b64]) => {
        const data = new DataTransfer()
        if (b64) data.items.add(new File([Uint8Array.from(atob(b64), c => c.charCodeAt(0))], name, { type: mime }))
        else data.setData('text/plain', name)
        const init = { bubbles: true, cancelable: true, [kind === 'paste' ? 'clipboardData' : 'dataTransfer']: data }
        return !document.querySelector('.composer textarea').dispatchEvent(kind === 'paste' ? new ClipboardEvent('paste', init) : new DragEvent('drop', init))
    }"""
    pics = page.locator(".tray .pic")
    roles = pics.locator(".pic-role")
    assert page.evaluate(handed, ["paste", "du texte", "", ""]) is False  # not held back: the browser pastes it
    expect(pics).to_have_count(0)
    for kind, file in (("paste", product), ("drop", inspiration)):
        mime = "image/png" if file.suffix == ".png" else "image/jpeg"
        assert page.evaluate(handed, [kind, file.name, mime, base64.b64encode(file.read_bytes()).decode()]) is True
    expect(pics).to_have_count(2)
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    expect(roles).to_have_text(["Produit", "Produit"])
    expect(roles.nth(1)).to_have_accessible_name("Produit : marquer comme modèle de style")
    expect(page.get_by_role("group", name="Style de l’affiche").get_by_role("button")).to_have_count(3)
    roles.nth(0).click()
    expect(roles).to_have_text(["Modèle de style", "Produit"])
    expect(roles.nth(0)).to_have_accessible_name("Modèle de style : marquer comme produit")
    expect(page.locator(".style-row")).to_have_text("Scène : votre modèle de style")
    roles.nth(1).click()
    expect(roles).to_have_text(["Produit", "Modèle de style"])
    roles.nth(1).click()
    expect(roles).to_have_text(["Produit", "Produit"])
    roles.nth(1).click()
    expect(roles).to_have_text(["Produit", "Modèle de style"])
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    for label in ("Ajouter des photos", "Envoyer", "Retirer cette image"):
        expect(page.get_by_role("button", name=label).first).to_be_visible()
    send.click()
    # One message, two images: the recap, with the price large and the cost said as the paid dialog says it.
    recap = thread.locator(".bubble.bot", has=page.locator(".recap"))
    expect(recap).to_have_count(1)
    expect(recap.locator(".recap b")).to_have_text("Sony WH-1000XM6 noir")
    expect(recap.locator(".recap-price")).to_have_text(re.compile(r"^700\s000 Ar$"))
    expect(recap.locator(".recap-format")).to_have_text("Publication 4:5")
    expect(recap).to_contain_text("Scène : votre modèle de style (lu, puis gardé dans votre kit)")
    expect(recap).to_contain_text(COST)
    expect(recap.locator(".pic")).to_have_text(["Produit", "Modèle de style"])
    expect(thread.locator(".bubble.me")).to_contain_text("Sony WH-1000XM6 noir, 700 000 Ar")
    expect(field).to_be_focused()
    expect(field).to_have_value("")
    assert page.evaluate("localStorage.getItem('affiche.shop1.chat.unsent') ?? localStorage.getItem('affiche.shop1.chat.pending')") is None
    assert len(reads) == 1, reads
    both_themes(page, "recap, desktop", "chat-recap-1366")

    # One tap: the card is spent before the request leaves, and its id is the paid request's key. The style photo is read
    # into one of the shop's looks first (D-KIT-006): one brief, no credit, and nothing paid has left while it is read.
    held["on"] = held["look"] = True
    create = page.get_by_role("button", name="Créer l’affiche")
    create.click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    poster = page.url.split("#message-")[1]
    wait = thread.locator(".chat-wait")
    expect(wait).to_have_text("Je lis votre modèle de style…")
    tapped = next(item for item in page.evaluate(THREAD, poster)["items"] if item.get("spent"))
    style_asset = next(picture["asset"] for picture in tapped["card"]["pictures"] if picture["role"] == "inspiration")
    assert scenes == [] and looks == [{"name": "Style 1", "reference_asset": style_asset}], (scenes, looks)
    held["look"] = False
    expect(wait).to_contain_text("Je dessine l’affiche… En général 1 à 2 minutes.")
    expect(thread).to_contain_text("Votre modèle de style est gardé dans votre kit : « Style 1 ».")
    model = page.request.get(smoke.ORIGIN + "/api/looks").json()["items"]
    assert [(item["name"], item["reference_asset"]) for item in model] == [("Style 1", style_asset)], model
    expect(create).to_have_count(0)
    field.fill("fond plus sombre")  # typing stays possible; « Envoyer » waits
    expect(send).to_be_disabled()
    spent = [item for item in page.evaluate(THREAD, poster)["items"] if item.get("spent")]
    assert len(spent) == 1 and scenes == [spent[0]["id"]], (spent, scenes)
    # The card holds its poster and its job; the new thread's key says where the thread went.
    assert spent[0]["creation"] == poster and re.fullmatch(r"[a-f0-9-]{36}", spent[0]["job"]), spent
    assert json.loads(page.evaluate("localStorage.getItem('affiche.shop1.chat.new')")) == {"moved": poster}
    both_themes(page, "creation, desktop", "chat-wait-1366", marks=(".chat-wait i",))
    # A reload in the middle: the job is followed again, the spent card has no button, nothing is asked twice.
    page.reload()
    expect(wait).to_contain_text("Je dessine l’affiche…")
    expect(recap).to_have_count(1)
    expect(create).to_have_count(0)
    expect(field).to_have_value("fond plus sombre")
    held["on"] = False
    # The version arrives as a card; the check never opens by itself.
    verify = page.get_by_role("button", name="Vérifier", exact=True)
    expect(verify).to_be_visible(timeout=30000)
    expect(page.get_by_role("heading", name=FINAL)).to_have_count(0)
    expect(thread).to_contain_text("Version 1 prête.")
    body = spent[0]["request"]["body"]
    assert body["format"] == "feed"
    # The scene names the look read from the style photo, never the raw image; one brief was asked for this poster.
    assert body["headline"]["look_id"] == model[0]["id"] and "style_reference_asset" not in body, body
    assert [job["kind"] for job in page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}/jobs").json()["items"]].count("look") == 1
    expect(recap.locator(".recap-format")).to_have_text("Publication 4:5")
    expect(recap).to_contain_text("Scène : votre modèle de style")
    assert scenes == [spent[0]["id"]], scenes
    side = page.locator(".chat-side")
    expect(side).to_contain_text("Version 1 · à vérifier")
    assert side.bounding_box()["x"] > thread.bounding_box()["x"] + thread.bounding_box()["width"], "wide: the poster has the right column"
    assert thread.locator(".chat-poster img").evaluate("e => e.complete && e.naturalWidth > 0 && e.src.includes('display=true')")
    both_themes(page, "result, desktop", "chat-result-1366", marks=(ARROW,))  # « fond plus sombre » typed
    pressed_send(page, "result, desktop")
    # A single review compares the original with the exact file; correction leaves both decisions open.
    address = f"{smoke.ORIGIN}/api/creations/{poster}"
    balance_url = smoke.ORIGIN + "/api/balance"
    before_review = page.request.get(balance_url, fail_on_status_code=True).json()
    verify.click()
    panel = page.locator(".final-preview")
    expect(panel.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    assert chat.evaluate("e => e.inert")
    expect(panel.get_by_alt_text("Photo originale 1 à comparer")).to_be_visible()
    expect(panel).to_contain_text("Chaque texte ou caractéristique ajouté par l’IA doit être exact")
    expect(panel).to_contain_text(re.compile(r"700\s000 Ar"))
    assert page.request.get(address).json()["confirmation"] is None
    # « Corriger l’affiche » from Message (D-KIT-007): the review closes on the poster's thread, whose field takes the
    # cursor for the correction.
    panel.get_by_role("button", name="Corriger l’affiche").click()
    expect(panel).to_have_count(0)
    assert page.url.endswith(f"#message-{poster}"), page.url
    expect(field).to_be_focused()
    expect(field).to_have_attribute("placeholder", "Dites ce qu’il faut corriger.")
    assert page.request.get(address + "/visuals").json()["items"][0]["status"] == "pending_review"
    verify.click()
    smoke.download_review(page)
    assert page.request.get(address + "/visuals").json()["items"][0]["status"] == "approved"
    expect(page.get_by_role("link", name="Télécharger le PNG")).to_be_visible()
    after_render = page.request.get(balance_url, fail_on_status_code=True).json()
    assert (after_render["available"], after_render["pending"]) == (before_review["available"], before_review["pending"])
    page.screenshot(path=str(OUT / "chat-confirmed-1366.png"))
    page.get_by_role("button", name="Fermer").click()
    expect(thread.locator(".chat-state")).to_have_text("Confirmée")
    expect(verify).to_have_count(0)
    # The chat never mounted the canvas, nor loaded its code (Konva and the fonts' module) or a poster font.
    expect(page.locator(".poster-canvas, .konvajs-content")).to_have_count(0)
    assert not fonts, fonts
    assert len(reads) == 1, reads

    # The style model is one of the shop's models in « Mon kit » from now on (D-KIT-006, 011).
    smoke.go(page, "Mon kit")
    expect(page.get_by_role("heading", name="Mon kit", exact=True)).to_be_visible()
    expect(page.locator(".look-card", has_text="Style 1")).to_have_count(1)
    # « Mes affiches » opens a poster in the chat when the chat is the start view; the switch shows the same poster in the editor.
    smoke.go(page, "Mes affiches")
    page.get_by_role("button", name=re.compile("Sony WH-1000XM6 noir")).first.click()
    page.wait_for_url(f"**/#message-{poster}")
    # As in the editor, a confirmed poster opens on its file, ready to download again.
    expect(page.get_by_role("link", name="Télécharger le PNG")).to_be_visible()
    page.get_by_role("button", name="Fermer").click()
    expect(thread).to_contain_text("Version 1 prête.")
    switch.get_by_role("button", name="Pas à pas").click()
    page.wait_for_url(f"**/#{poster}")
    expect(page.locator(".editor .poster-canvas canvas").first).to_be_visible()
    expect(chat).to_have_count(0)
    assert page.evaluate(START) == "steps"
    switch.get_by_role("button", name="Message").click()
    page.wait_for_url(f"**/#message-{poster}")
    expect(page.locator(".editor")).to_have_count(0)

    # A new poster shows nothing of the one just opened.
    smoke.go(page, "Nouvelle affiche")
    page.wait_for_url("**/#message")
    expect(thread.locator(".bubble")).to_have_count(0)  # only the welcome (D-REDESIGN-003)
    expect(thread.locator(".hello")).to_have_count(1)
    expect(page.locator(".chat-side, .chat-poster")).to_have_count(0)
    # A lost answer: the bubble stays with « Réessayer ». Typing the next message, and a reload, leave the pending read
    # alone: the retry is the same request (same key), and « Envoyer » waits for it.
    context.route("**/api/reads", lambda route: route.abort("failed"))
    say(page, "Casque JBL Tune")
    expect(thread.locator(".bubble.bot").last).to_contain_text("Connexion interrompue")
    expect(thread.locator(".bubble.me")).to_have_text("Casque JBL Tune")
    field.fill("250 000 Ar")
    expect(send).to_be_disabled()
    page.reload()
    expect(field).to_have_value("250 000 Ar")
    expect(send).to_be_disabled()
    expect(thread.locator(".bubble.me")).to_have_text("Casque JBL Tune")
    context.unroute("**/api/reads")
    thread.get_by_role("button", name="Réessayer").click()
    # No price: asked, with how to write it (D-KIT-002). No photo: asked, with its button.
    expect(thread).to_contain_text(NO_PRICE)
    assert len(reads) == 3 and reads[1] == reads[2] != reads[0], reads
    assert page.evaluate("localStorage.getItem('affiche.shop1.chat.pending')") is None
    send.click()
    ask = thread.locator(".bubble.bot").last
    expect(ask).to_contain_text("Il me faut une photo du produit.")
    with page.expect_file_chooser() as chooser:
        ask.get_by_role("button", name="Ajouter une photo").click()
    chooser.value.set_files(product)
    expect(page.locator(".tray .pic .pic-role")).to_have_text("Produit")
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    # Without an inspiration the house styles and the shop's model are offered (D-KIT-009): the last one used first, and
    # chosen for this new poster.
    styles = page.get_by_role("group", name="Style de l’affiche").get_by_role("button")
    expect(styles).to_have_text(["Style 1", "Studio clair", "Couleurs du produit", "Luxe sombre"])
    expect(styles.nth(0)).to_have_attribute("aria-pressed", "true")
    send.click()
    expect(ask.get_by_role("button", name="Ajouter une photo")).to_have_count(0)
    expect(recap.last.locator(".recap b")).to_have_text("Casque JBL Tune")
    expect(recap.last.locator(".recap-price")).to_have_text(re.compile(r"^250\s000 Ar$"))
    expect(recap.last).to_contain_text("Scène : Style 1")
    styles.filter(has_text="Luxe sombre").click()
    expect(recap.last).to_contain_text("Scène : Luxe sombre")
    assert len(reads) == 4, reads
    # A correction replaces the recap: only the latest can be tapped.
    say(page, "260 000 Ar")
    expect(recap).to_have_count(2)
    expect(page.get_by_role("button", name="Créer l’affiche")).to_have_count(1)
    expect(recap.last.locator(".recap-price")).to_have_text(re.compile(r"^260\s000 Ar$"))
    # The switch carries what is typed to the form (the same fields), and back.
    switch.get_by_role("button", name="Pas à pas").click()
    expect(page.get_by_label("Nom du produit", exact=True)).to_have_value("Casque JBL Tune")
    expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("260000")
    expect(page.locator(".photo-strip img")).to_have_count(1)
    assert page.url.endswith("#etapes"), page.url
    # Corrected in the form, the name comes back to the chat as a fresh recap, with no paid read.
    page.get_by_label("Nom du produit", exact=True).fill("Casque JBL Tune 520")
    switch.get_by_role("button", name="Message").click()
    expect(recap).to_have_count(3)
    expect(recap.last.locator(".recap b")).to_have_text("Casque JBL Tune 520")
    expect(page.get_by_role("button", name="Créer l’affiche")).to_have_count(1)
    assert len(reads) == 5 and scenes == [spent[0]["id"]], (reads, scenes)
    # The network fails as /scenes leaves: the card keeps the request as sent and waits with « Réessayer ». No new card: the
    # request may have reached the server.
    context.route("**/scenes", lambda route: route.abort("failed"))
    page.get_by_role("button", name="Créer l’affiche").click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    second = page.url.split("#message-")[1]
    retry, resume = thread.get_by_role("button", name="Réessayer"), thread.get_by_role("button", name="Reprendre")
    expect(retry).to_be_visible()
    expect(page.get_by_role("button", name="Créer l’affiche")).to_have_count(0)
    context.unroute("**/scenes")
    spent = lambda: [item for item in page.evaluate(THREAD, second)["items"] if item.get("spent")][-1]
    kept = spent()
    assert kept["request"]["path"] == f"/api/creations/{second}/scenes" and "job" not in kept and page.evaluate(SCENE_JOBS, second) == 0, kept
    revision = lambda: page.request.get(f"{smoke.ORIGIN}/api/creations/{second}").json()["revision"]

    def saved_after(before):
        for _ in range(50):
            if revision() > before:
                return
            page.wait_for_timeout(200)
        raise AssertionError("the edit was not saved")
    # The title changes in « Pas à pas ». Back in the chat nothing is sent by itself: the card says the poster may not have
    # been started and offers « Reprendre ». That sends the kept request exactly as it left; the server refuses it for good
    # (made for an older revision of the poster), and only then is a new card offered, with the new words.
    switch.get_by_role("button", name="Pas à pas").click()
    page.wait_for_url(f"**/#{second}")
    square = page.get_by_role("radio", name="Carré 1:1", exact=True)
    square.check()
    page.get_by_role("tab", name="Textes", exact=True).click()
    page.locator("textarea[name=title]").fill("Casque JBL Tune 520 Pro")
    page.get_by_label("Prix en ariary", exact=True).fill("270 000")
    saved_after(kept["request"]["revision"])
    switch.get_by_role("button", name="Message").click()
    page.wait_for_url(f"**/#message-{second}")
    expect(thread).to_contain_text("L’affiche n’a peut-être pas été lancée.")
    expect(resume).to_be_visible()
    page.wait_for_timeout(500)
    assert scenes.count(kept["id"]) == 1, scenes  # nothing sent on the return
    # The previously consented request may be replayed even if the product read is unavailable.
    source_path = "**/api/product-inputs/*"
    page.route(source_path, lambda route: route.abort("failed"))
    page.reload(wait_until="domcontentloaded")
    expect(resume).to_be_enabled()
    resume.click()
    # The new recap needs its actual source photos before its own first tap. Reloading these is free.
    create = thread.get_by_role("button", name="Créer l’affiche")
    expect(recap.last).to_contain_text("Les photos du produit sont indisponibles.")
    expect(create).to_be_disabled()
    page.unroute(source_path)
    pending_source = []
    page.route(source_path, lambda route: pending_source.append(route))
    recap.last.get_by_role("button", name="Recharger le produit").click()
    expect(recap.last).to_contain_text("Chargement des photos du produit…")
    expect(create).to_be_disabled()
    for _ in range(50):
        if pending_source:
            break
        page.wait_for_timeout(50)
    assert len(pending_source) == 1
    pending_source[0].continue_()
    page.unroute(source_path)
    expect(create).to_be_enabled()
    expect(page.get_by_role("button", name="Créer l’affiche")).to_have_count(1)
    expect(recap.last.locator(".recap b")).to_have_text("Casque JBL Tune 520 Pro")
    expect(recap.last.locator(".recap-format")).to_have_text("Carré 1:1")
    expect(recap.last.locator(".pic")).to_have_text(["Produit"])
    expect(recap.nth(-2).locator(".recap-format")).to_have_text("Publication 4:5")
    expect(recap.last.locator(".recap-price")).to_have_text(re.compile(r"^270\s000 Ar$"))
    assert scenes.count(kept["id"]) == 2 and page.evaluate(SCENE_JOBS, second) == 0, scenes
    # An open recap kept by an older client may predate a saved offer edit made elsewhere.
    page.evaluate("""id => {
      const key = 'affiche.shop1.chat.' + id, thread = JSON.parse(localStorage.getItem(key))
      thread.items.at(-1).card.price_ar = 1
      localStorage.setItem(key, JSON.stringify(thread))
    }""", second)
    page.reload(wait_until="domcontentloaded")
    expect(recap.last.locator(".recap-price")).to_have_text(re.compile(r"^270\s000 Ar$"))
    assert page.evaluate(SCENE_JOBS, second) == 0
    # A later correction in « Pas à pas » reaches the unpaid recap; spent cards stay as they were.
    switch.get_by_role("button", name="Pas à pas").click()
    page.wait_for_url(f"**/#{second}")
    before = revision()
    page.get_by_role("tab", name="Textes", exact=True).click()
    page.get_by_label("Prix en ariary", exact=True).fill("280 000")
    saved_after(before)
    switch.get_by_role("button", name="Message").click()
    expect(recap.last.locator(".recap-price")).to_have_text(re.compile(r"^280\s000 Ar$"))
    expect(recap.nth(-2).locator(".recap-price")).to_have_text(re.compile(r"^260\s000 Ar$"))
    # A refusal that a delivery still on its way could pass later (another scene is being made, here started from another
    # browser through the API) keeps the card, its request and its key, with the server's sentence and « Réessayer ».
    context.route("**/scenes", lambda route: route.abort("failed"))
    page.get_by_role("button", name="Créer l’affiche").click()
    expect(retry).to_be_visible()
    context.unroute("**/scenes")
    busy = spent()
    assert busy["request"]["body"]["format"] == "square"
    other = browser.new_context(storage_state=context.storage_state())
    headers = lambda: {"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE), "If-Match": f'"{revision()}"', "Idempotency-Key": str(uuid4())}
    plan = other.request.post(f"{smoke.ORIGIN}/api/creations/{second}/plans", headers=headers(), data={"mode": "fixed", "direction": "Studio clair", "format": "square"})
    assert plan.ok, plan.text()
    started = other.request.post(f"{smoke.ORIGIN}/api/creations/{second}/scenes", headers=headers(), data={"plan_id": plan.json()["id"], "format": "square"})
    assert started.status == 202, started.text()
    retry.click()
    expect(thread).to_contain_text("Une image est déjà en cours de préparation pour cette création.")
    expect(retry).to_be_visible()
    after = spent()
    assert after["id"] == busy["id"] and after["request"] == busy["request"] and "job" not in after and not after.get("done"), after
    assert scenes.count(busy["id"]) == 2, scenes  # sent, then sent again with the same key
    for _ in range(100):  # the other scene ends; it is the poster's first version, so the poster's revision moves on
        if not [job for job in other.request.get(f"{smoke.ORIGIN}/api/creations/{second}/jobs").json()["items"] if job["status"] in ("queued", "running")]:
            break
        page.wait_for_timeout(200)
    other.close()
    page.reload()
    expect(resume).to_be_visible()
    resume.click()
    expect(page.get_by_role("button", name="Créer l’affiche")).to_have_count(1)
    assert scenes.count(busy["id"]) == 3 and page.evaluate(SCENE_JOBS, second) == 1, scenes
    # The answer of the new card's request is lost and the page reloaded before the job is known: « Reprendre » sends the
    # kept request again with the same key, the server answers what it stored, and the job is followed. One job for it.
    stuck = []

    def lose_answer(route):
        route.fetch()  # the server has taken the request
        stuck.append(route)  # and the page never hears of it
    context.route("**/scenes", lose_answer)
    page.get_by_role("button", name="Créer l’affiche").click()
    for _ in range(100):
        if stuck:
            break
        page.wait_for_timeout(100)
    card = spent()
    assert card["request"] and "job" not in card and card["id"] != busy["id"], card
    page.reload()
    context.unroute("**/scenes")
    expect(resume).to_be_visible()
    expect(resume.locator("xpath=../..")).to_contain_text(ONCE)  # its cost, once
    expect(resume).to_have_accessible_description(ONCE)  # the visible once line is the button's description
    assert scenes.count(card["id"]) == 1, scenes
    resume.click()
    expect(page.get_by_role("button", name="Vérifier", exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_role("button", name="Créer l’affiche")).to_have_count(0)
    assert page.evaluate(SCENE_JOBS, second) == 2 and scenes.count(card["id"]) == 2, scenes
    adopted = spent()
    assert adopted["id"] == card["id"] and adopted.get("job"), adopted
    session = context.storage_state()
    context.close()
    return session


def walk_changes(browser, errors, session, data):
    """An existing poster is changed by message (T-CHAT-004): a new scene of it, a new price, the list of modifications.
    The poster is the first one of walk_desktop: one version, approved and downloaded."""
    reads, bodies, sent = [], [], {"refinements": [], "scenes": [], "plans": [], "revisions": [], "api/assets": []}

    def seen(request):
        if request.method != "POST":
            return
        if request.url.endswith("/api/reads"):
            reads.append(request.headers["idempotency-key"])
            bodies.append(request.post_data_json)
        for path in sent:
            if request.url.endswith("/" + path):
                sent[path].append(request.headers["idempotency-key"])

    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    context.on("request", seen)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: print(f"HTTP {response.status} {response.url}", flush=True) if response.status >= 400 else None)

    def open_poster():
        smoke.go(page, "Mes affiches")
        page.get_by_role("button", name=re.compile("Sony WH-1000XM6 noir")).first.click()
        page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
        page.get_by_role("button", name="Fermer").click()  # a confirmed poster opens on its file
    page.goto(smoke.ORIGIN + "/#creer")
    page.wait_for_url("**/#message")
    thread, field, side = page.get_by_role("log"), page.get_by_label("Votre message"), page.locator(".chat-side")
    # Photos already used (D-TEXT-FIRST-004): the same product named again, in other letters and without a photo, is
    # offered the photo of its first poster. One tap attaches it, with no upload and no second read, and the recap comes.
    say(page, "sony wh-1000xm6 NOIR, 500 000 Ar")
    asked = thread.locator(".bubble.bot").last
    expect(asked).to_contain_text("Il me faut une photo du produit.")
    offered = asked.get_by_role("button", name="Reprendre cette photo")
    expect(offered).to_have_count(1)  # the product photo, not the inspiration image
    expect(asked.get_by_role("button", name="Ajouter une photo")).to_be_visible()
    assert offered.locator("img").evaluate("e => e.decode().then(() => e.naturalWidth > 0)")
    looks_right(page, "photos already used", "chat-suggestions-1366.png")
    offered.click()
    recap = thread.locator(".bubble.bot", has=page.locator(".recap")).last
    expect(recap.locator(".recap b")).to_have_text("sony wh-1000xm6 NOIR")
    expect(recap.locator(".recap-price")).to_have_text(re.compile(r"^500\s000 Ar$"))
    expect(recap.locator(".pic")).to_have_count(1)
    expect(offered).to_have_count(0)
    expect(thread.get_by_role("button", name="Créer l’affiche")).to_be_enabled()
    assert len(reads) == 1 and not sent["api/assets"], (reads, sent)
    del reads[:]
    open_poster()
    poster = page.url.split("#message-")[1]
    create, cancel = thread.get_by_role("button", name="Créer", exact=True), thread.get_by_role("button", name="Annuler")
    redo = thread.get_by_role("button", name="Refaire l’affiche")
    verify, download = page.get_by_role("button", name="Vérifier", exact=True), page.get_by_role("button", name="Télécharger ou partager", exact=True)
    mods, toggle = side.locator(".mod"), side.get_by_role("button", name=re.compile("^Modifications"))
    items = lambda: page.evaluate(THREAD, poster)["items"]
    spent = lambda: [item for item in items() if item.get("spent")][-1]
    creation = lambda: page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}").json()
    versions = lambda: page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}/visuals").json()["items"]
    made = lambda kind: [job for job in page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}/jobs").json()["items"] if job["kind"] == kind]

    def selected(visual):  # the choice is saved by the editor's own saver
        for _ in range(50):
            if creation()["document"]["formats"]["feed"]["scene"]["visual_id"] == visual:
                return
            page.wait_for_timeout(200)
        raise AssertionError("the new version is not the poster's selected one")

    def arrived(number):
        expect(thread).to_contain_text(f"Version {number} prête.", timeout=30000)

    def approve():  # the newest version, the poster's: confirmed with its file. A version is approved only that way
        # (D-KIT-001): an older one still to check keeps its « Vérifier », and no longer speaks for the poster.
        left = verify.count()
        verify.last.click()
        expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
        smoke.download_review(page)
        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
        expect(verify).to_have_count(left - 1)
        expect(download.last).to_be_visible()  # on the selected version only

    expect(thread).to_contain_text("Dites ce qu’il faut changer")
    # Wide: the list of modifications is open under the poster, without its button.
    expect(toggle).to_be_hidden()
    expect(mods).to_have_count(1)
    expect(mods.first).to_have_text(re.compile(r"^V1\s*Première affiche\s*Confirmée$"))

    # A message on a poster is read for it; the answer is a card that says what will happen and what it costs.
    say(page, "fond plus sombre")
    card = thread.locator(".bubble.bot").last
    expect(card).to_contain_text("Scène : « fond plus sombre »")
    expect(card).to_contain_text(COST)
    # The warning, then the cost line under the buttons (D-REDESIGN-003).
    expect(create).to_have_accessible_description(COST)
    expect(card.get_by_text(WARNING, exact=True)).to_have_count(0)  # a scene's words alone do not warn (ADR-125)
    first = versions()[0]["id"]
    assert len(reads) == 1 and bodies[-1]["visual_id"] == first, (reads, bodies)  # the read names the version shown
    both_themes(page, "change card, desktop", "chat-change-1366")
    # « Annuler »: the words go back to the field, the card goes, nothing was asked for the poster.
    cancel.click()
    expect(create).to_have_count(0)
    expect(field).to_have_value("fond plus sombre")
    expect(field).to_be_focused()
    assert not sent["refinements"] and not sent["scenes"], sent
    page.get_by_role("button", name="Envoyer").click()
    expect(create).to_be_visible()
    assert len(reads) == 2 and reads[0] != reads[1], reads
    # The tap; the answer is lost and the page reloaded before the job is known. Nothing is sent by itself: « Reprendre »
    # sends the kept /refinements request again with the same key, and the server answers what it stored. One job.
    stuck = []

    def lose_answer(route):
        route.fetch()
        stuck.append(route)
    context.route("**/refinements", lose_answer)
    create.click()
    for _ in range(100):
        if stuck:
            break
        page.wait_for_timeout(100)
    kept = spent()
    assert kept["card"]["effect"] == "refine" and kept["card"]["visual_id"] == first and kept["request"]["path"] == f"/api/creations/{poster}/refinements" and "job" not in kept, kept
    assert kept["request"]["body"]["instruction_fr"] == "fond plus sombre" and kept["request"]["body"]["base_visual_id"] == first, kept
    page.reload()
    context.unroute("**/refinements")
    page.get_by_role("button", name="Fermer").click()
    resume = thread.get_by_role("button", name="Reprendre")
    expect(resume).to_be_visible()
    expect(resume.locator("xpath=../..")).to_contain_text(ONCE)
    expect(resume).to_have_accessible_description(ONCE)
    expect(resume.locator("xpath=../..").get_by_text(WARNING, exact=True)).to_have_count(0)  # restored from the device: still no features asked
    expect(page.get_by_role("button", name="Envoyer")).to_be_disabled()  # the waiting card comes first
    page.wait_for_timeout(500)
    assert sent["refinements"] == [kept["id"]], sent
    resume.click()
    arrived(2)
    assert sent["refinements"] == [kept["id"]] * 2 and len(made("refine")) == 1, sent
    # The new version is a result card like the first, and it is the poster's selected one.
    expect(side).to_contain_text("Version 2 · à vérifier")
    second = versions()[0]
    assert second["instruction_fr"] == "fond plus sombre" and versions()[1]["instruction_fr"] is None, second
    selected(second["id"])
    expect(download).to_have_count(0)  # the first version is no longer the selected one
    expect(mods).to_have_text([re.compile(r"^V2\s*fond plus sombre\s*À vérifier$"), re.compile(r"^V1\s*Première affiche\s*Confirmée$")])
    # A line of the list shows its version. Looking is free: the poster's choice does not move.
    mods.nth(1).click()
    expect(side).to_contain_text("Version 1 · confirmée")
    expect(mods.nth(1)).to_have_attribute("aria-current", "true")
    page.wait_for_timeout(1500)
    assert creation()["document"]["formats"]["feed"]["scene"]["visual_id"] == second["id"]
    mods.nth(0).click()
    expect(side).to_contain_text("Version 2 · à vérifier")
    both_themes(page, "second version, desktop", "chat-version2-1366")
    approve()
    expect(mods.first).to_contain_text("Confirmée")

    # A change is asked on the version the owner looks at (D-TEXT-FIRST-005): here the first one, while the second is
    # the poster's. Its price is drawn in the image: a whole new image, with its cost. At the tap that version becomes
    # the poster's, the card's words are set in the editor, and the new scene has the card's key.
    mods.nth(1).click()
    expect(side).to_contain_text("Version 1 · confirmée")
    say(page, "prix 650 000 Ar")
    card = thread.locator(".bubble.bot").last
    expect(card).to_contain_text(re.compile(r"Prix : 650\s000 Ar"))
    expect(card).to_contain_text(COST)
    expect(cancel).to_be_visible()
    assert bodies[-1]["visual_id"] == first, bodies[-1]
    redo.click()
    arrived(3)
    priced = spent()
    assert priced["card"]["effect"] == "scene" and priced["card"]["visual_id"] == first and "previous" not in priced["card"], priced
    assert priced["card"]["words"] == {"title": "Sony WH-1000XM6 noir", "brand": None, "subtitle": None, "price_ar": 650000}, priced
    assert sent["scenes"] == [priced["id"]] and priced["request"]["path"].endswith("/scenes"), (priced, sent)
    third = versions()[0]
    assert creation()["document"]["offer"]["price_ar"] == 650000 and third["headline"]["price_ar"] == 650000, third
    selected(third["id"])
    expect(side).to_contain_text(re.compile(r"Version 3 · à vérifier.*650\s000 Ar"))
    expect(mods.first).to_have_text(re.compile(r"^V3\s*Prix : 650\s000 Ar\s*À vérifier$"))

    # The user's report (ADR-099), in the stub reader's words, on a version still to check: the brand goes above the
    # title and leaves it. One card with one line per field, one new image to check, and its line in the list.
    say(page, "marque Sony")
    card = thread.locator(".bubble.bot").last
    lines = card.locator("p.lines")
    expect(lines).to_have_text(re.compile(r"^Titre : WH-1000XM6 noir\s+Marque : Sony\s+" + re.escape(REDRAW) + "$"))
    assert lines.evaluate("e => getComputedStyle(e).whiteSpace") == "pre-line" and "\n" in lines.evaluate("e => e.textContent")
    assert bodies[-1]["visual_id"] == third["id"], bodies[-1]
    looks_right(page, "words card, desktop", "chat-words-1366.png")
    redo.click()
    arrived(4)
    branded = spent()
    assert branded["request"]["body"]["headline"]["brand"] == "Sony" and branded["request"]["body"]["headline"]["subtitle"] is None, branded
    assert branded["request"]["body"]["keep_adjustments_of"] == third["id"], branded  # ADR-101: its scene adjustments are kept
    fourth = versions()[0]
    assert fourth["headline"]["title"] == "WH-1000XM6 noir" and fourth["headline"]["brand"] == "Sony" and fourth["headline"]["price_ar"] == 650000, fourth
    assert creation()["document"]["offer"]["title"] == "WH-1000XM6 noir"
    # The new image keeps the version's style (ADR-100): its plan is a revision of the plan of the version it replaces.
    plan_of = lambda visual: page.request.get(f"{smoke.ORIGIN}/api/plans/{visual['plan_id']}").json()
    assert plan_of(fourth)["parent_plan_id"] == third["plan_id"] and plan_of(fourth)["plan"]["palette"] == plan_of(third)["plan"]["palette"], (plan_of(fourth), third["plan_id"])
    selected(fourth["id"])
    expect(side).to_contain_text(re.compile(r"Version 4 · à vérifier\s*WH-1000XM6 noir · 650\s000 Ar"))
    expect(mods.first).to_have_text(re.compile(r"^V4\s*Titre : WH-1000XM6 noir · Marque : Sony\s*À vérifier$"))
    # The earlier V3 still to check: its review chooses it or refuses it, and never approves it apart from its file
    # (D-KIT-001). Closed, it changes nothing: V4 is still the export selection, and nothing is rendered.
    expect(verify).to_have_count(2)
    renders = len(made("render"))
    verify.first.click()
    historical = page.get_by_role("dialog", name=REVIEW)
    expect(historical.get_by_role("button", name="Choisir cette version")).to_be_visible()
    expect(historical.get_by_role("button", name="Signaler un problème")).to_be_visible()
    expect(historical.get_by_role("button", name="Tout est conforme, approuver")).to_have_count(0)
    historical.get_by_role("button", name="Fermer").click()
    expect(historical).to_have_count(0)
    selected(fourth["id"])
    assert len(made("render")) == renders
    approve()
    expect(verify).to_have_count(1)  # V3's, left to check

    # The card's words are saved in the document before the scene is asked. A reload between the two: nothing paid
    # left, a new card is offered, and the chat says what the image still shows, from the editor's own comparison.
    still, back = thread.locator(".why", has_text="L’affiche montre encore"), page.get_by_role("button", name="Remettre les textes de l’image")
    held_plans = []  # the version's plan, saved again at the new revision (ADR-100): held, so the scene never leaves
    context.route("**/plans/*/revisions", lambda route: held_plans.append(route))
    say(page, "titre WH-1000XM6 Pro")
    expect(thread.locator(".bubble.bot").last.locator("p.lines")).to_have_text(f"Titre : WH-1000XM6 Pro {REDRAW}")
    expect(still).to_have_count(0)
    redo.click()
    for _ in range(100):
        if held_plans:
            break
        page.wait_for_timeout(100)
    assert creation()["document"]["offer"]["title"] == "WH-1000XM6 Pro" and len(sent["scenes"]) == 2
    page.reload()
    context.unroute("**/plans/*/revisions")
    page.get_by_role("button", name="Fermer").click()
    # The leaving page may see its own plan request cut and say so itself; otherwise the next view finds nothing kept.
    expect(thread).to_contain_text(re.compile("Rien n’a été envoyé pour cette demande\\.|Connexion interrompue"))
    assert "request" not in spent() and len(sent["scenes"]) == 2, spent()
    expect(redo).to_have_count(1)
    expect(still).to_have_text("L’affiche montre encore : « WH-1000XM6 noir ».")
    expect(back).to_have_count(1)
    # The new scene is refused for good after the words were saved (here the server's own plan_stale: the request is
    # delivered with the plan of an older revision). The card is retired and a new one offered with its cost.
    def stale_plan(route):
        body = route.request.post_data_json
        route.continue_(post_data=json.dumps(body | {"plan_id": priced["request"]["body"]["plan_id"]}))
    context.route("**/scenes", stale_plan)
    redo.click()
    expect(thread).to_contain_text(PLAN_STALE)  # the server's sentence
    refused = spent()
    assert refused.get("done") and "job" not in refused and len(made("scene")) == 3, refused
    expect(redo).to_have_count(1)
    expect(back).to_have_count(1)
    # A later price card: the document then holds a title and a price that the image does not show. The line and
    # « Remettre les textes de l’image » are still there, on the newest card, whatever the cards before remembered.
    say(page, "prix 600 000 Ar")
    expect(thread.locator(".bubble.bot").last.locator("p.lines")).to_have_text(re.compile(r"^Titre : WH-1000XM6 Pro\s+Prix : 600\s000 Ar\s+" + re.escape(REDRAW) + "$"))
    expect(still).to_have_text("L’affiche montre encore : « WH-1000XM6 noir ».")
    redo.click()
    expect(still).to_have_text(re.compile(r"^L’affiche montre encore : « WH-1000XM6 noir », 650\s000 Ar\.$"))
    context.unroute("**/scenes")
    assert creation()["document"]["offer"] | {"currency": "MGA"} == {"title": "WH-1000XM6 Pro", "price_ar": 600000, "currency": "MGA"} and len(made("scene")) == 3
    stale = thread.locator(".bubble.bot").last
    expect(stale).to_contain_text(COST)
    expect(stale.get_by_role("button")).to_have_text(["Refaire l’affiche", "Annuler", "Remettre les textes de l’image"])
    both_themes(page, "the image still shows other words, desktop", "chat-stale-1366")
    # A mismatch in the drawn words blocks the new preview before rendering.
    before = len(made("render"))
    download.click()
    refusal = page.get_by_role("dialog", name="Préparation de l’aperçu")
    expect(refusal).to_contain_text("Un texte dessiné dans l’image a changé")
    assert len(made("render")) == before
    looks_right(page, "download refused, desktop")
    refusal.get_by_role("button", name="Fermer").click()
    # The same after a reload: nothing of it is kept on a card.
    page.reload()
    page.get_by_role("button", name="Fermer").click()
    expect(still).to_have_count(1)
    back.click()
    expect(thread).to_contain_text("Les textes de l’image sont remis.")
    expect(still).to_have_count(0)
    expect(back).to_have_count(0)
    for _ in range(50):
        if creation()["document"]["offer"]["price_ar"] == 650000:
            break
        page.wait_for_timeout(200)
    assert creation()["document"]["offer"]["title"] == "WH-1000XM6 noir" and creation()["document"]["offer"]["price_ar"] == 650000
    expect(download).to_have_count(1)  # the approved version shows the poster's words again
    # The card is still the one that was read: its tap sets its words again and pays once, with its own key.
    redo.click()
    arrived(5)
    again = spent()
    assert again["id"] != refused["id"] and sent["scenes"][-1] == again["id"] and sent["scenes"].count(again["id"]) == 1 and len(made("scene")) == 4, (again, sent)
    fifth = versions()[0]
    assert fifth["headline"]["title"] == "WH-1000XM6 Pro" and fifth["headline"]["brand"] == "Sony" and fifth["headline"]["price_ar"] == 600000, fifth
    selected(fifth["id"])
    expect(mods.first).to_have_text(re.compile(r"^V5\s*Titre : WH-1000XM6 Pro · Prix : 600\s000 Ar\s*À vérifier$"))
    looks_right(page, "five versions, desktop", "chat-mods-1366.png")
    approve()

    # An unsaved edit of « Pas à pas » is saved before a message is read (the reader takes the stored poster). A save
    # that fails keeps the message in the composer with the editor's sentence, and nothing is read.
    switch, send = page.get_by_role("group", name="Façon de créer"), page.get_by_role("button", name="Envoyer")
    switch.get_by_role("button", name="Pas à pas").click()
    page.wait_for_url(f"**/#{poster}")
    context.route(f"**/api/creations/{poster}", lambda route: route.abort("failed") if route.request.method == "PUT" else route.continue_())
    page.get_by_label("Prix en ariary", exact=True).fill("590 000")
    page.locator("input[name=subtitle]").fill("Brouillon jamais dessiné")  # typed for a next version, never drawn
    switch.get_by_role("button", name="Message").click()
    page.wait_for_url(f"**/#message-{poster}")
    count = len(reads)
    field.fill("titre WH-1000XM6 Max")
    send.click()
    expect(page.locator(".message.error")).to_be_visible()
    expect(field).to_have_value("titre WH-1000XM6 Max")
    expect(thread.locator(".bubble.me").last).not_to_have_text("titre WH-1000XM6 Max")
    assert len(reads) == count and creation()["document"]["offer"]["price_ar"] == 600000, reads
    for width, height in ((360, 480), (1366, 768)):
        page.set_viewport_size({"width": width, "height": height})
        expect(send).to_be_in_viewport(ratio=1)
        send.click(trial=True)  # the visible save error must leave the composer reachable
    context.unroute(f"**/api/creations/{poster}")
    page.locator(".message.error").get_by_role("button", name="Fermer").press("Enter")
    expect(field).to_be_focused()
    send.click()
    # The card is read against the saved poster: the price typed in « Pas à pas » is one of its lines.
    expect(thread.locator(".bubble.bot").last.locator("p.lines")).to_have_text(re.compile(r"^Titre : WH-1000XM6 Max\s+Prix : 590\s000 Ar\s+" + re.escape(REDRAW) + "$"))
    assert len(reads) == count + 1 and creation()["document"]["offer"]["price_ar"] == 590000, reads
    # The image is asked with the card's words only: the subtitle typed in « Pas à pas » is not in the request.
    redo.click()
    arrived(6)
    assert spent()["request"]["body"]["headline"]["subtitle"] is None and versions()[0]["headline"].get("subtitle") is None, spent()
    selected(versions()[0]["id"])
    approve()
    say(page, "sous-titre Casque sans fil")
    expect(thread.locator(".bubble.bot").last.locator("p.lines")).to_have_text(f"Sous-titre : Casque sans fil {REDRAW}")
    redo.click()
    arrived(7)
    seventh = versions()[0]
    assert seventh["headline"]["subtitle"] == "Casque sans fil", seventh
    selected(seventh["id"])
    expect(mods.first).to_have_text(re.compile(r"^V7\s*Sous-titre : Casque sans fil\s*À vérifier$"))
    approve()

    # A card from before D-TEXT-FIRST-005 that holds its kept request (here the last one, put back as it was stored
    # then): shown in today's shape, and « Reprendre » sends the request exactly as it left, with the card's key.
    old = spent()
    page.evaluate("""([key, id]) => { const thread = JSON.parse(localStorage.getItem(key))
      const item = thread.items.find(item => item.id === id); delete item.job; delete item.done
      item.card = { kind: 'change', change: 'price', price_ar: 590000, previous: 600000, said: 'prix 590 000 Ar' }
      localStorage.setItem(key, JSON.stringify(thread)) }""", [f"affiche.shop1.chat.{poster}", old["id"]])
    page.reload()
    page.get_by_role("button", name="Fermer").click()
    expect(resume).to_be_visible()
    replayed = []
    context.on("request", lambda request: replayed.append(request.post_data_json) if request.method == "POST" and request.url.endswith("/scenes") else None)
    resume.click()
    expect(thread.locator(".bubble.bot", has_text="Version 7 prête.")).to_have_count(2)
    restored = [item for item in items() if item["id"] == old["id"]][0]
    assert restored["card"] == {"kind": "change", "words": {"price_ar": 590000}, "said": "prix 590 000 Ar"} and restored["request"] == old["request"], restored
    assert replayed == [old["request"]["body"]] and sent["scenes"][-1] == old["id"] and len(made("scene")) == 6, (replayed, sent)
    selected(seventh["id"])
    # An answer stored before the upgrade, received after it (the server replays it as it was stored): its old shape is
    # converted where it enters. A price drawn in the selected version: a whole new image, as it was then.
    def old_answer(card):
        context.route("**/api/reads", lambda route: route.fulfill(status=201, json={"card": card, "draft": {"name": None, "price_ar": None, "style": None}}))
    old_answer({"kind": "change", "change": "price", "price_ar": 550000, "text_fr": "Le prix est dessiné dans l’image : je refais l’affiche avec 550 000 Ar. L’actuelle reste gardée."})
    say(page, "prix 550 000 Ar")
    card = thread.locator(".bubble.bot").last
    expect(card).to_contain_text("je refais l’affiche avec 550 000 Ar")
    expect(card.get_by_role("button")).to_have_text(["Refaire l’affiche", "Annuler"])
    expect(card).to_contain_text(COST)
    expect(card).not_to_contain_text(WARNING)  # a whole new scene sends no adjustment
    assert items()[-1]["card"] == {"kind": "change", "words": {"price_ar": 550000}, "said": "prix 550 000 Ar"}, items()[-1]
    cancel.click()
    context.unroute("**/api/reads")
    old_answer({"kind": "change", "change": "scene", "instruction_fr": "fond bleu", "text_fr": "Nouvelle version : « fond bleu ». L’actuelle reste gardée."})
    page.get_by_role("button", name="Envoyer").click()
    card = thread.locator(".bubble.bot").last
    expect(card.get_by_role("button")).to_have_text(["Créer", "Annuler"])
    assert items()[-1]["card"]["effect"] == "refine" and "change" not in items()[-1]["card"], items()[-1]
    cancel.click()
    context.unroute("**/api/reads")
    field.fill("")

    # « Textes dans l’image » switched off in « Pas à pas » after the version was made: the request would not carry the
    # words the card lists. The tap is refused with its sentence; nothing is sent, nothing is spent.
    def texts(on):
        switch.get_by_role("button", name="Pas à pas").click()
        page.wait_for_url(f"**/#{poster}")
        page.get_by_label("Dessiner les textes dans l’image").set_checked(on)
        switch.get_by_role("button", name="Message").click()
        page.wait_for_url(f"**/#message-{poster}")
    texts(False)
    say(page, "sans sous-titre")
    expect(thread.locator(".bubble.bot").last.locator("p.lines")).to_have_text(f"Sous-titre : retiré {REDRAW}")
    count = len(sent["scenes"])
    redo.click()
    expect(thread).to_contain_text("Les textes dessinés sont désactivés pour cette affiche : réglez-les dans Pas à pas.")
    expect(redo).to_have_count(1)  # the same card again, once the texts are back
    page.wait_for_timeout(500)
    assert len(sent["scenes"]) == count and len(made("scene")) == 6 and "request" not in spent(), sent
    texts(True)
    redo.click()
    arrived(8)
    eighth = versions()[0]
    assert eighth["headline"].get("subtitle") is None and eighth["headline"]["brand"] == "Sony" and len(made("scene")) == 7, eighth
    selected(eighth["id"])
    expect(mods.first).to_have_text(re.compile(r"^V8\s*Sous-titre : retiré\s*À vérifier$"))

    # The chat is taken by another tab while a card's version is being selected: this tab changes nothing more and
    # sends nothing. The card is read for the second version, which this tab's list no longer has (its listing is
    # answered without it), so the selection waits for a fresh listing; the other tab takes the chat meanwhile.
    def without_second(route):
        response = route.fetch()
        route.fulfill(response=response, json={"items": [item for item in response.json()["items"] if item["id"] != second["id"]]})
    context.route("**/creations/*/visuals", without_second)
    page.reload()
    page.get_by_role("button", name="Fermer").click()
    expect(mods).to_have_count(7)
    context.unroute("**/creations/*/visuals")
    context.route("**/api/reads", lambda route: route.continue_(post_data=json.dumps(route.request.post_data_json | {"visual_id": second["id"]})))
    say(page, "fond rouge, écris ses caractéristiques")
    expect(create).to_be_visible()
    context.unroute("**/api/reads")
    assert items()[-1]["card"]["visual_id"] == second["id"], items()[-1]
    listing = []
    # Only this tab's listing is held, and until the chat is taken: removing the route would let it through.
    context.route("**/creations/*/visuals", lambda route: route.continue_() if listing else listing.append((route, route.fetch())))
    create.click()
    for _ in range(100):
        if listing:
            break
        page.wait_for_timeout(100)
    other_tab = context.new_page()
    other_tab.set_default_timeout(10000)
    other_tab.on("pageerror", lambda error: errors.append(str(error)))
    other_tab.goto(f"{smoke.ORIGIN}/#message-{poster}")
    other_tab.get_by_role("button", name="Fermer").click()  # a confirmed poster opens on its file
    other_tab.get_by_role("button", name="Continuer ici").click()
    expect(page.get_by_text("Le chat est ouvert dans un autre onglet.")).to_be_visible()
    assert len(listing) == 1 and not sent["refinements"][2:], (listing, sent)
    listing[0][0].fulfill(response=listing[0][1])  # the fresh listing arrives: the version is there, the chat is not
    context.unroute("**/creations/*/visuals")
    expect(other_tab.get_by_role("log")).to_contain_text("Rien n’a été envoyé pour cette demande.")
    page.wait_for_timeout(1500)
    assert creation()["document"]["formats"]["feed"]["scene"]["visual_id"] == eighth["id"] and len(sent["refinements"]) == 2, sent
    other_tab.close()
    page.get_by_role("button", name="Continuer ici").click()
    expect(create).to_have_count(1)
    expect(thread.get_by_text(WARNING, exact=True)).to_have_count(1)  # refused, offered again: the new card warns, the old one is done
    expect(create.locator("xpath=../..").get_by_text(WARNING, exact=True)).to_be_visible()
    cancel.click()
    field.fill("")

    # The chat is taken while the card's words are being saved (code review r2 of T-CHAT-007): once the save is back,
    # this tab asks no plan and no scene. The price is saved (it left before the chat was taken); the image's is put back.
    say(page, "480 000 Ar")
    expect(redo).to_be_visible()
    plans, scenes, saves = len(sent["plans"]) + len(sent["revisions"]), len(sent["scenes"]), []
    hold_save = lambda route: route.continue_() if saves or route.request.method != "PUT" else saves.append((route, route.fetch()))
    context.route(f"**/api/creations/{poster}", hold_save)
    redo.click()
    for _ in range(100):
        if saves:
            break
        page.wait_for_timeout(100)
    assert saves, "the words were not saved before the scene"
    other_tab = context.new_page()
    other_tab.set_default_timeout(10000)
    other_tab.on("pageerror", lambda error: errors.append(str(error)))
    other_tab.goto(f"{smoke.ORIGIN}/#message-{poster}")
    other_tab.get_by_role("button", name="Fermer").click()
    other_tab.get_by_role("button", name="Continuer ici").click()
    expect(page.get_by_text("Le chat est ouvert dans un autre onglet.")).to_be_visible()
    saves[0][0].fulfill(response=saves[0][1])
    context.unroute(f"**/api/creations/{poster}")
    page.wait_for_timeout(1500)
    assert (len(sent["plans"]) + len(sent["revisions"]), len(sent["scenes"])) == (plans, scenes), sent
    other_tab.close()
    page.get_by_role("button", name="Continuer ici").click()
    expect(redo).to_have_count(1)
    page.get_by_role("button", name="Remettre les textes de l’image").click()
    expect(page.get_by_role("button", name="Remettre les textes de l’image")).to_have_count(0)
    cancel.click()
    field.fill("")

    # One unresolved paid card at a time (finding 1). A refinement's answer is lost; the version it started from is then
    # refused in the review. No new paid card is offered while the first waits: its « Reprendre » only. Once it has
    # its version, the card for the refused one comes.
    stuck.clear()
    context.route("**/refinements", lose_answer)
    say(page, "lumière plus chaude")
    create.click()
    for _ in range(100):
        if stuck:
            break
        page.wait_for_timeout(100)
    waiting = spent()
    page.reload()
    context.unroute("**/refinements")
    page.get_by_role("button", name="Fermer").click()
    expect(resume).to_be_enabled()
    verify.last.click()  # the eighth version, still to check (V3's is still there, D-KIT-001)
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Signaler un problème").click()
    page.locator("textarea[name=rejection]").fill("Le fond ne va pas")
    page.get_by_role("button", name="Refuser cette version").click()
    expect(page.get_by_role("heading", name=FINAL)).to_have_count(0)
    expect(thread.locator(".chat-state.rejected")).to_have_count(1)
    page.wait_for_timeout(500)
    paid_buttons = thread.get_by_role("button", name=re.compile("^(Créer|Créer l’affiche|Refaire l’affiche|Réessayer)$"))
    expect(paid_buttons).to_have_count(0)
    expect(thread).not_to_contain_text("Version refusée.")
    expect(page.get_by_role("button", name="Envoyer")).to_be_disabled()
    resume.click()
    arrived(9)
    expect(thread).to_contain_text("Version refusée. Je peux en refaire une.")
    expect(thread.get_by_role("button", name="Créer l’affiche")).to_have_count(1)
    assert sent["refinements"].count(waiting["id"]) == 2 and len(made("refine")) == 2 and len(made("scene")) == 7, sent
    ninth = versions()[0]
    selected(ninth["id"])
    # What the chat cannot do on a poster is said by the server's card, with the way to the steps.
    say(page, "change le titre")
    expect(thread.locator(".bubble.bot").last).to_contain_text("Dites ce qu’il faut changer : le titre, la marque, le sous-titre, le prix, l’image (fond, lumière, logo, caractéristiques, mise en scène), le style.")
    expect(thread.locator(".bubble.bot").last.get_by_role("button", name="Pas à pas")).to_be_visible()

    # The one pending read is never replaced (finding 2). Its answer is lost on this poster; on another poster nothing
    # can be sent, the composer says why and leads back; there « Réessayer » is the same request, with the same key.
    context.route("**/api/reads", lambda route: route.abort("failed"))
    say(page, "fond bleu nuit")
    expect(thread.locator(".bubble.bot").last).to_contain_text("Connexion interrompue")
    lost = page.evaluate(PENDING)
    assert lost == reads[-1]

    def open_other():
        smoke.go(page, "Mes affiches")
        page.get_by_role("button", name=re.compile("Casque JBL")).first.click()
        page.wait_for_url(re.compile(r"#message-(?!%s)[a-f0-9-]{36}$" % poster))
    open_other()
    other = page.url.split("#message-")[1]
    field.fill("prix 290 000 Ar")
    expect(send).to_be_disabled()
    waits = page.locator(".chat-elsewhere-read")
    expect(waits).to_contain_text("Un message attend encore sur une autre affiche.")
    looks_right(page, "a message waits on another poster", "chat-read-elsewhere-1366.png")
    count = len(reads)
    waits.get_by_role("button", name="Ouvrir cette affiche").click()
    page.wait_for_url(f"**/#message-{poster}")
    page.get_by_role("button", name="Fermer").click()
    expect(waits).to_have_count(0)
    context.unroute("**/api/reads")
    thread.get_by_role("button", name="Réessayer", exact=True).click()
    expect(thread.locator(".bubble.bot").last).to_contain_text("Scène : « fond bleu nuit »")
    assert len(reads) == count + 1 and reads[-1] == lost and page.evaluate(PENDING) is None, reads
    cancel.click()

    # A poster whose selected version has no drawn words (made through the API): its title and price are layers, so
    # they change without a new image. The card has no cost, « Changer » is the editor's own edit, and no job is made.
    open_other()
    expect(waits).to_have_count(0)
    before = page.request.get(f"{smoke.ORIGIN}/api/creations/{other}/jobs").json()["items"]
    document = lambda: page.request.get(f"{smoke.ORIGIN}/api/creations/{other}").json()["document"]
    other_format = document()["primary_format"]
    chosen = document()["formats"][other_format]["scene"]["visual_id"]
    drawn = [item for item in page.request.get(f"{smoke.ORIGIN}/api/creations/{other}/visuals").json()["items"] if item["id"] == chosen][0]["headline"]
    assert drawn is None, drawn
    change, scenes = thread.get_by_role("button", name="Changer", exact=True), len(sent["scenes"])

    def changed(field, value):
        expect(thread).to_contain_text("C’est changé sur l’affiche.")
        expect(card.get_by_role("button")).to_have_count(0)
        for _ in range(50):
            if document()["offer"][field] == value:
                break
            page.wait_for_timeout(200)
        assert document()["offer"][field] == value and document()["formats"][other_format]["scene"]["visual_id"] == chosen
        assert page.request.get(f"{smoke.ORIGIN}/api/creations/{other}/jobs").json()["items"] == before and len(sent["scenes"]) == scenes, sent
    say(page, "titre Casque JBL Tune 520 Max")
    card = thread.locator(".bubble.bot").last
    expect(card.locator("p.lines")).to_have_text("Titre : Casque JBL Tune 520 Max")
    expect(card).not_to_contain_text("crédit")  # a free change says no cost
    expect(card.get_by_role("button")).to_have_text(["Changer", "Annuler"])
    expect(card.get_by_role("button", name="Changer")).not_to_have_attribute("aria-describedby", re.compile("."))
    looks_right(page, "free title change", "chat-free-title-1366.png")
    change.click()
    changed("title", "Casque JBL Tune 520 Max")
    # A price card from before D-TEXT-FIRST-005 (its stored answer, received now) is still free on such a poster.
    old_answer({"kind": "change", "change": "price", "price_ar": 290000, "text_fr": "Le prix est dessiné dans l’image : je refais l’affiche avec 290 000 Ar. L’actuelle reste gardée."})
    say(page, "prix 290 000 Ar")
    context.unroute("**/api/reads")
    card = thread.locator(".bubble.bot").last
    expect(card).to_contain_text(re.compile(r"Je change le prix sur l’affiche : 290\s000 Ar\."))
    expect(card).not_to_contain_text("crédit")
    expect(card).not_to_contain_text("dessiné dans l’image")
    expect(create).to_have_count(0)
    looks_right(page, "free price change", "chat-free-price-1366.png")
    change.click()
    changed("price_ar", 290000)
    assert not [item for item in page.evaluate(THREAD, other)["items"] if item.get("card", {}).get("kind") == "change" and item.get("spent")]
    # A brand exists only as drawn words: on this poster the server's card leads to the steps.
    say(page, "marque JBL")
    card = thread.locator(".bubble.bot").last
    expect(card).to_contain_text("Cette affiche n’a pas de textes dessinés dans l’image : la marque et le sous-titre se règlent dans Pas à pas.")
    expect(card.get_by_role("button")).to_have_text(["Pas à pas"])

    # The version limit, by the server's rule: jobs are added straight into the temporary database.
    def seed(count):
        with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
            source = store.execute("SELECT id FROM poster_jobs WHERE creation_id=? AND kind='scene' AND status='succeeded'", (other,)).fetchone()[0]
            for _ in range(count):
                columns = ("shop_id,creation_id,origin_revision,input_id,kind,input_json,input_hash,status,result_ref,error_code,"
                           "created_at,started_at,finished_at,recovery_count")
                store.execute(f"INSERT INTO poster_jobs (id,{columns}) SELECT ?,{columns} FROM poster_jobs WHERE id=?",
                              (str(uuid4()), source))
    counted = len([job for job in before if job["kind"] in ("scene", "refine") and job["status"] in ("queued", "running", "succeeded")])
    say(page, "fond plus sombre")
    card = thread.locator(".bubble.bot").last
    expect(create).to_be_visible()
    expect(card).not_to_contain_text("Il reste")
    for add, line in ((10 - counted, "Il reste 2 versions pour cette affiche."), (1, "Il reste 1 version pour cette affiche.")):
        seed(add)
        page.reload()
        expect(card).to_contain_text(line)
        expect(create).to_be_enabled()
    seed(1)
    page.reload()
    expect(card).to_contain_text("Douze scènes ont déjà été demandées pour cette affiche.")
    expect(create).to_have_count(0)
    expect(cancel).to_be_visible()
    looks_right(page, "version limit reached", "chat-limit-1366.png")

    # The session ends (401): the sign-in form comes instead of a dead end. The sign-in loads the shop fresh, at its
    # start view and without the poster's address (D-MULTI-SHOP-007 rules 3 and 4); the poster's thread is there and
    # « Réessayer » sends the message.
    context.clear_cookies()
    say(page, "fond rouge")
    expect(page.locator("main:not(.gate)")).to_have_count(0)  # signed out: the shop's screen leaves (D-REDESIGN-002 r1)
    page.get_by_label("Identifiant de la boutique", exact=True).fill(smoke.IDENTIFIER)
    page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
    page.get_by_role("button", name="Ouvrir l’atelier").click()
    page.wait_for_url("**/#accueil")
    page.goto(f"{smoke.ORIGIN}/#message-{other}")
    # The chat left the page with the session (D-REDESIGN-002 r1, 2); its card says why all the same.
    expect(thread.locator(".bubble.bot").last).to_contain_text("Connectez-vous pour continuer.")
    expect(thread.get_by_text("L’envoi a été interrompu.")).to_have_count(0)
    thread.get_by_role("button", name="Réessayer", exact=True).click()
    expect(thread.locator(".bubble.bot").last).to_contain_text("Scène : « fond rouge »")
    state = context.storage_state()
    context.close()

    # 360 px: the list is folded behind « Modifications (n) » beside the small poster.
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark", storage_state=state)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN + "/#creer")
    page.wait_for_url("**/#message")
    smoke.go(page, "Mes affiches", tap=True)
    page.get_by_role("button", name=re.compile("WH-1000XM6 Max")).first.tap()  # the title a message gave it
    page.wait_for_url(f"**/#message-{poster}")
    page.get_by_role("button", name="Fermer", exact=True).tap()  # not « Fermer le menu », whose drawer is closing
    side = page.locator(".chat-side")
    mods, toggle = side.locator(".mod"), side.get_by_role("button", name="Modifications (9)")
    expect(side).to_contain_text("Version 9 · à vérifier")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(mods.first).to_be_hidden()
    looks_right(page, "list folded, 360 px", "chat-mods-folded-360.png")
    # The folded list is reached and opened with the keyboard alone.
    toggle.focus()
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Tab")
    expect(mods.first).to_be_focused()
    expect(mods).to_have_count(9)
    expect(mods.nth(0)).to_have_text(re.compile(r"^V9\s*lumière plus chaude\s*À vérifier$"))
    expect(mods.nth(1)).to_have_text(re.compile(r"^V8\s*Sous-titre : retiré\s*Refusée$"))
    expect(mods.nth(5)).to_have_text(re.compile(r"^V4\s*Titre : WH-1000XM6 noir · Marque : Sony\s*Confirmée$"))  # cut with « … », on one line
    expect(mods.nth(7)).to_have_text(re.compile(r"^V2\s*fond plus sombre\s*Confirmée$"))
    mods.nth(7).scroll_into_view_if_needed()
    box = mods.nth(7).bounding_box()
    assert box["height"] >= 44 and box["x"] >= 0 and box["x"] + box["width"] <= 360, box
    mods.nth(7).tap()
    expect(side).to_contain_text("Version 2 · confirmée")
    expect(mods.nth(7)).to_have_attribute("aria-current", "true")
    # No bottom bar in the chat (D-REDESIGN-002): the composer ends inside the visible screen with the list open.
    expect(page.locator(".phone-bar")).to_have_count(0)
    composer = page.locator(".composer").bounding_box()
    assert composer["y"] + composer["height"] <= page.evaluate("visualViewport.height"), "the composer stays in view with the list open"
    both_themes(page, "list of modifications, 360 px", "chat-mods-360")
    context.close()


def walk_uploads(browser, errors, session, small, broken, animated):
    """Images the chat cannot take, and a small product photo: each refusal says what to do, nothing is a dead end."""
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN + "/#creer")
    page.wait_for_url("**/#message")
    thread, picker, send = page.get_by_role("log"), page.locator(".composer input[type=file]"), page.get_by_role("button", name="Envoyer")
    pics, alert, notice = page.locator(".tray .pic"), page.locator(".composer .why"), page.locator(".message.notice")
    # « Entrée » while a photo is still on its way (T-KIT-018): the send is kept, the field is held as it was and a line
    # says why; nothing has left yet. The photo taken out drops the wish and gives the field back.
    kept = []
    page.route("**/api/assets", lambda route: kept.append(route))
    picker.set_input_files(small[0])
    field = page.get_by_label("Votre message")
    field.fill("Montre Casio F91, 90 000 Ar")
    field.press("Enter")
    expect(page.locator(".composer").get_by_text("Envoi dès que la photo est prête…")).to_be_visible()
    expect(field).not_to_be_editable()
    expect(field).to_have_value("Montre Casio F91, 90 000 Ar")
    expect(thread.locator(".bubble.me")).to_have_count(0)
    page.get_by_role("button", name="Retirer cette image").click()
    expect(page.locator(".composer").get_by_text("Envoi dès que la photo est prête…")).to_have_count(0)
    expect(field).to_be_editable()
    for route in kept:  # before the route is lifted: lifting it answers what it still holds
        route.abort()
    page.unroute("**/api/assets")
    field.fill("")
    # Not an image, then an animated one: the server's sentence under the tray, « Envoyer » waits, the image can be removed.
    for file, sentence in ((broken, "Utilisez une image JPEG, PNG ou WebP fixe."), (animated, "Les images animées ne sont pas acceptées.")):
        picker.set_input_files(file)
        expect(alert).to_contain_text(sentence)
        expect(pics.get_by_role("button", name="Réessayer")).to_be_visible()
        page.get_by_label("Votre message").fill("Montre Casio F91, 90 000 Ar")
        expect(send).to_be_disabled()
        page.get_by_role("button", name="Retirer cette image").click()
        expect(pics).to_have_count(0)
        expect(alert).to_have_count(0)
    # Five images at once: three product photos, the fourth can only be the style model and is taken as one (a pack of
    # three with a reference poster), the fifth is not taken and that is said. A role that has no room is not given.
    picker.set_input_files(small)
    expect(pics).to_have_count(4)
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    expect(pics.locator(".pic-role")).to_have_text(["Produit", "Produit", "Produit", "Modèle de style"])
    expect(notice).to_contain_text("Trois photos du produit et un modèle de style au plus.")
    looks_right(page, "fifth photo refused", "chat-fourth-photo-1366.png")
    # The notice can expire during screenshot capture. Clear it before testing the next refusal.
    notice.get_by_role("button", name="Fermer").evaluate_all("buttons => buttons[0]?.click()")
    expect(notice).to_have_count(0)
    pics.nth(3).locator(".pic-role").click()  # the style model as a fourth product photo
    expect(pics.nth(3).locator(".pic-role")).to_have_text("Modèle de style")
    expect(notice).to_contain_text("Trois photos du produit et un modèle de style au plus.")
    notice.get_by_role("button", name="Fermer").click()
    for _ in range(3):
        page.get_by_role("button", name="Retirer cette image").last.click()
    expect(pics).to_have_count(1)
    # A small product photo: the recap asks the agreement before the paid tap.
    send.click()
    create, agree = page.get_by_role("button", name="Créer l’affiche"), thread.get_by_label(re.compile("^La photo du produit est petite"))
    expect(create).to_be_disabled()
    looks_right(page, "small photo", "chat-small-photo-1366.png")
    agree.check()
    create.click()
    expect(page.get_by_role("button", name="Vérifier", exact=True)).to_be_visible(timeout=30000)
    context.close()


def walk_phone(browser, errors, session):
    """360 px with a touch pointer, then the height the keyboard leaves: the composer and « Envoyer » stay in view."""
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN + "/#creer")
    page.wait_for_url("**/#message")
    chat, composer = page.locator(".chat"), page.locator(".composer")
    # The visible area (visualViewport): with a keyboard open, innerHeight can stay taller than what is seen.
    in_view = "() => { const box = document.querySelector('.composer').getBoundingClientRect(), seen = visualViewport.offsetTop + visualViewport.height; return box.bottom <= seen && box.top > visualViewport.offsetTop }"
    expect(chat).to_be_visible()
    expect(page.locator(".chat-side")).to_have_count(0)
    header = page.locator(".app-header").bounding_box()
    assert header["height"] <= 64, header  # the menu, the switch, « Nouvelle affiche » and the credits on one line
    # No bottom bar in the chat (D-REDESIGN-002): the composer takes its place, inside the visible screen.
    expect(page.locator(".phone-bar")).to_have_count(0)
    page.wait_for_function(in_view)
    both_themes(page, "chat, 360 px", "chat-360")
    # The keyboard: the visible height shrinks, the field has the focus.
    page.set_viewport_size({"width": 360, "height": 420})
    page.get_by_label("Votre message").tap()
    expect(page.locator(".phone-bar")).to_have_count(0)
    expect(page.locator(".style-row")).to_be_hidden()
    page.wait_for_function(in_view)
    send = page.get_by_role("button", name="Envoyer").bounding_box()
    assert send["y"] + send["height"] <= 420, send
    looks_right(page, "chat with the keyboard, 360 px", "chat-360-keyboard.png")
    # A poster made by message, on the phone: the strip on top, the thread under it.
    page.set_viewport_size({"width": 360, "height": 740})
    page.get_by_label("Votre message").blur()
    page.wait_for_function(in_view)
    smoke.go(page, "Mes affiches", tap=True)
    page.get_by_role("button", name=re.compile("Sony WH-1000XM6 noir")).first.tap()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    page.get_by_role("button", name="Fermer", exact=True).tap()  # not « Fermer le menu », whose drawer is closing
    side, thread = page.locator(".chat-side"), page.get_by_role("log")
    expect(side).to_contain_text("Version 1 · confirmée")
    assert side.bounding_box()["y"] + side.bounding_box()["height"] <= thread.bounding_box()["y"], "phone: the strip is above the thread"
    both_themes(page, "poster in the chat, 360 px", "chat-poster-360")
    # In « Pas à pas » the phone's editor bar stands for the header: it holds the way back to the chat.
    poster = page.url.split("#message-")[1]
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Pas à pas").tap()
    page.wait_for_url(f"**/#{poster}")
    expect(page.locator(".editor .poster-canvas canvas").first).to_be_visible()
    expect(page.locator(".app-header")).to_be_hidden()
    # The editor mounted again after the chat measures its poster: the enlarged view fits the screen.
    page.get_by_role("button", name="Voir l’affiche").first.tap()
    enlarged = page.locator(".stage.peek .poster-canvas").bounding_box()
    assert enlarged["x"] >= 0 and enlarged["x"] + enlarged["width"] <= 360, enlarged
    page.get_by_role("button", name="Revenir aux réglages").tap()
    back = page.get_by_role("button", name="Continuer par message")
    box = back.bounding_box()
    assert box["width"] >= 44 and box["height"] >= 44 and box["x"] + box["width"] <= 360, box
    assert page.evaluate(smoke.NO_SIDEWAYS)
    smoke.check_one_blur(page, "editor bar with the way back, 360 px")
    page.screenshot(path=str(OUT / "editor-bar-360.png"))
    back.tap()
    page.wait_for_url(f"**/#message-{poster}")
    expect(chat).to_be_visible()
    context.close()


def walk_layout(browser, errors, session, product):
    """D-REDESIGN-003: where the welcome and the composer sit, empty and after the first message, at 1440 and 360 px; the
    tool row; the recap's cells; the cost beside its button on a phone; the side panel's surface at 1241 px."""
    box = lambda page, selector: page.locator(selector).first.bounding_box()
    bottom = lambda b: b["y"] + b["height"]
    tops = ".recap > *", "es => es.map(e => Math.round(e.getBoundingClientRect().top))"

    def open_chat(width, height):
        context = browser.new_context(viewport={"width": width, "height": height}, is_mobile=width < 720, has_touch=width < 720,
                                      color_scheme="light", storage_state=session)
        page = context.new_page()
        page.set_default_timeout(10000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(smoke.ORIGIN + "/#creer")
        page.wait_for_url("**/#message")
        expect(page.locator(".hello-q")).to_have_text("Quel produit vendez-vous ?")
        expect(page.locator(".hello")).to_contain_text("Le format Publication est déjà choisi")
        expect(page.get_by_role("button", name="Ajouter des photos").get_by_text("Photos", exact=True)).to_be_visible()
        return context, page

    def first_message(page, text):
        page.locator(".composer input[type=file]").set_input_files([product])
        expect(page.locator(".tray .pic")).to_have_count(1)
        expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
        say(page, text)
        card = page.get_by_role("log").locator(".bubble.bot", has=page.locator(".recap"))
        expect(card).to_have_count(1)
        expect(page.locator(".hello")).to_have_count(0)
        return card

    def cost_said(card):
        """The cost line says the shop's own balance, as the server counts it (D-BALANCE-006)."""
        available = card.page.request.get(f"{smoke.ORIGIN}/api/balance").json()["available"]
        cost = card.locator("small", has_text=COST)
        expect(cost).to_have_text(f"1 crédit · il vous en reste {available}")
        return cost

    def on_phone(page, where):
        """Not wider than the 360 px screen (a wider page is laid out larger and zoomed out, D-REDESIGN-003 review), the
        composer inside what is seen."""
        width = page.evaluate("document.documentElement.scrollWidth")
        assert width <= 361, f"the page is {width} px wide at 360 px, {where}"
        assert page.locator(".composer").evaluate(REACH_JS)["inside"], f"the composer is not in view, {where}"

    # 1440 px: the question and the composer are one group in the middle of the column; then the composer goes down. The
    # composer holds the kit row since D-KIT-009 (154 px tall): its foot may reach 4/5 of the column, no longer 3/4.
    context, page = open_chat(1440, 900)
    chat, question, composer = box(page, ".chat"), box(page, ".hello-q"), box(page, ".composer")
    assert question["y"] >= chat["y"] + chat["height"] / 4 and bottom(composer) <= chat["y"] + chat["height"] * 4 / 5, (chat, question, composer)
    both_themes(page, "empty chat, 1440 px", "chat-empty-1440", placeholders=(".composer textarea",))
    card = first_message(page, "Sony WH-1000XM6 noir, 700 000 Ar")
    chat, composer = box(page, ".chat"), box(page, ".composer")
    assert abs(bottom(composer) - bottom(chat)) <= 1, (chat, composer)
    cells = page.locator(tops[0]).evaluate_all(tops[1])
    assert len(cells) >= 3 and len(set(cells)) == 1, f"the recap's cells are not one row at 1440 px: {cells}"
    cost_said(card)
    both_themes(page, "recap, 1440 px", "chat-recap-1440", placeholders=(".composer textarea",))
    context.close()

    # 1440 px, a recap brought from « Pas à pas » before any message: the thread is a conversation, not the welcome; it is
    # not centred, the composer is at the bottom.
    context, page = open_chat(1440, 900)
    switch = page.get_by_role("group", name="Façon de créer")
    switch.get_by_role("button", name="Pas à pas").click()
    page.get_by_label("Photos du produit").set_input_files(product)
    page.get_by_label("Nom du produit", exact=True).fill("Sony WH-1000XM6 noir")
    page.get_by_label("Prix en ariary", exact=True).fill("700000")
    expect(page.locator(".photo-strip img")).to_have_count(1)
    switch.get_by_role("button", name="Message").click()
    expect(page.get_by_role("log").get_by_role("button", name="Créer l’affiche")).to_be_visible()
    expect(page.locator(".hello")).to_have_count(0)
    expect(page.locator(".chat.welcome")).to_have_count(0)
    expect(page.get_by_role("log").locator(".bubble.bot").first).to_contain_text("Ajoutez une photo du produit.")
    chat, composer = box(page, ".chat"), box(page, ".composer")
    assert abs(bottom(composer) - bottom(chat)) <= 1, ("imported recap", chat, composer)
    context.close()

    # 360 px: the composer is at the bottom, empty and after the first message; its tool row is one line, « Envoyer » at its right.
    context, page = open_chat(360, 740)
    chat, composer, tools, send = box(page, ".chat"), box(page, ".composer"), box(page, ".tools"), box(page, ".chat .send")
    attach = box(page, ".chat .attach")
    assert abs(bottom(composer) - bottom(chat)) <= 1, (chat, composer)
    assert tools["height"] < 2 * 44 and abs(send["x"] + send["width"] - tools["x"] - tools["width"]) <= 1 and send["y"] >= tools["y"], (tools, send)
    on_phone(page, "empty chat")
    # The style strip scrolls sideways to its last style; « Ajouter des photos » and « Envoyer » stay where they are.
    last = page.locator(".style-row .style-pill").last
    last.evaluate("e => e.scrollIntoView({ inline: 'end', block: 'nearest', behavior: 'instant' })")
    assert page.locator(".style-row").evaluate("e => e.scrollLeft > 0"), "the style strip did not scroll"
    reach = last.evaluate(REACH_JS)
    assert reach["inside"] and reach["hit"], f"the last style is not reachable: {reach}"
    assert smoke.same_boxes([attach, send], [box(page, ".chat .attach"), box(page, ".chat .send")]), "attach or send moved with the strip"
    both_themes(page, "empty chat, 360 px", "chat-empty-360", placeholders=(".composer textarea",))
    # 58 characters, the title's limit is 60. The price in one run of digits: written « 12 500 000 », it also reads
    # « 500 000 », and two amounts are asked with their buttons (D-KIT-002).
    card = first_message(page, "Casque Bluetooth Sony WH-1000XM6 noir à réduction de bruit, 12.500.000 Ar")
    chat, composer = box(page, ".chat"), box(page, ".composer")
    assert abs(bottom(composer) - bottom(chat)) <= 1, (chat, composer)
    on_phone(page, "recap")
    # The cost is read before the tap: the line and its button seen at once, the line in the card and named by the button.
    create, cost = card.get_by_role("button", name="Créer l’affiche"), cost_said(card)
    seen = box(page, ".chat-thread")
    for part in (create, cost):
        reach, b = part.evaluate(REACH_JS), part.bounding_box()
        assert reach["inside"] and b["y"] >= seen["y"] - .5 and bottom(b) <= bottom(seen) + .5, (reach, b, seen)
    assert cost.get_attribute("id") in create.get_attribute("aria-describedby").split()
    expect(create).to_have_accessible_description(COST)
    both_themes(page, "recap with a long title, 360 px", "chat-recap-360")
    context.close()

    # 1241 px: the poster's side panel is a resting surface with a hairline; the thread has none.
    context = browser.new_context(viewport={"width": 1241, "height": 800}, color_scheme="light", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN + "/#affiches")
    page.get_by_role("button", name=re.compile("Sony WH-1000XM6 noir")).first.click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    page.get_by_role("button", name="Fermer", exact=True).click()
    expect(page.locator(".chat-side")).to_be_visible()

    def surface(theme):
        faults = page.evaluate(smoke.RESTING_JS, [".chat-side", smoke.PAINT[theme]["surface"], smoke.PAINT[theme]["line"]])
        assert not faults, f"the side panel at 1241 px, {theme}: {faults}"
        assert page.locator(".chat-thread").evaluate("e => getComputedStyle(e).backgroundColor") == smoke.CLEAR, "the thread has a surface"
    smoke.both_themes(page, surface)
    looks_right(page, "result, 1241 px", "chat-result-1241.png")
    context.close()


def walk_two_tabs(browser, errors, session, product):
    """One chat per device (Web Locks): a second page of the same browser says that the chat is open in another tab and
    sends nothing; « Continuer ici » takes it over. The first page loses it between its plan and its /scenes request:
    nothing paid leaves from it, and the second page, which finds no request kept, offers a new card."""
    sent = {"A": [], "B": []}
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    pages = []
    for name in "AB":
        page = context.new_page()
        page.set_default_timeout(10000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request, name=name: sent[name].append(request.url) if request.method == "POST" else None)
        page.goto(smoke.ORIGIN + "/#creer")
        page.wait_for_url("**/#message")
        pages.append(page)
    first, second = pages
    elsewhere = "Le chat est ouvert dans un autre onglet."
    expect(first.locator(".chat")).to_be_visible()
    expect(second.get_by_text(elsewhere)).to_be_visible()
    expect(second.locator(".chat")).to_have_count(0)
    looks_right(second, "chat open in another tab", "chat-elsewhere-1366.png")
    first.locator(".composer input[type=file]").set_input_files(product)
    expect(first.locator(".tray .pic[aria-busy]")).to_have_count(0)
    say(first, "Enceinte Sony XB100, 150 000 Ar")
    create = "Créer l’affiche"
    expect(first.get_by_role("button", name=create)).to_be_visible()
    assert not sent["B"], sent
    held = []
    first.route("**/plans", lambda route: held.append((route, route.fetch())))
    first.get_by_role("button", name=create).click()
    for _ in range(100):
        if held:
            break
        first.wait_for_timeout(100)
    second.get_by_role("button", name="Continuer ici").click()
    expect(first.get_by_text(elsewhere)).to_be_visible()
    expect(second.get_by_role("log")).to_contain_text("Rien n’a été envoyé pour cette demande.")
    expect(second.get_by_role("button", name=create)).to_have_count(1)
    # The first page takes the chat back before its plan arrives: its earlier work stays stopped all the same.
    first.get_by_role("button", name="Continuer ici").click()
    expect(second.get_by_text(elsewhere)).to_be_visible()
    expect(first.get_by_role("button", name=create)).to_have_count(1)
    route, response = held[0]
    route.fulfill(response=response)
    first.unroute("**/plans")
    first.wait_for_timeout(1500)
    scenes = lambda: [url for url in sent["A"] + sent["B"] if url.endswith("/scenes")]
    assert not scenes(), sent
    # The new card is the one that pays: one /scenes, followed to its version.
    first.get_by_role("button", name=create).click()
    expect(first.get_by_role("button", name="Vérifier", exact=True)).to_be_visible(timeout=30000)
    assert len(scenes()) == 1, sent
    context.close()


def walk_guards(browser, errors, session):
    """What a change card does with an answer that comes late, fails or is refused (T-CHAT-D005-TESTS). The poster is
    the one of walk_two_tabs: one version made by message, still to check. Its thread is empty in this browser."""
    sent, looks = {"refinements": [], "scenes": [], "plans": [], "revisions": []}, []

    def seen(request):
        for path in sent:
            if request.method == "POST" and request.url.endswith("/" + path):
                sent[path].append(request.headers["idempotency-key"])

    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    context.on("request", seen)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN + "/#creer")
    page.wait_for_url("**/#message")
    smoke.go(page, "Mes affiches")
    page.get_by_role("button", name=re.compile("Enceinte Sony XB100")).first.click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    poster = page.url.split("#message-")[1]
    thread, field, send, side = page.get_by_role("log"), page.get_by_label("Votre message"), page.get_by_role("button", name="Envoyer"), page.locator(".chat-side")
    switch = page.get_by_role("group", name="Façon de créer")
    create, cancel = thread.get_by_role("button", name="Créer", exact=True), thread.get_by_role("button", name="Annuler")
    redo = thread.get_by_role("button", name="Refaire l’affiche")
    spent = lambda: [item for item in page.evaluate(THREAD, poster)["items"] if item.get("spent")][-1]
    versions = lambda: page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}/visuals").json()["items"]
    made = lambda kind: [job for job in page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}/jobs").json()["items"] if job["kind"] == kind]
    paid = lambda: {path: len(keys) for path, keys in sent.items()}
    expect(side).to_contain_text("Version 1 · à vérifier")
    assert len(versions()) == 1 and versions()[0]["headline"]["title"] == "Enceinte Sony XB100", versions()

    def listed(change):  # this tab's listing of the versions, rewritten: the stub's versions have no saved style and no coloured word
        def answer(route):
            response = route.fetch()
            route.fulfill(response=response, json={"items": change(response.json()["items"])})
        context.route("**/creations/*/visuals", answer)
        page.reload()
        expect(side).to_contain_text("à vérifier")

    # The version was made with a saved style that was removed since, and the server cannot give it (here a 500): the
    # tap stops there. No plan, no scene: the image would be asked with the lettering of the editor's current style.
    gone, unread = str(uuid4()), "Le style de cette version n’a pas pu être lu."

    def no_look(route):
        looks.append(route.request.url)
        route.fulfill(status=500, json={"error": {"code": "server_error", "message_fr": unread}})
    context.route("**/api/looks/*", no_look)
    listed(lambda found: [item | {"headline": item["headline"] | {"look_id": gone}} for item in found])
    say(page, "sous-titre Sans fil")
    expect(thread.locator(".bubble.bot").last.locator("p.lines")).to_have_text(f"Sous-titre : Sans fil {REDRAW}")
    asked = len(looks)
    redo.click()
    expect(thread).to_contain_text(unread)
    stopped = spent()
    assert len(looks) == asked + 1 and looks[-1].endswith(gone), looks  # the style was asked for this tap
    assert stopped.get("done") and "request" not in stopped and "job" not in stopped and not any(paid().values()), (stopped, sent)
    expect(redo).to_have_count(1)  # nothing left: the same card again
    page.wait_for_timeout(500)
    assert not any(paid().values()), sent
    cancel.click()
    field.fill("")
    context.unroute("**/api/looks/*")
    context.unroute("**/creations/*/visuals")

    # The editor is on « Aux couleurs du produit », whose accent is the photo's colour. The version has a coloured word
    # and no saved style: its new image keeps its own colour (ADR-100), read on the request as it left.
    accent = {"accent_word": "Enceinte", "accent_colour": "#D92B2B"}
    listed(lambda found: [item | {"headline": item["headline"] | accent} for item in found])
    switch.get_by_role("button", name="Pas à pas").click()
    page.wait_for_url(f"**/#{poster}")
    page.get_by_role("tab", name="Style").click()
    page.get_by_role("button", name="Aux couleurs du produit", exact=True).click()
    # No colour code is written (D-KIT-012): the swatch's own colour is read.
    swatches = page.get_by_role("img", name="Palette de la prochaine version").locator("i")
    expect(swatches).to_have_count(3)
    photo_colour = swatches.nth(2).evaluate("e => '#' + getComputedStyle(e).backgroundColor.match(/\\d+/g).slice(0, 3).map(n => (+n).toString(16).padStart(2, '0')).join('')").upper()
    assert re.fullmatch(r"#[0-9A-F]{6}", photo_colour) and photo_colour != accent["accent_colour"], photo_colour
    switch.get_by_role("button", name="Message").click()
    page.wait_for_url(f"**/#message-{poster}")
    say(page, "sous-titre Sans fil")
    redo.click()
    expect(thread).to_contain_text("Version 2 prête.", timeout=30000)
    drawn = spent()["request"]["body"]["headline"]
    assert drawn["accent_word"] == "Enceinte" and drawn["accent_colour"] == accent["accent_colour"] and drawn["subtitle"] == "Sans fil", drawn
    context.unroute("**/creations/*/visuals")
    second = versions()[0]
    assert second["headline"]["accent_colour"] == accent["accent_colour"] and paid() == {"refinements": 0, "scenes": 1, "plans": 0, "revisions": 1}, (second, sent)

    # The chat is taken by another tab after the server answered the card's plan request and before this tab hears of
    # it. The late answer starts nothing: no scene leaves from this tab. Then this tab takes the chat back.
    def taken(pattern):
        held, before = [], paid()
        context.route(pattern, lambda route: route.continue_() if held or route.request.method != "POST" else held.append((route, route.fetch())))
        redo.click()
        for _ in range(100):
            if held:
                break
            page.wait_for_timeout(100)
        assert held, f"no request for {pattern}"
        other_tab = context.new_page()
        other_tab.set_default_timeout(10000)
        other_tab.on("pageerror", lambda error: errors.append(str(error)))
        other_tab.goto(f"{smoke.ORIGIN}/#message-{poster}")
        other_tab.get_by_role("button", name="Continuer ici").click()
        expect(page.get_by_text("Le chat est ouvert dans un autre onglet.")).to_be_visible()
        expect(other_tab.get_by_role("log")).to_contain_text("Rien n’a été envoyé pour cette demande.")
        held[0][0].fulfill(response=held[0][1])
        context.unroute(pattern)
        page.wait_for_timeout(1500)
        assert paid()["scenes"] == before["scenes"] and "request" not in spent(), (sent, spent())
        other_tab.close()
        page.get_by_role("button", name="Continuer ici").click()
        expect(redo).to_have_count(1)
        return before
    # First the version's own plan, saved again as a revision (ADR-100).
    say(page, "sous-titre Portable")
    expect(redo).to_be_visible()
    before = taken("**/plans/*/revisions")
    assert paid() == before | {"revisions": before["revisions"] + 1}, sent
    # Then a version whose plan cannot be revised here (it is answered as another poster's, as for a copy): the image
    # is asked as « Nouvelle version » does, with a fresh plan. The late plan is not kept for the next tap, which asks
    # its own and pays once.
    def foreign_plan(route):
        response = route.fetch()
        route.fulfill(response=response, json=response.json() | {"creation_id": str(uuid4())})
    context.route("**/api/plans/*", foreign_plan)
    before = taken("**/plans")
    assert paid() == before | {"plans": before["plans"] + 1}, sent
    redo.click()
    expect(thread).to_contain_text("Version 3 prête.", timeout=30000)
    context.unroute("**/api/plans/*")
    assert paid() == before | {"plans": before["plans"] + 2, "scenes": before["scenes"] + 1} and sent["scenes"][-1] == spent()["id"], (sent, spent())
    third = versions()[0]
    assert third["headline"]["subtitle"] == "Portable" and len(made("scene")) == 3, third

    # The version's plan no longer fits the poster (as after a layout change in « Pas à pas »; here the revision is
    # delivered with a title region too small, and the server answers its own invalid_plan). A rule refused it: the
    # card is closed with the server's sentence and the way to the steps. No new card, nothing paid.
    def small_title(route):
        body = route.request.post_data_json
        for region in body["overlay_regions"]:
            if region["field"] == "title":
                region["box"]["h"] = .001
        route.continue_(post_data=json.dumps(body))
    context.route("**/plans/*/revisions", small_title)
    say(page, "sous-titre Nomade")
    card, before = thread.locator(".bubble.bot").last, paid()
    redo.click()
    expect(card.locator(".why")).to_have_text(INVALID_PLAN)
    context.unroute("**/plans/*/revisions")
    expect(card.get_by_role("button")).to_have_text(["Corriger dans Pas à pas"])
    expect(thread.locator(".bubble.bot").last.locator("p.lines")).to_have_text(f"Sous-titre : Nomade {REDRAW}")  # no card after it
    expect(redo).to_have_count(0)
    refused = spent()
    assert refused.get("done") and refused["card"].get("fix") and "request" not in refused and "job" not in refused, refused
    page.wait_for_timeout(500)
    assert paid() == before | {"revisions": before["revisions"] + 1} and len(made("scene")) == 3, sent
    looks_right(page, "kept plan refused", "chat-invalid-plan-1366.png")
    card.get_by_role("button", name="Corriger dans Pas à pas").click()
    page.wait_for_url(f"**/#{poster}")
    switch.get_by_role("button", name="Message").click()
    page.wait_for_url(f"**/#message-{poster}")

    # A card's job made its version, and the poster does not list it (this tab's listing is answered without it).
    # Trying again cannot help and the image exists: the card is closed, the thread says where to look, no paid card
    # is offered for it, and the composer is free again.
    known = {item["id"] for item in versions()}
    say(page, "fond plus sombre")
    expect(create).to_be_visible()
    context.route("**/creations/*/visuals", lambda route: route.fulfill(response=(response := route.fetch()), json={"items": [item for item in response.json()["items"] if item["id"] in known]}))
    create.click()
    expect(thread).to_contain_text(UNLISTED, timeout=30000)
    expect(thread.locator(".bubble.bot").last.get_by_role("button")).to_have_text(["Pas à pas"])
    closed = spent()
    assert closed.get("done") and closed.get("job") and not closed["card"].get("error"), closed
    assert [job["status"] for job in made("refine")] == ["succeeded"] and len(versions()) == len(known) + 1, made("refine")
    expect(thread.get_by_role("button", name=re.compile("^(Créer|Créer l’affiche|Refaire l’affiche|Réessayer|Reprendre)$"))).to_have_count(0)
    page.wait_for_timeout(500)
    assert sent["refinements"] == [closed["id"]] and len(made("scene")) == 3, sent
    field.fill("fond rouge")
    expect(send).to_be_enabled()  # no unresolved card holds the composer
    looks_right(page, "version made but not listed", "chat-unlisted-1366.png")
    field.fill("")
    context.unroute("**/creations/*/visuals")
    context.close()


def walk_lockless(browser, errors, session):
    """Without Web Locks the chat cannot be kept to one tab: it is not offered, and nothing is sent."""
    posts = []
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="light", storage_state=session)
    context.add_init_script("Object.defineProperty(Navigator.prototype, 'locks', { get: () => undefined, configurable: true })")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: posts.append(request.url) if request.method == "POST" else None)
    page.goto(smoke.ORIGIN)
    page.get_by_role("link", name="Créer une affiche").tap()
    page.wait_for_url("**/#etapes")
    expect(page.get_by_label("Photos du produit")).to_be_enabled()
    page.goto(smoke.ORIGIN + "/#message")  # a saved chat address still offers an explanation and a way out
    fallback = page.locator(".chat-elsewhere")
    expect(fallback).to_contain_text("Ce navigateur ne permet pas le chat.")
    expect(page.locator(".chat")).to_have_count(0)
    looks_right(page, "no Web Locks, 360 px", "chat-lockless-360.png")
    fallback.get_by_role("button", name="Pas à pas").tap()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    assert not posts, posts
    context.close()


# The chat's lock never given: ownership stays pending, and the page says when the chat asked. The identity's lock works as before.
LOCK_PENDING = """const request = LockManager.prototype.request
LockManager.prototype.request = function (name, ...rest) { if (name !== 'affiche-chat') return request.call(this, name, ...rest); window.chatLockAsked = true; return new Promise(() => {}) }"""
# Hidden from the eye: a box of 1 px at most that clips what it holds.
CLIPPED = "e => { const box = e.getBoundingClientRect(), style = getComputedStyle(e); return box.width <= 1 && box.height <= 1 && (style.overflowX === 'hidden' || style.clipPath === 'inset(50%)') }"


def check_title(page, name, where):
    """The chat route's one title (D-POLISH-003): one level-one heading for a screen reader, hidden from the eye, outside
    the conversation's live region."""
    title = page.get_by_role("heading", level=1)
    expect(title).to_have_count(1)
    expect(title).to_have_accessible_name(name)
    assert title.evaluate(CLIPPED) and title.evaluate("e => !e.closest('[aria-live], [role=log]')"), where


def walk_titles(browser, errors, session):
    """The chat's title in each state: no poster yet, a poster with its title and without, the chat in another tab, a
    browser without Web Locks, ownership still pending, and the chat's code that failed to load."""
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN + "/#creer")
    page.wait_for_url("**/#message")
    expect(page.locator(".chat")).to_be_visible()
    check_title(page, "Créer une affiche", "no poster")
    other = context.new_page()
    other.on("pageerror", lambda error: errors.append(str(error)))
    other.goto(smoke.ORIGIN + "/#message")
    expect(other.get_by_text("Le chat est ouvert dans un autre onglet.")).to_be_visible()
    check_title(other, "Créer une affiche", "chat in another tab")
    other.close()
    poster = page.request.get(smoke.ORIGIN + "/api/creations?limit=1").json()["items"][0]
    # A poster opened from « Mes affiches »: while its read is on its way, the list's title is the only one.
    page.goto(smoke.ORIGIN + "/#affiches")
    expect(page.get_by_role("heading", level=1)).to_have_accessible_name("Mes affiches")
    read, held = f"**/api/creations/{poster['id']}", []
    page.route(read, lambda route: held.append(route))
    with page.expect_request(read):
        page.evaluate("id => { location.hash = 'message-' + id }", poster["id"])
    expect(page.get_by_role("heading", level=1)).to_have_count(1)
    expect(page.get_by_role("heading", level=1)).to_have_accessible_name("Mes affiches")
    held.pop().continue_()
    page.unroute(read)
    expect(page.get_by_role("log")).to_be_visible()
    check_title(page, poster["title"], "a poster")
    def untitled(route):
        response = route.fetch()
        body = response.json()
        body["document"]["offer"]["title"] = ""
        route.fulfill(response=response, json=body)
    page.route(f"**/api/creations/{poster['id']}", untitled)
    page.reload()
    expect(page.get_by_role("log")).to_be_visible()
    check_title(page, "Votre affiche", "a poster without a title")
    context.close()
    for script, where, shown in ((smoke.NO_LOCKS, "no Web Locks", "Ce navigateur ne permet pas le chat."),
                                 (LOCK_PENDING, "ownership pending", None),
                                 (None, "the chat's code not loaded", "La création par message n’a pas pu se charger.")):
        context = browser.new_context(viewport={"width": 360, "height": 740}, color_scheme="light", storage_state=session)
        if script:
            context.add_init_script(script)
        else:
            context.route(re.compile(r"/ChatView[^/]*\.(vue|js)"), lambda route: route.abort())
        page = context.new_page()
        page.set_default_timeout(10000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(smoke.ORIGIN + "/#message")
        if shown:
            expect(page.get_by_text(shown)).to_be_visible()
        else:
            page.wait_for_function("window.chatLockAsked === true")
            expect(page.locator(".chat, .chat-elsewhere")).to_have_count(0)
        check_title(page, "Créer une affiche", where)
        context.close()


def walk_slow_read(browser, errors, session):
    """A read still on its way when the chat closes (a switch to « Pas à pas ») does nothing when its answer finally comes:
    the next read's pending record stays in place."""
    hold, held, keys = {"on": True}, [], []

    def hold_read(route):
        keys.append(route.request.headers["idempotency-key"])
        if not hold["on"]:
            return route.continue_()
        held.append((route, route.fetch()))
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", storage_state=session)
    context.route("**/api/reads", hold_read)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN + "/#creer")
    page.wait_for_url("**/#message")
    thread, switch = page.get_by_role("log"), page.get_by_role("group", name="Façon de créer")
    say(page, "Casque Marshall Major")
    page.wait_for_function("() => document.querySelector('.chat-wait')")
    first = page.evaluate(PENDING)
    switch.get_by_role("button", name="Pas à pas").click()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    switch.get_by_role("button", name="Message").click()
    expect(thread).to_contain_text("L’envoi a été interrompu.")
    hold["on"] = False
    thread.get_by_role("button", name="Réessayer").click()  # the same record: the server answers what it stored
    expect(thread).to_contain_text(NO_PRICE)
    assert keys == [first, first] and page.evaluate(PENDING) is None, (keys, first)
    hold["on"] = True
    say(page, "300 000 Ar")
    for _ in range(100):
        if len(held) == 2:
            break
        page.wait_for_timeout(100)
    second = page.evaluate(PENDING)
    assert second and second != first, (first, second)
    route, response = held[0]
    route.fulfill(response=response)  # the closed view's answer, late
    page.wait_for_timeout(500)
    assert page.evaluate(PENDING) == second
    route, response = held[1]
    route.fulfill(response=response)
    expect(thread).to_contain_text("Il me faut une photo du produit.")
    assert page.evaluate(PENDING) is None
    context.close()


def walk_failed(browser, errors, product):
    """The reader fails (STUB_FAIL): the bubble stays, « Réessayer » pays a new read, « Pas à pas » is one tap away."""
    reads = []
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="light")
    context.on("request", lambda request: reads.append(request.headers["idempotency-key"]) if request.method == "POST" and request.url.endswith("/api/reads") else None)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    sign_in(page)
    page.get_by_role("link", name="Créer une affiche").tap()
    expect(page.locator(".chat")).to_be_visible()
    looks_right(page, "start choice gone, 360 px")
    thread = page.get_by_role("log")
    say(page, "Sony WH-1000XM6 noir, 700 000 Ar")
    failed = thread.locator(".bubble.bot").last
    expect(failed).to_contain_text("Je n’ai pas pu lire votre message.")
    expect(thread.locator(".bubble.me")).to_have_text("Sony WH-1000XM6 noir, 700 000 Ar")
    looks_right(page, "read failed, 360 px", "chat-failed-360.png")
    failed.get_by_role("button", name="Réessayer").tap()
    expect(thread.locator(".bubble.bot").last).to_contain_text("Je n’ai pas pu lire votre message.")
    expect(thread.locator(".bubble.me")).to_have_count(1)
    page.wait_for_function("document.querySelectorAll('.chat-thread .bubble.bot').length === 3")
    assert len(reads) == 2 and reads[0] != reads[1], reads  # a failed read is not replayed: the retry is a new one
    expect(thread.get_by_role("button", name="Réessayer")).to_have_count(1)
    thread.get_by_role("button", name="Pas à pas").tap()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    expect(page.locator(".chat")).to_have_count(0)
    assert page.evaluate(START) == "steps"
    # The image job fails at the provider (not a refusal). The form gives the product without a read; back in the chat the recap is
    # there, the tap pays, and the failure is said with a new card: never a new attempt by itself.
    page.get_by_label("Photos du produit").set_input_files(product)
    page.get_by_label("Nom du produit", exact=True).fill("Sony WH-1000XM6 noir")
    page.get_by_label("Prix en ariary", exact=True).fill("700000")
    expect(page.locator(".photo-strip img")).to_have_count(1)
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Message").tap()
    create = page.get_by_role("button", name="Créer l’affiche")
    create.tap()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    expect(thread).to_contain_text("La génération a été interrompue. Aucun nouvel appel automatique n’a été lancé.", timeout=30000)
    expect(create).to_have_count(1)
    expect(create).to_be_enabled()
    expect(page.get_by_role("button", name="Vérifier", exact=True)).to_have_count(0)
    jobs = page.request.get(f"{smoke.ORIGIN}/api/creations/{page.url.split('#message-')[1]}/jobs").json()["items"]
    assert [(job["kind"], job["status"]) for job in jobs if job["kind"] == "scene"] == [("scene", "interrupted")], jobs  # a provider error may have been billed: not retried
    looks_right(page, "image job failed, 360 px", "chat-job-failed-360.png")
    # A job that ends while no page hears of it (its polls held) is said at the next opening as the editor says it: its
    # cause, then that its credit is back (T-BALANCE-006 review r1). Its own end once (interrupted); then its view
    # rewritten on the reopened page as failed, then as cancelled.
    poster = page.url.split("#message-")[1]
    returned = thread.locator(".bubble.bot", has_text="Votre crédit vous a été rendu.")
    for status, code, said in ((None, None, "La génération a été interrompue."),
                               ("failed", "refused", "Le service d’images a refusé cette demande"),
                               ("cancelled", "shop_suspended", "La tâche n’a pas abouti (code : shop_suspended).")):
        before = returned.count()
        page.route("**/api/jobs/*", lambda route: None)  # never answered on this page
        create.tap()
        for _ in range(100):  # the card just tapped holds its job, which has ended on the server
            waiting = [item for item in page.evaluate(THREAD, poster)["items"] if item.get("spent") and not item.get("done")]
            job = waiting[-1].get("job") if waiting else None
            if job and page.request.get(f"{smoke.ORIGIN}/api/jobs/{job}").json()["status"] not in ("queued", "running"):
                break
            page.wait_for_timeout(100)
        else:
            raise AssertionError("the card's job did not end")
        page.unroute("**/api/jobs/*")

        def rewritten(status, code):  # Playwright passes the request too to a handler of two parameters, defaults included
            def handle(route):
                answer = route.fetch()
                route.fulfill(response=answer, json=answer.json() | {"status": status, "error_code": code})
            return handle
        if status:
            page.route(f"**/api/jobs/{job}", rewritten(status, code))
        page.reload()
        expect(returned).to_have_count(before + 1, timeout=15000)
        expect(returned.last).to_contain_text(said)
        if status:
            page.unroute(f"**/api/jobs/{job}")
        expect(create).to_be_enabled()
    context.close()


WAITING_LINE = ("Une image demandée attend encore sa réponse. Si le serveur a reçu la demande, l’image se fait quand même et vous la "
                "trouverez dans « Mes affiches », sur cet appareil ou un autre ; sinon, rien n’est payé. Rien de cette conversation ne reste sur cet appareil.")
UNSTORED = "Ce navigateur ne peut pas garder la demande : rien n’a été envoyé. Utilisez Pas à pas."
SHOP_KEYS = "() => Object.keys(localStorage).filter(key => key.startsWith('affiche.shop1.')).sort()"
# setItem refused, as a full browser storage refuses it (until the page is reloaded): for the keys the pattern names, and
# with `needle`, only for a value that holds it.
REFUSE = """([pattern, needle]) => { const refused = new RegExp(pattern), set = Storage.prototype.setItem
  Storage.prototype.setItem = function (key, value) { if (refused.test(key) && String(value).includes(needle ?? '')) throw new DOMException('full', 'QuotaExceededError'); return set.call(this, key, value) } }"""
THREADS = r"^affiche\.shop1\.chat\.(?!unsent$|pending$)"


def walk_sign_out(browser, errors, product):
    """« Se déconnecter » keeps nothing of the shop on this device; the server is the authority for a paid request
    (ADR-108). (a) The answer to a paid card is lost and the owner signs out: no key of the shop is left; signed in
    again, the poster shows that one job's version, and the server has one job for the card. (b) A /scenes request held
    on its way while another tab signs out, released after: 401, no job, and the late answer writes nothing back. (c)
    That sign-out is from a tab that does not hold the chat. Strict send: a browser that cannot store the card, or its
    request, sends nothing."""
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    sent = []
    page.on("request", lambda request: sent.append(f"{request.method} {request.url.split('/api/')[1]}") if "/api/" in request.url and request.method == "POST" else None)
    sign_in(page)
    page.get_by_role("link", name="Créer une affiche").tap()
    page.get_by_role("button", name="Pas à pas", exact=True).tap()
    expect(page.get_by_label("Photos du produit")).to_be_visible()  # the form, before the shell's way to a new poster
    thread = page.get_by_role("log")
    dialog = page.get_by_role("dialog")
    create = thread.get_by_role("button", name="Créer l’affiche")

    def recap(name):
        """A recap from the form, its « Créer l’affiche » not tapped yet."""
        smoke.go(page, "Nouvelle affiche", tap=True)
        page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Pas à pas").tap()
        page.get_by_label("Photos du produit").set_input_files(product)
        page.get_by_label("Nom du produit", exact=True).fill(name)
        page.get_by_label("Prix en ariary", exact=True).fill("700000")
        expect(page.locator(".photo-strip img")).to_have_count(1)
        page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Message").tap()
        expect(create).to_be_visible()

    # Strict send, at the tap: the card cannot be stored, so nothing leaves, not even the poster.
    recap("Casque Garde Refus")
    page.evaluate(REFUSE, [THREADS, None])
    sent.clear()
    create.tap()
    expect(thread).to_contain_text(UNSTORED)
    expect(create).to_be_visible()  # a new card, the same offer
    assert sent == [], sent
    # At sending: the card is stored, its request is not: the poster and its free plan are made, the paid request is not.
    page.reload()
    recap("Casque Garde Refus Deux")
    page.evaluate(REFUSE, [THREADS, '"request":'])
    sent.clear()
    create.tap()
    expect(thread).to_contain_text(UNSTORED)
    expect(create).to_be_visible()
    assert not [entry for entry in sent if entry.endswith("/scenes")], sent
    page.reload()

    # (a) The paid card's answer is lost: the server made the job, the page never heard. Signed out, then in again.
    # Thirty stored threads dated a day ahead, as after the device's clock was set back (review r5 P2-2): the cap never
    # takes the thread just written, so the request is stored when it leaves.
    recap("Casque Garde Un")
    page.evaluate("""() => { for (let index = 0; index < 30; index++) localStorage.setItem('affiche.shop1.chat.ahead' + index,
      JSON.stringify({ at: Date.now() + 86400000, items: [], draft: {} })) }""")
    context.route("**/scenes", lambda route: (route.fetch(), route.abort("failed")))
    create.tap()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    poster = page.url.split("#message-")[1]
    expect(thread.get_by_role("button", name="Réessayer")).to_be_visible()
    stored = page.evaluate(THREAD, poster)
    assert stored and [item["request"]["path"] for item in stored["items"] if item.get("request")] == [f"/api/creations/{poster}/scenes"], stored
    context.unroute("**/scenes")
    # From the editor the chat is not mounted: the stored thread says that the image waits (review r5 P2-3).
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Pas à pas").tap()
    page.wait_for_url(f"**/#{poster}")
    page.locator(".bar").get_by_role("button", name="Se déconnecter").tap()
    expect(dialog).to_contain_text(WAITING_LINE)
    dialog.get_by_role("button", name="Annuler").tap()
    page.goto(f"{smoke.ORIGIN}/#message-{poster}")  # the phone's editor has no header, nor its switch
    expect(thread.get_by_role("button", name="Reprendre")).to_be_visible()  # the chat read again: its kept request
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Message").tap()  # the start view again
    assert page.evaluate(START) == "chat"
    smoke.go(page, "Se déconnecter", tap=True)
    expect(dialog).to_contain_text(WAITING_LINE)
    for scheme, theme in (("dark", "sombre"), ("light", "clair")):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"document.documentElement.dataset.theme === '{theme}'")
        smoke.check_contrast(page, f"sign-out with a waiting paid card, 360 px, {theme}")
        page.screenshot(path=str(OUT / f"sign-out-waiting-360-{theme}.png"))
    page.emulate_media(color_scheme="dark")
    with smoke.replaced(page):  # to the fresh page: the old one may show the sign-in a moment before
        dialog.get_by_role("button", name="Se déconnecter quand même").tap()
    expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
    assert page.evaluate(SHOP_KEYS) == [], page.evaluate(SHOP_KEYS)
    # The shop loads its list before the version has come (the page's answers are served as they were then, until the
    # owner opens « Mes affiches »); opening it reads the list again, without a reload.
    before, listing = {"on": True, "served": 0}, lambda url: "/api/creations?limit=5" in url

    def before_the_version(route):
        if not (before["on"] and route.request.headers.get("x-affiche-shop")):
            return route.continue_()  # this walk's own reads, and the list once opened
        body = route.fetch().json()
        for entry in body["items"]:
            if entry["id"] == poster:
                entry.update(state="draft", thumbnail_url=None)
        before["served"] += 1
        route.fulfill(json=body)
    page.route(listing, before_the_version)
    sign_in(page)
    expect(page.locator(".home-recent")).to_be_visible()
    page.screenshot(path=str(OUT / "signed-in-again-360.png"))
    end = time.monotonic() + 30
    while not page.evaluate("""id => fetch('/api/creations?limit=50').then(r => r.json())
      .then(body => body.items.some(item => item.id === id && item.state === 'to_review'))""", poster):
        assert time.monotonic() < end, "the version never came"
        page.wait_for_timeout(500)
    assert before["served"] >= 1, before  # the shop's list, read at its load
    before["on"] = False
    smoke.go(page, "Mes affiches")
    item = page.locator(".library-item", has_text="Casque Garde Un")
    expect(item).to_contain_text("À vérifier")
    # Opened again while the list cannot be read: it says so, and the list shown stays.
    smoke.go(page, "Nouvelle affiche")
    expect(page.get_by_label("Votre message")).to_be_visible()
    page.route(listing, lambda route: route.abort("failed"))
    smoke.go(page, "Mes affiches")
    expect(page.locator(".message.error")).to_contain_text("Connexion interrompue. Vos modifications restent dans cet onglet.")
    expect(item).to_contain_text("À vérifier")
    page.unroute(listing)
    page.screenshot(path=str(OUT / "signed-in-again-library-done-360.png"))
    item.click()
    page.wait_for_url(f"**/#message-{poster}")
    # The card does not come back: the poster's thread starts afresh, its version to review at the top.
    expect(page.get_by_text("Version 1 · à vérifier")).to_be_visible()
    expect(page.get_by_role("button", name="Agrandir l’affiche")).to_be_visible()
    expect(thread.get_by_role("button", name=re.compile("^(Réessayer|Reprendre|Créer l’affiche)$"))).to_have_count(0)
    page.screenshot(path=str(OUT / "signed-in-again-poster-360.png"))
    assert page.evaluate(SCENE_JOBS, poster) == 1  # the one request the server received: one job

    # (b, c) A paid card's /scenes request on its way while another tab, which does not hold the chat, signs out: that tab
    # reads the stored threads and asks first (review r5 P2-3). This tab is told, and writes nothing of the shop from that
    # moment (review r5 P2-1): the answer reaches it before its own session check has answered, or after that check
    # failed. Admitted before the sign-out, the request lives on the server (one job); arriving after it with the
    # session's cookie, it is refused (401) and makes no job.
    def across(name, admitted, check_fails):
        recap(name)
        token = next(cookie["value"] for cookie in context.cookies() if cookie["name"] == "affiche_session")
        held, checks = [], []
        context.route("**/scenes", lambda route: held.append((route, route.fetch() if admitted else None)))
        create.tap()
        page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
        made = page.url.split("#message-")[1]
        end = time.monotonic() + 15
        while not held:
            assert time.monotonic() < end, "the request never left"
            page.wait_for_timeout(50)
        page.route("**/api/session", lambda route: checks.append(route) if route.request.method == "GET" else route.continue_())
        other = context.new_page()
        other.set_default_timeout(10000)
        other.goto(smoke.ORIGIN + "/#creer")
        expect(other.locator("main:not(.gate)")).to_be_visible()
        smoke.go(other, "Se déconnecter")
        expect(other.get_by_role("dialog")).to_contain_text(WAITING_LINE)
        with smoke.replaced(other):
            other.get_by_role("dialog").get_by_role("button", name="Se déconnecter quand même").click()
        end = time.monotonic() + 15
        while not checks:  # told by the other tab: its own check is on its way
            assert time.monotonic() < end, "this tab never asked"
            page.wait_for_timeout(50)
        expect(page.get_by_label("Mot de passe", exact=True)).to_have_count(0)  # not the sign-in yet
        if check_fails:
            checks.pop(0).abort("failed")
            expect(page.get_by_text("Connexion au serveur impossible.")).to_be_visible()
        route, answer = held[0]
        if not admitted:
            answer = route.fetch(headers={**route.request.headers, "cookie": f"affiche_session={token}"})
            assert answer.status == 401, answer.status
        route.fulfill(response=answer)
        context.unroute("**/scenes")
        page.wait_for_timeout(500)  # the card's own work after its answer, had it written anything
        assert page.evaluate(SHOP_KEYS) == [], page.evaluate(SHOP_KEYS)
        for check in checks:
            check.continue_()  # nobody, now
        page.unroute("**/api/session")
        expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
        assert page.evaluate(SHOP_KEYS) == [], page.evaluate(SHOP_KEYS)
        other.close()
        sign_in(page)
        page.get_by_role("link", name="Créer une affiche").click()
        page.wait_for_url("**/#message")
        assert page.evaluate(SCENE_JOBS, made) == (1 if admitted else 0)

    across("Casque Garde Deux", admitted=True, check_fails=False)
    across("Casque Garde Trois", admitted=True, check_fails=True)
    across("Casque Garde Quatre", admitted=False, check_fails=False)
    context.close()


def walk_rest(browser, errors, product, inspiration):
    """D-TEXT-FIRST-006: the shop's logo and contact asked in the first message (an empty profile, then a filled one;
    asked off against the form's ticks), a change of style, a tab of an older bundle refused by the server, the two
    sentences to « Pas à pas », a card kind this bundle does not know. Its own session and browser storage; the shop's
    profile is empty until this walk fills it, at its end."""
    bodies, sent, drafts = [], {"scenes": [], "plans": [], "revisions": [], "looks": []}, []

    def seen(request):
        if request.method != "POST":
            return
        if request.url.endswith("/api/reads"):
            bodies.append(request.post_data_json)
        if request.url.endswith("/api/creations"):
            drafts.append(request.post_data_json)
        for path in sent:
            if request.url.endswith("/" + path):
                sent[path].append(request.headers["idempotency-key"])

    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    context.on("request", seen)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: print(f"HTTP {response.status} {response.url}", flush=True) if response.status >= 400 else None)
    sign_in(page)
    page.get_by_role("link", name="Créer une affiche").click()
    page.wait_for_url("**/#message")
    thread, field, side = page.get_by_role("log"), page.get_by_label("Votre message"), page.locator(".chat-side")
    switch = page.get_by_role("group", name="Façon de créer")
    recap = thread.locator(".bubble.bot", has=page.locator(".recap")).last
    create, cancel = thread.get_by_role("button", name="Créer", exact=True), thread.get_by_role("button", name="Annuler")
    redo, first_tap = thread.get_by_role("button", name="Refaire l’affiche"), thread.get_by_role("button", name="Créer l’affiche")
    last = thread.locator(".bubble.bot").last
    get = lambda path: page.request.get(f"{smoke.ORIGIN}/api/{path}").json()
    paid = lambda: {path: len(keys) for path, keys in sent.items()}
    with_identity = "avec le logo et le contact de la boutique"

    def new_poster(message, line, *files):
        """One message with its images to the first version; the inspiration, when given, marked as the style model by
        one touch (D-KIT-006). Returns the poster's id."""
        page.goto(f"{smoke.ORIGIN}/#message")
        expect(thread).to_contain_text("Ajoutez une photo du produit.")
        page.locator(".composer input[type=file]").set_input_files(list(files))
        expect(page.locator(".tray .pic")).to_have_count(len(files))
        expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
        if inspiration in files:
            role = page.locator(".tray .pic").nth(files.index(inspiration)).locator(".pic-role")
            role.click()
            expect(role).to_have_text("Modèle de style")
        say(page, message)
        # The recap's box holds the format; the scene and the shop's identity are the lines under it.
        expect(recap.locator(".recap small")).to_have_text(["Publication 4:5"])
        expect(recap.locator(":scope > small").nth(0)).to_have_text(re.compile("^Scène : "))
        expect(recap.locator(":scope > small").nth(1)).to_have_text(line)
        assert "identity" not in bodies[-1]["draft"], bodies[-1]  # asked in this message: the draft sent is the old shape
        first_tap.click()
        page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
        expect(thread).to_contain_text("Version 1 prête.", timeout=30000)
        return page.url.split("#message-")[1]

    # The shop has no logo and no contact: the recap says so, and the poster is made without them.
    empty = get("shop-profile")
    assert not empty["logo_asset"] and not empty["contact"], empty
    poster = new_poster(f"Casque Bose QC45, 300 000 Ar, {with_identity}",
                        "La boutique n’a pas encore de logo ni de contact : ajoutez-les dans Pas à pas.", product, inspiration)
    spent = lambda: [item for item in page.evaluate(THREAD, poster)["items"] if item.get("spent")][-1]
    versions = lambda: get(f"creations/{poster}/visuals")["items"]
    plan_of = lambda visual: get(f"plans/{visual['plan_id']}")

    def lineage(visual):  # a version's plan and the plans it was revised from
        plans, plan = [], visual["plan_id"]
        while plan:
            plans.append(plan)
            plan = get(f"plans/{plan}")["parent_plan_id"]
        return plans
    nothing = {"logo": False, "shop_name": False, "contact": False}
    assert drafts[-1]["offer"]["title"] == "Casque Bose QC45" and drafts[-1]["brand_selection"] == nothing, drafts[-1]
    assert get(f"creations/{poster}")["document"]["include"] == nothing
    # The style model is a look the shop already has from the same image (walk_desktop's « Style 1 »): taken again, with
    # no second brief (D-KIT-006).
    expect(thread).to_contain_text("Votre modèle de style est gardé dans votre kit : « Style 1 ».")
    model = get("looks")["items"]
    assert not sent["looks"] and len(model) == 1 and spent()["request"]["body"]["headline"]["look_id"] == model[0]["id"], (sent, model)
    looks_right(page, "recap, empty shop profile")

    # A change of style. The version follows the style model (a look, not a raw model image) and a scene adjustment
    # asked by message: the card says the adjustment is not carried, and is paid as a whole new image.
    say(page, "fond bleu nuit")
    create.click()
    expect(thread).to_contain_text("Version 2 prête.", timeout=30000)
    second = versions()[0]
    assert second["instruction_fr"] == "fond bleu nuit" and not second["style_reference_asset"], second
    say(page, "mets le style luxe sombre")
    expect(last.locator("p.lines")).to_have_text("Style : Luxe sombre Les ajustements de scène demandés avant ne sont pas repris.")
    expect(last.get_by_role("button")).to_have_text(["Refaire l’affiche", "Annuler"])
    expect(last).to_contain_text(COST)
    assert bodies[-1]["visual_id"] == second["id"], bodies[-1]
    both_themes(page, "style change card", "chat-restyle-1366")
    # « Annuler » gives the words back, as on a change card; nothing was asked for the poster.
    before = paid()
    cancel.click()
    expect(field).to_have_value("mets le style luxe sombre")
    expect(redo).to_have_count(0)
    page.get_by_role("button", name="Envoyer").click()
    expect(redo).to_be_visible()
    redo.click()
    expect(thread).to_contain_text("Version 3 prête.", timeout=30000)
    request, third = spent()["request"], versions()[0]
    assert spent()["card"]["kind"] == "restyle" and sent["scenes"][-1] == spent()["id"], spent()
    # A fresh plan in the new style, not the version's plan saved again; no model image and no kept adjustment.
    # (The editor saves a fresh plan again at the document's revision before the scene, as for a first poster.)
    assert paid() | {"revisions": 0} == before | {"plans": before["plans"] + 1, "scenes": before["scenes"] + 1, "revisions": 0}, (sent, before)
    assert request["path"].endswith("/scenes") and not {"style_reference_asset", "keep_adjustments_of"} & request["body"].keys(), request
    assert "look_id" not in request["body"]["headline"], request  # the new style replaces the model
    assert request["body"]["plan_id"] == third["plan_id"] and not set(lineage(third)) & set(lineage(second)), (lineage(third), lineage(second))
    assert plan_of(third)["plan"]["palette"] != plan_of(second)["plan"]["palette"], plan_of(third)["plan"]["palette"]
    assert third["style_reference_asset"] is None and third["replaces_visual_id"] is None and third["headline"]["title"] == "Casque Bose QC45", third
    # The new version becomes the poster's, as for a change card.
    for _ in range(50):
        if get(f"creations/{poster}")["document"]["formats"]["feed"]["scene"]["visual_id"] == third["id"]:
            break
        page.wait_for_timeout(200)
    else:
        raise AssertionError("the restyled version is not the poster's selected one")
    expect(side).to_contain_text("Version 3 · à vérifier")

    # A tab of an older bundle (here this page, the bundle's header taken off what it sends) taps a paid card. The
    # server refuses the first request that would change something, here the save of the poster with the new style's
    # colours: its sentence is shown, no request was kept, the poster's revision is the same, no plan and no job were
    # made, and the same card is offered again, with its cost.
    made = lambda: (len(get(f"creations/{poster}/jobs")["items"]), len(versions()), get(f"creations/{poster}")["revision"])
    say(page, "style studio clair")
    expect(redo).to_be_visible()
    before, refusals = made(), []
    page.on("response", lambda response: refusals.append(response.url.split("/api/")[1]) if response.status == 409 else None)
    context.route("**/api/**", lambda route: route.continue_() if route.request.method == "GET" else
                  route.continue_(headers={name: value for name, value in route.request.headers.items() if name != "x-affiche-bundle"}))
    redo.click()
    expect(thread).to_contain_text("Cette page est une ancienne version de l’application")
    context.unroute("**/api/**")
    refused = spent()
    assert refused["card"]["kind"] == "restyle" and refused.get("done") and "request" not in refused and "job" not in refused, refused
    assert made() == before and refusals == [f"creations/{poster}"], (made(), before, refusals)
    expect(redo).to_have_count(1)
    page.wait_for_timeout(500)
    assert made() == before, made()
    # The page as the current bundle again: that card goes through. Its version was made with a saved style that was
    # removed since and cannot be read (a 500): a change of style does not look it up, so nothing stops it.
    looks, gone = [], str(uuid4())
    context.route("**/api/looks/*", lambda route: (looks.append(route.request.url), route.fulfill(status=500, json={"error": {"code": "server_error", "message_fr": "Le style de cette version n’a pas pu être lu."}})))
    context.route("**/creations/*/visuals", lambda route: route.fulfill(response=(response := route.fetch()), json={"items": [item | {"headline": item["headline"] | {"look_id": gone}} for item in response.json()["items"]]}))
    page.reload()
    expect(side).to_contain_text("Version 3 · à vérifier")
    asked = len(looks)
    assert asked, "the editor did not ask for the version's style when the poster opened"
    redo.click()
    expect(thread).to_contain_text("Version 4 prête.", timeout=30000)
    context.unroute("**/api/looks/*")
    context.unroute("**/creations/*/visuals")
    assert len(looks) == asked and spent()["request"]["body"]["headline"]["price"] is True, (looks, spent())
    assert made()[:2] == (before[0] + 1, 4), made()

    # Another format and the shop's identity on an existing poster: one sentence each, the way to the steps, nothing paid.
    before = paid()
    for message, sentence in (("fais-la aussi en format story", "Un autre format est une nouvelle affiche : dans Pas à pas, « Style », « Refaire en … »."),
                              ("ajoute le logo de la boutique", "Le logo et le contact de la boutique se règlent dans Pas à pas, « Boutique ».")):
        say(page, message)
        expect(last.locator("p")).to_have_text([sentence])
        expect(last.get_by_role("button")).to_have_text(["Pas à pas"])
    # A card kind of a later bundle (here the answer's kind is rewritten on its way): text, and no button to pay with.
    context.route("**/api/reads", lambda route: route.fulfill(response=(response := route.fetch()), json=response.json() | {"card": response.json()["card"] | {"kind": "recolour"}}))
    say(page, "style studio clair")
    expect(last.locator("p")).to_have_text(["Style : Studio clair"])
    expect(last.get_by_role("button")).to_have_count(0)
    context.unroute("**/api/reads")
    assert page.evaluate(THREAD, poster)["items"][-1]["card"]["kind"] == "recolour" and paid() == before, sent

    # The chat is taken by another tab while the photo's colours are read for « Couleurs du produit » (the answer about
    # the photo is held). When the colours come, this tab asks no plan and no scene.
    held = []
    context.route("**/api/product-inputs/*", lambda route: route.continue_() if held or route.request.method != "GET" else held.append(route))
    page.reload()
    say(page, "style couleur")
    expect(redo).to_be_visible()
    redo.click()
    expect(thread.locator(".chat-wait")).to_contain_text("Je lis les couleurs de la photo…")
    assert held and "request" not in spent(), (held, spent())
    other_tab = context.new_page()
    other_tab.set_default_timeout(10000)
    other_tab.on("pageerror", lambda error: errors.append(str(error)))
    other_tab.goto(f"{smoke.ORIGIN}/#message-{poster}")
    other_tab.get_by_role("button", name="Continuer ici").click()
    expect(page.get_by_text("Le chat est ouvert dans un autre onglet.")).to_be_visible()
    expect(other_tab.get_by_role("log")).to_contain_text("Rien n’a été envoyé pour cette demande.")
    held[0].continue_()
    context.unroute("**/api/product-inputs/*")
    page.wait_for_timeout(1500)
    assert paid() == before and "request" not in spent() and len(versions()) == 4, (sent, spent())
    other_tab.close()
    page.get_by_role("button", name="Continuer ici").click()
    expect(redo).to_have_count(1)  # the same card again, with its cost
    cancel.click()
    field.fill("")

    # The shop now has a logo and a contact (typed in the form of « Pas à pas », saved with the poster): the recap says
    # so, the wish is kept in the draft for the next message, and the poster is made with both. The shop's name is not
    # turned on by it.
    page.goto(f"{smoke.ORIGIN}/#message")
    switch.get_by_role("button", name="Pas à pas").click()
    page.locator(".intake details > summary").click()
    page.get_by_role("textbox", name="Nom de la boutique").fill("Original Phone Mada")
    page.get_by_label("Contact", exact=True).first.fill("034 12 345 67")
    page.locator("label.file-pick", has_text="Logo").locator("input[type=file]").set_input_files(product)
    expect(page.get_by_alt_text("Logo de la boutique")).to_be_visible()
    switch.get_by_role("button", name="Message").click()
    branded = new_poster(f"Enceinte Bose Flex, 250 000 Ar, {with_identity}", "Avec le logo et le contact de la boutique", product)
    document = get(f"creations/{branded}")["document"]
    chosen = {"logo": True, "shop_name": False, "contact": True}
    assert drafts[-1]["brand_selection"] == chosen and document["include"] == chosen, (drafts[-1], document["include"])
    assert document["brand_snapshot"]["contact"] == "034 12 345 67" and document["brand_snapshot"]["logo_asset"], document["brand_snapshot"]
    assert any(layer["kind"] == "logo" for layer in document["formats"]["feed"]["layers"]), document["formats"]["feed"]["layers"]
    looks_right(page, "poster with the shop's identity", "chat-identity-1366.png")
    # « Sans logo ni contact » against the form's own ticks (logo and contact ticked in « Pas à pas » for the next
    # poster): the recap says it, and the poster is made without them. The shop's name, ticked too, is not its matter.
    page.goto(f"{smoke.ORIGIN}/#message")
    switch.get_by_role("button", name="Pas à pas").click()
    page.locator(".intake details > summary").click()
    for name in ("Logo", "Nom de la boutique", "Contact"):
        page.get_by_role("checkbox", name=name, exact=True).check()
    switch.get_by_role("button", name="Message").click()
    plain = new_poster("Enceinte Bose Mini, 120 000 Ar, sans logo ni contact", "Sans le logo ni le contact de la boutique", product)
    off = {"logo": False, "shop_name": True, "contact": False}
    assert drafts[-1]["offer"]["title"] == "Enceinte Bose Mini" and drafts[-1]["brand_selection"] == off, drafts[-1]
    assert get(f"creations/{plain}")["document"]["include"] == off
    # Asked in one message, the price corrected in the next: the draft carries the wish, and the new recap keeps its line.
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(thread).to_contain_text("Ajoutez une photo du produit.")
    page.locator(".composer input[type=file]").set_input_files(product)
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    say(page, f"Enceinte Bose Micro, 150 000 Ar, {with_identity}")
    expect(recap.locator(":scope > small").nth(1)).to_have_text("Avec le logo et le contact de la boutique")
    say(page, "140 000 Ar")
    expect(recap.locator(".recap-price")).to_have_text(re.compile(r"^140\s000 Ar$"))
    expect(recap.locator(":scope > small").nth(1)).to_have_text("Avec le logo et le contact de la boutique")
    assert bodies[-1]["draft"]["identity"] is True, bodies[-1]
    context.close()


def walk_photo(browser, errors, product, other):
    """D-TEXT-FIRST-007: an image sent on an existing poster is a product photo and is never read past. It offers the
    editor's copy of the poster on the new photo: nothing paid, no paid card added to the chat, the copy opened in
    « Pas à pas » without a version, the poster left behind unchanged. The features warning follows the request's
    words (ADR-125). Its own session."""
    reads, sent = [], {"product-inputs": [], "copies": [], "scenes": [], "refinements": []}

    def seen(request):
        if request.method != "POST":
            return
        if request.url.endswith("/api/reads"):
            reads.append(request.post_data_json)
        for path in sent:
            if request.url.endswith("/" + path):
                sent[path].append((request.headers["idempotency-key"], request.post_data_json, request.url))

    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    context.on("request", seen)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: print(f"HTTP {response.status} {response.url}", flush=True) if response.status >= 400 else None)
    sign_in(page)
    page.get_by_role("link", name="Créer une affiche").click()
    page.wait_for_url("**/#message")
    thread, files = page.get_by_role("log"), page.locator(".composer input[type=file]")
    last = thread.locator(".bubble.bot").last
    first_tap, copy = thread.get_by_role("button", name="Créer l’affiche"), thread.get_by_role("button", name="Copier avec cette photo")
    get = lambda path: page.request.get(f"{smoke.ORIGIN}/api/{path}").json()
    asset = lambda image: re.search(r"/api/assets/([a-f0-9]{64})", image.get_attribute("src"))[1]

    files.set_input_files([product])
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    expect(page.locator(".tray button.pic-role")).to_have_text("Produit")  # a new poster: the label is the swap button
    say(page, "Enceinte Marshall Willen, 450 000 Ar")
    first_tap.click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    expect(thread).to_contain_text("Version 1 prête.", timeout=30000)
    poster = page.url.split("#message-")[1]
    source = get(f"creations/{poster}")
    title = source["document"]["offer"]["title"]
    read_before, scenes_before = len(reads), len(sent["scenes"])

    # ADR-125, first: the warning stands under a request for features, and not under a scene's words alone.
    create, cancel = thread.get_by_role("button", name="Créer", exact=True), thread.get_by_role("button", name="Annuler")
    say(page, "fond bleu, ajoute ses caractéristiques")
    expect(create).to_be_visible()
    expect(last.get_by_text(WARNING, exact=True)).to_be_visible()
    cancel.click()
    page.get_by_label("Votre message").fill("")
    say(page, "fond plus sombre")
    expect(create).to_be_visible()
    expect(last.get_by_text(WARNING, exact=True)).to_have_count(0)
    expect(create).to_have_accessible_description(COST)
    cancel.click()
    page.get_by_label("Votre message").fill("")
    read_before = len(reads)

    # On the poster, an attached image is a product photo: plain words, nothing to swap, never an inspiration.
    files.set_input_files([other])
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    expect(page.locator(".tray .pic")).to_have_text("Produit")
    expect(page.locator(".tray .pic-role")).to_have_count(0)
    say(page, "Use this as product")
    expect(last).to_contain_text("Cette affiche garde sa photo. Je peux en faire une copie avec la nouvelle photo : même titre, même prix.")
    expect(last).to_contain_text("La copie s’ouvre dans Pas à pas, où vous créez son image.")
    expect(last).to_contain_text("Votre message n’est pas lu avec une photo : envoyez-le ensuite.")
    expect(copy).to_be_enabled()
    expect(copy).to_have_accessible_description("La copie est gratuite. Sa nouvelle image coûtera 1 crédit.")
    new_photo = asset(thread.locator(".bubble.me").last.locator(".pic img"))
    assert len(reads) == read_before, reads[read_before:]  # the message was not sent to the paid reader
    stored = page.evaluate(THREAD, poster)
    assert [picture["asset"] for picture in stored["draft"]["pictures"]] == source_photos(get, source), stored["draft"]  # the thread's draft keeps the poster's own photo
    card = stored["items"][-1]
    assert card["card"]["kind"] == "photo" and "spent" not in card and [picture["asset"] for picture in card["card"]["pictures"]] == [new_photo], card

    # The copy's answer is lost: the card stays, and the same tap on this page sends the same two requests. One copy.
    lost = []

    def lose_answer(route):
        route.fetch()
        lost.append(route.request.url)
        route.abort()
    context.route("**/copies", lose_answer)
    copy.click()
    expect(last.locator(".why[role=alert]")).to_be_visible()
    context.unroute("**/copies")
    assert len(lost) == 1 and page.url.endswith(f"#message-{poster}"), (lost, page.url)
    expect(copy).to_be_enabled()
    copy.click()
    # The copy opens in « Pas à pas », at its own address, with the editor's notice and no version.
    page.wait_for_url(re.compile(r"#[a-f0-9-]{36}$"))
    made = page.url.split("#")[1]
    assert made != poster
    expect(page.get_by_text("Copie de l’affiche avec la nouvelle photo, sans version : générez-la quand vous êtes prêt. L’affiche d’origine est conservée.")).to_be_visible()
    inputs, copies = sent["product-inputs"], sent["copies"]
    assert len(inputs) == 2, inputs  # the poster's own, then one for the copy: the second tap made no other
    assert inputs[1][1]["photo_assets"] == [new_photo] and inputs[1][1]["supersedes_id"] == source["document"]["input_id"], inputs
    assert len(copies) == 2 and copies[0][:2] == copies[1][:2], copies
    copied = get(f"creations/{made}")
    assert copies[0][1] == {"source_revision": source["revision"], "reason": "replace_input", "new_input_id": copied["document"]["input_id"]}, copies
    assert len([row for row in get("creations")["items"] if row["title"] == title]) == 2  # the poster and its one copy
    assert copied["document"]["input_id"] != source["document"]["input_id"] and source_photos(get, copied) == [new_photo]
    assert not get(f"creations/{made}/visuals")["items"] and len(get(f"creations/{poster}/visuals")["items"]) == 1
    # Its title and price, drawn in the source's image, are layers to see again until its own image draws them. The
    # editor's save carries that: asked until it has arrived.
    for _ in range(50):
        layers = {layer.get("role"): layer for layer in get(f"creations/{made}")["document"]["formats"]["feed"]["layers"]}
        if layers["title"]["visible"] and layers["price"]["visible"]:
            break
        page.wait_for_timeout(200)
    else:
        raise AssertionError("the copy's title and price are still hidden")
    assert [layer["id"] for layer in get(f"creations/{made}")["document"]["formats"]["feed"]["layers"]] == [layer["id"] for layer in source["document"]["formats"]["feed"]["layers"] if layer["kind"] != "product_cutout"]
    after = get(f"creations/{poster}")
    assert after["revision"] == source["revision"] and after["document"] == source["document"]  # the poster left behind is unchanged
    # Nothing was read or paid for the copy, and its image is the editor's own « Générer ».
    assert len(reads) == read_before and len(sent["scenes"]) == scenes_before and not sent["refinements"], (reads[read_before:], sent)
    # The guided copy has no chat history or image. Its chat takes the seller back to the same offer.
    page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Message").click()
    page.wait_for_url(f"**/#message-{made}")
    expect(page.locator(".hello-q")).to_have_text(title)
    expect(thread).to_contain_text("pour créer la première image")
    expect(first_tap).to_have_count(0)
    thread.get_by_role("button", name="Vérifier l’offre").click()
    page.wait_for_url(f"**/#{made}")
    expect(page.get_by_role("region", name="Offre à générer")).to_contain_text(title)
    assert len(reads) == read_before and len(sent["scenes"]) == scenes_before
    generate = page.get_by_role("button", name="Générer l’affiche")
    expect(generate).to_be_enabled()
    generate.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text(COST)
    assert len(sent["scenes"]) == scenes_before
    dialog.get_by_role("button", name="Annuler").click()
    assert len(sent["scenes"]) == scenes_before
    generate.click()
    dialog.get_by_role("button", name="Lancer la génération").click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    assert len(sent["scenes"]) == scenes_before + 1 and sent["scenes"][-1][2].endswith(f"/{made}/scenes")
    assert len(get(f"creations/{made}/visuals")["items"]) == 1
    assert get(f"creations/{poster}")["revision"] == source["revision"]
    # Back on the poster's chat: its card is over, and no paid card was added.
    page.goto(f"{smoke.ORIGIN}/#message-{poster}")
    expect(thread).to_contain_text("La copie est créée : retrouvez-la dans Mes affiches. Cette affiche reste telle quelle.")
    expect(copy).to_have_count(0)
    expect(first_tap).to_have_count(0)
    context.close()


def source_photos(get, creation):
    return get(f"product-inputs/{creation['document']['input_id']}")["photo_assets"]


def walk_choice_phone(browser, errors):
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    sign_in(page)
    expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
    assert page.evaluate(smoke.NO_SIDEWAYS)
    smoke.check_contrast(page, "start choice, 360 px")
    smoke.check_one_blur(page, "start choice, 360 px")
    page.screenshot(path=str(OUT / "choice-360.png"))
    page.get_by_role("link", name="Créer une affiche").tap()
    # « Pas à pas » is remembered too: the form, and the switch from then on.
    page.get_by_role("button", name=re.compile("^Pas à pas")).tap()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    assert page.evaluate(START) == "steps"
    page.reload()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    expect(page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Pas à pas")).to_have_attribute("aria-pressed", "true")
    context.close()


LINE_REFUSED = ("Une ligne de la boutique : 40 caractères au plus, sans guillemet droit, sans montant, remise ni numéro (le prix et "
                "le contact ont leurs champs). Trois lignes au plus, toutes différentes.")
LOOK_LIMIT = "Vous avez déjà enregistré le nombre maximal de styles."
NETWORK = "Connexion interrompue. Vos modifications restent dans cet onglet."


def walk_kit(browser, errors, product, data, app):
    """The seller's kit in Message (D-KIT-002 … 006): prices as sellers write them, the owner's scene words and the shop's
    lines in the first message, the recap's switch, a line asked on an existing poster, and the steps before a paid scene
    that can fail (keeping a line, reading a style model) with nothing paid; after any failure the recap shows what the
    retry sends. Its own session; it adds lines to the shop's profile, so it is the last walk of this server. `app`: the
    server's, whose image service is made to refuse one scene."""
    reads, scenes, profiles, looks = [], [], [], []

    def seen(request):
        if request.method == "POST" and request.url.endswith("/api/reads"):
            reads.append(request.headers["idempotency-key"])
        if request.method == "POST" and request.url.endswith("/scenes"):
            scenes.append(request.post_data_json)
        if request.method == "POST" and request.url.endswith("/looks"):
            looks.append(request.post_data_json)
        if request.method == "PUT" and request.url.endswith("/api/shop-profile"):
            profiles.append(request.post_data_json)

    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    context.on("request", seen)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: print(f"HTTP {response.status} {response.url}", flush=True) if response.status >= 400 else None)
    sign_in(page)
    page.get_by_role("link", name="Créer une affiche").click()
    page.wait_for_url("**/#message")
    thread = page.get_by_role("log")
    recap, last = thread.locator(".bubble.bot", has=page.locator(".recap")).last, thread.locator(".bubble.bot").last
    create = thread.get_by_role("button", name="Créer l’affiche")
    get = lambda path: page.request.get(f"{smoke.ORIGIN}/api/{path}").json()
    credits = lambda: get("balance")["available"]

    def prompts(poster):  # the scene prompts of a poster as the image model gets them: its jobs, in the temporary database
        with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
            rows = store.execute("SELECT input_json FROM poster_jobs WHERE creation_id=? AND kind='scene' ORDER BY created_at", (poster,))
            return [json.loads(row[0])["prompt"] for row in rows]

    def attach(*files):
        page.locator(".composer input[type=file]").set_input_files(list(files))
        expect(page.locator(".tray .pic")).to_have_count(len(files))
        expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)

    assert get("shop-profile")["lines"] == []
    attach(product)
    # Two amounts read (D-KIT-002): never guessed, one button each. A tap is the owner's own figure: the recap comes with
    # no second read.
    say(page, "Redmi Note 13 700 000")
    expect(last).to_contain_text(re.compile(r"J’ai lu 13\s700\s000 Ar ou 700\s000 Ar : lequel est le prix \?"))
    expect(last.get_by_role("button")).to_have_text([re.compile(r"^13\s700\s000 Ar$"), re.compile(r"^700\s000 Ar$")])
    last.get_by_role("button", name=re.compile(r"^700\s000 Ar$")).click()
    expect(recap.locator(".recap b")).to_have_text("Redmi Note")
    expect(recap.locator(".recap-price")).to_have_text(re.compile(r"^700\s000 Ar$"))
    assert len(reads) == 1, reads
    # « 250k » is a price.
    say(page, "250k")
    expect(recap.locator(".recap-price")).to_have_text(re.compile(r"^250\s000 Ar$"))
    # The owner's scene words, a line of the shop and a part the poster cannot use, in one message (D-KIT-003 … 005): the
    # recap says what will be used, the new line is offered to keep, the unused part is said apart.
    say(page, "scène : fond rouge, lumière douce ligne : Garantie 6 mois pas utilisé : livraison demain")
    expect(recap).to_contain_text("Scène : Studio clair, avec vos mots : « fond rouge, lumière douce »")
    lines = recap.get_by_role("checkbox", name=re.compile("^Lignes de la boutique : "))
    expect(lines).to_have_accessible_name("Lignes de la boutique : Garantie 6 mois")
    expect(lines).to_be_checked()
    expect(recap.locator(".recap-offer")).to_contain_text("« Garantie 6 mois » : nouvelle, gardée pour la boutique.")
    expect(recap.locator(".refusal")).to_have_text("« livraison demain » : je ne sais pas le mettre sur l’affiche. Dites-le autrement.")
    assert len(reads) == 3, reads
    # The line is kept before anything else: refused there (here the server's own refusal, put in its way), the tap stops
    # with the server's sentence, and the recap comes again with « Ne pas garder » (« Pas à pas » has no lines to
    # correct). No poster, nothing paid; dropped, the line leaves the recap; the next message offers it again.
    before = credits()
    context.route("**/api/shop-profile", lambda route: route.fulfill(status=422, json={"error": {"code": "shop_line_refused", "message_fr": LINE_REFUSED, "field": "lines"}})
                  if route.request.method == "PUT" else route.continue_())
    create.click()
    expect(thread.get_by_role("alert")).to_have_text(LINE_REFUSED)
    context.unroute("**/api/shop-profile")
    drop = recap.get_by_role("button", name="Ne pas garder « Garantie 6 mois »")
    expect(drop).to_be_visible()
    expect(recap).to_contain_text("Scène : Studio clair, avec vos mots : « fond rouge, lumière douce »")
    expect(recap.get_by_role("button", name="Créer l’affiche")).to_be_visible()
    expect(thread.get_by_role("button", name="Corriger dans Pas à pas")).to_have_count(0)
    assert page.url.endswith("#message") and not scenes and credits() == before and get("shop-profile")["lines"] == [], (page.url, scenes)
    drop.click()
    expect(recap.locator(".recap-offer")).to_have_count(0)
    expect(lines).to_have_count(0)
    expect(recap.get_by_role("button", name="Créer l’affiche")).to_be_visible()
    say(page, "scène : fond rouge, lumière douce ligne : Garantie 6 mois")
    expect(recap).to_contain_text("Scène : Studio clair, avec vos mots : « fond rouge, lumière douce »")
    expect(lines).to_be_checked()
    create.click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    poster = page.url.split("#message-")[1]
    expect(thread).to_contain_text("Version 1 prête.", timeout=30000)
    # Kept for the shop, then drawn: exactly the lines the recap showed, and the owner's words as the scene's adjustment.
    assert get("shop-profile")["lines"] == ["Garantie 6 mois"] and profiles[-1]["lines"] == ["Garantie 6 mois"], profiles
    assert len(scenes) == 1 and scenes[0]["headline"]["lines"] == ["Garantie 6 mois"] and scenes[0]["adjustment_fr"] == "fond rouge, lumière douce", scenes
    [made] = prompts(poster)
    assert "Garantie 6 mois" in made and "fond rouge, lumière douce" in made, made
    assert get(f"creations/{poster}/visuals")["items"][0]["headline"]["shop_lines"] == ["Garantie 6 mois"]
    # The review lists the line among the texts to check, and the file is confirmed with it.
    thread.get_by_role("button", name="Vérifier", exact=True).click()
    panel = page.locator(".final-preview")
    expect(panel.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    panel.get_by_text("Détails à vérifier", exact=True).click()
    expect(panel.locator("li", has_text="Lignes de la boutique")).to_have_text("Lignes de la boutique Garantie 6 mois")
    smoke.download_review(page)
    panel.get_by_role("button", name="Fermer").click()

    # Digits after the name are its price, with no unit (D-KIT-002). The shop's line is in the recap, its switch on by
    # default; switched off, no line is drawn on this poster, whatever the editor's own box says.
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(thread).to_contain_text("Ajoutez une photo du produit.")
    attach(product)
    say(page, "casque sony wh-ch720n noir 250000")
    expect(recap.locator(".recap b")).to_have_text("casque sony wh-ch720n noir")
    expect(recap.locator(".recap-price")).to_have_text(re.compile(r"^250\s000 Ar$"))
    expect(lines).to_be_checked()
    expect(recap.locator(".recap-offer")).to_have_count(0)
    lines.uncheck()
    # The poster is made, then its scene cannot be prepared (its plan lost on the way): nothing paid. After a reload the
    # recap is a new poster's again, its switch as the owner left it, and the tap draws no line, whatever the editor's
    # box (whose default draws them) holds for this poster (review t-kit-frontend r1, 1).
    before = credits()
    context.route("**/plans", lambda route: route.abort("failed") if route.request.method == "POST" else route.continue_())
    create.click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    second = page.url.split("#message-")[1]
    expect(thread).to_contain_text(NETWORK)
    context.unroute("**/plans")
    assert len(scenes) == 1 and credits() == before, scenes
    page.reload()
    expect(lines).to_have_accessible_name("Lignes de la boutique : Garantie 6 mois")
    expect(lines).not_to_be_checked()
    expect(recap).to_contain_text("Scène : Studio clair")
    create.click()
    expect(thread).to_contain_text("Version 1 prête.", timeout=30000)
    assert len(scenes) == 2 and "lines" not in scenes[1]["headline"] and "adjustment_fr" not in scenes[1], scenes[1]
    assert "Garantie 6 mois" not in prompts(second)[0]
    # On a poster, a line asked by message is a card of its own (D-KIT-005), paid as a new image: the tap keeps the line
    # for the shop first, then one scene draws the shop's lines.
    say(page, "ligne : Livraison gratuite")
    expect(last).to_contain_text("Je garde « Livraison gratuite » dans les lignes de la boutique et je refais l’affiche avec.")
    expect(last).to_contain_text(REDRAW)
    expect(last).to_contain_text(COST)
    # Every line the new image draws, the one kept before included (review t-kit-frontend r1, 3).
    expect(last).to_contain_text("Lignes de la boutique : Garantie 6 mois · Livraison gratuite")
    # The line refused when kept (the server's own refusal, put in its way): its sentence, and the way to « Mon compte »
    # where the shop's lines are; never « Corriger dans Pas à pas », which has none. Nothing kept, nothing paid.
    before = credits()
    context.route("**/api/shop-profile", lambda route: route.fulfill(status=422, json={"error": {"code": "shop_line_refused", "message_fr": LINE_REFUSED, "field": "lines"}})
                  if route.request.method == "PUT" else route.continue_())
    last.get_by_role("button", name="Garder et refaire l’affiche").click()
    expect(last.get_by_role("alert")).to_have_text(LINE_REFUSED)
    context.unroute("**/api/shop-profile")
    account = last.get_by_role("link", name="Modifier les lignes dans Mon compte")
    expect(account).to_be_visible()
    expect(last.get_by_role("button")).to_have_count(0)
    assert len(scenes) == 2 and credits() == before and get("shop-profile")["lines"] == ["Garantie 6 mois"], scenes
    account.click()
    page.wait_for_url("**/#compte")
    expect(page.locator(".shop-account").get_by_label("Ligne 1", exact=True)).to_have_value("Garantie 6 mois")
    page.goto(f"{smoke.ORIGIN}/#message-{second}")
    expect(account).to_be_visible()  # the card as it was left
    say(page, "ligne : Livraison gratuite")
    expect(last).to_contain_text("Je garde « Livraison gratuite » dans les lignes de la boutique et je refais l’affiche avec.")
    last.get_by_role("button", name="Garder et refaire l’affiche").click()
    expect(thread).to_contain_text("Version 2 prête.", timeout=30000)
    kept = ["Garantie 6 mois", "Livraison gratuite"]
    assert get("shop-profile")["lines"] == kept and profiles[-1]["lines"] == kept, profiles
    assert len(scenes) == 3 and scenes[2]["headline"]["lines"] == kept, scenes[2]
    assert len(prompts(second)) == 2 and all(line in prompts(second)[1] for line in kept)

    # A style model that cannot be read yet (D-KIT-006): the shop's limit of styles (put in its way), then a lost answer
    # while its brief is read. Each time the card says why, no scene is asked and nothing is paid; « Réessayer » (the
    # recap offered again) waits on the same brief, never a second one. That recap is a new poster's again, the poster
    # made: the scene words and the shop's lines it shows are what the tap sends (review t-kit-frontend r1, 1).
    model = OUT / "style-model.png"
    picture = Image.new("RGB", (1000, 1250), "#14213d")
    ImageDraw.Draw(picture).ellipse((200, 300, 800, 900), fill="#fca311")
    picture.save(model)
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(thread).to_contain_text("Ajoutez une photo du produit.")
    attach(product, model)
    page.locator(".tray .pic").nth(1).locator(".pic-role").click()
    say(page, "Enceinte JBL Go 4, 150 000 Ar")
    say(page, "scène : fond bleu nuit")
    shown = "Lignes de la boutique : Garantie 6 mois · Livraison gratuite"

    def same_recap():
        expect(recap).to_contain_text("Scène : votre modèle de style (lu, puis gardé dans votre kit), avec vos mots : « fond bleu nuit »")
        expect(lines).to_have_accessible_name(shown)
        expect(lines).to_be_checked()
    same_recap()
    before, asked = credits(), len(scenes)
    context.route("**/looks", lambda route: route.fulfill(status=409, json={"error": {"code": "look_limit", "message_fr": LOOK_LIMIT}})
                  if route.request.method == "POST" else route.continue_())
    create.click()
    expect(thread).to_contain_text(LOOK_LIMIT)
    context.unroute("**/looks")
    third = page.url.split("#message-")[1]
    expect(create).to_have_count(1)
    same_recap()
    assert len(scenes) == asked and credits() == before and len(looks) == 1, (scenes, looks)
    context.route("**/api/jobs/*", lambda route: route.abort("failed"))
    create.click()
    expect(thread).to_contain_text(NETWORK)
    context.unroute("**/api/jobs/*")
    expect(create).to_have_count(1)
    same_recap()
    assert len(scenes) == asked and credits() == before and len(looks) == 2, (scenes, looks)
    create.click()
    expect(thread).to_contain_text("Version 1 prête.", timeout=30000)
    assert len(looks) == 2, looks  # the brief asked before, waited on again
    made = [item for item in get("looks")["items"] if item["reference_asset"] == looks[-1]["reference_asset"]]
    assert len(made) == 1 and scenes[-1]["headline"]["look_id"] == made[0]["id"] and "style_reference_asset" not in scenes[-1], (made, scenes[-1])
    assert scenes[-1]["headline"]["lines"] == kept and scenes[-1]["adjustment_fr"] == "fond bleu nuit", scenes[-1]
    expect(thread).to_contain_text(f"Votre modèle de style est gardé dans votre kit : « {made[0]['name']} ».")
    assert [job["kind"] for job in get(f"creations/{third}/jobs")["items"]].count("look") == 1

    # The kit row (D-KIT-009, 012). A new poster starts from the last choices: the model just read, chosen and first, the
    # model's own title. Another of the shop's models chosen as a chip and a title style are what the scene asks, and the
    # poster after starts with them.
    chips = page.get_by_role("group", name="Style de l’affiche").get_by_role("button")
    title = page.locator(".composer .kit-title select")  # its label's name holds the option shown
    chip = lambda name: chips.filter(has_text=re.compile("^" + re.escape(name) + "$"))
    other = next(item for item in get("looks")["items"] if item["id"] != made[0]["id"])
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(thread).to_contain_text("Ajoutez une photo du produit.")
    expect(chips.first).to_have_text(made[0]["name"])
    expect(chips.first).to_have_attribute("aria-pressed", "true")
    expect(title).to_have_value("")  # « Celui du modèle »
    attach(product)
    chip(other["name"]).click()
    title.select_option("condense")
    say(page, "Enceinte JBL Flip 6, 200 000 Ar")

    def kit_recap():
        expect(recap).to_contain_text(f"Scène : {other['name']}")
        expect(recap).to_contain_text("Titre : Gras condensé")
        expect(lines).to_have_accessible_name(shown)
        expect(lines).to_be_checked()
    kit_recap()
    # The image service refuses this scene (a stub that fails once): its credit comes back, and the recap after it is a new
    # poster's again, with the saved look, the title and the lines the retry sends (review t-kit-frontend r1, 1).
    service, before = app.state.poster_service, credits()
    kept_provider, service.provider = service.provider, smoke.StubProvider(["refused"])
    try:
        create.click()
        page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
        fourth = page.url.split("#message-")[1]
        expect(thread).to_contain_text("Le service d’images a refusé cette demande", timeout=30000)
    finally:
        service.provider = kept_provider
    expect(thread).to_contain_text("Votre crédit vous a été rendu.")
    expect(create).to_have_count(1)
    kit_recap()
    failed = scenes[-1]
    assert credits() == before and [job["status"] for job in get(f"creations/{fourth}/jobs")["items"] if job["kind"] == "scene"] == ["failed"]
    create.click()
    expect(thread).to_contain_text("Version 1 prête.", timeout=30000)
    assert len(scenes) >= 2 and scenes[-1] is not failed
    for sent in (failed, scenes[-1]):
        assert sent["headline"]["look_id"] == other["id"] and sent["headline"]["title_style"] == "condense" and sent["headline"]["lines"] == kept, sent
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(chips.first).to_have_text(other["name"])
    expect(chips.first).to_have_attribute("aria-pressed", "true")
    expect(title).to_have_value("condense")

    # « Garder cette scène comme modèle » (D-KIT-010) in the final panel Message shares with « Pas à pas »: no dialog, no
    # credit. The model is in « Mon kit » and offered as a chip; the panel then says so in place of the button.
    page.goto(f"{smoke.ORIGIN}/#message-{fourth}")
    thread.get_by_role("button", name="Vérifier", exact=True).click()
    panel = page.locator(".final-preview")
    expect(panel.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    smoke.download_review(page)
    name = ("Modèle " + get(f"creations/{fourth}")["document"]["offer"]["title"])[:40].strip()
    scene = get(f"creations/{fourth}")["document"]["formats"]["feed"]["scene"]["visual_id"]
    before, count, notice = credits(), len(get("looks")["items"]), page.locator(".message.notice")
    panel.get_by_text("Autres actions", exact=True).click()
    keep = panel.get_by_role("button", name="Garder cette scène comme modèle")
    expect(keep.locator("xpath=following-sibling::p[1]")).to_have_text("Sans crédit.")
    with page.expect_response(lambda response: response.url.endswith(f"/creations/{fourth}/looks")) as answer:
        keep.click()
    assert answer.value.status == 202 and answer.value.json().get("reused") is None, answer.value.json()
    expect(notice).to_contain_text(f"Le modèle « {name} » est dans votre kit.")
    expect(page.locator(".confirm")).to_have_count(0)
    assert looks[-1] == {"name": name, "visual_id": scene}, looks[-1]
    assert len(get("looks")["items"]) == count + 1 and credits() == before
    # The panel says it in place of the button, which is gone: no second tap (the server's answer to one is test_looks').
    expect(panel.get_by_text(f"Cette scène est un modèle de votre kit : « {name} ».")).to_be_visible()
    expect(keep).to_have_count(0)
    panel.get_by_role("button", name="Fermer").click()
    smoke.go(page, "Mon kit")
    expect(page.locator(".look-card", has_text=name)).to_have_count(1)
    page.locator(".look-card", has_text=name).click()
    lettering = page.get_by_role("dialog", name=name).locator("li", has_text="Comme sur l’affiche modèle")
    expect(lettering).to_have_text("TitreComme sur l’affiche modèle")  # never the brief's English
    page.keyboard.press("Escape")
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(chip(name)).to_have_count(1)

    # The title style in « Pas à pas » (D-KIT-012): the version's own is shown, another one is what the next scene asks.
    # « Mon kit » keeps a default on this device, which a version's own title never hides. With the texts written by the
    # renderer, the style is the title's font (v2 point 8).
    tab = lambda label: page.get_by_role("tab", name=label, exact=True)
    styled = page.get_by_label("Style du titre", exact=True)

    def open_steps():  # a confirmed poster opens on its file in the editor too: closed, to reach « Style »
        page.goto(f"{smoke.ORIGIN}/#{fourth}")
        expect(page.get_by_role("link", name="Télécharger le PNG")).to_be_visible()
        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
        tab("Style").click()

    open_steps()
    expect(styled).to_have_value("condense")
    styled.select_option("sport")
    page.get_by_role("button", name=re.compile("^Nouvelle version")).click()
    with page.expect_request(lambda request: request.method == "POST" and request.url.endswith("/scenes")) as sent:
        page.get_by_role("button", name="Lancer la génération").click()
    assert sent.value.post_data_json["headline"]["title_style"] == "sport" and sent.value.post_data_json["headline"]["look_id"] == other["id"], sent.value.post_data_json
    made_job = sent.value.response().json()["job_id"]

    def until(holds, what):  # the server asked again until it says so (a fetch in wait_for_function resolves at once)
        for _ in range(120):
            if holds():
                return
            page.wait_for_timeout(250)
        raise AssertionError(what)

    until(lambda: get(f"jobs/{made_job}")["status"] == "succeeded", "the new version was not made")
    page.goto(f"{smoke.ORIGIN}/#styles")  # the version's review may be opening: the address leaves it
    default = page.get_by_label("Style du titre", exact=True)
    expect(default).to_have_value("sport")  # the last one chosen, in « Pas à pas »
    default.select_option("serif")
    open_steps()
    selected = get(f"creations/{fourth}")["document"]["formats"]["feed"]["scene"]["visual_id"]
    drawn = next(item for item in get(f"creations/{fourth}/visuals")["items"] if item["id"] == selected)["headline"]["title_style"]
    expect(styled).to_have_value(drawn)
    # Opening a version shows its own title and leaves the default as chosen: only the seller's choice changes it (the
    # lead's decision on review t-kit-frontend r1, 7).
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(title).to_have_value("serif")  # « Mon kit »'s default
    open_steps()
    tab("Textes").click()
    page.get_by_label("Dessiner les textes dans l’image").uncheck()
    tab("Style").click()
    expect(page.locator("#aide-style-titre")).to_have_text("Le titre écrit sur l’affiche prend la police de ce style.")
    font = lambda: next((layer["font_id"], layer["weight"]) for layer in get(f"creations/{fourth}")["document"]["formats"]["feed"]["layers"] if layer["role"] == "title")
    for style, saved in (("serif", ("noto-serif", 700)), ("sport", ("montserrat-black-italic", 900)), ("moderne", ("noto-sans", 700))):
        styled.select_option(style)
        until(lambda: font() == saved, f"the title layer did not take {saved} for {style}: {font()}")
    page.goto(f"{smoke.ORIGIN}/#message")
    expect(title).to_have_value("moderne")  # the last one chosen, in « Pas à pas »
    context.close()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    product = OUT / "product.png"
    photo = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(photo).rounded_rectangle((250, 160, 750, 840), 50, fill="#202020")
    photo.save(product)
    inspiration = smoke.ROOT / "frontend/public/styles/sombre.jpg"
    other = OUT / "product-other.png"  # the same product, another photo
    again = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(again).ellipse((220, 220, 780, 780), fill="#1b3a6b")
    again.save(other)
    small = [OUT / f"small-{index}.png" for index in range(5)]
    for index, file in enumerate(small):  # under the server's 800 px, each its own file
        Image.new("RGB", (600, 600), (40 * index, 90, 160)).save(file)
    broken, animated = OUT / "broken.png", OUT / "animated.webp"
    broken.write_bytes(b"not an image")
    Image.new("RGB", (64, 64), "red").save(animated, save_all=True, append_images=[Image.new("RGB", (64, 64), "blue")], duration=200)
    errors = []
    with tempfile.TemporaryDirectory(prefix="affiche-chat-") as data, tempfile.TemporaryDirectory(prefix="affiche-chat-fail-") as failing:
        server = smoke.serve(data, formats_enabled="feed,square,story")
        with (OUT / "vite.log").open("w", encoding="utf-8") as log:
            vite = subprocess.Popen(["node", str(smoke.ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1"],
                                    cwd=smoke.ROOT / "frontend", stdout=log, stderr=log,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True, channel=os.environ.get("SMOKE_CHANNEL") or None)
                    try:
                        session = walk_desktop(browser, errors, product, inspiration)
                        walk_phone(browser, errors, session)
                        walk_layout(browser, errors, session, product)
                        walk_two_tabs(browser, errors, session, product)
                        walk_lockless(browser, errors, session)
                        walk_titles(browser, errors, session)
                        walk_slow_read(browser, errors, session)
                        walk_uploads(browser, errors, session, small, broken, animated)
                        walk_guards(browser, errors, session)
                        walk_late_401(browser, errors, session)
                        walk_changes(browser, errors, session, data)  # last of this server: it signs in again
                        walk_rest(browser, errors, product, inspiration)  # its own session; it fills the shop's profile
                        walk_photo(browser, errors, product, other)
                        walk_choice_phone(browser, errors)
                        walk_sign_out(browser, errors, product)
                        walk_kit(browser, errors, product, data, server[0].config.app)  # last of this server: it gives the shop its lines
                        smoke.stop(*server)
                        server = smoke.serve(failing, stub_fail="provider_error")
                        walk_failed(browser, errors, product)
                        assert not errors, errors
                        print("Chat smoke passed: choice and remembered start view, one message with two images to a confirmed download, "
                              "reload in the middle and before the job is known (kept request sent again), stale kept request refused, « Reprendre » never automatic, transient refusal keeps the request, one chat per device (lock lost and taken back before /scenes), no Web Locks, late read after close, no photo, no price, lost answer, form to chat and recap refresh, editor remount measured, a scene change (« Annuler », reload with the answer lost, one refine job), a change asked on an older version shown (drawn price, whole new image), a brand set apart from the title on a version still to check with its list line, a reload between the saved words and the request, a refused scene then a later price card with « Remettre les textes de l’image » still offered and used, a failed save keeps the message unread, an unsaved step edit read after its save, a subtitle typed in steps kept out of the request, a subtitle added and removed, a kept old price card replayed as it left, old stored answers converted, drawn texts switched off refused with nothing sent, the chat taken during a selection and during the save of a card's words, no second paid card while one waits, a removed style that cannot be read stops a card, a version's accent kept under « Aux couleurs du produit », a late plan and a late plan revision after the chat was taken, a kept plan refused with the way to the steps, a version made but not listed, a pending read never replaced from another poster, a free title change and an old free price card on a poster without drawn words, the way to the steps for a brand there, the list of modifications folded at 360 px and open on desktop, photos already used, refused images and a fifth one, the small-photo agreement, a refused download said in the chat, the version limit at 10, 11 and 12, the session ended, the folded list by keyboard, sign-out with a waiting paid card (asked first, from the chat, the editor or another tab; nothing of the shop left; signed in again, the poster's one job and its version to review), a request admitted before another tab's sign-out answering late or after a failed check (nothing written back), one arriving after it (401, no job), a paid request sent only once stored (refused at the tap or at sending, kept despite threads dated ahead), a failed image job, a style change on a fresh plan, the shop's identity asked in the first message, the seller's kit (a style photo read into a look before the scene, taken again for the same image, its brief waited on again after a lost answer, the style limit with nothing paid; a price without its unit, « 250k », two amounts as buttons with no second read; scene words and a new shop line kept before the scene and listed by the review, a refused line with nothing paid and the recap again to drop it, the recap's switch off kept through a failed scene setup and a reload, a line asked on a poster naming every line drawn; « Corriger l’affiche » back to the field; the kit row's last choices on the next poster, a saved look chosen as a chip and a title style in the scene request, the same recap and request after a refused image and after a failed style read; « Garder cette scène comme modèle » twice with one model, in « Mon kit » and as a chip; the title style in « Pas à pas » restored from its version, asked in the next scene, set as the title layer's font, and « Mon kit »'s default changed only by a choice), read failed, 360 px and desktop, both themes, zero spend.")
                    finally:
                        browser.close()
            finally:
                vite.terminate()
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill()
                    vite.wait(timeout=10)
                smoke.stop(*server)


if __name__ == "__main__":
    run()
