# Gold release policy (BQ-G6)

Gold sets are the human-labelled reference sets under `curation/` (for example the A3 global
gold round). This policy says when a gold set counts as released, how a released set is protected,
how it is corrected, and what is published.

## Status

Nothing is released today. Labelling is in progress (H39, first global gold round). The release
manifest `curation/gold_releases.json` has an empty `releases` list, and
`py -3.14 scripts/check_gold_releases.py` prints "no gold release yet; nothing to protect".

## What "released" means

A gold set is released only when `curation/gold_releases.json` lists it in `releases`. Each entry
records:

- `version`: for example `gold_v1`. Unique across the manifest.
- `files`: an object that maps each repo-relative file path to its sha256 (lowercase hex).
- `release_date`: ISO date (YYYY-MM-DD).
- `licence`: `CC BY-NC 4.0` (owner 2026-11-25: all labels and data in this repo; `LICENSE-DATA.md`).

Labels in `curation/annotations/` are not released until they appear in the manifest. Until then
they may change freely.

## Immutability

- Once listed, a released file never changes. `scripts/check_gold_releases.py` recomputes each
  file's sha256 and fails, naming the file, when it is missing or has changed. It runs in CI.
- A file path, once released under one version, is never reused by a later version.
- Version strings are unique.

## Corrections

Corrections never edit a released file in place. They go into a new version:

1. Copy the affected files to new paths (for example `gold_v1.1`), apply the corrections there,
   and keep the old files untouched.
2. Add a changelog entry to this policy under "Changelog" that names every changed work ID and the
   reason for each change.
3. Add the new version to `curation/gold_releases.json` with the new paths and their sha256
   values, using the same `release_date` and `licence` fields.
4. Run `py -3.14 scripts/check_gold_releases.py` and the full gate before committing.

The manifest is edited by hand. There is no release helper script; these steps are the procedure.

## What is published

A published gold release contains:

- work IDs (OpenAlex work IDs or the project's internal work keys);
- labels (the adjudicated values);
- short excerpts of at most 300 characters, the evidence snippets only;
- the labeller role (for example "annotator" or "adjudicator"), never a name.

A release never contains personal data, full abstracts, or full titles where they are not needed
for the excerpt. Full-text sources are not redistributed.

All published gold files are licensed under **CC BY-NC 4.0**, like every label and data file in this
repo (owner 2026-11-25, superseding A3-Q9's CC BY 4.0; `LICENSE-DATA.md`). The licence text is at
https://creativecommons.org/licenses/by-nc/4.0/. Commercial use is not permitted.

## Where a release is published

A release is published as a Zenodo deposit (H6 / BQ-9). Not now: no release exists, and the Zenodo
step waits for the first gold release.

## Agreement statistics

Each release is accompanied by agreement statistics computed from the labelling rounds it covers
(inter-annotator agreement and the adjudication counts). The statistics are published with the
release, not as a separate untracked file.

## Changelog

- No releases yet.
