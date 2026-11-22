# First-poster guide

**Status** Approved for implementation on the owner’s « next » · 22 November 2026. [Approved requirements](../requirements/first-poster-guide.md) · [Current-release walkthrough](../guide-premiere-affiche.md) · [Companion journey design](saas-journey.md).

The guide now groups product fidelity and the finished image into one review, following the owner-approved single-review amendment.

## D-GUIDE-001 · Entry and return (R-GUIDE-001, 003)

Offer « Ma première affiche » beside « Créer une affiche » in the shop's empty Accueil. Show it when the existing recent-posters read succeeded and returned empty. After either accepting the conditions or choosing « Plus tard », the invitation becomes reachable in the ordinary home view. If the session opened a specific poster or an account deep link, keep its destination. A failed or stale library read never establishes that this is a new shop.

Provide a permanent « Aide » button in the sidebar/drawer. It opens the same reading panel from Home, chat, Pas à pas or Publier. Close the drawer before presenting help. On phone, keep the five primary navigation slots for work. On desktop use the existing dialog surface at reading width, and on phone use a scrollable sheet with a reachable close button. The invitation itself is inline and leaves all workspace actions available.

Keep the active view mounted underneath the reading panel. In particular, opening help must not call the hash router, release the publishing lock, switch chat mode, reset the intake form, flush a draft, or submit a pending action. Opening from a contextual link jumps to the relevant instruction. Closing returns focus to that link, or to the menu toggle if the link was in a drawer that closed. An operator signing in at /admin/ sees the operator workspace only.

## D-GUIDE-002 · Four steps in the seller’s words (R-GUIDE-002, 003)

Show one step at a time, headed « Étape 2 sur 4 », for example. Provide « Précédent », « Suivant » and « Fermer ». The final step ends with « Terminer ». It closes the guide. Replay starts at step one after completion; closing early preserves the current step for the same open session. Keep a short expandable « Si vous êtes bloqué » beside the relevant step. Use the French walkthrough as the editorial source and update its button labels together with the shipped UI.

| Step | Core instruction | Contextual help |
|---|---|---|
| 1 · Présenter le produit | Ajoutez une photo du produit et indiquez son nom, sa variante et son prix exact en ariary. | Explain product versus inspiration, where to find « Pas à pas », and how to retain an existing poster when using a new photo. |
| 2 · Préparer l’affiche | Relisez l’offre, choisissez le style et vérifiez le coût indiqué avant de lancer la génération. | A new offer already uses « Publication » for direct Page publishing and PNG download. Describe Carré and Story as optional format changes before generation. An AI message read costs the shop zero credits and is subject to its daily limit; generating the image costs one credit. Display the actual available balance at the live action. A drawn price change can require a new paid scene. |
| 3 · Vérifier l’affiche | Comparez le PNG final avec la photo du produit et le prix indiqué. Si nécessaire, corrigez l’affiche. | Explain checking the finished image at full size, reporting incorrect product fidelity and reviewing a new preview after edits. |
| 4 · Télécharger ou publier | Confirmez l’affiche pour plus tard dans « Mes affiches », confirmez et téléchargez le PNG, ou confirmez et préparez votre publication. | For several posters, select and order the confirmed Publication files. Check the Page name, description and image order before sending. For an unknown send, inspect the Page before answering. Native phone sharing is a separate destination with PNG fallback. |

Panel controls navigate instructions only. A seller returns to the real workspace to add photos, accept terms, generate or publish. This keeps the guide safe to explore even with a real account and an eligible post draft.

## D-GUIDE-003 · State, accessibility and failures (R-GUIDE-001–004)

**Interface and data.** Local Vue presentation under App.vue's authenticated shell. Use the existing French strings for actual control labels wherever they are shared. Keep the open flag, invoking control and step index in memory. No new HTTP contract, schema change, browser storage key, image download or analytics event. A refresh returns to the normal app; the guide is always available again from Aide. A session change resets the step and opener. Invitation visibility uses the existing home list; a returning shop without posters can see it again.

**Transitions.** Closed → open at the chosen step on explicit activation. Previous/next changes only the step, including a programmatically focused heading with the step number. Close, Escape or Terminer restores the initiating context. If terms, session verification or a higher-priority confirmation needs the screen, dismiss help and give that existing flow focus. Opening help cannot silently close a running consent, conflict or money confirmation. On a genuine route change or session loss, discard the opener and let the new screen own focus.

| Failure or edge case | Behaviour and verification |
|---|---|
| Slow network, stale list, service pause or zero credits | Help remains readable once the app shell is loaded. Home presents the existing loading/error/credit state separately. No retry, transition or example in the guide triggers a model read or job. |
| Phone keyboard or assistive technology | Put the sheet outside the composer's form. Trap focus within its labelled dialog; leave the underlying screen inert. Close and step navigation remain reachable at 360 px and 200% zoom. Test Escape, reverse tab order and focus restoration with the keyboard raised. |
| User is editing, uploading a photo or composing a batch | Keep work components alive. Closing help preserves their contents and existing in-flight activity. Read the UI again if something completed in the background. Announce completion in its normal surface. |
| Two tabs, different shop, logout or shared phone | Help is per open page. Opening or replaying it never reads another shop's work, takes a Web Lock, or persists an offer, caption, account identity or tutorial step. |
| Page connection unavailable, uncertain send, or terms deferred | Show a reading-only recovery hint. Existing controls remain the sole place to reconnect, answer the outcome or accept the terms. PNG instructions remain available. |

**Verification before release.** With isolated data, capture requests while traversing all steps, dismissing midway and replaying. Assert zero new mutation requests attributable to the guide. Repeat over unsent chat attachments and a batch with a non-empty description and ordered selections; verify state and focus after dismissing. Test the terms deferral and failed-home-read cases separately. Run the guide with the normal message and Pas à pas flows on a phone and desktop. Ask a first-time seller to obtain a stub PNG and prepare a stub Page post unaided, recording where the guide or labels failed. A browser smoke verifies mechanics; comprehension needs that observed session.
