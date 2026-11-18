# DESIGN — Conditions of use and the owner's check (service-terms)

## System overview

**Status:** Approved v3, 2026-11-18 (autonomy grant, ADR-112): round-2 fixes applied (not reviewed again); the owner amended R-TERMS-003 on 2026-11-18 (deletion and message retention). Tasks T-TERMS-001 … 004 in TODO.md. v1 was rejected by Codex ([round 1](../reviews/service-terms-design-r1-2026-11-17.md)); v2 applied the lead's eight decisions; [round 2](../reviews/service-terms-design-r2-2026-11-17.md) approved v2 with fixes.
**Requirements file:** [../requirements/service-terms.md](../requirements/service-terms.md), v2 (R-TERMS-001 to 003; R-TERMS-002 decided by the user, ADR-111).
**Depends on:** [multi-shop](multi-shop.md), [prepaid-balance](prepaid-balance.md), [admin-dashboard](admin-dashboard.md) as built (migrations 0013 to 0016). Fourth feature of Release 1 « Invitation » (ROADMAP.md, ADR-105).

The conditions are a French text held in the backend's code with a version. A shop accepts them through its session, and its row keeps the version and the date. One function, `terms.require`, refuses a shop-service paid operation for a shop that has not accepted the current version. It runs after authentication, replay and ownership, and before the admission limits (the active image job, the twelve scenes, the pause, the cap, the day, the read limits) and the credit, so nothing is generated, sent or charged before acceptance. Two route-level limits come before it, accepted in round 2: `look_limit` and `adjustments_limit` (D-TERMS-003). The page asks at opening; the owner may postpone (« Plus tard »), and free work continues. Without acceptance nothing new is asked of the AI and no credit is taken. A fresh paid control asks again. The warning about features and the wording of the check are the page's, the same for every card and every version. A static page, `/donnees.html`, says by category what is kept and where it goes.

The parts: migration 0017 (two columns), `posters/terms.py`, two routes, one call site in each admission path, one dialog, one static page. No new table, dependency or paid call.

```
page opens ──GET /api/terms──▶ not accepted ──▶ dialog: « J'accepte » ──POST /api/terms──▶ shop_profile.terms_version, terms_accepted_at
                                                       « Plus tard » ──▶ free work; a fresh paid control opens the dialog again
paid request ──▶ boundary (session, shop, Origin, bundle) ──▶ replay? ──▶ ownership, the request's own checks
             ──▶ terms.require ──▶ limits ──▶ credit ──▶ job/read
                      └─ 403 terms_required: nothing written or sent
/donnees.html   static file of frontend/public: public, no script, not in the shops' bundle
```

## What changed from v2 (round 2)

- R2-1: owner decisions 4 and 5 are marked as blocking R-TERMS-003 until the owner amends it. The « Vos données » link on the account screen is added to the shop dashboard's requirement by the lead.
- R2-2: the page discloses the Claude composition through the plans API now.
- R2-3: « Lire les conditions » appears on a fresh card or an open paid sheet whose balance reason becomes `terms`, a late balance included. Retained requests keep same-key « Réessayer » / « Reprendre ». The dialog has « Réessayer » when its text cannot be fetched.
- R2-4: three wording fixes on the page: suspension, device erasure, the contact route.
- R2-5: the dialog counts in `modalOpen`; covered panels are inert; focus moves when the front dialog changes; keyboard tests.
- R2-6: the date column must be non-empty; the exact list of head assertions to update; SQLite 3.40.1 pending until the release rehearsal.
- Overview: the two route-level exceptions are named, the boundary comes before replay, and R-TERMS-001's wording is used for « Plus tard ».
- Tasks: four. The page work is split in two; the fixture sweep names the shops made outside `credited()`; the gate-removal mutations give way to the delayed-balance and retained-key cases.

## What changed from v1, and why

