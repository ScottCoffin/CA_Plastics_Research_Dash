import { audit, type Ctx } from "./auth";
import type { Env } from "./env";
import { REGIONS, isRegion } from "./eligibility";
import { json } from "./http";
import { MODERATION_LIMIT, accountWithinLimit, err, moderator, readBody } from "./moderation";
import { ENTITY_TYPE, GEOGRAPHIC_SCOPE, PLASTICS_CENTRALITY, PRIMARY_ACTIVITIES, REVIEW_REASON, SECTOR } from "./groups_taxonomy";

// Community groups quality assurance (Add-on A4, CG-7b; BFFP §7.2-7.3, migration 0008).
//
// Deliberate blind second tags: one random position in each consecutive block of 10 usable primary tags per region
// (exactly 10%). The sampled group is held for a different active ambassador of the region, who sees it as an
// ordinary group in their batch. AMB-POOL stays first-wins: the first tag is the canonical candidate and every later
// tag carries the private second_tag_for link. The first usable second tag of a usable primary is recorded as a pair,
// with basis 'sample' (the tagger held the sample) or 'overlap' (two ambassadors happened to tag the same group).
//
// Reviewer checks: each ambassador's first 25 usable primary tags, then one random position in each block of 5
// (exactly 20%). A reviewer (owner or lead, never the tag's author) agrees with or edits each Tier-1 facet; an edit
// keeps the original and reviewed values with a reason code. The first complete review wins.
//
// A usable tag has status ambassador_tagged and is not marked not_an_organisation. Selection SQL runs in the same D1
// batch as the tag insert, so a retry repairs nothing twice and concurrent tags read the same block draw.

export const TIER1_FACETS = ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"] as const;
export type Tier1Facet = (typeof TIER1_FACETS)[number];

export const SAMPLE_BLOCK = 10;
export const REVIEW_FIRST = 25;
export const REVIEW_BLOCK = 5;
/** At most this many sampled groups join one batch. */
export const SAMPLE_BATCH_MAX = 5;
const REVIEW_QUEUE_LIMIT = 50;
const MAX_ACTIVITIES = 5;

const SINGLE_VOCAB: Record<Exclude<Tier1Facet, "primary_activities">, readonly string[]> = {
  entity_type: ENTITY_TYPE,
  sector: SECTOR,
  plastics_centrality: PLASTICS_CENTRALITY,
  geographic_scope: GEOGRAPHIC_SCOPE,
};

/** SQL condition: the submission aliased `x` is a usable tag (ambassador_tagged, not not_an_organisation). */
function usable(x: string): string {
  return `json_extract(${x}.payload, '$.status') = 'ambassador_tagged' ` +
    `AND COALESCE(json_extract(${x}.payload, '$.not_an_organisation'), 0) = 0`;
}

/** SQL condition: the submission aliased `x` is a primary (first) group tag. */
function primary(x: string): string {
  return `${x}.kind = 'group_tag' AND json_extract(${x}.payload, '$.second_tag_for') IS NULL`;
}

/** The caller's own tag of the group (?1 ambassador, ?2 group) when it is a usable primary. */
const OWN_PRIMARY =
  "own AS (SELECT s.id, s.region FROM submissions s WHERE s.kind = 'group_tag' AND s.ambassador_id = ?1 " +
  `AND json_extract(s.payload, '$.group_id') = ?2 AND json_extract(s.payload, '$.second_tag_for') IS NULL AND ${usable("s")})`;

/** Ordinal of that primary among the region's usable primaries (ids are monotonic, so the ordinal is stable). */
const REGION_ORDINAL =
  `WITH ${OWN_PRIMARY}, ord AS (SELECT own.id, own.region, (SELECT COUNT(*) FROM submissions c WHERE ${primary("c")} ` +
  `AND c.region = own.region AND c.id <= own.id AND ${usable("c")}) AS n FROM own) `;

/** Ordinal of that primary among the ambassador's own usable primaries, in every region. */
const AMBASSADOR_ORDINAL =
  `WITH ${OWN_PRIMARY}, ord AS (SELECT own.id, (SELECT COUNT(*) FROM submissions c WHERE ${primary("c")} ` +
  `AND c.ambassador_id = ?1 AND c.id <= own.id AND ${usable("c")}) AS n FROM own) `;

