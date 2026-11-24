"""« Partager » in real Chromium (T-SHARE-002, D-SHARE-001): every way of opening a confirmed poster opens its current
confirmation and that confirmation's own render; an older confirmed file is an earlier version, without the live price.
The caption (T-SHARE-003, D-SHARE-003): kept on this device per shop and poster, copied on demand, the clipboard stubbed.
« Partager » (T-SHARE-004, D-SHARE-002 and 004): the JPEG made in the page and the tap, with the share sheet, the clipboard
and the canvas encoder stubbed; the app switch is the page's visibilitychange with its document.hidden set (a headless
Chromium page stays visible whatever page is in front, minimized windows included). The production build (vite preview, so build first) and the API on temporary stub data, no real env file, zero spend. Run from
backend: uv run python ../frontend/tests/share_browser.py (ports 8000 and 5173 must be free). Pictures: outputs/share-browser/.
A newer unconfirmed render is written straight into the temporary database, as the smokes do."""
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

import browser_smoke as smoke
from affiche.api import BUNDLE, MESSAGES
from affiche.db import utc_now
from terms_browser import FRAMES, open_atelier, until

OUT = smoke.ROOT / "outputs" / "share-browser"
REVIEW, FINAL, READY = "Vérifier la fidélité du produit", "Vérifier votre affiche", "Affiche confirmée"
EARLIER = "Version confirmée précédente"
EARLIER_LEDE = "Ce fichier a été confirmé avant vos dernières modifications. Vérifiez la version actuelle pour la partager."
DRAFT, DRAFT_LEDE = "Aperçu d’une version précédente", "Ce fichier a été préparé avant vos dernières modifications. Vérifiez la version actuelle."
OPEN_FAILED = "L’affiche confirmée n’a pas pu être ouverte."
CHANGED = "Cette affiche a été modifiée ailleurs : la version enregistrée a été rechargée. Réessayez."
BUTTON = "Télécharger ou partager"
PUBLISH = "Publier sur ma Page"


def copy_row(store, table, source, **changes):
    """A copy of a row under a new id (or `id`): what the schema allows and the interface does not make."""
    store.row_factory = sqlite3.Row
    row = dict(store.execute(f"SELECT * FROM {table} WHERE id=?", (source,)).fetchone()) | {"id": str(uuid4())} | changes
    store.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' * len(row))})", tuple(row.values()))
    return row["id"]


