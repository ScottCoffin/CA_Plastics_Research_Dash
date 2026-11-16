// Runtime checks for the VD-10 display labels. The helpers live in
// framework/src/components/shared/labels.js; network_model.js delegates its sector label to them.
// tests/test_vd10_labels.py checks these lists against the Python sources they mirror.
import assert from "node:assert/strict";
import {
  INSTITUTION_TYPE_LABELS,
  WORK_TYPE_LABELS,
  humanise,
  institutionTypeLabel,
  sectorLabel,
  workTypeLabel
} from "../framework/src/components/shared/labels.js";
import {sectorLabel as networkSectorLabel} from "../framework/src/components/network_model.js";

// ATLAS_TYPES in src/atlas/ingest/institutions.py, plus "other" (the pages' fallback type).
const ATLAS_TYPES = [
  "UC", "CSU", "other-public", "private", "community-college", "nonprofit/NGO", "state-agency",
  "federal", "local-agency", "JPA", "company", "utility", "intergovernmental-organization"
];
// Work types found in code: the rank table in src/atlas/ingest/normalize.py, exclude_types in
// config/queries_v3.yml, the F10 slugs, and the "unknown" bucket used by the bundle.
const WORK_TYPES = [
  "article", "review", "book-chapter", "book", "conference-paper", "proceedings-article",
  "preprint", "posted-content", "dataset", "conference-abstract", "editorial", "erratum",
  "paratext", "peer-review", "retraction", "dissertation", "report", "letter", "other", "unknown"
];

const isSlugFree = (label) => !/[-/]/.test(label);

// Every vocabulary value has an explicit label, and the label is readable text (no hyphen or slash).
for (const type of ATLAS_TYPES) {
  assert.ok(Object.hasOwn(INSTITUTION_TYPE_LABELS, type), `missing institution label: ${type}`);
  const label = institutionTypeLabel(type);
  assert.ok(label && isSlugFree(label), `${type} -> ${label}`);
  assert.notEqual(label, type);
  assert.equal(sectorLabel(type), label, `sector label for ${type}`);
  assert.equal(networkSectorLabel(type), label, `network sector label for ${type}`);
}
for (const type of WORK_TYPES) {
  assert.ok(Object.hasOwn(WORK_TYPE_LABELS, type), `missing work-type label: ${type}`);
  const label = workTypeLabel(type);
  assert.ok(label && isSlugFree(label), `${type} -> ${label}`);
  assert.notEqual(label, type);
}

// The institution map has exactly the Atlas types plus "other".
assert.deepEqual(Object.keys(INSTITUTION_TYPE_LABELS).sort(), [...ATLAS_TYPES, "other"].sort());
for (const value of [...Object.values(INSTITUTION_TYPE_LABELS), ...Object.values(WORK_TYPE_LABELS)]) {
  assert.equal(typeof value, "string");
  assert.ok(value.trim().length > 0);
}

// Wording kept from the network page and the F10 examples.
assert.equal(institutionTypeLabel("UC"), "University of California");
assert.equal(institutionTypeLabel("nonprofit/NGO"), "Nonprofit or NGO");
assert.equal(institutionTypeLabel("local-agency"), "Local agency");
assert.equal(institutionTypeLabel("community-college"), "Community college");
assert.equal(institutionTypeLabel("other-public"), "Other public");
assert.equal(institutionTypeLabel("intergovernmental-organization"), "Intergovernmental organization");
assert.equal(workTypeLabel("book-chapter"), "Book chapter");
assert.equal(workTypeLabel("conference-abstract"), "Conference abstract");
assert.equal(workTypeLabel("unknown"), "Unknown");

// Unknown values fall back to humanised text; null and empty values give "".
assert.equal(humanise("zebra-crossing"), "Zebra crossing");
assert.equal(humanise("  "), "");
assert.equal(institutionTypeLabel("zebra-type"), "Zebra type");
assert.equal(workTypeLabel("new-kind"), "New kind");
for (const empty of [null, undefined, ""]) {
  assert.equal(institutionTypeLabel(empty), "");
  assert.equal(workTypeLabel(empty), "");
  assert.equal(sectorLabel(empty), "");
}

// Sector labels keep the network page's old behaviour: an unknown sector passes through unchanged.
assert.equal(sectorLabel("mystery"), "mystery");
assert.equal(networkSectorLabel("mystery"), "mystery");
assert.equal(sectorLabel("UC"), "University of California");
assert.equal(networkSectorLabel("nonprofit/NGO"), "Nonprofit or NGO");
