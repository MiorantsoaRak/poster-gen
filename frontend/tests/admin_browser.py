"""The operator's page (T-ADMIN-005) in real Chromium: the production build (vite preview, so build first) and the API on
temporary stub data, no real env file, no paid call. Run from backend: uv run python ../frontend/tests/admin_browser.py"""
import json
import math
import os
import re
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from sqlalchemy import text

import browser_smoke as smoke
from affiche import shops
from affiche.config import Settings
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import credits
from affiche.posters.auth import PASSWORDS, token_hash

OUTPUT = smoke.ROOT / "outputs" / "admin-browser"
ADMIN = f"{smoke.ORIGIN}/admin/"
OPERATOR = os.urandom(13).hex()  # a throwaway operator password per run, against temporary stub data
# The worst values the fields accept (D-ADMIN-005 « At 360 px »): an identifier of 32 letters, a name of 160, unbroken.
WIDE_ID, WIDE_NAME = "w" * 32, "N" * 160
WIDE_REFUSAL = "R" * 300
NO_SIDEWAYS = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
# Every visible control a finger can reach, under 44 × 44 px.
SMALL_TARGETS_JS = r"""() => [...document.querySelectorAll('button, a[href], input, select, textarea, summary')]
  .filter(e => e.checkVisibility({ visibilityProperty: true }))
  .map(e => [e, e.getBoundingClientRect()]).filter(([, box]) => box.width < 44 || box.height < 44)
  .map(([e, box]) => `${Math.round(box.width)} x ${Math.round(box.height)} <${e.tagName.toLowerCase()}> ${(e.textContent || e.id).trim().slice(0, 40)}`)"""
STORED_JS = "JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])"
# Money (T-ADMIN-006): the widest values the fields accept, unbroken; the kept request's key and the page's sentences.
REF100, METHOD40, NOTE500 = "R" * 100, "M" * 40, "n" * 500
PENDING_JS = ("JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.startsWith('affiche.admin.pending.'))"
              ".map(([key, value]) => [key.slice(22), JSON.parse(value)])))")
UNCERTAIN = "It may have been recorded: the history is read again below. Sending the same request again is safe: it is written once."
CAP_WARNING = "Warning: the outstanding credits would cost more than what is left of the cap. Raise SPEND_CAP_USD (deploy/README.md)."
OFFERED_REF = re.compile(r"^offered-\d{8}-\d{6}-[a-z2-9]{6}$")
APOSTROPHE = "’"
# Service (T-ADMIN-007): the longest purchase text, unbroken, with markup that must stay text; a browser name of 200
# characters, the most an operator session keeps.
TEXT500 = "<b>Pack</b> " + "W" * 488
LONG_AGENT = "Mozilla/5.0 (Linux; Android 14) " + "X" * 168


def wait_for(page, url):
    for attempt in range(40):
        try:
            page.goto(url)
            return
        except Exception:
            if attempt == 39:
                raise
            time.sleep(.2)


def password_field(page):
    return page.get_by_label("Operator password", exact=True)


def sign_in(page, password=OPERATOR):
    field = password_field(page)
    expect(field).to_be_enabled()
    field.fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()


def shop_api(playwright):
    """A shop's own client, to prove a password the page showed: the shops' sign-in, as their page sends it."""
    return playwright.request.new_context(base_url=smoke.ORIGIN, extra_http_headers={"Origin": smoke.ORIGIN, "X-Affiche-Bundle": str(smoke.BUNDLE)})


def shop_signs_in(api, identifier, password):
    return api.post("/api/session", data={"identifier": identifier, "password": password}).status


def ask(page, opener, title, action):
    """Opens a confirmation and checks it as the operator meets it: an alertdialog named and described, Cancel first."""
    opener.click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_have_accessible_name(title)
    expect(dialog).to_have_accessible_description(re.compile(r"\S"))
    expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_focused()
    return dialog, dialog.get_by_role("button", name=action, exact=True)


def new_shop_form(page):
    """Opens the « New shop » window when it is closed, by the Shops page's button (not the sidebar's link)."""
    if not page.locator("dialog.new-shop").evaluate("e => e.open"):
        page.locator("main").get_by_role("button", name="New shop", exact=True).click()
    expect(page.get_by_role("dialog", name="New shop")).to_be_visible()


def wait_until(page, ready):
    """Lets the route handlers run (they run during Playwright calls) until `ready()` holds."""
    for _ in range(100):
        if ready():
            return
        page.wait_for_timeout(50)
    raise AssertionError("never ready")


# Every visible field under 16 px: a phone zooms into it (D-ADMIN-005, « At 360 px »).
SMALL_FIELDS_JS = r"""() => [...document.querySelectorAll('input, select, textarea')].filter(e => e.checkVisibility({ visibilityProperty: true }))
  .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16)
  .map(e => `${getComputedStyle(e).fontSize} <${e.tagName.toLowerCase()}> ${e.id || e.name || e.placeholder}`)"""


def check_layout(page, where):
    page.wait_for_function(NO_SIDEWAYS)
    small = page.evaluate(SMALL_TARGETS_JS)
    assert not small, f"targets under 44 px on {where}:\n" + "\n".join(small)
    small = page.evaluate(SMALL_FIELDS_JS)
    assert not small, f"fields under 16 px on {where}:\n" + "\n".join(small)
    smoke.check_contrast(page, where)


# The console's paint as the browser computes it (D-REDESIGN-001, D-REDESIGN-005): the ground; and, named per screen, the
# surface and the main action that screen holds, so that another element of the page cannot answer for them.
GROUND = {"light": "rgb(245, 241, 232)", "dark": "rgb(32, 32, 29)"}
SURFACE = {"light": "rgb(255, 253, 248)", "dark": "rgb(43, 43, 39)"}
SIGNAL = ["rgb(242, 199, 68)", "rgb(32, 32, 29)"]  # the main action's fill and text, in both themes
# The top bar's glass, painted by its ::before: the one glass (--glass-strong), whose contrast brand.test.ts computes.
GLASS = {"light": "rgba(255, 253, 248, 0.86)", "dark": "rgba(43, 43, 39, 0.88)"}
BAR_GLASS_JS = "getComputedStyle(document.querySelector('header.bar'), '::before').backgroundColor"
PAINT_JS = r"""([surface, primary]) => {
  const paint = selector => {
    const e = selector && [...document.querySelectorAll(selector)].find(e => e.checkVisibility({ visibilityProperty: true }))
    return e ? [getComputedStyle(e).backgroundColor, getComputedStyle(e).color] : null
  }
  return { ground: getComputedStyle(document.body).backgroundColor, surface: paint(surface), primary: paint(primary) }
}"""


def paint(page, surface=None, primary=None):
    page.mouse.move(0, 0)  # no hovered control: a hover changes a fill
    page.wait_for_function(smoke.SETTLED, polling=100)
    return page.evaluate(PAINT_JS, [surface, primary])


def emulate(page, scheme):
    """The device's scheme, nothing stored: the page follows it, in its computed ground."""
    page.emulate_media(color_scheme=scheme)
    seen = paint(page)
    assert seen["ground"] == GROUND[scheme], (scheme, seen)


def go(page, name):
    """A destination of the sidebar, through the drawer at 1180 px and under."""
    menu = page.get_by_role("button", name="Open the menu", exact=True)
    if menu.is_visible():
        menu.click()
    page.locator("aside.side").get_by_role("link", name=name, exact=True).click()


def tab_to(page, target, back=False):
    """Keyboard only: Tab (or Shift+Tab) until `target` has the focus; it must be reachable that way."""
    for _ in range(60):
        if target.evaluate("e => e === document.activeElement"):
            outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
            assert outline != "none", f"no visible focus on {target}"
            return
        page.keyboard.press("Shift+Tab" if back else "Tab")
    raise AssertionError(f"not reachable with the keyboard: {target}")


