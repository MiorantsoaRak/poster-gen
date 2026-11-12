"""Real Chromium + Vue + HTTP API smoke, isolated stub data; run from backend with uv run python ../frontend/tests/browser_smoke.py."""
import json
import base64
import copy
import io
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time

import uvicorn
from playwright.sync_api import sync_playwright, expect
from PIL import Image, ImageChops, ImageDraw

from affiche.api import create_app
from affiche.config import Settings
from affiche.posters.auth import PASSWORDS

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs" / "editor-smoke"
ORIGIN = "http://127.0.0.1:5173"
PASSWORD = os.urandom(12).hex()  # a throwaway credential per run against temporary stub data


def check_material_pixels(page, document):
    fixture = copy.deepcopy(document)
    target = next(layer for layer in fixture["formats"]["feed"]["layers"] if layer["role"] == "title")
    target.update(x=64, y=64, width=950, height=140, font_size=72, fill="#FFFFFF", outline=None, shadow=None)
    fixture["offer"]["title"] = "Écouteurs R50i"
    fixture["formats"]["feed"]["scene"] = {"visual_id": None, "crop": None}
    swatch = Image.new("RGB", (32, 32), "#edc45e")
    drawing = ImageDraw.Draw(swatch)
    for x in range(0, 32, 4):
        drawing.line((x, 0, x, 31), fill="#84601b", width=2)
    stream = io.BytesIO()
    swatch.save(stream, format="PNG")
    sources = {"effect:material": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()}
    def render(doc):
        result = page.evaluate("async ([document, sources]) => (await import('/src/render.ts')).render(document, sources)", [doc, sources])
        assert not [issue for issue in result["issues"] if issue["blocking"]], result["issues"]
        return Image.open(io.BytesIO(base64.b64decode(result["png"].split(",", 1)[1]))).convert("RGB")
    plain = render(fixture)
    target["texture_effect_id"] = "material"
    material = render(fixture)
    box = ImageChops.difference(plain, material).getbbox()
    assert box and box[0] >= 64 and box[1] >= 64 and box[2] <= 1014 and box[3] <= 204, box
    # The native pattern fill cannot introduce pixels in the holes or space outside exact glyphs.
    background = Image.new("RGB", plain.size, "#17324D")
    def support(image):
        r, g, b = ImageChops.difference(image, background).split()
        return ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda value: 255 if value else 0)
    plain_glyphs, material_glyphs = support(plain), support(material)
    # Darker colours can round a faint antialias edge to zero; they may never paint outside the glyph.
    assert ImageChops.subtract(material_glyphs, plain_glyphs).getbbox() is None
    fixture["offer"]["price_ar"] += 1000
    edited = render(fixture)
    price = next(layer for layer in fixture["formats"]["feed"]["layers"] if layer["role"] == "price")
    box = ImageChops.difference(material, edited).getbbox()
    assert box and box[0] >= price["x"] and box[1] >= price["y"] and box[3] <= price["y"] + price["height"], box
    material.save(OUTPUT / "glyph-material-test.png")
    price.update(font_id="montserrat-black-italic", weight=900, font_size=72, x=240, width=600, height=150,
                 price_badge={"fill": "#FFFFFF", "border_start": "#009FE3", "border_end": "#1853BD"})
    plain_price = render(fixture)
    price["texture_effect_id"] = "material"
    textured_price = render(fixture)
    box = ImageChops.difference(plain_price, textured_price).getbbox()
    assert box and box[0] > price["x"] + 6 and box[2] < price["x"] + price["width"] - 6, box
    assert box[1] > price["y"] + 6 and box[3] < price["y"] + price["height"] - 6, box
    textured_price.save(OUTPUT / "capsule-material-test.png")


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="affiche-browser-") as data:
        settings = Settings(_env_file=None, image_provider="stub", planner_provider="stub", openai_api_key=None,
                            anthropic_api_key=None, stub_fail=None, spend_cap_usd="20", spend_cap_since="2026-11-06",
                            data_dir=data, app_origin=ORIGIN, shop_password_hash=PASSWORDS.hash(PASSWORD))
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=8000, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        with (OUTPUT / "vite.log").open("w", encoding="utf-8") as log:
            vite = subprocess.Popen(["node", str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1"],
                                    cwd=ROOT / "frontend", stdout=log, stderr=log,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                with sync_playwright() as playwright:
                    # SMOKE_CHANNEL=msedge runs the same flow in the installed Microsoft Edge.
                    browser = playwright.chromium.launch(headless=True, channel=os.environ.get("SMOKE_CHANNEL") or None)
                    print("Browser:", browser.browser_type.name, os.environ.get("SMOKE_CHANNEL") or "bundled", browser.version, flush=True)
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 1050})
                        errors = []
                        page.set_default_timeout(10000)
                        page.on("response", lambda response: print(f"HTTP {response.status} {response.url}", flush=True) if response.status >= 400 else None)
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        for attempt in range(60):
                            if vite.poll() is not None:
                                raise RuntimeError("Vite stopped; inspect outputs/editor-smoke/vite.log")
                            try:
                                page.goto(ORIGIN, timeout=2000)
                                break
                            except Exception:
                                if attempt == 59:
                                    raise
                                time.sleep(.25)
                        page.get_by_label("Mot de passe", exact=True).fill(PASSWORD)
                        page.get_by_role("button", name="Ouvrir l’atelier").click()
                        expect(page.get_by_label("Photos du produit")).to_be_enabled()
                        page.screenshot(path=str(OUTPUT / "intake.png"), full_page=True)
                        page.get_by_label("Photos du produit").set_input_files(ROOT / "outputs/review-2026-11-10/soundcore-r50i-black-original.jpg")
                        expect(page.locator(".photo-strip img")).to_have_count(1)
                        page.get_by_label("Nom du produit", exact=True).fill("Soundcore R50i")
                        page.get_by_label("Variante confirmée").fill("Noir · écouteurs et boîtier")
                        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
                        page.get_by_label("Les photos correspondent").check()
                        # A logo is saved in the profile but left off this poster; it is ticked after the scene, further down.
                        Image.new("RGBA", (256, 256), (20, 120, 220, 255)).save(OUTPUT / "logo.png")
                        page.locator("details input[type=file]").set_input_files(OUTPUT / "logo.png")
                        expect(page.get_by_alt_text("Logo de la boutique")).to_be_visible()
                        page.get_by_role("checkbox", name="Logo", exact=True).uncheck()
                        # The logo or the contact identifies the shop: its name starts unticked (ADR-053).
                        expect(page.get_by_role("checkbox", name="Nom de la boutique", exact=True)).not_to_be_checked()
                        page.get_by_label("Nom de la boutique", exact=True).first.fill("Original Phone Mada")
                        page.get_by_label("Contact", exact=True).first.fill("038 93 028 00 / 034 93 028 00")
                        page.get_by_role("checkbox", name="Nom de la boutique", exact=True).check()
                        page.get_by_role("checkbox", name="Contact", exact=True).check()
                        page.get_by_role("button", name="Préparer mon affiche").click()
                        expect(page.get_by_role("heading", name="Soundcore R50i", exact=True)).to_be_visible()
                        expect(page.locator(".poster-canvas canvas").first).to_be_visible()
                        # The contact is one compact line written by the renderer; its position is free and remembered.
                        def footer(role):
                            layers = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]["formats"]["feed"]["layers"]
                            return next((layer for layer in layers if layer["role"] == role), None)
                        def until(check):
                            for _ in range(50):
                                if check():
                                    return
                                page.wait_for_timeout(200)
                            raise AssertionError("condition not reached")
                        until(lambda: footer("contact").get("icon") == "phone")
                        compact = footer("contact")
                        assert (compact["font_size"], compact["weight"], compact["height"], compact["align"]) == (32, 700, 48, "center"), compact
                        assert page.get_by_label("Dessiner aussi le nom de la boutique et le contact dans l’image").count() == 0
                        page.get_by_label("Position du contact").select_option("right")
                        until(lambda: footer("contact")["align"] == "right")
                        assert json.loads(page.evaluate("localStorage.getItem('affiche.style')"))["contact_align"] == "right"
                        # The coach line and the reasons under blocked buttons tell a new owner what to do.
                        expect(page.locator(".coach")).to_contain_text("choisissez un style")
                        # Several versions are possible and announced before the first one exists.
                        expect(page.get_by_role("heading", name="Versions 0 sur 12")).to_be_visible()
                        expect(page.get_by_text("Vous choisirez celle à exporter.", exact=False)).to_be_visible()
                        assert page.get_by_text("S’inspirer d’une affiche").count() == 0 and page.get_by_label("Préparation").count() == 0
                        # A poster the shop likes becomes a saved look beside the built-in ones (stub brief, no spend).
                        page.get_by_text("Créer un style depuis une affiche", exact=True).click()
                        expect(page.get_by_text("Choisissez d’abord une affiche modèle ci-dessus.")).to_be_visible()
                        page.get_by_label("Affiche modèle").set_input_files(ROOT / "outputs/review-2026-11-10/soundcore-r50i-black-original.jpg")
                        expect(page.get_by_alt_text("Affiche modèle pour le nouveau style")).to_be_visible()
                        expect(page.get_by_text("Choisissez d’abord une affiche modèle ci-dessus.")).to_have_count(0)
                        page.get_by_label("Nom du style").fill("Vagues bleues")
                        page.get_by_role("button", name="Enregistrer ce style").click()
                        # A paid action is confirmed first, with its cost; cancelling does nothing.
                        expect(page.get_by_role("dialog")).to_contain_text("Créer un style depuis cette affiche ?")
                        expect(page.get_by_role("dialog")).to_contain_text("aucune dépense")
                        page.get_by_role("dialog").get_by_role("button", name="Annuler").click()
                        assert page.request.get(f"{ORIGIN}/api/looks").json()["items"] == []
                        page.get_by_role("button", name="Enregistrer ce style").click()
                        page.get_by_role("button", name="Créer le style").click()
                        expect(page.get_by_text("Style « Vagues bleues » enregistré", exact=False)).to_be_visible(timeout=15000)
                        expect(page.get_by_role("button", name="Vagues bleues")).to_have_attribute("aria-pressed", "true")
                        expect(page.get_by_label("Ambiance (modifiable)")).to_have_value(re.compile("vagues translucides"))
                        looks = page.request.get(f"{ORIGIN}/api/looks").json()["items"]
                        assert [item["name"] for item in looks] == ["Vagues bleues"] and looks[0]["brief"]["alignment"] == "left"
                        # The look picker sets the art direction; this flow then tests the editable title layer.
                        page.get_by_role("button", name="Luxe sombre").click()
                        expect(page.get_by_label("Ambiance (modifiable)")).to_have_value(re.compile("Fond noir charbon"))
                        page.screenshot(path=str(OUTPUT / "studio-start.png"), full_page=True)
                        # "Brand as plain text" is offered only once a brand is typed.
                        plain_brand = page.get_by_label("Écrire la marque en texte simple", exact=False)
                        page.get_by_label("Marque (facultative)").fill("")
                        expect(plain_brand).to_have_count(0)
                        page.get_by_label("Marque (facultative)").fill("JBL")
                        expect(plain_brand).to_be_visible()
                        page.get_by_label("Marque (facultative)").fill("")
                        page.get_by_text("Ce que l’IA dessine dans l’image", exact=True).click()
                        # By default the contact is drawn in the composition, at the chosen position, without the
                        # shop name (ADR-055). The request is caught here and refused, so no scene is made by it.
                        expect(page.get_by_label("Dessiner aussi le contact dans l’image")).to_be_checked()
                        asked = []
                        def catch_scene(route):
                            asked.append(route.request.post_data_json)
                            route.fulfill(status=409, content_type="application/json", body='{"detail": {"code": "plan_stale"}}')
                        page.route("**/api/creations/*/scenes", catch_scene)
                        page.get_by_role("button", name="Générer l’affiche").click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        until(lambda: asked)
                        page.unroute("**/api/creations/*/scenes", catch_scene)
                        assert asked[0]["headline"]["signature"] is True and asked[0]["headline"]["signature_align"] == "right", asked
                        assert "brand_text" not in asked[0]["headline"], asked
                        expect(page.get_by_role("alert")).to_be_visible()
                        page.get_by_label("Laisser l’IA composer le titre dans l’image").uncheck()
                        # One tap: the plan is made on the way and reused by the retry below.
                        # Lose the first paid-action response after the server accepted it; retry must reuse its key.
                        def lose_response(route):
                            route.fetch()
                            route.abort("failed")
                            page.unroute("**/api/creations/*/scenes", lose_response)
                        page.route("**/api/creations/*/scenes", lose_response)
                        page.get_by_role("button", name="Générer l’affiche").click()
                        expect(page.get_by_role("dialog")).to_contain_text("Générer l’affiche ?")
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("alert")).to_contain_text("Connexion interrompue")
                        page.get_by_role("button", name="Générer l’affiche").click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
                        # One agreement covers the listed points (ADR-051): a summary to read, no boxes to tick.
                        expect(page.locator(".review-checks .points li")).to_have_count(6)
                        expect(page.locator(".review-panel input[type=checkbox]")).to_have_count(0)
                        page.screenshot(path=str(OUTPUT / "review.png"))
                        page.get_by_role("button", name="Signaler un problème").click()
                        expect(page.get_by_role("button", name="Refuser cette version")).to_be_disabled()
                        page.get_by_role("button", name="Tout est conforme, approuver").click()
                        expect(page.get_by_text("Fidélité du produit approuvée.", exact=False)).to_be_visible()
                        # The position survived the scene request, and a logo ticked now stays clear of the contact.
                        assert footer("contact")["align"] == "right" and footer("contact")["visible"]
                        page.get_by_role("checkbox", name="Logo", exact=True).check()
                        until(lambda: footer("logo") and footer("logo")["visible"])
                        logo, beside = footer("logo"), footer("contact")
                        assert logo["x"] == 54 and beside["x"] >= logo["x"] + logo["width"] + 20 and beside["x"] + beside["width"] <= 1026.5, (logo, beside)
                        assert abs(logo["y"] + logo["height"] - beside["y"] - beside["height"]) < 1, (logo, beside)
                        page.get_by_role("checkbox", name="Logo", exact=True).uncheck()
                        until(lambda: footer("contact")["x"] == 54 and footer("contact")["width"] == 972)
                        jobs = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}/jobs").json()["items"]
                        assert len([job for job in jobs if job["kind"] == "scene"]) == 1
                        scene_before = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]["formats"]["feed"]["scene"]
                        page.get_by_label("Prix en ariary", exact=True).fill("95 000")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.get_by_role("button", name="Annuler", exact=True).click()
                        expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("90\u202f000")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.reload()
                        expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("90\u202f000")
                        saved = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert saved["document"]["formats"]["feed"]["scene"] == scene_before
                        visual = page.request.get(f"{ORIGIN}/api/visuals/{scene_before['visual_id']}").json()
                        # The editor no longer sends a separate style-reference image (the API still accepts one).
                        assert visual["style_reference_asset"] is None and len(visual["original_urls"]) == 1
                        expect(page.locator(".coach")).to_contain_text("Dernière étape")
                        # The chosen version is named, and another one is one confirmed tap away.
                        expect(page.get_by_role("heading", name="Versions 1 sur 12")).to_be_visible()
                        expect(page.get_by_text("Choisie pour l’export", exact=True)).to_be_visible()
                        expect(page.get_by_role("button", name="Nouvelle version")).to_be_enabled()
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
                        page.locator(".poster-canvas").focus()
                        page.keyboard.press("ArrowRight")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        moved = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert moved["document"]["formats"]["feed"]["layers"][0]["x"] == saved["document"]["formats"]["feed"]["layers"][0]["x"] + 1
                        page.evaluate("scrollTo(0, 0)")
                        page.screenshot(path=str(OUTPUT / "desktop.png"), full_page=True)
                        page.set_viewport_size({"width": 390, "height": 844})
                        expect(page.get_by_label("Titre", exact=True)).to_be_visible()
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        page.screenshot(path=str(OUTPUT / "mobile.png"), full_page=True)
                        # A second tab changes the saved version. Local work must remain available for a copy.
                        creation_id = page.url.split("#")[1]
                        remote = page.request.get(f"{ORIGIN}/api/creations/{creation_id}").json()
                        remote["document"]["offer"]["title"] = "Titre modifié dans un autre onglet"
                        from uuid import uuid4
                        response = page.request.put(f"{ORIGIN}/api/creations/{creation_id}", data=remote["document"],
                            headers={"Origin": ORIGIN, "If-Match": f'"{remote["revision"]}"', "Idempotency-Key": str(uuid4())})
                        assert response.status == 200
                        page.get_by_label("Titre", exact=True).fill("Mon titre conservé")
                        expect(page.get_by_role("button", name="Conserver mes modifications dans une copie")).to_be_visible(timeout=10000)
                        page.get_by_role("button", name="Conserver mes modifications dans une copie").click()
                        expect(page.get_by_text("Vos modifications ont été conservées dans une copie.")).to_be_visible()
                        assert page.url.split("#")[1] != creation_id
                        expect(page.get_by_label("Titre", exact=True)).to_have_value("Mon titre conservé")
                        # Layer-level editing lives under "Réglages avancés" in the third step.
                        page.get_by_text("Réglages avancés", exact=True).click()
                        # The stub proposal is explicitly labelled as a simulation and needs an apply decision.
                        page.get_by_text("Ajuster ce texte avec une consigne", exact=True).click()
                        page.get_by_label("Votre consigne").fill("Une couleur dorée")
                        before_polish = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        page.get_by_role("button", name="Proposer un ajustement", exact=True).click()
                        # Every paid call is confirmed with its cost first; Escape or "Annuler" backs out.
                        expect(page.get_by_role("dialog")).to_contain_text("aucune dépense")
                        page.keyboard.press("Escape")
                        expect(page.get_by_role("dialog")).to_have_count(0)
                        page.get_by_role("button", name="Proposer un ajustement", exact=True).click()
                        page.get_by_role("button", name="Lancer la proposition", exact=True).click()
                        expect(page.get_by_role("button", name="Appliquer au texte")).to_be_visible(timeout=15000)
                        unchanged = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert unchanged == before_polish
                        page.get_by_role("button", name="Appliquer au texte").click()
                        expect(page.get_by_role("button", name="Appliquer au texte")).to_have_count(0)
                        after_polish = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        expected = copy.deepcopy(before_polish["document"])
                        next(layer for layer in expected["formats"]["feed"]["layers"] if layer["role"] == "title")["fill"] = "#FFCC66"
                        assert after_polish["document"] == expected
                        check_material_pixels(page, expected)
                        page.get_by_role("button", name="Générer la matière du texte", exact=True).click()
                        page.get_by_role("button", name="Générer la matière", exact=True).click()
                        expect(page.get_by_role("button", name="Appliquer la matière", exact=True)).to_be_visible(timeout=15000)
                        still = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert still == after_polish
                        page.get_by_role("button", name="Appliquer la matière", exact=True).click()
                        expect(page.get_by_role("button", name="Retirer la matière du texte", exact=True)).to_be_visible()
                        with_effect = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        effect_id = next(layer for layer in with_effect["document"]["formats"]["feed"]["layers"] if layer["role"] == "title")["texture_effect_id"]
                        assert effect_id
                        expected_effect = copy.deepcopy(expected)
                        next(layer for layer in expected_effect["formats"]["feed"]["layers"] if layer["role"] == "title")["texture_effect_id"] = effect_id
                        assert with_effect["document"] == expected_effect
                        page.get_by_role("button", name="Annuler", exact=True).click()
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        undone = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        assert undone["document"] == expected
                        # Reference typography is a manual single-layer edit, saved and undoable without generation.
                        page.get_by_role("button", name="Prix", exact=True).click()
                        # The chosen look already dressed the price as its dark pill, at half the canvas width.
                        auto_pill = next(layer for layer in expected["formats"]["feed"]["layers"] if layer["role"] == "price")
                        assert auto_pill["price_badge"] == {"fill": "#111114", "border_start": "#C8A45A", "border_end": "#C8A45A"}
                        assert (auto_pill["width"], auto_pill["x"], auto_pill["fill"]) == (540, 270, "#FFFFFF")
                        expect(page.get_by_label("Présentation du prix", exact=True)).to_have_value("capsule")
                        page.get_by_label("Présentation du prix", exact=True).select_option("simple")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        expected = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]
                        page.get_by_label("Police", exact=True).select_option("montserrat-black-italic")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.get_by_label("Présentation du prix", exact=True).select_option("capsule")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        styled = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()
                        expected_styled = copy.deepcopy(expected)
                        price_layer = next(layer for layer in expected_styled["formats"]["feed"]["layers"] if layer["role"] == "price")
                        # The look left white digits, so the new capsule is dark: the price must stay readable.
                        assert price_layer["fill"] == "#FFFFFF"
                        price_layer.update(font_id="montserrat-black-italic", weight=900,
                                           price_badge={"fill": "#22262E", "border_start": "#009FE3", "border_end": "#1853BD"})
                        assert styled["document"] == expected_styled
                        runs = page.evaluate("""async doc => {
                            const { textRuns } = await import('/src/canvas.ts');
                            return textRuns(doc, doc.formats.feed.layers.find(layer => layer.role === 'price'));
                        }""", styled["document"])
                        assert [run["text"] for run in runs] == ["90\u00a0000", "AR"]
                        assert runs[0]["fontStyle"] == "italic 900" and runs[1]["fontStyle"] == "400"
                        assert runs[1]["fontSize"] < runs[0]["fontSize"]
                        page.get_by_role("button", name="Annuler", exact=True).click()
                        expect(page.get_by_label("Présentation du prix", exact=True)).to_have_value("simple")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.get_by_role("button", name="Rétablir", exact=True).click()
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.reload()
                        expect(page.get_by_label("Prix en ariary", exact=True)).to_have_value("90\u202f000")
                        page.get_by_text("Réglages avancés", exact=True).click()
                        page.get_by_role("button", name="Prix", exact=True).click()
                        expect(page.get_by_label("Police", exact=True)).to_have_value("montserrat-black-italic")
                        expect(page.get_by_label("Présentation du prix", exact=True)).to_have_value("capsule")
                        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth", timeout=5000)
                        assert page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"] == expected_styled
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
                        page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
                        expect(page.get_by_role("heading", name="Dernière vérification avant le téléchargement")).to_be_visible(timeout=40000)
                        preview_url = page.locator(".final-preview img").get_attribute("src")
                        preview_bytes = page.request.get(ORIGIN + preview_url).body()
                        expect(page.locator(".final-preview .points li")).not_to_have_count(0)
                        expect(page.locator(".final-preview input[type=checkbox]")).to_have_count(0)
                        expect(page.locator(".final-preview img")).to_be_visible()
                        page.screenshot(path=str(OUTPUT / "final-mobile.png"))
                        page.set_viewport_size({"width": 1440, "height": 1050})
                        page.screenshot(path=str(OUTPUT / "final.png"))
                        page.set_viewport_size({"width": 390, "height": 844})
                        page.get_by_role("button", name="Tout est conforme, confirmer", exact=True).click()
                        link = page.get_by_role("link", name="Télécharger le PNG confirmé")
                        expect(link).to_be_visible()
                        downloaded = page.request.get(ORIGIN + link.get_attribute("href"))
                        assert downloaded.status == 200 and downloaded.body() == preview_bytes
                        assert Image.open(io.BytesIO(preview_bytes)).size == (1080, 1350)
                        (OUTPUT / "confirmed-stub-poster.png").write_bytes(preview_bytes)
                        # The page behind an open panel is inert: close it, change the price, and reopen by reloading.
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        page.get_by_label("Prix en ariary", exact=True).fill("91 000")
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.reload()
                        expect(link).to_be_visible()
                        # A confirmed poster offers no second confirmation; the server's
                        # preview_stale refusal is covered in backend/tests/test_exports.py.
                        expect(page.get_by_role("button", name="Tout est conforme, confirmer", exact=True)).to_have_count(0)
                        expect(page.locator(".final-preview .points")).to_have_count(0)
                        assert page.request.get(ORIGIN + link.get_attribute("href")).body() == preview_bytes
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        page.get_by_label("Titre", exact=True).fill("Écouteurs " * 25)
                        expect(page.get_by_text("Le texte dépasse son cadre.", exact=False)).to_be_visible()
                        page.get_by_label("Titre", exact=True).fill("Son 🎵")
                        expect(page.get_by_text("Cette police ne contient pas tous les caractères du texte.")).to_be_visible()
                        # "Mes affiches" shows each poster itself: the confirmed one by its final preview.
                        expect(page.get_by_text("Enregistré", exact=True)).to_be_visible(timeout=10000)
                        page.set_viewport_size({"width": 1440, "height": 1000})
                        page.locator(".nav a", has_text="Mes affiches").click()
                        # The view is in the address: a reload stays on the list.
                        assert page.url.endswith("#affiches"), page.url
                        page.reload()
                        thumbnail = page.locator('.library-item img[src^="/api/thumbnails/"]').first
                        expect(thumbnail).to_be_visible()
                        # A small resized image of the 1080 x 1350 preview, not the full file.
                        page.wait_for_function("image => image.complete && image.naturalWidth === 192 && image.naturalHeight === 240", arg=thumbnail.element_handle())
                        assert len(page.request.get(ORIGIN + thumbnail.get_attribute("src")).body()) < 40_000
                        page.screenshot(path=str(OUTPUT / "mes-affiches.png"))
                        # Managing the list (R-CREATION-LIBRARY-003): state in words, copy, remove with confirmation, restore.
                        rows = page.locator(".library-row")
                        before = rows.count()
                        expect(page.locator(".library-item span").first).to_contain_text(re.compile("Brouillon|À vérifier|Approuvée|Confirmée"))
                        expect(page.locator(".nav a", has_text="Mes affiches")).to_contain_text(str(before))
                        rows.first.get_by_role("button", name=re.compile("^Dupliquer")).click()
                        expect(page.locator(".poster-canvas canvas").first).to_be_visible()
                        copy_id = page.url.split("#")[1]
                        page.locator(".nav a", has_text="Mes affiches").click()
                        expect(rows).to_have_count(before + 1)
                        rows.first.get_by_role("button", name=re.compile("^Retirer")).click()
                        expect(page.get_by_role("dialog")).to_contain_text("Rien n’est effacé")
                        page.get_by_role("dialog").get_by_role("button", name="Retirer de la liste").click()
                        expect(rows).to_have_count(before)
                        # A removed poster is not opened by its address: the list of removed posters is shown instead.
                        page.goto(f"{ORIGIN}/#{copy_id}")
                        expect(page.get_by_text("Cette affiche a été retirée de la liste.", exact=False)).to_be_visible()
                        expect(page.get_by_label("Afficher les affiches retirées")).to_be_checked()
                        expect(rows).to_have_count(1)
                        rows.first.get_by_role("button", name=re.compile("^Remettre")).click()
                        expect(rows).to_have_count(0)
                        page.get_by_label("Afficher les affiches retirées").uncheck()
                        expect(rows).to_have_count(before + 1)
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
                        # The logo as a round seal (ADR-057): a new poster with the logo and the contact, no shop name.
                        page.locator(".nav a", has_text="Créer").click()
                        page.get_by_label("Photos du produit").set_input_files(ROOT / "outputs/review-2026-11-10/soundcore-r50i-black-original.jpg")
                        expect(page.locator(".photo-strip img")).to_have_count(1)
                        page.get_by_label("Nom du produit", exact=True).fill("Soundcore R50i sceau")
                        page.get_by_label("Variante confirmée").fill("Noir")
                        page.get_by_label("Prix en ariary", exact=True).fill("90 000")
                        page.get_by_label("Les photos correspondent").check()
                        expect(page.get_by_role("checkbox", name="Logo", exact=True)).to_be_checked()
                        expect(page.get_by_role("checkbox", name="Nom de la boutique", exact=True)).not_to_be_checked()
                        page.get_by_role("button", name="Préparer mon affiche").click()
                        expect(page.get_by_role("heading", name="Soundcore R50i sceau", exact=True)).to_be_visible()
                        seal_option = page.get_by_label("Logo en sceau rond dans l’image")
                        expect(seal_option).to_be_checked()
                        expect(page.get_by_label("Position du contact")).to_be_disabled()
                        sent = []
                        page.on("request", lambda request: sent.append(request.post_data_json) if request.method == "POST" and request.url.endswith("/scenes") else None)
                        page.get_by_role("button", name="Générer l’affiche").click()
                        page.get_by_role("button", name="Lancer la génération").click()
                        expect(page.get_by_role("heading", name="Vérifier la fidélité du produit")).to_be_visible(timeout=30000)
                        assert sent[-1]["headline"]["logo_seal"] is True and sent[-1]["headline"]["signature_align"] == "right", sent[-1]
                        expect(page.get_by_text("Un disque blanc vide est prévu pour le logo", exact=False)).to_be_visible()
                        page.get_by_role("button", name="Tout est conforme, approuver").click()
                        expect(page.get_by_text("Fidélité du produit approuvée.", exact=False)).to_be_visible()
                        sealed = page.request.get(f"{ORIGIN}/api/creations/{page.url.split('#')[1]}").json()["document"]
                        disc = page.request.get(f"{ORIGIN}/api/visuals/{sealed['formats']['feed']['scene']['visual_id']}").json()["logo_disc"]
                        seal = footer("logo")
                        assert disc and seal["shape"] == "circle" and seal["visible"] and abs(seal["width"] - disc["d"] - 4) < .1, (disc, seal)
                        assert abs(seal["x"] + seal["width"] / 2 - disc["x"]) < .1 and abs(seal["y"] + seal["height"] / 2 - disc["y"]) < .1
                        # The seal is locked once a version exists; removing the logo would leave an empty disc, so export is blocked.
                        expect(seal_option).to_be_disabled()
                        page.get_by_role("checkbox", name="Logo", exact=True).uncheck()
                        expect(page.get_by_text("L’image contient un disque prévu pour le logo", exact=False)).to_be_visible()
                        expect(page.get_by_role("button", name="Vérifier l’aperçu final", exact=True)).to_be_disabled()
                        page.get_by_role("checkbox", name="Logo", exact=True).check()
                        until(lambda: footer("logo")["visible"] and abs(footer("logo")["x"] - seal["x"]) < .1)
                        expect(page.get_by_text("L’image contient un disque prévu pour le logo", exact=False)).to_have_count(0)
                        page.get_by_role("button", name="Vérifier l’aperçu final", exact=True).click()
                        expect(page.get_by_role("heading", name="Dernière vérification avant le téléchargement")).to_be_visible(timeout=40000)
                        expect(page.get_by_text("Le logo recouvre bien son disque", exact=True)).to_be_visible()
                        expect(page.locator(".final-preview img")).to_be_visible()
                        page.screenshot(path=str(OUTPUT / "seal-final.png"))
                        page.locator(".final-preview").get_by_role("button", name="Fermer").click()
                        # Managing styles (R-CREATION-LIBRARY-004): open, rename with its refusals, remove with confirmation.
                        page.locator(".final-preview").wait_for(state="detached")
                        page.locator(".nav a", has_text="Styles").click()
                        cards = page.locator(".look-card")
                        expect(cards).to_have_count(4)
                        cards.filter(has_text="Studio clair").click()
                        panel = page.get_by_role("dialog")
                        expect(panel).to_contain_text("ne peut pas être renommé ni retiré")
                        expect(panel.get_by_role("button", name="Retirer ce style")).to_have_count(0)
                        page.keyboard.press("Escape")
                        cards.filter(has_text="Vagues bleues").click()
                        expect(panel).to_contain_text("Ambiance")
                        panel.get_by_label("Nom du style").fill("Luxe sombre")
                        panel.get_by_role("button", name="Renommer").click()
                        expect(panel.get_by_role("alert")).to_contain_text("style fourni")
                        panel.get_by_label("Nom du style").fill("Vagues du soir")
                        panel.get_by_role("button", name="Renommer").click()
                        expect(panel.get_by_role("heading", name="Vagues du soir")).to_be_visible()
                        panel.get_by_role("button", name="Retirer ce style").click()
                        expect(page.locator(".confirm")).to_contain_text("le gardent")
                        page.locator(".confirm").get_by_role("button", name="Retirer ce style").click()
                        expect(cards).to_have_count(3)
                        expect(page.locator(".nav a", has_text="Styles")).to_contain_text("3")
                        assert page.request.get(f"{ORIGIN}/api/looks").json()["items"] == []
                        assert page.request.get(f"{ORIGIN}/api/usage").json()["recorded_micros"] == 0
                        page.screenshot(path=str(OUTPUT / "styles.png"))
                        assert not errors, errors
                        (OUTPUT / "result.json").write_text(json.dumps({"ok": True, "revision": saved["revision"], "page_errors": errors}, indent=2), encoding="utf-8")
                        print("Browser smoke passed: upload, identity, lost-response replay, scene/review, price undo, keyboard, autosave/reopen/conflict copy, overflow/glyph warnings, desktop/mobile, zero spend.")
                    except Exception:
                        page.screenshot(path=str(OUTPUT / "failure.png"), full_page=True)
                        print(page.locator("body").inner_text(), flush=True)
                        print("Page errors:", errors, flush=True)
                        raise
                    finally:
                        browser.close()
            finally:
                vite.terminate()
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill()
                    vite.wait(timeout=10)
                server.should_exit = True
                thread.join(timeout=20)
                assert not thread.is_alive(), "API did not stop"


if __name__ == "__main__":
    run()
