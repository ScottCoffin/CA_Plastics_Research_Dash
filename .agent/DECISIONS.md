# Decisions

ADR-style decisions belong here with date, alternatives, rationale, and decision
owner. Unanswered items continue to use the defaults in `spec.md` Part G and
remain listed in `QUESTIONS.md`.

## ADR-003 — 2026-11-05 — Institution API retrieval and usage accounting

- **Decision:** Use OpenAlex `geo.region:California` to seed California
  institutions and canonical `institutions.id` works filters in batches of at
  most 100 IDs. Use cursor paging for large works pulls. Use ROR v2 single-ID
  lookups to enrich known ROR IDs; use the ROR data dump, not exhaustive API
  paging, if a complete registry is needed. Record every API request and each
  run's aggregate credits and USD cost in the ignored JSONL usage log.
- **Alternatives:** Use the longer OpenAlex filter alias; send larger ID lists;
  use basic paging for large works pulls; build a complete ROR registry by
  paging the API; omit zero-cost ROR calls from usage accounting.
- **Rationale:** Live S1.1 tests found equivalent OpenAlex filter results, a
  hard 100-value OR cap, cursor metadata for works, and ROR's documented
  10,000-result retrieval ceiling and paging consistency warning. One shared
  log makes per-run request volume and paid/zero-cost usage auditable.
- **Decided by:** Build agent from verified API behavior under S1.1.

## ADR-002 — 2026-11-05 — Public GitHub Pages hosting and repository configuration

- **Decision:** Keep `ScottCoffin/CA_Plastics_Research_Dash` public and host it
  with GitHub Actions Pages. Permit guarded automation commits through
  `ENABLE_DATA_COMMITS=true`. Use MIT for source code and CC BY for derived data
  when upstream source licenses allow it.
- **Alternatives:** Keep the repository private and upgrade the GitHub plan;
  use alternate hosting; keep automation commits disabled.
- **Rationale:** Public visibility resolves the Pages plan restriction and is
  the owner's chosen G-7 hosting model. The existing guard keeps write-capable
  automation explicit. Per-source license review remains required before
  publishing derived data.
- **Decided by:** Owner answers in `QUESTIONS.md`, verified 2026-11-05.

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
