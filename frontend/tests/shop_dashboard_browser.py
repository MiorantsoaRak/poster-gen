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
