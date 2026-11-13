# Phone-first editor — design review round 1 and devil's advocate (2026-11-13)

Subject: designs/poster-editor.md, D-POSTER-EDITOR-005 v1, and its requirements (R-POSTER-EDITOR-007, the amendment to 006). Two fresh subagents, read-only. Claude's decision on each point is in the last column; the result is D-POSTER-EDITOR-005 v2 and ADR-075.

## Devil's advocate — points that change a decision

| # | Their judgment | Point | Decision |
|---|---|---|---|
| 1 | CHANGE | "The poster changes as you type" is false for a default poster: before the first version the draft shows only title and price (accent word and colour, brand, subtitle and style are drawn later by the image model); after a version, title and price are drawn inside the image, so typing shows only "générez une nouvelle version". The review's screenshots came from a smoke that unticks « Laisser l'IA composer le titre » | **Accepted.** During the steps the poster stays the thumbnail with « Voir l'affiche »; the chrome is cut instead. Once a version exists, the real image stays on top (useful for « Boutique », « Réglages », cropping) and collapses to a strip while a text field has the focus. The mockup's live accent colour overstated the product; said to the user |
| 2 | CHANGE | "The mockup is promising" is not his usual "go"; ADR-074 said the default theme and the font are his | **Accepted.** The four choices go to him in one message; the structure is approved under the autonomy grant with this review's fixes |
| 3 | CHANGE | Light by default fails R-006's "the poster is the brightest thing"; warm off-white with ink-black is close to the look he rejected (ADR-047) | **To the user**, with both sides; dark stays the default until he answers |
| 4 | CHANGE | Look and structure in one release, while the live pilot lacks the price fix and the eight fixes are uncommitted in the same files | **Accepted.** Recommend releasing the steps editor, the eight fixes, T-FOREGROUND and T-THEME-COLOR first (his word: commit, push, deploy), then the observed phone session, then the structure, then the look |
| 5 | CHANGE | Switches on options that only affect the next paid version mislead (a switch acts at once) | **Accepted**: switches only for Logo, Nom de la boutique, Contact, Contour, Ombre, Déplacer les éléments; the next-version options stay checkboxes under a heading |
| 6 | KEEP BUT NOTE | Figtree: no performance case against (1.1 MB of Noto Sans preloaded today; 20 kB woff2); a matter of taste | To the user, with the size argument |
| — | — | Bottom navigation: KEEP. Claims that the owner knows Canva or CapCut, and that his phone "looks like" Material 3 Expressive, are hypotheses | Labelled as hypotheses |
| — | — | Found on the way: `main.ts` set the light `theme-color` in dark mode | Fixed (T-THEME-COLOR) |

## Fresh reviewer — verdict: APPROVE WITH FIXES (part 3 needs a v2)

| # | Sev. | Finding | Decision |
|---|---|---|---|
| 1 | P1 | The large view (peek) is the same `.stage` and canvas: the height-based scale would shrink it too; the peek exists only during the steps (`App.vue:300`) | Height rule only when not peeking; the peek also in tabs; `.main-action` hidden inside it |
| 2 | P1 | The sticky stage also holds the head, a 240 px minimum host, the selection and removal text, job state, polish preview, save recovery, issues: up to about 560 of 740 px | Only the poster and one scrolling element row stay sticky; the other blocks move after the stage (a wrapper that is `display: contents` on one column keeps `.stage` as the peek element) |
| 3 | P1 | "First field above 444 px" is unreachable with a 38 % poster | The sticky poster is for tabs only; in steps the chrome is cut (step count in the step row, no lead line on phones, tighter paddings); the criterion applies to the steps |
| 4 | P1 | `.nav` is inside `.app-header`, which has `backdrop-filter`: a fixed bottom nav would be placed in the header | At 720 px and below the header loses its blur and the nav carries its own; one `.nav` element; no `backdrop-filter`, `filter`, `transform` or `will-change` on `.stage` |
| 5 | P1 | `scroll-padding-top` and `scroll-margin-top` both set: the offset counts twice | `scroll-padding-top` only |
| 6 | P2 | Keyboard: `interactive-widget=resizes-content` makes `innerHeight` and sticky follow the keyboard on Chrome (Safari ignores it); pinch-zoom shrinks `visualViewport`; each scale change resizes Konva | The attribute plus the existing resize handler; no `visualViewport` tracking; the poster collapses on text focus; the bottom bar hides while typing; at most one rescale per frame, ignoring changes under 100 px |
| 7 | P2 | Theme: a dark flash before `main.ts` runs; `toggleTheme` hard-codes the light colour; Playwright's default colour scheme is light | Part of the look task, waiting for the user: an inline head script and two `theme-color` metas with `media`; the smoke pins `color_scheme="dark"` |
| 8 | P2 | Light tokens: faint on the well is 4.31:1; the off switch track is 2.1:1 | Faint `#67605A`; the off track outlined in `--muted` (look task) |
| 9 | P2 | `--sticky-top` measured while peeking; `go()` hard-codes 56/200; scope it to the editor | Ignore observer entries while peeking; `go()` uses the offset; the padding only in the editor |
| 10 | P2 | Editor notices at `top: 108px` cover the sticky poster | Above the bottom bar in the editor |
| 11 | P2 | A state dot alone in the versions strip shows state by colour only; « Choisie pour l'export » does not fit under 56 px | The state word stays (small); « Choisie » under the chosen one; « Comparer » kept |
| 12 | P3 | `.stage:not(.peek)` for the sticky rule; no single root for `editing`; missing `store` and `sliders` icons; forced colours for switches; Figtree's U+202F and tabular figures; `touch-action: none` while moving elements; tapping the poster in steps selects without showing « Retirer »; up to three owner photos in the review | All taken into v2 |

Checked and correct by the reviewer: no ancestor with `overflow` blocks sticky; a sticky ancestor does not move the fixed bottom bar; Figtree cannot reach the server renderer (only `build_hash` changes); removing the TTF preloads is harmless (poster fonts are fetched); stored theme values stay valid; switches keep the checkbox role; dialogs stay above a nav below z-index 30.
