# Doka Studio — Signal logo kit v1

2026-11-15 · Prepared after the user selected Signal and requested the kit. **Digital artwork delivery; application integration is separate.**

[Open the visual overview](preview.html) · [Usage guide](USAGE.md) · [Six application mockups](presentation/index.html) · [Exact palette](palette.json) · [Verification report](checks/verification.json)

## Choose a file

| Need | File or folder |
| --- | --- |
| Main horizontal logo | [Charcoal SVG](digital/doka-horizontal-charcoal.svg) · [transparent PNG](digital/doka-horizontal-charcoal-1200.png) |
| Main logo on a dark background | [Paper SVG](digital/doka-horizontal-paper.svg) · [white SVG](digital/doka-horizontal-white.svg) |
| Stacked logo | [Charcoal SVG](digital/doka-stacked-charcoal.svg) · [paper SVG](digital/doka-stacked-paper.svg) |
| Name without the symbol | [Wordmark SVG](digital/doka-wordmark-charcoal.svg) |
| Symbol only | [Charcoal SVG](digital/doka-symbol-charcoal.svg) · [paper SVG](digital/doka-symbol-paper.svg) |
| Social avatar / app artwork | [Rounded icon SVG](web/doka-app-icon.svg) · [1024 px PNG](web/doka-app-icon-1024.png) |
| Web browser icons | [SVG favicon](web/favicon.svg) · [ICO, 16/32/48 px](web/favicon.ico) |
| Apple touch / PWA icons | [180 px](web/apple-touch-icon.png) · [192 px](web/icon-192.png) · [512 px](web/icon-512.png) · [maskable 512 px](web/maskable-512.png) |
| Editable vector originals | [Masters](masters/) |
| Fonts and licences | [Fonts](fonts/) |

`digital/` provides charcoal, black, paper and white for all four layouts, with transparent PNGs (1200 px longest side; standalone symbols 512 px). SVGs have outlined text, real transparent counters, no embedded images and no font dependencies. `masters/` retains the original layout geometry, the enlarged small-size symbol and optically adjusted reverse versions.

`web/` contains a manifest and an example HTML head snippet. Their paths are relative to that folder. Adapt paths and merge the icon entries with the application's real manifest during a separately scoped integration. The example does not implement PWA installation, offline support or native store metadata. Favicons use charcoal on a yellow tile so the same file remains visible in light and dark browser chrome.

`presentation/` shows six illustrative uses with the exact vector artwork. Contact details, account handles and the `example.invalid` address are placeholders. These are brand mockups, not implemented app screens or acquired domains. The earlier AI-generated moodboard remains in the separate exploration folder; it is not a vector master.

## Refinements and checks

- Preserved the selected D and bold Space Grotesk wordmark. Added stacked and name-only layouts from the same outlined letters.
- Reverse D counters are expanded by one source unit (48 → 49 radius), reducing apparent weight; wordmark outlines are preserved. Small-size artwork scales up the same simple D silhouette rather than introducing another symbol.
- Reviewed two exact-artwork proofs, actual-size symbols, conservative lockup minima, reversed artwork and circular icon crops. [Final proof](checks/artwork-proof.png).
- Master audits: 90–100/100 with no FAIL findings. Font contours retain documented near-angle/complexity notices; stacked artwork sits intentionally slightly above the geometric center. Audit scores are heuristics, not a legal or production certification.
- Scripted export checks cover SVG structure, font licence metadata, PNG dimensions/transparency, reverse ink coverage, ICO sizes, maskable safe area, manifest links and text/background contrast. See [verification](checks/verification.json) and [audit details](checks/masters-audit.json).

Regeneration scripts and intermediate proof files are kept in the project's git-ignored `outputs/doka-signal-kit-2026-11-15/`. This portable delivery contains the results and check evidence.

**Limits:** RGB/sRGB digital assets, with unprofiled CMYK estimates only; no Pantone match or physical print proof. Name/trademark/domain clearance and customer recognition tests remain open. No application source, production server or customer poster was changed.
