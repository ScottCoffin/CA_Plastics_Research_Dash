---
title: SPK-2(a) Parquet probe
sidebar: false
toc: false
---

# SPK-2(a): DuckDB 1.1.1 zstd Parquet via FileAttachment

```js
const db = DuckDBClient.of({fx: FileAttachment("data/zstd_default.parquet")});
```

```js
const expected = (await (await fetch("/data/parquet_expected.json")).json()).expected;
```

```js
await db.query("SET TimeZone='UTC'");
```

```js
const checks = {
  count: "SELECT CAST(COUNT(*) AS VARCHAR) AS v FROM fx",
  ecotox_contains: "SELECT CAST(COUNT(*) FILTER (WHERE list_contains(tags, 'ecotox')) AS VARCHAR) AS v FROM fx",
  unnest_tags: "SELECT CAST(COUNT(*) AS VARCHAR) AS v FROM (SELECT UNNEST(tags) AS t FROM fx)",
  max_published: "SELECT CAST(MAX(published) AS VARCHAR) AS v FROM fx",
  max_updated: "SELECT CAST(MAX(updated) AS VARCHAR) AS v FROM fx"
};
```

```js
const runChecks = async () => {
  const out = {};
  for (const [k, sql] of Object.entries(checks)) {
    const r = await db.queryRow(sql);
    out[k] = {got: String(r.v), want: expected[k], pass: String(r.v) === expected[k]};
  }
  out.all_pass = Object.values(out).every((c) => c.pass === true);
  return out;
};
```

```js
const spk2 = await runChecks();
```

```js
{
  window.__spk2 = spk2;
  window.__spk2Done = true;
}
```

```js
html`<pre id="spk2-result">${JSON.stringify(spk2, null, 1)}</pre>`
```
