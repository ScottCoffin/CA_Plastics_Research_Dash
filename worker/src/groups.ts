import { currentAmbassador, type Ctx } from "./auth";
import type { Env } from "./env";
import { REGIONS, type Region, isRegion } from "./eligibility";
import { HELD_SAMPLES_SQL, claimSamples, refreshSampleHold } from "./group_qa";
import { json } from "./http";
import { err, plainText } from "./moderation";
import type { Fetch } from "./outbound";
import {
  CANNOT_DETERMINE_REASON,
  CONSTITUENCY,
  ENTITY_TYPE,
  GEOGRAPHIC_SCOPE,
  LEGAL_FORM,
  PARTICIPATION_IN_SCIENCE,
  PLASTICS_CENTRALITY,
  PRIMARY_ACTIVITIES,
  RELATION,
  SECTOR,
} from "./groups_taxonomy";

// Community groups (Add-on A4, CG-6a): 30-day leases on roster groups, and the tag and suggestion payloads that
// ambassadors send back. Leases follow BFFP §5.2; the tag rules follow §8.2 V1-V13 and the owner's decisions
// A4-D25 (sector joint_power_authority), A4-D26 (one to five primary activities) and A4-D27 (no conflict-of-interest
// rule). Tags are stored as submissions of kind group_tag (stream knowledge).

const DAY_MS = 24 * 60 * 60 * 1000;
export const BATCH_SIZE = 25;
export const LEASE_HOURS = 2;
const LEASE_MS = LEASE_HOURS * 60 * 60 * 1000;
// Each round uses one D1 batch and one count query. Leave room for auth and roster queries on the Free plan.
const MAX_CLAIM_ROUNDS = 20;
const ROSTER_PATH = "/data/global/groups/roster.json";
const ROSTER_CACHE_SECONDS = DAY_MS / 1000;
/** Same User-Agent as the other outbound reads in this worker (kept as a literal). */
const USER_AGENT = "PlastiverseLive-Ambassadors";
export const TAG_MAX_CHARS = 12000;
const SUGGEST_KEYS = ["name", "url", "country", "note"];

export const GROUP_ID_RE = /^cg_[0-9a-f]{16}$/;
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const ISO_COUNTRY_RE = /^[A-Za-z]{2}$/;
const ISO_LANG_RE = /^[a-z]{2}$/;
/** ISO 3166-1 alpha-2, or ISO 3166-2 (for example US-CA). */
const PLACE_RE = /^[A-Z]{2}(-[A-Z0-9]{1,3})?$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * A region's roster country. A subnational ambassador works on the country's groups (see TODO AMB-PARENT-REGION).
 * A region with no entry gets no groups.
 */
export const REGION_COUNTRY: Partial<Record<Region, string>> = { california: "US", norway: "NO", belgium: "BE" };

/** Result of a payload check: the stored JSON, or the first failing field. */
export type PayloadResult = { ok: true; json: string } | { ok: false; field: string };

export interface RosterGroup {
  group_id: string;
  name: string;
  country: string;
  region: string;
  url: string | null;
}

interface LeaseRow {
  group_id: string;
}

// ---------------------------------------------------------------------------------------------------------------
// Roster (published file, read through the Cache API for one day)

/** Records that do not match the published shape are skipped; a body without a records array is refused. */
function parseRoster(data: unknown): RosterGroup[] | null {
  const records = isPlainObject(data) ? data.records : undefined;
  if (!Array.isArray(records)) return null;
  const out: RosterGroup[] = [];
  for (const item of records) {
    if (!isPlainObject(item)) continue;
    const { group_id: groupId, name, country, region, url } = item;
    if (typeof groupId !== "string" || !GROUP_ID_RE.test(groupId)) continue;
    if (typeof name !== "string" || typeof country !== "string" || typeof region !== "string") continue;
    out.push({ group_id: groupId, name, country, region, url: typeof url === "string" ? url : null });
  }
  return out;
}

function rosterUrl(env: Env): string {
  return `${env.SITE_ORIGIN}${ROSTER_PATH}`;
}

async function readRosterCache(env: Env): Promise<RosterGroup[] | null> {
  if (typeof caches === "undefined") return null;
  try {
    const hit = await caches.default.match(new Request(rosterUrl(env)));
    return hit ? ((await hit.json()) as RosterGroup[]) : null;
  } catch {
    return null; // A cache fault only costs a refetch.
  }
}

