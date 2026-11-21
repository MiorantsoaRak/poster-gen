# DESIGN — A publish page: one Facebook post with one or several posters

## System overview

**Status:** v3, 2026-11-21 (Claude), **approved under the owner's autonomy grant after its third review ([r3](../reviews/facebook-post-page-design-r3-2026-11-21.md): APPROVE WITH FIXES; its fixes are in the text below, marked *(r3)*)**. The one decision that reverses an earlier default, one way to publish (ADR-129), is the owner's to overturn. v1 was rejected by its first review ([r1](../reviews/facebook-post-page-design-r1-2026-11-21.md): five P1, five P2) and challenged by a devil's advocate ([report](../reviews/facebook-post-page-devils-advocate-2026-11-21.md)); v2 was rewritten on both. Its review ([r2](../reviews/facebook-post-page-design-r2-2026-11-21.md)) found the one-post model sound and seven points still partial; v3 answers them where they are, marked *(r2)*. Covers [R-FB-POST-001 to 007](../requirements/facebook-post-page.md) (ADR-128) and, from this version, replaces D-FB-PUBLISH-003 and the final panel of D-FB-PUBLISH-004 of [facebook-publishing](facebook-publishing.md). It keeps that design's other rules: the connected Page and its token (D-FB-PUBLISH-001, 002), `appsecret_proof` on every call, the Graph client's rule (it logs, returns and stores only its own words), no call under the write lock, nothing called published without Facebook's own id or the owner's word, no credit.

