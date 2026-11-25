// Runtime check for the /explore zoom helpers in framework/src/components/explore.js, run by
// tests/test_explore_zoom.py. Pure functions only: no network, no DOM.
import assert from "node:assert/strict";
import {
  ZOOM_MAX,
  clampView,
  clampWidth,
  frameXY,
  minimumBox,
  frameExtent,
  wheelFactor,
  zoomView,
  dragMode,
  nextActive,
  TOUCH_HINT,
  WHEEL_HINT,
  wheelZooms,
} from "../framework/src/components/explore.js";

const FW = 1000;
const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

// Zoom bounds: 1x is the frame width, ZOOM_MAX is the closest zoom.
assert.equal(ZOOM_MAX, 60);
assert.equal(clampWidth(5000, FW), FW, "zooming out past 1x stops at the frame");
close(clampWidth(0.001, FW), FW / 60, 1e-9);
assert.equal(clampWidth(120, FW), 120, "the search zoom for a place (120 units wide) is inside the bounds");

// Wheel: one notch is a small step, the sign sets the direction, and an extreme delta is capped.
assert.equal(wheelFactor(0), 1);
assert.ok(wheelFactor(100) < 1 && wheelFactor(-100) > 1, "scroll down zooms out, up zooms in");
close(wheelFactor(100) * wheelFactor(-100), 1, 1e-12);
assert.equal(wheelFactor(1e6), wheelFactor(200), "a huge wheel delta is capped");
close(wheelFactor(3, 1), wheelFactor(48), 1e-12); // three lines are 48 pixels
close(wheelFactor(1, 2), wheelFactor(400), 1e-12); // one page is 400 pixels
assert.ok(wheelFactor(4) > 0.9 && wheelFactor(4) < 1, "a typical trackpad step is gentle");

// Zoom keeps the point under the cursor fixed on screen: its fraction across the view is unchanged.
const world = [0, 0, 1000, 520];
const [x2, y2, w2, h2] = zoomView(world, 2, 250, 130, FW);
close(w2, 500); close(h2, 260); close(x2, 125); close(y2, 65);
close((250 - x2) / w2, 250 / 1000, 1e-12);
close((130 - y2) / h2, 130 / 520, 1e-12);

// Repeated zoom in stops at ZOOM_MAX, and zooming out again returns to the frame.
let v = world.slice();
for (let i = 0; i < 40; i++) v = zoomView(v, 1.6, 500, 260, FW);
close(v[2], FW / ZOOM_MAX, 1e-9);
assert.ok(Math.abs(v[3] / v[2] - 520 / 1000) < 1e-9, "the aspect is kept");
for (let i = 0; i < 40; i++) v = zoomView(v, 1 / 1.6, 500, 260, FW);
close(v[2], FW, 1e-9);

// A view is kept inside the frame: past an edge it is pushed back, and a view wider than the frame is centred.
const frame = [0, 0, 1000, 520];
assert.deepEqual(clampView([-50, 10, 200, 100], frame), [0, 10, 200, 100]);
assert.deepEqual(clampView([900, 430, 200, 100], frame), [800, 420, 200, 100]);
assert.deepEqual(clampView([10, 10, 1200, 600], frame), [-100, -40, 1200, 600]);

// Search zoom to a place and then user zoom stay consistent: a minimum box around Palau is inside the bounds.
const palau = frameExtent(minimumBox([134.2, 7.2, 134.8, 7.8]));
const palauW = palau[2] - palau[0];
assert.ok(palauW > 0 && palauW < 60, `Palau's minimum box is small (${palauW})`);
assert.ok(clampWidth(Math.max(palauW * 1.3, 120), FW) >= FW / ZOOM_MAX);
const [pxPalau] = frameXY(134.5, 7.5);
assert.ok(pxPalau > 800 && pxPalau < 950, `Palau sits in the Pacific part of the frame (${pxPalau})`);

// Gestures: a wheel zooms only with Ctrl or Cmd held or while the map is active; otherwise the page scrolls.
assert.equal(wheelZooms({ctrlKey: false, metaKey: false}, false), false, "plain wheel over an inactive map scrolls the page");
assert.equal(wheelZooms({ctrlKey: true, metaKey: false}, false), true, "Ctrl+wheel zooms without a click");
assert.equal(wheelZooms({ctrlKey: false, metaKey: true}, false), true, "Cmd+wheel zooms without a click");
assert.equal(wheelZooms({ctrlKey: false, metaKey: false}, true), true, "plain wheel zooms once the map is active");
// Activation: press or focus inside activates; Escape, focus leaving or a press outside deactivates.
let active = false;
active = nextActive(active, "inside"); assert.equal(active, true);
assert.equal(nextActive(active, "other"), true, "unknown events leave the state alone");
assert.equal(nextActive(active, "escape"), false);
active = nextActive(true, "leave"); assert.equal(active, false);
assert.equal(nextActive(true, "outside"), false);
// Touch: one finger scrolls the page (hint), two fingers or a mouse pan the map.
assert.equal(dragMode("touch", 1), "hint");
assert.equal(dragMode("touch", 2), "pan");
assert.equal(dragMode("mouse", 1), "pan");
assert.equal(dragMode("pen", 1), "pan");
assert.equal(TOUCH_HINT, "Use two fingers to move the map");
assert.match(WHEEL_HINT, /Hold Ctrl and scroll to zoom/);

console.log("explore zoom helpers: ok");
