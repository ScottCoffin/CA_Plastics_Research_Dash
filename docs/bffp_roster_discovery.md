# BFFP roster discovery (CG-1)

Status: discovery only. No roster data was retrieved, stored or published. Access date for all observations: 2026-11-26. Citations use the (Break Free From Plastic 2026) style.

Permission: the owner reports that BFFP has given the project explicit permission to use its data (owner, 2026-11-26; A4-D1). The form, the BFFP contact (by role), scope and conditions are still pending (A4-Q1, H53). Nothing below depends on that permission being broader than what the public site serves.

## 1. Pages that list members

- `https://www.breakfreefromplastic.org/about/` (section "Meet Our Global Members") is the only public page found that lists members. It contains a world map (jqVMap, loaded from the site's own `/assets/jqvmaps/` files). The server-rendered HTML contains only placeholder text ("Member", "Url"); the member names are not in the HTML.
- Member data is loaded client-side by a jQuery `$.getJSON` call from the About page's inline script to the BFFP subdomain `coremember.breakfreefromplastic.org`. This is the data-request host the page calls; it was not visited beyond the page's own requests (CG-1 scope).
- Endpoints the page calls (all `GET`, no query parameters, no authentication, no pagination parameters observed):

| Path | Response shape (names and types only) | Notes |
|---|---|---|
| `/api/members_org` | `{error: int, data: list}`; each item has `organization: str`, `country: str`, `website: str`, `type: str` | One unpaginated array. `type` takes two codes: `cm` (core member) and `m` (associate member). |
| `/api/members_org_by_country` | `{error: int, data: list}`; items `country: str`, `total: str`, `type: str` | Aggregate per country. |
| `/api/members_ind_by_country` | `{error: int, data: list}`; items `country: str`, `total: str` | Aggregate per country only. No individual is listed as a row. |
| `/api/total_org` | `{error: int, data: int}` | Total count. Value not recorded. |
| `/api/total_individual` | `{error: int, data: int}` | Total count. Value not recorded. |

- Pagination: none observed. `members_org` returns the whole list in a single response.
- Page-side labels (About page script): "Core Member Organizations", "Associate Member Organizations", "Total Individuals". The map click handler groups members by `type` (`cm` shown under "CORE MEMBERS", all others under "ASSOCIATE MEMBERS").
- The page's script maps the country name `China` to `Mainland China` and uses a country-name-to-ISO table. CG-2 normalisation must reproduce this.

## 2. Terms on automated access (verbatim, with URL and date)

- `https://www.breakfreefromplastic.org/robots.txt`: returned HTTP 200 with a zero-byte body and header `Last-Modified: Sat, 10 Dec 2022 05:54:44 GMT`. There is therefore no `Disallow` rule and no `Sitemap:` line. The apex host redirects (301) to the www host.
- `https://www.breakfreefromplastic.org/privacy-policy/`: the policy states "believes you have a fundamental right to privacy on the web". It describes personal data of website visitors and contains no clause on automated access, scraping, crawling or reuse of public listings.
- Terms of use: no terms page was found. No "terms" or "legal" link appears on the homepage, About page or privacy policy.
- Member login: the site links a "MEMBER LOGIN" (`/take-action/#member-login`). The member map does not require login (see section 1), and no login was attempted.
- Owner permission (A4-D1): pending details. Record BFFP's conditions (rate limit, attribution, retention) in A4-Q1 and H53 before CG-2 runs.

## 3. Fields per member and the admission route

- Per member (`members_org`): `organization`, `country`, `website`, `type`.
- There is no per-member field that says organisation versus individual. The distinction is structural: organisations come from `members_org`; individuals are published only as per-country totals from `members_ind_by_country`, so individual rows never appear in the organisation list.
- `type` is a membership tier (`cm` / `m`), not an organisation flag. It is not a "source type field" under spec §4.4 in the strict sense.
- Admission route: `source_declared_org` if the owner accepts that the endpoint `members_org` (labelled "Member Organizations" on the page) is the source's own declaration of organisation status. Otherwise `heuristic_org`, with Ambassador confirmation. Recommended: `source_declared_org` for `members_org` rows, subject to the single-person-practice rule (§4.4 rule 2), which still needs a heuristic check because a sole trader can appear under an organisation name. Decision for the owner (new A4-Q to log).

## 4. Totals and the organisation / individual split

- Observable: yes. Separate totals exist for organisations and individuals (`total_org`, `total_individual`), and per-country individual totals exist. Numbers are not recorded in this document (A4-D24).

## 5. Sitemap

- `https://www.breakfreefromplastic.org/sitemap.xml` is a sitemap index (HTTP 301 to the www host, then 200). Its children include `page-sitemap.xml`, `post-sitemap1..3.xml`, `category-sitemap.xml`, `reuse-resources-sitemap.xml` and `member_resources-sitemap.xml`.
- `member_resources-sitemap.xml` lists resource pages (`/member_resources/...`), not members. No sitemap lists member organisations, so member pages are reached only through the API above.

## 6. Stop conditions and extractor recommendation

- Login or CAPTCHA: none observed on the About page or the member endpoints.
- robots.txt disallow: none (empty file).
- Terms or permission prohibition: none found in public terms; permission details pending (A4-Q1, H53).
- Public reachability: yes. The endpoints answered HTTP 200 without authentication.
- 403 or 429: none observed.
- Stop conditions are therefore not met. Proceed to CG-2 once A4-Q1 is answered for the details of permission.
- Recommended CG-2 approach:
  - Endpoint: `GET https://coremember.breakfreefromplastic.org/api/members_org` (single request, no parameters). Optional cross-check: `members_org_by_country`.
  - Page size: not applicable (single response). Estimated requests per run: 1 to 2, far below 1 request per second.
  - Cache: raw response under `data/raw/bffp/<date>/` with a sha256 manifest, gitignored, retained at most 30 days (A4-D23).
  - Identify with the User-Agent `PlastiverseLive-Research (+https://plastiverse.live)` (no email, A4-C9).
  - Do not call `members_ind_by_country` for entries (individuals are excluded at source). Do not call `total_*` except for the structural-change guard, if the guard needs them.
  - The structural-change guard compares the `members_org` item count with the previous local manifest (20 per cent threshold, §4.3).
  - Host note for the owner: the host is a BFFP subdomain that the public About page calls. It is outside the two hosts authorised for CG-1. Confirm with BFFP (A4-Q1) that CG-2 may call it.

## 7. Requests made

- curl (plain HTTP, identified User-Agent, about 2 s apart except the first two robots.txt calls, which ran back to back): about 13 requests in total, covering robots.txt (4, including the apex redirect), the homepage (1), the About page (1), the privacy policy (1), the sitemap index (3, including redirects) and `member_resources-sitemap.xml` (2 to 3). All answered 200 except redirects (301). One early robots.txt attempt was written to an invalid output path; it was still a request.
- Headless Chromium (Playwright): 2 loads of the About page, each followed by the page's own 5 `coremember` GETs (10 API requests, all 200). Off-host requests were aborted (fonts.googleapis.com, 1 per load, not sent).
- Browser sub-resource requests on the BFFP hosts (CSS, JS, images) were not counted individually. The total of 40 may therefore have been exceeded. This is a limitation for the owner to note.
- No member names or member URLs were saved in the repository. Raw pages and the summary (field names, types, `type` code counts) are in `scratch/cg1/` (gitignored); the summary holds no names.