/** A uniform integer in [0, n). */
function randomBelow(n: number): number {
  const buf = new Uint32Array(1);
  crypto.getRandomValues(buf);
  return buf[0] % n;
}

/**
 * Statements appended to the group_tag insert batch (after the insert). For a usable primary they record the sample
 * and review selections; for a usable second tag they record the pair; either way the caller's sample hold ends.
 * Every statement is idempotent, so a retried submission changes nothing.
 */
export function qaStatements(db: D1Database, ambassadorId: string, groupId: string, now: number): D1PreparedStatement[] {
  return [
    db.prepare(
      `${REGION_ORDINAL}INSERT OR IGNORE INTO group_qa_blocks (kind, scope, block_no, pick) ` +
        `SELECT 'sample', region, (n - 1) / ${SAMPLE_BLOCK}, ?3 FROM ord`,
    ).bind(ambassadorId, groupId, randomBelow(SAMPLE_BLOCK)),
    db.prepare(
      `${REGION_ORDINAL}INSERT OR IGNORE INTO group_tag_samples (primary_id, group_id, region, selected_at) ` +
        "SELECT ord.id, ?2, ord.region, ?3 FROM ord JOIN group_qa_blocks b ON b.kind = 'sample' AND b.scope = ord.region " +
        `AND b.block_no = (ord.n - 1) / ${SAMPLE_BLOCK} WHERE (ord.n - 1) % ${SAMPLE_BLOCK} = b.pick`,
    ).bind(ambassadorId, groupId, now),
    db.prepare(
      `${AMBASSADOR_ORDINAL}INSERT OR IGNORE INTO group_qa_blocks (kind, scope, block_no, pick) ` +
        `SELECT 'review', ?1, (n - ${REVIEW_FIRST + 1}) / ${REVIEW_BLOCK}, ?3 FROM ord WHERE n > ${REVIEW_FIRST}`,
    ).bind(ambassadorId, groupId, randomBelow(REVIEW_BLOCK)),
    db.prepare(
      `${AMBASSADOR_ORDINAL}INSERT OR IGNORE INTO group_review_picks (submission_id, basis, selected_at) ` +
        `SELECT ord.id, CASE WHEN ord.n <= ${REVIEW_FIRST} THEN 'first_25' ELSE 'random_20' END, ?3 FROM ord ` +
        `LEFT JOIN group_qa_blocks b ON b.kind = 'review' AND b.scope = ?1 AND ord.n > ${REVIEW_FIRST} ` +
        `AND b.block_no = (ord.n - ${REVIEW_FIRST + 1}) / ${REVIEW_BLOCK} ` +
        `WHERE ord.n <= ${REVIEW_FIRST} OR (ord.n - ${REVIEW_FIRST + 1}) % ${REVIEW_BLOCK} = b.pick`,
    ).bind(ambassadorId, groupId, now),
    db.prepare(
      "WITH mine AS (SELECT s.id, json_extract(s.payload, '$.second_tag_for') AS primary_id FROM submissions s " +
        "WHERE s.kind = 'group_tag' AND s.ambassador_id = ?1 AND json_extract(s.payload, '$.group_id') = ?2 " +
        `AND json_extract(s.payload, '$.second_tag_for') IS NOT NULL AND ${usable("s")}) ` +
        "INSERT OR IGNORE INTO group_tag_pairs (primary_id, second_id, basis, paired_at) " +
        "SELECT mine.primary_id, mine.id, CASE WHEN EXISTS (SELECT 1 FROM group_tag_samples t " +
        "WHERE t.primary_id = mine.primary_id AND t.assigned_to = ?1) THEN 'sample' ELSE 'overlap' END, ?3 " +
        `FROM mine JOIN submissions p ON p.id = mine.primary_id WHERE ${usable("p")}`,
    ).bind(ambassadorId, groupId, now),
    // The caller's hold ends with any tag; a completed sample also releases another ambassador's hold.
    db.prepare(
      "UPDATE group_tag_samples SET assigned_to = NULL, hold_until = NULL WHERE group_id = ?2 AND (assigned_to = ?1 " +
        "OR EXISTS (SELECT 1 FROM group_tag_pairs x WHERE x.primary_id = group_tag_samples.primary_id))",
    ).bind(ambassadorId, groupId),
  ];
}

