# REQUIREMENTS — Publish a poster on the shop's Facebook Page

**Status:** v2: v1 amended the same day by what the proofs showed (each amendment is marked in its bullet); **the amendments approved by the owner on 2026-11-21 ("yes to all")**, as is the permission `business_management`. v1 was **approved by the owner on 2026-11-21** ("yes stage 1, free, only link to the post"; ADR-127), after his question "Can we start to see how we can add the feature to publish on a page?". Stage 1 only. The design is next; the three proofs below gate the implementation, not the design.

**Sources:** the [research of 2026-11-15](../reviews/social-publishing-saas-research-2026-11-15.md) and its [review](../reviews/saas-review-claude-2026-11-15.md); the owner's Meta app « Doka studio », read on 2026-11-21 (not changed); Meta's developer documentation, searched the same day (links at the end).

## What was found

- **The Meta app today:** use case « Tout gérer sur votre Page » (Pages API) with Facebook Login for Business; not published (« Non publiée »). Ready for test: `pages_show_list`, `business_management`, `public_profile`. **Not yet added: `pages_manage_posts` and `pages_read_engagement`**, the two that posting needs.
- **Who can use it without Meta's review:** only people who have a role on the app (administrator, developer, tester). Meta calls this Standard Access. A shop whose Page admin has no role needs Advanced Access: Meta's Business Verification, then App Review, permission by permission. The dashboard already offers « Devenez Fournisseur de technologies » for that.
- **How a photo is posted:** `POST /{page-id}/photos` with the Page's own token, the image sent as a file (`source`) or by a public address (`url`), and its text. A Page token made from a long-lived user token has no expiry date, but Meta can cancel it (password change, role removed, permission taken back).
- **What the app already has:** « Partager » makes one JPEG of the confirmed file and keeps a caption per poster (D-SHARE-002 to 004). Publishing can send that same file and that same caption.

## Proposed scope: two stages

**Stage 1 — Shops that have a role on the app (no Meta review).** The pilot shop and the invited ones. Each Page admin is added as a tester of the Meta app once, by the operator.
**Stage 2 — Any shop.** Needs Meta's Business Verification and App Review. Not designed here. Its largest unknown (2026-11-15, still open): whether a business registered in Madagascar passes the verification, and with which documents.

## R-FB-PUBLISH-001 — Connect the shop's Page, once
- **Story:** As a shop owner, I connect my Facebook Page once, so that I can publish a poster without leaving the app.
- [ ] From « Mon compte », « Connecter ma Page Facebook » opens Facebook's own dialog. The owner signs in there, never in the app, and allows his Pages; back in the app, he chooses one of them by name. *(Amended 2026-11-21: the proof showed that a person allows several Pages in Facebook's dialog.)*
- [ ] The app shows the connected Page's name, and « Déconnecter ». One Page per shop. *(Amended: no picture.)*
- [ ] The Page's access is kept on the server, never sent to the browser, never written to a log, and a copy of the database alone cannot use it. The Meta app's secret is in the server's environment only. *(Amended: « encrypted » replaced; Meta's own « app secret proof » does this without a key that can be lost.)*
- [ ] A Page that belongs to a business portfolio can be connected. *(Added: it needs the permission `business_management`.)*
- [ ] A shop without a role on the Meta app is told so in plain words, with what to ask the operator. Nothing fails silently.

## R-FB-PUBLISH-002 — Publish a confirmed poster
- **Story:** As a shop owner, I publish the poster I have just confirmed on my Page, with its text.
- [ ] « Publier sur ma Page » is offered beside « Partager », only for the poster's confirmed file: the file that is published is the file that is downloaded.
- [ ] The text is the caption of « Partager », shown and editable before publishing. No text is invented.
- [ ] Before anything is sent, one confirmation names the Page and shows the image and the text. After it: « Publié », with a link to the post on Facebook.
- [ ] Publishing costs no credit.

## R-FB-PUBLISH-003 — Never twice, never unknown
- **Story:** As a shop owner, I never find the same poster published twice, and I always know whether it was published.
- [ ] One tap makes at most one post, whatever the network does (a second tap, a reload, a lost answer).
- [ ] When Facebook's answer is lost, the app says the outcome is unknown, gives the way to the Page, and the owner says whether the poster is there. Until he has, the app offers no new publication of that poster on that Page. It never publishes again by itself. *(Amended: the app does not look by itself; a match by time and text can be wrong both ways.)*
- [ ] Each poster shows its publications: when, on which Page, the link. A post removed on Facebook keeps its line; its link then leads to Facebook's own « not available ». *(Amended: no « removed » state in stage 1.)*

## R-FB-PUBLISH-004 — When Facebook says no
- **Story:** As a shop owner, I am told what to do when publishing cannot be done.
- [ ] Access cancelled, role removed, permission taken back: « Reconnectez votre Page », and no retry by itself.
- [ ] Facebook unreachable or its limit reached: the poster and its file stay available; « Partager » and « Télécharger » still work.
- [ ] A suspended shop or one that has not accepted the conditions cannot publish.

## Out of scope for stage 1
Instagram; several images in one post; scheduling; comments and statistics; editing or removing a post from the app; shops without a role on the Meta app (stage 2); a caption written by the AI.

## To prove before the design (free, needs the owner's hands on the Meta app)
1. **A post made while the Meta app is not published:** who sees it? Meta's rule has been that only people with a role on the app do. If so, the Meta app must be published (« Publier », which needs a privacy policy address) before stage 1 is of any use.
2. **The tester role:** what a Page admin must do to accept it (a Meta developer registration may be asked).
3. **One real post** of a confirmed poster's JPEG on a test Page through `POST /{page-id}/photos` with the file itself: the answer's ids, the post's link, and whether Facebook adds an « AI info » label to it.

## Decided by the owner (2026-11-21)
1. Stage 1 as written: shops with a role on the Meta app. Stage 2 only after it works.
2. Publishing takes no credit.
3. Stage 1 shows the link to the post. It does not remove or edit a post (Meta's review for stage 2 will ask to see create, edit and delete: stage 2's matter).

## Sources (Meta, read 2026-11-21)
[Pages API](https://developers.facebook.com/documentation/pages-api) · [Posts](https://developers.facebook.com/documentation/pages-api/posts) · [Access levels](https://developers.facebook.com/documentation/development/graph-api/overview/access-levels) · [App roles](https://developers.facebook.com/docs/development/build-and-test/app-roles) · [Business Verification](https://developers.facebook.com/docs/development/release/business-verification) · [Access Verification](https://developers.facebook.com/docs/development/release/access-verification/) · [Long-lived tokens](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/) · [Facebook Login for Business](https://developers.facebook.com/docs/facebook-login/facebook-login-for-business/)
