Criterion numbers below follow checkbox order in the requirements file.

**1. Actionable defects**

| # | Severity | Location | Defect, failure scenario, suggested fix |
|---|---|---|---|
| 1 | **Blocker** | D-PV-003, gateway steps 1–2 | **Budget check and reservation are not atomic.** With a $1 cap and $0.60 spent, two concurrent $0.40 requests both pass and reserve $1.40. Put the check and attempt insertion in one serialized database transaction shared by API and CLI. |
| 2 | **Blocker** | D-PV-003, Cost math | **The claimed actual-spend bound does not hold.** With missing usage, ten calls estimated at $0.40 but actually costing $1 consume $10 against a $4 cap—well beyond two calls of overshoot. Rounding up does not make an estimate an upper bound. Reserve a justified maximum charge; retain unresolved charges conservatively or suspend paid requests pending reconciliation. |
| 3 | **Major** | D-PV-003, gateway step 3 | **Automatic retries bypass per-call accounting.** A connection failure after billing followed by success produces two potentially billable calls but only one described reservation/attempt row. Give every provider invocation its own reservation and ledger entry, linked to one logical request. |
| 4 | **Major** | D-PV-005, DQ-4 | **The limit contradicts ADR-010.** After three candidates, changing direction starts another chain; concurrent initial requests also bypass revision guards. Enforce three generated attempts **per variant**, with atomic allocation before dispatch. Define how uncertain outcomes consume that allowance. DQ-4 requires a requirements/ADR amendment, just as DQ-1 does. |
| 5 | **Major** | D-PV-001, D-PV-005 | **Restart recovery strands recent attempts.** Restart one minute after dispatch: the attempt misses the startup-only “older than 10 min” sweep and remains `running` indefinitely. An interrupted revision also retains its guard. Recover all attempts owned by the dead process and reconcile their guards atomically, without automatically regenerating. |
| 6 | **Major** | D-PV-003–004 | **Framing warnings do not enforce crop eligibility.** A returned 1080×1350 image passes the stated minimum-edge check but cannot supply a 1080×1920 crop. A clipped product can also be approved despite `fits_all_formats=0`. Validate actual dimensions and all three crops; require explicit framing verification when detection is uncertain. Replacement scenes need separate review. |
| 7 | **Major** | D-PV-006, placement | **Height-only scaling cannot guarantee fit.** A product with aspect ratio 2:1 becomes 1920 pixels wide at the proposed 960-pixel height, exceeding the 1080-pixel safe width. Compute scale from both bounding-box dimensions and validate the translated box before setting `fits_all_formats=1`. |
| 8 | **Major** | D-PV-003, API | **The low-resolution warning arrives too late.** The `202` response contains the warning after generation has been scheduled; the operator cannot decide whether to continue before spending. Add preflight validation and explicit acknowledgment before dispatch. |
| 9 | **Major** | D-PV-002 | **Commercial terms are still sent.** “Garantie 12 mois, 500 000 Ar” passes through verbatim; even a regex match only warns. R-003 does not restrict its prohibition to catalogue fields. Require correction of prohibited input before dispatch, or obtain an explicit scope amendment. |
| 10 | **Major** | D-PV-008 | **Batch evaluation bypasses cutout review.** A technically successful mask with visibly damaged edges is auto-confirmed and incurs background spend. Pause batch processing for operator cutout approval; segmentation success is not approval. |
| 11 | **Major** | D-PV-006 | **Cutout transitions lack concurrency rules.** Confirm/reject can race, and repeated confirmation can dispatch duplicate backgrounds. Define conditional transitions, atomically associate confirmation with its attempt, and specify an idempotent retry path for a confirmed cutout. |
| 12 | **Major** | D-PV-001, D-PV-007–008 | **Evaluation accounting cannot reliably reproduce the promised report.** Failed initial attempts have neither parent nor candidate, so their chain is unidentified. Runs/models can mix; abandonment is not recorded; mean duration replaces individual attempt durations. Assign logical request/run identifiers before calling, attach UI revisions, record abandonment, and export attempt-level timings alongside aggregates. |
| 13 | **Major** | D-PV-003, error mapping | **Terminal provider handling is incomplete.** An exhausted `rate_limit_exceeded` retry has no mapping; malformed successful image responses have no specified outcome. Add terminal mappings and response validation, preserving inputs and budget reservations without creating a usable candidate. |
| 14 | **Minor** | D-PV-002, fixed instructions | **Logo instructions conflict.** “Keep … logo” and “No … logos … anywhere” can induce removal of manufacturer markings. Distinguish preserved product markings from newly added scene graphics. |

Other claim checks:

- D-PV-004’s conditional update prevents two exits from `pending_review`. D-PV-005’s guard and unique-child index prevent branching successful chains; they do not enforce the variant-wide limit or bound paid invocations.
- Crop geometry is valid: all crops span `x=[4,1084)`; their vertical ranges are `[0,1920)`, `[285,1635)`, and `[420,1500)`.
- The pixel invariant is satisfiable: copy RGB from the consistently EXIF-oriented source and modify only alpha, including when resizing the mask. Explicitly test rotated EXIF inputs and the mask-downscale path.
- Unset-cap refusal is specified. This review establishes no runtime guarantee.

**2. Unmet or mis-covered requirements**

| Criterion | Gap |
|---|---|
| R-002 c2 | Unrestricted initial requests bypass the prescribed reject/revise path; see #4. |
| R-002 c4 | Whole-product visibility across all formats is not enforced; #6–7. |
| R-002 c7 | Warning does not precede the decision to generate; #8. |
| R-003 c1 | Prohibited commercial terms can reach the provider; #9. |
| R-005 c4 | Three attempts per chain replaces three per variant; #4. |
| R-006 c4 | Moving synthetic shadow contradicts the approved criterion. DQ-1 acknowledges this but does not amend it. |
| R-006 c5 | Evaluation spends before operator cutout review; #10. |
| R-007 c1 | Failed-attempt cost attribution is incomplete; #12. |
| R-008 c2 | Attempt-level timings, abandonment and reliable cost attribution are missing; #12. |
| R-008 c4 | Concurrent reservations and retries can start without available estimated budget; #1, #3. |

**3. Simpler logic / removable parts**

- DQ-1 has a third option: composite a **static synthetic shadow into the background**, leaving the cutout separate. This preserves ADR-009 without a movable shadow asset or a generated product “ghost.”
- Store revision ownership through a linked attempt identifier instead of maintaining an independently cleared timestamp flag.
- For the pilot, explicit three-crop human verification may replace the scene segmentation heuristic; retain dimension checks.

**4. Not yet on the radar**

- **Approval dependency:** evaluation requires implemented phase-2 screens, while final design approval requires evaluation evidence. Define the approval boundary for the evaluation implementation.
- **Variant integrity:** `photo_assets` accepts arbitrary hashes; specify validation that selected originals belong to the requested confirmed variant.
- **CPU recovery:** specify how native cutout inference is interrupted at 60 seconds. A timeout around synchronous inference alone does not stop its work.
- **Stub accounting:** specify zero-cost or excluded stub rows; the budget sum currently has no provider filter.
- Model availability, custom-size support and prices remain unverified in this offline review.

**REWORK**