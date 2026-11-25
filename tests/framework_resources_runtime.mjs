// Runtime checks for the Framework Related resources page (EM-16).
// The pure helpers live in framework/src/components/resources.js; the registry check reads the
// committed site/data/california/linkouts.json (the same file the page loads at runtime).
import assert from "node:assert/strict";
import {existsSync, readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {buildCard, iconUrl, institutionHref, isHttps, matchesQuery} from "../framework/src/components/resources.js";

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
    this.attributes = {};
  }

  get textContent() {
    return this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this.children = [new FakeText(value)];
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  append(...nodes) {
    for (const node of nodes) this.children.push(typeof node === "string" ? new FakeText(node) : node);
  }
}

globalThis.document = {
  baseURI: "http://localhost/resources",
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

// iconUrl: only stored icons under assets/linkouts/ resolve; anything else gets the initials plane.
{
  assert.equal(iconUrl("assets/linkouts/lo-1.png"), "http://localhost/assets/linkouts/lo-1.png");
  assert.equal(iconUrl("assets/linkouts/lo-13.svg"), "http://localhost/assets/linkouts/lo-13.svg");
  for (const bad of [null, undefined, "", "assets/networks/x.png", "assets/linkouts/../x.png",
    "/assets/linkouts/a.png", "https://example.org/a.png", "assets/linkouts/a.gif", "assets/linkouts/A.png"]) {
    assert.equal(iconUrl(bad), null, `no icon for ${JSON.stringify(bad)}`);
  }
}

// institutionHref: the steward links to ./institution#inst=<id>; unsafe ids get no link.
{
  assert.equal(institutionHref("I84218800"), "http://localhost/institution#inst=I84218800");
  assert.equal(institutionHref("CAAG-OEHHA"), "http://localhost/institution#inst=CAAG-OEHHA");
  for (const bad of [null, undefined, "", "a b", "I1#x", "../x", "x".repeat(65)]) {
    assert.equal(institutionHref(bad), null, `no link for ${JSON.stringify(bad)}`);
  }
}

// Card header: a decorative 40 px icon (empty alt, lazy) beside the title; initials when no icon.
{
  const base = {
    id: "LO-x",
    name: "Example registry",
    root_url: "https://example.org/",
    relation: "Registry",
    steward: "Example steward",
    description: "A registry of examples.",
    terms_status: "recorded",
    terms: "CC BY 4.0",
  };
  const withIcon = buildCard({...base, icon: "assets/linkouts/lo-x.png", initials: "ES"});
  const head = withIcon.children[0];
  assert.equal(head.className, "rs-head", "the icon and title share a header row");
  const [img, title] = head.children;
  assert.equal(img.tagName, "IMG");
  assert.equal(img.className, "rs-icon");
  assert.equal(img.src, "http://localhost/assets/linkouts/lo-x.png");
  assert.equal(img.alt, "", "decorative: the title names the site");
  assert.equal(img.width, 40);
  assert.equal(img.height, 40);
  assert.equal(img.loading, "lazy");
  assert.equal(title.tagName, "H2");
  assert.equal(title.children[0].tagName, "A", "the title still links to the resource");

  const plane = buildCard({...base, icon: null, initials: "DT"}).children[0].children[0];
  assert.equal(plane.tagName, "SPAN");
  assert.equal(plane.className, "rs-icon rs-icon-initials");
  assert.equal(plane.textContent, "DT");
  assert.equal(plane.attributes["aria-hidden"], "true", "initials are decorative too");

  const hostile = buildCard({...base, icon: null, initials: "<img src=x>"}).children[0].children[0];
  assert.equal(hostile.textContent, "", "initials are validated; markup never reaches the page");
}

// Steward link: a steward with an Atlas id links to its institution page; otherwise it is plain text.
{
  const base = {
    id: "LO-x",
    name: "Example registry",
    root_url: "https://example.org/",
    relation: "Registry",
    description: "A registry of examples.",
    terms_status: "recorded",
    terms: "CC BY 4.0",
    initials: "ES",
    icon: null,
  };
  const stewardField = (card) => card.children.find((node) => node.className === "rs-field");

  const linked = stewardField(buildCard({...base, steward: "SCCWRP", steward_inst_id: "I11006740"}));
  assert.equal(linked.children[0].textContent, "Steward: ");
  const link = linked.children[1];
  assert.equal(link.tagName, "A");
  assert.equal(link.textContent, "SCCWRP");
  assert.equal(link.href, "http://localhost/institution#inst=I11006740", "internal link, no external icon");
  assert.equal(link.target, undefined, "not a new-tab link");

  const plain = stewardField(buildCard({...base, steward: "Plastiverse", steward_inst_id: null}));
  assert.equal(plain.children[1].tagName, undefined, "unmatched steward stays text (a FakeText node)");
  assert.equal(plain.textContent, "Steward: Plastiverse");
}

// Registry export: every entry links to https and the public file never names the excluded map.
{
  const path = fileURLToPath(new URL("../site/data/california/linkouts.json", import.meta.url));
  const raw = readFileSync(path, "utf8");
  const payload = JSON.parse(raw);
  assert.ok(Array.isArray(payload.entries) && payload.entries.length > 0, "no entries");
  for (const entry of payload.entries) {
    assert.equal(isHttps(entry.root_url), true, `${entry.id} root_url must be https`);
    assert.equal(isHttps(entry.description_source), true, `${entry.id} description_source must be https`);
  }
  assert.equal(raw.toLowerCase().includes("minderoo"), false, "linkouts.json must not mention Minderoo");

  // Every stored icon exists under site/, every steward id links, and initials are valid.
  for (const entry of payload.entries) {
    if (entry.icon !== null) {
      assert.notEqual(iconUrl(entry.icon), null, `${entry.id} icon must be a stored asset path`);
      const iconPath = fileURLToPath(new URL(`../site/${entry.icon}`, import.meta.url));
      assert.equal(existsSync(iconPath), true, `${entry.id} icon file is missing`);
    }
    assert.match(entry.initials, /^[A-Z0-9]{1,3}$/, `${entry.id} initials`);
    if (entry.steward_inst_id !== null) {
      assert.notEqual(institutionHref(entry.steward_inst_id), null, `${entry.id} steward_inst_id`);
    }
  }
}