def walk(browser, errors, data, product):
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", accept_downloads=True)
    renders = []  # every render request that leaves the browser, with the revision it names
    context.on("request", lambda r: renders.append((r.url, r.headers.get("if-match"))) if r.method == "POST" and r.url.endswith("/renders") else None)
    page = context.new_page()
    page.set_default_timeout(15000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda r: print(f"HTTP {r.status} {r.request.method} {r.url}", flush=True) if r.status >= 400 and "/api/" in r.url else None)
    panel, error_line = page.locator(".final-preview"), page.locator(".message.error")
    download = page.get_by_role("button", name=BUTTON, exact=True)

    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)

    # A poster made in the chat at 450 000 Ar: its card's button reads « Télécharger ou partager »; with nothing confirmed it
    # asks for a render to check, then the check confirms it.
    poster = made_in_chat(page, product, "Casque Bose QC noir, 450 000 Ar")
    address = f"{smoke.ORIGIN}/api/creations/{poster}"
    assert len(renders) == 1, renders  # nothing current yet: a file to check
    page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    expect(page.get_by_role("heading", name=READY)).to_be_visible()
    first = page.request.get(address).json()["confirmation"]
    assert first and first["format"] == "feed", first
    panel.get_by_role("button", name="Fermer").click()
    # Now current: the button opens that confirmation, with no render request.
    download.click()
    current(panel, first)
    # FACEBOOK_PROVIDER=off (this server's): no « Publier sur ma Page », no publications (D-FB-PUBLISH-004).
    expect(panel.get_by_role("button", name=PUBLISH)).to_have_count(0)
    expect(panel.locator(".publications")).to_have_count(0)
    panel.get_by_text("Autres actions", exact=True).click()
    expect(panel.get_by_text("Le prix est dessiné dans l’image. Un nouveau prix demande une nouvelle version.")).to_be_visible()
    panel.get_by_role("button", name="Changer le prix").click()
    page.wait_for_url(f"{smoke.ORIGIN}/#{poster}")
    expect(page.locator("#champ-prix")).to_be_focused()
    assert len(renders) == 1, renders
    assert page.request.get(address).json()["confirmation"]["id"] == first["id"]

    def home():
        smoke.go(page, "Accueil")
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()

    def opened(way):
        """Opens the poster from Home (its recent row), the editor (its address) or the chat (its address), from Home."""
        home()
        if way == "home":
            page.locator(".home-recent button").first.click()
        else:
            page.evaluate("hash => { location.hash = hash }", poster if way == "editor" else f"message-{poster}")
        expect(panel).to_be_visible(timeout=20000)

    def saved_elsewhere(price):
        """Another price saved by the server's route, as another tab saves it, no render. Returns the new revision."""
        poster_now = page.request.get(address).json()
        document = poster_now["document"] | {"offer": poster_now["document"]["offer"] | {"price_ar": price}}
        saved = page.request.put(address, data=document, headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE),
            "If-Match": f'"{poster_now["revision"]}"', "Idempotency-Key": str(uuid4())})
        assert saved.ok and "confirmation" not in saved.json(), saved.text()
        assert page.request.get(address).json()["confirmation"] is None
        return saved.json()["revision"]

    def save_price(price):
        """The same with this tab on Home, its saver gone."""
        home()
        saved_elsewhere(price)

    # The price changed after the confirmation, no new render: from Home, the editor and the chat the confirmed file opens as
    # an earlier version, without the live price and without « Partager », its download kept and the check offered.
    # A verified file stays available from the library while another visual awaits review.
    listing = "**/api/creations?limit=50&status=active"
    def alternate_waiting(route):
        response = route.fetch()
        items = response.json()
        item = next(item for item in items["items"] if item["id"] == poster)
        assert item["has_current_file"]
        item["state"] = "to_review"
        route.fulfill(response=response, json=items)
    page.route(listing, alternate_waiting)
    smoke.go(page, "Mes affiches")
    file_row = page.locator(".library-row", has=page.locator(".library-item .badge", has_text="À vérifier"))
    file_row.get_by_role("button", name=re.compile("^Ouvrir le fichier de")).click()
    current(panel, first)
    panel.get_by_role("button", name="Fermer").click()
    page.unroute(listing)
    smoke.go(page, "Mes affiches")
    file_button = page.get_by_role("button", name=re.compile("^Ouvrir le fichier de"))
    expect(file_button).to_be_visible()
    saved_elsewhere(460000)
    file_button.click()
    expect(page.get_by_text("Cette affiche n’a plus de fichier confirmé pour sa version actuelle.")).to_be_visible()
    expect(panel).to_have_count(0)
    assert len(renders) == 1, renders
    for way in ("home", "editor", "chat"):
        opened(way)
        earlier(panel, first)
        assert len(renders) == 1, (way, renders)
        smoke.check_contrast(page, f"earlier version from {way}")
        page.screenshot(path=str(OUT / f"earlier-{way}-1366.png"))
        panel.get_by_role("button", name="Fermer").click()
    # Nothing is current: the chat's button asks for a render. The image draws the old price, so the server refuses it.
    download.click()
    blocked = page.get_by_role("dialog", name="Préparation de l’aperçu")
    expect(blocked).to_contain_text("Un texte dessiné dans l’image a changé")
    assert len(renders) == 1, renders
    expect(panel).to_have_count(0)
    blocked.get_by_role("button", name="Fermer").click()

    # The price back: the same image at a later revision. The earlier version's « Vérifier l’aperçu final » prepares the
    # current version, which is confirmed.
    save_price(450000)
    opened("chat")
    earlier(panel, first)
    # The new preview's PNG held after its metadata: the new live price waits for the new image.
    pngs, png = [], re.compile(r"/api/renders/[a-f0-9-]{36}/preview$")
    page.route(png, lambda route: pngs.append(route) if first["render_id"] not in route.request.url else route.continue_())
    panel.get_by_role("button", name="Vérifier l’aperçu final").click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    until(page, lambda: pngs)
    expect(panel.locator(".shot img")).not_to_have_attribute("src", f"/api/renders/{first['render_id']}/preview")
    expect(panel.locator(".facts")).not_to_contain_text("Prix")
    expect(panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True)).to_be_disabled()
    pngs.pop().continue_()
    page.unroute(png)
    expect(panel.locator(".facts")).to_contain_text(re.compile(r"Prix de l’offre\s*450\s000 Ar"))
    assert len(renders) == 2, renders
    page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    expect(page.get_by_role("heading", name=READY)).to_be_visible()
    confirmed = page.request.get(address).json()["confirmation"]
    assert confirmed["render_id"] not in (None, first["render_id"]), confirmed
    panel.get_by_role("button", name="Fermer").click()

    # A newer unconfirmed render at the same revision, the poster's latest render job: every opening still shows the
    # confirmation's own render, and no render request leaves.
    newer = str(uuid4())
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        job = store.execute("SELECT job_id FROM poster_renders WHERE id=?", (confirmed["render_id"],)).fetchone()[0]
        at = utc_now()
        copy_row(store, "poster_renders", confirmed["render_id"], id=newer, created_at=at, format_hash="0" * 64,
                 job_id=copy_row(store, "poster_jobs", job, result_ref=newer, created_at=at, started_at=at, finished_at=at))
    jobs = page.request.get(f"{address}/jobs").json()["items"]
    assert next(job for job in jobs if job["kind"] == "render")["result_ref"] == newer, jobs
    for way in ("home", "editor", "chat"):
        opened(way)
        current(panel, confirmed)
        page.screenshot(path=str(OUT / f"current-{way}-1366.png"))
        panel.get_by_role("button", name="Fermer").click()
    download.click()
    current(panel, confirmed)
    panel.get_by_role("button", name="Fermer").click()
    assert len(renders) == 2, renders

    # The poster read fails on the chat's button: the sentence and « Réessayer », never a render; the retry opens it.
    page.route(address, lambda route: route.abort() if route.request.method == "GET" else route.continue_())
    download.click()
    expect(error_line).to_contain_text(OPEN_FAILED)
    expect(panel).to_have_count(0)
    page.unroute(address)
    error_line.get_by_role("button", name="Réessayer").click()
    current(panel, confirmed)
    expect(error_line).to_have_count(0)
    panel.get_by_role("button", name="Fermer").click()
    assert len(renders) == 2, renders

    # The confirmation's render read fails at an opening: the same, and the newer unconfirmed render is never shown instead.
    rendered = f"{smoke.ORIGIN}/api/renders/{confirmed['render_id']}"
    page.route(rendered, lambda route: route.abort())
    home()
    page.evaluate("hash => { location.hash = hash }", poster)
    expect(error_line).to_contain_text(OPEN_FAILED)
    expect(page.locator(".editor")).to_be_visible()
    expect(panel).to_have_count(0)
    page.screenshot(path=str(OUT / "open-failed-1366.png"))
    page.unroute(rendered)
    error_line.get_by_role("button", name="Réessayer").click()
    current(panel, confirmed)
    assert len(renders) == 2, renders
    panel.get_by_role("button", name="Fermer").click()

    # The poster's jobs cannot be read at a direct opening: « Réessayer » reads the poster and its jobs again.
    jobs_reads = []

    def first_jobs_read_fails(route):
        jobs_reads.append(route.request.url)
        route.abort() if len(jobs_reads) == 1 else route.continue_()
    page.route(f"{address}/jobs", first_jobs_read_fails)
    home()
    page.evaluate("hash => { location.hash = hash }", poster)
    expect(error_line.get_by_role("button", name="Réessayer")).to_be_visible()
    expect(panel).to_have_count(0)
    error_line.get_by_role("button", name="Réessayer").click()
    current(panel, confirmed)
    assert len(jobs_reads) == 2, jobs_reads
    page.unroute(f"{address}/jobs")
    panel.get_by_role("button", name="Fermer").click()

    # Two formats confirmed at this revision (written in the database) and a finished render job that is the other one:
    # the poster's named confirmation, its primary format's, is shown, as current.
    square = str(uuid4())
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        at = utc_now()
        square_job = copy_row(store, "poster_jobs", job, result_ref=square, created_at=at, started_at=at, finished_at=at)
        copy_row(store, "poster_renders", confirmed["render_id"], id=square, format="square", job_id=square_job, created_at=at)
        copy_row(store, "confirmations", confirmed["id"], render_id=square, format="square", confirmed_at=at)
    assert page.request.get(address).json()["confirmation"] == confirmed
    opened("editor")
    current(panel, confirmed)
    panel.get_by_role("button", name="Fermer").click()
    # The current primary file is reused even when the newest render is square.
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
    current(panel, confirmed)
    assert len(renders) == 2, renders
    panel.get_by_role("button", name="Fermer").click()

    # A failed direct opening (a poster that does not exist), then a Home row whose read fails: « Réessayer » reads the
    # row's poster, not the address that failed before.
    home()
    page.evaluate("hash => { location.hash = hash }", str(uuid4()))
    expect(error_line).to_be_visible()
    page.route(address, lambda route: route.abort())
    page.locator(".home-recent button").first.click()
    expect(error_line.get_by_role("button", name="Réessayer")).to_be_visible()
    expect(panel).to_have_count(0)
    page.unroute(address)
    with page.expect_request(address):
        error_line.get_by_role("button", name="Réessayer").click()
    current(panel, confirmed)
    expect(error_line).to_have_count(0)
    panel.get_by_role("button", name="Fermer").click()

    # The named render's read answers after an edit and before its save is acknowledged: the panel opens as an earlier
    # version, without the live price, and stays so once the save lands.
    waiting, puts = [], []
    page.route(rendered, lambda route: waiting.append(route))
    page.route(address, lambda route: puts.append(route) if route.request.method == "PUT" else route.continue_())
    home()
    page.evaluate("hash => { location.hash = hash }", poster)
    until(page, lambda: waiting)
    page.get_by_label("Prix en ariary", exact=True).fill("455 000")
    until(page, lambda: puts)
    with page.expect_response(rendered):
        waiting.pop().continue_()
    earlier(panel, confirmed)
    puts.pop().continue_()
    expect(page.get_by_text("Enregistré", exact=True)).to_be_visible()
    earlier(panel, confirmed)
    page.unroute(rendered)
    page.unroute(address)
    panel.get_by_role("button", name="Fermer").click()
    opened("chat")  # the two tabs below start from the chat
    panel.get_by_role("button", name="Fermer").click()

    # Two tabs, two prices: this chat holds revision n at 450 000 Ar while revision n + 1 is saved elsewhere at 460 000 Ar
    # and confirmed (its render and confirmation written in the database: the stub cannot draw the new price). The tap reads
    # n + 1: the saved poster is reloaded, and nothing opens and nothing is asked. The next tap opens n + 1's own file beside
    # n + 1's price.
    held = page.request.get(address).json()["revision"]
    newest = saved_elsewhere(460000)
    assert newest == held + 1
    other, at = str(uuid4()), utc_now()
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        copy_row(store, "poster_renders", confirmed["render_id"], id=other, source_revision=newest, created_at=at,
                 job_id=copy_row(store, "poster_jobs", job, origin_revision=newest, result_ref=other, created_at=at, started_at=at, finished_at=at))
        copy_row(store, "confirmations", confirmed["id"], render_id=other, source_revision=newest, confirmed_revision=newest, confirmed_at=at)
    elsewhere = page.request.get(address).json()["confirmation"]
    assert elsewhere["render_id"] == other, elsewhere
    download.click()
    expect(page.locator(".message.notice")).to_contain_text(CHANGED)
    expect(panel).to_have_count(0)
    assert len(renders) == 2, renders
    download.click()
    current(panel, elsewhere)
    expect(panel.locator(".facts")).to_contain_text(re.compile(r"460\s000 Ar"))
    panel.get_by_role("button", name="Fermer").click()
    # An edit while the current file's panel is open (the page behind is inert for the owner; the attribute is lifted to
    # make one, its save held): the panel turns at once into the earlier version, and stays so once the save lands.
    opened("editor")
    current(panel, elsewhere)
    puts = []
    page.route(address, lambda route: puts.append(route) if route.request.method == "PUT" else route.continue_())
    page.locator(".editor").evaluate("e => e.removeAttribute('inert')")
    page.get_by_label("Prix en ariary", exact=True).fill("465 000")
    earlier(panel, elsewhere)
    until(page, lambda: puts)
    puts.pop().continue_()
    expect(page.get_by_text("Enregistré", exact=True)).to_be_visible()
    earlier(panel, elsewhere)
    page.unroute(address)
    # A failed save, then one refused as revision_conflict, the panel open: the same earlier file, its exact download.
    refusal = [(503, "storage_unavailable")]

    def refuse(route):
        if route.request.method != "PUT":
            return route.continue_()
        status, code = refusal[0]
        route.fulfill(status=status, content_type="application/json",
                      body=json.dumps({"error": {"code": code, "message_fr": "Refusé pour l’essai.", "retryable": status == 503}}))
    page.route(address, refuse)
    page.get_by_label("Prix en ariary", exact=True).fill("466 000")
    expect(page.get_by_text("Échec de l’enregistrement", exact=True)).to_be_visible()
    earlier(panel, elsewhere)
    refusal[0] = (409, "revision_conflict")
    page.get_by_role("button", name="Réessayer l’enregistrement").evaluate("e => e.click()")  # behind the panel
    expect(page.get_by_text("Une autre version existe", exact=True)).to_be_visible()
    earlier(panel, elsewhere)
    page.unroute(address)
    page.get_by_role("button", name="Abandonner mes modifications et recharger").evaluate("e => e.click()")
    page.get_by_role("button", name="Abandonner et recharger").click()
    expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value(re.compile(r"^465\D?000$"))
    earlier(panel, elsewhere)  # the saved poster reloaded opens on its latest render again
    panel.get_by_role("button", name="Fermer").click()
    opened("chat")
    panel.get_by_role("button", name="Fermer").click()
    # Saved elsewhere again, nothing confirmed: the tap reloads and asks for no render; the next one asks at the new revision.
    newest = saved_elsewhere(470000)
    download.click()
    expect(page.locator(".message.notice")).to_contain_text(CHANGED)
    expect(panel).to_have_count(0)
    assert len(renders) == 2, renders
    download.click()
    expect(blocked).to_contain_text("Un texte dessiné dans l’image a changé")
    assert len(renders) == 2, renders
    blocked.get_by_role("button", name="Fermer").click()

    # Nothing is current: an opening shows the latest render, n + 1's confirmed file, as an earlier version. Its read fails:
    # the sentence, then « Réessayer » reads the poster and its jobs again.
    fallback = f"{smoke.ORIGIN}/api/renders/{other}"
    page.route(fallback, lambda route: route.abort())
    home()
    page.evaluate("hash => { location.hash = hash }", poster)
    expect(error_line).to_contain_text(OPEN_FAILED)
    expect(panel).to_have_count(0)
    page.unroute(fallback)
    error_line.get_by_role("button", name="Réessayer").click()
    earlier(panel, elsewhere)
    panel.get_by_role("button", name="Fermer").click()
    # That read answers late, after this tab saved another price: its answer changes nothing.
    waiting = []
    page.route(fallback, lambda route: waiting.append(route))
    home()
    page.evaluate("hash => { location.hash = hash }", poster)
    until(page, lambda: waiting)
    with page.expect_response(fallback):
        page.get_by_label("Prix en ariary", exact=True).fill("480 000")
        until(page, lambda: page.request.get(address).json()["revision"] > newest)
        waiting.pop().continue_()
    page.evaluate(FRAMES)
    expect(panel).to_have_count(0)
    expect(error_line).to_have_count(0)
    page.unroute(fallback)
    assert len(renders) == 2, renders

    # A render prepared and never confirmed, then another price saved: reopened, it is an earlier version, without the live
    # price, the checklist or a download, and the check is offered.
    save_price(450000)
    opened("chat")
    panel.get_by_role("button", name="Fermer").click()
    download.click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    assert len(renders) == 3, renders
    prepared = next(item for item in page.request.get(f"{address}/jobs").json()["items"] if item["kind"] == "render")["result_ref"]
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{prepared}/preview")
    panel.get_by_role("button", name="Fermer").click()
    save_price(460000)
    for way in ("editor", "chat"):
        opened(way)
        expect(panel.get_by_role("heading", name=DRAFT)).to_be_visible()
        expect(panel.locator(".lede")).to_have_text(DRAFT_LEDE)
        expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{prepared}/preview")
        expect(panel.locator(".facts")).not_to_contain_text("Prix")
        expect(panel).not_to_contain_text(re.compile(r"\d{3}\s000"))
        expect(panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True)).to_have_count(0)
        expect(panel.get_by_role("link", name="Télécharger le PNG")).to_have_count(0)
        expect(panel.get_by_role("button", name="Vérifier l’aperçu final")).to_be_visible()
        page.screenshot(path=str(OUT / f"earlier-draft-{way}-1366.png"))
        panel.get_by_role("button", name="Fermer").click()
    assert len(renders) == 3, renders

    # The undo: the price back, the same image at a later revision, and that older render confirmed there (by the route, as
    # another tab would). Reopened, the poster read names it at the saved revision: the current file, ready.
    save_price(450000)
    made, revision = page.request.get(f"{smoke.ORIGIN}/api/renders/{prepared}").json(), page.request.get(address).json()["revision"]
    response = page.request.post(f"{address}/confirmations", data={"render_id": prepared, "png_sha256": made["png_sha256"],
        "checks": {check: True for check in ("framing", "content", "identity", "readability")},
        "acknowledged_warning_ids": [warning["id"] for warning in made["warnings"]]},
        headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "If-Match": f'"{revision}"', "Idempotency-Key": str(uuid4())})
    assert response.status == 201, response.text()
    undone = page.request.get(address).json()["confirmation"]
    assert undone["render_id"] == prepared and made["source_revision"] < revision, (undone, made, revision)
    for way in ("editor", "chat"):
        opened(way)
        current(panel, undone)
        expect(panel.get_by_role("heading", name=EARLIER)).to_have_count(0)
        expect(panel.locator(".facts")).to_contain_text(re.compile(r"450\s000 Ar"))
        panel.get_by_role("button", name="Fermer").click()
    assert len(renders) == 3, renders

    # A's confirmation answered after a render job B ended and replaced A in the panel: the answer belongs to A alone, and B
    # keeps its checklist, without a download. (Nothing named: two saves away and back. B is a second render of this
    # revision written in the database, presented as running until released.)
    save_price(460000)
    save_price(450000)
    opened("editor")  # the undone file, an earlier version now
    panel.get_by_role("button", name="Fermer").click()
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    assert len(renders) == 4, renders
    a_render = next(item for item in page.request.get(f"{address}/jobs").json()["items"] if item["kind"] == "render")["result_ref"]
    panel.get_by_role("button", name="Fermer").click()
    b_render = str(uuid4())
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        at = utc_now()
        a_job = store.execute("SELECT job_id FROM poster_renders WHERE id=?", (a_render,)).fetchone()[0]
        b_job = copy_row(store, "poster_jobs", a_job, result_ref=b_render, created_at=at, started_at=at, finished_at=at)
        copy_row(store, "poster_renders", a_render, id=b_render, job_id=b_job, format_hash="2" * 64, created_at=at)
    running = {"on": True}

    def as_running(route):
        if not running["on"]:
            return route.continue_()
        response = route.fetch()
        body = response.json()
        for item in body.get("items", [body]):
            if item["id"] == b_job:
                item.update(status="running", result_ref=None, finished_at=None)
        route.fulfill(response=response, json=body)
    page.route(f"{address}/jobs", as_running)
    page.route(f"{smoke.ORIGIN}/api/jobs/{b_job}", as_running)
    home()
    page.evaluate("hash => { location.hash = hash }", poster)
    expect(panel.get_by_role("heading", name=FINAL)).to_be_visible()
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{a_render}/preview")
    confirms = []
    page.route(f"{address}/confirmations", lambda route: confirms.append((route, route.fetch())))
    panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    until(page, lambda: confirms)
    running["on"] = False
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{b_render}/preview", timeout=20000)
    route, answer = confirms.pop()
    with page.expect_response(f"{address}/confirmations"):
        route.fulfill(response=answer)
    page.evaluate(FRAMES)
    expect(panel.get_by_role("heading", name=FINAL)).to_be_visible()
    expect(panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True)).to_be_enabled()
    expect(panel.get_by_role("link", name="Télécharger le PNG")).to_have_count(0)
    for pattern in (f"{address}/confirmations", f"{address}/jobs", f"{smoke.ORIGIN}/api/jobs/{b_job}"):
        page.unroute(pattern)
    a_confirmed = page.request.get(address).json()["confirmation"]
    assert a_confirmed["render_id"] == a_render, a_confirmed  # recorded on the server all the same
    panel.get_by_role("button", name="Fermer").click()

    # A private review in this tab at revision N whose poster read answers N + 1 with no confirmation (another tab
    # saved): « Affiche confirmée » never shows; the saved poster is reloaded, as the chat's button does.
    saved_elsewhere(470000)
    page.evaluate("""() => { window.sawReady = false; new MutationObserver(() => {
        if (document.getElementById('final-title')?.textContent.includes('Affiche confirmée')) window.sawReady = true
    }).observe(document.body, { childList: true, subtree: true, characterData: true }) }""")
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
    expect(page.locator(".message.notice")).to_contain_text(CHANGED)
    expect(panel).to_have_count(0)
    assert page.evaluate("window.sawReady") is False
    assert len(renders) == 4, renders  # the latest revision is checked before requesting a render

    # The poster's jobs cannot be read; its « Réessayer » reads the poster, held while the owner edits the price, then
    # released before that edit is saved: the edit stays and is saved, and the poster is read again after it.
    jobs_reads.clear()
    page.route(f"{address}/jobs", first_jobs_read_fails)
    home()
    page.evaluate("hash => { location.hash = hash }", poster)
    expect(error_line.get_by_role("button", name="Réessayer")).to_be_visible()
    page.unroute(f"{address}/jobs")
    gets = []
    page.route(address, lambda route: gets.append(route) if route.request.method == "GET" and not gets else route.continue_())
    error_line.get_by_role("button", name="Réessayer").click()
    until(page, lambda: gets)
    page.get_by_label("Prix en ariary", exact=True).fill("475 000")
    gets[0].continue_()
    until(page, lambda: page.request.get(address).json()["document"]["offer"]["price_ar"] == 475000)
    expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value(re.compile(r"^475\D?000$"))
    expect(page.get_by_text("Enregistré", exact=True)).to_be_visible()
    page.unroute(address)
    context.close()


