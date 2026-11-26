import { SELF, env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { validateGroupSuggest, validateGroupTag } from "../src/groups";
import { seedAmbassador } from "./helpers";

// Community-group leases, batch claims, renewal and release, and the group_tag and group_suggest payloads
// (AMB-1 Add-on A4, CG-6a). Local D1 in workerd; the roster is a fixture served through the fake fetch; no network.

const API = "https://api.plastiverse.live";
const ROSTER_URL = "https://plastiverse.live/data/global/groups/roster.json";
const DAY_MS = 24 * 60 * 60 * 1000;
const LEASE_MS = 30 * DAY_MS;
const GID = "cg_0123456789abcdef";

/** Roster ids: cg_ + 16 hex digits from the number. Groups 1-30 are US (California); 201-203 are NO. */
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

/** Mixed order on purpose: a Norwegian group sits between California groups, so the country filter is tested. */
function roster(): { schema: string; records: Record<string, unknown>[] } {
  const records: Record<string, unknown>[] = [];
  for (let n = 1; n <= 10; n++) records.push(rosterRecord(n, "US"));
  records.push(rosterRecord(201, "NO"));
  for (let n = 11; n <= 30; n++) records.push(rosterRecord(n, "US"));
  records.push(rosterRecord(202, "NO"), rosterRecord(203, "NO"));
  return { schema: "cg-roster-v1", records };
}

let rosterStatus = 200;

beforeEach(async () => {
  // The helpers' beforeEach clears the ambassador tables (leases cascade); clear the rest here.
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

function renew(cookie: string, groupId: string): Promise<Response> {
  return req("POST", "/groups/renew", { group_id: groupId }, cookie);
}

function release(cookie: string, groupId: string): Promise<Response> {
  return req("POST", "/groups/release", { group_id: groupId }, cookie);
}

function submitKind(cookie: string, kind: string, payload: unknown, region = "california", stream = "knowledge"): Promise<Response> {
  return req("POST", "/submissions", { region, stream, kind, payload }, cookie);
}

interface BatchBody {
  ok: boolean;
  region?: string;
  leases: { group_id: string; name: string; country: string; url: string | null; expires_at: number; renewals: number }[];
  remaining_in_region?: number;
  error?: string;
}

async function batchBody(cookie: string, region = "california"): Promise<BatchBody> {
  return (await (await batch(cookie, region)).json()) as BatchBody;
}

function leaseIds(body: BatchBody): string[] {
  return body.leases.map((l) => l.group_id);
}

function range(from: number, to: number): string[] {
  const out: string[] = [];
  for (let n = from; n <= to; n++) out.push(gid(n));
  return out;
}

async function leaseRow(groupId: string): Promise<{ ambassador_id: string; expires_at: number; renewals: number } | null> {
  return env.DB.prepare("SELECT ambassador_id, expires_at, renewals FROM group_leases WHERE group_id = ?1")
    .bind(groupId)
    .first<{ ambassador_id: string; expires_at: number; renewals: number }>();
}

/** The two evidence entries of the base tag: plastics_centrality (quoted) and primary_activities (not stated). */
function tagEvidence(): Record<string, unknown>[] {
  return tag().evidence as Record<string, unknown>[];
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

function failField(payload: unknown, validator: (p: unknown) => { ok: boolean; field?: string }): string | undefined {
  const res = validator(payload);
  return res.ok ? undefined : res.field;
}

const tagField = (p: unknown): string | undefined => failField(p, validateGroupTag);
const suggestField = (p: unknown): string | undefined => failField(p, validateGroupSuggest);

describe("batch claims", () => {
  it("claims 25 California groups in roster order and reports the remainder", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const body = await batchBody(a.cookie);
    expect(body.ok).toBe(true);
    expect(leaseIds(body)).toEqual(range(1, 25));
    expect(body.remaining_in_region).toBe(5);
    expect(body.leases[0]).toEqual(
      expect.objectContaining({ group_id: gid(1), name: "Group 1", country: "US", url: "https://group1.example.org/", renewals: 0 }),
    );
    const expires = body.leases[0].expires_at;
    expect(Math.abs(expires - (Date.now() + LEASE_MS))).toBeLessThan(60_000);
  });

  it("a repeat call returns the same leases and claims nothing more", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const first = await batchBody(a.cookie);
    const second = await batchBody(a.cookie);
    expect(leaseIds(second)).toEqual(leaseIds(first));
    expect(second.remaining_in_region).toBe(5);
  });

  it("a second ambassador gets only the unleased remainder (no double leasing)", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    await batchBody(a.cookie);
    const bBody = await batchBody(b.cookie);
    expect(leaseIds(bBody)).toEqual(range(26, 30));
    expect(bBody.remaining_in_region).toBe(0);
    const count = await env.DB.prepare("SELECT COUNT(DISTINCT group_id) AS n FROM group_leases").first<{ n: number }>();
    expect(count?.n).toBe(30);
  });

  it("expired leases are reusable by another ambassador", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    await batchBody(a.cookie);
    await env.DB.prepare("UPDATE group_leases SET expires_at = 1 WHERE ambassador_id = ?1").bind(a.id).run();
    const bBody = await batchBody(b.cookie);
    expect(leaseIds(bBody)).toEqual(range(1, 25));
    expect((await leaseRow(gid(1)))?.ambassador_id).toBe(b.id);
    expect(bBody.remaining_in_region).toBe(5);
  });

  it("tagged groups (pending or approved) are not claimed", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const tagger = await seedAmbassador({ region: "california", email: "t@example.org" });
    await env.DB.prepare(
      "INSERT INTO submissions (ambassador_id, region, stream, kind, payload, status, created_at) VALUES (?1, 'california', 'knowledge', 'group_tag', ?2, 'approved', 1)",
    )
      .bind(tagger.id, JSON.stringify({ group_id: gid(1), status: "ambassador_tagged" }))
      .run();
    const body = await batchBody(a.cookie);
    expect(leaseIds(body)).toEqual(range(2, 26));
    expect(body.remaining_in_region).toBe(4);
  });

  it("a rejected tag returns its group to the pool", async () => {
    const tagger = await seedAmbassador({ region: "california", email: "t@example.org" });
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    await env.DB.prepare(
      "INSERT INTO submissions (ambassador_id, region, stream, kind, payload, status, created_at) VALUES (?1, 'california', 'knowledge', 'group_tag', ?2, 'rejected', 1)",
    )
      .bind(tagger.id, JSON.stringify({ group_id: gid(1), status: "ambassador_tagged" }))
      .run();
    expect(leaseIds(await batchBody(a.cookie))).toEqual(range(1, 25));
  });

  it("a region with no roster country gets no groups (Belgium has none in the roster)", async () => {
    const b = await seedAmbassador({ region: "belgium", email: "be@example.org" });
    const body = await batchBody(b.cookie, "belgium");
    expect(body.ok).toBe(true);
    expect(body.leases).toEqual([]);
    expect(body.remaining_in_region).toBe(0);
  });

  it("a member of another region gets 403 not_region_member", async () => {
    const n = await seedAmbassador({ region: "norway", email: "n@example.org" });
    const res = await batch(n.cookie, "california");
    expect(res.status).toBe(403);
    expect(((await res.json()) as { error: string }).error).toBe("not_region_member");
  });

  it("no session is 401 and an unknown region is 400", async () => {
    expect((await batch(undefined)).status).toBe(401);
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const res = await batch(a.cookie, "atlantis");
    expect(res.status).toBe(400);
  });

  it("an unreadable roster is 502 and leaves no leases behind", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    rosterStatus = 503;
    const res = await batch(a.cookie);
    expect(res.status).toBe(502);
    expect(((await res.json()) as { error: string }).error).toBe("upstream_unavailable");
    const count = await env.DB.prepare("SELECT COUNT(*) AS n FROM group_leases").first<{ n: number }>();
    expect(count?.n).toBe(0);
  });
});

