import { SELF, env } from "cloudflare:test";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { seedAmbassador } from "./helpers";

// Community-group quality assurance (AMB-1 Add-on A4, CG-7b): sampled blind second tags, holds, reviewer picks, the
// review queue and POST, the export of pairs and reviews, and retry idempotence. Local D1 in workerd; roster served
// by the fake fetch; no network.

// Tests that tag 25 to 41 groups one at a time need more than the default 5 seconds.
vi.setConfig({ testTimeout: 30_000 });

const API = "https://api.plastiverse.live";
const ROSTER_URL = "https://plastiverse.live/data/global/groups/roster.json";
const HOLD_MS = 2 * 60 * 60 * 1000;
const EXPORT_TOKEN = "test-export-token-group-qa-0123456789";
const TIER1 = ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"];

/** Roster ids: cg_ + 16 hex digits from the number. Groups 1-80 are US (California); 201-203 are NO. */
function gid(n: number): string {
  return `cg_${n.toString(16).padStart(16, "0")}`;
}

function rosterRecord(n: number, country: string): Record<string, unknown> {
  return {
    group_id: gid(n),
    name: `Group ${n}`,
    name_alt: [],
    country,
    region: country === "NO" ? "Northern Europe" : "Northern America",
    ambassador_region: null,
    url: `https://group${n}.example.org/`,
    bffp_listed: true,
    bffp_listed_asof: "2026-11-01",
    org_status: "source_declared_org",
    roster_retrieved_at: "2026-11-01",
  };
}

/**
 * Extended fixture: 80 US groups (the cap test needs 41 primaries plus more than 20 untagged candidates). Norwegian
 * groups sit among them so the country filter is exercised.
 */
function roster(): { schema: string; records: Record<string, unknown>[] } {
  const records: Record<string, unknown>[] = [];
  for (let n = 1; n <= 80; n++) {
    records.push(rosterRecord(n, "US"));
    if (n === 10) records.push(rosterRecord(201, "NO"));
    if (n === 30) records.push(rosterRecord(202, "NO"), rosterRecord(203, "NO"));
  }
  return { schema: "cg-roster-v1", records };
}

let rosterStatus = 200;

beforeEach(async () => {
  // The helpers' beforeEach clears the ambassador and QA tables (leases cascade); clear the rest here.
  await env.DB.prepare("DELETE FROM group_leases").run();
  await caches.default.delete(new Request(ROSTER_URL));
  rosterStatus = 200;
  // Wrap the helpers' fake fetch: the roster is answered here, everything else keeps the helpers' rules.
  const previous = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url === ROSTER_URL) {
      if (rosterStatus !== 200) return new Response("unavailable", { status: rosterStatus });
      return new Response(JSON.stringify(roster()), { headers: { "Content-Type": "application/json" } });
    }
    return previous(input, init);
  }) as typeof fetch;
});

function req(method: string, path: string, body?: unknown, cookie?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (cookie) headers.Cookie = cookie;
  return SELF.fetch(`${API}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}

function batch(cookie: string | undefined, region = "california"): Promise<Response> {
  return req("GET", `/groups/batch?region=${region}`, undefined, cookie);
}

function submitKind(cookie: string, kind: string, payload: unknown, region = "california", stream = "knowledge"): Promise<Response> {
  return req("POST", "/submissions", { region, stream, kind, payload }, cookie);
}

interface BatchBody {
  ok: boolean;
  region?: string;
  leases: { group_id: string; name: string; country: string; url: string | null; [key: string]: unknown }[];
  remaining_in_region?: number;
  error?: string;
}

async function batchBody(cookie: string, region = "california"): Promise<BatchBody> {
  return (await (await batch(cookie, region)).json()) as BatchBody;
}

function leaseIds(body: BatchBody): string[] {
  return body.leases.map((l) => l.group_id);
}

/** A valid tier-1 tag for group id n. */
function tag(extra: Record<string, unknown> = {}, n = 1): Record<string, unknown> {
  return {
    group_id: gid(n),
    status: "ambassador_tagged",
    entity_type: "organisation",
    sector: "ngo_civil_society",
    plastics_centrality: "primary",
    primary_activities: ["advocacy_campaigning"],
    geographic_scope: "local",
    evidence: [
      {
        facet: "plastics_centrality",
        url: "https://example.org/about",
        accessed_at: "2026-11-20",
        quote: "We campaign against single-use plastic.",
      },
      {
        facet: "primary_activities",
        url: "https://example.org/programmes",
        accessed_at: "2026-11-20",
        not_stated: true,
      },
    ],
    ...extra,
  };
}

type Who = { id: string; cookie: string };
type Body = Record<string, unknown>;

async function bodyOf(res: Response): Promise<Body> {
  return (await res.json()) as Body;
}

async function count(table: string, where = "1 = 1"): Promise<number> {
  const row = await env.DB.prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE ${where}`).first<{ n: number }>();
  return row?.n ?? 0;
}

