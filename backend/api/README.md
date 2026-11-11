# Pilot HTTP contract

Implemented: original uploads, immutable inputs, shop identity, versioned drafts/history/copies, durable jobs/combined spending, fixed or Claude scene plans, GPT scene integration/refinement, fidelity review and owned generated assets. Constrained text proposals and separately requested material effects are implemented. Feed PNG rendering, final confirmation and immutable downloads are implemented. The API scheduler starts automatically under the exclusive API process lock.

The executable OpenAPI contract is generated from `affiche.api.create_app()` and served at authenticated `GET /api/openapi.json`. `tests/test_api.py` exercises the real ASGI app against temporary SQLite/files, with no remote providers or Postman workspace dependency. Run from `backend/`:

```powershell
uv run pytest tests/test_api.py tests/test_poster_drafts.py -q
```

Configure the server-only `APP_ORIGIN` and `SHOP_PASSWORD_HASH` variables listed in `.env.example`, alongside the existing required spend cap/date. The CLI does not require these HTTP settings. Generate an Argon2 hash locally without putting the password in shell history:

```powershell
uv run python -c "from getpass import getpass; from pwdlib import PasswordHash; print(PasswordHash.recommended().hash(getpass('Shop password: ')))"
uv run python -m affiche.api
```

The server binds `127.0.0.1:8000`, uses one process, and ignores forwarded client headers. For development, the Vite proxy forwards `/api` and preserves the configured browser Origin (`http://127.0.0.1:5173`). Hosting/proxy setup is separate: HTTPS and an exact trusted proxy policy are required before exposure. Never run this development entry point as a public unauthenticated file server. Existing data folders retain their provider mode and ledger.

Every mutating request requires `Origin: <APP_ORIGIN>`. Authenticate with `POST /api/session {"password":"…"}`; retain the HttpOnly, SameSite Strict cookie. HTTPS origins use Secure cookies. `GET /api/session` reports authentication state; `DELETE` revokes the session. Five failed logins from the actual peer IP in 15 minutes block further attempts, including across server restarts. Staff share one shop and its data.

| Route | Request | Result |
|---|---|---|
| POST `/api/assets` | multipart `file`, `role=original\|logo\|style` | asset hash, MIME, dimensions, low-resolution warning |
| GET `/api/assets/{sha}` | authenticated ownership | original bytes; unknown/unowned/missing → 404 |
| POST `/api/product-inputs` | name, confirmed variant, ordered 1–3 photo hashes, optional facts/replacement | immutable input ID |
| GET `/api/product-inputs/{id}` | owned input | original URLs and confirmed fields |
| GET/PUT `/api/shop-profile` | name/contact/logo hash, nullable | versioned profile; older draft snapshots unchanged |
| POST `/api/creations` | input ID, title/integer MGA price, three identity switches, primary format | draft revision 1 |
| GET/PUT `/api/creations/{id}` | full validated application document on PUT | current/new revision and ETag |
| GET `/api/creations` | `limit<=50`, opaque `before` cursor from response | newest first, next cursor |
| GET `/api/creations/{id}/versions` | `limit<=50`, integer `before` revision | immutable revision list |
| GET `/api/creations/{id}/versions/{revision}` | exact revision | saved document |
| POST `/api/creations/{id}/copies` | source revision, reason; replacement input or conflict document when applicable | linked new draft, no generation |
| POST `/api/creations/{id}/abandon` | no body or `{}` | read-only draft; active image job blocks abandonment |
| GET `/api/jobs/{id}` | owned job | status, result ID, safe error code, recorded cost/estimate flag; no prompt/source body |
| POST `/api/jobs/{id}/cancel` | no body or `{}`, Idempotency-Key | queued job only; releases unsent reservation |
| GET `/api/capabilities` | authenticated | configured provider availability and estimates; no credentials |
| GET `/api/creations/{id}/jobs` | owned creation | latest 50 jobs, active first, allowing reload recovery |
| GET `/api/usage` | authenticated | combined legacy/poster recorded micro-USD, cap and start date |
| POST `/api/creations/{id}/plans` | If-Match; mode=fixed or claude, direction, format | 201 fixed plan or 202 queued planner job |
| GET `/api/plans/{id}` | owned plan | immutable plan, source, origin revision |
| POST `/api/plans/{id}/revisions` | If-Match; scene/product_region/overlay_regions/palette | new manual plan bound to current revision |
| POST `/api/creations/{id}/scenes` | If-Match; plan_id, format, acknowledged_warnings, optional style_reference_asset, optional headline `{brand, subtitle, accent_word, accent_colour}` (all nullable) plus `signature` (boolean, ADR-043: also draw the included shop name/contact from the profile snapshot; one line each, at most 80 characters; stale or removed drawn words give 409 `signature_missing`) | 202 job; explicit low_resolution acknowledgement when needed. With `headline`, the image model sets brand, `offer.title` and subtitle in the scene (ADR-042); `invalid_headline` for commercial wording, quotes, a title over 60 characters or an accent word absent from the title. The price is never sent. The first scene hides the title layer; a hidden title needs a selected scene whose recorded headline title equals the offer title, else render/confirm return 409 `title_missing` and refinement 409 `headline_stale`. Visuals expose `headline` (with the exact `title` sent) or null. |
| POST `/api/creations/{id}/looks` | If-Match; `name` (1–40), `reference_asset` (owned `style` asset) | 202 job reported with kind `look`; result_ref is the look id. Claude writes a screened style brief (ADR-046). 503 `planner_unavailable` when the planner is disabled; 409 `look_limit` at 24 looks; job error `invalid_brief` when the answer fails validation |
| GET `/api/looks`, GET `/api/looks/{id}` | none | The shop's saved looks: `{id, name, reference_asset, brief, created_at}`. A scene request uses one with `headline.look_id`; the server reads its typography and alignment, and an unknown or foreign id is 404 |
| POST `/api/creations/{id}/refinements` | If-Match; selected base_visual_id, instruction_fr, format, optional style_reference_asset | 202 job; base retained, result is an alternative |
| GET `/api/creations/{id}/visuals` | owned creation | visuals for its exact immutable product input |
| GET `/api/visuals/{id}` | owned visual | original/generated URLs, fidelity status, provenance |
| POST `/api/visuals/{id}/decision` | action, checks, reasons/note | terminal approve/reject; all six fidelity checks required to approve |
| POST `/api/creations/{id}/text-proposals` | If-Match; format, title/price layer_id, instruction_fr | 202 Claude job; no automatic image call |
| GET `/api/text-proposals/{id}` | owned proposal | exact before/after documents, constrained patch and status |
| POST `/api/text-proposals/{id}/apply` | If-Match; acknowledged_content_change | applies one layer to the unchanged revision; shared content needs explicit acknowledgement |
| POST `/api/text-proposals/{id}/reject` | Idempotency-Key | terminal rejection; current draft intact |
| POST `/api/creations/{id}/text-effects` | If-Match; format, layer_id, applied proposal_id | 202 material swatch job, separately charged and reviewed |
| GET `/api/text-effects/{id}` | owned effect | texture URL, target/revision and status |
| POST `/api/text-effects/{id}/apply` | If-Match | unchanged origin/style required; attach one reviewed effect |
| POST `/api/text-effects/{id}/reject` | Idempotency-Key | terminal rejection; prior text/effect intact |
| POST `/api/creations/{id}/renders` | If-Match; format=feed | 202 local job, duplicate exact render reuses the job; no model charge |
| GET `/api/renders/{id}` | owned render | immutable PNG hash, preview URL/warnings, prior confirmation download if any |
| GET `/api/renders/{id}/preview` | owned render | verified stored PNG bytes |
| POST `/api/creations/{id}/confirmations` | If-Match; render_id, png_sha256, four checks, acknowledged_warning_ids | exact current effective layout/approved scene required; immutable confirmation |
| GET `/api/confirmations/{id}/download` | owned confirmation | the same verified PNG bytes, safe attachment filename and hash ETag |

