# Code review r2 — T-FB-009: publishing a Facebook post of one or several posters (the server part)

Reviewer: Codex, read-only, 2026-11-21. Verdict: APPROVE WITH FIXES (nine of ten closed; one sentence partial). The sentence is fixed; not reviewed again. `hide_parameters=True` found to take nothing from the operator's commands.

Nine items are **CLOSED**. One owner-facing sentence is **PARTIAL**.

| # | Round-one item | Ruling and evidence |
|---|---|---|
| 1 | P1 · SQL exception disclosure | **CLOSED** — `db.py:19` hides bound parameters. `test_db.py:782` checks that failed writes retain the foreign-key diagnostic and expose neither the photo ID nor the Page token. |
| 2 | P2 · Shutdown | **CLOSED** — `api.py:631` starts both drains together. `test_facebook_posts.py:798` holds the single-poster drain and verifies that the uploading post stops without a feed call. |
| 3 | P2 · Upload retry after stop | **CLOSED** — `facebook_posts.py:486` rechecks shutdown, stop, shop, Page and limit before retrying. `test_facebook_posts.py:521` verifies `stopped` at the current position after one request. |
| 4 | P2 · Replay after file refusal | **CLOSED** — `facebook_posts.py:550` waits for a same-key admission and rereads the row before propagating the refusal. `test_facebook_posts.py:446` covers the file-refusal race. |
| 5 | P2 · 30-second cutoff | **CLOSED** — `facebook_posts.py:426` samples the clock inside the write. `test_facebook_posts.py:699` advances it at commit and verifies zero feed calls. |
| 6 | P2 · Inconclusive upload wording | **PARTIAL** — `api.py:215` correctly says Facebook did not confirm the upload. « Rien n’a été publié » still overclaims: the client handles a photo published alone at `facebook.py:192`, and that reply can be lost. Replace only that sentence with « La publication n’a pas été envoyée. » and update `test_facebook_posts.py:518`. |
| 7 | P2 · History on reconnect | **CLOSED** — `facebook_posts.py:225` reads history only for a connected Page. The candidate test at `test_facebook_posts.py:863` checks both fields are null on reconnect. |
| 8 | Test · Simultaneous same-key requests | **CLOSED** — `test_facebook_posts.py:410` holds admission until both requests finish preparation, then asserts one admission, one row, one feed call and the same post ID in both responses. |
| 9 | Test · Cancellation after commit | **CLOSED** — `test_facebook_posts.py:466` cancels the waiting route after the real commit, verifies the row is still owned, and observes it reach `published`. |
| 10 | Test · Stale `seen` after `present: false` | **CLOSED** — `test_facebook_posts.py:362` verifies the old `unknown` status is refused and the refreshed `failed` status is accepted. |

**Operator impact:** `shops.py:321`, `:436` and `:794` use the driver’s original diagnostic. I found no backend refusal or error classifier that needs bound values from SQLAlchemy’s formatted exception.

Read-only review. I did not run tests or count the pending main-checkout suite.

**APPROVE WITH FIXES**