# Decisions

ADR-style decisions belong here with date, alternatives, rationale, and decision
owner. No owner-confirmed decisions have been recorded. Until then, the defaults
in `spec.md` Part G apply and remain listed in `QUESTIONS.md`.

## ADR-001 — 2026-11-05 — Bootstrap automation cadence and guards

- **Decision:** Deploy the static `site/` directory with official GitHub Pages
  actions after every main-branch push, by manual dispatch, and daily at 10:15
  UTC. Check for a missed run daily at 11:47 UTC and redispatch when the latest
  run is at least 25 hours old. Make the monthly keepalive commit only when
  `ENABLE_DATA_COMMITS` is exactly `true`.
- **Alternatives:** Deploy only on pushes; use an external watchdog; use a
  third-party keepalive action; allow unguarded automated commits.
- **Rationale:** This implements the Observable and Job_Scraper patterns named
  in the spec while using off-peak cron minutes, least-privilege permissions,
  and no new third-party workflow dependency.
- **Decided by:** Build agent under the S0.2 implementation contract; owner may
  revise the cadence later.
