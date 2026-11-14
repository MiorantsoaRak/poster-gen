# Failure-path audit of the chat — 2026-11-15 (T-CHAT-005 part A)

Environment: Linux laptop, stub providers, temporary data folders of `frontend/tests/chat_browser.py` (a fresh shop: no profile, no poster, no style), zero spend. Nothing was checked on the deployed pilot.

How each path was checked: **B** walked in a real browser by `chat_browser.py`; **T** by a test (Vitest or pytest); **R** read in the code only (not walked).

Count: 45 paths, 8 broken, 8 fixed (2 of the fixes have no test of their own: the 401 on an upload and on a paid request), 3 points left open (listed at the end).

## Reading a message (`POST /api/reads`)

| Path | What the owner sees | How | Verdict | Fix |
|---|---|---|---|---|
| `read_failed` (the reader fails, `STUB_FAIL`) | « Je n’ai pas pu lire votre message… », « Réessayer » (a new read), « Pas à pas » | B | good | |
| `read_running` | the server's sentence, « Réessayer » sends the same record | T, R | good | |
| `read_limit`, `chat_unavailable` | the server's sentence and « Pas à pas » | R | good | |
| `budget_exhausted` | the server's sentence; the text goes back to the field | R | good | |
| answer lost, timeout, unreadable answer | « Connexion interrompue… », « Réessayer » with the same key | B | good | |
| `validation_error` (a 501-character or empty text, a stored draft out of bounds) | it was the editor's sentence about brand and subtitle | R | **broken** | the chat's own sentence: « Ce message ne peut pas être lu tel quel. Écrivez-le plus court… ». The field itself stops at 500 characters and an empty text is never sent. |
| 401, the session ended | it was « Connectez-vous pour continuer. » with no sign-in form: a dead end until a reload | B | **broken** | the sign-in form comes (`adapter.signedOut`); after it the thread is there and « Réessayer » sends the message |
| `provider_mode_mismatch` | the fallback sentence with the code for the administrator | R | acceptable | only a wrong server configuration gives it |
| 413 | cannot happen from the chat: the body is bounded far under 128 KB | R | n/a | |
| `creation_abandoned`, `not_found` (the poster was removed elsewhere) | the server's sentence, no retry | R | acceptable | |
| a read waits on another poster | « Un message attend encore sur une autre affiche. » and « Ouvrir cette affiche » | B | good | |

## Images

| Path | What the owner sees | How | Verdict | Fix |
|---|---|---|---|---|
| `unsupported_type` (not an image) | the sentence under the tray, « Réessayer » on the thumbnail, « Retirer »; « Envoyer » waits | B | good | |
| `animated_image` | same, with its sentence | B | good | |
| `too_large`, `invalid_image`, `unsupported_colour` | same mechanism, each has its sentence | R | good | |
| a fifth image | « Trois photos du produit et une image d’inspiration au plus. » | B | good | |
| a role with no room (a second inspiration held by a sent image, a fourth product photo) | the tap on the label did nothing and said nothing | B | **broken** | the same sentence is shown |
| 401 during an upload | the sentence on the thumbnail, no sign-in form | R | **broken** | the sign-in form comes |
| a photo already used, offered on `ask_photo` | thumbnails with « Reprendre cette photo »; no upload, no read | B, T | new | lookup failure: the card comes without them, logged |
| a small product photo | the recap asks the agreement; « Créer l’affiche » waits for it | B | good | |
| a small photo the chat did not know (`acknowledgement_required`) | the server's sentence, then a new card with the agreement | R | good | |

## The paid request (`/scenes`, `/refinements`)

Codes listed from `visuals.request_scene`, `visuals.request_refinement`, `store._snapshot`, `store._asset`, `jobs.enqueue`, `jobs.call_spec`, `store.mutate` and the middleware, then compared with `MESSAGES` and with `chat.ts` `final`.

