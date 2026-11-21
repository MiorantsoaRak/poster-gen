"""Every screen of the shops' interface and of the operator's page, captured for a design review (D-POLISH-005).

Stub providers and temporary data seeded through the real screens (three posters, two shops, a bought and an offered
grant): no spend, no real env file. Build the frontend first, then from backend/:

    uv run python ../frontend/tests/design_capture.py [label]

Writes to outputs/design-capture/<label>/ (git-ignored; label defaults to « now »):
  <screen>-<width>-<theme>.png   full pages at 360, 768 and 1440 px, light and dark
  sheets/<screen>.png            one contact sheet per screen: phone light, phone dark, desktop light
  html/<screen>-<width>-<theme>.html   the signed-in page as a static snapshot (scripts removed, CSS from frontend/dist),
                                       for checkers that cannot sign in:
      impeccable detect --json outputs/design-capture/<label>/html
      node <design-taste>/scripts/inspect.mjs outputs/design-capture/<label>/html/<file>.html --app --widths 1440,390
A snapshot has no API behind it: its images are missing, and a font loaded by an absolute path is reported as absent.
Not a test: it asserts only what it needs to reach each screen. One run at a time with the smokes (ports 5173 and 8000).
"""
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright

import admin_browser as ab
import browser_smoke as smoke
import share_browser as sb
import terms_browser as tb
from affiche import shops
from affiche.db import make_engine, write_tx
from affiche.posters import credits
from affiche.posters.auth import PASSWORDS

OUT = smoke.ROOT / "outputs" / "design-capture" / (sys.argv[1] if len(sys.argv) > 1 else "now")
WIDTHS = {360: 780, 768: 1024, 1440: 900}
SNAPSHOTS = {(360, "light"), (360, "dark"), (1440, "light")}
SHOP2, SHOP2_PASSWORD = "boutiquetana", os.urandom(10).hex()
PRODUCTS = [("Casque Sony WH-CH720N noir, 289 000 Ar", "#1d1d1f", "headset"),
            ("Galaxy A15 128 Go bleu nuit, 650 000 Ar", "#23395d", "phone"),
            ("Écouteurs JBL Tune Flex blancs, 199 000 Ar", "#f2f2f2", "buds")]


def product_photo(path, colour, shape):
    photo = Image.new("RGB", (1000, 1000), "white")
    draw = ImageDraw.Draw(photo)
    if shape == "phone":
        draw.rounded_rectangle((330, 120, 670, 880), 60, fill=colour)
    elif shape == "buds":
        draw.ellipse((260, 380, 480, 600), fill=colour, outline="#999", width=8)
        draw.ellipse((520, 380, 740, 600), fill=colour, outline="#999", width=8)
    else:
        draw.arc((220, 160, 780, 720), 180, 360, fill=colour, width=60)
        draw.rounded_rectangle((180, 440, 330, 760), 50, fill=colour)
        draw.rounded_rectangle((670, 440, 820, 760), 50, fill=colour)
    photo.save(path)


def seed(browser, data):
    """An operator password, a second shop that has not accepted the conditions, two grants; then three posters made in
    the chat by the pilot shop, the first two confirmed. Returns the posters' ids."""
    with write_tx(make_engine(Path(data))) as conn:
        shops.set_operator_password(conn, PASSWORDS.hash(ab.OPERATOR))
        second = shops.create_shop(conn, SHOP2, "Boutique Tana Mobile", PASSWORDS.hash(SHOP2_PASSWORD))
        credits.grant(conn, second, 5, origin="offered", ref="welcome-2", actor="capture")
        credits.grant(conn, 1, 20, origin="bought", ref="MV-48213", actor="capture", amount_ar=40000, method="mvola")
    page = browser.new_context(viewport={"width": 1366, "height": 900}, color_scheme="light").new_page()
    page.set_default_timeout(30000)
    tb.open_atelier(page)
    sb.sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    made = []
    for number, (message, colour, shape) in enumerate(PRODUCTS):
        photo = OUT / f"product-{number}.png"
        product_photo(photo, colour, shape)
        page.goto(smoke.ORIGIN + "/#accueil")
        made.append(sb.made_in_chat(page, photo, message))
        if number < 2:
            page.get_by_role("button", name="Tout est conforme, confirmer").click()
            expect(page.get_by_role("heading", name=sb.READY)).to_be_visible()
    page.context.close()
    return made


