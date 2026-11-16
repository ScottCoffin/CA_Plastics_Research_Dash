// Runtime checks for the Framework V-4 trend panel helpers (EM-7).
// The pure helpers live in framework/src/components/v4_trend_model.js.
import assert from "node:assert/strict";
import {
  FIRST_YEAR,
  caShare,
  escapeHtml,
  isRecent,
  niceMax,
  refDateFor,
  seriesByTopic,
  seriesFromRows,
  yearRange
} from "../framework/src/components/v4_trend_model.js";

// yearRange and FIRST_YEAR.
assert.equal(FIRST_YEAR, 2000);
assert.deepEqual(yearRange(2024, 2026), [2024, 2025, 2026]);
assert.deepEqual(yearRange(2026, 2025), []);

// seriesByTopic asks the counts function one question per (year, topic) and one per year.
{
  const calls = [];
  const fake = (sel) => {
    calls.push(sel);
    const year = Number(sel.year[0]);
    if (!sel.topic) return year % 2 === 0 ? 10 : 5;
    return sel.topic[0] === "air" ? 2 : 1;
  };
  const out = seriesByTopic(fake, [2000, 2001], ["air", "soil"]);
  assert.deepEqual(out.years, [2000, 2001]);
  assert.deepEqual(out.totals, [10, 5]);
  assert.deepEqual(out.series, [
    {topic: "air", values: [2, 2]},
    {topic: "soil", values: [1, 1]}
  ]);
  assert.equal(calls.length, 2 + 4);
  assert.deepEqual(calls[0], {year: ["2000"], topic: ["air"]});
  assert.ok(calls.some((sel) => sel.topic === undefined && sel.year[0] === "2001"));
}

// caShare: fraction per year, skipping years with no positive global count and years not in corpus.
{
  const rows = caShare({2019: 5, 2020: 3, 2021: 0}, {2019: 100, 2020: 0, 2021: 50, 2018: 20});
  assert.deepEqual(rows, [
    {year: 2018, corpus: 0, global: 20, share: 0},
    {year: 2019, corpus: 5, global: 100, share: 0.05},
    {year: 2021, corpus: 0, global: 50, share: 0}
  ]);
  assert.deepEqual(caShare({}, null), []);
}

// isRecent: years overlapping the 12 months ending at the reference date.
{
  const ref = new Date("2026-11-12T18:00:00Z");
  assert.equal(isRecent(2026, ref), true);
  assert.equal(isRecent(2025, ref), true);
  assert.equal(isRecent(2024, ref), false);
  assert.equal(isRecent(2026, new Date("invalid")), false);
  assert.equal(isRecent(2010, null), false);
}

// refDateFor: fetched_at when valid, otherwise the supplied today.
{
  const today = new Date("2026-11-12T00:00:00Z");
  assert.equal(refDateFor({fetched_at: "2026-10-01T00:00:00Z"}, today).toISOString(), "2026-10-01T00:00:00.000Z");
  assert.equal(refDateFor(null, today), today);
  assert.equal(refDateFor({fetched_at: "not a date"}, today), today);
}

// niceMax rounds up to 1, 2, 5 or 10 times a power of ten.
assert.equal(niceMax(0), 1);
assert.equal(niceMax(7), 10);
assert.equal(niceMax(1200), 2000);
assert.equal(niceMax(0.3), 0.5);
assert.equal(niceMax(5), 5);

