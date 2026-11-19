"""« Partager » in real Chromium (T-SHARE-002, D-SHARE-001): every way of opening a confirmed poster opens its current
confirmation and that confirmation's own render; an older confirmed file is an earlier version, without the live price. The
production build (vite preview, so build first) and the API on temporary stub data, no real env file, zero spend. Run from
backend: uv run python ../frontend/tests/share_browser.py (ports 8000 and 5173 must be free). Pictures: outputs/share-browser/.
A newer unconfirmed render is written straight into the temporary database, as the smokes do."""
import json
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
REVIEW, FINAL, READY = "Vérifier la fidélité du produit", "Dernière vérification avant le téléchargement", "Votre affiche est prête"
EARLIER = "Version confirmée précédente"
EARLIER_LEDE = "Ce fichier a été confirmé avant vos dernières modifications. Vérifiez la version actuelle pour la partager."
DRAFT, DRAFT_LEDE = "Aperçu d’une version précédente", "Ce fichier a été préparé avant vos dernières modifications. Vérifiez la version actuelle."
OPEN_FAILED = "L’affiche confirmée n’a pas pu être ouverte."
CHANGED = "Cette affiche a été modifiée ailleurs : la version enregistrée a été rechargée. Réessayez."
BUTTON = "Télécharger ou partager"


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
    page.get_by_label("Identifiant de la boutique", exact=True).fill(smoke.IDENTIFIER)
    page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
    page.get_by_role("button", name="Ouvrir l’atelier").click()
    expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()

    # A poster made in the chat at 450 000 Ar: its card's button reads « Télécharger ou partager »; with nothing confirmed it
    # asks for a render to check, then the check confirms it.
    page.get_by_role("link", name="Créer une affiche").click()
    thread = page.get_by_role("log")
    page.locator(".composer input[type=file]").set_input_files([product])
    expect(page.locator(".tray .pic")).to_have_count(1)
    expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
    page.get_by_label("Votre message").fill("Casque Bose QC noir, 450 000 Ar")
    page.get_by_role("button", name="Envoyer").click()
    thread.get_by_role("button", name="Créer l’affiche").click()
    page.wait_for_url(re.compile(r"#message-[a-f0-9-]{36}$"))
    poster = page.url.split("#message-")[1]
    address = f"{smoke.ORIGIN}/api/creations/{poster}"
    page.get_by_role("button", name="Vérifier", exact=True).click(timeout=30000)
    expect(page.get_by_role("heading", name=REVIEW)).to_be_visible()
    page.get_by_role("button", name="Tout est conforme, approuver").click()
    expect(page.get_by_role("heading", name=REVIEW)).to_have_count(0)
    expect(download).to_have_count(1)
    expect(page.get_by_role("button", name="Télécharger", exact=True)).to_have_count(0)
    download.click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    assert len(renders) == 1, renders  # nothing current yet: a file to check
    page.get_by_role("button", name="Tout est conforme, confirmer").click()
    expect(page.get_by_role("heading", name=READY)).to_be_visible()
    first = page.request.get(address).json()["confirmation"]
    assert first and first["format"] == "feed", first
    panel.get_by_role("button", name="Fermer").click()
    # Now current: the button opens that confirmation, with no render request.
    download.click()
    current(panel, first)
    assert len(renders) == 1, renders
    panel.get_by_role("button", name="Fermer").click()

    def home():
        page.get_by_role("navigation", name="Navigation").get_by_role("link", name="Accueil").click()
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
    save_price(460000)
    for way in ("home", "editor", "chat"):
        opened(way)
        earlier(panel, first)
        assert len(renders) == 1, (way, renders)
        smoke.check_contrast(page, f"earlier version from {way}")
        page.screenshot(path=str(OUT / f"earlier-{way}-1366.png"))
        panel.get_by_role("button", name="Fermer").click()
    # Nothing is current: the chat's button asks for a render. The image draws the old price, so the server refuses it.
    download.click()
    expect(error_line).to_contain_text(MESSAGES["price_stale"])
    assert len(renders) == 2, renders
    expect(panel).to_have_count(0)
    error_line.get_by_role("button", name="Fermer").click()

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
    expect(panel.get_by_role("button", name="Tout est conforme, confirmer")).to_be_disabled()
    pngs.pop().continue_()
    page.unroute(png)
    expect(panel.locator(".facts")).to_contain_text(re.compile(r"Prix affiché\s*450\s000 Ar"))
    assert len(renders) == 3, renders
    page.get_by_role("button", name="Tout est conforme, confirmer").click()
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
    assert len(renders) == 3, renders

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
    assert len(renders) == 3, renders

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
    assert len(renders) == 3, renders
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
    page.route(f"{address}/renders", lambda route: route.fulfill(status=202, content_type="application/json",
               body=json.dumps({"job_id": square_job, "status_url": f"/api/jobs/{square_job}"})))
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
    current(panel, confirmed)
    page.unroute(f"{address}/renders")
    assert len(renders) == 4, renders  # answered by the page with the square file's job
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
    assert len(renders) == 4, renders
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
    assert len(renders) == 4, renders
    download.click()
    expect(error_line).to_contain_text(MESSAGES["price_stale"])  # the image draws 450 000 Ar
    assert len(renders) == 5 and renders[-1][1] == f'"{newest}"', renders

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
    assert len(renders) == 5, renders

    # A render prepared and never confirmed, then another price saved: reopened, it is an earlier version, without the live
    # price, the checklist or a download, and the check is offered.
    save_price(450000)
    opened("chat")
    panel.get_by_role("button", name="Fermer").click()
    download.click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    assert len(renders) == 6, renders
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
        expect(panel.get_by_role("button", name="Tout est conforme, confirmer")).to_have_count(0)
        expect(panel.get_by_role("link", name="Télécharger le PNG confirmé")).to_have_count(0)
        expect(panel.get_by_role("button", name="Vérifier l’aperçu final")).to_be_visible()
        page.screenshot(path=str(OUT / f"earlier-draft-{way}-1366.png"))
        panel.get_by_role("button", name="Fermer").click()
    assert len(renders) == 6, renders

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
    assert len(renders) == 6, renders

    # A's confirmation answered after a render job B ended and replaced A in the panel: the answer belongs to A alone, and B
    # keeps its checklist, without a download. (Nothing named: two saves away and back. B is a second render of this
    # revision written in the database, presented as running until released.)
    save_price(460000)
    save_price(450000)
    opened("editor")  # the undone file, an earlier version now
    panel.get_by_role("button", name="Fermer").click()
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
    expect(page.get_by_role("heading", name=FINAL)).to_be_visible(timeout=30000)
    assert len(renders) == 7, renders
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
    panel.get_by_role("button", name="Tout est conforme, confirmer").click()
    until(page, lambda: confirms)
    running["on"] = False
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{b_render}/preview", timeout=20000)
    route, answer = confirms.pop()
    with page.expect_response(f"{address}/confirmations"):
        route.fulfill(response=answer)
    page.evaluate(FRAMES)
    expect(panel.get_by_role("heading", name=FINAL)).to_be_visible()
    expect(panel.get_by_role("button", name="Tout est conforme, confirmer")).to_be_visible()
    expect(panel.get_by_role("link", name="Télécharger le PNG confirmé")).to_have_count(0)
    for pattern in (f"{address}/confirmations", f"{address}/jobs", f"{smoke.ORIGIN}/api/jobs/{b_job}"):
        page.unroute(pattern)
    a_confirmed = page.request.get(address).json()["confirmation"]
    assert a_confirmed["render_id"] == a_render, a_confirmed  # recorded on the server all the same
    panel.get_by_role("button", name="Fermer").click()

    # A reused confirmed job of this tab's revision N whose poster read answers N + 1 with no confirmation (another tab
    # saved): « Votre affiche est prête » never shows; the saved poster is reloaded, as the chat's button does.
    saved_elsewhere(470000)
    page.evaluate("""() => { window.sawReady = false; new MutationObserver(() => {
        if (document.getElementById('final-title')?.textContent.includes('Votre affiche est prête')) window.sawReady = true
    }).observe(document.body, { childList: true, subtree: true, characterData: true }) }""")
    a_job_id = next(item for item in page.request.get(f"{address}/jobs").json()["items"] if item["result_ref"] == a_render)["id"]
    page.route(f"{address}/renders", lambda route: route.fulfill(status=202, content_type="application/json",
               body=json.dumps({"job_id": a_job_id, "status_url": f"/api/jobs/{a_job_id}"})))
    page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
    expect(page.locator(".message.notice")).to_contain_text(CHANGED)
    expect(panel).to_have_count(0)
    assert page.evaluate("window.sawReady") is False
    page.unroute(f"{address}/renders")
    assert len(renders) == 8, renders  # answered by the page with the reused job

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


