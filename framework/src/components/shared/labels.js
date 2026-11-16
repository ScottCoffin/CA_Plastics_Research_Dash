// Display labels for vocabulary slugs (VD-10). Presentation only: URL hashes, <option value>
// attributes, data and CSV exports keep the raw slug; only text shown on screen goes through these
// helpers. No DOM access and no imports, so Node tests can load this file.

// Atlas institution types (ATLAS_TYPES in src/atlas/ingest/institutions.py) plus "other", the value
// the pages use for an institution without a type. Sectors use this same vocabulary.
export const INSTITUTION_TYPE_LABELS = Object.freeze({
  UC: "University of California",
  CSU: "California State University",
  "other-public": "Other public",
  private: "Private",
  "community-college": "Community college",
  "nonprofit/NGO": "Nonprofit or NGO",
  "state-agency": "State agency",
  federal: "Federal agency",
  "local-agency": "Local agency",
  JPA: "Joint powers authority",
  company: "Company",
  utility: "Utility",
  "intergovernmental-organization": "Intergovernmental organization",
  other: "Other institution"
});

// OpenAlex work types the pipeline handles (rank table in src/atlas/ingest/normalize.py, exclude_types
// in config/queries_v3.yml, the type counts in docs/S4_2_VERIFICATION.md), plus "unknown" for works
// without a type.
export const WORK_TYPE_LABELS = Object.freeze({
  article: "Article",
  review: "Review",
  "book-chapter": "Book chapter",
  book: "Book",
  "conference-paper": "Conference paper",
  "conference-abstract": "Conference abstract",
  "proceedings-article": "Proceedings article",
  preprint: "Preprint",
  "posted-content": "Posted content",
  dataset: "Dataset",
  dissertation: "Dissertation",
  report: "Report",
  letter: "Letter",
  editorial: "Editorial",
  erratum: "Erratum",
  paratext: "Paratext",
  "peer-review": "Peer review",
  retraction: "Retraction",
  other: "Other",
  unknown: "Unknown"
});

// Readable text for a slug that has no label: hyphens become spaces and the first letter is capitalised.
export function humanise(value) {
  if (value === null || value === undefined) return "";
  const text = String(value).trim().replace(/-/g, " ");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

function hasLabel(map, value) {
  return Object.prototype.hasOwnProperty.call(map, value);
}

export function institutionTypeLabel(value) {
  if (value === null || value === undefined || value === "") return "";
  return hasLabel(INSTITUTION_TYPE_LABELS, value) ? INSTITUTION_TYPE_LABELS[value] : humanise(value);
}

export function workTypeLabel(value) {
  if (value === null || value === undefined || value === "") return "";
  return hasLabel(WORK_TYPE_LABELS, value) ? WORK_TYPE_LABELS[value] : humanise(value);
}

// Sector values are institution types. An unknown value passes through unchanged, as the network
// page has always shown it (tests/framework_network_runtime.mjs pins that).
export function sectorLabel(value) {
  if (value === null || value === undefined || value === "") return "";
  return hasLabel(INSTITUTION_TYPE_LABELS, value) ? INSTITUTION_TYPE_LABELS[value] : String(value);
}
