# REQUIREMENTS — generation-jobs

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-GENERATION-JOBS-001 | Claude scene planning | P0 | Approved |
| R-GENERATION-JOBS-002 | Bounded, recoverable generation | P0 | Approved |

## R-GENERATION-JOBS-001 — Claude scene planning

As the operator, I can turn a French creative brief into a coherent scene direction without writing a technical image prompt.

Acceptance criteria:

- [ ] Claude can inspect the original references and use confirmed identity, the user's direction, target format and selected text/shop fields to propose setting, lighting, viewpoint, product placement and clear areas for overlays.
- [ ] Its result is a structured plan validated by the server. It references confirmed commercial fields rather than rewriting the price, contact, title or logo. It cannot supply executable HTML or code.
- [ ] The image prompt derived from the plan contains the confirmed identity and artistic instructions, with no commercial offer text, invented claims or request to draw the shop identity. Text/price/shop layers remain the editor's responsibility.
- [ ] The operator can inspect and adjust a concise French scene description before requesting the image. An explicit request creates one plan; the system does not run an automatic chain of creative retries.
- [ ] Invalid output, contradictory facts, timeout, refusal or missing Claude configuration preserves the user's inputs and shows a recoverable error. The operator can retry planning or explicitly use the existing validated prompt builder; there is no silent fallback or image spend.
- [ ] Planning usage is recorded separately from image usage, with actual or clearly estimated costs. Both count toward the configured budget. No API key reaches the browser.
- [ ] Before choosing the production planner/model, compare planned prompts with the current builder on the same real product inputs and record fidelity, composition, editing effort, latency and total cost. The existing two scene tests do not count as a Claude test.

Out of scope: automatic product-fact verification, autonomous creative optimisation and generated advertising claims/captions. Exact plan schema, model choice and provider error mapping belong in the design.

## R-GENERATION-JOBS-002 — Bounded, recoverable generation

As the operator, I know what is running, what it cost, and whether retrying will create another paid request.

Acceptance criteria:

- [ ] Every explicit image action requests one candidate. Double clicks, reconnects and replay of the same operation do not create duplicate paid jobs.
- [ ] Visible states distinguish waiting, running, successful candidate, failed and interrupted. A refresh/reopen recovers the stored job state and result; failure never appears as success.
- [ ] Only bounded transport retries are automatic; creative revisions and alternative scenes always require explicit action. A timeout with an uncertain provider outcome is not blindly replayed as a fresh paid call.
- [ ] Reserve an estimate before each provider call and refuse if it would exceed the global cap. Preserve actual/estimated usage for failed and rejected attempts. Restarting a draft never resets the global ledger.
- [ ] Normal poster drafts allow three successful or running scene attempts before further generation is blocked. The operator may retain a good version, replace an unsuitable source, or explicitly start a new draft after abandonment; they need not approve a bad image to continue. New drafts and their spending remain linked in history.
- [ ] Show why an attempt or budget limit blocks generation. Optional cutout is offered only as a choice, never launched automatically at the limit.
- [ ] Provider/storage failure leaves the last good candidate and draft intact. Late results cannot overwrite a newer selected candidate. A caller cannot read or change another operator's protected data.
- [ ] The phase-1 evaluation's immutable runs, arms and cycle rules remain separate from normal poster drafts. Their existing spend records and evidence are preserved.

Out of scope: billing/subscriptions and deployment. Queue, concurrency, access/session policy, cancellation semantics and recovery mechanics require explicit design failure modes.
