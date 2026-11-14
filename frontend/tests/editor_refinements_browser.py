"""Focused production-build browser checks; temporary stub data, no paid calls."""
import json
import re
import subprocess
import tempfile
import time
from uuid import uuid4

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

import browser_smoke as smoke


def run():
    out = smoke.ROOT / 'outputs/editor-refinements'
    out.mkdir(parents=True, exist_ok=True)
    photo = Image.new('RGB', (1000, 1000), 'white')
    ImageDraw.Draw(photo).rounded_rectangle((250, 160, 750, 840), 50, fill='#202020')
    photo.save(out / 'black-product.png')
    logo = Image.new('RGBA', (240, 120), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rectangle((15, 15, 225, 105), fill='#1266cc')
    logo.save(out / 'logo.png')
    errors, requests = [], []
    with tempfile.TemporaryDirectory(prefix='affiche-refinements-') as data:
        server, thread = smoke.serve(data)
        with (out / 'preview.log').open('w') as log:
            vite = subprocess.Popen(['node', str(smoke.ROOT / 'frontend/node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', '5173', '--strictPort'], cwd=smoke.ROOT / 'frontend', stdout=log, stderr=log)
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(viewport={'width': 1366, 'height': 900}, color_scheme='light', has_touch=True)
                    page = context.new_page()
                    page.set_default_timeout(10000)
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.on('response', lambda r: print(r.status, r.url, r.text(), flush=True) if r.status >= 400 and '/api/' in r.url else None)
                    page.on('request', lambda r: requests.append(r.post_data_json) if r.method == 'POST' and r.url.endswith('/scenes') else None)
                    for attempt in range(40):
                        try:
                            page.goto(smoke.ORIGIN)
                            break
                        except Exception:
                            if attempt == 39 or vite.poll() is not None:
                                raise
                            time.sleep(.2)
                    page.get_by_label('Mot de passe', exact=True).fill(smoke.PASSWORD)
                    page.get_by_role('button', name='Ouvrir l’atelier').click()
                    expect(page.get_by_label('Photos du produit')).to_be_enabled()
                    page.get_by_label('Photos du produit').set_input_files(out / 'black-product.png')
                    expect(page.locator('.photo-strip img')).to_have_count(1)
                    page.get_by_label('Nom du produit', exact=True).fill('Bose QuietComfort')
                    page.get_by_label('Prix en ariary', exact=True).fill('1 150 000')
                    page.get_by_label('Les photos correspondent').check()
                    for name in ('Logo', 'Contact', 'Nom de la boutique'):
                        expect(page.get_by_role('checkbox', name=name, exact=True)).not_to_be_checked()
                    page.get_by_role('button', name='Préparer mon affiche').click()
                    page.get_by_label('Marque (facultative)', exact=True).fill('Bose')
                    expect(page.get_by_text('déjà dans le titre', exact=False)).to_be_visible()
                    page.get_by_role('button', name='Continuer', exact=True).click()
                    page.get_by_text('Ajouter les informations manquantes', exact=True).click()
                    page.get_by_role('textbox', name='Nom de la boutique', exact=True).fill('Boutique test')
                    page.get_by_role('textbox', name='Contact', exact=True).fill('034 00 000 00')
                    page.locator('.identity-import input[type=file]').set_input_files(out / 'logo.png')
                    # The form is a copy: the shop's profile (its name in the header) changes only on « Ajouter ».
                    expect(page.locator('.shop-label')).to_have_text('Votre boutique')
                    draft_url = smoke.ORIGIN + '/api/creations/' + page.url.split('#')[1]
                    before_import = page.request.get(draft_url).json()['document']
                    page.route('**/api/shop-profile', lambda route: route.fulfill(status=409, content_type='application/json', body='{"error":{"code":"revision_conflict","message_fr":"Profil modifié ailleurs","retryable":false}}') if route.request.method == 'PUT' else route.continue_())
                    page.get_by_role('button', name='Ajouter à cette affiche', exact=True).click()
                    expect(page.get_by_role('alert')).to_contain_text('Profil modifié ailleurs')
                    expect(page.locator('.shop-label')).to_have_text('Votre boutique')
                    assert page.request.get(draft_url).json()['document'] == before_import
                    page.unroute('**/api/shop-profile')
                    page.get_by_role('button', name='Ajouter à cette affiche', exact=True).click()
                    expect(page.get_by_text('Informations ajoutées.', exact=False)).to_be_visible()
                    expect(page.locator('.shop-label')).to_have_text('Boutique test')
                    for name in ('Logo', 'Contact', 'Nom de la boutique'):
                        expect(page.get_by_role('checkbox', name=name, exact=True)).not_to_be_checked()
                    page.get_by_role('checkbox', name='Logo', exact=True).check()
                    page.get_by_role('button', name='En haut à gauche', exact=True).click()
                    page.get_by_role('button', name='Continuer', exact=True).click()
                    page.get_by_role('button', name='Aux couleurs du produit', exact=True).click()
                    palette = page.get_by_role('group', name='Palette de la prochaine version')
                    expect(palette).to_contain_text('#202020')
                    manual = page.get_by_label('Corriger la couleur principale')
                    manual.fill('#cc1122')
                    expect(palette).to_contain_text('#CC1122')
                    url = page.url
                    expect(page.get_by_text('Enregistré', exact=True)).to_be_visible()
                    page.reload()
                    page.get_by_role('button', name='Continuer', exact=True).click()
                    page.get_by_role('button', name='Continuer', exact=True).click()
                    page.get_by_role('button', name='Aux couleurs du produit', exact=True).click()
                    expect(palette).to_contain_text('#CC1122')
                    # A decoder already in flight cannot overwrite a newer manual choice.
                    page.evaluate("""() => {const original=window.createImageBitmap; window.restoreBitmap=()=>{window.createImageBitmap=original};
                      window.createImageBitmap=async (...args)=>{window.decodeStarted=true; await new Promise(r=>setTimeout(r,800)); return original(...args)}}""")
                    page.get_by_role('button', name='Reprendre les couleurs de la photo').click()
                    page.wait_for_function('window.decodeStarted === true')
                    manual.fill('#cc1122')
                    page.wait_for_timeout(1000)
                    expect(palette).to_contain_text('#CC1122')
                    page.evaluate('window.restoreBitmap()')
                    # Failure is visible and a manual colour recovers without any image call.
                    page.route('**/api/product-inputs/*', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":{"code":"service_down","message_fr":"Analyse indisponible","retryable":true}}'))
                    page.get_by_role('button', name='Reprendre les couleurs de la photo').click()
                    expect(page.locator('.product-palette [role=alert]')).to_be_visible()
                    expect(page.get_by_role('button', name='Générer l’affiche', exact=True)).to_be_disabled()
                    manual.fill('#334455')
                    expect(palette).to_contain_text('#334455')
                    assert not requests
                    page.unroute('**/api/product-inputs/*')
                    page.get_by_role('button', name='Reprendre les couleurs de la photo').click()
                    expect(palette).to_contain_text('#202020')
                    assert page.evaluate("localStorage.getItem('affiche.palette.' + location.hash.slice(1))") is None
                    page.get_by_role('button', name='Générer l’affiche', exact=True).click()
                    page.get_by_role('button', name='Lancer la génération', exact=True).click()
                    expect(page.get_by_role('heading', name='Vérifier la fidélité du produit')).to_be_visible(timeout=30000)
                    page.get_by_role('button', name='Tout est conforme, approuver').click()
                    expect(page.get_by_role('button', name='Vérifier l’aperçu final', exact=True)).to_be_enabled()
                    creation = page.request.get(smoke.ORIGIN + '/api/creations/' + url.split('#')[1]).json()
                    scene = creation['document']['formats']['feed']['scene']
                    visual = page.request.get(smoke.ORIGIN + '/api/visuals/' + scene['visual_id']).json()
                    assert visual['headline']['brand_in_title'] is True
                    assert visual['headline']['price_ar'] == 1150000
                    assert visual['logo_box']['x'] == 54
                    plan = page.request.get(smoke.ORIGIN + '/api/plans/' + requests[-1]['plan_id'])
                    assert plan.ok, plan.text()
                    assert plan.json()['plan']['palette'][-1] == '#202020'
                    page.get_by_role('tab', name='Boutique', exact=True).click()
                    page.get_by_role('button', name='En haut à droite', exact=True).click()
                    expect(page.get_by_role('button', name='Vérifier l’aperçu final', exact=True)).to_be_disabled()
                    page.get_by_role('tab', name='Textes', exact=True).click()
                    page.locator('.main-action .why').get_by_role('button', name='Ouvrir « Boutique »').click()
                    expect(page.get_by_role('tab', name='Boutique', exact=True)).to_have_attribute('aria-selected', 'true')
                    page.get_by_role('button', name='Rétablir la position et le cadrage').click()
                    expect(page.get_by_role('button', name='Vérifier l’aperçu final', exact=True)).to_be_enabled()
                    # A corner logo locks the crop: any other crop would block the export.
                    page.get_by_role('tab', name='Réglages', exact=True).click()
                    for name in ('Zoom', 'Position horizontale', 'Position verticale'):
                        expect(page.get_by_label(name, exact=True)).to_be_disabled()
                    expect(page.get_by_text('Le cadrage est verrouillé', exact=False)).to_be_visible()
                    page.reload()
                    page.get_by_role('tab', name='Boutique', exact=True).click()
                    expect(page.get_by_role('button', name='En haut à gauche', exact=True)).to_have_attribute('aria-pressed', 'true')
                    for width, height in ((390, 844), (360, 740), (320, 640)):
                        page.set_viewport_size({'width': width, 'height': height})
                        page.evaluate('scrollTo(0, 0)')
                        expect(page.get_by_role('button', name='Masquer l’aperçu')).to_be_visible()
                        page.get_by_role('button', name='Masquer l’aperçu').click()
                        expect(page.locator('#poster-proof')).to_be_hidden()
                        for tab in page.get_by_role('tab').all():
                            tab.click()
                            expect(tab).to_have_attribute('aria-selected', 'true')
                            assert tab.evaluate('(e) => {const r=e.getBoundingClientRect(); return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
                        expect(page.get_by_role('button', name='Vérifier l’aperçu final', exact=True)).to_be_enabled()
                        smoke.check_contrast(page, f'compact controls {width}x{height}')
                        page.screenshot(path=str(out / f'controls-{width}.png'))
                        page.get_by_role('button', name='Afficher l’aperçu').click()
                        expect(page.locator('#poster-proof')).to_be_visible()
                        page.get_by_role('button', name=re.compile(r'^Versions ')).click()
                        expect(page.get_by_role('button', name=re.compile(r'^Choisir la version 1'))).to_be_visible()
                        assert page.locator('.versions').evaluate('(e) => parseFloat(getComputedStyle(e).paddingLeft)') >= 4
                        page.get_by_role('button', name=re.compile(r'^Versions ')).click()
                    # The preview starts expanded; a keyboard-sized viewport shrinks it to the 96 px strip (user decision 2026-11-14).
                    page.get_by_role('tab', name='Textes', exact=True).click()
                    field = page.get_by_label('Prix en ariary', exact=True)
                    field.focus()
                    page.set_viewport_size({'width': 360, 'height': 282})
                    expect(page.locator('#poster-proof')).to_be_visible()
                    page.wait_for_function("() => {const h=document.querySelector('.poster-canvas canvas')?.getBoundingClientRect().height; return h > 80 && h <= 100}")
                    expect(page.locator('.preview-tools')).to_be_hidden()
                    expect(field).to_be_in_viewport(ratio=1)
                    page.wait_for_function("""() => {const e=document.activeElement; return e?.name === 'price' &&
                      e.getBoundingClientRect().top >= parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sticky-top'))}""")
                    assert field.evaluate('(e) => {const r=e.getBoundingClientRect(); return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
                    page.screenshot(path=str(out / 'keyboard-282.png'))
                    field.blur()
                    # Out of the field the preview tools come back; on the short screen they open the poster large.
                    expect(page.get_by_role('button', name='Aperçu plein écran')).to_be_visible()
                    page.set_viewport_size({'width': 1366, 'height': 900})
                    # A historical footer plan has no corner marker. Selecting it restores its own geometry.
                    expect(page.get_by_text('Enregistré', exact=True)).to_be_visible()
                    endpoint = smoke.ORIGIN + '/api/creations/' + url.split('#')[1]
                    saved = page.request.get(endpoint).json()
                    original_logo = next(l for l in saved['document']['formats']['feed']['layers'] if l['role'] == 'logo')
                    original_logo.update(x=54, y=1152.9, width=129.6, height=129.6)
                    response = page.request.put(endpoint, data=saved['document'], headers={'Origin': smoke.ORIGIN, 'If-Match': f'"{saved["revision"]}"', 'Idempotency-Key': str(uuid4())})
                    assert response.ok, response.text()
                    page.reload()
                    page.get_by_role('button', name='Nouvelle version', exact=False).click()
                    page.get_by_role('button', name='Lancer la génération', exact=True).click()
                    expect(page.get_by_role('heading', name='Vérifier la fidélité du produit')).to_be_visible(timeout=30000)
                    page.get_by_role('button', name='Tout est conforme, approuver').click()
                    page.get_by_role('button', name=re.compile(r'^Choisir la version 1')).click()
                    page.get_by_role('tab', name='Boutique', exact=True).click()
                    expect(page.get_by_role('button', name='En haut à gauche', exact=True)).to_have_attribute('aria-pressed', 'true')
                    page.get_by_role('button', name=re.compile(r'^Choisir la version 2')).click()
                    expect(page.get_by_role('button', name='Vérifier l’aperçu final', exact=True)).to_be_enabled()
                    expect(page.get_by_text('Enregistré', exact=True)).to_be_visible()
                    saved = page.request.get(endpoint).json()
                    restored = next(l for l in saved['document']['formats']['feed']['layers'] if l['role'] == 'logo')
                    assert restored['y'] > 675 and restored.get('shape') != 'circle'
                    # A footer scene with its logo moved to the top: refused for export, and put back for free.
                    footer = page.get_by_role('button', name='En bas, comme cette version', exact=True)
                    expect(footer).to_have_attribute('aria-pressed', 'true')
                    page.get_by_role('button', name='En haut à gauche', exact=True).click()
                    expect(footer).to_have_attribute('aria-pressed', 'false')
                    expect(page.get_by_role('button', name='Vérifier l’aperçu final', exact=True)).to_be_disabled()
                    expect(page.locator('.panel .why', has_text='Rétablissez-les gratuitement')).to_be_visible()
                    page.get_by_role('button', name='Remettre le logo en bas', exact=True).click()
                    expect(footer).to_have_attribute('aria-pressed', 'true')
                    expect(page.get_by_role('button', name='Vérifier l’aperçu final', exact=True)).to_be_enabled()
                    expect(page.get_by_text('Enregistré', exact=True)).to_be_visible()
                    saved = page.request.get(endpoint).json()
                    assert next(l for l in saved['document']['formats']['feed']['layers'] if l['role'] == 'logo') == restored
                    # An explicitly missing detected seal disc must not fall back to a guessed footer position.
                    def missing_disc(route):
                        response = route.fetch()
                        body = response.json()
                        for item in body['items']:
                            item['logo_disc'] = None
                        route.fulfill(response=response, json=body)
                    page.route('**/api/creations/*/visuals', missing_disc)
                    page.reload()
                    page.get_by_role('button', name=re.compile(r'^Choisir la version 2')).click()
                    expect(page.get_by_text('Enregistré', exact=True)).to_be_visible()
                    assert page.request.get(endpoint).json()['document']['include']['logo'] is False
                    page.unroute('**/api/creations/*/visuals')
                    # A populated profile does not opt in on either a new form or reload.
                    page.goto(smoke.ORIGIN)
                    expect(page.get_by_label('Photos du produit')).to_be_enabled()
                    for reload in (False, True):
                        if reload:
                            page.reload()
                            expect(page.get_by_label('Photos du produit')).to_be_enabled()
                        for name in ('Logo', 'Contact', 'Nom de la boutique'):
                            expect(page.get_by_role('checkbox', name=name, exact=True)).not_to_be_checked()
                        expect(page.get_by_role('textbox', name='Contact', exact=True)).to_have_value('034 00 000 00')
                    assert not errors, errors
                    assert len(requests) == 2
                    assert page.request.get(smoke.ORIGIN + '/api/usage').json()['recorded_micros'] == 0
                    (out / 'results.json').write_text(json.dumps({'errors': errors, 'scene_calls': len(requests), 'visual': visual, 'viewports': [390, 360, 320, 640]}, indent=2))
                    browser.close()
            finally:
                vite.terminate()
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill()
                    vite.wait(timeout=10)
                smoke.stop(server, thread)
    print('Editor refinements production-build browser checks passed (stub only).')


if __name__ == '__main__':
    run()
