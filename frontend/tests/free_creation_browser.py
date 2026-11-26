"""Walk the direct composer through a confirmed download and a simulated Page publication."""
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tempfile

from PIL import Image
from playwright.sync_api import expect, sync_playwright

from affiche.db import make_engine, write_tx
from affiche.posters import credits
import browser_smoke as smoke
from share_browser import sign_in
from terms_browser import open_atelier

OUT = smoke.ROOT / "outputs/free-creation"


def file(name, colour):
    output = io.BytesIO()
    Image.new("RGB", (850, 850), colour).save(output, "PNG")
    return {"name": name, "mimeType": "image/png", "buffer": output.getvalue()}


def say(page, text):
    page.get_by_label("Votre message").fill(text)
    page.get_by_role("button", name="Envoyer").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("crédit")
    return dialog


def open_free(browser, width):
    """« Nouvelle affiche », then the third way of creating: the chat's own shell, with its welcome."""
    ctx = browser.new_context(viewport={"width": width, "height": 850}, is_mobile=width < 600,
                              has_touch=width < 600, color_scheme="dark" if width < 600 else "light")
    page = ctx.new_page()
    page.set_default_timeout(15000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_atelier(page)
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    page.goto(smoke.ORIGIN + "/#creer")
    switch = page.get_by_role("group", name="Façon de créer")
    switch.get_by_role("button", name="Libre").click()
    page.wait_for_url("**/#libre")
    expect(switch.get_by_role("button", name="Libre")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".chat .hello-q")).to_have_text("Que voulez-vous créer ?")
    expect(page.locator(".phone-bar")).to_have_count(0)  # the composer takes its place, as in Message
    return ctx, page, errors


def walk(browser, width, data):
    ctx, page, errors = open_free(browser, width)
    label = "Sans photo : écris Fety sambatra" if width < 600 else "Trois photos en diagonale, comme le modèle"
    if width > 600:
        # One picker, as in Message: three photos, then the fourth image is the style model.
        page.get_by_label("Photos à joindre").set_input_files([file("a.png", "blue"), file("b.png", "red"), file("c.png", "gray"), file("ref.png", "gold")])
        expect(page.locator(".tray .pic")).to_have_count(4)
        expect(page.locator(".tray .pic[aria-busy]")).to_have_count(0)
        expect(page.locator(".tray .pic-role.inspiration")).to_have_text("Modèle de style")
    page.get_by_label("Votre message").fill(label)
    # The identity gate hides the page while checking the session on return from the phone photo picker.
    page.evaluate("""() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: true })
      document.dispatchEvent(new Event('visibilitychange'))
    }""")
    expect(page.get_by_label("Votre message")).to_be_hidden()
    page.evaluate("""() => {
      delete document.hidden
      document.dispatchEvent(new Event('visibilitychange'))
    }""")
    expect(page.get_by_label("Votre message")).to_have_value(label)
    expect(page.get_by_role("button", name="Envoyer")).to_be_enabled()
    page.screenshot(path=str(OUT / f"composer-{width}.png"))
    say(page, label).get_by_role("button", name="Lancer la génération").click()
    page.wait_for_url(re.compile("#libre-[a-f0-9-]{36}"))
    url = page.url
    page.reload()
    thread = page.get_by_role("log")
    expect(thread.get_by_text("Version 1 prête.")).to_be_visible()
    if width > 600:  # the images of the request, in its bubble, each decoded
        expect(thread.locator(".bubble.me .pic")).to_have_count(4)
        page.wait_for_function("Array.from(document.querySelectorAll('.bubble.me .pic img')).every(img => img.complete && img.naturalWidth > 0)")
    expect(page.get_by_role("button", name="Ajouter des photos")).to_have_count(1)  # a correction may carry new attachments
    say(page, "Change seulement le fond en vert.").get_by_role("button", name="Lancer la génération").click()
    expect(thread.get_by_text("Version 2 prête.")).to_be_visible()
    expect(thread.locator(".chat-poster")).to_have_count(2)
    expect(page.locator(".chat-side")).to_contain_text("Version 2 · à vérifier")
    # One review: the image, the requests in the seller's words, then the file. The download is the reviewed PNG.
    thread.get_by_role("button", name="Vérifier", exact=True).click()
    panel = page.get_by_role("dialog", name="Vérifier votre affiche")
    panel.get_by_text("Historique des demandes", exact=True).click()
    expect(panel.locator(".points li")).to_have_text([label, "Change seulement le fond en vert."])
    src = panel.locator(".shot img").get_attribute("src")
    expected = hashlib.sha256(page.request.get(smoke.ORIGIN + src).body()).digest()
    with page.expect_download() as download:
        panel.get_by_role("button", name="Confirmer et télécharger le PNG").click()
    assert hashlib.sha256(Path(download.value.path()).read_bytes()).digest() == expected
    confirmed = page.get_by_role("dialog", name="Affiche confirmée")
    expect(confirmed.get_by_role("link", name="Télécharger le PNG")).to_be_visible()
    confirmed.get_by_role("button", name="Fermer").click()
    expect(thread.locator(".chat-state.approved")).to_have_text("Confirmée")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
    page.screenshot(path=str(OUT / f"confirmed-{width}.png"))
    page.goto(smoke.ORIGIN + "/#affiches")
    page.locator(".library-item").filter(has_text=label).first.click()
    page.wait_for_url(url)
    expect(page.get_by_role("link", name="Télécharger le PNG")).to_be_visible()
    page.get_by_role("link", name="Publier sur ma Page").click()
    expect(page.get_by_role("heading", name="Publier sur Facebook", exact=True)).to_be_visible()
    if width > 600:
        page.get_by_role("button", name="Connecter ma Page Facebook").click()
        card = page.get_by_role("region", name="Page Facebook", exact=True)
        card.get_by_role("radio", name="Page d’essai 1").check()
        card.get_by_role("button", name="Connecter cette Page").click()
        page.get_by_label("Description de la publication").fill("Création libre de démonstration")
        page.get_by_role("button", name="Publier…", exact=True).click()
        sheet = page.get_by_role("dialog", name=re.compile("^Publier sur"))
        sheet.get_by_role("button", name="Publier", exact=True).click()
        expect(page.get_by_role("region", name="Résultat de la publication")).to_contain_text("Publié sur Page d’essai 1.", timeout=20000)
    else:
        engine = make_engine(Path(data))
        try:
            with write_tx(engine) as conn:
                credits.correct(conn, 1, -credits.balance(conn, 1)["available"], ref="free-smoke", note="Test épuisé", actor="test")
        finally:
            engine.dispose()
        page.goto(url)
        dialog = say(page, "Encore une retouche")
        expect(dialog).to_contain_text("Il ne vous reste plus de crédit")
        expect(dialog.get_by_role("button", name="Lancer la génération")).to_have_count(0)
        dialog.get_by_role("button", name="Fermer").click()
        expect(page.get_by_role("link", name="Télécharger le PNG")).to_be_visible()
        # « Nouvelle affiche » opens the way last used; another way chosen is remembered in its turn.
        page.goto(smoke.ORIGIN + "/#creer")
        page.wait_for_url("**/#libre")
        page.get_by_role("group", name="Façon de créer").get_by_role("button", name="Pas à pas").tap()
        page.wait_for_url("**/#etapes")
        page.goto(smoke.ORIGIN + "/#creer")
        page.wait_for_url("**/#libre")
    assert not errors, errors
    ctx.close()