def walk(browser, playwright, engine, errors):
    context = browser.new_context(viewport={"width": 360, "height": 640}, is_mobile=True, has_touch=True, color_scheme="light",
                                  permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    console, requested, writes = [], [], []
    page.on("console", lambda message: console.append(message.text))
    page.on("request", lambda request: requested.append(request.url))
    page.on("request", lambda request: writes.append((request.method, request.url.split("/api/admin/")[-1]))
            if "/api/admin/" in request.url and request.method != "GET" else None)
    api = shop_api(playwright)
    try:
        # No operator password yet: the page names the command, and a sign-in is refused with it.
        wait_for(page, ADMIN)
        expect(page.get_by_text("No operator password is set. On the server run: python -m affiche.shops operator-password")).to_be_visible()
        field = password_field(page)
        expect(field).to_have_attribute("autocomplete", "current-password")
        expect(field).to_have_attribute("type", "password")
        expect(page.locator("input[autocomplete=username]")).to_have_value("operator")
        sign_in(page, "anything at all")
        expect(page.get_by_role("alert").filter(has_text="No operator password is set")).to_be_visible()
        expect(field).to_have_value("")  # the password is not kept after its request
        with write_tx(engine) as conn:
            shops.set_operator_password(conn, PASSWORDS.hash(OPERATOR))

        # Wrong passwords, then the address's limit; the field is emptied after each.
        for _ in range(5):
            sign_in(page, "wrong-" + OPERATOR)
            expect(page.get_by_role("alert").filter(has_text="Wrong password.")).to_be_visible()
            expect(field).to_have_value("")
            expect(page.get_by_role("button", name="Sign in")).to_be_enabled()
        sign_in(page)
        expect(page.get_by_role("alert").filter(has_text="Too many wrong passwords from this address. Wait 15 minutes")).to_be_visible()
        with write_tx(engine) as conn:  # the 15 minutes, passed
            conn.execute(text("DELETE FROM login_failures"))
        sign_in(page)
        # A home entry: the overview, its heading focused (D-REDESIGN-006).
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        # At 360 px the session's actor is in the drawer, with « Sign out ».
        menu = page.get_by_role("button", name="Open the menu", exact=True)
        menu.click()
        expect(page.locator("aside.side").get_by_text(re.compile(r"^dashboard:[0-9a-f]{8}$"))).to_be_visible()
        page.keyboard.press("Escape")
        expect(menu).to_be_focused()
        go(page, "Shops")
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_focused()
        expect(page.get_by_role("link", name=smoke.IDENTIFIER, exact=True)).to_be_visible()

        # A shop with the widest values, its password shown once and copied. « New shop » is a window: a modal dialog
        # with its first field focused; created, it closes and the password takes the focus.
        page.locator("main").get_by_role("button", name="New shop", exact=True).click()
        expect(page.get_by_role("dialog", name="New shop")).to_be_visible()
        expect(page.get_by_label("Identifier", exact=True)).to_be_focused()
        page.get_by_label("Identifier", exact=True).fill(WIDE_ID)
        page.get_by_label("Name (optional)", exact=True).fill(WIDE_NAME)
        expect(page.get_by_label("Welcome credits", exact=True)).to_have_value("5")
        page.get_by_role("button", name="Create the shop", exact=True).click()
        panel = page.locator(".shown")
        expect(panel).to_contain_text(f"Password for {WIDE_ID}, shown once:")
        expect(panel).to_contain_text("It will not be shown again. Give it to the owner in person.")
        expect(panel).to_be_focused()
        first = panel.locator(".secret").inner_text()
        assert re.fullmatch(r"[a-z2-9]{12}", first), first
        assert page.content().count(first) == 1  # in one place only
        panel.get_by_role("button", name="Copy", exact=True).click()
        expect(panel.get_by_role("status")).to_have_text("Copied.")
        assert page.evaluate("navigator.clipboard.readText()") == first
        assert shop_signs_in(api, WIDE_ID, first) == 200  # the shop signs in at once
        row = page.locator("tr", has=page.get_by_role("link", name=WIDE_ID, exact=True))
        expect(row.locator("td.shop small")).to_have_text(WIDE_NAME)  # the name under the identifier, on a 360 px card
        expect(row.locator(".badge")).to_have_text(["active"])
        expect(row.locator("td[data-label=Available]")).to_have_text("5")
        expect(row.locator("td[data-label=Sessions]")).to_have_text("0")  # read at its creation: no polling (D-ADMIN-005)
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"the shop list at 360 px, {scheme}, a password shown")
            page.screenshot(path=str(OUTPUT / f"shops-360-{scheme}.png"), full_page=True)
        panel.get_by_role("button", name="Close", exact=True).click()
        expect(panel).to_have_count(0)
        assert first not in page.content() and first not in page.url and first not in page.evaluate(STORED_JS)

        # One shop: its line, then Access with each action behind the confirmation.
        page.get_by_role("link", name=WIDE_ID, exact=True).click()
        expect(page.get_by_role("heading", name=WIDE_ID, level=1)).to_be_focused()
        expect(page.get_by_text(WIDE_NAME, exact=True)).to_be_visible()
        expect(page.get_by_text("active · 1 live session", exact=True)).to_be_visible()
        expect(page.locator(".shop-head dt")).to_have_text(["Available", "En attente"])
        expect(page.locator(".shop-head dd")).to_have_text(["5", "0"])
        expect(page.get_by_text("Provider spend: $0.00 of $2.00", exact=True)).to_be_visible()
        expect(page.get_by_text("Messages read: 0 of 100", exact=True)).to_be_visible()
        page.get_by_text("Access", exact=True).click()

        dialog, confirm = ask(page, page.get_by_role("button", name="Set a new password", exact=True), "Set a new password?", "Set a new password")
        expect(dialog).to_have_accessible_description(f"A new password for {WIDE_ID}. Its 1 session ends.")
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            page.wait_for_function(NO_SIDEWAYS)
            for button in (dialog.get_by_role("button", name="Cancel"), confirm):
                expect(button).to_be_in_viewport(ratio=1)
            page.screenshot(path=str(OUTPUT / f"confirm-360-{scheme}.png"))
        confirm.click()
        expect(page.get_by_role("status").filter(has_text="New password set; 1 session ended.")).to_be_visible()
        second = panel.locator(".secret").inner_text()
        assert second != first and page.content().count(second) == 1
        assert shop_signs_in(api, WIDE_ID, first) == 401 and shop_signs_in(api, WIDE_ID, second) == 200
        panel.get_by_role("button", name="Close", exact=True).click()
        assert second not in page.content()

        # The shop signed in after the page read it: the page reads it again when the tab comes back (no polling).
        expect(page.get_by_text("active · 0 live sessions", exact=True)).to_be_visible()
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        expect(page.get_by_text("active · 1 live session", exact=True)).to_be_visible()
        dialog, confirm = ask(page, page.get_by_role("button", name="End its sessions", exact=True), "End its sessions?", "End its sessions")
        confirm.click()
        expect(page.get_by_role("status").filter(has_text="1 session ended.")).to_be_visible()
        expect(page.get_by_text("active · 0 live sessions", exact=True)).to_be_visible()

        # Suspend: Esc and Cancel close it with nothing sent, focus back on the button; then the action, once.
        suspend = page.get_by_role("button", name="Suspend", exact=True)
        dialog, confirm = ask(page, suspend, "Suspend this shop?", "Suspend")
        expect(dialog).to_have_accessible_description(f"{WIDE_ID} cannot sign in. Its sessions stop working. Its queued images are cancelled and their credits come back. An image being made finishes.")
        page.keyboard.press("Escape")
        expect(dialog).to_be_hidden()
        expect(suspend).to_be_focused()
        dialog, confirm = ask(page, suspend, "Suspend this shop?", "Suspend")
        dialog.get_by_role("button", name="Cancel", exact=True).click()
        expect(dialog).to_be_hidden()
        expect(suspend).to_be_focused()
        dialog, confirm = ask(page, suspend, "Suspend this shop?", "Suspend")
        confirm.click()
        expect(page.get_by_role("status").filter(has_text="Suspended; 0 queued images cancelled, credits back.")).to_be_visible()
        expect(page.get_by_text("suspended · 0 live sessions", exact=True)).to_be_visible()
        enable = page.get_by_role("button", name="Enable", exact=True)
        expect(enable).to_be_focused()  # the same control, now « Enable »
        assert shop_signs_in(api, WIDE_ID, second) == 403
        dialog, confirm = ask(page, enable, "Enable this shop?", "Enable")
        confirm.click()
        expect(page.get_by_role("status").filter(has_text="Enabled.")).to_be_visible()
        expect(page.get_by_text("active · 0 live sessions", exact=True)).to_be_visible()
        assert [method for method, path in writes if path.endswith(("/suspend", "/enable"))] == ["POST", "POST"], writes  # once each
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"one shop at 360 px, {scheme}")
            page.screenshot(path=str(OUTPUT / f"shop-360-{scheme}.png"), full_page=True)

        # An answer that arrives once the operator moved to another shop stays with its own shop (review r1 #4).
        held = []
        page.route("**/api/admin/shops/*/suspend", lambda route: held.append((route, route.fetch())))
        dialog, confirm = ask(page, page.get_by_role("button", name="Suspend", exact=True), "Suspend this shop?", "Suspend")
        confirm.click()
        wait_until(page, lambda: held)
        page.get_by_role("link", name="← Shops", exact=True).click()
        page.get_by_role("link", name=smoke.IDENTIFIER, exact=True).click()
        expect(page.get_by_role("heading", name=smoke.IDENTIFIER, level=1)).to_be_focused()
        page.get_by_text("Access", exact=True).click()
        route, response = held.pop()
        route.fulfill(response=response)
        expect(page.get_by_role("button", name="Suspend", exact=True)).to_be_enabled()  # the answer came: nothing in flight
        access = page.locator("details.fold", has=page.locator("summary", has_text="Access"))
        expect(access.locator("[role=status]")).to_have_text("")
        expect(access.locator("[role=alert]")).to_have_text("")
        page.unroute("**/api/admin/shops/*/suspend")
        page.get_by_role("link", name="← Shops", exact=True).click()
        page.get_by_role("link", name=WIDE_ID, exact=True).click()
        expect(page.get_by_text("suspended · 0 live sessions", exact=True)).to_be_visible()
        page.get_by_text("Access", exact=True).click()
        expect(page.get_by_role("status").filter(has_text="Suspended; 0 queued images cancelled, credits back.")).to_be_visible()

        # A long refusal under the form, both themes, no sideways scroll.
        page.get_by_role("link", name="← Shops", exact=True).click()
        def refuse(route):
            if route.request.method != "POST":
                return route.fallback()
            route.fulfill(status=409, json={"error": {"code": "operator_refused", "message_fr": "Refusé : rien n’a été écrit.",
                                                      "retryable": False, "detail": WIDE_REFUSAL}, "request_id": "r"})
        page.route("**/api/admin/shops", refuse)
        page.locator("main").get_by_role("button", name="New shop", exact=True).click()
        page.get_by_label("Identifier", exact=True).fill("refused")
        page.get_by_role("button", name="Create the shop", exact=True).click()
        expect(page.get_by_role("alert").filter(has_text=WIDE_REFUSAL)).to_be_visible()
        expect(page.get_by_label("Identifier", exact=True)).to_have_value("refused")  # what was typed stays
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"a 300-character refusal at 360 px, {scheme}")
        page.unroute("**/api/admin/shops", refuse)

        # An older page: nothing saved, a reload asked for, and it works.
        page.route("**/api/admin/shops", lambda route: route.fulfill(status=409, json={"error": {"code": "bundle_outdated", "message_fr": "…", "retryable": False}, "request_id": "r"})
                   if route.request.method == "POST" else route.fallback())
        page.get_by_role("button", name="Create the shop", exact=True).click()
        banner = page.locator(".banner")
        expect(banner).to_have_role("alert")
        expect(banner).to_contain_text("This page is out of date: nothing was saved.")
        expect(banner).to_be_visible()
        page.unroute("**/api/admin/shops")
        banner.get_by_role("button", name="Reload", exact=True).click()
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()
        expect(banner).to_have_count(0)

        # The session ended from the command line while a new password is shown: the next request shows the sign-in
        # form; the password is gone for good (review r1 #1), what was typed (no secret) stays.
        new_shop_form(page)
        page.get_by_label("Identifier", exact=True).fill("boutiquedeux")
        page.get_by_label("Name (optional)", exact=True).fill("Boutique Deux")
        page.get_by_role("button", name="Create the shop", exact=True).click()
        expect(panel).to_contain_text("Password for boutiquedeux, shown once:")
        third = panel.locator(".secret").inner_text()
        new_shop_form(page)
        page.get_by_label("Identifier", exact=True).fill("boutiquetrois")
        page.get_by_label("Name (optional)", exact=True).fill("Boutique Trois")
        with write_tx(engine) as conn:
            assert shops.end_operator_sessions(conn) == 1
        page.get_by_role("button", name="Create the shop", exact=True).click()
        signed_out_alert = page.locator("form", has=password_field(page)).get_by_role("alert")
        expect(password_field(page)).to_be_focused()
        expect(signed_out_alert).to_have_text("Your session has ended. Sign in again.")
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_hidden()
        assert third not in page.content()
        sign_in(page)
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()
        expect(page.get_by_label("Identifier", exact=True)).to_have_value("boutiquetrois")
        expect(page.get_by_label("Name (optional)", exact=True)).to_have_value("Boutique Trois")
        expect(panel).to_have_count(0)
        assert third not in page.content()
        # A confirmation open when the session ends (the tab's return reads the shop: 401): dismissed, nothing sent.
        page.get_by_role("link", name="boutiquedeux", exact=True).click()
        page.get_by_text("Access", exact=True).click()
        dialog, confirm = ask(page, page.get_by_role("button", name="Suspend", exact=True), "Suspend this shop?", "Suspend")
        with write_tx(engine) as conn:
            assert shops.end_operator_sessions(conn) == 1
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        expect(password_field(page)).to_be_focused()
        expect(dialog).to_be_hidden()
        sign_in(page)
        expect(page.get_by_text("active · 0 live sessions", exact=True)).to_be_visible()
        assert len([path for method, path in writes if path.endswith("/suspend")]) == 2, writes  # the two of the shop above
        page.get_by_role("link", name="← Shops", exact=True).click()

        # At 360 px the shops are cards that label each value: no number is pushed to the right there.
        expect(page.locator(".shops td.num").first).to_be_visible()  # the list is read again on arrival
        assert page.evaluate("[...document.querySelectorAll('.shops .num')].every(cell => getComputedStyle(cell).textAlign !== 'right')")
        # One column: each value of a card starts below the one before it; the long name wraps, nothing of it cut.
        overlaps = page.evaluate("""() => [...document.querySelectorAll('.shops tbody tr')].flatMap(row => [...row.cells].slice(1)
            .filter(cell => cell.getBoundingClientRect().top < cell.previousElementSibling.getBoundingClientRect().bottom - .5)
            .map(cell => `${row.cells[0].querySelector('a').textContent}: ${cell.dataset.label}`))""")
        assert not overlaps, overlaps
        assert page.locator(f"td.shop small[title='{WIDE_NAME}']").evaluate("e => e.scrollWidth <= e.clientWidth")
        # At 1280 px the shops are a table.
        page.set_viewport_size({"width": 1280, "height": 800})
        expect(page.get_by_role("columnheader", name="Shop", exact=True)).to_be_visible()
        check_layout(page, "the shop list at 1280 px, dark")
        # Numbers are right-aligned with tabular figures, headers and cells; the other columns are not (D-POLISH-004).
        # Each column by its position: the seven headers, then the seven cells of the first shop (the shop, its state,
        # Available, En attente, Posters, Last poster, Sessions).
        aligned = page.evaluate("""() => [...document.querySelectorAll('.shops th, .shops tbody tr:first-child td')].map(cell => {
            const style = getComputedStyle(cell)
            return [cell.cellIndex, style.textAlign === 'right' && style.fontVariantNumeric.includes('tabular-nums')] })""")
        numeric = {2, 3, 4, 6}  # Available, En attente, Posters, Sessions
        assert len(aligned) == 14 and all(right == (column in numeric) for column, right in aligned), aligned
        page.screenshot(path=str(OUTPUT / "shops-1280-dark.png"), full_page=True)

        # Sign out: back to the form, nothing shown, typed or read left behind, also through the history.
        def left_nothing(where):
            content = page.content()
            for trace in (WIDE_NAME, smoke.IDENTIFIER, "boutiquedeux", "Boutique Deux", "STALE-LIST"):
                assert trace not in content, f"{trace} still in the page {where}"
            for field in page.locator("#identifier").all():  # the new-shop form, when the address is the list's
                expect(field).to_have_value("")
        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(password_field(page)).to_be_focused()
        expect(page.locator(".shown")).to_have_count(0)
        left_nothing("after the sign-out")
        content, stored = page.content(), page.evaluate(STORED_JS)
        for secret in (OPERATOR, first, second, third):
            assert secret not in content and secret not in stored and secret not in page.url
            assert not [line for line in console if secret in line]
        page.go_back()
        expect(password_field(page)).to_be_visible()
        left_nothing("after Back")
        page.go_forward()
        left_nothing("after Forward")
        page.reload()
        expect(password_field(page)).to_be_visible()  # the cookie went with the sign-out

        # Answers that arrive after a sign-out, and after the next sign-in, land nowhere (review r1 #2).
        def late_answers(identifier, again):
            held = {}
            def hold(route):
                if route.request.method in held:
                    return route.fallback()
                response = route.fetch()
                body = response.json()
                if route.request.method == "GET":
                    body["items"][0]["name"] = "STALE-LIST"
                held[route.request.method] = (route, response, body)
            page.route("**/api/admin/shops", hold)
            page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")  # a read of the list
            new_shop_form(page)
            page.get_by_label("Identifier", exact=True).fill(identifier)
            page.get_by_role("button", name="Create the shop", exact=True).click()
            wait_until(page, lambda: len(held) == 2)
            page.keyboard.press("Escape")  # the window is modal: closed, the request still out, the page is usable again
            expect(page.locator("dialog.new-shop")).to_be_hidden()
            page.get_by_role("button", name="Sign out", exact=True).click()
            expect(password_field(page)).to_be_focused()
            if again:
                sign_in(page)
                expect(page.get_by_role("link", name=smoke.IDENTIFIER, exact=True)).to_be_visible()
            late = held["POST"][2]["password"]
            for route, response, body in held.values():
                route.fulfill(response=response, json=body)
            page.wait_for_timeout(500)  # an absence: the late answers get their chance to land
            page.unroute("**/api/admin/shops", hold)
            expect(page.locator(".shown")).to_have_count(0)
            assert late not in page.content() and "STALE-LIST" not in page.content()
            if again:
                new_shop_form(page)
                expect(page.get_by_role("button", name="Create the shop", exact=True)).to_be_enabled()
                page.keyboard.press("Escape")
            else:
                left_nothing("after late answers")
        sign_in(page)
        late_answers("boutiquequatre", again=False)
        sign_in(page)
        late_answers("boutiquecinq", again=True)

        # A sign-out the server made but whose answer is lost: the page is signed out at once (the sign-in waits), then
        # the server confirms; a second press sends nothing (review r1 #3).
        deletes = []
        def lose(route):
            if route.request.method != "DELETE":
                return route.fallback()
            route.fetch()  # the server ends the session...
            deletes.append(route)
        page.route("**/api/admin/session", lose)
        page.get_by_role("button", name="Sign out", exact=True).evaluate("button => { button.click(); button.click() }")
        wait_until(page, lambda: deletes)
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_hidden()
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_disabled()
        deletes[0].abort()  # ...and its answer never comes
        expect(signed_out_alert).to_have_text("The sign-out’s answer was lost; the server then confirmed that this browser is signed out.")
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_enabled()
        page.unroute("**/api/admin/session", lose)
        assert len(deletes) == 1
        # Lost before it reached the server: the server says signed in, the dashboard comes back read afresh.
        sign_in(page)
        page.route("**/api/admin/session", lambda route: route.abort() if route.request.method == "DELETE" else route.fallback())
        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(page.locator("header [role=alert]")).to_have_text("Not signed out. No answer from the server: the connection was lost. Try again.")
        expect(page.get_by_role("link", name=smoke.IDENTIFIER, exact=True)).to_be_visible()
        page.unroute("**/api/admin/session")
        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(password_field(page)).to_be_focused()

        # The page asked only for its own files and the operator's routes.
        own = [url for url in requested if not re.match(rf"{re.escape(smoke.ORIGIN)}/(admin/|api/admin/)", url) and url != f"{smoke.ORIGIN}/favicon.ico"]
        assert not own, own
        # Back from another page: still signed out, nothing of the session.
        page.goto(f"{smoke.ORIGIN}/")
        page.go_back()
        expect(password_field(page)).to_be_visible()
        left_nothing("back from another page")
    finally:
        api.dispose()
        context.close()


