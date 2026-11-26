// Runtime checks for the notification settings helpers (AMB-1 slice 3b). The pure helpers live in
// framework/src/components/ambassador_settings.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {PREF_DEFAULTS, prefsBody, prefsFrom, settingsSummary} from "../framework/src/components/ambassador_settings.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

check("defaults are reminders on and news off", () => {
  assert.deepEqual(PREF_DEFAULTS, {reminders: true, product_news: false});
  assert.deepEqual(prefsFrom(undefined), {reminders: true, product_news: false});
  assert.deepEqual(prefsFrom(null), {reminders: true, product_news: false});
  assert.deepEqual(prefsFrom({}), {reminders: true, product_news: false});
});

check("prefsFrom keeps booleans and replaces junk with the defaults", () => {
  assert.deepEqual(prefsFrom({reminders: false, product_news: true}), {reminders: false, product_news: true});
  assert.deepEqual(prefsFrom({reminders: "no", product_news: 1}), {reminders: true, product_news: false});
  assert.deepEqual(prefsFrom({reminders: null}), {reminders: true, product_news: false});
  assert.deepEqual(prefsFrom("on"), {reminders: true, product_news: false});
  assert.deepEqual(prefsFrom([false]), {reminders: true, product_news: false});
});

check("prefsBody returns one key for each known key and a boolean", () => {
  assert.deepEqual(prefsBody("reminders", false), {reminders: false});
  assert.deepEqual(prefsBody("product_news", true), {product_news: true});
});

check("prefsBody returns null for an unknown key or a non-boolean value", () => {
  assert.equal(prefsBody("badge", true), null);
  assert.equal(prefsBody("__proto__", true), null);
  assert.equal(prefsBody("reminders", "true"), null);
  assert.equal(prefsBody("product_news", 0), null);
  assert.equal(prefsBody("reminders", undefined), null);
});

check("settingsSummary is one plain sentence", () => {
  assert.equal(settingsSummary({reminders: true, product_news: false}), "Reminders are on. News is off.");
  assert.equal(settingsSummary({reminders: false, product_news: true}), "Reminders are off. News is on.");
  assert.equal(settingsSummary(undefined), "Reminders are on. News is off.");
});

console.log(`${passed} notification settings checks passed`);
