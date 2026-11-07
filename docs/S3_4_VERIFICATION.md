# S3.4 verification

The Institutions tab derives its metrics from the S3.1 work index. Only rows
with `plastic_related: true` count as tagged works. The leaderboard shows all
qualifying institutions, type chips filter it without a reload, and each row
has all-time and latest-five-year counts plus an accessible SVG sparkline.

The map is intentionally dependency-free for the static MVP. California rows
with valid OpenAlex coordinates are projected into a schematic view and grouped
with a small client-side grid clusterer. Keyboard-accessible markers and
leaderboard buttons write the existing `#experts?institution=<id>` hash, so the
S3.3 Experts filters and lazy researcher drawer remain the single destination.
Rows without coordinates remain in the leaderboard and are counted in the map
note rather than being discarded.

## Checks

```powershell
py -3.14 scripts/check_s3_4.py
py -3.14 scripts/check_s3_3.py
py -3.14 scripts/check_s3_2.py
C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test
```

The fixture acceptance found three qualifying institutions, rendered the UC
marker, filtered the leaderboard to `UC`, followed `View experts` to the
institution hash, and opened Alice's existing S3.3 researcher drawer. The
browser smoke used WSL Node 20.20.2/Chromium and an HTTP-served `site/` tree;
the only console errors were the expected missing `favicon.ico` requests.