def shoot(browser, name, url, sign_in=None, after=None):
    dist = smoke.ROOT / "frontend" / "dist"
    for width, height in WIDTHS.items():
        for scheme in ("light", "dark"):
            context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
            page = context.new_page()
            page.set_default_timeout(30000)
            if sign_in:
                sign_in(page)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            if after:
                after(page)
            time.sleep(.6)  # the last transition
            # The ambient glow is fixed to the window: a full-page picture would cut it at one window's height, a line a
            # scrolling reader never sees. For the picture only, it spans the page; removed before the snapshot.
            glow = page.add_style_tag(content="html::before { position: absolute !important; bottom: auto !important;"
                                              " height: max(100%, var(--page-h)) !important }")
            page.evaluate("document.documentElement.style.setProperty('--page-h', document.documentElement.scrollHeight + 'px')")
            page.screenshot(path=OUT / f"{name}-{width}-{scheme}.png", full_page=True)
            glow.evaluate("style => style.remove()")
            page.evaluate("document.documentElement.style.removeProperty('--page-h')")
            if (width, scheme) in SNAPSHOTS:
                relative = os.path.relpath(dist, OUT / "html") + "/"  # a file: address is not read by every checker
                html = re.sub(r"<script\b.*?</script>", "", page.content(), flags=re.S)
                html = html.replace('href="/', f'href="{relative}').replace('src="/', f'src="{relative}')
                (OUT / "html" / f"{name}-{width}-{scheme}.html").write_text(html, encoding="utf-8")
            context.close()
    print("captured", name, flush=True)


def sheets():
    for first in sorted(OUT.glob("*-360-light.png")):
        name = first.name.removesuffix("-360-light.png")
        parts = []
        for width, scheme, target in ((360, "light", 300), (360, "dark", 300), (1440, "light", 860)):
            image = Image.open(OUT / f"{name}-{width}-{scheme}.png").convert("RGB")
            image = image.crop((0, 0, image.width, min(image.height, int(image.width * 3.2))))  # a very long page is cut
            parts.append(image.resize((target, int(image.height * target / image.width))))
        sheet = Image.new("RGB", (sum(part.width for part in parts) + 40, max(part.height for part in parts) + 20), "#888")
        left = 10
        for part in parts:
            sheet.paste(part, (left, 10))
            left += part.width + 10
        sheet.save(OUT / "sheets" / f"{name}.png")


def shop_in(identifier, password):
    def go(page):
        tb.open_atelier(page)
        sb.sign_in(page, identifier, password)
    return go


def operator_in(page):
    page.goto(smoke.ORIGIN + "/admin/")
    ab.sign_in(page)
    page.wait_for_load_state("networkidle")


def run():
    for folder in (OUT, OUT / "html", OUT / "sheets"):
        folder.mkdir(parents=True, exist_ok=True)
    assert (smoke.ROOT / "frontend/dist/admin/index.html").is_file(), "build first: corepack npm@10 run build"
    with tempfile.TemporaryDirectory(prefix="affiche-design-") as data:
        server = smoke.serve(data)
        with (OUT / "preview.log").open("w") as log:
            vite = subprocess.Popen(["node", str(smoke.ROOT / "frontend/node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1",
                                     "--port", str(smoke.WEB_PORT), "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        made = seed(browser, data)
                        pilot, origin = shop_in(smoke.IDENTIFIER, smoke.PASSWORD), smoke.ORIGIN
                        shoot(browser, "client-signin", origin + "/")
                        for name, path in [("client-home", "/#accueil"), ("client-posters", "/#affiches"), ("client-credits", "/#credits"),
                                           ("client-account", "/#compte"), ("client-styles", "/#styles"), ("client-chat-new", "/#creer"),
                                           ("client-steps", "/#etapes"), ("client-final-panel", f"/#message-{made[0]}"),
                                           ("client-chat-unconfirmed", f"/#message-{made[2]}")]:
                            shoot(browser, name, origin + path, sign_in=pilot)
                        # A confirmed poster's address opens its final panel: closed, the chat behind it shows.
                        shoot(browser, "client-chat-poster", origin + f"/#message-{made[0]}", sign_in=pilot,
                              after=lambda page: page.get_by_role("button", name="Fermer", exact=True).first.click())
                        shoot(browser, "client-conditions", origin + "/#accueil", sign_in=shop_in(SHOP2, SHOP2_PASSWORD))
                        shoot(browser, "admin-signin", origin + "/admin/")
                        for name, path in [("admin-overview", "/admin/#/overview"), ("admin-shops", "/admin/#/shops"), ("admin-shop", "/admin/#/shops/1"),
                                           ("admin-money", "/admin/#/money"), ("admin-service", "/admin/#/service")]:
                            shoot(browser, name, origin + path, sign_in=operator_in)
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
    sheets()
    print(f"{len(list(OUT.glob('*-*-*.png')))} captures, {len(list((OUT / 'html').glob('*.html')))} snapshots: {OUT}")


if __name__ == "__main__":
    run()