// ---------------------------------------------------------------------------------------------------------------
// Sample holds in the batch

/** SQL condition on sample `t`: still open for the ambassador ?1 (no pair yet, no own tag of the group). */
const SAMPLE_OPEN_FOR_CALLER =
  "NOT EXISTS (SELECT 1 FROM group_tag_pairs x WHERE x.primary_id = t.primary_id) " +
  "AND NOT EXISTS (SELECT 1 FROM submissions o WHERE o.kind = 'group_tag' AND o.ambassador_id = ?1 " +
  "AND json_extract(o.payload, '$.group_id') = t.group_id)";

/**
 * Union arm for the caller's active holds (binds ?1 ambassador, ?2 region, ?3 now): sampled groups the caller holds.
 */
export const HELD_SAMPLES_SQL =
  `SELECT t.group_id FROM group_tag_samples t WHERE t.assigned_to = ?1 AND t.region = ?2 AND t.hold_until > ?3 AND ${SAMPLE_OPEN_FOR_CALLER}`;

/**
 * Holds up to SAMPLE_BATCH_MAX open samples of the region for the caller, oldest first. A sample is open when it has
 * no pair, no unexpired holder, a primary by another ambassador that moderation has not rejected, and no tag by the
 * caller. One UPDATE, so two concurrent claims never share a sample. Returns the number held.
 */
export async function claimSamples(db: D1Database, ambassadorId: string, region: string, now: number, holdMs: number): Promise<number> {
  const res = await db.prepare(
    "UPDATE group_tag_samples SET assigned_to = ?1, hold_until = ?4 WHERE primary_id IN (" +
      "SELECT t.primary_id FROM group_tag_samples t JOIN submissions p ON p.id = t.primary_id " +
      "WHERE t.region = ?2 AND p.ambassador_id <> ?1 AND p.status <> 'rejected' " +
      `AND (t.assigned_to IS NULL OR t.hold_until IS NULL OR t.hold_until <= ?3) AND ${SAMPLE_OPEN_FOR_CALLER} ` +
      "ORDER BY t.primary_id LIMIT ?5) AND (assigned_to IS NULL OR hold_until IS NULL OR hold_until <= ?3)",
  ).bind(ambassadorId, region, now, now + holdMs, SAMPLE_BATCH_MAX).run();
  return res.meta.changes;
}

/** Extends the caller's unexpired hold on a sampled group (the form's 15-minute refresh). */
export function refreshSampleHold(
  db: D1Database,
  ambassadorId: string,
  region: string,
  groupId: string,
  now: number,
  holdMs: number,
): D1PreparedStatement {
  return db.prepare(
    "UPDATE group_tag_samples SET hold_until = ?5 WHERE group_id = ?2 AND assigned_to = ?1 AND region = ?3 AND hold_until > ?4",
  ).bind(ambassadorId, groupId, region, now, now + holdMs);
}

// ---------------------------------------------------------------------------------------------------------------
// Reviewer checks

type Obj = Record<string, unknown>;

/** The stored form of a facet value: a vocabulary string, or activities joined by ";" in their listed order. */
export function facetValue(payload: Obj, facet: Tier1Facet): string | null {
  const value = payload[facet];
  if (facet === "primary_activities") {
    return Array.isArray(value) && value.length > 0 && value.every((v) => typeof v === "string") ? value.join(";") : null;
  }
  return typeof value === "string" ? value : null;
}

/** A reviewer's edited value, validated like the tag form (V2, V5), in stored form; null when invalid. */
function editedValue(facet: Tier1Facet, value: unknown): string | null {
  if (facet === "primary_activities") {
    if (!Array.isArray(value) || value.length < 1 || value.length > MAX_ACTIVITIES) return null;
    if (!value.every((v) => typeof v === "string" && PRIMARY_ACTIVITIES.includes(v))) return null;
    if (new Set(value).size !== value.length) return null;
    return value.join(";");
  }
  if (typeof value !== "string" || !SINGLE_VOCAB[facet].includes(value)) return null;
  if (facet === "plastics_centrality" && value === "cannot_determine") return null;
  return value;
}

