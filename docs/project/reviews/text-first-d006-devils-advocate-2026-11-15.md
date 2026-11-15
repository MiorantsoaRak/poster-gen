# Devil's advocate: D-TEXT-FIRST-006 (draft v1) — 2026-11-15

**Scope:** the section "Settings of the next image as rows of the field table", its requirements block, against the code at commit "T-CHAT-SCENE-FIELD…". Read only. No paid call, no server, no browser. One check was run in memory (point 2). Everything else is from reading; each point says so.

**Only points that would change a decision are listed.**

## Verdict

- Build A and B only if a baseline test shows that today's chat does them badly. That test was not made.
- Do not build C as designed. Two defects, found by reading, are not in its failure table. A smaller shape exists.
- Do not build D as a row before one paid image through today's path.
- E as a sentence is right. Cut task 7 from this design.
- Move the paid reading test to right after task 1, and make it a regression test of the old messages first.

## 1. The design's premise is out of date: the chat already takes most of these messages (changes A, B, D)

**What is wrong.** The problem statement says the chat "cannot" do the five things. That was true when the audit was written. ADR-102 was built after it. Since then, a message that changes no word goes whole to the scene adjustment, from the image shown.

**Evidence.**
- `reads.py:321-333` (`adjust`): no word asked and a scene signal → a `refine` card with the owner's message.
- `chat-change-eval-2026-11-15.md`, scene test: « mets le titre en dégradé violet » → version 9, brand and title in a violet gradient, words exact. This is A, wider than five colours, done today.
- Same report, version 10: adjustments add up and are said again on each refinement. ADR-101 carries them into a later word change.
- The design has no line that says what « mets Buds en rouge », « écris JBL en lettres simples » or « passe en style sombre » give today.

**What the rows change for the owner.** Today these are a refinement: the composition and the drawn features stay. As rows they become `scene`: a whole new image from the plan (design, "Recommendation per item"). The owner pays the same and keeps less.

**A row can make a request worse than today.** « mets Sony en rouge » on a poster with the brand apart: Sony is not in the title, so the accent row answers `refused`, « « Sony » n’est pas dans le titre. » (design, row `accent_word`). Today the same message is a scene adjustment, and version 9 shows the brand takes a colour.

**A colour outside the five is paid wrong.** « mets Buds en vert »: `accent_colour` is a `Literal` of five, so it stays null. `accent_word` is set. The card says « Mot en couleur : Buds » with no colour line. The request carries the version's stored colour (default `#1E6FE0`, `App.vue:38`). The owner pays for a blue word. Not caught by `carries`: the request matches the card.

**Smaller alternative.** Before task 1, run about eight setting messages through today's code and make three images (a word in a colour, the brand in plain letters, a darker style). Cost: about USD 0.11. Then:
- A: if the adjustment works, no row. If a row is still wanted, the card always prints the word and its colour, and a colour outside the five falls to the scene adjustment, not to a refusal.
- B: the best case for a row. The stored headline says "written as on the product" on every later redraw (`plans.py:382-386`), and the prompt says the headline wins over a kept adjustment (`plans.py:516-518`). An adjustment may not hold. Measure it.

## 2. C: a free identity change breaks every later request on that version (P1, checked in memory)

**What is wrong.** The identity rule has two `free` lines for "off". After a free « Logo de la boutique : retiré », `include.logo` is false. The version's plan still has a `logo` region. From then on that version can take no scene adjustment and no word change.

**Evidence.**
- `validate_plan` refuses a plan whose regions are not exactly the included fields (`plans.py:188-189`). The design knows this (finding 1) but applies it only to the card that changes the identity (`revise` step 10, "identity changed").
- Refinement: `request_refinement` builds the context from the document (`visuals.py:300`) and compiles the version's plan with it (`:310`) → `invalid_plan`.
- Next word change: `revise` → `acceptPlan(kept)` → `savePlan` → `/revisions` → `insert_plan` → `validate_plan` (`App.vue:1404-1405`, `visuals.py:161-163`) → `invalid_plan`.
- Run in memory, no file changed: `fixed_plan` with a corner logo, validated against the same context without the logo → `unselected_or_missing_overlay`. The reverse too.
- `invalid_plan` is final (`chat.ts:134`). `conclude` retires the card and `again` offers the same card (`ChatView.vue:352`, `:364`). It is refused again. The sentence is « Cette composition n’est pas valable… Annulez le dernier déplacement et réessayez. » (`api.py:68`). It means nothing in the chat.
- No stale flag: the logo is hidden, so `staleLogo` is false (`composition.ts:21-22`). « Remettre comme sur l’image » is not offered.

