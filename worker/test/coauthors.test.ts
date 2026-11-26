import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { COAUTHORS_LIMIT, COAUTHORS_ROWS } from "../src/coauthors";
import type { Env } from "../src/env";
import type { Fetch } from "../src/outbound";
import { handle } from "../src/index";
import { seedAmbassador } from "./helpers";

// GET /me/coauthors (AMB-1 front end slice 3, owner 2026-11-26). OpenAlex is answered by a fake Fetch passed to
// handle(); nothing reaches the network. Each test uses a fresh random author id, so the Workers cache cannot leak
// one test's answer into another.

const NIVA = "I2802939387";
const API = "https://api.plastiverse.live";

function randomAuthorId(): string {
  return `A${100000000 + Math.floor(Math.random() * 899999999)}`;
}

function oa(id: string): string {
  return `https://openalex.org/${id}`;
}

/** One authorship as OpenAlex returns it in a works listing (select=id,authorships). */
function authorship(id: string | null, name: string, institutions: [string, string][] = []) {
  return {
    author: id === null ? { display_name: name } : { id: oa(id), display_name: name },
    institutions: institutions.map(([instId, instName]) => ({ id: oa(instId), display_name: instName })),
  };
}

function fakeOpenAlex(answer: { status: number; body?: unknown } | "throw") {
  const urls: string[] = [];
  const fetchImpl: Fetch = async (input) => {
    urls.push(input);
    if (answer === "throw") throw new Error("network down");
    return new Response(JSON.stringify(answer.body ?? {}), {
      status: answer.status,
      headers: { "Content-Type": "application/json" },
    });
  };
  return { urls, fetchImpl };
}

async function seedWithAuthor(authorId: string | null): Promise<{ id: string; cookie: string }> {
  const seeded = await seedAmbassador({ region: "norway", email: `coauthor-${Math.random()}@niva.no` });
  await env.DB.prepare("UPDATE ambassadors SET author_id = ?1 WHERE id = ?2").bind(authorId, seeded.id).run();
  return seeded;
}

function getCoauthors(cookie: string | null, fetchImpl: Fetch, now = Date.now()): Promise<Response> {
  const headers: Record<string, string> = cookie ? { Cookie: cookie } : {};
  return handle(new Request(`${API}/me/coauthors`, { headers }), env as unknown as Env, now, fetchImpl);
}

