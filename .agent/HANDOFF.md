# Handoff — 2026-11-26 — AMB-1 slice 3 live; BQ-V.1/BQ-V.4 done; CG-0 (A4 integrated), CG-5, REG-CA done; global co-authors built

## State in one paragraph
The signed-in ambassador dashboard's three "Coming next" cards are now real screens, each its own module mounted by
`components/ambassador_workspace.js`: "Add local knowledge" (`ambassador_knowledge.js`; 11 knowledge kinds from the live
Worker; policy dates and group area folded into the reviewer note), "Notification settings" (`ambassador_settings.js`;
reminders and news switches that save on change) and "Invite your co-authors" (`ambassador_invite.js`; California
co-author list with eligibility, one invitation link per visit, mailto draft or copy, never an email address). Links in
the mails now land: `#notifications` opens settings and the reminder's `?region=&case=` opens that case. No Worker change,
no deploy of the Worker needed. Three Haiku workers built the modules in parallel; the lead wired them, fixed a
double-listed sent item, ran a mocked browser walk (axe 0 on every screen at 1440 and 390 px) and the full gate in a
clean worktree (3,457 passed). Spec: `docs/AMBASSADORS_SPEC.md` "Front end slice 3". CI and the Pages deploy passed; the new modules are served live.
Then BQ-V.1 slice 3: `scripts/build_global_works_graph.py [--check]` writes `site/data/global/graphs/works*.json`,
`layout_works.bin` and its own `works_manifest.json` (15,000 most cited backbone works, k=5 bge-small cosine, 60,000
edges, phone 5,000 / k=3, 51 communities, 37 non-English works marked low). The `ml` extra is now installed on this
machine. Cached rebuild about 4 minutes, byte-identical. Docs: NETWORK_BUILD §16c, SITE_DATA, DATA_DICTIONARY.

## In flight / next (in this order)
1. After the Pages deploy: open https://plastiverse.live/ambassadors signed in and check the three screens on the live
   site (one real knowledge item into the moderation queue, toggle a setting, copy an invitation).
2. AMB-1 build order step 5: pilot with Norway and Belgium (needs local leads; owner).
3. Done this session: REG-CA (`site/data/california/region.json`), CG-0 (A4 integrated, ADR-A4-INTEGRATION),
   CG-5 (`docs/ambassador_infrastructure.md`), AMB-COAUTHORS-GLOBAL built (`GET /me/coauthors`; deploy waits for H54).
   CG-1, CG-4, CG-2, CG-3 done; WORKS-FILTER done; Worker cbc9e050 deployed (global co-authors). Roster published:
   `site/data/global/groups/roster.json` (2,708 organisations, 143 countries); CG-9 done (groups.json + derived files);
   CG-8 approved (H55, A4-D25..D27); CG-13 `/groups` page done. Next: CG-6 (Worker tagging stream; deploy go-ahead),
   then CG-10..12b views; owner-queued AMB-NAV, AMB-CHOICE-CUES, AMB-FULLWIDTH
   (small, front end), AMB-PARENT-REGION, AMB-MAIL-STYLE, ALERTS-GLOBAL; BQ-S9b, BQ-G3. Rebuild denominators.json at the next global
   data refresh (owner).
4. Design-led, waiting on owner review (H25): VD-SM, UX-13 part b.

## Open findings
- `tests/test_bq24_denominators.py::test_check_mode_on_committed_file_exits_zero` fails on this machine's working tree
  (local ignored data makes `denominators.json --check` differ) but passes in a clean worktree of HEAD. Not caused by
  this checkpoint; rebuild `site/data/global/denominators.json` on the next global data refresh.
- `california/region.json` does not exist, so the dashboard's "Confirm the region page" is empty for California
  (a 404 in the console); Norway and Belgium have one.
- New defaults in QUESTIONS: AMB-KNOWLEDGE-EXTRAS, AMB-BADGE-HIDE, AMB-COAUTHORS-SCOPE, WORKS-GRAPH-SELECT.
- Earlier findings still open: `check_s2_2.py`/`check_s3_1.py` assert a fixture id against local data;
  `network_metrics.json` goes stale when `index.json` changes; Evidence filter contrast hit (`.ev-zero`).

## Owner actions (one line each)
- H39: label the first global gold round (`py -3.14 -m streamlit run scripts/review_gold_labels_app.py -- --global`).
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- H42: triage 43 PubMed misses (`py -3.14 -m streamlit run scripts/review_pubmed_misses_app.py`).
- H40: taxonomy decisions D1-D10 in `docs/TAXONOMY_PROPOSAL.md`. H2: 277 low-confidence work-relevance decisions.
- H54: say "deploy the Worker" for global co-author invitations. H53: BFFP permission details (one message).
- Accept or change WORKS-GRAPH-SELECT in `.agent/QUESTIONS.md` (works graph shows the 15,000 most cited).