/** Rate-limit rows are cleared between setup calls: one ambassador tags 40 groups and the limit is 30 an hour. */
async function clearLimits(): Promise<void> {
  await env.DB.prepare("DELETE FROM rate_limits").run();
}

/** Puts the group under a lease of the ambassador (direct SQL, no batch), replacing any older hold. */
async function leaseTo(ambassadorId: string, groups: number[], region = "california"): Promise<void> {
  const now = Date.now();
  await env.DB.batch(
    groups.map((n) =>
      env.DB.prepare(
        "INSERT OR REPLACE INTO group_leases (group_id, ambassador_id, region, leased_at, expires_at, renewals) " +
          "VALUES (?1, ?2, ?3, ?4, ?5, 0)",
      ).bind(gid(n), ambassadorId, region, now, now + HOLD_MS),
    ),
  );
}

/** Submits a group_tag payload for group n under a direct lease. */
async function submitTag(a: Who, n: number, payload: Record<string, unknown>): Promise<Response> {
  await leaseTo(a.id, [n]);
  await clearLimits();
  return submitKind(a.cookie, "group_tag", payload);
}

/** A valid Tier-1 tag for group n. */
function tagAs(a: Who, n: number, extra: Record<string, unknown> = {}): Promise<Response> {
  return submitTag(a, n, tag(extra, n));
}

/** Records a deterministic pick (the random draw is made on first use, so a preset row wins). */
async function presetPick(kind: "sample" | "review", scope: string, block: number, pick: number): Promise<void> {
  await env.DB.prepare("INSERT INTO group_qa_blocks (kind, scope, block_no, pick) VALUES (?1, ?2, ?3, ?4)")
    .bind(kind, scope, block, pick)
    .run();
}

/** Id of the first (primary) group_tag submission of group n. */
async function primaryOf(n: number): Promise<number> {
  const row = await env.DB.prepare(
    "SELECT MIN(id) AS id FROM submissions WHERE kind = 'group_tag' AND json_extract(payload, '$.group_id') = ?1",
  )
    .bind(gid(n))
    .first<{ id: number }>();
  return row?.id ?? 0;
}

async function decide(cookie: string, id: number, decision: "approve" | "reject" = "approve"): Promise<Response> {
  await clearLimits();
  return req("POST", "/moderation/decide", { type: "submission", id, decision }, cookie);
}

interface SampleRow {
  primary_id: number;
  group_id: string;
  assigned_to: string | null;
  hold_until: number | null;
}

async function samples(): Promise<SampleRow[]> {
  return (
    await env.DB.prepare("SELECT primary_id, group_id, assigned_to, hold_until FROM group_tag_samples ORDER BY primary_id")
      .all<SampleRow>()
  ).results;
}

async function sampleOf(n: number): Promise<SampleRow | null> {
  return (
    (await env.DB.prepare("SELECT primary_id, group_id, assigned_to, hold_until FROM group_tag_samples WHERE group_id = ?1")
      .bind(gid(n))
      .first<SampleRow>()) ?? null
  );
}

async function pairCount(): Promise<number> {
  return count("group_tag_pairs");
}

/** Usable primary tags of california, oldest first (the same test the selection SQL applies). */
async function usableCaliforniaPrimaries(): Promise<number[]> {
  const rows = await env.DB.prepare(
    "SELECT id FROM submissions WHERE kind = 'group_tag' AND region = 'california' " +
      "AND json_extract(payload, '$.second_tag_for') IS NULL AND json_extract(payload, '$.status') = 'ambassador_tagged' " +
      "AND COALESCE(json_extract(payload, '$.not_an_organisation'), 0) = 0 ORDER BY id",
  ).all<{ id: number }>();
  return rows.results.map((r) => r.id);
}

// ---------------------------------------------------------------------------------------------------------------
// Sampling

