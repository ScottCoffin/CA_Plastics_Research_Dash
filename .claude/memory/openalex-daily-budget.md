---
name: openalex-daily-budget
description: "Owner's standing rule that OpenAlex calls may use the full free USD 1/day allowance"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f4088465-74c3-42ab-9a02-fb224f2ea3b7
  modified: 2026-11-11T15:26:51.170Z
---

OpenAlex may run up to the $1/day free limit, every day, not only on the day it was said (owner, 2026-11-11).

**Why:** the earlier $0.25 local stop blocked the v3.1 backfill and the Experts tab stayed on fixture data.
**How to apply:** `config/budget.yml` stops at 0.95 USD; check remaining allowance for free via GET `https://api.openalex.org/rate-limit` before large pulls; still route calls through the budget guard and never use paid/prepaid credit. Related: [[overnight-mode]].
