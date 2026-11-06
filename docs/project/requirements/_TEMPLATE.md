# REQUIREMENTS — <feature>

> One file per feature. Copy this template to `requirements/<feature>.md`. Prefix IDs with the feature slug: `R-<FEAT>-001`. Update `_INDEX.md` when adding or changing statuses.

> Rules: every requirement has an ID, a status, and acceptance criteria that a machine or a checklist could verify. No design or code exists for a requirement that isn't `Approved`.

**Statuses:** `Draft` → `Approved` → `Implemented` → `Verified` (or `Dropped`)

## Index

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| R-<FEAT>-001 | | P0 | Draft |

---

## R-<FEAT>-001 — <title>

- **Status:** Draft
- **Priority:** P0 (blocker) / P1 (needed) / P2 (nice to have)
- **Story:** As a <user>, I want <capability>, so that <outcome>.

**Acceptance criteria** (each one testable):
- [ ] GIVEN <precondition> WHEN <action> THEN <observable result>
- [ ] Error case: WHEN <bad input / failure> THEN <defined behavior, not a crash>

**Out of scope for this requirement:**
- <explicitly excluded behavior>

**Open questions:**
- <anything blocking Approved status — must be empty before approval>

---

<!-- Duplicate the block above per requirement. Keep the index table in sync. -->
