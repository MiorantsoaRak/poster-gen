**Verdict: REJECT.** Suspension handling looks consistent with T-005. The restore introduces a data-loss path, and timeout cleanup remains incomplete.

1. **P1 — Repeated restores can overwrite the preserved database.** [restore.sh:15](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/restore.sh:15) chooses a seconds-only timestamp **before acquiring the lock**. Two invocations launched in the same second retain the same destination while waiting. The second [unconditional `mv`:35](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/restore.sh:35) overwrites the original database; it can also leave a mismatched preserved WAL. Allocate a unique preservation directory under the lock and refuse collisions. Add a repeated-restore test.

2. **P2 — A failed asset copy cannot reliably be repaired by rerunning.** [restore.sh:39](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/restore.sh:39) copies directly into final asset paths with `cp -rn`. Disk exhaustion or interruption can leave a truncated file. The documented rerun skips that existing file and can report success with broken posters. Copy missing assets through temporary files and rename after success; test an interrupted copy followed by retry.

3. **P2 — Timeout bounds the Docker client, without ensuring backup-container cleanup.** [release.sh:58](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/release.sh:58) permits a surviving one-off, then restarts the old service and exits, releasing the deployment lock. A later backup can delete the survivor’s partial files ([backup.py:31](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/backup.py:31)); a restore can replace its source database. Give the one-off a known identity and confirm termination before releasing the lock. The fake timeout test only returns an exit code—it never exercises a survivor. The README’s absolute downtime bound also exceeds what client deadlines prove.

Previous findings:

| Finding | Ruling |
|---|---|
| R1 P1: Docker failure bypasses backup | **CLOSED** |
| R1 P2: Restore exposes access before repairs | **CLOSED** |
| R1 P3: Fake misses inner-shell failures | **CLOSED** |
| R1 P3: Quoting | **CLOSED** |
| R2 P1: Password output enters journald | **CLOSED by inspection**; runtime verification outstanding |
| R2 P2: Restore starts after failed repairs | **CLOSED** |
| R2 P3: Unbounded downtime | **PARTIAL** — client deadlines added; cleanup remains incomplete |

The YAML-resolved application service, networks, volumes and project name equal HEAD exactly. The `REVISION` requirement is unchanged. No remaining documented password command uses a logged one-off, and no T-006 implementation leaked in. Reservation release and session preservation match R-MULTI-SHOP-006; restore preservation remains unsafe.

Python AST parsing, shell syntax and scoped whitespace checks passed. No files changed.

Pytest could not run within the read-only constraints; reported results are not independently counted. Real Docker behavior remains unverified, especially timeout survivors and password logging.