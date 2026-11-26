// Runtime checks for the ambassador workspace (AMB-1 slice 2b). The pure helpers live in
// framework/src/components/ambassador_workspace.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {
  activeRegions,
  regionMapHTML,
  regionPlace,
  admittingTerms,
  answerBody,
  caseChoices,
  caseProgress,
  choiceText,
  deepLinkFrom,
  knowledgeStatus,
  cleanText,
  estimateText,
  filterCases,
  firstUnanswered,
  highlightHtml,
  httpsAddress,
  itemsToConfirm,
  latestSubmissionByItem,
  mapFrame,
  progressSummary,
  progressText,
  timeLeftText,
  reviewText,
  submissionBody,
  workspaceErrorText,
} from "../framework/src/components/ambassador_workspace.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

const cases = [
  {case_id: "amb-000000000001", kind: "institution_in_region", options: ["agree", "disagree", "unsure"]},
  {case_id: "amb-000000000002", kind: "institution_type", options: ["education", "company", "unsure"]},
  {case_id: "amb-000000000003", kind: "local_terms", term: "plastique"},
  {case_id: "amb-000000000004", kind: "institution_in_region"},
];

check("email links: settings hash and the reminder's region and case", () => {
  assert.deepEqual(deepLinkFrom("", "#notifications"), {region: null, caseId: null, screen: "settings"});
  assert.deepEqual(deepLinkFrom("?region=norway&case=amb-0123456789ab", ""), {
    region: "norway",
    caseId: "amb-0123456789ab",
    screen: null,
  });
  assert.deepEqual(deepLinkFrom("?region=No%20Way&case=1", "#x"), {region: null, caseId: null, screen: null});
});

check("local knowledge card: invitation when empty, counts after", () => {
  assert.match(knowledgeStatus([]), /about 5 minutes each/);
  assert.equal(knowledgeStatus([{status: "pending"}, {status: "approved"}]), "2 sent for review · 1 approved");
});

check("progress counts answered cases and what is left", () => {
  const answers = new Map([[cases[0].case_id, {answer: "agree"}], [cases[2].case_id, {answer: "unsure"}]]);
  assert.deepEqual(caseProgress(cases, answers), {answered: 2, total: 4, remaining: 2});
  assert.equal(progressText(caseProgress(cases, answers)), "2 of 4 answered");
  assert.deepEqual(caseProgress([], new Map()), {answered: 0, total: 0, remaining: 0});
});

check("resume at the first unanswered case, -1 when all are answered", () => {
  assert.equal(firstUnanswered(cases, new Map()), 0);
  assert.equal(firstUnanswered(cases, new Map([[cases[0].case_id, {}]])), 1);
  const all = new Map(cases.map((c) => [c.case_id, {}]));
  assert.equal(firstUnanswered(cases, all), -1);
});

check("filter by case type; all keeps every case", () => {
  assert.equal(filterCases(cases, "all").length, 4);
  assert.deepEqual(
    filterCases(cases, "institution_in_region").map((c) => c.case_id),
    [cases[0].case_id, cases[3].case_id],
  );
  assert.deepEqual(filterCases(cases, "local_language_relevance"), []);
});

check("time estimates are about N minutes, rounded up, with singular and zero cases", () => {
  assert.equal(estimateText(0), "nothing left");
  assert.equal(estimateText(0.5), "about 1 minute");
  assert.equal(estimateText(1), "about 1 minute");
  assert.equal(estimateText(3), "about 3 minutes");
  assert.equal(estimateText(78 * 0.5), "about 39 minutes");
  assert.equal(estimateText(10 * 2), "about 20 minutes");
});

check("fixed-value case types offer choices; typed kinds do not", () => {
  const region = caseChoices({kind: "institution_in_region"});
  assert.deepEqual(
    region.map((c) => c.value),
    ["in region", "not in region"],
  );
  const type = caseChoices({kind: "institution_type", options: ["education", "company", "unsure"]});
  assert.deepEqual(
    type.map((c) => c.value),
    ["education", "company"],
  );
  assert.equal(caseChoices({kind: "local_terms"}), null);
  assert.equal(caseChoices({kind: "local_language_relevance"}), null);
});

