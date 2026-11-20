# App redesign — after report (2026-11-21)

**What:** both interfaces rebuilt after the approved mockup [mockups/doka-console/](../mockups/doka-console/README.md)
(ADR-123; [requirements](../requirements/app-redesign.md) and [design](../designs/app-redesign.md) v2).
**Where:** branch `redesign` (worktree `../affiche-ia-worktrees/app`), which holds T-REDESIGN-001 … 006 and the merged
branches `redesign-chat` and `redesign-console`. **Not on `main`, not pushed, not deployed.**

## Proof (Linux, local stub build, branch `redesign` after both merges, run once by the lead)

| Check | Result |
| --- | --- |
| Vitest | 312 passed |
| The build (`vue-tsc`, app and operator page) | passed |
| `browser_smoke.py`, `chat_browser.py`, `shop_dashboard_browser.py`, `share_browser.py`, `terms_browser.py`, `editor_refinements_browser.py`, `admin_browser.py` | all passed |
| Backend `pytest -q` | 1533 passed, 3 deselected (no backend file changed) |
| `design_capture.py redesign` | 102 captures, 51 snapshots in `outputs/design-capture/redesign/` of that worktree |

Reviews: every task had a Codex code review ([001 r1](t-redesign-001-code-r1.md), [r2](t-redesign-001-code-r2.md);
[002 r1](t-redesign-002-code-r1.md), [r2](t-redesign-002-code-r2.md), [r3](t-redesign-002-code-r3.md);
[003](t-redesign-003-code-r1.md); [004](t-redesign-004-code-r1.md); [005](t-redesign-005-code-r1.md);
[006](t-redesign-006-code-r1.md)). Every finding was fixed with a test. The fixes of the last round of each task were
checked by its smokes, not reviewed again; for T-REDESIGN-002 that was the owner's choice after the third round.

## Screen by screen, against the mockup

| Screen | Matches | Differs, and why |
| --- | --- | --- |
| Shell, wide | Framed window, sidebar with logo, « Nouvelle affiche », sections with counts, « Affiches récentes », credits, account, sign-out; rail; top bar with credits pill and theme | The frame scrolls with the page (the mockup's window scrolls inside: the app's dialogs and phone action bars are fixed to the screen). The step editor is flush with the window and always on the rail (a Story poster must fit 1366 × 768) |
| Shell, phone | Drawer, top bar, bottom bar with yellow centre « Nouvelle affiche » | Theme switch in the drawer; in the chat the top bar has menu, switch, plus and credits, no bottom bar. The bar also shows on the « Pas à pas » intake form before a poster exists |
| Chat | Centred D and « Quelle affiche créons-nous ? » over the greeting, one composer with « Images », the styles and send inside; plain assistant messages; poster panel as a card | No suggestion chips; the cost sentence stays under the button (R-BALANCE-001); the composer has a visible 3:1 edge; the owner's photos stay in the bubble |
| Accueil, Mes affiches | Cards as a surface with a hairline, state badges | The sidebar's « Affiches récentes » still shows the state as grey text |
| Final panel, review | Yellow main action, opaque cards | Unchanged layout; share-first ranking kept |
| Console | Sidebar, rail, drawer, the shops table with small headers, the filter, badges, Overview with four figures, « Needs you », payments, service | « Needs you » is a full-width block under the figures (the mockup has it top right). No « Conditions pending », no « Spend today ». Rows are about 75 px (a 44 px link and the name under it) |

## For the owner

1. **Look at it before anything ships.** From the worktree: `cd ../affiche-ia-worktrees/app/frontend && corepack npm@10 run build`, then from its `backend/`: `uv run python ../frontend/tests/design_capture.py look` and open `outputs/design-capture/look/sheets/`. Or run the app there with the stub.
2. **Real-phone checks, still open:** the yellow button in daylight; the dark cards on a cheap screen; the drawer and the phone top bar with a larger text size; the composer with the keyboard open.
3. **Decisions I took that you may overturn:** « Needs you » placement; the cost sentence kept (the mockup's shorter line is possible); « Images » as the attach button's word; « Payments » in place of « Money »; the theme switch in the phone drawer; Back with the drawer open acts on the page.
4. **Release order.** `main` still holds the interface polish only. The redesign can be merged into `main` as a whole, or cut by task (tokens alone, then the shell and the chat, then the console). Both are your word, as is the deploy.
5. **Known limits:** the console's colours need Chrome 123, Firefox 120 or Safari 17.5 or newer; French drafts to read: « Quelle affiche créons-nous ? », « Affiches récentes », « Images », « Ouvrir / Fermer / Réduire / Agrandir le menu ».

## Not done

`DESIGN.md` is being rewritten from the code on `redesign` (in progress at the time of this report). No real phone, no
screen reader, no forced-colours run.