**The natural sequence:** logo on (paid) → « enlève le logo » (free) → « fond plus sombre » → refused for good.

## 3. C: "contact on" puts an unplaced contact on every older version, with no warning (P1, from reading)

**What is wrong.** `include.contact` belongs to the poster, not to a version. The chat invites the owner to go back to older versions.

**Evidence.**
- `setIdentity` creates the contact layer at `x = 64`, `y = height - 150`, white (`document.ts:72-76`). Layers go to the plan's regions for the first version only (`service.py:153-171`; the design's own finding 2).
- `chooseVisual`: `layer.visible = document.include[role] && visual.headline?.[role] === undefined` (`App.vue:1322-1326`). On an older version without a drawn contact, the layer becomes visible, where `setIdentity` left it.
- `staleSignature` is false then (the layer is visible, `App.vue:740`). The export is not blocked. The design's stale line does not show. The design's edge case covers the logo only.
- The chat has no canvas. The first place the owner can see it is the final preview. A white line near the drawn price, on « Studio clair », may not be seen at all.

This is the design's own reason for leaving the shop name in « Pas à pas ». It applies to the contact as soon as a second version exists.

## 4. C: the smaller shape (changes the decision on tasks 5 and 6)

**Claim.** C is not a row. Its check does not fit `Row.check(value, message, drawn)`. It needs `shown` / `carried`, a snapshot, a second effect function, `freshPlan`, `staleIdentity`, a new button and a six-line rule. Two of those lines are wrong (point 2). `freshPlan` has never run (design, "Not established").

**Alternative.** Put the shop's identity on the first version, where the editor's path already works:
- `createPoster` already sends `brand_selection: include`, places the logo at the top right and makes the contact compact (`App.vue:880-887`).
- The first version places every layer in its region and hides what the image drew (`service.py:153-171`).
- The chat's `start` only has to set `include` before `createPoster`. One remembered choice per device, shown as one line on the recap card.
- On an existing poster: one sentence to « Pas à pas », « Boutique ».

A shop wants its logo on every poster, not on one poster by message. This shape needs no new plan path, no identity rule and no way back.

