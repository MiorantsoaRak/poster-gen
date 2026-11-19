# DESIGN — « Partager » a confirmed poster (share-poster)

**Status:** Approved v3, 2026-11-18 (autonomy grant, ADR-120): round-2 fixes applied (not reviewed again). Tasks T-SHARE-001 … 005 in TODO.md. Codex rejected v1 ([round 1](../reviews/share-poster-design-r1-2026-11-18.md)); a [devil's advocate](../reviews/share-poster-devils-advocate-2026-11-18.md) challenged it; v2 applied the lead's six decisions; [round 2](../reviews/share-poster-design-r2-2026-11-18.md) approved v2 with fixes, applied here with the lead's decision on its finding 1.
**Requirements file:** [../requirements/share-poster.md](../requirements/share-poster.md), Draft v1 2026-11-15 (R-SHARE-001 to 005); its **Default** lines are in force; two wordings await the owner (Traceability).
**Depends on:** what is built. One read-only field on the poster read; no migration. Sixth feature of Release 1 « Invitation » (ROADMAP.md, ADR-105). Source: the Meta check of the [review](../reviews/saas-review-claude-2026-11-15.md), lines 74-81.

## System overview

The owner shares from the panel that holds a confirmed poster's download: the editor's final panel.
- **Which file:** the poster read (`GET /api/creations/{id}`) now names the poster's *current* confirmation, the one made at its current revision. Opening a poster (from Home, the library or the editor) and the chat's « Télécharger ou partager » open that confirmation's render, read-only, with no render request. « Partager » exists only for it.
- **An older confirmed file:** it keeps its download but is labelled as an earlier version, without the live price. The existing action to prepare the current version is offered.
- **The JPEG:** the panel already loads the confirmed PNG as its preview. When the browser can share files, the page draws that image on a canvas and keeps one JPEG File for this opening.
- **The tap:** « Partager » starts copying the caption and opens the phone's share sheet with the file, in the same tap. Where the browser cannot share files there is no « Partager »: a sentence says why, and the download stays.
- **The caption** lives on this device, per shop and poster (ADR-083's way).

The parts: one computed field in api.py; `frontend/src/share.ts` (plain functions); App.vue's opening, panel and sentences; one label in ChatView.vue; one line in `donnees.html`; a probe page; a test sheet. No migration, dependency, job, credit or provider call.

```
GET /api/creations/{id} ─▶ confirmation: {id, render_id, format, download_url} | null   (confirmed_revision = current_revision)
  opening (Home, library, editor, chat address) / chat « Télécharger ou partager »
    ├ confirmation ─▶ GET /api/renders/{render_id} ─▶ panel, current: caption + « Partager »   (no POST)
    ├ null ────────▶ opening: today's latest render (if confirmed: « earlier version », no « Partager ») · chat: renderFinal
    └ read failed ─▶ error line + « Réessayer »   (never a render)
panel current, preview <img> loaded and bound to render_id
  canShareFiles()? ─ no ─▶ `cannot` + « Télécharger le PNG confirmé »
        │ yes
  canvas (render's size, #17324D ground) ─▶ toBlob('image/jpeg', 0.9), 10 s deadline ─▶ one File ─▶ « Partager »
  tap #n: capture field + File ─▶ writeText(caption), own handler ─▶ share({ files: [file] }) at once
caption field ── input ──▶ localStorage affiche.shop{N}.caption.{poster} (no prune; erased at sign-out)
```

## What changed from v2 (round 2)

| Round-2 finding | Disposition in v3 |
|---|---|
| High 1: the walk can miss the current confirmation (undo case, 50-job window) and show an old price as shareable | Walk dropped. A computed `confirmation` field on the poster read (lead's decision; D-SHARE-001). An older confirmed file is labelled « earlier version », shows no live price and has no « Partager ». A failed read is its own outcome with « Réessayer », never a render |
| High 2: an app switch closes the gate and loses the outcome | Hidden (`hidden`) is not `out`. The File is dropped on hide; the pending attempt's id and outcome are kept; both are shown, and the File re-prepared, only on return to the same shop, panel and confirmation. One attempt id per tap (D-SHARE-002, 004) |
| Medium 3: confirmation in place is missed | Preparation runs on image load, on a successful confirmation and on return; the loaded element is bound to the render id |
| Medium 4: encoder failures | No 2D context, exceptions, null blob, natural size ≠ render size, `blob.type` not JPEG, a 10 s deadline; late callbacks dropped; canvas released. Metadata wording corrected |
| Medium 5: caption storage | Reads caught; no prune (cross-tab eviction could delete fresh text); a failed clear has its own sentence; one blank rule, after the character rule; « Vos données » wording |
| Medium 6: pending attempts | Copy pending after the share: no claim, then `copy_unknown`. Share pending while visible: a provisional `stuck` after 15 s, withdrawn by a later cancel. Timing checked at the button handler |
| 7: probe commands and claims | Resolved quoted directory, two terminals, `-s SERIAL reverse --no-rebind`, remove only that mapping, stop the server. Own scratch log; buttons wait for the JPEG; `isSecureContext` and APIs logged; a sentinel per tap; what the probe changes, stated |
| 8: task size; acceptance | Five tasks (opening; caption; JPEG and tap; probe; sheet). Traceability separates proposed from verified; R-SHARE-005 stays open without iPhone rows or with guidance only ticketed |

## What changed from v1 (round 1 and the devil's advocate), as settled in v2

| Finding | Disposition |
|---|---|
| Codex 1: a confirmed poster reopens on an unconfirmed render; the chat renders to share | v2: a client walk of recent renders. v3: the `confirmation` field. « Télécharger ou partager » on the chat's card |
| Codex 2, 3: clipboard and share compete; cancel outcomes conflict | `share` called in the tap whatever the clipboard does; AbortError silent; no `busy`; owner decision 3 (D-SHARE-004) |
| Codex 4, 7: caption save; `maxlength` | No server save; device storage; code points, no `maxlength` (D-SHARE-003) |
| Codex 5, 6: file lifetime; JPEG fidelity | One opening token; a browser JPEG of the panel's PNG (D-SHARE-002) |
| Codex 8: migration tests | Moot: no migration |
| Codex 9: unbounded phone task | Probe before the build; the sheet as one deliverable; one follow-up per failure (D-SHARE-005) |
| Codex "keep a server JPEG and a caption column" | Overruled by the lead; the server caption is owner decision 1 |
| Devil's advocate 1, 2, 3, 5 | Applied: browser JPEG; device caption; T-SHARE-001 probe; the chat label |
| DA 4: the weight line never fires | Kept: R-SHARE-003 asks for it; one line |
| DA, tap by tap | The help line before the tap carries the paste instruction and the Page reminder; the invitation says to open the link in Chrome |

## What the code already gives (read 2026-11-18)

| Property | Where |
|---|---|
| `GET /api/creations/{id}` returns `store.get_creation` through `result_response`, a `JSONResponse`; `CreationView` documents it | api.py:941-944, :327-332, :362-364; store.py:232-239 |
| A confirmation records the revision current when it was made (`confirmed_revision`); the library's « Confirmée » is `confirmed_revision = current_revision`. An older render can be confirmed at a later revision when the effective format is unchanged | exports.py:162-183; 0009_poster_exports.py:19-25; api.py:922-923; test_exports.py:76 |
| The editor's format is the document's `primary_format` | App.vue:353; models.py:205 |
| The panel's preview `/api/renders/{id}/preview` is same-origin and serves that render's PNG, checked against its SHA; the render's one confirmation names the same SHA | exports.py:148, :152-159, :170, :176-182; api.py:739-743; App.vue:2140 |
| `get_render` gives `width`, `height`, `source_revision` and, if confirmed, `download_url`; export sizes are 1080×1350, 1080×1080, 1080×1920 | exports.py:144-149; models.py:14 |
| Opening reads the poster, then reopens its latest successful render job, confirmed or not; the facts show the live document's price | App.vue:1206, :1187-1189, :2143 |
| The chat's « Télécharger » runs `renderFinal`, a render POST; `confirmFinal` sets `confirmedDownload` without changing the image | chat.ts:260; ChatView.vue:542; App.vue:1726, :1567-1579 |
| Leaving the tab calls `close()`: the gate becomes `hidden`, the shop's `<main>` is hidden, not unmounted; returning asks the session; another identity gives `out` | App.vue:1404-1410, :1928; api.ts:76-84, :112-118 |
| « Fermer » clears `finalPreview` and leaves `confirmedDownload` set; `perform` holds an app-wide `busy`; `out` clears the shop's page state | App.vue:2138, :1063-1080, :1788-1790 |
| Per-shop device keys, written only for the open shop (a write throws otherwise), erased by a successful « Se déconnecter », a failed erasure reported | api.ts:54-70, :259-269; App.vue:1864-1865 |
| « Vos données » says what the device keeps | donnees.html:49-50 |
| Opening and downloading are free work; the conditions gate runs only at paid admission | terms.py:49-54 |

---

## D-SHARE-001 — Opening the current confirmation (covers R-SHARE-001)

**The one backend change: a read-only field on the poster read.** `GET /api/creations/{id}` (api.py:941-944) adds `confirmation`, computed in that route only. It is not computed in `store.get_creation`, whose result the mutation routes return and replays store. `CreationView` gains `confirmation: CurrentConfirmation | None = None`.

```sql
-- exports.current_confirmation(conn, shop, id, primary_format): one SELECT
SELECT k.id, k.render_id, k.format FROM confirmations k JOIN creations c ON c.id = k.creation_id
WHERE c.id = :id AND c.shop_id = :shop AND k.confirmed_revision = c.current_revision
ORDER BY k.format = :primary DESC, k.confirmed_at DESC, k.id DESC LIMIT 1
```
```
200 { …CreationView, "confirmation": { "id": str, "render_id": str, "format": "feed"|"square"|"story",
                                        "download_url": "/api/confirmations/{id}/download" } | null }
```
- **Current** means `confirmations.confirmed_revision = creations.current_revision`, the library's « Confirmée ». The undo case is caught: two saves, back to the same image, then the earlier preview confirmed. The confirmation records the later revision (exports.py:169-182), so it is current.
- **Two formats confirmed at that revision:** the document's `primary_format` (the format the editor shows) first, then the most recently confirmed. The schema allows it; the ordinary interface makes a locked format a separate poster.
- **Shop isolation:** the join requires `c.shop_id`. An unknown or foreign id is already 404 from `get_creation` (store.py:232-233), before the SELECT.
- **No job list is involved,** so the 50-job window no longer matters. No write, no migration. An older tab ignores the field, so `BUNDLE` is unchanged.

**The client.** One rule for every entry point.
- **Opening a poster** (Home, library, editor, chat address; the read at App.vue:1206). With `confirmation`, the page reads `GET /api/renders/{render_id}` and opens the panel as current. With null, today's rule applies (App.vue:1187-1189). If the latest render it opens is confirmed, that confirmation is not current, since the field would have named it. The panel then opens as an **earlier version**:
  - the heading `earlier` instead of « Votre affiche est prête »;
  - the facts without « Prix affiché » (App.vue:2143 shows the live price);
  - the PNG download kept;
  - « Vérifier l’aperçu final » (`renderFinal`, App.vue:948) offered to prepare the current version;
  - no caption and no « Partager ».
- **The chat's « Télécharger ou partager »** (App.vue:1726; ChatView.vue:542 renamed): `flush()`, then the poster read (quiet).
  - `confirmation` → its render → the current panel, with no render POST.
  - null → `renderFinal` as today, to prepare a file to check.
  - The result is dropped if the poster or its saved revision changed during the reads.
- **A read fails** (the poster read or the render read): the page's error line says `open_failed`, with « Réessayer » repeating the same reads. Never a render.
- A panel opened after `confirmFinal`, or from a render job at the current revision, is current by construction: a confirmation is made at the current revision (exports.py:169-182).
- The editor's « Vérifier l’aperçu final » stays `renderFinal`.

## D-SHARE-002 — The JPEG, made in the browser (covers R-SHARE-003)

**From the image already on screen.** The preview `<img>` holds the confirmed PNG's bytes. At its `load`, the page records `loadedRender = finalPreview.id`.

`prepare()` runs at three moments:
1. the image's `load`;
2. a successful `confirmFinal` (App.vue:1579), since the image is already loaded and does not load again;
3. the gate's return to `shown` within the same opening (D-SHARE-004).

It acts only when all of these hold:
- the panel is current;
- `loadedRender` equals the confirmation's `render_id`;
- `img.complete && img.naturalWidth > 0`;
- `canShareFiles()`;
- no File is held.

**`jpegOf(img, width, height)`** (share.ts), with `width × height` from `get_render` (1080×1350, 1080×1080 or 1080×1920):
- the image's natural size must equal the render's;
- create a canvas of that size; `getContext('2d')` must not be null;
- fill it with `#17324D`, the poster's own ground: an opaque poster is unchanged, a transparent pixel gets the ground, never black;
- `drawImage` from the element itself (a new `Image` would download the `no-store` PNG again);
- `toBlob(callback, 'image/jpeg', 0.9)`, all inside `try`;
- the callback's blob must not be null and `blob.type` must be `'image/jpeg'`: the canvas standard falls back to PNG for an unsupported type, and naming a File `.jpg` does not convert its bytes;
- a 10 s deadline from the start;
- the canvas is released (width and height set to 0) after the callback or the deadline;
- a callback arriving after the deadline, or for an older opening, is dropped.

Any failure gives the state `unprepared`: no « Partager », and the download stays. Reopening the panel tries again.

Then `new File([blob], 'affiche-{format}-{first 8 characters of the confirmation id}.jpg', { type: 'image/jpeg' })`, and `canShareFiles` again with that file.
- **Memory:** a story canvas is about 7.9 MiB in RGBA, plus the decoded preview and the encoder's buffers. A low-memory phone can fail or be slow, and the deadline and fallback cover it.
- **Fidelity:** same size and framing as the confirmed PNG; lossy, with the browser choosing the colour subsampling. Source metadata is not carried through the pixel draw. The browser's encoder may write its own segments. The PNG is never written.
- **Transfer:** nothing added; the panel loads the PNG anyway.
- **Weight:** `blob.size`. Over 1 000 000 bytes, « Image de 1,4 Mo » shows beside « Partager » (tenths, rounded up).

**Lifetime.** `opening` is a counter. It moves when the panel opens or closes (« Fermer » leaves `confirmedDownload` set, App.vue:2138), when it shows another confirmation, and on the gate's `out` (sign-out, another identity). Leaving `shown` for `hidden` (an app switch) does not move it.

| Event | The File | The pending attempt (D-SHARE-004) |
|---|---|---|
| gate → `hidden` (app switch) | dropped | kept: its id and any outcome so far, not shown |
| `hidden` → `shown`, same opening | `prepare()` again from the loaded element | its outcome is shown now, or when it settles |
| close, another confirmation, `out` (sign-out, another shop) | dropped | dropped; later outcomes ignored |

The gate returns to `shown` only when the session names the bound shop (api.ts:76-84), so a return is the same shop. At the tap, the File is used only if its opening, confirmation id and render id are current and the gate is `shown`. The server checked the session when the preview was fetched; at the tap the page enforces its last known session. A handoff already given to the system cannot be recalled.

| State | Panel |
|---|---|
| cannot share | no « Partager »; `cannot`; the download |
| preparing (preview loading, or encoding, at most 10 s) | « Partager » disabled, labelled « Préparation de l’image… », `aria-busy`; the download works |
| ready | « Partager »; the weight line if over 1 Mo |
| not prepared | no « Partager »; `unprepared`; the download |

## D-SHARE-003 — The caption, on this device (covers R-SHARE-002)

**Where:** `localStorage`, key `shopKey('caption.' + poster id)` through `shopStorage` (api.ts:54-70); the value is the text itself. One caption per poster on this device, for all its versions. A copy of a poster starts empty, and so does a second device. A successful sign-out erases the captions with the shop's other keys, as it erases chat threads (ADR-108); a failed erasure is already reported.

**No prune.** A caption is at most 2 000 code points (4 000 UTF-16 units), and there is one per poster the owner captions. A prune (as words.ts:25-28 does) would race across tabs: tab A picks a key to evict, tab B writes it, A removes B's fresh text. A full store instead makes a write fail visibly (`tab_only`).

**One rule, in this order** (share.ts, used by the field, the reader, the tap and « Copier la légende »):
1. **Characters first.** Refused: the C0 controls other than line feed and tab (NUL included), DEL, and the C1 controls (U+0080 to U+009F). A refused character gives `bad_character`. Such a text is never treated as blank, so it never erases the stored caption.
2. **Length:** at most 2 000 code points (`[...text].length`). Over the bound gives `too_long`. There is no `maxlength`, so a paste is never cut.
3. **Blank:** `text.trim() === ''`. A blank text removes the stored entry, copies nothing on « Partager », and disables « Copier la légende ».

With `bad_character` or `too_long`, the field keeps all the text, nothing is written, and the stored value stays.

**Writes:** on each `input` in the tab where the owner types, synchronously, when the rule allows. Nothing is written on opening, on closing, or from another tab's text. An idle tab never overwrites newer text. Two tabs both typing into the same poster's caption: the last keystroke's whole text wins (owner decision 1).

**Failures, every storage call in `try`:**
- **The read fails** on opening: the field opens empty, `tab_only` shows, and nothing is written for this opening, so an unread stored caption is not overwritten unseen.
- **A write fails:** the text stays in the field and `tab_only` shows.
- **A removal fails** (clearing the field): `not_cleared` shows.
- **The stored value is invalid** (not a string, over the bound, a refused character): the field opens empty.

**Copy:** the typed value captured at the tap, whatever its stored state. A poster confirmed before this feature has no entry: the field is empty, and the share runs without a clipboard call.

## D-SHARE-004 — The tap (covers R-SHARE-001, R-SHARE-004)

**Detection is by capability, never by user agent.** `canShareFiles(nav)` is true only when `nav.share` and `nav.canShare` are both functions and `nav.canShare({ files: [new File([new Uint8Array(1)], 'affiche.jpg', { type: 'image/jpeg' })] })` returns true; a throw counts as false.
- It catches a browser without file sharing (the review, line 76: Facebook's and Messenger's in-app browsers on Android), an insecure context, and a desktop without a share sheet.
- `canShare` checks the data, not whether any app will take it.
- A user-agent rule is added only for a browser the sheet shows saying yes and always failing.

**The tap.** The button's click handler calls `shareFile(file, caption, nav)` first, with nothing before it and no `await`:
1. A new attempt id. Capture the field's value and the ready File.
2. If the caption passes the rule and is not blank: `try { nav.clipboard.writeText(caption).then(ok, ko) } catch { ko() }`. The copy is started, never awaited; its outcome is recorded against this attempt.
3. `nav.share({ files: [file] })`, at once, whatever step 2 did. Only `files`: no `text`, `title` or `url` (the review, line 77; WebKit bug 251500).

Nothing else runs on that path: no storage write, no network, no `perform`. Without `perform` there is no app-wide `busy` (App.vue:1063-1080). An outcome applies only to the current attempt in the current opening, so a late outcome from tap one never overwrites tap two.

| Attempt | Panel |
|---|---|
| share resolves; copy settled | `copied` or `not_copied` |
| share resolves; copy still pending | nothing about the copy until it settles. Still pending 3 s later: `copy_unknown` (never a claim of success), replaced if it settles |
| AbortError (sheet closed, or no target) | nothing for this attempt: it withdraws any provisional line, and a later clipboard outcome is dropped |
| InvalidStateError (a share still open; an inactive page) | `stuck` |
| NotAllowedError, TypeError, DataError, anything else | `failed`, plus the copy's outcome as above |
| share pending 15 s of visible time (from the tap, or from the last return to `shown`) | provisional `stuck`: withdrawn by a later AbortError, replaced by a later outcome |
| page hidden meanwhile | the outcome waits for the return (D-SHARE-002) |

- « Partager » stays enabled while an attempt is pending. The download and « Copier la légende » work from the first tap on.
- A resolved share only means an app was picked; the page never says anything was posted.
- Nothing gates the tap: no credit, conditions or pause check, no server call.
- `help` shows before the tap. It carries the paste instruction and the Page reminder, because `copied` is hidden behind Facebook when it matters.

## D-SHARE-005 — Real phones (covers R-SHARE-005)

**Before the build: the probe (T-SHARE-001, optional, run by the owner).**
- Android only. A static page on the computer, reached by the phone over USB.
- Chrome's top-level `http://127.0.0.1:8765/` is potentially trustworthy. Whether the APIs are actually available is logged by the page.
- No application, provider or paid call; the poster store is never opened.
- **What it changes:**
  - adb may start its host server and create its host key;
  - the phone's USB-debugging authorization of this computer;
  - a port mapping, removed afterwards;
  - the phone's clipboard;
  - a real Messenger message, if the owner sends himself the link;
  - each composer up to, not including, publishing.
- The page and its log live in the scratchpad (`$PROBE`), never in the repo. Copying the results into the sheet and TODO.md are separate, explicit writes.

```
PROBE='/absolute/path/of/that/session/scratchpad/share-probe'   # resolved and quoted; never the repo
mkdir -p "$PROBE"                                                # index.html below goes here
# Terminal 1, left running:
python3 -m http.server 8765 --bind 127.0.0.1 --directory "$PROBE"
# Terminal 2:
adb devices -l                                                   # note SERIAL; accept « Autoriser le débogage USB » on the phone
adb -s SERIAL reverse --no-rebind tcp:8765 tcp:8765 && echo MAPPED
#   phone, Chrome: http://127.0.0.1:8765/   after each row: adb -s SERIAL exec-out screencap -p > "$PROBE/row-N.png"
adb -s SERIAL reverse --remove tcp:8765                          # only if MAPPED was printed
# Terminal 1: Ctrl-C stops the server.
```
```html
<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Probe Partager</title>
<textarea id="t" rows="3">Galaxy A15 128 Go
Livraison à Tana 📦</textarea>
<button id="go" disabled>Partager</button> <button id="bare" disabled>Partager sans copier</button> <button id="copy" disabled>Copier</button>
<pre id="log"></pre>
<script>
const $ = id => document.getElementById(id), log = m => { $('log').textContent += new Date().toISOString().slice(11, 23) + ' ' + m + '\n' }
let file, n = 0
log('secure ' + isSecureContext + ', share ' + typeof navigator.share + ', canShare ' + typeof navigator.canShare + ', writeText ' + typeof navigator.clipboard?.writeText)
const c = Object.assign(document.createElement('canvas'), { width: 1080, height: 1350 }), g = c.getContext('2d')
g.fillStyle = '#17324D'; g.fillRect(0, 0, 1080, 1350); g.font = 'bold 90px sans-serif'
g.fillStyle = '#fff'; g.fillText('Galaxy A15', 80, 300); g.fillStyle = '#fc0'; g.fillText('450 000 Ar', 80, 1200)
c.toBlob(b => {
  file = b && new File([b], 'affiche-probe.jpg', { type: 'image/jpeg' })
  const ok = !!b && b.type === 'image/jpeg' && typeof navigator.canShare === 'function' && navigator.canShare({ files: [file] })
  log('jpeg ' + (b ? b.type + ' ' + b.size + ' bytes' : 'null') + ', canShare(file) ' + ok)
  for (const id of ['go', 'bare', 'copy']) $(id).disabled = !(b && b.type === 'image/jpeg')
}, 'image/jpeg', 0.9)
const caption = () => $('t').value + '\n#' + (++n) + ' ' + new Date().toISOString().slice(11, 19)  // a sentinel per tap
function copy(t) { try { navigator.clipboard.writeText(t).then(() => log('copied ' + t.split('\n').pop()), e => log('copy ' + e.name)) } catch (e) { log('copy threw ' + e.name) } }
function tap(withCopy) {
  const t = caption()
  if (withCopy) copy(t)
  try { navigator.share({ files: [file] }).then(() => log('shared'), e => log('share ' + e.name)) } catch (e) { log('share threw ' + e.name) }
  log('tap done')
}
$('go').onclick = () => tap(true); $('bare').onclick = () => tap(false); $('copy').onclick = () => copy(caption())
document.addEventListener('visibilitychange', () => log('visible ' + !document.hidden))
</script>
```
For each Android target of the sheet, the owner:
1. taps « Partager »;
2. pastes in the composer and checks that the pasted sentinel (`#n`) is the log's latest;
3. returns to the page and takes the screenshot.

Then, once each: closes the sheet without choosing, and repeats with « Partager sans copier ». Last, he opens the address from a Messenger message to himself. If Messenger cannot open the loopback address, he records it as unreachable, and in-app sharing stays unverified.

The agent writes `"$PROBE/results.md"` (one line per row, screenshot names) as the probe's own log. Results that arrive before T-SHARE-004 ends adjust it; the probe never blocks the build.

**After the build: the test sheet (T-SHARE-005)**, `docs/project/reviews/share-poster-phones-<date>.md`; it copies in the probe's results if any.
- **Android rows:** the built application with stub data on the computer. A scratch script starts the API as the smokes' `serve()` does (browser_smoke.py:2273-2286: stub providers, `_env_file=None`, temporary data, the shop funded and the conditions accepted) on 127.0.0.1:8000, and prints the shop's password. Vite runs on 127.0.0.1:5173 as the smoke starts it (browser_smoke.py:2321), proxying `/api`. The phone uses `adb -s SERIAL reverse --no-rebind tcp:5173 tcp:5173`, so its origin is http://127.0.0.1:5173, the configured APP_ORIGIN. Never `data-probe`, never `backend/.env`.
- **iPhone rows** need HTTPS: they wait for the release rehearsal, and only if the owner has an iPhone (owner decision 6).

For each row, the owner records: phone and OS version; browser and version (for row 7, which in-app browser); the receiving app and its version; whether « Partager » shows, or which sentence; a screenshot of the sheet; the image in the composer, whole and sharp; who posts (the Page or the person); the caption pasted, with its sentinel, line breaks and emoji; **what the page shows after he returns to it**; whether « Partager » works a second time.

All of these are **to verify on the sheet**: clipboard timing, repeat taps, which targets appear, image quality in the composer, Page identity, the session's handoff to Chrome, app-specific behaviour.

| # | Combination (R-SHARE-005) | Expected |
|---|---|---|
| 1 | Android, Chrome → Facebook, switched to the Page first | image in the composer, posting as the Page; caption pasted; `copied` on return |
| 2 | Android, Chrome → Facebook Lite | unknown (the review could not verify it) |
| 3 | Android, Chrome → WhatsApp | image in the chat composer; caption pasted |
| 4 | Android, Chrome → WhatsApp Business | unknown (the review could not verify it) |
| 5, 6 | iPhone, Safari → Facebook; → WhatsApp | as rows 1 and 3, at the rehearsal |
| 7 | Android: the address opened from Messenger or Facebook | no « Partager », `cannot`. Record whether the download works there, and whether opening in Chrome asks to sign in |
| 8 | Each phone: close the sheet without choosing | nothing shown; « Partager » works again |

| Result (probe or sheet) | Follow-up: its own task, with its share_browser.py row |
|---|---|
| Works | none; the row is the evidence |
| An app gets no image, or a cropped or blurred one | a line under « Partager » naming that app and the way round (download, then attach), shown everywhere: the page cannot know the app |
| The copy fails alongside the share but works alone | the tap only shares, and `help` points to « Copier la légende ». R-SHARE-002's exception is accepted by the owner (owner decision 9) |
| A browser that says yes always fails | a user-agent rule hides « Partager » there, named with its row |
| The in-app browser downloads nothing | `cannot` leads with opening the page in Chrome |
| A share has not settled on return | `stuck` reworded from what the owner saw |

**Release note** (deploy/README.md « Release 1 », added by the lead): the invitation tells shops to open the link in Chrome, not inside Messenger or Facebook.

**Until the sheet is filled, the feature's behaviour on real phones is unverified**, and Release 1 is not complete (ROADMAP.md: "on a real phone").

---

## French texts (drafts, awaiting the owner's reading)

| Key | Sentence |
|---|---|
| field label | « Légende de la publication » |
| `help` (before the tap) | « Sur Facebook, passez d’abord sur votre Page dans l’application Facebook. Puis touchez « Partager », choisissez l’application et collez la légende dans votre publication. » |
| `copied` (R-SHARE-002) | « Légende copiée : collez-la dans votre publication. » |
| `not_copied` | « La copie a échoué. Sélectionnez la légende dans le champ, puis copiez-la. » *(Changed 2026-11-19 after T-SHARE-003's review: one sentence for a failed copy, from « Copier la légende » or from « Partager ».)* |
| `copy_unknown` | « La légende n’a peut-être pas été copiée. Touchez « Copier la légende » pour être sûr. » |
| copy button | « Copier la légende » |
| `tab_only` | « La légende reste dans cet onglet, sans être gardée sur cet appareil. Copiez-la avant de fermer : en rouvrant l’affiche, l’ancienne légende peut revenir. » |
| `not_cleared` | « La légende n’a pas pu être effacée de cet appareil : elle peut revenir quand vous rouvrez l’affiche. » |
| `too_long` | « La légende dépasse 2 000 caractères : elle n’est pas gardée sur cet appareil. » |
| `bad_character` | « La légende contient un caractère invisible non accepté : elle n’est pas gardée sur cet appareil. » |
| button / preparing | « Partager » / « Préparation de l’image… » |
| weight | « Image de 1,4 Mo » |
| `unprepared` | « L’image à partager n’a pas pu être préparée. Téléchargez l’affiche. » |
| `cannot` | « Ce navigateur ne peut pas envoyer l’image à une autre application. Téléchargez-la, ou ouvrez cette page dans Chrome (Android) ou Safari (iPhone). » |
| `failed` | « Le partage n’a pas pu s’ouvrir. Téléchargez l’affiche, puis ajoutez-la à votre publication. » |
| `stuck` | « Le partage n’a pas répondu. Téléchargez l’affiche, ou rouvrez cette page. » |
| `earlier` (heading, lede) | « Version confirmée précédente » · « Ce fichier a été confirmé avant vos dernières modifications. Vérifiez la version actuelle pour la partager. » |
| `open_failed` | « L’affiche confirmée n’a pas pu être ouverte. » + « Réessayer » |
| chat card button | « Télécharger ou partager » |
| donnees.html:50 | « La conversation de « Par message », vos textes en cours et la légende de chaque affiche restent dans ce navigateur, sur cet appareil seulement ; « Se déconnecter » les efface de cet appareil. Si l’effacement échoue, l’atelier vous le signale. … » |

## Security and isolation

- **The `confirmation` field:** shop-scoped by its join; computed after `get_creation`'s own ownership check; it names only ids and the existing download address, which keeps its own shop join (exports.py:187-192). test_two_shops.py covers it.
- **The File** is the page's copy of a preview already read with the session (api.py:739-743), kept for one opening and one shop (D-SHARE-002).
- **The caption's keys** carry the shop (`shopKey`); a write for any shop but the open one throws; a successful sign-out erases them. The caption is shown by interpolation and goes nowhere but the clipboard.

## Tasks and tests

Five tasks, one session each. Commands run from `backend/`; on Linux the frontend's npm is `corepack npm@10 …`. Generated fixtures only, never `data-probe`. `share_browser.py` is created by T-SHARE-002 and extended by T-SHARE-003 and 004 (stub, own data, zero spend).

**T-SHARE-001: the probe (optional, run by the owner, any time before T-SHARE-004 ends).** The agent writes the page into the scratchpad and gives the commands; the owner runs them.
Verify: `"$PROBE/results.md"` holds a line per Android target, the cancel and the in-app attempt (or "unreachable"). Each result that changes T-SHARE-003 or 004 is noted in TODO.md against that task.

**T-SHARE-002: open the intended render.** The `confirmation` field (api.py, `exports.current_confirmation`, `CreationView`, backend/api/README.md); the opening from the three entry points; the earlier-version panel; `open_failed`; the chat label.

| Test | What it proves |
|---|---|
| test_exports.py / test_api.py | null before any confirmation; after a confirmation, exactly `{id, render_id, format, download_url}`. **Price edit:** confirm at 450 000 Ar, save another price with no render → null. **Undo:** two saves back to the same image, then the earlier preview confirmed → current. **Two formats** confirmed at the revision → the primary's; primary unconfirmed → the most recently confirmed. **More than 50 jobs** after the confirmation, at the same revision → still named. Mutation responses carry no `confirmation` |
| test_two_shops.py | B reading A's poster → 404; B's own poster never names A's confirmation |
| share_browser.py | Confirm A at 450 000 Ar, change the price, no new render; reopen from Home, the editor and the chat. The panel shows the `earlier` heading, no live price in the facts, no « Partager », the download kept and « Vérifier l’aperçu final » offered. The chat posts a render only because nothing is current. Confirmed A plus a newer unconfirmed B at the same revision (written in the database, as the smokes do): from all three entry points the panel is A's and no `POST /renders` leaves. The poster read failing on the chat's button: `open_failed`, then « Réessayer » works, with no render POST. The chat's button reads « Télécharger ou partager » |
| chat_browser.py, browser_smoke.py, terms_browser.py | pass; chat_browser.py:221 and :473 select the renamed button |

Verify: `uv run pytest tests/test_exports.py tests/test_api.py tests/test_two_shops.py -q` → all passed; `uv run pytest -q` → all passed; `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `cd ../backend && uv run python ../frontend/tests/share_browser.py`, `chat_browser.py`, `browser_smoke.py`, `terms_browser.py` → pass.

**T-SHARE-003: keep and copy the caption.** `captionFault`, `readCaption`, the field, its storage, « Copier la légende », `help`, donnees.html:50.

| Test | What it proves |
|---|---|
| Vitest share.test.ts | 2 000 supplementary-plane emoji pass; 2 001 → `too_long`; LF and TAB pass; NUL after a valid prefix, ESC, DEL, U+0085 → `bad_character`; NUL plus spaces → `bad_character`, not blank; whitespace only → blank; invalid stored values → empty |
| share_browser.py | 2 000 emoji typed, edited, reloaded → kept. 2 001 typed → `too_long`, text visible, the stored value unchanged. Multiline paste kept. Clearing removes the entry; a failed removal → `not_cleared`. Read throwing → empty field, `tab_only`, nothing written; write throwing → `tab_only`, the typed text still copied by « Copier la légende ». Two tabs: an idle older tab never overwrites; no prune. Sign-out erases the caption keys. A poster confirmed before the feature → empty field. 360 × 640 in both themes; keyboard order field → « Copier la légende » |

Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `cd ../backend && uv run python ../frontend/tests/share_browser.py` → pass.

**T-SHARE-004: prepare and share the JPEG.** `canShareFiles`, `jpegOf`, `shareFile`, `weight`; the panel's states, the lifetime and visibility rules, the sentences.

| Test | What it proves |
|---|---|
| Vitest share.test.ts | `canShareFiles`: `share` or `canShare` missing, false or throwing → false. `shareFile`: with `writeText` never settling, or throwing synchronously, `share` is called before `shareFile` returns; its argument is exactly `{ files: [file] }`; a blank caption → no `writeText`. Outcomes per attempt: resolved with the copy settled / pending (`copy_unknown` after 3 s) / never settling; AbortError silent with the clipboard resolving, rejecting, or rejecting late; InvalidStateError → `stuck`; NotAllowedError, TypeError → `failed`; tap two's outcome never overwritten by tap one's. `weight`: 1 000 000 → none, 1 000 001 → « 1,1 Mo » |
| share_browser.py | `navigator.share`, `canShare`, `clipboard.writeText` and `HTMLCanvasElement.prototype.toBlob` stubbed with `add_init_script`. **Timing at the button:** `button.click()` inside `page.evaluate` returns with the share stub already called, with the clipboard held. **Share:** one File, `image/jpeg`, `.jpg`, the render's width and height (decoded in the page), the source PNG's metadata not carried; no text, title or url; `copied`. **Prepare on confirmation in place:** first confirmation, no reload → « Partager » ready. **Cancel** with both clipboard outcomes: nothing. **Refused:** `failed`. **Cannot share:** no « Partager », `cannot`, no `toBlob`. **Encoder:** the callback never called → `unprepared` after 10 s; a PNG blob, a null blob, natural size ≠ render size → `unprepared`. A transparent preview → `#17324D` pixels. **Pending while visible:** `stuck` after 15 s, withdrawn by a later AbortError. **App switch (real):** page hidden (`page.evaluate` cannot fake it: a second page brought to the front, or the context's visibility emulation), the session check held, then answered for the same shop: the outcome shown and the File re-prepared; answered for another shop: everything dropped. **Lifetime:** A→B, close → reopen A, sign-out, with a delayed `toBlob`: the shared File is always the current opening's. **Not gated:** conditions unaccepted and zero credit. **360 × 640, both themes; keyboard:** Enter on « Partager » shares |

Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `cd ../backend && uv run python ../frontend/tests/share_browser.py`, `chat_browser.py`, `browser_smoke.py` → pass.

**T-SHARE-005: the test sheet, filled.** Write the sheet, the scratch script and the commands (D-SHARE-005). The owner fills it after the build. Its only deliverable is the filled sheet; each failure becomes its own bounded follow-up task (T-SHARE-006 …).
Verify: rows 1 to 4, 7 and 8 are filled with OS, browser and app versions and the page after return. Rows 5 and 6 are filled, or marked "awaiting the rehearsal" or "no iPhone". Each failure names its follow-up task.

**Not proven here:** any behaviour on a real phone; a phone browser's JPEG weight, subsampling and memory; iPhone.

## Not built, on purpose

- Publishing through Meta's API; scheduling; a caption written by the AI; one caption per network; several posters in one share; a history of shares (out of scope in R-SHARE-001 and 002).
- A caption kept on the server, for a second device (owner decision 1).
- A JPEG made by the server: the panel's PNG is enough. Add one only if a phone's canvas fails on the sheet.
- Sharing an earlier confirmed version: it is downloadable, not shareable.
- User-agent rules, and an `intent://` link that opens Chrome: only from a sheet row.
- « Partager » on Home's rows or on the chat's card (owner decision 5); the caption in the share data.

## Traceability

| Requirement | Decisions | Tasks | Status |
|---|---|---|---|
| R-SHARE-001 | D-SHARE-001, 004 | T-SHARE-002, 004 | proposed; its wording awaits the owner (below) |
| R-SHARE-002 | D-SHARE-003, D-SHARE-004 (the copy) | T-SHARE-003, 004 | proposed; device wording awaits the owner; a phone where automatic copy fails needs owner decision 9 |
| R-SHARE-003 | D-SHARE-002 | T-SHARE-004 | proposed |
| R-SHARE-004 | D-SHARE-004, D-SHARE-002 (the states) | T-SHARE-004 | proposed; in-app behaviour verified only on the sheet |
| R-SHARE-005 | D-SHARE-005 | T-SHARE-001 (optional), T-SHARE-005 | open. Delivering the sheet does not tick it: it stays open while iPhone rows are missing ("no iPhone", "awaiting the rehearsal"), or while any guidance it requires is only ticketed and not shipped |

Wordings asked:
- R-SHARE-001: « beside the download, in the chat and in the editor » becomes « beside the download, on the current confirmed poster's panel, which the chat's « Télécharger ou partager » and the editor open ».
- R-SHARE-002: « kept with the poster » becomes « kept with the poster on this device » (owner decision 1).

## Decisions only the owner can take

Each is in force on its default and can change before the task named.

| # | Decision | Default in force | Until |
|---|---|---|---|
| 1 | Where the caption is kept | This device only, per shop and poster; a second device starts empty; a successful sign-out erases it; two tabs typing at once, the last keystroke wins. Alternative, for a second device: a nullable `creations.caption` column (a migration, with the seven positional `INSERT INTO creations` given column names); a shop-scoped `PUT /api/creations/{id}/caption`; the last save wins | T-SHARE-003 |
| 2 | The caption's bound | 2 000 characters (code points) | T-SHARE-003 |
| 3 | What « a share the owner cancels changes nothing » covers | the page's visible state only. The system clipboard may already hold the caption after a cancel, because the copy starts at the tap | T-SHARE-004 |
| 4 | The panel's main button | « Partager » where sharing works; the PNG download secondary there | T-SHARE-004 |
| 5 | « Partager » on the chat's card or Home's rows | not built: the chat's button becomes « Télécharger ou partager » and opens the panel; R-SHARE-001 is reworded | T-SHARE-002 |
| 6 | The iPhone rows | only if the owner has an iPhone, at the release rehearsal (HTTPS); R-SHARE-005 stays open without them | T-SHARE-005 |
| 7 | The French texts, `help`, `earlier` and `tab_only` included | the drafts above | T-SHARE-002 to 004 |
| 8 | Running the probe | optional, on his Android phone over USB | T-SHARE-001 |
| 9 | A phone where the copy fails alongside the share | the standalone « Copier la légende » accepted as R-SHARE-002's exception for that phone, recorded per row | T-SHARE-005 follow-ups |
