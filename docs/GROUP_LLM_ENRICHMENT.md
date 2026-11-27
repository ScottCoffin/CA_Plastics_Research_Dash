# Could an LLM with web search fill in the community-group tags? Cost and pilot plan

Prepared 2026-11-26 for the Plastiverse Live owner. Prices were read from the
official pages on that date unless marked **unverified**.

## Bottom line

- **Full roster (2,673 groups), one search-and-extract pass per group:** about
  **$60 to $130** with Gemini 3.1 Flash-Lite and Google Search grounding, or
  about **$85** with Claude Haiku 5.5 and its web search tool. The range
  across assumptions is roughly **$55 to $180**. The Google search allowance
  (5,000 free queries a month, see below) can bring the Google figure down
  to about $60 net.
- **Pilot (100 groups gold-checked, then 4 prompt rounds on 50 training
  groups, then a 50-group held-out test; about 350 group runs):** about
  **$10 to $25** on any of the options above. Budget **$50** to cover retries.
- **Recommendation:** run a pilot. Use an LLM only to draft suggestions that an
  ambassador confirms. That fits the current rule (A4-D11 and ADR-GRP-ENRICH-2026-11-26).
  Publishing machine tags needs a rule change first (options below).
- **Caveat:** the money is small. The real cost is ambassador review time, and
  the LLM only saves time if confirming a draft is much faster than tagging from
  scratch. The pilot should measure that.

## Verified prices (as of 2026-11-26)

