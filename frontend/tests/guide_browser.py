"""First-poster guide on the production bundle, with an isolated shop and simulated providers.

Build frontend first. From backend run `uv run python ../frontend/tests/guide_browser.py`.
"""
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

import browser_smoke as smoke
from affiche.db import make_engine
from share_browser import made_in_chat, sign_in
from terms_browser import FRAMES, open_atelier, set_terms, until

OUT = smoke.ROOT / 'outputs/guide01'
PRODUCT = smoke.ROOT / 'backend/fixtures/examples/phone-noir.jpg'
GUIDE = 'Ma première affiche'


@contextmanager
def reading(page):
    mutations = []
    def observe(request):
        if '/api/' in request.url and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            mutations.append((request.method, request.url))
    page.on('request', observe)
    address = page.url
    try:
        yield
        page.evaluate(FRAMES)
        assert page.url == address, (page.url, address)
        assert not mutations, mutations
    finally:
        page.remove_listener('request', observe)


def step(page, number):
    panel = page.get_by_role('dialog', name=GUIDE, exact=True)
    expect(panel.get_by_role('heading', name=re.compile(rf'^Étape {number} sur 4\.\s+\S'))).to_be_focused()
    return panel


def home(browser, engine, errors):
    set_terms(engine, None)
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, color_scheme='light')
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    open_atelier(page, '/#accueil')
    page.get_by_label('Identifiant de la boutique', exact=True).fill(smoke.IDENTIFIER)
    page.get_by_label('Mot de passe', exact=True).fill(smoke.PASSWORD)
    page.get_by_role('button', name='Ouvrir l’atelier').click()
    terms = page.get_by_role('dialog', name='Conditions d’utilisation')
    invite = page.get_by_role('button', name=GUIDE, exact=True)
    expect(terms).to_be_visible()
    expect(page.get_by_role('dialog', name=GUIDE)).to_have_count(0)
    expect(page.locator('.shop-home')).to_have_attribute('inert', '')
    terms.get_by_role('button', name='Plus tard').click()
    storage = "() => JSON.stringify([Object.entries(localStorage).sort(), Object.entries(sessionStorage).sort()])"
    saved = page.evaluate(storage)
    with reading(page):
        invite.click()
        panel = step(page, 1)
        expect(panel.get_by_role('button', name='Précédent')).to_be_disabled()
        page.screenshot(animations='disabled', path=str(OUT / 'guide-desktop-light.png'))
        panel.get_by_role('button', name='Fermer').focus()
        page.keyboard.press('Shift+Tab')
        expect(panel.get_by_role('button', name='Suivant')).to_be_focused()
        page.keyboard.press('Tab')
        expect(panel.get_by_role('button', name='Fermer')).to_be_focused()
        panel.get_by_role('button', name='Suivant').click()
        step(page, 2)
        panel.get_by_role('button', name='Fermer').click()
        expect(invite).to_be_focused()
        help_button = page.locator('aside.side').get_by_role('button', name='Aide', exact=True)
        help_button.click()
        panel = step(page, 2)
        panel.get_by_role('button', name='Précédent').click()
        for number in range(1, 5):
            panel = step(page, number)
            troubleshoot = panel.locator('summary', has_text='Si vous êtes bloqué')
            troubleshoot.click()
            assert troubleshoot.evaluate('e => e.parentElement.open')
            panel.get_by_role('button', name='Terminer' if number == 4 else 'Suivant').click()
        expect(help_button).to_be_focused()
        help_button.click()
        step(page, 1)
        page.keyboard.press('Escape')
        expect(help_button).to_be_focused()

    assert saved == page.evaluate(storage)
    # Hiding the tab closes the shop gate. Re-verification must not bring back the guide.
    with reading(page):
        help_button.click()
        step(page, 1)
        page.evaluate(smoke.VISIBILITY, True)
        expect(page.get_by_role('dialog', name=GUIDE)).to_have_count(0)
        assert page.evaluate(smoke.GATE_CLOSED, [])
        page.evaluate(smoke.VISIBILITY, False)
        expect(help_button).to_be_visible()
        expect(page.get_by_role('dialog', name=GUIDE)).to_have_count(0)

    # A previously successful empty response is stale throughout the failed refresh.
    reads = []
    route = '**/api/creations?limit=5'
    page.route(route, lambda request: reads.append(request))
    page.get_by_role('button', name='Actualiser', exact=True).click()
    expect(invite).to_have_count(0)
    until(page, lambda: len(reads) == 1)
    reads[0].fulfill(status=503, json={'error': {'code': 'service_down', 'message_fr': 'Liste indisponible.'}})
    expect(page.get_by_role('button', name='Réessayer les affiches')).to_be_visible()
    expect(invite).to_have_count(0)
    with reading(page):
        help_button.click()
        step(page, 1)
        page.keyboard.press('Escape')
    page.unroute(route)
    page.get_by_role('button', name='Réessayer les affiches').click()
    expect(invite).to_be_visible()
    # A real navigation dismisses the dialog and lets the destination receive focus.
    invite.click()
    step(page, 1)
    page.evaluate("location.hash = 'styles'")
    expect(page.get_by_role('dialog', name=GUIDE, exact=True)).to_have_count(0)
    expect(page.get_by_role('heading', name='Styles', exact=True)).to_be_visible()
    context.close()


