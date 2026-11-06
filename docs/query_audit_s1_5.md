# S1.5 query audit

Audit run: **2026-11-06T06:44:00Z**. The OpenAlex response was authenticated
with the ignored local credential; no credential or work corpus is committed.

## Count and contract checks

| Item | Result |
|---|---:|
| Query version | `plastic-v2-candidate` |
| Field | `title_and_abstract.search` |
| Candidate count (with exclusions) | **98,118** |
| Positive control (without exclusions) | **100,335** |
| Exclusion control | **PASS**; 2,217 fewer works |
| Group-by response | **PASS**; `publication_year` response returned a non-empty group |
| URL encoding | **PASS**; the complete filter value was percent-encoded |
| Requests / credits / cost | **6 / 60 / USD 0.0060** |
| Versioned cache | **PASS**; query version and rendered query are stored |

The count is a timestamped design estimate, not dashboard data. OpenAlex is
continuously updated, so later runs may differ.

## Precision spot check

A deterministic `cited_by_count` sample was reviewed from the candidate query
at global scope and for the California institution records for UCSF and SLAC.
Labels use a conservative title/abstract criterion: the work is relevant when
the visible title or abstract clearly treats plastics, microplastics, plastic
waste, or an environmental/health consequence as a research subject. This is
not a gold-set label.

| Scope | Sampled | Relevant | Precision | Notes |
|---|---:|---:|---:|---|
| Global | 10 | 10 | 100% | Plastic production/fate, debris, litter, pollution, and microplastics reviews or studies |
| UCSF | 10 | 8 | 80% | Two conservative false positives: generic microfiber vascular grafts and a broad brain-capital paper |
| SLAC | 2 | 2 | 100% | Compostable/recyclable packaging and a micro/nanoplastics ecosystem chapter |
| **Total** | **22** | **20** | **90.9%** | **PASS** for this bounded screening check |

The UCSF false positives are useful failure examples rather than reasons to
silently change the owner query: a generic `microfiber` can still be paired
with a biomedical `synthetic` context, and a broad work can mention plastics
without making them its main subject. Later relevance classification and owner
promotion review must handle those cases.

## Recall spot check

The four anchors were selected from the literature-informed environment,
food/analytical, soil/ecotoxicology, and human-exposure concepts recorded in
`docs/query_design_v2.md`. The candidate query matched all four by OpenAlex ID.

| OpenAlex work | Anchor basis | Result |
|---|---|---|
| `W3104558585` — *Microplastics in glaciers of the Tibetan Plateau* | environment / transport | PASS |
| `W3084664411` — *Microplastics in Food* | food / analytical methods | PASS |
| `W4322619704` — *Interactions of Microplastics with Pesticides in Soils* | soil / ecotoxicology | PASS |
| `W3196209576` — *A Review of Human Exposure to Microplastics* | human exposure | PASS |
| **Total** | **4 known relevant anchors** | **4/4; PASS** |

## Promotion status

`config/queries.yml` remains `status: owner_supplied_candidate`. S1.5 has
completed its machine and bounded screening checks, but the candidate is not
silently promoted to active. The owner must review the precision examples and
approve promotion before downstream ingestion uses this query as the
production candidate pool.