| Item | Price | Source |
|---|---|---|
| Gemini 3.1 Flash-Lite, paid | $0.25 in / $1.50 out per 1M tokens (text) | [Google AI Studio pricing](https://aistudio.google.com/docs/pricing) |
| Gemini 3.5 Flash-Lite, paid | $0.30 in / $2.50 out per 1M tokens | same |
| Gemini 2.5 Flash-Lite, paid | $0.10 in / $0.40 out per 1M tokens | same |
| Batch / Flex | 50% of standard token prices | same |
| Grounding with Google Search, Gemini 3+ | 5,000 free queries/month (shared), then $14 per 1,000 queries; daily cap 1,500 | [Grounding docs](https://aistudio.google.com/docs/google-search) |
| Grounding, Gemini 2.5 | billed per prompt: $35 per 1,000 grounded prompts, after daily free allowances | [Pricing](https://aistudio.google.com/docs/pricing) |
| Gemini billing rule (3+) | "billed for each search query the model decides to execute", including uncited queries | [Grounding docs](https://aistudio.google.com/docs/google-search) |
| Gemini free-tier data use | Free card: "Content used to improve our products" | [Pricing](https://aistudio.google.com/docs/pricing) |
| Claude Haiku 5.5 (prompts up to 100k) | $0.10 in / $0.50 out per 1M; batch halves it | [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude web search tool | $10 per 1,000 searches, plus search results as input tokens; failed searches not billed | same |
| Claude web fetch tool | no fee beyond tokens | same |
| OpenAI gpt-5-nano | $0.05 in / $0.40 out per 1M | [OpenAI pricing](https://developers.openai.com/api/docs/pricing) |
| OpenAI web search, reasoning models | $10 per 1,000 calls, plus search content tokens at model rates | same |
| OpenAI web search, other models (e.g. gpt-4.1-mini, $0.40 / $1.60 per 1M) | $25 per 1,000 calls; content tokens free | same |
| Perplexity Sonar | **unverified**: third-party sites give $1 in / $1 out per 1M plus $5 to $12 per 1,000 requests. The official page I could reach no longer lists Sonar (it lists a $5 per 1,000 Search API). | [Third-party summary](https://pricepertoken.com/pricing-page/model/perplexity-sonar); [Perplexity pricing](https://docs.perplexity.ai/docs/getting-started/pricing) |

Two items are **unverified**: the OpenAI forum report that gpt-4.1-mini
searches billed at $15 per 1,000 instead of the listed rate, and a
third-party claim that OpenAI bills an 8,000-token block per search for
gpt-4o-mini and gpt-4.1-mini. Check your own billing before relying on either.

## Cost model

Per group, one agentic attempt:

- **Searches:** low 2, central 3, high 4 (Google bills each query the model runs).
- **Input tokens:** 3k prompt and schema, plus about 3k to 8k of retrieved text per search. Totals: 9k low, 18k central, 35k high.
- **Output tokens:** 600 low, 1,000 central, 2,000 high, including any thinking tokens and the JSON with quotes and URLs.

| Option | Per group (low / central / high) | Total 2,673 groups (low / central / high) | Pilot, about 350 runs (central) |
|---|---|---|---|
| A. Gemini 3.1 Flash-Lite + grounding | $0.031 / $0.048 / $0.068 | $83 / $128 / $182 gross; about $14 / $58 / $111 after the 5,000 free queries | $17 |
| A2. Gemini 3.5 Flash-Lite + grounding | about $0.033 / $0.050 / $0.072 | about $88 / $133 / $190 gross | $17 |
| A3. Gemini 2.5 Flash-Lite + grounding (per-prompt billing) | about $0.02 / $0.037 / $0.05 | about $55 / $99 / $135 gross; daily free allowances may cover much of it | $13 |
| B. Claude Haiku 5.5 + web search | $0.021 / $0.032 / $0.045 | $57 / $86 / $119 | $11 |
| C. gpt-5-nano + web search (reasoning, $10/1k) | $0.021 / $0.031 / $0.043 | $55 / $84 / $114 | $11 |
| C2. gpt-4.1-mini + web search ($25/1k; **unverified** token block) | about $0.06 / $0.084 / $0.11 | about $160 / $224 / $300 | $29 |
| D. Perplexity Sonar (**unverified prices**) | $0.015 / $0.027 / $0.049 | $39 / $72 / $131 | $9 |
| E. Fetch each group's own homepage and About page, then a cheap model (no search) | about $0.003 per group, for the 2,250 groups with a website | about $7 | not needed |

Arithmetic example (option A, central): 3 queries at $14 per 1,000 = $0.042;
18k input tokens at $0.25 per 1M = $0.0045; 1k output tokens at $1.50 per 1M =
$0.0015. Total $0.048 per group. For all groups: 2,673 × $0.048 = $128.

Option E is cheap, but it is a crawl of group websites. It is **not allowed**
under A4-D11 as written. Option E is listed only for completeness.

Claude's web fetch tool costs only tokens. Using it to read the group's own
pages would also be a crawl-style lookup, so it falls under the same governance
question as option E.

### Pilot budget

- **Gold set:** ambassadors tag 100 groups first (human time, not API cost).
- **Tuning:** the LLM runs on a 50-group training split for 4 prompt rounds: 200 runs.
- **Test:** one run on a 50-group held-out split: 50 runs.
- **Total:** about 350 runs at $0.03 to $0.07 each, so **$11 to $24**. Budget **$50**
  for retries and cache misses.
- **Full run after the pilot:** budget **$150 to $200**, covering a re-run on the
  whole roster for prompt changes.

## Pilot and "self-evolution" design

1. **Gold.** Ambassadors tag 100 groups with the normal form. Have 30 of them
   double-coded by a second ambassador so there is a human-human agreement
   baseline.
2. **Run.** The LLM runs the same 100 groups. It returns, for each facet, a value
   plus the URL, access date and quote. Keep the raw output in `scratch/` (never in `data/`).
3. **Score.** Use `atlas.agreement`: weighted kappa for ordinal
   `plastics_centrality`, unweighted kappa for nominal facets, and PABAK and Gwet's AC1
   alongside them. Those two correct for the skew you get when most groups share one value,
   which kappa alone handles poorly. Report bootstrap intervals and the precision card.
   Quote validity, meaning the quote appears on the cited page, is measured separately (see
   risks).
4. **Iterate.** Each round, the lead changes the prompt, examples or tool use
   using only the training split. Ambassador corrections go into the few-shot
   examples. The held-out split is scored once, at the end.
5. **Stop rules (proposed).** Stop after 4 rounds, or when two rounds in a row
   improve the training kappa by less than 0.02. Also stop if quote validity
   stays below 90%, or if any facet's agreement is below the human-human baseline
   by more than 0.15.
6. **Sample size.** With 100 groups, the 95% interval on a raw 80% agreement is
   about ±8 points. Rare categories will have only a few cases each, so
   publication-grade claims need about 300 gold groups.

### Decision thresholds (proposed, for owner approval)

- **(a) Suggestions only (current rule).** Show the LLM values in the form,
  pre-filled, with the evidence attached. An ambassador must confirm each facet.
  Go ahead if held-out PABAK is at least 0.6 on the main facets and quote validity is at least 90%.
- **(b) Published machine tags (needs an A4-D11 amendment).** Publish only facets
  where the lower bound of the held-out agreement interval is at least the
  human-human baseline minus 0.05, and the lower bound of the kappa interval is at least 0.7.
  Label every machine tag as machine-generated. Never publish `plastics_centrality`
  automatically, because it is the most judgement-heavy facet.

## Governance options

- **(a) Suggestions confirmed by ambassadors.** Fits A4-D11 and ADR-GRP-ENRICH-2026-11-26
  as written. The LLM lookup is a search suggestion, the same status as the Wikidata
  and IRS hints. Nothing is tagged automatically.
- **(b) Machine tags published with a label.** Needs a new owner decision that
  amends A4-D11 to allow LLM-generated tags, with the thresholds above. It also needs
  a decision on whether machine-tagged groups show on the map.

## Risks and failure modes

- **Hallucinated quotes and URLs.** The model may invent a quote or cite a page
  that does not contain it. Verify each quote by checking the cited page. That
  is a fetch by the project, so it falls under the same crawl question as option E.
  The alternative is for the ambassador to check the quote at confirmation time.
- **Name collisions.** Generic names such as "Plastic Free Community" match
  unrelated organisations. Match on the roster's website domain and IRS or
  Wikidata identifiers wherever they exist.
- **Non-English sites.** Gemini handles many languages, but quotes must be in the
  page's own language, and ambassadors need to read them. Check quality by language
  group, since the roster is 652 US groups and many non-English sites.
- **Stale sites.** Store the access date. Flag sites whose content looks old.
- **Individuals versus organisations.** Personal blogs and creators should not be
  tagged as organisations. Add an explicit `entity_type` check.
- **Thin websites.** The roster has 423 groups with no website, and many more
  with little text. Expect the model to be weak there. Say so in the output
  instead of guessing.
- **Provider terms.** On the free tier, Google's page says content is "used to
  improve our products". Do not send any roster or ambassador data through the free
  tier. Use paid-tier terms, and confirm them before sending data. Google's
  grounding page refers to its Terms of Service for display rules, and I did not
  read those terms, so **display and storage rules for grounded results are unverified**.
- **Licensing.** The dataset is CC BY-NC. Check that model output stored in the
  dataset is compatible with the provider's output terms, and keep attribution
  to the source URLs.
- **Privacy.** Do not put personal data in prompts. Roster entries are organisations,
  but ambassador contact details must never go to a model.
- **Budget.** The project defaults to $0. Any paid API use needs owner approval.
  The OpenAI and Anthropic budget rules are not in force here.

## Owner decisions needed

1. Approve a pilot with a **$50 cap** on API spend, and choose the provider to test first (Gemini 3.1 Flash-Lite is the suggested default).
2. Confirm the **governance route**: suggestions only (a), or a proposed amendment to A4-D11 for published machine tags (b).
3. Decide who checks quotes: ambassadors at confirmation (no new fetching), or a project quote check that fetches cited pages, which needs a separate governance decision.
4. Confirm the **paid-tier** requirement for any Google use, so that no data goes through the free tier.
5. Approve the gold size (100 for the pilot, about 300 before any publication).

## Sources

- Google AI Studio pricing, read 2026-11-26: https://aistudio.google.com/docs/pricing (redirected from https://ai.google.dev/gemini-api/docs/pricing)
- Google grounding billing rules, read 2026-11-26: https://aistudio.google.com/docs/google-search
- Anthropic pricing, read 2026-11-26: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI API pricing, read 2026-11-26: https://developers.openai.com/api/docs/pricing
- Perplexity pricing, read 2026-11-26 (no Sonar prices on the page): https://docs.perplexity.ai/docs/getting-started/pricing
- Sonar third-party summary (unverified): https://pricepertoken.com/pricing-page/model/perplexity-sonar
- Repo: `docs/BFFP.md`, A4-D11 in `.agent/DECISIONS.md`, ADR-GRP-ENRICH-2026-11-26, `src/atlas/agreement.py`
