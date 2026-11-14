"""Creation by message in a real browser (T-CHAT-003, D-TEXT-FIRST-001 and 003): stub providers, temporary data, zero
spend. From backend/: uv run python ../frontend/tests/chat_browser.py (ports 8000 and 5173 must be free).
Pictures: outputs/chat-smoke/."""
import json
import os
import re
import subprocess
import tempfile
import time
from uuid import uuid4

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

import browser_smoke as smoke

OUT = smoke.ROOT / "outputs" / "chat-smoke"
REVIEW, FINAL = "Vérifier la fidélité du produit", "Dernière vérification avant le téléchargement"
THREAD = "id => JSON.parse(localStorage.getItem('affiche.chat.' + id))"
START = "localStorage.getItem('affiche.start')"
PENDING = "() => JSON.parse(localStorage.getItem('affiche.chat.pending'))?.key ?? null"
SCENE_JOBS = "id => fetch('/api/creations/' + id + '/jobs').then(r => r.json()).then(body => body.items.filter(job => job.kind === 'scene').length)"
POSTER_FONTS = re.compile(r"/fonts/(NotoSerif|Montserrat|NotoSans-Bold)")


def sign_in(page):
    page.goto(smoke.ORIGIN)
    page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
    page.get_by_role("button", name="Ouvrir l’atelier").click()


def looks_right(page, where, name=None):
    """No sideways scroll, readable text, one blur per surface; a picture for a person to judge."""
    assert page.evaluate(smoke.NO_SIDEWAYS), f"sideways scroll on {where}"
    page.wait_for_function("document.documentElement.scrollHeight <= innerHeight + 1")  # the page never scrolls behind the chat
    smoke.check_contrast(page, where)
    smoke.check_one_blur(page, where)
    if name:
        page.screenshot(path=str(OUT / name))


def both_themes(page, where, name):
    first = smoke.theme_of(page)
    for theme in (first, "clair" if first == "sombre" else "sombre"):
        if smoke.theme_of(page) != theme:
            smoke.toggle_theme(page, "Passer au thème clair" if theme == "clair" else "Passer au thème sombre")
        looks_right(page, f"{where}, {theme}", f"{name}-{theme}.png")


def say(page, text):
    page.get_by_label("Votre message").fill(text)
    page.get_by_role("button", name="Envoyer").click()


