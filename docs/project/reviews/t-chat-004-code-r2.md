**APPROVE**

| Round-1 finding | Ruling | Evidence |
|---|---|---|
| 1. Concurrent paid cards | **CLOSED** | `held` blocks fresh admissions; refusal recap waits; the unresolved card remains replayable. |
| 2. Pending read identity lost across threads | **CLOSED** | Other threads cannot send or replace it. Returning replays the original key and body. |
| 3. Unnecessary charge for layer-only price | **CLOSED** | Uses the selected visual’s price metadata. Free changes call only `adapter.price`, remain unspent and respect `held`; `whole` forces redraw. |
| 4. Obsolete ownership saves a queued price | **CLOSED** | Both adapter paths drain earlier saves, then check ownership before queuing the price. Restoration uses the same guard. |
| 5. Restoration captures the wrong price | **CLOSED** | `previous` comes from the selected image’s persisted price, despite a stale offer. |
| 6. Older count overwrites newer count | **CLOSED** | The sequence guard retains only the latest result, including when the latest request fails. |

No new in-scope findings.

Verified: TypeScript, diff whitespace, and targeted in-memory checks using the actual ChatView code, adapter members and `DraftSaver`. These covered all six corrections. Files remained unchanged.

Not rerun: Vitest, pytest, build, browser/device checks or contrast measurements; claimed suite results remain unverified. No servers, network, paid calls, persistent-store writes or `backend/.env` access.  
Remaining limitation: this review verifies the fixes in isolation, without end-to-end execution.