def creation(browser, errors):
    context = browser.new_context(viewport={'width': 360, 'height': 640}, color_scheme='dark')
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    open_atelier(page, '/#accueil')
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    terms = page.get_by_role('dialog', name='Conditions d’utilisation')
    terms.get_by_role('button', name='J’accepte').click()
    expect(terms).to_have_count(0)
    page.goto(smoke.ORIGIN + '/#message')
    message = page.get_by_label('Votre message')
    message.fill('Téléphone noir, 180 000 Ar')
    page.locator('.composer input[type=file]').set_input_files([PRODUCT, smoke.ROOT / 'frontend/public/styles/clair.jpg'])
    expect(page.locator('.tray .pic .pic-role')).to_have_text(['Produit', 'Inspiration'])
    expect(page.locator('.tray .pic[aria-busy]')).to_have_count(0)
    originals = page.locator('.tray img').evaluate_all('els => els.map(e => e.src)')
    with reading(page):
        menu = page.get_by_role('button', name='Ouvrir le menu')
        smoke.open_drawer(page).get_by_role('button', name='Aide', exact=True).click()
        panel = step(page, 1)
        page.screenshot(animations='disabled', path=str(OUT / 'guide-phone-dark.png'))
        page.set_viewport_size({'width': 360, 'height': 400})  # room left by a phone keyboard
        for label in ('Fermer', 'Suivant'):
            expect(panel.get_by_role('button', name=label, exact=True)).to_be_in_viewport(ratio=1)
        # At 200% browser zoom a 360 × 400 window has a 180 × 200 CSS layout viewport.
        page.set_viewport_size({'width': 180, 'height': 200})
        for label in ('Fermer', 'Suivant'):
            control = panel.get_by_role('button', name=label, exact=True)
            control.scroll_into_view_if_needed()
            expect(control).to_be_in_viewport(ratio=1)
        panel.get_by_role('button', name='Suivant').click()
        step(page, 2)
        assert panel.evaluate('d => d.scrollWidth <= d.clientWidth')
        page.screenshot(animations='disabled', path=str(OUT / 'guide-short-zoom.png'))
        page.keyboard.press('Tab')
        summary = panel.locator('summary')
        expect(summary).to_be_focused()
        expect(summary).to_be_in_viewport()
        summary.press('Enter')
        summary.press('End')
        expect(panel.locator('details p').last).to_be_in_viewport()
        page.set_viewport_size({'width': 360, 'height': 400})
        panel.get_by_role('button', name='Précédent').click()
        step(page, 1)
        expect(panel.get_by_role('heading')).to_be_in_viewport(ratio=1)
        page.screenshot(animations='disabled', path=str(OUT / 'guide-short-keyboard.png'))
        page.keyboard.press('Escape')
        page.set_viewport_size({'width': 360, 'height': 640})
        expect(menu).to_be_focused()
    expect(message).to_have_value('Téléphone noir, 180 000 Ar')
    expect(page.locator('.tray .pic .pic-role')).to_have_text(['Produit', 'Inspiration'])
    assert originals == page.locator('.tray img').evaluate_all('els => els.map(e => e.src)')
    # A fresh tab starts its guide from step one. The original chat keeps its unsent tray.
    guided = context.new_page()
    guided.on('pageerror', lambda e: errors.append(str(e)))
    open_atelier(guided, '/#etapes')
    guided.get_by_label('Nom du produit', exact=True).fill('Téléphone du guide')
    with reading(guided):
        smoke.open_drawer(guided).get_by_role('button', name='Aide', exact=True).click()
        step(guided, 1)
        guided.keyboard.press('Escape')
    expect(guided.get_by_label('Nom du produit', exact=True)).to_have_value('Téléphone du guide')
    guided.get_by_label('Photos du produit').set_input_files(PRODUCT)
    expect(guided.locator('.photo-strip img')).to_have_count(1)
    guided.get_by_label('Prix en ariary', exact=True).fill('180000')
    guided.get_by_label('Les photos correspondent').check()
    guided.get_by_role('button', name='Préparer mon affiche').click()
    expect(guided.get_by_role('region', name='Offre à générer')).to_be_visible()
    contextual = guided.get_by_role('button', name='Aide pour cette affiche')
    with reading(guided):
        contextual.click()
        panel = step(guided, 2)
        panel.get_by_role('button', name='Fermer').click()
        expect(contextual).to_be_focused()
    guided.get_by_role('button', name='Générer l’affiche').click()
    guided.get_by_role('button', name='Lancer la génération').click()
    review = guided.locator('.final-preview')
    expect(review.get_by_role('heading', name='Vérifier votre affiche')).to_be_visible(timeout=30000)
    expect(review.get_by_role('button', name='Confirmer et télécharger le PNG', exact=True)).to_be_enabled()
    guided.screenshot(animations='disabled', path=str(OUT / 'single-review-phone.png'))
    review.get_by_role('button', name='Corriger l’affiche').click()
    with reading(guided):
        contextual.click()
        panel = step(guided, 3)
        expect(panel).to_contain_text('Comparez l’affiche terminée à la photo du produit.')
        guided.keyboard.press('Escape')
        expect(contextual).to_be_focused()
    context.close()


