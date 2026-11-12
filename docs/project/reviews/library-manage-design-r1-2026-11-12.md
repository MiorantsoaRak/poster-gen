# Design review round 1 and devil's advocate — D-CREATION-LIBRARY-003/004

**Date:** 2026-11-12. **Design reviewed:** draft v1 of the two sections in [designs/creation-library.md](../designs/creation-library.md). **Result:** v2, then v2.1 after round 2; not approved by the user yet.

Both reviewers worked read-only and checked the design against the code.

## Fresh reviewer: findings and what v2 does

| # | Finding | v2 |
|---|---|---|
| 1 | "À vérifier" read only the scene chosen in the document; later versions wait outside it, so a poster with a waiting version showed "Brouillon" or "Approuvée". | State rule rewritten: any `pending_review` visual made for the creation; `to_review` first. |
| 2 | "Dupliquer" from a stale row copied an old revision silently (`copy_creation` never compares revisions). | A `new_campaign` copy is refused with `revision_conflict` when the revision is not current. |
| 3 | The editor keeps the key of a failed call; "retirer, remettre, retirer" or "rename B, C, B" would replay a stored answer without acting. | New key on every attempt for abandon, restore, rename, remove; only the copy keeps its key. List reloaded after every action. |
| 4 | The default style name ("Style n") can collide once removed styles are hidden. | Creation never fails on its name; free numbered name when the look is stored. |
| 5 | Case-insensitive uniqueness cannot be done in SQLite for accented names. | Compared in Python with `casefold` inside the write transaction. Supplied style names are checked in the editor only. |
| 6 | The design named a refusal code (`invalid_name`) that the code does not produce. | Uses the real `validation_error`, field `body.name`. |
| 7 | "`look_removed` before any paid call" was false: a paid plan can come first. | The refusal is dropped (see the devil's advocate, point 1). |
| 8 | Minor: suffix may exceed 40 characters; `image_job_running` does not cover plan or style jobs; a removed confirmed poster has no download entry until restored. | All three stated in v2. |

Confirmed sound: none of the routes can spend money or touch the ledger; the facts about paging, statuses, tables, the limit of 24 and migration numbering match the code; ownership checks and `BEGIN IMMEDIATE` cover the check-then-write.

## Devil's advocate: points that change a decision

1. **Removed-style fallback.** v1 dropped the style on the next version, so a price change on an old poster (a paid new scene) lost its typography, palette, surface, lighting and camera. v2: the poster keeps its removed style until the operator changes the ambiance or picks another one; the server accepts a removed `look_id`.
2. **"Dupliquer" on a stale row.** Same as the reviewer's finding 2; fixed the same way.
3. **Two name-clash rules.** v1 had a refusal at request time and a suffix at job end. v2 keeps one rule: the suffix when the look is stored; the refusal remains for rename only.
4. **"Confirmée" wins over everything.** A confirmed poster edited afterwards still says "Confirmée" while its file holds the old content. The design follows the requirement literally; left as a question for the user.

## Round 2 (fresh reviewer, on v2): four changes, all taken in v2.1

1. The waiting state missed a copy whose document names a version still waiting that its source made. Rule extended: also the visual named by the document. Versions made in a sibling copy do not count for the source's row; stated.
2. Two error rows still said that a retry reuses its key, against the new rule. Corrected: only "Dupliquer" keeps its key.
3. A retried rename would have been refused by its own name. The look being renamed is left out of the uniqueness check.
4. The kept removed style could leak into the next poster of the same session (the editor does not reset its style state between posters). v2.1 holds it in a state bound to the open poster, cleared on open and leave, never in the picker or the remembered style, and names the three readers.

Checked and sound in round 2: the stale-copy refusal breaks no caller or test; abandon and restore replays; the numbered name is chosen inside the write transaction; round-1 findings 2, 4, 5, 6, 7 and 8 closed; no acceptance criterion lost. No round 3 was run on v2.1.

Tried and not broken (devil's advocate): reusing `abandoned` with a `restore` route; computing the state at read time; refusing to open a removed poster; soft removal with `removed_at` (deleting the row would break refinements of old versions); uniqueness in code only; no revision on a rename; the overall size, once the two dropped branches are gone.
