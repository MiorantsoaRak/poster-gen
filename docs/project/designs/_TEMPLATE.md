# DESIGN — <feature>

> One file per feature, matching `../requirements/<feature>.md`. Prefix IDs: `D-<FEAT>-001`. Update `_INDEX.md` when adding or changing statuses.

> Rules: every design section maps to one or more requirement IDs. A design is not done until its edge cases and failure modes sections are filled in — "none" must be written deliberately, not left blank.

## System overview

**Status:** Draft / Approved / Implemented  
**Requirements file:** `../requirements/<feature>.md`  
**Approval record:** <date and user approval reference; pending while Draft>

<3–10 lines or an ASCII diagram: components, what talks to what, where state lives.>

```
[client] ──HTTP──▶ [api] ──▶ [db]
                     │
                     └──▶ [worker/queue]
```

---

## D-<FEAT>-001 — <feature/component name>  (covers R-<FEAT>-001, R-<FEAT>-00x)

**Approach:** <2–5 lines: the chosen approach and, if alternatives were considered, why this one. Link a DECISIONS.md entry for anything contested.>

**Data model changes:**
```sql
-- tables/columns added or changed, or "none"
```

**API contract / interface:**
```
POST /resource
request: { ... }
200: { ... }
4xx: { error codes and meanings }
```

**State machine** (if the feature has lifecycle states — transfers, jobs, orders):
```
created → processing → done
              └──▶ failed → retrying (max N) → dead
```
Every state must have: who/what triggers entry, what exits are legal, what happens on crash mid-state.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---------|-----------|----------|
| <external service timeout> | | retry N× then ... |
| <partial write / crash mid-operation> | | idempotency via ... |

**Edge cases:**
- <empty input, duplicates, concurrency, clock skew, unicode/encoding, pagination limits...>

**Security / data notes:**
- <authz checks, PII handling, input validation boundary — or "none, internal only">

---

<!-- One D-xxx block per feature. Small features can compress sections but never delete the failure-modes table. -->
