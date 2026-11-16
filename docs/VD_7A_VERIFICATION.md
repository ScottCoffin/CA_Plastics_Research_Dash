# VD-7a verification: Monitoring adoption

Date: 2026-11-16

## Result

Monitoring adopts the shared page header, visible caution callout, counted
disclosures, shared filter panel and map card in `framework/src/monitoring.md`,
`framework/src/components/monitoring.css`, and
`framework/src/components/monitoring.js`. The shared SVG map pointer resolver
in `framework/src/components/svg_map.js` supports the enlarged marker hit area.
The map details panel is named and scrollable; keyboard marker selection works,
and pressing Enter in a filter does not submit the form. Institutions retains
its existing behavior when no shared resolver is available.

## Verification

The implementation deployed as commit `6e89d172`. CI run `43897771727`,
GitHub Actions Pages run `43897771760`, and legacy Pages run `43897771106`
all completed successfully.

The focused final acceptance reported 9 passed; the final combined visual
regression set reported 37 passed. The consolidated suite reported 1,702 passed
and 9 expected placeholder skips. The Framework build produced 13
pages and 90 links.

The assembled local page was audited at 1440 x 900, 390 x 844, and 320 x 800.
Each viewport showed the caveat, five disclosures with populated counts, six
filter controls, and the map card with its SVG and five controls. At 320 px,
filters and the map stack within the page and the map controls wrap without
horizontal overflow. Axe violations, overflow, console, page, and request
errors, and actionable targets below 24 px were zero; the only excluded target
was Framework's inert 1 x 1 sidebar checkbox.

All six ordinary marker clicks selected the requested marker and opened its
details. A click 11.25 px from a marker selected the nearest marker. Enter and
Space selected markers; dragging left the selected marker unchanged. The
details view remained axe-clean. Collapsing all sections left zero open and
expanding all reopened five; the filters and map remained available.

Screenshots: `scratch/ux_vd_batch4/deep-monitoring-1440.png`,
`scratch/ux_vd_batch4/deep-monitoring-390.png`,
`scratch/ux_vd_batch4/deep-monitoring-320.png`, and the final mobile captures
`scratch/ux_vd_batch4_luna_final2/monitoring-390.png` and
`scratch/ux_vd_batch4_luna_final2/monitoring-320.png`.

Three local Lighthouse runs scored 76, 75, and 76 for performance (median 76),
with LCP 5.8 s, CLS 0, and accessibility, best practices, and SEO at 100.
These local results are not directly comparable with the live CDN results.

Live acceptance was checked at 1440 x 900, 390 x 844, and 320 x 568. Axe
reported zero violations, there was no horizontal overflow or console, page,
or request error, and the only actionable target below 24 px was the known
inert 1 x 1 Framework sidebar checkbox. All six marker clicks selected the
requested marker; the 11.25 px extended hit area selected the nearest marker;
Enter and Space selected markers; dragging preserved selection; and Enter in
search caused no navigation. The named details region is keyboard-focusable
and scrolls horizontally on mobile. All six disclosures (five main sections
plus the separate licence and caveat disclosure) collapsed and reopened.

Three comparable live post-deploy Lighthouse runs scored 97/97/97 for
performance, with accessibility, best practices, and SEO at 100. LCP was
2.4/2.5/2.5 s and CLS was 0 in all runs. The live pre-change control scored
100 for performance, LCP 1.7 s, and CLS 0. The performance score passes
Section 9's maximum three-point regression exactly at its boundary; the
repeatable LCP increase of about 0.7 to 0.8 s is recorded here. Live viewport
screenshots and interaction evidence are in
`scratch/ux_vd7a_live_acceptance/`; the audit result and Lighthouse runs are
recorded in `results.json`, `lh_repeat_2/`, and `lh_repeat_3/` there.

## Delegation and remaining work

Luna handled implementation, follow-up, browser audit, and code review. H25
owner review and VD-5 Overview acceptance, including LCP, remain open.
The Section 9 visitor workflow passed all six tasks; the Experts CSV task
exported the same 604 rows shown in the result count, and the Monitoring CSV
task exported four of four rows for the selected matrix.
