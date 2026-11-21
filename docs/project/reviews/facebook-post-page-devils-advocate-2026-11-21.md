# Devil's advocate — A publish page: one Facebook post with several posters (design v1)

A subagent asked to challenge the design, the settled decisions included, and to bring back only what would change a decision. 2026-11-21. Its points, and what the lead decided for v2.

| # | Its point | Decision for v2 |
| --- | --- | --- |
| 1 | Two records for one act: the single poster's publication beside the post costs mirror rules, two lists, two restore steps, two texts, for ever once rows exist. Nothing of the feature is on a remote: use one model; « Publier sur ma Page » stays as a quick button that makes a post of one. | **Taken.** One model; the final panel's button adds the poster to the draft and opens the page; `facebook_publish.py`, its routes and the sheet go; migration 0019 converts and drops 0018's table. The owner's to overturn: his default so far was that the one-poster path stays as built. |
| 2 | The saved draft against paged candidates: a draft poster on page 2 is taken out or cannot be sent. | **Taken:** `candidates?ids=`. |
| 3 | No way to stop the uploads: up to about 120 s an image with nothing the owner can do, and a wrong price still goes out. | **Taken:** « Arrêter l’envoi », one flag read with the other checks. |
| 4 | The draft is cleared at the 202: a refused image means choosing and typing again. | **Taken another way:** the draft is kept until the post is published. « Reprendre » on a failed post's line is not built. |
| 5 | The photo ids change the reasoning on an unknown outcome, not yet the answer: a read-back proves nothing when it finds nothing. A bigger lever: create the post unpublished, then set `is_published=true` on its known id; unproven. | **Kept as designed;** the lever is listed « to weigh » with its proof. |
| 6 | The proof of the largest number comes too late (at the first real post): the code of the refusal and the maximum are guesses in the code until then. | **Taken:** the proofs come before task 2. |
| 7 | Deleting leftover photos: drop it. They are not shown; two paths already leave ones that cannot be deleted; the deletions break the shutdown's bound (`stop_grace_period: 5m`). Check `temporary=true`. | **Taken:** nothing is deleted; `temporary=true` is a proof. |

Found sound as designed: a task per post and not the job system (`poster_jobs.creation_id` is NOT NULL; `claim` gives render and cutout one shared slot); uploads one by one and not a batch (private files need `source`, not `url`; N × 10 MB in one request in a 1 GB container; a lost batch answer leaves no photo ids); the page's shape on a phone. Checked: `restore.sh` runs `after-restore` before the service starts, and the Facebook recovery runs only when the API starts, so the posts' start-up rule must sit there, never in the shared runtime start.
