---
version: 1
slug: "impeccable-sketches-global-app-html"
primary_target: ".impeccable/sketches/global_app.html"
related_targets: [".impeccable/sketches/global_app_data.js",".impeccable/sketches/src/build_global_app_data.py"]
---

# Surface: Plastiverse Live global data app (prototype `.impeccable/sketches/global_app.html`)

Mode: Operate. Audience: researchers, agency and policy staff, funders, press (PRODUCT.md). Job: compare countries first, then step down to one country (and into a regional atlas where one exists) and read its evidence map, trend, experts, institutions, collaboration network and works. Proof: real OpenAlex counts and samples (`global_app_sample.json`, `global_counts.json`), labelled where illustrative. Constraints: becomes Framework pages after PLAT-3/PLAT-4; tokens only, self-hosted fonts, WCAG AA, keyboard-complete, reduced motion, usable at 375 px. Owner choices 2026-11-18: first job "compare countries"; views countries + profile, evidence map + trend, experts + institutions, network + works; one shell with a scope switch that California and Norway will reuse (VD-SM). Owner steer on the picked sketch: no desktop sidebar (a drawer on mobile is fine), the local-atlas indicator lives inside the map and the table, and the world map is bigger. The landing page is out of scope.

## Direction contract

THESIS: One shell, many scales. The scope ladder (World, continent, country, regional atlas) is the only navigation that changes the data; the seven view tabs stay put while every view re-scopes. Refuses the dashboard of KPI tiles and the sidebar of page links.

OWN-WORLD: Plastiverse Live light ground as built after the landing's burst: ground #F6F8F9, paper surfaces, navy ink, slate data steps (wash, mint, slate-2, slate), 1 px ink and line hairlines, square corners, no shadows. Schibsted Grotesk at regular weight for headlines and UI; Martian Mono only for counts, axes, legends and source lines. Coral marks only the live atlas (California); Norway is a dashed coral-ink outline.

STORY: A visitor sees the whole world's plastics research on a large pixel map with a ranked country table, spots California's live atlas on the map and in the table, picks a country, and watches the map zoom and every tab re-scope to that country; they read its trend, co-author countries, experts and newest works, and leave for the regional atlas or the source.

FIRST VIEWPORT: 60 px landing header (light). Under it a sticky 52 px scope bar: the ladder as breadcrumb steps, each a disclosure listing its children, with "Find a country" on the right. Then the scope headline at headline size beside one statement sentence carrying the scope's figures in mono. Then the tab row. Then the pixel world map at full content width (about 1340 by 560 px) with the California callout ("live atlas, Open") and the Norway callout inside the map; the country table starts below the fold.

FORM: Scope ladder (dealt lead, position 3 of 7 on my list), steered: desktop ladder is a horizontal breadcrumb bar, the vertical rail survives only as the mobile drawer. seed:2fe7429ad86b7253

Signature interaction: stepping down the ladder (from the bar, the map, the table or search) tweens the map's viewBox to the chosen country over 450 ms ease-out, dims the rest of the world and rewrites the headline; stepping up reverses it. Reduced motion cuts straight to the end state.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
