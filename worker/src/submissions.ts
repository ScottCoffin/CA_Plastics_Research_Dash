import { audit, currentAmbassador, type AmbassadorRow, type Ctx } from "./auth";
import type { Env } from "./env";
import { REGIONS, type Region, isRegion } from "./eligibility";
import { json } from "./http";
import { accountWithinLimit, err, plainText, readBody } from "./moderation";

const HOUR_MS = 60 * 60 * 1000;
export const SUBMIT_LIMIT = { limit: 30, windowMs: HOUR_MS };
export const ANSWER_LIMIT = { limit: 600, windowMs: HOUR_MS };
const CASE_ID_RE = /^amb-[0-9a-f]{12}$/;
const ITEM_ID_RE = /^[A-Za-z0-9_.:/#-]{1,200}$/;
const PAYLOAD_MAX_CHARS = 4000;
const LIST_LIMIT = 200;

type Field = "name" | "url" | "description" | "contact_route" | "licence" | "note" | "item_id";
const MAX_LENGTH: Record<Field, number> = {
  name: 200,
  url: 500,
  description: 1000,
  contact_route: 300,
  licence: 200,
  note: 1000,
  item_id: 200,
};

interface KindSpec {
  stream: "confirm" | "knowledge";
  required: Field[];
  optional: Field[];
  /** At least one of these must be present (beyond the required fields). */
  anyOf?: Field[];
}

/**
 * Stream B (confirm the region page's placeholders) and stream C (local knowledge). Allowed keys per kind; anything
 * else is refused. Only the kind's own fields are stored.
 */
export const KINDS: Record<string, KindSpec> = {
  confirm: { stream: "confirm", required: ["item_id"], optional: ["note"] },
  correct: { stream: "confirm", required: ["item_id"], optional: ["name", "url", "note"], anyOf: ["name", "url", "note"] },
  not_relevant: { stream: "confirm", required: ["item_id"], optional: ["note"] },
  community_group: { stream: "knowledge", required: ["name", "url"], optional: ["description", "contact_route", "note"] },
  volunteer_group: { stream: "knowledge", required: ["name", "url"], optional: ["description", "contact_route", "note"] },
  policy: { stream: "knowledge", required: ["name", "url"], optional: ["description", "note"] },
  funder: { stream: "knowledge", required: ["name", "url"], optional: ["description", "note"] },
  dataset: { stream: "knowledge", required: ["name", "url", "licence"], optional: ["description", "contact_route", "note"] },
  research_network: { stream: "knowledge", required: ["name", "url"], optional: ["description", "contact_route", "note"] },
  event: { stream: "knowledge", required: ["name"], optional: ["url", "description", "note"] },
  media: { stream: "knowledge", required: ["name", "url"], optional: ["description", "note"] },
  institution: { stream: "knowledge", required: ["name"], optional: ["url", "description", "note"] },
  researcher: { stream: "knowledge", required: ["name", "url"], optional: ["description", "note"] },
  community_knowledge: { stream: "knowledge", required: ["name", "contact_route"], optional: ["url", "description", "note"] },
  correction: { stream: "knowledge", required: ["item_id"], optional: ["name", "url", "description", "note"], anyOf: ["name", "url", "description", "note"] },
};

/** https only, no credentials, no whitespace or HTML. The stored value is the trimmed text as sent. */
export function isHttpsUrl(value: string): boolean {
  if (value.length > MAX_LENGTH.url || /\s/.test(value) || /[<>]/.test(value)) return false;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return false;
  }
  return url.protocol === "https:" && url.username === "" && url.password === "" && url.hostname.length > 0;
}

