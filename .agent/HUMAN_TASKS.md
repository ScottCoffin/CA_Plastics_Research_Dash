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

Last updated: 2026-11-14.

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

### H20b. Bing Webmaster Tools and Rich Results check (optional, S3.8, 10 minutes)
Google Search Console is done (H20). Two optional extras:
1. Bing: go to https://www.bing.com/webmasters and sign in. Choose **Import from
   Google Search Console**, or add `plastiverse.live` by hand and verify it with the
   same Cloudflare DNS TXT method you used for Google.
2. Under **Sitemaps**, submit `https://plastiverse.live/sitemap.xml`.
3. Rich Results: open https://search.google.com/test/rich-results, enter
   `https://plastiverse.live/experts/A5000014168/`, and check that **Person** is
   detected with no errors.
4. In Google Search Console > Sitemaps, check that `sitemap.xml` reads **Success** (it lists the
   new root pages since the switch; resubmit it if it still shows the old `/app/` pages).
- **Done when:** Bing lists the sitemap and the Rich Results test shows no errors. Tell the
  agent "H20b done", or say which part you skipped.

### H21. Review the collaboration network (S9.4, 10 minutes, after the next deploy)
Open https://plastiverse.live/network. It is now fully interactive: scroll to zoom, drag the
background to pan, drag a dot to move it, type a name in **Find an expert**, click a dot for its
panel, and try **Colour by** and **Re-run layout**. Check three slices: (a) no filters, (b) one
topic (e.g. Occurrence & monitoring), (c) years 2020-2026 with "Now in California only".
Do the clusters and links match the collaborations you know?
- **Done when:** you reply "network OK" or list what looks wrong.

### H22. Screen-reader check (UX-19 follow-up, optional, 20 minutes)
The agent's accessibility pass (`docs/UX_19_ACCESSIBILITY_PASS.md`) covers what tools can check.
A person still needs to listen to the site once.
1. On Windows, press Ctrl+Win+Enter to start Narrator (or use NVDA if installed).
2. Open https://plastiverse.live/experts. Press Tab through the filters and change one; Narrator
   should read each filter's name and then the new result count.
3. Open https://plastiverse.live/evidence, tick one heatmap cell, and check it reads the cell
   (topic, setting, count) and the "Table limited to ..." message.
4. Press Ctrl+Win+Enter again to stop Narrator.
- **Done when:** you reply "screen reader OK" or list what it read wrongly.

### H23. Look at the new institution pages and expert badges (S9.3, 15 minutes, after the next deploy)
1. Open https://plastiverse.live/institutions and click two institution names you know. Check
   the summary numbers, the lead authors, and that clicking a topic narrows the publication list.
2. Open the full profiles of ten experts (S9.3 acceptance), including some with funding, e.g.
   https://plastiverse.live/expert.html#author=A5027952240 . Check the "Active funding" and
   "Data steward" badges, the Funding, Datasets and Co-author institutions sections, and the
   one-sentence topic summary under the name.
3. Answer S9.3-NAMES in `.agent/QUESTIONS.md` (keep matching grants by PI name: yes/no).
- **Done when:** you reply "profiles OK" or list what to change.

### H17. Answer the UX decisions UXD-1..UXD-9 (10 minutes)
Your UX spec (`docs/EM_spec.md`) is now TODO section "UX". Its decisions are rows UXD-1..UXD-9
at the bottom of `.agent/QUESTIONS.md`, each with the default the agent is using.
1. Open `.agent/QUESTIONS.md` and scroll to the UXD rows.
2. For each row, write your answer in the "Owner answer" column, or leave it blank to keep the default.
   Most important: UXD-3 (what counts as "California-connected"), UXD-4 (Experts vs Authors),
   UXD-8 (licence wording; ADR-002 already chose MIT code + CC BY data), UXD-9 (add axe/Lighthouse to CI).
   Also rows UX-LICENCE and UX-GLOSS (agent-drafted page wording to confirm). UXD-1, UXD-2
   and UX-13-H16 are closed by your H16 switch. New: H16-STUBS (old addresses that now
   redirect) and REL-TITLE (title-only relevance patterns; explained in the session report).
3. Optional, same sitting: give a non-GitHub contact address for the About page, and say whether
   the Monitoring "Licences, citations and caveats" box should start open.
4. Save the file.
- **Done when:** saved. Tell the agent "UXD answered".

### H18. Run the moderated usability sessions (UX-20, optional, about 5 x 45 minutes)
Materials are ready in `docs/UX_20_SESSION_PLAN.md`: who to recruit, the facilitator script with the
six tasks, and a note-taking sheet. No recording and no personal data, so no consent form is needed.
1. Recruit five people from the audiences in the plan's table.
2. Run each session from the script and fill one note sheet per person.
3. Save the notes in `scratch/` or send them to the agent.
- **Done when:** five note sheets exist. Tell the agent "UX sessions done".

### H15. Look at the new expert pages (after the next deploy)
Open https://plastiverse.live/experts. The list is now sorted by plastics citations.
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
  cells, methods text, policy mapping and the hero page when each is built.

---

## Done
- **H16 Framework switch** (2026-11-13): owner said "switch"; the Framework app is the site root
  from the 2026-11-14 deploy, and old addresses redirect.
- **H20 Google Search Console and sitemap** (2026-11-13): owner set up the property and submitted
  `https://plastiverse.live/sitemap.xml`; the index and its three child sitemaps return 200.
  Bing and the Rich Results test are H20b.
- **Questions REL-TIER2, S3.8-AI, S3.8-RENDER, S9.4-DEP** (2026-11-13): answered; applied 2026-11-14.
- **H19 Spring photo credit** (2026-11-13): "Monterey Bay Aquarium", used with permission.
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