async function writeRosterCache(env: Env, groups: RosterGroup[]): Promise<void> {
  if (typeof caches === "undefined") return;
  try {
    await caches.default.put(
      new Request(rosterUrl(env)),
      new Response(JSON.stringify(groups), {
        headers: { "Content-Type": "application/json", "Cache-Control": `max-age=${ROSTER_CACHE_SECONDS}` },
      }),
    );
  } catch {
    // A cache fault must not turn a good roster into an error.
  }
}

/** The published roster's groups, or null when it cannot be read. */
export async function loadRoster(env: Env, fetchImpl: Fetch): Promise<RosterGroup[] | null> {
  const cached = await readRosterCache(env);
  if (cached) return cached;
  let res: Response;
  try {
    res = await fetchImpl(rosterUrl(env), { headers: { Accept: "application/json", "User-Agent": USER_AGENT } });
  } catch {
    return null;
  }
  if (!res.ok) return null;
  let groups: RosterGroup[] | null;
  try {
    groups = parseRoster(await res.json());
  } catch {
    return null;
  }
  if (groups === null) return null;
  await writeRosterCache(env, groups);
  return groups;
}

// ---------------------------------------------------------------------------------------------------------------
// Leases

/** Active membership of the region (ambassador_regions, status active). Same rule as submissions.ts. */
async function isActiveMember(db: D1Database, ambassadorId: string, region: Region): Promise<boolean> {
  const row = await db
    .prepare("SELECT 1 AS ok FROM ambassador_regions WHERE ambassador_id = ?1 AND region = ?2 AND status = 'active'")
    .bind(ambassadorId, region)
    .first();
  return row !== null;
}

/** The caller's active holds: ordinary leases on untagged groups, plus sampled groups held for a blind second tag. */
async function activeLeases(db: D1Database, ambassadorId: string, region: Region, now: number): Promise<LeaseRow[]> {
  const rows = await db
    .prepare(
      "SELECT group_id FROM group_leases " +
      "WHERE ambassador_id = ?1 AND region = ?2 AND MIN(expires_at, leased_at + ?4) > ?3 " +
      "AND NOT EXISTS (SELECT 1 FROM submissions s WHERE s.kind='group_tag' AND json_extract(s.payload,'$.group_id')=group_leases.group_id) " +
      `UNION ${HELD_SAMPLES_SQL}`,
    )
    .bind(ambassadorId, region, now, LEASE_MS)
    .all<LeaseRow>();
  return rows.results;
}

/** Group ids with an effective, unexpired hold held by anyone (clamps legacy 30-day rows). */
async function leasedGroupIds(db: D1Database, now: number): Promise<Set<string>> {
  const rows = await db.prepare("SELECT group_id FROM group_leases WHERE MIN(expires_at, leased_at + ?2) > ?1").bind(now, LEASE_MS).all<{ group_id: string }>();
  return new Set(rows.results.map((r) => r.group_id));
}

/** Any accepted tag removes the group globally, including after a moderation rejection. */
async function taggedGroupIds(db: D1Database): Promise<Set<string>> {
  const rows = await db
    .prepare(
      "SELECT DISTINCT json_extract(payload, '$.group_id') AS group_id FROM submissions " +
        "WHERE kind = 'group_tag'",
    )
    .all<{ group_id: string | null }>();
  return new Set(rows.results.flatMap((r) => (r.group_id === null ? [] : [r.group_id])));
}

/** Roster groups of the country that are neither tagged nor under an unexpired lease, in roster order. */
async function unclaimedGroups(db: D1Database, roster: RosterGroup[], country: string, now: number): Promise<RosterGroup[]> {
  const [leased, tagged] = await Promise.all([leasedGroupIds(db, now), taggedGroupIds(db)]);
  return roster.filter((g) => g.country === country && !leased.has(g.group_id) && !tagged.has(g.group_id));
}

/**
 * Upsert that takes over only an expired lease. The WHERE clause makes two concurrent claims safe: a group that
 * another ambassador has just leased is left alone. The cap ?7 counts the caller's sample holds too (CG-7b).
 */