describe("renew and release", () => {
  it("a lease renews once: +30 days, then 409", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    await batchBody(a.cookie);
    const before = (await leaseRow(gid(1)))?.expires_at ?? 0;
    const first = await renew(a.cookie, gid(1));
    expect(first.status).toBe(200);
    const body = (await first.json()) as { expires_at: number; renewals: number };
    expect(body.renewals).toBe(1);
    expect(body.expires_at).toBe(before + LEASE_MS);
    const second = await renew(a.cookie, gid(1));
    expect(second.status).toBe(409);
    expect(((await second.json()) as { error: string }).error).toBe("renewal_used");
  });

  it("renewal refuses a lease the caller does not hold, an expired one, or a bad id", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    await batchBody(a.cookie);
    expect((await renew(b.cookie, gid(1))).status).toBe(404);
    await env.DB.prepare("UPDATE group_leases SET expires_at = 1 WHERE ambassador_id = ?1").bind(a.id).run();
    expect((await renew(a.cookie, gid(1))).status).toBe(404);
    expect((await renew(a.cookie, "cg_XYZ")).status).toBe(400);
  });

  it("release frees the group for another ambassador", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const b = await seedAmbassador({ region: "california", email: "b@example.org" });
    await batchBody(a.cookie);
    expect((await release(a.cookie, gid(1))).status).toBe(200);
    expect(await leaseRow(gid(1))).toBeNull();
    expect((await release(a.cookie, gid(1))).status).toBe(404);
    expect((await release(b.cookie, gid(2))).status).toBe(404);
    // Group 1 is free again; the other ambassador's batch takes it with the untaken groups 26-30.
    expect(leaseIds(await batchBody(b.cookie))).toEqual([gid(1), ...range(26, 30)]);
  });
});