def walk_desktop(browser, errors, product, inspiration):
    held = {"on": False}
    reads, scenes, fonts = [], [], []

    # The stub makes a scene in about a second: its state is held at « running » in the answers (one job, and the
    # poster's list of jobs read at a reload) while the real job ends behind.
    def hold_job(route):
        if not held["on"]:
            return route.continue_()
        response = route.fetch()
        body = response.json()
        for job in body.get("items", [body]):
            if job["kind"] == "scene":
                job.update(status="running", result_ref=None, error_code=None, finished_at=None)
        route.fulfill(response=response, json=body)

    def seen(request):
        if request.method == "POST" and request.url.endswith("/api/reads"):
            reads.append(request.headers["idempotency-key"])
        if request.method == "POST" and request.url.endswith("/scenes"):
            scenes.append(request.headers["idempotency-key"])
        if POSTER_FONTS.search(request.url):
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

    # A device that never chose is asked once; no form, no switch yet.
    choice = page.get_by_role("heading", name="Comment voulez-vous créer vos affiches ?")
    expect(choice).to_be_visible()
    expect(page.get_by_label("Photos du produit")).to_have_count(0)
    expect(page.locator(".seg")).to_have_count(0)
    assert page.evaluate(START) is None
    looks_right(page, "start choice, desktop", "choice-1366.png")
    page.get_by_role("button", name=re.compile("^Par message")).click()
    chat = page.locator(".chat")
    expect(chat).to_be_visible()
    assert page.url.endswith("#message") and page.evaluate(START) == "chat", page.url
    switch = page.get_by_role("group", name="Façon de créer")
    expect(switch.get_by_role("button", name="Message")).to_have_attribute("aria-pressed", "true")
    thread, field, send = page.get_by_role("log"), page.get_by_label("Votre message"), page.get_by_role("button", name="Envoyer")
    expect(thread).to_contain_text("Quel produit, à quel prix ?")
    expect(send).to_be_disabled()
    # The start view is remembered: a reload, and the empty address, open the chat.
    page.reload()
    expect(chat).to_be_visible()
    page.goto(smoke.ORIGIN + "/#")
    expect(chat).to_be_visible()
    page.wait_for_url("**/#message")
    expect(choice).to_have_count(0)
    both_themes(page, "empty chat, desktop", "chat-empty-1366")

    # The unsent text survives a reload.
    field.fill("Sony WH-1000XM6 noir, 700 000 Ar")
    page.reload()
    expect(field).to_have_value("Sony WH-1000XM6 noir, 700 000 Ar")
    # Two images: the first is the product, the second the inspiration; each is uploaded at once; a label swaps the roles.
    page.locator(".composer input[type=file]").set_input_files([product, inspiration])
    pics = page.locator(".tray .pic")
    expect(pics).to_have_count(2)
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    expect(pics.nth(0).locator(".pic-role")).to_have_text("Produit")
    expect(pics.nth(1).locator(".pic-role")).to_have_text("Inspiration")
    expect(page.locator(".style-row")).to_have_text("Style : comme votre inspiration")
    pics.nth(0).locator(".pic-role").click()
    expect(pics.nth(0).locator(".pic-role")).to_have_text("Inspiration")
    expect(pics.nth(1).locator(".pic-role")).to_have_text("Produit")
    pics.nth(0).locator(".pic-role").click()
    expect(pics.nth(0).locator(".pic-role")).to_have_text("Produit")
    expect(pics.nth(1).locator(".pic-role")).to_have_text("Produit")
    pics.nth(1).locator(".pic-role").click()
    expect(pics.nth(1).locator(".pic-role")).to_have_text("Inspiration")
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    for label in ("Ajouter des images", "Envoyer", "Retirer cette image"):
        expect(page.get_by_role("button", name=label).first).to_be_visible()
    send.click()
    # One message, two images: the recap, with the price large and the cost said as the paid dialog says it.
    recap = thread.locator(".bubble.bot", has=page.locator(".recap"))
    expect(recap).to_have_count(1)
    expect(recap.locator(".recap b")).to_have_text("Sony WH-1000XM6 noir")
    expect(recap.locator(".recap-price")).to_have_text(re.compile(r"^700\s000 Ar$"))
    expect(recap).to_contain_text("Style : comme votre inspiration")
    expect(recap).to_contain_text("Mode de démonstration : aucune dépense.")
    expect(recap.locator(".pic")).to_have_count(2)
    expect(thread.locator(".bubble.me")).to_contain_text("Sony WH-1000XM6 noir, 700 000 Ar")
    expect(field).to_be_focused()
    expect(field).to_have_value("")
    assert page.evaluate("localStorage.getItem('affiche.chat.unsent') ?? localStorage.getItem('affiche.chat.pending')") is None
    assert len(reads) == 1, reads
    both_themes(page, "recap, desktop", "chat-recap-1366")

    # One tap: the card is spent before the request leaves, and its id is the paid request's key.
    held["on"] = True
    create = page.get_by_role("button", name="Créer l’affiche")
    create.click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    poster = page.url.split("#message-")[1]
    wait = thread.locator(".chat-wait")
    expect(wait).to_contain_text("Je dessine l’affiche…")
    expect(create).to_have_count(0)
    field.fill("fond plus sombre")  # typing stays possible; « Envoyer » waits
    expect(send).to_be_disabled()
    spent = [item for item in page.evaluate(THREAD, poster)["items"] if item.get("spent")]
    assert len(spent) == 1 and scenes == [spent[0]["id"]], (spent, scenes)
    # The card holds its poster and its job; the new thread's key says where the thread went.
    assert spent[0]["creation"] == poster and re.fullmatch(r"[a-f0-9-]{36}", spent[0]["job"]), spent
    assert json.loads(page.evaluate("localStorage.getItem('affiche.chat.new')")) == {"moved": poster}
    both_themes(page, "creation, desktop", "chat-wait-1366")
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
    expect(page.get_by_role("heading", name=REVIEW)).to_have_count(0)
    expect(thread).to_contain_text("Version 1 prête.")
    assert scenes == [spent[0]["id"]], scenes
    side = page.locator(".chat-side")
    expect(side).to_contain_text("Version 1 · à vérifier")
    assert side.bounding_box()["x"] > thread.bounding_box()["x"] + thread.bounding_box()["width"], "wide: the poster has the right column"
    assert thread.locator(".chat-poster img").evaluate("e => e.complete && e.naturalWidth > 0 && e.src.includes('display=true')")
    both_themes(page, "result, desktop", "chat-result-1366")
    # « Vérifier » is the editor's own review, with the photo; its approval turns the card into « Télécharger ».
    verify.click()
    expect(page.get_by_role("heading", name=REVIEW)).to_be_visible()
    assert chat.evaluate("e => e.inert")
    expect(page.get_by_alt_text("Photo originale 1 à comparer")).to_be_visible()
    page.get_by_role("button", name="Tout est conforme, approuver").click()
    expect(page.get_by_role("heading", name=REVIEW)).to_have_count(0)
    expect(thread.locator(".chat-state")).to_have_text("Approuvée")
    expect(verify).to_have_count(0)
    page.get_by_role("button", name="Télécharger", exact=True).click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Tout est conforme, confirmer").click()
    expect(page.get_by_role("heading", name="Votre affiche est prête")).to_be_visible()
    expect(page.get_by_role("link", name="Télécharger le PNG confirmé")).to_be_visible()
    page.screenshot(path=str(OUT / "chat-confirmed-1366.png"))
    page.get_by_role("button", name="Fermer").click()
    # The chat never mounted the canvas nor loaded a poster font.
    expect(page.locator(".poster-canvas, .konvajs-content")).to_have_count(0)
    assert not fonts, fonts
    # An existing poster: no paid read for a change the chat cannot carry out yet, and the way to the steps is offered.
    say(page, "fond plus sombre")
    expect(thread).to_contain_text("Pour changer cette affiche, passez par Pas à pas.")
    assert len(reads) == 1, reads

    # « Mes affiches » opens a poster in the chat when the chat is the start view; the switch shows the same poster in the editor.
    page.get_by_role("link", name=re.compile("^Mes affiches")).click()
    page.get_by_role("button", name=re.compile("Sony WH-1000XM6 noir")).first.click()
    page.wait_for_url(f"**/#message-{poster}")
    # As in the editor, a confirmed poster opens on its file, ready to download again.
    expect(page.get_by_role("link", name="Télécharger le PNG confirmé")).to_be_visible()
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
    page.get_by_role("link", name="Créer").click()
    page.wait_for_url("**/#message")
    expect(thread.locator(".bubble")).to_have_count(1)
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
    # No price: asked. No photo: asked, with its button.
    expect(thread).to_contain_text("Quel est le prix ?")
    assert len(reads) == 3 and reads[1] == reads[2] != reads[0], reads
    assert page.evaluate("localStorage.getItem('affiche.chat.pending')") is None
    send.click()
    ask = thread.locator(".bubble.bot").last
    expect(ask).to_contain_text("Il me faut une photo du produit.")
    with page.expect_file_chooser() as chooser:
        ask.get_by_role("button", name="Ajouter une photo").click()
    chooser.value.set_files(product)
    expect(page.locator(".tray .pic .pic-role")).to_have_text("Produit")
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    # Without an inspiration the three styles are offered, the last used one chosen.
    styles = page.get_by_role("group", name="Style de l’affiche").get_by_role("button")
    expect(styles).to_have_text(["Studio clair", "Couleurs du produit", "Luxe sombre"])
    expect(styles.nth(0)).to_have_attribute("aria-pressed", "true")
    send.click()
    expect(ask.get_by_role("button", name="Ajouter une photo")).to_have_count(0)
    expect(recap.last.locator(".recap b")).to_have_text("Casque JBL Tune")
    expect(recap.last.locator(".recap-price")).to_have_text(re.compile(r"^250\s000 Ar$"))
    styles.nth(2).click()
    expect(recap.last).to_contain_text("Style : Luxe sombre")
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
    assert page.url.endswith("#") or "#" not in page.url, page.url
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
    page.locator("textarea[name=title]").fill("Casque JBL Tune 520 Pro")
    page.get_by_label("Prix en ariary", exact=True).fill("270 000")
    saved_after(kept["request"]["revision"])
    switch.get_by_role("button", name="Message").click()
    page.wait_for_url(f"**/#message-{second}")
    expect(thread).to_contain_text("L’affiche n’a peut-être pas été lancée.")
    expect(resume).to_be_visible()
    page.wait_for_timeout(500)
    assert scenes.count(kept["id"]) == 1, scenes  # nothing sent on the return
    resume.click()
    expect(page.get_by_role("button", name="Créer l’affiche")).to_have_count(1)
    expect(recap.last.locator(".recap b")).to_have_text("Casque JBL Tune 520 Pro")
    expect(recap.last.locator(".recap-price")).to_have_text(re.compile(r"^270\s000 Ar$"))
    assert scenes.count(kept["id"]) == 2 and page.evaluate(SCENE_JOBS, second) == 0, scenes
    # A later correction in « Pas à pas » reaches the unpaid recap; spent cards stay as they were.
    switch.get_by_role("button", name="Pas à pas").click()
    page.wait_for_url(f"**/#{second}")
    before = revision()
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
    other = browser.new_context(storage_state=context.storage_state())
    headers = lambda: {"Origin": smoke.ORIGIN, "If-Match": f'"{revision()}"', "Idempotency-Key": str(uuid4())}
    plan = other.request.post(f"{smoke.ORIGIN}/api/creations/{second}/plans", headers=headers(), data={"mode": "fixed", "direction": "Studio clair", "format": "feed"})
    assert plan.ok, plan.text()
    started = other.request.post(f"{smoke.ORIGIN}/api/creations/{second}/scenes", headers=headers(), data={"plan_id": plan.json()["id"], "format": "feed"})
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
    expect(resume.locator("xpath=../..")).to_contain_text("Mode de démonstration : aucune dépense.")  # its cost, as for « Créer »
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


