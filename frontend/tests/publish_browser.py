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
from affiche.posters.facebook_connect import STUB_CODE
from share_browser import READY, show_sharing, made_in_chat, sign_in
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
    page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    expect(page.get_by_role("heading", name=READY)).to_be_visible()
    panel = page.locator(".final-preview")
    if caption is not None:
        show_sharing(panel)
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
    context.on("request", lambda r: sent.append((r.headers.get("idempotency-key"), r.post_data_json))
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
    card = page.get_by_role("region", name="Page Facebook", exact=True)

    def connect_and_return(destination):
        saved, requests = draft_of(page), len(sent)
        page.get_by_role("link", name="Mon compte", exact=True).last.click()
        page.wait_for_url(smoke.ORIGIN + "/#compte")
        expect(card.get_by_role("heading", name="Page Facebook", exact=True)).to_be_focused()
        card.get_by_role("button", name="Connecter ma Page Facebook").click()
        page.wait_for_url(smoke.ORIGIN + "/#compte")
        card.get_by_role("radio", name=PAGE_NAME).check()
        card.get_by_role("button", name="Connecter cette Page").click()
        expect(card).to_contain_text(f"Page connectée : {PAGE_NAME}")
        card.get_by_role("link", name="Revenir à ma publication").click()
        page.wait_for_url(smoke.ORIGIN + "/#" + destination)
        expect(mine).to_be_visible()
        current = draft_of(page)
        if saved is None:
            assert current is None or (current["items"] == [] and current["description"] == "" and current["post"] is None)
        else:
            assert current == saved
        assert len(sent) == requests

    # A browser refusing the OAuth return marker must show the ordinary route before the seller leaves.
    page.get_by_role("link", name="Mon compte", exact=True).last.click()
    page.evaluate("""() => {
      const write = Storage.prototype.setItem;
      window.restoreSessionWrites = () => { Storage.prototype.setItem = write };
      Storage.prototype.setItem = function (name, value) {
        if (this === sessionStorage) throw new DOMException('Session indisponible', 'SecurityError');
        return write.call(this, name, value)
      }
    }""")
    card.get_by_role("button", name="Connecter ma Page Facebook").click()
    expect(card.get_by_role("button", name="Continuer vers Facebook")).to_be_visible()
    expect(card.get_by_role("status")).to_contain_text(re.compile("ouvrez « Publier( sur Facebook)? » depuis le menu"))
    page.evaluate("() => window.restoreSessionWrites()")
    card.get_by_role("link", name="Revenir à ma publication").click()
    expect(page.get_by_text(NO_PAGE, exact=True)).to_be_visible()
    assert not sent
    connect_and_return("publier")

    # Three posters confirmed in the « Publication » format (the first with a caption), and a fourth changed since its
    # confirmation: counted among those left out, not offered.
    a, title_a = confirmed(page, product, "Casque Bose QC noir, 450 000 Ar", caption="Casque Bose QC\n450 000 Ar 😀")
    b, title_b = confirmed(page, product, "Casque Sony noir, 300 000 Ar")
    c, title_c = confirmed(page, product, "Casque JBL noir, 200 000 Ar")
    d, title_d = confirmed(page, product, "Casque Sennheiser noir, 500 000 Ar")
    address = f"{smoke.ORIGIN}/api/creations/{d}"
    def change_price(price):
        current = page.request.get(address)
        assert current.ok, current.text()
        poster = current.json()
        document = poster["document"]
        changed = page.request.put(address, data=document | {"offer": document["offer"] | {"price_ar": price}},
            headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "If-Match": f'"{poster["revision"]}"',
                     "Idempotency-Key": str(uuid4())})
        assert changed.ok, changed.text()
        return document["input_id"]

    source_input = change_price(510000)
    assert len({title_a, title_b, title_c, title_d}) == 4, (title_a, title_b, title_c, title_d)
    tile = lambda title: grid.locator(".tile", has_text=title)  # noqa: E731
    row = lambda title: mine.locator("ol.chosen > li", has_text=title)  # noqa: E731

    smoke.go(page, "Publier")
    omitted = grid.locator(".left-out")
    summary = omitted.locator("summary")
    expect(summary).to_have_text("Affiches à préparer (1)")
    summary.click()
    expect(omitted.locator("li", has_text=title_d)).to_be_visible()
    grid.screenshot(path=str(OUT / "affiches-a-preparer-1366.png"))
    smoke.go(page, "Accueil")

    # Put the changed poster on the second real page. These drafts reuse its source and need no generation.
    square_title = "Casque carré de démonstration"
    for i in range(20):
        square = i == 19
        created = page.request.post(f"{smoke.ORIGIN}/api/creations", data={
            "input_id": source_input, "offer": {"title": square_title if square else f"Casque test {i}", "price_ar": 100000},
            "primary_format": "square" if square else "feed", "brand_selection": {"logo": False, "shop_name": False, "contact": False}},
            headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "Idempotency-Key": str(uuid4())})
        assert created.ok, created.text()
        if square:
            square_id = created.json()["id"]
    calls = []
    excluded_route = "**/api/facebook/posts/excluded*"

    def fail_second_once(route):
        calls.append(route.request.url)
        if len(calls) == 2 and "before=" in route.request.url:
            route.abort()
        else:
            route.continue_()

    page.route(excluded_route, fail_second_once)
    smoke.go(page, "Publier")
    expect(heading).to_be_visible()
    expect(page.locator(".shop-publish .titlerow .meta")).to_have_text(f"Sur la Page {PAGE_NAME}")
    for title in (title_a, title_b, title_c):
        expect(tile(title)).to_have_attribute("aria-pressed", "false")
    expect(tile(title_d)).to_have_count(0)
    expect(summary).to_have_text("Affiches à préparer (21)")
    assert not calls, calls
    summary.click()
    square_row = omitted.locator("li", has_text=square_title)
    changed_row = omitted.locator("li", has_text=title_d)
    expect(omitted.locator("li")).to_have_count(20)
    expect(square_row.get_by_role("button", name=re.compile("Préparer au format Publication"))).to_be_visible()
    expect(changed_row).to_have_count(0)
    omitted.get_by_role("button", name="Voir plus").click()
    expect(omitted.get_by_role("button", name="Réessayer")).to_be_visible()
    expect(tile(title_a)).to_be_enabled()
    expect(omitted.locator("li")).to_have_count(20)
    omitted.get_by_role("button", name="Réessayer").click()
    expect(omitted.locator("li")).to_have_count(21)
    expect(changed_row).to_contain_text(re.compile("modifi", re.I))
    assert len(calls) == 3 and calls[1] == calls[2] and "before=" in calls[2], calls
    page.unroute(excluded_route)

    # The batch survives either repair link, including its description and the order of the selected posters.
    for title in (title_b, title_a):
        tile(title).click()
    old_draft = draft_of(page)
    page.evaluate("""key => { const write = Storage.prototype.setItem
      window.restoreBatchStorage = () => { Storage.prototype.setItem = write }
      Storage.prototype.setItem = function (name, value) {
        if (name === key) throw new DOMException('Plein pour l’essai.', 'QuotaExceededError')
        return write.call(this, name, value) } }""", DRAFT_KEY)
    field.fill("Deux casques en boutique")
    changed_row.get_by_role("button", name="Vérifier l’affiche").click()
    expect(page.get_by_role("alert").filter(has_text="Réessayez avant de quitter")).to_be_visible()
    expect(field).to_have_value("Deux casques en boutique")
    assert page.url.endswith("#publier") and draft_of(page) == old_draft
    page.evaluate("() => window.restoreBatchStorage()")
    field.fill("Deux casques disponibles en boutique")
    kept = draft_of(page)
    for candidate, action, poster in ((changed_row, "Vérifier l’affiche", d), (square_row, "Préparer au format Publication", square_id)):
        candidate.get_by_role("button", name=re.compile(action)).click()
        page.wait_for_url(smoke.ORIGIN + "/#" + poster)
        expect(heading).to_have_count(0)
        target = "textes" if poster == d else "style"
        expect(page.locator("#onglet-" + target)).to_have_attribute("aria-selected", "true")
        expect(page.get_by_role("button", name=re.compile("ajouter à ma publication$", re.I))).to_have_count(0)
        page.get_by_role("button", name="Revenir à ma publication", exact=True).click()
        page.wait_for_url(smoke.ORIGIN + "/#publier")
        expect(field).to_have_value("Deux casques disponibles en boutique")
        assert draft_of(page) == kept and not sent
        if poster == d:
            summary.click()
    add = page.get_by_role("button", name=re.compile(r"^(Ajouter|Confirmer et ajouter) à ma publication$"))
    outcome = page.locator("#retour-ajout")

    def repair_current_file(*, download_first=False):
        # Match the price already drawn in the scene. A new revision still needs its own confirmed PNG.
        change_price(510000)
        change_price(500000)
        page.reload()
        summary.click()
        omitted.get_by_role("button", name="Voir plus").click()
        changed_row.get_by_role("button", name="Vérifier l’affiche").click()
        page.wait_for_url(smoke.ORIGIN + "/#" + d)
        page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
        expect(page.locator(".final-preview").get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)
        if download_first:
            smoke.download_review(page)
        expect(add).to_be_enabled()

    # While the repaired file is open, another tab changes the description and order.
    repair_current_file()
    other = context.new_page()
    open_atelier(other, "/#publier")
    other_mine = other.get_by_role("region", name="Votre publication", exact=True)
    other_mine.get_by_label("Description de la publication").fill("Ordre choisi dans le second onglet")
    other_mine.get_by_role("button", name=f"Déplacer {title_a}", exact=True).press("ArrowUp")
    kept = draft_of(other)
    assert kept["items"] == [a, b]
    other.close()
    # Re-read the actual cap at the time of the add. Failed add leaves every stored field intact.
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        store.execute("UPDATE shop_profile SET post_image_limit=2 WHERE id=1")
    add.click()
    expect(outcome).to_contain_text("La limite d’images est atteinte.")
    expect(field).to_have_value("Ordre choisi dans le second onglet")
    assert draft_of(page) == kept and not sent
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        store.execute("UPDATE shop_profile SET post_image_limit=NULL WHERE id=1")
    page.get_by_role("button", name="Réessayer l’ajout").click()
    expect(row(title_d)).to_be_visible()
    assert draft_of(page)["items"] == [a, b, d] and not sent
    row(title_d).get_by_role("button", name=f"Retirer « {title_d} »").click()

    # A downloaded file can already be added by a second tab. Preserve its position and stamp.
    repair_current_file(download_first=True)
    other = context.new_page()
    open_atelier(other, "/#publier")
    other.locator(".tile", has_text=title_d).click()
    other.get_by_role("button", name=f"Déplacer {title_d}", exact=True).press("ArrowUp")
    kept = draft_of(other)
    assert kept["items"] == [a, d, b]
    other.close()
    add.click()
    expect(outcome).to_contain_text("Cette affiche est déjà dans votre publication.")
    assert draft_of(page) == kept and not sent
    row(title_d).get_by_role("button", name=f"Retirer « {title_d} »").click()

    # A saved offer changed after the file was checked. The current candidate read refuses that file.
    repair_current_file(download_first=True)
    kept = draft_of(page)
    change_price(510000)
    add.click()
    expect(outcome).to_contain_text("Cette affiche ne peut plus être ajoutée.")
    assert draft_of(page) == kept and not sent

    # Reload while the candidate read is interrupted. The explicit add tap never survives that reload.
    repair_current_file()
    pending = []
    candidates = re.compile(r"/api/facebook/posts/candidates(?:\?|$)")
    page.route(candidates, lambda route: pending.append(route))
    add.click()
    until(page, lambda: pending)
    assert draft_of(page) == kept and not sent
    page.once("framenavigated", lambda frame: page.unroute(candidates))
    page.reload(wait_until="domcontentloaded")
    expect(tile(title_d)).to_have_attribute("aria-pressed", "false")
    assert draft_of(page) == kept and not sent
    change_price(510000)
    mine.get_by_role("button", name="Vider", exact=True).click()
    expect(publish).to_be_disabled()
    expect(mine.get_by_text("Choisissez au moins une affiche.")).to_be_visible()
    expect(mine.get_by_text("2 000 caractères au plus. Les retours à la ligne et les émojis sont gardés. Les caractères de contrôle sont refusés, sauf les retours à la ligne et les tabulations.")).to_be_visible()

    # Three chosen, then reordered with the handles' arrow keys: the numbers follow, and the first leads. The row's two
    # actions are at its right end: the bin, then the handle; no other button on it.
    handle = lambda title: mine.get_by_role("button", name=f"Déplacer {title}", exact=True)  # noqa: E731
    for title in (title_a, title_b, title_c):
        tile(title).click()
    expect(mine.locator("ol.chosen > li")).to_have_count(3)
    for title in (title_a, title_b, title_c):
        expect(row(title).get_by_role("button")).to_have_count(2)
        bin_box, grip_box, row_box = (row(title).get_by_role("button", name=f"Retirer « {title} »").bounding_box(),
                                      handle(title).bounding_box(), row(title).bounding_box())
        assert bin_box["x"] < grip_box["x"] and grip_box["x"] + grip_box["width"] >= row_box["x"] + row_box["width"] - 2, (bin_box, grip_box, row_box)
    handle(title_c).focus()
    page.keyboard.press("ArrowUp")
    expect(handle(title_c)).to_be_focused()
    handle(title_a).focus()
    page.keyboard.press("ArrowDown")
    for number, title in enumerate([title_c, title_a, title_b], 1):
        expect(mine.locator("ol.chosen > li").nth(number - 1)).to_contain_text(title)
        expect(tile(title).locator(".number")).to_have_text(str(number))
    expect(row(title_c)).to_contain_text("En tête")
    expect(row(title_a)).not_to_contain_text("En tête")
    # Sliding (T-FB-014): each poster has its handle. Dragged by it with the mouse, the third goes to the first place; the
    # numbers and « En tête » follow during the drag; the drop is the draft's order.
    expect(mine.locator("#aide-glisser")).to_contain_text("Glissez une affiche par sa poignée pour changer l’ordre.")
    expect(handle(title_b)).to_have_css("touch-action", "none")
    expect(row(title_b).locator(".name")).not_to_have_css("touch-action", "none")
    smoke.check_contrast(page, "the draft with its handles, 1366")
    mine.locator("ol.chosen").screenshot(path=str(OUT / "list-1366.png"))
    stamp = draft_of(page)["stamp"]
    handle(title_b).click()  # a tap moves nothing
    assert draft_of(page)["stamp"] == stamp
    sliding = re.compile(r"\bsliding\b")

    def hold_drag(title, to_top_of=None, by=0, steps=10):
        """The mouse down on that poster's handle and moved, to just under the top of another row or by `by` pixels; held."""
        # Aimed only once the page has stopped moving under the pointer (a sheet that closes gives the focus back, which
        # may scroll after the test's own scroll): two reads in a row on the same point, and that point on this handle.
        handle(title).scroll_into_view_if_needed()
        aim, steady = None, 0
        for _ in range(100):
            box = handle(title).bounding_box()
            point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            on = handle(title).evaluate("(e, [x, y]) => e.contains(document.elementFromPoint(x, y))", list(point))
            steady = steady + 1 if on and point == aim else 0
            aim = point
            if steady >= 2:
                break
            page.wait_for_timeout(50)
        assert steady >= 2, ("the handle never held still under the pointer", title, aim)
        x, y = aim
        end = row(to_top_of).bounding_box()["y"] + 5 if to_top_of else y + by
        page.mouse.move(x, y)
        page.mouse.down()
        for step in range(1, steps + 1):
            page.mouse.move(x, y + (end - y) * step / steps)
        expect(mine.locator("ol.chosen")).to_have_class(sliding)
        expect(row(title)).to_have_class(re.compile(r"\blifted\b"))  # this poster's, not a neighbour's

    row(title_c).evaluate("e => scrollBy({ top: e.getBoundingClientRect().top - 220, behavior: 'instant' })")  # away from the edges
    hold_drag(title_b, to_top_of=title_c)
    expect(row(title_b).locator(".number")).to_have_text("1")
    expect(row(title_b)).to_contain_text("En tête")
    expect(row(title_c).locator(".number")).to_have_text("2")
    expect(tile(title_b).locator(".number")).to_have_text("1")  # the grid's numbers are the list's, during the drag too
    expect(tile(title_c).locator(".number")).to_have_text("2")
    assert draft_of(page)["items"] == [c, a, b]  # nothing stored before the drop
    page.wait_for_timeout(400)  # the others have made room
    boxes = [box for box in (mine.locator("ol.chosen > li").nth(i).bounding_box() for i in range(3))]
    # The two others have made room under the dragged one's new place, one row apart; it follows the pointer above them.
    assert abs(boxes[1]["y"] - boxes[0]["y"] - boxes[0]["height"]) <= 1 and boxes[2]["y"] < boxes[0]["y"], boxes
    page.screenshot(path=str(OUT / "mid-drag-1366.png"))
    page.mouse.up()
    expect(mine.locator("ol.chosen")).not_to_have_class(re.compile(r"\bsliding\b"))
    for number, title in enumerate([title_b, title_c, title_a], 1):
        expect(mine.locator("ol.chosen > li").nth(number - 1)).to_contain_text(title)
        expect(mine.locator("ol.chosen > li").nth(number - 1).locator(".number")).to_have_text(str(number))
    expect(row(title_b)).to_contain_text("En tête")
    assert draft_of(page)["items"] == [b, c, a] and draft_of(page)["stamp"] != stamp
    # A drag ended by Escape leaves the order as it was, and stores nothing.
    stamp = draft_of(page)["stamp"]
    hold_drag(title_c, by=175, steps=7)
    expect(row(title_c).locator(".number")).to_have_text("3")
    page.keyboard.press("Escape")
    page.mouse.up()
    expect(mine.locator("ol.chosen")).not_to_have_class(re.compile(r"\bsliding\b"))
    expect(row(title_c).locator(".number")).to_have_text("2")
    assert draft_of(page)["items"] == [b, c, a] and draft_of(page)["stamp"] == stamp
    # With the handle focused, the up arrow moves the poster one place; the focus stays on its handle, and the place is said.
    handle(title_a).focus()
    page.keyboard.press("ArrowUp")
    expect(handle(title_a)).to_be_focused()
    expect(mine.locator("p.visually-hidden[role=status]")).to_have_text(f"{title_a} : place 2 sur 3.")
    order = [title_b, title_a, title_c]
    for number, title in enumerate(order, 1):
        expect(mine.locator("ol.chosen > li").nth(number - 1)).to_contain_text(title)
    # The sheet opened by the keyboard (Tab, Enter) while a drag is held: the drag is put back, never committed; the sheet
    # shows the order as stored; the release changes nothing (the first post below sends that order).
    row(title_b).evaluate("e => scrollBy({ top: e.getBoundingClientRect().top - 220, behavior: 'instant' })")
    stamp = draft_of(page)["stamp"]
    hold_drag(title_c, to_top_of=title_b)
    expect(row(title_c).locator(".number")).to_have_text("1")
    expect(tile(title_c).locator(".number")).to_have_text("1")
    for _ in range(20):
        if publish.evaluate("e => e === document.activeElement"):
            break
        page.keyboard.press("Tab")
    expect(publish).to_be_focused()
    page.keyboard.press("Enter")
    expect(sheet.get_by_role("img")).to_have_count(3)
    for number, title in enumerate(order, 1):
        expect(sheet.get_by_role("img").nth(number - 1)).to_have_attribute("alt", f"Image {number} : {title}")
    expect(mine.locator("ol.chosen")).not_to_have_class(sliding)
    page.mouse.up()
    sheet.get_by_role("button", name="Annuler").click()
    expect(sheet).to_have_count(0)
    assert draft_of(page)["items"] == [b, a, c] and draft_of(page)["stamp"] == stamp, draft_of(page)
    expect(row(title_c).locator(".number")).to_have_text("3")
    # The dragged poster taken out of the draft during the drag (« Retirer », by the keyboard): the drag ends, no row
    # stays moved, and a new drag works.
    row(title_b).evaluate("e => scrollBy({ top: e.getBoundingClientRect().top - 220, behavior: 'instant' })")
    hold_drag(title_c, by=-60, steps=6)
    mine.get_by_role("button", name=f"Retirer « {title_c} »").focus()
    page.keyboard.press("Enter")
    expect(mine.locator("ol.chosen > li")).to_have_count(2)
    expect(mine.locator("ol.chosen")).not_to_have_class(sliding)
    expect(mine.locator("ol.chosen > li[style*=transform]")).to_have_count(0)
    page.mouse.up()
    tile(title_c).click()  # back at the end
    assert draft_of(page)["items"] == [b, a, c]
    row(title_b).evaluate("e => scrollBy({ top: e.getBoundingClientRect().top - 220, behavior: 'instant' })")
    hold_drag(title_a, to_top_of=title_b)
    page.mouse.up()
    expect(mine.locator("ol.chosen > li").nth(0)).to_contain_text(title_a)
    assert draft_of(page)["items"] == [a, b, c]
    # Every move is said, by the handle's arrows: the same words again are spoken again.
    status = mine.locator("p.visually-hidden[role=status]")
    status.evaluate("""e => { window.spoken = []
      new MutationObserver(() => { if (e.textContent) window.spoken.push(e.textContent) }).observe(e, { childList: true, characterData: true, subtree: true }) }""")
    handle(title_a).focus()
    page.keyboard.press("ArrowDown")
    expect(status).to_have_text(f"{title_a} : place 2 sur 3.")
    page.keyboard.press("ArrowUp")
    expect(status).to_have_text(f"{title_a} : place 1 sur 3.")
    handle(title_a).focus()
    page.keyboard.press("ArrowDown")
    until(page, lambda: len(page.evaluate("window.spoken")) == 3)
    assert page.evaluate("window.spoken") == [f"{title_a} : place {n} sur 3." for n in (2, 1, 2)], page.evaluate("window.spoken")
    assert draft_of(page)["items"] == [b, a, c]
    # A refused character is said as it is typed; then the first poster's caption is taken as the description.
    field.fill("Essai\u0007")
    expect(mine.locator("#etat-description")).to_have_text("La description contient un caractère de contrôle refusé.")
    expect(publish).to_be_disabled()
    field.fill("")
    mine.get_by_role("button", name=f"Reprendre la légende de « {title_a} »").click()
    expect(field).to_have_value("Casque Bose QC\n450 000 Ar 😀")
    expect(mine.locator("#compte-description")).to_have_text("27 / 2 000")
    stored = draft_of(page)
    assert stored["items"] == [b, a, c] and stored["description"] == "Casque Bose QC\n450 000 Ar 😀" and stored["post"] is None, stored
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
                                "items": [{"creation_id": poster, "confirmation_id": confirmations[poster], "seen": None} for poster in (b, a, c)]}), sent[-1]
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
    # Denied consent returns to the disconnected batch with its description, order and send key intact.
    kept, sends_before_denial = draft_of(page), len(sent)
    page.get_by_role("link", name="Mon compte", exact=True).last.click()
    def deny_consent(route):
        answer = route.fetch()
        route.fulfill(response=answer, json={"url": answer.json()["url"].replace(f"code={STUB_CODE}", "error=access_denied")})
    page.route("**/api/facebook/connect", deny_consent, times=1)
    card.get_by_role("button", name="Connecter ma Page Facebook").click()
    expect(card.get_by_role("alert")).to_have_text("Connexion annulée.")
    card.get_by_role("link", name="Revenir à ma publication").click()
    page.wait_for_url(smoke.ORIGIN + "/#publier")
    expect(page.get_by_text(NO_PAGE, exact=True)).to_be_visible()
    assert draft_of(page) == kept and len(sent) == sends_before_denial
    connect_and_return("publier")
    expect(mine.locator("ol.chosen > li")).to_have_count(2)
    expect(field).to_have_value("Inconnu [stub:unknown]")
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
    disconnected = page.request.delete(smoke.ORIGIN + "/api/facebook/page",
        headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE)})
    assert disconnected.ok, disconnected.text()
    page.reload()
    expect(page.get_by_text(NO_PAGE, exact=True)).to_be_visible()
    caption_key = f"affiche.shop1.caption.{a}"
    page.evaluate("""key => {
      const set = Storage.prototype.setItem, remove = Storage.prototype.removeItem;
      window.restoreCaptionStorage = () => { Storage.prototype.setItem = set; Storage.prototype.removeItem = remove };
      Storage.prototype.setItem = function (name, value) {
        if (name === key) throw new DOMException('Écriture refusée', 'SecurityError');
        return set.call(this, name, value)
      };
      Storage.prototype.removeItem = function (name) {
        if (name === key) throw new DOMException('Suppression refusée', 'SecurityError');
        return remove.call(this, name)
      }
    }""", caption_key)
    account_link = page.get_by_role("link", name="Mon compte", exact=True).last
    account_link.click()
    retained_caption = page.get_by_label("Légende de l’affiche")
    expect(retained_caption).to_have_value("Légende reprise ici")
    retained_caption.fill("")
    account_link.click()
    expect(page.get_by_role("alert").filter(has_text="Copiez votre légende")).to_be_visible()
    assert page.url.endswith(f"#publier-{a}")
    assert page.evaluate("key => localStorage.getItem(key)", caption_key) == "Légende reprise ici"
    page.evaluate("() => window.restoreCaptionStorage()")
    retained_caption.fill("Légende reprise ici")
    connect_and_return(f"publier-{a}")
    expect(field).to_have_value("Légende reprise ici")
    assert draft_of(page) == kept_draft
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
    mark = len(sent)
    page.get_by_role("button", name="Revenir à ma publication", exact=True).click()
    page.wait_for_url(smoke.ORIGIN + f"/#publier-{d}")
    expect(mine.get_by_text("Cette affiche a été modifiée depuis sa vérification : vérifiez-la à nouveau pour la publier.")).to_be_visible()
    assert draft_of(page) == kept_draft and len(sent) == mark

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
    phone_nav = page.locator("nav.phone-bar")
    expect(phone_nav.get_by_role("link")).to_have_count(5)
    expect(phone_nav.get_by_role("link", name="Publier", exact=True)).to_be_visible()
    expect(phone_nav.get_by_role("link", name="Styles")).to_have_count(0)
    page.wait_for_function(smoke.SETTLED, polling=100)
    page.screenshot(path=str(OUT / "mes-affiches-360.png"))
    phone_nav.get_by_role("link", name="Publier", exact=True).click()
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
    return square_id


