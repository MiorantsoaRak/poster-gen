What this change does: adds operator-session storage, password rotation and session-revocation commands, plus restore instructions.

**Verdict: APPROVE WITH FIXES.** One P2 documentation finding; no P1 or P3 findings.

1. **P2 — Missing logs cannot prove a stolen session was unused** — [deploy/README.md:475](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:475).

   A shop password reset can commit, then lose its journal line when the process stops. That creates no credit-ledger entry either. Following the shortcut—only pausing generation and rotating the operator password—leaves the attacker’s shop password and any shop sessions usable.

   **Smallest fix:** remove the shortcut based on absent journal/ledger entries. When use cannot independently be ruled out, require the full compromise procedure, including ending shop sessions and resetting potentially affected shop passwords. The approved design contains the same shortcut and needs the corresponding correction.

The implementation checks out on inspection:

- **Password handling:** generated internally, hashed before the transaction, printed once after commit. Neither password nor hash enters argv. SQLAlchemy failures print the driver error without bound parameters. Current HTTP code exposes no arbitrary `meta` writer or reader.
- **Transactions:** the upsert and operator-session deletion commit together. The injected deletion-failure test meaningfully checks rollback and empty stdout. `BEGIN IMMEDIATE` serializes this command with API writes; hashing outside it avoids holding the write lock during Argon2. The future sign-in race check correctly belongs to T-ADMIN-002.
- **Migration:** 0001–0015 are unchanged. Revision linkage, schema and `PRESERVED`/`ADDED` match the design; fourteen rehearsal guard lines remain. The new SQL uses no feature newer than SQLite 3.40.
- **Restore:** migration runs before `end-sessions --all`, so a backup lacking `operator_sessions` gets the empty table before deletion. The existing pre-0013 restore test exercises that command sequence. Pinning the dedicated 0015 test to `migrate_to(..., "0015")` preserves its original purpose.

**Docker output:** `compose run --rm operator` inherits `logging.driver: none`; Docker does not persist its stdout through the container logging driver. `--rm` alone would not provide that protection. The fake docker records invocation details, not generated passwords. [Docker logging documentation](https://docs.docker.com/engine/logging/configure/), [Compose run documentation](https://docs.docker.com/reference/cli/docker/compose/run/).

`docker exec` attaches separate output streams to its client; the engine’s command events contain argv, which contains no generated secret here. External terminal recording, redirection or configured sudo output capture can still retain stdout. [Docker engine implementation](https://github.com/moby/moby/blob/master/daemon/exec.go).

**Deviation rulings:**

1. **Accept:** two output lines preserve once-only disclosure after commit.
2. **Accept:** the changed `--all` message accurately reports both session groups; inspected callers do not parse the old wording.
3. **Accept:** the dated build-status note explicitly identifies the page, journal and verification checks as forthcoming. Those first-deploy steps are not executable today.
4. **Accept:** the sole production caller supplies a freshly generated Argon2 hash; additional validation is unnecessary for this task.
5. **Accept:** the automated HTTP non-write proof is explicitly assigned to T-ADMIN-002.

Read-only checks passed: changed Python files parse, `sh -n deploy/restore.sh`, and scoped `git diff --check`. No files changed; excluded paths remained untouched.

Not checked: pytest/mutations, real Docker/journald, deployed behavior or SQLite 3.40 execution; reported suite counts remain unverified.  
Remaining risk: fix the compromise shortcut before relying on this runbook.