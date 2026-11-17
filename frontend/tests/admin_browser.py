"""The operator's page (T-ADMIN-005) in real Chromium: the production build (vite preview, so build first) and the API on
temporary stub data, no real env file, no paid call. Run from backend: uv run python ../frontend/tests/admin_browser.py"""
import json
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
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import credits
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
# Money (T-ADMIN-006): the widest values the fields accept, unbroken; the kept request's key and the page's sentences.
REF100, METHOD40, NOTE500 = "R" * 100, "M" * 40, "n" * 500
PENDING_JS = ("JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.startsWith('affiche.admin.pending.'))"
              ".map(([key, value]) => [key.slice(22), JSON.parse(value)])))")
UNCERTAIN = "It may have been recorded: the history is read again below. Sending the same request again is safe: it is written once."
CAP_WARNING = "Warning: the outstanding credits would cost more than what is left of the cap. Raise SPEND_CAP_USD (deploy/README.md)."
OFFERED_REF = re.compile(r"^offered-\d{8}-\d{6}-[a-z2-9]{6}$")
APOSTROPHE = "’"


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


def shop_ids(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT identifier, id FROM shop_profile")).all())


def lines_of(engine, ref):
    """The credit lines written under one reference, whatever wrote them."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT id, shop_id, kind, origin, credits, amount_ar, method FROM credit_grants WHERE ref = :ref"
                                 " ORDER BY id"), {"ref": ref}).all()


def succeeded_jobs(engine, shop, count):
    """Images the shop made, written by hand as test_admin.py writes them: each took a credit and can be repaid."""
    made, at = [], utc_now()
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT OR IGNORE INTO product_inputs VALUES (?,?,'P1','JBL','Bleu','[]','{}',NULL,?)", (f"in-{shop}", shop, at))
        for _ in range(count):
            id = str(uuid.uuid4())
            conn.exec_driver_sql("INSERT INTO creations VALUES (?,?,NULL,1,'active',?,?)", (id, shop, at, at))
            conn.exec_driver_sql("INSERT INTO creation_versions VALUES (?,1,'{}','h',?)", (id, at))
            conn.exec_driver_sql("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,input_hash,"
                                 "status,created_at,started_at,finished_at,takes_credit) VALUES (?,?,?,1,?,'background','{}','h',"
                                 "'succeeded',?,?,?,1)", (id, shop, id, f"in-{shop}", at, at, at))
            made.append(id)
    return made


def pending(page):
    """What the page keeps in localStorage for unresolved money requests, read as the page reads it."""
    return json.loads(page.evaluate(PENDING_JS)) or None


def open_shop(page, id, identifier):
    if page.evaluate("location.hash") == f"#/shops/{id}":
        page.evaluate("location.hash = '#/shops'")
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_visible()
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
        expect(page.get_by_role("heading", name="Shops", exact=True)).to_be_visible()

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
            page.emulate_media(color_scheme=scheme)
            page.wait_for_function(NO_SIDEWAYS)
            for button in (dialog.get_by_role("button", name="Cancel"), confirm):
                expect(button).to_be_in_viewport(ratio=1)
            page.screenshot(path=str(OUTPUT / f"grant-confirm-360-{scheme}.png"))
        page.emulate_media(color_scheme="light")
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
            page.emulate_media(color_scheme=scheme)
            check_layout(page, f"a kept request with a 100-character reference at 360 px, {scheme}")
            page.screenshot(path=str(OUTPUT / f"kept-360-{scheme}.png"), full_page=True)
        page.emulate_media(color_scheme="light")
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
            page.emulate_media(color_scheme=scheme)
            check_layout(page, f"the history with the widest values at 360 px, {scheme}")
            page.screenshot(path=str(OUTPUT / f"history-360-{scheme}.png"), full_page=True)
        page.emulate_media(color_scheme="light")

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
            page.emulate_media(color_scheme=scheme)
            check_layout(page, f"a 300-character money refusal at 360 px, {scheme}")
        page.emulate_media(color_scheme="light")
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
        page.evaluate("location.hash = '#/money'")
        expect(page.get_by_role("heading", name="Money", level=1)).to_be_focused()
        now = datetime.now(UTC)
        first = now.date().replace(day=1)
        last = (first + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        with engine.connect() as conn:
            received = conn.execute(text("SELECT SUM(amount_ar), COUNT(*) FROM credit_grants WHERE amount_ar IS NOT NULL AND created_at >= :start"
                                         " AND created_at < :end"), {"start": first.isoformat(), "end": (last + timedelta(days=1)).isoformat()}).one()
        expect(page.get_by_label("First day (UTC)", exact=True)).to_have_value(first.isoformat())
        expect(page.get_by_label("Last day, included", exact=True)).to_have_value(last.isoformat())
        expect(page.get_by_text(re.compile(r"^Received: "))).to_have_text(f"Received: {received[0]:,} Ar".replace(",", " "))
        expect(page.locator(".lines li")).to_have_count(received[1])
        expect(page.locator(".lines li", has_text="MV-MOVE")).to_have_count(3)  # moved: +A, −A, +A, counted once
        expect(page.locator(".lines li", has_text="MV-SPENT")).to_contain_text("+20 000 Ar · boutiquesix · grant bought · line ")
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            check_layout(page, f"the payments at 360 px, {scheme}")
            page.screenshot(path=str(OUTPUT / f"payments-360-{scheme}.png"), full_page=True)
        page.emulate_media(color_scheme="light")
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
                        walk_money(browser, engine, errors)
                        walk_no_storage(browser, engine, errors)
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
          "answer after moving to another shop. Money: a bought grant with the widest values at 360 px, its answer lost "
          "after the commit and sent again (as sent, once), the request frozen behind the confirmation, double taps, other "
          "values and another shop's payment, a 503 then a reload, a discard, a 401 mid-send, an answer dropped by a new "
          "session, two tabs (one with a confirmation open), a correction refused, a move and its repeat, a move refused "
          "with the concession, a repayment, « Older », the payments of a period, storage refused, a grant by keyboard.")


if __name__ == "__main__":
    run()