// escapeHtml neutralises markup characters.
assert.equal(escapeHtml(`<a href="x">&'`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
assert.equal(escapeHtml(null), "");

// seriesFromRows counts filtered rows per year and per topic; duplicate tags count once,
// out-of-range years and unknown topics are ignored.
{
  const rows = [
    {year: 2024, domain_tags: ["air", "air"]},
    {year: 2024, domain_tags: ["air", "soil_and_agriculture"]},
    {year: 2025, domain_tags: []},
    {year: 1999, domain_tags: ["air"]},
    {year: 2025, domain_tags: ["unknown_tag"]}
  ];
  const data = seriesFromRows(rows, [2024, 2025], ["air", "soil_and_agriculture"]);
  assert.deepEqual(data.totals, [2, 2]);
  assert.deepEqual(data.series, [
    {topic: "air", values: [2, 0]},
    {topic: "soil_and_agriculture", values: [1, 0]}
  ]);
  assert.deepEqual(seriesFromRows(null, [2024], ["air"]).totals, [0]);

  // The row-derived initial chart and filtered redraw have the same series shape and counts
  // as the index query path, including multi-topic works and out-of-range years.
  const countRows = (selected) => rows.filter((row) => {
    const yearMatches = row.year >= Number(selected.year[0]) && row.year <= Number(selected.year.at(-1));
    const topicMatches = !selected.topic || selected.topic.some((topic) => row.domain_tags.includes(topic));
    return yearMatches && topicMatches;
  }).length;
  assert.deepEqual(
    seriesFromRows(rows, [2024, 2025], ["air", "soil_and_agriculture"]),
    seriesByTopic(countRows, [2024, 2025], ["air", "soil_and_agriculture"])
  );
  const filteredRows = rows.filter((row) => row.year === 2024);
  const filteredCounts = (selected) => (selected.year.includes("2024") ? countRows(selected) : 0);
  assert.deepEqual(
    seriesFromRows(filteredRows, [2024, 2025], ["air", "soil_and_agriculture"]),
    seriesByTopic(filteredCounts, [2024, 2025], ["air", "soil_and_agriculture"])
  );
}

// The trend renderer uses the supplied normalized rows for its initial chart, then uses the same
// row path for filtered updates. No index counts are needed when rows are available; the legacy
// index-count fallback remains available for callers without initialRows.
{
  const previousWindow = globalThis.window;
  const previousFetch = globalThis.fetch;
  globalThis.window = {};
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({query_version: "test-v1", fetched_at: "2026-01-01T00:00:00Z", by_year: {2024: 100, 2025: 120}})
  });
  try {
    const {mountV4Trend} = await import("../framework/src/components/v4_trend.js");
    const topics = new Set(["air", "soil_and_agriculture"]);
    const noCountIndex = {ids: {topic: topics}, counts: () => { throw new Error("initial rows should avoid index counts"); }};
    const initialRows = [
      {year: 2024, domain_tags: ["air", "air", "soil_and_agriculture"]},
      {year: 2024, domain_tags: ["air"]},
      {year: 2025, domain_tags: ["soil_and_agriculture"]},
      {year: 1999, domain_tags: ["air"]}
    ];
    const container = {classList: {add() {}}, innerHTML: ""};
    const trend = await mountV4Trend(container, noCountIndex, initialRows);
    assert.match(container.innerHTML, /2024 Air &amp; atmosphere: 2/);
    assert.match(container.innerHTML, /2024 Soil &amp; agriculture: 1/);
    assert.match(container.innerHTML, /<th scope="row">2024<\/th><td>2<\/td><td>1<\/td><td>2<\/td>/);

    trend.update([initialRows[2]], {filtered: true});
    assert.match(container.innerHTML, /Works per year by topic \(filtered\)/);
    assert.match(container.innerHTML, /<th scope="row">2025<\/th><td>1<\/td><td>1<\/td><td>0<\/td>/);

    const fallbackIndex = {
      ids: {topic: topics, year: new Set(Array.from({length: 27}, (_, index) => String(2000 + index)))},
      counts(selection) {
        const year = Number(selection.year[0]);
        const total = year === 2024 ? 3 : 0;
        const byTopic = selection.topic?.[0] === "air" ? 2 : 1;
        return {total: selection.topic ? byTopic : total};
      }
    };
    const fallbackContainer = {classList: {add() {}}, innerHTML: ""};
    await mountV4Trend(fallbackContainer, fallbackIndex);
    assert.match(fallbackContainer.innerHTML, /<th scope="row">2024<\/th><td>3<\/td><td>1<\/td><td>2<\/td>/);
  } finally {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
    globalThis.fetch = previousFetch;
  }
}

console.log("framework_v4_trend_runtime: all checks passed");