describe("group_tag and group_suggest submissions", () => {
  it("a tag without a lease is refused (403 not_leased)", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const res = await submitKind(a.cookie, "group_tag", tag());
    expect(res.status).toBe(403);
    expect(((await res.json()) as { error: string }).error).toBe("not_leased");
  });

  it("a tag under an expired lease is refused", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    await batchBody(a.cookie);
    await env.DB.prepare("UPDATE group_leases SET expires_at = 1 WHERE ambassador_id = ?1").bind(a.id).run();
    expect((await submitKind(a.cookie, "group_tag", tag())).status).toBe(403);
  });

  it("a tag under a lease is stored as a knowledge submission and deletes the lease", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    await batchBody(a.cookie);
    const res = await submitKind(a.cookie, "group_tag", tag());
    expect(res.status).toBe(201);
    expect(((await res.json()) as { status: string }).status).toBe("pending");
    const stored = await env.DB.prepare("SELECT stream, kind, status, payload FROM submissions WHERE ambassador_id = ?1")
      .bind(a.id)
      .first<{ stream: string; kind: string; status: string; payload: string }>();
    expect(stored).toEqual(expect.objectContaining({ stream: "knowledge", kind: "group_tag", status: "pending" }));
    expect(JSON.parse(stored?.payload ?? "{}")).toEqual(expect.objectContaining({ group_id: gid(1), sector: "ngo_civil_society" }));
    expect(await leaseRow(gid(1))).toBeNull();
    // The tagged group is not offered again; the other 24 leases stay.
    const after = await batchBody(a.cookie);
    expect(after.leases).toHaveLength(24);
    expect(after.remaining_in_region).toBe(5);
  });

  it("a group_tag sent on the confirm stream is refused as a stream mismatch", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const res = await submitKind(a.cookie, "group_tag", tag(), "california", "confirm");
    expect(((await res.json()) as { error: string }).error).toBe("stream_kind_mismatch");
  });

  it("an invalid tag is 400 invalid_payload with the field", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    await batchBody(a.cookie);
    const res = await submitKind(a.cookie, "group_tag", tag({ sector: "industry" }));
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ ok: false, error: "invalid_payload", field: "sector" });
  });

  it("a group_suggest needs no lease", async () => {
    const a = await seedAmbassador({ region: "california", email: "a@example.org" });
    const res = await submitKind(a.cookie, "group_suggest", { name: "Coast Crew", url: "https://coast.example.org/", country: "US" });
    expect(res.status).toBe(201);
  });
});