const UPSERT_LEASE =
  "INSERT INTO group_leases (group_id, ambassador_id, region, leased_at, expires_at, renewals) " +
  "SELECT ?1, ?2, ?3, ?4, ?5, 0 WHERE NOT EXISTS (SELECT 1 FROM submissions s WHERE s.kind='group_tag' " +
  "AND json_extract(s.payload,'$.group_id')=?1) AND (SELECT COUNT(*) FROM group_leases l WHERE l.ambassador_id=?2 " +
  "AND l.region=?3 AND MIN(l.expires_at,l.leased_at + ?6) > ?4) + (SELECT COUNT(*) FROM group_tag_samples t " +
  "WHERE t.assigned_to=?2 AND t.region=?3 AND t.hold_until > ?4) < ?7 " +
  "ON CONFLICT (group_id) DO UPDATE SET ambassador_id = excluded.ambassador_id, region = excluded.region, " +
  "leased_at = excluded.leased_at, expires_at = excluded.expires_at, renewals = 0 " +
  "WHERE MIN(group_leases.expires_at, group_leases.leased_at + ?6) <= ?4";

async function claimBatch(
  db: D1Database,
  ambassadorId: string,
  region: Region,
  roster: RosterGroup[],
  country: string,
  now: number,
): Promise<void> {
  const candidates = await unclaimedGroups(db, roster, country, now);
  for (let offset = 0; offset < candidates.length && offset < BATCH_SIZE * MAX_CLAIM_ROUNDS; offset += BATCH_SIZE) {
    const chunk = candidates.slice(offset, offset + BATCH_SIZE);
    await db.batch(chunk.map((g) =>
      db.prepare(UPSERT_LEASE).bind(g.group_id, ambassadorId, region, now, now + LEASE_MS, LEASE_MS, BATCH_SIZE),
    ));
    if ((await activeLeases(db, ambassadorId, region, now)).length >= BATCH_SIZE) break;
  }
}

/** GET /groups/batch?region=: active holds, claiming a batch only when none remain. */
export async function handleGroupBatch(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return err("not_signed_in", 401);
  const params = new URL(request.url).searchParams;
  const param = params.get("region");
  if (!isRegion(param)) return err("invalid_region", 400, { regions: REGIONS });
  if (!(await isActiveMember(env.DB, a.id, param))) return err("not_region_member", 403);
  const groupId = params.get("group_id");
  if (groupId !== null) {
    if (!GROUP_ID_RE.test(groupId)) return err("invalid_group_id", 400);
    await env.DB.batch([
      env.DB.prepare("UPDATE group_leases SET leased_at = ?1, expires_at = ?2 WHERE group_id = ?3 AND ambassador_id = ?4 AND region = ?5 AND MIN(expires_at, leased_at + ?6) > ?1 AND NOT EXISTS (SELECT 1 FROM submissions s WHERE s.kind='group_tag' AND json_extract(s.payload,'$.group_id')=?3)")
        .bind(ctx.now, ctx.now + LEASE_MS, groupId, a.id, param, LEASE_MS),
      refreshSampleHold(env.DB, a.id, param, groupId, ctx.now, LEASE_MS),
    ]);
    return json({ ok: true });
  }
  const roster = await loadRoster(env, ctx.fetch);
  if (roster === null) return err("upstream_unavailable", 502);

  const country = REGION_COUNTRY[param];
  if (country !== undefined && (await activeLeases(env.DB, a.id, param, ctx.now)).length === 0) {
    // Sampled groups first (blind second tags by a different ambassador), then untagged groups up to the cap.
    await claimSamples(env.DB, a.id, param, ctx.now, LEASE_MS);
    await claimBatch(env.DB, a.id, param, roster, country, ctx.now);
  }
  const byId = new Map((await activeLeases(env.DB, a.id, param, ctx.now)).map((l) => [l.group_id, l]));
  const leases = [];
  for (const g of roster) {
    const lease = byId.get(g.group_id);
    if (lease) {
      leases.push({
        group_id: g.group_id,
        name: g.name,
        country: g.country,
        url: g.url,
      });
    }
  }
  const remaining = country === undefined ? 0 : (await unclaimedGroups(env.DB, roster, country, ctx.now)).length;
  return json({ ok: true, region: param, leases, remaining_in_region: remaining });
}

// ---------------------------------------------------------------------------------------------------------------
// Payload validation (group_tag and group_suggest)

type Obj = Record<string, unknown>;

