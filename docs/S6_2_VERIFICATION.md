# S6.2 JATS parser verification

The independently implemented parser extracts bounded evidence from JATS
Methods, Study Area, Sampling, and Data Availability sections. It recognizes
headings and `sec-type`, handles nested and namespace-qualified sections,
preserves section IDs and titles, marks truncation, and returns an explicit
fallback when no requested sections are present. Standalone external DTDs are
preserved without resolution; internal entity declarations, malformed XML, and
non-article roots are rejected.

Acceptance includes ten real-article JATS excerpts and ten synthetic edge
fixtures. Europe PMC metadata marks each real source OA and CC BY; each selected
fullTextXML copy also contains a CC BY license block. The committed fragments
retain author/title/DOI/source attribution and contain at most two snippets of
180 characters per work. Full XML files were downloaded sequentially to
ignored local scratch after license checks, then kept out of Git. Hashes, exact
license blocks, and source references are in
`docs/api_notes/europepmc_s6_2_fixture_provenance.json`.

Parsing the ten complete local XML documents found target sections in 9/10.
PMC13608240 had no target section headings and returned the explicit empty
fallback. Target-section document counts were Methods 8/10, Study Area 1/10,
Sampling 4/10, and Data Availability 7/10. These counts describe only the
selected fixtures, not corpus-wide performance.

Commands:

Final verification for this checkpoint: 148 tests pass, including direct-parser
and cache regressions for an internal entity subset hidden between comment
tokens resembling CDATA delimiters. Ruff lint and format checks pass.

```powershell
py -3.14 -m pytest tests/test_s6_2_jats.py
py -3.14 -m pytest tests/test_fulltext_cache.py
py -3.14 scripts/check_s6_2.py
py -3.14 scripts/build_s6_2_real_fixtures.py  # requires ignored local XML cache
```

See [the parser API note](api_notes/europepmc_jats_parser.md) for the parser
contract and license boundary.
