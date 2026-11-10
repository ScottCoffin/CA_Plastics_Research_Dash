---
title: SPK-3 shell bench (Framework)
sidebar: false
toc: false
---

<style>
#facets { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px 12px; }
#results .scroll { height: 360px; overflow: auto; position: relative; border: 1px solid #ccc; font: 12px monospace; }
#results .row { position: absolute; left: 0; right: 0; height: 24px; line-height: 24px; white-space: nowrap; overflow: hidden; padding: 0 6px; box-sizing: border-box; }
#map { height: 120px; border: 1px dashed #888; display: flex; align-items: center; justify-content: center; margin: 8px 0; }
</style>

# SPK-3 shell bench (Framework)

```js
const ds = new URLSearchParams(location.search).get("ds") ?? "syn30k";
const rows = (await (await fetch(`/data/${ds}.json`)).json()).works;
```

```js
const DOMAIN = ["ecotox", "policy", "health", "fate", "monitoring", "recycling", "biodegradation", "sources"];
const FACET = ["ca-science", "water", "air", "soil", "food", "policy-brief"];
const INST = ["any", "academic", "government", "industry", "ngo", "unknown"];
const CA = ["any", "led", "any_author", "not_led"];
const YEARS = Array.from({length: 27}, (_, i) => 2000 + i);
const ROW_H = 24;
const WIN = 100;
const fmt = (r) => `${r.work_id} | ${r.year} | ${r.title} | ${(r.domain_tags ?? []).join(",")} | ${r.institution_type ?? "unknown"} | oa=${r.oa ?? false}`;
```

```js
const yfEl = Inputs.range([2000, 2026], {step: 1, value: 2000, label: "Year from"});
const ytEl = Inputs.range([2000, 2026], {step: 1, value: 2026, label: "Year to"});
const domEl = Inputs.checkbox(DOMAIN, {label: "Domain tags"});
const facEl = Inputs.checkbox(FACET, {label: "Facet tags"});
const instEl = Inputs.select(INST, {label: "Institution type"});
const caEl = Inputs.select(CA, {label: "CA basis"});
const oaEl = Inputs.toggle({label: "Open access only"});
const yf = Generators.input(yfEl);
const yt = Generators.input(ytEl);
const dom = Generators.input(domEl);
const fac = Generators.input(facEl);
const inst = Generators.input(instEl);
const ca = Generators.input(caEl);
const oa = Generators.input(oaEl);
```

```js
const facets = html`<div id="facets">
  <div data-facet="yf">${yfEl}</div>
  <div data-facet="yt">${ytEl}</div>
  <div data-facet="domain">${domEl}</div>
  <div data-facet="facet">${facEl}</div>
  <div data-facet="inst">${instEl}</div>
  <div data-facet="ca">${caEl}</div>
  <div data-facet="oa">${oaEl}</div>
</div>`;
```

```js
facets
```

```js
const filtered = rows.filter((r) => r.year >= yf && r.year <= yt
  && (!dom.length || (r.domain_tags ?? []).some((t) => dom.includes(t)))
  && (!fac.length || (r.facet_tags ?? []).some((t) => fac.includes(t)))
  && (inst === "any" || (r.institution_type ?? "unknown") === inst)
  && (ca === "any" || (ca === "led" && r.ca_led) || (ca === "any_author" && r.ca_any_author) || (ca === "not_led" && !r.ca_led))
  && (!oa || r.oa === true));
```

```js
function renderResults(list) {
  const tagCounts = {};
  const bins = new Map(YEARS.map((y) => [y, 0]));
  for (const r of list) {
    if (bins.has(r.year)) bins.set(r.year, bins.get(r.year) + 1);
    for (const t of [...(r.domain_tags ?? []), ...(r.facet_tags ?? [])]) tagCounts[t] = (tagCounts[t] ?? 0) + 1;
  }
  const chart = Plot.plot({
    width: 700, height: 150, marginBottom: 24,
    x: {tickFormat: "d", label: null},
    marks: [Plot.barY([...bins].map(([year, n]) => ({year, n})), {x: "year", y: "n"})]
  });
  const scroll = html`<div class="scroll"><div class="spacer" style="height:${list.length * ROW_H}px"></div></div>`;
  const draw = () => {
    const start = Math.min(Math.floor(scroll.scrollTop / ROW_H), Math.max(0, list.length - WIN));
    const end = Math.min(list.length, start + WIN);
    scroll.querySelectorAll(".row").forEach((n) => n.remove());
    for (let i = start; i < end; i++) {
      const d = document.createElement("div");
      d.className = "row";
      d.style.top = `${i * ROW_H}px`;
      d.textContent = fmt(list[i]);
      scroll.appendChild(d);
    }
  };
  scroll.addEventListener("scroll", draw);
  draw();
  window.__seq = (window.__seq ?? 0) + 1;
  return html`<div id="results">
    <div id="status" data-seq=${window.__seq} data-n=${list.length}>${list.length} of ${rows.length} works match</div>
    <div id="counts">${[...DOMAIN, ...FACET].map((t) => `${t}:${tagCounts[t] ?? 0}`).join(" ")}</div>
    ${chart}
    <div id="map">Map placeholder</div>
    ${scroll}
  </div>`;
}
```

```js
const results = renderResults(filtered);
```

```js
results
```

```js
{
  results;
  window.__ttiMs ??= performance.now();
}
```
