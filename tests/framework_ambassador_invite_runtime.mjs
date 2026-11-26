// Runtime checks for the co-author invite screen (AMB-1 front end slice 3c). The pure helpers live in
// framework/src/components/ambassador_invite.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {
  coAuthorRows,
  coAuthors,
  copyText,
  eligibilityText,
  eligibleRegions,
  parseMailto,
  rowsFromCoauthors,
} from "../framework/src/components/ambassador_invite.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

const SELF = "A-self";
const authorFile = {
  author: {name: "Self Person"},
  works: [
    {
      work_id: "W1",
      authors: [
        {id: SELF, name: "Self Person"},
        {id: "A-bo", name: "Bo Berg"},
        {id: "A-amy", name: "Amy Ash"},
        {name: "No Id"},
      ],
    },
    {
      work_id: "W2",
      authors: [
        {id: SELF, name: "Self Person"},
        {id: "A-bo", name: "Bo Berg"},
        {id: "A-bo", name: "Bo Berg"},
      ],
    },
    {work_id: "W3", authors: [{id: "A-cy", name: "Cy Dahl"}, {id: "A-amy", name: "Amy Ash"}]},
    {work_id: "W4"},
  ],
};

const eligibleBySlug = {
  california: new Set(["I-ucd"]),
  norway: new Set(["I-uio", "I-ntnu"]),
  belgium: new Set(["I-ugent"]),
};
const regionNames = {california: "California", norway: "Norway", belgium: "Belgium"};

check("coAuthors excludes self, skips missing ids, counts each co-author once per work", () => {
  const list = coAuthors(authorFile, SELF);
  assert.deepEqual(list, [
    {id: "A-amy", name: "Amy Ash", shared: 2},
    {id: "A-bo", name: "Bo Berg", shared: 2},
    {id: "A-cy", name: "Cy Dahl", shared: 1},
  ]);
  assert.equal(list.some((r) => r.id === SELF), false);
  assert.equal(list.some((r) => r.id === undefined), false);
});

check("coAuthors sorts by shared works descending, then name", () => {
  const file = {
    works: [
      {authors: [{id: "x", name: "Zed"}, {id: "y", name: "Abe"}, {id: "z", name: "Mia"}]},
      {authors: [{id: "z", name: "Mia"}, {id: "y", name: "Abe"}]},
    ],
  };
  assert.deepEqual(
    coAuthors(file, "none").map((r) => [r.id, r.shared]),
    [["y", 2], ["z", 2], ["x", 1]],
  );
});

check("coAuthors handles empty or missing works", () => {
  assert.deepEqual(coAuthors({}, SELF), []);
  assert.deepEqual(coAuthors(null, SELF), []);
  assert.deepEqual(coAuthors({works: [{}]}, SELF), []);
});

check("eligibleRegions lists every region whose set shares an institution", () => {
  assert.deepEqual(eligibleRegions(["I-zzz", "I-ntnu"], eligibleBySlug), ["norway"]);
  assert.deepEqual(eligibleRegions(["I-ucd", "I-ugent"], eligibleBySlug), ["california", "belgium"]);
});

check("eligibleRegions returns none for no match or no ids", () => {
  assert.deepEqual(eligibleRegions(["I-zzz"], eligibleBySlug), []);
  assert.deepEqual(eligibleRegions(undefined, eligibleBySlug), []);
  assert.deepEqual(eligibleRegions(["I-ucd"], {}), []);
});

const indexAuthors = [
  {author_id: "A-bo", name: "Bo Berg", primary_affiliations: ["University of Oslo", "Other"], institution_ids: ["I-uio"]},
  {author_id: "A-amy", name: "Amy Ash", primary_affiliations: [], institution_ids: ["I-ucd", "I-ugent"]},
  {author_id: "A-cy", name: "Cy Dahl", primary_affiliations: ["Somewhere Institute"], institution_ids: ["I-nope"]},
];

check("coAuthorRows builds rows with institution and region names", () => {
  const rows = coAuthorRows(coAuthors(authorFile, SELF), indexAuthors, eligibleBySlug, regionNames);
  assert.deepEqual(rows, [
    {id: "A-amy", name: "Amy Ash", shared: 2, institution: null, regions: ["California", "Belgium"]},
    {id: "A-bo", name: "Bo Berg", shared: 2, institution: "University of Oslo", regions: ["Norway"]},
    {id: "A-cy", name: "Cy Dahl", shared: 1, institution: "Somewhere Institute", regions: []},
  ]);
});