def current(panel, confirmation):
    """The panel holds that confirmation's own render, ready: the heading, its image, its download, no checklist."""
    expect(panel.get_by_role("heading", name=READY)).to_be_visible()
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{confirmation['render_id']}/preview")
    expect(panel.get_by_role("link", name="Télécharger le PNG confirmé")).to_have_attribute("href", confirmation["download_url"])
    expect(panel.get_by_role("button", name="Tout est conforme, confirmer")).to_have_count(0)


def earlier(panel, confirmation):
    """An earlier confirmed version: labelled, no live price, no « Partager », the download kept, the check offered."""
    expect(panel.get_by_role("heading", name=EARLIER)).to_be_visible()
    expect(panel.locator(".lede")).to_have_text(EARLIER_LEDE)
    expect(panel.locator(".shot img")).to_have_attribute("src", f"/api/renders/{confirmation['render_id']}/preview")
    expect(panel.locator(".facts")).not_to_contain_text("Prix")
    expect(panel).not_to_contain_text(re.compile(r"\d{3}\s000"))  # neither the live price nor the confirmed one
    expect(panel.locator(".done")).to_have_count(0)
    expect(panel.get_by_role("button", name="Partager")).to_have_count(0)
    expect(panel.get_by_role("link", name="Télécharger le PNG confirmé")).to_have_attribute("href", confirmation["download_url"])
    expect(panel.get_by_role("button", name="Vérifier l’aperçu final")).to_be_visible()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    assert (smoke.ROOT / "frontend/dist/index.html").is_file(), "build first: corepack npm@10 run build"
    product = OUT / "product.png"
    photo = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(photo).rounded_rectangle((250, 160, 750, 840), 50, fill="#202020")
    photo.save(product)
    errors = []
    with tempfile.TemporaryDirectory(prefix="affiche-share-") as data:
        server = smoke.serve(data)
        with (OUT / "preview.log").open("w") as log:
            vite = subprocess.Popen(["node", str(smoke.ROOT / "frontend/node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1",
                                     "--port", "5173", "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        walk(browser, errors, data, product)
                        assert not errors, errors
                    finally:
                        browser.close()
                (OUT / "results.json").write_text(json.dumps({"errors": errors, "viewports": [1366]}, indent=2))
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
          "answering after a save, changes nothing.")


if __name__ == "__main__":
    run()
