# Code review r5 — T-FB-001 after its rewrite on another principle

Reviewer: Codex, read-only, 2026-11-21. Verdict: REJECT, with this finding first: "The module's own log records and `GraphFailure` fields follow the principle." Four gaps in how the principle was applied (the post id gated in two parts and not whole; a Page's name not compared with the other Pages' tokens; an error of the HTTP client that could leave the module; two untyped arguments). All four are closed in the code, each with a test; that version has not been reviewed again.

The module’s own log records and `GraphFailure` fields follow the principle. Two returned fields and two exception paths still bypass it.

| Severity | Destination | Finding |
|---|---|---|
| **P1** | `Outcome.post_id`, `Outcome.link`, and their `repr` | `_kept` checks the two digit strings separately. The underscore makes the assembled post ID a possible `credential()` value. A complete sent credential spanning that underscore survives both checks and appears verbatim in both fields. The assembled value passes neither gate. [facebook.py:147](backend/src/affiche/posters/facebook.py#L147) |
| **P1** | `Page.name` and `repr(Page)` | `_kept` receives only the current row’s Page token, user token, proof and app secret. If one Page’s name contains another Page’s access token from the same answer, the complete second token survives, including when that second Page is filtered out by `tasks`. The name passes the shape check but bypasses the credential check for that token. [facebook.py:235](backend/src/affiche/posters/facebook.py#L235) |
| **P2** | Request address and exception | The installed `httpx2` builds `response.next_request` from `Location` even with redirects disabled. That unsent address can contain raw response text. A relative location within the URL length limit can exceed it when joined to the base URL. The resulting `InvalidURL` escapes both callers with credentials in traceback locals. `Location` passes neither gate. [facebook.py:174](backend/src/affiche/posters/facebook.py#L174) · [redirect construction](backend/.venv/lib/python3.12/site-packages/httpx2/_client.py#L1890) · [unguarded join](backend/.venv/lib/python3.12/site-packages/httpx2/_client.py#L515) |
| **P2** | Exception | A non-string caption such as `None` raises `AttributeError` at `.encode()`. A malformed `png` such as `None` reaches the multipart reader and can also raise `AttributeError`. Both arguments bypass type validation, and the escaping traceback retains `page_token`. [facebook.py:253](backend/src/affiche/posters/facebook.py#L253) · [facebook.py:260](backend/src/affiche/posters/facebook.py#L260) |

**Remaining destinations.** The application logger receives fixed call names, kinds, status classes, diagnostic phrases and selected `KNOWN_CODES`. `GraphFailure.kind/code` and `Outcome.status/error_code/reconnect` likewise use constants or values derived solely from them. `Page.id/name` pass `_kept` subject to the gap above. `Page.token` and returned exchange tokens pass `credential()`, and `Page.token` is omitted from `repr`. Sent request addresses use fixed endpoints, the accepted HMAC query parameter, or a Page ID checked directly against `DIGITS`. The stub uses that same digit check plus a generated suffix for its outcome. Neither digits-only ID can itself be an accepted credential. Parser and caption encoding exceptions can transiently contain input and are caught. [facebook.py](backend/src/affiche/posters/facebook.py)

**§4.** The ordinary rows match, including an unlisted code settling `unknown` with no retained code. The credential-bearing 200 above incorrectly settles `published`; the redirect exception escapes before settlement.

**Prior rounds.** The post-link, Page-metadata and credential-bearing traceback findings remain reachable through the paths above.

Read-only source review. I ran no tests and excluded the pending full suite.

**REJECT**