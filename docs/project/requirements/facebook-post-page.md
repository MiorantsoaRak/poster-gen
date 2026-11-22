# REQUIREMENTS — A publish page: one Facebook post with several posters

**Status:** v1, 2026-11-21 (Claude), **approved the same day under the owner's autonomy grant, on his own words** (ADR-128): "we can handle the publish page now, no max nb of image, as long as facebook support it; but add the feature for the max nb of image in case we add tier subscription. a post should be publication format only", after "we will have a dedicated button/menu, while clicked, open a publish page where we choose confirmed poster to use, and add the post description" and "Can the image be ordered as the user choose it". The points he did not state are working defaults, listed at the end as his to overturn. The design is next; the proofs below gate the implementation, not the design.

**It adds to** [facebook-publishing.md](facebook-publishing.md) (stage 1, approved, built as T-FB-001 to 004) and changes none of it: the same connected Page, the same Meta app, the same shops (those whose Page admin has a role on the Meta app), no credit taken, the link to the post only. « Several images in one post » leaves that file's « Out of scope ».

**Sources:** the owner's capture of a post of the pilot's Page (2026-11-21); Meta's documentation and third-party guides searched the same day (links at the end).

## What was found

- **How Facebook makes one post of several photos** (Meta's Page Photos reference): each photo is uploaded to `/{page-id}/photos` with `published=false`, which gives an id and shows nothing; then one call to `/{page-id}/feed` with the text and `attached_media[0]`, `attached_media[1]`, … each naming one uploaded photo. The permissions held today cover both calls. **Not tried by us.**
- **The order:** the post lists its photos in that numbered array. The order sent is expected to be the order shown, the first photo leading. Facebook alone chooses the collage's layout, from the number of photos and their shapes. **To prove.**
- **The largest number of photos:** Meta documents none. Publishing tools stop at 10 (Adobe, PostZen) or 4 by their own choice; one report says the API accepts more than 10. So the limit is Facebook's, unknown, and can change: the app has no limit of its own and must say Facebook's refusal plainly when it comes. **To prove, at least up to the number the pilot needs.**
- **What changes from one poster:** today one request makes one call, which is the publication. Here only the last call makes anything public; the uploads before it show nothing. So a failure or a stop before that last call publishes nothing and is safe to say; the unknown outcome can come from that one call only.
- **What the pilot's Page posts today** (his capture): a text of about fifteen lines, with emoji and « bold » made of special letters. The page's description field must take such a text as it is pasted. An editor that makes it is another feature (T-FB-007, not in this file).

## R-FB-POST-001 — A publish page of its own
- **Story:** As a shop owner, I open one page to prepare a post for my Facebook Page, so that I can publish several posters together.
- [ ] The page has a way in of its own, only when publishing on Facebook is on for the service: an entry in the navigation on a desktop; on a phone, whose bar already holds five entries, a button of its own on « Mes affiches » and on Accueil. It is not the final panel's « Partager » or « Publier sur ma Page ». *(Amended by the design, 2026-11-21: no sixth entry in the phone's bar.)*
- [ ] With no Page connected, or a Page to reconnect, the page says so and leads to « Mon compte ». Nothing else is offered.
- [ ] The page names the Page the post will go to.
- [ ] A shop that is suspended or has not accepted the conditions cannot publish; the page says what to do, as a paid control does.