def walk_touch(browser, square_id):
    """Sliding with a finger (T-FB-014) on a 360 px phone: touches sent through Chromium's own input (CDP
    Input.dispatchTouchEvent), so the page receives pointer events of type touch and the browser applies touch-action.
    A drag on the handle moves the poster; a swipe on the row outside it scrolls the page and moves nothing."""
    context = browser.new_context(viewport={"width": 360, "height": 640}, has_touch=True, is_mobile=True, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(15000)
    errors, kinds = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    page.evaluate("() => { location.hash = 'publier' }")
    mine = page.get_by_role("region", name="Votre publication", exact=True)
    grid = page.get_by_role("region", name="Affiches confirmées", exact=True)
    expect(grid.locator(".tile")).to_have_count(2)  # the two posters still confirmed as they are
    for tile in grid.locator(".tile").all():
        tile.tap()
    rows = mine.locator("ol.chosen > li")
    expect(rows).to_have_count(2)
    first, second = rows.nth(0).locator("strong").inner_text(), rows.nth(1).locator("strong").inner_text()
    page.evaluate("() => addEventListener('pointerdown', event => { window.kinds = [...(window.kinds ?? []), event.pointerType] }, true)")
    chosen = draft_of(page)["items"]
    cdp = context.new_cdp_session(page)

    def touch(kind, x=0, y=0):
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y}]})

    def drag(start, end, steps=10):
        touch("touchStart", *start)
        for step in range(1, steps + 1):
            touch("touchMove", start[0] + (end[0] - start[0]) * step / steps, start[1] + (end[1] - start[1]) * step / steps)
            page.wait_for_timeout(16)
        touch("touchEnd")

    handle = mine.get_by_role("button", name=f"Déplacer {first}", exact=True)
    handle.scroll_into_view_if_needed()
    box, below = handle.bounding_box(), rows.nth(1).bounding_box()
    centre = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    drag(centre, (centre[0], below["y"] + below["height"] - 10))
    expect(rows.nth(0)).to_contain_text(second)
    expect(rows.nth(1)).to_contain_text(first)
    expect(rows.nth(0)).to_contain_text("En tête")
    assert page.evaluate("window.kinds") == ["touch"], page.evaluate("window.kinds")
    assert draft_of(page)["items"] == chosen[::-1], (chosen, draft_of(page))
    moved = draft_of(page)
    # A swipe up on the row, outside the handle: the page scrolls, the order stays.
    page.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
    mine.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    name = rows.nth(1).locator(".name").bounding_box()
    start = (name["x"] + 20, name["y"] + name["height"] / 2)
    drag(start, (start[0], start[1] - 250), steps=12)
    page.wait_for_timeout(300)
    after = page.evaluate("scrollY")
    assert after > before + 50, (before, after)
    assert draft_of(page) == moved, (draft_of(page), moved)
    expect(rows.nth(0)).to_contain_text(second)
    assert page.evaluate(smoke.NO_SIDEWAYS), "sideways scroll at 360 px"
    rows.nth(0).scroll_into_view_if_needed()
    smoke.check_contrast(page, "the draft with its handles, 360")
    mine.screenshot(path=str(OUT / "list-360.png"))
    # A square that has its own first generation keeps its format. Repair from the single composer creates a new
    # feed poster, whose confirmed file is chosen explicitly. The phone's current two-image draft survives.
    sends = []
    page.on("request", lambda request: sends.append(request.url)
            if request.method == "POST" and request.url.endswith("/api/facebook/posts") else None)
    page.evaluate("id => { location.hash = 'publier-' + id }", square_id)
    mine.get_by_role("button", name="Ouvrir l’affiche").click()
    page.wait_for_url(smoke.ORIGIN + "/#" + square_id)
    remake = page.get_by_role("button", name="Refaire en Publication")

    def generate_visual():
        page.get_by_role("button", name="Générer l’affiche", exact=True).click()
        page.get_by_role("button", name="Lancer la génération", exact=True).click()
        expect(page.get_by_role("heading", name="Vérifier votre affiche")).to_be_visible(timeout=30000)

    expect(page.locator("#onglet-style")).to_have_attribute("aria-selected", "true")
    source_url = smoke.ORIGIN + "/api/creations/" + square_id
    if not page.request.get(source_url + "/visuals").json()["items"]:
        generate_visual()
        page.locator(".final-preview").get_by_role("button", name="Corriger l’affiche").click()
        page.locator("#onglet-style").click()
    original = page.request.get(source_url).json()
    assert original["document"]["primary_format"] == "square"
    with page.expect_response(lambda response: response.url == source_url + "/copies" and response.request.method == "POST") as copied:
        remake.click()
    assert copied.value.ok, copied.value.text()
    copy_id = copied.value.json()["id"]
    assert copy_id != square_id
    page.wait_for_url(smoke.ORIGIN + "/#" + copy_id)
    generate_visual()
    preview = page.locator(".final-preview")
    expect(preview).to_contain_text("Copie au format Publication")
    expect(preview.get_by_role("button", name=re.compile("ajouter à ma publication$", re.I))).to_have_count(0)
    preview.get_by_role("button", name="Confirmer et utiliser cette copie").tap()
    page.wait_for_url(smoke.ORIGIN + "/#publier-" + copy_id)
    expect(mine.get_by_role("figure")).to_be_visible()
    assert page.request.get(source_url).json()["document"] == original["document"]
    assert page.request.get(smoke.ORIGIN + "/api/creations/" + copy_id).json()["confirmation"]["format"] == "feed"
    assert draft_of(page) == moved and not sends
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
                        server = smoke.serve(Path(data), facebook_provider="stub", formats_enabled="feed,square")
                        square_id = walk(browser, data, product)
                        walk_touch(browser, square_id)
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
          "said, with « Mon compte » and the posts; batch and single Page connection returns; repair without adding, "
          "a confirmed file added to the latest draft, duplicate/cap/stale/reload and storage refusals; three posters chosen and reordered (numbers, « En tête »), a refused "
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