describe("sampling of usable primary tags", () => {
  it("selects one sample per block of 10 usable california primaries, from the stored block picks", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    for (let n = 1; n <= 20; n++) expect((await tagAs(a, n)).status).toBe(201);

    const rows = await samples();
    expect(rows).toHaveLength(2);
    const order = await usableCaliforniaPrimaries();
    const blocks = (
      await env.DB.prepare("SELECT block_no, pick FROM group_qa_blocks WHERE kind = 'sample' AND scope = 'california' ORDER BY block_no")
        .all<{ block_no: number; pick: number }>()
    ).results;
    expect(blocks.map((b) => b.block_no)).toEqual([0, 1]);
    expect(new Set(rows.map((r) => Math.floor(order.indexOf(r.primary_id) / 10)))).toEqual(new Set([0, 1]));
    for (const row of rows) {
      const ordinal = order.indexOf(row.primary_id);
      expect(blocks[Math.floor(ordinal / 10)].pick).toBe(ordinal % 10);
    }
  });

  it("a preset pick samples only the chosen position of its block", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    await presetPick("sample", "california", 0, 2);
    for (let n = 1; n <= 10; n++) expect((await tagAs(a, n)).status).toBe(201);

    const rows = await samples();
    expect(rows.map((r) => r.group_id)).toEqual([gid(3)]);
    expect((await env.DB.prepare("SELECT COUNT(*) AS n FROM group_qa_blocks WHERE kind = 'sample'").first<{ n: number }>())?.n).toBe(1);
  });

  it("cannot_determine and not_an_organisation primaries are not counted, sampled or picked", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    await presetPick("sample", "california", 0, 0);
    for (let n = 1; n <= 5; n++) {
      const payload = { group_id: gid(n), status: "cannot_determine", cannot_determine_reason: "dead_link" };
      expect((await submitTag(a, n, payload)).status).toBe(201);
    }
    const notOrg = { group_id: gid(6), status: "cannot_determine", cannot_determine_reason: "not_an_organisation", not_an_organisation: true };
    expect((await submitTag(a, 6, notOrg)).status).toBe(201);
    for (let n = 7; n <= 26; n++) expect((await tagAs(a, n)).status).toBe(201);

    // The first usable primary is group 7 (ordinal 1), so pick 0 samples it. Counting the excluded tags would move it.
    const rows = await samples();
    expect(rows.map((r) => r.group_id)).toContain(gid(7));
    expect(rows.map((r) => r.group_id).filter((g) => [1, 2, 3, 4, 5, 6].some((n) => g === gid(n)))).toEqual([]);
    expect(rows).toHaveLength(2);

    const picked = (
      await env.DB.prepare(
        "SELECT json_extract(s.payload, '$.group_id') AS group_id FROM group_review_picks r JOIN submissions s ON s.id = r.submission_id",
      ).all<{ group_id: string }>()
    ).results.map((r) => r.group_id);
    expect(picked.filter((g) => [1, 2, 3, 4, 5, 6].some((n) => g === gid(n)))).toEqual([]);
  });
});

// ---------------------------------------------------------------------------------------------------------------
// Holds, pairs and the batch