| Finding (round 1) | Disposition in v2 |
|---|---|
| 1, 2, 7, 8 — erasure races uploads; null pilot hash stops the API; erased state undefined; the 30-day backup promise exceeds the procedure | `erase` is not built in Release 1 (lead's decision 1). Its open problems are listed under "Not built". The page promises only what the operator can do today (owner decision 4) |
| 3 — a valid `false`, a replayed read or a restored card loses the warning | The `unlisted_features` field, its stub and the paid evaluation are removed. The page shows a lead-in and the required sentence on every actionable scene-adjustment card, restored and re-offered ones included, and in « Ajuster la scène » (D-TERMS-005) |
| 4 — limits checked before the guard hide `terms_required` | One function, called in `enqueue` and in the read's admission after ownership and before the active job, the twelve scenes, the pause, the cap, the day and the credit. `/api/balance` keeps 200 with a `terms` reason. Simultaneous refusals are tested. The claim is scoped to shop-service operations (D-TERMS-003) |
| 5 — the dialog blocks free work and covers its own sign-out confirmation; a `terms` balance reason sends no POST | « Plus tard »; no sign-out in the dialog; the sign-out confirmation stays in front; a paid control opens the dialog from the balance's `terms` reason; a lost answer says « L'acceptation n'a pas pu être confirmée » and reads again (D-TERMS-004) |
| 6 — `adjusted` describes how a scene was made; the check only shows for some renders | Flag removed. The `content` point and `extras_text` are broadened for every version; four confirmation keys unchanged; existing confirmations stay downloadable; saved preview pixels named as a limit (D-TERMS-006) |
| 9 — provider table mixes stored jobs with what is sent | Per operation, from the outbound functions; no counts, no removable negatives (D-TERMS-007) |
| 10 — retained data understated | The stored reading holds the instruction; job inputs, snapshots and saved answers hold the shop's name and contact; failed sign-ins keep identifier, address or prefix and time; the terms version; the journal; device downloads and caches. The mismatch with "messages' cost but not their text" is owner decision 5 |
| 11 — session claim, delayed GET, recovery sentence | The shop and session are checked again inside the acceptance transaction. A read older than a successful acceptance cannot reopen the dialog. The recovery sentence is corrected (D-TERMS-003) |
| 12 — migration proof; the "lost column asks again" claim | Claim removed. Tests on the full chain 0012→0017 and on a populated 0016 database; tests pinned to head 0016 move to 0017; no `SUPERSEDES` entry; SQLite 3.40.1 stays verified at the release rehearsal |
| 13 — task sizing | Three tasks: schema and API; the gate; the page. The operator's view of acceptance is deferred. The account-screen link becomes a shop-dashboard acceptance line. Mutations kept only where they guard money or the gate |
| Devil's advocate (no report file given to me; its points as relayed by the lead) | A much smaller design; no erasure in Release 1; the warning always shown rather than decided by a model; the dialog must not block free work, and must not offer sign-out (sign-out deletes the device's chat threads, api.ts:226-234) |

### What the code already gives (read 2026-11-17)

| Property | Where |
|---|---|
| A refusal inside `mutate` stores no key; a replayed key gets its stored answer before `apply` runs | store.py:42-57 |
| Every job route with a provider call goes through `enqueue`: scenes visuals.py:293, refinements :344, Claude plans :181-183, styles looks.py:84, text proposals typography.py:152, text materials :255. Renders reserve no call | jobs.py:37-41, :102-138 |
| In `enqueue`: provider config (:104), ownership and revision (:105-108), then the active image job (:109-112), the twelve scenes (:113-116), the mode lock, `_reserve` → `provider_guard` (suspension, pause, cap, day; jobs.py:63-77), then the credit (:136-137) | jobs.py |
| The chat read's admission: replay from its row first; ownership; then mode lock, `provider_guard`, read limit, reads busy | reads.py:552-600 |
| A 429 retry reserves call 2 through `provider_guard` only | jobs.py:242-256 |
| `/api/balance` re-raises a guard refusal that `BLOCKED` does not map; the page stops a charged control on any `blocked` entry | api.py:162, :528-533; generation.ts:59-63 |

---

## D-TERMS-001 — The text and its version (covers R-TERMS-001)

