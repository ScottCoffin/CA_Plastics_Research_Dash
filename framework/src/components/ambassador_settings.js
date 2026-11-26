// Notification settings (AMB-1 front end slice 3b; docs/AMBASSADORS_SPEC.md "Front end slice 3b").
// The signed-in ambassador chooses the reminder and news emails. The workspace mounts this screen and passes its
// ctx: {api, errorText, say}. api is the sign-up's api() (credentials included) and is the only way to reach the
// Worker: GET /me/notifications, then one POST per switch holding just that key. Each switch saves on change; there
// is no Save button. Preferences live in the mount closure and on the server; nothing is kept in browser storage.
// Pure helpers are exported for tests/framework_ambassador_settings_runtime.mjs and touch no DOM at import time.

export const PREF_KEYS = ["reminders", "product_news"];
/** Defaults the Worker uses when the ambassador has never changed a switch. */
export const PREF_DEFAULTS = Object.freeze({reminders: true, product_news: false});
const SWITCH_LABELS = {
  reminders: "Send me a reminder when I have open tasks",
  product_news: "Send me occasional news about new regions and features",
};
const CRUMB = '<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p>';

/** Notification preferences from the Worker's notifications object; defaults for missing or non-boolean values. */
export function prefsFrom(data) {
  const src = data && typeof data === "object" ? data : {};
  return {
    reminders: typeof src.reminders === "boolean" ? src.reminders : PREF_DEFAULTS.reminders,
    product_news: typeof src.product_news === "boolean" ? src.product_news : PREF_DEFAULTS.product_news,
  };
}

/** The POST body for one switch: {[key]: value} for a known key and a boolean value, otherwise null. */
export function prefsBody(key, value) {
  if (!PREF_KEYS.includes(key) || typeof value !== "boolean") return null;
  return {[key]: value};
}

/** One plain sentence for the saved state, e.g. "Reminders are on. News is off." */
export function settingsSummary(prefs) {
  const p = prefsFrom(prefs);
  return `Reminders are ${p.reminders ? "on" : "off"}. News is ${p.product_news ? "on" : "off"}.`;
}

const onOff = (on) => (on ? "On" : "Off");

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function switchHTML(key, prefs) {
  const on = prefs[key];
  return (
    `<label class="ns-switch"><input type="checkbox" role="switch" data-ns-key="${key}"${on ? " checked" : ""}>` +
    `<span class="ns-track" aria-hidden="true"></span><span class="ns-label">${SWITCH_LABELS[key]}</span>` +
    `<span class="ns-state" data-ns-state="${key}">${onOff(on)}</span></label>`
  );
}

function settingsHTML(prefs) {
  return (
    `<fieldset class="ns-group"><legend>Reminders</legend>${switchHTML("reminders", prefs)}` +
    `<p class="hint">Sent only while tasks are open. Reminders pause after three unanswered reminders until you come back.</p>` +
    `<p class="ns-fixed"><b>How often:</b> every two weeks. This is fixed.</p></fieldset>` +
    `<fieldset class="ns-group"><legend>News about Plastiverse</legend>${switchHTML("product_news", prefs)}</fieldset>`
  );
}

/**
 * Mount the notification settings screen into host. Sets the static screen synchronously, then loads the
 * preferences. ctx: {api, errorText(code) -> plain text, say(text) -> live announcement}.
 */
export function mountSettings(host, ctx) {
  host.innerHTML =
    `${CRUMB}<h2 tabindex="-1">Notification settings</h2>` +
    `<p class="lede">Choose what we email you about. Sign-in links are always sent and cannot be switched off.</p>` +
    `<div data-ns-body><p class="hint" role="status">Loading your settings…</p></div>` +
    `<div data-ns-msg></div>`;
  const bodyEl = host.querySelector("[data-ns-body]");
  const msgEl = host.querySelector("[data-ns-msg]");
  let prefs = {...PREF_DEFAULTS};

  // Re-sets every enabled switch from prefs. A switch that is saving keeps its "Saving…" state until its own answer.
  const paintAll = () => {
    for (const input of host.querySelectorAll("input[data-ns-key]")) {
      if (input.disabled) continue;
      const key = input.dataset.nsKey;
      input.checked = prefs[key];
      const state = host.querySelector(`[data-ns-state="${key}"]`);
      if (state) state.textContent = onOff(prefs[key]);
      input.closest(".ns-switch")?.classList.remove("is-saving");
    }
  };

  const showError = (code) => {
    msgEl.replaceChildren(el("p", "ws-error", ctx.errorText(code)));
  };

  const load = async () => {
    bodyEl.replaceChildren(el("p", "hint", "Loading your settings…"));
    const res = await ctx.api("/me/notifications");
    if (!host.contains(bodyEl)) return; // the screen was replaced while loading
    if (res.ok && res.data && typeof res.data.notifications === "object") {
      prefs = prefsFrom(res.data.notifications);
      bodyEl.innerHTML = settingsHTML(prefs);
      return;
    }
    const retry = el("button", "btn", "Try again");
    retry.type = "button";
    retry.dataset.nsAction = "retry";
    bodyEl.replaceChildren(el("p", "ws-error", ctx.errorText(res.error)), retry);
  };

  const save = async (input) => {
    const body = prefsBody(input.dataset.nsKey, input.checked);
    if (!body) return;
    msgEl.replaceChildren();
    input.disabled = true;
    const state = host.querySelector(`[data-ns-state="${input.dataset.nsKey}"]`);
    if (state) state.textContent = "Saving…";
    input.closest(".ns-switch")?.classList.add("is-saving");
    const res = await ctx.api("/me/notifications", {method: "POST", body});
    input.disabled = false;
    if (res.ok && res.data && typeof res.data.notifications === "object") {
      prefs = prefsFrom(res.data.notifications);
      paintAll();
      ctx.say(`Saved. ${settingsSummary(prefs)}`);
    } else {
      paintAll(); // reverts this switch to the last saved value
      showError(res.error);
    }
  };

  // Listeners are set as properties on host so that a second mount on the same host does not add a second one.
  host.onchange = (event) => {
    const input = event.target;
    if (input && input.dataset && input.dataset.nsKey) save(input);
  };
  host.onclick = (event) => {
    const button = event.target.closest?.('[data-ns-action="retry"]');
    if (button) load();
  };

  return load();
}