def shop_ids(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT identifier, id FROM shop_profile")).all())


def lines_of(engine, ref):
    """The credit lines written under one reference, whatever wrote them."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT id, shop_id, kind, origin, credits, amount_ar, method FROM credit_grants WHERE ref = :ref"
                                 " ORDER BY id"), {"ref": ref}).all()


def succeeded_jobs(engine, shop, count, status="succeeded"):
    """Images the shop made, written by hand as test_admin.py writes them: each took a credit and can be repaid. With
    another status, images it tried to make (« failed »: no credit taken, counted by the service's failed jobs)."""
    made, at = [], utc_now()
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT OR IGNORE INTO product_inputs VALUES (?,?,'P1','JBL','Bleu','[]','{}',NULL,?)", (f"in-{shop}", shop, at))
        for _ in range(count):
            id = str(uuid.uuid4())
            conn.exec_driver_sql("INSERT INTO creations VALUES (?,?,NULL,1,'active',?,?)", (id, shop, at, at))
            conn.exec_driver_sql("INSERT INTO creation_versions VALUES (?,1,'{}','h',?)", (id, at))
            conn.exec_driver_sql("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,input_hash,"
                                 "status,created_at,started_at,finished_at,takes_credit) VALUES (?,?,?,1,?,'background','{}','h',"
                                 "?,?,?,?,1)", (id, shop, id, f"in-{shop}", status, at, at, at))
            made.append(id)
    return made


def pending(page):
    """What the page keeps in localStorage for unresolved money requests, read as the page reads it."""
    return json.loads(page.evaluate(PENDING_JS)) or None


def open_shop(page, id, identifier):
    if page.evaluate("location.hash") == f"#/shops/{id}":
        page.evaluate("location.hash = '#/shops'")
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()
    page.evaluate(f"location.hash = '#/shops/{id}'")
    expect(page.get_by_role("heading", name=identifier, level=1)).to_be_focused()


def money_form(page, button):
    return page.locator("form", has=page.get_by_role("button", name=button, exact=True))


def unfold(page, title):
    """Opens a folded section when it is closed (a fold keeps its state across shops)."""
    fold = page.locator("details", has=page.locator("summary", has_text=title))
    if not fold.evaluate("e => e.open"):
        page.locator("summary", has_text=title).click()


def answers(page, title):
    """The (status, alert) regions under a money form: « Grant credits », « Correction » or « Move a payment »."""
    box = (page.locator("section", has=page.get_by_role("heading", name=title, exact=True)) if title == "Grant credits"
           else page.locator("details.fold", has=page.locator("summary", has_text=title)))
    return box.locator(":scope > [role=status]"), box.locator(":scope > [role=alert]")


def fill_grant(page, credits_, origin="bought", amount=None, method=None, ref=None, note=None):
    form = money_form(page, "Grant…")
    form.get_by_label("Credits", exact=True).fill(credits_)
    form.get_by_label("Bought or offered", exact=True).select_option(origin)
    if origin == "bought":
        form.get_by_label("Amount received, in ariary", exact=True).fill(amount)
        form.get_by_label("Method", exact=True).fill(method)
        form.get_by_label(f"The payment{APOSTROPHE}s reference", exact=True).fill(ref)
    elif ref is not None:
        form.get_by_label("Reference", exact=True).fill(ref)
    if note is not None:
        form.get_by_label("Note (optional)", exact=True).fill(note)
    return form


def grant(page, summary):
    """« Grant… », then the confirmation, which must say exactly `summary` (figures grouped), then « Grant »."""
    dialog, confirm = ask(page, page.get_by_role("button", name="Grant…", exact=True), "Grant credits?", "Grant")
    expect(dialog.locator("#confirm-text")).to_have_text(summary)
    return dialog, confirm


def unanswered_503(route):
    if route.request.method != "POST":
        return route.fallback()
    route.fulfill(status=503, json={"error": {"code": "storage_unavailable", "message_fr": "Stockage indisponible.", "retryable": True},
                                    "request_id": "r"})


def walk_money(browser, engine, errors):
    """T-ADMIN-006 at 360 × 640, the operator's phone on a bad connection: grants, corrections, moves and their kept
    requests (an answer lost after the commit, a 503 then a reload, a 401 mid-send, an answer dropped by a new session,
    two tabs, double taps), the comparisons of already_recorded, the history, the payments, the worst-case content."""
    context = browser.new_context(viewport={"width": 360, "height": 640}, is_mobile=True, has_touch=True, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    posts = []  # every money request that left the page: (path, body)
    money = re.compile(r"/api/admin/(shops/\d+/(grants|corrections)|payments/move)$")
    context.on("request", lambda request: posts.append((request.url.split("/api/admin/")[-1], request.post_data_json))
               if request.method == "POST" and money.search(request.url) else None)
    grants = "**/api/admin/shops/*/grants"
    ids = shop_ids(engine)
    wide, deux, pilot = ids[WIDE_ID], ids["boutiquedeux"], ids[smoke.IDENTIFIER]
    with write_tx(engine) as conn:  # a shop whose payment is partly spent, and a payment to move
        six, _ = shops.open_shop(conn, "boutiquesix", None, PASSWORDS.hash(os.urandom(8).hex()), 0, "tests")
        credits.grant(conn, six, 10, origin="bought", ref="MV-SPENT", actor="tests", amount_ar=20000, method="mvola")
        credits.grant(conn, deux, 3, origin="bought", ref="MV-MOVE", actor="tests", amount_ar=6000, method="orange")
    spent = succeeded_jobs(engine, six, 2)
    try:
        page.goto(ADMIN)
        sign_in(page)
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        go(page, "Shops")
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()

        # The grant comes first on a shop's screen, before the history and the access actions.
        open_shop(page, wide, WIDE_ID)
        tops = [page.get_by_role("heading", name=name, exact=True).bounding_box()["y"] for name in ("Grant credits", "History")]
        tops.append(page.locator("summary", has_text="Access").bounding_box()["y"])
        assert tops == sorted(tops), tops

        # A bought grant with the widest values; its answer is lost after the server wrote it, and the history read
        # that follows fails too: kept, the forms wait, « Send again » is written once and reads « as sent ».
        fill_grant(page, "10", amount="20000", method=METHOD40, ref=REF100, note=NOTE500)
        expect(money_form(page, "Grant…").get_by_label("Bought or offered", exact=True)).to_have_value("bought")
        lost, history_failed = [], []
        def lose(route):
            if route.request.method != "POST":
                return route.fallback()
            route.fetch()  # the server writes the line...
            lost.append(route.request.post_data_json)
            route.abort()  # ...and its answer never arrives
        def fail_history_once(route):
            if history_failed:
                return route.fallback()
            history_failed.append(route.request.url)
            route.abort()
        page.route(grants, lose)
        page.route("**/api/admin/shops/*/history*", fail_history_once)
        dialog, confirm = grant(page, f"Grant 10 bought credits to {WIDE_ID} ({WIDE_NAME})? 20 000 Ar by {METHOD40.lower()}, reference {REF100}.")
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            page.wait_for_function(NO_SIDEWAYS)
            for button in (dialog.get_by_role("button", name="Cancel"), confirm):
                expect(button).to_be_in_viewport(ratio=1)
            page.screenshot(path=str(OUTPUT / f"grant-confirm-360-{scheme}.png"))
        emulate(page, "light")
        # The request was frozen when « Grant… » was pressed: a change to the form behind the dialog is not sent.
        page.locator("#grant-credits").evaluate("field => { field.value = '99'; field.dispatchEvent(new Event('input')) }")
        confirm.evaluate("button => { button.click(); button.click() }")  # a double tap
        wait_until(page, lambda: lost and history_failed)
        sent = {"credits": 10, "origin": "bought", "ref": REF100, "note": NOTE500, "amount_ar": 20000, "method": METHOD40.lower()}
        assert lost == [sent], lost
        kept = page.locator(".kept")
        expect(kept).to_contain_text(f"No answer from the server: the connection was lost. {UNCERTAIN}")
        expect(kept).to_contain_text(f"Grant 10 bought credits to {WIDE_ID}")
        expect(page.locator("section", has=page.get_by_role("heading", name="History")).get_by_role("alert")).to_have_text(
            "No answer from the server: the connection was lost.")
        for button in ("Grant…", "Correct…", "Move…"):
            expect(page.get_by_role("button", name=button, exact=True)).to_have_count(0)
        expect(page.get_by_text("Waiting for the request above: send it again or discard it.")).to_have_count(3)
        held = pending(page)
        assert list(held) == [str(wide)] and held[str(wide)]["body"] == sent, held
        assert set(held[str(wide)]) == {"shop", "form", "path", "at", "body"}
        assert held[str(wide)]["path"] == f"/api/admin/shops/{wide}/grants" and held[str(wide)]["form"] == "grant"
        [written] = lines_of(engine, REF100)
        page.unroute(grants, lose)
        page.unroute("**/api/admin/shops/*/history*", fail_history_once)
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"a kept request with a 100-character reference at 360 px, {scheme}")
            page.screenshot(path=str(OUTPUT / f"kept-360-{scheme}.png"), full_page=True)
        emulate(page, "light")
        page.get_by_role("button", name="Send again", exact=True).evaluate("button => { button.click(); button.click() }")
        status, alert = answers(page, "Grant credits")
        expect(status).to_have_text(f"Already recorded as line {written.id}, as sent. Nothing more to do.")
        expect(alert).to_have_text("")
        assert len(lines_of(engine, REF100)) == 1 and len([path for path, body in posts if body.get("ref") == REF100]) == 2, posts
        assert pending(page) is None, "a resolved request left in localStorage"
        expect(kept).to_have_count(0)
        expect(money_form(page, "Grant…").get_by_label("Credits", exact=True)).to_have_value("")  # a new request now
        # The history holds the widest line; nothing scrolls sideways.
        widest = page.locator(".lines li", has_text=REF100)
        expect(widest).to_contain_text(f"+10 credits · grant bought · line {written.id}")
        expect(widest).to_contain_text(f"+20 000 Ar by {METHOD40.lower()}")
        expect(widest).to_contain_text(NOTE500)
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"the history with the widest values at 360 px, {scheme}")
            page.screenshot(path=str(OUTPUT / f"history-360-{scheme}.png"), full_page=True)
        emulate(page, "light")

        # The same reference with other credits only: no second line; the way out is a correction, never another reference.
        fill_grant(page, "7", amount="20000", method=METHOD40, ref=REF100)
        dialog, confirm = grant(page, f"Grant 7 bought credits to {WIDE_ID} ({WIDE_NAME})? 20 000 Ar by {METHOD40.lower()}, reference {REF100}.")
        confirm.click()
        expect(alert).to_have_text(f"Line {written.id} already holds this reference with other values. To change them, write a "
                                   "correction (or fix the amount). Do not use another reference.")
        # The same payment in another shop: it is recorded where it is; the way out is a move.
        open_shop(page, deux, "boutiquedeux")
        fill_grant(page, "10", amount="20000", method="mvola", ref=REF100)
        dialog, confirm = grant(page, f"Grant 10 bought credits to boutiquedeux (Boutique Deux)? 20 000 Ar by mvola, reference {REF100}.")
        confirm.click()
        expect(alert).to_have_text(f"This payment is recorded for {WIDE_ID}, line {written.id}. If it belongs here, move it.")
        assert len(lines_of(engine, REF100)) == 1 and pending(page) is None

        # A long refusal under the form, both themes.
        page.route(grants, lambda route: route.fulfill(status=409, json={"error": {"code": "operator_refused", "message_fr": "Refusé.",
                   "retryable": False, "detail": WIDE_REFUSAL}, "request_id": "r"}))
        fill_grant(page, "1", amount="1", method="cash", ref="REFUSED-1")
        dialog, confirm = grant(page, "Grant 1 bought credit to boutiquedeux (Boutique Deux)? 1 Ar by cash, reference REFUSED-1.")
        confirm.click()
        expect(alert).to_have_text(WIDE_REFUSAL)
        expect(money_form(page, "Grant…").get_by_label("Credits", exact=True)).to_have_value("1")  # what was typed stays
        assert pending(page) is None  # a refusal is definite
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"a 300-character money refusal at 360 px, {scheme}")
        emulate(page, "light")
        page.unroute(grants)

        # An offered grant answered 503, then the page reloaded: the shop's money forms reopen on the same request, no
        # new one starts, the list marks it; « Send again » writes it once, with the balance and the cap's headroom.
        fill_grant(page, "3", origin="offered")
        made = money_form(page, "Grant…").get_by_label("Reference", exact=True).input_value()
        assert OFFERED_REF.match(made), made
        page.route(grants, unanswered_503)
        dialog, confirm = grant(page, f"Grant 3 offered credits to boutiquedeux (Boutique Deux)? Reference {made}.")
        confirm.click()
        expect(kept).to_contain_text(f"The server{APOSTROPHE}s storage is busy or unavailable. {UNCERTAIN}")
        page.unroute(grants, unanswered_503)
        page.reload()
        expect(page.get_by_role("heading", name="boutiquedeux", level=1)).to_be_visible()
        expect(kept).to_contain_text(f"Grant 3 offered credits to boutiquedeux (Boutique Deux)? Reference {made}.")
        expect(kept).to_contain_text("No definite answer has reached this page. It may have been recorded. Sending the same request again is safe: it is written once.")
        expect(page.get_by_role("button", name="Grant…", exact=True)).to_have_count(0)
        assert pending(page)[str(deux)]["body"]["ref"] == made
        page.get_by_role("link", name="← Shops", exact=True).click()
        expect(page.locator("tr", has=page.get_by_role("link", name="boutiquedeux", exact=True))).to_contain_text("unresolved request")
        expect(page.locator("tr", has=page.get_by_role("link", name=WIDE_ID, exact=True))).not_to_contain_text("unresolved request")
        page.get_by_role("link", name="boutiquedeux", exact=True).click()
        page.get_by_role("button", name="Send again", exact=True).click()
        expect(status).to_contain_text("Granted: line ")
        [line] = lines_of(engine, made)
        expect(status).to_contain_text(f"Granted: line {line.id}. Balance: available ")
        expect(status).to_contain_text(re.compile(r"Service cap \$20\.00: \$\d+\.\d\d spent, \$\d+\.\d\d left\. Credits outstanding in all shops: "))
        expect(status.locator("strong")).to_have_text(CAP_WARNING)
        assert pending(page) is None and (line.shop_id, line.kind, line.origin, line.credits) == (deux, "grant", "offered", 3)

        # « Discard » warns, Esc keeps the request; confirmed, the forms start new requests again. Nothing was written.
        fill_grant(page, "2", origin="offered")
        made = money_form(page, "Grant…").get_by_label("Reference", exact=True).input_value()
        page.route(grants, unanswered_503)
        dialog, confirm = grant(page, f"Grant 2 offered credits to boutiquedeux (Boutique Deux)? Reference {made}.")
        confirm.click()
        page.unroute(grants, unanswered_503)
        discard = page.get_by_role("button", name="Discard", exact=True)
        dialog, confirm = ask(page, discard, "Discard this request?", "Discard")
        expect(dialog).to_have_accessible_description("If the first send was recorded, a new one writes a second line. Read the history first.")
        page.keyboard.press("Escape")
        expect(discard).to_be_focused()
        assert pending(page)[str(deux)]["body"]["ref"] == made
        dialog, confirm = ask(page, discard, "Discard this request?", "Discard")
        confirm.click()
        expect(kept).to_have_count(0)
        expect(page.get_by_role("button", name="Grant…", exact=True)).to_be_visible()
        assert pending(page) is None and lines_of(engine, made) == []

        # The session ended while the grant was on its way (401: nothing written): kept through the sign-in, then sent.
        fill_grant(page, "2", origin="offered")
        made = money_form(page, "Grant…").get_by_label("Reference", exact=True).input_value()
        held = []
        page.route(grants, lambda route: held.append(route))
        dialog, confirm = grant(page, f"Grant 2 offered credits to boutiquedeux (Boutique Deux)? Reference {made}.")
        confirm.click()
        wait_until(page, lambda: held)
        with write_tx(engine) as conn:
            assert shops.end_operator_sessions(conn) == 1
        held.pop().continue_()
        expect(password_field(page)).to_be_focused()
        expect(page.locator("form", has=password_field(page)).get_by_role("alert")).to_have_text("Your session has ended. Sign in again.")
        assert pending(page)[str(deux)]["body"]["ref"] == made and lines_of(engine, made) == []
        page.unroute(grants)
        sign_in(page)
        # Not a home entry: back to that shop, its heading focused, not to the overview (D-REDESIGN-006).
        expect(page.get_by_role("heading", name="boutiquedeux", level=1)).to_be_focused()
        expect(kept).to_contain_text("Not sent: your session had ended. Send it again.")
        page.get_by_role("button", name="Send again", exact=True).click()
        expect(status).to_contain_text("Granted: line ")
        assert len(lines_of(engine, made)) == 1 and pending(page) is None

        # Written, but its answer arrives after the session ended and a new one began: dropped (adminApi's epoch), the
        # request stays kept, and after the sign-in the history resolves it as recorded, once.
        fill_grant(page, "4", origin="offered")
        made = money_form(page, "Grant…").get_by_label("Reference", exact=True).input_value()
        held = []
        page.route(grants, lambda route: held.append((route, route.fetch())))
        dialog, confirm = grant(page, f"Grant 4 offered credits to boutiquedeux (Boutique Deux)? Reference {made}.")
        confirm.click()
        wait_until(page, lambda: held)
        with write_tx(engine) as conn:
            assert shops.end_operator_sessions(conn) == 1
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")  # a read: 401, a new epoch
        expect(password_field(page)).to_be_focused()
        route, response = held.pop()
        route.fulfill(response=response)
        page.wait_for_timeout(500)  # an absence: the dropped answer gets its chance to land
        assert ((pending(page) or {}).get(str(deux)) or {}).get("body", {}).get("ref") == made, "a dropped answer forgot its request"
        page.unroute(grants)
        sign_in(page)
        [line] = lines_of(engine, made)
        expect(status).to_have_text(f"Already recorded as line {line.id}, as sent. Nothing more to do.")
        assert pending(page) is None and len(lines_of(engine, made)) == 1

        # Two tabs of this browser: a request kept in one shows in the other at once and locks its forms, even under a
        # confirmation already open there (nothing is sent); sent from the second, it frees the first. A tab opened
        # later reads it at its start.
        other = context.new_page()
        other.on("pageerror", lambda error: errors.append(str(error)))
        other.goto(f"{ADMIN}#/shops/{deux}")
        expect(other.get_by_role("button", name="Grant…", exact=True)).to_be_visible()
        fill_grant(other, "6", origin="offered")
        raced = other.get_by_role("alertdialog")
        other.get_by_role("button", name="Grant…", exact=True).click()
        expect(raced).to_be_visible()
        fill_grant(page, "1", origin="offered")
        made = money_form(page, "Grant…").get_by_label("Reference", exact=True).input_value()
        page.route(grants, unanswered_503)
        dialog, confirm = grant(page, f"Grant 1 offered credit to boutiquedeux (Boutique Deux)? Reference {made}.")
        before = len(posts)
        confirm.click()
        expect(kept).to_be_visible()
        expect(other.locator(".kept")).to_contain_text(f"Reference {made}.")
        expect(other.get_by_role("button", name="Grant…", exact=True)).to_have_count(0)
        raced.get_by_role("button", name="Grant", exact=True).click()
        expect(other.locator("section", has=other.get_by_role("heading", name="Grant credits")).get_by_role("alert")).to_have_text(
            "This shop already has a request with no definite answer: nothing was sent. Send that one again or discard it first.")
        assert len(posts) == before + 1, posts[before:]  # the first tab's only
        assert pending(page)[str(deux)]["body"]["ref"] == made, "the other tab's request replaced the kept one"
        later = context.new_page()
        later.goto(f"{ADMIN}#/shops/{deux}")
        expect(later.locator(".kept")).to_contain_text(f"Reference {made}.")
        later.close()  # a tab the phone dropped
        other.get_by_role("button", name="Send again", exact=True).click()
        expect(other.locator("section", has=other.get_by_role("heading", name="Grant credits")).get_by_role("status")).to_contain_text("Granted: line ")
        expect(kept).to_have_count(0)
        expect(page.get_by_role("button", name="Grant…", exact=True)).to_be_visible()
        assert len(lines_of(engine, made)) == 1, lines_of(engine, made)
        assert pending(page) is None, "a resolved request left in localStorage"
        page.unroute(grants, unanswered_503)
        other.close()

        # A correction that would take the balance below zero: refused, nothing kept, what was typed stays.
        unfold(page, "Correction")
        form = money_form(page, "Correct…")
        form.get_by_label("Add or take back", exact=True).select_option(label="Take back")
        form.get_by_label("Credits", exact=True).fill("100000")
        form.get_by_label("Reason", exact=True).fill("too many")
        dialog, confirm = ask(page, form.get_by_role("button", name="Correct…"), "Write this correction?", "Correct")
        expect(dialog.locator("#confirm-text")).to_have_text(re.compile(r"^Take back 100\s000 credits from boutiquedeux \(Boutique Deux\)\? Reference correction-\d{8}-\d{6}-[a-z2-9]{6}\.$"))
        confirm.click()
        status_c, alert_c = answers(page, "Correction")
        expect(alert_c).to_have_text(re.compile(r"^the balance would go below zero \(available \d+\)$"))
        expect(form.get_by_label("Credits", exact=True)).to_have_value("100000")
        assert pending(page) is None

        # A move: written, then sent again from a new form: « already moved to … as sent ».
        open_shop(page, deux, "boutiquedeux")
        def move(page, ref, to, to_name):
            unfold(page, "Move a payment")
            form = money_form(page, "Move…")
            form.get_by_label(f"The payment{APOSTROPHE}s reference", exact=True).fill(ref)
            form.get_by_label("To the shop", exact=True).select_option(str(to))
            form.get_by_label("Reason", exact=True).fill("paid to the wrong shop")
            dialog, confirm = ask(page, form.get_by_role("button", name="Move…"), "Move this payment?", "Move")
            expect(dialog.locator("#confirm-text")).to_have_text(f"Move the payment {ref} from boutiquedeux (Boutique Deux) to {to_name}? "
                                                                 "Its credits and its ariary leave the first shop for the second.")
            confirm.click()
        with engine.connect() as conn:
            pilot_name = next(shop.name for shop in shops.list_shops(conn) if shop.id == pilot)
        pilot_called = f"{smoke.IDENTIFIER} ({pilot_name})" if pilot_name else smoke.IDENTIFIER
        move(page, "MV-MOVE", pilot, pilot_called)
        status_m, alert_m = answers(page, "Move a payment")
        expect(status_m).to_contain_text("Moved: line ")
        reversal, moved = lines_of(engine, "MV-MOVE")[1:]
        expect(status_m).to_contain_text(f"Moved: line {reversal.id} takes the payment back from boutiquedeux, line {moved.id} grants it to {smoke.IDENTIFIER}.")
        assert (moved.shop_id, moved.credits, moved.amount_ar) == (pilot, 3, 6000)
        move(page, "mv-move", pilot, pilot_called)
        expect(status_m).to_have_text(f"Already moved to {smoke.IDENTIFIER}, line {moved.id}, as sent.")
        assert len(lines_of(engine, "MV-MOVE")) == 3

        # A move refused because the source spent part of the payment: the right shop's grant form opens, filled with an
        # offered grant under the concession reference and no note, for the operator to read and confirm.
        open_shop(page, six, "boutiquesix")
        unfold(page, "Move a payment")
        form = money_form(page, "Move…")
        form.get_by_label(f"The payment{APOSTROPHE}s reference", exact=True).fill("MV-SPENT")
        form.get_by_label("To the shop", exact=True).select_option(str(deux))
        form.get_by_label("Reason", exact=True).fill("paid to the wrong shop")
        dialog, confirm = ask(page, form.get_by_role("button", name="Move…"), "Move this payment?", "Move")
        confirm.click()
        expect(page.get_by_role("heading", name="boutiquedeux", level=1)).to_be_focused()
        expect(alert).to_have_text("The move from boutiquesix was refused: the source shop has 8 credits left of the payment's 10: it stays "
                                   "where it is. To serve boutiquedeux anyway, the form below holds an offered grant under the reference "
                                   "MV-SPENT-geste, with no note: type the credits, read it, then grant it.", use_inner_text=True)
        form = money_form(page, "Grant…")
        expect(form.get_by_label("Bought or offered", exact=True)).to_have_value("offered")
        expect(form.get_by_label("Reference", exact=True)).to_have_value("MV-SPENT-geste")
        expect(form.get_by_label("Note (optional)", exact=True)).to_have_value("")
        expect(form.get_by_label("Credits", exact=True)).to_have_value("")
        form.get_by_label("Credits", exact=True).fill("10")
        dialog, confirm = grant(page, "Grant 10 offered credits to boutiquedeux (Boutique Deux)? Reference MV-SPENT-geste.")
        confirm.click()
        expect(status).to_contain_text("Granted: line ")
        assert [line.kind for line in lines_of(engine, "MV-SPENT")] == ["grant"]  # the payment stayed where it was

        # « Repay » on an image of the history fills the correction from its job, never typed by hand; once.
        open_shop(page, six, "boutiquesix")
        def image(id):  # an image of the history (a repayment line names its job too)
            return page.locator(".lines li", has=page.locator("code.copyable", has_text=id))
        job = image(spent[0])
        job.get_by_role("button", name="Repay", exact=True).click()
        form = money_form(page, "Correct…")
        expect(form).to_contain_text(f"Repay the job {spent[0]}: +1 credit, reference repay-{spent[0]}.")
        expect(form.get_by_label("Reason", exact=True)).to_be_focused()
        page.keyboard.type("image floue")
        dialog, confirm = ask(page, form.get_by_role("button", name="Correct…"), "Write this correction?", "Correct")
        expect(dialog.locator("#confirm-text")).to_have_text(f"Repay 1 credit to boutiquesix for the job {spent[0]}? Reference repay-{spent[0]}.")
        confirm.click()
        expect(status_c).to_contain_text("Corrected: line ")
        [repaid] = lines_of(engine, f"repay-{spent[0]}")
        expect(status_c).to_contain_text(f"Corrected: line {repaid.id}. Balance: available 9 · en attente 0.")
        expect(job).to_contain_text(f"repaid by line {repaid.id}")
        expect(job.get_by_role("button", name="Repay")).to_have_count(0)
        expect(image(spent[1]).get_by_role("button", name="Repay")).to_have_count(1)

        # The history 50 at a time, newest first; « Older » follows the cursor to the end.
        with write_tx(engine) as conn:
            for n in range(50):
                credits.grant(conn, six, 1, origin="offered", ref=f"PAGE-{n:02}", actor="tests")
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        history = page.locator(".lines li")
        expect(history.first).to_contain_text("PAGE-49")
        expect(history).to_have_count(50)
        page.get_by_role("button", name="Older", exact=True).click()
        expect(history).to_have_count(54)  # the payment, its two images and the repayment
        expect(history.last).to_contain_text("MV-SPENT")
        expect(page.get_by_role("button", name="Older", exact=True)).to_have_count(0)

        # The payments of a period: every line that carries ariary this UTC month, and the total received; an empty
        # period shows its zero.
        page.evaluate("location.hash = '#/money'")  # « Payments » now, at the same address
        expect(page.get_by_role("heading", name="Payments", level=1)).to_be_focused()
        now = datetime.now(UTC)
        first = now.date().replace(day=1)
        last = (first + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        with engine.connect() as conn:
            received = conn.execute(text("SELECT SUM(amount_ar), COUNT(*) FROM credit_grants WHERE amount_ar IS NOT NULL AND created_at >= :start"
                                         " AND created_at < :end"), {"start": first.isoformat(), "end": (last + timedelta(days=1)).isoformat()}).one()
        expect(page.get_by_label("First day (UTC)", exact=True)).to_have_value(first.isoformat())
        expect(page.get_by_label("Last day, included", exact=True)).to_have_value(last.isoformat())
        expect(page.get_by_text(re.compile(r"^Received: "))).to_have_text(f"Received: {received[0]:,} Ar".replace(",", " "))
        # A ledger: one payment a row, its values in their columns (When, Shop, Entry, Method, Reference, Credits, Amount).
        rows = page.locator(".payments tbody tr")
        expect(page.locator(".payments th")).to_have_text(["When", "Shop", "Entry", "Method", "Reference", "Credits", "Amount"])
        expect(rows).to_have_count(received[1])
        expect(rows.filter(has_text="MV-MOVE")).to_have_count(3)  # moved: +A, −A, +A, counted once
        spent = rows.filter(has_text="MV-SPENT")
        expect(spent.locator("td[data-label=Shop]")).to_have_text("boutiquesix")
        expect(spent.locator("td[data-label=Entry]")).to_contain_text("grant bought · line ")
        expect(spent.locator("td[data-label=Amount]")).to_have_text(re.compile(r"^\+20\s000\sAr$"))
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"the payments at 360 px, {scheme}")
            page.screenshot(path=str(OUTPUT / f"payments-360-{scheme}.png"), full_page=True)
        emulate(page, "light")
        page.get_by_label("First day (UTC)", exact=True).fill("2020-01-01")
        page.get_by_label("Last day, included", exact=True).fill("2020-01-31")
        page.get_by_role("button", name="Show", exact=True).click()
        expect(page.get_by_role("heading", name="Payments from 2020-01-01 to 2020-01-31")).to_be_visible()
        expect(page.get_by_text(re.compile(r"^Received: "))).to_have_text("Received: 0 Ar")
        expect(page.get_by_text("No payment in this period.", exact=True)).to_be_visible()

        # Nothing of a resolved request is left behind; nothing else was ever kept.
        assert pending(page) is None
        stored = page.evaluate(STORED_JS)
        assert OPERATOR not in stored and "affiche_operator" not in stored, stored
    finally:
        context.close()


