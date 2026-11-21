# Design review r3 — A publish page: one Facebook post with one or several posters (v3)

Reviewer: Codex, read-only, fresh to the design, 2026-11-21. Verdict: APPROVE WITH FIXES (six of round 2's seven closed, one partial; three new P2 and one P3, all in sentences and one check). The fixes are in the design's text, marked *(r3)*; the design is approved under the autonomy grant.

### Round‑2 rulings

| Finding | Ruling | Reason |
|---|---|---|
| 2 · Restore membership | **CLOSED** | The left join preserves the poster ID even when its confirmation is missing. The counts run before the drop, and releasing 0018 and 0019 together addresses the legacy-schema concern for production restores. |
| 4 · Lost admission answer | **CLOSED** | A failed `post-sent` write stops the request. After a lost answer, the browser replays the saved body and key, which the server checks before touching any file. |
| 5 · Shop limit | **CLOSED** | The server checks the limit at admission, before each upload, and in the transaction that commits `posting`. A client cannot bypass that last check. |
| 6 · Worker ownership | **CLOSED** | The task owns `(shop, key)` before admission commits and retains it through settlement. Orphan recovery updates only the status it observed. A same-key replay must preserve that ownership. |
| 7 · Draft and pagination | **CLOSED** | The submitted stamp protects later edits, saved IDs resolve in groups of 200, and the final-panel shortcut opens one poster with its own caption while preserving the multi-poster draft. |
| 9 · Shutdown bound | **CLOSED** | The 75-second deadline covers the whole Graph call, including a trickling response. Shutdown suppresses the upload retry, and expiry during `/feed` yields `unknown`. |
| 10 · Explanations and actions | **PARTIAL · P2** | The 190 and limit messages, disconnected history, owner controls, and completed-upload count are covered. « Les caractères invisibles sont refusés » still misstates the validator. It accepts tabs and zero-width joiners. Say « Les caractères de contrôle sont refusés, sauf les retours à la ligne et les tabulations », and retain the immediate invalid-text message. [Validator](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook_publish.py:32) |

### Additional findings

- **P2 · D-FB-POST-003 §4 — Poster changed before the first upload.** Admit posters A and B, edit B in another tab, then let the worker start. The first-upload check passes and the worker publishes both frozen files. R-FB-POST-005 explicitly says a poster changed before sending stops the post before anything is sent. Recheck **all** selected confirmation IDs against their current revisions at the first-upload check. A change after uploads begin can retain the documented snapshot behavior. [Requirement](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/requirements/facebook-post-page.md#r-fb-post-005--publish-one-post-never-twice-never-half)
- **P2 · D-FB-POST-003, failure messages — A refused image has no recovery action.** If Facebook refuses image 2 with code 324, the owner sees its position and the code, but R-FB-POST-005 also asks what to do. Append « Retirez l’image 2 ou remplacez-la, puis réessayez. » For a 190 or a limit during an upload, keep the image number alongside the existing instruction. [Failure messages](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/facebook-post-page.md:160)
- **P2 · D-FB-POST-002/003 — A withdrawn permission can miss the reconnect instruction.** The inherited classifier treats codes 10 and 200–299 as permission refusals and sets `reconnect` only for 190. A withdrawn grant reported as a permission refusal therefore gets only a generic code. R-FB-PUBLISH-004 asks for reconnect guidance. For permission refusals, direct the owner to reconnect and reauthorize, then contact the operator if refusal persists. [Graph classifier](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:136) · [Requirement](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/requirements/facebook-publishing.md#r-fb-publish-004--when-facebook-says-no)
- **P3 · D-FB-POST-004 — The dashboard already edits shop fields.** Its controls reset passwords and suspend or enable shops. Delete the parenthetical rationale. The CLI-only scope for `post-limit` can stand. [Dashboard controls](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:802)

Read-only review. Facebook behavior was assessed from the recorded proofs.

**APPROVE WITH FIXES**