def sign_in(page, identifier, password):
    page.get_by_label("Identifiant de la boutique", exact=True).fill(identifier)
    page.get_by_label("Mot de passe", exact=True).fill(password)
    page.get_by_role("button", name="Ouvrir l’atelier").click()
    expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()


def show_sharing(panel):
    summary = panel.locator("summary", has_text="Partager dans une autre application")
    expect(summary).to_be_visible()
    if not summary.evaluate("el => el.parentElement.open"):
        summary.click()


def made_in_chat(page, product, message):
    """Generate a poster in Message and open the private review of its selected scene."""
    page.get_by_role("link", name="Créer une affiche").click()
    page.locator(".composer input[type=file]").set_input_files([product])
    expect(page.locator(".tray .pic")).to_have_count(1)
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    page.get_by_label("Votre message").fill(message)
    page.get_by_role("button", name="Envoyer").click()
    page.get_by_role("log").get_by_role("button", name="Créer l’affiche").click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    page.get_by_role("button", name="Vérifier", exact=True).click(timeout=30000)
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    poster = page.url.split("#message-")[1]
    address = f"{smoke.ORIGIN}/api/creations/{poster}"
    assert page.request.get(address).json()["confirmation"] is None
    assert page.request.get(address + "/visuals").json()["items"][0]["status"] == "pending_review"
    return poster


# The clipboard, stubbed in every page of a context (the real one needs a permission and is shared by the whole machine):
# each copy is recorded, and refused while `copyRefused` is set.
CLIPBOARD = """window.copies = []; window.copyRefused = false
Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: text => { window.copies.push(text)
  return window.copyRefused ? Promise.reject(new DOMException('Refusé pour l’essai.', 'NotAllowedError')) : Promise.resolve() } } })"""
# One Storage method refusing for the captions' keys only (a full or blocked storage); `restore()` puts it back.
REFUSE = """method => { const real = Storage.prototype[method]; window.restore = () => { Storage.prototype[method] = real }
  Storage.prototype[method] = function (key, ...rest) {
    if (String(key).includes('.caption.')) throw new DOMException('Refusé pour l’essai.', 'QuotaExceededError')
    return real.call(this, key, ...rest) } }"""
STORED = "key => localStorage[key] ?? null"  # read past a refusing getItem
HELP = ("Sur Facebook, passez d’abord sur votre Page dans l’application Facebook. Puis touchez « Partager », choisissez "
        "l’application et collez la légende dans votre publication.")
TAB_ONLY = ("La légende reste dans cet onglet, sans être gardée sur cet appareil. Copiez-la avant de fermer : en rouvrant "
            "l’affiche, l’ancienne légende peut revenir.")
NOT_CLEARED = "La légende n’a pas pu être effacée de cet appareil : elle peut revenir quand vous rouvrez l’affiche."
TOO_LONG = "La légende dépasse 2 000 caractères : elle n’est pas gardée sur cet appareil."
BAD_CHARACTER = "La légende contient un caractère invisible non accepté : elle n’est pas gardée sur cet appareil."
COPIED = "Légende copiée : collez-la dans votre publication."
NOT_COPIED = "La copie a échoué. Sélectionnez la légende dans le champ, puis copiez-la."


