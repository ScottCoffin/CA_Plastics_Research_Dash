# VD-18 verification: owner design feedback (H25)

Scope: Framework Overview hero, Start here, Explore cards, the Experts drawer button, About,
the Evidence trend ticks, the footer and the sidebar brand. Visual reference:
`docs/design/style_tile.html`. Screenshots and measurements are in `scratch/w1/` (gitignored):
`before/` is the build before the change, `after/` the build after it, `measure.json` the
computed-style readings, `ux/results.json` the axe audit.

## Per item

1. **Hero coastline** (`framework/src/components/overview.css`, `.atlas-hero__motif`). The motif
   is a CSS mask of `assets/design/ca_contours_mask.svg`, so the strokes were
   `--atlas-on-brand-muted` at `opacity: .38` (effective stroke alpha about 0.21). Now
   `--atlas-brand-tint` (rgb 216, 238, 231, the tile's stroke colour) at `opacity: 1`, which gives
   the tile's 0.55 stroke alpha. Phone width uses `opacity: .8`, as the tile does. The mask asset
   is unchanged (a test pins its bytes). The mask fill is 0.12 against the tile's 0.07, a slightly
   stronger haze that a new mask would be needed to remove. Evidence: `after/overview_1440_hero.png`
   beside `before/overview_1440_hero.png` and `before/tile_hero_1440.png`.
2. **Eyebrow** (`framework/src/index.md`, `overview.css`). The "·" text is replaced by
   `<span>California</span> <i></i> <span>32.5° to 42° N</span> <i></i> <span>Plastics research since 1950</span>`.
   `.atlas-hero__eyebrow` is a wrapping flex row, and `.atlas-hero__eyebrow i` is a 4 px dot in
   `--atlas-accent`, as in the tile. The spaces between items are not rendered in flex and give
   screen readers word breaks. At 390 px the row wraps with the dot at the end of line one, the
   same behaviour as the tile's flex wrap.
3. **Text-to-box spacing** (`overview.css`). Values now follow the tile. KPI: padding 14 px 16 px,
   min-height 128 px (was 152), label icon 16 px (was 18), note 0.8 rem (was 0.78), value line
   height 1.1. Start-here row: padding 12 px 14 px, min-height 64 px (was 112), tile icon 38 px with
   a 20 px glyph (was 22), title 0.94 rem (was 1.05), subtext 0.85 rem (was 0.82). Entry card:
   min-height 128 px (was 160), title 1.12 rem / 1.15 (was 1.05), subtext 0.85 rem, meta 0.78 rem
   weight 650. Measured Start-here row height at 1440 px: 146 px to 90 px.
4. **"Quick routes" eyebrow** removed from `framework/src/index.md`; the "Start here" h2 stays.
   `tests/test_vd5_overview.py` asserts it is gone.
5. **Start-here underline** (`overview.css`). Cause: `style.css` sets
   `#observablehq-main li a { text-decoration: underline }` (specificity 1,0,2), which outranks
   `.atlas-task-list > li > a`. New rule `#observablehq-main .atlas-task-list a` (with `:visited` and
   `:hover`) sets `none`. Title weight 700, subtext 400. Measured at rest, on hover and on keyboard
   focus: no decoration; focus keeps the 3 px accent outline on `./experts`.
6. **Brand box** (`framework/src/design/shell.css`). Cause: the rule
   `#observablehq-sidebar > ol:first-child > li > a[aria-label="Overview"]` (brand-tint
   background and an inset bar), plus the sidebar hover wash. Background and box-shadow are now
   none in rest, hover and active states. Framework's active-page bar
   (`li.observablehq-link-active::before`) is hidden for the brand item only. Focus outline
   unchanged. Measured at 1440 px: `background-color` transparent, `box-shadow` none. Evidence:
   `before/sidebar_top_1440.png`, `after/sidebar_top_1440.png`. The header brand
   (`.atlas-header__brand`) has no background or box; it underlines on hover, as other links do.
7. **Footer links** (`shell.css`). `.atlas-footer__links` is `flex-wrap: nowrap`,
   `white-space: nowrap`, 13 px with a 0.875 rem gap. At 26 rem and below the footer takes the full
   viewport (`max-width: none; margin-inline: -2rem`), because the 2 rem page gutter had left it
   224 px wide at 320 px; links are 12 px with a 0.75 rem gap there. Measured: one row at 320, 375,
   390 and 1440 px; document width equals the viewport at 320, 375 and 390 px (before: 365 px and
   wrapping to 3 and 4 rows at 390 and 320 px). Evidence: `after/footer_320.png`.
8. **Experts drawer button** (`framework/src/components/experts.css`). Cause: `#experts-root a`
   (specificity 1,0,1) sets brand-strong text and outranks `.atlas-btn--primary`, and the link
   measured 1.94:1 in axe. New `#experts-root a.button-link`: background brand-strong, text
   `--atlas-on-brand` (12.1:1); hover and focus use brand (8.2:1). `experts_model.js` is unchanged.
   Institutions' `.button-link` rules are scoped to `#institutions-root` and were not touched.
   Evidence: `after/experts_1440_button.png`.
9. **About links** (`framework/src/about.md`). The bare `<a href=${…}>` text is now one
   `${html`<p>…</p>`}` expression. Measured: two anchors, `…/status.html` and `…/feed.xml`, at
   1440, 390 and 320 px. `tests/test_ux10_about.py` asserts the expression.
10. **Trend ticks** (`framework/src/components/v4_trend.js`, `yearTicks`). Labels are every even
    year (`year % 2 === 0`); the forced last-year label is gone. Both the bar and share charts use
    `yearTicks`. The lighter "recent" bars are unchanged. Measured: 2000 to 2026 in steps of 2.
    Evidence: `after/evidence_1440_chart1.png`.

No new tokens were needed (`tokens.css` is unchanged). `components.css`, `style.css`,
`about.css`, `experts_model.js` and `observablehq.config.js` are unchanged.

## Build

`cd framework && ATLAS_FW_OUT=dist-w1 npm run build` failed in the copy step:
`observablehq.config.js` (the search worker's change) references `./assets/site_search.css` and
`.js`, which are not yet in `framework/src/assets/`. To keep this change verifiable, the same
`framework/src` tree was built from `scratch/w1/fwbuild`, with the two search assets copied from
`site/assets/` into that scratch copy only, then postbuilt. Its output is copied to
`framework/dist-w1`. Re-run the official command once the search change lands.

## Checks

| Check | Result |
|---|---|
| `py -3.14 scripts/check_design_tokens.py` | exit 0; 0 Framework stylesheet hex uses |
| `py -3.14 scripts/check_at5.py --dist dist-w1` | exit 0; "AT-5 checks passed (static + build)" |
| `py -3.14 scripts/check_public_text.py --help` | usage printed |
| `py -3.14 scripts/check_public_text.py` (CI, repo root) | OK, 18 public files |
| `py -3.14 ../scripts/check_public_text.py` (CI, from `framework/`) | OK, 18 public files |
| `py -3.14 scripts/check_public_text.py framework/dist-w1` | OK, 14 built pages |
| `py -3.14 -m pytest -q tests -k "overview or about or design or footer or trend or v4 or experts or vd"` | 212 passed, 9 skipped (A2 placeholders), 1622 deselected |
| `py -3.14 -m ruff check .` | All checks passed |
| `py -3.14 -m ruff format --check` (two edited test files) | already formatted |
| `git diff --check` | clean (CRLF notices only) |
| axe via `ux_audit.py` on `/`, `experts`, `about`, `evidence` (1366 px and 375 px) | no violations on any page; no horizontal overflow |
| axe with the Experts drawer open (1440 px, 390 px) | drawer button contrast violation gone (was serious, 1.94:1). Two pre-existing findings remain, both on the baseline build too and outside VD-18: `aria-allowed-role` on `#researcher-drawer` (minor) and `scrollable-region-focusable` on `.atlas-table-wrap` at 390 px (serious) |

Not done: no full pytest run, no commit, no push. Preview servers on 8771 and 8772 stopped at the
end of the run. The Framework and preview artefacts are gitignored (`dist-*/`, `scratch/`).

## Lead follow-up (2026-11-16)
- Item 6 root cause: the green square was the sidebar nav-icon swatch (`.observablehq-link > a::before`,
  18 px, `mask: var(--atlas-nav-icon)`) on the brand/home link, which has no nav icon, so the mask was
  invalid and a solid square drew above the CA mark (ink colour on other pages). `shell.css` now drops
  the pseudo-element on the brand item. Zoomed screenshots before/after confirm.
- Hero search: the icon sat in a white strip outside the field (pre-existing; the shared
  `.atlas-search > .icon` rule does not reach the wrapped `.atlas-search__icon`). `overview.css` now
  positions the wrapped icon inside the field and removes the wrapper's box.
- Lead gate on the combined tree: full pytest 1,834 passed / 9 skipped; Ruff; build; links; A1/A2
  scaffolds; 0 hex; public text; `git diff --check`; axe none on /, experts, network, about, evidence,
  search (assembled local preview).
