/* AtlasFacets: dependency-free bit-set facet engine for the at4.v1 serving bundle (Appendix C).
 *
 * Filtering is AND across facets and OR within a facet. A label's count is
 * popcount(AND of the other facets' unions AND extra bits AND the label's set).
 * Text search is a bit-set too: pass searchBits(q) as the extra bits.
 *
 * Loads as a classic browser script (window.AtlasFacets) or from node (module.exports).
 */
(function () {
  'use strict';

  const MAGIC = 'BMF1';
  const VERSION = 1;
  const HEADER_BYTES = 16;

  function popcount32(x) {
    x -= (x >>> 1) & 0x55555555;
    x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
    return Math.imul((x + (x >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24;
  }

  function littleEndianHost() {
    return new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;
  }

  function parseJson(value) {
    return typeof value === 'string' ? JSON.parse(value) : value;
  }

  function toArrayBuffer(value) {
    if (value instanceof ArrayBuffer) return value;
    if (ArrayBuffer.isView(value)) {
      return value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
    }
    throw new Error('facets.bin must be an ArrayBuffer or typed array');
  }

  async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`fetch failed: ${url} (${response.status})`);
    return response.json();
  }

  class BitmaskIndex {
    constructor(facetsJson, arrayBuffer, worksIndexJson) {
      if (!littleEndianHost()) throw new Error('big-endian host not supported by this facet engine');
      const buf = toArrayBuffer(arrayBuffer);
      if (buf.byteLength < HEADER_BYTES) throw new Error('facets.bin is shorter than its header');
      const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 4));
      if (magic !== MAGIC) throw new Error(`bad magic: ${magic}`);
      const view = new DataView(buf);
      const version = view.getUint32(4, true);
      if (version !== VERSION) throw new Error(`unsupported facets.bin version: ${version}`);
      this.N = view.getUint32(8, true);
      const nsets = view.getUint32(12, true);
      this.W = Math.ceil(this.N / 32);
      if (buf.byteLength !== HEADER_BYTES + nsets * this.W * 4) {
        throw new Error('facets.bin length does not match its header');
      }
      this.bits = new Uint32Array(buf, HEADER_BYTES, nsets * this.W);

      const works = parseJson(worksIndexJson);
      if (works.work_ids.length !== this.N) throw new Error('works_index.json does not match facets.bin');
      this.workIds = works.work_ids;
      this.titles = works.titles.map((t) => (t || '').toLowerCase());

      this.facets = parseJson(facetsJson);
      this.names = Object.keys(this.facets);
      this.ids = {};
      this.plan = this.names.map((facet) => {
        this.ids[facet] = new Map();
        const items = this.facets[facet].map(({ label, id }) => {
          this.ids[facet].set(label, id);
          return { label, off: id * this.W };
        });
        return { facet, items };
      });
    }

    static async load(base) {
      const [facets, buf, works] = await Promise.all([
        fetchJson(`${base}facets.json`),
        fetch(`${base}facets.bin`).then((r) => {
          if (!r.ok) throw new Error(`fetch failed: ${base}facets.bin (${r.status})`);
          return r.arrayBuffer();
        }),
        fetchJson(`${base}works_index.json`),
      ]);
      return new BitmaskIndex(facets, buf, works);
    }

    // sel: {facet: [label, ...]}. Returns the union bit-set per selected facet.
    _unions(sel) {
      const unions = new Map();
      for (const [facet, labels] of Object.entries(sel || {})) {
        if (!labels || labels.length === 0) continue;
        const byLabel = this.ids[facet];
        if (!byLabel) throw new Error(`unknown facet: ${facet}`);
        const u = new Uint32Array(this.W);
        for (const label of labels) {
          const id = byLabel.get(label);
          if (id === undefined) throw new Error(`unknown label: ${facet}|${label}`);
          const off = id * this.W;
          for (let i = 0; i < this.W; i++) u[i] |= this.bits[off + i];
        }
        unions.set(facet, u);
      }
      return unions;
    }

    // AND of all unions (except `exclude`) and the extra bits. Null means no constraint.
    _intersect(unions, extra, exclude) {
      let out = null;
      const and = (arr) => {
        if (out === null) out = new Uint32Array(arr);
        else for (let i = 0; i < this.W; i++) out[i] &= arr[i];
      };
      for (const [facet, u] of unions) if (facet !== exclude) and(u);
      if (extra) and(extra);
      return out;
    }

    _checkExtra(extraBits) {
      if (extraBits && extraBits.length !== this.W) throw new Error('extra bit-set has the wrong length');
      return extraBits || null;
    }

    // Returns {total, counts: {"facet|label": n}}.
    counts(sel, extraBits) {
      const { W, bits } = this;
      const unions = this._unions(sel);
      const extra = this._checkExtra(extraBits);
      const selected = this._intersect(unions, extra, null);
      let total = this.N;
      if (selected !== null) {
        total = 0;
        for (let i = 0; i < W; i++) total += popcount32(selected[i]);
      }
      const counts = {};
      for (const { facet, items } of this.plan) {
        const base = this._intersect(unions, extra, facet);
        for (const { label, off } of items) {
          let c = 0;
          if (base === null) {
            for (let i = 0; i < W; i++) c += popcount32(bits[off + i]);
          } else {
            for (let i = 0; i < W; i++) c += popcount32(base[i] & bits[off + i]);
          }
          counts[`${facet}|${label}`] = c;
        }
      }
      return { total, counts };
    }

    // Bit-set of works whose lowercased title contains every whitespace-separated token.
    searchBits(query) {
      const tokens = String(query == null ? '' : query).toLowerCase().split(/\s+/).filter(Boolean);
      const out = new Uint32Array(this.W);
      for (let i = 0; i < this.N; i++) {
        const title = this.titles[i];
        let ok = true;
        for (const token of tokens) {
          if (title.indexOf(token) < 0) {
            ok = false;
            break;
          }
        }
        if (ok) out[i >>> 5] |= (1 << (i & 31)) >>> 0;
      }
      return out;
    }

    // Work ids (index order) selected by sel AND extra bits.
    selectedIds(sel, extraBits) {
      const selected = this._intersect(this._unions(sel), this._checkExtra(extraBits), null);
      if (selected === null) return this.workIds.slice();
      const ids = [];
      for (let i = 0; i < this.N; i++) {
        if (selected[i >>> 5] & (1 << (i & 31))) ids.push(this.workIds[i]);
      }
      return ids;
    }
  }

  const api = { MAGIC, popcount32, littleEndianHost, BitmaskIndex };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.AtlasFacets = api;
})();
