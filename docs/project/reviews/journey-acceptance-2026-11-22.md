# Poster journey release checks · 22 November 2026

T-JOURNEY-08 covers the [poster journey](../designs/saas-journey.md) and [first-poster guide](../designs/first-poster-guide.md). The tests use temporary shops, simulated image and Facebook providers, and the application's actual renderer and credit ledger.

## Feedback from the owner

The owner reported that it was difficult to reach the end and identified the first sticking point as “Before generation, while entering the product or choosing a format”. The route, device and completion outcome were not reported. The revised Message entry labels the photo control on a phone, gives a concrete offer example and explains the default format. The Pas à pas form groups the required product details, defers optional shop identity and explains the destination of the selected format. On 23 November the owner reported that the single review worked, but that confirmation happening only on download or preparation of the Facebook post was confusing. The device and final sharing destination were not specified. The revised labels name the confirmation, and « Confirmer pour plus tard » keeps the reviewed file in the library.

## Local results before the single-review amendment

All 1,944 default backend tests passed. The default test selection excludes the three opt-in cutout model tests. [Backend run](../../../outputs/journey08/backend-pytest.log)

| Path | Evidence |
| --- | --- |
| Accueil, account, credits and conditions | Dashboard and terms Chromium walks passed, including failed section reads, a session change, deferred terms, signed-out access to « Vos données », the simulated OAuth callback and PNG download after deferral. |
| Message, scene review and file | The review targets the selected visual and revision. The chat regression checks the balance across preparation of the matched file. The editor and sharing checks compare downloaded bytes with the exact PNG that was reviewed. Historical-file and changed-price cases run separately. |
| Sharing or publishing | Sharing and publishing Chromium walks passed with isolated providers. Native-share failure leaves PNG available. A denied Facebook reconnection preserves the two ordered image IDs, description, original send key and post count. All 92 Facebook API and posting tests passed, including agreement between the picker and exclusions when an alternative image is pending. |
| Operator recovery | All eight operator Chromium walks passed, including cancelling a discard, resolving a kept grant and verifying ledger effects. The discard dialog now identifies the affected shop and original reference inside the dialog. |
| Screen-reader output | GNOME Orca 50.3 read all five French step headings separately via Chromium and AT-SPI. The English discard dialog announced the shop, reference and local effect. Generated speech text was captured on an isolated desktop using a silent output module. [Speech excerpt](../../../outputs/journey08/assistive/screen-reader.txt) · [Chromium accessibility tree](../../../outputs/journey08/assistive/accessibility-tree.json) |
| Short chat viewport | A failed autosave had placed a sticky alert over « Envoyer ». The alert now occupies space within the chat. Keyboard dismissal returns focus to the composer and a retry preserves the typed message. [360 × 400](../../../outputs/journey08/chat-short-360x400.png) · [desktop](../../../outputs/journey08/chat-save-error-1366.png) |
| Responsive screens | 24 shop and operator screens were captured at 360, 768 and 1440 CSS px in each theme. All 144 captures passed the document-width overflow check. [Contact sheets](../../../outputs/design-capture/journey08/sheets/) · [Message](../../../outputs/design-capture/journey08/client-message-360-light.png) · [Format in Pas à pas](../../../outputs/journey08/intake/after-format-360.png) |
| Revised product entry | The production build, all 383 frontend unit tests and the complete Message, guide and editor browser walks passed. In Pas à pas, keyboard-only use retained a shop name after opening and closing the optional section. Selecting Carré updated its download hint. The editor walk verified all three formats, two-shop sign-out and credit recovery. At 360 × 640, the preparation button moved 460 px higher. [Before](../../../outputs/journey08/intake/before-intake-360.png) · [After](../../../outputs/journey08/intake/after-intake-360.png) · [Editor run](../../../outputs/journey08/editor_browser.log) |

To reproduce the automated checks, build the frontend with `corepack npm@10 run build` and run `corepack npm@10 test`. From backend use `.venv/bin/python ../frontend/tests/design_capture.py journey08` for the visual set and run the relevant `*_browser.py` suites against the built frontend. Separate concurrent suites with distinct `SMOKE_WEB_PORT` and `SMOKE_API_PORT` pairs. Run `.venv/bin/python -m pytest -q tests/test_facebook_api.py tests/test_facebook_posts.py` for the picker and publishing contract.

## Observed first use

The separate [local observation shop](http://127.0.0.1:5526/) has two empty shops and a returning shop with two offers. The ordinary [development shop](http://127.0.0.1:5273/) retains its own data. The observation shop listens on this computer's loopback interface. The facilitator has the temporary credentials in the private local file `/tmp/doka-journey08-trial/acces.txt`.

Give the participant only the brief, matching shop access and product photo. Let them find any help inside the shop. Use a fresh browser profile for each new participant. A second run in a shop already used by a participant measures repeat use.

| Trial | Brief for the participant | What the facilitator records |
| --- | --- | --- |
| First poster, Message · `essaimessage` | « Votre offre est un téléphone noir 128 Go à 899 000 Ar. À partir de cette photo, préparez une affiche que vous pourriez montrer à un client. Gardez l’image sur cet appareil. Commencez dans Message. » | Time to first generation and download, comparison with the supplied offer, any wrong price approved, unnecessary backtracking, use of Aide, first point that required a prompt, and whether the saved PNG opens. |
| First poster, Pas à pas · `essaiguide` | Give the same brief and photo to a new participant. End the brief with « Commencez dans Pas à pas. » | Use the same measures, including whether they noticed the generation cost, compared the finished image to the product and price, and saved the reviewed file in one action. |
| Returning seller · `originalphone` | « Préparez une publication pour la Page d’essai avec le téléphone bleu en premier et le noir en second. Utilisez la description “Nos deux offres”. Arrêtez-vous quand vous pouvez vérifier ce qui sera envoyé. » | The black file is already confirmed. The blue scene still needs its finished image checked. Record whether the seller can add that reviewed image to the draft and identify the Page and image order before the public send. A separate simulated-send check can then be observed. |

The supplied [black phone](../../../backend/fixtures/examples/phone-noir.jpg) and [blue phone](../../../backend/fixtures/examples/phone-bleu.jpg) are example images with [fixture offers](../../../backend/fixtures/products.example.csv). To assess price-error detection, use a separate controlled trial with a known discrepancy and record both the reference price and the displayed price.

| Observation awaiting a person or device | Evidence to enter |
| --- | --- |
| First-time seller using Message and Pas à pas, returning seller preparing the post | Date, path, actual outcome, elapsed time, assistance and the seller's own words. |
| Operator identifying an uncertain grant | Whether they located the original shop, reference and history before deciding how to resolve the request. |
| Android Chrome with TalkBack and the on-screen keyboard | Phone, Android and Chrome versions, spoken focus order, reachable primary action and any lost input after closing help. |
| Actual phone sharing and first live Page post | Use the existing [device share results](share-poster-phones-2026-11-19.md) and the owner's pilot-release procedure for the live post. |

The observation service is `doka-journey08-trial.service`. Its local files are temporary. Stopping this service leaves the normal development shop running.