def walk_failed(browser):
    """An image the service refuses: the sentence every other image of the app has, the credit back, « Réessayer »."""
    ctx, page, errors = open_free(browser, 390)
    before = page.request.get(smoke.ORIGIN + "/api/balance").json()["available"]
    say(page, "Une affiche de fête").get_by_role("button", name="Lancer la génération").click()
    answer = page.get_by_role("log").locator(".bubble.bot").last
    expect(answer).to_contain_text("Le service d’images a refusé cette demande")
    expect(answer).to_contain_text("Votre crédit vous a été rendu.")
    expect(answer).not_to_contain_text("code")
    assert page.request.get(smoke.ORIGIN + "/api/balance").json()["available"] == before
    page.reload()
    expect(answer).to_contain_text("Votre crédit vous a été rendu.")
    answer.get_by_role("button", name="Réessayer").click()
    expect(page.get_by_role("dialog")).to_contain_text("1 crédit")
    page.get_by_role("dialog").get_by_role("button", name="Lancer la génération").click()
    expect(page.get_by_role("log").locator(".bubble.me")).to_have_count(2)
    expect(answer).to_contain_text("Votre crédit vous a été rendu.")
    state = page.request.get(smoke.ORIGIN + '/api/free-creations/' + page.url.split('#libre-')[1]).json()
    assert len(state['turns']) == 2 and state['turns'][0]['context'] == state['turns'][1]['context']
    assert page.request.get(smoke.ORIGIN + "/api/balance").json()["available"] == before
    page.screenshot(path=str(OUT / "failed-390.png"))
    assert not errors, errors
    ctx.close()


def run(widths=(1366, 390)):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "browser.log").open("w") as log:
        vite = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1",
                                 "--port", str(smoke.WEB_PORT), "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                with tempfile.TemporaryDirectory() as data:
                    server = smoke.serve(data, facebook_provider="stub")
                    try:
                        for width in widths:
                            print(f'Browser walk: {width}px', flush=True)
                            walk(browser, width, data)
                    finally:
                        smoke.stop(*server)
                with tempfile.TemporaryDirectory() as data:  # every image refused by the service
                    server = smoke.serve(data, stub_fail="refused")
                    try:
                        walk_failed(browser)
                    finally:
                        smoke.stop(*server)
                browser.close()
        finally:
            vite.terminate()
            vite.wait(timeout=10)
    print(f"Free creation passed at {widths}, including a refused image")


if __name__ == "__main__":
    run()
