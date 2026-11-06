**Verdict: APPROVE.**

1. **CLOSED — Cleanup disabled before startup finished.** [runtime.py:113](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/runtime.py:113>)

   Previously, a logging exception could leave the engine and lock alive when the traceback was retained. Logging and `Runtime(...)` construction now remain inside `ExitStack`; `pop_all()` occurs immediately before returning.

   The regression at [test_store_lock.py:206](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_store_lock.py:206>) exercises a real delayed `FileHandler` failure, retains `_caught`, delegates to the real `Engine.dispose`, asserts exactly one disposal, and checks immediate lock reacquisition. This addresses the original failure scenario. No further fix required.

2. **CLOSED — Subprocess teardown raced the stdout reader.** [test_store_lock.py:36](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_store_lock.py:36>)

   Previously, exiting `Popen` could close stdout while its reader thread still needed it. All three subprocess tests now invoke `_reap()` from `finally` before leaving `Popen`. It kills/waits for the child and consumes the queue through `None`, with timeouts.

   The inspected `_stdout_lines()` publishes `None` only after finishing stdout iteration, so this synchronizes the relevant resource access, including assertion-failure cleanup. No further fix required.

**New actionable defects introduced by r2: none found.** Both inspected files match the supplied diff.

**Validation:** The requested pytest command failed to launch with `helper_unknown_error: setup refresh had errors`. No tests ran here; the reported 273 passes, repeated targeted passes, and mutation result were not independently reproduced. No files modified; no network used.