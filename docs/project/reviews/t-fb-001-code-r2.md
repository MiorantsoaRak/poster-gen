# Code review r2 — T-FB-001: settings, migration 0018 and the Graph client

Reviewer: Codex, read-only, 2026-11-21. Verdict: REJECT (nine of the ten round-1 findings closed; three remaining P1, each one small). Answered in the code the same day; see r3.

### Round‑1 rulings

| # | Severity | Ruling | Evidence |
|---|---|---|---|
| 1 | P1 | CLOSED | `facebook.py:202` validates the OAuth code before form encoding. A lone surrogate returns `GraphFailure("invalid")` with zero sends. |
| 2 | P1 | CLOSED | `facebook.py:180–189, 225–237` returns failure values for timeouts, transport errors and malformed accounts responses. Those paths expose no traceback. |
| 3 | P1 | CLOSED | `facebook.py:145` requires a 4xx before a Graph error can produce `failed`. Tests cover 202/190 and 307/506. |
| 4 | P1 | PARTIAL | `facebook.py:73–89` handles all three reported cases: duplicate keys, nonstandard constants and excessive nesting. Malformed wire bytes can still produce `published`, as detailed below. |
| 5 | P1 | CLOSED | `facebook.py:103–107, 187, 256` filters `fbtrace_id` against the call’s credentials before logging or returning it. Tests cover reflections and a genuine trace. |
| 6 | P2 | CLOSED | `facebook.py:172–173` sets `trust_env=False`. The test inspects the client options for all four calls. |
| 7 | P2 | CLOSED | `facebook.py:226–229` checks every task on every Page before filtering for `CREATE_CONTENT`. |
| 8 | P2 | CLOSED | `0018_facebook.py:37` declares `id TEXT PRIMARY KEY NOT NULL`. The migration test covers an omitted ID. |
| 9 | P3 | CLOSED | `config.py:117` requires printable, non-whitespace ASCII for the app ID under `meta`. |
| 10 | P3 | CLOSED | `facebook.py:196–197` sends both exchanges as POST forms to a fixed address. The GET exchange branch is gone. |

### Remaining defects

- **P1 — Malformed UTF‑8 can produce `published`.** `_json` passes raw bytes to `json.loads`, whose byte decoder uses `surrogatepass`. An HTTP 200 with a matching `post_id` and raw bytes `ED A0 80` inside another string therefore reaches the `published` branch. Decode the body as strict UTF‑8 before `json.loads`. The existing `ValueError` handler will turn the decoding failure into `unknown`. [facebook.py:87](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:87)
- **P1 — Invalid photo arguments can expose the Page token through an exception.** A lone surrogate in `page_token` reaches `_proof` and raises `UnicodeEncodeError` carrying the token. Independently, the existing invalid-Page-ID test expects a `ValueError` from a frame already holding the token and multipart form. Validate both arguments before computing the proof and return a constant pre-send failure, as the caption guard already does. [facebook.py:248](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:248)
- **P1 — Numeric credentials can still reach the log.** A digits-only OAuth code passes validation. If a malformed error reflects it as an integer `error_subcode`, `_graph_error` retains it and `_log_answer` prints it. The same path exists for the integer `code` field. Apply the credential check to the decimal rendering of both fields before logging or returning them. Treat a reflected primary error code as unreadable. [facebook.py:103](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:103)

Routes belong to T‑FB‑002/003. T‑FB‑003 owns the 30‑second pre-send clock and caption validation at admission. The client’s lone-surrogate caption guard correctly returns `failed` before building a request.

Read-only source review. The 253 targeted passes were reported by the implementer. The full suite is uncounted.

**REJECT**