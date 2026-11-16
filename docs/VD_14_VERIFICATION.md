# VD-14 verification: Collaboration network layout shift

Date: 2026-11-16

## Cause and fix

Live Lighthouse (mobile preset) on `/network` reported CLS 0.421 at `6df809a0`,
with `section.net-page` as the shifted node. `framework/src/network.md` rendered
the page header and the volume callout from a runtime `display()` cell, so they
were inserted above the section after first paint. They are now static markup with
the same text and classes (icons as `<use href="#i-...">`; `network.js` injects
the sprite). `network.css` positions `.net-message` over the chart box so showing
or hiding it moves nothing.

## Verification

- Local Lighthouse, 3 runs each: before 0 / 0 / 0.4207 (the third reproduced the
  live node); after 0 / 0 / 0, no layout-shift nodes. Combined assembled-site run:
  CLS 0, accessibility 100, axe clean at desktop and 375 px.
- Tests: `tests/test_vd14_network_cls.py` (5) plus the VD-6b and network suites.