**What changed from v1, and why:**
1. **One model, one way to publish** (devil's advocate 1). v1 kept the single poster's publication (`facebook_publications`, its routes and its sheet, built as T-FB-003) beside the post, with rules to stop one being played against the other; the review's worst findings were in those rules. Nothing of the feature is on a remote or a server: the table has no real row. So a publication of one poster is now a post of one image. The final panel's « Publier sur ma Page » stays as the quick way in: it adds the poster to the draft and opens the page. `facebook_publish.py`, its three routes and the final panel's sheet go; migration 0019 turns what 0018's table holds into posts and drops it.
2. **Nothing uploaded is deleted by the app** (devil's advocate 7, review 9). A photo left behind is not shown on the Page; two paths already left ones that could not be deleted; the deletions broke the shutdown's bound.
3. **« What the owner saw » carries a state, not only an id** (review 3).
4. **The request and its key are kept on the device before they leave** (review 4), and the draft is kept until the post is published (review 7, devil's advocate 4).
5. **One task owns a post from its admission to its settlement**, and a post in flight that no task holds is settled as at a restart (review 6).
6. **The last check, the limit included, is in the write that sets `posting`** (review 5).
7. **A restore never makes a possibly public post « non publiée »** and brings a post whole, whatever posters survive (review 1, 2).
8. **« Arrêter l’envoi »** while the images are being sent (devil's advocate 3).
9. **The draft's posters are resolved by id**, whatever page of the candidates they are on (review 7, devil's advocate 2).

**What the proofs settled** (requirements, « What the proofs showed »): photos uploaded with `published=false` answer `{"id"}` and are not in the Page's photo list; `POST /{page-id}/feed` with `attached_media[n]` makes one post whose photos keep the order sent, and answers `{"id": "<page>_<post>"}`; 12 photos are accepted; a post can be made unseen for a test. **Not settled, to prove before task 2** (« To prove »): the largest number Facebook accepts and the code of its refusal; a post of one photo made this way.

**The one idea.** A post is N uploads that show nothing, then one call that publishes. Everything before that last call can fail, stop or be tried again without anything public; only the last call can leave an unknown outcome.

```
browser                          server                                    Facebook
  keeps {key, body} on the device
  POST /api/facebook/posts   ──► one task: admitted (one write) 'uploading'
  ◄── 202 {id}                   for each image, in order
  GET  …/posts/{id} (2 s)          read the confirmed PNG ────────────────► POST /{page}/photos published=false
  ◄── uploading 3/7                keep its photo id (one short write)    ◄── {id}
                                 last check + 'posting' (one write)
                                                           ───────────────► POST /{page}/feed attached_media[…]
  ◄── published + link           settled (one write)                      ◄── {id: page_post}
  forgets {key, body}, the draft
```

## D-FB-POST-001 — What is stored (covers R-FB-POST-003, 005, 006)

Two migrations, forward only, hand-written SQL: **0019** adds the column and the two tables (T-FB-008, beside the built single poster's code, which keeps working); **0020** converts what 0018's table holds, counts, and drops it, with the code that replaces it (T-FB-009). Both are released with 0018.

```sql
ALTER TABLE shop_profile ADD COLUMN post_image_limit INTEGER CHECK (post_image_limit IS NULL OR post_image_limit >= 1);

CREATE TABLE facebook_posts (
  id TEXT PRIMARY KEY NOT NULL,
  shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  page_id TEXT NOT NULL, page_name TEXT NOT NULL,
  description TEXT NOT NULL,
  key TEXT NOT NULL, payload_sha TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('uploading','posting','published','failed','unknown')),
  stop_asked INTEGER NOT NULL DEFAULT 0,
  sent_at TEXT NOT NULL, settled_at TEXT,
  post_id TEXT, link TEXT, error_code TEXT, failed_position INTEGER,
  said_by_owner INTEGER NOT NULL DEFAULT 0,
  UNIQUE (shop_id, key)
);
CREATE TABLE facebook_post_items (
  post_id TEXT NOT NULL REFERENCES facebook_posts(id),
  position INTEGER NOT NULL CHECK (position >= 0),
  creation_id TEXT NOT NULL, confirmation_id TEXT NOT NULL, png_sha256 TEXT,
  photo_id TEXT,
  PRIMARY KEY (post_id, position),
  UNIQUE (post_id, creation_id)
);
CREATE INDEX facebook_post_items_creation ON facebook_post_items (creation_id);
-- 0020: what 0018's table holds becomes posts of one image (no real row exists: nothing was released), then it goes
INSERT INTO facebook_posts (id, shop_id, page_id, page_name, description, key, payload_sha, status, sent_at, settled_at,
                            post_id, link, error_code, said_by_owner)
  SELECT id, shop_id, page_id, page_name, caption, key, payload_sha, CASE status WHEN 'sending' THEN 'posting' ELSE status END,
         sent_at, settled_at, post_id, link, error_code, said_by_owner FROM facebook_publications ORDER BY rowid;
INSERT INTO facebook_post_items (post_id, position, creation_id, confirmation_id, png_sha256)
  SELECT p.id, 0, p.creation_id, p.confirmation_id, k.png_sha256 FROM facebook_publications p
  LEFT JOIN confirmations k ON k.id = p.confirmation_id;
-- the migration then counts: as many posts and as many items as the table held rows, or it stops before the drop
DROP TABLE facebook_publications;
```

- *(r2)* **The conversion loses nothing:** the join is a left one (a restored publication may name a confirmation that is not here), so every row becomes a post **with its item**; the migration counts posts and items against the rows before it drops the table. `png_sha256` is NULL only on such a converted item: a new item always has it. An item without a hash still blocks its poster while its post is unknown.
- A drop in a new forward migration: 0018 is not edited; it is applied on development data only, and 0018 and 0019 are released together, so no released database ever holds the old table.

- `creation_id` and `confirmation_id` on an item are historical references without a foreign key, as 0018's were: a post keeps its line when a poster is gone, and a restore can bring a post whose poster it lacks.
- `post_image_limit`: NULL is no limit (the default); the operator's setting, a later tier's lever.
- A post's order among posts is its `rowid` (the clock may step back); `sent_at` is shown only.
- `photo_id`: the unpublished photo Facebook made for that image. Never shown, never sent to the browser; kept as the proof that the image was uploaded.
- `stop_asked`: the owner asked to stop the uploads.
- No wall-clock time of the `posting` write is kept: its 30 s rule counts on the monotonic clock, in the task.

## D-FB-POST-002 — The Graph client (covers R-FB-POST-005)

In `posters/facebook.py`, under its existing rule and gates (`credential()`, `_kept`, typed arguments, failures returned, never raised). `publish_photo` goes with the single poster's path; two methods come:

| Method | Call | Returns |
| --- | --- | --- |
| `upload_photo(page_id, page_token, png) -> Upload` | `POST /{page-id}/photos`, multipart `source`, form `published=false`, `access_token`, `appsecret_proof`; 60 s | `Upload(status, photo_id, error_code, reconnect)`: `uploaded` only on a 200 whose `id` is digits and no credential; `failed` on a 4xx with a known code; `unknown` otherwise |
| `create_post(page_id, page_token, message, photo_ids) -> Outcome` | `POST /{page-id}/feed`, form `message` (left out when empty), `attached_media[n]={"media_fbid":"<photo id>"}` in order, `access_token`, `appsecret_proof`; 60 s | the existing `Outcome`: `published` only on a 200 whose `id` has the shape `<page_id>_<digits>`, the link built as today (`https://www.facebook.com/{id}`); the rest as `classify` rules today, which now reads `id` |

- `StubGraph` gains the two, with ids of the right shapes. The markers of T-FB-003 act on the description for `create_post` (`[stub:unknown]`, `[stub:refused]`, `[stub:reconnect]`); `[stub:image:N]` makes the Nth upload fail with code 100; `[stub:slow]` makes each upload wait for the smoke's « Arrêter l’envoi ».
- *(r2)* **Each call has a deadline on elapsed time**, around the whole call (75 s), beside the client's 60 s timeouts: an answer that trickles cannot hold a call open. Its expiry is an `unknown` upload, or an `unknown` post for the last call (the request may have left).
- No deletion of a photo: a photo uploaded and not attached is not shown on the Page (proof 3) and stays. Said in « Vos données » and the runbook.
- Facebook's refusal for too many photos has no known code until its proof; an unlisted code settles `unknown`, as today.

## D-FB-POST-003 — Publishing a post (covers R-FB-POST-002 to 005)

New module `posters/facebook_posts.py`, in place of `facebook_publish.py`, whose proven parts it keeps: the key and its `payload_sha` in the table's own column (never `store.mutate`), `_live` inside the write, the 30 s rule on the monotonic clock, the settling write tried again with the outcome in hand, the task shielded from the client's going.

**Routes** (registered only when the provider is not `off`):

| Route | Answers |
| --- | --- |
| `GET /api/facebook/posts/candidates?limit&before&ids` | the Page `{id,name,state}`; the shop's limit; a page of posters that can go in a post, or with `ids` those posters whatever their state; the counts of those that cannot, by reason |
| `GET /api/facebook/posts?limit&before&creation` | the shop's posts, newest first; with `creation`, those that hold that poster |
| `POST /api/facebook/posts` (`Idempotency-Key`) | 202, the post as it is now |
| `GET /api/facebook/posts/{id}` | the post, with its description, for the page's polling |
| `POST /api/facebook/posts/{id}/stop` | asks an `uploading` post to stop; answers the post |
| `POST /api/facebook/posts/{id}/outcome` (`Idempotency-Key`, `{present}`) | the owner's word on an `unknown` post, through `store.mutate` (no call) |

**A candidate** is an active poster of the shop with a confirmation in the format `feed` whose `confirmed_revision` is the poster's current revision (the latest such). It carries: the poster's id, name, title and price as `/api/creations` gives them; `confirmation_id`; the thumbnail and the download address of the confirmed file; and for the connected Page `last`: the id **and the status** of the latest post that holds this poster there (null when none), and `published_at`: the date of the latest one that is `published` (null when none). With `ids`, a poster that is not a candidate comes back with its reason instead: `other_format`, `changed`, `unconfirmed`, `gone`. Paged as `/api/creations` (cursor, 20 a page); `ids` is not paged (200 at most).

**The request:** `{ page_id, description, items: [{ creation_id, confirmation_id, seen: {id, status} | null }] }`, the items in the post's order.

**One task owns the post.** The route makes one task and registers it **under `(shop, key)` before the admission**, in the module's table of tasks; it stays there until its post is settled. The route awaits only the admission, shielded: a client that goes after the commit cannot leave a row without a task, and *(r2)* a read that comes right after the commit finds the row's owner by the row's own `(shop_id, key)`.

**1. The key first** (one read): a row of this shop with this key answers as it is now when the body is the same (`idempotency_reused` when not). No file is looked at before this: a request already accepted is answered even if a file has gone since.

**2. Prepared** (no transaction): each item's confirmed file exists and is at most 10 MB (a `stat`). `export_missing` or `facebook_too_large`, with the position.

**3. Admitted** (one write transaction; a refusal writes nothing), in this order:
1. the key again (a race with another request of the same key);
2. the session is live (`_live`) and the conditions accepted (`terms.require`);
3. the shop's Page is `connected` and is `page_id` (`facebook_not_connected`, `facebook_reconnect`, `facebook_stale`);
4. at least one item; no poster twice (`validation`); at most `post_image_limit` when the shop has one (`facebook_too_many`, 422, the limit in its sentence);
5. each item is a candidate and its `confirmation_id` is that candidate's (`facebook_stale`);
6. the description's rules, a caption's (2 000 code points; no control character but line feed and tab; only blanks is empty) (`caption_invalid`);
7. **nothing in flight:** the shop has no post `uploading` or `posting` (`facebook_running`); none of the items' posters is in a post `unknown` on this Page (`facebook_pending`);
8. **what the page showed is still true:** for each item, `seen` equals the id and the status of the latest post that holds this poster on this Page, or is null when there is none (`facebook_stale`). A tab whose unknown post was answered in another, or whose poster went out meanwhile, has not seen it;
9. `check_mode`.
The post is written `uploading` with its items (each with the confirmation's `png_sha256`); the Page's token and `connected_at` are taken for the task.

**4. The uploads**, one image at a time, in order. *(r3)* Before the first, every item is checked again as at the admission: still a candidate, with the same confirmation (`poster_changed`, with its position): a poster changed before anything is sent stops the post. After the first upload the post sends the files that were confirmed (edge cases). Before each, one short read: **stop** if the service is closing (`not_sent`), `stop_asked` (`stopped`), the shop no longer active (`not_sent`), the Page no longer the one that gave the token: same `page_id`, same `connected_at`, state `connected` (`page_changed`), or *(r2)* the shop's limit now below the number of items (`limit_lowered`): so a limit lowered right after the admission stops the post before its first image leaves. Else the PNG is read and its hash checked (`exports.read_png`: `export_missing`), then `upload_photo`. An `unknown` upload (timeout, network, 5xx) is tried **once more**, unless the service is closing: an upload shows nothing, so a second one cannot publish twice. The photo's id is written on the item (one short write, tried again as a settling write is). A stop or a failed upload settles the post `failed` with its code and `failed_position`; a 190 marks the Page `reconnect` under the existing rule. Nothing is deleted.

**5. The last check and `posting`: one write transaction, the cutoff.** In it: the service not closing, `stop_asked` not set, the shop active, the Page the same, **and the shop's limit still not below the number of items**; then `status='posting'`. Any of them failing settles `failed` in that same transaction (`not_sent`, `stopped`, `page_changed`, `limit_lowered`). What changes after this commit does not stop the post. No call is made inside it.

**6. The last call.** Right before it leaves, the 30 s rule (monotonic, from that commit): too late, and the post is `failed` (`not_sent`). Else `create_post`, **never sent twice**. Its `Outcome` settles the post: `published` with `post_id` and link; `failed` with a known code; `unknown`. The settling write is tried again with the outcome in hand.

**7. A post that no task holds.** At start, and whenever a route reads a post `uploading` or `posting` whose `(shop_id, key)` is not in this process's table of tasks (a task that died on a write that kept failing), by an update that names the status it read (`WHERE id=… AND status=…`), so that a task's own write is never overwritten: `uploading` becomes `failed` (`not_sent`): its last call was never made, since `posting` is committed before it; `posting` becomes `unknown`. So no row waits for a restart to free its shop. The start-up rule sits beside `facebook_connect.recover` in the API's start, **never** in the shared runtime start: `restore.sh` runs `after-restore` before the service starts, and must find the rows as the backup left them.

**8. Shutdown.** `drain()` sets the closing flag and awaits the tasks. A post still uploading ends at its next check (`not_sent`), without the second try of an upload; a post whose last call is on its way finishes and settles. The wait is one call's deadline (75 s) plus the settling's tries, well inside the container's `stop_grace_period` of 5 minutes.

**9. The owner's word** (`unknown` only): `present: true` gives `published`, `said_by_owner`, the link `https://www.facebook.com/{page_id}`; `false` gives `failed` (`not_published`). The same key replays its answer. His answer changes the post's status, so every tab that held `seen` on it is stale (admission 8).

**A post as a route answers it:** `{id, status, page_id, page_name, sent_at, settled_at, count, done, failed_position, link, error_code, said_by_owner, stop_asked, message_fr, items: [{position, creation_id, thumbnail_url}]}`; `done` is the number of items that have a photo id. No token, no key, no photo id. `GET …/posts/{id}` adds the description.

**Sentences** (`MESSAGES`, French):

| State | `message_fr` |
| --- | --- |
| `uploading`, `done < count` | « Envoi de l’image {done+1} sur {count}… » |
| `uploading`, `done = count` *(r2)* | « Images envoyées. Publication… » |
| `posting` | « Publication en cours… » |
| `published` | « Publié sur {Page}. » / « Présence confirmée par vous » |
| `unknown` | « Je ne sais pas si la publication est sur votre Page. Ouvrez votre Page et dites-le-moi. » |
| `failed`, an upload refused *(r3)* | « L’image {n} n’a pas pu être envoyée (code N). Rien n’a été publié. Retirez l’image {n} ou remplacez-la, puis réessayez. » |
| `failed`, `poster_changed` *(r3)* | « L’affiche {n} a changé avant l’envoi. Rien n’a été publié. Vérifiez-la à nouveau. » |
| `failed`, `export_missing` | « Le fichier de l’image {n} est introuvable ou abîmé. Rien n’a été publié. Vérifiez cette affiche à nouveau. » |
| `failed`, `not_sent` | « La publication n’est pas partie. Rien n’a été publié. Réessayez. » |
| `failed`, `stopped` | « Envoi arrêté. Rien n’a été publié. » |
| `failed`, `page_changed` | « Votre Page a changé pendant l’envoi. Rien n’a été publié. » |
| `failed`, `limit_lowered` | « Le nombre d’images permis a changé pendant l’envoi. Rien n’a été publié. » |
| `failed`, the post refused | « Facebook a refusé la publication (code N). Rien n’a été publié. » |
| `failed`, code 190 *(r2)* | « Reconnectez votre Page. Rien n’a été publié. » |
| `failed`, a permission code (10, 200 to 299) *(r3)* | « Facebook a refusé la publication (code N) : l’autorisation manque. Rien n’a été publié. Reconnectez votre Page en l’autorisant ; si cela se répète, contactez l’opérateur. » |
| `failed`, a limit code | « Facebook limite les publications pour le moment. Rien n’a été publié. Réessayez plus tard. » |

*(r3)* When the failure came at an upload, each of these sentences starts with the image: « Image {n} : … ».
| `failed`, `not_published` | « Vous avez dit qu’elle n’est pas sur votre Page. » |
| refusal `facebook_too_many` | « Votre boutique peut mettre {N} images au plus dans une publication. » |

## D-FB-POST-004 — The operator's limit (covers R-FB-POST-003)

`python -m affiche.shops post-limit <identifier> [<N> | none]`: with no value it prints the shop's limit; `N` (1 or more) sets it; `none` removes it. `list` shows it. The dashboard is not changed in this feature.

## D-FB-POST-005 — The page (covers R-FB-POST-001, 002, 004, 006)

A new view `publier` (`#publier`), its own component `ShopPublish.vue`. Shown only when `capabilities.facebook`.

**How it is reached.** Desktop: an entry « Publier » in `nav.nav`, after « Mes affiches ». Phone: the bar keeps its five entries; « Publier sur Facebook » is a button at the top of « Mes affiches » and a line on Accueil. **A confirmed poster's final panel:** « Publier sur ma Page », beside « Partager », for a poster that is a candidate. *(r2)* It opens the page **for this poster alone** (`#publier-<poster id>`): the one image, and as its description **the poster's own caption, the one « Partager » keeps**, shown and editable there (R-FB-PUBLISH-002 as it stands). The draft of a post of several is not touched: a line says « Votre publication en préparation ({n} affiches) est gardée. » with the way to it, and « Publier plusieurs affiches » leads to the page itself. For a confirmed poster in another format the panel says « Pour publier sur votre Page, vérifiez cette affiche au format Publication. » The final panel's own sheet (T-FB-003) goes.

**Current practice read first (2026-11-21):** composers keep the order visible, let it change after the choice without choosing again, and give a way that is not a drag (Agorapulse, ContentStudio, Typefully; WCAG 2.5.7). So: numbers on the thumbnails and two buttons to move; no drag in this version.

**The page, top to bottom, one column on a phone:**
1. **« Publier sur Facebook »** and « Sur la Page {name} ». With no Page, or one to reconnect: one sentence and the way to « Mon compte »; sections 2 and 3 are not shown. *(r2)* **Section 4 is always shown:** a post whose outcome is unknown must be answerable with no Page connected (after a restore, every connection is gone), and its route asks for none. With the conditions not accepted: the sentence and the button that opens them, as a paid control does. (A suspended shop has no session: the sign-in page says so, as today.)
2. **« Votre publication »** — the draft. The chosen posters in their order: thumbnail, number, name, « Plus tôt », « Plus tard », « Retirer »; the first says « En tête ». The shop's limit when it has one (« {N} images au plus par publication »; at the limit the grid no longer adds, and says why). « Description de la publication »: a textarea, and beside it, always shown, *(r3)* « 2 000 caractères au plus. Les retours à la ligne et les émojis sont gardés. Les caractères de contrôle sont refusés, sauf les retours à la ligne et les tabulations. » with the count; a refused character is said as soon as it is typed or pasted. « Reprendre la légende de… » (one button per chosen poster that has a caption; it asks before it replaces a description that is not empty). Then « Publier… » (the main action) and « Vider ».
3. **« Affiches confirmées »** — the candidates, a grid: a tap adds the poster at the end or takes it out; a chosen one shows its number; « Publiée le {date} » on one already on this Page; « Résultat inconnu : répondez plus bas » on one whose latest post is `unknown` (it cannot be added). « Voir plus » for the next page. Under the grid, when posters are left out: « {n} affiches ne sont pas proposées : » and one line per reason with its action (« confirmées dans un autre format : vérifiez-les au format Publication », « modifiées depuis leur vérification : vérifiez-les à nouveau », « jamais vérifiées »), each leading to « Mes affiches ».
4. **« Publications »** — the shop's posts: date, Page, « {count} images » with the first one's thumbnail, the state's sentence, « Voir la publication ». The one in flight shows its progress, is read again every 2 s while the page is open (the jobs' rhythm and back-off), and while `uploading` offers **« Arrêter l’envoi »**. An `unknown` one has « Ouvrir ma Page », « Elle est sur ma Page », « Elle n’y est pas » with its warning (« Si elle apparaît plus tard, publier à nouveau créera un doublon. »).

**The confirmation** (the editor's existing sheet): « Publier sur {Page} ? », the images in their order as a numbered strip that scrolls sideways inside the sheet, the description as it will be sent, « Publier », « Annuler ». The strip shows the confirmed files' thumbnails, each a link to its confirmed file: thirty full files would not load on a phone's connection, and the exact file is the server's to guarantee (its hash is checked before it leaves; a damaged one fails the post, names the image and publishes nothing). « Publier » is off until every thumbnail has loaded, and while a post is in flight (with the reason). What the sheet shows is frozen when it opens: the items, their `seen`, the description.

**What is kept on the device** (the shop's storage, cleared at sign-out):
- `post-draft`: the posters' ids in order, the description, and *(r2)* a stamp that changes at each edit. Written at each change; cleared by « Vider », and when the post made from it is `published` (by Facebook or by the owner's word) **and its stamp is still the one that was sent**: a draft edited since, in this tab or another, is kept. A failed or stopped post leaves it as it was: nothing is chosen or typed again. (The page for one poster keeps no draft: its description is the poster's caption.)
- `post-sent`: the exact body, its key and the draft's stamp, **written before the request leaves**. *(r2)* Unlike a chat read, which goes on from memory when the write fails, **a write that fails stops the publication:** nothing is sent, and the page says « Cet appareil n’a pas pu garder la demande : rien n’a été envoyé. Libérez de la place ou quittez la navigation privée, puis réessayez. » It is cleared only by the answer to its own key. At every opening of the page and before any new « Publier », a `post-sent` is sent again first, with its key: the server answers the post as it is, and the page follows it. It is cleared when its post is settled, or when the server refuses it without a row. So a lost 202, a reload or a closed tab never makes a second post.
At opening, the draft's posters are resolved with `candidates?ids=`, 200 ids a request: one that can no longer go is taken out and named with its reason.

**The final panel** lists the posts that hold its poster (`GET /api/facebook/posts?creation=`): date, Page, « seule » or « dans une publication de {count} images », state, link; an `unknown` one sends to the page to answer.

**Refusals on the page:** `facebook_stale` reads the candidates and the posts again, keeps the draft, closes the sheet and says what changed; `facebook_pending`, `facebook_running`, `facebook_too_many`, `caption_invalid` are said beside « Publier… »; no answer keeps `post-sent` and says « La réponse n’est pas arrivée. Je vérifie… » until the next read answers.

## D-FB-POST-006 — What is said and what is restored (covers R-FB-POST-007)

- **« Vos données » and the conditions** (version 2026-11-21, not released yet: the same version is amended; if it has been released by then, a new one): one or several posters; the record of a post is its posters, their order, its description, its result and what the service retained of Facebook's answer; a photo sent and not published stays with Facebook, unseen on the Page. One acceptance.
- **`shops after-restore`** (in place of T-FB-004's step on publications, same report and `--apply` rule): every Page connection goes, as today. A post the restored database lacks is copied **whole** with its items, whatever posters are here (items hold no foreign key); only a post whose shop is not here is named and skipped. A post both hold: when the kept one is `published` or `failed`, a restored one that is `uploading`, `posting` or `unknown` takes that settlement; when the kept one is `posting` or `unknown`, a restored one that is `uploading` or `posting` becomes `unknown`: **if either copy says the last call may have left, the post is unknown unless the kept copy knows its end.** `post_image_limit` is not copied; the report says when the two differ. The mode rule is unchanged.
- **Runbook:** `post-limit`; photos that an unfinished post left on a Page are not shown on it; the proofs below.

## Failure modes

| What fails | What happens |
| --- | --- |
| One image is refused, missing or damaged | nothing is published; the post is `failed` and names the image; the draft is kept |
| Facebook is slow or down during the uploads | each upload is tried twice at most; then `failed`, nothing published; the owner may stop it himself |
| The answer to the last call is lost | `unknown`: the owner says; none of its posters can go in a post on that Page until he has |
| Facebook refuses the post (too many photos, a limit, a permission) | `failed` with the code when it is a known one, `unknown` when it is not |
| The answer to « Publier » is lost, the page reloaded or closed | `post-sent` is sent again with its key at the next opening: the same post, never a second |
| The owner closes the application during the uploads | the task goes on; the page shows the state at his return |
| The server stops during the uploads | at start the post is `failed` (`not_sent`) |
| The server stops during the last call | `unknown` at start |
| A write of the task keeps failing | the task ends; the next read of the post settles it as at a start |
| The Page is disconnected or replaced, the shop suspended, or its limit lowered, before the last call | `failed`, nothing published |
| The access is cancelled (190) | the post fails and the Page becomes `reconnect`, only if it is still the Page that gave the token |
| Two tabs publish the same draft | the second is refused: a post is in flight, or its `seen` is no longer the latest id and status |
| A restore | `after-restore` brings the posts whole and never calls a possibly public one « non publiée » |

## Edge cases

- One poster only: a post of one photo through the same two kinds of call (to prove once that it looks like a photo post).
- A poster changed after the post was admitted: the post sends the file that was confirmed then, whose hash it holds. « Arrêter l’envoi » is the way to stop it.
- A poster abandoned after a post: the post keeps its line and its count; its thumbnail falls back to a placeholder.
- A limit lowered below a draft's size: the page says the limit and « Publier… » is off until posters are taken out.
- Very many images: one upload at a time (a 1 GB container, files up to 10 MB); a post of 30 images takes minutes, which the progress line shows; the worst case is two timeouts an image, which « Arrêter l’envoi » ends.
- A draft's poster confirmed again in another format: named and taken out at the next opening.

## Tests

- **Backend (pytest, `httpx2.MockTransport`):** the client's two methods (the fields sent, `published=false`, the order of `attached_media`, `id` as the post's id, each classification, no credential in a return or a log); the migration's rehearsal, with a row of each status of 0018's table turned into a post, one of them naming a confirmation that is not there: as many posts and items as rows. Admission: the key answered before any file is looked at; each refusal writes nothing; the limit (none, at, over); a poster twice; a candidate in another format, changed, another shop's; in flight; `seen` with a wrong id and with the right id and a status that has changed. The task: a client that goes right after the commit leaves a task; a read right after the commit does not take the post for one that no task holds; a call whose answer trickles past its deadline; the order sent is the order chosen; `done` after each upload; an upload tried once more and only once; a refused upload names its position and publishes nothing; a stop asked; a Page changed, a shop suspended, a limit lowered, before the last call; the last call never sent twice; the 30 s rule; the lock not held during a call. A post that no task holds, read by a route. Restart and shutdown. The owner's two answers, and the stale `seen` after them. `off`: 404 on the six routes. `post-limit`. `after-restore`: a post copied whole with a poster missing; settled from the kept database; `uploading` here and `posting` there becomes `unknown`.
- **Vitest:** the draft (add, remove, move, the limit, a poster resolved as no longer a candidate); `post-sent` written before the request and sent again at opening; a storage that refuses the write: nothing is sent; a draft edited after the request is kept when its post is published; the page for one poster uses the poster's caption and leaves the draft; what « Publier… » does in each state; a post's line.
- **Browser smoke (stub):** reach the page on a desktop, on a phone and from a poster's final panel (that poster alone, its caption, the draft kept); an unknown post answered with no Page connected; choose three posters, reorder, take a caption as the description, publish, the progress then the link, the order sent; the draft kept after a refused image (`[stub:image:2]`) and cleared after a published post; a reload while the answer is held: one post; « Arrêter l’envoi » (`[stub:slow]`); the operator's limit; an unknown outcome and each answer; a poster in another format counted and not offered; `off`: no entry and no button.

## To prove (free; with the owner's token)

Before task 2, unseen (scheduled, not published), on any Page of his:
1. The largest number of images and the code of Facebook's refusal (40 is next). A fixed maximum goes on the page before the owner reaches it.
2. A post of one photo made with `attached_media`: created, and read back as a photo.
3. `temporary=true` on an upload that is never attached: whether Facebook removes it by itself. If so, uploads use it.
At the first real post: the collage as a visitor sees it; that the link built from the post's id opens.
To weigh after it (devil's advocate 5): a post created `published=false` with no schedule, then `is_published=true` on its known id. A lost answer could then be read by id, and the unknown state would go.

## Not done

Drag to reorder; « Reprendre » a failed post on another device; the description editor (T-FB-007); scheduling; posters of several formats in one post; editing or removing a post; the dashboard editing the limit; uploads in parallel; deleting uploaded photos; a look-up of an unknown post.

## Tasks (to enter in TODO.md once this design is approved)

1. Migration 0019 (the column, the two tables); the client's two methods (`meta` and `stub`), beside `publish_photo`; `shops post-limit`; their tests.
2. Migration 0020 (the conversion and the drop); `publish_photo` removed; `facebook_posts.py` in place of `facebook_publish.py`: the six routes, the admission, the task, the post that no task holds, start and shutdown, the owner's word; `after-restore` on posts; their tests. *(After proofs 1 to 3.)*
3. The page, its ways in, the draft and `post-sent`; the final panel's button and list in place of its sheet; Vitest; the browser smokes.
4. « Vos données », the conditions, the runbook.
5. With the owner: the first real post's proofs. (T-FB-005's gates of stage 1 are unchanged.)