const TAG_KEYS = [
  "group_id",
  "status",
  "cannot_determine_reason",
  "entity_type",
  "sector",
  "plastics_centrality",
  "primary_activities",
  "geographic_scope",
  "places",
  "legal_form",
  "legal_form_note",
  "participation_in_science",
  "website_languages",
  "themes",
  "constituency",
  "stated_affiliations",
  "evidence",
  "not_an_organisation",
  "name_correction",
  "same_as",
];
/** Facets that must all be absent when not_an_organisation is true. */
const FACET_KEYS = [
  "entity_type",
  "sector",
  "plastics_centrality",
  "primary_activities",
  "geographic_scope",
  "places",
  "legal_form",
  "legal_form_note",
  "participation_in_science",
  "website_languages",
  "themes",
  "constituency",
  "stated_affiliations",
  "evidence",
];
/** Facets an evidence entry may cite (the tag's facet fields; legal_form_note is cited through legal_form). */
const EVIDENCE_FACETS = [
  "entity_type",
  "sector",
  "plastics_centrality",
  "primary_activities",
  "geographic_scope",
  "places",
  "legal_form",
  "participation_in_science",
  "website_languages",
  "themes",
  "constituency",
  "stated_affiliations",
];
const TIER1 = ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"];
const TIER1_EVIDENCE = ["plastics_centrality", "primary_activities"];
const MAX_EVIDENCE = 15;
const MAX_AFFILIATIONS = 10;
const MAX_LIST = 10;
/** Owner rule (2026-11-26): the plastics_centrality quote is 10 to 50 words; every other quote is at most 25. */
export const PLASTICS_QUOTE_MIN_WORDS = 10;
export const PLASTICS_QUOTE_MAX_WORDS = 50;
interface QuoteLimits {
  minWords: number;
  maxWords: number;
  maxChars: number;
}
const GENERAL_QUOTE: QuoteLimits = { minWords: 1, maxWords: 25, maxChars: 400 };
const PLASTICS_QUOTE: QuoteLimits = {
  minWords: PLASTICS_QUOTE_MIN_WORDS,
  maxWords: PLASTICS_QUOTE_MAX_WORDS,
  maxChars: 600,
};
/** AMB-ROSTER-QC: answers to "is this the same organisation as ...?" for likely-duplicate roster entries. */
export const SAME_AS_ANSWERS = ["same", "different", "unsure"];
const MAX_SAME_AS = 3;

function fail(field: string): PayloadResult {
  return { ok: false, field };
}

function isPlainObject(value: unknown): value is Obj {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function keysWithin(value: Obj, allowed: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}

/** Plain text (trimmed, no markup or control characters) up to max characters, or null. */
function text(value: unknown, max: number): string | null {
  return plainText(value, max);
}

function inVocabulary(vocab: readonly string[]): (value: unknown) => string | null {
  return (value) => (typeof value === "string" && vocab.includes(value) ? value : null);
}

/** An array of min to max items, each mapped by item(); null when any item fails or an item repeats. */
function list(value: unknown, min: number, max: number, item: (v: unknown) => string | null): string[] | null {
  if (!Array.isArray(value) || value.length < min || value.length > max) return null;
  const out: string[] = [];
  for (const v of value) {
    const t = item(v);
    if (t === null || out.includes(t)) return null;
    out.push(t);
  }
  return out;
}

function isWebUrl(value: string): boolean {
  if (value.length > 500 || /\s/.test(value) || /[<>]/.test(value)) return false;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return false;
  }
  return (url.protocol === "https:" || url.protocol === "http:") && url.username === "" && url.password === "" && url.hostname.length > 0;
}