interface ReviewRow {
  facet: Tier1Facet;
  outcome: "agree" | "edit";
  original: string;
  reviewed: string;
  reason: string | null;
}

/** Parses the facets object against the stored payload; returns the rows or the first failing field. */
function parseReview(facets: unknown, payload: Obj): { rows: ReviewRow[] } | { field: string } {
  if (typeof facets !== "object" || facets === null || Array.isArray(facets)) return { field: "facets" };
  const given = facets as Obj;
  for (const key of Object.keys(given)) if (!(TIER1_FACETS as readonly string[]).includes(key)) return { field: key };
  const rows: ReviewRow[] = [];
  for (const facet of TIER1_FACETS) {
    const entry = given[facet];
    const original = facetValue(payload, facet);
    if (original === null) return { field: facet };
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) return { field: facet };
    const e = entry as Obj;
    if (e.outcome === "agree") {
      if (Object.keys(e).some((k) => k !== "outcome")) return { field: facet };
      rows.push({ facet, outcome: "agree", original, reviewed: original, reason: null });
    } else if (e.outcome === "edit") {
      if (Object.keys(e).some((k) => !["outcome", "value", "reason_code"].includes(k))) return { field: facet };
      const reviewed = editedValue(facet, e.value);
      if (reviewed === null || reviewed === original) return { field: facet };
      if (typeof e.reason_code !== "string" || !REVIEW_REASON.includes(e.reason_code)) return { field: `${facet}.reason_code` };
      rows.push({ facet, outcome: "edit", original, reviewed, reason: e.reason_code });
    } else {
      return { field: facet };
    }
  }
  return { rows };
}

/**
 * GET /groups/reviews?region=: approved primary tags selected for a reviewer check and not yet reviewed, oldest
 * decision first. Owner and leads only; a reviewer never sees their own tags. No ambassador ids or names.
 */
export async function handleReviewQueue(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const m = await moderator(request, env, ctx);
  if ("error" in m) return m.error;
  const region = new URL(request.url).searchParams.get("region");
  if (region !== null && !isRegion(region)) return err("invalid_region", 400, { regions: REGIONS });
  const rows = await env.DB.prepare(
    "SELECT s.id, s.region, s.payload, s.decided_at FROM group_review_picks r JOIN submissions s ON s.id = r.submission_id " +
      "WHERE s.status = 'approved' AND s.ambassador_id <> ?1 AND (?2 IS NULL OR s.region = ?2) " +
      "AND NOT EXISTS (SELECT 1 FROM group_tag_reviews v WHERE v.submission_id = s.id) ORDER BY s.decided_at, s.id LIMIT ?3",
  ).bind(m.a.id, region, REVIEW_QUEUE_LIMIT).all<{ id: number; region: string; payload: string; decided_at: number }>();
  return json({
    ok: true,
    region,
    reviews: rows.results.map((r) => ({
      submission_id: r.id,
      region: r.region,
      decided_at: r.decided_at,
      payload: JSON.parse(r.payload) as unknown,
    })),
  });
}

/**
 * POST /groups/reviews {submission_id, facets: {<tier-1 facet>: {outcome: "agree"} | {outcome: "edit", value,
 * reason_code}}}: records the check of every Tier-1 facet at once. The insert is one statement guarded by "no review
 * yet", so the first complete review wins and a concurrent one gets 409 already_reviewed.
 */