def walk_no_storage(browser, engine, errors):
    """A browser that refuses storage (some private modes): the form says so; a kept request lives in the page alone,
    and is still sent again once."""
    context = browser.new_context(viewport={"width": 360, "height": 640}, is_mobile=True, has_touch=True)
    context.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('The operation is insecure.', 'SecurityError') } })")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    unstored = "This browser cannot keep an unanswered request across a reload."
    grants = "**/api/admin/shops/*/grants"
    try:
        page.goto(ADMIN)
        sign_in(page)
        open_shop(page, shop_ids(engine)["boutiquedeux"], "boutiquedeux")
        section = page.locator("section", has=page.get_by_role("heading", name="Grant credits"))
        expect(section).to_contain_text(unstored)
        fill_grant(page, "1", origin="offered")
        made = money_form(page, "Grant…").get_by_label("Reference", exact=True).input_value()
        page.route(grants, unanswered_503)
        dialog, confirm = grant(page, f"Grant 1 offered credit to boutiquedeux (Boutique Deux)? Reference {made}.")
        confirm.click()
        expect(page.locator(".kept")).to_contain_text(UNCERTAIN)
        expect(page.locator(".kept .note")).to_have_text(unstored)  # its own line, shown from before the request left
        page.unroute(grants, unanswered_503)
        # The theme switch and the rail work for this page alone; a navigation still finds the unanswered request.
        page.set_viewport_size({"width": 1280, "height": 800})
        side = page.locator("aside.side")
        side.get_by_role("button", name="Switch to dark theme", exact=True).click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        assert paint(page)["ground"] == GROUND["dark"]
        page.get_by_role("button", name="Collapse the menu", exact=True).click()
        expect(page.get_by_role("button", name="Expand the menu", exact=True)).to_be_visible()
        assert side.bounding_box()["width"] == 76
        side.get_by_role("link", name="Shops", exact=True).click()
        expect(page.locator("tr", has=page.get_by_role("link", name="boutiquedeux", exact=True))).to_contain_text("unresolved request")
        page.get_by_role("link", name="boutiquedeux", exact=True).click()
        expect(page.locator(".kept")).to_contain_text(UNCERTAIN)
        # « Needs you » lists it from the page's memory (storage refused it), and its line leads back to its shop.
        side.get_by_role("link", name="Overview", exact=True).click()
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        need = needs_box(page).get_by_role("link", name=re.compile("^A request with no definite answer"))
        expect(need).to_have_text("A request with no definite answer boutiquedeux")
        expect(need).to_have_attribute("href", f"#/shops/{shop_ids(engine)['boutiquedeux']}")
        need.click()
        expect(page.get_by_role("heading", name="boutiquedeux", level=1)).to_be_focused()
        expect(page.locator(".kept")).to_contain_text(UNCERTAIN)
        page.get_by_role("button", name="Expand the menu", exact=True).click()
        page.set_viewport_size({"width": 360, "height": 640})
        page.get_by_role("button", name="Send again", exact=True).click()
        expect(section.get_by_role("status")).to_contain_text("Granted: line ")
        assert len(lines_of(engine, made)) == 1
    finally:
        context.close()