def confirm_for_later(page, poster):
    panel = page.locator('.final-preview')
    preview_url = panel.locator('.shot img').evaluate('image => image.src')
    reviewed_png = page.request.get(preview_url, fail_on_status_code=True).body()
    address = f'{smoke.ORIGIN}/api/creations/{poster}'
    pending = page.request.get(address, fail_on_status_code=True).json()
    assert pending['confirmation'] is None
    origin = page.url
    downloads, mutations = [], []
    def record_download(download):
        downloads.append(download)
    def record(request):
        if '/api/' in request.url and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            mutations.append((request.method, request.url))
    page.on('request', record)
    page.on('download', record_download)
    try:
        panel.get_by_role('button', name='Confirmer pour plus tard', exact=True).click()
        expect(panel.get_by_role('heading', name='Affiche confirmée')).to_be_visible()
        page.screenshot(animations='disabled', path=str(OUT / 'confirmed-for-later.png'))
        assert page.url == origin
        panel.get_by_role('button', name='Fermer').click()
        page.goto(smoke.ORIGIN + '/#affiches')
        row = page.locator('.library-row', has_text=pending['document']['offer']['title'])
        expect(row.locator('.badge')).to_have_text('Confirmée')
        row.get_by_role('button', name=re.compile('^Ouvrir le fichier')).click()
        expect(panel.get_by_role('heading', name='Affiche confirmée')).to_be_visible()
        assert panel.locator('.shot img').evaluate('image => image.src') == preview_url
        assert mutations == [('POST', address + '/confirmations')], mutations
        assert not downloads, downloads
    finally:
        page.remove_listener('request', record)
        page.remove_listener('download', record_download)
    with page.expect_download() as saved:
        panel.get_by_role('link', name='Télécharger le PNG', exact=True).click()
    assert saved.value.path().read_bytes() == reviewed_png