describe("validateGroupTag", () => {
  it("accepts a tier-1 tag and keeps only the allowed keys", () => {
    const res = validateGroupTag(tag());
    expect(res.ok).toBe(true);
    if (res.ok) expect(JSON.parse(res.json)).toEqual(expect.objectContaining({ group_id: gid(1), status: "ambassador_tagged" }));
  });

  it("refuses unknown keys, a malformed group_id and an unknown status", () => {
    expect(tagField(tag({ owner_note: "x" }))).toBe("owner_note");
    expect(tagField(tag({ group_id: "cg_XYZ" }))).toBe("group_id");
    expect(tagField(tag({ status: "reviewed" }))).toBe("status");
    expect(tagField("not an object")).toBe("payload");
  });

  it("cannot_determine needs a reason; a reason is refused on a tagged group", () => {
    const base = { group_id: GID, status: "cannot_determine" };
    expect(tagField(base)).toBe("cannot_determine_reason");
    expect(tagField({ ...base, cannot_determine_reason: "bogus" })).toBe("cannot_determine_reason");
    expect(tagField({ ...base, cannot_determine_reason: "no_web_presence" })).toBeUndefined();
    expect(tagField(tag({ cannot_determine_reason: "dead_link" }))).toBe("cannot_determine_reason");
  });

  it("tier 1 needs the five core facets and evidence for plastics_centrality and primary_activities", () => {
    for (const key of ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"]) {
      const p = tag();
      delete p[key];
      expect(tagField(p)).toBe(key);
    }
    const [plasticsEvidence, primaryEvidence] = tagEvidence();
    const onlyPlastics = tag({ evidence: [plasticsEvidence] });
    expect(primaryEvidence).toBeDefined();
    expect(tagField(onlyPlastics)).toBe("evidence");
    expect(tagField(tag({ plastics_centrality: "cannot_determine" }))).toBe("plastics_centrality");
  });

  it("primary activities: one to five, from the vocabulary, no repeats", () => {
    expect(tagField(tag({ primary_activities: [] }))).toBe("primary_activities");
    expect(tagField(tag({ primary_activities: ["advocacy_campaigning", "policy_governance", "research_monitoring", "education_awareness", "cleanup_removal", "other"] }))).toBe(
      "primary_activities",
    );
    expect(tagField(tag({ primary_activities: ["advocacy_campaigning", "advocacy_campaigning"] }))).toBe("primary_activities");
    expect(tagField(tag({ primary_activities: ["lobbying"] }))).toBe("primary_activities");
    const five = ["advocacy_campaigning", "policy_governance", "research_monitoring", "education_awareness", "cleanup_removal"];
    expect(tagField(tag({ primary_activities: five }))).toBeUndefined();
  });

  it("accepts joint_power_authority as a sector (A4-D25) and refuses an unlisted one", () => {
    expect(tagField(tag({ sector: "joint_power_authority" }))).toBeUndefined();
    expect(tagField(tag({ sector: "cooperative" }))).toBe("sector");
  });

  it("participation other than not_applicable needs research_monitoring among the activities", () => {
    expect(tagField(tag({ participation_in_science: "contributory" }))).toBe("participation_in_science");
    expect(tagField(tag({ participation_in_science: "not_applicable" }))).toBeUndefined();
    expect(
      tagField(tag({ participation_in_science: "contributory", primary_activities: ["research_monitoring"] })),
    ).toBeUndefined();
  });

  it("places are ISO 3166 codes (five at most); website languages are two lowercase letters", () => {
    expect(tagField(tag({ places: ["NO", "US-CA"] }))).toBeUndefined();
    expect(tagField(tag({ places: ["usa"] }))).toBe("places");
    expect(tagField(tag({ places: ["NO", "BE", "US", "FR", "DE", "ES"] }))).toBe("places");
    expect(tagField(tag({ website_languages: ["en", "no"] }))).toBeUndefined();
    expect(tagField(tag({ website_languages: ["EN"] }))).toBe("website_languages");
  });

  it("themes are short strings (80 characters) and constituency is from its vocabulary", () => {
    expect(tagField(tag({ themes: ["plastic pellets"] }))).toBeUndefined();
    expect(tagField(tag({ themes: ["x".repeat(81)] }))).toBe("themes");
    expect(tagField(tag({ constituency: ["youth", "faith"] }))).toBeUndefined();
    expect(tagField(tag({ constituency: ["martians"] }))).toBe("constituency");
  });

  it("quotes are at most 25 words, and exactly one of quote or not_stated", () => {
    const words = (n: number): string => Array.from({ length: n }, () => "word").join(" ");
    const evidence = (extra: Record<string, unknown>): Record<string, unknown>[] => [
      { facet: "plastics_centrality", url: "https://example.org/a", accessed_at: "2026-11-20", ...extra },
      tagEvidence()[1],
    ];
    expect(tagField(tag({ evidence: evidence({ quote: words(25) }) }))).toBeUndefined();
    expect(tagField(tag({ evidence: evidence({ quote: words(26) }) }))).toBe("evidence");
    expect(tagField(tag({ evidence: evidence({ quote: "a quote", not_stated: true }) }))).toBe("evidence");
    expect(tagField(tag({ evidence: evidence({}) }))).toBe("evidence");
  });

  it("evidence URLs are http or https without credentials, and accessed_at is a real date", () => {
    const withUrl = (url: string, accessed = "2026-11-20"): Record<string, unknown> =>
      tag({
        evidence: [
          { facet: "plastics_centrality", url, accessed_at: accessed, quote: "a short quote" },
          { facet: "primary_activities", url: "https://example.org/p", accessed_at: "2026-11-20", not_stated: true },
        ],
      });
    expect(tagField(withUrl("http://example.org/x"))).toBeUndefined();
    expect(tagField(withUrl("ftp://example.org/x"))).toBe("evidence");
    expect(tagField(withUrl("https://user:pw@example.org/x"))).toBe("evidence");
    expect(tagField(withUrl("https://example.org/x", "2026-02-30"))).toBe("evidence");
  });

  it("stated affiliations need a relation from the vocabulary and a quote (not_stated is refused)", () => {
    const affiliation = (relation: string, evidence: Record<string, unknown>): Record<string, unknown> => ({
      target_name: "Parent Coalition",
      relation,
      evidence: { url: "https://example.org/partners", accessed_at: "2026-11-20", ...evidence },
    });
    expect(tagField(tag({ stated_affiliations: [affiliation("member_of", { quote: "a member of the network" })] }))).toBeUndefined();
    expect(tagField(tag({ stated_affiliations: [affiliation("sibling_of", { quote: "x" })] }))).toBe("stated_affiliations");
    expect(tagField(tag({ stated_affiliations: [affiliation("member_of", { not_stated: true })] }))).toBe("stated_affiliations");
    expect(tagField(tag({ stated_affiliations: [{ relation: "member_of", evidence: { url: "https://e.org", accessed_at: "2026-11-20", quote: "q" } }] }))).toBe(
      "stated_affiliations",
    );
  });

  it("not_an_organisation true leaves every facet absent", () => {
    expect(tagField(tag({ not_an_organisation: true }))).toBe("entity_type");
    const onlyStatus = { group_id: GID, status: "cannot_determine", cannot_determine_reason: "not_an_organisation", not_an_organisation: true };
    expect(tagField(onlyStatus)).toBeUndefined();
    expect(tagField({ ...onlyStatus, not_an_organisation: "yes" })).toBe("not_an_organisation");
  });

  it("refuses email-looking strings anywhere in the tag", () => {
    expect(tagField(tag({ legal_form_note: "write to info@example.org" }))).toBe("email");
    expect(tagField(tag({ themes: ["contact: a.b@c.org"] }))).toBe("email");
  });

  it("the stored JSON is capped at 12,000 characters", () => {
    const longUrl = `https://example.org/${"a".repeat(480)}`;
    const quote = Array.from({ length: 25 }, () => "abcdefghijklmno").join(" ");
    // Tier 1 needs the two core-facet entries; the rest are long themes entries that push the stored JSON past 12,000.
    const [plasticsEvidence, primaryEvidence] = tagEvidence();
    const themes = Array.from({ length: 13 }, () => ({ facet: "themes", url: longUrl, accessed_at: "2026-11-20", quote }));
    expect(tagField(tag({ evidence: [plasticsEvidence, primaryEvidence, ...themes] }))).toBe("payload");
  });
});

describe("validateGroupSuggest", () => {
  it("accepts a name and an http(s) URL, uppercasing the country", () => {
    const res = validateGroupSuggest({ name: "Coast Crew", url: "http://coast.example.org/", country: "no", note: "found on a map" });
    expect(res.ok).toBe(true);
    if (res.ok) expect(JSON.parse(res.json)).toEqual({ name: "Coast Crew", url: "http://coast.example.org/", country: "NO", note: "found on a map" });
  });

  it("needs a name and a URL; the country is two letters; the note is at most 1000 characters", () => {
    expect(suggestField({ url: "https://e.org" })).toBe("name");
    expect(suggestField({ name: "x" })).toBe("url");
    expect(suggestField({ name: "x", url: "ftp://e.org" })).toBe("url");
    expect(suggestField({ name: "x", url: "https://e.org", country: "USA" })).toBe("country");
    expect(suggestField({ name: "x", url: "https://e.org", note: "n".repeat(1001) })).toBe("note");
    expect(suggestField({ name: "x", url: "https://e.org", website: "https://e.org" })).toBe("website");
  });

  it("refuses an email address in the note", () => {
    expect(suggestField({ name: "x", url: "https://e.org", note: "ask jo@example.org" })).toBe("email");
  });
});