describe("sample holds, pairs and the batch", () => {
  it("holds a sample for another ambassador of the region; never for its tagger or for a norway member", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    const norway = await seedAmbassador({ region: "norway", email: "n@example.org" });
    await presetPick("sample", "california", 0, 0);
    expect((await tagAs(a, 1)).status).toBe(201);

    const bBody = await batchBody(b.cookie);
    expect(leaseIds(bBody)).toContain(gid(1));
    expect((await sampleOf(1))?.assigned_to).toBe(b.id);

    expect(leaseIds(await batchBody(a.cookie))).not.toContain(gid(1));
    expect(leaseIds(await batchBody(norway.cookie, "norway"))).not.toContain(gid(1));
  });

  it("a lapsed sample hold is reclaimed by another member, and the former holder's tag then counts as an overlap", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    const c = await seedAmbassador({ region: "california", email: "c@example.org" });
    await presetPick("sample", "california", 0, 0);
    expect((await tagAs(a, 1)).status).toBe(201);
    expect(leaseIds(await batchBody(b.cookie))).toContain(gid(1));
    await env.DB.prepare("UPDATE group_tag_samples SET hold_until = 1 WHERE group_id = ?1").bind(gid(1)).run();
    await env.DB.prepare("DELETE FROM group_leases WHERE ambassador_id = ?1").bind(b.id).run();

    expect(leaseIds(await batchBody(c.cookie))).toContain(gid(1));
    expect((await sampleOf(1))?.assigned_to).toBe(c.id);
    expect(leaseIds(await batchBody(b.cookie))).not.toContain(gid(1));

    expect((await tagAs(b, 1)).status).toBe(201);
    const pair = await env.DB.prepare("SELECT basis FROM group_tag_pairs").first<{ basis: string }>();
    expect(pair?.basis).toBe("overlap");
    expect((await sampleOf(1))?.assigned_to ?? null).toBeNull();
  });

  it("a rejected primary's sample is not assigned to another ambassador", async () => {
    const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, email: "owner@example.org" });
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    await presetPick("sample", "california", 0, 0);
    const created = await bodyOf(await tagAs(a, 1));
    expect((await decide(owner.cookie, created.id as number, "reject")).status).toBe(200);

    expect(leaseIds(await batchBody(b.cookie))).not.toContain(gid(1));
    expect((await sampleOf(1))?.assigned_to ?? null).toBeNull();
  });

  it("two concurrent claims never share a sample", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    const c = await seedAmbassador({ region: "california", email: "c@example.org" });
    for (const block of [0, 1, 2, 3]) await presetPick("sample", "california", block, 0);
    for (let n = 1; n <= 40; n++) expect((await tagAs(a, n)).status).toBe(201);
    expect((await samples()).map((r) => r.group_id).sort()).toEqual([gid(1), gid(11), gid(21), gid(31)].sort());

    const [bb, cc] = await Promise.all([batchBody(b.cookie), batchBody(c.cookie)]);
    const sampled = [gid(1), gid(11), gid(21), gid(31)];
    const bHeld = leaseIds(bb).filter((g) => sampled.includes(g));
    const cHeld = leaseIds(cc).filter((g) => sampled.includes(g));
    expect(bHeld.filter((g) => cHeld.includes(g))).toEqual([]);
    expect([...bHeld, ...cHeld].sort()).toEqual([...sampled].sort());
    for (const row of await samples()) {
      const expected = bHeld.includes(row.group_id) ? b.id : c.id;
      expect(row.assigned_to).toBe(expected);
    }
  });

  it("a usable blind second tag by the holder records a sample pair, ends the hold and is not offered again", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    const c = await seedAmbassador({ region: "california", email: "c@example.org" });
    await presetPick("sample", "california", 0, 0);
    const primary = await bodyOf(await tagAs(a, 1));
    expect(leaseIds(await batchBody(b.cookie))).toContain(gid(1));

    const second = await bodyOf(await tagAs(b, 1));
    expect(second.second_tag).toBe(true);
    expect(second.status).toBe("pending");
    const pair = await env.DB.prepare("SELECT primary_id, second_id, basis FROM group_tag_pairs").first<{
      primary_id: number;
      second_id: number;
      basis: string;
    }>();
    expect(pair).toEqual({ primary_id: primary.id, second_id: second.id, basis: "sample" });
    const row = await sampleOf(1);
    expect(row?.assigned_to ?? null).toBeNull();
    expect(row?.hold_until ?? null).toBeNull();

    expect(leaseIds(await batchBody(b.cookie))).not.toContain(gid(1));
    expect(leaseIds(await batchBody(c.cookie))).not.toContain(gid(1));
  });

  it("two ambassadors tagging the same group record an overlap pair; a third adds no second pair", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    const c = await seedAmbassador({ region: "california", email: "c@example.org" });
    // Pick 9 of block 0 keeps group 1 (the first usable primary) unsampled.
    await presetPick("sample", "california", 0, 9);
    const [ra, rb] = await Promise.all([
      submitKind(a.cookie, "group_tag", tag({}, 1)),
      submitKind(b.cookie, "group_tag", tag({ name_correction: "Second Researcher Name" }, 1)),
    ]);
    expect([ra.status, rb.status]).toEqual([201, 201]);
    const secondId = [await bodyOf(ra), await bodyOf(rb)].find((x) => x.second_tag === true)?.id as number;
    const primaryId = await primaryOf(1);
    expect(await pairCount()).toBe(1);
    const pair = await env.DB.prepare("SELECT primary_id, second_id, basis FROM group_tag_pairs").first<{
      primary_id: number;
      second_id: number;
      basis: string;
    }>();
    expect(pair).toEqual({ primary_id: primaryId, second_id: secondId, basis: "overlap" });

    const later = await bodyOf(await tagAs(c, 1));
    expect(later.second_tag).toBe(true);
    expect(await pairCount()).toBe(1);
  });

  it("a cannot_determine second tag records no pair and re-opens the sample for a third ambassador", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    const c = await seedAmbassador({ region: "california", email: "c@example.org" });
    await presetPick("sample", "california", 0, 0);
    await tagAs(a, 1);
    expect(leaseIds(await batchBody(b.cookie))).toContain(gid(1));

    const cannot = { group_id: gid(1), status: "cannot_determine", cannot_determine_reason: "dead_link" };
    const res = await bodyOf(await submitTag(b, 1, cannot));
    expect(res.second_tag).toBe(true);
    expect(await pairCount()).toBe(0);
    expect((await sampleOf(1))?.assigned_to ?? null).toBeNull();

    expect(leaseIds(await batchBody(c.cookie))).toContain(gid(1));
    expect((await sampleOf(1))?.assigned_to).toBe(c.id);
  });

  it("the 25-group cap counts sample holds: five sample holds leave 20 ordinary leases", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    for (const block of [0, 1, 2, 3, 4]) await presetPick("sample", "california", block, 0);
    for (let n = 1; n <= 41; n++) expect((await tagAs(a, n)).status).toBe(201);
    expect(await samples()).toHaveLength(5);

    const body = await batchBody(b.cookie);
    const held = leaseIds(body);
    expect(held).toHaveLength(25);
    const sampled = [1, 11, 21, 31, 41].map(gid);
    expect(held.filter((g) => sampled.includes(g))).toHaveLength(5);
    expect(body.remaining_in_region).toBeGreaterThan(0);
  });

  it("a repeated group_id GET extends only the holder's sample hold", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    const c = await seedAmbassador({ region: "california", email: "c@example.org" });
    await presetPick("sample", "california", 0, 0);
    await tagAs(a, 1);
    await batchBody(b.cookie);
    // Shorten the hold so a refresh is visible.
    await env.DB.prepare("UPDATE group_tag_samples SET hold_until = ?1 WHERE group_id = ?2")
      .bind(Date.now() + 60_000, gid(1))
      .run();
    const shortened = (await sampleOf(1))?.hold_until ?? 0;

    // A refresh by another ambassador is answered but leaves the holder's hold alone.
    expect((await req("GET", `/groups/batch?region=california&group_id=${gid(1)}`, undefined, c.cookie)).status).toBe(200);
    expect((await sampleOf(1))?.hold_until).toBe(shortened);

    const refreshed = await req("GET", `/groups/batch?region=california&group_id=${gid(1)}`, undefined, b.cookie);
    expect(refreshed.status).toBe(200);
    expect((await sampleOf(1))?.hold_until ?? 0).toBeGreaterThan(Date.now() + HOLD_MS - 60_000);
    expect((await sampleOf(1))?.assigned_to).toBe(b.id);
  });
});

