// SPK-4 bit-mask facet engine (Add-on A1, Appendix C). Dependency-free ES module.
// Facets: {facet: [{label, id, count}]}; facets.bin: header (magic "BMF1",
// version, N, nsets; uint32 LE) then one Uint32Array of ceil(N/32) words per id.
// Filtering: AND across facets, OR within a facet. A label's count is
// popcount(AND of the other facets' unions AND the label's set).

export const MAGIC = 'BMF1';
const HEADER_BYTES = 16;

export function popcount32(x) {
  x -= (x >>> 1) & 0x55555555;
  x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
  return Math.imul((x + (x >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24;
}

export function littleEndianHost() {
  return new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;
}

export class BitmaskIndex {
  constructor(facets, buf) {
    if (!littleEndianHost()) throw new Error('big-endian host not supported by this spike');
    const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 4));
    if (magic !== MAGIC) throw new Error(`bad magic: ${magic}`);
    const view = new DataView(buf);
    this.N = view.getUint32(8, true);
    const nsets = view.getUint32(12, true);
    this.W = Math.ceil(this.N / 32);
    this.bits = new Uint32Array(buf, HEADER_BYTES, nsets * this.W);
    this.facets = facets;
    this.names = Object.keys(facets);
    // Precomputed plan: facet -> [{label, off}] with off = word offset of its set.
    this.ids = {};
    this.plan = this.names.map((facet) => {
      this.ids[facet] = {};
      const items = facets[facet].map(({ label, id }) => {
        this.ids[facet][label] = id;
        return { label, off: id * this.W };
      });
      return { facet, items };
    });
  }

  static async load(base) {
    const [facets, buf] = await Promise.all([
      fetch(`${base}facets.json`).then((r) => r.json()),
      fetch(`${base}facets.bin`).then((r) => r.arrayBuffer()),
    ]);
    return new BitmaskIndex(facets, buf);
  }

  // sel: {facet: [label, ...]}. Returns {total, counts: {"facet|label": n}}.
  counts(sel) {
    const { W, bits } = this;
    const unions = new Map();
    for (const [facet, labels] of Object.entries(sel)) {
      if (!labels || labels.length === 0) continue;
      const u = new Uint32Array(W);
      for (const label of labels) {
        const off = this.ids[facet][label] * W;
        for (let i = 0; i < W; i++) u[i] |= bits[off + i];
      }
      unions.set(facet, u);
    }
    let total = this.N;
    if (unions.size > 0) {
      const all = new Uint32Array(W).fill(0xffffffff);
      for (const u of unions.values()) for (let i = 0; i < W; i++) all[i] &= u[i];
      total = 0;
      for (let i = 0; i < W; i++) total += popcount32(all[i]);
    }
    const counts = {};
    for (const { facet, items } of this.plan) {
      const base = new Uint32Array(W).fill(0xffffffff);
      for (const [g, u] of unions) {
        if (g === facet) continue;
        for (let i = 0; i < W; i++) base[i] &= u[i];
      }
      for (const { label, off } of items) {
        let c = 0;
        for (let i = 0; i < W; i++) c += popcount32(base[i] & bits[off + i]);
        counts[`${facet}|${label}`] = c;
      }
    }
    return { total, counts };
  }
}