def walk_keyboard(browser, errors):
    """The whole flow with the keyboard alone, at 1280 px: sign in, create a shop, its password closed, suspend with Esc
    first, enable, sign out."""
    context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(ADMIN)
        expect(password_field(page)).to_be_enabled()
        tab_to(page, password_field(page))
        page.keyboard.type(OPERATOR)
        page.keyboard.press("Enter")
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        tab_to(page, page.locator("aside.side").get_by_role("link", name="Shops", exact=True), back=True)
        page.keyboard.press("Enter")
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_focused()
        tab_to(page, page.locator("main").get_by_role("button", name="New shop", exact=True))
        page.keyboard.press("Enter")
        expect(page.get_by_label("Identifier", exact=True)).to_be_focused()  # the window's first field
        page.keyboard.type("clavier")
        page.keyboard.press("Enter")  # the form's own submission
        panel = page.locator(".shown")
        expect(panel).to_be_focused()
        tab_to(page, panel.get_by_role("button", name="Close", exact=True))
        page.keyboard.press("Enter")
        expect(panel).to_have_count(0)
        tab_to(page, page.get_by_role("link", name="clavier", exact=True))
        page.keyboard.press("Enter")
        expect(page.get_by_role("heading", name="clavier", level=1)).to_be_focused()
        tab_to(page, page.locator("summary", has_text="Access"))
        page.keyboard.press("Enter")
        suspend = page.get_by_role("button", name="Suspend", exact=True)
        tab_to(page, suspend)
        page.keyboard.press("Enter")
        dialog = page.get_by_role("alertdialog")
        cancel = dialog.get_by_role("button", name="Cancel", exact=True)
        expect(cancel).to_be_focused()
        assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"
        page.keyboard.press("Enter")  # Enter on Cancel cancels
        expect(dialog).to_be_hidden()
        expect(suspend).to_be_focused()
        page.keyboard.press("Enter")
        expect(cancel).to_be_focused()
        page.keyboard.press("Escape")
        expect(dialog).to_be_hidden()
        expect(suspend).to_be_focused()
        page.keyboard.press("Enter")
        page.keyboard.press("Tab")
        expect(dialog.get_by_role("button", name="Suspend", exact=True)).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.get_by_text("suspended · 0 live sessions", exact=True)).to_be_visible()
        enable = page.get_by_role("button", name="Enable", exact=True)
        expect(enable).to_be_focused()
        page.keyboard.press("Enter")
        page.keyboard.press("Tab")
        page.keyboard.press("Enter")
        expect(page.get_by_text("active · 0 live sessions", exact=True)).to_be_visible()

        # A grant with the keyboard alone: its fields in order, the reference made when the form opened, Cancel first in
        # the confirmation, then Grant; the answer with the cap's warning in bold.
        credits_field = page.locator("#grant-credits")
        tab_to(page, credits_field, back=True)
        page.keyboard.type("100000")
        page.keyboard.press("Tab")
        origin = page.locator("#grant-origin")
        expect(origin).to_be_focused()
        page.keyboard.press("ArrowDown")
        expect(origin).to_have_value("offered")
        page.keyboard.press("Tab")
        expect(page.locator("#grant-ref")).to_be_focused()
        expect(page.locator("#grant-ref")).to_have_value(OFFERED_REF)
        page.keyboard.press("Tab")
        page.keyboard.type("au clavier")
        tab_to(page, page.get_by_role("button", name="Grant…", exact=True))
        page.keyboard.press("Enter")
        dialog = page.get_by_role("alertdialog")
        expect(dialog).to_have_accessible_name("Grant credits?")
        expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_focused()
        page.keyboard.press("Tab")
        expect(dialog.get_by_role("button", name="Grant", exact=True)).to_be_focused()
        page.keyboard.press("Enter")
        status = page.locator("section", has=page.get_by_role("heading", name="Grant credits")).get_by_role("status")
        expect(status).to_contain_text(re.compile(r"Granted: line \d+\. Balance: available 100\s005 · en attente 0\."))  # its 5 welcome credits
        expect(status.locator("strong")).to_have_text(CAP_WARNING)
        tab_to(page, page.get_by_role("button", name="Sign out", exact=True), back=True)
        page.keyboard.press("Enter")
        expect(password_field(page)).to_be_focused()
    finally:
        context.close()


