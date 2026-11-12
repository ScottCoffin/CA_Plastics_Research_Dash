# eScholarship recall audit (S2.5, eScholarship part)

Status (2026-11-11): the HTML search and OAI routes are blocked by a BotStopper bot screen
(HTTP 403). The GraphQL read API works. It has **no keyword search**, so the audit now runs on
a list of known item ids. The owner found 349 "microplastics" hits on the eScholarship portal,
which is a useful yardstick for the expected size of the gap. Nothing was added to the corpus.

## Goal

Measure how many plastics-related University of California deposits on eScholarship
(escholarship.org) are missing from the corpus. Method (`scripts/audit_escholarship.py`,
`src/atlas/ingest/escholarship.py`): fetch each candidate id with `item(id:)`, apply the local
rule (`classify_plastic_text` or `always_relevant`), then match the corpus by normalized DOI,
then by casefolded, punctuation-stripped title.

## Routes tried

| Route | Result |
|---|---|
| `GET https://escholarship.org/search?q=...` (HTML/JSON search) | HTTP 403, BotStopper "Request blocked" page. Not used. |
| `GET https://escholarship.org/oai?verb=Identify` (OAI-PMH) | HTTP 403, same page. Not used. |
| `GET https://escholarship.org/` (site root) | HTTP 403, same page. |
| `POST https://escholarship.org/graphql` (public read API) | HTTP 200. Used. |

The 403 pages are the BotStopper screen. The session did not change the User-Agent or try any
other way around it, and it did not touch those routes again after the owner's instruction.
One connectivity check to a non-authorized host (`example.com`) was made early on and is
disclosed here.

## GraphQL endpoint (verified)

- URL: `POST https://escholarship.org/graphql`, `Content-Type: application/json`, body
  `{"query": "...", "variables": {...}}`. No key is needed.
- Root type is `AccessQuery`. Root fields: `author`, `item`, `items`, `rootUnit`, `unit`,
  `unitsUCPMSList`.
- `item(id: ID!, scheme: ItemIDScheme)` returns one `Item`. The id is the ark, for example
  `ark:/13030/qt2ds3m2mm`.
- `Item` fields used: `id`, `title`, `abstract`, `published` (a string such as `2021-05-01`
  or a bare year), `type` (enum `ARTICLE`, `CHAPTER`, `ETD`, `MONOGRAPH`, `MULTIMEDIA`,
  `NON_TEXTUAL`; there is no "report" value), `permalink`, `disciplines`, `localIDs { id }`
  (the DOI appears here as a bare `10.x/...` or a `https://doi.org/` prefixed value), and
  `units { name }`.
- `items(first, more, order, tags, include)` pages the repository. `tags` filters on strings
  such as `discipline:Life Sciences`, `keyword:...`, `type:...`, `source:...`. The `disciplines`
  field holds only top-level names, and there is no subdiscipline tag.
- Per-discipline totals at the time of probing: Life Sciences 10,307; Physical Sciences and
  Mathematics 12,924; Engineering 10,437; Medicine and Health Sciences 8,183; Social and
  Behavioral Sciences 32,127. Total repository 563,891.
- Paging facts from the probes: `first: 500` works. The `more` cursor encodes `first`,
  `order` and the last id, but not the tag filter, so a tag-filtered scan must send `tags`
  together with `more`. Bulk paging was stopped on the lead's instruction and is not needed for
  the current scope.

## Request log

About 50 requests to escholarship.org on 2026-11-12, including about 32 discipline pages from a
worker paging run that the lead stopped (44 cached responses). No further eScholarship
requests are planned: the GraphQL client was removed in favour of the OpenAlex route below.

## Result via OpenAlex (2026-11-12; `scripts/audit_escholarship_openalex.py`)

OpenAlex indexes eScholarship as source S4306400115. One query (eScholarship location AND the
active `plastic-v3.1` query AND the type exclusions) took 2 requests and 20 credits:

| Measure | Works |
|---|---:|
| eScholarship-hosted works matching the query | 214 |
| already in the raw corpus | 164 (77%) |
| missing | 50 |
| missing, passing the California gate | 0 |
| missing, no affiliation of any kind | 32 |

Missing by type: article 31, dissertation 14, report 2, book 1, review 1, preprint 1. Relevance
is mixed. Clearly relevant examples are a 2026 dissertation on "living" vs conventional plastic
in aquatic ecosystems and a 2024 report on the climate impact of primary plastic production.
Off-topic examples are an oral history and a social-science dissertation, which probably
match on stemmed terms in their abstracts.

The portal's 349 'microplastics' hits likely include full-text matches. Our query is
title/abstract only, so the portal count overstates the gap.

## Decision needed (QUESTIONS ESCH-CA)

These 50 works are missing only because they carry no California affiliation. Being deposited
in UC's repository is strong evidence of a UC author. If the owner accepts "hosted on
eScholarship" as a California basis, ingest them through the normal relevance rules, and give
the owner a review app for the 50 (owner rule: more than 10 cases means a Streamlit app).