`backend/src/affiche/posters/terms.py` holds `VERSION` (the text's date, ISO, at most one a day), `PARAGRAPHS_FR` and `NO_CONTACT_FR`. `paragraphs(settings)` puts `SUPPORT_CONTACT_FR` (config.py:57), else the fallback, in place of `{contact}` with `replace`, never `format`. It also holds `require` (D-TERMS-003) and `accept` (D-TERMS-002), and imports only `text` and `store.Refused`, so jobs.py and reads.py can import it.
- **Not in the database:** a stored text needs a writer, has no git history, and a restore could pair an older text with a newer version. The text changes only with a release, and a constant costs nothing at each admission.
- **Not in the bundle:** the page shows the server's words of now, whatever the tab's age.
- A test pins the SHA-256 of the joined paragraphs to `VERSION`: a word changed without a new date fails it.
- The contact is not part of the version; changing it asks nobody again.

## D-TERMS-002 — Acceptance: migration 0017 and the API (covers R-TERMS-001)

```sql
-- 0017_terms_acceptance.py, forward-only, hand-written STATEMENTS as 0014 to 0016
ALTER TABLE shop_profile ADD COLUMN terms_version TEXT CHECK (terms_version IS NULL OR length(terms_version) BETWEEN 1 AND 32);
ALTER TABLE shop_profile ADD COLUMN terms_accepted_at TEXT
  CHECK ((terms_accepted_at IS NULL) = (terms_version IS NULL) AND (terms_accepted_at IS NULL OR length(terms_accepted_at) > 0));
```
- **No backfill:** the pilot accepts like every shop.
- **Rehearsal contract:** `PRESERVED = {"shop_profile": (the ten 0013 columns)}`; `ADDED = {"shop_profile: nothing accepted": ("SELECT count(*) FROM shop_profile WHERE terms_version IS NOT NULL OR terms_accepted_at IS NOT NULL", [(0,)])}`.
- `GUARDS` is unchanged (fourteen guard lines) and no `SUPERSEDES` entry is needed (rounds 1 and 2). A later rebuild of `shop_profile` must carry both columns; without them the gate's query fails. That migration's own rehearsal contract is the check.
- The rehearsal takes the earliest pending projection: from 0012 it hashes the six old shop columns, from a populated 0016 all ten.
- Checked on SQLite 3.46.1 here, the tightened CHECK included: a half-NULL pair, an empty version and an empty date are refused. **SQLite 3.40.1 is pending until the release rehearsal.**
- **One record per shop:** the last acceptance (owner decision 1).

```
GET  /api/terms   session
  200 { "version": "2026-11-17", "paragraphs_fr": [str…], "accepted_at": str|null, "changed": bool }
      accepted_at: of the current version, else null; changed: an earlier version was accepted
POST /api/terms   session; Origin; X-Affiche-Bundle; body { "version": str 1–32 }; no Idempotency-Key
  200 { "version": …, "accepted_at": … }
  409 terms_outdated · 401 unauthenticated · 403 forbidden_origin · 409 bundle_outdated · 503 storage_unavailable
```

`terms.accept`, in one `write_tx`:
1. Check the session again: the token's row live and its shop active and equal to `request.state.shop`. The query of `auth.session_shop` (auth.py:77-83) becomes `auth.live_shop(conn, token)`, used by both. A miss is 401 with nothing written: the session was read before the transaction (api.py:245-249).
2. `version != VERSION` → 409 `terms_outdated`, nothing written.
3. `UPDATE … SET terms_version=:v, terms_accepted_at=:now WHERE id=:shop AND terms_version IS NOT :v`, then read the date. Sent twice, or by two devices at once, it answers the first date.

Acceptance belongs to the shop: whoever signs in with its password accepts for it, and the conditions say so (owner decision 8).

## D-TERMS-003 — The gate at admission (covers R-TERMS-001)

`terms.require(conn, shop)` reads `terms_version` and raises `Refused("terms_required", 403)` when it is not `VERSION`. It is the only comparison, and it has three callers:

| Caller | Where it runs | What comes after it |
|---|---|---|
| `jobs.enqueue`, when the kind has a call spec | after ownership, revision and abandonment (jobs.py:105-108) | the active image job, the twelve scenes, the mode lock, `provider_guard` (suspension, pause, cap, day) and the credit |
| `reads._admit`, for a new read | after ownership and the poster's words (reads.py:563-572) | the mode lock, `provider_guard`, the read limit and reads busy |
| `jobs.blocked` | first | `provider_guard` |

- **Precedence:** the HTTP boundary (session, shop, Origin, bundle; api.py:234-263); replay; the route's own checks; `call_spec`'s configuration (503); ownership; **terms**; the common admission limits; the credit.
- **Two route limits come before the gate, accepted in round 2:** a style beyond `look_limit` (looks.py:81-82) and a chain beyond `adjustments_limit` (visuals.py:67-79, called at :265, :324). Each refuses before `enqueue`, takes no credit and sends nothing. A gate in every route would change the error message without strengthening the guarantee. Two tests keep the order.
- **Nothing is taken:** the refusal raises inside `mutate`, or inside the read's transaction, before any job, call, key, read row or credit. Nothing reaches a provider.
- **`/api/balance`** stays 200: `BLOCKED` gains `"terms_required": "terms"`. Each charged kind then reads `{"reason": "terms", "message_fr": …}`.
- **Scope: shop-service operations** (scenes, refinements, text materials, Claude plans, styles, text proposals, chat reads). The operator's evaluation CLI keeps its own admission.
- **Three cases stay distinct:** a **replay** of an admitted key gets its stored answer (store.py:42-57; reads.py:593-600); **the internal 429 retry** reserves call 2 through `provider_guard`, where the gate is not; **a new attempt after a failed job** is a new key, a new admission, refused until acceptance.
- **Jobs admitted before a new version** are not admitted again. At the restart, recovery finalises a spooled result, requeues a job whose call was not sent, and marks one whose call may have been sent `interrupted`, with its credit back (jobs.py:315-341). Queued jobs run.
- `MESSAGES` gains `terms_required` and `terms_outdated`. `terms_required` is not in the chat's final list (chat.ts:151-155): a refused card keeps its request and « Réessayer ».

## D-TERMS-004 — The dialog (covers R-TERMS-001)

**When it opens:**
- **At opening:** App.vue reads `GET /api/terms` when the shop's page opens (`openShop`, App.vue:1563-1570), after a sign-in or on an existing session, apart from the other loads as the balance is (App.vue:868). A failed read at opening shows nothing; the server still refuses.
- **A fresh request whose balance reason is `terms`.** `credit()` (generation.ts:59-63) returns `terms: true` when the entry's reason is `terms`. No ask function checks the conditions itself, so the recovery of an admitted request is never intercepted.
  - **The chat:** `cardButton` (chat.ts:246-257) gains the action `conditions` for a paid card not yet tapped (`!item.spent`) when the stop's reason is `terms`. Today `stop` removes « Créer » and leaves nothing; the card now shows « Lire les conditions », which calls a new adapter function, `conditions()`.
  - **The editor:** the paid sheet opens before `readBalance()` answers (App.vue:653-657). Whenever `paidCost` stops for `terms` on a request that is not `again`, the sheet's row (App.vue:1875) shows « Lire les conditions » beside « Fermer », even if the balance arrived after the sheet opened. The button closes the sheet and opens the dialog.
- **A retained request** keeps its same-key action: « Réessayer » or « Reprendre » in the chat (chat.ts:254), and the sheet's `again` path with `ONCE` in the editor. It is sent as it is. The server replays an admitted key (its stored 202), or refuses a never-admitted one with 403, which opens the dialog.
- **From a refusal:** api.ts's `request()` (api.ts:179-182) bumps an exported `termsAsked` counter on `terms_required`. App then reads again and opens the dialog. This covers the free-of-credit Claude buttons, chat messages, a stale balance and a refused retained request. A refused chat message gives its text back to the field: ChatView.vue:258 gains `terms_required`.
- **Text not available:** when the dialog is opened by one of these and its paragraphs cannot be fetched, it says « Les conditions n'ont pas pu être chargées. » with « Réessayer » beside « Plus tard ».

**What it holds:** a `v-modal` section with `role="dialog"`. Inside: « Conditions d'utilisation » (« Les conditions d'utilisation ont changé » when `changed`), « Version du 17 novembre 2026 », the paragraphs by interpolation, the link « Vos données » (new tab), « J'accepte » and « Plus tard ». No sign-out button: sign-out deletes the device's chat threads (api.ts:226-234).