// ---------------------------------------------------------------------------------------------------------------
// Reviewer picks

describe("reviewer picks", () => {
  it("the first 25 usable primaries of an ambassador are picked as first_25", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    for (let n = 1; n <= 25; n++) expect((await tagAs(a, n)).status).toBe(201);
    const picks = (
      await env.DB.prepare("SELECT basis FROM group_review_picks r JOIN submissions s ON s.id = r.submission_id WHERE s.ambassador_id = ?1")
        .bind(a.id)
        .all<{ basis: string }>()
    ).results;
    expect(picks).toHaveLength(25);
    expect(picks.every((p) => p.basis === "first_25")).toBe(true);
  });

  it("primary 27 is random_20 from the preset block; 26 and 28-30 are not picked; 40 primaries give 25 + 3 picks", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    // Block 0 covers primaries 26-30 (pick 1 is #27); block 1 covers 31-35 (pick 0 is #31); block 2 covers 36-40 (pick 0 is #36).
    await presetPick("review", a.id, 0, 1);
    await presetPick("review", a.id, 1, 0);
    await presetPick("review", a.id, 2, 0);
    for (let n = 1; n <= 40; n++) expect((await tagAs(a, n)).status).toBe(201);

    const ids = (await env.DB.prepare("SELECT id FROM submissions WHERE ambassador_id = ?1 AND kind = 'group_tag' ORDER BY id")
      .bind(a.id)
      .all<{ id: number }>()).results.map((r) => r.id);
    const picks = (
      await env.DB.prepare("SELECT submission_id, basis FROM group_review_picks WHERE submission_id IN (SELECT id FROM submissions WHERE ambassador_id = ?1)")
        .bind(a.id)
        .all<{ submission_id: number; basis: string }>()
    ).results;
    expect(picks).toHaveLength(28);
    const byPosition = new Map(picks.map((p) => [ids.indexOf(p.submission_id), p.basis]));
    expect(byPosition.get(26)).toBe("random_20");
    for (const position of [25, 27, 28, 29]) expect(byPosition.has(position)).toBe(false);
    expect(byPosition.get(30)).toBe("random_20");
    expect(byPosition.get(35)).toBe("random_20");
    expect([...byPosition.entries()].filter(([, basis]) => basis === "first_25")).toHaveLength(25);
    expect([...byPosition.entries()].filter(([, basis]) => basis === "random_20")).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------------------------------------------
// Review queue and POST

/** Owner, one california ambassador with 26 tags (group 1 and 26 approved, #26 never picked, #2 pending). */
async function reviewFixture(): Promise<{ owner: Who; a: Who }> {
  const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, email: "owner@example.org" });
  const a = await seedAmbassador({ region: "california", email: "a@example.org" });
  await presetPick("review", a.id, 0, 1);
  for (let n = 1; n <= 26; n++) expect((await tagAs(a, n)).status).toBe(201);
  expect((await decide(owner.cookie, await primaryOf(1))).status).toBe(200);
  expect((await decide(owner.cookie, await primaryOf(26))).status).toBe(200);
  return { owner, a };
}