check("admitting terms are the quoted place names, or the local term", () => {
  const inRegion = {
    kind: "institution_in_region",
    evidence: {signals: ['affiliation mentions "Bergen"', "author country NO", 'affiliation mentions "Oslo"']},
  };
  assert.deepEqual(admittingTerms(inRegion), ["Bergen", "Oslo"]);
  assert.deepEqual(admittingTerms({kind: "local_terms", evidence: {term: "plast"}}), ["plast"]);
  assert.deepEqual(admittingTerms({kind: "institution_type", evidence: {}}), []);
});

check("highlight wraps admitting terms in mark and escapes everything else", () => {
  assert.equal(
    highlightHtml("University of Bergen", ["Bergen"]),
    "University of <mark>Bergen</mark>",
  );
  // Case-insensitive; the longer term wins where two overlap.
  assert.equal(highlightHtml("plastic plastics", ["plastic", "plastics"]), "<mark>plastic</mark> <mark>plastics</mark>");
  assert.equal(highlightHtml("bergen", ["BERGEN"]), "<mark>bergen</mark>");
  // Markup in the text is escaped, also inside a highlighted term.
  assert.equal(
    highlightHtml('<img src=x onerror="a">Bergen', ["Bergen"]),
    "&lt;img src=x onerror=&quot;a&quot;&gt;<mark>Bergen</mark>",
  );
  // A term that is itself markup-like is matched as text, never as HTML.
  assert.equal(highlightHtml("a <b> c", ["<b>"]), "a <mark>&lt;b&gt;</mark> c");
  // Regular-expression characters in a term are literal.
  assert.equal(highlightHtml("x.y xzy", ["x.y"]), "<mark>x.y</mark> xzy");
  assert.equal(highlightHtml("none here", []), "none here");
  assert.equal(highlightHtml(null, ["x"]), "");
});

check("answer body: agree and unsure carry no value; disagree needs one", () => {
  assert.deepEqual(answerBody({region: "norway", caseId: cases[0].case_id, answer: "agree"}), {
    region: "norway",
    case_id: cases[0].case_id,
    answer: "agree",
  });
  assert.deepEqual(answerBody({region: "norway", caseId: cases[0].case_id, answer: "unsure"}), {
    region: "norway",
    case_id: cases[0].case_id,
    answer: "unsure",
  });
  assert.deepEqual(
    answerBody({region: "norway", caseId: cases[1].case_id, answer: "disagree", correctValue: " company "}),
    {region: "norway", case_id: cases[1].case_id, answer: "disagree", correct_value: "company"},
  );
  assert.equal(answerBody({region: "norway", caseId: cases[1].case_id, answer: "disagree", correctValue: "  "}), null);
  assert.equal(answerBody({region: "norway", caseId: cases[1].case_id, answer: "maybe"}), null);
  assert.equal(answerBody({region: "norway", caseId: "", answer: "agree"}), null);
});

check("https addresses only, no credentials", () => {
  assert.equal(httpsAddress("https://example.org/a"), true);
  assert.equal(httpsAddress("http://example.org"), false);
  assert.equal(httpsAddress("https://user:pw@example.org"), false);
  assert.equal(httpsAddress("not a url"), false);
});

check("clean text collapses spaces and refuses markup and control characters", () => {
  assert.equal(cleanText("  a \n  b  ", 20), "a b");
  assert.equal(cleanText("a<b", 20), null);
  assert.equal(cleanText("x".repeat(21), 20), null);
  assert.equal(cleanText("a\u0007b", 20), null);
  assert.equal(cleanText(undefined, 20), "");
});

check("submission bodies: confirm and not relevant carry the item id and an optional note", () => {
  const id = "norway:funding:3";
  assert.deepEqual(submissionBody({region: "norway", kind: "confirm", itemId: id, note: " ok "}), {
    region: "norway",
    stream: "confirm",
    kind: "confirm",
    payload: {item_id: id, note: "ok"},
  });
  assert.deepEqual(submissionBody({region: "norway", kind: "not_relevant", itemId: id, note: ""}), {
    region: "norway",
    stream: "confirm",
    kind: "not_relevant",
    payload: {item_id: id},
  });
});

