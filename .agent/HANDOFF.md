# Handoff — 2026-11-17 — owner feedback rounds (VD-27..VD-35), EM-17, daily ingest repair

## Done this run (all committed, pushed, CI + deploy green)
- VD-27..VD-31: favicon/brand mark (base64; Framework double-escaped percent-encoded hrefs), full-width text rules, Funding heatmap filtering, Experts/Network filters, network mobile (VD-28), viewport-clamped tooltips (VD-29), homepage map spring intro on every load (VD-30, Web Animations; Motion dropped at 64 KB gzip), creator credit replaces the disclaimer/disclosure (VD-31, ADR-CREDIT-2026-11-17).
- EM-17 partial: 22 OPC early actions panel + review app (owner review H28 pending).
- VD-32..VD-35: Related resources icons (13/13) and steward institution links; no repo links on the site (corrections mailto theplastiverse@gmail.com); Evidence journal filter + "2-yr mean citedness (OpenAlex)" column (`site/data/journal_metrics.json`); owner logos; compact page heads.
- Ingest: OpenAlex made `from_updated_date` a paid filter (HTTP 403 "Plan upgrade required" 2026-11-16/17). Incremental runs now use `from_publication_date` with an adaptive lookback (max(30, gap+7), cap 366), Sunday 180-day deep sweep, `OpenAlexPlanError`, and a "Daily ingest failing" issue (label `ingest-alert`) that the next success closes. Institution types and journal metrics rebuild after the export. Owner's missing paper (doi 10.1021/acsestwater.6c01560) is now on the site.

## Open findings
- Plan refusals returned as HTTP 429 still defer without an alert; failures after a good refresh do not alert.
- Push notifications: options A (feed/email), B (ntfy topic), C (PWA web push via Cloudflare Worker) proposed; owner to choose.
- `.agent/MEMORY.md` is over 200 lines; compact at a quiet checkpoint.

## Next eligible
- VD-26 (finish review, DESIGN.md); push-notification task once the owner picks an option.

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- Confirm the DTSC logo source (origin pfasproject.com file; the i0.wp.com link returned 404) and the Land to Sea logo on its resource card.
- Choose a notification option (A feed/email, B ntfy, C web push).
- H27: tick Enforce HTTPS once GitHub finishes the certificate.