def walk_service(browser, engine, errors):
    """T-ADMIN-007 at 360 × 640, with a second device signed in: the Service screen with the worst values (a 500-character
    purchase text, a 200-character browser name), the pause (Esc and Cancel send nothing, a 503 said as unknown, a double
    tap sent once) and its end, an answer that arrives after the operator left the screen, the purchase text (shown as
    text, a blank one refused, kept across a lost session), the live operator sessions with this device marked, and « End
    all operator sessions »: both devices reach the sign-in form."""
    with write_tx(engine) as conn:  # the earlier walks' sessions: this walk counts its own two
        shops.end_operator_sessions(conn)
    mobile = {"viewport": {"width": 360, "height": 640}, "is_mobile": True, "has_touch": True}
    context, other = browser.new_context(**mobile, color_scheme="light"), browser.new_context(**mobile, user_agent=LONG_AGENT)
    page, laptop = context.new_page(), other.new_page()
    for each in (page, laptop):
        each.set_default_timeout(10000)
        each.on("pageerror", lambda error: errors.append(str(error)))
    writes, reads = [], []  # the Service screen's requests, (method, path) and reads of the service
    context.on("request", lambda request: writes.append((request.method, request.url.split("/api/admin/")[-1]))
               if "/api/admin/service/" in request.url else reads.append(1) if request.url.endswith("/api/admin/service") else None)
    try:
        wait_for(laptop, ADMIN)
        sign_in(laptop)
        expect(laptop.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        go(laptop, "Shops")
        expect(laptop.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()
        page.goto(ADMIN)
        sign_in(page)
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        go(page, "Shops")
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_focused()
        # The keyboard alone, through the drawer: at 360 px the sidebar's links are in it.
        tab_to(page, page.get_by_role("button", name="Open the menu", exact=True), back=True)
        page.keyboard.press("Enter")
        link = page.locator("aside.side").get_by_role("link", name="Service", exact=True)
        tab_to(page, link)
        page.keyboard.press("Enter")
        expect(page.get_by_role("heading", name="Service", level=1)).to_be_focused()
        expect(link).to_have_attribute("aria-current", "page")

        # What runs, the spend, the limits: the server's figures.
        with engine.connect() as conn:
            migration = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        main = page.locator("main")
        expect(main.locator("p", has_text="Version")).to_have_text(re.compile(rf"^Version dev · schema {migration} · started \d{{4}}-\d\d-\d\d \d\d:\d\d UTC$"))
        expect(main.get_by_text("Last backup: unknown", exact=True)).to_be_visible()  # the smokes' server keeps no backup
        expect(main.get_by_text(re.compile(r"^Jobs failed or interrupted in the last 24 hours: \d+$"))).to_be_visible()
        expect(main.locator("p", has_text="Service cap")).to_have_text(re.compile(r"^Service cap \$20\.00: \$\d+\.\d\d spent, \$\d+\.\d\d left\. .* Counted from 2026-11-06\.$"))
        expect(main.get_by_text("Provider spend per shop: $2.00 · messages read per shop: 100", exact=True)).to_be_visible()

        # The live operator sessions: both devices, this one marked once, the other's 200-character browser name.
        sessions = page.locator("section", has=page.get_by_role("heading", name="Operator sessions")).locator("li")
        expect(sessions).to_have_count(2)
        expect(sessions.filter(has_text="this device")).to_have_count(1)
        expect(sessions.filter(has_text=LONG_AGENT)).not_to_contain_text("this device")
        expect(sessions.filter(has_text=LONG_AGENT)).to_contain_text("Address 127.0.0.1")

        # The pause: Esc and Cancel send nothing and give the focus back; a 503 is said as unknown, never as done, and the
        # service is read again; then a double tap on « Pause » pauses once.
        state = page.locator("section", has=page.get_by_role("heading", name="New requests to the AI"))
        status, alert = state.locator("[role=status]"), state.locator("[role=alert]")
        expect(state).to_contain_text("Running: new requests reach the AI.")
        toggle = state.get_by_role("button", name="Pause new requests…", exact=True)
        tab_to(page, toggle)
        page.keyboard.press("Enter")
        dialog = page.get_by_role("alertdialog")
        expect(dialog).to_have_accessible_name("Pause new requests?")
        expect(dialog).to_have_accessible_description("No new request reaches the AI for any shop: images, styles, text proposals, "
                                                      "reading messages. What was admitted finishes. Shops can still edit and download.")
        expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_focused()
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            page.wait_for_function(NO_SIDEWAYS)
            for button in (dialog.get_by_role("button", name="Cancel"), dialog.get_by_role("button", name="Pause", exact=True)):
                expect(button).to_be_in_viewport(ratio=1)
        emulate(page, "light")
        page.keyboard.press("Escape")
        expect(dialog).to_be_hidden()
        expect(toggle).to_be_focused()
        dialog, confirm = ask(page, toggle, "Pause new requests?", "Pause")
        dialog.get_by_role("button", name="Cancel", exact=True).click()
        expect(toggle).to_be_focused()
        assert writes == [], writes
        page.route("**/api/admin/service/pause", unanswered_503)
        dialog, confirm = ask(page, toggle, "Pause new requests?", "Pause")
        before = len(reads)
        confirm.click()
        expect(alert).to_have_text(f"The server{APOSTROPHE}s storage is busy or unavailable. It may have been done. Read the state here; « Refresh » reads it again.")
        expect(status).to_have_text("")
        wait_until(page, lambda: len(reads) > before)
        expect(state).to_contain_text("Running: new requests reach the AI.")  # the server, read again, says
        page.unroute("**/api/admin/service/pause", unanswered_503)
        dialog, confirm = ask(page, toggle, "Pause new requests?", "Pause")
        before = len(writes)
        confirm.evaluate("button => { button.click(); button.click() }")
        expect(status).to_have_text("Paused.")
        expect(alert).to_have_text("")
        expect(state.locator("p").first).to_have_text(re.compile(r"^Paused since \d{4}-\d\d-\d\d \d\d:\d\d UTC: no new request reaches the AI for any shop\.$"))
        assert writes[before:] == [("POST", "service/pause")], writes[before:]
        with engine.connect() as conn:
            assert conn.execute(text("SELECT value FROM meta WHERE key='generation_paused'")).scalar() is not None
        resume = state.get_by_role("button", name="Resume", exact=True)
        expect(resume).to_be_focused()  # the same control, now « Resume »

        # Resumed, but its answer arrives once the operator is on another screen: it shows nowhere.
        held = []
        page.route("**/api/admin/service/resume", lambda route: held.append((route, route.fetch())))
        dialog, confirm = ask(page, resume, "Resume the service?", "Resume")
        expect(dialog).to_have_accessible_description("New requests reach the AI again, for every shop.")
        confirm.click()
        wait_until(page, lambda: held)
        go(page, "Shops")
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_focused()
        route, response = held.pop()
        route.fulfill(response=response)
        page.wait_for_timeout(500)  # an absence: the late answer gets its chance to land
        expect(page.get_by_text("Resumed.")).to_have_count(0)
        page.unroute("**/api/admin/service/resume")
        go(page, "Service")
        expect(state).to_contain_text("Running: new requests reach the AI.")  # read afresh
        expect(status).to_have_text("")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT value FROM meta WHERE key='generation_paused'")).scalar() is None

        # The purchase text: the fallback until one is set (French, as shops read it); a blank one refused with what was
        # typed kept; the longest, with markup, shown as text; a double tap saves once.
        section = page.locator("section", has=page.get_by_role("heading", name="Purchase text"))
        shown, said, refused = section.locator(".purchase"), section.locator("[role=status]"), section.locator("[role=alert]")
        expect(section).to_contain_text("(none set: every shop reads this fallback)")
        expect(shown).to_have_attribute("lang", "fr")
        expect(shown).to_have_text(f"Pour obtenir des crédits, contactez {smoke.SUPPORT}.")
        area = page.get_by_label("New text, 1 to 500 characters", exact=True)
        expect(area).to_have_value("")
        area.fill(" \n ")
        save = section.get_by_role("button", name="Save", exact=True)
        save.click()
        expect(refused).to_have_text("a purchase text has 1 to 500 characters")
        expect(area).to_have_value(" \n ")
        area.fill(TEXT500 + "cut")  # never cut silently: refused by the server's rule, and what was typed stays
        save.click()
        expect(refused).to_have_text("a purchase text has 1 to 500 characters")
        expect(area).to_have_value(TEXT500 + "cut")
        area.fill(TEXT500)
        before = len(writes)
        save.evaluate("button => { button.click(); button.click() }")
        expect(said).to_have_text("Saved. Every shop reads it from now on.")
        expect(refused).to_have_text("")
        expect(shown).to_have_text(TEXT500)
        expect(shown.locator("b")).to_have_count(0)  # never HTML
        expect(section).not_to_contain_text("none set")
        assert writes[before:] == [("PUT", "service/purchase-text")], writes[before:]
        with engine.connect() as conn:
            assert conn.execute(text("SELECT value FROM meta WHERE key='purchase_text_fr'")).scalar() == TEXT500
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"the Service screen at 360 px, {scheme}, a 500-character text and a 200-character browser")
            page.screenshot(path=str(OUTPUT / f"service-360-{scheme}.png"), full_page=True)
        emulate(page, "light")

        # This session ended elsewhere while a text was typed: the sign-in form, then the same screen with what was typed
        # (no secret), nothing saved.
        area.fill("Texte gardé pendant la connexion")
        token = next(cookie["value"] for cookie in context.cookies() if cookie["name"] == "affiche_operator")
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM operator_sessions WHERE token_hash=:hash"), {"hash": token_hash(token)})
        save.click()
        expect(password_field(page)).to_be_focused()
        expect(page.locator("form", has=password_field(page)).get_by_role("alert")).to_have_text("Your session has ended. Sign in again.")
        sign_in(page)
        expect(page.get_by_role("heading", name="Service", level=1)).to_be_visible()
        expect(area).to_have_value("Texte gardé pendant la connexion")
        expect(shown).to_have_text(TEXT500)

        # An older page: nothing saved, a reload asked for.
        page.route("**/api/admin/service/purchase-text", lambda route: route.fulfill(status=409, json={"error": {
            "code": "bundle_outdated", "message_fr": "…", "retryable": False}, "request_id": "r"}))
        save.click()
        expect(page.locator(".banner")).to_contain_text("This page is out of date: nothing was saved.")
        page.unroute("**/api/admin/service/purchase-text")
        page.locator(".banner").get_by_role("button", name="Reload", exact=True).click()
        expect(page.get_by_role("heading", name="Service", level=1)).to_be_visible()
        expect(sessions.filter(has_text="this device")).to_have_count(1)

        # « End all operator sessions »: this device returns to the sign-in form at once, its cookie gone, what was typed
        # dropped as at a sign-out; the other device's next request finds its session ended.
        area.fill("Brouillon abandonné")
        end_all = page.get_by_role("button", name="End all operator sessions", exact=True)
        dialog, confirm = ask(page, end_all, "End all operator sessions?", "End all")
        expect(dialog).to_have_accessible_description(f"Every operator session ends, this device{APOSTROPHE}s too. You will sign in again.")
        confirm.click()
        expect(password_field(page)).to_be_focused()
        expect(page.locator("form", has=password_field(page)).get_by_role("alert")).to_have_text(
            f"Every operator session has ended, this device{APOSTROPHE}s too. Sign in again.")
        expect(page.get_by_role("heading", name="Service", level=1)).to_be_hidden()
        assert not [cookie for cookie in context.cookies() if cookie["name"] == "affiche_operator"]
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM operator_sessions")).scalar_one() == 0
        laptop.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        expect(password_field(laptop)).to_be_focused()
        expect(laptop.locator("form", has=password_field(laptop)).get_by_role("alert")).to_have_text("Your session has ended. Sign in again.")
        sign_in(page)  # a new session: the text area holds the stored text, not what was typed before « End all »
        expect(area).to_have_value(TEXT500)
        expect(sessions).to_have_count(1)
        page.reload()
        expect(page.get_by_role("heading", name="Service", level=1)).to_be_visible()  # the new session's cookie
    finally:
        context.close()
        other.close()


# Figtree is really used: a face of that family has loaded (document.fonts.check() alone passes on a fallback).
FIGTREE_JS = "[...document.fonts].some(face => face.family.replace(/[\"']/g, '') === 'Figtree' && face.status === 'loaded')"
# The sidebar's logo as shown: its file, its intrinsic width (0 when it did not load) and its width on screen.
LOGO_JS = r"""() => [...document.querySelectorAll('aside .brand img')].filter(img => img.checkVisibility())
  .map(img => [img.getAttribute('src'), img.naturalWidth, Math.round(img.getBoundingClientRect().width)])"""
IN_DRAWER_JS = "() => [!!document.activeElement?.closest('aside.side'), document.activeElement?.outerHTML.slice(0, 80)]"
OUTDATED = {"error": {"code": "bundle_outdated", "message_fr": "…", "retryable": False}, "request_id": "r"}


def logo(page, scheme):
    """The kit's horizontal logo of the theme, loaded, at least 220 px wide; the one shown."""
    [[src, natural, width]] = page.evaluate(LOGO_JS)
    assert natural > 0 and width >= 220 and ("charcoal" if scheme == "light" else "paper") in src, (scheme, src, natural, width)


def walk_shell(browser, engine, errors):
    """T-REDESIGN-005: the sidebar's links by exact name and aria-current; every screen at 1280 and 360 px in both themes;
    Figtree and the logo of the theme at 1181 and 1440 px; the table's states, its widest cell and « Filter shops »;
    « New shop » from the sidebar; the rail; the drawer at 1024 and 360 px (focus in, Tab inside it never reaching the
    banner or a shown password, Escape, the scrim, its close button, a destination, a resize); the theme switch kept
    across the device's scheme and a reload."""
    with write_tx(engine) as conn:  # with no password: suspended, its one state is « suspended »; active, « no password »
        quiet = shops.create_shop(conn, "sanspasse", "Boutique sans mot de passe", None)
        shops.suspend(conn, quiet)
        shops.create_shop(conn, "ouverte", "Boutique ouverte", None)
    deux = shop_ids(engine)["boutiquedeux"]
    context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    reads = []
    page.on("request", lambda request: reads.append(request.url) if "/api/admin/" in request.url else None)
    side = page.locator("aside.side")
    try:
        page.goto(ADMIN)
        sign_in(page)
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        side.get_by_role("link", name="Shops", exact=True).click()
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_focused()

        # Figtree, really: its face loaded, and a button's family starts with it.
        page.wait_for_function(FIGTREE_JS)
        family = side.get_by_role("button", name="Sign out", exact=True).evaluate("e => getComputedStyle(e).fontFamily")
        assert family.startswith("Figtree"), family
        # The logo of the theme over 1180 px, and no name typed beside it.
        for width in (1181, 1440):
            page.set_viewport_size({"width": width, "height": 800})
            for scheme in ("light", "dark"):
                emulate(page, scheme)
                logo(page, scheme)
        expect(side.get_by_text("Doka Studio")).to_have_count(0)

        # The sidebar's links by their exact names; each destination is the current page and takes the focus.
        page.set_viewport_size({"width": 1280, "height": 800})
        emulate(page, "light")
        expect(side.get_by_role("link")).to_have_count(6)
        for name in ("Doka Studio — Overview", "New shop", "Overview", "Shops", "Payments", "Service"):
            expect(side.get_by_role("link", name=name, exact=True)).to_be_visible()
        expect(side.get_by_role("navigation", name="Console", exact=True).get_by_role("link")).to_have_text(["Overview", "Shops", "Payments", "Service"])
        for name, address in (("Payments", "#/money"), ("Service", "#/service"), ("Overview", "#/overview"), ("Shops", "#/shops")):
            link = side.get_by_role("link", name=name, exact=True)
            link.click()
            expect(page.get_by_role("heading", name=name, level=1)).to_be_focused()
            assert page.evaluate("location.hash") == address
            expect(link).to_have_attribute("aria-current", "page")
            expect(side.locator("[aria-current]")).to_have_count(1)

        # Every screen at 1280 and 360 px, in both themes, nothing stored: the device decides. Each screen's own surface
        # and main action are read: the table (a card per shop on a phone), a section, the period's form; on Shops the
        # sidebar's « New shop » where it shows, and none on a phone.
        screens = (("#/overview", "Overview", page.locator("main .kpis .value").first, ("main .kpi",) * 2, (None, None)),
                   ("#/shops", "Shops", page.locator(".shops"), (".table-card", ".shops tbody tr"), ("aside .new", None)),
                   (f"#/shops/{deux}", "boutiquedeux", page.get_by_role("heading", name="History"), ("main section.card",) * 2, ("main button.primary",) * 2),
                   ("#/money", "Payments", page.get_by_text(re.compile(r"^Received: ")), ("main div.card",) * 2, ("main button.primary",) * 2),
                   ("#/service", "Service", page.get_by_role("heading", name="Health"), ("main section.card",) * 2, ("main button.primary",) * 2))
        for phone, (width, height) in enumerate(((1280, 800), (360, 640))):
            page.set_viewport_size({"width": width, "height": height})
            for address, title, ready, surfaces, actions in screens:
                page.evaluate(f"location.hash = '{address}'")
                expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()
                expect(ready).to_be_visible()
                for scheme in ("light", "dark"):
                    emulate(page, scheme)
                    seen = paint(page, surfaces[phone], actions[phone])
                    assert seen["surface"] and seen["surface"][0] == SURFACE[scheme], (title, width, scheme, seen)
                    assert (seen["primary"] == SIGNAL) if actions[phone] else seen["primary"] is None, (title, width, scheme, seen)
                    assert page.evaluate(BAR_GLASS_JS) == GLASS[scheme], (title, width, scheme, page.evaluate(BAR_GLASS_JS))
                    check_layout(page, f"{title} at {width} px, {scheme}")
        emulate(page, "light")

        # The table at 1280 px: the shop's cell the widest of its row, rows of one height with the longest identifier and
        # name the fields accept; one state per shop, exactly the right one.
        page.set_viewport_size({"width": 1280, "height": 800})
        page.evaluate("location.hash = '#/shops'")
        rows = page.locator(".shops tbody tr")
        total = len(shop_ids(engine))
        expect(rows).to_have_count(total)
        boxes = page.evaluate("() => [...document.querySelectorAll('.shops tbody tr')].map(row => [row.getBoundingClientRect().height, ...[...row.cells].map(cell => cell.getBoundingClientRect().width)])")
        assert all(row[1] == max(row[1:]) for row in boxes), boxes
        heights = [row[0] for row in boxes]
        assert max(heights) - min(heights) < 1, heights
        expect(page.get_by_role("link", name=WIDE_ID, exact=True)).to_have_attribute("title", WIDE_ID)
        expect(page.locator("td.shop small", has_text=WIDE_NAME)).to_have_attribute("title", WIDE_NAME)
        with engine.connect() as conn:
            states = {shop.identifier: "suspended" if shop.state == "suspended" else "active" if shop.has_password else "no password"
                      for shop in shops.list_shops(conn)}
        assert set(states.values()) == {"suspended", "no password", "active"}, states
        for identifier, word in states.items():
            expect(page.locator("tr", has=page.get_by_role("link", name=identifier, exact=True)).locator(".badge")).to_have_text([word])

        # « Filter shops »: on the page, no request; by identifier and by name, in any case; none; cleared.
        field = page.get_by_label("Filter shops", exact=True)
        before = len(reads)
        field.fill("QUEDEUX")  # in the identifier boutiquedeux, not in its name « Boutique Deux »
        expect(rows).to_have_count(1)
        expect(rows.get_by_role("link")).to_have_text("boutiquedeux")
        field.fill("sans mot")  # in the name only
        expect(rows).to_have_count(1)
        expect(rows.get_by_role("link")).to_have_text("sanspasse")
        field.fill("no such shop")
        expect(rows).to_have_count(0)
        expect(page.get_by_text("No shop matches.", exact=True)).to_be_visible()
        field.fill("")
        expect(rows).to_have_count(total)
        assert len(reads) == before, reads[before:]

        # « New shop » in the sidebar: the list, its window open over it, its first field focused; also when already on
        # Shops. Esc closes the window and the page behind it is usable again.
        new = side.get_by_role("link", name="New shop", exact=True)
        window = page.locator("dialog.new-shop")
        page.evaluate("location.hash = '#/money'")
        expect(page.get_by_role("heading", name="Payments", level=1)).to_be_focused()
        new.click()
        expect(page.get_by_label("Identifier", exact=True)).to_be_focused()
        assert page.evaluate("location.hash") == "#/shops" and window.evaluate("e => e.open && e.matches(':modal')")
        page.keyboard.press("Escape")
        expect(window).to_be_hidden()
        new.click()
        expect(page.get_by_label("Identifier", exact=True)).to_be_focused()
        assert window.evaluate("e => e.open")
        window.get_by_role("button", name="Cancel", exact=True).click()
        expect(window).to_be_hidden()

        # The rail, by one button: 76 px, every link keeps its name, the D alone; in memory only, so a reload undoes it.
        page.get_by_role("button", name="Collapse the menu", exact=True).click()
        expect(page.get_by_role("button", name="Expand the menu", exact=True)).to_be_visible()
        assert side.bounding_box()["width"] == 76
        for name in ("New shop", "Overview", "Shops", "Payments", "Service"):
            expect(side.get_by_role("link", name=name, exact=True)).to_be_visible()
        for name in ("Switch to dark theme", "Sign out"):
            expect(side.get_by_role("button", name=name, exact=True)).to_be_visible()
        [[_, natural, width]] = page.evaluate(LOGO_JS)
        assert natural > 0 and width == 40, (natural, width)
        check_layout(page, "the rail at 1280 px")
        page.reload()
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()
        expect(page.get_by_role("button", name="Collapse the menu", exact=True)).to_be_visible()
        assert side.bounding_box()["width"] == 288

        # The drawer at 1024 and 360 px, with a password shown once and the reload banner at the root of the page: both
        # behind the drawer, out of the keyboard's reach while it is open.
        page.set_viewport_size({"width": 1024, "height": 768})
        new_shop_form(page)
        page.get_by_label("Identifier", exact=True).fill("tiroir")
        page.get_by_role("button", name="Create the shop", exact=True).click()
        expect(page.locator(".shown")).to_be_visible()
        page.route("**/api/admin/shops", lambda route: route.fulfill(status=409, json=OUTDATED) if route.request.method == "POST" else route.fallback())
        new_shop_form(page)
        page.get_by_label("Identifier", exact=True).fill("tiroirdeux")
        page.get_by_role("button", name="Create the shop", exact=True).click()
        expect(page.locator(".banner")).to_be_visible()
        page.unroute("**/api/admin/shops")
        menu = page.get_by_role("button", name="Open the menu", exact=True)
        close = page.get_by_role("button", name="Close the menu", exact=True)
        for width, height in ((1024, 768), (360, 640)):
            page.set_viewport_size({"width": width, "height": height})
            expect(side).to_be_hidden()
            expect(menu).to_have_attribute("aria-expanded", "false")
            menu.click()
            expect(close).to_be_focused()
            expect(menu).to_have_attribute("aria-expanded", "true")
            for behind in (".banner", "header.bar", ".shown", "main"):
                expect(page.locator(behind)).to_have_attribute("inert", "")
            for key in ["Tab"] * 9 + ["Shift+Tab"] * 9:
                page.keyboard.press(key)
                inside, at = page.evaluate(IN_DRAWER_JS)
                assert inside, f"{key} left the drawer at {width} px: {at}"
            for scheme in ("light", "dark"):
                emulate(page, scheme)
                check_layout(page, f"the open drawer at {width} px, {scheme}")
            emulate(page, "light")
            page.keyboard.press("Escape")
            assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Open the menu"
            # At once, while it still slides away: the closing drawer is out of the keyboard's reach already.
            page.keyboard.press("Shift+Tab")
            inside, at = page.evaluate(IN_DRAWER_JS)
            assert not inside, f"Shift+Tab entered the closing drawer at {width} px: {at}"
            expect(side).to_be_hidden()
            # A click on the drawer's plain text leaves the focus in it: Escape still closes it.
            menu.click()
            side.locator(".section").click()
            page.keyboard.press("Escape")
            expect(menu).to_be_focused()
            expect(side).to_be_hidden()
            menu.click()
            page.locator(".scrim").click(position={"x": width - 10, "y": height - 10})
            expect(menu).to_be_focused()
            menu.click()
            close.click()
            expect(menu).to_be_focused()
            expect(page.locator("main")).not_to_have_attribute("inert", "")
            # A destination: the drawer closes and the page's h1 takes the focus.
            menu.click()
            side.get_by_role("link", name="Payments", exact=True).click()
            expect(page.get_by_role("heading", name="Payments", level=1)).to_be_focused()
            expect(side).to_be_hidden()
            page.evaluate("location.hash = '#/shops'")
            expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_focused()
            # Back with the drawer open: the drawer closes, the previous page's h1 takes the focus.
            menu.click()
            expect(close).to_be_focused()
            page.go_back()
            expect(page.get_by_role("heading", name="Payments", level=1)).to_be_focused()
            expect(page.locator(".scrim")).to_have_count(0)
            expect(side).to_be_hidden()
            page.go_forward()
            expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_focused()
        # Wider than 1180 px, an open drawer closes; the focus on « Close the menu », not shown there, goes to the rail toggle.
        page.set_viewport_size({"width": 1024, "height": 768})
        menu.click()
        expect(close).to_be_focused()
        page.set_viewport_size({"width": 1300, "height": 800})
        expect(page.locator(".scrim")).to_have_count(0)
        expect(page.locator("header.bar")).not_to_have_attribute("inert", "")
        expect(page.get_by_role("button", name="Collapse the menu", exact=True)).to_be_focused()
        page.set_viewport_size({"width": 1024, "height": 768})
        expect(side).to_be_hidden()
        page.locator(".shown").get_by_role("button", name="Close", exact=True).click()
        page.locator(".banner").get_by_role("button", name="Reload", exact=True).click()
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()

        # The theme switch, in the sidebar: the other theme, kept on this device; a change of the device's scheme and a
        # reload leave it; the logo follows it either way.
        page.set_viewport_size({"width": 1280, "height": 800})
        emulate(page, "light")
        side.get_by_role("button", name="Switch to dark theme", exact=True).click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        assert page.evaluate("localStorage.getItem('affiche.admin.theme')") == "dark"
        for device in ("dark", "light"):
            page.emulate_media(color_scheme=device)
            assert paint(page)["ground"] == GROUND["dark"], device
            logo(page, "dark")
        page.reload()
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()
        assert paint(page)["ground"] == GROUND["dark"]
        page.emulate_media(color_scheme="dark")
        side.get_by_role("button", name="Switch to light theme", exact=True).click()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        assert paint(page)["ground"] == GROUND["light"]
        logo(page, "light")
        page.reload()
        expect(page.get_by_role("heading", name="Shops", exact=True, level=1)).to_be_visible()
        assert paint(page)["ground"] == GROUND["light"] and page.evaluate("localStorage.getItem('affiche.admin.theme')") == "light"
    finally:
        context.close()


# The overview (T-REDESIGN-006): what a browser check reads of the page's formatters (no-break spaces read as spaces).
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
SERVER_ERROR = {"error": {"code": "internal_error", "message_fr": "Erreur.", "retryable": False}, "request_id": "r"}
KPI_JS = "kpis => kpis.map(kpi => { const box = kpi.getBoundingClientRect(); return [Math.round(box.top), Math.round(box.left)] })"
NEEDS_JS = r"""box => [[...box.querySelectorAll('li a')].map(a => [a.querySelector('strong').textContent, a.querySelector('small').textContent, a.getAttribute('href')]),
  [...box.querySelectorAll(':scope > p')].map(p => p.textContent)]"""


def usd(micros, up=False):
    """The page's dollars(): micro-USD to the cent, rounded as Math.round does, or up."""
    cents = math.ceil(micros / 1e4) if up else math.floor(micros / 1e4 + .5)
    return f"${cents / 100:.2f}"


def grouped(n):
    return ("−" if n < 0 else "") + f"{abs(n):,}".replace(",", " ")


def signed(n):
    return ("+" if n > 0 else "") + grouped(n)


def kpi(page, label):
    return page.locator("main .kpi", has=page.locator("dt", has_text=label))


def panel(page, title):
    """An overview's section by its own heading (the h1 of another screen never answers for it)."""
    return page.locator("main section", has=page.get_by_role("heading", name=title, exact=True, level=2))


def needs_box(page):
    return panel(page, "Needs you")


def needs(page, lines, sentences=()):
    """Waits until « Needs you » shows exactly these lines (text, detail, link) and, under them, these sentences."""
    want, seen = [[list(line) for line in lines], list(sentences)], None
    for _ in range(100):
        seen = needs_box(page).evaluate(NEEDS_JS)
        if seen == want:
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"« Needs you » shows {seen}, not {want}")


