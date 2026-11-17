**REJECT — one P1 remains.** The four round-2 findings are closed in their original scope.

| Round-2 finding | Ruling |
|---|---|
| 1. Release erases another shop’s request | **CLOSED** — writes now touch separate keys. |
| 2. Busy retry removes `memoryOnly` | **CLOSED** — persistence bookkeeping runs only after admission. |
| 3. U+0085 concession divergence | **CLOSED** — collapsed text is always used. |
| 4. Oversized concession | **CLOSED** — truncation always precedes `-geste`. |

**P1 — An older response can still erase a newer unanswered request for the same shop.** [admin.ts:199](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:199), [Admin.vue:218](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:218).

`release()` compares the stored request and removes its key in separate operations. This interleaving remains possible:

1. Tab A starts releasing request **R** and reads the key containing R.
2. Tab B resolves that same R, removes its key, then successfully admits and sends confirmed request **S**.
3. Tab A resumes and removes the key, now containing S.
4. Tab B’s `shared()` handler deletes S from memory because storage no longer contains it.

S is then lost from both copies. If S committed but its response and history read fail, reopening the shop creates a fresh offered reference; repeating the intended grant can credit it again.

This requires a narrow scheduling interleave, but **S is admitted after R resolves**: it does not require the accepted simultaneous-admission race. Web Storage provides no guaranteed cross-window lock for this comparison/removal. [HTML standard](https://html.spec.whatwg.org/multipage/webstorage.html#introduction-16)

**Concrete fix:** serialize `keep()` and `release()` under the same cross-tab lock per shop, covering the complete read/check/write or read/check/remove operation. Release the lock before HTTP. Add a controlled regression proving that an older release cannot delete a newly admitted request.

I reproduced this with the actual `keep()`, `settle()`, `release()` and `shared()` functions using an in-memory store.

Other requested checks:

- Odd suffix values (`03`, `3.0`, `1e2`) are ignored; canonical keys supply any loaded request.
- The old `affiche.admin.pending` map is ignored and left untouched; its requests are **not migrated**.
- Changing enumeration can temporarily omit a request from memory. Its stored key survives, admission still returns `busy`, and the subsequent removal event restores it. That probe did not establish persistent loss or a second POST.

No files changed. Suites, builds and browser/device checks were not rerun; your reported passes remain the validation evidence.  
The P1 timing was demonstrated by controlled interleaving, not reproduced in a browser; prohibited paths and production/deployment commands were untouched.