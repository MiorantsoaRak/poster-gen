Static review of [r2](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/product-visuals.md>). `D-PV-*` abbreviates design section IDs; criterion numbers follow checkbox order. No files changed or network used.

R1 findings:

| # | Status | Evidence |
|---|---|---|
| 1 | CLOSED | D-PV-003: budget check and reservation share `BEGIN IMMEDIATE` across API and CLI. |
| 2 | PARTIAL | D-PV-003: estimated-spend semantics are explicit, but the replacement external “hard stop” remains unestablished. |
| 3 | PARTIAL | D-PV-001/003: separate retry rows specified, but request-level idempotency prevents their insertion as written. |
| 4 | PARTIAL | D-PV-005: variant scope restored; approval reset is unapproved, retries escape counting, and initial requests still bypass rejection. |
| 5 | CLOSED | D-PV-001: all owned running attempts become interrupted, releasing guards; assumes the stated single API process. |
| 6 | PARTIAL | D-PV-003/004: dimensions enforced; crop frames displayed, but explicit framing confirmation is not an approval precondition. UQ-2 remains pending. |
| 7 | CLOSED | D-PV-006: placement uses both dimensions and asserts safe-square containment. |
| 8 | CLOSED | D-PV-003: preflight and required acknowledgment precede spending; CLI acknowledgment specified. |
| 9 | PARTIAL | D-PV-002: matching terms block, but `500 euros, livré demain` passes the specified rules and sends prohibited terms. |
| 10 | CLOSED | D-PV-006/008: batch stops at proposed cutout; operator confirmation precedes background generation. |
| 11 | PARTIAL | D-PV-001/006: conditional decisions specified; background guard excludes retries and CSV retry identity is unspecified. |
| 12 | PARTIAL | D-PV-001/008: request/run IDs and invocation timings added; abandonment, immutable run configuration and billed-share allocation remain unspecified. |
| 13 | CLOSED | D-PV-003: terminal rate-limit and invalid-response mappings added. |
| 14 | CLOSED | D-PV-002: preserved product markings distinguished from added graphics. Requirements amendment remains pending separately. |

R1 “not yet on the radar”:

| Item | Status | Evidence |
|---|---|---|
| Approval dependency | PARTIAL | Phasing defines an evaluation boundary, awaiting UQ-3 approval. |
| Variant integrity | PARTIAL | D-PV-003 checks scene photos; D-PV-006 does not explicitly apply membership validation to `photo_asset`. |
| CPU recovery | CLOSED | D-PV-006 removes the unenforceable timeout and specifies serialized thread-pool inference. |
| Stub accounting | CLOSED | D-PV-003: zero-cost stub rows excluded from budget. |
| Model availability, dimensions, prices | OPEN | Stack/D-PV-003 defer verification to scaffolding and probe; no verified evidence supplied. |

New defects in r2:

| Severity | Location | Failure scenario → fix |
|---|---|---|
| **Major** | D-PV-003 steps 1, 3; polling API | Retry retains `request_id`; step 1 finds the failed root and returns it instead of inserting the retry. Polling also exposes the root rather than a defined logical outcome. → Separate logical-request idempotency from invocation insertion; resolve polling to the logical request’s current result. Reject same-ID/different-payload reuse. |
| **Major** | D-PV-001 partial unique indexes | **SQLite syntax is valid; guard semantics are wrong.** A failed root plus a running/succeeded retry contributes no indexed row, allowing another root for the same parent/cutout and duplicate candidates. → Hold ownership across the logical request, including retries; enforce successful-child uniqueness. |
| **Major** | D-PV-005 allowance | With two candidates and the last root running, retry admission sees three used slots and refuses its own replacement. Marking the root failed instead releases its slot, while the retry is excluded: another request can enter and produce a fourth candidate. → Maintain an allowance reservation across retries. This is logical self-blocking/undercounting, not a SQLite lock-cycle deadlock; define `SQLITE_BUSY` handling separately. |
| **Major** | D-PV-005 `window_start` | Approving an old pending candidate or a fallback resets the window and excludes existing scenes. Repeating fallback approvals replenishes scene attempts. ADR-010 authorizes no reset. → Remove it pending explicit approval; if approved, use explicit generation cycles rather than review timestamps. |
| **Major** | D-PV-005/006/008 | Revising a rejected fallback encounters its cutout’s already-successful background guard; the generic revision allowance can also block it after three scenes. `build_background_prompt(direction)` accepts no corrections. → Define treatment-specific revisions, reuse the confirmed cutout, permit a parent-linked replacement background, and pass reasons/note. |
| **Major** | D-PV-001 cutouts; D-PV-008 `apply` | CSV rows have no stable action/request ID; cutouts retain neither direction nor run label. After interruption between confirmation and generation, replay identity and request reconstruction are unspecified. Duplicate/conflicting rows can also pass independent prevalidation. → Persist action IDs and request context; reject conflicting rows; report resumable per-row outcomes. |
| **Major** | Cross-cutting / Security | LAN transport has no HTTPS requirement. `HttpOnly`/`SameSite` do not prevent interception of the login token or cookie. Cookie authenticity and server-enforced expiry are unspecified; “every `/api` route” also includes login. → Require trusted HTTPS and `Secure`; define opaque/signed sessions, expiry/revocation, and an explicit login exemption. |
| **Major** | D-PV-003 money guards | An optional project budget is called a hard stop without establishing request-blocking behavior. A probe and 25% margin cannot establish a future maximum bill. → Remove that guarantee or require verified enforcement; keep estimated and billed figures clearly distinguished. |
| **Minor** | D-PV-008 suggested run | “Worst case” $30/$46 excludes automatic retries, failed calls and repeated backgrounds. → Label these base-scenario estimates and account for those additional invocations. |

Remaining requirement gaps:

| Criterion | Why |
|---|---|
| R-002 c2 | Different initial-request UUIDs still obtain additional candidates without rejecting/revising the preceding candidate. |
| R-002 c4 | Displaying crop frames does not require the operator to verify whole-product visibility before approval. |
| R-003 c1 | The blacklist permits ordinary commercial phrasing. Constrain accepted input or obtain an amendment acknowledging a weaker guarantee. |
| R-005 c1–2, c4 | Fallback revisions/corrections are incomplete; allowance retry handling and approval resets violate the prescribed limit. |
| R-007 c1; R-008 c2 | CSV context/replay remains incomplete. “Not approved” conflates pending, failed, exhausted and abandoned; `run_label` alone does not prevent model/configuration mixing. Billed allocation is undefined. |

UQ decisions remain pending:

- **UQ-1:** option (a) preserves R-006 c4; option (b) requires its amendment.
- **UQ-2:** current R-003 c2/R-004 c2 remain binding until the text/checklist amendment is approved.
- **UQ-3:** phase-1 sheets do not establish the required phone review experience; phase-only approval needs explicit agreement.
- **UQ-4:** five attempts and omitted corrections conflict with R-005 c4 and c1 respectively until the evaluation exception is approved.

The CSV path specifies rejection reasons, conditional decisions and cutout confirmation before spending. It does **not** yet preserve all R-005 behavior through revisions, interruptions and replays.

Simpler parts:

- One logical-request record can own idempotency, retry state, allowance reservation and concurrency guards.
- Separate review decisions from generation actions in CSV; this makes retrying generation independent of replaying a final decision.
- If UQ-1(a) wins, remove the separate movable-shadow path and unnecessary shadow asset persistence.

Not yet on the radar:

- **Stub contamination:** zero cost does not isolate stub candidates from paid allowances, approval resets or reusable visuals.
- **Budget configuration:** define empty-ledger `SUM → 0`; reject future `SPEND_CAP_SINCE` and nonpositive/nonfinite estimates.
- **Mask correctness:** hole filling can preserve actual background inside product openings; fixed erosion can remove thin details. Pixel equality alone detects neither.
- **Evaluation validity:** UQ-4’s “half the products” comparison confounds correction effectiveness with product difficulty unless assignment is paired or appropriately balanced.

**REWORK**