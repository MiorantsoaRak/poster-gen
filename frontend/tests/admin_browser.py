"""The operator's page (T-ADMIN-005) in real Chromium: the production build (vite preview, so build first) and the API on
temporary stub data, no real env file, no paid call. Run from backend: uv run python ../frontend/tests/admin_browser.py"""
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from sqlalchemy import text

import browser_smoke as smoke
from affiche import shops
from affiche.db import make_engine, write_tx
from affiche.posters.auth import PASSWORDS

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
    """Opens « New shop » when it is folded (its fold keeps its state across views)."""
    if not page.locator("details", has=page.locator("summary", has_text="New shop")).evaluate("e => e.open"):
        page.get_by_text("New shop", exact=True).click()


def wait_until(page, ready):
    """Lets the route handlers run (they run during Playwright calls) until `ready()` holds."""
    for _ in range(100):
        if ready():
            return
        page.wait_for_timeout(50)
    raise AssertionError("never ready")


def check_layout(page, where):
    page.wait_for_function(NO_SIDEWAYS)
    small = page.evaluate(SMALL_TARGETS_JS)
    assert not small, f"targets under 44 px on {where}:\n" + "\n".join(small)
    smoke.check_contrast(page, where)


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
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_visible()
        expect(page.get_by_text(re.compile(r"^dashboard:[0-9a-f]{8}$"))).to_be_visible()
        expect(page.get_by_role("link", name=smoke.IDENTIFIER, exact=True)).to_be_visible()

        # A shop with the widest values, its password shown once and copied.
        page.get_by_text("New shop", exact=True).click()
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
        expect(row.locator("td[data-label=Name]")).to_have_text(WIDE_NAME)
        expect(row.locator("td[data-label=Available]")).to_have_text("5")
        expect(row.locator("td[data-label=Sessions]")).to_have_text("0")  # read at its creation: no polling (D-ADMIN-005)
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
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
        expect(page.locator("main p").filter(has_text="available 5")).to_have_text("available 5 · en attente 0")
        expect(page.get_by_text("Provider spend: $0.00 of $2.00", exact=True)).to_be_visible()
        expect(page.get_by_text("Messages read: 0 of 100", exact=True)).to_be_visible()
        page.get_by_text("Access", exact=True).click()

        dialog, confirm = ask(page, page.get_by_role("button", name="Set a new password", exact=True), "Set a new password?", "Set a new password")
        expect(dialog).to_have_accessible_description(f"A new password for {WIDE_ID}. Its 1 session ends.")
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
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
            page.emulate_media(color_scheme=scheme)
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
        expect(page.locator("details.fold [role=status]")).to_have_text("")
        expect(page.locator("details.fold [role=alert]")).to_have_text("")
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
        page.get_by_text("New shop", exact=True).click()
        page.get_by_label("Identifier", exact=True).fill("refused")
        page.get_by_role("button", name="Create the shop", exact=True).click()
        expect(page.get_by_role("alert").filter(has_text=WIDE_REFUSAL)).to_be_visible()
        expect(page.get_by_label("Identifier", exact=True)).to_have_value("refused")  # what was typed stays
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
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
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_visible()
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
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_hidden()
        assert third not in page.content()
        sign_in(page)
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_visible()
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

        # At 1280 px the shops are a table.
        page.set_viewport_size({"width": 1280, "height": 800})
        expect(page.get_by_role("columnheader", name="Identifier")).to_be_visible()
        check_layout(page, "the shop list at 1280 px, dark")
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
                expect(page.get_by_role("button", name="Create the shop", exact=True)).to_be_enabled()
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
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_hidden()
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
        own = [url for url in requested if not re.match(rf"{re.escape(smoke.ORIGIN)}/(admin/|api/admin/)", url) and not url.endswith("/favicon.ico")]
        assert not own, own
        # Back from another page: still signed out, nothing of the session.
        page.goto(f"{smoke.ORIGIN}/")
        page.go_back()
        expect(password_field(page)).to_be_visible()
        left_nothing("back from another page")
    finally:
        api.dispose()
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
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_focused()
        tab_to(page, page.locator("summary", has_text="New shop"))
        page.keyboard.press("Enter")
        tab_to(page, page.get_by_label("Identifier", exact=True))
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
        tab_to(page, page.get_by_role("button", name="Sign out", exact=True), back=True)
        page.keyboard.press("Enter")
        expect(password_field(page)).to_be_focused()
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
                                     "--port", "5173", "--strictPort"], cwd=smoke.ROOT / "frontend", stdout=log, stderr=log)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        walk(browser, playwright, engine, errors)
                        walk_keyboard(browser, errors)
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
          "answer after moving to another shop.")


if __name__ == "__main__":
    run()