export async function handleReview(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const m = await moderator(request, env, ctx);
  if ("error" in m) return m.error;
  const body = await readBody(request);
  if (!body) return err("invalid_request", 400);
  const id = body.submission_id;
  if (typeof id !== "number" || !Number.isSafeInteger(id) || id < 1) return err("invalid_id", 400);
  if (!(await accountWithinLimit(env.DB, "moderate", m.a.id, MODERATION_LIMIT.limit, MODERATION_LIMIT.windowMs, ctx.now))) {
    return err("rate_limited", 429);
  }
  const item = await env.DB.prepare(
    "SELECT s.ambassador_id, s.status, s.payload, EXISTS (SELECT 1 FROM group_review_picks r WHERE r.submission_id = s.id) AS picked " +
      "FROM submissions s WHERE s.id = ?1 AND s.kind = 'group_tag'",
  ).bind(id).first<{ ambassador_id: string; status: string; payload: string; picked: number }>();
  if (!item) return err("not_found", 404);
  if (item.ambassador_id === m.a.id) return err("self_review", 403);
  if (!item.picked) return err("not_selected", 409);
  if (item.status !== "approved") return err("not_approved", 409);
  const parsed = parseReview(body.facets, JSON.parse(item.payload) as Obj);
  if ("field" in parsed) return err("invalid_review", 400, { field: parsed.field });

  // ?1 submission, ?2 reviewer, ?3 time; then five binds per facet row.
  const values: string[] = [];
  const binds: unknown[] = [id, m.a.id, ctx.now];
  for (const row of parsed.rows) {
    const at = binds.length + 1;
    values.push(`(?1, ?${at}, ?${at + 1}, ?${at + 2}, ?${at + 3}, ?${at + 4}, ?2, ?3)`);
    binds.push(row.facet, row.outcome, row.original, row.reviewed, row.reason);
  }
  const res = await env.DB.prepare(
    "INSERT INTO group_tag_reviews (submission_id, facet, outcome, original_value, reviewed_value, reason_code, reviewer_id, reviewed_at) " +
      `SELECT * FROM (VALUES ${values.join(", ")}) WHERE NOT EXISTS (SELECT 1 FROM group_tag_reviews WHERE submission_id = ?1)`,
  ).bind(...binds).run();
  if (res.meta.changes !== parsed.rows.length) return err("already_reviewed", 409);
  const edits = parsed.rows.filter((r) => r.outcome === "edit").length;
  await audit(env.DB, ctx.now, "groups.review", m.a.id, { submission_id: id, edits, by: m.role });
  return json({ ok: true, submission_id: id, edits }, 201);
}

// ---------------------------------------------------------------------------------------------------------------
// Export (GET /export/approved): pairs and reviews, never an ambassador id

function tier1Values(payload: Obj): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const facet of TIER1_FACETS) out[facet] = payload[facet] ?? null;
  return out;
}

/** Pairs whose primary is approved, changed at or after `since` (the later of the decision and the second tag). */
export async function exportPairs(db: D1Database, since: number): Promise<Obj[]> {
  const rows = await db.prepare(
    "SELECT p.region, p.payload AS a, s.payload AS b, MAX(p.decided_at, pr.paired_at) AS at FROM group_tag_pairs pr " +
      "JOIN submissions p ON p.id = pr.primary_id JOIN submissions s ON s.id = pr.second_id " +
      "WHERE p.status = 'approved' AND MAX(p.decided_at, pr.paired_at) >= ?1 ORDER BY at, pr.primary_id",
  ).bind(since).all<{ region: string; a: string; b: string; at: number }>();
  return rows.results.map((r) => {
    const a = JSON.parse(r.a) as Obj;
    return { group_id: a.group_id, region: r.region, paired_at: r.at, value_a: tier1Values(a), value_b: tier1Values(JSON.parse(r.b) as Obj) };
  });
}

/** Reviewer checks recorded at or after `since`, one row per facet. */
export async function exportReviews(db: D1Database, since: number): Promise<Obj[]> {
  const rows = await db.prepare(
    "SELECT json_extract(s.payload, '$.group_id') AS group_id, s.region, r.facet, r.outcome, r.reason_code, r.original_value, " +
      "r.reviewed_value, r.reviewed_at FROM group_tag_reviews r JOIN submissions s ON s.id = r.submission_id " +
      "WHERE r.reviewed_at >= ?1 ORDER BY r.reviewed_at, r.submission_id, r.facet",
  ).bind(since).all<Obj>();
  return rows.results;
}