/** Validates a submission payload against its kind. Returns the stored JSON, or the first failing field. */
export function validatePayload(spec: KindSpec, payload: unknown): { ok: true; json: string } | { ok: false; field: string } {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return { ok: false, field: "payload" };
  const allowed = new Set<string>([...spec.required, ...spec.optional]);
  const clean: Partial<Record<Field, string>> = {};
  for (const [key, value] of Object.entries(payload as Record<string, unknown>)) {
    if (!allowed.has(key)) return { ok: false, field: key };
    if (typeof value !== "string") return { ok: false, field: key };
    const field = key as Field;
    const text = field === "item_id" ? value.trim() : plainText(value, MAX_LENGTH[field]);
    if (text === null) return { ok: false, field };
    if (field === "item_id" && (text.length > MAX_LENGTH.item_id || !ITEM_ID_RE.test(text))) return { ok: false, field };
    if (field === "url" && !isHttpsUrl(text)) return { ok: false, field };
    clean[field] = text;
  }
  for (const field of spec.required) {
    if (clean[field] === undefined) return { ok: false, field };
  }
  if (spec.anyOf && !spec.anyOf.some((field) => clean[field] !== undefined)) return { ok: false, field: spec.anyOf[0] };
  const stored = JSON.stringify(clean);
  if (stored.length > PAYLOAD_MAX_CHARS) return { ok: false, field: "payload" };
  return { ok: true, json: stored };
}

/** Active membership of the region (ambassador_regions, status active). */
async function isActiveMember(db: D1Database, ambassadorId: string, region: Region): Promise<boolean> {
  const row = await db
    .prepare("SELECT 1 AS ok FROM ambassador_regions WHERE ambassador_id = ?1 AND region = ?2 AND status = 'active'")
    .bind(ambassadorId, region)
    .first();
  return row !== null;
}

interface ConsensusRow {
  case_id: string;
  answer: string;
  correct_value: string | null;
  n: number;
}

/**
 * Consensus per case in one region: two or more active ambassadors giving the same non-'unsure' answer (and, for
 * 'disagree', the same correct value). A case with two different agreed values has no consensus (null).
 */
export async function consensusByCase(
  db: D1Database,
  region: Region,
): Promise<Map<string, { answer: string; correct_value: string | null }>> {
  const rows = await db
    .prepare(
      "SELECT ca.case_id, ca.answer, ca.correct_value, COUNT(*) AS n " +
        "FROM case_answers ca JOIN ambassadors a ON a.id = ca.ambassador_id " +
        "WHERE ca.region = ?1 AND ca.answer <> 'unsure' AND a.status = 'active' " +
        "GROUP BY ca.case_id, ca.answer, ca.correct_value HAVING COUNT(*) >= 2",
    )
    .bind(region)
    .all<ConsensusRow>();
  const byCase = new Map<string, ConsensusRow[]>();
  for (const row of rows.results) {
    const list = byCase.get(row.case_id) ?? [];
    list.push(row);
    byCase.set(row.case_id, list);
  }
  const out = new Map<string, { answer: string; correct_value: string | null }>();
  for (const [caseId, list] of byCase) {
    if (list.length === 1) out.set(caseId, { answer: list[0].answer, correct_value: list[0].correct_value });
  }
  return out;
}

/** POST /cases/answer {region, case_id, answer, correct_value?}: one answer per ambassador and case. */
export async function handleCaseAnswer(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return err("not_signed_in", 401);
  const body = await readBody(request);
  if (!body) return err("invalid_request", 400);
  if (!isRegion(body.region)) return err("invalid_region", 400, { regions: REGIONS });
  const region = body.region;
  if (typeof body.case_id !== "string" || !CASE_ID_RE.test(body.case_id)) return err("invalid_case_id", 400);
  const caseId = body.case_id;
  const answer = body.answer;
  if (answer !== "agree" && answer !== "disagree" && answer !== "unsure") return err("invalid_answer", 400);
  let correctValue: string | null = null;
  if (answer === "disagree") {
    correctValue = plainText(body.correct_value, 200);
    if (correctValue === null) return err("correct_value_required", 400);
  } else if (body.correct_value !== undefined && body.correct_value !== null) {
    return err("correct_value_not_allowed", 400);
  }
  if (!(await isActiveMember(env.DB, a.id, region))) return err("not_region_member", 403);
  if (!(await accountWithinLimit(env.DB, "answer", a.id, ANSWER_LIMIT.limit, ANSWER_LIMIT.windowMs, ctx.now))) {
    return err("rate_limited", 429);
  }

  await env.DB.prepare(
    "INSERT INTO case_answers (ambassador_id, region, case_id, answer, correct_value, answered_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6) " +
      "ON CONFLICT (ambassador_id, region, case_id) DO UPDATE SET answer = excluded.answer, " +
      "correct_value = excluded.correct_value, answered_at = excluded.answered_at",
  )
    .bind(a.id, region, caseId, answer, correctValue, ctx.now)
    .run();
  await audit(env.DB, ctx.now, "case.answer", a.id, { region, answer });

  // The caller sees the consensus for this case only once it exists (single answers stay private).
  const consensus = (await consensusByCase(env.DB, region)).get(caseId) ?? null;
  return json({ ok: true, region, case_id: caseId, answer, correct_value: correctValue, consensus });
}

