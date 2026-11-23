# BQ-V.0 Sigma.js benchmark (gate)

Run date: 2026-11-22. Spike only. Synthetic graph, one laptop, headless Edge.

## Result in brief

- Desktop: 20,000 nodes meets both targets. 60,000 nodes is fast enough to start, but drops to about 28 fps. 150,000 nodes misses both.
- Mobile emulation: 5,000 nodes meets both targets, with a thin fps margin. 20,000 nodes and up miss both. 150,000 nodes took 17 to 27 s to become interactive.
- No run crashed or timed out. All 24 runs finished.
- Proposed N_MAX: **desktop 20,000 nodes**. **Mobile 5,000 nodes**.
- Owner decision A3-Q10 (2026-11-18): start at 60,000 and refine after shipping. On this laptop 60,000 nodes starts in 1.4 s but pans at about 28 fps, just under the target, so the desktop default stays 60,000. On phones 60,000 nodes took about 11 s and ran at about 3 fps, so the default in use for phones is 5,000 nodes (QUESTIONS A3-Q10b) until the owner says otherwise.

Targets (A3): time to interactive at most 3 s, at least 30 fps, no crash.

## Machine and browser

| Item | Value |
|---|---|
| OS | Windows 11 Pro, 10.0.26100 |
| CPU | 13th Gen Intel Core i7-1365U, 12 logical CPUs |
| RAM | 63.6 GB |
| GPU (as seen by Edge) | Intel Iris Xe Graphics, ANGLE on Direct3D 11, WebGL 2.0 |
| Browser | Microsoft Edge 158.0.4370.33, launched by Playwright 1.58.0 (`channel="msedge"`, headless) |
| Python | 3.14.0 (`py -3.14`) |
| Libraries | sigma 3.0.3, graphology 0.26.0 (same versions as `framework/src/components/network.js`) |

sigma and graphology are not in `framework/node_modules`. The runner loads them from the Observable npm cache (`framework/src/.observablehq/cache/_npm`). That cache is what the site build uses. No package was installed.

## Method

- Runner: `scripts/bench/bq_v0_sigma_bench.py`. Page: `scripts/bench/bq_v0_sigma_bench.html`.
- The runner serves the bench folder and the npm cache on 127.0.0.1 only. It makes no other network calls.
- Graph: synthetic and seeded (mulberry32, seed 20261122). Mean degree 6. 50 clusters, 90% of edges stay inside a cluster. Random preset x/y positions, no layout run. Node sizes follow a skewed degree (Pareto-like node weights). Each node has a label.
- Renderer settings match the site (`createRenderer` in `network.js`): label density 0.07, label grid 70, camera ratio 0.02 to 5.
- Time to interactive (TTI): starts when the graph data is in memory. It includes building the graphology graph, creating the sigma renderer, the first presented frame, and one frame triggered by a real wheel event (zoom). Generating the synthetic arrays is not timed.
- FPS: frames sigma renders during a 4 s scripted pan and zoom. The camera moves once per animation frame.
- Desktop: 1280 x 800, scale 1, no throttling.
- Mobile emulation: Playwright "Pixel 7" profile (412 x 915, scale 2.625, mobile user agent), with CDP `Emulation.setCPUThrottlingRate` set to 4.
- Each size and mode ran 3 times. The table shows the median. A failed run would stop repeats. No run failed.
- Run limit: 60 s per run. The slowest run took 39 s of wall time (mobile 150,000 nodes).
- Not measured: network fetch and JSON parsing of real data. A real page will be slower by that amount.

## Results

Desktop (1280 x 800, no throttling)

| Nodes | Edges | TTI median (ms) [3 runs] | FPS median [3 runs] | Meets both targets |
|---:|---:|---|---|---|
| 5,000 | 15,000 | 139 [210, 139, 129] | 59.8 [59.8, 59.8, 59.8] | Yes |
| 20,000 | 60,000 | 270 [336, 270, 257] | 59.8 [59.8, 59.8, 59.1] | Yes |
| 60,000 | 180,000 | 1,424 [1,233, 1,424, 1,449] | 27.9 [29.0, 27.9, 26.8] | No (fps) |
| 150,000 | 450,000 | 3,737 [3,427, 3,989, 3,737] | 13.3 [13.3, 12.6, 13.4] | No (TTI and fps) |

Mobile emulation (Pixel 7 profile, 4x CPU throttle)

| Nodes | Edges | TTI median (ms) [3 runs] | FPS median [3 runs] | Meets both targets |
|---:|---:|---|---|---|
| 5,000 | 15,000 | 750 [750, 852, 735] | 31.8 [31.8, 32.5, 31.0] | Yes (thin fps margin) |
| 20,000 | 60,000 | 2,555 [3,301, 2,544, 2,555] | 9.6 [10.0, 9.0, 9.6] | No |
| 60,000 | 180,000 | 10,872 [11,110, 10,872, 10,647] | 2.7 [3.0, 2.7, 2.7] | No |
| 150,000 | 450,000 | 23,550 [26,865, 17,486, 23,550] | 1.2 [1.2, 1.2, 1.1] | No |

Where the time goes (medians, ms)

| Nodes | Desktop: graph build | Desktop: sigma init | Desktop: frame time | Mobile: graph build | Mobile: sigma init | Mobile: frame time |
|---:|---:|---:|---:|---:|---:|---:|
| 5,000 | 27 | 76 | 16.7 | 256 | 393 | 30.2 |
| 20,000 | 92 | 141 | 16.7 | 1,316 | 1,182 | 93.1 |
| 60,000 | 610 | 724 | 33.5 | 6,335 | 4,274 | 368.1 |
| 150,000 | 2,314 | 1,316 | 72.8 | 14,862 | 5,720 | 785.9 |

Graph build is the largest share of TTI at the top sizes. At 150,000 nodes on desktop it is about 60% of TTI. Build means creating the graphology graph from the arrays.

Desktop frame time sits at the 60 Hz display cap (about 16.7 ms) up to 20,000 nodes. So the 59.8 fps there is a cap, not a measured limit. Headroom above 20,000 nodes is not known.

## Crashes and timeouts

- None. All 24 runs status "ok". No page errors or console errors were logged.
- Every run passed the wheel-zoom interaction check (the wheel event produced a new frame and changed the camera).

## Proposed N_MAX

- Desktop: **20,000 nodes**. Largest tested size that meets both targets. TTI is about 0.3 s, well under 3 s. The fps is at the display cap. The true limit is somewhere between 20,000 and 60,000. Sizes in between were not tested.
- Mobile emulation: **5,000 nodes**. Largest tested size that meets both targets. The fps margin is small (31.8 against 30). Mobile needs its own check on a real phone before any higher limit is used.

## Caveats

- Headless Edge on one laptop (i7-1365U, Intel Iris Xe). Other GPUs and phones will differ.
- The Pixel 7 run is an emulation, not a phone. The 4x CPU throttle and the 2.625 device scale are estimates. The high device scale makes each frame fill more pixels, so the mobile numbers mix CPU and GPU effects.
- Synthetic graph: random positions and random edges. Real layouts may draw differently. Labels are on, as on the site.
- Data fetch and JSON parse are not timed. Real TTI will be higher.
- Three runs per point. Medians only, no confidence intervals.
- Raw results: `scratch/bq_v0/results.json` and `scratch/bq_v0/run.log` (scratch is gitignored). Rerun with `py -3.14 scripts/bench/bq_v0_sigma_bench.py`.
