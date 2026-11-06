# Project Progress

## Goal

Complete exactly S2.3: deterministic provisional plastic-relevance and domain
tags, with coverage evidence, then stop before S2.4.

## Overall Progress

S2.2 remains the last completed roadmap task. S2.3 discovery and contract
design are complete, but implementation was paused before code changes because
the session token budget was nearly exhausted.

## Current Position

The agreed design writes a separate `work_labels` Parquet, preserves the S2.2
normalized schema and reviewed institution registry, joins raw OpenAlex records
only for topic display names, and keeps `plastic-v2-candidate` unpromoted. The
exact continuation checklist is in `.agent/HANDOFF.md`; no S2.3 tests, commit,
or push were performed.

## Next Milestone

Resume S2.3 from the handoff, implement and verify the bounded rule-labeling
package, complete B4 records, commit and push only S2.3, and stop before S2.4.
