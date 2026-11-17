# VD-12 verification: global acceptance measurements (machine part)

Measured on the live site, `https://plastiverse.live/`, on 2026-11-16. The owner review (H25) is not part of
this document. The first run (tables below) found three gaps that became VD-15 (context-page headers and
icons), VD-16 (Evidence Chart/Table controls) and VD-17 (0 stylesheet hex literals); all three are deployed
and the rerun section records the result. Open after the rerun: the classic `expert.html` profile has no
sprite icon (it moves into the shell with UX-13), and single-run Lighthouse performance on experts and
institutions is below baseline (see the A/B context).

## Commands

| Step | Command | Result |
|---|---|---|
| Snapshot run (final) | `py -3.14 scripts/design_snapshots.py --base https://plastiverse.live/ --out scratch/design_snapshots` | exit 0; log `scratch/vd12/design_snapshots_run4.txt` |
| Lighthouse | `py -3.14 ~/tools/ux-audit/ux_audit.py https://plastiverse.live/ "" experts network institutions "institution#inst=I84218800" monitoring funding evidence policy resources about glossary --out scratch/vd12/lh --lighthouse --no-mobile` | wrote `scratch/vd12/lh/results.json`; log `scratch/vd12/lh_run.txt` |
| Token check | `py -3.14 scripts/check_design_tokens.py` | first run `OK: 84 ...`; final run on the working tree `OK: 0 ...`; both exit 0 |
| Unit tests | `py -3.14 -m pytest -q tests/test_vd12_design_snapshots.py` | 10 passed |
| Lint | `py -3.14 -m ruff check` and `ruff format --check` on the two new files | passed |
| Doc links | `py -3.14 scripts/check_doc_links.py` | see the final report |

Gate conventions: 60 KB is 61,440 bytes and 12 KB is 12,288 bytes. The Lighthouse run used the CLI default
mobile preset, one run per route. `--no-mobile` only skips ux-audit's 375 px pass. The VD-6c deployed numbers
used three-run medians, so single-run figures here are noisier.

## Route keys

The 14 keys match `docs/design/baseline_2026-11-14.json`. Two routes use IDs different from the baseline:

- `institution` is measured at `institution#inst=I84218800` (the brief's ID). The baseline `institution` entry
  was `/institution` with no ID, so its Lighthouse figure is not like-for-like.
- `expert_profile` is measured at `expert.html#author=A5036007957` (the brief's ID). The baseline used
  `A5046986222`. The template is the same, but the entity differs.
- `institution_page` is measured at `institution#inst=I97018004`, the baseline URL.

## Per-route table (1440x900 first screen)

Fonts are the first platform font reported by CDP for the probe (headings, body, sidebar link, header, button,
td). `ok` means no banned face (Palatino Linotype, Times New Roman, Arial), h1/h2 render Barlow Semi Condensed
(weight variants included), and the paragraph renders the system face. "Charts" is charts with a Table view
over all `.atlas-chart` elements. M is Hasler-Susstrunk colourfulness of the fold PNG. Sat% is the share of
pixels with HSV saturation above 0.5 and value above 0.3.

| Route | Fonts | Page header | Icons | Charts with table | M now / base | Sat% now / base | Font KB |
|---|---|---|---|---|---|---|---|
| home | ok | FAIL | 19 | 0/0 | 36.1 / 18.0 | 2.42 / 2.87 | 45.8 |
| experts | ok | ok | 5 | 0/0 | 21.7 / 15.9 | 2.50 / 3.00 | 45.5 |
| network | ok | ok | 9 | 0/0 | 15.8 / 19.2 | 1.69 / 3.18 | 45.6 |
| institutions | ok | ok | 4 | 0/0 | 21.1 / 18.4 | 2.02 / 4.07 | 45.6 |
| institution | ok | ok | 1 | 0/0 | 18.3 / 14.9 | 2.10 / 2.32 | 45.6 |
| monitoring | ok | ok | 3 | 0/0 | 19.9 / 15.2 | 1.61 / 2.09 | 45.7 |
| funding | ok | ok | 111 | 5/5 | 22.0 / 16.1 | 2.11 / 2.73 | 45.7 |
| evidence | ok | ok | 0 FAIL | 0/3 FAIL | 17.9 / 21.0 | 1.69 / 3.67 | 45.5 |
| policy | ok | FAIL | 0 FAIL | 0/0 | 21.0 / 19.8 | 2.94 / 3.43 | 45.5 |
| resources | ok | FAIL | 0 FAIL | 0/0 | 19.0 / 17.3 | 2.36 / 2.65 | 45.6 |
| about | ok | FAIL | 0 FAIL | 0/0 | 24.1 / 23.2 | 3.59 / 4.68 | 45.7 |
| glossary | ok | FAIL | 0 FAIL | 0/0 | 21.6 / 21.2 | 3.06 / 3.91 | 45.5 |
| expert_profile | ok | ok (`header.site-header`) | 0 FAIL | 0/0 | 36.3 / 36.9 | 1.46 / 34.68 | 45.5 |
| institution_page | ok | ok | 1 | 0/0 | 13.8 / 13.8 | 1.62 / 2.35 | 45.5 |

Probe gaps (not judged, so the font result for these routes is partial):

- Body paragraph on monitoring and network: the probe marks a visible paragraph whose computed CSS family is
  the system-ui stack, but CDP `CSS.getPlatformFontsForNode` returns no fonts for that node. The cause was not
  traced. Institutions was not traced. The body-font gate is therefore not measured on those three routes.
- No `h2` on monitoring and glossary; no visible `button` or `td` on several routes; no sidebar link on
  expert_profile (that page has no Observable sidebar).
- Missing probes are listed in `design_snapshots.json` under `missing_probes`.

Notes on the table:

- **Header:** `.atlas-page-head` is absent on home, policy, resources, about and glossary. home renders its
  hero (`atlas-hero`) instead.
- **Icons:** `svg use[href^="#i-"]` count is 0 on evidence, policy, resources, about, glossary and
  expert_profile.
- **Charts:** the three charts on evidence (Trends, Evidence heatmap, Publications) have no `.atlas-segmented`
  Table control. Trends has no buttons at all. The control was checked in the DOM.
- **Sat%:** the baseline file does not define its saturated share, so the threshold used here is the brief's.
  expert_profile reads 1.46 now against 34.68 at baseline while M is nearly the same (36.3 vs 36.9). That
  mismatch is not explained by this run and needs checking before the saturated column is used.

## Rerun after VD-15, VD-16 and VD-17 (live, `scratch/design_snapshots_v2`)

`py -3.14 scripts/design_snapshots.py --out scratch/design_snapshots_v2` after deploy `7a55aa92`: policy,
resources, about and glossary now report a page header and an icon; evidence charts 3 of 3 with a Table
view (the Publications card, a table itself, is marked `data-kind="table"` and not counted); fonts ok on
every route; design CSS 8,128 B gzip; fonts 45.5 to 45.7 KB. The run still showed evidence with 0 icons
(its eyebrow had none) and home without `.atlas-page-head`: the evidence eyebrow now carries the `grid` nav
icon with sprite injection, and the script accepts the Overview hero (`.atlas-hero`, VD-5) as the page header
(both in the commit that records this rerun). `expert_profile` still has no sprite icon (classic page; UX-13).

## Lighthouse (mobile preset, single run, `scratch/vd12/lh/results.json`)

Gates: performance no more than 3 points below baseline; accessibility at or above baseline; CLS under 0.1.

| Route | Perf now / base | Perf gate | A11y now / base | CLS now / base | LCP now / base (s) | Gates |
|---|---|---|---|---|---|---|
| home | 99 / 93 | pass (+6) | 100 / 100 | 0 / 0.17 | 1.9 / 1.01 | pass |
| experts | 72 / 77 | FAIL (-5) | 100 / 100 | 0.009 / 0 | 5.3 / 2.37 | perf FAIL |
| network | 91 / 80 | pass (+11) | 100 / 100 | 0 / 0 | 2.3 / 1.93 | pass |
| institutions | 65 / 75 | FAIL (-10) | 100 / 100 | 0 / 0 | 6.0 / 1.17 | perf FAIL |
| institution | 79 / 98 (baseline `/institution`, no ID) | FAIL (-19, not like-for-like) | 100 / 100 | 0.008 / 0 | 5.6 / 2.22 | perf FAIL |
| monitoring | 98 / 100 | pass (-2) | 100 / 100 | 0 / 0 | 2.4 / 1.13 | pass |
| funding | 93 / 91 | pass (+2) | 100 / 100 | 0 / 0 | 2.3 / 1.18 | pass |
| evidence | 96 / 77 | pass (+19) | 100 / 96 | 0.088 / 0.037 | 1.8 / 1.2 | pass (CLS close to 0.1) |
| policy | 100 / 100 | pass | 100 / 100 | 0 / 0.031 | 1.6 / 0.99 | pass |
| resources | 100 / 100 | pass | 100 / 100 | 0 / 0 | 1.6 / 0.98 | pass |
| about | 99 / 98 | pass (+1) | 100 / 100 | 0.051 / 0 | 1.9 / 1.34 | pass |
| glossary | 100 / 100 | pass | 100 / 100 | 0 / 0 | 1.6 / 1.0 | pass |

- Accessibility is at or above baseline on all 12 routes (lowest is 100).
- CLS is under 0.1 on all 12 routes (highest is evidence at 0.088).
- Not in this Lighthouse run and not gated: expert_profile and institution_page (the baseline has no Lighthouse
  figures for them either).
- Context from `docs/VD_6C_VERIFICATION.md` (Deployed): a same-machine A/B of the VD-6c build found no
  performance cost, and the unchanged `/policy` measured 1.59 s LCP on 2026-11-16 against 0.99 s at baseline.
  This run's `/policy` LCP is 1.6 s, which matches that drift. The experts and institutions LCP rises (5.3 s and
  6.0 s) and the institution performance drop are not explained by this run. This is a single run per route, so
  they need repeat runs before being attributed to the host or to the pages.

## Font transfer and CSS size

- woff2 transfer per route (desktop, fresh context): 45.5 to 45.8 KB. Gate 60 KB: pass on every route.
- Added global CSS, gzip level 9, each file compressed on its own:
  `design/tokens.css` 1,469 B, `design/shell.css` 2,974 B, `design/components.css` 3,615 B, total 8,128 B.
  Gate 12 KB (12,288 B): pass.

## Colour and token checks

- `scripts/check_design_tokens.py`, first run of this task: `OK: 84 Framework stylesheet hex uses (< 293;
  baseline 183)`, exit 0. The 84 were in `ev_heatmap.css` 29, `ev_table.css` 35, `experts.css` 3,
  `institutions.css` 1 and `monitoring.css` 16. Against the strict gate (0 outside `tokens.css`) that run failed.
- Re-run at the end of this task on the current working tree: `OK: 0 Framework stylesheet hex uses (limit 0;
  293 before VD-1)`, exit 0, and a direct count of 0 outside `tokens.css`. In between, `framework/src/**` and
  `scripts/check_design_tokens.py` gained uncommitted edits (`git status` shows them; this task did not make
  them). The strict zero gate therefore passes on the working tree only. It is not committed and the deployed
  site has not been re-measured against it. The CSS gzip figure above was taken from the working tree at run 4.
- Distinct hex literals in `framework/src/components/*.js` (top level): 3, against a baseline of 53. Pass.
  The three are `#1d2a33`, `#dfe5e8` and `#eef1f2` in `network.js`.

## Gate summary

| Gate | Result |
|---|---|
| Banned faces (Palatino, Times, Arial) | pass on all routes |
| Headings in Barlow, body in system face | pass where probed |
| Page header on every route | pass after VD-15 (Overview hero counts as its header) |
| At least one icon per route | pass after VD-15 and the Evidence eyebrow icon, except classic `expert_profile` (UX-13) |
| Every chart has a Table view | pass after VD-16 (Evidence 3 of 3, Funding 5 of 5) |
| Lighthouse CLS under 0.1 | pass |
| Lighthouse accessibility at or above baseline | pass |
| Lighthouse performance within 3 points of baseline | FAIL: experts (-5), institutions (-10), institution (-19, URL differs) |
| Font transfer at most 60 KB | pass |
| Added CSS at most 12 KB gzip | pass (8,128 B) |
| 0 hex literals outside tokens.css | pass after VD-17 (0; CI ratchet cap 0) |
| Component JS hex count below baseline 53 | pass (3) |
| Colourfulness (information only) | Overview 36.1, inside 25 to 40. Other routes: network 15.8, institution 18.3, evidence 17.9, monitoring 19.9 and institution_page 13.8 are below 20 |

## Screenshots

- `scratch/design_snapshots/<route>_1440_fold.png`: first screen at 1440x900 (fold colourfulness source).
- `scratch/design_snapshots/<route>_390_full.png`: full page at 390x844.
- `scratch/design_snapshots/design_snapshots.json`: all measurements and gate inputs.
- `scratch/vd12/lh/`: Lighthouse JSON per route and ux-audit desktop screenshots (1366 px).

The baseline screenshots are not stored in the repository. The baseline is the metrics in
`docs/design/baseline_2026-11-14.json` and `docs/design/style_tile.html`.

## Owner review (H25): pending

The owner should compare, route by route:

1. `scratch/design_snapshots/<route>_1440_fold.png` against the live site and `docs/design/style_tile.html`
   (the target direction).
2. The first screens after VD-15/16/17 in `scratch/design_snapshots_v2/`.
3. Whether expert_profile and institution_page use the intended entity IDs (I84218800 and A5036007957 are the
   brief's values; the baseline used I97018004 and A5046986222).
4. The saturated-share definition for expert_profile (1.46 now against 34.68 at baseline).

Nothing in this section is a decision. H25 belongs to the owner.
