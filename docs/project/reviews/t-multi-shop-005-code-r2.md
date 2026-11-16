**Verdict: REJECT.** The backup fix closes the original P1. The restore fixes introduce password logging and still permit startup after failed repairs.

1. **P1 — One-off password commands enter journald.** The [restore helper](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:340) inherits the service’s [journald configuration](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/compose.yml:46). Running `create` or `set-password` through it records the printed password in the journal; `--rm` does not remove journal entries. The recovery example at README:225 has the same problem. Disable container logging for these operator one-offs while preserving their mounts and settings. Python `caplog` tests cannot detect this exposure.

2. **P2 — Restore can restart after repairs fail.** The [restore block](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:341) runs `list`, `end-sessions`, then `docker start` without checking failures. Its `set -e` belongs only to the earlier copy container. With a pre-0013 backup, both shop commands refuse, but the outer shell can still start the service before revocations and suspensions are repaired. Put migration, password preparation and repairs into one checked sequence; allow startup only after success. A shell-only probe confirmed the current fall-through.

3. **P3 — Worst-case downtime is unbounded.** The [backup invocation](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/release.sh:54) and subsequent restart have no deadline. A hung Docker operation or backup never reaches recovery. The five-minute limit covers shutdown only. Document this limit or bound the operation with cleanup and restart handling.

**Previous findings**

| Round 1 finding | Ruling |
|---|---|
| P1: Docker failure bypasses backup | **CLOSED** |
| P2: Restore exposes access before repairs | **PARTIAL** — normal ordering fixed; failure path remains |
| P3: Fake Docker misses inner-shell failures | **CLOSED** |
| P3: `$rc` / `$REV` quoting | **CLOSED** |

**Other checks**

- No ordinary exit-code-3 collision found: the backup CLI returns 0/1/2; missing commands and signal termination use other statuses.
- Returned backup failures attempt the old-container restart before replacement or `up`. `app.new` and the archive remain for retry; partial backups are cleaned by the next backup. Normal script exit releases the advisory lock.
- The one-off helper shares the service’s data and settings and works while it is stopped. The pre-0013 migration command serves nothing; its password fallback is sound when completed before startup.
- Suspension cutoffs, zero-cost reservation release, recovery, ownership and committed-script staging look consistent with T-005. No T-006 leakage found. Keep the combined backup call; simplify restore into one ordered, checked sequence.

Python AST syntax, shell syntax and diff whitespace checks passed. No files changed.

Pytest and real Docker were not run under the read-only constraints; implementer results remain independently unverified. Container logging and restore failure handling need correction before approval.