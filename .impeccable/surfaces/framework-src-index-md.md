---
version: 2
slug: "framework-src-index-md"
primary_target: "framework/src/index.md"
related_targets: ["framework/src/components/landing_story.js", "framework/src/components/landing_story.css"]
---

# Surface: plastiverse.live global landing (framework/src/index.md after PLAT-1)

Mode: Persuade. Audience: researchers, agency staff, funders, press, and local experts who might become ambassadors. Job: feel the scale of plastics research worldwide, see how Plastiverse Live turns it into knowledge, then open a regional atlas or join as a local ambassador. Proof: real OpenAlex counts (works per year, works by country), real CC BY paper pages, live regional atlases. Constraints: static Framework page, no external CDNs, tokens only, WCAG AA, reduced motion, usable at 375 px. Owner approved the prototype on 2026-11-17 (`.impeccable/sketches/spectral_story.html`); build spec `docs/PLAT_2_LANDING_SPEC.md`; replaces the version 1 Tile-cartogram contract.

## Direction contract

THESIS: Data, then knowledge, then understanding, told as one scroll. A 1950s throwaway picnic shatters into microplastics, the particles become studies, the studies order into a Barker-like mandala, the mandala lights a bulb, and the light opens onto the real global record. Refuses the SaaS hero, the chart wall and doom imagery.

OWN-WORLD: Spectral Match, recoloured by the Plastiverse Live logo. Black story ground until the light burst, then an airy light ground (#F6F8F9). Navy ink #17263D; data in slate #436487 with mint #C5EADF steps; coral #FA6B68 for "LIVE", California and live markers (coral-ink #D9443F for text on light); butter yellow #FFF49A turning gold #E2B714 for the bulb. Schibsted Grotesk for text, Martian Mono only for data and source lines. Real photographic plastics and real paper pages before the light; flat data marks after.

STORY: A visitor sees a picnic, watches each plastic item pop and shatter into particles of its own colours, learns microplastics were first described more than 50 years ago, sees every particle become a paper, watches the papers organise into knowledge and light a bulb, then sees the exponential growth of the research, where the evidence is and is missing, who works with whom, how global it is, and that local knowledge matters, ending at a regional atlas and an invitation to become a local ambassador.

FIRST VIEWPORT: Black stage under a black header. The picnic fills the screen with no text; the blanket and then each item light up one at a time within about 1.5 s; a small scroll cue appears. The first scroll brings "Plastic is everywhere…" in at the top while the picnic stays nearly full screen below it.

FORM: Spectral Match (assigned direction, seed:2c42143eccc874ce), steered by the owner into a scroll story after Hartmann, Mennekes and Wagner (2026).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Signature interaction: one sticky canvas stage driven by scroll position. Items crack along clean Voronoi lines and crumble into their own colours; the bulb's light bursts radially and turns the page light; the dots stream out of the bulb into the chart; network nodes ride damped springs and get plucked. Text never overlaps an image (measured safe zones). Reduced motion shows the beats as a static sequence.
