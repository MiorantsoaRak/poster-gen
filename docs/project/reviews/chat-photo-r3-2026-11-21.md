# Review r3 — D-TEXT-FIRST-007 v3 and its code; the features warning by words (ADR-125)

Reviewer: Codex, read-only, 2026-11-21. Verdict: REJECT (two P1). Third and last round: v4 answers its findings and has not been reviewed again; the owner decides.

**Two P1 defects remain.** A restored first-image card can still charge for an image that already exists. A long thread can also send a paid request after its card and replay key have been trimmed from storage.

### Round‑2 rulings

| Finding | Ruling | Evidence and smallest remaining fix |
|---|---|---|
| P1 · Stale empty visuals list | **PARTIAL** | The jobs check protects a **new** offer. Restore an untapped `first` card, let `/visuals` return empty and `/jobs` return a just-succeeded scene. `imageless()` exits because the card exists, `first()` leaves it open because the local list is empty, and the paid button still works. Validate restored `first` cards before enabling them. Close the card on a succeeded image job and refresh visuals. Keep it disabled while the read is unknown. [ChatView.vue:280](frontend/src/ChatView.vue#L280) · [App.vue:1260](frontend/src/App.vue#L1260) |
| P1 · PUT after takeover | **PARTIAL** | The copy’s visibility PUT is gone. The old tab can still finish adoption after losing the hold during the visuals GET. On the released new-poster path, takeover during the input POST still permits `/creations` and subsequent logo/contact autosaves. Pass a **hold-only** check through chat-initiated `createPoster`, `openCreation` and `adopt`, and check it after waits before writes or installing the document. [App.vue:1185](frontend/src/App.vue#L1185) · [App.vue:1219](frontend/src/App.vue#L1219) |
| P1 · Replay adopts the old answer | **CLOSED** | `remake` opens the returned ID through a fresh creation GET. The replayed document is never installed or queued for a visibility save. [App.vue:2012](frontend/src/App.vue#L2012) · [App.vue:1283](frontend/src/App.vue#L1283) |
| P2 · Automatic recap cancels the copy | **CLOSED** | A pending photo card blocks `firstImage`; adding the first recap no longer supersedes an open-copy action. Cancellation triggers another lookup. [ChatView.vue:280](frontend/src/ChatView.vue#L280) · [ChatView.vue:398](frontend/src/ChatView.vue#L398) |
| P2 · Previous lookup suppresses the next poster | **CLOSED** | The lookup checks poster and hold across the wait. A failed read retries after ten seconds. [ChatView.vue:282](frontend/src/ChatView.vue#L282) |
| P2 · Storage refusal and credit-gated recovery | **PARTIAL** | `made` retains the ID after an observed success, and a pinned revision bypasses the credit stop. But lose the response **after commit**, then refuse storage on retry: `owned()` still displays « la copie n’a pas été faite ». Use « La tentative est interrompue. Réessayez pour retrouver ou terminer la copie. » [ChatView.vue:258](frontend/src/ChatView.vue#L258) · [chat.ts:293](frontend/src/chat.ts#L293) |
| P2 · Tray crosses posters during copy | **CLOSED** | Both the picker button and its file-change handler check `copying`. [ChatView.vue:179](frontend/src/ChatView.vue#L179) · [ChatView.vue:672](frontend/src/ChatView.vue#L672) |
| P2 · Browser assertions contradict ADR‑125 | **CLOSED** | The ordinary adjustment and its restored card expect no warning. A re-offered features request expects the warning. The editor covers both cases. [chat_browser.py:646](frontend/tests/chat_browser.py#L646) · [chat_browser.py:945](frontend/tests/chat_browser.py#L945) · [editor_refinements_browser.py:151](frontend/tests/editor_refinements_browser.py#L151) |
| P3 · Malformed stored copy ID / exported predicate | **PARTIAL** | Display and navigation share `copyMade`, and `picture` is private. The regex still accepts 36 hyphens. Such a card offers « Ouvrir la copie » and suppresses retry. Require the UUID’s `8-4-4-4-12` hexadecimal groups. [chat.ts:47](frontend/src/chat.ts#L47) |
| P3 · Mixed-message pre-save | **CLOSED** | An existing-poster message with images skips `savedFirst()` and goes directly to the free offer. [ChatView.vue:229](frontend/src/ChatView.vue#L229) |

### Remaining round‑1 rulings

| Finding | Ruling | Evidence |
|---|---|---|
| P1‑2 · Destination thread overwritten or recap lost | **CLOSED** for the reported copy transition. | `made` records the link on the source. The destination loads its own thread, and an open recap blocks automatic replacement. [ChatView.vue:268](frontend/src/ChatView.vue#L268) · [ChatView.vue:461](frontend/src/ChatView.vue#L461) |
| P1‑3 · Earlier lock holder keeps acting | **PARTIAL** | Planning now checks ownership. Adoption and the middle of `createPoster` still have the gaps above. [App.vue:1952](frontend/src/App.vue#L1952) |
| P2‑5 · Retry combines different source revisions | **PARTIAL** | The card pins the words and revision together. If storage refuses the copy’s words entry, `keepWords` swallows the failure, adoption resets the headline for the new input, and the first paid scene can omit the pinned brand or subtitle. Verify the words entry before offering generation, or supply the pinned words directly during that opening and retain recovery on the source card. [App.vue:1201](frontend/src/App.vue#L1201) · [App.vue:1225](frontend/src/App.vue#L1225) · [App.vue:2012](frontend/src/App.vue#L2012) |
| P2‑6 · Same-format copy damages layout | **CLOSED** for layout preservation. | The client leaves the server’s copied layout intact. The separate editor wording issue is below. [App.vue:2015](frontend/src/App.vue#L2015) |
| P2‑8 · Wrong recap pictures or tray | **CLOSED** for picture provenance and tray isolation. | Existing posters render input photos and use the editor’s style reference. Copying blocks attachments. [ChatView.vue:42](frontend/src/ChatView.vue#L42) · [ChatView.vue:561](frontend/src/ChatView.vue#L561) |
| P3 · Interruption tests | **PARTIAL** | `walk_photo` exercises a committed copy with a lost response, identical retry bodies, reload and one scene. It does not exercise takeover during adoption, storage refusal after commit, or replay after editing the copy. [chat_browser.py:2328](frontend/tests/chat_browser.py#L2328) |

### New defects

- **P1 · Strict send can succeed without storing the paid card.** Leave the first recap open on a versionless poster and send 50 text-only corrections. Each adds two history items and leaves the recap actionable. Tap that recap: `save()` verifies the last 100 items, which now exclude the recap. `keepRequest` accepts that success and `/scenes` leaves without its stored card, body or replay key. The same trimming can lose a free copy’s recovery keys. Preserve the actionable card inside the cap and verify that the serialized thread contains the exact card and request before sending. [ChatView.vue:111](frontend/src/ChatView.vue#L111) · [ChatView.vue:237](frontend/src/ChatView.vue#L237) · [chat.ts:136](frontend/src/chat.ts#L136) · [chat.ts:212](frontend/src/chat.ts#L212)
- **P2 · A versionless copy says its title or price is already drawn.** Copy a poster whose scene drew those fields, then open « Pas à pas » before generating. The copied layers are hidden, so the editor says « Le titre est dessiné dans l’image » or « Le prix est dessiné dans l’image » while the copy has no image. Keep the hidden-layer detection and give the versionless case its own sentence, such as « Cette affiche n’a pas encore d’image. » [App.vue:1050](frontend/src/App.vue#L1050) · [App.vue:2364](frontend/src/App.vue#L2364) · [App.vue:2368](frontend/src/App.vue#L2368)

**Removable:** the `state.creation &&` term in the pre-save exception. `versions` is already empty without a creation, so `!tray.value.length` suffices inside that branch. [ChatView.vue:229](frontend/src/ChatView.vue#L229)

Read-only review. The supplied checks cover type checking, Vitest and the editor smoke. The chat browser smoke remains unverified.

**Verdict: REJECT.**