# Code review r2 — T-FB-010: the « Publier sur Facebook » page, reworked

Reviewer: Codex, read-only, 2026-11-21. Verdict: REJECT (of round 1's eight: four closed, one no longer applies, three partial; three P1 and two P2: two tabs racing on the draft's storage, an unreadable draft, and the one-poster page after a reload). Answered by removing the cause, not by a lock around each write: one tab at a time holds the page, and the sheet names what is already on the Page; see r3.

### Round-one rulings

| # | Ruling | Evidence |
|---|---|---|
| 1 | **PARTIAL** | A different stored stamp protects the newer draft, but the check and removal are separate operations. A late answer can still erase another tab’s edit. [publish.ts:95](frontend/src/publish.ts#L95) · [ShopPublish.vue:163](frontend/src/ShopPublish.vue#L163) |
| 2 | **NO LONGER APPLIES** | The replay-then-submit path is gone. An `unknown` answer retains its key, and the owner’s two buttons remain available with the Page disconnected. [publish.ts:98](frontend/src/publish.ts#L98) · [ShopPublish.vue:442](frontend/src/ShopPublish.vue#L442) |
| 3 | **CLOSED** | `answered()` checks the live stamp first, so publication leaves a newer in-memory edit intact even when its write failed. [publish.ts:94](frontend/src/publish.ts#L94) |
| 4 | **PARTIAL** | `post-sent` is gone, but an unreadable `post-draft` can still cause data loss during settlement or leave confirmation without a recovery message. [ShopPublish.vue:33](frontend/src/ShopPublish.vue#L33) · [publish.ts:83](frontend/src/publish.ts#L83) |
| 5 | **CLOSED** | `export_missing` displays the refusal and retains the draft’s stamp. [ShopPublish.vue:260](frontend/src/ShopPublish.vue#L260) |
| 6 | **PARTIAL** | List and stop answers now reach the settlement handler. A failed candidate re-read after a POST refusal can still re-enable « Publier… ». [ShopPublish.vue:178](frontend/src/ShopPublish.vue#L178) · [ShopPublish.vue:264](frontend/src/ShopPublish.vue#L264) |
| 7 | **CLOSED** | With three selected and a limit of two, the grid now says « Retirez des affiches ». The count sentence is reserved for equality. [publish.ts:147](frontend/src/publish.ts#L147) |
| 8 | **CLOSED** | Candidate pagination guards the outstanding request, discards superseded answers and filters IDs already displayed. [ShopPublish.vue:103](frontend/src/ShopPublish.vue#L103) |

### Findings

- **P1 — A late answer can erase or restore a draft.** Tab A reads stamp K while handling `published`. Tab B saves edit L before A calls `removeItem`. A deletes L. There is also a path without simultaneous writes: if the storage read throws, `stored()` returns `null` and A still deletes the record. Conversely, after B taps « Vider », a delayed `uploading` answer can write K back. Serialize conditional settlement with draft edits under the same shop-scoped lock. Require a successful read of K before writing or removing anything. [ShopPublish.vue:33](frontend/src/ShopPublish.vue#L33) · [ShopPublish.vue:162](frontend/src/ShopPublish.vue#L162) · [publish.ts:95](frontend/src/publish.ts#L95)
- **P1 — Retrying a failed save can overwrite another tab’s draft.** A’s write fails, B saves L while A’s sheet is open, then A retries. `unsaved` skips the stamp comparison, so A overwrites L and sends. The unit test explicitly expects this mismatch to succeed. Keep the stamp last successfully read by A and compare it before retrying the write. Catch failures from **both** storage reads so « Publier » gives a visible recovery message. [publish.ts:82](frontend/src/publish.ts#L82) · [publish.test.ts:84](frontend/tests/publish.test.ts#L84)
- **P1 — Reloading the one-poster page can duplicate a successful post.** Send K, lose the answer, then reload after Facebook publishes. The component generates L for the unchanged caption. The candidate read supplies the current `published` mark, which permits another submission. The server sees a fresh key and current `seen`. To preserve the one-object rule, use a server-recoverable request identity or require an explicit « Publier à nouveau » confirmation that identifies the existing publication before issuing L. [ShopPublish.vue:63](frontend/src/ShopPublish.vue#L63) · [publish.ts:124](frontend/src/publish.ts#L124)
- **P2 — A failed re-read can enable stale submission.** After `facebook_stale`, the refusal handler calls `readCandidates()` without setting `stale`. If that read fails, `reading` returns to false and the old selection enables « Publier… » again. Use `marksMoved()` on this path so only a successful refresh unlocks publishing. [ShopPublish.vue:116](frontend/src/ShopPublish.vue#L116) · [ShopPublish.vue:264](frontend/src/ShopPublish.vue#L264)
- **P2 — A late list can stop polling an admitted post.** A list request starts before admission. The POST returns `uploading` and schedules a poll. The older list then arrives without that ID, replaces `posts`, and `follow()` cancels the timer. The page can stay on « Aucune publication pour le moment » while the post settles. Keep polling the tracked ID independently of list membership. [ShopPublish.vue:171](frontend/src/ShopPublish.vue#L171) · [ShopPublish.vue:196](frontend/src/ShopPublish.vue#L196)

Static review only. No tests were run or counted.

**REJECT**