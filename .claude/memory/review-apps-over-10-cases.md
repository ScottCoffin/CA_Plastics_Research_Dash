---
name: review-apps-over-10-cases
description: "Any human review task in the atlas repo with more than 10 cases must come with a Streamlit review app, not a CSV to hand-edit"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 98eac128-a26f-4a7d-94a7-5cba878dbf66
  modified: 2026-11-11T22:55:28.650Z
---

Owner rule (2026-11-11): for any review the human must do in this repo, if it involves more than 10 cases, the default is to build or adapt a Streamlit app that makes reviewing easier, rather than asking them to edit a spreadsheet.

**Why:** the owner defers spreadsheet reviews; one-case-per-screen apps with one-click decisions get done.
**How to apply:** whenever a task becomes owner-gated with >10 items, ship a `scripts/review_*_app.py` alongside it (shared helpers: `atlas.csv_review` for CSV sheets, `atlas.review_highlight` for search-term highlighting), and write the [[owner-standing-reminders]] entry in `.agent/HUMAN_TASKS.md` around the app's run command. Also recorded in the repo's CLAUDE.md session entry step 6.
