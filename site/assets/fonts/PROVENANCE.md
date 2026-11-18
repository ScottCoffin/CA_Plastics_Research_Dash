# Brand font provenance (Plastiverse Live, PLAT-2)

Both faces are SIL Open Font License 1.1 and are self-hosted like Archivo (owner approval
2026-11-17, PLAT2-FONTS). Neither upstream declares a Reserved Font Name, so the modified
(instanced and subset) files keep the upstream family names.

Rebuild from the repository root, with fonttools and brotli supplied by uv:

    uv run --no-project --with fonttools --with brotli python -I scripts/build_brand_fonts.py

Add `--offline` to reuse the cached upstream files in `data/raw/fonts/` (ignored by git).
`tests/test_brand_fonts.py` checks the committed outputs offline.

## Schibsted Grotesk (body and headline text)

- Output: `SchibstedGrotesk-Variable-latin.woff2`, 45,928 bytes (target 45 KB = 46,080 bytes),
  sha256 `cfe6a6e329797038de25e0a5bcb9d9ad5b59c5694e6477fe7851ee35813a501a`
- Upstream: https://github.com/google/fonts/tree/main/ofl/schibstedgrotesk
  (project: https://github.com/schibsted/schibsted-grotesk)
- Pinned file: https://raw.githubusercontent.com/google/fonts/cc054e5ee906ac9b9024971b64d821aa2561c582/ofl/schibstedgrotesk/SchibstedGrotesk%5Bwght%5D.ttf
  (google/fonts commit `cc054e5ee906ac9b9024971b64d821aa2561c582`; git blob `78ad61cf65a390c517248f46d325a1e9b88d367d`)
- Upstream sha256: `6ceeadf6be8e1fd7687011c7fa38ed0edd1abe967a0b73d97caec183552e823d` (176,068 bytes)
- Axes kept: `wght` limited to 400-700 (upstream 400-900); the font stays variable. Default 400.
- Subset: the Archivo `unicode-range` from `framework/observablehq.config.js`, plus U+2192
  (rightwards arrow, used by the landing page and absent from the Archivo range). All layout features kept.
- Licence: `OFL-SchibstedGrotesk.txt`, byte-identical to upstream `OFL.txt`
  (sha256 `3b4f3063b6ac7c1e403e2c4a5e8ef3a58190ff83ed7b15af66511858699139ce`).

## Martian Mono (data labels and source lines only)

- Output: `MartianMono-Regular-latin.woff2`, 10,112 bytes (target 30 KB = 30,720 bytes),
  sha256 `8dd28767027354986cfcc38d6f499ff24723693bde481b31211ea8ae3cfcf3fc`
- Upstream: https://github.com/google/fonts/tree/main/ofl/martianmono
  (project: https://github.com/evilmartians/mono)
- Pinned file: https://raw.githubusercontent.com/google/fonts/1386d6284a09c9c25d8c1db08717d6e42a44867d/ofl/martianmono/MartianMono%5Bwdth,wght%5D.ttf
  (google/fonts commit `1386d6284a09c9c25d8c1db08717d6e42a44867d`; git blob `1dbec63b6d3a76f0eb2d63f3a6f921efbe66769c`)
- Upstream sha256: `c3467843ec1c2574b05fbcfd7147c7bfbcf63ddca8fc2bcb9d117f1bfb1b22e7` (148,460 bytes)
- Axes kept: none. Static instance at wght 400 and wdth 87.5 (upstream wght 100-800, wdth 75-112.5).
  The output has no `fvar` table, and the instancer renames it "Martian Mono SemiCondensed" (usWidthClass 4).
- Subset: same as Schibsted Grotesk.
- Licence: `OFL-MartianMono.txt`, byte-identical to upstream `OFL.txt`
  (sha256 `ddafd2c3f37ef1d83ef284ca63e159befd3820850c5e9eded14ca52eee92c256`).

## Build notes

- Tools: fontTools 4.68.0 with brotli, run through `uv run --no-project`. Nothing is installed globally or added to `pyproject.toml`.
- Instancing: `fontTools.varLib.instancer.instantiateVariableFont(..., updateFontNames=True)`.
- Subsetting: `fontTools.subset` with `flavor="woff2"` and `layout_features=["*"]`.
- Reproducibility: `head.modified` is kept from upstream (`recalcTimestamp` off). Two rebuilds
  with the same fontTools and brotli give identical bytes.
- Output sizes and sha256 values depend on the fontTools and brotli versions. After any
  upgrade, rebuild, check the size targets and update this file.
- The upstream files are checked against the sha256 values pinned in the script.
  Archivo and Barlow are documented in `docs/REUSE.md`.