describe("GET /me/coauthors", () => {
  it("requires a session", async () => {
    const net = fakeOpenAlex({ status: 200, body: { results: [] } });
    const res = await getCoauthors(null, net.fetchImpl);
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ ok: false, error: "not_signed_in" });
    expect(net.urls).toHaveLength(0);
  });

  it("answers no_author_record without calling OpenAlex when there is no author id or it is malformed", async () => {
    for (const authorId of [null, "A12", "https://openalex.org/A123456", "A1234567890123"]) {
      const { cookie } = await seedWithAuthor(authorId);
      const net = fakeOpenAlex({ status: 200, body: { results: [] } });
      const res = await getCoauthors(cookie, net.fetchImpl);
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ ok: true, coauthors: [], reason: "no_author_record" });
      expect(net.urls).toHaveLength(0);
    }
  });

  it("aggregates co-authors: self excluded, shared counted once per work, institutions and regions", async () => {
    const self = randomAuthorId();
    const { cookie } = await seedWithAuthor(self);
    const net = fakeOpenAlex({
      status: 200,
      body: {
        results: [
          {
            id: oa("W1"),
            authorships: [
              authorship(self, "Self Person"),
              authorship("A5000000002", "Bo Berg", [[NIVA, "NIVA"]]),
              authorship("A5000000003", "Cy Dahl"),
              authorship(null, "Nameless Id"),
            ],
          },
          {
            id: oa("W2"),
            authorships: [
              authorship(self, "Self Person"),
              authorship("A5000000002", "Bo Berg", [[NIVA, "NIVA"], ["I5", "Other Lab"]]),
              authorship("A5000000002", "Bo Berg", [[NIVA, "NIVA"]]),
              authorship("A5000000003", "Cy Dahl"),
            ],
          },
          {
            id: oa("W3"),
            authorships: [authorship("A5000000003", "Cy Dahl"), authorship("A5000000004", " Amy Ash ", [["I999", "Unlisted Lab"]])],
          },
        ],
      },
    });
    const res = await getCoauthors(cookie, net.fetchImpl);
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.ok).toBe(true);
    expect(body.total).toBe(3);
    expect(body.works_read).toBe(3);
    expect(body.coauthors).toEqual([
      { id: "A5000000003", name: "Cy Dahl", shared: 3, institution_ids: [], institution: null, regions: [] },
      {
        id: "A5000000002",
        name: "Bo Berg",
        shared: 2,
        institution_ids: [NIVA, "I5"],
        institution: "NIVA",
        regions: ["norway"],
      },
      {
        id: "A5000000004",
        name: "Amy Ash",
        shared: 1,
        institution_ids: ["I999"],
        institution: "Unlisted Lab",
        regions: [],
      },
    ]);
    const serialised = JSON.stringify(body);
    expect(serialised).not.toContain(self);
    expect(serialised).not.toMatch(/@|orcid/i);
  });

  it("sends one OpenAlex works request with the author filter and the selected fields", async () => {
    const self = randomAuthorId();
    const { cookie } = await seedWithAuthor(self);
    const net = fakeOpenAlex({ status: 200, body: { results: [] } });
    const res = await getCoauthors(cookie, net.fetchImpl);
    expect(res.status).toBe(200);
    expect(net.urls).toHaveLength(1);
    const url = new URL(net.urls[0]);
    expect(url.origin + url.pathname).toBe("https://api.openalex.org/works");
    expect(url.searchParams.get("filter")).toBe(`author.id:${self}`);
    expect(url.searchParams.get("select")).toBe("id,authorships");
    expect(url.searchParams.get("per-page")).toBe("200");
    expect(url.searchParams.get("sort")).toBe("publication_date:desc");
    expect(await res.json()).toEqual({ ok: true, coauthors: [], total: 0, works_read: 0 });
  });

  it("returns the top 50 by shared works, then by name, with the total", async () => {
    const self = randomAuthorId();
    const { cookie } = await seedWithAuthor(self);
    const pad = (n: number) => String(n).padStart(2, "0");
    const crowd = Array.from({ length: 60 }, (_, i) => authorship(`A70000000${pad(i)}`, `Person ${pad(i)}`));
    const net = fakeOpenAlex({
      status: 200,
      body: {
        results: [
          { authorships: [authorship(self, "Self"), ...crowd] },
          { authorships: [authorship(self, "Self"), authorship("A7000000059", "Person 59")] },
        ],
      },
    });
    const body = (await (await getCoauthors(cookie, net.fetchImpl)).json()) as {
      coauthors: { id: string; shared: number }[];
      total: number;
    };
    expect(body.total).toBe(60);
    expect(body.coauthors).toHaveLength(COAUTHORS_ROWS);
    expect(body.coauthors[0]).toMatchObject({ id: "A7000000059", shared: 2 });
    expect(body.coauthors[1]).toMatchObject({ id: "A7000000000", shared: 1 });
    expect(body.coauthors[COAUTHORS_ROWS - 1]).toMatchObject({ id: "A7000000048", shared: 1 });
  });

  it("answers 502 upstream_unavailable when OpenAlex fails or cannot be reached", async () => {
    for (const answer of [{ status: 500 }, { status: 429 }, "throw"] as const) {
      const { cookie } = await seedWithAuthor(randomAuthorId());
      const net = fakeOpenAlex(answer);
      const res = await getCoauthors(cookie, net.fetchImpl);
      expect(res.status).toBe(502);
      expect(await res.json()).toEqual({ ok: false, error: "upstream_unavailable" });
    }
  });

  it("caches the answer per author, so a second visit makes no OpenAlex call", async () => {
    const { cookie } = await seedWithAuthor(randomAuthorId());
    const net = fakeOpenAlex({ status: 200, body: { results: [] } });
    expect((await getCoauthors(cookie, net.fetchImpl)).status).toBe(200);
    expect((await getCoauthors(cookie, net.fetchImpl)).status).toBe(200);
    expect(net.urls).toHaveLength(1);
  });

  it("limits uncached reads to 30 per account per hour", async () => {
    const now = Date.now();
    const { id, cookie } = await seedWithAuthor(randomAuthorId());
    const windowIndex = Math.floor(now / COAUTHORS_LIMIT.windowMs);
    const expiresAt = (windowIndex + 1) * COAUTHORS_LIMIT.windowMs;
    await env.DB.prepare("INSERT INTO rate_limits (bucket, count, expires_at) VALUES (?1, ?2, ?3)")
      .bind(`account:coauthors:${id}:${windowIndex}`, COAUTHORS_LIMIT.limit, expiresAt)
      .run();
    const net = fakeOpenAlex({ status: 200, body: { results: [] } });
    const res = await getCoauthors(cookie, net.fetchImpl, now);
    expect(res.status).toBe(429);
    expect(await res.json()).toEqual({ ok: false, error: "rate_limited" });
    expect(net.urls).toHaveLength(0);
  });

  it("refuses other methods", async () => {
    const { cookie } = await seedWithAuthor(randomAuthorId());
    const net = fakeOpenAlex({ status: 200, body: { results: [] } });
    const res = await handle(
      new Request(`${API}/me/coauthors`, { method: "POST", headers: { Cookie: cookie } }),
      env as unknown as Env,
      Date.now(),
      net.fetchImpl,
    );
    expect(res.status).toBe(405);
    expect(net.urls).toHaveLength(0);
  });
});