def walk_phone(browser, errors, session):
    """360 px with a touch pointer, then the height the keyboard leaves: the composer and « Envoyer » stay in view."""
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark", storage_state=session)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(smoke.ORIGIN)
    page.wait_for_url("**/#message")
    chat, nav, composer = page.locator(".chat"), page.locator(".nav"), page.locator(".composer")
    expect(chat).to_be_visible()
    expect(page.locator(".chat-side")).to_have_count(0)
    header = page.locator(".app-header").bounding_box()
    assert header["height"] <= 64, header  # the mark, the switch and the theme button on one line
    assert composer.bounding_box()["y"] + composer.bounding_box()["height"] <= nav.bounding_box()["y"], "the composer is above the navigation bar"
    both_themes(page, "chat, 360 px", "chat-360")
    # The keyboard: the visible height shrinks, the field has the focus.
    page.set_viewport_size({"width": 360, "height": 420})
    page.get_by_label("Votre message").tap()
    expect(nav).to_be_hidden()
    expect(page.locator(".style-row")).to_be_hidden()
    page.wait_for_function("() => { const box = document.querySelector('.composer').getBoundingClientRect(); return box.bottom <= innerHeight && box.top > 0 }")
    send = page.get_by_role("button", name="Envoyer").bounding_box()
    assert send["y"] + send["height"] <= 420, send
    looks_right(page, "chat with the keyboard, 360 px", "chat-360-keyboard.png")
    # A poster made by message, on the phone: the strip on top, the thread under it.
    page.set_viewport_size({"width": 360, "height": 740})
    page.get_by_label("Votre message").blur()
    expect(nav).to_be_visible()
    page.get_by_role("link", name=re.compile("Mes affiches")).tap()
    page.get_by_role("button", name=re.compile("Sony WH-1000XM6 noir")).first.tap()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    page.get_by_role("button", name="Fermer").tap()
    side, thread = page.locator(".chat-side"), page.get_by_role("log")
    expect(side).to_contain_text("Version 1 · approuvée")
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
        page.goto(smoke.ORIGIN)
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
    page.wait_for_url("**/#message")
    fallback = page.locator(".chat-elsewhere")
    expect(fallback).to_contain_text("Ce navigateur ne permet pas le chat.")
    expect(page.locator(".chat")).to_have_count(0)
    looks_right(page, "no Web Locks, 360 px", "chat-lockless-360.png")
    fallback.get_by_role("button", name="Pas à pas").tap()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    assert not posts, posts
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
    page.goto(smoke.ORIGIN)
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
    expect(thread).to_contain_text("Quel est le prix ?")
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