## R-FB-POST-002 — Choose the posters and their order
- **Story:** As a shop owner, I choose which confirmed posters go in the post and in which order.
- [ ] The page offers the shop's posters that can go in a post: those whose current version is confirmed in the « Publication » format (4:5). The image shown for each is its confirmed file, the one « Télécharger » gives.
- [ ] A poster that cannot go in a post is not silently missing: the page says how many are left out and why (confirmed in another format; changed since its confirmation; never confirmed), and what to do for each reason.
- [ ] The owner chooses one poster or several. A poster is in a post once.
- [ ] The order of the post is the order he chose, shown with numbers, and he can move a poster earlier or later and take one out before publishing *(by sliding it, and by the keyboard; amended 2026-11-22, below)*. The first is named as the one that leads the post.
- [ ] He changes the order by sliding a poster up or down in the list, with a finger or a mouse, by a handle at the row's right end; with the keyboard, the handle's arrow keys move it one place. A poster is taken out by a bin icon beside the handle. *(Added 2026-11-22 on the owner's words: "Add drag options to the pictures order so we can order it by sliding it up or down"; then "Put the indicator at the right end of the element, and replace retirer with a trash icon, and remove the two other buttons (plus tot ou plus tard). the action buttons are on the right end". Told to him once: without « Plus tôt » / « Plus tard » there is no way to reorder by a single tap for whoever cannot drag (WCAG 2.5.7); the keyboard still can.)*
- [ ] A poster already published on this Page, alone or in a post, is marked with its date. It can be chosen again, knowingly.

## R-FB-POST-003 — No limit of the app; a limit per shop for later
- **Story:** As the operator, I can set how many images a shop may put in one post, so that a later subscription tier can change it.
- [ ] By default a shop has no limit: the app accepts as many posters as the owner chooses.
- [ ] The operator can set, change and remove a largest number of images per post for one shop. No subscription, price or payment is built here: only the setting and its effect.
- [ ] With a limit, the page says it (« N images au plus par publication ») before the owner reaches it, and does not let him go beyond; the server refuses beyond it whatever the page sends.
- [ ] When Facebook refuses a post for its size or its number of photos, the page says that the refusal is Facebook's, and nothing is published.

## R-FB-POST-004 — The post's description
- **Story:** As a shop owner, I write the text of my post on the page.
- [ ] One description for the post, written on the page, shown as it will be sent. It may be empty. No text is invented or added by the app.
- [ ] The owner can take a chosen poster's caption (the one « Partager » keeps) as a start, by his own action.
- [ ] Line breaks, blank lines, emoji and special letters pasted from elsewhere are sent as typed. The length allowed and the characters refused are said on the page, beside the field, before he publishes.
- [ ] The draft (the chosen posters, their order, the description) survives a reload and a return to the page on the same device, until it is published or he clears it. A post that fails or is stopped leaves it as it was.

## R-FB-POST-005 — Publish: one post, never twice, never half
- **Story:** As a shop owner, I publish the post once, and I always know whether it is on my Page.
- [ ] Before anything is sent, one confirmation names the Page and shows the images in their order and the description.
- [ ] One tap makes at most one post, whatever the network does (a second tap, a reload, a lost answer, another tab).
- [ ] The post is all of the chosen images or nothing: if one image cannot be sent, nothing is published, and the page names that image and what to do.
- [ ] While the images are being sent, the page shows how far it is (« image 3 sur 7 »). The owner may leave the page or close the application: the work goes on, and the page shows where it stands when he comes back. He can stop the sending before the post is published: nothing is then published. *(The stop: added with the design's v2.)*
- [ ] After it: « Publié », with the link to the post on Facebook.
- [ ] When the answer to the last step is lost, the outcome is unknown: the page says so, gives the way to the Page, and the owner says whether the post is there. Until he has, none of that post's posters can be published again on that Page, alone or in a post. The app never publishes again by itself.
- [ ] A stop of the server before the last step publishes nothing, and the page says « non publiée ». A stop during it is unknown, as above.
- [ ] What is published is each poster's confirmed file as it was when he confirmed the post. A poster changed, a Page changed or a limit lowered between the confirmation and the sending stops the post before anything is sent, and the page says what changed.
- [ ] Publishing costs no credit.

## R-FB-POST-006 — What was published
- **Story:** As a shop owner, I see my posts and where each poster went.
- [ ] The page lists the shop's posts: the date, the Page, the number of images with the first one shown, the state, the link.
- [ ] Each poster's final panel lists the posts it is in. *(Amended with the design's v2: a poster published alone is a post of one image.)*
- [ ] A post removed on Facebook keeps its line; its link then leads to Facebook's own « not available ».

## R-FB-POST-007 — What is kept is said
- **Story:** As a shop owner, I can read what the service keeps of my posts.
- [ ] « Vos données » and the conditions of use say what a post keeps (its posters, their order, its description, its state and its link) in the same paragraph as a publication of one poster, released together with it: the shops are asked to accept once, not twice.

## Out of scope
The editor that makes « bold » letters, emoji bullets and the shop's fixed block (T-FB-007); Instagram; scheduling; a story or a reel; a poster in the « Carré » or « Story » format; a photo that is not a confirmed poster; several Pages; editing or removing a post from the app; subscriptions, tiers' prices and payment; shops without a role on the Meta app (stage 2).

## To prove before the implementation (free; needs the owner's hands for the token, as the proofs of 2026-11-21)
1. **A post of several photos through the API** on a test Page: the two kinds of call, the answer's ids, the post's link, the order shown against the order sent.
2. **How many photos Facebook accepts** in one such post, tried at 10, 20 and 30 (or the number the pilot wants), and what it answers beyond its limit.
3. **A photo uploaded with `published=false` and never attached:** that nobody sees it on the Page, and what becomes of it.
4. **Whether a post made this way can be kept unseen** for a test (not published, or scheduled), as the test post of 2026-11-21 was; else the proofs are made on a Page that is not the pilot's.

## What the proofs showed (2026-11-21, the owner's word "you can run them"; Graph API Explorer in his browser, Graph API v27.0, the Page token of Original Phone Mada, every post scheduled and not published)

- **Proof 1, the calls: done.** Four photos uploaded with `POST /{page-id}/photos`, `url=…&published=false`: each answer is `{"id": "<photo id>"}` only. Then `POST /{page-id}/feed` with `message`, `published=false`, `scheduled_publish_time` and `attached_media[0..2]={"media_fbid":"<photo id>"}`: the answer is `{"id": "<page id>_<post id>", "post_supports_client_mutation_id": true}`. **The post's id comes in `id`, not in `post_id`** (a single photo's answer has `post_id`). The photos did not need `temporary=true`.
- **The order: done at the API.** Uploaded red, blue, green; attached green, red, blue. Read back (`attachments{type,subattachments{type,target{id}}}`): one attachment of type `album` whose photos are green, red, blue: the order sent, not the order uploaded. How Facebook lays the collage out for a visitor is not checked: the posts are not published.
- **The post's link:** `permalink_url` is `https://www.facebook.com/<another id>/posts/<post id>`, whose first part is not the Page id. The link is to be read from Facebook, or built from the Page id and the post id as for one poster: to settle in the design.
- **Proof 2, how many: 12 accepted.** One batch request (`POST /` with `batch`: twelve uploads named `p0`…`p11`, then the post, each `media_fbid` taken from its upload by `{result=pN:$.id}`) answered thirteen times 200 in about 8 s, with the post's id. So more than the 10 that publishing tools stop at. **40 accepted** (the same batch with forty uploads, run by the owner himself in the Explorer on 2026-11-21: forty-one times 200, the post created). Facebook's own largest number is above 40 and is not looked for further: a batch holds fewer than 50 calls, and no shop's post needs more. The code of its refusal stays unknown: the app says a refusal without naming a cause.
- **A post of ONE photo made this way: done 2026-11-22** (the owner, in the Explorer, one batch: the upload, then `/feed` with `attached_media[0]`, then the post read back): the post reads `status_type: added_photos` and one attachment of `type: photo`, `media_type: photo`, whose target is the uploaded photo, as a photo post reads; not an album. So a poster published alone through the post's two calls is an ordinary photo post (ADR-129 holds). The test post (`111875903561009_1468849735385459`, scheduled, unpublished) is his to delete.
- **Deleting a post removes its photos (seen 2026-11-22, read in the Explorer by the lead):** after the owner deleted the test posts, a photo of the one-photo post and one of the 40-photo post answer « does not exist » (code 100, subcode 33); a photo uploaded and never attached is still there (`1468242568779509`, made 2026-11-21). So what a stopped or failed post leaves on Facebook is its uploaded photos, unseen on the Page, until someone deletes them one by one.
- **Proof 3, a photo uploaded and never attached:** it exists with an `id`, a `link` and a `page_story_id`, `can_delete` true, and it is **not** in the Page's `photos?type=uploaded` list, where the latest photo is hours older. Whether its direct link opens for a visitor is not checked. So an upload left behind is not shown on the Page, and the app can delete it.
- **Proof 4, unseen tests: yes.** A post of several photos can be created scheduled and not published (`is_published: false`), as the single test post of the same day.
- **Also seen:** Facebook's batch requests work with the Page token and let one request upload and post. Not needed by the design (it would hide which image failed), but it exists.

