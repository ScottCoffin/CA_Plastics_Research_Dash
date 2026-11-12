// Runtime checks for the Framework Related resources page (EM-16).
// The pure helpers live in framework/src/components/resources.js; the registry check reads the
// committed site/data/linkouts.json (the same file the page loads at runtime).
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {isHttps, matchesQuery} from "../framework/src/components/resources.js";

// isHttps: only absolute https URLs with a host qualify.
{
  assert.equal(isHttps("https://www.globalplasticlaws.org/"), true);
  assert.equal(isHttps("https://example.org/a?b=c#d"), true);
  assert.equal(isHttps("HTTPS://EXAMPLE.ORG/"), true);
  assert.equal(isHttps("http://example.org/"), false);
  assert.equal(isHttps("javascript:alert(1)"), false);
  assert.equal(isHttps("https://"), false);
  assert.equal(isHttps("not a url"), false);
  assert.equal(isHttps(""), false);
  assert.equal(isHttps(null), false);
  assert.equal(isHttps(undefined), false);
  assert.equal(isHttps(42), false);
}

// matchesQuery: case-insensitive match on name, steward or description; empty query matches all.
{
  const entry = {
    name: "Global Plastic Laws",
    steward: "Plastic Pollution Coalition",
    description: "plastic legislation that has been passed around the world"
  };
  assert.equal(matchesQuery(entry, ""), true);
  assert.equal(matchesQuery(entry, "   "), true);
  assert.equal(matchesQuery(entry, undefined), true);
  assert.equal(matchesQuery(entry, "global plastic"), true);
  assert.equal(matchesQuery(entry, "COALITION"), true);
  assert.equal(matchesQuery(entry, "legislation"), true);
  assert.equal(matchesQuery(entry, "  legislation  "), true);
  assert.equal(matchesQuery(entry, "toxicity"), false);
  assert.equal(matchesQuery({}, "anything"), false);
  assert.equal(matchesQuery(null, ""), true);
}

// Registry export: every entry links to https and the public file never names the excluded map.
{
  const path = fileURLToPath(new URL("../site/data/linkouts.json", import.meta.url));
  const raw = readFileSync(path, "utf8");
  const payload = JSON.parse(raw);
  assert.ok(Array.isArray(payload.entries) && payload.entries.length > 0, "no entries");
  for (const entry of payload.entries) {
    assert.equal(isHttps(entry.root_url), true, `${entry.id} root_url must be https`);
    assert.equal(isHttps(entry.description_source), true, `${entry.id} description_source must be https`);
  }
  assert.equal(raw.toLowerCase().includes("minderoo"), false, "linkouts.json must not mention Minderoo");
}
