# Devil's advocate — Publish a poster on the shop's Facebook Page (design v1, ADR-127)

Subagent (Opus), read-only, 2026-11-21. Its points, and what is done with each.

| Point | Taken? |
| --- | --- |
| 1. Stage 1 may need the same Business Verification as stage 2: the review of 2026-11-15 said that going Live with a business-login app "appears to need Advanced Access to `public_profile`". And « Partager » as the Page has never been tried on a real phone: if it works, the API adds only the desktop and a link | Yes, first: two free proofs before any more design. Seen the same day in the Meta app (read only): its « Publier » page asks for a privacy policy address and lists the use case; it names no verification. Not proved until the app is actually published |
| 2. The look-up of an unknown publication can block a shop for good and can lead to a double post | Yes: no look-up. The owner opens his Page and says « Elle est sur ma Page » or « Elle n’y est pas » |
| 3. `cryptography` and a key protect little (the backups and the key are on the same box); Meta's « Require App Secret » with `appsecret_proof` (stdlib `hmac`) makes a copied token useless, with no dependency and no key to lose | Yes, if the proof shows it works for a Page's token. The Meta app has the switch (« Clé requise », seen, not changed) |
| 4. The design's "mutations" cannot make their calls outside a transaction through `store.mutate` | Yes: no Idempotency-Key on the two connection routes (the single-use `state` is the guard); publications follow `reads._admit` |
| 5. « Publié » for a post nobody else sees (Meta app not Live, or restricted later); codes 10 and 200 would tell every shop to reconnect for nothing | Yes: `meta` only once the Meta app is Live (runbook); only code 190 asks to reconnect |
| 6. Connecting on a phone is untested (the Facebook app, another browser, a forgotten password). Hypothesis: a system user of the owner's business portfolio, with each shop's Page shared as a partner asset, removes the whole sign-in flow | Yes: the connection is proved on the pilot owner's own phone; the system-user way is looked at in Business Settings before v2 |
| 7. A restore of the database loses the publications made since: a double post | Yes: a line in the restore's list of what is undone |
| 8. « Connect once » may be false (Meta's 90-day data access) | Yes: `data_access_expires_at` is read during the real post's proof |
| Survive: the long-lived exchange, a server-side image, the connects table, the list of publications, a stub for publishing | Kept |
