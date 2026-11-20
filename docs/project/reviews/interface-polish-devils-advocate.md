# Interface polish — devil's advocate (Opus subagent, 2026-11-20)

On design v1, read-only. Eight points that would change a decision, most important first, and what the lead did
with each (v2 of [designs/interface-polish.md](../designs/interface-polish.md)).

| # | Point | Evidence it gave | Lead's ruling |
| --- | --- | --- | --- |
| 1 | Release T-POLISH-001 alone before the invitations and hold the rest: nothing in 002–005 blocks the owner's next steps; C13 is already fixed (`style.css` 784, 791); centring an empty chat helps desktop only and moves the composer at the first send | HANDOFF.md 18–22; requirements 64 | Partly taken: the centring and C13 are dropped. The rest goes on: the owner asked for the whole polish ("go to the end without stopping"); a deploy is his word in any case |
| 2 | `--hue` → `#F2C744` turns about ten other things yellow; in the light theme the wait bar's moving part falls from 1.85:1 to 1.16:1 against its track and the loading line from 2.27:1 to 1.43:1 | `style.css` 93, 151, 162, 338, 378, 395–396, 404, 702, 756, 790 | Taken: two tokens, a fill (`--signal`) and a line (`--hue`) |
| 3 | A yellow main button on paper is 1.43:1 against the page; an ochre border makes it differ from the operator's; « one yellow action » fails on the final panel (`App.vue` 2366) and in the chat (`chat.ts` 261 beside the send button) | as cited | Taken: the main button does not change. A yellow one waits for the owner's look at a phone in daylight |
| 4 | Dark ground `#100f0e` → `#20201D`: about 25 tuned values; `--ok-bg`, `--warn-bg`, `--bad-bg`, `--warn-glass` would merge with the new ground; `#14110e` behind a chat poster (`style.css` 720); shops never see the operator's page | `style.css` 392, 411, 488, 605, 720 | Taken: the dark greys stay; the text becomes the kit's paper |
| 5 | `contrast.test.ts` checks the wrong background: the page shows the patches' gradient, not `--ground`; state text sits on glass, not only on its own ground; `--bad` on the dark bubble is 4.29:1 today and the table would miss it | `style.css` 42, 48, 281, 346, 679, 718–719, 738 | Taken: the smoke's rendered measure (`check_contrast`) is extended instead |
| 6 | The 12 px phone gutter is `main`'s for every screen; removing it takes 16 px from the editor at 360 px | `style.css` 590, 606–607 | Taken: 16 px on the five screens only |
| 7 | A bare « 117 » under a card icon can read as money; « −2 » untested; if « Mes » is hidden in one bar only, the bars differ again. Proposed « Crédits » alone | `App.vue` 441; shop-dashboard.md 88; `generation.ts` 69 | Partly taken: the number stays (D-SHOP-DASH-001 shows and links the balance in the creator); −2 and an unread balance are tested; « Affiches » in both bars if needed. The bare number is an owner decision on its default |
| 8 | The operator's page has one user; the session fold solves a test artefact; T-ADMIN-008 and 009 add sections to those screens | baseline 70; TODO.md 65–66 | Taken: numbers aligned only |

It agreed with: Figtree (Noto Sans lacks the 550 and 650 weights the interface uses), a hidden chat title, no box on
a focused title (`admin.css` 22 does the same), one 860 px width. It also noted that ADR-122 was cited before it was
written (written the same day) and recommended dropping `DESIGN.md` and the full recapture; the lead keeps both, as
the record the owner asked these skills for, with the capture script kept in the repository.