Style references use the existing asset upload with `role=style`. The optional `style_reference_asset` is an owned SHA-256, never a URL. Missing, corrupt, wrong-role or cross-shop references are refused before spend and rechecked before dispatch. Image order is base (refinement only), original views, then style reference. Visual responses expose `style_reference_asset` separately from `original_urls`; job provenance retains its immutable hash. Omitting it (or passing null) preserves the previous request and replay contract.

Editor image URLs request `GET /api/assets/{sha}?prepared=true` for upright bounded sRGB PNG copies that preserve alpha. The server renderer uses the same preparation. Original URLs still return the unchanged upload. Build the frontend before rendering (`npm.cmd run build`); install the pinned Playwright Chromium with `uv run playwright install --only-shell --no-remove chromium`. Rendered HTML/JS come only from the trusted dist bundle, all browser network requests are intercepted, and image/font bytes are injected as data. A final PNG is never regenerated on download. Missing/corrupt stored exports return `export_missing` and require restoring their exact bytes.

Text proposal style keys are allowlisted. A new title must match an explicit quoted string in the instruction; a new price must match one unambiguous literal integer Ariary amount. Neither model can edit the scene through this route. Generated material pixels fill locally rendered font glyphs; manual price/font changes reuse the applied texture without calling a provider. Generic saves may reuse applied same-shop effects, but cannot attach proposed/rejected effects.

Text layers and proposal styles accept `font_id: "montserrat-black-italic"` with `weight: 900`; Noto IDs require 400/700. Only price layers accept `price_badge: {fill: "#FFFFFF", border_start: "#009FE3", border_end: "#1853BD"}`; null removes it. The exact grouped amount and smaller upright `AR` share one editable capsule. Null badge is omitted from saved documents, preserving old hashes. Invalid font/weight pairs, badge roles and colours are rejected; manual changes cause no provider call.

All mutations except uploads and session actions require a UUID `Idempotency-Key`. PUT and abandon also require a strong `If-Match`, such as `"2"`. Missing revision → 428; stale → 409 with `error.current_revision`. Replay with the same key, body and revision returns the original result, even if the current revision changed; reusing a key for another request → 409. Failed mutations do not consume the key. Uploads deduplicate by content hash.

Prices are JSON integers from 0 through 9,007,199,254,740,991, never strings, floats or booleans. Unknown properties and canvas-library objects are rejected. Text layers bind title/price/shop roles; there is no second free-form price string. Originals remain byte-identical; colour validation never runs cutout/rembg. Accepted files: static JPEG/PNG/WebP, at most 10 MiB and 40 million pixels. JSON requests are capped at 128 KiB; multipart overhead is separately bounded, including requests without Content-Length.

All errors use `{error:{code,message_fr,retryable,field?,current_revision?},request_id}`. Responses have `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and a server-generated request ID. Passwords, original bytes, commercial information, SQL and filesystem details are never echoed in error payloads/logs. Persisted sessions contain token hashes only. Storage failures return 503 and preserve earlier committed versions.

References checked during implementation: [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) and [file uploads](https://fastapi.tiangolo.com/tutorial/request-files/). Installed FastAPI 0.162.2, Starlette 1.10.0, pwdlib 0.3.1 and Uvicorn 0.54.0 signatures were checked; the uv lockfile pins dependencies. Cookie sessions intentionally follow the approved local contract rather than the tutorial's JWT example.
