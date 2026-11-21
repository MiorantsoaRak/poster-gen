"""« Publier sur Facebook » in real Chromium (T-FB-010, D-FB-POST-005) on the stand-in (FACEBOOK_PROVIDER=stub), whose
description markers give the answers a real Page cannot be asked for: an image refused, a slow sending, an unknown
outcome. The production build (vite preview, so build first) and the API on temporary stub data, no real env file, zero
spend. Run from backend: uv run python ../frontend/tests/publish_browser.py (ports from SMOKE_WEB_PORT and SMOKE_API_PORT,
5173 and 8000 unless they say). Pictures: outputs/publish-browser/. The operator's limit is written straight into the
temporary database, as the smokes do for what the interface does not make."""
import asyncio
import json
import re
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

import browser_smoke as smoke
from affiche.api import BUNDLE, MESSAGES
from affiche.posters import facebook
from share_browser import READY, made_in_chat, sign_in
from terms_browser import open_atelier, until

OUT = smoke.ROOT / "outputs" / "publish-browser"
PAGE_NAME = "Page d’essai 1"
NO_PAGE = "Aucune Page Facebook n’est connectée. Connectez votre Page dans « Mon compte »."
DRAFT_KEY = "affiche.shop1.post-draft"
STORED = "() => ({ ...localStorage })"
# The smoke's server runs in this process: while UPLOADS is set, the stand-in's uploads wait (a post stays in flight for
# as long as a walk needs it to: a reload during the uploads, a list answered late). Cleared, they go as before.
UPLOADS = threading.Event()
_upload = facebook.StubGraph.upload_photo


async def _held_upload(self, *args, **kwargs):
    while UPLOADS.is_set():
        await asyncio.sleep(0.05)
    return await _upload(self, *args, **kwargs)


facebook.StubGraph.upload_photo = _held_upload


def draft_of(page):
    """`post-draft` as this device keeps it, or None."""
    return json.loads(page.evaluate("key => localStorage.getItem(key)", DRAFT_KEY) or "null")


