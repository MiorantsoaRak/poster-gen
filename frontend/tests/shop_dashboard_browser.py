"""Run from backend after the production frontend build. Stub stores and providers only."""
import subprocess
import tempfile
from uuid import uuid4
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

import browser_smoke as smoke
from terms_browser import open_atelier, set_terms


def set_theme(page, scheme):
    page.emulate_media(color_scheme=scheme)
    page.wait_for_function("theme => document.documentElement.dataset.theme === theme", arg="clair" if scheme == "light" else "sombre")


def walk_header(browser):
    context = browser.new_context()
    try:
        page = context.new_page()
        open_atelier(page, "#accueil")
        header = page.locator(".app-header")
        brand = header.get_by_role("link", name="Doka Studio — Accueil", exact=True)
        def check():
            for width in (360, 1440):
                page.set_viewport_size({"width": width, "height": 740})
                for scheme in ("light", "dark"):
                    set_theme(page, scheme)
                    expect(brand).to_be_visible()
                    expect(brand).to_have_attribute("href", "#accueil")
                    expect(brand.get_by_role("img")).to_have_count(0)
                    image = brand.locator("img:visible")
                    expect(image).to_have_count(1)
                    expect(image).to_have_js_property("complete", True)
                    assert image.evaluate("e => e.naturalWidth > 0")
                    box = image.bounding_box()
                    if width == 360:
                        expect(brand.get_by_text("Doka Studio", exact=True)).to_be_visible()
                        assert box["width"] == 32 and image.evaluate("e => getComputedStyle(e).paddingLeft") == "6px"
                    else:
                        assert box["width"] >= 220 and box["height"] > 0
                        assert ("reverse" in image.get_attribute("src")) == (scheme == "dark")
                    page.wait_for_function(smoke.NO_SIDEWAYS)
                    brand.focus()
                    expect(brand).to_be_focused()
                    page.keyboard.press("Tab")
                    assert header.evaluate("e => e.contains(document.activeElement)") and not brand.evaluate("e => e === document.activeElement")
                    last_mode = header.locator(".seg button").last
                    if width == 360 and last_mode.is_visible():
                        assert header.bounding_box()["height"] <= 64
                        controls = [brand, header.locator(".sign-out"), *header.locator(".seg button").all(), header.locator(".theme-toggle")]
                        boxes = [control.bounding_box() for control in controls]
                        assert all(box["height"] >= 44 and box["width"] >= 44 for box in boxes)
                        assert all(left["x"] + left["width"] <= right["x"] + 1 for left, right in zip(boxes, boxes[1:]))
                        theme_button = header.locator(".theme-toggle")
                        last_mode.focus()
                        page.keyboard.press("Tab")
                        expect(theme_button).to_be_focused()
                        mode_box, theme_box = last_mode.bounding_box(), theme_button.bounding_box()
                        assert mode_box["x"] + mode_box["width"] <= theme_box["x"]
                        assert abs(mode_box["y"] + mode_box["height"]/2 - theme_box["y"] - theme_box["height"]/2) < 2
        expect(page.get_by_label("Identifiant de la boutique")).to_be_visible()
        check()
        page.get_by_label("Identifiant de la boutique").fill(smoke.IDENTIFIER)
        page.get_by_label("Mot de passe", exact=True).fill(smoke.PASSWORD)
        page.get_by_role("button", name="Ouvrir l’atelier").click()
        expect(page.get_by_role("heading", name="Accueil", exact=True)).to_be_visible()
        check()
        for route, heading in (("credits", "Mes crédits"), ("compte", "Mon compte")):
            page.goto(smoke.ORIGIN + "/#" + route)
            expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
            check()
        def long_name(route):
            response = route.fetch()
            profile = response.json()
            profile["name"] = "Boutique " * 17
            route.fulfill(json=profile)
        page.route("**/api/shop-profile", long_name)
        page.goto(smoke.ORIGIN + "/#etapes")
        expect(page.get_by_label("Photos du produit")).to_be_enabled()
        check()
        assert header.locator(".shop-label").evaluate("e => e.scrollWidth > e.clientWidth")
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
        assert not any(path.startswith(("looks", "capabilities", "shop-profile", "creations?limit=50")) for path in reads), reads
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
        summary["review"] = {"total": 3, "first_creation_id": made["id"], "first_creation_title": made["document"]["offer"]["title"]}
        summary["failed"] = {"total": 1, "first_creation_id": recent_id}  # dashboard response from an older build
        page.route("**/api/shop-dashboard", lambda route: route.fulfill(json=summary))
        page.locator("nav").get_by_role("link", name="Accueil").click()
        review_action = home.get_by_role("button", name="Vérifier Casque de la boutique")
        expect(review_action).to_be_visible()
        expect(all_clear).to_have_count(0)
        expect(home.get_by_text("+ 2 à vérifier")).to_be_visible()
        expect(home.get_by_role("button", name="Génération échouée")).to_be_visible()
        poster = home.get_by_role("button", name="Affiche 5 Brouillon")
        expect(poster).to_be_visible()
        expect(home.locator(".home-recent button")).to_have_count(5)
        expect(home.locator(".home-recent")).not_to_contain_text("Casque de la boutique")
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


def check_balance_explanation(page, view, balance):
    reserved = view.get_by_text("Les crédits en attente sont déjà déduits du solde disponible.")
    empty = view.get_by_text("Un crédit disponible est nécessaire", exact=False)
    for available, pending, reason in [(2, 1, None), (0, 0, "terms"), (-2, 1, "service")]:
        balance.update(available=available, pending=pending)
        restriction = "Acceptez les conditions." if reason == "terms" else "La génération est en pause."
        balance["blocked"]["scene"] = {"reason": reason, "message_fr": restriction} if reason else None
        with page.expect_response("**/api/balance"):
            view.get_by_role("button", name="Actualiser").click()
        expect(view.locator("dd")).to_have_text([str(available), str(pending)])
        expect(reserved).to_have_count(int(pending > 0))
        expect(empty).to_have_count(int(available <= 0))
        expect(view.get_by_text(restriction, exact=True)).to_have_count(int(bool(reason)))
        expect(view.get_by_text(balance["purchase_fr"], exact=True)).to_have_count(1)
    checked = view.locator(".credit-balance .meta").inner_text().split(" à ")[-1]
    page.route("**/api/balance", lambda route: route.abort(), times=1)
    view.get_by_role("button", name="Actualiser").click()
    expect(view.get_by_role("button", name="Réessayer le solde")).to_be_visible()
    expect(view.get_by_text("Dernier solde connu à " + checked)).to_be_visible()
    expect(view.locator("dd")).to_have_text(["-2", "1"])
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
        page.locator("nav").get_by_role("link", name="Accueil").click()
        page.get_by_role("link", name="Mon compte").click()
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
        page.get_by_role("link", name="Mon compte").click()
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
        page.locator("nav").get_by_role("link", name="Styles").click()
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
            page.locator("nav").get_by_role("link", name="Styles").click()
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
        page.get_by_role("link", name="Mon compte").click()
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
            page.get_by_role("link", name="Mon compte").click()
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
                        walk_header(browser)
                        walk_credits(browser, out)
                        walk(browser, out)
                        walk_account(browser, out, data)
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
