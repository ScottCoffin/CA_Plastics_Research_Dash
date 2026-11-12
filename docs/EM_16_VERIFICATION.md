# EM-16 verification: Related Resources (2026-11-12)

- Registry `config/linkouts.yml` (LO-1..LO-12, link-only) validates (`atlas.linkouts.validate_registry`); the weekly HTTP-status checker (`atlas.linkouts`, source-watch workflow) flags broken links (EAT-7, `tests/test_linkouts_em16.py`).
- Public export `site/data/linkouts.json` (`scripts/build_linkouts_json.py --check`): id, name, steward, description, relation, root_url, topics, default, description_source, update_model, terms_status, terms, url_status. No terms text beyond what the registry records; nothing from the resources is ingested (EAT-9); no Minderoo (EAT-8, `tests/test_linkouts_strip_em5.py`).
- Framework page `/app/resources`: one card per entry (name link, relation, steward, quoted description with its source link, update model, terms), a text filter, and the note that links are checked weekly. Headless Edge smoke: 12 of 12 cards. Tests: `tests/test_framework_resources.py`.
- The contextual strip on `/app/evidence` uses the same export (EM-5).
- Not verified: keyboard walk-through in a real browser.