/** GET /cases/answers?region=: the caller's own answers, each with the consensus when one exists. */
export async function handleCaseAnswers(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return err("not_signed_in", 401);
  const regionParam = new URL(request.url).searchParams.get("region");
  if (!isRegion(regionParam)) return err("invalid_region", 400, { regions: REGIONS });
  if (!(await isActiveMember(env.DB, a.id, regionParam))) return err("not_region_member", 403);
  const own = await env.DB.prepare(
    "SELECT case_id, answer, correct_value, answered_at FROM case_answers WHERE ambassador_id = ?1 AND region = ?2 ORDER BY case_id LIMIT ?3",
  )
    .bind(a.id, regionParam, LIST_LIMIT)
    .all<{ case_id: string; answer: string; correct_value: string | null; answered_at: number }>();
  const consensus = await consensusByCase(env.DB, regionParam);
  return json({
    ok: true,
    region: regionParam,
    answers: own.results.map((r) => ({
      case_id: r.case_id,
      answer: r.answer,
      correct_value: r.correct_value,
      answered_at: r.answered_at,
      consensus: consensus.get(r.case_id) ?? null,
    })),
  });
}

/** POST /submissions {region, stream, kind, payload}: a pending item for the moderation queue. */
export async function handleSubmit(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a: AmbassadorRow | null = await currentAmbassador(request, env, ctx.now);
  if (!a) return err("not_signed_in", 401);
  const body = await readBody(request);
  if (!body) return err("invalid_request", 400);
  if (!isRegion(body.region)) return err("invalid_region", 400, { regions: REGIONS });
  const region = body.region;
  // Own-property lookup only, so names such as "toString" are not kinds.
  const kind = typeof body.kind === "string" && Object.hasOwn(KINDS, body.kind) ? KINDS[body.kind] : undefined;
  if (typeof body.kind !== "string" || !kind) return err("invalid_kind", 400);
  if (body.stream !== kind.stream) return err("stream_kind_mismatch", 400);
  const checked = validatePayload(kind, body.payload);
  if (!checked.ok) return err("invalid_payload", 400, { field: checked.field });
  if (!(await isActiveMember(env.DB, a.id, region))) return err("not_region_member", 403);
  if (!(await accountWithinLimit(env.DB, "submit", a.id, SUBMIT_LIMIT.limit, SUBMIT_LIMIT.windowMs, ctx.now))) {
    return err("rate_limited", 429);
  }

  const row = await env.DB.prepare(
    "INSERT INTO submissions (ambassador_id, region, stream, kind, payload, status, created_at) " +
      "VALUES (?1, ?2, ?3, ?4, ?5, 'pending', ?6) RETURNING id",
  )
    .bind(a.id, region, kind.stream, body.kind, checked.json, ctx.now)
    .first<{ id: number }>();
  await audit(env.DB, ctx.now, "submission.create", a.id, { region, stream: kind.stream, kind: body.kind });
  return json({ ok: true, id: row?.id ?? null, status: "pending" }, 201);
}

/** GET /submissions/mine: the caller's submissions with their decision status. */
export async function handleMySubmissions(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return err("not_signed_in", 401);
  const rows = await env.DB.prepare(
    "SELECT id, region, stream, kind, payload, status, created_at, decided_at, decision_note FROM submissions " +
      "WHERE ambassador_id = ?1 ORDER BY id DESC LIMIT ?2",
  )
    .bind(a.id, LIST_LIMIT)
    .all<{
      id: number;
      region: string;
      stream: string;
      kind: string;
      payload: string;
      status: string;
      created_at: number;
      decided_at: number | null;
      decision_note: string | null;
    }>();
  return json({
    ok: true,
    submissions: rows.results.map((r) => ({
      id: r.id,
      region: r.region,
      stream: r.stream,
      kind: r.kind,
      payload: JSON.parse(r.payload) as unknown,
      status: r.status,
      created_at: r.created_at,
      decided_at: r.decided_at,
      decision_note: r.decision_note,
    })),
  });
}
