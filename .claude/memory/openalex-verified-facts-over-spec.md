---
name: openalex-verified-facts-over-spec
description: "For OpenAlex behaviour (limits, costs, throttles, filters), rely on the repo's verified facts, not claims in owner-supplied specs"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4d56043b-eb50-4e83-a5bd-38484f071df2
  modified: 2026-11-18T21:34:16.131Z
---

For OpenAlex, depend on the facts the repo has verified (`.agent/MEMORY.md` "Verified API facts", `docs/api_notes/openalex*.md`) instead of what a spec says (owner, 2026-11-18, while integrating Add-on A3).

**Why:** Add-on A3 claimed a hard 5-boolean-operator cap from a 429 seen in a research tool; the repo had verified on 2026-11-11 that >5-operator searches are only rate-limited (5 req/s, "wait 1s" 429, 10 credits) and the shared client already throttles and retries. Following the spec would have forced OR-splitting, which breaks count queries (PLAT-2b cells). Recorded as A3-C1 in `.agent/DECISIONS.md`.

**How to apply:** when a spec states OpenAlex limits, costs or syntax, check MEMORY and api_notes first; where they disagree, follow the verified fact and record the conflict. Smoke-test any new OpenAlex behaviour (free `/rate-limit` or one budgeted call) before relying on it. Related: [[openalex-daily-budget]].