def walk_overview(browser, engine, data, errors):
    """T-REDESIGN-006 at 1280 px, on a store seeded with more than five payments this month (a moved one, an amount
    corrected down), one of the month before, offered grants, three real image costs of no round cent, a failed job,
    shops whose last posters do not follow their identifiers, no purchase text: the four figures and both lists against
    the store, and a spend over the cap and another month's negative total as told; one read of each on a sign-in; the
    request's mark among the first eight; « Needs you » with each of its six causes, removed one by one down to its empty
    sentence, the last one while the service's answer is held; a failed service read and a failed payments read;
    refreshes answered out of order, an older one's 401; the blocks' positions at 1280, 800 and 360 px; 360 px in both
    themes."""
    settings = Settings(_env_file=None, spend_cap_usd="20", spend_cap_since="2026-11-06", data_dir=data)  # as smoke.serve sets them
    ids = shop_ids(engine)
    wide, six, pilot = ids[WIDE_ID], ids["boutiquesix"], ids[smoke.IDENTIFIER]
    first = datetime.now(UTC).date().replace(day=1)
    last = (first + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    with write_tx(engine) as conn:
        credits.correct(conn, six, 0, ref="MV-SPENT", note="mistyped amount", actor="tests", amount_ar=-1000)
        # A line is never changed: one of the month before is written with its date, as a restore's copy keeps one.
        credits._line(conn, ids["boutiquedeux"], "grant", 2, "MV-BEFORE", "tests", None, origin="bought", amount_ar=4000, method="cash",
                      at=f"{first - timedelta(days=1)}T12:00:00.000000+00:00")
        credits.grant(conn, ids["ouverte"], 5, origin="bought", ref="OR-77", actor="tests", amount_ar=12500, method="orange")
        conn.execute(text("DELETE FROM meta WHERE key='purchase_text_fr'"))  # never set, as on a new server
    made = succeeded_jobs(engine, pilot, 3)
    with write_tx(engine) as conn:  # the provider's real costs of three images: their average is no round cent
        for job, cost in zip(made, (58000, 58500, 58500)):
            conn.exec_driver_sql("INSERT INTO poster_calls (id,job_id,call_no,provider,model,rate_card_json,status,cost_micros,cost_is_estimate,"
                                 "created_at) VALUES (?,?,1,'openai','gpt-image-2','{}','succeeded',?,0,?)", (str(uuid.uuid4()), job, cost, utc_now()))
    [failed] = succeeded_jobs(engine, ids["clavier"], 1, status="failed")
    # The latest posters: the widest shop's (its request's mark is then among the first eight) and the suspended shop's
    # with no password (cancelled, as a suspension cancels): one badge, and its « No password » line apart.
    succeeded_jobs(engine, wide, 1)
    succeeded_jobs(engine, ids["sanspasse"], 1, status="cancelled")

    context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    # The overview's three reads, as they leave the page: one each per arrival.
    reads = []
    page.on("request", lambda request: reads.append(request.url.rsplit("/", 1)[-1]) if re.search(r"/api/admin/(shops|service|payments)$", request.url) else None)
    side, refresh = page.locator("aside.side"), page.get_by_role("button", name="Refresh", exact=True)
    alert = page.locator("main > div.refusal[role=alert]")
    shops_box, pay_box, service_box = panel(page, "Shops"), panel(page, "Payments this month"), panel(page, "Service")
    # The smokes' server keeps no backup (unknown); a backup on time and a late one are the service's answer as told here.
    backup = {}
    def told_backup(route):
        response = route.fetch()
        route.fulfill(response=response, json={**response.json(), **backup} if backup and response.ok else response.json())
    page.route("**/api/admin/service", told_backup)
    def broken(route):
        route.fulfill(status=500, json=SERVER_ERROR)
    grants = "**/api/admin/shops/*/grants"
    def shop_row(identifier):
        return shops_box.locator("tr", has=page.get_by_role("link", name=identifier, exact=True))
    def read_once(why):
        """Every block answered, then an absence: the sign-in read each of the three once (the mount's read alone)."""
        for label in ("Active shops", "Credits outstanding", "Received in"):
            expect(kpi(page, label).locator(".value")).to_be_visible()
        page.wait_for_timeout(300)
        assert sorted(reads) == ["payments", "service", "shops"], (why, reads)
    try:
        page.goto(ADMIN)
        sign_in(page)
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        read_once("the first sign-in")
        # An unanswered request, in this page's memory.
        open_shop(page, wide, WIDE_ID)
        fill_grant(page, "1", origin="offered")
        made = money_form(page, "Grant…").get_by_label("Reference", exact=True).input_value()
        page.route(grants, unanswered_503)
        dialog, confirm = grant(page, f"Grant 1 offered credit to {WIDE_ID} ({WIDE_NAME})? Reference {made}.")
        confirm.click()
        expect(page.locator(".kept")).to_contain_text(UNCERTAIN)
        page.unroute(grants, unanswered_503)
        side.get_by_role("link", name="Overview", exact=True).click()
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        expect(side.get_by_role("link", name="Overview", exact=True)).to_have_attribute("aria-current", "page")

        # The four figures, against the store.
        with engine.connect() as conn:
            listed = shops.list_shops(conn)
            room = shops.headroom(conn, settings)
            paid = credits.payments(conn, first, last)
            posters = dict(conn.execute(text("SELECT p.identifier, (SELECT MAX(created_at) FROM creations c WHERE c.shop_id=p.id) FROM shop_profile p")).all())
        assert room["images"] == 3 and room["cost"] % 10_000 and room["warning"], room  # no round cent; the cap passed
        assert len(paid) > 5 and any(line["kind"] == "correction" and line["amount_ar"] < 0 for line in paid), paid
        expect(kpi(page, "Active shops").locator(".value")).to_have_text(f"{sum(shop.state == 'active' for shop in listed)} of {len(listed)}")
        expect(kpi(page, "Credits outstanding").locator("dd")).to_have_text(
            [grouped(room["outstanding"]), f"≈ {usd(room['cost'], up=True)} at ${room['unit'] / 1e6:.3f} an image"])
        received = kpi(page, "Received in")
        expect(received.locator("dt")).to_have_text(f"Received in {MONTHS[first.month - 1]} (UTC)")
        expect(received.locator(".value")).to_have_text(f"{grouped(sum(line['amount_ar'] for line in paid))} Ar")
        spend = kpi(page, "Provider spend")
        expect(spend.locator("dd")).to_have_text([f"{usd(room['spent'])} of {usd(room['cap'])}", "since 2026-11-06", ""])
        share = room["spent"] / room["cap"] * 100
        expect(spend.get_by_role("img")).to_have_accessible_name(f"{math.floor(share + .5)}% of the cap spent")
        meter_js = "meter => meter.firstElementChild.getBoundingClientRect().width / meter.getBoundingClientRect().width * 100"
        drawn = spend.locator(".meter").evaluate(meter_js)
        assert abs(drawn - min(share, 100)) < .5, (drawn, share)
        # Answers the store does not reach, as told here: a spend over the cap (the real figure, the real share named, the
        # meter full) and another UTC month with a negative total (the month from the answer's start, not this clock).
        other = first.month % 12 + 1
        def over_cap(route):
            response = route.fetch()
            body = response.json()
            route.fulfill(response=response, json={**body, "headroom": {**body["headroom"], "spent": 30_000_000, "cap": 20_000_000}})
        def other_month(route):
            response = route.fetch()
            route.fulfill(response=response, json={**response.json(), "start": f"{first.year}-{other:02}-01", "received_ar": -2500})
        page.route("**/api/admin/service", over_cap)
        page.route("**/api/admin/payments", other_month)
        refresh.click()
        expect(spend.locator(".value")).to_have_text("$30.00 of $20.00")
        expect(spend.get_by_role("img")).to_have_accessible_name("150% of the cap spent")
        assert abs(spend.locator(".meter").evaluate(meter_js) - 100) < .5
        expect(received.locator("dt")).to_have_text(f"Received in {MONTHS[other - 1]} (UTC)")
        expect(received.locator(".value")).to_have_text("−2 500 Ar")
        page.unroute("**/api/admin/service", over_cap)
        page.unroute("**/api/admin/payments", other_month)
        refresh.click()
        expect(received.locator("dt")).to_have_text(f"Received in {MONTHS[first.month - 1]} (UTC)")
        expect(spend.locator(".value")).to_have_text(f"{usd(room['spent'])} of {usd(room['cap'])}")

        # The shops: the first eight by last poster, none last, then by identifier; the payments: the last five, newest first.
        latest = [identifier for identifier, _ in sorted(sorted(posters.items()), key=lambda shop: shop[1] or "", reverse=True)][:8]
        assert latest != sorted(latest), latest
        expect(shops_box.locator("tbody td.shop a")).to_have_text(latest)
        expect(shops_box.get_by_role("link", name=f"View all {len(listed)}", exact=True)).to_have_attribute("href", "#/shops")
        newest = paid[-5:][::-1]
        assert {"MV-MOVE", "MV-SPENT"} <= {line["ref"] for line in newest}, newest  # the move's two lines and the amount fixed
        expect(pay_box.locator(".paid p")).to_have_text(
            [f"{line['identifier']} · {signed(line['credits'])} {'credit' if abs(line['credits']) == 1 else 'credits'}" for line in newest])
        expect(pay_box.locator(".paid small")).to_have_text([f"{line['kind']}{' ' + line['origin'] if line['origin'] else ''}"
                                                             f"{' · ' + line['method'] if line['method'] else ''} · {line['ref']} · {line['at'][:10]}" for line in newest])
        expect(pay_box.locator(".paid .amount")).to_have_text([f"{signed(line['amount_ar'])} Ar" for line in newest])
        expect(pay_box).not_to_contain_text("MV-BEFORE")  # the month before
        expect(pay_box.get_by_role("link", name="View all", exact=True)).to_have_attribute("href", "#/money")

        # « Needs you »: its six causes, each line a link to where it is settled or read.
        no_password = [shop.identifier for shop in sorted(listed, key=lambda shop: shop.identifier) if not shop.has_password]
        assert no_password == ["ouverte", "sanspasse"], no_password
        lines = [("A request with no definite answer", WIDE_ID, f"#/shops/{wide}"),
                 *[("No password", identifier, f"#/shops/{ids[identifier]}") for identifier in no_password],
                 ("No purchase text", "Shops read the fallback sentence", "#/service"),
                 ("Last backup unknown", "No backup marker could be read", "#/service"),
                 ("1 failed job", "Failed or interrupted in the last 24 hours", "#/service"),
                 ("Cap warning", "The outstanding credits would cost more than what is left of the cap", "#/service")]
        needs(page, lines)
        # Among the first eight, the request's mark beside its shop's badge, as on the Shops table; the suspended shop with
        # no password keeps its one badge, its « No password » being a line of « Needs you ».
        assert {WIDE_ID, "sanspasse"} <= set(latest), latest
        [widest] = [shop for shop in listed if shop.id == wide]  # suspended by the first walk
        expect(shop_row(WIDE_ID).locator(".badge")).to_have_text(["suspended" if widest.state == "suspended" else "active"])
        expect(shop_row(WIDE_ID).locator(".unresolved")).to_have_text("unresolved request")
        expect(shop_row("sanspasse").locator(".badge")).to_have_text(["suspended"])
        expect(shop_row("sanspasse").locator(".unresolved")).to_have_count(0)
        page.screenshot(path=str(OUTPUT / "overview-1280-light.png"), full_page=True)

        # The figures four across over 1180 px, two by two from 600 px, one column under. « Needs you » the full width
        # under them at every width, then the shops and the service, the payments beside them over 1180 px and last on a
        # phone. At 360 px, with the widest identifier among « Needs you » and a 100-character reference among the
        # payments, both themes.
        blocks = [page.locator(selector) for selector in ("main .kpis", "main .needs")] + [shops_box, service_box, pay_box]
        for width, rows, columns in ((1280, 1, 4), (800, 2, 2), (360, 4, 1)):
            page.set_viewport_size({"width": width, "height": 800})
            boxes = page.locator("main .kpi").evaluate_all(KPI_JS)
            assert (len({top for top, _ in boxes}), len({left for _, left in boxes})) == (rows, columns), (width, boxes)
            assert boxes == sorted(boxes), (width, boxes)  # in reading order
            figures, need, shop, service, payment = [block.bounding_box() for block in blocks]
            first_shop = shops_box.locator("tbody tr").first.bounding_box()
            assert figures["y"] + figures["height"] <= need["y"] and need["y"] + need["height"] <= first_shop["y"], (width, need, first_shop)
            assert abs(need["x"] - figures["x"]) < 1 and abs(need["width"] - figures["width"]) < 1, (width, need, figures)
            assert shop["y"] + shop["height"] <= service["y"], (width, shop, service)
            if width > 1180:
                assert payment["x"] > shop["x"] + shop["width"] and abs(payment["y"] - shop["y"]) < 1, (width, payment, shop)
            else:
                assert service["y"] + service["height"] <= payment["y"] and abs(payment["width"] - figures["width"]) < 1, (width, payment)
        page.set_viewport_size({"width": 360, "height": 640})
        for scheme in ("light", "dark"):
            emulate(page, scheme)
            check_layout(page, f"the overview at 360 px, {scheme}, every cause of « Needs you »")
            page.screenshot(path=str(OUTPUT / f"overview-360-{scheme}.png"), full_page=True)
        emulate(page, "light")
        page.set_viewport_size({"width": 1280, "height": 800})

        # Each cause settled, one at a time: only its line goes. The request: its line opens its shop, discarded there.
        settled = []
        def left(**instead):
            return [instead.get(line[0], line) for line in lines if line[0] not in settled]
        needs_box(page).get_by_role("link", name=re.compile("^A request with no definite answer")).click()
        expect(page.get_by_role("heading", name=WIDE_ID, level=1)).to_be_focused()
        dialog, confirm = ask(page, page.get_by_role("button", name="Discard", exact=True), "Discard this request?", "Discard")
        confirm.click()
        expect(page.locator(".kept")).to_have_count(0)
        side.get_by_role("link", name="Overview", exact=True).click()
        settled.append("A request with no definite answer")
        needs(page, left())
        expect(shop_row(WIDE_ID).locator(".unresolved")).to_have_count(0)
        needs_box(page).get_by_role("link", name=re.compile("^No purchase text")).click()
        expect(page.get_by_role("heading", name="Service", level=1)).to_be_focused()
        page.go_back()
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        with write_tx(engine) as conn:
            shops.set_purchase_text(conn, "Mvola 034 00 000 00, référence : votre identifiant.")
        refresh.click()
        settled.append("No purchase text")
        needs(page, left())
        backup.update(backup={"finished_at": "2026-11-01T00:00:00+00:00", "age_hours": 72.5, "late": True})
        refresh.click()
        needs(page, left(**{"Last backup unknown": ("Backup late", "Last backup 72.5 hours ago", "#/service")}))
        backup.update(backup={"finished_at": utc_now(), "age_hours": 1, "late": False})
        refresh.click()
        settled.append("Last backup unknown")
        needs(page, left())
        with write_tx(engine) as conn:  # the failed job, more than 24 hours ago now
            conn.execute(text("UPDATE poster_jobs SET finished_at=:at WHERE id=:id"),
                         {"id": failed, "at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(timespec="microseconds")})
        refresh.click()
        settled.append("1 failed job")
        needs(page, left())
        with write_tx(engine) as conn:  # the keyboard walk's 100 000 credits, taken back: the cap holds what is outstanding
            credits.correct(conn, ids["clavier"], -100_000, ref="overview-take-back", note="tests", actor="tests")
            assert not shops.headroom(conn, settings)["warning"]
        refresh.click()
        settled.append("Cap warning")
        needs(page, left())
        assert [line[0] for line in left()] == ["No password", "No password"]
        # The last cause, the passwords, settled by the shops' answer while the service's is held: « Checking service… »,
        # never « Nothing needs you », until the service answers.
        with write_tx(engine) as conn:
            for identifier in no_password:
                shops.set_password(conn, ids[identifier], PASSWORDS.hash(os.urandom(8).hex()))
        held = []
        def hold(route):
            held.append(route)
        page.route("**/api/admin/service", hold)
        refresh.click()
        needs(page, [], ["Checking service…"])
        page.unroute("**/api/admin/service", hold)
        told_backup(held.pop())
        needs(page, [], ["Nothing needs you."])
        # The service's own fields, as read.
        with engine.connect() as conn:
            migration = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        expect(service_box.locator("dd")).to_have_text(["Running", f"dev · schema {migration}", "1 hour ago", "0", "$2.00 · 100 messages read"])
        with write_tx(engine) as conn:
            shops.pause(conn)
        refresh.click()
        expect(service_box.locator("dd").first).to_have_text(re.compile(r"^Paused since \d{4}-\d\d-\d\d \d\d:\d\d UTC$"))
        with write_tx(engine) as conn:
            shops.resume(conn)
        refresh.click()
        expect(service_box.locator("dd").first).to_have_text("Running")

        # A failed payments read alone: its blocks say so; « Needs you » is as it was.
        page.route("**/api/admin/payments", broken)
        refresh.click()
        expect(alert).to_have_text("Payments: The server failed (error 500).")
        expect(received.locator("dt")).to_have_text("Received in this month (UTC)")
        for block in (received, pay_box):
            expect(block).to_contain_text("Could not be read.")
            expect(block.get_by_role("button", name="Try again", exact=True)).to_be_visible()
        needs(page, [], ["Nothing needs you."])
        page.unroute("**/api/admin/payments", broken)
        pay_box.get_by_role("button", name="Try again", exact=True).click()
        expect(received.locator(".value")).to_be_visible()
        expect(alert).to_have_text("")

        # A failed service read: never « Nothing needs you »; the line names what was not checked; the shops stay usable.
        page.route("**/api/admin/service", broken)
        refresh.click()
        needs(page, [], ["Service not read: purchase text, backup, jobs and cap not checked."])
        expect(alert).to_have_text("Service: The server failed (error 500).")
        for block in (kpi(page, "Credits outstanding"), kpi(page, "Provider spend"), service_box):
            expect(block).to_contain_text("Could not be read.")
        expect(page.locator("main").get_by_role("button", name="Try again", exact=True)).to_have_count(3)
        expect(kpi(page, "Active shops").locator(".value")).to_be_visible()
        shops_box.get_by_role("link", name=latest[0], exact=True).click()
        expect(page.get_by_role("heading", name=latest[0], level=1)).to_be_focused()
        page.go_back()
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        page.unroute("**/api/admin/service", broken)
        refresh.click()
        needs(page, [], ["Nothing needs you."])

        # Refreshes answered out of order: the older one changes nothing, a success after a failure ...
        older = []
        def older_waits_newer_fails(route):
            if older:
                return route.fulfill(status=500, json=SERVER_ERROR)
            older.append((route, route.fetch()))
        page.route("**/api/admin/shops", older_waits_newer_fails)
        refresh.click()
        wait_until(page, lambda: older)
        refresh.click()
        needs(page, [], ["Shops not read: passwords not checked."])
        route, response = older.pop()
        route.fulfill(response=response)
        page.wait_for_timeout(500)  # an absence: the older answer gets its chance to land
        needs(page, [], ["Shops not read: passwords not checked."])
        for block in (kpi(page, "Active shops"), shops_box):
            expect(block).to_contain_text("Could not be read.")
        expect(alert).to_have_text("Shops: The server failed (error 500).")
        page.unroute("**/api/admin/shops", older_waits_newer_fails)
        # ... and a failure after a success.
        def older_waits(route):
            if older:
                return route.fallback()
            older.append(route)
        page.route("**/api/admin/shops", older_waits)
        refresh.click()
        wait_until(page, lambda: older)
        refresh.click()
        expect(shops_box.locator("tbody tr")).to_have_count(8)
        older.pop().fulfill(status=500, json=SERVER_ERROR)
        page.wait_for_timeout(500)
        expect(shops_box.locator("tbody tr")).to_have_count(8)
        expect(alert).to_have_text("")
        needs(page, [], ["Nothing needs you."])
        # An older refresh's 401 still opens the sign-in; after it, a home entry focuses the overview's heading.
        refresh.click()
        wait_until(page, lambda: older)
        with page.expect_response(re.compile(r"/api/admin/shops$")):
            refresh.click()
        with write_tx(engine) as conn:
            shops.end_operator_sessions(conn)
        older.pop().continue_()
        expect(password_field(page)).to_be_focused()
        expect(page.locator("form", has=password_field(page)).get_by_role("alert")).to_have_text("Your session has ended. Sign in again.")
        page.unroute("**/api/admin/shops", older_waits)
        reads.clear()
        sign_in(page)
        expect(page.get_by_role("heading", name="Overview", level=1)).to_be_focused()
        needs(page, [], ["Nothing needs you."])
        read_once("the sign-in after a 401")
        page.screenshot(path=str(OUTPUT / "overview-1280-empty.png"), full_page=True)
    finally:
        context.close()


def walk_shops_page(browser, errors):
    """The shops' page asks for nothing under /admin/ (D-ADMIN-005: no byte of the operator's page reaches it)."""
    page = browser.new_page(viewport={"width": 360, "height": 640})
    page.on("pageerror", lambda error: errors.append(str(error)))
    requested = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{smoke.ORIGIN}/")
    expect(page.get_by_label("Identifiant de la boutique", exact=True)).to_be_enabled()
    page.wait_for_load_state("networkidle")
    assert requested and not [url for url in requested if "/admin" in url], requested
    page.close()


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    assert (smoke.ROOT / "frontend/dist/admin/index.html").is_file(), "build first: corepack npm@10 run build"
    errors = []
    with tempfile.TemporaryDirectory(prefix="affiche-admin-") as data:
        server = smoke.serve(data)
        engine = make_engine(Path(data))
        with (OUTPUT / "preview.log").open("w") as log:
            vite = subprocess.Popen(["node", str(smoke.ROOT / "frontend/node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1",
                                     "--port", str(smoke.WEB_PORT), "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        walk(browser, playwright, engine, errors)
                        walk_money(browser, engine, errors)
                        walk_no_storage(browser, engine, errors)
                        walk_keyboard(browser, errors)
                        walk_service(browser, engine, errors)
                        walk_shell(browser, engine, errors)
                        walk_overview(browser, engine, Path(data), errors)
                        walk_shops_page(browser, errors)
                        assert not errors, errors
                    finally:
                        browser.close()
                (OUTPUT / "results.json").write_text(json.dumps({"errors": errors, "viewports": [360, 1280]}, indent=2))
            finally:
                vite.terminate()
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill()
                    vite.wait(timeout=10)
                engine.dispose()
                smoke.stop(*server)
    print("Admin browser checks passed (stub only): sign-in refusals and limit, a shop created and its password shown once, "
          "a new password, its sessions ended, suspend (Esc and Cancel send nothing) and enable, a 401 and a reload kept in "
          "place, 360 px in both themes with the widest values, 1280 px, the keyboard alone, the shops' page apart; a 401 "
          "with a password shown or a question open, late answers after a sign-out and a new sign-in, a lost sign-out, an "
          "answer after moving to another shop. Money: a bought grant with the widest values at 360 px, its answer lost "
          "after the commit and sent again (as sent, once), the request frozen behind the confirmation, double taps, other "
          "values and another shop's payment, a 503 then a reload, a discard, a 401 mid-send, an answer dropped by a new "
          "session, two tabs (one with a confirmation open), a correction refused, a move and its repeat, a move refused "
          "with the concession, a repayment, « Older », the payments of a period, storage refused, a grant by keyboard. "
          "Service: its figures at 360 px with a 500-character text and a 200-character browser, the pause (Esc, Cancel, a 503 "
          "said as unknown, a double tap sent once) and its end, an answer after leaving the screen, the purchase text as "
          "text (blank refused, kept across a lost session), the operator sessions with this device marked, « End all "
          "operator sessions » with a second device: both signed out. Shell: the sidebar's links, every screen at 1280 and "
          "360 px in both themes, Figtree and the logo of the theme, the table's states and filter, « New shop », the rail, "
          "the drawer at 1024 and 360 px, the theme switch kept across the device's scheme and a reload. Overview: the home "
          "on a sign-in, its figures and lists against a seeded store, each cause of « Needs you » and its empty sentence, a "
          "request held in memory only, a failed service read and a failed payments read, refreshes out of order and an "
          "older one's 401, the figures at 1280, 800 and 360 px.")


if __name__ == "__main__":
    run()
