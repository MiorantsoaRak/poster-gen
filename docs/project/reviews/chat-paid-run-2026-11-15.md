# Creation by message: first real poster and the read-back measurement — 2026-11-15 (T-CHAT-005)

## One real poster through the chat

**What was run:** `outputs/chat-paid-2026-11-15/serve.py` and `run.py` (git-ignored, with the screenshots), on the Linux machine: the production build and the API on loopback, the paid data folder `backend/data-probe`, the pilot's image model (`gpt-image-2.5-flare`, medium) and the Claude reader. A scripted Chromium at 390 × 800 signed in, attached one product photo, wrote one message, tapped the recap, then asked for one scene change. Nobody approved the versions: both are left « à vérifier » in `data-probe` (poster `1375a1df-bbaa-4380-83f9-f89de37b8f48`).

| Step | Result | Delay | Cost (ledger) |
|---|---|---|---|
| « JBL Tune 770NC noir, 350 000 Ar, style sombre » + one photo | recap with the name, 350 000 Ar and the style | 2.9 s | USD 0.0025 |
| « Créer l’affiche » | version 1: title « JBL Tune 770NC noir », price « 350 000 AR », dark scene with gold lines | 19.6 s | USD 0.0277 |
| « mets un fond bleu nuit avec des reflets » | change card « Mettre un fond bleu nuit avec des reflets » | 2.4 s | USD 0.0028 |
| « Créer » | version 2: same product and words, night-blue scene; the list reads « Modifications (2) » | 23.5 s | USD 0.0395 |

Total on the ledger: **USD 0.0725**. The server was stopped by the PID of its ports afterwards.

**Seen by Claude on the two images:** the title and the price are exact in both; the product keeps its shape and its JBL mark; nothing else is written.

**A real defect of the test data, and what it shows:** the photo is the purple headphones and the message says « noir ». The poster shows purple headphones under the title « … noir ». The reader never sees the images, so the chat cannot notice a photo that contradicts the words; the owner's check (photo beside image, in the review) is the only guard, as in « Pas à pas ». Not fixed; a requirement of Draft v1 (« An attached photo conflicting with the supplied product facts requires resolution ») was dropped with the web search and this is its remainder.

**Not covered by this run:** a real phone and its keyboard; the review, approval and download with real images; a price change; an inspiration image; two tabs; anything on the hosted pilot.

## Can the model read back the drawn price? (offline, no product code)

**What was run:** `outputs/price-readback-2026-11-15/measure.py`: 14 existing scenes of `data-probe` whose price was drawn, each sent to `claude-sonnet-5-5` with one question (the price as written, and every piece of text). Direct study calls, **outside the ledger**: USD 0.0806 (about USD 0.0058 and 3.4 s per image).

**Result:** 14 of 14 prices read exactly (« 350 000 AR », « 190 000 AR », « 340 000 AR »). The list of texts was right on the titles, the contact and the shop name; on one image the brand line « CMF by Nothing » came back as « CMF by NöthinG » and on another it was missing.

**What this does not show:** every one of the 14 prices was drawn right, and there are only three different amounts. The sample has no wrong price, so it says nothing about the case the check exists for: catching a wrong digit. The devil's advocate's objection (after one true warning, silence reads as "checked") is not answered by this either.

**Recommendation:** do not build the read-back now. It reads right prices reliably at about half a cent, so it is cheap to add later; before building it, make a handful of deliberately wrong prices (a script that draws them, no image model needed) and measure whether it catches them. Listing every text could also catch an invented line, the failure actually seen on 2026-11-12.

## Spend of the whole feature (2026-11-14 and 15)

| | USD |
|---|---|
| Reads, two evaluation runs (ledger) | 0.138 |
| Diagnostic calls for the reasoning-block failure (outside the ledger, estimated) | 0.05 |
| One poster and one change through the chat (ledger) | 0.0725 |
| Read-back measurement (outside the ledger) | 0.0806 |
| **Total** | **about 0.34** |
