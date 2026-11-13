// Evidence heatmap for the Evidence Map page (EV-HEATMAP). Topic x matrix, or topic x 5-year period.
// Hand-built HTML table of buttons; no chart library. Rows are passed in already filtered by the page.
// Cells and topic names are multi-select: the selected works narrow the publication table (onSelect).
import "./shared/topics.js";
import {
  cellKey,
  colorFor,
  escapeHtml,
  heatmapCells,
  NO_MATRIX_KEY,
  pruneSelection,
  rowSelected,
  selectedIds,
  textInk,
  toggleCell,
  toggleRow
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

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
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

function tableHtml(model, mode, selected) {
  const head = model.cols
    .map((col) => `<th scope="col">${escapeHtml(colLabel(col))}</th>`)
    .join("");
  const body = model.rows
    .map((row) => {
      const hasWorks = model.cells.some((c) => c.row === row && c.count > 0);
      const rowButton =
        `<button type="button" class="ev-heatmap-rowbtn" data-row="${escapeHtml(row)}" ` +
        `aria-pressed="${rowSelected(selected, model, row)}"${hasWorks ? "" : " disabled"}>${escapeHtml(labelFor(row))}</button>`;
      const cells = model.cols
        .map((col) => {
          const cell = model.cells.find((c) => c.row === row && c.col === col.key);
          const fill = colorFor(cell.count, model.max);
          const ink = textInk(fill);
          const name = `${labelFor(row)}, ${colLabel(col)}: ${plural(cell.count, "work", "works")}`;
          if (!cell.count) {
            return (
              `<td><button type="button" class="ev-heatmap-cell" data-row="${escapeHtml(row)}" ` +
              `data-col="${escapeHtml(col.key)}" style="background:${fill};color:${ink}" disabled ` +
              `aria-label="${escapeHtml(name)}">${cell.count}</button></td>`
            );
          }
          const pressed = selected.has(cellKey(row, col.key));
          return (
            `<td><button type="button" class="ev-heatmap-cell" data-row="${escapeHtml(row)}" ` +
            `data-col="${escapeHtml(col.key)}" style="background:${fill};color:${ink}" ` +
            `aria-pressed="${pressed}" aria-label="${escapeHtml(name)}">${cell.count}</button></td>`
          );
        })
        .join("");
      return `<tr><th scope="row">${rowButton}</th>${cells}</tr>`;
    })
    .join("");
  const caption = mode === "topic-matrix" ? "Works by topic and matrix" : "Works by topic and five-year period";
  return (
    `<div class="ev-heatmap-scroll" role="region" aria-label="${escapeHtml(caption)} grid" tabindex="0">` +
    `<table class="ev-heatmap-table"><caption class="ev-heatmap-sr">${escapeHtml(caption)}</caption>` +
    `<thead><tr><th scope="col">Topic</th>${head}</tr></thead><tbody>${body}</tbody></table></div>`
  );
}

// onSelect(ids) runs on every selection change and on every update(rows): ids are the works in the
// selected cells, and onSelect(null) means nothing is selected (the table then shows every work).
export function mountHeatmap(container, {onSelect = () => {}} = {}) {
  if (!container) throw new Error("mountHeatmap needs a container element");
  container.classList.add("ev-heatmap");
  let mode = "topic-matrix";
  let rows = [];
  let model = null;
  let selected = new Set();

  container.innerHTML =
    '<div class="ev-heatmap-toggle" role="group" aria-label="Heatmap view">' +
    Object.entries(MODE_LABELS)
      .map(
        ([key, text]) =>
          `<button type="button" data-mode="${key}" aria-pressed="${key === mode}">${escapeHtml(text)}</button>`
      )
      .join("") +
    "</div>" +
    '<div class="ev-heatmap-selection">' +
    '<p class="ev-heatmap-status" role="status" aria-live="polite"></p>' +
    '<button type="button" class="ev-heatmap-clear" disabled>Clear selection</button>' +
    "</div>" +
    '<div class="ev-heatmap-body"></div>';
  const body = container.querySelector(".ev-heatmap-body");
  const status = container.querySelector(".ev-heatmap-status");
  const clearButton = container.querySelector(".ev-heatmap-clear");

  // Updates pressed state and the status line in place, so keyboard focus stays on the pressed button.
  function refreshSelection() {
    const count = selected.size;
    status.textContent = count
      ? `Table limited to ${plural(count, "selected cell", "selected cells")} (${plural(selectedIds(model, selected).length, "work", "works")}).`
      : "";
    clearButton.disabled = count === 0;
    for (const button of container.querySelectorAll("button.ev-heatmap-cell:not(:disabled)")) {
      button.setAttribute("aria-pressed", String(selected.has(cellKey(button.dataset.row, button.dataset.col))));
    }
    for (const button of container.querySelectorAll("button.ev-heatmap-rowbtn:not(:disabled)")) {
      button.setAttribute("aria-pressed", String(rowSelected(selected, model, button.dataset.row)));
    }
  }

  function publish() {
    onSelect(selected.size ? selectedIds(model, selected) : null);
  }

  function setSelected(next) {
    selected = next;
    refreshSelection();
    publish();
  }

  function render() {
    if (!rows.length) {
      model = null;
      body.innerHTML = `<p class="ev-heatmap-empty" role="status">${escapeHtml(EMPTY_TEXT)}</p>`;
    } else {
      model = heatmapCells(rows, mode);
      body.innerHTML =
        tableHtml(model, mode, selected) +
        legendHtml(model.max) +
        `<p class="ev-heatmap-note">${escapeHtml(CAPTION)}</p>`;
    }
    // A selected cell that no longer has works (after a filter change) is dropped. The works behind a
    // surviving cell can change too, so the selection is published on every render, not only on a drop.
    selected = pruneSelection(selected, model);
    refreshSelection();
    publish();
  }

  container.querySelector(".ev-heatmap-toggle").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-mode]");
    if (!button || button.dataset.mode === mode) return;
    mode = button.dataset.mode;
    selected = new Set();
    for (const other of container.querySelectorAll(".ev-heatmap-toggle button")) {
      other.setAttribute("aria-pressed", String(other === button));
    }
    render();
  });

  body.addEventListener("click", (event) => {
    if (!model) return;
    const cellButton = event.target.closest("button.ev-heatmap-cell");
    if (cellButton) {
      if (!cellButton.disabled) setSelected(toggleCell(selected, cellKey(cellButton.dataset.row, cellButton.dataset.col)));
      return;
    }
    const rowButton = event.target.closest("button.ev-heatmap-rowbtn");
    if (rowButton && !rowButton.disabled) setSelected(toggleRow(selected, model, rowButton.dataset.row));
  });

  clearButton.addEventListener("click", () => {
    if (selected.size) setSelected(new Set());
  });

  render();
  return {
    update(nextRows) {
      rows = Array.isArray(nextRows) ? nextRows : [];
      render();
    }
  };
}
