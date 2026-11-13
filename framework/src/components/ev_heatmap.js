// Evidence heatmap for the Evidence Map page (EV-HEATMAP). Topic x matrix, or topic x 5-year period.
// Hand-built HTML table of buttons; no chart library. Rows are passed in already filtered by the page.
import "./shared/topics.js";
import {
  colorFor,
  escapeHtml,
  heatmapCells,
  NO_MATRIX_KEY,
  textInk
} from "./ev_heatmap_model.js";

const MODE_LABELS = {"topic-matrix": "Topic × matrix", "topic-year": "Topic × time"};
const CAPTION =
  "Works can carry several tags, so cells overlap and do not sum to the total. " +
  "Tags come from keyword rules and are provisional.";
const EMPTY_TEXT = "No works match the current filters.";

function labelFor(tag) {
  const api = window.AtlasTopics;
  return api ? api.label(tag) : String(tag);
}

function colLabel(col) {
  if (col.key === NO_MATRIX_KEY) return col.label;
  return String(col.key).startsWith("matrix:") ? labelFor(col.key) : col.label;
}

function plural(count) {
  return `${count} ${count === 1 ? "work" : "works"}`;
}

function legendHtml(max) {
  const low = colorFor(0, max);
  const high = colorFor(max, max);
  return (
    '<div class="ev-heatmap-legend" aria-hidden="true">' +
    `<span class="ev-heatmap-swatch" style="background:${low}"></span><span>0</span>` +
    `<span class="ev-heatmap-swatch" style="background:${high}"></span><span>${max}</span>` +
    "<span>works per cell</span></div>"
  );
}

function tableHtml(model, mode) {
  const head = model.cols
    .map((col) => `<th scope="col">${escapeHtml(colLabel(col))}</th>`)
    .join("");
  const body = model.rows
    .map((row) => {
      const cells = model.cols
        .map((col) => {
          const cell = model.cells.find((c) => c.row === row && c.col === col.key);
          const fill = colorFor(cell.count, model.max);
          const ink = textInk(fill);
          const name = `${labelFor(row)}, ${colLabel(col)}: ${plural(cell.count)}`;
          return (
            `<td><button type="button" class="ev-heatmap-cell" data-row="${escapeHtml(row)}" ` +
            `data-col="${escapeHtml(col.key)}" style="background:${fill};color:${ink}"` +
            `${cell.count ? "" : " disabled"} aria-label="${escapeHtml(name)}">${cell.count}</button></td>`
          );
        })
        .join("");
      return `<tr><th scope="row">${escapeHtml(labelFor(row))}</th>${cells}</tr>`;
    })
    .join("");
  const caption = mode === "topic-matrix" ? "Works by topic and matrix" : "Works by topic and five-year period";
  return (
    `<div class="ev-heatmap-scroll" role="region" aria-label="${escapeHtml(caption)} grid" tabindex="0">` +
    `<table class="ev-heatmap-table"><caption class="ev-heatmap-sr">${escapeHtml(caption)}</caption>` +
    `<thead><tr><th scope="col">Topic</th>${head}</tr></thead><tbody>${body}</tbody></table></div>`
  );
}

export function mountHeatmap(container, {onCell = () => {}} = {}) {
  if (!container) throw new Error("mountHeatmap needs a container element");
  container.classList.add("ev-heatmap");
  let mode = "topic-matrix";
  let rows = [];
  let model = null;

  container.innerHTML =
    '<div class="ev-heatmap-toggle" role="group" aria-label="Heatmap view">' +
    Object.entries(MODE_LABELS)
      .map(
        ([key, text]) =>
          `<button type="button" data-mode="${key}" aria-pressed="${key === mode}">${escapeHtml(text)}</button>`
      )
      .join("") +
    "</div>" +
    '<div class="ev-heatmap-body"></div>';
  const body = container.querySelector(".ev-heatmap-body");

  function render() {
    if (!rows.length) {
      model = null;
      body.innerHTML = `<p class="ev-heatmap-empty" role="status">${escapeHtml(EMPTY_TEXT)}</p>`;
      return;
    }
    model = heatmapCells(rows, mode);
    body.innerHTML =
      tableHtml(model, mode) +
      legendHtml(model.max) +
      `<p class="ev-heatmap-note">${escapeHtml(CAPTION)}</p>`;
  }

  container.querySelector(".ev-heatmap-toggle").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-mode]");
    if (!button || button.dataset.mode === mode) return;
    mode = button.dataset.mode;
    for (const other of container.querySelectorAll(".ev-heatmap-toggle button")) {
      other.setAttribute("aria-pressed", String(other === button));
    }
    render();
  });

  body.addEventListener("click", (event) => {
    const button = event.target.closest("button.ev-heatmap-cell");
    if (!button || button.disabled || !model) return;
    const cell = model.cells.find((c) => c.row === button.dataset.row && c.col === button.dataset.col);
    if (!cell || cell.count === 0) return;
    const col = model.cols.find((c) => c.key === cell.col);
    onCell({title: `${labelFor(cell.row)} · ${colLabel(col)}`, ids: [...cell.ids]});
  });

  render();
  return {
    update(nextRows) {
      rows = Array.isArray(nextRows) ? nextRows : [];
      render();
    }
  };
}
