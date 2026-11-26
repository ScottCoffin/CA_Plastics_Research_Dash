import { currentAmbassador, type Ctx } from "./auth";
import type { Env } from "./env";
import type { Fetch } from "./outbound";
import { regionsForInstitution } from "./eligibility";
import { json } from "./http";
import { accountWithinLimit } from "./moderation";

const HOUR_MS = 60 * 60 * 1000;
const CACHE_SECONDS = 7 * 24 * 60 * 60;
/** Per-account limit on uncached co-author reads (each one spends an OpenAlex call). */
export const COAUTHORS_LIMIT = { limit: 30, windowMs: HOUR_MS };
/** Rows returned to the client. */
export const COAUTHORS_ROWS = 50;
const WORKS_PER_PAGE = 200;
const INSTITUTIONS_PER_PERSON = 5;
/** Same User-Agent as the ORCID lookups in openalex.ts (kept as a literal; that module does not export it). */
const USER_AGENT = "PlastiverseLive-Ambassadors";
const AUTHOR_ID = /^A\d{4,12}$/;

export interface Coauthor {
  /** Short OpenAlex author id (A<digits>). */
  id: string;
  name: string;
  /** Works the ambassador and this person share (within the works read). */
  shared: number;
  institution_ids: string[];
  institution: string | null;
  /** Region slugs whose allowlist lists one of the institution ids. */
  regions: string[];
}

export interface CoauthorsBody {
  ok: true;
  coauthors: Coauthor[];
  total: number;
  works_read: number;
}

interface RawInstitution {
  id?: unknown;
  display_name?: unknown;
}

interface RawAuthorship {
  author?: { id?: unknown; display_name?: unknown };
  institutions?: RawInstitution[];
}

interface RawWork {
  authorships?: RawAuthorship[];
}

/** Short id (A<digits> or I<digits>) from a short or openalex.org URL form, or null. */
function shortId(value: unknown, prefix: "A" | "I"): string | null {
  if (typeof value !== "string") return null;
  const match = value.match(new RegExp(`^(?:https?://openalex\\.org/)?(${prefix}\\d+)$`));
  return match ? match[1] : null;
}

function text(value: unknown, max = 200): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

/** Works (newest first) for one author. Throws on any non-200 answer or malformed body. */
async function fetchWorks(fetchImpl: Fetch, authorId: string): Promise<RawWork[]> {
  const url =
    `https://api.openalex.org/works?filter=author.id:${authorId}&per-page=${WORKS_PER_PAGE}` +
    "&select=id,authorships&sort=publication_date:desc";
  const res = await fetchImpl(url, { headers: { Accept: "application/json", "User-Agent": USER_AGENT } });
  if (!res.ok) throw new Error(`openalex responded ${res.status}`);
  const data = (await res.json()) as { results?: unknown };
  if (!Array.isArray(data.results)) throw new Error("openalex body has no results");
  return data.results as RawWork[];
}

/** Co-authors across the works (self excluded, each counted once per work), with regions from the allowlists. */
export function summariseCoauthors(works: RawWork[], selfId: string): CoauthorsBody {
  const people = new Map<string, Coauthor>();
  for (const work of works) {
    const seen = new Set<string>();
    for (const authorship of Array.isArray(work?.authorships) ? work.authorships : []) {
      const id = shortId(authorship?.author?.id, "A");
      if (!id || id === selfId || seen.has(id)) continue;
      seen.add(id);
      const institutions = Array.isArray(authorship.institutions) ? authorship.institutions : [];
      let person = people.get(id);
      if (!person) {
        person = {
          id,
          name: text(authorship.author?.display_name) || id,
          shared: 0,
          institution_ids: [],
          institution: text(institutions[0]?.display_name) || null,
          regions: [],
        };
        people.set(id, person);
      }
      person.shared += 1;
      for (const inst of institutions) {
        const instId = shortId(inst?.id, "I");
        if (instId && !person.institution_ids.includes(instId) && person.institution_ids.length < INSTITUTIONS_PER_PERSON) {
          person.institution_ids.push(instId);
        }
      }
    }
  }
  const all = [...people.values()];
  for (const person of all) {
    for (const instId of person.institution_ids) {
      for (const region of regionsForInstitution(instId)) if (!person.regions.includes(region)) person.regions.push(region);
    }
  }
  all.sort((a, b) => b.shared - a.shared || a.name.localeCompare(b.name));
  return { ok: true, coauthors: all.slice(0, COAUTHORS_ROWS), total: all.length, works_read: works.length };
}

/** Workers Cache API entry for one author, or null when the cache is not available (tests). */
function cacheKey(authorId: string): Request {
  return new Request(`https://cache.internal/coauthors/${authorId}`);
}

async function readCache(authorId: string): Promise<CoauthorsBody | null> {
  if (typeof caches === "undefined") return null;
  try {
    const hit = await caches.default.match(cacheKey(authorId));
    return hit ? ((await hit.json()) as CoauthorsBody) : null;
  } catch {
    return null; // A cache fault only costs a fresh read.
  }
}

async function writeCache(authorId: string, body: CoauthorsBody): Promise<void> {
  if (typeof caches === "undefined") return;
  // A cache fault must not turn a good answer into an error.
  await caches.default.put(
    cacheKey(authorId),
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json", "Cache-Control": `max-age=${CACHE_SECONDS}` },
    }),
  ).catch(() => undefined);
}

/**
 * GET /me/coauthors (session): the ambassador's co-authors from OpenAlex works, with the institution and eligible
 * regions of each. Nothing is stored in D1; no emails or ORCIDs are read or returned.
 */
export async function handleCoauthors(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return json({ ok: false, error: "not_signed_in" }, 401);
  if (!a.author_id || !AUTHOR_ID.test(a.author_id)) {
    return json({ ok: true, coauthors: [], reason: "no_author_record" });
  }
  const authorId = a.author_id;
  const cached = await readCache(authorId);
  if (cached) return json(cached);
  if (!(await accountWithinLimit(env.DB, "coauthors", a.id, COAUTHORS_LIMIT.limit, COAUTHORS_LIMIT.windowMs, ctx.now))) {
    return json({ ok: false, error: "rate_limited" }, 429);
  }
  let works: RawWork[];
  try {
    works = await fetchWorks(ctx.fetch, authorId);
  } catch {
    return json({ ok: false, error: "upstream_unavailable" }, 502);
  }
  const body = summariseCoauthors(works, authorId);
  await writeCache(authorId, body);
  return json(body);
}