**Modal priority and focus.**
- The dialog counts in `modalOpen` (App.vue:672), so the header is inert.
- The panels it covers (review, style, final preview) are inert while it is open.
- It is itself inert while `paid` is open, so that the sign-out confirmation (App.vue:1597, which uses `paid`) stays in front.
- `v-modal` focuses only on mount (App.vue:632-635). One watcher on "the front panel" (`paid`, then the conditions, then the other panels) focuses that panel whenever it changes: when the dialog opens over an open review, and when `paid` closes over the dialog.
- « Plus tard » returns focus to the panel below, or to the control that opened the dialog.

**After « Plus tard »:** the owner postpones, and free work continues: editing, the review, the final preview, confirming and downloading, and following or replaying a request already admitted. Without acceptance nothing new is asked of the AI and no credit is taken. Nothing is stored; the page's next opening asks again.

**After « J'accepte »:**
- 200 closes the dialog and reads the balance again.
- 409 shows the new text with its sentence.
- A network failure or 5xx says « L'acceptation n'a pas pu être confirmée. », reads `GET /api/terms` again, and closes if the shop accepted.
- **A read older than the acceptance cannot reopen the dialog:** reads and the acceptance share one turn counter, and only the latest answer applies (the rule of `balanceTurn`, App.vue:35-38).

**The pilot:** 0017 accepts nothing. The dialog shows at his first opening after the release; his session lasts. Release steps (deploy/README.md "Release 1"): set `SUPPORT_CONTACT_FR`; tell the pilot.

## D-TERMS-005 — The warning before the paid tap (covers R-TERMS-002)

Shown by the page, always; no server change.
- `generation.ts` holds `FEATURES_WARNING`: the lead-in, then the required sentence (French texts).
- **The chat:** every scene-adjustment card shows it above its button while it is actionable: a card whose effect is `refine` (chat.ts:233) and that is not `done`. That includes the first offer, a card restored from the device, a card re-offered after a refusal (ChatView.vue:357-366), and « Réessayer » / « Reprendre ». A card read before this change shows it too: the page adds it, not the stored answer.
- **« Pas à pas »:** the « Ajuster la scène » dialog (App.vue:653-657) shows it before « Lancer l'ajustement ».
- Other cards send no adjustment: a word change drops it (reads.py:374, :428-429), and the new-poster reader carries none. A word change that redraws a version with earlier adjustments is covered by the check (D-TERMS-006).
- ADR-111 quotes the bare sentence; the conditional lead-in is owner decision 2.

## D-TERMS-006 — The check before download (covers R-TERMS-002)

**Server: unchanged.**
- Approval needs `extras_text` and every point (visuals.py:108-116, :427).
- Export needs approval (exports.py:31-38).
- Confirmation needs its four keys and every warning (exports.py:164-174).

**Page: one wording for every version and every render** (owner decision 3):
- `checkNames.extras_text` (App.vue:21), the review's « Aucun autre texte que ceux ci-dessus » (App.vue:1910) and `finalPoints.content` (App.vue:333) are reworded so that they are true for a version made with or without the owner's request for features.
- The confirmation's keys stay `framing`, `content`, `identity`, `readability`.

**Existing confirmations stay downloadable:** `exports.download` reads the confirmation and its file only (exports.py:185-190). Their stored `checks` hold keys, not labels.

**Named limit (owner decision 7):** the review and the check link to the full images (App.vue:1880, :1906). A phone can save those pixels without approving or confirming. The check guarantees the confirmed download, not the pixels on the screen.

## D-TERMS-007 — « Vos données » (covers R-TERMS-003)

**Where:** `frontend/public/donnees.html`. Vite copies it to `dist/donnees.html`; the static mount serves it without a session, `no-cache` (api.py:209-211, :910-912). The admin build does not copy `public/`.
- It holds French text, inline CSS for both themes, no script, nothing from outside.
- **Links:** the sign-in screen (App.vue:1679, same tab) and the dialog (new tab). The account screen does not exist yet (shop-dashboard.md:5). Its « Vos données » link is added to the shop dashboard's requirement (R-SHOP-DASH-003) by the lead, not by this design, and is verified there from a signed-in shop that has already accepted. Today's line in that requirement links the conditions, a different page.

**Content, by category, from the code that writes or sends:**