check("coAuthorRows gives unknown people null institution and no regions", () => {
  const rows = coAuthorRows([{id: "A-new", name: "New Person", shared: 1}], [], eligibleBySlug, regionNames);
  assert.deepEqual(rows, [{id: "A-new", name: "New Person", shared: 1, institution: null, regions: []}]);
});

check("coAuthorRows caps the list at 50 by default and honours a limit", () => {
  const list = Array.from({length: 60}, (_, i) => ({id: `A${i}`, name: `P${i}`, shared: 1}));
  assert.equal(coAuthorRows(list, [], eligibleBySlug, regionNames).length, 50);
  assert.equal(coAuthorRows(list, [], eligibleBySlug, regionNames, 3).length, 3);
});

check("eligibilityText covers one, two and no regions, and unknown institutions", () => {
  assert.equal(eligibilityText({regions: ["Norway"], institution: "X"}), "Their institution is eligible in Norway");
  assert.equal(
    eligibilityText({regions: ["California", "Belgium"], institution: null}),
    "Their institution is eligible in California and Belgium",
  );
  assert.equal(
    eligibilityText({regions: ["California", "Norway", "Belgium"], institution: null}),
    "Their institution is eligible in California, Norway and Belgium",
  );
  assert.equal(
    eligibilityText({regions: [], institution: "Somewhere Institute"}),
    "Their institution is not on a region list yet. They can still sign up and propose it.",
  );
  assert.equal(eligibilityText({regions: [], institution: null}), "Institution not known. They can still sign up.");
  assert.equal(eligibilityText({}), "Institution not known. They can still sign up.");
});

check("parseMailto reads subject and body with encoded newlines and symbols", () => {
  const href = "mailto:?subject=Join%20me%20%26%20more&body=Hello%2C%0A%0Ahttps%3A%2F%2Fx.test%2Fi%2Fabc%2B1%0A100%25";
  assert.deepEqual(parseMailto(href), {subject: "Join me & more", body: "Hello,\n\nhttps://x.test/i/abc+1\n100%"});
});

check("parseMailto keeps a literal plus and tolerates missing fields", () => {
  assert.deepEqual(parseMailto("mailto:?subject=A+B&body=C"), {subject: "A+B", body: "C"});
  assert.deepEqual(parseMailto("mailto:?body=%E0%A4"), {subject: "", body: "%E0%A4"});
  assert.deepEqual(parseMailto(""), {subject: "", body: ""});
});

check("rowsFromCoauthors maps the Worker answer to rows with region names", () => {
  const response = {
    ok: true,
    total: 2,
    works_read: 3,
    coauthors: [
      {id: "A1", name: "Bo Berg", shared: 2, institution_ids: ["I1"], institution: "University of Oslo", regions: ["norway", "belgium"]},
      {id: "A2", name: "", shared: 1, institution_ids: [], institution: null, regions: []},
    ],
  };
  assert.deepEqual(rowsFromCoauthors(response, regionNames), [
    {id: "A1", name: "Bo Berg", shared: 2, institution: "University of Oslo", regions: ["Norway", "Belgium"]},
    {id: "A2", name: "A2", shared: 1, institution: null, regions: []},
  ]);
});

check("rowsFromCoauthors gives no rows for a missing or empty answer and caps at 50", () => {
  assert.deepEqual(rowsFromCoauthors({ok: true, coauthors: []}, regionNames), []);
  assert.deepEqual(rowsFromCoauthors(null, regionNames), []);
  assert.deepEqual(rowsFromCoauthors({}, regionNames), []);
  const many = {coauthors: Array.from({length: 60}, (_, i) => ({id: `A${i}`, name: `P${i}`, shared: 1, regions: []}))};
  assert.equal(rowsFromCoauthors(many, regionNames).length, 50);
});

check("copyText puts the subject, a blank line, then the body", () => {
  assert.equal(copyText("Subject here", "Line one\n\nLine two"), "Subject: Subject here\n\nLine one\n\nLine two");
});

console.log(`${passed} invite helper checks passed`);
