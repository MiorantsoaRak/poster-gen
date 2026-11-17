**Verdict: APPROVE WITH FIXES.** No remaining shop-row replacement bypass found. One P2 concerns the rehearsal contract.

- **P2 — Arbitrary check names can suppress earlier contracts.** [rehearse.py:207](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/rehearse.py:207). The dictionary discards earlier assertions sharing a name. I confirmed the consequence with a synthetic in-memory migration: change legacy `login_failures.identifier` values, restate 0013’s check as `SELECT 0`, and rehearsal still passes. Projected hashes exclude that new column; GUARDS do not cover its values.

  The particular 0015 override preserves the intended protection, but this general mechanism weakens the release gate. Prefer a narrow, documented compatibility rule for 0013’s trigger-list check: validate `keep_shop` by name, retain version-qualified checks, and give 0015 its own check name. This leaves 0013 untouched. Add a regression ensuring unrelated duplicate names cannot silently erase assertions.

- **P3 — Document the accepted `-1` boundary accurately.** [0015_shop_guards.py:18](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0015_shop_guards.py:18). “Collides with nothing” is conditional: inserting a fresh shop explicitly at id `-1` succeeds, then ordinary automatic-ID creation fails with “a shop is never replaced.” Deletion and re-identification guards prevent repairing that row through ordinary DML. This matches the earlier accepted failure-closed boundary; document it and pin it with a test.

- **P3 — Commit the fourth pragma combination.** [test_credits.py:264](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_credits.py:264), using [WRITERS:73](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_credits.py:73), omits foreign keys **off**, recursive triggers **on**. My independent checks passed there. Include that combination and representative INSERT … SELECT and NULL/negative-ID cases in the regression suite.

The remaining implementation choices are sound:

- Renaming to a free identifier matches the approved forward-migration provision.
- `id INTEGER PRIMARY KEY` aliases rowid in the existing table; no separate rowid clause is needed. This conclusion uses the actual schema, without assuming WITHOUT ROWID.
- NOT NULL violations have no defaults to substitute here; CHECK violations abort under OR REPLACE. Neither offers another deletion path. [SQLite conflict semantics](https://www.sqlite.org/lang_conflict.html).
- `PRESERVED = {}` is correct: 0015 changes no table data or columns.
- Adding `keep_shop` gives **14 guard lines**. The [README checklist](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:215) matches the current report, including the overridden check.
- No unnecessary abstraction or removable trigger found.

**Independent verification:** 296 refusal cases on **each** of SQLite 3.46.1 and 3.53.1, across all four pragma combinations, with complete database dumps unchanged after every refusal. In-memory adaptations of the actual migration/rehearsal logic passed populated 0012→0015, isolated 0014→0015, transactional rollback on injected 0015 failure, and missing-trigger detection at head. Actual shop writer functions, the profile UPDATE, and zero-credit restore-style creation remained compatible.

**Adjacent scope:** sessions remain replaceable: replacing an existing token hash can change its `shop_id` with foreign keys enabled ([schema](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0005_api_sessions.py:15)). That predates this diff and merits separate identity-hardening work; these shop guards make no broader guarantee.

Not checked: SQLite 3.40.1, filesystem/WAL behavior, full pytest suite, CLI/API end-to-end flows, browser/device or deployment checks. No files changed; excluded resources were untouched.  
Release risk: the release-image rehearsal remains required; reported implementer counts remain unverified.