| Statement | Where |
|---|---|
| The shop: identifier, name, logo, contact, password as a hash, accepted version and date | 0013; 0017; shops.py:384 |
| Photos as sent, with the phone's metadata; the copies sent out have none | store.py:107, :118; gateway.py:90-122; service.py:38-53 |
| Posters: texts, versions, final files | exports.py:124, :179 |
| Each AI request and its cost; image requests keep the poster's words, the shop's name and contact when drawn, the adjustments word for word; saved answers keep documents with the shop's snapshot | jobs.py:126-131; visuals.py:249-254, :284, :314, :336; store.py:57 |
| Each chat read: its cost and the answer, which may repeat the owner's words up to the whole instruction | reads.py:370-371, :619-629 |
| Credits with payments' amount, method, reference | 0014 |
| Sessions for a limited time; a failed sign-in's identifier, address or IPv6 prefix, and time | auth.py:32, :86-96, :173-174 |
| The server's journal: technical events, the operator's actions with the shop's identifier | admin.py:99-103; api.py:299 |
| Backups of the database and the images, on the same server | backup.py:28-38; deploy/README.md:530-540 |
| On the device: chat threads and words in progress until « Se déconnecter », whose failed cleanup the sign-in screen reports; downloads and the browser's image cache stay | api.ts:226-234; App.vue:1679; api.py:376 (a year's cache) |
| Suspension blocks new requests; one already past its last check can still reach the provider and finish | shops.py:132; worker.py:57; reads.py:657 |
| Sent, per operation (below), the Claude composition included: a signed-in shop can ask for it through the plans API, which sends the prepared product photos and the composition context, though no screen sets it (App.vue:50) | service.py:38-106; plans.py:509-516; typography.py:157-163, :249-255; reads.py:631-647; looks.py:90-94; api.py:560-562 → visuals.py:181-183 → service.py:88-93 |

---

## French texts (drafts, waiting for the user's reading)

No price, phone number, legal entity, law, count or duration is written. A jurist has read none of this.

**The conditions** (`PARAGRAPHS_FR`; the dialog's buttons are « J'accepte » and « Plus tard »):
1. « Ce service fabrique vos affiches avec une intelligence artificielle (IA). L'IA peut se tromper : un mot mal écrit, un prix déformé, un détail du produit inexact, une caractéristique que le produit n'a pas, un logo de marque mal dessiné. »
2. « Avant d'utiliser une affiche, vous vérifiez chaque mot, chaque prix, chaque caractéristique et chaque logo ou marque. Si vous demandez des caractéristiques sans les écrire, l'IA les choisit, et elles peuvent être fausses. Ce que vous publiez reste sous votre responsabilité. »
3. « Les crédits se paient à l'avance. Un crédit sert à une image : une nouvelle version de l'affiche, un ajustement de la scène ou la matière d'un texte. Si l'image n'a pas pu être faite, le crédit vous est rendu. Une image faite n'est pas remboursée, même si elle ne vous convient pas. »
4. « Ces conditions valent pour la boutique. Toute personne qui se connecte avec l'identifiant et le mot de passe de la boutique agit en son nom : ne les confiez qu'à des personnes de confiance. »
5. « Ce que le service garde de vos photos et de vos messages, et ce qu'il envoie à d'autres services, est expliqué sur la page « Vos données ». »
6. « Si ces conditions changent, la nouvelle version vous sera montrée ; il faudra l'accepter avant de demander quoi que ce soit de nouveau à l'IA. »
7. « Une question, un problème, une demande sur vos données : contactez {contact}. » — fallback contact: « l'opérateur qui vous a remis votre identifiant ».

**Sentences:**

| Key | Sentence |
|---|---|
| `terms_required` | « Acceptez d'abord les conditions d'utilisation : rien n'a été envoyé, et aucun crédit n'a été pris. » |
| `terms_outdated` | « Les conditions viennent de changer : lisez la nouvelle version avant de l'accepter. » |
| lost answer | « L'acceptation n'a pas pu être confirmée. » |
| `FEATURES_WARNING` | « Vous demandez des caractéristiques sans les lister ? L'IA choisira les caractéristiques : vérifiez-les avant de publier. » (the lead's example lead-in, « Si vous demandez des caractéristiques sans les lister : », would put two colons in one sentence) |
| chat card button | « Lire les conditions » |
| `extras_text` | « Rien d'ajouté par l'IA sans votre demande, et ce qu'elle a ajouté est exact pour ce produit » |
| review, texts group | « Aucun autre texte, sauf ceux que vous avez demandés à l'IA » |
| `content` | « Tous les textes sont exacts : le titre, le prix, et chaque mot, chiffre ou caractéristique ajouté par l'IA » |

**« Vos données »:**
- *Ce que le service garde, tant que la boutique existe.*
  - La boutique : son identifiant, son nom, son logo, son contact, la version des conditions acceptée et sa date. Le mot de passe est gardé sous une forme qui ne permet pas de le relire.
  - Les photos que vous envoyez, telles que vous les envoyez, avec les informations que le téléphone y a mises (parfois le lieu de la prise de vue).
  - Les affiches : leurs textes, chaque version faite par l'IA et les fichiers finaux.
  - Chaque demande faite à l'IA et son coût. Une demande d'image garde les textes de l'affiche, le nom et le contact de la boutique quand ils y figurent, et vos demandes d'ajustement mot pour mot.
  - Chaque message lu dans « Par message » : son coût et la réponse de l'application, qui peut reprendre vos mots, jusqu'à votre demande entière.
  - Les crédits : chaque crédit reçu, dépensé ou rendu ; pour un paiement, son montant, son moyen et sa référence.
  - Pour la sécurité : la connexion de chaque appareil, pour une durée limitée ; pour une connexion manquée, l'identifiant saisi, l'adresse IP (ou son début) et l'heure. Le journal du serveur garde des traces techniques, dont les actions de l'opérateur avec l'identifiant de la boutique.
  - Des copies de secours de la base et des images, sur le même serveur, loué par l'opérateur (Hetzner).
