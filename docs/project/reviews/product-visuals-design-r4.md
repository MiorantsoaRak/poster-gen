Three local fixes remain:

1. **Major — [abandonment targeting, L446](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/product-visuals.md:446>):** CSV identifies only variant and treatment, although abandonment requires run and cycle. Multiple runs are ambiguous; replay after `new-cycle` targets the new cycle. **Fix:** persist explicit run/cycle in the action, validate the full scope, and make replay address that original scope.

2. **Major — [cross-cycle background identity, L453](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/product-visuals.md:453>):** reusing a previously successful cutout in another cycle produces the same `{target}:background:{k}` UUID. Idempotency returns the old request or raises `request_id_reused`. **Fix:** include the action’s persisted run/cycle in its identity and failure counter.

3. **Major — [initial guard, L119](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/product-visuals.md:119>) plus [same-cutout revision, L348](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/product-visuals.md:348>):** after rejecting a fallback because its cutout is wrong, a replacement cutout cannot start another initial background, while revision requires the old cutout. Without another approval, a new cycle is unavailable. **Fix:** permit a parent-linked fallback revision to select another confirmed cutout of the same variant/run; retain the linear chain.

R3 dispositions below use design section numbers.

| R3 item | Status | Evidence |
|---|---|---|
| New defect: run-label loophole | CLOSED | §001/008: unique model/quality; duplicate label configuration refused; limit constrained to 1–5. |
| New defect: stale lock | CLOSED | §001: lifetime OS lock acquired before owner-scoped recovery, including call 2. |
| New defect: refused retry admission | CLOSED | §003: budget denial finalizes atomically; busy/write-failure outcomes specified. |
| New defect: arm-B fallback revisions | CLOSED | §005: both revision purposes omit corrections using snapshotted arm. |
| New defect: fallback framing | CLOSED | §003/004: both treatments require framing confirmation. |
| New defect: cost figures | CLOSED | §008: $72/$104; explicitly not a ceiling. |
| Requirement: R-002 c2 | CLOSED | §001/003: initial uniqueness plus parent-linked revisions prevents fresh-root bypass. |
| Requirement: R-005 c4 | CLOSED | §001/008: equivalent labels cannot replenish allowance. |
| Requirement: R-005 evaluation exception | CLOSED | §005: arm B applies to scenes and backgrounds. |
| Requirement: R-004 c2 | CLOSED | §004: approval requires framing for both treatments. |
| Requirement: R-008 c2 | PARTIAL | Table/action/report exist; abandonment’s input scope remains ambiguous (#1). |
| Radar: mutable evaluation inputs | CLOSED | §008: row hash and arm snapshot; changed existing rows refused. |
| Radar: estimate recalibration | CLOSED | §003: prospective usage-based floor; historical costs unchanged. |
| Radar: cross-cycle reporting | CLOSED | §008: grouping includes run, variant, cycle and treatment. |

The indexes permit fallback after the scene limit, replacement of a failed initial request, and initials in a new cycle. Earlier-cycle cutouts pass those guards but encounter #2. No phase-1 conflict found with model/quality uniqueness. Windows lock-before-recovery ordering is correct as specified.

**APPROVE WITH FIXES** — the three local contract edits above.