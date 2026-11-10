# SPK-1 hosting spike: GitHub Pages vs Cloudflare R2 (gate G-HOST)

Contract: [Add-on A1](add_on_spec.md) SPK-1. Owner authorization: ADR-SPK-AUTH-2026-11-09.
Measured 2026-11-10 UTC. Harness: `spikes/spk1_hosting/` (`make_parquet.py`,
`probe.html` with DuckDB-Wasm 1.29.0, `measure.py`). The deploy run was
`gh workflow run build_deploy.yml -f spk1_parquet=true` (run 42762957646); the
files existed only in that Pages artifact and a normal deploy then removed them.

## GitHub Pages (`https://scottcoff.in/CA_Plastics_Research_Dash/spikes/spk1/`)

| File | Size | HEAD | `Range: bytes=0-1023` | `Range: bytes=-8` | CORS | count / filtered agg (ms) | Parquet transfer for both queries |
|---|---:|---|---|---|---|---|---|
| p5 | 4,942,215 | 200, `Accept-Ranges: bytes` | 206 `0-1023/4942215` | 206 | `*` | 519 / 50 | 4 requests, 43,400 B |
| p25 | 24,708,983 | 200 | 206 | 206 | `*` | 31 / 207 | 17 requests, 493,432 B |
| p100 | 98,820,485 | 200 | 206 | 206 | `*` | 39 / 463 | 48 requests, 1,204,614 B |

- No 200 fallbacks occurred: every Parquet response in the browser was a 206
  partial read. No `Content-Encoding` was applied to Parquet.
- Control: Python's `http.server` (no Range support) returned 200 for every
  request, and DuckDB-Wasm downloaded each file in full twice (197.6 MB for
  p100). The harness therefore distinguishes the two cases.
- Headless Chromium 145 on the owner's desktop network; the first file's count
  includes DuckDB-Wasm warm-up. Single run; timings are indicative.

## Decision (contract rule)

"Pages 206 + CORS → Pages only until a file exceeds 25 MB." **G-HOST = GitHub
Pages only** while every served Parquet is at most 25 MB. Cloudflare R2 remains
the planned scale lever for larger files (A1-D4 default accepted). GitHub Pages
itself served 100 MB with ranges, but A1 keeps the 25 MB threshold for
Cloudflare portability, and git and Pages artifacts are a poor home for large
binaries.

## Cloudflare R2 (`https://data.plastiverse.live/spk1/`, measured 2026-11-10 UTC)

The owner created the bucket, connected the custom domain `data.plastiverse.live`,
set CORS, and uploaded the files (the agent never handled Cloudflare credentials).
The uploads are regenerated files, so their sizes differ slightly from the Pages copies.

| File | Size | HEAD | `Range: bytes=0-1023` | `Range: bytes=-8` | CORS (`Origin: https://plastiverse.live`) | count / filtered agg (ms) | Parquet transfer for both queries |
|---|---:|---|---|---|---|---|---|
| p5 | 4,941,420 | 200, `Accept-Ranges: bytes`, ETag | 206 `0-1023/4941420` | 206 | allowed; exposes `Content-Range,Content-Length,Accept-Ranges,ETag` | 1,943 / 238 | 4 requests, 42,605 B |
| p25 | 24,704,942 | 200 | 206 | 206 | allowed | 146 / 1,402 | 16 requests, 440,239 B |
| p100 | 98,805,090 | 200 | 206 | 206 | allowed | 264 / 5,243 | 55 requests, 1,566,051 B |

- Every browser Parquet response was a 206; no 200 full-file fallback occurred.
- Cross-origin reads were measured from `https://plastiverse.live`, which the bucket
  allows. That origin hosts no site (Cloudflare 522), so the harness served the local
  `probe.html` there by Playwright request interception (`--serve-origin-probe`):
  `py -3.14 spikes/spk1_hosting/measure.py --base https://data.plastiverse.live/spk1/ --origin https://plastiverse.live --probe "https://plastiverse.live/spk1-probe.html?base=https://data.plastiverse.live/spk1/" --serve-origin-probe`.
  The browser still applies real CORS against R2; only the HTML document is local.
- Headless Chromium on the owner's desktop network; single run; timings are indicative
  (the first count includes DuckDB-Wasm warm-up).
- On 2026-11-10 the site moved to the repo custom domain `https://plastiverse.live/`
  (old `scottcoff.in/CA_Plastics_Research_Dash/` paths return 301). From the live page
  origin, Chromium `fetch` with `Range: bytes=-8` returned 206 with the exposed
  `Content-Range` and `ETag` and the Parquet `PAR1` footer for p5 and p100. The
  bucket's CORS policy (`https://plastiverse.live` only) therefore already matches
  the production origin.

## Result

SPK-1 is closed. G-HOST stands: GitHub Pages serves every Parquet file of 25 MB or
less. Cloudflare R2 at `data.plastiverse.live` is a verified scale lever for larger
files: it serves 206 range reads with exposed headers, and DuckDB-Wasm read 1.6% of a
99 MB file. No further configuration is needed before production use.
