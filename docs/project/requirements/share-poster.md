# REQUIREMENTS — « Partager » a confirmed poster

**Status:** v1, approved 2026-11-18 under the autonomy grant with its **Default** lines in force (ADR-120); two wordings (R-SHARE-001's place of the button, R-SHARE-002's device retention) await the owner's reading (design, Traceability). Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105). Depends on nothing else in the release. Source: the Meta check of the [review](../reviews/saas-review-claude-2026-11-15.md). No design yet. **Its behaviour on real phones is not verified.**

**What exists:** a confirmed poster can be downloaded as PNG. The owner then opens Facebook and attaches the file by hand.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-SHARE-001 | Share from the phone | P0 | Draft |
| R-SHARE-002 | The caption | P0 | Draft |
| R-SHARE-003 | A file made for sharing | P1 | Draft |
| R-SHARE-004 | When sharing is not possible | P0 | Draft |
| R-SHARE-005 | Seen on real phones | P0 | Draft |

## R-SHARE-001 — Share from the phone
- **Story:** As a shop owner, I send my confirmed poster to Facebook or WhatsApp in a few taps, without looking for a file.
- [ ] « Partager » is offered on a confirmed poster, beside the download, in the chat and in the editor.
- [ ] It opens the phone's own share sheet with the poster's image. The owner picks the application; the service posts nothing itself.
- [ ] Only a confirmed version can be shared, and it is the confirmed file, never a new generation.
- [ ] **Default:** one poster at a time.
- **Out of scope:** publishing through Meta's API; scheduling; several posters in one post; a list of what was published.

## R-SHARE-002 — The caption
- **Story:** As a shop owner, I write my text once and paste it where I post.
- [ ] A caption field with line breaks and emoji, kept with the poster.
- [ ] On « Partager » the caption is copied, and the screen says so: « Légende copiée : collez-la dans votre publication. »
- [ ] The caption is not sent with the image through the share sheet (Facebook does not take it; on iPhone it can make the image disappear).
- **Out of scope:** a caption written by the AI; one caption per network.

## R-SHARE-003 — A file made for sharing
- **Story:** As a shop owner on mobile data, the file I share is light and accepted everywhere.
- [ ] The shared file is a JPEG made from the confirmed poster, at its size, with nothing cropped; the confirmed PNG is not changed.
- [ ] Its weight is shown before sharing when it is over one megabyte.

## R-SHARE-004 — When sharing is not possible
- **Story:** As a shop owner whose phone or browser cannot share a file, I am not left with a dead button.
- [ ] Where the browser cannot share files (a computer, an application's built-in browser), « Partager » is replaced by the download and a sentence that says why, with « Ouvrir dans Chrome / Safari » where that helps.
- [ ] A share the owner cancels changes nothing and shows no error.

## R-SHARE-005 — Seen on real phones
- **Story:** As the operator, I know which combinations work before I tell a shop it does.
- [ ] Tried and recorded, with what the owner sees at each tap: Android with Chrome to Facebook (as a Page), Facebook Lite, WhatsApp and WhatsApp Business; iPhone with Safari to Facebook and WhatsApp.
- [ ] What does not work is said in the application for that case, or the button is not offered there.