def walk_off(browser):
    """FACEBOOK_PROVIDER=off: no way in anywhere, and the page's address falls back as an unknown one does."""
    context = browser.new_context(viewport={"width": 1366, "height": 768})
    page = context.new_page()
    page.set_default_timeout(15000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    page.wait_for_load_state("networkidle")
    expect(page.locator("aside.side").get_by_role("link", name="Publier", exact=True)).to_have_count(0)
    expect(page.get_by_role("link", name="Publier sur Facebook")).to_have_count(0)
    smoke.go(page, "Mes affiches")
    expect(page.get_by_role("heading", name="Mes affiches", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Publier sur Facebook")).to_have_count(0)
    for address in ("publier", f"publier-{uuid4()}"):
        page.evaluate("hash => { location.hash = hash }", address)
        page.wait_for_url(re.compile(r"#accueil$"))
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Publier sur Facebook")).to_have_count(0)
    assert not errors, errors
    context.close()


def confirmed(page, product, message, caption=None):
    """A poster made in the chat from Accueil, confirmed in the « Publication » format, its caption typed when given;
    the final panel closed. Returns its id and its title."""
    page.evaluate("() => { location.hash = 'accueil' }")
    expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
    poster = made_in_chat(page, product, message)
    page.get_by_role("button", name="Tout est conforme, confirmer").click()
    expect(page.get_by_role("heading", name=READY)).to_be_visible()
    panel = page.locator(".final-preview")
    if caption is not None:
        panel.get_by_label("Légende de la publication").fill(caption)
    panel.get_by_role("button", name="Fermer").click()
    found = page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}").json()
    assert found["confirmation"]["format"] == "feed", found["confirmation"]
    return poster, found["document"]["offer"]["title"]


def walk(browser, data, product):
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(15000)
    errors, sent = [], []  # every POST /api/facebook/posts that leaves the browser: its key and its body
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda r: print(f"HTTP {r.status} {r.request.method} {r.url}", flush=True) if r.status >= 400 and "/api/" in r.url else None)
    page.on("request", lambda r: sent.append((r.headers.get("idempotency-key"), r.post_data_json))
            if r.method == "POST" and r.url.endswith("/api/facebook/posts") else None)
    heading = page.get_by_role("heading", name="Publier sur Facebook", exact=True)
    mine = page.get_by_role("region", name="Votre publication", exact=True)
    grid = page.get_by_role("region", name="Affiches confirmées", exact=True)
    listed = page.get_by_role("region", name="Publications", exact=True)
    lines = listed.locator("ol.posts > li")
    sheet = page.get_by_role("dialog", name=re.compile("^Publier sur "))
    confirm = sheet.get_by_role("button", name=re.compile(r"^Publier( à nouveau)?$"))  # « à nouveau » once a poster is on the Page
    publish = mine.get_by_role("button", name="Publier…", exact=True)
    field = mine.get_by_label("Description de la publication")
    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)

    # From the desktop navigation, with no Page connected: the page says so, leads to « Mon compte », and shows the posts.
    nav = page.locator("aside.side").get_by_role("link", name="Publier", exact=True)
    nav.click()
    page.wait_for_url(re.compile(r"#publier$"))
    expect(heading).to_be_visible()
    expect(heading).to_be_focused()
    expect(nav).to_have_attribute("aria-current", "page")
    expect(page.get_by_text(NO_PAGE, exact=True)).to_be_visible()
    expect(listed).to_be_visible()
    expect(listed.get_by_text("Aucune publication pour le moment.")).to_be_visible()
    expect(mine).to_have_count(0)
    expect(grid).to_have_count(0)
    page.screenshot(path=str(OUT / "no-page-1366.png"), full_page=True)
    page.get_by_role("link", name="Mon compte", exact=True).last.click()
    page.wait_for_url(re.compile(r"#compte$"))
    card = page.get_by_role("region", name="Page Facebook", exact=True)
    card.get_by_role("button", name="Connecter ma Page Facebook").click()
    page.wait_for_url(smoke.ORIGIN + "/#compte")
    card.get_by_role("radio", name=PAGE_NAME).check()
    card.get_by_role("button", name="Connecter cette Page").click()
    expect(card).to_contain_text(f"Page connectée : {PAGE_NAME}")

    # Three posters confirmed in the « Publication » format (the first with a caption), and a fourth changed since its
    # confirmation: counted among those left out, not offered.
    a, title_a = confirmed(page, product, "Casque Bose QC noir, 450 000 Ar", caption="Casque Bose QC\n450 000 Ar 😀")
    b, title_b = confirmed(page, product, "Casque Sony noir, 300 000 Ar")
    c, title_c = confirmed(page, product, "Casque JBL noir, 200 000 Ar")
    d, title_d = confirmed(page, product, "Casque Sennheiser noir, 500 000 Ar")
    address = f"{smoke.ORIGIN}/api/creations/{d}"
    now = page.request.get(address).json()
    changed = page.request.put(address, data=now["document"] | {"offer": now["document"]["offer"] | {"price_ar": 510000}},
        headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "If-Match": f'"{now["revision"]}"', "Idempotency-Key": str(uuid4())})
    assert changed.ok, changed.text()
    assert len({title_a, title_b, title_c, title_d}) == 4, (title_a, title_b, title_c, title_d)
    tile = lambda title: grid.locator(".tile", has_text=title)  # noqa: E731
    row = lambda title: mine.locator("ol.chosen > li", has_text=title)  # noqa: E731

    smoke.go(page, "Publier")
    expect(heading).to_be_visible()
    expect(page.locator(".shop-publish .titlerow .meta")).to_have_text(f"Sur la Page {PAGE_NAME}")
    for title in (title_a, title_b, title_c):
        expect(tile(title)).to_have_attribute("aria-pressed", "false")
    expect(tile(title_d)).to_have_count(0)
    expect(grid.locator(".left-out")).to_contain_text("1 affiche n’est pas proposée :")
    expect(grid.get_by_role("link", name="1 modifiée depuis sa vérification : vérifiez-la à nouveau")).to_have_attribute("href", "#affiches")
    expect(publish).to_be_disabled()
    expect(mine.get_by_text("Choisissez au moins une affiche.")).to_be_visible()
    expect(mine.get_by_text("2 000 caractères au plus. Les retours à la ligne et les émojis sont gardés. Les caractères de contrôle sont refusés, sauf les retours à la ligne et les tabulations.")).to_be_visible()

    # Three chosen, then reordered with the buttons: the numbers follow, and the first leads.
    for title in (title_a, title_b, title_c):
        tile(title).click()
    expect(mine.locator("ol.chosen > li")).to_have_count(3)
    mine.get_by_role("button", name=f"Plus tôt « {title_c} »").click()
    expect(mine.get_by_role("button", name=f"Plus tôt « {title_c} »")).to_be_focused()
    mine.get_by_role("button", name=f"Plus tard « {title_a} »").click()
    order = [title_c, title_a, title_b]
    for number, title in enumerate(order, 1):
        expect(mine.locator("ol.chosen > li").nth(number - 1)).to_contain_text(title)
        expect(tile(title).locator(".number")).to_have_text(str(number))
    expect(row(title_c)).to_contain_text("En tête")
    expect(row(title_a)).not_to_contain_text("En tête")
    expect(mine.get_by_role("button", name=f"Plus tôt « {title_c} »")).to_be_disabled()
    expect(mine.get_by_role("button", name=f"Plus tard « {title_b} »")).to_be_disabled()
    # A refused character is said as it is typed; then the first poster's caption is taken as the description.
    field.fill("Essai\u0007")
    expect(mine.locator("#etat-description")).to_have_text("La description contient un caractère de contrôle refusé.")
    expect(publish).to_be_disabled()
    field.fill("")
    mine.get_by_role("button", name=f"Reprendre la légende de « {title_a} »").click()
    expect(field).to_have_value("Casque Bose QC\n450 000 Ar 😀")
    expect(mine.locator("#compte-description")).to_have_text("27 / 2 000")
    stored = draft_of(page)
    assert stored["items"] == [c, a, b] and stored["description"] == "Casque Bose QC\n450 000 Ar 😀" and stored["post"] is None, stored
    # Kept on this device: a reload brings the draft back as it was.
    page.reload()
    expect(heading).to_be_visible()
    expect(field).to_have_value("Casque Bose QC\n450 000 Ar 😀")
    for number, title in enumerate(order, 1):
        expect(mine.locator("ol.chosen > li").nth(number - 1)).to_contain_text(title)
    page.screenshot(path=str(OUT / "draft-1366.png"), full_page=True)

    # The confirmation: the Page, the strip of images in order, the description as it will be sent. A thumbnail that
    # does not load says so, with « Réessayer », and « Publier » waits for it.
    failing = []

    def fail_once(route):
        if failing:
            return route.continue_()
        failing.append(route.request.url)
        route.abort()

    page.route("**/api/thumbnails/**", fail_once)  # a route turns the browser's cache off: the sheet's images are asked
    publish.click()
    expect(sheet.get_by_role("heading")).to_have_text(f"Publier sur {PAGE_NAME} ?")
    expect(sheet.get_by_role("alert")).to_have_text("Une image n’a pas pu être affichée : elle doit être vue avant d’être publiée.")
    expect(confirm).to_have_text("Publier")  # nothing of it on the Page yet
    expect(sheet).not_to_contain_text("déjà sur votre Page")
    expect(confirm).to_be_disabled()
    sheet.get_by_role("button", name="Réessayer").click()
    expect(sheet.get_by_role("alert")).to_have_count(0)
    expect(confirm).to_be_enabled()
    page.unroute("**/api/thumbnails/**")
    assert len(failing) == 1, failing
    expect(sheet.get_by_role("img")).to_have_count(3)
    for number, title in enumerate(order, 1):
        expect(sheet.get_by_role("img").nth(number - 1)).to_have_attribute("alt", f"Image {number} : {title}")
    expect(sheet.get_by_role("link").first).to_have_attribute("href", re.compile(r"^/api/confirmations/[a-f0-9-]{36}/download$"))
    expect(sheet.locator(".sent-text")).to_have_text("Casque Bose QC\n450 000 Ar 😀")
    expect(page.locator("aside.side")).to_have_attribute("inert", "")
    smoke.check_contrast(page, "publish sheet 1366")
    page.screenshot(path=str(OUT / "sheet-1366.png"))
    page.keyboard.press("Escape")
    expect(sheet).to_have_count(0)
    expect(publish).to_be_focused()
    publish.click()
    expect(sheet.get_by_role("button", name="Annuler")).to_be_focused()
    stamp = draft_of(page)["stamp"]
    confirm.click()
    expect(sheet).to_have_count(0)
    expect(lines).to_have_count(1)
    expect(lines.first).to_contain_text(re.compile(r"Envoi de l’image \d sur 3…|Images envoyées\. Publication…|Publication en cours…"))
    expect(lines.first).to_contain_text("3 images")
    expect(lines.first).to_contain_text(f"Publié sur {PAGE_NAME}.", timeout=20000)
    expect(lines.first.get_by_role("link", name="Voir la publication")).to_have_attribute("href", re.compile(r"^https://www\.facebook\.com/100000000000001_\d+$"))
    confirmations = {poster: page.request.get(f"{smoke.ORIGIN}/api/creations/{poster}").json()["confirmation"]["id"] for poster in (a, b, c)}
    # The draft's stamp is the key; the posters in the order chosen.
    assert sent[-1] == (stamp, {"page_id": "100000000000001", "description": "Casque Bose QC\n450 000 Ar 😀",
                                "items": [{"creation_id": poster, "confirmation_id": confirmations[poster], "seen": None} for poster in (c, a, b)]}), sent[-1]
    # Published from that very draft: the draft is forgotten; the posters are marked.
    until(page, lambda: draft_of(page) is None)
    expect(mine.get_by_text("Choisissez vos affiches plus bas, dans l’ordre de la publication.")).to_be_visible()
    expect(field).to_have_value("")
    expect(tile(title_a)).to_contain_text(re.compile(r"Publiée le \d{1,2} \w+ 2\d{3}"))

    # An image refused: nothing is published, the image is named, the draft is kept with a new stamp; « Publier » again
    # is a new try, a second post. The sheet says those posters are on the Page already, and asks to publish again.
    tile(title_a).click()
    tile(title_b).click()
    field.fill("Essai [stub:image:2]")
    refused = "L’image 2 n’a pas pu être envoyée (code 100). Rien n’a été publié. Retirez l’image 2 ou remplacez-la, puis réessayez."
    for count in (2, 3):
        stamp = draft_of(page)["stamp"]
        publish.click()
        expect(sheet).to_contain_text(re.compile(r"2 de ces affiches sont déjà sur votre Page \(la dernière le \d{1,2} \w+ 2\d{3}\)\. Publier à nouveau \?"))
        expect(confirm).to_have_text("Publier à nouveau")
        confirm.click()
        expect(lines).to_have_count(count)
        expect(lines.first).to_contain_text(refused, timeout=20000)
        assert sent[-1][0] == stamp and sent[-1][1]["items"][0]["seen"]["status"] in ("published", "failed"), sent[-1]
        expect(mine.locator("ol.chosen > li")).to_have_count(2)
        expect(field).to_have_value("Essai [stub:image:2]")
        until(page, lambda: (draft_of(page) or {}).get("stamp") not in (None, stamp))
        assert draft_of(page)["post"] is None and draft_of(page)["items"] == [a, b]
    expect(lines.nth(1)).to_contain_text(refused)
    assert sent[-1][0] != sent[-2][0]

    # One tab at a time holds the page: a second tab says so and can take it over; the first then says so and reads,
    # writes, polls and sends nothing more, until it takes the page back.
    elsewhere_line = "La page Publier est ouverte dans un autre onglet."
    other = context.new_page()
    other.set_default_timeout(15000)
    other.on("pageerror", lambda error: errors.append(str(error)))
    open_atelier(other, "/#publier")
    expect(other.get_by_text(elsewhere_line, exact=True)).to_be_visible()
    expect(other.get_by_role("region", name="Votre publication", exact=True)).to_have_count(0)
    other.get_by_role("button", name="Continuer ici").click()
    other_mine = other.get_by_role("region", name="Votre publication", exact=True)
    expect(other_mine.get_by_label("Description de la publication")).to_have_value("Essai [stub:image:2]")
    expect(page.get_by_text(elsewhere_line, exact=True)).to_be_visible()
    expect(mine).to_have_count(0)
    expect(listed).to_have_count(0)
    asked = []

    def ask(request):
        if "/api/facebook/" in request.url:
            asked.append(request.url)

    page.on("request", ask)
    page.wait_for_timeout(4500)  # two of the polling's periods
    page.remove_listener("request", ask)
    assert not asked, asked
    page.screenshot(path=str(OUT / "elsewhere-1366.png"))
    page.get_by_role("button", name="Continuer ici").click()
    expect(field).to_have_value("Essai [stub:image:2]")
    expect(other.get_by_text(elsewhere_line, exact=True)).to_be_visible()
    other.close()

    # A reload while the answer to « Publier » is held: the draft is still there with its stamp, and « Publier » again
    # sends the same key, answered by the one post the server made.
    field.fill("Rechargement")
    before = len(page.request.get(f"{smoke.ORIGIN}/api/facebook/posts?limit=50").json()["items"])
    stamp, held = draft_of(page)["stamp"], []

    def hold(route):
        if route.request.method != "POST" or held:
            return route.continue_()
        held.append(route.fetch())  # the server has the request; its answer never reaches the page

    # Removed only after the reload: an unroute would let the held request go on to the page.
    page.route("**/api/facebook/posts", hold)
    publish.click()
    confirm.click()
    until(page, lambda: held)
    page.reload()
    expect(heading).to_be_visible()
    expect(lines).to_have_count(4)
    expect(lines.first).to_contain_text(f"Publié sur {PAGE_NAME}.", timeout=20000)
    assert draft_of(page)["stamp"] == stamp
    expect(field).to_have_value("Rechargement")
    expect(publish).to_be_enabled()
    publish.click()
    confirm.click()
    until(page, lambda: draft_of(page) is None)
    expect(lines).to_have_count(4)
    assert len(page.request.get(f"{smoke.ORIGIN}/api/facebook/posts?limit=50").json()["items"]) == before + 1
    assert sent[-1][0] == sent[-2][0] == stamp, sent[-2:]
    page.unroute_all(behavior="ignoreErrors")

    # A list asked before the post was admitted, answered after its 202: the post keeps its row and is followed to its end.
    tile(title_a).click()
    tile(title_c).click()
    field.fill("Liste en retard")
    late = []

    def late_list(route):
        if late:
            return route.continue_()
        late.append((route, route.fetch()))  # the list as it was before the post

    page.route(re.compile(r"/api/facebook/posts\?limit=20$"), late_list)
    UPLOADS.set()
    try:
        page.reload()
        expect(field).to_have_value("Liste en retard")
        until(page, lambda: late)
        publish.click()
        confirm.click()
        expect(lines).to_have_count(1)
        followed_id = lines.first.get_attribute("data-post")
        expect(lines.first).to_contain_text("Envoi de l’image 1 sur 2…")
        route, answer = late[0]
        route.fulfill(response=answer)
        expect(listed.get_by_text("Lecture des publications…")).to_have_count(0)
        expect(lines).to_have_count(5)
        assert lines.first.get_attribute("data-post") == followed_id
        expect(lines.first).to_contain_text("Envoi de l’image 1 sur 2…")
    finally:
        UPLOADS.clear()
    expect(lines.first).to_contain_text(f"Publié sur {PAGE_NAME}.", timeout=20000)
    until(page, lambda: draft_of(page) is None)
    page.unroute(re.compile(r"/api/facebook/posts\?limit=20$"))

    # « Arrêter l’envoi » while the images are being sent (each takes a second on the stand-in).
    for title in (title_a, title_b, title_c):
        tile(title).click()
    field.fill("Lent [stub:slow]")
    publish.click()
    confirm.click()
    lines.first.get_by_role("button", name="Arrêter l’envoi").click()
    expect(lines.first).to_contain_text("Envoi arrêté. Rien n’a été publié.", timeout=20000)
    expect(mine.locator("ol.chosen > li")).to_have_count(3)

    # The operator's limit, lowered while the page shows three chosen: the server refuses, the page says it beside
    # « Publier… », reads again and says the limit; the grid no longer adds once the draft is at it.
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        store.execute("UPDATE shop_profile SET post_image_limit=2 WHERE id=1")
    field.fill("Limite")
    publish.click()
    confirm.click()
    expect(sheet).to_have_count(0)
    expect(mine.get_by_role("alert")).to_have_text(MESSAGES["facebook_too_many"].format(2))
    expect(mine.get_by_text("2 images au plus par publication", exact=True)).to_be_visible()
    expect(publish).to_be_disabled()
    expect(mine.get_by_text("Retirez des affiches : 2 images au plus par publication.")).to_be_visible()
    expect(grid.get_by_text("Retirez des affiches : 2 images au plus par publication.")).to_be_visible()  # never « compte 2 »
    mine.get_by_role("button", name=f"Retirer « {title_c} »").click()
    expect(tile(title_c)).to_be_disabled()
    expect(grid.get_by_text("Votre publication compte 2 images, le plus permis : retirez-en une pour en ajouter une autre.")).to_be_visible()
    expect(publish).to_be_enabled()

    # An unknown outcome: the owner's three controls, « Publier… » off until he says. The Page disconnected meanwhile,
    # the post is still answerable: « Elle n’y est pas » after its warning. Unknown again, « Elle est sur ma Page ».
    field.fill("Inconnu [stub:unknown]")
    publish.click()
    confirm.click()
    unknown = lines.first
    expect(unknown).to_contain_text("Je ne sais pas si la publication est sur votre Page. Ouvrez votre Page et dites-le-moi.", timeout=20000)
    expect(unknown.get_by_role("link", name="Ouvrir ma Page")).to_have_attribute("href", "https://www.facebook.com/100000000000001")
    expect(unknown.get_by_role("link", name="Ouvrir ma Page")).to_have_attribute("target", "_blank")
    expect(tile(title_a)).to_contain_text("Résultat inconnu : répondez plus bas")
    expect(publish).to_be_disabled()
    expect(mine.get_by_text("Une de ces affiches attend votre réponse sur une publication au résultat inconnu : répondez plus bas.")).to_be_visible()
    stamp = draft_of(page)["stamp"]
    assert draft_of(page)["post"] == unknown.get_attribute("data-post")
    page.screenshot(path=str(OUT / "unknown-1366.png"), full_page=True)
    page.evaluate("() => { location.hash = 'compte' }")
    card.get_by_role("button", name="Déconnecter").click()
    expect(card.get_by_role("button", name="Connecter ma Page Facebook")).to_be_visible()
    page.evaluate("() => { location.hash = 'publier' }")
    expect(page.get_by_text(NO_PAGE, exact=True)).to_be_visible()
    expect(mine).to_have_count(0)
    lines.first.get_by_role("button", name="Elle n’y est pas").click()
    absent = page.get_by_role("dialog", name="Elle n’est pas sur votre Page ?")
    expect(absent).to_contain_text("Si elle apparaît plus tard, publier à nouveau créera un doublon.")
    absent.get_by_role("button", name="Elle n’y est pas").click()
    expect(lines.first).to_contain_text("Vous avez dit qu’elle n’est pas sur votre Page.")
    expect(lines.first.get_by_role("button")).to_have_count(0)
    until(page, lambda: draft_of(page)["stamp"] != stamp)  # not on the Page: the draft stays, a new try
    assert draft_of(page)["post"] is None and len(draft_of(page)["items"]) == 2
    page.screenshot(path=str(OUT / "unknown-no-page-1366.png"), full_page=True)
    page.get_by_role("link", name="Mon compte", exact=True).last.click()
    card.get_by_role("button", name="Connecter ma Page Facebook").click()
    page.wait_for_url(smoke.ORIGIN + "/#compte")
    card.get_by_role("radio", name=PAGE_NAME).check()
    card.get_by_role("button", name="Connecter cette Page").click()
    expect(card).to_contain_text(f"Page connectée : {PAGE_NAME}")
    smoke.go(page, "Publier")
    expect(mine.locator("ol.chosen > li")).to_have_count(2)
    expect(publish).to_be_enabled()
    publish.click()
    confirm.click()
    expect(lines.first.get_by_role("button", name="Elle est sur ma Page")).to_be_visible(timeout=20000)
    lines.first.get_by_role("button", name="Elle est sur ma Page").click()
    expect(lines.first).to_contain_text("Présence confirmée par vous")
    expect(lines.first.get_by_role("link", name="Ouvrir la Page")).to_have_attribute("href", "https://www.facebook.com/100000000000001")
    until(page, lambda: draft_of(page) is None)

    # The page for one poster: its caption is the description; published from there, with its own key, the draft of
    # several posters untouched. Its answer held and the page reloaded during the uploads: « Publier… » is off while the
    # post is in flight; once it is published, the sheet says the poster is on the Page and asks to publish again.
    tile(title_b).click()
    kept_draft = draft_of(page)
    page.evaluate("hash => { location.hash = hash }", f"publier-{a}")
    expect(heading).to_be_visible()
    expect(field).to_have_value("Casque Bose QC\n450 000 Ar 😀")
    expect(mine.get_by_role("figure")).to_contain_text(title_a)
    expect(grid).to_have_count(0)
    expect(mine.get_by_text("Votre publication en préparation (1 affiche) est gardée.")).to_be_visible()
    field.fill("Légende reprise ici")
    assert page.evaluate("key => localStorage.getItem(key)", f"affiche.shop1.caption.{a}") == "Légende reprise ici"
    page.screenshot(path=str(OUT / "one-poster-1366.png"), full_page=True)
    last = page.request.get(f"{smoke.ORIGIN}/api/facebook/posts/candidates?ids={a}").json()["items"][0]["last"]
    confirmation = page.request.get(f"{smoke.ORIGIN}/api/creations/{a}").json()["confirmation"]["id"]
    count, held = lines.count(), []
    page.route("**/api/facebook/posts", hold)
    UPLOADS.set()
    try:
        publish.click()
        expect(sheet.get_by_role("img")).to_have_count(1)
        expect(sheet.locator(".sent-text")).to_have_text("Légende reprise ici")
        expect(sheet).to_contain_text(re.compile(r"Cette affiche est déjà sur votre Page depuis le \d{1,2} \w+ 2\d{3}\. Publier à nouveau \?"))
        confirm.click()
        until(page, lambda: held)
        page.reload()
        expect(field).to_have_value("Légende reprise ici")
        expect(lines).to_have_count(count + 1)
        expect(lines.first).to_contain_text("Envoi de l’image 1 sur 1…")
        expect(publish).to_be_disabled()
        expect(mine.get_by_text("Une publication est en cours : attendez son résultat.")).to_be_visible()
    finally:
        UPLOADS.clear()
    page.unroute_all(behavior="ignoreErrors")
    expect(lines.first).to_contain_text(f"Publié sur {PAGE_NAME}.", timeout=20000)
    expect(lines.first).to_contain_text("1 image")
    assert sent[-1][1] == {"page_id": "100000000000001", "description": "Légende reprise ici",
                           "items": [{"creation_id": a, "confirmation_id": confirmation, "seen": last}]}, sent[-1]
    assert sent[-1][0] != kept_draft["stamp"] and draft_of(page) == kept_draft
    publish.click()
    expect(sheet).to_contain_text(re.compile(r"Cette affiche est déjà sur votre Page depuis le \d{1,2} \w+ 2\d{3}\. Publier à nouveau \?"))
    expect(confirm).to_have_text("Publier à nouveau")
    sheet.get_by_role("button", name="Annuler").click()
    assert len(page.request.get(f"{smoke.ORIGIN}/api/facebook/posts?limit=50").json()["items"]) == count + 1
    mine.get_by_role("link", name="Publier plusieurs affiches").click()
    page.wait_for_url(re.compile(r"#publier$"))
    expect(mine.locator("ol.chosen > li")).to_have_count(1)
    expect(row(title_b)).to_be_visible()
    # A poster that cannot go: its reason, and the way to it.
    page.evaluate("hash => { location.hash = hash }", f"publier-{d}")
    expect(mine.get_by_text("Cette affiche a été modifiée depuis sa vérification : vérifiez-la à nouveau pour la publier.")).to_be_visible()
    expect(field).to_have_count(0)
    mine.get_by_role("button", name="Ouvrir l’affiche").click()
    page.wait_for_url(re.compile(rf"#(message-)?{d}$"))

    # A draft that cannot be read is never an empty one: said, with « Réessayer » and, damaged, « Vider »; nothing is
    # removed or written over, nothing is sent.
    page.evaluate("key => localStorage.setItem(key, '{abîmé')", DRAFT_KEY)
    mark = len(sent)
    page.evaluate("() => { location.hash = 'publier' }")
    expect(mine.get_by_role("alert")).to_have_text("Votre publication gardée sur cet appareil n’a pas pu être lue.")
    expect(grid).to_have_count(0)
    expect(field).to_have_count(0)
    mine.get_by_role("button", name="Réessayer").click()
    expect(mine.get_by_role("alert")).to_have_text("Votre publication gardée sur cet appareil n’a pas pu être lue.")
    assert page.evaluate("key => localStorage.getItem(key)", DRAFT_KEY) == "{abîmé" and len(sent) == mark
    page.screenshot(path=str(OUT / "unreadable-1366.png"), full_page=True)
    mine.get_by_role("button", name="Vider").click()
    expect(mine.get_by_text("Choisissez vos affiches plus bas, dans l’ordre de la publication.")).to_be_visible()
    assert draft_of(page) is None and len(sent) == mark
    tile(title_b).click()

    # Crossed reads after a reload: the candidates read while the post was in flight answer only once the post is
    # published and the list has said so. « Publier… » is not left off: the marks are read again.
    marks_route, list_route = re.compile(r"/api/facebook/posts/candidates\?"), re.compile(r"/api/facebook/posts\?limit=20$")
    early, waiting = [], []

    def early_marks(route):
        if early:
            return route.continue_()
        early.append((route, route.fetch()))  # read while the post is in flight; answered later

    def later_list(route):
        if waiting:
            return route.continue_()
        waiting.append(route)  # sent on once the post is published

    page.evaluate("hash => { location.hash = hash }", f"publier-{b}")
    expect(field).to_be_visible()
    UPLOADS.set()
    try:
        publish.click()
        confirm.click()
        expect(lines.first).to_contain_text("Envoi de l’image 1 sur 1…")
        flying = lines.first.get_attribute("data-post")
        page.route(marks_route, early_marks)
        page.route(list_route, later_list)
        page.reload()
        until(page, lambda: early and waiting)
    finally:
        UPLOADS.clear()
    until(page, lambda: page.request.get(f"{smoke.ORIGIN}/api/facebook/posts/{flying}").json()["status"] == "published")
    waiting[0].continue_()
    expect(lines.first).to_contain_text(f"Publié sur {PAGE_NAME}.")
    route, answer = early[0]
    assert any(item.get("last") == {"id": flying, "status": "uploading"} for item in answer.json()["items"]), answer.json()
    route.fulfill(response=answer)
    expect(publish).to_be_enabled()
    expect(mine.get_by_text("Une publication est en cours : attendez son résultat.")).to_have_count(0)
    page.unroute(marks_route)
    page.unroute(list_route)

    # A poster taken out of the draft at the opening: the draft is another request (a new stamp), so publishing what is
    # left makes a new post, never `idempotency_reused`. The first answer held, the poster then changed, a reload.
    page.evaluate("() => { location.hash = 'publier' }")
    expect(row(title_b)).to_be_visible()
    tile(title_c).click()
    field.fill("Retirée au rechargement")
    stamp, held = draft_of(page)["stamp"], []
    page.route("**/api/facebook/posts", hold)
    publish.click()
    confirm.click()
    until(page, lambda: held)
    address = f"{smoke.ORIGIN}/api/creations/{c}"
    now = page.request.get(address).json()
    changed = page.request.put(address, data=now["document"] | {"offer": now["document"]["offer"] | {"price_ar": 210000}},
        headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "If-Match": f'"{now["revision"]}"', "Idempotency-Key": str(uuid4())})
    assert changed.ok, changed.text()
    page.reload()
    page.unroute_all(behavior="ignoreErrors")
    expect(mine.get_by_text("L’affiche 2 de votre publication a été retirée : elle a été modifiée depuis sa vérification.")).to_be_visible()
    expect(mine.locator("ol.chosen > li")).to_have_count(1)
    expect(row(title_b)).to_be_visible()
    kept = draft_of(page)
    assert kept["items"] == [b] and kept["stamp"] != stamp and kept["post"] is None, kept
    count = len(page.request.get(f"{smoke.ORIGIN}/api/facebook/posts?limit=50").json()["items"])
    expect(publish).to_be_enabled()
    publish.click()
    confirm.click()
    until(page, lambda: draft_of(page) is None)
    assert sent[-1][0] == kept["stamp"] and [item["creation_id"] for item in sent[-1][1]["items"]] == [b], sent[-1]
    assert len(page.request.get(f"{smoke.ORIGIN}/api/facebook/posts?limit=50").json()["items"]) == count + 1
    expect(mine.get_by_role("alert")).to_have_count(0)
    tile(title_b).click()

    # Both themes at 1366, then on a 360 px phone: from « Mes affiches » and from Accueil; no sideways scroll.
    page.evaluate("() => { location.hash = 'publier' }")
    expect(heading).to_be_visible()
    expect(lines.first).to_be_visible()

    def look(width):
        def check(theme):
            assert page.evaluate(smoke.NO_SIDEWAYS), f"sideways scroll at {width} px, {theme}"
            smoke.check_contrast(page, f"publish page {width} {theme}")
            page.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
            page.screenshot(path=str(OUT / f"page-{width}-{theme}.png"), full_page=True)
        smoke.both_themes(page, check)

    look(1366)
    page.set_viewport_size({"width": 360, "height": 640})
    smoke.go(page, "Mes affiches")
    expect(page.get_by_role("heading", name="Mes affiches", exact=True)).to_be_visible()
    expect(page.locator("nav.phone-bar a")).to_have_count(5)
    page.wait_for_function(smoke.SETTLED, polling=100)
    page.screenshot(path=str(OUT / "mes-affiches-360.png"))
    page.get_by_role("link", name="Publier sur Facebook").click()
    page.wait_for_url(re.compile(r"#publier$"))
    expect(heading).to_be_visible()
    look(360)
    publish.click()
    expect(sheet).to_be_visible()
    assert page.evaluate(smoke.NO_SIDEWAYS), "sideways scroll with the sheet at 360 px"
    smoke.check_contrast(page, "publish sheet 360")
    page.screenshot(path=str(OUT / "sheet-360.png"))
    sheet.get_by_role("button", name="Annuler").click()
    smoke.go(page, "Accueil")
    expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
    page.get_by_role("link", name="Publier sur Facebook").scroll_into_view_if_needed()
    page.wait_for_function(smoke.SETTLED, polling=100)
    page.screenshot(path=str(OUT / "accueil-360.png"))
    page.get_by_role("link", name="Publier sur Facebook").click()
    page.wait_for_url(re.compile(r"#publier$"))
    expect(heading).to_be_visible()

    # Nothing of the feature is kept on the device but its draft and the captions.
    kept = {key: value for key, value in page.evaluate(STORED).items() if key != DRAFT_KEY and ".caption." not in key}
    assert not any(key.endswith("post-sent") for key in page.evaluate(STORED)), page.evaluate(STORED)
    assert not re.search(r"facebook|stub:|post_id|100000000000001|Page d’essai", json.dumps(kept, ensure_ascii=False), re.I), kept
    session = page.evaluate("() => ({ ...sessionStorage })")
    assert not re.search(r"facebook|stub:|post_id|100000000000001|Page d’essai", json.dumps(session, ensure_ascii=False), re.I), session
    assert not errors, errors
    context.close()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    assert (smoke.ROOT / "frontend/dist/index.html").is_file(), "build first: corepack npm@10 run build"
    product = OUT / "product.png"
    photo = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(photo).rounded_rectangle((250, 160, 750, 840), 50, fill="#202020")
    photo.save(product)
    with (tempfile.TemporaryDirectory(prefix="affiche-publish-off-") as off_data,
          tempfile.TemporaryDirectory(prefix="affiche-publish-") as data):
        server = smoke.serve(off_data)
        with (OUT / "preview.log").open("w") as log:
            vite = subprocess.Popen(["node", str(smoke.ROOT / "frontend/node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1",
                                     "--port", str(smoke.WEB_PORT), "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        walk_off(browser)
                        # The page exists only with the feature on: a server of its own, on the stand-in.
                        smoke.stop(*server)
                        server = smoke.serve(Path(data), facebook_provider="stub")
                        walk(browser, data, product)
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
    print("Publish browser checks passed (stub only): with the feature off no way in and #publier falls back to Accueil; "
          "on the stand-in the page from the desktop navigation, « Mes affiches » and Accueil on a 360 px phone; no Page: "
          "said, with « Mon compte » and the posts; three posters chosen and reordered (numbers, « En tête »), a refused "
          "character said, a caption taken as the description, the draft kept through a reload; the sheet's Page, strip "
          "in order, description, a thumbnail failed then « Réessayer », what is already on the Page and « Publier à nouveau »; "
          "published in the order sent with the draft's stamp as the key, then the draft forgotten; an image refused names it, "
          "keeps the draft with a new stamp, and « Publier » again makes a second post; one tab at a time holds the page "
          "(« Continuer ici », the other then silent); a reload while the answer is held, then « Publier » again: one post; "
          "a list answered after the 202 keeps following the post; « Arrêter l’envoi »; the operator's limit refused by the "
          "server, then said by what the draft holds; an unknown outcome answered with the Page disconnected, then « Elle "
          "est sur ma Page »; the page for one poster published with its caption, reloaded during its uploads (« Publier… » "
          "off), then « Publier à nouveau »; a poster that cannot go; a damaged draft said, kept, then dropped by « Vider »; "
          "both themes at 1366 and 360 px, no sideways scroll; nothing of the feature kept on the device but its draft.")


if __name__ == "__main__":
    run()
