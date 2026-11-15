**Verdict: REJECT.** Four reproduced defects need fixes.

1. **P1 — The word guard admits invented words.** [reads.py:343](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:343) splits the raw text before normalization, while `known` uses `name_words`. For message `ajoute le sous-titre`, model output `ⓑⓛⓤⓔⓣⓞⓞⓣⓗ` produces a `change` card although “bluetooth” appears nowhere. Decomposed `écouteurs` also wrongly fails against `écouteurs`. Use the same tokenizer on both sides and add both regressions.

2. **P2 — Separating a brand corrupts brackets.** [reads.py:282](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:282) deletes punctuation attached to the brand token. Separating Sony from `(Sony WH-CH720N)` offers `Titre : WH-CH720N)`. Preserve brackets enclosing retained text, or refuse the ambiguous rewrite.

3. **P2 — A retained brand can still disappear during generation.** [reads.py:327](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:327) separates the brand only when the model returns `brand`. With stored brand `Sony`, changing the title to `Sony WH-CH720N noir` returns a scene card carrying both. The scene compiler then deduplicates Sony, contradicting the four-word promise. Check the final title/brand pair before offering the card.

4. **P2 — Carried document titles bypass scene validation.** [reads.py:334](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:334) validates only requested fields. A document title of 61 characters beside an older drawn title, followed by `650 000 Ar`, produces a scene card containing that invalid title. Generation subsequently refuses it. Validate carried values when the computed effect requires drawing them.

No regression found in ADR-095, replay ordering, or the shared ownership/eligibility query. New-poster model inputs and canonical bodies without `visual_id` matched `HEAD`.

Small simplification: at line 351, `image | document | image` equals `document | image`. The four failures above lack regression coverage.

Verified: **123 tests without store writes passed**, plus isolated reproductions. Full suites, devices, production and paid calls were not rerun; the reported 969 passes remain independently unverified.