function isIsoDate(value: string): boolean {
  if (!DATE_RE.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

/**
 * The citation shared by evidence entries and affiliations: url, accessed_at, and exactly one of a quote (within the
 * word and character limits) or not_stated true. Affiliations never accept not_stated (V11).
 */
function citation(value: Obj, notStatedAllowed: boolean, limits: QuoteLimits): Obj | null {
  const url = value.url;
  const accessed = value.accessed_at;
  if (typeof url !== "string" || !isWebUrl(url)) return null;
  if (typeof accessed !== "string" || !isIsoDate(accessed)) return null;
  if (value.not_stated !== undefined && typeof value.not_stated !== "boolean") return null;
  if (value.not_stated === true) {
    if (!notStatedAllowed || value.quote !== undefined) return null;
    return { url, accessed_at: accessed, quote: null, not_stated: true };
  }
  const quote = text(value.quote, limits.maxChars);
  if (quote === null) return null;
  const words = quote.split(/\s+/).length;
  if (words < limits.minWords || words > limits.maxWords) return null;
  return { url, accessed_at: accessed, quote, not_stated: false };
}

function evidenceEntry(value: unknown, status: string): Obj | null {
  if (!isPlainObject(value) || !keysWithin(value, ["facet", "url", "accessed_at", "quote", "not_stated", "note"])) return null;
  const facet = inVocabulary(EVIDENCE_FACETS)(value.facet);
  if (facet === null) return null;
  const plastics = facet === "plastics_centrality";
  // Owner rule (2026-11-26): an ambassador-tagged plastics_centrality entry must quote the page, not mark it not_stated.
  const notStatedAllowed = !(plastics && status === "ambassador_tagged");
  const cite = citation(value, notStatedAllowed, plastics ? PLASTICS_QUOTE : GENERAL_QUOTE);
  if (cite === null) return null;
  const note = value.note === undefined ? null : text(value.note, 200);
  if (value.note !== undefined && note === null) return null;
  return { facet, ...cite, note };
}

function affiliation(value: unknown): Obj | null {
  if (!isPlainObject(value) || !keysWithin(value, ["target_name", "relation", "evidence"])) return null;
  const name = text(value.target_name, 200);
  const relation = inVocabulary(RELATION)(value.relation);
  const ev = value.evidence;
  if (name === null || relation === null || !isPlainObject(ev)) return null;
  if (!keysWithin(ev, ["url", "accessed_at", "quote"])) return null;
  const cite = citation(ev, false, GENERAL_QUOTE);
  return cite === null ? null : { target_name: name, relation, evidence: cite };
}

/** A proposed display name: 2 to 200 characters of plain text that is not an email address, or null. */
function nameCorrection(value: unknown): string | null {
  const name = text(value, 200);
  if (name === null || name.length < 2 || EMAIL_RE.test(name)) return null;
  return name;
}

/** Validates a group_tag payload (tier 1 and tier 2 rules). Returns the stored JSON, or the first failing field. */
export function validateGroupTag(payload: unknown): PayloadResult {
  if (!isPlainObject(payload)) return fail("payload");
  for (const key of Object.keys(payload)) if (!TAG_KEYS.includes(key)) return fail(key);
  const p = payload;

  if (typeof p.group_id !== "string" || !GROUP_ID_RE.test(p.group_id)) return fail("group_id");
  if (p.status !== "ambassador_tagged" && p.status !== "cannot_determine") return fail("status");
  const status = p.status;
  const out: Obj = { group_id: p.group_id, status };

  if (status === "cannot_determine") {
    const reason = inVocabulary(CANNOT_DETERMINE_REASON)(p.cannot_determine_reason);
    if (reason === null) return fail("cannot_determine_reason");
    out.cannot_determine_reason = reason;
  } else if (p.cannot_determine_reason !== undefined) {
    return fail("cannot_determine_reason");
  }

  const singles: [string, readonly string[]][] = [
    ["entity_type", ENTITY_TYPE],
    ["sector", SECTOR],
    ["plastics_centrality", PLASTICS_CENTRALITY],
    ["geographic_scope", GEOGRAPHIC_SCOPE],
    ["legal_form", LEGAL_FORM],
    ["participation_in_science", PARTICIPATION_IN_SCIENCE],
  ];
  for (const [key, vocab] of singles) {
    if (p[key] === undefined) continue;
    const value = inVocabulary(vocab)(p[key]);
    if (value === null) return fail(key);
    out[key] = value;
  }
  // V2: plastics_centrality = cannot_determine only with status cannot_determine.
  if (status === "ambassador_tagged" && out.plastics_centrality === "cannot_determine") return fail("plastics_centrality");

  if (p.legal_form_note !== undefined) {
    const note = text(p.legal_form_note, 200);
    if (note === null) return fail("legal_form_note");
    out.legal_form_note = note;
  }

  if (p.primary_activities !== undefined) {
    // A4-D26: one to five activities (V5 allows at most five).
    const activities = list(p.primary_activities, 1, 5, inVocabulary(PRIMARY_ACTIVITIES));
    if (activities === null) return fail("primary_activities");
    out.primary_activities = activities;
  }

  if (p.places !== undefined) {
    const places = list(p.places, 0, 5, (v) => (typeof v === "string" && PLACE_RE.test(v) ? v : null));
    if (places === null) return fail("places");
    out.places = places;
  }

  // V6: participation other than not_applicable needs research_monitoring among the activities.
  if (p.participation_in_science !== undefined) {
    const activities = (out.primary_activities as string[] | undefined) ?? [];
    if (out.participation_in_science !== "not_applicable" && !activities.includes("research_monitoring")) {
      return fail("participation_in_science");
    }
  }

  if (p.website_languages !== undefined) {
    const languages = list(p.website_languages, 0, MAX_LIST, (v) => (typeof v === "string" && ISO_LANG_RE.test(v) ? v : null));
    if (languages === null) return fail("website_languages");
    out.website_languages = languages;
  }

  if (p.themes !== undefined) {
    const themes = list(p.themes, 0, MAX_LIST, (v) => text(v, 80));
    if (themes === null) return fail("themes");
    out.themes = themes;
  }

  if (p.constituency !== undefined) {
    const constituency = list(p.constituency, 0, MAX_LIST, inVocabulary(CONSTITUENCY));
    if (constituency === null) return fail("constituency");
    out.constituency = constituency;
  }

  if (p.stated_affiliations !== undefined) {
    if (!Array.isArray(p.stated_affiliations) || p.stated_affiliations.length > MAX_AFFILIATIONS) return fail("stated_affiliations");
    const items: Obj[] = [];
    for (const item of p.stated_affiliations) {
      const parsed = affiliation(item);
      if (parsed === null) return fail("stated_affiliations");
      items.push(parsed);
    }
    out.stated_affiliations = items;
  }

  if (p.evidence !== undefined) {
    if (!Array.isArray(p.evidence) || p.evidence.length > MAX_EVIDENCE) return fail("evidence");
    const items: Obj[] = [];
    for (const item of p.evidence) {
      const parsed = evidenceEntry(item, status);
      if (parsed === null) return fail("evidence");
      items.push(parsed);
    }
    out.evidence = items;
  }

  if (p.not_an_organisation !== undefined) {
    if (typeof p.not_an_organisation !== "boolean") return fail("not_an_organisation");
    if (p.not_an_organisation) {
      const facet = FACET_KEYS.find((key) => p[key] !== undefined);
      if (facet !== undefined) return fail(facet);
    }
    out.not_an_organisation = p.not_an_organisation;
  }

  // Any status may propose a corrected display name (a wrong name can be why a group is hard to find).
  if (p.name_correction !== undefined) {
    const name = nameCorrection(p.name_correction);
    if (name === null) return fail("name_correction");
    out.name_correction = name;
  }

  // AMB-ROSTER-QC: any status may answer the duplicate questions (one answer per other group, never itself).
  if (p.same_as !== undefined) {
    if (!Array.isArray(p.same_as) || p.same_as.length > MAX_SAME_AS) return fail("same_as");
    const answers: Obj[] = [];
    for (const item of p.same_as) {
      if (!isPlainObject(item) || !keysWithin(item, ["group_id", "answer"])) return fail("same_as");
      const other = item.group_id;
      if (typeof other !== "string" || !GROUP_ID_RE.test(other) || other === p.group_id) return fail("same_as");
      if (answers.some((a) => a.group_id === other)) return fail("same_as");
      if (typeof item.answer !== "string" || !SAME_AS_ANSWERS.includes(item.answer)) return fail("same_as");
      answers.push({ group_id: other, answer: item.answer });
    }
    out.same_as = answers;
  }

  // Tier 1 (V2, V4): an ambassador_tagged group has the five core facets and evidence for two of them.
  if (status === "ambassador_tagged") {
    for (const key of TIER1) if (out[key] === undefined) return fail(key);
    const evidence = (out.evidence as Obj[] | undefined) ?? [];
    for (const facet of TIER1_EVIDENCE) {
      if (!evidence.some((e) => e.facet === facet)) return fail("evidence");
    }
  }

  return finish(out, TAG_MAX_CHARS);
}

/** Validates a group_suggest payload: a group the ambassador found and the roster lacks. */
export function validateGroupSuggest(payload: unknown): PayloadResult {
  if (!isPlainObject(payload)) return fail("payload");
  for (const key of Object.keys(payload)) if (!SUGGEST_KEYS.includes(key)) return fail(key);
  const name = text(payload.name, 200);
  if (name === null) return fail("name");
  const url = payload.url;
  if (typeof url !== "string" || !isWebUrl(url)) return fail("url");
  const out: Obj = { name, url };
  if (payload.country !== undefined) {
    const country = payload.country;
    if (typeof country !== "string" || !ISO_COUNTRY_RE.test(country)) return fail("country");
    out.country = country.toUpperCase();
  }
  if (payload.note !== undefined) {
    const note = text(payload.note, 1000);
    if (note === null) return fail("note");
    out.note = note;
  }
  return finish(out, 4000);
}

/** Last checks shared by both kinds: no email-looking string anywhere, and the stored size cap. */
function finish(out: Obj, maxChars: number): PayloadResult {
  const stored = JSON.stringify(out);
  if (EMAIL_RE.test(stored)) return fail("email");
  if (stored.length > maxChars) return fail("payload");
  return { ok: true, json: stored };
}