## Working defaults, the owner's to overturn
1. **« Publication format only » is read as:** only posters confirmed in the 4:5 format that the app calls « Publication »; « Carré » and « Story » posters are not offered.
2. **One way to publish** *(changed by the design's v2, 2026-11-21, on its devil's advocate; the default before was that the one-poster path stays as built)*: the final panel's « Publier sur ma Page » stays as the quick way in, but it adds the poster to the draft and opens the page; a poster alone is a post of one image. The single poster's own record, routes and sheet (T-FB-003) go: nothing of them was released.
3. **The limit per shop is set by the operator** with the `shops` command (and later the operator's dashboard); no limit by default.
4. **The description is the post's own**, not a poster's caption; it starts empty.
5. **The description's length** keeps the caption's rule (2 000 characters) unless the pilot's posts need more: his capture is about 650.
6. **Stage 1 still:** only shops whose Page admin has a role on the Meta app.

## Sources (read 2026-11-21)
[Page Photos reference (Meta)](https://developers.facebook.com/docs/graph-api/reference/page/photos) · [Posts, Pages API (Meta)](https://developers.facebook.com/documentation/pages-api/posts) · [bundle.social: Facebook posting API](https://bundle.social/blog/facebook-posting-api) · [Adobe Content Scheduler: media specifications](https://helpx.adobe.com/lv/express/web/publish-and-share/schedule-manage-posts/media-specifications.html) · [PostZen: post to a Page](https://www.postzen.dev/blog/facebook-graph-api-post-to-page) · [DEV: social media API posting limits](https://dev.to/dominic_frei_73028ac46c47/social-media-api-posting-limits-in-2026-every-platform-1okf) · [Zoho community: the API allows more than 10](https://help.zoho.com/portal/ja/community/topic/zoho-social-allows-only-4-images-per-post-even-for-facebook-though-api-allows-more-than-10?page=72) · [Stack Overflow mirror: page post with multiple photos](https://kaweah.freedombox.rocks/kiwix/content/stackoverflow.com_en_all_2023-11/questions/65089225/facebook-graph-api-page-post-with-multiple-photos)
