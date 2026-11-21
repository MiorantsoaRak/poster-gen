# Design review r2 — Publish a poster on the shop's Facebook Page (design v2)

Reviewer: Codex, read-only, 2026-11-21. Verdict: REJECT (five P1, three P2; seven round-1 findings closed). Answered by v3, which removes a state, the browser hand-over and the photo-id success.

**Two P1 defects remain.** The only response shape actually proved for an *unpublished* photo can produce « Publié » in v2. Separately, a crash before dispatch can block that poster and Page forever, even though nothing was sent.

### Round‑1 rulings

| Round‑1 finding | Ruling against v2 |
|---|---|
| Matching an unknown upload by time and caption | **CLOSED** — the lookup and automatic permission to retry are gone. |
| Two stale sheets and same-key replay | **PARTIAL** — `seen` closes the two-fresh-key race and replay comes first. Replay must also match the route’s `creation_id`, and the sheet must acknowledge a settled result. |
| Different image or Page from the preview | **CLOSED** — admission checks both displayed IDs, ownership and revision, then uses that confirmation’s file. |
| Ambiguous response or failed settlement | **PARTIAL** — preparation moved before dispatch. Photo-ID-only success, stranded rows and loss of a known settlement remain. |
| Suspension, disconnect or replacement before dispatch | **CLOSED** — dispatch rechecks shop, terms and connection identity. A late 190 applies only to the connection that supplied the token. |
| Credentials in Graph URLs or logs | **PARTIAL** — raw Graph messages are gone. Body-only exchange and rejection of a copied Page token without proof remain unverified. |
| Callback code in history, referrers or ingress logs | **PARTIAL** — the dedicated page strips the query immediately. Query-free ingress logging is still optional, and the hand-over retains the code. |
| OAuth state consumption and concurrent replacement | **PARTIAL** — claim and conditional completion protect the successful exchange. Session binding and conditional failure cleanup need to be explicit. |
| `mutation_keys` retaining the dialog URL or callback data | **CLOSED** — connection routes can use the ordinary API helper directly, with neither mutation replay store. |
| Page picture and no-role failure | **PARTIAL** — the amendment drops the picture and the card explains refusal. If Facebook never returns, the design gives no trigger for that message. |
| Removed post and state-changing history GET | **CLOSED** — the amended history keeps its link and GET only reads. |
| Multiple Pages, lookup permission and shop-wide lock | **CLOSED** — the owner chooses from the disclosed first 100, lookup is gone, and the lock is per poster and Page. |
| Dialog settings and incomplete connection failures | **PARTIAL** — scope, timeouts and preservation of the earlier Page are specified. The actual login exchange still needs proof. |
| Confirmed file and caption fidelity | **CLOSED** — v2 sends the hash-checked PNG, mirrors caption handling and distinguishes stale confirmation from missing storage. |
| Database restore | **PARTIAL** — the warning discloses loss but neither restores known publications nor invalidates resurrected connections. |
| Migration, stub isolation and visibility proof | **PARTIAL** — `0018` follows `0017`. Stub isolation is unspecified, and customer visibility is explicitly unproved. |

The devil’s-advocate’s remaining proof questions are the phone connection and sharing flow, enforced Page-token proof, customer visibility and data-access expiry. The scheduled-photo test did not establish those. The requirements file also still marks its amendments as awaiting the owner’s word. [Proof table](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/facebook-publishing.md:22) · [Requirements](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/requirements/facebook-publishing.md:3)

### Findings and smallest fixes

| Severity | Place and trace | Smallest fix |
|---|---|---|
| **P1** | **Settlement, lines 126–136.** The unpublished proof returned `{id}`. The success rule accepts exactly that evidence and offers « Voir la publication ». A coded 5xx also matches both a refusal row and `unknown`. | Remove the photo-ID success branch. Require a valid `post_id` for the intended Page. Give 5xx precedence over Graph error codes. If saving a known success fails, retry only the local write with that result. |
| **P1** | **Recovery, lines 118–138.** A crash after `admitted` leaves no `sent_at`, no recovery and no owner action. A stale `sending` row has the opposite problem: GET can display `unknown` while the outcome POST still sees `sending` and refuses it until restart. | Close abandoned `admitted` as `failed` at startup and on stale admission. Dispatch only if its conditional `admitted → sending` update wins. Let the outcome transaction itself accept an eligible stale `sending` row atomically. |
| **P1** | **Callback, lines 75–95, 186.** The proxy receives `?code=…` before any script runs. Checking its log after a real connection can discover a leak only after it happened. `sessionStorage` also leaves the code readable by same-origin scripts if the app never consumes it. | Verify query-free ingress with a dummy query before real OAuth. Remove the storage hand-over: strip the URL, POST directly from the loaded callback document with the existing Origin, bundle and session checks, then replace-navigate to the account. Fail closed if the exchange requires secrets in a logged URL. |
| **P1** | **Restore, line 166.** Restore yesterday’s database after today’s successful post and disconnect. The sheet now sees `seen=null` and the old Page token, so a first-looking tap can duplicate today’s post. | Keep publishing off, discard restored attempts and connections, and reconcile publications from the kept database. Where history is lost, require the affected owner to check the Page before resuming. The runbook already retains the replaced database. [Restore procedure](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:617) |
| **P1** | **Provider mode, lines 43, 64–72.** A stub success survives a switch to `meta` on the same database and appears as real publication history. | Reuse the existing per-database provider-mode guard for `stub` versus `meta`. [Existing guard](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:572) |
| **P2** | **Connection claim and choice, lines 87–96.** There are **two** write transactions with network calls between them. A concurrent connect or DELETE wins on the success path. An unconditional failure delete could erase the replacement. Shop-only choice also lets another session of that shop see and finish the first session’s attempt. | Bind the attempt to the initiating session. Check the live session, attempt identity, step and expiry under the lock for completion and selection. Apply the same attempt predicate to failure deletion. [Existing session check](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/terms.py:57) |
| **P2** | **Waiting tokens, lines 57–63, 87–96.** The public response allows only IDs and names. Database and backup readers can read every raw candidate token. Ten minutes limits *selection* only: an abandoned row persists, and deleting it leaves existing snapshots intact. | Enforce expiry when storing and listing choices, purge expired rows, and state backup retention accurately. Gate real connections on proof that Meta rejects the copied token **without** proof and accepts it **with** proof. [Snapshot implementation](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/backup.py:53) |
| **P2** | **Admission and owner outcome, lines 108–117, 138–148.** The same key and body replayed against another poster URL could return the first poster’s « Publié ». Also, the latest row keeps its ID when `unknown` becomes `published`: a sheet opened on the pending row could pass `seen` without showing the repeat warning. A mistaken « Elle n’y est pas » then permits a deliberate second send. | Match `creation_id` on replay. Offer the publish sheet only after a fresh read shows no pending row. Label an owner-confirmed result « Présence confirmée par vous » with « Ouvrir la Page ». Before an absence answer, say **« Si elle apparaît plus tard, publier à nouveau créera un doublon. »** That residual risk is acceptable under the amendment once visible and accepted by the owner. |

The two removals with the most value are the photo-ID success branch and the browser storage hand-over. This was a read-only assessment of the design, code and recorded proofs. No device, store or live Meta checks were run.

**Verdict: REJECT.**