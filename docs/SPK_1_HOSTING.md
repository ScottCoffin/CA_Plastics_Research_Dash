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

## R2 leg (pending owner steps; the agent never handles Cloudflare credentials)

1. Create an R2 bucket (for example `atlas-data`) in the account that owns `scottcoff.in`.
2. Connect a custom domain to the bucket (for example `data.scottcoff.in`;
   production access requires a custom domain on a zone in the same account).
3. Add this CORS policy to the bucket:
   ```json
   [{"AllowedOrigins": ["https://scottcoff.in"], "AllowedMethods": ["GET", "HEAD"],
     "AllowedHeaders": ["Range"], "ExposeHeaders": ["Content-Range", "Content-Length", "Accept-Ranges", "ETag"],
     "MaxAgeSeconds": 3600}]
   ```
4. Upload `p5/p25/p100.parquet` (regenerate with
   `py -3.14 spikes/spk1_hosting/make_parquet.py <dir>`) to `spk1/` in the bucket.
5. Tell the agent the base URL. It will then run
   `py -3.14 spikes/spk1_hosting/measure.py --base https://data.scottcoff.in/spk1/ --probe <Pages probe URL>?base=https://data.scottcoff.in/spk1/`
   after one more opt-in Pages deploy, which tests cross-origin lazy reads.

SPK-1 stays unchecked until the R2 leg is measured. The Pages-only decision
already stands for files of 25 MB or less.
