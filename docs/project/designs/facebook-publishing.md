# DESIGN — Publish a poster on the shop's Facebook Page

## System overview

**Status:** v3, 2026-11-21 (Claude), **approved under the owner's autonomy grant after its third review ([r3](../reviews/facebook-publishing-design-r3-2026-11-21.md): APPROVE WITH FIXES; its two fixes are in the text below, marked r3).** The owner then said "yes to all" to the three points under « Open » (2026-11-21): the requirement amendments, `business_management`, and the conditions of use, read as a new version with this feature (T-FB-004). `meta` waits for the proofs. v1 was rejected by its review ([r1](../reviews/facebook-publishing-design-r1-2026-11-21.md)) and challenged ([devil's advocate](../reviews/facebook-publishing-devils-advocate-2026-11-21.md)); it was parked, the proofs below were run, and v2 was written from them without the look-up of a lost publication, the encryption library, the image conversion and the calls inside a stored mutation. [Round 2](../reviews/facebook-publishing-design-r2-2026-11-21.md) closed seven of round 1's findings and found five more; v3 answers them by removing again: the `admitted` state (the admission is the send's boundary), the hand-over through the browser's storage (the return page sends the code itself), and « published » on a photo's id alone.
**Requirements file:** [../requirements/facebook-publishing.md](../requirements/facebook-publishing.md) (R-FB-PUBLISH-001 to 004; approved by the owner, ADR-127; amended on 2026-11-21 by what the proofs showed, the amendments marked there for his word). Stage 1 only.
**Facts it stands on:** Meta's documentation read on 2026-11-21 (Graph API v27.0), the proofs below, and the code on `main`.

```
[page] ── « Connecter » ──▶ [api] gives the address of Facebook's dialog
[Facebook] ── sends the owner back to /facebook.html with a code ──▶ [page] ── code ──▶ [api]
[api] ──▶ [Graph API]  code → user token → the Pages the owner allowed (each with its token)
[page] ── the owner picks one Page ──▶ [api] ──▶ [db] facebook_pages
[page] ── « Publier » ──▶ [api] ──▶ [db] facebook_publications ──▶ [Graph API] POST /{page}/photos
                                         └──▶ published | failed | unknown (the owner looks at his Page and says)
```

Everything that talks to Facebook is on the server. The browser never holds a token or the Meta app's secret. Nothing here takes a credit or asks the image provider.

**Two rules, from this project's last reviews.** A publication is a row on the server before anything is sent, and only Facebook's own answer makes it « published ». What the app does not know, it does not work out: the owner, who can see his Page, says.

## What the proofs showed (2026-11-21, with the owner)