- *Sur votre appareil.* La conversation de « Par message » et vos textes en cours restent dans ce navigateur ; « Se déconnecter » les efface de cet appareil. Si l'effacement échoue, l'atelier vous le signale. Les affiches téléchargées et les images gardées par le navigateur restent sur l'appareil.
- *Ce qui part vers d'autres services.* Les images envoyées sont des copies, sans les informations du téléphone.
  - « Générer l'affiche », « Nouvelle version », « Créer l'affiche » : OpenAI reçoit les photos du produit, l'image d'inspiration s'il y en a une, et une demande écrite : le nom du produit, le style, les textes à dessiner (dont le contact de la boutique s'il est dessiné) et les ajustements de scène demandés avant, s'il y en a.
  - « Ajuster la scène », ou un changement de la scène par message : OpenAI reçoit aussi la version de départ et votre demande, mot pour mot.
  - « Générer la matière du texte » : OpenAI reçoit la description d'une matière et ses couleurs.
  - Un message dans « Par message » : Anthropic (Claude) reçoit le message, les dernières lignes de la conversation, et le produit, le prix et le style en cours, ou les textes de l'affiche.
  - « Créer un style » : Anthropic reçoit l'affiche modèle.
  - « Proposer un ajustement » : Anthropic reçoit le texte choisi, son réglage et votre consigne.
  - Si la composition est demandée à Claude, Anthropic reçoit aussi les photos du produit et les indications de composition.
  - Ces services traitent ce qu'ils reçoivent selon leurs propres conditions.
- *Effacer vos données* (owner decision 4). Demandez-le à l'opérateur. Il peut suspendre la boutique tout de suite : plus personne ne peut s'y connecter. La suspension bloque les nouvelles demandes. Une demande déjà lancée peut encore aboutir. Il vous dit ensuite ce qui peut être effacé, et quand. Pour le joindre : l'opérateur qui vous a remis votre identifiant.
- « Retour à l'atelier »

---

## Edge cases and failure modes

| Case | What happens |
|---|---|
| Version changes between the read and the tap | 409 `terms_outdated`; nothing written; the new text is shown |
| Two devices accept at once | serialised by `BEGIN IMMEDIATE`; one write; both get the first date |
| Suspended, or session ended, between the boundary and the write | 401 inside the transaction; nothing written |
| Acceptance committed, answer lost | « L'acceptation n'a pas pu être confirmée. »; the read finds it accepted; sending again answers the same date |
| A delayed `GET /api/terms` after a successful acceptance | ignored (turn counter) |
| `GET /api/terms` fails at opening | no dialog; free work; the first fresh paid control (balance reason or 403) opens it; if its text still cannot be fetched, « Réessayer » beside « Plus tard » |
| The balance answers after the paid sheet opened, with reason `terms` | the sheet shows « Lire les conditions » beside « Fermer » |
| A request admitted, its 202 lost, then a new version | « Reprendre » sends the same key: the stored 202 comes back, the job is followed, no dialog |
| A retained request never admitted, then a new version | the same key is refused 403; the dialog opens; « Réessayer » after acceptance is its first admission |
| A late 403 while a review is open | the dialog comes in front, focused; the review is inert; « Plus tard » returns focus to the review |
| Sign-out confirmation open and a late 403 arrives | the confirmation stays in front with focus; the dialog behind is inert, and is focused when the confirmation closes |
| A restore older than an acceptance | the shop is asked again |
| Database busy during acceptance | 503; nothing written; the dialog stays |

## Security

- `/api/terms` takes no id: always the session's shop, checked again in the write.
- The paragraphs are shown by interpolation (no `v-html` in frontend/src).
- `/donnees.html` holds no data and runs no script.
- test_two_shops.py: both routes join `OWN`. A's acceptance does not admit B.

## Tasks and tests

Four tasks, one session each. Commands run from `backend/`; on Linux the frontend's npm is `corepack npm@10 …`. Generated fixtures only, never `data-probe`.

**T-TERMS-001 — Migration 0017, `terms.py`, `GET`/`POST /api/terms`.** Also `auth.live_shop`, `terms_outdated`, test_two_shops.py `OWN`, backend/api/README.md.

| Test | What it proves |
|---|---|
| test_db.py | 0017 on the 0012 pilot fixture through the full chain: rehearsal OK, pending list and schema version ending in 0017 (test_db.py:378), fourteen guard lines. **The 0016 `ADDED` assertion stays (test_db.py:388), and a separate 0017 one is added.** A populated 0016 database (shops, sessions, operator sessions, credit lines, jobs) migrates with every row of its ten shop columns kept. The CHECKs refuse a half-NULL pair, an empty version and an empty date |
| current-head checks moved to 0017 | test_db.py:97, :295, :441, :524; test_api.py:829; test_reads.py:111; test_phone_session.py:68, :85 |
| test_terms.py | the text's hash pinned to `VERSION`; `VERSION` an ISO date; `paragraphs` with the contact, the fallback, and a contact holding « {} »; GET before and after, `changed` after a version change; POST 200; the same POST answers the same date without a write; an older version → 409, nothing written; no Origin → 403; older bundle → 409; signed out → 401; **suspended, or session ended, after the boundary's read → 401, nothing written**; two concurrent POSTs → one write, one date |

