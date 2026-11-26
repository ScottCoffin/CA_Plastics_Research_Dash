// Name-based pickers for the group tagging form (AMB-GROUPS-UX). Pure helpers: no DOM at import time.
// People choose languages and places by name; the codes (ISO 639-1, ISO 3166-1 alpha-2, and US-XX states) are what the
// Worker stores. Names come from Intl.DisplayNames in English, and US states are hard-coded.

/** ISO 639-1 two-letter language codes. */
export const LANGUAGE_CODES = "aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy da de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi yo za zh zu".split(" ");

/** ISO 3166-1 alpha-2 country codes. */
export const COUNTRY_CODES = ("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ " +
  "CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR " +
  "GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP " +
  "KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ " +
  "NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW " +
  "SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ " +
  "UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW").split(" ");

/** US states and DC as [code, English name]. */
export const US_STATES = [
  ["AL", "Alabama"], ["AK", "Alaska"], ["AZ", "Arizona"], ["AR", "Arkansas"], ["CA", "California"], ["CO", "Colorado"],
  ["CT", "Connecticut"], ["DE", "Delaware"], ["FL", "Florida"], ["GA", "Georgia"], ["HI", "Hawaii"], ["ID", "Idaho"],
  ["IL", "Illinois"], ["IN", "Indiana"], ["IA", "Iowa"], ["KS", "Kansas"], ["KY", "Kentucky"], ["LA", "Louisiana"],
  ["ME", "Maine"], ["MD", "Maryland"], ["MA", "Massachusetts"], ["MI", "Michigan"], ["MN", "Minnesota"], ["MS", "Mississippi"],
  ["MO", "Missouri"], ["MT", "Montana"], ["NE", "Nebraska"], ["NV", "Nevada"], ["NH", "New Hampshire"], ["NJ", "New Jersey"],
  ["NM", "New Mexico"], ["NY", "New York"], ["NC", "North Carolina"], ["ND", "North Dakota"], ["OH", "Ohio"], ["OK", "Oklahoma"],
  ["OR", "Oregon"], ["PA", "Pennsylvania"], ["RI", "Rhode Island"], ["SC", "South Carolina"], ["SD", "South Dakota"],
  ["TN", "Tennessee"], ["TX", "Texas"], ["UT", "Utah"], ["VT", "Vermont"], ["VA", "Virginia"], ["WA", "Washington"],
  ["WV", "West Virginia"], ["WI", "Wisconsin"], ["WY", "Wyoming"], ["DC", "District of Columbia"],
];

const languageNames = new Intl.DisplayNames(["en"], {type: "language"});
const regionNames = new Intl.DisplayNames(["en"], {type: "region"});

/** Name for a language code, e.g. "es" -> "Spanish". Falls back to the code only when Intl has no name. */
export function languageName(code) {
  return languageNames.of(code) || code;
}

/** Options for the language picker: {code, label}, sorted by label. */
export function languageOptions() {
  return LANGUAGE_CODES.map((code) => ({code, label: languageName(code)})).sort((a, b) => a.label.localeCompare(b.label, "en"));
}

/**
 * Options for the place picker: countries by name, then US states. A state label carries "(US state)" so names
 * that are also countries (Georgia) stay distinct.
 */
export function placeOptions() {
  const countries = COUNTRY_CODES.map((code) => ({code, label: regionNames.of(code) || code}));
  const states = US_STATES.map(([state, name]) => ({code: `US-${state}`, label: `${name} (US state)`}));
  return [...countries, ...states].sort((a, b) => a.label.localeCompare(b.label, "en"));
}

/** Case, accent and extra-space insensitive form of a name. */
const foldName = (value) => String(value || "").normalize("NFKD").replace(/\p{M}/gu, "").replace(/\s+/g, " ").trim().toLowerCase();

/**
 * Picks the option the typed text names. Tiers, best first: exact name or code, name prefix, word prefix, substring.
 * The first tier with any match decides. One match there picks it; several give {ambiguous: true} and no code.
 * Returns {code, ambiguous}; code is "" when nothing matches.
 */
export function pickerMatch(options, text) {
  const wanted = foldName(text);
  if (!wanted) return {code: "", ambiguous: false};
  const folded = options.map((option) => ({code: option.code, name: foldName(option.label), id: foldName(option.code)}));
  const escaped = wanted.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const wordPrefix = new RegExp(`(^|[^\\p{L}\\p{N}])${escaped}`, "u");
  const tiers = [
    (o) => o.name === wanted || o.id === wanted,
    (o) => o.name.startsWith(wanted),
    (o) => wordPrefix.test(o.name),
    (o) => o.name.includes(wanted),
  ];
  for (const matches of tiers) {
    const hits = folded.filter(matches);
    if (hits.length === 1) return {code: hits[0].code, ambiguous: false};
    if (hits.length > 1) return {code: "", ambiguous: true};
  }
  return {code: "", ambiguous: false};
}

/** The code the typed text picks, or "" when nothing or several options match. */
export function lookupPickerCode(options, text) {
  return pickerMatch(options, text).code;
}

/** Website languages prefilled for a region (removable in the form). */
export function languageDefaults(region) {
  if (region === "california") return ["en"];
  if (region === "norway") return ["no"];
  if (region === "belgium") return ["nl", "fr"];
  return [];
}

/** Places prefilled from the group's roster country and, for California, US-CA. */
export function placeDefaults(region, group) {
  const codes = [];
  const country = String(group?.country || "").trim().toUpperCase();
  if (COUNTRY_CODES.includes(country)) codes.push(country);
  if (region === "california" && !codes.includes("US-CA")) codes.push("US-CA");
  return codes.slice(0, 5);
}