check("correction needs a name, an https address or a note, and only https addresses", () => {
  const id = "norway:policy:0";
  assert.deepEqual(
    submissionBody({region: "norway", kind: "correct", itemId: id, name: "New name", url: "https://example.org/x"}),
    {
      region: "norway",
      stream: "confirm",
      kind: "correct",
      payload: {item_id: id, name: "New name", url: "https://example.org/x"},
    },
  );
  assert.deepEqual(submissionBody({region: "norway", kind: "correct", itemId: id, note: "Only a note"}).payload, {
    item_id: id,
    note: "Only a note",
  });
  assert.equal(submissionBody({region: "norway", kind: "correct", itemId: id, name: "", url: ""}), null);
  assert.equal(submissionBody({region: "norway", kind: "correct", itemId: id, url: "http://example.org"}), null);
  assert.equal(submissionBody({region: "norway", kind: "correct", itemId: id, url: "https://user@x.org"}), null);
  assert.equal(submissionBody({region: "norway", kind: "correct", itemId: id, name: "<b>x</b>"}), null);
  assert.equal(submissionBody({region: "norway", kind: "delete", itemId: id}), null);
  assert.equal(submissionBody({region: "norway", kind: "confirm", itemId: ""}), null);
});

check("items to confirm keep the region.json item_id and skip confirmed or not-relevant items", () => {
  const sections = [
    {
      id: "funding",
      title: "Funding",
      items: [
        {item_id: "norway:funding:0", name: "A", url: "", status: "to_confirm", note: "n"},
        {item_id: "norway:funding:1", name: "B", url: "https://b.example", status: "confirmed", note: "n"},
      ],
    },
    {id: "policy", title: "Policy", items: [{item_id: "norway:policy:2", name: "C", url: "", status: "draft", note: ""}]},
  ];
  const items = itemsToConfirm(sections);
  assert.deepEqual(
    items.map((i) => i.item_id),
    ["norway:funding:0", "norway:policy:2"],
  );
  assert.equal(items[1].section_title, "Policy");
  assert.equal(itemsToConfirm(null).length, 0);
});

check("latest submission per item for one region, newest first", () => {
  const rows = [
    {region: "norway", stream: "confirm", status: "pending", payload: {item_id: "norway:funding:0"}},
    {region: "norway", stream: "confirm", status: "rejected", payload: {item_id: "norway:funding:0"}},
    {region: "belgium", stream: "confirm", status: "approved", payload: {item_id: "belgium:funding:0"}},
    {region: "norway", stream: "knowledge", status: "approved", payload: {item_id: "norway:funding:0"}},
  ];
  const byItem = latestSubmissionByItem(rows, "norway");
  assert.equal(byItem.get("norway:funding:0").status, "pending");
  assert.equal(byItem.has("belgium:funding:0"), false);
  assert.equal(reviewText("pending"), "Sent for review");
  assert.equal(reviewText("approved"), "Accepted");
  assert.equal(reviewText("rejected"), "Not accepted");
  assert.equal(reviewText("other"), "");
});

check("stream B choice text names the choice and the review state", () => {
  assert.equal(choiceText({kind: "confirm", status: "pending"}), "Confirmed. Waiting for review.");
  assert.equal(choiceText({kind: "not_relevant", status: "pending"}), "Marked not relevant. Waiting for review.");
  assert.equal(choiceText({kind: "correct", status: "pending"}), "Correction sent. Waiting for review.");
  assert.equal(choiceText({kind: "confirm", status: "approved"}), "Confirmed. Accepted.");
  assert.equal(choiceText({kind: "correct", status: "rejected"}), "Correction sent. Not accepted.");
  assert.equal(choiceText({kind: "other", status: "pending"}), "");
  assert.equal(choiceText(undefined), "");
});

check("active regions only, in order", () => {
  const ambassador = {
    regions: [
      {region: "norway", status: "active"},
      {region: "belgium", status: "pending_email"},
      {region: "california", status: "active"},
    ],
  };
  assert.deepEqual(activeRegions(ambassador), ["norway", "california"]);
  assert.deepEqual(activeRegions({}), []);
});