Mutation (guards the gate's input): `accept` writes any version → the 409 test fails.
Verify: `uv run pytest tests/test_terms.py tests/test_db.py tests/test_api.py tests/test_reads.py tests/test_phone_session.py tests/test_two_shops.py -q` → all passed; `uv run pytest -q` → all passed.

**T-TERMS-002 — The gate at admission, the balance's reason, the fixture sweep.**
- `terms.require` in `enqueue`, `reads._admit` and `jobs.blocked`; `BLOCKED`; `terms_required`.
- **Fixtures:** `credited()` (test_db.py:32-37; browser_smoke.py:2261-2265) also accepts. Every shop made outside it is named and accepts explicitly: the browser smoke's own funded shop (browser_smoke.py:1995), and each `shops.create_shop` / `second_shop` in the tests (`grep -rn "create_shop\|second_shop" tests/ ../frontend/tests/`). One shop stays explicitly unaccepted, for the refusal tests.

| Test | What it proves |
|---|---|
| test_poster_jobs.py | Not accepted: scene, refinement, text material, Claude plan, style, text proposal each → 403 with no job, call, key, or change of balance. Accepted → admitted. **Simultaneous refusals:** not accepted with an image running, with twelve scenes, paused, cap reached, day reached, zero credit → `terms_required` each; with `look_limit` or `adjustments_limit` → that refusal. **Three cases:** an admitted key replayed after a version change → its stored 202, no new job; the internal 429 retry of a job admitted before → call 2 reserved and sent; a new attempt after a failed job → 403 |
| test_reads.py | Not accepted: no `chat_reads` row, no provider call; with read limit or reads busy too → `terms_required`; an admitted read's replay answered |
| test_api.py | `/api/balance` 200 with `{"reason": "terms", …}` for both kinds, also while paused; every code has a sentence |
| test_two_shops.py | A accepted, B not: B refused, A admitted |

Verify: `uv run pytest tests/test_poster_jobs.py tests/test_reads.py tests/test_api.py tests/test_two_shops.py -q` → all passed; `uv run pytest -q` → all passed; `uv run python ../frontend/tests/browser_smoke.py` and `chat_browser.py` → pass.

**T-TERMS-003 — The dialog, the balance's reason, the replay controls, focus.**
- The dialog and its text-not-available state; `termsAsked`; `credit().terms`.
- `cardButton`'s `conditions` and the adapter's `conditions()`; the paid sheet's « Lire les conditions »; ChatView.vue:258.
- `modalOpen`, the inert panels, the focus watcher; deploy/README.md's release steps.

| Test | What it proves |
|---|---|
| Vitest | `credit()` gives `terms: true` for reason `terms`; `cardButton` gives `conditions` for a fresh card stopped by `terms`, and `retry` / `resume` for a retained one in the same state; `termsAsked` moves on `terms_required` only; the turn rule (an older read never overrides a later acceptance); the version's French date |
| terms_browser.py (new; stub, own data, zero spend) — **the journey once, at 1280** | Shop 1's acceptance set to NULL. The dialog at opening, without a sign-out button; « Plus tard » → edit, approve, confirm, download. A fresh chat card shows « Lire les conditions » and no `/scenes` request leaves. **Delayed balance:** the paid sheet opened while `/api/balance` is held, then answered with `terms` → « Lire les conditions » appears. **Retained key:** a paid card's 202 dropped after the server took it, then the stored version set older → « Reprendre » gets the stored 202 and the job is followed, with no dialog. A free Claude button → 403 → dialog. A chat message → text back in the field, dialog. The text fetch failing → « Réessayer » beside « Plus tard ». « J'accepte » → closed → a scene admitted. Acceptance answer lost after the commit → « L'acceptation n'a pas pu être confirmée. », then closed by the read. A held read released after acceptance leaves it closed |
| terms_browser.py — **keyboard, at 360 × 640, both themes, without repeating the races** | From an open review, a late 403: focus on the dialog, Tab stays inside, « Plus tard » returns focus to the review and free work continues. From the sign-out confirmation, a late 403: the confirmation keeps focus and stays in front; closing it focuses the dialog. Nothing scrolls sideways |

Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `cd ../backend && uv run python ../frontend/tests/terms_browser.py`, `browser_smoke.py`, `chat_browser.py`, `editor_refinements_browser.py` → pass.

**T-TERMS-004 — The warning, the check's wording, « Vos données ».**
- `FEATURES_WARNING` on cards and in « Ajuster la scène »; the three reworded points.
- `frontend/public/donnees.html` and its sign-in link (the dialog's link comes with T-TERMS-003 and points to the same path).

| Test | What it proves |
|---|---|
| Vitest | the warning for a `refine` card that is not `done` (offered, restored, re-offered), not for a `scene` or `free` card |
| test_api.py | the static mount (temporary build folder) serves `donnees.html` without a session, `no-cache` |
| chat_browser.py, editor_refinements_browser.py rows | the warning on a fresh card, after a reload and after a refusal; in the « Ajuster la scène » dialog; the new wording in the review and the check |
| terms_browser.py row | `/donnees.html` from the sign-in screen, signed out; at 360 × 640 in both themes, nothing scrolls sideways |
| browser_smoke.py | passes, with the reworded labels updated where they are asserted |

Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build && test -f dist/donnees.html` → pass; `cd ../backend && uv run pytest tests/test_api.py -q` → all passed; `uv run python ../frontend/tests/chat_browser.py`, `editor_refinements_browser.py`, `browser_smoke.py`, `terms_browser.py` → pass.

**Not proven here:** 0017 on SQLite 3.40.1 (pending until the release rehearsal); a real phone; what the providers keep; whether Maizina's Caddy logs addresses (a read-only look, on the user's word, before the release).

## Not built, on purpose

- **`erase` (Release 1).** Its later design must solve:
  - an offline operation under the release/backup/restore lock: an upload of the same bytes and the backup copier race the ownership scan (store.py:118; assets.py:21; backup.py:35);
  - shop 1 with a null password hash stops the API at start (auth.py:99-122, `adopt_password_setting`);
  - files shared by hash, and which references count as live (two successive erasures, evaluation data, enabling an erased shop);
  - backups, restore leftovers (restore.sh:24, :42-44), spool files and their crash temporaries (jobs.py:267-284);
  - unused prepaid credits;
  - what routes answer afterwards (404, 503 `asset_missing`, 503 `export_missing`, a thumbnail warm in memory, api.py:364-373).
- **The operator's view of acceptance** (dashboard list and header, `shops list` column): after Release 1, on the owner's word.
- **Not built here at all:** an acceptance history table (owner decision 1); a reading field or a regex for the warning; a fifth confirmation key; a public conditions page; terms in Malagasy; a legal review (Phase 2); a raise of `BUNDLE` (no bundle 3 was ever deployed); a guard on the two columns.

## Wording asked of the requirements

- **R-TERMS-001:** « The first time the application opens on a shop that has not accepted the current version, the owner is asked to accept; he may postpone, and free work continues. Without acceptance nothing new is asked of the AI and no credit is taken. »
- **R-TERMS-002:** « Every scene-adjustment request, in the chat and in « Ajuster la scène », shows the warning (owner decision 2) before the paid tap. The review and the check before download include the texts the AI added; a saved preview is the owner's matter. »
- **R-TERMS-003:** replace the first bullet with the categories of D-TERMS-007, and the deletion with owner decision 4's wording.
- **R-SHOP-DASH-003:** a link to « Vos données », verified from a signed-in shop that has already accepted. The lead adds it to the shop dashboard's requirement; this design does not.

## Traceability

| Requirement | Decisions | Task |
|---|---|---|
| R-TERMS-001 | D-TERMS-001, 002, 003, 004 | T-TERMS-001, 002, 003 |
| R-TERMS-002 | D-TERMS-005, 006 | T-TERMS-004 |
| R-TERMS-003 | D-TERMS-007; open until owner decisions 4 and 5 amend it; the account-screen link is R-SHOP-DASH-003's (added by the lead) | T-TERMS-004 (page), T-TERMS-003 (the dialog's link) |

## Decisions only the owner can take

Each is in force on its default and can change before the task named.

| # | Decision | Default in force | Until |
|---|---|---|---|
| 1 | What is kept of an acceptance | the last one per shop, two columns. Alternative: an append-only table of every acceptance | T-TERMS-001 |
| 2 | The warning's wording (ADR-111 quotes the bare sentence) | « Vous demandez des caractéristiques sans les lister ? » before the required sentence, on every actionable scene-adjustment card and in « Ajuster la scène ». Alternative: the bare sentence, which reads as a fact on « fond plus sombre » | T-TERMS-004 |
| 3 | The check's wording | `extras_text`, the review's text line and `content` as drafted, for every version | T-TERMS-004 |
| 4 | Deletion, as the page says it | **Decided by the owner, 2026-11-18 (ADR-112): the requirement is amended to this default.** Suspension at once (new requests blocked; one already started can still finish); then the operator says what can be erased, and when; no deadline, no claim about backups until a procedure exists. `erase` waits for its own design | T-TERMS-004 |
| 5 | R-TERMS-003's "messages' cost but not their text" | **Decided by the owner, 2026-11-18 (ADR-112): the requirement is amended to this default.** Accurate wording now (the stored answer may repeat the instruction whole). Alternative: a storage change later (not keeping the card's text) | T-TERMS-004 |
| 6 | Naming OpenAI, Anthropic and Hetzner on the page | named. Alternative: « un service d'images », « un service de lecture » | T-TERMS-004 |
| 7 | Pixels saved from a preview without the check | accepted, named limit. Alternative: a mark on previews (not designed) | T-TERMS-004 |
| 8 | Who accepts | the shop, through whoever holds its password | T-TERMS-001 |
| 9 | The French texts as a whole | the drafts above; `VERSION` becomes the date of the approved text | T-TERMS-001 (conditions), T-TERMS-004 (page) |
