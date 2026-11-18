"""Run from backend after the production frontend build. Stub stores and providers only."""
import subprocess
import tempfile
from uuid import uuid4
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

import browser_smoke as smoke
from terms_browser import open_atelier


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
        assert "shop-dashboard" in reads and "creations?limit=5" in reads
        assert not any(path.startswith(("looks", "capabilities", "shop-profile", "creations?limit=50")) for path in reads), reads
        held.pop().abort()
        expect(home.get_by_text("Affiches indisponibles.", exact=False)).to_be_visible()
        assert home.get_by_text("Aucune affiche pour le moment.").count() == 0
        page.unroute("**/api/creations?limit=5")
        home.get_by_role("button", name="Réessayer les affiches").click()
        expect(home.get_by_text("Aucune affiche pour le moment.")).to_be_visible()
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            page.wait_for_function("theme => document.documentElement.dataset.theme === theme", arg="clair" if scheme == "light" else "sombre")
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
        expect(stamp).to_have_text("Solde vérifié à 10:30.")
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
        page.locator("nav").get_by_role("link", name="Accueil").click()
        home.get_by_role("link", name="Créer une affiche").click()
        expect(page.get_by_label("Votre message")).to_be_visible()
        page.locator(".chat input[type=file]").set_input_files(smoke.ROOT / "backend/fixtures/examples/phone-noir.jpg")
        page.go_back()
        dialog = page.get_by_role("dialog", name="Quitter le message ?")
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Annuler").click()
        expect(page.locator(".chat .pic img").first).to_be_visible()
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
        page.locator("nav").get_by_role("link", name="Accueil").click()
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
        summary["review"] = {"total": 3, "first_creation_id": made["id"]}
        summary["failed"] = {"total": 1, "first_creation_id": made["id"]}
        page.route("**/api/shop-dashboard", lambda route: route.fulfill(json=summary))
        page.locator("nav").get_by_role("link", name="Accueil").click()
        expect(home.get_by_text("+ 2 à vérifier")).to_be_visible()
        expect(home.get_by_role("button", name="Génération échouée")).to_be_visible()
        poster = home.get_by_role("button", name="Affiche 5 Brouillon")
        expect(poster).to_be_visible()
        expect(home.locator(".home-recent button")).to_have_count(5)
        expect(home.locator(".home-recent")).not_to_contain_text("Casque de la boutique")
        for button, target, title in ((home.get_by_role("button", name="Affiche à vérifier"), made["id"], "Casque de la boutique"),
                                      (home.get_by_role("button", name="Génération échouée"), made["id"], "Casque de la boutique"),
                                      (poster, recent_id, "Affiche 5")):
            button.click()
            page.wait_for_url(f"**/#{target}")
            expect(page.get_by_label("Titre", exact=True)).to_have_value(title)
            with page.expect_response(lambda r: r.url.endswith("/api/balance")):
                page.evaluate(smoke.VISIBILITY, True)
                page.evaluate(smoke.VISIBILITY, False)
            page.go_back()
            expect(home).to_be_visible()
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
        page.locator("nav").get_by_role("link", name="Accueil").click()
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
        gallery.get_by_role("button", name="Réessayer la liste").click()
        expect(gallery.locator(".library-item")).to_have_count(6)
        # From an open poster, a successful creator reload must yield to the later choice of the gallery.
        page.set_viewport_size({"width": 1366, "height": 768})
        gallery.get_by_role("button", name="Affiche 5 Brouillon", exact=False).click()
        expect(page.get_by_label("Titre", exact=True)).to_have_value("Affiche 5")
        page.route("**/api/capabilities", lambda route: pending_caps.append(route))
        nav = page.get_by_role("navigation", name="Navigation", exact=True)
        with page.expect_request("**/api/capabilities"):
            nav.get_by_role("link", name="Créer", exact=True).click()
        nav.get_by_role("link", name="Mes affiches", exact=False).click()
        pending_caps.pop().continue_()
        expect(gallery).to_be_visible()
        page.wait_for_url("**/#affiches")
        page.unroute("**/api/capabilities")
        page.set_viewport_size({"width": 360, "height": 640})
        page.locator("nav").get_by_role("link", name="Accueil").click()
        balance = page.request.get(smoke.ORIGIN + "/api/balance").json()
        balance["available"] = 0
        balance["blocked"]["scene"] = {"reason": "terms", "message_fr": "Acceptez les conditions."}
        page.route("**/api/balance", lambda route: route.fulfill(json=balance))
        home.get_by_role("button", name="Actualiser").click()
        expect(home.get_by_role("button", name="Lire les conditions")).to_be_visible()
        expect(home.get_by_role("link", name="Obtenir des crédits")).to_have_count(0)
        page.unroute("**/api/balance")
        page.unroute("**/api/shop-dashboard")
        home.get_by_role("link", name="Créer une affiche").click()
        expect(page.get_by_label("Photos du produit")).to_be_enabled()
        # A late list response cannot restore the dashboard after the identity has changed.
        page.route("**/api/creations?limit=5", lambda route: held.append(route))
        page.route("**/api/shop-dashboard", lambda route: route.fulfill(status=409, json={"error": {"code": "shop_changed"}}))
        page.locator("nav").get_by_role("link", name="Accueil").click()
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
        opener = page.locator(".creator-credits")
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
        opener = page.locator(".creator-credits")
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
        opener = page.locator(".creator-credits")
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
        page.goto(smoke.ORIGIN + "/#credits")
        view = page.get_by_role("region", name="Mes crédits")
        expect(view.get_by_text("-2", exact=True)).to_be_visible()
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
            page.emulate_media(color_scheme=scheme)
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


def run():
    out = smoke.ROOT / "outputs" / "shop-dash"
    out.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory() as data, (out / "home-preview.log").open("w") as log:
        server = smoke.serve(Path(data))
        try:
            vite = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1",
                                     "--port", "5173", "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    try:
                        walk_credits(browser, out)
                        walk(browser, out)
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