function allAgree(): Record<string, unknown> {
  return Object.fromEntries(TIER1.map((facet) => [facet, { outcome: "agree" }]));
}

function postReview(cookie: string, submissionId: number, facets: unknown): Promise<Response> {
  return req("POST", "/groups/reviews", { submission_id: submissionId, facets }, cookie);
}

interface ReviewRowDb {
  facet: string;
  outcome: string;
  original_value: string;
  reviewed_value: string;
  reason_code: string | null;
  reviewer_id: string | null;
}

async function reviewRows(submissionId: number): Promise<ReviewRowDb[]> {
  return (
    await env.DB.prepare(
      "SELECT facet, outcome, original_value, reviewed_value, reason_code, reviewer_id FROM group_tag_reviews " +
        "WHERE submission_id = ?1 ORDER BY facet",
    )
      .bind(submissionId)
      .all<ReviewRowDb>()
  ).results;
}

describe("review queue", () => {
  it("lists approved, picked, unreviewed tags for owner and leads, never the reviewer's own; 403 and 401 otherwise", async () => {
    const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, email: "owner@example.org" });
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const lead = await seedAmbassador({ region: "california", role: "lead", email: "lead@example.org" });
    for (let n = 1; n <= 25; n++) expect((await tagAs(a, n)).status).toBe(201);
    const leadTag = await bodyOf(await tagAs(lead, 26));
    for (let n = 1; n <= 5; n++) expect((await decide(owner.cookie, await primaryOf(n))).status).toBe(200);
    expect((await decide(owner.cookie, leadTag.id as number)).status).toBe(200);

    const ids = async (cookie: string): Promise<number[]> => {
      const res = await req("GET", "/groups/reviews", undefined, cookie);
      expect(res.status).toBe(200);
      return ((await bodyOf(res)).reviews as { submission_id: number }[]).map((r) => r.submission_id).sort((x, y) => x - y);
    };
    const approved = [await primaryOf(1), await primaryOf(2), await primaryOf(3), await primaryOf(4), await primaryOf(5)];
    expect(await ids(owner.cookie)).toEqual([...approved, leadTag.id as number].sort((x, y) => x - y));
    expect(await ids(lead.cookie)).toEqual(approved.sort((x, y) => x - y));

    const queue = await req("GET", "/groups/reviews", undefined, lead.cookie);
    const text = await queue.text();
    expect(text).not.toContain(a.id);
    expect(text).not.toContain(lead.id);

    expect((await req("GET", "/groups/reviews", undefined, a.cookie)).status).toBe(403);
    expect((await req("GET", "/groups/reviews")).status).toBe(401);

    // A completed review takes the tag out of the queue.
    expect((await postReview(owner.cookie, approved[0], allAgree())).status).toBe(201);
    expect(await ids(owner.cookie)).not.toContain(approved[0]);
  });
});

