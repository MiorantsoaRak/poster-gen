Static review of [r3](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/product-visuals.md>). No files changed or network used. `D-PV-*` abbreviates design section IDs.

Phase 1 still permits bypassing the reject/revise path and has unresolved recovery cases.

R2 “new defects,” in their original order:

| Item | Status | Evidence |
|---|---|---|
| Retry idempotency / polling | CLOSED | D-PV-001/003: logical request owns ID/hash; polling returns its outcome; calls are children. |
| Guards excluding retries | CLOSED | D-PV-001: partial indexes cover the logical request throughout retry. |
| Retry allowance self-blocking / undercount | CLOSED | D-PV-003/005: request retains its slot; call 2 repeats only budget admission. |
| Approval-driven reset | CLOSED | D-PV-005: explicit cycle, requiring current-cycle approval; implements ADR-011. |
| Fallback revision | CLOSED | D-PV-005/006: parent-linked background, same cutout, corrections, no scene slot. |
| CSV identity/context/conflicting rows | CLOSED | D-PV-001/008: stored context, deterministic IDs, whole-file validation and row results. Crash-lock issue below remains separate. |
| LAN/session security | CLOSED | Cross-cutting: HTTPS, secure opaque sessions, expiry/revocation and login exemption specified for phase 2. |
| Claimed external hard spending stop | CLOSED | D-PV-003: explicitly unverified; cap described as estimated spend. |
| “Worst case” figures | PARTIAL | D-PV-008: base scenario relabelled; new “upper bound” remains wrong. |

R2 “remaining requirement gaps”:

| Criterion | Status | Evidence |
|---|---|---|
| R-002 c2 | PARTIAL | D-PV-003 blocks pending/running scenes, but a fresh initial request is allowed after rejection, bypassing revision linkage and corrections. |
| R-002 c4 | CLOSED | D-PV-003/006: exact dimensions, mandatory scene framing confirmation, contained fallback placement. |
| R-003 c1 | CLOSED | D-PV-002 implements amended best-effort screening, including the cited commercial examples. |
| R-005 c1–2, c4 | PARTIAL | D-PV-005 fixes revision mechanics/cycles; arbitrary run labels still replenish allowance. |
| R-007 c1; R-008 c2 | PARTIAL | D-PV-001/008 fixes provenance and allocation; no abandonment action/state distinguishes abandoning from merely stopping. |

R2 “not yet on the radar”:

| Item | Status | Evidence |
|---|---|---|
| Stub contamination | CLOSED | D-PV-001/003: immutable provider mode and separate data directory. |
| Budget configuration | CLOSED | D-PV-001/003: startup validation, integer estimates and empty-ledger `COALESCE`. |
| Mask correctness | CLOSED | D-PV-006 explicitly distinguishes pixel preservation from segmentation correctness; operator preview remains required. |
| Evaluation difficulty confound | CLOSED | D-PV-008 implements user-assigned balanced arms and acknowledges weak evidence; ADR-011 decides this. |

Carried-forward r1 radar items in r2: approval dependency **CLOSED** (Phasing); variant integrity **CLOSED** (D-PV-003/006); CPU recovery **CLOSED** (D-PV-006); stub accounting **CLOSED** (D-PV-003); model availability/dimensions/prices **OPEN**, explicitly deferred to scaffold/probe verification.

New r3 defects, ranked:

| Severity | Location | Failure scenario → fix |
|---|---|---|
| **Major** | D-PV-003 rule 3; D-PV-008 `generate` | Changing only `--run L1` to `L2` grants another allowance and bypasses `review_pending`, even with identical model/configuration and no approval. “CLI-only” provides no restriction in phase 1. → Reuse/refuse equivalent evaluation runs within the campaign; labels must not independently create allowances. Preserve independent runs for genuinely different evaluated configurations. |
| **Major** | D-PV-001 crash recovery | A crash leaves the `O_EXCL` lock file. The next CLI refuses before it can recover the running request—including one whose call 2 was running. → Specify a process-lifetime lock or safe stale-lock recovery before owner-scoped database recovery. |
| **Major** | D-PV-003 retry admission | Call 1 fails, but its reservation leaves insufficient budget for call 2. Retry admission returns before inserting call 2; no explicit transition finalizes the logical request. It can retain `running`, its slot and guards. → Explicitly finalize denied/exhausted retry admission as `failed`, with the admission error and retained costs. Cover terminal database-admission failure too. |
| **Major** | D-PV-005 fallback revisions | Arm B suppresses corrections only for scene revisions; fallback revisions explicitly apply corrections. This violates the evaluation exception and mixes corrected backgrounds into the plain-reroll arm. → Apply the same `by_arm` rule to background revisions. |
| **Major** | D-PV-003/004 approval | A fallback can be approved without `framing=ok`. Amended R-004 c2 requires the checklist confirmation; computed placement is not an exemption. → Require/store framing confirmation for both treatments. |
| **Minor** | D-PV-008 suggested run | Retrying every invocation **and** adding one background per product costs approximately **$72 / $104**, not $60 / $92. Unlimited failed requests/background revisions also prevent a workload-based upper bound. → Use those figures for the stated bounded scenario and remove “upper bound.” |

Requested concurrency/accounting checks:

- **CSV `k`:** under the single-CLI lock, concurrent replays cannot race. A successful action retains its ID; failed/interrupted actions intentionally receive a new one. This is not itself a duplicate-request defect. After interruption, a fresh paid request can still duplicate provider work whose result was lost; retained reservations account for that uncertainty.
- **Call-2 crash recovery:** the database rule correctly interrupts the parent and its running child, preserving both call costs. The stale lock prevents reaching that rule.
- **Budget:** both calls reserve before dispatch. No unreserved paid invocation is specified.
- **Cycles:** the approval prerequisite implements ADR-011. The distinct loophole is creating another run label without starting a cycle.

Remaining phase-1 requirement failures:

- **R-002 c2:** initial requests after rejection evade mandatory reject/revise. Reject a new initial request once that scope has a successful scene request; require revision or an authorized new cycle.
- **R-005 c4:** equivalent new run labels evade the allowance.
- **R-005 evaluation exception:** fallback arm-B revisions retain corrections.
- **R-004 c2:** fallback approval omits mandatory framing confirmation.
- **R-008 c2:** abandonment remains unrecorded; add an explicit abandonment decision and report outcome.

**Deferred, not defects:** phone review/toggle/zoom, HTTP/UI direction and upload flows, poster API/UI approval enforcement, and editor reuse/move/resize/shadow messaging. These belong to phase 2 or the downstream editor designs.

Simplifications: move draft HTTP/session contracts into the later design; use a process-lifetime CLI lock instead of maintaining a stale-file recovery protocol.

Not yet on the radar:

- **Mutable evaluation inputs:** immutable runs do not snapshot fixture hashes or arm assignments. Editing the CSV can change corrections/report labels mid-run. Persist those assignments.
- **Estimate recalibration:** immutable run estimates conflict with the requirement to raise estimates after a higher billed observation. Define a prospective reservation floor without rewriting historical calls or forcing a new run.
- **Cross-cycle reporting:** reports group by run/variant/treatment but omit cycle, although `attempt_no` restarts. Include cycle to avoid ambiguous “first approved attempt.”

**REWORK**