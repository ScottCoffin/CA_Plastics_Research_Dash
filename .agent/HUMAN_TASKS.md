# Human tasks (owner to-do list)

Persistent list of things only the owner (Scott) can do. The lead agent keeps it
current: it adds a task when work becomes owner-gated, and moves a task to "Done"
when the owner finishes it. Each task says where, what to do, and how to tell the
agent it is finished.

Owner rule (2026-11-11): any human review with more than 10 cases gets a Streamlit
review app (one case per screen, one-click decisions saved at once), not a
spreadsheet to edit by hand. Small reviews (10 or fewer) may stay as a file edit.

All commands run from the repository folder in Git Bash:
`cd ~/R_new/CA_Plastics_Research_Dash`

Last updated: 2026-11-12.

---

## Do now

### H1. Renew the CORE API key (due 2026-11-12, repeats daily)
1. Sign in at https://core.ac.uk/services/api and copy the new API key.
2. Open `.env` in the repository folder in a text editor.
3. Find the existing line that holds the CORE key. Replace only the value after `=`
   with the new key. Do not add quotes or spaces, and do not rename the variable.
4. Save the file. Never commit `.env`; it is gitignored.
- **Done when:** the file is saved. Tell the agent "CORE key renewed".

### H2. Review the 277 low-confidence work-relevance decisions
1. Run `py -3.14 -m streamlit run scripts/review_work_relevance_app.py`.
   A browser tab opens. If it does not, go to http://localhost:8501.
2. In the left sidebar, type your initials in **Your initials (required)**.
3. In **Show**, choose **Low confidence pending**.
4. For each work, read the title and abstract. Highlighted words are the search
   terms that admitted the work; open **Highlight legend** for the colour key.
   Then click one of:
   - **Plastic-related ✓**: plastic is a central subject of the work.
   - **Not plastic-related ✗**: plastic is not central (for example "plasticity",
     plastic surgery, or a passing mention).
   - **Unsure (skip)**: leave it for later.
   With **Advance after deciding** ticked, the next work appears automatically.
5. Stop at any time. Every click is saved to `curation/work_relevance.csv` at once.
   The sidebar shows how many are still pending.
- **Done when:** the sidebar shows 0 low-confidence pending. Tell the agent
  "work relevance review done".
- The queue now includes 93 works added on 2026-11-12 (from experts' ORCID records
  and eScholarship), mixed into the same view. One of them, W4394182873, has the title
  "Delete" in OpenAlex; judge it from its abstract.
- Optional: the default **Smart queue (active learning)** view asks about the works
  the model is least sure of. Use it after H2 to label faster.

### H6. Cut a new archived release when you want a citable snapshot (AT-10, optional)
1. On GitHub: repository > **Releases** > **Draft a new release**.
2. Tag: `v` plus today's date, for example `v2026.11.12`. Title: the same.
   Click **Publish release**.
3. Wait about 5 minutes. Zenodo archives the release automatically. Open
   https://zenodo.org/ > your uploads and copy the new version DOI.
4. Tell the agent "release vYYYY.MM.DD, DOI 10.5281/zenodo.NNNNNNN". The agent
   updates `config/release.yml` and the About page.

### H6b. Report the wrong PNAS abstracts to OpenAlex (optional, 5 minutes)
The Atlas already hides these abstracts; this fixes them for everyone.
1. Go to https://openalex.org, click **Help** (or the feedback / "report an issue" link)
   and open a new support request.