describe("POST /groups/reviews", () => {
  it("an all-agree review stores five agree rows with the original values and no reason", async () => {
    const { owner } = await reviewFixture();
    const id = await primaryOf(1);
    expect((await postReview(owner.cookie, id, allAgree())).status).toBe(201);
    const rows = await reviewRows(id);
    expect(rows.map((r) => r.facet)).toEqual([...TIER1].sort());
    for (const row of rows) {
      expect(row.outcome).toBe("agree");
      expect(row.reviewed_value).toBe(row.original_value);
      expect(row.reason_code).toBeNull();
      expect(row.reviewer_id).toBe(owner.id);
    }
    expect(rows.find((r) => r.facet === "primary_activities")?.original_value).toBe("advocacy_campaigning");
  });

  it("an edit stores the original and reviewed values and the reason; activities are joined by ';'", async () => {
    const { owner } = await reviewFixture();
    const id = await primaryOf(1);
    const facets = {
      ...allAgree(),
      primary_activities: { outcome: "edit", value: ["advocacy_campaigning", "policy_governance"], reason_code: "activity_order" },
    };
    expect((await postReview(owner.cookie, id, facets)).status).toBe(201);
    const edit = (await reviewRows(id)).find((r) => r.facet === "primary_activities");
    expect(edit).toMatchObject({
      outcome: "edit",
      original_value: "advocacy_campaigning",
      reviewed_value: "advocacy_campaigning;policy_governance",
      reason_code: "activity_order",
    });
  });

  const withFacet = (facet: string, value: unknown): Record<string, unknown> => ({ ...allAgree(), [facet]: value });
  const invalidCases: [string, Record<string, unknown>, string][] = [
    ["a missing facet", Object.fromEntries(Object.entries(allAgree()).filter(([k]) => k !== "geographic_scope")), "geographic_scope"],
    ["an unknown facet", withFacet("legal_form", { outcome: "agree" }), "legal_form"],
    ["an edit to the same value", withFacet("entity_type", { outcome: "edit", value: "organisation", reason_code: "slip" }), "entity_type"],
    ["an unknown reason code", withFacet("sector", { outcome: "edit", value: "foundation", reason_code: "bogus" }), "sector.reason_code"],
    ["an agree carrying a value", withFacet("geographic_scope", { outcome: "agree", value: "local" }), "geographic_scope"],
    [
      "a plastics_centrality edit to cannot_determine",
      withFacet("plastics_centrality", { outcome: "edit", value: "cannot_determine", reason_code: "other" }),
      "plastics_centrality",
    ],
  ];

  it.each(invalidCases)("refuses %s with 400 invalid_review naming the field", async (_name, facets, field) => {
    const { owner } = await reviewFixture();
    const id = await primaryOf(1);
    const res = await postReview(owner.cookie, id, facets);
    expect(res.status).toBe(400);
    const body = await bodyOf(res);
    expect(body.error).toBe("invalid_review");
    expect(body.field).toBe(field);
    expect(await reviewRows(id)).toEqual([]);
  });

  it("refuses an unpicked tag with 409 not_selected and a pending one with 409 not_approved", async () => {
    const { owner } = await reviewFixture();
    const unpicked = await postReview(owner.cookie, await primaryOf(26), allAgree());
    expect(unpicked.status).toBe(409);
    expect((await bodyOf(unpicked)).error).toBe("not_selected");

    const pending = await postReview(owner.cookie, await primaryOf(2), allAgree());
    expect(pending.status).toBe(409);
    expect((await bodyOf(pending)).error).toBe("not_approved");
  });

  it("refuses a reviewer's own tag with 403 self_review", async () => {
    const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, email: "owner@example.org" });
    const lead = await seedAmbassador({ region: "california", role: "lead", email: "lead@example.org" });
    const own = await bodyOf(await tagAs(lead, 40));
    expect((await decide(owner.cookie, own.id as number)).status).toBe(200);
    const res = await postReview(lead.cookie, own.id as number, allAgree());
    expect(res.status).toBe(403);
    expect((await bodyOf(res)).error).toBe("self_review");
  });

  it("two reviewers posting at once: exactly one 201, the other 409 already_reviewed, five rows from one reviewer", async () => {
    const { owner } = await reviewFixture();
    const lead = await seedAmbassador({ role: "lead", email: "lead@example.org" });
    const id = await primaryOf(1);
    const [x, y] = await Promise.all([postReview(owner.cookie, id, allAgree()), postReview(lead.cookie, id, allAgree())]);
    expect([x.status, y.status].sort()).toEqual([201, 409]);
    const loser = x.status === 409 ? x : y;
    expect((await bodyOf(loser)).error).toBe("already_reviewed");
    const rows = await reviewRows(id);
    expect(rows).toHaveLength(5);
    expect(new Set(rows.map((r) => r.reviewer_id)).size).toBe(1);
  });
});

