# Wikidata and Commons photo metadata for experts (S9.5(2))

Date: 2026-11-11. Status: metadata only. No image was downloaded and nothing
was published to `site/`. The owner must review every row before any photo is
displayed. Wikidata P496 (ORCID iD) links can point at the wrong person.

## Counts (full run, 1,605 ORCIDs)

- Experts with an ORCID in `site/data/index.json`: 1,605 of 2,426 authors. All
  parsed as valid bare ORCIDs.
- ORCIDs queried against Wikidata: 1,605 (9 SPARQL batches of at most 200).
- Expert rows with a Wikidata item (P496 match): 843.
- Rows with an image (P18): 44. All 44 have a Commons thumb and a name match.
- Usable (open licence, name match, thumb): 44.
- Licence breakdown for the 44 images:
  - CC BY-SA: 29 (CC BY-SA 4.0: 21; 3.0: 5; 2.0: 3)
  - CC BY: 8 (CC BY 2.0: 6; 3.0: 2)
  - Public domain: 6
  - CC0: 1
  - Excluded (not usable): 0
- Attribution required (`AttributionRequired`): 37 of 44 true.
- Name mismatches among the 843 items: 17. 14 have no English label (the
  label is the QID, so the match cannot be judged). Three have a real label
  that does not share the family name and need review:
  - A5008249397, Q90909359, "Emilia Laing"
  - A5076477801, Q93031999, "Vera Smirnova"
  - A5077663125, Q92189641, "Sarah Simko"

Limit check (`--limit 50`): 50 ORCIDs, 27 items, 3 images, 3 usable (all CC BY-SA).

## Method

- Wikidata SPARQL (`https://query.wikidata.org/sparql`, POST, `format=json`)
  with the VALUES query built in `src/atlas/ingest/wikidata_photos.py`. Batches
  of at most 200 ORCIDs. Requests are at least 1 s apart.
- For each ORCID, the item is the one with an image if several exist, otherwise
  the lowest QID. The stored image is the first P18 file in sorted order.
- Commons API (`action=query`, `prop=imageinfo`, `iiprop=extmetadata|url`,
  `iiurlwidth=240`), batches of at most 50 titles, at least 1 s apart. Kept:
  LicenseShortName, LicenseUrl, Artist and Credit (HTML stripped),
  AttributionRequired, the 240 px thumb URL and the description URL.
- User-Agent: `CAPlasticsAtlas/0.1 (https://github.com/ScottCoffin/CA_Plastics_Research_Dash)`.
- Licence classes: CC0, PD (Public domain, PD-*), CC BY, CC BY-SA. NC and ND
  variants, fair use and "All rights reserved" are `other` and never usable.
  The licence short name decides; the URL is used only if the name is empty.
- Name match: accents and case are folded. The family name is the last token
  (or the part before a comma). It matches when either family name appears
  among the other name's tokens, which tolerates compound surnames.
- `usable` is true only when the licence class is open, `name_match` is true and
  a thumb URL exists.

## Outputs

- `data/processed/expert_photos.parquet`: one row per queried author (1,605
  rows). Columns: author_id, orcid, wikidata_qid, wikidata_label, name_match,
  image_file, license_short, license_url, artist, credit,
  attribution_required, thumb_url, description_url, usable, fetched_at.
- Raw responses: `data/raw/wikidata/` (gitignored). Each file keeps the
  request result with its fetch time. The cache key is a hash of the exact
  request, so `--offline` replays the same responses. Rebuilding offline
  reproduced the online Parquet byte for byte.
- Command: `py -3.14 scripts/fetch_wikidata_photos.py [--limit N] [--offline]`.

## Caveats

- P496 links can be wrong. The name match is a heuristic on the family name
  only. The owner must confirm identity before display.
- No English label means no name check. Those items are flagged as mismatches.
- Only the first P18 image is used. Experts with several Wikidata images are
  not fully covered.
- Cached Commons and Wikidata responses never refresh on their own. To refresh,
  delete the matching file in `data/raw/wikidata/` and re-run online.
- Licence and attribution fields are copied from Commons metadata as of the
  fetch time. Re-check the licence on Commons before display.
- Thumb and description URLs point at Wikimedia servers. No image file was
  downloaded.
