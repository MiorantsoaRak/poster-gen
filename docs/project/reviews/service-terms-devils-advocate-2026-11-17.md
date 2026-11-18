# Devil's advocate — designs/service-terms.md, Draft v1 (2026-11-17, Opus subagent, read-only)

Summary of the points that would change a decision, as reported to the lead. All five were taken into v2.

1. **Warning in the chat:** drop the `unlisted_features` reading field; every scene-adjustment card always carries a conditional sentence. Saves the reader and stub change, the paid evaluation, and meets "chat and editor alike". Cost: the sentence also shows on requests such as « fond plus sombre »; ADR-111 quotes the bare sentence, so the wording needs the owner's word.
2. **The `adjusted` flag:** one wording for every version instead of a per-version flag and two branches.
3. **« Vos données » claims:** the backup-erasure claim depends on an off-box backup choice not yet made; counts and negatives ("six dernières lignes", "14 jours", « Votre logo ne lui est pas envoyé ») can become false with no test failing; "le jour même" leaves one operator no slack. Describe categories, soften the promise.
4. **`erase`:** defer until the first request; R-TERMS-003 asks only that the page say the operator deletes on request.
5. **Five tasks become two or three;** the operator-side display of acceptance is optional.

**First sign-in on a phone:** the dialog's « Se déconnecter » is the hazard. `askSignOut` signs out with no confirmation when nothing is waiting (App.vue:1597-1602), and sign-out deletes the device's chat threads (api.ts:226-234); when something is waiting, its confirmation would be hidden behind the dialog. Drop the button.

**Tried to break and could not:** the text and its version as a code constant served by the API; the check at admission rather than at session level.
