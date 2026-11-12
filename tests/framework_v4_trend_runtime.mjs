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

console.log("framework_v4_trend_runtime: all checks passed");
