# « Partager » on real phones — test sheet (T-SHARE-005, D-SHARE-005)

Filled by the owner **after the release, on the live site** `https://affiches.miorantsoa.app` (ADR-121), with any
phone, on a poster whose final image is already confirmed: no new image, nothing paid. (Before the release it could
be done over USB, `adb reverse`, with stub data: D-SHARE-005.) Each failure becomes its own follow-up task
(T-SHARE-006 …), using the table « Result → Follow-up » at the end of D-SHARE-005 in `designs/share-poster.md`.
The invitations to new shops wait for rows 1 and 3 (deploy/README.md).

**Phone:** _model_ · Android _version_ · Chrome _version_ · Facebook _version_ · Facebook Lite _version_ ·
WhatsApp _version_ · WhatsApp Business _version_

For every row, before you tap: type a caption with **two lines and an emoji** (for example `Galaxy A15 128 Go` /
`Livraison à Tana 📦`) and add a **number at the end** (`#1`, `#2`, …) that changes at each tap: it tells which tap
the pasted caption came from.

| # | Combination | « Partager » shown? (or the sentence) | Image in the composer whole and sharp? | Who posts (Page / person) | Caption pasted: right number, line breaks, emoji? | What the page shows on return | Works a 2nd time? | Screenshot(s) |
|---|---|---|---|---|---|---|---|---|
| 1 | Chrome → Facebook, switched to the Page first | | | | | | | |
| 2 | Chrome → Facebook Lite | | | | | | | |
| 3 | Chrome → WhatsApp | | | | | | | |
| 4 | Chrome → WhatsApp Business | | | | | | | |
| 7 | The address opened from a Messenger message to yourself (in-app browser: which?) | expected: no « Partager », a sentence | Does « Télécharger » work there? | — | — | Opening in Chrome: asked to sign in? | — | |
| 8 | Close the share sheet without choosing an app | expected: nothing shown | — | — | — | | « Partager » works again? | |
| 5, 6 | iPhone, Safari → Facebook; → WhatsApp | only if an iPhone is at hand: _no iPhone_ | | | | | | |

Do not publish anything: stop in each composer before « Publier » / « Envoyer », except for the Messenger message
to yourself in row 7.

## Notes

_Anything surprising: a delay, a crop, a sentence that did not make sense, the clipboard holding the wrong caption._