check("error text: workspace codes first, then the shared sign-up map, then the generic line", () => {
  assert.match(workspaceErrorText("not_region_member"), /not open/);
  assert.match(workspaceErrorText("rate_limited"), /too many attempts/);
  assert.match(workspaceErrorText("SQLITE_BUSY stack"), /Something went wrong/);
});

check("the region map: the region is highlighted and the view zooms to it; California outlines, not the country", () => {
  const world = {
    crop: [0, 400], w: 1000, sphere: "M0 0", ca: "M1 1Z",
    countries: [{iso_a2: "US", d: "M2 2"}, {iso_a2: "NO", d: "M3 3"}],
  };
  const rows = [
    {kind: "country", iso: "US", name: "United States", geom: [-125, 32, -114, 42]},
    {kind: "admin1", iso: "US", name: "California", geom: [-124.4, 32.5, -114.1, 42]},
    {kind: "country", iso: "NO", name: "Norway", geom: [5, 58, 31, 71]},
  ];
  const geo = {
    world,
    rows,
    regions: [
      {slug: "california", country_codes: ["US"], subdivision_names: ["California"]},
      {slug: "norway", country_codes: ["NO"], subdivision_names: []},
    ],
  };
  const ca = regionMapHTML(geo, "california");
  assert.match(ca, /viewBox="\d/);
  assert.match(ca, /<path class="ca open" d="M1 1Z"\/>/);
  assert.doesNotMatch(ca, /class="c open" d="M2 2"/);
  assert.match(ca, /class="c" d="M2 2"/);
  const no = regionMapHTML(geo, "norway");
  assert.match(no, /class="c open" d="M3 3"/);
  assert.doesNotMatch(no, /class="ca open"/);
  assert.equal(regionMapHTML(geo, "nowhere"), "");
  assert.equal(regionPlace({country_codes: ["US"], subdivision_names: ["California"]}, rows).name, "California");
  assert.equal(regionPlace({country_codes: ["NO"], subdivision_names: []}, rows).name, "Norway");
  assert.equal(regionPlace({country_codes: []}, rows), null);
});

check("progress summary: per-stream answered, share and minutes left, and the region's overall share", () => {
  // Stream A: 2 of 4 cases answered, 30 seconds each -> 1 minute left. Stream B: 1 of 3 items sent, 2 minutes each -> 4.
  const summary = progressSummary([
    {done: 2, total: 4, minutes: 0.5},
    {done: 1, total: 3, minutes: 2},
  ]);
  assert.deepEqual(summary.streams[0], {done: 2, total: 4, remaining: 2, percent: 50, minutes: 1});
  assert.deepEqual(summary.streams[1], {done: 1, total: 3, remaining: 2, percent: 33, minutes: 4});
  assert.deepEqual(
    {done: summary.done, total: summary.total, remaining: summary.remaining, percent: summary.percent, minutes: summary.minutes},
    {done: 3, total: 7, remaining: 4, percent: 43, minutes: 5},
  );
  assert.equal(timeLeftText(summary.minutes), "Time left: about 5 minutes");
  // Everything answered: nothing left; an empty region has no share and nothing to do.
  const done = progressSummary([{done: 4, total: 4, minutes: 0.5}, {done: 0, total: 0, minutes: 2}]);
  assert.equal(done.percent, 100);
  assert.equal(timeLeftText(done.minutes), "Nothing left to do");
  const empty = progressSummary([]);
  assert.deepEqual({done: empty.done, total: empty.total, percent: empty.percent}, {done: 0, total: 0, percent: 0});
  // Counts are clamped: more answers than cases never go negative, and a single minute reads singular.
  const over = progressSummary([{done: 9, total: 4, minutes: 0.5}, {done: 2, total: 3, minutes: 0.5}]);
  assert.equal(over.streams[0].remaining, 0);
  assert.equal(over.streams[0].done, 4);
  assert.equal(timeLeftText(over.streams[1].minutes), "Time left: about 1 minute");
});

check("the map frame is the shared world_map.js frame, so the map box can reserve its aspect ratio", () => {
  assert.deepEqual(mapFrame({crop: [10, 210], w: 1000}), [0, 10, 1000, 200]);
});

console.log(`${passed} workspace runtime checks passed`);