2. Paste this text and submit:
   > Wrong abstract on 10 PNAS works: W2127391942, W2013886709, W2150748212,
   > W1975799990, W1971788246, W3108707921, W3108784206, W3124276284, W4200564390,
   > W4389073027 all carry the same abstract ("Micro-nano plastics originating from the
   > prevalent usage of plastics have raised increasingly alarming concerns worldwide...").
   > It is two teaser snippets about nanoplastics joined by "...", apparently scraped
   > from related-article text on the PNAS landing pages. None of these papers is about
   > plastics; please remove the abstract_inverted_index for them.
- **Done when:** submitted. Tell the agent "OpenAlex report sent".

### H16. Compare the new Framework pages with the current site (AT-5, 15 minutes)
The site is being moved to Observable Framework one page at a time. After the next deploy the
new pages run at https://plastiverse.live/app/ next to the current site, which stays the
main site until you approve the switch.
1. Open https://plastiverse.live/app/ and click through Experts, Institutions, Monitoring,
   Funding and About. Each should show the same data and controls as the matching tab at
   https://plastiverse.live/ (the layout differs: a left sidebar instead of tabs).
2. Try a few things you use: an expert search, the "Find up-and-coming researchers" button,
   an expert's drawer, the institutions map and tiers, the monitoring map, the funding filters
   and CSV download.
3. Locally, without deploying: `cd framework && npm run build`, then
   `py -3.14 scripts/serve_framework_preview.py` and open
   http://127.0.0.1:8766/CA_Plastics_Research_Dash/app/ .
- **Done when:** you reply "Framework pages OK, switch" (the agent then makes the Framework
  app the main site and keeps the old pages as redirects), or list what differs.

### H15. Look at the new expert pages (after the next deploy)
Open https://plastiverse.live/#experts. The list is now sorted by plastics citations.
1. Click **Full profile** on a few experts you know. Check the primary affiliation, the
   citations-per-year chart (orange = plastics-related), the m-quotient, and that clicking a
   topic tag filters the publication list.
2. Click **Find up-and-coming researchers** (under Career stage). Check whether the names
   look right to you.
3. Answer RISING-METRIC in `.agent/QUESTIONS.md` ("keep default" or describe the change).
- **Done when:** you reply "expert pages OK" or list what to change.

### H9. Label the gold set (unblocks the whole S5 classifier chain)
The S5 classifiers (and Haiku) are tested against your gold labels. You only need the
**evaluation set: 150 works** (dev + test random sample; 13 already done). The 350 train
works are not needed (training labels come from the active-learning app) and the 80
leak-check works wait for S5.7.
1. Run `py -3.14 -m streamlit run scripts/review_gold_labels_app.py` (restart it if it is
   already open).
2. Keep **Show** on "Evaluation set: unlabelled".
   About 40 works show "You already judged this ... on <date>": your earlier audit call
   is pre-selected, so check it and click Save and next (for a "not relevant" one that is
   the only click).
3. For each work, read the highlighted title and abstract (authors, journal, year and a
   DOI link to the full paper sit under the title), then set:
   - **plastic_related** (true or false). If **false**, nothing else is needed: go to step 4.
   - If true: the **tier** (core, or chemicals-in-plastics); **ca_sampled** (yes,
     partial, no or unclear: did they sample in California?); **study_type**
     (definitions in `docs/LABELING_GUIDE_A2_ADDENDUM.md` §1.1; if none fits, pick
     "+ Create a new design label" and type one, and it is offered for later works);
     **domain tags** (any that apply);
   - optionally an evidence snippet copied from the text.
4. Click **Save and next**. If you can't decide, click **Needs adjudication**.
   Every click saves immediately.
- **Done when:** the sidebar shows "Evaluation set: labelled 150 of 150". Tell the agent
  "gold evaluation set done". The agent then runs the Claude second rater on 20%, the
  Haiku evaluation and the S5.1 test evaluation.

---

## Later (the agent will say when each is ready)

Each later review with more than 10 cases (H12 need cells) will
come with its own Streamlit app and run command here.

- **H8. Outreach emails (S9.6).** Now unblocked (H7 done, emails allowed in `data/private/`): approve the email template in
  `docs/OUTREACH.md`, then send the first batch from your own email account. The
  agent never sends email.
- **H10. Leak-test widening decision (S5.7).** Choose whether to widen the
  candidate pool after the agent writes the report.
- **H11. ToMEx DOI list (EM-15).** Run the R script the agent provides
  (`PSSDplusplus::tomex2`) and save its output where the script says.
- **H12. Evidence map reviews (EM-13, EM-14, EM-17, S3.7, S3.8).** Review need
  cells, methods text, policy mapping, the hero page, and Search Console set-up
  when each is built.

---

## Done
- **H13 MiniSearch / H14 Framework install** (2026-11-12): MiniSearch 7.2.0 vendored and wired;
  Observable Framework 1.13.4 installed in `framework/`.
- **H4 photos** (2026-11-11): 43 approved, 1 rejected; approved photos ship with the next export.
- **H5 questions** (2026-11-12): AT4-SEARCH MiniSearch (see H13), AT11-WINDOW cap at yesterday
  (applied), CA-CARRY-ORCID drop contradicted years (applied), EM5-FRAMEWORK Framework first
  (see H14), OUTREACH-EMAILS emails only in `data/private/` (S9.6 after H8); UNSURE-SEM unsure =
  not plastic-related (applied).
- **H7 profiles** (2026-11-12): reviewed; owner asked for full-page views, primary affiliation,
  citation histogram, sortable/filterable publications, plastics-citation default sort,
  up-and-coming finder and m-quotient (built 2026-11-12; check them in H15).
- **H3 / AT2-REVIEW** (2026-11-12): 46 new top-100 institutions typed in the review app.
  Applied as owner overrides; new types `JPA` (in use), `utility` and
  `intergovernmental-organization` added to the pipeline.
- 2026-11-12: HIST-EMAILS answered (keep history). CORE key: owner renews 2026-11-13 when reissued.
- 2026-11-11: ESCH-CA answered (use eScholarship UC evidence).
- 2026-11-11: PLASTISPHERE-SCOPE answered (soil-community effects and biodegradation-only
  works are not Plastisphere).
- Earlier owner actions are in `.agent/archive/HANDOFF_history.md`.
