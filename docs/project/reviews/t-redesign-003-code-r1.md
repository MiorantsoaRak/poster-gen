# T-REDESIGN-003 — code review (Codex, 2026-11-21)

Verdict: REQUEST CHANGES (small).

**Verdict — request changes.** The diff preserves the charging decisions, French card copy, button names and card order. Two gaps remain before sign-off: the phone smoke can pass with the composer off the physical screen, and « Réessayer » / « Reprendre » omit their visible one-charge assurance from their accessible descriptions.

**1. Balance and card predicates.** `cardButton`, `buttonOf`, `costs`, `free`, `limitOf`, `warns`, `asksPhoto`, the disabled conditions and the click handlers are unchanged. The DOM still puts facts and status before the warning and small-photo acknowledgement, then actions, cost and correction hint. Pending review still offers « Vérifier »; only the approved, selected version offers « Télécharger ou partager ». Cancel, restore-text, photo, fix, resend and steps retain their conditions. [ChatView.vue]

| Card | Visible and accessible behavior |
|---|---|
| Recap or paid change | `button === 'create' && !free(item)` renders `state.credit.text` with `id="cout-<item.id>"`. The button references that exact ID, after the warning ID when present. Unknown balance, pending credits and low-balance wording come through intact. |
| Free change | No cost line or cost reference. This preserves the approved chat behavior. The broader R-BALANCE-001 wording that a free button “says so” is an existing discrepancy. |
| Paid retry/resume | `ONCE` is visible but has no ID. The button references only the warning, if present. Link `ONCE` after the optional warning and update the existing warning-only resume assertion. Replaying the stored request incurs no additional charge. |
| Stop, terms or version limit | Credit stop shows its status sentence for an untapped paid card. Terms offers « Lire les conditions »; exhausted versions suppress creation and retain the limit sentence. None references an absent cost ID. |

**2. Welcome.** Only the lock-owning chat gets `.welcome`, when there is neither a displayed visual nor an owner item. Sending text or photos appends the owner item before the reply. Restoration loads saved items, and `shown` falls back to the first visual. Only the greeting switches branches; the item loop and poster render independently. One real edge case is a recap imported from « Pas à pas » before any owner message. It appears **alongside** the welcome, and on wide screens the populated thread gets the centered layout. A stored assistant-only thread behaves the same way. [ChatView.vue]

**3. Phone layout.** `measure()` uses visual-viewport height, subtracts the chat’s document-top position, body bottom padding and 12 px. The phone grid gives remaining height to the scrolling thread and the last row to the composer. At 360 px, attach and send reserve 44 px each; `minmax(0, 1fr)` lets the composer shrink, and the style strip takes the remainder with `min-width: 0` and horizontal scrolling. Coarse-pointer typing hides the strip. The keyboard smoke resizes the whole viewport to 420 px; it does not exercise keyboard-only visual-viewport shrinkage or panning. [ChatView.vue] · [style.css]

**4. Contrast and structural rules.** Owner photo labels inherit the bubble’s foreground in both themes. Cost and hint use 13 px `--muted`; the composer uses `--control` at rest and `--text` on focus. The smoke checks both themes, placeholder contrast, composer edges and send marks. The diff introduces no fixed-position containing block, blur or filter, no page wrapper or sticky-ancestor overflow, and no change to drawer/dialog exposure. The yellow D is decorative, and « Images » is contained in « Ajouter des images ». [style.css]

**5. What green tests miss.** The three replacements are justified: the placeholder selector follows the textarea, the fresh-thread count expects zero bubbles and one welcome, and the paid-change description expects warning then cost. The added free-change assertion checks for a nonempty description. But `\d+` accepts a wrong balance; compare with the fixture’s available amount. The tool-row assertion checks height and send alignment even if the strip disappears or its last style is unreachable. Scroll the strip, reach its last pill, and verify attach/send stay put. [chat_browser.py]

**6. Catch the 447 × 919 regression.** `scrollWidth <= innerWidth` can compare two inflated widths. In the unzoomed 360 × 740 fixture, assert against the configured width in both empty and recap states, then check the composer against the visible viewport independently. [chat_browser.py]

```python
assert page.evaluate("document.documentElement.scrollWidth") <= 361
assert page.locator(".composer").evaluate(smoke.REACH_JS)["inside"]
```

Read-only source review. The reported Vitest, build and smoke results are the implementer’s; physical-keyboard behavior remains unverified.