// Runtime checks for the Framework Related resources page (EM-16).
// The pure helpers live in framework/src/components/resources.js; the registry check reads the
// committed site/data/linkouts.json (the same file the page loads at runtime).
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {buildCard, isHttps, matchesQuery} from "../framework/src/components/resources.js";

// buildCard only creates elements, sets text and appends children, so a small stand-in document is
// enough. Text enters only through textContent or text nodes, as it does in the browser.
class FakeText {
  constructor(data) {
    this.data = String(data);
  }

  get textContent() {
    return this.data;
  }
}

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.className = "";
  }

  get textContent() {
    return this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this.children = [new FakeText(value)];
  }

  append(...nodes) {
    for (const node of nodes) this.children.push(typeof node === "string" ? new FakeText(node) : node);
  }
}

globalThis.document = {
  createElement: (tagName) => new FakeElement(tagName),
  createTextNode: (text) => new FakeText(text),
};

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

// Disclosure: a link-out's disclosure is a text paragraph after the card, present only when non-empty.
{
  const base = {
    id: "example",
    name: "Example registry",
    root_url: "https://example.org/",
    relation: "Registry",
    steward: "Example steward",
    description: "A registry of examples.",
    terms_status: "recorded",
    terms: "CC BY 4.0",
  };
  const disclosed = buildCard({...base, disclosure: "The Atlas owner is a listed contributor to this consortium."});
  const notes = disclosed.children.filter((node) => node.className === "rs-disclosure");
  assert.equal(notes.length, 1, "one disclosure paragraph");
  assert.equal(notes[0].tagName, "P");
  assert.equal(notes[0].textContent, "Disclosure: The Atlas owner is a listed contributor to this consortium.");
  assert.equal(disclosed.children.at(-1), notes[0], "the disclosure comes last on the card");

  const hostile = buildCard({...base, disclosure: "<img src=x onerror=alert(1)>"});
  const hostileNote = hostile.children.find((node) => node.className === "rs-disclosure");
  assert.equal(hostileNote.textContent, "Disclosure: <img src=x onerror=alert(1)>", "disclosure text stays text");
  assert.equal(hostileNote.children.length, 1, "no markup is parsed out of the disclosure");

  for (const disclosure of [undefined, null, "", "   ", 42]) {
    const card = buildCard({...base, disclosure});
    assert.equal(card.children.some((node) => node.className === "rs-disclosure"), false, `no paragraph for ${JSON.stringify(disclosure)}`);
  }
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
