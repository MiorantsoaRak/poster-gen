# T-REDESIGN-002 — code review, round 3 (Codex, 2026-11-21)

Reviewed: the worktree `app` after round 2's fixes. Verdict: REQUEST CHANGES (two edge cases left; the third round, so the owner decides).

**REQUEST CHANGES.** Two blockers remain. A second browser traversal can leave a stale photo-discard confirmation active. A delayed 401 can overwrite a conversation after another tab acquires the chat lock.

| Round‑2 point | Ruling | File:line evidence |
|---|---|---|
| 1. Unsent photos and navigation | **PARTIAL** | `App.vue:746–759` distinguishes the current poster from an empty thread and clears the tray before `fresh()`. The ordinary Back → cancel → Back → confirm → Forward sequence is covered at `shop_dashboard_browser.py:1180–1195`. A second traversal while the question is open remains unsafe. |
| 2. Signed-out shop DOM and verification | **CLOSED** | `App.vue:2263` unmounts the shop on `out` and keeps it mounted but hidden during verification. The gate cases are in `shop_dashboard_browser.py:1395–1468`. |
| 3. Recent-poster focus | **CLOSED** | `App.vue:765–767` checks the adopted ID, address and modal state. `shop_dashboard_browser.py:1317` asserts focus on the title. |
| 4. Recent results and count | **CLOSED** | Duplicate, restore and remove share `onRow()`, which calls `madePoster()` before reloading the list. That invalidates `listKnown` immediately. `App.vue:1316–1329,2050`. The failed-refresh case asserts the reduced count at `shop_dashboard_browser.py:1152–1161`. |
| 5. Gate header | **CLOSED** | Both header mode classes depend on `shown` at `App.vue:2244`. |
| 6. Drawer stacking | **CLOSED** | Drawer, scrim and notice have descending stacking order at `style.css:289,294,325`. The overlap hit-test remains at `shop_dashboard_browser.py:1382`. |
| 7. Replacement assertions | **CLOSED** | Switch sizing, header keyboard navigation and rail controls are covered in `shop_dashboard_browser.py:17,99,1039,1295`. The composer uses the visual viewport at `chat_browser.py:1193`. |
| 8. Cleanup | **CLOSED** | Capture listeners have matching removals at `App.vue:2214,2221`. The chat heading remains scoped at `App.vue:2275`. |
| Capability fallback | **CLOSED** | `App.vue:768,1243` replaces the provisional address. `shop_dashboard_browser.py:1216–1223` checks history length and one Back to Accueil. |
| Local 401 sentence and retry | **PARTIAL** | `chat_browser.py:1089–1092` requires the sign-in sentence, excludes the interruption sentence and exercises retry. The persistence path at `ChatView.vue:255–259` lacks current lock ownership. |

**1. A stale confirmation can silently discard photos on a later Back.** From chat C with photos, press Back to B, then Forward to C while the question is open. `onHash()` sees `hash === here()` and only updates `shownAt`, leaving B’s question active. Confirming now sets `discardedFor = B` before checking the address. The next Back to B consumes that permission and clears the tray without asking. Escape likewise applies a delta captured at B from the new position C. Invalidate the photo prompt when its destination entry changes, and check the live entry before arming discard or restoring history. `App.vue:751–757,822–823`. Ordinary replacement, reload, account departure and credits open/close show no independent blocker. Other confirmations have an optional cancel hook, and ordinary confirmation clears the tray before re-entry, so it does not loop. `App.vue:632–644,671–676,695,813–823,837,2461–2464`.

**2. The 401 handler writes after releasing the lock.** Tab A unmounts on the 401 headers and releases its lock before the response body finishes. Tab B can acquire the lock and update the same thread. A’s `heldAtClose` and token still match its own old instance. Even if the pending key changed, A skips only the removal and still writes its entire stale thread. Settle under the current chat lock and verify the stored request before changing either record. `api.ts:165–171`, `ChatView.vue:255–259,464–469,501`.

Read-only source review. No files changed or runtime checks executed.