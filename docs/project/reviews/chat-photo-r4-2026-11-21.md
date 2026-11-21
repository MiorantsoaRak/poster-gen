# Review r4 — D-TEXT-FIRST-007 v4 and its code; the features warning by words (ADR-125)

Reviewer: Codex, read-only, 2026-11-21, asked by the owner after three rounds. Verdict: REJECT (two P1, two P2; two of the items left on purpose ruled not acceptable). Not answered yet: the owner chooses between a smaller design and more fixes.

**Two paths still let someone pay for a different image than the recap promises.** A replacement first-image recap loses its guard, and a copy can silently lose its pinned words before generation.

### Round‑3 rulings

| Finding | Ruling | Evidence |
|---|---|---|
| P1 · Restored first-image card | **PARTIAL** | An intact `first` card waits for the jobs check. Failed reads retry after ten seconds, and an answer for a different poster or hold is discarded. But a refused first tap replaces the card with an ordinary recap that bypasses the check. [ChatView.vue:287](frontend/src/ChatView.vue#L287) · [ChatView.vue:465](frontend/src/ChatView.vue#L465) |
| P1 · Trimmed paid or copy card | **CLOSED** for the reported long thread | Save and restore both retain unfinished paid and photo cards ahead of the last 100 items. Normal supersession and the single outstanding paid action bound that extra history. `readThread` also reads legacy identity from the full parsed list. Whole-thread eviction is a separate defect below. [chat.ts:138](frontend/src/chat.ts#L138) · [chat.ts:154](frontend/src/chat.ts#L154) |
| P1 · PUT after takeover / earlier holder keeps acting | **PARTIAL** | Copy mutations and paid dispatch check ownership. `createPoster` still crosses awaits before creating the poster and scheduling document edits. [App.vue:1186](frontend/src/App.vue#L1186) · [App.vue:1951](frontend/src/App.vue#L1951) |
| P2 · Retry combines different source words and revision | **PARTIAL** | Both are pinned together. The copy can still lose the words during adoption. [App.vue:2004](frontend/src/App.vue#L2004) · [App.vue:1235](frontend/src/App.vue#L1235) |
| P2 · Storage refusal / credit-gated recovery | **CLOSED** | A pinned attempt gets neutral retry wording and remains recoverable despite a credit stop. [ChatView.vue:267](frontend/src/ChatView.vue#L267) · [chat.ts:295](frontend/src/chat.ts#L295) |
| P2 · Versionless title and price wording | **PARTIAL** | The two specific stale-field messages are fixed. Adjacent help still says both fields remain drawn in an image that does not exist. [App.vue:2364](frontend/src/App.vue#L2364) · [App.vue:2369](frontend/src/App.vue#L2369) |
| P3 · Malformed copy ID / exported predicate | **CLOSED** | `copyMade` requires hexadecimal UUID groups and `picture` is private. [chat.ts:47](frontend/src/chat.ts#L47) · [chat.ts:140](frontend/src/chat.ts#L140) |
| P3 · Interruption tests | **PARTIAL** | `walk_photo` covers a committed copy with a lost answer, identical replay bodies, reload and one scene. Takeover, refused words storage and replay after editing the copy remain uncovered. [chat_browser.py:2328](frontend/tests/chat_browser.py#L2328) |

The other round‑3 rulings remain **CLOSED** for their reported cases. Replay reads the current copy, the destination loads its own thread, pending copies block automatic recaps, lookup responses check poster and hold, and the copy preserves layout. Picker guards, recap photo provenance, mixed-message pre-save and the ADR‑125 warning assertions remain in place. The redundant pre-save term is gone. [App.vue:2012](frontend/src/App.vue#L2012) · [ChatView.vue:230](frontend/src/ChatView.vue#L230) · [ChatView.vue:295](frontend/src/ChatView.vue#L295) · [ChatView.vue:477](frontend/src/ChatView.vue#L477) · [chat_browser.py:2328](frontend/tests/chat_browser.py#L2328)

### Release defects and smallest fixes

- **P1 · A replacement first recap can pay again.** Trigger `acknowledgement_required` on a small photo. `again()` calls `recap()` and drops `first`. Generate the image in « Pas à pas », then reopen chat. `first()` closes only marked recaps, and `firstChecked()` accepts the replacement immediately. Its fresh key can buy another scene. Preserve `first` on this replacement and run it through the same jobs check before enabling it. Also invalidate `imagelessFor` on thread load so returning to the same poster under the same hold cannot reuse an earlier visit’s answer. [ChatView.vue:146](frontend/src/ChatView.vue#L146) · [ChatView.vue:287](frontend/src/ChatView.vue#L287) · [ChatView.vue:310](frontend/src/ChatView.vue#L310) · [ChatView.vue:454](frontend/src/ChatView.vue#L454)
- **P1 · A restored recap can show the wrong price.** Leave a versionless poster with an untapped recap, change its price in the editor, then navigate directly from another poster’s chat to it. The poster-change watcher calls `load()` without `importForm()`. The successful jobs check enables the restored recap without updating it. The button shows the stored price while generation uses the current document. Refresh the restored card’s title, price and photos from the current poster before setting `imagelessFor`. [ChatView.vue:159](frontend/src/ChatView.vue#L159) · [ChatView.vue:302](frontend/src/ChatView.vue#L302) · [ChatView.vue:477](frontend/src/ChatView.vue#L477)
- **P2 · Whole-thread eviction can erase copy recovery.** Lose the response after the copy commits, then use enough other threads to evict the source. `storeThread` protects only unresolved **paid** cards. The copy’s keys disappear, so repeating the photo workflow can make a second copy. Exclude threads with an unfinished photo card holding a pinned revision and no confirmed copy ID from eviction. [chat.ts:237](frontend/src/chat.ts#L237) · [chat.ts:250](frontend/src/chat.ts#L250)
- **P2 · The adjacent price help is still false.** With drawn text enabled on a versionless copy, « Le titre et le prix restent dessinés ensemble dans l’image » still appears. Keep the first sentence about the next version and omit the second for a versionless poster. [App.vue:2369](frontend/src/App.vue#L2369)

For an **already-succeeded job**, `adapter.follow` schedules a status GET. The success branch refreshes visuals and rereads the saved creation when appropriate. It sends no second scene request. [App.vue:1508](frontend/src/App.vue#L1508) · [App.vue:1578](frontend/src/App.vue#L1578)

### Known and left

- **Copy’s last read after takeover — acceptable for the stated data/payment test**, but it still violates the explicit stop-on-takeover rule. Check the hold after the visuals GET and before installing the copy. [App.vue:1218](frontend/src/App.vue#L1218)
- **Takeover inside `createPoster` — unacceptable.** The former holder can create a poster and schedule logo/contact saves. Pass the hold check through creation and adoption, checking after awaits before writes. [App.vue:1186](frontend/src/App.vue#L1186)
- **Refused copy-words entry — unacceptable.** A paid scene can omit the pinned brand and subtitle. Verify the destination words before enabling generation and preserve recovery through the source card if storage refuses them. [App.vue:1201](frontend/src/App.vue#L1201) · [App.vue:2012](frontend/src/App.vue#L2012)
- **Missing takeover/storage smoke — acceptable as a coverage gap alone.** The supplied passing runs do not exercise those failure paths. This review was static and read-only. [chat_browser.py:2328](frontend/tests/chat_browser.py#L2328)

**Verdict: REJECT.**