def publishing(browser, errors):
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    open_atelier(page, '/#accueil')
    sign_in(page, smoke.IDENTIFIER, smoke.PASSWORD)
    expect(page.get_by_role('button', name=GUIDE, exact=True)).to_have_count(0)
    for index, message in enumerate(('Sony WH-1000XM6 noir, 700 000 Ar', 'Samsung Galaxy A15 noir, 650 000 Ar')):
        page.goto(smoke.ORIGIN + '/#accueil')
        poster = made_in_chat(page, PRODUCT, message)
        if index == 0:
            confirm_for_later(page, poster)
        else:
            smoke.download_review(page)
        panel = page.locator('.final-preview')
        panel.get_by_role('button', name='Fermer').click()
    page.goto(smoke.ORIGIN + '/#compte')
    facebook = page.get_by_role('region', name='Page Facebook', exact=True)
    facebook.get_by_role('button', name='Connecter ma Page Facebook').click()
    facebook.get_by_role('radio', name='Page d’essai 1').check()
    facebook.get_by_role('button', name='Connecter cette Page').click()
    expect(facebook).to_contain_text('Page connectée')
    page.goto(smoke.ORIGIN + '/#publier')
    field = page.get_by_label('Description de la publication')
    field.fill('Nos deux offres de la semaine')
    tiles = page.locator('.tile')
    expect(tiles).to_have_count(2)
    for tile in tiles.all():
        tile.click()
    chosen = page.locator('ol.chosen > li strong')
    titles = chosen.all_text_contents()
    assert len(titles) == 2
    page.get_by_role('button', name=f'Déplacer {titles[1]}', exact=True).press('ArrowUp')
    expect(chosen).to_have_text(titles[::-1])
    stored = page.evaluate("localStorage.getItem('affiche.shop1.post-draft')")
    assert stored
    help_button = page.get_by_role('button', name='Aide à la publication', exact=True)
    with reading(page):
        help_button.click()
        panel = step(page, 4)
        assert page.evaluate("async () => (await navigator.locks.query()).held.some(l => l.name === 'affiche-publish')")
        panel.locator('summary').click()
        page.screenshot(animations='disabled', path=str(OUT / 'guide-publishing.png'))
        panel.get_by_role('button', name='Terminer').click()
        expect(help_button).to_be_focused()
    expect(chosen).to_have_text(titles[::-1])
    expect(field).to_have_value('Nos deux offres de la semaine')
    assert stored == page.evaluate("localStorage.getItem('affiche.shop1.post-draft')")
    page.get_by_role('button', name='Publier…', exact=True).click()
    expect(page.get_by_role('dialog', name=re.compile('^Publier sur '))).to_be_visible()
    expect(help_button).to_have_count(0)
    context.close()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='affiche-guide-') as data, (OUT / 'preview.log').open('w') as log:
        server = smoke.serve(data, facebook_provider='stub')
        engine = make_engine(Path(data))
        try:
            with subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', str(smoke.WEB_PORT), '--strictPort'], cwd=smoke.ROOT / 'frontend', stdout=log, stderr=log) as vite:
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch()
                        errors = []
                        try:
                            home(browser, engine, errors)
                            creation(browser, errors)
                            publishing(browser, errors)
                            assert not errors, errors
                        finally:
                            browser.close()
                finally:
                    vite.terminate()
        finally:
            engine.dispose()
            smoke.stop(*server)
    print('Guide checks passed: four steps, keyboard focus, retained work, library-only confirmation without download or post, two matching PNGs, prepared batch and zero guide mutations.')


if __name__ == '__main__':
    run()