// ---------------------------------------------------------------------------------------------------------------
// Export

describe("export of pairs and reviews", () => {
  beforeEach(() => {
    (env as unknown as Record<string, string>).EXPORT_TOKEN = EXPORT_TOKEN;
  });
  afterEach(() => {
    (env as unknown as Record<string, string>).EXPORT_TOKEN = "";
  });

  it("group_pairs holds only approved primaries with the five Tier-1 values; group_reviews has the eight keys and no ids", async () => {
    const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, email: "owner@example.org" });
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    await presetPick("sample", "california", 0, 9);
    await tagAs(a, 1);
    await tagAs(b, 1);
    await tagAs(a, 2);
    await tagAs(b, 2);
    expect((await decide(owner.cookie, await primaryOf(1))).status).toBe(200);
    expect((await postReview(owner.cookie, await primaryOf(1), {
      ...allAgree(),
      entity_type: { outcome: "edit", value: "network_coalition", reason_code: "evidence_contradicts" },
    })).status).toBe(201);

    const res = await SELF.fetch(`${API}/export/approved?since=0`, { headers: { Authorization: `Bearer ${EXPORT_TOKEN}` } });
    expect(res.status).toBe(200);
    const text = await res.text();
    const body = JSON.parse(text) as Record<string, unknown>;

    const pairs = body.group_pairs as { group_id: string; value_a: Body; value_b: Body }[];
    expect(pairs).toHaveLength(1);
    expect(pairs[0].group_id).toBe(gid(1));
    expect(Object.keys(pairs[0].value_a).sort()).toEqual([...TIER1].sort());
    expect(Object.keys(pairs[0].value_b).sort()).toEqual([...TIER1].sort());

    const reviews = body.group_reviews as Body[];
    expect(reviews).toHaveLength(5);
    for (const row of reviews) {
      expect(Object.keys(row).sort()).toEqual(
        ["group_id", "region", "facet", "outcome", "reason_code", "original_value", "reviewed_value", "reviewed_at"].sort(),
      );
    }
    expect(reviews.find((r) => r.facet === "entity_type")).toMatchObject({
      outcome: "edit",
      original_value: "organisation",
      reviewed_value: "network_coalition",
      reason_code: "evidence_contradicts",
    });

    for (const who of [a, b, owner]) expect(text).not.toContain(who.id);
    expect(text).not.toContain('"basis"');
    expect(text).not.toContain('"assigned_to"');
    expect(text).not.toContain('"reviewer');
  });
});

// ---------------------------------------------------------------------------------------------------------------
// Retry idempotence

describe("retries", () => {
  it("resubmitting the same primary or second tag creates no duplicate sample, pick, pair or block row", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    await presetPick("sample", "california", 0, 0);
    const first = await bodyOf(await tagAs(a, 1));

    const snapshot = async (): Promise<number[]> => [
      await count("group_qa_blocks"),
      await count("group_tag_samples"),
      await count("group_review_picks"),
      await count("group_tag_pairs"),
    ];
    const before = await snapshot();
    const retry = await bodyOf(await submitKind(a.cookie, "group_tag", tag({}, 1)));
    expect(retry.id).toBe(first.id);
    expect(await snapshot()).toEqual(before);

    const second = await bodyOf(await tagAs(b, 1));
    const afterSecond = await snapshot();
    expect(afterSecond[3]).toBe(1);
    const secondRetry = await bodyOf(await submitKind(b.cookie, "group_tag", tag({}, 1)));
    expect(secondRetry.id).toBe(second.id);
    expect(await snapshot()).toEqual(afterSecond);
  });
});
