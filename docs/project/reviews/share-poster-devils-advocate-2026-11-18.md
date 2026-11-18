# Devil's advocate — designs/share-poster.md, Draft v1 (2026-11-18, Opus subagent, read-only)

Summary of the points that would change a decision, as reported to the lead.

1. **Make the JPEG in the browser from the image already on screen.** The panel's `<img>` already loads `/api/renders/{id}/preview`, the render's full PNG, the same `png_sha256` the confirmation names (App.vue:2140, api.py:739-743, exports.py:151-183). Drawing it on a canvas at natural size and calling `toBlob('image/jpeg', 0.9)` on `@load` removes `?jpeg=true`, its tests, the 20 s fetch, the « Réessayer » state and ~0.2 MB per showing. Risk: the browser chooses chroma subsampling.
2. **Keep the caption on the device only**, keyed by poster, as ADR-083 keeps a poster's typed words (words.ts:3-6) and chat threads are kept per poster (chat.ts:112). Removes migration 0018, the seven `INSERT INTO creations VALUES` edits, the PUT route, `caption_invalid` and the save-failure states. Risk: sign-out erases it; a second device does not see it. Add the column when a second device is reported or direct publishing needs it.
   Together, 1 and 2 remove the backend task; no requirement line fails.
3. **Run the phone check before building**, with a throwaway page on the operator's Android phone over USB (`adb reverse`; 127.0.0.1 is a secure context), so the outcomes that change the screen are known first. iPhone rows need HTTPS and wait for the release rehearsal.
4. **The weight line** never fires at 0.15–0.23 MB; reword or keep, small either way.
5. **Rename the chat's « Télécharger »** (ChatView.vue:542) so an owner who wants to post knows sharing is behind it.

**Tried to break and could not:** one place for the button (the final panel); fetching before the tap if the JPEG stayed on the server (transient activation is time-limited, HTML Standard); the tap itself (capability detection, `writeText` started before `share()`, files only).

**Tap by tap on a cheap Android phone:** switching Facebook to the Page must happen before the tap, in another app; « Légende copiée » is hidden behind Facebook when it matters, so the help line before the tap must carry the paste instruction; a link opened from Messenger has no « Partager » and asks to sign in again in Chrome: the invitation should say to open it in Chrome.
