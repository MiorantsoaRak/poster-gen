"""New creation paths, attachment edits, kit and branching through the real browser/API (stub images)."""
import re
import sys
from uuid import uuid4
from playwright.sync_api import expect
import free_creation_browser as free

OUT = free.smoke.ROOT / 'outputs/unified-creation'


def walk(browser, width, data):
    ctx, page, errors = free.open_free(browser, width)
    try:
        expect(page.get_by_role('button', name='Message', exact=True)).to_have_count(0)
        page.get_by_label('Votre message').fill('Mon brouillon reste ici')
        page.get_by_role('button', name='Pas à pas', exact=True).click()
        expect(page.get_by_role('heading', name='Préparons votre affiche')).to_be_visible()
        page.get_by_label('Que voulez-vous annoncer ?').fill('Une ouverture de boutique')
        page.get_by_label('Textes et prix à écrire').fill('Bienvenue à Tana')
        page.get_by_label('Quel style souhaitez-vous ?').fill('Papier crème, typographie noire')
        page.screenshot(path=str(OUT / f'guided-{width}.png'))
        if width < 600:
            page.set_viewport_size({'width': 360, 'height': 850})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('button', name='Libre', exact=True).click()
        expect(page.get_by_label('Votre message')).to_have_value('Mon brouillon reste ici')
        page.get_by_role('button', name='Pas à pas', exact=True).click()
        expect(page.get_by_label('Que voulez-vous annoncer ?')).to_have_value('Une ouverture de boutique')
        page.get_by_role('button', name='Préparer ma demande').focus()
        page.keyboard.press('Enter')
        expect(page.get_by_label('Votre message')).to_have_value(re.compile('Bienvenue à Tana'))
        page.locator('.free-options summary').click()
        profile = page.request.get(free.smoke.ORIGIN + '/api/shop-profile').json()
        response = page.request.put(free.smoke.ORIGIN + '/api/shop-profile', data={
            'name': 'Boutique Tana', 'contact': '034 00 000 00', 'logo_asset': None, 'lines': []},
            headers={'Origin': free.smoke.ORIGIN, 'X-Affiche-Bundle': str(free.smoke.BUNDLE), 'Idempotency-Key': str(uuid4()), 'If-Match': f'"{profile["revision"]}"'})
        assert response.ok, response.text()
        # Reload obtains the latest kit. Test drafts separately above; ordinary navigation need not persist unsent text.
        page.reload()
        page.get_by_role('button', name='Libre', exact=True).click()
        page.locator('.free-options summary').click()
        page.get_by_label('Utiliser mon kit boutique').check()
        expect(page.locator('.free-options')).to_contain_text('Boutique Tana')
        page.get_by_role('button', name='Ajouter un logo', exact=True).click()
        page.get_by_label('Photos à joindre').set_input_files(free.file('logo.png', 'purple'))
        expect(page.locator('.pic-role.logo')).to_be_visible()
        expect(page.locator('.tray .pic[aria-busy]')).to_have_count(0)
        page.get_by_role('button', name='Ajouter une photo', exact=True).click()
        page.get_by_label('Photos à joindre').set_input_files(free.file('product.png', 'blue'))
        expect(page.locator('.tray .pic[aria-busy]')).to_have_count(0)
        page.get_by_role('button', name='Ajouter un modèle', exact=True).click()
        page.get_by_label('Photos à joindre').set_input_files(free.file('reference.png', 'gold'))
        expect(page.locator('.tray .pic[aria-busy]')).to_have_count(0)
        page.get_by_label('Utiliser ce modèle pour').select_option('style')
        page.screenshot(path=str(OUT / f'attachments-{width}.png'))
        page.locator('.free-options summary').click()
        free.say(page, 'Affiche de bienvenue. Aucun prix.').get_by_role('button', name='Lancer la génération').click()
        expect(page.get_by_role('log')).to_contain_text('Version 1 prête.', timeout=30000)
        id = page.url.split('#libre-')[1]
        url = free.smoke.ORIGIN + '/api/free-creations/' + id
        first = page.request.get(url).json()
        assert first['document']['reference_mode'] == 'style'
        assert first['document']['identity']['name'] == 'Boutique Tana'
        assert first['document']['identity']['logo'] and len(first['photos']) == 1
        stale = ctx.new_page()
        stale.route('**/api/free-creations/' + id, lambda route: route.fulfill(json=first))
        stale.goto(free.smoke.ORIGIN + '/#libre-' + id)
        expect(stale.get_by_role('log')).to_contain_text('Version 1 prête.')
        page.locator('.free-options summary').click()
        page.get_by_role('button', name='Retirer cette photo', exact=True).click()
        page.get_by_role('button', name='Ne pas utiliser ce logo').click()
        page.get_by_role('button', name='Ajouter une photo', exact=True).click()
        page.get_by_label('Photos à joindre').set_input_files(free.file('replacement.png', 'red'))
        expect(page.locator('.tray .pic[aria-busy]')).to_have_count(0)
        page.locator('.free-options summary').click()
        free.say(page, 'Utilise la nouvelle photo, sans logo.').get_by_role('button', name='Lancer la génération').click()
        expect(page.get_by_role('log')).to_contain_text('Version 2 prête.', timeout=30000)
        second = page.request.get(url).json()
        assert second['photos'] != first['photos'] and second['document']['identity']['logo'] is None
        before = page.request.get(free.smoke.ORIGIN + '/api/balance').json()['available']
        dialog = free.say(stale, 'Une modification depuis un onglet ancien')
        stale.unroute('**/api/free-creations/' + id)
        dialog.get_by_role('button', name='Lancer la génération').click()
        expect(stale.locator('.composer [role=alert]')).to_contain_text('Une version plus récente existe')
        expect(stale.get_by_label('Votre message')).to_have_value('Une modification depuis un onglet ancien')
        assert page.request.get(free.smoke.ORIGIN + '/api/balance').json()['available'] == before
        stale.close()

        page.get_by_role('button', name='Repartir de cette version', exact=True).first.click()
        expect(page.locator('.composer')).to_contain_text('Correction à partir de la version 1')
        free.say(page, 'Un fond plus clair.').get_by_role('button', name='Lancer la génération').click()
        expect(page.get_by_role('log')).to_contain_text('Version 3 prête.', timeout=30000)
        third = page.request.get(url).json()
        assert third['photos'] == first['photos']
        assert third['document']['identity'] == first['document']['identity']
        assert third['turns'][-1]['base_render_id'] == first['document']['render_id']
        page.screenshot(path=str(OUT / f'branch-{width}.png'))
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('.free-result').first.evaluate('e => getComputedStyle(e).animationName') == 'none'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        # Existing product documents remain accessible through their old Message links.
        headers = {'Origin': free.smoke.ORIGIN, 'X-Affiche-Bundle': str(free.smoke.BUNDLE)}
        def post(path, body):
            response = page.request.post(free.smoke.ORIGIN + path, data=body,
                                         headers={**headers, 'Idempotency-Key': str(uuid4())})
            assert response.ok, response.text()
            return response.json()
        product = post('/api/product-inputs', {'name': 'JBL', 'variant': 'Conforme à la photo', 'photo_assets': first['photos']})
        legacy = post('/api/creations', {'input_id': product['id'], 'offer': {'title': 'Ancienne affiche', 'price_ar': 120000},
                                      'brand_selection': {'logo': False, 'shop_name': False, 'contact': False}})
        page.goto(free.smoke.ORIGIN + '/#message-' + legacy['id'])
        page.wait_for_url('**/#' + legacy['id'])
        expect(page.locator('.poster-title')).to_have_text('Ancienne affiche')
        # A kit card actually seeds the new free composer, instead of changing an obsolete editor default.
        page.goto(free.smoke.ORIGIN + '/#styles')
        page.locator('.look-card').first.click()
        page.get_by_role('button', name='Créer une affiche avec ce style').click()
        page.wait_for_url('**/#libre')
        expect(page.get_by_label('Votre message')).to_have_value(re.compile('Direction visuelle'))
        page.goto(free.smoke.ORIGIN + '/#message')
        page.wait_for_url('**/#libre')
        expect(page.get_by_role('button', name='Message', exact=True)).to_have_count(0)
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('html').evaluate("e => getComputedStyle(e).scrollBehavior") == 'auto'
        assert not errors, errors
    finally:
        ctx.close()


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    free.walk = walk
    free.run(tuple(map(int, sys.argv[1:])) or (1366, 390))