def walk_failed(browser, errors):
    """The reader fails (STUB_FAIL): the bubble stays, « Réessayer » pays a new read, « Pas à pas » is one tap away."""
    reads = []
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="light")
    context.on("request", lambda request: reads.append(request.headers["idempotency-key"]) if request.method == "POST" and request.url.endswith("/api/reads") else None)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    sign_in(page)
    page.get_by_role("button", name=re.compile("^Par message")).tap()
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
    context.close()


def walk_choice_phone(browser, errors):
    context = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, color_scheme="dark")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    sign_in(page)
    expect(page.get_by_role("heading", name="Comment voulez-vous créer vos affiches ?")).to_be_visible()
    assert page.evaluate(smoke.NO_SIDEWAYS)
    smoke.check_contrast(page, "start choice, 360 px")
    smoke.check_one_blur(page, "start choice, 360 px")
    page.screenshot(path=str(OUT / "choice-360.png"))
    # « Pas à pas » is remembered too: the form, and the switch from then on.
    page.get_by_role("button", name=re.compile("^Pas à pas")).tap()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    assert page.evaluate(START) == "steps"
    page.reload()
    expect(page.get_by_label("Photos du produit")).to_be_attached()
    expect(page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Pas à pas")).to_have_attribute("aria-pressed", "true")
    context.close()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    product = OUT / "product.png"
    photo = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(photo).rounded_rectangle((250, 160, 750, 840), 50, fill="#202020")
    photo.save(product)
    inspiration = smoke.ROOT / "frontend/public/styles/sombre.jpg"
    errors = []
    with tempfile.TemporaryDirectory(prefix="affiche-chat-") as data, tempfile.TemporaryDirectory(prefix="affiche-chat-fail-") as failing:
        server = smoke.serve(data)
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
                        walk_two_tabs(browser, errors, session, product)
                        walk_lockless(browser, errors, session)
                        walk_slow_read(browser, errors, session)
                        walk_choice_phone(browser, errors)
                        smoke.stop(*server)
                        server = smoke.serve(failing, stub_fail="provider_error")
                        walk_failed(browser, errors)
                        assert not errors, errors
                        print("Chat smoke passed: choice and remembered start view, one message with two images to a confirmed download, "
                              "reload in the middle and before the job is known (kept request sent again), stale kept request refused, « Reprendre » never automatic, transient refusal keeps the request, one chat per device (lock lost and taken back before /scenes), no Web Locks, late read after close, no photo, no price, lost answer, form to chat and recap refresh, editor remount measured, read failed, 360 px and desktop, both themes, zero spend.")
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