| Path | What the owner sees | How | Verdict | Fix |
|---|---|---|---|---|
| `plan_stale`, `revision_conflict`, `not_found`, `idempotency_reused`, `format_locked` | the sentence, the card retired, a new card with its cost | B (`plan_stale`, `revision_conflict`) | good | |
| `title_too_long`, `title_unsupported`, `title_commercial_text`, `validation_error` | the sentence and « Corriger dans Pas à pas » | R | good | |
| `contact_unsupported`, `invalid_headline` | the sentence and « Réessayer », which sent the same request and got the same refusal; the waiting card also held « Envoyer » and every paid button | T | **broken** | both are final now: the card is retired with « Corriger dans Pas à pas » |
| `attempt_limit` | the sentence; no new card for a scene change | T | good | |
| `headline_stale` | « Le texte a changé : je refais l’affiche entière. » with its cost | T, R | good | |
| `base_not_selected`, `scene_format_mismatch`, `logo_disc_uncovered`, `logo_placement_stale`, `invalid_plan`, `invalid_reference`, `unsupported_visual` | the sentence, then the same change offered again | T (final), R | good | |
| `image_job_running` | the sentence, « Réessayer » keeps the request | B | good | |
| `budget_exhausted`, `provider_unavailable`, `format_unavailable`, `creation_abandoned`, `asset_missing`, `asset_corrupt` | the sentence, « Réessayer » keeps the request | R | acceptable | see open point 1 |
| `format_missing`, `unknown_asset`, `provider_mode_mismatch`, `invalid_idempotency_key` | the fallback sentence with the code | R | acceptable | programming or configuration errors only (`DEVELOPER_ONLY` in `test_api.py`) |
| 401 on the paid request | the sentence and « Réessayer », no sign-in form | R | **broken** | the sign-in form comes; the card keeps its request and shows « Reprendre » afterwards |
| answer lost, reload | « L’affiche n’a peut-être pas été lancée. », « Reprendre » with the cost | B | good | |
| the image job fails at the provider (`STUB_FAIL`) | « La génération a été interrompue. Aucun nouvel appel automatique n’a été lancé. », then a new card | B | good | |
| the version limit at 10, 11 and 12 | « Il reste 2 versions… », « Il reste 1 version… », then the `attempt_limit` sentence, no paid button, « Annuler » stays | B, T | good | |

## Review, download, price

| Path | What the owner sees | How | Verdict | Fix |
|---|---|---|---|---|
| a download refused by the server (`price_stale`, also `scene_unapproved`, `layout_invalid`, `title_missing`, `signature_missing`) | nothing: the sentence went beside an editor group that the chat does not show | B (`price_stale`) | **broken** | in the chat a refusal goes to the general message |
| a general message appears above the chat | the chat kept its height, so the composer was pushed down (read in the code; not reproduced before the fix) | R, then B with the fix | **broken** | the chat is measured again when a message comes or goes |
| a refusal inside the review or the final dialog | the editor's message above the dialog | R | good | |
| a version refused in the review | « Version refusée. Je peux en refaire une. » once no paid card waits | B | good | |
| the price edit fails (« Changer le prix », « Remettre l’ancien prix ») | the sentence on the card, the button stays | R | good | |
| the new version cannot be chosen | the sentence on the card, tried again by itself | R | good | |

## Controls folded or hidden

| Path | What the owner sees | How | Verdict | Fix |
|---|---|---|---|---|
| the list folded behind « Modifications (n) » | a real button with `aria-expanded`; Enter opens it, Tab reaches the lines | B | good | |
| the style row hidden while typing | only on a touch pointer; back as soon as the field loses the focus | B | good | |
| the tray on one line while typing | scrolls sideways; every thumbnail has its buttons | R | good | |
| « Refusée » in a card and in the list | under 4.5:1 on the dark bubble (found by the browser check in T-CHAT-004) | B | fixed earlier | the text colour |
| without Web Locks, or the chat open in another tab | a sentence and one button | B | good | |
| thread storage full or blocked | said once in the general message; the chat goes on | R | good | |

## Left open

1. A paid card refused for a reason that does not pass by itself (`budget_exhausted`, `provider_unavailable`, `format_unavailable`) stays with « Réessayer », and while it waits no message is sent on that poster (ADR-098). The sentence says why and « Pas à pas » stays one tap away, but nothing removes the card. A decision is needed before changing it: retiring it would break the rule of ADR-097.
2. After « Version refusée », and for a poster made in steps, the new card goes through the first-poster path, which sets the chat's style (`pickLook`). Known since T-CHAT-003; not changed here.
3. Not walked in a browser, read only: `read_limit`, `chat_unavailable`, `budget_exhausted` on a read, `too_large` and `invalid_image` on an upload, `acknowledgement_required` on a reopened poster, refusals inside the review and final dialogs.
