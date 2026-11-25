/* Site-wide search (VD-19): the header combobox, the /search results page, and the expert hero
   form. A plain script with no imports or dependencies, loaded on every page from the config head.
   The index (data/california/search_index.json, built by scripts/build_search_index.py) loads once, on the
   first focus or keystroke, and is matched in the browser. */
(function () {
  "use strict";

  var script = document.currentScript;
  var BASE = script && script.src ? new URL("../", script.src) : new URL("./", location.href);
  var INDEX_URL = new URL("data/california/search_index.json", BASE).href;
  var PER_GROUP = 5;
  var GROUP_NAMES = {
    page: "Pages",
    expert: "Authors",
    institution: "Institutions",
    topic: "Topics",
    funder: "Funders and agencies",
    term: "Glossary terms",
    resource: "Related resources"
  };
  var store = {status: "idle", types: [], items: [], promise: null};
  var uiByForm = new WeakMap();
  var counter = 0;

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (name) {
      node.setAttribute(name, attrs[name]);
    });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function normalize(text) {
    return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function words(text) {
    return text.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  }

  function compare(a, b) {
    return a < b ? -1 : a > b ? 1 : 0;
  }

  function prepare(row) {
    var label = String(row[1] || "");
    var detail = String(row[2] || "");
    var n = normalize(label);
    var all = normalize(label + " " + detail);
    return {
      type: row[0],
      label: label,
      detail: detail,
      href: new URL(row[3], BASE).href,
      n: n,
      text: all,
      labelWords: words(n),
      allWords: words(all)
    };
  }

  function loadIndex() {
    if (!store.promise) {
      store.status = "loading";
      store.promise = fetch(INDEX_URL, {credentials: "same-origin"})
        .then(function (response) {
          if (!response.ok) throw new Error("search index HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          store.types = data.types || [];
          store.items = (data.items || []).map(prepare);
          store.status = "ready";
          return store;
        })
        .catch(function (error) {
          store.status = "error";
          throw error;
        });
      // Callers handle the failure; this stops an unhandled-rejection report for the stored promise.
      store.promise.catch(function () {});
    }
    return store.promise;
  }

  function startsEach(list, terms) {
    return terms.every(function (term) {
      return list.some(function (word) {
        return word.indexOf(term) === 0;
      });
    });
  }

  function containsEach(text, terms) {
    return terms.every(function (term) {
      return text.indexOf(term) !== -1;
    });
  }

  // 0: every term starts a label word; 1: starts a word in the label or detail;
  // 2: occurs inside the label; 3: occurs inside label or detail; -1: no match.
  function rank(item, terms) {
    if (startsEach(item.labelWords, terms)) return 0;
    if (startsEach(item.allWords, terms)) return 1;
    if (containsEach(item.n, terms)) return 2;
    if (containsEach(item.text, terms)) return 3;
    return -1;
  }

  function search(query) {
    var terms = words(normalize(query).trim());
    if (!terms.length) return [];
    var hits = [];
    store.items.forEach(function (item) {
      var score = rank(item, terms);
      if (score >= 0) hits.push({item: item, rank: score});
    });
    hits.sort(function (a, b) {
      return a.item.type - b.item.type || a.rank - b.rank || compare(a.item.n, b.item.n);
    });
    return hits;
  }

  // Hits are sorted by type, so each type is one run.
  function groups(hits) {
    var out = [];
    hits.forEach(function (hit) {
      var last = out[out.length - 1];
      if (!last || last.type !== hit.item.type) {
        last = {type: hit.item.type, total: 0, rows: []};
        out.push(last);
      }
      last.total += 1;
      last.rows.push(hit.item);
    });
    return out;
  }

  function countText(count) {
    return count === 1 ? "1 result" : count + " results";
  }

  function searchUrl(query) {
    return new URL("california/search#" + new URLSearchParams({q: query}).toString(), BASE).href;
  }

  function expertsUrl(query) {
    return new URL("california/authors#" + new URLSearchParams({search: query}).toString(), BASE).href;
  }

  function formOf(target) {
    return target && target.closest ? target.closest("form[data-atlas-site-search]") : null;
  }

  function headerUi(form) {
    var state = uiByForm.get(form);
    if (state) return state;
    var input = form.querySelector("input");
    counter += 1;
    var id = "site-search-" + counter;
    var list = el("div", {
      id: id + "-listbox",
      role: "listbox",
      "aria-label": "Search results",
      class: "site-search__listbox"
    });
    list.hidden = true;
    var status = el("div", {class: "site-search__status", role: "status", "aria-live": "polite"});
    form.appendChild(list);
    form.appendChild(status);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-haspopup", "listbox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", list.id);
    input.setAttribute("autocapitalize", "off");
    input.setAttribute("spellcheck", "false");
    state = {id: id, input: input, list: list, status: status, options: [], active: -1};
    uiByForm.set(form, state);
    return state;
  }

  function option(state, label, detail, href, extraClass) {
    var node = el("div", {
      id: state.id + "-option-" + state.options.length,
      role: "option",
      "aria-selected": "false",
      class: "site-search__option" + (extraClass ? " " + extraClass : "")
    });
    node.setAttribute("data-href", href);
    node.appendChild(el("span", {class: "site-search__label"}, label));
    if (detail) node.appendChild(el("span", {class: "site-search__detail"}, detail));
    state.options.push(node);
    return node;
  }

  function clearList(state) {
    state.list.textContent = "";
    state.options = [];
    state.active = -1;
    state.input.removeAttribute("aria-activedescendant");
  }

  function hideList(state) {
    clearList(state);
    state.list.hidden = true;
    state.input.setAttribute("aria-expanded", "false");
  }

  function setActive(state, index) {
    var previous = state.options[state.active];
    if (previous) previous.setAttribute("aria-selected", "false");
    state.active = index;
    var node = state.options[index];
    if (!node) {
      state.input.removeAttribute("aria-activedescendant");
      return;
    }
    node.setAttribute("aria-selected", "true");
    state.input.setAttribute("aria-activedescendant", node.id);
    node.scrollIntoView({block: "nearest"});
  }

  function renderList(state) {
    var query = state.input.value.trim();
    var hits = search(query);
    clearList(state);
    if (!hits.length) {
      state.list.hidden = true;
      state.input.setAttribute("aria-expanded", "false");
      state.status.textContent = "No matches for " + query + ".";
      return;
    }
    groups(hits).forEach(function (group, index) {
      var headingId = state.id + "-group-" + index;
      var section = el("div", {role: "group", "aria-labelledby": headingId});
      var name = GROUP_NAMES[store.types[group.type]] || "Results";
      section.appendChild(
        el("div", {id: headingId, class: "site-search__group"}, name + " (" + group.total + ")")
      );
      group.rows.slice(0, PER_GROUP).forEach(function (item) {
        section.appendChild(option(state, item.label, item.detail, item.href));
      });
      state.list.appendChild(section);
    });
    state.list.appendChild(
      option(state, "See all " + countText(hits.length) + " on the search page", "", searchUrl(query), "site-search__all")
    );
    state.list.hidden = false;
    state.input.setAttribute("aria-expanded", "true");
    state.status.textContent = countText(hits.length) + ". Use the arrow keys to choose one.";
  }

  // Loads the index if needed, then shows the matches for what is in the box now.
  function refresh(state) {
    return loadIndex().then(
      function () {
        if (!state.input.value.trim()) hideList(state);
        else renderList(state);
      },
      function () {
        hideList(state);
        state.status.textContent = "Search is unavailable. Press Enter to search the authors list.";
      }
    );
  }

  function closeMobileSearch() {
    var header = document.getElementById("observablehq-header");
    var toggle = document.getElementById("atlas-search-toggle");
    if (header && toggle && header.classList.contains("atlas-search-open")) {
      toggle.click();
      toggle.focus();
    }
  }

  function onInput(event) {
    var form = formOf(event.target);
    if (!form) return;
    refresh(headerUi(form));
  }

  function onFocusIn(event) {
    var form = formOf(event.target);
    if (!form) return;
    headerUi(form);
    loadIndex().catch(function () {});
  }

  function onFocusOut(event) {
    var form = formOf(event.target);
    if (form) hideList(headerUi(form));
  }

  function onKeydown(event) {
    var form = formOf(event.target);
    if (!form) return;
    var state = headerUi(form);
    var open = !state.list.hidden && state.options.length > 0;
    var count = state.options.length;
    var arrow = event.key === "ArrowDown" || event.key === "ArrowUp";
    if (arrow && !open) {
      if (!state.input.value.trim()) return;
      event.preventDefault();
      refresh(state).then(function () {
        if (state.options.length) {
          setActive(state, event.key === "ArrowUp" ? state.options.length - 1 : 0);
        }
      });
    } else if (arrow) {
      event.preventDefault();
      if (event.key === "ArrowDown") setActive(state, (state.active + 1) % count);
      else setActive(state, state.active <= 0 ? count - 1 : state.active - 1);
    } else if ((event.key === "Home" || event.key === "End") && open && state.active >= 0) {
      event.preventDefault();
      setActive(state, event.key === "Home" ? 0 : count - 1);
    } else if (event.key === "Enter" && open && state.active >= 0) {
      event.preventDefault();
      window.location.assign(state.options[state.active].getAttribute("data-href"));
    } else if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        hideList(state);
      } else {
        closeMobileSearch();
      }
    }
  }

  // Keeps the input focused while an option is pressed, so the click still reaches the option.
  function onMouseDown(event) {
    if (event.target.closest && event.target.closest(".site-search__listbox")) {
      event.preventDefault();
    }
  }

  function onClick(event) {
    var node = event.target.closest ? event.target.closest(".site-search__option") : null;
    if (node && node.closest(".site-search__listbox")) {
      window.location.assign(node.getAttribute("data-href"));
    }
  }

  // Enter with no active option: the results page, or the experts list if the index failed.
  function onSubmit(event) {
    var target = event.target;
    var hero = target && target.closest ? target.closest("form[data-atlas-expert-search]") : null;
    if (hero) {
      event.preventDefault();
      var heroUrl = new URL(hero.action, location.href);
      heroUrl.hash = new URLSearchParams({search: hero.elements.search.value.trim()}).toString();
      window.location.assign(heroUrl.href);
      return;
    }
    var form = formOf(target);
    if (!form) return;
    event.preventDefault();
    var query = headerUi(form).input.value.trim();
    if (!query) {
      headerUi(form).input.focus();
      return;
    }
    loadIndex().then(
      function () {
        window.location.assign(searchUrl(query));
      },
      function () {
        window.location.assign(expertsUrl(query));
      }
    );
  }

  // The /search page: reads q from the hash (or the query string), lists every match by type.
  function initResultsPage() {
    var results = document.querySelector("[data-atlas-search-results]");
    if (!results) return;
    var status = document.querySelector("[data-atlas-search-status]");
    var form = document.querySelector("form[data-atlas-search-page]");
    var input = form ? form.querySelector("input") : null;

    function queryFromUrl() {
      var fromHash = new URLSearchParams(location.hash.replace(/^#/, "")).get("q");
      var fromSearch = new URLSearchParams(location.search).get("q");
      return String(fromHash || fromSearch || "").trim();
    }

    function show() {
      var query = queryFromUrl();
      if (input && document.activeElement !== input) input.value = query;
      results.textContent = "";
      if (!query) {
        status.textContent =
          "Type a name, institution, topic, funder or glossary term to search the Atlas.";
        return;
      }
      status.textContent = "Searching for " + query + ".";
      loadIndex().then(
        function () {
          var hits = search(query);
          if (!hits.length) {
            status.textContent = "No matches for " + query + ". Try a shorter word.";
            return;
          }
          status.textContent = countText(hits.length) + " for " + query + ".";
          groups(hits).forEach(function (group, index) {
            var headingId = "site-search-page-group-" + index;
            var section = el("section", {class: "site-search-page__group", "aria-labelledby": headingId});
            var name = GROUP_NAMES[store.types[group.type]] || "Results";
            section.appendChild(
              el("h2", {id: headingId, class: "site-search-page__heading"}, name + " (" + group.total + ")")
            );
            var list = el("ul", {class: "site-search-page__list"});
            group.rows.forEach(function (item) {
              var entry = el("li");
              entry.appendChild(el("a", {href: item.href}, item.label));
              if (item.detail) entry.appendChild(el("span", {class: "site-search-page__detail"}, item.detail));
              list.appendChild(entry);
            });
            section.appendChild(list);
            results.appendChild(section);
          });
        },
        function () {
          status.textContent =
            "The search index could not be loaded. Browse the Authors page or try again later.";
        }
      );
    }

    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var query = input.value.trim();
        if (!query) {
          input.focus();
          return;
        }
        var hash = "#" + new URLSearchParams({q: query}).toString();
        if (location.hash === hash) show();
        else location.hash = hash;
      });
    }
    window.addEventListener("hashchange", show);
    show();
  }

  function start() {
    document.querySelectorAll("form[data-atlas-site-search]").forEach(headerUi);
    document.addEventListener("input", onInput);
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    document.addEventListener("keydown", onKeydown);
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("click", onClick);
    document.addEventListener("submit", onSubmit);
    initResultsPage();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
