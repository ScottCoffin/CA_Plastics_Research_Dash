# Landing story prototype: sources

These are the sources for the "Spectral Match" scroll-story prototype in `../spectral_story.html`.
It is a design prototype for the global landing page (PLAT-2), not production code.

## Rebuild

Run from the repo root:

```bash
# 1. After editing story_engine7.js or the patch, regenerate the template
cd .impeccable/sketches/src && py -3.14 -I patch_beats5.py . && cd -
# 2. Fill the data placeholders and write the page
py -3.14 -I .impeccable/sketches/src/story.py . .impeccable/sketches/spectral_story.html
```

## Preview

The canvas reads image pixels, so the page has to be served over HTTP; opening it from `file://` does not work:

```bash
cd .impeccable/sketches && py -3.14 -m http.server 8765 --bind 127.0.0.1
```

Then open http://127.0.0.1:8765/spectral_story.html.

## Screenshots

`snap3.py <url> <outdir> <w> <h> <units>` captures beats and writes a contact sheet to `<outdir>`.
The units are scroll units; `TOT` must match the engine's `TOT`.

## Files

| File | Purpose |
|---|---|
| `story_template.bak3.html` | Base page: styles, sections and pickers |
| `story_engine7.js` | Story engine: timeline `TU`, picnic fracture, mandala, bulb, chart, map |
| `patch_beats5.py` | Splices the engine, captions, theme, header and footer into the base, then writes `story_template.html` |
| `story.py` | Fills in OpenAlex trend data (`site/data/trend_global.json`) and the geography rasters |
| `sketchlib.py`, `geo/world.json`, `build_geo.py` | Natural Earth world and California geometry (Equal Earth projection) |
| `scan_cc.py`, `render_papers.py`, `redact_papers.py`, `cc_papers.json` | Find the CC BY papers in Zotero, render their first pages, and redact download stamps |

## Assets

- `../scene/blanket.png` and `../scene/picnic_items.png` were generated with gpt-image-2.6-sunburst. The prompts are in the `.json` sidecar files.
- The web copies in `../scene/web/` are the files the page loads.
- Paper first pages are in `../papers/web/`, with their licence evidence in `../papers/credits.json`.
- The logo is `src/Plastiverse Live_ From Pollution to Progress.png`. To make a variant, use the prompt in `src/plastiverse_logo_gen_prompt.md`.
