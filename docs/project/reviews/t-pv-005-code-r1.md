**Verdict: APPROVE WITH FIXES.** Two P2 findings.

1. **P2 — Cleanup is disabled before startup finishes.** [runtime.py:113](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/runtime.py:113>)

   `pop_all()` runs before `log.info()`. After recovery, a logging handler can raise—for example, a delayed `FileHandler` cannot open its destination. `start()` then fails without disposing the engine or closing the lock. Retaining the exception traceback keeps the lock alive, blocking another start.

   **Fix:** Keep logging and `Runtime` construction inside the `ExitStack`; call `pop_all()` immediately before returning. Add a regression with logging raising and `pytest.raises(...) as _caught`.

   **Evidence:** An in-memory probe produced **0 lock closes and 0 engine disposals**.

2. **P2 — Subprocess teardown races the stdout reader.** [test_store_lock.py:133](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_store_lock.py:133>) — also the two preceding subprocess tests.

   `_stdout_lines()` starts a reader thread, but these tests discard its queue after the readiness message. `worker.wait()` waits for the child, not that thread. If the reader is descheduled after publishing `"ready"`, leaving the `Popen` context closes stdout before its next read, producing an intermittent `PytestUnhandledThreadExceptionWarning`.

   **Fix:** Retain the queue and consume its `None` EOF sentinel before leaving `Popen`, including failure cleanup after killing/waiting. The existing `test_db.py` already uses this synchronization.

   **Evidence:** A controlled in-memory scheduling probe reproduced **`ValueError: I/O operation on closed file`**.

Keep the 2-second retry, `seek(0)`, owner-wide running-call recovery, first-kind-wins insertion, and `_caught` bindings. No substantial deletion is warranted. For T-PV-009, retain the complete `Runtime` throughout the command. The known concurrent Windows `put` failure remains a follow-up before simultaneous API/CLI use.

**Validation:** The requested pytest command could not start: the shell launcher returned `helper_unknown_error: setup refresh had errors`. The two probes ran separately; **no pytest tests are counted as passing**, and the reported 272 passes were not independently verified. No files modified; no network used.