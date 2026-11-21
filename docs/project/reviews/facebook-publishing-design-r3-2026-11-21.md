# Design review r3 — Publish a poster on the shop's Facebook Page (design v3)

Reviewer: Codex, read-only, 2026-11-21. Verdict: APPROVE WITH FIXES (two P1 to fix before implementation; both are in the design as approved). Its last two paragraphs sort what is left between the implementation and the proofs with the owner.

Four round‑2 findings are closed. Two paths still permit a duplicate even when the owner checks the Page and answers accurately.

| Round‑2 finding | Ruling against v3 |
|---|---|
| P1 Settlement | **CLOSED** — only a Page-matching `post_id` establishes success, 5xx takes precedence, and settlement retries only the database write. |
| P1 Recovery | **PARTIAL** — the stranded `admitted` state is gone, but the two-minute rule lets the owner release a send that can still run. |
| P1 Callback | **PARTIAL** — browser storage is gone and the dummy-query gate covers ingress. The outbound exchange still allows a secret-bearing GET without an explicit fail-closed rule if its URL can be logged. |
| P1 Restore | **PARTIAL** — restore clears credentials and copies missing rows, but skips a known publication when the backup already contains its pending row. |
| P1 Provider mode | **CLOSED** for ordinary operation — the database records `stub` or `meta` and refuses the other mode. Restore must preserve that invariant too. |
| P2 Connection claim and choice | **PARTIAL** — session binding and conditional cleanup are specified. Exchange completion checks only hash and step, omitting the live-session and expiry checks requested in round 2. |
| P2 Waiting tokens | **PARTIAL** — selection, listing, backup retention and the proof gate are covered. An expired exchange can still store tokens, and without another connect an abandoned row can remain past ten minutes. |
| P2 Admission and owner outcome | **CLOSED** — replay matches the poster, pending rows suppress the sheet, and both owner answers carry the requested wording. |

**Two P1 fixes before implementation**

1. **Recovery can release a live sender.** The handler commits `sending`, then pauses before dispatch. After two minutes the owner sees an empty Page, truthfully chooses « Elle n’y est pas » and publishes again. The first handler resumes and sends too. The 60-second HTTP timeout starts too late to prevent this trace. Remove age alone as permission to resolve the row. While the local handler can still dispatch or settle, keep the outcome action unavailable. Once it exits, or startup recovery establishes that it died, allow resolution. [Dispatch and recovery](docs/project/designs/facebook-publishing.md#d-fb-publish-003--publishing-covers-r-fb-publish-002-003-004)
2. **Restore can discard Facebook’s receipt.** The backup captures `sending`. The kept database later records `published` and the `post_id`. Both contain the same row ID, so “copy rows the restored one lacks” skips the receipt. Recovery then asks the owner to decide something the kept database already proves. For a matching pending row, copy the kept settlement and link. Also carry or verify `facebook_mode` when importing history into a backup that predates its first Facebook call. [Restore rule](docs/project/designs/facebook-publishing.md#failure-modes-external-system-access-secrets)

**Implementation and tests.** The callback entry has to strip the URL, await the session check, and open the verified shop gate before posting the code. Otherwise the existing helper throws `gate_closed` on every return. Test the built entry, expiry and revocation during exchange, the paused sender, and a restore with the same publication ID in both databases. For OAuth exchange, keep `meta` off if the working method exposes a secret in any log. [Request helper](frontend/src/api.ts) · [Live-session check](backend/src/affiche/posters/auth.py) · [Restore command](backend/src/affiche/shops.py)

**With the owner.** The dummy-query log check, token rejection without proof and acceptance with proof, phone connection and sharing, and the first customer-visible post remain release proofs. That post should verify the returned ID and link, PNG rendering and AI label. The requirement amendments and terms timing still need the owner’s decision. This review used repository reads only. [Proofs and owner decisions](docs/project/designs/facebook-publishing.md#open-for-the-owner)

**APPROVE WITH FIXES**