def captions(browser, errors, data, product):
    """The caption (T-SHARE-003, D-SHARE-003): kept on this device per shop and poster, copied on demand."""
    engine = smoke.make_engine(Path(data))
    password_b = os.urandom(12).hex()
    hashed = smoke.PASSWORDS.hash(password_b)
    with smoke.write_tx(engine) as conn:
        shop_b = smoke.shops.create_shop(conn, "boutiquedeux", "Boutique Deux", hashed)
        smoke.credits.grant(conn, shop_b, 20, origin="offered", ref="tests", actor="tests")
        smoke.accepted(conn, shop_b)
    engine.dispose()
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    context.add_init_script(CLIPBOARD)

    def tab():
        made = context.new_page()
        made.set_default_timeout(15000)
        made.on("pageerror", lambda error: errors.append(str(error)))
        return made
    page = tab()
    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    poster = made_in_chat(page, product, "Casque Bose QC noir, 450 000 Ar")
    key, other = f"affiche.shop1.caption.{poster}", f"affiche.shop1.caption.{uuid4()}"
    stored = lambda at=page, name=key: at.evaluate(STORED, name)

    def parts(at):
        panel = at.locator(".final-preview")
        return (panel, panel.get_by_label("Légende de la publication", exact=True),
                panel.get_by_role("button", name="Copier la légende", exact=True))
    panel, field, copy = parts(page)
    status, address = panel.locator("#etat-legende"), f"{smoke.ORIGIN}/api/creations/{poster}"  # mounted with the field

    def reopen(at=page):
        parts(at)[0].get_by_role("button", name="Fermer").click()
        at.get_by_role("button", name=BUTTON, exact=True).click()
        expect(at.get_by_role("heading", name=READY)).to_be_visible()
        show_sharing(at.locator(".final-preview"))

    # No field on the file to check; confirmed in place, the field appears, empty: nothing kept for this poster yet.
    expect(field).to_have_count(0)
    page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    expect(page.get_by_role("heading", name=READY)).to_be_visible()
    show_sharing(page.locator(".final-preview"))
    expect(field).to_have_value("")
    expect(copy).to_be_disabled()
    expect(panel.get_by_text(HELP, exact=True)).to_be_visible()
    assert stored() is None
    page.evaluate("key => localStorage.setItem(key, 'Légende d’une autre affiche')", other)  # never pruned below

    # 2 000 emoji (4 000 UTF-16 units) kept, edited, reloaded.
    many = "😀" * 2000
    field.fill(many)
    assert stored() == many
    field.press("Control+End")
    field.press("Backspace")
    page.keyboard.insert_text("🎉")
    edited = "😀" * 1999 + "🎉"
    expect(field).to_have_value(edited)
    assert stored() == edited
    page.reload()
    expect(page.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(page.locator(".final-preview"))
    expect(field).to_have_value(edited)
    # 2 001: the sentence, the text kept in the field, the stored value unchanged; nothing to copy.
    field.press("Control+End")
    page.keyboard.insert_text("😀")
    expect(field).to_have_value(edited + "😀")
    expect(panel.get_by_text(TOO_LONG, exact=True)).to_be_visible()
    expect(field).to_have_attribute("aria-invalid", "true")
    expect(copy).to_be_disabled()
    assert stored() == edited
    # A NUL after valid text: refused the same way, never taken for blank.
    field.fill("Galaxy A15\x00   ")
    expect(panel.get_by_text(BAD_CHARACTER, exact=True)).to_be_visible()
    assert stored() == edited
    # A multiline text with a tab, pasted at once: kept as it is, the sentence gone.
    multi = "Galaxy A15 128 Go\nLivraison à Tana 📦\tdès demain"
    field.fill(multi)
    assert stored() == multi
    expect(status).to_have_text("")
    expect(field).not_to_have_attribute("aria-invalid", "true")

    # « Copier la légende »: refused, then copied; the typed value each time.
    page.evaluate("window.copyRefused = true")
    copy.click()
    expect(panel.get_by_text(NOT_COPIED, exact=True)).to_be_visible()
    expect(panel.get_by_text(COPIED, exact=True)).to_have_count(0)
    page.evaluate("window.copyRefused = false")
    copy.click()
    expect(panel.get_by_text(COPIED, exact=True)).to_be_visible()
    expect(panel.get_by_text(NOT_COPIED, exact=True)).to_have_count(0)
    assert page.evaluate("window.copies") == [multi, multi]
    field.press("Control+End")
    page.keyboard.insert_text("!")  # a new input withdraws « copiée »: it named the text before it
    expect(panel.get_by_text(COPIED, exact=True)).to_have_count(0)
    assert stored() == multi + "!"
    # No clipboard at all (an insecure page): the same sentence, nothing else blocked.
    page.evaluate("Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined })")
    copy.click()
    expect(panel.get_by_text(NOT_COPIED, exact=True)).to_be_visible()
    expect(copy).to_be_enabled()
    page.reload()  # the stub back
    expect(page.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(page.locator(".final-preview"))

    # Clearing: a refused removal says so and keeps the entry; a later clear removes it.
    page.evaluate(REFUSE, "removeItem")
    field.fill("")
    expect(panel.get_by_text(NOT_CLEARED, exact=True)).to_be_visible()
    assert stored() == multi + "!"
    page.evaluate("restore()")
    field.fill("   ")
    assert stored() is None
    expect(panel.get_by_text(NOT_CLEARED, exact=True)).to_have_count(0)
    expect(copy).to_be_disabled()
    # A refused write: the text stays in the field with the sentence, and is still copied.
    page.evaluate(REFUSE, "setItem")
    field.fill("Texte gardé dans l’onglet")
    expect(panel.get_by_text(TAB_ONLY, exact=True)).to_be_visible()
    expect(field).to_have_value("Texte gardé dans l’onglet")
    assert stored() is None
    copy.click()
    expect(panel.get_by_text(COPIED, exact=True)).to_be_visible()
    assert page.evaluate("window.copies")[-1] == "Texte gardé dans l’onglet"
    page.evaluate("restore()")
    field.fill(multi)
    assert stored() == multi
    # A refused read at opening: an empty field, the sentence, and nothing written or removed for this opening (cleared,
    # the field says the unread caption may come back).
    page.evaluate(REFUSE, "getItem")
    reopen()
    expect(field).to_have_value("")
    expect(status).to_have_text(TAB_ONLY)
    field.fill("Ne remplace rien")
    expect(status).to_have_text(TAB_ONLY)
    assert stored() == multi
    field.fill("")
    expect(status).to_have_text(NOT_CLEARED)
    assert stored() == multi
    page.evaluate("restore()")
    reopen()
    expect(field).to_have_value(multi)
    expect(status).to_have_text("")

    # A render job ending while the confirmed panel is open replaces its preview (no « Fermer »): the field goes until the
    # new file is confirmed, and comes back with the typed text and its sentence, never read again. (The job is a second
    # render of this revision written in the database, presented as running until released, as walk() does. It keeps the
    # format hash, which the confirmation checks, and differs by its build hash, which the schema's UNIQUE needs.)
    confirmed = page.request.get(address).json()["confirmation"]
    later_render = str(uuid4())
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        at = utc_now()
        render_job = store.execute("SELECT job_id FROM poster_renders WHERE id=?", (confirmed["render_id"],)).fetchone()[0]
        later_job = copy_row(store, "poster_jobs", render_job, result_ref=later_render, created_at=at, started_at=at, finished_at=at)
        copy_row(store, "poster_renders", confirmed["render_id"], id=later_render, job_id=later_job, renderer_build_hash="3" * 64, created_at=at)
    running = {"on": True}

    def as_running(route):
        if not running["on"]:
            return route.continue_()
        response = route.fetch()
        body = response.json()
        for item in body.get("items", [body]):
            if item["id"] == later_job:
                item.update(status="running", result_ref=None, finished_at=None)
        route.fulfill(response=response, json=body)
    page.route(f"{address}/jobs", as_running)
    page.route(f"{smoke.ORIGIN}/api/jobs/{later_job}", as_running)
    def opened_from_home(hash):
        """A new opening of the poster: from the chat straight to its editor is only a change of view, which opens nothing."""
        smoke.go(page, "Accueil")
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        page.evaluate("hash => { location.hash = hash }", hash)
    panel.get_by_role("button", name="Fermer").click()
    opened_from_home(poster)  # the editor's opening shows the confirmation and follows the running job
    expect(page.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(page.locator(".final-preview"))
    expect(field).to_have_value(multi)
    page.evaluate(REFUSE, "setItem")
    field.fill("Gardé pendant le rendu")
    expect(status).to_have_text(TAB_ONLY)
    running["on"] = False
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{later_render}/preview", timeout=20000)
    expect(field).to_have_count(0)
    panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    expect(page.get_by_role("heading", name=READY)).to_be_visible()
    show_sharing(page.locator(".final-preview"))
    expect(field).to_have_value("Gardé pendant le rendu")
    expect(status).to_have_text(TAB_ONLY)
    assert stored() == multi
    page.evaluate("restore()")
    page.unroute(f"{address}/jobs")
    page.unroute(f"{smoke.ORIGIN}/api/jobs/{later_job}")
    # « Fermer » ends the opening: reopened from the chat, the stored caption is read again.
    panel.get_by_role("button", name="Fermer").click()
    opened_from_home(f"message-{poster}")
    expect(page.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(page.locator(".final-preview"))
    expect(field).to_have_value(multi)
    expect(status).to_have_text("")

    # Two tabs on the poster: an idle tab never writes; the last keystroke's whole text wins; nothing is pruned.
    second = tab()
    second.goto(f"{smoke.ORIGIN}/#message-{poster}")
    expect(second.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(second.locator(".final-preview"))
    second_field = parts(second)[1]
    expect(second_field).to_have_value(multi)
    second_field.fill("Texte du second onglet")
    assert stored() == "Texte du second onglet"
    page.evaluate(FRAMES)
    expect(field).to_have_value(multi)  # this tab idle: shown as read, never written
    assert stored() == "Texte du second onglet"
    field.press("Control+End")
    page.keyboard.insert_text(" !")
    assert stored() == multi + " !"
    second.reload()  # this tab's chat holds no card: its address opens the panel again
    expect(second.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(second.locator(".final-preview"))
    expect(second_field).to_have_value(multi + " !")
    second.close()
    assert stored(name=other) == "Légende d’une autre affiche"

    # A phone, 360 × 640, both themes; the keyboard goes from the field to « Copier la légende », which Enter copies.
    page.set_viewport_size({"width": 360, "height": 640})
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        field.scroll_into_view_if_needed()
        smoke.check_contrast(page, f"caption, 360 px, {scheme}")
        assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), "the page scrolls sideways"
        assert panel.evaluate("e => e.scrollWidth <= e.clientWidth"), "the panel scrolls sideways"
        page.screenshot(path=str(OUT / f"caption-360-{scheme}.png"))
    page.emulate_media(color_scheme="light")
    field.focus()
    page.keyboard.press("Tab")
    expect(copy).to_be_focused()
    page.keyboard.press("Enter")
    expect(panel.get_by_text(COPIED, exact=True)).to_be_visible()
    assert page.evaluate("window.copies")[-1] == multi + " !"
    page.set_viewport_size({"width": 1366, "height": 768})

    # Another shop signs in on this device: its own poster's field reads only its own keys, even under the same poster id,
    # and writes only its own; this shop's tab is signed out and shows no caption.
    context.clear_cookies()
    other_shop = tab()
    open_atelier(other_shop)
    sign_in(other_shop, "boutiquedeux", password_b)
    expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()
    expect(page.get_by_label("Légende de la publication")).to_be_hidden()
    assert page.evaluate("() => !document.body.innerText.includes('Galaxy A15')")
    page.close()  # it still holds the device's chat
    theirs = made_in_chat(other_shop, product, "Casque Sony noir, 300 000 Ar")
    other_shop.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    expect(other_shop.get_by_role("heading", name=READY)).to_be_visible()
    show_sharing(other_shop.locator(".final-preview"))
    their_field, their_key = parts(other_shop)[1], f"affiche.shop{shop_b}.caption.{theirs}"
    expect(their_field).to_have_value("")
    other_shop.evaluate("key => localStorage.setItem(key, 'Légende de la boutique A')", f"affiche.shop1.caption.{theirs}")
    reopen(other_shop)
    expect(their_field).to_have_value("")
    their_field.fill("Légende de la boutique B")
    assert stored(other_shop, their_key) == "Légende de la boutique B"
    assert stored(other_shop) == multi + " !" and stored(other_shop, other) == "Légende d’une autre affiche"

    # « Se déconnecter » erases the shop's captions, and only that shop's.
    def sign_out(at):
        parts(at)[0].get_by_role("button", name="Fermer").click()
        with smoke.replaced(at):
            smoke.go(at, "Se déconnecter")
        expect(at.get_by_label("Mot de passe", exact=True)).to_be_visible()
    keys = lambda prefix: other_shop.evaluate("prefix => Object.keys(localStorage).filter(key => key.startsWith(prefix))", prefix)
    sign_out(other_shop)
    assert keys(f"affiche.shop{shop_b}.") == []
    assert sorted(keys("affiche.shop1.caption.")) == sorted([key, other, f"affiche.shop1.caption.{theirs}"])
    sign_in(other_shop, smoke.IDENTIFIER, smoke.PASSWORD)
    other_shop.goto(f"{smoke.ORIGIN}/#message-{poster}")
    expect(other_shop.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(other_shop.locator(".final-preview"))
    expect(parts(other_shop)[1]).to_have_value(multi + " !")
    sign_out(other_shop)
    assert keys("affiche.shop1.") == []
    context.close()


# The share sheet, the clipboard and the canvas encoder, stubbed in every page of a context before the application runs.
# `shareMode`: resolve, hold (settled later through heldShares) or the name of the DOMException it rejects with;
# `copyMode`: resolve, reject, throw (at once) or hold (heldCopies); `blobMode`: real, hold (the real blob, delivered
# through heldBlobs), never, png, null. `noFiles`: canShare refuses every file. Every canvas given to toBlob is kept.
SHARE_STUBS = """window.shares = []; window.shareMode = 'resolve'; window.heldShares = []
window.copies = []; window.copyMode = 'resolve'; window.heldCopies = []
window.blobMode = 'real'; window.toBlobs = 0; window.heldBlobs = []; window.canvases = []
const refused = name => new DOMException('Refusé pour l’essai.', name)
Object.defineProperty(navigator, 'share', { configurable: true, value: data => {
  window.shares.push(data)
  if (window.shareMode === 'resolve') return Promise.resolve()
  if (window.shareMode === 'hold') return new Promise((ok, ko) => window.heldShares.push({ ok, ko: name => ko(refused(name)) }))
  return Promise.reject(refused(window.shareMode)) } })
Object.defineProperty(navigator, 'canShare', { configurable: true, value: data => !window.noFiles && Array.isArray(data?.files)
  && data.files.length > 0 && data.files.every(file => file instanceof File && file.type === 'image/jpeg') })
Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: text => {
  window.copies.push(text)
  if (window.copyMode === 'throw') throw refused('NotAllowedError')
  if (window.copyMode === 'hold') return new Promise((ok, ko) => window.heldCopies.push({ ok, ko: () => ko(refused('NotAllowedError')) }))
  return window.copyMode === 'reject' ? Promise.reject(refused('NotAllowedError')) : Promise.resolve() } } })
const toBlob = HTMLCanvasElement.prototype.toBlob
HTMLCanvasElement.prototype.toBlob = function (callback, ...rest) {
  window.toBlobs++; window.canvases.push(this)
  const mode = window.blobMode
  if (mode === 'never') return
  if (mode === 'null') return setTimeout(() => callback(null))
  if (mode === 'png') return toBlob.call(this, callback, 'image/png')
  if (mode === 'hold') return toBlob.call(this, blob => window.heldBlobs.push(() => callback(blob)), ...rest)
  return toBlob.call(this, callback, ...rest) }"""
# One tap on « Partager », by the button's own click(): what the stubs saw by the time click() returned (the handler has
# run, the tap's activation not yet spent). null when there is no « Partager » to tap.
TAP = """() => { const button = [...document.querySelectorAll('.final-preview button')].find(e => e.textContent.trim() === 'Partager')
  if (!button) return null
  const shares = window.shares.length, copies = window.copies.length
  button.click()
  return { shared: window.shares.length - shares, copied: window.copies.length - copies, held: window.heldCopies.length } }"""
# The last share's data, its file decoded in the page: its keys, the file, its size in pixels, its centre pixel, its bytes.
SHARED = """async () => { const data = window.shares.at(-1), file = data.files[0], bitmap = await createImageBitmap(file)
  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height), drawing = canvas.getContext('2d')
  drawing.drawImage(bitmap, 0, 0)
  const centre = [...drawing.getImageData(bitmap.width >> 1, bitmap.height >> 1, 1, 1).data].slice(0, 3)
  const url = await new Promise(done => { const reader = new FileReader(); reader.onload = () => done(reader.result); reader.readAsDataURL(file) })
  return { keys: Object.keys(data), count: data.files.length, file: file instanceof File, type: file.type, name: file.name,
           width: bitmap.width, height: bitmap.height, centre, base64: url.split(',')[1] } }"""
RELEASED = "() => window.canvases.every(canvas => canvas.width === 0 && canvas.height === 0)"
PREPARING = "Préparation de l’image…"
CANNOT = ("Ce navigateur ne peut pas envoyer l’image à une autre application. Téléchargez-la, ou ouvrez cette page dans "
          "Chrome (Android) ou Safari (iPhone).")
UNPREPARED = "L’image à partager n’a pas pu être préparée. Téléchargez l’affiche."
FAILED = "Le partage n’a pas pu s’ouvrir. Téléchargez l’affiche, puis ajoutez-la à votre publication."
STUCK = "Le partage n’a pas répondu. Téléchargez l’affiche, ou rouvrez cette page."
TAP_NOT_COPIED = NOT_COPIED  # one sentence for a failed copy, from « Copier la légende » or from « Partager »
COPY_UNKNOWN = "La légende n’a peut-être pas été copiée. Touchez « Copier la légende » pour être sûr."
MARKER = b"marqueur-des-metadonnees-du-png"


def png_bytes(size, colour, mode="RGB", text=None):
    from io import BytesIO
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    if text:
        info.add_text("Comment", text.decode())
    out = BytesIO()
    Image.new(mode, size, colour).save(out, "PNG", pnginfo=info)
    return out.getvalue()


def png_texts(data):
    """The text and Exif chunks' payloads of a PNG."""
    found, at = [], 8
    while at + 8 <= len(data):
        size, kind = int.from_bytes(data[at:at + 4], "big"), data[at + 4:at + 8]
        if kind in (b"tEXt", b"iTXt", b"zTXt", b"eXIf"):
            found.append(data[at + 8:at + 8 + size])
        at += 12 + size
    return found


def sharing(browser, errors, data, product):
    """« Partager » (T-SHARE-004, D-SHARE-002 and 004): the JPEG made in the page from the current confirmation's preview,
    the tap (share called within the click, the file alone, the caption by the clipboard), its outcomes, the panel's
    states, the File's lifetime and the app switch. The share sheet, the clipboard and toBlob are stubbed."""
    import base64
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light", accept_downloads=True)
    context.add_init_script(SHARE_STUBS)
    page = context.new_page()
    page.set_default_timeout(15000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    panel = page.locator(".final-preview")
    field = panel.get_by_label("Légende de la publication", exact=True)
    copy = panel.get_by_role("button", name="Copier la légende", exact=True)
    share = panel.get_by_role("button", name="Partager", exact=True)
    preparing = panel.get_by_role("button", name=PREPARING, exact=True)
    download = panel.get_by_role("link", name="Télécharger le PNG")
    status, copied = panel.locator("#partage-etat"), panel.locator("#copie-legende")
    value = lambda name: page.evaluate(f"() => window.{name}")
    tap = lambda: page.evaluate(TAP)

    def home():
        smoke.go(page, "Accueil")
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()

    def open_poster(poster, ready=True, loaded=True, address=None):
        """A new opening of the poster's current confirmation, by the chat's address from Home (or `address`); `loaded`:
        until its image is shown; `ready`: until « Partager »."""
        if panel.count():
            panel.get_by_role("button", name="Fermer").click()
        home()
        page.evaluate("hash => { location.hash = hash }", address or f"message-{poster}")
        expect(panel).to_be_visible(timeout=20000)
        if loaded:
            expect(panel.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
        show_sharing(panel)
        if ready:
            expect(share).to_be_enabled()

    def shared():
        found = page.evaluate(SHARED)
        found["bytes"] = base64.b64decode(found.pop("base64"))
        return found

    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    # A file to check (an unconfirmed render): no « Partager », no sentence, nothing encoded.
    poster = made_in_chat(page, product, "Casque Bose QC noir, 450 000 Ar")
    expect(panel.locator(".shot img")).to_have_js_property("complete", True)
    for absent in (share, preparing, status):
        expect(absent).to_have_count(0)
    assert value("toBlobs") == 0
    # Confirmed in place, no reload: prepared from the image already loaded, the confirmed PNG stays the primary action.
    panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    show_sharing(panel)
    expect(share).to_be_enabled()
    expect(share).to_have_class(re.compile(r"\bsecondary\b"))
    expect(download).not_to_have_class(re.compile(r"\bsecondary\b"))
    assert value("toBlobs") == 1 and page.evaluate(RELEASED)
    address = f"{smoke.ORIGIN}/api/creations/{poster}"
    confirmation = page.request.get(address).json()["confirmation"]
    render = page.request.get(f"{smoke.ORIGIN}/api/renders/{confirmation['render_id']}").json()
    preview = f"{smoke.ORIGIN}{render['preview_url']}"
    # A second poster, confirmed, never captioned (as a poster confirmed before this feature).
    panel.get_by_role("button", name="Fermer").click()
    home()
    second = made_in_chat(page, product, "Casque Sony noir, 300 000 Ar")
    panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    show_sharing(panel)
    expect(share).to_be_enabled()
    second_confirmation = page.request.get(f"{smoke.ORIGIN}/api/creations/{second}").json()["confirmation"]

    # That poster, its field empty: the tap shares with no clipboard call and says nothing of a copy.
    expect(field).to_have_value("")
    assert tap() == {"shared": 1, "copied": 0, "held": 0}
    page.evaluate(FRAMES)
    expect(copied).to_have_text("")
    expect(status).to_have_text("")

    # The share: exactly { files: [File] }, a JPEG of the render's size named after the confirmation, the caption copied.
    open_poster(poster)
    caption = "Galaxy A15 128 Go\nLivraison à Tana 📦"
    field.fill(caption)
    assert tap() == {"shared": 1, "copied": 1, "held": 0}
    expect(copied).to_have_text(COPIED)
    expect(status).to_have_text("")
    assert value("copies")[-1] == caption
    made = shared()
    assert made["keys"] == ["files"] and made["count"] == 1 and made["file"], made["keys"]
    assert made["type"] == "image/jpeg" and made["name"] == f"affiche-{render['format']}-{confirmation['id'][:8]}.jpg", made["name"]
    assert (made["width"], made["height"]) == (render["width"], render["height"]) == (1080, 1350), (made["width"], made["height"])
    assert made["bytes"][:3] == b"\xff\xd8\xff" and b"Exif" not in made["bytes"]
    for text in png_texts(page.request.get(preview).body()):
        assert text not in made["bytes"], text

    # Timing at the button: share is called before click() returns, whether the copy is held or throws at once.
    page.evaluate("window.copyMode = 'hold'")
    assert tap() == {"shared": 1, "copied": 1, "held": 1}  # the copy started, still pending, the share already called
    expect(copied).to_have_text(COPY_UNKNOWN, timeout=6000)  # resolved share, copy pending 3 s: never a claim
    expect(panel.get_by_text(COPIED, exact=True)).to_have_count(0)
    page.evaluate("window.heldCopies.pop().ok()")
    expect(copied).to_have_text(COPIED)
    page.evaluate("window.copyMode = 'throw'")
    assert tap() == {"shared": 1, "copied": 1, "held": 0}
    expect(copied).to_have_text(TAP_NOT_COPIED)
    expect(copied).to_have_class(re.compile(r"\bwhy\b"))
    # The clipboard refusing: the same sentence, the share itself fine.
    page.evaluate("window.copyMode = 'reject'")
    tap()
    expect(copied).to_have_text(TAP_NOT_COPIED)
    expect(status).to_have_text("")

    # Cancel (AbortError): nothing at all, the copy resolved, refused, or refused after the cancel.
    page.evaluate("window.shareMode = 'AbortError'")
    for mode in ("resolve", "reject"):
        page.evaluate("mode => { window.copyMode = mode }", mode)
        tap()
        page.evaluate(FRAMES)
        expect(copied).to_have_text("")
        expect(status).to_have_text("")
    page.evaluate("window.copyMode = 'hold'")
    tap()
    page.evaluate(FRAMES)
    page.evaluate("window.heldCopies.pop().ko()")
    page.wait_for_timeout(3500)
    expect(copied).to_have_text("")
    expect(status).to_have_text("")

    # Refused (NotAllowedError): the sentence pointing to the download, with the copy's outcome; the download kept.
    page.evaluate("window.shareMode = 'NotAllowedError'; window.copyMode = 'resolve'")
    tap()
    expect(status).to_have_text(FAILED)
    expect(copied).to_have_text(COPIED)
    expect(download).to_be_visible()
    smoke.check_contrast(page, "share refused")
    page.screenshot(path=str(OUT / "share-failed-1366.png"))

    # A share that never settles locks nothing: « Partager », the download and « Copier la légende » work; after 15 s of
    # visible waiting the provisional line, withdrawn by a later cancel.
    page.evaluate("window.shareMode = 'hold'")
    tap()
    expect(status).to_have_text("")
    expect(share).to_be_enabled()
    with page.expect_download():
        download.click()
    copy.click()
    expect(copied).to_have_text(COPIED)
    expect(status).to_have_text(STUCK, timeout=20000)
    expect(share).to_be_enabled()
    page.screenshot(path=str(OUT / "share-stuck-1366.png"))
    page.evaluate("window.heldShares.pop().ko('AbortError')")
    expect(status).to_have_text("")
    # Two taps, both pending: tap two's outcome is shown; tap one's, settled after it, changes neither line.
    tap()
    tap()
    page.evaluate("window.heldShares[1].ok()")
    expect(copied).to_have_text(COPIED)
    expect(status).to_have_text("")
    page.evaluate("window.heldShares[0].ko('NotAllowedError')")
    page.evaluate(FRAMES)
    expect(copied).to_have_text(COPIED)
    expect(status).to_have_text("")
    page.evaluate("window.heldShares.length = 0; window.shareMode = 'resolve'")

    # The JPEG not ready at the tap: « Préparation de l’image… », disabled and busy, nothing shared; the download works.
    page.evaluate("window.blobMode = 'hold'")
    open_poster(poster, ready=False)
    expect(preparing).to_be_disabled()
    expect(preparing).to_have_attribute("aria-busy", "true")
    shares = value("shares.length")
    assert tap() is None
    preparing.click(force=True)
    assert value("shares.length") == shares
    with page.expect_download():
        download.click()
    until(page, lambda: value("heldBlobs.length") == 1)
    page.evaluate("window.heldBlobs.pop()()")
    expect(share).to_be_enabled()
    assert page.evaluate(RELEASED)

    # The encoder failing: no callback (the 10 s deadline), a PNG, a null blob, then a preview whose natural size is not
    # the render's (nothing encoded): « Partager » withdrawn, the sentence, the download the main button again.
    for mode in ("never", "png", "null"):
        page.evaluate("mode => { window.blobMode = mode }", mode)
        open_poster(poster, ready=False)
        expect(status).to_have_text(UNPREPARED, timeout=15000)
        expect(share).to_have_count(0)
        expect(preparing).to_have_count(0)
        expect(download).not_to_have_class(re.compile(r"\bsecondary\b"))
        assert page.evaluate(RELEASED), mode
    page.evaluate("window.blobMode = 'real'")
    page.route(preview, lambda route: route.fulfill(status=200, content_type="image/png", body=png_bytes((540, 675), "white")))
    before = value("toBlobs")
    open_poster(poster, ready=False)
    expect(status).to_have_text(UNPREPARED)
    assert value("toBlobs") == before
    page.screenshot(path=str(OUT / "share-unprepared-1366.png"))
    page.unroute(preview)
    # The PNG request failing: the page's error line, and the same sentence.
    page.route(preview, lambda route: route.abort())
    open_poster(poster, ready=False, loaded=False)
    expect(status).to_have_text(UNPREPARED)
    expect(page.locator(".message.error")).to_contain_text("Le fichier d’aperçu ne peut pas être chargé.")
    page.unroute(preview)
    # The PNG request held past the deadline: the whole visible preparation lasts 10 s at most, and the image arriving
    # later brings nothing back.
    pngs = []
    page.route(preview, lambda route: pngs.append(route))
    before = value("toBlobs")
    open_poster(poster, ready=False, loaded=False)
    until(page, lambda: pngs)
    expect(preparing).to_be_disabled()
    expect(status).to_have_text(UNPREPARED, timeout=13000)
    expect(download).not_to_have_class(re.compile(r"\bsecondary\b"))
    pngs.pop().continue_()
    expect(panel.get_by_role("heading", name=READY)).to_be_visible()
    page.evaluate(FRAMES)
    expect(status).to_have_text(UNPREPARED)
    expect(share).to_have_count(0)
    assert value("toBlobs") == before
    page.unroute(preview)
    panel.get_by_role("button", name="Fermer").click()
    if page.locator(".message.error").count():
        page.locator(".message.error").get_by_role("button", name="Fermer").click()
    # A transparent preview (with a text chunk): the JPEG's pixels are the poster's ground, never black, and the PNG's
    # metadata is not carried.
    page.route(preview, lambda route: route.fulfill(status=200, content_type="image/png",
               body=png_bytes((1080, 1350), (0, 0, 0, 0), "RGBA", MARKER)))
    open_poster(poster)
    expect(share).to_be_enabled()
    tap()
    made = shared()
    assert all(abs(a - b) <= 6 for a, b in zip(made["centre"], (0x17, 0x32, 0x4D))), made["centre"]
    assert MARKER not in made["bytes"]
    page.unroute(preview)

    # Lifetime: a slow encoding of one opening never becomes another opening's File. A → B, then A closed and reopened.
    # A's and B's previews are two plain colours, so the shared JPEG's pixels say whose they are. While two encodings
    # are held, no canvas keeps its full-size backing store.
    a_colour, b_colour = (200, 40, 40), (40, 60, 200)
    second_preview = f"{smoke.ORIGIN}/api/renders/{second_confirmation['render_id']}/preview"
    def plain(colour):
        body = png_bytes((1080, 1350), colour)
        return lambda route: route.fulfill(status=200, content_type="image/png", body=body)
    for url, colour in ((preview, a_colour), (second_preview, b_colour)):
        page.route(url, plain(colour))
    near = lambda found, colour: all(abs(a - b) <= 6 for a, b in zip(found, colour))
    page.evaluate("window.blobMode = 'hold'")
    open_poster(poster, ready=False)
    until(page, lambda: value("heldBlobs.length") == 1)
    open_poster(second, ready=False)
    until(page, lambda: value("heldBlobs.length") == 2)
    assert page.evaluate("() => window.canvases.filter(canvas => canvas.width || canvas.height).length") == 0
    page.evaluate("window.heldBlobs.shift()()")  # A's, late
    page.evaluate(FRAMES)
    expect(preparing).to_be_visible()
    page.evaluate("window.heldBlobs.shift()()")
    expect(share).to_be_enabled()
    tap()
    made = shared()
    assert made["name"] == f"affiche-{render['format']}-{second_confirmation['id'][:8]}.jpg" and near(made["centre"], b_colour), made["centre"]
    open_poster(poster, ready=False)
    open_poster(poster, ready=False)
    until(page, lambda: value("heldBlobs.length") == 2)
    assert page.evaluate("() => window.canvases.filter(canvas => canvas.width || canvas.height).length") == 0
    page.evaluate("window.heldBlobs.shift()()")  # the closed opening's
    page.evaluate(FRAMES)
    expect(preparing).to_be_visible()
    page.evaluate("window.heldBlobs.shift()()")
    expect(share).to_be_enabled()
    tap()
    made = shared()
    assert made["name"] == f"affiche-{render['format']}-{confirmation['id'][:8]}.jpg" and near(made["centre"], a_colour), made["centre"]
    page.evaluate("window.blobMode = 'real'")
    assert page.evaluate(RELEASED)
    page.unroute(preview)
    page.unroute(second_preview)

    # The tap checks the panel is still the current confirmation: an edit of the price, then the click in the same task,
    # before the page has redrawn (the button still there, still enabled), shares nothing. Then, reopened, the file is an
    # earlier version, with no « Partager » and nothing encoded.
    open_poster(second, address=second)
    edited = page.evaluate("""price => {
      const button = [...document.querySelectorAll('.final-preview button')].find(e => e.textContent.trim() === 'Partager')
      const field = document.getElementById('champ-prix')
      if (!button || !field) return null
      const before = window.shares.length
      field.value = price; field.dispatchEvent(new Event('input', { bubbles: true }))
      button.click()
      return { shared: window.shares.length - before, drawn: button.isConnected && !button.disabled } }""", "310 000")
    assert edited == {"shared": 0, "drawn": True}, edited
    expect(panel.get_by_role("heading", name=EARLIER)).to_be_visible()
    expect(page.get_by_text("Enregistré", exact=True)).to_be_visible()
    panel.get_by_role("button", name="Fermer").click()
    home()
    encoded = value("toBlobs")
    page.evaluate("hash => { location.hash = hash }", f"message-{second}")
    earlier(panel, second_confirmation)
    expect(panel.locator(".shot img")).to_have_js_property("complete", True)
    page.evaluate(FRAMES)
    assert value("toBlobs") == encoded

    # Not gated: no credit left and the conditions not accepted; the tap sends nothing to the server.
    engine = smoke.make_engine(Path(data))
    with smoke.write_tx(engine) as conn:
        left = smoke.credits.balance(conn, 1)["available"]
        if left:
            smoke.credits.correct(conn, 1, -left, ref="share-test", note="zero for the share test", actor="tests")
        conn.exec_driver_sql("UPDATE shop_profile SET terms_version=NULL, terms_accepted_at=NULL WHERE id=1")
    open_poster(poster)
    expect(share).to_be_enabled()
    sent = []
    page.on("request", lambda r: sent.append(r.url) if "/api/" in r.url and r.method != "GET" else None)
    assert tap()["shared"] == 1
    page.evaluate(FRAMES)
    expect(status).to_have_text("")
    expect(page.locator(".terms-sheet")).to_have_count(0)
    assert sent == [], sent
    with smoke.write_tx(engine) as conn:
        smoke.accepted(conn, 1)
    engine.dispose()

    # A phone, 360 × 640, both themes; the keyboard: field, « Copier la légende », then « Partager », which Enter shares.
    page.set_viewport_size({"width": 360, "height": 640})
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        share.scroll_into_view_if_needed()
        smoke.check_contrast(page, f"share, 360 px, {scheme}")
        assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), "the page scrolls sideways"
        assert panel.evaluate("e => e.scrollWidth <= e.clientWidth"), "the panel scrolls sideways"
        page.screenshot(path=str(OUT / f"share-360-{scheme}.png"))
    # With Facebook disabled the confirmed PNG takes the primary action.
    smoke.check_primary(page, "share, 360 px", download, share)
    page.emulate_media(color_scheme="light")
    expect(field).to_have_value(caption)
    field.focus()
    page.keyboard.press("Tab")
    expect(copy).to_be_focused()
    page.keyboard.press("Tab")
    expect(share).to_be_focused()
    shares = value("shares.length")
    page.keyboard.press("Enter")
    until(page, lambda: value("shares.length") == shares + 1)
    expect(copied).to_have_text(COPIED)
    page.set_viewport_size({"width": 1366, "height": 768})

    # A browser that cannot share files: no « Partager », the sentence, the download the main button, nothing encoded.
    other = context.new_page()
    other.on("pageerror", lambda error: errors.append(str(error)))
    other.add_init_script("window.noFiles = true")
    other.goto(f"{smoke.ORIGIN}/#message-{poster}")
    other_panel = other.locator(".final-preview")
    expect(other_panel.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(other_panel)
    expect(other_panel.locator("#partage-etat")).to_have_text(CANNOT)
    expect(other_panel.get_by_role("button", name="Partager", exact=True)).to_have_count(0)
    expect(other_panel.get_by_role("button", name=PREPARING, exact=True)).to_have_count(0)
    expect(other_panel.get_by_role("link", name="Télécharger le PNG")).not_to_have_class(re.compile(r"\bsecondary\b"))
    assert other.evaluate("() => window.toBlobs") == 0
    smoke.check_contrast(other, "cannot share")
    smoke.check_primary(other, "cannot share", other_panel.get_by_role("link", name="Télécharger le PNG"))  # the main action there
    other.screenshot(path=str(OUT / "share-cannot-1366.png"))
    other.close()

    # An app switch while the sheet is open: the page hidden (its visibilitychange), the session check held; the share
    # refused meanwhile. Answered for the same shop: the outcome is shown and the File prepared again.
    page.evaluate("window.shareMode = 'hold'")
    open_poster(poster)
    expect(share).to_be_enabled()
    tap()
    sessions = []
    page.route(f"{smoke.ORIGIN}/api/session", lambda route: sessions.append(route) if route.request.method == "GET" else route.continue_())
    encoded = value("toBlobs")
    page.evaluate(smoke.VISIBILITY, True)
    page.evaluate(smoke.VISIBILITY, False)
    until(page, lambda: sessions)
    expect(panel).to_be_hidden()
    page.evaluate("window.heldShares.pop().ko('NotAllowedError')")
    page.evaluate(FRAMES)
    sessions.pop().continue_()
    page.unroute(f"{smoke.ORIGIN}/api/session")
    expect(status).to_have_text(FAILED)
    expect(share).to_be_enabled()
    assert value("toBlobs") == encoded + 1
    # Another shop signs in from another tab of this browser and opens its own confirmed panel while this tab's share is
    # still pending: this tab is signed out by the identity change, and its late answer reaches neither panel. (Its poster
    # is made and confirmed beforehand on another device: this tab holds the browser's chat.)
    engine = smoke.make_engine(Path(data))
    password_c = os.urandom(12).hex()
    with smoke.write_tx(engine) as conn:
        shop_c = smoke.shops.create_shop(conn, "boutiquetrois", "Boutique Trois", smoke.PASSWORDS.hash(password_c))
        smoke.credits.grant(conn, shop_c, 20, origin="offered", ref="tests", actor="tests")
        smoke.accepted(conn, shop_c)
    engine.dispose()
    device = browser.new_context(viewport={"width": 1366, "height": 768})
    elsewhere_page = device.new_page()
    elsewhere_page.set_default_timeout(15000)
    open_atelier(elsewhere_page)
    sign_in(elsewhere_page, "boutiquetrois", password_c)
    their_poster = made_in_chat(elsewhere_page, product, "Casque JBL noir, 200 000 Ar")
    elsewhere_page.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True).click()
    expect(elsewhere_page.get_by_role("heading", name=READY)).to_be_visible()
    device.close()
    tap()
    context.clear_cookies()
    theirs = context.new_page()
    theirs.set_default_timeout(15000)
    theirs.on("pageerror", lambda error: errors.append(str(error)))
    open_atelier(theirs)
    sign_in(theirs, "boutiquetrois", password_c)
    expect(page.get_by_label("Mot de passe", exact=True)).to_be_visible()  # this tab: signed out
    theirs.evaluate("hash => { location.hash = hash }", their_poster)
    their_panel = theirs.locator(".final-preview")
    expect(their_panel.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    show_sharing(their_panel)
    expect(their_panel.get_by_role("button", name="Partager", exact=True)).to_be_enabled()
    page.evaluate("window.heldShares.pop().ko('NotAllowedError')")
    page.evaluate(FRAMES)
    theirs.evaluate(FRAMES)
    assert page.evaluate("() => document.querySelector('#partage-etat')?.textContent ?? ''") == ""
    assert page.evaluate(TAP) is None
    expect(their_panel.locator("#partage-etat")).to_have_text("")
    page.close()
    # « Se déconnecter » with the panel open and its encoding held (a key's removal refused, so that the page stays):
    # the shop's part leaves the page, and the late encoding prepares nothing.
    theirs.evaluate("window.blobMode = 'hold'")
    their_panel.get_by_role("button", name="Fermer").click()
    smoke.go(theirs, "Accueil")
    expect(theirs.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
    theirs.evaluate("hash => { location.hash = hash }", their_poster)
    expect(their_panel.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)
    until(theirs, lambda: theirs.evaluate("() => window.heldBlobs.length") == 1)
    theirs.evaluate("key => localStorage.setItem(key, '{}')", f"affiche.shop{shop_c}.style")
    theirs.evaluate(smoke.REFUSE_REMOVAL, rf"^affiche\.shop{shop_c}\.style$")
    theirs.locator(".sign-out").first.evaluate("e => e.click()")  # behind the panel
    expect(theirs.locator("main.gate").get_by_text(smoke.LEFT_BEHIND)).to_be_visible()
    expect(theirs.locator("main:not(.gate)")).to_have_count(0)
    theirs.evaluate("window.heldBlobs.pop()()")
    theirs.evaluate(FRAMES)
    assert theirs.evaluate(RELEASED) and theirs.evaluate(TAP) is None
    context.close()


def publishing(browser, errors, data, product):
    """« Publier sur ma Page » (D-FB-POST-005, ADR-129) on the stand-in: from a confirmed poster's final panel it opens the
    page for that poster alone (`#publier-<id>`), whose description is the caption of « Partager »; published there, the
    panel lists the post with Facebook's link. An unknown post (the stand-in's marker) offers « Répondre », which leads to
    « Publier », where the owner says. A poster confirmed in another format is told so, without the button; an earlier
    version keeps its posts, without the button. The panel reads its posts at each opening, never by a timer."""
    context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(15000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda r: print(f"HTTP {r.status} {r.request.method} {r.url}", flush=True) if r.status >= 400 and "/api/" in r.url else None)
    sent = []  # every post request that leaves the browser, with its body
    page.on("request", lambda r: sent.append(r.post_data_json) if r.method == "POST" and r.url.endswith("/api/facebook/posts") else None)
    panel, button = page.locator(".final-preview"), page.locator(".final-preview").get_by_role("button", name=PUBLISH)
    lines = panel.locator(".publications li")
    heading = page.get_by_role("heading", name="Publier sur Facebook", exact=True)
    mine = page.get_by_role("region", name="Votre publication", exact=True)
    field = mine.get_by_label("Description de la publication")
    posts = page.get_by_role("region", name="Publications", exact=True).locator("ol.posts > li")
    sheet = page.get_by_role("dialog", name=re.compile("^Publier sur "))
    confirm = sheet.get_by_role("button", name=re.compile(r"^Publier( à nouveau)?$"))  # « à nouveau » once it is on the Page
    other = "Pour publier sur votre Page, vérifiez cette affiche au format Publication."
    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    poster = made_in_chat(page, product, "Casque Bose QC noir, 450 000 Ar")
    page.set_viewport_size({"width": 360, "height": 640})
    preview_url = panel.locator(".shot img").evaluate("img => img.src")
    panel.get_by_role("button", name="Confirmer et préparer la publication", exact=True).click()
    page.wait_for_url(f"**/#publier-{poster}")
    expect(heading).to_be_visible()
    assert not sent, "preparing the confirmed file must not publish"
    address = f"{smoke.ORIGIN}/api/creations/{poster}"
    title = page.request.get(address).json()["document"]["offer"]["title"]

    def reopen():
        """A new opening of the poster's file, from Accueil."""
        page.evaluate("() => { location.hash = 'accueil' }")
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        expect(panel).to_have_count(0)
        page.evaluate("hash => { location.hash = hash }", poster)
        expect(page.get_by_role("heading", name=READY)).to_be_visible(timeout=20000)

    def alone():
        """The final panel's button: the page for this poster alone, its caption as the description."""
        button.click()
        page.wait_for_url(re.compile(rf"#publier-{poster}$"))
        expect(heading).to_be_visible()

    confirmed = page.request.get(address).json()["confirmation"]
    assert preview_url.endswith(f"/api/renders/{confirmed['render_id']}/preview")
    reopen()
    # Reopening the confirmed file on a small phone keeps focus in the panel with both output actions in view.
    expect(panel.get_by_role("heading", name=READY)).to_be_visible()
    page.wait_for_function("document.querySelector('.final-preview')?.contains(document.activeElement)")
    download = panel.get_by_role("link", name="Télécharger le PNG", exact=True)
    expect(button).to_be_in_viewport()
    expect(download).to_be_in_viewport()
    shot = panel.locator(".shot img")
    for control in (button, download):
        box = control.bounding_box()
        assert box["y"] + box["height"] <= shot.bounding_box()["y"], (box, shot.bounding_box())
    expect(panel.get_by_role("button", name="Copier la légende")).to_have_count(0)
    expect(panel.locator('details[open]')).to_have_count(0)
    page.screenshot(path=str(OUT / "ready-actions-360.png"))
    with page.expect_download() as received:
        download.click()
    png = received.value.path().read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and png == page.request.get(shot.evaluate("el => el.src")).body()
    assert not sent
    page.set_viewport_size({"width": 1366, "height": 768})

    # No post yet, and no sheet of the panel's own: the button opens the page for this poster, which says that no Page is
    # connected and connects one itself (D-KIT-008): the stand-in's dialog, « Connecter cette Page » in « Mon compte »,
    # then back on the same post by itself, its caption as the description, nothing sent.
    expect(lines).to_have_count(0)
    expect(panel.get_by_text(other)).to_have_count(0)
    show_sharing(panel)
    panel.get_by_label("Légende de la publication").fill("Casque Bose QC, 450 000 Ar")
    alone()
    expect(page.get_by_text("Aucune Page Facebook n’est connectée.", exact=True)).to_be_visible()
    page.locator(".shop-publish").get_by_role("button", name="Connecter ma Page Facebook").click()
    page.wait_for_url(smoke.ORIGIN + "/#compte")
    card = page.get_by_role("region", name="Page Facebook", exact=True)
    card.get_by_role("radio", name="Page d’essai 1").check()
    card.get_by_role("button", name="Connecter cette Page").click()
    page.wait_for_url(f"**/#publier-{poster}")
    expect(field).to_have_value("Casque Bose QC, 450 000 Ar")
    assert not sent

    # Published from the page for this poster: that poster alone, the caption its field shows (this device refuses to
    # keep the edit: storage still holds the earlier text); then on the panel, its line and its link.
    reopen()
    expect(lines).to_have_count(0)
    key = f"affiche.shop1.caption.{poster}"
    page.evaluate("""key => { const real = Storage.prototype.setItem; window.realSetItem = real
      Storage.prototype.setItem = function (name, value) {
        if (name === key) throw new DOMException('Plein pour l’essai.', 'QuotaExceededError')
        return real.call(this, name, value) } }""", key)
    typed = "Casque Bose QC, prix 450 000 Ar"
    show_sharing(panel)
    panel.get_by_label("Légende de la publication").fill(typed)
    assert page.evaluate("key => localStorage.getItem(key)", key) == "Casque Bose QC, 450 000 Ar"
    alone()
    expect(field).to_have_value(typed)
    # Another tab takes the page, then this one takes it back: the caption it was handed stays (storage is behind it).
    elsewhere_line = "La page Publier est ouverte dans un autre onglet."
    other_tab = context.new_page()
    other_tab.on("pageerror", lambda error: errors.append(str(error)))
    open_atelier(other_tab, "/#publier")
    other_tab.get_by_role("button", name="Continuer ici").click()
    expect(page.get_by_text(elsewhere_line, exact=True)).to_be_visible()
    page.get_by_role("button", name="Continuer ici").click()
    expect(field).to_have_value(typed)
    other_tab.close()
    page.evaluate("() => { Storage.prototype.setItem = window.realSetItem }")
    expect(mine.get_by_role("figure")).to_contain_text(title)
    mine.get_by_role("button", name="Publier…", exact=True).click()
    expect(sheet.locator(".sent-text")).to_have_text(typed)
    confirm.click()
    expect(posts.first).to_contain_text("Publié sur Page d’essai 1.", timeout=20000)
    confirmation = page.request.get(address).json()["confirmation"]["id"]
    assert sent == [{"page_id": "100000000000001", "description": typed,
                     "items": [{"creation_id": poster, "confirmation_id": confirmation, "seen": None}]}], sent
    reopen()
    panel.locator("summary", has_text="Autres actions").click()
    expect(lines).to_have_count(1)
    expect(lines.first).to_contain_text("Publié sur Page d’essai 1.")
    expect(lines.first.locator("small")).to_contain_text("Page d’essai 1 · seule")
    expect(lines.first.get_by_role("link", name="Voir la publication")).to_have_attribute("href", re.compile(r"^https://www\.facebook\.com/100000000000001_\d+$"))
    expect(lines.first.get_by_role("link", name="Voir la publication")).to_have_attribute("target", "_blank")
    expect(lines.first.get_by_role("link", name="Répondre")).to_have_count(0)
    page.screenshot(path=str(OUT / "publish-lines-1366.png"))

    # Facebook's answer lost (the stand-in's marker in the description): the panel offers « Répondre », which leads to
    # « Publier », where the owner says it is on his Page; the panel then says so, with no link to a post.
    alone()
    field.fill("Casque Bose [stub:unknown]")
    mine.get_by_role("button", name="Publier…", exact=True).click()
    confirm.click()
    expect(posts.first).to_contain_text(MESSAGES["post_unknown"], timeout=20000)
    reopen()
    expect(lines).to_have_count(2)
    expect(lines.first).to_contain_text(MESSAGES["post_unknown"])
    expect(lines.first.get_by_role("link", name="Voir la publication")).to_have_count(0)
    smoke.check_contrast(page, "publications")
    lines.first.get_by_role("link", name="Répondre").click()
    page.wait_for_url(re.compile(r"#publier$"))
    posts.first.get_by_role("button", name="Elle est sur ma Page").click()
    expect(posts.first).to_contain_text("Présence confirmée par vous")
    reopen()
    panel.locator("summary", has_text="Autres actions").click()
    expect(lines.first).to_contain_text("Présence confirmée par vous")
    expect(lines.first.get_by_role("link")).to_have_count(0)  # the owner's word gives the Page, not a post
    expect(lines.last.get_by_role("link", name="Voir la publication")).to_be_visible()
    page.set_viewport_size({"width": 360, "height": 640})
    reopen()  # read again at each opening, never by a timer
    expect(lines).to_have_count(2)
    assert panel.evaluate("el => el.scrollWidth <= el.clientWidth"), "the panel scrolls sideways at 360 px"
    panel.locator("summary", has_text="Autres actions").click()
    lines.last.scroll_into_view_if_needed()
    page.screenshot(path=str(OUT / "publish-lines-360.png"))
    page.set_viewport_size({"width": 1366, "height": 768})

    # Confirmed in another format only (written in the database: the confirmation and its render made Carré): the panel
    # says why, without the button; its posts stay.
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        store.execute("UPDATE poster_renders SET format='square' WHERE id=(SELECT render_id FROM confirmations WHERE id=?)",
                      (confirmation,))
        store.execute("UPDATE confirmations SET format='square' WHERE id=?", (confirmation,))
    reopen()
    expect(panel.get_by_text(other, exact=True)).to_be_visible()
    expect(button).to_have_count(0)
    expect(lines).to_have_count(2)
    page.screenshot(path=str(OUT / "publish-other-format-1366.png"))
    # An earlier version now: its posts stay with the poster; neither the button nor the sentence.
    now = page.request.get(address).json()
    saved = page.request.put(address, data=now["document"] | {"offer": now["document"]["offer"] | {"price_ar": 460000}},
        headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(BUNDLE), "If-Match": f'"{now["revision"]}"', "Idempotency-Key": str(uuid4())})
    assert saved.ok, saved.text()
    page.evaluate("() => { location.hash = 'accueil' }")
    expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
    page.evaluate("hash => { location.hash = hash }", poster)
    expect(page.get_by_role("heading", name=EARLIER)).to_be_visible(timeout=20000)
    expect(lines).to_have_count(2)
    expect(button).to_have_count(0)
    expect(panel.get_by_text(other)).to_have_count(0)
    # Every post keeps its line: twenty more (written in the database), a page of twenty, then « Voir plus ».
    with sqlite3.connect(Path(data) / "affiche.db", timeout=10) as store:
        for n in range(20):
            id = str(uuid4())
            store.execute("INSERT INTO facebook_posts (id,shop_id,page_id,page_name,description,key,payload_sha,status,sent_at,"
                          "settled_at,post_id,link) VALUES (?,1,'100000000000001','Page d’essai 1','',?,'s','published',?,?,?,?)",
                          (id, str(uuid4()), utc_now(), utc_now(), f"100000000000001_{n + 1}",
                           f"https://www.facebook.com/100000000000001_{n + 1}"))
            store.execute("INSERT INTO facebook_post_items (post_id,position,creation_id,confirmation_id) VALUES (?,0,?,?)",
                          (id, poster, confirmation))
    page.evaluate("() => { location.hash = 'accueil' }")
    expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
    page.evaluate("hash => { location.hash = hash }", poster)
    expect(page.get_by_role("heading", name=EARLIER)).to_be_visible(timeout=20000)
    expect(lines).to_have_count(20)
    panel.locator("summary", has_text="Autres actions").click()
    panel.get_by_role("button", name="Voir plus").click()
    expect(lines).to_have_count(22)
    expect(lines.last).to_contain_text("Publié sur Page d’essai 1.")  # the first post, oldest, last
    expect(panel.get_by_role("button", name="Voir plus")).to_have_count(0)
    # Kept on the device: the caption, « Partager »'s own key, and no record of a post.
    stored = page.evaluate("() => [{...localStorage}, {...sessionStorage}]")
    assert stored[0][f"affiche.shop1.caption.{poster}"] == "Casque Bose [stub:unknown]", stored
    kept = json.dumps([{key: value for key, value in part.items() if ".caption." not in key and not key.endswith(".post-draft")}
                       for part in stored])
    assert not re.search(r"stub:|post_id|100000000000001", kept, re.I), kept
    context.close()


def current(panel, confirmation):
    """The panel holds that confirmation's own render, ready: the heading, its image, its download, no checklist."""
    expect(panel.get_by_role("heading", name=READY)).to_be_visible()
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{confirmation['render_id']}/preview")
    expect(panel.get_by_role("link", name="Télécharger le PNG")).to_have_attribute("href", confirmation["download_url"])
    expect(panel.get_by_role("button", name="Confirmer et télécharger le PNG", exact=True)).to_have_count(0)


def earlier(panel, confirmation):
    """An earlier confirmed version: labelled, no live price, no « Partager », the download kept, the check offered."""
    expect(panel.get_by_role("heading", name=EARLIER)).to_be_visible()
    expect(panel.locator(".lede")).to_have_text(EARLIER_LEDE)
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{confirmation['render_id']}/preview")
    expect(panel.locator(".facts")).not_to_contain_text("Prix")
    expect(panel).not_to_contain_text(re.compile(r"\d{3}\s000"))  # neither the live price nor the confirmed one
    expect(panel.locator(".done")).to_have_count(0)
    expect(panel.get_by_role("button", name="Partager")).to_have_count(0)
    expect(panel.get_by_role("button", name="Préparation de l’image…")).to_have_count(0)
    expect(panel.locator("#partage-etat")).to_have_count(0)
    expect(panel.get_by_role("link", name="Télécharger le PNG")).to_have_attribute("href", confirmation["download_url"])
    expect(panel.get_by_role("button", name="Vérifier l’aperçu final")).to_be_visible()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    assert (smoke.ROOT / "frontend/dist/index.html").is_file(), "build first: corepack npm@10 run build"
    product = OUT / "product.png"
    photo = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(photo).rounded_rectangle((250, 160, 750, 840), 50, fill="#202020")
    photo.save(product)
    errors = []
    with (tempfile.TemporaryDirectory(prefix="affiche-share-") as data,
          tempfile.TemporaryDirectory(prefix="affiche-publish-") as facebook_data):
        server = smoke.serve(data)
        with (OUT / "preview.log").open("w") as log:
            vite = subprocess.Popen(["node", str(smoke.ROOT / "frontend/node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1",
                                     "--port", str(smoke.WEB_PORT), "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        walk(browser, errors, data, product)
                        captions(browser, errors, data, product)
                        sharing(browser, errors, data, product)
                        # « Publier sur ma Page » exists only with the feature on: a server of its own, on the stand-in.
                        smoke.stop(*server)
                        server = smoke.serve(Path(facebook_data), facebook_provider="stub")
                        publishing(browser, errors, facebook_data, product)
                        assert not errors, errors
                    finally:
                        browser.close()
                (OUT / "results.json").write_text(json.dumps({"errors": errors, "viewports": [1366, 360]}, indent=2))
            finally:
                vite.terminate()
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill()
                    vite.wait(timeout=10)
                smoke.stop(*server)
    print("Share browser checks passed (stub only): the chat's « Télécharger ou partager » renders only while nothing is "
          "current and otherwise opens the current confirmation; a price saved after the confirmation opens it as an earlier "
          "version from Home, the editor and the chat (no live price, no « Partager », its download, the check offered, which "
          "prepares the current version); a newer unconfirmed render never replaces the confirmation's own; a failed poster "
          "read or render read says so with « Réessayer », never a render; a Home row's failed read retried; another tab's "
          "save at another price reloads the poster and opens or asks for nothing; the latest render's read failing, or "
          "answering after a save, changes nothing. The caption: kept per shop and poster on this device (2 000 emoji "
          "through an edit and a reload; 2 001, or a control character, refused with the text kept and the stored value "
          "intact); « Copier la légende » copies the typed value and says « copiée » only on success; a refused read, "
          "write or removal says so and keeps the typed text; an idle tab never writes and nothing is pruned; another "
          "shop reads and writes only its own keys; « Se déconnecter » erases that shop's captions; 360 px, both themes, "
          "keyboard. « Partager »: share called within the click, the copy held or throwing; exactly { files: [File] }, a "
          "JPEG of the render's size, the ground under transparency, no PNG metadata; cancel silent; refused, clipboard "
          "refused, a share never settling (nothing locked, then the line, withdrawn by a cancel); not ready, the encoder "
          "failing (deadline, PNG, null, size), cannot share; prepared on confirmation in place; a late encoding never "
          "another opening's; an earlier version never offers it; not gated; the app switch keeps the outcome for the same "
          "shop and drops it for another; 360 px, both themes, keyboard. « Publier sur ma Page » (stand-in; none with the "
          "feature off): opens the page for this poster alone, which connects a Page itself and comes back to the same post; published "
          "there with the caption the field shows (its storage write refused), the panel lists the post (« seule ») with Facebook's link; an unknown one offers "
          "« Répondre », which leads to « Publier » where the owner says; confirmed in another format, the sentence and no "
          "button; an earlier version keeps its posts, without the button, twenty a page with « Voir plus »; 360 px; no record "
          "of a post kept.")


if __name__ == "__main__":
    run()
