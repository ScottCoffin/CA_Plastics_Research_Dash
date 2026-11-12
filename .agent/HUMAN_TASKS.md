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

Last updated: 2026-11-11.

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

### H3. Set institution types for the new top-100 institutions (AT2-REVIEW)
1. Run `py -3.14 -m streamlit run scripts/review_institution_types_app.py`
   (47 institutions today; QUESTIONS.md says 52).
2. For each institution, read the name and the proposed type. Use **Open in
   OpenAlex** or **Search the web** if you are not sure what it is.
3. Click **✓ Accept proposed** if it is right. Otherwise click the correct type
   (hover a button for its definition; **Type definitions** in the sidebar lists
   them all). If none fits (for example a community college), pick the closest and
   type a note first; the agent will add a type if needed.
4. Each click saves the type, today's date and your note to
   `data/processed/institution_review_needs_v31.csv`, and the next institution appears.
- **Done when:** the sidebar shows "Reviewed 47 of 47". Tell the agent
  "AT2-REVIEW done".

### H4. Approve or reject 44 expert photos from Wikidata (S9.5)
1. Run `py -3.14 -m streamlit run scripts/review_expert_photos_app.py`.
2. For each photo, compare it with the expert. Use **Atlas profile**, **Wikidata**
   and **Commons page** if you need to check the person or the licence.
3. Click **✓ Approve** (same person, fine to show with the licence and credit) or
   **✗ Reject** (wrong person, or you do not want it shown). Type a note first if useful.
4. Each click saves to `curation/expert_photo_review.csv`, and the next photo appears.
   (If the sheet is regenerated with `py -3.14 scripts/build_photo_review.py`,
   your decisions are kept.)
- **Done when:** all 44 rows have `approve` or `reject`. Tell the agent
  "photos reviewed". No photo is shown on the site before this.

### H5. Answer three open questions (defaults are in use until you answer)
Open `.agent/QUESTIONS.md`, find each ID, and reply to the agent in one line
("keep default" or "change").
- **AT4-SEARCH:** title search is the home-made token search. Default: keep it.
  Change = add the MiniSearch library (better search, one new dependency).
- **AT11-WINDOW:** the daily ingest has no "only up to yesterday" cap. Default: no
  cap. Change = cap at yesterday (future-dated works arrive a day later).
- **CA-CARRY-ORCID:** some authors are counted as California-based in years when
  their ORCID shows a job elsewhere (19 of 109 checkable cases; list in
  `docs/api_notes/orcid_enrichment.md`). Default: keep counting them and list the
  cases. Change = drop those years.

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

### H9. Label the gold set (unblocks the whole S5 classifier chain)
The S5 classifiers can only be tested against your gold labels. There are 580 works:
start with dev and test (230), then train.
1. Run `py -3.14 -m streamlit run scripts/review_gold_labels_app.py`. The first launch
   creates `curation/annotations/annotations_SC.csv`.
2. Keep **Show** on "Unlabelled (dev+test first)".
3. For each work, read the highlighted title and abstract, then set:
   - **plastic_related** (true or false), and the **tier** if true (core, or
     chemicals-in-plastics);
   - **ca_sampled**: yes, partial, no or unclear. Did they sample in California?
   - **study_type** (definitions in `docs/LABELING_GUIDE_A2_ADDENDUM.md` §1.1);
   - **domain tags** (any that apply);
   - optionally an evidence snippet copied from the text.
4. Click **Save and next**. If you can't decide, click **Needs adjudication**.
   Every click saves immediately.
- **Done when:** dev and test show "labelled 230 of 230" in the sidebar (train can
  follow later). Tell the agent "gold dev+test done". The agent then runs the Claude
  second rater on 20% and the S5.1 test evaluation.

### H7. Review 10 expert profiles (S9.3/S9.5)
The drawer now shows ORCID bios, keywords and links (399 experts). Open
https://plastiverse.live/#experts, open 10 experts you know, and check name,
affiliation, bio and links. Reply "10 profiles OK" or list the problems.

---

## Later (the agent will say when each is ready)

Each later review with more than 10 cases (H12 need cells) will
come with its own Streamlit app and run command here.

- **H8. Outreach emails (S9.6).** After H7: approve the email template in
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
- 2026-11-12: HIST-EMAILS answered (keep history). CORE key: owner renews 2026-11-13 when reissued.
- 2026-11-11: ESCH-CA answered (use eScholarship UC evidence).
- 2026-11-11: PLASTISPHERE-SCOPE answered (soil-community effects and biodegradation-only
  works are not Plastisphere).
- Earlier owner actions are in `.agent/archive/HANDOFF_history.md`.