**If C is kept as designed, the minimum:** no `free` effect at all (every identity change that differs from the version's plan is `scene`); the contact layer is placed by the fresh plan or the older versions are refused; a stub smoke for "identity card, then scene adjustment, then word change, then an older version".

**Not verified:** whether the review dialog shows the logo over the image. If it shows the raw image, a logo corner that the image model did not keep free is first seen at the final preview.

## 5. D: the style row is the most dangerous misread, and it drops what the user asked to keep

**What is wrong, reading.** The values are « clair », « couleur », « sombre ». These are ordinary words of scene requests. « fond plus sombre » and « fond plus clair » are measured today as refinements. « couleur » is also the word of row A. The stub's own pattern shows the overlap (`reads.py:104`, `_STYLES`). The row has no check and is "always `scene`".

**What a wrong read costs.** A card for a whole new image with another plan, no model image and none of the kept adjustments. Settings count as "asked", so the scene adjustment the owner wanted is dropped (design, "Order in `_change`"). No wording gets the owner back to the adjustment if the reader repeats itself.

**What is wrong, dropping.** ADR-101 is a user decision: carry the adjustments into the new image. The user's own showcase poster (features with icons, the Sony mark) is made of adjustments. A style card removes them and says so in one line. The owner will read « Les ajustements de scène demandés avant ne sont pas repris » as jargon. He did not ask for "adjustments". He asked for icons.

**Keeping them is not right either.** The prompt says a kept adjustment wins over the art direction and the palette (`plans.py:512-515`). An old « fond bleu nuit » would beat the new style. So neither choice is good inside a whole new image.

**Smaller alternative.** A style request stays a scene adjustment in the owner's words, as today. It starts from the image shown, keeps the features, and "the later one wins" is already written and tested (version 10). Test one image first (« passe en luxe sombre » on a light version). Build the row only if that image fails. If it is built: the row is filled only when the message has the word « style » or a style's full name (a check in the row, not a prompt rule), and the card names what is lost in the owner's words (« les icônes et le fond demandés avant »).

**Also, from reading:** a style card with « Couleurs du produit » and a word colour in the same message is refused at the tap by `carries`, after the read was paid. `sceneAccent` takes the photo's colour (`App.vue:55`), not the card's.

## 6. The reader: nothing measured, and the old measurements no longer hold

**What is wrong.** With `rows: 2` every read on a poster uses the new schema: 14 outputs against 7. The 59 messages measured today (26 + 15 + 18) were read with the old one. The design's paid test has 25 new messages on the new rows only. It does not read the old ones again.

**The two misreads that matter most are old messages.**
- « Use sony logo » (the user's own report) → `logo: true` → « Logo de la boutique : en haut à droite ». The design names this and answers "counted in the paid test".
- « fond plus sombre » → `style: sombre` (point 5).

**Delay.** The median is already 3.1 s on the last run; the design's threshold is 3 s (eval report, "To watch"). More fields are more output.

**Alternative, and order.** The reading test needs the backend only. Run it right after task 1, before any frontend:
1. The 59 old messages again with the new schema. Compare card by card. Any old message that fills a new row is a failure.
2. Then the new messages, with at least ten that must fill no new row.
3. Report the median delay.
Cost: about USD 0.25. It decides whether rows are viable before the adapter is written.

**For the images:** one image per setting is not a result. The brand mark came out twice in three runs. Use three for the logo corner. After each setting image, ask one scene adjustment and one word change on the new version. Every defect of the day was "the next change lost it".

## 7. `rows` and `since`: use the precedent instead

**What is wrong.** `Row.since`, a filtered schema, a filtered sentence and tests for both keep two readers alive for an old tab. D-005 met the same case and chose one path: 409 `reload_required`, nothing paid ("one user, no read yet", D-005, "What changed from v1").

**Alternative.** The body sends `rows: 2`. Absent → `reload_required`, looked up after the key as today (`reads.py:505-507`). Cut `Row.since` and the dual schema. The requirement "never pays for a change it cannot carry out" is met.

## 8. Tasks: what to cut, and the order

| Task | Verdict |
|---|---|
| New task 0 | Baseline: today's code on setting messages, three images. Needs the user's word. |
| SET-001 | Keep `brand_text` and the `format` sentence. `accent_*` only if the baseline says so. No `since`. |
| SET-004 (paid reads) | Move to right after SET-001. Old messages first. |
| SET-002 | After the reading test. |
| SET-003 (style) | Cut unless the baseline image fails. |
| SET-005, SET-006 (identity) | Cut. Replace by identity at the recap (one small task) and one sentence on an existing poster. |
| SET-007 (format from the chat) | Remove from this design. One line under "What this does not do" is enough. Its own open points say it is not designed. |

## Tried to break, and could not

- **E as a sentence.** Right call. The row also stops a format request from becoming a paid scene adjustment at the same size. Its one cost: a format word in a message hides the other fields; the owner writes again.
- **`carries`.** Worth keeping for A and B. `headlineBody()` does drop silently (`App.vue:307`), and the guard is one pure function before a paid request. It does not cover the colour case of point 1 or the style.
- **`freshPlan` by reading.** `prepareScene` takes the editor's `direction`, not the version's, but the prompt reads `plan.scene.setting` and the palette, which are overwritten from the kept plan (`plans.py:509`). `revise_plan` then validates against the new context. It looks sound. It has never run.
- **ADR-097 and ADR-098.** The settings add one unpaid `/plans` request before the paid one; a lost answer there leaves no kept request. No way found for the chat to guess a paid outcome.
- **The brand rule of `brand_text`.** The brand is set apart before the check, so it is never inside the title when `brand_text` is asked.
- **Hash of kept requests.** `exclude_if` on the new body field keeps old hashes, as `visual_id` does (`reads.py:77`).

## Limits of this report

Nothing was run except the plan check of point 2. Points 1 and 5 say what the reader may do; only a paid test gives a rate. Point 3 is read from `chooseVisual` and `setIdentity`; a stub browser run would confirm it at no cost.