| Proof | Result |
| --- | --- |
| The Meta app « Doka studio » published | Done on the owner's word: privacy address `https://affiches.miorantsoa.app/donnees.html`, then « Publier ». No business verification was asked. Stage 1 does not wait on Meta's verification |
| A post through the API on Original Phone Mada | Done: a scheduled, unpublished photo, read back, then deleted (`success: true`). `POST /{page-id}/photos` works with the Page's token |
| Why the Page was not offered at first | It is owned by a business portfolio. With the three `pages_*` permissions the dialog and `me/accounts` gave only Pages managed directly; with `business_management` added, the Page appeared. **The app's consent needs `business_management`** |
| How many Pages a person allows | The owner's dialog ended with three, then four Pages allowed, though one was meant. **The app cannot count on one Page: it must let the owner choose** |
| The answer for an unpublished photo | `{ "id": <photo id> }` only, no `post_id`. Its post is `{page-id}_{photo-id}` in `scheduled_posts` |
| Meta Business Suite | Does not list a photo scheduled through the API. Scheduling stays out |
| The person who connects | May have partial access (content, messages, ads). `CREATE_CONTENT` in `tasks` is what posting needs |
| Not proved yet | That customers see a post the app publishes (Meta's documentation says so once the Meta app is published); an « AI info » label; `appsecret_proof` with « Clé requise » on; « Partager » as the Page on a phone; the connection on the pilot owner's phone |

---

## D-FB-PUBLISH-001 — Settings and what is stored (covers R-FB-PUBLISH-001)

**Settings** (`config.py`; names in `.env.example` and in the test fixture's `NAMES`):

| Name | Kind | Meaning |
| --- | --- | --- |
| `FACEBOOK_PROVIDER` | `off` (default) \| `stub` \| `meta` | `off`: no card, no button, the routes answer `not_found`. `stub`: a local stand-in for tests, smokes and the dev server. `meta` only once the Meta app is published (runbook): an unpublished app's posts are seen by its own role holders only |
| `FACEBOOK_APP_ID` | text | required when `meta` |
| `FACEBOOK_APP_SECRET` | `SecretStr` | required when `meta`; the image key's guards (never printed, never in an error) |

**No new dependency and no encryption key.** A Page's token is stored as Facebook gave it. Every call the server makes carries `appsecret_proof` (HMAC-SHA256 of the token with the Meta app's secret, standard library), and the Meta app's switch « Clé requise » is turned on before the first shop connects (runbook): Facebook then refuses a token that comes without the proof. A copy of the database, which every backup is, holds tokens that nobody can use without the secret, and the secret is in the server's environment only. v1's Fernet key protected the same copies and could be lost; the secret can always be read again in the Meta app.

**Data model** (migration `0018_facebook`, forward-only, `PRESERVED`/`ADDED` stated):
```sql
CREATE TABLE facebook_pages (              -- the shop's Page: one per shop
  shop_id INTEGER PRIMARY KEY REFERENCES shop_profile(id),
  page_id TEXT NOT NULL, page_name TEXT NOT NULL, token TEXT NOT NULL,   -- never returned by a route
  state TEXT NOT NULL CHECK (state IN ('connected','reconnect')),
  connected_at TEXT NOT NULL
);
CREATE TABLE facebook_connects (           -- the shop's one attempt to connect, at most
  shop_id INTEGER PRIMARY KEY REFERENCES shop_profile(id),
  state_sha TEXT NOT NULL,                 -- SHA-256 of the dialog's `state`; the value itself is stored nowhere
  session_sha TEXT NOT NULL,               -- the session that began it: only that session goes on with it
  step TEXT NOT NULL CHECK (step IN ('dialog','exchange','choice')),
  pages_json TEXT,                         -- at 'choice': the Pages allowed, each with its token; gone with the row
  created_at TEXT NOT NULL
);
CREATE TABLE facebook_publications (
  id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  creation_id TEXT NOT NULL, confirmation_id TEXT NOT NULL,
  page_id TEXT NOT NULL, page_name TEXT NOT NULL, caption TEXT NOT NULL,
  key TEXT NOT NULL, payload_sha TEXT NOT NULL, UNIQUE (shop_id, key),
  status TEXT NOT NULL CHECK (status IN ('sending','published','failed','unknown')),
  sent_at TEXT NOT NULL, settled_at TEXT,
  post_id TEXT, link TEXT, error_code TEXT, said_by_owner INTEGER NOT NULL DEFAULT 0
);
```

**One mode per database.** The first Facebook call of a data folder records `facebook_mode` in `meta` (`stub` or `meta`), as the planner's reads record theirs (`reads.py`, `planner_mode`); with the other mode the routes refuse (`provider_mode_mismatch`). A publication made by the stand-in can never sit beside real ones.

**Logs.** The app logs no token, no code, no `state` and no secret. Of a Graph error it logs `code`, `error_subcode` and `fbtrace_id`, never the message's text. The HTTP client's own logging stays off for these calls. A token goes in the request's body or in the `Authorization` header. One exception, Meta's own: the two exchanges of §002 are documented as `GET` with the secret in the address; the proof of the first connection tries them as `POST` with a body first. If only the `GET` works, `meta` stays off until it is shown that nothing on the way out keeps that address (the app's client logs none; the server calls Facebook directly, through no proxy).

---

## D-FB-PUBLISH-002 — Connecting a Page (covers R-FB-PUBLISH-001)

**Approach:** Facebook Login for Business, authorization-code flow, the permissions asked by `scope`: `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`, `business_management` (the Explorer's dialog ran with them for this Meta app). None of the three routes goes through `store.mutate`: it holds the database's write lock for its whole body, and these make calls to Facebook. They take no `Idempotency-Key`; the single-use `state` is the guard against a replay.

**The return address is a page of its own, `APP_ORIGIN/facebook.html`**: a second small entry of the build, as the operator's page is one, with no image, no font and `<meta name="referrer" content="no-referrer">`. The session cookie is `SameSite=Strict`, so it is not sent when Facebook sends the browser back; but it is sent with the requests that page makes itself. Its script takes `code`, `state` and `error` from the address, removes them from it at once (`history.replaceState`), sends `{code, state}` to the API with the application's own request helper (Origin, bundle and session checked as for any change), and then replaces itself with `/#compte`, where the card reads the result from the API. Nothing is put in the browser's storage, and the application's shell never loads with a code in its address. The code is single-use and worth nothing without the secret; it passes through the browser's address once, as in any such sign-in.

**A gate before `meta` is turned on:** the box's front proxy is asked for `/facebook.html?code=test`, and its log is read: if it keeps the query, `meta` stays off and the owner decides (the proxy is shared with other projects and is not this project's to change).

| Route | What it does |
| --- | --- |
| `GET /api/facebook` | deletes every attempt older than 10 minutes (as the server does when it starts), then `{ page: {id, name, state} \| null, choice: [{id, name}] \| null }`. With `off`: `not_found`. `capabilities` gains `facebook: true` when not `off` |
| `POST /api/facebook/connect` | deletes every attempt older than 10 minutes, then writes the shop's attempt (replacing an older one, whatever its step): a new `state` (32 random bytes), the caller's session, `step: dialog`. Answers `{ url }`: `https://www.facebook.com/v27.0/dialog/oauth?client_id&redirect_uri&state&scope`. The address is not stored |
| `POST /api/facebook/code` `{code, state}` | the steps below |
| `POST /api/facebook/page` `{page_id}` | the owner's choice among the Pages of the attempt (`step: choice`, this session's, at most 10 minutes old; checked under the write lock): writes `facebook_pages` (replacing the shop's earlier Page only now), deletes the attempt with the other Pages' tokens |
| `DELETE /api/facebook/page` | removes the shop's Page and its attempt. Publications already made keep their line and their link |

**`POST /api/facebook/code`.** Three short transactions, the calls between them:
1. *Claimed:* the shop's attempt must be at `dialog`, this session's, at most 10 minutes old, with this `state`'s hash: it goes to `exchange`. Anything else: `facebook_state` (« Recommencez la connexion. »), and the attempt, if it was this shop's, is left as it is. A second request with the same code finds `exchange` and is refused before any call.
2. *Calls*, each with a 20 s timeout, no redirect followed, its answer's fields checked: the code for a user token; that token for a long-lived one (a Page's token made from it has no expiry date); `GET /v27.0/me/accounts?fields=id,name,tasks,access_token&limit=100`. The user tokens are dropped.
3. *Stored*, only if the attempt is still at `exchange` with the same hash, is still under 10 minutes old and its session is still live (a new « Connecter », a « Déconnecter », a sign-out or the clock wins: nothing is stored then): the Pages that have `CREATE_CONTENT`, with their tokens, at `choice`. None: `facebook_no_page`. A failed call: « La connexion à Facebook n’a pas abouti. Réessayez. ». In both cases the attempt is deleted only if it is still this one (same hash, still at `exchange`): a newer attempt is never touched, and the shop's earlier Page, if any, stays. `GET /api/facebook` lists a choice only for the session that began it and only while it is under 10 minutes old.

The answer lists the Pages by name. One Page: the page still asks « Connecter {Page} ? »: the owner sees which Page before it is bound. More than a hundred allowed Pages: the first hundred, said so.

**A shop without a role on the Meta app** cannot finish Facebook's dialog, and Facebook may send nothing back. So the card always carries, under its button: « Si Facebook refuse l’accès, votre Page doit d’abord être autorisée par Doka Studio : demandez-le à l’opérateur. » When Facebook does return an error: « La connexion n’a pas abouti. » A cancelled dialog (`error=access_denied`): « Connexion annulée. »

---

## D-FB-PUBLISH-003 — Publishing (covers R-FB-PUBLISH-002, 003, 004)

**Approach:** one request made by the route itself, as the paid reading of a message is (`reads.read`): admitted in one transaction, sent outside any, settled in another. Not a job.

`POST /api/creations/{id}/publications` (`Idempotency-Key`, kept in the table's own `key` column as `reads` keeps its own) `{ confirmation_id, page_id, caption, seen }`, where `seen` is the id of the last publication of this poster on this Page that the sheet showed, or null. `GET /api/creations/{id}/publications`: the poster's publications, newest first; it reads and changes nothing.

**1. Prepared** (no transaction, nothing written yet): the confirmation named by the request is read and checked as the download does (`read_png`). Missing or damaged: `export_missing`. Over Meta's 10 MB: `facebook_too_large`. The file sent is the PNG itself: what is published is the file that is downloaded, byte for byte.

**2. Admitted, which is the send's boundary** (one write transaction; a refusal writes nothing):
- the same key first: it must be for this poster and have the same body (otherwise `idempotency_reused`); it answers the row as it is now, or `facebook_running` (409) while the row is `sending`;
- the shop is active and the conditions accepted (`terms.require`);
- the shop's Page is `connected` and is `page_id`: otherwise `facebook_not_connected`, `facebook_reconnect`, or `facebook_stale` (the sheet reads again);
- `confirmation_id` is a confirmation of this shop's poster at its current revision, and is the one read in step 1: otherwise `facebook_stale`;
- the caption passes the rules of « Partager » (2000 code points, no control character other than a line feed or a tab); only blanks is taken as empty, and empty is allowed;
- no publication of this poster on this Page is `sending` or `unknown`: `facebook_pending`. Other posters are free;
- `seen` is the last publication of this poster on this Page: otherwise `facebook_stale`. Two sheets opened before either published cannot both publish without the second seeing the first.
The row is written `sending`, with `sent_at`, the Page's id and name and the caption. There is no state before it: a row exists only for a request that is about to leave.

**3. Sent** (no transaction): `POST https://graph.facebook.com/v27.0/{page-id}/photos`, multipart: the file, `caption`, `access_token`, `appsecret_proof`. Timeout 60 s, no retry, no redirect followed. The send and its settlement run to their end even when the browser has gone (the route does not stop them with the request). *(r3)* Right before the request leaves, the handler looks at the clock: more than 30 s since the admission and it does not send; the row is `failed` (« La publication n’est pas partie. Réessayez. »).

**4. Settled** (a write transaction, only while the row is `sending`; when that write fails it is tried again with the answer in hand, three times, and never by sending again):

| Facebook's answer, read in this order | Status | What the owner reads |
| --- | --- | --- |
| HTTP 5xx, whatever its body; no answer; a cut connection; an answer that cannot be read | `unknown` | §5 |
| 200 with a `post_id` of the shape `{this Page's id}_{digits}` | `published`; `link` is `https://www.facebook.com/{post_id}` | « Publié sur {Page}. », « Voir la publication » |
| 200 without such a `post_id` (the proof's unpublished photo answered an `id` alone) | `unknown` | §5 |
| an error with code 190 (the access is cancelled or its owner lost his role) | `failed`; the Page becomes `reconnect`, only if its row is still the one that gave the token | « Reconnectez votre Page. » |
| an error with code 4, 17, 32, 613, 80001 (limits) or 368 (blocked) | `failed` | « Facebook limite les publications pour le moment. Réessayez plus tard. » |
| an error with code 10 or 200–299 (a permission), 100 (a parameter), 324 (the image), 506 (a duplicate) | `failed` | « Facebook a refusé la publication (code N). » |
| an error with any other code | `unknown` | §5 |

*(r3)* **A `sending` row is never released by its age.** While it is `sending` its handler may still send or settle, so the owner is offered nothing for it but « Publication en cours… »: no outcome, no new publication. It leaves `sending` in two ways only: its handler settles it (every path above, an exception included, ends in a status), or the server starts and writes every `sending` row `unknown`, which proves the handler is dead. A handler that hangs without the server stopping keeps its one poster and Page waiting until a restart: the runbook says so.

**5. Unknown: the owner says.** The line reads « Je ne sais pas si l’affiche est publiée. Ouvrez votre Page et dites-le-moi. », with « Ouvrir ma Page » (`https://www.facebook.com/{page-id}`) and two buttons: « Elle est sur ma Page » and « Elle n’y est pas ». Before the second is sent the sheet says: « Si elle apparaît plus tard, publier à nouveau créera un doublon. » `POST /api/creations/{id}/publications/{pid}/outcome` (`Idempotency-Key`) `{ present }`, accepted for an `unknown` row only: `published` with `said_by_owner` and the Page's address as its link, shown as « Présence confirmée par vous » with « Ouvrir la Page »; or `failed` (`not_published`). Until then no new publication of this poster on this Page is admitted, and the publish sheet is not offered. The app never looks on the Page and never sends again by itself. A wrong « Elle n’y est pas » followed by a new publication makes a second post: the owner's own word, said after the warning.

**Never twice:** the key, tied to its poster; the last publication seen; one in flight per poster and Page; no retry by the server; an unknown outcome closed by the owner before another send.

---

## D-FB-PUBLISH-004 — The page (covers R-FB-PUBLISH-001 to 004)

- **« Mon compte »**, a card « Page Facebook », only when `capabilities.facebook`. Not connected: « Connecter ma Page Facebook », with « Facebook vous demandera quelles Pages autoriser. » Back from Facebook: the allowed Pages by name, one to pick, « Connecter cette Page ». Connected: the Page's name, « Déconnecter ». `reconnect`: « Reconnecter ma Page ».
- **The final panel**, beside « Partager », only when `capabilities.facebook` and for the confirmed file: « Publier sur ma Page ». Not connected: it leads to « Mon compte ». It opens the editor's confirmation sheet: the Page's name, the image (the confirmation's preview), the caption of « Partager » in its field (the same text, kept on the device as today; what is sent is what the field shows), « Publier », « Annuler ». When this poster was already published on this Page, the sheet says so with its date: publishing again is allowed, knowingly. A `facebook_stale` answer makes the sheet read again and say what changed.
- **Under the buttons**, the poster's publications: date, Page, state, « Voir la publication ». An unknown one shows its two buttons. Nothing is asked again by a timer.
- No state of this feature is kept in the browser.

---

## Failure modes (external system, access, secrets)

| What fails | What happens |
| --- | --- |
| Facebook does not answer during the connection | the attempt is deleted; the sentence; the shop's earlier Page stays |
| The return address is loaded twice, or its code is sent twice | the attempt is no longer at `dialog`: refused before any call |
| A forged or foreign `state` | refused; the attempt of the shop it does not belong to is untouched |
| « Connecter » again, or « Déconnecter », while an exchange is on its way | the exchange's result is dropped at its last step |
| The access is cancelled between two publications | the next one fails with 190: the Page becomes `reconnect`; no retry |
| The Meta app is restricted by Meta, or a permission is taken back (codes 10, 200–299) | `failed` with the code; the Page is not asked to reconnect, which would not help |
| The server stops before the request leaves, or between « sent » and « settled » | the row is `sending`, then unknown: the owner says. Nothing was written before the admission, so no row exists for a request that never could leave |
| The Meta app's secret is reset | every call fails with 190: every shop reconnects. Nothing else is lost |
| A copy of the database is read by someone else | its tokens, the Pages' and for ten minutes the waiting ones of an attempt, are refused by Facebook without the secret (« Clé requise »). Backups keep fourteen days of copies: a token deleted here is still in them, as unusable |
| A restore of the database | the copy's connections and publications are older than Facebook's truth: a poster published since would look unpublished, and a Page disconnected since would be connected again. So `FACEBOOK_PROVIDER` is `off` for the restore, and the existing `shops after-restore <kept database>` gains two steps: it deletes `facebook_pages` and `facebook_connects` (each shop connects again), and it brings the publications to what the kept database knows: the rows the restored one lacks are copied, and *(r3)* a row both hold takes the kept one's settlement (status, `post_id`, link) when the restored one is still `sending` or `unknown`; `facebook_mode` is carried when the restored database has none, and refused when it differs. Where the kept database is lost, the owner of each shop is told to look at his Page before publishing |
| The confirmed file is missing, damaged or over 10 MB | `failed` before anything is sent |
| Facebook is down | publications fail or are unknown; « Partager » and « Télécharger » do not depend on it |

## Edge cases

- The poster is edited after it was confirmed: no confirmation at the current revision, the button is not offered until it is confirmed again.
- The shop connects another Page: old publications keep their own Page's name and link.
- Two tabs, two sheets: the second is refused by `seen` or by the publication in flight, and reads again.
- The owner removes the post on Facebook: the app's line keeps its link, which Facebook then answers as gone (requirements, as amended).
- The person who connected loses his role on the Page: the next publication fails with 190, and someone who has the role connects.
- A shop whose conditions are not accepted: the button offers to read them, as a paid control does.

## What must be done outside the code (runbook, `deploy/README.md`)

- Done: the two `pages_*` permissions added; the privacy address; the Meta app published.
- « Valid OAuth redirect URIs »: `https://affiches.miorantsoa.app/facebook.html` (and `http://127.0.0.1:5173/facebook.html` for local work).
- **A gate before any shop connects:** « Clé requise » on, then two calls with one token: without the proof Facebook must refuse it, with the proof accept it. If either fails, no shop is connected and the design's token rule is reopened.
- Each shop's Page admin added as a tester of the Meta app (50 at most while it is not tied to a verified business).
- The « Vos données » page, which is now the Meta app's privacy policy, says what this feature keeps and how to have it removed.
- The gate of §002 on the front proxy's log, before `meta`.
- The restore procedure gains its two steps (failure modes).

## Tests

- **Backend (pytest, `httpx2.MockTransport` in place of Facebook):** settings (each guard; `off` hides the routes); the migration's rehearsal. Connect: a foreign, old, reused or replaced `state`; a second `code` request; each failing call leaves the earlier Page; no Page with `CREATE_CONTENT`; the choice among several, the others' tokens gone; a token is in no answer and no log line; every call carries `appsecret_proof`. Publish: each refusal of « admitted » writes nothing; two sheets one after the other (`seen`); a Page or a confirmation changed after the sheet; the bytes sent are the confirmed file's; each row of the answers' table; a 190 after a reconnect leaves the new Page alone; the same key sends once and is refused for another poster; a handler held back over 30 s does not send; a `sending` row offers no outcome and no new publication, whatever its age; a 200 with an `id` alone and a 5xx with a code are unknown; the settling write that fails is tried again without a second send; `sending` becomes unknown at start only; the owner's two answers; a new publication refused until then; the other mode on the same data folder is refused; `after-restore`: the connections gone, a missing row copied, a row held by both and settled only in the kept one, the mode carried.
- **Vitest:** the card's states; the button's conditions; the sheet's « already published ».
- **Browser smoke (stub):** connect with two Pages and choose one; publish a confirmed poster; the line and its link; publish again knowingly; an unknown outcome and each answer; disconnect; `off`: no card and no button. The return page: its address is clean at once, nothing is in the browser's storage, and the application loads without a code.

## Not done

- A look-up of a lost publication on the Page (v1): the owner says.
- **To weigh after the first public post:** send the photo unpublished first, then publish that known object by its id (Meta lists `is_published` among a Page post's fields that can be updated; no example is documented). A lost answer could then be read back by id, and the owner's two buttons would go. Not relied on until a real publication shows it.
- A JPEG in place of the PNG: only if Facebook's rendering of the PNG proves poor at the first public post.
- Scheduling, several images, Instagram, editing or removing a post, the Page's picture on the card, a system user of the owner's business (it would remove the sign-in, but each shop's Page would have to be shared with his business: the owner's call if the dialog proves hard for shops).

## Tasks (to enter in TODO.md once this design is approved)

1. Settings, migration 0018, the Graph client (`meta` and `stub`) with `appsecret_proof`, their tests.
2. Connect, choose, disconnect; the return page; « Mon compte »'s card.
3. Publish, the outcome said by the owner; the final panel's button, sheet and list.
4. « Vos données » and the conditions say what is kept; the runbook's lines.
5. With the owner, on the released app: « Clé requise » on; the first connection (the exchanges as `POST`; his phone); the first public post (customers see it; the PNG's rendering; an « AI info » label).

## Answered by the owner (2026-11-21: "yes to all")

1. **The conditions of use** list what is kept; this adds the Page's name and id, its access and the publications. A new version asks every shop to accept again: now, or with the next change of the conditions? **Read as: a new version, released with the feature (T-FB-004). His « yes » was to a list; this one point was an either-or, so it is his to correct.**
2. **The requirement changes** the proofs brought (marked in the requirements): the owner says whether a lost publication is on his Page, the app does not look; a post removed on Facebook keeps its link; no Page picture; « encrypted » becomes « a copy of the database cannot use it »; the owner chooses among the Pages he allowed.
3. **`business_management`** is a broad permission. Stage 1 needs it for any Page that is in a business portfolio. For stage 2 it will weigh on Meta's review.
