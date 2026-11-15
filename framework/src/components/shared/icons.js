const SVG_NS = "http://www.w3.org/2000/svg";

// Atlas-drawn line symbols from docs/design/style_tile.html. Keep these paths local and
// constant: icon() only accepts names from this map and never inserts caller text as markup.
const ICONS = Object.freeze({
  home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h5v-6h3v6h5V10"/>',
  person: '<circle cx="12" cy="8" r="3.6"/><path d="M4.5 20.5c.6-3.9 3.6-6 7.5-6s6.9 2.1 7.5 6"/>',
  network: '<circle cx="5.5" cy="6.5" r="2.4"/><circle cx="18.5" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.6"/><path d="M7.7 7.4 10.6 15.7M16.6 7.5 13.3 15.8M8 6.4h8"/>',
  building: '<path d="M3 20.5h18M4.5 9.5 12 4l7.5 5.5M6 10v10.5M10 10v10.5M14 10v10.5M18 10v10.5"/>',
  drop: '<path d="M12 3.5s-5.5 6.4-5.5 10.3a5.5 5.5 0 0 0 11 0C17.5 9.9 12 3.5 12 3.5Z"/><path d="M9.5 14.5c.3 1.3 1.3 2.2 2.6 2.4"/>',
  coins: '<ellipse cx="12" cy="6.5" rx="6.5" ry="2.8"/><path d="M5.5 6.5v5c0 1.6 2.9 2.8 6.5 2.8s6.5-1.2 6.5-2.8v-5M5.5 11.5v5c0 1.6 2.9 2.8 6.5 2.8s6.5-1.2 6.5-2.8v-5"/>',
  grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.4"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.4"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.4"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.4"/>',
  scale: '<path d="M12 4v16.5M7 20.5h10M5 7.5h14M12 4l-1.2 3.5M7.5 7.5 4.5 14a3 3 0 0 0 6 0Zm9 0-3 6.5a3 3 0 0 0 6 0Z"/>',
  link: '<path d="M10 14a4.2 4.2 0 0 0 6 0l3-3a4.2 4.2 0 0 0-6-6l-1 1"/><path d="M14 10a4.2 4.2 0 0 0-6 0l-3 3a4.2 4.2 0 0 0 6 6l1-1"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.6v.2"/>',
  book: '<path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v15H7.5A2.5 2.5 0 0 0 5 20.5Z"/><path d="M5 20.5A2.5 2.5 0 0 1 7.5 18H19v3H7.5"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  download: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/>',
  filter: '<path d="M4 5.5h16l-6.2 7.3v5.4l-3.6 1.8v-7.2Z"/>',
  x: '<path d="m7 7 10 10M17 7 7 17"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  alert: '<path d="M12 4 2.8 19.5h18.4Z"/><path d="M12 10v4.5M12 17v.2"/>',
  spark: '<path d="M12 3.5v4M12 16.5v4M3.5 12h4M16.5 12h4M6 6l2.6 2.6M15.4 15.4 18 18M18 6l-2.6 2.6M8.6 15.4 6 18"/>',
  tools: '<path d="M4 20h16M6 20v-4l9-9 4 4-9 9"/><path d="m13 9 2 2"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  external: '<path d="M13 5h6v6"/><path d="m19 5-8 8"/><path d="M17 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h5"/>',
});

function createSvgElement(name) {
  return document.createElementNS(SVG_NS, name);
}

/** Inject the hidden symbol sprite once into this document. */
export function injectIconSprite(root = document.body) {
  const existing = document.getElementById("atlas-icon-sprite");
  if (existing) return existing;

  const sprite = createSvgElement("svg");
  sprite.id = "atlas-icon-sprite";
  sprite.setAttribute("class", "atlas-icon-sprite");
  sprite.setAttribute("aria-hidden", "true");
  sprite.setAttribute("focusable", "false");

  for (const [name, markup] of Object.entries(ICONS)) {
    const symbol = createSvgElement("symbol");
    symbol.id = `i-${name}`;
    symbol.setAttribute("viewBox", "0 0 24 24");
    // `markup` is selected only from the module's fixed, reviewed symbol table.
    symbol.innerHTML = markup;
    sprite.append(symbol);
  }

  root.prepend(sprite);
  return sprite;
}

/** Return a decorative icon, or a named image when `label` is supplied. */
export function icon(name, { label } = {}) {
  if (!Object.hasOwn(ICONS, name)) {
    throw new RangeError(`Unknown Atlas icon: ${String(name)}`);
  }

  injectIconSprite();
  const svg = createSvgElement("svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("focusable", "false");

  const accessibleLabel = typeof label === "string" ? label.trim() : "";
  if (accessibleLabel) {
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", accessibleLabel);
  } else {
    svg.setAttribute("aria-hidden", "true");
  }

  const use = createSvgElement("use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}
