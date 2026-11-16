**Verdict: REJECT.** Suspension handling looks sound. The release still permits migration without a successful backup.

1. **P1 — Docker failure can bypass the backup.** [release.sh:49](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/release.sh:49) treats every failed database-existence probe as “first deploy,” then reaches `up`, which migrates. `set -e` does not stop failures used as an `if` condition. This is **pre-existing, not an extraction regression**, but retaining it violates R-MULTI-SHOP-005’s mandatory backup and this task’s fail-closed constraint. Combine existence checking and backup inside one container invocation; any Docker failure must restart the old container and abort. Add that failure case to the script test.

2. **P2 — Restore exposes revoked access before repairs.** The runbook [starts the container:312](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:312), then separately instructs the operator to [end sessions and redo suspensions:325](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:325). During that interval, a lost phone’s restored session works, and previously suspended shops can submit calls. Perform revocations, resets and suspension repairs before reopening public service. Document the pre-0013 restore path explicitly.

3. **P3 — Fake Docker proves outer ordering only.** [test_release_script.py:16](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_release_script.py:16) accepts unknown arguments and fails by substring; it never executes the inner `sh -c`. The tests could still pass if that shell swallowed Python’s failure. The current script’s `exec` is correct by inspection, but tighten the fake to validate arguments and exercise inner failure propagation. Also cover backup-probe failure and old-container restart.

4. **P3 — Quoting requirement is incomplete outside release.sh.** The wrapper uses [unquoted `$rc`:242](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/deploy.py:242); new recovery instructions use [unquoted `$REV`:204](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:204). These values are currently constrained, but quote them to meet the explicit rule.

**Verified by inspection**

- Existing release steps retain their order and shared `flock`. The staged script comes from HEAD under a unique run name. Rehearsal failure exits before `docker stop` at line 48.
- Rehearsal uses SQLite online backup of the live WAL database into container `/tmp`, then deletes the temporary directory. It does not accumulate database copies on host disk; tmpfs/memory exhaustion remains possible.
- Dispatch checks suspension and releases only `reserved` calls in one transaction, including retry call 2. Recovery preserves sent-call accounting and spooled results. Every `_ask` path, including stub, crosses `_send`; refused reads become failed at zero cost.
- Operator head checks, hashing outside write transactions, generated-password output, session preservation, `--yes`, and exit codes look correct. No T-006 changes leaked in.

**Declared deviations:** 1, 2 and 5–8 are acceptable. For 3, existence checking and rehearsal share a container; configuration validation is a separate invocation. Both propagate failure. Deviation 4 blocks approval as finding 1.

Python AST syntax, release-shell syntax and diff whitespace checks passed. No files changed. Pytest, mutations, browser checks and real Docker were not run in this read-only review; implementer results remain independently unverified.